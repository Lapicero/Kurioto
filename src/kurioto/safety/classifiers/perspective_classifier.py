"""
Perspective API safety classifier for toxicity detection.

Google's Perspective API provides:
- State-of-the-art toxicity detection
- Multiple toxicity attributes (profanity, threats, insults, etc.)
- Probability scores for nuanced filtering
- Child-specific content analysis

This is used as a secondary LLM layer specializing in harmful language detection.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from kurioto.config import get_settings
from kurioto.logging import get_logger
from kurioto.safety.base import (
    BaseSafetyClassifier,
    SafetyAction,
    SafetyCategory,
    SafetyResult,
    SafetySeverity,
)

logger = get_logger(__name__)

# Map Perspective API attributes to our categories
PERSPECTIVE_CATEGORY_MAP = {
    "TOXICITY": SafetyCategory.HARASSMENT,
    "SEVERE_TOXICITY": SafetyCategory.HARASSMENT,
    "IDENTITY_ATTACK": SafetyCategory.HATE_SPEECH,
    "INSULT": SafetyCategory.HARASSMENT,
    "PROFANITY": SafetyCategory.PROFANITY,
    "THREAT": SafetyCategory.VIOLENCE,
    "SEXUALLY_EXPLICIT": SafetyCategory.SEXUAL,
    "FLIRTATION": SafetyCategory.SEXUAL,
}


class PerspectiveAPIClassifier(BaseSafetyClassifier):
    """
    Safety classifier using Google's Perspective API.

    Specializes in detecting toxic, harmful, and inappropriate language.
    Works alongside Gemini for comprehensive safety coverage.
    """

    # API endpoint
    API_URL = "https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze"

    # Attributes to request from Perspective API
    REQUESTED_ATTRIBUTES = [
        "TOXICITY",
        "SEVERE_TOXICITY",
        "IDENTITY_ATTACK",
        "INSULT",
        "PROFANITY",
        "THREAT",
    ]

    # Thresholds for different age groups (more strict for younger)
    AGE_THRESHOLDS = {
        "early_childhood": {
            "block": 0.3,  # Very strict
            "review": 0.15,
        },
        "middle_childhood": {
            "block": 0.4,
            "review": 0.25,
        },
        "late_childhood": {
            "block": 0.5,
            "review": 0.35,
        },
        "early_teen": {
            "block": 0.6,
            "review": 0.45,
        },
        "late_teen": {
            "block": 0.7,
            "review": 0.55,
        },
    }

    def __init__(
        self,
        api_key: str | None = None,
        fail_safe: bool = True,
    ):
        """
        Initialize Perspective API classifier.

        Args:
            api_key: Google API key with Perspective API enabled.
                    If None, reads from PERSPECTIVE_API_KEY env var or settings.
            fail_safe: If True, block content when API fails.
        """
        super().__init__(fail_safe=fail_safe)
        import os

        settings = get_settings()
        self._api_key = (
            api_key or os.getenv("PERSPECTIVE_API_KEY") or settings.google_api_key
        )

    @property
    def name(self) -> str:
        return "perspective_api"

    @property
    def is_available(self) -> bool:
        """Check if Perspective API is configured."""
        return bool(self._api_key and self._api_key != "your_api_key_here")

    async def classify(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> SafetyResult:
        """
        Classify text using Perspective API.

        Returns toxicity scores and safety classification based on
        the child's age group.
        """
        if not self.is_available:
            return self._fail_safe_result("Perspective API key not configured")

        # Skip very short text (API doesn't handle well)
        if len(text.strip()) < 3:
            return SafetyResult(
                action=SafetyAction.ALLOW,
                reason="Text too short for toxicity analysis",
                severity=SafetySeverity.NONE,
                categories=[SafetyCategory.NONE],
                confidence=0.5,
                classifier_name=self.name,
            )

        try:
            # Get age group for threshold selection
            age_group = (context or {}).get("age_group", "middle_childhood")
            if hasattr(age_group, "value"):
                age_group = age_group.value
            thresholds = self.AGE_THRESHOLDS.get(
                age_group, self.AGE_THRESHOLDS["middle_childhood"]
            )

            # Make API request
            scores = await self._analyze_text(text)

            # Process scores
            return self._process_scores(scores, thresholds)

        except Exception as e:
            logger.error("perspective_classify_error", error=str(e))
            return self._fail_safe_result(str(e))

    async def _analyze_text(self, text: str) -> dict[str, float]:
        """Call Perspective API and return attribute scores."""

        request_body = {
            "comment": {"text": text},
            "requestedAttributes": {attr: {} for attr in self.REQUESTED_ATTRIBUTES},
            "languages": ["en"],
        }

        url = f"{self.API_URL}?key={self._api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request_body) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Perspective API error: {response.status} - {error_text}"
                    )

                data = await response.json()

        # Extract scores from response
        scores = {}
        for attr, attr_data in data.get("attributeScores", {}).items():
            score = attr_data.get("summaryScore", {}).get("value", 0.0)
            scores[attr] = score

        return scores

    def _process_scores(
        self,
        scores: dict[str, float],
        thresholds: dict[str, float],
    ) -> SafetyResult:
        """Process Perspective API scores into a SafetyResult."""
        max_score = 0.0
        max_attribute = None
        detected_categories = []

        for attr, score in scores.items():
            if score > max_score:
                max_score = score
                max_attribute = attr

            # Track categories that exceed review threshold
            if score >= thresholds["review"]:
                category = PERSPECTIVE_CATEGORY_MAP.get(attr, SafetyCategory.NONE)
                if category not in detected_categories:
                    detected_categories.append(category)

        # Determine action based on max score
        if max_score >= thresholds["block"]:
            action = SafetyAction.BLOCK
            severity = SafetySeverity.HIGH if max_score > 0.8 else SafetySeverity.MEDIUM
            reason = f"High toxicity detected: {max_attribute} ({max_score:.2f})"
            parent_alert = True
        elif max_score >= thresholds["review"]:
            action = SafetyAction.REVIEW
            severity = SafetySeverity.MEDIUM if max_score > 0.5 else SafetySeverity.LOW
            reason = f"Moderate toxicity detected: {max_attribute} ({max_score:.2f})"
            parent_alert = max_score > 0.5
        else:
            action = SafetyAction.ALLOW
            severity = SafetySeverity.NONE
            reason = "No significant toxicity detected"
            parent_alert = False
            detected_categories = [SafetyCategory.NONE]

        return SafetyResult(
            action=action,
            reason=reason,
            severity=severity,
            categories=detected_categories,
            confidence=0.85,  # Perspective API is quite reliable
            parent_alert=parent_alert,
            classifier_name=self.name,
            raw_scores=scores,
            metadata={"max_attribute": max_attribute, "max_score": max_score},
        )


class MockPerspectiveClassifier(BaseSafetyClassifier):
    """
    Mock Perspective API classifier for testing and development.

    Uses simple keyword matching to simulate toxicity detection
    without making actual API calls.
    """

    TOXIC_KEYWORDS = {
        "hate": 0.8,
        "stupid": 0.4,
        "idiot": 0.6,
        "dumb": 0.35,
        "ugly": 0.45,
        "kill": 0.7,
        "die": 0.5,
        "hurt": 0.4,
    }

    @property
    def name(self) -> str:
        return "perspective_api_mock"

    @property
    def is_available(self) -> bool:
        """Mock is always available."""
        return True

    async def classify(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> SafetyResult:
        """Mock classification based on keyword matching."""
        text_lower = text.lower()
        max_score = 0.0
        detected_word = None

        for word, score in self.TOXIC_KEYWORDS.items():
            if word in text_lower:
                if score > max_score:
                    max_score = score
                    detected_word = word

        # Get thresholds based on age group
        age_group = (context or {}).get("age_group", "middle_childhood")
        if hasattr(age_group, "value"):
            age_group = age_group.value
        thresholds = PerspectiveAPIClassifier.AGE_THRESHOLDS.get(
            age_group, PerspectiveAPIClassifier.AGE_THRESHOLDS["middle_childhood"]
        )

        if max_score >= thresholds["block"]:
            return SafetyResult(
                action=SafetyAction.BLOCK,
                reason=f"Mock toxicity detected: '{detected_word}' (score: {max_score})",
                severity=SafetySeverity.MEDIUM,
                categories=[SafetyCategory.HARASSMENT],
                confidence=0.7,
                parent_alert=True,
                classifier_name=self.name,
                metadata={"mock": True, "detected_word": detected_word},
            )
        elif max_score >= thresholds["review"]:
            return SafetyResult(
                action=SafetyAction.REVIEW,
                reason=f"Mock mild toxicity: '{detected_word}' (score: {max_score})",
                severity=SafetySeverity.LOW,
                categories=[SafetyCategory.PROFANITY],
                confidence=0.6,
                classifier_name=self.name,
                metadata={"mock": True},
            )
        else:
            return SafetyResult(
                action=SafetyAction.ALLOW,
                reason="No toxicity detected (mock)",
                severity=SafetySeverity.NONE,
                categories=[SafetyCategory.NONE],
                confidence=0.7,
                classifier_name=self.name,
                metadata={"mock": True},
            )
