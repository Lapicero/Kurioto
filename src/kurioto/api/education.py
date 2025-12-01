from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from google import genai

from kurioto.api.deps import (
    provide_material_manager,
    rate_limiter,
    require_parent_auth,
)
from kurioto.config import get_settings
from kurioto.education.material_manager import EducationalMaterialManager
from kurioto.education.parent_dashboard import EducationDashboard
from kurioto.memory import MemoryManager

# Simple in-memory registries for app lifetime
memory_registry: dict[str, MemoryManager] = {}
material_registry: dict[str, EducationalMaterialManager] = {}

router = APIRouter(prefix="/api", tags=["education"])


def get_memory(child_id: str) -> MemoryManager:
    if child_id not in memory_registry:
        memory_registry[child_id] = MemoryManager(
            child_id=child_id, max_episodic_entries=100
        )
    return memory_registry[child_id]


def get_material_manager(child_id: str) -> EducationalMaterialManager:
    if child_id in material_registry:
        return material_registry[child_id]
    settings = get_settings()
    if not settings.validate_api_key():
        raise RuntimeError("Google API key not configured; uploads disabled")
    client = genai.Client(api_key=settings.google_api_key)
    mm = EducationalMaterialManager(child_id=child_id, client=client)
    material_registry[child_id] = mm
    return mm


@router.get(
    "/children/{child_id}/dashboard/summary",
    dependencies=[Depends(require_parent_auth), Depends(rate_limiter)],
)
async def get_dashboard_summary(
    child_id: str, timeframe: str = "week"
) -> dict[str, Any]:
    dashboard = EducationDashboard(
        child_id=child_id, memory_manager=get_memory(child_id)
    )
    return await dashboard.get_session_summary(timeframe=timeframe)


@router.get(
    "/children/{child_id}/dashboard/progress",
    dependencies=[Depends(require_parent_auth), Depends(rate_limiter)],
)
async def get_dashboard_progress(
    child_id: str, subject: str | None = None, days: int = 30
) -> dict[str, Any]:
    dashboard = EducationDashboard(
        child_id=child_id, memory_manager=get_memory(child_id)
    )
    return await dashboard.get_learning_progress(subject=subject, days=days)


@router.get(
    "/children/{child_id}/dashboard/concerns",
    dependencies=[Depends(require_parent_auth), Depends(rate_limiter)],
)
async def get_dashboard_concerns(child_id: str) -> list[dict[str, Any]]:
    dashboard = EducationDashboard(
        child_id=child_id, memory_manager=get_memory(child_id)
    )
    return await dashboard.get_concerns_alert()


@router.post(
    "/children/{child_id}/materials/textbook",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_parent_auth), Depends(rate_limiter)],
)
async def upload_textbook(
    child_id: str,
    file: UploadFile,
    subject: str = Form(...),
    grade_level: str = Form(...),
    metadata_json: str | None = Form(None),
    mm: EducationalMaterialManager = Depends(provide_material_manager),
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.validate_api_key():
        raise HTTPException(
            status_code=400, detail="Uploads require Google API key; set GOOGLE_API_KEY"
        )
    # Prepare metadata
    import json

    metadata: dict[str, Any] | None = None
    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid metadata_json; must be valid JSON"
            )
    # Ensure manager and store
    await mm.initialize_store()
    # Persist uploaded file to a temp path
    import tempfile
    from pathlib import Path

    data = await file.read()
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(file.filename or "uploaded").suffix
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    op_name = await mm.upload_textbook(
        tmp_path, subject=subject, grade_level=grade_level, metadata=metadata
    )
    return {"operation": op_name}


@router.post(
    "/children/{child_id}/materials/homework",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_parent_auth), Depends(rate_limiter)],
)
async def upload_homework(
    child_id: str,
    file: UploadFile,
    subject: str = Form(...),
    assignment_name: str = Form(...),
    due_date: str | None = Form(None),
    mm: EducationalMaterialManager = Depends(provide_material_manager),
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.validate_api_key():
        raise HTTPException(
            status_code=400, detail="Uploads require Google API key; set GOOGLE_API_KEY"
        )
    await mm.initialize_store()
    import tempfile
    from pathlib import Path

    data = await file.read()
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(file.filename or "uploaded").suffix
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    op_name = await mm.upload_homework(
        tmp_path, subject=subject, assignment_name=assignment_name, due_date=due_date
    )
    return {"operation": op_name}


@router.post(
    "/children/{child_id}/materials/study_guide",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_parent_auth), Depends(rate_limiter)],
)
async def upload_study_guide(
    child_id: str,
    file: UploadFile,
    subject: str = Form(...),
    topic: str = Form(...),
    mm: EducationalMaterialManager = Depends(provide_material_manager),
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.validate_api_key():
        raise HTTPException(
            status_code=400, detail="Uploads require Google API key; set GOOGLE_API_KEY"
        )
    await mm.initialize_store()
    import tempfile
    from pathlib import Path

    data = await file.read()
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(file.filename or "uploaded").suffix
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    op_name = await mm.upload_study_guide(tmp_path, subject=subject, topic=topic)
    return {"operation": op_name}
