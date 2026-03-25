"""Local ephemeral state for TreatmentAgent, with goal-check helper."""
from __future__ import annotations

from typing import TypedDict


class TreatmentLocalState(TypedDict, total=False):
    goal: str
    step: str
    done: bool
    condition: str
    severity: str
    retrieved_count: int
    plans_count: int
    error: str


def goal_check(state: TreatmentLocalState) -> bool:
    """Return True when TreatmentAgent has completed its treatment-planning goal."""
    if state.get("done") is True:
        return True
    if state.get("retrieved_count", 0) > 0 and state.get("step") == "completed":
        return True
    if state.get("plans_count", 0) > 0:
        return True
    if state.get("error"):
        return True
    return False
