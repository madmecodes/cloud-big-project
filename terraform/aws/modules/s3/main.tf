resource "aws_s3_bucket" "main" {
  for_each = var.buckets

  bucket = each.value.name

  tags = merge(
    var.tags,
    {
      Name = each.value.name
    }
  )
}

resource "aws_s3_bucket_versioning" "main" {
  for_each = { for k, v in var.buckets : k => v if v.versioning }

  bucket = aws_s3_bucket.main[each.key].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  for_each = { for k, v in var.buckets : k => v if v.encryption }

  bucket = aws_s3_bucket.main[each.key].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "main" {
  for_each = var.buckets

  bucket = aws_s3_bucket.main[each.key].id

  block_public_acls       = !each.value.public_access
  block_public_policy     = !each.value.public_access
  ignore_public_acls      = !each.value.public_access
  restrict_public_buckets = !each.value.public_access
}
