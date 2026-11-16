"""Independent named-rule persistence, isolation, migration and stale-run QA.

Child workers are controlled here to test orchestration. Actual public AI
retrieval is a separate runtime acceptance gate and is not claimed by mocks.
"""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.local_portfolio import LocalPortfolioStore
from app.research_schedules import ResearchSchedules, PREFERENCE, JOB_PREFIX, LEGACY_JOB_IDS


ACTOR = {"id": "synthetic-operator", "role": "Operator"}


class Scheduler:
    def __init__(self):
        self.jobs = {}

    def add_job(self, function, trigger=None, **options):
        self.jobs[options["id"]] = SimpleNamespace(id=options["id"], function=function,
            trigger=trigger, next_run_time=datetime(2026, 11, 20, tzinfo=timezone.utc), **{
                key: value for key, value in options.items() if key != "id"})

    def remove_job(self, identifier):
        self.jobs.pop(identifier, None)

    def get_job(self, identifier):
        return self.jobs.get(identifier)

    def get_jobs(self):
        return list(self.jobs.values())


class Workers:
    def __init__(self):
        self.callbacks = []

    def __call__(self, *, target, **_):
        return SimpleNamespace(start=lambda: self.callbacks.append(target))


class Child:
    def __init__(self):
        self.calls = []
        self.hook = None

    def start(self, owner, headers, language, *args, **options):
        if options.get("scheduled_credentials"):
            credentials, cleanup = options["scheduled_credentials"]()
            assert set(credentials) == {"cookie", "x-csrf-token"}
            cleanup()
        self.calls.append(dict(owner=owner, language=language, args=args,
                               options={key: deepcopy(value) for key, value in options.items() if key != "scheduled_credentials"}))
        if self.hook:
            hook, self.hook = self.hook, None
            hook()
        return dict(request_id="synthetic-child", status="completed", code="completed",
                    counts=dict(model_requests=1, rest_requests=1, web_requests=1),
                    coverage={"next_batch_offset": 3})


def environment(tmp_path, *, legacy=None):
    store = LocalPortfolioStore(tmp_path / "qa-schedules.sqlite")
    scheduler, workers = Scheduler(), Workers()
    portfolio, risk, countries = Child(), Child(), Child()
    logouts = []
    auth = SimpleNamespace(scheduled_session=lambda _: ("synthetic-token", "synthetic-csrf"), logout=logouts.append)
    sources = deepcopy(legacy or {})
    manager = ResearchSchedules(lambda: store.get_preference(PREFERENCE),
        lambda value: store.set_preference(PREFERENCE, value), lambda: scheduler, lambda: auth,
        portfolio, risk, countries, legacy_reader=lambda: deepcopy(sources),
        inventory_reader=lambda: [dict(security_key="QA|NASDAQ|USD")], worker_factory=workers,
        poll_seconds=0)
    return SimpleNamespace(store=store, scheduler=scheduler, workers=workers, manager=manager,
                           portfolio=portfolio, risk=risk, countries=countries,
                           auth=auth, logouts=logouts, sources=sources)


def rule(name="Weekly risk", **extra):
    return dict(name=name, enabled=True, data_types=["risk_inputs"], position_scope="open",
                refresh_policy="stale", mode="api_then_ai", timezone="UTC", language="en",
                schedule_config=dict(frequency="weekly", weekdays=[0], hour=8, minute=15), **extra)


def test_multiple_same_target_rules_keep_independent_identity_settings_and_persistence(tmp_path):
    env = environment(tmp_path)
    first = env.manager.save(ACTOR, rule())
    second_payload = rule("Daily risk refresh")
    second_payload.update(refresh_policy="refresh_existing", mode="api",
                          schedule_config=dict(frequency="daily", hour=16, minute=20))
    second = env.manager.save(ACTOR, second_payload)
    assert first["id"] != second["id"]
    assert set(env.scheduler.jobs) == {JOB_PREFIX + first["id"], JOB_PREFIX + second["id"]}
    before_second = deepcopy(next(row for row in env.store.get_preference(PREFERENCE)["items"] if row["id"] == second["id"]))
    env.manager.save(ACTOR, dict(name="Renamed first rule", enabled=False,
                                expected_revision=first["revision"]), first["id"])
    assert env.store.get_preference(PREFERENCE)["items"][1] == before_second
    assert set(env.scheduler.jobs) == {JOB_PREFIX + second["id"]}
    fresh = ResearchSchedules(lambda: env.store.get_preference(PREFERENCE),
        lambda value: env.store.set_preference(PREFERENCE, value), lambda: env.scheduler, lambda: env.auth,
        env.portfolio, env.risk, env.countries, legacy_reader=lambda: {"risk_inputs": rule("Must not revive")},
        worker_factory=env.workers)
    fresh.configure()
    assert {row["id"] for row in fresh.status(ACTOR)["items"]} == {first["id"], second["id"]}
    fresh.delete(ACTOR, first["id"])
    assert [row["id"] for row in fresh.status(ACTOR)["items"]] == [second["id"]]
    assert env.store.get_preference(PREFERENCE)["items"][0] == before_second


def test_legacy_migration_is_once_and_replaces_every_old_job_without_duplicates(tmp_path):
    legacy = dict(runtime=dict(ai_enrichment_schedules={
        "open": dict(owner_id=ACTOR["id"], enabled=True, schedule_config=dict(frequency="daily", hour=7, minute=0), timezone="UTC"),
        "all": dict(owner_id=ACTOR["id"], enabled=False, schedule_config=dict(frequency="weekly", weekdays=[2], hour=18, minute=0), timezone="UTC")}),
        risk_inputs=dict(owner_id=ACTOR["id"], enabled=True, mode="ai", timezone="UTC",
                         schedule_config=dict(frequency="daily", hour=9, minute=0)))
    env = environment(tmp_path, legacy=legacy)
    for identifier in LEGACY_JOB_IDS:
        env.scheduler.add_job(lambda: None, id=identifier)
    env.manager.configure()
    saved = deepcopy(env.store.get_preference(PREFERENCE))
    assert len(saved["items"]) == 3
    assert len({row["id"] for row in saved["items"]}) == 3
    assert set(env.scheduler.jobs) == {JOB_PREFIX + row["id"] for row in saved["items"] if row["enabled"]}
    env.sources["risk_inputs"]["enabled"] = False
    env.manager.configure()
    assert env.store.get_preference(PREFERENCE) == saved
    assert len(env.scheduler.jobs) == 2


@pytest.mark.parametrize("reference", ["risk_inputs", "country_ratings"])
def test_legacy_cadence_save_preserves_advanced_choices_on_its_stable_named_rule(tmp_path, reference):
    raw = dict(owner_id=ACTOR["id"], enabled=True, timezone="UTC", language="en",
               schedule_config=dict(frequency="daily", hour=8, minute=0))
    if reference == "risk_inputs":
        raw.update(mode="api_then_ai", security_keys=None)
    else:
        raw.update(country_scope="accounts")
    env = environment(tmp_path, legacy={reference: raw})
    env.manager.configure()
    migrated = env.manager.status(ACTOR)["items"][0]
    changes = dict(name="Advanced named rule", refresh_policy="refresh_existing", position_scope="all",
                   data_types=["prices", "risk_inputs"] if reference == "risk_inputs" else ["risk_inputs", "country_ratings"],
                   expected_revision=migrated["revision"])
    if reference == "risk_inputs":
        changes["mode"] = "ai"
    else:
        changes.update(country_scope="selected", country_codes=["US"])
    edited = env.manager.save(ACTOR, changes, migrated["id"])
    # The old editors cannot express these advanced choices. Their existing
    # projected controls remain unchanged while the user edits only recurrence.
    if reference == "risk_inputs":
        env.sources[reference].update(mode="ai", security_keys=None)
    else:
        env.sources[reference]["country_scope"] = "all"  # selected projects to old all
    env.sources[reference]["schedule_config"] = dict(frequency="daily", hour=17, minute=20)
    env.manager.import_legacy(reference)
    after = env.manager.status(ACTOR)["items"][0]
    assert after["id"] == edited["id"]
    for field in ("name", "data_types", "refresh_policy", "position_scope", "security_keys", "country_scope", "country_codes", "mode"):
        assert after[field] == edited[field], field
    assert after["schedule_config"] == dict(frequency="daily", hour=17, minute=20)
    assert after["revision"] == edited["revision"] + 1
    assert set(env.scheduler.jobs) == {JOB_PREFIX + edited["id"]}
    # A genuine change in an old editor's represented scope must still apply;
    # preserving advanced fields is not permission to ignore old user actions.
    if reference == "risk_inputs":
        env.sources[reference]["security_keys"] = ["QA|NASDAQ|USD"]
    else:
        env.sources[reference]["country_scope"] = "accounts"
    env.manager.import_legacy(reference)
    changed_scope = env.manager.status(ACTOR)["items"][0]
    assert changed_scope["name"] == edited["name"]
    assert changed_scope["data_types"] == edited["data_types"]
    assert changed_scope["refresh_policy"] == "refresh_existing"
    if reference == "risk_inputs":
        assert changed_scope["position_scope"] == "selected"
        assert changed_scope["security_keys"] == ["QA|NASDAQ|USD"]
    else:
        assert changed_scope["country_scope"] == "accounts" and changed_scope["country_codes"] is None
        assert changed_scope["position_scope"] == "all"


def test_editing_scope_during_old_child_completion_cannot_restore_old_batch_cursor(tmp_path):
    env = environment(tmp_path)
    saved = env.manager.save(ACTOR, rule())
    identifier = saved["id"]
    env.manager.run(identifier, ACTOR, manual=True)
    env.portfolio.hook = lambda: env.manager.save(ACTOR,
        dict(position_scope="all", refresh_policy="refresh_existing", expected_revision=saved["revision"]), identifier)
    env.workers.callbacks.pop(0)()
    current = next(row for row in env.store.get_preference(PREFERENCE)["items"] if row["id"] == identifier)
    assert current["position_scope"] == "all"
    assert current["refresh_policy"] == "refresh_existing"
    assert current["batch_cursor"] == 0, "An old-scope child must not overwrite the new-scope cursor reset"
    assert env.logouts == ["synthetic-token"]


def test_named_rules_reject_viewer_changes_and_invalid_or_stale_inputs(tmp_path):
    env = environment(tmp_path)
    with pytest.raises(HTTPException) as forbidden:
        env.manager.save(dict(id="viewer", role="Viewer"), rule())
    assert forbidden.value.status_code == 403
    saved = env.manager.save(ACTOR, rule())
    with pytest.raises(HTTPException) as stale:
        env.manager.save(ACTOR, dict(name="Stale edit", expected_revision=0), saved["id"])
    assert stale.value.status_code == 409
    for changed in [dict(name=""), dict(enabled="true"), dict(data_types=["unsupported"]),
                    dict(position_scope="selected", security_keys=["unknown|NASDAQ|USD"]),
                    dict(mode="unsupported"), dict(refresh_policy="unsupported")]:
        payload = rule()
        payload.update(changed)
        with pytest.raises(HTTPException) as invalid:
            env.manager.save(ACTOR, payload)
        assert invalid.value.status_code == 400
    assert len(env.manager.status(ACTOR)["items"]) == 1


def test_actual_schedule_routes_enforce_auth_roles_csrf_and_shared_editor_model(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from app.auth import AuthStore

    store = LocalPortfolioStore(tmp_path / "qa-schedule-api.sqlite")
    auth = AuthStore(store.path)
    auth.initialize()
    for name, role in [("admin", "Admin"), ("operator", "Operator"), ("viewer", "Viewer")]:
        user = auth.create_user(dict(username=f"qa-{name}", first_name="Synthetic", last_name=role,
                                     role=role, password="Synthetic-QA-Password!"))
        with auth._connect() as connection:
            connection.execute("update app_users set must_change_password=0 where id=?", (user["id"],))
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    monkeypatch.setattr(main, "scheduler", None)
    manager = main.research_schedules
    workers = Workers()
    monkeypatch.setattr(manager, "legacy_reader", lambda: {})
    monkeypatch.setattr(manager, "worker_factory", workers)
    monkeypatch.setattr(manager, "_active", {})
    monkeypatch.setattr(manager, "_configured_ids", set())
    monkeypatch.setattr(manager, "inventory_reader", lambda: [])
    main._login_failures.clear()
    endpoint = "/api/settings/research-schedules"
    client = TestClient(main.app, base_url="https://localhost:6443")
    assert client.get(endpoint).status_code == 401
    assert client.post(endpoint, json=rule()).status_code == 401

    def login(name):
        return client.post("/api/auth/login", json=dict(username=f"qa-{name}", password="Synthetic-QA-Password!")).json()

    viewer = login("viewer")
    assert client.get(endpoint).status_code == 200
    assert client.post(endpoint, json=rule(), headers={"X-CSRF-Token": viewer["csrf_token"]}).status_code == 403
    operator = login("operator")
    assert client.post(endpoint, json=rule()).status_code == 403
    saved = client.post(endpoint, json=rule(), headers={"X-CSRF-Token": operator["csrf_token"]})
    assert saved.status_code == 201, saved.text
    row = saved.json()
    assert "owner_id" not in row
    path = endpoint + "/" + row["id"]
    viewer = login("viewer")
    public = client.get(endpoint).json()["items"][0]
    assert public["editable"] is False
    for method, url, payload in [("put", path, {"name": "Forbidden"}), ("delete", path, None), ("post", path + "/run", {})]:
        options = {"headers": {"X-CSRF-Token": viewer["csrf_token"]}}
        if payload is not None:
            options["json"] = payload
        assert getattr(client, method)(url, **options).status_code == 403
    operator = login("operator")
    assert client.put(path, json={"name": "No CSRF"}).status_code == 403
    stale = client.put(path, json={"name": "Old revision", "expected_revision": 0},
                       headers={"X-CSRF-Token": operator["csrf_token"]})
    assert stale.status_code == 409
    run = client.post(path + "/run", json={}, headers={"X-CSRF-Token": operator["csrf_token"]})
    assert run.status_code == 202
    assert len(workers.callbacks) == 1
    admin = login("admin")
    changed = client.put(path, json={"name": "Admin review", "expected_revision": row["revision"]},
                         headers={"X-CSRF-Token": admin["csrf_token"]})
    assert changed.status_code == 200
    assert client.delete(path).status_code == 403
    assert client.delete(path, headers={"X-CSRF-Token": admin["csrf_token"]}).status_code == 200
    assert client.get(endpoint).json()["items"] == []
