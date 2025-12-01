import os
from io import BytesIO
from typing import cast

from fastapi.testclient import TestClient

from kurioto.api.deps import set_material_manager_factory
from kurioto.app import app
from kurioto.education.material_manager import EducationalMaterialManager


class FakeMaterialManager:
    def __init__(self, child_id: str):
        self.child_id = child_id

    async def initialize_store(self):
        return object()

    async def upload_textbook(
        self, file_path, subject: str, grade_level: str, metadata=None
    ) -> str:
        return "op_textbook"

    async def upload_homework(
        self, file_path, subject: str, assignment_name: str, due_date: str | None = None
    ) -> str:
        return "op_homework"

    async def upload_study_guide(self, file_path, subject: str, topic: str) -> str:
        return "op_study"


def _setup_auth():
    os.environ["PARENT_API_TOKEN"] = "test-parent-token"
    # Settings cache cleared implicitly by testclient app startup if needed


def _set_fake_factory():
    def factory(child_id: str) -> EducationalMaterialManager:
        return cast(EducationalMaterialManager, FakeMaterialManager(child_id))

    set_material_manager_factory(factory)


def test_upload_textbook_with_fake_manager():
    _setup_auth()
    _set_fake_factory()
    client = TestClient(app)

    files = {"file": ("math.pdf", BytesIO(b"PDFDATA"), "application/pdf")}
    data = {"subject": "math", "grade_level": "3"}

    res = client.post(
        "/api/children/child_upload/materials/textbook",
        files=files,
        data=data,
        headers={"Authorization": "Bearer test-parent-token"},
    )
    assert res.status_code == 202
    assert res.json().get("operation") == "op_textbook"


def test_upload_homework_with_fake_manager():
    _setup_auth()
    _set_fake_factory()
    client = TestClient(app)

    files = {"file": ("hw.png", BytesIO(b"IMGDATA"), "image/png")}
    data = {
        "subject": "science",
        "assignment_name": "worksheet",
        "due_date": "2025-12-31",
    }

    res = client.post(
        "/api/children/child_upload/materials/homework",
        files=files,
        data=data,
        headers={"Authorization": "Bearer test-parent-token"},
    )
    assert res.status_code == 202
    assert res.json().get("operation") == "op_homework"


def test_upload_study_guide_with_fake_manager():
    _setup_auth()
    _set_fake_factory()
    client = TestClient(app)

    files = {"file": ("guide.pdf", BytesIO(b"PDFDATA"), "application/pdf")}
    data = {"subject": "history", "topic": "ancient rome"}

    res = client.post(
        "/api/children/child_upload/materials/study_guide",
        files=files,
        data=data,
        headers={"Authorization": "Bearer test-parent-token"},
    )
    assert res.status_code == 202
    assert res.json().get("operation") == "op_study"
