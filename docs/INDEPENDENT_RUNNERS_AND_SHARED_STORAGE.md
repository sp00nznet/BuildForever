# Independent Runners and Shared Storage Features

## Overview

BuildForever now supports flexible deployment modes and shared storage mounting across all GitLab and runner instances. This allows you to:

1. Deploy runners without deploying a new GitLab server
2. Connect runners to existing external GitLab instances
3. Mount NFS or Samba/CIFS shared storage on all instances
4. Share build artifacts and caches across the build farm

## Features

### 1. GitLab Deployment Modes

You can now choose from three deployment modes:

#### Mode 1: Deploy New GitLab Server (Default)
- Creates a fresh GitLab instance
- Automatically configures and registers runners
- Full control over GitLab configuration
- Best for: New projects, isolated environments

#### Mode 2: Use Existing GitLab Server
- Connects runners to an external GitLab instance
- No local GitLab deployment
- Runners auto-register with the existing server
- Best for: Adding capacity to existing GitLab, multi-site setups

#### Mode 3: Runners Only (No GitLab)
- Deploys standalone runners without GitLab
- Runners are not registered to any GitLab instance
- Can be manually registered later
- Best for: Pre-provisioning infrastructure, testing runner configurations

### 2. Shared Storage

#### NFS (Network File System)
Mount NFS shares on all GitLab and runner instances for sharing:
- Build artifacts
- Cache directories
- Shared libraries and dependencies
- Custom build tools

**Configuration:**
- **NFS Share**: Server and path (e.g., `192.168.1.100:/export/shared`)
- **Mount Path**: Where to mount on each instance (default: `/mnt/shared`)

**Supported on:** Linux (Debian, Ubuntu, Rocky, Arch), macOS runners, GitLab server

#### Samba/CIFS (Windows File Sharing)
Mount Windows/Samba shares with authentication:
- Ideal for Windows build environments
- Domain authentication support
- Guest access available

**Configuration:**
- **Samba Share**: Server and share name (e.g., `192.168.1.100/builds` or `fileserver.local/shared`)
- **Mount Path**: Where to mount (Linux: `/mnt/samba`, Windows: `S:`)
- **Username**: Authentication username (optional for guest access)
- **Password**: Authentication password (optional for guest access)
- **Domain**: Windows domain or workgroup (optional)

**Supported on:** All platforms (Linux, Windows, macOS)

## Usage Guide

### Web UI

#### Selecting GitLab Deployment Mode

1. Navigate to the **GitLab Deployment Mode** section
2. Choose your deployment mode:
   - **Deploy New GitLab Server**: Creates a new GitLab instance
   - **Use Existing GitLab Server**: Connects to external GitLab
   - **Runners Only**: Deploys runners without GitLab

3. For existing GitLab:
   - Enter the GitLab URL (e.g., `https://gitlab.company.com`)
   - Click **Test Connection** to verify accessibility
   - The system will detect the GitLab version and confirm connectivity

4. For new GitLab:
   - Configure domain, email, and admin password as usual
   - All GitLab Server Configuration options will be available

5. For runners only:
   - Skip GitLab configuration entirely
   - Runners will be deployed but not registered

#### Configuring Shared Storage

1. Expand the **Shared Storage (Optional)** section
2. Enable NFS if you have an NFS server:
   - Check **Enable NFS Shared Storage**
   - Enter NFS Share (format: `server:/path`)
   - Optionally customize the mount path
3. Enable Samba/CIFS if you have a Windows file share:
   - Check **Enable Samba/CIFS Shared Storage**
   - Enter Samba Share (format: `server/share`)
   - Optionally customize the mount path
   - Provide credentials if required (username, password, domain)
   - Leave credentials empty for guest access

### API Usage

#### Deploy Runners with Existing GitLab

```bash
curl -X POST http://localhost:5000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deploy_gitlab": false,
    "gitlab_url": "https://gitlab.company.com",
    "domain": "runners-production",
    "runners": ["debian", "ubuntu", "windows-11"],
    "provider": "proxmox",
    "provider_config": {
      "host": "proxmox.company.com",
      "user": "root@pam",
      "password": "password",
      "node": "pve",
      "storage": "local-lvm",
      "bridge": "vmbr0"
    },
    "nfs_share": "192.168.1.100:/export/builds",
    "nfs_mount_path": "/mnt/shared"
  }'
```

#### Deploy Runners Only (No GitLab)

```bash
curl -X POST http://localhost:5000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deploy_gitlab": false,
    "domain": "standalone-runners",
    "runners": ["debian", "windows-server-2022"],
    "provider": "proxmox",
    "provider_config": {...},
    "samba_share": "192.168.1.100/builds",
    "samba_mount_path": "/mnt/samba",
    "samba_username": "builduser",
    "samba_password": "SecurePass123",
    "samba_domain": "COMPANY"
  }'
```

#### Test Existing GitLab Server

```bash
curl -X POST http://localhost:5000/api/test-gitlab \
  -H "Content-Type: application/json" \
  -d '{"gitlab_url": "https://gitlab.company.com"}'
```

Response:
```json
{
  "success": true,
  "message": "GitLab 16.5.1 detected",
  "gitlab_url": "https://gitlab.company.com"
}
```

### Terraform/Docker Deployment

#### Variables

New Terraform variables for conditional deployment and shared storage:

```hcl
# GitLab deployment control
variable "deploy_gitlab" {
  description = "Whether to deploy a new GitLab server"
  type        = bool
  default     = true
}

variable "gitlab_url" {
  description = "URL of existing GitLab server (if not deploying new)"
  type        = string
  default     = ""
}

# NFS configuration
variable "nfs_share" {
  description = "NFS share to mount (format: server:/path)"
  type        = string
  default     = ""
}

variable "nfs_mount_path" {
  description = "Path where NFS should be mounted"
  type        = string
  default     = "/mnt/shared"
}

# Samba configuration
variable "samba_share" {
  description = "Samba/CIFS share to mount (format: server/share)"
  type        = string
  default     = ""
}

variable "samba_mount_path" {
  description = "Path where Samba share should be mounted"
  type        = string
  default     = "/mnt/samba"
}

variable "samba_username" {
  description = "Username for Samba authentication"
  type        = string
  default     = ""
  sensitive   = true
}

variable "samba_password" {
  description = "Password for Samba authentication"
  type        = string
  default     = ""
  sensitive   = true
}

variable "samba_domain" {
  description = "Domain for Samba authentication"
  type        = string
  default     = ""
}
```

#### Example: Runners Only with NFS

```hcl
module "buildforever" {
  source = "./terraform"

  # Disable GitLab deployment
  deploy_gitlab = false

  # Enable runners
  enabled_runners = ["debian", "ubuntu", "windows-11"]

  # NFS shared storage
  nfs_share      = "192.168.1.100:/export/builds"
  nfs_mount_path = "/mnt/shared"

  # Proxmox configuration
  # ... (standard Proxmox settings)
}
```

## Architecture

### Deployment Flow

#### New GitLab + Runners
```
┌─────────────────────────────────────────┐
│ BuildForever Deployment                 │
├─────────────────────────────────────────┤
│                                         │
│  1. Deploy GitLab Server                │
│     ↓                                   │
│  2. Wait for GitLab initialization      │
│     ↓                                   │
│  3. Obtain runner registration token    │
│     ↓                                   │
│  4. Deploy Runners                      │
│     ↓                                   │
│  5. Auto-register runners to GitLab     │
│     ↓                                   │
│  6. Mount shared storage (optional)     │
│                                         │
└─────────────────────────────────────────┘
```

#### Existing GitLab + Runners
```
┌─────────────────────────────────────────┐
│ BuildForever Deployment                 │
├─────────────────────────────────────────┤
│                                         │
│  1. Verify external GitLab accessibility│
│     ↓                                   │
│  2. Obtain runner registration token    │
│     ↓                                   │
│  3. Deploy Runners                      │
│     ↓                                   │
│  4. Auto-register runners to GitLab     │
│     ↓                                   │
│  5. Mount shared storage (optional)     │
│                                         │
└─────────────────────────────────────────┘
```

#### Runners Only (No GitLab)
```
┌─────────────────────────────────────────┐
│ BuildForever Deployment                 │
├─────────────────────────────────────────┤
│                                         │
│  1. Deploy Runners                      │
│     ↓                                   │
│  2. Mount shared storage (optional)     │
│     ↓                                   │
│  3. Runners ready for manual registration│
│                                         │
└─────────────────────────────────────────┘
```

### Storage Mounting

#### Linux Runners (Debian, Ubuntu, Rocky, Arch)
```bash
# NFS mounting
apt-get install -y nfs-common
mkdir -p /mnt/shared
echo "192.168.1.100:/export/shared /mnt/shared nfs defaults,_netdev 0 0" >> /etc/fstab
mount -a

# Samba mounting with credentials
apt-get install -y cifs-utils
mkdir -p /mnt/samba
cat > /root/.smbcredentials << EOF
username=builduser
password=password
domain=COMPANY
EOF
chmod 600 /root/.smbcredentials
echo "//192.168.1.100/builds /mnt/samba cifs credentials=/root/.smbcredentials,_netdev 0 0" >> /etc/fstab
mount -a
```

#### Windows Runners
```powershell
# NFS mounting
Install-WindowsFeature -Name NFS-Client
New-PSDrive -Name N -PSProvider FileSystem -Root "\\192.168.1.100\export\shared" -Persist

# Samba mounting
$secPassword = ConvertTo-SecureString "password" -AsPlainText -Force
$credential = New-Object System.Management.Automation.PSCredential("COMPANY\builduser", $secPassword)
New-PSDrive -Name S -PSProvider FileSystem -Root "\\192.168.1.100\builds" -Credential $credential -Persist
```

#### macOS Runners
```bash
# NFS mounting
mkdir -p /Volumes/NFSShare
mount -t nfs 192.168.1.100:/export/shared /Volumes/NFSShare

# Samba mounting
mkdir -p /Volumes/Shared
mount -t smbfs smb://builduser:password@192.168.1.100/builds /Volumes/Shared
```

## Use Cases

### 1. Multi-Site Build Farm
Deploy runners in multiple data centers connecting to a central GitLab instance:

- **Central Site**: GitLab server + local runners
- **Remote Site 1**: Runners only (connecting to central)
- **Remote Site 2**: Runners only (connecting to central)
- **Shared Storage**: NFS server for artifacts distributed to all sites

### 2. Hybrid Cloud Deployment
Mix on-premise and cloud infrastructure:

- **On-Premise**: GitLab server + shared storage server
- **Cloud Provider A**: Linux runners (connecting to on-premise)
- **Cloud Provider B**: Windows runners (connecting to on-premise)
- **Storage**: Samba share mounted across all locations

### 3. Development vs Production Separation
Separate runners for different environments:

- **Production GitLab**: Existing corporate GitLab instance
- **Dev Runner Farm**: Dedicated development runners connected to production
- **Test Runner Farm**: Independent test runners for runner configuration testing
- **Shared Storage**: Separate NFS shares for dev and test environments

### 4. Capacity Expansion
Add runner capacity to existing GitLab without modifying the server:

- **Existing**: GitLab Community Edition with 2 runners
- **New Deployment**: 10 additional specialized runners (Windows, macOS, GPU)
- **Integration**: Automatic registration to existing GitLab
- **Storage**: Shared cache for faster builds

## Best Practices

### Security

1. **NFS Security**
   - Use NFS v4 with Kerberos authentication in production
   - Restrict NFS exports to specific IP ranges
   - Use `no_root_squash` carefully

2. **Samba Security**
   - Always use strong passwords
   - Store credentials securely (use credential management)
   - Consider domain authentication for enterprise environments
   - Use SMB3 encryption where possible

3. **Runner Security**
   - Register runners with tags to control job assignment
   - Use separate runners for sensitive workloads
   - Implement runner token rotation

### Performance

1. **Storage Performance**
   - Use SSD-backed NFS/Samba servers for better build performance
   - Consider local caching for frequently accessed files
   - Monitor network bandwidth usage

2. **Resource Allocation**
   - Size runners based on expected workload
   - Use concurrent job limits to prevent overload
   - Monitor runner resource usage

3. **Network**
   - Use dedicated VLANs for build farm traffic
   - Implement QoS for storage traffic
   - Co-locate storage servers with runners when possible

### Maintenance

1. **Runner Updates**
   - Schedule regular GitLab Runner updates
   - Test runner updates in non-production first
   - Maintain runner version compatibility with GitLab

2. **Storage Management**
   - Implement automatic cleanup policies for old artifacts
   - Monitor storage capacity
   - Regular backups of shared storage

3. **Monitoring**
   - Monitor runner health and job success rates
   - Track storage usage and performance
   - Set up alerts for runner failures

## Troubleshooting

### GitLab Connection Issues

**Problem**: Cannot connect to existing GitLab server

**Solutions**:
1. Verify GitLab URL is correct and accessible
2. Check firewall rules allow HTTPS (443) traffic
3. Verify SSL certificate is valid (or disable SSL verification for self-signed)
4. Ensure GitLab version is compatible (14.0+)

### Storage Mounting Failures

**Problem**: NFS mount fails

**Solutions**:
1. Verify NFS server is running: `showmount -e nfs-server`
2. Check NFS exports: `cat /etc/exports` on NFS server
3. Ensure `nfs-common` (Debian/Ubuntu) or `nfs-utils` (Rocky) is installed
4. Check network connectivity to NFS server
5. Verify permissions on NFS export

**Problem**: Samba mount fails

**Solutions**:
1. Verify Samba server is accessible: `smbclient -L //server -U username`
2. Check credentials are correct
3. Ensure `cifs-utils` is installed
4. Verify share name and server address
5. Check Windows firewall allows SMB traffic (445)

### Runner Registration Issues

**Problem**: Runners not appearing in GitLab

**Solutions**:
1. Verify GitLab URL is accessible from runner
2. Check runner logs: `gitlab-runner verify`
3. Ensure registration token is valid
4. Verify network connectivity
5. Check GitLab runner settings allow registration

## Limitations

1. **Docker Volume Drivers**: NFS and CIFS mounting in Docker requires appropriate volume drivers
2. **Platform Support**: Some features may not be available on all platforms
3. **Performance**: Network storage will be slower than local storage
4. **Dependencies**: Requires external storage infrastructure (NFS/Samba server)

## Migration Guide

### From Standard Deployment to Existing GitLab

1. Note your current runners and configurations
2. Prepare your existing GitLab instance
3. Deploy new runners with `deploy_gitlab=false` and `gitlab_url` set
4. Verify runners register successfully
5. Decommission old GitLab instance (if desired)
6. Update CI/CD pipelines to use new runner tags

### Adding Shared Storage to Existing Deployment

1. Set up NFS or Samba server
2. Configure exports/shares
3. Update deployment configuration with storage settings
4. Redeploy or update existing instances
5. Verify mounts are accessible
6. Update CI/CD pipelines to use shared paths

## Support and Contributing

For issues, feature requests, or contributions:
- GitHub Issues: https://github.com/sp00nznet/BuildForever/issues
- Documentation: https://github.com/sp00nznet/BuildForever/docs

## Changelog

### Version 2.0.0
- Added independent runner deployment mode
- Added support for existing GitLab servers
- Implemented NFS shared storage
- Implemented Samba/CIFS shared storage
- Updated web UI with deployment mode selection
- Updated Terraform templates for conditional resources
- Added comprehensive API endpoints for new features
