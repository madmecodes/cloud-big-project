output "function_arn" {
  value       = aws_lambda_function.main.arn
  description = "Lambda function ARN"
}

output "function_name" {
  value       = aws_lambda_function.main.function_name
  description = "Lambda function name"
}

output "role_arn" {
  value       = aws_iam_role.lambda.arn
  description = "Lambda IAM role ARN"
}
