FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY winxtract /app/winxtract
COPY config /app/config

RUN pip install --no-cache-dir .
RUN python -m playwright install --with-deps chromium

EXPOSE 8787

CMD ["python", "-m", "winxtract.cli", "ui", "--host", "0.0.0.0", "--port", "8787"]
