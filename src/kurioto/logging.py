"""
Logging and observability for Kurioto.

Provides structured logging with tracing support for agent actions,
tool calls, and safety events.
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any
from uuid import uuid4

import structlog

from kurioto.config import get_settings


def configure_logging() -> None:
    """Configure structured logging for the application."""
    settings = get_settings()

    # Safely get log level string
    log_level = getattr(settings, "log_level", "INFO")
    if not isinstance(log_level, str):
        log_level = "INFO"

    is_dev = getattr(settings, "is_development", True)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            # Use pretty console output in development
            (
                structlog.dev.ConsoleRenderer()
                if is_dev
                else structlog.processors.JSONRenderer()
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog, log_level.upper(), structlog.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance with the given name."""
    return structlog.get_logger(name)


class TraceContext:
    """
    Context manager for tracing agent operations.

    Provides a way to track and log agent reasoning steps, tool calls,
    and safety events for observability and debugging.
    """

    def __init__(
        self,
        operation: str,
        child_id: str | None = None,
        session_id: str | None = None,
    ):
        self.operation = operation
        self.trace_id = str(uuid4())[:8]
        self.child_id = child_id
        self.session_id = session_id or str(uuid4())[:8]
        self.start_time = datetime.now()
        self.events: list[dict[str, Any]] = []
        self.logger = get_logger("trace")

    def __enter__(self) -> "TraceContext":
        self.logger.info(
            "trace_start",
            trace_id=self.trace_id,
            operation=self.operation,
            session_id=self.session_id,
            child_id=self.child_id,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = (datetime.now() - self.start_time).total_seconds() * 1000
        self.logger.info(
            "trace_end",
            trace_id=self.trace_id,
            operation=self.operation,
            duration_ms=round(duration_ms, 2),
            event_count=len(self.events),
            error=str(exc_val) if exc_val else None,
        )

    def log_event(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """Log an event within this trace."""
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data or {},
            **kwargs,
        }
        self.events.append(event)
        self.logger.debug(
            f"trace_event_{event_type}",
            trace_id=self.trace_id,
            **event,
        )

    def log_tool_call(
        self,
        tool_name: str,
        inputs: dict[str, Any],
        outputs: Any = None,
        error: str | None = None,
    ) -> None:
        """Log a tool call event."""
        self.log_event(
            "tool_call",
            data={
                "tool": tool_name,
                "inputs": inputs,
                "outputs": outputs,
                "error": error,
            },
        )

    def log_safety_event(
        self,
        action: str,
        reason: str,
        severity: str = "low",
    ) -> None:
        """Log a safety-related event."""
        self.log_event(
            "safety",
            data={
                "action": action,
                "reason": reason,
                "severity": severity,
            },
        )

    def log_reasoning_step(
        self,
        step: int,
        thought: str,
        action: str | None = None,
    ) -> None:
        """Log an agent reasoning step."""
        self.log_event(
            "reasoning",
            data={
                "step": step,
                "thought": thought,
                "action": action,
            },
        )


# Configure logging on module import
configure_logging()
