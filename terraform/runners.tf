terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

# Windows 10 Runner
resource "docker_container" "runner_windows_10" {
  count = contains(var.enabled_runners, "windows-10") ? 1 : 0
  name  = "gitlab-runner-windows-10"
  image = "gitlab/gitlab-runner:latest"

  restart = "unless-stopped"

  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
  }

  volumes {
    host_path      = "${var.data_dir}/runners/windows-10"
    container_path = "/etc/gitlab-runner"
  }

  env = [
    "RUNNER_NAME=windows-10-runner",
    "RUNNER_TAGS=windows,windows-10,desktop",
    "RUNNER_EXECUTOR=docker",
    "DOCKER_IMAGE=mcr.microsoft.com/windows:10.0.19041.1415"
  ]

  depends_on = [docker_container.gitlab]
}

# Windows 11 Runner
resource "docker_container" "runner_windows_11" {
  count = contains(var.enabled_runners, "windows-11") ? 1 : 0
  name  = "gitlab-runner-windows-11"
  image = "gitlab/gitlab-runner:latest"

  restart = "unless-stopped"

  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
  }

  volumes {
    host_path      = "${var.data_dir}/runners/windows-11"
    container_path = "/etc/gitlab-runner"
  }

  env = [
    "RUNNER_NAME=windows-11-runner",
    "RUNNER_TAGS=windows,windows-11,desktop",
    "RUNNER_EXECUTOR=docker",
    "DOCKER_IMAGE=mcr.microsoft.com/windows:ltsc2022"
  ]

  depends_on = [docker_container.gitlab]
}

# Windows Server 2022 Runner
resource "docker_container" "runner_windows_server_2022" {
  count = contains(var.enabled_runners, "windows-server-2022") ? 1 : 0
  name  = "gitlab-runner-windows-server-2022"
  image = "gitlab/gitlab-runner:latest"

  restart = "unless-stopped"

  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
  }

  volumes {
    host_path      = "${var.data_dir}/runners/windows-server-2022"
    container_path = "/etc/gitlab-runner"
  }

  env = [
    "RUNNER_NAME=windows-server-2022-runner",
    "RUNNER_TAGS=windows,server,2022",
    "RUNNER_EXECUTOR=docker",
    "DOCKER_IMAGE=mcr.microsoft.com/windows/servercore:ltsc2022"
  ]

  depends_on = [docker_container.gitlab]
}

# Windows Server 2025 Runner
resource "docker_container" "runner_windows_server_2025" {
  count = contains(var.enabled_runners, "windows-server-2025") ? 1 : 0
  name  = "gitlab-runner-windows-server-2025"
  image = "gitlab/gitlab-runner:latest"

  restart = "unless-stopped"

  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
  }

  volumes {
    host_path      = "${var.data_dir}/runners/windows-server-2025"
    container_path = "/etc/gitlab-runner"
  }

  env = [
    "RUNNER_NAME=windows-server-2025-runner",
    "RUNNER_TAGS=windows,server,2025",
    "RUNNER_EXECUTOR=docker",
    "DOCKER_IMAGE=mcr.microsoft.com/windows/servercore:ltsc2025"
  ]

  depends_on = [docker_container.gitlab]
}

# Debian Runner
resource "docker_container" "runner_debian" {
  count = contains(var.enabled_runners, "debian") ? 1 : 0
  name  = "gitlab-runner-debian"
  image = "gitlab/gitlab-runner:latest"

  restart = "unless-stopped"

  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
  }

  volumes {
    host_path      = "${var.data_dir}/runners/debian"
    container_path = "/etc/gitlab-runner"
  }

  env = [
    "RUNNER_NAME=debian-runner",
    "RUNNER_TAGS=linux,debian",
    "RUNNER_EXECUTOR=docker",
    "DOCKER_IMAGE=debian:latest"
  ]

  depends_on = [docker_container.gitlab]
}

# Ubuntu Runner
resource "docker_container" "runner_ubuntu" {
  count = contains(var.enabled_runners, "ubuntu") ? 1 : 0
  name  = "gitlab-runner-ubuntu"
  image = "gitlab/gitlab-runner:latest"

  restart = "unless-stopped"

  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
  }

  volumes {
    host_path      = "${var.data_dir}/runners/ubuntu"
    container_path = "/etc/gitlab-runner"
  }

  env = [
    "RUNNER_NAME=ubuntu-runner",
    "RUNNER_TAGS=linux,ubuntu",
    "RUNNER_EXECUTOR=docker",
    "DOCKER_IMAGE=ubuntu:latest"
  ]

  depends_on = [docker_container.gitlab]
}

# Arch Linux Runner
resource "docker_container" "runner_arch" {
  count = contains(var.enabled_runners, "arch") ? 1 : 0
  name  = "gitlab-runner-arch"
  image = "gitlab/gitlab-runner:latest"

  restart = "unless-stopped"

  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
  }

  volumes {
    host_path      = "${var.data_dir}/runners/arch"
    container_path = "/etc/gitlab-runner"
  }

  env = [
    "RUNNER_NAME=arch-runner",
    "RUNNER_TAGS=linux,arch",
    "RUNNER_EXECUTOR=docker",
    "DOCKER_IMAGE=archlinux:latest"
  ]

  depends_on = [docker_container.gitlab]
}

# Rocky Linux Runner
resource "docker_container" "runner_rocky" {
  count = contains(var.enabled_runners, "rocky") ? 1 : 0
  name  = "gitlab-runner-rocky"
  image = "gitlab/gitlab-runner:latest"

  restart = "unless-stopped"

  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
  }

  volumes {
    host_path      = "${var.data_dir}/runners/rocky"
    container_path = "/etc/gitlab-runner"
  }

  env = [
    "RUNNER_NAME=rocky-runner",
    "RUNNER_TAGS=linux,rocky,rhel",
    "RUNNER_EXECUTOR=docker",
    "DOCKER_IMAGE=rockylinux:latest"
  ]

  depends_on = [docker_container.gitlab]
}

# macOS Runner (requires macOS host)
resource "docker_container" "runner_macos" {
  count = contains(var.enabled_runners, "macos") ? 1 : 0
  name  = "gitlab-runner-macos"
  image = "gitlab/gitlab-runner:latest"

  restart = "unless-stopped"

  volumes {
    host_path      = "/var/run/docker.sock"
    container_path = "/var/run/docker.sock"
  }

  volumes {
    host_path      = "${var.data_dir}/runners/macos"
    container_path = "/etc/gitlab-runner"
  }

  env = [
    "RUNNER_NAME=macos-runner",
    "RUNNER_TAGS=macos,darwin",
    "RUNNER_EXECUTOR=shell"
  ]

  depends_on = [docker_container.gitlab]
}
