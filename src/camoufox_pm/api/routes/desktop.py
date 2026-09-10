from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from camoufox_pm.api.dependencies import get_profile_manager, require_profile_read
from camoufox_pm.api.models.system import ApiResponse
from triada_desktop.backup import create_backup, inspect_backup, restore_backup
from triada_desktop.integrity import check_data_integrity
from triada_desktop.bundle_security import build_encrypted_zip, read_encrypted_zip
from triada_desktop.migrations import plan as migration_plan, apply as apply_migrations
from triada_desktop.recovery import recovery_status, rollback_last_restore, quarantine_orphans, verify_backup_for_restore
from triada_desktop.support_bundle import create_support_bundle
from triada_desktop.update_center import check as check_update, stage as stage_update, pending as pending_update, install_pending
from triada_desktop import DESKTOP_APP_NAME, APP_VERSION

router = APIRouter()

@router.get("/desktop/data/status", operation_id="desktop_data_status")
async def desktop_data_status():
    return {"app": DESKTOP_APP_NAME, "version": APP_VERSION, "migration": migration_plan(), "recovery": recovery_status()}


@router.post("/desktop/data/migrate", operation_id="desktop_apply_migrations")
async def desktop_apply_migrations():
    try:
        state = apply_migrations()
        return {"applied": True, "version": state.version, "updated_at": state.updated_at}
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/desktop/recovery/rollback-last-restore", operation_id="desktop_rollback_last_restore")
async def desktop_rollback_last_restore():
    active = await get_profile_manager().get_active_browsers()
    if active:
        raise HTTPException(status_code=409, detail="Close all running browsers before rollback")
    try:
        return rollback_last_restore()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/desktop/recovery/quarantine-orphans", operation_id="desktop_quarantine_orphans")
async def desktop_quarantine_orphans():
    active = await get_profile_manager().get_active_browsers()
    if active:
        raise HTTPException(status_code=409, detail="Close all running browsers before quarantine")
    return quarantine_orphans()


@router.post("/desktop/support-bundle", operation_id="desktop_support_bundle")
async def desktop_support_bundle():
    path = create_support_bundle()
    return {"path": str(path), "filename": Path(path).name}


class UpdateCheckRequest(BaseModel):
    manifest_url: str | None = None
    current_version: str = APP_VERSION
    public_key_b64: str | None = None
    channel: str = "stable"


@router.post("/desktop/updates/check", operation_id="desktop_update_check")
async def desktop_update_check(payload: UpdateCheckRequest):
    try:
        return check_update(payload.manifest_url, payload.current_version, payload.public_key_b64, payload.channel)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc




class UpdateStageRequest(UpdateCheckRequest):
    pass


@router.post("/desktop/updates/stage", operation_id="desktop_update_stage")
async def desktop_update_stage(payload: UpdateStageRequest):
    try:
        result = check_update(payload.manifest_url, payload.current_version, payload.public_key_b64, payload.channel)
        if not result.get("update_available"):
            return result
        info = __import__("triada_desktop.updater", fromlist=["UpdateInfo"]).UpdateInfo(
            result["version"], result["download_url"], result["sha256"], None, result.get("channel", payload.channel), tuple(result.get("installer_args", []))
        )
        return stage_update(info)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/desktop/updates/install", operation_id="desktop_update_install")
async def desktop_update_install():
    try:
        return install_pending()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.get("/desktop/updates/pending", operation_id="desktop_pending_update")
async def desktop_pending_update():
    return {"pending": pending_update()}


@router.post("/desktop/backups/preflight", operation_id="desktop_backup_preflight")
async def desktop_backup_preflight(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Backup file name is required")
    import tempfile
    with tempfile.NamedTemporaryFile(prefix="triada-preflight-", suffix=".tnb", delete=False) as fh:
        while chunk := await file.read(1024 * 1024):
            fh.write(chunk)
        temp = Path(fh.name)
    try:
        return verify_backup_for_restore(temp)
    finally:
        temp.unlink(missing_ok=True)



@router.post("/desktop/backups", response_model=ApiResponse[dict], operation_id="create_desktop_backup")
async def create_desktop_backup(include_browser_data: bool = False):
    path = create_backup(include_browser_data=include_browser_data)
    return ApiResponse(success=True, message="Backup created", data={"path": str(path)})


@router.post("/desktop/backups/inspect", response_model=ApiResponse[dict], operation_id="inspect_desktop_backup")
async def inspect_desktop_backup(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Backup file name is required")
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(prefix="triada-upload-", suffix=".tnb", delete=False) as fh:
        while chunk := await file.read(1024 * 1024):
            fh.write(chunk)
        temp = Path(fh.name)
    try:
        manifest = inspect_backup(temp)
        return ApiResponse(success=True, message="Backup verified", data=manifest)
    finally:
        temp.unlink(missing_ok=True)


@router.post("/desktop/backups/restore", response_model=ApiResponse[None], operation_id="restore_desktop_backup")
async def restore_desktop_backup(include_browser_data: bool = False, file: UploadFile = File(...)):
    # Restore while no browsers are running to avoid replacing an active SQLite/WAL state.
    active = await get_profile_manager().get_active_browsers()
    if active:
        raise HTTPException(status_code=409, detail="Close all running browsers before restore")
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(prefix="triada-upload-", suffix=".tnb", delete=False) as fh:
        while chunk := await file.read(1024 * 1024):
            fh.write(chunk)
        temp = Path(fh.name)
    try:
        restore_backup(temp, include_browser_data=include_browser_data)
        return ApiResponse(success=True, message="Backup restored", data=None)
    finally:
        temp.unlink(missing_ok=True)


@router.get("/desktop/integrity", response_model=ApiResponse[dict], operation_id="desktop_data_integrity")
async def desktop_data_integrity():
    return ApiResponse(success=True, message="Integrity check complete", data=check_data_integrity())


@router.post("/desktop/backups/verify", response_model=ApiResponse[dict], operation_id="verify_desktop_backup")
async def verify_desktop_backup(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Backup file name is required")
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(prefix="triada-verify-", suffix=".tnb", delete=False) as fh:
        while chunk := await file.read(1024 * 1024):
            fh.write(chunk)
        temp = Path(fh.name)
    try:
        manifest = inspect_backup(temp)
        return ApiResponse(success=True, message="Backup verified", data=manifest)
    finally:
        temp.unlink(missing_ok=True)


class SecureBundleRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    profile_ids: list[str] = Field(default_factory=list, max_length=200)


@router.post("/desktop/secure-bundle/export", operation_id="export_secure_account_bundle")
async def export_secure_bundle(payload: SecureBundleRequest):
    # Security boundary: bundle export uses metadata-only envelopes here. Session/cookie material
    # is intentionally not read from raw profile files; the existing cookie APIs remain local.
    from camoufox_pm.api.dependencies import get_storage_manager
    import json
    ids = payload.profile_ids
    if not ids:
        raise HTTPException(status_code=400, detail="profile_ids is required")
    files = {}
    for pid in ids:
        profile = await get_profile_manager().get_profile(pid)
        if not profile:
            continue
        files[f"{pid}.profile.json"] = json.dumps({"profile_id": profile.id, "profile_name": profile.name}, separators=(",", ":")).encode()
    if not files:
        raise HTTPException(status_code=404, detail="No matching profiles")
    return Response(content=build_encrypted_zip(files, payload.password, kind="account-metadata"), media_type="application/octet-stream", headers={"Content-Disposition": 'attachment; filename="triada-secure-account-bundle.tnbx"', "Cache-Control": "no-store"})


@router.post("/desktop/secure-bundle/inspect", operation_id="inspect_secure_account_bundle")
async def inspect_secure_bundle(password: str = Form(...), file: UploadFile = File(...)):
    raw = await file.read(15 * 1024 * 1024 + 1)
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Secure bundle too large (15 MB max)")
    try:
        files = read_encrypted_zip(raw, password, kind="account-metadata")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"files": sorted(files), "count": len(files)}
