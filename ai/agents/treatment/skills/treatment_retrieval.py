"""
TreatmentRetrieval skill — retrieves evidence-based treatment options.
Hybrid: external RAG (Milvus/Neo4j/Cohere) when available, in-memory fallback otherwise.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)


def _norm(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(c) != "Mn"
    )


def _in(query: str, text: str) -> bool:
    q_words = set(_norm(w) for w in re.findall(r"\w+", query))
    t_norm = _norm(text)
    return any(qw in t_norm for qw in q_words)


TREATMENT_KB: dict[str, dict[str, Any]] = {
    "cbt": {
        "name": "Liệu pháp nhận thức hành vi (CBT)",
        "description": "CBT tập trung vào mối quan hệ giữa suy nghĩ, cảm xúc và hành vi.",
        "evidence_level": "Rất cao (A)",
        "suitable_for": ["Trầm cảm", "Lo âu", "PTSD", "Panic"],
        "techniques": ["Cognitive restructuring", "Exposure", "Behavioral activation"],
    },
    "dbt": {
        "name": "Liệu pháp hành vi biện chứng (DBT)",
        "description": "DBT dành cho điều hòa cảm xúc, đặc biệt ở ca tự hại/BPD.",
        "evidence_level": "Cao (A)",
        "suitable_for": ["BPD", "Tự hại", "Rối loạn cảm xúc"],
        "techniques": ["Mindfulness", "Distress tolerance", "Emotion regulation"],
    },
    "ssri": {
        "name": "Thuốc chống trầm cảm (SSRI)",
        "description": "Nhóm thuốc thường dùng cho trầm cảm/lo âu, cần bác sĩ kê đơn.",
        "evidence_level": "Cao (A)",
        "suitable_for": ["Trầm cảm", "Lo âu", "OCD"],
        "examples": ["Sertraline", "Escitalopram", "Fluoxetine"],
    },
    "mindfulness": {
        "name": "Liệu pháp chánh niệm (MBCT/MBSR)",
        "description": "Kết hợp chánh niệm giúp giảm lo âu và phòng tái phát trầm cảm.",
        "evidence_level": "Cao (A)",
        "suitable_for": ["Stress", "Lo âu", "Trầm cảm tái phát"],
    },
}


class TreatmentRetrieval:
    """Retrieve treatment options from external RAG or fallback KB."""

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

    async def retrieve(self, condition: str, context: str = "") -> list[dict[str, Any]]:
        external = self._external_rag(condition)
        if external:
            return external[:3]

        results = self._score_in_memory(condition)
        if not results and self._llm:
            results = await self._llm_fallback(condition)

        results = self._rerank(condition, results)
        return results[:3]

    def _external_rag(self, condition: str) -> list[dict[str, Any]]:
        if self._milvus is None:
            return []

        try:
            from ai.shared.rag.vectors.embeddings import encode_text
            query_vector = encode_text(condition)
            hits = self._milvus.search(query_vector, top_k=8, threshold=0.0)
            if not hits:
                return []

            names = {}
            if self._neo4j:
                node_ids = [h["node_id"] for h in hits if "node_id" in h]
                names = self._neo4j.get_node_names(node_ids)

            out = []
            for h in hits:
                nid = h.get("node_id")
                out.append(
                    {
                        "name": names.get(nid, f"Treatment Node {nid}"),
                        "description": "Retrieved from vector graph search",
                        "evidence_level": "Unknown",
                        "source": "milvus+neo4j" if self._neo4j else "milvus",
                        "score": h.get("score", 0.0),
                    }
                )
            return out
        except Exception as e:
            logger.warning("[TreatmentRetrieval] external RAG failed: %s", e)
            return []

    def _score_in_memory(self, condition: str) -> list[dict[str, Any]]:
        scored = []
        for _, treatment in TREATMENT_KB.items():
            score = 0
            if _in(condition, treatment.get("name", "")):
                score += 3
            for s in treatment.get("suitable_for", []):
                if _in(condition, s):
                    score += 2
            if score > 0:
                scored.append((score, treatment))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored]

    async def _llm_fallback(self, condition: str) -> list[dict[str, Any]]:
        try:
            prompt = f"""What treatment area matches this condition?
Condition: {condition}
Reply one keyword: cbt | dbt | ssri | mindfulness"""
            key = (await self._llm.generate(prompt)).strip().lower()
            for k, v in TREATMENT_KB.items():
                if k in key:
                    return [v]
        except Exception as e:
            logger.warning("[TreatmentRetrieval] LLM fallback failed: %s", e)
        return []

    def _rerank(self, query: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self._reranker or not items:
            return items
        try:
            docs = [{**it, "text": f"{it.get('name','')} {it.get('description','')}"} for it in items]
            reranked = self._reranker.rerank(
                query=query,
                candidates=docs,
                top_k=min(5, len(docs)),
                candidates_key="text",
            )
            for d in reranked:
                d.pop("text", None)
            return reranked
        except Exception as e:
            logger.warning("[TreatmentRetrieval] rerank failed: %s", e)
            return items
