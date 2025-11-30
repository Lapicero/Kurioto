"""
Kurioto: A Safe AI Companion for Curious Minds

This package implements a cloud-based AI agent designed specifically for children's
educational needs, featuring multi-step reasoning, tool integration, memory management,
and comprehensive safety governance.

Safety Architecture:
- Multi-layer safety evaluation (regex, Gemini, Perspective API)
- Human review queue for edge cases
- Age-appropriate content filtering
- Fail-safe design (blocks on uncertainty)
"""

__version__ = "0.1.0"
__author__ = "Lapicero"

from kurioto.agent import KuriotoAgent
from kurioto.config import ChildProfile, Settings
from kurioto.safety import (
    MultiLayerSafetyEvaluator,
    SafetyAction,
    SafetyEvaluator,
    SafetyResult,
)

__all__ = [
    "KuriotoAgent",
    "ChildProfile",
    "Settings",
    "SafetyEvaluator",
    "SafetyAction",
    "SafetyResult",
    "MultiLayerSafetyEvaluator",
    "__version__",
]
