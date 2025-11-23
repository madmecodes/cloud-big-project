from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import httpx
import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="API Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])

# Service URLs from environment
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8001")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8001")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8003")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8004")

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, status=response.status_code).inc()
    REQUEST_LATENCY.labels(method=request.method, endpoint=request.url.path).observe(duration)
    return response

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "api-gateway"}

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# User Service Proxy
@app.post("/api/v1/auth/login")
async def login(request: Request):
    async with httpx.AsyncClient() as client:
        body = await request.json()
        response = await client.post(f"{USER_SERVICE_URL}/auth/login", json=body)
        return response.json()

@app.post("/api/v1/users")
async def create_user(request: Request):
    async with httpx.AsyncClient() as client:
        body = await request.json()
        response = await client.post(f"{USER_SERVICE_URL}/users", json=body)
        return response.json()

@app.get("/api/v1/users/{user_id}")
async def get_user(user_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{USER_SERVICE_URL}/users/{user_id}")
        return response.json()

# Product Service Proxy
@app.get("/api/v1/products")
async def list_products():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{PRODUCT_SERVICE_URL}/api/v1/products")
        return response.json()

@app.get("/api/v1/products/{product_id}")
async def get_product(product_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{PRODUCT_SERVICE_URL}/api/v1/products/{product_id}")
        return response.json()

@app.post("/api/v1/products")
async def create_product(request: Request):
    async with httpx.AsyncClient() as client:
        body = await request.json()
        response = await client.post(f"{PRODUCT_SERVICE_URL}/api/v1/products", json=body)
        return response.json()

# Order Service Proxy
@app.post("/api/v1/orders")
async def create_order(request: Request):
    async with httpx.AsyncClient() as client:
        body = await request.json()
        response = await client.post(f"{ORDER_SERVICE_URL}/api/v1/orders", json=body, timeout=30.0)
        return response.json()

@app.get("/api/v1/orders/{order_id}")
async def get_order(order_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{ORDER_SERVICE_URL}/api/v1/orders/{order_id}")
        return response.json()

@app.get("/api/v1/orders/user/{user_id}")
async def get_user_orders(user_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{ORDER_SERVICE_URL}/api/v1/orders/user/{user_id}")
        return response.json()

# Payment Service Proxy
@app.post("/api/v1/payments")
async def process_payment(request: Request):
    async with httpx.AsyncClient() as client:
        body = await request.json()
        response = await client.post(f"{PAYMENT_SERVICE_URL}/api/v1/payments", json=body)
        return response.json()

@app.get("/api/v1/payments/{payment_id}")
async def get_payment(payment_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{PAYMENT_SERVICE_URL}/api/v1/payments/{payment_id}")
        return response.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
