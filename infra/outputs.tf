output "ecr_repository_url" {
  description = "Repository URL to use when tagging and pushing the API image."
  value       = aws_ecr_repository.sentiment_api.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.demo.name
}

output "ecs_service_name" {
  value = aws_ecs_service.api.name
}

output "cloudwatch_log_group" {
  value = aws_cloudwatch_log_group.api.name
}
