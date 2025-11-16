# GitOps Workflow Guide

This guide walks through the complete GitOps workflow for the E-Commerce platform using ArgoCD.

## Table of Contents
1. [Initial Setup](#initial-setup)
2. [Development Workflow](#development-workflow)
3. [Staging/Testing Workflow](#stagingtesting-workflow)
4. [Production Deployment](#production-deployment)
5. [Rollback Procedures](#rollback-procedures)
6. [Troubleshooting](#troubleshooting)

---

## Initial Setup

### 1. Prepare Your Git Repository

Fork the repository to your GitHub organization:
```bash
# Clone the repository
git clone https://github.com/your-org/cloud-bigProject.git
cd cloud-bigProject

# Ensure main branch is up to date
git checkout main
git pull origin main
```

### 2. Install ArgoCD on EKS Cluster

```bash
# Create namespace
kubectl create namespace argocd

# Install ArgoCD from your Git repo
kubectl apply -k k8s/argocd/install/

# Wait for ArgoCD to be ready
kubectl wait --for=condition=healthy \
  -l app.kubernetes.io/name=argocd-server \
  -n argocd pod --timeout=300s

# Forward port to access UI
kubectl port-forward svc/argocd-server -n argocd 8443:443 &

# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# Access ArgoCD UI: https://localhost:8443
```

### 3. Register Git Repository with ArgoCD

```bash
# Create personal access token on GitHub (with repo access)
# Go to Settings > Developer settings > Personal access tokens

# Register repository
argocd repo add https://github.com/your-org/cloud-bigProject \
  --username <github-username> \
  --password <personal-access-token> \
  --insecure

# List registered repositories
argocd repo list
```

### 4. Deploy Root Application

```bash
# Create the app-of-apps application
kubectl apply -f k8s/argocd/app-of-apps.yaml

# Check status
argocd app list

# Wait for sync
argocd app wait ecommerce-app-of-apps

# Get detailed status
argocd app get ecommerce-app-of-apps
```

---

## Development Workflow

### Scenario: Adding a new feature to Order Service

#### Step 1: Create Feature Branch

```bash
# Update main branch
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/new-order-feature
```

#### Step 2: Develop and Test Locally

```bash
# Make code changes
vi services/order-service/main.go

# Test locally with docker-compose
docker-compose down  # Clean previous state
docker-compose up -d

# Verify your changes work
curl http://localhost:8003/health
curl http://localhost:8080/api/v1/orders

# Run tests (if available)
cd services/order-service
go test ./...
```

#### Step 3: Update Kubernetes Manifests (if needed)

```bash
# If you changed deployment specifications
vi k8s/base/order-service-deployment.yaml

# Validate manifests
kubectl apply -k k8s/overlays/default --dry-run=client

# Or test with kustomize
kubectl kustomize k8s/overlays/default > /tmp/manifests.yaml
kubectl apply -f /tmp/manifests.yaml --dry-run=client
```

#### Step 4: Commit and Push

```bash
# Stage changes
git add .

# Commit with meaningful message
git commit -m "feat: add new order feature

- Implements feature X
- Updates Order Service API
- Adds new endpoint /api/v1/orders/new"

# Push feature branch
git push origin feature/new-order-feature
```

#### Step 5: Create Pull Request

On GitHub:
1. Create PR from `feature/new-order-feature` → `main`
2. Add description of changes
3. Verify CI/CD checks pass (tests, build, etc.)
4. Request code review
5. After approval, merge PR

#### Step 6: ArgoCD Auto-Syncs

Once merged to `main`:
1. GitHub Actions automatically builds Docker image
2. Tags with semantic version (e.g., `v1.2.0`)
3. Pushes to container registry
4. ArgoCD detects change in `k8s/overlays/default/kustomization.yaml`
5. ArgoCD syncs the cluster
6. Pod restarts with new image
7. Health checks verify new version is healthy

```bash
# Monitor the sync
argocd app get ecommerce-services
argocd app wait ecommerce-services

# Watch pods restart
kubectl get pods -n ecommerce -w

# Check logs
kubectl logs -f -n ecommerce deployment/order-service
```

#### Step 7: Verify Deployment

```bash
# Check that new pods are running
kubectl get pods -n ecommerce | grep order-service

# Verify service is healthy
curl http://api-gateway.ecommerce.svc.cluster.local:8080/health

# Check metrics
curl http://api-gateway:8080/metrics | grep orders

# Run smoke tests
./load-tests/smoke-test.sh
```

---

## Release Workflow

### Preparing and Deploying a Release

#### Step 1: Create Release

```bash
# When main branch is stable and ready to release
git checkout main
git pull origin main

# Create Git tag with semantic version
git tag v1.1.0
git push origin v1.1.0
```

#### Step 2: GitHub Actions Build

```bash
# GitHub Actions automatically:
# 1. Detects tag v1.1.0
# 2. Builds Docker images
# 3. Tags as v1.1.0
# 4. Pushes to container registry
```

#### Step 3: Update Manifests

```bash
# Update image versions
vi k8s/overlays/default/kustomization.yaml

# Change:
# images:
#   - name: ecommerce/api-gateway
#     newTag: v1.1.0

# Commit
git add k8s/overlays/default/kustomization.yaml
git commit -m "deployment: deploy v1.1.0"
git push origin main
```

#### Step 4: Testing Checklist

```bash
# Full regression testing
./scripts/test-all.sh

# Load testing
k6 run --vus 100 --duration 10m load-tests/k6/load-test.js

# Chaos testing
kubectl delete pod <random-pod> -n ecommerce

# Verify recovery
watch kubectl get pods -n ecommerce

# Check metrics and logs
# Access Grafana at http://localhost:3000
# Review dashboards for anomalies
```

#### Step 5: ArgoCD Syncs

```bash
# ArgoCD detects the commit and syncs

# Monitor the deployment
argocd app sync ecommerce-services
argocd app wait ecommerce-services --timeout 600s

# Watch pods rolling out
kubectl get pods -n ecommerce -w

# Verify health
kubectl get deployment -n ecommerce
curl https://api.ecommerce.com/health
```

#### Step 6: Rolling Deployment

With HPA enabled, ArgoCD performs rolling updates:

```
Old Version (Blue)    →    New Version (Green)
3 replicas running         1 new replica starts
                          ↓ Health check passes
                          2 new replicas start
                          ↓ Health check passes
                          3 new replicas running
Old replicas removed
```

```bash
# Monitor rolling update
watch kubectl rollout status deployment/api-gateway -n ecommerce

# Check replica sets
kubectl get replicasets -n ecommerce | grep api-gateway

# Watch endpoint transitions
kubectl get endpoints api-gateway -n ecommerce -w
```

#### Step 7: Post-Deployment Verification

```bash
# Check pod status
kubectl get pods -n ecommerce --selector app=api-gateway

# Check service endpoints
kubectl get endpoints -n ecommerce

# Verify metrics
curl https://api.ecommerce.com/metrics | grep -i "request_total"

# Check logs for errors
kubectl logs -f -n ecommerce deployment/api-gateway | tail -20

# Run health checks
./scripts/health-check.sh

# Monitor error rates and latency
# Access Grafana: https://grafana.ecommerce.com

# Check alerts in AlertManager
# Access AlertManager: https://alertmanager.ecommerce.com
```

---

## Rollback Procedures

### Scenario: Issue Detected in Deployment

#### Option 1: Git Revert (Preferred)

```bash
# Revert the problematic commit
git log --oneline k8s/overlays/default/

# Find the commit to revert
# Example: abc1234 "deployment: deploy v1.1.0"

# Revert the commit
git revert abc1234

# Commit the revert
git commit -m "revert: roll back to v1.0.5 due to issue"

# Push to main
git push origin main

# ArgoCD automatically syncs back to v1.0.5
# Monitor the rollback
argocd app wait ecommerce-services
```

#### Option 2: Manual Sync to Previous Revision

```bash
# Get application history
argocd app history ecommerce-services

# Rollback to previous revision
argocd app rollback ecommerce-services 1

# Verify rollback
argocd app get ecommerce-services
```

#### Option 3: Emergency Pod Deletion

```bash
# If immediate action needed (nuclear option)
# Delete problematic pods - new ones will start with stable version

kubectl delete pod -n ecommerce deployment/api-gateway --all

# Verify new pods start
kubectl get pods -n ecommerce -w

# This forces a redeploy of the same version
# Still safe because it's controlled by ArgoCD
```

#### Verification After Rollback

```bash
# Check version is rolled back
curl https://api.ecommerce.com/version

# Verify error rates dropped
kubectl logs -f -n ecommerce deployment/api-gateway

# Check metrics in Grafana
# Error rates should decrease
# Latency should stabilize

# Run smoke tests
./scripts/smoke-test.sh

# Alert on-call team
slack-notify "#incidents" "Rollback to v1.0.5 complete"
```

---

## Troubleshooting

### Application Out of Sync

```bash
# Check diff
argocd app diff ecommerce-services

# Shows differences between Git and cluster

# Possible causes:
# 1. Manual kubectl changes (revert them!)
# 2. HPA modified replicas (expected, use ignoreDifferences)
# 3. Git changes not synced yet (wait or force sync)

# Force sync
argocd app sync ecommerce-services --force
```

### Kustomize Build Errors

```bash
# Validate kustomization files
kubectl kustomize k8s/overlays/default > /tmp/out.yaml

# Check for errors
cat /tmp/out.yaml | grep -i error

# View generated manifests
kubectl kustomize k8s/overlays/default | head -100

# Test apply
kubectl apply -k k8s/overlays/default --dry-run=client
```

### Image Not Updating

```bash
# Check image in kustomization.yaml
cat k8s/overlays/default/kustomization.yaml | grep -A3 "images:"

# Ensure format is correct:
# images:
#   - name: ecommerce/api-gateway
#     newTag: v1.0.0

# Force pod restart if image is correct
kubectl rollout restart deployment/api-gateway -n ecommerce

# Check what image is running
kubectl get deployment -n ecommerce -o jsonpath='{.items[0].spec.template.spec.containers[0].image}'
```

### ArgoCD Can't Access Git Repo

```bash
# Check repository credentials
argocd repo list

# If not found, re-add it:
argocd repo add https://github.com/your-org/cloud-bigProject \
  --username <github-username> \
  --password <token>

# Check SSH keys (if using SSH)
kubectl get secret -n argocd argocd-repo-<repo-name>

# Test connectivity
argocd repo get https://github.com/your-org/cloud-bigProject
```

### Sync Webhook Not Triggered

```bash
# GitHub Webhook might not be configured

# Add webhook to GitHub:
# 1. Go to Settings > Webhooks
# 2. Add webhook:
#    - Payload URL: https://argocd.ecommerce.com/api/webhook
#    - Content-type: application/json
#    - Push events: Checked

# Test webhook
curl -X POST https://argocd.ecommerce.com/api/webhook \
  -H "Content-Type: application/json" \
  -d '{"repository": {"name": "cloud-bigProject"}}'

# Or manually sync
argocd app sync ecommerce-services
```

---

## Best Practices Summary

✅ **Always:**
- Commit manifests to Git before deploying
- Use feature branches for development
- Create PRs for code review
- Test locally before pushing
- Use semantic versioning for releases
- Tag all releases
- Monitor metrics after deployment
- Keep main branch stable

❌ **Never:**
- `kubectl apply` directly to cluster (use GitOps)
- Commit secrets to Git
- Use `latest` tag for deployments
- Deploy untested code
- Manually modify resources in cluster
- Skip code review
- Mix different versions in one deployment

---

## Command Reference

```bash
# List all applications
argocd app list

# Get application status
argocd app get <app-name>

# Synchronize application
argocd app sync <app-name>

# Monitor sync progress
argocd app wait <app-name> --timeout 600s

# Rollback to previous revision
argocd app rollback <app-name> 1

# Force refresh from Git
argocd app refresh <app-name> --hard

# View application history
argocd app history <app-name>

# Delete an application
argocd app delete <app-name>

# Get detailed diff
argocd app diff <app-name>

# Log in to ArgoCD
argocd login <argocd-server>

# Add Git repository
argocd repo add <repo-url> --username <user> --password <password>

# List registered repositories
argocd repo list
```

---

## Next Steps

1. Follow the [Initial Setup](#initial-setup) section
2. Practice with the [Development Workflow](#development-workflow)
3. Test rollback procedures
4. Deploy releases following [Release Workflow](#release-workflow)
5. Document your team's specific processes

For more help, see `README.md` in this directory.
