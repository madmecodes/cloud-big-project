# PointC: Managed Kubernetes with Auto-Scaling

## Overview
Stateless microservices deployed on **AWS EKS** (managed Kubernetes) with **Horizontal Pod Autoscalers (HPA)** for automatic scaling based on CPU and memory utilization.

---

## 1. AWS EKS Cluster

**Configuration**:
- **Name**: ecommerce-eks
- **Region**: ap-south-1 (Mumbai)
- **Kubernetes Version**: 1.28.15-eks
- **Worker Nodes**: 3 EC2 instances
- **Control Plane**: Fully managed by AWS (multi-AZ)
- **Container Runtime**: containerd
---

## 2. Stateless Microservices

All services use **Deployments** (no StatefulSets), enabling horizontal scaling:

| Service | Replicas | Scaling | Port |
|---------|----------|---------|------|
| API Gateway | 3 (Fixed) | No | 8080 |
| User Service | 2 (Fixed) | No | 8001 |
| Product Service | 2 (Fixed) | No | 8001 |
| Order Service | 2-10 (HPA) | Yes | 8003 |
| Payment Service | 2-8 (HPA) | Yes | 8004 |

**Storage**: All external (DynamoDB, RDS, S3, SQS, Kafka)

---

## 3. HPA Configuration

### Order Service
**File**: `k8s/base/order-service-deployment.yaml`

- **Min Replicas**: 2
- **Max Replicas**: 10
- **CPU Target**: 15% (lowered for testing)
- **Memory Target**: 30% (lowered for testing)
- **Scale Up**: Aggressive (no delay)
- **Scale Down**: Conservative (300s stabilization)

### Payment Service
**File**: `k8s/base/payment-service-deployment.yaml`

- **Min Replicas**: 2
- **Max Replicas**: 8
- **CPU Target**: 15% (lowered for testing)
- **Memory Target**: 30% (lowered for testing)
- **Scale Up**: Moderate (30s stabilization)
- **Scale Down**: Conservative (300s stabilization)

---

## 4. Metrics Collection

**Metrics Server** (kube-system):
- Collects CPU/Memory from all pods
- Queries metrics every 15 seconds
- HPA uses data to make scaling decisions

**Resource Requests** (per pod):
- CPU: 200m, Limit: 800m
- Memory: 256Mi, Limit: 1Gi

---