# BuildForever - Deployment Guide

## Overview

BuildForever automates GitLab deployment across multiple platforms using a web interface, Terraform for infrastructure provisioning, and Ansible for configuration management.

## Deployment Process

### 1. Configure Deployment

Access the web interface at `http://localhost:5000` and provide:

- **Platform**: Windows, Linux, or macOS
- **OS Version**: Specific version (e.g., Ubuntu, Windows 11)
- **Domain**: Your GitLab domain (e.g., `gitlab.example.com`)
- **Email**: Email for Let's Encrypt SSL certificates
- **Admin Password**: GitLab root user password (minimum 8 characters)
- **Let's Encrypt**: Enable/disable automatic SSL

### 2. DNS Configuration

Before deployment, ensure your domain points to the server:

```bash
# Check DNS resolution
nslookup gitlab.example.com

# Should return your server's IP address
```

### 3. Start Deployment

Click "Deploy GitLab" in the web interface. The deployment process includes:

1. **Validation**: Checks configuration and requirements
2. **Terraform Init**: Initializes infrastructure provider
3. **Terraform Plan**: Creates deployment plan
4. **Terraform Apply**: Provisions GitLab container
5. **Ansible Provisioning**: Configures the system
6. **Let's Encrypt**: Sets up SSL certificates (if enabled)
7. **Verification**: Waits for GitLab to be ready

### 4. Deployment Timeline

- **Initial setup**: 2-3 minutes
- **Container deployment**: 3-5 minutes
- **GitLab initialization**: 10-15 minutes
- **Total time**: 15-30 minutes

## Manual Deployment (CLI)

For advanced users or automation, use the CLI:

### Full Deployment
```bash
./scripts/deploy.sh deploy
```

### Step-by-Step Deployment
```bash
# Initialize Terraform
./scripts/deploy.sh init

# Plan changes
./scripts/deploy.sh plan

# Apply infrastructure
./scripts/deploy.sh apply
```

### Destroy Deployment
```bash
./scripts/deploy.sh destroy
```

## Post-Deployment

### Access GitLab

1. Navigate to `https://your-domain.com`
2. Username: `root`
3. Password: [as configured during deployment]

### Initial Configuration

After first login:

1. **Change root password** (if needed)
2. **Configure email settings** in Admin Area → Settings → Email
3. **Create groups and projects**
4. **Add users** in Admin Area → Users
5. **Configure runners** for CI/CD

### SSL Certificate

If Let's Encrypt is enabled:
- Certificates are automatically generated
- Auto-renewal is configured
- Certificates renew every 60 days

To manually renew:
```bash
docker exec gitlab gitlab-ctl renew-le-certs
```

## Platform-Specific Notes

### Windows

- Requires Hyper-V and Windows Containers
- May require system reboot during deployment
- Docker Desktop must be running

### Linux

- Requires Docker Engine
- User must be in docker group
- Firewall rules may need configuration

### macOS

- Requires Docker Desktop
- May need to approve security prompts
- Performance depends on Docker Desktop allocation

## Monitoring Deployment

### Web Interface

The web interface shows real-time deployment logs and status.

### CLI Logs

Logs are saved to:
```
logs/[domain]_[timestamp].log
```

### GitLab Container Logs

```bash
docker logs -f gitlab
```

### Check GitLab Status

```bash
docker exec gitlab gitlab-rake gitlab:check
```

## Backup and Restore

### Create Backup

```bash
docker exec gitlab gitlab-backup create
```

Backups are stored in `/var/opt/gitlab/backups` inside the container.

### Restore Backup

```bash
# Stop processes
docker exec gitlab gitlab-ctl stop puma
docker exec gitlab gitlab-ctl stop sidekiq

# Restore
docker exec gitlab gitlab-backup restore BACKUP=[timestamp]

# Restart
docker exec gitlab gitlab-ctl restart
```

## Upgrading GitLab

```bash
# Pull latest image
docker pull gitlab/gitlab-ce:latest

# Stop and remove old container
docker stop gitlab
docker rm gitlab

# Redeploy with same configuration
./scripts/deploy.sh deploy
```

## Troubleshooting

### GitLab Not Starting

Check container status:
```bash
docker ps -a
docker logs gitlab
```

### SSL Certificate Issues

Check Let's Encrypt logs:
```bash
docker exec gitlab cat /var/log/gitlab/gitlab-rails/production.log | grep -i letsencrypt
```

### Performance Issues

Increase resource allocation:
1. Edit `terraform/variables.tf`
2. Increase `unicorn_workers` and `shared_buffers`
3. Redeploy

### Network Issues

Ensure ports are accessible:
```bash
# Test HTTP
curl http://localhost:80

# Test HTTPS
curl https://localhost:443

# Test SSH
nc -zv localhost 2222
```

## Security Recommendations

1. **Use strong passwords** (minimum 12 characters)
2. **Enable 2FA** for all users
3. **Regular backups** (daily recommended)
4. **Keep GitLab updated** to latest version
5. **Configure firewall** to restrict access
6. **Monitor logs** for suspicious activity
7. **Use SSH keys** instead of passwords for Git operations

## Advanced Configuration

### Custom GitLab Configuration

Edit `terraform/templates/gitlab.rb.tpl` and add custom settings:

```ruby
# SMTP settings
gitlab_rails['smtp_enable'] = true
gitlab_rails['smtp_address'] = "smtp.example.com"
gitlab_rails['smtp_port'] = 587

# Registry settings
registry_external_url 'https://registry.example.com'
```

### Multiple Instances

Deploy multiple GitLab instances by using different domains and container names.

## Support

For issues and questions:
- GitHub Issues: https://github.com/sp00nznet/BuildForever/issues
- GitLab Documentation: https://docs.gitlab.com
