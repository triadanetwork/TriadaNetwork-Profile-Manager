"""Cloud control-plane routes. Sensitive browser state remains local."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from camoufox_pm.api.dependencies import get_storage_manager, require_permission
from camoufox_pm.api.models.cloud import (ApiKeyCreateRequest, ApiKeyResponse, CloudWorkspace, DeviceRegisterRequest, DeviceResponse, SyncPullResponse, SyncPushRequest, SyncPushResponse, WorkspaceCreateRequest)

router=APIRouter()
ALLOWED_SCOPES={"workspace:read","profiles:read","sync:read","sync:write","devices:read","devices:write","keys:read","keys:write"}

def _user_id(request: Request) -> str:
    uid=getattr(request.state,'user_id',None)
    if not uid: raise HTTPException(status_code=401, detail='Human session required for cloud control plane')
    return uid

def _workspace_id(request: Request) -> str:
    return getattr(request.state,'cloud_workspace_id',None) or "ws-personal-default"

async def _require_cloud_scope(request: Request, scope: str) -> None:
    if getattr(request.state,'auth_kind',None)=='api_key':
        scopes=getattr(request.state,'api_key_scopes',set())
        if scope not in scopes and '*' not in scopes: raise HTTPException(status_code=403, detail=f'API key scope required: {scope}')
        return
    if scope == 'workspace:write':
        role=getattr(request.state,'workspace_role',None)
        if role != 'owner': raise HTTPException(status_code=403, detail='Workspace owner role required')
        return
    if scope in {'keys:write','devices:write','sync:write'}:
        role=getattr(request.state,'workspace_role',None)
        if role not in {'owner','admin'}: raise HTTPException(status_code=403, detail='Workspace admin role required')

@router.get('/cloud/me')
async def me(request: Request):
    uid=_user_id(request)
    storage=get_storage_manager()
    return {'user_id':uid,'username':getattr(request.state,'username',None),'accounts':await storage.list_cloud_accounts(uid),'workspaces':await storage.list_cloud_workspaces(uid)}

@router.get('/cloud/workspaces', response_model=list[CloudWorkspace])
async def workspaces(request: Request):
    await _require_cloud_scope(request, 'workspace:read')
    return [CloudWorkspace(**x) for x in await get_storage_manager().list_cloud_workspaces(_user_id(request))]

@router.post('/cloud/workspaces', response_model=CloudWorkspace, status_code=201)
async def create_workspace(body: WorkspaceCreateRequest, request: Request):
    await _require_cloud_scope(request, 'workspace:write')
    uid=_user_id(request)
    row=await get_storage_manager().create_cloud_workspace(uid, body.name, body.workspace_type)
    return CloudWorkspace(**row)

@router.post('/cloud/workspaces/{workspace_id}/select')
async def select_workspace(workspace_id: str, request: Request, response: Response):
    uid=_user_id(request)
    allowed={x['id'] for x in await get_storage_manager().list_cloud_workspaces(uid)}
    if workspace_id not in allowed: raise HTTPException(status_code=403, detail='Workspace access denied')
    request.state.cloud_workspace_id=workspace_id
    response.set_cookie('triada_workspace', workspace_id, max_age=60*60*24*90, path='/', httponly=True, samesite='lax', secure=request.url.scheme=='https')
    return {'workspace_id':workspace_id}

@router.get('/cloud/api-keys', response_model=list[ApiKeyResponse])
async def api_keys(request: Request):
    await _require_cloud_scope(request,'keys:read')
    workspace_id=_workspace_id(request)
    return [ApiKeyResponse(**x) for x in await get_storage_manager().list_workspace_api_keys(workspace_id)]

@router.post('/cloud/api-keys', response_model=ApiKeyResponse, status_code=201)
async def create_api_key(body: ApiKeyCreateRequest, request: Request):
    await _require_cloud_scope(request,'keys:write')
    bad=set(body.scopes)-ALLOWED_SCOPES
    if bad: raise HTTPException(status_code=400, detail=f'Unsupported scopes: {sorted(bad)}')
    secret='triada_'+secrets.token_urlsafe(32)
    prefix=secret[:16]
    key_hash=hashlib.sha256(secret.encode()).hexdigest()
    expires=(datetime.now(timezone.utc)+timedelta(days=body.expires_days)).isoformat() if body.expires_days else None
    row=await get_storage_manager().create_workspace_api_key(_workspace_id(request),body.name,key_hash,prefix,body.scopes,getattr(request.state,'user_id',None),expires)
    row['secret']=secret
    await get_storage_manager().db.log_audit(getattr(request.state,'user_id',None),'cloud.api_key.create','api_key',row['id'],{'name':body.name,'scopes':body.scopes})
    return ApiKeyResponse(**row)

@router.delete('/cloud/api-keys/{key_id}')
async def revoke_api_key(key_id: str, request: Request):
    await _require_cloud_scope(request,'keys:write')
    ok=await get_storage_manager().revoke_workspace_api_key(_workspace_id(request),key_id)
    if not ok: raise HTTPException(status_code=404, detail='API key not found')
    await get_storage_manager().db.log_audit(getattr(request.state,'user_id',None),'cloud.api_key.revoke','api_key',key_id)
    return {'revoked':True}

@router.get('/cloud/devices', response_model=list[DeviceResponse])
async def devices(request: Request):
    await _require_cloud_scope(request,'devices:read')
    accounts=await get_storage_manager().list_cloud_accounts(_user_id(request))
    if not accounts: return []
    return [DeviceResponse(**x) for x in await get_storage_manager().list_devices(accounts[0]['id'])]

@router.post('/cloud/devices', response_model=DeviceResponse, status_code=201)
async def register_device(body: DeviceRegisterRequest, request: Request):
    await _require_cloud_scope(request,'devices:write')
    uid=_user_id(request); accounts=await get_storage_manager().list_cloud_accounts(uid)
    if not accounts: raise HTTPException(status_code=400, detail='Account not initialized')
    token_hash=hashlib.sha256(body.device_token.encode()).hexdigest()
    return DeviceResponse(**await get_storage_manager().register_device(accounts[0]['id'],uid,body.name,body.platform,body.app_version,token_hash))

@router.get('/cloud/sync', response_model=SyncPullResponse)
async def sync_pull(request: Request, after_revision: int = 0, limit: int = 500):
    await _require_cloud_scope(request,'sync:read')
    workspace_id=_workspace_id(request)
    return SyncPullResponse(**await get_storage_manager().list_cloud_sync_records(workspace_id,max(0,after_revision),min(500,limit)))

@router.post('/cloud/sync', response_model=SyncPushResponse)
async def sync_push(body: SyncPushRequest, request: Request):
    await _require_cloud_scope(request,'sync:write')
    workspace_id=_workspace_id(request)
    if body.entity_type=='profile':
        # Reject attempts to push local-only secrets/state into the control plane.
        forbidden={'browser_settings','fingerprint','proxy_config','storage_path','notes'}
        if forbidden.intersection(body.payload): raise HTTPException(status_code=400, detail='Payload contains local-only browser state')
    try:
        row=await get_storage_manager().upsert_cloud_sync_record(workspace_id,body.entity_type,body.entity_id,body.payload,body.expected_revision)
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
    await get_storage_manager().db.log_audit(getattr(request.state,'user_id',None),'cloud.sync.push',body.entity_type,body.entity_id,{'revision':row['revision']})
    return SyncPushResponse(**{k:row[k] for k in ('workspace_id','entity_type','entity_id','revision')})

@router.post('/cloud/sync/profiles')
async def sync_profiles(request: Request):
    await _require_cloud_scope(request,'sync:write')
    result=await get_storage_manager().sync_workspace_profiles(_workspace_id(request))
    return result
