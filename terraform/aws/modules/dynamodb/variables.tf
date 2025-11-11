variable "tables" {
  type = map(object({
    name           = string
    billing_mode   = string
    hash_key       = string
    range_key      = optional(string)
    ttl_attribute  = string
    attributes     = list(object({
      name = string
      type = string
    }))
  }))
  description = "DynamoDB tables configuration"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
