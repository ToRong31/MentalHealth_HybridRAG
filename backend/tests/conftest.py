"""
pytest configuration — shared fixtures and setup.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root and ai/ are on path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "ai"))

import pytest

# Disable LangSmith tracing during tests
import os

os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")


@pytest.fixture
def sample_agent_request():
    """Sample AgentRequest for testing."""
    from ai.shared.communication.http_schemas import AgentRequest

    return AgentRequest(
        message="Tôi cảm thấy lo âu về công việc",
        conversation_id="test-conv-1",
        user_id="test-user-1",
        language="vi",
    )


@pytest.fixture
def sample_global_state():
    """Sample GlobalState for testing."""
    from ai.shared.agent_based.state import GlobalState

    return GlobalState(
        conversation_id="test-conv-1",
        user_id="test-user-1",
        language="vi",
        original_message="Tôi cảm thấy lo âu",
    )
