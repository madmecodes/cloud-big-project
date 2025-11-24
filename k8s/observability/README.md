# Observability Stack Setup

Complete guide to deploy Prometheus + Grafana monitoring for the e-commerce Kubernetes cluster.

## Architecture

- **Prometheus**: Metrics collection and storage (port 9090)
- **Grafana**: Visualization and dashboards (LoadBalancer on port 80)
- **kube-state-metrics**: Kubernetes cluster metrics
- **Auto-scraping**: Prometheus discovers pods via annotations

## Quick Start

### 1. Deploy Prometheus (if not already deployed)

```bash
kubectl apply -f ../base/prometheus-deployment.yaml
```

### 2. Deploy kube-state-metrics with RBAC

```bash
kubectl apply -f kube-state-metrics-rbac.yaml
```

### 3. Install Grafana using Helm

```bash
# Add Grafana Helm repository
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install Grafana with our configuration
helm install grafana grafana/grafana \
  -n observability \
  -f grafana-values.yaml
```

### 4. Import Dashboard

Wait for Grafana pod to be ready, then import the dashboard:

```bash
# Get Grafana pod name
GRAFANA_POD=$(kubectl get pod -n observability -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].metadata.name}')

# Copy dashboard to pod
kubectl cp grafana-dashboard.json observability/$GRAFANA_POD:/tmp/dashboard.json

# Import dashboard
kubectl exec -n observability $GRAFANA_POD -- \
  curl -X POST http://localhost:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -u 'admin:admin123' \
  -d @/tmp/dashboard.json
```

### 5. Access Grafana

Get the LoadBalancer URL:

```bash
kubectl get svc grafana -n observability
```

**Credentials:**
- Username: `admin`
- Password: `admin123`

**Direct Dashboard URL:**
```
http://<LOADBALANCER-URL>/d/ecommerce-k8s-v2/e-commerce-kubernetes-monitoring
```

## Dashboard Features

The dashboard includes 11 panels:

### Performance Metrics
- **Request Rate Per Second**: HTTP traffic by service instance
- **Request Latency p95**: 95th percentile response times
- **HTTP Error Rate (5xx)**: Server error monitoring

### Cluster Health
- **Running Pods by Namespace**: Pod distribution across namespaces
- **Kubernetes Nodes Ready**: Total ready nodes
- **Total Pods Running**: Overall pod count
- **Active Prometheus Targets**: Monitoring health

### Resource Analysis
- **Pod CPU Resource Requests (Top 15)**: Highest CPU requesters
- **Pod Memory Resource Requests (Top 15)**: Highest memory requesters
- **Pod Restarts (Top 15)**: Identifies problematic pods

### Business Metrics
- **Orders Created (Total)**: E-commerce order count

## Enable Metrics in Your Services

Add these annotations to your deployment pod template:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"  # Your service port
    prometheus.io/path: "/metrics"
```

## Troubleshooting

### Dashboard shows "No Data"

1. Check Prometheus targets:
```bash
kubectl port-forward -n observability svc/prometheus 9090:9090
# Visit http://localhost:9090/targets
```

2. Verify kube-state-metrics is running:
```bash
kubectl get pods -n observability -l app=kube-state-metrics
kubectl logs -n observability -l app=kube-state-metrics
```

3. Check service annotations have correct ports

### Grafana "Access Denied" errors

The Helm installation automatically creates proper RBAC. If using manual deployment, ensure service account has dashboard permissions.

## Cleanup

```bash
# Remove Grafana
helm uninstall grafana -n observability

# Remove kube-state-metrics
kubectl delete -f kube-state-metrics-rbac.yaml

# Remove Prometheus (optional)
kubectl delete -f ../base/prometheus-deployment.yaml
```

## Files

- `grafana-dashboard.json`: Working dashboard configuration
- `grafana-values.yaml`: Helm chart values with Prometheus datasource
- `kube-state-metrics-rbac.yaml`: RBAC permissions for cluster metrics
- `../base/prometheus-deployment.yaml`: Prometheus deployment manifest

## Notes

- Dashboard auto-refreshes every 30 seconds
- LoadBalancer creates AWS ELB (costs apply)
- No persistence enabled (data lost on pod restart)
- For production, enable Grafana persistence and use proper secrets management
