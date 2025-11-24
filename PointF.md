# PointF: Multi-Cloud Storage Architecture

## Overview
Comprehensive storage solution using **three distinct cloud storage products** for different data types:
- **RDS PostgreSQL** (Managed SQL) - Relational structured data
- **DynamoDB** (Managed NoSQL) - High-throughput semi-structured data
- **S3** (Object Store) - Raw data files and analytics exports

---

## 1. Storage Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│           MICROSERVICES & DATA SOURCES                          │
│  (Order Service, Payment Service, Lambda, Dataproc Spark)       │
└──────────┬──────────────────┬──────────────────┬────────────────┘
           │                  │                  │
           │ Transactional    │ High-throughput  │ Raw files &
           │ (REST APIs)      │ (Events)         │ Analytics
           │                  │                  │
      ┌────▼────┐      ┌─────▼──────┐      ┌───▼────────┐
      │   RDS   │      │ DynamoDB   │      │     S3     │
      │PostgreSQL│     │  (NoSQL)   │      │ (Objects)  │
      └────┬────┘      └─────┬──────┘      └───┬────────┘
           │                  │                  │
           │                  │                  │
      ┌────▼──────┐      ┌────▼────────┐   ┌──▼───────────┐
      │ Users     │      │ Orders      │   │ Product      │
      │ Products  │      │ Payments    │   │ Images       │
      │ Metadata  │      │ Sessions    │   │ Order Docs   │
      │           │      │ Carts       │   │ Analytics    │
      │           │      │ Notifications  │ Results      │
      └───────────┘      └─────────────┘   └──────────────┘
```

---

## 2. RDS PostgreSQL (SQL Database)

### Configuration
**File**: `terraform/aws/modules/rds/main.tf`

**Instance Details**:
- **Name**: ecommerce-db
- **Engine**: PostgreSQL 15.15
- **Database**: ecommerce
- **Class**: db.t3.micro (configurable)
- **Storage**: 20GB (configurable)
- **Backup Retention**: 30 days
- **Multi-AZ**: Enabled (high availability)
- **Public Access**: Disabled (private only)
- **VPC**: Private subnets only

### Purpose: Relational Structured Data
```
Tables (Designed for):
├─ users
│  ├─ user_id (PK)
│  ├─ email
│  ├─ name
│  ├─ created_at
│  └─ updated_at
│
├─ products
│  ├─ product_id (PK)
│  ├─ name
│  ├─ description
│  ├─ price
│  ├─ category
│  └─ stock_level
│
├─ product_categories
│  └─ Hierarchical product organization
│
└─ user_metadata
   ├─ user_id (FK)
   ├─ preferences
   ├─ account_status
   └─ verification_status
```

### When RDS is Triggered

**User Registration**:
```
User Service
    ↓
POST /api/v1/users
    ↓
Validate input
    ↓
INSERT INTO users (email, name, password_hash, ...)
    ↓
RDS PostgreSQL (ecommerce-db)
    ↓
Return user_id ✓
```

**Product Catalog**:
```
Admin uploads product catalog
    ↓
Product Service
    ↓
Batch INSERT INTO products (name, price, ...)
    ↓
RDS PostgreSQL (ecommerce-db)
    ↓
S3 bucket (ecommerce-product-images)
    ↓
Products queryable via REST API ✓
```

### Read Patterns
```
Order Service needs to validate user:
    GET /users/{user_id}
    ↓
    Query RDS: SELECT * FROM users WHERE user_id = ?
    ↓
    Return user details or 404
```

---

## 3. DynamoDB (NoSQL Database)

### Configuration
**File**: `terraform/aws/modules/dynamodb/main.tf`

**Tables Created**:

#### Table 1: Sessions
```
Name: ecommerce-sessions
Billing: PAY_PER_REQUEST
Hash Key: session_id (String)
TTL: expires_at (auto-cleanup after expiry)
Purpose: User session state, temporary data
```

#### Table 2: Carts
```
Name: ecommerce-carts
Billing: PAY_PER_REQUEST
Hash Key: user_id (String)
Range Key: product_id (String)
TTL: expires_at (auto-cleanup abandoned carts)
Purpose: Shopping cart items, temporary
```

#### Table 3: Orders
```
Name: ecommerce-orders
Billing: PAY_PER_REQUEST
Hash Key: id (String - order_id)
Attributes:
  - id: order_id (unique)
  - user_id: user who created order
  - items: list of items
  - total_amount: order total
  - status: pending/confirmed/shipped
  - created_at: timestamp
  - updated_at: timestamp
Purpose: Order transactions (high throughput)
```

#### Table 4: Payments
```
Name: ecommerce-payments
Billing: PAY_PER_REQUEST
Hash Key: id (String - payment_id)
Attributes:
  - id: payment_id (unique)
  - order_id: associated order
  - user_id: who made payment
  - amount: payment amount
  - status: pending/success/failed
  - transaction_id: gateway transaction
  - created_at: timestamp
Purpose: Payment records (high throughput)
```

#### Table 5: Notifications
```
Name: notifications
Billing: PAY_PER_REQUEST
Hash Key: order_id (String)
Range Key: timestamp (String)
TTL: ttl (90-day auto-cleanup)
Attributes:
  - order_id: associated order
  - user_id: recipient user
  - event_type: order.created, order.shipped
  - status: processed/failed
  - total_amount: order amount
  - items_count: number of items
Purpose: Notification audit trail (Lambda writes)
```

### When DynamoDB is Triggered

**Order Creation Flow**:
```
User submits order (POST /api/v1/orders)
    ↓
Order Service (main.py)
    ↓
Validate user (HTTP to User Service)
    ↓
Reserve stock (HTTP to Product Service)
    ↓
CREATE order_id = uuid()
    ↓
DynamoDB PUT:
  Table: ecommerce-orders
  Item: {
    id: order_id,
    user_id: user_id,
    items: [...],
    total_amount: amount,
    status: "pending",
    created_at: now(),
    updated_at: now()
  }
    ↓
Publish to Kafka (ecommerce-orders topic)
    ↓
Send to SQS (ecommerce-order-events queue)
    ↓
Return 201 Created ✓
```

**Lambda Notification Processing**:
```
SQS Message arrives (from Order Service)
    ↓
Lambda Handler (notification-lambda/lambda_function.py)
    ↓
Parse SQS event
    ↓
process_order_event()
    ↓
Convert total_amount to Decimal (DynamoDB format)
    ↓
DynamoDB PUT:
  Table: notifications
  Item: {
    order_id: order_id,
    timestamp: now(),
    user_id: user_id,
    event_type: "order.created",
    total_amount: Decimal(amount),
    items_count: count,
    status: "processed"
  }
    ↓
Log to CloudWatch
    ↓
Return {statusCode: 200} ✓
```

**Dataproc Spark reads from Kafka, writes to DynamoDB**:
```
Spark Streaming Job (GCP Dataproc)
    ↓
Consume from Kafka (orders topic)
    ↓
Aggregate per 1-minute window
    ↓
Calculate metrics:
  - unique_users (count)
  - total_orders
  - total_revenue
  - avg_order_value
    ↓
Could store window results in DynamoDB (optional):
  Table: analytics-windows
  Item: {
    window_id: timestamp,
    unique_users: count,
    total_orders: count,
    total_revenue: amount,
    avg_order_value: amount
  }
```

### High-Throughput Characteristics
```
Order Creation: ~100-1000 requests/second
├─ Each creates DynamoDB item
├─ DynamoDB auto-scales (PAY_PER_REQUEST)
└─ No pre-provisioning needed

Payment Processing: ~50-500 requests/second
├─ Each writes to payments table
├─ Low latency required
└─ DynamoDB enables fast writes

Shopping Carts: Frequently updated
├─ User adds/removes items
├─ TTL auto-cleans abandoned carts
└─ Session-based data
```

---

## 4. S3 (Object Store)

### Buckets Configuration
**File**: `terraform/aws/modules/s3/main.tf`

#### Bucket 1: Product Images
```
Name: ecommerce-product-images-{ACCOUNT_ID}
Versioning: Enabled (history tracking)
Encryption: AES256 (server-side)
Public Access: Blocked
Path Structure:
  /products/{product_id}/
    ├─ main.jpg
    ├─ detail_1.jpg
    ├─ detail_2.jpg
    └─ specifications.pdf

Purpose: Product catalog images
```

#### Bucket 2: Order Documents
```
Name: ecommerce-order-documents-{ACCOUNT_ID}
Versioning: Enabled
Encryption: AES256
Public Access: Blocked (signed URLs for access)
Path Structure:
  /orders/{order_id}/
    ├─ receipt.pdf
    ├─ invoice.pdf
    └─ shipment_label.pdf

Purpose: Order receipts, invoices, shipping docs
```

#### Bucket 3: Analytics Results
```
Name: ecommerce-analytics-results-{ACCOUNT_ID}
Versioning: Disabled (results are immutable)
Encryption: AES256
Public Access: Blocked
Path Structure:
  /daily/
    └─ 2025-11-24/
       ├─ orders_summary.json
       ├─ user_metrics.csv
       ├─ revenue_report.json
       └─ top_products.csv

  /hourly/
    └─ 2025-11-24-10/
       ├─ orders_minute_windows.json
       └─ unique_user_count.json

Purpose: Analytics exports from Dataproc Spark
```
