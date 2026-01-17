external_url '${external_url}'

# Let's Encrypt configuration
%{ if enable_letsencrypt }
letsencrypt['enable'] = true
letsencrypt['contact_emails'] = ['${letsencrypt_email}']
letsencrypt['auto_renew'] = true
letsencrypt['auto_renew_hour'] = 0
letsencrypt['auto_renew_minute'] = 30
letsencrypt['auto_renew_day_of_month'] = "*/7"
%{ else }
letsencrypt['enable'] = false
%{ endif }

# GitLab configuration
gitlab_rails['gitlab_shell_ssh_port'] = 2222
gitlab_rails['time_zone'] = 'UTC'

# Email configuration (optional - can be configured later)
# gitlab_rails['smtp_enable'] = true
# gitlab_rails['smtp_address'] = "smtp.example.com"
# gitlab_rails['smtp_port'] = 587
# gitlab_rails['smtp_user_name'] = "gitlab@example.com"
# gitlab_rails['smtp_password'] = "password"
# gitlab_rails['smtp_domain'] = "example.com"
# gitlab_rails['smtp_authentication'] = "login"
# gitlab_rails['smtp_enable_starttls_auto'] = true
# gitlab_rails['smtp_tls'] = false

# Performance tuning
unicorn['worker_processes'] = 2
postgresql['shared_buffers'] = "256MB"
