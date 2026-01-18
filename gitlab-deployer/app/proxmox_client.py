"""Proxmox client for VM and container management with full provisioning support."""
import time
import paramiko
from io import StringIO


class ProxmoxClient:
    """Client for interacting with Proxmox VE API."""

    # ISO download URLs for various operating systems
    ISO_URLS = {
        'debian': 'https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.4.0-amd64-netinst.iso',
        'ubuntu': 'https://releases.ubuntu.com/22.04.3/ubuntu-22.04.3-live-server-amd64.iso',
        'rocky': 'https://download.rockylinux.org/pub/rocky/9/isos/x86_64/Rocky-9.3-x86_64-minimal.iso',
        'arch': 'https://geo.mirror.pkgbuild.com/iso/latest/archlinux-x86_64.iso',
    }

    # LXC container templates
    CT_TEMPLATES = {
        'debian': 'debian-12-standard_12.2-1_amd64.tar.zst',
        'ubuntu': 'ubuntu-22.04-standard_22.04-1_amd64.tar.zst',
        'rocky': 'rockylinux-9-default_20221109_amd64.tar.xz',
        'arch': 'archlinux-base_20231015-1_amd64.tar.zst',
    }

    # Runner resource configurations
    RUNNER_RESOURCES = {
        'windows-10': {'cores': 4, 'memory': 8192, 'disk': 60, 'type': 'vm'},
        'windows-11': {'cores': 4, 'memory': 8192, 'disk': 60, 'type': 'vm'},
        'windows-server-2022': {'cores': 4, 'memory': 16384, 'disk': 80, 'type': 'vm'},
        'windows-server-2025': {'cores': 4, 'memory': 16384, 'disk': 80, 'type': 'vm'},
        'debian': {'cores': 2, 'memory': 4096, 'disk': 40, 'type': 'lxc'},
        'ubuntu': {'cores': 2, 'memory': 4096, 'disk': 40, 'type': 'lxc'},
        'arch': {'cores': 2, 'memory': 4096, 'disk': 40, 'type': 'lxc'},
        'rocky': {'cores': 2, 'memory': 4096, 'disk': 40, 'type': 'lxc'},
        'macos': {'cores': 4, 'memory': 8192, 'disk': 80, 'type': 'vm'},
    }

    def __init__(self, host, port=8006, user=None, password=None, token_name=None, token_value=None, verify_ssl=False):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.token_name = token_name
        self.token_value = token_value
        self.verify_ssl = verify_ssl
        self.proxmox = None

    def connect(self):
        """Establish connection to Proxmox API."""
        from proxmoxer import ProxmoxAPI

        if self.token_name and self.token_value:
            self.proxmox = ProxmoxAPI(
                self.host,
                port=self.port,
                user=self.user,
                token_name=self.token_name,
                token_value=self.token_value,
                verify_ssl=self.verify_ssl
            )
        else:
            self.proxmox = ProxmoxAPI(
                self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                verify_ssl=self.verify_ssl
            )
        return self

    def test_connection(self):
        """Test the connection and return version info."""
        version = self.proxmox.version.get()
        return {'success': True, 'version': version.get('version')}

    def get_nodes(self):
        """Get list of available nodes."""
        return [node['node'] for node in self.proxmox.nodes.get()]

    def get_node_status(self, node):
        """Get node status including CPU, memory, storage."""
        status = self.proxmox.nodes(node).status.get()
        return {
            'cpu_cores': status.get('cpuinfo', {}).get('cpus', 0),
            'memory_total': status.get('memory', {}).get('total', 0),
            'memory_used': status.get('memory', {}).get('used', 0),
        }

    def get_storage_pools(self, node, content_type=None):
        """Get available storage pools."""
        storages = self.proxmox.nodes(node).storage.get()
        if content_type:
            storages = [s for s in storages if content_type in s.get('content', '')]
        return storages

    def get_next_vmid(self):
        """Get next available VMID."""
        cluster_resources = self.proxmox.cluster.resources.get(type='vm')
        used_ids = {r['vmid'] for r in cluster_resources}
        vmid = 100
        while vmid in used_ids:
            vmid += 1
        return vmid

    def download_iso_to_proxmox(self, node, storage, url, filename, callback=None):
        """Download ISO directly to Proxmox storage."""
        task = self.proxmox.nodes(node).storage(storage)('download-url').post(
            url=url,
            filename=filename,
            content='iso'
        )
        return self.wait_for_task(node, task, callback)

    def wait_for_task(self, node, task_id, callback=None, timeout=3600):
        """Wait for a Proxmox task to complete."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.proxmox.nodes(node).tasks(task_id).status.get()
            if callback:
                callback(status)
            if status['status'] == 'stopped':
                if status.get('exitstatus') == 'OK':
                    return {'success': True, 'task': task_id}
                else:
                    return {'success': False, 'error': status.get('exitstatus', 'Task failed')}
            time.sleep(2)
        return {'success': False, 'error': 'Task timed out'}

    def get_available_isos(self, node, storage):
        """Get list of available ISOs in storage."""
        try:
            content = self.proxmox.nodes(node).storage(storage).content.get()
            return [item for item in content if item.get('content') == 'iso']
        except Exception:
            return []

    def get_available_templates(self, node, storage='local'):
        """Get list of available container templates."""
        try:
            content = self.proxmox.nodes(node).storage(storage).content.get()
            return [item for item in content if item.get('content') == 'vztmpl']
        except Exception:
            return []

    def download_template(self, node, storage, template):
        """Download a container template."""
        task = self.proxmox.nodes(node).storage(storage)('download-url').post(
            url=f'http://download.proxmox.com/images/system/{template}',
            filename=template,
            content='vztmpl'
        )
        return self.wait_for_task(node, task)

    # =========================================================================
    # Container (LXC) Management
    # =========================================================================

    def create_container(self, node, vmid, hostname, ostemplate, storage, rootfs_size,
                         cores=2, memory=4096, bridge='vmbr0', ip='dhcp',
                         gateway=None, ssh_keys=None, password=None, start=False):
        """Create an LXC container."""
        params = {
            'vmid': vmid,
            'hostname': hostname,
            'ostemplate': ostemplate,
            'storage': storage,
            'rootfs': f'{storage}:{rootfs_size}',
            'cores': cores,
            'memory': memory,
            'unprivileged': 1,
            'onboot': 1,
            'start': 1 if start else 0,
        }

        # Network configuration
        if ip == 'dhcp':
            params['net0'] = f'name=eth0,bridge={bridge},ip=dhcp'
        else:
            cidr = ip if '/' in ip else f'{ip}/24'
            net_config = f'name=eth0,bridge={bridge},ip={cidr}'
            if gateway:
                net_config += f',gw={gateway}'
            params['net0'] = net_config

        # SSH keys
        if ssh_keys:
            params['ssh-public-keys'] = ssh_keys

        # Root password
        if password:
            params['password'] = password

        task = self.proxmox.nodes(node).lxc.create(**params)
        result = self.wait_for_task(node, task)

        if result['success'] and start:
            time.sleep(2)
            self.start_container(node, vmid)

        return result

    def start_container(self, node, vmid):
        """Start a container."""
        try:
            self.proxmox.nodes(node).lxc(vmid).status.start.post()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def stop_container(self, node, vmid):
        """Stop a container."""
        try:
            self.proxmox.nodes(node).lxc(vmid).status.stop.post()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_container_status(self, node, vmid):
        """Get container status."""
        return self.proxmox.nodes(node).lxc(vmid).status.current.get()

    def get_container_ip(self, node, vmid, timeout=120):
        """Wait for and return container IP address."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                config = self.proxmox.nodes(node).lxc(vmid).config.get()
                net0 = config.get('net0', '')
                if 'ip=' in net0:
                    ip_part = [p for p in net0.split(',') if p.startswith('ip=')]
                    if ip_part and ip_part[0] != 'ip=dhcp':
                        return ip_part[0].replace('ip=', '').split('/')[0]

                # Try to get IP from interfaces
                interfaces = self.proxmox.nodes(node).lxc(vmid).interfaces.get()
                for iface in interfaces:
                    if iface.get('name') == 'eth0':
                        for addr in iface.get('inet', '').split():
                            if addr and not addr.startswith('127.'):
                                return addr.split('/')[0]
            except Exception:
                pass
            time.sleep(3)
        return None

    def provision_container(self, node, vmid, script, timeout=600):
        """Execute a provisioning script inside a container via SSH."""
        ip = self.get_container_ip(node, vmid)
        if not ip:
            return {'success': False, 'error': 'Could not get container IP'}

        # Wait for SSH to be ready
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        start_time = time.time()
        connected = False
        while time.time() - start_time < 120:
            try:
                ssh.connect(ip, username='root', password='root', timeout=10)
                connected = True
                break
            except Exception:
                time.sleep(5)

        if not connected:
            return {'success': False, 'error': 'Could not connect via SSH'}

        try:
            # Execute the script
            stdin, stdout, stderr = ssh.exec_command(f'bash -c "{script}"', timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode()
            errors = stderr.read().decode()

            ssh.close()

            if exit_code == 0:
                return {'success': True, 'output': output}
            else:
                return {'success': False, 'error': errors or output, 'exit_code': exit_code}
        except Exception as e:
            ssh.close()
            return {'success': False, 'error': str(e)}

    # =========================================================================
    # VM (QEMU) Management
    # =========================================================================

    def create_vm(self, node, vmid, name, memory, cores, storage, disk_size,
                  bridge='vmbr0', ostype='l26', iso=None, bios='seabios',
                  machine='pc', cpu='host', is_macos=False, is_windows=False):
        """Create a QEMU VM."""
        params = {
            'vmid': vmid,
            'name': name,
            'memory': memory,
            'cores': cores,
            'sockets': 1,
            'cpu': cpu,
            'net0': f'virtio,bridge={bridge}',
            'scsihw': 'virtio-scsi-pci',
            'scsi0': f'{storage}:{disk_size}',
            'ostype': ostype,
            'boot': 'order=scsi0;ide2',
            'agent': 'enabled=1',
        }

        # ISO attachment
        if iso:
            params['ide2'] = f'{iso},media=cdrom'

        # macOS-specific configuration
        if is_macos:
            osk = 'ourhardworkbythesewordsguardedpleasedontsteal(c)AppleComputerInc'
            params.update({
                'bios': 'ovmf',
                'machine': 'q35',
                'vga': 'vmware',
                'ostype': 'other',
                'efidisk0': f'{storage}:1',
                'args': ' '.join([
                    f'-device isa-applesmc,osk={osk}',
                    '-smbios type=2',
                    '-device usb-kbd,bus=ehci.0,port=2',
                    '-global nec-usb-xhci.msi=off',
                    '-global ICH9-LPC.acpi-pci-hotplug-with-bridge-support=off',
                    '-cpu host,kvm=on,vendor=GenuineIntel,+kvm_pv_unhalt,+kvm_pv_eoi,+hypervisor,+invtsc'
                ])
            })
        # Windows-specific configuration
        elif is_windows:
            params.update({
                'bios': 'ovmf',
                'machine': 'q35',
                'ostype': 'win11',
                'efidisk0': f'{storage}:1',
                'tpmstate0': f'{storage}:1,version=v2.0',
            })
        else:
            params['bios'] = bios
            params['machine'] = machine

        task = self.proxmox.nodes(node).qemu.create(**params)
        return self.wait_for_task(node, task)

    def start_vm(self, node, vmid):
        """Start a VM."""
        try:
            self.proxmox.nodes(node).qemu(vmid).status.start.post()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def stop_vm(self, node, vmid):
        """Stop a VM."""
        try:
            self.proxmox.nodes(node).qemu(vmid).status.stop.post()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_vm_status(self, node, vmid):
        """Get VM status."""
        return self.proxmox.nodes(node).qemu(vmid).status.current.get()


# =============================================================================
# Installation Scripts
# =============================================================================

def get_gitlab_install_script(domain, admin_password, letsencrypt_email=None):
    """Get GitLab installation script."""
    external_url = f'https://{domain}' if letsencrypt_email else f'http://{domain}'

    script = f'''#!/bin/bash
set -e

# Update system
apt-get update
apt-get install -y curl openssh-server ca-certificates tzdata perl

# Add GitLab repository
curl -sS https://packages.gitlab.com/install/repositories/gitlab/gitlab-ee/script.deb.sh | bash

# Install GitLab
GITLAB_ROOT_PASSWORD="{admin_password}" EXTERNAL_URL="{external_url}" apt-get install -y gitlab-ee

# Configure GitLab
cat >> /etc/gitlab/gitlab.rb << 'GITLAB_CONFIG'
gitlab_rails['initial_root_password'] = "{admin_password}"
'''

    if letsencrypt_email:
        script += f'''
letsencrypt['enable'] = true
letsencrypt['contact_emails'] = ['{letsencrypt_email}']
'''

    script += '''GITLAB_CONFIG

# Reconfigure GitLab
gitlab-ctl reconfigure

echo "GitLab installation complete!"
'''
    return script


def get_runner_install_script(runner_type, gitlab_url, registration_token):
    """Get GitLab runner installation script based on runner type."""

    if runner_type in ['debian', 'ubuntu', 'rocky', 'arch']:
        return get_linux_runner_script(runner_type, gitlab_url, registration_token)
    elif runner_type.startswith('windows'):
        return get_windows_runner_script(gitlab_url, registration_token)
    elif runner_type == 'macos':
        return get_macos_runner_script(gitlab_url, registration_token)
    else:
        return None


def get_linux_runner_script(distro, gitlab_url, registration_token):
    """Get Linux runner installation script."""
    return f'''#!/bin/bash
set -e

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Install GitLab Runner
curl -L "https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.deb.sh" | bash
apt-get install -y gitlab-runner

# Register runner
gitlab-runner register \\
    --non-interactive \\
    --url "{gitlab_url}" \\
    --registration-token "{registration_token}" \\
    --executor "docker" \\
    --docker-image "alpine:latest" \\
    --description "{distro}-runner" \\
    --tag-list "linux,{distro},docker" \\
    --run-untagged="true" \\
    --locked="false"

# Start runner
gitlab-runner start

echo "GitLab Runner ({distro}) installation complete!"
'''


def get_windows_runner_script(gitlab_url, registration_token):
    """Get Windows runner installation script (PowerShell)."""
    return f'''# PowerShell script for Windows GitLab Runner installation
$ErrorActionPreference = "Stop"

# Create runner directory
New-Item -ItemType Directory -Force -Path C:\\GitLab-Runner

# Download runner
Invoke-WebRequest -Uri "https://gitlab-runner-downloads.s3.amazonaws.com/latest/binaries/gitlab-runner-windows-amd64.exe" -OutFile "C:\\GitLab-Runner\\gitlab-runner.exe"

# Register runner
cd C:\\GitLab-Runner
.\\gitlab-runner.exe register `
    --non-interactive `
    --url "{gitlab_url}" `
    --registration-token "{registration_token}" `
    --executor "shell" `
    --description "windows-runner" `
    --tag-list "windows,shell" `
    --run-untagged="true" `
    --locked="false"

# Install as service
.\\gitlab-runner.exe install
.\\gitlab-runner.exe start

Write-Host "GitLab Runner (Windows) installation complete!"
'''


def get_macos_runner_script(gitlab_url, registration_token):
    """Get macOS runner installation script."""
    return f'''#!/bin/bash
set -e

# Install Homebrew if not present
if ! command -v brew &> /dev/null; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install GitLab Runner
brew install gitlab-runner

# Register runner
gitlab-runner register \\
    --non-interactive \\
    --url "{gitlab_url}" \\
    --registration-token "{registration_token}" \\
    --executor "shell" \\
    --description "macos-runner" \\
    --tag-list "macos,darwin,shell,xcode" \\
    --run-untagged="true" \\
    --locked="false"

# Install Xcode command line tools
xcode-select --install 2>/dev/null || true

# Install common build tools
brew install cocoapods fastlane

# Start runner as service
brew services start gitlab-runner

echo "GitLab Runner (macOS) installation complete!"
'''
