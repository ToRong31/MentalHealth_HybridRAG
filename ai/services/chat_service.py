"""
ChatService — entry point of the AI engine.

Orchestrates:
  1. SupervisorAgent.route() → target_domain_agent
  2. Dispatch to correct domain agent
  3. Return response

Called by FastAPI endpoint (backend).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from ai.shared.agent_based.base_agent import BaseAgent
from ai.shared.agent_based.state import GlobalState, create_initial_state
from ai.shared.agent_based.constants import AgentID
from ai.shared.services.memory_service import MemoryService
from ai.shared.communication.message_bus import MessageBus
from ai.shared.communication.events import emitter

logger = logging.getLogger(__name__)


class ChatService:
    """
    Main entry point of the AI engine.

    Usage:
        chat_service = ChatService(supervisor=..., domain_agents=..., memory_service=...)
        result = await chat_service.process_message(message="...", conv_id="...", user_id="...")
    """

    def __init__(
        self,
        supervisor: Any,            # SupervisorAgent
        domain_agents: dict[str, BaseAgent],
        memory_service: MemoryService,
        message_bus: MessageBus | None = None,
    ):
        self._supervisor = supervisor
        self._domain_agents = domain_agents
        self._memory = memory_service
        self._bus = message_bus or MessageBus()

        # Inject message_bus + register domain agents into supervisor
        if hasattr(self._supervisor, "register_domain_agents"):
            self._supervisor.register_domain_agents(domain_agents)

        # Register all agents with message bus
        for agent_id, agent in domain_agents.items():
            agent.message_bus = self._bus

        logger.info(
            f"[ChatService] Initialized with domain agents: {list(domain_agents.keys())}"
        )

    async def process_message(
        self,
        message: str,
        conversation_id: str,
        user_id: str,
        language: str = "vi",
    ) -> dict[str, Any]:
        """
        Process a single user message through the full agent pipeline.

        Pipeline:
          1. Create GlobalState
          2. Crisis check (fast path)
          3. SupervisorAgent.route() → target agent
          4. Dispatch to domain agent
          5. Return response
        """
        logger.info(
            f"[ChatService] Processing message for conv={conversation_id} user={user_id}"
        )

        # Create initial state
        gs = create_initial_state(
            conversation_id=conversation_id,
            user_id=user_id,
            message=message,
            language=language,
        )

        try:
            # ── Step 1: Check if already in crisis ──────────────────────────
            crisis_state = await self._memory.get_crisis_state(conversation_id)
            if crisis_state.get("is_high_risk"):
                logger.warning(f"[ChatService] Active crisis state — routing to CrisisAgent")
                return await self._dispatch(
                    AgentID.CRISIS,
                    {
                        "context": {
                            "conv_id": conversation_id,
                            "user_id": user_id,
                            "message": message,
                            "language": language,
                            "preliminary_slots": {},
                        }
                    },
                    gs,
                )

            # ── Step 2: Supervisor routes ────────────────────────────────────
            routing = await self._supervisor.run(
                {
                    "message": message,
                    "conv_id": conversation_id,
                    "user_id": user_id,
                    "language": language,
                },
                gs,
            )

            target_agent: str = routing["target_agent"]
            context: dict = routing["context"]

            emitter.emit_routing_decided(
                agent_id=AgentID.SUPERVISOR,
                intent=context.get("intent", "unknown"),
                target_agent=target_agent,
            )

            # ── Step 3: Dispatch to domain agent ─────────────────────────────
            result = await self._dispatch(target_agent, {"context": context}, gs)

            return result

        except Exception as e:
            logger.error(f"[ChatService] Error: {e}", exc_info=True)
            gs["error"] = str(e)

            # Safe fallback
            return {
                "response": (
                    "Mình gặp một chút trục trặc kỹ thuật. "
                    "Bạn có thể thử lại được không? "
                    "Nếu vấn đề tiếp tục, xin liên hệ hỗ trợ."
                ),
                "agent_id": "system",
                "error": str(e),
                "intent": "error",
            }

    async def _dispatch(
        self,
        agent_id: str,
        input: dict[str, Any],
        gs: GlobalState,
    ) -> dict[str, Any]:
        """
        Dispatch to a specific domain agent by ID.
        """
        agent = self._domain_agents.get(agent_id)

        if agent is None:
            logger.error(f"[ChatService] Agent not found: {agent_id}")
            return {
                "response": "Agent không tìm thấy.",
                "agent_id": agent_id,
                "error": f"Agent {agent_id} not registered",
            }

        gs["target_agent"] = agent_id

        logger.info(f"[ChatService] Dispatching to {agent_id}")

        try:
            result = await agent.run(input, gs)
            result["agent_id"] = agent_id
            return result
        except Exception as e:
            logger.error(f"[ChatService] {agent_id} failed: {e}", exc_info=True)
            emitter.emit_agent_error(agent_id, str(e))
            return {
                "response": (
                    "Mình gặp khó khăn khi xử lý yêu cầu của bạn. "
                    "Bạn có thể chia sẻ lại không?"
                ),
                "agent_id": agent_id,
                "error": str(e),
                "intent": gs.get("intent", "unknown"),
            }

    # ── Public accessors ────────────────────────────────────────────────────

    def get_memory_service(self) -> MemoryService:
        return self._memory

    def get_supervisor(self) -> Any:
        return self._supervisor

    def get_domain_agent(self, agent_id: str) -> Optional[BaseAgent]:
        return self._domain_agents.get(agent_id)
