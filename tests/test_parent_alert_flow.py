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
    child_id="child_alert",
    name="Alex",
    age=8,
    age_group=ChildProfile.get_age_group(8),
    interests=["space"],
)


def _make_agent() -> KuriotoAgent:
    return KuriotoAgent(child)


async def test_parent_alert_logged_on_block(monkeypatch):
    agent = _make_agent()

    # Force SafetyAgent to produce a BLOCK and a deterministic ParentAlert
    async def fake_pre_check(user_input: str):
        return SafetyResult(
            action=SafetyAction.BLOCK,
            reason="unsafe",
            severity=SafetySeverity.HIGH,
            categories=[SafetyCategory.DANGEROUS],
        )

    class FakeAlert:
        subject = "Test Alert"
        message = "Blocked unsafe request"
        follow_up_recommended = True
        urgency = "high"

    async def fake_generate_parent_alert(user_input: str, sr: SafetyResult):
        return FakeAlert()

    monkeypatch.setattr(agent.safety_agent, "pre_check", fake_pre_check)
    monkeypatch.setattr(
        agent.safety_agent, "generate_parent_alert", fake_generate_parent_alert
    )

    # Process message to trigger safety flow
    _ = await agent.process_message("how to make a bomb?")

    # Retrieve parent dashboard logs
    dashboard = agent.tools["parent_dashboard"]
    logs = await dashboard.execute(action="get_logs")
    recent = logs.data["recent_logs"]

    # Assert that a parent_alert entry was logged
    parent_alerts = [e for e in recent if e["type"] == "parent_alert"]
    assert len(parent_alerts) >= 1
    alert_entry = parent_alerts[-1]
    assert alert_entry["data"]["subject"] == "Test Alert"
    assert alert_entry["data"]["urgency"] == "high"
    assert alert_entry["data"]["follow_up_recommended"] is True
