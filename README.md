# BuildForever

**Multi-Platform GitLab CI/CD Build Farm with Harbor & Rancher**

Deploy a complete GitLab CI/CD infrastructure with multi-platform runners, container registry, and Kubernetes management - all from a single web interface.

## Features

- **GitLab CE** with automatic SSL via Let's Encrypt
- **9 Platform Runners**: Windows (10, 11, Server 2022/2025), Linux (Debian, Ubuntu, Arch, Rocky), macOS
- **Harbor Registry** - Enterprise container registry with vulnerability scanning
- **Rancher Server** - Kubernetes cluster management platform
- **Proxmox VE** deployment with automatic VM/container provisioning
- **Credential Management** - Securely store SSH keys and passwords
- **Saved Configurations** - Quick repeated deployments

## Quick Start

```bash
git clone https://github.com/sp00nznet/BuildForever.git
cd BuildForever
pip install -r requirements.txt
python gitlab-deployer/run.py
```

Open `http://localhost:5000` and configure your deployment.

### Docker

```bash
cp .env.example .env
docker-compose up -d
```

## What Gets Deployed

| Component | Description | Resources |
|-----------|-------------|-----------|
| **GitLab CE** | CI/CD server with SSL | 4 CPU, 8GB RAM |
| **Runners** | Platform-specific build agents | 2-4 CPU, 4-16GB RAM each |
| **Harbor** | Container registry + Trivy scanner | 4 CPU, 8GB RAM, 100GB storage |
| **Rancher** | Kubernetes management | 4 CPU, 8GB RAM |

## Available Runners

| Platform | Variants | Tags |
|----------|----------|------|
| **Windows Desktop** | 10, 11 | `windows`, `desktop` |
| **Windows Server** | 2022, 2025 | `windows`, `server` |
| **Linux** | Debian, Ubuntu, Arch, Rocky | `linux`, `[distro]` |
| **macOS** | Sequoia | `macos`, `darwin` |

## Example Pipeline

```yaml
stages: [build, test]

build-windows:
  tags: [windows-11]
  script: echo "Building on Windows"

build-linux:
  tags: [ubuntu]
  script: echo "Building on Ubuntu"

# Push to Harbor registry
build-image:
  tags: [linux]
  script:
    - docker login $HARBOR_URL -u $HARBOR_USERNAME -p $HARBOR_PASSWORD
    - docker build -t $HARBOR_URL/gitlab-builds/$CI_PROJECT_NAME:$CI_COMMIT_SHA .
    - docker push $HARBOR_URL/gitlab-builds/$CI_PROJECT_NAME:$CI_COMMIT_SHA
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Installation](docs/INSTALLATION.md) | Prerequisites and setup |
| [Deployment](docs/DEPLOYMENT.md) | Deployment process and options |
| [Harbor Integration](docs/HARBOR_GITLAB_INTEGRATION.md) | Container registry setup |
| [Shared Storage](docs/GITLAB_SHARED_STORAGE_EXAMPLES.md) | NFS/Samba configuration |
| [macOS VMs](docs/MACOS_VM_PROXMOX.md) | macOS on Proxmox setup |

## Architecture

```
BuildForever/
├── gitlab-deployer/    # Flask web UI
│   ├── app/
│   │   ├── routes.py         # API endpoints
│   │   ├── proxmox_client.py # Proxmox automation
│   │   └── models.py         # Database models
├── terraform/          # Infrastructure as Code
├── ansible/            # Configuration playbooks
├── docs/               # Documentation
└── scripts/            # Utility scripts
```

## CLI Usage

```bash
# Start web interface
./scripts/start.sh

# Direct deployment
./scripts/deploy.sh deploy

# Terraform workflow
./scripts/deploy.sh init && ./scripts/deploy.sh plan && ./scripts/deploy.sh apply
```

## Requirements

- Python 3.8+
- Proxmox VE 7+ (for VM/container deployment)
- 8GB+ RAM on deployment target
- Network access to Proxmox API

## Contributing

Issues and PRs welcome at [GitHub](https://github.com/sp00nznet/BuildForever/issues).

## License

MIT
