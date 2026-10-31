"""Opening a chart must reuse saved evidence before contacting providers."""
from datetime import date, timedelta

import pytest

from app import main
from app.models import Ohlcv
from app.providers import MarketDataHub, SqliteCache


def test_nref_chart_uses_saved_history_without_provider_io_and_preserves_local_overrides(monkeypatch, tmp_path):
    today = date.today()
    cached = [Ohlcv(today - timedelta(days=offset), 10, 11, 9, 10, 10, 100) for offset in range(40, -1, -1)]
    cache = SqliteCache(tmp_path / "market.sqlite3", ttl_hours=1)
    cache.set_prices("yahoo_finance", "NREF", cached)

    class Provider:
        name = "yahoo_finance"
        calls = 0

        def prices(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("The chart must not wait for an external provider when saved prices exist")

    market_hub = object.__new__(MarketDataHub)
    market_hub.providers = [Provider()]
    market_hub.cache = cache

    class Store:
        def price_history(self, *args):
            return [{"price_date": today.isoformat(), "price": 12}]

        def manual_security_exists(self, *args):
            return False

    monkeypatch.setattr(main, "hub", lambda: market_hub)
    monkeypatch.setattr(main, "local_store", Store())
    before = cache.get_prices("yahoo_finance", "NREF", today - timedelta(days=40), today)
    result = main.security_history("NREF", "MANUAL", period="1m")
    assert result["source"] == "merged"
    assert result["status"] == {"yahoo_finance": "cached"}
    assert result["points"][-1]["price"] == 12
    assert len(result["points"]) == len(cached)
    assert market_hub.providers[0].calls == 0
    assert cache.get_prices("yahoo_finance", "NREF", today - timedelta(days=40), today) == before


def test_cached_us_ticker_cannot_be_used_for_a_different_tase_listing(tmp_path):
    cache = SqliteCache(tmp_path / "market.sqlite3", ttl_hours=1)
    cache.set_prices("yahoo_finance", "EXAMPLE", [Ohlcv(date.today(), 10, 10, 10, 10, 10, 1)])
    market_hub = object.__new__(MarketDataHub)
    market_hub.providers = [type("Provider", (), {"name": "yahoo_finance"})()]
    market_hub.cache = cache
    prices, status = market_hub.cached_prices("EXAMPLE", date.today() - timedelta(days=30), date.today(), stock_market="TASE")
    assert prices == []
    assert status == {"cache": "pending"}


@pytest.mark.parametrize("old_cache,local_override", [(True, False), (False, True)])
def test_uncovered_chart_interval_and_local_only_override_keep_live_history_fallback(monkeypatch, tmp_path, old_cache, local_override):
    today = date.today()
    cache = SqliteCache(tmp_path / "market.sqlite3", ttl_hours=1)
    if old_cache:
        cache.set_prices("yahoo_finance", "NREF", [Ohlcv(today - timedelta(days=180), 10, 10, 10, 10, 10, 1)])

    class Provider:
        name = "yahoo_finance"
        calls = 0

        def prices(self, *args, **kwargs):
            self.calls += 1
            return [Ohlcv(today - timedelta(days=offset), 10, 11, 9, 10, 10, 100) for offset in range(30, -1, -1)]

    market_hub = object.__new__(MarketDataHub)
    market_hub.providers = [Provider()]
    market_hub.cache = cache

    class Store:
        def price_history(self, *args):
            return [{"price_date": today.isoformat(), "price": 12}] if local_override else []

        def manual_security_exists(self, *args):
            return False

    monkeypatch.setattr(main, "hub", lambda: market_hub)
    monkeypatch.setattr(main, "local_store", Store())
    result = main.security_history("NREF", "NYSE", period="1m", date_from=(today - timedelta(days=31)).isoformat())
    assert market_hub.providers[0].calls == 1
    assert len(result["points"]) == 31
    assert result["points"][-1]["price"] == (12 if local_override else 10)


@pytest.mark.parametrize("old_cache", [False, True])
def test_failed_provider_without_visible_saved_prices_preserves_error_state_for_retry(monkeypatch, tmp_path, old_cache):
    class Provider:
        name = "yahoo_finance"

        def prices(self, *args, **kwargs):
            raise TimeoutError("private provider detail")

    market_hub = object.__new__(MarketDataHub)
    market_hub.providers = [Provider()]
    market_hub.cache = SqliteCache(tmp_path / "market.sqlite3", ttl_hours=1)
    if old_cache:
        market_hub.cache.set_prices("yahoo_finance", "NREF", [Ohlcv(date.today() - timedelta(days=180), 10, 10, 10, 10, 10, 1)])

    class Store:
        def price_history(self, *args):
            return []

        def manual_security_exists(self, *args):
            return False

    monkeypatch.setattr(main, "hub", lambda: market_hub)
    monkeypatch.setattr(main, "local_store", Store())
    result = main.security_history("NREF", "NYSE", date_from=(date.today() - timedelta(days=31)).isoformat())
    assert result["points"] == []
    assert result["state"] == "error"
    assert "TimeoutError" in result["status"]["yahoo_finance"]
    assert "private provider detail" not in str(result)
