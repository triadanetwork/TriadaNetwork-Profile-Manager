from pydantic import BaseModel, Field

class RegisterRequest(BaseModel): username: str = Field(min_length=3,max_length=120); password: str = Field(min_length=12,max_length=256); account_name: str = Field(min_length=2,max_length=120)
class LoginRequest(BaseModel): username: str; password: str; workspace_id: str
class TokenResponse(BaseModel): access_token: str; refresh_token: str; token_type: str="bearer"; expires_in: int
class RefreshRequest(BaseModel): refresh_token: str = Field(min_length=20)
class WorkspaceCreate(BaseModel): name: str = Field(min_length=2,max_length=120); workspace_type: str = Field(default="team",pattern="^(personal|team)$")
class ApiKeyCreate(BaseModel): name: str = Field(min_length=2,max_length=100); scopes: list[str]; expires_days: int|None = Field(default=None,ge=1,le=3650)
class DeviceCreate(BaseModel): name: str = Field(min_length=2,max_length=100); platform: str|None=None; app_version: str|None=None; device_token: str = Field(min_length=16,max_length=300)
class SyncPush(BaseModel): entity_type: str = Field(pattern="^(profile|proxy_pool|tag)$"); entity_id: str; payload: dict; expected_revision: int|None=Field(default=None,ge=0)
