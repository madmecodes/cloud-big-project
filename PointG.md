# PointG: Comprehensive Observability Stack

## Overview
A complete observability solution deployed on Kubernetes with metrics collection (Prometheus), centralized logging (Loki), and visualization (Grafana) for all microservices and the analytics job.

---

## 1. Observability Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      Microservices                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ API Gateway  │  │ User Service │  │ Product Svc  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Order Svc    │  │ Payment Svc  │  │ Dataproc Job │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└──┬─────────────┬────────────────────────────────┬────────────────┘
   │             │                                │
   │ Prometheus  │ Logs (stdout/stderr)           │
   │ Metrics     │                                │ Metrics
   ▼             ▼                                ▼
┌──────────────────────────────────────────────────────────────────┐
│              Observability Namespace (EKS Cluster)               │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Prometheus (Port 9090)                                   │  │
│  │ ├─ Scrapes metrics from all services                    │  │
│  │ ├─ Stores time-series data (15-day retention)           │  │
│  │ ├─ Evaluates alerting rules                             │  │
│  │ └─ Config: observability/prometheus/configmap.yaml      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Promtail DaemonSet                                       │  │
│  │ ├─ Runs on all Kubernetes nodes                          │  │
│  │ ├─ Scrapes pod logs (stdout/stderr)                     │  │
│  │ ├─ Extracts labels from pod metadata                     │  │
│  │ └─ Config: observability/loki/promtail.yaml             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Loki (Port 3100)                                         │  │
│  │ ├─ Log aggregation and indexing                          │  │
│  │ ├─ Accepts logs from Promtail                            │  │
│  │ ├─ Stores with 7-day retention                           │  │
│  │ ├─ Supports label-based querying                         │  │
│  │ └─ Config: observability/loki/deployment.yaml           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Grafana (Port 80 via LoadBalancer)                       │  │
│  │ ├─ Datasource 1: Prometheus (metrics)                    │  │
│  │ ├─ Datasource 2: Loki (logs)                             │  │
│  │ ├─ Dashboard 1: Kubernetes & Service Metrics             │  │
│  │ ├─ Dashboard 2: Microservices Logs                       │  │
│  │ └─ Config: observability/grafana/deployment.yaml        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
                ┌─────────┐      ┌────────────┐
                │Dashboard│      │Log Queries │
                │ Browser │      │ & Insights │
                └─────────┘      └────────────┘
```

---

## 2. Components

### 2.1 Prometheus (Metrics Collection)
**Location**: `observability/prometheus/`

**Purpose**: Time-series database for metrics collection

**Deployment**:
- File: `prometheus/deployment.yaml`
- Config: `prometheus/configmap.yaml`
- Service: ClusterIP on port 9090

**Metrics Scraped**:
- Kubernetes cluster metrics (nodes, pods, memory, CPU)
- Application metrics from all microservices
- HTTP request rates, errors, and latency
- Custom application metrics (orders created, user registrations, etc.)

**Data Retention**: 15 days

**Configuration**:
- Scrape interval: 15 seconds
- Targets: API Gateway, User Service, Product Service, Order Service, Payment Service, Dataproc metrics

---

### 2.2 Loki (Log Aggregation)
**Location**: `observability/loki/`

**Purpose**: Centralized log aggregation and indexing

**Deployment**:
- Loki Server: `loki/deployment.yaml` (Deployment + Service + ConfigMap)
- Promtail Collector: `loki/promtail.yaml` (DaemonSet + Config + RBAC)
- Service: ClusterIP on port 3100

**Log Collection**:
- Promtail runs as DaemonSet on all Kubernetes nodes
- Scrapes pod logs from ecommerce and observability namespaces
- Extracts labels: namespace, pod, container, app
- Sends to Loki for indexing and storage

**Log Sources**:
- API Gateway
- User Service
- Product Service
- Order Service
- Payment Service
- Dataproc Analytics Job (via pod logs)

**Data Retention**: 7 days

**Storage**: Local filesystem with boltdb-shipper (production: use S3/GCS)

---

### 2.3 Grafana (Visualization)
**Location**: `observability/grafana/`

**Purpose**: Dashboards and visualization UI

**Deployment**:
- File: `grafana/deployment.yaml` (Deployment + Service)
- Service: LoadBalancer on port 80
- Access: `http://<EXTERNAL-IP>`
- Credentials: `admin / admin123`

**Datasources**:
- **Prometheus**: `http://prometheus:9090` (auto-configured)
- **Loki**: `http://loki:3100` (auto-configured)

---