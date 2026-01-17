"""Flask routes for GitLab Build Farm Deployer"""
from flask import Blueprint, render_template, request, jsonify, session
import subprocess
import json
import os
import time
from pathlib import Path

bp = Blueprint('main', __name__)

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

    # Save deployment configuration
    config = {
        'domain': data['domain'],
        'admin_password': data['admin_password'],
        'email': data['email'],
        'letsencrypt_enabled': data.get('letsencrypt_enabled', True),
        'runners': runners
    }

    # Save config to file for deployment script
    config_dir = Path(__file__).parent.parent.parent / 'config'
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / 'deployment_config.json'

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    # Create deployment plan
    deployment_steps = [
        'Deploy GitLab Server',
        'Configure SSL with Let\'s Encrypt' if config['letsencrypt_enabled'] else 'Configure GitLab',
        'Wait for GitLab initialization',
        'Obtain runner registration token'
    ]

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
