"""
Routing tools for SupervisorAgent.
"""

from __future__ import annotations

from typing import Any


def route_to_agent(intent: str, domain_agents: dict[str, Any] | None = None) -> str:
    """
    Map classified intent string to target agent ID.

    Parameters
    ----------
    intent : str
        Classified intent (e.g. "diagnostic", "support").
    domain_agents : dict | None
        Optional dict of available domain agents. If provided and non-empty,
        validates that target agent exists in the dict.

    Returns
    -------
    str
        Agent ID string: "diagnostic" | "theory" | "treatment" | "support" | "crisis"
    """
    from ai.shared.agent_based.constants import AgentID

    mapping: dict[str, str] = {
        "diagnostic": AgentID.DIAGNOSTIC,
        "theory": AgentID.THEORY,
        "treatment": AgentID.TREATMENT,
        "support": AgentID.SUPPORT,
        "crisis": AgentID.CRISIS,
    }

    target = mapping.get(intent, AgentID.SUPPORT)

    # Only validate against domain_agents if it was actually populated
    # (empty dict means standalone microservice mode using HTTP routing)
    if domain_agents and target not in domain_agents:
        # Fallback to support if specific agent not available
        return AgentID.SUPPORT

    return target


def build_routing_context(
    original_message: str,
    translated_message: str,
    language: str,
    preliminary_slots: dict,
    intent: str,
    conv_id: str,
) -> dict:
    """
    Build the routing context dict passed to the domain agent.
    This is the canonical input format for all domain agents.
    """
    return {
        "original_message": original_message,
        "translated_message": translated_message,
        "language": language,
        "preliminary_slots": preliminary_slots,
        "intent": intent,
        "conv_id": conv_id,
    }
