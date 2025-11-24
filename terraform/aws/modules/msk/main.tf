resource "aws_security_group" "msk" {
  name        = "${var.cluster_name}-sg"
  description = "Security group for MSK"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Allow public access for cross-cloud connectivity
    description = "Kafka PLAINTEXT from anywhere (for GCP Dataproc)"
  }

  ingress {
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Allow public access for cross-cloud connectivity
    description = "Kafka TLS from anywhere"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.cluster_name}-sg"
  }
}

resource "aws_msk_cluster" "main" {
  cluster_name           = var.cluster_name
  kafka_version          = var.kafka_version
  number_of_broker_nodes = var.number_of_brokers
  broker_node_group_info {
    instance_type   = var.instance_type
    storage_info {
      ebs_storage_info {
        volume_size = var.ebs_storage_size
      }
    }
    client_subnets  = var.client_subnets
    security_groups = [aws_security_group.msk.id]

    connectivity_info {
      public_access {
        type = "SERVICE_PROVIDED_EIPS"
      }
    }
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"  # Required for public access
      in_cluster    = true
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = var.cloudwatch_logs_enabled
        log_group = aws_cloudwatch_log_group.msk[0].name
      }
      firehose {
        enabled = false
      }
      s3 {
        enabled = var.s3_logs_enabled
      }
    }
  }

  tags = merge(
    var.tags,
    {
      Name = var.cluster_name
    }
  )
}

resource "aws_cloudwatch_log_group" "msk" {
  count             = var.cloudwatch_logs_enabled ? 1 : 0
  name              = "/aws/msk/${var.cluster_name}"
  retention_in_days = 7

  tags = var.tags
}
