from typing import Any
from pydantic import BaseModel, Field

class WorkspaceResponse(BaseModel):
    id: str
    name: str
    workspace_type: str
    current_role: str | None = None

class MemberResponse(BaseModel):
    id: str
    username: str
    role: str

class MemberRoleUpdateRequest(BaseModel):
    role: str = Field(pattern=r"^(owner|admin|team_lead|buyer|viewer)$")

class InviteCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    role: str = Field(default="buyer", pattern=r"^(admin|team_lead|buyer|viewer)$")
    expires_hours: int = Field(default=72, ge=1, le=720)

class InviteResponse(BaseModel):
    id: str
    invited_username: str
    role: str
    expires_at: str
    token: str

class TagResponse(BaseModel):
    id: str
    name: str

class ProxyPoolResponse(BaseModel):
    id: str
    name: str
    provider: str | None = None
    country: str | None = None
    proxy_type: str | None = None
    status: str = "active"
    profile_count: int = 0
    proxy_count: int = 0

class ProfileOperationsResponse(BaseModel):
    profile_id: str
    owner_id: str | None = None
    assigned_user_id: str | None = None
    proxy_pool_id: str | None = None
    proxy_id: str | None = None
    tag_ids: list[str] = Field(default_factory=list)
    tags: list[TagResponse] = Field(default_factory=list)

class FieldAction(BaseModel):
    """Explicit set/clear/unchanged semantics for operational metadata."""
    action: str = Field(default="unchanged", pattern="^(unchanged|set|clear)$")
    value: str | list[str] | None = None

class ProfileOperationsUpdateRequest(BaseModel):
    owner: FieldAction = Field(default_factory=FieldAction)
    assigned_user: FieldAction = Field(default_factory=FieldAction)
    proxy_pool: FieldAction = Field(default_factory=FieldAction)
    tags: FieldAction = Field(default_factory=FieldAction)

class BulkProfileOperationsRequest(BaseModel):
    profile_ids: list[str] = Field(min_length=1)
    owner: FieldAction = Field(default_factory=FieldAction)
    assigned_user: FieldAction = Field(default_factory=FieldAction)
    proxy_pool: FieldAction = Field(default_factory=FieldAction)
    tags: FieldAction = Field(default_factory=FieldAction)


class TeamSummaryResponse(BaseModel):
    members: int
    roles: dict[str, int] = Field(default_factory=dict)
    assigned_profiles: int
    owned_profiles: int
    unassigned_profiles: int

class TeamDashboardResponse(BaseModel):
    workspace: WorkspaceResponse
    summary: TeamSummaryResponse
    pending_invites: int
    recent_activity: list[dict] = Field(default_factory=list)

class WorkspaceUpdateRequest(BaseModel):
    name: str | None = None
    workspace_type: str | None = None

class TagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

class ProxyPoolCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: str | None = None
    country: str | None = None
    proxy_type: str | None = None
    status: str = "active"


class ProxyInventoryResponse(BaseModel):
    id: str
    name: str
    workspace_id: str
    provider: str | None = None
    country: str | None = None
    proxy_type: str
    server: str
    username_set: bool = False
    pool_id: str | None = None
    pool_name: str | None = None
    status: str = "unknown"
    latency_ms: int | None = None
    last_check_at: str | None = None
    exit_ip: str | None = None
    exit_country: str | None = None
    exit_timezone: str | None = None
    last_error: str | None = None
    assigned_profile_id: str | None = None
    assigned_profile_name: str | None = None


class ProxyBulkImportRequest(BaseModel):
    pool_id: str | None = None
    provider: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=64)
    proxy_type: str = Field(default="http", pattern=r"^(http|https|socks4|socks5)$")

class ProxyInventoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    proxy_type: str = Field(pattern=r"^(http|https|socks4|socks5)$")
    server: str = Field(min_length=3, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=255)
    provider: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, min_length=2, max_length=64)
    pool_id: str | None = None

class ProxyInventoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    proxy_type: str | None = Field(default=None, pattern=r"^(http|https|socks4|socks5)$")
    server: str | None = Field(default=None, min_length=3, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=255)
    provider: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, min_length=2, max_length=64)
    pool_id: str | None = None
    status: str | None = Field(default=None, pattern=r"^(active|disabled|retired|unknown|healthy|degraded|unhealthy)$")

class ProxyAssignmentRequest(BaseModel):
    profile_id: str

class PoolAssignNextRequest(BaseModel):
    profile_id: str

class ProxyInventoryListResponse(BaseModel):
    proxies: list[ProxyInventoryResponse]
    total: int

class ProxyHealthResponse(BaseModel):
    proxy: ProxyInventoryResponse
    reachable: bool
    latency_ms: int | None = None
    error: str | None = None
    exit_ip: str | None = None
    exit_country: str | None = None
    exit_timezone: str | None = None
    findings: list[dict[str, str]] = Field(default_factory=list)
