"""
MessageBus — Singleton async message bus for agent-to-agent communication.
Supports: queues, publish/subscribe, interrupt, and result waiting.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Optional

from ..agents.shared.constants import AgentID, Priority, MessageType
from ..agents.shared.message import AgentMessage
from ..agents.shared.exceptions import AgentNotFoundError, MessageBusError, QueueFullError

logger = logging.getLogger(__name__)


class MessageBus:
    """
    Singleton async message bus for agent communication.

    Features:
    - Per-agent message queues (FIFO)
    - Publish/subscribe for events
    - Interrupt broadcast (CrisisAgent → all agents)
    - Wait for result (task/response pattern)

    Thread-safety: All operations are async and use asyncio primitives.
    """

    _instance: Optional[MessageBus] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls) -> MessageBus:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Per-agent message queues
        self._queues: dict[str, asyncio.Queue[AgentMessage]] = {}
        self._queues_lock = asyncio.Lock()

        # Subscriptions: event_type -> list of callbacks
        self._subscriptions: dict[str, list[Callable[..., Any]]] = defaultdict(list)

        # Pending results: task_id -> asyncio.Future
        self._pending_results: dict[str, asyncio.Future[AgentMessage]] = {}
        self._results_lock = asyncio.Lock()

        # Interrupt state
        self._interrupt_event = asyncio.Event()
        self._interrupt_message: Optional[AgentMessage] = None

        # Agent registry (agents subscribe to the bus)
        self._agents: dict[str, Any] = {}  # agent_id -> agent instance

        self._initialized = True
        logger.info("[MessageBus] Initialized (singleton)")

    # ── Agent registration ──────────────────────────────────────────────

    async def register_agent(self, agent_id: str, agent: Any) -> None:
        """Register an agent and create its inbox queue."""
        async with self._queues_lock:
            if agent_id not in self._queues:
                self._queues[agent_id] = asyncio.Queue(maxsize=100)
                logger.info(f"[MessageBus] Registered agent: {agent_id}")
            else:
                logger.warning(f"[MessageBus] Agent already registered: {agent_id}")
        self._agents[agent_id] = agent

    async def unregister_agent(self, agent_id: str) -> None:
        """Remove an agent and drain its queue."""
        async with self._queues_lock:
            if agent_id in self._queues:
                # Drain queue
                q = self._queues.pop(agent_id)
                while not q.empty():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        break
        self._agents.pop(agent_id, None)
        logger.info(f"[MessageBus] Unregistered agent: {agent_id}")

    # ── Send / Receive ─────────────────────────────────────────────────

    async def send(self, message: AgentMessage) -> str:
        """
        Send a message to a specific agent (or broadcast).

        Returns message ID.
        Raises AgentNotFoundError if target agent not registered.
        """
        if message.to_agent != "broadcast":
            async with self._queues_lock:
                if message.to_agent not in self._queues:
                    raise AgentNotFoundError(message.to_agent, "send")

        if message.to_agent == "broadcast":
            # Broadcast: put in all queues
            async with self._queues_lock:
                targets = list(self._queues.keys())
            tasks = []
            for target_id in targets:
                if target_id != message.from_agent:  # Don't send to self
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
                    tasks.append(self._enqueue(target_id, msg_copy))
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            await self._enqueue(message.to_agent, message)

        logger.debug(
            f"[MessageBus] Sent {message.message_type.value} "
            f"{message.from_agent} → {message.to_agent} [id={message.id[:8]}]"
        )
        return message.id

    async def _enqueue(self, agent_id: str, message: AgentMessage) -> None:
        """Internal: put message in agent's queue."""
        try:
            self._queues[agent_id].put_nowait(message)
        except asyncio.QueueFull:
            raise QueueFullError(agent_id, self._queues[agent_id].maxsize)

    async def receive(
        self,
        agent_id: str,
        timeout: float = 30.0,
    ) -> Optional[AgentMessage]:
        """
        Receive the next message for an agent.
        Blocks until a message is available or timeout.

        Returns None if timeout expires.
        """
        if agent_id not in self._queues:
            raise AgentNotFoundError(agent_id, "receive")

        try:
            message = await asyncio.wait_for(
                self._queues[agent_id].get(),
                timeout=timeout,
            )
            return message
        except asyncio.TimeoutError:
            return None

    async def try_receive(self, agent_id: str) -> Optional[AgentMessage]:
        """Non-blocking receive. Returns None if queue is empty."""
        if agent_id not in self._queues:
            raise AgentNotFoundError(agent_id, "try_receive")
        try:
            return self._queues[agent_id].get_nowait()
        except asyncio.QueueEmpty:
            return None

    # ── Task / Response pattern ────────────────────────────────────────

    async def send_and_wait(
        self,
        message: AgentMessage,
        timeout: float = 60.0,
    ) -> AgentMessage:
        """
        Send a task message and wait for the result.
        Creates a Future that gets resolved when RESULT message arrives.

        Returns the RESULT message.
        Raises asyncio.TimeoutError on timeout.
        """
        if message.task_id is None:
            raise MessageBusError("task_id is required for send_and_wait", operation="send_and_wait")

        # Register future
        future: asyncio.Future[AgentMessage] = asyncio.Future()
        async with self._results_lock:
            self._pending_results[message.task_id] = future

        # Send message
        await self.send(message)

        # Wait for result
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        finally:
            # Cleanup
            async with self._results_lock:
                self._pending_results.pop(message.task_id, None)

    async def resolve_result(self, message: AgentMessage) -> None:
        """
        Resolve a pending Future for a RESULT message.
        Called by the receiving agent when it sends a result.
        """
        if message.task_id is None:
            return
        async with self._results_lock:
            future = self._pending_results.get(message.task_id)
        if future and not future.done():
            future.set_result(message)

    # ── Interrupt (CrisisAgent → all agents) ─────────────────────────

    async def emit_interrupt(
        self,
        from_agent: str,
        target_agents: Optional[list[str]] = None,
        reason: str = "crisis_detected",
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Emit an INTERRUPT message to all (or specific) agents.
        Used by CrisisAgent to abort all running agents.

        Also sets the global interrupt event and calls interrupt() on each agent.
        """
        message = AgentMessage.interrupt(
            from_agent=from_agent,
            target_agents=target_agents or "broadcast",
            reason=reason,
            metadata=metadata,
        )

        # Set global event
        self._interrupt_event.set()
        self._interrupt_message = message

        # Send to all registered agents
        await self.send(message)

        # Directly call interrupt() on registered agents
        for agent_id, agent in list(self._agents.items()):
            if target_agents is None or agent_id in target_agents:
                agent.interrupt(reason)

        logger.warning(
            f"[MessageBus] INTERRUPT emitted by {from_agent}: {reason} "
            f"(targets={target_agents or 'broadcast'})"
        )

    async def wait_for_interrupt(self, timeout: Optional[float] = None) -> Optional[AgentMessage]:
        """
        Wait for the next interrupt.
        Used by agents to be notified of crisis.
        """
        try:
            await asyncio.wait_for(self._interrupt_event.wait(), timeout=timeout)
            return self._interrupt_message
        except asyncio.TimeoutError:
            return None

    def clear_interrupt(self) -> None:
        """Clear the interrupt event (after handling crisis)."""
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
        """Subscribe an agent to specific event types."""
        for event_type in event_types:
            self._subscriptions[event_type].append(callback)
        logger.debug(f"[MessageBus] {agent_id} subscribed to {event_types}")

    def unsubscribe(
        self,
        agent_id: str,
        event_types: list[str],
        callback: Callable[..., Any],
    ) -> None:
        """Unsubscribe from event types."""
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
        """Publish an event to all subscribers."""
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

    def get_queue_size(self, agent_id: str) -> int:
        """Return number of messages in agent's queue."""
        return self._queues.get(agent_id, asyncio.Queue()).qsize()

    def get_registered_agents(self) -> list[str]:
        """Return list of registered agent IDs."""
        return list(self._agents.keys())

    def reset(self) -> None:
        """
        Reset the message bus (for testing).
        Clears all queues, subscriptions, and pending results.
        """
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
        logger.info("[MessageBus] Reset complete")
