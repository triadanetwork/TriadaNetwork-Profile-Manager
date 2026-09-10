"""
SQLite storage layer for the Camoufox profile management system.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
import uuid

from loguru import logger
from pydantic import ValidationError

from .crypto import decrypt, encrypt
from .models import (
    Profile,
    ProfileGroup,
    ProfileStatus,
    ProxyCheckRecord,
    ProxyConfig,
    Schedule,
    ScheduleRun,
    UsageStats,
)


def _serialize_proxy(proxy: ProxyConfig) -> dict:
    """Serialize a proxy for storage, encrypting the password."""
    data = proxy.model_dump()
    if data.get("password"):
        data["password"] = encrypt(data["password"])
    return data


def _deserialize_proxy(data: dict) -> ProxyConfig:
    """Rebuild a proxy from storage, decrypting the password."""
    if data.get("password"):
        data["password"] = decrypt(data["password"])
    return ProxyConfig(**data)


class DatabaseManager:
    """Async-friendly SQLite database manager."""

    def __init__(self, db_path: str = "data/profiles.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection = None  # type: ignore[assignment]
        logger.info(f"DatabaseManager initialized with database: {self.db_path}")

    async def initialize(self):
        """Initialize the database and create tables."""
        self._connection = sqlite3.connect(str(self.db_path), timeout=30.0)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")

        await self._create_tables()
        await self._migrate()
        await self._ensure_cloud_bootstrap()
        await self._create_indexes()
        logger.info("Database initialized")

    async def _migrate(self):
        """Bring an existing database up to the current schema.

        Tables are created with ``CREATE TABLE IF NOT EXISTS``, so a database made
        by an older version keeps its original columns forever. Each entry here
        adds one column when it is missing; adding a column is safe to re-run and
        never touches existing rows.
        """
        added_columns = {
            "profiles": [("fingerprint", "TEXT"), ("proxy_check", "TEXT")],
            "profile_assignments": [("proxy_id", "TEXT")],
        }
        for table, columns in added_columns.items():
            cursor = self._connection.execute(f"PRAGMA table_info({table})")
            existing = {row["name"] for row in cursor.fetchall()}
            for name, column_type in columns:
                if name in existing:
                    continue
                self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")
                logger.info(f"Migrated {table}: added column {name}")
        self._connection.commit()

    async def _create_tables(self):
        """Create the database tables."""
        # Profiles table
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                group_id TEXT,
                status TEXT DEFAULT 'active',
                browser_settings TEXT NOT NULL,
                proxy_config TEXT,
                extensions TEXT,
                storage_path TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                fingerprint TEXT,
                proxy_check TEXT
            )
        """)

        # Profile groups table
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS profile_groups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                profile_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Usage statistics table
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT NOT NULL,
                action TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration INTEGER,
                success BOOLEAN DEFAULT 1,
                details TEXT
            )
        """)

        # User accounts for the web UI. Their mere existence turns login on, so a
        # database without rows here behaves exactly as before the table existed.
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Login sessions, keyed by the SHA-256 of the cookie token — the token
        # itself is never stored, so this table cannot be replayed if leaked.
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        """)

        # Workspace / team / operational metadata.
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                workspace_type TEXT NOT NULL DEFAULT 'personal',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS workspace_members (
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role TEXT NOT NULL DEFAULT 'buyer',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (workspace_id, user_id)
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS profile_assignments (
                profile_id TEXT PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                owner_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                assigned_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                proxy_pool_id TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                UNIQUE(workspace_id, name)
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS profile_tags (
                profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (profile_id, tag_id)
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS proxy_pools (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                provider TEXT,
                country TEXT,
                proxy_type TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(workspace_id, name)
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS proxy_inventory (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                proxy_type TEXT NOT NULL,
                server TEXT NOT NULL,
                username TEXT,
                password TEXT,
                provider TEXT,
                country TEXT,
                pool_id TEXT REFERENCES proxy_pools(id) ON DELETE SET NULL,
                status TEXT NOT NULL DEFAULT 'unknown',
                latency_ms INTEGER,
                last_check_at TIMESTAMP,
                exit_ip TEXT,
                exit_country TEXT,
                exit_timezone TEXT,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS profile_trash (
                profile_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                profile_json TEXT NOT NULL,
                operations_json TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                original_storage_path TEXT,
                trashed_storage_path TEXT,
                deleted_by TEXT REFERENCES users(id) ON DELETE SET NULL,
                deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS workspace_invites (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                invited_username TEXT NOT NULL COLLATE NOCASE,
                role TEXT NOT NULL DEFAULT 'buyer',
                token_hash TEXT NOT NULL UNIQUE,
                created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                accepted_at TIMESTAMP
            )
        """)

        # Cloud control plane / account layer. The browser remains local-first: these
        # tables contain account, workspace, device, API-key and sync metadata only.
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(owner_user_id)
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS account_members (
                account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role TEXT NOT NULL DEFAULT 'member',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, user_id)
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS account_workspaces (
                account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, workspace_id)
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS workspace_api_keys (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                prefix TEXT NOT NULL,
                scopes TEXT NOT NULL,
                created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                expires_at TIMESTAMP,
                revoked_at TIMESTAMP
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                platform TEXT,
                app_version TEXT,
                device_token_hash TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revoked_at TIMESTAMP
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS profile_workspaces (
                profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (profile_id, workspace_id)
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS cloud_sync_records (
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                payload TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (workspace_id, entity_type, entity_id)
            )
        """)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS workspace_cursors (
                workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
                revision INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Scheduled tasks. New tables need no _migrate entry: IF NOT EXISTS adds
        # them to an existing database without touching what is already there.
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                action TEXT NOT NULL,
                kind TEXT NOT NULL,
                interval_minutes INTEGER,
                at_time TEXT,
                days TEXT,
                run_minutes INTEGER,
                enabled BOOLEAN DEFAULT 1,
                next_run_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS schedule_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id TEXT NOT NULL,
                started_at TIMESTAMP NOT NULL,
                finished_at TIMESTAMP,
                outcome TEXT NOT NULL,
                message TEXT
            )
        """)

        self._connection.commit()

    async def _create_indexes(self):
        """Create indexes to optimize queries."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_profiles_group ON profiles(group_id)",
            "CREATE INDEX IF NOT EXISTS idx_profiles_status ON profiles(status)",
            "CREATE INDEX IF NOT EXISTS idx_profiles_created ON profiles(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_usage_stats_profile ON usage_stats(profile_id)",
            "CREATE INDEX IF NOT EXISTS idx_usage_stats_timestamp ON usage_stats(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_schedules_profile ON schedules(profile_id)",
            "CREATE INDEX IF NOT EXISTS idx_schedule_runs_schedule ON schedule_runs(schedule_id)",
            "CREATE INDEX IF NOT EXISTS idx_profile_assignments_workspace ON profile_assignments(workspace_id)",
            "CREATE INDEX IF NOT EXISTS idx_profile_tags_tag ON profile_tags(tag_id)",
            "CREATE INDEX IF NOT EXISTS idx_proxy_pools_workspace ON proxy_pools(workspace_id)",
            "CREATE INDEX IF NOT EXISTS idx_proxy_inventory_workspace ON proxy_inventory(workspace_id)",
            "CREATE INDEX IF NOT EXISTS idx_proxy_inventory_pool ON proxy_inventory(pool_id)",
            "CREATE INDEX IF NOT EXISTS idx_profile_workspaces_workspace ON profile_workspaces(workspace_id)",
            "CREATE INDEX IF NOT EXISTS idx_profile_workspaces_profile ON profile_workspaces(profile_id)",
            "CREATE INDEX IF NOT EXISTS idx_cloud_sync_workspace_updated ON cloud_sync_records(workspace_id, updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_workspace_api_keys_workspace ON workspace_api_keys(workspace_id)",
            "CREATE INDEX IF NOT EXISTS idx_account_members_user ON account_members(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_account_workspaces_workspace ON account_workspaces(workspace_id)",
            "CREATE INDEX IF NOT EXISTS idx_devices_account ON devices(account_id)",
            "CREATE INDEX IF NOT EXISTS idx_proxy_inventory_status ON proxy_inventory(status)",
            "CREATE INDEX IF NOT EXISTS idx_audit_log_workspace_created ON audit_log(workspace_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_workspace_invites_workspace ON workspace_invites(workspace_id)",
            "CREATE INDEX IF NOT EXISTS idx_profile_trash_workspace ON profile_trash(workspace_id, deleted_at)",
            "CREATE INDEX IF NOT EXISTS idx_workspace_invites_token ON workspace_invites(token_hash)",
        ]

        for index_sql in indexes:
            self._connection.execute(index_sql)

        self._connection.commit()

    # --- Profiles ---

    async def save_profile(self, profile: Profile):
        """Save a profile to the database."""
        self._connection.execute(
            """
            INSERT INTO profiles (
                id, name, group_id, status, browser_settings, proxy_config,
                extensions, storage_path, notes, created_at, updated_at, last_used,
                fingerprint, proxy_check
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                group_id = excluded.group_id,
                status = excluded.status,
                browser_settings = excluded.browser_settings,
                proxy_config = excluded.proxy_config,
                extensions = excluded.extensions,
                storage_path = excluded.storage_path,
                notes = excluded.notes,
                updated_at = excluded.updated_at,
                last_used = excluded.last_used,
                fingerprint = excluded.fingerprint,
                proxy_check = excluded.proxy_check
        """,
            (
                profile.id,
                profile.name,
                profile.group,
                profile.status.value if hasattr(profile.status, "value") else profile.status,
                json.dumps(profile.browser_settings.model_dump()),
                json.dumps(_serialize_proxy(profile.proxy)) if profile.proxy else None,
                json.dumps(profile.extensions),
                profile.storage_path,
                profile.notes,
                profile.created_at.isoformat(),
                profile.updated_at.isoformat(),
                profile.last_used.isoformat() if profile.last_used else None,
                json.dumps(profile.fingerprint) if profile.fingerprint else None,
                profile.proxy_check.model_dump_json() if profile.proxy_check else None,
            ),
        )
        self._connection.commit()
        workspace = self._connection.execute("SELECT id FROM workspaces ORDER BY created_at LIMIT 1").fetchone()
        if workspace:
            self._connection.execute("INSERT OR IGNORE INTO profile_workspaces (profile_id, workspace_id) VALUES (?, ?)", (profile.id, workspace["id"]))
            self._connection.commit()
        logger.debug(f"Profile {profile.name} saved")

    async def get_profile(self, profile_id: str) -> Profile | None:
        """Get a profile by ID."""
        cursor = self._connection.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_profile(row)
        return None

    async def update_profile(self, profile: Profile):
        """Update a profile."""
        profile.updated_at = datetime.now()
        await self.save_profile(profile)
        logger.debug(f"Profile {profile.name} updated")

    async def set_proxy_check(self, profile_id: str, record: ProxyCheckRecord | None) -> None:
        """Write only the proxy check, leaving every other column alone.

        A check takes seconds — up to thirty against a proxy that never answers —
        and `save_profile` replaces the whole row. Writing back a Profile read
        before that wait would revert anything edited during it, which is the
        hazard already noted in profile_manager.launch_browser. This also keeps a
        check from touching `updated_at`: asking a proxy a question is not an
        edit, and a bulk check should not make a selection look modified.
        """
        self._connection.execute(
            "UPDATE profiles SET proxy_check = ? WHERE id = ?",
            (record.model_dump_json() if record else None, profile_id),
        )
        self._connection.commit()

    async def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile, and the schedules that would otherwise fire against it."""
        self._connection.execute(
            "DELETE FROM schedule_runs WHERE schedule_id IN "
            "(SELECT id FROM schedules WHERE profile_id = ?)",
            (profile_id,),
        )
        self._connection.execute("DELETE FROM schedules WHERE profile_id = ?", (profile_id,))
        cursor = self._connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        self._connection.commit()
        deleted = cursor.rowcount > 0

        if deleted:
            logger.debug(f"Profile {profile_id} deleted")

        return deleted

    async def list_profiles(
        self, filters: dict | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Profile]:
        """List profiles with filtering and optional workspace visibility scope."""
        query = "SELECT * FROM profiles WHERE 1=1"
        params: list = []

        if filters:
            if "workspace_profile_predicate" in filters:
                query += filters["workspace_profile_predicate"]
                params.extend(filters.get("workspace_profile_params", []))
            if "group" in filters:
                query += " AND group_id = ?"
                params.append(filters["group"])
            if "status" in filters:
                query += " AND status = ?"
                params.append(filters["status"])
            if "name_like" in filters:
                query += " AND name LIKE ?"
                params.append(f"%{filters['name_like']}%")

        query += " ORDER BY created_at DESC"

        # SQLite will not take an OFFSET without a LIMIT, so an offset on its own
        # used to be dropped and the caller silently got the first page back.
        if limit or offset:
            query += " LIMIT ?"
            params.append(limit if limit else -1)
        if offset:
            query += " OFFSET ?"
            params.append(offset)

        cursor = self._connection.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_profile(row) for row in rows]

    async def count_profiles(self, filters: dict | None = None) -> int:
        """Count profiles with the same visibility scope used by list_profiles."""
        query = "SELECT COUNT(*) FROM profiles WHERE 1=1"
        params: list = []

        if filters:
            if "workspace_profile_predicate" in filters:
                query += filters["workspace_profile_predicate"]
                params.extend(filters.get("workspace_profile_params", []))
            if "group" in filters:
                query += " AND group_id = ?"
                params.append(filters["group"])
            if "status" in filters:
                query += " AND status = ?"
                params.append(filters["status"])

        cursor = self._connection.execute(query, params)
        return cursor.fetchone()[0]

    # --- Profile groups ---

    async def save_profile_group(self, group: ProfileGroup):
        """Save a profile group."""
        self._connection.execute(
            """
            INSERT OR REPLACE INTO profile_groups (
                id, name, description, profile_count, created_at
            ) VALUES (?, ?, ?, ?, ?)
        """,
            (
                group.id,
                group.name,
                group.description,
                group.profile_count,
                group.created_at.isoformat(),
            ),
        )
        self._connection.commit()
        logger.debug(f"Group {group.name} saved")

    async def list_profile_groups(self) -> list[ProfileGroup]:
        """List all groups."""
        cursor = self._connection.execute("""
            SELECT pg.*, COUNT(p.id) as actual_count
            FROM profile_groups pg
            LEFT JOIN profiles p ON pg.id = p.group_id
            GROUP BY pg.id
            ORDER BY pg.created_at DESC
        """)
        rows = cursor.fetchall()

        groups = []
        for row in rows:
            group = ProfileGroup(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                profile_count=row["actual_count"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            groups.append(group)

        return groups

    async def delete_profile_group(self, group_id: str) -> bool:
        """Delete a profile group."""
        # Ungroup the profiles that belonged to this group
        self._connection.execute(
            "UPDATE profiles SET group_id = NULL WHERE group_id = ?", (group_id,)
        )

        # Delete the group
        cursor = self._connection.execute("DELETE FROM profile_groups WHERE id = ?", (group_id,))
        self._connection.commit()

        return cursor.rowcount > 0

    # --- Workspace / operations ---

    async def ensure_default_workspace(self) -> str:
        row = self._connection.execute("SELECT id FROM workspaces ORDER BY created_at LIMIT 1").fetchone()
        if row:
            workspace_id = row["id"]
            # Repair legacy installs where the first account was created after the
            # workspace and was incorrectly inserted as viewer.
            first_user = self._connection.execute("SELECT id FROM users ORDER BY created_at LIMIT 1").fetchone()
            if first_user:
                member = self._connection.execute(
                    "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                    (workspace_id, first_user["id"]),
                ).fetchone()
                if member is None:
                    self._connection.execute(
                        "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, 'owner')",
                        (workspace_id, first_user["id"]),
                    )
                    self._connection.commit()
                elif member["role"] != "owner":
                    owner_exists = self._connection.execute(
                        "SELECT 1 FROM workspace_members WHERE workspace_id = ? AND role = 'owner' LIMIT 1",
                        (workspace_id,),
                    ).fetchone()
                    if owner_exists is None:
                        self._connection.execute(
                            "UPDATE workspace_members SET role = 'owner' WHERE workspace_id = ? AND user_id = ?",
                            (workspace_id, first_user["id"]),
                        )
                        self._connection.commit()
            return workspace_id
        workspace_id = "ws-personal-default"
        self._connection.execute(
            "INSERT INTO workspaces (id, name, workspace_type) VALUES (?, ?, ?)",
            (workspace_id, "Personal Workspace", "personal"),
        )
        first_user = self._connection.execute("SELECT id FROM users ORDER BY created_at LIMIT 1").fetchone()
        if first_user:
            self._connection.execute(
                "INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, 'owner')",
                (workspace_id, first_user["id"]),
            )
        self._connection.commit()
        return workspace_id

    async def get_workspace(self) -> dict:
        workspace_id = await self.ensure_default_workspace()
        row = self._connection.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        return dict(row)

    async def update_workspace(self, updates: dict) -> dict:
        workspace = await self.get_workspace()
        fields = []
        params = []
        if updates.get("name"):
            fields.append("name = ?"); params.append(updates["name"])
        if updates.get("workspace_type") in {"personal", "team"}:
            fields.append("workspace_type = ?"); params.append(updates["workspace_type"])
        if fields:
            fields.append("updated_at = ?"); params.append(datetime.now().isoformat())
            params.append(workspace["id"])
            self._connection.execute(f"UPDATE workspaces SET {', '.join(fields)} WHERE id = ?", params)
            self._connection.commit()
        return await self.get_workspace()

    async def list_workspace_members(self) -> list[dict]:
        workspace_id = await self.ensure_default_workspace()
        rows = self._connection.execute(
            "SELECT u.id, u.username, wm.role FROM workspace_members wm JOIN users u ON u.id = wm.user_id WHERE wm.workspace_id = ? ORDER BY u.username",
            (workspace_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    async def workspace_member_role(self, user_id: str) -> str | None:
        """Return a user's role in the local workspace, if any."""
        workspace_id = await self.ensure_default_workspace()
        row = self._connection.execute(
            "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_id),
        ).fetchone()
        return str(row["role"]) if row else None

    async def set_workspace_member_role(self, username: str, role: str) -> bool:
        workspace_id = await self.ensure_default_workspace()
        if role not in {"owner", "admin", "team_lead", "buyer", "viewer"}:
            raise ValueError("Unsupported workspace role")
        row = self._connection.execute(
            "SELECT user_id, role FROM workspace_members wm JOIN users u ON u.id = wm.user_id WHERE workspace_id = ? AND u.username = ?",
            (workspace_id, username),
        ).fetchone()
        if row is None:
            return False
        if row["role"] == "owner" and role != "owner":
            owners = self._connection.execute(
                "SELECT COUNT(*) FROM workspace_members WHERE workspace_id = ? AND role = 'owner'",
                (workspace_id,),
            ).fetchone()[0]
            if owners <= 1:
                raise ValueError("The workspace must retain at least one owner")
        cursor = self._connection.execute(
            "UPDATE workspace_members SET role = ? WHERE workspace_id = ? AND user_id = ?",
            (role, workspace_id, row["user_id"]),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    async def remove_workspace_member(self, username: str) -> bool:
        workspace_id = await self.ensure_default_workspace()
        row = self._connection.execute(
            "SELECT u.id, wm.role FROM workspace_members wm JOIN users u ON u.id = wm.user_id WHERE wm.workspace_id = ? AND u.username = ?",
            (workspace_id, username),
        ).fetchone()
        if row is None:
            return False
        if row["role"] == "owner":
            owners = self._connection.execute(
                "SELECT COUNT(*) FROM workspace_members WHERE workspace_id = ? AND role = 'owner'",
                (workspace_id,),
            ).fetchone()[0]
            if owners <= 1:
                raise ValueError("The workspace must retain at least one owner")
        self._connection.execute(
            "UPDATE profile_assignments SET owner_id = NULL, assigned_user_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE workspace_id = ? AND (owner_id = ? OR assigned_user_id = ?)",
            (workspace_id, row["id"], row["id"]),
        )
        self._connection.execute("DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?", (workspace_id, row["id"]))
        self._connection.commit()
        return True

    async def create_workspace_invite(self, invited_username: str, role: str, created_by: str | None, token_hash: str, expires_at: datetime) -> dict:
        workspace_id = await self.ensure_default_workspace()
        invite_id = f"invite-{uuid.uuid4().hex[:12]}"
        self._connection.execute(
            "INSERT INTO workspace_invites (id, workspace_id, invited_username, role, token_hash, created_by, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (invite_id, workspace_id, invited_username.strip(), role, token_hash, created_by, expires_at.isoformat()),
        )
        self._connection.commit()
        row = self._connection.execute("SELECT id, workspace_id, invited_username, role, created_at, expires_at, accepted_at FROM workspace_invites WHERE id = ?", (invite_id,)).fetchone()
        return dict(row)

    async def get_invite_by_token_hash(self, token_hash: str) -> dict | None:
        row = self._connection.execute(
            "SELECT * FROM workspace_invites WHERE token_hash = ? AND accepted_at IS NULL",
            (token_hash,),
        ).fetchone()
        return dict(row) if row else None

    async def accept_workspace_invite(self, invite_id: str, user_id: str, username: str, password_hash: str) -> None:
        invite = self._connection.execute("SELECT * FROM workspace_invites WHERE id = ? AND accepted_at IS NULL", (invite_id,)).fetchone()
        if invite is None:
            raise ValueError("Invite is invalid or already used")
        expires = datetime.fromisoformat(invite["expires_at"])
        now = datetime.now(expires.tzinfo) if expires.tzinfo else datetime.now()
        if expires <= now:
            raise ValueError("Invite has expired")
        try:
            self._connection.execute("INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)", (user_id, username.strip(), password_hash, datetime.now().isoformat()))
        except sqlite3.IntegrityError as exc:
            raise ValueError("Username already exists") from exc
        self._connection.execute("INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)", (invite["workspace_id"], user_id, invite["role"]))
        account = self._connection.execute("SELECT account_id FROM account_workspaces WHERE workspace_id = ? LIMIT 1", (invite["workspace_id"],)).fetchone()
        if account:
            self._connection.execute("INSERT OR IGNORE INTO account_members (account_id, user_id, role) VALUES (?, ?, 'member')", (account["account_id"], user_id))
        self._connection.execute("UPDATE workspace_invites SET accepted_at = ? WHERE id = ?", (datetime.now().isoformat(), invite_id))
        self._connection.commit()

    async def list_pending_invites(self) -> list[dict]:
        workspace_id = await self.ensure_default_workspace()
        rows = self._connection.execute("SELECT id, invited_username, role, created_at, expires_at, accepted_at FROM workspace_invites WHERE workspace_id = ? ORDER BY created_at DESC", (workspace_id,)).fetchall()
        return [dict(r) for r in rows]

    async def list_tags(self) -> list[dict]:
        workspace_id = await self.ensure_default_workspace()
        rows = self._connection.execute("SELECT id, name FROM tags WHERE workspace_id = ? ORDER BY name", (workspace_id,)).fetchall()
        return [dict(row) for row in rows]

    async def create_tag(self, name: str) -> dict:
        workspace_id = await self.ensure_default_workspace()
        tag_id = f"tag-{uuid.uuid4().hex[:12]}"
        try:
            self._connection.execute("INSERT INTO tags (id, workspace_id, name) VALUES (?, ?, ?)", (tag_id, workspace_id, name.strip()))
            self._connection.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Tag already exists") from exc
        row = self._connection.execute("SELECT id, name FROM tags WHERE id = ?", (tag_id,)).fetchone()
        return dict(row)

    async def list_proxy_pools(self) -> list[dict]:
        workspace_id = await self.ensure_default_workspace()
        rows = self._connection.execute(
            """SELECT pp.*, COUNT(DISTINCT pa.profile_id) AS profile_count,
                      (SELECT COUNT(*) FROM proxy_inventory pi WHERE pi.pool_id = pp.id AND pi.workspace_id = pp.workspace_id) AS proxy_count
               FROM proxy_pools pp LEFT JOIN profile_assignments pa ON pa.proxy_pool_id = pp.id
               WHERE pp.workspace_id = ? GROUP BY pp.id ORDER BY pp.name""",
            (workspace_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    async def create_proxy_pool(self, data: dict) -> dict:
        workspace_id = await self.ensure_default_workspace()
        pool_id = f"pool-{uuid.uuid4().hex[:12]}"
        try:
            self._connection.execute(
                "INSERT INTO proxy_pools (id, workspace_id, name, provider, country, proxy_type, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (pool_id, workspace_id, data["name"].strip(), data.get("provider"), data.get("country"), data.get("proxy_type"), data.get("status", "active")),
            )
            self._connection.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Proxy pool already exists") from exc
        row = self._connection.execute("""SELECT pp.*, 0 AS profile_count,
               (SELECT COUNT(*) FROM proxy_inventory pi WHERE pi.pool_id = pp.id AND pi.workspace_id = pp.workspace_id) AS proxy_count
               FROM proxy_pools pp WHERE pp.id = ? AND pp.workspace_id = ?""", (pool_id, workspace_id)).fetchone()
        return dict(row)

    async def get_profile_operations(self, profile_id: str) -> dict:
        workspace_id = await self.ensure_default_workspace()
        row = self._connection.execute(
            "SELECT owner_id, assigned_user_id, proxy_pool_id, proxy_id, workspace_id FROM profile_assignments WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
        if row and row["workspace_id"] != workspace_id:
            raise ValueError("Profile does not belong to the current workspace")
        assignment = dict(row) if row else {"owner_id": None, "assigned_user_id": None, "proxy_pool_id": None, "proxy_id": None}
        tags = self._connection.execute(
            "SELECT t.id, t.name FROM tags t JOIN profile_tags pt ON pt.tag_id = t.id WHERE pt.profile_id = ? AND t.workspace_id = ? ORDER BY t.name",
            (profile_id, workspace_id),
        ).fetchall()
        return {"profile_id": profile_id, "workspace_id": workspace_id, **{k: assignment.get(k) for k in ("owner_id", "assigned_user_id", "proxy_pool_id", "proxy_id")}, "tags": [dict(t) for t in tags], "tag_ids": [t["id"] for t in tags]}

    def _validate_operation_refs(self, workspace_id: str, owner_id, assigned_user_id, proxy_pool_id, tag_ids):
        user_ids = [x for x in (owner_id, assigned_user_id) if x is not None]
        if user_ids:
            placeholders = ','.join('?' for _ in user_ids)
            rows = self._connection.execute(
                f"SELECT user_id FROM workspace_members WHERE workspace_id = ? AND user_id IN ({placeholders})",
                [workspace_id, *user_ids],
            ).fetchall()
            if {r["user_id"] for r in rows} != set(user_ids):
                raise ValueError("Owner or assigned user is not a member of this workspace")
        if proxy_pool_id is not None:
            row = self._connection.execute(
                "SELECT 1 FROM proxy_pools WHERE id = ? AND workspace_id = ?", (proxy_pool_id, workspace_id)
            ).fetchone()
            if row is None:
                raise ValueError("Proxy pool does not belong to this workspace")
        if tag_ids is not None:
            ids = list(dict.fromkeys(tag_ids))
            if ids:
                placeholders = ','.join('?' for _ in ids)
                rows = self._connection.execute(
                    f"SELECT id FROM tags WHERE workspace_id = ? AND id IN ({placeholders})",
                    [workspace_id, *ids],
                ).fetchall()
                if {r["id"] for r in rows} != set(ids):
                    raise ValueError("One or more tags do not belong to this workspace")

    async def update_profile_operations(self, profile_id: str, updates: dict) -> dict:
        workspace_id = await self.ensure_default_workspace()
        profile = self._connection.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if profile is None:
            raise ValueError("Profile not found")
        current_row = self._connection.execute(
            "SELECT owner_id, assigned_user_id, proxy_pool_id, proxy_id, workspace_id FROM profile_assignments WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
        if current_row and current_row["workspace_id"] != workspace_id:
            raise ValueError("Profile does not belong to the current workspace")
        current = {k: (current_row[k] if current_row else None) for k in ("owner_id", "assigned_user_id", "proxy_pool_id", "proxy_id")}
        next_values = dict(current)
        for field, action in (("owner_id", updates.get("owner")), ("assigned_user_id", updates.get("assigned_user")), ("proxy_pool_id", updates.get("proxy_pool"))):
            if action is None or action.get("action", "unchanged") == "unchanged":
                continue
            if action["action"] == "clear":
                next_values[field] = None
            elif action["action"] == "set":
                value = action.get("value")
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field} requires a non-empty value when action=set")
                next_values[field] = value.strip()
        tags_action = updates.get("tags")
        next_tags = None
        if tags_action is not None and tags_action.get("action", "unchanged") != "unchanged":
            if tags_action["action"] == "clear":
                next_tags = []
            else:
                raw = tags_action.get("value")
                if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
                    raise ValueError("tags requires a list of tag IDs when action=set")
                next_tags = list(dict.fromkeys(raw))
        self._validate_operation_refs(workspace_id, next_values["owner_id"], next_values["assigned_user_id"], next_values["proxy_pool_id"], next_tags)
        now = datetime.now().isoformat()
        self._connection.execute(
            "INSERT INTO profile_assignments (profile_id, workspace_id, owner_id, assigned_user_id, proxy_pool_id, proxy_id, updated_at) VALUES (?, ?, ?, ?, ?, COALESCE((SELECT proxy_id FROM profile_assignments WHERE profile_id = ?), NULL), ?) ON CONFLICT(profile_id) DO UPDATE SET workspace_id=excluded.workspace_id, owner_id=excluded.owner_id, assigned_user_id=excluded.assigned_user_id, proxy_pool_id=excluded.proxy_pool_id, updated_at=excluded.updated_at",
            (profile_id, workspace_id, next_values["owner_id"], next_values["assigned_user_id"], next_values["proxy_pool_id"], profile_id, now),
        )
        if next_tags is not None:
            self._connection.execute("DELETE FROM profile_tags WHERE profile_id = ?", (profile_id,))
            for tag_id in next_tags:
                self._connection.execute("INSERT INTO profile_tags (profile_id, tag_id) VALUES (?, ?)", (profile_id, tag_id))
        self._connection.commit()
        return await self.get_profile_operations(profile_id)

    async def bulk_update_profile_operations(self, profile_ids: list[str], updates: dict) -> int:
        workspace_id = await self.ensure_default_workspace()
        unique_ids = list(dict.fromkeys(profile_ids))
        if not unique_ids:
            return 0
        placeholders = ','.join('?' for _ in unique_ids)
        rows = self._connection.execute(f"SELECT id FROM profiles WHERE id IN ({placeholders})", unique_ids).fetchall()
        found = {r["id"] for r in rows}
        if found != set(unique_ids):
            missing = sorted(set(unique_ids) - found)
            raise ValueError(f"Profiles not found: {', '.join(missing)}")
        for profile_id in unique_ids:
            await self.update_profile_operations(profile_id, updates)
        return len(unique_ids)

    def _proxy_inventory_row(self, row) -> dict:
        if row is None:
            return None
        data = dict(row)
        data["username_set"] = bool(data.get("username"))
        data.pop("username", None)
        data.pop("password", None)
        return data

    async def list_proxy_inventory(self, pool_id: str | None = None, status: str | None = None) -> list[dict]:
        workspace_id = await self.ensure_default_workspace()
        query = """
            SELECT pi.*, pp.name AS pool_name, p.name AS assigned_profile_name, pa.profile_id AS assigned_profile_id
            FROM proxy_inventory pi
            LEFT JOIN proxy_pools pp ON pp.id = pi.pool_id AND pp.workspace_id = pi.workspace_id
            LEFT JOIN profile_assignments pa ON pa.proxy_id = pi.id AND pa.workspace_id = pi.workspace_id
            LEFT JOIN profiles p ON p.id = pa.profile_id
            WHERE pi.workspace_id = ?
        """
        params: list = [workspace_id]
        if pool_id:
            query += " AND pi.pool_id = ?"; params.append(pool_id)
        if status:
            query += " AND pi.status = ?"; params.append(status)
        query += " ORDER BY pi.updated_at DESC, pi.name"
        rows = self._connection.execute(query, params).fetchall()
        return [self._proxy_inventory_row(r) for r in rows]

    async def get_proxy_inventory(self, proxy_id: str) -> dict | None:
        workspace_id = await self.ensure_default_workspace()
        row = self._connection.execute("""
            SELECT pi.*, pp.name AS pool_name, p.name AS assigned_profile_name, pa.profile_id AS assigned_profile_id
            FROM proxy_inventory pi
            LEFT JOIN proxy_pools pp ON pp.id = pi.pool_id AND pp.workspace_id = pi.workspace_id
            LEFT JOIN profile_assignments pa ON pa.proxy_id = pi.id AND pa.workspace_id = pi.workspace_id
            LEFT JOIN profiles p ON p.id = pa.profile_id
            WHERE pi.id = ? AND pi.workspace_id = ?
        """, (proxy_id, workspace_id)).fetchone()
        return self._proxy_inventory_row(row) if row else None

    async def _get_proxy_inventory_secret(self, proxy_id: str) -> dict | None:
        workspace_id = await self.ensure_default_workspace()
        row = self._connection.execute("SELECT * FROM proxy_inventory WHERE id = ? AND workspace_id = ?", (proxy_id, workspace_id)).fetchone()
        return dict(row) if row else None

    async def create_proxy_inventory(self, data: dict) -> dict:
        workspace_id = await self.ensure_default_workspace()
        if data.get("pool_id"):
            ok = self._connection.execute("SELECT 1 FROM proxy_pools WHERE id = ? AND workspace_id = ?", (data["pool_id"], workspace_id)).fetchone()
            if not ok: raise ValueError("Proxy pool does not belong to this workspace")
        proxy_id = f"prx-{uuid.uuid4().hex[:12]}"
        self._connection.execute("""INSERT INTO proxy_inventory
            (id, workspace_id, name, proxy_type, server, username, password, provider, country, pool_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown')""",
            (proxy_id, workspace_id, data["name"].strip(), data["proxy_type"], data["server"].strip(),
             encrypt(data.get("username")) if data.get("username") else None,
             encrypt(data.get("password")) if data.get("password") else None,
             data.get("provider"), data.get("country"), data.get("pool_id")))
        self._connection.commit()
        return await self.get_proxy_inventory(proxy_id)

    async def update_proxy_inventory(self, proxy_id: str, updates: dict) -> dict:
        current = await self._get_proxy_inventory_secret(proxy_id)
        if not current: raise ValueError("Proxy not found in this workspace")
        workspace_id = current["workspace_id"]
        if "pool_id" in updates and updates["pool_id"]:
            ok = self._connection.execute("SELECT 1 FROM proxy_pools WHERE id = ? AND workspace_id = ?", (updates["pool_id"], workspace_id)).fetchone()
            if not ok: raise ValueError("Proxy pool does not belong to this workspace")
        fields=[]; params=[]
        for key in ("name","proxy_type","server","provider","country","pool_id","status"):
            if key in updates:
                fields.append(f"{key} = ?"); params.append(updates[key].strip() if key in {"name","server","provider","country"} and isinstance(updates[key], str) else updates[key])
        if "username" in updates:
            fields.append("username = ?"); params.append(encrypt(updates["username"]) if updates["username"] else None)
        if "password" in updates:
            fields.append("password = ?"); params.append(encrypt(updates["password"]) if updates["password"] else None)
        if not fields: return await self.get_proxy_inventory(proxy_id)
        fields.append("updated_at = ?"); params.append(datetime.now().isoformat()); params.extend([proxy_id, workspace_id])
        self._connection.execute(f"UPDATE proxy_inventory SET {', '.join(fields)} WHERE id = ? AND workspace_id = ?", params)
        self._connection.commit()
        assigned = self._connection.execute(
            "SELECT profile_id FROM profile_assignments WHERE proxy_id = ? AND workspace_id = ?",
            (proxy_id, workspace_id),
        ).fetchone()
        if assigned:
            latest = await self._get_proxy_inventory_secret(proxy_id)
            profile = await self.get_profile(assigned["profile_id"])
            if latest and profile:
                from .models import ProxyConfig
                proxy_data = {
                    "type": latest["proxy_type"],
                    "server": latest["server"],
                    "country": latest.get("country"),
                }
                if latest.get("username"):
                    proxy_data["username"] = decrypt(latest["username"])
                if latest.get("password"):
                    proxy_data["password"] = decrypt(latest["password"])
                profile.proxy = ProxyConfig(**proxy_data)
                await self.update_profile(profile)
        return await self.get_proxy_inventory(proxy_id)

    async def delete_proxy_inventory(self, proxy_id: str) -> bool:
        current = await self._get_proxy_inventory_secret(proxy_id)
        if not current: return False
        assigned = self._connection.execute("SELECT profile_id FROM profile_assignments WHERE proxy_id = ?", (proxy_id,)).fetchone()
        if assigned: raise ValueError("Proxy is assigned to a profile; unassign it first")
        cursor = self._connection.execute("DELETE FROM proxy_inventory WHERE id = ? AND workspace_id = ?", (proxy_id, current["workspace_id"]))
        self._connection.commit()
        return cursor.rowcount > 0

    async def set_proxy_health(self, proxy_id: str, result: dict) -> dict:
        current = await self._get_proxy_inventory_secret(proxy_id)
        if not current: raise ValueError("Proxy not found in this workspace")
        status = "healthy" if result.get("reachable") and not any(f.get("level") == "error" for f in result.get("findings", [])) else ("degraded" if result.get("reachable") else "unhealthy")
        self._connection.execute("""UPDATE proxy_inventory SET status=?, latency_ms=?, last_check_at=?, exit_ip=?, exit_country=?, exit_timezone=?, last_error=?, updated_at=? WHERE id=? AND workspace_id=?""",
            (status, result.get("latency_ms"), result.get("checked_at"), result.get("exit_ip"), result.get("exit_country"), result.get("exit_timezone"), result.get("error"), datetime.now().isoformat(), proxy_id, current["workspace_id"]))
        self._connection.commit()
        return await self.get_proxy_inventory(proxy_id)

    async def assign_next_proxy_from_pool(self, pool_id: str, profile_id: str) -> dict:
        workspace_id = await self.ensure_default_workspace()
        pool = self._connection.execute("SELECT 1 FROM proxy_pools WHERE id = ? AND workspace_id = ?", (pool_id, workspace_id)).fetchone()
        if not pool:
            raise ValueError("Proxy pool does not belong to this workspace")
        profile = self._connection.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not profile:
            raise ValueError("Profile not found")
        row = self._connection.execute("""
            SELECT pi.id FROM proxy_inventory pi
            LEFT JOIN profile_assignments pa ON pa.proxy_id = pi.id AND pa.workspace_id = pi.workspace_id
            WHERE pi.workspace_id = ? AND pi.pool_id = ? AND pa.profile_id IS NULL
              AND pi.status NOT IN ('disabled', 'retired', 'unhealthy')
            ORDER BY CASE pi.status WHEN 'healthy' THEN 0 WHEN 'active' THEN 1 WHEN 'unknown' THEN 2 ELSE 3 END,
                     COALESCE(pi.latency_ms, 999999), pi.updated_at ASC
            LIMIT 1
        """, (workspace_id, pool_id)).fetchone()
        if not row:
            raise ValueError("No available proxy in this pool")
        return await self.assign_proxy_to_profile(row["id"], profile_id)

    async def assign_proxy_to_profile(self, proxy_id: str, profile_id: str) -> dict:
        current = await self._get_proxy_inventory_secret(proxy_id)
        if not current: raise ValueError("Proxy not found in this workspace")
        profile = self._connection.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not profile: raise ValueError("Profile not found")
        old = self._connection.execute("SELECT profile_id FROM profile_assignments WHERE proxy_id = ?", (proxy_id,)).fetchone()
        if old and old["profile_id"] != profile_id: raise ValueError("Proxy is already assigned to another profile")
        # Clear any prior managed-proxy association for this profile.
        self._connection.execute("UPDATE profile_assignments SET proxy_id = NULL WHERE profile_id = ?", (profile_id,))
        self._connection.execute("""INSERT INTO profile_assignments (profile_id, workspace_id, proxy_id) VALUES (?, ?, ?)
            ON CONFLICT(profile_id) DO UPDATE SET proxy_id=excluded.proxy_id, workspace_id=excluded.workspace_id, updated_at=CURRENT_TIMESTAMP""",
            (profile_id, current["workspace_id"], proxy_id))
        # Keep the existing browser profile schema authoritative for launch compatibility.
        proxy_data = {"type": current["proxy_type"], "server": current["server"], "country": current["country"]}
        if current.get("username"): proxy_data["username"] = decrypt(current["username"])
        if current.get("password"): proxy_data["password"] = decrypt(current["password"])
        from .models import ProxyConfig
        # Rehydrate through the existing row converter to avoid duplicating serialization rules.
        profile_obj = self._row_to_profile(profile)
        profile_obj.proxy = ProxyConfig(**proxy_data)
        await self.update_profile(profile_obj)
        self._connection.commit()
        return await self.get_proxy_inventory(proxy_id)

    async def unassign_proxy_from_profile(self, proxy_id: str) -> dict:
        current = await self._get_proxy_inventory_secret(proxy_id)
        if not current: raise ValueError("Proxy not found in this workspace")
        row = self._connection.execute("SELECT profile_id FROM profile_assignments WHERE proxy_id = ?", (proxy_id,)).fetchone()
        if row:
            profile = await self.get_profile(row["profile_id"])
            if profile:
                profile.proxy = None
                await self.update_profile(profile)
            self._connection.execute("UPDATE profile_assignments SET proxy_id=NULL, updated_at=CURRENT_TIMESTAMP WHERE profile_id=?", (row["profile_id"],))
            self._connection.commit()
        return await self.get_proxy_inventory(proxy_id)

    async def get_team_summary(self) -> dict:
        workspace_id = await self.ensure_default_workspace()
        members = self._connection.execute(
            "SELECT COUNT(*) FROM workspace_members WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()[0]
        by_role = self._connection.execute(
            "SELECT role, COUNT(*) AS count FROM workspace_members WHERE workspace_id = ? GROUP BY role ORDER BY role",
            (workspace_id,),
        ).fetchall()
        assigned = self._connection.execute(
            "SELECT COUNT(*) FROM profile_assignments WHERE workspace_id = ? AND assigned_user_id IS NOT NULL",
            (workspace_id,),
        ).fetchone()[0]
        owned = self._connection.execute(
            "SELECT COUNT(*) FROM profile_assignments WHERE workspace_id = ? AND owner_id IS NOT NULL",
            (workspace_id,),
        ).fetchone()[0]
        unassigned = self._connection.execute(
            "SELECT COUNT(*) FROM profiles p WHERE NOT EXISTS (SELECT 1 FROM profile_assignments pa WHERE pa.profile_id = p.id AND pa.workspace_id = ? AND (pa.owner_id IS NOT NULL OR pa.assigned_user_id IS NOT NULL))",
            (workspace_id,),
        ).fetchone()[0]
        return {
            "members": members,
            "roles": {row["role"]: row["count"] for row in by_role},
            "assigned_profiles": assigned,
            "owned_profiles": owned,
            "unassigned_profiles": unassigned,
        }

    async def list_audit(self, limit: int = 100, action: str | None = None, actor_user_id: str | None = None) -> list[dict]:
        workspace_id = await self.ensure_default_workspace()
        query = """SELECT a.id, a.workspace_id, a.actor_user_id, u.username, a.action, a.entity_type, a.entity_id, a.metadata, a.created_at
                   FROM audit_log a LEFT JOIN users u ON u.id = a.actor_user_id
                   WHERE a.workspace_id = ?"""
        params: list = [workspace_id]
        if action:
            query += " AND a.action = ?"; params.append(action)
        if actor_user_id:
            query += " AND a.actor_user_id = ?"; params.append(actor_user_id)
        query += " ORDER BY a.id DESC LIMIT ?"; params.append(max(1, min(limit, 500)))
        rows = self._connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    async def list_audit_actions(self) -> list[str]:
        workspace_id = await self.ensure_default_workspace()
        rows = self._connection.execute(
            "SELECT DISTINCT action FROM audit_log WHERE workspace_id = ? ORDER BY action", (workspace_id,)
        ).fetchall()
        return [str(r["action"]) for r in rows]

    async def log_audit(self, actor_user_id: str | None, action: str, entity_type: str, entity_id: str | None = None, metadata: dict | None = None) -> None:
        workspace_id = await self.ensure_default_workspace()
        self._connection.execute(
            "INSERT INTO audit_log (workspace_id, actor_user_id, action, entity_type, entity_id, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (workspace_id, actor_user_id, action, entity_type, entity_id, json.dumps(metadata or {})),
        )
        self._connection.commit()


    # --- Statistics ---

    async def log_usage(self, usage_stats: UsageStats):
        """Record a usage statistic."""
        self._connection.execute(
            """
            INSERT INTO usage_stats (
                profile_id, action, timestamp, duration, success, details
            ) VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                usage_stats.profile_id,
                usage_stats.action,
                usage_stats.timestamp.isoformat(),
                usage_stats.duration,
                usage_stats.success,
                json.dumps(usage_stats.details) if usage_stats.details else None,
            ),
        )
        self._connection.commit()

    async def get_profile_usage_stats(self, profile_id: str, limit: int = 100) -> list[UsageStats]:
        """Get usage statistics for a profile."""
        cursor = self._connection.execute(
            """
            SELECT * FROM usage_stats
            WHERE profile_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (profile_id, limit),
        )

        rows = cursor.fetchall()
        stats = []

        for row in rows:
            stat = UsageStats(
                id=row["id"],
                profile_id=row["profile_id"],
                action=row["action"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                duration=row["duration"],
                success=bool(row["success"]),
                details=json.loads(row["details"]) if row["details"] else None,
            )
            stats.append(stat)

        return stats

    # --- Users and sessions ---

    async def create_user(self, user_id: str, username: str, password_hash: str) -> None:
        """Create a user; raises ``ValueError`` when the username is taken."""
        try:
            self._connection.execute(
                "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user_id, username, password_hash, datetime.now().isoformat()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"User {username!r} already exists") from exc
        self._connection.commit()
        workspace_id = await self.ensure_default_workspace()
        existing_users = await self.count_users()
        owner_exists = self._connection.execute(
            "SELECT 1 FROM workspace_members WHERE workspace_id = ? AND role = 'owner' LIMIT 1", (workspace_id,)
        ).fetchone()
        role = "owner" if existing_users == 1 or owner_exists is None else "viewer"
        self._connection.execute(
            "INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace_id, user_id, role),
        )
        self._connection.commit()
        # Deliberately logs the name only, never the hash.
        logger.info(f"User {username} created")

    async def get_user_by_username(self, username: str) -> dict | None:
        cursor = self._connection.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    async def update_user_password(self, username: str, password_hash: str) -> bool:
        cursor = self._connection.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username)
        )
        self._connection.commit()
        return cursor.rowcount > 0

    async def delete_user(self, username: str) -> bool:
        """Delete a user; the foreign key cascades their open sessions away."""
        cursor = self._connection.execute("DELETE FROM users WHERE username = ?", (username,))
        self._connection.commit()
        return cursor.rowcount > 0

    async def count_users(self) -> int:
        cursor = self._connection.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]

    async def list_users(self) -> list[dict]:
        """Usernames and creation times only — hashes stay in the table."""
        cursor = self._connection.execute(
            "SELECT username, created_at FROM users ORDER BY created_at"
        )
        return [dict(row) for row in cursor.fetchall()]

    async def create_session(self, token_hash: str, user_id: str, expires_at: datetime) -> None:
        self._connection.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash, user_id, datetime.now().isoformat(), expires_at.isoformat()),
        )
        self._connection.commit()

    async def get_session(self, token_hash: str) -> dict | None:
        cursor = self._connection.execute(
            """
            SELECT s.token_hash, s.user_id, s.expires_at, u.username
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ?
            """,
            (token_hash,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    async def delete_session(self, token_hash: str) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM sessions WHERE token_hash = ?", (token_hash,)
        )
        self._connection.commit()
        return cursor.rowcount > 0

    async def delete_expired_sessions(self) -> int:
        cursor = self._connection.execute(
            "DELETE FROM sessions WHERE expires_at <= ?", (datetime.now().isoformat(),)
        )
        self._connection.commit()
        return cursor.rowcount

    # --- Schedules ---

    async def save_schedule(self, schedule: Schedule):
        """Insert or replace a schedule."""
        self._connection.execute(
            """
            INSERT OR REPLACE INTO schedules (
                id, profile_id, action, kind, interval_minutes, at_time, days,
                run_minutes, enabled, next_run_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                schedule.id,
                schedule.profile_id,
                schedule.action,
                schedule.kind,
                schedule.interval_minutes,
                schedule.at_time,
                json.dumps(schedule.days) if schedule.days else None,
                schedule.run_minutes,
                schedule.enabled,
                schedule.next_run_at.isoformat() if schedule.next_run_at else None,
                schedule.created_at.isoformat(),
                schedule.updated_at.isoformat(),
            ),
        )
        self._connection.commit()

    async def get_schedule(self, schedule_id: str) -> Schedule | None:
        """Get a schedule by ID."""
        cursor = self._connection.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
        row = cursor.fetchone()
        return self._row_to_schedule(row) if row else None

    async def list_schedules(self, profile_id: str | None = None) -> list[Schedule]:
        """List schedules, oldest first so the UI order is stable."""
        if profile_id:
            cursor = self._connection.execute(
                "SELECT * FROM schedules WHERE profile_id = ? ORDER BY created_at",
                (profile_id,),
            )
        else:
            cursor = self._connection.execute("SELECT * FROM schedules ORDER BY created_at")
        return [self._row_to_schedule(row) for row in cursor.fetchall()]

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule and its run history."""
        self._connection.execute("DELETE FROM schedule_runs WHERE schedule_id = ?", (schedule_id,))
        cursor = self._connection.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        self._connection.commit()
        return cursor.rowcount > 0

    async def log_schedule_run(self, run: ScheduleRun, keep: int = 20) -> ScheduleRun:
        """Record one firing and prune the history to the newest ``keep`` rows.

        Bounded per schedule rather than by age: an every-five-minutes schedule
        would otherwise write hundreds of rows a day into a database that also
        holds the profiles.
        """
        cursor = self._connection.execute(
            """
            INSERT INTO schedule_runs (schedule_id, started_at, finished_at, outcome, message)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                run.schedule_id,
                run.started_at.isoformat(),
                run.finished_at.isoformat() if run.finished_at else None,
                run.outcome,
                run.message,
            ),
        )
        run.id = cursor.lastrowid
        self._connection.execute(
            """
            DELETE FROM schedule_runs WHERE schedule_id = ? AND id NOT IN (
                SELECT id FROM schedule_runs WHERE schedule_id = ? ORDER BY id DESC LIMIT ?
            )
        """,
            (run.schedule_id, run.schedule_id, keep),
        )
        self._connection.commit()
        return run

    async def list_schedule_runs(self, schedule_id: str, limit: int = 20) -> list[ScheduleRun]:
        """Get the newest runs of a schedule, newest first."""
        cursor = self._connection.execute(
            "SELECT * FROM schedule_runs WHERE schedule_id = ? ORDER BY id DESC LIMIT ?",
            (schedule_id, limit),
        )
        return [
            ScheduleRun(
                id=row["id"],
                schedule_id=row["schedule_id"],
                started_at=datetime.fromisoformat(row["started_at"]),
                finished_at=(
                    datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None
                ),
                outcome=row["outcome"],
                message=row["message"],
            )
            for row in cursor.fetchall()
        ]

    # --- Utilities ---

    def _row_to_schedule(self, row) -> Schedule:
        """Convert a database row into a Schedule object."""
        return Schedule(
            id=row["id"],
            profile_id=row["profile_id"],
            action=row["action"],
            kind=row["kind"],
            interval_minutes=row["interval_minutes"],
            at_time=row["at_time"],
            days=json.loads(row["days"]) if row["days"] else None,
            run_minutes=row["run_minutes"],
            enabled=bool(row["enabled"]),
            next_run_at=(
                datetime.fromisoformat(row["next_run_at"]) if row["next_run_at"] else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_profile(self, row) -> Profile:
        """Convert a database row into a Profile object."""
        from .models import BrowserSettings

        # Parse browser_settings
        browser_settings_data = json.loads(row["browser_settings"])
        browser_settings = BrowserSettings(**browser_settings_data)

        # Parse proxy_config if present (password is decrypted on read).
        proxy = None
        if row["proxy_config"]:
            proxy = _deserialize_proxy(json.loads(row["proxy_config"]))

        # Parse extensions
        extensions = json.loads(row["extensions"]) if row["extensions"] else []

        # Present only once the profile has been launched, and absent entirely on
        # rows written before the column existed.
        keys = row.keys()
        fingerprint = (
            json.loads(row["fingerprint"]) if "fingerprint" in keys and row["fingerprint"] else None
        )
        stored_check = None
        if "proxy_check" in keys and row["proxy_check"]:
            try:
                stored_check = ProxyCheckRecord.model_validate_json(row["proxy_check"])
            except ValidationError as error:
                # A cosmetic column must not be able to take down the list: this
                # runs for every row, so raising here 500s the whole screen over
                # one unreadable value. Losing the dot is the right cost.
                logger.warning(f"Profile {row['id']}: unreadable proxy check, ignoring ({error})")

        return Profile(
            id=row["id"],
            name=row["name"],
            group=row["group_id"],
            status=ProfileStatus(row["status"]),
            browser_settings=browser_settings,
            proxy=proxy,
            extensions=extensions,
            storage_path=row["storage_path"],
            notes=row["notes"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_used=datetime.fromisoformat(row["last_used"]) if row["last_used"] else None,
            fingerprint=fingerprint,
            proxy_check=stored_check,
        )

    async def _ensure_cloud_bootstrap(self) -> None:
        """Create account/workspace links and metadata sync state for legacy installs."""
        workspace_id = await self.ensure_default_workspace()
        users = self._connection.execute("SELECT id, username FROM users ORDER BY created_at").fetchall()
        if users:
            owner = users[0]
            account = self._connection.execute(
                "SELECT id FROM accounts WHERE owner_user_id = ?", (owner["id"],)
            ).fetchone()
            if account is None:
                account_id = f"acct-{uuid.uuid4().hex[:12]}"
                self._connection.execute(
                    "INSERT INTO accounts (id, owner_user_id, name) VALUES (?, ?, ?)",
                    (account_id, owner["id"], f"{owner['username']}'s Account"),
                )
            else:
                account_id = account["id"]
            self._connection.execute(
                "INSERT OR IGNORE INTO account_workspaces (account_id, workspace_id) VALUES (?, ?)",
                (account_id, workspace_id),
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO account_members (account_id, user_id, role) VALUES (?, ?, 'owner')",
                (account_id, owner["id"]),
            )
        # Every legacy profile is explicitly linked to the default workspace.
        self._connection.execute(
            "INSERT OR IGNORE INTO profile_workspaces (profile_id, workspace_id) "
            "SELECT id, ? FROM profiles", (workspace_id,)
        )
        self._connection.execute(
            "INSERT OR IGNORE INTO workspace_cursors (workspace_id, revision) VALUES (?, 0)",
            (workspace_id,),
        )
        self._connection.commit()

    async def list_cloud_accounts(self, user_id: str) -> list[dict]:
        rows = self._connection.execute(
            "SELECT a.id, a.name, a.created_at, a.updated_at, "
            "COUNT(DISTINCT aw.workspace_id) AS workspace_count "
            "FROM accounts a JOIN account_members am ON am.account_id = a.id AND am.user_id = ? "
            "LEFT JOIN account_workspaces aw ON aw.account_id = a.id "
            "GROUP BY a.id ORDER BY a.created_at", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    async def list_cloud_workspaces(self, user_id: str) -> list[dict]:
        rows = self._connection.execute(
            "SELECT w.id, w.name, w.workspace_type, wm.role, aw.account_id "
            "FROM account_workspaces aw JOIN accounts a ON a.id = aw.account_id "
            "JOIN account_members am ON am.account_id = a.id AND am.user_id = ? "
            "JOIN workspaces w ON w.id = aw.workspace_id "
            "JOIN workspace_members wm ON wm.workspace_id = w.id AND wm.user_id = ? "
            "ORDER BY w.created_at", (user_id, user_id)
        ).fetchall()
        return [dict(r) for r in rows]

    async def create_cloud_workspace(self, user_id: str, name: str, workspace_type: str = "personal") -> dict:
        role = "owner"
        account = self._connection.execute(
            "SELECT id FROM accounts WHERE owner_user_id = ?", (user_id,)
        ).fetchone()
        if account is None:
            raise ValueError("Account not initialized")
        ws_id = f"ws-{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        try:
            self._connection.execute(
                "INSERT INTO workspaces (id, name, workspace_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (ws_id, name.strip(), workspace_type, now, now),
            )
            self._connection.execute(
                "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)",
                (ws_id, user_id, role),
            )
            self._connection.execute(
                "INSERT INTO account_workspaces (account_id, workspace_id) VALUES (?, ?)",
                (account["id"], ws_id),
            )
            self._connection.execute(
                "INSERT INTO workspace_cursors (workspace_id, revision) VALUES (?, 0)", (ws_id,)
            )
            self._connection.commit()
        except sqlite3.IntegrityError as exc:
            self._connection.rollback()
            raise ValueError("Workspace could not be created") from exc
        return (await self.list_cloud_workspaces(user_id))[-1]

    async def list_workspace_api_keys(self, workspace_id: str) -> list[dict]:
        rows = self._connection.execute(
            "SELECT id, workspace_id, name, prefix, scopes, created_at, last_used_at, expires_at, revoked_at "
            "FROM workspace_api_keys WHERE workspace_id = ? ORDER BY created_at DESC", (workspace_id,)
        ).fetchall()
        data=[]
        for r in rows:
            item=dict(r); item['scopes']=json.loads(item['scopes']); data.append(item)
        return data

    async def create_workspace_api_key(self, workspace_id: str, name: str, key_hash: str, prefix: str, scopes: list[str], created_by: str | None, expires_at: str | None) -> dict:
        key_id=f"key-{uuid.uuid4().hex[:12]}"
        self._connection.execute(
            "INSERT INTO workspace_api_keys (id, workspace_id, name, key_hash, prefix, scopes, created_by, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (key_id, workspace_id, name.strip(), key_hash, prefix, json.dumps(sorted(set(scopes))), created_by, expires_at),
        )
        self._connection.commit()
        return (await self._get_workspace_api_key_meta(key_id))

    async def _get_workspace_api_key_meta(self, key_id: str) -> dict:
        row=self._connection.execute("SELECT id, workspace_id, name, prefix, scopes, created_at, last_used_at, expires_at, revoked_at FROM workspace_api_keys WHERE id=?", (key_id,)).fetchone()
        if not row: raise ValueError("API key not found")
        item=dict(row); item['scopes']=json.loads(item['scopes']); return item

    async def get_workspace_api_key_by_hash(self, key_hash: str) -> dict | None:
        row=self._connection.execute("SELECT * FROM workspace_api_keys WHERE key_hash=?", (key_hash,)).fetchone()
        return dict(row) if row else None

    async def revoke_workspace_api_key(self, workspace_id: str, key_id: str) -> bool:
        cur=self._connection.execute("UPDATE workspace_api_keys SET revoked_at=? WHERE id=? AND workspace_id=? AND revoked_at IS NULL", (datetime.now().isoformat(), key_id, workspace_id))
        self._connection.commit(); return cur.rowcount>0

    async def touch_workspace_api_key(self, key_id: str) -> None:
        self._connection.execute("UPDATE workspace_api_keys SET last_used_at=? WHERE id=?", (datetime.now().isoformat(), key_id)); self._connection.commit()

    async def register_device(self, account_id: str, user_id: str, name: str, platform: str | None, app_version: str | None, token_hash: str) -> dict:
        device_id=f"dev-{uuid.uuid4().hex[:12]}"
        self._connection.execute(
            "INSERT INTO devices (id, account_id, user_id, name, platform, app_version, device_token_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (device_id, account_id, user_id, name.strip(), platform, app_version, token_hash),
        )
        self._connection.commit()
        row=self._connection.execute("SELECT id, account_id, user_id, name, platform, app_version, created_at, last_seen_at, revoked_at FROM devices WHERE id=?", (device_id,)).fetchone()
        return dict(row)

    async def list_devices(self, account_id: str) -> list[dict]:
        rows=self._connection.execute("SELECT id, account_id, user_id, name, platform, app_version, created_at, last_seen_at, revoked_at FROM devices WHERE account_id=? ORDER BY last_seen_at DESC", (account_id,)).fetchall()
        return [dict(r) for r in rows]

    async def revoke_device(self, account_id: str, device_id: str) -> bool:
        cur=self._connection.execute("UPDATE devices SET revoked_at=? WHERE id=? AND account_id=? AND revoked_at IS NULL", (datetime.now().isoformat(), device_id, account_id)); self._connection.commit(); return cur.rowcount>0

    async def _next_workspace_revision(self, workspace_id: str) -> int:
        row=self._connection.execute("SELECT revision FROM workspace_cursors WHERE workspace_id=?", (workspace_id,)).fetchone()
        rev=(int(row['revision']) if row else 0)+1
        self._connection.execute("INSERT INTO workspace_cursors(workspace_id, revision, updated_at) VALUES(?,?,?) ON CONFLICT(workspace_id) DO UPDATE SET revision=excluded.revision, updated_at=excluded.updated_at", (workspace_id, rev, datetime.now().isoformat()))
        return rev

    async def upsert_cloud_sync_record(self, workspace_id: str, entity_type: str, entity_id: str, payload: dict, expected_revision: int | None = None) -> dict:
        existing=self._connection.execute("SELECT revision FROM cloud_sync_records WHERE workspace_id=? AND entity_type=? AND entity_id=?", (workspace_id, entity_type, entity_id)).fetchone()
        current_revision=int(existing['revision']) if existing else 0
        if expected_revision is not None and expected_revision != current_revision:
            raise ValueError(f"Sync conflict: expected revision {expected_revision}, current revision {current_revision}")
        revision=await self._next_workspace_revision(workspace_id)
        self._connection.execute(
            "INSERT INTO cloud_sync_records(workspace_id, entity_type, entity_id, revision, payload, updated_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(workspace_id, entity_type, entity_id) DO UPDATE SET revision=excluded.revision, payload=excluded.payload, updated_at=excluded.updated_at",
            (workspace_id, entity_type, entity_id, revision, json.dumps(payload, separators=(',', ':')), datetime.now().isoformat()),
        )
        self._connection.commit()
        return {'workspace_id':workspace_id,'entity_type':entity_type,'entity_id':entity_id,'revision':revision,'payload':payload}

    async def list_cloud_sync_records(self, workspace_id: str, after_revision: int = 0, limit: int = 500) -> dict:
        rows=self._connection.execute(
            "SELECT workspace_id, entity_type, entity_id, revision, payload, updated_at FROM cloud_sync_records WHERE workspace_id=? AND revision>? ORDER BY revision LIMIT ?",
            (workspace_id, after_revision, limit),
        ).fetchall()
        records=[]
        for r in rows:
            item=dict(r); item['payload']=json.loads(item['payload']); records.append(item)
        cursor=self._connection.execute("SELECT revision FROM workspace_cursors WHERE workspace_id=?", (workspace_id,)).fetchone()
        current=int(cursor['revision']) if cursor else 0
        return {'workspace_id':workspace_id,'revision':current,'records':records,'has_more':len(records)>=limit}

    async def build_profile_cloud_metadata(self, workspace_id: str, profile_id: str) -> dict | None:
        link=self._connection.execute("SELECT 1 FROM profile_workspaces WHERE profile_id=? AND workspace_id=?", (profile_id, workspace_id)).fetchone()
        if not link: return None
        p=self._connection.execute("SELECT id,name,group_id,status,created_at,updated_at,last_used FROM profiles WHERE id=?", (profile_id,)).fetchone()
        if not p: return None
        op=await self.get_profile_operations(profile_id)
        tags=[dict(r) for r in self._connection.execute("SELECT t.id,t.name FROM profile_tags pt JOIN tags t ON t.id=pt.tag_id WHERE pt.profile_id=? AND t.workspace_id=? ORDER BY t.name", (profile_id,workspace_id)).fetchall()]
        return {
            'id': p['id'], 'name': p['name'], 'group_id': p['group_id'], 'status': p['status'],
            'created_at': p['created_at'], 'updated_at': p['updated_at'], 'last_used': p['last_used'],
            'ownership': {'owner_id': op.get('owner_id'), 'assigned_user_id': op.get('assigned_user_id')},
            'proxy': {'pool_id': op.get('proxy_pool_id'), 'proxy_id': op.get('proxy_id')},
            'tags': tags,
        }

    async def sync_workspace_profiles(self, workspace_id: str) -> dict:
        profile_ids=[r['profile_id'] for r in self._connection.execute("SELECT profile_id FROM profile_workspaces WHERE workspace_id=?", (workspace_id,)).fetchall()]
        pushed=0
        for pid in profile_ids:
            payload=await self.build_profile_cloud_metadata(workspace_id,pid)
            if payload is not None:
                await self.upsert_cloud_sync_record(workspace_id,'profile',pid,payload)
                pushed+=1
        return {'pushed':pushed}



    async def trash_profile(self, profile_id: str, deleted_by: str | None = None) -> dict | None:
        """Soft-delete a profile into the local trash, retaining enough metadata to restore it."""
        profile = await self.get_profile(profile_id)
        if not profile:
            return None
        workspace = await self.ensure_default_workspace()
        existing = self._connection.execute("SELECT 1 FROM profile_trash WHERE profile_id = ?", (profile_id,)).fetchone()
        if existing:
            return dict(self._connection.execute("SELECT * FROM profile_trash WHERE profile_id = ?", (profile_id,)).fetchone())

        ops = await self.get_profile_operations(profile_id)
        safe_profile = profile.model_dump(mode="json")
        if safe_profile.get("proxy"):
            proxy = safe_profile["proxy"]
            if proxy.get("password"):
                proxy["password"] = encrypt(proxy["password"])
            if proxy.get("username"):
                proxy["username"] = encrypt(proxy["username"])
        tags = [dict(r) for r in self._connection.execute(
            "SELECT t.id, t.name FROM profile_tags pt JOIN tags t ON t.id = pt.tag_id WHERE pt.profile_id = ?", (profile_id,)
        ).fetchall()]
        original = profile.storage_path
        trashed = None
        if original:
            trashed = str(Path(original).parent / "trash" / Path(original).name)
        self._connection.execute(
            "INSERT INTO profile_trash (profile_id, workspace_id, profile_json, operations_json, tags_json, original_storage_path, trashed_storage_path, deleted_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (profile_id, workspace, json.dumps(safe_profile), json.dumps(ops), json.dumps(tags), original, trashed, deleted_by),
        )
        self._connection.execute("DELETE FROM schedule_runs WHERE schedule_id IN (SELECT id FROM schedules WHERE profile_id = ?)", (profile_id,))
        self._connection.execute("DELETE FROM schedules WHERE profile_id = ?", (profile_id,))
        self._connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        self._connection.commit()
        return dict(self._connection.execute("SELECT * FROM profile_trash WHERE profile_id = ?", (profile_id,)).fetchone())

    async def _get_profile_trash_record(self, profile_id: str) -> dict | None:
        workspace=await self.ensure_default_workspace()
        row=self._connection.execute("SELECT * FROM profile_trash WHERE profile_id=? AND workspace_id=?", (profile_id,workspace)).fetchone()
        return dict(row) if row else None

    async def list_profile_trash(self) -> list[dict]:
        workspace = await self.ensure_default_workspace()
        rows=self._connection.execute("SELECT profile_id, workspace_id, profile_json, operations_json, tags_json, original_storage_path, trashed_storage_path, deleted_by, deleted_at FROM profile_trash WHERE workspace_id = ? ORDER BY deleted_at DESC", (workspace,)).fetchall()
        result=[]
        for row in rows:
            item=dict(row)
            profile=json.loads(item.pop('profile_json'))
            ops=json.loads(item.pop('operations_json'))
            tags=json.loads(item.pop('tags_json'))
            item['name']=profile.get('name')
            item['status']=profile.get('status')
            item['tags']=tags
            item['owner_id']=ops.get('owner_id')
            item['assigned_user_id']=ops.get('assigned_user_id')
            result.append(item)
        return result

    async def restore_profile_from_trash(self, profile_id: str) -> Profile | None:
        workspace = await self.ensure_default_workspace()
        row=self._connection.execute("SELECT * FROM profile_trash WHERE profile_id = ? AND workspace_id = ?", (profile_id, workspace)).fetchone()
        if not row:
            return None
        item=dict(row)
        profile_data=json.loads(item['profile_json'])
        if profile_data.get('proxy'):
            proxy=profile_data['proxy']
            if proxy.get('password'): proxy['password']=decrypt(proxy['password'])
            if proxy.get('username'): proxy['username']=decrypt(proxy['username'])
        profile_data['storage_path']=item['original_storage_path']
        profile=Profile(**profile_data)
        await self.save_profile(profile)
        self._connection.execute("INSERT OR IGNORE INTO profile_workspaces (profile_id, workspace_id) VALUES (?, ?)", (profile.id, workspace))
        ops=json.loads(item['operations_json'])
        if any(ops.get(k) for k in ('owner_id','assigned_user_id','proxy_pool_id','proxy_id')):
            self._connection.execute("INSERT INTO profile_assignments (profile_id, workspace_id, owner_id, assigned_user_id, proxy_pool_id, proxy_id) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(profile_id) DO UPDATE SET workspace_id=excluded.workspace_id, owner_id=excluded.owner_id, assigned_user_id=excluded.assigned_user_id, proxy_pool_id=excluded.proxy_pool_id, proxy_id=excluded.proxy_id, updated_at=CURRENT_TIMESTAMP", (profile.id,workspace,ops.get('owner_id'),ops.get('assigned_user_id'),ops.get('proxy_pool_id'),ops.get('proxy_id')))
        for tag in json.loads(item['tags_json']):
            if self._connection.execute("SELECT 1 FROM tags WHERE id = ? AND workspace_id = ?", (tag['id'],workspace)).fetchone():
                self._connection.execute("INSERT OR IGNORE INTO profile_tags (profile_id, tag_id) VALUES (?, ?)", (profile.id,tag['id']))
        self._connection.execute("DELETE FROM profile_trash WHERE profile_id = ?", (profile_id,))
        self._connection.commit()
        return profile

    async def permanently_delete_trash(self, profile_id: str) -> bool:
        workspace=await self.ensure_default_workspace()
        cur=self._connection.execute("DELETE FROM profile_trash WHERE profile_id = ? AND workspace_id = ?", (profile_id,workspace))
        self._connection.commit()
        return cur.rowcount > 0

    async def bulk_create_proxy_inventory(self, rows: list[dict]) -> dict:
        workspace=await self.ensure_default_workspace()
        created=[]; failed=[]
        for idx,data in enumerate(rows, start=1):
            try:
                data=dict(data); data['workspace_id']=workspace
                if not data.get('name'): data['name']=f"Proxy {idx:04d}"
                if data.get('pool_id') and not self._connection.execute("SELECT 1 FROM proxy_pools WHERE id=? AND workspace_id=?", (data['pool_id'],workspace)).fetchone():
                    raise ValueError('Pool does not belong to this workspace')
                proxy_id=f"px-{uuid.uuid4().hex[:12]}"
                username=encrypt(data['username']) if data.get('username') else None
                password=encrypt(data['password']) if data.get('password') else None
                self._connection.execute("INSERT INTO proxy_inventory (id,workspace_id,name,proxy_type,server,username,password,provider,country,pool_id) VALUES (?,?,?,?,?,?,?,?,?,?)", (proxy_id,workspace,data['name'],data.get('proxy_type','http'),data['server'],username,password,data.get('provider'),data.get('country'),data.get('pool_id')))
                created.append(proxy_id)
            except Exception as exc:
                failed.append({'line': idx, 'error': str(exc)})
        self._connection.commit()
        result=[]
        for pid in created:
            item=await self.get_proxy_inventory(pid)
            if item: result.append(item)
        return {'created': len(result), 'failed': failed, 'proxies': result}

    async def close(self):
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection: sqlite3.Connection = None  # type: ignore[assignment]
        logger.info("Database connection closed")


class StorageManager:
    """StorageManager backed by the SQLite database."""

    def __init__(self, db_path: str = "data/profiles.db"):
        self.db = DatabaseManager(db_path)
        logger.info(f"StorageManager initialized with database: {db_path}")

    async def initialize(self):
        """Initialize the database."""
        await self.db.initialize()

    # Profile methods
    async def save_profile(self, profile: Profile):
        await self.db.save_profile(profile)

    async def get_profile(self, profile_id: str) -> Profile | None:
        return await self.db.get_profile(profile_id)

    async def update_profile(self, profile: Profile):
        await self.db.update_profile(profile)

    async def set_proxy_check(self, profile_id: str, record: ProxyCheckRecord | None) -> None:
        await self.db.set_proxy_check(profile_id, record)

    async def delete_profile(self, profile_id: str) -> bool:
        return await self.db.delete_profile(profile_id)

    async def list_profiles(
        self, filters: dict | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Profile]:
        return await self.db.list_profiles(filters, limit, offset)

    async def count_profiles(self, filters: dict | None = None) -> int:
        return await self.db.count_profiles(filters)

    # Group methods
    async def save_profile_group(self, group: ProfileGroup):
        await self.db.save_profile_group(group)

    async def list_profile_groups(self) -> list[ProfileGroup]:
        return await self.db.list_profile_groups()

    # Statistics methods
    async def log_usage(self, usage_stats: UsageStats):
        await self.db.log_usage(usage_stats)

    async def get_profile_usage_stats(self, profile_id: str) -> list[UsageStats]:
        return await self.db.get_profile_usage_stats(profile_id)

    async def delete_profile_group(self, group_id: str) -> bool:
        return await self.db.delete_profile_group(group_id)

    # User and session methods
    async def create_user(self, user_id: str, username: str, password_hash: str) -> None:
        await self.db.create_user(user_id, username, password_hash)

    async def get_user_by_username(self, username: str) -> dict | None:
        return await self.db.get_user_by_username(username)

    async def update_user_password(self, username: str, password_hash: str) -> bool:
        return await self.db.update_user_password(username, password_hash)

    async def delete_user(self, username: str) -> bool:
        return await self.db.delete_user(username)

    async def count_users(self) -> int:
        return await self.db.count_users()

    async def list_users(self) -> list[dict]:
        return await self.db.list_users()

    async def create_session(self, token_hash: str, user_id: str, expires_at: datetime) -> None:
        await self.db.create_session(token_hash, user_id, expires_at)

    async def get_session(self, token_hash: str) -> dict | None:
        return await self.db.get_session(token_hash)

    async def delete_session(self, token_hash: str) -> bool:
        return await self.db.delete_session(token_hash)

    async def delete_expired_sessions(self) -> int:
        return await self.db.delete_expired_sessions()

    # Schedule methods
    async def save_schedule(self, schedule: Schedule):
        await self.db.save_schedule(schedule)

    async def get_schedule(self, schedule_id: str) -> Schedule | None:
        return await self.db.get_schedule(schedule_id)

    async def list_schedules(self, profile_id: str | None = None) -> list[Schedule]:
        return await self.db.list_schedules(profile_id)

    async def delete_schedule(self, schedule_id: str) -> bool:
        return await self.db.delete_schedule(schedule_id)

    async def log_schedule_run(self, run: ScheduleRun) -> ScheduleRun:
        return await self.db.log_schedule_run(run)

    async def list_schedule_runs(self, schedule_id: str, limit: int = 20) -> list[ScheduleRun]:
        return await self.db.list_schedule_runs(schedule_id, limit)

    async def list_cloud_accounts(self, user_id: str) -> list[dict]: return await self.db.list_cloud_accounts(user_id)
    async def list_cloud_workspaces(self, user_id: str) -> list[dict]: return await self.db.list_cloud_workspaces(user_id)
    async def create_cloud_workspace(self, user_id: str, name: str, workspace_type: str = "personal") -> dict: return await self.db.create_cloud_workspace(user_id, name, workspace_type)
    async def list_workspace_api_keys(self, workspace_id: str) -> list[dict]: return await self.db.list_workspace_api_keys(workspace_id)
    async def create_workspace_api_key(self, *args, **kwargs) -> dict: return await self.db.create_workspace_api_key(*args, **kwargs)
    async def get_workspace_api_key_by_hash(self, key_hash: str) -> dict | None: return await self.db.get_workspace_api_key_by_hash(key_hash)
    async def revoke_workspace_api_key(self, workspace_id: str, key_id: str) -> bool: return await self.db.revoke_workspace_api_key(workspace_id, key_id)
    async def touch_workspace_api_key(self, key_id: str) -> None: return await self.db.touch_workspace_api_key(key_id)
    async def register_device(self, *args, **kwargs) -> dict: return await self.db.register_device(*args, **kwargs)
    async def list_devices(self, account_id: str) -> list[dict]: return await self.db.list_devices(account_id)
    async def revoke_device(self, account_id: str, device_id: str) -> bool: return await self.db.revoke_device(account_id, device_id)
    async def upsert_cloud_sync_record(self, *args, **kwargs) -> dict: return await self.db.upsert_cloud_sync_record(*args, **kwargs)
    async def list_cloud_sync_records(self, *args, **kwargs) -> dict: return await self.db.list_cloud_sync_records(*args, **kwargs)
    async def build_profile_cloud_metadata(self, *args, **kwargs) -> dict | None: return await self.db.build_profile_cloud_metadata(*args, **kwargs)
    async def sync_workspace_profiles(self, workspace_id: str) -> dict: return await self.db.sync_workspace_profiles(workspace_id)


    async def trash_profile(self, profile_id: str, deleted_by: str | None = None) -> dict | None:
        """Soft-delete a profile into the local trash, retaining enough metadata to restore it."""
        profile = await self.get_profile(profile_id)
        if not profile:
            return None
        workspace = await self.ensure_default_workspace()
        existing = self._connection.execute("SELECT 1 FROM profile_trash WHERE profile_id = ?", (profile_id,)).fetchone()
        if existing:
            return dict(self._connection.execute("SELECT * FROM profile_trash WHERE profile_id = ?", (profile_id,)).fetchone())

        ops = await self.get_profile_operations(profile_id)
        safe_profile = profile.model_dump(mode="json")
        if safe_profile.get("proxy"):
            proxy = safe_profile["proxy"]
            if proxy.get("password"):
                proxy["password"] = encrypt(proxy["password"])
            if proxy.get("username"):
                proxy["username"] = encrypt(proxy["username"])
        tags = [dict(r) for r in self._connection.execute(
            "SELECT t.id, t.name FROM profile_tags pt JOIN tags t ON t.id = pt.tag_id WHERE pt.profile_id = ?", (profile_id,)
        ).fetchall()]
        original = profile.storage_path
        trashed = None
        if original:
            trashed = str(Path(original).parent / "trash" / Path(original).name)
        self._connection.execute(
            "INSERT INTO profile_trash (profile_id, workspace_id, profile_json, operations_json, tags_json, original_storage_path, trashed_storage_path, deleted_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (profile_id, workspace, json.dumps(safe_profile), json.dumps(ops), json.dumps(tags), original, trashed, deleted_by),
        )
        self._connection.execute("DELETE FROM schedule_runs WHERE schedule_id IN (SELECT id FROM schedules WHERE profile_id = ?)", (profile_id,))
        self._connection.execute("DELETE FROM schedules WHERE profile_id = ?", (profile_id,))
        self._connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        self._connection.commit()
        return dict(self._connection.execute("SELECT * FROM profile_trash WHERE profile_id = ?", (profile_id,)).fetchone())

    async def _get_profile_trash_record(self, profile_id: str) -> dict | None:
        workspace=await self.ensure_default_workspace()
        row=self._connection.execute("SELECT * FROM profile_trash WHERE profile_id=? AND workspace_id=?", (profile_id,workspace)).fetchone()
        return dict(row) if row else None

    async def list_profile_trash(self) -> list[dict]:
        workspace = await self.ensure_default_workspace()
        rows=self._connection.execute("SELECT profile_id, workspace_id, profile_json, operations_json, tags_json, original_storage_path, trashed_storage_path, deleted_by, deleted_at FROM profile_trash WHERE workspace_id = ? ORDER BY deleted_at DESC", (workspace,)).fetchall()
        result=[]
        for row in rows:
            item=dict(row)
            profile=json.loads(item.pop('profile_json'))
            ops=json.loads(item.pop('operations_json'))
            tags=json.loads(item.pop('tags_json'))
            item['name']=profile.get('name')
            item['status']=profile.get('status')
            item['tags']=tags
            item['owner_id']=ops.get('owner_id')
            item['assigned_user_id']=ops.get('assigned_user_id')
            result.append(item)
        return result

    async def restore_profile_from_trash(self, profile_id: str) -> Profile | None:
        workspace = await self.ensure_default_workspace()
        row=self._connection.execute("SELECT * FROM profile_trash WHERE profile_id = ? AND workspace_id = ?", (profile_id, workspace)).fetchone()
        if not row:
            return None
        item=dict(row)
        profile_data=json.loads(item['profile_json'])
        if profile_data.get('proxy'):
            proxy=profile_data['proxy']
            if proxy.get('password'): proxy['password']=decrypt(proxy['password'])
            if proxy.get('username'): proxy['username']=decrypt(proxy['username'])
        profile_data['storage_path']=item['original_storage_path']
        profile=Profile(**profile_data)
        await self.save_profile(profile)
        self._connection.execute("INSERT OR IGNORE INTO profile_workspaces (profile_id, workspace_id) VALUES (?, ?)", (profile.id, workspace))
        ops=json.loads(item['operations_json'])
        if any(ops.get(k) for k in ('owner_id','assigned_user_id','proxy_pool_id','proxy_id')):
            self._connection.execute("INSERT INTO profile_assignments (profile_id, workspace_id, owner_id, assigned_user_id, proxy_pool_id, proxy_id) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(profile_id) DO UPDATE SET workspace_id=excluded.workspace_id, owner_id=excluded.owner_id, assigned_user_id=excluded.assigned_user_id, proxy_pool_id=excluded.proxy_pool_id, proxy_id=excluded.proxy_id, updated_at=CURRENT_TIMESTAMP", (profile.id,workspace,ops.get('owner_id'),ops.get('assigned_user_id'),ops.get('proxy_pool_id'),ops.get('proxy_id')))
        for tag in json.loads(item['tags_json']):
            if self._connection.execute("SELECT 1 FROM tags WHERE id = ? AND workspace_id = ?", (tag['id'],workspace)).fetchone():
                self._connection.execute("INSERT OR IGNORE INTO profile_tags (profile_id, tag_id) VALUES (?, ?)", (profile.id,tag['id']))
        self._connection.execute("DELETE FROM profile_trash WHERE profile_id = ?", (profile_id,))
        self._connection.commit()
        return profile

    async def permanently_delete_trash(self, profile_id: str) -> bool:
        workspace=await self.ensure_default_workspace()
        cur=self._connection.execute("DELETE FROM profile_trash WHERE profile_id = ? AND workspace_id = ?", (profile_id,workspace))
        self._connection.commit()
        return cur.rowcount > 0

    async def bulk_create_proxy_inventory(self, rows: list[dict]) -> dict:
        workspace=await self.ensure_default_workspace()
        created=[]; failed=[]
        for idx,data in enumerate(rows, start=1):
            try:
                data=dict(data); data['workspace_id']=workspace
                if not data.get('name'): data['name']=f"Proxy {idx:04d}"
                if data.get('pool_id') and not self._connection.execute("SELECT 1 FROM proxy_pools WHERE id=? AND workspace_id=?", (data['pool_id'],workspace)).fetchone():
                    raise ValueError('Pool does not belong to this workspace')
                proxy_id=f"px-{uuid.uuid4().hex[:12]}"
                username=encrypt(data['username']) if data.get('username') else None
                password=encrypt(data['password']) if data.get('password') else None
                self._connection.execute("INSERT INTO proxy_inventory (id,workspace_id,name,proxy_type,server,username,password,provider,country,pool_id) VALUES (?,?,?,?,?,?,?,?,?,?)", (proxy_id,workspace,data['name'],data.get('proxy_type','http'),data['server'],username,password,data.get('provider'),data.get('country'),data.get('pool_id')))
                created.append(proxy_id)
            except Exception as exc:
                failed.append({'line': idx, 'error': str(exc)})
        self._connection.commit()
        result=[]
        for pid in created:
            item=await self.get_proxy_inventory(pid)
            if item: result.append(item)
        return {'created': len(result), 'failed': failed, 'proxies': result}

    async def close(self):
        """Close the database."""
        await self.db.close()
