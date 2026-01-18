// GitLab server resource requirements (base requirement)
const GITLAB_SERVER_RESOURCES = { cpu: 4, memory: 8, storage: 50 };

// Runner resource requirements (CPU cores, Memory GB, Storage GB)
const RUNNER_RESOURCES = {
    'windows-10': { cpu: 4, memory: 8, storage: 60 },
    'windows-11': { cpu: 4, memory: 8, storage: 60 },
    'windows-server-2022': { cpu: 4, memory: 16, storage: 80 },
    'windows-server-2025': { cpu: 4, memory: 16, storage: 80 },
    'debian': { cpu: 2, memory: 4, storage: 40 },
    'ubuntu': { cpu: 2, memory: 4, storage: 40 },
    'arch': { cpu: 2, memory: 4, storage: 40 },
    'rocky': { cpu: 2, memory: 4, storage: 40 },
    'macos': { cpu: 4, memory: 8, storage: 80 }
};

// Store node capacity after successful connection test
let nodeCapacity = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    const deploymentForm = document.getElementById('deploymentForm');

    // Load saved configurations on page load
    loadSavedConfigs();

    // Update runner count and resources on checkbox change
    document.querySelectorAll('input[name="runners"]').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updateSelectedCount();
            updateResourceTotals();
        });
    });

    // Traefik toggle handler
    const traefikCheckbox = document.getElementById('traefik');
    if (traefikCheckbox) {
        traefikCheckbox.addEventListener('change', toggleTraefikOptions);
    }

    // Initialize resource display
    updateResourceTotals();

    // Form submission handler
    deploymentForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const adminPassword = document.getElementById('adminPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;

        // Validate passwords match
        if (adminPassword !== confirmPassword) {
            showStatus('error', 'Passwords do not match!');
            return;
        }

        // Validate password strength
        if (adminPassword.length < 8) {
            showStatus('error', 'Password must be at least 8 characters long!');
            return;
        }

        // Collect selected runners
        const selectedRunners = [];
        document.querySelectorAll('input[name="runners"]:checked').forEach(checkbox => {
            selectedRunners.push(checkbox.value);
        });

        // Get selected credential
        const credentialId = document.getElementById('deployCredential')?.value || '';

        // Get Proxmox configuration
        const providerConfig = getProviderConfig();

        // Validate Proxmox connection is configured
        if (!providerConfig.host || !providerConfig.user || !providerConfig.password) {
            showStatus('error', 'Please configure Proxmox connection and test it first');
            return;
        }

        // Collect form data
        const deploymentData = {
            domain: document.getElementById('domain').value,
            email: document.getElementById('email').value,
            admin_password: adminPassword,
            letsencrypt_enabled: document.getElementById('letsencrypt').checked,
            runners: selectedRunners,
            // Traefik settings
            traefik_enabled: document.getElementById('traefik').checked,
            base_domain: document.getElementById('baseDomain')?.value || '',
            traefik_dashboard: document.getElementById('traefikDashboard')?.checked || false,
            // Infrastructure provider - always Proxmox
            provider: 'proxmox',
            provider_config: providerConfig,
            // Credential for VM/container injection
            credential_id: credentialId ? parseInt(credentialId) : null,
            // Network configuration
            network_config: getNetworkConfig()
        };

        // Show loading status
        showStatus('info', `Preparing to deploy GitLab server${selectedRunners.length > 0 ? ' and ' + selectedRunners.length + ' runner(s)' : ''}...`);
        showSpinner();

        // Send deployment request
        fetch('/api/deploy', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(deploymentData)
        })
        .then(response => response.json())
        .then(data => {
            hideSpinner();
            if (data.success) {
                showStatus('success', data.message);
                showDeploymentPlan(data.deployment_plan);

                // Ask for confirmation before executing
                if (confirm(`Ready to deploy:\n- GitLab Server\n- ${selectedRunners.length} Runner(s)\n\nThis may take 30-60 minutes. Continue?`)) {
                    executeDeployment(data.deployment_id);
                }
            } else {
                showStatus('error', data.error || 'Deployment failed');
            }
        })
        .catch(error => {
            hideSpinner();
            showStatus('error', 'An error occurred: ' + error.message);
        });
    });
});

// Update selected runner count display
function updateSelectedCount() {
    const count = document.querySelectorAll('input[name="runners"]:checked').length;
    const countDisplay = document.querySelector('.selected-count');
    if (countDisplay) {
        countDisplay.textContent = `${count} selected`;
    }
}

// Calculate and update resource totals
function updateResourceTotals() {
    // Start with GitLab server requirements
    let totalCpu = GITLAB_SERVER_RESOURCES.cpu;
    let totalMemory = GITLAB_SERVER_RESOURCES.memory;
    let totalStorage = GITLAB_SERVER_RESOURCES.storage;

    // Add runner requirements
    document.querySelectorAll('input[name="runners"]:checked').forEach(checkbox => {
        const runner = checkbox.value;
        const resources = RUNNER_RESOURCES[runner];
        if (resources) {
            totalCpu += resources.cpu;
            totalMemory += resources.memory;
            totalStorage += resources.storage;
        }
    });

    // Update display
    document.getElementById('totalCpu').textContent = totalCpu;
    document.getElementById('totalMemory').textContent = `${totalMemory} GB`;
    document.getElementById('totalStorage').textContent = `${totalStorage} GB`;

    // Update comparison status if node capacity is available
    if (nodeCapacity) {
        updateResourceComparison(totalCpu, totalMemory, totalStorage);
    }
}

// Update resource comparison indicators
function updateResourceComparison(requiredCpu, requiredMemory, requiredStorage) {
    if (!nodeCapacity) return;

    // CPU status
    const cpuStatus = document.getElementById('cpuStatus');
    if (cpuStatus) {
        if (requiredCpu <= nodeCapacity.cpu * 0.7) {
            cpuStatus.textContent = 'OK';
            cpuStatus.className = 'resource-status ok';
        } else if (requiredCpu <= nodeCapacity.cpu) {
            cpuStatus.textContent = 'TIGHT';
            cpuStatus.className = 'resource-status warning';
        } else {
            cpuStatus.textContent = 'OVER';
            cpuStatus.className = 'resource-status error';
        }
    }

    // Memory status
    const memoryStatus = document.getElementById('memoryStatus');
    if (memoryStatus) {
        if (requiredMemory <= nodeCapacity.memory * 0.7) {
            memoryStatus.textContent = 'OK';
            memoryStatus.className = 'resource-status ok';
        } else if (requiredMemory <= nodeCapacity.memory) {
            memoryStatus.textContent = 'TIGHT';
            memoryStatus.className = 'resource-status warning';
        } else {
            memoryStatus.textContent = 'OVER';
            memoryStatus.className = 'resource-status error';
        }
    }

    // Storage status
    const storageStatus = document.getElementById('storageStatus');
    if (storageStatus) {
        if (requiredStorage <= nodeCapacity.storage * 0.7) {
            storageStatus.textContent = 'OK';
            storageStatus.className = 'resource-status ok';
        } else if (requiredStorage <= nodeCapacity.storage) {
            storageStatus.textContent = 'TIGHT';
            storageStatus.className = 'resource-status warning';
        } else {
            storageStatus.textContent = 'OVER';
            storageStatus.className = 'resource-status error';
        }
    }
}

// Set node capacity and show comparison panel
function setNodeCapacity(capacity, nodeName) {
    nodeCapacity = capacity;

    // Update display
    document.getElementById('nodeCpu').textContent = capacity.cpu;
    document.getElementById('nodeMemory').textContent = `${capacity.memory} GB`;
    document.getElementById('nodeStorage').textContent = `${capacity.storage} GB`;
    document.getElementById('nodeNameDisplay').textContent = nodeName ? `(${nodeName})` : '';

    // Show the panel
    document.getElementById('nodeCapacityPanel').style.display = 'block';

    // Update comparison
    updateResourceTotals();
}

// Hide node capacity panel
function hideNodeCapacity() {
    nodeCapacity = null;
    document.getElementById('nodeCapacityPanel').style.display = 'none';
}

// Toggle Traefik options visibility
function toggleTraefikOptions() {
    const traefikCheckbox = document.getElementById('traefik');
    const traefikOptions = document.getElementById('traefikOptions');

    if (traefikOptions) {
        if (traefikCheckbox.checked) {
            traefikOptions.style.display = 'block';
            // Auto-populate base domain from GitLab domain
            const domain = document.getElementById('domain').value;
            if (domain && !document.getElementById('baseDomain').value) {
                const parts = domain.split('.');
                if (parts.length > 1) {
                    document.getElementById('baseDomain').value = parts.slice(-2).join('.');
                }
            }
        } else {
            traefikOptions.style.display = 'none';
        }
    }
}

// Show deployment plan
function showDeploymentPlan(plan) {
    const progressDiv = document.getElementById('deploymentProgress');
    progressDiv.innerHTML = '<h3>Deployment Plan:</h3><ul>';

    if (plan && plan.steps) {
        plan.steps.forEach(step => {
            progressDiv.innerHTML += `<li>${step}</li>`;
        });
    }

    progressDiv.innerHTML += '</ul>';
    progressDiv.style.display = 'block';
}

// Execute the deployment
function executeDeployment(deploymentId) {
    showStatus('info', 'Starting deployment... This may take 30-60 minutes.');
    showSpinner();
    updateProgress('Deploying GitLab Server...', 10);

    fetch('/api/execute-deployment', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ deployment_id: deploymentId })
    })
    .then(response => response.json())
    .then(data => {
        hideSpinner();
        if (data.success) {
            showStatus('success', data.message);
            if (data.output) {
                showLogs(data.output);
            }
            if (data.runner_urls) {
                showRunnerStatus(data.runner_urls);
            }
        } else {
            showStatus('error', data.error || 'Deployment failed');
            if (data.output) {
                showLogs(data.output);
            }
        }
    })
    .catch(error => {
        hideSpinner();
        showStatus('error', 'An error occurred: ' + error.message);
    });

    // Poll for deployment progress
    pollDeploymentProgress(deploymentId);
}

// Poll deployment progress
function pollDeploymentProgress(deploymentId) {
    const interval = setInterval(() => {
        fetch(`/api/status/${deploymentId}`)
            .then(response => response.json())
            .then(data => {
                if (data.progress) {
                    updateProgress(data.current_step, data.progress);
                }
                if (data.completed) {
                    clearInterval(interval);
                }
            })
            .catch(() => {
                // Ignore polling errors
            });
    }, 5000); // Poll every 5 seconds
}

// Update progress display
function updateProgress(step, percentage) {
    const progressDiv = document.getElementById('deploymentProgress');
    progressDiv.innerHTML = `
        <div class="progress-bar">
            <div class="progress-fill" style="width: ${percentage}%"></div>
        </div>
        <p class="progress-text">${step} (${percentage}%)</p>
    `;
    progressDiv.style.display = 'block';
}

// Show runner status
function showRunnerStatus(runnerUrls) {
    const progressDiv = document.getElementById('deploymentProgress');
    progressDiv.innerHTML += '<h3>Runner Status:</h3><ul>';

    runnerUrls.forEach(runner => {
        progressDiv.innerHTML += `<li><strong>${runner.name}</strong>: ${runner.status}</li>`;
    });

    progressDiv.innerHTML += '</ul>';
}

// Show status message
function showStatus(type, message) {
    const statusSection = document.getElementById('statusSection');
    const statusMessage = document.getElementById('statusMessage');

    statusMessage.className = 'status-message ' + type;
    statusMessage.textContent = message;
    statusSection.style.display = 'block';

    // Scroll to status
    statusSection.scrollIntoView({ behavior: 'smooth' });
}

// Show deployment logs
function showLogs(logs) {
    const logsDiv = document.getElementById('deploymentLogs');
    logsDiv.textContent = logs;
    logsDiv.style.display = 'block';
}

// Show loading spinner
function showSpinner() {
    const statusSection = document.getElementById('statusSection');
    let spinner = document.querySelector('.spinner');

    if (!spinner) {
        spinner = document.createElement('div');
        spinner.className = 'spinner';
        statusSection.appendChild(spinner);
    }
}

// Hide loading spinner
function hideSpinner() {
    const spinner = document.querySelector('.spinner');
    if (spinner) {
        spinner.remove();
    }
}

// Hide status section
function hideStatus() {
    document.getElementById('statusSection').style.display = 'none';
}

// Reset form
function resetForm() {
    document.getElementById('deploymentForm').reset();
    hideStatus();
}

// Select all runners
function selectAllRunners() {
    document.querySelectorAll('input[name="runners"]').forEach(checkbox => {
        checkbox.checked = true;
    });
    updateSelectedCount();
    updateResourceTotals();
}

// Deselect all runners
function deselectAllRunners() {
    document.querySelectorAll('input[name="runners"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    updateSelectedCount();
    updateResourceTotals();
}

// ============================================================================
// Saved Configurations
// ============================================================================

// Load saved configurations into dropdown
function loadSavedConfigs() {
    fetch('/api/configs')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const select = document.getElementById('savedConfig');
                // Clear existing options except the first one
                select.innerHTML = '<option value="">-- Select a saved configuration --</option>';

                data.configs.forEach(config => {
                    const option = document.createElement('option');
                    option.value = config.id;
                    option.textContent = `${config.name} (${config.domain})`;
                    select.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('Failed to load saved configs:', error);
        });
}

// Load a saved configuration into the form
function loadSavedConfig() {
    const select = document.getElementById('savedConfig');
    const configId = select.value;

    if (!configId) {
        return;
    }

    fetch(`/api/configs/${configId}?include_password=true`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.config) {
                const config = data.config;

                // Fill form fields
                document.getElementById('domain').value = config.domain || '';
                document.getElementById('email').value = config.email || '';

                if (config.admin_password) {
                    document.getElementById('adminPassword').value = config.admin_password;
                    document.getElementById('confirmPassword').value = config.admin_password;
                } else {
                    document.getElementById('adminPassword').value = '';
                    document.getElementById('confirmPassword').value = '';
                }

                document.getElementById('letsencrypt').checked = config.letsencrypt_enabled;

                // Traefik settings
                const traefikCheckbox = document.getElementById('traefik');
                if (traefikCheckbox) {
                    traefikCheckbox.checked = config.traefik_enabled || false;
                    toggleTraefikOptions();
                }
                if (config.base_domain && document.getElementById('baseDomain')) {
                    document.getElementById('baseDomain').value = config.base_domain;
                }
                if (document.getElementById('traefikDashboard')) {
                    document.getElementById('traefikDashboard').checked = config.traefik_dashboard !== false;
                }

                // Restore Proxmox settings
                if (config.proxmox_config) {
                    setProviderConfig(config.proxmox_config);
                }

                // Restore network settings
                if (config.network_config) {
                    setNetworkConfig(config.network_config);
                }

                // Set runner checkboxes
                document.querySelectorAll('input[name="runners"]').forEach(checkbox => {
                    checkbox.checked = config.runners && config.runners.includes(checkbox.value);
                });

                updateSelectedCount();
                updateResourceTotals();
                showStatus('info', `Loaded configuration: ${config.name}`);
            } else {
                showStatus('error', data.error || 'Failed to load configuration');
            }
        })
        .catch(error => {
            showStatus('error', 'Failed to load configuration: ' + error.message);
        });
}

// Toggle save configuration modal
function toggleSaveConfigModal() {
    const modal = document.getElementById('saveConfigModal');
    if (modal.style.display === 'none' || !modal.style.display) {
        modal.style.display = 'flex';
        document.getElementById('configName').focus();
    } else {
        modal.style.display = 'none';
    }
}

// Save current form configuration
function saveCurrentConfig() {
    const name = document.getElementById('configName').value.trim();

    if (!name) {
        alert('Please enter a configuration name');
        return;
    }

    const domain = document.getElementById('domain').value;
    const email = document.getElementById('email').value;

    if (!domain || !email) {
        alert('Please fill in domain and email before saving');
        return;
    }

    // Collect selected runners
    const selectedRunners = [];
    document.querySelectorAll('input[name="runners"]:checked').forEach(checkbox => {
        selectedRunners.push(checkbox.value);
    });

    // Get Proxmox config (without password for security)
    const proxmoxConfig = getProviderConfig();
    const proxmoxConfigToSave = {
        host: proxmoxConfig.host,
        port: proxmoxConfig.port,
        node: proxmoxConfig.node,
        user: proxmoxConfig.user,
        verify_ssl: proxmoxConfig.verify_ssl,
        storage: proxmoxConfig.storage,
        iso_storage: proxmoxConfig.iso_storage,
        bridge: proxmoxConfig.bridge,
        virtio_iso: proxmoxConfig.virtio_iso,
        windows_isos: proxmoxConfig.windows_isos
    };

    // Get network config
    const networkConfig = getNetworkConfig();

    const config = {
        name: name,
        domain: domain,
        email: email,
        letsencrypt_enabled: document.getElementById('letsencrypt').checked,
        runners: selectedRunners,
        // Traefik settings
        traefik_enabled: document.getElementById('traefik')?.checked || false,
        base_domain: document.getElementById('baseDomain')?.value || '',
        traefik_dashboard: document.getElementById('traefikDashboard')?.checked || false,
        // Proxmox settings
        proxmox_config: proxmoxConfigToSave,
        // Network settings
        network_config: networkConfig
    };

    // Include password if checkbox is checked
    if (document.getElementById('savePassword').checked) {
        config.admin_password = document.getElementById('adminPassword').value;
        // Also save Proxmox password
        config.proxmox_config.password = proxmoxConfig.password;
    }

    fetch('/api/configs', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(config)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            toggleSaveConfigModal();
            loadSavedConfigs();
            showStatus('success', 'Configuration saved successfully');
            document.getElementById('configName').value = '';
            document.getElementById('savePassword').checked = false;
        } else {
            alert(data.error || 'Failed to save configuration');
        }
    })
    .catch(error => {
        alert('Failed to save configuration: ' + error.message);
    });
}

// Toggle deployment history modal
function toggleHistoryModal() {
    const modal = document.getElementById('historyModal');
    if (modal.style.display === 'none' || !modal.style.display) {
        modal.style.display = 'flex';
        loadDeploymentHistory();
    } else {
        modal.style.display = 'none';
    }
}

// Load deployment history
function loadDeploymentHistory() {
    const historyList = document.getElementById('historyList');
    historyList.innerHTML = '<p>Loading...</p>';

    fetch('/api/history')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.history.length > 0) {
                historyList.innerHTML = data.history.map(item => `
                    <div class="history-item">
                        <div class="domain">${item.domain}</div>
                        <div class="meta">
                            <span class="status ${item.status}">${item.status}</span>
                            <span>Started: ${new Date(item.started_at).toLocaleString()}</span>
                            ${item.completed_at ? `<span>Completed: ${new Date(item.completed_at).toLocaleString()}</span>` : ''}
                        </div>
                        ${item.runners && item.runners.length > 0 ? `<div class="meta">Runners: ${item.runners.join(', ')}</div>` : ''}
                    </div>
                `).join('');
            } else if (data.success) {
                historyList.innerHTML = '<p>No deployment history yet.</p>';
            } else {
                historyList.innerHTML = '<p>Failed to load history.</p>';
            }
        })
        .catch(error => {
            historyList.innerHTML = '<p>Failed to load history: ' + error.message + '</p>';
        });
}

// Close modals when clicking outside
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) {
        e.target.style.display = 'none';
    }
});

// Close modals on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.style.display = 'none';
        });
    }
});

// ============================================================================
// Infrastructure Provider Functions
// ============================================================================

// Toggle provider options visibility
function toggleProviderOptions() {
    const provider = document.getElementById('provider').value;

    // Hide all provider options
    document.querySelectorAll('.provider-options').forEach(el => {
        el.style.display = 'none';
    });

    // Show selected provider options
    const optionsId = provider + 'Options';
    const optionsEl = document.getElementById(optionsId);
    if (optionsEl) {
        optionsEl.style.display = 'block';
    }
}

// Get Proxmox configuration
function getProviderConfig() {
    return {
        host: document.getElementById('proxmoxHost')?.value || '',
        port: parseInt(document.getElementById('proxmoxPort')?.value) || 8006,
        node: document.getElementById('proxmoxNode')?.value || 'pve',
        user: document.getElementById('proxmoxUser')?.value || '',
        password: document.getElementById('proxmoxPassword')?.value || '',
        verify_ssl: document.getElementById('proxmoxVerifySSL')?.checked || false,
        storage: document.getElementById('proxmoxStorage')?.value || 'local-lvm',
        iso_storage: document.getElementById('proxmoxIsoStorage')?.value || 'local',
        bridge: document.getElementById('proxmoxBridge')?.value || 'vmbr0',
        // VirtIO drivers ISO for all Windows VMs
        virtio_iso: document.getElementById('isoVirtio')?.value || '',
        // Individual Windows ISOs for each version
        windows_isos: {
            'windows-10': document.getElementById('isoWindows10')?.value || '',
            'windows-11': document.getElementById('isoWindows11')?.value || '',
            'windows-server-2022': document.getElementById('isoWindowsServer2022')?.value || '',
            'windows-server-2025': document.getElementById('isoWindowsServer2025')?.value || ''
        }
    };
}

// Set Proxmox configuration in form
function setProviderConfig(config) {
    if (!config) return;

    if (document.getElementById('proxmoxHost')) document.getElementById('proxmoxHost').value = config.host || '';
    if (document.getElementById('proxmoxPort')) document.getElementById('proxmoxPort').value = config.port || 8006;
    if (document.getElementById('proxmoxNode')) document.getElementById('proxmoxNode').value = config.node || '';
    if (document.getElementById('proxmoxUser')) document.getElementById('proxmoxUser').value = config.user || '';
    if (document.getElementById('proxmoxPassword')) document.getElementById('proxmoxPassword').value = config.password || '';
    if (document.getElementById('proxmoxVerifySSL')) document.getElementById('proxmoxVerifySSL').checked = config.verify_ssl || false;
    if (document.getElementById('proxmoxStorage')) document.getElementById('proxmoxStorage').value = config.storage || '';
    if (document.getElementById('proxmoxIsoStorage')) document.getElementById('proxmoxIsoStorage').value = config.iso_storage || 'local';
    if (document.getElementById('proxmoxBridge')) document.getElementById('proxmoxBridge').value = config.bridge || '';

    // Set VirtIO ISO if available
    if (document.getElementById('isoVirtio')) document.getElementById('isoVirtio').value = config.virtio_iso || '';

    // Set Windows ISOs if available
    if (config.windows_isos) {
        if (document.getElementById('isoWindows10')) document.getElementById('isoWindows10').value = config.windows_isos['windows-10'] || '';
        if (document.getElementById('isoWindows11')) document.getElementById('isoWindows11').value = config.windows_isos['windows-11'] || '';
        if (document.getElementById('isoWindowsServer2022')) document.getElementById('isoWindowsServer2022').value = config.windows_isos['windows-server-2022'] || '';
        if (document.getElementById('isoWindowsServer2025')) document.getElementById('isoWindowsServer2025').value = config.windows_isos['windows-server-2025'] || '';
    }
}

// Get network configuration
function getNetworkConfig() {
    const useStaticIps = document.getElementById('useStaticIps')?.checked || false;

    // If not using static IPs, return DHCP config
    if (!useStaticIps) {
        return { use_dhcp: true };
    }

    const config = {
        use_dhcp: false,
        subnet: document.getElementById('networkSubnet')?.value || '',
        gateway: document.getElementById('networkGateway')?.value || '',
        dns: document.getElementById('networkDns')?.value || '8.8.8.8',
        ip_assignments: {}
    };

    // Get GitLab IP
    const gitlabIp = document.getElementById('ip-gitlab')?.value?.trim();
    if (gitlabIp) {
        config.ip_assignments['gitlab'] = gitlabIp;
    }

    // Collect all runner IP assignments
    document.querySelectorAll('input[name="runners"]:checked').forEach(checkbox => {
        const runner = checkbox.value;
        const ipInput = document.getElementById(`ip-${runner}`);
        const ip = ipInput?.value?.trim();
        if (ip) {
            config.ip_assignments[runner] = ip;
        }
    });

    return config;
}

// Set network configuration
function setNetworkConfig(config) {
    if (!config) return;

    // Set the static IPs checkbox (use_dhcp: false means static IPs are enabled)
    const useStaticIps = document.getElementById('useStaticIps');
    if (useStaticIps) {
        useStaticIps.checked = !config.use_dhcp;
        toggleStaticIpConfig(); // Show/hide the static IP config section
    }

    // Set network values
    if (document.getElementById('networkSubnet')) document.getElementById('networkSubnet').value = config.subnet || '';
    if (document.getElementById('networkGateway')) document.getElementById('networkGateway').value = config.gateway || '';
    if (document.getElementById('networkDns')) document.getElementById('networkDns').value = config.dns || '';

    // Set IP assignments
    if (config.ip_assignments) {
        Object.entries(config.ip_assignments).forEach(([hostId, ip]) => {
            const input = document.getElementById(`ip-${hostId}`);
            if (input) {
                input.value = ip || '';
            }
        });
    }
}

// Test Proxmox connection
function testProxmoxConnection() {
    const config = getProviderConfig();

    if (!config.host || !config.user || !config.password) {
        showStatus('error', 'Please fill in host, username, and password');
        return;
    }

    showStatus('info', 'Testing Proxmox connection...');

    fetch('/api/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: 'proxmox', config: config })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showStatus('success', `Connected to Proxmox! Node: ${data.node_info || config.node}`);

            // Set node capacity if available
            if (data.capacity) {
                setNodeCapacity(data.capacity, data.node_info || config.node);
            }

            // Show ISO selection section and auto-refresh ISOs
            showWindowsIsoSection();
            refreshProxmoxIsos();
        } else {
            showStatus('error', `Connection failed: ${data.error}`);
            hideNodeCapacity();
            hideWindowsIsoSection();
        }
    })
    .catch(error => {
        showStatus('error', 'Connection test failed: ' + error.message);
        hideNodeCapacity();
        hideWindowsIsoSection();
    });
}

// ============================================================================
// Windows ISO Selection Functions
// ============================================================================

// Store available ISOs
let availableIsos = [];

// Show Windows ISO section
function showWindowsIsoSection() {
    const section = document.getElementById('windowsIsoSection');
    if (section) {
        section.style.display = 'block';
    }
}

// Hide Windows ISO section
function hideWindowsIsoSection() {
    const section = document.getElementById('windowsIsoSection');
    if (section) {
        section.style.display = 'none';
    }
}

// Refresh ISOs from Proxmox
function refreshProxmoxIsos() {
    const config = getProviderConfig();

    if (!config.host || !config.user || !config.password) {
        showStatus('error', 'Please fill in Proxmox connection details first');
        return;
    }

    showStatus('info', 'Loading ISOs from Proxmox storage...');

    // Use iso_storage for fetching ISOs
    const fetchConfig = {
        ...config,
        storage: config.iso_storage || 'local'
    };

    fetch('/api/proxmox/isos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fetchConfig)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            availableIsos = data.isos;
            updateAllIsoDropdowns(data.isos);

            if (data.isos.length === 0) {
                const isoStorage = config.iso_storage || 'local';
                showStatus('warning', `No ISOs found in "${isoStorage}" storage. Upload Windows ISOs to your Proxmox server.`);
            } else {
                showStatus('success', `Loaded ${data.isos.length} ISOs from storage`);
            }
        } else {
            showStatus('error', `Failed to load ISOs: ${data.error}`);
        }
    })
    .catch(error => {
        showStatus('error', `Failed to load ISOs: ${error.message}`);
    });
}

// Update all Windows ISO dropdowns and VirtIO dropdown
function updateAllIsoDropdowns(isos) {
    // Windows ISO dropdowns
    const windowsDropdowns = [
        'isoWindows10',
        'isoWindows11',
        'isoWindowsServer2022',
        'isoWindowsServer2025'
    ];

    windowsDropdowns.forEach(dropdownId => {
        const select = document.getElementById(dropdownId);
        if (!select) return;

        // Save current selection
        const currentValue = select.value;

        // Clear and rebuild
        select.innerHTML = '<option value="">-- Select ISO --</option>';

        // Add all ISOs as options
        isos.forEach(iso => {
            const option = document.createElement('option');
            option.value = iso.volid;
            option.textContent = `${iso.filename} (${iso.size_display})`;
            select.appendChild(option);
        });

        // Restore selection if it still exists
        if (currentValue) {
            select.value = currentValue;
        }
    });

    // Update VirtIO dropdown separately - look for virtio ISOs
    const virtioSelect = document.getElementById('isoVirtio');
    if (virtioSelect) {
        const currentVirtioValue = virtioSelect.value;
        virtioSelect.innerHTML = '<option value="">-- Select VirtIO ISO --</option>';

        isos.forEach(iso => {
            const option = document.createElement('option');
            option.value = iso.volid;
            // Highlight VirtIO ISOs
            const isVirtio = iso.filename.toLowerCase().includes('virtio');
            option.textContent = `${iso.filename} (${iso.size_display})${isVirtio ? ' [VirtIO]' : ''}`;
            if (isVirtio) {
                option.style.fontWeight = 'bold';
            }
            virtioSelect.appendChild(option);
        });

        // Restore selection if it still exists
        if (currentVirtioValue) {
            virtioSelect.value = currentVirtioValue;
        }
    }
}


// Get selected Windows ISO
function getSelectedWindowsIso() {
    const select = document.getElementById('windowsIsoSelect');
    return select ? select.value : '';
}

// ============================================================================
// Credential Management Functions
// ============================================================================

// Current credential tab
let currentCredentialTab = 'manual';

// Load credentials on page load
document.addEventListener('DOMContentLoaded', function() {
    loadCredentials();
});

// Load saved credentials
function loadCredentials() {
    fetch('/api/credentials')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateCredentialDropdown(data.credentials);
                updateCredentialsList(data.credentials);
            }
        })
        .catch(error => {
            console.error('Failed to load credentials:', error);
        });
}

// Update the credential dropdown
function updateCredentialDropdown(credentials) {
    const select = document.getElementById('deployCredential');
    if (!select) return;

    // Clear and rebuild
    select.innerHTML = '<option value="">-- No credential (use defaults) --</option>';

    credentials.forEach(cred => {
        const option = document.createElement('option');
        option.value = cred.id;
        option.textContent = `${cred.name} (${cred.username})`;
        if (cred.is_default) {
            option.textContent += ' [Default]';
            option.selected = true;
        }
        select.appendChild(option);
    });
}

// Update the credentials list display
function updateCredentialsList(credentials) {
    const list = document.getElementById('credentialsList');
    if (!list) return;

    if (credentials.length === 0) {
        list.innerHTML = '<p class="empty-message">No credentials saved. Add one to inject into VMs/containers.</p>';
        return;
    }

    list.innerHTML = credentials.map(cred => `
        <div class="credential-item ${cred.is_default ? 'default' : ''}">
            <div class="credential-info">
                <strong>${cred.name}</strong>
                <span class="credential-user">@${cred.username}</span>
                ${cred.is_default ? '<span class="badge default-badge">Default</span>' : ''}
            </div>
            <div class="credential-auth">
                ${cred.has_password ? '<span class="auth-badge password">Password</span>' : ''}
                ${cred.has_ssh_key ? '<span class="auth-badge ssh">SSH Key</span>' : ''}
            </div>
            <div class="credential-actions">
                <button type="button" class="btn btn-tiny btn-secondary" onclick="editCredential(${cred.id})">Edit</button>
                ${!cred.is_default ? `<button type="button" class="btn btn-tiny btn-secondary" onclick="setDefaultCredential(${cred.id})">Set Default</button>` : ''}
                ${cred.has_ssh_key ? `<button type="button" class="btn btn-tiny btn-secondary" onclick="downloadCredentialKey(${cred.id})">Download Key</button>` : ''}
                <button type="button" class="btn btn-tiny btn-danger" onclick="deleteCredential(${cred.id})">Delete</button>
            </div>
        </div>
    `).join('');
}

// Toggle credential modal
function toggleCredentialModal() {
    const modal = document.getElementById('credentialModal');
    if (modal.style.display === 'none' || !modal.style.display) {
        modal.style.display = 'flex';
        resetCredentialForm();
        document.getElementById('credentialName').focus();
    } else {
        modal.style.display = 'none';
    }
}

// Reset credential form
function resetCredentialForm() {
    document.getElementById('credentialForm').reset();
    document.getElementById('credentialId').value = '';
    document.getElementById('credentialModalTitle').textContent = 'Add Credential';
    showCredentialTab('manual');
}

// Show credential tab
function showCredentialTab(tab) {
    currentCredentialTab = tab;

    // Update tab buttons
    document.querySelectorAll('.credential-tabs .tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`.credential-tabs .tab-btn[onclick="showCredentialTab('${tab}')"]`).classList.add('active');

    // Update tab content
    document.querySelectorAll('.credential-tab-content').forEach(content => {
        content.style.display = 'none';
    });
    document.getElementById('credentialTab' + tab.charAt(0).toUpperCase() + tab.slice(1)).style.display = 'block';
}

// Save credential
function saveCredential() {
    const name = document.getElementById('credentialName').value.trim();
    const username = document.getElementById('credentialUsername').value.trim();

    if (!name || !username) {
        alert('Please enter a name and username');
        return;
    }

    let saveData = {
        name: name,
        username: username,
        is_default: document.getElementById('credentialDefault').checked
    };

    // Handle based on current tab
    if (currentCredentialTab === 'manual') {
        saveData.password = document.getElementById('credentialPassword').value;
        saveData.ssh_public_key = document.getElementById('credentialPublicKey').value.trim();
        saveData.ssh_private_key = document.getElementById('credentialPrivateKey').value.trim();

        if (!saveData.password && !saveData.ssh_public_key) {
            alert('Please enter either a password or SSH public key');
            return;
        }

        saveCredentialData(saveData);
    } else if (currentCredentialTab === 'upload') {
        // Use FormData for file upload
        const formData = new FormData();
        formData.append('name', name);
        formData.append('username', username);
        formData.append('password', document.getElementById('credentialPasswordUpload').value);
        formData.append('is_default', document.getElementById('credentialDefault').checked);

        const publicKeyFile = document.getElementById('publicKeyFile').files[0];
        const privateKeyFile = document.getElementById('privateKeyFile').files[0];

        if (publicKeyFile) {
            formData.append('public_key', publicKeyFile);
        }
        if (privateKeyFile) {
            formData.append('private_key', privateKeyFile);
        }

        if (!document.getElementById('credentialPasswordUpload').value && !publicKeyFile) {
            alert('Please enter a password or upload a public key');
            return;
        }

        fetch('/api/credentials/upload-key', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                toggleCredentialModal();
                loadCredentials();
                showStatus('success', 'Credential saved successfully');
            } else {
                alert(data.error || 'Failed to save credential');
            }
        })
        .catch(error => {
            alert('Failed to save credential: ' + error.message);
        });
    } else if (currentCredentialTab === 'generate') {
        saveData.password = document.getElementById('credentialPasswordGenerate').value;
        saveData.key_type = document.getElementById('keyType').value;
        saveData.ssh_key_passphrase = document.getElementById('keyPassphrase').value;

        fetch('/api/credentials/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(saveData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                toggleCredentialModal();
                loadCredentials();
                showStatus('success', 'Credential with SSH keypair generated successfully');
            } else {
                alert(data.error || 'Failed to generate credential');
            }
        })
        .catch(error => {
            alert('Failed to generate credential: ' + error.message);
        });
    }
}

// Save credential data (for manual entry)
function saveCredentialData(data) {
    const credentialId = document.getElementById('credentialId')?.value;
    const isEditing = credentialId && credentialId !== '';
    const url = isEditing ? `/api/credentials/${credentialId}` : '/api/credentials';
    const method = isEditing ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            toggleCredentialModal();
            loadCredentials();
            showStatus('success', isEditing ? 'Credential updated successfully' : 'Credential saved successfully');
        } else {
            alert(result.error || 'Failed to save credential');
        }
    })
    .catch(error => {
        alert('Failed to save credential: ' + error.message);
    });
}

// Edit credential
function editCredential(credentialId) {
    // Fetch the credential data
    fetch(`/api/credentials/${credentialId}?include_secrets=true`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.credential) {
                const cred = data.credential;

                // Open modal
                const modal = document.getElementById('credentialModal');
                modal.style.display = 'flex';

                // Set modal title
                document.getElementById('credentialModalTitle').textContent = 'Edit Credential';

                // Populate form fields
                document.getElementById('credentialId').value = cred.id;
                document.getElementById('credentialName').value = cred.name || '';
                document.getElementById('credentialUsername').value = cred.username || '';
                document.getElementById('credentialPassword').value = cred.password || '';
                document.getElementById('credentialPublicKey').value = cred.ssh_public_key || '';
                document.getElementById('credentialPrivateKey').value = cred.ssh_private_key || '';
                document.getElementById('credentialDefault').checked = cred.is_default || false;

                // Show manual tab for editing
                showCredentialTab('manual');
            } else {
                showStatus('error', data.error || 'Failed to load credential for editing');
            }
        })
        .catch(error => {
            showStatus('error', 'Failed to load credential: ' + error.message);
        });
}

// Delete credential
function deleteCredential(credentialId) {
    if (!confirm('Are you sure you want to delete this credential?')) {
        return;
    }

    fetch(`/api/credentials/${credentialId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadCredentials();
            showStatus('success', 'Credential deleted');
        } else {
            alert(data.error || 'Failed to delete credential');
        }
    })
    .catch(error => {
        alert('Failed to delete credential: ' + error.message);
    });
}

// Set default credential
function setDefaultCredential(credentialId) {
    fetch(`/api/credentials/${credentialId}/set-default`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadCredentials();
            showStatus('success', 'Default credential updated');
        } else {
            alert(data.error || 'Failed to set default credential');
        }
    })
    .catch(error => {
        alert('Failed to set default: ' + error.message);
    });
}

// Download credential private key
function downloadCredentialKey(credentialId) {
    window.location.href = `/api/credentials/${credentialId}/download-key`;
}

// ============================================================================
// Network/IP Configuration Functions
// ============================================================================

// Toggle static IP configuration section
function toggleStaticIpConfig() {
    const checkbox = document.getElementById('useStaticIps');
    const configSection = document.getElementById('staticIpConfig');

    if (checkbox && configSection) {
        configSection.style.display = checkbox.checked ? 'block' : 'none';
        if (checkbox.checked) {
            updateIpAssignments();
        }
    }
}

// Update IP assignments list based on selected runners
function updateIpAssignments() {
    const container = document.getElementById('ipAssignments');
    if (!container) return;

    // Start with GitLab server
    let html = `
        <div class="ip-assignment-row">
            <span class="ip-host-name">GitLab Server</span>
            <input type="text" id="ip-gitlab" placeholder="e.g., 192.168.1.10" class="ip-input">
        </div>
    `;

    // Add selected runners
    document.querySelectorAll('input[name="runners"]:checked').forEach(checkbox => {
        const runner = checkbox.value;
        const displayName = getRunnerDisplayName(runner);
        html += `
            <div class="ip-assignment-row">
                <span class="ip-host-name">${displayName} <span class="runner-type">(${runner})</span></span>
                <input type="text" id="ip-${runner}" placeholder="e.g., 192.168.1.x" class="ip-input">
            </div>
        `;
    });

    container.innerHTML = html;
}

// Get display name for runner
function getRunnerDisplayName(runner) {
    const names = {
        'windows-10': 'Windows 10 Runner',
        'windows-11': 'Windows 11 Runner',
        'windows-server-2022': 'Windows Server 2022',
        'windows-server-2025': 'Windows Server 2025',
        'debian': 'Debian Runner',
        'ubuntu': 'Ubuntu Runner',
        'arch': 'Arch Linux Runner',
        'rocky': 'Rocky Linux Runner',
        'macos': 'macOS Runner'
    };
    return names[runner] || runner;
}

// NOTE: getNetworkConfig() is defined earlier in this file (around line 760)

// Update IP assignments when runners change
document.addEventListener('DOMContentLoaded', function() {
    // Listen for runner checkbox changes to update IP list
    document.querySelectorAll('input[name="runners"]').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            if (document.getElementById('useStaticIps')?.checked) {
                updateIpAssignments();
            }
        });
    });
});

