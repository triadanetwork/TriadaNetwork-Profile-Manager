"""Cloud control-plane API models."""
from pydantic import BaseModel, Field
from typing import Literal

ROLE = Literal["owner", "admin", "team_lead", "buyer", "viewer"]

class CloudWorkspace(BaseModel):
    id: str
    name: str
    workspace_type: str
    role: str | None = None
    account_id: str

class CloudAccount(BaseModel):
    id: str
    name: str
    workspace_count: int
    created_at: str
    updated_at: str

class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    workspace_type: str = Field(default="personal", pattern=r"^(personal|team)$")

class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["workspace:read", "profiles:read", "sync:read"])
    expires_days: int | None = Field(default=None, ge=1, le=3650)

class ApiKeyResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    prefix: str
    scopes: list[str]
    created_at: str
    last_used_at: str | None = None
    expires_at: str | None = None
    revoked_at: str | None = None
    secret: str | None = None

class DeviceRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    platform: str | None = Field(default=None, max_length=50)
    app_version: str | None = Field(default=None, max_length=50)
    device_token: str = Field(min_length=16, max_length=300)

class DeviceResponse(BaseModel):
    id: str
    account_id: str
    user_id: str
    name: str
    platform: str | None = None
    app_version: str | None = None
    created_at: str
    last_seen_at: str
    revoked_at: str | None = None

class SyncPullResponse(BaseModel):
    workspace_id: str
    revision: int
    records: list[dict]
    has_more: bool

class SyncPushRequest(BaseModel):
    entity_type: str = Field(pattern=r"^(profile|proxy_pool|tag)$")
    entity_id: str
    payload: dict
    expected_revision: int | None = Field(default=None, ge=0)

class SyncPushResponse(BaseModel):
    workspace_id: str
    entity_type: str
    entity_id: str
    revision: int
