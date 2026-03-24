"""
BaseAgent — Abstract base class for all domain agents.
Provides shared infrastructure: memory injection, LLM, tool execution, ReAct loop.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, Optional

from .circuit_breaker import CircuitBreaker
from .constants import AgentConfig, AgentID, Priority
from .exceptions import AgentError, CircuitOpenError, RetryableError
from .message import AgentMessage
from .state import GlobalState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    Design principles:
    - MemoryService is injected via constructor (never imported directly)
    - Each agent owns its local_memory (ephemeral, per-request)
    - Agents communicate ONLY via MessageBus (not direct calls)
    - Agents do NOT call other agents directly

    Subclasses must implement:
    - run(): main agent logic
    - _register_tools(): return dict of available tools
    - _register_skills(): return dict of skills
    """

    def __init__(
        self,
        agent_id: str,
        memory_service: Any,  # MemoryService instance (injected)
        llm: Any,            # LLM client (e.g. LLMClient from rag/llm/)
        config: Optional[dict] = None,
        message_bus: Optional[Any] = None,  # MessageBus (injected)
    ):
        self.agent_id = agent_id
        self.memory_service = memory_service
        self.llm = llm
        self.config = config or {}
        self.message_bus = message_bus

        # Agent-local ephemeral state (lifetime = 1 request)
        self.local_memory: dict[str, Any] = {}

        # Register tools and skills
        self._tools = self._register_tools()
        self._skills = self._register_skills()

        # Circuit breakers per tool
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        for tool_name in self._tools:
            self._circuit_breakers[tool_name] = CircuitBreaker(
                name=f"{self.agent_id}.{tool_name}",
                threshold=self.config.get("circuit_breaker_threshold", AgentConfig.circuit_breaker_threshold),
                timeout=self.config.get("circuit_breaker_timeout", AgentConfig.circuit_breaker_timeout),
            )

        # Interrupt flag (set by CrisisAgent via MessageBus)
        self._interrupted = asyncio.Event()
        self._interrupt_reason: Optional[str] = None

        logger.info(f"[{self.agent_id}] Initialized with tools={list(self._tools.keys())}")

    # ── Abstract methods ─────────────────────────────────────────────────

    @abstractmethod
    async def run(self, input: dict[str, Any], gs: GlobalState) -> dict[str, Any]:
        """
        Main agent logic — runs once per request (NOT a loop).

        Args:
            input:  Raw input dict from upstream (Supervisor or previous agent).
                    Expected keys vary by agent type.
            gs:     GlobalState — shared mutable state across agents.

        Returns:
            dict with at minimum:
                - "response": str (human-readable answer)
                - Other agent-specific fields
        """
        ...

    @abstractmethod
    def _register_tools(self) -> dict[str, dict[str, Any]]:
        """
        Return available tools as a dict:
        {
            "tool_name": {
                "description": "...",
                "parameters": {...},  # JSON Schema
                "handler": Callable,
            }
        }
        """
        ...

    @abstractmethod
    def _register_skills(self) -> dict[str, Any]:
        """
        Return agent skills as a dict:
        {
            "SkillName": SkillInstance,
        }
        """
        ...

    # ── Tool execution ──────────────────────────────────────────────────

    async def execute_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        gs: GlobalState,
    ) -> Any:
        """
        Execute a named tool with circuit breaker protection.

        Raises:
            AgentError: Tool not found or execution failed
            CircuitOpenError: Circuit breaker is open
        """
        if tool_name not in self._tools:
            raise AgentError(f"Tool '{tool_name}' not found on agent '{self.agent_id}'", agent_id=self.agent_id)

        tool = self._tools[tool_name]
        handler: Callable[..., Coroutine] = tool["handler"]
        cb = self._circuit_breakers.get(tool_name)

        logger.debug(f"[{self.agent_id}] Executing tool '{tool_name}' with params={params}")

        if cb:
            return await cb.call(handler, params, gs)
        else:
            return await handler(params, gs)

    def list_tools(self) -> list[str]:
        """Return list of available tool names."""
        return list(self._tools.keys())

    # ── Memory helpers (delegated to injected MemoryService) ──────────────

    async def save_to_buffer(
        self,
        conv_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """Save a Q&A pair to conversation buffer."""
        await self.memory_service.save_buffer(conv_id, role, content, metadata)

    async def get_context(self, conv_id: str) -> str:
        """Get formatted context (buffer + summary + slots)."""
        return await self.memory_service.get_context(conv_id)

    async def merge_slots(self, conv_id: str, new_slots: dict) -> dict:
        """Merge new slots into accumulated slots."""
        return await self.memory_service.merge_slots(conv_id, new_slots)

    async def get_accumulated_slots(self, conv_id: str) -> dict:
        """Get all accumulated slots."""
        return await self.memory_service.get_accumulated_slots(conv_id)

    async def get_crisis_state(self, conv_id: str) -> dict:
        """Get crisis state."""
        return await self.memory_service.get_crisis_state(conv_id)

    async def update_crisis_state(self, conv_id: str, state: dict) -> None:
        """Update crisis state."""
        await self.memory_service.update_crisis_state(conv_id, state)

    # ── Interrupt handling (for CrisisAgent / message bus) ───────────────

    def interrupt(self, reason: str = "") -> None:
        """Set interrupt flag — called by MessageBus on INTERRUPT message."""
        logger.warning(f"[{self.agent_id}] INTERRUPT received: {reason}")
        self._interrupted.set()
        self._interrupt_reason = reason

    def clear_interrupt(self) -> None:
        """Clear interrupt flag (e.g., after handling crisis)."""
        self._interrupted.clear()
        self._interrupt_reason = None

    def is_interrupted(self) -> bool:
        return self._interrupted.is_set()

    async def wait_for_interrupt(self, timeout: float = 30.0) -> bool:
        """Wait for an interrupt signal. Returns True if interrupted."""
        try:
            await asyncio.wait_for(self._interrupted.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    # ── LLM helper ────────────────────────────────────────────────────────

    async def llm_generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text using the injected LLM client.

        Wraps synchronous invoke() in asyncio.to_thread().
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.llm.invoke(prompt, **kwargs),
        )

    # ── Logging ────────────────────────────────────────────────────────────

    def log(self, level: str, message: str, **kwargs) -> None:
        """Log with agent prefix."""
        getattr(logger, level)(f"[{self.agent_id}] {message}", **kwargs)

    def info(self, message: str, **kwargs) -> None:
        self.log("info", message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self.log("warning", message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self.log("error", message, **kwargs)

    def debug(self, message: str, **kwargs) -> None:
        self.log("debug", message, **kwargs)
