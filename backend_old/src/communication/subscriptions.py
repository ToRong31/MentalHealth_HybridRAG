"""
SubscriptionManager — manages agent subscriptions to event types.
Provides higher-level subscribe/unsubscribe API on top of MessageBus.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class SubscriptionManager:
    """
    Manages agent subscriptions to MessageBus events.

    Provides a cleaner API for agents to subscribe to groups of related events
    without managing individual callbacks.

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
        # agent_id -> {event_type -> callback}
        self._agent_subscriptions: dict[str, dict[str, Callable[..., Any]]] = {}

    def subscribe_agent(
        self,
        agent_id: str,
        events: list[str],
        handler: Callable[..., Any],
    ) -> None:
        """
        Subscribe an agent to multiple event types with a single handler.

        The handler receives the full AgentMessage as its argument.
        """
        if agent_id not in self._agent_subscriptions:
            self._agent_subscriptions[agent_id] = {}

        for event_type in events:
            # Wrap handler to extract event data
            async def wrapped_handler(msg: Any) -> None:
                await handler(msg)

            self._bus.subscribe(agent_id, [event_type], wrapped_handler)
            self._agent_subscriptions[agent_id][event_type] = wrapped_handler

        logger.info(f"[SubscriptionManager] {agent_id} subscribed to {events}")

    def unsubscribe_agent(self, agent_id: str) -> None:
        """Unsubscribe an agent from all its events."""
        subscriptions = self._agent_subscriptions.pop(agent_id, {})
        for event_type, callback in subscriptions.items():
            # Note: MessageBus.unsubscribe needs event_types list
            self._bus.unsubscribe(agent_id, [event_type], callback)
        logger.info(f"[SubscriptionManager] {agent_id} unsubscribed from all events")

    def get_subscriptions(self, agent_id: str) -> list[str]:
        """Return list of event types an agent is subscribed to."""
        return list(self._agent_subscriptions.get(agent_id, {}).keys())

    def get_all_subscriptions(self) -> dict[str, list[str]]:
        """Return all subscriptions as {agent_id: [event_types]}."""
        return {
            agent_id: list(events.keys())
            for agent_id, events in self._agent_subscriptions.items()
        }
