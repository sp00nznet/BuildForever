#!/bin/bash
# BuildForever Cache Clearing Script
# Clears Python bytecode, temporary files, and browser cache artifacts

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "BuildForever Cache Clearing Utility"
echo "===================================="
echo ""

# Function to clear Python cache
clear_python_cache() {
    echo "Clearing Python bytecode cache..."
    find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$PROJECT_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true
    find "$PROJECT_DIR" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    echo "  Done."
}

# Function to clear Flask cache
clear_flask_cache() {
    echo "Clearing Flask cache..."
    rm -rf "$PROJECT_DIR/gitlab-deployer/instance" 2>/dev/null || true
    rm -rf "$PROJECT_DIR/gitlab-deployer/.webassets-cache" 2>/dev/null || true
    echo "  Done."
}

# Function to clear logs
clear_logs() {
    if [ "$1" == "--include-logs" ]; then
        echo "Clearing log files..."
        rm -rf "$PROJECT_DIR/logs"/*.log 2>/dev/null || true
        echo "  Done."
    fi
}

# Function to clear temporary files
clear_temp_files() {
    echo "Clearing temporary files..."
    find "$PROJECT_DIR" -type f -name "*.tmp" -delete 2>/dev/null || true
    find "$PROJECT_DIR" -type f -name "*.bak" -delete 2>/dev/null || true
    find "$PROJECT_DIR" -type f -name "*~" -delete 2>/dev/null || true
    find "$PROJECT_DIR" -type f -name ".DS_Store" -delete 2>/dev/null || true
    rm -rf "$PROJECT_DIR/tmp" 2>/dev/null || true
    rm -rf "$PROJECT_DIR/temp" 2>/dev/null || true
    echo "  Done."
}

# Function to clear Terraform cache (optional)
clear_terraform_cache() {
    if [ "$1" == "--include-terraform" ]; then
        echo "Clearing Terraform cache..."
        rm -rf "$PROJECT_DIR/terraform/.terraform" 2>/dev/null || true
        rm -f "$PROJECT_DIR/terraform/.terraform.lock.hcl" 2>/dev/null || true
        echo "  Done."
        echo "  Note: You will need to run 'terraform init' again."
    fi
}

# Function to clear Ansible cache
clear_ansible_cache() {
    echo "Clearing Ansible cache..."
    rm -rf "$PROJECT_DIR/ansible/.ansible" 2>/dev/null || true
    find "$PROJECT_DIR/ansible" -type f -name "*.retry" -delete 2>/dev/null || true
    echo "  Done."
}

# Main execution
echo "Project directory: $PROJECT_DIR"
echo ""

clear_python_cache
clear_flask_cache
clear_temp_files
clear_ansible_cache
clear_logs "$1"
clear_terraform_cache "$1"

echo ""
echo "Cache cleared successfully!"
echo ""
echo "Options:"
echo "  --include-logs      Also clear log files"
echo "  --include-terraform Also clear Terraform cache (requires re-init)"
