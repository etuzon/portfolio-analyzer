"""Historical 30-calendar-day portfolio loss in ILS, with joint price/FX shocks.

This module only reads saved evidence. Current signed positions and account cash
are held fixed; no independent asset VaRs or current-rate historical conversions
are substituted for the jointly observed monthly scenarios.
"""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
import math
import re

from .local_portfolio import _cash_delta
from .optimization_data import _history
from .investment_scope import investments

PERIOD_DAYS = {"1y": 365, "3y": 1096, "5y": 1827}
HORIZON_DAYS = 30
CONFIDENCE = .95
MIN_SAMPLES = 100
MAX_ASSETS = 100
SUPPORTED_ASSETS = {"EQUITY", "STOCK", "RSU", "ETF", "MUTUALFUND", "BOND"}
CASH_ACTIONS = {"BUY", "SELL", "SHORT", "DIVIDEND", "INTEREST", "FEE"}


class VarError(ValueError):
    """Safe machine-readable input error."""


def _number(value):
    try:
        result = float(value)
        return result if not isinstance(value, bool) and math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _sum(values):
    try:
        result = math.fsum(values)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _day(value):
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _class(value):
    value = str(value or "").upper().strip()
    return "EQUITY" if value in {"EQUITY", "STOCK", "RSU"} else value


def _label(account):
    return " · ".join(str(account.get(key) or "").strip() for key in
                      ("management_company", "username", "account_id") if account.get(key)) or str(account.get("id") or "")


def loss_statistics(losses):
    """Empirical inverted-CDF VaR and exact worst-5%-probability average loss."""
    if not isinstance(losses, (list, tuple)) or not losses:
        raise VarError("var_invalid_scenarios")
    numbers = [_number(value) for value in losses]
    if any(value is None for value in numbers):
        raise VarError("var_invalid_scenarios")
    ordered = sorted(numbers)
    n = len(ordered)
    quantile = ordered[max(0, math.ceil(CONFIDENCE * n) - 1)]
    # Use rational 5/100 so exact multiples are not perturbed by (1-.95).
    tail_size = n / 20
    whole = math.floor(tail_size)
    fraction = tail_size - whole
    descending = ordered[::-1]
    terms = [value / tail_size for value in descending[:whole]]
    if fraction:
        terms.append(descending[whole] * (fraction / tail_size))
    shortfall = _sum(terms)
    if shortfall is None:
        raise VarError("var_invalid_scenarios")
    return {"var_ils": max(0.0, quantile), "expected_shortfall_ils": max(0.0, shortfall),
            "raw_var_ils": quantile, "raw_expected_shortfall_ils": shortfall}


def _fx_history(currency, snapshots, start, today):
    snapshot = snapshots.get(currency)
    meta = {"currency": currency, "pair": currency + "/ILS", "source": None, "count": 0,
            "from": None, "to": None, "current_rate": None, "current_date": None, "status": "missing_fx_history"}
    if not isinstance(snapshot, dict):
        return {}, meta
    rows = snapshot.get("rates")
    if snapshot.get("currency") != currency or not isinstance(rows, list) or not isinstance(snapshot.get("source"), str) or not snapshot["source"].strip():
        meta["status"] = "invalid_fx_history"
        return {}, meta
    values, invalid = {}, False
    for row in rows:
        if not isinstance(row, dict):
            invalid = True
            continue
        day, rate = _day(row.get("date")), _number(row.get("rate"))
        if day is None or rate is None or rate <= 0:
            invalid = True
            continue
        if day > today or day < start:
            continue
        if day in values and values[day] != rate:
            invalid = True
        values[day] = rate
    meta.update(source=str(snapshot["source"]), updated_at=snapshot.get("updated_at") if isinstance(snapshot.get("updated_at"), str) else None, count=len(values))
    if values:
        latest = max(values)
        meta.update(**{"from": min(values).isoformat(), "to": latest.isoformat()},
                    current_rate=values[latest], current_date=latest.isoformat(),
                    status="stale_fx" if (today - latest).days > 7 else "ok")
    if invalid:
        meta["status"] = "invalid_fx_history"
    return values, meta


def build_var(store, market_hub, fx_histories, *, account_id="", period="3y", today=None):
    store = investments(store)
    today = today or date.today()
    if not isinstance(today, date):
        raise VarError("var_invalid_date")
    if not isinstance(period, str) or period not in PERIOD_DAYS:
        raise VarError("var_invalid_period")
    if not isinstance(fx_histories, dict):
        raise VarError("var_invalid_fx_history")
    accounts = store.list_accounts()
    if not isinstance(account_id, str) or account_id and account_id not in {row["id"] for row in accounts}:
        raise VarError("var_unknown_account")
    selected_accounts = {row["id"]: row for row in accounts if not account_id or row["id"] == account_id}
    start = today - timedelta(days=PERIOD_DAYS[period])
    result = {"status": "unavailable", "reason": "coverage_incomplete", "confidence": CONFIDENCE,
              "horizon_days": HORIZON_DAYS, "currency": "ILS", "var_ils": None,
              "expected_shortfall_ils": None, "var_without_fx_ils": None, "portfolio_value_ils": None,
              "sample_count": 0, "min_samples": MIN_SAMPLES, "from": None, "to": None,
              "valuation_date": None, "as_of": today.isoformat(), "requested_from": start.isoformat(),
              "requested_to": today.isoformat(), "period": period, "account_id": account_id,
              "accounts": [{key: str(row.get(key) or "") for key in ("id", "account_id", "username", "management_company", "currency", "type", "location")} for row in accounts],
              "assets": [], "cash": [], "fx": [], "issues": [], "warnings": [],
              "scenarios": [], "currency_exposures": [], "basis": None, "scope_complete": False}
    issues, warnings = result["issues"], result["warnings"]

    def issue(code, **context):
        value = {"code": code, **context}
        if value not in issues:
            issues.append(value)

    # Keep the established ledger cash model. A cross-currency trade cannot
    # establish its account-currency cash amount without conversion evidence.
    cash_parts, invalid_cash_accounts = {}, set()
    for aid, account in selected_accounts.items():
        amount = _number(account.get("initial_cash", 0))
        cash_parts[aid] = [amount] if amount is not None else []
        if amount is None:
            issue("invalid_cash", account_id=aid)
            invalid_cash_accounts.add(aid)
    for tx in store.list_transactions():
        aid = str(tx.get("account_db_id") or "")
        if aid not in selected_accounts:
            continue
        action = str(tx.get("action") or "").upper()
        if (day := _day(tx.get("trade_date"))) is not None and day > today:
            issue("future_transaction", account_id=aid)
            if action in CASH_ACTIONS:
                invalid_cash_accounts.add(aid)
        if action not in CASH_ACTIONS:
            continue
        account_currency = str(selected_accounts[aid].get("currency") or "").upper()
        if str(tx.get("currency") or "").upper() != account_currency:
            issue("cash_currency_mismatch", account_id=aid, currency=account_currency)
            invalid_cash_accounts.add(aid)
            continue
        try:
            delta = _number(_cash_delta({**tx, "action": action}))
        except (KeyError, TypeError, ValueError, OverflowError):
            delta = None
        if delta is None:
            issue("invalid_cash", account_id=aid)
            invalid_cash_accounts.add(aid)
        else:
            cash_parts[aid].append(delta)
    for aid, account in selected_accounts.items():
        amount = _sum(cash_parts[aid]) if aid not in invalid_cash_accounts else None
        currency = str(account.get("currency") or "").upper().strip()
        if amount is None or not re.fullmatch(r"[A-Z]{3}", currency):
            issue("invalid_cash", account_id=aid)
            amount = None
        result["cash"].append({"account_id": aid, "account_label": _label(account), "currency": currency,
                               "amount": amount, "value_ils": None, "fx_date": None})

    groups, listing_currencies, listing_classes = {}, {}, {}
    for analysis in store.holdings():
        holding = analysis.holding
        if holding.account_id not in selected_accounts:
            continue
        symbol, market = str(holding.symbol or "").upper().strip(), str(holding.stock_market or "").upper().strip()
        currency, asset_class = str(holding.currency or "").upper().strip(), _class(holding.asset_class)
        quantity = _number(holding.quantity)
        if quantity == 0:
            continue
        key = symbol, market, currency, asset_class
        listing_currencies.setdefault((symbol, market), set()).add(currency)
        listing_classes.setdefault((symbol, market), set()).add(asset_class)
        groups.setdefault(key, []).append(holding)
        if quantity is None:
            issue("invalid_position", symbol=symbol, account_id=holding.account_id)
    for fund in store.list_funds():
        if str(fund.get("account_id") or "") in selected_accounts:
            amount = _number(fund.get("amount"))
            if amount is None or amount != 0:
                issue("unsupported_fund", account_id=str(fund.get("account_id") or ""), symbol=str(fund.get("fund_name") or fund.get("id") or ""))

    histories = {}
    if len(groups) > MAX_ASSETS:
        issue("too_many_assets")
    for key, holdings in sorted(groups.items()):
        symbol, market, currency, asset_class = key
        quantity = _sum(_number(row.quantity) for row in holdings)
        aid = sha256(repr(key).encode()).hexdigest()[:20]
        asset = {"id": aid, "symbol": symbol, "name": str(holdings[0].name or symbol), "stock_market": market,
                 "currency": currency, "asset_class": asset_class, "quantity": quantity,
                 "account_ids": sorted({row.account_id for row in holdings}), "status": "ok", "value_ils": None,
                 "current_price": None, "current_price_date": None, "current_fx": None, "current_fx_date": None,
                 "secondary_symbol": str(holdings[0].secondary_symbol or ""), "price_count": 0}
        result["assets"].append(asset)
        code = None
        if quantity is None or not symbol or not market or not re.fullmatch(r"[A-Z]{3}", currency):
            code = "invalid_position"
        elif asset_class not in SUPPORTED_ASSETS:
            code = "unsupported_asset"
        elif len(listing_currencies[(symbol, market)]) > 1:
            code = "currency_conflict"
        elif len(listing_classes[(symbol, market)]) > 1:
            code = "classification_conflict"
        elif len(groups) > MAX_ASSETS:
            code = "too_many_assets"
        if code:
            asset["status"] = code
            issue(code, symbol=symbol)
            continue
        raw, adjusted = _history(store, market_hub, asset, start, today)
        # _history's optimizer-specific weekly eligibility does not apply here.
        asset.pop("eligible", None)
        asset["status"] = "ok"
        histories[aid] = raw, adjusted
        if not raw:
            asset["status"] = "missing_price_history"
            issue("missing_price_history", symbol=symbol)
            continue
        latest = max(raw)
        asset.update(current_price=raw[latest], current_price_date=latest.isoformat())
        if (today - latest).days > 7:
            asset["status"] = "stale_price"
            issue("stale_price", symbol=symbol)

    required_currencies = {row["currency"] for row in result["assets"] if row["quantity"] != 0}
    required_currencies.update(row["currency"] for row in result["cash"] if row["amount"] not in (None, 0))
    required_currencies.discard("ILS")
    fx_series, fx_meta = {}, {}
    for currency in sorted(required_currencies):
        values, meta = _fx_history(currency, fx_histories, start, today)
        fx_series[currency], fx_meta[currency] = values, meta
        result["fx"].append(meta)
        if meta["status"] != "ok":
            issue(meta["status"], currency=currency)

    def current_fx(currency):
        return (1.0, today.isoformat()) if currency == "ILS" else (fx_meta.get(currency, {}).get("current_rate"), fx_meta.get(currency, {}).get("current_date"))

    exposure_parts = {}
    valuation_dates = []
    for asset in result["assets"]:
        rate, stamp = current_fx(asset["currency"])
        asset.update(current_fx=rate, current_fx_date=stamp)
        if asset["quantity"] is None or asset["current_price"] is None or rate is None:
            continue
        value = _number(asset["quantity"] * asset["current_price"] * rate)
        if value is None:
            asset["status"] = "invalid_valuation"
            issue("invalid_valuation", symbol=asset["symbol"])
            continue
        asset["value_ils"] = value
        exposure_parts.setdefault(asset["currency"], []).append(value)
        valuation_dates.extend([asset["current_price_date"], stamp])
    for row in result["cash"]:
        rate, stamp = current_fx(row["currency"])
        row["fx_date"] = stamp
        if row["amount"] == 0:
            row["value_ils"] = 0.0
        elif row["amount"] is not None and rate is not None:
            row["value_ils"] = _number(row["amount"] * rate)
            if row["value_ils"] is None:
                issue("invalid_valuation", account_id=row["account_id"])
        if row["value_ils"] is not None:
            exposure_parts.setdefault(row["currency"], []).append(row["value_ils"])
            if row["amount"] != 0:
                valuation_dates.append(stamp)
    for currency, values in sorted(exposure_parts.items()):
        value = _sum(values)
        if value is None:
            issue("invalid_valuation", currency=currency)
        result["currency_exposures"].append({"currency": currency, "value_ils": value})
    if issues:
        return result
    total = _sum(row["value_ils"] for row in result["currency_exposures"])
    if total is None:
        issue("invalid_valuation")
        return result
    result.update(portfolio_value_ils=total, valuation_date=min(valuation_dates) if valuation_dates else today.isoformat(), scope_complete=True)
    if total <= 0:
        warnings.append("nonpositive_equity")
    if not result["assets"] and not required_currencies:
        result.update(status="empty" if not any(row["amount"] for row in result["cash"]) else "ok", reason=None,
                      var_ils=0.0, expected_shortfall_ils=0.0, var_without_fx_ils=0.0,
                      raw_var_ils=0.0, raw_expected_shortfall_ils=0.0, basis="nominal_cash")
        if result["status"] == "ok":
            warnings.append("nominal_ils_cash_only")
        return result

    adjusted = bool(result["assets"]) and all(row.get("adjusted_available") for row in result["assets"])
    result["basis"] = "adjusted_close" if adjusted else "close"
    if result["assets"] and not adjusted:
        warnings.append("unadjusted_prices")
    price_series = {row["id"]: histories[row["id"]][1 if adjusted else 0] for row in result["assets"]}
    series = list(price_series.values()) + list(fx_series.values())
    common = set.intersection(*(set(values) for values in series))
    pairs = [(end - timedelta(days=HORIZON_DAYS), end) for end in sorted(common)
             if end - timedelta(days=HORIZON_DAYS) in common]
    result.update(sample_count=len(pairs), **{"from": pairs[0][0].isoformat() if pairs else None,
                                           "to": pairs[-1][1].isoformat() if pairs else None})
    if len(pairs) < MIN_SAMPLES:
        result["reason"] = "insufficient_monthly_history"
        return result
    if (today - pairs[-1][1]).days > 14:
        issue("stale_monthly_history")
        result.update(reason="coverage_incomplete", scope_complete=False)
        return result
    warnings.append("overlapping_scenarios")
    if len(pairs) < 250:
        warnings.append("limited_history")
    if fx_series:
        warnings.append("fx_fixing_times")
    if any(len(set(values.values())) == 1 for values in price_series.values()):
        warnings.append("constant_asset_history")
    for before, after in pairs:
        pnl_parts, price_parts = [], []
        for asset in result["assets"]:
            prices = price_series[asset["id"]]
            price_ratio = prices[after] / prices[before]
            fx_ratio = 1.0 if asset["currency"] == "ILS" else fx_series[asset["currency"]][after] / fx_series[asset["currency"]][before]
            pnl_parts.append(asset["value_ils"] * (price_ratio * fx_ratio - 1))
            price_parts.append(asset["value_ils"] * (price_ratio - 1))
        for row in result["cash"]:
            if row["currency"] != "ILS" and row["amount"] != 0:
                fx_values = fx_series[row["currency"]]
                pnl_parts.append(row["value_ils"] * (fx_values[after] / fx_values[before] - 1))
        pnl, price_pnl = _sum(pnl_parts), _sum(price_parts)
        if pnl is None or price_pnl is None:
            result.update(reason="invalid_scenarios", scenarios=[])
            return result
        result["scenarios"].append({"from": before.isoformat(), "to": after.isoformat(), "pnl_ils": pnl,
                                    "loss_ils": -pnl, "price_only_loss_ils": -price_pnl})
    statistics = loss_statistics([row["loss_ils"] for row in result["scenarios"]])
    price_statistics = loss_statistics([row["price_only_loss_ils"] for row in result["scenarios"]])
    result.update(status="ok", reason=None, **statistics, var_without_fx_ils=price_statistics["var_ils"])
    if statistics["raw_var_ils"] <= 0:
        warnings.append("no_observed_tail_loss")
    return result
