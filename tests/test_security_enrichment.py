"""AI workers see portfolio facts only through authenticated allowlisted REST."""
import ast
from copy import deepcopy
from datetime import date, datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest

from app.llm_assistant import PortfolioAssistant, assistant_settings
from app.security_enrichment import EnrichmentJobs, PREFIX


class DeferredThread:
    workers = []
    def __init__(self, target, args, **_):
        self.target, self.args = target, args
        self.workers.append(self)
    def start(self):
        pass
    def run(self):
        self.target(*self.args)


def candidate(symbol):
    return {"security_key": symbol + "|NASDAQ|USD", "symbol": symbol, "stock_market": "NASDAQ", "currency": "USD",
            "asset_class": "EQUITY", "name": symbol, "missing_fields": ["prices", "profile"]}


def decision(key):
    return {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": key,
            "function": {"name": "fetch_security_information", "arguments": json.dumps({"security_key": key, "field": "auto"})}}]}}]}


def answer():
    return {"choices": [{"message": {"role": "assistant", "content": "Only source-backed results were returned."}}]}


@pytest.fixture
def environment(monkeypatch):
    app = FastAPI()
    state = SimpleNamespace(items=[candidate(name) for name in ("A", "B", "C", "D")], observations=[], saved=[],
                            fetched=[], expired=False, fetch_error=False, total=4, unavailable=False, model_messages=[])
    users = {"operator": {"id": "owner", "role": "Operator"}, "other": {"id": "other", "role": "Operator"},
             "viewer": {"id": "viewer", "role": "Viewer"}}
    @app.middleware("http")
    async def authenticate(request, call_next):
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        owner = users.get(token)
        state.observations.append((request.method, request.url.path, dict(request.headers)))
        if not owner or state.expired:
            return JSONResponse({"detail": "authentication_required"}, 401)
        request.state.auth_user = owner
        if request.method not in {"GET", "HEAD"} and (owner["role"] == "Viewer" or request.headers.get("X-CSRF-Token") != "synthetic-csrf"):
            return JSONResponse({"detail": "forbidden"}, 403)
        return await call_next(request)
    def inventory():
        return {"items": deepcopy(state.items), "total_count": state.total, "truncated": state.total > len(state.items)}
    def fetch(item, field):
        state.fetched.append((item["security_key"], field))
        if state.fetch_error:
            raise RuntimeError("synthetic-secret-must-not-leak")
        if state.unavailable:
            return {**item, "status": "unavailable", "code": "data_unavailable", "available_fields": [], "missing_fields": item["missing_fields"]}
        return {**item, "status": "updated", "code": "data_found", "available_fields": ["prices", "profile"], "missing_fields": []}
    settings = assistant_settings({"llm": {"enabled": True, "provider": "openai", "base_url": "https://never-called.invalid",
                                          "api_key": "synthetic-model-secret", "model": "fixture"}})
    manager = EnrichmentJobs(app, lambda: settings, candidate_reader=inventory, security_fetcher=fetch,
                             outcome_reader=lambda: deepcopy(state.saved),
                             outcome_writer=lambda outcomes, user_id, request_id: state.saved.extend(deepcopy(outcomes)), worker_factory=DeferredThread)
    app.include_router(manager.router())
    responses = iter([decision(item["security_key"]) for item in state.items[:3]] + [answer()])
    def model(self, *, messages, tools):
        state.model_messages.append(deepcopy(messages))
        return next(responses)
    monkeypatch.setattr(PortfolioAssistant, "_call_provider", model)
    headers = {"Authorization": "Bearer operator", "X-CSRF-Token": "synthetic-csrf"}
    DeferredThread.workers = []
    return SimpleNamespace(app=app, client=TestClient(app), manager=manager, state=state, headers=headers, settings=settings,
                           run=lambda: DeferredThread.workers[-1].run())


def start(env):
    response = env.client.post(PREFIX + "/ai", headers=env.headers, json={})
    assert response.status_code == 202, response.text
    return response.json()["request_id"]


def job(env, identifier):
    response = env.client.get(PREFIX + "/ai/" + identifier, headers=env.headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_one_click_shares_five_rest_and_five_model_ceiling_across_batch(environment):
    env = environment
    identifier = start(env)
    assert job(env, identifier)["status"] == "queued"
    env.run()
    result = job(env, identifier)
    assert result["status"] == "completed"
    assert result["code"] == "partial_data"  # Fourth candidate remains unprocessed.
    assert result["counts"]["rest_requests"] == 5
    assert result["counts"]["model_requests"] == 4
    assert result["summary"] == {"total_candidates": 4, "selected": 3, "updated": 3, "partial": 0, "unavailable": 0, "not_attempted": 1}
    assert len(env.state.fetched) == 3
    assert len(env.state.saved) == 4
    assert result["outcomes"][-1]["attempted"] is False
    assert "last_attempted_at" not in result["outcomes"][-1]
    worker_requests = [entry for entry in env.state.observations if entry[1].endswith(("/candidates", "/security", "/finalize"))]
    assert len(worker_requests) == 5
    assert all(entry[2].get("authorization") == "Bearer operator" and entry[2].get("x-csrf-token") == "synthetic-csrf" for entry in worker_requests)
    assert "synthetic-csrf" not in str(env.state.model_messages)
    assert "synthetic-model-secret" not in str(env.state.model_messages)


def test_unavailable_data_never_reports_completed_fields(environment):
    env = environment
    env.state.unavailable = True
    identifier = start(env)
    env.run()
    result = job(env, identifier)
    assert result["status"] == "completed" and result["code"] == "data_unavailable"
    assert result["summary"]["updated"] == result["summary"]["partial"] == 0
    assert result["summary"]["unavailable"] == 3
    assert result["portfolio_refresh_required"] is False
    assert all(item["code"] == "data_unavailable" for item in env.state.saved[:3])


def test_missing_ai_configuration_has_friendly_per_security_outcomes(environment):
    env = environment
    env.settings["enabled"] = False
    identifier = start(env)
    env.run()
    result = job(env, identifier)
    assert result["status"] == "failed" and result["code"] == "ai_unavailable"
    assert result["counts"]["model_requests"] == 0 and result["counts"]["rest_requests"] == 2
    assert len(env.state.saved) == 4
    assert all(item["code"] == "ai_unavailable" for item in result["outcomes"][:3])


def test_looping_model_cannot_exceed_shared_call_limits(environment, monkeypatch):
    env = environment
    monkeypatch.setattr(PortfolioAssistant, "_call_provider", lambda *_, **__: {"choices": [{"message": {"tool_calls": [{"id": "bad", "function": {"name": "execute_sql", "arguments": "{}"}}]}}]})
    identifier = start(env)
    env.run()
    result = job(env, identifier)
    assert result["status"] == "failed" and result["code"] == "request_limit"
    assert result["counts"]["model_requests"] == 5
    assert result["counts"]["rest_requests"] == 2
    assert env.state.fetched == []


def test_provider_exception_is_logged_via_application_outcome_without_secret(environment):
    env = environment
    env.state.fetch_error = True
    identifier = start(env)
    env.run()
    result = job(env, identifier)
    assert result["summary"]["unavailable"] == 3
    assert "synthetic-secret" not in str(result)
    assert all(item["code"] == "provider_unavailable" for item in env.state.saved[:3])


def test_jobs_require_auth_owner_role_and_csrf_and_cannot_finalize_early(environment):
    env = environment
    assert env.client.post(PREFIX + "/ai", json={}).status_code == 401
    viewer = {"Authorization": "Bearer viewer", "X-CSRF-Token": "synthetic-csrf"}
    assert env.client.post(PREFIX + "/ai", headers=viewer, json={}).status_code == 403
    assert env.client.post(PREFIX + "/ai", headers={"Authorization": "Bearer operator"}, json={}).status_code == 403
    identifier = start(env)
    assert env.client.get(PREFIX + "/ai/" + identifier, headers={"Authorization": "Bearer other"}).status_code == 404
    response = env.client.post(PREFIX + "/ai/" + identifier + "/finalize", headers=env.headers)
    assert response.status_code == 409
    assert env.state.saved == []
    assert env.client.get(PREFIX + "/status", headers=viewer).status_code == 200
    env.run()
    assert env.client.post(PREFIX + "/ai/" + identifier + "/finalize", headers=env.headers).status_code == 200
    assert len(env.state.saved) == 4


def test_duplicate_click_does_not_spawn_another_worker(environment):
    env = environment
    first = start(env)
    second = start(env)
    assert first == second
    assert len(DeferredThread.workers) == 1


def test_large_candidate_inventory_reports_capped_coverage(environment):
    env = environment
    env.state.items = [candidate("ITEM" + str(index)) for index in range(200)]
    env.state.total = 250
    env.settings["enabled"] = False
    identifier = start(env)
    env.run()
    result = job(env, identifier)
    assert result["summary"]["total_candidates"] == 250
    assert result["summary"]["not_attempted"] == 247
    assert result["coverage"] == {"inventory_truncated": True, "listed_candidates": 200}
    assert len(result["outcomes"]) == 200


def test_expired_session_never_uses_a_privileged_fallback(environment, monkeypatch):
    env = environment
    def model(*_, **__):
        env.state.expired = True
        return decision(env.state.items[0]["security_key"])
    monkeypatch.setattr(PortfolioAssistant, "_call_provider", model)
    identifier = start(env)
    env.run()
    env.state.expired = False
    result = job(env, identifier)
    assert result["status"] == "failed" and result["code"] == "authentication_expired"
    assert result["counts"]["model_requests"] == 1
    assert result["counts"]["rest_requests"] == 3
    assert env.state.fetched == [] and env.state.saved == []


def test_coordinator_has_no_database_or_filesystem_portfolio_channel():
    source = Path("app/security_enrichment.py").read_text()
    tree = ast.parse(source)
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
    assert not {"sqlite3", "sqlalchemy", "LocalPortfolioStore", "psycopg", "Path", "open"} & imported
    run = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "run")
    called = {node.func.attr for node in ast.walk(run) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not {"_candidate_reader", "_security_fetcher", "_outcome_reader", "_outcome_writer", "get_preference", "set_preference", "execute"} & called


def preflight(env, results, *, research_available=True):
    env.manager._candidate_reader = lambda: {"items": deepcopy(env.state.items), "total_count": env.state.total,
        "preflight_outcomes": deepcopy(results), "research_available": research_available}
    captured = []
    def save(outcomes, user_id, request_id, **kwargs):
        captured.append(deepcopy(kwargs))
        env.state.saved.extend(deepcopy(outcomes))
        return outcomes
    env.manager._outcome_writer = save
    return captured


def test_api_preflight_resolves_information_without_calling_ai(environment):
    env = environment
    results = [{**item, "status": "updated", "code": "data_found", "available_fields": ["prices", "profile"], "missing_fields": []}
               for item in env.state.items[:3]]
    captured = preflight(env, results)
    env.settings["enabled"] = False
    identifier = start(env)
    env.run()
    result = job(env, identifier)
    assert result["status"] == "completed" and result["code"] == "partial_data"
    assert result["counts"]["model_requests"] == 0 and result["counts"]["rest_requests"] == 2
    assert result["summary"]["updated"] == 3 and not env.state.fetched
    assert captured[0]["proposal"] is None


def test_missing_search_configuration_runs_no_model_and_preserves_api_partial_result(environment):
    env = environment
    results = [{**item, "status": "partial" if index == 0 else "unavailable", "code": "data_unavailable",
                "available_fields": ["profile"] if index == 0 else [], "missing_fields": ["prices"]}
               for index, item in enumerate(env.state.items[:3])]
    preflight(env, results, research_available=False)
    identifier = start(env)
    env.run()
    result = job(env, identifier)
    assert result["status"] == "completed"
    assert result["counts"]["model_requests"] == 0 and result["counts"]["rest_requests"] == 2
    assert result["outcomes"][0]["status"] == "partial"
    assert result["outcomes"][1]["code"] == "research_unavailable"
    assert result["outcomes"][1]["attempted"] is True  # Ordinary APIs already attempted it.


def test_real_fetched_evidence_and_wrapped_model_proposal_cross_finalization_rest(environment, monkeypatch):
    env = environment
    env.state.items, env.state.total = env.state.items[:1], 1
    item = env.state.items[0]
    preflight_result = {**item, "status": "unavailable", "code": "data_unavailable", "available_fields": [], "missing_fields": ["prices", "profile"]}
    captured = preflight(env, [preflight_result])
    evidence = [{"url": "https://example.invalid/source", "text": "A NASDAQ USD Last 123.45 on 06 November 2026", "retrieved_at": "2026-11-07T00:00:00+00:00"}]
    env.manager._security_fetcher = lambda candidate, field: {"evidence": evidence, "source_status": "data_found"}
    proposal = {"observations": [{"security_key": item["security_key"], "price_input": 123.45}], "profiles": []}
    responses = iter([decision(item["security_key"]), {"choices": [{"message": {"content": json.dumps({"answer": json.dumps(proposal), "support_status": "answered"})}}]}])
    monkeypatch.setattr(PortfolioAssistant, "_call_provider", lambda *_, **__: next(responses))
    identifier = start(env)
    env.run()
    result = job(env, identifier)
    assert result["counts"]["rest_requests"] == 3 and result["counts"]["model_requests"] == 2
    assert captured[0]["evidence_by_key"] == {item["security_key"]: evidence}
    assert json.loads(captured[0]["proposal"]) == proposal
    # A fetched page and a model proposal do not establish a saved observation.
    assert result["summary"]["updated"] == 0 and result["outcomes"][0]["code"] == "evidence_rejected"


def test_only_application_validated_outcomes_can_report_saved_web_fields(environment, monkeypatch):
    env = environment
    env.state.items, env.state.total = env.state.items[:1], 1
    item = env.state.items[0]
    preflight(env, [{**item, "status": "unavailable", "code": "data_unavailable", "available_fields": [], "missing_fields": ["prices"]}])
    evidence = [{"url": "https://example.invalid/source", "text": "synthetic fetched evidence", "retrieved_at": "2026-11-07T00:00:00+00:00"}]
    env.manager._security_fetcher = lambda candidate, field: {"evidence": evidence, "source_status": "data_found"}
    responses = iter([decision(item["security_key"]), answer()])
    monkeypatch.setattr(PortfolioAssistant, "_call_provider", lambda *_, **__: next(responses))
    def app_owned_save(outcomes, *args, **kwargs):
        assert kwargs["evidence_by_key"] == {item["security_key"]: evidence}
        return [{**outcome, "status": "updated", "code": "data_found", "missing_fields": [], "available_fields": ["prices"]} for outcome in outcomes]
    env.manager._outcome_writer = app_owned_save
    identifier = start(env)
    env.run()
    result = job(env, identifier)
    assert result["status"] == "completed" and result["code"] == "data_found"
    assert result["summary"]["updated"] == 1 and result["portfolio_refresh_required"] is True


def test_closed_after_research_cannot_keep_data_found_job_code(environment):
    env = environment
    env.manager._outcome_writer = lambda outcomes, *args: [{**outcome, "status": "not_attempted", "code": "not_open",
        "available_fields": [], "missing_fields": [], "attempted": False} for outcome in outcomes]
    identifier = start(env)
    env.run()
    result = job(env, identifier)
    assert result["code"] != "data_found" and result["summary"]["updated"] == 0
    assert result["portfolio_refresh_required"] is False


@pytest.mark.parametrize("valid", [True, False])
def test_application_finalizer_validates_source_saves_and_logs_real_outcome(environment, monkeypatch, valid):
    """Exercise the real application callbacks with synthetic storage, never a DB."""
    from app import main
    env = environment
    item = {**env.state.items[0], "missing_fields": ["prices"]}
    metadata = {**item, "location": "US", "name": "Example Incorporated", "quantity": 4,
                "id": "synthetic-security-id", "created_at": "2020-01-01", "updated_at": "2020-01-02"}
    saved_prices, notes, logs = [], {}, []
    class FakeStore:
        def manual_security(self, symbol, market):
            return deepcopy(metadata)
        def save_prices(self, rows):
            saved_prices.extend(deepcopy(rows))
        def get_preference(self, key, default):
            return deepcopy(notes.get(key, default))
        def set_preference(self, key, value):
            notes[key] = deepcopy(value)
    def inventory(*, preflight=False, limit=200):
        items = [] if saved_prices else [deepcopy(item)]
        payload = {"items": items, "total_count": len(items), "truncated": False}
        if preflight:
            payload.update(research_available=True, preflight_outcomes=[{**item, "status": "unavailable", "code": "data_unavailable",
                "missing_fields": ["prices"], "available_fields": []}])
        return payload
    day = date.today().isoformat()
    quote = "A NASDAQ USD Last 123.45 on " + day
    source = {"url": "https://example.invalid/quoted-price", "text": quote,
              "retrieved_at": datetime.now(timezone.utc).isoformat()}
    proposal = {"observations": [{"security_key": item["security_key"], "price_input": 123.45,
        "price_date": day, "currency": "USD", "quote_unit": "currency", "price_basis": "last", "observed_at": None,
        "source_url": source["url"], "evidence_quote": quote if valid else "fabricated price evidence"}], "profiles": []}
    monkeypatch.setattr(main, "local_store", FakeStore())
    monkeypatch.setattr(main, "_enrichment_candidates", inventory)
    monkeypatch.setattr(main, "enriched_local_holdings", lambda **_: [{"holding": metadata}])
    monkeypatch.setattr(main, "to_dict", lambda value: value)
    monkeypatch.setattr(main, "research_sources", lambda *_: {"evidence": [source], "source_status": "evidence_found"})
    monkeypatch.setattr(main, "_record_log", lambda *args, **kwargs: logs.append(kwargs))
    monkeypatch.setattr(main, "clear_portfolio_cache", lambda: None)
    env.manager._candidate_reader = lambda: main._enrichment_candidates(preflight=True)
    env.manager._security_fetcher = main._enrichment_research_security
    env.manager._outcome_writer = main._save_enrichment_outcomes
    responses = iter([decision(item["security_key"]), {"choices": [{"message": {"content": json.dumps({"answer": json.dumps(proposal), "support_status": "answered"})}}]}])
    monkeypatch.setattr(PortfolioAssistant, "_call_provider", lambda *_, **__: next(responses))
    identifier = start(env)
    env.run()
    result = job(env, identifier)
    assert result["status"] == "completed", result
    assert result["counts"]["rest_requests"] == 3 and result["counts"]["model_requests"] == 2
    assert len(saved_prices) == int(valid)
    assert result["summary"]["updated"] == int(valid)
    assert len(logs) == 1
    assert logs[0]["code"] == ("data_found" if valid else "evidence_rejected")
    persisted = notes["security_enrichment_outcomes_v1"][item["security_key"]]
    assert persisted["code"] == logs[0]["code"]
    if valid:
        assert set(saved_prices[0]) == {"symbol", "stock_market", "currency", "asset_class", "location", "price_input", "price_date", "source", "comments"}
        evidence = json.loads(saved_prices[0]["comments"])
        assert evidence["source_url"] == source["url"] and evidence["evidence_quote"] == quote


def metadata_application(monkeypatch, *, industry="", name="A", quantity=3):
    from app import main
    state = SimpleNamespace(holding={"symbol": "A", "stock_market": "NASDAQ", "currency": "USD", "location": "US",
                                    "asset_class": "EQUITY", "quantity": quantity, "name": name, "industry": industry},
                            profiles=[], prices=[], preferences={}, overrides={}, cached={})
    class FakeStore:
        def manual_security(self, symbol, market):
            return deepcopy(state.holding)
        def list_security_industry_overrides(self):
            return list(deepcopy(state.overrides).values())
        def save_manual_security(self, value):
            state.profiles.append(deepcopy(value))
            state.holding.update(value)
        def save_security_industry_override(self, value):
            state.profiles.append(deepcopy(value))
            state.overrides[value["symbol"]] = deepcopy(value)
        def save_prices(self, values):
            state.prices.extend(deepcopy(values))
        def get_preference(self, key, default):
            return deepcopy(state.preferences.get(key, default))
        def set_preference(self, key, value):
            state.preferences[key] = deepcopy(value)
    monkeypatch.setattr(main, "local_store", FakeStore())
    monkeypatch.setattr(main, "enriched_local_holdings", lambda **_: [{"holding": deepcopy(state.holding), "missing": ["industry"],
        "price_ranges": {"1y": {"current": 1, "current_date": date.today().isoformat()}}}])
    monkeypatch.setattr(main, "hub", lambda: SimpleNamespace(cached_profile=lambda *args, **kwargs: deepcopy(state.cached)))
    monkeypatch.setattr(main, "to_dict", lambda value: value)
    return main, state


def test_candidates_use_effective_metadata_and_only_nonzero_current_holdings(monkeypatch):
    main, state = metadata_application(monkeypatch, industry="Known industry")
    for quantity in (3, -2, 1e-12):
        state.holding["quantity"] = quantity
        result = main._enrichment_candidates()["items"]
        assert len(result) == 1
        assert result[0]["needs_name"] is True and result[0]["needs_industry"] is False
        assert result[0]["quote_unit"] == "currency"
    state.cached = {"name": "Cached exact name"}
    assert main._enrichment_candidates()["items"] == []  # Stale missing-industry marker ignored.
    state.holding["quantity"] = 0
    state.cached = {}
    assert main._enrichment_candidates()["total_count"] == 0
    state.holding["quantity"] = 4  # Reopened holding remains eligible.
    assert len(main._enrichment_candidates()["items"]) == 1


def test_verified_web_name_and_industry_complete_real_candidate_gaps_with_provenance(monkeypatch):
    main, state = metadata_application(monkeypatch)
    candidate = main._enrichment_candidates()["items"][0]
    excerpt = "A NASDAQ Company name: Example Incorporated Industry: Software"
    source = {"url": "https://example.invalid/profile", "text": excerpt, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    proposal = {"profiles": [{"security_key": candidate["security_key"], "field": field, "value": value,
        "source_url": source["url"], "evidence_quote": excerpt} for field, value in (("name", "Example Incorporated"), ("industry", "Software"))]}
    results = main._apply_enrichment_proposals(proposal, {candidate["security_key"]: [source]}, {candidate["security_key"]: candidate})
    assert results[candidate["security_key"]]["status"] == "updated"
    assert len(state.profiles) == 2 and not state.prices
    assert state.holding["name"] == "Example Incorporated"
    assert main._enrichment_candidates()["items"] == []
    assert len(state.preferences["security_enrichment_sources_v1"]) == 2


def test_ai_profile_cannot_replace_existing_user_industry(monkeypatch):
    main, state = metadata_application(monkeypatch, industry="User classification")
    candidate = main._enrichment_candidates()["items"][0]
    excerpt = "A NASDAQ Industry: Another industry"
    source = {"url": "https://example.invalid/profile", "text": excerpt, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    proposal = {"profiles": [{"security_key": candidate["security_key"], "field": "industry", "value": "Another industry",
                              "source_url": source["url"], "evidence_quote": excerpt}]}
    results = main._apply_enrichment_proposals(proposal, {candidate["security_key"]: [source]}, {candidate["security_key"]: candidate})
    assert not state.profiles and state.holding["industry"] == "User classification"
    assert results[candidate["security_key"]]["available_fields"] == []


def test_close_after_preparation_before_save_prevents_any_write(monkeypatch):
    main, state = metadata_application(monkeypatch)
    candidate = main._enrichment_candidates()["items"][0]
    excerpt = "A NASDAQ Company name: Example Incorporated"
    source = {"url": "https://example.invalid/profile", "text": excerpt, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    real_validate = main.validate_proposals
    def validate_and_close(*args):
        verified = real_validate(*args)
        state.holding["quantity"] = 0  # Closes after prepared metadata, before write.
        return verified
    monkeypatch.setattr(main, "validate_proposals", validate_and_close)
    proposal = {"profiles": [{"security_key": candidate["security_key"], "field": "name", "value": "Example Incorporated",
                              "source_url": source["url"], "evidence_quote": excerpt}]}
    results = main._apply_enrichment_proposals(proposal, {candidate["security_key"]: [source]}, {candidate["security_key"]: candidate})
    assert not state.profiles and not state.prices and not state.preferences
    assert results[candidate["security_key"]]["available_fields"] == []


def test_close_during_final_apply_does_not_persist_or_log_success(monkeypatch):
    main, state = metadata_application(monkeypatch)
    candidate = main._enrichment_candidates()["items"][0]
    def apply_and_close(*args):
        state.holding["quantity"] = 0
        return {candidate["security_key"]: {**candidate, "status": "updated", "code": "data_found", "available_fields": ["profile"], "missing_fields": []}}
    monkeypatch.setattr(main, "_apply_enrichment_proposals", apply_and_close)
    monkeypatch.setattr(main, "_record_log", lambda *args, **kwargs: pytest.fail("Closed holdings must not be logged as attempted"))
    result = main._save_enrichment_outcomes([{**candidate, "status": "unavailable", "code": "data_unavailable"}], "operator", "job",
                                            proposal="{}", candidates={candidate["security_key"]: candidate})
    assert result[0]["code"] == "not_open" and result[0]["status"] == "not_attempted"
    assert not state.preferences["security_enrichment_outcomes_v1"]


def test_expired_research_keeps_fields_already_retrieved_by_normal_apis(environment, monkeypatch):
    env = environment
    env.state.items, env.state.total = env.state.items[:1], 1
    item = env.state.items[0]
    preflight(env, [{**item, "status": "partial", "code": "partial_data", "available_fields": ["profile"], "missing_fields": ["prices"]}])
    def model(*args, **kwargs):
        env.state.expired = True
        return decision(item["security_key"])
    monkeypatch.setattr(PortfolioAssistant, "_call_provider", model)
    identifier = start(env)
    env.run()
    env.state.expired = False
    result = job(env, identifier)
    assert result["status"] == "failed" and result["code"] == "authentication_expired"
    assert result["summary"]["partial"] == 1 and result["outcomes"][0]["available_fields"] == ["profile"]
    assert result["outcomes"][0]["missing_fields"] == ["prices"]
    assert not env.state.saved  # Final REST never switches to privileged identity.


def test_rejected_web_proposal_does_not_discard_earlier_api_fields(monkeypatch):
    main, state = metadata_application(monkeypatch)
    candidate = main._enrichment_candidates()["items"][0]
    monkeypatch.setattr(main, "_apply_enrichment_proposals", lambda *args: {candidate["security_key"]: {
        **candidate, "status": "unavailable", "code": "evidence_rejected", "available_fields": [], "missing_fields": ["profile"]}})
    monkeypatch.setattr(main, "_record_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "clear_portfolio_cache", lambda: None)
    outcome = {**candidate, "status": "partial", "code": "partial_data", "available_fields": ["prices"], "missing_fields": ["profile"]}
    result = main._save_enrichment_outcomes([outcome], "operator", "job", proposal="{}", candidates={candidate["security_key"]: candidate})
    assert result[0]["status"] == "partial" and result[0]["code"] == "evidence_rejected"
    assert result[0]["available_fields"] == ["prices"] and result[0]["missing_fields"] == ["profile"]


def test_dashboard_price_research_defaults_to_codex_independently_of_chat(monkeypatch):
    from app import main
    monkeypatch.delenv("PORTFOLIO_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.delenv("PORTFOLIO_CODEX_SOCKET", raising=False)
    raw = {"llm": {"provider": "local_claude", "enabled": False, "model": "chat-model", "reasoning_effort": "high",
                   "codex_socket": "/synthetic-shared-bridge.sock"}}
    monkeypatch.setattr(main, "config", SimpleNamespace(raw=raw))
    settings = main._enrichment_assistant_settings()
    assert settings["provider"] == "local_codex" and settings["model"] == "gpt-6.1-sol"
    assert settings["reasoning_effort"] == "medium" and settings["max_tool_loops"] == 5
    assert settings["codex_socket"] == "/synthetic-shared-bridge.sock" and settings["enabled"] is False
    assert assistant_settings(raw)["provider"] == "local_claude" and assistant_settings(raw)["model"] == "chat-model"


def test_dashboard_price_research_supports_selected_claude(monkeypatch):
    from app import main
    monkeypatch.delenv("PORTFOLIO_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.setattr(main, "config", SimpleNamespace(raw={"llm": {"enabled": True}, "price_agent": {"provider": "claude"}}))
    settings = main._enrichment_assistant_settings()
    assert settings["provider"] == "local_claude" and settings["model"] == "sonnet"
    assert settings["reasoning_effort"] == "medium" and settings["enabled"] is True


def test_dashboard_forwards_explicit_research_model_effort_and_bounded_settings(monkeypatch):
    from app import main
    monkeypatch.delenv("PORTFOLIO_ASSISTANT_PROVIDER", raising=False)
    raw = {"llm": {"enabled": True, "model": "chat-model", "max_tool_loops": 1, "reasoning_effort": "low"},
           "price_agent": {"provider": "claude", "model": "explicit-price-model", "reasoning_effort": "high",
                           "max_model_calls": 999, "timeout_seconds": 999}}
    monkeypatch.setattr(main, "config", SimpleNamespace(raw=raw))
    settings = main._enrichment_assistant_settings()
    assert (settings["provider"], settings["model"], settings["reasoning_effort"]) == ("local_claude", "explicit-price-model", "high")
    assert settings["max_tool_loops"] == 5 and settings["timeout_seconds"] == 110
    assert assistant_settings(raw)["max_tool_loops"] == 1 and assistant_settings(raw)["model"] == "chat-model"
