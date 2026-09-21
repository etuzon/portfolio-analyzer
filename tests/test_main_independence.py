import io
import hashlib
import json
import sqlite3
import zipfile
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app import main
from app.config import AppConfig
from app.models import Ohlcv
from app.providers import SqliteCache
from fastapi import HTTPException
from fastapi.testclient import TestClient


def test_external_db_config_accepts_a_structurally_valid_legacy_section(tmp_path):
    expected = {"host": "source-db", "database": "portfolio", "username": "reader"}
    config = AppConfig(raw={"legacy_source": {"db": expected}}, path=tmp_path / "config.yaml")

    assert config.db == expected


def test_delete_account_returns_conflict_when_data_is_attached(monkeypatch):
    class Store:
        def delete_account(self, account_id):
            raise ValueError("Account has attached data and cannot be removed: funds=1")

    monkeypatch.setattr(main, "local_store", Store())

    with pytest.raises(HTTPException) as exc_info:
        main.delete_local_account("account-1")

    assert exc_info.value.status_code == 409
    assert "funds=1" in exc_info.value.detail


def test_manual_security_api_rejects_currencies_outside_ils_usd_eur(monkeypatch):
    class Store:
        def save_manual_security(self, payload):
            raise AssertionError("Unsupported currency must be rejected before storage")

    monkeypatch.setattr(main, "local_store", Store())

    with pytest.raises(HTTPException) as exc_info:
        main.save_manual_security({"symbol": "GBP-ASSET", "currency": "GBP"})

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Security currency must be ILS, USD, or EUR"


def test_manual_security_api_rejects_rsu_as_an_instrument_type(monkeypatch):
    class Store:
        def save_manual_security(self, payload):
            raise AssertionError("RSU instrument types must be rejected before storage")

    monkeypatch.setattr(main, "local_store", Store())

    with pytest.raises(HTTPException) as exc_info:
        main.save_manual_security({"symbol": "AAPL", "currency": "USD", "instrument_type": "RSU"})

    assert exc_info.value.status_code == 400
    assert "grant type" in exc_info.value.detail
    assert "transaction as RSU" in exc_info.value.detail


def test_rsu_is_available_for_transactions_but_not_instrument_definitions():
    options = main.local_options()

    assert "RSU" in options["asset_classes"]
    assert "RSU" not in options["instrument_types"]


def test_industry_override_api_uses_supported_catalog_and_clears_cache(monkeypatch):
    class Store:
        def __init__(self):
            self.saved = None

        def list_security_industry_overrides(self):
            return [{"symbol": "MSFT", "stock_market": "NASDAQ", "industry": "Software"}]

        def save_security_industry_override(self, payload):
            self.saved = payload
            return payload

        def delete_security_industry_override(self, symbol, stock_market):
            return symbol == "MSFT" and stock_market == "NASDAQ"

    store = Store()
    cache_clears = []
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "clear_portfolio_cache", lambda: cache_clears.append(True))

    listed = main.list_security_industry_overrides()
    saved = main.save_security_industry_override(
        {"symbol": "MSFT", "stock_market": "NASDAQ", "industry": "Software"}
    )
    deleted = main.delete_security_industry_override("MSFT", "NASDAQ")

    assert "Banks" in listed["industries"]
    assert "Bonds" not in listed["industries"]
    assert saved["industry"] == "Software"
    assert deleted == {"deleted": True}
    assert len(cache_clears) == 2
    with pytest.raises(HTTPException) as exc_info:
        main.save_security_industry_override(
            {"symbol": "MSFT", "stock_market": "NASDAQ", "industry": "Made Up"}
        )
    assert exc_info.value.status_code == 400


def test_portfolio_industry_overrides_and_keeps_bonds_out_of_industries(monkeypatch):
    class Store:
        def list_security_industry_overrides(self):
            return [{"symbol": "MSFT", "stock_market": "NASDAQ", "industry": "Software"}]

    rows = {
        "stock": {
            "holding": {"symbol": "MSFT", "stock_market": "NASDAQ", "asset_class": "EQUITY", "industry": "EDP Services", "sector": "Technology"},
            "industry": "EDP Services",
        },
        "bank": {
            "holding": {"symbol": "BANK", "stock_market": "NYSE", "asset_class": "EQUITY", "industry": "Major Banks", "sector": "Financial Services"},
            "industry": "Major Banks",
        },
        "bond": {
            "holding": {"symbol": "IL001", "stock_market": "TASE", "asset_class": "BOND", "industry": "Financial Services", "sector": "Financial Services"},
            "industry": "Financial Services",
        },
    }
    monkeypatch.setattr(main, "local_store", Store())
    monkeypatch.setattr(main, "enriched_local_holdings", lambda: list(rows))
    monkeypatch.setattr(main, "to_dict", lambda key: rows[key])
    monkeypatch.setattr(main, "_portfolio_cache", None)

    items = main.portfolio_payload()["items"]

    assert items[0]["industry"] == "Software"
    assert items[0]["industry_source"] == "manual"
    assert items[0]["provider_industry"] == "EDP Services"
    assert items[1]["industry"] == "Banks"
    assert items[1]["industry_source"] == "provider"
    assert items[2]["industry"] == "Bonds"
    assert items[2]["industry_source"] == "asset_class"


class _LocalStore:
    def __init__(self):
        self.imported = False

    def holdings(self):
        return []

    def import_external(self, holdings, account_cash=None, source_transactions=None):
        self.imported = True
        self.account_cash = account_cash or []
        self.source_transactions = source_transactions or []
        return {"accounts": 1, "positions": len(holdings), "updated_positions": 0, "attached_positions": len(holdings)}

    def capture_daily_snapshots(self):
        self.snapshots_captured = True


def test_portfolio_reads_local_store_without_external_sync(monkeypatch, tmp_path):
    class ExternalSourceShouldNotLoad:
        def __init__(self, db_config):
            pass

        def load_holdings(self):
            raise AssertionError("portfolio should not sync the external source")

    monkeypatch.setattr(main, "ExternalImportClient", ExternalSourceShouldNotLoad)
    monkeypatch.setattr(main, "local_store", _LocalStore())
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    result = main.portfolio()

    assert result["status"]["local_portfolio"] == "ok (0 local positions)"
    assert result["items"] == []


def test_external_import_is_explicit(monkeypatch):
    class ExternalSource:
        def __init__(self, db_config):
            pass

        def load_holdings(self):
            return [object()], {"external_import": "ok (1 positions)"}

        def load_account_cash(self):
            return [{"account": "Main", "currency": "USD", "cash": 123}], {"source_accounts": "ok (1 accounts)"}

        def load_order_transactions(self):
            return [{"account": "Main", "account_currency": "USD", "symbol": "ABC", "quantity": 1}], {"source_orders": "ok (1 transactions)"}

    store = _LocalStore()
    monkeypatch.setattr(main, "ExternalImportClient", ExternalSource)
    monkeypatch.setattr(main, "local_store", store)

    result = main.import_source()

    assert store.imported is True
    assert store.account_cash == [{"account": "Main", "currency": "USD", "cash": 123}]
    assert store.source_transactions == [{"account": "Main", "account_currency": "USD", "symbol": "ABC", "quantity": 1}]
    assert store.snapshots_captured is True
    assert result["positions"] == 1
    assert result["source"] == "ok (1 positions)"


def test_account_trends_clamp_requested_start_date(monkeypatch):
    class Store:
        def account_trends(self, filters):
            self.filters = filters
            return {"filters": filters}

    store = Store()
    monkeypatch.setattr(main, "local_store", store)

    result = main.local_account_trends(date_from="2025-07-30", date_to="2026-07-30")

    assert result["filters"]["from"] == "2026-04-14"
    assert store.filters["from"] == "2026-04-14"


def test_portfolio_report_pdf_uses_the_same_scope_and_period(monkeypatch):
    class Store:
        def reports(self, filters):
            self.report_filters = filters
            return {"accounts": 0, "holdings": 0, "funds": {"count": 0}, "account_details": [], "scope": filters}

        def account_trends(self, filters):
            self.trend_filters = filters
            return {"accounts": []}

    store = Store()
    captured = {}

    def build_pdf(report, trend, **options):
        captured.update({"report": report, "trend": trend, **options})
        return b"%PDF-1.7\nreport"

    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "build_portfolio_report_pdf", build_pdf)

    response = main.local_reports_pdf(
        account_type="Long-Term Savings",
        person_id="person-1",
        person_name="Dana Levi",
        date_from="01/08/2026",
        date_to="22/08/2026",
        language="he",
    )

    assert store.report_filters["account_type"] == "Long-Term Savings"
    assert store.report_filters["person_id"] == "person-1"
    assert store.trend_filters["from"] == "2026-08-01"
    assert store.trend_filters["to"] == "2026-08-22"
    assert captured["language"] == "he"
    assert response.media_type == "application/pdf"
    assert response.body.startswith(b"%PDF")
    assert "portfolio-report-" in response.headers["content-disposition"]


def test_security_history_clamps_requested_start_date(monkeypatch):
    class Store:
        def price_history(self, symbol, stock_market, from_date, to_date):
            self.from_date = from_date
            self.to_date = to_date
            return []

        def manual_security_exists(self, symbol, stock_market):
            return False

    class Hub:
        def prices(self, symbol, from_date, to_date, **kwargs):
            self.from_date = from_date
            return [], {"provider": "empty"}

    store = Store()
    hub = Hub()
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "hub", lambda: hub)

    result = main.security_history("TRIN", "YAHOO", date_from="2025-07-30")

    assert store.from_date == main.HISTORY_START_DATE
    assert hub.from_date == main.HISTORY_START_DATE
    assert result["points"] == []


def test_security_history_returns_ohlcv_and_chart_metrics(monkeypatch):
    class Store:
        def price_history(self, symbol, stock_market, from_date, to_date):
            return []

        def manual_security_exists(self, symbol, stock_market):
            return False

    class Hub:
        def prices(self, symbol, from_date, to_date, **kwargs):
            start = date.today() - timedelta(days=39)
            rows = [
                Ohlcv(
                    date=start + timedelta(days=index),
                    open=100 + index,
                    high=103 + index,
                    low=98 + index,
                    close=101 + index,
                    adjusted_close=101 + index,
                    volume=1000 + index * 10,
                )
                for index in range(40)
            ]
            return rows, {"provider": "test"}

    monkeypatch.setattr(main, "local_store", Store())
    monkeypatch.setattr(main, "hub", lambda: Hub())

    result = main.security_history("CSCO", "NASDAQ", period="1m")

    assert result["has_candles"] is True
    assert result["has_volume"] is True
    assert result["points"][0].keys() >= {"open", "high", "low", "close", "adjusted_close", "volume", "price"}
    assert result["moving_averages"]["30"]["state"] == "ok"
    assert result["support_resistance"]["1m"]["state"] == "ok"
    assert result["volume"]["average_20d"] is not None
    assert result["technical_signals"]["confirmed_breakout"]["state"] == "ok"
    assert result["technical_signals"]["confirmed_breakout"]["score_total"] == 4


def test_security_signal_uses_analysis_history_when_visible_chart_is_short():
    start = date.today() - timedelta(days=39)
    analysis_prices = [
        Ohlcv(
            date=start + timedelta(days=index),
            open=100 + index,
            high=102 + index,
            low=99 + index,
            close=101 + index,
            adjusted_close=101 + index,
            volume=1000 + index * 10,
        )
        for index in range(40)
    ]

    result = main._security_history_response(
        "CSCO",
        "NASDAQ",
        "1m",
        "test",
        analysis_prices[-10:],
        analysis_prices,
    )

    assert result["moving_averages"]["30"]["state"] == "missing"
    assert result["technical_signals"]["confirmed_breakout"]["state"] == "ok"


def test_security_history_passes_primary_secondary_and_tase_market_to_provider(monkeypatch):
    class Store:
        def price_history(self, symbol, stock_market, from_date, to_date):
            return []

        def manual_security(self, symbol, stock_market):
            return {
                "symbol": "1101534",
                "secondary_symbol": "CEL",
                "stock_market": "TASE",
            }

    class Hub:
        def prices(self, symbol, from_date, to_date, **kwargs):
            self.call = (symbol, kwargs)
            return [
                Ohlcv(
                    date=to_date,
                    open=32,
                    high=33,
                    low=31,
                    close=32.47,
                    adjusted_close=32.47,
                    volume=100,
                )
            ], {"yahoo_finance": "ok"}

    hub = Hub()
    monkeypatch.setattr(main, "local_store", Store())
    monkeypatch.setattr(main, "hub", lambda: hub)

    result = main.security_history("1101534", "TASE", period="1m")

    assert hub.call == ("1101534", {"secondary_symbol": "CEL", "stock_market": "TASE"})
    assert result["points"][-1]["price"] == 32.47
    assert result["status"] == {"yahoo_finance": "ok"}


def test_us_transaction_validation_accepts_sec_ticker_without_quote(monkeypatch):
    class Store:
        def manual_security_exists(self, symbol, stock_market):
            return False

        def add_transaction(self, payload):
            self.payload = payload
            return payload

    class Hub:
        def quote(self, symbol):
            return {}, {"quote": "missing"}

        def market_screener(self, criteria):
            return [{"symbol": "CSCO", "name": "CISCO SYSTEMS, INC.", "exchange": "SEC"}], {"sec_company_tickers": "ok"}

    store = Store()
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "hub", lambda: Hub())

    result = main.add_local_security(
        {
            "account_db_id": "account-1",
            "action": "ADD",
            "symbol": "CSCO",
            "stock_market": "NASDAQ",
            "asset_class": "RSU",
            "quantity": 1,
            "price_input": 0,
            "trade_date": "31/07/2026",
        }
    )

    assert result["stock_market"] == "NASDAQ"
    assert store.payload["stock_market"] == "NASDAQ"


def test_transaction_validation_accepts_existing_manual_market(monkeypatch):
    class Store:
        def manual_security_exists(self, symbol, stock_market):
            return symbol == "5136924" and stock_market == "MANUAL"

        def add_transaction(self, payload):
            self.payload = payload
            return payload

    store = Store()
    monkeypatch.setattr(main, "local_store", store)

    result = main.add_local_security(
        {
            "account_db_id": "account-1",
            "action": "SELL",
            "symbol": "5136924",
            "stock_market": "MANUAL",
            "asset_class": "MUTUALFUND",
            "quantity": 1,
            "price_input": 91.09,
            "trade_date": "06/08/2026",
        }
    )

    assert result["stock_market"] == "MANUAL"
    assert store.payload["stock_market"] == "MANUAL"


def test_transaction_validation_rejects_provider_as_stock_market(monkeypatch):
    class Store:
        def manual_security_exists(self, symbol, stock_market):
            return False

    monkeypatch.setattr(main, "local_store", Store())

    try:
        main.add_local_security({"symbol": "CSCO", "stock_market": "YAHOO", "quantity": 1})
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "Unsupported stock market" in str(exc.detail)
    else:
        raise AssertionError("Provider names should not be accepted as stock markets")


def test_finance_report_normalizes_online_fundamentals(monkeypatch):
    class Hub:
        def fundamentals(self, symbol):
            assert symbol == "CSCO"
            return {
                "profile": {"name": "Cisco Systems"},
                "income_statement": {
                    "annualReports": [
                        {"fiscalDateEnding": "2025-07-31", "totalRevenue": "1000", "netIncome": "100"},
                        {"fiscalDateEnding": "2026-07-31", "totalRevenue": "1250", "netIncome": "150"},
                    ]
                },
            }, {"sec_company_facts": "ok"}

    monkeypatch.setattr(main, "hub", lambda: Hub())

    result = main.finance_report("csco")

    assert result["symbol"] == "CSCO"
    assert result["profile"]["name"] == "Cisco Systems"
    assert result["provider_status"] == {"sec_company_facts": "ok"}
    assert result["reports"][0]["fiscal_date"] == "2026-07-31"
    assert result["reports"][0]["revenue_growth_percent"] == 25
    assert result["reports"][0]["net_income_growth_percent"] == 50
    assert result["reports"][0]["net_margin_percent"] == 12
    assert result["summary"]["years"] == 2


def test_finance_report_backtest_cutoff_uses_filing_date(monkeypatch):
    class Hub:
        def fundamentals(self, symbol):
            return {
                "income_statement": {
                    "annualReports": [
                        {"fiscalDateEnding": "2023-12-31", "filingDate": "2024-02-01", "totalRevenue": 100, "netIncome": 10},
                        {"fiscalDateEnding": "2024-12-31", "filingDate": "2025-02-01", "totalRevenue": 120, "netIncome": 15},
                    ]
                }
            }, {"test_reports": "ok"}

    monkeypatch.setattr(main, "hub", lambda: Hub())

    result = main._finance_report_payload("ACME", as_of_date="2024-08-05")

    assert len(result["reports"]) == 1
    assert result["latest"]["fiscal_date"] == "2023-12-31"
    assert result["latest"]["filing_date"] == "2024-02-01"


def test_finance_report_normalizes_income_cash_flow_and_balance_sheet_metrics(monkeypatch):
    class Hub:
        def fundamentals(self, symbol):
            return {
                "income_statement": {
                    "annualReports": [
                        {
                            "fiscalDateEnding": "2024-12-31",
                            "totalRevenue": 100,
                            "grossProfit": 60,
                            "operatingIncome": 20,
                            "netIncome": 10,
                            "operatingCashFlow": 25,
                            "capitalExpenditures": -5,
                            "totalCurrentAssets": 80,
                            "totalCurrentLiabilities": 40,
                            "netReceivables": 15,
                            "inventory": 10,
                        }
                    ]
                }
            }, {"test_reports": "ok"}

    monkeypatch.setattr(main, "hub", lambda: Hub())

    report = main._finance_report_payload("ACME")
    latest = report["latest"]

    assert latest["gross_margin_percent"] == 60
    assert latest["operating_margin_percent"] == 20
    assert latest["free_cash_flow"] == 20
    assert latest["cash_conversion_percent"] == 200
    assert latest["current_ratio"] == 2
    assert latest["accounts_receivable"] == 15


def test_company_outlook_batch_runs_at_most_ten_companies_and_returns_review(tmp_path, monkeypatch):
    calls = []

    def backtest(symbol, request):
        calls.append((symbol, request))
        return {
            "analysis": {"prediction_record": {"id": symbol}},
            "evaluation": {"id": symbol, "direction": "positive", "actual_direction": "positive", "accuracy_score": 100},
        }

    monkeypatch.setattr(main, "_company_outlook_backtest", backtest)
    from app.local_portfolio import LocalPortfolioStore

    monkeypatch.setattr(main, "local_store", LocalPortfolioStore(tmp_path / "local.sqlite3"))

    result = main._company_outlook_backtest_batch(
        {
            "as_of_date": "2024-08-05",
            "horizon_months": 24,
            "phase": "holdout",
            "batch_number": 3,
            "companies": [
                {"symbol": "ACME", "industry": "Networking", "peers": ["PEER1", "PEER2"]},
                {"symbol": "PEER1", "industry": "Networking", "peers": ["ACME", "PEER2"]},
            ],
        }
    )

    assert len(calls) == 2
    assert calls[0][1]["batch"]["phase"] == "holdout"
    assert calls[0][1]["industry"] == "Networking"
    assert result["review"]["accuracy_percent"] == 100
    assert result["review"]["calibration_notice"].startswith("This is an untouched holdout")

    with pytest.raises(ValueError, match="at most 10"):
        main._company_outlook_backtest_batch(
            {
                "as_of_date": "2024-08-05",
                "companies": [{"symbol": f"S{i}", "peers": ["P1", "P2"]} for i in range(11)],
            }
        )


def test_company_outlook_compares_peer_reports_saves_prediction_and_has_no_feedback_loops(tmp_path, monkeypatch):
    reports = {
        "ACME": {
            "profile": {"name": "Acme Networks", "industry": "Networking"},
            "income_statement": {
                "annualReports": [
                    {"fiscalDateEnding": "2024-12-31", "totalRevenue": 100, "netIncome": 10},
                    {"fiscalDateEnding": "2025-12-31", "totalRevenue": 120, "netIncome": 15},
                    {"fiscalDateEnding": "2026-12-31", "totalRevenue": 150, "netIncome": 24},
                ]
            },
        },
        "PEER1": {
            "profile": {"name": "Peer One", "industry": "Networking"},
            "income_statement": {
                "annualReports": [
                    {"fiscalDateEnding": "2024-12-31", "totalRevenue": 100, "netIncome": 12},
                    {"fiscalDateEnding": "2025-12-31", "totalRevenue": 110, "netIncome": 14},
                    {"fiscalDateEnding": "2026-12-31", "totalRevenue": 121, "netIncome": 15},
                ]
            },
        },
        "PEER2": {
            "profile": {"name": "Peer Two", "industry": "Networking"},
            "income_statement": {
                "annualReports": [
                    {"fiscalDateEnding": "2024-12-31", "totalRevenue": 100, "netIncome": 10},
                    {"fiscalDateEnding": "2025-12-31", "totalRevenue": 105, "netIncome": 10},
                    {"fiscalDateEnding": "2026-12-31", "totalRevenue": 110, "netIncome": 11},
                ]
            },
        },
    }

    class Hub:
        def fundamentals(self, symbol):
            return reports[symbol], {"test_reports": "ok"}

        def market_screener(self, criteria):
            assert criteria["industry"] == "Networking"
            return [{"symbol": "PEER1"}, {"symbol": "PEER2"}], {"test_screener": "ok"}

    from app.local_portfolio import LocalPortfolioStore

    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    monkeypatch.setattr(main, "hub", lambda: Hub())
    monkeypatch.setattr(main, "local_store", store)

    result = main.company_outlook("acme", {"save_prediction": True, "horizon_months": 12})

    assert result["symbol"] == "ACME"
    assert result["industry"]["name"] == "Networking"
    assert result["industry"]["peer_count"] == 2
    assert result["rank"] == 1
    assert result["prediction_record"]["status"] == "pending"
    assert result["graph"]["feedback_loops"] == 0
    assert result["mermaid"].startswith("flowchart LR")
    assert len(store.list_company_report_predictions("ACME")) == 1


def test_market_screener_filters_latest_annual_profit_and_yields(monkeypatch):
    reports = {
        "GOOD": {
            "profile": {"name": "Good Company", "sector": "Technology", "industry": "Hardware", "currency": "USD"},
            "income_statement": {
                "annualReports": [
                    {"fiscalDateEnding": "2024-12-31", "totalRevenue": 800_000_000, "netIncome": 80_000_000},
                    {"fiscalDateEnding": "2025-12-31", "totalRevenue": 1_000_000_000, "netIncome": 120_000_000, "operatingCashFlow": 170_000_000, "capitalExpenditures": 20_000_000},
                ]
            },
        },
        "WEAK": {
            "profile": {"name": "Weak Company", "sector": "Technology", "industry": "Hardware", "currency": "USD"},
            "income_statement": {
                "annualReports": [
                    {"fiscalDateEnding": "2024-12-31", "totalRevenue": 500_000_000, "netIncome": 20_000_000},
                    {"fiscalDateEnding": "2025-12-31", "totalRevenue": 510_000_000, "netIncome": 10_000_000},
                ]
            },
        },
    }

    class Hub:
        def market_screener(self, criteria):
            assert criteria["limit"] == 75
            return [
                {"symbol": "GOOD", "price": 100, "market_cap": 1_000_000_000, "dividend": 2, "currency": "USD"},
                {"symbol": "WEAK", "price": 50, "market_cap": 500_000_000, "dividend": 0.25, "currency": "USD"},
            ], {"test_screener": "ok"}

        def fundamentals(self, symbol):
            return reports[symbol], {"test_reports": "ok"}

        def quote(self, symbol):
            return {}, {"test_quote": "missing"}

        def dividends(self, symbol):
            return [], {"test_dividends": "missing"}

    monkeypatch.setattr(main, "hub", lambda: Hub())

    result = main.market_screener(
        {
            "limit": 25,
            "annualNetIncomeMoreThan": 100_000_000,
            "profitMarketCapMoreThan": 10,
            "dividendYieldMoreThan": 1.5,
            "revenueGrowthMoreThan": 20,
            "sortBy": "annual_profit:desc",
        }
    )

    assert result["count"] == 1
    assert result["items"][0]["symbol"] == "GOOD"
    assert result["items"][0]["fiscal_year"] == 2025
    assert result["items"][0]["annual_net_income"] == 120_000_000
    assert result["items"][0]["dividend_yield_percent"] == 2
    assert result["items"][0]["profit_market_cap_percent"] == 12
    assert result["items"][0]["revenue_growth_percent"] == 25
    assert result["meta"]["financial_rows"] == 2


def test_market_screener_missing_financial_filter_is_explicit(monkeypatch):
    class Hub:
        def market_screener(self, criteria):
            return [{"symbol": "UNKNOWN", "price": 10, "market_cap": 100_000_000}], {"test_screener": "ok"}

        def fundamentals(self, symbol):
            return {}, {"test_reports": "missing"}

        def quote(self, symbol):
            return {}, {"test_quote": "missing"}

        def dividends(self, symbol):
            return [], {"test_dividends": "missing"}

    monkeypatch.setattr(main, "hub", lambda: Hub())

    excluded = main.market_screener({"annualNetIncomeMoreThan": 0})
    included = main.market_screener({"annualNetIncomeMoreThan": 0, "includeMissing": True})

    assert excluded["count"] == 0
    assert included["count"] == 1
    assert included["meta"]["missing_financial_rows"] == 1


def test_backup_archive_contains_all_backup_files(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    first = backup_dir / "portfolio-data-20260801-010000.json"
    second = backup_dir / "portfolio-data-20260801-020000.json"
    first.write_text('{"name": "first"}')
    second.write_text('{"name": "second"}')

    class Store:
        def backup_dir(self):
            return backup_dir

        def list_backups(self):
            return [
                {"filename": second.name},
                {"filename": first.name},
            ]

    monkeypatch.setattr(main, "local_store", Store())

    response = main.backup_archive_response()
    archive = zipfile.ZipFile(io.BytesIO(response.body))

    assert response.media_type == "application/zip"
    assert archive.namelist() == [second.name, first.name]


def test_full_backup_contains_all_persistent_application_state(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    data_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("dashboard:\n  base_currency: ILS\nprovider_secret: test-only\n")
    cert_root = tmp_path / "certs"
    cert_root.mkdir()
    (cert_root / "server.crt").write_text("certificate")
    (cert_root / "server.key").write_text("private-key")
    (data_root / "settings.json").write_text('{"backup": {"enabled": true}}')
    (data_root / "alerts.json").write_text('[{"name": "Saved rule"}]')
    (data_root / "market-cache.json").write_text('{"cached": true}')
    market_cache = SqliteCache(data_root / "market-cache.sqlite3", ttl_hours=24)
    market_cache.set_security_snapshot("provider", "FDUS", "profile", {"sector": "Financial Services"})
    legacy_dir = data_root / "backups"
    legacy_dir.mkdir()
    (legacy_dir / "portfolio-data-old.json").write_text('{"old": true}')

    monkeypatch.setenv("DATA_DIR", str(data_root))
    store = main.LocalPortfolioStore(data_root / "local-portfolio.sqlite3")
    store.set_preference(
        "client_state",
        {
            "dashboard": {"mode": "expanded"},
            "pensionSimulation": {"scenarios": [{"name": "Full retirement plan"}]},
        },
    )
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "config", SimpleNamespace(path=config_path))

    result = main.write_full_backup(keep=5)
    archive_path = data_root / "backups" / result["filename"]
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        portable_data = json.loads(archive.read("portfolio-data.json"))
        sqlite_snapshot = archive.read("data/local-portfolio.sqlite3")
        market_cache_snapshot = archive.read("data/market-cache.sqlite3")

    assert result["type"] == "full"
    assert result["sensitive"] is True
    assert result["filename"].startswith("portfolio-full-")
    assert result["filename"].endswith(".zip")
    assert {
        "manifest.json",
        "RESTORE.md",
        "portfolio-data.json",
        "config.yaml",
        "data/local-portfolio.sqlite3",
        "data/settings.json",
        "data/alerts.json",
        "data/market-cache.json",
        "data/market-cache.sqlite3",
        "certs/server.crt",
        "certs/server.key",
    }.issubset(names)
    assert not any(name.startswith("data/backups/") for name in names)
    assert manifest["kind"] == main.FULL_BACKUP_KIND
    assert manifest["sensitive"] is True
    assert all(item["sha256"] for item in manifest["files"])
    assert portable_data["data"]["app_preferences"]
    saved_state = json.loads(portable_data["data"]["app_preferences"][0]["value"])
    assert saved_state["pensionSimulation"]["scenarios"][0]["name"] == "Full retirement plan"
    assert sqlite_snapshot.startswith(b"SQLite format 3")
    restored_market_cache = sqlite3.connect(":memory:")
    restored_market_cache.deserialize(market_cache_snapshot)
    assert restored_market_cache.execute(
        "select value from security_snapshot where symbol = 'FDUS' and data_type = 'profile'"
    ).fetchone()
    restored_market_cache.close()
    assert store.list_backups()[0]["type"] == "full"

    inspection = main.inspect_full_backup(archive_path.read_bytes())
    assert inspection["kind"] == main.FULL_BACKUP_KIND
    assert inspection["files"] == len(names)
    assert inspection["contains"] == {
        "portfolio_database": True,
        "portable_data_export": True,
        "client_preferences_and_pension_simulations": True,
        "application_config": True,
        "runtime_data_and_caches": True,
        "tls_certificates": True,
    }


def test_full_backup_inspection_rejects_tampered_payload(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    data_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("dashboard:\n  base_currency: ILS\n")
    monkeypatch.setenv("DATA_DIR", str(data_root))
    store = main.LocalPortfolioStore(data_root / "local-portfolio.sqlite3")
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "config", SimpleNamespace(path=config_path))
    result = main.write_full_backup(keep=5)
    original_path = data_root / "backups" / result["filename"]
    tampered = io.BytesIO()
    with zipfile.ZipFile(original_path) as source, zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            value = source.read(info)
            if info.filename == "portfolio-data.json":
                value = bytes([value[0] ^ 1]) + value[1:]
            target.writestr(info, value)

    with pytest.raises(ValueError, match="integrity validation failed"):
        main.inspect_full_backup(tampered.getvalue())


def test_full_restore_replaces_complete_state_and_creates_safety_backup(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    data_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "dashboard:\n  base_currency: ILS\nalerts:\n  timezone: Asia/Jerusalem\nbackup:\n  enabled: false\n  keep: 10\n"
    )
    cert_root = tmp_path / "certs"
    cert_root.mkdir()
    (cert_root / "server.crt").write_text("original-certificate")
    (cert_root / "server.key").write_text("original-private-key")
    (data_root / "settings.json").write_text('{"backup": {"enabled": false, "keep": 10}}')
    (data_root / "saved-cache.json").write_text('{"state": "from-backup"}')
    monkeypatch.setenv("DATA_DIR", str(data_root))
    monkeypatch.setenv("CONFIG_PATH", str(config_path))
    monkeypatch.setattr(main, "config", main.load_config())
    store = main.LocalPortfolioStore(data_root / "local-portfolio.sqlite3")
    store.set_preference("client_state", {"marker": "from-backup"})
    auth = main.AuthStore(store.path)
    auth.initialize()
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    result = main.write_full_backup(keep=10)
    archive_path = data_root / "backups" / result["filename"]
    restore_payload = archive_path.read_bytes()

    store.set_preference("client_state", {"marker": "current-state"})
    config_path.write_text("dashboard:\n  base_currency: USD\n")
    (data_root / "saved-cache.json").write_text('{"state": "current"}')
    (data_root / "stale-after-backup.json").write_text('{"remove": true}')
    (cert_root / "server.crt").write_text("current-certificate")

    restored = main.restore_full_backup(restore_payload)

    assert restored["status"] == "restored"
    assert restored["restart_required"] is True
    assert restored["safety_backup"].startswith("portfolio-full-")
    assert restored["safety_backup"] != result["filename"]
    assert store.get_preference("client_state") == {"marker": "from-backup"}
    assert "base_currency: ILS" in config_path.read_text()
    assert (data_root / "saved-cache.json").read_text() == '{"state": "from-backup"}'
    assert not (data_root / "stale-after-backup.json").exists()
    assert (cert_root / "server.crt").read_text() == "original-certificate"
    assert (data_root / "backups" / restored["safety_backup"]).exists()


def test_full_restore_rejects_cross_site_requests():
    cross_site = SimpleNamespace(
        headers={"sec-fetch-site": "cross-site"},
        url=SimpleNamespace(scheme="https", netloc="localhost:6443"),
    )
    with pytest.raises(HTTPException) as exc:
        main._require_same_origin_restore(cross_site)
    assert exc.value.status_code == 403

    wrong_origin = SimpleNamespace(
        headers={"origin": "https://example.invalid"},
        url=SimpleNamespace(scheme="https", netloc="localhost:6443"),
    )
    with pytest.raises(HTTPException) as exc:
        main._require_same_origin_restore(wrong_origin)
    assert exc.value.status_code == 403


def test_full_backup_inspection_rejects_unsafe_paths_and_size_limit(monkeypatch):
    unsafe_value = b"not allowed"
    manifest = {
        "kind": main.FULL_BACKUP_KIND,
        "version": main.FULL_BACKUP_VERSION,
        "app_version": "test",
        "created_at": "2026-08-15T12:00:00Z",
        "files": [{
            "path": "../config.yaml",
            "size_bytes": len(unsafe_value),
            "sha256": hashlib.sha256(unsafe_value).hexdigest(),
        }],
    }
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("../config.yaml", unsafe_value)
    with pytest.raises(ValueError, match="unsafe path"):
        main.inspect_full_backup(archive_bytes.getvalue())

    monkeypatch.setattr(main, "MAX_FULL_BACKUP_COMPRESSED_BYTES", 3)
    with pytest.raises(ValueError, match="larger than"):
        main.inspect_full_backup(b"four")


def test_full_restore_rolls_back_to_safety_backup_on_write_failure(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    data_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("dashboard:\n  base_currency: ILS\nbackup:\n  enabled: false\n  keep: 10\n")
    (data_root / "settings.json").write_text('{"backup": {"enabled": false, "keep": 10}}')
    monkeypatch.setenv("DATA_DIR", str(data_root))
    monkeypatch.setenv("CONFIG_PATH", str(config_path))
    monkeypatch.setattr(main, "config", main.load_config())
    store = main.LocalPortfolioStore(data_root / "local-portfolio.sqlite3")
    auth = main.AuthStore(store.path)
    auth.initialize()
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    store.set_preference("client_state", {"marker": "incoming-backup"})
    incoming_result = main.write_full_backup(keep=10)
    incoming_payload = (data_root / "backups" / incoming_result["filename"]).read_bytes()

    store.set_preference("client_state", {"marker": "state-before-failed-restore"})
    config_path.write_text("dashboard:\n  base_currency: EUR\nbackup:\n  enabled: false\n  keep: 10\n")
    original_apply = main._apply_full_backup_files
    attempts = 0

    def fail_first_apply(files):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            config_path.write_text("dashboard:\n  base_currency: BROKEN\n")
            raise OSError("injected restore failure")
        original_apply(files)

    monkeypatch.setattr(main, "_apply_full_backup_files", fail_first_apply)
    with pytest.raises(RuntimeError, match="recovered from the safety backup"):
        main.restore_full_backup(incoming_payload)

    assert attempts == 2
    assert store.get_preference("client_state") == {"marker": "state-before-failed-restore"}
    assert "base_currency: EUR" in config_path.read_text()
    assert len(store.list_backups()) >= 2


def test_full_restore_api_requires_confirmation_and_rejects_invalid_zip(tmp_path, monkeypatch):
    store = main.LocalPortfolioStore(tmp_path / "local.sqlite3")
    auth = main.AuthStore(store.path)
    auth.initialize()
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    main._login_failures.clear()
    client = TestClient(main.app, base_url="https://localhost:6443")
    signed_in = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    ).json()
    changed = client.post(
        "/api/auth/change-password",
        headers={"X-CSRF-Token": signed_in["csrf_token"]},
        json={
            "current_password": "admin",
            "new_password": "test-admin-password",
            "confirm_password": "test-admin-password",
        },
    ).json()
    csrf_token = changed["csrf_token"]
    response = client.post(
        "/api/local/backups/restore",
        content=b"not-a-zip",
        headers={
            "Origin": "https://localhost:6443",
            "Content-Type": "application/zip",
            "X-CSRF-Token": csrf_token,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Explicit full-restore confirmation is required"

    response = client.post(
        "/api/local/backups/inspect",
        content=b"not-a-zip",
        headers={"Content-Type": "application/zip", "X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "The selected file is not a valid ZIP archive."
