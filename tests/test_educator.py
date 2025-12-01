from typing import Any

import pytest

from kurioto.agents.educator import EducatorAgent
from kurioto.config import AgeGroup, ChildProfile


class FakeGroundingChunks:
    def __init__(self):
        self.grounding_chunks = []


class FakeCandidate:
    def __init__(self):
        self.grounding_metadata = FakeGroundingChunks()


class FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.candidates = [FakeCandidate()]


class FakeModels:
    async def generate_content(self, _model: str, _contents: str, _config: Any):
        # Return a Socratic-style response (includes a question and guidance)
        return FakeResponse(
            "What do you notice about the denominators? Can you try a step?"
        )


class FakeStores:
    def __init__(self, display_name: str):
        class Store:
            def __init__(self, name: str, display_name: str):
                self.name = name
                self.display_name = display_name

        self._store = Store(name=f"stores/{display_name}", display_name=display_name)

    def list(self):
        return iter([self._store])

    def create(self, config: dict[str, Any]):
        return self._store


class FakeClient:
    def __init__(self, display_name: str):
        self.models = FakeModels()
        self.file_search_stores = FakeStores(display_name=display_name)

        class Ops:
            def get(self, op):
                return op

        self.operations = Ops()


@pytest.mark.asyncio
async def test_tutor_homework_returns_socratic_guidance():
    profile = ChildProfile(
        child_id="child1",
        name="Alex",
        age=9,
        age_group=AgeGroup.MIDDLE_CHILDHOOD,
        interests=["math"],
    )
    client = FakeClient(display_name=f"child_{profile.child_id}_education")
    agent = EducatorAgent(child_profile=profile, client=client)
    # Ensure file search store is initialized
    await agent.material_manager.initialize_store()

    result = await agent.tutor_homework("How do I add 3/4 + 1/2?", subject="math")
    assert isinstance(result, dict)
    assert "response" in result
    # Socratic method: should ask questions, not give direct numeric answer
    assert "?" in result["response"]
    assert "add" in result["response"].lower() or "try" in result["response"].lower()


@pytest.mark.asyncio
async def test_explain_concept_returns_string():
    profile = ChildProfile(
        child_id="child2",
        name="Sam",
        age=10,
        age_group=AgeGroup.MIDDLE_CHILDHOOD,
        interests=["science"],
    )
    client = FakeClient(display_name=f"child_{profile.child_id}_education")
    agent = EducatorAgent(child_profile=profile, client=client)
    await agent.material_manager.initialize_store()

    explanation = await agent.explain_concept("photosynthesis", subject="science")
    assert isinstance(explanation, str)
    assert len(explanation) > 0
    # Should be under 200 words per prompt instruction, but we won't count words here
