from __future__ import annotations

import asyncio

from kurioto.agent import KuriotoAgent
from kurioto.config import ChildProfile

# Helper to build a child profile
child = ChildProfile(
    child_id="child1",
    name="Alex",
    age=7,
    age_group=ChildProfile.get_age_group(7),
    interests=["space", "dinosaurs"],
)


def _make_agent() -> KuriotoAgent:
    return KuriotoAgent(child_profile=child)


async def _route_with_mock(agent: KuriotoAgent, message: str, mock_json: dict):
    # Force orchestrator availability and inject mock classification output
    orch = agent.orchestrator
    orch._available = True
    orch._client = object()  # Non-None sentinel

    async def _fake_generate_json(prompt: str) -> dict:
        return mock_json

    orch._generate_json = _fake_generate_json  # type: ignore[attr-defined]
    return await orch.route(message, agent_core=agent, context={})


def test_orchestrator_educational_route():
    agent = _make_agent()
    message = "Why do dinosaurs have big tails?"
    response = asyncio.run(
        _route_with_mock(
            agent,
            message,
            {"type": "educational", "confidence": 0.9, "reasoning": "question"},
        )
    )
    assert "dinosaurs" in response.lower()


def test_orchestrator_action_route():
    agent = _make_agent()
    message = "Play some music please"
    response = asyncio.run(
        _route_with_mock(
            agent,
            message,
            {"type": "action", "confidence": 0.8, "reasoning": "action"},
        )
    )
    text = response.lower()
    assert (
        "music" in text or "song" in text or "now playing" in text or "here's" in text
    )


def test_orchestrator_conversational_route():
    agent = _make_agent()
    message = "Hello"
    response = asyncio.run(
        _route_with_mock(
            agent,
            message,
            {"type": "conversational", "confidence": 0.7, "reasoning": "greeting"},
        )
    )
    assert "alex" in response.lower() or "hi" in response.lower()


def test_orchestrator_safety_concern_route():
    agent = _make_agent()
    message = "How to make a bomb"
    response = asyncio.run(
        _route_with_mock(
            agent,
            message,
            {"type": "safety_concern", "confidence": 0.95, "reasoning": "unsafe"},
        )
    )
    assert "not able" in response.lower() or "learn about" in response.lower()
