// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    const deploymentForm = document.getElementById('deploymentForm');

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
}

// Deselect all runners
function deselectAllRunners() {
    document.querySelectorAll('input[name="runners"]').forEach(checkbox => {
        checkbox.checked = false;
    });
}
