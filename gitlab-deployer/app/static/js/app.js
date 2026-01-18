// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    const deploymentForm = document.getElementById('deploymentForm');

    // Load saved configurations on page load
    loadSavedConfigs();

    // Update runner count on checkbox change
    document.querySelectorAll('input[name="runners"]').forEach(checkbox => {
        checkbox.addEventListener('change', updateSelectedCount);
    });

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

        // Collect form data
        const deploymentData = {
            domain: document.getElementById('domain').value,
            email: document.getElementById('email').value,
            admin_password: adminPassword,
            letsencrypt_enabled: document.getElementById('letsencrypt').checked,
            runners: selectedRunners
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
}

// Deselect all runners
function deselectAllRunners() {
    document.querySelectorAll('input[name="runners"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    updateSelectedCount();
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
        runners: selectedRunners
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
