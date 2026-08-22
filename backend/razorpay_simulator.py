# backend/razorpay_simulator.py
# RecoverIQ — Razorpay Test API Response Simulator
# Generates realistic API responses matching Razorpay's actual response schemas
# Used for demo environments where test-mode API keys are not configured

import uuid
import time
import hmac
import hashlib
import json
import random
from datetime import datetime
from typing import Optional


# =============================================================================
# ID GENERATORS — Match Razorpay's format conventions
# =============================================================================

def _rzp_id(prefix: str) -> str:
    """Generate a Razorpay-style ID with the given prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def generate_order_id() -> str:
    return _rzp_id("order")

def generate_payment_id() -> str:
    return _rzp_id("pay")

def generate_payment_link_id() -> str:
    return _rzp_id("plink")

def generate_refund_id() -> str:
    return _rzp_id("rfnd")

def generate_invoice_id() -> str:
    return _rzp_id("inv")


# =============================================================================
# ORDER API SIMULATION
# =============================================================================

def create_order(
    amount: int,
    currency: str = "INR",
    receipt: Optional[str] = None,
    notes: Optional[dict] = None,
) -> dict:
    """
    Simulate Razorpay Orders API: POST /v1/orders
    
    Args:
        amount: Amount in paise (e.g., 50000 = ₹500)
        currency: Currency code (default: INR)
        receipt: Optional receipt ID
        notes: Optional key-value metadata
    
    Returns:
        dict matching Razorpay's Order entity schema
    """
    order_id = generate_order_id()
    now = int(time.time())

    return {
        "id": order_id,
        "entity": "order",
        "amount": amount,
        "amount_paid": 0,
        "amount_due": amount,
        "currency": currency,
        "receipt": receipt or f"rcpt_{uuid.uuid4().hex[:8]}",
        "offer_id": None,
        "status": "created",
        "attempts": 0,
        "notes": notes or {},
        "created_at": now,
    }


# =============================================================================
# PAYMENT API SIMULATION
# =============================================================================

def create_payment(
    order_id: str,
    amount: int,
    method: str = "upi",
    bank: Optional[str] = None,
    status: str = "captured",
    error_code: Optional[str] = None,
    error_description: Optional[str] = None,
    error_source: Optional[str] = None,
    error_reason: Optional[str] = None,
    vpa: Optional[str] = None,
) -> dict:
    """
    Simulate Razorpay Payments API response.
    
    Args:
        order_id: Associated order ID
        amount: Amount in paise
        method: Payment method (upi, card, netbanking, wallet)
        bank: Bank code
        status: Payment status (captured, failed, authorized)
        error_*: Error details for failed payments
    
    Returns:
        dict matching Razorpay's Payment entity schema
    """
    payment_id = generate_payment_id()
    now = int(time.time())

    payment = {
        "id": payment_id,
        "entity": "payment",
        "amount": amount,
        "currency": "INR",
        "status": status,
        "order_id": order_id,
        "invoice_id": None,
        "international": False,
        "method": method,
        "amount_refunded": 0,
        "refund_status": None,
        "captured": status == "captured",
        "description": "RecoverIQ simulated payment",
        "card_id": None,
        "bank": bank,
        "wallet": None,
        "vpa": vpa or ("user@upi" if method == "upi" else None),
        "email": "customer@example.com",
        "contact": "+919876543210",
        "fee": int(amount * 0.02) if status == "captured" else 0,
        "tax": int(amount * 0.02 * 0.18) if status == "captured" else 0,
        "error_code": error_code,
        "error_description": error_description,
        "error_source": error_source,
        "error_step": "payment_authorization" if error_code else None,
        "error_reason": error_reason,
        "notes": {},
        "created_at": now,
    }

    return payment


def simulate_failure(
    order_id: str,
    amount: int,
    method: str = "upi",
    bank: str = "SBI",
    failure_type: str = "gateway",
) -> dict:
    """
    Generate a realistically failed payment with proper error codes.
    
    Args:
        order_id: Associated order ID
        amount: Amount in paise
        method: Payment method
        bank: Bank name
        failure_type: 'gateway' or 'customer'
    
    Returns:
        Failed payment entity with realistic error details
    """
    gateway_errors = [
        {
            "code": "GATEWAY_ERROR",
            "description": "Payment processing failed due to error at bank or wallet gateway",
            "source": "gateway",
            "reason": "bank_timeout",
        },
        {
            "code": "GATEWAY_ERROR",
            "description": "The bank servers are currently unavailable. Please try after some time.",
            "source": "gateway",
            "reason": "gateway_unavailable",
        },
        {
            "code": "GATEWAY_ERROR",
            "description": "Payment could not be completed due to a temporary network issue",
            "source": "gateway",
            "reason": "network_error",
        },
    ]

    customer_errors = [
        {
            "code": "BAD_REQUEST_ERROR",
            "description": "Payment was not completed due to insufficient account balance",
            "source": "customer",
            "reason": "insufficient_funds",
        },
        {
            "code": "BAD_REQUEST_ERROR",
            "description": "OTP verification timed out. Please retry the payment.",
            "source": "customer",
            "reason": "otp_expired",
        },
        {
            "code": "BAD_REQUEST_ERROR",
            "description": "Payment was cancelled by the customer",
            "source": "customer",
            "reason": "payment_cancelled",
        },
        {
            "code": "BAD_REQUEST_ERROR",
            "description": "Card authentication failed. Please check your card details.",
            "source": "customer",
            "reason": "authentication_failed",
        },
    ]

    errors = gateway_errors if failure_type == "gateway" else customer_errors
    error = random.choice(errors)

    return create_payment(
        order_id=order_id,
        amount=amount,
        method=method,
        bank=bank,
        status="failed",
        error_code=error["code"],
        error_description=error["description"],
        error_source=error["source"],
        error_reason=error["reason"],
    )


# =============================================================================
# PAYMENT LINK API SIMULATION
# =============================================================================

def create_payment_link(
    amount: int,
    customer_name: str = "Customer",
    customer_email: str = "customer@example.com",
    customer_phone: str = "+919876543210",
    description: str = "Complete your payment",
    callback_url: Optional[str] = None,
) -> dict:
    """
    Simulate Razorpay Payment Links API: POST /v1/payment_links
    
    Returns:
        dict matching Razorpay's Payment Link entity schema
    """
    link_id = generate_payment_link_id()
    short_url = f"https://rzp.io/i/{uuid.uuid4().hex[:8]}"
    now = int(time.time())

    return {
        "id": link_id,
        "entity": "payment_link",
        "amount": amount,
        "currency": "INR",
        "accept_partial": False,
        "first_min_partial_amount": 0,
        "description": description,
        "customer": {
            "name": customer_name,
            "email": customer_email,
            "contact": customer_phone,
        },
        "notify": {
            "sms": True,
            "email": True,
            "whatsapp": True,
        },
        "reminder_enable": True,
        "callback_url": callback_url or "",
        "callback_method": "get",
        "short_url": short_url,
        "status": "created",
        "created_at": now,
        "expire_by": now + 86400,  # 24 hours
    }


# =============================================================================
# WEBHOOK PAYLOAD SIMULATION
# =============================================================================

def generate_webhook_payload(
    event: str,
    payment: dict,
    webhook_secret: str = "recoveriq_test_secret",
) -> tuple[dict, str]:
    """
    Generate a Razorpay webhook payload with valid HMAC signature.
    
    Args:
        event: Event name (e.g., 'payment.failed', 'payment.captured', 'order.paid')
        payment: Payment entity dict
        webhook_secret: Secret for HMAC signature generation
    
    Returns:
        Tuple of (payload_dict, signature_string)
    """
    payload = {
        "entity": "event",
        "account_id": "acc_recoveriq_test",
        "event": event,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": payment,
            },
        },
        "created_at": int(time.time()),
    }

    # Generate valid HMAC SHA256 signature
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        payload_json.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return payload, signature


def verify_webhook_signature(
    payload: dict,
    signature: str,
    webhook_secret: str = "recoveriq_test_secret",
) -> bool:
    """
    Verify a Razorpay webhook signature using HMAC SHA256.
    
    Args:
        payload: The webhook payload dict
        signature: The x-razorpay-signature header value
        webhook_secret: The webhook secret configured in Razorpay dashboard
    
    Returns:
        True if signature is valid, False otherwise
    """
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    expected = hmac.new(
        webhook_secret.encode("utf-8"),
        payload_json.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# =============================================================================
# BATCH SIMULATION — End-to-End Transaction Flow
# =============================================================================

def simulate_transaction_batch(
    n: int = 10,
    failure_rate: float = 0.15,
) -> list[dict]:
    """
    Simulate a batch of end-to-end transactions (order → payment → webhook).
    
    Returns a list of transaction dicts with order, payment, and webhook details.
    """
    banks = ["SBI", "HDFC", "ICICI", "Axis", "Kotak", "PNB", "BOB", "Yes Bank"]
    methods = ["upi", "card", "netbanking", "wallet"]
    method_weights = [60, 30, 7, 3]

    transactions = []

    for _ in range(n):
        amount_inr = random.randint(99, 49999)
        amount_paise = amount_inr * 100
        bank = random.choice(banks)
        method = random.choices(methods, weights=method_weights, k=1)[0]

        # Create order
        order = create_order(amount=amount_paise)

        # Determine if payment fails
        fails = random.random() < failure_rate
        failure_type = random.choice(["gateway", "customer"]) if fails else None

        if fails:
            payment = simulate_failure(
                order_id=order["id"],
                amount=amount_paise,
                method=method,
                bank=bank,
                failure_type=failure_type,
            )
            event_name = "payment.failed"
        else:
            payment = create_payment(
                order_id=order["id"],
                amount=amount_paise,
                method=method,
                bank=bank,
                status="captured",
            )
            event_name = "payment.captured"

        # Generate webhook
        webhook_payload, webhook_signature = generate_webhook_payload(
            event=event_name,
            payment=payment,
        )

        transactions.append({
            "order": order,
            "payment": payment,
            "webhook": {
                "event": event_name,
                "payload": webhook_payload,
                "signature": webhook_signature,
            },
            "is_failed": fails,
            "amount_inr": amount_inr,
            "bank": bank,
            "method": method,
        })

    return transactions


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RecoverIQ — Razorpay API Simulator")
    print("=" * 60)

    # Simulate a batch
    batch = simulate_transaction_batch(n=10)

    for i, txn in enumerate(batch):
        status = "❌ FAILED" if txn["is_failed"] else "✅ SUCCESS"
        reason = txn["payment"].get("error_reason", "—")
        print(f"  [{i+1}] {status} | ₹{txn['amount_inr']:,} | {txn['bank']} | {txn['method']} | {reason}")

    # Verify webhook signatures
    print("\n🔐 Webhook Signature Verification:")
    for txn in batch[:3]:
        valid = verify_webhook_signature(
            txn["webhook"]["payload"],
            txn["webhook"]["signature"],
        )
        print(f"  {txn['payment']['id']}: {'✅ Valid' if valid else '❌ Invalid'}")
