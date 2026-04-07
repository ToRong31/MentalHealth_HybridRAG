"""
Unit tests for AgentHTTPClient — call_agent, call_all, retry, timeout behavior.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "ai"))

from ai.shared.communication.http_client import (
    AgentHTTPClient,
    _resolve_url,
    DEFAULT_AGENT_URLS,
)
from ai.shared.communication.http_schemas import AgentRequest


class DummyRequest(AgentRequest):
    """Concrete request for testing."""


def make_req() -> AgentRequest:
    return AgentRequest(
        message=" Xin chào ",
        conversation_id="conv-123",
        user_id="user-1",
        language="vi",
    )


class TestResolveUrl:
    """Test URL resolution from env vars."""

    def test_returns_default_url(self):
        url = _resolve_url("agent-diagnostic")
        assert url == DEFAULT_AGENT_URLS["agent-diagnostic"]

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("AGENT_DIAGNOSTIC_URL", "http://custom:9999")
        url = _resolve_url("agent-diagnostic")
        assert url == "http://custom:9999"

    def test_unknown_agent_returns_empty(self):
        url = _resolve_url("agent-nonexistent")
        assert url == ""


class TestAgentHTTPClientInit:
    """Test AgentHTTPClient initialization."""

    def test_defaults(self):
        client = AgentHTTPClient()
        assert client.timeout == 60.0
        assert client.connect_timeout == 10.0
        assert client.max_retries == 3
        assert client.retry_backoff == 1.5

    def test_custom_overrides(self):
        client = AgentHTTPClient(timeout=30.0, max_retries=5)
        assert client.timeout == 30.0
        assert client.max_retries == 5


class TestCallAgent:
    """Test call_agent method."""

    @pytest.mark.asyncio
    async def test_raises_on_no_url(self):
        client = AgentHTTPClient()
        req = make_req()
        with pytest.raises(ValueError, match="No URL configured"):
            await client.call_agent("agent-nonexistent", req)

    @pytest.mark.asyncio
    async def test_success_returns_response(self):
        client = AgentHTTPClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": "Chào bạn",
            "agent_id": "agent-support",
            "intent": "support",
            "language": "vi",
            "skills_used": [],
            "crisis_detected": False,
            "conversation_id": "conv-123",
            "turn": 1,
            "metadata": {},
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.is_closed = False

        with patch.object(client, "_get_client", return_value=mock_client):
            req = make_req()
            resp = await client.call_agent("agent-support", req)

        assert resp.response == "Chào bạn"
        assert resp.agent_id == "agent-support"
        assert resp.intent == "support"

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self):
        client = AgentHTTPClient(max_retries=3)
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Not found"
        mock_resp.raise_for_status.side_effect = Exception("404")

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.is_closed = False

        with patch.object(client, "_get_client", return_value=mock_client):
            with pytest.raises(Exception):
                await client.call_agent("agent-support", make_req(), retry=True)
            # Should have only tried once (no retry on 4xx)
            assert mock_client.post.call_count == 1


class TestCallAll:
    """Test call_all fan-out method."""

    @pytest.mark.asyncio
    async def test_calls_all_agents(self):
        client = AgentHTTPClient()

        async def mock_call(agent_id, req, retry=True):
            from ai.shared.communication.http_schemas import AgentResponse
            return AgentResponse(
                response=f"response from {agent_id}",
                agent_id=agent_id,
                intent="support",
                language="vi",
                skills_used=[],
                crisis_detected=False,
                conversation_id=req.conversation_id,
            )

        with patch.object(client, "call_agent", side_effect=mock_call):
            req = make_req()
            agents = ["agent-support", "agent-theory"]
            results = await client.call_all(agents, req)

        assert "agent-support" in results
        assert "agent-theory" in results


class TestHealthCheck:
    """Test health check methods."""

    @pytest.mark.asyncio
    async def test_check_health_returns_true_on_200(self):
        client = AgentHTTPClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.is_closed = False

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.check_health("agent-support")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_health_returns_false_on_error(self):
        client = AgentHTTPClient()
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("connection refused")
        mock_client.is_closed = False

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.check_health("agent-support")

        assert result is False
