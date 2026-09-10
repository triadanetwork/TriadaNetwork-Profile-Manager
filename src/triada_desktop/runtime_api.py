from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .runtime_manager import install, list_versions, remove, set_active, status

router = APIRouter(prefix="/api/v1/system/runtime", tags=["Desktop Runtime"])


@router.get("")
def runtime_status() -> dict:
    s = status()
    return {
        "available": s.available,
        "executable": s.executable,
        "message": s.message,
        "active_version": s.active_version,
        "installed_versions": [v.__dict__ for v in s.installed_versions],
    }


@router.get("/versions")
def versions() -> dict:
    return list_versions()


class RuntimeAction(BaseModel):
    specifier: str | None = Field(default=None, min_length=1, max_length=200)


@router.post("/install")
def install_runtime(payload: RuntimeAction) -> dict:
    try:
        return install(payload.specifier)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/activate")
def activate_runtime(payload: RuntimeAction) -> dict:
    if not payload.specifier:
        raise HTTPException(status_code=400, detail="specifier is required")
    try:
        return set_active(payload.specifier)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/remove")
def remove_runtime(payload: RuntimeAction) -> dict:
    if not payload.specifier:
        raise HTTPException(status_code=400, detail="specifier is required")
    try:
        return remove(payload.specifier)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
