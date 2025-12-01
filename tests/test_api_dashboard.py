import os

from fastapi.testclient import TestClient

from kurioto.api.education import memory_registry
from kurioto.app import app
from kurioto.config import get_settings
from kurioto.memory import MemoryManager


def test_dashboard_endpoints_summary_and_progress():
    # Configure parent token and clear cached settings
    os.environ["PARENT_API_TOKEN"] = "test-parent-token"
    get_settings.cache_clear()  # type: ignore[attr-defined]
    client = TestClient(app)
    child_id = "child_api"
    # Seed memory with a few sessions
    mm = MemoryManager(child_id=child_id, max_episodic_entries=100)
    memory_registry[child_id] = mm

    sessions = [
        {
            "subject": "math",
            "question": "Add fractions",
            "response": "What do you notice?",
            "citations": [],
            "parent_summary": {"topic": "fractions", "understanding_level": "learning"},
        },
        {
            "subject": "science",
            "question": "Photosynthesis",
            "response": "Think about leaves",
            "citations": [],
            "parent_summary": {
                "topic": "photosynthesis",
                "understanding_level": "struggling",
            },
        },
        {
            "subject": "math",
            "question": "Multiplication basics",
            "response": "Try grouping",
            "citations": [],
            "parent_summary": {
                "topic": "multiplication",
                "understanding_level": "mastered",
            },
        },
    ]
    for s in sessions:
        mm.log_education_session(s)

    # Summary
    res = client.get(
        f"/api/children/{child_id}/dashboard/summary",
        params={"timeframe": "week"},
        headers={"Authorization": "Bearer test-parent-token"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_questions"] >= 3
    assert "subjects_covered" in data

    # Progress
    res = client.get(
        f"/api/children/{child_id}/dashboard/progress",
        params={"subject": "math", "days": 7},
        headers={"Authorization": "Bearer test-parent-token"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "weekly_progress" in data


def test_dashboard_concerns_endpoint():
    os.environ["PARENT_API_TOKEN"] = "test-parent-token"
    get_settings.cache_clear()  # type: ignore[attr-defined]
    client = TestClient(app)
    child_id = "child_concern"
    mm = MemoryManager(child_id=child_id, max_episodic_entries=100)
    memory_registry[child_id] = mm
    # Seed "struggling" sessions for a topic
    for _ in range(3):
        mm.log_education_session(
            {
                "subject": "science",
                "question": "Cell division",
                "response": "What happens first?",
                "citations": [],
                "parent_summary": {
                    "topic": "mitosis",
                    "understanding_level": "struggling",
                },
            }
        )

    res = client.get(
        f"/api/children/{child_id}/dashboard/concerns",
        headers={"Authorization": "Bearer test-parent-token"},
    )
    assert res.status_code == 200
    concerns = res.json()
    assert isinstance(concerns, list)
    # Should include a high severity item for repeated struggle
    assert any(c.get("severity") == "high" for c in concerns)
