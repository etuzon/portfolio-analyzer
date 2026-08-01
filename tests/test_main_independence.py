import io
import zipfile
from datetime import date, timedelta

from app import main
from app.models import Ohlcv
from fastapi import HTTPException


class _LocalStore:
    def __init__(self):
        self.imported = False

    def holdings(self):
        return []

    def import_ghostfolio(self, holdings, account_cash=None, source_transactions=None):
        self.imported = True
        self.account_cash = account_cash or []
        self.source_transactions = source_transactions or []
        return {"accounts": 1, "positions": len(holdings), "updated_positions": 0, "attached_positions": len(holdings)}

    def capture_daily_snapshots(self):
        self.snapshots_captured = True


def test_portfolio_reads_local_store_without_ghostfolio_sync(monkeypatch):
    class GhostfolioShouldNotLoad:
        def __init__(self, db_config):
            pass

        def load_holdings(self):
            raise AssertionError("portfolio should not sync Ghostfolio")

    monkeypatch.setattr(main, "GhostfolioClient", GhostfolioShouldNotLoad)
    monkeypatch.setattr(main, "local_store", _LocalStore())

    result = main.portfolio()

    assert result["status"]["local_portfolio"] == "ok (0 local positions)"
    assert result["items"] == []


def test_ghostfolio_import_is_explicit(monkeypatch):
    class GhostfolioSource:
        def __init__(self, db_config):
            pass

        def load_holdings(self):
            return [object()], {"ghostfolio": "ok (1 positions)"}

        def load_account_cash(self):
            return [{"account": "Main", "currency": "USD", "cash": 123}], {"ghostfolio_accounts": "ok (1 accounts)"}

        def load_order_transactions(self):
            return [{"account": "Main", "account_currency": "USD", "symbol": "ABC", "quantity": 1}], {"source_orders": "ok (1 transactions)"}

    store = _LocalStore()
    monkeypatch.setattr(main, "GhostfolioClient", GhostfolioSource)
    monkeypatch.setattr(main, "local_store", store)

    result = main.import_ghostfolio()

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


def test_security_history_clamps_requested_start_date(monkeypatch):
    class Store:
        def price_history(self, symbol, stock_market, from_date, to_date):
            self.from_date = from_date
            self.to_date = to_date
            return []

        def manual_security_exists(self, symbol, stock_market):
            return False

    class Hub:
        def prices(self, symbol, from_date, to_date):
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
        def prices(self, symbol, from_date, to_date):
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
