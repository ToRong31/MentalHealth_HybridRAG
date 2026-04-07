"""
CrisisAgent skills package.
"""

from .crisis_detection import CrisisDetection
from .immediate_response import ImmediateResponse
from .professional_escalation import ProfessionalEscalation
from .follow_up_support import FollowUpSupport
from .documentation import Documentation

__all__ = [
    "CrisisDetection",
    "ImmediateResponse",
    "ProfessionalEscalation",
    "FollowUpSupport",
    "Documentation",
]
