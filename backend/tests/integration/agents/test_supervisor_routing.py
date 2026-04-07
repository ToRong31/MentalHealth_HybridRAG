"""
Integration tests for SupervisorAgent routing — crisis gate, intent classification,
and domain agent dispatch.
"""

from __future__ import annotations

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "ai"))

from ai.shared.agent_based.constants import AgentID
from ai.shared.agent_based.state import GlobalState
from ai.agents.supervisor.supervisor_agent import SupervisorAgent
from ai.agents.supervisor.router import check_crisis_gate, make_routing_decision
from ai.agents.supervisor.tools.routing_tools import (
    route_to_agent,
    build_routing_context,
)


class TestCrisisGate:
    """Test crisis safety gate keyword detection."""

    def test_detects_vietnamese_crisis_keywords(self):
        has_crisis, matched = check_crisis_gate("Tôi muốn tự tử")
        assert has_crisis is True
        assert "tự tử" in matched

    def test_detects_english_crisis_keywords(self):
        has_crisis, matched = check_crisis_gate("I want to kill myself")
        assert has_crisis is True
        assert any(
            "suicide" in kw.lower() or "kill myself" in kw.lower() for kw in matched
        )

    def test_no_false_positive_on_normal_text(self):
        has_crisis, matched = check_crisis_gate("Tôi cảm thấy buồn vì công việc")
        assert has_crisis is False
        assert matched == []

    def test_case_insensitive(self):
        has_crisis, _ = check_crisis_gate("TỰ TỬ tôi muốn")
        assert has_crisis is True

    def test_partial_match_not_enough(self):
        # "tự" alone shouldn't trigger (needs "tử")
        has_crisis, matched = check_crisis_gate("Tôi tự hỏi")
        assert has_crisis is False


class TestRouteToAgent:
    """Test intent → agent mapping."""

    def test_diagnostic_routes_to_diagnostic_agent(self):
        result = route_to_agent("diagnostic", domain_agents={})
        assert result == AgentID.DIAGNOSTIC

    def test_theory_routes_to_theory_agent(self):
        result = route_to_agent("theory", domain_agents={})
        assert result == AgentID.THEORY

    def test_treatment_routes_to_treatment_agent(self):
        result = route_to_agent("treatment", domain_agents={})
        assert result == AgentID.TREATMENT

    def test_support_routes_to_support_agent(self):
        result = route_to_agent("support", domain_agents={})
        assert result == AgentID.SUPPORT

    def test_crisis_routes_to_crisis_agent(self):
        result = route_to_agent("crisis", domain_agents={})
        assert result == AgentID.CRISIS

    def test_unknown_intent_falls_back_to_support(self):
        result = route_to_agent("unknown-intent", domain_agents={})
        assert result == AgentID.SUPPORT

    def test_empty_domain_agents_dict_allows_routing(self):
        """Empty dict should NOT block routing (standalone microservice mode)."""
        # In standalone mode, domain_agents = {} but routing should still work
        result = route_to_agent("support", domain_agents={})
        assert result == AgentID.SUPPORT

    def test_non_empty_domain_agents_validates(self):
        """When domain_agents is populated, only registered agents are allowed."""
        agents = {AgentID.SUPPORT: object(), AgentID.DIAGNOSTIC: object()}
        result = route_to_agent("theory", domain_agents=agents)
        # theory not in agents → fallback to SUPPORT
        assert result == AgentID.SUPPORT


class TestBuildRoutingContext:
    """Test routing context builder."""

    def test_builds_full_context(self):
        ctx = build_routing_context(
            original_message="Tôi lo âu",
            translated_message="I am anxious",
            language="vi",
            preliminary_slots={"emotion": "lo âu"},
            intent="support",
            conv_id="conv-1",
        )
        assert ctx["original_message"] == "Tôi lo âu"
        assert ctx["translated_message"] == "I am anxious"
        assert ctx["language"] == "vi"
        assert ctx["preliminary_slots"] == {"emotion": "lo âu"}
        assert ctx["intent"] == "support"
        assert ctx["conv_id"] == "conv-1"


class TestMakeRoutingDecision:
    """Test full routing decision pipeline."""

    def test_crisis_decision(self):
        decision = make_routing_decision(
            message="Tôi muốn tự tử",
            language="vi",
        )
        assert decision["target_agent"] == AgentID.CRISIS
        assert decision["intent"] == "crisis"
        assert decision["context"]["has_crisis_keywords"] is True

    def test_support_decision(self):
        decision = make_routing_decision(
            message="Tôi cảm thấy buồn và stress",
            language="vi",
        )
        assert decision["target_agent"] in [
            AgentID.SUPPORT,
            AgentID.DIAGNOSTIC,
            AgentID.THEORY,
            AgentID.TREATMENT,
        ]

    def test_theory_decision(self):
        decision = make_routing_decision(
            message="Rối loạn lo âu tổng quát là gì?",
            language="vi",
        )
        assert decision["intent"] == "theory"


class TestSupervisorAgentRouting:
    """Test SupervisorAgent.run() routing output."""

    @pytest.mark.asyncio
    async def test_runs_without_domain_agents_registered(self):
        """SupervisorAgent should route even without domain agents (HTTP mode)."""
        mock_memory = AsyncMock()
        mock_memory.get_context.return_value = ""
        mock_memory.get_accumulated_slots.return_value = {}
        mock_memory.get_crisis_state.return_value = {
            "is_high_risk": False,
            "crisis_level": "none",
        }

        agent = SupervisorAgent(memory_service=mock_memory, llm=None, config={})
        gs: GlobalState = {}

        result = await agent.run(
            input={
                "message": "Tôi cảm thấy lo âu",
                "conv_id": "conv-test",
                "user_id": "user-1",
                "language": "vi",
            },
            gs=gs,
        )

        assert "target_agent" in result
        assert result["target_agent"] in [
            AgentID.DIAGNOSTIC,
            AgentID.SUPPORT,
            AgentID.THEORY,
            AgentID.TREATMENT,
        ]
        assert "context" in result

    @pytest.mark.asyncio
    async def test_crisis_routes_to_crisis_agent(self):
        mock_memory = AsyncMock()
        mock_memory.get_context.return_value = ""
        mock_memory.get_accumulated_slots.return_value = {}
        mock_memory.get_crisis_state.return_value = {
            "is_high_risk": False,
            "crisis_level": "none",
        }

        agent = SupervisorAgent(memory_service=mock_memory, llm=None, config={})
        gs: GlobalState = {}

        result = await agent.run(
            input={
                "message": "Tôi muốn tự tử",
                "conv_id": "conv-crisis",
                "user_id": "user-1",
                "language": "vi",
            },
            gs=gs,
        )

        assert result["target_agent"] == AgentID.CRISIS

    @pytest.mark.asyncio
    async def test_updates_global_state(self):
        mock_memory = AsyncMock()
        mock_memory.get_context.return_value = ""
        mock_memory.get_accumulated_slots.return_value = {}
        mock_memory.get_crisis_state.return_value = {
            "is_high_risk": False,
            "crisis_level": "none",
        }

        agent = SupervisorAgent(memory_service=mock_memory, llm=None, config={})
        gs: GlobalState = {}

        await agent.run(
            input={
                "message": "Triệu chứng của trầm cảm là gì?",
                "conv_id": "conv-gs",
                "user_id": "user-1",
                "language": "vi",
            },
            gs=gs,
        )

        assert gs.get("original_message") == "Triệu chứng của trầm cảm là gì?"
        assert gs.get("conversation_id") == "conv-gs"
