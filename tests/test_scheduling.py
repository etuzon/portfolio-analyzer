from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main
from app.auth import AuthStore, SESSION_COOKIE_NAME
from app.local_portfolio import LocalPortfolioStore
from app.scheduling import normalize_schedule, schedule_cron, schedule_from_cron, schedule_trigger


@pytest.mark.parametrize("raw,cron", [
    ({"frequency": "minutely", "interval": 15}, "*/15 * * * *"),
    ({"frequency": "hourly", "interval": 3, "minute": 10}, "10 */3 * * *"),
    ({"frequency": "daily", "hour": 8, "minute": 30}, "30 8 * * *"),
    ({"frequency": "weekly", "weekdays": [6, 0], "hour": 8, "minute": 30}, "30 8 * * mon,sun"),
    ({"frequency": "monthly", "month_days": [31, 1], "hour": 8, "minute": 30}, "30 8 1,31 * *"),
])
def test_universal_schedule_cron_contract(raw, cron):
    assert schedule_cron(raw) == cron
    assert schedule_cron(schedule_from_cron(cron)) == cron
    assert main.backup_cron_from_config(raw) == cron


@pytest.mark.parametrize("raw", [
    {"frequency": "invalid"}, {"frequency": "weekly", "weekdays": []},
    {"frequency": "weekly", "weekdays": [7]}, {"frequency": "monthly", "month_days": []},
    {"frequency": "monthly", "month_days": [0]}, {"frequency": "daily", "hour": 24},
    {"frequency": "daily", "minute": 2.5}, {"frequency": "minutely", "interval": 0},
    {"frequency": "hourly", "interval": 24}, {"frequency": "daily", "hour": True},
])
def test_invalid_schedule_is_rejected(raw):
    with pytest.raises(ValueError):
        normalize_schedule(raw)


def test_monthly_day_31_skips_short_month():
    trigger = schedule_trigger({"frequency": "monthly", "month_days": [31], "hour": 8, "minute": 0}, "Asia/Jerusalem")
    next_run = trigger.get_next_fire_time(None, datetime(2026, 4, 1, tzinfo=ZoneInfo("Asia/Jerusalem")))
    assert (next_run.month, next_run.day, next_run.hour) == (5, 31, 8)


@pytest.fixture
def schedule_environment(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    auth = AuthStore(store.path)
    auth.initialize()
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    monkeypatch.setattr(main, "runtime_settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(main, "scheduler", None)
    main._login_failures.clear()
    client = TestClient(main.app, base_url="https://localhost:6443")
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    changed = client.post("/api/auth/change-password", headers={"X-CSRF-Token": login["csrf_token"]},
                          json={"current_password": "admin", "new_password": "Schedule-Testing-2026!", "confirm_password": "Schedule-Testing-2026!"})
    assert changed.status_code == 200
    return client, auth, changed.json(), tmp_path


def test_schedule_api_persistence_validation_and_auth(schedule_environment):
    client, auth, session, path = schedule_environment
    endpoint = "/api/settings/ai-enrichment-schedule"
    assert TestClient(main.app).get(endpoint).status_code == 401
    assert client.get(endpoint).json()["enabled"] is False
    payload = {"enabled": True, "schedule_config": {"frequency": "weekly", "weekdays": [0, 3], "hour": 9, "minute": 5},
               "timezone": "Asia/Jerusalem", "position_scope": "all", "language": "he"}
    assert client.put(endpoint, json=payload).status_code == 403
    response = client.put(endpoint, headers={"X-CSRF-Token": session["csrf_token"]}, json=payload)
    assert response.status_code == 200, response.text
    assert "owner_id" not in response.json()
    assert client.get(endpoint).json()["position_scope"] == "all"
    old = (path / "settings.json").read_text()
    payload["timezone"] = "Bad/Timezone"
    assert client.put(endpoint, headers={"X-CSRF-Token": session["csrf_token"]}, json=payload).status_code == 400
    assert (path / "settings.json").read_text() == old
    assert "cookie" not in old and "csrf" not in old


def test_scheduled_credentials_use_normal_auth_and_revoke(schedule_environment):
    client, auth, session, path = schedule_environment
    owner = auth.list_users()[0]
    token, csrf = auth.scheduled_session(owner["id"])
    assert auth.session(token)["user"]["id"] == owner["id"]
    worker = TestClient(main.app, base_url="https://localhost:6443")
    worker.cookies.set(SESSION_COOKIE_NAME, token)
    assert worker.get("/api/securities/enrichment/status").status_code == 200
    auth.logout(token)
    assert worker.get("/api/securities/enrichment/status").status_code == 401
    with pytest.raises(PermissionError):
        auth.scheduled_session("deleted-owner")


def test_schedule_job_reconfigures_and_disables(schedule_environment, monkeypatch):
    client, auth, session, path = schedule_environment
    calls = []
    class Scheduler:
        def remove_job(self, identifier): calls.append(("remove", identifier))
        def add_job(self, callback, trigger, **kwargs): calls.append(("add", callback, trigger, kwargs))
        def get_job(self, identifier): return None
    monkeypatch.setattr(main, "scheduler", Scheduler())
    endpoint = "/api/settings/ai-enrichment-schedule"
    headers = {"X-CSRF-Token": session["csrf_token"]}
    assert client.put(endpoint, headers=headers, json={"enabled": True}).status_code == 200
    assert calls[-1][0] == "add"
    assert calls[-1][3]["max_instances"] == 1
    assert client.put(endpoint, headers=headers, json={"enabled": False}).status_code == 200
    assert calls[-1] == ("remove", main.AI_ENRICHMENT_JOB_ID)


def test_scheduled_job_skips_active_job_without_minting_credentials_and_cleans_failure(monkeypatch):
    from fastapi import FastAPI
    from app.security_enrichment import EnrichmentJobs
    workers = []
    class Deferred:
        def __init__(self, target, args, **kwargs):
            self.target, self.args = target, args
            workers.append(self)
        def start(self): pass
    jobs = EnrichmentJobs(FastAPI(), lambda: {}, candidate_reader=lambda: {}, security_fetcher=lambda *_: {},
                          outcome_reader=lambda: [], outcome_writer=lambda *_: [], worker_factory=Deferred)
    events = []
    def credentials():
        events.append("mint")
        return {"cookie": "session-secret"}, lambda: events.append("revoke")
    first = jobs.start("owner", {}, "en", scheduled_credentials=credentials)
    for owner in ("owner", "another-owner"):
        with pytest.raises(HTTPException) as busy:
            jobs.start(owner, {}, "en", scheduled_credentials=credentials)
        assert busy.value.status_code == 409
    assert len(workers) == 1 and events == ["mint"]
    def failing_run(*args):
        raise RuntimeError("worker failed")
    monkeypatch.setattr(jobs, "run", failing_run)
    with pytest.raises(RuntimeError):
        workers[0].target(*workers[0].args)
    assert events == ["mint", "revoke"]


def test_scheduled_job_does_not_overlap_other_owners_manual_research():
    from fastapi import FastAPI
    from app.security_enrichment import EnrichmentJobs

    class Deferred:
        def __init__(self, **kwargs): pass
        def start(self): pass

    jobs = EnrichmentJobs(FastAPI(), lambda: {}, candidate_reader=lambda: {}, security_fetcher=lambda *_: {},
                          outcome_reader=lambda: [], outcome_writer=lambda *_: [], worker_factory=Deferred)
    manual = jobs.start("manual-owner", {}, "en")
    events = []
    with pytest.raises(HTTPException) as busy:
        jobs.start("scheduler-owner", {}, "en", scheduled_credentials=lambda: events.append("mint"))
    assert busy.value.status_code == 409
    assert not events
    # The existing manual concurrency and same-owner reuse contract remains.
    assert jobs.start("manual-owner", {}, "en")["request_id"] == manual["request_id"]
    jobs.start("second-manual-owner", {}, "en")
    assert len(jobs._jobs) == 2


@pytest.mark.parametrize("raw,cron", [
    ({"frequency": "minutely", "interval": 5, "hour": "", "minute": -1}, "*/5 * * * *"),
    ({"frequency": "hourly", "interval": 4, "hour": "", "minute": 12}, "12 */4 * * *"),
])
def test_hidden_clock_fields_do_not_invalidate_recurrence(raw, cron):
    assert schedule_cron(raw) == cron


@pytest.mark.parametrize("endpoint", ["/api/settings/ai-enrichment-schedule", "/api/settings/backup"])
@pytest.mark.parametrize("draft", [
    {"schedule_config": {"frequency": "weekly", "weekdays": []}},
    {"schedule_config": {"frequency": "monthly", "month_days": []}},
    {"timezone": "Bad/Timezone"},
])
def test_disable_preserves_last_valid_schedule_despite_invalid_draft(schedule_environment, endpoint, draft):
    client, auth, session, path = schedule_environment
    headers = {"X-CSRF-Token": session["csrf_token"]}
    saved = client.put(endpoint, headers=headers, json={"enabled": True, "timezone": "UTC",
                       "schedule_config": {"frequency": "daily", "hour": 6, "minute": 20}})
    assert saved.status_code == 200, saved.text
    disabled = client.put(endpoint, headers=headers, json={"enabled": False, **draft})
    assert disabled.status_code == 200, disabled.text
    reloaded = client.get(endpoint).json() if endpoint.endswith("ai-enrichment-schedule") else client.get("/api/settings").json()["backup"]
    assert reloaded["enabled"] is False
    assert reloaded["schedule_config"] == saved.json()["schedule_config"]
    assert reloaded["timezone"] == "UTC"
    assert client.put(endpoint, headers=headers, json={"enabled": True}).status_code == 200


@pytest.mark.parametrize("invalid", [
    {"timezone": "Bad/Timezone"}, {"timezone": None}, {"timezone": 7},
    {"schedule": "no cron values here today"}, {"schedule": "99 23 * * *"},
    {"schedule": "0 6 * * *", "timezone": "Bad/Timezone"},
    {"schedule_config": None},
])
def test_backup_rejects_invalid_candidate_before_either_persistence(schedule_environment, invalid):
    client, auth, session, path = schedule_environment
    headers = {"X-CSRF-Token": session["csrf_token"]}
    endpoint = "/api/settings/backup"
    assert client.put(endpoint, headers=headers, json={"enabled": True, "timezone": "UTC"}).status_code == 200
    previous_file = (path / "settings.json").read_text()
    previous_preference = main.local_store.get_preference(main.BACKUP_SETTINGS_PREF_KEY)
    rejected = client.put(endpoint, headers=headers, json=invalid)
    assert rejected.status_code == 400, rejected.text
    assert (path / "settings.json").read_text() == previous_file
    assert main.local_store.get_preference(main.BACKUP_SETTINGS_PREF_KEY) == previous_preference


@pytest.mark.parametrize("restored_schedule", [None, {
    "enabled": True, "timezone": "UTC", "owner_id": "restored-owner",
    "schedule_config": {"frequency": "hourly", "interval": 4, "minute": 15},
}])
def test_restore_reconfigures_ai_job_from_restored_runtime(schedule_environment, monkeypatch, restored_schedule):
    client, auth, session, path = schedule_environment
    registered = {main.AI_ENRICHMENT_JOB_ID: "old-job"}

    class Scheduler:
        def pause(self): pass
        def resume(self): pass
        def remove_job(self, identifier): registered.pop(identifier, None)
        def add_job(self, callback, trigger, **kwargs): registered[kwargs["id"]] = trigger

    monkeypatch.setattr(main, "scheduler", Scheduler())
    monkeypatch.setattr(main, "_validated_full_backup_archive", lambda payload: ({}, {}))
    monkeypatch.setattr(main, "write_full_backup", lambda keep: {"filename": "safety.zip"})
    restored = {"backup": {**main.default_backup_settings(), "enabled": False}}
    if restored_schedule is not None:
        restored["ai_enrichment_schedule"] = restored_schedule
    monkeypatch.setattr(main, "_apply_full_backup_files", lambda files: main.save_runtime_settings(restored))
    previous_config = main.config
    monkeypatch.setattr(main, "load_config", lambda: previous_config)
    monkeypatch.setattr(main, "configure_dividend_job", lambda: None)
    assert main.restore_full_backup(b"archive")["status"] == "restored"
    if restored_schedule is None:
        assert main.AI_ENRICHMENT_JOB_ID not in registered
    else:
        assert str(registered[main.AI_ENRICHMENT_JOB_ID].timezone) == "UTC"
        assert "hour='*/4'" in str(registered[main.AI_ENRICHMENT_JOB_ID])


def test_scheduled_session_rejects_viewer_and_disabled(schedule_environment):
    client, auth, session, path = schedule_environment
    viewer = auth.create_user({"first_name": "Read", "last_name": "Only", "username": "viewer", "password": "Viewer-Testing-2026!", "role": "Viewer"})
    with pytest.raises(PermissionError):
        auth.scheduled_session(viewer["id"])
    operator = auth.create_user({"first_name": "Op", "last_name": "Erator", "username": "operator", "password": "Operator-Testing-2026!", "role": "Operator"})
    auth.set_user_enabled(operator["id"], False, auth.list_users()[0]["id"])
    with pytest.raises(PermissionError):
        auth.scheduled_session(operator["id"])
