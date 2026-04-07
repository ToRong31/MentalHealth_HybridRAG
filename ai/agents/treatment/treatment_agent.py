"""
TreatmentAgent — evidence-based treatment guidance.
"""
from __future__ import annotations

import logging
from typing import Any

from ai.shared.agent_based.base_agent import BaseAgent
from ai.shared.agent_based.state import GlobalState
from ai.shared.agent_based.constants import AgentID
from ai.shared.communication.events import emitter
from ai.shared.memory_tools import create_shared_memory_tools
from ai.shared.exceptions import RetrievalUnavailableError
from .agent_state import TreatmentLocalState
from ai.shared.exceptions import RetrievalUnavailableError
from .agent_state import TreatmentLocalState

from .skills.treatment_retrieval import TreatmentRetrieval
from .skills.treatment_planning import TreatmentPlanning
from .skills.patient_guidance import PatientGuidance
from .skills.answer_formatting import AnswerFormatting

logger = logging.getLogger(__name__)


DISCLAIMER = (
    "*⚠️ **Tuyên bố miễn trừ trách nhiệm:**\n"
    "Thông tin trong cuộc trò chuyện này chỉ mang tính chất giáo dục và KHÔNG phải "
    "là lời khuyên y khoa. Mình không phải bác sĩ. "
    "Mọi quyết định điều trị phải được thực hiện cùng với bác sĩ hoặc nhà trị liệu "
    "có chuyên môn. Nếu bạn đang có ý nghĩ tự hại, xin gọi ngay: **094 234 99 99**.*"
)


class TreatmentAgent(BaseAgent):
    """
    TreatmentAgent — evidence-based treatment options and guidance.

    GOAL: Provide treatment information based on evidence, NOT replace professional care.
    Always includes medical disclaimer.
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
            "TreatmentRetrieval":  TreatmentRetrieval(
                llm=llm,
                milvus=milvus,
                neo4j=neo4j,
                reranker=reranker,
            ),
            "TreatmentPlanning":   TreatmentPlanning(llm=llm),
            "PatientGuidance":     PatientGuidance(llm=llm),
            "AnswerFormatting":     AnswerFormatting(llm=llm),
        }
        self._shared_tools = create_shared_memory_tools(memory_service)

        super().__init__(
            agent_id=AgentID.TREATMENT,
            memory_service=memory_service,
            llm=llm,
            config=config or {},
        )

        logger.info("[TreatmentAgent] Initialized")

    def _register_tools(self) -> dict[str, dict[str, Any]]:
        return self._shared_tools

    def _register_skills(self) -> dict[str, Any]:
        return self._skills

    async def run(self, input: dict[str, Any], gs: GlobalState) -> dict[str, Any]:
        context: dict = input.get("context", {})
        conv_id: str = context.get("conv_id", "")
        message: str = context.get("original_message", "")
        language: str = context.get("language", "vi")

        local: TreatmentLocalState = {
            "goal": "retrieve_and_plan_treatment",
            "step": "start",
            "done": False,
            "condition": message,
        }
        self.local_memory.update(local)

        self.info(f"Processing treatment request: '{message[:50]}...'")
        emitter.emit_agent_started(self.agent_id, input_summary=message[:100])

        try:
            # 1. Retrieve treatments
            local["step"] = "retrieve_treatments"
            treatments = await self._skills["TreatmentRetrieval"].retrieve(
                condition=message,
                context=await self.memory_service.get_context(conv_id),
            )

            if not treatments:
                fallback_text = (
                    "Mình chưa tìm được thông tin điều trị cụ thể cho vấn đề của bạn. "
                    "Mình khuyên bạn nên gặp bác sĩ tâm thần để được đánh giá chính xác."
                )
                return await self._finalize(fallback_text, [], gs, conv_id, language)

            # 2. Plan treatments
            severity = self._estimate_severity(context)
            plans = await self._skills["TreatmentPlanning"].plan(
                treatments=treatments,
                severity=severity,
            )

            # 3. Patient guidance
            treatment_types = [self._classify_type(t) for t in plans]
            guidance = await self._skills["PatientGuidance"].get_guidance(
                treatment_types=treatment_types,
                severity=severity,
                language=language,
            )

            # 4. Format response
            formatted = await self._skills["AnswerFormatting"].format(
                treatments=plans,
                patient_guidance=guidance,
                disclaimer=DISCLAIMER,
                language=language,
            )

            response_text = formatted["response"]

            # 5. Save
            await self.memory_service.save_buffer(
                conv_id=conv_id,
                role="assistant",
                content=response_text,
                metadata={
                    "agent": self.agent_id,
                    "treatment_count": formatted.get("treatment_count", 0),
                },
            )

            local["retrieved_count"] = len(treatments)
            local["plans_count"] = len(plans)
            local["step"] = "completed"
            local["done"] = True
            self.local_memory.update(local)

            local["retrieved_count"] = len(treatments)
            local["plans_count"] = len(plans)
            local["step"] = "completed"
            local["done"] = True
            self.local_memory.update(local)

            gs["response"] = response_text
            gs["skills_used"] = list(self._skills.keys())

            emitter.emit_agent_finished(self.agent_id, output_summary=response_text[:80])

            return {
                "response": response_text,
                "agent_id": self.agent_id,
                "skills_used": list(self._skills.keys()),
                "intent": "treatment",
            }

        except RetrievalUnavailableError as e:
            self.error(f"TreatmentAgent external retrieval unavailable: {e}")
            emitter.emit_agent_error(self.agent_id, str(e))
            gs["error"] = str(e)
            return {
                "response": "External treatment retrieval chưa sẵn sàng hoặc không có dữ liệu. Vui lòng ingest/index dữ liệu trước.",
                "agent_id": self.agent_id,
                "skills_used": [],
                "intent": "treatment",
                "error": str(e),
            }
        except Exception as e:
            self.error(f"TreatmentAgent failed: {e}")
            emitter.emit_agent_error(self.agent_id, str(e))
            gs["error"] = str(e)
            return {
                "response": "TreatmentAgent gặp lỗi nội bộ khi xử lý yêu cầu.",
                "agent_id": self.agent_id,
                "skills_used": [],
                "intent": "treatment",
                "error": str(e),
            }

    async def _finalize(
        self,
        text: str,
        skills: list[str],
        gs: GlobalState,
        conv_id: str,
        language: str,
    ) -> dict[str, Any]:
        await self.memory_service.save_buffer(conv_id, "assistant", text, metadata={"agent": self.agent_id})
        gs["response"] = text
        gs["skills_used"] = skills
        return {"response": text, "agent_id": self.agent_id, "skills_used": skills, "intent": "treatment"}

    def _estimate_severity(self, context: dict) -> str:
        """Estimate condition severity from context."""
        preliminary = context.get("preliminary_slots", {})
        intensity = preliminary.get("intensity")

        if isinstance(intensity, int):
            if intensity >= 8:
                return "severe"
            elif intensity >= 5:
                return "moderate"
        return "mild"

    def _classify_type(self, treatment: dict) -> str:
        """Classify treatment type for guidance."""
        name = treatment.get("name", "").lower()
        if any(w in name for w in ["thuốc", "ssri", "medication"]):
            return "medication"
        if any(w in name for w in ["liệu pháp", "therapy", "cbt", "dbt"]):
            return "therapy"
        return "therapy"
