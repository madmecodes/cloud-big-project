terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment for remote state storage
  # backend "s3" {
  #   bucket         = "ecommerce-terraform-state"
  #   key            = "aws/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = "ecommerce-platform"
      ManagedBy   = "Terraform"
    }
  }
}

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  project_name          = var.project_name
  environment           = var.environment
  aws_region            = var.aws_region
  vpc_cidr              = var.vpc_cidr
  availability_zones    = var.availability_zones
  private_subnet_cidrs  = var.private_subnet_cidrs
  public_subnet_cidrs   = var.public_subnet_cidrs
  enable_nat_gateway    = true
  single_nat_gateway    = var.single_nat_gateway
}

# EKS Module
module "eks" {
  source = "./modules/eks"

  cluster_name           = var.eks_cluster_name
  environment            = var.environment
  kubernetes_version     = var.kubernetes_version
  vpc_id                 = module.vpc.vpc_id
  subnet_ids             = concat(module.vpc.private_subnet_ids, module.vpc.public_subnet_ids)

  node_groups = var.node_groups

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# RDS Module
module "rds" {
  source = "./modules/rds"

  instance_identifier      = "${var.project_name}-db"
  engine                   = "postgres"
  engine_version           = "15.15"
  instance_class           = var.rds_instance_class
  allocated_storage         = var.rds_storage_gb
  db_name                  = "ecommerce"
  username                 = var.db_username
  password                 = var.db_password
  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnet_ids

  backup_retention_days    = 30
  multi_az                 = var.rds_multi_az
  publicly_accessible      = false
  skip_final_snapshot      = var.skip_final_snapshot

  security_group_cidrs = [var.vpc_cidr]

  tags = {
    Environment = var.environment
  }
}

# DynamoDB Module
module "dynamodb" {
  source = "./modules/dynamodb"

  tables = {
    sessions = {
      name           = "${var.project_name}-sessions"
      billing_mode   = "PAY_PER_REQUEST"
      hash_key       = "session_id"
      ttl_attribute  = "expires_at"
      attributes = [
        { name = "session_id", type = "S" }
      ]
    }

    carts = {
      name           = "${var.project_name}-carts"
      billing_mode   = "PAY_PER_REQUEST"
      hash_key       = "user_id"
      range_key      = "product_id"
      ttl_attribute  = "expires_at"
      attributes = [
        { name = "user_id", type = "S" },
        { name = "product_id", type = "S" }
      ]
    }

    orders = {
      name           = "${var.project_name}-orders"
      billing_mode   = "PAY_PER_REQUEST"
      hash_key       = "id"
      ttl_attribute  = null
      attributes = [
        { name = "id", type = "S" }
      ]
    }

    payments = {
      name           = "${var.project_name}-payments"
      billing_mode   = "PAY_PER_REQUEST"
      hash_key       = "id"
      ttl_attribute  = null
      attributes = [
        { name = "id", type = "S" }
      ]
    }
  }

  tags = {
    Environment = var.environment
  }
}

# S3 Module
module "s3" {
  source = "./modules/s3"

  buckets = {
    product_images = {
      name           = "${var.project_name}-product-images-${data.aws_caller_identity.current.account_id}"
      versioning     = true
      encryption     = true
      public_access  = false
    }

    order_documents = {
      name           = "${var.project_name}-order-documents-${data.aws_caller_identity.current.account_id}"
      versioning     = true
      encryption     = true
      public_access  = false
    }

    analytics_results = {
      name           = "${var.project_name}-analytics-results-${data.aws_caller_identity.current.account_id}"
      versioning     = false
      encryption     = true
      public_access  = false
    }
  }

  tags = {
    Environment = var.environment
  }
}

# MSK (Managed Kafka) Module
module "msk" {
  source = "./modules/msk"

  cluster_name              = "${var.project_name}-kafka"
  environment               = var.environment
  kafka_version             = "3.5.1"
  number_of_brokers         = var.msk_broker_count
  instance_type             = var.msk_instance_type
  ebs_storage_size          = var.msk_ebs_storage_gb
  vpc_id                    = module.vpc.vpc_id
  client_subnets            = module.vpc.private_subnet_ids
  security_group_cidrs      = [var.vpc_cidr]
  cloudwatch_logs_enabled   = true
  s3_logs_enabled           = false

  tags = {
    Environment = var.environment
  }

  depends_on = [module.vpc]
}

# Lambda IAM Role
module "lambda_role" {
  source = "./modules/lambda"

  function_name          = "${var.project_name}-notification"
  handler                = "index.handler"
  runtime                = "python3.11"
  vpc_subnet_ids         = module.vpc.private_subnet_ids
  vpc_security_group_ids = [aws_security_group.lambda_sg.id]

  environment_variables = {
    KAFKA_BROKERS = module.msk.bootstrap_servers
    SNS_TOPIC_ARN = aws_sns_topic.notifications.arn
  }

  policies = [
    jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          Action = [
            "ec2:CreateNetworkInterface",
            "ec2:DescribeNetworkInterfaces",
            "ec2:DeleteNetworkInterface"
          ]
          Resource = "*"
        },
        {
          Effect = "Allow"
          Action = [
            "sns:Publish"
          ]
          Resource = aws_sns_topic.notifications.arn
        }
      ]
    })
  ]

  tags = {
    Environment = var.environment
  }

  depends_on = [module.msk, module.vpc]
}

# Application Load Balancer Module
module "alb" {
  source = "./modules/alb"

  name               = "${var.project_name}-alb"
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.public_subnet_ids
  security_group_ids = [aws_security_group.alb_sg.id]

  enable_deletion_protection = var.alb_deletion_protection
  enable_http2               = true
  enable_cross_zone_lb       = true

  # Add target groups later via Kubernetes service LoadBalancer

  tags = {
    Environment = var.environment
  }

  depends_on = [module.vpc]
}

# Security Groups
resource "aws_security_group" "alb_sg" {
  name        = "${var.project_name}-alb-sg"
  description = "Security group for ALB"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-alb-sg"
  }
}

resource "aws_security_group" "lambda_sg" {
  name        = "${var.project_name}-lambda-sg"
  description = "Security group for Lambda functions"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-lambda-sg"
  }
}

# SNS Topic for Notifications
resource "aws_sns_topic" "notifications" {
  name              = "${var.project_name}-notifications"
  kms_master_key_id = "alias/aws/sns"

  tags = {
    Environment = var.environment
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

# Outputs
output "vpc_id" {
  value       = module.vpc.vpc_id
  description = "VPC ID"
}

output "eks_cluster_name" {
  value       = module.eks.cluster_name
  description = "EKS Cluster Name"
}

output "eks_cluster_endpoint" {
  value       = module.eks.cluster_endpoint
  description = "EKS Cluster Endpoint"
}

output "rds_endpoint" {
  value       = module.rds.endpoint
  description = "RDS Database Endpoint"
  sensitive   = true
}

output "msk_bootstrap_servers" {
  value       = module.msk.bootstrap_servers
  description = "MSK Bootstrap Servers"
}

output "s3_bucket_names" {
  value = {
    for k, v in module.s3.bucket_ids : k => v
  }
  description = "S3 Bucket Names"
}

output "dynamodb_table_names" {
  value = {
    for k, v in module.dynamodb.table_names : k => v
  }
  description = "DynamoDB Table Names"
}

output "alb_dns_name" {
  value       = module.alb.load_balancer_dns_name
  description = "ALB DNS Name"
}

output "sns_topic_arn" {
  value       = aws_sns_topic.notifications.arn
  description = "SNS Topic ARN for notifications"
}
