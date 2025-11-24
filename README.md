# E-Commerce Microservices Platform - Complete Cloud-Native Implementation

## Assignment Overview
This project implements a **comprehensive cloud-native e-commerce platform** demonstrating enterprise-grade microservices architecture across multiple cloud providers with advanced DevOps practices.

**Assignment Document**: [Link to Assignment PDF](./assignment.pdf)

---

## 📋 Deliverables & Documentation

### Quick Navigation
Each point below represents a specific requirement with comprehensive documentation:

| Point | Requirement | Documentation | Status |
|-------|-------------|---|---|
| **PointA** | Infrastructure as Code (Terraform) | [PointA.md](./PointA.md) | ✅ Complete |
| **PointB** | Microservices Architecture (6+ services) | [PointB.md](./PointB.md) | ✅ Complete |
| **PointC** | Managed Kubernetes with HPA Scaling | [PointC.md](./PointC.md) | ✅ Complete |
| **PointD** | GitOps & CI/CD Pipeline (ArgoCD) | [PointD.md](./PointD.md) | ✅ Complete |
| **PointE** | Real-Time Stream Processing (Spark) | [PointE.md](./PointE.md) | ✅ Complete |
| **PointF** | Multi-Cloud Storage (RDS + DynamoDB + S3) | [PointF.md](./PointF.md) | ✅ Complete |
| **PointG** | Observability Stack (Prometheus + Loki + Grafana) | [PointG.md](./PointG.md) | ✅ Complete |
| **PointH** | Load Testing & HPA Validation (K6) | [PointH.md](./PointH.md) | ✅ Complete |

---

## 🎯 What's Implemented

### Infrastructure (PointA)
- **Terraform** manages all cloud infrastructure
- AWS EKS cluster (3 nodes, auto-scaling enabled)
- RDS PostgreSQL database
- DynamoDB tables (5 tables for orders, payments, sessions, carts, notifications)
- S3 buckets (product images, order documents, analytics results)
- SQS queues, IAM roles, VPC, security groups

### Microservices (PointB)
**7 Services, 6+ distinct purposes**:
1. **API Gateway** - Request routing (AWS ELB)
2. **User Service** - User management (FastAPI)
3. **Product Service** - Catalog & inventory (FastAPI)
4. **Order Service** - Order processing (FastAPI, Kafka + SQS publishing)
5. **Payment Service** - Payment handling (FastAPI)
6. **Notification Service** - Async event processing (AWS Lambda)
7. **Data Analytics Service** - Real-time metrics (GCP Dataproc + Spark)

**Multi-Cloud**: AWS (primary) + GCP (analytics)
**Serverless**: AWS Lambda for notifications

### Kubernetes & Auto-Scaling (PointC)
- **Managed K8s**: AWS EKS in ap-south-1
- **Stateless Services**: All 5 microservices are Deployments (horizontally scalable)
- **HPA (Horizontal Pod Autoscaler)**:
  - Order Service: 2-10 pods (15% CPU, 30% memory thresholds)
  - Payment Service: 2-8 pods (15% CPU, 30% memory thresholds)
- **Metrics Server**: Collecting real-time pod metrics
- **Load Balancing**: ClusterIP services with automatic traffic distribution

### GitOps & CI/CD (PointD)
- **GitHub Actions** (CI): Detects code changes → Builds Docker images → Pushes to ECR → Updates manifests
- **ArgoCD** (CD/GitOps): Monitors Git repo → Syncs manifests to EKS cluster
- **No Direct kubectl**: All deployments via Git commits
- **Automated**: Code push → CI builds → Manifests update → CD deploys (fully automated pipeline)

### Stream Processing (PointE)
- **Apache Spark Streaming** on GCP Dataproc
- **Consumes**: Kafka topic "orders" (from Order Service)
- **Processes**: Stateful 1-minute tumbling windows with unique user count aggregation
- **Publishes**: Results to "analytics-results" Kafka topic
- **Also stores**: Results to S3 and BigQuery
- **Different Cloud**: GCP (vs AWS primary)

### Storage Architecture (PointF)
**3 Distinct Cloud Storage Products**:
1. **RDS PostgreSQL** (SQL) - Users, Products, Metadata
2. **DynamoDB** (NoSQL) - Orders, Payments, Sessions, Carts, Notifications (high-throughput)
3. **S3** (Object Store) - Product images, Order docs, Analytics results
- **Integrated**: Each microservice uses optimal storage for its data type
- **Triggered**: Different storage systems triggered by different events in the order pipeline

### Observability (PointG)
- **Prometheus**: Scrapes metrics from all services (15-day retention)
- **Loki**: Aggregates logs from all pods via Promtail (7-day retention)
- **Grafana**: 2 production dashboards
  - Dashboard 1: Kubernetes & service metrics (RPS, error rate, latency, cluster health)
  - Dashboard 2: Microservice logs (per-service log streams)
- **Coverage**: All 5 microservices + Lambda + Dataproc job

### Load Testing & Validation (PointH)
- **K6 Load Testing**: Simple, concise test script (4.5 min duration)
- **Test Execution**: 0→25 virtual users generating sustained load
- **Results**:
  - 661 successful requests (0% error rate)
  - Order Service scaled 2→4 pods automatically
  - Response time: 264ms average (p95=584ms)
  - HPA scaling confirmed working perfectly
- **Tool**: `load-tests/k6/order-service-load-test.js` with README

---