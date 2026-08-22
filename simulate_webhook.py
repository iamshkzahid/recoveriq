import hmac
import hashlib
import json
import time
import requests
import random
import uuid

# Configuration
WEBHOOK_SECRET = "recoveriq_test_secret"
WEBHOOK_URL = "http://localhost:8000/api/webhooks/razorpay"
WEBHOOK_EVENT = "payment.failed"

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Sample failure reasons
FAILURE_REASONS = [
    ("network_error", "bank", "Issuer bank network is currently unreachable."),
    ("authentication_failed", "customer", "3D Secure OTP verification failed."),
    ("insufficient_funds", "customer", "Customer bank account has insufficient balance."),
    ("gateway_timeout", "gateway", "The payment gateway timed out waiting for the bank."),
    ("risk_decline", "razorpay", "Transaction flagged by Razorpay risk engine.")
]

def generate_payload():
    """Generate a realistic Razorpay payment.failed payload"""
    reason_code, reason_source, reason_desc = random.choice(FAILURE_REASONS)
    amount = random.randint(5000, 150000) # ₹50 to ₹1500
    
    payload = {
        "entity": "event",
        "account_id": "acc_JMlvwG08R65MvY",
        "event": WEBHOOK_EVENT,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_{uuid.uuid4().hex[:14]}",
                    "entity": "payment",
                    "amount": amount,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": f"order_{uuid.uuid4().hex[:14]}",
                    "invoice_id": None,
                    "international": False,
                    "method": random.choice(["upi", "card", "netbanking"]),
                    "amount_refunded": 0,
                    "refund_status": None,
                    "captured": False,
                    "description": "Test Transaction",
                    "card_id": None,
                    "bank": random.choice(["SBI", "HDFC", "ICICI", "Axis", "Yes Bank", "PNB"]),
                    "wallet": None,
                    "vpa": "test@upi" if random.choice([True, False]) else None,
                    "email": "customer@example.com",
                    "contact": "+919876543210",
                    "notes": [],
                    "fee": None,
                    "tax": None,
                    "error_code": reason_code,
                    "error_description": reason_desc,
                    "error_source": reason_source,
                    "error_step": "payment_authentication",
                    "error_reason": reason_code,
                    "created_at": int(time.time())
                }
            }
        },
        "created_at": int(time.time())
    }
    return json.dumps(payload, separators=(',', ':'))

def sign_payload(payload: str) -> str:
    """Generate the HMAC SHA256 signature for the payload"""
    return hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def emit_webhook():
    payload = generate_payload()
    signature = sign_payload(payload)
    
    headers = {
        "Content-Type": "application/json",
        "x-razorpay-signature": signature
    }
    
    payment_id = json.loads(payload)["payload"]["payment"]["entity"]["id"]
    amount = json.loads(payload)["payload"]["payment"]["entity"]["amount"]
    
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}⚡ [WEBHOOK GENERATOR]{Colors.ENDC} Emitting event: {Colors.WARNING}{WEBHOOK_EVENT}{Colors.ENDC}")
    print(f"  {Colors.BOLD}Payment ID:{Colors.ENDC} {payment_id}")
    print(f"  {Colors.BOLD}Amount:{Colors.ENDC} ₹{amount / 100:.2f}")
    print(f"  {Colors.BOLD}Signature:{Colors.ENDC} {signature[:12]}...{signature[-4:]}")
    
    try:
        start_time = time.time()
        response = requests.post(WEBHOOK_URL, data=payload, headers=headers)
        latency = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            print(f"  {Colors.OKGREEN}✓ SUCCESS{Colors.ENDC} (200 OK) in {latency:.1f}ms")
            print(f"  {Colors.HEADER}Response:{Colors.ENDC} {response.json()}")
        else:
            print(f"  {Colors.FAIL}✗ FAILED{Colors.ENDC} ({response.status_code}) in {latency:.1f}ms")
            print(f"  {Colors.HEADER}Response:{Colors.ENDC} {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"  {Colors.FAIL}✗ CONNECTION ERROR:{Colors.ENDC} {e}")

if __name__ == "__main__":
    print(f"{Colors.HEADER}{Colors.BOLD}=================================================={Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}🚀 RecoverIQ Webhook Simulation Script Started{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}=================================================={Colors.ENDC}")
    print(f"Target URL: {Colors.UNDERLINE}{WEBHOOK_URL}{Colors.ENDC}\n")
    
    try:
        while True:
            emit_webhook()
            sleep_time = random.uniform(3.0, 7.0)
            print(f"Waiting {sleep_time:.1f}s for next event...\n")
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Simulation stopped by user.{Colors.ENDC}")
