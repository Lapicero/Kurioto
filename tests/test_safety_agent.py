from __future__ import annotations

from kurioto.agents.safety_agent import SafetyAgent
from kurioto.config import ChildProfile
from kurioto.safety.base import (
    SafetyAction,
    SafetyCategory,
    SafetyResult,
    SafetySeverity,
)
from kurioto.safety.multi_layer import MultiLayerResult

child = ChildProfile(
    child_id="child_sa",
    name="Alex",
    age=8,
    age_group=ChildProfile.get_age_group(8),
    interests=["space"],
)


def _make_agent() -> SafetyAgent:
    return SafetyAgent(child)


async def test_pre_check_escalates_with_llm(monkeypatch):
    agent = _make_agent()

    async def fake_evaluate(text: str, skip_human_review: bool = False):
        # Base result suggests REVIEW with LOW severity
        base = SafetyResult(
            action=SafetyAction.REVIEW,
            reason="edge case",
            severity=SafetySeverity.LOW,
            categories=[SafetyCategory.NONE],
            confidence=0.5,
        )
        return MultiLayerResult(
            final_action=base.action,
            final_reason=base.reason,
            final_severity=base.severity,
            layer_results=[base],
            review_item_id=None,
            execution_time_ms=10.0,
            layers_executed=["regex"],
        )

    # Force LLM available and JSON response indicating escalation
    agent._available = True

    async def fake_generate_json(prompt: str):
        return {
            "is_safe": False,
            "severity": "high",
            "category": "dangerous",
            "reasoning": "subtle unsafe intent",
            "action": "block",
        }

    monkeypatch.setattr(agent, "_generate_json", fake_generate_json)
    monkeypatch.setattr(agent._multi_layer, "evaluate", fake_evaluate)

    result = await agent.pre_check("how to make a bomb?")
    assert result.action == SafetyAction.BLOCK
    assert result.severity in {SafetySeverity.HIGH, SafetySeverity.CRITICAL}


async def test_generate_parent_alert_template_fallback():
    agent = _make_agent()
    agent._available = False  # Force template path

    safety_result = SafetyResult(
        action=SafetyAction.BLOCK,
        reason="unsafe",
        severity=SafetySeverity.MEDIUM,
        categories=[SafetyCategory.DANGEROUS],
    )

    alert = await agent.generate_parent_alert("unsafe input", safety_result)
    assert "Safety Notice" in alert.subject
    assert child.name in alert.subject
    assert alert.urgency == "medium"
    assert alert.follow_up_recommended is True


async def test_generate_parent_alert_llm(monkeypatch):
    agent = _make_agent()
    agent._available = True

    async def fake_generate_json_alert(prompt: str):
        return {
            "subject": "Alert: Unsafe Request",
            "message": "We blocked a concerning request and logged it.",
            "follow_up_recommended": True,
            "urgency": "high",
        }

    monkeypatch.setattr(agent, "_generate_json", fake_generate_json_alert)

    sr = SafetyResult(
        action=SafetyAction.BLOCK,
        reason="unsafe",
        severity=SafetySeverity.HIGH,
        categories=[SafetyCategory.DANGEROUS],
    )

    alert = await agent.generate_parent_alert("unsafe input", sr)
    assert alert.subject.startswith("Alert:")
    assert alert.urgency == "high"
    assert alert.follow_up_recommended is True
