"""Base agent abstractions used in multi-agent orchestration.

Week 1 scope: lightweight base class + Intent dataclass to enable
orchestrator routing without disrupting existing functionality.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from kurioto.config import ChildProfile, get_settings
from kurioto.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Intent:
    """Parsed intent produced by the orchestrator's classification step."""

    type: str  # educational | conversational | action | safety_concern | unknown
    confidence: float = 0.0
    reasoning: str | None = None

    def is_confident(self, threshold: float = 0.5) -> bool:
        return self.confidence >= threshold and self.type not in {"unknown"}


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

    def __init__(self, child_profile: ChildProfile):
        self.child_profile = child_profile
        self.settings = get_settings()

    @property
    def name(self) -> str:
        return self.__class__.__name__.lower()
