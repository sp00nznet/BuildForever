terraform {
  required_version = ">= 1.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {
  host = var.docker_host
}

# GitLab Container
resource "docker_image" "gitlab" {
  name         = "gitlab/gitlab-ce:latest"
  keep_locally = false
}

resource "docker_container" "gitlab" {
  name  = var.gitlab_container_name
  image = docker_image.gitlab.image_id

  restart = "always"

  hostname = var.gitlab_domain

  ports {
    internal = 443
    external = 443
  }

  ports {
    internal = 80
    external = 80
  }

  ports {
    internal = 22
    external = 2222
  }

  volumes {
    host_path      = var.gitlab_config_path
    container_path = "/etc/gitlab"
  }

  volumes {
    host_path      = var.gitlab_logs_path
    container_path = "/var/log/gitlab"
  }

  volumes {
    host_path      = var.gitlab_data_path
    container_path = "/var/opt/gitlab"
  }

  env = [
    "GITLAB_OMNIBUS_CONFIG=${local.gitlab_config}",
    "GITLAB_ROOT_PASSWORD=${var.admin_password}"
  ]

  shm_size = 256
}

locals {
  gitlab_config = templatefile("${path.module}/templates/gitlab.rb.tpl", {
    external_url      = "https://${var.gitlab_domain}"
    letsencrypt_email = var.letsencrypt_email
    enable_letsencrypt = var.enable_letsencrypt
  })
}
