"""Read-only correlations of held securities using saved, date-aligned returns."""
from __future__ import annotations

from datetime import date, timedelta
from math import fsum, isfinite, sqrt

MIN_OBSERVATIONS = 30
MAX_ASSETS = 60
PERIOD_DAYS = {"3m": 92, "1y": 365, "3y": 1096}


def _positive(value):
    try:
        number = float(value)
        return number if isfinite(number) and number > 0 else None
    except (ValueError, TypeError):
        return None


def _returns(prices):
    ordered = sorted(prices.items())
    # Match BOTH endpoints, so a multi-day return never meets a one-day return.
    # Gaps over a week indicate sparse history, not a daily market series.
    return {
        (before, after): prices[after] / prices[before] - 1
        for (before, _), (after, _) in zip(ordered, ordered[1:])
        if (after - before).days <= 7
    }


def _pair(left, right):
    intervals = sorted(left.keys() & right.keys())
    result = {"value": None, "observations": len(intervals), "status": "insufficient_history",
              "from": intervals[0][0].isoformat() if intervals else None,
              "to": intervals[-1][1].isoformat() if intervals else None}
    if len(intervals) < MIN_OBSERVATIONS:
        return result
    x, y = [left[key] for key in intervals], [right[key] for key in intervals]
    mx, my = fsum(x) / len(x), fsum(y) / len(y)
    dx, dy = [value - mx for value in x], [value - my for value in y]
    xx, yy = fsum(value * value for value in dx), fsum(value * value for value in dy)
    if xx <= 1e-24 or yy <= 1e-24:
        result["status"] = "constant_returns"
        return result
    value = fsum(a * b for a, b in zip(dx, dy)) / sqrt(xx * yy)
    result.update(value=round(max(-1.0, min(1.0, value)), 6), status="ok")
    return result


def portfolio_correlation(store, market_hub, *, period="1y", account_id="", today=None):
    today = today or date.today()
    start = today - timedelta(days=PERIOD_DAYS[period])
    accounts = store.list_accounts()
    if account_id and account_id not in {row["id"] for row in accounts}:
        raise ValueError("unknown_account")
    listings = {}
    for analysis in store.holdings():
        holding = analysis.holding
        if account_id and holding.account_id != account_id:
            continue
        key = (holding.symbol.strip().upper(), holding.stock_market.strip().upper())
        if abs(holding.quantity) > 1e-9:
            listings.setdefault(key, []).append(holding)
    if len(listings) > MAX_ASSETS:
        return {"status": "too_many_assets", "asset_count": len(listings), "max_assets": MAX_ASSETS,
                "assets": [], "matrix": [], "accounts": accounts}
    assets, returns = [], []
    for (symbol, market), holdings in sorted(listings.items()):
        holding = holdings[0]
        currencies = {str(item.currency or "").strip().upper() for item in holdings}
        currency_conflict = len(currencies) > 1
        currency = next(iter(currencies)) if not currency_conflict else ""
        manual = store.manual_security(symbol, market)
        local = store.price_history(symbol, market, start, today)
        saved, _status = ([], {}) if manual and not manual.get("secondary_symbol") else market_hub.cached_prices(
            symbol, start, today, stock_market=market,
            secondary_symbol=(manual or {}).get("secondary_symbol") or holding.secondary_symbol,
        )
        # Local prices are raw. If overrides exist, use raw closes for the whole
        # series; mixing their scale with adjusted closes invents false returns.
        adjusted = bool(saved) and not local and all(_positive(row.adjusted_close) for row in saved)
        prices = {row.date: price for row in saved
                  if start <= row.date <= today
                  and (price := _positive(row.adjusted_close if adjusted else row.close)) is not None}
        for row in local:
            day = date.fromisoformat(row["price_date"])
            if start <= day <= today and (price := _positive(row["price"])) is not None:
                prices[day] = price
        returns.append({} if currency_conflict else _returns(prices))
        assets.append({"symbol": symbol, "stock_market": market, "currency": currency,
                       "currency_conflict": currency_conflict,
                       "name": holding.name, "basis": "adjusted_close" if adjusted else "close",
                       "source": "merged" if saved and local else "local" if local else "cached" if saved else "missing",
                       "price_count": len(prices), "from": min(prices).isoformat() if prices else None,
                       "to": max(prices).isoformat() if prices else None})
    matrix = [[None] * len(assets) for _ in assets]
    for i, left in enumerate(returns):
        for j in range(i, len(returns)):
            matrix[i][j] = matrix[j][i] = _pair(left, returns[j])
            if assets[i]["currency_conflict"] or assets[j]["currency_conflict"]:
                matrix[i][j]["status"] = "currency_conflict"
    usable = sum(cell["value"] is not None for i, row in enumerate(matrix) for cell in row[i + 1:])
    pair_count = len(assets) * (len(assets) - 1) // 2
    return {"status": "ok" if pair_count and usable == pair_count else "partial" if usable else "unavailable",
            "period": period, "from": start.isoformat(), "to": today.isoformat(),
            "min_observations": MIN_OBSERVATIONS, "max_assets": MAX_ASSETS,
            "asset_count": len(assets), "usable_pairs": usable, "pair_count": pair_count,
            "assets": assets, "matrix": matrix, "accounts": accounts}
