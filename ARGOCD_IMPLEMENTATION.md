# Complete ArgoCD Implementation for E-Commerce Platform

## Overview

This document summarizes the **complete GitOps implementation** using ArgoCD for the E-Commerce microservices platform.

---

## What Has Been Implemented ✅

### 1. **ArgoCD Installation Files**
Location: `k8s/argocd/install/`

```
namespace.yaml          - ArgoCD namespace
argocd-cm.yaml         - Configuration (RBAC, TLS, server settings)
argocd-rbac.yaml       - ServiceAccounts and ClusterRoles
kustomization.yaml     - Kustomize overlay for installation
```

**Features:**
- RBAC configuration (admin, developer, ops roles)
- SSH known hosts for Git repositories
- TLS certificate management
- Logging configuration
- Server and repo server settings

### 2. **Kustomize Overlay** (Configuration Management)
Location: `k8s/overlays/default/`

```
k8s/overlays/default/
├── kustomization.yaml     - Deployment configuration
├── configmap.yaml         - Environment variables
└── networkpolicy.yaml     - Network security policies
```

**Configuration:**
- 2-3 replicas per service (High Availability)
- Semantic version tags (v1.0.0)
- HPA enabled (min: 3, max: 15-20)
- Info logging
- Network policies for security
- Resource limits enforced

### 3. **App-of-Apps Pattern**
Location: `k8s/argocd/`

```yaml
ecommerce-app-of-apps (Root Application)
  ├─ ecommerce-services (Microservices deployment)
  ├─ observability (Prometheus/Grafana)
  └─ gitops-tools (ArgoCD, Flux, etc.)
```

**Benefits:**
- Single source of truth
- Declarative management of all applications
- Easy to manage applications
- Hierarchical deployment control

### 4. **Git Repository Structure**
Location: `.gitops/`

```
.gitops/
├── README.md     - Repository structure guide
└── WORKFLOW.md   - Complete GitOps workflow
```

**Documentation:**
- Git branch strategy
- Directory organization
- Deployment flow
- Image tagging strategy
- Secret management
- Troubleshooting guide

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Repository                        │
│  (Source of Truth for all K8s configurations & services)   │
└──────┬──────────────────────────────────────────────────────┘
       │
       │ Watches: main branch
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                      ArgoCD Server                            │
│                     (argocd namespace)                        │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Root Application: ecommerce-app-of-apps                ││
│  │ ├─ ecommerce-services (k8s/overlays/default)           ││
│  │ ├─ observability (Prometheus/Grafana)                  ││
│  │ └─ gitops-tools                                         ││
│  └─────────────────────────────────────────────────────────┘│
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Components:                                             ││
│  │ - argocd-server (UI & API)                              ││
│  │ - argocd-repo-server (Git reconciliation)               ││
│  │ - argocd-application-controller (Syncing)               ││
│  │ - argocd-dex-server (OIDC authentication)               ││
│  └─────────────────────────────────────────────────────────┘│
└───────┬──────────────────────────────────────────────────────┘
        │ Syncs state
        │ (Pull-based)
        │
        ▼
   ┌──────────────┐
   │   Cluster    │
   │ (EKS - AWS)  │
   │              │
   │ ecommerce    │
   │ namespace    │
   │              │
   │ Services:    │
   │ - api-gate   │
   │ - user       │
   │ - product    │
   │ - order      │
   │ - payment    │
   │ - notif(λ)   │
   │              │
   │ 2-3 replicas │
   │ HPA enabled  │
   └──────────────┘
```

---

## GitOps Workflow

### Standard Deployment (Automatic)
```
Feature Branch
    ↓ (Push)
main branch
    ↓ (Merge)
GitHub Actions builds: ecommerce/service:v1.0.0
    ↓ (Pushes image)
Container Registry
    ↓ (ArgoCD watches)
k8s/overlays/default/kustomization.yaml
    ↓ (Auto-sync enabled)
EKS Cluster
    ↓ (Pod restart)
New service version running
```

### Rollback (Git-based)
```
Issue detected
    ↓
git revert <commit>
    ↓
git push origin main
    ↓
ArgoCD auto-detects change
    ↓
Syncs to previous version
    ↓
Problem resolved
```

---

## Key Features Implemented

### 1. **Automated Synchronization** ✅
- Auto-sync enabled (continuous deployment)
- Drift detection and correction
- 3-minute reconciliation interval

### 2. **Configuration Management** ✅
- Single overlay for consistent configuration
- Environment-specific configurations via configmaps
- Different replicas and resource limits
- HPA configuration for critical services

### 3. **Role-Based Access Control** ✅
```yaml
Roles:
  - admin: Full access
  - developer: Can sync/view ecommerce apps
  - ops: Full access to ecommerce namespace
  - readonly: View-only access
```

### 4. **High Availability** ✅
- 2-3 replicas per service
- HPA for Order and Payment services
- Rolling updates with health checks
- Network policies for security

### 5. **GitOps Principles** ✅
- Git as single source of truth
- Declarative configuration
- Automated reconciliation
- Version control for all changes

---

## Installation & Setup

### Step 1: Install ArgoCD

```bash
# Using Kustomize from this repo
kubectl apply -k k8s/argocd/install/

# Or with kubectl directly
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### Step 2: Configure Git Repository

```bash
# Port-forward ArgoCD server
kubectl port-forward svc/argocd-server -n argocd 8443:443 &

# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# Login to CLI
argocd login localhost:8443 --username admin --password <password>

# Add Git repository
argocd repo add https://github.com/your-org/cloud-bigProject \
  --username <github-username> \
  --password <personal-access-token>
```

### Step 3: Deploy Root Application

```bash
# Create app-of-apps
kubectl apply -f k8s/argocd/app-of-apps.yaml

# Monitor deployment
argocd app get ecommerce-app-of-apps

# Wait for sync
argocd app wait ecommerce-app-of-apps --timeout 600s
```

### Step 4: Verify Deployment

```bash
# Check all applications
argocd app list

# Check status
argocd app get ecommerce-services

# Verify in cluster
kubectl get pods -n ecommerce
kubectl get deployments -n ecommerce
kubectl get hpa -n ecommerce
```

---

## File Locations

```
k8s/
├── argocd/
│   ├── install/                          # ArgoCD installation
│   │   ├── namespace.yaml
│   │   ├── argocd-cm.yaml
│   │   ├── argocd-rbac.yaml
│   │   └── kustomization.yaml
│   │
│   ├── app-of-apps.yaml                  # Root Application
│   │
│   └── apps/                              # Individual Applications
│       ├── ecommerce-services.yaml
│       └── observability.yaml
│
├── base/                                  # Base Kustomize configuration
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── *-deployment.yaml
│   ├── *-hpa.yaml
│   └── kustomization.yaml
│
└── overlays/
    └── default/                          # Standard overlay
        ├── kustomization.yaml
        ├── configmap.yaml
        └── networkpolicy.yaml

.gitops/
├── README.md          # Repository structure guide
└── WORKFLOW.md        # Complete GitOps workflow
```

---

## Deployment Flow Examples

### Example 1: Deploy (Standard)

```bash
# Developer makes change and pushes to main
git commit -am "feat: add new feature"
git push origin main

# GitHub Actions automatically:
# 1. Runs tests
# 2. Builds Docker image: ecommerce/service:v1.0.0
# 3. Pushes to registry

# ArgoCD automatically:
# 1. Detects Git change
# 2. Compares with cluster state
# 3. Finds new image tag
# 4. Syncs k8s/overlays/default
# 5. Updates pods with new image

# Result: New version running within 2-3 minutes
```

### Example 2: Rollback (Git-based)

```bash
# If issue found:
# Option 1: Revert commit
git revert <commit-hash>
git push origin main
# ArgoCD auto-syncs back

# Option 2: Manual rollback
argocd app rollback ecommerce-services 1
# Goes to previous revision

# Result: Previous version restored
```

---

## Best Practices

✅ **DO:**
- Use Kustomize overlays for configuration differences
- Commit all manifests to Git
- Use semantic versioning for releases
- Create detailed commit messages
- Use feature branches and PRs
- Test manifests locally before pushing
- Monitor metrics after deployment
- Use ArgoCD UI or CLI for visibility

❌ **DON'T:**
- Manually `kubectl apply` to cluster
- Commit secrets to Git
- Use `latest` tag in manifests
- Modify resources directly in cluster
- Skip code review process
- Deploy untested code
- Mix configurations in one directory

---

## Useful Commands

```bash
# List applications
argocd app list

# Get application status
argocd app get <app-name>

# Check what changed
argocd app diff <app-name>

# Sync application
argocd app sync <app-name>

# Force sync (overwrite local changes)
argocd app sync <app-name> --force

# Rollback to previous revision
argocd app rollback <app-name> 1

# Refresh from Git
argocd app refresh <app-name> --hard

# View application history
argocd app history <app-name>

# Wait for sync to complete
argocd app wait <app-name> --timeout 600s

# Get detailed status
kubectl get applications -n argocd -o wide
```

---

## Troubleshooting

### Application not syncing
```bash
# Check sync status
argocd app get ecommerce-services

# Force refresh from Git
argocd app refresh ecommerce-services --hard

# Force sync
argocd app sync ecommerce-services --force
```

### Image not updating
```bash
# Check kustomization.yaml
cat k8s/overlays/default/kustomization.yaml | grep images -A5

# Force pod restart
kubectl rollout restart deployment/api-gateway -n ecommerce
```

### Git repository not accessible
```bash
# List registered repos
argocd repo list

# Re-add if needed
argocd repo add https://github.com/your-org/cloud-bigProject \
  --username <user> --password <token>
```

---

## Summary

✅ **Complete ArgoCD Implementation includes:**
1. Installation manifests for ArgoCD
2. Kustomize overlay for configuration management
3. App-of-Apps pattern for managing multiple applications
4. RBAC configuration for different roles
5. Complete GitOps workflow documentation
6. Git repository structure guide
7. Examples and troubleshooting guide

✅ **You can now:**
- Deploy automatically (continuous deployment)
- Manage configurations from a single Git repo
- Rollback with a single Git revert
- Track all changes in Git history
- Enforce code review before deployment
- Monitor deployments in ArgoCD UI

**Next Steps:** Follow `.gitops/WORKFLOW.md` to start using the GitOps workflow!
