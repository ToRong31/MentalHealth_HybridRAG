"""Local ephemeral state for TheoryAgent, with goal-check helper."""

from __future__ import annotations

from typing import TypedDict, Any


class TheoryLocalState(TypedDict, total=False):
    goal: str
    step: str
    done: bool
    query: str
    retrieved_count: int
    concepts: list[dict[str, Any]]
    error: str


def goal_check(state: TheoryLocalState) -> bool:
    """Return True when TheoryAgent has completed its retrieval goal."""
    if state.get("done") is True:
        return True
    if state.get("retrieved_count", 0) > 0 and state.get("step") == "completed":
        return True
    if state.get("error"):
        return True  # terminal with error
    return False
