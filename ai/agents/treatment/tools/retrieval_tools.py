"""Tool functions for Treatment retrieval skill."""
from __future__ import annotations

from typing import Any

from ai.shared.agent_based.tooling import tool


@tool(name="embed_condition", description="Encode treatment condition query into embedding vector")
def embed_condition(agent_state: dict, condition: str) -> list[float]:
    from ai.shared.rag.vectors.embeddings import encode_text
    agent_state["step"] = "embedding"
    return encode_text(condition)


@tool(name="milvus_search_treatment", description="Search Milvus for treatment nodes")
def milvus_search_treatment(
    agent_state: dict,
    milvus_client: Any,
    query_vector: list[float],
    top_k: int = 8,
) -> list[dict[str, Any]]:
    agent_state["step"] = "milvus_search"
    return milvus_client.search(query_vector, top_k=top_k, threshold=0.0)


@tool(name="neo4j_treatment_names", description="Resolve treatment node names from Neo4j")
def neo4j_treatment_names(
    agent_state: dict,
    neo4j_client: Any,
    node_ids: list[int],
) -> dict[int, str]:
    agent_state["step"] = "neo4j_enrichment"
    return neo4j_client.get_node_names(node_ids)


@tool(name="rerank_treatments", description="Rerank treatment candidates")
def rerank_treatments(
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
