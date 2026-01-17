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
    export PLATFORM=$(jq -r '.platform' "$CONFIG_FILE")
    export OS_VERSION=$(jq -r '.os_version' "$CONFIG_FILE")

    log_success "Configuration loaded"
    log_info "Domain: $GITLAB_DOMAIN"
    log_info "Platform: $PLATFORM ($OS_VERSION)"
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

# Main deployment function
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
    destroy)
        load_config
        destroy_deployment
        ;;
    *)
        echo "BuildForever - GitLab Deployment Script"
        echo ""
        echo "Usage: $0 {init|plan|apply|deploy|destroy}"
        echo ""
        echo "Commands:"
        echo "  init    - Initialize Terraform"
        echo "  plan    - Plan Terraform changes"
        echo "  apply   - Apply Terraform changes"
        echo "  deploy  - Full deployment (init + plan + apply + ansible)"
        echo "  destroy - Destroy deployment"
        echo ""
        exit 1
        ;;
esac
