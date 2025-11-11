output "endpoint" {
  value       = aws_db_instance.main.endpoint
  description = "RDS endpoint address"
}

output "port" {
  value       = aws_db_instance.main.port
  description = "RDS port"
}

output "database_name" {
  value       = aws_db_instance.main.db_name
  description = "Database name"
}

output "resource_id" {
  value       = aws_db_instance.main.resource_id
  description = "RDS resource ID"
}

output "arn" {
  value       = aws_db_instance.main.arn
  description = "RDS ARN"
}
