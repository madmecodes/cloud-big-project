# Cloud E-Commerce Microservices Platform

A production-grade cloud-native e-commerce platform demonstrating advanced cloud architecture patterns using AWS and GCP.

## Architecture Diagram

```
                                    External Users
                                          |
                                          v
                              +-------------------+
                              |   AWS ALB (L7)    |
                              +-------------------+
                                          |
                                          v
+---------------------------------------------------------------------------------+
|                              AWS EKS Cluster                                     |
|  +---------------+                                                               |
|  | API Gateway   |-----> Routes to all internal services                         |
|  | (Python/8080) |                                                               |
|  +---------------+                                                               |
|         |                                                                        |
|         +----------------+----------------+----------------+                     |
|         |                |                |                |                     |
|         v                v                v                v                     |
|  +-------------+  +-------------+  +-------------+  +---------------+            |
|  |User Service |  |Product Svc  |  |Order Service|  |Payment Service|            |
|  |(Python/8001)|  |(Python/8001)|  |(Python/8003)|  |(Python/8004)  |            |
|  +-------------+  +-------------+  +-------------+  +---------------+            |
|         |                |                |                |                     |
|         v                v                |                |                     |
|  +-------------+  +-------------+         |                |                     |
|  |  RDS        |  |  RDS        |         |                |                     |
|  | PostgreSQL  |  | PostgreSQL  |         v                v                     |
|  +-------------+  +-------------+  +-------------+  +-------------+              |
|                                    |  DynamoDB   |  |  DynamoDB   |              |
|                                    |   orders    |  |  payments   |              |
|                                    +-------------+  +-------------+              |
+---------------------------------------------------------------------------------+

Inter-Service Communication (HTTP REST):
  - Order Service --> User Service (validate user)
  - Order Service --> Product Service (reserve stock)
  - Payment Service --> Order Service (update order status callback)

Event Streaming:
  +-------------+        +-------------+        +------------------+
  |Order Service| -----> |  AWS MSK    | -----> | GCP Dataproc     |
  |   (Kafka)   |        |   Kafka     |        | (Apache Flink)   |
  +-------------+        +-------------+        +------------------+
                               |
                               v
                        +-------------+
                        | AWS Lambda  |
                        | (Notifier)  |
                        +-------------+
```

## Microservices Architecture

| Service | Language | Port | Database | Description |
|---------|----------|------|----------|-------------|
| API Gateway | Python/FastAPI | 8080 | - | Public REST API entry point, routes to internal services |
| User Service | Python/FastAPI | 8001 | PostgreSQL (RDS) | User management and authentication |
| Product Service | Python/FastAPI | 8001 | PostgreSQL (RDS) | Product catalog, inventory management |
| Order Service | Python/FastAPI | 8003 | DynamoDB | Order processing, validates users, reserves stock |
| Payment Service | Python/FastAPI | 8004 | DynamoDB | Payment transactions, updates order status |
| Notification Lambda | Python | - | - | Serverless email/SMS notifications |
| Analytics (Flink) | Python | - | GCS | Real-time order analytics on GCP Dataproc |

## Database Architecture

```
+-------------------+     +-------------------+
|   PostgreSQL      |     |     DynamoDB      |
|   (AWS RDS)       |     |                   |
+-------------------+     +-------------------+
| - users           |     | - ecommerce-orders|
| - products        |     | - ecommerce-payments|
| - sessions        |     | - ecommerce-carts |
+-------------------+     | - ecommerce-sessions|
                          +-------------------+
```

## Inter-Service Communication

### HTTP REST Communication Flow

```
1. Create Order Flow:
   Client --> API Gateway --> Order Service
                                   |
                                   +--> User Service (GET /users/{id}) - Validate user exists
                                   |
                                   +--> Product Service (POST /products/{id}/reserve) - Reserve stock
                                   |
                                   +--> DynamoDB (PutItem) - Save order
                                   |
                                   +--> Kafka (publish) - Order event

2. Process Payment Flow:
   Client --> API Gateway --> Payment Service
                                   |
                                   +--> DynamoDB (PutItem) - Save payment
                                   |
                                   +--> Order Service (PUT /orders/{id}/status) - Update to "paid"
```

## Cloud Providers

### AWS (Primary)
- **EKS**: Managed Kubernetes for microservices
- **RDS PostgreSQL**: Relational data (users, products)
- **DynamoDB**: NoSQL data (orders, payments, sessions, carts)
- **MSK**: Managed Kafka for event streaming
- **Lambda**: Serverless notifications
- **S3**: Object storage (product images, documents)
- **ALB**: Application Load Balancer

### GCP (Analytics)
- **Dataproc**: Apache Flink for real-time analytics
- **Cloud Storage**: Analytics results storage

## Project Structure

```
cloud-bigProject/
├── terraform/                 # Infrastructure as Code
│   ├── aws/                   # AWS infrastructure
│   │   └── modules/           # VPC, EKS, RDS, DynamoDB, S3, MSK, Lambda, ALB
│   └── gcp/                   # GCP infrastructure
│       └── modules/           # Dataproc, Cloud Storage
├── services/                  # Microservices
│   ├── api-gateway/           # Python FastAPI Gateway
│   ├── user-service/          # Python FastAPI User Service
│   ├── product-service/       # Python FastAPI Product Service
│   ├── order-service/         # Python FastAPI Order Service
│   ├── payment-service/       # Python FastAPI Payment Service
│   └── notification-lambda/   # Python Lambda Notification
├── analytics/
│   └── flink-job/             # Python Flink Analytics Job
├── k8s/                       # Kubernetes & GitOps
│   ├── base/                  # Base manifests
│   ├── overlays/              # Environment-specific (dev/prod)
│   └── argocd/                # ArgoCD configuration
├── bruno/                     # API Collection (Bruno)
│   ├── External APIs/         # Public-facing APIs
│   └── Internal APIs/         # Service-to-service APIs
├── observability/             # Monitoring & Logging
├── load-tests/                # k6 load testing
└── docs/                      # Documentation
```

## Getting Started

### Prerequisites
- AWS Account with credentials configured
- GCP Project with credentials configured
- Docker installed
- Terraform >= 1.0
- kubectl installed

### Deploy Infrastructure
```bash
cd terraform/aws && terraform init && terraform apply
cd ../gcp && terraform init && terraform apply
```

### Deploy Microservices
```bash
# ArgoCD automatically syncs from Git
kubectl get pods -n ecommerce
```

## API Documentation

See `bruno/` directory for complete API collection.

## Scaling & Performance

| Service | Min Replicas | Max Replicas | Scaling Metric |
|---------|-------------|--------------|----------------|
| API Gateway | 2 | 5 | Manual |
| User Service | 2 | 4 | Manual |
| Product Service | 2 | 8 | Memory (80%) |
| Order Service | 2 | 10 | CPU (70%) |
| Payment Service | 2 | 8 | CPU (70%) |

## Monitoring

- **Prometheus**: Metrics collection (scrapes every 15s)
- **Grafana**: Visualization dashboards
- **Loki**: Log aggregation

## License

MIT
