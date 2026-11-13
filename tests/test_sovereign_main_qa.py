"""Independent main-app acceptance with real auth and isolated local stores.

Queue children are deterministic dispatch probes here; the separate retained
actual-AI receipt establishes public-source/model parity without production use.
"""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main, credit_ratings_api
from app.auth import AuthStore
from app.local_portfolio import LocalPortfolioStore
from app.providers import SqliteCache
from app.sovereign_rating_service import SovereignRatingService


PREFIX = "/api/countries/credit-ratings"
SCHEDULE = "/api/settings/country-rating-schedule"


def login(auth, role="Operator", suffix="owner"):
    created = auth.create_user({"username": "country-qa-" + suffix, "first_name": "Synthetic", "last_name": "Reviewer",
                                "role": role, "password": "Initial-Synthetic-2026!"})
    client = TestClient(main.app, base_url="https://localhost:6443")
    signed = client.post("/api/auth/login", json={"username": created["username"], "password": "Initial-Synthetic-2026!"})
    assert signed.status_code == 200
    changed = client.post("/api/auth/change-password", headers={"X-CSRF-Token": signed.json()["csrf_token"]}, json={
        "current_password": "Initial-Synthetic-2026!", "new_password": "Changed-Synthetic-2026!",
        "confirm_password": "Changed-Synthetic-2026!"})
    assert changed.status_code == 200
    return client, {"X-CSRF-Token": changed.json()["csrf_token"]}, created["id"]


class DispatchChildren:
    def __init__(self):
        self.calls = []
        self.fail_call = None

    def settings(self):
        return {"max_tool_loops": 8, "max_rest_calls": 8, "max_web_calls": 8}

    def start(self, owner, headers, language, scope, *, security_keys):
        assert len(security_keys) == 1
        self.calls.append((owner, deepcopy(headers), language, scope, list(security_keys)))
        return {"request_id": "dispatch-child-" + str(len(self.calls)),
                "status": "failed" if len(self.calls) == self.fail_call else "completed",
                "counts": {"model_requests": 2, "rest_requests": 3, "web_requests": 1},
                "outcomes": [{"security_key": security_keys[0], "status": "unavailable", "code": "data_unavailable",
                              "attempted": True, "verified_agencies": [], "agency_statuses": {
                                  "moodys": "unavailable", "sp": "unavailable", "fitch": "unavailable"}}]}


@pytest.fixture
def country_env(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "local.sqlite")
    auth = AuthStore(store.path)
    auth.initialize()
    cache = SqliteCache(tmp_path / "market.sqlite", ttl_hours=24)
    accounts = [store.save_account({"type": "Investment", "location": location, "currency": "JPY",
        "username": "Synthetic account " + str(index), "initial_cash": 0,
        "persons": [{"name": "Synthetic Owner", "birth_date": "01/01/1990"}]})
        for index, location in enumerate(("USA", "United States", "Israel", "Unknown synthetic location"))]
    for market, currency in (("NASDAQ", "USD"), ("NYSE", "EUR")):
        store.save_manual_security({"symbol": "QADUAL", "stock_market": market, "asset_class": "EQUITY",
                                    "currency": currency, "name": "Synthetic display label", "location": "USA"})
    profiles = {"NASDAQ": {"name": "Synthetic Canadian Corporation", "country": "Canada"},
                "NYSE": {"name": "Synthetic British Corporation", "country": "United Kingdom"}}
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    monkeypatch.setattr(main, "hub", lambda: SimpleNamespace(cache=cache, cached_profile=lambda symbol, **kw: deepcopy(profiles[kw["stock_market"]])))
    monkeypatch.setattr(main, "_record_log", lambda *a, **kw: None)
    monkeypatch.setattr(main, "_bond_market_data", lambda *a, **kw: None)
    monkeypatch.setattr(main, "_us_fund_market_data", lambda *a, **kw: None)
    monkeypatch.setattr(main.sovereign_rating_service, "_settings", lambda: {
        "verification_ttl_days": 30, "spglobal": {"enabled": True, "bearer_token": "synthetic-licensed-token-must-not-be-used"}})
    def forbidden_rating_api(*a, **kw):
        raise AssertionError("Sovereign public AI invoked a licensed ratings API")
    monkeypatch.setattr(credit_ratings_api, "fetch", forbidden_rating_api)
    def forbidden_market(*a, **kw):
        raise AssertionError("Sovereign research consulted market-data inventory")
    monkeypatch.setattr(main, "_ai_enrichment_candidates", forbidden_market)
    children, callbacks, logs = DispatchChildren(), [], []
    class Deferred:
        def __init__(self, target, **_):
            callbacks.append(target)
        def start(self):
            pass
    parent = main.country_rating_research
    monkeypatch.setattr(parent, "_jobs", {})
    monkeypatch.setattr(parent, "credit_jobs", children)
    monkeypatch.setattr(parent, "market_jobs", SimpleNamespace(settings=children.settings))
    monkeypatch.setattr(parent, "_worker_factory", Deferred)
    monkeypatch.setattr(parent, "poll_seconds", 0)
    schedules = main.country_rating_schedules
    monkeypatch.setattr(schedules, "auth_store", auth)
    monkeypatch.setattr(schedules, "scheduler_getter", lambda: None)
    monkeypatch.setattr(schedules, "logger", lambda event, **fields: logs.append((event, fields)))
    main._login_failures.clear()
    client, headers, owner = login(auth)
    return SimpleNamespace(store=store, auth=auth, cache=cache, accounts=accounts, profiles=profiles, client=client,
        headers=headers, owner=owner, children=children, callbacks=callbacks, parent=parent, schedules=schedules, logs=logs)


def context(env, code="IL"):
    response = env.client.get(PREFIX, params={"country_code": code})
    assert response.status_code == 200
    return response.json()


def test_account_country_scope_is_location_only_deduplicated_and_cache_only(country_env):
    env = country_env
    token = env.store.change_token()
    response = env.client.get(PREFIX + "/countries").json()
    assert {r["country_code"] for r in response["items"]} == {"US", "IL"}
    assert next(r for r in response["items"] if r["country_code"] == "US")["account_count"] == 2
    assert response["unknown_account_countries"] == 1
    all_rows = env.client.get(PREFIX + "/countries", params={"country_scope": "all"}).json()["items"]
    assert len(all_rows) == len({r["country_code"] for r in all_rows}) == 249
    assert {"PR", "PS"} <= {r["country_code"] for r in all_rows}
    risk = env.client.get(PREFIX + "/risk-context").json()
    assert risk["risk_formula_applied"] is False and risk["country_basis"] == "account_location"
    assert {r["country_code"] for r in risk["items"]} == {"IL", "US"}
    assert {r["country_code"] for r in risk["security_countries"]} == {"CA", "GB"}
    assert all(len(r["credit_ratings"]["ratings"]) == 9 for r in risk["items"])
    assert env.store.change_token() == token and not env.children.calls


def test_unknown_account_locations_never_fall_back_and_all_249_get_one_bounded_child(country_env):
    env = country_env
    for account in env.accounts:
        env.store.save_account({**account, "location": "Unknown synthetic location"})
    response = env.client.get(PREFIX + "/countries").json()
    assert response["items"] == [] and response["unknown_account_countries"] == 4
    started = env.client.post(PREFIX + "/ai", headers=env.headers, json={})
    assert started.status_code == 202
    env.callbacks.pop(0)()
    empty = env.client.get(PREFIX + "/ai/" + started.json()["request_id"]).json()
    assert empty["status"] == "completed" and empty["summary"]["total_candidates"] == 0 and not env.children.calls
    started = env.client.post(PREFIX + "/ai", headers=env.headers, json={"country_scope": "all"})
    assert started.status_code == 202
    env.callbacks.pop(0)()
    result = env.client.get(PREFIX + "/ai/" + started.json()["request_id"]).json()
    assert result["status"] == "completed" and result["country_scope"] == "all" and result["country_codes"] is None
    assert len(env.children.calls) == len({call[4][0] for call in env.children.calls}) == 249
    assert all(call[3] == "all" and len(call[4]) == 1 for call in env.children.calls)
    assert result["progress"]["completed"] == result["progress"]["total"] == 249
    assert result["summary"]["not_attempted"] == 0
    assert result["per_batch_limits"] == {"model": 8, "rest": 8, "web": 8}
    assert all(result["counts"]["max_" + kind + "_requests"] == 249 * 8 for kind in ("model", "rest", "web"))


@pytest.mark.parametrize("manual_country", ["DE", "PS"])
def test_country_association_profile_domicile_manual_cas_clear_and_exact_listing_isolation(country_env, manual_country):
    env = country_env
    params = {"symbol": "QADUAL", "stock_market": "NASDAQ", "currency": "USD"}
    current = env.client.get("/api/securities/country", params=params).json()
    assert current["country_code"] == "CA" and current["source_kind"] == "provider_profile"
    token = env.store.change_token()
    payload = {"security_key": "QADUAL|NASDAQ|USD", "country_code": manual_country, "expected_revision": 0,
               "expected_identity": current["identity_token"], "notes": "Synthetic domicile assertion"}
    saved = env.client.put("/api/securities/country", headers=env.headers, json=payload)
    assert saved.status_code == 200 and saved.json()["country_code"] == manual_country and saved.json()["source_kind"] == "manual"
    assert env.client.put("/api/securities/country", headers=env.headers, json=payload).status_code == 409
    assert env.client.put("/api/securities/country", headers=env.headers, json={**payload, "country_code": "ZZ", "expected_revision": 1}).status_code == 422
    other = env.client.get("/api/securities/country", params={**params, "stock_market": "NYSE", "currency": "EUR"}).json()
    assert other["country_code"] == "GB"
    env.profiles["NASDAQ"]["country"] = "France"
    assert env.client.get("/api/securities/country", params=params).json()["country_code"] == manual_country
    clear = env.client.delete("/api/securities/country", headers=env.headers, params={
        "security_key": payload["security_key"], "expected_revision": 1, "expected_identity": current["identity_token"]})
    assert clear.status_code == 200 and clear.json()["country_code"] == "FR"
    assert clear.json()["source_kind"] == "provider_profile" and clear.json()["revision"] == 2
    env.profiles["NASDAQ"]["name"] = "Different Legal Corporation"
    assert env.client.put("/api/securities/country", headers=env.headers, json={**payload, "expected_revision": 2}).status_code == 409
    assert env.store.change_token() == token


def test_normal_auth_roles_csrf_and_parent_schema_are_effective(country_env):
    env = country_env
    anonymous = TestClient(main.app, base_url="https://localhost:6443")
    assert anonymous.get(PREFIX + "/catalog").status_code == 401
    assert anonymous.post(PREFIX + "/ai", json={}).status_code == 401
    viewer, viewer_headers, _ = login(env.auth, "Viewer", "viewer")
    initial = context(env)
    payload = {"country_code": "IL", "agency": "moodys", "currency_basis": "foreign_currency", "status": "rated",
        "rating": "A3", "notes": "Synthetic assertion", "expected_revision": 0, "expected_identity": initial["identity_token"]}
    assert viewer.get(PREFIX, params={"country_code": "IL"}).status_code == 200
    assert viewer.get(SCHEDULE).status_code == 200
    candidates = env.client.get(PREFIX + "/candidates", params={"position_scope": "all", "security_keys": "COUNTRY:IL"})
    assert candidates.status_code == 422, "Model metadata must remain bound to an actual child request"
    metadata = main.sovereign_rating_service.candidates("all", ["COUNTRY:IL"])
    assert len(metadata["items"]) == 1 and metadata["items"][0]["retrieval_mode"] == "public_ai"
    assert "synthetic-licensed-token-must-not-be-used" not in json.dumps(metadata)
    assert viewer.put(PREFIX + "/manual", headers=viewer_headers, json=payload).status_code == 403
    assert viewer.put(SCHEDULE, headers=viewer_headers, json={"enabled": True}).status_code == 403
    assert viewer.post(PREFIX + "/ai", headers=viewer_headers, json={}).status_code == 403
    assert env.client.put(PREFIX + "/manual", json=payload).status_code == 403
    assert env.client.put(SCHEDULE, json={"enabled": True}).status_code == 403
    assert env.client.post(PREFIX + "/ai", json={}).status_code == 403
    assert env.client.post(PREFIX + "/ai", headers=env.headers, json={"country_scope": "open"}).status_code == 422
    assert env.client.post(PREFIX + "/ai", headers=env.headers, json={"country_codes": ["ZZ"]}).status_code == 422
    schema = main.app.openapi()
    assert schema["paths"][PREFIX + "/ai"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert "CountryResearchStart" in schema["components"]["schemas"]
    def expanded(routes):
        for route in routes:
            nested = getattr(route, "original_router", None)
            if nested is not None:
                yield from expanded(nested.routes)
            else:
                yield route
    effective = list(expanded(main.app.routes))
    for suffix, method in (("/ai", "POST"), ("/ai/{request_id}", "GET"), ("/status", "GET")):
        assert len([r for r in effective if getattr(r, "path", None) == PREFIX + suffix and method in getattr(r, "methods", set())]) == 1
    for suffix in ("/candidates", "/web/search", "/web/read", "/web/follow"):
        assert any(getattr(r, "path", None) == PREFIX + suffix for r in effective)


def test_manual_basis_history_cas_public_overlay_backup_and_get_no_writes(country_env, tmp_path):
    env = country_env
    initial = context(env)
    assert len(initial["ratings"]) == 9 and len({(r["agency"], r["currency_basis"]) for r in initial["ratings"]}) == 9
    token = env.store.change_token()
    payload = {"country_code": "IL", "agency": "moodys", "currency_basis": "foreign_currency", "status": "rated",
        "rating": "A3", "notes": "Synthetic manual assertion", "rating_date": "2026-11-12",
        "expected_revision": 0, "expected_identity": initial["identity_token"]}
    saved = env.client.put(PREFIX + "/manual", headers=env.headers, json=payload)
    assert saved.status_code == 200
    assert env.client.put(PREFIX + "/manual", headers=env.headers, json=payload).status_code == 409
    service = main.sovereign_rating_service
    candidate = service.candidate("IL")
    source = {"source_id": "public-fixture", "url": "https://ratings.moodys.com/ratings-news/qa", "title": "Israel rating action",
        "text": "30 Jan 2026\n\nMoody's affirmed Israel's Baa1 long-term local and foreign-currency issuer ratings. The outlook is Stable.",
        "retrieved_at": "2026-11-13T12:00:00+00:00"}
    assert service.publish(candidate, service._accept_sources(candidate, [source]))
    combined = context(env)
    def selected(c, basis):
        return next(r for r in c["ratings"] if r["agency"] == "moodys" and r["currency_basis"] == basis)
    assert selected(combined, "foreign_currency")["rating"] == "A3"
    assert selected(combined, "foreign_currency")["verification_status"] == "user_entered"
    assert selected(combined, "local_currency")["rating"] == "Baa1"
    assert selected(combined, "unknown")["rating"] is None
    assert {e["event_type"] for e in combined["rating_history"]} == {"manual_added", "first_observation"}
    cleared = env.client.delete(PREFIX + "/manual", headers=env.headers, params={"country_code": "IL", "agency": "moodys",
        "currency_basis": "foreign_currency", "expected_revision": 1, "expected_identity": initial["identity_token"]})
    assert cleared.status_code == 200
    current = cleared.json()
    assert selected(current, "foreign_currency")["rating"] == "Baa1"
    assert selected(current, "foreign_currency")["latest_change"]["event_type"] == "manual_cleared"
    assert not [e for e in current["rating_history"] if e["event_type"] == "rating_change"]
    history_key = service._keys(candidate)[1]
    retained = env.store.get_preference(history_key)
    assert context(env) == current and env.store.get_preference(history_key) == retained
    assert env.store.change_token() == token
    clone = LocalPortfolioStore(tmp_path / "restored.sqlite")
    clone.import_data(env.store.export_data())
    empty_cache = SqliteCache(tmp_path / "empty-cache.sqlite", ttl_hours=24)
    restarted = SovereignRatingService(cache=lambda: empty_cache, settings=lambda: {}, inventory=lambda: [deepcopy(candidate)],
        research_settings=lambda: {}, manual_store=lambda: clone)
    assert restarted.read(candidate) == current


def test_status_retains_explicit_codes_and_same_id_resume_never_repeats_completed_country(country_env):
    env = country_env
    env.children.fail_call = 2
    payload = {"country_scope": "all", "country_codes": ["IL", "USA", "IL"]}
    started = env.client.post(PREFIX + "/ai", headers=env.headers, json=payload)
    assert started.status_code == 202
    identifier = started.json()["request_id"]
    assert started.json()["country_codes"] == ["IL", "US"]
    env.callbacks.pop(0)()
    status = env.client.get(PREFIX + "/status").json()["last_job"]
    assert status["status"] == "failed" and status["country_codes"] == ["IL", "US"]
    other, _, _ = login(env.auth, suffix="other")
    assert other.get(PREFIX + "/ai/" + identifier).status_code == 404
    assert env.client.post(PREFIX + "/ai", headers=env.headers, json={"country_scope": "all", "resume_request_id": identifier}).status_code == 409
    resumed = env.client.post(PREFIX + "/ai", headers=env.headers, json={**payload, "resume_request_id": identifier})
    assert resumed.status_code == 202 and resumed.json()["request_id"] == identifier
    env.callbacks.pop(0)()
    result = env.client.get(PREFIX + "/ai/" + identifier).json()
    assert result["status"] == "completed" and result["country_codes"] == ["IL", "US"]
    assert [call[4] for call in env.children.calls] == [["COUNTRY:IL"], ["COUNTRY:US"], ["COUNTRY:US"]]
    assert result["summary"]["not_attempted"] == 0 and result["progress"]["completed"] == 2


def test_schedule_is_opt_in_and_uses_revocable_real_owner_credentials(country_env):
    env = country_env
    default = env.client.get(SCHEDULE).json()
    assert default["enabled"] is False and default["country_scope"] == "accounts"
    env.schedules.run()
    assert not env.callbacks and not env.children.calls
    token = env.store.change_token()
    enabled = env.client.put(SCHEDULE, headers=env.headers, json={"enabled": True, "country_scope": "accounts",
        "language": "he", "timezone": "Asia/Jerusalem", "schedule_config": {"frequency": "weekly", "weekdays": [0], "hour": 8, "minute": 15}})
    assert enabled.status_code == 200 and "owner_id" not in enabled.json()
    env.schedules.run()
    env.schedules.run()
    assert len(env.callbacks) == 1
    env.callbacks.pop(0)()
    assert {call[4][0] for call in env.children.calls} == {"COUNTRY:IL", "COUNTRY:US"}
    assert all(call[2] == "he" and call[3] == "open" for call in env.children.calls)
    scheduled_token = env.children.calls[0][1]["cookie"].split("=", 1)[1]
    assert env.auth.session(scheduled_token) is None, "Temporary scheduled credentials were not revoked"
    admin = next(u for u in env.auth.list_users() if u["role"] == "Admin")
    env.auth.set_user_enabled(env.owner, False, admin["id"])
    completed_calls = len(env.children.calls)
    env.schedules.run()
    assert len(env.children.calls) == completed_calls and not env.callbacks
    assert env.logs[-1][1]["code"] == "owner_not_authorized"
    assert env.store.change_token() == token
