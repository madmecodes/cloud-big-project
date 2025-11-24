# PointD: GitOps with ArgoCD - CI/CD Pipeline

## Overview
All Kubernetes deployments are managed exclusively via **ArgoCD** (GitOps controller). Direct `kubectl apply` is forbidden. GitHub Actions automates the entire CI/CD pipeline.

---

## 1. Architecture: Code to Cluster

```
Developer
    ↓
Git Push (GitHub)
    ↓
GitHub Actions (CI)
    ├─ Detect changed services
    ├─ Build Docker Image
    ├─ Push to ECR Registry
    └─ Update Kubernetes Manifests
    ↓
Git Commit (Manifest Update)
    ↓
ArgoCD (CD - GitOps Controller)
    ├─ Monitor Git (every 3 minutes)
    ├─ Detect Manifest Changes
    ├─ Pull Latest from Git
    └─ Sync to EKS Cluster
    ↓
Kubernetes Cluster
    ├─ Apply New Manifests
    ├─ Rolling Update Deployments
    └─ Services Running ✅
```

---

## 2. CI/CD Flow - Step by Step

### Step 1: Developer Pushes Code
Developer commits changes to microservice code and pushes to main branch.

### Step 2: GitHub Actions Triggered (CI)
GitHub Actions workflow automatically starts:
- Detects which services changed
- Builds Docker image for each changed service
- Pushes images to AWS ECR with commit SHA as tag
- Updates Kubernetes manifests with new image tags

**Workflow File**: `.github/workflows/build.yaml`

### Step 3: Manifests Updated in Git
GitHub Actions commits the updated manifest files back to the repository.

**Example Update**:
```
k8s/base/order-service-deployment.yaml
OLD: image: ecommerce-order-service:abc123
NEW: image: ecommerce-order-service:def456
```

### Step 4: ArgoCD Detects Changes (CD)
ArgoCD continuously monitors the Git repository (every 3 minutes):
- Polls repository for changes
- Detects manifest file modifications
- Compares Git state with cluster state

**ArgoCD Configuration**: `.k8s/argocd-app.yaml`

### Step 5: ArgoCD Syncs to Cluster
When differences detected, ArgoCD automatically syncs:
- Pulls latest manifests from Git
- Applies to EKS cluster
- Kubernetes performs rolling update
- Old pods terminated, new pods created

---

## 3. Repository Structure

```
cloud-bigProject/
├── .github/workflows/
│   └── build.yaml           # GitHub Actions CI Pipeline
│
├── services/                # Microservice Source Code
│   ├── order-service/
│   ├── user-service/
│   ├── product-service/
│   ├── payment-service/
│   └── notification-lambda/
│
├── k8s/                     # Kubernetes Manifests (GitOps Source)
│   ├── base/
│   │   ├── configmap.yaml
│   │   ├── order-service-deployment.yaml
│   │   ├── user-service-deployment.yaml
│   │   ├── product-service-deployment.yaml
│   │   ├── payment-service-deployment.yaml
│   │   └── observability/
│   ├── argocd-app.yaml      # ArgoCD Application definition
│   └── overlays/            # Environment-specific overrides
│
├── terraform/               # Infrastructure as Code
│
└── PointD.md               # This file
```

---

## 4. GitHub Actions Workflow (CI)

**File**: `.github/workflows/build.yaml`

**Workflow Steps**:
1. Trigger: Push to main branch with changes in `services/` or `k8s/`
2. Detect: Identify which services changed
3. Build: Create Docker image for each changed service
4. Push: Upload image to AWS ECR with commit SHA as tag
5. Update: Modify k8s manifest with new image reference
6. Commit: Push manifest changes back to Git

**Key Features**:
- Uses GitHub Actions secrets for AWS credentials
- Matrix strategy to build multiple services in parallel
- Only builds services that actually changed
- Automatic manifest updates

---

## 5. ArgoCD Configuration

**File**: `k8s/argocd-app.yaml`

**Configuration Details**:
- **Repository**: Watches GitHub repository main branch
- **Path**: Monitors `k8s/base/` directory
- **Auto-sync**: Enabled (automatic sync on detected changes)
- **Prune**: Deletes resources not defined in Git
- **Self-heal**: Auto-syncs if cluster drifts from Git state
