#!/bin/bash

# Build and push Docker images for all microservices
# Usage: ./build-docker-images.sh [registry-url] [tag]

set -e

REGISTRY=${1:-"ecommerce"}
TAG=${2:-"latest"}

echo "Building Docker images for E-Commerce Platform"
echo "Registry: $REGISTRY"
echo "Tag: $TAG"
echo ""

SERVICES=(
  "api-gateway"
  "user-service"
  "product-service"
  "order-service"
  "payment-service"
  "notification-lambda"
)

for service in "${SERVICES[@]}"; do
  echo "=========================================="
  echo "Building $service..."
  echo "=========================================="

  if [ ! -d "services/$service" ]; then
    echo "Warning: services/$service directory not found"
    continue
  fi

  IMAGE_NAME="$REGISTRY/$service:$TAG"

  docker build -t "$IMAGE_NAME" -f "services/$service/Dockerfile" "services/$service/"

  echo "Successfully built: $IMAGE_NAME"
  echo ""
done

echo "=========================================="
echo "All images built successfully!"
echo "=========================================="
echo ""
echo "To push images to registry, run:"
echo "docker push $REGISTRY/*:$TAG"
