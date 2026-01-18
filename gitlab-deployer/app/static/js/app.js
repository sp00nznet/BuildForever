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

        // Get selected provider
        const provider = document.getElementById('provider')?.value || 'docker';

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
            // Infrastructure provider
            provider: provider,
            provider_config: getProviderConfig(provider)
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
    let totalCpu = 0;
    let totalMemory = 0;
    let totalStorage = 0;

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

                // Set runner checkboxes
                document.querySelectorAll('input[name="runners"]').forEach(checkbox => {
                    checkbox.checked = config.runners && config.runners.includes(checkbox.value);
                });

                updateSelectedCount();
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

    const config = {
        name: name,
        domain: domain,
        email: email,
        letsencrypt_enabled: document.getElementById('letsencrypt').checked,
        runners: selectedRunners,
        // Traefik settings
        traefik_enabled: document.getElementById('traefik')?.checked || false,
        base_domain: document.getElementById('baseDomain')?.value || '',
        traefik_dashboard: document.getElementById('traefikDashboard')?.checked || false
    };

    // Include password if checkbox is checked
    if (document.getElementById('savePassword').checked) {
        config.admin_password = document.getElementById('adminPassword').value;
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

// Get provider-specific configuration
function getProviderConfig(provider) {
    switch (provider) {
        case 'proxmox':
            return {
                host: document.getElementById('proxmoxHost')?.value || '',
                port: parseInt(document.getElementById('proxmoxPort')?.value) || 8006,
                node: document.getElementById('proxmoxNode')?.value || 'pve',
                user: document.getElementById('proxmoxUser')?.value || '',
                password: document.getElementById('proxmoxPassword')?.value || '',
                verify_ssl: document.getElementById('proxmoxVerifySSL')?.checked || false,
                storage: document.getElementById('proxmoxStorage')?.value || 'local-lvm',
                bridge: document.getElementById('proxmoxBridge')?.value || 'vmbr0'
            };
        case 'docker':
        default:
            return {};
    }
}

// Set provider configuration in form
function setProviderConfig(provider, config) {
    if (!config) return;

    switch (provider) {
        case 'proxmox':
            if (document.getElementById('proxmoxHost')) document.getElementById('proxmoxHost').value = config.host || '';
            if (document.getElementById('proxmoxPort')) document.getElementById('proxmoxPort').value = config.port || 8006;
            if (document.getElementById('proxmoxNode')) document.getElementById('proxmoxNode').value = config.node || '';
            if (document.getElementById('proxmoxUser')) document.getElementById('proxmoxUser').value = config.user || '';
            if (document.getElementById('proxmoxPassword')) document.getElementById('proxmoxPassword').value = config.password || '';
            if (document.getElementById('proxmoxVerifySSL')) document.getElementById('proxmoxVerifySSL').checked = config.verify_ssl || false;
            if (document.getElementById('proxmoxStorage')) document.getElementById('proxmoxStorage').value = config.storage || '';
            if (document.getElementById('proxmoxBridge')) document.getElementById('proxmoxBridge').value = config.bridge || '';
            break;
    }
}

// Test Proxmox connection
function testProxmoxConnection() {
    const config = getProviderConfig('proxmox');

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
        } else {
            showStatus('error', `Connection failed: ${data.error}`);
            hideNodeCapacity();
        }
    })
    .catch(error => {
        showStatus('error', 'Connection test failed: ' + error.message);
        hideNodeCapacity();
    });
}

