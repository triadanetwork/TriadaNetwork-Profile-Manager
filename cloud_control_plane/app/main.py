from contextlib import asynccontextmanager
from datetime import timedelta
from hashlib import sha256
import secrets
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from .config import settings
from .db import engine, get_db
from .models import Base, Account, AccountMember, ApiKey, AuditEvent, Device, RefreshToken, SyncRecord, User, Workspace, WorkspaceCursor, WorkspaceMember
from .schemas import ApiKeyCreate, DeviceCreate, LoginRequest, RefreshRequest, RegisterRequest, SyncPush, TokenResponse, WorkspaceCreate
from .security import CLOUD_SCOPES, hash_token, issue_access, now, ph, principal, require, workspace_membership, decode_access
from .config import settings
from .health import router as health_router
from .observability import RequestContextMiddleware, configure_logging
from .ratelimit import RateLimiter
from redis.asyncio import Redis
from .metrics import router as metrics_router
from .telemetry import configure_optional_telemetry

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    redis = Redis.from_url(settings().redis_url, decode_responses=True)
    app.state.redis = redis
    app.state.rate_limiter = RateLimiter(redis, settings().rate_limit_per_minute, 60)
    yield
    await redis.aclose()
    await engine.dispose()

app=FastAPI(title="Triada Network Cloud Control Plane",version="1.2.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings().cors_origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.add_middleware(RequestContextMiddleware)
app.include_router(health_router)
app.include_router(metrics_router)
configure_optional_telemetry(app)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    try:
        if path.startswith("/v1/auth/"):
            await request.app.state.rate_limiter.check(request, "auth")
        elif path.startswith("/v1/"):
            await request.app.state.rate_limiter.check(request, "api")
    except Exception as exc:
        from fastapi.responses import JSONResponse
        from .observability import log_event
        import logging
        log_event(logging.ERROR, "rate_limit.unavailable", request_id=getattr(request.state, "request_id", None), error=str(exc))
        return JSONResponse(status_code=503, content={"detail": "Rate limiting service unavailable"})
    return await call_next(request)

async def log(db:AsyncSession, ws:str, actor:str|None, action:str, entity_type:str, entity_id:str|None, metadata:dict|None=None):
    db.add(AuditEvent(workspace_id=ws,actor_user_id=actor,action=action,entity_type=entity_type,entity_id=entity_id,metadata_json=metadata or {})); await db.flush()

@app.get("/health")
async def legacy_health():
    return {"status":"healthy","service":"triada-cloud","version":"1.2.0"}

@app.post("/v1/auth/register",response_model=TokenResponse,status_code=201)
async def register(body:RegisterRequest,db:AsyncSession=Depends(get_db)):
    if (await db.execute(select(User).where(User.username==body.username))).scalar_one_or_none(): raise HTTPException(409,"Username already exists")
    user=User(username=body.username,password_hash=ph.hash(body.password)); acct=Account(name=body.account_name); ws=Workspace(account_id=acct.id if acct.id else "",name=body.account_name,workspace_type="personal")
    db.add_all([user,acct]); await db.flush(); ws.account_id=acct.id; db.add(ws); await db.flush()
    db.add_all([AccountMember(account_id=acct.id,user_id=user.id,role="owner"),WorkspaceMember(workspace_id=ws.id,user_id=user.id,role="owner"),WorkspaceCursor(workspace_id=ws.id,revision=0)]); await db.commit()
    refresh=secrets.token_urlsafe(48); db.add(RefreshToken(token_hash=hash_token(refresh),user_id=user.id,workspace_id=ws.id,expires_at=now()+timedelta(days=settings().refresh_ttl_days))); await db.commit()
    return TokenResponse(access_token=issue_access(user.id,ws.id,"owner"),refresh_token=refresh,expires_in=settings().jwt_ttl_minutes*60)

@app.post("/v1/auth/login",response_model=TokenResponse)
async def login(body:LoginRequest,db:AsyncSession=Depends(get_db)):
    user=(await db.execute(select(User).where(User.username==body.username))).scalar_one_or_none()
    if not user: raise HTTPException(401,"Invalid credentials")
    try: ph.verify(user.password_hash,body.password)
    except Exception as exc: raise HTTPException(401,"Invalid credentials") from exc
    member=await workspace_membership(db,user.id,body.workspace_id)
    if not member: raise HTTPException(403,"Workspace access denied")
    refresh=secrets.token_urlsafe(48); db.add(RefreshToken(token_hash=hash_token(refresh),user_id=user.id,workspace_id=body.workspace_id,expires_at=now()+timedelta(days=settings().refresh_ttl_days))); await db.commit()
    return TokenResponse(access_token=issue_access(user.id,body.workspace_id,member.role),refresh_token=refresh,expires_in=settings().jwt_ttl_minutes*60)

@app.post("/v1/auth/refresh",response_model=TokenResponse)
async def refresh(body:RefreshRequest,db:AsyncSession=Depends(get_db)):
    row=(await db.execute(select(RefreshToken).where(RefreshToken.token_hash==hash_token(body.refresh_token)))).scalar_one_or_none()
    if not row or row.revoked_at or row.expires_at<=now(): raise HTTPException(401,"Invalid refresh token")
    member=(await db.execute(select(WorkspaceMember).where(WorkspaceMember.user_id==row.user_id,WorkspaceMember.workspace_id==row.workspace_id))).scalar_one_or_none()
    if not member: raise HTTPException(403,"No workspace membership")
    row.revoked_at=now(); new=secrets.token_urlsafe(48); db.add(RefreshToken(token_hash=hash_token(new),user_id=row.user_id,workspace_id=row.workspace_id,expires_at=now()+timedelta(days=settings().refresh_ttl_days))); await db.commit()
    return TokenResponse(access_token=issue_access(row.user_id,member.workspace_id,member.role),refresh_token=new,expires_in=settings().jwt_ttl_minutes*60)

@app.get("/v1/me")
async def me(request:Request,db:AsyncSession=Depends(get_db)):
    p=await require(request,db)
    user=(await db.execute(select(User).where(User.id==p["user_id"]))).scalar_one()
    memberships=(await db.execute(select(WorkspaceMember,Workspace).join(Workspace,Workspace.id==WorkspaceMember.workspace_id).where(WorkspaceMember.user_id==user.id))).all()
    return {"user":{"id":user.id,"username":user.username},"workspaces":[{"id":ws.id,"name":ws.name,"workspace_type":ws.workspace_type,"role":m.role,"account_id":ws.account_id} for m,ws in memberships]}

@app.post("/v1/workspaces",status_code=201)
async def create_workspace(body:WorkspaceCreate,request:Request,db:AsyncSession=Depends(get_db)):
    p=await require(request,db,"workspace:write")
    ws=Workspace(account_id="",name=body.name.strip(),workspace_type=body.workspace_type); db.add(ws); await db.flush()
    member=await db.get(WorkspaceMember,(p["workspace_id"],p["user_id"]))
    if not member: raise HTTPException(403,"Workspace membership required")
    account=(await db.execute(select(AccountMember.account_id).where(AccountMember.user_id==p["user_id"]))).scalars().first(); ws.account_id=account
    db.add_all([WorkspaceMember(workspace_id=ws.id,user_id=p["user_id"],role="owner"),WorkspaceCursor(workspace_id=ws.id,revision=0)]); await db.commit(); await log(db,ws.id,p["user_id"],"workspace.create","workspace",ws.id); await db.commit()
    return {"id":ws.id,"name":ws.name,"workspace_type":ws.workspace_type,"role":"owner","account_id":ws.account_id}

@app.post("/v1/api-keys",status_code=201)
async def create_key(body:ApiKeyCreate,request:Request,db:AsyncSession=Depends(get_db)):
    p=await require(request,db,"keys:write")
    bad=set(body.scopes)-CLOUD_SCOPES
    if bad: raise HTTPException(400,f"Unsupported scopes: {sorted(bad)}")
    secret="tnk_"+secrets.token_urlsafe(36); row=ApiKey(workspace_id=p["workspace_id"],name=body.name,key_hash=hash_token(secret),prefix=secret[:12],scopes=sorted(set(body.scopes)),created_by=p["user_id"])
    if body.expires_days: row.expires_at=now()+timedelta(days=body.expires_days)
    db.add(row); await db.flush(); await log(db,row.workspace_id,p["user_id"],"api_key.create","api_key",row.id,{"scopes":row.scopes}); await db.commit()
    return {"id":row.id,"workspace_id":row.workspace_id,"name":row.name,"prefix":row.prefix,"scopes":row.scopes,"created_at":row.created_at,"expires_at":row.expires_at,"secret":secret}

@app.get("/v1/api-keys")
async def list_keys(request:Request,db:AsyncSession=Depends(get_db)):
    p=await require(request,db,"keys:read"); rows=(await db.execute(select(ApiKey).where(ApiKey.workspace_id==p["workspace_id"]).order_by(ApiKey.created_at.desc()))).scalars().all()
    return [{"id":r.id,"name":r.name,"prefix":r.prefix,"scopes":r.scopes,"created_at":r.created_at,"expires_at":r.expires_at,"revoked_at":r.revoked_at,"last_used_at":r.last_used_at} for r in rows]

@app.post("/v1/devices",status_code=201)
async def device(body:DeviceCreate,request:Request,db:AsyncSession=Depends(get_db)):
    p=await require(request,db,"devices:write")
    acct=(await db.execute(select(Workspace.account_id).where(Workspace.id==p["workspace_id"]))).scalar_one()
    row=Device(account_id=acct,user_id=p["user_id"],name=body.name,platform=body.platform,app_version=body.app_version,device_token_hash=hash_token(body.device_token)); db.add(row); await db.flush(); await log(db,p["workspace_id"],p["user_id"],"device.register","device",row.id); await db.commit()
    return {"id":row.id,"account_id":row.account_id,"user_id":row.user_id,"name":row.name,"platform":row.platform,"app_version":row.app_version,"created_at":row.created_at,"last_seen_at":row.last_seen_at}

@app.get("/v1/sync")
async def sync_pull(request:Request,after_revision:int=0,limit:int=500,db:AsyncSession=Depends(get_db)):
    p=await require(request,db,"sync:read"); limit=min(max(limit,1),500)
    cursor=await db.get(WorkspaceCursor,p["workspace_id"]); rows=(await db.execute(select(SyncRecord).where(SyncRecord.workspace_id==p["workspace_id"],SyncRecord.revision>after_revision).order_by(SyncRecord.revision).limit(limit))).scalars().all()
    return {"workspace_id":p["workspace_id"],"revision":cursor.revision if cursor else 0,"records":[{"entity_type":r.entity_type,"entity_id":r.entity_id,"revision":r.revision,"payload":r.payload,"updated_at":r.updated_at} for r in rows],"has_more":len(rows)>=limit}

@app.post("/v1/sync")
async def sync_push(body:SyncPush,request:Request,db:AsyncSession=Depends(get_db)):
    p=await require(request,db,"sync:write")
    if body.entity_type=="profile" and {"browser_settings","fingerprint","proxy_config","storage_path","cookies"}.intersection(body.payload): raise HTTPException(400,"Payload contains local-only browser state")
    cursor=await db.get(WorkspaceCursor,p["workspace_id"])
    existing=(await db.execute(select(SyncRecord).where(SyncRecord.workspace_id==p["workspace_id"],SyncRecord.entity_type==body.entity_type,SyncRecord.entity_id==body.entity_id))).scalar_one_or_none()
    current=existing.revision if existing else 0
    if body.expected_revision is not None and body.expected_revision!=current: raise HTTPException(409,f"Sync conflict: expected {body.expected_revision}, current {current}")
    cursor.revision=(cursor.revision if cursor else 0)+1
    if existing: existing.revision=cursor.revision; existing.payload=body.payload
    else: db.add(SyncRecord(workspace_id=p["workspace_id"],entity_type=body.entity_type,entity_id=body.entity_id,revision=cursor.revision,payload=body.payload))
    await log(db,p["workspace_id"],p["user_id"],"sync.push",body.entity_type,body.entity_id,{"revision":cursor.revision}); await db.commit()
    return {"workspace_id":p["workspace_id"],"entity_type":body.entity_type,"entity_id":body.entity_id,"revision":cursor.revision}

@app.get("/v1/activity")
async def activity(request:Request,limit:int=100,db:AsyncSession=Depends(get_db)):
    p=await require(request,db,"audit:read"); rows=(await db.execute(select(AuditEvent).where(AuditEvent.workspace_id==p["workspace_id"]).order_by(AuditEvent.created_at.desc()).limit(min(max(limit,1),250)))).scalars().all()
    return [{"id":r.id,"actor_user_id":r.actor_user_id,"action":r.action,"entity_type":r.entity_type,"entity_id":r.entity_id,"metadata":r.metadata_json,"created_at":r.created_at} for r in rows]

def main():
    import uvicorn
    uvicorn.run("app.main:app",host=settings().host,port=settings().port)
