"""Read-only calendar and annual dividend comparisons from retained evidence."""
from __future__ import annotations

from .investment_scope import investments

import calendar
from datetime import date, datetime, timedelta, timezone
from math import fsum, isfinite

EX_DATE_PROVIDERS = {"alpha_vantage", "financial_modeling_prep", "yahoo_finance"}
US_MARKETS = {"NASDAQ", "NYSE", "NYSEARCA", "AMEX", "OTC"}
SUPPORTED = {"EQUITY", "ETF", "MUTUALFUND", "RSU"}


def _date(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _number(value):
    try:
        number = float(value)
        return number if isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _sum(values):
    try:
        total = fsum(values)
        return total if isfinite(total) else None
    except OverflowError:
        return None


def _records(rows, provider, currency):
    grouped, invalid = {}, 0
    for row in rows:
        if not isinstance(row, dict):
            invalid += 1
            continue
        amount = _number(row.get("amount"))
        if amount is None or amount <= 0 or (row.get("currency") and row["currency"] != currency):
            invalid += 1
            continue
        ex = _date(row.get("ex_dividend_date") or row.get("ex_date"))
        if not ex and provider in EX_DATE_PROVIDERS:
            ex = _date(row.get("date"))
        pay = _date(row.get("payment_date") or row.get("paymentDate"))
        reported = _date(row.get("date"))
        shown = pay or ex or reported
        date_type = "payment" if pay else "ex_date" if ex else "provider_date" if reported else "undated"
        basis = ex or pay or reported
        # Same ex-date and amount identify duplicate snapshots, including rows
        # where only one duplicate retains the payment-date metadata.
        key = ((ex or reported or pay).isoformat() if (ex or reported or pay) else "", amount)
        value = {"date": shown.isoformat() if shown else None, "date_type": date_type,
                 "ex_date": ex.isoformat() if ex else None, "payment_date": pay.isoformat() if pay else None,
                 "basis_date": basis.isoformat() if basis else None, "amount_per_share": amount,
                 "yield_amount_per_share": _number(row.get("adjusted_amount")) if (_number(row.get("adjusted_amount")) or 0) > 0 else amount}
        if key not in grouped or (pay and not grouped[key]["payment_date"]):
            grouped[key] = value
    return sorted(grouped.values(), key=lambda row: (row["date"] or "", row["amount_per_share"])), invalid


def build_dividend_calendar(store, market_hub, *, year=None, account_id="", today=None):
    store = investments(store)
    today = today or date.today()
    year = today.year if year is None else year
    if not 1900 <= year <= 2200:
        raise ValueError("invalid_dividend_year")
    accounts = store.list_accounts()
    if account_id and account_id not in {row["id"] for row in accounts}:
        raise ValueError("unknown_dividend_account")
    start = date(today.year - 1, today.month, min(today.day, calendar.monthrange(today.year - 1, today.month)[1]))
    groups, excluded = {}, []
    for analysis in store.holdings():
        h = analysis.holding
        if abs(h.quantity) <= 1e-9 or (account_id and h.account_id != account_id):
            continue
        if h.quantity < 0 or h.asset_class not in SUPPORTED:
            excluded.append({"symbol": h.symbol, "stock_market": h.stock_market,
                             "reason": "short" if h.quantity < 0 else "unsupported"})
            continue
        groups.setdefault((h.symbol.upper(), h.stock_market.upper()), []).append(h)
    cached = market_hub.cached_view()
    transactions = store.list_transactions()
    assets, events = [], []
    years = {today.year + 1, year, *range(today.year - 5, today.year + 1)}
    for (symbol, market), positions in sorted(groups.items()):
        currencies = {h.currency for h in positions}
        currency = positions[0].currency
        conflict = len(currencies) != 1 or not currency
        manual = store.manual_security(symbol, market)
        context = {"stock_market": market, "secondary_symbol": (manual or {}).get("secondary_symbol") or positions[0].secondary_symbol}
        restricted = manual and not manual.get("secondary_symbol")
        saved = {"items": [], "provider": None, "updated_at": None} if restricted else cached.dividend_calendar(symbol, **context)
        if saved["provider"] in EX_DATE_PROVIDERS and market in US_MARKETS and currency != "USD":
            conflict = True
        records, invalid = _records(saved["items"], saved["provider"], currency)
        if conflict:
            records = []
        latest = None if restricted else cached.latest_price(symbol, today - timedelta(days=366 * 5), today, **context)
        by_day = {latest["date"]: latest["close"]} if latest else {}
        invalid_prices = 0
        local_dates = set()
        for row in store.price_history(symbol, market, today - timedelta(days=366 * 5), today):
            if str(row.get("currency") or "").upper() != currency:
                invalid_prices += 1
                continue
            day, price = _date(row.get("price_date")), _number(row.get("price"))
            if day and day <= today and price and price > 0:
                by_day[day] = price
                local_dates.add(day)
        price_date = max(by_day) if by_day and not conflict else None
        price = by_day[price_date] if price_date else None
        basis_dates = [_date(row["basis_date"]) for row in records if row["basis_date"]]
        observed = [row for row in records if row["basis_date"] and start < _date(row["basis_date"]) <= today]
        ttm = _sum(row["yield_amount_per_share"] for row in observed) if observed else None
        annual_yield = ttm / price * 100 if ttm is not None and price else None
        if annual_yield is not None and not isfinite(annual_yield):
            annual_yield = None
        partial = not basis_dates or min(basis_dates) > start or invalid > 0 or any(row["date"] is None for row in records)
        timestamp = _number(saved.get("updated_at"))
        fetched = datetime.fromtimestamp(timestamp, timezone.utc).date() if timestamp else None
        stale_history = not fetched or (today - fetched).days > 30
        stale_price = not price_date or (today - price_date).days > 7
        selected = [row for row in records if row["date"] and _date(row["date"]).year == year]
        yearly = _sum(row["amount_per_share"] for row in selected) if selected else None
        recorded = {}
        ledger_events = []
        account_ids = {h.account_id for h in positions}
        for tx in transactions:
            if tx.get("action") != "DIVIDEND" or tx.get("account_db_id") not in account_ids or str(tx.get("symbol") or "").upper() != symbol or str(tx.get("stock_market") or "").upper() != market:
                continue
            day = _date(tx.get("trade_date"))
            quantity, tx_price = _number(tx.get("quantity")), _number(tx.get("price"))
            amount = quantity * tx_price if quantity is not None and tx_price is not None else None
            if not day or day.year != year or day > today or amount is None or not isfinite(amount) or amount <= 0:
                continue
            tx_currency = str(tx.get("currency") or "")
            if not tx_currency:
                continue
            recorded.setdefault(tx_currency, []).append(amount)
            ledger_events.append({"date": day.isoformat(), "date_type": "ledger", "recorded_amount": amount,
                                  "amount_per_share": None, "currency": tx_currency})
        asset_id = f"{symbol}@{market}"
        asset = {"id": asset_id, "symbol": symbol, "stock_market": market, "name": positions[0].name,
                 "currency": currency if not conflict else None, "currency_conflict": conflict,
                 "year_dividend_per_share": yearly, "year_payment_count": len(selected),
                 "ttm_dividend_per_share": ttm, "annual_yield_percent": annual_yield,
                 "price": price, "price_date": price_date.isoformat() if price_date else None,
                 "price_source": "local" if price_date in local_dates else latest["provider"] if latest and price_date else None,
                 "invalid_prices": invalid_prices,
                 "history_partial": partial, "history_stale": stale_history, "price_stale": stale_price,
                 "source": saved["provider"], "fetched_date": fetched.isoformat() if fetched else None,
                 "history_from": min(basis_dates).isoformat() if basis_dates else None,
                 "history_to": max(basis_dates).isoformat() if basis_dates else None,
                 "invalid_records": invalid, "undated_records": sum(row["date"] is None for row in records),
                 "recorded_income": [{"currency": c, "amount": _sum(a)} for c, a in sorted(recorded.items())],
                 "rankable": annual_yield is not None and not partial and not stale_price and not stale_history and not conflict,
                 "highest_yield": False}
        assets.append(asset)
        for row in records:
            if row["date"]:
                years.add(_date(row["date"]).year)
        # Ledger entries supply known recorded dates only when no provider dates
        # exist for this security/year, avoiding duplicate payment markers.
        for index, row in enumerate(selected or ledger_events):
            events.append({**row, "id": f"{asset_id}:{index}", "asset_id": asset_id,
                           "currency": row.get("currency") or asset["currency"],
                           "future": _date(row["date"]) > today})
    valid = [asset["annual_yield_percent"] for asset in assets if asset["rankable"]]
    maximum = max(valid) if valid else None
    for asset in assets:
        asset["highest_yield"] = bool(asset["rankable"] and abs(asset["annual_yield_percent"] - maximum) < 1e-9)
    events.sort(key=lambda row: (row["date"], row["asset_id"]))
    return {"year": year, "accounts": accounts, "account_id": account_id, "assets": assets, "events": events,
            "available_years": sorted(y for y in years if 1900 <= y <= 2200), "excluded": excluded,
            "ttm_from": start.isoformat(), "ttm_to": today.isoformat(), "highest_yield_percent": maximum}
