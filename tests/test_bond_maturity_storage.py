"""Storage compatibility for optional, instrument-wide bond maturity metadata."""
import sqlite3

import pytest

from app.local_portfolio import LocalPortfolioStore
from test_local_portfolio import _save_owned_account


def setup_bond(store):
    owner = _save_owned_account(store, {"type": "Investment", "account_id": "maturity", "location": "USA", "currency": "USD"})
    security = store.save_manual_security({"symbol": "BONDQA", "stock_market": "MANUAL", "instrument_type": "BOND", "maturity_date": "02/11/2026"})
    trade = store.add_transaction({"account_db_id": owner["id"], "security_id": security["id"], "action": "BUY", "quantity": 8000, "price_input": 98, "trade_date": "01/01/2026"})
    return owner, security, trade


def test_maturity_schema_is_additive_and_older_backup_still_imports(tmp_path):
    store = LocalPortfolioStore(tmp_path / "source.sqlite")
    setup_bond(store)
    backup = store.export_data()
    backup["data"].pop("bond_maturity_dates")
    restored = LocalPortfolioStore(tmp_path / "restore.sqlite")
    restored.import_data(backup)
    assert restored.holdings()[0].holding.quantity == 8000
    assert not restored.holdings()[0].holding.maturity_date
    with sqlite3.connect(restored.path) as conn:
        conn.execute("drop table bond_maturity_dates")
    migrated = LocalPortfolioStore(restored.path)
    assert migrated.list_transactions()[0]["maturity_date"] is None
    assert migrated.holdings()[0].holding.quantity == 8000


def test_failed_sale_never_changes_shared_maturity_or_cash(tmp_path):
    store = LocalPortfolioStore(tmp_path / "source.sqlite")
    owner, security, trade = setup_bond(store)
    before = store.export_data()["data"]
    with pytest.raises(ValueError):
        store.add_transaction({"account_db_id": owner["id"], "security_id": security["id"], "action": "SELL", "quantity": 8001, "price_input": 100, "trade_date": "02/11/2026", "maturity_date": "01/01/2099"})
    assert store.export_data()["data"] == before
