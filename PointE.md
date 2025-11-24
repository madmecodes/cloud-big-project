# PointE: Real-Time Stream Processing with Flink/Spark

## Overview
Real-time stream processing service using **Apache Spark** (PySpark) on **GCP Dataproc** (Provider B) that consumes order events from Kafka, performs stateful time-windowed aggregations, and publishes results back to Kafka.

---

## 1. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AWS (Provider A)                                │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Order Service (EKS)                                              │ │
│  │  ├─ Create Order                                                  │ │
│  │  ├─ Publish Event to Kafka                                       │ │
│  │  └─ Message Format:                                              │ │
│  │     {                                                             │ │
│  │       "order_id": "uuid",                                        │ │
│  │       "user_id": "uuid",                                         │ │
│  │       "total_amount": 1000.0,                                    │ │
│  │       "status": "pending",                                       │ │
│  │       "items_count": 2,                                          │ │
│  │       "event_type": "order.created",                             │ │
│  │       "created_at": "2025-11-24T10:50:09Z"                       │ │
│  │     }                                                             │ │
│  └───────────────────────────┬───────────────────────────────────────┘ │
│                              │                                         │
│                              │ Publishes Events                        │
│                              ▼                                         │
└──────────────────────────────┼─────────────────────────────────────────┘
                               │
                ┌──────────────▼──────────────┐
                │  Confluent Cloud Kafka      │
                │  Managed Service            │
                │                             │
                │  Topic: "orders"            │
                │  Partitions: 3              │
                │  Retention: 7 days          │
                │  Security: SASL/SSL         │
                └──────────────┬──────────────┘
                               │
                               │ Consumes Events
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    GCP (Provider B)                                      │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Dataproc Cluster (Streaming)                                     │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │ Spark Streaming Job (PySpark)                              │ │ │
│  │  │                                                             │ │ │
│  │  │ 1. Read from Kafka "orders" topic                         │ │ │
│  │  │ 2. Parse JSON events                                      │ │ │
│  │  │ 3. Extract timestamp & user_id                            │ │ │
│  │  │ 4. Apply Tumbling Window (1-minute)                       │ │ │
│  │  │ 5. Count unique users per window                          │ │ │
│  │  │ 6. Calculate aggregations:                                │ │ │
│  │  │    - Unique User Count                                    │ │ │
│  │  │    - Total Orders                                         │ │ │
│  │  │    - Total Revenue                                        │ │ │
│  │  │    - Average Order Value                                  │ │ │
│  │  │ 7. Publish results to Kafka "analytics-results" topic    │ │ │
│  │  │                                                             │ │ │
│  │  │ STATE:                                                      │ │ │
│  │  │   Maintains user counts within each window                │ │ │
│  │  │   Watermark: Handles late-arriving events (30 sec delay)  │ │ │
│  │  │   Approximate count for streaming efficiency              │ │ │
│  │  │                                                             │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                   │ │
│  │  Job File: analytics/flink-job/order_analytics.py               │ │
│  │  Platform: GCP Dataproc (Spark Structured Streaming)            │ │
│  │  Runtime: 24/7 continuous                                        │ │
│  │  Checkpoint: gs://ecommerce-analytics-checkpoints/order-analytics
│  └───────────────────────────┬───────────────────────────────────────┘ │
│                              │                                         │
│                              │ Publishes Aggregations to Kafka        │
│                              ▼                                         │
└───────────────────────────────────────────────────────────────────────┘
                               │
                ┌──────────────────────────────┐
                │ Confluent Cloud Kafka        │
                │ Topic: "analytics-results"   │
                │                              │
                │ Message Format:              │
                │ {                            │
                │   "window_start": "...",     │
                │   "window_end": "...",       │
                │   "unique_users": 150,       │
                │   "total_orders": 342,       │
                │   "total_revenue": 125000,   │
                │   "avg_order_value": 365.5   │
                │ }                            │
                └──────────────────────────────┘
```

---

## 2. Stream Processing Components

### 2.1 Data Sources (Kafka Input)

**Topic**: `orders`
**Source**: Order Service (AWS EKS)
**Message Format**: JSON with order details
**Frequency**: Real-time, as orders are created

### 2.2 Stream Processing Service

**Platform**: GCP Dataproc
**Technology**: Apache Spark Structured Streaming (PySpark)
**Location**: `analytics/flink-job/order_analytics.py`
**Runtime**: Python 3.x on Spark cluster (Structured Streaming)

**Processing Steps**:
1. Consume events from Kafka "orders" topic
2. Parse JSON messages
3. Apply transformations (extract fields)
4. Create tumbling windows (1-minute intervals)
5. Perform stateful aggregations
6. Publish results to "analytics-results" topic

### 2.3 Stateful Aggregations

**Time Window**: 1-minute tumbling window
**State Type**: Count of unique users per window

**Aggregation Metrics**:
- `unique_users`: Count of distinct user_ids in window
- `total_orders`: Total number of orders in window
- `total_revenue`: Sum of all order amounts in window
- `avg_order_value`: Average order amount in window

**State Management**:
- Spark maintains window state in memory
- Watermark: 30 seconds (handles late-arriving events)
- State backend: Checkpointed to GCS (`gs://ecommerce-analytics-checkpoints/order-analytics`) for fault tolerance

### 2.4 Results Output

**Topic**: `analytics-results`
**Destination**: Kafka topic (for real-time subscribers)
**Message Format**: JSON with window_start, window_end, unique_users, total_revenue, avg_order_value
**Update Frequency**: Every 1 minute

---

## 3. Kafka Configuration

### Managed Service
**Provider**: Confluent Cloud
**Hosting**: GCP (asia-south1 region)
**Type**: Fully managed, serverless Kafka

### Topics

| Topic | Purpose | Partitions | Retention |
|-------|---------|-----------|-----------|
| `orders` | Order events from services | 3 | 7 days |
| `analytics-results` | Aggregation results from Spark | 3 | 7 days |

### Security
- **Protocol**: SASL/SSL (TLS encryption)
- **Authentication**: API key + secret
- **Network**: Accessible from AWS and GCP

---

## 4. Time-Windowed Aggregation Flow

```
Input Stream (Kafka "orders" topic):
┌────────────────────────────────────────────────┐
│ Event 1: order_id=123, user_id=u1, amount=100 │ T=10:50:05
│ Event 2: order_id=124, user_id=u2, amount=200 │ T=10:50:08
│ Event 3: order_id=125, user_id=u1, amount=150 │ T=10:50:12
│ Event 4: order_id=126, user_id=u3, amount=300 │ T=10:50:45
│ Event 5: order_id=127, user_id=u2, amount=250 │ T=10:51:05 (next window)
│ Event 6: order_id=128, user_id=u1, amount=180 │ T=10:51:22 (next window)
└────────────────────────────────────────────────┘
                    │
                    ▼
        Apply Tumbling Window (1 minute)
                    │
        ┌───────────┴──────────┐
        │                      │
        ▼                      ▼
Window 1 [10:50:00-10:51:00)  Window 2 [10:51:00-10:52:00)
├─ Event 1                     ├─ Event 5
├─ Event 2                     └─ Event 6
├─ Event 3
└─ Event 4
        │                      │
        ▼                      ▼
    Aggregate                 Aggregate
        │                      │
    ┌───┴────────────┐         │
    │ STATE:         │         │
    │ u1: 2 times    │         │
    │ u2: 1 time     │         │
    │ u3: 1 time     │         │
    └────────────────┘         │
        │                      │
        ▼                      ▼
    Result 1              Result 2
    {                     {
      window_start: 10:50,   window_start: 10:51,
      unique_users: 3,       unique_users: 2,
      total_orders: 4,       total_orders: 2,
      total_revenue: 650,    total_revenue: 430,
      avg_order_value: 162.5 avg_order_value: 215
    }                     }
        │                      │
        └──────────┬───────────┘
                   │
                   ▼
    Kafka Topic: analytics-results
    (published for real-time subscribers)
```

---

## 5. Key Streaming Features

### 5.1 Stateful Processing
- **Maintains State**: Unique user count within each time window
- **State Updates**: User count incremented as events arrive
- **State Cleanup**: Old windows cleaned up after watermark passes

### 5.2 Time Windowing
- **Window Type**: Tumbling (non-overlapping)
- **Window Duration**: 1 minute
- **Window Operator**: GroupedAggregation with window()

### 5.3 Watermarking
- **Watermark Delay**: 30 seconds
- **Purpose**: Handle out-of-order and late-arriving events
- **Behavior**: Events arriving within 30 seconds of window close are included

### 5.4 Fault Tolerance
- **Checkpointing**: Spark saves state to GCS periodically
- **Restart**: Can recover from failures without data loss
- **Idempotence**: Exactly-once semantics via Kafka offsets

---

## 6. Data Flow Example

**Scenario**: Orders arriving in 10:50 minute

**Input (Kafka "orders" topic)**:
```
10:50:05 - order_id=ORD001, user_id=USER1, amount=100, event_type=order.created
10:50:12 - order_id=ORD002, user_id=USER2, amount=200, event_type=order.created
10:50:28 - order_id=ORD003, user_id=USER1, amount=150, event_type=order.created
10:50:45 - order_id=ORD004, user_id=USER3, amount=300, event_type=order.created
```

**Spark Streaming Processing**:
1. Spark reads 4 events from Kafka
2. Extracts: timestamp, user_id, amount
3. Groups by 1-minute window [10:50:00-10:51:00)
4. State maintained:
   - USER1: appears 2 times
   - USER2: appears 1 time
   - USER3: appears 1 time
5. Calculates aggregations

**Output (Kafka "analytics-results" topic)**:
```json
{
  "window_start": "2025-11-24T10:50:00Z",
  "window_end": "2025-11-24T10:51:00Z",
  "unique_users": 3,
  "total_orders": 4,
  "total_revenue": 750.0,
  "avg_order_value": 187.5,
  "processed_at": "2025-11-24T10:51:15Z"
}
```

---

## 7. Implementation Details

### Service Location
**File**: `analytics/flink-job/order_analytics.py`
- Spark Structured Streaming application
- Kafka consumer (using Spark Kafka integration)
- Stateful aggregations (using DataFrame operations)
- Kafka producer (publishing results)

### Deployment
**Location**: GCP Dataproc cluster
**Submission**: Spark submit job
**Runtime**: 24/7 continuous processing
**Scaling**: Auto-scales based on Kafka lag

### Kafka Integration
- **Input**: Spark Kafka source for "orders" topic
- **Output**: Spark Kafka sink for "analytics-results" topic
- **Offset Management**: Spark manages offsets automatically

### Data Persistence
- **Output Topic**: `analytics-results` (Confluent Cloud Kafka)
- **Checkpoint Location**: `gs://ecommerce-analytics-checkpoints/order-analytics` (GCS)
- **State Recovery**: Enables fault-tolerant streaming

---

## 8. Real-Time Insights

### Available Metrics
From analytics-results Kafka topic:
- Real-time user activity (unique users per minute)
- Order rate (orders per minute)
- Revenue metrics (total, average per order)
- User engagement patterns
- Peak activity windows

### Downstream Consumers
Other services can consume "analytics-results" topic:
- **Dashboard Service**: Display live metrics
- **Alert Service**: Trigger alerts on anomalies
- **Recommendation Engine**: Feed user behavior data
- **Business Analytics**: Track KPIs

---

## 9. Requirements Compliance

| Requirement | Implementation | Status |
|---|---|---|
| Real-time stream processing | Spark Streaming on Dataproc | ✅ |
| Managed cluster (Provider B) | GCP Dataproc | ✅ |
| Kafka topic consumption | Consumes "orders" topic | ✅ |
| Stateful aggregation | Unique user count per window | ✅ |
| Time-windowed (tumbling) | 1-minute windows | ✅ |
| Aggregation type specified | Count of unique users | ✅ |
| Results published to Kafka | "analytics-results" topic | ✅ |
| Separate results topic | Yes, "analytics-results" | ✅ |
| Managed Kafka service | Confluent Cloud | ✅ |
| Cloud-native | All managed services | ✅ |

---