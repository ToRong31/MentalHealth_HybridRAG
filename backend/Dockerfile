# syntax=docker/dockerfile:1.6

############################
# builder: compile/install deps
############################
FROM python:3.11-slim AS builder
WORKDIR /build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install deps directly into /usr/local (NO wheels layer in final image)
RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir --retries 20 --timeout 180 -r requirements.txt


############################
# runtime: minimal
############################
FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

# ✅ bring installed packages + console scripts
COPY --from=builder /usr/local /usr/local

# app code
COPY . .
RUN mkdir -p /app/data /app/logs

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]


############################
# dev: development stage
############################
FROM runtime AS dev

RUN pip install --no-cache-dir \
    ipython ipdb pytest pytest-asyncio black flake8 mypy \
 && pip install --no-cache-dir langgraph-cli

CMD ["bash"]
