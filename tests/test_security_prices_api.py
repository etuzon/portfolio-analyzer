from datetime import date, datetime, timedelta
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.local_portfolio import LocalPortfolioStore
from app.models import Ohlcv
from app.security_prices import price_router


@pytest.fixture
def prices(tmp_path):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    store.save_manual_security({"symbol": "ABC", "stock_market": "NASDAQ", "name": "Example", "currency": "USD", "location": "USA", "asset_class": "EQUITY"})
    invalidations = []
    app = FastAPI()
    app.include_router(price_router(lambda: store, lambda: pytest.fail("Manual listing must not download provider data"), lambda: invalidations.append(True), date(2020, 1, 1)))
    return SimpleNamespace(store=store, client=TestClient(app), invalidations=invalidations)


def observation(day=None, **changes):
    return {
        "price_input": 123.45, "price_date": (day or date.today()).isoformat(),
        "currency": "USD", "quote_unit": "currency", "price_basis": "close",
        "source_url": "https://exchange.example/ABC/history", "observed_at": None,
        # Keep the retrieval calendar day aligned with date.today() even during
        # the interval when local midnight precedes midnight in UTC.
        "retrieved_at": datetime.now().astimezone().isoformat(), **changes,
    }


def put(env, items, **changes):
    return env.client.put("/api/security/prices", json={"symbol": "ABC", "stock_market": "NASDAQ", "items": items, **changes})


def test_batch_upsert_returns_persisted_identity_and_current_ignores_history_filter(prices):
    today = date.today()
    first = put(prices, [observation()])
    assert first.status_code == 200, first.text
    identifier = first.json()["items"][0]["id"]
    second = put(prices, [observation(price_input=150), observation(today - timedelta(days=10), price_input=90)])
    assert second.status_code == 200, second.text
    assert second.json()["items"][0]["id"] == identifier
    assert len(prices.store.list_prices()) == 2
    params = {"symbol": "ABC", "stock_market": "NASDAQ", "date_to": (today - timedelta(days=1)).strftime("%d/%m/%Y")}
    filtered = prices.client.get("/api/security/prices", params=params).json()
    assert [row["price"] for row in filtered["items"]] == [90]
    assert filtered["current"]["price"] == 150
    assert filtered["current_status"] == "dated"
    assert filtered["current"]["evidence"]["source_url"] == "https://exchange.example/ABC/history"
    assert filtered["current"]["price_basis"] == "close"
    current = prices.client.get("/api/security/price", params={"symbol": "ABC", "stock_market": "NASDAQ"}).json()
    assert current["current"] == filtered["current"]
    assert "items" not in current
    assert len(prices.invalidations) == 2


@pytest.mark.parametrize("location,currency,asset_class,instrument_type,market,unit,raw,normalized", [
    ("USA", "USD", "EQUITY", "STOCK", "NASDAQ", "currency", 123.45, 123.45),
    ("Israel", "ILS", "EQUITY", "STOCK", "TASE", "agorot", 12345, 123.45),
    ("USA", "USD", "BOND", "BOND", "NYSE", "cents", 9875, 98.75),
])
def test_financial_quote_conventions_and_alias_identity(prices, location, currency, asset_class, instrument_type, market, unit, raw, normalized):
    prices.store.save_manual_security({"symbol": "PRIMARY", "secondary_symbol": "ALIAS", "stock_market": market, "name": "Example", "currency": currency, "location": location, "asset_class": asset_class, "instrument_type": instrument_type})
    result = put(prices, [observation(currency=currency, quote_unit=unit, price_input=raw)], symbol="ALIAS", stock_market=market)
    assert result.status_code == 200, result.text
    row = result.json()["items"][0]
    assert row["price"] == normalized
    assert row["price_input"] == raw
    assert row["symbol"] == "PRIMARY"
    assert len(prices.store.price_history("ALIAS", market)) == 1


@pytest.mark.parametrize("changes", [
    {"price_input": 0}, {"price_input": -1}, {"price_input": True}, {"price_input": "15"}, {"price_input": 10 ** 400},
    {"price_date": "nonsense"}, {"price_date": "2019-12-31"},
    {"price_date": (date.today() + timedelta(days=1)).isoformat()},
    {"currency": "ILS"}, {"quote_unit": "agorot"}, {"price_basis": "adjusted_close"},
    {"source_url": "file:///etc/passwd"}, {"source_url": "https://user:secret@example.org/quote"},
    {"retrieved_at": "2026-01-01T00:00:00"}, {"observed_at": "2026-01-01T00:00:00Z"},
])
def test_invalid_member_never_partially_writes_batch(prices, changes):
    response = put(prices, [observation(date.today() - timedelta(days=1)), observation(**changes)])
    assert response.status_code == 422, response.text
    assert prices.store.list_prices() == []
    assert prices.invalidations == []


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_raw_json_returns_validation_error_without_writing(prices, raw):
    body = json.dumps({"symbol": "ABC", "stock_market": "NASDAQ", "items": [observation()]}).replace("123.45", raw)
    response = prices.client.put("/api/security/prices", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"] == ["body", "items", 0, "price_input"]
    assert prices.store.list_prices() == []


def test_missing_stale_duplicate_and_unknown_listing(prices):
    params = {"symbol": "ABC", "stock_market": "NASDAQ"}
    missing = prices.client.get("/api/security/price", params=params).json()
    assert missing["current"] is None and missing["current_status"] == "missing"
    assert put(prices, [observation(), observation()]).status_code == 422
    assert put(prices, [observation()], stock_market="TASE").status_code == 404
    assert prices.client.get("/api/security/prices", params={**params, "date_from": "bad"}).status_code == 422
    assert put(prices, [observation(date.today() - timedelta(days=8))]).status_code == 200
    assert prices.client.get("/api/security/price", params=params).json()["current_status"] == "stale"


def test_store_batch_rolls_back_after_database_failure(prices):
    payload = {"symbol": "ABC", "stock_market": "NASDAQ", "price_input": 25, "price_date": date.today().isoformat()}
    with pytest.raises(ValueError):
        prices.store.save_prices([payload, {**payload, "symbol": ""}])
    assert prices.store.list_prices() == []


def test_same_day_observation_cannot_regress_or_lose_its_known_timestamp(prices):
    yesterday = date.today() - timedelta(days=1)
    newer = yesterday.isoformat() + "T16:00:00Z"
    older = yesterday.isoformat() + "T10:00:00Z"
    assert put(prices, [observation(yesterday, observed_at=newer)]).status_code == 200
    assert put(prices, [observation(yesterday, price_input=100, observed_at=older)]).status_code == 409
    assert put(prices, [observation(yesterday, price_input=100, observed_at=None)]).status_code == 409
    assert prices.store.list_prices()[0]["price"] == 123.45


def test_evidence_override_survives_same_day_provider_in_dashboard_and_reports(prices):
    from app.portfolio_refresh import attach_market_analysis
    from copy import deepcopy
    store = prices.store
    store.save_manual_security({"symbol": "DUAL", "secondary_symbol": "DUAL.A", "stock_market": "NASDAQ", "name": "Example", "currency": "USD", "location": "USA"})
    owner = store.save_account({"type": "Investment", "location": "USA", "currency": "USD", "initial_cash": 1000, "persons": [{"name": "Test", "birth_date": "01/01/1990"}]})
    store.add_transaction({"account_db_id": owner["id"], "action": "BUY", "symbol": "DUAL", "stock_market": "NASDAQ", "quantity": 2, "price_input": 50, "trade_date": date.today().isoformat(), "currency": "USD", "location": "USA", "asset_class": "EQUITY"})
    assert put(prices, [observation(price_input=100)], symbol="DUAL").status_code == 200
    local = store.holdings()[0]
    provider = deepcopy(local)
    for values in provider.price_ranges.values():
        values.pop("local_override", None)
        values["current"] = 110
    merged = attach_market_analysis(local, provider)
    assert merged.holding.market_value == 200
    assert all(row["current"] == 100 for row in merged.price_ranges.values() if row.get("current_date"))
    from app.metrics import to_dict
    reports = store.reports(valuation_items=[to_dict(provider)])
    assert reports["securities_value"] == 200
    history = store.account_trends({"from": date.today().isoformat(), "to": date.today().isoformat()}, valuation_items=[to_dict(provider)])
    assert history["accounts"][0]["points"][-1]["value"] == 1100


def test_reads_preserve_cache_and_local_override_uses_raw_close(prices):
    prices.store.save_manual_security({"symbol": "DUAL", "secondary_symbol": "DUAL.A", "stock_market": "NYSE", "name": "Example", "currency": "USD", "location": "USA"})
    today = date.today()
    cached = [Ohlcv(today - timedelta(days=1), 20, 20, 20, 20, 10, 1), Ohlcv(today, 25, 25, 25, 25, 12, 1)]
    seen = []
    def saved(*args, **kwargs):
        seen.append((args, kwargs))
        return cached, {"fixture": "cached"}
    app = FastAPI()
    app.include_router(price_router(lambda: prices.store, lambda: SimpleNamespace(cached_prices=saved), lambda: None, date(2020, 1, 1)))
    client = TestClient(app)
    result = client.get("/api/security/prices", params={"symbol": "DUAL.A", "stock_market": "NYSE"}).json()
    assert [row["price"] for row in result["items"]] == [20, 25]
    assert result["provider_status"] == {"fixture": "cached"}
    assert seen[0][1] == {"secondary_symbol": "DUAL.A", "stock_market": "NYSE"}
    assert cached[0].adjusted_close == 10


def test_routes_enforce_existing_auth_role_csrf_and_rest_mode(tmp_path, monkeypatch):
    from app import main
    from app.auth import AuthStore
    store = LocalPortfolioStore(tmp_path / "auth.sqlite3")
    store.save_manual_security({"symbol": "ABC", "stock_market": "NASDAQ", "name": "Example", "currency": "USD", "location": "USA"})
    auth = AuthStore(store.path)
    auth.initialize()
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    client = TestClient(main.app, base_url="https://localhost:6443")
    assert client.get("/api/security/price", params={"symbol": "ABC", "stock_market": "NASDAQ"}).status_code == 401
    session = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    changed = client.post("/api/auth/change-password", headers={"X-CSRF-Token": session["csrf_token"]}, json={"current_password": "admin", "new_password": "Test-Prices-2026-Password!", "confirm_password": "Test-Prices-2026-Password!"})
    assert changed.status_code == 200
    assert client.put("/api/security/prices", json={"symbol": "ABC", "stock_market": "NASDAQ", "items": [observation()]}).status_code == 403
    assert store.list_prices() == []


def test_bounded_research_controller_integrates_with_real_price_api(prices):
    from app.price_agent import PriceAgent, price_agent_settings
    yesterday = date.today() - timedelta(days=1)
    url = "https://exchange.example/ABC/quote"
    text = f"ABC NASDAQ USD Last 150.25 on {yesterday.isoformat()}."
    proposed = {key: value for key, value in observation(yesterday, price_input=150.25, price_basis="last", source_url=url, evidence_quote=text).items() if key != "retrieved_at"}
    decisions = iter([
        ("search_web", {"query": "ABC NASDAQ USD last price"}),
        ("read_source", {"url": url}),
        ("submit_prices", {"items": [proposed]}),
    ])
    def model(*_):
        name, args = next(decisions)
        return {"role": "assistant", "tool_calls": [{"id": name, "function": {"name": name, "arguments": json.dumps(args)}}]}
    def rest(method, path, *, params=None, payload=None):
        response = prices.client.request(method, path, params=params, json=payload)
        assert response.status_code == 200, response.text
        return response.json()
    agent = PriceAgent(price_agent_settings({}), rest, model=model, search=lambda _: [{"url": url}], fetch=lambda _: text)
    result = agent.run("ABC", "NASDAQ")
    assert result["status"] == "updated"
    assert result["model_calls"] == result["rest_calls"] == 3
    assert result["items"][0]["price"] == 150.25
    assert result["items"][0]["evidence"]["evidence_quote"] == text
    assert prices.invalidations == [True]
