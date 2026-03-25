"""Local ephemeral state for CrisisAgent."""
from __future__ import annotations

from typing import TypedDict


class CrisisLocalState(TypedDict, total=False):
    goal: str
    step: str
    done: bool
    crisis_level: str
    indicators: list[str]
    escalation_done: bool
    hotline_count: int
    error: str
