"""
DiagnosticRetrieval skill — external-only retrieval.
No local DSM KB fallback.
"""
from __future__ import annotations

from typing import Any

from ai.shared.exceptions import RetrievalUnavailableError
from ai.shared.prompts import load_prompt
from ai.agents.diagnostic.tools.retrieval_tools import (
    embed_diagnostic_query,
    milvus_search_diagnostic,
    neo4j_diagnostic_names,
    rerank_diagnostic,
)


class DiagnosticRetrieval:
    """Retrieve diagnostic candidates from external RAG only."""

    SYSTEM_PROMPT = load_prompt("diagnostic.skills.diagnostic_retrieval")

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
        slots: dict[str, Any],
        conv_id: str | None = None,
        agent_state: dict[str, Any] | None = None,
        collection: str = "mental_health_diagnostic",
    ) -> dict[str, Any]:
        if agent_state is not None:
            agent_state["step"] = "retrieval"
            agent_state["goal"] = "find_diagnostic_candidates"

        if self._milvus is None:
            raise RetrievalUnavailableError(
                message="Diagnostic retrieval unavailable: Milvus client is not configured",
                agent_id="diagnostic",
                operation="diagnostic_retrieve",
            )

        state = agent_state or {}
        query_vector = embed_diagnostic_query(state, query)

        # ── Step 1: Retrieve disorder candidates ────────────────────────────
        hits = milvus_search_diagnostic(state, self._milvus, query_vector, top_k=10)

        if not hits:
            raise RetrievalUnavailableError(
                message="Diagnostic retrieval unavailable: no data found in external vector index",
                agent_id="diagnostic",
                operation="diagnostic_retrieve",
                context={"query": query},
            )

        names = {}
        if self._neo4j is not None:
            try:
                node_ids = [h.get("node_id") for h in hits if "node_id" in h]
                names = neo4j_diagnostic_names(state, self._neo4j, node_ids)
            except Exception:
                pass

        candidates: list[dict[str, Any]] = []
        for h in hits:
            nid = h.get("node_id")
            disorder_name = names.get(nid, f"Diagnostic Node {nid}")
            candidates.append(
                {
                    "disorder": disorder_name,
                    "disorder_vi": disorder_name,
                    "criteria": ["Externally retrieved candidate"],
                    "score": h.get("score", 0.0),
                    "min_symptoms": 0,
                    "must_have": [],
                    "text": h.get("text", f"{disorder_name} diagnostic candidate"),
                    "source": "milvus+neo4j" if self._neo4j is not None else "milvus",
                }
            )

        # ── Step 2: Retrieve DSM-5 diagnostic chunks (criteria, symptoms, causes) ─
        # Search again with different query to get criteria text
        criteria_query = f"{query} DSM-5 criteria symptoms causes diagnostic"
        criteria_vector = embed_diagnostic_query(state, criteria_query)
        criteria_hits = milvus_search_diagnostic(state, self._milvus, criteria_vector, top_k=10)

        diagnostic_chunks: list[str] = []
        seen = set()
        for h in criteria_hits:
            text = h.get("text", "")
            node_id = h.get("node_id")
            if text and text not in seen and node_id not in seen:
                seen.add(node_id)
                diagnostic_chunks.append(text)

        if self._reranker is not None:
            try:
                candidates = rerank_diagnostic(state, self._reranker, query, candidates)
            except Exception:
                pass

        for c in candidates:
            c.pop("text", None)

        if not candidates:
            raise RetrievalUnavailableError(
                message="Diagnostic retrieval unavailable: candidates empty after external processing",
                agent_id="diagnostic",
                operation="diagnostic_retrieve",
            )

        if agent_state is not None:
            agent_state["candidates_count"] = len(candidates)
            agent_state["step"] = "completed"
            agent_state["done"] = True

        return {
            "candidates": candidates[:5],
            "diagnostic_chunks": diagnostic_chunks[:5],
        }
