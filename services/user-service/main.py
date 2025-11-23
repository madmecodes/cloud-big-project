from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import os
import uuid
import hashlib
import logging
from datetime import datetime
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="User Service", version="1.0.0")

# Prometheus metrics
REQUEST_COUNT = Counter('user_service_requests_total', 'Total requests', ['method', 'endpoint'])
USER_CREATED = Counter('users_created_total', 'Total users created')

# In-memory storage (in production, use PostgreSQL via DATABASE_URL)
users_db = {}
tokens_db = {}

DATABASE_URL = os.getenv("DATABASE_URL", "")

class UserCreate(BaseModel):
    email: str
    password: str
    name: str

class UserLogin(BaseModel):
    email: str
    password: str

class User(BaseModel):
    id: str
    email: str
    name: str
    created_at: str

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "user-service"}

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/auth/login")
async def login(credentials: UserLogin):
    REQUEST_COUNT.labels(method="POST", endpoint="/auth/login").inc()

    for user_id, user in users_db.items():
        if user["email"] == credentials.email:
            if user["password_hash"] == hash_password(credentials.password):
                token = str(uuid.uuid4())
                tokens_db[token] = user_id
                return {"token": token, "user_id": user_id, "message": "Login successful"}

    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/users", response_model=User)
async def create_user(user_data: UserCreate):
    REQUEST_COUNT.labels(method="POST", endpoint="/users").inc()

    # Check if email already exists
    for user in users_db.values():
        if user["email"] == user_data.email:
            raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": user_data.email,
        "name": user_data.name,
        "password_hash": hash_password(user_data.password),
        "created_at": datetime.utcnow().isoformat()
    }
    users_db[user_id] = user
    USER_CREATED.inc()

    logger.info(f"Created user: {user_id}")
    return User(id=user_id, email=user["email"], name=user["name"], created_at=user["created_at"])

@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str):
    REQUEST_COUNT.labels(method="GET", endpoint="/users/{id}").inc()

    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    user = users_db[user_id]
    return User(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"])

@app.put("/users/{user_id}")
async def update_user(user_id: str, user_data: UserCreate):
    REQUEST_COUNT.labels(method="PUT", endpoint="/users/{id}").inc()

    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    users_db[user_id]["email"] = user_data.email
    users_db[user_id]["name"] = user_data.name
    if user_data.password:
        users_db[user_id]["password_hash"] = hash_password(user_data.password)

    return {"message": "User updated", "user_id": user_id}

@app.delete("/users/{user_id}")
async def delete_user(user_id: str):
    REQUEST_COUNT.labels(method="DELETE", endpoint="/users/{id}").inc()

    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    del users_db[user_id]
    return {"message": "User deleted", "user_id": user_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
