from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import os
import uuid
import logging
from datetime import datetime
from typing import Optional
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Payment Service", version="1.0.0")

# Prometheus metrics
REQUEST_COUNT = Counter('payment_service_requests_total', 'Total requests', ['method', 'endpoint'])
PAYMENTS_PROCESSED = Counter('payments_processed_total', 'Total payments processed', ['status'])
PAYMENT_AMOUNT = Counter('payment_amount_total', 'Total payment amount processed')
PAYMENT_LATENCY = Histogram('payment_processing_seconds', 'Payment processing time')

# In-memory storage
payments_db = {}

class PaymentStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"

class PaymentMethod(str, Enum):
    credit_card = "credit_card"
    debit_card = "debit_card"
    upi = "upi"
    net_banking = "net_banking"

class PaymentCreate(BaseModel):
    order_id: str
    user_id: str
    amount: float
    currency: str = "INR"
    payment_method: PaymentMethod = PaymentMethod.credit_card
    card_last_four: Optional[str] = None

class Payment(BaseModel):
    id: str
    order_id: str
    user_id: str
    amount: float
    currency: str
    status: PaymentStatus
    payment_method: str
    transaction_id: str
    created_at: str

class RefundRequest(BaseModel):
    reason: str

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "payment-service"}

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/payments", response_model=Payment)
async def process_payment(payment_data: PaymentCreate):
    REQUEST_COUNT.labels(method="POST", endpoint="/payments").inc()

    payment_id = str(uuid.uuid4())
    transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

    # Simulate payment processing (in production, integrate with payment gateway)
    # For demo, 95% success rate
    import random
    is_successful = random.random() < 0.95

    status = PaymentStatus.completed if is_successful else PaymentStatus.failed

    payment = {
        "id": payment_id,
        "order_id": payment_data.order_id,
        "user_id": payment_data.user_id,
        "amount": payment_data.amount,
        "currency": payment_data.currency,
        "status": status,
        "payment_method": payment_data.payment_method.value,
        "transaction_id": transaction_id,
        "card_last_four": payment_data.card_last_four,
        "created_at": datetime.utcnow().isoformat()
    }

    payments_db[payment_id] = payment

    # Update metrics
    PAYMENTS_PROCESSED.labels(status=status.value).inc()
    if is_successful:
        PAYMENT_AMOUNT.inc(payment_data.amount)

    logger.info(f"Payment processed: {payment_id} - Status: {status}")

    return Payment(
        id=payment_id,
        order_id=payment_data.order_id,
        user_id=payment_data.user_id,
        amount=payment_data.amount,
        currency=payment_data.currency,
        status=status,
        payment_method=payment_data.payment_method.value,
        transaction_id=transaction_id,
        created_at=payment["created_at"]
    )

@app.get("/payments/{payment_id}", response_model=Payment)
async def get_payment(payment_id: str):
    REQUEST_COUNT.labels(method="GET", endpoint="/payments/{id}").inc()

    if payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment = payments_db[payment_id]
    return Payment(
        id=payment["id"],
        order_id=payment["order_id"],
        user_id=payment["user_id"],
        amount=payment["amount"],
        currency=payment["currency"],
        status=PaymentStatus(payment["status"]),
        payment_method=payment["payment_method"],
        transaction_id=payment["transaction_id"],
        created_at=payment["created_at"]
    )

@app.get("/payments/order/{order_id}")
async def get_payments_by_order(order_id: str):
    REQUEST_COUNT.labels(method="GET", endpoint="/payments/order/{id}").inc()

    order_payments = [
        Payment(
            id=p["id"],
            order_id=p["order_id"],
            user_id=p["user_id"],
            amount=p["amount"],
            currency=p["currency"],
            status=PaymentStatus(p["status"]),
            payment_method=p["payment_method"],
            transaction_id=p["transaction_id"],
            created_at=p["created_at"]
        )
        for p in payments_db.values()
        if p["order_id"] == order_id
    ]
    return {"payments": order_payments, "count": len(order_payments)}

@app.post("/payments/{payment_id}/refund")
async def refund_payment(payment_id: str, refund_request: RefundRequest):
    REQUEST_COUNT.labels(method="POST", endpoint="/payments/{id}/refund").inc()

    if payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment = payments_db[payment_id]

    if payment["status"] != "completed":
        raise HTTPException(status_code=400, detail="Can only refund completed payments")

    payments_db[payment_id]["status"] = PaymentStatus.refunded
    PAYMENTS_PROCESSED.labels(status="refunded").inc()

    logger.info(f"Payment refunded: {payment_id} - Reason: {refund_request.reason}")

    return {
        "message": "Refund processed successfully",
        "payment_id": payment_id,
        "refund_amount": payment["amount"],
        "reason": refund_request.reason
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
