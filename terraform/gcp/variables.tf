variable "gcp_project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "ecommerce"
}

variable "environment" {
  description = "Environment"
  type        = string
  default     = "dev"
}

variable "subnet_cidr" {
  description = "Subnet CIDR range"
  type        = string
  default     = "10.0.0.0/24"
}

variable "dataproc_master_machine_type" {
  description = "Dataproc master machine type"
  type        = string
  default     = "n1-standard-2"
}

variable "dataproc_worker_machine_type" {
  description = "Dataproc worker machine type"
  type        = string
  default     = "n1-standard-2"
}

variable "dataproc_worker_count" {
  description = "Number of Dataproc worker nodes"
  type        = number
  default     = 2
}

variable "dataproc_boot_disk_size_gb" {
  description = "Boot disk size for Dataproc nodes"
  type        = number
  default     = 50
}

variable "force_destroy_buckets" {
  description = "Force destroy GCS buckets even if not empty"
  type        = bool
  default     = true
}

variable "create_cloud_sql" {
  description = "Create Cloud SQL instance for analytics"
  type        = bool
  default     = false
}

variable "cloud_sql_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-f1-micro"
}
