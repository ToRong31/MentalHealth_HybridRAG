"""
SubscriptionManager — manages agent subscriptions to event types.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class SubscriptionManager:
    """
    Manages agent subscriptions to MessageBus events.

    Example:
        sub_mgr = SubscriptionManager(message_bus)
        sub_mgr.subscribe_agent(
            agent_id="diagnostic",
            events=["agent_started", "agent_finished", "crisis_detected"],
            handler=my_handler,
        )
    """

    def __init__(self, message_bus: Any):
        self._bus = message_bus
        self._agent_subscriptions: dict[str, dict[str, Callable[..., Any]]] = {}

    def subscribe_agent(
        self,
        agent_id: str,
        events: list[str],
        handler: Callable[..., Any],
    ) -> None:
        if agent_id not in self._agent_subscriptions:
            self._agent_subscriptions[agent_id] = {}

        for event_type in events:
            self._bus.subscribe(agent_id, [event_type], handler)
            self._agent_subscriptions[agent_id][event_type] = handler

        logger.info(f"[SubscriptionManager] {agent_id} subscribed to {events}")

    def unsubscribe_agent(self, agent_id: str) -> None:
        subscriptions = self._agent_subscriptions.pop(agent_id, {})
        for event_type, callback in subscriptions.items():
            self._bus.unsubscribe(agent_id, [event_type], callback)
        logger.info(f"[SubscriptionManager] {agent_id} unsubscribed")

    def get_subscriptions(self, agent_id: str) -> list[str]:
        return list(self._agent_subscriptions.get(agent_id, {}).keys())
