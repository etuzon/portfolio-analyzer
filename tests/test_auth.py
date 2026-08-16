import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import main
from app.auth import PASSWORD_MIN_LENGTH, SESSION_COOKIE_NAME, AuthStore, verify_password
from app.local_portfolio import LocalPortfolioStore


def _auth_environment(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    auth = AuthStore(store.path)
    auth.initialize()
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    main._login_failures.clear()
    return auth


def _client():
    return TestClient(main.app, base_url="https://localhost:6443")


def _login(client, username="admin", password="admin"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def _change_password(client, auth_payload, current_password, new_password):
    response = client.post(
        "/api/auth/change-password",
        headers={"X-CSRF-Token": auth_payload["csrf_token"]},
        json={
            "current_password": current_password,
            "new_password": new_password,
            "confirm_password": new_password,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_existing_database_is_migrated_with_hashed_default_admin(tmp_path):
    database = tmp_path / "existing.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("create table sentinel (value text not null)")
        connection.execute("insert into sentinel values ('preserved')")

    auth = AuthStore(database)
    auth.initialize()

    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        admin = connection.execute("select * from app_users where username = 'admin'").fetchone()
        assert connection.execute("select value from sentinel").fetchone()[0] == "preserved"
    assert admin["password_hash"] != "admin"
    assert "admin" not in admin["password_hash"]
    assert verify_password("admin", admin["password_hash"])
    assert admin["role"] == "Admin"
    assert admin["enabled"] == 1
    assert admin["must_change_password"] == 1


def test_default_admin_must_change_password_before_using_portfolio(tmp_path, monkeypatch):
    auth = _auth_environment(tmp_path, monkeypatch)
    client = _client()

    anonymous = client.get("/api/about")
    assert anonymous.status_code == 401
    assert anonymous.json()["detail"]["code"] == "authentication_required"

    signed_in = _login(client)
    cookie = client.cookies.get(SESSION_COOKIE_NAME)
    assert signed_in["user"]["must_change_password"] is True
    assert cookie
    assert auth.session(cookie)
    cookie_client = _client()
    set_cookie = cookie_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    ).headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=strict" in set_cookie

    blocked = client.get("/api/about")
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "password_change_required"

    no_csrf = client.post(
        "/api/auth/change-password",
        json={"current_password": "admin", "new_password": "new-admin-password", "confirm_password": "new-admin-password"},
    )
    assert no_csrf.status_code == 403
    assert no_csrf.json()["detail"]["code"] == "csrf_failed"

    changed = _change_password(client, signed_in, "admin", "new-admin-password")
    assert changed["user"]["must_change_password"] is False
    assert client.get("/api/about").status_code == 200

    logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": changed["csrf_token"]})
    assert logout.status_code == 200
    assert client.get("/api/about").status_code == 401


def test_admin_operator_and_viewer_permissions_are_enforced_server_side(tmp_path, monkeypatch):
    auth = _auth_environment(tmp_path, monkeypatch)
    admin_client = _client()
    admin_auth = _change_password(admin_client, _login(admin_client), "admin", "new-admin-password")

    operator_password = "operator-password"
    viewer_password = "viewer-password-1"
    for payload in [
        {"first_name": "Opal", "last_name": "Operator", "username": "operator", "password": operator_password, "role": "Operator"},
        {"first_name": "Vera", "last_name": "Viewer", "username": "viewer", "password": viewer_password, "role": "Viewer"},
    ]:
        response = admin_client.post(
            "/api/auth/users",
            headers={"X-CSRF-Token": admin_auth["csrf_token"]},
            json=payload,
        )
        assert response.status_code == 200, response.text
        assert "password" not in response.json()

    operator_client = _client()
    operator_auth = _change_password(
        operator_client,
        _login(operator_client, "operator", operator_password),
        operator_password,
        "operator-password-new",
    )
    operator_write = operator_client.put(
        "/api/settings/client-state",
        headers={"X-CSRF-Token": operator_auth["csrf_token"]},
        json={"language": "en"},
    )
    assert operator_write.status_code == 200
    assert operator_client.get("/api/auth/users").status_code == 403

    viewer_client = _client()
    viewer_auth = _change_password(
        viewer_client,
        _login(viewer_client, "viewer", viewer_password),
        viewer_password,
        "viewer-password-new",
    )
    assert viewer_client.get("/api/about").status_code == 200
    viewer_write = viewer_client.put(
        "/api/settings/client-state",
        headers={"X-CSRF-Token": viewer_auth["csrf_token"]},
        json={"language": "he"},
    )
    assert viewer_write.status_code == 403
    assert viewer_write.json()["detail"]["code"] == "read_only"
    assert viewer_client.get("/api/auth/users").status_code == 403
    assert viewer_client.get("/api/local/backups").status_code == 403

    viewer = next(user for user in auth.list_users() if user["username"] == "viewer")
    invalid_status = admin_client.put(
        f"/api/auth/users/{viewer['id']}/status",
        headers={"X-CSRF-Token": admin_auth["csrf_token"]},
        json={"enabled": "false"},
    )
    assert invalid_status.status_code == 400
    disabled = admin_client.put(
        f"/api/auth/users/{viewer['id']}/status",
        headers={"X-CSRF-Token": admin_auth["csrf_token"]},
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert viewer_client.get("/api/about").status_code == 401


def test_user_validation_and_last_admin_guards(tmp_path):
    auth = AuthStore(tmp_path / "auth.sqlite3")
    auth.initialize()
    admin = auth.list_users()[0]

    try:
        auth.create_user(
            {
                "first_name": "Short",
                "last_name": "Password",
                "username": "short-password",
                "password": "seven77",
                "role": "Viewer",
            }
        )
        assert False, "short password should be rejected"
    except ValueError as exc:
        assert str(PASSWORD_MIN_LENGTH) in str(exc)

    exactly_minimum = auth.create_user(
        {
            "first_name": "Eight",
            "last_name": "Characters",
            "username": "eight-characters",
            "password": "eight888",
            "role": "Viewer",
        }
    )
    assert exactly_minimum["username"] == "eight-characters"

    auth.create_user(
        {
            "first_name": "Case",
            "last_name": "Sensitive",
            "username": "Case.User",
            "password": "case-user-password",
            "role": "Viewer",
        }
    )
    try:
        auth.create_user(
            {
                "first_name": "Duplicate",
                "last_name": "Username",
                "username": "case.user",
                "password": "duplicate-password",
                "role": "Viewer",
            }
        )
        assert False, "case-insensitive duplicate username should be rejected"
    except ValueError as exc:
        assert "already exists" in str(exc)

    try:
        auth.set_user_enabled(admin["id"], False, "different-admin-id")
        assert False, "last enabled admin should not be disabled"
    except ValueError as exc:
        assert "one enabled Admin" in str(exc)


def test_expired_session_is_rejected_and_removed(tmp_path):
    auth = AuthStore(tmp_path / "auth.sqlite3")
    auth.initialize()
    _user, token, _csrf = auth.authenticate("admin", "admin")
    expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(auth.path) as connection:
        connection.execute("update auth_sessions set expires_at = ?", (expired,))

    assert auth.session(token) is None
    with sqlite3.connect(auth.path) as connection:
        assert connection.execute("select count(*) from auth_sessions").fetchone()[0] == 0


def test_session_secret_is_hashed_and_portable_export_excludes_credentials(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    auth = AuthStore(store.path)
    auth.initialize()
    _user, token, _csrf = auth.authenticate("admin", "admin")

    with sqlite3.connect(store.path) as connection:
        stored_token = connection.execute("select token_hash from auth_sessions").fetchone()[0]
        assert stored_token == hashlib.sha256(token.encode("utf-8")).hexdigest()
        assert stored_token != token

    portable = store.export_data()
    assert "app_users" not in portable["data"]
    assert "auth_sessions" not in portable["data"]

    snapshot_path = tmp_path / "snapshot.sqlite3"
    snapshot_path.write_bytes(store.sqlite_snapshot_bytes())
    with sqlite3.connect(snapshot_path) as snapshot:
        tables = {row[0] for row in snapshot.execute("select name from sqlite_master where type = 'table'")}
    assert {"app_users", "auth_sessions"} <= tables


def test_login_failures_are_rate_limited(tmp_path, monkeypatch):
    _auth_environment(tmp_path, monkeypatch)
    client = _client()

    for _ in range(main.AUTH_LOGIN_MAX_FAILURES):
        rejected = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "incorrect-password"},
        )
        assert rejected.status_code == 401

    limited = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "incorrect-password"},
    )
    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "login_rate_limited"
    assert int(limited.headers["Retry-After"]) > 0


def test_health_check_is_public_and_does_not_expose_runtime_paths(tmp_path, monkeypatch):
    _auth_environment(tmp_path, monkeypatch)
    response = _client().get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": main.__version__}
    assert "config_path" not in response.text
