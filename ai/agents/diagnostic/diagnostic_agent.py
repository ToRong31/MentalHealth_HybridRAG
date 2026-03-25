"""
DiagnosticAgent — DSM-5 based mental health symptom assessment.
"""
from __future__ import annotations

import logging
from typing import Any

from ai.shared.agent_based.base_agent import BaseAgent
from ai.shared.agent_based.state import GlobalState
from ai.shared.agent_based.constants import AgentID, MIN_SUFFICIENT_SLOTS
from ai.shared.communication.events import emitter
from ai.shared.memory_tools import create_shared_memory_tools

from .skills.symptom_extraction import SymptomExtraction
from .skills.diagnostic_retrieval import DiagnosticRetrieval
from .skills.clinical_reasoning import ClinicalReasoning
from .skills.response_drafting import ResponseDrafting

logger = logging.getLogger(__name__)


_SLOT_QUESTIONS: dict[str, str] = {
    "emotion": "Bạn đang cảm thấy như thế nào? (buồn, lo âu, sợ, giận, chán, v.v.)",
    "trigger": "Điều gì đã xảy ra hoặc điều gì khiến bạn cảm thấy như vậy?",
    "duration": "Tình trạng này kéo dài bao lâu rồi? (hôm nay, vài ngày, tuần, tháng...)",
    "intensity": "Mức độ nghiêm trọng? Bạn đánh giá 1-10 (1=nhẹ, 10=rất nặng)?",
    "impact": "Triệu chứng này ảnh hưởng đến cuộc sống hàng ngày của bạn như thế nào?",
    "stress_level": "Mức độ căng thẳng của bạn hiện tại? 1-10?",
    "sleep": "Giấc ngủ của bạn có thay đổi gì không? (mất ngủ, ngủ nhiều, ác mộng...)",
    "appetite": "Ăn uống của bạn có thay đổi không? (chán ăn, ăn nhiều hơn...)",
}


class DiagnosticAgent(BaseAgent):
    """
    DiagnosticAgent — DSM-5 mental health symptom assessment.

    GOAL: Collect symptoms (slots), retrieve candidates, reason, and provide
    a preliminary assessment. NOT a medical diagnosis.

    Pipeline:
      1. Extract slots from message (SymptomExtraction)
      2. Merge with accumulated slots (MemoryService)
      3. Check sufficiency (≥5/6 required slots)
      4. If sufficient → retrieve + reason → format
      5. If insufficient → ask for missing slots
    """

    def __init__(
        self,
        memory_service: Any,
        llm: Any = None,
        config: dict | None = None,
        message_bus: Any = None,
    ):
        # RAG clients injected via config by ai.main.create_ai_engine()
        milvus = (config or {}).get("milvus")
        neo4j = (config or {}).get("neo4j")
        reranker = (config or {}).get("reranker")

        self._skills = {
            "SymptomExtraction":   SymptomExtraction(llm=llm),
            "DiagnosticRetrieval": DiagnosticRetrieval(
                llm=llm,
                milvus=milvus,
                neo4j=neo4j,
                reranker=reranker,
            ),
            "ClinicalReasoning":   ClinicalReasoning(llm=llm),
            "ResponseDrafting":    ResponseDrafting(llm=llm),
        }
        self._shared_tools = create_shared_memory_tools(memory_service)

        super().__init__(
            agent_id=AgentID.DIAGNOSTIC,
            memory_service=memory_service,
            llm=llm,
            config=config or {},
            message_bus=message_bus,
        )

        logger.info("[DiagnosticAgent] Initialized")

    def _register_tools(self) -> dict[str, dict[str, Any]]:
        return self._shared_tools

    def _register_skills(self) -> dict[str, Any]:
        return self._skills

    async def run(self, input: dict[str, Any], gs: GlobalState) -> dict[str, Any]:
        context: dict = input.get("context", {})
        conv_id: str = context.get("conv_id", "")
        message: str = context.get("original_message", "")
        language: str = context.get("language", "vi")
        preliminary_slots: dict = context.get("preliminary_slots", {})

        self.info(f"Processing diagnostic request: '{message[:50]}...'")
        emitter.emit_agent_started(self.agent_id, input_summary=message[:100])

        try:
            # ── 1. Get accumulated slots from memory ────────────────────────
            existing_slots = await self.memory_service.get_accumulated_slots(conv_id)

            # ── 2. Extract new slots from message ─────────────────────────
            new_slots = await self._skills["SymptomExtraction"].extract(
                message=message,
                existing_slots=existing_slots,
            )

            # Merge preliminary slots from Supervisor
            for k, v in preliminary_slots.items():
                if v and k not in new_slots:
                    new_slots[k] = v

            # ── 3. Merge slots into memory ─────────────────────────────────
            merged = await self.memory_service.merge_slots(conv_id, new_slots)

            # ── 4. Check sufficiency ───────────────────────────────────────
            sufficiency = await self.memory_service.get_slot_sufficiency(conv_id)

            if not sufficiency["is_sufficient"]:
                return await self._ask_for_slots(
                    conv_id=conv_id,
                    missing=sufficiency["missing"],
                    merged=merged,
                    gs=gs,
                    language=language,
                )

            # ── 5. Diagnostic retrieval ─────────────────────────────────────
            candidates = await self._skills["DiagnosticRetrieval"].search(
                query=message,
                slots=merged,
            )

            # ── 6. Clinical reasoning ─────────────────────────────────────
            diagnosis = await self._skills["ClinicalReasoning"].reason(
                slots=merged,
                candidates=candidates,
                context=message,
            )

            # ── 7. Response drafting ──────────────────────────────────────
            formatted = await self._skills["ResponseDrafting"].format(
                diagnosis=diagnosis,
                slots=merged,
                language=language,
            )

            response_text = formatted["response"]

            # ── 8. Save to memory ─────────────────────────────────────────
            await self.memory_service.save_buffer(
                conv_id=conv_id,
                role="assistant",
                content=response_text,
                metadata={
                    "agent": self.agent_id,
                    "diagnosis": diagnosis.get("diagnosis"),
                    "confidence": diagnosis.get("confidence"),
                },
            )

            gs["detected_disease"] = diagnosis.get("diagnosis")
            gs["diagnostic_confidence"] = diagnosis.get("confidence")
            gs["response"] = response_text
            gs["skills_used"] = list(self._skills.keys())

            emitter.emit_agent_finished(self.agent_id, output_summary=response_text[:80])

            return {
                "response": response_text,
                "agent_id": self.agent_id,
                "diagnosis": diagnosis.get("diagnosis"),
                "confidence": diagnosis.get("confidence"),
                "skills_used": list(self._skills.keys()),
                "intent": "diagnostic",
            }

        except Exception as e:
            self.error(f"DiagnosticAgent failed: {e}")
            emitter.emit_agent_error(self.agent_id, str(e))
            gs["error"] = str(e)

            fallback = (
                "Mình gặp khó khăn khi xử lý thông tin chuẩn đoán. "
                "Bạn có thể chia sẻ thêm về triệu chứng và cảm xúc của mình không?"
            )
            return {
                "response": fallback,
                "agent_id": self.agent_id,
                "skills_used": [],
                "intent": "diagnostic",
            }

    async def _ask_for_slots(
        self,
        conv_id: str,
        missing: list[str],
        merged: dict[str, Any],
        gs: GlobalState,
        language: str,
    ) -> dict[str, Any]:
        """Generate a response asking for missing diagnostic slots."""
        # Ask for top 2 missing slots
        ask_slots = missing[:2]
        questions = []
        for slot in ask_slots:
            if slot in _SLOT_QUESTIONS:
                questions.append(_SLOT_QUESTIONS[slot])

        response_text = (
            "Để mình có thể hỗ trợ bạn tốt hơn, bạn có thể cho mình biết thêm:\n\n"
            + "\n\n".join(f"• {q}" for q in questions)
            + "\n\n_Thông tin càng nhiều, mình càng giúp bạn rõ hơn._"
        )

        await self.memory_service.save_buffer(
            conv_id=conv_id,
            role="assistant",
            content=response_text,
            metadata={
                "agent": self.agent_id,
                "type": "slot_filling",
                "missing_slots": ask_slots,
            },
        )

        gs["slots_sufficient"] = False
        gs["missing_slots"] = missing

        return {
            "response": response_text,
            "agent_id": self.agent_id,
            "skills_used": ["SymptomExtraction"],
            "missing_slots": missing,
            "intent": "diagnostic",
            "slot_filling": True,
        }
