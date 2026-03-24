"""
Communication — MessageBus, events, and subscriptions.
Inter-agent communication layer.
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
