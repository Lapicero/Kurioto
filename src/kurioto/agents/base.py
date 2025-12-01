"""Base agent abstractions used in multi-agent orchestration.

Week 1 scope: lightweight base class + Intent dataclass to enable
orchestrator routing without disrupting existing functionality.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from kurioto.config import ChildProfile, get_settings
from kurioto.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Intent:
    """Parsed intent produced by the orchestrator's classification step."""

    type: str  # educational_homework | educational_concept | conversational | action | safety_concern | unknown
    confidence: float = 0.0
    subject: str | None = None  # math | science | english | history | other
    reasoning: str | None = None

    def is_confident(self, threshold: float = 0.5) -> bool:
        return self.confidence >= threshold and self.type not in {"unknown"}

    def is_educational(self) -> bool:
        """Check if intent is educational (homework or concept)."""
        return self.type in {"educational_homework", "educational_concept"}


@runtime_checkable
class SupportsHandle(Protocol):  # Future extension placeholder
    async def handle(
        self, user_input: str, context: dict[str, Any] | None = None
    ) -> str: ...


class BaseAgent:
    """Minimal base class for specialized agents.

    Later phases will extend this with tracing, token accounting,
    caching, and evaluation hooks.
    """

    # Safety limits for LLM inputs
    MAX_INPUT_LENGTH = 4000  # Conservative limit (~1000 tokens)
    MAX_INPUT_CHARS_WARNING = 2000  # Warn at half the limit

    def __init__(self, child_profile: ChildProfile):
        self.child_profile = child_profile
        self.settings = get_settings()

    @property
    def name(self) -> str:
        return self.__class__.__name__.lower()

    def _validate_and_truncate_input(
        self, user_input: str, max_length: int | None = None
    ) -> str:
        """Validate and truncate user input to prevent API issues.

        Args:
            user_input: Raw user input text
            max_length: Override default max length (useful for different contexts)

        Returns:
            Validated and potentially truncated input string
        """
        if not user_input or not user_input.strip():
            logger.warning(
                "empty_user_input",
                agent=self.name,
                child_id=self.child_profile.child_id,
            )
            return ""

        max_len = max_length or self.MAX_INPUT_LENGTH
        input_len = len(user_input)

        # Warn if approaching limit
        if input_len > self.MAX_INPUT_CHARS_WARNING:
            logger.warning(
                "long_user_input",
                agent=self.name,
                child_id=self.child_profile.child_id,
                length=input_len,
                max_length=max_len,
            )

        # Truncate if exceeds limit
        if input_len > max_len:
            truncated = user_input[:max_len]
            logger.info(
                "input_truncated",
                agent=self.name,
                child_id=self.child_profile.child_id,
                original_length=input_len,
                truncated_length=max_len,
            )
            return truncated

        return user_input

    async def _generate_json(
        self, prompt: str, client: Any, model_name: str
    ) -> dict[str, Any]:
        """Helper to call Gemini and parse JSON output safely.

        Args:
            prompt: The prompt to send to the model
            client: Initialized Gemini client
            model_name: Model identifier

        Returns:
            Parsed JSON dict, or empty dict on error
        """
        if client is None:
            return {}
        response = await self._run_blocking(
            lambda: client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
        )
        text = getattr(response, "text", "{}")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning(
                "json_parse_error",
                agent=self.name,
                text_preview=text[:100],
            )
            return {}

    async def _run_blocking(self, func):
        """Minimal async bridge for sync SDK calls.

        Args:
            func: Synchronous function to execute

        Returns:
            Result of the function call
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func)
