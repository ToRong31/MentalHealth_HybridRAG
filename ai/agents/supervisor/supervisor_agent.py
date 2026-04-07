"""
SupervisorAgent — pure router, no ReAct loop.

Responsibilities:
  1. Crisis safety gate (keyword match, O(1), NO LLM)
  2. Intent classification (keyword + LLM fallback)
  3. Extract preliminary context
  4. Route to correct domain agent

KHÔNG điều khiển từng bước. KHÔNG gọi domain agents trực tiếp.
"""
from __future__ import annotations

import logging
from typing import Any

from ai.shared.agent_based.base_agent import BaseAgent
from ai.shared.agent_based.state import GlobalState
from ai.shared.agent_based.constants import AgentID
from ai.shared.communication.events import emitter

from .skills.intent_classification import IntentClassification
from .skills.preliminary_context import PreliminaryContextSkill
from .tools.routing_tools import route_to_agent, build_routing_context
from .agent_state import RoutingDecision

logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    """
    SupervisorAgent — intent routing only.

    Runs ONCE per user message:
      message → crisis_gate → intent_classify → preliminary_context → route

    Output: {"target_agent": str, "context": dict}
    Does NOT call the target agent — ChatService dispatches.
    """

    def __init__(
        self,
        memory_service: Any,
        llm: Any = None,
        config: dict | None = None,
    ):
        self._intent_classifier = IntentClassification(llm=llm)
        self._preliminary_context = PreliminaryContextSkill(llm=llm)
        # _domain_agents: populated by register_domain_agents() for in-process routing.
        # For standalone microservice (main.py), domain agents are called via HTTP,
        # so this dict is not used — but we initialize to {} to avoid AttributeError.
        self._domain_agents: dict[str, Any] = {}

        super().__init__(
            agent_id=AgentID.SUPERVISOR,
            memory_service=memory_service,
            llm=llm,
            config=config or {},
        )

        logger.info("[SupervisorAgent] Initialized — routing only, no ReAct loop")

    # ── Register domain agents ──────────────────────────────────────────────

    def register_domain_agents(self, agents: dict[str, Any]) -> None:
        """Called by ChatService to inject domain agent references (in-process mode)."""
        self._domain_agents = agents
        logger.info(f"[SupervisorAgent] Domain agents registered: {list(agents.keys())}")

    # ── BaseAgent abstract methods ──────────────────────────────────────────

    def _register_tools(self) -> dict[str, dict[str, Any]]:
        """Supervisor has no tools — pure routing."""
        return {}

    def _register_skills(self) -> dict[str, Any]:
        return {
            "IntentClassification": self._intent_classifier,
            "PreliminaryContext": self._preliminary_context,
        }

    async def run(self, input: dict[str, Any], gs: GlobalState) -> dict[str, Any]:
        """
        Main entry point — called by ChatService.

        Input
        -----
        {
            "message": "user message text",
            "conv_id": "uuid",
            "user_id": "uuid",
            "language": "vi",
        }

        Output
        ------
        {
            "target_agent": "diagnostic" | "theory" | "treatment" | "support" | "crisis",
            "context": {
                "original_message": str,
                "translated_message": str,
                "language": str,
                "preliminary_slots": dict,
                "intent": str,
                "conv_id": str,
            },
        }
        """
        message: str = input.get("message", "")
        conv_id: str = input.get("conv_id", "")
        user_id: str = input.get("user_id", "")
        language: str = input.get("language", "vi")

        self.info(f"Routing message: '{message[:50]}...'")

        # Update GlobalState
        gs["original_message"] = message
        gs["conversation_id"] = conv_id
        gs["user_id"] = user_id
        gs["language"] = language

        emitter.emit_agent_started(self.agent_id, input_summary=message[:100])

        try:
            # ── Step 1: Crisis gate ────────────────────────────────────────
            from ai.agents.supervisor.router import check_crisis_gate
            has_crisis, matched_keywords = check_crisis_gate(message)

            if has_crisis:
                self.warning(f"CRISIS GATE triggered: {matched_keywords}")
                emitter.emit_crisis_detected(
                    self.agent_id,
                    crisis_level="active",
                    indicators=matched_keywords,
                )
                gs["is_high_risk"] = True
                gs["crisis_indicators"] = matched_keywords

                return {
                    "target_agent": AgentID.CRISIS,
                    "context": build_routing_context(
                        original_message=message,
                        translated_message=message,
                        language=language,
                        preliminary_slots={"crisis_keywords": matched_keywords},
                        intent="crisis",
                        conv_id=conv_id,
                    ),
                }

            # ── Step 2: Intent classification ─────────────────────────────
            intent_result = await self._intent_classifier.classify(message, language)
            gs["intent"] = intent_result["intent"]

            # ── Step 3: Preliminary context ───────────────────────────────
            preliminary = await self._preliminary_context.extract(message)

            # ── Step 4: Route ─────────────────────────────────────────────
            target = route_to_agent(intent_result["intent"], self._domain_agents)

            gs["target_agent"] = target
            gs["language"] = preliminary.get("language", language)

            routing = RoutingDecision(
                target_agent=target,
                intent=intent_result["intent"],
                confidence=float(intent_result["confidence"]),
                context={
                    "language": preliminary.get("language", language),
                    "has_crisis_keywords": intent_result["has_crisis_keywords"],
                    "crisis_keywords_found": intent_result.get("crisis_keywords_found", []),
                    "preliminary_slots": preliminary.get("preliminary_slots", {}),
                },
                translated_message=message,
            )

            emitter.emit_routing_decided(
                self.agent_id,
                intent=intent_result["intent"],
                target_agent=target,
            )

            emitter.emit_agent_finished(
                self.agent_id,
                output_summary=f"→ {target}",
                duration_ms=None,
            )

            self.info(f"Routed: intent={intent_result['intent']} confidence={intent_result['confidence']:.2f} → {target}")

            return {
                "target_agent": target,
                "context": build_routing_context(
                    original_message=message,
                    translated_message=routing["translated_message"],
                    language=routing["context"]["language"],
                    preliminary_slots=routing["context"]["preliminary_slots"],
                    intent=routing["intent"],
                    conv_id=conv_id,
                ),
            }

        except Exception as e:
            self.error(f"Routing failed: {e}")
            emitter.emit_agent_error(self.agent_id, str(e))
            gs["error"] = str(e)
            # Fallback to support on any error
            return {
                "target_agent": AgentID.SUPPORT,
                "context": build_routing_context(
                    original_message=message,
                    translated_message=message,
                    language=language,
                    preliminary_slots={},
                    intent="support",
                    conv_id=conv_id,
                ),
            }
