from datetime import datetime, timedelta, timezone

import pytest

from kurioto.education.parent_dashboard import EducationDashboard
from kurioto.memory import MemoryManager


@pytest.mark.asyncio
async def test_dashboard_summaries_and_alerts():
    child_id = "child_dash"
    mm = MemoryManager(child_id=child_id, max_episodic_entries=100)
    dashboard = EducationDashboard(child_id=child_id, memory_manager=mm)

    # Log a few education sessions
    now = datetime.now(timezone.utc)
    sessions = [
        {
            "child_id": child_id,
            "session_type": "homework_help",
            "subject": "math",
            "question": "Add fractions",
            "response": "What do you notice?",
            "citations": [],
            "parent_summary": {"topic": "fractions", "understanding_level": "learning"},
            "timestamp": now.isoformat(),
        },
        {
            "child_id": child_id,
            "session_type": "homework_help",
            "subject": "science",
            "question": "Photosynthesis",
            "response": "Think about leaves",
            "citations": [],
            "parent_summary": {
                "topic": "photosynthesis",
                "understanding_level": "struggling",
            },
            "timestamp": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "child_id": child_id,
            "session_type": "concept_explanation",
            "subject": "math",
            "question": "Multiplication basics",
            "response": "Try grouping",
            "citations": [],
            "parent_summary": {
                "topic": "multiplication",
                "understanding_level": "mastered",
            },
            "timestamp": (now - timedelta(days=1)).isoformat(),
        },
    ]
    for s in sessions:
        mm.log_education_session(s)

    summary = await dashboard.get_session_summary(timeframe="week")
    assert summary["total_questions"] >= 3
    assert "subjects_covered" in summary

    alerts = await dashboard.get_concerns_alert()
    assert isinstance(alerts, list)

    progress = await dashboard.get_learning_progress(subject="math", days=7)
    assert "weekly_progress" in progress
