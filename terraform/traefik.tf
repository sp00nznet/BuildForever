# Traefik Reverse Proxy Container Configuration
# Provides automatic SSL, load balancing, and service discovery

resource "docker_image" "traefik" {
  count = var.enable_traefik ? 1 : 0
  name  = "traefik:v3.0"
}

resource "docker_container" "traefik" {
  count = var.enable_traefik ? 1 : 0

  name  = var.traefik_container_name
  image = docker_image.traefik[0].image_id

  restart = "unless-stopped"

  # Traefik command configuration
  command = [
    # API and Dashboard
    "--api.dashboard=${var.traefik_dashboard_enabled}",
    "--api.insecure=false",

    # Docker provider
    "--providers.docker=true",
    "--providers.docker.exposedbydefault=false",
    "--providers.docker.network=buildforever-net",

    # File provider for dynamic configuration
    "--providers.file.directory=/etc/traefik/dynamic",
    "--providers.file.watch=true",

    # Entrypoints
    "--entrypoints.web.address=:80",
    "--entrypoints.websecure.address=:443",

    # HTTP to HTTPS redirect
    "--entrypoints.web.http.redirections.entrypoint.to=websecure",
    "--entrypoints.web.http.redirections.entrypoint.scheme=https",

    # Let's Encrypt ACME
    "--certificatesresolvers.letsencrypt.acme.email=${var.letsencrypt_email}",
    "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json",
    "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web",

    # Logging
    "--log.level=INFO",
    "--accesslog=true"
  ]

  # Port mappings
  ports {
    internal = 80
    external = 80
  }

  ports {
    internal = 443
    external = 443
  }

  dynamic "ports" {
    for_each = var.traefik_dashboard_enabled ? [1] : []
    content {
      internal = 8080
      external = 8080
    }
  }

  # Volume mounts
  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
    read_only      = true
  }

  volumes {
    host_path      = var.traefik_acme_path
    container_path = "/letsencrypt"
  }

  volumes {
    host_path      = "${var.traefik_config_path}/dynamic"
    container_path = "/etc/traefik/dynamic"
    read_only      = true
  }

  # Network
  networks_advanced {
    name = docker_network.buildforever.name
  }

  # Labels for self-routing (dashboard)
  dynamic "labels" {
    for_each = var.traefik_dashboard_enabled ? [1] : []
    content {
      label = "traefik.enable"
      value = "true"
    }
  }

  dynamic "labels" {
    for_each = var.traefik_dashboard_enabled && var.base_domain != "" ? [1] : []
    content {
      label = "traefik.http.routers.traefik-dashboard.rule"
      value = "Host(`traefik.${var.base_domain}`)"
    }
  }

  dynamic "labels" {
    for_each = var.traefik_dashboard_enabled ? [1] : []
    content {
      label = "traefik.http.routers.traefik-dashboard.entrypoints"
      value = "websecure"
    }
  }

  dynamic "labels" {
    for_each = var.traefik_dashboard_enabled ? [1] : []
    content {
      label = "traefik.http.routers.traefik-dashboard.tls.certresolver"
      value = "letsencrypt"
    }
  }

  dynamic "labels" {
    for_each = var.traefik_dashboard_enabled ? [1] : []
    content {
      label = "traefik.http.routers.traefik-dashboard.service"
      value = "api@internal"
    }
  }

  # Health check
  healthcheck {
    test         = ["CMD", "traefik", "healthcheck"]
    interval     = "30s"
    timeout      = "10s"
    retries      = 3
    start_period = "10s"
  }
}

# Docker network for service discovery
resource "docker_network" "buildforever" {
  name   = "buildforever-net"
  driver = "bridge"

  # Only create if Traefik is enabled, otherwise it may already exist
  count = var.enable_traefik ? 1 : 0
}

# Create Traefik configuration directory
resource "null_resource" "traefik_config_dirs" {
  count = var.enable_traefik ? 1 : 0

  provisioner "local-exec" {
    command = <<-EOT
      mkdir -p ${var.traefik_config_path}/dynamic
      mkdir -p ${var.traefik_acme_path}
      chmod 600 ${var.traefik_acme_path} 2>/dev/null || true
    EOT
  }
}

# Output Traefik information
output "traefik_enabled" {
  description = "Whether Traefik is enabled"
  value       = var.enable_traefik
}

output "traefik_dashboard_url" {
  description = "URL for Traefik dashboard"
  value       = var.enable_traefik && var.traefik_dashboard_enabled && var.base_domain != "" ? "https://traefik.${var.base_domain}" : null
}
