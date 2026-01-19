"""Database models for BuildForever credential and configuration management"""
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

# Database path - use data directory for persistence
DATA_DIR = Path(__file__).parent.parent.parent / 'data'
DATA_DIR.mkdir(exist_ok=True)
DATABASE_PATH = DATA_DIR / 'buildforever.db'


@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database with required tables"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Saved configurations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                domain TEXT NOT NULL,
                email TEXT NOT NULL,
                admin_password TEXT,
                letsencrypt_enabled INTEGER DEFAULT 1,
                runners TEXT,
                traefik_enabled INTEGER DEFAULT 0,
                base_domain TEXT,
                traefik_dashboard INTEGER DEFAULT 1,
                proxmox_config TEXT,
                network_config TEXT,
                deploy_gitlab INTEGER DEFAULT 1,
                gitlab_url TEXT,
                nfs_share TEXT,
                nfs_mount_path TEXT,
                samba_share TEXT,
                samba_mount_path TEXT,
                samba_username TEXT,
                samba_password TEXT,
                samba_domain TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Add Traefik columns if they don't exist (migration for existing databases)
        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN traefik_enabled INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN base_domain TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN traefik_dashboard INTEGER DEFAULT 1')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN proxmox_config TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN network_config TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN deploy_gitlab INTEGER DEFAULT 1')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN gitlab_url TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN nfs_share TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN nfs_mount_path TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN samba_share TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN samba_mount_path TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN samba_username TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN samba_password TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute('ALTER TABLE saved_configs ADD COLUMN samba_domain TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Deployment history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deployment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deployment_id TEXT NOT NULL,
                config_name TEXT,
                domain TEXT NOT NULL,
                runners TEXT,
                status TEXT DEFAULT 'pending',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                logs TEXT
            )
        ''')

        # SSH keys table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ssh_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                key_type TEXT DEFAULT 'private',
                key_content TEXT NOT NULL,
                passphrase TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Credentials table - unified credential management for all platforms
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL,
                password TEXT,
                ssh_public_key TEXT,
                ssh_private_key TEXT,
                ssh_key_passphrase TEXT,
                is_default INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')


class SavedConfig:
    """Model for saved deployment configurations"""

    @staticmethod
    def create(name, domain, email, admin_password=None, letsencrypt_enabled=True, runners=None,
               traefik_enabled=False, base_domain=None, traefik_dashboard=True, proxmox_config=None,
               network_config=None, deploy_gitlab=True, gitlab_url=None, nfs_share=None, nfs_mount_path=None,
               samba_share=None, samba_mount_path=None, samba_username=None, samba_password=None, samba_domain=None):
        """Create a new saved configuration"""
        runners_json = json.dumps(runners or [])
        proxmox_config_json = json.dumps(proxmox_config) if proxmox_config else None
        network_config_json = json.dumps(network_config) if network_config else None
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO saved_configs (name, domain, email, admin_password, letsencrypt_enabled, runners,
                                          traefik_enabled, base_domain, traefik_dashboard, proxmox_config, network_config,
                                          deploy_gitlab, gitlab_url, nfs_share, nfs_mount_path, samba_share, samba_mount_path,
                                          samba_username, samba_password, samba_domain)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, domain, email, admin_password, int(letsencrypt_enabled), runners_json,
                  int(traefik_enabled), base_domain, int(traefik_dashboard), proxmox_config_json, network_config_json,
                  int(deploy_gitlab), gitlab_url, nfs_share, nfs_mount_path, samba_share, samba_mount_path,
                  samba_username, samba_password, samba_domain))
            return cursor.lastrowid

    @staticmethod
    def update(config_id, **kwargs):
        """Update an existing configuration"""
        allowed_fields = ['name', 'domain', 'email', 'admin_password', 'letsencrypt_enabled', 'runners',
                         'traefik_enabled', 'base_domain', 'traefik_dashboard', 'proxmox_config', 'network_config',
                         'deploy_gitlab', 'gitlab_url', 'nfs_share', 'nfs_mount_path', 'samba_share', 'samba_mount_path',
                         'samba_username', 'samba_password', 'samba_domain']
        updates = []
        values = []

        for field in allowed_fields:
            if field in kwargs:
                value = kwargs[field]
                if field == 'runners':
                    value = json.dumps(value or [])
                elif field in ('proxmox_config', 'network_config'):
                    value = json.dumps(value) if value else None
                elif field in ('letsencrypt_enabled', 'traefik_enabled', 'traefik_dashboard', 'deploy_gitlab'):
                    value = int(value)
                updates.append(f'{field} = ?')
                values.append(value)

        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            values.append(config_id)

            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    UPDATE saved_configs SET {', '.join(updates)} WHERE id = ?
                ''', values)
                return cursor.rowcount > 0
        return False

    @staticmethod
    def delete(config_id):
        """Delete a saved configuration"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM saved_configs WHERE id = ?', (config_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_all():
        """Get all saved configurations (without passwords)"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, domain, email, letsencrypt_enabled, runners,
                       traefik_enabled, base_domain, traefik_dashboard, proxmox_config, network_config,
                       deploy_gitlab, gitlab_url, nfs_share, nfs_mount_path, samba_share, samba_mount_path,
                       samba_username, samba_domain, created_at, updated_at
                FROM saved_configs ORDER BY updated_at DESC
            ''')
            rows = cursor.fetchall()
            results = []
            for row in rows:
                proxmox_cfg = None
                if 'proxmox_config' in row.keys() and row['proxmox_config']:
                    try:
                        proxmox_cfg = json.loads(row['proxmox_config'])
                    except (json.JSONDecodeError, TypeError):
                        proxmox_cfg = None
                network_cfg = None
                if 'network_config' in row.keys() and row['network_config']:
                    try:
                        network_cfg = json.loads(row['network_config'])
                    except (json.JSONDecodeError, TypeError):
                        network_cfg = None
                results.append({
                    'id': row['id'],
                    'name': row['name'],
                    'domain': row['domain'],
                    'email': row['email'],
                    'letsencrypt_enabled': bool(row['letsencrypt_enabled']),
                    'runners': json.loads(row['runners']) if row['runners'] else [],
                    'traefik_enabled': bool(row['traefik_enabled']) if row['traefik_enabled'] is not None else False,
                    'base_domain': row['base_domain'] or '',
                    'traefik_dashboard': bool(row['traefik_dashboard']) if row['traefik_dashboard'] is not None else True,
                    'proxmox_config': proxmox_cfg,
                    'network_config': network_cfg,
                    'deploy_gitlab': bool(row['deploy_gitlab']) if 'deploy_gitlab' in row.keys() and row['deploy_gitlab'] is not None else True,
                    'gitlab_url': row['gitlab_url'] if 'gitlab_url' in row.keys() else None,
                    'nfs_share': row['nfs_share'] if 'nfs_share' in row.keys() else None,
                    'nfs_mount_path': row['nfs_mount_path'] if 'nfs_mount_path' in row.keys() else '/mnt/shared',
                    'samba_share': row['samba_share'] if 'samba_share' in row.keys() else None,
                    'samba_mount_path': row['samba_mount_path'] if 'samba_mount_path' in row.keys() else '/mnt/samba',
                    'samba_username': row['samba_username'] if 'samba_username' in row.keys() else None,
                    'samba_domain': row['samba_domain'] if 'samba_domain' in row.keys() else None,
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                })
            return results

    @staticmethod
    def get_by_id(config_id, include_password=False):
        """Get a specific configuration by ID"""
        with get_db() as conn:
            cursor = conn.cursor()
            if include_password:
                cursor.execute('SELECT * FROM saved_configs WHERE id = ?', (config_id,))
            else:
                cursor.execute('''
                    SELECT id, name, domain, email, letsencrypt_enabled, runners,
                           traefik_enabled, base_domain, traefik_dashboard, proxmox_config, network_config,
                           deploy_gitlab, gitlab_url, nfs_share, nfs_mount_path, samba_share, samba_mount_path,
                           samba_username, samba_domain, created_at, updated_at
                    FROM saved_configs WHERE id = ?
                ''', (config_id,))
            row = cursor.fetchone()
            if row:
                proxmox_cfg = None
                if 'proxmox_config' in row.keys() and row['proxmox_config']:
                    try:
                        proxmox_cfg = json.loads(row['proxmox_config'])
                    except (json.JSONDecodeError, TypeError):
                        proxmox_cfg = None
                network_cfg = None
                if 'network_config' in row.keys() and row['network_config']:
                    try:
                        network_cfg = json.loads(row['network_config'])
                    except (json.JSONDecodeError, TypeError):
                        network_cfg = None
                result = {
                    'id': row['id'],
                    'name': row['name'],
                    'domain': row['domain'],
                    'email': row['email'],
                    'letsencrypt_enabled': bool(row['letsencrypt_enabled']),
                    'runners': json.loads(row['runners']) if row['runners'] else [],
                    'traefik_enabled': bool(row['traefik_enabled']) if 'traefik_enabled' in row.keys() and row['traefik_enabled'] is not None else False,
                    'base_domain': row['base_domain'] if 'base_domain' in row.keys() else '',
                    'traefik_dashboard': bool(row['traefik_dashboard']) if 'traefik_dashboard' in row.keys() and row['traefik_dashboard'] is not None else True,
                    'proxmox_config': proxmox_cfg,
                    'network_config': network_cfg,
                    'deploy_gitlab': bool(row['deploy_gitlab']) if 'deploy_gitlab' in row.keys() and row['deploy_gitlab'] is not None else True,
                    'gitlab_url': row['gitlab_url'] if 'gitlab_url' in row.keys() else None,
                    'nfs_share': row['nfs_share'] if 'nfs_share' in row.keys() else None,
                    'nfs_mount_path': row['nfs_mount_path'] if 'nfs_mount_path' in row.keys() else '/mnt/shared',
                    'samba_share': row['samba_share'] if 'samba_share' in row.keys() else None,
                    'samba_mount_path': row['samba_mount_path'] if 'samba_mount_path' in row.keys() else '/mnt/samba',
                    'samba_username': row['samba_username'] if 'samba_username' in row.keys() else None,
                    'samba_domain': row['samba_domain'] if 'samba_domain' in row.keys() else None,
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                if include_password and 'admin_password' in row.keys():
                    result['admin_password'] = row['admin_password']
                if include_password and 'samba_password' in row.keys():
                    result['samba_password'] = row['samba_password']
                return result
            return None

    @staticmethod
    def get_by_name(name):
        """Get a configuration by name"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, domain, email, letsencrypt_enabled, runners,
                       traefik_enabled, base_domain, traefik_dashboard, proxmox_config, network_config,
                       deploy_gitlab, gitlab_url, nfs_share, nfs_mount_path, samba_share, samba_mount_path,
                       samba_username, samba_domain, created_at, updated_at
                FROM saved_configs WHERE name = ?
            ''', (name,))
            row = cursor.fetchone()
            if row:
                proxmox_cfg = None
                if 'proxmox_config' in row.keys() and row['proxmox_config']:
                    try:
                        proxmox_cfg = json.loads(row['proxmox_config'])
                    except (json.JSONDecodeError, TypeError):
                        proxmox_cfg = None
                network_cfg = None
                if 'network_config' in row.keys() and row['network_config']:
                    try:
                        network_cfg = json.loads(row['network_config'])
                    except (json.JSONDecodeError, TypeError):
                        network_cfg = None
                return {
                    'id': row['id'],
                    'name': row['name'],
                    'domain': row['domain'],
                    'email': row['email'],
                    'letsencrypt_enabled': bool(row['letsencrypt_enabled']),
                    'runners': json.loads(row['runners']) if row['runners'] else [],
                    'traefik_enabled': bool(row['traefik_enabled']) if row['traefik_enabled'] is not None else False,
                    'base_domain': row['base_domain'] or '',
                    'traefik_dashboard': bool(row['traefik_dashboard']) if row['traefik_dashboard'] is not None else True,
                    'proxmox_config': proxmox_cfg,
                    'network_config': network_cfg,
                    'deploy_gitlab': bool(row['deploy_gitlab']) if 'deploy_gitlab' in row.keys() and row['deploy_gitlab'] is not None else True,
                    'gitlab_url': row['gitlab_url'] if 'gitlab_url' in row.keys() else None,
                    'nfs_share': row['nfs_share'] if 'nfs_share' in row.keys() else None,
                    'nfs_mount_path': row['nfs_mount_path'] if 'nfs_mount_path' in row.keys() else '/mnt/shared',
                    'samba_share': row['samba_share'] if 'samba_share' in row.keys() else None,
                    'samba_mount_path': row['samba_mount_path'] if 'samba_mount_path' in row.keys() else '/mnt/samba',
                    'samba_username': row['samba_username'] if 'samba_username' in row.keys() else None,
                    'samba_domain': row['samba_domain'] if 'samba_domain' in row.keys() else None,
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
            return None


class DeploymentHistory:
    """Model for deployment history tracking"""

    @staticmethod
    def create(deployment_id, domain, config_name=None, runners=None):
        """Create a new deployment record"""
        runners_json = json.dumps(runners or [])
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO deployment_history (deployment_id, config_name, domain, runners)
                VALUES (?, ?, ?, ?)
            ''', (deployment_id, config_name, domain, runners_json))
            return cursor.lastrowid

    @staticmethod
    def update_status(deployment_id, status, error_message=None, logs=None):
        """Update deployment status"""
        with get_db() as conn:
            cursor = conn.cursor()
            if status in ('completed', 'failed'):
                cursor.execute('''
                    UPDATE deployment_history
                    SET status = ?, error_message = ?, logs = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE deployment_id = ?
                ''', (status, error_message, logs, deployment_id))
            else:
                cursor.execute('''
                    UPDATE deployment_history SET status = ?, error_message = ?, logs = ?
                    WHERE deployment_id = ?
                ''', (status, error_message, logs, deployment_id))
            return cursor.rowcount > 0

    @staticmethod
    def get_recent(limit=10):
        """Get recent deployment history"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM deployment_history ORDER BY started_at DESC LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [
                {
                    'id': row['id'],
                    'deployment_id': row['deployment_id'],
                    'config_name': row['config_name'],
                    'domain': row['domain'],
                    'runners': json.loads(row['runners']) if row['runners'] else [],
                    'status': row['status'],
                    'started_at': row['started_at'],
                    'completed_at': row['completed_at'],
                    'error_message': row['error_message']
                }
                for row in rows
            ]


class SSHKey:
    """Model for SSH key management"""

    @staticmethod
    def create(name, key_content, key_type='private', passphrase=None):
        """Save an SSH key"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ssh_keys (name, key_type, key_content, passphrase)
                VALUES (?, ?, ?, ?)
            ''', (name, key_type, key_content, passphrase))
            return cursor.lastrowid

    @staticmethod
    def delete(key_id):
        """Delete an SSH key"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ssh_keys WHERE id = ?', (key_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_all():
        """Get all SSH keys (metadata only, not content)"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, key_type, created_at FROM ssh_keys ORDER BY created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_id(key_id):
        """Get an SSH key by ID (includes content)"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ssh_keys WHERE id = ?', (key_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


class Credential:
    """Model for unified credential management across all platforms (Windows/Linux/macOS)"""

    @staticmethod
    def create(name, username, password=None, ssh_public_key=None, ssh_private_key=None,
               ssh_key_passphrase=None, is_default=False):
        """Create a new credential"""
        with get_db() as conn:
            cursor = conn.cursor()
            # If setting as default, clear other defaults first
            if is_default:
                cursor.execute('UPDATE credentials SET is_default = 0')
            cursor.execute('''
                INSERT INTO credentials (name, username, password, ssh_public_key, ssh_private_key,
                                         ssh_key_passphrase, is_default)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, username, password, ssh_public_key, ssh_private_key,
                  ssh_key_passphrase, int(is_default)))
            return cursor.lastrowid

    @staticmethod
    def update(credential_id, **kwargs):
        """Update an existing credential"""
        allowed_fields = ['name', 'username', 'password', 'ssh_public_key', 'ssh_private_key',
                          'ssh_key_passphrase', 'is_default']
        updates = []
        values = []

        for field in allowed_fields:
            if field in kwargs:
                value = kwargs[field]
                if field == 'is_default':
                    value = int(value)
                updates.append(f'{field} = ?')
                values.append(value)

        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            values.append(credential_id)

            with get_db() as conn:
                cursor = conn.cursor()
                # If setting as default, clear other defaults first
                if kwargs.get('is_default'):
                    cursor.execute('UPDATE credentials SET is_default = 0')
                cursor.execute(f'''
                    UPDATE credentials SET {', '.join(updates)} WHERE id = ?
                ''', values)
                return cursor.rowcount > 0
        return False

    @staticmethod
    def delete(credential_id):
        """Delete a credential"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM credentials WHERE id = ?', (credential_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_all(include_secrets=False):
        """Get all credentials"""
        with get_db() as conn:
            cursor = conn.cursor()
            if include_secrets:
                cursor.execute('''
                    SELECT * FROM credentials ORDER BY is_default DESC, updated_at DESC
                ''')
            else:
                cursor.execute('''
                    SELECT id, name, username, is_default,
                           CASE WHEN password IS NOT NULL AND password != '' THEN 1 ELSE 0 END as has_password,
                           CASE WHEN ssh_public_key IS NOT NULL AND ssh_public_key != '' THEN 1 ELSE 0 END as has_ssh_key,
                           created_at, updated_at
                    FROM credentials ORDER BY is_default DESC, updated_at DESC
                ''')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_by_id(credential_id, include_secrets=True):
        """Get a specific credential by ID"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM credentials WHERE id = ?', (credential_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if not include_secrets:
                    result.pop('password', None)
                    result.pop('ssh_private_key', None)
                    result.pop('ssh_key_passphrase', None)
                return result
            return None

    @staticmethod
    def get_by_name(name):
        """Get a credential by name"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM credentials WHERE name = ?', (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_default():
        """Get the default credential"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM credentials WHERE is_default = 1')
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def set_default(credential_id):
        """Set a credential as the default"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE credentials SET is_default = 0')
            cursor.execute('UPDATE credentials SET is_default = 1 WHERE id = ?', (credential_id,))
            return cursor.rowcount > 0

    @staticmethod
    def generate_ssh_keypair(name, username, password=None, key_type='ed25519', passphrase=None):
        """Generate a new SSH keypair and save as a credential"""
        import subprocess
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = os.path.join(tmpdir, 'id_key')

            # Generate key using ssh-keygen
            cmd = ['ssh-keygen', '-t', key_type, '-f', key_path, '-N', passphrase or '', '-C', f'{username}@buildforever']

            try:
                subprocess.run(cmd, check=True, capture_output=True)

                # Read generated keys
                with open(key_path, 'r') as f:
                    private_key = f.read()
                with open(f'{key_path}.pub', 'r') as f:
                    public_key = f.read()

                # Create credential with the generated keys
                return Credential.create(
                    name=name,
                    username=username,
                    password=password,
                    ssh_public_key=public_key.strip(),
                    ssh_private_key=private_key.strip(),
                    ssh_key_passphrase=passphrase
                )
            except subprocess.CalledProcessError as e:
                raise Exception(f'Failed to generate SSH keypair: {e.stderr.decode()}')
            except FileNotFoundError:
                raise Exception('ssh-keygen not found. Please install OpenSSH.')


# Initialize database on module import
init_db()
