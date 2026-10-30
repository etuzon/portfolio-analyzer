from datetime import date
import json

import pytest

from app.local_portfolio import LocalPortfolioStore
from app.models import Holding
from app.trade_history import build_trade_history


@pytest.fixture
def ledger(tmp_path):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    account = store.save_account({
        "id": "account-a", "account_id": "source-a", "username": "Owner", "type": "Investment",
        "location": "USA", "currency": "USD", "persons": [{"name": "Owner", "birth_date": "01/01/1990"}],
    })
    return store, account


def trade(store, account, action, quantity, price, day, **extra):
    return store.add_transaction({
        "account_db_id": account["id"], "symbol": "ABC", "stock_market": "NYSE", "action": action,
        "quantity": quantity, "price_input": price, "trade_date": day, **extra,
    })


def quote(store, price, day="2026-01-11", **extra):
    return store.save_price({"symbol": "ABC", "stock_market": "NYSE", "price_input": price,
                             "price_date": day, "currency": "USD", "location": "USA", **extra})


def test_full_closure_and_reopening_retains_sold_security(ledger):
    store, account = ledger
    trade(store, account, "BUY", 10, 10, "2026-01-01")
    trade(store, account, "SELL", 10, 15, "2026-01-11")
    first = store.trade_history(as_of_date="2026-01-20")["items"][0]
    assert store.holdings() == []
    assert first["status"] == "closed"
    assert first["duration_days"] == 10
    assert first["realized_profit"] == first["total_profit"] == 50
    assert first["unrealized_profit"] == 0
    assert first["profit_per_day"] == 5
    assert first["profit_per_year"] == 1825
    assert first["valuation_date"] is None
    trade(store, account, "BUY", 2, 20, "2026-01-15")
    rows = store.trade_history(as_of_date="2026-01-20")["items"]
    assert len(rows) == 2
    assert {row["status"] for row in rows} == {"open", "closed"}
    assert len(store.trade_history({"status": "closed"})["items"]) == 1
    assert len(store.trade_history({"status": "open"})["items"]) == 1


def test_average_cost_partial_exits_income_fees_and_calendar_formula(ledger):
    store, account = ledger
    trade(store, account, "BUY", 10, 10, "2026-01-01")
    trade(store, account, "BUY", 10, 20, "2026-01-02")
    trade(store, account, "SELL", 5, 25, "2026-01-03")
    trade(store, account, "DIVIDEND", 1, 8, "2026-01-04")
    trade(store, account, "FEE", 1, 3, "2026-01-04")
    quote(store, 18, "2026-01-09")
    row = store.trade_history(as_of_date="2026-01-11")["items"][0]
    assert row["quantity_remaining"] == 15
    assert row["cost_basis_remaining"] == 225
    assert row["realized_trading_profit"] == 50
    assert row["income"] == 8 and row["fees"] == 3
    assert row["realized_profit"] == 55
    assert row["unrealized_profit"] == 45
    assert row["total_profit"] == 100
    assert row["duration_days"] == 10
    assert row["profit_per_day"] == 10 and row["profit_per_year"] == 3650
    assert row["valuation_date"] == "2026-01-09" and row["valuation_age_days"] == 2
    assert "valuation_before_as_of" in row["issues"]


def test_short_partial_cover_and_close(ledger):
    store, account = ledger
    trade(store, account, "SHORT", 10, 20, "2026-01-01")
    trade(store, account, "SHORT", 10, 30, "2026-01-02")
    trade(store, account, "BUY", 5, 15, "2026-01-03")
    quote(store, 20)
    row = store.trade_history(as_of_date="2026-01-11")["items"][0]
    assert row["side"] == "short" and row["quantity_remaining"] == -15
    assert row["realized_profit"] == 50 and row["unrealized_profit"] == 75
    assert row["total_profit"] == 125
    trade(store, account, "BUY", 15, 20, "2026-01-12")
    row = store.trade_history(as_of_date="2026-01-12")["items"][0]
    assert row["status"] == "closed" and row["total_profit"] == 125


def test_same_day_and_future_transactions_do_not_invent_elapsed_days(ledger):
    store, account = ledger
    trade(store, account, "BUY", 1, 10, "2026-01-01", created_at="2026-01-01T01:00:00")
    trade(store, account, "SELL", 1, 12, "2026-01-01", created_at="2026-01-01T02:00:00")
    trade(store, account, "BUY", 1, 15, "2026-02-01")
    report = store.trade_history(as_of_date=date(2026, 1, 1))
    assert len(report["items"]) == 1
    row = report["items"][0]
    assert row["total_profit"] == 2 and row["duration_days"] == 0
    assert row["profit_per_day"] is row["profit_per_year"] is None


def test_snapshot_import_withholds_synthetic_purchase_date_but_order_import_keeps_dates(ledger):
    store, account = ledger
    holding = Holding(symbol="ABC", name="ABC", asset_class="EQUITY", data_source="LOCAL",
                      stock_market="NYSE", currency="USD", quantity=10, cost_basis=100,
                      market_value=120, account="source-a")
    store.import_external([holding])
    row = store.trade_history()["items"][0]
    assert row["opened_date"] is row["duration_days"] is row["profit_per_year"] is None
    assert row["total_profit"] == 20
    assert "imported_position_date_unknown" in row["issues"]
    store.import_external([], source_transactions=[
        {"account": "source-a", "currency": "USD", "symbol": "ABC", "stock_market": "NYSE",
         "action": "BUY", "quantity": 10, "price": 10, "trade_date": "2026-01-01"},
        {"account": "source-a", "currency": "USD", "symbol": "ABC", "stock_market": "NYSE",
         "action": "SELL", "quantity": 10, "price": 12, "trade_date": "2026-01-11"},
    ])
    row = store.trade_history(as_of_date="2026-01-11")["items"][0]
    assert row["opened_date"] == "2026-01-01" and row["duration_days"] == 10
    assert row["total_profit"] == 20


def test_unknown_dates_and_invalid_quantities_are_explicit_and_json_safe(ledger):
    store, account = ledger
    tx = trade(store, account, "BUY", 1, 10, "2026-01-01")
    with store._connect() as conn:
        conn.execute("update transactions set trade_date = '' where id = ?", (tx["id"],))
    quote(store, 12)
    row = store.trade_history(as_of_date="2026-01-11")["items"][0]
    assert row["opened_date"] is row["duration_days"] is row["profit_per_year"] is None
    bad = {**tx, "id": "bad", "quantity": float("inf")}
    report = build_trade_history([bad], {account["id"]: account}, [], "2026-01-11")
    assert report["items"] == []
    assert report["unallocated_transactions"][0]["quantity"] is None
    json.dumps(report, allow_nan=False)


def test_account_currency_scope_and_normalized_agorot(ledger):
    store, account = ledger
    second = store.save_account({"id": "b", "account_id": "b", "username": "Other", "type": "Bank",
        "location": "Israel", "currency": "ILS", "persons": [{"name": "Other", "birth_date": "01/01/1991"}]})
    trade(store, account, "BUY", 2, 10, "2026-01-01")
    trade(store, second, "BUY", 2, 1000, "2026-01-01", location="Israel", currency="ILS")
    quote(store, 1200, currency="ILS", location="Israel")
    rows = store.trade_history(as_of_date="2026-01-11")["items"]
    assert len(rows) == 2
    usd = next(row for row in rows if row["currency"] == "USD")
    ils = next(row for row in rows if row["currency"] == "ILS")
    assert usd["total_profit"] is None
    assert ils["total_profit"] == 4
    assert ils["transactions"][0]["price"] == 10
    assert ils["transactions"][0]["price_input"] == 1000
    assert store.trade_history({"account_id": second["id"]})["items"][0]["account_id"] == second["id"]
    assert len(store.trade_history({"account_type": "Bank", "location": "Israel", "person_name": "Other"})["items"]) == 1
    assert store.trade_history({"person_name": "Absent"})["items"] == []


def test_currency_positions_in_same_account_are_separate(ledger):
    store, account = ledger
    trade(store, account, "BUY", 1, 10, "2026-01-01", currency="USD")
    trade(store, account, "BUY", 1, 20, "2026-01-02", currency="EUR")
    rows = store.trade_history(as_of_date="2026-01-11")["items"]
    assert len(rows) == 2
    assert {row["currency"] for row in rows} == {"USD", "EUR"}
    assert {row["cost_basis_remaining"] for row in rows} == {10, 20}


def test_missing_and_preopening_quotes_do_not_fabricate_profit(ledger):
    store, account = ledger
    trade(store, account, "BUY", 10, 10, "2026-01-02")
    trade(store, account, "SELL", 2, 15, "2026-01-03")
    quote(store, 15, "2026-01-01")
    quote(store, 30, "2026-02-01")
    row = store.trade_history(as_of_date="2026-01-11")["items"][0]
    assert row["realized_profit"] == 10
    assert row["unrealized_profit"] is row["total_profit"] is row["profit_per_day"] is None
    assert row["valuation_date"] is None and "missing_valuation" in row["issues"]


def test_remove_retains_known_realized_component_and_marks_unknown_total(ledger):
    store, account = ledger
    trade(store, account, "BUY", 10, 10, "2026-01-01")
    trade(store, account, "SELL", 2, 15, "2026-01-02")
    trade(store, account, "REMOVE", 8, 0, "2026-01-03")
    row = store.trade_history(as_of_date="2026-01-11")["items"][0]
    assert row["status"] == "closed" and row["realized_profit"] == 10
    assert row["total_profit"] is row["profit_per_year"] is None
    assert "transfer_without_profit" in row["issues"]


def test_delayed_income_and_reentry_are_not_silently_allocated(ledger):
    store, account = ledger
    trade(store, account, "BUY", 1, 10, "2026-01-01")
    trade(store, account, "SELL", 1, 12, "2026-01-02")
    trade(store, account, "DIVIDEND", 1, 5, "2026-01-03")
    trade(store, account, "BUY", 1, 10, "2026-01-04")
    trade(store, account, "DIVIDEND", 1, 7, "2026-01-05")
    report = store.trade_history(as_of_date="2026-01-11")
    assert len(report["unallocated_transactions"]) == 2
    assert {tx["issues"][0] for tx in report["unallocated_transactions"]} == {"unallocated_cash_entry", "ambiguous_cash_allocation"}
    assert all(row["income"] == 0 for row in report["items"])


def test_corrected_transaction_replays_current_ledger_and_report_is_read_only(ledger):
    store, account = ledger
    buy = trade(store, account, "BUY", 10, 1000, "2026-01-01", location="Israel", currency="ILS")
    trade(store, account, "SELL", 10, 1200, "2026-01-11", location="Israel", currency="ILS")
    assert store.trade_history(as_of_date="2026-01-11")["items"][0]["total_profit"] == 20
    store.update_transaction(buy["id"], {**buy, "price_input": 900})
    with store._connect() as conn:
        before = list(conn.iterdump())
    report = store.trade_history(as_of_date="2026-01-11")
    with store._connect() as conn:
        assert list(conn.iterdump()) == before
    row = report["items"][0]
    assert row["total_profit"] == 30 and row["profit_per_day"] == 3
    assert row["transactions"][0]["price_input"] == 900 and row["transactions"][0]["price"] == 9


def test_invalid_report_parameters(ledger):
    store, _ = ledger
    with pytest.raises(ValueError, match="as_of_date"):
        store.trade_history(as_of_date="invalid")
    with pytest.raises(ValueError, match="status"):
        store.trade_history({"status": "invalid"})


def test_invalid_history_does_not_produce_complete_returns(ledger):
    store, account = ledger
    buy = trade(store, account, "BUY", 1, 10, "2026-01-01")
    malformed = {**buy, "id": "malformed", "quantity": 1e308, "price": 1e308, "trade_date": "2025-01-01"}
    report = build_trade_history([malformed, buy], {account["id"]: account}, [], "2026-01-11")
    assert "incomplete_cost_basis" in report["items"][0]["issues"]
    assert report["items"][0]["total_profit"] is None
    json.dumps(report, allow_nan=False)


def test_unsupported_derivative_does_not_claim_unscaled_realized_profit(ledger):
    store, account = ledger
    buy = trade(store, account, "BUY", 1, 10, "2026-01-01")
    sell = trade(store, account, "SELL", 1, 12, "2026-01-11")
    records = [{**tx, "instrument_type": "OPTION"} for tx in [buy, sell]]
    row = build_trade_history(records, {account["id"]: account}, [], "2026-01-11")["items"][0]
    assert "unsupported_instrument" in row["issues"]
    assert row["realized_profit"] is row["realized_trading_profit"] is row["total_profit"] is None


def test_defining_instrument_after_purchase_keeps_one_closed_episode(ledger):
    store, account = ledger
    buy = trade(store, account, "BUY", 10, 10, "2026-01-01")
    assert buy["security_id"] == ""
    security = store.save_manual_security({
        "symbol": "ABC", "name": "ABC company", "stock_market": "NYSE",
        "instrument_type": "STOCK", "currency": "USD", "location": "USA",
    })
    sell = trade(store, account, "SELL", 10, 12, "2026-01-11")
    assert sell["security_id"] == security["id"]
    report = store.trade_history(as_of_date="2026-01-11")
    assert len(report["items"]) == 1
    row = report["items"][0]
    assert row["security_id"] == security["id"]
    assert row["side"] == "long" and row["status"] == "closed"
    assert row["quantity_remaining"] == 0 and row["duration_days"] == 10
    assert row["total_profit"] == 20
    assert row["profit_per_day"] == 2 and row["profit_per_year"] == 730
    assert {tx["id"] for tx in row["transactions"]} == {buy["id"], sell["id"]}
    assert store.holdings() == []
    assert next(tx for tx in store.list_transactions() if tx["id"] == buy["id"])["security_id"] == ""


def test_legacy_identity_resolution_does_not_merge_distinct_explicit_securities(ledger):
    store, account = ledger
    buy = trade(store, account, "BUY", 10, 10, "2026-01-01")
    sell = trade(store, account, "SELL", 10, 12, "2026-01-11")
    # Sanitized legacy ledger: two explicit instruments reuse the same symbol.
    records = [
        {**buy, "security_id": "instrument-a"},
        {**sell, "security_id": "instrument-b"},
        {**buy, "id": "legacy-blank", "trade_date": "2026-01-02"},
    ]
    rows = build_trade_history(records, {account["id"]: account}, [], "2026-01-11")["items"]
    assert len(rows) == 3
    assert {row["security_id"] for row in rows} == {"", "instrument-a", "instrument-b"}
    assert all(len(row["transactions"]) == 1 for row in rows)
    legacy = next(row for row in rows if not row["security_id"])
    assert "incomplete_cost_basis" in legacy["issues"]
    assert legacy["total_profit"] is None


def test_unknown_basis_withholds_realized_amounts_instead_of_claiming_valid_subset(ledger):
    store, account = ledger
    buy = trade(store, account, "BUY", 1, 10, "2026-01-02")
    sell = trade(store, account, "SELL", 1, 20, "2026-01-11")
    invalid_buy = {**buy, "id": "invalid-buy", "trade_date": "2026-01-01", "quantity": float("nan")}
    report = build_trade_history([invalid_buy, buy, sell], {account["id"]: account}, [], "2026-01-11")
    row = report["items"][0]
    assert "incomplete_cost_basis" in row["issues"]
    assert row["realized_trading_profit"] is row["realized_profit"] is row["total_profit"] is None
    assert row["profit_per_day"] is row["profit_per_year"] is None
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("acquisition_class", ["RSU", "STOCK"])
@pytest.mark.parametrize("define_instrument", [False, True])
def test_stock_grant_metadata_changes_keep_one_closed_episode(ledger, acquisition_class, define_instrument):
    store, account = ledger
    add = trade(store, account, "ADD", 10, 10, "2026-01-01", asset_class=acquisition_class)
    if define_instrument:
        store.save_manual_security({
            "symbol": "ABC", "name": "ABC company", "stock_market": "NYSE",
            "instrument_type": "STOCK", "currency": "USD", "location": "USA",
        })
    sell = trade(store, account, "SELL", 10, 12, "2026-01-11")
    assert store.holdings() == []
    rows = store.trade_history(as_of_date="2026-01-11")["items"]
    assert len(rows) == 1
    row = rows[0]
    assert row["side"] == "long" and row["status"] == "closed"
    assert row["quantity_remaining"] == 0 and row["duration_days"] == 10
    assert row["total_profit"] == 20
    assert row["profit_per_day"] == 2 and row["profit_per_year"] == 730
    assert row["transactions"][0]["asset_class"] == acquisition_class
    assert {tx["id"] for tx in row["transactions"]} == {add["id"], sell["id"]}


def test_compatible_stock_class_quote_and_identity_guards(ledger):
    store, account = ledger
    add = trade(store, account, "ADD", 10, 10, "2026-01-01", asset_class="RSU")
    quote(store, 12)
    row = store.trade_history(as_of_date="2026-01-11")["items"][0]
    assert row["unrealized_profit"] == 20
    assert row["valuation_date"] == "2026-01-11"
    records = [
        {**add, "security_id": "instrument-a"},
        {**add, "id": "other-security", "asset_class": "EQUITY", "security_id": "instrument-b"},
        {**add, "id": "other-currency", "currency": "EUR", "asset_class": "EQUITY", "security_id": "instrument-a"},
    ]
    rows = build_trade_history(records, {account["id"]: account}, [], "2026-01-11")["items"]
    assert len(rows) == 3
    assert {(row["security_id"], row["currency"]) for row in rows} == {
        ("instrument-a", "USD"), ("instrument-b", "USD"), ("instrument-a", "EUR"),
    }
