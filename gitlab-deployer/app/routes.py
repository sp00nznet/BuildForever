"""Flask routes for GitLab Build Farm Deployer"""
from flask import Blueprint, render_template, request, jsonify, session, make_response
import subprocess
import json
import os
import time
from pathlib import Path
from functools import wraps
from .models import SavedConfig, DeploymentHistory, SSHKey, init_db

bp = Blueprint('main', __name__)


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

    # Validate required fields
    required_fields = ['domain', 'admin_password', 'email']
    missing_fields = [field for field in required_fields if not data.get(field)]

    if missing_fields:
        return jsonify({
            'success': False,
            'error': f'Missing required fields: {", ".join(missing_fields)}'
        }), 400

    runners = data.get('runners', [])

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
        'admin_password': data['admin_password'],
        'email': data['email'],
        'letsencrypt_enabled': data.get('letsencrypt_enabled', True),
        'runners': runners,
        # Provider settings
        'provider': provider,
        'provider_config': provider_config,
        # Traefik settings
        'traefik_enabled': data.get('traefik_enabled', False),
        'base_domain': data.get('base_domain', ''),
        'traefik_dashboard': data.get('traefik_dashboard', True)
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
    if config['traefik_enabled']:
        deployment_steps.append('Deploy Traefik Reverse Proxy')
        deployment_steps.append('Configure Traefik SSL certificates')

    deployment_steps.extend([
        'Deploy GitLab Server',
        'Configure SSL with Let\'s Encrypt' if config['letsencrypt_enabled'] and not config['traefik_enabled'] else 'Configure GitLab',
        'Wait for GitLab initialization',
        'Obtain runner registration token'
    ])

    for runner_id in runners:
        runner_name = SUPPORTED_RUNNERS[runner_id]['name']
        deployment_steps.append(f'Deploy {runner_name} runner')
        deployment_steps.append(f'Register {runner_name} runner to GitLab')

    deployment_steps.append('Verify all runners are connected')
    deployment_steps.append('Deployment complete')

    # Store in session for status tracking
    session['deployment_id'] = data['domain']
    session['deployment_steps'] = deployment_steps

    return jsonify({
        'success': True,
        'message': f'Deployment plan created: GitLab Server + {len(runners)} runner(s)',
        'deployment_id': data['domain'],
        'deployment_plan': {
            'steps': deployment_steps,
            'estimated_time': f'{15 + len(runners) * 5}-{30 + len(runners) * 10} minutes'
        }
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
    from .proxmox_client import (
        ProxmoxClient, get_gitlab_install_script, get_runner_install_script
    )

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

        # Track created resources
        created = []
        errors = []

        # =====================================================================
        # Step 1: Create GitLab Server (LXC Container)
        # =====================================================================
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
                ip='dhcp',
                password='root',
                start=True
            )

            if result['success']:
                created.append({
                    'vmid': gitlab_vmid,
                    'name': 'GitLab Server',
                    'type': 'lxc',
                    'status': 'created',
                    'resources': '4 CPU, 8GB RAM, 50GB disk'
                })

                # Get container IP
                gitlab_ip = client.get_container_ip(selected_node, gitlab_vmid)
                if gitlab_ip:
                    created[-1]['ip'] = gitlab_ip

                    # Start provisioning in background
                    def provision_gitlab():
                        script = get_gitlab_install_script(
                            domain=domain,
                            admin_password=admin_password,
                            letsencrypt_email=email if config.get('letsencrypt_enabled') else None
                        )
                        prov_result = client.provision_container(selected_node, gitlab_vmid, script)
                        # Update status (would need proper status tracking)

                    thread = threading.Thread(target=provision_gitlab, daemon=True)
                    thread.start()
                    created[-1]['status'] = 'provisioning'
            else:
                errors.append(f'GitLab Server: {result.get("error", "Creation failed")}')

        except Exception as e:
            errors.append(f'GitLab Server: {str(e)}')

        # =====================================================================
        # Step 2: Create Runner VMs/Containers
        # =====================================================================
        gitlab_url = f'https://{domain}'

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
                        ip='dhcp',
                        password='root',
                        start=True
                    )

                    if result['success']:
                        created.append({
                            'vmid': runner_vmid,
                            'name': runner_name,
                            'type': 'lxc',
                            'os': runner,
                            'status': 'created',
                            'resources': f'{runner_config.get("cores", 2)} CPU, {runner_config.get("memory", 4096)//1024}GB RAM, {runner_config.get("disk", 40)}GB disk'
                        })

                        # Provision runner in background
                        def provision_runner(vmid, rtype):
                            ip = client.get_container_ip(selected_node, vmid)
                            if ip:
                                # Note: registration_token would come from GitLab API after it's running
                                script = get_runner_install_script(rtype, gitlab_url, 'REGISTRATION_TOKEN')
                                client.provision_container(selected_node, vmid, script)

                        thread = threading.Thread(
                            target=provision_runner,
                            args=(runner_vmid, runner),
                            daemon=True
                        )
                        thread.start()
                        created[-1]['status'] = 'provisioning'
                    else:
                        errors.append(f'{runner}: {result.get("error", "Creation failed")}')

                elif is_windows:
                    # Auto-download Windows ISO if not available
                    iso_result = client.ensure_vm_image(selected_node, 'local', runner)
                    windows_iso = iso_result.get('iso') if iso_result.get('success') else None

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
                        is_windows=True
                    )

                    if result['success']:
                        iso_status = 'ISO attached' if windows_iso else 'ISO download pending'
                        created.append({
                            'vmid': runner_vmid,
                            'name': runner_name,
                            'type': 'qemu',
                            'os': runner,
                            'status': f'created ({iso_status})',
                            'iso': windows_iso,
                            'resources': f'{runner_config.get("cores", 4)} CPU, {runner_config.get("memory", 8192)//1024}GB RAM, {runner_config.get("disk", 60)}GB disk'
                        })

                        # Start VM if ISO is attached
                        if windows_iso:
                            client.start_vm(selected_node, runner_vmid)
                            created[-1]['status'] = 'started (Windows installation ready)'
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
                        created.append({
                            'vmid': runner_vmid,
                            'name': runner_name,
                            'type': 'qemu',
                            'os': 'macos',
                            'status': f'created ({iso_status})',
                            'iso': macos_iso,
                            'resources': '4 CPU, 8GB RAM, 80GB disk',
                            'notes': 'Requires Apple hardware per licensing. Uses OSX-PROXMOX configuration.'
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
            ''
        ]

        if created:
            output_lines.append('Created Resources:')
            for item in created:
                ip_str = f' - IP: {item["ip"]}' if item.get('ip') else ''
                output_lines.append(f'  - {item["type"].upper()} {item["vmid"]}: {item["name"]} ({item["resources"]}){ip_str}')
                output_lines.append(f'    Status: {item["status"]}')

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
            traefik_dashboard=data.get('traefik_dashboard', True)
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
