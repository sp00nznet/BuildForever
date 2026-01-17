output "gitlab_url" {
  description = "GitLab URL"
  value       = "https://${var.gitlab_domain}"
}

output "gitlab_container_id" {
  description = "GitLab container ID"
  value       = docker_container.gitlab.id
}

output "gitlab_ssh_port" {
  description = "GitLab SSH port"
  value       = 2222
}

output "status" {
  description = "Deployment status"
  value       = "GitLab deployed successfully"
}
