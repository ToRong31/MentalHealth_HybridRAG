# syntax=docker/dockerfile:1.6
# Supervisor Agent — multi-stage build with uv

FROM python:3.11-slim AS builder
WORKDIR /build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY ai/agents/supervisor/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# ── runtime ────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash appuser

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY ai/ ./ai/

EXPOSE 8001
USER appuser

CMD ["uvicorn", "ai.agents.supervisor.main:app", "--host", "0.0.0.0", "--port", "8001"]
