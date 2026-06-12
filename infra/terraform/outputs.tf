output "alb_dns_name" {
  description = "Public URL for the app"
  value       = "http://${aws_lb.app.dns_name}"
}

output "api_url" {
  value = "http://${aws_lb.app.dns_name}/api/v1"
}

output "ws_url" {
  value = "ws://${aws_lb.app.dns_name}/ws"
}

output "backend_ecr_repository" {
  value = aws_ecr_repository.backend.repository_url
}

output "frontend_ecr_repository" {
  value = aws_ecr_repository.frontend.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.app.name
}

output "backend_service_name" {
  value = aws_ecs_service.backend.name
}

output "frontend_service_name" {
  value = aws_ecs_service.frontend.name
}

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC (set as AWS_DEPLOY_ROLE_ARN variable)"
  value       = aws_iam_role.github_actions.arn
}
