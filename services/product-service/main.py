import os
import logging
import json
from typing import List, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, func
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
import uvicorn
import boto3
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:password@localhost:5432/ecommerce"
)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1024))
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    sku = Column(String(255), unique=True)
    category = Column(String(255))
    image_url = Column(String(512))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# Metrics
product_requests = Counter(
    'product_requests_total',
    'Total product requests',
    ['method', 'status']
)

product_latency = Histogram(
    'product_request_duration_seconds',
    'Product request latency'
)

db_queries = Counter(
    'product_db_queries_total',
    'Total database queries',
    ['operation', 'status']
)

# Pydantic models
from pydantic import BaseModel

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int
    sku: str
    category: Optional[str] = None
    image_url: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "Laptop",
                "description": "High-performance laptop",
                "price": 999.99,
                "stock": 10,
                "sku": "LAPTOP-001",
                "category": "Electronics"
            }
        }

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    category: Optional[str] = None
    image_url: Optional[str] = None

class ProductResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    price: float
    stock: int
    sku: str
    category: Optional[str]
    image_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# S3 client for product images
s3_client = None

def get_s3_client():
    global s3_client
    if s3_client is None:
        s3_client = boto3.client(
            's3',
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
    return s3_client

# Dependencies
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Product Service starting up")
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown
    logger.info("Product Service shutting down")

app = FastAPI(
    title="Product Service",
    description="Microservice for managing product catalog",
    version="1.0.0",
    lifespan=lifespan
)

# Routes

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "product-service",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/metrics", tags=["Metrics"])
async def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()

@app.get("/api/v1/products", response_model=List[ProductResponse], tags=["Products"])
@product_latency.time()
async def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all products with pagination"""
    try:
        query = db.query(Product)

        if category:
            query = query.filter(Product.category == category)

        products = query.offset(skip).limit(limit).all()
        product_requests.labels(method="list", status="200").inc()
        db_queries.labels(operation="select", status="success").inc()

        return products
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        product_requests.labels(method="list", status="500").inc()
        db_queries.labels(operation="select", status="error").inc()
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/api/v1/products/{product_id}", response_model=ProductResponse, tags=["Products"])
@product_latency.time()
async def get_product(product_id: str, db: Session = Depends(get_db)):
    """Get a specific product by ID"""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:
            product_requests.labels(method="get", status="404").inc()
            raise HTTPException(status_code=404, detail="Product not found")

        product_requests.labels(method="get", status="200").inc()
        db_queries.labels(operation="select", status="success").inc()

        return product
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        product_requests.labels(method="get", status="500").inc()
        db_queries.labels(operation="select", status="error").inc()
        raise HTTPException(status_code=500, detail="Database error")

@app.post("/api/v1/products", response_model=ProductResponse, status_code=201, tags=["Products"])
@product_latency.time()
async def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db)
):
    """Create a new product"""
    try:
        # Check if SKU already exists
        existing = db.query(Product).filter(Product.sku == product.sku).first()
        if existing:
            product_requests.labels(method="create", status="409").inc()
            raise HTTPException(status_code=409, detail="Product with this SKU already exists")

        import uuid
        new_product = Product(
            id=str(uuid.uuid4()),
            **product.dict()
        )

        db.add(new_product)
        db.commit()
        db.refresh(new_product)

        product_requests.labels(method="create", status="201").inc()
        db_queries.labels(operation="insert", status="success").inc()

        logger.info(f"Created product: {new_product.id}")

        return new_product
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        product_requests.labels(method="create", status="500").inc()
        db_queries.labels(operation="insert", status="error").inc()
        raise HTTPException(status_code=500, detail="Database error")

@app.put("/api/v1/products/{product_id}", response_model=ProductResponse, tags=["Products"])
@product_latency.time()
async def update_product(
    product_id: str,
    product_update: ProductUpdate,
    db: Session = Depends(get_db)
):
    """Update a product"""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:
            product_requests.labels(method="update", status="404").inc()
            raise HTTPException(status_code=404, detail="Product not found")

        # Update only provided fields
        update_data = product_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)

        db.commit()
        db.refresh(product)

        product_requests.labels(method="update", status="200").inc()
        db_queries.labels(operation="update", status="success").inc()

        logger.info(f"Updated product: {product_id}")

        return product
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        product_requests.labels(method="update", status="500").inc()
        db_queries.labels(operation="update", status="error").inc()
        raise HTTPException(status_code=500, detail="Database error")

@app.delete("/api/v1/products/{product_id}", status_code=204, tags=["Products"])
@product_latency.time()
async def delete_product(product_id: str, db: Session = Depends(get_db)):
    """Delete a product"""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:
            product_requests.labels(method="delete", status="404").inc()
            raise HTTPException(status_code=404, detail="Product not found")

        db.delete(product)
        db.commit()

        product_requests.labels(method="delete", status="204").inc()
        db_queries.labels(operation="delete", status="success").inc()

        logger.info(f"Deleted product: {product_id}")

        return None
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        product_requests.labels(method="delete", status="500").inc()
        db_queries.labels(operation="delete", status="error").inc()
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/api/v1/products/{product_id}/stock", tags=["Products"])
@product_latency.time()
async def get_product_stock(product_id: str, db: Session = Depends(get_db)):
    """Get product stock information"""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:
            product_requests.labels(method="get_stock", status="404").inc()
            raise HTTPException(status_code=404, detail="Product not found")

        product_requests.labels(method="get_stock", status="200").inc()

        return {
            "product_id": product_id,
            "stock": product.stock,
            "available": product.stock > 0
        }
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        product_requests.labels(method="get_stock", status="500").inc()
        raise HTTPException(status_code=500, detail="Database error")

@app.post("/api/v1/products/{product_id}/reserve", tags=["Products"])
@product_latency.time()
async def reserve_product_stock(
    product_id: str,
    quantity: int = Query(..., gt=0),
    db: Session = Depends(get_db)
):
    """Reserve product stock for an order"""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:
            product_requests.labels(method="reserve", status="404").inc()
            raise HTTPException(status_code=404, detail="Product not found")

        if product.stock < quantity:
            product_requests.labels(method="reserve", status="400").inc()
            raise HTTPException(status_code=400, detail="Insufficient stock")

        product.stock -= quantity
        db.commit()
        db.refresh(product)

        product_requests.labels(method="reserve", status="200").inc()
        db_queries.labels(operation="update", status="success").inc()

        logger.info(f"Reserved {quantity} units of product {product_id}")

        return {
            "product_id": product_id,
            "reserved": quantity,
            "remaining_stock": product.stock
        }
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        product_requests.labels(method="reserve", status="500").inc()
        db_queries.labels(operation="update", status="error").inc()
        raise HTTPException(status_code=500, detail="Database error")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
