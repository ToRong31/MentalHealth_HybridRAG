"""Local ephemeral state for DiagnosticAgent, with goal-check helper."""

from __future__ import annotations

from typing import TypedDict


class DiagnosticLocalState(TypedDict, total=False):
    goal: str
    step: str
    done: bool
    query: str
    slots_collected: int
    slots_missing: list[str]
    candidates_count: int
    diagnosis: str
    confidence: float
    error: str


def goal_check(state: DiagnosticLocalState) -> bool:
    """Return True when DiagnosticAgent has completed its diagnostic goal."""
    if state.get("done") is True:
        return True
    if state.get("candidates_count", 0) > 0 and state.get("step") == "completed":
        return True
    if state.get("diagnosis") and state.get("confidence", 0) > 0:
        return True
    if state.get("error"):
        return True
    return False
