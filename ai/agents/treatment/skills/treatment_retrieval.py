"""
TreatmentRetrieval skill — external-only retrieval.
No local KB fallback.
"""
from __future__ import annotations

from typing import Any

from ai.shared.exceptions import RetrievalUnavailableError
from ai.shared.prompts import load_prompt
from ai.agents.treatment.tools.retrieval_tools import (
    embed_condition,
    milvus_search_treatment,
    neo4j_treatment_names,
    rerank_treatments,
)


class TreatmentRetrieval:
    """Retrieve treatment candidates from external RAG only."""

    SYSTEM_PROMPT = load_prompt("treatment.skills.treatment_retrieval")

    def __init__(
        self,
        llm: Any = None,
        milvus: Any = None,
        neo4j: Any = None,
        reranker: Any = None,
    ):
        self._llm = llm
        self._milvus = milvus
        self._neo4j = neo4j
        self._reranker = reranker

    async def retrieve(
        self,
        condition: str,
        context: str = "",
        agent_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if agent_state is not None:
            agent_state["step"] = "retrieval"
            agent_state["goal"] = "find_treatments"

        if self._milvus is None:
            raise RetrievalUnavailableError(
                message="Treatment retrieval unavailable: Milvus client is not configured",
                agent_id="treatment",
                operation="treatment_retrieve",
            )

        state = agent_state or {}
        query_vector = embed_condition(state, condition)
        hits = milvus_search_treatment(state, self._milvus, query_vector, top_k=8)

        if not hits:
            raise RetrievalUnavailableError(
                message="Treatment retrieval unavailable: no data found in external vector index",
                agent_id="treatment",
                operation="treatment_retrieve",
                context={"condition": condition},
            )

        names = {}
        if self._neo4j is not None:
            try:
                node_ids = [h.get("node_id") for h in hits if "node_id" in h]
                names = neo4j_treatment_names(state, self._neo4j, node_ids)
            except Exception:
                pass

        candidates: list[dict[str, Any]] = []
        for h in hits:
            nid = h.get("node_id")
            name = names.get(nid, f"Treatment Node {nid}")
            candidates.append(
                {
                    "name": name,
                    "description": "Retrieved externally from treatment retrieval graph",
                    "evidence_level": "Unknown",
                    "source": "milvus+neo4j" if self._neo4j is not None else "milvus",
                    "score": h.get("score", 0.0),
                    "text": f"{name} Retrieved externally from treatment retrieval graph",
                }
            )

        if self._reranker is not None:
            try:
                candidates = rerank_treatments(state, self._reranker, condition, candidates)
            except Exception:
                pass

        for c in candidates:
            c.pop("text", None)

        if not candidates:
            raise RetrievalUnavailableError(
                message="Treatment retrieval unavailable: candidates empty after external processing",
                agent_id="treatment",
                operation="treatment_retrieve",
            )

        if agent_state is not None:
            agent_state["retrieved_count"] = len(candidates)
            agent_state["step"] = "completed"
            agent_state["done"] = True

        return candidates[:3]
