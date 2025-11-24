# E-Commerce API Collection

This directory contains Bruno API collection for the E-Commerce microservices platform.

## Getting Started

1. Install [Bruno](https://www.usebruno.com/)
2. Open Bruno and import this collection (File > Open Collection > Select this folder)
3. Select the `dev` environment from the dropdown

## Environment Variables

Edit `environments/dev.bru` to set your environment:

| Variable | Description | Default |
|----------|-------------|---------|
| `base_url` | API Gateway URL | AWS ALB endpoint |
| `user_service_url` | User Service internal URL | http://user-service:8001 |
| `product_service_url` | Product Service internal URL | http://product-service:8001 |
| `order_service_url` | Order Service internal URL | http://order-service:8003 |
| `payment_service_url` | Payment Service internal URL | http://payment-service:8004 |

## Collection Structure

```
bruno/
├── External APIs/          # Public APIs (via API Gateway)
│   ├── Users/
│   │   ├── Create User.bru
│   │   └── Get User.bru
│   ├── Products/
│   │   ├── Create Product.bru
│   │   ├── Get Products.bru
│   │   └── Get Product.bru
│   ├── Orders/
│   │   ├── Create Order.bru
│   │   ├── Get Order.bru
│   │   └── Get User Orders.bru
│   └── Payments/
│       ├── Process Payment.bru
│       ├── Get Payment.bru
│       └── Refund Payment.bru
├── Internal APIs/          # Service-to-Service APIs
│   ├── Order-Service/
│   │   ├── Validate User.bru
│   │   └── Reserve Stock.bru
│   └── Payment-Service/
│       └── Update Order Status.bru
└── environments/
    └── dev.bru
```

---

## External APIs

These APIs are accessed through the API Gateway and are intended for external clients.

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/users` | Create a new user |
| GET | `/api/v1/users/{user_id}` | Get user by ID |

### Products

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/products` | Create a new product |
| GET | `/api/v1/products` | List all products |
| GET | `/api/v1/products/{product_id}` | Get product by ID |

### Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/orders` | Create a new order |
| GET | `/api/v1/orders/{order_id}` | Get order by ID |
| GET | `/api/v1/orders/user/{user_id}` | Get orders by user |

### Payments

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/payments` | Process a payment |
| GET | `/api/v1/payments/{payment_id}` | Get payment by ID |
| POST | `/api/v1/payments/{payment_id}/refund` | Refund a payment |

---

## Internal APIs (Service-to-Service)

These APIs are used internally between microservices and are NOT exposed through the API Gateway.

### Order Service Dependencies

When creating an order, the Order Service makes these internal calls:

#### 1. Validate User (Order -> User Service)

```
GET http://user-service:8001/users/{user_id}
```

**Purpose:** Verify that the user exists before creating an order.

**Response:**
- `200 OK` - User exists
- `404 Not Found` - User does not exist

#### 2. Reserve Stock (Order -> Product Service)

```
POST http://product-service:8001/api/v1/products/{product_id}/reserve?quantity=N
```

**Purpose:** Reserve product inventory when creating an order.

**Response:**
- `200 OK` - Stock reserved successfully
- `400 Bad Request` - Insufficient stock

### Payment Service Callbacks

When processing a payment, the Payment Service makes these callbacks:

#### 1. Update Order Status (Payment -> Order Service)

```
PUT http://order-service:8003/api/v1/orders/{order_id}/status?status={status}
```

**Purpose:** Update order status after payment processing.

**Status Values:**
- `paid` - Payment successful
- `payment_failed` - Payment failed
- `refunded` - Payment refunded

---

## Communication Flow Diagram

```
External Client
      |
      v
+-------------+
| API Gateway |  (Port 8080)
+-------------+
      |
      +---> User Service (8001) ---> PostgreSQL
      |
      +---> Product Service (8001) ---> PostgreSQL
      |
      +---> Order Service (8003) ---> DynamoDB
      |           |
      |           +---> User Service (validate)
      |           +---> Product Service (reserve stock)
      |           +---> Kafka (publish event)
      |
      +---> Payment Service (8004) ---> DynamoDB
                  |
                  +---> Order Service (update status)
```

## E2E Test Flow

1. **Create User** - `POST /api/v1/users`
2. **Create Product** - `POST /api/v1/products`
3. **Create Order** - `POST /api/v1/orders` (triggers internal calls)
4. **Process Payment** - `POST /api/v1/payments` (triggers status update callback)
5. **Verify Order** - `GET /api/v1/orders/{id}` (status should be "paid")

## Database Storage

| Service | Database | Table/Collection |
|---------|----------|------------------|
| User Service | PostgreSQL (RDS) | users |
| Product Service | PostgreSQL (RDS) | products |
| Order Service | DynamoDB | ecommerce-orders |
| Payment Service | DynamoDB | ecommerce-payments |
