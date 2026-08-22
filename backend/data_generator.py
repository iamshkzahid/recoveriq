# backend/data_generator.py
# RecoverIQ — Synthetic Indian Payment Data Generator
# Generates realistic transaction data modeling the Indian digital payments ecosystem

import random
import uuid
import math
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd


# =============================================================================
# CONSTANTS — Indian Payment Ecosystem Parameters
# =============================================================================

# Bank-specific base failure rates (sourced from industry benchmarks)
BANK_FAILURE_RATES = {
    "SBI":       0.021,   # State Bank of India — legacy infra, highest volume
    "HDFC":      0.008,   # HDFC Bank — modern infra, lowest failure
    "ICICI":     0.012,   # ICICI Bank
    "Axis":      0.015,   # Axis Bank
    "Kotak":     0.010,   # Kotak Mahindra
    "PNB":       0.028,   # Punjab National Bank — older core banking
    "BOB":       0.025,   # Bank of Baroda
    "Yes Bank":  0.018,   # Yes Bank
    "IndusInd":  0.013,   # IndusInd Bank
    "Federal":   0.016,   # Federal Bank
    "IDBI":      0.022,   # IDBI Bank
    "Canara":    0.024,   # Canara Bank
}

# Payment instrument distribution (mirrors RBI FY2025-26 data)
INSTRUMENT_DISTRIBUTION = {
    "UPI":         0.60,
    "Credit Card": 0.15,
    "Debit Card":  0.15,
    "Net Banking": 0.07,
    "Wallet":      0.03,
}

# Instrument-specific failure multipliers
INSTRUMENT_FAILURE_MULTIPLIER = {
    "UPI":         1.0,   # baseline
    "Credit Card": 0.7,   # lower failure due to token-based auth
    "Debit Card":  1.2,   # higher — OTP dependency
    "Net Banking": 1.5,   # highest — redirect-based, session timeouts
    "Wallet":      0.4,   # lowest — pre-funded, minimal bank dependency
}

# Failure reason distribution by error source
FAILURE_REASONS = {
    "gateway": {
        "bank_timeout":        0.35,
        "network_error":       0.25,
        "gateway_unavailable": 0.20,
        "processing_error":    0.20,
    },
    "customer": {
        "insufficient_funds":   0.30,
        "otp_expired":          0.25,
        "authentication_failed": 0.20,
        "card_expired":         0.10,
        "daily_limit_exceeded": 0.10,
        "payment_cancelled":    0.05,
    },
}

# Transaction amount distribution (Indian e-commerce)
AMOUNT_RANGES = [
    (99,     499,    0.20),   # Small purchases (₹99-₹499)
    (500,    999,    0.18),   # Mid-small (₹500-₹999)
    (1000,   2999,   0.25),   # Mid-range (₹1,000-₹2,999)
    (3000,   9999,   0.20),   # Mid-high (₹3,000-₹9,999)
    (10000,  24999,  0.12),   # High-value (₹10,000-₹24,999)
    (25000,  49999,  0.05),   # Premium (₹25,000-₹49,999)
]

# Merchant categories for realistic simulation
MERCHANT_CATEGORIES = [
    "E-commerce", "Food Delivery", "Travel", "Education",
    "Subscription", "Grocery", "Electronics", "Fashion",
    "Healthcare", "Utilities",
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _generate_razorpay_id(prefix: str) -> str:
    """Generate a realistic Razorpay-format ID."""
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def _get_hour_failure_multiplier(hour: int) -> float:
    """
    Model time-of-day failure patterns in Indian banking.
    
    Higher failures during:
    - 1-5 AM: Bank maintenance windows
    - 9-10 AM: Salary processing spike (batch jobs)
    - 11 PM-12 AM: End-of-day reconciliation
    
    Lower failures during:
    - 2-6 PM: Stable banking hours
    """
    if 1 <= hour <= 4:
        return 2.5    # Maintenance window — 2.5x base rate
    elif hour == 5:
        return 1.8    # Winding down maintenance
    elif 9 <= hour <= 10:
        return 1.9    # Salary processing spike
    elif 23 <= hour or hour == 0:
        return 1.6    # End-of-day reconciliation
    elif 14 <= hour <= 17:
        return 0.6    # Stable hours — lowest failure
    elif 10 <= hour <= 13:
        return 0.8    # Normal business hours
    else:
        return 1.0    # Default


def _get_day_of_week_multiplier(day: int) -> float:
    """
    Model day-of-week patterns.
    day: 0=Monday, 6=Sunday
    
    Higher failures on:
    - Saturday/Sunday: Reduced bank IT staff
    - 1st of month: Salary credit + bill payment surge
    """
    if day >= 5:  # Weekend
        return 1.3
    elif day == 0:  # Monday — post-weekend batch processing
        return 1.15
    else:
        return 1.0


def _generate_amount() -> int:
    """Generate a realistic Indian e-commerce transaction amount."""
    ranges = AMOUNT_RANGES
    probabilities = [r[2] for r in ranges]
    selected = random.choices(ranges, weights=probabilities, k=1)[0]
    return random.randint(selected[0], selected[1])


def _select_weighted(distribution: dict) -> str:
    """Select a key from a weighted distribution dictionary."""
    keys = list(distribution.keys())
    weights = list(distribution.values())
    return random.choices(keys, weights=weights, k=1)[0]


def _generate_customer_id() -> str:
    """Generate a realistic customer identifier."""
    return f"cust_{uuid.uuid4().hex[:10]}"


def _generate_email(customer_id: str) -> str:
    """Generate a placeholder email for the customer."""
    domains = ["gmail.com", "yahoo.co.in", "outlook.com", "rediffmail.com"]
    return f"{customer_id}@{random.choice(domains)}"


def _generate_phone() -> str:
    """Generate a realistic Indian mobile number."""
    prefixes = ["98", "97", "96", "95", "94", "93", "91", "90", "89", "88", "87", "86", "85", "70", "76", "77", "78"]
    return f"+91{random.choice(prefixes)}{random.randint(10000000, 99999999)}"


# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate_batch(
    n: int = 500,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    seed: Optional[int] = 42,
) -> pd.DataFrame:
    """
    Generate a batch of synthetic Indian payment transactions.
    
    Args:
        n: Number of transactions to generate
        start_date: Start of the time range (default: 7 days ago)
        end_date: End of the time range (default: now)
        seed: Random seed for reproducibility
    
    Returns:
        pd.DataFrame with columns:
            - transaction_id, order_id, payment_id, customer_id
            - amount, currency, instrument, bank
            - merchant_category, timestamp, hour, day_of_week, day_of_month
            - is_failed, failure_reason, error_source
            - predicted_failure_prob (placeholder, filled by model)
            - customer_email, customer_phone
            - is_weekend, is_salary_day, is_maintenance_window
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    if start_date is None:
        start_date = datetime.now() - timedelta(days=7)
    if end_date is None:
        end_date = datetime.now()

    records = []
    time_range_seconds = int((end_date - start_date).total_seconds())

    # Pre-generate a pool of ~100 customers for realistic repeat patterns
    customer_pool_size = min(n // 3, 150)
    customer_pool = [
        {
            "customer_id": _generate_customer_id(),
            "email": None,
            "phone": _generate_phone(),
            "preferred_instrument": _select_weighted(INSTRUMENT_DISTRIBUTION),
            "preferred_bank": random.choice(list(BANK_FAILURE_RATES.keys())),
        }
        for _ in range(customer_pool_size)
    ]
    for c in customer_pool:
        c["email"] = _generate_email(c["customer_id"])

    for i in range(n):
        # Select a customer (repeat customers are realistic)
        customer = random.choice(customer_pool)

        # Generate timestamp with realistic distribution (more txns during business hours)
        random_offset = random.randint(0, time_range_seconds)
        timestamp = start_date + timedelta(seconds=random_offset)
        hour = timestamp.hour
        day_of_week = timestamp.weekday()
        day_of_month = timestamp.day

        # Select bank and instrument
        # 70% chance customer uses their preferred instrument/bank
        if random.random() < 0.7:
            instrument = customer["preferred_instrument"]
            bank = customer["preferred_bank"]
        else:
            instrument = _select_weighted(INSTRUMENT_DISTRIBUTION)
            bank = random.choice(list(BANK_FAILURE_RATES.keys()))

        # Calculate failure probability
        base_rate = BANK_FAILURE_RATES[bank]
        hour_mult = _get_hour_failure_multiplier(hour)
        dow_mult = _get_day_of_week_multiplier(day_of_week)
        instrument_mult = INSTRUMENT_FAILURE_MULTIPLIER[instrument]

        # Salary day spike (1st, 5th, 10th of month)
        salary_day_mult = 1.4 if day_of_month in [1, 5, 10] else 1.0

        # Combined failure probability (capped at 15%)
        failure_prob = min(
            base_rate * hour_mult * dow_mult * instrument_mult * salary_day_mult,
            0.15,
        )

        # Add random noise to prevent deterministic patterns
        failure_prob *= np.random.uniform(0.5, 2.0)
        failure_prob = min(failure_prob, 0.20)

        # Determine if this transaction fails
        is_failed = random.random() < failure_prob

        # Assign failure reason and error source
        failure_reason = None
        error_source = None
        if is_failed:
            # 60% gateway errors, 40% customer errors
            error_source = "gateway" if random.random() < 0.6 else "customer"
            failure_reason = _select_weighted(FAILURE_REASONS[error_source])

        # Generate amount
        amount = _generate_amount()

        # Build the record
        record = {
            "transaction_id": _generate_razorpay_id("txn"),
            "order_id": _generate_razorpay_id("order"),
            "payment_id": _generate_razorpay_id("pay"),
            "customer_id": customer["customer_id"],
            "customer_email": customer["email"],
            "customer_phone": customer["phone"],
            "amount": amount,
            "currency": "INR",
            "instrument": instrument,
            "bank": bank,
            "merchant_category": random.choice(MERCHANT_CATEGORIES),
            "timestamp": timestamp.isoformat(),
            "hour": hour,
            "day_of_week": day_of_week,
            "day_of_month": day_of_month,
            "is_weekend": int(day_of_week >= 5),
            "is_salary_day": int(day_of_month in [1, 5, 10]),
            "is_maintenance_window": int(1 <= hour <= 4),
            "is_failed": int(is_failed),
            "failure_reason": failure_reason,
            "error_source": error_source,
            "failure_probability_actual": round(failure_prob, 6),
            "predicted_failure_prob": None,  # To be filled by the ML model
        }
        records.append(record)

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df


def generate_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features from raw transaction data for the ML model.
    
    Features (12 total):
        1. bank_failure_rate       — Historical base failure rate for this bank
        2. instrument_multiplier   — Instrument-specific failure multiplier
        3. hour_sin                — Cyclical encoding of hour (sin component)
        4. hour_cos                — Cyclical encoding of hour (cos component)
        5. dow_sin                 — Cyclical encoding of day-of-week (sin)
        6. dow_cos                 — Cyclical encoding of day-of-week (cos)
        7. amount_log              — Log-transformed transaction amount
        8. is_weekend              — Binary: weekend flag
        9. is_salary_day           — Binary: salary day flag (1st, 5th, 10th)
        10. is_maintenance_window  — Binary: 1-4 AM maintenance flag
        11. hour_failure_mult      — Time-of-day failure multiplier
        12. rolling_bank_failure   — Rolling bank failure rate (last 50 txns)
    """
    features = pd.DataFrame()

    # Feature 1: Bank base failure rate
    features["bank_failure_rate"] = df["bank"].map(BANK_FAILURE_RATES)

    # Feature 2: Instrument failure multiplier
    features["instrument_multiplier"] = df["instrument"].map(INSTRUMENT_FAILURE_MULTIPLIER)

    # Features 3-4: Cyclical hour encoding (captures circular nature of time)
    features["hour_sin"] = np.sin(2 * math.pi * df["hour"] / 24)
    features["hour_cos"] = np.cos(2 * math.pi * df["hour"] / 24)

    # Features 5-6: Cyclical day-of-week encoding
    features["dow_sin"] = np.sin(2 * math.pi * df["day_of_week"] / 7)
    features["dow_cos"] = np.cos(2 * math.pi * df["day_of_week"] / 7)

    # Feature 7: Log-transformed amount (normalizes the skewed distribution)
    features["amount_log"] = np.log1p(df["amount"])

    # Features 8-10: Binary flags
    features["is_weekend"] = df["is_weekend"]
    features["is_salary_day"] = df["is_salary_day"]
    features["is_maintenance_window"] = df["is_maintenance_window"]

    # Feature 11: Hour failure multiplier
    features["hour_failure_mult"] = df["hour"].apply(_get_hour_failure_multiplier)

    # Feature 12: Rolling bank failure rate (captures recent bank health)
    # Group by bank and compute rolling mean of is_failed over last 50 transactions
    df_sorted = df.sort_values("timestamp")
    rolling_rates = []
    for _, row in df_sorted.iterrows():
        bank_mask = df_sorted["bank"] == row["bank"]
        time_mask = df_sorted["timestamp"] <= row["timestamp"]
        bank_history = df_sorted[bank_mask & time_mask].tail(50)
        if len(bank_history) > 1:
            rolling_rates.append(bank_history["is_failed"].mean())
        else:
            rolling_rates.append(BANK_FAILURE_RATES.get(row["bank"], 0.015))
    features["rolling_bank_failure"] = rolling_rates

    return features


def get_summary_stats(df: pd.DataFrame) -> dict:
    """Generate summary statistics for a transaction batch."""
    total = len(df)
    failed = df["is_failed"].sum()
    success = total - failed

    amount_at_risk = df[df["is_failed"] == 1]["amount"].sum()
    total_volume = df["amount"].sum()

    stats = {
        "total_transactions": total,
        "successful": int(success),
        "failed": int(failed),
        "failure_rate": round(failed / total * 100, 2),
        "total_volume_inr": int(total_volume),
        "amount_at_risk_inr": int(amount_at_risk),
        "top_failing_bank": df[df["is_failed"] == 1]["bank"].mode().iloc[0] if failed > 0 else None,
        "top_failing_instrument": df[df["is_failed"] == 1]["instrument"].mode().iloc[0] if failed > 0 else None,
        "failure_by_source": df[df["is_failed"] == 1]["error_source"].value_counts().to_dict() if failed > 0 else {},
        "failure_by_bank": df[df["is_failed"] == 1]["bank"].value_counts().to_dict() if failed > 0 else {},
        "avg_failed_amount": round(df[df["is_failed"] == 1]["amount"].mean(), 2) if failed > 0 else 0,
    }
    return stats


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RecoverIQ — Synthetic Payment Data Generator")
    print("=" * 60)

    df = generate_batch(n=500, seed=42)
    stats = get_summary_stats(df)

    print(f"\n📊 Generated {stats['total_transactions']} transactions")
    print(f"   ✅ Successful: {stats['successful']}")
    print(f"   ❌ Failed: {stats['failed']} ({stats['failure_rate']}%)")
    print(f"   💰 Total Volume: ₹{stats['total_volume_inr']:,}")
    print(f"   ⚠️  Amount at Risk: ₹{stats['amount_at_risk_inr']:,}")
    print(f"   🏦 Top Failing Bank: {stats['top_failing_bank']}")
    print(f"   💳 Top Failing Instrument: {stats['top_failing_instrument']}")

    print("\n📉 Failure by Error Source:")
    for source, count in stats["failure_by_source"].items():
        print(f"   {source}: {count}")

    print("\n📉 Failure by Bank:")
    for bank, count in sorted(stats["failure_by_bank"].items(), key=lambda x: -x[1])[:5]:
        print(f"   {bank}: {count}")

    # Save to CSV
    output_path = "backend/data/synthetic_transactions.csv"
    import os
    os.makedirs("backend/data", exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"\n💾 Saved to {output_path}")

    # Generate and display feature matrix
    print("\n🧠 Feature Engineering Preview:")
    features = generate_feature_matrix(df)
    print(features.head().to_string())
    print(f"\nFeature columns: {list(features.columns)}")
