"""
Safety evaluation for Kurioto.

Implements content filtering, topic blocking, and age-appropriate response
adaptation to ensure child safety.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from kurioto.config import AgeGroup, ChildProfile
from kurioto.logging import get_logger

logger = get_logger(__name__)


class SafetyAction(str, Enum):
    """Actions the safety evaluator can take."""

    ALLOW = "allow"  # Content is safe, proceed
    BLOCK = "block"  # Content is unsafe, refuse completely
    REDIRECT = "redirect"  # Redirect to a safe alternative
    SIMPLIFY = "simplify"  # Simplify for age appropriateness
    WARN_PARENT = "warn_parent"  # Allow but notify parent


@dataclass
class SafetyResult:
    """Result of a safety evaluation."""

    action: SafetyAction
    reason: str
    severity: str = "low"  # low, medium, high
    suggested_response: str | None = None
    parent_alert: bool = False


class SafetyEvaluator:
    """
    Evaluates content for child safety.

    Checks for:
    - Blocked topics (violence, adult content, etc.)
    - Age-inappropriate complexity
    - Dangerous instructions
    - Personal information requests

    Provides safe alternatives and redirects where possible.
    """

    # Topics that are always blocked regardless of age
    BLOCKED_TOPICS = [
        "weapon",
        "bomb",
        "explosive",
        "gun",
        "knife attack",
        "drugs",
        "alcohol",
        "smoking",
        "vaping",
        "suicide",
        "self-harm",
        "eating disorder",
        "pornography",
        "sexual",
        "nude",
        "gambling",
        "betting",
        "hacking",
        "malware",
        "virus",
    ]

    # Patterns for dangerous instructions
    DANGEROUS_PATTERNS = [
        r"how to (make|build|create) (a )?(bomb|weapon|explosive|gun)",
        r"how to (hurt|harm|kill|attack)",
        r"how to (steal|hack|break into)",
        r"(credit card|password|social security) number",
    ]

    # Patterns for personal information requests
    PII_PATTERNS = [
        r"(what is|tell me|give me) your (address|phone|school|password)",
        r"where do you live",
        r"what('s| is) your (real|full) name",
        r"(send|share) (me )?(a )?photo of (yourself|you)",
    ]

    # Safe redirects for common blocked topics
    SAFE_REDIRECTS = {
        "bomb": "I can't help with that because it's dangerous. But I can tell you how fireworks create bright colors!",
        "weapon": "I can't help with that. Would you like to learn about how knights protected castles instead?",
        "drugs": "That's not something I can help with. How about we learn about how doctors help people stay healthy?",
        "hacking": "I can't help with that. But I can teach you about how computers work to keep information safe!",
    }

    def __init__(self, child_profile: ChildProfile):
        self.profile = child_profile
        self._compile_patterns()
        logger.info(
            "safety_evaluator_init",
            child_id=child_profile.child_id,
            age_group=child_profile.age_group.value,
        )

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self._dangerous_re = [
            re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_PATTERNS
        ]
        self._pii_re = [re.compile(p, re.IGNORECASE) for p in self.PII_PATTERNS]

    def evaluate_input(self, user_input: str) -> SafetyResult:
        """
        Evaluate user input for safety concerns.

        Returns a SafetyResult indicating what action to take.
        """
        input_lower = user_input.lower()

        # Check for dangerous instruction requests
        for pattern in self._dangerous_re:
            if pattern.search(user_input):
                redirect = self._find_redirect(input_lower)
                return SafetyResult(
                    action=SafetyAction.REDIRECT if redirect else SafetyAction.BLOCK,
                    reason="Dangerous instruction request detected",
                    severity="high",
                    suggested_response=redirect,
                    parent_alert=True,
                )

        # Check for personal information requests
        for pattern in self._pii_re:
            if pattern.search(user_input):
                return SafetyResult(
                    action=SafetyAction.BLOCK,
                    reason="Personal information request detected",
                    severity="medium",
                    suggested_response="I keep my personal information private, and you should too! Is there something else I can help you with?",
                    parent_alert=True,
                )

        # Check for blocked topics
        for topic in self.BLOCKED_TOPICS:
            if topic in input_lower:
                # Check if parent has explicitly allowed this topic (override)
                # But never allow override if parent also explicitly blocked it
                if topic in self.profile.blocked_topics:
                    # Parent explicitly blocked - no override possible
                    pass
                elif topic in self.profile.allowed_topics:
                    # Parent explicitly allowed this globally-blocked topic
                    continue

                redirect = self._find_redirect(input_lower)
                return SafetyResult(
                    action=SafetyAction.REDIRECT if redirect else SafetyAction.BLOCK,
                    reason=f"Blocked topic detected: {topic}",
                    severity="medium",
                    suggested_response=redirect,
                    parent_alert=topic in ["weapon", "drugs", "self-harm"],
                )

        # Check child's specific blocked topics
        for topic in self.profile.blocked_topics:
            if topic.lower() in input_lower:
                return SafetyResult(
                    action=SafetyAction.BLOCK,
                    reason=f"Parent-blocked topic: {topic}",
                    severity="low",
                    suggested_response=f"I'm not able to talk about that. Let's explore something else!",
                )

        # Content is safe
        return SafetyResult(
            action=SafetyAction.ALLOW,
            reason="Content passed safety checks",
        )

    def evaluate_output(self, response: str) -> SafetyResult:
        """
        Evaluate agent output for safety before sending to child.

        Checks that responses are age-appropriate and don't contain
        accidentally leaked unsafe content.
        """
        response_lower = response.lower()

        # Check for blocked topics in output
        for topic in self.BLOCKED_TOPICS:
            if topic in response_lower:
                return SafetyResult(
                    action=SafetyAction.BLOCK,
                    reason=f"Blocked topic in response: {topic}",
                    severity="high",
                    parent_alert=True,
                )

        # Check complexity for younger children
        if self.profile.age_group in [
            AgeGroup.EARLY_CHILDHOOD,
            AgeGroup.MIDDLE_CHILDHOOD,
        ]:
            complexity_result = self._check_complexity(response)
            if complexity_result:
                return complexity_result

        return SafetyResult(
            action=SafetyAction.ALLOW,
            reason="Response passed safety checks",
        )

    def _check_complexity(self, text: str) -> SafetyResult | None:
        """Check if text is too complex for the child's age group."""
        # Simple heuristics for complexity
        words = text.split()
        avg_word_length = sum(len(w) for w in words) / max(len(words), 1)
        sentence_count = text.count(".") + text.count("!") + text.count("?")
        avg_sentence_length = len(words) / max(sentence_count, 1)

        # Thresholds based on age group
        if self.profile.age_group == AgeGroup.EARLY_CHILDHOOD:
            if avg_word_length > 6 or avg_sentence_length > 12:
                return SafetyResult(
                    action=SafetyAction.SIMPLIFY,
                    reason="Response may be too complex for early childhood",
                    severity="low",
                )
        elif self.profile.age_group == AgeGroup.MIDDLE_CHILDHOOD:
            if avg_word_length > 7 or avg_sentence_length > 18:
                return SafetyResult(
                    action=SafetyAction.SIMPLIFY,
                    reason="Response may be too complex for middle childhood",
                    severity="low",
                )

        return None

    def _find_redirect(self, input_text: str) -> str | None:
        """Find a safe redirect response for blocked content."""
        for keyword, redirect in self.SAFE_REDIRECTS.items():
            if keyword in input_text:
                return redirect
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
                - Use lots of analogies to everyday objects
            """,
            AgeGroup.MIDDLE_CHILDHOOD: """
                - Use simple but varied vocabulary
                - Keep sentences moderate length (8-15 words)
                - Explain concepts with relatable examples
                - Be friendly and encouraging
                - Can introduce some abstract ideas with concrete support
                - Use analogies and "like" comparisons
            """,
            AgeGroup.LATE_CHILDHOOD: """
                - Use age-appropriate vocabulary
                - Can handle longer explanations
                - Encourage curiosity and follow-up questions
                - Be informative but approachable
                - Can discuss more complex topics at basic level
            """,
            AgeGroup.EARLY_TEEN: """
                - Use standard vocabulary
                - Can handle nuanced explanations
                - Treat them with respect for their growing independence
                - Be informative and engaging
                - Can discuss complex topics appropriately
            """,
            AgeGroup.LATE_TEEN: """
                - Use full vocabulary
                - Provide detailed, accurate information
                - Treat them as young adults
                - Be informative and direct
                - Can discuss most educational topics in depth
            """,
        }
        return guidelines.get(
            self.profile.age_group, guidelines[AgeGroup.MIDDLE_CHILDHOOD]
        )
