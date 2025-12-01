from __future__ import annotations

import os

import pytest

from kurioto.agent import KuriotoAgent
from kurioto.config import ChildProfile

child = ChildProfile(
    child_id="child_integration",
    name="Alex",
    age=7,
    age_group=ChildProfile.get_age_group(7),
    interests=["space", "science"],
)


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY not set; skipping real LLM integration test",
)
async def test_classify_intent_with_real_llm(monkeypatch: pytest.MonkeyPatch):
    # Force LLM path to ensure we exercise the real API
    monkeypatch.setenv("KURIOTO_FORCE_LLM", "true")

    agent = KuriotoAgent(child_profile=child)

    # If SDK is missing or client can't init, skip
    if not agent.orchestrator.is_available:
        pytest.skip(
            "Orchestrator LLM not available (SDK missing or client init failed)"
        )

    message = "Why do stars twinkle at night?"
    try:
        intent = await agent.orchestrator.classify_intent(message)
    except Exception as e:  # Gracefully handle quota/rate-limit issues in CI/dev
        msg = str(e).lower()
        if (
            "resource_exhausted" in msg
            or "rate limit" in msg
            or "quota" in msg
            or "429" in msg
        ):
            pytest.skip(f"Skipping due to API quota/rate limit: {e}")
        raise

    assert intent.type in {
        "educational",
        "conversational",
        "action",
        "safety_concern",
        "unknown",
    }
    assert 0.0 <= float(intent.confidence) <= 1.0

    # Verify we actually used the LLM path
    assert getattr(agent.orchestrator, "_last_llm_used", False) is True
