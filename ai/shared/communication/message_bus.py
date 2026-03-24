"""
MessageBus — Singleton async message bus for agent-to-agent communication.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Optional

from ai.shared.agent_based.constants import Priority, MessageType
from ai.shared.communication.message import AgentMessage
from ai.shared.exceptions import AgentNotFoundError, QueueFullError

logger = logging.getLogger(__name__)


class MessageBus:
    """
    Singleton async message bus.

    Features:
    - Per-agent message queues
    - Interrupt broadcast (CrisisAgent -> all agents)
    - Wait for result (task/response pattern)
    - Publish/subscribe events
    """

    _instance: Optional[MessageBus] = None

    def __new__(cls) -> MessageBus:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._queues: dict[str, asyncio.Queue[AgentMessage]] = {}
        self._queues_lock = asyncio.Lock()

        self._subscriptions: dict[str, list[Callable[..., Any]]] = defaultdict(list)

        self._pending_results: dict[str, asyncio.Future[AgentMessage]] = {}
        self._results_lock = asyncio.Lock()

        self._interrupt_event = asyncio.Event()
        self._interrupt_message: Optional[AgentMessage] = None

        self._agents: dict[str, Any] = {}

        self._initialized = True
        logger.info("[MessageBus] Initialized (singleton)")

    # ── Agent registration ──────────────────────────────────────────────

    async def register_agent(self, agent_id: str, agent: Any) -> None:
        async with self._queues_lock:
            if agent_id not in self._queues:
                self._queues[agent_id] = asyncio.Queue(maxsize=100)
                logger.info(f"[MessageBus] Registered: {agent_id}")
        self._agents[agent_id] = agent

    async def unregister_agent(self, agent_id: str) -> None:
        async with self._queues_lock:
            if agent_id in self._queues:
                q = self._queues.pop(agent_id)
                while not q.empty():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        break
        self._agents.pop(agent_id, None)

    # ── Send / Receive ─────────────────────────────────────────────────

    async def send(self, message: AgentMessage) -> str:
        if message.to_agent != "broadcast":
            async with self._queues_lock:
                if message.to_agent not in self._queues:
                    raise AgentNotFoundError(message.to_agent, "send")

        if message.to_agent == "broadcast":
            async with self._queues_lock:
                targets = [a for a in self._queues if a != message.from_agent]
            for target_id in targets:
                msg_copy = AgentMessage(
                    id=message.id,
                    task_id=message.task_id,
                    from_agent=message.from_agent,
                    to_agent=target_id,
                    message_type=message.message_type,
                    priority=message.priority,
                    content=message.content,
                    metadata=message.metadata,
                )
                await self._enqueue(target_id, msg_copy)
        else:
            await self._enqueue(message.to_agent, message)

        return message.id

    async def _enqueue(self, agent_id: str, message: AgentMessage) -> None:
        try:
            self._queues[agent_id].put_nowait(message)
        except asyncio.QueueFull:
            raise QueueFullError(agent_id, self._queues[agent_id].maxsize)

    async def receive(
        self,
        agent_id: str,
        timeout: float = 30.0,
    ) -> Optional[AgentMessage]:
        if agent_id not in self._queues:
            raise AgentNotFoundError(agent_id, "receive")
        try:
            return await asyncio.wait_for(
                self._queues[agent_id].get(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return None

    async def try_receive(self, agent_id: str) -> Optional[AgentMessage]:
        if agent_id not in self._queues:
            raise AgentNotFoundError(agent_id, "try_receive")
        try:
            return self._queues[agent_id].get_nowait()
        except asyncio.QueueEmpty:
            return None

    # ── Task / Response ────────────────────────────────────────────────

    async def send_and_wait(
        self,
        message: AgentMessage,
        timeout: float = 60.0,
    ) -> AgentMessage:
        if message.task_id is None:
            raise ValueError("task_id required for send_and_wait")

        future: asyncio.Future[AgentMessage] = asyncio.Future()
        async with self._results_lock:
            self._pending_results[message.task_id] = future

        await self.send(message)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            async with self._results_lock:
                self._pending_results.pop(message.task_id, None)

    async def resolve_result(self, message: AgentMessage) -> None:
        if message.task_id is None:
            return
        async with self._results_lock:
            future = self._pending_results.get(message.task_id)
        if future and not future.done():
            future.set_result(message)

    # ── Interrupt ─────────────────────────────────────────────────────

    async def emit_interrupt(
        self,
        from_agent: str,
        target_agents: Optional[list[str]] = None,
        reason: str = "crisis_detected",
        metadata: Optional[dict] = None,
    ) -> None:
        message = AgentMessage.interrupt(
            from_agent=from_agent,
            target_agents=target_agents,
            reason=reason,
            metadata=metadata,
        )

        self._interrupt_event.set()
        self._interrupt_message = message
        await self.send(message)

        for agent_id, agent in list(self._agents.items()):
            if target_agents is None or agent_id in target_agents:
                agent.interrupt(reason)

        logger.warning(
            f"[MessageBus] INTERRUPT by {from_agent}: {reason}"
        )

    async def wait_for_interrupt(self, timeout: Optional[float] = None) -> Optional[AgentMessage]:
        try:
            await asyncio.wait_for(self._interrupt_event.wait(), timeout=timeout)
            return self._interrupt_message
        except asyncio.TimeoutError:
            return None

    def clear_interrupt(self) -> None:
        self._interrupt_event.clear()
        self._interrupt_message = None
        for agent in self._agents.values():
            agent.clear_interrupt()
        logger.info("[MessageBus] Interrupt cleared")

    def is_interrupted(self) -> bool:
        return self._interrupt_event.is_set()

    # ── Publish / Subscribe ───────────────────────────────────────────

    def subscribe(
        self,
        agent_id: str,
        event_types: list[str],
        callback: Callable[..., Any],
    ) -> None:
        for event_type in event_types:
            self._subscriptions[event_type].append(callback)

    def unsubscribe(
        self,
        agent_id: str,
        event_types: list[str],
        callback: Callable[..., Any],
    ) -> None:
        for event_type in event_types:
            if callback in self._subscriptions.get(event_type, []):
                self._subscriptions[event_type].remove(callback)

    async def publish_event(
        self,
        from_agent: str,
        event_type: str,
        data: Any,
        metadata: Optional[dict] = None,
    ) -> None:
        message = AgentMessage.event(
            from_agent=from_agent,
            event_type=event_type,
            content=data,
            metadata=metadata,
        )
        callbacks = list(self._subscriptions.get(event_type, []))
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"[MessageBus] Event callback error ({event_type}): {e}")

    # ── Utility ───────────────────────────────────────────────────────

    def get_registered_agents(self) -> list[str]:
        return list(self._agents.keys())

    def reset(self) -> None:
        for q in self._queues.values():
            while not q.empty():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break
        self._subscriptions.clear()
        self._pending_results.clear()
        self._interrupt_event.clear()
        self._interrupt_message = None
        self._initialized = False
        MessageBus._instance = None
