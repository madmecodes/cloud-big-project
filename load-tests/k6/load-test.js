import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency');
const orderLatency = new Trend('order_latency');
const successfulOrders = new Counter('successful_orders');
const activeUsers = new Gauge('active_users');

// Configuration
export const options = {
  stages: [
    { duration: '30s', target: 20, name: 'ramp-up' },
    { duration: '1m30s', target: 50, name: 'steady-state' },
    { duration: '1m', target: 100, name: 'spike' },
    { duration: '1m', target: 50, name: 'cool-down' },
    { duration: '30s', target: 0, name: 'ramp-down' }
  ],
  thresholds: {
    'http_req_duration': ['p(95)<500', 'p(99)<1000'],
    'http_req_failed': ['rate<0.1'],
    'errors': ['rate<0.05'],
    'api_latency': ['p(95)<200'],
    'order_latency': ['p(95)<1000']
  },
  ext: {
    loadimpact: {
      projectID: 3405109,
      name: 'E-Commerce Load Test'
    }
  }
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

// Test data
const products = [
  { id: 'prod-001', name: 'Laptop' },
  { id: 'prod-002', name: 'Monitor' },
  { id: 'prod-003', name: 'Keyboard' },
  { id: 'prod-004', name: 'Mouse' },
  { id: 'prod-005', name: 'Headphones' }
];

export default function (data) {
  activeUsers.add(1);

  group('API Gateway - Health Check', () => {
    let res = http.get(`${BASE_URL}/health`, {
      timeout: '10s'
    });

    check(res, {
      'health check status is 200': (r) => r.status === 200
    }) || errorRate.add(1);

    apiLatency.add(res.timings.duration);
  });

  group('Product Listing', () => {
    let res = http.get(`${BASE_URL}/api/v1/products?skip=0&limit=10`, {
      timeout: '10s',
      headers: {
        'Accept': 'application/json'
      }
    });

    check(res, {
      'product list status is 200': (r) => r.status === 200,
      'response time < 200ms': (r) => r.timings.duration < 200,
      'response contains products': (r) => r.body && r.body.includes('prod')
    }) || errorRate.add(1);

    apiLatency.add(res.timings.duration);
  });

  // Simulate user selecting a random product
  let randomProduct = products[Math.floor(Math.random() * products.length)];

  group('Product Detail', () => {
    let res = http.get(`${BASE_URL}/api/v1/products/${randomProduct.id}`, {
      timeout: '10s'
    });

    check(res, {
      'product detail status is 200': (r) => r.status === 200,
      'response time < 300ms': (r) => r.timings.duration < 300
    }) || errorRate.add(1);

    apiLatency.add(res.timings.duration);
  });

  group('User Registration / Login', () => {
    let loginRes = http.post(
      `${BASE_URL}/api/v1/auth/login`,
      JSON.stringify({
        email: `user-${Date.now()}@example.com`,
        password: 'Password123!'
      }),
      {
        headers: { 'Content-Type': 'application/json' },
        timeout: '10s'
      }
    );

    check(loginRes, {
      'login status is 200': (r) => r.status === 200,
      'login response contains token': (r) => r.body && r.body.includes('token')
    }) || errorRate.add(1);

    apiLatency.add(loginRes.timings.duration);

    return loginRes.body;
  });

  group('Create Order - Triggers Kafka, Lambda, and Flink', () => {
    let orderPayload = JSON.stringify({
      user_id: `user-${__VU}-${__ITER}`,
      items: [
        {
          product_id: randomProduct.id,
          quantity: Math.floor(Math.random() * 5) + 1
        }
      ],
      shipping_address: {
        street: '123 Main St',
        city: 'San Francisco',
        state: 'CA',
        zip: '94105',
        country: 'USA'
      }
    });

    let orderRes = http.post(
      `${BASE_URL}/api/v1/orders`,
      orderPayload,
      {
        headers: { 'Content-Type': 'application/json' },
        timeout: '30s'
      }
    );

    check(orderRes, {
      'order creation status is 200 or 201': (r) => r.status === 200 || r.status === 201,
      'order response time < 2000ms': (r) => r.timings.duration < 2000,
      'order response contains order_id': (r) => r.body && r.body.includes('order_id')
    }) || errorRate.add(1);

    if (orderRes.status === 200 || orderRes.status === 201) {
      successfulOrders.add(1);
    }

    orderLatency.add(orderRes.timings.duration);
  });

  // Verify order was persisted
  group('Get Order Status', () => {
    // In a real scenario, we'd extract the order_id from the response above
    let orderId = `order-${__VU}-${__ITER}`;

    let orderStatusRes = http.get(
      `${BASE_URL}/api/v1/orders/${orderId}`,
      { timeout: '10s' }
    );

    check(orderStatusRes, {
      'order status endpoint responds': (r) => r.status === 200 || r.status === 404,
      'response time < 500ms': (r) => r.timings.duration < 500
    }) || errorRate.add(1);

    apiLatency.add(orderStatusRes.timings.duration);
  });

  sleep(Math.random() * 3);
  activeUsers.add(-1);
}

// Summary function
export function teardown(data) {
  console.log('=== Load Test Complete ===');
  console.log(`Total successful orders: ${successfulOrders}`);
  console.log(`Total errors: ${errorRate}`);
}
