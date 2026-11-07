from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.providers import SqliteCache
from app.security_market_data import SecurityMarketData, lookup_range, normalize_identifier, security_market_router


CUSIP = "91282CKD2"
TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


def bond_payload(day=YESTERDAY, price=99.354):
    return {
        "security": {"cusip": CUSIP, "isin": "US91282CKD29", "kind": "bond", "name": "Synthetic Treasury", "currency": "USD"},
        "items": [{"price_date": day.isoformat(), "price": price, "currency": "USD",
                   "quote_unit": "percent_of_par", "price_basis": "unknown", "side": "valuation",
                   "adjustment_basis": "unadjusted", "source_url": "https://www.treasurydirect.gov/"}],
        "details": {"coupon_rate_percent": 4.25, "maturity_date": "2029-02-28", "coupon_frequency": "Semi-Annual"},
        "source_url": "https://www.treasurydirect.gov/", "coverage": {"complete": True},
    }


class Provider:
    def __init__(self, payload=None, error=None, attempts=1):
        self.payload, self.error, self.attempts = payload or bond_payload(), error, attempts
        self.calls = []

    def fetch(self, identifier, identifier_type, kind, start, end, budget):
        self.calls.append((identifier, identifier_type, kind, start, end))
        for _ in range(self.attempts):
            budget.consume()
        if self.error:
            from app.us_market_providers import ProviderFailure
            raise ProviderFailure(self.error, "fixture-secret-must-not-leak")
        return deepcopy(self.payload)


@pytest.fixture
def cache(tmp_path):
    return SqliteCache(tmp_path / "cache.sqlite3", ttl_hours=24)


def service(cache, provider=None, **config):
    return SecurityMarketData({"security_lookup": config}, cache,
                              providers={"finnhub": provider or Provider()})


def test_fetches_dated_data_without_prior_security_or_manual_prices_and_caches(cache):
    provider = Provider()
    lookup = service(cache, provider)
    result = lookup.fetch(CUSIP, "bond")
    assert result["status"] == "ok"
    assert result["quote"]["price"] == 99.354
    assert result["quote"]["quote_unit"] == "percent_of_par"
    assert result["details"]["coupon_rate_percent"] == 4.25
    assert result["details_scope"] == "latest_provider_profile_not_historical_point_in_time"
    assert result["portfolio_updated"] is False
    assert result["provider_requests"] == 1
    assert result["quote_status"] == "dated"
    again = lookup.fetch(CUSIP, "bond")
    assert again["cache_status"] == "fresh"
    assert again["provider_requests"] == 0
    assert len(provider.calls) == 1
    again["items"][0]["price"] = 1
    assert lookup.fetch(CUSIP, "bond")["items"][0]["price"] == 99.354


def test_historical_scope_is_not_current_and_older_profile_not_invented(cache):
    old_day = TODAY - timedelta(days=100)
    lookup = service(cache, Provider(bond_payload(old_day)))
    result = lookup.fetch(CUSIP, "bond", date_from=old_day.strftime("%d/%m/%Y"), date_to=old_day.isoformat())
    assert result["quote"] is None
    assert result["quote_status"] == "missing"
    assert result["latest_in_range"]["price_date"] == old_day.isoformat()
    assert result["details_scope"].startswith("latest_provider_profile")
    assert result["coverage"]["count"] == 1


def test_refresh_outage_retains_saved_prices_and_does_not_expose_secrets(cache):
    provider = Provider()
    lookup = service(cache, provider)
    first = lookup.fetch(CUSIP, "bond")
    provider.error = "provider_error"
    stale = lookup.fetch(CUSIP, "bond", refresh=True)
    assert stale["status"] == stale["cache_status"] == "stale"
    assert stale["retrieved_at"] == first["retrieved_at"]
    assert stale["items"] == first["items"]
    assert "fixture-secret" not in str(stale)
    assert lookup.fetch(CUSIP, "bond", cache_only=True)["items"] == first["items"]


def test_empty_refresh_does_not_replace_retained_history(cache):
    provider = Provider()
    lookup = service(cache, provider)
    before = lookup.fetch(CUSIP, "bond")
    provider.payload["items"] = []
    result = lookup.fetch(CUSIP, "bond", refresh=True)
    assert result["status"] == "stale" and result["items"] == before["items"]
    assert lookup.fetch(CUSIP, "bond", cache_only=True)["items"] == before["items"]


def test_primary_outage_and_partial_fallback_preserve_richer_saved_history(cache):
    payload = bond_payload()
    payload["items"] = [bond_payload(TODAY - timedelta(days=offset))["items"][0] for offset in range(20, 0, -1)]
    primary = Provider(payload)
    fallback_payload = bond_payload()
    fallback_payload["coverage"] = {"complete": False, "next_date": (TODAY - timedelta(days=2)).isoformat()}
    fallback_payload["items"][0]["price_basis"] = "programme_purchase"
    lookup = SecurityMarketData({}, cache, providers={"finnhub": primary, "treasury_direct": Provider(fallback_payload)})
    before = lookup.fetch(CUSIP, "bond")
    assert len(before["items"]) == 20
    primary.error = "provider_error"
    result = lookup.fetch(CUSIP, "bond", refresh=True)
    assert result["status"] == result["cache_status"] == "stale"
    assert result["items"] == before["items"]
    assert result["retrieved_at"] == before["retrieved_at"]
    assert lookup.fetch(CUSIP, "bond", cache_only=True)["items"] == before["items"]


@pytest.mark.parametrize("kind,identifier,identifier_type,expected", [
    ("bond", "91282ckd2", "auto", (CUSIP, "cusip")),
    ("bond", "US91282CKD29", "auto", ("US91282CKD29", "isin")),
    ("fund", "SWPPX", "auto", ("SWPPX", "ticker")),
    ("etf", "VTI.US", "auto", ("VTI.US", "ticker")),
])
def test_generic_identifier_resolution(kind, identifier, identifier_type, expected):
    assert normalize_identifier(identifier, identifier_type, kind) == expected


@pytest.mark.parametrize("identifier,identifier_type,kind", [
    ("AAPL", "auto", "bond"), ("../../config.yaml", "ticker", "fund"),
    ("https://example.com", "auto", "fund"), ("AAPL?token=secret", "ticker", "etf"),
    ("WRONG", "cusip", "bond"), ("US123", "isin", "fund"),
    ("US91282CKD20", "isin", "bond"), ("91282CKD0", "cusip", "bond"),
])
def test_bad_identifiers_never_reach_provider(cache, identifier, identifier_type, kind):
    provider = Provider()
    with pytest.raises(ValueError):
        service(cache, provider).fetch(identifier, kind, identifier_type)
    assert provider.calls == []


def test_provider_identity_mismatch_cannot_be_cached_as_requested_bond(cache):
    payload = bond_payload()
    payload["security"]["cusip"] = "037833DV9"
    result = service(cache, Provider(payload)).fetch(CUSIP, "bond")
    assert result["status"] == "provider_error"
    assert result["items"] == [] and result["security"] is None


@pytest.mark.parametrize("bad", [True, -1, float("nan"), float("inf"), 10 ** 400, "99.35"])
def test_invalid_prices_fail_safely(cache, bad):
    result = service(cache, Provider(bond_payload(price=bad))).fetch(CUSIP, "bond")
    assert result["status"] == "provider_error"
    assert result["items"] == []


def test_explicit_zero_bond_price_is_not_missing(cache):
    result = service(cache, Provider(bond_payload(price=0))).fetch(CUSIP, "bond")
    assert result["status"] == "ok" and result["quote"]["price"] == 0


def test_partial_history_exposes_provider_cursor_and_counts_failure_budget(cache):
    payload = bond_payload()
    payload["coverage"] = {"complete": False, "next_date_to": (TODAY - timedelta(days=4)).isoformat()}
    bad = Provider(error="provider_error", attempts=2)
    good = Provider(payload, attempts=3)
    lookup = SecurityMarketData({"security_lookup": {"max_provider_requests": 999}}, cache,
                                providers={"finnhub": bad, "treasury_direct": good})
    result = lookup.fetch(CUSIP, "bond")
    assert result["status"] == "partial"
    assert result["provider_requests"] == result["max_provider_requests"] == 5
    assert result["coverage"]["next_date_to"]
    assert result["provider_errors"] == [{"provider": "finnhub", "code": "provider_error"}]


def test_cache_only_miss_and_missing_configuration_are_explicit(cache):
    lookup = SecurityMarketData({}, cache, providers={})
    assert lookup.fetch("SWPPX", "fund")["status"] == "not_configured"
    assert lookup.fetch(CUSIP, "bond", cache_only=True)["reason"] == "cache_empty"
    with pytest.raises(ValueError):
        lookup.fetch(CUSIP, "bond", refresh=True, cache_only=True)


def test_fund_and_etf_prices_keep_basis_currency_and_share_class(cache):
    for kind, basis, value in [("fund", "nav", 20.5), ("etf", "market_close", 21)]:
        payload = {"security": {"ticker": "EXAMPLE.US", "kind": kind, "currency": "USD", "share_class": "Investor"},
                   "items": [{"price_date": YESTERDAY.isoformat(), "price": value, "currency": "USD", "quote_unit": "currency_per_share", "price_basis": basis}],
                   "coverage": {"complete": True}, "details": {"net_asset_value": 20.5}}
        lookup = SecurityMarketData({}, cache, providers={"eodhd": Provider(payload)})
        result = lookup.fetch("EXAMPLE", kind)
        assert result["quote"]["price_basis"] == basis and result["quote"]["price"] == value
        assert result["security"]["share_class"] == "Investor"


def test_router_and_assistant_catalog_expose_generic_read_contract(cache):
    from app import main
    app = FastAPI()
    app.include_router(security_market_router(lambda: service(cache)))
    client = TestClient(app)
    response = client.get("/api/security/market-data", params={"identifier": CUSIP, "kind": "bond"})
    assert response.status_code == 200 and response.json()["quote"]["price"] == 99.354
    assert client.get("/api/security/market-data", params={"identifier": CUSIP, "kind": "crypto"}).status_code == 422
    assert client.get("/api/security/market-data", params={"identifier": CUSIP, "kind": "bond", "date_from": "wrong"}).status_code == 422
    entry = main.ASSISTANT_READ_TOOLS["get_security_market_data"]
    assert entry["path"] == "/api/security/market-data"
    assert entry.get("method", "GET") == "GET"
    from app.assistant_rest import validate_arguments
    assert validate_arguments({"identifier": CUSIP, "kind": "bond", "refresh": True}, entry["parameters"])["refresh"] is True


def test_route_requires_authentication_and_allows_viewer_read_without_ledger_changes(tmp_path, monkeypatch, cache):
    from app import main
    from app.auth import AuthStore
    from app.local_portfolio import LocalPortfolioStore
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    auth = AuthStore(store.path)
    auth.initialize()
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    monkeypatch.setattr(main, "SecurityMarketData", lambda *_: service(cache))
    monkeypatch.setattr(main, "hub", lambda: type("Hub", (), {"cache": cache})())
    client = TestClient(main.app, base_url="https://localhost:6443")
    params = {"identifier": CUSIP, "kind": "bond"}
    assert client.get("/api/security/market-data", params=params).status_code == 401
    auth.create_user({"username": "research-viewer", "first_name": "Research", "last_name": "Viewer", "role": "Viewer", "password": "Temporary-Research-2026!"})
    session = client.post("/api/auth/login", json={"username": "research-viewer", "password": "Temporary-Research-2026!"}).json()
    changed = client.post("/api/auth/change-password", headers={"X-CSRF-Token": session["csrf_token"]}, json={"current_password": "Temporary-Research-2026!", "new_password": "New-Research-Password-2026!", "confirm_password": "New-Research-Password-2026!"})
    assert changed.status_code == 200
    before = store.export_data()
    response = client.get("/api/security/market-data", params=params)
    assert response.status_code == 200 and response.json()["portfolio_updated"] is False
    after = store.export_data()
    for table in ("price_history", "transactions", "accounts", "manual_securities"):
        assert after["data"][table] == before["data"][table]
