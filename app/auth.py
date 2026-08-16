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
            token, csrf_token = self._create_session(connection, user_id)
            updated = connection.execute("select * from app_users where id = ?", (user_id,)).fetchone()
        return self._user_out(updated), token, csrf_token

    def clear_sessions(self) -> None:
        self._ensure_initialized()
        with self._lock, self._connect() as connection:
            connection.execute("delete from auth_sessions")
