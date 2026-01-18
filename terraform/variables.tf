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

variable "enabled_runners" {
  description = "List of enabled GitLab runners"
  type        = list(string)
  default     = []
}

variable "data_dir" {
  description = "Base directory for runner data"
  type        = string
  default     = "/srv/gitlab"
}

# Traefik Reverse Proxy Variables
variable "enable_traefik" {
  description = "Enable Traefik reverse proxy"
  type        = bool
  default     = false
}

variable "traefik_container_name" {
  description = "Name for the Traefik container"
  type        = string
  default     = "traefik"
}

variable "base_domain" {
  description = "Base domain for all services"
  type        = string
  default     = ""
}

variable "traefik_dashboard_enabled" {
  description = "Enable Traefik dashboard"
  type        = bool
  default     = true
}

variable "traefik_config_path" {
  description = "Host path for Traefik configuration"
  type        = string
  default     = "/srv/traefik"
}

variable "traefik_acme_path" {
  description = "Host path for Traefik ACME certificates"
  type        = string
  default     = "/srv/traefik/acme"
}
