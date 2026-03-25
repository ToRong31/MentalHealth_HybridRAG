"""
Lightweight @tool decorator for skill tool definitions.

Each tool receives agent_state (local state dict) as its first positional arg,
enabling tools to update progress / track goal completion.

Example:
    @tool(name="milvus_search", description="Search vectors in Milvus")
    def milvus_search(agent_state: dict, milvus_client, query_vector, top_k):
        agent_state["step"] = "searching"
        ...
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable


@dataclass
class ToolSpec:
    name: str
    description: str


def tool(name: str | None = None, description: str = ""):
    """
    Decorator to mark a callable as a tool with agent_state injection.

    The decorated function's signature should start with ``agent_state: dict``.
    The decorator injects it automatically, so callers pass args from position 1.

    Example:
        @tool(name="vector_search", description="Search vectors in Milvus")
        def vector_search(agent_state: dict, milvus_client, query_vector, top_k=10):
            agent_state["step"] = "searching"
            ...
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        spec = ToolSpec(
            name=name or fn.__name__,
            description=description or (fn.__doc__ or "").strip(),
        )

        @wraps(fn)
        def wrapper(agent_state: dict, *args: Any, **kwargs: Any) -> Any:
            return fn(agent_state, *args, **kwargs)

        setattr(wrapper, "tool_spec", spec)
        return wrapper

    return decorator
