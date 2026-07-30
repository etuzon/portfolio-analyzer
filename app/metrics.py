from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import date, timedelta
from statistics import mean
from typing import Any

from .models import Holding, Ohlcv, SymbolAnalysis, Trend
from .providers import MarketDataHub


PERIODS = {
    "1m": 31,
    "1y": 366,
    "3y": 366 * 3,
    "5y": 366 * 5,
}


def analyze_holding(holding: Holding, hub: MarketDataHub) -> SymbolAnalysis:
    today = date.today()
    prices, price_status = hub.prices(holding.symbol, today - timedelta(days=PERIODS["5y"]), today)
    fundamentals, fundamental_status = hub.fundamentals(holding.symbol)
    dividends, dividend_status = hub.dividends(holding.symbol)
    profile, profile_status = hub.profile(holding.symbol)

    if profile.get("name") and (not holding.name or holding.name.upper() == holding.symbol.upper()):
        holding.name = str(profile.get("name") or holding.name)
    industry = profile.get("industry") or holding.industry or holding.sector or ""
    if industry:
        holding.industry = str(industry)
    if profile.get("sector") and not holding.sector:
        holding.sector = str(profile.get("sector") or "")
    if profile.get("exchange") and not holding.stock_market:
        holding.stock_market = str(profile.get("exchange") or "")
    market_cap = profile.get("market_cap")
    if not market_cap and profile.get("shares_outstanding") and prices:
        market_cap = float(profile["shares_outstanding"]) * prices[-1].adjusted_close
    reports = _annual_reports(fundamentals)
    missing = []

    price_ranges = price_range_metrics(prices)
    if not prices:
        missing.append("price history")

    income = trend_from_reports(reports, ["totalRevenue", "revenue"], "income")
    profit = trend_from_reports(reports, ["netIncome", "net_income"], "profit")
    dividend = dividend_trend(dividends)
    profit_market_cap = profit_market_cap_trend(reports, market_cap)

    for label, trend in [("income", income), ("profit", profit), ("dividend", dividend), ("profit/market cap", profit_market_cap)]:
        if trend.state == "missing":
            missing.append(label)
    if not industry:
        missing.append("industry")

    return SymbolAnalysis(
        holding=holding,
        provider_status={
            **_status_group("prices", price_status),
            **_status_group("fundamentals", fundamental_status),
            **_status_group("dividends", dividend_status),
            **_status_group("profile", profile_status),
        },
        price_ranges=price_ranges,
        moving_averages=moving_averages(prices),
        support_resistance=support_resistance(prices),
        volume=volume_metrics(prices),
        income_trend=income,
        profit_trend=profit,
        dividend_trend=dividend,
        profit_market_cap_trend=profit_market_cap,
        industry=industry,
        missing=missing,
        market_cap=market_cap,
    )


def price_range_metrics(prices: list[Ohlcv]) -> dict[str, dict]:
    today = date.today()
    out = {}
    for label, days in PERIODS.items():
        period_start = today - timedelta(days=days)
        subset = [row for row in prices if row.date >= period_start]
        if not subset:
            out[label] = {"state": "missing", "message": "No price data"}
            continue
        high = max(subset, key=lambda row: row.high)
        low = min(subset, key=lambda row: row.low)
        current = subset[-1].adjusted_close
        oldest = subset[0].date
        grace_days = min(45, max(7, int(days * 0.1)))
        state = "partial" if oldest > period_start + timedelta(days=grace_days) else "ok"
        out[label] = {
            "state": state,
            "high": high.high,
            "high_date": high.date.isoformat(),
            "min": low.low,
            "min_date": low.date.isoformat(),
            "current": current,
            "percent_from_high": percent(current, high.high),
            "percent_from_min": percent(current, low.low),
            "message": f"Only from {oldest.isoformat()}" if state == "partial" else "",
        }
    return out


def moving_averages(prices: list[Ohlcv]) -> dict[str, dict]:
    out = {}
    closes = [row.adjusted_close for row in prices]
    current = closes[-1] if closes else None
    for window in [7, 10, 15, 30]:
        if len(closes) < window:
            out[str(window)] = {"state": "missing", "message": f"Need {window} prices"}
            continue
        value = mean(closes[-window:])
        previous = mean(closes[-window - 1 : -1]) if len(closes) > window else value
        out[str(window)] = {
            "state": "ok",
            "value": value,
            "price_vs_ma_percent": percent(current, value),
            "direction": direction(value, previous),
        }
    return out


def volume_metrics(prices: list[Ohlcv]) -> dict:
    if not prices:
        return {"state": "missing", "message": "No volume data"}
    latest = prices[-1].volume
    avg20 = mean([row.volume for row in prices[-20:]]) if len(prices) >= 20 else None
    avg90 = mean([row.volume for row in prices[-90:]]) if len(prices) >= 90 else None
    return {
        "state": "ok" if avg20 else "partial",
        "latest": latest,
        "average_20d": avg20,
        "average_90d": avg90,
        "relative_20d": latest / avg20 if avg20 else None,
        "direction": direction(avg20, avg90) if avg20 and avg90 else "missing",
    }


def support_resistance(prices: list[Ohlcv]) -> dict[str, dict]:
    today = date.today()
    out = {}
    for label, days in PERIODS.items():
        subset = [row for row in prices if row.date >= today - timedelta(days=days)]
        if len(subset) < 10:
            out[label] = {"state": "missing", "message": "Not enough price data"}
            continue
        lows = _local_extrema(subset, "low")
        highs = _local_extrema(subset, "high")
        out[label] = {
            "state": "ok",
            "support": _ranked_level(lows, subset),
            "resistance": _ranked_level(highs, subset),
            "method": "clustered local extrema with volume weighting",
        }
    return out


def trend_from_reports(reports: list[dict[str, Any]], keys: list[str], label: str) -> Trend:
    series = []
    for report in reports:
        value = next((_number(report.get(key)) for key in keys if _number(report.get(key)) is not None), None)
        fiscal_date = report.get("fiscalDateEnding") or report.get("date") or report.get("calendarYear")
        if value is not None and fiscal_date:
            series.append({"date": str(fiscal_date), "value": value})
    series = sorted(series, key=lambda row: row["date"])
    if len(series) < 2:
        return Trend(state="missing", message=f"No {label} trend data", series=series)
    current = series[-1]["value"]
    previous = series[-2]["value"]
    return Trend(state="ok", direction=direction(current, previous), current=current, previous=previous, percent_change=percent(current, previous), series=series)


def dividend_trend(dividends: list[dict[str, Any]]) -> Trend:
    by_year = defaultdict(float)
    for item in dividends:
        if not item.get("date"):
            continue
        by_year[str(item["date"])[:4]] += float(item.get("amount") or 0)
    series = [{"date": year, "value": amount} for year, amount in sorted(by_year.items()) if amount > 0]
    if len(series) < 2:
        return Trend(state="missing", message="No dividend trend data", series=series)
    current = series[-1]["value"]
    previous = series[-2]["value"]
    return Trend(state="ok", direction=direction(current, previous), current=current, previous=previous, percent_change=percent(current, previous), series=series)


def profit_market_cap_trend(reports: list[dict[str, Any]], market_cap: float | None) -> Trend:
    if not market_cap:
        return Trend(state="missing", message="No market cap data")
    trend = trend_from_reports(reports, ["netIncome", "net_income"], "profit/market cap")
    if trend.state != "ok":
        return trend
    series = [{"date": row["date"], "value": row["value"] / market_cap} for row in trend.series]
    current = series[-1]["value"]
    previous = series[-2]["value"]
    return Trend(state="ok", direction=direction(current, previous), current=current, previous=previous, percent_change=percent(current, previous), series=series)


def screen(items: list[SymbolAnalysis], criteria: dict[str, Any]) -> list[SymbolAnalysis]:
    results = []
    for item in items:
        h = item.holding
        text = (criteria.get("query") or "").lower()
        if text and text not in h.symbol.lower() and text not in h.name.lower():
            continue
        if criteria.get("industry") and criteria["industry"].lower() not in item.industry.lower():
            continue
        if criteria.get("sector") and criteria["sector"].lower() not in h.sector.lower():
            continue
        if criteria.get("account") and criteria["account"].lower() not in h.account.lower():
            continue
        if criteria.get("accountType") and criteria["accountType"].lower() != h.account_type.lower():
            continue
        if criteria.get("location") and criteria["location"].lower() != h.location.lower():
            continue
        if criteria.get("platform") and criteria["platform"].lower() not in h.platform.lower():
            continue
        if criteria.get("currency") and criteria["currency"].upper() != h.currency.upper():
            continue
        if criteria.get("country") and criteria["country"].upper() != h.country.upper():
            continue
        if criteria.get("assetClass") and criteria["assetClass"].upper() != h.asset_class.upper():
            continue
        if criteria.get("trend"):
            requested = criteria["trend"]
            if requested not in {item.income_trend.direction, item.profit_trend.direction, item.dividend_trend.direction, item.profit_market_cap_trend.direction}:
                continue
        if criteria.get("dividendTrend") and criteria["dividendTrend"] != item.dividend_trend.direction:
            continue
        if criteria.get("profitTrend") and criteria["profitTrend"] != item.profit_trend.direction:
            continue
        min_value = _number(criteria.get("minHoldingValue"))
        if min_value is not None and h.market_value < min_value:
            continue
        max_value = _number(criteria.get("maxHoldingValue"))
        if max_value is not None and h.market_value > max_value:
            continue
        min_unrealized_profit = _number(criteria.get("minUnrealizedProfit"))
        if min_unrealized_profit is not None and h.unrealized_profit < min_unrealized_profit:
            continue
        min_income = _number(criteria.get("minIncomeGrowth"))
        if min_income is not None and (item.income_trend.percent_change is None or item.income_trend.percent_change < min_income):
            continue
        min_profit = _number(criteria.get("minProfitGrowth"))
        if min_profit is not None and (item.profit_trend.percent_change is None or item.profit_trend.percent_change < min_profit):
            continue
        min_dividend = _number(criteria.get("minDividendGrowth"))
        if min_dividend is not None and (item.dividend_trend.percent_change is None or item.dividend_trend.percent_change < min_dividend):
            continue
        min_profit_market_cap = _number(criteria.get("minProfitMarketCap"))
        if min_profit_market_cap is not None and (item.profit_market_cap_trend.current is None or item.profit_market_cap_trend.current < min_profit_market_cap):
            continue
        if not criteria.get("includeMissing", True) and item.missing:
            continue
        results.append(item)
    return results


def to_dict(item: SymbolAnalysis) -> dict:
    return asdict(item)


def _status_group(group: str, status: dict[str, str]) -> dict[str, str]:
    return {f"{group}.{provider}": value for provider, value in (status or {}).items()}


def percent(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / abs(previous)) * 100


def direction(current: float | None, previous: float | None) -> str:
    change = percent(current, previous)
    if change is None:
        return "missing"
    if abs(change) < 0.25:
        return "flat"
    return "up" if change > 0 else "down"


def _annual_reports(fundamentals: dict[str, Any]) -> list[dict[str, Any]]:
    income = fundamentals.get("income_statement", {})
    if isinstance(income, dict):
        return income.get("annualReports") or []
    if isinstance(income, list):
        return income
    return []


def _number(value: Any) -> float | None:
    try:
        if value in (None, "", "None"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _local_extrema(prices: list[Ohlcv], attr: str) -> list[tuple[float, float]]:
    points = []
    for idx in range(2, len(prices) - 2):
        value = getattr(prices[idx], attr)
        neighbors = [getattr(prices[idx + offset], attr) for offset in [-2, -1, 1, 2]]
        if attr == "low" and value <= min(neighbors):
            points.append((value, prices[idx].volume))
        if attr == "high" and value >= max(neighbors):
            points.append((value, prices[idx].volume))
    return points


def _ranked_level(points: list[tuple[float, float]], prices: list[Ohlcv]) -> dict:
    if not points:
        values = [row.low for row in prices] + [row.high for row in prices]
        return {"price": mean(values), "touches": 0, "confidence": "low"}
    tolerance = mean([row.adjusted_close for row in prices]) * 0.015
    clusters = []
    for price, volume in points:
        for cluster in clusters:
            if abs(cluster["price"] - price) <= tolerance:
                cluster["prices"].append(price)
                cluster["volume"] += volume
                cluster["price"] = mean(cluster["prices"])
                break
        else:
            clusters.append({"price": price, "prices": [price], "volume": volume})
    best = max(clusters, key=lambda item: (len(item["prices"]), item["volume"]))
    return {"price": best["price"], "touches": len(best["prices"]), "confidence": "high" if len(best["prices"]) >= 3 else "medium"}
