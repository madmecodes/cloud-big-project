# K6 Load Testing for HPA Scaling Validation

## Overview
K6 load testing script to generate sustained traffic and validate **Horizontal Pod Autoscaler (HPA)** scaling behavior on Order Service.

---

## Prerequisites

### Install k6
```bash
# macOS (Homebrew)
brew install k6

# Linux (Ubuntu/Debian)
sudo apt-get install k6

# Verify installation
k6 version
```

---

## Test Configuration

### File: `order-service-load-test.js`

**Test Stages**:
1. **Ramp-up (30s)**: 0 → 15 Virtual Users
2. **Sustained Load (3m)**: 25 Virtual Users (sustained)
3. **Ramp-down (1m)**: 25 → 0 Virtual Users

**Total Duration**: 4 minutes 30 seconds

**Endpoint Tested**: `POST /api/v1/orders`

**Metrics Tracked**:
- HTTP request duration (p95 < 1000ms)
- Error rate (< 10%)
- Successful order creations

---

## Running the Load Test

### 1. Basic Run (using API Gateway)
```bash
cd load-tests/k6
k6 run order-service-load-test.js
```

### 2. Custom Base URL
```bash
k6 run -e BASE_URL=http://your-api-endpoint order-service-load-test.js
```

### 3. Run with Output to File
```bash
k6 run order-service-load-test.js --out json=results.json
```

### 4. Run with Custom Virtual Users
```bash
k6 run --vus 50 --duration 5m order-service-load-test.js
```

---

## Monitoring HPA During Test

### Terminal 1: Run the Load Test
```bash
k6 run order-service-load-test.js
```

### Terminal 2: Watch HPA Status (new terminal)
```bash
# Watch HPA in real-time
kubectl get hpa -n ecommerce -w

# Expected output during load:
# NAME                  TARGETS           MINPODS   MAXPODS   REPLICAS
# order-service-hpa     0%/70%, 10%/80%   2         10        2
# (After ~1 min of load)
# order-service-hpa     15%/70%, 25%/80%  2         10        3
# order-service-hpa     35%/70%, 45%/80%  2         10        5
# order-service-hpa     55%/70%, 70%/80%  2         10        8
```

### Terminal 3: Monitor Pod Scaling (new terminal)
```bash
# Watch pods being created/deleted
kubectl get pods -n ecommerce -w -l app=order-service

# Expected output:
# NAME                            READY   STATUS
# order-service-xxx               1/1     Running
# order-service-yyy               1/1     Running
# order-service-zzz               0/1     Pending   (new pod)
# order-service-aaa               0/1     ContainerCreating
# order-service-aaa               1/1     Running
```

### Terminal 4: Monitor Metrics (new terminal)
```bash
# Watch CPU/Memory usage
kubectl top pods -n ecommerce -l app=order-service --containers

# Expected output:
# NAME                            CPU(cores)   MEMORY(bytes)
# order-service-xxx               50m          80Mi
# order-service-yyy               45m          78Mi
# order-service-zzz               52m          82Mi
# order-service-aaa               48m          79Mi
```

---

## Test Execution Timeline

### What Happens When

```
T=0s:    Load test starts (0 VUs)
         ├─ Pods running: 2 (minimum)
         └─ CPU usage: ~5% per pod

T=30s:   Ramp-up complete (15 VUs, ~15 RPS)
         ├─ CPU usage: ~15-20% per pod
         └─ Status: SUSTAINED below thresholds

T=1m30s: Sustained load begins (25 VUs, ~25 RPS)
         ├─ CPU usage: ~30-40% per pod
         └─ Status: Still below 70% threshold

T=2m:    Load effect accumulates
         ├─ CPU usage: ~45-55% per pod
         └─ Status: Approaching threshold

T=2m30s: CPU reaches ~65-70% threshold
         ├─ HPA detects scaling trigger
         ├─ New pods scheduled
         └─ Load distributed across 3-4 pods

T=3m:    Pods scaled up (3-5 pods running)
         ├─ CPU normalized: ~20-30% per pod
         ├─ Load balanced
         └─ Service handles sustained load

T=4m:    Sustained load ends, ramp-down begins (25 → 0 VUs)
         ├─ CPU drops: ~5-10% per pod
         ├─ HPA enters stabilization (300s window)
         └─ Extra pods remain for 5 minutes

T=4m30s: Test completes
         └─ Results printed

T=5m30s: Scale-down begins
         ├─ HPA removes excess pods
         └─ Pods: 5 → 3 → 2 (minimum)
```

---

## Expected Results

### Successful HPA Scaling Indicators

✅ **Pod Count Increases**:
```
Before load: 2 pods
During load: 3-5 pods
After load:  2 pods (after 5 minute stabilization)
```

✅ **CPU Utilization Increases**:
```
Before: 0-5% per pod
During: 30-65% per pod
After: 5-10% per pod
```

✅ **Load Distributed**:
```
Requests per pod decreases as pod count increases
Service latency remains stable (<1000ms p95)
```

✅ **No Errors**:
```
Error rate < 10%
All requests return 201 Created
```

---

## K6 Output Explanation

### Key Metrics
- **http_req_duration**: Time from request sent to response received
- **http_req_failed**: Failed requests (non-2xx/3xx status)
- **data_received/sent**: Total data transferred
- **http_reqs**: Total requests sent
- **iteration_duration**: Time per virtual user iteration

### Sample Output
```
✓ status is 201
✓ response time < 1000ms
✓ contains order_id

    checks........................: 100.00% ✓ 1500 ✗ 0
    data_received..................: 180 kB  667 B/s
    data_sent.......................: 450 kB  1.7 kB/s
    http_req_duration...............: avg=250ms    p(95)=450ms  p(99)=800ms
    http_req_failed.................: 0.00%
    http_reqs.......................: 1500   5.5/s
    iteration_duration..............: avg=2.3s     min=2.0s   max=4.2s
    vus............................: 0      min=0 max=25
    vus_max.........................: 25
```

---

## Troubleshooting

### Issue: "Connection Refused"
```
Error: connection refused
Solution: Check API Gateway endpoint is accessible
  kubectl get svc api-gateway -n ecommerce
  Ensure LoadBalancer has EXTERNAL-IP assigned
```

### Issue: "All Requests Failed"
```
Error: status 0
Solution:
  1. Verify network connectivity to endpoint
  2. Check Order Service is running: kubectl get pods -n ecommerce
  3. Check Order Service logs: kubectl logs -n ecommerce -l app=order-service
```

### Issue: "HPA Not Scaling"
```
Problem: Replicas stay at 2 even under load
Solution:
  1. Check Metrics Server: kubectl get deployment metrics-server -n kube-system
  2. Verify HPA sees metrics: kubectl describe hpa order-service-hpa -n ecommerce
  3. Check if CPU actually exceeds 70%: kubectl top pods -n ecommerce -l app=order-service
```

---

## Advanced Options

### Custom Thresholds
Edit `order-service-load-test.js`:
```javascript
// Change stages to increase load
stages: [
  { duration: '30s', target: 50 },   // More aggressive ramp-up
  { duration: '3m', target: 100 },   // Higher sustained load
  { duration: '1m', target: 0 }
]
```

### Increase Request Duration
```javascript
// Add artificial delay to increase CPU usage
sleep(5);  // 5-second sleep between requests
```

### Add More Virtual Users
```bash
k6 run --vus 100 --duration 5m order-service-load-test.js
```

---

## Files

| File | Purpose |
|------|---------|
| `order-service-load-test.js` | Simple K6 load test (4.5 min, 0-25 VUs) |
| `README.md` | This file - how to use K6 |

---

**Status**: Ready for HPA Validation Testing
**Test Type**: HTTP Load Testing
**Duration**: 4m 30s
**Scope**: Order Service Scaling
