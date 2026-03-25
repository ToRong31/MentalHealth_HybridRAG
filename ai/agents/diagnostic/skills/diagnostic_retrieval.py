"""
DiagnosticRetrieval skill — hybrid search over DSM-5 diagnostic KB.
"""
from __future__ import annotations

import logging
import unicodedata
import re
from typing import Any

logger = logging.getLogger(__name__)

# In-memory DSM-5 diagnostic KB (replace with Milvus + Neo4j RAG in production)
DSM5_KB: list[dict[str, Any]] = [
    {
        "disorder": "Major Depressive Disorder",
        "disorder_vi": "Rối loạn trầm cảm nặng",
        "criteria": [
            "Tâm trạng trầm cảm hầu hết thời gian, hầu như mỗi ngày",
            "Mất hứng thú hoặc quan tâm (anhedonia)",
            "Thay đổi cân nặng / ăn uống",
            "Mất ngủ hoặc ngủ nhiều",
            "Kích động hoặc ức chế tâm vận",
            "Mệt mỏi, mất năng lượng",
            "Cảm giác vô giá trị hoặc tội lỗi quá mức",
            "Khó tập trung hoặc do dự",
            "Ý nghĩ tự sát",
        ],
        "min_symptoms": 5,
        "duration": "ít nhất 2 tuần",
        "must_have": ["anhedonia", "sad"],
        "keywords": ["tram cam", "trầm cảm", "depression", "depressed", "buon", "sad"],
    },
    {
        "disorder": "Generalized Anxiety Disorder",
        "disorder_vi": "Rối loạn lo âu tổng quát",
        "criteria": [
            "Lo âu và lo lắng quá mức, nhiều ngày trong tuần trong ít nhất 6 tháng",
            "Khó kiểm soát sự lo âu",
            "≥3 triệu chứng (với trẻ: 1): bồn chồn, mệt mỏi, khó tập trung, cáu kỉnh, căng cơ, rối loạn giấc ngủ",
        ],
        "min_symptoms": 3,
        "duration": "ít nhất 6 tháng",
        "must_have": ["anxiety", "lo au", "worry"],
        "keywords": ["lo au", "lo âu", "anxiety", "anxious", "lo lắng", "worry"],
    },
    {
        "disorder": "Panic Disorder",
        "disorder_vi": "Rối loạn hoảng sợ",
        "criteria": [
            "Cơn hoảng sợ tái diễn, không dự đoán được",
            "Lo âu kéo dài về việc có thêm cơn hoảng sợ",
            "Thay đổi hành vi liên quan đến cơn hoảng (tránh né, v.v.)",
        ],
        "min_symptoms": 4,
        "duration": "tái diễn",
        "must_have": ["panic", "hoang", "đau ngực"],
        "keywords": ["hoảng sợ", "hoang", "panic", "đau ngực", "tim đập nhanh"],
    },
    {
        "disorder": "Acute Stress Disorder",
        "disorder_vi": "Rối loạn stress cấp tính",
        "criteria": [
            "Phơi nhiễm với sự kiện gây chấn thương (thực tế hoặc đe dọa)",
            "≥9 triệu chứng từ 5 nhóm: intrusive, negative mood, dissociative, avoidance, arousal",
            "Kéo dài 3 ngày đến 1 tháng",
        ],
        "min_symptoms": 9,
        "duration": "3 ngày – 1 tháng",
        "must_have": ["trauma", "chấn thương", "stress"],
        "keywords": ["sang chấn", "trauma", "chấn thương", "stress", "căng thẳng"],
    },
    {
        "disorder": "Adjustment Disorder",
        "disorder_vi": "Rối loạn thích nghi",
        "criteria": [
            "Phản ứng cảm xúc hoặc hành vi tiêu cực đáng kể",
            "Phát triển trong vòng 3 tháng sau sự kiện căng thẳng",
            "Các triệu chứng không đáp ứng tiêu chuẩn của rối loạn khác",
            "Các triệu chứng không kéo dài quá 6 tháng sau sự kiện",
        ],
        "min_symptoms": 1,
        "duration": "dưới 6 tháng",
        "must_have": [],
        "keywords": ["thích nghi", "adjustment", "đáp ứng căng thẳng", "stress response"],
    },
]


def _norm(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(c) != "Mn"
    )


def _match(query: str, keywords: list[str]) -> int:
    """Count keyword matches. Returns 0 if no match."""
    q_norm = _norm(query)
    return sum(1 for kw in keywords if _norm(kw) in q_norm)


class DiagnosticRetrieval:
    """Hybrid search over DSM-5 diagnostic KB + Milvus + Neo4j + Cohere."""

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

    async def search(
        self,
        query: str,
        slots: dict[str, Any],
        collection: str = "mental_health_diagnostic",
    ) -> list[dict[str, Any]]:
        """
        Hybrid retrieval pipeline:
          1) Milvus vector search (if available)
          2) Neo4j subgraph expansion (if available)
          3) In-memory DSM5 keyword fallback
          4) Cohere reranking (if available)
        """
        candidates = []

        # ── Step 1: Try Milvus vector search (best-effort) ───────────────
        milvus_hits = []
        if self._milvus is not None:
            try:
                from ai.shared.rag.vectors.embeddings import encode_text
                query_vector = encode_text(query)
                milvus_hits = self._milvus.search(query_vector, top_k=10, threshold=0.0)
                logger.debug("[DiagnosticRetrieval] Milvus hits: %d", len(milvus_hits))
            except Exception as e:
                logger.warning("[DiagnosticRetrieval] Milvus search failed: %s", e)

        # ── Step 2: Expand Neo4j subgraph from Milvus node_ids ───────────
        graph_node_names = {}
        if self._neo4j is not None and milvus_hits:
            try:
                node_ids = [h["node_id"] for h in milvus_hits if "node_id" in h]
                graph_node_names = self._neo4j.get_node_names(node_ids)
                logger.debug("[DiagnosticRetrieval] Neo4j names: %d", len(graph_node_names))
            except Exception as e:
                logger.warning("[DiagnosticRetrieval] Neo4j query failed: %s", e)

        # ── Step 3: In-memory DSM5 fallback scoring ────────────────────────
        # Always run this so system works without infra.

        for disorder in DSM5_KB:
            score = _match(query, disorder.get("keywords", []))

            # Boost score if slots match disorder criteria
            emotion = slots.get("emotion", "")
            if emotion:
                emotion_kws = disorder.get("keywords", [])
                if _norm(emotion) in _norm(" ".join(emotion_kws)):
                    score += 2

            # Duration match
            duration = slots.get("duration", "")
            if duration and duration in disorder.get("duration", "").lower():
                score += 1

            if score > 0:
                candidates.append({
                    "disorder": disorder["disorder"],
                    "disorder_vi": disorder["disorder_vi"],
                    "criteria": disorder["criteria"],
                    "score": score,
                    "min_symptoms": disorder["min_symptoms"],
                    "must_have": disorder["must_have"],
                })

        # Sort by score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)

        # ── Step 4: Cohere rerank (if available) ───────────────────────────
        if self._reranker is not None and candidates:
            try:
                # Build text field for reranker
                for c in candidates:
                    c["text"] = (
                        f"{c['disorder_vi']} {c['disorder']} "
                        + " ".join(c.get("criteria", [])[:3])
                    )
                candidates = self._reranker.rerank(
                    query=query,
                    candidates=candidates,
                    top_k=5,
                    candidates_key="text",
                )
                # Cleanup helper text
                for c in candidates:
                    c.pop("text", None)
            except Exception as e:
                logger.warning("[DiagnosticRetrieval] Rerank failed: %s", e)

        logger.info(f"[DiagnosticRetrieval] Found {len(candidates)} candidates")
        return candidates[:5] if candidates else []
