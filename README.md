# BuildForever

**Automated GitLab Environment Builder for Multiple Platforms**

BuildForever is a comprehensive deployment tool that automates GitLab installation and configuration across Windows, Linux, and macOS platforms with a user-friendly web interface.

## Features

- **Multi-Platform Support**: Deploy GitLab on Windows (10, 11, Server 2022, 2025), Linux (Debian, Ubuntu, Arch, Rocky), and macOS
- **Web Interface**: Easy-to-use Flask-based web UI for configuration and deployment
- **Automated SSL**: Built-in Let's Encrypt integration with automatic certificate generation and renewal
- **Infrastructure as Code**: Terraform for consistent infrastructure provisioning
- **Configuration Management**: Ansible playbooks for platform-specific setup
- **One-Click Deployment**: Simple deployment process - just provide domain and password
- **Fully Automated**: From bare system to fully functional GitLab instance

## Quick Start

### Prerequisites

- Python 3.8+
- Docker
- Terraform
- Ansible (Linux/macOS)
- 4GB RAM (8GB recommended)
- 20GB free disk space

### Installation

**Linux/macOS:**
```bash
git clone https://github.com/sp00nznet/BuildForever.git
cd BuildForever
./scripts/start.sh
```

**Windows:**
```powershell
git clone https://github.com/sp00nznet/BuildForever.git
cd BuildForever
scripts\start.bat
```

### Deploy GitLab

1. Open `http://localhost:5000` in your browser
2. Select your platform and OS version
3. Enter your domain (e.g., `gitlab.example.com`)
4. Provide your email for SSL certificates
5. Set admin password
6. Click "Deploy GitLab"

That's it! In 15-30 minutes, you'll have a fully functional GitLab instance with SSL.

## Supported Platforms

### Windows
- Windows 10
- Windows 11
- Windows Server 2022
- Windows Server 2025

### Linux
- Debian
- Ubuntu
- Arch Linux
- Rocky Linux

### macOS
- macOS 11 (Big Sur) and later

## Architecture

BuildForever uses a modern infrastructure-as-code approach:

```
BuildForever/
├── gitlab-deployer/     # Flask web application
│   ├── app/            # Web interface
│   └── run.py          # Application entry point
├── terraform/          # Infrastructure provisioning
│   ├── main.tf         # GitLab container configuration
│   └── templates/      # Configuration templates
├── ansible/            # Configuration management
│   ├── playbooks/      # Platform-specific playbooks
│   └── roles/          # Reusable roles
├── scripts/            # Deployment orchestration
│   ├── deploy.sh       # Main deployment script
│   └── start.sh/bat    # Web interface launcher
└── docs/               # Documentation
```

## Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## What You Get

After deployment, you'll have:

- GitLab Community Edition running in Docker
- SSL certificate via Let's Encrypt (auto-renewing)
- Admin access with your configured password
- SSH access on port 2222
- Web interface on ports 80/443
- Automated backups configured
- Ready to create users, groups, and repositories

## Access Your GitLab

After deployment completes:

- **URL**: `https://your-domain.com`
- **Username**: `root`
- **Password**: [as configured during deployment]
- **SSH**: `git@your-domain.com:2222`

## Technology Stack

- **Web Interface**: Flask (Python)
- **Infrastructure**: Terraform
- **Configuration**: Ansible
- **Containerization**: Docker
- **SSL**: Let's Encrypt (automated)
- **GitLab**: Community Edition (latest)

## Advanced Usage

### CLI Deployment

For automation or advanced users:

```bash
# Full deployment
./scripts/deploy.sh deploy

# Step-by-step
./scripts/deploy.sh init
./scripts/deploy.sh plan
./scripts/deploy.sh apply

# Destroy
./scripts/deploy.sh destroy
```

### Custom Configuration

Edit configuration files in `config/` and Terraform templates in `terraform/templates/` to customize your GitLab installation.

## Security Features

- Strong password requirements
- Let's Encrypt SSL/TLS encryption
- Automatic certificate renewal
- Secure container configuration
- Configurable firewall rules
- SSH key authentication support

## Backup and Restore

GitLab backups are automatically configured:

```bash
# Create backup
docker exec gitlab gitlab-backup create

# Restore backup
docker exec gitlab gitlab-backup restore BACKUP=[timestamp]
```

## Monitoring

Monitor your deployment:

- Web interface shows real-time logs
- CLI logs saved to `logs/` directory
- GitLab built-in monitoring at `/admin/monitoring`

## Troubleshooting

### Common Issues

**Docker not running:**
```bash
docker info
```

**Permission errors (Linux):**
```bash
sudo usermod -aG docker $USER
newgrp docker
```

**Port conflicts:**
```bash
export PORT=8080
./scripts/start.sh
```

See [Deployment Guide](docs/DEPLOYMENT.md) for more troubleshooting tips.

## Inspiration

This project was inspired by [myhome](https://github.com/sp00nznet/myhome) and uses a similar architecture for deployment automation.

## Contributing

Contributions welcome! Please open an issue or pull request.

## License

MIT License

## Support

- Issues: https://github.com/sp00nznet/BuildForever/issues
- GitLab Docs: https://docs.gitlab.com

---

Built with by sp00nznet | Deploy GitLab Anywhere, Anytime
