from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from kafka import KafkaProducer
import os
import uuid
import json
import logging
from datetime import datetime
from typing import List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Order Service", version="1.0.0")

# Prometheus metrics
REQUEST_COUNT = Counter('order_service_requests_total', 'Total requests', ['method', 'endpoint'])
ORDERS_CREATED = Counter('orders_created_total', 'Total orders created')
ORDER_LATENCY = Histogram('order_processing_seconds', 'Order processing time')

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "orders")

# In-memory storage
orders_db = {}

# Kafka producer (lazy initialization)
kafka_producer = None

def get_kafka_producer():
    global kafka_producer
    if kafka_producer is None:
        try:
            kafka_producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                api_version=(0, 10, 1)
            )
            logger.info(f"Kafka producer connected to {KAFKA_BOOTSTRAP_SERVERS}")
        except Exception as e:
            logger.warning(f"Kafka connection failed: {e}. Running without Kafka.")
            return None
    return kafka_producer

class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price: float = 0.0

class ShippingAddress(BaseModel):
    street: str
    city: str
    state: str
    zip: str
    country: str

class OrderCreate(BaseModel):
    user_id: str
    items: List[OrderItem]
    shipping_address: ShippingAddress

class Order(BaseModel):
    id: str
    user_id: str
    items: List[OrderItem]
    total_amount: float
    status: str
    created_at: str

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "order-service"}

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/orders", response_model=Order)
async def create_order(order_data: OrderCreate):
    REQUEST_COUNT.labels(method="POST", endpoint="/orders").inc()

    order_id = str(uuid.uuid4())
    total_amount = sum(item.quantity * (item.price or 10.0) for item in order_data.items)

    order = {
        "id": order_id,
        "user_id": order_data.user_id,
        "items": [item.dict() for item in order_data.items],
        "shipping_address": order_data.shipping_address.dict(),
        "total_amount": total_amount,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    }

    orders_db[order_id] = order
    ORDERS_CREATED.inc()

    # Publish to Kafka
    producer = get_kafka_producer()
    if producer:
        try:
            event = {
                "event_type": "order_created",
                "order_id": order_id,
                "user_id": order_data.user_id,
                "total_amount": total_amount,
                "items_count": len(order_data.items),
                "timestamp": datetime.utcnow().isoformat()
            }
            producer.send(KAFKA_TOPIC, value=event)
            producer.flush()
            logger.info(f"Order event published to Kafka: {order_id}")
        except Exception as e:
            logger.error(f"Failed to publish to Kafka: {e}")

    logger.info(f"Order created: {order_id}")
    return Order(
        id=order_id,
        user_id=order_data.user_id,
        items=order_data.items,
        total_amount=total_amount,
        status="pending",
        created_at=order["created_at"]
    )

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    REQUEST_COUNT.labels(method="GET", endpoint="/orders/{id}").inc()

    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")

    order = orders_db[order_id]
    return Order(
        id=order["id"],
        user_id=order["user_id"],
        items=[OrderItem(**item) for item in order["items"]],
        total_amount=order["total_amount"],
        status=order["status"],
        created_at=order["created_at"]
    )

@app.get("/orders/user/{user_id}")
async def get_user_orders(user_id: str):
    REQUEST_COUNT.labels(method="GET", endpoint="/orders/user/{id}").inc()

    user_orders = [
        Order(
            id=order["id"],
            user_id=order["user_id"],
            items=[OrderItem(**item) for item in order["items"]],
            total_amount=order["total_amount"],
            status=order["status"],
            created_at=order["created_at"]
        )
        for order in orders_db.values()
        if order["user_id"] == user_id
    ]
    return {"orders": user_orders, "count": len(user_orders)}

@app.put("/orders/{order_id}/status")
async def update_order_status(order_id: str, status: str):
    REQUEST_COUNT.labels(method="PUT", endpoint="/orders/{id}/status").inc()

    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")

    orders_db[order_id]["status"] = status
    return {"message": "Order status updated", "order_id": order_id, "status": status}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
