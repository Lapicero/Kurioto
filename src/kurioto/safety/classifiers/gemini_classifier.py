"""
Gemini-based safety classifier using Google's built-in safety settings.

This classifier leverages:
- Gemini's native safety filters (HARM_CATEGORY_*)
- Semantic understanding of content
- Context-aware safety decisions
- Age-appropriate content assessment

This is the primary LLM-based safety layer for production use.
"""

from __future__ import annotations

import json
from typing import Any

import google.generativeai as genai

from kurioto.config import AgeGroup, get_settings
from kurioto.logging import get_logger
from kurioto.safety.base import (
    BaseSafetyClassifier,
    SafetyAction,
    SafetyCategory,
    SafetyResult,
    SafetySeverity,
)

logger = get_logger(__name__)

# Map Gemini harm categories to our internal categories
GEMINI_CATEGORY_MAP = {
    "HARM_CATEGORY_HARASSMENT": SafetyCategory.HARASSMENT,
    "HARM_CATEGORY_HATE_SPEECH": SafetyCategory.HATE_SPEECH,
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": SafetyCategory.SEXUAL,
    "HARM_CATEGORY_DANGEROUS_CONTENT": SafetyCategory.DANGEROUS,
    "HARM_CATEGORY_CIVIC_INTEGRITY": SafetyCategory.DECEPTION,
}

# Map Gemini probability levels to our severity
GEMINI_PROBABILITY_MAP = {
    "NEGLIGIBLE": SafetySeverity.NONE,
    "LOW": SafetySeverity.LOW,
    "MEDIUM": SafetySeverity.MEDIUM,
    "HIGH": SafetySeverity.HIGH,
}


class GeminiSafetyClassifier(BaseSafetyClassifier):
    """
    Safety classifier using Google Gemini with built-in safety settings.

    Uses Gemini's native content filtering plus a custom safety assessment
    prompt for child-specific concerns.
    """

    # Safety assessment prompt template
    SAFETY_PROMPT = """You are a child safety content evaluator for an AI companion designed for children ages 3-17.

Analyze the following text for safety concerns. Consider:
1. Is this content appropriate for children of age {age}?
2. Does it contain violence, adult themes, or dangerous instructions?
3. Does it attempt to extract personal information?
4. Is the language and complexity appropriate for the age group?
5. Could this content cause harm if a child acts on it?

Text to analyze:
"{text}"

Respond with a JSON object:
{{
    "is_safe": true/false,
    "confidence": 0.0-1.0,
    "categories": ["list of concern categories if unsafe"],
    "severity": "none|low|medium|high|critical",
    "reason": "brief explanation",
    "age_appropriate": true/false,
    "suggested_action": "allow|block|redirect|simplify|review"
}}

Only respond with the JSON object, no other text."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-2.0-flash",
        fail_safe: bool = True,
    ):
        """
        Initialize Gemini safety classifier.

        Args:
            api_key: Google API key. If None, reads from settings.
            model_name: Gemini model to use for safety assessment.
            fail_safe: If True, block content when API fails.
        """
        super().__init__(fail_safe=fail_safe)
        settings = get_settings()
        self._api_key = api_key or settings.google_api_key
        self._model_name = model_name
        self._client = None
        self._model = None

    @property
    def name(self) -> str:
        return "gemini_safety"

    @property
    def is_available(self) -> bool:
        """Check if Gemini API is configured."""
        return bool(self._api_key and self._api_key != "your_api_key_here")

    def _get_client(self):
        """Lazy-load the Gemini client."""
        if self._client is None:
            try:
                genai.configure(api_key=self._api_key)
                self._client = genai

                # Configure safety settings for the model - we want to receive
                # safety ratings, not have content blocked before we see it
                self._model = genai.GenerativeModel(
                    model_name=self._model_name,
                    safety_settings={
                        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
                    },
                )
            except ImportError:
                logger.error(
                    "gemini_import_error", error="google-generativeai not installed"
                )
                raise
        return self._client

    async def classify(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> SafetyResult:
        """
        Classify text using Gemini's safety analysis.

        Uses both Gemini's built-in safety ratings and a custom safety
        assessment prompt for child-specific concerns.
        """
        if not self.is_available:
            return self._fail_safe_result("Gemini API key not configured")

        try:
            self._get_client()

            # Get child's age for age-appropriate assessment
            age = (context or {}).get("age", 10)
            age_group = (context or {}).get("age_group", AgeGroup.MIDDLE_CHILDHOOD)

            # Format the safety assessment prompt
            prompt = self.SAFETY_PROMPT.format(age=age, text=text)

            # Make the API call
            response = await self._async_generate(prompt)

            # Parse the response
            return self._parse_response(response, text, age_group)

        except Exception as e:
            logger.error("gemini_classify_error", error=str(e))
            return self._fail_safe_result(str(e))

    async def _async_generate(self, prompt: str) -> Any:
        """Generate content asynchronously."""
        import asyncio

        # google-generativeai doesn't have native async, so we run in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._model.generate_content(prompt)
        )

    def _parse_response(
        self,
        response: Any,
        original_text: str,
        age_group: AgeGroup,
    ) -> SafetyResult:
        """Parse Gemini response into SafetyResult."""
        try:
            # First, check Gemini's built-in safety ratings
            if hasattr(response, "prompt_feedback"):
                feedback = response.prompt_feedback
                if hasattr(feedback, "block_reason") and feedback.block_reason:
                    return SafetyResult(
                        action=SafetyAction.BLOCK,
                        reason=f"Gemini blocked content: {feedback.block_reason}",
                        severity=SafetySeverity.HIGH,
                        categories=[SafetyCategory.DANGEROUS],
                        confidence=0.95,
                        parent_alert=True,
                        classifier_name=self.name,
                    )

            # Extract safety ratings from candidates
            raw_scores = {}
            detected_categories = []
            max_severity = SafetySeverity.NONE

            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "safety_ratings"):
                    for rating in candidate.safety_ratings:
                        category_name = str(rating.category)
                        probability = str(rating.probability)

                        # Map to our types
                        our_category = GEMINI_CATEGORY_MAP.get(
                            category_name, SafetyCategory.NONE
                        )
                        our_severity = GEMINI_PROBABILITY_MAP.get(
                            probability, SafetySeverity.NONE
                        )

                        raw_scores[category_name] = probability

                        if our_severity.value > max_severity.value:
                            max_severity = our_severity
                        if our_severity >= SafetySeverity.MEDIUM:
                            detected_categories.append(our_category)

            # Parse the JSON response from our custom prompt
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            assessment = json.loads(response_text.strip())

            is_safe = assessment.get("is_safe", True)
            confidence = assessment.get("confidence", 0.8)
            severity_str = assessment.get("severity", "none")
            action_str = assessment.get("suggested_action", "allow")
            reason = assessment.get("reason", "No specific concerns")

            # Map string values to enums
            severity = (
                SafetySeverity(severity_str)
                if severity_str in [s.value for s in SafetySeverity]
                else max_severity
            )

            action_map = {
                "allow": SafetyAction.ALLOW,
                "block": SafetyAction.BLOCK,
                "redirect": SafetyAction.REDIRECT,
                "simplify": SafetyAction.SIMPLIFY,
                "review": SafetyAction.REVIEW,
            }
            action = action_map.get(
                action_str, SafetyAction.BLOCK if not is_safe else SafetyAction.ALLOW
            )

            # Add any categories from the assessment
            for cat_str in assessment.get("categories", []):
                try:
                    cat = SafetyCategory(cat_str)
                    if cat not in detected_categories:
                        detected_categories.append(cat)
                except ValueError:
                    pass

            # For younger children, be more conservative
            if age_group in [AgeGroup.EARLY_CHILDHOOD, AgeGroup.MIDDLE_CHILDHOOD]:
                if severity >= SafetySeverity.LOW and action == SafetyAction.ALLOW:
                    action = SafetyAction.SIMPLIFY
                if severity >= SafetySeverity.MEDIUM:
                    action = SafetyAction.BLOCK

            return SafetyResult(
                action=action,
                reason=reason,
                severity=severity,
                categories=detected_categories or [SafetyCategory.NONE],
                confidence=confidence,
                parent_alert=severity >= SafetySeverity.HIGH,
                classifier_name=self.name,
                raw_scores=raw_scores,
                metadata={"age_appropriate": assessment.get("age_appropriate", True)},
            )

        except json.JSONDecodeError as e:
            logger.warning("gemini_json_parse_error", error=str(e))
            # If we can't parse the response, use built-in ratings only
            if detected_categories and max_severity >= SafetySeverity.MEDIUM:
                return SafetyResult(
                    action=SafetyAction.BLOCK,
                    reason="Safety concern detected by Gemini ratings",
                    severity=max_severity,
                    categories=detected_categories,
                    confidence=0.7,
                    classifier_name=self.name,
                    raw_scores=raw_scores,
                )
            return SafetyResult(
                action=SafetyAction.ALLOW,
                reason="No safety concerns in Gemini ratings",
                severity=SafetySeverity.NONE,
                categories=[SafetyCategory.NONE],
                confidence=0.6,
                classifier_name=self.name,
                raw_scores=raw_scores,
            )

        except Exception as e:
            logger.error("gemini_parse_error", error=str(e))
            return self._fail_safe_result(f"Failed to parse Gemini response: {e}")
