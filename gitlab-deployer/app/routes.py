"""Flask routes for GitLab Deployer"""
from flask import Blueprint, render_template, request, jsonify, session
import subprocess
import json
import os
from pathlib import Path

bp = Blueprint('main', __name__)

SUPPORTED_PLATFORMS = {
    'windows': ['Windows 10', 'Windows 11', 'Windows Server 2022', 'Windows Server 2025'],
    'linux': ['Debian', 'Ubuntu', 'Arch Linux', 'Rocky Linux'],
    'macos': ['macOS']
}

@bp.route('/')
def index():
    """Main deployment interface"""
    return render_template('index.html', platforms=SUPPORTED_PLATFORMS)

@bp.route('/api/deploy', methods=['POST'])
def deploy():
    """Handle GitLab deployment request"""
    data = request.json

    # Validate required fields
    required_fields = ['platform', 'os_version', 'domain', 'admin_password', 'email']
    missing_fields = [field for field in required_fields if not data.get(field)]

    if missing_fields:
        return jsonify({
            'success': False,
            'error': f'Missing required fields: {", ".join(missing_fields)}'
        }), 400

    # Save deployment configuration
    config = {
        'platform': data['platform'],
        'os_version': data['os_version'],
        'domain': data['domain'],
        'admin_password': data['admin_password'],
        'email': data['email'],
        'letsencrypt_enabled': data.get('letsencrypt_enabled', True)
    }

    # Save config to file for deployment script
    config_dir = Path(__file__).parent.parent.parent / 'config'
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / 'deployment_config.json'

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    # Store in session for status tracking
    session['deployment_id'] = data['domain']

    return jsonify({
        'success': True,
        'message': 'Deployment configuration saved. Ready to deploy.',
        'deployment_id': data['domain']
    })

@bp.route('/api/execute-deployment', methods=['POST'])
def execute_deployment():
    """Execute the GitLab deployment"""
    data = request.json
    deployment_id = data.get('deployment_id')

    if not deployment_id:
        return jsonify({
            'success': False,
            'error': 'No deployment ID provided'
        }), 400

    # Path to deployment script
    script_path = Path(__file__).parent.parent.parent / 'scripts' / 'deploy.sh'

    try:
        # Execute deployment script
        result = subprocess.run(
            [str(script_path), 'deploy'],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )

        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': 'GitLab deployment completed successfully',
                'output': result.stdout
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Deployment failed',
                'output': result.stderr
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Deployment timed out after 1 hour'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/status/<deployment_id>')
def deployment_status(deployment_id):
    """Check deployment status"""
    log_file = Path(__file__).parent.parent.parent / 'logs' / f'{deployment_id}.log'

    if log_file.exists():
        with open(log_file, 'r') as f:
            logs = f.read()
        return jsonify({
            'success': True,
            'logs': logs
        })
    else:
        return jsonify({
            'success': True,
            'logs': 'No logs available yet'
        })

@bp.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})
