# syntax=docker/dockerfile:1.6

############################
# builder: compile + install
############################
FROM python:3.11-slim AS builder
WORKDIR /build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --retries 20 --timeout=180 -r requirements.txt


############################
# runtime: minimal
############################
FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Security: non-root user
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy app source
COPY src/ ./src/
COPY ai/ ./ai/
COPY pyproject.toml uv.lock .env.example ./

# Install just runtime deps
RUN pip install --no-cache-dir -r requirements.txt \
    --target=/usr/local/lib/python3.11/site-packages \
    2>/dev/null || true

# Expose port
EXPOSE 8000

# Run as non-root
USER appuser

# Run uvicorn
CMD ["uvicorn", "backend.src.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]


############################
# dev: interactive shell
############################
FROM runtime AS dev
USER root
USER appuser
ENV DEBUG=1
