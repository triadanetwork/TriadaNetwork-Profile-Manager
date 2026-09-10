"""API routes for user login sessions.

Mounted without the auth guard: login must be reachable logged out, and the
session probe is how the UI decides whether to show the login screen at all.
"""

import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import NoReturn

from fastapi import APIRouter, HTTPException, Request, Response
from loguru import logger

from camoufox_pm.api.dependencies import get_storage_manager
from camoufox_pm.api.models.auth import AuthSessionResponse, LoginRequest
from camoufox_pm.api.models.system import ApiResponse
from camoufox_pm.config import get_settings
from camoufox_pm.core import auth

router = APIRouter()

# Flat friction against online guessing; argon2 already makes each attempt cost
# real work, this keeps a loop from trying thousands per second regardless.
FAILED_LOGIN_DELAY_SECONDS = 0.5


def _set_session_cookie(request: Request, response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        auth.SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies or request.url.scheme == "https",
    )


async def _reject_login(password: str, burn_hash: bool) -> NoReturn:
    """One indistinguishable failure for wrong password and unknown user."""
    if burn_hash:
        auth.verify_dummy(password)
    await asyncio.sleep(FAILED_LOGIN_DELAY_SECONDS)
    raise HTTPException(status_code=401, detail="Invalid username or password")


@router.post(
    "/auth/login",
    response_model=AuthSessionResponse,
    operation_id="login",
    summary="Log in and receive a session cookie.",
    description=(
        "Exchange a username and password for an HttpOnly session cookie. The failure "
        "response is identical whether the username exists or the password is wrong."
    ),
)
async def login(body: LoginRequest, request: Request, response: Response) -> AuthSessionResponse:
    """Verify credentials and open a session."""
    storage = get_storage_manager()
    user = await storage.get_user_by_username(body.username)
    if user is None:
        await _reject_login(body.password, burn_hash=True)
    if not auth.verify_password(user["password_hash"], body.password):
        await _reject_login(body.password, burn_hash=False)
    if auth.password_needs_rehash(user["password_hash"]):
        # Transparent upgrade to current argon2 parameters while we hold the
        # plaintext; the old hash keeps working if this write is never reached.
        await storage.update_user_password(user["username"], auth.hash_password(body.password))

    await storage.delete_expired_sessions()
    token = await auth.create_session(storage, user["id"])
    _set_session_cookie(request, response, token)
    logger.info(f"User {user['username']} logged in")
    return AuthSessionResponse(
        user_auth_enabled=True, authenticated=True, username=user["username"]
    )


@router.post(
    "/auth/logout",
    response_model=ApiResponse[None],
    operation_id="logout",
    summary="Log out and invalidate the session.",
    description=(
        "Delete the server-side session and clear the cookie. Idempotent: logging out "
        "without a session is not an error."
    ),
)
async def logout(request: Request, response: Response) -> ApiResponse[None]:
    """Invalidate the caller's session, if any."""
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token:
        await get_storage_manager().delete_session(auth.hash_token(token))
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return ApiResponse(success=True, message="Logged out", data=None)


@router.get(
    "/auth/session",
    response_model=AuthSessionResponse,
    operation_id="get_auth_session",
    summary="Report the caller's authentication state.",
    description=(
        "Whether user login is enabled on this instance and whether this request "
        "carries a valid session. Reachable without authentication."
    ),
)
async def get_auth_session(request: Request) -> AuthSessionResponse:
    """Report whether login is required and whether the caller is logged in."""
    storage = get_storage_manager()
    user_auth_enabled = await storage.count_users() > 0
    username = None
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token:
        username = await auth.validate_session(storage, token)
    return AuthSessionResponse(
        user_auth_enabled=user_auth_enabled,
        authenticated=username is not None,
        username=username,
    )


from pydantic import BaseModel, Field

class InviteAcceptRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=10, max_length=200)

@router.post(
    "/auth/invites/accept",
    response_model=AuthSessionResponse,
    operation_id="accept_invite",
    summary="Accept a workspace invite and create an account.",
)
async def accept_invite(body: InviteAcceptRequest, request: Request, response: Response) -> AuthSessionResponse:
    storage = get_storage_manager()
    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    invite = await storage.db.get_invite_by_token_hash(token_hash)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found or already used")
    expiry = datetime.fromisoformat(invite["expires_at"])
    now = datetime.now(expiry.tzinfo or timezone.utc)
    if expiry <= now:
        raise HTTPException(status_code=410, detail="Invite has expired")
    if body.username.strip().casefold() != invite["invited_username"].strip().casefold():
        raise HTTPException(status_code=400, detail="Username does not match this invite")
    user_id = f"usr-{secrets.token_hex(6)}"
    await storage.db.accept_workspace_invite(invite["id"], user_id, body.username, auth.hash_password(body.password))
    token = await auth.create_session(storage, user_id)
    _set_session_cookie(request, response, token)
    await storage.db.log_audit(user_id, "team.invite.accept", "workspace", invite["workspace_id"], {"username": body.username})
    return AuthSessionResponse(user_auth_enabled=True, authenticated=True, username=body.username)
