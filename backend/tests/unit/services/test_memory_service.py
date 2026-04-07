"""
Unit tests for MemoryService — buffer, slots, context, crisis state.
"""

from __future__ import annotations

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "ai"))

from ai.shared.services.memory_service import MemoryService
from ai.shared.agent_based.constants import REQUIRED_SLOTS, MIN_SUFFICIENT_SLOTS


class MockRedis:
    """Sync-like mock for async Redis (tracks calls)."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._call_count: int = 0

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._call_count += 1
        self._store[key] = value

    async def get(self, key: str) -> str | None:
        self._call_count += 1
        return self._store.get(key)

    async def delete(self, key: str) -> None:
        self._call_count += 1
        self._store.pop(key, None)


@pytest.fixture
def redis_mock():
    return MockRedis()


@pytest.fixture
def memory(redis_mock):
    return MemoryService(redis_client=redis_mock, max_buffer_size=3, cache_ttl=60)


class TestSaveBuffer:
    """Test save_buffer()."""

    @pytest.mark.asyncio
    async def test_saves_entry_to_working_buffer(self, memory, redis_mock):
        await memory.save_buffer("conv-1", "user", " Xin chào ", {})
        buf = await memory.get_buffer("conv-1")
        assert len(buf) == 1
        assert buf[0]["role"] == "user"
        assert buf[0]["content"] == " Xin chào "

    @pytest.mark.asyncio
    async def test_prunes_to_max_buffer_size(self, memory, redis_mock):
        for i in range(5):
            await memory.save_buffer("conv-2", "user", f"msg {i}", {})
        buf = await memory.get_buffer("conv-2")
        assert len(buf) == 3  # max_buffer_size = 3
        assert buf[0]["content"] == "msg 2"
        assert buf[2]["content"] == "msg 4"

    @pytest.mark.asyncio
    async def test_persists_to_redis(self, memory, redis_mock):
        await memory.save_buffer("conv-3", "assistant", " Phản hồi ", {})
        # Redis should have been called
        assert redis_mock._call_count > 0


class TestGetBuffer:
    """Test get_buffer()."""

    @pytest.mark.asyncio
    async def test_returns_working_buffer_first(self, memory, redis_mock):
        await memory.save_buffer("conv-4", "user", "test", {})
        buf = await memory.get_buffer("conv-4")
        assert len(buf) == 1
        assert buf[0]["content"] == "test"

    @pytest.mark.asyncio
    async def test_falls_back_to_redis(self, memory, redis_mock):
        # Directly set in Redis
        import json

        redis_mock._store["mental_health:conv-5:buffer"] = json.dumps(
            [{"role": "user", "content": "from redis", "metadata": {}}]
        )
        buf = await memory.get_buffer("conv-5")
        assert buf[0]["content"] == "from redis"

    @pytest.mark.asyncio
    async def test_returns_empty_list_if_no_data(self, memory):
        buf = await memory.get_buffer("nonexistent-conv")
        assert buf == []


class TestMergeSlots:
    """Test merge_slots()."""

    @pytest.mark.asyncio
    async def test_merges_new_slots(self, memory, redis_mock):
        # First merge
        result = await memory.merge_slots(
            "conv-6", {"emotion": "lo âu", "trigger": "công việc"}
        )
        assert result["emotion"] == "lo âu"
        assert result["trigger"] == "công việc"

        # Second merge adds / overrides
        result2 = await memory.merge_slots("conv-6", {"intensity": "cao"})
        assert result2["emotion"] == "lo âu"
        assert result2["intensity"] == "cao"

    @pytest.mark.asyncio
    async def test_new_slots_override_existing(self, memory, redis_mock):
        await memory.merge_slots("conv-7", {"emotion": "buồn"})
        await memory.merge_slots("conv-7", {"emotion": "lo âu"})
        slots = await memory.get_accumulated_slots("conv-7")
        assert slots["emotion"] == "lo âu"


class TestSlotSufficiency:
    """Test get_slot_sufficiency()."""

    @pytest.mark.asyncio
    async def test_insufficient_with_no_slots(self, memory):
        result = await memory.get_slot_sufficiency("conv-8")
        assert result["is_sufficient"] is False
        assert result["collected_count"] == 0
        assert len(result["missing"]) == len(REQUIRED_SLOTS)

    @pytest.mark.asyncio
    async def test_sufficient_with_min_slots(self, memory):
        # Fill MIN_SUFFICIENT_SLOTS slots
        slots = {slot: "value" for slot in REQUIRED_SLOTS[:MIN_SUFFICIENT_SLOTS]}
        await memory.merge_slots("conv-9", slots)
        result = await memory.get_slot_sufficiency("conv-9")
        assert result["is_sufficient"] is True
        assert result["collected_count"] == MIN_SUFFICIENT_SLOTS


class TestCrisisState:
    """Test crisis state operations."""

    @pytest.mark.asyncio
    async def test_default_crisis_state(self, memory):
        state = await memory.get_crisis_state("conv-10")
        assert state["is_high_risk"] is False
        assert state["crisis_level"] == "none"

    @pytest.mark.asyncio
    async def test_update_crisis_state(self, memory):
        await memory.update_crisis_state(
            "conv-11",
            {
                "is_high_risk": True,
                "crisis_level": "high",
            },
        )
        state = await memory.get_crisis_state("conv-11")
        assert state["is_high_risk"] is True
        assert state["crisis_level"] == "high"


class TestSummary:
    """Test summary operations."""

    @pytest.mark.asyncio
    async def test_append_and_get_summary(self, memory):
        await memory.append_to_summary("conv-12", "User mentioned work stress")
        await memory.append_to_summary("conv-12", "Difficulty sleeping reported")
        summary = await memory.get_summary("conv-12")
        assert "work stress" in summary
        assert "Difficulty sleeping" in summary

    @pytest.mark.asyncio
    async def test_get_summary_empty(self, memory):
        summary = await memory.get_summary("nonexistent")
        assert summary == ""


class TestGetContext:
    """Test get_context()."""

    @pytest.mark.asyncio
    async def test_empty_context(self, memory):
        ctx = await memory.get_context("conv-empty")
        assert ctx == ""

    @pytest.mark.asyncio
    async def test_context_includes_buffer(self, memory):
        await memory.save_buffer("conv-13", "user", "Tôi lo âu", {})
        await memory.save_buffer("conv-13", "assistant", "Bạn cảm thấy thế nào?", {})
        ctx = await memory.get_context("conv-13")
        assert "Tôi lo âu" in ctx
        assert "Bạn cảm thấy" in ctx

    @pytest.mark.asyncio
    async def test_context_includes_slots(self, memory):
        await memory.merge_slots("conv-14", {"emotion": "lo âu", "duration": "2 tuần"})
        ctx = await memory.get_context("conv-14")
        assert "emotion" in ctx
        assert "lo âu" in ctx

    @pytest.mark.asyncio
    async def test_context_includes_crisis_flag(self, memory):
        await memory.update_crisis_state(
            "conv-15",
            {
                "is_high_risk": True,
                "crisis_level": "high",
            },
        )
        ctx = await memory.get_context("conv-15")
        assert "CRISIS STATE" in ctx


class TestClearWorkingBuffer:
    """Test clear_working_buffer()."""

    @pytest.mark.asyncio
    async def test_clears_l1_buffer(self, memory):
        await memory.save_buffer("conv-16", "user", "test", {})
        assert len(memory._working_buffers.get("conv-16", [])) == 1
        memory.clear_working_buffer("conv-16")
        assert "conv-16" not in memory._working_buffers
