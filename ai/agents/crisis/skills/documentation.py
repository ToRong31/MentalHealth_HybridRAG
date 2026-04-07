"""
Documentation skill — logs crisis events for audit and follow-up.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class Documentation:
    """Log crisis events for audit trail and follow-up."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def log_crisis_event(
        self,
        conv_id: str,
        user_id: str,
        message: str,
        crisis_level: str,
        indicators: list[str],
        response: str,
        escalation_done: bool,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """
        Log crisis event for audit trail.

        Returns
        -------
        Audit log dict (to be stored in DB / sent to admin)
        """
        event = {
            "event_type": "crisis_detected",
            "conversation_id": conv_id,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_preview": message[:200] if message else "",
            "crisis_level": crisis_level,
            "indicators": indicators,
            "response_provided": response[:500] if response else "",
            "escalation_done": escalation_done,
            "agent_id": "crisis",
            "metadata": metadata or {},
        }

        # Log to standard logger for now
        logger.warning(
            f"[Crisis Documentation] conv={conv_id} level={crisis_level} "
            f"indicators={indicators} escalation={escalation_done}"
        )

        # TODO: Store to database / send to admin notification system
        # Example:
        # await self._db.insert_crisis_log(event)

        return event

    async def create_followup_task(
        self,
        conv_id: str,
        user_id: str,
        crisis_level: str,
    ) -> dict[str, Any]:
        """
        Create a follow-up task for clinicians / admins.
        """
        priority_map = {
            "critical": "urgent",
            "high": "high",
            "medium": "normal",
            "low": "low",
        }

        return {
            "task_type": "crisis_followup",
            "conversation_id": conv_id,
            "user_id": user_id,
            "priority": priority_map.get(crisis_level, "normal"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "description": f"Follow up with user after crisis level={crisis_level}",
        }
