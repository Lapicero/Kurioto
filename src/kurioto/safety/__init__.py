"""
Multi-layer safety evaluation system for Kurioto.

This module provides a comprehensive safety architecture:
1. Fast regex-based blocklist (first pass)
2. Google Gemini with safety settings (semantic analysis)
3. Perspective API for toxicity detection
4. Human review queue for edge cases

The system is designed to be fail-safe: if any layer fails,
content is blocked by default for child safety.
"""

from kurioto.safety.base import (
    BaseSafetyClassifier,
    SafetyAction,
    SafetyCategory,
    SafetyClassifier,
    SafetyResult,
    SafetySeverity,
)
from kurioto.safety.classifiers import (
    GeminiSafetyClassifier,
    MockPerspectiveClassifier,
    PerspectiveAPIClassifier,
    RegexSafetyClassifier,
)
from kurioto.safety.evaluator import SafetyEvaluator
from kurioto.safety.multi_layer import MultiLayerResult, MultiLayerSafetyEvaluator
from kurioto.safety.review_queue import (
    HumanReviewQueue,
    ReviewPriority,
    ReviewQueueItem,
    ReviewStatus,
    get_review_queue,
)

__all__ = [
    # Base types
    "SafetyAction",
    "SafetyCategory",
    "SafetyClassifier",
    "SafetyResult",
    "SafetySeverity",
    "BaseSafetyClassifier",
    # Classifiers
    "RegexSafetyClassifier",
    "GeminiSafetyClassifier",
    "PerspectiveAPIClassifier",
    "MockPerspectiveClassifier",
    # Multi-layer system
    "MultiLayerResult",
    "MultiLayerSafetyEvaluator",
    "SafetyEvaluator",
    # Review queue
    "HumanReviewQueue",
    "ReviewPriority",
    "ReviewQueueItem",
    "ReviewStatus",
    "get_review_queue",
]
