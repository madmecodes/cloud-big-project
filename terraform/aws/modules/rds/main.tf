resource "aws_db_subnet_group" "main" {
  name       = "${var.instance_identifier}-subnet-group"
  subnet_ids = var.subnet_ids

  tags = {
    Name = "${var.instance_identifier}-subnet-group"
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.instance_identifier}-sg"
  description = "Security group for RDS"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.security_group_cidrs
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.instance_identifier}-sg"
  }
}

resource "aws_db_instance" "main" {
  identifier         = var.instance_identifier
  engine             = var.engine
  engine_version     = var.engine_version
  instance_class     = var.instance_class
  allocated_storage  = var.allocated_storage
  db_name            = var.db_name
  username           = var.username
  password           = var.password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible    = var.publicly_accessible
  multi_az               = var.multi_az
  backup_retention_period = var.backup_retention_days
  backup_window          = "03:00-04:00"
  maintenance_window     = "mon:04:00-mon:05:00"

  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.instance_identifier}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  enable_cloudwatch_logs_exports = ["postgresql"]
  copy_tags_to_snapshot          = true
  deletion_protection            = var.deletion_protection

  tags = merge(
    var.tags,
    {
      Name = var.instance_identifier
    }
  )
}

resource "aws_ssm_parameter" "rds_endpoint" {
  name  = "/ecommerce/rds/endpoint"
  type  = "String"
  value = aws_db_instance.main.endpoint

  tags = var.tags
}

resource "aws_ssm_parameter" "rds_password" {
  name  = "/ecommerce/rds/password"
  type  = "SecureString"
  value = var.password

  tags = var.tags
}
