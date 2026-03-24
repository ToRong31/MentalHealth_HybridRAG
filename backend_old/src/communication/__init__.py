"""
Communication — MessageBus, events, and subscriptions.
"""
from .message_bus import MessageBus
from .events import EventEmitter, AgentEvent, emitter
from .subscriptions import SubscriptionManager

__all__ = [
    "MessageBus",
    "EventEmitter",
    "AgentEvent",
    "SubscriptionManager",
    "emitter",
]
