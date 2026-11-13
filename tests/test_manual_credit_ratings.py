"""Manual agency opinions are durable annotations, never retrieved evidence."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from app.credit_rating_service import AGENCIES, CreditRatingService, PREFIX, SCHEMA
from app.local_portfolio import LocalPortfolioStore
from app.manual_credit_ratings import normalize_manual, preference_key
from app.providers import SqliteCache
from app.security_research_tools import ResearchSession, WebRequestBudget


@pytest.fixture
def manual_env(tmp_path):
    candidate = {"security_key": "JPM|NYSE|USD", "symbol": "JPM", "stock_market": "NYSE", "currency": "USD",
        "asset_class": "EQUITY", "asset_sub_class": "STOCK", "name": "JPMorgan Chase & Co.",
        "issuer_name": "JPMorgan Chase & Co.", "issuer_identity_verified": True}
    cache = SqliteCache(tmp_path / "market.sqlite", ttl_hours=24)
    store = LocalPortfolioStore(tmp_path / "local.sqlite")
    inventory = [candidate]
    settings = {"verification_ttl_days": 30}
    service = CreditRatingService(cache=lambda: cache, settings=lambda: settings, inventory=lambda: inventory,
        research_settings=lambda: {}, manual_store=lambda: store)
    return service, candidate, cache, store, inventory, settings


def draft(service, candidate, **changes):
    context = service.read(candidate)
    agency = changes.get("agency", "moodys")
    return {"security_key": candidate["security_key"], "agency": agency, "status": "rated", "rating": "Baa2",
        "entity_name": candidate["issuer_name"], "notes": "Synthetic user assertion for acceptance",
        "expected_identity": context["identity_token"], "expected_revision": context["manual_revisions"][agency], **changes}


def publish_fixture(service, candidate):
    stamp = datetime.now(timezone.utc).isoformat()
    rows = [{"agency": agency, "status": "rated", "rating": grade, "scope": "issuer", "scale": "global", "term": "long_term",
        "rating_type": "issuer_default" if agency == "fitch" else "issuer", "entity_name": candidate["issuer_name"],
        "outlook": "stable", "watch": "unknown", "rating_date": "2025-06-01", "outlook_date": None,
        "fetched_at": stamp, "outlook_fetched_at": stamp, "source_url": "https://www.jpmorganchase.com/ir/fixed-income",
        "sources": [{"url": "https://www.jpmorganchase.com/ir/fixed-income", "fetched_at": stamp,
                     "evidence_quote": "Synthetic source fixture, not a new current-market observation"}]}
        for agency, grade in (("moodys", "A1"), ("sp", "A"), ("fitch", "AA-"))]
    assert service.publish(candidate, rows)
    return rows


def test_manual_create_edit_clear_keeps_retrieved_sources_and_original_dates(manual_env):
    service, candidate, cache, store, _, _ = manual_env
    publish_fixture(service, candidate)
    original = service.read(candidate)["retrieved_ratings"]
    cached_original = deepcopy(cache.get_security_snapshot("credit_ratings", candidate["security_key"], SCHEMA))
    token = store.change_token()
    first = service.save_manual(draft(service, candidate, outlook="negative", rating_date="12/11/2026"), {"username": "operator"})
    row = first["ratings"][0]
    assert row["rating"] == "Baa2" and row["outlook"] == "negative" and row["watch"] == "unknown"
    assert row["source_kind"] == "manual" and row["verification_status"] == "user_entered"
    assert row["identity_verification"] == "verified_identity" and row["rating_date"] == "2026-11-12"
    assert row["fetched_at"] is None and row["verified_at"] is None
    assert row["updated_by"] == "operator" and row["manual_revision"] == 1
    assert first["retrieved_ratings"] == original
    assert cache.get_security_snapshot("credit_ratings", candidate["security_key"], SCHEMA) == cached_original
    edited = service.save_manual(draft(service, candidate, rating="A3"), {"username": "admin"})
    assert edited["ratings"][0]["created_at"] == row["created_at"]
    assert edited["ratings"][0]["updated_by"] == "admin" and edited["manual_revisions"]["moodys"] == 2
    assert edited["ratings"][0]["outlook"] == "unknown", "Manual blanks must not borrow retrieved Stable"
    cleared = service.clear_manual(candidate["security_key"], "moodys", 2, edited["identity_token"])
    assert cleared["ratings"][0]["rating"] == "A1" and cleared["ratings"][0]["outlook"] == "stable"
    assert cleared["ratings"][0]["rating_date"] == "2025-06-01"
    assert cleared["manual_revisions"]["moodys"] == 3 and cleared["manual_ratings"] == []
    assert cleared["retrieved_ratings"] == original and store.change_token() == token


def test_manual_survives_late_publish_cache_clear_restart_and_backup(manual_env, tmp_path):
    service, candidate, cache, store, inventory, settings = manual_env
    rows = publish_fixture(service, candidate)
    service.save_manual(draft(service, candidate), {"username": "operator"})
    service.publish(candidate, rows)
    assert service.read(candidate)["ratings"][0]["rating"] == "Baa2"
    with cache._connect() as connection:
        connection.execute("delete from security_snapshot")
        connection.execute("delete from cache")
    restored_store = LocalPortfolioStore(tmp_path / "restored.sqlite")
    restored_store.import_data(store.export_data())
    for local in (LocalPortfolioStore(store.path), restored_store):
        restarted = CreditRatingService(cache=lambda: cache, settings=lambda: settings, inventory=lambda: inventory,
            research_settings=lambda: {}, manual_store=lambda: local)
        context = restarted.read(candidate)
        assert context["ratings"][0]["rating"] == "Baa2"
        assert context["retrieved_ratings"][0]["rating"] == "A1", "Persistent source baseline survives market-cache clearing"
        assert context["rating_history"]


def test_manual_revision_tombstone_and_identity_preconditions_reject_old_writers(manual_env):
    service, candidate, _, store, _, _ = manual_env
    old = draft(service, candidate)
    saved = service.save_manual(old, {"username": "operator"})
    with pytest.raises(HTTPException) as conflict:
        service.save_manual(old, {"username": "other"})
    assert conflict.value.status_code == 409 and conflict.value.detail == "manual_rating_conflict"
    service.clear_manual(candidate["security_key"], "moodys", 1, saved["identity_token"])
    with pytest.raises(HTTPException):
        service.save_manual(old, {"username": "operator"})
    candidate["issuer_name"] = "JPMorgan Chase Bank, N.A."
    assert service.read(candidate)["manual_ratings"] == []
    with pytest.raises(HTTPException) as identity:
        service.save_manual(old, {"username": "operator"})
    assert identity.value.status_code == 409 and identity.value.detail == "security_identity_changed"
    assert any(row["key"].startswith("manual-credit-ratings-v1:") for row in store.export_data()["data"]["app_preferences"])


def test_database_revision_compare_is_atomic_across_service_instances(manual_env):
    service, candidate, cache, store, inventory, settings = manual_env
    second_store = LocalPortfolioStore(store.path)
    other = CreditRatingService(cache=lambda: cache, settings=lambda: settings, inventory=lambda: inventory,
        research_settings=lambda: {}, manual_store=lambda: second_store)
    payload = draft(service, candidate)
    def write(target):
        try:
            target.save_manual(payload, {"username": "operator"})
            return 200
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, (service, other)))
    assert sorted(results) == [200, 409]
    assert service.read(candidate)["manual_revisions"]["moodys"] == 1


@pytest.mark.parametrize("changes,code", [
    ({"agency": "sp", "rating": "Aa2"}, "manual_invalid_rating"),
    ({"agency": "sp", "rating": "A-1"}, "manual_invalid_rating"),
    ({"rating": "(P)A3"}, "manual_invalid_rating"),
    ({"scale": "national"}, "manual_invalid_scope"),
    ({"scope": "issue"}, "manual_invalid_scope"),
    ({"entity_name": "JPMorgan Chase Bank, N.A."}, "manual_invalid_entity"),
    ({"outlook": "garbage"}, "manual_invalid_outlook"),
    ({"watch": "garbage"}, "manual_invalid_watch"),
    ({"outlook_date": "12/11/2026"}, "manual_invalid_date"),
    ({"watch_date": "12/11/2026"}, "manual_invalid_date"),
    ({"rating_date": "31/02/2026"}, "manual_invalid_date"),
    ({"rating_date": "01/01/2099"}, "manual_invalid_date"),
    ({"status": "unrated", "rating": "" , "watch": "none"}, "manual_invalid_forward_status"),
    ({"status": "withdrawn"}, "manual_invalid_rating"),
    ({"notes": "", "source_url": ""}, "manual_source_required"),
    ({"source_url": "https://example.com/?api_key=secret"}, "manual_invalid_source_url"),
    ({"source_url": "https://127.0.0.1/source"}, "manual_invalid_source_url"),
    ({"expected_revision": True}, "manual_invalid_revision"),
    ({"updated_by": "spoofed"}, "manual_invalid_fields"),
])
def test_manual_validation_rejects_financially_inconsistent_or_unsafe_values(manual_env, changes, code):
    service, candidate, _, store, _, _ = manual_env
    payload = draft(service, candidate, **changes)
    before = store.export_data()["data"]["app_preferences"]
    with pytest.raises(HTTPException) as rejected:
        service.save_manual(payload, {"username": "operator"})
    assert rejected.value.status_code == 422 and rejected.value.detail == code
    assert store.export_data()["data"]["app_preferences"] == before


@pytest.mark.parametrize("agency,grade", [("moodys", "C"), ("sp", "SD"), ("sp", "D"), ("fitch", "RD"), ("fitch", "D")])
def test_native_default_symbols_remain_rated(manual_env, agency, grade):
    service, candidate, *_ = manual_env
    result = service.save_manual(draft(service, candidate, agency=agency, rating=grade), {"username": "operator"})
    row = next(row for row in result["ratings"] if row["agency"] == agency)
    assert row["status"] == "rated" and row["rating"] == grade and row["verification_status"] == "user_entered"


def test_unrated_is_explicit_manual_assertion_and_stale_entry_is_not_verified(manual_env):
    service, candidate, _, store, *_ = manual_env
    result = service.save_manual(draft(service, candidate, status="unrated", rating=None), {"username": "operator"})
    row = result["ratings"][0]
    assert row["rating"] is None and row["outlook"] == row["watch"] == "unknown"
    key = preference_key(candidate, result["identity_token"])
    saved = store.get_preference(key)
    saved["records"]["moodys"]["updated_at"] = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    store.set_preference(key, saved)
    stale = service.read(candidate)["ratings"][0]
    assert stale["stale"] and stale["staleness_basis"] == "manual_updated_at"
    assert stale["fetched_at"] is None and stale["verified_at"] is None and not stale["outlook_stale"]


def test_manual_unknown_issuer_is_explicit_and_bond_issue_needs_bound_identifier(manual_env):
    service, candidate, *_ = manual_env
    candidate.update(issuer_name="", name="JPM", issuer_identity_verified=False)
    result = service.save_manual(draft(service, candidate, entity_name="User Asserted Legal Corporation"), {"username": "operator"})
    assert result["ratings"][0]["identity_verification"] == "user_entered"
    assert result["manual_policy"]["canonical_issuer_name"] is None
    candidate.update(asset_class="BOND", asset_sub_class="BOND", symbol="US9128285M81",
                     stock_market="BOND", security_key="US9128285M81|BOND|USD")
    result = service.save_manual(draft(service, candidate, entity_name="User Asserted Legal Corporation", scope="issue"), {"username": "operator"})
    assert result["ratings"][0]["scope"] == "issue" and result["ratings"][0]["entity_id"] == "US9128285M81"


def test_router_permissions_and_batch_keep_manual_provenance_without_source_quotes(manual_env, monkeypatch):
    service, candidate, *_ = manual_env
    publish_fixture(service, candidate)
    app = FastAPI()
    @app.middleware("http")
    async def auth(request, call_next):
        if role := request.headers.get("X-Test-Role"):
            request.state.auth_user = {"id": "synthetic", "username": "operator", "role": role}
        return await call_next(request)
    app.include_router(service.router())
    client = TestClient(app)
    payload = draft(service, candidate)
    assert client.put(PREFIX + "/manual", json=payload).status_code == 401
    assert client.put(PREFIX + "/manual", json=payload, headers={"X-Test-Role": "Viewer"}).status_code == 403
    def forbidden(*args, **kwargs):
        raise AssertionError("Manual editing cannot call a provider or AI")
    monkeypatch.setattr(service, "check_apis", forbidden)
    monkeypatch.setattr(service, "_research_settings", forbidden)
    result = client.put(PREFIX + "/manual", json=payload, headers={"X-Test-Role": "Operator"})
    assert result.status_code == 200
    summary = client.get(PREFIX + "/summaries", params={"security_keys": candidate["security_key"]}, headers={"X-Test-Role": "Viewer"}).json()
    row = summary["items"][0]["ratings"][0]
    assert row["manual_override"] is True and row["rating"] == "Baa2" and row["source_kind"] == "manual"
    assert "evidence_quote" not in str(summary) and "notes" not in row
    params = {"security_key": candidate["security_key"], "agency": "moodys", "expected_revision": 1,
              "expected_identity": result.json()["identity_token"]}
    assert client.delete(PREFIX + "/manual", params=params, headers={"X-Test-Role": "Viewer"}).status_code == 403
    assert client.delete(PREFIX + "/manual", params=params, headers={"X-Test-Role": "Admin"}).status_code == 200


def test_manual_citations_never_become_previously_verified_research_leads(manual_env):
    service, candidate, *_ = manual_env
    service.save_manual(draft(service, candidate, source_url="https://manual-reference.example/rating"), {"username": "operator"})
    candidate["_request_id"] = "manual-discovery"
    session = ResearchSession({}, WebRequestBudget(8),
        resolver=lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))])
    service._sessions["manual-discovery"] = session
    result = service.research_tool(candidate, "discover", {})
    assert result["sources"] and all("manual-reference.example" not in source["url"] for source in result["sources"])
    assert result["evidence"] == [] and session.budget.used == 0


def test_fidus_agency_discovery_lead_requires_a_real_read_before_any_rating(manual_env):
    service, candidate, *_ = manual_env
    candidate.update(symbol="FDUS", security_key="FDUS|NASDAQ|USD", stock_market="NASDAQ",
        name="Fidus Investment Corporation", issuer_name="Fidus Investment Corporation",
        verified_issuer_domains=["fdus.com"], _request_id="fdus-discovery")
    session = ResearchSession({}, WebRequestBudget(8),
        resolver=lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))])
    service._sessions["fdus-discovery"] = session
    discovered = service.research_tool(candidate, "discover", {})
    lead = discovered["sources"][0]
    assert lead["url"].startswith("https://www.fitchratings.com/research/corporate-finance/")
    assert lead["discovery_only"] and discovered["evidence"] == []
    assert session.budget.used == 0
    assert all(row["status"] == "not_checked" for row in service.read(candidate)["ratings"])
    authorized = service._authorize_source(candidate, {"url": lead["url"]})
    assert not authorized.get("_issuer_source_verified"), "An agency domain is never marked as issuer-owned"
