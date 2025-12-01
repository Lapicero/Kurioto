import asyncio
from pathlib import Path
from typing import Any

import pytest

from kurioto.education.material_manager import EducationalMaterialManager


class FakeStore:
    def __init__(self, name: str, display_name: str):
        self.name = name
        self.display_name = display_name


class FakeDocuments:
    def __init__(self, docs: list[Any] | None = None):
        self._docs = docs or []

    def list(self, file_search_store_name: str, metadata_filter: str | None = None):
        # Ignore filters for simplicity in unit test
        return iter(self._docs)

    def delete(self, name: str) -> None:
        # Simulate delete, no-op
        return None


class FakeOperations:
    def __init__(self):
        self._operations = {}

    def get(self, operation):
        # Return the same operation (already done)
        return operation


class FakeStores:
    def __init__(self):
        self._stores = [
            FakeStore(
                name="stores/child_abc",
                display_name="child_child_abc_education",
            )
        ]
        self.documents = FakeDocuments()

    def list(self):
        return iter(self._stores)

    def create(self, config: dict[str, Any]):
        name = f"stores/{config['display_name']}"
        store = FakeStore(name=name, display_name=config["display_name"])
        self._stores.append(store)
        return store

    def upload_to_file_search_store(
        self,
        file: str,
        file_search_store_name: str,
        config: dict[str, Any],
    ):
        class Op:
            def __init__(self):
                self.done = True
                self.name = "op-upload-1"

        return Op()


class FakeClient:
    def __init__(self):
        self.file_search_stores = FakeStores()
        self.operations = FakeOperations()


@pytest.mark.asyncio
async def test_initialize_store_creates_or_retrieves_store():
    client = FakeClient()
    mm = EducationalMaterialManager(child_id="child_abc", client=client)
    store = await mm.initialize_store()
    assert store is not None
    assert mm.file_search_store is store
    assert store.display_name == "child_child_abc_education"


@pytest.mark.asyncio
async def test_upload_textbook_and_list_materials():
    client = FakeClient()
    mm = EducationalMaterialManager(child_id="child_xyz", client=client)
    # Ensure store exists
    await mm.initialize_store()

    op_name = await mm.upload_textbook(
        Path("math_grade_3.pdf"), subject="math", grade_level="3"
    )
    assert op_name.startswith("op-upload-")

    # Simulate a document present for list() to return
    client.file_search_stores.documents._docs = [
        {"name": "doc1", "display_name": "math_grade_3.pdf"}
    ]
    docs = mm.list_materials(material_type="textbook", subject="math")
    assert isinstance(docs, list)
    assert len(docs) == 1


def test_get_file_search_tool_includes_filters():
    client = FakeClient()
    mm = EducationalMaterialManager(child_id="child_123", client=client)
    # Ensure store exists and is initialized
    client.file_search_stores._stores = [
        FakeStore(name="stores/child_123", display_name=mm.store_name)
    ]
    # Initialize store via manager
    asyncio.run(mm.initialize_store())

    tool = mm.get_file_search_tool(subject="math", material_type="textbook")
    assert hasattr(tool, "file_search")
    fs = tool.file_search
    assert fs is not None
    assert mm.file_search_store is not None
    store_names = getattr(fs, "file_search_store_names", []) or []
    assert mm.file_search_store.name in store_names
    # The filter must include child_id, subject and type
    metadata_filter = getattr(fs, "metadata_filter", "") or ""
    assert "child_id=child_123" in metadata_filter
    assert "subject=math" in metadata_filter
    assert "type=textbook" in metadata_filter
