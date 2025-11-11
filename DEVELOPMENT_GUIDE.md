# Cloud E-Commerce Microservices - Development Guide

## Project Overview
This guide provides the complete structure and skeleton code for implementing the e-commerce platform with 6+ microservices across AWS and GCP.

## Completed Phases

### Phase 1: Infrastructure (COMPLETED)
✅ AWS Terraform modules (VPC, EKS, RDS, DynamoDB, S3, MSK, Lambda, ALB)
✅ GCP Terraform modules (Dataproc, Cloud Storage, Cloud SQL)
✅ Project structure and documentation

### Phase 2: Microservices (IN PROGRESS)

#### Completed Services:
1. **User Service** (Go, gRPC)
   - Location: `services/user-service/`
   - Files: `main.go`, `go.mod`, `proto/user.proto`, `Dockerfile`
   - Port: 50051
   - DB: PostgreSQL

#### Services to Build (Templates Provided Below):

### 2. API Gateway (Go, REST)
**Location:** `services/api-gateway/`

```go
// main.go
package main

import (
	"context"
	"log"
	"os"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

func main() {
	router := gin.Default()

	// Prometheus metrics
	requestCounter := prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total HTTP requests",
		},
		[]string{"method", "path", "status"},
	)
	prometheus.MustRegister(requestCounter)

	// gRPC connections to downstream services
	userConn, _ := grpc.Dial(
		os.Getenv("USER_SERVICE_HOST")+":50051",
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	defer userConn.Close()

	// REST endpoints
	router.POST("/api/v1/auth/login", func(c *gin.Context) {
		// Call User Service gRPC
	})

	router.GET("/api/v1/users/:id", func(c *gin.Context) {
		// Call User Service gRPC
	})

	router.GET("/metrics", gin.WrapF(promhttp.Handler().ServeHTTP))
	router.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "healthy"})
	})

	router.Run(":8080")
}
```

**Dockerfile:**
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o api-gateway .

FROM alpine:latest
WORKDIR /root/
COPY --from=builder /app/api-gateway .
EXPOSE 8080
CMD ["./api-gateway"]
```

---

### 3. Product Service (Python, FastAPI + gRPC)
**Location:** `services/product-service/`

```python
# main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import os
from sqlalchemy import create_engine, Column, String, Float, DateTime, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import asyncpg
from concurrent import futures
import grpc
from prometheus_client import Counter, Histogram
import json

app = FastAPI(title="Product Service")
Base = declarative_base()

# Metrics
request_count = Counter('product_requests_total', 'Total requests', ['method'])
request_latency = Histogram('product_request_seconds', 'Request latency')

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5432/ecommerce")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class Product(Base):
    __tablename__ = "products"
    id = Column(String, primary_key=True)
    name = Column(String)
    description = Column(String)
    price = Column(Float)
    inventory = Column(String)  # JSON
    created_at = Column(DateTime, server_default=func.now())

Base.metadata.create_all(engine)

@app.get("/api/v1/products")
async def list_products(skip: int = 0, limit: int = 10):
    request_count.labels(method="list").inc()
    session = SessionLocal()
    products = session.query(Product).offset(skip).limit(limit).all()
    return products

@app.get("/api/v1/products/{product_id}")
async def get_product(product_id: str):
    request_count.labels(method="get").inc()
    session = SessionLocal()
    product = session.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.post("/api/v1/products")
async def create_product(name: str, description: str, price: float):
    request_count.labels(method="create").inc()
    # Implementation

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["python", "main.py"]
```

**requirements.txt:**
```
fastapi==0.104.0
uvicorn==0.24.0
sqlalchemy==2.0.0
psycopg2-binary==2.9.9
grpcio==1.59.0
grpcio-tools==1.59.0
prometheus-client==0.18.0
```

---

### 4. Order Service (Go, gRPC + REST + Kafka producer)
**Location:** `services/order-service/`

**Key Features:**
- gRPC server (port 50053)
- REST endpoints (port 8003)
- Kafka producer for order events
- Calls Payment Service gRPC
- Publishes to Kafka topic: `orders`

**Structure:**
```go
// services/order-service/main.go
// Similar to User Service but with:
// 1. Kafka producer initialization
// 2. Order creation that publishes to Kafka
// 3. REST endpoints via Gin
// 4. gRPC client calls to Payment Service
```

---

### 5. Payment Service (Go, gRPC + HPA)
**Location:** `services/payment-service/`

**Key Features:**
- gRPC server (port 50054)
- Stripe-like payment processing (mock)
- HPA configured for CPU-based scaling
- Calls to external payment APIs

---

### 6. Notification Service (Python, AWS Lambda)
**Location:** `services/notification-lambda/`

**Handler:**
```python
# lambda_function.py
import json
import boto3
import os

sns_client = boto3.client('sns')
dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    """
    Triggered by Kafka event through EventBridge
    - Consumes order.created events
    - Sends email/SMS notifications
    """
    try:
        for record in event['Records']:
            body = json.loads(record['body'])
            order_id = body['order_id']
            user_email = body['user_email']

            # Send SNS notification
            sns_client.publish(
                TopicArn=os.getenv('SNS_TOPIC_ARN'),
                Subject='Order Confirmation',
                Message=f'Your order {order_id} has been received!'
            )

        return {
            'statusCode': 200,
            'body': json.dumps('Notifications sent successfully')
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }
```

---

### 7. Analytics Service (Python, Flink on GCP Dataproc)
**Location:** `analytics/flink-job/`

**Key Features:**
- Consumes from Kafka topic: `orders`
- Tumbling window: 1 minute
- Aggregations: count, total_revenue, unique_users
- Publishes to topic: `analytics-results`

```python
# analytics/flink-job/main.py
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.window import TumblingEventTimeWindow
from pyflink.common.serialization import SimpleStringSchema
import json
from datetime import datetime, timedelta

def run():
    env = StreamExecutionEnvironment.get_execution_environment()

    # Source: Kafka
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    order_stream = env.add_source(
        FlinkKafkaConsumer(
            topics=['orders'],
            deserialization_schema=SimpleStringSchema(),
            properties={'bootstrap.servers': kafka_bootstrap}
        )
    )

    # Parse JSON
    parsed_stream = order_stream.map(lambda x: json.loads(x))

    # Window aggregation: 1-minute tumbling window
    windowed_stream = (
        parsed_stream
        .map(lambda x: (x['user_id'], 1, x['amount']))
        .key_by(lambda x: 'order_metrics')
        .window(TumblingEventTimeWindow.of(TimeUnit.MINUTES, 1))
        .reduce(lambda x, y: (
            x[0],  # dummy key
            x[1] + y[1],  # count
            x[2] + y[2]   # total_revenue
        ))
    )

    # Sink: Kafka results topic
    windowed_stream.add_sink(
        FlinkKafkaProducer(
            topic='analytics-results',
            serialization_schema=SimpleStringSchema(),
            properties={'bootstrap.servers': kafka_bootstrap}
        )
    )

    env.execute("E-commerce Analytics")

if __name__ == "__main__":
    run()
```

---

## Phase 3: Kubernetes Manifests & GitOps

### Kubernetes Base Manifests Structure

**Location:** `k8s/base/`

```yaml
# k8s/base/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ecommerce

---
# k8s/base/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ecommerce-config
  namespace: ecommerce
data:
  USER_SERVICE_HOST: "user-service"
  PRODUCT_SERVICE_HOST: "product-service"
  ORDER_SERVICE_HOST: "order-service"
  PAYMENT_SERVICE_HOST: "payment-service"
  DATABASE_HOST: "rds-endpoint"
  KAFKA_BOOTSTRAP_SERVERS: "msk-bootstrap-servers"

---
# k8s/base/user-service-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
  namespace: ecommerce
spec:
  replicas: 2
  selector:
    matchLabels:
      app: user-service
  template:
    metadata:
      labels:
        app: user-service
    spec:
      containers:
      - name: user-service
        image: ecommerce/user-service:latest
        ports:
        - containerPort: 50051
          name: grpc
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        livenessProbe:
          exec:
            command: ["/bin/sh", "-c", "grpcurl -plaintext localhost:50051 user.UserService/Authenticate"]
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          exec:
            command: ["/bin/sh", "-c", "grpcurl -plaintext localhost:50051 user.UserService/Authenticate"]
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi

---
# k8s/base/user-service-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: user-service
  namespace: ecommerce
spec:
  type: ClusterIP
  ports:
  - port: 50051
    targetPort: 50051
    protocol: TCP
    name: grpc
  selector:
    app: user-service
```

---

## Phase 4: HPA Configuration

```yaml
# k8s/base/order-service-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service-hpa
  namespace: ecommerce
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30

---
# k8s/base/payment-service-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: payment-service-hpa
  namespace: ecommerce
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: payment-service
  minReplicas: 2
  maxReplicas: 8
  metrics:
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## Phase 5: ArgoCD Setup

```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Create Application manifest
# k8s/argocd/ecommerce-app.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ecommerce-platform
  namespace: argocd
spec:
  project: default
  source:
    repoURL: 'https://github.com/your-org/cloud-bigProject'
    targetRevision: HEAD
    path: k8s/overlays/dev
  destination:
    server: 'https://kubernetes.default.svc'
    namespace: ecommerce
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

---

## Phase 6: Observability Stack

### Prometheus Configuration

```yaml
# observability/prometheus/prometheus-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s

    scrape_configs:
    - job_name: 'kubernetes-pods'
      kubernetes_sd_configs:
      - role: pod
      relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        regex: ([^:]+)(?::\d+)?;(\d+)
        replacement: $1:$2
        target_label: __address__
```

---

## Phase 7: Load Testing

```javascript
// load-tests/k6/load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  vus: 100,
  duration: '5m',
  stages: [
    { duration: '30s', target: 50 },
    { duration: '1m', target: 100 },
    { duration: '3m', target: 100 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.1'],
  }
};

export default function () {
  // Test API Gateway
  let response = http.get('http://api-gateway.example.com/api/v1/products');

  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time OK': (r) => r.timings.duration < 500,
  });

  // Create order (triggers Kafka, Lambda, Flink)
  let orderResponse = http.post(
    'http://api-gateway.example.com/api/v1/orders',
    JSON.stringify({
      user_id: 'user123',
      items: [{ product_id: 'prod1', quantity: 2 }]
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );

  check(orderResponse, {
    'order created': (r) => r.status === 201,
  });

  sleep(1);
}
```

---

## Build & Deployment Instructions

### 1. Build all Docker images
```bash
#!/bin/bash
cd services/
for service in api-gateway user-service product-service order-service payment-service; do
  docker build -t ecommerce/$service:latest $service/
  docker push ecommerce/$service:latest
done
```

### 2. Deploy AWS Infrastructure
```bash
cd terraform/aws
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

### 3. Deploy GCP Infrastructure
```bash
cd terraform/gcp
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

### 4. Deploy to EKS via ArgoCD
```bash
kubectl apply -f k8s/argocd/ecommerce-app.yaml
```

### 5. Deploy Flink Job
```bash
gcloud dataproc jobs submit spark-job \
  --cluster=analytics-cluster \
  --region=us-central1 \
  --jars=gs://analytics-results-bucket/flink-job.jar
```

---

## Environment Variables Required

### AWS Credentials
```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
```

### GCP Credentials
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
export GCP_PROJECT_ID=...
export GCP_REGION=us-central1
```

### Application Configuration
```bash
export DATABASE_URL=postgres://user:pass@rds-endpoint:5432/ecommerce
export KAFKA_BOOTSTRAP_SERVERS=msk-bootstrap-servers:9092
export REDIS_HOST=redis-endpoint
```

---

## Testing Checklist

- [ ] All Terraform plans execute successfully
- [ ] EKS cluster is running with nodes ready
- [ ] All microservices deployed and healthy
- [ ] gRPC communication working between services
- [ ] REST API endpoints responding
- [ ] Kafka topics created and receiving messages
- [ ] Lambda function triggered on order events
- [ ] Flink job running and aggregating data
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards displaying data
- [ ] EFK stack aggregating logs
- [ ] HPA scaling Order and Payment services under load

---

## Next Steps

1. **Generate protobuf code** for all gRPC services
2. **Implement database migrations** for each service
3. **Create Kubernetes manifests** for all services
4. **Set up ArgoCD** to manage deployments
5. **Deploy observability stack** (Prometheus, Grafana, EFK)
6. **Run load tests** to validate scaling
7. **Record demo video** showing end-to-end flow
8. **Document architecture** with diagrams

---

For detailed implementation of each service, follow the templates above and expand with business logic specific to your e-commerce domain.
