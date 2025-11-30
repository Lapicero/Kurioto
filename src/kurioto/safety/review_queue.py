"""
Human review queue for edge case content moderation.

Provides a mechanism to flag content for human review when:
- Classifiers are uncertain (low confidence)
- Multiple classifiers disagree
- Content is in a gray area
- Severity requires human judgment

In production, this would integrate with:
- Parent notification systems
- Admin dashboards
- Content moderation workflows
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from kurioto.logging import get_logger
from kurioto.safety.base import SafetyAction, SafetyResult, SafetySeverity

logger = get_logger(__name__)


class ReviewStatus(str, Enum):
    """Status of a review queue item."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ReviewPriority(str, Enum):
    """Priority levels for review queue items."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ReviewQueueItem:
    """An item in the human review queue."""

    id: str
    content: str
    child_id: str
    classifier_results: list[SafetyResult]
    created_at: datetime
    status: ReviewStatus = ReviewStatus.PENDING
    priority: ReviewPriority = ReviewPriority.MEDIUM
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None
    review_decision: SafetyAction | None = None
    review_notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age_hours(self) -> float:
        """How many hours since this item was created."""
        return (datetime.now() - self.created_at).total_seconds() / 3600


class HumanReviewQueue:
    """
    Queue for content requiring human review.

    Features:
    - Priority-based queuing
    - Automatic escalation for urgent items
    - Integration with parent notification
    - Audit logging
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        auto_expire_hours: float = 24.0,
        default_action_on_expire: SafetyAction = SafetyAction.BLOCK,
    ):
        """
        Initialize the review queue.

        Args:
            max_queue_size: Maximum items in queue before oldest are expired
            auto_expire_hours: Hours after which pending items expire
            default_action_on_expire: Action to take when items expire
        """
        self._queue: deque[ReviewQueueItem] = deque(maxlen=max_queue_size)
        self._items_by_id: dict[str, ReviewQueueItem] = {}
        self.auto_expire_hours = auto_expire_hours
        self.default_action_on_expire = default_action_on_expire

        # Callbacks for integration
        self._on_urgent_item: list[Any] = []
        self._on_item_expired: list[Any] = []

    @property
    def pending_count(self) -> int:
        """Number of pending items in queue."""
        return sum(1 for item in self._queue if item.status == ReviewStatus.PENDING)

    @property
    def urgent_count(self) -> int:
        """Number of urgent pending items."""
        return sum(
            1
            for item in self._queue
            if item.status == ReviewStatus.PENDING
            and item.priority == ReviewPriority.URGENT
        )

    async def add_for_review(
        self,
        content: str,
        child_id: str,
        classifier_results: list[SafetyResult],
        priority: ReviewPriority | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReviewQueueItem:
        """
        Add content to the review queue.

        Args:
            content: The content to be reviewed
            child_id: ID of the child user
            classifier_results: Results from safety classifiers
            priority: Override priority (auto-calculated if None)
            metadata: Additional metadata

        Returns:
            The created ReviewQueueItem
        """
        # Auto-calculate priority if not provided
        if priority is None:
            priority = self._calculate_priority(classifier_results)

        item = ReviewQueueItem(
            id=str(uuid4()),
            content=content,
            child_id=child_id,
            classifier_results=classifier_results,
            created_at=datetime.now(),
            priority=priority,
            metadata=metadata or {},
        )

        self._queue.append(item)
        self._items_by_id[item.id] = item

        logger.info(
            "review_queue_add",
            item_id=item.id,
            child_id=child_id,
            priority=priority.value,
        )

        # Trigger urgent callbacks
        if priority == ReviewPriority.URGENT:
            await self._notify_urgent(item)

        return item

    def _calculate_priority(
        self, classifier_results: list[SafetyResult]
    ) -> ReviewPriority:
        """Calculate priority based on classifier results."""
        max_severity = SafetySeverity.NONE
        has_parent_alert = False
        low_confidence = False

        for result in classifier_results:
            if result.severity.value > max_severity.value:
                max_severity = result.severity
            if result.parent_alert:
                has_parent_alert = True
            if result.confidence < 0.5:
                low_confidence = True

        # Urgent: critical severity or parent alert with high severity
        if max_severity == SafetySeverity.CRITICAL:
            return ReviewPriority.URGENT
        if has_parent_alert and max_severity >= SafetySeverity.HIGH:
            return ReviewPriority.URGENT

        # High: high severity or parent alert
        if max_severity >= SafetySeverity.HIGH or has_parent_alert:
            return ReviewPriority.HIGH

        # Medium: medium severity or low confidence
        if max_severity >= SafetySeverity.MEDIUM or low_confidence:
            return ReviewPriority.MEDIUM

        return ReviewPriority.LOW

    async def get_pending_items(
        self,
        limit: int = 10,
        priority: ReviewPriority | None = None,
    ) -> list[ReviewQueueItem]:
        """
        Get pending items for review.

        Args:
            limit: Maximum items to return
            priority: Filter by priority (None for all)

        Returns:
            List of pending review items, highest priority first
        """
        # First, expire old items
        await self._expire_old_items()

        # Filter pending items
        pending = [
            item
            for item in self._queue
            if item.status == ReviewStatus.PENDING
            and (priority is None or item.priority == priority)
        ]

        # Sort by priority (urgent first) then age
        priority_order = {
            ReviewPriority.URGENT: 0,
            ReviewPriority.HIGH: 1,
            ReviewPriority.MEDIUM: 2,
            ReviewPriority.LOW: 3,
        }
        pending.sort(key=lambda x: (priority_order[x.priority], -x.age_hours))

        return pending[:limit]

    async def submit_review(
        self,
        item_id: str,
        decision: SafetyAction,
        reviewer_id: str,
        notes: str | None = None,
    ) -> bool:
        """
        Submit a review decision.

        Args:
            item_id: ID of the item being reviewed
            decision: The safety action decision
            reviewer_id: ID of the reviewer
            notes: Optional review notes

        Returns:
            True if review was submitted successfully
        """
        item = self._items_by_id.get(item_id)
        if not item:
            logger.warning("review_not_found", item_id=item_id)
            return False

        if item.status != ReviewStatus.PENDING:
            logger.warning(
                "review_invalid_status",
                item_id=item_id,
                status=item.status.value,
            )
            return False

        # Update item
        if decision == SafetyAction.ALLOW:
            item.status = ReviewStatus.APPROVED
        else:
            item.status = ReviewStatus.REJECTED

        item.reviewer_id = reviewer_id
        item.reviewed_at = datetime.now()
        item.review_decision = decision
        item.review_notes = notes

        logger.info(
            "review_submitted",
            item_id=item_id,
            decision=decision.value,
            reviewer_id=reviewer_id,
        )

        return True

    async def get_decision(self, item_id: str) -> SafetyAction | None:
        """
        Get the review decision for an item.

        Returns None if item not found or still pending.
        """
        item = self._items_by_id.get(item_id)
        if not item:
            return None

        if item.status == ReviewStatus.PENDING:
            return None

        if item.status == ReviewStatus.EXPIRED:
            return self.default_action_on_expire

        return item.review_decision

    async def _expire_old_items(self) -> None:
        """Expire items that have been pending too long."""
        now = datetime.now()
        expired_count = 0

        for item in self._queue:
            if item.status != ReviewStatus.PENDING:
                continue

            if item.age_hours > self.auto_expire_hours:
                item.status = ReviewStatus.EXPIRED
                item.review_decision = self.default_action_on_expire
                expired_count += 1

                logger.warning(
                    "review_item_expired",
                    item_id=item.id,
                    age_hours=item.age_hours,
                )

                # Notify callbacks
                for callback in self._on_item_expired:
                    try:
                        await callback(item)
                    except Exception as e:
                        logger.error("expire_callback_error", error=str(e))

        if expired_count > 0:
            logger.info("review_items_expired", count=expired_count)

    async def _notify_urgent(self, item: ReviewQueueItem) -> None:
        """Notify callbacks about urgent items."""
        for callback in self._on_urgent_item:
            try:
                await callback(item)
            except Exception as e:
                logger.error("urgent_callback_error", error=str(e))

    def on_urgent_item(self, callback) -> None:
        """Register a callback for urgent items."""
        self._on_urgent_item.append(callback)

    def on_item_expired(self, callback) -> None:
        """Register a callback for expired items."""
        self._on_item_expired.append(callback)

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        status_counts = {}
        priority_counts = {}

        for item in self._queue:
            status_counts[item.status.value] = (
                status_counts.get(item.status.value, 0) + 1
            )
            if item.status == ReviewStatus.PENDING:
                priority_counts[item.priority.value] = (
                    priority_counts.get(item.priority.value, 0) + 1
                )

        return {
            "total_items": len(self._queue),
            "pending_count": self.pending_count,
            "urgent_count": self.urgent_count,
            "status_breakdown": status_counts,
            "priority_breakdown": priority_counts,
        }


# Global singleton for the review queue
_review_queue: HumanReviewQueue | None = None


def get_review_queue() -> HumanReviewQueue:
    """Get the global review queue instance."""
    global _review_queue
    if _review_queue is None:
        _review_queue = HumanReviewQueue()
    return _review_queue
