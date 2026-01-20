"""Flask routes for GitLab Build Farm Deployer"""
from flask import Blueprint, render_template, request, jsonify, session, make_response
import subprocess
import json
import os
import time
import threading
from pathlib import Path
from functools import wraps
from .models import SavedConfig, DeploymentHistory, SSHKey, Credential, init_db

bp = Blueprint('main', __name__)

# Global provisioning status tracker
provisioning_status = {}
provisioning_lock = threading.Lock()


def check_gitlab_server(url, timeout=10):
    """Check if a GitLab server is accessible and responding"""
    try:
        import requests
    except ImportError:
        return False, "requests library not installed. Run: pip install requests"
    try:
        # Try to access GitLab's health endpoint
        health_url = f"{url.rstrip('/')}/api/v4/version"
        response = requests.get(health_url, timeout=timeout, verify=False)
        if response.status_code == 200:
            version_data = response.json()
            return True, f"GitLab {version_data.get('version', 'unknown')} detected"
        elif response.status_code == 401:
            # Unauthorized but server is responding
            return True, "GitLab server detected (authentication required)"
        else:
            return False, f"Server responded with status {response.status_code}"
    except requests.exceptions.SSLError:
        # SSL error but server exists - try without verification
        try:
            response = requests.get(f"{url.rstrip('/')}/api/v4/version", timeout=timeout, verify=False)
            if response.status_code in [200, 401]:
                return True, "GitLab server detected (SSL verification disabled)"
        except:
            pass
        return False, "SSL error - server may not be GitLab"
    except requests.exceptions.ConnectionError:
        return False, "Connection refused - server not accessible"
    except requests.exceptions.Timeout:
        return False, "Connection timeout - server not responding"
    except Exception as e:
        return False, f"Error: {str(e)}"


def no_cache(f):
    """Decorator to add no-cache headers to responses"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return decorated_function


@bp.after_request
def add_cache_headers(response):
    """Add no-cache headers to all API responses"""
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

SUPPORTED_RUNNERS = {
    'windows-10': {'name': 'Windows 10', 'tags': 'windows,windows-10,desktop'},
    'windows-11': {'name': 'Windows 11', 'tags': 'windows,windows-11,desktop'},
    'windows-server-2022': {'name': 'Windows Server 2022', 'tags': 'windows,server,2022'},
    'windows-server-2025': {'name': 'Windows Server 2025', 'tags': 'windows,server,2025'},
    'debian': {'name': 'Debian', 'tags': 'linux,debian'},
    'ubuntu': {'name': 'Ubuntu', 'tags': 'linux,ubuntu'},
    'arch': {'name': 'Arch Linux', 'tags': 'linux,arch'},
    'rocky': {'name': 'Rocky Linux', 'tags': 'linux,rocky,rhel'},
    'macos': {'name': 'macOS', 'tags': 'macos,darwin'}
}

@bp.route('/')
def index():
    """Main deployment interface"""
    return render_template('index.html')

@bp.route('/api/deploy', methods=['POST'])
def deploy():
    """Handle GitLab + Runners deployment request"""
    data = request.json

    # Check if GitLab deployment is requested
    deploy_gitlab = data.get('deploy_gitlab', True)
    gitlab_url = data.get('gitlab_url', '')
    runner_token = data.get('runner_token', '')

    # Validate required fields based on deployment mode
    if deploy_gitlab:
        required_fields = ['domain', 'admin_password', 'email']
    else:
        # If not deploying GitLab, we need either an existing GitLab URL or just runners
        required_fields = []
        if gitlab_url:
            # Validate GitLab URL format
            if not gitlab_url.startswith(('http://', 'https://')):
                return jsonify({
                    'success': False,
                    'error': 'GitLab URL must start with http:// or https://'
                }), 400
        # For runners-only deployment, domain is used for identification only
        if not data.get('domain'):
            data['domain'] = f"runners-{int(time.time())}"

    missing_fields = [field for field in required_fields if not data.get(field)]

    if missing_fields:
        return jsonify({
            'success': False,
            'error': f'Missing required fields: {", ".join(missing_fields)}'
        }), 400

    runners = data.get('runners', [])

    # Validate at least one runner is selected
    if not runners:
        return jsonify({
            'success': False,
            'error': 'At least one runner must be selected'
        }), 400

    # Validate runners
    invalid_runners = [r for r in runners if r not in SUPPORTED_RUNNERS]
    if invalid_runners:
        return jsonify({
            'success': False,
            'error': f'Invalid runners: {", ".join(invalid_runners)}'
        }), 400

    # Validate provider if not docker
    provider = data.get('provider', 'docker')
    provider_config = data.get('provider_config', {})

    if provider != 'docker':
        # Validate provider connection settings
        if provider == 'proxmox':
            required_provider_fields = ['host', 'user', 'password']
        else:
            return jsonify({
                'success': False,
                'error': f'Unsupported provider: {provider}'
            }), 400

        missing_provider_fields = [f for f in required_provider_fields if not provider_config.get(f)]
        if missing_provider_fields:
            return jsonify({
                'success': False,
                'error': f'Missing provider settings: {", ".join(missing_provider_fields)}'
            }), 400

    # Save deployment configuration
    config = {
        'domain': data['domain'],
        'admin_password': data.get('admin_password', ''),
        'email': data.get('email', ''),
        'letsencrypt_enabled': data.get('letsencrypt_enabled', True),
        'runners': runners,
        # Provider settings
        'provider': provider,
        'provider_config': provider_config,
        # Network settings (static IP configuration)
        'network_config': data.get('network_config', {'use_dhcp': True}),
        # Credential for VM/container injection
        'credential_id': data.get('credential_id'),
        # Traefik settings
        'traefik_enabled': data.get('traefik_enabled', False),
        'base_domain': data.get('base_domain', ''),
        'traefik_dashboard': data.get('traefik_dashboard', True),
        # GitLab deployment settings
        'deploy_gitlab': deploy_gitlab,
        'gitlab_url': gitlab_url,
        'runner_token': runner_token,
        # Shared storage settings
        'nfs_share': data.get('nfs_share', ''),
        'nfs_mount_path': data.get('nfs_mount_path', '/mnt/shared'),
        'samba_share': data.get('samba_share', ''),
        'samba_mount_path': data.get('samba_mount_path', '/mnt/samba'),
        'samba_username': data.get('samba_username', ''),
        'samba_password': data.get('samba_password', ''),
        'samba_domain': data.get('samba_domain', '')
    }

    # Save config to file for deployment script
    config_dir = Path(__file__).parent.parent.parent / 'config'
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / 'deployment_config.json'

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    # Create deployment plan
    deployment_steps = []

    # Add Traefik deployment step if enabled
    if config['traefik_enabled'] and deploy_gitlab:
        deployment_steps.append('Deploy Traefik Reverse Proxy')
        deployment_steps.append('Configure Traefik SSL certificates')

    # Add GitLab deployment steps if requested
    if deploy_gitlab:
        deployment_steps.extend([
            'Deploy GitLab Server',
            'Configure SSL with Let\'s Encrypt' if config['letsencrypt_enabled'] and not config['traefik_enabled'] else 'Configure GitLab',
            'Wait for GitLab initialization',
            'Obtain runner registration token'
        ])
    elif gitlab_url:
        deployment_steps.extend([
            'Verify GitLab server accessibility',
            'Obtain runner registration token from existing GitLab'
        ])
    else:
        deployment_steps.append('Deploy runners without GitLab registration')

    # Add shared storage mounting steps
    if config.get('nfs_share'):
        deployment_steps.append('Configure NFS shared storage on all instances')
    if config.get('samba_share'):
        deployment_steps.append('Configure Samba/CIFS shared storage on all instances')

    for runner_id in runners:
        runner_name = SUPPORTED_RUNNERS[runner_id]['name']
        deployment_steps.append(f'Deploy {runner_name} runner')
        if deploy_gitlab or gitlab_url:
            deployment_steps.append(f'Register {runner_name} runner to GitLab')

    if deploy_gitlab or gitlab_url:
        deployment_steps.append('Verify all runners are connected')
    deployment_steps.append('Deployment complete')

    # Store in session for status tracking
    session['deployment_id'] = data['domain']
    session['deployment_steps'] = deployment_steps

    # Generate deployment message
    if deploy_gitlab:
        message = f'Deployment plan created: GitLab Server + {len(runners)} runner(s)'
        estimated_time = f'{15 + len(runners) * 5}-{30 + len(runners) * 10} minutes'
    elif gitlab_url:
        message = f'Deployment plan created: {len(runners)} runner(s) connecting to existing GitLab'
        estimated_time = f'{5 + len(runners) * 5}-{10 + len(runners) * 10} minutes'
    else:
        message = f'Deployment plan created: {len(runners)} standalone runner(s)'
        estimated_time = f'{5 + len(runners) * 5}-{10 + len(runners) * 10} minutes'

    return jsonify({
        'success': True,
        'message': message,
        'deployment_id': data['domain'],
        'deployment_plan': {
            'steps': deployment_steps,
            'estimated_time': estimated_time
        }
    })


@bp.route('/api/test-gitlab', methods=['POST'])
def test_gitlab():
    """Test connectivity to an existing GitLab server"""
    data = request.json
    gitlab_url = data.get('gitlab_url', '')

    if not gitlab_url:
        return jsonify({
            'success': False,
            'error': 'GitLab URL is required'
        }), 400

    if not gitlab_url.startswith(('http://', 'https://')):
        return jsonify({
            'success': False,
            'error': 'GitLab URL must start with http:// or https://'
        }), 400

    is_accessible, message = check_gitlab_server(gitlab_url)

    return jsonify({
        'success': is_accessible,
        'message': message,
        'gitlab_url': gitlab_url
    })


@bp.route('/api/provision-gitlab', methods=['POST'])
def provision_gitlab_manual():
    """Manually trigger GitLab installation on an existing container."""
    data = request.json
    provider_config = data.get('provider_config', {})
    vmid = data.get('vmid')
    domain = data.get('domain', 'gitlab.local')
    admin_password = data.get('admin_password', 'changeme')

    if not vmid:
        return jsonify({
            'success': False,
            'error': 'VMID is required'
        }), 400

    if not provider_config.get('host') or not provider_config.get('password'):
        return jsonify({
            'success': False,
            'error': 'Proxmox host and password are required'
        }), 400

    try:
        from .proxmox_client import ProxmoxClient, get_gitlab_install_script

        client = ProxmoxClient(
            host=provider_config['host'],
            user=provider_config.get('user', 'root@pam'),
            password=provider_config['password'],
            verify_ssl=provider_config.get('verify_ssl', False)
        )
        client.connect()  # MUST connect before using!

        # Get the node where the container is running - try to auto-detect
        nodes = client.get_nodes()
        node = provider_config.get('node', '')
        if not node or node not in nodes:
            node = nodes[0] if nodes else 'pve'

        # Generate and run the GitLab install script
        script = get_gitlab_install_script(
            domain=domain,
            admin_password=admin_password,
            letsencrypt_email=None,
            storage_config={}
        )

        print(f"[PROVISION-MANUAL] Starting GitLab installation on VMID {vmid}...")
        result = client.provision_container(node, vmid, script)

        if result.get('success'):
            print(f"[PROVISION-MANUAL] GitLab installation COMPLETE")
            return jsonify({
                'success': True,
                'message': f'GitLab installation completed on VMID {vmid}',
                'output': result.get('output', '')[:2000]  # Truncate output
            })
        else:
            print(f"[PROVISION-MANUAL] GitLab installation FAILED: {result.get('error')}")
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error'),
                'exit_code': result.get('exit_code')
            }), 500

    except Exception as e:
        print(f"[PROVISION-MANUAL] Exception: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/test-ssh', methods=['POST'])
def test_ssh():
    """Test SSH connection to Proxmox host."""
    data = request.json
    host = data.get('host')
    password = data.get('password')
    vmid = data.get('vmid')

    if not host or not password:
        return jsonify({'success': False, 'error': 'Host and password required'})

    try:
        import paramiko
    except ImportError:
        return jsonify({'success': False, 'error': 'paramiko not installed'})

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username='root', password=password, timeout=10)

        # Test basic command
        stdin, stdout, stderr = ssh.exec_command('hostname')
        hostname = stdout.read().decode().strip()

        # If vmid provided, test pct exec
        if vmid:
            stdin, stdout, stderr = ssh.exec_command(f'pct exec {vmid} -- echo "test"')
            exit_code = stdout.channel.recv_exit_status()
            pct_output = stdout.read().decode().strip()
            pct_error = stderr.read().decode().strip()
            ssh.close()
            return jsonify({
                'success': exit_code == 0,
                'hostname': hostname,
                'pct_exit_code': exit_code,
                'pct_output': pct_output,
                'pct_error': pct_error
            })

        ssh.close()
        return jsonify({'success': True, 'hostname': hostname, 'message': 'SSH works'})

    except paramiko.AuthenticationException as e:
        return jsonify({'success': False, 'error': f'SSH auth failed: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/api/provisioning-status', methods=['GET'])
def get_provisioning_status():
    """Get the current provisioning status for all VMs."""
    with provisioning_lock:
        return jsonify({
            'success': True,
            'status': dict(provisioning_status)
        })


@bp.route('/api/provisioning-status/<int:vmid>', methods=['GET'])
def get_vm_provisioning_status(vmid):
    """Get provisioning status for a specific VM."""
    with provisioning_lock:
        status = provisioning_status.get(vmid, {'status': 'unknown'})
        return jsonify({
            'success': True,
            'vmid': vmid,
            'status': status
        })


@bp.route('/api/execute-deployment', methods=['POST'])
def execute_deployment():
    """Execute the full deployment (GitLab + Runners)"""
    data = request.json
    deployment_id = data.get('deployment_id')

    if not deployment_id:
        return jsonify({
            'success': False,
            'error': 'No deployment ID provided'
        }), 400

    # Load deployment config
    config_dir = Path(__file__).parent.parent.parent / 'config'
    config_file = config_dir / 'deployment_config.json'

    if not config_file.exists():
        return jsonify({
            'success': False,
            'error': 'No deployment configuration found. Please configure deployment first.'
        }), 400

    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to load deployment config: {str(e)}'
        }), 500

    provider = config.get('provider', 'docker')

    try:
        if provider == 'docker':
            return execute_docker_deployment(config, deployment_id)
        elif provider == 'proxmox':
            return execute_proxmox_deployment(config, deployment_id)
        else:
            return jsonify({
                'success': False,
                'error': f'Unsupported provider: {provider}'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def execute_docker_deployment(config, deployment_id):
    """Deploy GitLab and runners using Docker"""
    import shutil

    # Check if Docker is available
    docker_cmd = shutil.which('docker')
    if not docker_cmd:
        return jsonify({
            'success': False,
            'error': 'Docker is not installed or not in PATH. Please install Docker Desktop first.'
        }), 400

    # Check if docker-compose is available
    compose_cmd = shutil.which('docker-compose') or shutil.which('docker')

    try:
        # Test Docker connection
        result = subprocess.run(
            [docker_cmd, 'info'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return jsonify({
                'success': False,
                'error': 'Docker is not running. Please start Docker Desktop.'
            }), 400

        # For now, return success with instructions
        # Full docker-compose deployment would go here
        return jsonify({
            'success': True,
            'message': 'Docker deployment initialized successfully',
            'output': f'''Docker deployment ready for: {config.get("domain")}

To complete deployment:
1. Docker is installed and running ✓
2. Run 'docker-compose up -d' in the project directory
3. GitLab will be available at https://{config.get("domain")}

Selected runners: {", ".join(config.get("runners", [])) or "None"}
Traefik enabled: {config.get("traefik_enabled", False)}
''',
            'runner_urls': []
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Docker command timed out. Is Docker running?'
        }), 500
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': 'Docker executable not found. Please install Docker Desktop.'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Docker deployment failed: {str(e)}'
        }), 500


def execute_proxmox_deployment(config, deployment_id):
    """Deploy GitLab and runners to Proxmox VE with full provisioning."""
    import threading

    # Import proxmox_client with proper error handling for missing dependencies
    try:
        from .proxmox_client import (
            ProxmoxClient, get_gitlab_install_script, get_runner_install_script,
            get_linux_credential_script, get_windows_credential_script,
            get_windows_ssh_key_script, get_macos_credential_script
        )
    except ImportError as e:
        missing_module = str(e)
        return jsonify({
            'success': False,
            'error': f'Missing required library: {missing_module}. Please install dependencies with: pip install proxmoxer paramiko requests'
        }), 500

    provider_config = config.get('provider_config', {})

    if not provider_config.get('host'):
        return jsonify({
            'success': False,
            'error': 'Proxmox host not configured. Please test connection first.'
        }), 400

    try:
        # Create client and connect
        client = ProxmoxClient(
            host=provider_config.get('host'),
            port=provider_config.get('port', 8006),
            user=provider_config.get('user'),
            password=provider_config.get('password'),
            verify_ssl=provider_config.get('verify_ssl', False)
        )
        client.connect()

        # Get target node
        nodes = client.get_nodes()
        target_node = provider_config.get('node', '')
        selected_node = target_node if target_node in nodes else (nodes[0] if nodes else None)

        if not selected_node:
            return jsonify({
                'success': False,
                'error': 'No Proxmox node available'
            }), 400

        storage = provider_config.get('storage', 'local-lvm')
        bridge = provider_config.get('bridge', 'vmbr0')
        runners = config.get('runners', [])
        domain = config.get('domain', 'gitlab.local')
        admin_password = config.get('admin_password', 'changeme')
        email = config.get('email', '')

        # Get GitLab deployment settings
        deploy_gitlab = config.get('deploy_gitlab', True)
        gitlab_url = config.get('gitlab_url', '')
        runner_token = config.get('runner_token', '')

        # Get shared storage configuration
        storage_config = {
            'nfs_share': config.get('nfs_share', ''),
            'nfs_mount_path': config.get('nfs_mount_path', '/mnt/shared'),
            'samba_share': config.get('samba_share', ''),
            'samba_mount_path': config.get('samba_mount_path', '/mnt/samba'),
            'samba_username': config.get('samba_username', ''),
            'samba_password': config.get('samba_password', ''),
            'samba_domain': config.get('samba_domain', '')
        }

        # Get deployment credential if specified
        deploy_credential = None
        credential_id = config.get('credential_id')
        if credential_id:
            deploy_credential = Credential.get_by_id(credential_id, include_secrets=True)

        # Get network configuration
        network_config = config.get('network_config', {'use_dhcp': True})
        use_dhcp = network_config.get('use_dhcp', True)
        network_gateway = network_config.get('gateway', '')
        network_dns = network_config.get('dns', '8.8.8.8')
        ip_assignments = network_config.get('ip_assignments', {})

        def get_ip_config(host_key):
            """Get IP configuration for a host (returns 'dhcp' or 'ip/cidr' - without gateway)"""
            if use_dhcp or host_key not in ip_assignments:
                return 'dhcp'
            ip = ip_assignments[host_key]
            # If IP doesn't have CIDR notation, add /24
            if '/' not in ip:
                ip = f'{ip}/24'
            # Note: gateway is passed separately to create_container/create_vm
            return ip

        # Track created resources
        created = []
        errors = []

        # Determine GitLab URL based on deployment mode
        if not deploy_gitlab and gitlab_url:
            # Use existing GitLab server
            final_gitlab_url = gitlab_url
        elif deploy_gitlab:
            # Will deploy GitLab, construct URL
            final_gitlab_url = f'https://{domain}'
        else:
            # No GitLab (standalone runners)
            final_gitlab_url = None

        # =====================================================================
        # Step 1: Create GitLab Server (LXC Container) - Only if deploy_gitlab is True
        # =====================================================================
        print(f"[DEPLOY] deploy_gitlab={deploy_gitlab}")
        if deploy_gitlab:
          print(f"[DEPLOY] Creating GitLab container...")
          try:
            gitlab_vmid = client.get_next_vmid()

            # Check for Debian template, download if needed
            templates = client.get_available_templates(selected_node, 'local')
            debian_template = None
            for t in templates:
                if 'debian' in t.get('volid', '').lower():
                    debian_template = t['volid']
                    break

            if not debian_template:
                # Download template
                debian_template = 'local:vztmpl/debian-12-standard_12.2-1_amd64.tar.zst'

            # Get IP config for GitLab
            gitlab_ip_config = get_ip_config('gitlab')

            # Debug logging for static IP
            print(f"[DEBUG] Network config: use_dhcp={use_dhcp}, ip_assignments={ip_assignments}")
            print(f"[DEBUG] GitLab IP config: {gitlab_ip_config}, gateway: {network_gateway}")

            # Create GitLab container
            result = client.create_container(
                node=selected_node,
                vmid=gitlab_vmid,
                hostname=f'gitlab-{deployment_id.replace(".", "-")}',
                ostemplate=debian_template,
                storage=storage,
                rootfs_size=50,
                cores=4,
                memory=8192,
                bridge=bridge,
                ip=gitlab_ip_config,
                gateway=network_gateway if gitlab_ip_config != 'dhcp' else None,
                password='root1',
                start=True
            )

            if result['success']:
                created.append({
                    'vmid': gitlab_vmid,
                    'name': 'GitLab Server',
                    'type': 'lxc',
                    'status': 'created',
                    'ip_config': gitlab_ip_config,
                    'resources': '4 CPU, 8GB RAM, 50GB disk'
                })

                # Get container IP (for display purposes)
                gitlab_ip = client.get_container_ip(selected_node, gitlab_vmid)
                if gitlab_ip:
                    created[-1]['ip'] = gitlab_ip

                # Provision GitLab SYNCHRONOUSLY - no background thread
                print(f"[PROVISION] Starting GitLab provisioning for VMID {gitlab_vmid}...")

                # First inject credentials if specified
                if deploy_credential:
                    print(f"[PROVISION] Injecting credentials for user {deploy_credential['username']}...")
                    cred_script = get_linux_credential_script(
                        username=deploy_credential['username'],
                        password=deploy_credential.get('password'),
                        ssh_public_key=deploy_credential.get('ssh_public_key')
                    )
                    cred_result = client.provision_container(selected_node, gitlab_vmid, cred_script)
                    if not cred_result.get('success'):
                        print(f"[PROVISION] Credential injection failed: {cred_result.get('error')}")
                    else:
                        print(f"[PROVISION] Credentials injected successfully")
                    created[-1]['credential'] = deploy_credential['name']

                # Install GitLab
                print(f"[PROVISION] Installing GitLab (this may take 10-15 minutes)...")
                script = get_gitlab_install_script(
                    domain=domain,
                    admin_password=admin_password,
                    letsencrypt_email=email if config.get('letsencrypt_enabled') else None,
                    storage_config=storage_config
                )
                # GitLab install takes 10-15 minutes - use 30 minute timeout
                prov_result = client.provision_container(selected_node, gitlab_vmid, script, timeout=1800)
                if prov_result.get('success'):
                    print(f"[PROVISION] GitLab installation COMPLETE for VMID {gitlab_vmid}")
                    created[-1]['status'] = 'running'
                else:
                    error_msg = prov_result.get('error', 'Unknown error')
                    print(f"[PROVISION] GitLab installation FAILED: {error_msg}")
                    created[-1]['status'] = 'provisioning_failed'
                    errors.append(f"GitLab provisioning failed: {error_msg}")
                # Include log in response
                created[-1]['provision_log'] = prov_result.get('log', [])
                created[-1]['provision_log_file'] = prov_result.get('log_file', '')
            else:
                errors.append(f'GitLab Server: {result.get("error", "Creation failed")}')

          except Exception as e:
            errors.append(f'GitLab Server: {str(e)}')

        # =====================================================================
        # Step 2: Create Runner VMs/Containers
        # =====================================================================

        for runner in runners:
            try:
                runner_vmid = client.get_next_vmid()
                runner_name = f'runner-{runner}-{runner_vmid}'
                runner_config = client.RUNNER_RESOURCES.get(runner, {})

                is_linux = runner in ['debian', 'ubuntu', 'arch', 'rocky']
                is_windows = runner.startswith('windows')
                is_macos = runner == 'macos'

                if is_linux:
                    # Create LXC container for Linux runner
                    template_name = client.CT_TEMPLATES.get(runner)
                    ostemplate = f'local:vztmpl/{template_name}'

                    # Get IP config for this runner
                    runner_ip_config = get_ip_config(runner)

                    result = client.create_container(
                        node=selected_node,
                        vmid=runner_vmid,
                        hostname=runner_name,
                        ostemplate=ostemplate,
                        storage=storage,
                        rootfs_size=runner_config.get('disk', 40),
                        cores=runner_config.get('cores', 2),
                        memory=runner_config.get('memory', 4096),
                        bridge=bridge,
                        ip=runner_ip_config,
                        gateway=network_gateway if runner_ip_config != 'dhcp' else None,
                        password='root1',
                        start=True
                    )

                    if result['success']:
                        created.append({
                            'vmid': runner_vmid,
                            'name': runner_name,
                            'type': 'lxc',
                            'os': runner,
                            'status': 'created',
                            'ip_config': runner_ip_config,
                            'resources': f'{runner_config.get("cores", 2)} CPU, {runner_config.get("memory", 4096)//1024}GB RAM, {runner_config.get("disk", 40)}GB disk'
                        })

                        # Provision runner in background
                        def provision_runner(vmid, rtype, cred):
                            ip = client.get_container_ip(selected_node, vmid)
                            if ip:
                                # First inject credentials if specified
                                if cred:
                                    cred_script = get_linux_credential_script(
                                        username=cred['username'],
                                        password=cred.get('password'),
                                        ssh_public_key=cred.get('ssh_public_key')
                                    )
                                    client.provision_container(selected_node, vmid, cred_script)

                                # Then install runner
                                # Note: registration_token would come from GitLab API after it's running
                                script = get_runner_install_script(
                                    rtype,
                                    final_gitlab_url if final_gitlab_url else '',
                                    'REGISTRATION_TOKEN' if final_gitlab_url else '',
                                    storage_config
                                )
                                client.provision_container(selected_node, vmid, script)

                        thread = threading.Thread(
                            target=provision_runner,
                            args=(runner_vmid, runner, deploy_credential),
                            daemon=True
                        )
                        thread.start()
                        created[-1]['status'] = 'provisioning'
                        if deploy_credential:
                            created[-1]['credential'] = deploy_credential['name']
                    else:
                        errors.append(f'{runner}: {result.get("error", "Creation failed")}')

                elif is_windows:
                    # Get IP config for Windows runner (DHCP for runners by default)
                    runner_ip_config = get_ip_config(runner)
                    runner_static_ip = None
                    if runner_ip_config != 'dhcp':
                        # IP config is now just "192.168.1.10/24" (gateway passed separately)
                        runner_static_ip = runner_ip_config

                    # Get credentials for Windows unattended install
                    win_username = deploy_credential['username'] if deploy_credential else 'Admin'
                    win_password = deploy_credential.get('password', 'BuildForever!') if deploy_credential else 'BuildForever!'

                    # Check if user selected a specific ISO for this Windows version
                    windows_isos = provider_config.get('windows_isos', {})
                    user_selected_iso = windows_isos.get(runner, '')
                    iso_storage = provider_config.get('iso_storage', 'local')
                    # Get VirtIO drivers ISO (applies to all Windows VMs)
                    virtio_iso = provider_config.get('virtio_iso', '')
                    windows_iso = None
                    windows_answer_iso = None
                    iso_source = 'none'

                    if user_selected_iso:
                        # User selected an ISO from Proxmox storage
                        # Create an ISO with autounattend.xml for unattended installation
                        windows_iso = user_selected_iso
                        iso_source = 'user-selected'

                        # Create autounattend ISO for unattended install
                        answer_result = client.create_windows_answer_iso(
                            node=selected_node,
                            storage=iso_storage,
                            windows_type=runner,
                            username=win_username,
                            password=win_password,
                            static_ip=runner_static_ip,
                            gateway=network_gateway if runner_static_ip else None,
                            dns=network_dns
                        )
                        if answer_result.get('success'):
                            windows_answer_iso = answer_result.get('answer_iso')
                            iso_source = 'user-selected+autounattend'
                    else:
                        # No ISO selected - try to create unattended Windows ISO with credentials baked in
                        # This requires 7z and other tools on the Proxmox host
                        print(f"[DEBUG] No ISO selected for {runner}, attempting to create unattended ISO...")
                        iso_result = client.create_unattended_windows_iso(
                            node=selected_node,
                            storage=iso_storage,
                            windows_type=runner,
                            username=win_username,
                            password=win_password,
                            gitlab_url=gitlab_url,
                            runner_token=runner_token if runner_token else None,
                            static_ip=runner_static_ip,
                            gateway=network_gateway if runner_static_ip else None,
                            dns=network_dns
                        )
                        if iso_result.get('success'):
                            windows_iso = iso_result.get('iso')
                            iso_source = 'auto-created'
                        else:
                            windows_iso = None
                            iso_source = 'no-iso-selected'
                            print(f"[WARNING] No ISO selected for {runner} and auto-creation failed: {iso_result.get('error', 'Unknown error')}")

                    # Create QEMU VM for Windows
                    result = client.create_vm(
                        node=selected_node,
                        vmid=runner_vmid,
                        name=runner_name,
                        memory=runner_config.get('memory', 8192),
                        cores=runner_config.get('cores', 4),
                        storage=storage,
                        disk_size=runner_config.get('disk', 60),
                        bridge=bridge,
                        iso=windows_iso,
                        answer_iso=windows_answer_iso,
                        virtio_iso=virtio_iso if virtio_iso else None,
                        is_windows=True,
                        windows_version=runner  # Pass the runner type (windows-10, windows-11, etc.)
                    )

                    if result['success']:
                        # Determine status message based on ISO source
                        if iso_source == 'user-selected+autounattend':
                            iso_status = 'user ISO + autounattend attached'
                        elif iso_source == 'user-selected':
                            iso_status = 'user ISO attached (manual install required)'
                        elif iso_source == 'auto-created':
                            iso_status = 'unattended ISO attached'
                        elif iso_source == 'no-iso-selected':
                            iso_status = 'NO ISO - select Windows ISO in Proxmox settings!'
                        else:
                            iso_status = 'ISO creation failed'

                        # Add VirtIO info to status
                        if virtio_iso:
                            iso_status += ' + VirtIO drivers'

                        cred_info = {
                            'credential': deploy_credential['name'] if deploy_credential else 'default',
                            'credential_user': win_username,
                        }
                        created.append({
                            'vmid': runner_vmid,
                            'name': runner_name,
                            'type': 'qemu',
                            'os': runner,
                            'status': f'created ({iso_status})',
                            'iso': windows_iso,
                            'virtio_iso': virtio_iso if virtio_iso else None,
                            'iso_source': iso_source,
                            'ip_config': runner_ip_config,
                            'resources': f'{runner_config.get("cores", 4)} CPU, {runner_config.get("memory", 8192)//1024}GB RAM, {runner_config.get("disk", 60)}GB disk',
                            **cred_info
                        })

                        # Start VM - Windows will install automatically with autounattend.xml
                        if windows_iso:
                            client.start_vm(selected_node, runner_vmid)
                            if iso_source == 'user-selected+autounattend':
                                created[-1]['status'] = 'started (Windows auto-installing via autounattend)'
                            elif iso_source == 'user-selected':
                                created[-1]['status'] = 'started (manual Windows install required)'
                            else:
                                created[-1]['status'] = 'started (Windows auto-installing)'
                    else:
                        errors.append(f'{runner}: {result.get("error", "Creation failed")}')

                elif is_macos:
                    # Auto-download macOS recovery image from Apple servers
                    recovery_result = client.get_macos_recovery(selected_node, 'local', 'sonoma')
                    macos_iso = recovery_result.get('iso') if recovery_result.get('success') else None

                    # Prepare OpenCore bootloader
                    if macos_iso:
                        client.prepare_macos_opencore(selected_node, 'local', 'sonoma')

                    # Create QEMU VM for macOS with OSX-PROXMOX settings
                    result = client.create_vm(
                        node=selected_node,
                        vmid=runner_vmid,
                        name=runner_name,
                        memory=8192,
                        cores=4,
                        storage=storage,
                        disk_size=80,
                        bridge=bridge,
                        iso=macos_iso,
                        is_macos=True
                    )

                    if result['success']:
                        iso_status = 'recovery image attached' if macos_iso else 'recovery download pending'
                        # Get IP config for macOS runner
                        runner_ip_config = get_ip_config(runner)
                        cred_info = {}
                        if deploy_credential:
                            cred_info['credential'] = deploy_credential['name']
                            cred_info['credential_user'] = deploy_credential['username']
                            cred_info['provisioning_script'] = 'macos'
                        created.append({
                            'vmid': runner_vmid,
                            'name': runner_name,
                            'type': 'qemu',
                            'os': 'macos',
                            'status': f'created ({iso_status})',
                            'iso': macos_iso,
                            'ip_config': runner_ip_config,
                            'resources': '4 CPU, 8GB RAM, 80GB disk',
                            'notes': 'Requires Apple hardware per licensing. Uses OSX-PROXMOX configuration.',
                            **cred_info
                        })

                        # Start VM if recovery image is attached
                        if macos_iso:
                            client.start_vm(selected_node, runner_vmid)
                            created[-1]['status'] = 'started (macOS installation ready)'
                    else:
                        errors.append(f'{runner}: {result.get("error", "Creation failed")}')

            except Exception as e:
                errors.append(f'{runner}: {str(e)}')

        # =====================================================================
        # Build Response
        # =====================================================================
        output_lines = [
            f'Proxmox deployment for: {domain}',
            f'Node: {selected_node}',
            f'Storage: {storage}',
            f'Network: {bridge}',
            f'IP Mode: {"DHCP" if use_dhcp else "Static"}',
        ]

        # Show network config if using static IPs
        if not use_dhcp:
            if network_gateway:
                output_lines.append(f'Gateway: {network_gateway}')
            if network_dns:
                output_lines.append(f'DNS: {network_dns}')

        # Show credential info
        if deploy_credential:
            output_lines.append(f'Credential: {deploy_credential["name"]} (user: {deploy_credential["username"]})')
            if deploy_credential.get('ssh_public_key'):
                output_lines.append('  - SSH key will be added to authorized_keys')
            if deploy_credential.get('password'):
                output_lines.append('  - Password will be set for login')
        output_lines.append('')

        if created:
            output_lines.append('Created Resources:')
            for item in created:
                ip_str = f' - IP: {item["ip"]}' if item.get('ip') else ''
                ip_config_str = ''
                if item.get('ip_config') and item['ip_config'] != 'dhcp':
                    ip_config_str = f' [Static: {item["ip_config"]}]'
                elif item.get('ip_config') == 'dhcp':
                    ip_config_str = ' [DHCP]'
                output_lines.append(f'  - {item["type"].upper()} {item["vmid"]}: {item["name"]} ({item["resources"]}){ip_str}{ip_config_str}')
                output_lines.append(f'    Status: {item["status"]}')
                if item.get('credential'):
                    output_lines.append(f'    Credential: {item["credential"]} ({item.get("credential_user", "")})')

        if errors:
            output_lines.append('')
            output_lines.append('Errors:')
            for err in errors:
                output_lines.append(f'  - {err}')
            output_lines.append('')
            output_lines.append('Note: Some errors may be due to missing templates.')
            output_lines.append('Download templates: Proxmox UI > local > CT Templates > Templates')

        output_lines.append('')
        output_lines.append('Provisioning Status:')
        output_lines.append('- Linux containers: Auto-provisioning GitLab and runners via SSH')
        output_lines.append('- Windows/macOS VMs: Attach ISO and install manually, then run runner script')

        return jsonify({
            'success': len(created) > 0,
            'message': f'Created {len(created)} resources ({len(errors)} errors)',
            'output': '\n'.join(output_lines),
            'created': created,
            'errors': errors,
            'runner_urls': []
        })

    except ImportError as e:
        return jsonify({
            'success': False,
            'error': f'Missing library: {str(e)}. Run: pip install proxmoxer paramiko'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Proxmox deployment failed: {str(e)}'
        }), 500

@bp.route('/api/status/<deployment_id>')
def deployment_status(deployment_id):
    """Check deployment status and progress"""
    log_file = Path(__file__).parent.parent.parent / 'logs' / f'{deployment_id}.log'
    progress_file = Path(__file__).parent.parent.parent / 'logs' / f'{deployment_id}.progress'

    progress_data = {
        'success': True,
        'logs': '',
        'progress': 0,
        'current_step': 'Initializing...',
        'completed': False
    }

    # Read logs
    if log_file.exists():
        with open(log_file, 'r') as f:
            progress_data['logs'] = f.read()

    # Read progress
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            progress = json.load(f)
            progress_data.update(progress)

    return jsonify(progress_data)

@bp.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

def parse_runner_status(logs):
    """Parse runner status from deployment logs"""
    runner_status = []

    for runner_id, runner_info in SUPPORTED_RUNNERS.items():
        runner_name = runner_info['name']

        # Simple parsing - look for success messages
        if f'Runner {runner_name} registered successfully' in logs:
            runner_status.append({
                'name': runner_name,
                'status': 'Connected',
                'id': runner_id
            })
        elif f'Deploying {runner_name}' in logs:
            runner_status.append({
                'name': runner_name,
                'status': 'Deploying...',
                'id': runner_id
            })

    return runner_status


# ============================================================================
# Saved Configurations API
# ============================================================================

@bp.route('/api/configs', methods=['GET'])
def get_saved_configs():
    """Get all saved configurations"""
    try:
        configs = SavedConfig.get_all()
        return jsonify({
            'success': True,
            'configs': configs
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/configs', methods=['POST'])
def save_config():
    """Save a new configuration"""
    data = request.json

    if not data.get('name'):
        return jsonify({
            'success': False,
            'error': 'Configuration name is required'
        }), 400

    try:
        # Check if name already exists
        existing = SavedConfig.get_by_name(data['name'])
        if existing:
            return jsonify({
                'success': False,
                'error': 'A configuration with this name already exists'
            }), 400

        config_id = SavedConfig.create(
            name=data['name'],
            domain=data.get('domain', ''),
            email=data.get('email', ''),
            admin_password=data.get('admin_password'),
            letsencrypt_enabled=data.get('letsencrypt_enabled', True),
            runners=data.get('runners', []),
            traefik_enabled=data.get('traefik_enabled', False),
            base_domain=data.get('base_domain', ''),
            traefik_dashboard=data.get('traefik_dashboard', True),
            proxmox_config=data.get('proxmox_config'),
            network_config=data.get('network_config')
        )

        return jsonify({
            'success': True,
            'message': 'Configuration saved successfully',
            'config_id': config_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/configs/<int:config_id>', methods=['GET'])
def get_config(config_id):
    """Get a specific configuration"""
    try:
        # Include password only if explicitly requested
        include_password = request.args.get('include_password', 'false').lower() == 'true'
        config = SavedConfig.get_by_id(config_id, include_password=include_password)

        if config:
            return jsonify({
                'success': True,
                'config': config
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Configuration not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/configs/<int:config_id>', methods=['PUT'])
def update_config(config_id):
    """Update an existing configuration"""
    data = request.json

    try:
        success = SavedConfig.update(config_id, **data)
        if success:
            return jsonify({
                'success': True,
                'message': 'Configuration updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Configuration not found or no changes made'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/configs/<int:config_id>', methods=['DELETE'])
def delete_config(config_id):
    """Delete a saved configuration"""
    try:
        success = SavedConfig.delete(config_id)
        if success:
            return jsonify({
                'success': True,
                'message': 'Configuration deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Configuration not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Deployment History API
# ============================================================================

@bp.route('/api/history', methods=['GET'])
def get_deployment_history():
    """Get recent deployment history"""
    try:
        limit = request.args.get('limit', 10, type=int)
        history = DeploymentHistory.get_recent(limit=limit)
        return jsonify({
            'success': True,
            'history': history
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# SSH Keys API
# ============================================================================

@bp.route('/api/ssh-keys', methods=['GET'])
def get_ssh_keys():
    """Get all saved SSH keys (metadata only)"""
    try:
        keys = SSHKey.get_all()
        return jsonify({
            'success': True,
            'keys': keys
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/ssh-keys', methods=['POST'])
def save_ssh_key():
    """Save a new SSH key"""
    data = request.json

    if not data.get('name') or not data.get('key_content'):
        return jsonify({
            'success': False,
            'error': 'Name and key content are required'
        }), 400

    try:
        key_id = SSHKey.create(
            name=data['name'],
            key_content=data['key_content'],
            key_type=data.get('key_type', 'private'),
            passphrase=data.get('passphrase')
        )

        return jsonify({
            'success': True,
            'message': 'SSH key saved successfully',
            'key_id': key_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/ssh-keys/<int:key_id>', methods=['DELETE'])
def delete_ssh_key(key_id):
    """Delete an SSH key"""
    try:
        success = SSHKey.delete(key_id)
        if success:
            return jsonify({
                'success': True,
                'message': 'SSH key deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'SSH key not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/ssh-keys/upload', methods=['POST'])
def upload_ssh_key():
    """Upload an SSH key file"""
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No file provided'
        }), 400

    file = request.files['file']
    name = request.form.get('name', file.filename)

    # Validate file extension
    allowed_extensions = {'.pub', '.pem', '.key', ''}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({
            'success': False,
            'error': 'Invalid file type. Allowed: .pub, .pem, .key'
        }), 400

    try:
        key_content = file.read().decode('utf-8')
        key_type = 'public' if file_ext == '.pub' else 'private'

        key_id = SSHKey.create(
            name=name,
            key_content=key_content,
            key_type=key_type
        )

        return jsonify({
            'success': True,
            'message': 'SSH key uploaded successfully',
            'key_id': key_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Utility Endpoints
# ============================================================================

@bp.route('/api/runners')
def get_runners():
    """Get list of supported runners"""
    return jsonify({
        'success': True,
        'runners': SUPPORTED_RUNNERS
    })


# ============================================================================
# Infrastructure Provider Connection Tests
# ============================================================================

@bp.route('/api/test-connection', methods=['POST'])
def test_connection():
    """Test connection to infrastructure provider"""
    data = request.json
    provider = data.get('provider')
    config = data.get('config', {})

    if not provider:
        return jsonify({
            'success': False,
            'error': 'Provider not specified'
        }), 400

    try:
        if provider == 'proxmox':
            return test_proxmox_connection(config)
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown provider: {provider}'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def test_proxmox_connection(config):
    """Test connection to Proxmox VE server and return node capacity"""
    try:
        from proxmoxer import ProxmoxAPI

        host = config.get('host')
        port = config.get('port', 8006)
        user = config.get('user')
        password = config.get('password')
        verify_ssl = config.get('verify_ssl', False)
        target_node = config.get('node', '')
        target_storage = config.get('storage', 'local-lvm')

        if not all([host, user, password]):
            return jsonify({
                'success': False,
                'error': 'Missing required connection parameters'
            }), 400

        # Connect to Proxmox
        proxmox = ProxmoxAPI(
            host,
            port=port,
            user=user,
            password=password,
            verify_ssl=verify_ssl
        )

        # Test connection by getting version info
        version = proxmox.version.get()
        nodes = proxmox.nodes.get()

        node_names = [node['node'] for node in nodes] if nodes else []

        # Use target node or first available
        selected_node = target_node if target_node in node_names else (node_names[0] if node_names else None)

        # Get node capacity info
        capacity = None
        if selected_node:
            try:
                # Get node status for CPU and memory
                node_status = proxmox.nodes(selected_node).status.get()

                # CPU cores
                cpu_cores = node_status.get('cpuinfo', {}).get('cpus', 0)

                # Memory in GB (convert from bytes)
                memory_bytes = node_status.get('memory', {}).get('total', 0)
                memory_gb = round(memory_bytes / (1024 ** 3))

                # Get storage capacity
                storage_gb = 0
                try:
                    storages = proxmox.nodes(selected_node).storage.get()
                    for storage in storages:
                        if storage.get('storage') == target_storage:
                            # Storage is in bytes
                            storage_bytes = storage.get('total', 0)
                            storage_gb = round(storage_bytes / (1024 ** 3))
                            break
                    # If target storage not found, sum all available storage
                    if storage_gb == 0:
                        for storage in storages:
                            if storage.get('active', 0) == 1:
                                storage_bytes = storage.get('total', 0)
                                storage_gb += round(storage_bytes / (1024 ** 3))
                except Exception:
                    pass

                capacity = {
                    'cpu': cpu_cores,
                    'memory': memory_gb,
                    'storage': storage_gb
                }
            except Exception as e:
                # Continue without capacity info if we can't get it
                pass

        return jsonify({
            'success': True,
            'message': 'Connected successfully',
            'version': version.get('version', 'unknown'),
            'nodes': node_names,
            'node_info': selected_node,
            'capacity': capacity
        })

    except ImportError:
        return jsonify({
            'success': False,
            'error': 'proxmoxer library not installed. Run: pip install proxmoxer'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Connection failed: {str(e)}'
        }), 400


# ============================================================================
# Proxmox ISO Management API
# ============================================================================

@bp.route('/api/proxmox/isos', methods=['POST'])
def get_proxmox_isos():
    """Get list of available ISOs from Proxmox storage"""
    try:
        from proxmoxer import ProxmoxAPI

        config = request.json or {}
        host = config.get('host')
        port = config.get('port', 8006)
        user = config.get('user')
        password = config.get('password')
        verify_ssl = config.get('verify_ssl', False)
        target_node = config.get('node', 'pve')
        storage = config.get('storage', 'local')

        if not all([host, user, password]):
            return jsonify({
                'success': False,
                'error': 'Missing required connection parameters'
            }), 400

        # Connect to Proxmox
        proxmox = ProxmoxAPI(
            host,
            port=port,
            user=user,
            password=password,
            verify_ssl=verify_ssl
        )

        # Get nodes to find the right one
        nodes = proxmox.nodes.get()
        node_names = [node['node'] for node in nodes] if nodes else []
        selected_node = target_node if target_node in node_names else (node_names[0] if node_names else None)

        if not selected_node:
            return jsonify({
                'success': False,
                'error': 'No Proxmox nodes available'
            }), 400

        # Get storage content - ISO files
        isos = []
        try:
            # Try 'local' storage first (where ISOs are typically stored)
            iso_storage = 'local' if storage == 'local-lvm' else storage
            content = proxmox.nodes(selected_node).storage(iso_storage).content.get()
            for item in content:
                if item.get('content') == 'iso':
                    volid = item.get('volid', '')
                    filename = volid.split('/')[-1] if '/' in volid else volid.split(':')[-1] if ':' in volid else volid
                    size_mb = item.get('size', 0) // (1024 * 1024)

                    # Categorize the ISO
                    lower_name = filename.lower()
                    iso_type = 'other'
                    if 'windows' in lower_name or 'win10' in lower_name or 'win11' in lower_name:
                        iso_type = 'windows'
                    elif 'debian' in lower_name or 'ubuntu' in lower_name or 'linux' in lower_name or 'rocky' in lower_name or 'arch' in lower_name:
                        iso_type = 'linux'
                    elif 'macos' in lower_name or 'osx' in lower_name:
                        iso_type = 'macos'

                    isos.append({
                        'volid': volid,
                        'filename': filename,
                        'size': item.get('size', 0),
                        'size_mb': size_mb,
                        'size_display': f'{size_mb} MB' if size_mb < 1024 else f'{size_mb / 1024:.1f} GB',
                        'type': iso_type
                    })
        except Exception as e:
            # Storage might not exist or have no content
            pass

        # Sort: Windows first, then by name
        isos.sort(key=lambda x: (0 if x['type'] == 'windows' else 1, x['filename']))

        return jsonify({
            'success': True,
            'isos': isos,
            'node': selected_node,
            'storage': iso_storage if 'iso_storage' in dir() else storage
        })

    except ImportError:
        return jsonify({
            'success': False,
            'error': 'proxmoxer library not installed. Run: pip install proxmoxer'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get ISOs: {str(e)}'
        }), 400


@bp.route('/api/proxmox/vm/reconfigure-boot', methods=['POST'])
def reconfigure_vm_boot():
    """Reconfigure VM boot order after OS installation.

    This endpoint changes the boot order to boot from hard disk and optionally
    ejects CD-ROM media. Use this after Windows/macOS installation completes
    to ensure the VM boots from the installed OS.

    Request body:
        proxmox_url: Proxmox server URL
        proxmox_user: Proxmox username
        proxmox_password: Proxmox password (or token_value for API token)
        proxmox_token_name: (optional) API token name
        proxmox_node: Node where VM is running
        vmid: VM ID to reconfigure
        eject_cdroms: (optional, default true) Eject all CD-ROM media
    """
    data = request.json

    required_fields = ['proxmox_url', 'proxmox_user', 'proxmox_node', 'vmid']
    for field in required_fields:
        if not data.get(field):
            return jsonify({
                'success': False,
                'error': f'Missing required field: {field}'
            }), 400

    try:
        client = ProxmoxClient(
            host=data['proxmox_url'],
            user=data['proxmox_user'],
            password=data.get('proxmox_password'),
            token_name=data.get('proxmox_token_name'),
            token_value=data.get('proxmox_password') if data.get('proxmox_token_name') else None
        )

        eject_cdroms = data.get('eject_cdroms', True)
        result = client.reconfigure_vm_boot(
            node=data['proxmox_node'],
            vmid=data['vmid'],
            eject_cdroms=eject_cdroms
        )

        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'VM boot configuration updated. The VM will now boot from the hard disk.'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to reconfigure VM boot: {str(e)}'
        }), 400


# ============================================================================
# Credentials API - Unified credential management for Windows/Linux/macOS
# ============================================================================

@bp.route('/api/credentials', methods=['GET'])
def get_credentials():
    """Get all saved credentials (without secrets)"""
    try:
        credentials = Credential.get_all(include_secrets=False)
        return jsonify({
            'success': True,
            'credentials': credentials
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/credentials', methods=['POST'])
def create_credential():
    """Create a new credential"""
    data = request.json

    if not data.get('name') or not data.get('username'):
        return jsonify({
            'success': False,
            'error': 'Name and username are required'
        }), 400

    # Must have at least password or SSH key
    if not data.get('password') and not data.get('ssh_public_key'):
        return jsonify({
            'success': False,
            'error': 'Either password or SSH public key is required'
        }), 400

    try:
        # Check if name already exists
        existing = Credential.get_by_name(data['name'])
        if existing:
            return jsonify({
                'success': False,
                'error': 'A credential with this name already exists'
            }), 400

        credential_id = Credential.create(
            name=data['name'],
            username=data['username'],
            password=data.get('password'),
            ssh_public_key=data.get('ssh_public_key'),
            ssh_private_key=data.get('ssh_private_key'),
            ssh_key_passphrase=data.get('ssh_key_passphrase'),
            is_default=data.get('is_default', False)
        )

        return jsonify({
            'success': True,
            'message': 'Credential created successfully',
            'credential_id': credential_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/credentials/<int:credential_id>', methods=['GET'])
def get_credential(credential_id):
    """Get a specific credential"""
    try:
        include_secrets = request.args.get('include_secrets', 'false').lower() == 'true'
        credential = Credential.get_by_id(credential_id, include_secrets=include_secrets)

        if credential:
            return jsonify({
                'success': True,
                'credential': credential
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Credential not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/credentials/<int:credential_id>', methods=['PUT'])
def update_credential(credential_id):
    """Update an existing credential"""
    data = request.json

    try:
        success = Credential.update(credential_id, **data)
        if success:
            return jsonify({
                'success': True,
                'message': 'Credential updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Credential not found or no changes made'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/credentials/<int:credential_id>', methods=['DELETE'])
def delete_credential(credential_id):
    """Delete a credential"""
    try:
        success = Credential.delete(credential_id)
        if success:
            return jsonify({
                'success': True,
                'message': 'Credential deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Credential not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/credentials/<int:credential_id>/set-default', methods=['POST'])
def set_default_credential(credential_id):
    """Set a credential as the default"""
    try:
        success = Credential.set_default(credential_id)
        if success:
            return jsonify({
                'success': True,
                'message': 'Default credential updated'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Credential not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/credentials/generate', methods=['POST'])
def generate_credential():
    """Generate a new credential with SSH keypair"""
    data = request.json

    if not data.get('name') or not data.get('username'):
        return jsonify({
            'success': False,
            'error': 'Name and username are required'
        }), 400

    try:
        # Check if name already exists
        existing = Credential.get_by_name(data['name'])
        if existing:
            return jsonify({
                'success': False,
                'error': 'A credential with this name already exists'
            }), 400

        credential_id = Credential.generate_ssh_keypair(
            name=data['name'],
            username=data['username'],
            password=data.get('password'),
            key_type=data.get('key_type', 'ed25519'),
            passphrase=data.get('ssh_key_passphrase')
        )

        return jsonify({
            'success': True,
            'message': 'Credential with SSH keypair generated successfully',
            'credential_id': credential_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/credentials/upload-key', methods=['POST'])
def upload_credential_key():
    """Upload SSH key files to create or update a credential"""
    name = request.form.get('name')
    username = request.form.get('username')
    password = request.form.get('password')
    is_default = request.form.get('is_default', 'false').lower() == 'true'

    if not name or not username:
        return jsonify({
            'success': False,
            'error': 'Name and username are required'
        }), 400

    ssh_public_key = None
    ssh_private_key = None

    # Handle public key upload
    if 'public_key' in request.files:
        public_key_file = request.files['public_key']
        if public_key_file.filename:
            ssh_public_key = public_key_file.read().decode('utf-8').strip()

    # Handle private key upload
    if 'private_key' in request.files:
        private_key_file = request.files['private_key']
        if private_key_file.filename:
            ssh_private_key = private_key_file.read().decode('utf-8').strip()

    # Handle pasted public key
    if not ssh_public_key and request.form.get('ssh_public_key'):
        ssh_public_key = request.form.get('ssh_public_key').strip()

    # Handle pasted private key
    if not ssh_private_key and request.form.get('ssh_private_key'):
        ssh_private_key = request.form.get('ssh_private_key').strip()

    # Must have at least password or SSH key
    if not password and not ssh_public_key:
        return jsonify({
            'success': False,
            'error': 'Either password or SSH public key is required'
        }), 400

    try:
        # Check if name already exists
        existing = Credential.get_by_name(name)
        if existing:
            # Update existing credential
            Credential.update(
                existing['id'],
                username=username,
                password=password,
                ssh_public_key=ssh_public_key,
                ssh_private_key=ssh_private_key,
                is_default=is_default
            )
            return jsonify({
                'success': True,
                'message': 'Credential updated successfully',
                'credential_id': existing['id']
            })

        # Create new credential
        credential_id = Credential.create(
            name=name,
            username=username,
            password=password,
            ssh_public_key=ssh_public_key,
            ssh_private_key=ssh_private_key,
            is_default=is_default
        )

        return jsonify({
            'success': True,
            'message': 'Credential created successfully',
            'credential_id': credential_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/credentials/<int:credential_id>/download-key', methods=['GET'])
def download_credential_key(credential_id):
    """Download the SSH private key for a credential"""
    try:
        credential = Credential.get_by_id(credential_id, include_secrets=True)
        if not credential:
            return jsonify({
                'success': False,
                'error': 'Credential not found'
            }), 404

        if not credential.get('ssh_private_key'):
            return jsonify({
                'success': False,
                'error': 'This credential does not have an SSH private key'
            }), 400

        from flask import Response
        response = Response(
            credential['ssh_private_key'],
            mimetype='application/x-pem-file'
        )
        response.headers['Content-Disposition'] = f'attachment; filename={credential["name"]}_id_key'
        return response
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/providers')
def get_providers():
    """Get list of supported infrastructure providers"""
    return jsonify({
        'success': True,
        'providers': {
            'docker': {
                'name': 'Local Docker',
                'description': 'Deploy to local Docker engine'
            },
            'proxmox': {
                'name': 'Proxmox VE',
                'description': 'Deploy VMs to Proxmox Virtual Environment'
            }
        }
    })


@bp.route('/api/provision-log/<int:vmid>')
def get_provision_log(vmid):
    """Get the provision log for a specific VM/container."""
    log_file = Path(__file__).parent.parent.parent / 'logs' / f'provision_{vmid}.log'
    if log_file.exists():
        try:
            with open(log_file, 'r') as f:
                content = f.read()
            return jsonify({
                'success': True,
                'vmid': vmid,
                'log': content.split('\n'),
                'log_file': str(log_file)
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Failed to read log: {str(e)}'
            }), 500
    else:
        return jsonify({
            'success': False,
            'error': f'No log file found for vmid {vmid}'
        }), 404
