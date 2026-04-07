#!/usr/bin/env python3
"""
run_agents.py — Start all agent microservices locally (no Docker).

Usage:
    python run_agents.py          # Start all agents
    python run_agents.py --help   # Show help

Requirements:
    - Redis running on localhost:6379
    - PostgreSQL running on localhost:5432
    - Milvus running on localhost:19530
    - Neo4j running on localhost:7687
    - NVIDIA_API_KEY or GEMINI_API_KEY set for LLM calls

Agents started:
    SupervisorAgent  → http://localhost:8001
    DiagnosticAgent  → http://localhost:8101
    TheoryAgent      → http://localhost:8102
    TreatmentAgent   → http://localhost:8103
    SupportAgent     → http://localhost:8104
    CrisisAgent      → http://localhost:8105
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing import Process, Queue
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(process)d] %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Agent definitions ─────────────────────────────────────────────────────────

AGENTS: list[dict[str, Any]] = [
    {
        "name": "SupervisorAgent",
        "port": 8001,
        "module": "ai.agents.supervisor.main",
        "app": "app",
        "env_prefix": "SUPERVISOR",
    },
    {
        "name": "DiagnosticAgent",
        "port": 8101,
        "module": "ai.agents.diagnostic.main",
        "app": "app",
        "env_prefix": "DIAGNOSTIC",
    },
    {
        "name": "TheoryAgent",
        "port": 8102,
        "module": "ai.agents.theory.main",
        "app": "app",
        "env_prefix": "THEORY",
    },
    {
        "name": "TreatmentAgent",
        "port": 8103,
        "module": "ai.agents.treatment.main",
        "app": "app",
        "env_prefix": "TREATMENT",
    },
    {
        "name": "SupportAgent",
        "port": 8104,
        "module": "ai.agents.support.main",
        "app": "app",
        "env_prefix": "SUPPORT",
    },
    {
        "name": "CrisisAgent",
        "port": 8105,
        "module": "ai.agents.crisis.main",
        "app": "app",
        "env_prefix": "CRISIS",
    },
]

# ─── Process management ───────────────────────────────────────────────────────

_processes: list[Process] = []


def _run_uvicorn(agent_def: dict[str, Any]) -> None:
    """Run a single agent in this process (called by multiprocessing)."""
    import uvicorn

    agent_name = agent_def["name"]
    port = agent_def["port"]
    module = agent_def["module"]
    app_attr = agent_def["app"]

    # Set agent-specific port env var
    os.environ["AGENT_PORT"] = str(port)

    log_cfg = uvicorn.config.LOGGING_CONFIG
    log_cfg["formatters"]["default"]["fmt"] = (
        f"%(asctime)s [%(process)d] [%(name)s] %(levelprefix)s %(message)s"
    )

    logger.info(f"[{agent_name}] Starting on port {port}...")
    uvicorn.run(
        f"{module}:{app_attr}",
        host="0.0.0.0",
        port=port,
        log_level="info",
        log_config=log_cfg,
    )


def start_all_agents() -> list[Process]:
    """Start all agent processes."""
    processes = []

    for agent_def in AGENTS:
        p = Process(
            target=_run_uvicorn,
            args=(agent_def,),
            name=agent_def["name"],
            daemon=False,
        )
        p.start()
        processes.append(p)
        logger.info(
            f"[{agent_def['name']}] PID={p.pid} port={agent_def['port']} started"
        )
        # Small delay to avoid port conflicts on startup
        import time
        time.sleep(0.5)

    return processes


def stop_all_agents(processes: list[Process]) -> None:
    """Stop all agent processes gracefully."""
    logger.info("Stopping all agents...")

    # First: SIGTERM (graceful)
    for p in processes:
        if p.is_alive():
            logger.info(f"[{p.name}] Sending SIGTERM...")
            p.terminate()

    # Wait for graceful shutdown
    alive = [p for p in processes if p.is_alive()]
    for p in alive:
        p.join(timeout=5.0)

    # Force kill if still alive
    for p in processes:
        if p.is_alive():
            logger.warning(f"[{p.name}] Force killing...")
            p.kill()
            p.join(timeout=2.0)

    logger.info("All agents stopped.")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Start all MentalHealth agent microservices")
    parser.add_argument(
        "--agents",
        nargs="+",
        choices=[a["name"] for a in AGENTS] + ["all"],
        default=["all"],
        help="Which agents to start (default: all)",
    )
    args = parser.parse_args()

    agents_to_start = AGENTS if "all" in args.agents else [
        a for a in AGENTS if a["name"] in args.agents
    ]

    logger.info(f"Starting {len(agents_to_start)} agent(s)...")
    processes = []

    try:
        for agent_def in agents_to_start:
            p = Process(
                target=_run_uvicorn,
                args=(agent_def,),
                name=agent_def["name"],
                daemon=False,
            )
            p.start()
            processes.append(p)
            import time
            time.sleep(0.5)

        logger.info(f"All {len(processes)} agents started.")
        logger.info("Press Ctrl+C to stop all agents.")

        # Wait for agents
        while True:
            alive = [p for p in processes if p.is_alive()]
            if len(alive) < len(processes):
                dead = [p for p in processes if not p.is_alive()]
                for p in dead:
                    logger.error(f"[{p.name}] Agent died with exit code {p.exitcode}")
                logger.error("Some agents died. Stopping all...")
                break
            import time
            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("Interrupt received.")
    finally:
        stop_all_agents(processes)


if __name__ == "__main__":
    main()
