FROM python:3.12-slim

WORKDIR /app

# System dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY workers/pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Copy application
COPY workers/ .

CMD ["celery", "-A", "app.celery_app", "worker", "--loglevel=info"]
