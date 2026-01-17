variable "docker_host" {
  description = "Docker host connection string"
  type        = string
  default     = "unix:///var/run/docker.sock"
}

variable "gitlab_container_name" {
  description = "Name for the GitLab container"
  type        = string
  default     = "gitlab"
}

variable "gitlab_domain" {
  description = "Domain for GitLab instance"
  type        = string
}

variable "admin_password" {
  description = "GitLab root admin password"
  type        = string
  sensitive   = true
}

variable "letsencrypt_email" {
  description = "Email for Let's Encrypt SSL certificate"
  type        = string
}

variable "enable_letsencrypt" {
  description = "Enable Let's Encrypt automatic SSL"
  type        = bool
  default     = true
}

variable "gitlab_config_path" {
  description = "Host path for GitLab configuration"
  type        = string
  default     = "/srv/gitlab/config"
}

variable "gitlab_logs_path" {
  description = "Host path for GitLab logs"
  type        = string
  default     = "/srv/gitlab/logs"
}

variable "gitlab_data_path" {
  description = "Host path for GitLab data"
  type        = string
  default     = "/srv/gitlab/data"
}
