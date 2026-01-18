# BuildForever - GitLab CI/CD Build Farm Deployer
# Multi-stage Docker build for production deployment

FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Production stage
FROM python:3.11-slim

# Labels
LABEL maintainer="BuildForever Team"
LABEL description="GitLab CI/CD Build Farm Deployment Platform"
LABEL version="2.0"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=run.py
ENV FLASK_ENV=production

# Create non-root user for security
RUN groupadd -r buildforever && useradd -r -g buildforever buildforever

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder stage
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

# Install Python packages from wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY gitlab-deployer/ ./gitlab-deployer/
COPY ansible/ ./ansible/
COPY terraform/ ./terraform/
COPY scripts/ ./scripts/
COPY docs/ ./docs/

# Create necessary directories
RUN mkdir -p /app/config /app/logs /app/data && \
    chown -R buildforever:buildforever /app

# Copy and set permissions for startup script
COPY scripts/start.sh /app/start.sh
RUN chmod +x /app/start.sh /app/scripts/*.sh

# Switch to non-root user
USER buildforever

# Expose Flask port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Set working directory to gitlab-deployer
WORKDIR /app/gitlab-deployer

# Default command
CMD ["python", "run.py"]
