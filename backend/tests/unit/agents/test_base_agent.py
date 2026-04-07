"""
Unit tests for BaseAgent — initialization, tools, skills, and interrupt handling.
"""
from __future__ import annotations

import asyncio
import pytest

# Adjust import path for project root
import sys
from pathlib import Path

# Ensure ai/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "ai"))

from ai.shared.agent_based.base_agent import BaseAgent
from ai.shared.agent_based.state import GlobalState
from ai.shared.agent_based.constants import AgentID, AgentConfig


class DummyAgent(BaseAgent):
    """Concrete agent for testing BaseAgent."""

    def __init__(self, agent_id: str = "test-agent", **kwargs):
        super().__init__(agent_id=agent_id, **kwargs)
        self._run_count = 0

    def _register_tools(self) -> dict:
        return {
            "test_tool": {
                "description": "A test tool",
                "parameters": {"type": "object", "properties": {}},
            }
        }

    def _register_skills(self) -> dict:
        return {
            "TestSkill": DummySkill(),
        }

    async def run(self, input: dict, gs: GlobalState) -> dict:
        self._run_count += 1
        return {"response": f"ran {self._run_count} times", "agent_id": self.agent_id}


class DummySkill:
    """Dummy skill for testing."""

    async def execute(self, **kwargs):
        return {"result": "ok"}


class TestBaseAgentInit:
    """Test BaseAgent.__init__()."""

    def test_sets_agent_id(self):
        agent = DummyAgent(agent_id="my-agent")
        assert agent.agent_id == "my-agent"

    def test_sets_memory_service(self):
        mem = object()
        agent = DummyAgent(memory_service=mem)
        assert agent.memory_service is mem

    def test_sets_llm(self):
        llm = object()
        agent = DummyAgent(llm=llm)
        assert agent.llm is llm

    def test_sets_config_default_empty(self):
        agent = DummyAgent()
        assert agent.config == {}

    def test_sets_config_custom(self):
        agent = DummyAgent(config={"key": "value"})
        assert agent.config == {"key": "value"}

    def test_circuit_breakers_created_per_tool(self):
        agent = DummyAgent(
            agent_id="cb-test",
            config={"circuit_breaker_threshold": 3},
        )
        assert "test_tool" in agent._circuit_breakers
        cb = agent._circuit_breakers["test_tool"]
        assert cb.threshold == 3

    def test_interrupted_flag_initialized(self):
        agent = DummyAgent()
        assert agent._interrupted is not None
        assert isinstance(agent._interrupted, asyncio.Event)
        # Not set initially
        assert not agent._interrupted.is_set()


class TestBaseAgentRegister:
    """Test _register_tools and _register_skills."""

    def test_tools_registered(self):
        agent = DummyAgent()
        assert "test_tool" in agent._tools

    def test_skills_registered(self):
        agent = DummyAgent()
        assert "TestSkill" in agent._skills


class TestBaseAgentInterrupt:
    """Test interrupt signal handling."""

    def test_interrupt_sets_event(self):
        agent = DummyAgent()
        agent.interrupt("test reason")
        assert agent._interrupted.is_set()
        assert agent._interrupt_reason == "test reason"

    def test_clear_interrupt_resets_event(self):
        agent = DummyAgent()
        agent.interrupt("reason")
        agent.clear_interrupt()
        assert not agent._interrupted.is_set()
        assert agent._interrupt_reason is None

    def test_is_interrupted_returns_state(self):
        agent = DummyAgent()
        assert not agent.is_interrupted()
        agent.interrupt("reason")
        assert agent.is_interrupted()


class TestBaseAgentRun:
    """Test the run() method."""

    @pytest.mark.asyncio
    async def test_run_calls_subclass_logic(self):
        agent = DummyAgent(agent_id="run-test")
        gs: GlobalState = {}
        result = await agent.run({"input": "test"}, gs)
        assert result["response"] == "ran 1 times"
        assert result["agent_id"] == "run-test"
        assert agent._run_count == 1

    @pytest.mark.asyncio
    async def test_run_accepts_gs(self):
        agent = DummyAgent(agent_id="gs-test")
        gs: GlobalState = {"custom_key": "custom_value"}
        await agent.run({}, gs)
        # gs is passed through unchanged (BaseAgent doesn't modify it)


class TestAgentConfig:
    """Test AgentConfig defaults."""

    def test_defaults(self):
        cfg = AgentConfig()
        assert cfg.max_retries == 3
        assert cfg.timeout_seconds == 60
        assert cfg.circuit_breaker_threshold == 5
        assert cfg.circuit_breaker_timeout == 30.0
