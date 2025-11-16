# GitOps Repository Structure

This document explains the Git repository structure for managing the E-Commerce platform using ArgoCD GitOps principles.

## Overview

The repository is organized into distinct directories following GitOps best practices:

```
cloud-bigProject/
├── k8s/
│   ├── base/                      # Base Kustomize configuration
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   ├── secrets.yaml
│   │   ├── *-deployment.yaml      # All service deployments
│   │   ├── *-hpa.yaml             # HPA configurations
│   │   ├── prometheus-deployment.yaml
│   │   ├── grafana-deployment.yaml
│   │   └── kustomization.yaml
│   │
│   ├── overlays/
│   │   └── default/               # Standard configuration
│   │       ├── kustomization.yaml
│   │       ├── configmap.yaml
│   │       └── networkpolicy.yaml
│   │
│   └── argocd/
│       ├── install/               # ArgoCD installation files
│       │   ├── namespace.yaml
│       │   ├── argocd-cm.yaml
│       │   ├── argocd-rbac.yaml
│       │   └── kustomization.yaml
│       │
│       ├── app-of-apps.yaml       # Root Application (manages all apps)
│       │
│       └── apps/                  # Individual Application definitions
│           ├── ecommerce-services.yaml
│           └── observability.yaml
│
├── services/                      # Microservices source code
│   ├── api-gateway/
│   ├── user-service/
│   ├── product-service/
│   ├── order-service/
│   ├── payment-service/
│   └── notification-lambda/
│
├── terraform/                     # Infrastructure as Code
│   ├── aws/
│   └── gcp/
│
├── load-tests/
│   └── k6/
│
└── .gitops/
    ├── README.md                  # This file
    └── WORKFLOW.md                # GitOps workflow guide
```

## Key Principles

### 1. **Declarative Configuration**
- All desired state is declared in Git
- Kubernetes manifests are the source of truth
- No manual `kubectl apply` commands
- All changes go through Git commits

### 2. **Git as Source of Truth**
- Application state is versioned
- Full audit trail via Git history
- Easy rollback by reverting commits
- Code review process for deployments

### 3. **Automated Synchronization**
- ArgoCD automatically syncs Git state to cluster
- Drift detection and correction
- No manual deployment steps
- Continuous reconciliation

## Branch Strategy

```
main (stable)
  ├─ Release branches (release/v1.0.0, release/v1.1.0)
  ├─ Feature branches (feature/new-service)
  └─ Hotfix branches (hotfix/critical-bug)
```

### Main Branch
- Protected branch (requires PR review)
- Stable, tagged releases
- Manual or automatic deployments
- Production-ready code

## File Organization

### Base Configuration (`k8s/base/`)
- Shared Kubernetes manifests
- All services deployed the same way
- Common ConfigMaps and Secrets
- Prometheus and Grafana definitions

**Usage:** Base is NOT deployed directly; it's extended by overlays.

### Configuration Overlay (`k8s/overlays/default/`)

```
kustomization.yaml    # Kustomize configuration
  ├─ Extends: ../../base
  ├─ Namespace: ecommerce
  ├─ Replicas: 2-3 per service (High Availability)
  ├─ Images: v1.0.0 (specific versions)
  ├─ HPA: Enabled (min: 3, max: 15-20)
  ├─ Resources: High limits
  └─ Policies: Network policies enabled
```

**Deploy:** `kubectl apply -k overlays/default/`

## ArgoCD Application Structure

### App-of-Apps Pattern
```
Root Application (ecommerce-app-of-apps)
  ├─ ecommerce-services (Microservices)
  ├─ observability (Prometheus/Grafana)
  └─ gitops-tools
```

### Individual Application (`k8s/argocd/apps/ecommerce-services.yaml`)
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ecommerce-services
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/your-org/cloud-bigProject
    targetRevision: main
    path: k8s/overlays/default      # Path to Kustomize overlay

  destination:
    server: https://kubernetes.default.svc
    namespace: ecommerce

  syncPolicy:
    automated:
      prune: true              # Delete resources not in Git
      selfHeal: true           # Auto-sync every 3 minutes
```

## Deployment Flow

### Standard Deployment
```
1. Developer commits code and manifests to main branch
2. GitHub Actions builds Docker image with tag 'v1.0.0'
3. Pushes image to registry
4. ArgoCD detects Git change in main
5. ArgoCD syncs `k8s/overlays/default` to EKS cluster
6. Services restart with new image
7. Health checks verify deployment success
```

## Image Tagging Strategy

### Release Images
```
ecommerce/api-gateway:v1.0.0
ecommerce/user-service:v1.0.0
```
- Tagged with semantic version
- Immutable (never overwritten)
- Explicitly updated in `kustomization.yaml`

## ConfigMap and Secret Management

### ConfigMaps (Non-sensitive)
Located in `k8s/overlays/default/`

**ConfigMap:**
```yaml
env-config:
  ENVIRONMENT: production
  LOG_LEVEL: info
  CACHE_TTL: 3600
```

### Secrets (Sensitive Data)
**DO NOT** commit secrets to Git!

Instead:
1. Use external secret management (AWS Secrets Manager, GCP Secret Manager)
2. Use Sealed Secrets or External Secrets operator
3. Reference secrets from cluster

**Example with External Secrets Operator:**
```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
```

## Syncing and Monitoring

### Manual Sync
```bash
# Sync specific application
argocd app sync ecommerce-services

# Sync with prune
argocd app sync ecommerce-services --prune

# Force refresh
argocd app refresh ecommerce-services --hard
```

### Auto Sync Status
```bash
# Check application status
argocd app get ecommerce-services

# Watch for changes
argocd app wait ecommerce-services

# Get detailed diff
argocd app diff ecommerce-services
```

## Troubleshooting

### Application Out of Sync
```bash
# Check diff
argocd app diff ecommerce-services

# Show detailed status
argocd app get ecommerce-services

# Force sync
argocd app sync ecommerce-services --force
```

### Rollback
```bash
# Rollback to previous revision
git revert <commit-hash>
git push origin main

# ArgoCD will automatically sync to previous state
```

### Debugging Kustomize
```bash
# See what Kustomize will generate
kubectl kustomize k8s/overlays/default

# Apply with validation
kubectl apply -k k8s/overlays/default --dry-run=client

# Apply with server-side validation
kubectl apply -k k8s/overlays/default --dry-run=server
```

## Best Practices

✅ **DO:**
- Commit all manifests to Git
- Use feature branches for changes
- Tag releases
- Use Kustomize overlays for configuration
- Create detailed commit messages
- Request code review before merge
- Test manifests locally before pushing
- Use `.gitignore` for sensitive files

❌ **DON'T:**
- Use `kubectl apply` directly for deployments
- Manually edit resources in cluster
- Commit secrets to Git
- Use `latest` tags in manifests
- Skip code review process
- Deploy without Git history
- Manually modify ArgoCD applications

## Useful Commands

```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Access ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8443:443

# Login to ArgoCD CLI
argocd login localhost:8443

# List applications
argocd app list

# Get app status
argocd app get ecommerce-services

# Sync all applications
argocd app sync ecommerce-app-of-apps

# Watch sync progress
watch argocd app get ecommerce-app-of-apps
```

See `WORKFLOW.md` for detailed GitOps workflow documentation.
