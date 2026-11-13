"""Provider, persistence and asynchronous-publication contract checks."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.credit_rating_service import CreditRatingService, PREFIX, SCHEMA, select_observation
from app.credit_ratings_api import fetch, registry
from app.providers import SqliteCache
from app.us_market_providers import RequestBudget
from app.llm_assistant import PortfolioAssistant, assistant_settings
from app.security_research_tools import ResearchSession, WebRequestBudget


CANDIDATE = {"security_key": "JPM|NYSE|USD", "symbol": "JPM", "stock_market": "NYSE", "currency": "USD",
             "has_open_position": True,
             "asset_class": "EQUITY", "asset_sub_class": "STOCK", "name": "JPMorgan Chase & Co.",
             "issuer_name": "JPMorgan Chase & Co."}
TABLE = """Credit Ratings
JPMorgan Chase & Co.
 | Moody's | S&P | Fitch
Outlook | Stable | Stable | Stable
Long-term issuer rating | A1 | A | AA-
JPMorgan Chase & Co. Credit Ratings
JPMorgan Chase Bank, N.A.
 | Moody's | S&P | Fitch
Outlook | Stable | Stable | Stable
Long-term issuer rating | Aa2 | AA- | AA
JPMorgan Chase Bank, N.A. Credit Ratings
"""


def source(*, text=TABLE, url="https://www.jpmorganchase.com/ir/fixed-income", fetched=None):
    return {"source_id": "source-parent", "url": url, "title": "Issuer IR credit ratings", "text": text,
            "retrieved_at": fetched or datetime.now(timezone.utc).isoformat()}


def api_payload():
    return {"results": [{"identifierType": "TICKER", "identifierValue": "JPM",
        "s&pRatingsData": [{"entityLegalName": "JPMorgan Chase & Co.", "rxEntityId": "parent-sp",
            "s&pData": [{"ratingType": "Long-Term Issuer Credit Rating", "ratingValue": "A", "ratingDate": "2026-06-01",
                "lastReviewDate": "2026-10-01", "creditWatchOutlookIndicator": "Outlook", "creditWatchOutlookValue": "Stable"}]},
            {"entityLegalName": "JPMorgan Chase Bank, N.A.", "rxEntityId": "bank-sp",
             "s&pData": [{"ratingType": "Long-Term Issuer Credit Rating", "ratingValue": "AA-", "ratingDate": "2026-06-01"}]}],
        "moodysRatingsData": [{"entityLegalName": "JPMorgan Chase & Co.", "moodysOrgId": "parent-moodys",
            "moodysData": [{"ratingTypeText": "Long-Term Issuer Rating", "ratingValue": "A1", "ratingDate": "2026-06-01"},
                {"ratingTypeText": "Outlook", "ratingValue": "Stable"}]}],
        "fitchRatingsData": [{"entityLegalName": "JPMorgan Chase & Co.", "fitchIssuerId": "parent-fitch",
            "fitchData": [{"ratingTypeName": "Long-Term Issuer Default Rating", "ratingValue": "AA-",
                "ratingEffectiveDate": "2026-06-01", "ratingAlertDescription": "Rating Outlook Stable"}]}]}]}


@pytest.fixture
def environment(tmp_path):
    cache = SqliteCache(tmp_path / "cache.sqlite", ttl_hours=24)
    inventory = [deepcopy(CANDIDATE)]
    settings = {"verification_ttl_days": 30}
    service = CreditRatingService(cache=lambda: cache, settings=lambda: settings,
        inventory=lambda: inventory, research_settings=lambda: {"max_web_calls": 8, "search_provider": "auto"})
    return service, cache, inventory, settings


def test_cache_only_read_retains_all_agencies_and_survives_new_service_instance(environment):
    service, cache, inventory, settings = environment
    before = service.read(inventory[0])
    assert [r["status"] for r in before["ratings"]] == ["not_checked"] * 3
    rows = service._accept_sources(inventory[0], [source()])
    assert len(rows) == 3
    assert service.publish(inventory[0], rows)
    after = service.read(inventory[0])
    assert after["status"] == "ok"
    assert {r["agency"]: r["rating"] for r in after["ratings"]} == {"moodys": "A1", "sp": "A", "fitch": "AA-"}
    assert all(r["reason_code"] == "data_found" and r["rating_date"] is None for r in after["ratings"])
    restarted = CreditRatingService(cache=lambda: SqliteCache(cache.path, ttl_hours=24), settings=lambda: settings,
        inventory=lambda: inventory, research_settings=lambda: {})
    assert restarted.read(inventory[0]) == after


def test_main_inventory_uses_listing_bound_issuer_profile_and_excludes_noncompany_instruments(monkeypatch):
    from types import SimpleNamespace
    from app import main
    common = {"stock_market": "NASDAQ", "currency": "USD", "asset_class": "EQUITY", "instrument_type": "STOCK"}
    records = [{**common, "symbol": "AAPL", "name": "My Apple label"},
        {**common, "symbol": "PRIVATE", "stock_market": "PRIVATE", "name": "Private company"},
        {**common, "symbol": "OPTION", "instrument_type": "OPTION", "name": "Option"},
        {**common, "symbol": "ETF", "asset_class": "ETF", "name": "Fund"}]
    monkeypatch.setattr(main, "local_store", SimpleNamespace(list_manual_securities=lambda: records, holdings=lambda **kwargs: []))
    monkeypatch.setattr(main, "hub", lambda: SimpleNamespace(cached_profile=lambda *args, **kwargs:
        {"name": "Apple Inc.", "website": "https://www.apple.com/"}))
    candidate, = main._credit_rating_inventory()
    assert candidate["symbol"] == "AAPL" and candidate["issuer_name"] == "Apple Inc."
    assert candidate["name"] == "My Apple label" and candidate["verified_issuer_domains"] == ["apple.com"]
    assert candidate["has_open_position"] is False


def test_holdings_batch_is_viewer_cache_only_deduplicated_and_retains_financial_scope(environment, monkeypatch):
    service, _, inventory, _ = environment
    candidate = inventory[0]
    rows = service._accept_sources(candidate, [source()])
    service.publish(candidate, rows)
    captures = []
    service._inventory = lambda: (captures.append(True) or inventory)
    def forbidden(*args, **kwargs):
        raise AssertionError("A cache-only table read called a provider or AI")
    monkeypatch.setattr(service, "check_apis", forbidden)
    monkeypatch.setattr(service, "_research_settings", forbidden)
    app = FastAPI()
    @app.middleware("http")
    async def authenticate(request, call_next):
        if request.headers.get("X-Test-Viewer") == "yes":
            request.state.auth_user = {"id": "viewer", "role": "Viewer"}
        return await call_next(request)
    app.include_router(service.router())
    client = TestClient(app)
    path = PREFIX + "/summaries"
    assert client.get(path).status_code == 401
    response = client.get(path, headers={"X-Test-Viewer": "yes"}, params=[
        ("security_keys", candidate["security_key"].lower()), ("security_keys", candidate["security_key"]),
        ("security_keys", "MISSING|NYSE|USD")])
    assert response.status_code == 200
    assert len(captures) == 1
    result = response.json()
    assert result["summary_only"] is True and len(result["items"]) == 1
    assert result["not_found_keys"] == ["MISSING|NYSE|USD"]
    item, = result["items"]
    assert item["summary_only"] is True
    assert {row["agency"]: row["rating"] for row in item["ratings"]} == {"moodys": "A1", "sp": "A", "fitch": "AA-"}
    assert all(row["scope"] == "issuer" and row["term"] == "long_term" and row["outlook"] == "stable" for row in item["ratings"])
    assert "evidence_quote" not in json.dumps(result) and "claims" not in json.dumps(result)
    # The full overview continues to expose the original retained evidence.
    overview = client.get(PREFIX, headers={"X-Test-Viewer": "yes"},
        params={key: candidate[key] for key in ("symbol", "stock_market", "currency")}).json()
    assert overview["ratings"][0]["sources"][0]["evidence_quote"] == rows[0]["sources"][0]["evidence_quote"]
    assert "JPMorgan Chase Bank" not in overview["ratings"][0]["sources"][0]["evidence_quote"]


def test_holdings_batch_rejects_invalid_bounds_and_empty_batch_never_reads_inventory(environment):
    service, _, _, _ = environment
    service._inventory = lambda: (_ for _ in ()).throw(AssertionError("Empty batch captured inventory"))
    assert service.summaries([]) == {"items": [], "not_found_keys": [], "summary_only": True}
    for keys in ([""] , [" "], ["x" * 301], [CANDIDATE["security_key"]] * 201):
        with pytest.raises(Exception) as error:
            service.summaries(keys)
        assert error.value.status_code == 422


def test_batch_and_overview_recompute_ancillary_freshness_from_its_own_dates_without_writes(environment):
    service, cache, inventory, _ = environment
    candidate = inventory[0]
    old = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    rows = service._accept_sources(candidate, [source(fetched=old)])
    ancillary = {**rows[0], "rating_type": "senior_unsecured_class", "primary_eligible": False}
    service.publish(candidate, [ancillary])
    before = cache.get_security_snapshot("credit_ratings", candidate["security_key"], SCHEMA)
    item, = service.summaries([candidate["security_key"]])["items"]
    primary = item["ratings"][0]
    assert primary["status"] == "unavailable" and primary["rating"] is None
    saved, = primary["observations"]
    assert saved["rating"] == "A1" and saved["rating_type"] == "senior_unsecured_class"
    assert saved["stale"] and saved["outlook_stale"] and saved["outlook_fetched_at"] == old
    assert service.read(candidate)["ratings"][0]["observations"][0]["stale"] is True
    assert cache.get_security_snapshot("credit_ratings", candidate["security_key"], SCHEMA) == before


def test_documented_api_maps_three_native_schemas_without_parent_bank_or_date_substitution(environment):
    service, _, inventory, settings = environment
    settings["spglobal"] = {"enabled": True, "bearer_token": "synthetic-license-token"}
    seen = []
    def handler(request):
        seen.append(request)
        assert request.url.path == "/agencyratings/api/v1/issuer"
        assert request.url.params["creditRatingAgency"] == "S&P + MOODY'S + FITCH"
        return httpx.Response(200, json=api_payload())
    service._api_transport = httpx.MockTransport(handler)
    result = service.candidates(security_keys=[CANDIDATE["security_key"]])
    assert len(seen) == 1
    assert result["preflight_outcomes"][0]["status"] == "updated"
    rows = service.read(inventory[0])["ratings"]
    assert {r["agency"]: r["rating"] for r in rows} == {"moodys": "A1", "sp": "A", "fitch": "AA-"}
    assert all(r["rating_date"] == "2026-06-01" and r["outlook"] == "stable" for r in rows)
    assert "synthetic-license-token" not in json.dumps(result)


@pytest.mark.parametrize("status,code", [(401, "authentication_required"), (403, "entitlement_required"), (429, "rate_limited"), (503, "provider_unavailable")])
def test_unavailable_licensed_api_preserves_fallback_and_never_leaks_response(status, code):
    settings = {"spglobal": {"bearer_token": "synthetic-token"}}
    result = fetch(CANDIDATE, settings, RequestBudget(1),
        transport=httpx.MockTransport(lambda _: httpx.Response(status, text="provider-credentials-must-not-leak")))
    assert result["sources"] == [] and result["provider_status"][0]["status"] == code
    assert "provider-credentials" not in str(result) and "synthetic-token" not in str(result)
    assert registry({})[0]["configured"] is False


def test_partial_api_data_keeps_missing_agencies_research_eligible(environment):
    service, _, inventory, settings = environment
    settings["spglobal"] = {"bearer_token": "synthetic-token"}
    payload = api_payload()
    payload["results"][0].pop("moodysRatingsData")
    payload["results"][0].pop("fitchRatingsData")
    service._api_transport = httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    result = service.candidates(security_keys=[CANDIDATE["security_key"]])
    assert result["items"][0]["missing_agencies"] == ["moodys", "fitch"]
    assert result["preflight_outcomes"][0]["research_eligible"] is True
    assert next(r for r in service.read(inventory[0])["ratings"] if r["agency"] == "sp")["rating"] == "A"


def test_failed_attempt_is_persisted_without_erasing_verified_ratings_or_refreshing_them(environment):
    service, cache, inventory, _ = environment
    candidate = inventory[0]
    service.publish(candidate, service._accept_sources(candidate, [source()]))
    before = service.read(candidate)
    service.record_attempt(candidate, ["moodys", "sp", "fitch"], "source_read_failed")
    after = service.read(candidate)
    assert [r["rating"] for r in after["ratings"]] == [r["rating"] for r in before["ratings"]]
    assert after["fetched_at"] == before["fetched_at"]
    assert all(r.get("checked_at") for r in after["ratings"])
    empty = {**candidate, "symbol": "EMPTY", "security_key": "EMPTY|NYSE|USD"}
    inventory.append(empty)
    service.record_attempt(empty, ["sp"], "data_unavailable")
    assert [r["status"] for r in service.read(empty)["ratings"]] == ["not_checked", "unavailable", "not_checked"]


def test_identity_edit_and_out_of_order_refresh_cannot_publish_old_evidence(environment):
    service, _, inventory, _ = environment
    candidate = deepcopy(inventory[0])
    original_rows = service._accept_sources(candidate, [source()])
    service.publish(candidate, original_rows)
    old_start = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    assert service.publish(candidate, original_rows, started_at=old_start) is False
    inventory[0]["issuer_name"] = "JPMorgan Chase Bank, N.A."
    assert service.publish(candidate, original_rows) is False
    assert service.read(inventory[0])["status"] == "unavailable"


def test_same_axis_conflict_retains_both_sources_and_hides_unresolved_grade(environment):
    service, _, inventory, _ = environment
    candidate = inventory[0]
    first = source()
    second = source(text=TABLE.replace("| A1 | A | AA-", "| A1 | A- | AA-"), url="https://www.jpmorganchase.com/ir/ratings")
    service.publish(candidate, service._accept_sources(candidate, [first, second]))
    row = next(r for r in service.read(candidate)["ratings"] if r["agency"] == "sp")
    assert row["status"] == "conflicting" and row["rating"] is None
    assert {s["url"] for s in row["sources"]} == {first["url"], second["url"]}


def test_fresh_grade_does_not_refresh_preserved_older_forward_evidence(environment):
    service, _, inventory, _ = environment
    candidate = inventory[0]
    old = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    service.publish(candidate, service._accept_sources(candidate, [source(fetched=old)]))
    no_outlook = TABLE.replace("Outlook | Stable | Stable | Stable\n", "")
    service.publish(candidate, service._accept_sources(candidate, [source(text=no_outlook)]))
    rows = service.read(candidate)["ratings"]
    assert all(r["stale"] is False and r["outlook"] == "stable" and r["outlook_stale"] for r in rows)
    assert service.missing(service.read(candidate)) == ["moodys", "sp", "fitch"]
    assert all(r["outlook_fetched_at"] == old for r in rows)
    assert all(any("Outlook | Stable" in s["evidence_quote"] and s["fetched_at"] == old for s in r["sources"]) for r in rows)


def test_newer_explicit_outlook_action_resolves_unchanged_grade_without_reusing_grade_date(environment):
    service, _, inventory, _ = environment
    candidate = inventory[0]
    base = service._accept_sources(candidate, [source()])[0]
    old = {**base, "outlook": "stable", "rating_date": "2026-06-01", "outlook_date": "2026-06-01",
           "source_url": "https://www.jpmorganchase.com/ir/older"}
    newer = {**base, "outlook": "negative", "rating_date": "2026-06-01", "outlook_date": "2026-11-06",
             "source_url": "https://www.jpmorganchase.com/ir/newer"}
    service.publish(candidate, [old, newer])
    result = service.read(candidate)["ratings"][0]
    assert result["status"] == "rated" and result["rating_date"] == "2026-06-01"
    assert result["outlook"] == "negative" and result["outlook_date"] == "2026-11-06"
    service.publish(candidate, [{**old, "source_url": newer["source_url"]}])
    result = service.read(candidate)["ratings"][0]
    assert result["outlook"] == "negative" and result["outlook_date"] == "2026-11-06"


def test_deposit_national_and_short_term_observations_do_not_replace_company_primary(environment):
    service, _, inventory, _ = environment
    candidate = inventory[0]
    rows = service._accept_sources(candidate, [source()])
    ancillary = {**rows[0], "rating_type": "deposit", "primary_eligible": False}
    display = select_observation([ancillary], candidate)
    assert display["status"] == "unavailable" and display["rating"] is None
    assert display["observations"][0]["rating"] == "A1"


def test_unknown_source_id_proposal_never_saves_a_rating_and_records_actual_attempt(environment):
    service, cache, inventory, _ = environment
    candidate = inventory[0]
    service.finalize([], "owner", "request", proposal={"records": [{"security_key": candidate["security_key"],
        "source_id": "forged", "record_id": "forged"}]}, evidence_by_key={candidate["security_key"]: [source()]},
        candidates={candidate["security_key"]: candidate})
    after = service.read(candidate)
    assert all(r["rating"] is None and r["status"] == "unavailable" for r in after["ratings"])
    assert cache.get_security_snapshot("credit_ratings", candidate["security_key"], SCHEMA).get("observations", []) == []


def test_third_party_source_remains_a_lead_and_does_not_offer_unpublishable_rating_records(environment):
    service, _, inventory, _ = environment
    candidate = {**inventory[0], "_request_id": "authority-request"}
    session = ResearchSession({}, WebRequestBudget(8),
        fetch=lambda url, settings: {**source(), "url": url}, resolver=lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))])
    source_id = session._add(candidate["security_key"], "https://third-party-claims.example/ratings")
    service._sessions["authority-request"] = session
    result = service.research_tool(candidate, "read", {"source_id": source_id})
    assert result["evidence"][0]["context_records"] == []
    assert result["evidence"][0]["source_authority"] == "unverified"
    assert "Long-term issuer rating" in result["evidence"][0]["text"]
    assert service.read(candidate)["status"] == "unavailable"


def test_open_scope_and_public_all_scope_keep_registered_unheld_identities_distinct(environment):
    service, _, inventory, _ = environment
    inventory.append({**CANDIDATE, "symbol": "AAPL", "security_key": "AAPL|NASDAQ|USD", "has_open_position": False})
    assert [r["symbol"] for r in service.candidates(position_scope="open")["items"]] == ["JPM"]
    assert [r["symbol"] for r in service.candidates(position_scope="all")["items"]] == ["JPM", "AAPL"]
    candidate = service.candidates(position_scope="open")["items"][0]
    rows = service._accept_sources(candidate, [source()])
    inventory[0]["has_open_position"] = False
    assert service.publish(candidate, rows) is False
    outcome, = service.finalize([], "owner", "scope-request", candidates={candidate["security_key"]: candidate})
    assert outcome["status"] == "not_attempted" and outcome["code"] == "not_open"


@pytest.mark.parametrize("grade,action,status", [("NR", "", "unrated"), ("WR", "", "withdrawn"), ("A", "Rating Withdrawal", "withdrawn"), ("D", "", "rated")])
def test_api_preserves_explicit_unrated_withdrawn_and_default_instead_of_active_old_grade(environment, grade, action, status):
    service, _, inventory, settings = environment
    settings["spglobal"] = {"bearer_token": "synthetic-token"}
    payload = api_payload()
    row = payload["results"][0]["s&pRatingsData"][0]["s&pData"][0]
    row.update(ratingValue=grade, ratingAction=action)
    service._api_transport = httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    service.candidates(security_keys=[CANDIDATE["security_key"]])
    result = next(r for r in service.read(inventory[0])["ratings"] if r["agency"] == "sp")
    assert result["status"] == status
    assert result["rating"] == (grade if status == "rated" else None)


def test_api_future_action_date_is_rejected_instead_of_silently_becoming_undated(environment):
    service, _, inventory, settings = environment
    settings["spglobal"] = {"bearer_token": "synthetic-token"}
    payload = api_payload()
    payload["results"][0]["s&pRatingsData"][0]["s&pData"][0]["ratingDate"] = "2099-01-01"
    service._api_transport = httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    service.candidates(security_keys=[CANDIDATE["security_key"]])
    result = next(r for r in service.read(inventory[0])["ratings"] if r["agency"] == "sp")
    assert result["status"] == "not_checked" and result["rating"] is None


def test_exact_issue_query_binds_identifier_without_accepting_an_issuer_row_as_issue(environment):
    service, _, inventory, settings = environment
    candidate = {**CANDIDATE, "symbol": "US46647PFL58", "secondary_symbol": "46647PFL5", "stock_market": "BOND",
        "security_key": "US46647PFL58|BOND|USD", "asset_class": "BOND", "asset_sub_class": "BOND", "name": "Informal bond name", "issuer_name": ""}
    inventory[:] = [candidate]
    settings["spglobal"] = {"bearer_token": "synthetic-token"}
    payload = {"results": [{"identifierType": "ISIN", "identifierValue": candidate["symbol"],
        "s&pRatingsData": [{"entityLegalName": "JPMorgan Chase & Co.", "rxEntityId": "parent-sp", "s&pData": [
            {"ratingType": "Global Long-Term Issue Rating", "ratingValue": "A", "ratingDate": "2026-06-01"},
            {"ratingType": "Global Long-Term Issuer Credit Rating", "ratingValue": "AA-", "ratingDate": "2026-06-01"}]}]}]}
    observed = []
    def handler(request):
        observed.append(request)
        return httpx.Response(200, json=payload)
    service._api_transport = httpx.MockTransport(handler)
    service.candidates(position_scope="all", security_keys=[candidate["security_key"]])
    assert len(observed) == 1 and observed[0].url.path.endswith("/issue")
    row = next(r for r in service.read(candidate)["ratings"] if r["agency"] == "sp")
    assert row["status"] == "rated" and row["scope"] == "issue" and row["rating"] == "A"


def test_authenticated_job_uses_fixed_rest_workflow_selected_identity_and_shared_limits(environment, monkeypatch):
    service, _, inventory, _ = environment
    app = FastAPI()
    requests, workers = [], []
    @app.middleware("http")
    async def auth(request, call_next):
        name = request.headers.get("Authorization", "").removeprefix("Bearer ")
        role = {"operator": "Operator", "other": "Operator", "viewer": "Viewer"}.get(name)
        if not role:
            return JSONResponse({"detail": "authentication_required"}, 401)
        request.state.auth_user = {"id": name, "role": role}
        if request.method != "GET" and (role == "Viewer" or request.headers.get("X-CSRF-Token") != "synthetic-csrf"):
            return JSONResponse({"detail": "forbidden"}, 403)
        requests.append((request.method, request.url.path))
        return await call_next(request)
    class Deferred:
        def __init__(self, target, args, **kwargs):
            workers.append(lambda: target(*args))
        def start(self):
            pass
    settings = assistant_settings({"llm": {"provider": "openai", "enabled": True, "api_key": "synthetic-secret", "base_url": "https://never-called.invalid", "model": "fixture"}})
    settings.update(max_tool_loops=8, max_rest_calls=8, max_web_calls=8)
    manager = service.manager(app, lambda: settings, worker_factory=Deferred)
    app.include_router(service.router())
    app.include_router(manager.router())
    client = TestClient(app)
    headers = {"Authorization": "Bearer operator", "X-CSRF-Token": "synthetic-csrf"}
    payload = {"position_scope": "all", "security_keys": [CANDIDATE["security_key"]]}
    assert client.get(PREFIX, params={"symbol": "JPM"}).status_code == 401
    assert client.post(PREFIX + "/ai", json=payload).status_code == 401
    assert client.post(PREFIX + "/ai", headers={"Authorization": "Bearer viewer", "X-CSRF-Token": "synthetic-csrf"}, json=payload).status_code == 403
    assert client.post(PREFIX + "/ai", headers={"Authorization": "Bearer operator"}, json=payload).status_code == 403
    first = client.post(PREFIX + "/ai", headers=headers, json=payload)
    assert first.status_code == 202
    identifier = first.json()["request_id"]
    assert client.post(PREFIX + "/ai", headers=headers, json=payload).json()["request_id"] == identifier
    assert len(workers) == 1
    assert client.post(PREFIX + "/ai", headers=headers, json={**payload, "security_keys": ["AAPL|NASDAQ|USD"]}).status_code == 409
    assert client.get(PREFIX + "/ai/" + identifier, headers={"Authorization": "Bearer other"}).status_code == 404
    session = ResearchSession({"search_provider": "auto"}, WebRequestBudget(8),
        fetch=lambda url, settings: {**source(), "url": url}, resolver=lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))])
    service._sessions[identifier] = session
    def model(self, *, messages, tools):
        assert {tool["function"]["name"] for tool in tools} == {"search_security_sources", "read_security_source", "follow_security_source"}
        assert "synthetic-secret" not in json.dumps(messages)
        job = manager._jobs[identifier]
        evidence = job["_evidence_by_key"].get(CANDIDATE["security_key"])
        if not evidence:
            hint = job["_candidates"][CANDIDATE["security_key"]]["source_hints"][0]
            return {"choices": [{"message": {"tool_calls": [{"id": "read-official", "function": {"name": "read_security_source",
                "arguments": json.dumps({"security_key": CANDIDATE["security_key"], "source_id": hint["source_id"]})}}]}}]}
        records = [{"security_key": CANDIDATE["security_key"], "source_id": src["source_id"], "record_id": row["record_id"]}
            for src in evidence["evidence"] for row in src["context_records"]]
        return {"choices": [{"message": {"content": json.dumps({"records": records})}}]}
    monkeypatch.setattr(PortfolioAssistant, "_call_provider", model)
    workers[0]()
    job = client.get(PREFIX + "/ai/" + identifier, headers=headers).json()
    assert job["code"] == "data_found" and job["status"] == "completed", json.dumps({"failure": job.get("failure"), "trace": manager._jobs[identifier]["_trace"]})
    assert job["counts"]["rest_requests"] == 3 and job["counts"]["model_requests"] == 2 and job["counts"]["web_requests"] == 1
    assert job["portfolio_refresh_required"] is False
    assert any(method == "POST" and path.endswith("/finalize") for method, path in requests)
    assert service.read(inventory[0])["status"] == "ok"
    viewer = client.get(PREFIX, params={k: CANDIDATE[k] for k in ("symbol", "stock_market", "currency")}, headers={"Authorization": "Bearer viewer"})
    assert viewer.status_code == 200 and viewer.json()["status"] == "ok"
