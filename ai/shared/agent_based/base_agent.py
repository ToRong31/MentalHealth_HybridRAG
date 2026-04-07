"""
BaseAgent — Abstract base class for all domain agents.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, Optional

from ..circuit_breaker import CircuitBreaker
from .constants import AgentConfig
from ..exceptions import AgentError
from .state import GlobalState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    Design:
    - MemoryService injected via constructor
    - LLM injected via constructor
    - Agents communicate ONLY via MessageBus
    - Agents do NOT call other agents directly

    Subclasses must implement:
    - run(): main agent logic
    - _register_tools(): available tools dict
    - _register_skills(): skills dict
    """

    def __init__(
        self,
        agent_id: str,
        memory_service: Any,
        llm: Any,
        config: Optional[dict] = None,
    ):
        self.agent_id = agent_id
        self.memory_service = memory_service
        self.llm = llm
        self.config = config or {}

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

        # Interrupt flag (cross-service crisis interrupt via HTTP header/event)
        self._interrupted = asyncio.Event()
        self._interrupt_reason: Optional[str] = None

        logger.info(f"[{self.agent_id}] Initialized with tools={list(self._tools.keys())}")

    # ── Abstract methods ─────────────────────────────────────────────────

    @abstractmethod
    async def run(self, input: dict[str, Any], gs: GlobalState) -> dict[str, Any]:
        """
        Main agent logic — runs once per request.

        Args:
            input: Raw input dict from upstream (Supervisor or previous agent).
            gs:    GlobalState — shared mutable state across agents.

        Returns:
            dict with at minimum {"response": str, ...}
        """
        ...

    @abstractmethod
    def _register_tools(self) -> dict[str, dict[str, Any]]:
        """
        Return available tools:
        {
            "tool_name": {
                "description": "...",
                "parameters": {...},
                "handler": Callable,
            }
        }
        """
        ...

    @abstractmethod
    def _register_skills(self) -> dict[str, Any]:
        """Return agent skills: {"SkillName": SkillInstance}"""
        ...

    # ── Tool execution ──────────────────────────────────────────────────

    async def execute_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        gs: GlobalState,
    ) -> Any:
        """Execute a named tool with circuit breaker protection."""
        if tool_name not in self._tools:
            raise AgentError(f"Tool '{tool_name}' not found on agent '{self.agent_id}'", agent_id=self.agent_id)

        tool = self._tools[tool_name]
        handler: Callable[..., Coroutine] = tool["handler"]
        cb = self._circuit_breakers.get(tool_name)

        logger.debug(f"[{self.agent_id}] Executing tool '{tool_name}'")

        if cb:
            return await cb.call(handler, params, gs)
        else:
            return await handler(params, gs)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    # ── Memory helpers (delegated to injected MemoryService) ──────────────

    async def save_to_buffer(
        self,
        conv_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> None:
        await self.memory_service.save_buffer(conv_id, role, content, metadata)

    async def get_context(self, conv_id: str) -> str:
        return await self.memory_service.get_context(conv_id)

    async def merge_slots(self, conv_id: str, new_slots: dict) -> dict:
        return await self.memory_service.merge_slots(conv_id, new_slots)

    async def get_accumulated_slots(self, conv_id: str) -> dict:
        return await self.memory_service.get_accumulated_slots(conv_id)

    async def get_crisis_state(self, conv_id: str) -> dict:
        return await self.memory_service.get_crisis_state(conv_id)

    async def update_crisis_state(self, conv_id: str, state: dict) -> None:
        await self.memory_service.update_crisis_state(conv_id, state)

    # ── Interrupt handling ───────────────────────────────────────────────

    def interrupt(self, reason: str = "") -> None:
        logger.warning(f"[{self.agent_id}] INTERRUPT received: {reason}")
        self._interrupted.set()
        self._interrupt_reason = reason

    def clear_interrupt(self) -> None:
        self._interrupted.clear()
        self._interrupt_reason = None

    def is_interrupted(self) -> bool:
        return self._interrupted.is_set()

    async def wait_for_interrupt(self, timeout: float = 30.0) -> bool:
        try:
            await asyncio.wait_for(self._interrupted.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    # ── LLM helper ────────────────────────────────────────────────────────

    async def llm_generate(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """
        Generate text using the injected LLM client.

        Supports both OpenAIClient (async) and GeminiClient (async).
        Falls back gracefully if no LLM is configured.
        """
        if self.llm is None:
            raise RuntimeError(
                f"[{self.agent_id}] No LLM configured — set NVIDIA_API_KEY or GEMINI_API_KEY"
            )

        # OpenAIClient.generate() is async
        if hasattr(self.llm, "generate"):
            return await self.llm.generate(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

        # GeminiClient.generate() is also async
        if hasattr(self.llm, "generate_content"):
            import asyncio
            return await asyncio.to_thread(
                lambda: self.llm.generate_content(
                    prompt,
                    generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
                ).text.strip()
            )

        raise RuntimeError(
            f"[{self.agent_id}] LLM client has no supported generate method"
        )

    # ── Logging ───────────────────────────────────────────────────────────

    def info(self, message: str, **kwargs) -> None:
        logger.info(f"[{self.agent_id}] {message}", **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        logger.warning(f"[{self.agent_id}] {message}", **kwargs)

    def error(self, message: str, **kwargs) -> None:
        logger.error(f"[{self.agent_id}] {message}", **kwargs)

    def debug(self, message: str, **kwargs) -> None:
        logger.debug(f"[{self.agent_id}] {message}", **kwargs)
