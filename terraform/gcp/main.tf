terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

resource "google_project_service" "required_apis" {
  for_each = toset([
    "compute.googleapis.com",
    "container.googleapis.com",
    "dataproc.googleapis.com",
    "storage.googleapis.com",
    "sqladmin.googleapis.com",
    "cloudresourcemanager.googleapis.com"
  ])

  service            = each.value
  disable_on_destroy = false
}

# VPC Network for Dataproc
resource "google_compute_network" "main" {
  name                    = "${var.project_name}-network"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

# Subnet for Dataproc
resource "google_compute_subnetwork" "main" {
  name          = "${var.project_name}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.gcp_region
  network       = google_compute_network.main.id
  private_ip_google_access = true
}

# Cloud Storage Bucket for Flink Job Code
resource "google_storage_bucket" "flink_code" {
  name          = "${var.project_name}-flink-code-${data.google_client_config.current.project}"
  location      = var.gcp_region
  force_destroy = var.force_destroy_buckets

  uniform_bucket_level_access = true

  lifecycle {
    ignore_changes = [uniform_bucket_level_access]
  }

  labels = {
    environment = var.environment
    project     = var.project_name
  }
}

# Cloud Storage Bucket for Analytics Results
resource "google_storage_bucket" "analytics_results" {
  name          = "${var.project_name}-analytics-results-${data.google_client_config.current.project}"
  location      = var.gcp_region
  force_destroy = var.force_destroy_buckets

  uniform_bucket_level_access = true

  lifecycle {
    ignore_changes = [uniform_bucket_level_access]
  }

  labels = {
    environment = var.environment
    project     = var.project_name
  }
}

# GKE Cluster for Dataproc (will host Flink)
resource "google_dataproc_cluster" "analytics" {
  name       = "${var.project_name}-analytics"
  region     = var.gcp_region
  graceful_decommission_timeout = "0s"

  cluster_config {
    staging_bucket = google_storage_bucket.flink_code.name

    master_config {
      num_instances = 1
      machine_type  = var.dataproc_master_machine_type
      disk_config {
        boot_disk_size_gb = var.dataproc_boot_disk_size_gb
      }
    }

    worker_config {
      num_instances = var.dataproc_worker_count
      machine_type  = var.dataproc_worker_machine_type
      disk_config {
        boot_disk_size_gb = var.dataproc_boot_disk_size_gb
      }
    }

    software_config {
      image_version = "2.1-debian11"
      override_properties = {
        "dataproc:dataproc.allow.zero.workers" = "true"
      }

      optional_components = [
        "PYTHON3",
        "JUPYTER",
        "DOCKER",
        "HIVE_WEBHCAT"
      ]
    }

    gce_cluster_config {
      subnetwork        = google_compute_subnetwork.main.id
      internal_ip_only  = false
      service_account_scopes = [
        "https://www.googleapis.com/auth/cloud-platform"
      ]

      tags = [
        "${var.project_name}-dataproc"
      ]
    }

    endpoint_config {
      enable_http_port_access = true
    }
  }

  depends_on = [
    google_project_service.required_apis
  ]

  labels = {
    environment = var.environment
    project     = var.project_name
  }
}

# IAM Service Account for Flink Jobs
resource "google_service_account" "flink" {
  account_id   = "${var.project_name}-flink"
  display_name = "Service Account for Flink Jobs"
}

# Grant permissions to Flink service account
resource "google_project_iam_member" "flink_permissions" {
  for_each = toset([
    "roles/storage.admin",
    "roles/dataproc.worker",
    "roles/dataproc.editor"
  ])

  project = var.gcp_project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.flink.email}"
}

# Cloud SQL Instance (Optional - for backup analytics data)
resource "google_sql_database_instance" "analytics_db" {
  count             = var.create_cloud_sql ? 1 : 0
  name              = "${var.project_name}-analytics-db"
  database_version  = "POSTGRES_15"
  region            = var.gcp_region
  deletion_protection = false

  settings {
    tier              = var.cloud_sql_tier
    availability_type = "ZONAL"
    backup_configuration {
      enabled = true
    }
    ip_configuration {
      require_ssl = false
    }
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_sql_database" "analytics" {
  count    = var.create_cloud_sql ? 1 : 0
  name     = "analytics"
  instance = google_sql_database_instance.analytics_db[0].name
}

# Data source for current GCP config
data "google_client_config" "current" {}

# Outputs
output "dataproc_cluster_name" {
  value       = google_dataproc_cluster.analytics.name
  description = "Dataproc cluster name"
}

output "dataproc_cluster_endpoint" {
  value       = "https://${google_dataproc_cluster.analytics.name}-m:8088"
  description = "Dataproc cluster endpoint"
}

output "flink_code_bucket_name" {
  value       = google_storage_bucket.flink_code.name
  description = "GCS bucket for Flink code"
}

output "analytics_results_bucket_name" {
  value       = google_storage_bucket.analytics_results.name
  description = "GCS bucket for analytics results"
}

output "flink_service_account_email" {
  value       = google_service_account.flink.email
  description = "Service account email for Flink jobs"
}

output "cloud_sql_instance_name" {
  value       = var.create_cloud_sql ? google_sql_database_instance.analytics_db[0].name : null
  description = "Cloud SQL instance name"
}

output "cloud_sql_connection_name" {
  value       = var.create_cloud_sql ? google_sql_database_instance.analytics_db[0].connection_name : null
  description = "Cloud SQL connection name for app connections"
}
