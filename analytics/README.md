# Real-Time Order Analytics Pipeline

Complete real-time stream processing architecture for e-commerce order analytics using **Confluent Cloud Kafka** and **GCP Dataproc PySpark**.

## What It Is

A real-time data pipeline that captures order events from your e-commerce service, aggregates them into meaningful metrics, and streams the results back—all within seconds. Built on cloud-native technologies for scalability and reliability.

```
Order Service (EKS) → Confluent Cloud Kafka → GCP Dataproc (PySpark) → Analytics Results
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Order Service (EKS)                        │
│              Creates orders, publishes events to Kafka           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ SASL/SSL (Confluent Cloud)
                           │
        ┌──────────────────▼──────────────────┐
        │     Confluent Cloud Kafka Cluster    │
        │  (pkc-41p56.asia-south1.gcp.cloud)  │
        ├──────────────────────────────────────┤
        │  Topic: orders (order events)        │
        │  Topic: analytics-results (agg data) │
        └──────────────────┬──────────────────┘
                           │
                           │ SASL/SSL (Confluent Cloud)
                           │
        ┌──────────────────▼──────────────────┐
        │    GCP Dataproc (PySpark Cluster)   │
        │  Real-time Stream Processing Job     │
        ├──────────────────────────────────────┤
        │  1-Min Tumbling Window Aggregation   │
        │  Calculate Metrics & Insights        │
        └──────────────────────────────────────┘
```

## Components

### 1. Order Service (AWS EKS)
**What it does**: Creates orders and publishes each order event to Kafka in real-time.

**Event published** (JSON format):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-123",
  "total_amount": 5500.00,
  "status": "pending",
  "items_count": 5,
  "event_type": "order.created",
  "created_at": "2025-11-24T09:08:16.293872",
  "items": [
    {"product_id": "prod-001", "quantity": 2, "price": 1500.00},
    {"product_id": "prod-002", "quantity": 3, "price": 1333.33}
  ]
}
```

**Kafka Config**:
- Bootstrap Server: `pkc-41p56.asia-south1.gcp.confluent.cloud:9092`
- Topic: `orders`
- Authentication: SASL/SSL (API Key + Secret)
- Deployment: `k8s/base/order-service-deployment.yaml`
- Code: `services/order-service/main.py`

### 2. Confluent Cloud Kafka
**What it is**: Fully managed, cloud-hosted message broker. Handles all networking, scaling, and security automatically.

**Why we use it**:
- Public endpoint (no VPC complexity)
- Built-in SASL/SSL authentication
- Automatic replication and backups
- Scales with demand

**Topics**:
- `orders` - Raw order events (7-day retention)
- `analytics-results` - Aggregated metrics (7-day retention)

**Credentials**:
- API Key: `I3XN2DJTHYXGK2EN`
- API Secret: Stored in K8s Secret `kafka-confluent-secret`

### 3. GCP Dataproc PySpark Job
**What it does**: Continuously consumes order events, aggregates them into 1-minute windows, calculates metrics, and publishes results.

**Processing Logic**:
1. Reads raw events from `orders` topic
2. Parses JSON into structured DataFrame
3. Groups events by 1-minute time windows
4. Calculates 4 key metrics per window:
   - `order_count` - Total orders created
   - `unique_users` - How many different users (approx count)
   - `total_revenue` - Sum of all order amounts
   - `avg_order_value` - Revenue divided by order count
5. Publishes aggregated result to `analytics-results` topic

**Technology**:
- PySpark 3.3.0 (Structured Streaming)
- Spark-Kafka 0-10 connector
- SASL/SSL for Confluent Cloud
- 30-second watermark for late-arriving events

**Deployment**: `analytics/flink-job/order_analytics.py`
- Cluster: `ecommerce-analytics` (GCP Dataproc)
- Region: `asia-south1`
- Current Job ID: `be58b21491114612ac9d3bdb399bf8d4` (RUNNING)

## Data Flow Example

### Step 1: Create Order
```bash
curl -X POST http://api-gateway/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "d61d7bd4-8fc0-48f9-8f9e-39e6759ff0a4",
    "items": [
      {
        "product_id": "0be37192-b396-4d46-94df-0c922dfe3cf6",
        "quantity": 2,
        "price": 1000.00
      }
    ],
    "shipping_address": {
      "street": "123 Main Street",
      "city": "Mumbai",
      "state": "Maharashtra",
      "zip": "400001",
      "country": "India"
    }
  }'
```

**Response**:
```json
{
  "id": "b42f3a92-1295-472a-a079-995ad59a6877",
  "user_id": "d61d7bd4-8fc0-48f9-8f9e-39e6759ff0a4",
  "items": [...],
  "total_amount": 2000.0,
  "status": "pending",
  "created_at": "2025-11-24T09:04:57.367274"
}
```

### Step 2: Order Published to Kafka
Order service automatically publishes event to `orders` topic with full order details + timestamp.

### Step 3: Dataproc Processes
PySpark job reads event and waits for 1-minute window to close. Once window closes, it aggregates all orders from that minute.

### Step 4: Analytics Result Published
Result appears in `analytics-results` topic:
```json
{
  "window_start": "2025-11-24 09:08:00",
  "window_end": "2025-11-24 09:09:00",
  "order_count": 3,
  "unique_users": 1,
  "total_revenue": 10000.0,
  "avg_order_value": 3333.33,
  "processed_at": "2025-11-24T09:08:30.218",
  "metric_type": "order_analytics",
  "window_type": "1_minute_window"
}
```

### Timeline
```
09:08:16 - Order 1 created
09:08:17 - Order 2 created
09:08:18 - Order 3 created
        ↓
09:09:00 - 1-minute window closes
09:09:30 - Dataproc publishes aggregated result
```

## What Insights It Provides

### Real-Time Business Metrics
By minute, you know:
- **How many orders** were created (transaction volume)
- **Revenue generated** (business performance)
- **Average order value** (customer spend patterns)
- **User engagement** (how many unique customers)

### Use Cases
1. **Live Dashboard**: Display current minute metrics on executive dashboard
2. **Alerting**: Alert if revenue drops below threshold or order volume spikes
3. **Anomaly Detection**: Detect unusual patterns (e.g., surge in small orders = bot activity)
4. **Capacity Planning**: Track peak demand hours to optimize resource allocation
5. **Marketing Attribution**: Correlate campaigns with order volume spikes

### Example Insights
If you see:
- `order_count: 150, avg_order_value: $250` → Healthy sales volume
- `order_count: 5, avg_order_value: $50` → Possible bot traffic or discount abuse
- `unique_users: 150, order_count: 150` → Each user orders once (good conversion)
- `unique_users: 50, order_count: 150` → Few users ordering multiple times (high LTV customers)

## Business Benefits

### 1. Real-Time Decision Making
- Detect issues within minutes, not hours
- React to market trends instantly
- Reduce data latency from hours to seconds

### 2. Operational Visibility
- Know current business performance without waiting for batch jobs
- Monitor system health through order flow metrics
- Identify system bottlenecks via processing delays

### 3. Scalability
- Handles thousands of orders per second automatically
- No manual intervention needed
- Cloud-native infrastructure scales with growth

### 4. Cost Efficiency
- Managed services (no server management)
- Pay only for what you use
- No storage of raw events (only aggregated metrics)

### 5. Integration Ready
- Results available in Kafka for consumption by:
  - Real-time dashboards
  - ML models for predictions
  - Business intelligence tools
  - Mobile apps for live metrics
  - Email/SMS alerting systems

## Testing the Pipeline

### Create a Test User
```bash
curl -X POST http://api-gateway/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@example.com","password":"pass123"}'
# Save the returned user_id
```

### Create Test Products
```bash
curl -X POST http://api-gateway/api/v1/products \
  -H "Content-Type: application/json" \
  -d '{"name":"Product 1","price":1000,"stock":100,"sku":"PROD-001"}'
# Save the returned product_id
```

### Create Orders (triggers pipeline)
```bash
curl -X POST http://api-gateway/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<USER_ID>",
    "items": [{"product_id": "<PRODUCT_ID>", "quantity": 1, "price": 1000}],
    "shipping_address": {
      "street": "123 Main St",
      "city": "Mumbai",
      "state": "MH",
      "zip": "400001",
      "country": "India"
    }
  }'
```

Create 3-5 orders within same minute to see aggregation.

### Watch Results (70+ seconds after last order)
```bash
# Check Dataproc job logs
gcloud dataproc jobs describe be58b21491114612ac9d3bdb399bf8d4 \
  --region=asia-south1 --format="value(status.state)"

# View driver output
gsutil cat gs://dataproc-staging-asia-south1-79643021118-u2v9kob0/google-cloud-dataproc-metainfo/a2d5e136-959c-4c2a-8567-312c3208cea0/jobs/be58b21491114612ac9d3bdb399bf8d4/driveroutput.000000000 | tail -30
```

### Expected Output
```
Batch: 2
+-------------------+-------------------+-----------+------------+-------------+------------------+-----------------------+
|window_start       |window_end         |order_count|unique_users|total_revenue|avg_order_value   |processed_at           |
+-------------------+-------------------+-----------+------------+-------------+------------------+-----------------------+
|2025-11-24 09:08:00|2025-11-24 09:09:00|5          |3           |15000.0      |3000.0             |2025-11-24 09:08:45.123|
+-------------------+-------------------+-----------+------------+-------------+------------------+-----------------------+
```

## Kubernetes Configuration

### Environment Variables
Order service receives Kafka config from:
- **ConfigMap** (`ecommerce-config`): Server, topics, API key
- **Secret** (`kafka-confluent-secret`): API secret

### Creating the Secret
```bash
kubectl create secret generic kafka-confluent-secret \
  --from-literal=api-secret='cfltyB5+5BItHzO8WV5DuQ+CTFf4Fadlxk4XlnQWYvzxnCRvDSZDZ1U8m88GLLbw' \
  -n ecommerce
```

### Files
- Order Service: `k8s/base/order-service-deployment.yaml`
- Analytics Job: Submitted via `gcloud dataproc jobs submit pyspark`
- Config: `k8s/base/configmap.yaml`
