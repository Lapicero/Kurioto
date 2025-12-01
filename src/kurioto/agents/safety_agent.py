"""Week 2 SafetyAgent implementation.

Responsible for:
- Pre-checking user inputs for safety concerns
- Post-checking agent outputs before delivery
- LLM-based semantic safety verification (edge cases)
- Generating parent alerts for concerning incidents

Design goals (Week 2):
- Wrap existing multi-layer safety system
- Add LLM semantic verification layer
- Generate human-readable parent alerts
- Maintain backwards compatibility
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from google import genai

from kurioto.agents.base import BaseAgent
from kurioto.config import ChildProfile
from kurioto.logging import get_logger
from kurioto.safety.base import (
    SafetyAction,
    SafetyCategory,
    SafetyResult,
    SafetySeverity,
)
from kurioto.safety.multi_layer import MultiLayerSafetyEvaluator

logger = get_logger(__name__)

# Prompt for LLM-based semantic safety verification
_SEMANTIC_SAFETY_PROMPT = """You are a safety expert for a child-focused AI companion.

Analyze this content for safety concerns that might be missed by keyword filters.

Child age: {age}
Child age group: {age_group}

Content to analyze: "{content}"

Consider:
1. Subtle inappropriate references or innuendo
2. Age-inappropriate complexity or topics
3. Manipulation or deception attempts
4. Requests for personal information
5. Emotional manipulation or distress
6. Context-dependent safety issues

Return JSON:
{{
    "is_safe": true|false,
    "severity": "none"|"low"|"medium"|"high"|"critical",
    "category": "violence"|"sexual"|"hate_speech"|"harassment"|"self_harm"|
                "dangerous"|"drugs_alcohol"|"profanity"|"pii"|
                "deception"|"age_inappropriate"|"safe",
    "reasoning": "brief explanation",
    "action": "allow"|"block"|"redirect"|"warn_parent"
}}
"""

# Prompt for generating parent alerts
_PARENT_ALERT_PROMPT = """Generate a clear, professional parent alert for this safety incident.

Child: {child_name}, age {age}
Incident type: {category}
Severity: {severity}
User input: "{user_input}"
System action: {action}

Create a brief message for parents that:
1. Explains what happened (without repeating inappropriate content verbatim)
2. Describes what action was taken
3. Indicates whether parent follow-up is recommended
4. Uses a professional but reassuring tone

Return JSON:
{{
    "subject": "Brief subject line",
    "message": "2-3 sentence explanation",
    "follow_up_recommended": true|false,
    "urgency": "low"|"medium"|"high"
}}
"""


class ParentAlert:
    """Structured parent alert for safety incidents."""

    def __init__(
        self,
        subject: str,
        message: str,
        follow_up_recommended: bool = False,
        urgency: str = "low",
    ):
        self.subject = subject
        self.message = message
        self.follow_up_recommended = follow_up_recommended
        self.urgency = urgency

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "message": self.message,
            "follow_up_recommended": self.follow_up_recommended,
            "urgency": self.urgency,
        }


class SafetyAgent(BaseAgent):
    """Specialized agent for safety verification and parent alerts.

    Wraps the existing multi-layer safety system and adds:
    - LLM-based semantic verification for edge cases
    - Parent alert generation with context-aware messaging
    """

    def __init__(self, child_profile: ChildProfile):
        super().__init__(child_profile)
        self._client = None
        self._model_name = self.settings.model_name
        self._available = False

        # Wrap existing multi-layer safety evaluator
        self._multi_layer = MultiLayerSafetyEvaluator(
            child_profile=child_profile,
            use_gemini=True,
            use_perspective=True,
            use_mock_perspective=False,
        )

        self._init_client()

        logger.info(
            "safety_agent_init",
            child_id=child_profile.child_id,
            model=self._model_name,
            llm_available=self._available,
        )

    def _init_client(self) -> None:
        """Initialize Gemini client for LLM-based safety verification."""
        if genai is None:
            logger.warning(
                "safety_agent_llm_unavailable", reason="google-genai not installed"
            )
            return

        api_key = self.settings.google_api_key
        if not api_key:
            logger.warning("safety_agent_no_api_key")
            return

        try:
            self._client = genai.Client(api_key=api_key)
            self._available = True
            logger.info("safety_agent_client_ready", model=self._model_name)
        except Exception as e:  # pragma: no cover
            logger.error("safety_agent_client_error", error=str(e))

    @property
    def is_available(self) -> bool:
        """Check if LLM-based semantic verification is available."""
        return self._available

    def get_age_appropriate_guidelines(self) -> str:
        """Expose age-appropriate guidelines via underlying multi-layer system."""
        return self._multi_layer.get_age_appropriate_guidelines()

    async def pre_check(self, user_input: str) -> SafetyResult:
        """Check user input before processing.

        Uses multi-layer evaluation + optional LLM semantic verification.

        Args:
            user_input: The child's message

        Returns:
            SafetyResult with action and reasoning
        """
        # Run existing multi-layer check
        multi_result = await self._multi_layer.evaluate(user_input)
        base_result = multi_result.to_safety_result()

        logger.debug(
            "safety_agent_pre_check",
            action=base_result.action.value,
            severity=base_result.severity.value,
            layers_triggered=len(multi_result.layers_executed),
        )

        # If multi-layer is confident (BLOCK or ALLOW), trust it
        if base_result.action == SafetyAction.BLOCK:
            return base_result
        if base_result.severity == SafetySeverity.NONE:
            return base_result

        # For edge cases (REVIEW/REDIRECT), add LLM verification
        if self.is_available and base_result.action in {
            SafetyAction.REVIEW,
            SafetyAction.REDIRECT,
        }:
            llm_result = await self._llm_verify(user_input, is_input=True)

            # LLM can escalate but not de-escalate
            def _sev_rank(s: SafetySeverity) -> int:
                order = {
                    SafetySeverity.NONE: 0,
                    SafetySeverity.LOW: 1,
                    SafetySeverity.MEDIUM: 2,
                    SafetySeverity.HIGH: 3,
                    SafetySeverity.CRITICAL: 4,
                }
                return order.get(s, 0)

            if _sev_rank(llm_result.severity) > _sev_rank(base_result.severity):
                logger.info(
                    "safety_agent_llm_escalation",
                    base_severity=base_result.severity.value,
                    llm_severity=llm_result.severity.value,
                )
                return llm_result

        return base_result

    async def post_check(self, output: str) -> SafetyResult:
        """Check agent output before delivery to child.

        Args:
            output: The generated response

        Returns:
            SafetyResult with action and reasoning
        """
        # Run multi-layer check on output
        multi_result = await self._multi_layer.evaluate(output)
        result = multi_result.to_safety_result()

        logger.debug(
            "safety_agent_post_check",
            action=result.action.value,
            severity=result.severity.value,
        )

        return result

    async def _llm_verify(self, content: str, is_input: bool = True) -> SafetyResult:
        """LLM-based semantic safety verification for edge cases.

        Args:
            content: Text to verify
            is_input: Whether this is user input (vs agent output)

        Returns:
            SafetyResult from LLM analysis
        """
        if not self.is_available:
            # No LLM available, return neutral result
            return SafetyResult(
                action=SafetyAction.ALLOW,
                severity=SafetySeverity.NONE,
                reason="LLM verification unavailable",
            )

        prompt = _SEMANTIC_SAFETY_PROMPT.format(
            age=self.child_profile.age,
            age_group=self.child_profile.age_group.value,
            content=content,
        )

        try:
            response_json = await self._generate_json(prompt)

            is_safe = response_json.get("is_safe", True)
            severity_str = response_json.get("severity", "none")
            category_str = response_json.get("category", "safe")
            reasoning = response_json.get("reasoning", "LLM semantic check")
            action_str = response_json.get("action", "allow")

            # Map strings to enums safely
            try:
                severity = SafetySeverity(severity_str)
            except Exception:
                severity = SafetySeverity.NONE
            try:
                action = SafetyAction(action_str)
            except Exception:
                action = SafetyAction.ALLOW

            # Map category string to list of SafetyCategory
            categories: list[SafetyCategory] = []
            if category_str and category_str != "safe":
                try:
                    categories = [SafetyCategory(category_str)]
                except Exception:
                    categories = [SafetyCategory.NONE]
            else:
                categories = [SafetyCategory.NONE]

            logger.info(
                "safety_agent_llm_verify",
                is_safe=is_safe,
                severity=severity.value,
                action=action.value,
            )

            return SafetyResult(
                action=action,
                reason=reasoning,
                severity=severity,
                categories=categories,
            )

        except Exception as e:
            logger.warning("safety_agent_llm_verify_error", error=str(e))
            # On error, be conservative
            return SafetyResult(
                action=SafetyAction.REVIEW,
                severity=SafetySeverity.LOW,
                reason=f"LLM verification error: {str(e)}",
            )

    async def generate_parent_alert(
        self,
        user_input: str,
        safety_result: SafetyResult,
    ) -> ParentAlert:
        """Generate human-readable parent alert for safety incident.

        Args:
            user_input: The child's original message
            safety_result: The safety evaluation result

        Returns:
            ParentAlert with subject, message, and urgency
        """
        if not self.is_available:
            # Fallback to template-based alert
            return self._generate_template_alert(user_input, safety_result)

        # Derive a primary category string for the alert prompt
        primary_category = (
            safety_result.categories[0].value if safety_result.categories else "safe"
        )

        prompt = _PARENT_ALERT_PROMPT.format(
            child_name=self.child_profile.name,
            age=self.child_profile.age,
            category=primary_category,
            severity=safety_result.severity.value,
            user_input=user_input[:100],  # Truncate long inputs
            action=safety_result.action.value,
        )

        try:
            response_json = await self._generate_json(prompt)

            return ParentAlert(
                subject=response_json.get("subject", "Safety Alert"),
                message=response_json.get(
                    "message", "A safety concern was detected and handled."
                ),
                follow_up_recommended=response_json.get("follow_up_recommended", False),
                urgency=response_json.get("urgency", "low"),
            )

        except Exception as e:
            logger.warning("safety_agent_alert_generation_error", error=str(e))
            return self._generate_template_alert(user_input, safety_result)

    def _generate_template_alert(
        self, user_input: str, safety_result: SafetyResult
    ) -> ParentAlert:
        """Fallback template-based alert generation."""
        severity = safety_result.severity.value
        action = safety_result.action.value

        if severity in {"critical", "high"}:
            subject = f"Important Safety Alert - {self.child_profile.name}"
            urgency = "high"
            follow_up = True
        elif severity == "medium":
            subject = f"Safety Notice - {self.child_profile.name}"
            urgency = "medium"
            follow_up = True
        else:
            subject = f"Safety Log - {self.child_profile.name}"
            urgency = "low"
            follow_up = False

        message = (
            f"A safety concern was detected in {self.child_profile.name}'s interaction. "
            f"The system took action: {action}. "
            f"Reason: {safety_result.reason}"
        )

        return ParentAlert(
            subject=subject,
            message=message,
            follow_up_recommended=follow_up,
            urgency=urgency,
        )

    async def _generate_json(self, prompt: str) -> dict[str, Any]:
        """Helper to call Gemini and parse JSON output safely."""
        client = self._client
        if client is None:
            return {}

        response = await self._run_blocking(
            lambda: client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
        )

        text = getattr(response, "text", "{}")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("safety_agent_json_parse_error", text=text[:100])
            return {}

    async def _run_blocking(self, func):
        """Minimal async bridge for sync SDK."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func)
