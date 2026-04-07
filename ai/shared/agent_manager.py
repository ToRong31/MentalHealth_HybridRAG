"""
AgentManager — singleton registry for all domain agents.

Manages agent lifecycle: create, store, retrieve.
Injected into ChatService / HTTP server so they don't import agent classes directly.

Usage:
    from ai.shared.agent_manager import get_agent_manager

    manager = get_agent_manager()
    supervisor = manager.get_agent(AgentID.SUPERVISOR)
"""
from __future__ import annotations

import logging
from typing import Any

from ai.shared.agent_based.constants import AgentID
from ai.shared.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Singleton registry for all agent instances.

    Tracks:
      - supervisor
      - diagnostic
      - theory
      - treatment
      - support
      - crisis

    Each agent gets the same MemoryService and LLM instance.
    """

    _instance: "AgentManager | None" = None

    def __init__(
        self,
        memory_service: MemoryService,
        llm: Any,
        config: dict[str, Any] | None = None,
    ):
        self._agents: dict[str, Any] = {}
        self._memory_service = memory_service
        self._llm = llm
        self._config = config or {}
        self._initialized = False

    # ── Singleton ──────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(
        cls,
        memory_service: MemoryService | None = None,
        llm: Any = None,
        config: dict[str, Any] | None = None,
    ) -> "AgentManager":
        """Get or create the singleton AgentManager instance."""
        if cls._instance is None:
            if memory_service is None:
                raise ValueError("AgentManager.get_instance() called without memory_service on first call")
            cls._instance = cls(memory_service=memory_service, llm=llm, config=config)
            logger.info("[AgentManager] Singleton created")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton — useful for testing."""
        cls._instance = None
        logger.info("[AgentManager] Singleton reset")

    # ── Registration ───────────────────────────────────────────────────────────

    def register_domain_agents(self) -> None:
        """Create and store all domain agents + supervisor."""
        if self._initialized:
            logger.warning("[AgentManager] Agents already registered, skipping")
            return

        # Import here to avoid circular imports
        from ai.agents.supervisor.supervisor_agent import SupervisorAgent
        from ai.agents.diagnostic.diagnostic_agent import DiagnosticAgent
        from ai.agents.theory.theory_agent import TheoryAgent
        from ai.agents.treatment.treatment_agent import TreatmentAgent
        from ai.agents.support.support_agent import SupportAgent
        from ai.agents.crisis.crisis_agent import CrisisAgent

        agent_cfg = self._config.copy()

        self._agents[AgentID.SUPERVISOR] = SupervisorAgent(
            memory_service=self._memory_service,
            llm=self._llm,
            config=agent_cfg,
        )
        self._agents[AgentID.DIAGNOSTIC] = DiagnosticAgent(
            memory_service=self._memory_service,
            llm=self._llm,
            config=agent_cfg,
        )
        self._agents[AgentID.THEORY] = TheoryAgent(
            memory_service=self._memory_service,
            llm=self._llm,
            config=agent_cfg,
        )
        self._agents[AgentID.TREATMENT] = TreatmentAgent(
            memory_service=self._memory_service,
            llm=self._llm,
            config=agent_cfg,
        )
        self._agents[AgentID.SUPPORT] = SupportAgent(
            memory_service=self._memory_service,
            llm=self._llm,
            config=agent_cfg,
        )
        self._agents[AgentID.CRISIS] = CrisisAgent(
            memory_service=self._memory_service,
            llm=self._llm,
            config=agent_cfg,
        )

        self._initialized = True
        logger.info(
            f"[AgentManager] Registered {len(self._agents)} agents: {list(self._agents.keys())}"
        )

    # ── Access ─────────────────────────────────────────────────────────────────

    def get_agent(self, agent_id: str) -> Any:
        """Get an agent by AgentID."""
        agent = self._agents.get(agent_id)
        if agent is None:
            raise KeyError(f"[AgentManager] Agent not found: {agent_id}")
        return agent

    def has_agent(self, agent_id: str) -> bool:
        """Check if agent is registered."""
        return agent_id in self._agents

    @property
    def all_agents(self) -> dict[str, Any]:
        """Return all registered agents."""
        return self._agents.copy()

    @property
    def supervisor(self) -> Any:
        """Shortcut: get the SupervisorAgent."""
        return self._agents.get(AgentID.SUPERVISOR)


# ── Module-level convenience ──────────────────────────────────────────────────

_manager_instance: AgentManager | None = None


def init_agent_manager(
    memory_service: MemoryService,
    llm: Any,
    config: dict[str, Any] | None = None,
) -> AgentManager:
    """Initialize the global AgentManager singleton."""
    global _manager_instance
    _manager_instance = AgentManager.get_instance(
        memory_service=memory_service,
        llm=llm,
        config=config,
    )
    _manager_instance.register_domain_agents()
    return _manager_instance


def get_agent_manager() -> AgentManager:
    """Get the global AgentManager singleton. Raises if not initialized."""
    if _manager_instance is None:
        raise RuntimeError(
            "[AgentManager] Not initialized. Call init_agent_manager() first."
        )
    return _manager_instance
