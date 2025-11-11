output "table_names" {
  value = {
    for k, v in aws_dynamodb_table.main : k => v.name
  }
  description = "DynamoDB table names"
}

output "table_arns" {
  value = {
    for k, v in aws_dynamodb_table.main : k => v.arn
  }
  description = "DynamoDB table ARNs"
}
