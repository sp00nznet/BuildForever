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

# Shared Storage Volumes
# NFS Volume (if configured)
resource "docker_volume" "nfs_shared" {
  count = var.nfs_share != "" ? 1 : 0
  name  = "nfs_shared"

  driver = "local"
  driver_opts = {
    type   = "nfs"
    o      = "addr=${split(":", var.nfs_share)[0]},rw"
    device = ":${split(":", var.nfs_share)[1]}"
  }
}

# Samba/CIFS Volume (if configured)
resource "docker_volume" "samba_shared" {
  count = var.samba_share != "" ? 1 : 0
  name  = "samba_shared"

  driver = "local"
  driver_opts = {
    type   = "cifs"
    o      = var.samba_username != "" ? "username=${var.samba_username},password=${var.samba_password}${var.samba_domain != "" ? ",domain=${var.samba_domain}" : ""},rw" : "guest,rw"
    device = "//${var.samba_share}"
  }
}

# GitLab Container (conditional - only created if deploy_gitlab is true)
resource "docker_image" "gitlab" {
  count        = var.deploy_gitlab ? 1 : 0
  name         = "gitlab/gitlab-ce:latest"
  keep_locally = false
}

resource "docker_container" "gitlab" {
  count   = var.deploy_gitlab ? 1 : 0
  name    = var.gitlab_container_name
  image   = docker_image.gitlab[0].image_id

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

  # NFS volume mount (if configured)
  dynamic "volumes" {
    for_each = var.nfs_share != "" ? [1] : []
    content {
      volume_name    = "nfs_shared"
      container_path = var.nfs_mount_path
    }
  }

  # Samba/CIFS volume mount (if configured)
  dynamic "volumes" {
    for_each = var.samba_share != "" ? [1] : []
    content {
      volume_name    = "samba_shared"
      container_path = var.samba_mount_path
    }
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
