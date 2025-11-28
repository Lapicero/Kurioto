"""
Memory management for Kurioto.

Implements episodic (conversation) and semantic (profile/preferences) memory
for maintaining context across interactions.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from kurioto.logging import get_logger

logger = get_logger(__name__)


class MemoryEntry(BaseModel):
    """A single memory entry."""

    entry_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    timestamp: datetime = Field(default_factory=datetime.now)
    entry_type: str = Field(..., description="Type: episodic, semantic, safety")
    content: dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class ConversationTurn(BaseModel):
    """A single turn in a conversation."""

    turn_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    timestamp: datetime = Field(default_factory=datetime.now)
    role: str = Field(..., description="user or assistant")
    content: str = Field(..., description="Message content")
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryManager:
    """
    Manages both episodic (short-term) and semantic (long-term) memory.

    Episodic memory stores recent conversation turns.
    Semantic memory stores child preferences, interests, and learning progress.

    This is designed to work with ADK's session management for state persistence.
    """

    def __init__(
        self,
        child_id: str,
        max_episodic_entries: int = 50,
        max_semantic_entries: int = 100,
    ):
        self.child_id = child_id
        self.max_episodic_entries = max_episodic_entries
        self.max_semantic_entries = max_semantic_entries

        # In-memory stores (can be backed by ADK session state)
        self._episodic: list[ConversationTurn] = []
        self._semantic: list[MemoryEntry] = []
        self._safety_events: list[MemoryEntry] = []

        logger.info("memory_manager_init", child_id=child_id)

    # === Episodic Memory (Conversation) ===

    def add_turn(
        self,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationTurn:
        """Add a conversation turn to episodic memory."""
        turn = ConversationTurn(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self._episodic.append(turn)

        # Trim if exceeds max
        if len(self._episodic) > self.max_episodic_entries:
            self._episodic = self._episodic[-self.max_episodic_entries :]

        logger.debug("memory_add_turn", role=role, turn_id=turn.turn_id)
        return turn

    def get_recent_turns(self, n: int = 10) -> list[ConversationTurn]:
        """Get the n most recent conversation turns."""
        return self._episodic[-n:]

    def get_conversation_context(self, n: int = 10) -> str:
        """Get formatted conversation history for context."""
        turns = self.get_recent_turns(n)
        lines = []
        for turn in turns:
            prefix = "Child" if turn.role == "user" else "Kurioto"
            lines.append(f"{prefix}: {turn.content}")
        return "\n".join(lines)

    def clear_episodic(self) -> None:
        """Clear episodic memory (e.g., on session end)."""
        self._episodic = []
        logger.info("memory_clear_episodic", child_id=self.child_id)

    # === Semantic Memory (Long-term) ===

    def add_semantic_entry(
        self,
        content: dict[str, Any],
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        """Add a semantic memory entry (preferences, interests, learning)."""
        entry = MemoryEntry(
            entry_type="semantic",
            content=content,
            importance=importance,
            tags=tags or [],
        )
        self._semantic.append(entry)

        # Trim low-importance entries if exceeds max
        if len(self._semantic) > self.max_semantic_entries:
            self._semantic.sort(key=lambda e: e.importance, reverse=True)
            self._semantic = self._semantic[: self.max_semantic_entries]

        logger.debug("memory_add_semantic", entry_id=entry.entry_id, tags=tags)
        return entry

    def get_semantic_by_tag(self, tag: str) -> list[MemoryEntry]:
        """Get semantic memories by tag."""
        return [e for e in self._semantic if tag in e.tags]

    def get_interests(self) -> list[str]:
        """Get child's remembered interests."""
        interest_entries = self.get_semantic_by_tag("interest")
        interests = []
        for entry in interest_entries:
            if "topic" in entry.content:
                interests.append(entry.content["topic"])
        return interests

    def remember_interest(self, topic: str, context: str = "") -> MemoryEntry:
        """Remember that the child showed interest in a topic."""
        return self.add_semantic_entry(
            content={"topic": topic, "context": context},
            importance=0.7,
            tags=["interest", "preference"],
        )

    # === Safety Events ===

    def log_safety_event(
        self,
        event_type: str,
        description: str,
        severity: str = "low",
        action_taken: str = "",
    ) -> MemoryEntry:
        """Log a safety-related event for parent dashboard."""
        entry = MemoryEntry(
            entry_type="safety",
            content={
                "event_type": event_type,
                "description": description,
                "severity": severity,
                "action_taken": action_taken,
            },
            importance=1.0 if severity == "high" else 0.8,
            tags=["safety", severity],
        )
        self._safety_events.append(entry)

        logger.warning(
            "memory_safety_event",
            child_id=self.child_id,
            event_type=event_type,
            severity=severity,
        )
        return entry

    def get_safety_events(self, severity: str | None = None) -> list[MemoryEntry]:
        """Get safety events, optionally filtered by severity."""
        if severity:
            return [e for e in self._safety_events if severity in e.tags]
        return self._safety_events.copy()

    # === State Export/Import (for ADK session integration) ===

    def export_state(self) -> dict[str, Any]:
        """Export memory state for session persistence."""
        return {
            "child_id": self.child_id,
            "episodic": [t.model_dump(mode="json") for t in self._episodic],
            "semantic": [e.model_dump(mode="json") for e in self._semantic],
            "safety_events": [e.model_dump(mode="json") for e in self._safety_events],
        }

    def import_state(self, state: dict[str, Any]) -> None:
        """Import memory state from session."""
        if "episodic" in state:
            self._episodic = [ConversationTurn(**t) for t in state["episodic"]]
        if "semantic" in state:
            self._semantic = [MemoryEntry(**e) for e in state["semantic"]]
        if "safety_events" in state:
            self._safety_events = [MemoryEntry(**e) for e in state["safety_events"]]

        logger.info(
            "memory_import_state",
            child_id=self.child_id,
            episodic_count=len(self._episodic),
            semantic_count=len(self._semantic),
        )
