# ai/Dockerfile — Build all agent microservices as Docker images
#
# Build:
#   docker build -f ai/Dockerfile -t mental-health-agents .
#
# Run a specific agent:
#   docker run --rm -p 8001:8001 \
#     -e AGENT_PORT=8001 \
#     mental-health-agents \
#     python -m uvicorn ai.agents.supervisor.main:app --host 0.0.0.0 --port 8001
#
# Environment variables required:
#   AGENT_PORT        — port for this agent (default: 8001)
#   REDIS_URL         — Redis URL (default: redis://redis:6379/0)
#   NEO4J_URI         — Neo4j bolt URL
#   NEO4J_PASSWORD    — Neo4j password
#   NVIDIA_API_KEY    — NVIDIA API key for LLM
#   OPENAI_BASE_URL  — OpenAI-compatible base URL
#   OPENAI_MODEL     — OpenAI model name
#   GEMINI_API_KEY   — Gemini API key (fallback)
#
FROM python:3.11-slim

WORKDIR /app

# Install system deps for building python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies
COPY backend/requirements.txt /tmp/requirements.txt
RUN uv pip install --system --no-cache -r /tmp/requirements.txt

# Copy agent code
COPY ai/ /app/ai/

# Ensure ai is importable (add parent dir to PYTHONPATH)
ENV PYTHONPATH=/app:${PYTHONPATH:-}
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default agent port (can be overridden at runtime)
ENV AGENT_PORT=8001

EXPOSE 8001 8101 8102 8103 8104 8105

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${AGENT_PORT:-8001}/health || exit 1

# Default: run SupervisorAgent on port 8001
# Override the CMD in docker-compose or docker run to start a different agent
CMD ["python", "-m", "uvicorn", "ai.agents.supervisor.main:app", "--host", "0.0.0.0", "--port", "8001"]
