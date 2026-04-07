"""
MemoryService — conversation memory with Redis L2 cache + PostgreSQL L3 persistence.

This is a SERVICE (not an Agent). Injected into every agent constructor.
Communication: direct method call, NOT via MessageBus.

3-layer architecture:
  L1: in-memory dict (ephemeral, per-request working buffer)
  L2: Redis (async, session cache, fast read/write)
  L3: PostgreSQL (durable, long-term storage)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from ai.shared.agent_based.constants import (
    REQUIRED_SLOTS,
    MIN_SUFFICIENT_SLOTS,
)

logger = logging.getLogger(__name__)

# Default config
DEFAULT_MAX_BUFFER = 3        # Max Q&A pairs in L1 working buffer
DEFAULT_CACHE_TTL = 3600     # Redis TTL = 1 hour
DEFAULT_SUMMARY_MAX_TOKENS = 256


class MemoryService:
    """
    Service for conversation memory management across 3 layers:

    L1 (in-memory dict)  — per-request ephemeral working buffer
    L2 (Redis)           — session cache, fast read/write (async)
    L3 (PostgreSQL)      — durable long-term storage

    Usage: inject into every agent via constructor.
    NEVER call via MessageBus.
    """

    def __init__(
        self,
        redis_client: Any = None,
        db_session_factory: Any = None,
        max_buffer_size: int = DEFAULT_MAX_BUFFER,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ):
        """
        Args:
            redis_client: an async redis client (redis.asyncio.Redis).
                          If None, L2 cache is disabled.
            db_session_factory: an async session factory for PostgreSQL.
                          If None, L3 checkpoint is disabled.
            max_buffer_size: max Q&A pairs in L1 working buffer.
            cache_ttl: TTL for Redis L2 cache entries in seconds.
        """
        self._redis: Optional[Any] = redis_client
        self._db = db_session_factory
        self._max_buffer = max_buffer_size
        self._cache_ttl = cache_ttl

        # L1: ephemeral in-memory working buffers
        # Keyed by conv_id, cleared at end of each request
        self._working_buffers: dict[str, list[dict[str, Any]]] = {}

        logger.info(
            f"[MemoryService] Initialized (redis={'yes' if redis_client else 'NO'}, "
            f"db={'yes' if db_session_factory else 'NO'}, max_buffer={max_buffer_size})"
        )

    # ── Key helpers ─────────────────────────────────────────────────────────

    def _redis_key(self, conv_id: str, key_type: str) -> str:
        return f"mental_health:{conv_id}:{key_type}"

    # ── Redis L2 operations (async) ──────────────────────────────────────────

    async def _redis_set(self, key: str, value: Any) -> None:
        """Async Redis SET with TTL."""
        if self._redis is None:
            return
        try:
            await self._redis.setex(
                key,
                self._cache_ttl,
                json.dumps(value, ensure_ascii=False),
            )
        except Exception as e:
            logger.warning(f"[MemoryService] Redis set error: {e}")

    async def _redis_get(self, key: str) -> Any:
        """Async Redis GET with JSON parse."""
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.warning(f"[MemoryService] Redis get error: {e}")
            return None

    async def _redis_delete(self, key: str) -> None:
        """Async Redis DELETE."""
        if self._redis is None:
            return
        try:
            await self._redis.delete(key)
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
        await self._redis_set(redis_key, self._working_buffers[conv_id])

        logger.debug(f"[MemoryService] save_buffer conv={conv_id} role={role} len={len(content)}")

    async def get_buffer(self, conv_id: str) -> list[dict[str, Any]]:
        """Read L1 working buffer. Falls back to Redis L2 if empty."""
        if conv_id in self._working_buffers and self._working_buffers[conv_id]:
            return self._working_buffers[conv_id]

        # L2 fallback
        redis_key = self._redis_key(conv_id, "buffer")
        cached = await self._redis_get(redis_key)
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
        return await self._redis_get(redis_key) or {}

    async def merge_slots(self, conv_id: str, new_slots: dict[str, Any]) -> dict[str, Any]:
        """
        Merge new slots into existing accumulated slots.
        Returns the merged result.
        """
        existing = await self.get_accumulated_slots(conv_id)
        merged = {**existing, **new_slots}

        redis_key = self._redis_key(conv_id, "slots")
        await self._redis_set(redis_key, merged)

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
        existing = await self._redis_get(redis_key) or ""
        updated = f"{existing}\n{summary_text}".strip()
        await self._redis_set(redis_key, updated)

    async def get_summary(self, conv_id: str) -> str:
        """Read conversation summary."""
        redis_key = self._redis_key(conv_id, "summary")
        result = await self._redis_get(redis_key)
        return result or ""

    # ── Crisis State ─────────────────────────────────────────────────────────

    async def get_crisis_state(self, conv_id: str) -> dict[str, Any]:
        """Read crisis state from Redis L2."""
        redis_key = self._redis_key(conv_id, "crisis")
        result = await self._redis_get(redis_key)
        return result or {
            "is_high_risk": False,
            "crisis_level": "none",
        }

    async def update_crisis_state(self, conv_id: str, state: dict[str, Any]) -> None:
        """Update crisis state in Redis L2."""
        redis_key = self._redis_key(conv_id, "crisis")
        await self._redis_set(redis_key, state)
        logger.warning(
            f"[MemoryService] Crisis state updated: {state.get('crisis_level')} "
            f"risk={state.get('is_high_risk')}"
        )

    # ── L3 Persistence (PostgreSQL) ─────────────────────────────────────────

    async def checkpoint_to_postgres(self, conv_id: str) -> None:
        """
        Persist full conversation memory to PostgreSQL L3.
        Called at conversation end or on a timer.

        Writes to ConversationMemory table:
          - conversation_id (PK)
          - buffer (JSON)
          - summary (text)
          - slots (JSON)
          - crisis_state (JSON)
          - updated_at (timestamp)
        """
        if self._db is None:
            logger.debug("[MemoryService] No DB configured, skipping checkpoint")
            return

        try:
            buffer = await self.get_buffer(conv_id)
            summary = await self.get_summary(conv_id)
            slots = await self.get_accumulated_slots(conv_id)
            crisis = await self.get_crisis_state(conv_id)

            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()

            # Upsert into ConversationMemory
            record = {
                "conversation_id": conv_id,
                "buffer": json.dumps(buffer, ensure_ascii=False),
                "summary": summary,
                "slots": json.dumps(slots, ensure_ascii=False),
                "crisis_state": json.dumps(crisis, ensure_ascii=False),
                "updated_at": now,
            }

            # Use the async session factory
            async with self._db() as session:
                # Try to upsert
                from sqlalchemy import text
                stmt = text("""
                    INSERT INTO conversation_memory
                        (conversation_id, buffer, summary, slots, crisis_state, updated_at)
                    VALUES
                        (:conversation_id, :buffer::jsonb, :summary, :slots::jsonb, :crisis_state::jsonb, :updated_at::timestamptz)
                    ON CONFLICT (conversation_id)
                    DO UPDATE SET
                        buffer = EXCLUDED.buffer,
                        summary = EXCLUDED.summary,
                        slots = EXCLUDED.slots,
                        crisis_state = EXCLUDED.crisis_state,
                        updated_at = EXCLUDED.updated_at
                """)
                await session.execute(stmt, record)
                await session.commit()

            logger.info(f"[MemoryService] Checkpointed conv={conv_id} to PostgreSQL")

        except Exception as e:
            logger.error(f"[MemoryService] Checkpoint failed: {e}")

    async def load_from_postgres(self, conv_id: str) -> dict[str, Any]:
        """
        Load full conversation memory from PostgreSQL L3 and warm the Redis L2 cache.
        Called when resuming a conversation.

        Returns dict with buffer, summary, slots, crisis_state keys.
        """
        if self._db is None:
            logger.debug("[MemoryService] No DB configured, cannot load from postgres")
            return {}

        try:
            async with self._db() as session:
                from sqlalchemy import text
                stmt = text("""
                    SELECT buffer, summary, slots, crisis_state
                    FROM conversation_memory
                    WHERE conversation_id = :conv_id
                """)
                result = await session.execute(stmt, {"conv_id": conv_id})
                row = result.fetchone()

                if not row:
                    logger.debug(f"[MemoryService] No checkpoint found for conv={conv_id}")
                    return {}

                buffer_json, summary, slots_json, crisis_json = row
                buffer = json.loads(buffer_json) if buffer_json else []
                slots = json.loads(slots_json) if slots_json else {}
                crisis = json.loads(crisis_json) if crisis_json else {}

                # Warm L2 cache
                await self._redis_set(self._redis_key(conv_id, "buffer"), buffer)
                await self._redis_set(self._redis_key(conv_id, "summary"), summary)
                await self._redis_set(self._redis_key(conv_id, "slots"), slots)
                await self._redis_set(self._redis_key(conv_id, "crisis"), crisis)

                # Warm L1 buffer
                self._working_buffers[conv_id] = buffer

                logger.info(f"[MemoryService] Loaded checkpoint for conv={conv_id}")
                return {
                    "buffer": buffer,
                    "summary": summary,
                    "slots": slots,
                    "crisis_state": crisis,
                }

        except Exception as e:
            logger.error(f"[MemoryService] Load from postgres failed: {e}")
            return {}

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def clear_working_buffer(self, conv_id: str) -> None:
        """Clear L1 working buffer (end of request)."""
        self._working_buffers.pop(conv_id, None)

    async def clear_conversation(self, conv_id: str) -> None:
        """Clear all memory layers for a conversation."""
        self.clear_working_buffer(conv_id)

        # Clear Redis L2
        for key_type in ("buffer", "summary", "slots", "crisis"):
            await self._redis_delete(self._redis_key(conv_id, key_type))

        # Clear PostgreSQL L3
        if self._db is not None:
            try:
                async with self._db() as session:
                    from sqlalchemy import text
                    await session.execute(
                        text("DELETE FROM conversation_memory WHERE conversation_id = :conv_id"),
                        {"conv_id": conv_id},
                    )
                    await session.commit()
            except Exception as e:
                logger.warning(f"[MemoryService] Failed to clear postgres: {e}")

        logger.info(f"[MemoryService] Cleared all memory for conv={conv_id}")
