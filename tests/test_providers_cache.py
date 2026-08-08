import time
from datetime import date, timedelta

from app.models import Ohlcv
from app import providers
from app.providers import MarketDataHub, NasdaqQuoteProvider, SecCompanyFactsProvider, SqliteCache, YahooChartProvider


def test_sqlite_cache_round_trips_and_reports_limit(tmp_path):
    cache = SqliteCache(tmp_path / "market-cache.sqlite3", ttl_hours=24, max_mb=1)
    cache.set("quote:AAPL", {"symbol": "AAPL", "price": 200})

    assert cache.get("quote:AAPL") == {"symbol": "AAPL", "price": 200}
    status = cache.status()
    assert status["entries"] == 1
    assert status["max_mb"] == 1


def test_sqlite_cache_persists_daily_prices_and_checked_date(tmp_path):
    cache = SqliteCache(tmp_path / "market-cache.sqlite3", ttl_hours=24, max_mb=1)
    rows = [
        Ohlcv(date=date(2026, 1, 2), open=10, high=11, low=9, close=10.5, adjusted_close=10.5, volume=1000),
        Ohlcv(date=date(2026, 1, 3), open=11, high=12, low=10, close=11.5, adjusted_close=11.5, volume=1200),
    ]

    cache.set_prices("provider", "aapl", rows)
    cache.set_prices_checked("provider", "AAPL", date(2026, 1, 4))

    cached = cache.get_prices("provider", "AAPL", date(2026, 1, 1), date(2026, 1, 5))
    assert [row.date for row in cached] == [date(2026, 1, 2), date(2026, 1, 3)]
    assert cache.price_bounds("provider", "AAPL") == (date(2026, 1, 2), date(2026, 1, 3))
    assert cache.get_prices_checked("provider", "AAPL") == date(2026, 1, 4)
    assert cache.status()["price_entries"] == 2


def test_market_data_hub_chooses_fuller_price_series(tmp_path):
    class SparseProvider:
        name = "sparse"

        def prices(self, symbol, from_date, to_date):
            return [Ohlcv(date=to_date - timedelta(days=3), open=1, high=1, low=1, close=1, adjusted_close=1, volume=0)]

    class FullProvider:
        name = "full"

        def prices(self, symbol, from_date, to_date):
            return [
                Ohlcv(date=from_date + timedelta(days=idx), open=1, high=1, low=1, close=idx, adjusted_close=idx, volume=0)
                for idx in range(35)
            ]

    hub = MarketDataHub({"primary": "frankfurter_fx", "fallback": [], "experimental_fallback": [], "cache_ttl_hours": 24}, {})
    hub.providers = [SparseProvider(), FullProvider()]

    rows, status = hub.prices("ABC", date(2026, 1, 1), date(2026, 3, 1))

    assert len(rows) == 35
    assert status == {"sparse": "ok", "full": "ok"}


def test_historical_cache_prefixes_do_not_expire(tmp_path):
    cache = SqliteCache(tmp_path / "market-cache.sqlite3", ttl_hours=1, max_mb=1)
    cache.set("sec:companyfacts:0000000001", {"facts": {"ok": True}})
    with cache._connect() as conn:
        conn.execute("update cache set created_at = ? where key = ?", (time.time() - 7200, "sec:companyfacts:0000000001"))

    assert cache.get("sec:companyfacts:0000000001") == {"facts": {"ok": True}}


def test_market_screener_falls_back_to_sec_ticker_lookup(monkeypatch, tmp_path):
    class StubSecProvider:
        name = "sec_company_tickers"

        def __init__(self, config, cache):
            self.config = config
            self.cache = cache

        def market_screener(self, criteria):
            return [{"symbol": "CSCO", "name": "CISCO SYSTEMS, INC.", "price": None}]

    monkeypatch.setattr(providers, "SecCompanyTickerProvider", StubSecProvider)
    hub = MarketDataHub({"primary": "frankfurter_fx", "fallback": [], "experimental_fallback": [], "cache_ttl_hours": 24}, {})
    hub.cache = SqliteCache(tmp_path / "market-cache.sqlite3", ttl_hours=24, max_mb=1)

    rows, status = hub.market_screener({"query": "CSCO"})

    assert status["sec_company_tickers"] == "ok"
    assert rows[0]["symbol"] == "CSCO"
    assert rows[0]["name"] == "CISCO SYSTEMS, INC."


def test_nasdaq_quote_provider_maps_public_stock_quote(monkeypatch, tmp_path):
    provider = NasdaqQuoteProvider({}, SqliteCache(tmp_path / "market-cache.sqlite3", ttl_hours=24, max_mb=1))

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "symbol": "CSCO",
                    "companyName": "Cisco Systems, Inc.",
                    "exchange": "NASDAQ-GS",
                    "isNasdaqListed": True,
                    "primaryData": {
                        "lastSalePrice": "$115.99",
                        "netChange": "+2.43",
                        "percentageChange": "+2.14%",
                        "lastTradeTimestamp": "Jul 30, 2026",
                    },
                }
            }

    class Client:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, params):
            assert url.endswith("/CSCO/info")
            assert params == {"assetclass": "stocks"}
            return Response()

    monkeypatch.setattr(providers.httpx, "Client", Client)

    quote = provider.quote("csco")

    assert quote["symbol"] == "CSCO"
    assert quote["price"] == 115.99
    assert quote["currency"] == "USD"
    assert quote["change"] == 2.43
    assert quote["changes_percentage"] == 2.14


def test_yahoo_summary_maps_fundamentals_and_profile(monkeypatch, tmp_path):
    provider = YahooChartProvider({}, SqliteCache(tmp_path / "market-cache.sqlite3", ttl_hours=24, max_mb=1))

    def fake_get_json(url, params, cache_key, force_refresh=False):
        return {
            "quoteSummary": {
                "result": [
                    {
                        "incomeStatementHistory": {
                            "incomeStatementHistory": [
                                {"endDate": {"fmt": "2025-12-31"}, "totalRevenue": {"raw": 200}, "netIncome": {"raw": 20}},
                                {"endDate": {"fmt": "2024-12-31"}, "totalRevenue": {"raw": 100}, "netIncome": {"raw": 10}},
                            ]
                        },
                        "assetProfile": {"industry": "Medical Instruments", "sector": "Healthcare"},
                        "price": {"longName": "Bruker Corporation", "marketCap": {"raw": 1000}},
                    }
                ]
            }
        }

    monkeypatch.setattr(provider, "_get_json", fake_get_json)

    fundamentals = provider.fundamentals("BRKR")
    profile = provider.profile("BRKR")

    assert fundamentals["income_statement"]["annualReports"][0]["totalRevenue"] == 200
    assert fundamentals["income_statement"]["annualReports"][1]["netIncome"] == 10
    assert profile["industry"] == "Medical Instruments"
    assert profile["market_cap"] == 1000


def test_sec_company_facts_maps_net_income_revenue_and_shares(monkeypatch, tmp_path):
    provider = SecCompanyFactsProvider({}, SqliteCache(tmp_path / "market-cache.sqlite3", ttl_hours=24, max_mb=1))

    monkeypatch.setattr(provider, "_ticker_row", lambda symbol: {"cik": "0000000001", "title": "Example Corp"})
    monkeypatch.setattr(
        provider,
        "_company_facts",
        lambda cik: {
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [
                                {"fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01", "end": "2024-12-31", "val": 1000},
                                {"fy": 2025, "fp": "FY", "form": "10-K", "filed": "2026-02-01", "end": "2025-12-31", "val": 1200},
                            ]
                        }
                    },
                    "NetIncomeLoss": {
                        "units": {
                            "USD": [
                                {"fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01", "end": "2024-12-31", "val": 100},
                                {"fy": 2025, "fp": "FY", "form": "10-K", "filed": "2026-02-01", "end": "2025-12-31", "val": 180},
                            ]
                        }
                    },
                },
                "dei": {
                    "EntityCommonStockSharesOutstanding": {
                        "units": {
                            "shares": [
                                {"filed": "2026-02-01", "end": "2025-12-31", "val": 50000000}
                            ]
                        }
                    }
                },
            }
        },
    )

    fundamentals = provider.fundamentals("EXM")
    profile = provider.profile("EXM")

    assert fundamentals["income_statement"]["annualReports"][-1]["netIncome"] == 180
    assert fundamentals["income_statement"]["annualReports"][-1]["totalRevenue"] == 1200
    assert profile["shares_outstanding"] == 50000000


def test_sec_company_facts_as_of_uses_filing_available_at_historical_cutoff(monkeypatch, tmp_path):
    provider = SecCompanyFactsProvider({}, SqliteCache(tmp_path / "cache.sqlite3", ttl_hours=24))
    monkeypatch.setattr(provider, "_ticker_row", lambda symbol: {"ticker": symbol, "cik": "0000000001", "title": "Example"})
    monkeypatch.setattr(
        provider,
        "_company_facts",
        lambda cik: {
            "facts": {
                "us-gaap": {
                    "Revenues": {"units": {"USD": [
                        {"fy": 2023, "fp": "FY", "form": "10-K", "filed": "2023-09-01", "end": "2023-07-29", "val": 100},
                        {"fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-09-01", "end": "2023-07-29", "val": 101},
                        {"fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-09-01", "end": "2024-07-27", "val": 120},
                    ]}},
                    "NetIncomeLoss": {"units": {"USD": [
                        {"fy": 2023, "fp": "FY", "form": "10-K", "filed": "2023-09-01", "end": "2023-07-29", "val": 10},
                        {"fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-09-01", "end": "2024-07-27", "val": 12},
                    ]}},
                },
                "dei": {},
            }
        },
    )

    reports = provider.fundamentals_as_of("EXM", date(2024, 8, 5))["income_statement"]["annualReports"]

    assert reports == [{"fiscalDateEnding": "2023-07-29", "totalRevenue": 100.0, "filingDate": "2023-09-01", "netIncome": 10.0}]
