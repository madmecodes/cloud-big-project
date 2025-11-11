variable "name" {
  type        = string
  description = "ALB name"
}

variable "environment" {
  type        = string
  description = "Environment name"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs"
}

variable "enable_deletion_protection" {
  type        = bool
  description = "Enable deletion protection"
  default     = false
}

variable "enable_http2" {
  type        = bool
  description = "Enable HTTP/2"
  default     = true
}

variable "enable_cross_zone_lb" {
  type        = bool
  description = "Enable cross-zone load balancing"
  default     = true
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN for HTTPS"
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
