# BuildForever

**Multi-Platform GitLab CI/CD Build Farm**

BuildForever is a comprehensive deployment tool that creates a complete GitLab CI/CD build farm with runners for multiple platforms. Deploy a fully configured GitLab instance with dedicated runners for Windows (10, 11, Server 2022, 2025), Linux (Debian, Ubuntu, Arch, Rocky), and macOS - all from a user-friendly web interface.

## Features

- **Complete Build Farm**: Deploy GitLab server + multi-platform runners in one click
- **9 Platform Runners**:
  - 2 Windows Desktop (10, 11)
  - 2 Windows Server (2022, 2025)
  - 4 Linux Distributions (Debian, Ubuntu, Arch, Rocky)
  - 1 macOS Runner
- **Automatic Runner Registration**: All runners auto-register with your GitLab instance
- **Web Interface**: Easy-to-use Flask-based UI for selecting and deploying runners
- **Saved Configurations**: Save and load deployment configurations for quick repeated deployments
- **Credential Management**: Securely store and reuse SSH keys and deployment credentials
- **Docker Support**: Full Docker containerization with docker-compose for easy deployment
- **Traefik Reverse Proxy**: Optional automatic SSL, load balancing, and service discovery
- **Automated SSL**: Built-in Let's Encrypt integration with automatic certificate generation and renewal
- **Infrastructure as Code**: Terraform for consistent infrastructure provisioning
- **Configuration Management**: Ansible playbooks for platform-specific setup
- **Tagged Runners**: Each runner pre-configured with platform-specific tags for targeted builds
- **Deployment History**: Track all deployments with status and logs
- **Fully Automated**: From configuration to fully functional build farm

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

**Docker:**
```bash
git clone https://github.com/sp00nznet/BuildForever.git
cd BuildForever
cp .env.example .env
# Edit .env with your configuration
docker-compose up -d
```

### Deploy Build Farm

1. Open `http://localhost:5000` in your browser
2. Enter your GitLab domain (e.g., `gitlab.example.com`)
3. Provide your email for SSL certificates
4. Set admin password
5. **Select runners** - Choose which platform runners to deploy (Windows, Linux, macOS)
6. Click "Deploy Build Farm"

That's it! In 30-60 minutes (depending on runner count), you'll have a fully functional GitLab build farm with SSL and all selected runners connected.

## Available Runners

BuildForever can deploy GitLab runners for the following platforms. Select any combination during deployment:

### Windows Runners (4)
- **Windows 10** - Desktop builds and testing (tags: `windows`, `windows-10`, `desktop`)
- **Windows 11** - Latest desktop platform (tags: `windows`, `windows-11`, `desktop`)
- **Windows Server 2022** - Enterprise builds (tags: `windows`, `server`, `2022`)
- **Windows Server 2025** - Latest server platform (tags: `windows`, `server`, `2025`)

### Linux Runners (4)
- **Debian** - Stable Linux builds (tags: `linux`, `debian`)
- **Ubuntu** - Popular Linux platform (tags: `linux`, `ubuntu`)
- **Arch Linux** - Bleeding edge builds (tags: `linux`, `arch`)
- **Rocky Linux** - RHEL-compatible builds (tags: `linux`, `rocky`, `rhel`)

### macOS Runner (1)
- **macOS** - Apple platform builds (tags: `macos`, `darwin`)

## Architecture

BuildForever uses a modern infrastructure-as-code approach:

```
BuildForever/
├── gitlab-deployer/     # Flask web application
│   ├── app/            # Web interface with saved configs
│   │   ├── models.py   # Database models for credentials
│   │   └── routes.py   # API endpoints
│   └── run.py          # Application entry point
├── terraform/          # Infrastructure provisioning
│   ├── main.tf         # GitLab container configuration
│   └── templates/      # Configuration templates
├── ansible/            # Configuration management
│   ├── playbooks/      # Platform-specific playbooks
│   └── roles/          # Reusable roles
├── scripts/            # Deployment orchestration
│   ├── deploy.sh       # Main deployment script
│   ├── start.sh/bat    # Web interface launcher
│   ├── stop.sh/bat     # Stop running services
│   └── clear_cache.*   # Cache clearing utilities
├── docs/               # Documentation
├── Dockerfile          # Container build configuration
├── docker-compose.yml  # Docker orchestration
└── .env.example        # Environment configuration template
```

## Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## What You Get

After deployment, you'll have a complete CI/CD build farm:

- **GitLab Community Edition** running in Docker
- **SSL certificate** via Let's Encrypt (auto-renewing)
- **Admin access** with your configured password
- **SSH access** on port 2222
- **Web interface** on ports 80/443
- **GitLab Runners** for your selected platforms, all automatically registered
- **Tagged runners** ready for multi-platform builds in your CI/CD pipelines
- **Automated backups** configured
- Ready to create users, groups, repositories, and run multi-platform CI/CD jobs

### Example .gitlab-ci.yml

```yaml
stages:
  - build
  - test

build-windows:
  stage: build
  tags:
    - windows-11
  script:
    - echo "Building on Windows 11"

build-linux:
  stage: build
  tags:
    - ubuntu
  script:
    - echo "Building on Ubuntu"

test-macos:
  stage: test
  tags:
    - macos
  script:
    - echo "Testing on macOS"
```

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

### Docker Deployment

Deploy BuildForever in a container:

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f buildforever

# Stop services
docker-compose down

# Deploy with GitLab (optional profile)
docker-compose --profile gitlab up -d
```

### Saved Configurations

BuildForever allows you to save and load deployment configurations:

1. Fill in your deployment details (domain, email, runners)
2. Click "Save Current" and give it a name
3. Next time, select from the dropdown to instantly load saved settings
4. Optionally save passwords locally for quick re-deployments

### Utility Scripts

```bash
# Stop running services
./scripts/stop.sh          # Linux/macOS
scripts\stop.bat           # Windows

# Clear cache (Python bytecode, temp files)
./scripts/clear_cache.sh   # Linux/macOS
scripts\clear_cache.bat    # Windows

# Clear including logs
./scripts/clear_cache.sh --include-logs

# Clear including Terraform state (requires re-init)
./scripts/clear_cache.sh --include-terraform
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

Built with by sp00nznet | Multi-Platform CI/CD Build Farms Made Easy

## Use Cases

- **Cross-Platform Development**: Test your application on Windows, Linux, and macOS simultaneously
- **Enterprise CI/CD**: Build and deploy software across multiple operating systems
- **Quality Assurance**: Run automated tests on all target platforms in parallel
- **Open Source Projects**: Provide comprehensive platform support for your users
- **Development Teams**: Give developers access to consistent build environments across all platforms
