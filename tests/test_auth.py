import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import admin_cli, main
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


def test_event_workflow_is_authenticated_and_available_through_assistant(tmp_path, monkeypatch):
    _auth_environment(tmp_path, monkeypatch)
    client = _client()
    path = "/api/assistant/workflows/world-event-impact"
    assert client.get(path).status_code == 401
    assert client.get(path + "/cases").status_code == 401
    assert client.get(path + "/events").status_code == 401

    session = _login(client)
    _change_password(client, session, "admin", "Workflow-Test-Password-2026!")
    response = client.get(path)
    assert response.status_code == 200
    workflow = response.json()
    catalog = client.get("/api/assistant/read-tools").json()["items"]
    entry = next(item for item in catalog if item["name"] == "get_event_impact_workflow")
    assert entry["path"] == path
    assert entry["method"] == "GET"
    assert client.get("/api/assistant/read-tools/get_event_impact_workflow").json() == workflow
    assert workflow["templates"]["probability"]["estimate_pct"] is None
    assert workflow["templates"]["forecast"]["status"] == "insufficient_evidence"

    # A response is a fresh blank template; callers cannot contaminate later cases.
    workflow["templates"]["probability"]["estimate_pct"] = 99
    assert client.get(path).json()["templates"]["probability"]["estimate_pct"] is None

    cases = client.get(path + "/cases", params={"symbol": " bbd "}).json()
    assert cases["count"] == 1
    record = cases["items"][0]
    assert record["case"]["symbol"] == "BBD"
    assert record["probabilities"][0]["estimate_pct"] is None
    assert record["learning_status"]["eligible_as_population_probability_sample"] is False
    assert client.get("/api/assistant/read-tools/get_event_impact_cases", params={"symbol": "bbd"}).json() == cases
    # A ticker is a filter, never a path chosen by the caller.
    assert client.get(path + "/cases", params={"symbol": "../../config"}).json()["items"] == []
    assert client.get(path + "/cases", params={"symbol": "UNKNOWN"}).json()["count"] == 0

    event_id = record["case"]["event_id"]
    cohort = client.get(path + "/cases", params={"event_id": event_id}).json()
    cursor = cohort["next_offset"]
    while cursor is not None:
        page = client.get(path + "/cases", params={"event_id": event_id, "offset": cursor}).json()
        cohort["items"].extend(page["items"])
        cursor = page["next_offset"]
    assert cohort["distinct_event_count"] == 1
    symbols = {item["case"]["symbol"] for item in cohort["items"]}
    assert {"BBD", "XP", "STNE", "NU", "ITUB", "PBR", "ABEV", "VALE", "SUZ"} <= symbols
    assert all(item["case"]["event_id"] == event_id for item in cohort["items"])
    assert cases["event_patterns"] == cohort["event_patterns"]
    assert cohort["event_patterns"][0]["independent_event_count"] == 1
    assert cohort["calibrated_probability_model"] is False
    assert client.get(path + "/cases", params={"symbol": "BBD", "event_id": "unrelated"}).json()["items"] == []
    assert client.get(path + "/cases", params={"event_id": "../../config"}).json()["event_patterns"] == []

    for item in cohort["items"]:
        for outcome in item["case"]["verified_outcomes"]:
            if outcome["metric"] == "stock_return":
                calculated = 100 * (outcome["end_value"] / outcome["baseline_value"] - 1)
                assert abs(outcome["change_pct"] - calculated) < 1e-7
        assert item["learning_status"]["eligible_as_population_probability_sample"] is False
    suz = next(item for item in cohort["items"] if item["case"]["symbol"] == "SUZ")
    assert suz["case"]["verified_outcomes"][0]["change_pct"] > 0

    event_index = client.get(path + "/events").json()
    assert event_index["count"] >= 9
    assert event_index["case_count"] >= 37
    assert client.get("/api/assistant/read-tools/get_event_impact_events").json() == event_index
    assert client.get(path + "/cases", params={"limit": 6}).status_code == 422
    assert client.get(path + "/cases", params={"offset": -1}).status_code == 422


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
    about = client.get("/api/about")
    assert about.status_code == 200
    assert about.json() == {"name": "Portfolio Analyzer", "version": main.__version__}

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


def test_admin_password_reset_sets_temporary_password_and_revokes_sessions(tmp_path):
    auth = AuthStore(tmp_path / "auth.sqlite3")
    auth.initialize()
    _user, token, _csrf = auth.authenticate("admin", "admin")

    reset_user = auth.reset_admin_password("ADMIN", "temporary-admin-password")

    assert reset_user["username"] == "admin"
    assert reset_user["must_change_password"] is True
    assert auth.session(token) is None
    try:
        auth.authenticate("admin", "admin")
        assert False, "old password should be rejected after reset"
    except ValueError as exc:
        assert "Invalid username or password" in str(exc)
    authenticated, _new_token, _new_csrf = auth.authenticate("admin", "temporary-admin-password")
    assert authenticated["must_change_password"] is True


def test_password_reset_rejects_non_admin_user(tmp_path):
    auth = AuthStore(tmp_path / "auth.sqlite3")
    auth.initialize()
    auth.create_user(
        {
            "first_name": "Vera",
            "last_name": "Viewer",
            "username": "viewer",
            "password": "viewer-password",
            "role": "Viewer",
        }
    )

    try:
        auth.reset_admin_password("viewer", "temporary-viewer-password")
        assert False, "non-Admin password reset should be rejected"
    except LookupError as exc:
        assert "Admin user not found" in str(exc)


def test_admin_cli_resets_password_without_accepting_it_as_an_argument(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    entered_passwords = iter(["temporary-admin-password", "temporary-admin-password"])
    monkeypatch.setattr(admin_cli.getpass, "getpass", lambda _prompt: next(entered_passwords))

    assert admin_cli.main(["reset-password", "--username", "admin"]) == 0

    output = capsys.readouterr()
    assert "Password reset for Admin 'admin'" in output.out
    assert "temporary-admin-password" not in output.out
    assert "temporary-admin-password" not in output.err
    user, _token, _csrf = AuthStore(tmp_path / "local-portfolio.sqlite3").authenticate(
        "admin", "temporary-admin-password"
    )
    assert user["must_change_password"] is True


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
    assert "api_tokens" not in portable["data"]
    assert "api_access_settings" not in portable["data"]

    snapshot_path = tmp_path / "snapshot.sqlite3"
    snapshot_path.write_bytes(store.sqlite_snapshot_bytes())
    with sqlite3.connect(snapshot_path) as snapshot:
        tables = {row[0] for row in snapshot.execute("select name from sqlite_master where type = 'table'")}
    assert {"app_users", "auth_sessions", "api_tokens", "api_access_settings"} <= tables


def test_admin_controls_api_access_and_read_only_tokens_can_self_revoke(tmp_path, monkeypatch):
    auth = _auth_environment(tmp_path, monkeypatch)
    client = _client()

    disabled = client.post("/api/auth/token", json={"username": "admin", "password": "admin"})
    assert disabled.status_code == 403
    assert disabled.json()["detail"]["code"] == "api_disabled"

    admin_session = _change_password(client, _login(client), "admin", "new-admin-password")
    enabled = client.put(
        "/api/settings/api-access",
        headers={"X-CSRF-Token": admin_session["csrf_token"]},
        json={"mode": "read_only"},
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["mode"] == "read_only"
    assert enabled.json()["write_enabled"] is False

    issued = client.post(
        "/api/auth/token",
        json={"username": "admin", "password": "new-admin-password"},
    )
    assert issued.status_code == 200, issued.text
    token_payload = issued.json()
    token = token_payload["access_token"]
    assert token_payload["token_type"] == "bearer"
    assert token_payload["scope"] == "read"
    assert token_payload["expires_in"] == 8 * 60 * 60

    with sqlite3.connect(auth.path) as connection:
        stored_hash = connection.execute("select token_hash from api_tokens").fetchone()[0]
    assert stored_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert token not in stored_hash

    bearer = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/about", headers=bearer).status_code == 200
    write = client.put("/api/settings/client-state", headers=bearer, json={"language": "he"})
    assert write.status_code == 403
    assert write.json()["detail"]["code"] == "api_read_only"

    revoked = client.delete("/api/auth/token", headers=bearer)
    assert revoked.status_code == 200
    assert revoked.json() == {"revoked": True}
    rejected = client.get("/api/about", headers=bearer)
    assert rejected.status_code == 401
    assert rejected.json()["detail"]["code"] == "invalid_token"


def test_admin_controls_mcp_independently_and_mcp_tokens_can_self_revoke(tmp_path, monkeypatch):
    _auth_environment(tmp_path, monkeypatch)
    client = _client()
    admin_session = _change_password(client, _login(client), "admin", "new-admin-password")

    initial = client.get("/api/settings/integration-access")
    assert initial.status_code == 200
    assert initial.json()["rest"]["mode"] == "disabled"
    assert initial.json()["mcp"]["mode"] == "disabled"
    assert initial.json()["mcp"]["endpoint"] == "/mcp/"

    invalid = client.post(
        "/api/auth/token",
        json={"username": "admin", "password": "new-admin-password", "service": "unknown"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"]["code"] == "invalid_service"

    enabled = client.put(
        "/api/settings/integration-access",
        headers={"X-CSRF-Token": admin_session["csrf_token"]},
        json={"rest_mode": "disabled", "mcp_mode": "read_only"},
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["rest"]["enabled"] is False
    assert enabled.json()["mcp"]["mode"] == "read_only"

    rest_blocked = client.post(
        "/api/auth/token",
        json={"username": "admin", "password": "new-admin-password"},
    )
    assert rest_blocked.status_code == 403
    assert rest_blocked.json()["detail"]["code"] == "api_disabled"
    issued = client.post(
        "/api/auth/token",
        json={"username": "admin", "password": "new-admin-password", "service": "mcp"},
    )
    assert issued.status_code == 200, issued.text
    token_payload = issued.json()
    assert token_payload["service"] == "mcp"
    assert token_payload["scope"] == "read"
    assert token_payload["endpoint"] == "/mcp/"

    bearer = {"Authorization": f"Bearer {token_payload['access_token']}"}
    revoked = client.delete("/api/auth/token", headers=bearer)
    assert revoked.status_code == 200
    assert revoked.json() == {"revoked": True}
    assert client.post("/mcp/", headers=bearer, json={}).status_code == 401


def test_read_write_api_honors_roles_and_disabling_revokes_all_tokens(tmp_path, monkeypatch):
    auth = _auth_environment(tmp_path, monkeypatch)
    admin_client = _client()
    admin_session = _change_password(admin_client, _login(admin_client), "admin", "new-admin-password")
    viewer = auth.create_user(
        {
            "first_name": "Vera",
            "last_name": "Viewer",
            "username": "api-viewer",
            "password": "viewer-temporary-password",
            "role": "Viewer",
        }
    )
    viewer_client = _client()
    viewer_session = _change_password(
        viewer_client,
        _login(viewer_client, "api-viewer", "viewer-temporary-password"),
        "viewer-temporary-password",
        "viewer-api-password",
    )

    forbidden = viewer_client.put(
        "/api/settings/api-access",
        headers={"X-CSRF-Token": viewer_session["csrf_token"]},
        json={"mode": "read_write"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "admin_required"

    enabled = admin_client.put(
        "/api/settings/api-access",
        headers={"X-CSRF-Token": admin_session["csrf_token"]},
        json={"mode": "read_write"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["write_enabled"] is True

    admin_token = admin_client.post(
        "/api/auth/token",
        json={"username": "admin", "password": "new-admin-password"},
    ).json()
    viewer_token = viewer_client.post(
        "/api/auth/token",
        json={"username": "api-viewer", "password": "viewer-api-password"},
    ).json()
    assert admin_token["scope"] == "read write"
    assert viewer_token["scope"] == "read"

    admin_bearer = {"Authorization": f"Bearer {admin_token['access_token']}"}
    viewer_bearer = {"Authorization": f"Bearer {viewer_token['access_token']}"}
    write = admin_client.put("/api/settings/client-state", headers=admin_bearer, json={"language": "en"})
    assert write.status_code == 200, write.text
    viewer_write = viewer_client.put("/api/settings/client-state", headers=viewer_bearer, json={"language": "he"})
    assert viewer_write.status_code == 403
    assert viewer_write.json()["detail"]["code"] == "read_only"

    disabled = admin_client.put(
        "/api/settings/api-access",
        headers={"X-CSRF-Token": admin_session["csrf_token"]},
        json={"mode": "disabled"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["active_tokens"] == 0
    with sqlite3.connect(auth.path) as connection:
        assert connection.execute("select count(*) from api_tokens").fetchone()[0] == 0
    blocked = admin_client.get("/api/about", headers=admin_bearer)
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "api_disabled"
    assert viewer["role"] == "Viewer"


def test_api_tokens_require_a_completed_password_change_and_expire(tmp_path, monkeypatch):
    auth = _auth_environment(tmp_path, monkeypatch)
    auth.set_api_access_mode("read_only")
    client = _client()

    forced_change = client.post("/api/auth/token", json={"username": "admin", "password": "admin"})
    assert forced_change.status_code == 403
    assert forced_change.json()["detail"]["code"] == "password_change_required"

    session = _change_password(client, _login(client), "admin", "new-admin-password")
    issued = client.post(
        "/api/auth/token",
        json={"username": "admin", "password": "new-admin-password"},
    )
    token = issued.json()["access_token"]
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(auth.path) as connection:
        connection.execute("update api_tokens set expires_at = ?", (expired,))

    rejected = client.get("/api/about", headers={"Authorization": f"Bearer {token}"})
    assert rejected.status_code == 401
    assert rejected.json()["detail"]["code"] == "invalid_token"
    with sqlite3.connect(auth.path) as connection:
        assert connection.execute("select count(*) from api_tokens").fetchone()[0] == 0
    assert session["user"]["must_change_password"] is False


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
