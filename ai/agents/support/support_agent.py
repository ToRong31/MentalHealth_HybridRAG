"""
SupportAgent — emotional support, coping strategies, psychoeducation.
"""

from __future__ import annotations

import logging
from typing import Any

from ai.shared.agent_based.base_agent import BaseAgent
from ai.shared.agent_based.state import GlobalState
from ai.shared.agent_based.constants import AgentID
from ai.shared.communication.events import emitter
from ai.shared.memory_tools import create_shared_memory_tools

from .skills.coping_retrieval import CopingRetrieval
from .skills.emotional_support import EmotionalSupport
from .skills.psycho_education import PsychoEducation
from .skills.skill_building import SkillBuilding
from .skills.answer_formatting import AnswerFormatting

logger = logging.getLogger(__name__)


class SupportAgent(BaseAgent):
    """
    SupportAgent — non-disorder emotional support.

    GOAL: Hỗ trợ sức khỏe tinh thần (không phải chuẩn đoán bệnh).
    Mỗi request hoàn thành A→Z trong 1 lần run().
    """

    def __init__(
        self,
        memory_service: Any,
        llm: Any = None,
        config: dict | None = None,
    ):
        self._skills = {
            "CopingRetrieval": CopingRetrieval(llm=llm),
            "EmotionalSupport": EmotionalSupport(llm=llm),
            "PsychoEducation": PsychoEducation(llm=llm),
            "SkillBuilding": SkillBuilding(llm=llm),
            "AnswerFormatting": AnswerFormatting(llm=llm),
        }
        self._shared_tools = create_shared_memory_tools(memory_service)

        super().__init__(
            agent_id=AgentID.SUPPORT,
            memory_service=memory_service,
            llm=llm,
            config=config or {},
        )

        logger.info("[SupportAgent] Initialized")

    def _register_tools(self) -> dict[str, dict[str, Any]]:
        return self._shared_tools

    def _register_skills(self) -> dict[str, Any]:
        return self._skills

    async def run(self, input: dict[str, Any], gs: GlobalState) -> dict[str, Any]:
        """
        Full pipeline: extract context → run skills → format response → save.
        """
        context: dict = input.get("context", {})
        conv_id: str = context.get("conv_id", "")
        message: str = context.get("original_message", "")
        language: str = context.get("language", "vi")
        preliminary_slots: dict = context.get("preliminary_slots", {})

        self.info(f"Processing support request: '{message[:50]}...'")

        emitter.emit_agent_started(self.agent_id, input_summary=message[:100])

        try:
            # ── 1. Get accumulated context from memory ──────────────────────
            full_context = await self.memory_service.get_context(conv_id)
            if full_context:
                combined_context = f"{full_context}\n\nUser: {message}"
            else:
                combined_context = message

            # ── 2. Extract emotion hint from slots ─────────────────────────
            emotion_hint = preliminary_slots.get("emotion")

            # ── 3. Run skills in parallel groups ───────────────────────────
            # Group 1: content retrieval (can run in parallel)
            coping_task = self._skills["CopingRetrieval"].execute(
                context=combined_context,
                gs=gs,
                emotion_hint=emotion_hint,
            )
            psycho_task = self._skills["PsychoEducation"].execute(
                context=combined_context,
                gs=gs,
            )
            exercises_task = self._skills["SkillBuilding"].execute(
                context=combined_context,
                gs=gs,
            )

            coping_strategies, psycho_content, exercises = await self._run_parallel(
                coping_task, psycho_task, exercises_task
            )

            # Group 2: response generation (sequential — needs coping results)
            emotional_response = await self._skills["EmotionalSupport"].execute(
                context=combined_context,
                gs=gs,
                emotion_hint=emotion_hint,
            )

            # ── 4. Format final response ───────────────────────────────────
            formatted = await self._skills["AnswerFormatting"].format(
                emotional_response=emotional_response,
                coping_strategies=coping_strategies,
                exercises=exercises,
                psychoeducation=psycho_content,
                language=language,
            )

            response_text = formatted["response"]

            # ── 5. Save to memory buffer ───────────────────────────────────
            await self.memory_service.save_buffer(
                conv_id=conv_id,
                role="assistant",
                content=response_text,
                metadata={"agent": self.agent_id, "skills_used": formatted["sections"]},
            )

            # ── 6. Update GlobalState ──────────────────────────────────────
            gs["response"] = response_text
            gs["skills_used"] = list(self._skills.keys())

            emitter.emit_agent_finished(
                self.agent_id,
                output_summary=response_text[:80],
                duration_ms=None,
            )

            self.info(f"Support response generated ({len(response_text)} chars)")

            return {
                "response": response_text,
                "agent_id": self.agent_id,
                "skills_used": list(self._skills.keys()),
                "intent": "support",
            }

        except Exception as e:
            self.error(f"SupportAgent failed: {e}")
            emitter.emit_agent_error(self.agent_id, str(e))
            gs["error"] = str(e)

            # Graceful fallback
            fallback = (
                "Mình hiểu bạn đang trải qua điều gì đó khó khăn. "
                "Cảm ơn bạn đã chia sẻ. "
                "Bạn muốn nói thêm về cảm xúc của mình không?"
            )
            return {
                "response": fallback,
                "agent_id": self.agent_id,
                "skills_used": [],
                "intent": "support",
            }

    async def _run_parallel(self, *tasks):
        """Run coroutines in parallel and return results."""
        import asyncio

        return await asyncio.gather(*tasks, return_exceptions=True)
