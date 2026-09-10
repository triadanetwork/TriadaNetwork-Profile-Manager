"""API dependencies (dependency injection and auth guards)."""

import hmac
import hashlib
import json
from datetime import datetime, timezone

from fastapi import Header, HTTPException, Request

from camoufox_pm.config import get_settings
from camoufox_pm.core import auth
from camoufox_pm.core.database import StorageManager
from camoufox_pm.core.profile_manager import ProfileManager
from camoufox_pm.core.scheduler import TaskScheduler

_storage_manager: StorageManager | None = None
_profile_manager: ProfileManager | None = None
_scheduler: TaskScheduler | None = None


def set_storage_manager(storage_manager: StorageManager) -> None:
    """Register the shared ``StorageManager`` instance."""
    global _storage_manager
    _storage_manager = storage_manager


def set_profile_manager(profile_manager: ProfileManager) -> None:
    """Register the shared ``ProfileManager`` instance."""
    global _profile_manager
    _profile_manager = profile_manager


def get_storage_manager() -> StorageManager:
    """Return the shared ``StorageManager`` instance."""
    if _storage_manager is None:
        raise HTTPException(status_code=500, detail="StorageManager is not initialized")
    return _storage_manager


def get_profile_manager() -> ProfileManager:
    """Return the shared ``ProfileManager`` instance."""
    if _profile_manager is None:
        raise HTTPException(status_code=500, detail="ProfileManager is not initialized")
    return _profile_manager


def _api_key_matches(x_api_key: str | None) -> bool:
    """Whether the presented key equals the legacy instance key, in constant time."""
    configured = get_settings().api_key
    if not configured or x_api_key is None:
        return False
    return hmac.compare_digest(x_api_key, configured)

async def _cloud_api_key_context(x_api_key: str | None):
    """Resolve a workspace-scoped cloud key without exposing its secret."""
    if not x_api_key or get_settings().api_key and _api_key_matches(x_api_key):
        return None
    storage = get_storage_manager()
    row = await storage.get_workspace_api_key_by_hash(hashlib.sha256(x_api_key.encode()).hexdigest())
    if not row or row.get('revoked_at'):
        return None
    if row.get('expires_at'):
        try:
            expiry = datetime.fromisoformat(str(row['expires_at']))
            now = datetime.now(expiry.tzinfo or timezone.utc)
            if expiry <= now:
                return None
        except ValueError:
            return None
    return row


def set_scheduler(scheduler: TaskScheduler) -> None:
    """Register the shared ``TaskScheduler`` instance."""
    global _scheduler
    _scheduler = scheduler


def get_scheduler() -> TaskScheduler:
    """Return the shared ``TaskScheduler`` instance."""
    if _scheduler is None:
        raise HTTPException(status_code=500, detail="TaskScheduler is not initialized")
    return _scheduler


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Enforce the API key when ``CPM_API_KEY`` is set; a no-op otherwise."""
    if not get_settings().api_key:
        return
    if not _api_key_matches(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")



async def storage_touch_api_key(key_id: str) -> None:
    try:
        await get_storage_manager().touch_workspace_api_key(key_id)
    except Exception:
        pass

async def require_auth(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """The guard on every API route: a login session or the API key.

    Three configurations, all decided per request so a user created by the CLI
    while the server runs takes effect immediately:

    - no users, no ``CPM_API_KEY`` — open, exactly the pre-auth loopback default;
    - ``CPM_API_KEY`` set — a matching ``X-API-Key`` always passes, so machine
      clients are unaffected by user accounts existing or not;
    - any user account exists — everything else needs a valid session cookie.
    """
    cloud_key = await _cloud_api_key_context(x_api_key)
    if cloud_key is not None:
        request.state.auth_kind = "cloud_api_key"
        request.state.api_key_id = cloud_key["id"]
        request.state.api_key_scopes = set(json.loads(cloud_key["scopes"]))
        request.state.user_id = cloud_key.get("created_by")
        request.state.cloud_workspace_id = cloud_key["workspace_id"]
        await storage_touch_api_key(cloud_key["id"])
        return
    if _api_key_matches(x_api_key):
        request.state.auth_kind = "api_key"
        request.state.api_key_scopes = {"*"}
        return
    storage = get_storage_manager()
    if await storage.count_users() == 0:
        # Team mode must never be anonymously usable merely because its first
        # account has not been created yet.
        if (await storage.db.get_workspace())["workspace_type"] == "team":
            raise HTTPException(status_code=401, detail="Team workspace requires an account")
        if not get_settings().api_key:
            return
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token and await auth.validate_session(storage, token) is not None:
        session = await storage.get_session(auth.hash_token(token))
        if session is not None:
            request.state.auth_kind = "session"
            request.state.user_id = session["user_id"]
            request.state.username = session["username"]
            role = await storage.db.workspace_member_role(session["user_id"])
            # Every human session must belong to the local workspace. Personal
            # mode changes the UI, not the authorization boundary.
            if role is None:
                raise HTTPException(status_code=403, detail="Not a member of this workspace")
            request.state.workspace_role = role
            selected_workspace = request.cookies.get("triada_workspace")
            if selected_workspace:
                accessible = await storage.db.list_cloud_workspaces(session["user_id"])
                selected = next((item for item in accessible if item["id"] == selected_workspace), None)
                if selected is not None:
                    request.state.cloud_workspace_id = selected_workspace
                    request.state.workspace_role = selected["role"]
            return
    raise HTTPException(
        status_code=401, detail="Authentication required: log in or send a valid API key"
    )


ROLE_PERMISSIONS = {
    "owner": {"workspace:write", "team:write", "profiles:read", "profiles:write", "profiles:delete", "assignments:write", "proxies:read", "proxies:write", "audit:read"},
    "admin": {"workspace:write", "team:write", "profiles:read", "profiles:write", "profiles:delete", "assignments:write", "proxies:read", "proxies:write", "audit:read"},
    "team_lead": {"profiles:read", "profiles:write", "assignments:write", "proxies:read", "proxies:write", "audit:read"},
    "buyer": {"profiles:read", "profiles:write", "proxies:read"},
    "viewer": {"profiles:read", "proxies:read"},
}

async def require_permission(request: Request, permission: str) -> None:
    """Enforce a named workspace permission for local human/API operations."""
    auth_kind = getattr(request.state, "auth_kind", None)
    if auth_kind == "cloud_api_key":
        raise HTTPException(status_code=403, detail="Use the Cloud Control Plane endpoint for workspace-scoped API keys")
    if auth_kind == "api_key":
        return
    workspace = await get_storage_manager().db.get_workspace()
    if workspace["workspace_type"] != "team":
        return
    role = getattr(request.state, "workspace_role", None)
    if permission not in ROLE_PERMISSIONS.get(role, set()):
        raise HTTPException(status_code=403, detail=f"Permission required: {permission}")

async def require_workspace_admin(request: Request) -> None:
    """Require owner/admin for workspace configuration in all authenticated modes.

    Anonymous loopback installs may still use the pre-auth defaults, but once a
    human account exists only an owner/admin can rename or switch the workspace.
    """
    if getattr(request.state, "auth_kind", None) in {"api_key", "cloud_api_key"}:
        if getattr(request.state, "auth_kind", None) == "cloud_api_key":
            raise HTTPException(status_code=403, detail="Cloud API keys cannot manage local workspace settings through this endpoint")
        return
    role = getattr(request.state, "workspace_role", None)
    if role is None:
        # Preserve the local no-user development mode.
        return
    if role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Workspace admin role required")


async def require_role(request: Request, *roles: str) -> None:
    role = getattr(request.state, 'workspace_role', None)
    if getattr(request.state, 'auth_kind', None) == 'api_key':
        return
    if getattr(request.state, 'auth_kind', None) == 'cloud_api_key':
        raise HTTPException(status_code=403, detail='Cloud API keys cannot use local role endpoints')
    if role is None and await get_storage_manager().count_users() == 0:
        return
    if role not in roles:
        raise HTTPException(status_code=403, detail=f'Role required: {", ".join(roles)}')

async def require_profile_read(request: Request) -> None:
    await require_permission(request, 'profiles:read')

async def require_profile_write(request: Request) -> None:
    await require_permission(request, 'profiles:write')

async def require_profile_delete(request: Request) -> None:
    await require_permission(request, 'profiles:delete')

async def require_assignment_write(request: Request) -> None:
    await require_permission(request, 'assignments:write')


async def get_current_role(request: Request) -> str | None:
    """Return the authenticated workspace role, if any."""
    role = getattr(request.state, "workspace_role", None)
    if role:
        return role
    if getattr(request.state, "auth_kind", None) == "api_key":
        # Machine callers retain local API compatibility; treat them as workspace admins.
        return "admin"
    return None


async def require_audit_read(request: Request) -> None:
    await require_permission(request, "audit:read")


def profile_scope_sql(role: str | None, user_id: str | None) -> tuple[str, list[str]]:
    """Return a SQL predicate for production profile visibility.

    Team leads/admins/owners can see the workspace. Buyers see only profiles they own
    or are assigned to. Viewers retain read-only workspace visibility.
    """
    if role == "buyer" and user_id:
        return (" AND EXISTS (SELECT 1 FROM profile_assignments pa "
                "WHERE pa.profile_id = profiles.id AND (pa.owner_id = ? OR pa.assigned_user_id = ?))",
                [user_id, user_id])
    return "", []
