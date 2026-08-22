from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4


AUTH_ROLES = ("Admin", "Operator", "Viewer")
SESSION_COOKIE_NAME = "__Host-portfolio_session"
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 256
SESSION_ABSOLUTE_HOURS = 8
SESSION_IDLE_MINUTES = 30
API_TOKEN_HOURS = 8
API_ACCESS_MODES = ("disabled", "read_only", "read_write")
_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 3
_SCRYPT_DKLEN = 32
_SCRYPT_MAXMEM = 64 * 1024 * 1024
_DUMMY_PASSWORD_HASH = (
    "scrypt$32768$8$3$cG9ydGZvbGlvLWF1dGgtZA$"
    "HX8zEuK2ChL18V-M00s2J6K55tpME6SiFgSuyGmxVFY"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _now()).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def validate_password(password: Any) -> str:
    value = password if isinstance(password, str) else ""
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters")
    return value


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=_SCRYPT_MAXMEM,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(password: Any, encoded: str) -> bool:
    value = password if isinstance(password, str) else ""
    if len(value) > PASSWORD_MAX_LENGTH:
        return False
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        derived = hashlib.scrypt(
            value.encode("utf-8"),
            salt=_b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_b64decode(expected)),
            maxmem=_SCRYPT_MAXMEM,
        )
        return hmac.compare_digest(derived, _b64decode(expected))
    except (TypeError, ValueError):
        return False


def _clean_name(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    if len(text) > 80:
        raise ValueError(f"{label} must be at most 80 characters")
    return text


def _clean_username(value: Any) -> str:
    username = str(value or "").strip()
    if not _USERNAME_PATTERN.fullmatch(username):
        raise ValueError("Username must be 3-64 characters using letters, numbers, dots, dashes, or underscores")
    return username


def _clean_role(value: Any) -> str:
    candidate = str(value or "").strip().casefold()
    role = next((item for item in AUTH_ROLES if item.casefold() == candidate), "")
    if not role:
        raise ValueError("Role must be Admin, Operator, or Viewer")
    return role


class AuthStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys=on")
        connection.execute("pragma busy_timeout=30000")
        return connection

    def initialize(self) -> None:
        with self._lock:
            with self._connect() as connection:
                connection.execute("pragma journal_mode=wal")
                connection.execute(
                    """
                    create table if not exists app_users (
                        id text primary key,
                        first_name text not null,
                        last_name text not null,
                        username text not null collate nocase unique,
                        password_hash text not null,
                        role text not null check(role in ('Admin', 'Operator', 'Viewer')),
                        enabled integer not null default 1,
                        must_change_password integer not null default 1,
                        created_at text not null,
                        updated_at text not null,
                        last_login_at text not null default ''
                    )
                    """
                )
                connection.execute(
                    """
                    create table if not exists auth_sessions (
                        token_hash text primary key,
                        user_id text not null references app_users(id) on delete cascade,
                        csrf_token text not null,
                        created_at text not null,
                        last_seen_at text not null,
                        expires_at text not null
                    )
                    """
                )
                connection.execute("create index if not exists idx_auth_sessions_user on auth_sessions(user_id)")
                connection.execute("create index if not exists idx_auth_sessions_expiry on auth_sessions(expires_at)")
                connection.execute(
                    """
                    create table if not exists api_tokens (
                        token_hash text primary key,
                        user_id text not null references app_users(id) on delete cascade,
                        service text not null default 'rest',
                        created_at text not null,
                        last_used_at text not null,
                        expires_at text not null
                    )
                    """
                )
                connection.execute("create index if not exists idx_api_tokens_user on api_tokens(user_id)")
                connection.execute("create index if not exists idx_api_tokens_expiry on api_tokens(expires_at)")
                connection.execute(
                    """
                    create table if not exists api_access_settings (
                        singleton integer primary key check(singleton = 1),
                        mode text not null check(mode in ('disabled', 'read_only', 'read_write')),
                        mcp_mode text not null default 'disabled' check(mcp_mode in ('disabled', 'read_only', 'read_write')),
                        updated_at text not null
                    )
                    """
                )
                token_columns = {str(row["name"]) for row in connection.execute("pragma table_info(api_tokens)")}
                if "service" not in token_columns:
                    connection.execute("alter table api_tokens add column service text not null default 'rest'")
                access_columns = {str(row["name"]) for row in connection.execute("pragma table_info(api_access_settings)")}
                if "mcp_mode" not in access_columns:
                    connection.execute("alter table api_access_settings add column mcp_mode text not null default 'disabled'")
                connection.execute("create index if not exists idx_api_tokens_service on api_tokens(service)")
                connection.execute(
                    "insert or ignore into api_access_settings (singleton, mode, mcp_mode, updated_at) values (1, 'disabled', 'disabled', ?)",
                    (_timestamp(),),
                )
                if connection.execute("select count(*) from app_users").fetchone()[0] == 0:
                    timestamp = _timestamp()
                    connection.execute(
                        """
                        insert into app_users
                          (id, first_name, last_name, username, password_hash, role, enabled,
                           must_change_password, created_at, updated_at, last_login_at)
                        values (?, ?, ?, ?, ?, 'Admin', 1, 1, ?, ?, '')
                        """,
                        (
                            str(uuid4()),
                            "System",
                            "Administrator",
                            "admin",
                            hash_password("admin"),
                            timestamp,
                            timestamp,
                        ),
                    )
            self._initialized = True

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.initialize()

    @staticmethod
    def _user_out(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "first_name": str(row["first_name"]),
            "last_name": str(row["last_name"]),
            "username": str(row["username"]),
            "role": str(row["role"]),
            "enabled": bool(row["enabled"]),
            "must_change_password": bool(row["must_change_password"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "last_login_at": str(row["last_login_at"]),
        }

    def list_users(self) -> list[dict[str, Any]]:
        self._ensure_initialized()
        with self._connect() as connection:
            rows = connection.execute(
                """
                select * from app_users
                order by case role when 'Admin' then 1 when 'Operator' then 2 else 3 end,
                         username collate nocase
                """
            ).fetchall()
        return [self._user_out(row) for row in rows]

    def create_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_initialized()
        first_name = _clean_name(payload.get("first_name"), "First Name")
        last_name = _clean_name(payload.get("last_name"), "Last Name")
        username = _clean_username(payload.get("username"))
        role = _clean_role(payload.get("role"))
        password = validate_password(payload.get("password"))
        timestamp = _timestamp()
        user_id = str(uuid4())
        try:
            with self._lock, self._connect() as connection:
                connection.execute(
                    """
                    insert into app_users
                      (id, first_name, last_name, username, password_hash, role, enabled,
                       must_change_password, created_at, updated_at, last_login_at)
                    values (?, ?, ?, ?, ?, ?, 1, 1, ?, ?, '')
                    """,
                    (user_id, first_name, last_name, username, hash_password(password), role, timestamp, timestamp),
                )
                row = connection.execute("select * from app_users where id = ?", (user_id,)).fetchone()
        except sqlite3.IntegrityError as exc:
            if "username" in str(exc).lower() or "unique" in str(exc).lower():
                raise ValueError("Username already exists") from exc
            raise
        return self._user_out(row)

    def _enabled_admin_count(self, connection: sqlite3.Connection) -> int:
        return int(
            connection.execute("select count(*) from app_users where role = 'Admin' and enabled = 1").fetchone()[0]
        )

    def set_user_enabled(self, user_id: str, enabled: bool, actor_user_id: str) -> dict[str, Any]:
        self._ensure_initialized()
        with self._lock, self._connect() as connection:
            row = connection.execute("select * from app_users where id = ?", (user_id,)).fetchone()
            if not row:
                raise LookupError("User not found")
            if not enabled and user_id == actor_user_id:
                raise ValueError("You cannot disable your own account")
            if not enabled and row["role"] == "Admin" and row["enabled"] and self._enabled_admin_count(connection) <= 1:
                raise ValueError("At least one enabled Admin is required")
            connection.execute(
                "update app_users set enabled = ?, updated_at = ? where id = ?",
                (int(enabled), _timestamp(), user_id),
            )
            if not enabled:
                connection.execute("delete from auth_sessions where user_id = ?", (user_id,))
                connection.execute("delete from api_tokens where user_id = ?", (user_id,))
            updated = connection.execute("select * from app_users where id = ?", (user_id,)).fetchone()
        return self._user_out(updated)

    def delete_user(self, user_id: str, actor_user_id: str) -> None:
        self._ensure_initialized()
        with self._lock, self._connect() as connection:
            row = connection.execute("select * from app_users where id = ?", (user_id,)).fetchone()
            if not row:
                raise LookupError("User not found")
            if user_id == actor_user_id:
                raise ValueError("You cannot delete your own account")
            if row["role"] == "Admin" and row["enabled"] and self._enabled_admin_count(connection) <= 1:
                raise ValueError("At least one enabled Admin is required")
            connection.execute("delete from app_users where id = ?", (user_id,))

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _create_session(self, connection: sqlite3.Connection, user_id: str) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(24)
        now = _now()
        connection.execute(
            """
            insert into auth_sessions
              (token_hash, user_id, csrf_token, created_at, last_seen_at, expires_at)
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                self._token_hash(token),
                user_id,
                csrf_token,
                _timestamp(now),
                _timestamp(now),
                _timestamp(now + timedelta(hours=SESSION_ABSOLUTE_HOURS)),
            ),
        )
        return token, csrf_token

    def integration_access(self) -> dict[str, dict[str, Any]]:
        self._ensure_initialized()
        now = _timestamp()
        with self._lock, self._connect() as connection:
            connection.execute("delete from api_tokens where expires_at <= ?", (now,))
            row = connection.execute("select mode, mcp_mode, updated_at from api_access_settings where singleton = 1").fetchone()
            token_counts = {
                str(item["service"]): int(item["count"])
                for item in connection.execute(
                    "select service, count(*) as count from api_tokens group by service"
                ).fetchall()
            }
        updated_at = str(row["updated_at"] if row else "")

        def service_state(service: str, mode: str, endpoint: str) -> dict[str, Any]:
            return {
                "service": service,
                "mode": mode,
                "enabled": mode != "disabled",
                "write_enabled": mode == "read_write",
                "token_ttl_seconds": API_TOKEN_HOURS * 60 * 60,
                "active_tokens": token_counts.get(service, 0),
                "endpoint": endpoint,
                "updated_at": updated_at,
            }

        return {
            "rest": service_state("rest", str(row["mode"] if row else "disabled"), "/api"),
            "mcp": service_state("mcp", str(row["mcp_mode"] if row else "disabled"), "/mcp/"),
        }

    def api_access(self) -> dict[str, Any]:
        return self.integration_access()["rest"]

    def mcp_access(self) -> dict[str, Any]:
        return self.integration_access()["mcp"]

    @staticmethod
    def _clean_access_mode(mode: Any) -> str:
        clean_mode = str(mode or "").strip().lower()
        if clean_mode not in API_ACCESS_MODES:
            raise ValueError("Access mode must be disabled, read_only, or read_write")
        return clean_mode

    def set_integration_access_modes(self, rest_mode: Any, mcp_mode: Any) -> dict[str, dict[str, Any]]:
        self._ensure_initialized()
        clean_rest_mode = self._clean_access_mode(rest_mode)
        clean_mcp_mode = self._clean_access_mode(mcp_mode)
        with self._lock, self._connect() as connection:
            connection.execute(
                "update api_access_settings set mode = ?, mcp_mode = ?, updated_at = ? where singleton = 1",
                (clean_rest_mode, clean_mcp_mode, _timestamp()),
            )
            if clean_rest_mode == "disabled":
                connection.execute("delete from api_tokens where service = 'rest'")
            if clean_mcp_mode == "disabled":
                connection.execute("delete from api_tokens where service = 'mcp'")
        return self.integration_access()

    def set_api_access_mode(self, mode: Any) -> dict[str, Any]:
        self._ensure_initialized()
        clean_mode = self._clean_access_mode(mode)
        with self._lock, self._connect() as connection:
            connection.execute(
                "update api_access_settings set mode = ?, updated_at = ? where singleton = 1",
                (clean_mode, _timestamp()),
            )
            if clean_mode == "disabled":
                connection.execute("delete from api_tokens where service = 'rest'")
        return self.api_access()

    def set_mcp_access_mode(self, mode: Any) -> dict[str, Any]:
        self._ensure_initialized()
        clean_mode = self._clean_access_mode(mode)
        with self._lock, self._connect() as connection:
            connection.execute(
                "update api_access_settings set mcp_mode = ?, updated_at = ? where singleton = 1",
                (clean_mode, _timestamp()),
            )
            if clean_mode == "disabled":
                connection.execute("delete from api_tokens where service = 'mcp'")
        return self.mcp_access()

    def create_api_token(self, username: Any, password: Any, service: str = "rest") -> tuple[dict[str, Any], str, datetime]:
        self._ensure_initialized()
        clean_service = str(service or "rest").strip().lower()
        if clean_service not in {"rest", "mcp"}:
            raise ValueError("Token service must be rest or mcp")
        candidate = str(username or "").strip()[:64]
        now = _now()
        with self._lock, self._connect() as connection:
            row = connection.execute("select * from app_users where username = ? collate nocase", (candidate,)).fetchone()
            valid_password = verify_password(password, row["password_hash"] if row else _DUMMY_PASSWORD_HASH)
            if not row or not valid_password or not row["enabled"]:
                raise ValueError("Invalid username or password")
            if row["must_change_password"]:
                raise PermissionError("Change the temporary password in the dashboard before creating an API token")
            connection.execute("delete from api_tokens where expires_at <= ?", (_timestamp(now),))
            token = secrets.token_urlsafe(40)
            expires_at = now + timedelta(hours=API_TOKEN_HOURS)
            connection.execute(
                """
                insert into api_tokens (token_hash, user_id, service, created_at, last_used_at, expires_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    self._token_hash(token),
                    row["id"],
                    clean_service,
                    _timestamp(now),
                    _timestamp(now),
                    _timestamp(expires_at),
                ),
            )
            connection.execute("update app_users set last_login_at = ? where id = ?", (_timestamp(now), row["id"]))
            updated = connection.execute("select * from app_users where id = ?", (row["id"],)).fetchone()
        return self._user_out(updated), token, expires_at

    def api_token(self, token: Any, service: str | None = None) -> dict[str, Any] | None:
        self._ensure_initialized()
        clean_service = str(service or "").strip().lower()
        if clean_service and clean_service not in {"rest", "mcp"}:
            return None
        raw_token = str(token or "")
        if not raw_token or len(raw_token) > 512:
            return None
        token_hash = self._token_hash(raw_token)
        now = _now()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                select t.token_hash, t.service, t.created_at as token_created_at, t.last_used_at,
                       t.expires_at, u.*
                from api_tokens t
                join app_users u on u.id = t.user_id
                where t.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if not row:
                return None
            if clean_service and str(row["service"]) != clean_service:
                return None
            expires_at = _parse_timestamp(row["expires_at"])
            if not row["enabled"] or not expires_at or expires_at <= now:
                connection.execute("delete from api_tokens where token_hash = ?", (token_hash,))
                return None
            last_used_at = _parse_timestamp(row["last_used_at"])
            if not last_used_at or now - last_used_at >= timedelta(minutes=1):
                connection.execute(
                    "update api_tokens set last_used_at = ? where token_hash = ?",
                    (_timestamp(now), token_hash),
                )
        return {
            "user": self._user_out(row),
            "token_hash": token_hash,
            "service": str(row["service"]),
            "expires_at": str(row["expires_at"]),
        }

    def revoke_api_token(self, token: Any) -> None:
        self._ensure_initialized()
        raw_token = str(token or "")
        if not raw_token or len(raw_token) > 512:
            return
        with self._lock, self._connect() as connection:
            connection.execute("delete from api_tokens where token_hash = ?", (self._token_hash(raw_token),))

    def authenticate(self, username: Any, password: Any) -> tuple[dict[str, Any], str, str]:
        self._ensure_initialized()
        candidate = str(username or "").strip()[:64]
        with self._lock, self._connect() as connection:
            row = connection.execute("select * from app_users where username = ? collate nocase", (candidate,)).fetchone()
            valid_password = verify_password(password, row["password_hash"] if row else _DUMMY_PASSWORD_HASH)
            if not row or not valid_password or not row["enabled"]:
                raise ValueError("Invalid username or password")
            connection.execute("delete from auth_sessions where expires_at <= ?", (_timestamp(),))
            token, csrf_token = self._create_session(connection, row["id"])
            connection.execute(
                "update app_users set last_login_at = ?, updated_at = updated_at where id = ?",
                (_timestamp(), row["id"]),
            )
            updated = connection.execute("select * from app_users where id = ?", (row["id"],)).fetchone()
        return self._user_out(updated), token, csrf_token

    def session(self, token: Any) -> dict[str, Any] | None:
        self._ensure_initialized()
        raw_token = str(token or "")
        if not raw_token:
            return None
        token_hash = self._token_hash(raw_token)
        now = _now()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                select s.token_hash, s.csrf_token, s.created_at as session_created_at,
                       s.last_seen_at, s.expires_at, u.*
                from auth_sessions s
                join app_users u on u.id = s.user_id
                where s.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if not row:
                return None
            expires_at = _parse_timestamp(row["expires_at"])
            last_seen_at = _parse_timestamp(row["last_seen_at"])
            idle_deadline = last_seen_at + timedelta(minutes=SESSION_IDLE_MINUTES) if last_seen_at else None
            if not row["enabled"] or not expires_at or expires_at <= now or not idle_deadline or idle_deadline <= now:
                connection.execute("delete from auth_sessions where token_hash = ?", (token_hash,))
                return None
            if now - last_seen_at >= timedelta(minutes=1):
                connection.execute(
                    "update auth_sessions set last_seen_at = ? where token_hash = ?",
                    (_timestamp(now), token_hash),
                )
        return {
            "user": self._user_out(row),
            "csrf_token": str(row["csrf_token"]),
            "token_hash": token_hash,
        }

    def logout(self, token: Any) -> None:
        self._ensure_initialized()
        raw_token = str(token or "")
        if not raw_token:
            return
        with self._lock, self._connect() as connection:
            connection.execute("delete from auth_sessions where token_hash = ?", (self._token_hash(raw_token),))

    def change_password(
        self,
        user_id: str,
        current_password: Any,
        new_password: Any,
    ) -> tuple[dict[str, Any], str, str]:
        self._ensure_initialized()
        password = validate_password(new_password)
        with self._lock, self._connect() as connection:
            row = connection.execute("select * from app_users where id = ?", (user_id,)).fetchone()
            if not row or not row["enabled"]:
                raise LookupError("User not found")
            if not verify_password(current_password, row["password_hash"]):
                raise ValueError("Current password is incorrect")
            if verify_password(password, row["password_hash"]):
                raise ValueError("New password must be different from the current password")
            connection.execute(
                """
                update app_users
                set password_hash = ?, must_change_password = 0, updated_at = ?
                where id = ?
                """,
                (hash_password(password), _timestamp(), user_id),
            )
            connection.execute("delete from auth_sessions where user_id = ?", (user_id,))
            connection.execute("delete from api_tokens where user_id = ?", (user_id,))
            token, csrf_token = self._create_session(connection, user_id)
            updated = connection.execute("select * from app_users where id = ?", (user_id,)).fetchone()
        return self._user_out(updated), token, csrf_token

    def reset_admin_password(self, username: Any, new_password: Any) -> dict[str, Any]:
        """Set a temporary password for an existing Admin and revoke their sessions."""
        self._ensure_initialized()
        candidate = str(username or "").strip()[:64]
        password = validate_password(new_password)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "select * from app_users where username = ? collate nocase",
                (candidate,),
            ).fetchone()
            if not row or row["role"] != "Admin":
                raise LookupError("Admin user not found")
            if verify_password(password, row["password_hash"]):
                raise ValueError("New password must be different from the current password")
            connection.execute(
                """
                update app_users
                set password_hash = ?, must_change_password = 1, updated_at = ?
                where id = ?
                """,
                (hash_password(password), _timestamp(), row["id"]),
            )
            connection.execute("delete from auth_sessions where user_id = ?", (row["id"],))
            connection.execute("delete from api_tokens where user_id = ?", (row["id"],))
            updated = connection.execute("select * from app_users where id = ?", (row["id"],)).fetchone()
        return self._user_out(updated)

    def clear_sessions(self) -> None:
        self._ensure_initialized()
        with self._lock, self._connect() as connection:
            connection.execute("delete from auth_sessions")
            connection.execute("delete from api_tokens")
