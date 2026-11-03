"""Read-only mean–variance inputs from qualified, jointly dated price evidence."""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
import math

import numpy as np

from .optimization import OptimizationError, solve_portfolio, portfolio_metrics

PERIODS = {"1y": 365, "3y": 1096, "5y": 1827}
MIN_OBSERVATIONS = 26
MAX_ASSETS = 30
ANNUALIZATION = 52
ALLOWED_ASSETS = {"EQUITY", "ETF", "MUTUALFUND", "RSU", "STOCK"}
US_MARKETS = {"US", "NYSE", "NASDAQ", "NYSEARCA", "AMEX", "OTC"}
IL_MARKETS = {"TASE", "TLV", "TELAVIV"}


def _positive(value):
    try:
        number = float(value)
        return number if not isinstance(value, bool) and math.isfinite(number) and number > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _percent(value, default, *, low=-10000, high=10000):
    value = default if value is None else value
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise OptimizationError("optimization_invalid_assumptions")
    return float(value)


def _scope(store, account_id, period):
    if not isinstance(period, str) or period not in PERIODS:
        raise OptimizationError("optimization_invalid_period")
    accounts = store.list_accounts()
    if not isinstance(account_id, str) or account_id and account_id not in {row["id"] for row in accounts}:
        raise OptimizationError("optimization_unknown_account")
    return accounts


def _class(value):
    return "EQUITY" if value in {"STOCK", "RSU", "EQUITY"} else value


def _finite_total(values):
    try:
        total = math.fsum(values)
        return total if math.isfinite(total) else None
    except (ValueError, OverflowError):
        return None


def _universe(store, account_id):
    groups, excluded = {}, []
    for analysis in store.holdings():
        holding = analysis.holding
        if account_id and holding.account_id != account_id:
            continue
        if not math.isfinite(holding.quantity):
            excluded.append({"symbol": holding.symbol, "stock_market": holding.stock_market, "reason": "invalid_position"})
            continue
        if holding.quantity <= 0:
            excluded.append({"symbol": holding.symbol, "stock_market": holding.stock_market, "reason": "short_position"})
            continue
        if holding.asset_class not in ALLOWED_ASSETS:
            excluded.append({"symbol": holding.symbol, "stock_market": holding.stock_market, "reason": "unsupported_asset"})
            continue
        key = holding.symbol.strip().upper(), holding.stock_market.strip().upper()
        groups.setdefault(key, []).append(holding)
    assets = []
    for (symbol, market), holdings in sorted(groups.items()):
        quantity = _finite_total(row.quantity for row in holdings)
        if quantity is None:
            excluded.append({"symbol": symbol, "stock_market": market, "reason": "invalid_position"})
            continue
        currencies = {str(row.currency or "").strip().upper() for row in holdings}
        classes = {_class(row.asset_class) for row in holdings}
        asset = {"id": sha256(repr((symbol, market)).encode()).hexdigest()[:20], "symbol": symbol,
                 "name": holdings[0].name or symbol, "stock_market": market,
                 "currency": next(iter(currencies)) if len(currencies) == 1 else "",
                 "asset_class": next(iter(classes)) if len(classes) == 1 else "",
                 "quantity": quantity,
                 "secondary_symbol": holdings[0].secondary_symbol,
                 "status": "ok", "eligible": True}
        if len(currencies) != 1 or not asset["currency"]:
            asset.update(status="currency_conflict", eligible=False)
        elif len(classes) != 1:
            asset.update(status="classification_conflict", eligible=False)
        assets.append(asset)
    return assets, excluded


def _history(store, market_hub, asset, start, today):
    symbol, market = asset["symbol"], asset["stock_market"]
    manual = store.manual_security(symbol, market)
    # Cache identity is supported for US/USD and Israeli/ILS listings. Other
    # exchanges require currency-qualified local evidence, never a bare US alias.
    cache_qualified = (market in US_MARKETS and asset["currency"] == "USD") or (market in IL_MARKETS and asset["currency"] == "ILS")
    saved = []
    if cache_qualified and not (manual and not manual.get("secondary_symbol")):
        saved, _ = market_hub.cached_prices(symbol, start, today, stock_market=market,
                                           secondary_symbol=(manual or {}).get("secondary_symbol") or asset["secondary_symbol"])
    raw, adjusted = {}, {}
    for row in saved:
        if start <= row.date <= today and (price := _positive(row.close)) is not None:
            raw[row.date] = price
            if (price := _positive(row.adjusted_close)) is not None:
                adjusted[row.date] = price
    local = {}
    for row in store.price_history(symbol, market, start, today):
        if str(row.get("currency") or "").upper() != asset["currency"] or _class(str(row.get("asset_class") or "").upper()) != asset["asset_class"]:
            continue
        try:
            day = date.fromisoformat(row["price_date"])
        except (TypeError, ValueError, KeyError):
            continue
        if start <= day <= today and (price := _positive(row.get("price"))) is not None:
            local[day] = price
    raw.update(local)
    asset.update(price_count=len(raw), adjusted_available=bool(raw) and not local and raw.keys() == adjusted.keys(),
                 source="merged" if local and saved else "local" if local else "cached" if saved else "missing",
                 basis="adjusted_close" if raw and not local and raw.keys() == adjusted.keys() else "close",
                 **{"from": min(raw).isoformat() if raw else None, "to": max(raw).isoformat() if raw else None})
    if len(raw) < MIN_OBSERVATIONS + 1:
        asset.update(status="insufficient_history", eligible=False)
    return raw, adjusted


def _prepare(store, market_hub, account_id, period, currency, today):
    accounts = _scope(store, account_id, period)
    assets, excluded = _universe(store, account_id)
    currencies = sorted({row["currency"] for row in assets if row["currency"]})
    if not isinstance(currency, str) or currency and currency not in currencies:
        raise OptimizationError("optimization_unknown_currency")
    currency = currency or ("ILS" if "ILS" in currencies else "USD" if "USD" in currencies else currencies[0] if currencies else "")
    start = today - timedelta(days=PERIODS[period])
    history = {}
    for asset in assets:
        if asset["currency"] != currency:
            excluded.append({**asset, "reason": asset["status"] if not asset["eligible"] else "different_currency"})
            continue
        if asset["eligible"]:
            history[asset["id"]] = _history(store, market_hub, asset, start, today)
    shown = [row for row in assets if row["currency"] == currency]
    values = {}
    for row in shown:
        raw = history.get(row["id"], ({}, {}))[0]
        last = max(raw) if raw else None
        row["current_price_date"] = last.isoformat() if last else None
        values[row["id"]] = _positive(raw[last] * row["quantity"]) if last is not None and (today - last).days <= 7 else None
    total = _finite_total(value for value in values.values() if value is not None)
    for row in shown:
        row["current_weight_percent"] = values[row["id"]] / total * 100 if total and values[row["id"]] is not None and all(v is not None for v in values.values()) else None
    payload = {"accounts": accounts, "currencies": currencies, "currency": currency, "period": period,
               "assets": shown, "excluded": excluded, "min_observations": MIN_OBSERVATIONS,
               "max_assets": MAX_ASSETS, "as_of": today.isoformat(), "from": start.isoformat(), "to": today.isoformat()}
    return payload, history, values


def optimization_universe(store, market_hub, *, account_id="", period="3y", currency="", today=None):
    return _prepare(store, market_hub, account_id, period, currency, today or date.today())[0]


def _weekly_panel(histories, today):
    common = set.intersection(*(set(series) for series in histories))
    weeks = {}
    for day in sorted(common):
        if day.weekday() > 4:
            continue
        friday = day + timedelta(days=4 - day.weekday())
        if friday < today:
            weeks[friday] = day
    dates = [weeks[week] for week in sorted(weeks)]
    intervals = [(before, after) for before, after in zip(dates, dates[1:]) if 4 <= (after - before).days <= 10]
    rows = [[series[after] / series[before] - 1 for series in histories] for before, after in intervals]
    return np.asarray(rows, dtype=float), intervals


def optimize_portfolio(store, market_hub, payload, *, today=None):
    if not isinstance(payload, dict):
        raise OptimizationError("optimization_invalid_request")
    today = today or date.today()
    context, histories, values = _prepare(store, market_hub, payload.get("account_id", ""), payload.get("period", "3y"), payload.get("currency", ""), today)
    ids = payload.get("asset_ids")
    if not isinstance(ids, list) or not 2 <= len(ids) <= MAX_ASSETS or any(not isinstance(key, str) for key in ids) or len(ids) != len(set(ids)):
        raise OptimizationError("optimization_invalid_assets")
    universe = {row["id"]: row for row in context["assets"]}
    if any(key not in universe for key in ids):
        raise OptimizationError("optimization_invalid_assets")
    assets = [dict(universe[key]) for key in ids]
    result = {"status": "unavailable", "solution": None, "current": None, "frontier": [], "assets": assets,
              "currency": context["currency"], "annualization": ANNUALIZATION, "observations": 0,
              "from": None, "to": None, "requested_from": context["from"], "requested_to": context["to"],
              "excluded": context["excluded"], "warnings": [], "min_observations": MIN_OBSERVATIONS}
    cap = _percent(payload.get("max_weight_percent"), 100, low=0.000001, high=100) / 100
    risk_free = _percent(payload.get("risk_free_rate_percent"), 0) / 100
    target = payload.get("target_return_percent")
    target = _percent(target, None) / 100 if target is not None else None
    shrinkage = _percent(payload.get("shrinkage_percent"), 10, low=0, high=100) / 100
    objective = payload.get("objective", "min_variance")
    if not isinstance(objective, str) or objective not in {"min_variance", "max_sharpe", "target_return"} or objective == "target_return" and target is None:
        raise OptimizationError("optimization_invalid_objective")
    overrides = payload.get("expected_returns", {})
    if not isinstance(overrides, dict) or any(key not in ids for key in overrides):
        raise OptimizationError("optimization_invalid_assumptions")
    overrides = {key: _percent(value, None) / 100 for key, value in overrides.items()}
    if any(not row["eligible"] for row in assets):
        result["reason"] = "ineligible_assets"
        return result
    adjusted = all(row["adjusted_available"] for row in assets)
    basis = "adjusted_close" if adjusted else "close"
    panel, intervals = _weekly_panel([histories[key][1 if adjusted else 0] for key in ids], today)
    result.update(basis=basis, shrinkage_percent=shrinkage * 100, observations=len(intervals),
                  intervals=[{"from": before.isoformat(), "to": after.isoformat()} for before, after in intervals],
                  **{"from": intervals[0][0].isoformat() if intervals else None,
                     "to": intervals[-1][1].isoformat() if intervals else None})
    if len(intervals) < MIN_OBSERVATIONS:
        result["reason"] = "insufficient_common_history"
        return result
    if not np.all(np.isfinite(panel)):
        result["reason"] = "invalid_returns"
        return result
    sample = np.cov(panel, rowvar=False, ddof=1) * ANNUALIZATION
    if np.any(np.diag(sample) <= 1e-14):
        result["reason"] = "constant_returns"
        return result
    covariance = (1 - shrinkage) * sample + shrinkage * np.diag(np.diag(sample))
    mu = np.mean(panel, axis=0) * ANNUALIZATION
    historical = mu.copy()
    for i, key in enumerate(ids):
        mu[i] = overrides.get(key, mu[i])
        assets[i].update(historical_return_percent=float(historical[i] * 100), expected_return_percent=float(mu[i] * 100),
                         basis=basis, current_weight_percent=None)
    if not adjusted:
        result["warnings"].append("unadjusted_prices")
    if len(intervals) < 52:
        result["warnings"].append("limited_history")
    if any((today - date.fromisoformat(row["to"])).days > 7 for row in assets):
        result["warnings"].append("stale_prices")
    if (today - intervals[-1][1]).days > 14:
        result["warnings"].append("stale_common_history")
    total = _finite_total(values[key] for key in ids) if all(values[key] is not None for key in ids) else None
    if total is not None and total > 0:
        weights = np.asarray([values[key] / total for key in ids])
        result["current"] = portfolio_metrics(weights, mu, covariance, risk_free)
        for row, weight in zip(assets, weights):
            row["current_weight_percent"] = float(weight * 100)
    else:
        result["warnings"].append("current_weights_unavailable")
    solved = solve_portfolio(mu, covariance, objective=objective, max_weight=cap, risk_free_rate=risk_free,
                             target_return=target)
    result.update(status=solved["status"], reason=solved.get("reason"), solution=solved.get("selected"),
                  minimum_variance=solved.get("minimum_variance"), frontier=solved.get("frontier", []),
                  feasible_return_range=solved.get("feasible_return_range"), covariance_status=solved.get("covariance_status"))
    if result.get("covariance_status") == "singular":
        result["warnings"].append("singular_covariance")
    result["covariance"] = covariance.tolist()
    return result
