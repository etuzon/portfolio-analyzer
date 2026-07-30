from app import main


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
