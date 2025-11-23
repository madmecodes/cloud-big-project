import os
import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, DateTime, func
from sqlalchemy.orm import sessionmaker, declarative_base
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5432/ecommerce")

engine = None
SessionLocal = None
Base = declarative_base()

def get_engine():
    global engine
    if engine is None:
        try:
            engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)
            logger.info("Database connected")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return None
    return engine

def get_db():
    global SessionLocal
    if SessionLocal is None:
        eng = get_engine()
        if eng:
            SessionLocal = sessionmaker(bind=eng)
    if SessionLocal:
        return SessionLocal()
    return None

# User Model
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())

# Pydantic Models
class UserCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None

    class Config:
        from_attributes = True

# Metrics
REQUEST_COUNT = Counter('user_service_requests_total', 'Total requests', ['method', 'endpoint'])

app = FastAPI(title="User Service", version="1.0.0")

@app.on_event("startup")
def startup():
    eng = get_engine()
    if eng:
        Base.metadata.create_all(bind=eng)
        logger.info("Database tables created")

@app.get("/health")
def health():
    return {"status": "healthy", "service": "user-service"}

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/users", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate):
    REQUEST_COUNT.labels(method="POST", endpoint="/users").inc()
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        existing = db.query(User).filter(User.email == user.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already exists")
        new_user = User(id=str(uuid.uuid4()), name=user.name, email=user.email, phone=user.phone)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"User created: {new_user.id}")
        return new_user
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: str):
    REQUEST_COUNT.labels(method="GET", endpoint="/users/{id}").inc()
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    finally:
        db.close()

@app.get("/users")
def list_users():
    REQUEST_COUNT.labels(method="GET", endpoint="/users").inc()
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        users = db.query(User).limit(100).all()
        return {"users": [{"id": u.id, "name": u.name, "email": u.email, "phone": u.phone} for u in users]}
    finally:
        db.close()

@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str):
    REQUEST_COUNT.labels(method="DELETE", endpoint="/users/{id}").inc()
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        db.delete(user)
        db.commit()
        return None
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
