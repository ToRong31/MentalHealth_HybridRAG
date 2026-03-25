"""
AI Engine — Application Factory.

Entry point that wires all agents + RAG infrastructure.
Called by FastAPI backend.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from ai.shared.agent_based.constants import AgentID
from ai.shared.services.memory_service import MemoryService
from ai.shared.communication.message_bus import MessageBus
from ai.shared.rag import MilvusClient, Neo4jClient, GeminiClient, CohereReranker

from ai.agents.supervisor.supervisor_agent import SupervisorAgent
from ai.agents.support.support_agent import SupportAgent
from ai.agents.crisis.crisis_agent import CrisisAgent
from ai.agents.theory.theory_agent import TheoryAgent
from ai.agents.treatment.treatment_agent import TreatmentAgent
from ai.agents.diagnostic.diagnostic_agent import DiagnosticAgent

from ai.services.chat_service import ChatService

logger = logging.getLogger(__name__)

# ─── RAG Factory ───────────────────────────────────────────────────────────────


def _create_milvus(config: dict[str, Any]) -> Optional[MilvusClient]:
    """Create Milvus client from config / env."""
    uri = config.get("milvus_uri") or os.getenv("MILVUS_HOST", "localhost")
    port = config.get("milvus_port") or os.getenv("MILVUS_PORT", "19530")
    collection = config.get("milvus_collection", "mental_health")
    token = config.get("milvus_token") or os.getenv("MILVUS_TOKEN", "")

    uri_full = f"http://{uri}:{port}" if not uri.startswith("http") else uri

    try:
        client = MilvusClient(
            uri=uri_full,
            collection=collection,
            token=token,
            hnsw_ef=config.get("milvus_hnsw_ef", 128),
        )
        logger.info("[AI Engine] Milvus client created: %s/%s", uri_full, collection)
        return client
    except Exception as e:
        logger.warning("[AI Engine] Milvus init failed: %s", e)
        return None


def _create_neo4j(config: dict[str, Any]) -> Optional[Neo4jClient]:
    """Create Neo4j client from config / env."""
    uri = config.get("neo4j_uri") or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = config.get("neo4j_user") or os.getenv("NEO4J_USER", "neo4j")
    password = config.get("neo4j_password") or os.getenv("NEO4J_PASSWORD", "")

    if not password:
        logger.warning("[AI Engine] NEO4J_PASSWORD not set — Neo4j disabled")
        return None

    try:
        client = Neo4jClient(uri=uri, user=user, password=password)
        logger.info("[AI Engine] Neo4j client created: %s", uri)
        return client
    except Exception as e:
        logger.warning("[AI Engine] Neo4j init failed: %s", e)
        return None


def _create_llm(config: dict[str, Any]) -> Optional[Any]:
    """Create Gemini LLM client from config / env."""
    api_key = config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")
    model = config.get("gemini_model", "gemini-1.5-flash")

    if not api_key:
        logger.warning("[AI Engine] GEMINI_API_KEY not set — LLM calls will use keyword fallback")
        return None

    try:
        client = GeminiClient(api_key=api_key, model=model)
        logger.info("[AI Engine] Gemini LLM client created: %s", model)
        return client
    except Exception as e:
        logger.warning("[AI Engine] Gemini init failed: %s", e)
        return None


def _create_reranker(config: dict[str, Any]) -> Optional[CohereReranker]:
    """Create Cohere reranker from config / env."""
    api_key = config.get("cohere_api_key") or os.getenv("COHERE_API_KEY", "")

    if not api_key:
        logger.debug("[AI Engine] COHERE_API_KEY not set — reranking disabled")
        return None

    try:
        client = CohereReranker(api_key=api_key)
        logger.info("[AI Engine] Cohere reranker created")
        return client
    except Exception as e:
        logger.warning("[AI Engine] Cohere init failed: %s", e)
        return None


# ─── Redis / DB ───────────────────────────────────────────────────────────────


def _create_redis_client() -> Any:
    """Create Redis client. Returns None if not configured."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        logger.warning("[AI Engine] REDIS_URL not set — using ephemeral L1 only")
        return None

    try:
        import redis
        return redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.warning("[AI Engine] Redis connection failed: %s", e)
        return None


def _create_db_session() -> Any:
    """DB session factory. Returns None if not configured."""
    # TODO: wire actual SQLAlchemy session factory
    return None


# ─── App Factory ───────────────────────────────────────────────────────────────


def create_ai_engine(
    config: dict[str, Any] | None = None,
    redis_client: Any = None,
    db_session_factory: Any = None,
) -> ChatService:
    """
    Wire and return a fully configured ChatService with RAG infrastructure.

    Usage:
        chat_service = create_ai_engine(config={
            "gemini_api_key": "...",
            "milvus_uri": "http://localhost:19530",
            "neo4j_uri": "bolt://localhost:7687",
            "neo4j_password": "...",
        })
        result = await chat_service.process_message(...)
    """
    config = config or {}

    # ── RAG Clients ────────────────────────────────────────────────────────
    milvus = _create_milvus(config)
    neo4j = _create_neo4j(config)
    llm = _create_llm(config)
    reranker = _create_reranker(config)

    # ── Memory ───────────────────────────────────────────────────────────
    memory_service = MemoryService(
        redis_client=redis_client or _create_redis_client(),
        db_session_factory=db_session_factory or _create_db_session(),
        max_buffer_size=config.get("max_buffer_size", 3),
        cache_ttl=config.get("cache_ttl", 3600),
    )

    # ── MessageBus ─────────────────────────────────────────────────────
    message_bus = MessageBus()

    # ── RAG config dict passed to agents ───────────────────────────────
    rag_config = {
        "milvus": milvus,
        "neo4j": neo4j,
        "reranker": reranker,
    }

    # ── Domain Agents ─────────────────────────────────────────────────
    domain_agents = {
        AgentID.SUPPORT:     SupportAgent(
            memory_service=memory_service,
            llm=llm,
            config={**config, **rag_config},
            message_bus=message_bus,
        ),
        AgentID.CRISIS:      CrisisAgent(
            memory_service=memory_service,
            llm=llm,
            config={**config, **rag_config},
            message_bus=message_bus,
        ),
        AgentID.THEORY:      TheoryAgent(
            memory_service=memory_service,
            llm=llm,
            config={**config, **rag_config},
            message_bus=message_bus,
        ),
        AgentID.TREATMENT:   TreatmentAgent(
            memory_service=memory_service,
            llm=llm,
            config={**config, **rag_config},
            message_bus=message_bus,
        ),
        AgentID.DIAGNOSTIC:  DiagnosticAgent(
            memory_service=memory_service,
            llm=llm,
            config={**config, **rag_config},
            message_bus=message_bus,
        ),
    }

    # ── Supervisor ──────────────────────────────────────────────────────
    supervisor = SupervisorAgent(
        memory_service=memory_service,
        llm=llm,
        config=config,
        message_bus=message_bus,
    )

    # ── ChatService ───────────────────────────────────────────────────
    chat_service = ChatService(
        supervisor=supervisor,
        domain_agents=domain_agents,
        memory_service=memory_service,
        message_bus=message_bus,
    )

    logger.info(
        "[AI Engine] Initialized — "
        "llm=%s, milvus=%s, neo4j=%s, reranker=%s, redis=%s, agents=%s",
        "yes" if llm else "NO",
        "yes" if milvus else "NO",
        "yes" if neo4j else "NO",
        "yes" if reranker else "NO",
        "yes" if memory_service._redis else "NO",
        list(domain_agents.keys()),
    )

    return chat_service


# ─── Singleton ────────────────────────────────────────────────────────────────

_ai_engine_instance: ChatService | None = None


def get_ai_engine() -> ChatService:
    """Get or create the singleton ChatService instance."""
    global _ai_engine_instance
    if _ai_engine_instance is None:
        _ai_engine_instance = create_ai_engine()
    return _ai_engine_instance


def reset_ai_engine() -> None:
    """Reset the singleton (for testing)."""
    global _ai_engine_instance
    _ai_engine_instance = None
    MessageBus._instance = None  # type: ignore
