"""
TheoryAgent — psychological knowledge and educational explanations.
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
from .agent_state import TheoryLocalState
from ai.shared.exceptions import RetrievalUnavailableError
from .agent_state import TheoryLocalState

from .skills.concept_retrieval import ConceptRetrieval
from .skills.educational_explanation import EducationalExplanation
from .skills.answer_formatting import AnswerFormatting

logger = logging.getLogger(__name__)


class TheoryAgent(BaseAgent):
    """
    TheoryAgent — psychological knowledge and educational explanations.

    GOAL: Provide accurate, educational psychological knowledge.
    NOT for diagnosis or treatment advice.
    """

    def __init__(
        self,
        memory_service: Any,
        llm: Any = None,
        config: dict | None = None,
        message_bus: Any = None,
    ):
        milvus = (config or {}).get("milvus")
        neo4j = (config or {}).get("neo4j")
        reranker = (config or {}).get("reranker")

        self._skills = {
            "ConceptRetrieval":        ConceptRetrieval(
                llm=llm,
                milvus=milvus,
                neo4j=neo4j,
                reranker=reranker,
            ),
            "EducationalExplanation":  EducationalExplanation(llm=llm),
            "AnswerFormatting":         AnswerFormatting(llm=llm),
        }
        self._shared_tools = create_shared_memory_tools(memory_service)

        super().__init__(
            agent_id=AgentID.THEORY,
            memory_service=memory_service,
            llm=llm,
            config=config or {},
            message_bus=message_bus,
        )

        logger.info("[TheoryAgent] Initialized")

    def _register_tools(self) -> dict[str, dict[str, Any]]:
        return self._shared_tools

    def _register_skills(self) -> dict[str, Any]:
        return self._skills

    async def run(self, input: dict[str, Any], gs: GlobalState) -> dict[str, Any]:
        context: dict = input.get("context", {})
        conv_id: str = context.get("conv_id", "")
        message: str = context.get("original_message", "")
        language: str = context.get("language", "vi")

        local: TheoryLocalState = {
            "goal": "retrieve_and_explain_theory",
            "step": "start",
            "done": False,
            "query": message,
        }
        self.local_memory.update(local)

        self.info(f"Processing theory request: '{message[:50]}...'")
        emitter.emit_agent_started(self.agent_id, input_summary=message[:100])

        try:
            # 1. Retrieve concepts
            local["step"] = "retrieve_concepts"
            concepts = await self._skills["ConceptRetrieval"].retrieve(
                query=message,
                context=await self.memory_service.get_context(conv_id),
            )

            # 2. Generate explanation
            explanation = await self._skills["EducationalExplanation"].explain_multiple(
                concepts=concepts,
                question=message,
                language=language,
            )

            # 3. Format response
            formatted = await self._skills["AnswerFormatting"].format(
                explanation=explanation,
                concepts_used=[c.get("name", "") for c in concepts],
                language=language,
            )

            response_text = formatted["response"]

            # 4. Save to memory
            await self.memory_service.save_buffer(
                conv_id=conv_id,
                role="assistant",
                content=response_text,
                metadata={"agent": self.agent_id, "concepts": formatted.get("concepts", [])},
            )

            local["retrieved_count"] = len(concepts)
            local["concepts"] = concepts
            local["step"] = "completed"
            local["done"] = True
            self.local_memory.update(local)

            local["retrieved_count"] = len(concepts)
            local["concepts"] = concepts
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
                "concepts": formatted.get("concepts", []),
                "intent": "theory",
            }

        except RetrievalUnavailableError as e:
            self.error(f"TheoryAgent external retrieval unavailable: {e}")
            emitter.emit_agent_error(self.agent_id, str(e))
            gs["error"] = str(e)
            return {
                "response": "External theory retrieval chưa sẵn sàng hoặc không có dữ liệu. Vui lòng ingest/index dữ liệu trước.",
                "agent_id": self.agent_id,
                "skills_used": [],
                "intent": "theory",
                "error": str(e),
            }
        except Exception as e:
            self.error(f"TheoryAgent failed: {e}")
            emitter.emit_agent_error(self.agent_id, str(e))
            gs["error"] = str(e)
            return {
                "response": "TheoryAgent gặp lỗi nội bộ khi xử lý yêu cầu.",
                "agent_id": self.agent_id,
                "skills_used": [],
                "intent": "theory",
                "error": str(e),
            }
