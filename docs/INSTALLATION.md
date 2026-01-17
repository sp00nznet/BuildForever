# BuildForever - Installation Guide

## Prerequisites

### All Platforms
- Python 3.8 or later
- Git
- 4GB RAM minimum (8GB recommended)
- 20GB free disk space

### Platform-Specific Requirements

#### Windows
- Windows 10, Windows 11, Windows Server 2022, or Windows Server 2025
- Docker Desktop for Windows
- Hyper-V enabled
- PowerShell 5.1 or later

#### Linux
- Debian, Ubuntu, Arch Linux, or Rocky Linux
- Docker Engine
- sudo privileges

#### macOS
- macOS 11 (Big Sur) or later
- Docker Desktop for Mac
- Homebrew (optional but recommended)

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/sp00nznet/BuildForever.git
cd BuildForever
```

### 2. Install Python Dependencies

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Install Terraform

**Linux:**
```bash
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

**macOS:**
```bash
brew install terraform
```

**Windows:**
Download from https://www.terraform.io/downloads and add to PATH

### 4. Install Ansible

**Linux/macOS:**
```bash
pip install ansible
```

**Windows:**
Use WSL2 or install via pip in the virtual environment

### 5. Install Docker

**Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**macOS:**
```bash
brew install --cask docker
```

**Windows:**
Download Docker Desktop from https://www.docker.com/products/docker-desktop

### 6. Verify Installation

```bash
python --version
terraform --version
ansible --version
docker --version
```

## Starting BuildForever

### Linux/macOS
```bash
./scripts/start.sh
```

### Windows
```powershell
scripts\start.bat
```

The web interface will be available at `http://localhost:5000`

## Next Steps

1. Open your browser and navigate to `http://localhost:5000`
2. Select your platform and OS version
3. Configure your GitLab domain and credentials
4. Click "Deploy GitLab" to start the deployment

## Troubleshooting

### Docker Not Running
Ensure Docker is running before deploying:
```bash
docker info
```

### Permission Errors (Linux)
Add your user to the docker group:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Port Already in Use
If port 5000 is already in use, set a different port:
```bash
export PORT=8080
./scripts/start.sh
```

### Firewall Issues
Ensure ports 80, 443, and 2222 are open for GitLab:
```bash
# Ubuntu/Debian
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 2222/tcp
```

## Support

For issues and questions, please visit:
https://github.com/sp00nznet/BuildForever/issues
