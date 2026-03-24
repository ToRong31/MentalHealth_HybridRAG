"""
Message dataclass for agent-to-agent communication.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .constants import AgentID, MessageType, Priority


@dataclass
class AgentMessage:
    """
    Standard message format for all agent communication.

    All fields are immutable after creation except `content` and `metadata`
    which agents may update in-flight.
    """

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: Optional[str] = None  # Groups related messages (request + response)

    # Routing
    from_agent: str = ""  # AgentID value
    to_agent: str = ""    # AgentID value or "broadcast"

    # Message semantics
    message_type: MessageType = MessageType.TASK
    priority: Priority = Priority.NORMAL

    # Payload
    content: Any = None   # The actual data (intent dict, response, error, etc.)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None  # For TTL-based messages

    def __post_init__(self):
        # Convert string enums
        if isinstance(self.message_type, str):
            self.message_type = MessageType(self.message_type)
        if isinstance(self.priority, str):
            self.priority = Priority(self.priority)

    # -------------------------------------------------------------------------
    # Factory methods
    # -------------------------------------------------------------------------

    @classmethod
    def task(
        cls,
        from_agent: str,
        to_agent: str,
        content: Any,
        *,
        task_id: Optional[str] = None,
        priority: Priority = Priority.NORMAL,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentMessage:
        """Create a TASK message."""
        return cls(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.TASK,
            content=content,
            task_id=task_id or str(uuid.uuid4()),
            priority=priority,
            metadata=metadata or {},
        )

    @classmethod
    def result(
        cls,
        from_agent: str,
        to_agent: str,
        content: Any,
        *,
        task_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentMessage:
        """Create a RESULT message (reply to a task)."""
        return cls(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.RESULT,
            content=content,
            task_id=task_id,
            priority=Priority.NORMAL,
            metadata=metadata or {},
        )

    @classmethod
    def error(
        cls,
        from_agent: str,
        to_agent: str,
        error_message: str,
        *,
        task_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentMessage:
        """Create an ERROR message."""
        return cls(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.ERROR,
            content={"error": error_message},
            task_id=task_id,
            priority=Priority.HIGH,
            metadata=metadata or {},
        )

    @classmethod
    def interrupt(
        cls,
        from_agent: str,
        target_agents: list[str] | str = "broadcast",
        reason: str = "crisis_detected",
        *,
        task_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentMessage:
        """Create an INTERRUPT message (CrisisAgent → all agents)."""
        target = target_agents if isinstance(target_agents, str) else ",".join(target_agents)
        return cls(
            from_agent=from_agent,
            to_agent=target,
            message_type=MessageType.INTERRUPT,
            content={"reason": reason},
            task_id=task_id,
            priority=Priority.CRITICAL,
            metadata=metadata or {},
        )

    @classmethod
    def event(
        cls,
        from_agent: str,
        event_type: str,
        content: Any,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentMessage:
        """Create an EVENT notification message."""
        return cls(
            from_agent=from_agent,
            to_agent="broadcast",
            message_type=MessageType.EVENT,
            content={"event_type": event_type, "data": content},
            priority=Priority.LOW,
            metadata=metadata or {},
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def is_reply_to(self, other: AgentMessage) -> bool:
        """Check if this message is a reply to another message."""
        return self.task_id == other.id

    def is_critical(self) -> bool:
        return self.priority == Priority.CRITICAL

    def is_interrupt(self) -> bool:
        return self.message_type == MessageType.INTERRUPT

    def is_task(self) -> bool:
        return self.message_type == MessageType.TASK

    def is_result(self) -> bool:
        return self.message_type == MessageType.RESULT

    def to_dict(self) -> dict:
        """Serialize to dict for transport/logging."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type.value,
            "priority": self.priority.value,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
