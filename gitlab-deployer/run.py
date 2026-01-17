#!/usr/bin/env python3
"""GitLab Deployer - Main Entry Point"""
from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'

    print(f"""
    ╔══════════════════════════════════════════════════╗
    ║         BuildForever - GitLab Deployer          ║
    ║                                                  ║
    ║  Web Interface: http://localhost:{port}        ║
    ║                                                  ║
    ║  Supported Platforms:                            ║
    ║  • Windows 10, 11, Server 2022, Server 2025     ║
    ║  • Linux: Debian, Ubuntu, Arch, Rocky           ║
    ║  • macOS                                         ║
    ╚══════════════════════════════════════════════════╝
    """)

    app.run(host='0.0.0.0', port=port, debug=debug)
