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
from ai.shared.exceptions import RetrievalUnavailableError
from .agent_state import DiagnosticLocalState

from .skills.symptom_extraction import SymptomExtraction
from .skills.diagnostic_retrieval import DiagnosticRetrieval
from .skills.clinical_reasoning import ClinicalReasoning

logger = logging.getLogger(__name__)


_SLOT_QUESTIONS: dict[str, str] = {
    "emotion": "Bạn đang cảm thấy như thế nào? (buồn, lo âu, sợ, giận, bế tắc, v.v.)",
    "trigger": "Điều gì đã xảy ra hoặc điều gì khiến bạn cảm thấy như vậy?",
    "duration": "Tình trạng này kéo dài bao lâu rồi? (hôm nay, vài ngày, tuần, tháng...)",
    "intensity": "Mức độ nghiêm trọng? Bạn đánh giá như thế nào? (nhẹ, trung bình, nặng)",
    "impact": "Triệu chứng này ảnh hưởng đến cuộc sống hàng ngày của bạn như thế nào? (công việc, học tập, ngủ, ăn...)",
    "stress_level": "Mức độ căng thẳng hiện tại của bạn? 1-10?",
    "sleep_quality": "Giấc ngủ của bạn có thay đổi gì không? (mất ngủ, ngủ ít, ngủ nhiều hơn, ác mộng...)",
    "appetite_changes": "Ăn uống của bạn có thay đổi không? (chán ăn, ăn nhiều hơn, không muốn ăn...)",
}


class DiagnosticAgent(BaseAgent):
    """
    DiagnosticAgent — DSM-5 mental health symptom assessment.

    GOAL: Collect symptoms, reason, and output binary decision.
    NOT a medical diagnosis — just "có bệnh" or "không có bệnh".

    Pipeline:
      1. Extract slots from message (SymptomExtraction)
      2. Merge with accumulated slots (MemoryService)
      3. Check sufficiency (≥5/8 required slots)
      4. If insufficient → ask for missing slots (slot filling)
      5. If sufficient → retrieve candidates + DSM chunks
      6. LLM clinical reasoning → has_disorder?
      7. Return result to SupervisorAgent

    Output:
      - has_disorder=true  → Supervisor routes → TreatmentAgent (treatment plan)
      - has_disorder=false → Supervisor routes → SupportAgent (coping strategies)
    """

    def __init__(
        self,
        memory_service: Any,
        llm: Any = None,
        config: dict | None = None,
    ):
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
            "ClinicalReasoning":   ClinicalReasoning(llm=llm, memory_service=memory_service),
        }
        self._shared_tools = create_shared_memory_tools(memory_service)

        super().__init__(
            agent_id=AgentID.DIAGNOSTIC,
            memory_service=memory_service,
            llm=llm,
            config=config or {},
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
        preliminary_slots: dict = context.get("preliminary_slots", {})

        local: DiagnosticLocalState = {
            "goal": "diagnostic_assessment",
            "step": "start",
            "done": False,
            "query": message,
        }
        self.local_memory.update(local)

        self.info(f"Processing diagnostic: '{message[:50]}...'")
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
                )

            # ── 5. Diagnostic retrieval ─────────────────────────────────────
            local["step"] = "retrieval"
            retrieval_result = await self._skills["DiagnosticRetrieval"].retrieve(
                query=message,
                slots=merged,
                conv_id=conv_id,
            )
            candidates = retrieval_result["candidates"]
            diagnostic_chunks = retrieval_result["diagnostic_chunks"]

            # ── 6. Clinical reasoning (LLM) ─────────────────────────────────
            local["step"] = "reasoning"
            diagnosis = await self._skills["ClinicalReasoning"].reason(
                slots=merged,
                candidates=candidates,
                diagnostic_chunks=diagnostic_chunks,
                conv_id=conv_id,
                context="",
            )

            has_disorder = diagnosis.get("has_disorder", False)
            slots_collected = sum(1 for v in merged.values() if v not in (None, ""))

            local["slots_collected"] = slots_collected
            local["candidates_count"] = len(candidates)
            local["has_disorder"] = has_disorder
            local["diagnosis"] = diagnosis.get("diagnosis") or ""
            local["confidence"] = float(diagnosis.get("confidence") or 0.0)
            local["step"] = "completed"
            local["done"] = True
            self.local_memory.update(local)

            # ── 7. Save to memory ─────────────────────────────────────────
            await self.memory_service.save_buffer(
                conv_id=conv_id,
                role="assistant",
                content=f"[DiagnosticAgent] has_disorder={has_disorder} diagnosis={diagnosis.get('diagnosis')} confidence={diagnosis.get('confidence')}",
                metadata={
                    "agent": self.agent_id,
                    "has_disorder": has_disorder,
                    "diagnosis": diagnosis.get("diagnosis"),
                    "confidence": diagnosis.get("confidence"),
                },
            )

            # ── 8. Update GlobalState ──────────────────────────────────────
            gs["has_disorder"] = has_disorder
            gs["diagnosis"] = diagnosis.get("diagnosis")
            gs["diagnostic_confidence"] = diagnosis.get("confidence")
            gs["diagnostic_reasoning"] = diagnosis.get("reasoning", "")
            gs["diagnostic_basis"] = diagnosis.get("basis", [])
            gs["diagnostic_differential"] = diagnosis.get("differential", [])
            gs["diagnostic_recommendation"] = diagnosis.get("recommendation", "")

            emitter.emit_agent_finished(self.agent_id, output_summary=f"has_disorder={has_disorder}")

            # ── 9. Return binary result to Supervisor ─────────────────────────
            return {
                "agent_id": self.agent_id,
                "has_disorder": has_disorder,
                "diagnosis": diagnosis.get("diagnosis"),
                "confidence": diagnosis.get("confidence"),
                "reasoning": diagnosis.get("reasoning", ""),
                "basis": diagnosis.get("basis", []),
                "differential": diagnosis.get("differential", []),
                "recommendation": diagnosis.get("recommendation", ""),
                "slots_collected": slots_collected,
                "candidates_count": len(candidates),
                "intent": "diagnostic",
            }

        except RetrievalUnavailableError as e:
            self.error(f"DiagnosticAgent retrieval unavailable: {e}")
            emitter.emit_agent_error(self.agent_id, str(e))
            gs["error"] = str(e)
            gs["has_disorder"] = False
            return {
                "agent_id": self.agent_id,
                "has_disorder": False,
                "diagnosis": None,
                "confidence": 0.0,
                "error": str(e),
                "intent": "diagnostic",
            }
        except Exception as e:
            self.error(f"DiagnosticAgent failed: {e}")
            emitter.emit_agent_error(self.agent_id, str(e))
            gs["error"] = str(e)
            gs["has_disorder"] = False
            return {
                "agent_id": self.agent_id,
                "has_disorder": False,
                "diagnosis": None,
                "confidence": 0.0,
                "error": str(e),
                "intent": "diagnostic",
            }

    async def _ask_for_slots(
        self,
        conv_id: str,
        missing: list[str],
        merged: dict[str, Any],
        gs: GlobalState,
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
