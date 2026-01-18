# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for BuildForever Win32 executable.

This creates a standalone Windows executable that bundles:
- Flask web application
- SQLite database support
- All static assets and templates
- pywebview for native Windows UI

Build command: pyinstaller --clean --noconfirm buildforever.spec
"""

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Collect all Flask and related submodules
hiddenimports = [
    # Flask core
    'flask',
    'flask.json',
    'flask.templating',
    'werkzeug',
    'werkzeug.serving',
    'werkzeug.debug',
    'jinja2',
    'markupsafe',

    # Application modules
    'app',
    'app.routes',
    'app.models',

    # Database
    'sqlite3',

    # HTTP and networking
    'requests',
    'urllib3',

    # YAML and JSON
    'yaml',
    'json',

    # pywebview for native window
    'webview',
    'webview.platforms.winforms',

    # Windows-specific
    'clr',
    'pythonnet',

    # Cryptography (for secure storage)
    'cryptography',
    'cryptography.fernet',

    # Infrastructure providers
    'proxmoxer',
    'proxmoxer.core',
    'proxmoxer.backends',
    'proxmoxer.backends.https',

    # SSH for container provisioning
    'paramiko',
    'paramiko.ssh_exception',
    'paramiko.transport',
    'paramiko.channel',

    # Application - Proxmox client
    'app.proxmox_client',
]

# Data files to include
datas = [
    ('app/templates', 'app/templates'),
    ('app/static', 'app/static'),
]

# Analysis
a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'tensorflow',
        'torch',
        'pytest',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Create PYZ archive
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# Create executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BuildForever',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window - GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if desired: icon='app/static/icon.ico'
)
