"""
API routes for managing profiles.
"""

import re
import json
import io
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from loguru import logger
from pydantic import ValidationError
from starlette.background import BackgroundTask

from camoufox_pm.api.dependencies import get_profile_manager, get_storage_manager, require_workspace_admin, require_profile_write, require_profile_delete, require_permission, get_current_role, profile_scope_sql
from camoufox_pm.api.errors import ApiError, validation_message
from camoufox_pm.api.models.profiles import (
    ActiveBrowsersResponse,
    BrowserCloseResponse,
    BrowsersCloseAllResponse,
    ClearGeographyRequest,
    ClearGeographyResponse,
    ProfileCloneRequest,
    ProfileCreateRequest,
    ProfileLaunchRequest,
    ProfileLaunchResponse,
    ProfileListResponse,
    ProfileResponse,
    ProfileStatsResponse,
    ProfileUpdateRequest,
    ProxyCheckRequest,
    ProxyCheckResponse,
    ReconcileOsRequest,
)
from camoufox_pm.api.models.system import ApiResponse, ExcelImportData
from camoufox_pm.core import proxy_check
from camoufox_pm.core.excel_manager import ExcelManager
from camoufox_pm.core.models import BrowserSettings, ProfileStatus, ProxyConfig
from camoufox_pm.config import get_settings


# These options affect behaviour but cannot replace the profile's proxy,
# storage directory, fingerprint config or Firefox preferences.  Everything
# else is deliberately rejected instead of becoming an undocumented escape
# hatch around profile isolation.
_ALLOWED_LAUNCH_OPTIONS = {"humanize", "geoip", "block_webrtc"}

router = APIRouter()

async def _enforce_profile_visibility(request: Request, profile_id: str) -> None:
    role = await get_current_role(request)
    if role != "buyer":
        return
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=403, detail="Profile visibility requires a user session")
    row = await get_storage_manager().db.get_profile_operations(profile_id)
    if row.get("owner_id") != user_id and row.get("assigned_user_id") != user_id:
        raise HTTPException(status_code=403, detail="Profile is not assigned to your workspace scope")


# Maps the deprecated flattened update fields onto their browser_settings keys.
_FLATTENED_BROWSER_FIELDS = {
    "browser_os": "os",
    "browser_screen": "screen",
    "browser_user_agent": "user_agent",
    "browser_languages": "languages",
    "browser_timezone": "timezone",
    "browser_locale": "locale",
    "browser_webrtc_mode": "webrtc_mode",
    "browser_canvas_noise": "canvas_noise",
    "browser_stable_canvas": "stable_canvas",
    "browser_webgl_noise": "webgl_noise",
    "browser_audio_noise": "audio_noise",
    "browser_hardware_concurrency": "hardware_concurrency",
    "browser_device_memory": "device_memory",
    "browser_max_touch_points": "max_touch_points",
    "browser_window_width": "window_width",
    "browser_window_height": "window_height",
}


@router.get(
    "/profiles",
    response_model=ProfileListResponse,
    operation_id="list_profiles",
    summary="List profiles.",
    description="List all profiles with filtering and pagination.",
)
async def list_profiles(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Profiles per page"),
    status: ProfileStatus | None = Query(None, description="Filter by status"),
    group: str | None = Query(None, description="Filter by group"),
    search: str | None = Query(None, description="Search by name"),
):
    """List profiles with filtering."""
    try:
        profile_manager = get_profile_manager()

        # Build the filters
        filters: dict[str, Any] = {}
        if status:
            filters["status"] = status
        if group:
            filters["group"] = group
        if search:
            filters["name_like"] = search

        role = await get_current_role(request)
        user_id = getattr(request.state, "user_id", None)
        scope_sql, scope_params = profile_scope_sql(role, user_id)
        if scope_sql:
            filters["workspace_profile_predicate"] = scope_sql
            filters["workspace_profile_params"] = scope_params

        # Fetch the profiles
        profiles = await profile_manager.list_profiles(filters=filters)

        # Pagination
        total = len(profiles)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_profiles = profiles[start_idx:end_idx]

        # Convert to API models
        profile_responses = []
        for profile in paginated_profiles:
            profile_responses.append(ProfileResponse.from_profile(profile))

        return ProfileListResponse(
            profiles=profile_responses,
            total=total,
            page=page,
            per_page=per_page,
            has_next=end_idx < total,
            has_prev=page > 1,
        )

    except Exception as e:
        logger.error(f"Failed to list profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/profiles",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_profile",
    summary="Create a profile.",
    description="Create a new profile with an auto-generated fingerprint.",
)
async def create_profile(request: ProfileCreateRequest, http_request: Request):
    """Create a new profile."""
    await require_permission(http_request, "profiles:write")
    try:
        profile_manager = get_profile_manager()

        # Create the profile
        profile = await profile_manager.create_profile(
            name=request.name,
            group=request.group,
            browser_settings=request.browser_settings,
            proxy_config=request.proxy_config,
            generate_fingerprint=request.generate_fingerprint,
            notes=request.notes,
            fingerprint_preset=request.fingerprint_preset,
        )

        # In production team mode, a buyer must be able to see profiles they create.
        # Owner/admin/TL workflows can reassign later through Profile Operations.
        if getattr(http_request.state, "workspace_role", None) == "buyer":
            await get_storage_manager().db.update_profile_operations(
                profile.id,
                {"owner": {"action": "set", "value": getattr(http_request.state, "user_id", None)}},
            )

        logger.info(f"Created profile: {profile.name} (ID: {profile.id})")
        await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.create', 'profile', profile.id, {'name': profile.name})

        return ProfileResponse.from_profile(profile)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to create profile: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e




@router.get('/profiles/trash', response_model=list[dict], operation_id='list_profile_trash')
async def list_profile_trash(http_request: Request):
    await require_profile_read(http_request)
    return await get_storage_manager().db.list_profile_trash()

@router.post('/profiles/trash/{profile_id}/restore', response_model=ProfileResponse, operation_id='restore_profile')
async def restore_profile(profile_id: str, http_request: Request):
    await require_profile_delete(http_request)
    try:
        profile = await get_profile_manager().restore_profile(profile_id)
    except Exception as exc:
        logger.error(f'Failed to restore profile {profile_id}: {exc}')
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not profile:
        raise HTTPException(status_code=404, detail='Profile not found in trash')
    await get_storage_manager().db.log_audit(getattr(http_request.state,'user_id',None),'profile.restore','profile',profile_id)
    return ProfileResponse.from_profile(profile)

@router.delete('/profiles/trash/{profile_id}', response_model=ApiResponse[None], operation_id='purge_profile')
async def purge_profile(profile_id: str, http_request: Request):
    await require_profile_delete(http_request)
    record=await get_storage_manager().db._get_profile_trash_record(profile_id)
    if not record: raise HTTPException(status_code=404, detail='Profile not found in trash')
    trash_path=Path(record.get('trashed_storage_path') or '')
    if trash_path.exists(): shutil.rmtree(trash_path, ignore_errors=True)
    await get_storage_manager().db.permanently_delete_trash(profile_id)
    await get_storage_manager().db.log_audit(getattr(http_request.state,'user_id',None),'profile.purge','profile',profile_id)
    return ApiResponse(success=True, message='Profile permanently removed', data=None)



def _normalize_cookie_payload(data: Any) -> list[dict[str, Any]]:
    """Normalize a standard Playwright-compatible cookie JSON payload."""
    cookies = data.get("cookies", data) if isinstance(data, dict) else data
    if not isinstance(cookies, list):
        raise ValueError("Expected a cookies array")
    normalized: list[dict[str, Any]] = []
    for cookie in cookies:
        if not isinstance(cookie, dict) or not cookie.get("name"):
            continue
        item = {
            key: cookie[key]
            for key in ("name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite", "url")
            if key in cookie
        }
        if not item.get("domain") and not item.get("url"):
            continue
        normalized.append(item)
    if not normalized:
        raise ValueError("No usable cookies found")
    return normalized


async def _apply_cookies_to_profile(profile_id: str, cookies: list[dict[str, Any]]) -> int:
    """Apply cookies to a closed profile using a temporary headless browser."""
    pm = get_profile_manager()
    if pm.browser_sessions.is_running(profile_id):
        raise ValueError("Close the browser before importing cookies")
    profile = await pm.get_profile(profile_id)
    if not profile:
        raise ValueError("Profile not found")
    from camoufox.async_api import AsyncCamoufox

    options = profile.to_camoufox_launch_options()
    options["headless"] = True
    cf = AsyncCamoufox(**options)
    ctx = await cf.start()
    try:
        if not hasattr(ctx, "add_cookies") and getattr(ctx, "contexts", None):
            ctx = ctx.contexts[0]
        await ctx.add_cookies(cookies)
    finally:
        await cf.__aexit__(None, None, None)
    return len(cookies)



@router.post('/profiles/cookies/export-bulk', operation_id='export_profiles_cookies_bulk')
async def export_profiles_cookies_bulk(request: Request, http_request: Request):
    """Export selected profiles' cookie jars as a ZIP of standard JSON cookie files."""
    await require_profile_write(http_request)
    body = await request.json()
    profile_ids = body.get('profile_ids') if isinstance(body, dict) else None
    if not isinstance(profile_ids, list) or not profile_ids or len(profile_ids) > 200:
        raise HTTPException(status_code=400, detail='profile_ids must contain 1-200 profiles')
    pm = get_profile_manager()
    buffer = io.BytesIO()
    exported = 0
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for profile_id in profile_ids:
            await _enforce_profile_visibility(http_request, str(profile_id))
            profile = await pm.get_profile(str(profile_id))
            if not profile:
                continue
            try:
                if pm.browser_sessions.is_running(profile.id):
                    session = pm.browser_sessions.active_sessions[profile.id]
                    context = getattr(session.camoufox, 'context', None) or getattr(session.camoufox, '_context', None) or session.camoufox
                    cookies = await context.cookies() if hasattr(context, 'cookies') else []
                else:
                    from camoufox.async_api import AsyncCamoufox
                    options = profile.to_camoufox_launch_options(); options['headless'] = True
                    cf = AsyncCamoufox(**options)
                    ctx = await cf.start()
                    try:
                        if not hasattr(ctx, 'cookies') and getattr(ctx, 'contexts', None): ctx = ctx.contexts[0]
                        cookies = await ctx.cookies()
                    finally:
                        await cf.__aexit__(None, None, None)
                safe_name = re.sub(r'[^A-Za-z0-9_.-]+', '-', profile.name).strip('-') or profile.id
                archive.writestr(f'{safe_name}.{profile.id}.cookies.json', json.dumps({
                    'format_version': 1, 'profile_id': profile.id, 'profile_name': profile.name, 'cookies': cookies
                }, ensure_ascii=False, indent=2))
                exported += 1
            except Exception as exc:
                logger.warning(f'Could not export cookies for {profile.id}: {exc}')
    await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.cookies.export_bulk', 'profile', None, {'count': exported})
    buffer.seek(0)
    return Response(content=buffer.getvalue(), media_type='application/zip', headers={
        'Content-Disposition': 'attachment; filename="triada-cookie-export.zip"', 'Cache-Control': 'no-store'
    })


@router.post('/profiles/cookies/import-bulk', operation_id='import_profiles_cookies_bulk')
async def import_profiles_cookies_bulk(file: UploadFile = File(...), http_request: Request = None):
    """Create one local profile per cookie JSON inside an uploaded ZIP."""
    await require_workspace_admin(http_request)
    raw = await file.read(25 * 1024 * 1024 + 1)
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='Bulk cookie archive too large (25 MB max)')
    if not file.filename or not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail='Upload a ZIP containing .cookies.json files')
    created: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    pm = get_profile_manager()
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = [n for n in archive.namelist() if n.lower().endswith(('.json', '.cookies.json')) and not n.endswith('/') and not n.startswith('__MACOSX/')][:100]
            if not entries:
                raise HTTPException(status_code=400, detail='ZIP contains no cookie JSON files')
            for entry in entries:
                try:
                    info = archive.getinfo(entry)
                    if info.file_size > 4 * 1024 * 1024:
                        raise ValueError('Cookie JSON exceeds 4 MB limit')
                    data = json.loads(archive.read(entry).decode('utf-8-sig'))
                    cookies = _normalize_cookie_payload(data)
                    file_stem = Path(entry).name
                    for suffix in ('.cookies.json', '.json'):
                        if file_stem.lower().endswith(suffix):
                            file_stem = file_stem[:-len(suffix)]
                            break
                    name = str(data.get('profile_name') or file_stem or f'Imported {len(created)+1}')[:255]
                    profile = await pm.create_profile(name)
                    try:
                        await _apply_cookies_to_profile(profile.id, cookies)
                    except Exception:
                        await pm.delete_profile(profile.id, remove_data=True, deleted_by=getattr(http_request.state, 'user_id', None))
                        raise
                    await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.cookies.import_bulk', 'profile', profile.id, {'count': len(cookies), 'source': file_stem})
                    created.append({'profile_id': profile.id, 'name': profile.name, 'cookies': len(cookies)})
                except Exception as exc:
                    errors.append({'file': entry, 'error': str(exc)})
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail='Invalid ZIP archive') from exc
    return {'created': created, 'created_count': len(created), 'error_count': len(errors), 'errors': errors}



async def _get_profile_cookies(profile_id: str) -> list[dict[str, Any]]:
    pm = get_profile_manager()
    profile = await pm.get_profile(profile_id)
    if not profile:
        raise ValueError("Profile not found")
    if pm.browser_sessions.is_running(profile_id):
        session = pm.browser_sessions.active_sessions[profile_id]
        context = getattr(session.camoufox, 'context', None) or getattr(session.camoufox, '_context', None) or session.camoufox
        return await context.cookies() if hasattr(context, 'cookies') else []
    from camoufox.async_api import AsyncCamoufox
    options = profile.to_camoufox_launch_options(); options['headless'] = True
    cf = AsyncCamoufox(**options)
    ctx = await cf.start()
    try:
        if not hasattr(ctx, 'cookies') and getattr(ctx, 'contexts', None): ctx = ctx.contexts[0]
        return await ctx.cookies()
    finally:
        await cf.__aexit__(None, None, None)


@router.post('/profiles/cookies/export-secure', operation_id='export_profiles_cookies_secure')
async def export_profiles_cookies_secure(request: Request, http_request: Request):
    """Export selected local profile cookie jars into a password-encrypted bundle.

    The bundle is produced locally and never sent to cloud services. Use only
    for sessions/accounts the operator is authorized to move.
    """
    await require_profile_write(http_request)
    body = await request.json()
    profile_ids = body.get('profile_ids') if isinstance(body, dict) else None
    password = body.get('password') if isinstance(body, dict) else None
    if not isinstance(profile_ids, list) or not profile_ids or len(profile_ids) > 100:
        raise HTTPException(status_code=400, detail='profile_ids must contain 1-100 profiles')
    if not isinstance(password, str) or len(password) < 8:
        raise HTTPException(status_code=400, detail='password must contain at least 8 characters')
    from triada_desktop.bundle_security import build_encrypted_zip
    files: dict[str, bytes] = {}
    for profile_id in profile_ids:
        await _enforce_profile_visibility(http_request, str(profile_id))
        profile = await get_profile_manager().get_profile(str(profile_id))
        if not profile:
            continue
        cookies = await _get_profile_cookies(profile.id)
        safe_name = re.sub(r'[^A-Za-z0-9_.-]+', '-', profile.name).strip('-') or profile.id
        files[f'{safe_name}.{profile.id}.cookies.json'] = json.dumps({
            'format_version': 1,
            'profile_id': profile.id,
            'profile_name': profile.name,
            'cookies': cookies,
        }, ensure_ascii=False).encode('utf-8')
    if not files:
        raise HTTPException(status_code=404, detail='No matching profiles')
    bundle = build_encrypted_zip(files, password, kind='cookie-bundle')
    await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.cookies.export_secure', 'profile', None, {'count': len(files), 'encrypted': True})
    return Response(content=bundle, media_type='application/octet-stream', headers={
        'Content-Disposition': 'attachment; filename="triada-secure-cookie-bundle.tnbx"',
        'Cache-Control': 'no-store',
    })


@router.post('/profiles/cookies/import-secure', operation_id='import_profiles_cookies_secure')
async def import_profiles_cookies_secure(file: UploadFile = File(...), password: str = Form(...), http_request: Request = None):
    """Import a password-encrypted cookie bundle as new local profiles."""
    await require_workspace_admin(http_request)
    if len(password) < 8:
        raise HTTPException(status_code=400, detail='password must contain at least 8 characters')
    raw = await file.read(25 * 1024 * 1024 + 1)
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='Secure cookie bundle too large (25 MB max)')
    from triada_desktop.bundle_security import read_encrypted_zip
    try:
        files = read_encrypted_zip(raw, password, kind='cookie-bundle')
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if len(files) > 100:
        raise HTTPException(status_code=400, detail='Secure cookie bundle contains too many files')
    created: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    pm = get_profile_manager()
    for name, content in files.items():
        if not name.lower().endswith('.json'):
            continue
        try:
            data = json.loads(content.decode('utf-8-sig'))
            cookies = _normalize_cookie_payload(data)
            profile_name = str(data.get('profile_name') or Path(name).stem)[:255]
            profile = await pm.create_profile(profile_name)
            try:
                await _apply_cookies_to_profile(profile.id, cookies)
            except Exception:
                await pm.delete_profile(profile.id, remove_data=True, deleted_by=getattr(http_request.state, 'user_id', None))
                raise
            await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.cookies.import_secure', 'profile', profile.id, {'count': len(cookies), 'encrypted': True})
            created.append({'profile_id': profile.id, 'name': profile.name, 'cookies': len(cookies)})
        except Exception as exc:
            errors.append({'file': name, 'error': str(exc)})
    return {'created': created, 'created_count': len(created), 'error_count': len(errors), 'errors': errors}

@router.get('/profiles/{profile_id}/cookies/export', operation_id='export_profile_cookies')
async def export_profile_cookies(profile_id: str, http_request: Request):
    """Export the current profile cookie jar for local/session portability."""
    await require_profile_write(http_request)
    await _enforce_profile_visibility(http_request, profile_id)
    pm=get_profile_manager()
    profile=await pm.get_profile(profile_id)
    if not profile: raise HTTPException(status_code=404, detail='Profile not found')
    if pm.browser_sessions.is_running(profile_id):
        session=pm.browser_sessions.active_sessions[profile_id]
        context = getattr(session.camoufox, 'context', None) or getattr(session.camoufox, '_context', None) or session.camoufox
        cookies = await context.cookies() if hasattr(context,'cookies') else []
    else:
        from camoufox.async_api import AsyncCamoufox
        options=profile.to_camoufox_launch_options(); options['headless']=True
        cf=AsyncCamoufox(**options)
        ctx=await cf.start()
        try:
            if not hasattr(ctx,'cookies') and getattr(ctx,'contexts',None): ctx=ctx.contexts[0]
            cookies=await ctx.cookies()
        finally:
            await cf.__aexit__(None,None,None)
    payload=json.dumps({'format_version':1,'profile_id':profile_id,'profile_name':profile.name,'cookies':cookies}, ensure_ascii=False, indent=2).encode()
    return Response(content=payload, media_type='application/json', headers={'Content-Disposition':f'attachment; filename="{re.sub(r"[^A-Za-z0-9_.-]+","-",profile.name).strip("-") or profile_id}.cookies.json"','Cache-Control':'no-store'})

@router.post('/profiles/{profile_id}/cookies/import', response_model=dict, operation_id='import_profile_cookies')
async def import_profile_cookies(profile_id: str, file: UploadFile = File(...), http_request: Request = None):
    """Import a cookie jar into an existing local profile. Use only with accounts you own/are authorised to access."""
    await require_profile_write(http_request)
    await _enforce_profile_visibility(http_request, profile_id)
    pm=get_profile_manager(); profile=await pm.get_profile(profile_id)
    if not profile: raise HTTPException(status_code=404, detail='Profile not found')
    if pm.browser_sessions.is_running(profile_id):
        raise HTTPException(status_code=409, detail='Close the browser before importing cookies')
    raw=await file.read(2*1024*1024+1)
    if len(raw)>2*1024*1024: raise HTTPException(status_code=413, detail='Cookie file too large (2 MB max)')
    try:
        data = json.loads(raw.decode('utf-8-sig'))
        normalized = _normalize_cookie_payload(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f'Invalid cookie JSON: {exc}') from exc
    try:
        await _apply_cookies_to_profile(profile_id, normalized)
    except ValueError as exc:
        raise HTTPException(status_code=409 if 'Close the browser' in str(exc) else 400, detail=str(exc)) from exc
    await get_storage_manager().db.log_audit(getattr(http_request.state,'user_id',None),'profile.cookies.import','profile',profile_id,{'count':len(normalized)})
    return {'profile_id':profile_id,'imported':len(normalized)}

@router.get(
    "/profiles/{profile_id}",
    response_model=ProfileResponse,
    operation_id="get_profile",
    summary="Get a profile.",
    description="Get detailed information about a profile.",
)
async def get_profile(profile_id: str, http_request: Request):
    """Get a profile by ID."""
    await require_permission(http_request, "profiles:read")
    await _enforce_profile_visibility(http_request, profile_id)
    try:
        profile_manager = get_profile_manager()
        profile = await profile_manager.get_profile(profile_id)

        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")

        return ProfileResponse.from_profile(profile)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put(
    "/profiles/{profile_id}",
    response_model=ProfileResponse,
    operation_id="update_profile",
    summary="Update a profile.",
    description=(
        "Update a profile's data. A field that is sent is authoritative, including "
        "an explicit null, which clears it; a field that is omitted is left alone. "
        "browser_settings is merged over the stored settings."
    ),
)
async def update_profile(profile_id: str, request: ProfileUpdateRequest, http_request: Request):
    """Update a profile."""
    await require_permission(http_request, "profiles:write")
    await _enforce_profile_visibility(http_request, profile_id)
    try:
        profile_manager = get_profile_manager()

        # A field the client sent is authoritative, including an explicit null,
        # which clears it. A field it omitted is left untouched. Testing for
        # "is not None" instead would make clearing a proxy, a group or the
        # notes silently do nothing while still reporting success.
        # Read through model_dump: attribute access on the deprecated flattened
        # fields would raise DeprecationWarning from inside our own route.
        sent = request.model_dump(exclude_unset=True)

        updates: dict[str, Any] = {}
        if sent.get("name") is not None:
            updates["name"] = sent["name"]
        if "group" in sent:
            updates["group"] = sent["group"]
        if sent.get("status") is not None:
            updates["status"] = sent["status"]
        if "proxy_config" in sent:
            updates["proxy_config"] = sent["proxy_config"]
        if "notes" in sent:
            updates["notes"] = sent["notes"]

        # Browser settings arrive either as a nested object or as the deprecated
        # flattened browser_* fields. Both are collected here and merged over the
        # stored settings, so a client that sends only the fields it edits cannot
        # wipe the rest of the generated fingerprint.
        browser_updates: dict[str, Any] = {}
        if sent.get("browser_settings") is not None:
            browser_updates.update(sent["browser_settings"])
        for field, key in _FLATTENED_BROWSER_FIELDS.items():
            if sent.get(field) is not None:
                browser_updates[key] = sent[field]

        if browser_updates:
            current_profile = await profile_manager.get_profile(profile_id)
            if current_profile and current_profile.browser_settings:
                merged = current_profile.browser_settings.model_dump()
                merged.update(browser_updates)
                updates["browser_settings"] = merged
            else:
                updates["browser_settings"] = browser_updates

        # Apply the update
        updated_profile = await profile_manager.update_profile(profile_id, updates)

        if not updated_profile:
            raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")

        logger.info(f"Updated profile: {updated_profile.name} (ID: {profile_id})")
        await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.update', 'profile', profile_id, {'fields': sorted(sent.keys())})

        return ProfileResponse.from_profile(updated_profile)

    except HTTPException:
        raise
    except ValidationError as e:
        # browser_settings is a free-form dict on the way in, so bad values only
        # fail when it is turned into a BrowserSettings. That is the client's
        # mistake, not a server fault.
        logger.warning(f"Rejected invalid update for profile {profile_id}: {e}")
        raise ApiError(422, validation_message(e.errors()), details=e.errors()) from e
    except Exception as e:
        logger.error(f"Failed to update profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete(
    "/profiles/{profile_id}",
    response_model=ApiResponse[None],
    operation_id="delete_profile",
    summary="Delete a profile.",
    description="Delete a profile and all associated data.",
)
async def delete_profile(profile_id: str, http_request: Request):
    """Delete a profile."""
    await require_profile_delete(http_request)
    await _enforce_profile_visibility(http_request, profile_id)
    try:
        profile_manager = get_profile_manager()
        success = await profile_manager.delete_profile(profile_id, deleted_by=getattr(http_request.state, 'user_id', None))

        if not success:
            raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")

        logger.info(f"Deleted profile: ID {profile_id}")
        await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.delete', 'profile', profile_id)

        return ApiResponse(
            success=True, message=f"Profile {profile_id} deleted successfully", data=None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/profiles/{profile_id}/launch",
    response_model=ProfileLaunchResponse,
    operation_id="launch_profile",
    summary="Launch a browser.",
    description="Launch Camoufox with the profile's settings.",
)
async def launch_profile(profile_id: str, request: ProfileLaunchRequest, http_request: Request):
    """Launch a browser with a profile."""
    await require_profile_write(http_request)
    try:
        profile_manager = get_profile_manager()

        # Launch the browser
        additional_options = request.additional_options or {}
        forbidden = set(additional_options) - _ALLOWED_LAUNCH_OPTIONS
        if forbidden:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported launch option(s): {', '.join(sorted(forbidden))}",
            )
        browser_session = await profile_manager.launch_browser(
            profile_id,
            headless=request.headless,
            window_size=request.window_size,
            **additional_options,
        )

        logger.info(f"Launched browser for profile: {profile_id}")
        await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.launch', 'profile', profile_id, {'headless': request.headless})

        return ProfileLaunchResponse(
            profile_id=profile_id,
            browser_session_id=str(uuid.uuid4()),
            status=browser_session.get("status", "launched"),
            message=browser_session.get("message", "Browser launched successfully"),
            process_id=browser_session.get("process_id"),
            # Never reflect launch options: they include the proxy password and
            # a detailed fingerprint, neither of which a UI needs after launch.
            camoufox_options={
                "process_id": browser_session.get("process_id"),
                "status": browser_session.get("status"),
            },
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to launch browser for profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/profiles/{profile_id}/clone",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="clone_profile",
    summary="Clone a profile.",
    description="Create a copy of a profile with a new fingerprint.",
)
async def clone_profile(profile_id: str, request: ProfileCloneRequest, http_request: Request):
    """Clone a profile."""
    await require_profile_write(http_request)
    await _enforce_profile_visibility(http_request, profile_id)
    try:
        profile_manager = get_profile_manager()

        # Clone the profile
        cloned_profile = await profile_manager.clone_profile(
            profile_id,
            request.new_name,
            regenerate_fingerprint=request.regenerate_fingerprint,
            copy_browser_data=request.copy_browser_data,
        )
        if not cloned_profile:
            raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")

        logger.info(f"Cloned profile: {profile_id} -> {cloned_profile.id}")

        return ProfileResponse.from_profile(cloned_profile)

    except HTTPException:
        # Without this the 404 raised above is caught by the handler below and
        # served as a 500: the client's own bad id reported as a server fault,
        # and a page for whoever watches the error rate.
        raise
    except ValueError as e:
        # A missing source returns None above; a ValueError here is bad input
        # (pydantic's ValidationError subclasses it), not a missing profile.
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to clone profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/profiles/{profile_id}/check-proxy",
    response_model=ProxyCheckResponse,
    operation_id="check_profile_proxy",
    summary="Check a profile's proxy.",
    description=(
        "Reach the internet through the profile's proxy, report where it comes out, "
        "and list everything a page could notice between that and the profile's settings."
    ),
)
async def check_profile_proxy(profile_id: str, http_request: Request):
    """Check a saved profile's proxy against its settings."""
    await require_permission(http_request, "profiles:read")
    await _enforce_profile_visibility(http_request, profile_id)
    profile = await get_profile_manager().get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")

    result = await proxy_check.check(profile.proxy, profile.browser_settings)

    # Kept on the profile so the list can show this answer later. A check the
    # user asked for is the only thing that writes it — nothing here polls.
    #
    # Read back rather than writing the profile fetched above: the check just
    # spent seconds on the network, and anything edited in the meantime would be
    # reverted by writing a stale copy. If the proxy itself moved, the answer is
    # about a proxy this profile no longer has, so it is dropped rather than
    # shown — the same rule that clears the record on an edit.
    stored = proxy_check.record(result)
    manager = get_profile_manager()
    current = await manager.get_profile(profile_id)
    if current and current.proxy == profile.proxy:
        await manager.storage.set_proxy_check(profile_id, stored)
        return ProxyCheckResponse.from_result(result, checked_at=stored.checked_at)

    return ProxyCheckResponse.from_result(result)


@router.post(
    "/proxy/check",
    response_model=ProxyCheckResponse,
    operation_id="check_proxy",
    summary="Check an unsaved proxy.",
    description=(
        "The same check for a proxy that has not been saved yet, so a profile can be "
        "checked while it is still being filled in."
    ),
)
async def check_proxy(request: ProxyCheckRequest):
    """Check an unsaved proxy against unsaved settings."""
    try:
        proxy = ProxyConfig(**request.proxy_config) if request.proxy_config else None
        settings = BrowserSettings(**(request.browser_settings or {}))
    except ValidationError as e:
        raise ApiError(422, validation_message(e.errors()), details=e.errors()) from e

    result = await proxy_check.check(proxy, settings)
    return ProxyCheckResponse.from_result(result)


@router.get(
    "/profiles/{profile_id}/stats",
    response_model=ProfileStatsResponse,
    operation_id="get_profile_stats",
    summary="Get profile statistics.",
    description="Get usage statistics for a profile.",
)
async def get_profile_stats(profile_id: str, http_request: Request):
    """Get usage statistics for a profile."""
    await require_permission(http_request, "profiles:read")
    await _enforce_profile_visibility(http_request, profile_id)
    try:
        profile_manager = get_profile_manager()

        # Verify the profile exists
        profile = await profile_manager.get_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")

        # Fetch the statistics
        stats = await profile_manager.get_profile_stats(profile_id)

        return ProfileStatsResponse(
            profile_id=profile_id,
            total_sessions=stats.get("total_sessions", 0),
            total_duration_minutes=stats.get("total_duration_minutes", 0),
            last_session=stats.get("last_session"),
            success_rate=stats.get("success_rate", 0.0),
            actions=stats.get("actions", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get statistics for profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/profiles/{profile_id}/refresh-browser",
    response_model=ProfileResponse,
    operation_id="refresh_browser_version",
    summary="Refresh the pinned browser version.",
    description=(
        "Move the profile's pinned machine onto the installed browser version, "
        "keeping its hardware. A pin never ages on its own, and a browser several "
        "releases behind is itself unusual."
    ),
)
async def refresh_browser_version(profile_id: str, http_request: Request):
    """Update only the browser-version part of a profile's pinned fingerprint."""
    await require_profile_write(http_request)
    await _enforce_profile_visibility(http_request, profile_id)
    try:
        profile_manager = get_profile_manager()
        profile = await profile_manager.refresh_browser_version(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")
        return ProfileResponse.from_profile(profile)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to refresh the browser version for {profile_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/profiles/{profile_id}/reconcile-os",
    response_model=ProfileResponse,
    summary="Reconcile the OS setting with the pinned machine",
    description=(
        "A profile's OS setting and its pinned machine can disagree, because the pin is "
        "what a page sees and the setting is only a dropdown. Either put the setting back "
        "to what the machine reports (no fingerprint change), or pin a new machine for the "
        "setting — new screen, GPU, cores, fonts and noise seeds."
    ),
)
async def reconcile_profile_os(profile_id: str, request: ReconcileOsRequest, http_request: Request):
    """Bring a profile's OS setting and its pinned machine back into agreement."""
    await require_profile_write(http_request)
    await _enforce_profile_visibility(http_request, profile_id)
    try:
        profile = await get_profile_manager().reconcile_os(profile_id, request.keep_machine)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")
        return ProfileResponse.from_profile(profile)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to reconcile the OS for {profile_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/profiles/clear-geography",
    response_model=ClearGeographyResponse,
    summary="Clear stored timezone and coordinates",
    description=(
        "Unset the timezone and coordinates of the named profiles so both follow the "
        "proxy's exit address again, as a profile created today does. Takes a list "
        "because profiles created before that behaviour all carry a randomly chosen "
        "region. Languages and locale are left alone."
    ),
)
async def clear_profiles_geography(request: ClearGeographyRequest):
    """Make the named profiles derive their location from their proxy again."""
    try:
        result = await get_profile_manager().clear_geography(request.profile_ids)
        return ClearGeographyResponse(**result)
    except Exception as exc:
        logger.error(f"Failed to clear geography: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/profiles/{profile_id}/export",
    operation_id="export_profile",
    summary="Export a profile.",
    description=(
        "Download the profile and its browser data (cookies, storage, history) as a "
        "single archive. Contains the proxy password and live session cookies."
    ),
    response_class=FileResponse,
    dependencies=[Depends(require_workspace_admin)],
    responses={200: {"content": {"application/zip": {}}, "description": "The profile archive"}},
)
async def export_profile(profile_id: str, http_request: Request):
    """Stream a profile archive."""
    await _enforce_profile_visibility(http_request, profile_id)
    profile_manager = get_profile_manager()
    profile = await profile_manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")

    # Written to a temp file rather than memory: a warmed-up profile carries
    # tens of megabytes of storage and history.
    handle = tempfile.NamedTemporaryFile(suffix=".triada.zip", delete=False)
    handle.close()
    destination = Path(handle.name)

    try:
        await profile_manager.export_profile(profile_id, destination)
    except ValueError as exc:
        destination.unlink(missing_ok=True)
        # A running browser is a state conflict, not a bad request.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        destination.unlink(missing_ok=True)
        logger.error(f"Failed to export profile {profile_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", profile.name).strip("-") or profile_id
    return FileResponse(
        destination,
        media_type="application/zip",
        filename=f"{safe_name}.triada.zip",
        background=BackgroundTask(destination.unlink, missing_ok=True),
    )


@router.post(
    "/profiles/import",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="import_profile",
    summary="Import a profile.",
    description="Create a profile from an archive produced by the export endpoint.",
)
async def import_profile(
    file: UploadFile = File(...),
    name: str | None = None,
    form_name: str | None = Form(default=None, alias="name"),
    _: None = Depends(require_workspace_admin),
):
    """Restore a profile from an uploaded archive.

    ``name`` is accepted both as a query parameter and as a form field. Every
    other part of this request travels in the multipart body, so a client author
    reaches for the form field first — and used to get no error and no rename,
    because only the query parameter was read.
    """
    name = name or form_name
    profile_manager = get_profile_manager()

    handle = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    source = Path(handle.name)
    try:
        # Do not let an arbitrarily large compressed upload fill the system
        # temp volume before the archive extractor gets to apply its own limit.
        remaining = get_settings().max_import_bytes
        while chunk := file.file.read(min(1024 * 1024, remaining + 1)):
            remaining -= len(chunk)
            if remaining < 0:
                raise HTTPException(status_code=413, detail="Import archive is too large")
            handle.write(chunk)
        handle.close()
        profile = await profile_manager.import_profile(source, name=name)
        return ProfileResponse.from_profile(profile)
    except HTTPException:
        raise
    except (ValueError, zipfile.BadZipFile) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to import profile: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        handle.close()
        source.unlink(missing_ok=True)


@router.post(
    "/profiles/{profile_id}/reset-fingerprint",
    response_model=ProfileResponse,
    operation_id="reset_profile_fingerprint",
    summary="Reset the fingerprint.",
    description="Fully regenerate the browser fingerprint for a profile.",
)
async def reset_profile_fingerprint(profile_id: str, http_request: Request):
    """Reset and regenerate a profile's fingerprint."""
    await require_profile_write(http_request)
    await _enforce_profile_visibility(http_request, profile_id)
    try:
        profile_manager = get_profile_manager()

        # Verify the profile exists
        profile = await profile_manager.get_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")

        # Regenerate the fingerprint
        updated_profile = await profile_manager.rotate_profile_fingerprint(profile_id)
        if not updated_profile:
            raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")

        logger.info(f"Reset fingerprint for profile: {updated_profile.name} (ID: {profile_id})")

        return ProfileResponse.from_profile(updated_profile)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset fingerprint for profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/profiles/export/excel",
    operation_id="export_profiles_to_excel",
    summary="Export profiles to Excel.",
    description="Export all profiles to an Excel file for bulk editing.",
    response_class=Response,
    responses={
        200: {
            "content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}},
            "description": "The Excel workbook",
        }
    },
)
async def export_profiles_to_excel():
    """Export all profiles to an Excel file."""
    try:
        profile_manager = get_profile_manager()
        excel_manager = ExcelManager(profile_manager)

        # Export the profiles
        excel_data = await excel_manager.export_profiles_to_excel()

        logger.info("Profiles exported to Excel")

        return Response(
            content=excel_data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=camoufox_profiles.xlsx"},
        )

    except Exception as e:
        logger.error(f"Failed to export profiles to Excel: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/profiles/import/excel",
    response_model=ApiResponse[ExcelImportData],
    operation_id="import_profiles_from_excel",
    summary="Import profiles from Excel.",
    description="Import profiles from an Excel file, creating new ones.",
)
async def import_profiles_from_excel(file: UploadFile = File(...)):
    """Import profiles from an Excel file."""
    try:
        # Validate the file type
        if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
            raise HTTPException(
                status_code=400, detail="Only Excel files (.xlsx, .xls) are supported"
            )

        # Read the file
        excel_data = await file.read()

        profile_manager = get_profile_manager()
        excel_manager = ExcelManager(profile_manager)

        # Import the profiles
        result = await excel_manager.import_profiles_from_excel(excel_data)

        if result["success"]:
            logger.info(
                f"Import complete: created {result['created_count']}, updated {result['updated_count']}"
            )
        else:
            logger.warning(f"Import finished with {result['error_count']} errors")

        return ApiResponse(
            success=result["success"],
            message=result["summary"],
            data=ExcelImportData(
                created_count=result["created_count"],
                updated_count=result["updated_count"],
                error_count=result["error_count"],
                errors=result["errors"],
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to import profiles from Excel: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/profiles/{profile_id}/close",
    response_model=BrowserCloseResponse,
    operation_id="close_profile_browser",
    summary="Close a profile's browser.",
    description="Force-close the browser for a profile. Closing one that is not running is a no-op.",
)
async def close_profile_browser(profile_id: str, http_request: Request):
    """Close the browser for a profile."""
    await require_profile_write(http_request)
    await _enforce_profile_visibility(http_request, profile_id)
    try:
        profile_manager = get_profile_manager()
        result = await profile_manager.close_browser(profile_id)

        logger.info(f"Browser closed for profile: {profile_id}")
        await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.close', 'profile', profile_id)
        return result

    except Exception as e:
        logger.error(f"Failed to close browser for profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/browsers/sessions",
    operation_id="list_browser_sessions",
    summary="List detailed browser sessions.",
    description="List tracked browser sessions with PID, uptime and process health.",
)
async def list_browser_sessions(http_request: Request):
    await require_permission(http_request, "profiles:read")
    try:
        pm = get_profile_manager()
        await pm.reconcile_browser_sessions()
        sessions = await pm.get_active_browsers()
        visible: list[dict[str, Any]] = []
        for session in sessions:
            try:
                await _enforce_profile_visibility(http_request, session["profile_id"])
            except HTTPException:
                continue
            visible.append(session)
        return {"sessions": visible, "count": len(visible)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to list browser sessions")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/profiles/{profile_id}/restart",
    operation_id="restart_profile_browser",
    summary="Restart a profile browser.",
)
async def restart_profile_browser(profile_id: str, http_request: Request):
    await require_profile_write(http_request)
    await _enforce_profile_visibility(http_request, profile_id)
    try:
        result = await get_profile_manager().restart_browser(profile_id, headless=False)
        await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.restart', 'profile', profile_id)
        return result
    except Exception as exc:
        logger.exception("Failed to restart browser %s", profile_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/profiles/{profile_id}/force-close",
    operation_id="force_close_profile_browser",
    summary="Force-close a profile browser.",
)
async def force_close_profile_browser(profile_id: str, http_request: Request):
    await require_profile_write(http_request)
    await _enforce_profile_visibility(http_request, profile_id)
    try:
        result = await get_profile_manager().force_close_browser(profile_id)
        await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.force_close', 'profile', profile_id)
        return result
    except Exception as exc:
        logger.exception("Failed to force-close browser %s", profile_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/browsers/reconcile",
    operation_id="reconcile_browser_sessions",
    summary="Reconcile tracked browser sessions with OS processes.",
)
async def reconcile_browser_sessions(http_request: Request):
    await require_profile_write(http_request)
    try:
        result = await get_profile_manager().reconcile_browser_sessions()
        await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'browser.reconcile', 'browser', None, result)
        return result
    except Exception as exc:
        logger.exception("Failed to reconcile browser sessions")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/browsers/active",
    response_model=ActiveBrowsersResponse,
    operation_id="get_active_browsers",
    summary="List active browsers.",
    description="List all running browsers.",
)
async def get_active_browsers():
    """List active browsers."""
    try:
        profile_manager = get_profile_manager()
        active_browsers = await profile_manager.get_active_browsers()

        return {"active_browsers": active_browsers, "count": len(active_browsers)}

    except Exception as e:
        logger.error(f"Failed to list active browsers: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/browsers/close-all",
    response_model=BrowsersCloseAllResponse,
    operation_id="close_all_browsers",
    summary="Close all browsers.",
    description="Force-close all active browsers.",
)
async def close_all_browsers(http_request: Request):
    """Close all active browsers."""
    await require_profile_write(http_request)
    try:
        profile_manager = get_profile_manager()
        result = await profile_manager.close_all_browsers()

        logger.info(f"Closed {result['closed_count']} browsers")
        await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'browser.close_all', 'browser', None, {'closed_count': result.get('closed_count', 0)})
        return result

    except Exception as e:
        logger.error(f"Failed to close all browsers: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
