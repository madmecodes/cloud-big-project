variable "buckets" {
  type = map(object({
    name          = string
    versioning    = bool
    encryption    = bool
    public_access = bool
  }))
  description = "S3 buckets configuration"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
