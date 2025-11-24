# Observability Stack

Complete observability solution with metrics (Prometheus), logs (Loki), and visualization (Grafana) for the E-Commerce microservices platform.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Microservices                         │
│  (API Gateway, User, Product, Order, Payment Services) │
└──────┬──────────────────────────────────────────────────┘
       │
       ├─────────────────────────┬─────────────────────────┐
       │                         │                         │
       ▼                         ▼                         ▼
   Prometheus              Loki (Logs)            Grafana (UI)
  (Metrics)         (Log Aggregation)         (Dashboards)
       │                    │
       ├──────────────┐     │
       │         ┌────┴─────┴───────┐
       │         │                  │
       └─────────┼──────────────────┘
                 │
         ┌───────┴────────┐
         │                │
    Dashboard 1      Dashboard 2
    (Prometheus      (Loki Logs)
     Metrics)
```

## Components

### 1. **Prometheus** (Metrics Collection)
- **Location**: `prometheus/`
- **Deployment**: `prometheus/deployment.yaml`
- **Config**: `prometheus/configmap.yaml`
- **Service**: ClusterIP on port 9090
- **Scrapes**: Kubernetes metrics, applications, node metrics
- **Data**: Time-series metrics for performance monitoring

### 2. **Loki** (Log Aggregation)
- **Location**: `loki/`
- **Deployment**: `loki/deployment.yaml` (includes ConfigMap + Service)
- **Service**: ClusterIP on port 3100
- **Storage**: In-memory with boltdb-shipper backend
- **Retention**: 168h (7 days)
- **Log Sources**:
  - API Gateway
  - User Service
  - Product Service
  - Order Service
  - Payment Service

### 3. **Promtail** (Log Collector)
- **Location**: `loki/promtail.yaml`
- **Deployment**: DaemonSet (runs on all nodes)
- **Function**: Collects pod logs and sends to Loki
- **Configuration**:
  - Scrapes ecommerce namespace pods
  - Scrapes observability namespace pods
  - Extracts app labels via regex matching

### 4. **Grafana** (Visualization)
- **Location**: `grafana/`
- **Deployment**: `grafana/deployment.yaml`
- **Service**: LoadBalancer on port 80
- **Credentials**: `admin/admin123`
- **Data Sources**:
  - Prometheus (http://prometheus:9090)
  - Loki (http://loki:3100)

## Dashboards

### Dashboard 1: E-Commerce Kubernetes Monitoring
**UID**: `ecommerce-k8s-v2` | **Tags**: kubernetes, prometheus

11 Prometheus panels monitoring:
1. **Request Rate Per Second** - HTTP request throughput
2. **Running Pods by Namespace** - Cluster resource overview
3. **HTTP Error Rate (5xx)** - Error monitoring
4. **Request Latency p95** - Performance tracking
5. **Kubernetes Nodes Ready** - Node health status
6. **Total Pods Running** - Cluster pod count
7. **Orders Created (Total)** - Business metric
8. **Active Prometheus Targets** - Scraping status
9. **Pod CPU Resource Requests (Top 15)** - Resource usage
10. **Pod Memory Resource Requests (Top 15)** - Memory allocation
11. **Pod Restarts (Top 15)** - Stability tracking

### Dashboard 2: Microservices Logs
**UID**: `microservices-logs-v1` | **Tags**: loki, logs, microservices

5 Loki log panels (one per microservice):
1. **API Gateway Logs** - Entry point logs
2. **User Service Logs** - User operations
3. **Product Service Logs** - Product catalog
4. **Order Service Logs** - Order processing
5. **Payment Service Logs** - Payment transactions

## Deployment

### Files Structure
```
observability/
├── namespace.yaml                    # observability namespace
├── prometheus/
│   ├── configmap.yaml               # Prometheus scrape config
│   └── deployment.yaml              # Prometheus deployment
├── loki/
│   ├── deployment.yaml              # Loki deployment + service + config
│   └── promtail.yaml                # Promtail DaemonSet + config + RBAC
├── grafana/
│   └── deployment.yaml              # Grafana deployment + service
├── dashboards/
│   └── configmap.yaml               # Dashboard definitions (both dashboards)
└── README.md                        # This file
```

### Deploy Stack
```bash
# Deploy all components
kubectl apply -f observability/namespace.yaml
kubectl apply -f observability/prometheus/
kubectl apply -f observability/loki/
kubectl apply -f observability/grafana/
kubectl apply -f observability/dashboards/

# Verify deployment
kubectl get pods -n observability
kubectl get svc -n observability
```

### Access Grafana
```bash
# Get LoadBalancer endpoint
kubectl get svc grafana -n observability

# Login
URL: http://<EXTERNAL-IP>
Username: admin
Password: admin123
```

## Monitoring Coverage

### Metrics Monitored (Prometheus)
- HTTP request rate, errors, latency
- Pod CPU and memory usage
- Container restarts
- Node status and availability
- Kubernetes cluster health

### Logs Collected (Loki)
- All pod logs from ecommerce services
- All pod logs from observability stack
- Structured with labels: `namespace`, `pod`, `container`, `app`

## Configuration Highlights

### Promtail Label Extraction
- Automatically extracts service name (`app` label) from pod name
- Supported services: api-gateway, user-service, product-service, order-service, payment-service
- Pipeline processing with CRI log parsing

### Loki Storage
- **Type**: Filesystem (local storage with boltdb indexing)
- **Directory**: `/tmp/loki-chunks` (ephemeral - for demo)
- **For Production**: Should use external storage (S3, GCS, etc.)

### Grafana Datasources
- **Prometheus**: Default datasource for metrics
- **Loki**: For log queries and visualization

## Troubleshooting

### Loki not showing logs
1. Verify Promtail pods are running: `kubectl get pods -n observability -l app=promtail`
2. Check Promtail logs: `kubectl logs -n observability -l app=promtail`
3. Verify Loki is receiving data: `kubectl exec -n observability deployment/loki -- wget -q -O - 'http://localhost:3100/loki/api/v1/label/app/values'`

### Prometheus not scraping
1. Check Prometheus targets: Visit Grafana -> Datasources -> Prometheus -> Test
2. Verify scrape configs in `prometheus/configmap.yaml`
3. Check Prometheus logs: `kubectl logs -n observability deployment/prometheus`

### Grafana datasources missing
1. Prometheus should be auto-configured via deployment
2. Loki datasource is added programmatically when Grafana starts
3. If missing, add manually: Grafana -> Configuration -> Data Sources

## Resources

- **Prometheus CPU**: 100m request, 500m limit
- **Prometheus Memory**: 128Mi request, 512Mi limit
- **Loki CPU**: 250m request, 500m limit
- **Loki Memory**: 512Mi request, 1Gi limit
- **Grafana CPU**: 100m request, 500m limit
- **Grafana Memory**: 128Mi request, 512Mi limit
- **Promtail CPU**: 100m request, 200m limit (per pod)
- **Promtail Memory**: 128Mi request, 256Mi limit (per pod)

## Next Steps

For production deployment:
1. Use persistent storage for Loki (S3, GCS, Azure Blob, etc.)
2. Set up log retention policies
3. Configure alerting rules in Prometheus
4. Add more dashboard panels for business metrics
5. Enable HTTPS for Grafana
6. Implement backup strategy for dashboards
