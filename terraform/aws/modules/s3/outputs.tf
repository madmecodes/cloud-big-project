output "bucket_ids" {
  value = {
    for k, v in aws_s3_bucket.main : k => v.id
  }
  description = "S3 bucket IDs"
}

output "bucket_arns" {
  value = {
    for k, v in aws_s3_bucket.main : k => v.arn
  }
  description = "S3 bucket ARNs"
}
