resource "aws_iam_role" "lambda" {
  name = "${var.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_policies" {
  count  = length(var.policies)
  name   = "${var.function_name}-policy-${count.index}"
  role   = aws_iam_role.lambda.id
  policy = var.policies[count.index]
}

resource "aws_iam_role_policy_attachment" "vpc_execution" {
  count              = length(var.vpc_subnet_ids) > 0 ? 1 : 0
  role               = aws_iam_role.lambda.name
  policy_arn         = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_lambda_function" "main" {
  filename         = "lambda_placeholder.zip"
  function_name    = var.function_name
  role             = aws_iam_role.lambda.arn
  handler          = var.handler
  runtime          = var.runtime
  timeout          = var.timeout
  memory_size      = var.memory_size

  vpc_config {
    subnet_ids         = var.vpc_subnet_ids
    security_group_ids = var.vpc_security_group_ids
  }

  environment {
    variables = var.environment_variables
  }

  tags = merge(
    var.tags,
    {
      Name = var.function_name
    }
  )
}
