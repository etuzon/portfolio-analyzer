"""Local trade reasoning and append-only reviews, separate from the trade ledger.

Captured trade facts never change. Saved raw quotes are descriptive price
evidence only; they are not a return or an automatic quality rating.
"""
from __future__ import annotations

from .investment_scope import investments

from copy import deepcopy
from datetime import date, datetime, timezone
import json
import math
import re

PREFIX = "trading_journal_v1:"
ELIGIBLE_ACTIONS = {"BUY", "SELL", "SHORT"}
RATINGS = {"good", "mixed", "bad"}
PRICE_ASSETS = {"EQUITY", "ETF", "MUTUALFUND", "RSU", "STOCK"}
MAX_TEXT = 5000
MAX_HISTORY = 1000
MAX_ENTRIES = 10000
FACT_FIELDS = ("id", "account_id", "symbol", "stock_market", "asset_class", "security_id",
               "currency", "action", "trade_date", "quantity", "price")


class JournalError(ValueError):
    """Public, machine-readable error code."""


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _number(value):
    try:
        result = float(value)
        return result if not isinstance(value, bool) and math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _date(value, *, optional=False):
    if optional and value in (None, ""):
        return ""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise JournalError("journal_invalid_date")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise JournalError("journal_invalid_date") from None


def _text(value, *, required=False, code="journal_invalid_text"):
    if value is None and not required:
        return ""
    if not isinstance(value, str) or len(value.strip()) > MAX_TEXT or (required and not value.strip()):
        raise JournalError(code)
    return value.strip()


def _id(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise JournalError("journal_invalid_transaction")
    return value.strip()


def _revision(payload):
    value = payload.get("expected_revision")
    if type(value) is not int or value < 0:
        raise JournalError("journal_revision_required")
    return value


def _author(actor):
    return str((actor or {}).get("username") or "")[:200] if isinstance(actor, dict) else ""


def _label(account):
    return " · ".join(str(account.get(key) or "").strip() for key in
                      ("management_company", "username", "account_id") if account.get(key)) or str(account.get("id") or "")


def _safe_trade(tx, accounts):
    account_id = str(tx.get("account_db_id") or tx.get("account_id") or "")
    account = accounts.get(account_id, {})
    return {"id": str(tx.get("id") or ""), "account_id": account_id,
            "account_label": _label(account) or str(tx.get("account_label") or account_id),
            "symbol": str(tx.get("symbol") or "").upper().strip(),
            "name": str(tx.get("security_name") or tx.get("name") or tx.get("symbol") or ""),
            "stock_market": str(tx.get("stock_market") or "").upper().strip(),
            "asset_class": str(tx.get("asset_class") or "").upper().strip(),
            "security_id": str(tx.get("security_id") or ""),
            "currency": str(tx.get("currency") or "").upper().strip(),
            "action": str(tx.get("action") or "").upper().strip(),
            "trade_date": str(tx.get("trade_date") or ""),
            "quantity": _number(tx.get("quantity")), "price": _number(tx.get("price"))}


def _ledger(store):
    store = investments(store)
    accounts = store.list_accounts()
    by_account = {row["id"]: row for row in accounts}
    trades = {str(tx.get("id")): _safe_trade(tx, by_account) for tx in store.list_transactions()}
    return accounts, trades


def _entry_allowed(item, account_ids, transaction_accounts):
    # A deleted trade can keep its original notes while its authoritative
    # account remains Investment. A moved trade must also still be in scope.
    return item["trade"].get("account_id") in account_ids and (
        item["transaction_id"] not in transaction_accounts
        or transaction_accounts[item["transaction_id"]] in account_ids)


def _decode(raw, transaction_id=None):
    try:
        item = json.loads(raw)
    except (ValueError, TypeError):
        raise JournalError("journal_invalid_saved_entry") from None
    if not isinstance(item, dict) or not isinstance(item.get("trade"), dict) or type(item.get("revision")) is not int:
        raise JournalError("journal_invalid_saved_entry")
    if not isinstance(item.get("reason_history"), list) or not isinstance(item.get("reviews"), list):
        raise JournalError("journal_invalid_saved_entry")
    if (not isinstance(item.get("transaction_id"), str) or not isinstance(item.get("reason"), str)
            or not isinstance(item.get("created_at"), str)
            or any(not isinstance(row, dict) or not isinstance(row.get("reason"), str) for row in item["reason_history"])
            or any(not isinstance(row, dict) or not isinstance(row.get("rating"), str) or row.get("rating") not in RATINGS
                   or not isinstance(row.get("notes"), str) for row in item["reviews"])):
        raise JournalError("journal_invalid_saved_entry")
    trade = item["trade"]
    if (item.get("id") != item["transaction_id"] or trade.get("id") != item["transaction_id"]
            or (transaction_id is not None and item["transaction_id"] != transaction_id)
            or any(not isinstance(trade.get(key), str) for key in
                   ("account_id", "symbol", "stock_market", "asset_class", "security_id", "currency", "action", "trade_date"))):
        raise JournalError("journal_invalid_saved_entry")
    return item


def _read(conn, transaction_id):
    row = conn.execute("select value from app_preferences where key=?", (PREFIX + transaction_id,)).fetchone()
    return _decode(row["value"], transaction_id) if row else None


def _write(conn, item):
    conn.execute("""insert into app_preferences(key,value,updated_at) values(?,?,?)
                    on conflict(key) do update set value=excluded.value,updated_at=excluded.updated_at""",
                 (PREFIX + item["transaction_id"], json.dumps(item, allow_nan=False), item["updated_at"]))


def _asset(value):
    return "EQUITY" if value in {"STOCK", "RSU", "EQUITY"} else value


def _price_identity(row):
    return tuple(str(row.get(key) or "").upper().strip() for key in ("symbol", "stock_market", "currency")) + (
        _asset(str(row.get("asset_class") or "").upper().strip()),)


def _group_prices(prices):
    groups = {}
    for row in prices:
        groups.setdefault(_price_identity(row), []).append(row)
    return groups


def _outcome(trade, prices, link_status, today):
    result = {"status": "no_later_price", "price_change_percent": None, "last_price": None,
              "last_price_date": None, "currency": trade.get("currency"), "source": None}
    if link_status != "current":
        result["status"] = "link_changed" if link_status == "changed" else "deleted_transaction"
        return result
    if trade.get("asset_class") not in PRICE_ASSETS:
        result["status"] = "unsupported_instrument"
        return result
    entry = _number(trade.get("price"))
    if entry is None or entry <= 0:
        result["status"] = "invalid_trade_price"
        return result
    try:
        trade_day = _date(trade.get("trade_date"))
    except JournalError:
        return result
    candidates = []
    for row in prices:
        if (str(row.get("symbol") or "").upper().strip() != trade.get("symbol")
                or str(row.get("stock_market") or "").upper().strip() != trade.get("stock_market")
                or str(row.get("currency") or "").upper().strip() != trade.get("currency")
                or _asset(str(row.get("asset_class") or "").upper()) != _asset(trade.get("asset_class"))):
            continue
        try:
            day = _date(row.get("price_date"))
        except JournalError:
            continue
        price = _number(row.get("price"))
        if price is not None and price > 0 and trade_day < day <= today.isoformat():
            candidates.append((day, str(row.get("id") or ""), price, row.get("source")))
    if not candidates:
        return result
    day, _, price, source = max(candidates)
    change = (price / entry - 1) * 100
    if not math.isfinite(change):
        result["status"] = "invalid_trade_price"
        return result
    result.update(status="stale" if (today - date.fromisoformat(day)).days > 7 else "ok",
                  price_change_percent=change, last_price=price, last_price_date=day,
                  source=str(source or "local"))
    return result


def _view(item, trades, prices, today):
    result = deepcopy(item)
    current = trades.get(item["transaction_id"])
    status = "deleted" if current is None else "changed" if any(
        item["trade"].get(key) != current.get(key) for key in FACT_FIELDS) else "current"
    result.update(link_status=status, current_trade=current,
                  review_status=item["reviews"][-1]["rating"] if item["reviews"] else "pending")
    result["outcome"] = _outcome(item["trade"], prices.get(_price_identity(item["trade"]), []), status, today)
    result["review_due"] = bool(item.get("review_date") and item["review_date"] <= today.isoformat()
                                and not item["reviews"])
    return result


def journal_payload(store, *, account_id="", action="", review_status="", query="", today=None):
    store = investments(store)
    today = today or date.today()
    if not isinstance(today, date):
        raise JournalError("journal_invalid_date")
    if not isinstance(action, str) or action not in ELIGIBLE_ACTIONS | {""}:
        raise JournalError("journal_invalid_action")
    if not isinstance(review_status, str) or review_status not in RATINGS | {"", "pending"}:
        raise JournalError("journal_invalid_rating")
    if not isinstance(account_id, str) or not isinstance(query, str) or len(query) > 500:
        raise JournalError("journal_invalid_filter")
    accounts, trades = _ledger(store)
    with store._connect() as conn:
        rows = conn.execute("select key,value from app_preferences where substr(key,1,?)=? order by updated_at desc limit ?",
                            (len(PREFIX), PREFIX, MAX_ENTRIES + 1)).fetchall()
    if len(rows) > MAX_ENTRIES:
        raise JournalError("journal_entry_limit")
    entries = [_decode(row["value"], row["key"][len(PREFIX):]) for row in rows]
    known = {row["id"] for row in accounts}
    transaction_accounts = store.transaction_accounts()
    entries = [item for item in entries if _entry_allowed(item, known, transaction_accounts)]
    if account_id and account_id not in known:
        raise JournalError("journal_unknown_account")
    prices = _group_prices(store.list_prices())
    views = [_view(item, trades, prices, today) for item in entries]
    counts = {"total": len(views), "pending": sum(row["review_status"] == "pending" for row in views),
              "good": sum(row["review_status"] == "good" for row in views),
              "mixed": sum(row["review_status"] == "mixed" for row in views),
              "bad": sum(row["review_status"] == "bad" for row in views),
              "due": sum(row["review_due"] for row in views)}
    search = query.strip().casefold()
    def matches(row):
        trade = row["trade"]
        text = " ".join(str(value or "") for value in [trade.get("symbol"), trade.get("name"),
                       trade.get("account_label"), row.get("reason"), row.get("thesis"),
                       *(r.get("notes") for r in row["reviews"])])
        return (not account_id or trade.get("account_id") == account_id) and (not action or trade.get("action") == action) \
            and (not review_status or row["review_status"] == review_status) and (not search or search in text.casefold())
    return {"items": sorted((row for row in views if matches(row)), key=lambda row: row["created_at"], reverse=True),
            "transactions": sorted((row for row in trades.values() if row["action"] in ELIGIBLE_ACTIONS),
                                   key=lambda row: (row["trade_date"], row["id"]), reverse=True),
            "accounts": accounts, "counts": counts, "as_of_date": today.isoformat()}


def save_reason(store, payload, actor=None):
    store = investments(store)
    if not isinstance(payload, dict):
        raise JournalError("journal_invalid_payload")
    transaction_id = _id(payload.get("transaction_id"))
    expected = _revision(payload)
    reason = _text(payload.get("reason"), required=True, code="journal_reason_required")
    thesis = _text(payload.get("thesis", ""))
    review_date = _date(payload.get("review_date", ""), optional=True)
    with store._sync_lock:
        with store._connect() as conn:
            conn.execute("begin immediate")
            # Read linked trade facts while the SQLite writer lock prevents a
            # concurrent correction/deletion from racing the initial capture.
            _, trades = _ledger(store)
            current = trades.get(transaction_id)
            item = _read(conn, transaction_id)
            if item is not None and not _entry_allowed(item, store.account_ids(), store.transaction_accounts()):
                raise JournalError("journal_invalid_transaction")
            if (item["revision"] if item else 0) != expected:
                raise JournalError("journal_conflict")
            if item is None:
                if current is None or current["action"] not in ELIGIBLE_ACTIONS:
                    raise JournalError("journal_invalid_transaction")
                _date(current["trade_date"])
                if not current["symbol"] or not current["account_id"]:
                    raise JournalError("journal_invalid_transaction")
                count = conn.execute("select count(*) from app_preferences where substr(key,1,?)=?",
                                     (len(PREFIX), PREFIX)).fetchone()[0]
                if count >= MAX_ENTRIES:
                    raise JournalError("journal_entry_limit")
                now = _now()
                item = {"id": transaction_id, "transaction_id": transaction_id, "trade": current,
                        "created_at": now, "updated_at": now, "revision": 0,
                        "reason_history": [], "reviews": []}
            changed = any(item.get(key, "") != value for key, value in
                          (("reason", reason), ("thesis", thesis), ("review_date", review_date)))
            if changed:
                if len(item["reason_history"]) >= MAX_HISTORY:
                    raise JournalError("journal_history_limit")
                now = _now()
                item.update(reason=reason, thesis=thesis, review_date=review_date,
                            updated_at=now, revision=item["revision"] + 1)
                item["reason_history"].append({"reason": reason, "thesis": thesis, "review_date": review_date,
                                                "recorded_at": now, "author": _author(actor)})
                _write(conn, item)
    _, trades = _ledger(store)
    return _view(item, trades, _group_prices(store.list_prices()), date.today())


def add_review(store, entry_id, payload, actor=None):
    store = investments(store)
    entry_id = _id(entry_id)
    if not isinstance(payload, dict):
        raise JournalError("journal_invalid_payload")
    expected = _revision(payload)
    rating = payload.get("rating")
    if not isinstance(rating, str) or rating not in RATINGS:
        raise JournalError("journal_invalid_rating")
    notes = _text(payload.get("notes"), required=True, code="journal_review_notes_required")
    with store._sync_lock:
        with store._connect() as conn:
            conn.execute("begin immediate")
            item = _read(conn, entry_id)
            if item is None or not _entry_allowed(item, store.account_ids(), store.transaction_accounts()):
                raise JournalError("journal_not_found")
            if item["revision"] != expected:
                raise JournalError("journal_conflict")
            if len(item["reviews"]) >= MAX_HISTORY:
                raise JournalError("journal_history_limit")
            now = _now()
            item["reviews"].append({"rating": rating, "notes": notes, "recorded_at": now, "author": _author(actor)})
            item.update(updated_at=now, revision=item["revision"] + 1)
            _write(conn, item)
    _, trades = _ledger(store)
    return _view(item, trades, _group_prices(store.list_prices()), date.today())
