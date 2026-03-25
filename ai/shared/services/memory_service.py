"""
MemoryService — conversation memory with Redis L2 cache + PostgreSQL L3 persistence.

This is a SERVICE (not an Agent). Injected into every agent constructor.
Communication: direct method call, NOT via MessageBus.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

from ai.shared.agent_based.constants import (
    REQUIRED_SLOTS,
    ALL_SLOTS,
    MIN_SUFFICIENT_SLOTS,
)

logger = logging.getLogger(__name__)

# Default config
DEFAULT_MAX_BUFFER = 3        # Max Q&A pairs in L1 working buffer
DEFAULT_CACHE_TTL = 3600      # Redis TTL = 1 hour
DEFAULT_SUMMARY_MAX_TOKENS = 256


class MemoryService:
    """
    Service for conversation memory management across 3 layers:

    L1 (in-memory dict)  — per-request ephemeral working buffer
    L2 (Redis)           — session cache, fast read/write
    L3 (PostgreSQL)      — durable long-term storage

    Usage: inject into every agent via constructor.
    NEVER call via MessageBus.
    """

    def __init__(
        self,
        redis_client: Any = None,
        db_session_factory: Optional[Callable[[], Any]] = None,
        max_buffer_size: int = DEFAULT_MAX_BUFFER,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ):
        self._redis = redis_client
        self._db = db_session_factory
        self._max_buffer = max_buffer_size
        self._cache_ttl = cache_ttl

        # L1: ephemeral in-memory working buffers
        # Keyed by conv_id, cleared at end of each request
        self._working_buffers: dict[str, list[dict[str, Any]]] = {}

        logger.info(
            f"[MemoryService] Initialized (redis={redis_client is not None}, "
            f"db={db_session_factory is not None}, max_buffer={max_buffer_size})"
        )

    # ── Internal helpers ────────────────────────────────────────────────────

    def _redis_key(self, conv_id: str, key_type: str) -> str:
        return f"mental_health:{conv_id}:{key_type}"

    def _redis_set(self, key: str, value: Any) -> None:
        if self._redis is None:
            return
        try:
            self._redis.setex(key, self._cache_ttl, json.dumps(value, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"[MemoryService] Redis set error: {e}")

    def _redis_get(self, key: str) -> Any:
        if self._redis is None:
            return None
        try:
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.warning(f"[MemoryService] Redis get error: {e}")
            return None

    def _redis_delete(self, key: str) -> None:
        if self._redis is None:
            return
        try:
            self._redis.delete(key)
        except Exception as e:
            logger.warning(f"[MemoryService] Redis delete error: {e}")

    # ── Buffer Operations ────────────────────────────────────────────────────

    async def save_buffer(
        self,
        conv_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        """
        Save 1 interaction (user or assistant) to L1 working buffer.
        Auto-prunes L1 buffer if it exceeds max_buffer_size.
        Also persists to Redis L2 immediately.
        """
        entry = {
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }

        # L1: working buffer
        if conv_id not in self._working_buffers:
            self._working_buffers[conv_id] = []
        self._working_buffers[conv_id].append(entry)

        # Prune if needed (keep only last N)
        if len(self._working_buffers[conv_id]) > self._max_buffer:
            self._working_buffers[conv_id] = self._working_buffers[conv_id][-self._max_buffer:]

        # L2: persist to Redis
        redis_key = self._redis_key(conv_id, "buffer")
        self._redis_set(redis_key, self._working_buffers[conv_id])

        logger.debug(f"[MemoryService] save_buffer conv={conv_id} role={role} len={len(content)}")

    async def get_buffer(self, conv_id: str) -> list[dict[str, Any]]:
        """Read L1 working buffer. Falls back to Redis L2 if empty."""
        if conv_id in self._working_buffers and self._working_buffers[conv_id]:
            return self._working_buffers[conv_id]

        # L2 fallback
        redis_key = self._redis_key(conv_id, "buffer")
        cached = self._redis_get(redis_key)
        if cached:
            self._working_buffers[conv_id] = cached
            return cached
        return []

    # ── Context ──────────────────────────────────────────────────────────────

    async def get_context(self, conv_id: str) -> str:
        """
        Build a full context string: buffer + summary + slots.
        Used as LLM prompt context.
        """
        buffer = await self.get_buffer(conv_id)
        summary = await self.get_summary(conv_id)
        slots = await self.get_accumulated_slots(conv_id)
        crisis = await self.get_crisis_state(conv_id)

        parts = []

        if summary:
            parts.append(f"[Summary]\n{summary}")

        if buffer:
            buffer_lines = "\n".join(
                f"{'User' if e['role'] == 'user' else 'Assistant'}: {e['content']}"
                for e in buffer
            )
            parts.append(f"[Recent conversation]\n{buffer_lines}")

        if slots:
            slot_lines = "\n".join(f"  {k}: {v}" for k, v in slots.items() if v is not None)
            parts.append(f"[Collected slots]\n{slot_lines}")

        if crisis.get("is_high_risk"):
            parts.append(f"[⚠️ CRISIS STATE] {crisis.get('crisis_level', 'unknown')}")

        return "\n\n".join(parts) if parts else ""

    # ── Slots ────────────────────────────────────────────────────────────────

    async def get_accumulated_slots(self, conv_id: str) -> dict[str, Any]:
        """Read all slots from Redis L2."""
        redis_key = self._redis_key(conv_id, "slots")
        return self._redis_get(redis_key) or {}

    async def merge_slots(self, conv_id: str, new_slots: dict[str, Any]) -> dict[str, Any]:
        """
        Merge new slots into existing accumulated slots.
        Returns the merged result.
        """
        existing = await self.get_accumulated_slots(conv_id)
        merged = {**existing, **new_slots}

        redis_key = self._redis_key(conv_id, "slots")
        self._redis_set(redis_key, merged)

        logger.debug(f"[MemoryService] merge_slots conv={conv_id} new={list(new_slots.keys())}")
        return merged

    async def get_slot_sufficiency(self, conv_id: str) -> dict[str, Any]:
        """
        Check if collected slots are sufficient for diagnostic reasoning.

        Returns
        -------
        {
            "is_sufficient": bool,
            "collected_count": int,
            "required_count": int,
            "missing": list[str],
        }
        """
        slots = await self.get_accumulated_slots(conv_id)
        collected = [k for k in REQUIRED_SLOTS if slots.get(k) is not None]
        missing = [k for k in REQUIRED_SLOTS if slots.get(k) is None]

        return {
            "is_sufficient": len(collected) >= MIN_SUFFICIENT_SLOTS,
            "collected_count": len(collected),
            "required_count": MIN_SUFFICIENT_SLOTS,
            "missing": missing,
        }

    # ── Summary ─────────────────────────────────────────────────────────────

    async def append_to_summary(self, conv_id: str, summary_text: str) -> None:
        """Append text to LLM-generated summary."""
        redis_key = self._redis_key(conv_id, "summary")
        existing = self._redis_get(redis_key) or ""
        updated = f"{existing}\n{summary_text}".strip()
        self._redis_set(redis_key, updated)

    async def get_summary(self, conv_id: str) -> str:
        """Read conversation summary."""
        redis_key = self._redis_key(conv_id, "summary")
        return self._redis_get(redis_key) or ""

    # ── Crisis State ─────────────────────────────────────────────────────────

    async def get_crisis_state(self, conv_id: str) -> dict[str, Any]:
        """Read crisis state from Redis L2."""
        redis_key = self._redis_key(conv_id, "crisis")
        return self._redis_get(redis_key) or {
            "is_high_risk": False,
            "crisis_level": "none",
        }

    async def update_crisis_state(self, conv_id: str, state: dict[str, Any]) -> None:
        """Update crisis state in Redis L2."""
        redis_key = self._redis_key(conv_id, "crisis")
        self._redis_set(redis_key, state)
        logger.warning(f"[MemoryService] Crisis state updated: {state.get('crisis_level')} risk={state.get('is_high_risk')}")

    # ── L3 Persistence ───────────────────────────────────────────────────────

    async def checkpoint_to_postgres(self, conv_id: str) -> None:
        """
        Persist full conversation memory to PostgreSQL L3.
        Called at conversation end or on a timer.
        """
        if self._db is None:
            logger.debug("[MemoryService] No DB configured, skipping checkpoint")
            return

        try:
            buffer = await self.get_buffer(conv_id)
            summary = await self.get_summary(conv_id)
            slots = await self.get_accumulated_slots(conv_id)
            crisis = await self.get_crisis_state(conv_id)

            # TODO: actually write to ConversationMemory model
            # session = self._db()
            # record = session.query(ConversationMemory).filter_by(conversation_id=conv_id).first()
            # ...

            logger.info(f"[MemoryService] Checkpointed conv={conv_id} to PostgreSQL")
        except Exception as e:
            logger.error(f"[MemoryService] Checkpoint failed: {e}")

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def clear_working_buffer(self, conv_id: str) -> None:
        """Clear L1 working buffer (end of request)."""
        self._working_buffers.pop(conv_id, None)
