"""Complete-panel market evidence and authenticated read-only optimization."""
from datetime import date, timedelta
from math import cos, sin
from types import SimpleNamespace

from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
import numpy as np
import pytest

from app import main
from app.auth import AuthStore
from app.local_portfolio import LocalPortfolioStore
from app.models import Holding, Ohlcv
from app.optimization import OptimizationError
from app.optimization_data import _weekly_panel, optimization_universe, optimize_portfolio

TODAY = date(2026, 11, 3)


def history(which=0, weeks=70, end=TODAY - timedelta(days=4), adjusted_factor=1):
    value = 100.0
    points = []
    for i in range(weeks + 1):
        if i:
            change = .002 + .015 * (sin(i * .71) if which == 0 else cos(i * .43))
            value *= 1 + change
        day = end - timedelta(weeks=weeks-i)
        points.append(Ohlcv(day, value, value, value, value, value*adjusted_factor, 100))
    return points


class Store:
    def __init__(self, holdings=None, local=None, manual=None):
        self.positions = holdings if holdings is not None else [holding("AAA"), holding("BBB", quantity=2)]
        self.local = local or {}
        self.manual = manual or {}
    def holdings(self): return [SimpleNamespace(holding=row) for row in self.positions]
    def list_accounts(self): return [{"id": "a", "type":"Investment", "account_id": "Synthetic A"}, {"id": "b", "type":"Investment", "account_id": "Synthetic B"}]
    def manual_security(self, symbol, market): return self.manual.get(symbol)
    def price_history(self, symbol, market, start, end): return [r for r in self.local.get(symbol, []) if start.isoformat() <= r["price_date"] <= end.isoformat()]


class Hub:
    def __init__(self, histories=None): self.histories = histories if histories is not None else {"AAA": history(), "BBB": history(1)}; self.calls = []
    def cached_prices(self, symbol, start, end, **context):
        self.calls.append((symbol, context))
        return [row for row in self.histories.get(symbol, []) if start <= row.date <= end], {"fixture": "cached"}
    def prices(self, *args, **kwargs): raise AssertionError("Optimization cannot download prices")


def holding(symbol, **kwargs):
    return Holding(symbol=symbol, account_id=kwargs.pop("account_id", "a"), stock_market=kwargs.pop("stock_market", "NASDAQ"),
                   asset_class=kwargs.pop("asset_class", "EQUITY"), currency=kwargs.pop("currency", "USD"), quantity=kwargs.pop("quantity", 1), **kwargs)


def calculate(store=None, hub=None, **changes):
    store, hub = store or Store(), hub or Hub()
    universe = optimization_universe(store, hub, currency="USD", today=TODAY)
    payload = {"currency": "USD", "asset_ids": [row["id"] for row in universe["assets"]], **changes}
    return optimize_portfolio(store, hub, payload, today=TODAY)


def test_annual_model_matches_independent_complete_weekly_sample_and_current_raw_values():
    hub = Hub()
    result = calculate(hub=hub, shrinkage_percent=10)
    a, b = hub.histories["AAA"], hub.histories["BBB"]
    panel = np.array([[x.close / prev_x.close - 1, y.close / prev_y.close - 1] for prev_x, x, prev_y, y in zip(a, a[1:], b, b[1:])])
    means = panel.mean(axis=0)*52
    sample = np.cov(panel, rowvar=False, ddof=1)*52
    covariance = .9*sample+.1*np.diag(np.diag(sample))
    assert result["status"] == "ok" and result["observations"] == 70
    assert np.asarray(result["covariance"]) == pytest.approx(covariance)
    assert [row["historical_return_percent"] for row in result["assets"]] == pytest.approx(means*100)
    w = np.asarray(result["solution"]["weights"])
    assert w.sum() == pytest.approx(1) and np.all(w >= 0)
    assert result["solution"]["expected_return_percent"] == pytest.approx(means @ w*100)
    assert result["solution"]["volatility_percent"] == pytest.approx(np.sqrt(w @ covariance @ w)*100)
    values = np.array([a[-1].close, b[-1].close*2])
    assert result["current"]["weights"] == pytest.approx(values/values.sum())
    assert result["intervals"][0] == {"from": a[0].date.isoformat(), "to": a[1].date.isoformat()}


def test_adjustment_scale_is_global_and_local_override_forces_raw_for_every_asset():
    hub = Hub({"AAA": history(adjusted_factor=.5), "BBB": history(1, adjusted_factor=.25)})
    baseline = calculate(hub=hub)
    assert baseline["basis"] == "adjusted_close"
    row = hub.histories["AAA"][30]
    local = {"AAA": [{"price_date": row.date.isoformat(), "price": row.close, "currency": "USD", "asset_class": "EQUITY"}]}
    raw = calculate(Store(local=local), hub)
    assert raw["basis"] == "close" and "unadjusted_prices" in raw["warnings"]
    assert raw["covariance"] == pytest.approx(np.asarray(baseline["covariance"]))
    assert [r["historical_return_percent"] for r in raw["assets"]] == pytest.approx([r["historical_return_percent"] for r in baseline["assets"]])


def test_daily_price_counts_do_not_establish_common_weekly_returns_or_use_future_quotes():
    shifted = [Ohlcv(row.date-timedelta(days=1), row.close, row.close, row.close, row.close, row.close, 100) for row in history(1)]
    result = calculate(hub=Hub({"AAA": history(), "BBB": shifted}))
    assert result["reason"] == "insufficient_common_history" and result["observations"] == 0
    raw_a = {row.date: row.close for row in history()}
    raw_b = {row.date: row.close for row in history(1)}
    raw_a[TODAY] = raw_b[TODAY] = 10000
    raw_a[TODAY+timedelta(days=3)] = raw_b[TODAY+timedelta(days=3)] = 20000
    panel, intervals = _weekly_panel([raw_a, raw_b], TODAY)
    assert len(panel) == 70 and intervals[-1][1] < TODAY
    missing = history()[35].date
    raw_a.pop(missing)
    panel, intervals = _weekly_panel([raw_a, raw_b], TODAY)
    assert len(panel) == 68
    assert all((after-before).days <= 10 for before, after in intervals)


def test_listings_deduplicate_accounts_while_currency_conflicts_and_nonlong_assets_are_visible():
    holdings = [holding("AAA"), holding("AAA", account_id="b", quantity=2), holding("BBB", quantity=2),
                holding("SHORT", quantity=-5), holding("OPTION", asset_class="OPTION"), holding("ILS", stock_market="TASE", currency="ILS")]
    store, hub = Store(holdings), Hub()
    universe = optimization_universe(store, hub, currency="USD", today=TODAY)
    assert len(universe["assets"]) == 2 and universe["assets"][0]["quantity"] == 3
    assert {row["reason"] for row in universe["excluded"]} == {"short_position", "unsupported_asset", "different_currency"}
    store.positions.append(holding("AAA", account_id="b", currency="EUR"))
    universe = optimization_universe(store, hub, currency="USD", today=TODAY)
    assert any(row["reason"] == "currency_conflict" for row in universe["excluded"])
    assert len(universe["assets"]) == 1
    with pytest.raises(OptimizationError, match="optimization_unknown_account"):
        optimization_universe(store, hub, account_id="missing", today=TODAY)


def test_wrong_currency_and_unknown_exchange_never_borrow_us_provider_history():
    hub = Hub({"AAA": history(), "BBB": history(1)})
    universe = optimization_universe(Store([holding("AAA", currency="EUR"), holding("BBB", stock_market="XETRA", currency="EUR")]), hub, currency="EUR", today=TODAY)
    assert hub.calls == [] and all(not row["eligible"] for row in universe["assets"])
    local = {"AAA": [{"price_date": row.date.isoformat(), "price": row.close, "currency": "ILS", "asset_class": "EQUITY"} for row in history()]}
    manual = {"AAA": {"secondary_symbol": ""}, "BBB": {"secondary_symbol": ""}}
    universe = optimization_universe(Store(local=local, manual=manual), hub, currency="USD", today=TODAY)
    assert all(not row["eligible"] for row in universe["assets"])


def test_stale_evidence_can_model_history_without_inventing_current_sleeve_weights():
    result = calculate(hub=Hub({"AAA": history(end=TODAY-timedelta(days=18)), "BBB": history(1,end=TODAY-timedelta(days=18))}))
    assert result["status"] == "ok" and result["current"] is None
    assert {"stale_prices", "stale_common_history", "current_weights_unavailable"} <= set(result["warnings"])
    assert all(row["current_weight_percent"] is None for row in result["assets"])


def test_overrides_risk_free_and_shrinkage_have_declared_units_and_validate_without_writes():
    store, hub = Store(), Hub()
    ids = [row["id"] for row in optimization_universe(store, hub, currency="USD", today=TODAY)["assets"]]
    result = calculate(store, hub, expected_returns={ids[0]: 12, ids[1]: 4}, shrinkage_percent=100, risk_free_rate_percent=2)
    assert [row["expected_return_percent"] for row in result["assets"]] == [12, 4]
    assert result["covariance"][0][1] == 0
    p = result["solution"]
    assert p["sharpe"] == pytest.approx((p["expected_return_percent"]-2)/p["volatility_percent"])
    for change in [{"expected_returns": {"unknown": 5}}, {"expected_returns": {ids[0]: None}}, {"max_weight_percent": True}, {"shrinkage_percent": 101}, {"risk_free_rate_percent": float("nan")}, {"objective": "target_return"}, {"asset_ids": [ids[0], ids[0]]}]:
        with pytest.raises(OptimizationError): calculate(store, hub, **change)
    assert calculate(store, hub, max_weight_percent=49)["reason"] == "optimization_infeasible_weights"
    assert calculate(store, hub, objective="target_return", target_return_percent=999)["reason"] == "optimization_infeasible_target"
    assert calculate(store, hub, objective="max_sharpe", risk_free_rate_percent=100)["reason"] == "optimization_no_positive_excess_return"


def test_constant_price_series_never_produces_a_risk_free_optimized_recommendation():
    rows = [Ohlcv(row.date, 100, 100, 100, 100, 100, 100) for row in history()]
    result = calculate(hub=Hub({"AAA": rows, "BBB": history(1)}))
    assert result["reason"] == "constant_returns" and result["solution"] is None


def test_extreme_finite_quantities_and_aggregate_values_remain_json_safe():
    store, hub = Store([holding("AAA", quantity=1e308), holding("BBB")]), Hub()
    universe = optimization_universe(store, hub, currency="USD", today=TODAY)
    assert all(asset["current_weight_percent"] is None for asset in universe["assets"])
    assert JSONResponse(universe).status_code == 200
    result = calculate(store, hub)
    assert result["status"] == "ok" and result["current"] is None
    assert "current_weights_unavailable" in result["warnings"]
    assert JSONResponse(result).status_code == 200
    store.positions.append(holding("AAA", quantity=1e308, account_id="b"))
    universe = optimization_universe(store, hub, currency="USD", today=TODAY)
    assert any(row["reason"] == "invalid_position" for row in universe["excluded"])
    assert JSONResponse(universe).status_code == 200


@pytest.mark.parametrize("role", ["Viewer", "Operator"])
def test_authenticated_computation_is_read_only_including_viewers(monkeypatch, tmp_path, role):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    account = store.save_account({"account_id": "Optimization fixture", "type": "Investment", "currency": "USD", "location": "USA", "persons": [{"name": "Synthetic", "birth_date": "01/01/1990"}]})
    # Provider fixtures remain independent from the ledger and local price store.
    for symbol in ("AAA", "BBB"):
        store.add_transaction({"account_db_id": account["id"], "action": "BUY", "symbol": symbol, "stock_market": "NASDAQ", "quantity": 1, "price_input": 100, "trade_date": "2025-01-01"})
    auth = AuthStore(store.path); auth.initialize()
    user = auth.create_user({"username": "optqa", "first_name": "Synthetic", "last_name": role, "role": role, "password": "Optimization-QA123!"})
    with auth._connect() as conn: conn.execute("update app_users set must_change_password=0 where id=?", (user["id"],))
    monkeypatch.setattr(main, "local_store", store); monkeypatch.setattr(main, "auth_store", auth); monkeypatch.setattr(main, "hub", lambda: Hub())
    # Store-created manual metadata may have no provider alias: explicitly name
    # it in this isolated fixture to establish matching cached provider identity.
    monkeypatch.setattr(store, "manual_security", lambda symbol, market: {"secondary_symbol": symbol})
    client = TestClient(main.app, base_url="https://localhost:6443")
    assert client.get("/api/portfolio/optimization").status_code == 401
    session = client.post("/api/auth/login", json={"username": "optqa", "password": "Optimization-QA123!"}).json()
    baseline = store.export_data()["data"]; token = store.change_token()
    universe = client.get("/api/portfolio/optimization?currency=USD").json()
    payload = {"currency": "USD", "asset_ids": [row["id"] for row in universe["assets"]]}
    assert client.post("/api/portfolio/optimization", json=payload).status_code == 403
    response = client.post("/api/portfolio/optimization", json=payload, headers={"X-CSRF-Token": session["csrf_token"]})
    assert response.status_code == 200 and response.json()["status"] == "ok"
    assert store.change_token() == token and store.export_data()["data"] == baseline
    assert client.get("/api/portfolio/optimization?period=invalid").status_code == 400
