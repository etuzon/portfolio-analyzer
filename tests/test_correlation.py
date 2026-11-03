from datetime import date, timedelta
from statistics import correlation
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth import AuthStore
from app.correlation import _pair, _returns, portfolio_correlation
from app.models import Holding, Ohlcv
from app.providers import MarketDataHub, SqliteCache


TODAY = date(2026, 11, 3)


def prices(returns, start=None):
    start = start or TODAY - timedelta(days=len(returns))
    value, rows = 100, [Ohlcv(start, 100, 100, 100, 100, 100, 1)]
    for offset, change in enumerate(returns, 1):
        value *= 1 + change
        rows.append(Ohlcv(start + timedelta(days=offset), value, value, value, value, value, 1))
    return rows


class Store:
    def __init__(self, holdings, local=None, manual=None):
        self.items = holdings
        self.local = local or {}
        self.manual = manual or {}

    def holdings(self):
        return [SimpleNamespace(holding=h) for h in self.items]

    def list_accounts(self):
        return [{"id": "a", "account_id": "First", "type": "Investment"}, {"id": "b", "account_id": "Second", "type": "Investment"}]

    def price_history(self, symbol, market, *_args):
        return self.local.get((symbol, market), [])

    def manual_security(self, symbol, market):
        return self.manual.get((symbol, market))


class Hub:
    def __init__(self, data):
        self.data, self.calls = data, []

    def cached_prices(self, symbol, *_args, stock_market="", **kwargs):
        self.calls.append((symbol, stock_market, kwargs))
        return self.data.get((symbol, stock_market), []), {}

    def prices(self, *_args, **_kwargs):
        raise AssertionError("Correlation must never download market data")


def holding(symbol, account="a", market="NASDAQ", quantity=1):
    return Holding(symbol=symbol, account_id=account, stock_market=market, quantity=quantity)


def calculate(store, hub, **kwargs):
    return portfolio_correlation(store, hub, today=TODAY, **kwargs)


@pytest.mark.parametrize("factor,expected", [(1, 1), (-1, -1)])
def test_known_positive_and_negative_return_correlations(factor, expected):
    changes = [0.01, -0.02, 0.03, -0.01] * 10
    result = calculate(Store([holding("A"), holding("B")]), Hub({
        ("A", "NASDAQ"): prices(changes), ("B", "NASDAQ"): prices([factor * x for x in changes]),
    }))
    assert result["matrix"][0][1]["value"] == expected
    assert result["matrix"][0][1]["observations"] == 40
    assert result["matrix"][0][1] == result["matrix"][1][0]
    assert result["matrix"][0][0]["value"] == 1


def test_matches_independent_return_oracle_rather_than_price_levels():
    x = [0.01, -0.02, 0.03, -0.01] * 10
    y = [0.02, 0.04, -0.01, -0.03] * 10
    result = calculate(Store([holding("A"), holding("B")]), Hub({
        ("A", "NASDAQ"): prices(x), ("B", "NASDAQ"): prices(y),
    }))
    assert result["matrix"][0][1]["value"] == pytest.approx(correlation(x, y), abs=1e-6)


def test_zero_is_distinct_from_missing_and_constant_returns():
    x, y = [0.01, -0.01, 0.01, -0.01] * 10, [0.01, 0.01, -0.01, -0.01] * 10
    result = calculate(Store([holding(s) for s in "ABCD"]), Hub({
        ("A", "NASDAQ"): prices(x), ("B", "NASDAQ"): prices(y), ("C", "NASDAQ"): prices([0] * 40),
    }))
    assert result["matrix"][0][1]["value"] == 0
    assert result["matrix"][0][2]["status"] == "constant_returns"
    assert result["matrix"][2][2]["value"] is None
    assert result["matrix"][0][3]["status"] == "insufficient_history"
    assert result["matrix"][0][3]["observations"] == 0
    assert result["status"] == "partial"


def test_threshold_and_exact_endpoint_alignment_without_fill():
    days = {TODAY - timedelta(days=i): 100 + i % 3 for i in range(41)}
    partial = dict(days)
    del partial[TODAY - timedelta(days=20)]
    result = _pair(_returns(days), _returns(partial))
    assert result["observations"] == 38  # two endpoints lost; no invented zero return
    assert _pair(_returns(dict(list(days.items())[:30])), _returns(days))["value"] is None
    assert _pair(_returns(dict(list(days.items())[:31])), _returns(days))["value"] is not None


def test_sparse_monthly_prices_do_not_become_daily_returns():
    sparse = {TODAY - timedelta(days=30 * i): 100 + i for i in range(40)}
    assert _returns(sparse) == {}


def test_deduplication_accounts_markets_and_short_direction():
    store = Store([holding("A"), holding("A", "b", quantity=-2), holding("A", "b", "TASE"), holding("C", quantity=0)])
    hub = Hub({("A", "NASDAQ"): prices([0.01, -0.02] * 20)})
    result = calculate(store, hub)
    assert result["asset_count"] == 2
    assert [(x["symbol"], x["stock_market"]) for x in result["assets"]] == [("A", "NASDAQ"), ("A", "TASE")]
    assert result["assets"][1]["price_count"] == 0
    assert len(hub.calls) == 2
    assert calculate(store, hub, account_id="a")["asset_count"] == 1
    with pytest.raises(ValueError, match="unknown_account"):
        calculate(store, hub, account_id="bad")


def test_raw_local_overrides_never_splice_into_adjusted_price_scale():
    rows = prices([0.01, -0.02] * 20)
    for row in rows:
        row.adjusted_close = row.close / 2
    local = [{"price_date": rows[-1].date.isoformat(), "price": rows[-1].close}]
    store = Store([holding("A"), holding("B")], local={("A", "NASDAQ"): local})
    result = calculate(store, Hub({("A", "NASDAQ"): rows, ("B", "NASDAQ"): rows}))
    assert result["assets"][0]["basis"] == "close"
    assert result["assets"][1]["basis"] == "adjusted_close"
    assert result["matrix"][0][1]["value"] == 1


def test_same_listing_with_conflicting_currency_is_one_unavailable_asset():
    usd, ils = holding("A"), holding("A", "b")
    ils.currency = "ILS"
    store = Store([usd, ils, holding("B")])
    hub = Hub({("A", "NASDAQ"): prices([0.01, -0.02] * 20)})
    result = calculate(store, hub)
    assert result["asset_count"] == 2
    assert result["assets"][0]["currency_conflict"] is True
    assert result["matrix"][0][1]["status"] == "currency_conflict"
    assert result["matrix"][0][1]["value"] is None
    assert result["matrix"][0][0]["value"] is None
    assert calculate(store, hub, account_id="a")["assets"][0]["currency_conflict"] is False


def test_manual_only_and_invalid_prices_are_explicitly_missing():
    rows = [{"price_date": row.date.isoformat(), "price": row.close} for row in prices([0.01, -0.02] * 20)]
    rows.append({"price_date": TODAY.isoformat(), "price": float("nan")})
    store = Store([holding("A")], local={("A", "NASDAQ"): rows}, manual={("A", "NASDAQ"): {"symbol": "A"}})
    hub = Hub({})
    result = calculate(store, hub)
    assert hub.calls == []
    assert result["assets"][0]["source"] == "local"
    assert result["assets"][0]["price_count"] == 41


def test_period_clamps_saved_evidence_and_excludes_future_prices():
    rows = prices([0.01, -0.02] * 100)
    rows += [Ohlcv(TODAY + timedelta(days=1), 1, 1, 1, 1, 1, 1)]
    result = calculate(Store([holding("A")]), Hub({("A", "NASDAQ"): rows}), period="3m")
    assert result["assets"][0]["from"] == (TODAY - timedelta(days=92)).isoformat()
    assert result["assets"][0]["to"] == TODAY.isoformat()
    assert result["assets"][0]["price_count"] == 93


def test_matrix_limit_never_silently_selects_assets():
    result = calculate(Store([holding(f"A{i}") for i in range(61)]), Hub({}))
    assert result["status"] == "too_many_assets"
    assert result["asset_count"] == 61
    assert result["matrix"] == []


def test_real_saved_cache_is_read_without_provider_io_or_modification(tmp_path):
    cache = SqliteCache(tmp_path / "market.sqlite3", ttl_hours=1)
    rows = prices([0.01, -0.02] * 20)
    cache.set_prices("yahoo_finance", "A", rows)
    cache.set_prices("yahoo_finance", "B", rows)
    class Provider:
        name = "yahoo_finance"
        def prices(self, *_args):
            raise AssertionError("Unexpected provider call")
    hub = object.__new__(MarketDataHub)
    hub.cache, hub.providers = cache, [Provider()]
    before = cache.path.read_bytes()
    result = calculate(Store([holding("A"), holding("B")]), hub)
    assert result["matrix"][0][1]["value"] == 1
    assert cache.path.read_bytes() == before


def test_api_requires_auth_and_allows_viewer_read_only(monkeypatch, tmp_path):
    auth = AuthStore(tmp_path / "auth.sqlite3")
    auth.initialize()
    viewer = auth.create_user({"username": "matrixviewer", "first_name": "Matrix", "last_name": "Viewer", "password": "ViewMatrix-Test123!", "role": "Viewer"})
    with auth._connect() as conn:
        conn.execute("update app_users set must_change_password = 0 where id = ?", (viewer["id"],))
    monkeypatch.setattr(main, "auth_store", auth)
    monkeypatch.setattr(main, "local_store", Store([holding("A"), holding("B")]))
    monkeypatch.setattr(main, "hub", lambda: Hub({("A", "NASDAQ"): prices([0.01, -0.02] * 20)}))
    # No lifespan: avoid scheduler or application-state changes.
    client = TestClient(main.app, base_url="https://localhost:6443")
    assert client.get("/api/portfolio/correlation").status_code == 401
    assert client.post("/api/auth/login", json={"username": "matrixviewer", "password": "ViewMatrix-Test123!"}).status_code == 200
    assert client.get("/api/portfolio/correlation").status_code == 200
    assert client.get("/api/portfolio/correlation?period=bad").status_code == 422
    assert client.get("/api/portfolio/correlation?account_id=bad").status_code == 400
