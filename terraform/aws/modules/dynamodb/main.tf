resource "aws_dynamodb_table" "main" {
  for_each = var.tables

  name             = each.value.name
  billing_mode     = each.value.billing_mode
  hash_key         = each.value.hash_key
  range_key        = lookup(each.value, "range_key", null)

  dynamic "attribute" {
    for_each = each.value.attributes
    content {
      name = attribute.value.name
      type = attribute.value.type
    }
  }

  ttl {
    attribute_name = each.value.ttl_attribute
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = merge(
    var.tags,
    {
      Name = each.value.name
    }
  )
}
