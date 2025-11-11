variable "function_name" {
  type        = string
  description = "Lambda function name"
}

variable "handler" {
  type        = string
  description = "Lambda handler"
}

variable "runtime" {
  type        = string
  description = "Lambda runtime"
}

variable "timeout" {
  type        = number
  description = "Lambda timeout in seconds"
  default     = 60
}

variable "memory_size" {
  type        = number
  description = "Lambda memory size in MB"
  default     = 128
}

variable "vpc_subnet_ids" {
  type        = list(string)
  description = "VPC subnet IDs"
  default     = []
}

variable "vpc_security_group_ids" {
  type        = list(string)
  description = "VPC security group IDs"
  default     = []
}

variable "environment_variables" {
  type        = map(string)
  description = "Environment variables"
  default     = {}
}

variable "policies" {
  type        = list(string)
  description = "IAM policies (JSON)"
  default     = []
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
