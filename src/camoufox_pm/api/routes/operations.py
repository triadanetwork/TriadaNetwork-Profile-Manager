from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from loguru import logger
from datetime import datetime, timezone, timedelta
import hashlib
import secrets
import sqlite3
from camoufox_pm.core import proxy_check
from camoufox_pm.core.models import BrowserSettings, ProxyConfig
from camoufox_pm.core.crypto import decrypt

from camoufox_pm.api.dependencies import get_storage_manager, require_permission, require_workspace_admin, require_assignment_write
from camoufox_pm.api.models.operations import (
    BulkProfileOperationsRequest,
    MemberResponse,
    ProfileOperationsUpdateRequest,
    ProfileOperationsResponse,
    ProxyPoolCreateRequest,
    ProxyPoolResponse,
    TagCreateRequest,
    TagResponse,
    WorkspaceResponse, TeamDashboardResponse, TeamSummaryResponse,
    WorkspaceUpdateRequest, MemberRoleUpdateRequest, InviteCreateRequest, InviteResponse,
    ProxyInventoryCreateRequest, ProxyInventoryUpdateRequest, ProxyAssignmentRequest,
    ProxyInventoryListResponse, ProxyInventoryResponse, ProxyHealthResponse, PoolAssignNextRequest, ProxyBulkImportRequest,
)

router = APIRouter()

async def require_proxy_read(request: Request):
    await require_permission(request, 'proxies:read')

async def require_proxy_write(request: Request):
    await require_permission(request, 'proxies:write')

async def require_profile_write(request: Request):
    await require_permission(request, 'profiles:write')

async def require_permission_audit(request: Request):
    await require_permission(request, 'audit:read')


@router.get('/workspace', response_model=WorkspaceResponse)
async def workspace(request: Request):
    row = await get_storage_manager().db.get_workspace()
    row['current_role'] = getattr(request.state, 'workspace_role', None)
    return WorkspaceResponse(**row)

@router.get('/team/dashboard', response_model=TeamDashboardResponse)
async def team_dashboard(request: Request):
    await require_permission(request, 'profiles:read')
    storage = get_storage_manager()
    workspace_row = await storage.db.get_workspace()
    workspace_row['current_role'] = getattr(request.state, 'workspace_role', None)
    summary = await storage.db.get_team_summary()
    invites = await storage.db.list_pending_invites()
    recent = await storage.db.list_audit(limit=10) if getattr(request.state, 'workspace_role', None) in {'owner','admin','team_lead'} else []
    return TeamDashboardResponse(
        workspace=WorkspaceResponse(**workspace_row),
        summary=TeamSummaryResponse(**summary),
        pending_invites=len([x for x in invites if not x.get('accepted_at')]),
        recent_activity=recent,
    )

@router.patch('/workspace', response_model=WorkspaceResponse, dependencies=[Depends(require_workspace_admin)])
async def update_workspace(request: WorkspaceUpdateRequest):
    data = request.model_dump(exclude_none=True)
    if data.get('workspace_type') not in (None, 'personal', 'team'):
        raise HTTPException(status_code=400, detail='workspace_type must be personal or team')
    if data.get('workspace_type') == 'team' and await get_storage_manager().count_users() == 0:
        raise HTTPException(status_code=400, detail='Create an owner account before enabling team mode')
    return WorkspaceResponse(**await get_storage_manager().db.update_workspace(data))

@router.get('/members', response_model=list[MemberResponse])
async def members(request: Request):
    await require_permission(request, 'profiles:read')
    return [MemberResponse(**row) for row in await get_storage_manager().db.list_workspace_members()]

@router.post('/members/invites', response_model=InviteResponse, status_code=201)
async def create_invite(payload: InviteCreateRequest, request: Request):
    await require_permission(request, 'team:write')
    storage = get_storage_manager()
    existing = await storage.db.get_user_by_username(payload.username)
    if existing is not None:
        raise HTTPException(status_code=409, detail='Username already exists')
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(hours=payload.expires_hours)
    try:
        row = await storage.db.create_workspace_invite(payload.username, payload.role, getattr(request.state, 'user_id', None), token_hash, expires)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail='An invite for this username already exists') from exc
    await storage.db.log_audit(getattr(request.state, 'user_id', None), 'team.invite.create', 'invite', row['id'], {'username': payload.username, 'role': payload.role})
    return InviteResponse(**row, token=token)

@router.get('/invites', response_model=list[dict])
async def invites(request: Request):
    await require_permission(request, 'team:write')
    return await get_storage_manager().db.list_pending_invites()

@router.patch('/members/{username}', response_model=MemberResponse)
async def update_member(username: str, payload: MemberRoleUpdateRequest, request: Request):
    await require_permission(request, 'team:write')
    current = getattr(request.state, 'username', None)
    if current and current.casefold() == username.casefold() and payload.role not in {'owner', 'admin'}:
        raise HTTPException(status_code=400, detail='You cannot demote your own workspace role')
    try:
        changed = await get_storage_manager().db.set_workspace_member_role(username, payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not changed:
        raise HTTPException(status_code=404, detail='Member not found')
    await get_storage_manager().db.log_audit(getattr(request.state, 'user_id', None), 'team.member.role_update', 'member', username, {'role': payload.role})
    row = next(x for x in await get_storage_manager().db.list_workspace_members() if x['username'].casefold() == username.casefold())
    return MemberResponse(**row)

@router.delete('/members/{username}', response_model=dict)
async def remove_member(username: str, request: Request):
    await require_permission(request, 'team:write')
    current = getattr(request.state, 'username', None)
    if current and current.casefold() == username.casefold():
        raise HTTPException(status_code=400, detail='Use workspace transfer before removing yourself')
    try:
        removed = await get_storage_manager().db.remove_workspace_member(username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=404, detail='Member not found')
    await get_storage_manager().db.log_audit(getattr(request.state, 'user_id', None), 'team.member.remove', 'member', username)
    return {'removed': True}

@router.get('/tags', response_model=list[TagResponse])
async def tags(request: Request):
    await require_permission(request, 'profiles:read')
    return [TagResponse(**row) for row in await get_storage_manager().db.list_tags()]

@router.post('/tags', response_model=TagResponse, status_code=201, dependencies=[Depends(require_workspace_admin)])
async def create_tag(request: TagCreateRequest):
    try:
        return TagResponse(**await get_storage_manager().db.create_tag(request.name))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.get('/proxy-pools', response_model=list[ProxyPoolResponse])
async def proxy_pools(request: Request):
    await require_proxy_read(request)
    return [ProxyPoolResponse(**row) for row in await get_storage_manager().db.list_proxy_pools()]

@router.post('/proxy-pools', response_model=ProxyPoolResponse, status_code=201, dependencies=[Depends(require_proxy_write)])
async def create_proxy_pool(request: ProxyPoolCreateRequest):
    try:
        return ProxyPoolResponse(**await get_storage_manager().db.create_proxy_pool(request.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get('/audit/actions', response_model=list[str], dependencies=[Depends(require_permission_audit)])
async def audit_actions():
    return await get_storage_manager().db.list_audit_actions()

@router.get('/audit', response_model=list[dict], dependencies=[Depends(require_permission_audit)])
async def audit(limit: int = 100, action: str | None = None, actor_user_id: str | None = None):
    return await get_storage_manager().db.list_audit(limit=limit, action=action, actor_user_id=actor_user_id)
@router.get('/profiles/{profile_id}/operations', response_model=ProfileOperationsResponse)
async def profile_operations(profile_id: str, http_request: Request):
    storage = get_storage_manager()
    await require_permission(http_request, 'profiles:read')
    row = await storage.get_profile(profile_id)
    if not row:
        raise HTTPException(status_code=404, detail='Profile not found')
    role = getattr(http_request.state, 'workspace_role', None)
    if role == 'buyer':
        current_user = getattr(http_request.state, 'user_id', None)
        preview = await storage.db.get_profile_operations(profile_id)
        if preview.get('owner_id') != current_user and preview.get('assigned_user_id') != current_user:
            raise HTTPException(status_code=403, detail='Profile is outside your workspace scope')
    try:
        data = await storage.db.get_profile_operations(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProfileOperationsResponse(**data)

@router.put('/profiles/{profile_id}/operations', response_model=ProfileOperationsResponse)
async def update_profile_operations(profile_id: str, request: ProfileOperationsUpdateRequest, http_request: Request):
    storage = get_storage_manager()
    await require_permission(http_request, 'profiles:write')
    data = request.model_dump()
    if any(data.get(k, {}).get('action') != 'unchanged' for k in ('owner', 'assigned_user')):
        await require_assignment_write(http_request)
    if not await storage.get_profile(profile_id):
        raise HTTPException(status_code=404, detail='Profile not found')
    if getattr(http_request.state, 'workspace_role', None) == 'buyer':
        current_user = getattr(http_request.state, 'user_id', None)
        current = await storage.db.get_profile_operations(profile_id)
        if current.get('owner_id') != current_user and current.get('assigned_user_id') != current_user:
            raise HTTPException(status_code=403, detail='Profile is outside your workspace scope')
    try:
        result = await storage.db.update_profile_operations(profile_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await storage.db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.operations.update', 'profile', profile_id, data)
    return ProfileOperationsResponse(**result)

@router.post('/profiles/bulk', response_model=dict)
async def bulk_profile_operations(request: BulkProfileOperationsRequest, http_request: Request):
    storage = get_storage_manager()
    await require_permission(http_request, 'profiles:write')
    updates = request.model_dump()
    if any(updates.get(k, {}).get('action') != 'unchanged' for k in ('owner', 'assigned_user')):
        await require_assignment_write(http_request)
    profile_ids = updates.pop('profile_ids')
    role = getattr(http_request.state, 'workspace_role', None)
    if role == 'buyer':
        current_user = getattr(http_request.state, 'user_id', None)
        visible = []
        for pid in profile_ids:
            item = await storage.db.get_profile_operations(pid)
            if item.get('owner_id') == current_user or item.get('assigned_user_id') == current_user:
                visible.append(pid)
        if len(visible) != len(profile_ids):
            raise HTTPException(status_code=403, detail='Bulk operation includes profiles outside your workspace scope')
    try:
        count = await storage.db.bulk_update_profile_operations(profile_ids, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await storage.db.log_audit(getattr(http_request.state, 'user_id', None), 'profile.operations.bulk_update', 'profile', None, {'profile_ids': profile_ids, 'updates': updates})
    logger.info('Bulk-updated profile operations: {} profiles', count)
    return {'updated': count}



@router.post('/proxies/bulk-import/file', response_model=dict, dependencies=[Depends(require_proxy_write)])
async def bulk_import_proxy_file(file: UploadFile = File(...), pool_id: str | None = None, provider: str | None = None, country: str | None = None, proxy_type: str = 'http', http_request: Request = None):
    import csv, io
    from urllib.parse import urlparse
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='Proxy import file is too large (5 MB max)')
    text = raw.decode('utf-8-sig', errors='strict')
    rows=[]
    reader=csv.DictReader(io.StringIO(text)) if text.splitlines() and any(x.lower() in text.splitlines()[0].lower() for x in ('server','proxy_type','host','port')) else None
    def parse_line(line: str):
        line=line.strip()
        if not line or line.startswith('#'): return None
        parsed=urlparse(line if '://' in line else 'http://' + line)
        if not parsed.hostname or not parsed.port: raise ValueError('Expected host:port or scheme://user:pass@host:port')
        typ=(parsed.scheme or proxy_type).lower()
        if typ not in {'http','https','socks4','socks5'}: raise ValueError(f'Unsupported protocol: {typ}')
        return {'proxy_type':typ,'server':f'{parsed.hostname}:{parsed.port}','username':parsed.username,'password':parsed.password,'provider':provider,'country':country,'pool_id':pool_id}
    if reader:
        for idx,row in enumerate(reader,1):
            try:
                server=(row.get('server') or row.get('host') or '').strip()
                port=(row.get('port') or '').strip()
                line=server + (f':{port}' if port and ':' not in server else '')
                if row.get('proxy_type'): line=row['proxy_type']+'://'+line
                if row.get('username'):
                    auth=row['username'] + ((':'+row.get('password')) if row.get('password') else '') + '@'
                    line=(row.get('proxy_type') or proxy_type)+'://'+auth+line.split('://',1)[-1]
                item=parse_line(line)
                for key in ('provider','country','pool_id'):
                    if row.get(key): item[key]=row[key]
                item['name']=row.get('name') or ''
                rows.append(item)
            except Exception as exc:
                rows.append({'_error': {'line':idx,'error':str(exc)}})
    else:
        for idx,line in enumerate(text.splitlines(),1):
            try:
                item=parse_line(line)
                if item: rows.append(item)
            except Exception as exc:
                rows.append({'_error': {'line':idx,'error':str(exc)}})
    errors=[r['_error'] for r in rows if '_error' in r]
    valid=[r for r in rows if '_error' not in r]
    result=await get_storage_manager().db.bulk_create_proxy_inventory(valid)
    result['failed'] = errors + result.get('failed', [])
    await get_storage_manager().db.log_audit(getattr(http_request.state,'user_id',None), 'proxy.bulk_import', 'proxy', None, {'created': result['created'], 'failed': len(result['failed'])})
    return result

@router.get('/proxies', response_model=ProxyInventoryListResponse, dependencies=[Depends(require_proxy_read)])
async def list_proxies(pool_id: str | None = None, status: str | None = None):
    rows = await get_storage_manager().db.list_proxy_inventory(pool_id=pool_id, status=status)
    return ProxyInventoryListResponse(proxies=[ProxyInventoryResponse(**row) for row in rows], total=len(rows))

@router.post('/proxies', response_model=ProxyInventoryResponse, status_code=201, dependencies=[Depends(require_proxy_write)])
async def create_proxy(request: ProxyInventoryCreateRequest, http_request: Request):
    try:
        row = await get_storage_manager().db.create_proxy_inventory(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'proxy.create', 'proxy', row['id'], {'name': row['name'], 'pool_id': row.get('pool_id')})
    return ProxyInventoryResponse(**row)

@router.get('/proxies/{proxy_id}', response_model=ProxyInventoryResponse)
async def get_proxy(proxy_id: str, http_request: Request):
    await require_proxy_read(http_request)
    row = await get_storage_manager().db.get_proxy_inventory(proxy_id)
    if not row: raise HTTPException(status_code=404, detail='Proxy not found')
    return ProxyInventoryResponse(**row)

@router.patch('/proxies/{proxy_id}', response_model=ProxyInventoryResponse, dependencies=[Depends(require_proxy_write)])
async def update_proxy(proxy_id: str, request: ProxyInventoryUpdateRequest, http_request: Request):
    try:
        row = await get_storage_manager().db.update_proxy_inventory(proxy_id, request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_data = request.model_dump(exclude_unset=True)
    audit_data.pop('username', None)
    audit_data.pop('password', None)
    await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'proxy.update', 'proxy', proxy_id, audit_data)
    return ProxyInventoryResponse(**row)

@router.delete('/proxies/{proxy_id}', dependencies=[Depends(require_proxy_write)])
async def delete_proxy(proxy_id: str, http_request: Request):
    try: deleted = await get_storage_manager().db.delete_proxy_inventory(proxy_id)
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted: raise HTTPException(status_code=404, detail='Proxy not found')
    await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'proxy.delete', 'proxy', proxy_id)
    return {'deleted': True}

@router.post('/proxies/{proxy_id}/check', response_model=ProxyHealthResponse, dependencies=[Depends(require_proxy_write)])
async def check_proxy(proxy_id: str, http_request: Request):
    row = await get_storage_manager().db._get_proxy_inventory_secret(proxy_id)
    if not row: raise HTTPException(status_code=404, detail='Proxy not found')
    config = ProxyConfig(type=row['proxy_type'], server=row['server'], username=decrypt(row['username']) if row.get('username') else None, password=decrypt(row['password']) if row.get('password') else None, country=row.get('country'))
    result = await proxy_check.check(config, BrowserSettings())
    checked = {
      'reachable': result.reachable, 'latency_ms': result.latency_ms, 'error': result.error,
      'exit_ip': result.location.ip if result.location else None, 'exit_country': result.location.country if result.location else None,
      'exit_timezone': result.location.timezone if result.location else None, 'checked_at': datetime.now(timezone.utc).isoformat(),
      'findings': [{'level': f.level, 'field': f.field, 'message': f.message} for f in result.findings],
    }
    updated = await get_storage_manager().db.set_proxy_health(proxy_id, checked)
    await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'proxy.health_check', 'proxy', proxy_id, {'reachable': result.reachable, 'latency_ms': result.latency_ms})
    return ProxyHealthResponse(proxy=ProxyInventoryResponse(**updated), **{k: checked[k] for k in ('reachable','latency_ms','error','exit_ip','exit_country','exit_timezone','findings')})

@router.post('/proxies/{proxy_id}/assign', response_model=ProxyInventoryResponse, dependencies=[Depends(require_profile_write)])
async def assign_proxy(proxy_id: str, request: ProxyAssignmentRequest, http_request: Request):
    if getattr(http_request.state, 'workspace_role', None) == 'buyer':
        current = await get_storage_manager().db.get_profile_operations(request.profile_id)
        uid = getattr(http_request.state, 'user_id', None)
        if current.get('owner_id') != uid and current.get('assigned_user_id') != uid:
            raise HTTPException(status_code=403, detail='Profile is outside your workspace scope')
    try: row = await get_storage_manager().db.assign_proxy_to_profile(proxy_id, request.profile_id)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'proxy.assign', 'proxy', proxy_id, {'profile_id': request.profile_id})
    return ProxyInventoryResponse(**row)

@router.post('/proxies/{proxy_id}/unassign', response_model=ProxyInventoryResponse, dependencies=[Depends(require_profile_write)])
async def unassign_proxy(proxy_id: str, http_request: Request):
    try: row = await get_storage_manager().db.unassign_proxy_from_profile(proxy_id)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'proxy.unassign', 'proxy', proxy_id)
    return ProxyInventoryResponse(**row)

@router.post('/proxy-pools/{pool_id}/assign-next', response_model=ProxyInventoryResponse, dependencies=[Depends(require_profile_write)])
async def assign_next_from_pool(pool_id: str, request: PoolAssignNextRequest, http_request: Request):
    if getattr(http_request.state, 'workspace_role', None) == 'buyer':
        current = await get_storage_manager().db.get_profile_operations(request.profile_id)
        uid = getattr(http_request.state, 'user_id', None)
        if current.get('owner_id') != uid and current.get('assigned_user_id') != uid:
            raise HTTPException(status_code=403, detail='Profile is outside your workspace scope')
    try:
        row = await get_storage_manager().db.assign_next_proxy_from_pool(pool_id, request.profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await get_storage_manager().db.log_audit(getattr(http_request.state, 'user_id', None), 'proxy.pool_assign_next', 'proxy_pool', pool_id, {'profile_id': request.profile_id, 'proxy_id': row['id']})
    return ProxyInventoryResponse(**row)
