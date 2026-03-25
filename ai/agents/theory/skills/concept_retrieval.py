"""
ConceptRetrieval skill — retrieves psychological concepts.
Hybrid: external RAG (Milvus/Neo4j/Cohere) when available, in-memory fallback otherwise.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# In-memory psychology KB fallback
PSYCHOLOGY_KB: dict[str, dict[str, Any]] = {
    "trauma": {
        "name": "Sang chấn tâm lý (Trauma)",
        "definition": "Sang chấn tâm lý là phản ứng của cơ thể và tâm trí trước một sự kiện gây tổn thương.",
        "symptoms": ["Flashbacks", "Mất ngủ", "Né tránh", "Hypervigilance"],
    },
    "stress": {
        "name": "Lý thuyết Stress (Selye)",
        "definition": "Stress là phản ứng không đặc hiệu của cơ thể với áp lực.",
        "stages": ["Alarm", "Resistance", "Exhaustion"],
    },
    "lo_au": {
        "name": "Rối loạn Lo âu",
        "definition": "Lo âu là cảm giác lo lắng kéo dài, quá mức so với mối đe dọa thực tế.",
        "theories": ["Sinh học", "Nhận thức", "Hành vi"],
    },
    "triet_ly_nhan_thuc": {
        "name": "Lý thuyết nhận thức",
        "definition": "Cảm xúc/hành vi bị ảnh hưởng bởi cách diễn giải sự kiện.",
        "key_figures": ["Aaron Beck", "Albert Ellis"],
    },
}


class ConceptRetrieval:
    """Retrieve psychology concepts from external RAG or fallback KB."""

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

    async def retrieve(self, query: str, context: str = "") -> list[dict[str, Any]]:
        """Main retrieval entry point."""
        # 1) external RAG best-effort
        external = self._external_rag(query)
        if external:
            return external[:2]

        # 2) in-memory fallback
        results = self._score_in_memory(query)

        # 3) llm fallback when no keyword hit
        if not results and self._llm:
            results = await self._llm_fallback(query)

        concepts = results[:3]

        # 4) optional rerank
        concepts = self._rerank(query, concepts)

        return concepts[:2]

    def _external_rag(self, query: str) -> list[dict[str, Any]]:
        """Best-effort external retrieval from Milvus + Neo4j."""
        if self._milvus is None:
            return []

        try:
            from ai.shared.rag.vectors.embeddings import encode_text
            query_vector = encode_text(query)
            milvus_hits = self._milvus.search(query_vector, top_k=8, threshold=0.0)
            if not milvus_hits:
                return []

            # If Neo4j available, enrich names
            if self._neo4j:
                node_ids = [h["node_id"] for h in milvus_hits if "node_id" in h]
                names = self._neo4j.get_node_names(node_ids)
            else:
                names = {}

            concepts = []
            for hit in milvus_hits:
                nid = hit.get("node_id")
                name = names.get(nid, f"Concept Node {nid}")
                concepts.append(
                    {
                        "name": name,
                        "definition": f"Retrieved from vector node {nid}",
                        "source": "milvus+neo4j" if self._neo4j else "milvus",
                        "score": hit.get("score", 0.0),
                    }
                )
            return concepts

        except Exception as e:
            logger.warning("[ConceptRetrieval] external RAG failed: %s", e)
            return []

    def _score_in_memory(self, query: str) -> list[dict[str, Any]]:
        query_lower = query.lower()
        scored = []
        for _, concept in PSYCHOLOGY_KB.items():
            score = 0
            if any(w in query_lower for w in concept["name"].lower().split()):
                score += 2
            if any(w in query_lower for w in concept["definition"].lower().split()[:6]):
                score += 1
            if score > 0:
                scored.append((score, concept))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored]

    async def _llm_fallback(self, query: str) -> list[dict[str, Any]]:
        try:
            prompt = f"""What psychology topic is this question about?
Question: {query}
Reply with one topic keyword only."""
            topic = (await self._llm.generate(prompt)).strip().lower()
            for key, concept in PSYCHOLOGY_KB.items():
                if key in topic or topic in key:
                    return [concept]
        except Exception as e:
            logger.warning("[ConceptRetrieval] LLM fallback failed: %s", e)
        return []

    def _rerank(self, query: str, concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self._reranker or not concepts:
            return concepts

        try:
            items = [{**c, "text": f"{c.get('name','')} {c.get('definition','')}"} for c in concepts]
            reranked = self._reranker.rerank(
                query=query,
                candidates=items,
                top_k=min(3, len(items)),
                candidates_key="text",
            )
            for c in reranked:
                c.pop("text", None)
            return reranked
        except Exception as e:
            logger.warning("[ConceptRetrieval] rerank failed: %s", e)
            return concepts
