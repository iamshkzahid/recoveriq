import pytest
from fastapi.testclient import TestClient
import hmac
import hashlib
import json
import uuid
import sys
import os

# Add parent directory to path to import core_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core_engine import app, RAZORPAY_WEBHOOK_SECRET, idempotency_cache, init_database

# Initialize DB tables for testing
init_database()

client = TestClient(app)

def test_webhook_signature_validation():
    payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_{uuid.uuid4().hex[:14]}",
                    "amount": 1000,
                    "error_source": "bank",
                    "error_reason": "bank_timeout"
                }
            }
        }
    }
    
    # Needs to match exactly how the frontend or Razorpay sends it (compact JSON)
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    # Valid signature
    response = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"x-razorpay-signature": signature}
    )
    assert response.status_code == 200
    assert response.json().get("status") == "received"

    # Invalid signature
    response = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"x-razorpay-signature": "invalid_signature_hash"}
    )
    assert response.status_code == 400
    assert "Invalid webhook signature" in response.json().get("detail", "")

def test_idempotency_check():
    payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 5000,
                    "error_source": "razorpay"
                }
            }
        }
    }
    
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    # First request
    response1 = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"x-razorpay-signature": signature}
    )
    assert response1.status_code == 200
    assert response1.json().get("status") == "received"
    
    # Second request (duplicate)
    response2 = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"x-razorpay-signature": signature}
    )
    assert response2.status_code == 200
    assert response2.json().get("status") == "duplicate"
    
    # Verify TTL cache behavior
    sig_hash = hashlib.sha256(f"{payment_id}:payment.failed:{signature}".encode()).hexdigest()[:32]
    assert f"{payment_id}:payment.failed:{sig_hash}" in idempotency_cache

def test_xai_factor_calculations():
    # Test High Risk transaction (Yes Bank, netbanking, amount=75000)
    response = client.get("/api/predict?bank=Yes%20Bank&instrument=netbanking&amount=75000")
    assert response.status_code == 200
    data = response.json()
    
    factors = [f["factor"] for f in data["xai_factors"]]
    impacts = [f["impact"] for f in data["xai_factors"]]
    
    assert "Bank historical downtime (Elevated)" in factors
    assert "+45%" in impacts
    assert "Multi-step auth drop-off risk" in factors
    assert "+30%" in impacts
    assert "High-value scrutiny & limits" in factors
    assert "+25%" in impacts

    # Test Low Risk transaction (HDFC, UPI, amount=500)
    response = client.get("/api/predict?bank=HDFC&instrument=UPI&amount=500")
    assert response.status_code == 200
    data = response.json()
    
    factors = [f["factor"] for f in data["xai_factors"]]
    
    assert "Optimal routing available for HDFC" in factors
    assert "UPI fast-track settlement" in factors
