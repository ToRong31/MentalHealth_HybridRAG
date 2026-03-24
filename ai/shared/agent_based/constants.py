"""
Constants for the Multi-Agent System.
Defines agent IDs, priorities, message types, and shared configuration.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Final


# =============================================================================
# Agent IDs
# =============================================================================
class AgentID(str, Enum):
    SUPERVISOR: Final[str] = "supervisor"
    DIAGNOSTIC: Final[str] = "diagnostic"
    THEORY: Final[str] = "theory"
    TREATMENT: Final[str] = "treatment"
    SUPPORT: Final[str] = "support"
    CRISIS: Final[str] = "crisis"


DOMAIN_AGENTS: Final[list[str]] = [
    AgentID.DIAGNOSTIC,
    AgentID.THEORY,
    AgentID.TREATMENT,
    AgentID.SUPPORT,
    AgentID.CRISIS,
]

ALL_AGENTS: Final[list[str]] = [
    AgentID.SUPERVISOR,
    *DOMAIN_AGENTS,
]


# =============================================================================
# Message Types
# =============================================================================
class MessageType(str, Enum):
    TASK: Final[str] = "task"
    RESULT: Final[str] = "result"
    ERROR: Final[str] = "error"
    EVENT: Final[str] = "event"
    INTERRUPT: Final[str] = "interrupt"
    STREAM: Final[str] = "stream"
    ROUTE: Final[str] = "route"


# =============================================================================
# Priority Levels
# =============================================================================
class Priority(str, Enum):
    CRITICAL: Final[str] = "critical"
    HIGH: Final[str] = "high"
    NORMAL: Final[str] = "normal"
    LOW: Final[str] = "low"


PRIORITY_ORDER: Final[dict[str, int]] = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.NORMAL: 2,
    Priority.LOW: 3,
}


# =============================================================================
# Event Types
# =============================================================================
class EventType(str, Enum):
    AGENT_STARTED: Final[str] = "agent_started"
    AGENT_FINISHED: Final[str] = "agent_finished"
    AGENT_ERROR: Final[str] = "agent_error"
    TOOL_CALLED: Final[str] = "tool_called"
    TOOL_RESULT: Final[str] = "tool_result"
    CRISIS_DETECTED: Final[str] = "crisis_detected"
    CRISIS_RESOLVED: Final[str] = "crisis_resolved"
    RETRIEVAL_COMPLETED: Final[str] = "retrieval_completed"
    ROUTING_DECIDED: Final[str] = "routing_decided"
    STATE_UPDATED: Final[str] = "state_updated"
    INTERRUPT_EMITTED: Final[str] = "interrupt_emitted"
    INTERRUPT_RECEIVED: Final[str] = "interrupt_received"


# =============================================================================
# Routing Intents
# =============================================================================
class Intent(str, Enum):
    DIAGNOSTIC: Final[str] = "diagnostic"
    THEORY: Final[str] = "theory"
    TREATMENT: Final[str] = "treatment"
    SUPPORT: Final[str] = "support"
    CRISIS: Final[str] = "crisis"


INTENT_TO_AGENT: Final[dict[str, str]] = {
    Intent.DIAGNOSTIC: AgentID.DIAGNOSTIC,
    Intent.THEORY: AgentID.THEORY,
    Intent.TREATMENT: AgentID.TREATMENT,
    Intent.SUPPORT: AgentID.SUPPORT,
    Intent.CRISIS: AgentID.CRISIS,
}

AGENT_TO_INTENT: Final[dict[str, str]] = {v: k for k, v in INTENT_TO_AGENT.items()}


# =============================================================================
# Shared Configuration
# =============================================================================
@dataclass(frozen=True)
class AgentConfig:
    max_retries: int = 3
    timeout_seconds: int = 60
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 30.0


# =============================================================================
# Crisis Keywords (O(1) safety gate)
# =============================================================================
CRISIS_KEYWORDS_VI: Final[list[str]] = [
    "tự tử", "tự sát", "buốc tử", "từ tử",
    "muốn chết", "mong muốn được chết", "ước muốn được chết",
    "giết chết mình", "tự hại mình",
    "dã thủ", "đã thủ",
    "overdose", "uống thuốc nhiều", "uống thuốc tự tử",
    "treo cổ", "nhảy lầu", "nhảy cầu",
    "không còn muốn sống", "chán đời muốn chết",
    "hết cách rồi", "không còn đường cứu",
]

CRISIS_KEYWORDS_EN: Final[list[str]] = [
    "suicide", "kill myself", "want to die", "wish to die",
    "end my life", "take my own life", "self-harm",
    "overdose", "hang myself", "jump off", "slit my wrists",
    "don't want to live anymore", "no reason to live",
    "no way out", "end it all",
]

CRISIS_KEYWORDS: Final[list[str]] = CRISIS_KEYWORDS_VI + CRISIS_KEYWORDS_EN


# =============================================================================
# Slot definitions for DiagnosticAgent
# =============================================================================
REQUIRED_SLOTS: Final[list[str]] = [
    "emotion",
    "trigger",
    "duration",
    "intensity",
    "impact",
    "stress_level",
]

OPTIONAL_SLOTS: Final[list[str]] = [
    "sleep",
    "appetite",
    "concentration",
    "social_withdrawal",
    "physical_symptoms",
]

ALL_SLOTS: Final[list[str]] = REQUIRED_SLOTS + OPTIONAL_SLOTS

MIN_SUFFICIENT_SLOTS: Final[int] = 5


# =============================================================================
# Language codes
# =============================================================================
class Language(str, Enum):
    VIETNAMESE: Final[str] = "vi"
    ENGLISH: Final[str] = "en"
    AUTO: Final[str] = "auto"

    @classmethod
    def detect(cls, text: str) -> str:
        """Simple language detection based on Vietnamese character presence."""
        for char in text:
            if "\u0041" <= char <= "\u007a" or "\u0030" <= char <= "\u0039":
                continue
            if "\u00c0" <= char <= "\u024f" or "\u1ea0" <= char <= "\u1ef9":
                return cls.VIETNAMESE
        return cls.ENGLISH
