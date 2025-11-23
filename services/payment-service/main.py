import os
import uuid
import json
import random
import logging
from datetime import datetime
from typing import Optional
from enum import Enum

import boto3
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
PAYMENTS_TABLE = os.getenv("PAYMENTS_TABLE", "ecommerce-payments")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8003")

# DynamoDB
dynamodb = None
def get_dynamodb():
    global dynamodb
    if dynamodb is None:
        try:
            dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
            logger.info(f"DynamoDB connected: {AWS_REGION}")
        except Exception as e:
            logger.error(f"DynamoDB connection failed: {e}")
    return dynamodb

def get_payments_table():
    db = get_dynamodb()
    if db:
        return db.Table(PAYMENTS_TABLE)
    return None

# Enums
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

# Pydantic Models
class PaymentCreate(BaseModel):
    order_id: str
    user_id: str
    amount: float
    currency: str = "INR"
    payment_method: PaymentMethod = PaymentMethod.credit_card
    card_last_four: Optional[str] = None

class PaymentResponse(BaseModel):
    id: str
    order_id: str
    user_id: str
    amount: float
    currency: str
    status: str
    payment_method: str
    transaction_id: str
    created_at: str

class RefundRequest(BaseModel):
    reason: str

# Metrics
REQUEST_COUNT = Counter('payment_service_requests_total', 'Total requests', ['method', 'endpoint'])
PAYMENTS_PROCESSED = Counter('payments_processed_total', 'Payments processed', ['status'])

app = FastAPI(title="Payment Service", version="1.0.0")

# HTTP call to update order status
def update_order_status(order_id: str, status: str):
    try:
        resp = httpx.put(
            f"{ORDER_SERVICE_URL}/api/v1/orders/{order_id}/status",
            params={"status": status},
            timeout=5.0
        )
        if resp.status_code == 200:
            logger.info(f"Order {order_id} updated to {status}")
        else:
            logger.warning(f"Order update failed: {resp.status_code}")
    except Exception as e:
        logger.error(f"Order update failed: {e}")

@app.get("/health")
def health():
    return {"status": "healthy", "service": "payment-service"}

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/api/v1/payments", response_model=PaymentResponse, status_code=201)
def process_payment(payment_data: PaymentCreate):
    REQUEST_COUNT.labels(method="POST", endpoint="/payments").inc()

    payment_id = str(uuid.uuid4())
    transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

    # Simulate payment (95% success rate)
    is_successful = random.random() < 0.95
    status = PaymentStatus.completed if is_successful else PaymentStatus.failed

    payment = {
        "id": payment_id,
        "order_id": payment_data.order_id,
        "user_id": payment_data.user_id,
        "amount": payment_data.amount,
        "currency": payment_data.currency,
        "status": status.value,
        "payment_method": payment_data.payment_method.value,
        "transaction_id": transaction_id,
        "card_last_four": payment_data.card_last_four,
        "created_at": datetime.utcnow().isoformat()
    }

    # Save to DynamoDB
    table = get_payments_table()
    if table:
        try:
            from decimal import Decimal
            payment_db = json.loads(json.dumps(payment), parse_float=Decimal)
            table.put_item(Item=payment_db)
            logger.info(f"Payment saved: {payment_id}")
        except Exception as e:
            logger.error(f"DynamoDB save failed: {e}")

    # Update order status via HTTP callback
    order_status = "paid" if is_successful else "payment_failed"
    update_order_status(payment_data.order_id, order_status)

    PAYMENTS_PROCESSED.labels(status=status.value).inc()
    logger.info(f"Payment {payment_id}: {status.value}")

    return PaymentResponse(
        id=payment_id,
        order_id=payment_data.order_id,
        user_id=payment_data.user_id,
        amount=payment_data.amount,
        currency=payment_data.currency,
        status=status.value,
        payment_method=payment_data.payment_method.value,
        transaction_id=transaction_id,
        created_at=payment["created_at"]
    )

@app.get("/api/v1/payments/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: str):
    REQUEST_COUNT.labels(method="GET", endpoint="/payments/{id}").inc()

    table = get_payments_table()
    if table:
        try:
            resp = table.get_item(Key={"id": payment_id})
            if "Item" in resp:
                item = resp["Item"]
                return PaymentResponse(
                    id=item["id"],
                    order_id=item["order_id"],
                    user_id=item["user_id"],
                    amount=float(item["amount"]),
                    currency=item["currency"],
                    status=item["status"],
                    payment_method=item["payment_method"],
                    transaction_id=item["transaction_id"],
                    created_at=item["created_at"]
                )
        except Exception as e:
            logger.error(f"DynamoDB get failed: {e}")

    raise HTTPException(status_code=404, detail="Payment not found")

@app.get("/api/v1/payments/order/{order_id}")
def get_payments_by_order(order_id: str):
    REQUEST_COUNT.labels(method="GET", endpoint="/payments/order/{id}").inc()

    table = get_payments_table()
    payments = []
    if table:
        try:
            resp = table.scan(FilterExpression=boto3.dynamodb.conditions.Attr("order_id").eq(order_id))
            for item in resp.get("Items", []):
                payments.append({
                    "id": item["id"],
                    "amount": float(item["amount"]),
                    "status": item["status"],
                    "transaction_id": item["transaction_id"]
                })
        except Exception as e:
            logger.error(f"DynamoDB scan failed: {e}")

    return {"payments": payments, "count": len(payments)}

@app.post("/api/v1/payments/{payment_id}/refund")
def refund_payment(payment_id: str, refund_request: RefundRequest):
    REQUEST_COUNT.labels(method="POST", endpoint="/payments/{id}/refund").inc()

    table = get_payments_table()
    if table:
        try:
            resp = table.get_item(Key={"id": payment_id})
            if "Item" not in resp:
                raise HTTPException(status_code=404, detail="Payment not found")

            item = resp["Item"]
            if item["status"] != "completed":
                raise HTTPException(status_code=400, detail="Can only refund completed payments")

            table.update_item(
                Key={"id": payment_id},
                UpdateExpression="SET #s = :status",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":status": "refunded"}
            )

            # Update order status
            update_order_status(item["order_id"], "refunded")

            PAYMENTS_PROCESSED.labels(status="refunded").inc()
            logger.info(f"Payment refunded: {payment_id}")

            return {
                "message": "Refund processed",
                "payment_id": payment_id,
                "refund_amount": float(item["amount"]),
                "reason": refund_request.reason
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Refund failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=503, detail="Database unavailable")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
