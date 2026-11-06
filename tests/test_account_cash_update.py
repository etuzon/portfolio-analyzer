"""Current-balance corrections use cash ledger entries, never opening balances."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.local_portfolio import CashBalanceError, LocalPortfolioStore, _cash_delta


@pytest.fixture
def book(tmp_path):
    store = LocalPortfolioStore(tmp_path / "cash.sqlite3")
    account = store.save_account({"type": "Investment", "location": "USA", "currency": "USD",
                                  "initial_cash": 1000, "account_id": "cash-test",
                                  "persons": [{"name": "Synthetic Owner", "birth_date": "01/01/1990"}]})
    return store, account


def request(store, account, target, **extra):
    return {"target_cash": target, "cash_revision": store.account_cash_balance(account["id"])["cash_revision"],
            "request_id": str(uuid4()), **extra}


def trade(store, account, **extra):
    return store.add_transaction({"account_db_id": account["id"], "action": "BUY", "symbol": "ABC",
                                  "stock_market": "NYSE", "quantity": 10, "price_input": 20,
                                  "trade_date": "2026-01-01", **extra})


def test_current_cash_correction_preserves_positions_profit_and_history(book):
    store, account = book
    trade(store, account)
    today = store.account_cash_balance(account["id"])["effective_date"]
    yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    store.save_price({"symbol": "ABC", "stock_market": "NYSE", "price_input": 25,
                      "currency": "USD", "location": "USA", "price_date": yesterday})
    store.capture_daily_snapshots(today)
    store.save_account_snapshot({"account_db_id": account["id"], "snapshot_date": yesterday,
                                 "value": 1234, "cash": 987, "source": "manual"})
    before = store.holdings()[0].holding
    assert store.account_cash_balance(account["id"])["cash"] == 800
    result = store.update_account_cash(account["id"], request(store, account, 500))
    assert result["cash"] == 500 and result["delta"] == -300
    tx = next(tx for tx in store.list_transactions() if tx["source"] == "cash_adjustment")
    assert (tx["action"], tx["quantity"], tx["price"]) == ("CASH_OUT", 300, 1)
    assert store.list_accounts()[0]["initial_cash"] == 1000
    after = store.holdings()[0].holding
    assert (after.quantity, after.cost_basis, after.unrealized_profit) == (before.quantity, before.cost_basis, 50)
    assert store.reports()["value"] == 750
    history = {p["snapshot_date"]: p for p in store.list_account_snapshots({"account_id": account["id"]})}
    assert history[yesterday]["value"] == 1234 and history[today]["cash"] == 500
    assert history[today]["value"] == 750 and history[today]["profit"] == 50
    assert len(store.trade_history()["items"]) == 1


@pytest.mark.parametrize("target", [0, -250.5, 1500])
def test_signed_balance_and_replay_are_raw_units_and_idempotent(book, target):
    store, account = book
    payload = request(store, account, target)
    first = store.update_account_cash(account["id"], payload)
    store.update_account_cash(account["id"], request(store, account, 123))
    replay = store.update_account_cash(account["id"], payload)
    assert replay["replayed"] and replay["cash"] == 123
    assert first["delta"] == target - 1000
    assert len(store.list_transactions()) == 2
    with pytest.raises(CashBalanceError, match="request_id_conflict"):
        store.update_account_cash(account["id"], {**payload, "target_cash": 999})


def test_noop_and_revision_conflict(book):
    store, account = book
    payload = request(store, account, 1000)
    assert not store.update_account_cash(account["id"], payload)["adjusted"]
    assert not store.list_transactions()
    trade(store, account)
    with pytest.raises(CashBalanceError, match="cash_revision_conflict"):
        store.update_account_cash(account["id"], payload)


@pytest.mark.parametrize("target", [None, "", True, "nan", "inf", float("-inf"), {}, []])
def test_invalid_targets_are_rejected(book, target):
    store, account = book
    with pytest.raises(CashBalanceError, match="invalid_target_cash"):
        store.update_account_cash(account["id"], request(store, account, target))
    assert not store.list_transactions()


@pytest.mark.parametrize("change,reason", [({"currency": "EUR"}, "mixed_cash_currencies"),
    ({"trade_date": "2099-01-01"}, "future_cash_transactions")])
def test_unprovable_cash_is_unavailable(book, change, reason):
    store, account = book
    trade(store, account, **change)
    context = store.account_cash_balance(account["id"])
    assert not context["available"] and context["cash"] is None and context["reason"] == reason
    with pytest.raises(CashBalanceError, match=reason):
        store.update_account_cash(account["id"], request(store, account, 0))


def test_israeli_cash_not_normalized_and_generated_records_are_readonly(book):
    store, account = book
    account = store.save_account({**account, "currency": "ILS", "location": "Israel"})
    result = store.update_account_cash(account["id"], request(store, account, 500))
    tx = store.list_transactions()[0]
    assert tx["price"] == 1 and tx["quantity"] == 500 and _cash_delta(tx) == -500
    for action in (lambda: store.update_transaction(result["transaction_id"], {"quantity": 1}),
                   lambda: store.delete_transaction(result["transaction_id"]),
                   lambda: store.add_transaction({**tx, "id": str(uuid4())})):
        with pytest.raises(ValueError, match="[Cc]ash"):
            action()
    with pytest.raises(ValueError, match="cannot change currency"):
        store.save_account({**account, "currency": "USD"})


def test_snapshot_refresh_failure_rolls_back_cash_entry(book, monkeypatch):
    store, account = book
    def fail(*args):
        raise RuntimeError("synthetic snapshot failure")
    monkeypatch.setattr(store, "_refresh_transaction_snapshots", fail)
    with pytest.raises(RuntimeError):
        store.update_account_cash(account["id"], request(store, account, 500))
    assert not store.list_transactions()
    assert store.account_cash_balance(account["id"])["cash"] == 1000


def test_competing_current_balance_updates_are_serialized(book):
    store, account = book
    payloads = [request(store, account, target) for target in (500, 700)]
    def save(payload):
        try:
            return store.update_account_cash(account["id"], payload)
        except CashBalanceError as exc:
            return exc.reason
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, payloads))
    assert results.count("cash_revision_conflict") == 1
    assert len(store.list_transactions()) == 1
    assert store.account_cash_balance(account["id"])["cash"] in (500, 700)


def test_import_preserves_locally_adjusted_cash_and_backup_roundtrips(book, tmp_path):
    store, account = book
    store.update_account_cash(account["id"], request(store, account, 500))
    result = store.import_external([], [{"account": "cash-test", "currency": "USD", "cash": 9999}])
    assert result["account_cash_updated"] == 0 and result["account_cash_preserved"] == 1
    assert store.account_cash_balance(account["id"])["cash"] == 500
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    restored.import_data(store.export_data())
    assert restored.account_cash_balance(account["id"])["cash"] == 500
    assert restored.holdings() == [] and restored.trade_history()["items"] == []
