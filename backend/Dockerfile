# syntax=docker/dockerfile:1.6

############################
# builder: compile deps
############################
FROM python:3.11-slim AS builder

WORKDIR /build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Build wheels (để runtime không cần gcc/g++)
RUN pip install --upgrade pip setuptools wheel \
 && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


############################
# runtime: minimal
############################
FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Runtime-only packages (curl dùng cho healthcheck, libpq5 cho psycopg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
 && rm -rf /wheels

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

WORKDIR /app

# Install development tools
RUN pip install --no-cache-dir \
    ipython \
    ipdb \
    pytest \
    pytest-asyncio \
    black \
    flake8 \
    mypy

# Install LangGraph CLI for visualization
RUN pip install --no-cache-dir langgraph-cli

# Development mode - no CMD, will use docker-compose command
CMD ["bash"]
