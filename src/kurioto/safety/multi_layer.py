"""
Multi-layer safety evaluation system.

Orchestrates multiple safety classifiers in a layered approach:
1. Regex blocklist (fast, cheap, catches obvious violations)
2. Perspective API (toxicity detection specialist)
3. Gemini (semantic analysis, age-appropriate content)
4. Human review queue (edge cases, low confidence)

The system is designed to be:
- Fail-safe: blocks content if any classifier fails
- Efficient: fast layers run first to avoid expensive API calls
- Comprehensive: multiple perspectives catch different issues
- Transparent: provides detailed audit trail
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from kurioto.config import AgeGroup, ChildProfile
from kurioto.logging import get_logger
from kurioto.safety.base import (
    BaseSafetyClassifier,
    SafetyAction,
    SafetyCategory,
    SafetyResult,
    SafetySeverity,
)
from kurioto.safety.classifiers import (
    GeminiSafetyClassifier,
    MockPerspectiveClassifier,
    PerspectiveAPIClassifier,
    RegexSafetyClassifier,
)
from kurioto.safety.review_queue import (
    HumanReviewQueue,
    ReviewPriority,
    get_review_queue,
)

logger = get_logger(__name__)


@dataclass
class MultiLayerResult:
    """Result from the multi-layer safety evaluation."""

    final_action: SafetyAction
    final_reason: str
    final_severity: SafetySeverity
    layer_results: list[SafetyResult] = field(default_factory=list)
    review_item_id: str | None = None  # If sent to human review
    execution_time_ms: float = 0.0
    layers_executed: list[str] = field(default_factory=list)

    def to_safety_result(self) -> SafetyResult:
        """Convert to a standard SafetyResult for backwards compatibility."""
        categories = []
        for result in self.layer_results:
            categories.extend(result.categories)
        categories = list(set(categories))  # Deduplicate

        parent_alert = any(r.parent_alert for r in self.layer_results)

        return SafetyResult(
            action=self.final_action,
            reason=self.final_reason,
            severity=self.final_severity,
            categories=categories or [SafetyCategory.NONE],
            confidence=self._calculate_confidence(),
            parent_alert=parent_alert,
            classifier_name="multi_layer",
            metadata={
                "layers_executed": self.layers_executed,
                "review_item_id": self.review_item_id,
                "execution_time_ms": self.execution_time_ms,
            },
        )

    def _calculate_confidence(self) -> float:
        """Calculate overall confidence from layer results."""
        if not self.layer_results:
            return 0.0
        # Weight more recent (later) layers higher
        total_weight = 0.0
        weighted_sum = 0.0
        for i, result in enumerate(self.layer_results):
            weight = 1.0 + (i * 0.5)  # Later layers have higher weight
            weighted_sum += result.confidence * weight
            total_weight += weight
        return weighted_sum / total_weight if total_weight > 0 else 0.0


class MultiLayerSafetyEvaluator:
    """
    Orchestrates multi-layer safety evaluation.

    Layers (in order):
    1. Regex blocklist - Fast first pass
    2. Perspective API - Toxicity specialist
    3. Gemini - Semantic + age-appropriate
    4. Human review - Edge cases

    Early termination: If a high-confidence BLOCK is detected,
    skip remaining layers to save API costs.
    """

    def __init__(
        self,
        child_profile: ChildProfile,
        use_gemini: bool = True,
        use_perspective: bool = True,
        use_mock_perspective: bool = False,
        review_queue: HumanReviewQueue | None = None,
        early_termination_confidence: float = 0.9,
    ):
        """
        Initialize the multi-layer evaluator.

        Args:
            child_profile: Profile of the child user
            use_gemini: Enable Gemini classifier
            use_perspective: Enable Perspective API classifier
            use_mock_perspective: Use mock Perspective (for testing)
            review_queue: Custom review queue (uses global if None)
            early_termination_confidence: Skip layers if confidence exceeds this
        """
        self.child_profile = child_profile
        self.review_queue = review_queue or get_review_queue()
        self.early_termination_confidence = early_termination_confidence

        # Initialize classifiers
        self.classifiers: list[BaseSafetyClassifier] = []

        # Layer 1: Regex (always on, no external dependencies)
        self.regex_classifier = RegexSafetyClassifier()
        self.classifiers.append(self.regex_classifier)

        # Layer 2: Perspective API
        if use_perspective:
            if use_mock_perspective:
                self.perspective_classifier = MockPerspectiveClassifier()
            else:
                self.perspective_classifier = PerspectiveAPIClassifier()
            if self.perspective_classifier.is_available:
                self.classifiers.append(self.perspective_classifier)

        # Layer 3: Gemini
        if use_gemini:
            self.gemini_classifier = GeminiSafetyClassifier()
            if self.gemini_classifier.is_available:
                self.classifiers.append(self.gemini_classifier)

        logger.info(
            "multi_layer_init",
            child_id=child_profile.child_id,
            classifiers=[c.name for c in self.classifiers],
        )

    def _get_context(self) -> dict[str, Any]:
        """Build context dict from child profile."""
        return {
            "age": self.child_profile.age,
            "age_group": self.child_profile.age_group,
            "allowed_topics": self.child_profile.allowed_topics,
            "blocked_topics": self.child_profile.blocked_topics,
        }

    async def evaluate(
        self,
        text: str,
        skip_human_review: bool = False,
    ) -> MultiLayerResult:
        """
        Evaluate text through all safety layers.

        Args:
            text: The text to evaluate
            skip_human_review: If True, don't add to review queue

        Returns:
            MultiLayerResult with comprehensive evaluation
        """
        import time

        start_time = time.time()

        context = self._get_context()
        layer_results: list[SafetyResult] = []
        layers_executed: list[str] = []

        current_action = SafetyAction.ALLOW
        current_reason = "No safety concerns detected"
        current_severity = SafetySeverity.NONE

        # Run through classifiers in order
        for classifier in self.classifiers:
            try:
                result = await classifier.classify(text, context)
                layer_results.append(result)
                layers_executed.append(classifier.name)

                logger.debug(
                    "layer_result",
                    classifier=classifier.name,
                    action=result.action.value,
                    confidence=result.confidence,
                )

                # Update current decision based on this layer
                current_action, current_reason, current_severity = self._merge_decision(
                    current_action,
                    current_reason,
                    current_severity,
                    result,
                )

                # Early termination for high-confidence blocks
                if (
                    result.action == SafetyAction.BLOCK
                    and result.confidence >= self.early_termination_confidence
                ):
                    logger.info(
                        "early_termination",
                        classifier=classifier.name,
                        confidence=result.confidence,
                    )
                    break

            except Exception as e:
                logger.error(
                    "classifier_error",
                    classifier=classifier.name,
                    error=str(e),
                )
                # Fail-safe: treat classifier failure as concerning
                layer_results.append(
                    SafetyResult(
                        action=SafetyAction.REVIEW,
                        reason=f"Classifier {classifier.name} failed: {e}",
                        severity=SafetySeverity.MEDIUM,
                        confidence=0.0,
                        classifier_name=classifier.name,
                    )
                )
                current_action = SafetyAction.REVIEW
                current_reason = f"Safety evaluation incomplete: {e}"
                current_severity = SafetySeverity.MEDIUM

        # Handle REVIEW action - add to human review queue
        review_item_id = None
        if current_action == SafetyAction.REVIEW and not skip_human_review:
            review_item = await self.review_queue.add_for_review(
                content=text,
                child_id=self.child_profile.child_id,
                classifier_results=layer_results,
            )
            review_item_id = review_item.id

            # For safety, block while awaiting review
            current_action = SafetyAction.BLOCK
            current_reason = f"Content flagged for human review (ID: {review_item_id})"

        execution_time = (time.time() - start_time) * 1000

        return MultiLayerResult(
            final_action=current_action,
            final_reason=current_reason,
            final_severity=current_severity,
            layer_results=layer_results,
            review_item_id=review_item_id,
            execution_time_ms=execution_time,
            layers_executed=layers_executed,
        )

    def _merge_decision(
        self,
        current_action: SafetyAction,
        current_reason: str,
        current_severity: SafetySeverity,
        new_result: SafetyResult,
    ) -> tuple[SafetyAction, str, SafetySeverity]:
        """
        Merge a new classifier result with the current decision.

        Decision priority (highest to lowest):
        1. BLOCK - Any block overrides everything
        2. REVIEW - Flag for human review
        3. REDIRECT - Safe alternative available
        4. WARN_PARENT - Allow but notify
        5. SIMPLIFY - Needs age adaptation
        6. ALLOW - Safe to proceed
        """
        action_priority = {
            SafetyAction.BLOCK: 6,
            SafetyAction.REVIEW: 5,
            SafetyAction.REDIRECT: 4,
            SafetyAction.WARN_PARENT: 3,
            SafetyAction.SIMPLIFY: 2,
            SafetyAction.ALLOW: 1,
        }

        # Take the higher-priority action
        if action_priority[new_result.action] > action_priority[current_action]:
            return new_result.action, new_result.reason, new_result.severity

        # If same priority, take higher severity
        if (
            action_priority[new_result.action] == action_priority[current_action]
            and new_result.severity.value > current_severity.value
        ):
            return current_action, new_result.reason, new_result.severity

        return current_action, current_reason, current_severity

    async def evaluate_output(self, response: str) -> MultiLayerResult:
        """
        Evaluate agent output before sending to child.

        Uses the same multi-layer approach but with output-specific context.
        """
        # For output, we're more concerned about accidentally leaked content
        # and age-appropriateness than about dangerous requests
        result = await self.evaluate(response, skip_human_review=True)

        # Additional check: complexity for young children
        if self.child_profile.age_group in [
            AgeGroup.EARLY_CHILDHOOD,
            AgeGroup.MIDDLE_CHILDHOOD,
        ]:
            complexity_result = self._check_output_complexity(response)
            if complexity_result:
                result.layer_results.append(complexity_result)
                if complexity_result.action.value > result.final_action.value:
                    result.final_action = complexity_result.action
                    result.final_reason = complexity_result.reason

        return result

    def _check_output_complexity(self, text: str) -> SafetyResult | None:
        """Check if output text is too complex for the child's age."""
        words = text.split()
        if not words:
            return None

        avg_word_length = sum(len(w) for w in words) / len(words)
        sentence_count = text.count(".") + text.count("!") + text.count("?")
        avg_sentence_length = len(words) / max(sentence_count, 1)

        # Thresholds based on age group
        if self.child_profile.age_group == AgeGroup.EARLY_CHILDHOOD:
            if avg_word_length > 6 or avg_sentence_length > 12:
                return SafetyResult(
                    action=SafetyAction.SIMPLIFY,
                    reason="Response may be too complex for early childhood",
                    severity=SafetySeverity.LOW,
                    categories=[SafetyCategory.AGE_INAPPROPRIATE],
                    confidence=0.7,
                    classifier_name="complexity_check",
                )
        elif self.child_profile.age_group == AgeGroup.MIDDLE_CHILDHOOD:
            if avg_word_length > 7 or avg_sentence_length > 18:
                return SafetyResult(
                    action=SafetyAction.SIMPLIFY,
                    reason="Response may be too complex for middle childhood",
                    severity=SafetySeverity.LOW,
                    categories=[SafetyCategory.AGE_INAPPROPRIATE],
                    confidence=0.7,
                    classifier_name="complexity_check",
                )

        return None

    def get_age_appropriate_guidelines(self) -> str:
        """Get guidelines for the LLM based on child's age group."""
        guidelines = {
            AgeGroup.EARLY_CHILDHOOD: """
- Use very simple words (1-2 syllables preferred)
- Keep sentences short (5-10 words)
- Use concrete examples and comparisons to familiar things
- Be warm, encouraging, and playful
- Avoid abstract concepts
- Use lots of analogies to everyday objects""",
            AgeGroup.MIDDLE_CHILDHOOD: """
- Use simple but varied vocabulary
- Keep sentences moderate length (8-15 words)
- Explain concepts with relatable examples
- Be friendly and encouraging
- Can introduce some abstract ideas with concrete support
- Use analogies and "like" comparisons""",
            AgeGroup.LATE_CHILDHOOD: """
- Use age-appropriate vocabulary
- Can handle longer explanations
- Encourage curiosity and follow-up questions
- Be informative but approachable
- Can discuss more complex topics at basic level""",
            AgeGroup.EARLY_TEEN: """
- Use standard vocabulary
- Can handle nuanced explanations
- Treat them with respect for their growing independence
- Be informative and engaging
- Can discuss complex topics appropriately""",
            AgeGroup.LATE_TEEN: """
- Use full vocabulary
- Provide detailed, accurate information
- Treat them as young adults
- Be informative and direct
- Can discuss most educational topics in depth""",
        }
        return guidelines.get(
            self.child_profile.age_group,
            guidelines[AgeGroup.MIDDLE_CHILDHOOD],
        )
