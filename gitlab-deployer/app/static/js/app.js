// Platform and OS version mapping
const platformVersions = {
    windows: ['Windows 10', 'Windows 11', 'Windows Server 2022', 'Windows Server 2025'],
    linux: ['Debian', 'Ubuntu', 'Arch Linux', 'Rocky Linux'],
    macos: ['macOS']
};

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    const platformSelect = document.getElementById('platform');
    const osVersionSelect = document.getElementById('osVersion');
    const deploymentForm = document.getElementById('deploymentForm');

    // Platform change handler
    platformSelect.addEventListener('change', function() {
        const platform = this.value;
        osVersionSelect.innerHTML = '<option value="">Select OS Version</option>';

        if (platform && platformVersions[platform]) {
            platformVersions[platform].forEach(version => {
                const option = document.createElement('option');
                option.value = version;
                option.textContent = version;
                osVersionSelect.appendChild(option);
            });
            osVersionSelect.disabled = false;
        } else {
            osVersionSelect.disabled = true;
        }
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

        // Collect form data
        const deploymentData = {
            platform: document.getElementById('platform').value,
            os_version: document.getElementById('osVersion').value,
            domain: document.getElementById('domain').value,
            email: document.getElementById('email').value,
            admin_password: adminPassword,
            letsencrypt_enabled: document.getElementById('letsencrypt').checked
        };

        // Show loading status
        showStatus('info', 'Preparing deployment...');
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
                // Ask for confirmation before executing
                if (confirm('Configuration saved. Do you want to start the deployment now?')) {
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

// Execute the deployment
function executeDeployment(deploymentId) {
    showStatus('info', 'Starting GitLab deployment... This may take 15-30 minutes.');
    showSpinner();

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
    document.getElementById('osVersion').disabled = true;
    hideStatus();
}
