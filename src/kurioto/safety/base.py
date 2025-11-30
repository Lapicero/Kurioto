"""
Base interfaces and types for the safety evaluation system.

Defines the protocol that all safety classifiers must implement,
along with shared enums and result types.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class SafetyAction(str, Enum):
    """Actions the safety system can take."""

    ALLOW = "allow"  # Content is safe, proceed
    BLOCK = "block"  # Content is unsafe, refuse completely
    REDIRECT = "redirect"  # Redirect to a safe alternative
    SIMPLIFY = "simplify"  # Simplify for age appropriateness
    REVIEW = "review"  # Flag for human review
    WARN_PARENT = "warn_parent"  # Allow but notify parent


class SafetySeverity(str, Enum):
    """Severity levels for safety issues."""

    NONE = "none"  # No safety concern
    LOW = "low"  # Minor concern, may need simplification
    MEDIUM = "medium"  # Moderate concern, redirect recommended
    HIGH = "high"  # Serious concern, block required
    CRITICAL = "critical"  # Immediate block, parent alert


class SafetyCategory(str, Enum):
    """Categories of safety concerns."""

    VIOLENCE = "violence"
    SEXUAL = "sexual"
    HATE_SPEECH = "hate_speech"
    HARASSMENT = "harassment"
    SELF_HARM = "self_harm"
    DANGEROUS = "dangerous"  # Instructions for dangerous activities
    DRUGS_ALCOHOL = "drugs_alcohol"
    PROFANITY = "profanity"
    PII = "personal_information"  # Personal information request
    DECEPTION = "deception"  # Attempts to deceive the AI
    AGE_INAPPROPRIATE = "age_inappropriate"  # Too complex or mature
    GAMBLING = "gambling"
    NONE = "none"  # No safety concern detected


@dataclass
class SafetyResult:
    """Result of a safety evaluation."""

    action: SafetyAction
    reason: str
    severity: SafetySeverity = SafetySeverity.NONE
    categories: list[SafetyCategory] = field(default_factory=list)
    confidence: float = 1.0  # 0.0 to 1.0, how confident the classifier is
    suggested_response: str | None = None
    parent_alert: bool = False
    classifier_name: str = "unknown"  # Which classifier produced this result
    raw_scores: dict[str, float] = field(default_factory=dict)  # Raw API scores
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_legacy_severity(self) -> str:
        """Convert to legacy string severity for backwards compatibility."""
        return self.severity.value


@runtime_checkable
class SafetyClassifier(Protocol):
    """
    Protocol for safety classifiers.

    All safety classifiers must implement this interface to be used
    in the multi-layer safety system.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this classifier."""
        ...

    @property
    def is_available(self) -> bool:
        """Check if the classifier is properly configured and available."""
        ...

    async def classify(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> SafetyResult:
        """
        Classify text for safety concerns.

        Args:
            text: The text to classify
            context: Optional context (child age, conversation history, etc.)

        Returns:
            SafetyResult with classification outcome
        """
        ...


class BaseSafetyClassifier(ABC):
    """
    Abstract base class for safety classifiers.

    Provides common functionality and enforces the classifier interface.
    """

    def __init__(self, fail_safe: bool = True):
        """
        Initialize the classifier.

        Args:
            fail_safe: If True, block content when classifier fails.
                       For child safety, this should always be True.
        """
        self.fail_safe = fail_safe

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this classifier."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the classifier is properly configured."""
        ...

    @abstractmethod
    async def classify(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> SafetyResult:
        """Classify text for safety concerns."""
        ...

    def _fail_safe_result(self, error: str) -> SafetyResult:
        """Return a fail-safe result when classifier fails."""
        if self.fail_safe:
            return SafetyResult(
                action=SafetyAction.BLOCK,
                reason=f"Safety classifier failed: {error}. Blocking for safety.",
                severity=SafetySeverity.HIGH,
                categories=[],
                confidence=0.0,
                classifier_name=self.name,
                parent_alert=True,
            )
        else:
            return SafetyResult(
                action=SafetyAction.ALLOW,
                reason=f"Safety classifier failed: {error}. Allowing (non-fail-safe mode).",
                severity=SafetySeverity.NONE,
                confidence=0.0,
                classifier_name=self.name,
            )
