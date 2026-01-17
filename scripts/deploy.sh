#!/bin/bash
set -e

# BuildForever - GitLab Deployment Script
# This script orchestrates the deployment of GitLab across multiple platforms

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$PROJECT_ROOT/config"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"
ANSIBLE_DIR="$PROJECT_ROOT/ansible"
LOG_DIR="$PROJECT_ROOT/logs"

# Configuration file
CONFIG_FILE="$CONFIG_DIR/deployment_config.json"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Checking requirements..."

    local missing_tools=()

    if ! command -v terraform &> /dev/null; then
        missing_tools+=("terraform")
    fi

    if ! command -v ansible &> /dev/null; then
        missing_tools+=("ansible")
    fi

    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    fi

    if ! command -v python3 &> /dev/null; then
        missing_tools+=("python3")
    fi

    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Please install the missing tools and try again."
        exit 1
    fi

    log_success "All required tools are installed"
}

load_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        log_info "Please use the web interface to configure your deployment first."
        exit 1
    fi

    log_info "Loading configuration from $CONFIG_FILE"

    # Export configuration as environment variables
    export GITLAB_DOMAIN=$(jq -r '.domain' "$CONFIG_FILE")
    export ADMIN_PASSWORD=$(jq -r '.admin_password' "$CONFIG_FILE")
    export LETSENCRYPT_EMAIL=$(jq -r '.email' "$CONFIG_FILE")
    export ENABLE_LETSENCRYPT=$(jq -r '.letsencrypt_enabled' "$CONFIG_FILE")

    # Get runners list (new for v2.0)
    export ENABLED_RUNNERS=$(jq -r '.runners | join(",")' "$CONFIG_FILE")
    RUNNER_COUNT=$(jq -r '.runners | length' "$CONFIG_FILE")

    log_success "Configuration loaded"
    log_info "Domain: $GITLAB_DOMAIN"
    log_info "Runners: $RUNNER_COUNT selected"
}

init_terraform() {
    log_info "Initializing Terraform..."
    cd "$TERRAFORM_DIR"
    terraform init
    log_success "Terraform initialized"
}

plan_terraform() {
    log_info "Planning Terraform deployment..."
    cd "$TERRAFORM_DIR"

    terraform plan \
        -var "gitlab_domain=$GITLAB_DOMAIN" \
        -var "admin_password=$ADMIN_PASSWORD" \
        -var "letsencrypt_email=$LETSENCRYPT_EMAIL" \
        -var "enable_letsencrypt=$ENABLE_LETSENCRYPT" \
        -out=tfplan

    log_success "Terraform plan created"
}

apply_terraform() {
    log_info "Applying Terraform configuration..."
    cd "$TERRAFORM_DIR"

    terraform apply tfplan

    log_success "Terraform applied successfully"
}

deploy_runners() {
    if [ -z "$ENABLED_RUNNERS" ] || [ "$ENABLED_RUNNERS" = "" ]; then
        log_info "No runners selected, skipping runner deployment"
        return 0
    fi

    log_info "Deploying GitLab runners..."
    log_info "Selected runners: $ENABLED_RUNNERS"

    cd "$TERRAFORM_DIR"

    # Convert comma-separated list to JSON array for Terraform
    RUNNERS_JSON="[\"${ENABLED_RUNNERS//,/\",\"}\"]"

    terraform plan \
        -var "gitlab_domain=$GITLAB_DOMAIN" \
        -var "admin_password=$ADMIN_PASSWORD" \
        -var "letsencrypt_email=$LETSENCRYPT_EMAIL" \
        -var "enable_letsencrypt=$ENABLE_LETSENCRYPT" \
        -var "enabled_runners=$RUNNERS_JSON" \
        -out=tfplan-runners

    terraform apply tfplan-runners

    log_success "Runners deployed successfully"
}

register_runners() {
    if [ -z "$ENABLED_RUNNERS" ] || [ "$ENABLED_RUNNERS" = "" ]; then
        log_info "No runners to register"
        return 0
    fi

    log_info "Registering runners with GitLab..."

    cd "$ANSIBLE_DIR"

    # Create deployment vars file for Ansible
    cat > vars/deployment_config.yml <<EOF
---
gitlab_domain: "$GITLAB_DOMAIN"
enabled_runners:
EOF

    # Convert comma-separated to YAML list
    IFS=',' read -ra RUNNERS <<< "$ENABLED_RUNNERS"
    for runner in "${RUNNERS[@]}"; do
        echo "  - $runner" >> vars/deployment_config.yml
    done

    # Run registration playbook
    ansible-playbook playbooks/register_runners.yml -v

    log_success "All runners registered successfully"
}

verify_runners() {
    log_info "Verifying runner connections..."

    # Give runners a moment to connect
    sleep 5

    local connected_count=$(docker exec gitlab gitlab-rails runner "puts Runner.count" 2>/dev/null || echo "0")

    log_success "$connected_count runner(s) connected to GitLab"
}

run_ansible() {
    log_info "Running Ansible playbook..."
    cd "$ANSIBLE_DIR"

    ansible-playbook playbooks/deploy_gitlab.yml \
        -e "config_file=$CONFIG_FILE" \
        -v

    log_success "Ansible playbook completed"
}

configure_letsencrypt() {
    if [ "$ENABLE_LETSENCRYPT" = "true" ]; then
        log_info "Configuring Let's Encrypt..."
        cd "$ANSIBLE_DIR"

        ansible-playbook playbooks/letsencrypt_setup.yml \
            -e "config_file=$CONFIG_FILE"

        log_success "Let's Encrypt configured"
    else
        log_info "Let's Encrypt disabled, skipping SSL configuration"
    fi
}

wait_for_gitlab() {
    log_info "Waiting for GitLab to start..."
    log_warning "This may take 5-10 minutes..."

    local max_attempts=60
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if docker exec gitlab gitlab-rake gitlab:check SANITIZE=true &> /dev/null; then
            log_success "GitLab is ready!"
            return 0
        fi

        attempt=$((attempt + 1))
        echo -n "."
        sleep 10
    done

    log_error "GitLab did not start within the expected time"
    return 1
}

display_info() {
    log_success "GitLab deployment completed!"
    echo ""
    echo "=========================================="
    echo "GitLab Access Information"
    echo "=========================================="
    echo "URL: https://$GITLAB_DOMAIN"
    echo "Username: root"
    echo "Password: [as configured]"
    echo "SSH Port: 2222"
    echo "=========================================="
    echo ""
    log_info "You can now access GitLab at https://$GITLAB_DOMAIN"
    log_info "It may take a few more minutes for all services to be fully ready"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f "$TERRAFORM_DIR/tfplan"
    log_success "Cleanup complete"
}

destroy_deployment() {
    log_warning "Destroying GitLab deployment..."
    read -p "Are you sure you want to destroy the deployment? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Deployment destruction cancelled"
        exit 0
    fi

    cd "$TERRAFORM_DIR"
    terraform destroy \
        -var "gitlab_domain=$GITLAB_DOMAIN" \
        -var "admin_password=$ADMIN_PASSWORD" \
        -var "letsencrypt_email=$LETSENCRYPT_EMAIL" \
        -var "enable_letsencrypt=$ENABLE_LETSENCRYPT" \
        -auto-approve

    log_success "Deployment destroyed"
}

# Main deployment function (GitLab only)
deploy() {
    log_info "Starting GitLab deployment..."
    echo ""

    # Create log directory
    mkdir -p "$LOG_DIR"

    # Log file
    LOG_FILE="$LOG_DIR/${GITLAB_DOMAIN}_$(date +%Y%m%d_%H%M%S).log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    check_requirements
    load_config
    init_terraform
    plan_terraform
    apply_terraform
    run_ansible
    configure_letsencrypt
    wait_for_gitlab
    display_info
    cleanup

    log_success "Deployment complete!"
}

# Full deployment function (GitLab + Runners)
deploy_all() {
    log_info "Starting GitLab Build Farm deployment..."
    echo ""

    # Create log directory
    mkdir -p "$LOG_DIR"

    # Log file
    LOG_FILE="$LOG_DIR/${GITLAB_DOMAIN}_$(date +%Y%m%d_%H%M%S).log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    check_requirements
    load_config

    # Step 1: Deploy GitLab Server
    log_info "=== Step 1/4: Deploying GitLab Server ==="
    init_terraform
    plan_terraform
    apply_terraform
    configure_letsencrypt
    wait_for_gitlab

    # Step 2: Deploy Runners
    log_info "=== Step 2/4: Deploying GitLab Runners ==="
    deploy_runners

    # Step 3: Register Runners
    log_info "=== Step 3/4: Registering Runners ==="
    register_runners

    # Step 4: Verify
    log_info "=== Step 4/4: Verifying Installation ==="
    verify_runners

    display_build_farm_info
    cleanup

    log_success "Build Farm deployment complete!"
}

display_build_farm_info() {
    log_success "GitLab Build Farm deployment completed!"
    echo ""
    echo "=========================================="
    echo "GitLab Build Farm Access Information"
    echo "=========================================="
    echo "GitLab URL: https://$GITLAB_DOMAIN"
    echo "Username: root"
    echo "Password: [as configured]"
    echo "SSH Port: 2222"
    echo ""
    echo "Runners Deployed: $RUNNER_COUNT"
    if [ -n "$ENABLED_RUNNERS" ]; then
        echo "Runner Platforms:"
        IFS=',' read -ra RUNNERS <<< "$ENABLED_RUNNERS"
        for runner in "${RUNNERS[@]}"; do
            echo "  - $runner"
        done
    fi
    echo "=========================================="
    echo ""
    log_info "You can now access GitLab at https://$GITLAB_DOMAIN"
    log_info "Check Admin Area > Runners to see your connected runners"
}

# Command line interface
case "${1:-}" in
    init)
        init_terraform
        ;;
    plan)
        load_config
        plan_terraform
        ;;
    apply)
        load_config
        apply_terraform
        ;;
    deploy)
        deploy
        ;;
    deploy-all)
        deploy_all
        ;;
    destroy)
        load_config
        destroy_deployment
        ;;
    *)
        echo "BuildForever - GitLab Build Farm Deployment Script"
        echo ""
        echo "Usage: $0 {init|plan|apply|deploy|deploy-all|destroy}"
        echo ""
        echo "Commands:"
        echo "  init       - Initialize Terraform"
        echo "  plan       - Plan Terraform changes"
        echo "  apply      - Apply Terraform changes"
        echo "  deploy     - Deploy GitLab server only"
        echo "  deploy-all - Full deployment (GitLab + Runners)"
        echo "  destroy    - Destroy deployment"
        echo ""
        exit 1
        ;;
esac
