# PointB: Microservices Architecture with Multi-Cloud Analytics

## Overview
E-Commerce platform with 7 microservices deployed across AWS and GCP, featuring event-driven serverless processing and real-time analytics on a separate cloud provider.

---

## 1. Six+ Microservices

| Service | Technology | Purpose | Cloud |
|---------|-----------|---------|-------|
| API Gateway | FastAPI (Custom Python) | Request routing & reverse proxy | AWS EKS |
| User Service | FastAPI | User management | AWS EKS |
| Product Service | FastAPI | Inventory management | AWS EKS |
| Order Service | FastAPI | Order processing & orchestration | AWS EKS |
| Payment Service | FastAPI | Payment processing | AWS EKS |
| Notification Service | AWS Lambda | Async event processing | AWS Lambda |
| Data Analytics Service | Apache Spark | Real-time analytics | GCP Dataproc |

**Total: 7 services** (exceeds minimum requirement of 6)

**API Gateway Details**:
- **Custom FastAPI service** written in Python (not AWS-managed)
- **Reverse proxy**: Routes all incoming requests to appropriate microservices
- **Location**: Deployed on AWS EKS alongside other services
- **Port**: 8080
- **Metrics**: Exposes Prometheus metrics for request count and latency monitoring
- **Endpoints**:
  - `/api/v1/users/*` → User Service
  - `/api/v1/products/*` → Product Service
  - `/api/v1/orders/*` → Order Service
  - `/api/v1/payments/*` → Payment Service

---

## 2. Data Analytics on Different Cloud Provider
**Service**: Data Analytics Service

**Cloud Provider**: GCP (Google Cloud Platform) - Different from Primary AWS
- **Technology**: Apache Spark (PySpark)
- **Platform**: GCP Dataproc
- **Data Source**: Confluent Cloud Kafka
- **Purpose**: Real-time order analytics and metrics

**Architecture**:
```
Order Service (AWS)
    ↓ (Publish Event)
Kafka Topic "orders" (Confluent Cloud)
    ↓ (Consumer)
GCP Dataproc Spark Job
    ↓ (Process & Aggregate)
Analytics Results (Cloud Storage S3)
```

---

## 3. Serverless Function (Event-Driven)

**Service**: Notification Service

**Platform**: AWS Lambda
- **Runtime**: Python 3.11
- **Trigger**: AWS SQS (event queue)
- **Asynchronous**: Yes
- **Event-Driven**: Yes

**Flow**:
```
Order Service
    ↓ (Send Message)
SQS Queue (ecommerce-order-events-dev)
    ↓ (Event Trigger)
Lambda Function (Notification Service)
    ↓ (Process Event)
DynamoDB (notifications table)
    ↓ (Store)
Notification Record Persisted
```

**Lambda Functionality**:
- Parse SQS events
- Extract order details
- Store notification records in DynamoDB
- Handle errors and logging

---

## 4. Cloud-Native Communication Mechanisms

### 4.1 REST/HTTP
- **Used Between**: User Service, Product Service, Order Service, Payment Service
- **Protocol**: Synchronous HTTP calls
- **Example**: Order Service validates user → HTTP GET to User Service

### 4.2 Message Queue (AWS SQS)
- **Queue Name**: ecommerce-order-events-dev
- **Purpose**: Asynchronous order event notification
- **Message Format**: JSON with order details
- **Retention**: 14 days

### 4.3 Stream Processing (Kafka)
- **Platform**: Confluent Cloud (Managed Kafka)
- **Topic**: orders
- **Purpose**: Real-time event streaming for analytics
- **Security**: SASL/SSL authentication
- **Subscribers**: GCP Dataproc Spark job

---

## 5. Architecture Diagram

```
┌─────────────┐
│   Users     │
└──────┬──────┘
       │ HTTP
       ▼
┌──────────────────────────────────────┐
│      AWS EKS Cluster                 │
│  ┌──────────┐  ┌─────────────┐      │
│  │   User   │  │  Product    │      │
│  │ Service  │  │  Service    │      │
│  └──────────┘  └─────────────┘      │
│  ┌────────────────────────────────┐ │
│  │      Order Service             │ │
│  │  (REST + Kafka + SQS)          │ │
│  └────────────────────────────────┘ │
│  ┌─────────────┐                   │
│  │  Payment    │                   │
│  │  Service    │                   │
│  └─────────────┘                   │
└──────┬──────────────┬───────────────┘
       │              │
       │ SQS          │ Kafka
       ▼              ▼
    ┌─────────┐   ┌──────────────────────┐
    │ SQS     │   │ Confluent Cloud      │
    │ Queue   │   │ Kafka Topic "orders" │
    └────┬────┘   └──────────┬───────────┘
         │                   │
         ▼                   ▼
    ┌────────────┐    ┌──────────────────┐
    │  Lambda    │    │ GCP Dataproc     │
    │ Function   │    │ Spark Job        │
    └────┬───────┘    └──────────────────┘
         │
         ▼
    ┌──────────────┐
    │ DynamoDB     │
    │ notifications│
    └──────────────┘
```

---

## 6. Deployment Across Clouds

### AWS (Primary)
- **Region**: ap-south-1
- **Services**: User, Product, Order, Payment (FastAPI on EKS)
- **Serverless**: Notification Lambda
- **Data Storage**: DynamoDB, RDS, S3
- **Message Queue**: SQS
- **Managed Kafka**: Confluent Cloud (hosted in Asia-South)

### GCP (Analytics Cloud)
- **Region**: asia-south1
- **Service**: Dataproc Cluster with Spark
- **Purpose**: Real-time analytics consumer from Kafka
- **Results**: Stored in BigQuery/Cloud Storage

---

## 7. Data Flow Examples

### Example 1: Order Creation to Notification Storage
```
1. User creates order via API Gateway
2. Order Service receives request
3. Order Service validates user (HTTP → User Service)
4. Order Service reserves stock (HTTP → Product Service)
5. Order Service saves to DynamoDB
6. Order Service publishes to Kafka topic "orders"
7. Order Service sends message to SQS queue
8. Lambda receives SQS event (automatic trigger)
9. Lambda parses event and converts types (float → Decimal)
10. Lambda stores notification in DynamoDB notifications table
11. Order fully processed ✅
```

### Example 2: Real-Time Analytics
```
1. Order Service publishes event to Kafka
2. GCP Dataproc Spark job consumes from Kafka
3. Spark processes and aggregates order data
4. Results sent to BigQuery for dashboards
5. Analytics available in real-time
```

---