#!/bin/bash

# Submit Flink analytics job to GCP Dataproc

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"your-project-id"}
CLUSTER_NAME=${CLUSTER_NAME:-"ecommerce-analytics"}
REGION=${GCP_REGION:-"us-central1"}
JOB_NAME="ecommerce-analytics-job"
BOOTSTRAP_SERVERS=${KAFKA_BOOTSTRAP_SERVERS:-"msk-kafka-cluster:9092"}

echo "Submitting Flink job to Dataproc..."
echo "Project: $PROJECT_ID"
echo "Cluster: $CLUSTER_NAME"
echo "Region: $REGION"
echo "Kafka Bootstrap Servers: $BOOTSTRAP_SERVERS"

# Build Python package
echo "Building Python package..."
cd "$(dirname "$0")"
python -m pip install -r requirements.txt

# Package the job
echo "Packaging Flink job..."
zip -r flink-job.zip main.py requirements.txt

# Upload to GCS
echo "Uploading to GCS..."
gsutil cp flink-job.zip "gs://ecommerce-flink-code-bucket/"

# Submit job
echo "Submitting job to Dataproc..."
gcloud dataproc jobs submit pyspark \
  --cluster="$CLUSTER_NAME" \
  --region="$REGION" \
  --jars="gs://ecommerce-flink-code-bucket/flink-job.zip" \
  --py-files="gs://ecommerce-flink-code-bucket/flink-job.zip" \
  main.py \
  --BOOTSTRAP_SERVERS="$BOOTSTRAP_SERVERS"

echo "Job submitted successfully!"
echo "Job name: $JOB_NAME"
echo ""
echo "To check job status, run:"
echo "gcloud dataproc jobs list --cluster=$CLUSTER_NAME --region=$REGION"
