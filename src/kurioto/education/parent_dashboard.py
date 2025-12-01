"""
Education Dashboard - Parent Oversight

Provides comprehensive visibility into child's tutoring sessions,
learning progress, and areas needing attention.
"""

from datetime import datetime, timedelta
from typing import Any

import structlog

from kurioto.memory import MemoryManager

logger = structlog.get_logger()


class EducationDashboard:
    """
    Parent oversight dashboard for tutoring sessions.

    Provides insights into:
    - Session summaries and transcripts
    - Learning progress by subject
    - Struggling vs mastered topics
    - Time spent on different subjects
    """

    def __init__(self, child_id: str, memory_manager: MemoryManager):
        """
        Initialize education dashboard.

        Args:
            child_id: Unique identifier for the child
            memory_manager: Memory manager for session storage/retrieval
        """
        self.child_id = child_id
        self.memory = memory_manager

    async def get_session_summary(self, timeframe: str = "today") -> dict[str, Any]:
        """
        Get summary of tutoring sessions for a timeframe.

        Args:
            timeframe: One of "today", "week", "month", or "all"

        Returns:
            dict with:
                - total_questions: Number of questions asked
                - timeframe: Timeframe used
                - subjects_covered: Dict of subject -> question count
                - struggling_topics: List of topics child is struggling with
                - mastered_topics: List of topics child has mastered
                - sessions: List of session summaries

        Example:
            >>> dashboard = EducationDashboard("child_123", memory)
            >>> summary = await dashboard.get_session_summary("week")
            >>> print(f"Questions this week: {summary['total_questions']}")
            >>> print(f"Struggling with: {summary['struggling_topics']}")
        """
        # Determine time range
        start_time = self._get_start_time(timeframe)

        # Get education sessions from memory
        sessions = await self.memory.get_sessions(
            child_id=self.child_id, start_time=start_time, session_type="education"
        )

        # Aggregate statistics
        total_questions = len(sessions)
        subjects: dict[str, int] = {}
        struggling_topics: list[str] = []
        mastered_topics: list[str] = []
        learning_topics: list[str] = []

        for session in sessions:
            summary = session.get("parent_summary", {})

            # Count by subject
            subject = session.get("subject", "unknown")
            subjects[subject] = subjects.get(subject, 0) + 1

            # Track understanding level
            topic = summary.get("topic", "unknown topic")
            understanding = summary.get("understanding_level")

            if understanding == "struggling":
                struggling_topics.append(topic)
            elif understanding == "mastered":
                mastered_topics.append(topic)
            elif understanding == "learning":
                learning_topics.append(topic)

        logger.info(
            "generated_session_summary",
            child_id=self.child_id,
            timeframe=timeframe,
            total_questions=total_questions,
            struggling_count=len(struggling_topics),
            mastered_count=len(mastered_topics),
        )

        return {
            "total_questions": total_questions,
            "timeframe": timeframe,
            "subjects_covered": subjects,
            "struggling_topics": list(set(struggling_topics)),  # Deduplicate
            "mastered_topics": list(set(mastered_topics)),
            "learning_topics": list(set(learning_topics)),
            "sessions": [self._format_session_preview(s) for s in sessions],
        }

    async def get_session_transcript(self, session_id: str) -> dict[str, Any]:
        """
        Get full transcript of a tutoring session.

        Args:
            session_id: Unique session identifier

        Returns:
            dict with:
                - session_id: Session identifier
                - timestamp: When session occurred
                - subject: Subject area
                - conversation: Full conversation history
                - parent_summary: Summary for parent
                - citations: Textbook references used

        Example:
            >>> transcript = await dashboard.get_session_transcript("sess_456")
            >>> for turn in transcript['conversation']:
            ...     print(f"{turn['role']}: {turn['content']}")
        """
        session = await self.memory.get_session(session_id)

        if not session:
            logger.warning(
                "session_not_found", child_id=self.child_id, session_id=session_id
            )
            return {}

        return {
            "session_id": session_id,
            "timestamp": session.get("timestamp"),
            "subject": session.get("subject"),
            "conversation": session.get("conversation_history", []),
            "parent_summary": session.get("parent_summary", {}),
            "citations": session.get("citations", []),
        }

    async def get_learning_progress(
        self, subject: str | None = None, days: int = 30
    ) -> dict[str, Any]:
        """
        Track child's learning progress over time.

        Args:
            subject: Optional subject filter
            days: Number of days to analyze (default 30)

        Returns:
            dict with:
                - subject: Subject analyzed (or "all_subjects")
                - timeframe: Number of days
                - weekly_progress: Dict of week -> understanding levels
                - total_sessions: Total sessions in timeframe
                - improvement_trend: "improving", "stable", "declining"

        Example:
            >>> progress = await dashboard.get_learning_progress(
            ...     subject="math",
            ...     days=30
            ... )
            >>> print(f"Trend: {progress['improvement_trend']}")
        """
        # Get sessions from last N days
        start_time = datetime.now() - timedelta(days=days)
        sessions = await self.memory.get_sessions(
            child_id=self.child_id, start_time=start_time, session_type="education"
        )

        # Filter by subject if provided
        if subject:
            sessions = [s for s in sessions if s.get("subject") == subject]

        # Track progress by week
        weekly_progress: dict[int, dict[str, int]] = {}

        for session in sessions:
            # Get week number (ISO calendar)
            timestamp = session.get("timestamp", datetime.now())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)

            week = timestamp.isocalendar()[1]
            summary = session.get("parent_summary", {})
            understanding = summary.get("understanding_level", "unknown")

            if week not in weekly_progress:
                weekly_progress[week] = {
                    "struggling": 0,
                    "learning": 0,
                    "mastered": 0,
                    "unknown": 0,
                }

            weekly_progress[week][understanding] = (
                weekly_progress[week].get(understanding, 0) + 1
            )

        # Calculate improvement trend
        improvement_trend = self._calculate_trend(weekly_progress)

        return {
            "subject": subject or "all_subjects",
            "timeframe": f"{days}_days",
            "weekly_progress": weekly_progress,
            "total_sessions": len(sessions),
            "improvement_trend": improvement_trend,
        }

    async def get_concerns_alert(self) -> list[dict[str, Any]]:
        """
        Get list of concerns that need parent attention.

        Returns:
            List of concern objects with:
                - topic: Topic causing concern
                - severity: "low", "medium", "high"
                - reason: Why it's flagged
                - sessions_count: How many sessions on this topic
                - recommendation: What parent should do

        Example:
            >>> concerns = await dashboard.get_concerns_alert()
            >>> for concern in concerns:
            ...     if concern['severity'] == 'high':
            ...         print(f"Attention needed: {concern['topic']}")
        """
        # Get recent sessions (last 7 days)
        start_time = datetime.now() - timedelta(days=7)
        sessions = await self.memory.get_sessions(
            child_id=self.child_id, start_time=start_time, session_type="education"
        )

        # Track topics with multiple struggling sessions
        struggling_topics: dict[str, list[dict[str, Any]]] = {}

        for session in sessions:
            summary = session.get("parent_summary", {})

            if summary.get("understanding_level") == "struggling":
                topic = summary.get("topic", "unknown")

                if topic not in struggling_topics:
                    struggling_topics[topic] = []

                struggling_topics[topic].append(summary)

        # Generate concern alerts
        concerns = []

        for topic, summaries in struggling_topics.items():
            session_count = len(summaries)

            # Determine severity based on frequency
            if session_count >= 3:
                severity = "high"
                reason = f"Child has struggled with {topic} in {session_count} sessions this week"
                recommendation = "Consider additional support or tutoring in this area"
            elif session_count == 2:
                severity = "medium"
                reason = f"Child struggled with {topic} twice this week"
                recommendation = "Monitor progress; may need review or practice"
            else:
                severity = "low"
                reason = f"Child had difficulty with {topic}"
                recommendation = "Continue current approach"

            concerns.append(
                {
                    "topic": topic,
                    "severity": severity,
                    "reason": reason,
                    "sessions_count": session_count,
                    "recommendation": recommendation,
                }
            )

        # Sort by severity (high first)
        severity_order = {"high": 0, "medium": 1, "low": 2}
        concerns.sort(key=lambda x: severity_order.get(x["severity"], 3))

        logger.info(
            "generated_concerns_alert",
            child_id=self.child_id,
            concerns_count=len(concerns),
            high_severity=len([c for c in concerns if c["severity"] == "high"]),
        )

        return concerns

    def _get_start_time(self, timeframe: str) -> datetime:
        """Convert timeframe string to datetime."""

        now = datetime.now()

        if timeframe == "today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == "week":
            return now - timedelta(days=7)
        elif timeframe == "month":
            return now - timedelta(days=30)
        else:  # "all" or unknown
            return datetime.min

    def _format_session_preview(self, session: dict[str, Any]) -> dict[str, Any]:
        """Format session data for preview (not full transcript)."""

        summary = session.get("parent_summary", {})

        return {
            "session_id": session.get("session_id"),
            "timestamp": session.get("timestamp"),
            "subject": session.get("subject"),
            "topic": summary.get("topic"),
            "understanding_level": summary.get("understanding_level"),
            "learning_outcome": summary.get("learning_outcome"),
        }

    def _calculate_trend(self, weekly_progress: dict[int, dict[str, int]]) -> str:
        """
        Calculate improvement trend from weekly progress data.

        Returns: "improving", "stable", or "declining"
        """
        if len(weekly_progress) < 2:
            return "stable"  # Not enough data

        # Get sorted weeks
        weeks = sorted(weekly_progress.keys())

        # Calculate mastery ratio for each week
        ratios = []
        for week in weeks:
            data = weekly_progress[week]
            total = sum(data.values())

            if total == 0:
                continue

            # Weight: mastered = 1.0, learning = 0.5, struggling = 0.0
            mastery_score = (
                data.get("mastered", 0) * 1.0
                + data.get("learning", 0) * 0.5
                + data.get("struggling", 0) * 0.0
            ) / total

            ratios.append(mastery_score)

        if len(ratios) < 2:
            return "stable"

        # Compare recent weeks to earlier weeks
        recent_avg = sum(ratios[-2:]) / 2  # Last 2 weeks
        earlier_avg = (
            sum(ratios[:-2]) / len(ratios[:-2]) if len(ratios) > 2 else ratios[0]
        )

        if recent_avg > earlier_avg + 0.1:  # 10% improvement
            return "improving"
        elif recent_avg < earlier_avg - 0.1:  # 10% decline
            return "declining"
        else:
            return "stable"
