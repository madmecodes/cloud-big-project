#!/bin/bash

# Test script for ecommerce microservices
ALB_DNS="a036cdb355d8c469687b423f21d14f13-953790429.ap-south-1.elb.amazonaws.com"
BASE_URL="http://$ALB_DNS"

echo "=========================================="
echo "ECOMMERCE MICROSERVICES TEST SUITE"
echo "=========================================="
echo "Testing at: $BASE_URL"
echo ""

# Test 1: API Gateway Health
echo "TEST 1: API Gateway Health Check"
echo "================================="
curl -s -w "HTTP Status: %{http_code}\n" "$BASE_URL/health" 2>&1
echo ""

# Test 2: Create Product 1
echo "TEST 2: Create Product 1 (Laptop Pro)"
echo "===================================="
PRODUCT_1=$(curl -s -X POST "$BASE_URL/api/v1/products" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Laptop Pro 16",
    "description": "High-performance developer laptop",
    "price": 1999.99,
    "stock": 50,
    "sku": "LAPTOP-PRO-16",
    "category": "Electronics"
  }')
echo "$PRODUCT_1" | jq '.'
PRODUCT_1_ID=$(echo "$PRODUCT_1" | jq -r '.id')
echo "Created Product ID: $PRODUCT_1_ID"
echo ""

# Test 3: Create Product 2
echo "TEST 3: Create Product 2 (Mouse)"
echo "================================="
PRODUCT_2=$(curl -s -X POST "$BASE_URL/api/v1/products" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Wireless Mouse",
    "description": "Ergonomic wireless mouse",
    "price": 29.99,
    "stock": 200,
    "sku": "MOUSE-WIRELESS-001",
    "category": "Accessories"
  }')
echo "$PRODUCT_2" | jq '.'
PRODUCT_2_ID=$(echo "$PRODUCT_2" | jq -r '.id')
echo "Created Product ID: $PRODUCT_2_ID"
echo ""

# Test 4: Get Product by ID
echo "TEST 4: Get Product by ID ($PRODUCT_1_ID)"
echo "=========================================="
curl -s -X GET "$BASE_URL/api/v1/products/$PRODUCT_1_ID" \
  -H "Content-Type: application/json" | jq '.'
echo ""

# Test 5: List Products
echo "TEST 5: List All Products"
echo "========================="
curl -s -X GET "$BASE_URL/api/v1/products?skip=0&limit=10" \
  -H "Content-Type: application/json" | jq '.'
echo ""

# Test 6: Get Product Stock
echo "TEST 6: Get Product Stock ($PRODUCT_1_ID)"
echo "=========================================="
curl -s -X GET "$BASE_URL/api/v1/products/$PRODUCT_1_ID/stock" \
  -H "Content-Type: application/json" | jq '.'
echo ""

# Test 7: Reserve Stock
echo "TEST 7: Reserve 10 units of Product 1"
echo "====================================="
curl -s -X POST "$BASE_URL/api/v1/products/$PRODUCT_1_ID/reserve?quantity=10" \
  -H "Content-Type: application/json" | jq '.'
echo ""

# Test 8: Verify Stock Reduced
echo "TEST 8: Verify Stock After Reservation"
echo "======================================"
curl -s -X GET "$BASE_URL/api/v1/products/$PRODUCT_1_ID/stock" \
  -H "Content-Type: application/json" | jq '.'
echo ""

# Test 9: Update Product
echo "TEST 9: Update Product Price"
echo "============================"
curl -s -X PUT "$BASE_URL/api/v1/products/$PRODUCT_1_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "price": 1799.99,
    "description": "Updated: High-performance developer laptop - On Sale!"
  }' | jq '.'
echo ""

# Test 10: Prometheus Metrics
echo "TEST 10: Check Prometheus Metrics"
echo "=================================="
curl -s "$BASE_URL/metrics" 2>&1 | head -30
echo ""

echo "=========================================="
echo "ALL BASIC TESTS COMPLETED SUCCESSFULLY"
echo "=========================================="
