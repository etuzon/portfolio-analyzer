"""Independent routing acceptance checks using synthetic in-memory evidence.

Execute with a temporary DATA_DIR and CONFIG_PATH=config.example.yaml; application
imports initialize the configured runtime storage even when callbacks are faked.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

from app.security_enrichment import PREFIX, RestError
from test_security_enrichment import environment, job, start


@pytest.fixture
def routing_application(monkeypatch):
    from app import main
    bond = {"symbol": "121899CH9", "stock_market": "BOND", "asset_class": "BOND",
            "asset_sub_class": "", "currency": "USD", "location": "USA", "data_source": "MANUAL",
            "quantity": 1000, "name": "Example bond", "secondary_symbol": ""}
    state = SimpleNamespace(holdings=[bond], metadata=deepcopy(bond), saved=[], logs=[], history_hook=None,
                            metadata_reads=0, metadata_hook=None, holdings_hook=None)
    state.original_enriched = main.enriched_local_holdings
    day = (date.today() - timedelta(days=1)).isoformat()
    state.snapshot = {"status": "partial", "cache_status": "fresh", "provider": "finnhub",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "security": {"kind": "bond", "cusip": bond["symbol"], "currency": "USD", "name": "Example bond"},
        "details": {"maturity_date": "2035-01-01"},
        "items": [{"price_date": day, "price": 98.5, "currency": "USD", "quote_unit": "percent_of_par",
                   "price_basis": "close", "source_url": "https://api.finnhub.io/api/v1/bond/price"}]}

    class Store:
        def holdings(self):
            if state.holdings_hook:
                state.holdings_hook()
            return [{"holding": deepcopy(holding)} for holding in state.holdings]

        def manual_security(self, *_args):
            state.metadata_reads += 1
            if state.metadata_hook:
                state.metadata_hook()
            return deepcopy(state.metadata)

        def price_history(self, *_args):
            if state.history_hook:
                state.history_hook()
            return []

        def save_prices(self, rows, *, only_missing=False):
            assert only_missing is True
            state.saved.extend(deepcopy(rows))
            return rows

    class Cache:
        def __init__(self):
            self.saved = {}

        def get_security_snapshot(self, provider, identifier, key):
            return deepcopy(self.saved.get((provider, identifier, key)))

        def set_security_snapshot(self, provider, identifier, key, value):
            self.saved[provider, identifier, key] = deepcopy(value)

    state.cache = Cache()
    monkeypatch.setattr(main, "local_store", Store())
    monkeypatch.setattr(main, "to_dict", deepcopy)
    monkeypatch.setattr(main, "hub", lambda: SimpleNamespace(cache=state.cache, cached_profile=lambda *_a, **_k: {}))
    monkeypatch.setattr(main, "config", SimpleNamespace(market_data={"primary": "stooq",
        "security_lookup": {"finnhub": {"api_key": "synthetic"}}}, raw={}, dashboard={}))
    monkeypatch.setattr(main, "_bond_market_data", lambda *_a, **_k: deepcopy(state.snapshot))
    monkeypatch.setattr(main, "_israeli_fund_data", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "enriched_local_holdings", lambda **_k: [
        {"holding": deepcopy(holding), "missing": ["price history"], "price_ranges": {}}
        for holding in state.holdings])
    monkeypatch.setattr(main, "_enrichment_outcomes", lambda: [])
    monkeypatch.setattr(main, "_record_log", lambda *_a, **kwargs: state.logs.append(kwargs))
    return main, state


def test_failed_rest_attempts_use_one_job_budget_and_sixth_never_reaches_app(environment):
    env = environment
    identifier = start(env)
    before = len(env.state.observations)
    # A queued job cannot read inventory. Every rejected authorized attempt
    # still consumes one of the five attempts for this same click.
    for _ in range(5):
        with pytest.raises(RestError, match="job_failed"):
            env.manager._request(identifier, env.headers, "GET", PREFIX + "/candidates",
                                 params={"request_id": identifier})
    assert len(env.state.observations) == before + 5
    with pytest.raises(RestError, match="request_limit"):
        env.manager._request(identifier, env.headers, "GET", PREFIX + "/candidates",
                             params={"request_id": identifier})
    assert len(env.state.observations) == before + 5
    result = job(env, identifier)
    assert result["counts"]["rest_requests"] == 5
    assert result["counts"]["model_requests"] == 0
    assert env.state.fetched == [] and env.state.saved == []


def test_failed_model_attempt_is_counted_and_does_not_get_privileged_retry(environment, monkeypatch):
    from app.llm_assistant import PortfolioAssistant
    env = environment
    calls = []

    def failed_model(*_args, **_kwargs):
        calls.append(True)
        raise RuntimeError("synthetic-provider-password-must-not-leak")

    monkeypatch.setattr(PortfolioAssistant, "_call_provider", failed_model)
    identifier = start(env)
    env.run()
    result = job(env, identifier)
    assert result["status"] == "failed"
    assert result["counts"]["model_requests"] == len(calls) == 1
    assert result["counts"]["rest_requests"] == 2  # Inventory and finalization.
    assert not env.state.fetched
    assert "synthetic-provider-password" not in str(result)


def test_ordinary_refresh_visits_already_priced_api_listing_without_ai(routing_application):
    main, state = routing_application
    # The automatic inventory comes directly from open holdings; it does not
    # depend on missing-field flags, the AI inventory, or a three-item AI cap.
    state.holdings = [{**state.holdings[0], "account_id": str(index)} for index in range(4)]
    inventory = main._automatic_price_inventory()
    assert len(inventory) == 1 and inventory[0]["quantity"] == 4000
    assert main._apply_automatic_security_prices(inventory[0], state.snapshot) == 1
    assert state.saved[0]["price_input"] == 98.5
    assert main._ai_enrichment_candidates()["items"] == []


@pytest.mark.parametrize("symbol,asset", [("AAPL", "EQUITY"), ("US8085098551", "FUND")])
def test_api_owned_native_manual_listing_has_normal_provider_refresh_path(routing_application, monkeypatch, symbol, asset):
    from dataclasses import asdict
    from app.automatic_security_refresh import AutomaticSecurityRefresh
    from app.models import Holding, SymbolAnalysis, Trend
    main, state = routing_application
    holding = Holding(symbol=symbol, stock_market="MANUAL", asset_class=asset, data_source="MANUAL",
                      currency="USD", location="USA", quantity=5, name="Synthetic public listing")
    analysis = SymbolAnalysis(holding, {}, {}, {}, {}, {}, Trend(), Trend(), Trend(), Trend(), "", ["price history"])
    monkeypatch.setattr(main.local_store, "holdings", lambda: [deepcopy(analysis)])
    monkeypatch.setattr(main, "to_dict", asdict)
    main.config.market_data["security_lookup"]["eodhd"] = {"api_key": "synthetic"}
    calls = []

    class Market:
        cache = state.cache
        def cached_view(self):
            return self
        def cached_profile(self, *_a, **_k):
            return {}
        def prices(self, *_a, **_k):
            calls.append("prices")
            return [], {}
        def fundamentals(self, *_a, **_k):
            calls.append("fundamentals")
            return {}, {}
        def dividends(self, *_a, **_k):
            calls.append("dividends")
            return [], {}
        def profile(self, *_a, **_k):
            calls.append("profile")
            return {}, {}

    class Lookup:
        def fetch(self, *_a, **_k):
            if not _k.get("cache_only", False):
                calls.append("reference")
            return None

    monkeypatch.setattr(main, "hub", lambda: Market())
    monkeypatch.setattr(main, "SecurityMarketData", lambda *_a, **_k: Lookup())
    runner = AutomaticSecurityRefresh()
    monkeypatch.setattr(main, "_automatic_api_refresher", runner)
    try:
        assert main._security_api_route(asdict(holding))["owner"] == "api"
        main._refresh_automatic_security_prices()
        state.original_enriched(on_progress=lambda *_a, **_k: None)
        assert calls, "An API-owned native listing must reach a provider in normal refresh"
    finally:
        runner._pool.shutdown(wait=True)


@pytest.mark.parametrize("quantity", [8, -8])
def test_us_fund_application_keeps_native_share_close_and_manual_precedence(routing_application, monkeypatch, quantity):
    main, state = routing_application
    state.holdings[0].update(symbol="SWPPX", asset_class="FUND", stock_market="MANUAL", quantity=quantity)
    state.metadata.update(state.holdings[0])
    main.config.market_data["security_lookup"]["eodhd"] = {"api_key": "synthetic"}
    day = (date.today() - timedelta(days=1)).isoformat()
    snapshot = {"status": "partial", "cache_status": "fresh", "provider": "eodhd",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "security": {"kind": "fund", "ticker": "SWPPX", "isin": "US8085098551", "currency": "USD", "venue": "NASDAQ"},
        "items": [{"price_date": day, "price": 17.125, "currency": "USD", "quote_unit": "currency_per_share",
                   "price_basis": "close", "adjustment_basis": "unadjusted", "source_url": "https://eodhd.com/api/eod/SWPPX.US"}]}
    candidate = main._automatic_price_inventory()[0]
    assert main._apply_automatic_security_prices(candidate, snapshot) == 1
    assert state.saved[0]["price_input"] == 17.125
    assert abs(quantity) * state.saved[0]["price_input"] == 137
    assert json.loads(state.saved[0]["comments"])["normalization"] == "raw_price"
    state.saved.clear()
    monkeypatch.setattr(main.local_store, "price_history", lambda *_a: [{"price_date": day, "price_input": 20, "source": "manual"}])
    assert main._apply_automatic_security_prices(candidate, snapshot) == 0
    assert state.saved == []


def test_eodhd_valuation_source_matches_saved_mark(routing_application, monkeypatch):
    main, state = routing_application
    holding = {**state.holdings[0], "symbol": "SWPPX", "stock_market": "MANUAL", "asset_class": "FUND"}
    day = (date.today() - timedelta(days=1)).isoformat()
    mark = {**holding, "price_date": day, "price": 17.125, "source": "api_evidence",
            "comments": json.dumps({"kind": "price_evidence_v1", "provider": "eodhd"})}
    monkeypatch.setattr(main.local_store, "list_prices", lambda: [mark], raising=False)
    item = {"holding": holding, "price_ranges": {"1y": {"current": 17.125, "current_date": day}}}
    result = main._serialized_portfolio_payload([item], "cached")["items"][0]
    assert result.get("valuation_price_provider") == "eodhd"


def test_manual_stock_currency_conflict_preserves_prices_then_recovers(routing_application, monkeypatch):
    from dataclasses import asdict
    from app.models import Holding, SymbolAnalysis, Trend
    main, state = routing_application
    holding = Holding(symbol="AAPL", stock_market="MANUAL", asset_class="EQUITY", data_source="MANUAL",
        currency="USD", location="USA", quantity=5, cost_basis=40, market_value=60, unrealized_profit=20)
    local = SymbolAnalysis(holding, {}, {"1y": {"current": 12, "current_date": (date.today()-timedelta(days=1)).isoformat()}},
        {"local": 11}, {"local": 10}, {"local": 9}, Trend(), Trend(), Trend(), Trend(), "", [])
    source = deepcopy(local)
    source.price_ranges = {"1y": {"current": 100, "current_date": date.today().isoformat()}}
    source.moving_averages, source.support_resistance, source.volume = {"source": 101}, {"source": 102}, {"source": 103}
    source.industry = "Verified source industry"
    state.currency, state.fetches = "EUR", 0

    class Market:
        cache = state.cache
        def cached_view(self):
            return self
        def cached_profile(self, *_a, **_k):
            return {"currency": state.currency}

    market = Market()
    monkeypatch.setattr(main, "hub", lambda: market)
    monkeypatch.setattr(main.local_store, "holdings", lambda: [deepcopy(local)])
    monkeypatch.setattr(main, "to_dict", asdict)

    def analyze(*_a, **_k):
        state.fetches += 1
        return deepcopy(source)

    monkeypatch.setattr(main, "analyze_holding", analyze)
    ready = []
    def progress(_key, status, analysis, _total):
        if status == "ready":
            ready.append(analysis)

    conflicting = state.original_enriched(on_progress=progress)[0]
    assert state.fetches == 1 and ready
    for result in (conflicting, ready[-1]):
        assert result.holding.market_value == 60 and result.holding.unrealized_profit == 20
        for field in ("price_ranges", "moving_averages", "support_resistance", "volume"):
            assert getattr(result, field) == getattr(local, field)
        assert result.provider_status["prices.currency"] == "error: source_currency_mismatch"
        assert result.industry == "Verified source industry"
    state.currency = "USD"
    recovered = state.original_enriched(on_progress=progress)[0]
    assert state.fetches == 2
    assert recovered.holding.market_value == 500 and recovered.holding.unrealized_profit == 460
    assert recovered.price_ranges["1y"]["current"] == 100
    assert "prices.currency" not in recovered.provider_status


@pytest.mark.parametrize("quantity", [1, -1, 1e-12])
def test_ai_only_no_route_open_long_short_and_reopened_holdings(routing_application, quantity):
    main, state = routing_application
    holding = state.holdings[0]
    holding.update(symbol="SYNTHETIC", stock_market="MANUAL", asset_class="EQUITY", location="Israel", currency="ILS")
    holding["quantity"] = 0
    assert main._ai_enrichment_candidates()["items"] == []
    holding["quantity"] = quantity
    assert len(main._ai_enrichment_candidates()["items"]) == 1
    holding.update(stock_market="PRIVATE", asset_class="PRIVATE_STOCK")
    assert main._ai_enrichment_candidates()["items"] == []


@pytest.mark.parametrize("asset", ["PRIVATE_STOCK", "EMPLOYEE_STOCK_OPTION", "STOCK_OPTION"])
def test_private_employee_records_never_reach_either_public_inventory(routing_application, asset):
    main, state = routing_application
    state.holdings[0].update(symbol="PRIVATE-SYNTHETIC", stock_market="MANUAL", asset_class=asset)
    assert main._ai_enrichment_candidates()["items"] == []
    assert main._automatic_price_inventory() == []


@pytest.mark.parametrize("change", [
    {"asset_class": "UNKNOWN", "asset_sub_class": "BOND"},
    {"location": "France"},
    {"data_source": "IMPORT"},
])
def test_automatic_price_contract_changed_during_read_prevents_old_metadata_write(routing_application, change):
    main, state = routing_application
    candidate = main._automatic_price_inventory()[0]

    def change_contract():
        for item in (state.metadata, *state.holdings):
            item.update(change)

    state.history_hook = change_contract
    assert main._apply_automatic_security_prices(candidate, state.snapshot) == 0
    assert state.saved == []


def test_close_during_last_metadata_read_prevents_automatic_write(routing_application):
    main, state = routing_application
    candidate = main._automatic_price_inventory()[0]

    def close_on_final_read():
        if state.metadata_reads >= 2:
            state.holdings[0]["quantity"] = 0

    state.metadata_hook = close_on_final_read
    assert main._apply_automatic_security_prices(candidate, state.snapshot) == 0
    assert state.saved == []


def test_final_inventory_rejects_location_contract_newer_than_metadata_read(routing_application):
    main, state = routing_application
    candidate = main._automatic_price_inventory()[0]

    def change_after_metadata_read():
        if state.metadata_reads >= 2:
            state.holdings[0]["location"] = "France"
            state.metadata["location"] = "France"

    state.holdings_hook = change_after_metadata_read
    assert main._apply_automatic_security_prices(candidate, state.snapshot) == 0
    assert state.saved == []


@pytest.mark.parametrize("code", ["entitlement_required", "rate_limited", "provider_error", "invalid_response", "request_limit"])
def test_api_failure_inventory_remains_excluded_from_ai(routing_application, code):
    main, state = routing_application
    identifier = state.holdings[0]["symbol"]
    state.snapshot = None
    evidence = {"retrieved_at": datetime.now(timezone.utc).isoformat(),
        "request": {"identifier": identifier}, "status": "provider_error",
        "provider_errors": [{"provider": "finnhub", "code": code}]}
    state.cache.set_security_snapshot("security_lookup", identifier, "security-coverage-v1:bond", evidence)
    route = main._security_api_route(state.holdings[0])
    assert route["owner"] == "api" and route["coverage"] == "candidate"
    assert main._ai_enrichment_candidates()["items"] == []


def test_unknown_exact_coverage_requires_configuration_and_never_spends_ai(routing_application):
    main, state = routing_application
    state.snapshot = None
    main.config.market_data["security_lookup"]["finnhub"]["api_key"] = ""
    route = main._security_api_route(state.holdings[0])
    assert route["owner"] == "api" and route["configured"] is False
    assert route["coverage"] == "candidate" and route["reason"] == "configuration_required"
    assert main._ai_enrichment_candidates()["items"] == []
    assert main._automatic_price_inventory() == []


def test_only_exact_negative_coverage_allows_bond_ai_inventory(routing_application):
    main, state = routing_application
    state.snapshot = None
    identifier = state.holdings[0]["symbol"]
    proof = {"retrieved_at": datetime.now(timezone.utc).isoformat(),
        "request": {"identifier": identifier}, "status": "not_found",
        "provider_errors": [{"provider": "finnhub", "code": "not_found"}]}
    state.cache.set_security_snapshot("security_lookup", identifier, "security-coverage-v1:bond", proof)
    result = main._ai_enrichment_candidates()
    assert len(result["items"]) == 1
    assert result["items"][0]["api_data_route"]["owner"] == "ai"
    assert result["items"][0]["missing_fields"] == ["prices"]
    assert main._automatic_price_inventory() == []
    # A different identifier's failed response never qualifies this listing.
    proof["request"]["identifier"] = "88059ESH8"
    state.cache.set_security_snapshot("security_lookup", identifier, "security-coverage-v1:bond", proof)
    assert main._ai_enrichment_candidates()["items"] == []


def test_api_recovery_after_ai_inventory_stops_application_research(routing_application, monkeypatch):
    main, state = routing_application
    state.snapshot = None
    proof = {"retrieved_at": datetime.now(timezone.utc).isoformat(),
        "request": {"identifier": state.holdings[0]["symbol"]}, "status": "not_found",
        "provider_errors": [{"provider": "finnhub", "code": "not_found"}]}
    state.cache.set_security_snapshot("security_lookup", state.holdings[0]["symbol"], "security-coverage-v1:bond", proof)
    candidate = main._ai_enrichment_candidates()["items"][0]
    state.cache.saved.clear()  # A new configuration/data refresh restores discovery.
    monkeypatch.setattr(main, "research_sources", lambda *_a, **_k: pytest.fail("Recovered API must not invoke AI research"))
    result = main._enrichment_research_security(candidate, "auto")
    assert result["source_status"] == "api_managed" and result["evidence"] == []


def test_recent_historical_observation_after_maturity_is_retained_without_current_write(routing_application):
    main, state = routing_application
    state.snapshot["details"]["maturity_date"] = (date.today() - timedelta(days=1)).isoformat()
    state.snapshot["current_quote_eligible"] = False
    before = deepcopy(state.snapshot)
    assert main._apply_automatic_security_prices(main._automatic_price_inventory()[0], state.snapshot) == 0
    assert state.saved == []
    assert state.snapshot == before and state.snapshot["items"][0]["price"] == 98.5


@pytest.mark.parametrize("field,value", [("quote_currency", "EUR"), ("quote_unit", "currency_per_unit"), ("enabled", False)])
def test_source_contract_change_cannot_reuse_old_snapshot(routing_application, field, value):
    from app.security_market_data import SecurityMarketData
    from test_security_market_data import CUSIP, Provider
    _main, state = routing_application
    config = {"security_lookup": {"finnhub": {"enabled": True, "quote_currency": "USD",
        "quote_unit": "percent_of_par", "api_key": "synthetic-secret-contract-key"}}}
    provider = Provider()
    first = SecurityMarketData(config, state.cache, providers={"finnhub": provider}).fetch(CUSIP, "bond")
    assert first["quote"]["currency"] == "USD" and len(provider.calls) == 1
    config["security_lookup"]["finnhub"][field] = value
    changed = SecurityMarketData(config, state.cache, providers={"finnhub": provider}).fetch(CUSIP, "bond", cache_only=True)
    assert changed["status"] == "missing" and changed["quote"] is None
    assert len(provider.calls) == 1
    assert "synthetic-secret-contract-key" not in str(state.cache.saved)


def test_old_schema_current_quote_is_ignored_without_provider_work():
    from app.security_market_data import SecurityMarketData
    from test_security_market_data import CUSIP

    class LegacyCache:
        def get_security_snapshot(self, *_args):
            return {"schema_version": "security-market-data-v1", "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "status": "ok", "quote": {"price": 100}, "items": [{"price": 100}],
                    "security": {"cusip": CUSIP}, "provider": "finnhub"}

    result = SecurityMarketData({}, LegacyCache(), providers={}).fetch(CUSIP, "bond", cache_only=True)
    assert result["status"] == "missing" and result["quote"] is None and result["items"] == []
    assert result["provider_requests"] == 0


def test_fresh_current_cache_crossing_maturity_becomes_historical_without_refetch(routing_application):
    from app.security_market_data import SecurityMarketData
    from test_security_market_data import CUSIP, Provider
    _main, state = routing_application
    provider = Provider()
    service = SecurityMarketData({}, state.cache, providers={"finnhub": provider})
    service.fetch(CUSIP, "bond")
    for snapshot in state.cache.saved.values():
        # A still-fresh saved response was fetched before the maturity boundary.
        # A later read must recheck today's calendar without discarding history.
        snapshot["details"]["maturity_date"] = (date.today() - timedelta(days=1)).isoformat()
        snapshot["current_quote_eligible"] = True
    result = service.fetch(CUSIP, "bond", cache_only=True)
    assert result["quote"] is None and result["quote_status"] == "matured"
    assert result["current_quote_eligible"] is False
    assert result["items"][0]["price"] == 99.354 and len(provider.calls) == 1


def test_heatmap_has_exact_three_signed_bands_and_white_text_contrast():
    from test_heatmap_frontend import run_ui
    run_ui(r'''
const positive=[heatmapColor(0.001),heatmapColor(1),heatmapColor(3)];
const negative=[heatmapColor(-0.001),heatmapColor(-1),heatmapColor(-3)];
assert.equal(new Set([...positive,...negative]).size,6);
for(const sign of [1,-1]){
 const colors=sign>0?positive:negative;
 for(const value of [Number.MIN_VALUE,0.01,0.999999999])assert.equal(heatmapColor(sign*value),colors[0]);
 for(const value of [1,1.000000001,2,2.999999999])assert.equal(heatmapColor(sign*value),colors[1]);
 for(const value of [3,3.000000001,10,1e100])assert.equal(heatmapColor(sign*value),colors[2]);
}
const all=[...positive,...negative,heatmapColor(0),heatmapColor(null)];
assert.equal(new Set(all).size,8);
for(const color of all){
 assert.match(color,/^#[0-9a-f]{6}$/i);
 const channels=[1,3,5].map(i=>parseInt(color.slice(i,i+2),16)/255);
 const linear=channels.map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4);
 const luminance=0.2126*linear[0]+0.7152*linear[1]+0.0722*linear[2];
 assert.ok(1.05/(luminance+0.05)>=4.5,`${color} white text contrast`);
}
''')

