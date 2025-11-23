# Cloud E-Commerce Microservices Platform - Comprehensive Analysis

## Executive Summary

This is a **production-grade, cloud-native e-commerce platform** demonstrating advanced cloud architecture patterns with **multi-cloud deployment** (AWS + GCP), **GitOps-based deployment** via ArgoCD, **real-time stream processing** with Apache Flink, and a **comprehensive observability stack**.

The project is designed to showcase enterprise-level cloud architecture with 6-7 microservices, managed cloud infrastructure, containerization, orchestration, and full observability.

---

## 1. MICROSERVICES ARCHITECTURE (6 Core Services)

### 1.1 Service Overview

| Service | Language | Protocol | Purpose | Port(s) |
|---------|----------|----------|---------|---------|
| API Gateway | Go | REST/HTTP + gRPC | Public entry point, request routing | 8080 (HTTP), 9090 (metrics) |
| User Service | Go | gRPC | Authentication, user management | 50051 (gRPC), 9090 (metrics) |
| Product Service | Python (FastAPI) | REST/HTTP + gRPC | Product catalog, search | 50052 (gRPC), 8001 (HTTP), 9090 (metrics) |
| Order Service | Go | gRPC + REST + Kafka | Order processing, event publishing | 50053 (gRPC), 8003 (HTTP), 9090 (metrics) |
| Payment Service | Go | gRPC + REST | Payment processing | 50054 (gRPC), 8004 (HTTP), 9090 (metrics) |
| Notification Lambda | Python | Kafka Consumer | Serverless notifications | (AWS Lambda) |
| Analytics (Flink) | Python | Kafka Consumer | Real-time analytics | (GCP Dataproc) |

### 1.2 Communication Patterns

**REST (Synchronous)**
- API Gateway ↔ External Clients: All public REST API endpoints
- Gateway → Backend Services: Orchestration and data retrieval

**gRPC (High-Performance Internal)**
- User Service ↔ Order Service: User verification and authentication
- Order Service ↔ Payment Service: Payment processing
- Product Service ↔ Order Service: Product information lookup
- Low latency, binary protocol, multiplexing support

**Kafka/Event Streaming (Asynchronous)**
- Order Service → Kafka `orders` topic: Order created events
- Lambda Consumer: Order events → Sends email notifications (AWS SNS)
- Flink Analytics: Order events → Real-time aggregations (1-min windows)
- Analytics Results → Kafka `analytics-results` topic

### 1.3 Key Service Characteristics

**All Services Include:**
- Prometheus metrics instrumentation (custom counters, histograms)
- Health checks (liveness/readiness probes)
- Structured logging
- Graceful shutdown handling
- Resource limits (CPU/Memory)
- Security context (non-root, read-only filesystem, no privilege escalation)

---

## 2. CLOUD INFRASTRUCTURE (AWS + GCP)

### 2.1 AWS Infrastructure (Primary Cloud)

**Location:** `/terraform/aws/`

Terraform modules for complete infrastructure provisioning:

#### VPC & Network
- VPC with CIDR: 10.0.0.0/16
- 3 Availability Zones (us-east-1a, us-east-1b, us-east-1c)
- Public subnets: 10.0.1.0/24, 10.0.2.0/24, 10.0.3.0/24
- Private subnets: 10.0.11.0/24, 10.0.12.0/24, 10.0.13.0/24
- NAT Gateway for high availability
- Internet Gateway for public access

#### EKS (Kubernetes)
- **Cluster Name:** ecommerce-eks
- **Version:** 1.28
- **Node Groups:**
  - Primary: t3.medium instances (3 desired, 3-10 range)
  - Capacity type: ON_DEMAND
  - Disk size: 50GB
- Multi-AZ deployment for HA

#### Relational Database (RDS)
- **Engine:** PostgreSQL 15.3
- **Instance Class:** db.t3.micro (configurable)
- **Storage:** 20GB (configurable)
- **Features:**
  - Multi-AZ: Optional
  - Automated backups: 30-day retention
  - Not publicly accessible
  - VPC-based deployment

#### Cache & Session Store (DynamoDB)
- **Tables:** 
  - `ecommerce-sessions`: Session storage with TTL
    - Hash key: session_id
    - Billing: PAY_PER_REQUEST
  - `ecommerce-carts`: Shopping cart state
    - Hash key: user_id, Range key: product_id
    - TTL support for expiring carts
    - Billing: PAY_PER_REQUEST

#### File Storage (S3)
- **Buckets:**
  - `ecommerce-product-images-{account-id}`: Product images
  - `ecommerce-order-documents-{account-id}`: Order documentation
  - `ecommerce-analytics-results-{account-id}`: Analytics outputs
- **Features:**
  - Versioning enabled (product images, order documents)
  - Server-side encryption
  - No public access
  - Account ID in bucket name for uniqueness

#### Message Queue (MSK - Managed Kafka)
- **Cluster Name:** ecommerce-kafka
- **Kafka Version:** 3.5.1
- **Brokers:** 3 (configurable)
- **Instance Type:** kafka.t3.small
- **Storage:** 100GB per broker (configurable)
- **Features:**
  - CloudWatch logging enabled
  - Private VPC deployment
  - Auto topic creation enabled
  - Topic deletion allowed
- **Topics:**
  - `orders`: Order placement events
  - `analytics-results`: Real-time analytics output
  - `notifications`: Notification events

#### Serverless Compute (Lambda)
- **Function:** ecommerce-notification
- **Runtime:** Python 3.11
- **Handler:** index.handler
- **Memory:** 512MB (configurable)
- **Timeout:** 60 seconds (configurable)
- **VPC Deployment:** Integrated with private subnets
- **Environment Variables:**
  - KAFKA_BROKERS: MSK connection string
  - SNS_TOPIC_ARN: SNS topic for email notifications

#### Load Balancer (ALB)
- **Name:** ecommerce-alb
- **Type:** Application Load Balancer
- **Deployment:** Public subnets across AZs
- **Features:**
  - HTTP/2 enabled
  - Cross-zone load balancing
  - Deletion protection (configurable)

#### Notifications (SNS)
- **Topic:** ecommerce-notifications
- **Purpose:** Email and notification delivery
- **Integration:** Lambda → SNS → Email subscribers

#### Security
- **ALB Security Group:**
  - Inbound: HTTP (80), HTTPS (443) from 0.0.0.0/0
  - Outbound: All protocols
- **Lambda Security Group:**
  - Inbound: All protocols from ALB
  - Outbound: All protocols
- **Tags:** Environment, Project, ManagedBy, CreatedAt

### 2.2 GCP Infrastructure (Analytics Cloud)

**Location:** `/terraform/gcp/`

#### Network
- **VPC Network:** ecommerce-network
- **Subnet:** ecommerce-subnet (CIDR configurable)
- **Private Google Access:** Enabled
- **Routing Mode:** Regional

#### Cloud Storage (GCS)
- **Buckets:**
  - `ecommerce-flink-code-{project-id}`: Python Flink job code and jars
  - `ecommerce-analytics-results-{project-id}`: Analytics results storage
- **Features:**
  - Uniform bucket-level access
  - Force destroy enabled for cleanup
  - Labels for organization

#### Dataproc (Apache Spark/Flink Cluster)
- **Cluster Name:** ecommerce-analytics
- **Region:** us-central1 (configurable)
- **Master Node:**
  - Machine type: n1-standard-4 (configurable)
  - Boot disk: 50GB
- **Worker Nodes:**
  - Count: 2 (configurable)
  - Machine type: n1-standard-4
  - Boot disk: 50GB
- **Software Configuration:**
  - Image version: 2.1-debian11
  - Optional components: PYTHON3, JUPYTER, DOCKER, HIVE_WEBHCAT
  - Allow zero workers for cost optimization
- **Staging Bucket:** GCS bucket for code/jars
- **Endpoint Configuration:** HTTP port access enabled

#### IAM & Service Accounts
- **Service Account:** ecommerce-flink
- **Roles:**
  - Storage Admin (GCS access)
  - Dataproc Worker (cluster operations)
  - Dataproc Editor (job submission)
- **Scope:** Cloud Platform (full access)

#### Cloud SQL (Optional)
- **Purpose:** Analytics data warehouse
- **Engine:** PostgreSQL 15
- **Configuration:** ZONAL availability
- **Features:**
  - Backup enabled
  - Deletion protection: false
  - SSL not required

#### Enabled APIs
- compute.googleapis.com
- container.googleapis.com
- dataproc.googleapis.com
- storage.googleapis.com
- sqladmin.googleapis.com
- cloudresourcemanager.googleapis.com

---

## 3. KUBERNETES DEPLOYMENTS & SCALING

### 3.1 Deployment Configuration

**Location:** `/k8s/base/`

All services deployed to `ecommerce` namespace with:
- **Image Pull Policy:** IfNotPresent
- **Replica Defaults:** 2 (managed by HPA for Order/Payment)
- **Security Context:**
  - runAsNonRoot: true
  - readOnlyRootFilesystem: true
  - allowPrivilegeEscalation: false
  - capabilities: ALL dropped

### 3.2 Service Deployments Details

#### 1. API Gateway Deployment
```
Replicas: 2
Ports: 8080 (HTTP), 9090 (metrics)
Resources:
  Requests: 100m CPU, 128Mi RAM
  Limits: 500m CPU, 512Mi RAM
Health Checks:
  Liveness: HTTP /health (10s initial, 10s period, 3 failures)
  Readiness: HTTP /health (5s initial, 5s period, 2 failures)
Service Type: LoadBalancer (exposes on port 80)
HPA: Manual scaling (1-5 replicas)
```

#### 2. User Service Deployment
```
Replicas: 2
Ports: 50051 (gRPC), 9090 (metrics)
Resources:
  Requests: 100m CPU, 128Mi RAM
  Limits: 500m CPU, 512Mi RAM
Health Checks:
  Liveness: gRPC HealthCheck on 50051 (15s initial, 10s period, 3 failures)
  Readiness: gRPC HealthCheck on 50051 (10s initial, 5s period, 2 failures)
Service Type: ClusterIP
HPA: Manual scaling (1-3 replicas)
```

#### 3. Product Service Deployment
```
Replicas: 2
Ports: 50052 (gRPC), 8001 (HTTP), 9090 (metrics)
Resources:
  Requests: 100m CPU, 256Mi RAM
  Limits: 500m CPU, 1Gi RAM
Health Checks:
  Liveness: HTTP /health on 8001 (15s initial, 10s period, 3 failures)
  Readiness: HTTP /health on 8001 (10s initial, 5s period, 2 failures)
Service Type: ClusterIP
HPA: Memory-based (2-8 replicas)
```

#### 4. Order Service Deployment
```
Replicas: 2
Ports: 50053 (gRPC), 8003 (HTTP), 9090 (metrics)
Resources:
  Requests: 200m CPU, 256Mi RAM
  Limits: 800m CPU, 1Gi RAM
Health Checks:
  Liveness: gRPC HealthCheck on 50053 (15s initial, 10s period, 3 failures)
  Readiness: gRPC HealthCheck on 50053 (10s initial, 5s period, 2 failures)
Service Type: ClusterIP
HPA: CPU + Memory based (2-10 replicas)
Kafka Integration: Publishes to 'orders' topic
```

#### 5. Payment Service Deployment
```
Replicas: 2
Ports: 50054 (gRPC), 8004 (HTTP), 9090 (metrics)
Resources:
  Requests: 200m CPU, 256Mi RAM
  Limits: 800m CPU, 1Gi RAM
Health Checks:
  Liveness: gRPC HealthCheck on 50054 (15s initial, 10s period, 3 failures)
  Readiness: gRPC HealthCheck on 50054 (10s initial, 5s period, 2 failures)
Service Type: ClusterIP
HPA: CPU + Memory based (2-8 replicas)
Stripe Integration: Uses STRIPE_API_KEY secret
```

### 3.3 Horizontal Pod Autoscaling (HPA) Configuration

#### Order Service HPA
```yaml
API Version: autoscaling/v2
Min Replicas: 2
Max Replicas: 10
Metrics:
  - CPU: 70% target utilization
  - Memory: 80% target utilization
Scale Up:
  - 100% increase every 30 seconds
  - Or 2 pods every 30 seconds
  - Stabilization: 0 seconds (immediate scaling)
Scale Down:
  - 50% decrease every 60 seconds
  - Stabilization: 300 seconds (5 minutes)
```

#### Payment Service HPA
```yaml
API Version: autoscaling/v2
Min Replicas: 2
Max Replicas: 8
Metrics:
  - Memory: 80% target utilization
  - CPU: 70% target utilization
Scale Up:
  - 50% increase every 30 seconds
  - Or 1 pod every 30 seconds
  - Stabilization: 30 seconds
Scale Down:
  - 25% decrease every 60 seconds
  - Stabilization: 300 seconds (5 minutes)
```

#### Product Service HPA (Memory-based)
```yaml
API Version: autoscaling/v2
Min Replicas: 2
Max Replicas: 8
Metrics:
  - Memory: Primary scaling trigger
Scale Behavior: Custom policies for stable scaling
```

### 3.4 Kubernetes Secrets & ConfigMaps

**Secrets (`/k8s/base/secrets.yaml`):**
- `db-credentials`: DATABASE_URL (PostgreSQL RDS)
- `stripe-credentials`: STRIPE_API_KEY (Payment processing)
- Other service credentials

**ConfigMaps (`/k8s/base/configmap.yaml`):**
- KAFKA_BOOTSTRAP_SERVERS: MSK cluster endpoint
- KAFKA_ORDERS_TOPIC: Topic for order events
- SERVICE_HOST variables for service discovery
- LOG_LEVEL: Application logging level

### 3.5 Service Mesh & Network Policies

**Network Policies (`k8s/overlays/default/networkpolicy.yaml`):**
- Pod-to-pod communication rules
- Namespace isolation
- Egress to external services

---

## 4. GITOPS & ARGOCD DEPLOYMENT

### 4.1 ArgoCD Architecture

**Location:** `/k8s/argocd/`

#### App-of-Apps Pattern
```
Root Application: ecommerce-app-of-apps
├── ecommerce-services (Microservices)
│   └── Deployed from: k8s/overlays/default/
│       Namespace: ecommerce
│
├── ecommerce-observability (Monitoring Stack)
│   └── Deployed from: k8s/base/
│       Namespace: monitoring
│       Components: Prometheus, Grafana, Loki, Promtail
│
└── Infrastructure (via Helm charts)
    └── kube-prometheus-stack (v54.0.0)
```

#### Key Features
- **Sync Policy:** Automated (prune: true, selfHeal: true)
- **Retry Logic:** 5 retries with exponential backoff (5s-3m)
- **Sync Options:**
  - CreateNamespace: Create if missing
  - RespectIgnoreDifferences: Ignore specific fields
  - Validate: Validate manifests before apply
- **Ignore Differences:** HPA-managed replicas (spec.replicas)

### 4.2 Kustomize Configuration

**Location:** `/k8s/overlays/default/`

#### Kustomization Structure
```
k8s/overlays/default/
├── kustomization.yaml      - Overlay configuration
├── configmap.yaml          - Environment-specific config
└── networkpolicy.yaml      - Network policies
```

#### Overlay Configuration
- **Bases:** References `k8s/base/` manifests
- **Resource Patches:**
  - Replica count adjustments
  - Image tag overrides
  - Resource limit patches
- **Config Patches:**
  - Environment-specific values
  - Service discovery addresses

### 4.3 ArgoCD Installation & RBAC

**Location:** `/k8s/argocd/install/`

```
argocd/install/
├── namespace.yaml          - argocd namespace
├── argocd-cm.yaml         - ConfigMap (settings, RBAC, SSH keys)
├── argocd-rbac.yaml       - ServiceAccounts and ClusterRoles
└── kustomization.yaml     - Installation overlay
```

#### RBAC Roles Defined
- **admin:** Full cluster access
- **developer:** Application deployment and management
- **ops:** Operational tasks and monitoring

#### Configuration Includes
- SSH known hosts for Git repositories
- TLS certificate configuration
- Server and repo server settings
- Webhook configuration
- Logging levels

### 4.4 Git Repository Integration

**Git Structure:** `.gitops/`

```
.gitops/
├── README.md               - Repository structure guide
└── WORKFLOW.md            - Complete GitOps workflow
```

#### Workflow
1. Developer pushes changes to Git repo
2. ArgoCD detects changes in monitored paths
3. Automatic sync applies manifests to EKS
4. No direct `kubectl apply` commands needed
5. Single source of truth: Git repository

#### Branch Strategy
- `main` branch: Production deployments
- Pull request reviews: Code changes
- Commit messages: Conventional commits format
- Tags: Semantic versioning for releases

---

## 5. KAFKA & STREAM PROCESSING

### 5.1 Kafka/MSK Setup

**Cluster Details:**
- Managed Service: AWS MSK (Managed Streaming for Apache Kafka)
- Version: 3.5.1
- Brokers: 3 (production-ready)
- Instance Type: kafka.t3.small
- Storage: 100GB per broker
- Network: Private VPC subnets

**Topics:**
1. **orders** - Order placement events
   - Producer: Order Service
   - Consumers: Lambda (notifications), Flink (analytics)
   - Retention: Default (7 days)

2. **analytics-results** - Aggregated analytics
   - Producer: Flink job
   - Consumer: Applications/dashboards
   - Retention: Long-term (for historical analysis)

### 5.2 Stream Processing with Apache Flink

**Location:** `/analytics/flink-job/`

#### Flink Job Architecture
```python
Kafka Source: orders topic
    ↓
Order Event Parser: Parse JSON to OrderEvent objects
    ↓
Filter: Remove invalid events
    ↓
Timestamp Assignment: Extract event time for windowing
    ↓
Key-By Aggregation: Key by 'all_orders' (global aggregation)
    ↓
1-Minute Tumbling Window: 60-second time windows
    ↓
Reduce & Window Function: Aggregate within window
    ↓
Kafka Sink: analytics-results topic
    ↓
Console Sink: Stdout for debugging
```

#### Flink Configuration
- **Execution Environment:** StreamExecutionEnvironment
- **Parallelism:** 4 (configurable)
- **State Backend:** RocksDB (fault-tolerant)
- **Watermarking:** 10-second lag for late data
- **Checkpointing:** Enabled for recovery

#### Window Aggregations (1-minute windows)
```
Output Metrics:
- order_count: Number of orders in window
- total_revenue: Sum of order amounts
- total_items: Total items sold
- unique_users: Count of unique user IDs
- average_order_value: total_revenue / order_count
- window_start/end: Window timestamps
```

#### Flink Job Deployment
- **Platform:** GCP Dataproc cluster
- **Python Runtime:** Python 3.8+
- **Dependencies:**
  - pyflink: Apache Flink Python API
  - kafka: Kafka connectivity
  - logging: Structured logging
- **Job Name:** ecommerce-analytics
- **Submission:** Via `submit.sh` script

---

## 6. OBSERVABILITY STACK

### 6.1 Prometheus (Metrics Collection)

**Location:** `/k8s/base/prometheus-deployment.yaml` & `/observability/prometheus/`

#### Configuration
```yaml
Global Settings:
  Scrape Interval: 15 seconds
  Evaluation Interval: 15 seconds
  Retention: 30 days
  Storage Path: /prometheus (EmptyDir in K8s)

Scrape Configs:
1. kubernetes-pods:
   - Scrapes pods with prometheus.io/scrape: "true" annotation
   - Namespace filter: ecommerce, monitoring
   - Relabeling: Extracts port, path, labels from annotations

2. kubernetes-services:
   - Service monitoring
   - Blackbox exporter for HTTP checks

3. self-monitoring:
   - Prometheus scrapes itself
```

#### Deployment Details
```yaml
Replicas: 1
Image: prom/prometheus:latest
Port: 9090
Resources:
  Requests: 100m CPU, 256Mi RAM
  Limits: 500m CPU, 1Gi RAM
Volume:
  Config: ConfigMap (prometheus.yml)
  Storage: EmptyDir (non-persistent)
RBAC: ClusterRole with pod/node/service discovery
```

#### Custom Metrics from Services

**API Gateway Metrics:**
- http_requests_total: Total requests by method/path/status
- http_request_duration_seconds: Request latency histogram
- grpc_calls_total: gRPC downstream service calls

**Order Service Metrics:**
- orders_created_total: Orders created by user_id
- order_latency_seconds: Processing latency by operation
- kafka_events_published_total: Events published to Kafka by topic/status

**Other Services:**
- Service-specific counters, histograms, gauges
- Kubernetes metrics (kubelet)
- Container metrics (cAdvisor)

### 6.2 Grafana (Visualization & Dashboards)

**Location:** `/k8s/base/grafana-deployment.yaml` & `/observability/grafana/`

#### Deployment
```yaml
Replicas: 1
Image: grafana/grafana:latest
Port: 3000
Default Admin Password: admin (change in production!)
Resources:
  Requests: CPU/RAM as per needs
  Limits: High for dashboard rendering
Volume:
  Provisioning: Datasources config
  Storage: grafana_data volume
Plugins: grafana-piechart-panel
```

#### Datasources
```yaml
Primary: Prometheus
  - URL: http://prometheus:9090
  - IsDefault: true
  - Allow external access to Prometheus (cors enabled)

Loki (Logs):
  - URL: http://loki:3100
  - Log aggregation source
```

#### Pre-configured Dashboards
- **Cluster Health:** CPU, memory, disk utilization across nodes
- **Service Metrics:** RPS, latency, error rates per service
- **Kafka Metrics:** Broker health, topic metrics, lag monitoring
- **Flink Job Metrics:** Window processing, output rates
- **Kubernetes Dashboards:** Pod status, resource usage

#### Access
- **URL:** http://grafana.ecommerce.local:3000
- **Default User:** admin
- **Password:** admin

### 6.3 Loki (Log Aggregation)

**Location:** `/k8s/base/loki-deployment.yaml` & `/observability/`

#### Deployment
```yaml
Replicas: 1
Image: grafana/loki:2.9.0
Port: 3100
Configuration File: /etc/loki/local-config.yaml
Volume:
  Storage: loki_data (persistent)
Health Check: /loki/api/v1/status/ready endpoint
```

#### Loki Features
- Log ingestion from Promtail
- Label-based storage and retrieval
- Integration with Grafana
- Query language: LogQL (similar to PromQL)

#### Log Streams
- Application logs from all microservices
- Container logs from Kubernetes
- System logs

### 6.4 Promtail (Log Scraping)

**Location:** `/k8s/base/promtail-deployment.yaml` & `/observability/promtail/`

#### Configuration
```yaml
Image: grafana/promtail:2.9.0
Volumes:
  - /var/lib/docker/containers: Docker container logs
  - /var/run/docker.sock: Docker daemon socket
Configuration: /etc/promtail/config.yaml
Environment: HOSTNAME=docker-host
```

#### Scrape Configuration
- Docker log driver log collection
- Label extraction from container metadata
- Forwarding to Loki on port 3100

### 6.5 Docker Compose Observability Stack

**Local Development:** `/docker-compose.yml`

```yaml
Services:
- prometheus:9090
- grafana:3000
- loki:3100
- promtail:3101 (readiness endpoint)
- kafka-ui:8888 (Kafka monitoring)

Volumes:
- prometheus_data: Metrics storage
- grafana_data: Dashboard storage
- loki_data: Log storage
```

---

## 7. API ENDPOINTS & SERVICES

### 7.1 REST Endpoints (API Gateway)

**Base URL:** `http://api-gateway.ecommerce.local` or `http://localhost:8080`

#### Authentication Endpoints
```
POST   /api/v1/auth/login
  Request: { email, password }
  Response: { id, email, token }
  
POST   /api/v1/auth/logout
  Headers: Authorization: Bearer {token}
  
POST   /api/v1/auth/register
  Request: { email, password, first_name, last_name }
```

#### Product Endpoints
```
GET    /api/v1/products
  Query: skip=0, limit=10
  Response: { products: [...], total }
  
GET    /api/v1/products/{product_id}
  Response: { id, name, price, stock, description }
  
GET    /api/v1/products/search
  Query: q=keyboard
  Response: { results: [...] }
```

#### Order Endpoints
```
POST   /api/v1/orders
  Request: { user_id, items, shipping_address }
  Response: { order_id, status, total_amount }
  
GET    /api/v1/orders/{order_id}
  Response: { id, status, items, total_amount, created_at }
  
GET    /api/v1/orders
  Query: user_id, status=pending
  Response: { orders: [...] }
  
PUT    /api/v1/orders/{order_id}/cancel
  Response: { status, cancelled_at }
```

#### Payment Endpoints
```
POST   /api/v1/payments
  Request: { order_id, amount, method }
  Response: { payment_id, status, transaction_id }
  
GET    /api/v1/payments/{payment_id}
  Response: { id, order_id, amount, status }
```

#### Health & Metrics
```
GET    /health
  Response: { status: "healthy" }
  
GET    /metrics
  Response: Prometheus metrics format
```

### 7.2 gRPC Services

#### UserService (Port 50051)
```
service UserService {
  rpc Authenticate(AuthRequest) returns (UserResponse);
  rpc GetUser(GetUserRequest) returns (UserResponse);
  rpc CreateUser(CreateUserRequest) returns (UserResponse);
  rpc HealthCheck(Empty) returns (HealthStatus);
}
```

#### ProductService (Port 50052)
```
service ProductService {
  rpc GetProduct(GetProductRequest) returns (ProductResponse);
  rpc ListProducts(ListProductsRequest) returns (ListProductsResponse);
  rpc SearchProducts(SearchRequest) returns (SearchResponse);
  rpc HealthCheck(Empty) returns (HealthStatus);
}
```

#### OrderService (Port 50053)
```
service OrderService {
  rpc CreateOrder(CreateOrderRequest) returns (OrderResponse);
  rpc GetOrder(GetOrderRequest) returns (OrderResponse);
  rpc ListOrders(ListOrdersRequest) returns (ListOrdersResponse);
  rpc HealthCheck(Empty) returns (HealthStatus);
}
```

#### PaymentService (Port 50054)
```
service PaymentService {
  rpc ProcessPayment(PaymentRequest) returns (PaymentResponse);
  rpc GetPaymentStatus(PaymentStatusRequest) returns (PaymentStatus);
  rpc HealthCheck(Empty) returns (HealthStatus);
}
```

---

## 8. LOAD TESTING & TESTING INFRASTRUCTURE

### 8.1 K6 Load Testing Framework

**Location:** `/load-tests/k6/load-test.js`

#### Test Configuration
```javascript
Stages:
1. Ramp-up (30s): 0 → 20 VUs
2. Steady-state (1m30s): 20 → 50 VUs
3. Spike (1m): 50 → 100 VUs
4. Cool-down (1m): 100 → 50 VUs
5. Ramp-down (30s): 50 → 0 VUs

Total Duration: ~5 minutes
```

#### Performance Thresholds
```
HTTP Request Duration: p(95) < 500ms, p(99) < 1000ms
Request Failure Rate: < 10%
Custom Error Rate: < 5%
API Latency: p(95) < 200ms
Order Latency: p(95) < 1000ms
```

#### Test Scenarios
1. **Health Check**
   - Endpoint: GET /health
   - Expected: 200 status

2. **Product Listing**
   - Endpoint: GET /api/v1/products?skip=0&limit=10
   - Assertion: Includes product data, < 200ms latency

3. **Product Detail**
   - Endpoint: GET /api/v1/products/{product_id}
   - Assertion: Returns product details, < 300ms latency

4. **User Registration/Login**
   - Endpoint: POST /api/v1/auth/login
   - Assertion: Returns JWT token, < 500ms latency

5. **Order Creation** (Triggers Kafka Pipeline)
   - Endpoint: POST /api/v1/orders
   - Request: Order with items, shipping address
   - Assertion: Returns order_id, < 2000ms latency
   - Triggers: Lambda notification + Flink analytics

6. **Order Status Check**
   - Endpoint: GET /api/v1/orders/{order_id}
   - Assertion: Returns order status, < 500ms latency

#### Custom Metrics
- `errors`: Rate metric for failures
- `api_latency`: Trend metric for API response times
- `order_latency`: Trend metric for order operations
- `successful_orders`: Counter for completed orders
- `active_users`: Gauge for concurrent virtual users

#### Execution
```bash
# Run with default settings
k6 run load-tests/k6/load-test.js

# Run with custom base URL
k6 run --env BASE_URL=http://api-gateway:8080 load-tests/k6/load-test.js

# Run with more VUs and duration
k6 run --vus 100 --duration 5m load-tests/k6/load-test.js

# Run with output to Grafana Cloud (optional)
k6 run -o cloud load-tests/k6/load-test.js
```

### 8.2 Testing Infrastructure

#### Local Testing
- **Docker Compose:** `/docker-compose.yml` provides complete local environment
- **Kafka UI:** Port 8888 for Kafka topic monitoring
- **Prometheus UI:** Port 9090 for metrics
- **Grafana UI:** Port 3000 for dashboards

#### Load Test Validation Points
1. **API Gateway Response Times:** < 500ms p95
2. **Order Processing:** < 2 seconds end-to-end
3. **Kafka Event Delivery:** Verify orders appear in topics
4. **Lambda Execution:** Notifications are sent
5. **Flink Aggregations:** Analytics results appear in 1-min windows
6. **Auto-scaling:** Pods scale up under load
7. **Error Handling:** Graceful degradation under stress

#### Monitoring During Load Tests
```bash
# Watch Kubernetes pod scaling
kubectl get pods -n ecommerce -w

# View Prometheus metrics
http://localhost:9090/targets

# View Grafana dashboards
http://localhost:3000/d/orders-dashboard

# Check Kafka topics
http://localhost:8888
```

---

## 9. DIRECTORY STRUCTURE

```
cloud-bigProject/
├── terraform/                          # Infrastructure as Code
│   ├── aws/                           # AWS Infrastructure
│   │   ├── main.tf                    # Primary AWS resources
│   │   ├── variables.tf               # Input variables
│   │   ├── terraform.tfvars.example   # Example values
│   │   └── modules/
│   │       ├── vpc/                   # VPC, subnets, NAT
│   │       ├── eks/                   # EKS cluster
│   │       ├── rds/                   # PostgreSQL database
│   │       ├── dynamodb/              # Session/cart tables
│   │       ├── s3/                    # Storage buckets
│   │       ├── msk/                   # Kafka cluster
│   │       ├── alb/                   # Load balancer
│   │       └── lambda/                # Notification function
│   └── gcp/                           # GCP Infrastructure
│       ├── main.tf                    # GCP resources
│       ├── variables.tf               # Input variables
│       └── terraform.tfvars.example   # Example values
│
├── services/                          # Microservices
│   ├── api-gateway/                   # Go REST Gateway
│   │   ├── main.go                    # Entry point
│   │   ├── Dockerfile                 # Container image
│   │   └── go.mod/go.sum              # Dependencies
│   │
│   ├── user-service/                  # Go gRPC User Service
│   │   ├── main.go
│   │   ├── proto/user.proto           # gRPC definitions
│   │   └── Dockerfile
│   │
│   ├── product-service/               # Python FastAPI Product Service
│   │   ├── main.py                    # FastAPI application
│   │   ├── requirements.txt           # Python dependencies
│   │   └── Dockerfile
│   │
│   ├── order-service/                 # Go gRPC Order Service
│   │   ├── main.go
│   │   ├── proto/order.proto
│   │   └── Dockerfile
│   │
│   ├── payment-service/               # Go gRPC Payment Service
│   │   ├── main.go
│   │   ├── proto/payment.proto
│   │   └── Dockerfile
│   │
│   └── notification-lambda/           # Python Lambda Notification
│       ├── lambda_function.py
│       ├── requirements.txt
│       └── template.yaml              # SAM template
│
├── analytics/                         # Stream Processing
│   └── flink-job/                     # Apache Flink Analytics
│       ├── main.py                    # Flink job (1-min windows)
│       ├── requirements.txt           # Python dependencies
│       └── submit.sh                  # Job submission script
│
├── k8s/                              # Kubernetes & GitOps
│   ├── base/                         # Base Kustomize resources
│   │   ├── namespace.yaml            # ecommerce namespace
│   │   ├── configmap.yaml            # Environment config
│   │   ├── secrets.yaml              # Database/API credentials
│   │   ├── api-gateway-deployment.yaml
│   │   ├── user-service-deployment.yaml
│   │   ├── product-service-deployment.yaml
│   │   ├── order-service-deployment.yaml (with HPA)
│   │   ├── payment-service-deployment.yaml (with HPA)
│   │   ├── prometheus-deployment.yaml
│   │   ├── grafana-deployment.yaml
│   │   ├── loki-deployment.yaml
│   │   ├── promtail-deployment.yaml
│   │   └── kustomization.yaml
│   │
│   ├── overlays/                    # Environment-specific configs
│   │   └── default/
│   │       ├── kustomization.yaml   # Overlay patches
│   │       ├── configmap.yaml       # Dev-specific config
│   │       └── networkpolicy.yaml
│   │
│   └── argocd/                      # GitOps with ArgoCD
│       ├── app-of-apps.yaml         # Root Application
│       ├── argocd-application.yaml
│       ├── apps/
│       │   ├── ecommerce-services.yaml   # Microservices app
│       │   └── observability.yaml        # Monitoring app
│       └── install/
│           ├── namespace.yaml
│           ├── argocd-cm.yaml       # Configuration
│           ├── argocd-rbac.yaml     # Roles & service accounts
│           └── kustomization.yaml
│
├── observability/                   # Monitoring Configuration
│   ├── prometheus/
│   │   └── prometheus.yml           # Scrape config
│   ├── grafana/
│   │   └── provisioning/
│   │       └── datasources/
│   │           └── datasources.yaml
│   └── promtail/
│       └── config.yaml
│
├── load-tests/                      # Performance Testing
│   └── k6/
│       └── load-test.js            # K6 load test scenarios
│
├── scripts/                         # Deployment Scripts
│   └── build-docker-images.sh      # Build all service images
│
├── docs/                           # Documentation
│   ├── design-document.md          # Architecture overview
│   └── video walkthroughs
│
├── .gitops/                        # GitOps Workflow Documentation
│   ├── README.md
│   └── WORKFLOW.md
│
├── docker-compose.yml              # Local development environment
├── README.md                       # Project overview
├── DEPLOYMENT.md                   # Deployment guide
├── DEVELOPMENT_GUIDE.md            # Development setup
├── ARGOCD_IMPLEMENTATION.md        # ArgoCD setup details
├── CLOUD_STORAGE_VERIFICATION.md   # Cloud storage setup
├── LOKI_IMPLEMENTATION.md          # Log aggregation guide
└── PHASE2_COMPLETION.md            # Project completion summary
```

---

## 10. KEY TECHNOLOGIES & VERSIONS

### Programming Languages
- **Go:** Services: API Gateway, User Service, Order Service, Payment Service
- **Python:** Services: Product Service, Notification Lambda, Flink Analytics, FastAPI
- **Protocol Buffers:** gRPC service definitions

### Cloud Platforms
- **AWS:** EKS, RDS, DynamoDB, S3, MSK, Lambda, ALB, SNS, CloudWatch
- **GCP:** Dataproc, Cloud Storage, Cloud SQL (optional)

### Container & Orchestration
- **Docker:** Container runtime
- **Kubernetes:** 1.28 (EKS)
- **Kustomize:** Configuration management
- **ArgoCD:** GitOps deployment

### Stream Processing
- **Apache Kafka:** Message broker (AWS MSK)
- **Apache Flink:** Real-time stream processing
- **Python:** pyflink library for Flink jobs

### Monitoring & Observability
- **Prometheus:** Metrics collection (15s scrape interval, 30-day retention)
- **Grafana:** Dashboarding and alerting
- **Loki:** Log aggregation
- **Promtail:** Log shipper

### Load Testing
- **K6:** Performance testing framework
- **VUs:** 100 concurrent virtual users
- **Thresholds:** 95th percentile latency < 500ms

### Terraform
- **Version:** >= 1.0
- **Providers:** AWS 5.x, GCP 5.x
- **State:** Local (can be configured for remote S3 backend)

---

## 11. DEPLOYMENT FLOW

### Phase 1: Infrastructure Setup
```bash
# Deploy AWS infrastructure
cd terraform/aws
terraform init
terraform plan
terraform apply -var-file=terraform.tfvars

# Deploy GCP infrastructure
cd ../gcp
terraform init
terraform plan
terraform apply -var-file=terraform.tfvars
```

### Phase 2: Kubernetes Cluster Setup
```bash
# Configure kubectl for EKS cluster
aws eks update-kubeconfig --region us-east-1 --name ecommerce-eks

# Install ArgoCD
kubectl apply -f k8s/argocd/install/kustomization.yaml

# Create app-of-apps
kubectl apply -f k8s/argocd/app-of-apps.yaml
```

### Phase 3: Service Deployment
```bash
# Build and push service Docker images
./scripts/build-docker-images.sh

# ArgoCD automatically syncs services from Git
# Verify deployments
kubectl get pods -n ecommerce
```

### Phase 4: Observability Stack
```bash
# Prometheus and Grafana deployed via ArgoCD
# Access Grafana: http://grafana.ecommerce.local:3000
# Access Prometheus: http://prometheus.ecommerce.local:9090
```

### Phase 5: Analytics Job Submission
```bash
# Submit Flink job to Dataproc
gcloud dataproc jobs submit pyspark \
  --cluster=ecommerce-analytics \
  --region=us-central1 \
  gs://ecommerce-flink-code-{project-id}/main.py
```

### Phase 6: Load Testing
```bash
# Run load test
k6 run --vus 100 --duration 5m load-tests/k6/load-test.js

# Monitor results in Grafana dashboards
```

---

## 12. SCALING & PERFORMANCE CHARACTERISTICS

### Horizontal Scaling
- **Order Service:** 2-10 pods (CPU + Memory triggered)
- **Payment Service:** 2-8 pods (Memory primary, CPU secondary)
- **Product Service:** 2-8 pods (Memory-based)
- **API Gateway:** Manual scaling 1-5 replicas
- **User Service:** Manual scaling 1-3 replicas

### Kafka Performance
- **3 Brokers:** Handle 100s of thousands of messages/second
- **Replication Factor:** 1-3 (configurable per topic)
- **Topic Throughput:** Orders topic tested with K6 load tool

### Database Performance
- **RDS PostgreSQL:** t3.micro starting point, upgradeable to larger instances
- **DynamoDB:** PAY_PER_REQUEST billing (no provisioned capacity management)
- **Connection Pooling:** Configured in service applications

### Flink Analytics
- **Parallelism:** 4 (scalable via Dataproc workers)
- **Window Size:** 1 minute (configurable)
- **Latency:** ~10-second lag for watermarking
- **Throughput:** Depends on Dataproc cluster size

### Load Test Results (Baseline)
From K6 configuration:
- API Latency p95: < 200ms
- Order Processing p95: < 1000ms
- HTTP Request Duration p95: < 500ms
- Error Rate: < 5%

---

## 13. SECURITY & BEST PRACTICES

### Kubernetes Security
- **Network Policies:** Namespace isolation, pod-to-pod communication rules
- **RBAC:** ServiceAccount with minimal required permissions
- **Security Context:**
  - runAsNonRoot: Pods run as non-root users
  - readOnlyRootFilesystem: Prevents filesystem modifications
  - allowPrivilegeEscalation: Disabled
  - Capabilities: ALL dropped

### Secrets Management
- **Database Credentials:** Kubernetes Secrets
- **API Keys:** Stored in Secrets (Stripe API key)
- **Not in Git:** Credentials excluded from version control

### Cloud Security
- **VPC Isolation:** Services in private subnets
- **NAT Gateway:** Outbound internet access through NAT
- **Security Groups:** Restrictive ingress/egress rules
- **S3 Buckets:** No public access, versioning enabled
- **RDS:** Not publicly accessible, encrypted storage

### ArgoCD Security
- **RBAC:** Fine-grained access control (admin, developer, ops roles)
- **Git Authentication:** SSH keys for repository access
- **TLS:** Certificate-based secure communication

---

## 14. CURRENT STATUS & NEXT STEPS

### Implemented
- All 6 core microservices (API Gateway, User, Product, Order, Payment, Notification)
- Complete AWS infrastructure (EKS, RDS, DynamoDB, S3, MSK, Lambda, ALB)
- GCP analytics infrastructure (Dataproc, Cloud Storage)
- ArgoCD GitOps deployment (app-of-apps pattern)
- HPA scaling for Order and Payment services
- Complete observability stack (Prometheus, Grafana, Loki, Promtail)
- Flink analytics job for real-time aggregations
- K6 load testing framework
- Docker Compose local development environment

### Potential Enhancements
- Service mesh (Istio/Linkerd) for advanced traffic management
- API gateway rate limiting and authentication
- Circuit breaker patterns (Hystrix/Resilience4j)
- Distributed tracing (Jaeger/Zipkin)
- Multi-region disaster recovery
- Cost optimization (spot instances, reserved capacity)
- CI/CD pipeline integration (GitHub Actions)
- Database replication across regions
- Advanced monitoring (custom dashboards, alerting rules)

---

## Summary

This is a **comprehensive, production-ready microservices platform** that demonstrates:

1. **Multi-Cloud Architecture:** AWS + GCP integration
2. **Infrastructure as Code:** 100% Terraform-based provisioning
3. **GitOps Workflow:** ArgoCD for declarative deployments
4. **Microservices:** 6 services with REST + gRPC communication
5. **Async Processing:** Kafka-driven event pipeline with Flink analytics
6. **Auto-Scaling:** HPA configured for demand-driven scaling
7. **Observability:** Prometheus + Grafana + Loki for complete visibility
8. **Performance Testing:** K6 load testing framework
9. **Security:** RBAC, network policies, secrets management
10. **Best Practices:** Container security, health checks, resource limits

The platform is ready for demonstration, learning, and production deployment.
