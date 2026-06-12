resource "aws_ssm_parameter" "database_url" {
  name  = "/${local.name_prefix}/database_url"
  type  = "SecureString"
  value = var.database_url

  tags = local.common_tags
}

resource "aws_ssm_parameter" "client_token_secret" {
  name  = "/${local.name_prefix}/client_token_secret"
  type  = "SecureString"
  value = var.client_token_secret

  tags = local.common_tags
}

resource "aws_ssm_parameter" "room_code_secret" {
  name  = "/${local.name_prefix}/room_code_secret"
  type  = "SecureString"
  value = var.room_code_secret

  tags = local.common_tags
}

resource "aws_iam_role_policy" "ecs_execution_ssm" {
  name = "${local.name_prefix}-ecs-ssm"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ssm:GetParameters",
        "ssm:GetParameter"
      ]
      Resource = [
        aws_ssm_parameter.database_url.arn,
        aws_ssm_parameter.client_token_secret.arn,
        aws_ssm_parameter.room_code_secret.arn,
      ]
    }]
  })
}
