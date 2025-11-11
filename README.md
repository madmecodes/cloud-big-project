# Cloud E-Commerce Microservices Platform

A production-grade cloud-native e-commerce platform demonstrating advanced cloud architecture patterns using AWS and GCP.

## Architecture Overview

### Microservices (6 total)
1. **API Gateway** (Go) - Public REST API entry point
2. **User Service** (Go) - Authentication and user management
3. **Product Service** (Python) - Product catalog and search
4. **Order Service** (Go) - Order processing
5. **Payment Service** (Go) - Payment transactions
6. **Notification Service** (Python/Lambda) - Serverless notifications
7. **Analytics Service** (Python/Flink on GCP) - Real-time order analytics

### Cloud Providers
- **AWS (Primary):** EKS, RDS, DynamoDB, S3, MSK, Lambda, ALB
- **GCP (Analytics):** Dataproc (Apache Flink), Cloud Storage

### Communication Patterns
- **REST:** API Gateway ↔ External clients, Gateway → Services
- **gRPC:** High-performance internal service communication (User ↔ Order, Order ↔ Payment, Product ↔ Order)
- **Pub/Sub:** Kafka/MSK for event streaming (Orders → Flink Analytics & Lambda Notifications)

## Project Structure

```
cloud-bigProject/
├── terraform/                 # Infrastructure as Code
│   ├── aws/                   # AWS infrastructure
│   │   └── modules/           # VPC, EKS, RDS, DynamoDB, S3, MSK, Lambda, ALB
│   └── gcp/                   # GCP infrastructure
│       └── modules/           # Dataproc, Cloud Storage
├── services/                  # Microservices
│   ├── api-gateway/           # Go REST API Gateway
│   ├── user-service/          # Go gRPC User Service
│   ├── product-service/       # Python gRPC Product Service
│   ├── order-service/         # Go gRPC Order Service
│   ├── payment-service/       # Go gRPC Payment Service
│   └── notification-lambda/   # Python Lambda Notification
├── analytics/
│   └── flink-job/             # Python Flink Analytics Job
├── k8s/                       # Kubernetes & GitOps
│   ├── base/                  # Base manifests
│   ├── overlays/              # Environment-specific (dev/prod)
│   └── argocd/                # ArgoCD configuration
├── observability/             # Monitoring & Logging
│   ├── prometheus/            # Metrics collection
│   ├── grafana/               # Dashboards
│   └── efk/                   # Elasticsearch, Fluentd, Kibana
├── load-tests/
│   └── k6/                    # Load testing scripts
├── docs/                      # Documentation
│   ├── design-document.md
│   ├── demo_video.txt
│   └── <idno>_video.txt
└── README.md
```

## Key Features

- **100% Infrastructure as Code:** All resources provisioned with Terraform
- **GitOps Deployment:** ArgoCD manages all K8s deployments (no direct kubectl)
- **Multi-Cloud:** AWS + GCP for disaster recovery and provider diversity
- **Serverless Functions:** AWS Lambda for asynchronous notifications
- **Stream Processing:** Apache Flink for real-time analytics (1-min windows)
- **Managed Services:** EKS, MSK, RDS, DynamoDB, Cloud SQL
- **Horizontal Scaling:** HPA configured for Order & Payment services
- **Observability:** Prometheus + Grafana for metrics, EFK for centralized logging
- **Load Testing:** k6 scripts to validate resilience and auto-scaling

## Getting Started

### Prerequisites
- AWS Account with credentials configured
- GCP Project with credentials configured
- Docker installed
- Terraform >= 1.0
- kubectl installed
- git configured

### Phase 1: Infrastructure Setup
```bash
cd terraform/aws
terraform init
terraform plan
terraform apply

cd ../gcp
terraform init
terraform plan
terraform apply
```

### Phase 2: Deploy Microservices
```bash
# Build Docker images for all services
./build-all-images.sh

# ArgoCD will automatically sync from Git
# Verify deployments
kubectl get pods -n ecommerce
```

### Phase 3: Deploy Analytics
```bash
# Submit Flink job to Dataproc
gcloud dataproc jobs submit spark-job \
  --cluster=analytics-cluster \
  --class=org.apache.flink.python.runner \
  analytics/flink-job/main.py
```

### Phase 4: Observability
```bash
# Prometheus & Grafana automatically deployed via ArgoCD
# Access Grafana at http://grafana.ecommerce.local
# Access Prometheus at http://prometheus.ecommerce.local
```

### Phase 5: Load Testing
```bash
cd load-tests/k6
k6 run --vus 100 --duration 5m load-test.js
```

## API Endpoints

### REST Endpoints
- `POST /api/v1/auth/login` - User login
- `GET /api/v1/products` - List products
- `POST /api/v1/orders` - Create order
- `GET /api/v1/orders/{id}` - Get order details

### gRPC Services
- `UserService.Authenticate()` - Verify user credentials
- `ProductService.GetProduct()` - Fetch product details
- `OrderService.CreateOrder()` - Create new order
- `PaymentService.ProcessPayment()` - Process payment

## Event Flows

### Order Placed Event
1. Order Service receives REST request
2. Creates order and publishes to Kafka `orders` topic
3. Lambda consumes → sends email notification
4. Flink consumes → aggregates for analytics
5. Analytics results published to `analytics-results` topic

## Scaling & Performance

- **API Gateway:** 1-5 replicas (manual)
- **Product Service:** 2-8 pods (HPA, memory-based)
- **Order Service:** 2-10 pods (HPA, CPU-based)
- **User Service:** 1-3 replicas (manual)
- **Payment Service:** 2-8 pods (HPA, CPU-based)

## Monitoring

- **Prometheus:** Scrapes metrics every 15s
- **Grafana Dashboards:**
  - Cluster health (CPU, memory, disk)
  - Service metrics (RPS, latency, errors)
  - Kafka broker metrics
  - Flink job metrics
- **EFK Stack:** Centralized log aggregation
  - Elasticsearch for storage
  - Fluentd for log collection
  - Kibana for visualization

## Documentation

See `docs/` directory for:
- Design document with architecture diagrams
- Implementation guides
- Video walkthroughs

## Testing

### Load Testing
```bash
k6 run load-tests/k6/load-test.js
```

### Unit Tests
```bash
# Each service has its own test suite
cd services/order-service
go test ./...
```

## Deployment Strategy

All deployments use GitOps:
1. Push changes to Git
2. ArgoCD detects changes
3. Automatic sync to EKS cluster
4. No manual `kubectl apply` commands

## Contributing

- Each team member records video explaining their code
- Commit messages follow conventional commits
- All changes go through Git before cluster deployment

## License

MIT
