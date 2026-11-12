"""Read-only saved evidence for browser-local portfolio risk scenarios.

Unlike observed risk history, these contexts neither register a token nor save
an observation. Unknown ledger inputs must stay unavailable rather than becoming
zero through the dashboard's legacy cash arithmetic.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
import re
from typing import Callable
from zoneinfo import ZoneInfo

from . import risk_history
from .local_portfolio import ASSET_CLASSES, CASH_LEDGER_ACTIONS, _cash_delta, _parse_date


_SECURITY_ACTIONS = {"ADD", "REMOVE", "BUY", "SELL", "SHORT"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fail(code: str):
    raise risk_history.RiskHistoryError(code, 409)


def _known_currency(value) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Z]{3}", value))


def _validate(inputs: dict, now: datetime) -> None:
    today = now.astimezone(ZoneInfo("Asia/Jerusalem")).date()
    accounts = {str(account["id"]): account for account in inputs["accounts"]}
    balances = {}
    for account_id, account in accounts.items():
        cash = risk_history._number(account.get("initial_cash"))
        if cash is None:
            _fail("risk_context_unknown_cash")
        if not _known_currency(account.get("currency")):
            _fail("risk_context_missing_currency")
        balances[account_id] = cash
    for item in inputs["items"]:
        holding = item.get("holding") or {}
        if str(holding.get("account_id") or "") not in accounts:
            _fail("risk_context_unassigned_account")
        if holding.get("asset_class") not in ASSET_CLASSES:
            _fail("risk_context_missing_classification")
        if not _known_currency(holding.get("currency")):
            _fail("risk_context_missing_currency")
    for tx in inputs["transactions"]:
        action = tx.get("action")
        if action not in CASH_LEDGER_ACTIONS | _SECURITY_ACTIONS:
            _fail("risk_context_invalid_transaction")
        raw_day = tx.get("trade_date")
        day = (_parse_date(raw_day) if isinstance(raw_day, str) and
               re.fullmatch(r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})", raw_day) else None)
        if day is None:
            _fail("risk_context_invalid_transaction_date")
        if day > today:
            _fail("risk_context_future_transactions")
        # Canonical wire dates let every browser use the same frozen cutoff;
        # this changes only the detached response, never the saved ledger.
        tx["trade_date"] = day.isoformat()
        account_id = str(tx.get("account_db_id") or "")
        if account_id not in accounts:
            _fail("risk_context_unassigned_account")
        if action not in CASH_LEDGER_ACTIONS:
            continue
        quantity, price = risk_history._number(tx.get("quantity")), risk_history._number(tx.get("price"))
        if quantity is None or price is None or quantity < 0 or price < 0:
            _fail("risk_context_invalid_cash_transaction")
        delta = _cash_delta(tx)
        if not math.isfinite(delta):
            _fail("risk_context_invalid_cash_transaction")
        if delta and tx.get("currency") != accounts[account_id]["currency"]:
            _fail("risk_context_mixed_cash_currencies")
        balances[account_id] += delta
        if not math.isfinite(balances[account_id]):
            _fail("risk_context_invalid_cash_transaction")


def create_context(base_currency: str, capture: Callable[[str], dict]) -> dict:
    """Caller holds the shared portfolio/store locks through capture and copy."""
    if not _known_currency(base_currency):
        _fail("risk_context_invalid_currency")
    now = _now()
    try:
        inputs = deepcopy(capture(base_currency))
    except risk_history.RiskHistoryError:
        raise
    except (ValueError, TypeError, OverflowError, KeyError):
        # Legacy canonical cash arithmetic may fail before stricter validation.
        _fail("risk_context_incomplete_values")
    _validate(inputs, now)
    return {key: value for key, value in {
        **inputs, "observed_at": now.isoformat().replace("+00:00", "Z"),
        "date": now.astimezone(ZoneInfo("Asia/Jerusalem")).date().isoformat(),
        "source": "saved_evidence",
    }.items() if key != "guard"}
