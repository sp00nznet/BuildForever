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

    # Path to deployment script
    script_path = Path(__file__).parent.parent.parent / 'scripts' / 'deploy.sh'

    # Create logs directory
    logs_dir = Path(__file__).parent.parent.parent / 'logs'
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f'{deployment_id}.log'

    try:
        # Execute deployment script
        with open(log_file, 'w') as log:
            result = subprocess.run(
                [str(script_path), 'deploy-all'],
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=7200  # 2 hour timeout for full deployment
            )

        # Read logs
        with open(log_file, 'r') as log:
            logs = log.read()

        if result.returncode == 0:
            # Parse runner status from logs
            runner_status = parse_runner_status(logs)

            return jsonify({
                'success': True,
                'message': 'Build farm deployment completed successfully',
                'output': logs,
                'runner_urls': runner_status
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Deployment failed',
                'output': logs
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Deployment timed out after 2 hours'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
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
