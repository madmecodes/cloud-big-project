# PointA: Infrastructure as Code with Terraform

## Overview
All cloud infrastructure across AWS, GCP, and Confluent Cloud is provisioned exclusively using **Terraform** as the Infrastructure as Code platform.

---

## 1. Terraform Modules

**AWS Modules** (`terraform/aws/modules/`):
- **alb**: Application Load Balancer for API Gateway
- **dynamodb**: 5 NoSQL tables (orders, payments, sessions, carts, notifications)
- **eks**: Kubernetes cluster with node groups and RBAC
- **lambda**: Serverless functions for event processing
- **msk**: Managed Streaming for Kafka (switched to confluent)
- **rds**: PostgreSQL database
- **s3**: 3 object storage buckets
- **vpc**: VPC, subnets, security groups, and routing

**GCP Modules** (`terraform/gcp/modules/`):
- **cloud_storage**: GCS buckets for data
- **dataproc**: Spark/PySpark cluster for analytics

**Configuration Files**:
- `terraform/aws/main.tf`: Orchestrates all AWS modules
- `terraform/aws/variables.tf`: Variable definitions
- `terraform/aws/terraform.tfvars`: Variable values
- `terraform/gcp/main.tf`: Orchestrates all GCP modules
- `terraform/gcp/variables.tf`: Variable definitions
- `terraform/gcp/terraform.tfvars`: Variable values

See: [`terraform/aws/modules/`](./terraform/aws/modules/) and [`terraform/gcp/modules/`](./terraform/gcp/modules/)

---

## 2. How to Use Terraform

### Step 1: Initialize
```bash
cd terraform/aws/
terraform init
```

### Step 2: Set Variables
```bash
# terraform.tfvars
aws_region = "ap-south-1"
gcp_project = "your-gcp-project"
```

### Step 3: Plan
```bash
terraform plan -out=tfplan
```

### Step 4: Apply
```bash
terraform apply tfplan
```

### Step 5: Verify
```bash
terraform state list
terraform output
```

---

## 3. Repository Structure

```
terraform/
├── aws/
│   ├── main.tf
│   ├── variables.tf
│   ├── terraform.tfvars
│   └── modules/
│       ├── alb/
│       ├── dynamodb/
│       ├── eks/
│       ├── lambda/
│       ├── msk/
│       ├── rds/
│       ├── s3/
│       └── vpc/
│
└── gcp/
    ├── main.tf
    ├── variables.tf
    ├── terraform.tfvars
    └── modules/
        ├── cloud_storage/
        └── dataproc/
```

---

## 4. Key Terraform Commands

| Command | Purpose |
|---------|---------|
| `terraform init` | Initialize Terraform working directory |
| `terraform plan` | Preview infrastructure changes |
| `terraform apply` | Apply infrastructure changes |
| `terraform destroy` | Destroy all managed infrastructure |
| `terraform state list` | List all managed resources |
| `terraform output` | Display output values |

---