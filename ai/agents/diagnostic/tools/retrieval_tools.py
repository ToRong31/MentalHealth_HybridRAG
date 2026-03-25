"""Tool functions for Diagnostic retrieval skill."""
from __future__ import annotations

from typing import Any

from ai.shared.agent_based.tooling import tool


@tool(name="embed_diagnostic_query", description="Encode diagnostic query into embedding vector")
def embed_diagnostic_query(agent_state: dict, query: str) -> list[float]:
    from ai.shared.rag.vectors.embeddings import encode_text
    agent_state["step"] = "embedding"
    return encode_text(query)


@tool(name="milvus_search_diagnostic", description="Search Milvus for diagnostic nodes")
def milvus_search_diagnostic(
    agent_state: dict,
    milvus_client: Any,
    query_vector: list[float],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    agent_state["step"] = "milvus_search"
    return milvus_client.search(query_vector, top_k=top_k, threshold=0.0)


@tool(name="neo4j_diagnostic_names", description="Resolve diagnostic node names from Neo4j")
def neo4j_diagnostic_names(
    agent_state: dict,
    neo4j_client: Any,
    node_ids: list[int],
) -> dict[int, str]:
    agent_state["step"] = "neo4j_enrichment"
    return neo4j_client.get_node_names(node_ids)


@tool(name="rerank_diagnostic", description="Rerank diagnostic candidates")
def rerank_diagnostic(
    agent_state: dict,
    reranker: Any,
    query: str,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    agent_state["step"] = "reranking"
    return reranker.rerank(
        query=query,
        candidates=candidates,
        top_k=min(5, len(candidates)),
        candidates_key="text",
    )
