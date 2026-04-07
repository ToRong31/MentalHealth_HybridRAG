"""
CrisisAgent — psychological crisis intervention.

Priority: CRITICAL — can interrupt all other agents.
"""

from __future__ import annotations

import logging
from typing import Any

from ai.shared.agent_based.base_agent import BaseAgent
from ai.shared.agent_based.state import GlobalState
from ai.shared.agent_based.constants import AgentID
from ai.shared.communication.events import emitter
from ai.shared.memory_tools import create_shared_memory_tools

from .skills.crisis_detection import CrisisDetection
from .skills.immediate_response import ImmediateResponse
from .skills.professional_escalation import ProfessionalEscalation
from .skills.follow_up_support import FollowUpSupport
from .skills.documentation import Documentation

logger = logging.getLogger(__name__)


class CrisisAgent(BaseAgent):
    """
    CrisisAgent — psychological crisis intervention.

    Priority: CRITICAL
    Can interrupt all other running agents via MessageBus.

    Pipeline:
      1. CrisisDetection → determine crisis level
      2. ImmediateResponse → respond immediately
      3. ProfessionalEscalation → provide hotlines
      4. FollowUpSupport → next steps guidance
      5. Documentation → log event
    """

    def __init__(
        self,
        memory_service: Any,
        llm: Any = None,
        config: dict | None = None,
    ):
        self._skills = {
            "CrisisDetection": CrisisDetection(llm=llm),
            "ImmediateResponse": ImmediateResponse(llm=llm),
            "ProfessionalEscalation": ProfessionalEscalation(llm=llm),
            "FollowUpSupport": FollowUpSupport(llm=llm),
            "Documentation": Documentation(llm=llm),
        }
        self._shared_tools = create_shared_memory_tools(memory_service)

        super().__init__(
            agent_id=AgentID.CRISIS,
            memory_service=memory_service,
            llm=llm,
            config=config or {},
        )

        logger.warning("[CrisisAgent] Initialized — CRITICAL priority")

    def _register_tools(self) -> dict[str, dict[str, Any]]:
        return self._shared_tools

    def _register_skills(self) -> dict[str, Any]:
        return self._skills

    async def handle_crisis(
        self,
        input: dict[str, Any],
        gs: GlobalState,
    ) -> dict[str, Any]:
        """
        Full crisis handling pipeline.
        Called by ChatService when CrisisAgent is targeted.
        Also called as interrupt by any other agent.
        """
        context: dict = input.get("context", {})
        conv_id: str = context.get("conv_id", "")
        message: str = context.get("original_message", "")
        user_id: str = gs.get("user_id", "") or context.get("user_id", "")
        language: str = context.get("language", "vi")
        matched_keywords: list[str] = context.get("preliminary_slots", {}).get(
            "crisis_keywords", []
        )

        self.warning(f"Handling crisis: '{message[:50]}...'")

        emitter.emit_agent_started(self.agent_id, input_summary=message[:100])
        emitter.emit_crisis_detected(
            self.agent_id,
            crisis_level="active",
            indicators=matched_keywords,
        )

        try:
            # ── 1. Update crisis state in memory ───────────────────────────
            crisis_state = {
                "is_high_risk": True,
                "crisis_level": "active",
                "detected_at": _utc_now(),
                "escalation_done": False,
                "hotline_provided": False,
                "notes": [],
            }
            await self.memory_service.update_crisis_state(conv_id, crisis_state)

            # ── 2. CrisisDetection: determine level ────────────────────────
            detection = await self._skills["CrisisDetection"].detect(
                message=message,
                matched_keywords=matched_keywords,
                context=await self.memory_service.get_context(conv_id),
            )
            crisis_level = detection["level"]

            # ── 3. Persist crisis state in Redis ────────────────────────────
            # Subsequent requests for this conversation will route to CrisisAgent immediately
            # (checked in MemoryService.get_crisis_state by all agents)
            await self.update_crisis_state(
                conv_id,
                {
                    "is_high_risk": True,
                    "level": crisis_level,
                    "indicators": detection["indicators"],
                    "detected_at": detection.get("detected_at"),
                },
            )

            gs["is_high_risk"] = True
            gs["crisis_level"] = crisis_level
            gs["crisis_indicators"] = detection["indicators"]
            gs["interrupted"] = True

            # ── 4. ImmediateResponse ───────────────────────────────────────
            immediate_text = await self._skills["ImmediateResponse"].respond(
                crisis_level=crisis_level,
                message=message,
                language=language,
            )

            # ── 5. ProfessionalEscalation: hotlines ────────────────────────
            escalation = await self._skills["ProfessionalEscalation"].escalate(
                crisis_level=crisis_level,
                language=language,
            )

            hotlines_text = self._format_hotlines(escalation["hotlines"])

            # ── 6. FollowUpSupport ─────────────────────────────────────────
            followup_text = await self._skills["FollowUpSupport"].generate(
                crisis_level=crisis_level,
                language=language,
            )

            # ── 7. Build final response ───────────────────────────────────
            response_parts = [
                immediate_text,
                f"\n\n**Thông tin hỗ trợ:**\n{hotlines_text}",
                f"\n\n{followup_text}",
                "\n\n---\n*Mình không phải bác sĩ. Nếu bạn đang trong nguy hiểm ngay lập tức, xin gọi cấp cứu 113.*",
            ]
            response = "\n".join(response_parts)

            # ── 8. Documentation ───────────────────────────────────────────
            await self._skills["Documentation"].log_crisis_event(
                conv_id=conv_id,
                user_id=user_id,
                message=message,
                crisis_level=crisis_level,
                indicators=detection["indicators"],
                response=response,
                escalation_done=escalation["professional_help_needed"],
            )

            # ── 9. Save to memory ─────────────────────────────────────────
            await self.memory_service.save_buffer(
                conv_id=conv_id,
                role="assistant",
                content=response,
                metadata={
                    "agent": self.agent_id,
                    "crisis_level": crisis_level,
                    "skills_used": list(self._skills.keys()),
                },
            )

            # Update crisis state
            crisis_state["crisis_level"] = crisis_level
            crisis_state["escalation_done"] = escalation["professional_help_needed"]
            crisis_state["hotline_provided"] = True
            await self.memory_service.update_crisis_state(conv_id, crisis_state)

            emitter.emit_agent_finished(
                self.agent_id,
                output_summary=f"Crisis level={crisis_level} response generated",
                duration_ms=None,
            )

            self.warning(f"Crisis handled: level={crisis_level}")

            return {
                "response": response,
                "agent_id": self.agent_id,
                "crisis_level": crisis_level,
                "crisis_detected": True,
                "hotlines": escalation["hotlines"],
                "skills_used": list(self._skills.keys()),
                "intent": "crisis",
            }

        except Exception as e:
            self.error(f"CrisisAgent failed: {e}")
            emitter.emit_agent_error(self.agent_id, str(e))

            # Even on error, return safe fallback
            fallback = (
                "**Mình rất lo cho bạn.**\n\n"
                "Nếu bạn đang nghĩ đến việc tự hại, xin hãy gọi ngay: **094 234 99 99**.\n"
                "Bạn có thể gọi bất cứ lúc nào, 24/7."
            )
            return {
                "response": fallback,
                "agent_id": self.agent_id,
                "crisis_level": "unknown",
                "crisis_detected": True,
                "skills_used": [],
                "intent": "crisis",
            }

    async def run(self, input: dict[str, Any], gs: GlobalState) -> dict[str, Any]:
        """Entry point — delegates to handle_crisis."""
        return await self.handle_crisis(input, gs)

    def _format_hotlines(self, hotlines: list[dict[str, str]]) -> str:
        """Format hotlines list as readable text."""
        lines = []
        for h in hotlines:
            lines.append(f"- **{h.get('name', '')}**")
            lines.append(f"  📞 {h.get('phone', '')}")
            if h.get("hours"):
                lines.append(f"  ⏰ {h.get('hours', '')}")
            if h.get("description"):
                lines.append(f"  {h.get('description', '')}")
        return "\n".join(lines)


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
