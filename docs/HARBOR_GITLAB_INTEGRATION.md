# Harbor + GitLab Integration Guide

## Deployed Services

### Rancher Server
- **URL:** https://192.168.100.22:8443
- **Bootstrap Password:** `tm98swbb5xqkp7mh6k4fqlbxk4r9pqw2hfc9sv8hnthc2jpbq8c69c`
- **Location:** Running on dpiprox2 Proxmox host

### Harbor Registry
- **URL:** http://192.168.100.106
- **Username:** admin
- **Password:** L9sefm!n
- **Location:** LXC container 103 on dpiprox2

---

## Configuring GitLab CI/CD to use Harbor

### Step 1: Create a Project in Harbor

1. Log into Harbor at http://192.168.100.106
2. Click "New Project"
3. Create a project (e.g., `gitlab-builds`)
4. Note the project name for CI/CD configuration

### Step 2: Create Harbor Robot Account (Recommended)

1. In Harbor, go to your project > Robot Accounts
2. Click "+ New Robot Account"
3. Set name: `gitlab-ci`
4. Set permissions: Push, Pull
5. Copy the generated token

### Step 3: Add Harbor Credentials to GitLab

#### Option A: Project-level CI/CD Variables

In GitLab, go to your project > Settings > CI/CD > Variables:

| Variable | Value |
|----------|-------|
| `HARBOR_URL` | `192.168.100.106` |
| `HARBOR_USERNAME` | `admin` (or robot account) |
| `HARBOR_PASSWORD` | `L9sefm!n` (or robot token) - **Masked** |
| `HARBOR_PROJECT` | `gitlab-builds` |

#### Option B: Group-level Variables (for multiple projects)

Go to your GitLab Group > Settings > CI/CD > Variables and add the same variables.

### Step 4: Configure .gitlab-ci.yml

Add this to your project's `.gitlab-ci.yml`:

```yaml
variables:
  # Harbor registry configuration
  DOCKER_REGISTRY: ${HARBOR_URL}
  DOCKER_IMAGE: ${HARBOR_URL}/${HARBOR_PROJECT}/${CI_PROJECT_NAME}

stages:
  - build
  - push

# Docker-in-Docker service for building images
services:
  - docker:dind

build-image:
  stage: build
  image: docker:latest
  before_script:
    # Login to Harbor
    - echo "$HARBOR_PASSWORD" | docker login $HARBOR_URL -u "$HARBOR_USERNAME" --password-stdin
  script:
    - docker build -t $DOCKER_IMAGE:$CI_COMMIT_SHA .
    - docker tag $DOCKER_IMAGE:$CI_COMMIT_SHA $DOCKER_IMAGE:latest
  after_script:
    - docker logout $HARBOR_URL

push-image:
  stage: push
  image: docker:latest
  before_script:
    - echo "$HARBOR_PASSWORD" | docker login $HARBOR_URL -u "$HARBOR_USERNAME" --password-stdin
  script:
    - docker push $DOCKER_IMAGE:$CI_COMMIT_SHA
    - docker push $DOCKER_IMAGE:latest
  only:
    - main
    - master
  after_script:
    - docker logout $HARBOR_URL
```

### Step 5: Configure Docker Daemon for Insecure Registry (if using HTTP)

Since Harbor is running on HTTP (not HTTPS), Docker clients need to trust it.

#### On GitLab Runners:

Create or edit `/etc/docker/daemon.json`:

```json
{
  "insecure-registries": ["192.168.100.106"]
}
```

Then restart Docker:
```bash
sudo systemctl restart docker
```

#### For Docker-in-Docker in CI:

Add to your `.gitlab-ci.yml`:

```yaml
variables:
  DOCKER_TLS_CERTDIR: ""
  DOCKER_DRIVER: overlay2

services:
  - name: docker:dind
    command: ["--insecure-registry=192.168.100.106"]
```

---

## Complete Example .gitlab-ci.yml

```yaml
variables:
  DOCKER_REGISTRY: "192.168.100.106"
  DOCKER_IMAGE: "192.168.100.106/gitlab-builds/${CI_PROJECT_NAME}"
  DOCKER_TLS_CERTDIR: ""
  DOCKER_DRIVER: overlay2

stages:
  - build
  - test
  - push

services:
  - name: docker:dind
    command: ["--insecure-registry=192.168.100.106"]

.docker-login: &docker-login
  before_script:
    - echo "$HARBOR_PASSWORD" | docker login $DOCKER_REGISTRY -u "$HARBOR_USERNAME" --password-stdin

build:
  stage: build
  image: docker:latest
  <<: *docker-login
  script:
    - docker build -t $DOCKER_IMAGE:$CI_COMMIT_SHA .
    - docker save $DOCKER_IMAGE:$CI_COMMIT_SHA > image.tar
  artifacts:
    paths:
      - image.tar
    expire_in: 1 hour

test:
  stage: test
  image: docker:latest
  <<: *docker-login
  script:
    - docker load < image.tar
    - docker run --rm $DOCKER_IMAGE:$CI_COMMIT_SHA /bin/sh -c "echo 'Tests passed!'"
  dependencies:
    - build

push:
  stage: push
  image: docker:latest
  <<: *docker-login
  script:
    - docker load < image.tar
    - docker push $DOCKER_IMAGE:$CI_COMMIT_SHA
    - docker tag $DOCKER_IMAGE:$CI_COMMIT_SHA $DOCKER_IMAGE:latest
    - docker push $DOCKER_IMAGE:latest
  dependencies:
    - build
  only:
    - main
    - master
  after_script:
    - docker logout $DOCKER_REGISTRY
```

---

## Enabling HTTPS for Harbor (Recommended for Production)

To enable HTTPS on Harbor:

1. SSH to the Harbor container:
   ```bash
   ssh root@192.168.100.106
   ```

2. Generate or obtain SSL certificates

3. Edit `/opt/harbor/harbor.yml`:
   ```yaml
   hostname: harbor.yourdomain.com
   https:
     port: 443
     certificate: /your/certificate/path
     private_key: /your/private/key/path
   ```

4. Reconfigure Harbor:
   ```bash
   cd /opt/harbor
   ./prepare
   docker-compose down
   docker-compose up -d
   ```

---

## Rancher Integration with Harbor

To use Harbor as a registry in Rancher-managed Kubernetes clusters:

1. Log into Rancher at https://192.168.100.22:8443
2. Complete initial setup with bootstrap password
3. Go to Cluster Management > your cluster > More Resources > Core > Secrets
4. Create a Registry credential secret:
   - Name: `harbor-registry`
   - Registry: `192.168.100.106`
   - Username: `admin`
   - Password: `L9sefm!n`

5. In your Kubernetes deployments, reference the secret:
   ```yaml
   spec:
     imagePullSecrets:
       - name: harbor-registry
     containers:
       - name: myapp
         image: 192.168.100.106/gitlab-builds/myapp:latest
   ```

---

## Troubleshooting

### Cannot push/pull images
- Verify Harbor is running: `docker ps` on 192.168.100.106
- Check insecure registry config on client
- Verify credentials

### GitLab CI fails to login
- Check CI/CD variables are set correctly
- Ensure HARBOR_PASSWORD is masked but not protected (unless on protected branch)

### Harbor UI not accessible
- Check firewall rules
- Verify container is running: `pct exec 103 -- docker ps`
