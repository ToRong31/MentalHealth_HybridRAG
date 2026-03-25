"""
Factory — creates shared memory tools dict from a MemoryService instance.
Each agent injects this into their tool registry.
"""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ai.shared.services.memory_service import MemoryService


def create_shared_memory_tools(memory_service: "MemoryService") -> dict[str, dict[str, Any]]:
    """
    Factory: build the standard 6 memory tools from a MemoryService instance.

    Returns
    -------
    {
        "save_to_buffer": {...},
        "get_context": {...},
        "merge_slots": {...},
        "get_accumulated_slots": {...},
        "get_crisis_state": {...},
        "update_crisis_state": {...},
    }

    Each entry has: description, parameters JSON schema, handler callable.
    """

    def _save_to_buffer(params: dict, gs: Any) -> dict:
        return memory_service.save_buffer(
            conv_id=params["conv_id"],
            role=params["role"],
            content=params["content"],
            metadata=params.get("metadata"),
        )

    def _get_context(params: dict, gs: Any) -> str:
        return memory_service.get_context(params["conv_id"])

    def _merge_slots(params: dict, gs: Any) -> dict:
        return memory_service.merge_slots(
            conv_id=params["conv_id"],
            new_slots=params["new_slots"],
        )

    def _get_accumulated_slots(params: dict, gs: Any) -> dict:
        return memory_service.get_accumulated_slots(params["conv_id"])

    def _get_crisis_state(params: dict, gs: Any) -> dict:
        return memory_service.get_crisis_state(params["conv_id"])

    def _update_crisis_state(params: dict, gs: Any) -> None:
        return memory_service.update_crisis_state(
            conv_id=params["conv_id"],
            state=params["state"],
        )

    return {
        "save_to_buffer": {
            "description": "Lưu 1 interaction (user/assistant message) vào conversation buffer. Tự prune nếu buffer vượt max size.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conv_id": {"type": "string"},
                    "role": {"type": "string", "enum": ["user", "assistant"]},
                    "content": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["conv_id", "role", "content"],
            },
            "handler": _save_to_buffer,
        },
        "get_context": {
            "description": "Đọc buffer + summary + slots, format thành string cho LLM context.",
            "parameters": {
                "type": "object",
                "properties": {"conv_id": {"type": "string"}},
                "required": ["conv_id"],
            },
            "handler": _get_context,
        },
        "merge_slots": {
            "description": "Merge slots mới vào accumulated slots. Trả về dict sau khi merge.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conv_id": {"type": "string"},
                    "new_slots": {"type": "object"},
                },
                "required": ["conv_id", "new_slots"],
            },
            "handler": _merge_slots,
        },
        "get_accumulated_slots": {
            "description": "Đọc tất cả slots đã collect từ đầu conversation.",
            "parameters": {
                "type": "object",
                "properties": {"conv_id": {"type": "string"}},
                "required": ["conv_id"],
            },
            "handler": _get_accumulated_slots,
        },
        "get_crisis_state": {
            "description": "Đọc crisis state hiện tại của conversation.",
            "parameters": {
                "type": "object",
                "properties": {"conv_id": {"type": "string"}},
                "required": ["conv_id"],
            },
            "handler": _get_crisis_state,
        },
        "update_crisis_state": {
            "description": "Update crisis state của conversation (dùng bởi CrisisAgent).",
            "parameters": {
                "type": "object",
                "properties": {
                    "conv_id": {"type": "string"},
                    "state": {"type": "object"},
                },
                "required": ["conv_id", "state"],
            },
            "handler": _update_crisis_state,
        },
    }
