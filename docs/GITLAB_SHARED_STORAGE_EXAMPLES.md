# GitLab Shared Storage Usage Examples

## Overview

This guide provides practical examples of how to use shared storage (NFS/Samba) with your GitLab server and runners. Shared storage enables the GitLab server itself to access artifacts, caches, and build outputs directly alongside the runners.

## Table of Contents

1. [GitLab Artifact Storage on NFS](#gitlab-artifact-storage-on-nfs)
2. [Shared Build Cache](#shared-build-cache)
3. [GitLab Backup to Network Storage](#gitlab-backup-to-network-storage)
4. [Container Registry on Shared Storage](#container-registry-on-shared-storage)
5. [GitLab Pages on NFS](#gitlab-pages-on-nfs)
6. [Large File Storage (LFS)](#large-file-storage-lfs)
7. [Complete Configuration Examples](#complete-configuration-examples)

---

## 1. GitLab Artifact Storage on NFS

Store CI/CD artifacts on shared storage so GitLab and runners can access them efficiently.

### Configuration

**Deploy with NFS:**
```bash
# Via API
curl -X POST http://localhost:5000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deploy_gitlab": true,
    "domain": "gitlab.company.com",
    "email": "admin@company.com",
    "admin_password": "SecurePass123",
    "runners": ["debian", "ubuntu"],
    "nfs_share": "storage.company.com:/export/gitlab-data",
    "nfs_mount_path": "/mnt/gitlab-storage",
    "provider": "proxmox",
    "provider_config": {...}
  }'
```

**GitLab Configuration (gitlab.rb):**
```ruby
# After deployment, update GitLab config to use shared storage for artifacts
# Connect to GitLab container:
docker exec -it gitlab bash
# or for Proxmox:
pct exec <vmid> -- bash

# Edit GitLab config
vi /etc/gitlab/gitlab.rb

# Add these lines:
gitlab_rails['artifacts_enabled'] = true
gitlab_rails['artifacts_path'] = "/mnt/gitlab-storage/artifacts"

# Reconfigure GitLab
gitlab-ctl reconfigure
```

**Directory Structure:**
```
/mnt/gitlab-storage/
├── artifacts/           # CI/CD artifacts
│   ├── project1/
│   ├── project2/
│   └── ...
├── cache/              # Shared build cache
├── lfs-objects/        # Git LFS objects
└── backups/            # GitLab backups
```

### Usage in CI/CD Pipeline

**.gitlab-ci.yml:**
```yaml
stages:
  - build
  - test
  - deploy

build:
  stage: build
  script:
    - make build
  artifacts:
    paths:
      - build/
    expire_in: 1 week
  # Artifacts automatically stored on NFS at:
  # /mnt/gitlab-storage/artifacts/<project>/<pipeline>/

test:
  stage: test
  script:
    - ./run-tests.sh
  dependencies:
    - build
  # Automatically downloads artifacts from NFS
```

**Benefits:**
- ✅ GitLab stores artifacts on fast network storage
- ✅ Runners access artifacts directly from NFS (faster than GitLab API)
- ✅ No artifact size limits from GitLab database
- ✅ Easy backup and retention management

---

## 2. Shared Build Cache

Configure a shared cache location accessible by both GitLab and all runners.

### Configuration

**Deploy with Shared Cache:**
```bash
curl -X POST http://localhost:5000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deploy_gitlab": true,
    "domain": "gitlab.example.com",
    "runners": ["debian", "ubuntu", "windows-11"],
    "nfs_share": "192.168.1.100:/export/build-cache",
    "nfs_mount_path": "/mnt/cache",
    "provider": "proxmox",
    ...
  }'
```

**GitLab Runner Config (config.toml):**
```toml
[[runners]]
  name = "debian-runner"
  [runners.cache]
    Type = "local"
    Shared = true
    [runners.cache.local]
      ServerAddress = "/mnt/cache"
  [runners.docker]
    volumes = ["/mnt/cache:/cache"]
```

**CI/CD Pipeline with Cache:**
```yaml
variables:
  CACHE_DIR: "/cache"

build-frontend:
  stage: build
  cache:
    key: node-modules
    paths:
      - node_modules/
  script:
    - npm ci --cache $CACHE_DIR/npm
    - npm run build
  artifacts:
    paths:
      - dist/

build-backend:
  stage: build
  cache:
    key: maven-deps
    paths:
      - .m2/
  script:
    - mvn clean package -Dmaven.repo.local=$CACHE_DIR/maven
```

**Benefits:**
- ✅ Dependencies cached across all runners
- ✅ Faster builds (no re-downloading dependencies)
- ✅ Reduced network bandwidth usage
- ✅ Cache persists across runner restarts

---

## 3. GitLab Backup to Network Storage

Automatically store GitLab backups on network storage for disaster recovery.

### Configuration

**Deploy with Samba Backup Storage:**
```bash
curl -X POST http://localhost:5000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deploy_gitlab": true,
    "domain": "gitlab.company.com",
    "samba_share": "backup-server.company.com/gitlab-backups",
    "samba_mount_path": "/mnt/backups",
    "samba_username": "backup-user",
    "samba_password": "BackupPass123",
    "samba_domain": "COMPANY",
    "provider": "proxmox",
    ...
  }'
```

**GitLab Backup Configuration:**
```ruby
# In GitLab container/LXC
vi /etc/gitlab/gitlab.rb

# Configure backup location
gitlab_rails['backup_path'] = "/mnt/backups/gitlab"
gitlab_rails['backup_keep_time'] = 604800  # 7 days

# Reconfigure
gitlab-ctl reconfigure
```

**Automated Backup Script:**
```bash
#!/bin/bash
# /opt/gitlab-backup.sh

# Create backup
gitlab-backup create

# Verify backup was created on network storage
ls -lh /mnt/backups/gitlab/

# Optional: Sync to second location
rsync -av /mnt/backups/gitlab/ backup-user@offsite-server:/backups/gitlab/
```

**Cron Job:**
```bash
# Run daily backups at 2 AM
0 2 * * * /opt/gitlab-backup.sh >> /var/log/gitlab-backup.log 2>&1
```

**Benefits:**
- ✅ Backups automatically stored off-server
- ✅ No local disk space concerns
- ✅ Easy disaster recovery
- ✅ Centralized backup management

---

## 4. Container Registry on Shared Storage

Store Docker container images on shared storage accessible by GitLab and all runners.

### Configuration

**Deploy with NFS for Registry:**
```bash
curl -X POST http://localhost:5000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deploy_gitlab": true,
    "domain": "gitlab.company.com",
    "nfs_share": "storage.company.com:/export/docker-registry",
    "nfs_mount_path": "/mnt/registry",
    "runners": ["debian", "ubuntu"],
    "provider": "proxmox",
    ...
  }'
```

**GitLab Registry Configuration:**
```ruby
# In GitLab container
vi /etc/gitlab/gitlab.rb

# Enable container registry on shared storage
registry_external_url 'https://registry.company.com'
gitlab_rails['registry_path'] = "/mnt/registry/docker"
gitlab_rails['registry_enabled'] = true

# Reconfigure
gitlab-ctl reconfigure
```

**CI/CD Pipeline with Registry:**
```yaml
variables:
  IMAGE_TAG: $CI_REGISTRY_IMAGE:$CI_COMMIT_REF_SLUG

stages:
  - build
  - push
  - deploy

build-image:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker build -t $IMAGE_TAG .
    - docker push $IMAGE_TAG
  # Image layers stored on NFS at /mnt/registry/docker/

deploy-app:
  stage: deploy
  script:
    - docker pull $IMAGE_TAG
    - docker run -d $IMAGE_TAG
  # Fast pull from local NFS storage
```

**Benefits:**
- ✅ Fast image pulls from local network storage
- ✅ Shared image layers across runners
- ✅ No external registry costs
- ✅ Unlimited registry storage

---

## 5. GitLab Pages on NFS

Host static sites from GitLab Pages on shared storage.

### Configuration

**Deploy with Pages Storage:**
```bash
curl -X POST http://localhost:5000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deploy_gitlab": true,
    "domain": "gitlab.company.com",
    "nfs_share": "webserver.company.com:/export/pages",
    "nfs_mount_path": "/mnt/pages",
    "runners": ["debian"],
    "provider": "proxmox",
    ...
  }'
```

**GitLab Pages Configuration:**
```ruby
# In GitLab container
vi /etc/gitlab/gitlab.rb

# Configure GitLab Pages
pages_external_url "http://pages.company.com"
gitlab_pages['enable'] = true
gitlab_rails['pages_path'] = "/mnt/pages"

# Reconfigure
gitlab-ctl reconfigure
```

**CI/CD Pipeline for Pages:**
```yaml
pages:
  stage: deploy
  script:
    - npm run build
    - mkdir -p /mnt/pages/$CI_PROJECT_NAMESPACE/$CI_PROJECT_NAME
    - cp -r dist/* /mnt/pages/$CI_PROJECT_NAMESPACE/$CI_PROJECT_NAME/
  artifacts:
    paths:
      - dist/
  only:
    - main
```

**Web Server Configuration (nginx):**
```nginx
# On webserver.company.com
server {
    listen 80;
    server_name pages.company.com *.pages.company.com;

    root /export/pages;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

**Benefits:**
- ✅ Static sites served directly from NFS
- ✅ No GitLab Pages daemon needed
- ✅ Separate web server can serve pages
- ✅ Easy CDN integration

---

## 6. Large File Storage (LFS)

Store Git LFS objects on network storage to keep GitLab database lean.

### Configuration

**Deploy with LFS Storage:**
```bash
curl -X POST http://localhost:5000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deploy_gitlab": true,
    "domain": "gitlab.company.com",
    "nfs_share": "storage.company.com:/export/git-lfs",
    "nfs_mount_path": "/mnt/lfs",
    "runners": ["debian", "ubuntu", "windows-11"],
    "provider": "proxmox",
    ...
  }'
```

**GitLab LFS Configuration:**
```ruby
# In GitLab container
vi /etc/gitlab/gitlab.rb

# Configure LFS storage
gitlab_rails['lfs_enabled'] = true
gitlab_rails['lfs_storage_path'] = "/mnt/lfs/objects"

# Reconfigure
gitlab-ctl reconfigure
```

**Repository .gitattributes:**
```
# Track large files with Git LFS
*.psd filter=lfs diff=lfs merge=lfs -text
*.zip filter=lfs diff=lfs merge=lfs -text
*.bin filter=lfs diff=lfs merge=lfs -text
*.dll filter=lfs diff=lfs merge=lfs -text
*.exe filter=lfs diff=lfs merge=lfs -text
```

**Usage:**
```bash
# Clone with LFS
git lfs install
git clone git@gitlab.company.com:project/repo.git

# Add large file
cp large-file.zip repo/
cd repo
git add large-file.zip
git commit -m "Add large file"
git push

# File stored on NFS at /mnt/lfs/objects/
```

**Benefits:**
- ✅ Keep Git repository size small
- ✅ Fast access to large files from network storage
- ✅ Shared across all runners
- ✅ Easy to manage and backup

---

## 7. Complete Configuration Examples

### Example 1: Development Team Setup

**Scenario:** Small team with code, artifacts, and container images.

```bash
curl -X POST http://localhost:5000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deploy_gitlab": true,
    "domain": "gitlab.dev.company.com",
    "email": "devops@company.com",
    "admin_password": "DevSecurePass123",
    "letsencrypt_enabled": true,

    "runners": ["debian", "ubuntu", "windows-11"],

    "nfs_share": "nas.company.com:/volume1/gitlab",
    "nfs_mount_path": "/mnt/shared",

    "provider": "proxmox",
    "provider_config": {
      "host": "proxmox.company.com",
      "user": "root@pam",
      "password": "proxmox-password",
      "node": "pve1",
      "storage": "local-lvm",
      "bridge": "vmbr0"
    }
  }'
```

**Post-Deployment GitLab Config:**
```ruby
# /etc/gitlab/gitlab.rb
gitlab_rails['artifacts_path'] = "/mnt/shared/artifacts"
gitlab_rails['lfs_storage_path'] = "/mnt/shared/lfs-objects"
gitlab_rails['backup_path'] = "/mnt/shared/backups"
gitlab_rails['registry_path'] = "/mnt/shared/registry"
gitlab_rails['gitlab_shell_ssh_port'] = 2222
```

**Directory Structure:**
```
/mnt/shared/
├── artifacts/          # Build artifacts (5-10 GB typical)
├── lfs-objects/        # Large files (varies)
├── backups/           # Daily backups (20-50 GB)
├── registry/          # Docker images (10-100 GB)
└── cache/             # Shared build cache (5-20 GB)
```

---

### Example 2: Enterprise Multi-Site Setup

**Scenario:** Multiple sites with shared Windows file server.

**Central Site (with GitLab):**
```bash
curl -X POST http://localhost:5000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deploy_gitlab": true,
    "domain": "gitlab.hq.company.com",
    "email": "gitlab-admin@company.com",
    "admin_password": "EnterpriseSecure!",

    "runners": ["debian", "ubuntu", "windows-server-2022"],

    "samba_share": "fileserver.hq.company.com/gitlab-storage",
    "samba_mount_path": "/mnt/storage",
    "samba_username": "gitlab-service",
    "samba_password": "ServiceAccount123!",
    "samba_domain": "COMPANY",

    "provider": "proxmox",
    "provider_config": {...}
  }'
```

**Remote Site 1 (runners only):**
```bash
curl -X POST http://localhost:5000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deploy_gitlab": false,
    "gitlab_url": "https://gitlab.hq.company.com",

    "runners": ["windows-11", "debian"],

    "samba_share": "fileserver.hq.company.com/gitlab-storage",
    "samba_mount_path": "/mnt/storage",
    "samba_username": "gitlab-service",
    "samba_password": "ServiceAccount123!",
    "samba_domain": "COMPANY",

    "provider": "proxmox",
    "provider_config": {...}
  }'
```

**Windows Runner Access:**
```powershell
# On Windows runners, storage mounted as S:\
dir S:\artifacts
dir S:\cache
dir S:\lfs-objects

# CI/CD jobs can access directly
# .gitlab-ci.yml:
# script:
#   - Copy-Item S:\cache\dependencies\* .\deps\
#   - Build-Project
#   - Copy-Item .\output\* S:\artifacts\$CI_PROJECT_NAME\
```

---

### Example 3: High-Performance Build Farm

**Scenario:** Large codebase with heavy build requirements.

```bash
curl -X POST http://localhost:5000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deploy_gitlab": true,
    "domain": "gitlab.build.company.com",
    "email": "build-admin@company.com",
    "admin_password": "BuildFarm2024!",

    "runners": [
      "debian", "ubuntu", "rocky",
      "windows-10", "windows-11", "windows-server-2022",
      "macos"
    ],

    "nfs_share": "nvme-storage.company.com:/export/build-data",
    "nfs_mount_path": "/mnt/build",

    "samba_share": "backup.company.com/gitlab-backups",
    "samba_mount_path": "/mnt/backups",
    "samba_username": "backup-service",
    "samba_password": "BackupPass!",

    "provider": "proxmox",
    "provider_config": {
      "host": "proxmox-cluster.company.com",
      "storage": "nvme-pool",
      ...
    }
  }'
```

**GitLab Configuration for Performance:**
```ruby
# /etc/gitlab/gitlab.rb

# Use NFS for artifacts (fast read/write)
gitlab_rails['artifacts_path'] = "/mnt/build/artifacts"
gitlab_rails['artifacts_object_store_enabled'] = false

# Use NFS for registry (local network speed)
gitlab_rails['registry_path'] = "/mnt/build/registry"

# Use NFS for LFS (large files)
gitlab_rails['lfs_storage_path'] = "/mnt/build/lfs"

# Use Samba for backups (separate backup network)
gitlab_rails['backup_path'] = "/mnt/backups/gitlab"
gitlab_rails['backup_keep_time'] = 1209600  # 14 days

# Optimize for heavy concurrent builds
gitlab_rails['max_request_duration_seconds'] = 300
unicorn['worker_processes'] = 8
postgresql['shared_buffers'] = "2GB"
```

**Dedicated Cache Structure:**
```
/mnt/build/
├── artifacts/
│   └── (organized by project/pipeline)
├── cache/
│   ├── npm/              # Node.js packages
│   ├── maven/            # Java dependencies
│   ├── nuget/            # .NET packages
│   ├── gradle/           # Gradle cache
│   └── cargo/            # Rust packages
├── registry/
│   └── docker/           # Container images
└── lfs/
    └── objects/          # Large binary files
```

---

## Performance Tips

### NFS Performance Optimization

1. **Use NFSv4 for better performance:**
```bash
# On NFS server (/etc/exports)
/export/gitlab-data  192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)

# On clients (GitLab/runners)
mount -t nfs -o vers=4,rsize=1048576,wsize=1048576 nfs-server:/export/gitlab-data /mnt/shared
```

2. **Enable async for better write performance** (if data loss acceptable):
```bash
/export/gitlab-data  192.168.1.0/24(rw,async,no_subtree_check)
```

3. **Use SSD-backed storage for NFS server**

4. **Monitor NFS performance:**
```bash
nfsstat -c  # Client stats
nfsstat -s  # Server stats
```

### Samba Performance Optimization

1. **Enable SMB3 protocol:**
```bash
# In /etc/samba/smb.conf
[global]
    server min protocol = SMB3
    smb encrypt = desired
```

2. **Optimize for large files:**
```ini
[gitlab-storage]
    path = /srv/samba/gitlab
    read only = no
    socket options = TCP_NODELAY IPTOS_LOWDELAY SO_RCVBUF=65536 SO_SNDBUF=65536
    use sendfile = yes
    min receivefile size = 16384
```

3. **Use multichannel for faster transfers** (if multiple NICs)

---

## Troubleshooting

### Issue: Slow artifact uploads/downloads

**Solution:**
```bash
# Check NFS mount options
mount | grep nfs

# Remount with performance options
mount -o remount,rsize=1048576,wsize=1048576,hard,intr /mnt/shared

# Check network bandwidth
iperf3 -c nfs-server
```

### Issue: Permission denied on shared storage

**Solution:**
```bash
# On GitLab server, check mount permissions
ls -la /mnt/shared/

# Fix ownership
chown -R git:git /mnt/shared/artifacts/
chmod -R 755 /mnt/shared/artifacts/

# For NFS, check server exports
showmount -e nfs-server
```

### Issue: Stale NFS file handles

**Solution:**
```bash
# Unmount and remount
umount -f /mnt/shared
mount -t nfs nfs-server:/export/gitlab-data /mnt/shared

# Add to /etc/fstab for auto-recovery
nfs-server:/export/gitlab-data /mnt/shared nfs defaults,soft,timeo=30,retrans=3 0 0
```

---

## Security Best Practices

1. **Use read-only mounts where possible:**
```ruby
# For runners that only need to read artifacts
# Mount with ro option
```

2. **Separate sensitive data:**
```ruby
# Use different shares for different data types
gitlab_rails['artifacts_path'] = "/mnt/public-storage/artifacts"
gitlab_rails['backup_path'] = "/mnt/secure-storage/backups"
```

3. **Enable encryption:**
```ruby
# For Samba
samba_share_options = "sec=krb5,seal"

# For NFS
nfs_options = "sec=krb5p"
```

4. **Regular backups of shared storage:**
```bash
# Backup script
#!/bin/bash
rsync -avz --progress /mnt/shared/ backup-server:/backups/gitlab-shared/$(date +%Y%m%d)/
```

---

## Summary

Shared storage with GitLab provides:

✅ **Performance**: Fast local network access to artifacts and cache
✅ **Scalability**: Unlimited storage without database bloat
✅ **Efficiency**: Shared dependencies across all runners
✅ **Reliability**: Centralized backups and disaster recovery
✅ **Flexibility**: Easy migration and expansion

Choose NFS for Linux-heavy environments, Samba for Windows integration, or both for hybrid infrastructures!
