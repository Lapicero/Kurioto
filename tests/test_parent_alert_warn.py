from __future__ import annotations

from kurioto.agent import KuriotoAgent
from kurioto.config import ChildProfile
from kurioto.safety.base import (
    SafetyAction,
    SafetyCategory,
    SafetyResult,
    SafetySeverity,
)

child = ChildProfile(
    child_id="child_warn",
    name="Alex",
    age=8,
    age_group=ChildProfile.get_age_group(8),
    interests=["space"],
)


def _make_agent() -> KuriotoAgent:
    return KuriotoAgent(child)


async def test_parent_alert_logged_on_warn_parent(monkeypatch):
    agent = _make_agent()

    # Mock SafetyAgent to return WARN_PARENT action
    async def fake_pre_check(user_input: str):
        return SafetyResult(
            action=SafetyAction.WARN_PARENT,
            reason="allowed but notify",
            severity=SafetySeverity.LOW,
            categories=[SafetyCategory.NONE],
        )

    class FakeAlert:
        subject = "Notice: Parental Attention"
        message = "Allowed content but notifying parent."
        follow_up_recommended = False
        urgency = "low"

    async def fake_generate_parent_alert(user_input: str, sr: SafetyResult):
        return FakeAlert()

    monkeypatch.setattr(agent.safety_agent, "pre_check", fake_pre_check)
    monkeypatch.setattr(
        agent.safety_agent, "generate_parent_alert", fake_generate_parent_alert
    )

    # Process a benign message to trigger WARN_PARENT path
    _ = await agent.process_message("I shared my full name online")

    # Retrieve parent dashboard logs
    dashboard = agent.tools["parent_dashboard"]
    logs = await dashboard.execute(action="get_logs")
    recent = logs.data["recent_logs"]

    # Assert that a parent_alert entry was logged for warn_parent
    parent_alerts = [e for e in recent if e["type"] == "parent_alert"]
    assert len(parent_alerts) >= 1
    alert_entry = parent_alerts[-1]
    assert alert_entry["data"]["subject"].startswith("Notice")
    assert alert_entry["data"]["urgency"] == "low"
    assert alert_entry["data"]["follow_up_recommended"] is False
