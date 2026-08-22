# backend/core_engine.py
# ═══════════════════════════════════════════════════════════════════════════════
# RecoverIQ — AI-Powered Autonomous Revenue Recovery Engine
# Core FastAPI Backend: Webhook Processing, ML Prediction, Recovery Orchestration
# ═══════════════════════════════════════════════════════════════════════════════
# Track 3: AI Revenue Recovery | Razorpay AI Builder Internship 2026
# Author: Zahid Shaikh
# ═══════════════════════════════════════════════════════════════════════════════

import os
import json
import hmac
import hashlib
import sqlite3
import asyncio
import logging
import math
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
import joblib
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

# Local imports
from data_generator import (
    generate_batch,
    generate_feature_matrix,
    BANK_FAILURE_RATES,
    INSTRUMENT_FAILURE_MULTIPLIER,
    get_summary_stats,
)
from razorpay_simulator import (
    create_order,
    create_payment,
    simulate_failure,
    create_payment_link,
    generate_webhook_payload,
    verify_webhook_signature,
    simulate_transaction_batch,
)


# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================

DATABASE_PATH = os.getenv("DATABASE_URL", "recoveriq.db")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "recoveriq_test_secret")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
PORT = int(os.getenv("PORT", 8000))

# Recovery policy constants
MAX_RETRY_ATTEMPTS = 3          # Max retry attempts per payment
MAX_CONTACT_ATTEMPTS = 3        # Max outreach attempts per customer
COOLOFF_HOURS = 24              # Hours between retry cycles
PREEMPTIVE_THRESHOLD = 0.70     # Failure probability above this → preemptive switch
SMART_RETRY_THRESHOLD = 0.40    # Below this → safe to smart retry
ESCALATION_THRESHOLD = 3        # Contact count triggering manual escalation

# Model paths
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "failure_predictor.joblib")
SCALER_PATH = os.path.join(os.path.dirname(__file__), "models", "feature_scaler.joblib")

# Logging configuration
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("recoveriq")


# =============================================================================
# ENUMS
# =============================================================================

class RecoveryStrategy(str, Enum):
    """Available recovery strategies for failed payments."""
    SMART_RETRY = "smart_retry"           # Retry at optimal time
    PAYMENT_LINK_WHATSAPP = "payment_link_whatsapp"  # WhatsApp payment link
    PAYMENT_LINK_SMS = "payment_link_sms"  # SMS payment link
    PAYMENT_LINK_EMAIL = "payment_link_email"  # Email payment link
    PREEMPTIVE_SWITCH = "preemptive_switch"  # Switch instrument before failure
    ESCALATE = "escalate"                  # Manual review
    NO_ACTION = "no_action"                # Within cooloff or max attempts reached


class RecoveryStatus(str, Enum):
    """Status of a recovery action."""
    PENDING = "pending"
    ATTEMPTED = "attempted"
    RECOVERED = "recovered"
    FAILED = "failed"
    ESCALATED = "escalated"
    STOPPED = "stopped"      # Compliance stopping rule triggered


class EventType(str, Enum):
    """Webhook event types we handle."""
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_CAPTURED = "payment.captured"
    ORDER_PAID = "order.paid"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class TransactionRecord(BaseModel):
    """A processed transaction record in our system."""
    transaction_id: str
    order_id: str
    payment_id: str
    amount: int                     # Amount in paise
    currency: str = "INR"
    instrument: str
    bank: str
    status: str
    error_code: Optional[str] = None
    error_source: Optional[str] = None
    error_reason: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    failure_probability: Optional[float] = None
    created_at: str


class RecoveryAction(BaseModel):
    """A recovery action taken by the system."""
    action_id: str
    payment_id: str
    order_id: str
    amount: int
    strategy: RecoveryStrategy
    channel: Optional[str] = None
    status: RecoveryStatus
    reasoning: str
    contact_count: int = 0
    payment_link_id: Optional[str] = None
    payment_link_url: Optional[str] = None
    created_at: str
    updated_at: str


class WebhookEvent(BaseModel):
    """A webhook event logged in the idempotency ledger."""
    event_id: str
    payment_id: str
    event_type: str
    signature: str
    processed: bool = False
    created_at: str


class DashboardMetrics(BaseModel):
    """Real-time dashboard KPIs."""
    total_transactions: int
    total_failed: int
    total_recovered: int
    recovery_rate: float
    revenue_at_risk: int            # In paise
    revenue_recovered: int          # In paise
    active_recoveries: int
    avg_recovery_time_minutes: float
    top_failing_bank: Optional[str] = None
    top_recovery_channel: Optional[str] = None


class SimulationRequest(BaseModel):
    """Request body for triggering a batch simulation."""
    batch_size: int = Field(default=50, ge=5, le=500)
    failure_rate: float = Field(default=0.15, ge=0.05, le=0.50)


# =============================================================================
# DATABASE LAYER
# =============================================================================

def get_db() -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent performance
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database() -> None:
    """Initialize the SQLite database with all required tables."""
    conn = get_db()
    cursor = conn.cursor()

    # Transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            payment_id TEXT UNIQUE NOT NULL,
            amount INTEGER NOT NULL,
            currency TEXT DEFAULT 'INR',
            instrument TEXT,
            bank TEXT,
            status TEXT NOT NULL,
            error_code TEXT,
            error_source TEXT,
            error_reason TEXT,
            customer_email TEXT,
            customer_phone TEXT,
            failure_probability REAL,
            created_at TEXT NOT NULL,
            version INTEGER DEFAULT 1
        )
    """)

    # Webhook event ledger — for idempotent processing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS webhook_events (
            event_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            signature TEXT NOT NULL,
            payload TEXT,
            processed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            UNIQUE(payment_id, event_type, signature)
        )
    """)

    # Recovery actions — audit trail
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recovery_actions (
            action_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            strategy TEXT NOT NULL,
            channel TEXT,
            status TEXT NOT NULL,
            reasoning TEXT NOT NULL,
            contact_count INTEGER DEFAULT 0,
            payment_link_id TEXT,
            payment_link_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Indices for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_status ON transactions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_payment ON transactions(payment_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhook_payment ON webhook_events(payment_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recovery_payment ON recovery_actions(payment_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recovery_status ON recovery_actions(status)")

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")


# =============================================================================
# ML PREDICTION ENGINE
# =============================================================================

class FailurePredictionEngine:
    """
    ML engine for predicting payment failure probability.
    Uses a pre-trained GradientBoosting model with 12 engineered features.
    Falls back to heuristic scoring if no trained model is available.
    """

    def __init__(self):
        self.model = None
        self.scaler = None
        self.is_loaded = False
        self._load_model()

    def _load_model(self) -> None:
        """Attempt to load the pre-trained model and scaler."""
        try:
            if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
                self.model = joblib.load(MODEL_PATH)
                self.scaler = joblib.load(SCALER_PATH)
                self.is_loaded = True
                logger.info("ML model loaded successfully")
            else:
                logger.warning("No pre-trained model found. Using heuristic fallback.")
        except Exception as e:
            logger.error(f"Failed to load model: {e}. Using heuristic fallback.")

    def predict(
        self,
        bank: str,
        instrument: str,
        amount: int,
        hour: int,
        day_of_week: int,
        day_of_month: int,
    ) -> float:
        """
        Predict the failure probability for a transaction.
        
        Args:
            bank: Bank name
            instrument: Payment instrument type
            amount: Transaction amount in INR
            hour: Hour of day (0-23)
            day_of_week: Day of week (0=Mon, 6=Sun)
            day_of_month: Day of month (1-31)
        
        Returns:
            float: Failure probability between 0 and 1
        """
        if self.is_loaded:
            return self._predict_ml(bank, instrument, amount, hour, day_of_week, day_of_month)
        else:
            return self._predict_heuristic(bank, instrument, amount, hour, day_of_week, day_of_month)

    def _predict_ml(
        self, bank, instrument, amount, hour, day_of_week, day_of_month
    ) -> float:
        """Predict using the trained ML model."""
        features = self._engineer_features(bank, instrument, amount, hour, day_of_week, day_of_month)
        features_scaled = self.scaler.transform([features])
        prob = self.model.predict_proba(features_scaled)[0][1]
        return round(float(prob), 4)

    def _predict_heuristic(
        self, bank, instrument, amount, hour, day_of_week, day_of_month
    ) -> float:
        """Fallback heuristic prediction when no ML model is available."""
        base_rate = BANK_FAILURE_RATES.get(bank, 0.015)
        inst_mult = INSTRUMENT_FAILURE_MULTIPLIER.get(instrument, 1.0)

        # Time-of-day multiplier
        if 1 <= hour <= 4:
            hour_mult = 2.5
        elif 9 <= hour <= 10:
            hour_mult = 1.9
        elif 14 <= hour <= 17:
            hour_mult = 0.6
        else:
            hour_mult = 1.0

        # Weekend multiplier
        dow_mult = 1.3 if day_of_week >= 5 else 1.0

        # Salary day multiplier
        sal_mult = 1.4 if day_of_month in [1, 5, 10] else 1.0

        prob = base_rate * inst_mult * hour_mult * dow_mult * sal_mult
        return round(min(prob, 0.20), 4)

    def _engineer_features(
        self, bank, instrument, amount, hour, day_of_week, day_of_month
    ) -> list:
        """
        Engineer the 12 features expected by the model.
        Must match the order in data_generator.generate_feature_matrix().
        """
        bank_rate = BANK_FAILURE_RATES.get(bank, 0.015)
        inst_mult = INSTRUMENT_FAILURE_MULTIPLIER.get(instrument, 1.0)

        # Time-of-day multiplier
        if 1 <= hour <= 4:
            hour_fail_mult = 2.5
        elif hour == 5:
            hour_fail_mult = 1.8
        elif 9 <= hour <= 10:
            hour_fail_mult = 1.9
        elif 23 <= hour or hour == 0:
            hour_fail_mult = 1.6
        elif 14 <= hour <= 17:
            hour_fail_mult = 0.6
        elif 10 <= hour <= 13:
            hour_fail_mult = 0.8
        else:
            hour_fail_mult = 1.0

        features = [
            bank_rate,                                          # bank_failure_rate
            inst_mult,                                          # instrument_multiplier
            math.sin(2 * math.pi * hour / 24),                 # hour_sin
            math.cos(2 * math.pi * hour / 24),                 # hour_cos
            math.sin(2 * math.pi * day_of_week / 7),           # dow_sin
            math.cos(2 * math.pi * day_of_week / 7),           # dow_cos
            math.log1p(amount),                                 # amount_log
            int(day_of_week >= 5),                              # is_weekend
            int(day_of_month in [1, 5, 10]),                    # is_salary_day
            int(1 <= hour <= 4),                                # is_maintenance_window
            hour_fail_mult,                                     # hour_failure_mult
            bank_rate,                                          # rolling_bank_failure (approx)
        ]
        return features


# =============================================================================
# RECOVERY ORCHESTRATOR — The Decision Engine
# =============================================================================

class RecoveryOrchestrator:
    """
    Autonomous recovery decision engine.
    
    Implements the core Detect → Diagnose → Choose → Execute workflow:
    1. Checks idempotency (has this payment already been processed?)
    2. Checks stopping rules (max attempts, cooloff period)
    3. Selects optimal recovery strategy
    4. Executes the recovery action
    5. Logs everything to the audit trail
    """

    def __init__(self, prediction_engine: FailurePredictionEngine, event_queue: asyncio.Queue):
        self.predictor = prediction_engine
        self.event_queue = event_queue

    async def process_failed_payment(
        self,
        payment_id: str,
        order_id: str,
        amount: int,
        bank: str,
        instrument: str,
        error_source: str,
        error_reason: str,
        customer_email: Optional[str] = None,
        customer_phone: Optional[str] = None,
    ) -> RecoveryAction:
        """
        Process a failed payment and determine the recovery strategy.
        
        This is the main entry point for the recovery workflow.
        """
        conn = get_db()

        # Step 1: Check contact count for this customer/payment
        contact_count = self._get_contact_count(conn, payment_id)

        # Step 2: Check stopping rules
        if contact_count >= MAX_CONTACT_ATTEMPTS:
            action = self._create_action(
                payment_id=payment_id,
                order_id=order_id,
                amount=amount,
                strategy=RecoveryStrategy.ESCALATE,
                channel="manual_review",
                status=RecoveryStatus.ESCALATED,
                reasoning=f"Stopping rule triggered: {contact_count}/{MAX_CONTACT_ATTEMPTS} contact attempts exhausted. Escalated to manual review for compliance.",
                contact_count=contact_count,
            )
            self._save_action(conn, action)
            await self._push_event("recovery_escalated", action)
            conn.close()
            return action

        # Step 3: Check cooloff period
        if self._is_in_cooloff(conn, payment_id):
            action = self._create_action(
                payment_id=payment_id,
                order_id=order_id,
                amount=amount,
                strategy=RecoveryStrategy.NO_ACTION,
                status=RecoveryStatus.STOPPED,
                reasoning=f"Cooloff period active ({COOLOFF_HOURS}h). No action taken.",
                contact_count=contact_count,
            )
            self._save_action(conn, action)
            conn.close()
            return action

        # Step 4: Predict failure probability for retry
        now = datetime.now()
        failure_prob = self.predictor.predict(
            bank=bank,
            instrument=instrument,
            amount=amount // 100,  # Convert paise to INR
            hour=now.hour,
            day_of_week=now.weekday(),
            day_of_month=now.day,
        )

        # Step 5: Select strategy based on error source and prediction
        strategy, channel, reasoning = self._select_strategy(
            error_source=error_source,
            error_reason=error_reason,
            failure_prob=failure_prob,
            contact_count=contact_count,
            bank=bank,
            instrument=instrument,
        )

        # Step 6: Execute recovery action
        payment_link_id = None
        payment_link_url = None

        if strategy in [
            RecoveryStrategy.PAYMENT_LINK_WHATSAPP,
            RecoveryStrategy.PAYMENT_LINK_SMS,
            RecoveryStrategy.PAYMENT_LINK_EMAIL,
        ]:
            # Create a Razorpay payment link
            link = create_payment_link(
                amount=amount,
                customer_email=customer_email or "customer@example.com",
                customer_phone=customer_phone or "+919876543210",
                description=f"Complete your payment of ₹{amount // 100:,}",
            )
            payment_link_id = link["id"]
            payment_link_url = link["short_url"]

        # Step 7: Create and save the action
        action = self._create_action(
            payment_id=payment_id,
            order_id=order_id,
            amount=amount,
            strategy=strategy,
            channel=channel,
            status=RecoveryStatus.ATTEMPTED,
            reasoning=reasoning,
            contact_count=contact_count + 1,
            payment_link_id=payment_link_id,
            payment_link_url=payment_link_url,
        )
        self._save_action(conn, action)
        await self._push_event("recovery_attempted", action)

        conn.close()
        logger.info(f"Recovery action created: {action.action_id} | {strategy} | {channel}")
        return action

    def _select_strategy(
        self,
        error_source: str,
        error_reason: str,
        failure_prob: float,
        contact_count: int,
        bank: str,
        instrument: str,
    ) -> tuple[RecoveryStrategy, str, str]:
        """
        Select the optimal recovery strategy.
        
        Decision tree:
        1. If failure_prob > 0.70 → preemptive instrument switch
        2. If error_source == 'gateway' → smart retry (bank-side issue, retryable)
        3. If error_source == 'customer' → payment link via optimal channel
        4. Channel waterfall: WhatsApp > SMS > Email (based on contact count)
        """
        if failure_prob > PREEMPTIVE_THRESHOLD:
            return (
                RecoveryStrategy.PREEMPTIVE_SWITCH,
                "instrument_switch",
                f"High failure probability ({failure_prob:.2%}) for {bank}/{instrument}. "
                f"Recommending instrument switch to reduce re-failure risk. "
                f"Alternative: UPI if currently card, or card if currently UPI.",
            )

        if error_source == "gateway":
            # Gateway errors are transient — smart retry at optimal window
            return (
                RecoveryStrategy.SMART_RETRY,
                "auto_retry",
                f"Gateway error ({error_reason}) detected from {bank}. "
                f"Current failure probability: {failure_prob:.2%}. "
                f"Scheduling smart retry during optimal bank uptime window (2-6 PM IST).",
            )

        # Customer errors — send payment link via optimal channel
        # Waterfall: WhatsApp (highest conversion) → SMS → Email
        if contact_count == 0:
            return (
                RecoveryStrategy.PAYMENT_LINK_WHATSAPP,
                "whatsapp",
                f"Customer error ({error_reason}). First contact attempt. "
                f"Sending branded WhatsApp payment link (28% conversion rate). "
                f"Failure probability for retry: {failure_prob:.2%}.",
            )
        elif contact_count == 1:
            return (
                RecoveryStrategy.PAYMENT_LINK_SMS,
                "sms",
                f"Customer error ({error_reason}). Second contact attempt. "
                f"Sending SMS payment link (18% conversion rate). "
                f"WhatsApp link sent previously; escalating to SMS.",
            )
        else:
            return (
                RecoveryStrategy.PAYMENT_LINK_EMAIL,
                "email",
                f"Customer error ({error_reason}). Third/final contact attempt. "
                f"Sending email payment link (11% conversion rate). "
                f"Previous attempts: WhatsApp, SMS. Next step: escalation.",
            )

    def _get_contact_count(self, conn: sqlite3.Connection, payment_id: str) -> int:
        """Get the number of recovery contact attempts for a payment."""
        cursor = conn.execute(
            "SELECT COUNT(*) FROM recovery_actions WHERE payment_id = ? AND status != ?",
            (payment_id, RecoveryStatus.STOPPED.value),
        )
        return cursor.fetchone()[0]

    def _is_in_cooloff(self, conn: sqlite3.Connection, payment_id: str) -> bool:
        """Check if the payment is within the cooloff period."""
        cooloff_cutoff = (datetime.now() - timedelta(hours=COOLOFF_HOURS)).isoformat()
        cursor = conn.execute(
            "SELECT COUNT(*) FROM recovery_actions WHERE payment_id = ? AND created_at > ? AND strategy != ?",
            (payment_id, cooloff_cutoff, RecoveryStrategy.NO_ACTION.value),
        )
        return cursor.fetchone()[0] > 0

    def _create_action(self, **kwargs) -> RecoveryAction:
        """Create a RecoveryAction with generated ID and timestamps."""
        now = datetime.now().isoformat()
        return RecoveryAction(
            action_id=f"act_{uuid.uuid4().hex[:12]}",
            created_at=now,
            updated_at=now,
            **kwargs,
        )

    def _save_action(self, conn: sqlite3.Connection, action: RecoveryAction) -> None:
        """Persist a recovery action to the database."""
        conn.execute(
            """INSERT INTO recovery_actions 
               (action_id, payment_id, order_id, amount, strategy, channel, 
                status, reasoning, contact_count, payment_link_id, payment_link_url,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                action.action_id, action.payment_id, action.order_id,
                action.amount, action.strategy.value, action.channel,
                action.status.value, action.reasoning, action.contact_count,
                action.payment_link_id, action.payment_link_url,
                action.created_at, action.updated_at,
            ),
        )
        conn.commit()

    async def _push_event(self, event_type: str, action: RecoveryAction) -> None:
        """Push a recovery event to the SSE queue for real-time dashboard updates."""
        event = {
            "type": event_type,
            "data": {
                "action_id": action.action_id,
                "payment_id": action.payment_id,
                "amount": action.amount,
                "strategy": action.strategy.value,
                "channel": action.channel,
                "status": action.status.value,
                "reasoning": action.reasoning,
                "timestamp": action.updated_at,
            },
        }
        await self.event_queue.put(event)


# =============================================================================
# SSE EVENT STREAM
# =============================================================================

# Global event queue for SSE
event_queue: asyncio.Queue = asyncio.Queue()


async def event_stream():
    """Generator for Server-Sent Events stream."""
    while True:
        try:
            event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
            data = json.dumps(event)
            yield f"event: {event['type']}\ndata: {data}\n\n"
        except asyncio.TimeoutError:
            # Send heartbeat to keep connection alive
            yield f"event: heartbeat\ndata: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now().isoformat()})}\n\n"


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

# Initialize engines
prediction_engine = FailurePredictionEngine()
recovery_orchestrator = RecoveryOrchestrator(prediction_engine, event_queue)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    logger.info("=" * 60)
    logger.info("RecoverIQ — Starting up...")
    logger.info("=" * 60)
    init_database()
    logger.info(f"ML Model loaded: {prediction_engine.is_loaded}")
    logger.info(f"Database: {DATABASE_PATH}")
    logger.info("RecoverIQ ready! 🚀")
    yield
    # Shutdown
    logger.info("RecoverIQ shutting down...")


app = FastAPI(
    title="RecoverIQ API",
    description="AI-Powered Autonomous Revenue Recovery Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# API ENDPOINTS
# =============================================================================

# ---- Health Check ----

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "RecoverIQ",
        "version": "1.0.0",
        "ml_model_loaded": prediction_engine.is_loaded,
        "timestamp": datetime.now().isoformat(),
    }


# ---- Webhook Receiver ----

@app.post("/api/webhooks/razorpay")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive and process Razorpay webhooks with idempotent handling.
    
    Flow:
    1. Verify HMAC SHA256 signature
    2. Check idempotency (deduplicate by composite key)
    3. Process the event (trigger recovery if payment.failed)
    4. Return 200 immediately (heavy processing in background)
    """
    body = await request.body()
    payload = await request.json()

    # Step 1: Verify signature
    signature = request.headers.get("x-razorpay-signature", "")
    if signature:
        expected = hmac.new(
            RAZORPAY_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # Step 2: Extract event data
    event_type = payload.get("event", "")
    payment_data = payload.get("payload", {}).get("payment", {}).get("entity", {})
    payment_id = payment_data.get("id", f"pay_{uuid.uuid4().hex[:14]}")

    # Step 3: Idempotency check
    conn = get_db()
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    sig_hash = hashlib.sha256(f"{payment_id}:{event_type}:{signature}".encode()).hexdigest()[:32]

    try:
        conn.execute(
            """INSERT INTO webhook_events (event_id, payment_id, event_type, signature, payload, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_id, payment_id, event_type, sig_hash, json.dumps(payload), datetime.now().isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        logger.info(f"Duplicate webhook ignored: {payment_id}/{event_type}")
        return {"status": "duplicate", "message": "Event already processed"}

    # Step 4: Store transaction
    txn_id = f"txn_{uuid.uuid4().hex[:12]}"
    try:
        conn.execute(
            """INSERT OR REPLACE INTO transactions 
               (transaction_id, order_id, payment_id, amount, instrument, bank, 
                status, error_code, error_source, error_reason, customer_email, customer_phone,
                failure_probability, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                txn_id,
                payment_data.get("order_id", ""),
                payment_id,
                payment_data.get("amount", 0),
                payment_data.get("method", "unknown"),
                payment_data.get("bank", "unknown"),
                payment_data.get("status", "unknown"),
                payment_data.get("error_code"),
                payment_data.get("error_source"),
                payment_data.get("error_reason"),
                payment_data.get("email"),
                payment_data.get("contact"),
                None,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to store transaction: {e}")

    conn.close()

    # Step 5: Trigger recovery for failed payments (in background)
    if event_type == "payment.failed":
        background_tasks.add_task(
            _process_failed_payment_background,
            payment_id=payment_id,
            order_id=payment_data.get("order_id", ""),
            amount=payment_data.get("amount", 0),
            bank=payment_data.get("bank", "unknown"),
            instrument=payment_data.get("method", "unknown"),
            error_source=payment_data.get("error_source", "unknown"),
            error_reason=payment_data.get("error_reason", "unknown"),
            customer_email=payment_data.get("email"),
            customer_phone=payment_data.get("contact"),
        )

    # Step 6: Handle successful recovery (payment.captured after a recovery link)
    if event_type == "payment.captured":
        background_tasks.add_task(
            _process_recovery_success_background,
            payment_id=payment_id,
            order_id=payment_data.get("order_id", ""),
            amount=payment_data.get("amount", 0),
        )

    return {"status": "received", "event_id": event_id}


async def _process_failed_payment_background(**kwargs):
    """Background task to process a failed payment."""
    try:
        await recovery_orchestrator.process_failed_payment(**kwargs)
    except Exception as e:
        logger.error(f"Recovery processing failed: {e}")


async def _process_recovery_success_background(payment_id: str, order_id: str, amount: int):
    """Background task to mark a recovery as successful."""
    conn = get_db()
    now = datetime.now().isoformat()

    # Update any pending recovery actions for this order to 'recovered'
    conn.execute(
        """UPDATE recovery_actions SET status = ?, updated_at = ?
           WHERE order_id = ? AND status IN (?, ?)""",
        (RecoveryStatus.RECOVERED.value, now, order_id,
         RecoveryStatus.ATTEMPTED.value, RecoveryStatus.PENDING.value),
    )
    conn.commit()
    conn.close()

    # Push success event to SSE
    await event_queue.put({
        "type": "recovery_success",
        "data": {
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": amount,
            "status": "recovered",
            "timestamp": now,
        },
    })
    logger.info(f"Recovery successful: {payment_id} | ₹{amount // 100:,}")


# ---- Dashboard Endpoints ----

@app.get("/api/dashboard/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics():
    """Get real-time dashboard KPIs aggregated from the database."""
    conn = get_db()

    # Total transactions
    total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM transactions WHERE status = 'failed'").fetchone()[0]

    # Recovery stats
    recovered = conn.execute(
        "SELECT COUNT(*) FROM recovery_actions WHERE status = ?",
        (RecoveryStatus.RECOVERED.value,)
    ).fetchone()[0]

    active = conn.execute(
        "SELECT COUNT(*) FROM recovery_actions WHERE status IN (?, ?)",
        (RecoveryStatus.PENDING.value, RecoveryStatus.ATTEMPTED.value)
    ).fetchone()[0]

    # Revenue calculations
    revenue_at_risk = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE status = 'failed'"
    ).fetchone()[0]

    revenue_recovered = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM recovery_actions WHERE status = ?",
        (RecoveryStatus.RECOVERED.value,)
    ).fetchone()[0]

    # Top failing bank
    top_bank_row = conn.execute(
        """SELECT bank, COUNT(*) as cnt FROM transactions 
           WHERE status = 'failed' GROUP BY bank ORDER BY cnt DESC LIMIT 1"""
    ).fetchone()
    top_bank = top_bank_row["bank"] if top_bank_row else None

    # Top recovery channel
    top_channel_row = conn.execute(
        """SELECT channel, COUNT(*) as cnt FROM recovery_actions 
           WHERE status = ? AND channel IS NOT NULL 
           GROUP BY channel ORDER BY cnt DESC LIMIT 1""",
        (RecoveryStatus.RECOVERED.value,)
    ).fetchone()
    top_channel = top_channel_row["channel"] if top_channel_row else None

    # Average recovery time (minutes between creation and recovery)
    avg_time = 0.0
    recovered_actions = conn.execute(
        """SELECT created_at, updated_at FROM recovery_actions WHERE status = ?""",
        (RecoveryStatus.RECOVERED.value,)
    ).fetchall()
    if recovered_actions:
        deltas = []
        for row in recovered_actions:
            try:
                created = datetime.fromisoformat(row["created_at"])
                updated = datetime.fromisoformat(row["updated_at"])
                deltas.append((updated - created).total_seconds() / 60)
            except Exception:
                pass
        avg_time = round(np.mean(deltas), 1) if deltas else 0.0

    conn.close()

    recovery_rate = round((recovered / failed * 100), 1) if failed > 0 else 0.0

    return DashboardMetrics(
        total_transactions=total,
        total_failed=failed,
        total_recovered=recovered,
        recovery_rate=recovery_rate,
        revenue_at_risk=revenue_at_risk,
        revenue_recovered=revenue_recovered,
        active_recoveries=active,
        avg_recovery_time_minutes=avg_time,
        top_failing_bank=top_bank,
        top_recovery_channel=top_channel,
    )


@app.get("/api/dashboard/timeline")
async def get_recovery_timeline(limit: int = 50):
    """Get the recovery action timeline (most recent first)."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM recovery_actions ORDER BY created_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()

    return [dict(row) for row in rows]


@app.get("/api/dashboard/analytics")
async def get_analytics():
    """
    Get analytics data for charts:
    - Failure heatmap (bank × hour)
    - Channel performance
    - Failure reason breakdown
    - Recovery trend (hourly)
    """
    conn = get_db()

    # Failure heatmap: bank × hour
    heatmap_rows = conn.execute(
        """SELECT bank, 
                  CAST(strftime('%H', created_at) AS INTEGER) as hour, 
                  COUNT(*) as count
           FROM transactions WHERE status = 'failed'
           GROUP BY bank, hour"""
    ).fetchall()
    heatmap = [{"bank": r["bank"], "hour": r["hour"], "count": r["count"]} for r in heatmap_rows]

    # Channel performance (conversion rates)
    channel_stats = []
    for channel in ["whatsapp", "sms", "email", "auto_retry", "instrument_switch"]:
        total = conn.execute(
            "SELECT COUNT(*) FROM recovery_actions WHERE channel = ?", (channel,)
        ).fetchone()[0]
        recovered = conn.execute(
            "SELECT COUNT(*) FROM recovery_actions WHERE channel = ? AND status = ?",
            (channel, RecoveryStatus.RECOVERED.value)
        ).fetchone()[0]
        if total > 0:
            channel_stats.append({
                "channel": channel,
                "total_attempts": total,
                "recovered": recovered,
                "conversion_rate": round(recovered / total * 100, 1),
            })

    # Failure reason breakdown
    reason_rows = conn.execute(
        """SELECT error_reason, COUNT(*) as count 
           FROM transactions WHERE status = 'failed' AND error_reason IS NOT NULL
           GROUP BY error_reason ORDER BY count DESC"""
    ).fetchall()
    failure_reasons = [{"reason": r["error_reason"], "count": r["count"]} for r in reason_rows]

    # Recovery trend (last 24 hours, hourly)
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    trend_rows = conn.execute(
        """SELECT strftime('%H', created_at) as hour, 
                  status, COUNT(*) as count
           FROM recovery_actions WHERE created_at > ?
           GROUP BY hour, status""",
        (cutoff,),
    ).fetchall()
    trend = [{"hour": r["hour"], "status": r["status"], "count": r["count"]} for r in trend_rows]

    conn.close()

    return {
        "heatmap": heatmap,
        "channel_performance": channel_stats,
        "failure_reasons": failure_reasons,
        "recovery_trend": trend,
    }


# ---- SSE Stream ----

@app.get("/api/stream/events")
async def sse_stream():
    """Server-Sent Events endpoint for real-time dashboard updates."""
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---- Simulation ----

@app.post("/api/simulate/batch")
async def simulate_batch(req: SimulationRequest, background_tasks: BackgroundTasks):
    """
    Trigger a batch of simulated transactions for demo purposes.
    Creates orders, simulates payments (some fail), and processes webhooks.
    """
    batch = simulate_transaction_batch(n=req.batch_size, failure_rate=req.failure_rate)

    processed = 0
    failed_count = 0

    for txn in batch:
        payment = txn["payment"]
        webhook_payload = txn["webhook"]["payload"]
        webhook_sig = txn["webhook"]["signature"]

        # Store the transaction
        conn = get_db()
        txn_id = f"txn_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        try:
            conn.execute(
                """INSERT OR REPLACE INTO transactions 
                   (transaction_id, order_id, payment_id, amount, instrument, bank,
                    status, error_code, error_source, error_reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    txn_id, txn["order"]["id"], payment["id"],
                    payment["amount"], txn["method"], txn["bank"],
                    payment["status"], payment.get("error_code"),
                    payment.get("error_source"), payment.get("error_reason"),
                    now,
                ),
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to store simulated txn: {e}")
        finally:
            conn.close()

        # Process failed payments through recovery
        if txn["is_failed"]:
            failed_count += 1
            background_tasks.add_task(
                _process_failed_payment_background,
                payment_id=payment["id"],
                order_id=txn["order"]["id"],
                amount=payment["amount"],
                bank=txn["bank"],
                instrument=txn["method"],
                error_source=payment.get("error_source", "gateway"),
                error_reason=payment.get("error_reason", "bank_timeout"),
            )

            # Simulate some recoveries (34% of failed payments recover)
            if np.random.random() < 0.34:
                background_tasks.add_task(
                    _process_recovery_success_background,
                    payment_id=payment["id"],
                    order_id=txn["order"]["id"],
                    amount=payment["amount"],
                )

        processed += 1

    # Push batch event to SSE
    await event_queue.put({
        "type": "batch_simulated",
        "data": {
            "total": processed,
            "failed": failed_count,
            "timestamp": datetime.now().isoformat(),
        },
    })

    return {
        "status": "simulation_complete",
        "total_processed": processed,
        "total_failed": failed_count,
        "recovery_processing": True,
    }


# ---- Audit Log ----

@app.get("/api/audit/log")
async def get_audit_log(limit: int = 100, offset: int = 0):
    """Full audit trail of all recovery actions with pagination."""
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM recovery_actions").fetchone()[0]
    rows = conn.execute(
        "SELECT * FROM recovery_actions ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "actions": [dict(row) for row in rows],
    }


# ---- Prediction Endpoint ----

@app.get("/api/predict")
async def predict_failure(
    bank: str = "SBI",
    instrument: str = "UPI",
    amount: int = 1000,
):
    """
    Predict failure probability for a given transaction configuration.
    Useful for preemptive instrument switching.
    """
    now = datetime.now()
    prob = prediction_engine.predict(
        bank=bank,
        instrument=instrument,
        amount=amount,
        hour=now.hour,
        day_of_week=now.weekday(),
        day_of_month=now.day,
    )

    risk_level = "LOW" if prob < 0.03 else "MEDIUM" if prob < PREEMPTIVE_THRESHOLD else "HIGH"

    return {
        "bank": bank,
        "instrument": instrument,
        "amount": amount,
        "failure_probability": prob,
        "risk_level": risk_level,
        "recommendation": "preemptive_switch" if prob > PREEMPTIVE_THRESHOLD else "proceed",
        "timestamp": now.isoformat(),
    }


# ---- Seed Demo Data ----

@app.post("/api/seed/demo")
async def seed_demo_data():
    """
    Pre-populate the database with rich historical demo data for impressive charts.
    Creates 500 transactions spread across 7 days with varied hours, banks, instruments.
    Generates recovery actions with multiple channels and statuses.
    """
    import random as rng
    rng.seed(42)

    conn = get_db()

    banks = list(BANK_FAILURE_RATES.keys())
    instruments = ["upi", "card", "netbanking", "wallet"]
    inst_weights = [60, 30, 7, 3]
    failure_reasons_gateway = ["bank_timeout", "network_error", "gateway_unavailable", "processing_error"]
    failure_reasons_customer = ["insufficient_funds", "otp_expired", "authentication_failed", "card_expired", "daily_limit_exceeded", "payment_cancelled"]
    channels = ["whatsapp", "sms", "email", "auto_retry", "instrument_switch"]
    strategies = ["payment_link_whatsapp", "payment_link_sms", "payment_link_email", "smart_retry", "preemptive_switch"]
    statuses_map = {
        "whatsapp": ("payment_link_whatsapp", 0.35),
        "sms": ("payment_link_sms", 0.22),
        "email": ("payment_link_email", 0.14),
        "auto_retry": ("smart_retry", 0.45),
        "instrument_switch": ("preemptive_switch", 0.50),
    }

    now = datetime.now()
    txn_count = 0
    failed_count = 0
    recovered_count = 0

    for i in range(500):
        # Spread across last 7 days with varied hours
        hours_ago = rng.randint(0, 168)  # 7 days in hours
        txn_time = now - timedelta(hours=hours_ago, minutes=rng.randint(0, 59))
        hour = txn_time.hour

        bank = rng.choice(banks)
        instrument = rng.choices(instruments, weights=inst_weights, k=1)[0]
        amount_inr = rng.randint(99, 49999)
        amount_paise = amount_inr * 100

        # Failure probability based on bank and hour
        base_rate = BANK_FAILURE_RATES[bank]
        if 1 <= hour <= 4:
            fail_mult = 2.5
        elif 9 <= hour <= 10:
            fail_mult = 1.9
        elif 14 <= hour <= 17:
            fail_mult = 0.6
        else:
            fail_mult = 1.0

        actual_rate = min(base_rate * fail_mult * rng.uniform(0.8, 3.0), 0.20)
        is_failed = rng.random() < actual_rate

        txn_id = f"txn_{uuid.uuid4().hex[:12]}"
        order_id = f"order_{uuid.uuid4().hex[:14]}"
        payment_id = f"pay_{uuid.uuid4().hex[:14]}"

        error_source = None
        error_reason = None
        error_code = None

        if is_failed:
            error_source = rng.choice(["gateway", "customer"])
            if error_source == "gateway":
                error_reason = rng.choice(failure_reasons_gateway)
            else:
                error_reason = rng.choice(failure_reasons_customer)
            error_code = "GATEWAY_ERROR" if error_source == "gateway" else "BAD_REQUEST_ERROR"
            failed_count += 1

        try:
            conn.execute(
                """INSERT OR IGNORE INTO transactions
                   (transaction_id, order_id, payment_id, amount, instrument, bank,
                    status, error_code, error_source, error_reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    txn_id, order_id, payment_id, amount_paise,
                    instrument, bank,
                    "failed" if is_failed else "captured",
                    error_code, error_source, error_reason,
                    txn_time.isoformat(),
                ),
            )
        except Exception:
            pass

        # Create recovery actions for failed payments
        if is_failed:
            channel = rng.choice(channels)
            strategy, recovery_rate = statuses_map[channel]
            is_recovered = rng.random() < recovery_rate

            action_time = txn_time + timedelta(minutes=rng.randint(1, 30))
            recovery_time = action_time + timedelta(minutes=rng.randint(5, 120)) if is_recovered else action_time

            status = "recovered" if is_recovered else rng.choice(["attempted", "escalated"])
            if is_recovered:
                recovered_count += 1

            reasoning_templates = {
                "whatsapp": f"Customer error ({error_reason}). Sent branded WhatsApp payment link. {'Customer completed payment via link.' if is_recovered else 'Awaiting customer action.'}",
                "sms": f"Customer error ({error_reason}). Sent SMS payment link to customer phone. {'Payment completed successfully.' if is_recovered else 'No response yet.'}",
                "email": f"Customer error ({error_reason}). Sent email payment link. {'Customer paid via email link.' if is_recovered else 'Email pending open.'}",
                "auto_retry": f"Gateway error ({error_reason}) from {bank}. Scheduled smart retry during optimal window. {'Retry succeeded.' if is_recovered else 'Retry pending.'}",
                "instrument_switch": f"High failure probability for {bank}/{instrument}. Recommended instrument switch. {'Customer switched and paid.' if is_recovered else 'Switch suggestion sent.'}",
            }

            try:
                conn.execute(
                    """INSERT OR IGNORE INTO recovery_actions
                       (action_id, payment_id, order_id, amount, strategy, channel,
                        status, reasoning, contact_count, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f"act_{uuid.uuid4().hex[:12]}",
                        payment_id, order_id, amount_paise,
                        strategy, channel, status,
                        reasoning_templates[channel],
                        rng.randint(1, 3),
                        action_time.isoformat(),
                        recovery_time.isoformat(),
                    ),
                )
            except Exception:
                pass

        txn_count += 1

    conn.commit()
    conn.close()

    recovery_rate = round(recovered_count / failed_count * 100, 1) if failed_count > 0 else 0

    return {
        "status": "demo_data_seeded",
        "total_transactions": txn_count,
        "total_failed": failed_count,
        "total_recovered": recovered_count,
        "recovery_rate": recovery_rate,
        "time_range": "7 days",
        "message": f"Seeded {txn_count} transactions with {failed_count} failures and {recovered_count} recoveries ({recovery_rate}%)",
    }


# =============================================================================
# ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "core_engine:app",
        host="0.0.0.0",
        port=PORT,
        reload=True,
        log_level=LOG_LEVEL.lower(),
    )

