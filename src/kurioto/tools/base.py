"""
Base tool interface for Kurioto.

All tools inherit from BaseTool and implement a consistent interface
for the agent to discover and use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """
    Result returned by a tool execution.

    Attributes:
        success: Whether the tool executed successfully
        data: The result data (type depends on tool)
        error: Error message if success is False
        metadata: Additional metadata about the execution
    """

    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_context(self) -> str:
        """Format result for inclusion in agent context."""
        if self.success:
            return f"Tool result: {self.data}"
        else:
            return f"Tool error: {self.error}"


class BaseTool(ABC):
    """
    Abstract base class for all Kurioto tools.

    Tools are callable components that the agent can use to perform
    actions or retrieve information.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does (shown to agent)."""
        ...

    @property
    def parameters(self) -> dict[str, Any]:
        """
        JSON Schema for tool parameters.

        Override in subclasses to define expected inputs.
        """
        return {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with execution outcome
        """
        ...

    def to_function_declaration(self) -> dict[str, Any]:
        """
        Convert tool to Gemini function declaration format.

        This format is used by the ADK for tool registration.
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
