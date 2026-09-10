import hashlib, secrets
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .config import settings
from .models import ApiKey, RefreshToken, User, WorkspaceMember

ph = PasswordHasher()
ROLES={"owner","admin","team_lead","buyer","viewer"}
PERMISSIONS={
 "owner": {"workspace:read","workspace:write","team:read","team:write","profiles:read","profiles:write","profiles:delete","assignments:write","proxies:read","proxies:write","sync:read","sync:write","devices:read","devices:write","keys:read","keys:write","audit:read"},
 "admin": {"workspace:read","workspace:write","team:read","team:write","profiles:read","profiles:write","profiles:delete","assignments:write","proxies:read","proxies:write","sync:read","sync:write","devices:read","devices:write","keys:read","keys:write","audit:read"},
 "team_lead": {"workspace:read","team:read","profiles:read","profiles:write","profiles:delete","assignments:write","proxies:read","proxies:write","sync:read","sync:write","devices:read","audit:read"},
 "buyer": {"workspace:read","profiles:read","profiles:write","assignments:write","proxies:read","sync:read","devices:read"},
 "viewer": {"workspace:read","team:read","profiles:read","proxies:read","sync:read","audit:read"},
}
CLOUD_SCOPES={"workspace:read","workspace:write","team:read","team:write","profiles:read","profiles:write","profiles:delete","assignments:write","sync:read","sync:write","devices:read","devices:write","keys:read","keys:write","audit:read"}

def hash_token(value:str)->str: return hashlib.sha256(value.encode()).hexdigest()
def now(): return datetime.now(timezone.utc)
def issue_access(user_id:str, workspace_id:str, role:str)->str:
    payload={"sub":user_id,"workspace_id":workspace_id,"role":role,"typ":"access","exp":now()+timedelta(minutes=settings().jwt_ttl_minutes)}
    return jwt.encode(payload,settings().jwt_secret,algorithm="HS256")
def decode_access(token:str)->dict:
    try:
        payload=jwt.decode(token,settings().jwt_secret,algorithms=["HS256"])
        if payload.get("typ")!="access": raise ValueError
        return payload
    except Exception as exc:
        raise HTTPException(401,"Invalid or expired access token") from exc

async def principal(request:Request, db:AsyncSession)->dict:
    auth=request.headers.get("Authorization","")
    if auth.startswith("Bearer "):
        return decode_access(auth[7:]) | {"auth_kind":"user"}
    api=request.headers.get("X-API-Key")
    if api:
        row=(await db.execute(select(ApiKey).where(ApiKey.key_hash==hash_token(api)))).scalar_one_or_none()
        if not row or row.revoked_at or (row.expires_at and row.expires_at<=now()): raise HTTPException(401,"Invalid API key")
        row.last_used_at=now(); await db.commit()
        return {"auth_kind":"api_key","workspace_id":row.workspace_id,"user_id":row.created_by,"scopes":set(row.scopes),"role":None}
    raise HTTPException(401,"Authentication required")

async def require(request:Request, db:AsyncSession, permission:str|None=None)->dict:
    p=await principal(request,db)
    if permission:
        if p["auth_kind"]=="api_key":
            if permission not in p["scopes"] and "*" not in p["scopes"]: raise HTTPException(403,f"API key scope required: {permission}")
        elif permission not in PERMISSIONS.get(p.get("role"),set()):
            raise HTTPException(403,"Insufficient permission")
    return p

async def workspace_membership(db:AsyncSession,user_id:str,workspace_id:str)->WorkspaceMember|None:
    return (await db.execute(select(WorkspaceMember).where(WorkspaceMember.user_id==user_id,WorkspaceMember.workspace_id==workspace_id))).scalar_one_or_none()
