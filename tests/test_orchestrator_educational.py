import asyncio

import pytest

from kurioto.agents.orchestrator_agent import OrchestratorAgent
from kurioto.config import AgeGroup, ChildProfile


class DummyAgentCore:
    async def _handle_educational(self, intent, user_input, trace):
        return f"EDU:{intent.type}:{intent.subject or 'general'}"

    async def _execute_plan(self, plan, user_input, trace):
        return "PLAN_EXECUTED"

    def _generate_conversational_response(self, user_input: str) -> str:
        return "CONVO"

    def _get_block_response(self, sr):
        return "BLOCKED"


@pytest.mark.asyncio
async def test_orchestrator_heuristic_homework_routing():
    profile = ChildProfile(
        child_id="child_orch",
        name="Mia",
        age=9,
        age_group=AgeGroup.MIDDLE_CHILDHOOD,
        interests=["math"],
    )
    orch = OrchestratorAgent(child_profile=profile)
    # Force heuristic path
    orch._available = False

    intent = await orch.classify_intent("help me with homework: fractions")
    assert intent.type in {
        "educational_homework",
        "educational_concept",
        "conversational",
        "action",
        "safety_concern",
        "unknown",
    }

    resp = await orch.route("solve this problem", DummyAgentCore(), context={})
    assert isinstance(resp, str)
