"""
ClinicalReasoning skill — LLM-driven DSM-5 diagnostic evaluation.

Pipeline:
  1. Retrieve conversation context from MemoryService
  2. Receive diagnostic candidates + DSM-5 chunks from DiagnosticRetrieval
  3. LLM evaluates: do the user's symptoms match any disorder criteria?
  4. Output: has_disorder (binary), diagnosis, confidence, reasoning, basis, differential, recommendation

Prompts loaded from: ai/agents/diagnostic/skills/prompts/clinical_reasoning.yaml
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ai.shared.prompts import load_prompt_meta

logger = logging.getLogger(__name__)

# Load skill metadata from YAML
_SKILL_META = load_prompt_meta("diagnostic.skills.clinical_reasoning")
_SYSTEM_PROMPT = _SKILL_META["system"]
_EXAMPLES_BLOCK = json.dumps(
    _SKILL_META.get("examples", []), ensure_ascii=False, indent=2
)


class ClinicalReasoning:
    """
    LLM-driven clinical reasoning for DSM-5 diagnostic evaluation.

    Receives:
      - slots: accumulated diagnostic slots (25 slots, 8 required)
      - candidates: disorder candidates from DiagnosticRetrieval
      - diagnostic_chunks: DSM-5 criteria text from Milvus
      - conv_id: to retrieve conversation context from MemoryService
      - memory_service: MemoryService instance

    Returns:
      - has_disorder: bool
      - diagnosis: str | None
      - confidence: float 0.0–1.0
      - reasoning: str (clinical reasoning in Vietnamese)
      - basis: list[str] (DSM criteria matched)
      - differential: list[dict]
      - recommendation: str
    """

    def __init__(
        self,
        llm: Any = None,
        memory_service: Any = None,
    ):
        self._llm = llm
        self._memory_service = memory_service

    async def reason(
        self,
        slots: dict[str, Any],
        candidates: list[dict[str, Any]],
        diagnostic_chunks: list[str],
        conv_id: str = "",
        context: str = "",
        agent_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate user symptoms against disorder candidates using LLM.

        Parameters
        ----------
        slots : dict
            Accumulated 25-slot diagnostic data.
        candidates : list[dict]
            Disorder candidates from DiagnosticRetrieval.
        diagnostic_chunks : list[str]
            DSM-5 criteria/symptoms/causes text from Milvus retrieval.
        conv_id : str
            Conversation ID — used to retrieve context from MemoryService.
        context : str
            Fallback context string if MemoryService unavailable.
        agent_state : dict | None
            Agent state for instrumentation.

        Returns
        -------
        {
            "has_disorder": bool,
            "diagnosis": str | None,
            "confidence": float,
            "reasoning": str,
            "basis": list[str],
            "differential": list[dict],
            "recommendation": str,
        }
        """
        if agent_state is not None:
            agent_state["step"] = "clinical_reasoning"
            agent_state["goal"] = "evaluate_disorder"

        # ── 1. Get conversation context from MemoryService ──────────────────
        conversation_context = context
        if self._memory_service and conv_id:
            try:
                conversation_context = await self._memory_service.get_context(conv_id)
            except Exception as e:
                logger.warning(
                    f"[ClinicalReasoning] MemoryService.get_context failed: {e}"
                )

        # ── 2. Fallback if no candidates ───────────────────────────────────
        if not candidates:
            return self._no_candidates_result(slots, agent_state)

        # ── 3. Build LLM prompt ───────────────────────────────────────────
        prompt = self._build_prompt(
            slots=slots,
            candidates=candidates,
            diagnostic_chunks=diagnostic_chunks,
            conversation_context=conversation_context,
        )

        # ── 4. Call LLM ───────────────────────────────────────────────────
        if self._llm is None:
            # Fallback: score-based reasoning without LLM
            return self._score_based_reasoning(slots, candidates, agent_state)

        try:
            raw_response = await self._llm.generate(prompt)
            return self._parse_llm_response(raw_response, agent_state)
        except json.JSONDecodeError as e:
            logger.warning(
                f"[ClinicalReasoning] LLM JSON parse failed: {e}, falling back to score-based"
            )
            return self._score_based_reasoning(slots, candidates, agent_state)
        except Exception as e:
            logger.error(f"[ClinicalReasoning] LLM call failed: {e}")
            return self._score_based_reasoning(slots, candidates, agent_state)

    # ── Prompt builder ─────────────────────────────────────────────────────────

    def _build_prompt(
        self,
        slots: dict[str, Any],
        candidates: list[dict[str, Any]],
        diagnostic_chunks: list[str],
        conversation_context: str,
    ) -> str:
        # Format slots for readability
        filled_slots = {k: v for k, v in slots.items() if v is not None and v != ""}
        slots_str = json.dumps(filled_slots, ensure_ascii=False, indent=2)

        # Format candidates
        candidate_names = [
            c.get("disorder", c.get("disorder_vi", "Unknown")) for c in candidates
        ]
        candidates_str = ", ".join(candidate_names) if candidate_names else "None"

        # Format diagnostic chunks
        chunks_str = (
            "\n\n".join(
                f"--- Chunk {i+1} ---\n{chunk}"
                for i, chunk in enumerate(diagnostic_chunks[:8])
            )
            if diagnostic_chunks
            else "No diagnostic chunks available."
        )

        # Conversation context
        ctx_str = (
            conversation_context if conversation_context else "No prior conversation."
        )

        prompt = f"""\
{_SYSTEM_PROMPT}

EXAMPLES:
{_EXAMPLES_BLOCK}

USER INFORMATION:
=================
Query: (current message — see conversation)

Extracted Symptoms (Slots):
{slots_str}

Recent Conversation:
{ctx_str}

=======================================
DIAGNOSTIC KNOWLEDGE (READ CAREFULLY):
=======================================
{chunks_str}
=======================================

CANDIDATE DISORDERS TO EVALUATE:
{candidates_str}

EVALUATION STEPS:

1. IDENTIFY all candidate disorders from the list above.

2. FOR EACH CANDIDATE DISORDER:
   - Extract the diagnostic criteria/symptoms from the provided chunks.
   - Compare with user's symptoms (slots + conversation context).
   - Count how many criteria match.
   - Calculate match percentage.

3. DECIDE "has_disorder":
   - true: User meets enough criteria for a specific disorder (usually ≥50% of criteria + clinically significant impairment).
   - false: User does NOT meet criteria for any disorder; symptoms are subclinical/normal stress.

4. SELECT the disorder with HIGHEST match percentage.
   - If no disorder meets criteria → has_disorder=false.

5. ASSIGN CONFIDENCE SCORE:
   - >0.75: User CLEARLY meets most diagnostic criteria.
   - 0.50–0.75: User meets some criteria but not complete.
   - <0.50: User has few matching symptoms, criteria NOT met.
   - <0.30: Likely no disorder → has_disorder=false.

6. WRITE detailed reasoning explaining:
   - Which specific user symptoms you identified.
   - Which DSM-5 criteria they match (cite specific criteria).
   - Why this disorder has highest match among candidates.
   - Why you gave this confidence score.
   - Why has_disorder=true/false.

7. LIST basis: specific DSM criteria matched by user symptoms.

NOW EVALUATE AND RESPOND WITH ONLY VALID JSON:
"""
        return prompt

    # ── Response parser ────────────────────────────────────────────────────────

    def _parse_llm_response(
        self,
        raw: str,
        agent_state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        # Try to extract JSON from markdown code blocks first
        text = raw.strip()
        if text.startswith("```"):
            # Strip triple backtick wrapper
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        data = json.loads(text)

        result = {
            "has_disorder": bool(data.get("has_disorder", False)),
            "diagnosis": data.get("disease"),
            "confidence": float(data.get("confidence", 0.0)),
            "reasoning": data.get("reasoning", ""),
            "basis": data.get("basis", []),
            "differential": data.get("differential", []),
            "recommendation": data.get("recommendation", ""),
        }

        # Override diagnosis to None if has_disorder is false
        if not result["has_disorder"]:
            result["diagnosis"] = None

        if agent_state is not None:
            agent_state["has_disorder"] = result["has_disorder"]
            agent_state["diagnosis"] = result["diagnosis"]
            agent_state["confidence"] = result["confidence"]
            agent_state["step"] = "completed"
            agent_state["done"] = True

        return result

    # ── Score-based fallback (no LLM) ─────────────────────────────────────────

    def _score_based_reasoning(
        self,
        slots: dict[str, Any],
        candidates: list[dict[str, Any]],
        agent_state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Score-based fallback when LLM is unavailable.
        Uses retrieval scores + slot coverage to estimate confidence.
        """
        if not candidates:
            return self._no_candidates_result(slots, agent_state)

        top = candidates[0]
        top_score = top.get("score", 0.0)

        # Estimate confidence from retrieval score
        if top_score >= 4:
            confidence = 0.75
        elif top_score >= 3:
            confidence = 0.60
        elif top_score >= 2:
            confidence = 0.45
        else:
            confidence = 0.30

        # Penalty for insufficient slots
        filled = sum(1 for v in slots.values() if v is not None and v != "")
        if filled < 5:
            confidence *= 0.8

        # Determine has_disorder based on estimated confidence
        has_disorder = confidence >= 0.45

        # Build reasoning
        reasoning_parts = [
            f"Top candidate: {top.get('disorder_vi', top.get('disorder', 'Unknown'))} (score={top_score})",
            f"Filled slots: {filled}/25 (8 required)",
        ]
        if confidence >= 0.45:
            reasoning_parts.append(
                "Triệu chứng có đặc điểm liên quan đến rối loạn này. Confidence cao đủ để đề xuất."
            )
        else:
            reasoning_parts.append(
                "Triệu chứng chưa đủ để chẩn đoán rối loạn. Cần thêm thông tin."
            )

        differential = [
            {"disorder": c.get("disorder", ""), "confidence": c.get("score", 0.0)}
            for c in candidates[1:3]
        ]

        if confidence >= 0.45:
            recommendation = (
                "Các triệu chứng có đặc điểm liên quan đến rối loạn này. "
                "**Khuyến nghị:** Gặp bác sĩ tâm thần để được chẩn đoán chính xác."
            )
        else:
            recommendation = (
                "Triệu chứng chưa đủ để đưa ra chẩn đoán. "
                "**Khuyến nghị:** Theo dõi thêm và chia sẻ thêm về triệu chứng."
            )

        result = {
            "has_disorder": has_disorder,
            "diagnosis": top.get("disorder_vi") if has_disorder else None,
            "confidence": round(confidence, 2),
            "reasoning": "\n".join(reasoning_parts),
            "basis": [f"Retrieval score: {top_score}", f"Slot coverage: {filled}/25"],
            "differential": differential,
            "recommendation": recommendation,
        }

        if agent_state is not None:
            agent_state["has_disorder"] = result["has_disorder"]
            agent_state["diagnosis"] = result["diagnosis"]
            agent_state["confidence"] = result["confidence"]
            agent_state["step"] = "completed"
            agent_state["done"] = True

        return result

    # ── No candidates fallback ─────────────────────────────────────────────────

    def _no_candidates_result(
        self,
        slots: dict[str, Any],
        agent_state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        filled = sum(1 for v in slots.values() if v)

        result = {
            "has_disorder": False,
            "diagnosis": None,
            "confidence": 0.0,
            "reasoning": (
                f"Không tìm thấy rối loạn phù hợp với thông tin hiện tại. "
                f"Số slot đã thu thập: {filled}/25. "
                f"Cần thêm thông tin về triệu chứng để đề xuất chẩn đoán."
            ),
            "basis": [],
            "differential": [],
            "recommendation": (
                "Mình chưa tìm được rối loạn phù hợp với thông tin hiện tại. "
                "Bạn có thể chia sẻ thêm về triệu chứng, thời gian kéo dài, "
                "và ảnh hưởng đến cuộc sống không?"
            ),
        }

        if agent_state is not None:
            agent_state["has_disorder"] = False
            agent_state["diagnosis"] = None
            agent_state["confidence"] = 0.0
            agent_state["step"] = "completed"
            agent_state["done"] = True

        return result
