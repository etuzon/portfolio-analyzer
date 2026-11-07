"""Provider-native US bond research never replaces portfolio valuation units."""
from copy import deepcopy
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security_market_data import SecurityMarketData, SNAPSHOT_VERSION, security_market_router
from app.us_market_providers import ProviderFailure


CUSIP = "91282CKD2"
ISIN = "US91282CKD29"


class MemoryCache:
    def __init__(self):
        self.saved = {}
    def get_security_snapshot(self, provider, symbol, key):
        return deepcopy(self.saved.get((provider, symbol, key)))
    def set_security_snapshot(self, provider, symbol, key, value):
        self.saved[provider, symbol, key] = deepcopy(value)


@pytest.fixture
def bond_application(monkeypatch):
    from app import main
    security = {"id": "synthetic-security-uuid", "symbol": CUSIP, "secondary_symbol": "", "stock_market": "MANUAL",
                "asset_class": "BOND", "location": "USA", "currency": "USD", "name": "Synthetic registered bond",
                "quantity": 6, "market_value": 100.5, "data_source": "MANUAL"}
    state = SimpleNamespace(security=security, calls=[], error=None, basis="valuation", side="valuation", cache=MemoryCache(), invalidations=[], local_rows=[{"price_date": date.today().isoformat(), "price": 16.75}])
    class Provider:
        def fetch(self, identifier, identifier_type, kind, start, end, budget):
            state.calls.append((identifier, identifier_type, kind, start, end))
            budget.consume()
            if state.error:
                raise ProviderFailure(state.error, "synthetic-provider-secret-must-not-leak")
            day = min(end, date.today() - timedelta(days=1)).isoformat()
            return {"security": {"cusip": CUSIP, "isin": ISIN, "kind": "bond", "currency": "USD", "name": "Synthetic Treasury"},
                "items": [{"price_date": day, "price": {"valuation": 99.34375, "programme_purchase": 99.35, "programme_redemption": 99.34}[state.basis], "currency": "USD", "quote_unit": "percent_of_par",
                           "price_basis": state.basis, "side": state.side, "adjustment_basis": "unadjusted",
                           "source_url": "https://www.treasurydirect.gov/", "programme_purchase_price": 99.35,
                           "programme_redemption_price": 99.34}],
                "details": {"coupon_rate_percent": 4.25, "maturity_date": "2029-02-28"},
                "coverage": {"complete": False, "next_date": (date.today() - timedelta(days=2)).isoformat()},
                "source_url": "https://www.treasurydirect.gov/", "warnings": ["Synthetic programme reference prices"]}
    class Hub:
        cache = state.cache
        def cached_profile(self, *args, **kwargs):
            return {}
        def prices(self, *args, **kwargs):
            pytest.fail("A CUSIP bond must not be looked up as an equity ticker")
        profile = fundamentals = dividends = prices
    class Store:
        def manual_security(self, *args):
            return deepcopy(state.security)
        def price_history(self, *args):
            return deepcopy(state.local_rows)
        def save_prices(self, *args):
            pytest.fail("Raw percent-of-par research must not save portfolio unit prices")
    monkeypatch.setattr(main, "hub", lambda: Hub())
    monkeypatch.setattr(main, "local_store", Store())
    monkeypatch.setattr(main, "to_dict", lambda item: deepcopy(item))
    monkeypatch.setattr(main, "clear_portfolio_cache", lambda: state.invalidations.append(True))
    provider = Provider()
    monkeypatch.setattr(main, "SecurityMarketData", lambda config, cache: SecurityMarketData(config, cache, providers={"treasury_direct": provider}))
    return main, state


@pytest.mark.parametrize("identifier", [CUSIP, ISIN])
def test_registered_us_bond_history_automatically_fetches_raw_api_data_before_manual_return(bond_application, identifier):
    main, state = bond_application
    state.security["symbol"] = identifier
    result = main.security_history(identifier, "MANUAL", period="1m")
    assert len(state.calls) == 1
    assert result["source"] == "manual" and result["points"][0]["price"] == 16.75
    data = result["market_data"]
    assert data["provider"] == "treasury_direct" and data["portfolio_updated"] is False
    assert data["latest_in_range"]["price"] == 99.34375
    assert data["latest_in_range"]["quote_unit"] == "percent_of_par"
    assert data["latest_in_range"]["price_basis"] == data["latest_in_range"]["side"] == "valuation"
    assert data["details"]["coupon_rate_percent"] == 4.25 and data["coverage"]["complete"] is False
    assert state.security["market_value"] == 100.5 and state.security["quantity"] == 6
    assert len(state.invalidations) == 1


def test_empty_portfolio_reference_cache_does_not_start_provider_requests(bond_application):
    main, state = bond_application
    payload = main._serialized_portfolio_payload([{"holding": state.security}], "cached")
    assert "market_data" not in payload["items"][0]
    assert state.calls == [] and state.invalidations == []


def test_serialized_holding_reads_latest_api_snapshot_without_fetch_or_revaluation(bond_application):
    main, state = bond_application
    history = main.security_history(CUSIP, "MANUAL", period="1m")
    count = len(state.calls)
    original = deepcopy(state.security)
    payload = main._serialized_portfolio_payload([{"holding": state.security}], "cached")
    item = payload["items"][0]
    assert len(state.calls) == count
    assert item["market_data"]["provider_requests"] == 0 and item["market_data"]["cache_status"] == "fresh"
    assert item["market_data"]["request"] == history["market_data"]["request"]
    assert item["holding"]["data_source"] == "MANUAL" and item["holding"]["market_value"] == original["market_value"]
    assert item["holding"]["quantity"] == original["quantity"] and state.security == original
    assert len(state.invalidations) == 1  # History invalidates; serialization is read-only.


def test_bond_enrichment_uses_one_reference_fetch_and_retains_missing_valuation(bond_application, monkeypatch):
    main, state = bond_application
    candidate = {**state.security, "security_key": CUSIP + "|MANUAL|USD", "missing_fields": ["prices", "profile", "reference"]}
    monkeypatch.setattr(main, "_enrichment_candidates", lambda **_: {"items": [deepcopy(candidate)]})
    result = main._enrichment_fetch_security(candidate, "auto")
    assert len(state.calls) == 1 and result["status"] == "partial"
    assert result["available_fields"] == ["reference"] and result["missing_fields"] == ["prices", "profile"]
    assert state.security["market_value"] == 100.5


def test_api_metadata_completes_profile_without_requesting_ai_to_invent_a_face_mapping(bond_application, monkeypatch):
    main, state = bond_application
    state.security["name"] = CUSIP
    monkeypatch.setattr(main, "_enrichment_outcomes", lambda: [])
    monkeypatch.setattr(main, "enriched_local_holdings", lambda **kwargs: [{"holding": deepcopy(state.security), "missing": ["industry"], "price_ranges": {}}])
    candidate = main._enrichment_candidates()["items"][0]
    result = main._enrichment_fetch_security(candidate, "auto")
    assert len(state.calls) == 1 and result["status"] == "partial"
    assert result["code"] == "bond_reference_only" and result["research_eligible"] is False
    assert result["available_fields"] == ["reference", "profile"] and result["missing_fields"] == ["prices"]
    assert state.security["name"] == CUSIP and state.security["market_value"] == 100.5


def test_unavailable_reference_is_safe_and_does_not_break_existing_local_chart(bond_application):
    main, state = bond_application
    state.error = "not_found"
    result = main.security_history(CUSIP, "MANUAL")
    assert result["points"][0]["price"] == 16.75
    assert result["market_data"]["status"] == "not_found"
    assert result["market_data"]["provider_errors"] == [{"provider": "treasury_direct", "code": "not_found"}]
    assert "synthetic-provider-secret" not in str(result)
    assert state.invalidations == []


def test_unrelated_security_registration_keeps_existing_manual_history_behavior(bond_application):
    main, state = bond_application
    state.security.update(symbol="AAPL", asset_class="EQUITY")
    result = main.security_history("AAPL", "MANUAL")
    assert "market_data" not in result and state.calls == []
    assert result["source"] == "manual" and result["points"][0]["price"] == 16.75


def test_generic_lookup_populates_cache_alias_for_read_only_portfolio_attachment(bond_application):
    main, state = bond_application
    lookup = main.SecurityMarketData({}, state.cache)
    result = lookup.fetch(CUSIP, "bond", date_from=(date.today() - timedelta(days=10)).isoformat())
    alias = state.cache.get_security_snapshot("security_lookup", CUSIP, SNAPSHOT_VERSION + ":latest:bond")
    assert alias["request"] == result["request"]
    assert main._bond_market_data(state.security, cache_only=True)["request"] == result["request"]
    assert len(state.calls) == 1


@pytest.mark.parametrize("registered_name,expected_name", [(CUSIP, "Synthetic Treasury"), ("My registered bond", "My registered bond")])
def test_verified_api_name_fills_display_and_inventory_without_overwriting_registration(bond_application, monkeypatch, registered_name, expected_name):
    main, state = bond_application
    state.security.update(name=registered_name, asset_class="UNKNOWN", asset_sub_class="BOND")
    main.security_history(CUSIP, "MANUAL")
    calls = len(state.calls)
    monkeypatch.setattr(main, "_enrichment_outcomes", lambda: [])
    monkeypatch.setattr(main, "enriched_local_holdings", lambda **kwargs: [{"holding": deepcopy(state.security), "missing": ["industry"], "price_ranges": {}}])
    item = main._serialized_portfolio_payload([{"holding": deepcopy(state.security)}], "cached")["items"][0]
    candidate = main._enrichment_candidates()["items"][0]
    assert item["holding"]["name"] == candidate["name"] == expected_name
    assert candidate["asset_sub_class"] == "BOND" and candidate["needs_name"] is False
    assert candidate["missing_fields"] == ["prices"]
    assert len(state.calls) == calls
    assert state.security["name"] == registered_name and state.security["market_value"] == 100.5


def test_market_data_endpoint_invalidates_only_successful_non_cache_only_bond_reads(bond_application):
    main, state = bond_application
    app = FastAPI()
    app.include_router(security_market_router(lambda: main.SecurityMarketData({}, state.cache), lambda: state.invalidations.append(True)))
    client = TestClient(app)
    params = {"identifier": CUSIP, "kind": "bond"}
    assert client.get("/api/security/market-data", params={**params, "cache_only": True}).status_code == 200
    assert not state.invalidations and not state.calls
    assert client.get("/api/security/market-data", params=params).status_code == 200
    assert len(state.invalidations) == 1
    assert client.get("/api/security/market-data", params={**params, "cache_only": True}).status_code == 200
    assert len(state.invalidations) == 1 and len(state.calls) == 1
    state.error = "provider_error"
    response = client.get("/api/security/market-data", params={**params, "refresh": True})
    assert response.status_code == 200 and response.json()["status"] == "stale"
    assert len(state.invalidations) == 1


@pytest.mark.parametrize("basis,side,price", [("valuation", "valuation", 99.34375),
    ("programme_purchase", "programme_purchase_mean", 99.35), ("programme_redemption", "programme_redemption_bid", 99.34)])
def test_raw_treasury_valuation_purchase_and_redemption_conventions_remain_distinct(bond_application, basis, side, price):
    main, state = bond_application
    state.basis, state.side = basis, side
    result = main.security_history(CUSIP, "MANUAL")
    raw = result["market_data"]["latest_in_range"]
    assert (raw["price_basis"], raw["side"], raw["price"]) == (basis, side, price)
    assert raw["currency"] == "USD" and raw["quote_unit"] == "percent_of_par"
    assert result["points"][0]["price"] == 16.75 and state.security["market_value"] == 100.5
