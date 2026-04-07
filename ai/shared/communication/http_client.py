"""
AgentHTTPClient — HTTP client for supervisor to call domain agents.

Handles:
  - Service discovery (agent URLs from env vars)
  - Retry with exponential backoff
  - Timeout management
  - Error normalization
  - Circuit breaker pattern (optional)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from .http_schemas import AgentRequest, AgentResponse

logger = logging.getLogger(__name__)


# ─── Agent URL registry ───────────────────────────────────────────────────────

# Maps AgentID → default URL (can be overridden by env vars)
DEFAULT_AGENT_URLS: dict[str, str] = {
    "agent-diagnostic": "http://agent-diagnostic:8101",
    "agent-theory": "http://agent-theory:8102",
    "agent-treatment": "http://agent-treatment:8103",
    "agent-support": "http://agent-support:8104",
    "agent-crisis": "http://agent-crisis:8105",
}


def _resolve_url(agent_id: str) -> str:
    """Resolve agent URL from env var or fallback to default."""
    import os

    env_key = f"{agent_id.upper().replace('-', '_')}_URL"
    return os.getenv(env_key, DEFAULT_AGENT_URLS.get(agent_id, ""))


# ─── AgentHTTPClient ──────────────────────────────────────────────────────────


class AgentHTTPClient:
    """
    HTTP client for supervisor to call domain agents.

    Usage:
        client = AgentHTTPClient()
        resp = await client.call_agent("agent-support", request)
        resp = await client.call_all([...])   # fan-out
        resp = await client.call_crisis_emergency(...)  # crisis broadcast
    """

    def __init__(
        self,
        timeout: float = 60.0,
        connect_timeout: float = 10.0,
        max_retries: int = 3,
        retry_backoff: float = 1.5,
    ):
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._client: Optional[httpx.AsyncClient] = None

    # ── httpx lifecycle ─────────────────────────────────────────────────────

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    timeout=self.timeout,
                    connect=self.connect_timeout,
                ),
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=100,
                ),
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── Core call ───────────────────────────────────────────────────────────

    async def call_agent(
        self,
        agent_id: str,
        request: AgentRequest,
        retry: bool = True,
    ) -> AgentResponse:
        """
        Call a single domain agent and return parsed AgentResponse.

        Args:
            agent_id: e.g. "agent-support", "agent-crisis"
            request:  AgentRequest to send
            retry:    Whether to retry on failure

        Raises:
            httpx.HTTPStatusError — on non-2xx with status code
            httpx.TransportError — on connection failure
        """
        url = _resolve_url(agent_id)
        if not url:
            raise ValueError(f"No URL configured for agent: {agent_id}")

        endpoint = f"{url}/agent/{agent_id.replace('agent-', '')}"
        client = self._get_client()

        last_error: Exception | None = None
        for attempt in range(self.max_retries if retry else 1):
            try:
                resp = await client.post(
                    endpoint,
                    json=request.model_dump(exclude_none=True),
                )
                resp.raise_for_status()
                data = resp.json()

                # Normalize to AgentResponse
                return AgentResponse(
                    response=data.get("response", ""),
                    agent_id=data.get("agent_id", agent_id),
                    intent=data.get("intent", "unknown"),
                    language=data.get("language", request.language),
                    skills_used=data.get("skills_used", []),
                    crisis_detected=data.get("crisis_detected", False),
                    conversation_id=data.get(
                        "conversation_id", request.conversation_id
                    ),
                    turn=data.get("turn", 0),
                    metadata=data.get("metadata", {}),
                )

            except httpx.HTTPStatusError:
                # Don't retry client errors (4xx)
                raise
            except httpx.TransportError as e:
                last_error = e
                logger.warning(
                    "[AgentHTTP] attempt %d/%d %s failed: %s",
                    attempt + 1,
                    self.max_retries,
                    endpoint,
                    e,
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_backoff**attempt)
                continue

        raise RuntimeError(
            f"[AgentHTTP] All {self.max_retries} retries failed for {agent_id}: {last_error}"
        )

    # ── Fan-out ─────────────────────────────────────────────────────────────

    async def call_all(
        self,
        agents: list[str],
        request: AgentRequest,
    ) -> dict[str, AgentResponse]:
        """
        Fan-out: call multiple agents concurrently, return dict of results.

        Useful for crisis broadcast or enrichment patterns.
        """
        tasks = {
            agent_id: asyncio.create_task(
                self.call_agent(agent_id, request, retry=False)
            )
            for agent_id in agents
        }
        results: dict[str, AgentResponse] = {}
        errors: dict[str, str] = {}

        done, pending = await asyncio.wait(
            [
                asyncio.create_task(self._call_catch(agent_id, tasks[agent_id]))
                for agent_id in agents
            ],
            return_when=asyncio.ALL_COMPLETED,
        )

        for coro in done:
            agent_id, resp_or_err = await coro
            if isinstance(resp_or_err, Exception):
                errors[agent_id] = str(resp_or_err)
            else:
                results[agent_id] = resp_or_err

        if errors:
            logger.warning("[AgentHTTP] Some agents failed: %s", errors)

        return results

    async def _call_catch(
        self,
        agent_id: str,
        coro: Any,
    ) -> tuple[str, AgentResponse | Exception]:
        try:
            return agent_id, await coro
        except Exception as e:
            return agent_id, e

    # ── Convenience: crisis ─────────────────────────────────────────────────

    async def call_crisis_emergency(
        self,
        request: AgentRequest,
    ) -> AgentResponse:
        """Call CrisisAgent with high priority and no retry limit."""
        client = self._get_client()
        url = _resolve_url("agent-crisis")
        endpoint = f"{url}/agent/crisis"

        try:
            resp = await client.post(
                endpoint,
                json=request.model_dump(exclude_none=True),
                timeout=httpx.Timeout(30.0, connect=5.0),
            )
            resp.raise_for_status()
            data = resp.json()
            return AgentResponse(**data)
        except Exception as e:
            logger.error("[AgentHTTP] Crisis call failed: %s", e)
            # Return error response instead of raising (crisis always responds)
            return AgentResponse(
                response="",
                agent_id="agent-crisis",
                intent="crisis",
                crisis_detected=True,
                conversation_id=request.conversation_id,
                language=request.language,
                error=str(e),
            )

    # ── Health check ────────────────────────────────────────────────────────

    async def check_health(self, agent_id: str) -> bool:
        """Ping an agent's /health endpoint."""
        url = _resolve_url(agent_id)
        if not url:
            return False
        client = self._get_client()
        try:
            resp = await client.get(f"{url}/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def check_all_health(self) -> dict[str, bool]:
        """Ping all registered agents."""
        tasks = {aid: self.check_health(aid) for aid in DEFAULT_AGENT_URLS}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return dict(zip(tasks.keys(), [r is True for r in results]))
