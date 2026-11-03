"""Synthetic ledger tests for preserved reasoning, review history and price evidence."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date
import json
import sqlite3

import pytest

from app.local_portfolio import LocalPortfolioStore
from app.trading_journal import JournalError, PREFIX, add_review, journal_payload, save_reason

TODAY = date(2025, 4, 1)


@pytest.fixture
def ledger(tmp_path):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    a = store.save_account({"type": "Investment", "account_id": "First", "currency": "USD", "location": "USA",
                            "persons": [{"name": "Synthetic one", "birth_date": "01/01/1990"}]})
    b = store.save_account({"type": "Investment", "account_id": "Second", "currency": "USD", "location": "USA",
                            "persons": [{"name": "Synthetic two", "birth_date": "01/01/1990"}]})
    def trade(account=a, action="BUY", **kwargs):
        return store.add_transaction({"account_db_id": account["id"], "symbol": "TEST", "stock_market": "NASDAQ",
                                      "asset_class": "EQUITY", "quantity": 10, "price_input": 100,
                                      "currency": "USD", "location": "USA", "trade_date": "2025-01-01",
                                      "action": action, **kwargs})
    buy = trade()
    sell = trade(action="SELL", price_input=110, trade_date="2025-02-01")
    short = trade(account=b, action="SHORT", symbol="SHORTY", price_input=200)
    return store, a, b, buy, sell, short, trade


def reason(store, transaction, **kwargs):
    return save_reason(store, {"transaction_id": transaction["id"], "reason": "Earnings thesis", "thesis": "Margins can weaken",
                               "review_date": "2025-03-01", "expected_revision": 0, **kwargs}, {"id": "operator", "username": "Analyst"})


def add_price(store, **kwargs):
    return store.save_price({"symbol": "TEST", "stock_market": "NASDAQ", "asset_class": "EQUITY", "currency": "USD",
                             "location": "USA", "price_input": 120, "price_date": "2025-03-30", "source": "Synthetic quote", **kwargs})


def test_closed_trades_remain_selectable_and_snapshot_original_facts(ledger):
    store, a, b, buy, sell, short, _ = ledger
    data = journal_payload(store, today=TODAY)
    assert data["items"] == []
    assert {row["id"] for row in data["transactions"]} == {buy["id"], sell["id"], short["id"]}
    saved = reason(store, sell)
    assert saved["trade"]["price"] == 110 and saved["trade"]["action"] == "SELL"
    assert saved["trade"]["account_id"] == a["id"]
    assert saved["link_status"] == "current"
    assert saved["reason_history"][0]["author"] == "Analyst"
    assert saved["reason_history"][0]["recorded_at"].endswith("Z")
    assert saved["review_status"] == "pending"
    assert journal_payload(store, today=TODAY)["items"][0]["review_due"]


def test_reason_updates_preserve_original_snapshot_and_every_revision(ledger):
    store, _, _, buy, *_ = ledger
    first = reason(store, buy)
    revised = reason(store, buy, expected_revision=1, reason="New information changed my thesis", review_date="2027-01-01")
    assert revised["revision"] == 2
    assert revised["reason"] == "New information changed my thesis"
    assert revised["reason_history"][0]["reason"] == "Earnings thesis"
    assert len(revised["reason_history"]) == 2
    assert revised["created_at"] == first["created_at"] and revised["trade"] == first["trade"]
    noop = reason(store, buy, expected_revision=2, reason=revised["reason"], review_date="2027-01-01")
    assert noop["revision"] == 2 and len(noop["reason_history"]) == 2
    assert not journal_payload(store, today=TODAY)["items"][0]["review_due"]


def test_reviews_are_manual_append_only_and_do_not_rewrite_reason(ledger):
    store, _, _, buy, *_ = ledger
    first = reason(store, buy)
    reviewed = add_review(store, buy["id"], {"expected_revision": 1, "rating": "good", "notes": "The original evidence held"}, {"username": "Reviewer"})
    revised = add_review(store, buy["id"], {"expected_revision": 2, "rating": "bad", "notes": "Later evidence changed the assessment"})
    assert reviewed["revision"] == 2 and revised["revision"] == 3
    assert revised["reason_history"] == first["reason_history"]
    assert [row["rating"] for row in revised["reviews"]] == ["good", "bad"]
    assert revised["reviews"][0]["author"] == "Reviewer"
    assert revised["review_status"] == "bad"
    assert not revised["review_due"]


@pytest.mark.parametrize("patch,code", [
    ({"expected_revision": True}, "journal_revision_required"),
    ({"expected_revision": 1.0}, "journal_revision_required"),
    ({"reason": "  "}, "journal_reason_required"),
    ({"reason": "x" * 5001}, "journal_reason_required"),
    ({"reason": []}, "journal_reason_required"),
    ({"thesis": 12}, "journal_invalid_text"),
    ({"review_date": "31/03/2025"}, "journal_invalid_date"),
    ({"review_date": "2025-02-30"}, "journal_invalid_date"),
    ({"transaction_id": "missing"}, "journal_invalid_transaction"),
])
def test_invalid_reason_inputs_leave_preferences_unchanged(ledger, patch, code):
    store, _, _, buy, *_ = ledger
    with pytest.raises(JournalError, match=f"^{code}$"):
        reason(store, buy, **patch)
    assert journal_payload(store, today=TODAY)["items"] == []


@pytest.mark.parametrize("patch,code", [
    ({"rating": "pending"}, "journal_invalid_rating"), ({"rating": []}, "journal_invalid_rating"),
    ({"rating": {}}, "journal_invalid_rating"),
    ({"notes": ""}, "journal_review_notes_required"), ({"notes": "x" * 5001}, "journal_review_notes_required"),
    ({"expected_revision": None}, "journal_revision_required"),
])
def test_invalid_review_does_not_append_or_increment(ledger, patch, code):
    store, _, _, buy, *_ = ledger
    reason(store, buy)
    payload = {"expected_revision": 1, "rating": "mixed", "notes": "A lesson", **patch}
    with pytest.raises(JournalError, match=f"^{code}$"):
        add_review(store, buy["id"], payload)
    entry = journal_payload(store, today=TODAY)["items"][0]
    assert entry["revision"] == 1 and entry["reviews"] == []


def test_missing_and_ineligible_transactions_cannot_create_journals(ledger):
    store, _, _, buy, _, _, trade = ledger
    dividend = trade(action="DIVIDEND", quantity=1, price_input=10)
    gift = trade(action="ADD", symbol="GIFT")
    for tx in (dividend, gift):
        with pytest.raises(JournalError, match="journal_invalid_transaction"):
            reason(store, tx)
    assert {row["action"] for row in journal_payload(store)["transactions"]} == {"BUY", "SELL", "SHORT"}
    with pytest.raises(JournalError, match="journal_not_found"):
        add_review(store, "missing", {"expected_revision": 0, "rating": "good", "notes": "A note"})


def test_stale_revision_and_duplicate_creation_cannot_overwrite_audit(ledger):
    store, _, _, buy, *_ = ledger
    reason(store, buy)
    for operation in (lambda: reason(store, buy), lambda: add_review(store, buy["id"], {"expected_revision": 0, "rating": "good", "notes": "late"})):
        with pytest.raises(JournalError, match="journal_conflict"):
            operation()
    entry = journal_payload(store)["items"][0]
    assert entry["revision"] == 1 and entry["reviews"] == []


def test_corrected_trade_keeps_original_facts_and_suppresses_misleading_evidence(ledger):
    store, _, _, _, sell, *_ = ledger
    saved = reason(store, sell)
    add_price(store)
    store.update_transaction(sell["id"], {"price_input": 130, "trade_date": "2025-02-02"})
    result = journal_payload(store, today=TODAY)["items"][0]
    assert result["link_status"] == "changed"
    assert result["trade"]["price"] == 110 and result["current_trade"]["price"] == 130
    assert result["trade"]["trade_date"] == "2025-02-01"
    assert result["outcome"]["status"] == "link_changed" and result["outcome"]["price_change_percent"] is None
    updated = reason(store, sell, expected_revision=1, reason="Correction explained")
    assert updated["trade"] == saved["trade"] and len(updated["reason_history"]) == 2


def test_deleted_trade_keeps_journal_and_can_receive_a_review(ledger):
    store, _, _, _, sell, *_ = ledger
    saved = reason(store, sell)
    assert store.delete_transaction(sell["id"])
    result = journal_payload(store, today=TODAY)["items"][0]
    assert result["link_status"] == "deleted" and result["current_trade"] is None
    assert result["trade"] == saved["trade"]
    assert result["outcome"]["status"] == "deleted_transaction"
    reviewed = add_review(store, sell["id"], {"expected_revision": 1, "rating": "mixed", "notes": "The transaction was removed during reconciliation"})
    assert reviewed["review_status"] == "mixed" and reviewed["link_status"] == "deleted"


def test_outcome_uses_later_matching_raw_quotes_without_auto_rating(ledger):
    store, _, _, buy, sell, *_ = ledger
    reason(store, buy)
    reason(store, sell)
    add_price(store)
    data = journal_payload(store, today=TODAY)
    by_id = {row["id"]: row for row in data["items"]}
    assert by_id[buy["id"]]["outcome"]["price_change_percent"] == pytest.approx(20)
    assert by_id[sell["id"]]["outcome"]["price_change_percent"] == pytest.approx((120 / 110 - 1) * 100)
    assert all(row["review_status"] == "pending" for row in data["items"])
    assert by_id[buy["id"]]["outcome"]["last_price_date"] == "2025-03-30"
    assert by_id[buy["id"]]["outcome"]["source"] == "Synthetic quote"
    assert by_id[buy["id"]]["outcome"]["status"] == "ok"


@pytest.mark.parametrize("patch", [
    {"currency": "ILS"}, {"stock_market": "NYSE"}, {"symbol": "OTHER"}, {"asset_class": "BOND"},
    {"price_date": "2025-01-01"}, {"price_date": "2025-04-02"},
])
def test_mismatched_same_day_and_future_quotes_are_not_evidence(ledger, patch):
    store, _, _, buy, *_ = ledger
    reason(store, buy)
    # Source quote storage may normalize market units; matching must remain strict.
    add_price(store, **patch)
    outcome = journal_payload(store, today=TODAY)["items"][0]["outcome"]
    assert outcome["status"] == "no_later_price" and outcome["last_price"] is None


def test_old_quote_is_dated_and_flagged_stale(ledger):
    store, _, _, buy, *_ = ledger
    reason(store, buy)
    add_price(store, price_date="2025-03-01")
    result = journal_payload(store, today=TODAY)["items"][0]["outcome"]
    assert result["status"] == "stale" and result["last_price_date"] == "2025-03-01"
    assert result["price_change_percent"] == pytest.approx(20)


@pytest.mark.parametrize("price", [True, float("nan"), float("inf"), -1, 0, "invalid"])
def test_invalid_saved_numeric_quotes_never_create_price_evidence(ledger, monkeypatch, price):
    store, _, _, buy, *_ = ledger
    reason(store, buy)
    monkeypatch.setattr(store, "list_prices", lambda: [{"symbol": "TEST", "stock_market": "NASDAQ", "asset_class": "EQUITY",
                                                      "currency": "USD", "price_date": "2025-03-30", "price": price}])
    outcome = journal_payload(store, today=TODAY)["items"][0]["outcome"]
    assert outcome["status"] == "no_later_price" and outcome["last_price"] is None


def test_zero_entry_price_and_derivatives_keep_manual_review_available(ledger):
    store, _, _, _, _, _, trade = ledger
    zero = trade(symbol="FREE", price_input=0)
    option = trade(symbol="FUT", asset_class="FUTURE")
    reason(store, zero)
    reason(store, option)
    result = {row["id"]: row for row in journal_payload(store, today=TODAY)["items"]}
    assert result[zero["id"]]["outcome"]["status"] == "invalid_trade_price"
    assert result[option["id"]]["outcome"]["status"] == "unsupported_instrument"


def test_filters_and_summary_keep_manual_assessment_independent(ledger):
    store, a, b, buy, sell, short, _ = ledger
    reason(store, buy)
    reason(store, sell, reason="Reducing concentration")
    reason(store, short, reason="Risk thesis")
    add_review(store, buy["id"], {"expected_revision": 1, "rating": "good", "notes": "Stayed within plan"})
    assert len(journal_payload(store, account_id=a["id"])["items"]) == 2
    assert [row["id"] for row in journal_payload(store, action="SHORT")["items"]] == [short["id"]]
    assert [row["id"] for row in journal_payload(store, review_status="good")["items"]] == [buy["id"]]
    assert [row["id"] for row in journal_payload(store, query="concentration")["items"]] == [sell["id"]]
    data = journal_payload(store, query="STAYED within plan", today=TODAY)
    assert [row["id"] for row in data["items"]] == [buy["id"]]
    assert data["counts"] == {"total": 3, "pending": 2, "good": 1, "mixed": 0, "bad": 0, "due": 2}
    for filters in ({"action": "DIVIDEND"}, {"review_status": "profit"}, {"account_id": "missing"}):
        with pytest.raises(JournalError): journal_payload(store, **filters)


def test_concurrent_reviews_compare_revisions_across_store_instances(ledger):
    store, _, _, buy, *_ = ledger
    reason(store, buy)
    other = LocalPortfolioStore(store.path)
    def review(target, rating):
        try:
            add_review(target, buy["id"], {"expected_revision": 1, "rating": rating, "notes": rating})
            return "saved"
        except JournalError as error:
            return str(error)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(review, target, rating) for target, rating in ((store, "good"), (other, "bad"))]
        assert sorted(f.result() for f in futures) == ["journal_conflict", "saved"]
    entry = journal_payload(store)["items"][0]
    assert entry["revision"] == 2 and len(entry["reviews"]) == 1


def test_first_snapshot_reserves_database_before_reading_trade_facts(ledger, monkeypatch):
    from app import trading_journal
    store, _, _, _, sell, *_ = ledger
    other = LocalPortfolioStore(store.path)
    original_ledger = trading_journal._ledger
    attempted = []
    def check_reservation(target):
        if not attempted:
            attempted.append(True)
            with other._connect() as conn:
                conn.execute("pragma busy_timeout=1")
                with pytest.raises(sqlite3.OperationalError, match="locked"):
                    conn.execute("delete from transactions where id=?", (sell["id"],))
        return original_ledger(target)
    monkeypatch.setattr(trading_journal, "_ledger", check_reservation)
    saved = reason(store, sell)
    assert attempted and saved["link_status"] == "current"
    assert saved["trade"]["price"] == 110


def test_journal_writes_leave_ledger_and_balances_unchanged_and_restore_in_backup(ledger, tmp_path):
    store, _, _, buy, *_ = ledger
    before = deepcopy(store.export_data()["data"])
    reason(store, buy)
    add_review(store, buy["id"], {"expected_revision": 1, "rating": "mixed", "notes": "A recorded lesson"})
    after = store.export_data()
    for table in before:
        if table != "app_preferences": assert after["data"][table] == before[table]
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    restored.import_data(after)
    assert journal_payload(restored, today=TODAY) == journal_payload(store, today=TODAY)


def test_preference_namespace_matching_is_exact_and_invalid_saved_data_is_visible_error(ledger):
    store, _, _, buy, *_ = ledger
    store.set_preference("tradingXjournalYv1:other", {"unrelated": True})
    assert journal_payload(store)["items"] == []
    store.set_preference(PREFIX + buy["id"], {"trade": {}, "revision": 1, "reason_history": [], "reviews": []})
    with pytest.raises(JournalError, match="journal_invalid_saved_entry"):
        journal_payload(store)
