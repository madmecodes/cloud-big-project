import os
import uuid
import json
import logging
from datetime import datetime
from typing import List, Optional

import boto3
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from kafka import KafkaProducer
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
ORDERS_TABLE = os.getenv("ORDERS_TABLE", "ecommerce-orders")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8001")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8001")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_ORDERS_TOPIC", "orders")
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
KAFKA_SASL_MECHANISM = os.getenv("KAFKA_SASL_MECHANISM", "PLAIN")
KAFKA_API_KEY = os.getenv("KAFKA_API_KEY", "")
KAFKA_API_SECRET = os.getenv("KAFKA_API_SECRET", "")

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

def get_orders_table():
    db = get_dynamodb()
    if db:
        return db.Table(ORDERS_TABLE)
    return None

# Kafka
kafka_producer = None
def get_kafka():
    global kafka_producer
    if kafka_producer is None:
        try:
            kafka_config = {
                "bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS.split(","),
                "value_serializer": lambda v: json.dumps(v).encode('utf-8')
            }
            # Add SASL/SSL configuration for Confluent Cloud
            if KAFKA_SECURITY_PROTOCOL == "SASL_SSL":
                kafka_config.update({
                    "security_protocol": "SASL_SSL",
                    "sasl_mechanism": KAFKA_SASL_MECHANISM,
                    "sasl_plain_username": KAFKA_API_KEY,
                    "sasl_plain_password": KAFKA_API_SECRET
                })
            kafka_producer = KafkaProducer(**kafka_config)
            logger.info(f"Kafka connected: {KAFKA_BOOTSTRAP_SERVERS} (protocol: {KAFKA_SECURITY_PROTOCOL})")
        except Exception as e:
            logger.warning(f"Kafka connection failed: {e}")
    return kafka_producer

# Pydantic Models
class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price: float = 0.0

class ShippingAddress(BaseModel):
    street: str
    city: str
    state: str
    zip: str
    country: str = "India"

class OrderCreate(BaseModel):
    user_id: str
    items: List[OrderItem]
    shipping_address: ShippingAddress

class OrderResponse(BaseModel):
    id: str
    user_id: str
    items: List[dict]
    total_amount: float
    status: str
    created_at: str

# Metrics
REQUEST_COUNT = Counter('order_service_requests_total', 'Total requests', ['method', 'endpoint'])
ORDERS_CREATED = Counter('orders_created_total', 'Orders created')

app = FastAPI(title="Order Service", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "healthy", "service": "order-service"}

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# HTTP call to validate user
def validate_user(user_id: str) -> bool:
    try:
        resp = httpx.get(f"{USER_SERVICE_URL}/users/{user_id}", timeout=5.0)
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"User validation failed: {e}")
        return True  # Allow if user service is down

# HTTP call to reserve product stock
def reserve_stock(product_id: str, quantity: int) -> bool:
    try:
        resp = httpx.post(
            f"{PRODUCT_SERVICE_URL}/api/v1/products/{product_id}/reserve",
            params={"quantity": quantity},
            timeout=5.0
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Stock reservation failed: {e}")
        return True  # Allow if product service is down

# Publish to Kafka
def publish_order_event(order: dict, event_type: str):
    producer = get_kafka()
    if producer:
        try:
            event = {
                "event_type": event_type,
                "order_id": order["id"],
                "user_id": order["user_id"],
                "total_amount": order["total_amount"],
                "timestamp": datetime.utcnow().isoformat()
            }
            producer.send(KAFKA_TOPIC, value=event)
            producer.flush()
            logger.info(f"Event published: {event_type} for order {order['id']}")
        except Exception as e:
            logger.error(f"Kafka publish failed: {e}")

@app.post("/api/v1/orders", response_model=OrderResponse, status_code=201)
def create_order(order_data: OrderCreate):
    REQUEST_COUNT.labels(method="POST", endpoint="/orders").inc()

    # Validate user exists
    if not validate_user(order_data.user_id):
        raise HTTPException(status_code=400, detail="User not found")

    # Reserve stock for each item
    for item in order_data.items:
        if not reserve_stock(item.product_id, item.quantity):
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {item.product_id}")

    order_id = str(uuid.uuid4())
    total = sum(item.quantity * (item.price if item.price > 0 else 10.0) for item in order_data.items)
    now = datetime.utcnow().isoformat()

    order = {
        "id": order_id,
        "user_id": order_data.user_id,
        "items": [item.dict() for item in order_data.items],
        "shipping_address": order_data.shipping_address.dict(),
        "total_amount": total,
        "status": "pending",
        "created_at": now,
        "updated_at": now
    }

    # Save to DynamoDB
    table = get_orders_table()
    if table:
        try:
            # Convert float to Decimal for DynamoDB
            from decimal import Decimal
            order_db = json.loads(json.dumps(order), parse_float=Decimal)
            table.put_item(Item=order_db)
            logger.info(f"Order saved to DynamoDB: {order_id}")
        except Exception as e:
            logger.error(f"DynamoDB save failed: {e}")

    # Publish event to Kafka
    publish_order_event(order, "order.created")
    ORDERS_CREATED.inc()

    return OrderResponse(**order)

@app.get("/api/v1/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str):
    REQUEST_COUNT.labels(method="GET", endpoint="/orders/{id}").inc()

    table = get_orders_table()
    if table:
        try:
            resp = table.get_item(Key={"id": order_id})
            if "Item" in resp:
                item = resp["Item"]
                # Convert Decimal back to float
                return OrderResponse(
                    id=item["id"],
                    user_id=item["user_id"],
                    items=item["items"],
                    total_amount=float(item["total_amount"]),
                    status=item["status"],
                    created_at=item["created_at"]
                )
        except Exception as e:
            logger.error(f"DynamoDB get failed: {e}")

    raise HTTPException(status_code=404, detail="Order not found")

@app.get("/api/v1/orders/user/{user_id}")
def get_user_orders(user_id: str):
    REQUEST_COUNT.labels(method="GET", endpoint="/orders/user/{id}").inc()

    table = get_orders_table()
    orders = []
    if table:
        try:
            # Scan for user orders (in production, use GSI)
            resp = table.scan(FilterExpression=boto3.dynamodb.conditions.Attr("user_id").eq(user_id))
            for item in resp.get("Items", []):
                orders.append({
                    "id": item["id"],
                    "total_amount": float(item["total_amount"]),
                    "status": item["status"],
                    "created_at": item["created_at"]
                })
        except Exception as e:
            logger.error(f"DynamoDB scan failed: {e}")

    return {"orders": orders, "count": len(orders)}

@app.put("/api/v1/orders/{order_id}/status")
def update_order_status(order_id: str, status: str):
    REQUEST_COUNT.labels(method="PUT", endpoint="/orders/{id}/status").inc()

    table = get_orders_table()
    if table:
        try:
            table.update_item(
                Key={"id": order_id},
                UpdateExpression="SET #s = :status, updated_at = :updated",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":status": status, ":updated": datetime.utcnow().isoformat()}
            )
            logger.info(f"Order {order_id} status updated to {status}")
            return {"message": "Status updated", "order_id": order_id, "status": status}
        except Exception as e:
            logger.error(f"Status update failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=503, detail="Database unavailable")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
