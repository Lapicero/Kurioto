"""
Regex-based safety classifier for fast first-pass filtering.

This classifier provides:
- Extremely fast blocklist matching (microseconds)
- Zero external API calls
- Zero cost
- Catches obvious violations before hitting expensive LLM calls

Limitations (by design - other classifiers handle these):
- Easy to bypass with creative spelling
- No semantic understanding
- English-only patterns
"""

from __future__ import annotations

import re
from typing import Any

from kurioto.safety.base import (
    BaseSafetyClassifier,
    SafetyAction,
    SafetyCategory,
    SafetyResult,
    SafetySeverity,
)


class RegexSafetyClassifier(BaseSafetyClassifier):
    """
    Fast regex-based safety classifier for obvious blocklist terms.

    This is the first layer of defense - catches clear violations
    without needing to call external APIs.
    """

    # Topics that are always blocked regardless of age
    BLOCKED_TERMS: dict[str, tuple[SafetyCategory, SafetySeverity]] = {
        # Weapons and violence
        "weapon": (SafetyCategory.VIOLENCE, SafetySeverity.HIGH),
        "bomb": (SafetyCategory.DANGEROUS, SafetySeverity.CRITICAL),
        "explosive": (SafetyCategory.DANGEROUS, SafetySeverity.CRITICAL),
        "gun": (SafetyCategory.VIOLENCE, SafetySeverity.HIGH),
        "knife attack": (SafetyCategory.VIOLENCE, SafetySeverity.CRITICAL),
        # Substances
        "drugs": (SafetyCategory.DRUGS_ALCOHOL, SafetySeverity.HIGH),
        "alcohol": (SafetyCategory.DRUGS_ALCOHOL, SafetySeverity.MEDIUM),
        "smoking": (SafetyCategory.DRUGS_ALCOHOL, SafetySeverity.MEDIUM),
        "vaping": (SafetyCategory.DRUGS_ALCOHOL, SafetySeverity.MEDIUM),
        # Self-harm
        "suicide": (SafetyCategory.SELF_HARM, SafetySeverity.CRITICAL),
        "self-harm": (SafetyCategory.SELF_HARM, SafetySeverity.CRITICAL),
        "eating disorder": (SafetyCategory.SELF_HARM, SafetySeverity.HIGH),
        # Adult content
        "pornography": (SafetyCategory.SEXUAL, SafetySeverity.CRITICAL),
        "sexual": (SafetyCategory.SEXUAL, SafetySeverity.HIGH),
        "nude": (SafetyCategory.SEXUAL, SafetySeverity.HIGH),
        # Gambling
        "gambling": (SafetyCategory.GAMBLING, SafetySeverity.MEDIUM),
        "betting": (SafetyCategory.GAMBLING, SafetySeverity.MEDIUM),
        # Dangerous tech
        "hacking": (SafetyCategory.DANGEROUS, SafetySeverity.MEDIUM),
        "malware": (SafetyCategory.DANGEROUS, SafetySeverity.HIGH),
        "virus": (SafetyCategory.DANGEROUS, SafetySeverity.MEDIUM),
    }

    # Patterns for dangerous instruction requests (high confidence blocks)
    DANGEROUS_INSTRUCTION_PATTERNS = [
        (
            r"how to (make|build|create|construct) (a )?(bomb|weapon|explosive|gun)",
            SafetyCategory.DANGEROUS,
            SafetySeverity.CRITICAL,
        ),
        (
            r"how to (hurt|harm|kill|attack|murder)",
            SafetyCategory.VIOLENCE,
            SafetySeverity.CRITICAL,
        ),
        (
            r"how to (steal|hack|break into)",
            SafetyCategory.DANGEROUS,
            SafetySeverity.HIGH,
        ),
        (
            r"(credit card|password|social security) number",
            SafetyCategory.PII,
            SafetySeverity.HIGH,
        ),
    ]

    # Patterns for personal information requests
    PII_PATTERNS = [
        (
            r"(what is|tell me|give me) your (address|phone|school|password)",
            SafetyCategory.PII,
            SafetySeverity.HIGH,
        ),
        (
            r"where do you live",
            SafetyCategory.PII,
            SafetySeverity.MEDIUM,
        ),
        (
            r"what('s| is) your (real|full) name",
            SafetyCategory.PII,
            SafetySeverity.MEDIUM,
        ),
        (
            r"(send|share) (me )?(a )?photo of (yourself|you)",
            SafetyCategory.PII,
            SafetySeverity.HIGH,
        ),
    ]

    # Safe redirects for common blocked topics
    SAFE_REDIRECTS = {
        "bomb": "I can't help with that because it's dangerous. But I can tell you how fireworks create bright colors!",
        "weapon": "I can't help with that. Would you like to learn about how knights protected castles instead?",
        "drugs": "That's not something I can help with. How about we learn about how doctors help people stay healthy?",
        "hacking": "I can't help with that. But I can teach you about how computers work to keep information safe!",
    }

    def __init__(self, fail_safe: bool = True):
        super().__init__(fail_safe=fail_safe)
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self._dangerous_re = [
            (re.compile(p, re.IGNORECASE), cat, sev)
            for p, cat, sev in self.DANGEROUS_INSTRUCTION_PATTERNS
        ]
        self._pii_re = [
            (re.compile(p, re.IGNORECASE), cat, sev)
            for p, cat, sev in self.PII_PATTERNS
        ]

    @property
    def name(self) -> str:
        return "regex_blocklist"

    @property
    def is_available(self) -> bool:
        """Always available - no external dependencies."""
        return True

    async def classify(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> SafetyResult:
        """
        Fast regex-based classification.

        Checks in order of severity:
        1. Dangerous instruction patterns (CRITICAL)
        2. PII patterns (HIGH)
        3. Blocked terms (varies)
        """
        text_lower = text.lower()

        # Check dangerous instruction patterns first (highest priority)
        for pattern, category, severity in self._dangerous_re:
            if pattern.search(text):
                redirect = self._find_redirect(text_lower)
                return SafetyResult(
                    action=SafetyAction.REDIRECT if redirect else SafetyAction.BLOCK,
                    reason="Dangerous instruction request detected",
                    severity=severity,
                    categories=[category],
                    confidence=0.95,  # High confidence for pattern match
                    suggested_response=redirect,
                    parent_alert=True,
                    classifier_name=self.name,
                )

        # Check PII patterns
        for pattern, category, severity in self._pii_re:
            if pattern.search(text):
                return SafetyResult(
                    action=SafetyAction.BLOCK,
                    reason="Personal information request detected",
                    severity=severity,
                    categories=[category],
                    confidence=0.9,
                    suggested_response=(
                        "I keep my personal information private, and you should too! "
                        "Is there something else I can help you with?"
                    ),
                    parent_alert=severity >= SafetySeverity.HIGH,
                    classifier_name=self.name,
                )

        # Check blocked terms
        for term, (category, severity) in self.BLOCKED_TERMS.items():
            if term in text_lower:
                # Check for allowed topics override from context
                allowed_topics = (context or {}).get("allowed_topics", [])
                blocked_topics = (context or {}).get("blocked_topics", [])

                # Parent-blocked always takes precedence
                if term in blocked_topics:
                    pass  # Continue to block
                elif term in allowed_topics:
                    continue  # Skip this term, parent allowed it

                redirect = self._find_redirect(text_lower)
                return SafetyResult(
                    action=SafetyAction.REDIRECT if redirect else SafetyAction.BLOCK,
                    reason=f"Blocked term detected: {term}",
                    severity=severity,
                    categories=[category],
                    confidence=0.85,  # Slightly lower - term match without context
                    suggested_response=redirect,
                    parent_alert=severity >= SafetySeverity.HIGH,
                    classifier_name=self.name,
                )

        # Check parent's custom blocked topics
        blocked_topics = (context or {}).get("blocked_topics", [])
        for topic in blocked_topics:
            if topic.lower() in text_lower:
                return SafetyResult(
                    action=SafetyAction.BLOCK,
                    reason=f"Parent-blocked topic: {topic}",
                    severity=SafetySeverity.LOW,
                    categories=[SafetyCategory.AGE_INAPPROPRIATE],
                    confidence=0.9,
                    suggested_response="I'm not able to talk about that. Let's explore something else!",
                    parent_alert=False,
                    classifier_name=self.name,
                )

        # No issues detected
        return SafetyResult(
            action=SafetyAction.ALLOW,
            reason="No blocklist matches found",
            severity=SafetySeverity.NONE,
            categories=[SafetyCategory.NONE],
            confidence=0.7,  # Lower confidence - we only checked blocklists
            classifier_name=self.name,
        )

    def _find_redirect(self, text_lower: str) -> str | None:
        """Find a safe redirect response for blocked content."""
        for keyword, redirect in self.SAFE_REDIRECTS.items():
            if keyword in text_lower:
                return redirect
        return None
