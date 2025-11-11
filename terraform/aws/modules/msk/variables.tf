variable "cluster_name" {
  type        = string
  description = "MSK cluster name"
}

variable "environment" {
  type        = string
  description = "Environment name"
}

variable "kafka_version" {
  type        = string
  description = "Kafka version"
  default     = "3.5.1"
}

variable "number_of_brokers" {
  type        = number
  description = "Number of broker nodes"
  default     = 3
}

variable "instance_type" {
  type        = string
  description = "Broker instance type"
  default     = "kafka.t3.small"
}

variable "ebs_storage_size" {
  type        = number
  description = "EBS storage per broker in GB"
  default     = 100
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "client_subnets" {
  type        = list(string)
  description = "List of client subnets"
}

variable "security_group_cidrs" {
  type        = list(string)
  description = "CIDR blocks for security group"
}

variable "cloudwatch_logs_enabled" {
  type        = bool
  description = "Enable CloudWatch logs"
  default     = true
}

variable "s3_logs_enabled" {
  type        = bool
  description = "Enable S3 logs"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
