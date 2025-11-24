import http from 'k6/http';
import { check, sleep } from 'k6';

// Simple HPA scaling test
export const options = {
  stages: [
    { duration: '30s', target: 15, name: 'ramp-up' },
    { duration: '3m', target: 25, name: 'sustained load' },
    { duration: '1m', target: 0, name: 'ramp-down' }
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000'],
    http_req_failed: ['rate<0.1'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://a036cdb355d8c469687b423f21d14f13-953790429.ap-south-1.elb.amazonaws.com';

export default function () {
  const payload = JSON.stringify({
    user_id: 'd61d7bd4-8fc0-48f9-8f9e-39e6759ff0a4',
    shipping_address: {
      street: 'Test Street',
      city: 'Mumbai',
      state: 'MH',
      zip: '400001',
      country: 'India'
    },
    items: [{
      product_id: '0be37192-b396-4d46-94df-0c922dfe3cf6',
      quantity: 1,
      price: 1000
    }]
  });

  const res = http.post(`${BASE_URL}/api/v1/orders`, payload, {
    headers: { 'Content-Type': 'application/json' },
    timeout: '30s',
  });

  check(res, {
    'status is 201': (r) => r.status === 201,
    'response time < 1000ms': (r) => r.timings.duration < 1000,
    'contains order_id': (r) => r.body.includes('id'),
  });

  sleep(Math.random() * 2);
}
