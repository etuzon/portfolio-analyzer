"""Read-only position episodes reconstructed from the recorded, normalized ledger.

Rates are monetary amounts per calendar day/year, never percentage returns.
No provider, fallback quote, or inferred acquisition date is used here.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
import math
from typing import Any


EPSILON = 1e-9
CASH_ACTIONS = {"DIVIDEND", "INTEREST", "FEE"}
SAFE_FIELDS = ("id", "action", "trade_date", "quantity", "price", "price_input", "currency", "asset_class", "source")


def _position_asset_class(value: Any) -> str:
    asset_class = str(value or "").upper().strip()
    # RSU describes how stock was acquired, not a different underlying
    # instrument. Defining the stock later also normalizes STOCK to EQUITY.
    return "EQUITY" if asset_class in {"STOCK", "EQUITY", "RSU"} else asset_class


def _day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _safe_tx(tx: dict[str, Any], quantity: float | None = None) -> dict[str, Any]:
    result = {key: tx.get(key) for key in SAFE_FIELDS}
    result["trade_date"] = _day(tx.get("trade_date")).isoformat() if _day(tx.get("trade_date")) else None
    for key in ("quantity", "price", "price_input"):
        result[key] = _number(tx.get(key))
    if quantity is not None:
        result["allocated_quantity"] = quantity
    return result


def _snapshot(tx: dict[str, Any]) -> bool:
    # import_external stores a synthetic ADD dated on the sync day. Source
    # orders use the same source key, so source alone cannot identify snapshots.
    return (
        str(tx.get("source") or "").lower().endswith("_import")
        and tx.get("action") == "ADD"
        and str(tx.get("comments") or "").startswith("Imported quantity ")
    )


def build_trade_history(
    transactions: list[dict[str, Any]],
    accounts: dict[str, dict[str, Any]],
    prices: list[dict[str, Any]],
    as_of_date: Any = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return episodes; input account keys already represent authorized scope."""
    as_of = _day(as_of_date) if as_of_date is not None else date.today()
    if as_of is None:
        raise ValueError("Invalid as_of_date; expected YYYY-MM-DD")
    filters = filters or {}
    status = str(filters.get("status") or "all").lower()
    if status not in {"all", "open", "closed"}:
        raise ValueError("Invalid trade history status")
    # A transaction saved before its manual instrument was defined retains a
    # blank security_id. Resolve that legacy reference only when the recorded
    # identity is unambiguous; never merge two explicit instrument IDs merely
    # because they share a symbol.
    scoped: list[tuple[tuple[str, ...], str, dict[str, Any]]] = []
    security_ids: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for tx in transactions:
        if tx.get("account_db_id") not in accounts:
            continue
        trade_day = _day(tx.get("trade_date"))
        if trade_day and trade_day > as_of:
            continue
        position_key = (*tuple(str(tx.get(field) or "") for field in (
            "account_db_id", "symbol", "stock_market", "currency"
        )), _position_asset_class(tx.get("asset_class")))
        security_id = str(tx.get("security_id") or "").strip()
        scoped.append((position_key, security_id, tx))
        if security_id:
            security_ids[position_key].add(security_id)

    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    ambiguous_identities: set[tuple[str, ...]] = set()
    for position_key, security_id, tx in scoped:
        candidates = security_ids[position_key]
        if not security_id and len(candidates) == 1:
            security_id = next(iter(candidates))
        key = (*position_key, security_id)
        if not security_id and len(candidates) > 1:
            ambiguous_identities.add(key)
        grouped[key].append(tx)

    price_index: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for price in prices:
        price_day = _day(price.get("price_date"))
        value = _number(price.get("price"))
        if price_day and price_day <= as_of and value is not None and value >= 0:
            key = (*tuple(str(price.get(field) or "") for field in ("symbol", "stock_market", "currency")),
                   _position_asset_class(price.get("asset_class")))
            price_index[key].append(price)

    items: list[dict[str, Any]] = []
    unallocated: list[dict[str, Any]] = []
    report_issues: set[str] = set()
    for key, records in sorted(grouped.items()):
        records.sort(key=lambda tx: (str(tx.get("trade_date") or ""), str(tx.get("created_at") or ""), str(tx.get("id") or "")))
        account_id, symbol, market, currency, asset_class, security_id = key
        episode: dict[str, Any] | None = None
        episode_count = 0
        ledger_incomplete = key in ambiguous_identities

        def orphan(tx: dict[str, Any], issue: str) -> None:
            unallocated.append({**_safe_tx(tx), "account_id": account_id, "symbol": symbol, "stock_market": market, "issues": [issue]})
            report_issues.add(issue)

        def start(tx: dict[str, Any], side: str) -> dict[str, Any]:
            nonlocal episode_count
            episode_count += 1
            opened = _day(tx.get("trade_date"))
            issues: set[str] = set()
            if ledger_incomplete:
                issues.add("incomplete_cost_basis")
            if _snapshot(tx):
                opened = None
                issues.add("imported_position_date_unknown")
                if str(tx.get("comments") or "").startswith("Imported quantity -"):
                    # Legacy snapshot import represented short quantities as
                    # positive ADDs; their economics cannot be reconstructed.
                    issues.add("incomplete_cost_basis")
            if opened is None:
                issues.add("opening_date_unknown")
            instrument = str(tx.get("instrument_type") or asset_class).upper()
            if instrument in {"EMPLOYEE_STOCK_OPTION", "OPTION", "STOCK_OPTION", "FUTURE"}:
                issues.add("unsupported_instrument")
            return {
                "id": f"{tx.get('id')}:{side}", "account_id": account_id,
                "account_label": accounts[account_id].get("label") or account_id,
                "symbol": symbol, "name": tx.get("security_name") or symbol,
                "stock_market": market, "currency": currency, "asset_class": asset_class,
                "security_id": security_id, "side": side, "status": "open",
                "opened_date": opened.isoformat() if opened else None, "closed_date": None,
                "quantity_remaining": 0.0, "cost_basis_remaining": 0.0,
                "realized_trading_profit": 0.0, "income": 0.0, "fees": 0.0,
                "transactions": [], "_issues": issues, "_first_recorded_date": _day(tx.get("trade_date")),
                "_secondary_symbol": tx.get("secondary_symbol") or "",
            }

        def finish(current: dict[str, Any]) -> None:
            issues = current.pop("_issues")
            opened = _day(current["opened_date"])
            closed = _day(current["closed_date"])
            first_recorded = current.pop("_first_recorded_date")
            secondary = current.pop("_secondary_symbol")
            current.update({"latest_price": None, "valuation_date": None, "valuation_age_days": None, "market_value": None})
            unrealized: float | None = 0.0 if current["status"] == "closed" else None
            if current["status"] == "open":
                quotes = []
                for alias in {symbol, secondary} - {""}:
                    quotes.extend(price_index.get((alias, market, currency, asset_class), []))
                quotes = [row for row in quotes if first_recorded is None or _day(row["price_date"]) >= first_recorded]
                if quotes:
                    quote = max(quotes, key=lambda row: (row["price_date"], row["symbol"] == symbol, str(row.get("id") or "")))
                    latest = float(quote["price"])
                    quote_day = _day(quote["price_date"])
                    market_value = current["quantity_remaining"] * latest
                    current.update({"latest_price": latest, "valuation_date": quote_day.isoformat(), "valuation_age_days": (as_of - quote_day).days, "market_value": market_value})
                    unrealized = market_value - current["cost_basis_remaining"]
                    if quote_day < as_of:
                        issues.add("valuation_before_as_of")
                else:
                    issues.add("missing_valuation")
            realized = current["realized_trading_profit"] + current["income"] - current["fees"]
            incomplete = bool(issues & {"unsupported_instrument", "incomplete_cost_basis", "transfer_without_profit"})
            current["realized_profit"] = realized
            current["unrealized_profit"] = unrealized if not incomplete else None
            current["total_profit"] = realized + unrealized if unrealized is not None and not incomplete else None
            duration = ((closed or as_of) - opened).days if opened and (current["status"] == "open" or closed) else None
            if "trade_date_unknown" in issues:
                duration = None
            current["duration_days"] = duration
            if duration == 0:
                issues.add("zero_duration")
            total = current["total_profit"]
            current["profit_per_day"] = total / duration if total is not None and duration and duration > 0 else None
            current["profit_per_year"] = current["profit_per_day"] * 365 if current["profit_per_day"] is not None else None
            if issues & {"unsupported_instrument", "incomplete_cost_basis"}:
                current["realized_trading_profit"] = None
                current["realized_profit"] = None
            for field, value in current.items():
                if isinstance(value, float) and not math.isfinite(value):
                    current[field] = None
                    issues.add("incomplete_cost_basis")
            current["issues"] = sorted(issues)
            if status == "all" or current["status"] == status:
                items.append(current)

        for tx in records:
            action = str(tx.get("action") or "").upper()
            quantity, price = _number(tx.get("quantity")), _number(tx.get("price"))
            if (quantity is None or quantity <= 0 or price is None or price < 0
                    or not math.isfinite(quantity * price)
                    or (episode is not None and not math.isfinite(abs(episode["quantity_remaining"]) + quantity))):
                orphan(tx, "invalid_transaction")
                ledger_incomplete = True
                if episode:
                    episode["_issues"].add("incomplete_cost_basis")
                continue
            if action in CASH_ACTIONS:
                if episode is None:
                    orphan(tx, "unallocated_cash_entry")
                elif episode_count > 1 or not _day(tx.get("trade_date")):
                    orphan(tx, "ambiguous_cash_allocation")
                    episode["_issues"].add("ambiguous_cash_allocation")
                else:
                    episode["transactions"].append(_safe_tx(tx))
                    episode["fees" if action == "FEE" else "income"] += quantity * price
                continue
            if action not in {"ADD", "BUY", "SELL", "SHORT", "REMOVE"}:
                orphan(tx, "unsupported_action")
                ledger_incomplete = True
                if episode:
                    episode["_issues"].add("incomplete_cost_basis")
                continue
            if episode is None:
                if action == "REMOVE":
                    orphan(tx, "transfer_without_position")
                    continue
                episode = start(tx, "short" if action in {"SELL", "SHORT"} else "long")
                if action == "SELL":
                    episode["_issues"].add("incomplete_cost_basis")
            if not _day(tx.get("trade_date")):
                episode["_issues"].add("trade_date_unknown")
            remaining = episode["quantity_remaining"]
            increasing = (remaining >= 0 and action in {"ADD", "BUY"}) or (remaining <= 0 and action == "SHORT")
            if remaining == 0:
                increasing = True
            if increasing:
                signed = -quantity if episode["side"] == "short" else quantity
                episode["quantity_remaining"] += signed
                episode["cost_basis_remaining"] += signed * price
                episode["transactions"].append(_safe_tx(tx))
            else:
                released = min(quantity, abs(remaining))
                average = abs(episode["cost_basis_remaining"] / remaining)
                if action == "REMOVE":
                    episode["_issues"].add("transfer_without_profit")
                elif action in {"SELL", "BUY"}:
                    episode["realized_trading_profit"] += released * ((price - average) if remaining > 0 else (average - price))
                else:
                    episode["_issues"].add("incomplete_cost_basis")
                direction = 1 if remaining > 0 else -1
                episode["quantity_remaining"] -= direction * released
                episode["cost_basis_remaining"] -= direction * released * average
                episode["transactions"].append(_safe_tx(tx, released))
                if quantity > released + EPSILON:
                    episode["_issues"].add("incomplete_cost_basis")
                    orphan({**tx, "quantity": quantity - released}, "excess_closing_quantity")
            if abs(episode["quantity_remaining"]) <= EPSILON:
                episode["quantity_remaining"] = 0.0
                episode["cost_basis_remaining"] = 0.0
                episode["status"] = "closed"
                closing = _day(tx.get("trade_date"))
                episode["closed_date"] = closing.isoformat() if closing else None
                finish(episode)
                episode = None
        if episode:
            finish(episode)

    items.sort(key=lambda item: (item["opened_date"] or "", item["account_label"], item["symbol"], item["id"]), reverse=True)
    return {"as_of_date": as_of.isoformat(), "cost_basis_method": "average_cost", "items": items,
            "issues": sorted(report_issues), "unallocated_transactions": unallocated}
