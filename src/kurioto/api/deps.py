from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from google import genai

from kurioto.config import get_settings
from kurioto.education.material_manager import EducationalMaterialManager

# In-memory rate limit store: token -> [(timestamp), ...]
_rate_store: dict[str, list[float]] = {}


def require_parent_auth(authorization: str | None = Header(None)) -> str:
    """Require Authorization: Bearer <token> if configured.

    If `PARENT_API_TOKEN` (settings.parent_api_token) is set, enforce matching token.
    If not set, allow access (development convenience).
    Returns the token used (may be empty string if not configured).
    """
    settings = get_settings()
    configured = settings.parent_api_token
    if not configured:
        # No token configured; allow in development/test
        return ""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    token = authorization.split(" ", 1)[1].strip()
    if token != configured:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token"
        )
    return token


def rate_limiter(token: str = Depends(require_parent_auth)) -> None:
    """Naive in-memory rate limiter keyed by token (or empty string).

    Uses settings RATE_LIMIT_REQUESTS per RATE_LIMIT_WINDOW_SECONDS.
    """
    settings = get_settings()
    limit = settings.rate_limit_requests
    window = settings.rate_limit_window_seconds
    now = time.monotonic()
    key = token or "__public__"
    bucket = _rate_store.setdefault(key, [])
    # Drop old entries
    cutoff = now - window
    bucket[:] = [t for t in bucket if t >= cutoff]
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    bucket.append(now)


# Material manager factory injection
MATERIAL_MANAGER_FACTORY: Callable[[str], EducationalMaterialManager] | None = None


def set_material_manager_factory(
    factory: Callable[[str], EducationalMaterialManager],
) -> None:
    global MATERIAL_MANAGER_FACTORY
    MATERIAL_MANAGER_FACTORY = factory


def provide_material_manager(
    child_id: str, token: str = Depends(require_parent_auth)
) -> EducationalMaterialManager:
    """Provide EducationalMaterialManager via injectable factory or default constructor."""
    if MATERIAL_MANAGER_FACTORY:
        return MATERIAL_MANAGER_FACTORY(child_id)
    settings = get_settings()
    if not settings.validate_api_key():
        raise HTTPException(status_code=400, detail="Uploads require Google API key")
    client = genai.Client(api_key=settings.google_api_key)
    return EducationalMaterialManager(child_id=child_id, client=client)
