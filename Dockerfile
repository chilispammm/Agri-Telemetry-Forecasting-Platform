# Agri Telemetry & Forecasting Platform — Production Runtime Image
FROM python:3.11-slim

# System metadata
LABEL maintainer="Antigravity Team"
LABEL description="Agri Telemetry & Forecasting Platform Operational Container"
LABEL version="1.0.0"

# Set deterministic Python runtime environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    AGRI_ENV=production

# Install essential system utilities and security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user and group
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -s /bin/bash appuser

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source tree and configuration
COPY agri_telemetry/ /app/agri_telemetry/
COPY config/ /app/config/
COPY data/ /app/data/
COPY tests/ /app/tests/
COPY generate_html.py /app/

# Create persistent storage directories and assign permissions
RUN mkdir -p /app/data /app/runs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Container Healthcheck verifying CLI and metrics subsystem
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -m agri_telemetry.cli show-metrics || exit 1

# Standard entrypoint
ENTRYPOINT ["python", "-m", "agri_telemetry.cli"]

# Default command runs the operational pipeline
CMD ["run-operational", "--file", "data/uscrn/CRNH0203-2023-NE_Lincoln_11_SW.txt"]
