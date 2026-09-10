"""Application settings loaded from environment variables (prefix ``CPM_``)."""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from the environment or a ``.env`` file."""

    model_config = SettingsConfigDict(env_prefix="CPM_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    api_key: str | None = None
    db_path: str = "data/profiles.db"
    secret_key: str | None = None
    webui_dir: str | None = None
    # Lifetime of a login session. Sessions are stored server-side, so shortening
    # this takes effect for existing sessions on their next request.
    session_ttl_hours: int = 168
    # Force the Secure flag on the session cookie. The flag is set automatically
    # when the request itself arrived over HTTPS, but behind a TLS-terminating
    # proxy the app sees plain HTTP — set this there.
    secure_cookies: bool = False
    # Input is written to a temporary file before ZIP validation.  Keep that
    # separate from the extracted-data ceiling so a tiny compressed payload
    # cannot consume unbounded temporary disk.
    max_import_bytes: int = 1024 * 1024 * 1024
    # Cloud control-plane mode. Local-first remains the default; set a remote URL
    # later when a hosted control plane is deployed. The current v0.9 embedded
    # control plane uses the same database and exposes the same API contract.
    cloud_enabled: bool = True
    cloud_base_url: str | None = None
    cloud_sync_interval_seconds: int = 30
    cloud_workspace_cookie: bool = True
    # Local desktop bridge token. Generated per desktop process and never written
    # to the database. It authorizes tray/desktop-shell control of the loopback API.
    desktop_bridge_token: str | None = None
    # Optional remote control-plane sync endpoint. Empty keeps the desktop local-first.
    cloud_sync_enabled: bool = False
    cloud_sync_token: str | None = None
    # Optional update manifest. The desktop only checks metadata and verifies a
    # downloaded payload hash; it never executes an unverified update automatically.
    update_manifest_url: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()
