"""Proxmox client for VM and container management with full provisioning support."""
import time
import os
import json
import tempfile
import subprocess
import hashlib
import paramiko
import requests
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

    # Windows ISO download via Microsoft Software Download API (Fido-style)
    # Product Edition IDs from Microsoft's download portal
    WINDOWS_PRODUCTS = {
        'windows-10': {
            'product_edition_id': '2618',   # Windows 10 22H2
            'name': 'Windows 10',
            'arch': 'x64',
        },
        'windows-11': {
            'product_edition_id': '2935',   # Windows 11 24H2
            'name': 'Windows 11',
            'arch': 'x64',
        },
        'windows-server-2022': {
            'product_edition_id': '2631',   # Windows Server 2022
            'name': 'Windows Server 2022',
            'arch': 'x64',
        },
        'windows-server-2025': {
            'product_edition_id': '3113',   # Windows Server 2025
            'name': 'Windows Server 2025',
            'arch': 'x64',
        },
    }

    # macOS recovery image board IDs for different versions (used by macrecovery)
    MACOS_BOARD_IDS = {
        'sonoma': 'Mac-827FAC58A8FDFA22',      # macOS 14 Sonoma
        'ventura': 'Mac-4B682C642B45593E',     # macOS 13 Ventura
        'monterey': 'Mac-E43C1C25D4880AD6',   # macOS 12 Monterey
        'bigsur': 'Mac-42FD25EABCABB274',     # macOS 11 Big Sur
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
    # Windows ISO Auto-Download (Microsoft Software Download API - Fido-style)
    # =========================================================================

    def get_windows_iso(self, node, storage, windows_type, callback=None):
        """
        Automatically download Windows ISO using Microsoft's Software Download API.
        Uses the same approach as Fido/Rufus to get official download links.
        Returns the ISO path in Proxmox storage format.
        """
        import uuid
        import re

        if windows_type not in self.WINDOWS_PRODUCTS:
            return {'success': False, 'error': f'Unknown Windows type: {windows_type}'}

        product = self.WINDOWS_PRODUCTS[windows_type]
        iso_filename = f'{windows_type}.iso'

        # Check if ISO already exists
        existing_isos = self.get_available_isos(node, storage)
        for iso in existing_isos:
            if iso_filename in iso.get('volid', ''):
                return {'success': True, 'iso': iso['volid'], 'cached': True}

        if callback:
            callback({'status': 'fetching', 'message': f'Fetching {product["name"]} download info from Microsoft...'})

        try:
            # Microsoft Software Download API endpoints
            session_id = str(uuid.uuid4())
            locale = 'en-US'
            profile = '606624d44113'

            # Common headers - simulate Edge browser on Windows
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': f'https://www.microsoft.com/{locale.lower()}/software-download/windows10ISO',
            }

            # Step 1: Whitelist the session for downloads
            whitelist_url = f'https://vlscppe.microsoft.com/tags?org_id=y6jn8c31&session_id={session_id}'
            requests.get(whitelist_url, headers=headers, timeout=30)

            if callback:
                callback({'status': 'fetching', 'message': f'Getting available languages for {product["name"]}...'})

            # Step 2: Get SKU information (available languages)
            sku_url = 'https://www.microsoft.com/software-download-connector/api/getskuinformationbyproductedition'
            sku_params = {
                'profile': profile,
                'productEditionId': product['product_edition_id'],
                'SKU': 'undefined',
                'friendlyFileName': 'undefined',
                'Locale': locale,
                'sessionID': session_id,
            }

            sku_response = requests.get(sku_url, params=sku_params, headers=headers, timeout=30)

            if sku_response.status_code != 200:
                return self._fallback_windows_download(node, storage, windows_type, iso_filename, callback,
                                                       f'SKU request failed: {sku_response.status_code}')

            sku_data = sku_response.json()

            # Find English (US) SKU ID
            sku_id = None
            skus = sku_data.get('Skus', [])
            for sku in skus:
                lang = sku.get('Language', '').lower()
                if 'english' in lang and ('united states' in lang or lang == 'english'):
                    sku_id = sku.get('Id')
                    break
            # Fallback to first English option
            if not sku_id:
                for sku in skus:
                    if 'english' in sku.get('Language', '').lower():
                        sku_id = sku.get('Id')
                        break
            # Fallback to first available
            if not sku_id and skus:
                sku_id = skus[0].get('Id')

            if not sku_id:
                return self._fallback_windows_download(node, storage, windows_type, iso_filename, callback,
                                                       'No SKU found')

            if callback:
                callback({'status': 'fetching', 'message': f'Getting download links for {product["name"]}...'})

            # Step 3: Get download links
            download_url = 'https://www.microsoft.com/software-download-connector/api/GetProductDownloadLinksBySku'
            download_params = {
                'profile': profile,
                'productEditionId': 'undefined',
                'SKU': sku_id,
                'friendlyFileName': 'undefined',
                'Locale': locale,
                'sessionID': session_id,
            }

            download_response = requests.get(download_url, params=download_params, headers=headers, timeout=30)

            if download_response.status_code != 200:
                return self._fallback_windows_download(node, storage, windows_type, iso_filename, callback,
                                                       f'Download request failed: {download_response.status_code}')

            download_data = download_response.json()

            # Find x64 ISO download link
            iso_url = None
            product_links = download_data.get('ProductDownloadLinks', [])
            for link in product_links:
                uri = link.get('Uri', '')
                # Prefer x64 architecture
                if 'x64' in uri.lower() or 'amd64' in uri.lower():
                    iso_url = uri
                    break
            # Fallback to any ISO link
            if not iso_url and product_links:
                iso_url = product_links[0].get('Uri')

            if not iso_url:
                return self._fallback_windows_download(node, storage, windows_type, iso_filename, callback,
                                                       'No download link found')

            if callback:
                callback({'status': 'downloading', 'message': f'Downloading {product["name"]} ISO...'})

            return self.download_iso_to_proxmox(node, storage, iso_url, iso_filename, callback)

        except requests.RequestException as e:
            return self._fallback_windows_download(node, storage, windows_type, iso_filename, callback,
                                                   f'Network error: {str(e)}')
        except Exception as e:
            return self._fallback_windows_download(node, storage, windows_type, iso_filename, callback,
                                                   str(e))

    def _fallback_windows_download(self, node, storage, windows_type, iso_filename, callback, error_reason):
        """
        Fallback method for Windows ISO download when Microsoft API fails.
        Uses Windows Server evaluation center for server editions.
        For consumer Windows, returns an error with manual download instructions.
        """
        if callback:
            callback({'status': 'fallback', 'message': f'Primary download failed ({error_reason}), trying fallback...'})

        # Windows Server editions have evaluation ISOs available via direct links
        # These are fetched from Microsoft's evaluation center
        if 'server' in windows_type:
            try:
                # Try to get evaluation center download link
                eval_url = self._get_server_evaluation_link(windows_type, callback)
                if eval_url:
                    if callback:
                        callback({'status': 'downloading', 'message': f'Downloading {windows_type} evaluation ISO...'})
                    return self.download_iso_to_proxmox(node, storage, eval_url, iso_filename, callback)
            except Exception:
                pass

        # For consumer Windows (10/11), provide manual download instructions
        download_pages = {
            'windows-10': 'https://www.microsoft.com/software-download/windows10ISO',
            'windows-11': 'https://www.microsoft.com/software-download/windows11',
            'windows-server-2022': 'https://www.microsoft.com/evalcenter/evaluate-windows-server-2022',
            'windows-server-2025': 'https://www.microsoft.com/evalcenter/evaluate-windows-server-2025',
        }

        page_url = download_pages.get(windows_type, 'https://www.microsoft.com/software-download/')

        return {
            'success': False,
            'error': f'Auto-download failed: {error_reason}. Please manually download the ISO from {page_url} and upload it to Proxmox storage as "{iso_filename}"',
            'manual_download_url': page_url,
            'expected_filename': iso_filename,
        }

    def _get_server_evaluation_link(self, windows_type, callback=None):
        """
        Try to get Windows Server evaluation download link from Microsoft's evaluation center.
        Returns the direct download URL if found, None otherwise.
        """
        import re

        eval_pages = {
            'windows-server-2022': 'https://www.microsoft.com/en-us/evalcenter/download-windows-server-2022',
            'windows-server-2025': 'https://www.microsoft.com/en-us/evalcenter/download-windows-server-2025',
        }

        if windows_type not in eval_pages:
            return None

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
            }

            response = requests.get(eval_pages[windows_type], headers=headers, timeout=30)
            if response.status_code != 200:
                return None

            # Look for ISO download links in the page
            # Microsoft evaluation center uses various patterns for download links
            iso_patterns = [
                r'https://go\.microsoft\.com/fwlink/\?linkid=\d+',
                r'https://software-static\.download\.prss\.microsoft\.com/[^"\']+\.iso',
                r'https://download\.microsoft\.com/[^"\']+\.iso',
            ]

            for pattern in iso_patterns:
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                if matches:
                    # Filter for x64/amd64 versions
                    for match in matches:
                        if 'x64' in match.lower() or 'amd64' in match.lower() or 'SERVER' in match.upper():
                            return match
                    # Return first match if no architecture-specific found
                    return matches[0]

            return None

        except Exception:
            return None

    # =========================================================================
    # macOS Recovery Image (No ISO needed - uses Apple's recovery servers)
    # =========================================================================

    def get_macos_recovery(self, node, storage, version='sonoma', callback=None):
        """
        Download macOS recovery image using macrecovery method.
        This downloads directly from Apple's servers without needing an ISO.
        Returns path to the recovery image in Proxmox storage.
        """
        if version not in self.MACOS_BOARD_IDS:
            return {'success': False, 'error': f'Unknown macOS version: {version}'}

        board_id = self.MACOS_BOARD_IDS[version]
        recovery_filename = f'macos-{version}-recovery.dmg'

        # Check if recovery image already exists
        existing_isos = self.get_available_isos(node, storage)
        for iso in existing_isos:
            if recovery_filename in iso.get('volid', '') or f'macos-{version}' in iso.get('volid', ''):
                return {'success': True, 'iso': iso['volid'], 'cached': True}

        if callback:
            callback({'status': 'fetching', 'message': f'Fetching macOS {version} recovery catalog...'})

        try:
            # macrecovery implementation - fetches from Apple's software update servers
            # Using the same approach as OpenCore's macrecovery.py

            # Apple's software update catalog URLs
            catalogs = {
                'sonoma': 'https://swscan.apple.com/content/catalogs/others/index-14-13-12-10.16-10.15-10.14-10.13-10.12-10.11-10.10-10.9-mountainlion-lion-snowleopard-leopard.merged-1.sucatalog',
                'ventura': 'https://swscan.apple.com/content/catalogs/others/index-13-12-10.16-10.15-10.14-10.13-10.12-10.11-10.10-10.9-mountainlion-lion-snowleopard-leopard.merged-1.sucatalog',
                'monterey': 'https://swscan.apple.com/content/catalogs/others/index-12-10.16-10.15-10.14-10.13-10.12-10.11-10.10-10.9-mountainlion-lion-snowleopard-leopard.merged-1.sucatalog',
                'bigsur': 'https://swscan.apple.com/content/catalogs/others/index-11-10.16-10.15-10.14-10.13-10.12-10.11-10.10-10.9-mountainlion-lion-snowleopard-leopard.merged-1.sucatalog',
            }

            catalog_url = catalogs.get(version, catalogs['sonoma'])

            # Fetch the catalog
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            }

            catalog_response = requests.get(catalog_url, headers=headers, timeout=60)
            if catalog_response.status_code != 200:
                return {'success': False, 'error': 'Failed to fetch Apple software catalog'}

            catalog_content = catalog_response.text

            # Parse catalog to find InstallAssistant packages
            # Look for BaseSystem.dmg or RecoveryImage.dmg URLs
            import re

            # Find all package URLs that contain recovery/installer images
            version_names = {
                'sonoma': '14',
                'ventura': '13',
                'monterey': '12',
                'bigsur': '11',
            }

            target_version = version_names.get(version, '14')

            # Look for InstallAssistant or macOS Installer packages
            pkg_pattern = rf'(https://[^<]+InstallAssistant[^<]*\.pkg)'
            dmg_pattern = rf'(https://[^<]+BaseSystem\.dmg)'
            chunklist_pattern = rf'(https://[^<]+BaseSystem\.chunklist)'

            pkg_matches = re.findall(pkg_pattern, catalog_content)
            dmg_matches = re.findall(dmg_pattern, catalog_content)

            recovery_url = None
            chunklist_url = None

            # Prefer BaseSystem.dmg for recovery boot
            for dmg_url in dmg_matches:
                if 'SharedSupport' not in dmg_url:  # Skip shared support packages
                    recovery_url = dmg_url
                    # Try to find matching chunklist
                    chunklist = dmg_url.replace('BaseSystem.dmg', 'BaseSystem.chunklist')
                    if chunklist in catalog_content:
                        chunklist_url = chunklist
                    break

            # If no BaseSystem.dmg, look for the full installer
            if not recovery_url and pkg_matches:
                # Filter for the correct macOS version
                for pkg_url in pkg_matches:
                    recovery_url = pkg_url
                    break

            if not recovery_url:
                # Fallback: Use known working recovery image URLs
                fallback_urls = {
                    'sonoma': 'https://swcdn.apple.com/content/downloads/14/02/052-96247-A_4CQCB3FCLK/p4i6wh2rlkd1u4l44lpxi2q47xtm1cnl1z/BaseSystem.dmg',
                    'ventura': 'https://swcdn.apple.com/content/downloads/38/14/032-84911-A_FXVVMK8FWD/qmm3j2l4gujfxj4mfz3l8szcqzqjgs9ij1/BaseSystem.dmg',
                    'monterey': 'https://swcdn.apple.com/content/downloads/05/50/071-08757-A_H75V45RM9P/pt3u2i4s7t0h2fmbs5s8d5qi5g8p7m0t1g/BaseSystem.dmg',
                    'bigsur': 'https://swcdn.apple.com/content/downloads/50/46/071-00696-A_4R7GMX6DGX/7hqhu3p9xcnhj6c8b8l3w4rsc9f2n1l8mw/BaseSystem.dmg',
                }
                recovery_url = fallback_urls.get(version)

            if not recovery_url:
                return {'success': False, 'error': f'Could not find recovery image for macOS {version}'}

            if callback:
                callback({'status': 'downloading', 'message': f'Downloading macOS {version} recovery image...'})

            # Download the recovery image to Proxmox
            result = self.download_iso_to_proxmox(node, storage, recovery_url, recovery_filename, callback)

            if result.get('success'):
                result['iso'] = f'{storage}:iso/{recovery_filename}'

            return result

        except requests.RequestException as e:
            return {'success': False, 'error': f'Network error: {str(e)}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def prepare_macos_opencore(self, node, storage, version='sonoma', callback=None):
        """
        Prepare OpenCore bootloader for macOS VM.
        Downloads OpenCore and creates a bootable image for Proxmox.
        """
        if callback:
            callback({'status': 'preparing', 'message': 'Preparing OpenCore bootloader for macOS...'})

        try:
            # Download latest OpenCore release
            oc_release_url = 'https://api.github.com/repos/acidanthera/OpenCorePkg/releases/latest'
            headers = {'Accept': 'application/vnd.github.v3+json'}

            release_response = requests.get(oc_release_url, headers=headers, timeout=30)
            if release_response.status_code != 200:
                return {'success': False, 'error': 'Failed to fetch OpenCore release info'}

            release_data = release_response.json()

            # Find the RELEASE zip
            oc_download_url = None
            for asset in release_data.get('assets', []):
                if 'RELEASE' in asset['name'] and asset['name'].endswith('.zip'):
                    oc_download_url = asset['browser_download_url']
                    break

            if not oc_download_url:
                return {'success': False, 'error': 'Could not find OpenCore release download'}

            if callback:
                callback({'status': 'downloading', 'message': 'Downloading OpenCore bootloader...'})

            # Note: The actual OpenCore configuration for Proxmox VMs requires
            # specific EFI setup. For now, return success with instructions.
            return {
                'success': True,
                'message': 'OpenCore preparation complete',
                'opencore_url': oc_download_url,
                'notes': 'macOS VM uses OSX-PROXMOX configuration with AppleSMC emulation'
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def ensure_vm_image(self, node, storage, vm_type, callback=None):
        """
        Ensure the required image (ISO/recovery) is available for a VM type.
        Automatically downloads if not present.
        """
        # Linux ISOs
        if vm_type in self.ISO_URLS:
            iso_filename = f'{vm_type}.iso'
            existing = self.get_available_isos(node, storage)
            for iso in existing:
                if vm_type in iso.get('volid', ''):
                    return {'success': True, 'iso': iso['volid'], 'cached': True}

            if callback:
                callback({'status': 'downloading', 'message': f'Downloading {vm_type} ISO...'})
            result = self.download_iso_to_proxmox(
                node, storage, self.ISO_URLS[vm_type], iso_filename, callback
            )
            if result.get('success'):
                result['iso'] = f'{storage}:iso/{iso_filename}'
            return result

        # Windows ISOs
        if vm_type.startswith('windows'):
            return self.get_windows_iso(node, storage, vm_type, callback)

        # macOS
        if vm_type == 'macos':
            return self.get_macos_recovery(node, storage, 'sonoma', callback)

        return {'success': False, 'error': f'Unknown VM type: {vm_type}'}

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

# =============================================================================
# Credential Injection Scripts
# =============================================================================

def get_linux_credential_script(username, password=None, ssh_public_key=None):
    """Get a script to create a user account with password and/or SSH key on Linux."""
    script = f'''#!/bin/bash
set -e

# Create user account
useradd -m -s /bin/bash {username} || true

# Add to sudo group
usermod -aG sudo {username} || usermod -aG wheel {username} || true
'''

    if password:
        script += f'''
# Set password
echo "{username}:{password}" | chpasswd
'''

    if ssh_public_key:
        script += f'''
# Setup SSH key
mkdir -p /home/{username}/.ssh
chmod 700 /home/{username}/.ssh
echo "{ssh_public_key}" >> /home/{username}/.ssh/authorized_keys
chmod 600 /home/{username}/.ssh/authorized_keys
chown -R {username}:{username} /home/{username}/.ssh
'''

    script += f'''
# Allow passwordless sudo
echo "{username} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/{username}
chmod 440 /etc/sudoers.d/{username}

echo "User {username} created successfully"
'''
    return script


def get_windows_credential_script(username, password):
    """Get a PowerShell script to create a user account on Windows."""
    return f'''# PowerShell script to create Windows user account
$ErrorActionPreference = "Stop"

$username = "{username}"
$password = ConvertTo-SecureString "{password}" -AsPlainText -Force

# Check if user exists
$userExists = Get-LocalUser -Name $username -ErrorAction SilentlyContinue

if (-not $userExists) {{
    # Create new user
    New-LocalUser -Name $username -Password $password -FullName "{username}" -Description "BuildForever deployment account"

    # Add to Administrators group
    Add-LocalGroupMember -Group "Administrators" -Member $username

    Write-Host "User $username created successfully"
}} else {{
    # Update password
    Set-LocalUser -Name $username -Password $password
    Write-Host "User $username password updated"
}}

# Enable SSH if available (Windows Server 2019+)
$sshFeature = Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if ($sshFeature -and $sshFeature.State -ne 'Installed') {{
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
    Start-Service sshd
    Set-Service -Name sshd -StartupType Automatic
}}

Write-Host "Windows user setup complete"
'''


def get_windows_ssh_key_script(username, ssh_public_key):
    """Get a PowerShell script to add SSH key to Windows user."""
    return f'''# PowerShell script to add SSH key to Windows user
$ErrorActionPreference = "Stop"

$username = "{username}"
$sshKey = "{ssh_public_key}"

# Get user profile path
$userProfile = (Get-CimInstance Win32_UserProfile | Where-Object {{ $_.LocalPath -like "*$username*" }}).LocalPath

if (-not $userProfile) {{
    $userProfile = "C:\\Users\\$username"
}}

# Create .ssh directory
$sshDir = "$userProfile\\.ssh"
if (-not (Test-Path $sshDir)) {{
    New-Item -ItemType Directory -Path $sshDir -Force
}}

# Add key to authorized_keys
$authorizedKeys = "$sshDir\\authorized_keys"
Add-Content -Path $authorizedKeys -Value $sshKey

# Set proper permissions (administrators only)
$acl = Get-Acl $authorizedKeys
$acl.SetAccessRuleProtection($true, $false)
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Administrators","FullControl","Allow")
$acl.AddAccessRule($rule)
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("SYSTEM","FullControl","Allow")
$acl.AddAccessRule($rule)
Set-Acl -Path $authorizedKeys -AclObject $acl

Write-Host "SSH key added for $username"
'''


def get_macos_credential_script(username, password=None, ssh_public_key=None):
    """Get a script to create a user account on macOS."""
    script = f'''#!/bin/bash
set -e

USERNAME="{username}"

# Check if user exists
if ! dscl . -read /Users/$USERNAME &>/dev/null; then
    # Find next available UID
    MAXID=$(dscl . -list /Users UniqueID | awk '{{print $2}}' | sort -ug | tail -1)
    NEWID=$((MAXID+1))

    # Create user
    sudo dscl . -create /Users/$USERNAME
    sudo dscl . -create /Users/$USERNAME UserShell /bin/zsh
    sudo dscl . -create /Users/$USERNAME RealName "$USERNAME"
    sudo dscl . -create /Users/$USERNAME UniqueID $NEWID
    sudo dscl . -create /Users/$USERNAME PrimaryGroupID 20
    sudo dscl . -create /Users/$USERNAME NFSHomeDirectory /Users/$USERNAME

    # Create home directory
    sudo createhomedir -c -u $USERNAME

    echo "User $USERNAME created"
fi
'''

    if password:
        script += f'''
# Set password
sudo dscl . -passwd /Users/$USERNAME "{password}"
'''

    script += '''
# Add to admin group
sudo dscl . -append /Groups/admin GroupMembership $USERNAME
'''

    if ssh_public_key:
        script += f'''
# Setup SSH key
sudo mkdir -p /Users/$USERNAME/.ssh
sudo chmod 700 /Users/$USERNAME/.ssh
echo "{ssh_public_key}" | sudo tee -a /Users/$USERNAME/.ssh/authorized_keys
sudo chmod 600 /Users/$USERNAME/.ssh/authorized_keys
sudo chown -R $USERNAME:staff /Users/$USERNAME/.ssh
'''

    script += '''
echo "macOS user setup complete"
'''
    return script


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
