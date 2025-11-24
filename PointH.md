# PointH: Load Testing & HPA Scaling Validation

## Overview
K6 load testing validated **Horizontal Pod Autoscaler (HPA)** automatically scales Order Service and Payment Service based on CPU and memory utilization under sustained load.

---

## 1. Load Test Configuration

**Test File**: `load-tests/k6/order-service-load-test.js`

**Duration**: 4.5 minutes
- Ramp-up: 30s (0→15 VUs)
- Sustained: 3min (25 VUs)
- Ramp-down: 1min (25→0 VUs)

**Endpoint**: POST `/api/v1/orders`

**HPA Thresholds (lowered for testing)**:
- Order Service: CPU 15%, Memory 30%
- Payment Service: CPU 15%, Memory 30%

---

## 2. Test Results

**Load Test Metrics**:
- Total Requests: 661
- Error Rate: 0% (all successful)
- Response Time: 264ms average, p95=584ms
- Duration: 4m7.9s
- Peak VUs: 25

**Status Code Distribution**:
- 201 Created: 661 (100%)
- 4xx/5xx Errors: 0

---

## 3. HPA Scaling Results

**Order Service**:
- Initial: 2 pods
- Scaled to: 4 pods during load
- CPU per pod: 18% (2 pods) → 6-8% (4 pods normalized)
- Pod creation time: ~25 seconds

**Payment Service**:
- Remained at 2 pods (load below thresholds)
- Metrics actively monitored

**Scale-down**:
- Conservative 300s stabilization window
- Gracefully scaled down to 2 pods after test

---

## 4. Key Findings

**HPA Triggered**: Thresholds exceeded, scaling activated automatically
**Pods Scaled**: 2 → 4 replicas confirmed during load
**Load Balanced**: Requests distributed across all pods
**Zero Errors**: 0% error rate throughout test
**Graceful Scaling**: No disruption during pod creation/deletion
**Performance Stable**: Response times remained consistent

---

## 5. How to Run

```bash
# Terminal 1: Run load test
cd load-tests/k6
k6 run order-service-load-test.js

# Terminal 2 (optional): Watch HPA
kubectl get hpa -n ecommerce -w

# Terminal 3 (optional): Watch pods
kubectl get pods -n ecommerce -l app=order-service -w
```

---

## 6. Requirements Compliance

Load testing tool (K6)
Sustained traffic (25 VUs, 3+ minutes)
HPA scaling confirmed (2→4 pods)
Resilience demonstrated (0% errors)
Automatic scaling (no manual intervention)
Zero downtime during scaling

---