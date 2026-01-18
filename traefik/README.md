# Traefik Reverse Proxy Configuration

BuildForever includes optional Traefik reverse proxy support for automatic SSL, load balancing, and service discovery.

## Quick Start

Enable Traefik with docker-compose:

```bash
docker-compose --profile traefik up -d
```

## Features

- **Automatic SSL**: Let's Encrypt certificates with auto-renewal
- **Service Discovery**: Automatically detects Docker containers
- **HTTP to HTTPS**: Automatic redirect
- **Security Headers**: XSS protection, HSTS, content-type sniffing protection
- **Rate Limiting**: Configurable request limits
- **Dashboard**: Web UI for monitoring (port 8080)

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
# Traefik settings
TRAEFIK_ENABLED=true
TRAEFIK_LOG_LEVEL=INFO
TRAEFIK_DASHBOARD_AUTH=admin:$apr1$xyz$hashedpassword

# Domain settings
BASE_DOMAIN=example.com
BUILDFOREVER_DOMAIN=buildforever.example.com
GITLAB_HOSTNAME=gitlab.example.com
LETSENCRYPT_EMAIL=admin@example.com
```

### Generate Dashboard Password

```bash
# Using htpasswd
htpasswd -nb admin yourpassword

# Or using Docker
docker run --rm httpd:2.4-alpine htpasswd -nb admin yourpassword
```

### Dynamic Configuration

Place additional configuration files in `traefik/dynamic/`:

- `middlewares.yml` - Security headers, rate limiting, compression
- `tls.yml` - TLS options and cipher suites
- Custom routers and services

## Architecture

```
Internet
    │
    ▼
┌─────────┐
│ Traefik │ ← Port 80/443
└────┬────┘
     │ Docker Network
     ├──────────────────┐
     ▼                  ▼
┌──────────┐     ┌──────────┐
│BuildForever│   │  GitLab  │
│  :5000   │     │   :80    │
└──────────┘     └──────────┘
```

## Endpoints

| Service | URL | Description |
|---------|-----|-------------|
| BuildForever | `https://buildforever.example.com` | Main application |
| GitLab | `https://gitlab.example.com` | GitLab instance |
| Dashboard | `https://traefik.example.com` | Traefik dashboard |

## Security Notes

1. **Dashboard Access**: The Traefik dashboard is protected by basic auth. Change the default credentials!
2. **HTTPS Only**: All HTTP traffic is redirected to HTTPS
3. **TLS 1.2+**: Only modern TLS versions are supported
4. **Rate Limiting**: Default 100 req/s with burst of 50

## Troubleshooting

### Check Traefik logs
```bash
docker-compose logs -f traefik
```

### Verify certificates
```bash
curl -vI https://your-domain.com 2>&1 | grep -i "SSL\|certificate"
```

### Test configuration
```bash
docker-compose --profile traefik config
```

## Disabling Traefik

To use BuildForever without Traefik:

```bash
# Run without traefik profile
docker-compose up -d

# Or set in .env
TRAEFIK_ENABLED=false
```

GitLab will then handle its own Let's Encrypt certificates.
