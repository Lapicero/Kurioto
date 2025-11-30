"""
Parent Dashboard tool for Kurioto.

Provides functionality for logging events, retrieving usage statistics,
and managing child settings - all accessible to parents.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from kurioto.logging import get_logger
from kurioto.tools.base import BaseTool, ToolResult

logger = get_logger(__name__)


# Mock parent dashboard data store
_dashboard_logs: list[dict[str, Any]] = []
_settings: dict[str, Any] = {
    "music_enabled": True,
    "max_session_minutes": 30,
    "allowed_topics": ["science", "nature", "art", "music", "stories"],
    "blocked_topics": [],
    "notifications_enabled": True,
}


class ParentDashboardTool(BaseTool):
    """
    Tool for parent dashboard operations.

    Provides logging, settings management, and usage analytics
    for parental oversight of child interactions.
    """

    @property
    def name(self) -> str:
        return "parent_dashboard"

    @property
    def description(self) -> str:
        return (
            "Log events for parents, check settings, or retrieve usage information. "
            "Used internally to ensure parental oversight of all interactions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["log_event", "get_settings", "get_logs"],
                    "description": "Action to perform",
                },
                "event_type": {
                    "type": "string",
                    "description": "Type of event to log (for log_event action)",
                },
                "event_data": {
                    "type": "object",
                    "description": "Additional event data",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Execute parent dashboard action."""
        action: str = kwargs.get("action", "")
        event_type: str | None = kwargs.get("event_type")
        event_data: dict[str, Any] | None = kwargs.get("event_data")

        logger.info("parent_dashboard_execute", action=action)

        if action == "log_event":
            return await self._log_event(event_type or "unknown", event_data or {})
        elif action == "get_settings":
            return await self._get_settings()
        elif action == "get_logs":
            return await self._get_logs()
        else:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}",
            )

    async def _log_event(
        self,
        event_type: str,
        event_data: dict[str, Any],
    ) -> ToolResult:
        """Log an event to the parent dashboard."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": event_data,
        }
        _dashboard_logs.append(log_entry)

        logger.info("parent_dashboard_log", event_type=event_type)

        return ToolResult(
            success=True,
            data={"logged": True, "entry_id": len(_dashboard_logs)},
        )

    async def _get_settings(self) -> ToolResult:
        """Get current parent settings."""
        return ToolResult(
            success=True,
            data=_settings.copy(),
        )

    async def _get_logs(self) -> ToolResult:
        """Get recent dashboard logs."""
        # Return last 20 logs
        recent_logs = _dashboard_logs[-20:]
        return ToolResult(
            success=True,
            data={
                "total_logs": len(_dashboard_logs),
                "recent_logs": recent_logs,
            },
        )


def check_setting(key: str, default: Any = None) -> Any:
    """Helper to check a specific setting value."""
    return _settings.get(key, default)


def update_setting(key: str, value: Any) -> None:
    """Helper to update a setting (for parent interface)."""
    _settings[key] = value
    logger.info("setting_updated", key=key)
