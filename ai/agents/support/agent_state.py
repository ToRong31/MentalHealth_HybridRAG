"""Local ephemeral state for SupportAgent, with goal-check helper."""

from __future__ import annotations

from typing import TypedDict


class SupportLocalState(TypedDict, total=False):
    goal: str
    step: str
    done: bool
    emotion_hint: str
    coping_count: int
    exercises_count: int
    response_length: int
    error: str


def goal_check(state: SupportLocalState) -> bool:
    """Return True when SupportAgent has assembled its support response."""
    if state.get("done") is True:
        return True
    has_content = (
        state.get("coping_count", 0) > 0
        or state.get("exercises_count", 0) > 0
        or state.get("response_length", 0) > 50
    )
    if has_content and state.get("step") == "completed":
        return True
    if state.get("error"):
        return True
    return False
