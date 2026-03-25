"""
ConceptRetrieval skill — external-only retrieval.
No local KB fallback.
"""
from __future__ import annotations

from typing import Any

from ai.shared.exceptions import RetrievalUnavailableError
from ai.shared.prompts import load_prompt
from ai.agents.theory.tools.retrieval_tools import (
    embed_query,
    milvus_search,
    neo4j_node_names,
    rerank_candidates,
)


class ConceptRetrieval:
    """Retrieve psychology concepts from external RAG only."""

    SYSTEM_PROMPT = load_prompt("theory.skills.concept_retrieval")

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
        query: str,
        context: str = "",
        agent_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if agent_state is not None:
            agent_state["step"] = "retrieval"
            agent_state["goal"] = "find_concepts"

        if self._milvus is None:
            raise RetrievalUnavailableError(
                message="Concept retrieval unavailable: Milvus client is not configured",
                agent_id="theory",
                operation="concept_retrieve",
            )

        state = agent_state or {}
        query_vector = embed_query(state, query)
        hits = milvus_search(state, self._milvus, query_vector, top_k=8)

        if not hits:
            raise RetrievalUnavailableError(
                message="Concept retrieval unavailable: no data found in external vector index",
                agent_id="theory",
                operation="concept_retrieve",
                context={"query": query},
            )

        names = {}
        if self._neo4j is not None:
            try:
                node_ids = [h.get("node_id") for h in hits if "node_id" in h]
                names = neo4j_node_names(state, self._neo4j, node_ids)
            except Exception:
                pass

        candidates: list[dict[str, Any]] = []
        for hit in hits:
            nid = hit.get("node_id")
            name = names.get(nid, f"Concept Node {nid}")
            candidates.append(
                {
                    "name": name,
                    "definition": f"Retrieved externally from node {nid}",
                    "source": "milvus+neo4j" if self._neo4j is not None else "milvus",
                    "score": hit.get("score", 0.0),
                    "text": f"{name} Retrieved externally from node {nid}",
                }
            )

        if self._reranker is not None:
            try:
                candidates = rerank_candidates(state, self._reranker, query, candidates)
            except Exception:
                pass

        for c in candidates:
            c.pop("text", None)

        if not candidates:
            raise RetrievalUnavailableError(
                message="Concept retrieval unavailable: candidates empty after external processing",
                agent_id="theory",
                operation="concept_retrieve",
            )

        if agent_state is not None:
            agent_state["retrieved_count"] = len(candidates)
            agent_state["concepts"] = candidates
            agent_state["step"] = "completed"
            agent_state["done"] = True

        return candidates[:2]
