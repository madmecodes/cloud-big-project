# Deployment Guide - Cloud E-Commerce Platform

## Prerequisites

- AWS Account with appropriate IAM permissions
- GCP Project with appropriate IAM permissions
- kubectl configured to access EKS cluster
- Terraform >= 1.0 installed
- Docker installed
- gcloud CLI configured
- ArgoCD CLI installed (optional)

## Step 1: Deploy AWS Infrastructure

### Configure AWS Credentials
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
```

### Deploy Terraform
```bash
cd terraform/aws

# Copy and update the variables file
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# Initialize Terraform
terraform init

# Plan the deployment
terraform plan -out=tfplan

# Apply the configuration
terraform apply tfplan

# Save the outputs for later use
terraform output > aws-outputs.json
```

### Output Values to Note
- EKS Cluster Name
- RDS Endpoint
- MSK Bootstrap Servers
- S3 Bucket Names
- DynamoDB Table Names

## Step 2: Deploy GCP Infrastructure

### Configure GCP Credentials
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
export GCP_PROJECT_ID=your-gcp-project-id
export GCP_REGION=us-central1
```

### Deploy Terraform
```bash
cd terraform/gcp

# Copy and update the variables file
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your GCP project ID

# Initialize Terraform
terraform init

# Plan the deployment
terraform plan -out=tfplan

# Apply the configuration
terraform apply tfplan

# Save the outputs
terraform output > gcp-outputs.json
```

### Output Values to Note
- Dataproc Cluster Name
- GCS Bucket Names
- Flink Service Account Email

## Step 3: Configure EKS Access

### Get Cluster Credentials
```bash
aws eks update-kubeconfig --region us-east-1 --name ecommerce-eks
```

### Verify Cluster Access
```bash
kubectl cluster-info
kubectl get nodes
```

## Step 4: Build and Push Docker Images

### Build All Services
```bash
# Make script executable
chmod +x scripts/build-docker-images.sh

# Build images
./scripts/build-docker-images.sh ecommerce latest

# Or build individual service:
cd services/user-service
docker build -t ecommerce/user-service:latest .
docker push ecommerce/user-service:latest
```

### Create ECR Repositories (Optional)
```bash
aws ecr create-repository --repository-name user-service --region us-east-1
aws ecr create-repository --repository-name api-gateway --region us-east-1
aws ecr create-repository --repository-name product-service --region us-east-1
aws ecr create-repository --repository-name order-service --region us-east-1
aws ecr create-repository --repository-name payment-service --region us-east-1
```

## Step 5: Deploy ArgoCD

### Install ArgoCD
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ArgoCD to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s
```

### Access ArgoCD Dashboard
```bash
# Port forward to access the dashboard
kubectl port-forward svc/argocd-server -n argocd 8443:443

# Get the initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo

# Open browser: https://localhost:8443
```

### Register Git Repository
```bash
argocd repo add https://github.com/your-org/cloud-bigProject \
  --username your-username \
  --password your-personal-access-token \
  --insecure
```

## Step 6: Create Kubernetes Secrets

### Create Database Credentials Secret
```bash
kubectl create secret generic db-credentials \
  --from-literal=url="postgres://admin:PASSWORD@rds-endpoint:5432/ecommerce" \
  --from-literal=username=admin \
  --from-literal=password=PASSWORD \
  -n ecommerce

# Note: Replace PASSWORD and rds-endpoint with actual values from Terraform output
```

### Create AWS Credentials Secret
```bash
kubectl create secret generic aws-credentials \
  --from-literal=access-key-id=$AWS_ACCESS_KEY_ID \
  --from-literal=secret-access-key=$AWS_SECRET_ACCESS_KEY \
  -n ecommerce
```

### Create Stripe Credentials Secret
```bash
kubectl create secret generic stripe-credentials \
  --from-literal=api-key="sk_test_YOUR_STRIPE_KEY" \
  --from-literal=webhook-secret="whsec_YOUR_WEBHOOK_SECRET" \
  -n ecommerce
```

## Step 7: Deploy Applications via ArgoCD

### Apply ArgoCD Application Manifests
```bash
kubectl apply -f k8s/argocd/argocd-application.yaml
```

### Monitor Deployment
```bash
# Watch ArgoCD sync status
argocd app list
argocd app sync ecommerce-platform
argocd app wait ecommerce-platform

# Check pod status
kubectl get pods -n ecommerce -w

# Check service status
kubectl get svc -n ecommerce
```

## Step 8: Deploy Monitoring Stack

### Install Prometheus Operator (Optional)
```bash
kubectl apply -f k8s/base/prometheus-deployment.yaml
```

### Access Prometheus & Grafana
```bash
# Prometheus
kubectl port-forward svc/prometheus -n monitoring 9090:9090

# Grafana
kubectl port-forward svc/grafana -n monitoring 3000:3000

# Open browser:
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

## Step 9: Setup MSK Kafka Topics

### Create Kafka Topics
```bash
# SSH into a Kafka broker or use a Kafka client container
# Create orders topic
kafka-topics.sh --create \
  --bootstrap-servers msk-bootstrap-servers:9092 \
  --topic orders \
  --partitions 3 \
  --replication-factor 2 \
  --config retention.ms=604800000

# Create analytics-results topic
kafka-topics.sh --create \
  --bootstrap-servers msk-bootstrap-servers:9092 \
  --topic analytics-results \
  --partitions 3 \
  --replication-factor 2 \
  --config retention.ms=86400000
```

## Step 10: Deploy Flink Analytics Job

### Build Flink Job JAR
```bash
cd analytics/flink-job
mvn clean package

# Or build from Docker image if using Docker-based build
docker build -t ecommerce/flink-job:latest .
```

### Submit to Dataproc
```bash
gcloud dataproc jobs submit spark-job \
  --cluster=ecommerce-analytics \
  --region=us-central1 \
  --class=org.apache.flink.batch.FlinkBatch \
  gs://ecommerce-flink-code-bucket/flink-job.jar \
  --jars=gs://ecommerce-flink-code-bucket/flink-job.jar
```

## Step 11: Run Load Tests

### Install k6
```bash
# On macOS
brew install k6

# Or download from https://k6.io/docs/getting-started/installation
```

### Run Load Tests
```bash
# Get API Gateway LoadBalancer DNS
API_GW_DNS=$(kubectl get svc api-gateway -n ecommerce -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

# Run the load test
k6 run --vus 100 --duration 5m load-tests/k6/load-test.js \
  --env BASE_URL="http://$API_GW_DNS"

# Or with more detailed output
k6 run --out json=load-test-results.json load-tests/k6/load-test.js
```

## Step 12: Verify Everything is Working

### Check All Services are Running
```bash
# Check pods in ecommerce namespace
kubectl get pods -n ecommerce

# Check if services are ready
kubectl get deployment -n ecommerce

# Check HPA status
kubectl get hpa -n ecommerce
```

### Test API Endpoints
```bash
API_GW_DNS=$(kubectl get svc api-gateway -n ecommerce -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

# Health check
curl http://$API_GW_DNS/health

# List products
curl http://$API_GW_DNS/api/v1/products

# Create a test order
curl -X POST http://$API_GW_DNS/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-123",
    "items": [{"product_id": "prod-001", "quantity": 1}]
  }'
```

### Check Kafka Messages
```bash
# Consume from orders topic to verify events are being published
kafka-console-consumer.sh \
  --bootstrap-servers msk-bootstrap-servers:9092 \
  --topic orders \
  --from-beginning
```

### View Flink Job Status
```bash
# Check Dataproc job status
gcloud dataproc jobs list --cluster=ecommerce-analytics --region=us-central1

# View job output
gcloud dataproc jobs describe job-id --cluster=ecommerce-analytics --region=us-central1
```

## Troubleshooting

### Pods Not Starting
```bash
# Check pod logs
kubectl logs -n ecommerce deployment/api-gateway

# Describe pod for events
kubectl describe pod -n ecommerce pod-name

# Check resource usage
kubectl top nodes
kubectl top pods -n ecommerce
```

### Database Connection Issues
```bash
# Verify RDS endpoint
aws rds describe-db-instances --query 'DBInstances[0].Endpoint'

# Test PostgreSQL connection from within the cluster
kubectl run -it --rm debug --image=postgres --restart=Never -- \
  psql -h rds-endpoint -U admin -d ecommerce
```

### Kafka Connection Issues
```bash
# Check MSK cluster status
aws kafka describe-cluster --cluster-arn <cluster-arn>

# Test Kafka connection
kubectl run -it --rm kafka-client --image=confluentinc/cp-kafka:7.0.0 --restart=Never -- \
  kafka-broker-api-versions.sh --bootstrap-server msk-bootstrap-servers:9092
```

### HPA Not Scaling
```bash
# Check HPA status
kubectl describe hpa -n ecommerce order-service-hpa

# Check metrics-server is running
kubectl get deployment metrics-server -n kube-system

# Check pod metrics
kubectl top pods -n ecommerce
```

## Cleanup

### Delete Everything
```bash
# Remove Kubernetes applications
kubectl delete namespace ecommerce
kubectl delete namespace monitoring
kubectl delete namespace argocd

# Delete AWS infrastructure
cd terraform/aws
terraform destroy -auto-approve

# Delete GCP infrastructure
cd terraform/gcp
terraform destroy -auto-approve
```

## Next Steps

1. Configure domain name and SSL certificates
2. Set up monitoring alerts
3. Configure log aggregation (ELK/Loki)
4. Set up CI/CD pipeline for automated deployments
5. Configure backup and disaster recovery
6. Performance tuning based on load test results
