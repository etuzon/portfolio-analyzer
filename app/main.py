from __future__ import annotations

import io
import json
import zipfile
from datetime import date, datetime, time as clock_time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from threading import RLock
import time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .alerts import ALERT_JOB_ID, AlertStore, alert_rule_options, start_scheduler
from .config import data_dir, load_config
from .ghostfolio import GhostfolioClient
from .local_portfolio import ACCOUNT_TYPES, ASSET_CLASSES, FUND_KINDS, INSTRUMENT_TYPES, ISSUER_LISTING_STATUSES, OPTION_TYPES, LocalPortfolioStore
from .metrics import analyze_holding, moving_averages, screen, support_resistance, to_dict, volume_metrics
from .models import Ohlcv
from .providers import MarketDataHub


app = FastAPI(title="Portfolio Analyzer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_web_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

config = load_config()
alert_store = AlertStore()
local_store = LocalPortfolioStore()
scheduler = None
BACKUP_JOB_ID = "local-data-backup"
DIVIDEND_JOB_ID = "local-dividend-scan"
DIVIDEND_DEFAULT_START_DATE = date(2026, 8, 1)
WEEKDAY_CRON = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PORTFOLIO_CACHE_FILE = "portfolio-analysis-cache.json"
HISTORY_START_DATE = date(2026, 4, 14)
US_STOCK_MARKETS = {"NASDAQ", "NYSE", "AMEX", "NYSEARCA", "OTC"}
SUPPORTED_STOCK_MARKETS = {*US_STOCK_MARKETS, "TASE"}
CLIENT_STATE_PREF_KEY = "client_state"
BACKUP_SETTINGS_PREF_KEY = "backup_settings"
_portfolio_cache_lock = RLock()
_portfolio_cache: dict[str, Any] | None = None


def _parse_query_date(value: str) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if "/" in text:
        parts = text.split("/")
        if len(parts) == 3:
            try:
                day, month, year = (int(part) for part in parts)
                return date(year, month, day)
            except ValueError:
                return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _clamped_history_start(value: str, fallback: date | None = None) -> date:
    requested = _parse_query_date(value) or fallback or HISTORY_START_DATE
    return max(requested, HISTORY_START_DATE)


def _local_price_ohlcv(row: dict[str, Any]) -> Ohlcv:
    price = float(row.get("price") or 0)
    return Ohlcv(
        date=date.fromisoformat(str(row["price_date"])),
        open=price,
        high=price,
        low=price,
        close=price,
        adjusted_close=price,
        volume=0,
    )


def _security_history_point(row: Ohlcv) -> dict[str, Any]:
    return {
        "date": row.date.isoformat(),
        "price": row.adjusted_close,
        "open": row.open,
        "high": row.high,
        "low": row.low,
        "close": row.close,
        "adjusted_close": row.adjusted_close,
        "volume": row.volume,
    }


def _security_history_response(
    symbol: str,
    stock_market: str,
    period: str,
    source: str,
    prices: list[Ohlcv],
    level_prices: list[Ohlcv] | None = None,
    status: dict[str, str] | None = None,
) -> dict[str, Any]:
    level_source = level_prices if level_prices is not None else prices
    return {
        "symbol": symbol,
        "stock_market": stock_market,
        "period": period,
        "source": source,
        "status": status or {},
        "points": [_security_history_point(row) for row in prices],
        "moving_averages": moving_averages(prices),
        "support_resistance": support_resistance(level_source),
        "volume": volume_metrics(prices),
        "has_candles": any(
            row.open != row.close or row.high != row.low or row.high != row.close or row.low != row.close
            for row in prices
        ),
        "has_volume": any(row.volume > 0 for row in prices),
    }


def _safe_symbol(value: Any) -> str:
    symbol = str(value or "").upper().strip()
    if not symbol or len(symbol) > 24 or any(char for char in symbol if not (char.isalnum() or char in ".-")):
        raise HTTPException(status_code=400, detail="Symbol must contain only letters, numbers, dots, or dashes")
    return symbol


def _number_or_none(value: Any) -> float | None:
    try:
        if value in (None, "", "None"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _percent_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / abs(previous) * 100


def _report_date(value: Any) -> str:
    text = str(value or "").strip()
    parsed = _parse_query_date(text)
    if parsed:
        return parsed.isoformat()
    if len(text) == 4 and text.isdigit():
        return f"{text}-12-31"
    return text[:10]


def _report_value(row: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = _number_or_none(row.get(key))
        if value is not None:
            return value
    return None


def _annual_report_rows(fundamentals: dict[str, Any], limit: int, as_of: date | None = None) -> list[dict[str, Any]]:
    income = fundamentals.get("income_statement", {})
    raw_rows = income.get("annualReports") if isinstance(income, dict) else income if isinstance(income, list) else []
    rows: list[dict[str, Any]] = []
    for row in raw_rows or []:
        if not isinstance(row, dict):
            continue
        fiscal_date = _report_date(row.get("fiscalDateEnding") or row.get("date") or row.get("calendarYear") or row.get("fillingDate"))
        filing_date = _report_date(row.get("filingDate") or row.get("fillingDate") or row.get("acceptedDate"))
        revenue = _report_value(row, ["totalRevenue", "revenue", "Revenue", "sales"])
        net_income = _report_value(row, ["netIncome", "net_income", "NetIncomeLoss", "income"])
        gross_profit = _report_value(row, ["grossProfit", "gross_profit"])
        operating_income = _report_value(row, ["operatingIncome", "operating_income", "operatingIncomeLoss"])
        operating_cash_flow = _report_value(row, ["operatingCashFlow", "netCashProvidedByOperatingActivities", "cashFlowFromOperations"])
        capital_expenditures = _report_value(row, ["capitalExpenditures", "capitalExpenditure", "capex"])
        cash = _report_value(row, ["cashAndCashEquivalents", "cash", "cashAndShortTermInvestments"])
        current_assets = _report_value(row, ["totalCurrentAssets", "currentAssets"])
        current_liabilities = _report_value(row, ["totalCurrentLiabilities", "currentLiabilities"])
        accounts_receivable = _report_value(row, ["netReceivables", "accountsReceivable"])
        inventory = _report_value(row, ["inventory"])
        long_term_debt = _report_value(row, ["longTermDebt", "totalDebt", "netDebt"])
        interest_expense = _report_value(row, ["interestExpense", "interest_expense"])
        if not fiscal_date or (revenue is None and net_income is None):
            continue
        available_date = _parse_query_date(filing_date) or _parse_query_date(fiscal_date)
        if as_of and available_date and available_date > as_of:
            continue
        free_cash_flow = operating_cash_flow - abs(capital_expenditures) if operating_cash_flow is not None and capital_expenditures is not None else None
        rows.append(
            {
                "fiscal_date": fiscal_date,
                "filing_date": filing_date or None,
                "fiscal_year": int(fiscal_date[:4]) if fiscal_date[:4].isdigit() else None,
                "revenue": revenue,
                "net_income": net_income,
                "gross_profit": gross_profit,
                "gross_margin_percent": (gross_profit / revenue * 100) if revenue not in (None, 0) and gross_profit is not None else None,
                "operating_income": operating_income,
                "operating_margin_percent": (operating_income / revenue * 100) if revenue not in (None, 0) and operating_income is not None else None,
                "net_margin_percent": (net_income / revenue * 100) if revenue not in (None, 0) and net_income is not None else None,
                "operating_cash_flow": operating_cash_flow,
                "capital_expenditures": capital_expenditures,
                "free_cash_flow": free_cash_flow,
                "free_cash_flow_margin_percent": (free_cash_flow / revenue * 100) if free_cash_flow is not None and revenue not in (None, 0) else None,
                "cash_conversion_percent": (free_cash_flow / net_income * 100) if free_cash_flow is not None and net_income not in (None, 0) else None,
                "cash": cash,
                "current_assets": current_assets,
                "current_liabilities": current_liabilities,
                "current_ratio": (current_assets / current_liabilities) if current_assets is not None and current_liabilities not in (None, 0) else None,
                "accounts_receivable": accounts_receivable,
                "inventory": inventory,
                "long_term_debt": long_term_debt,
                "debt_to_revenue_percent": (long_term_debt / revenue * 100) if long_term_debt is not None and revenue not in (None, 0) else None,
                "interest_expense": interest_expense,
            }
        )
    rows.sort(key=lambda item: item["fiscal_date"])
    previous: dict[str, Any] | None = None
    for row in rows:
        row["revenue_growth_percent"] = _percent_change(row.get("revenue"), previous.get("revenue") if previous else None)
        row["net_income_growth_percent"] = _percent_change(row.get("net_income"), previous.get("net_income") if previous else None)
        previous = row
    rows.reverse()
    return rows[:limit]


def _finance_report_payload(symbol: str, limit: int = 6, as_of_date: str = "") -> dict[str, Any]:
    normalized_symbol = _safe_symbol(symbol)
    row_limit = min(max(int(limit or 6), 1), 10)
    as_of = _parse_query_date(as_of_date)
    if as_of_date and not as_of:
        raise ValueError("As-of date must use dd/mm/yyyy or yyyy-mm-dd")
    provider_hub = hub()
    if as_of and callable(getattr(provider_hub, "fundamentals_as_of", None)):
        fundamentals, status = provider_hub.fundamentals_as_of(normalized_symbol, as_of)
    else:
        fundamentals, status = provider_hub.fundamentals(normalized_symbol)
    raw_profile = fundamentals.get("profile") if isinstance(fundamentals.get("profile"), dict) else fundamentals.get("overview") if isinstance(fundamentals.get("overview"), dict) else {}
    profile = {
        **raw_profile,
        "name": raw_profile.get("name") or raw_profile.get("Name") or raw_profile.get("companyName"),
        "sector": raw_profile.get("sector") or raw_profile.get("Sector"),
        "industry": raw_profile.get("industry") or raw_profile.get("Industry"),
        "exchange": raw_profile.get("exchange") or raw_profile.get("Exchange") or raw_profile.get("exchangeShortName"),
        "currency": raw_profile.get("currency") or raw_profile.get("Currency"),
        "country": raw_profile.get("country") or raw_profile.get("Country"),
        "market_cap": _number_or_none(raw_profile.get("market_cap") or raw_profile.get("MarketCapitalization") or raw_profile.get("marketCap") or raw_profile.get("mktCap")),
        "shares_outstanding": _number_or_none(raw_profile.get("shares_outstanding") or raw_profile.get("SharesOutstanding") or raw_profile.get("sharesOutstanding")),
        "beta": _number_or_none(raw_profile.get("beta") or raw_profile.get("Beta")),
    } if raw_profile else {}
    reports = _annual_report_rows(fundamentals, row_limit, as_of)
    latest = reports[0] if reports else {}
    missing = []
    if not reports:
        missing.append("annual financial reports")
    if not profile:
        missing.append("company profile")
    if reports:
        latest = reports[0]
        if latest.get("free_cash_flow") is None:
            missing.append("free cash flow")
        if latest.get("long_term_debt") is None:
            missing.append("long-term debt")
    if as_of and any(not row.get("filing_date") for row in reports):
        missing.append("filing dates unavailable; fiscal-date cutoff used for some reports")
    return {
        "symbol": normalized_symbol,
        "profile": profile,
        "provider_status": status,
        "reports": reports,
        "latest": latest,
        "summary": {
            "latest_revenue": latest.get("revenue"),
            "latest_net_income": latest.get("net_income"),
            "latest_gross_margin_percent": latest.get("gross_margin_percent"),
            "latest_operating_margin_percent": latest.get("operating_margin_percent"),
            "latest_net_margin_percent": latest.get("net_margin_percent"),
            "latest_revenue_growth_percent": latest.get("revenue_growth_percent"),
            "latest_net_income_growth_percent": latest.get("net_income_growth_percent"),
            "latest_free_cash_flow": latest.get("free_cash_flow"),
            "latest_free_cash_flow_margin_percent": latest.get("free_cash_flow_margin_percent"),
            "latest_cash_conversion_percent": latest.get("cash_conversion_percent"),
            "latest_current_ratio": latest.get("current_ratio"),
            "latest_long_term_debt": latest.get("long_term_debt"),
            "years": len(reports),
        },
        "statement_coverage": {
            "income_statement": bool(latest.get("revenue") is not None and latest.get("net_income") is not None),
            "cash_flow_statement": bool(latest.get("operating_cash_flow") is not None and latest.get("capital_expenditures") is not None),
            "balance_sheet": bool(latest.get("cash") is not None or latest.get("long_term_debt") is not None or latest.get("current_ratio") is not None),
        },
        "missing": missing,
        "as_of_date": as_of.isoformat() if as_of else None,
    }


OUTLOOK_MODEL_VERSION = "report-outlook-v4"
OUTLOOK_BATCH_MAX_COMPANIES = 10


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _median(values: list[float | None]) -> float | None:
    numbers = sorted(value for value in values if value is not None)
    if not numbers:
        return None
    middle = len(numbers) // 2
    return numbers[middle] if len(numbers) % 2 else (numbers[middle - 1] + numbers[middle]) / 2


def _symbol_list(value: Any, maximum: int = 6) -> list[str]:
    values = value if isinstance(value, list) else str(value or "").replace(";", ",").split(",")
    result: list[str] = []
    for item in values:
        candidate = item.get("symbol") if isinstance(item, dict) else item
        try:
            symbol = _safe_symbol(candidate)
        except HTTPException:
            continue
        if symbol not in result:
            result.append(symbol)
        if len(result) >= maximum:
            break
    return result


def _same_industry(left: Any, right: Any) -> bool:
    left_text = str(left or "").strip().casefold()
    right_text = str(right or "").strip().casefold()
    return bool(left_text and right_text and (left_text == right_text or left_text in right_text or right_text in left_text))


def _outlook_company(symbol: str, payload: dict[str, Any], target_industry: str = "", peer_source: str = "") -> dict[str, Any]:
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    latest = payload.get("latest") if isinstance(payload.get("latest"), dict) else {}
    reports = payload.get("reports") if isinstance(payload.get("reports"), list) else []
    previous = reports[1] if len(reports) > 1 and isinstance(reports[1], dict) else {}
    industry = str(profile.get("industry") or profile.get("sector") or "").strip()
    return {
        "symbol": symbol,
        "name": str(profile.get("name") or symbol),
        "industry": industry,
        "fiscal_date": latest.get("fiscal_date"),
        "filing_date": latest.get("filing_date"),
        "revenue": latest.get("revenue"),
        "revenue_growth_percent": latest.get("revenue_growth_percent"),
        "net_income": latest.get("net_income"),
        "net_income_growth_percent": latest.get("net_income_growth_percent"),
        "gross_margin_percent": latest.get("gross_margin_percent"),
        "operating_margin_percent": latest.get("operating_margin_percent"),
        "net_margin_percent": latest.get("net_margin_percent"),
        "profit_margin_percent": latest.get("operating_margin_percent") if latest.get("operating_margin_percent") is not None else latest.get("net_margin_percent"),
        "profit_margin_source": "operating margin" if latest.get("operating_margin_percent") is not None else "net margin",
        "net_margin_change_percent": (
            latest["net_margin_percent"] - previous["net_margin_percent"]
            if latest.get("net_margin_percent") is not None and previous.get("net_margin_percent") is not None
            else None
        ),
        "free_cash_flow": latest.get("free_cash_flow"),
        "free_cash_flow_margin_percent": latest.get("free_cash_flow_margin_percent"),
        "cash_conversion_percent": latest.get("cash_conversion_percent"),
        "current_ratio": latest.get("current_ratio"),
        "receivables_to_revenue_percent": (latest["accounts_receivable"] / latest["revenue"] * 100)
        if latest.get("accounts_receivable") is not None and latest.get("revenue") not in (None, 0) else None,
        "inventory_to_revenue_percent": (latest["inventory"] / latest["revenue"] * 100)
        if latest.get("inventory") is not None and latest.get("revenue") not in (None, 0) else None,
        "long_term_debt": latest.get("long_term_debt"),
        "debt_to_revenue_percent": latest.get("debt_to_revenue_percent"),
        "report_years": payload.get("summary", {}).get("years", 0),
        "same_industry": _same_industry(industry, target_industry) if target_industry else False,
        "peer_source": peer_source,
        "missing": payload.get("missing") or [],
        "provider_status": payload.get("provider_status") or {},
        "statement_coverage": payload.get("statement_coverage") or {},
    }


def _relative_points(value: float | None, median: float | None, maximum: float, spread: float) -> float:
    if value is None or median is None:
        return 0.0
    return round(_clamp(maximum / 2 + (value - median) / max(spread, 0.1) * (maximum / 2), 0, maximum), 1)


def _fundamental_score(
    company: dict[str, Any],
    median_revenue_growth: float | None,
    median_income_growth: float | None,
    median_margin: float | None,
    median_free_cash_flow_margin: float | None,
    median_cash_conversion: float | None,
    median_debt_to_revenue: float | None,
    median_current_ratio: float | None,
) -> float:
    score = 0.0
    available_weight = 0.0
    for value, median, maximum, spread in [
        (company.get("revenue_growth_percent"), median_revenue_growth, 12, 20),
        (company.get("net_income_growth_percent"), median_income_growth, 10, 30),
        (company.get("profit_margin_percent"), median_margin, 10, 20),
    ]:
        if value is None or median is None:
            continue
        score += _relative_points(value, median, maximum, spread)
        available_weight += maximum
    cash_quality_points = []
    if company.get("free_cash_flow_margin_percent") is not None and median_free_cash_flow_margin is not None:
        cash_quality_points.append(_relative_points(company["free_cash_flow_margin_percent"], median_free_cash_flow_margin, 5, 15))
    if company.get("cash_conversion_percent") is not None and median_cash_conversion is not None:
        cash_quality_points.append(_relative_points(company["cash_conversion_percent"], median_cash_conversion, 5, 40))
    if cash_quality_points:
        score += sum(cash_quality_points) / len(cash_quality_points)
        available_weight += 5
    if company.get("debt_to_revenue_percent") is not None and median_debt_to_revenue is not None:
        score += _relative_points(median_debt_to_revenue, company["debt_to_revenue_percent"], 2, 30)
        available_weight += 2
    if company.get("current_ratio") is not None and median_current_ratio is not None:
        score += _relative_points(company["current_ratio"], median_current_ratio, 1, 0.8)
        available_weight += 1
    margin_change = company.get("net_margin_change_percent")
    if margin_change is not None:
        score += 5 if margin_change >= 0 else 1
        available_weight += 5
    return round(score / available_weight * 45, 1) if available_weight else 0.0


def _score_band(score: float) -> tuple[str, str]:
    if score >= 80:
        return "Strong", "positive"
    if score >= 65:
        return "Good", "positive"
    if score >= 50:
        return "Mixed", "neutral"
    return "Weak", "negative"


def _mermaid_label(value: Any) -> str:
    return str(value or "").replace('"', "'").replace("[", "(").replace("]", ")").replace("|", "/")[:80]


def _pct_label(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}%"


def _outlook_mermaid(target: dict[str, Any], industry: dict[str, Any], peers: list[dict[str, Any]], related: list[dict[str, Any]], score: float) -> tuple[dict[str, Any], str]:
    nodes = [
        {"id": "target", "label": target["symbol"], "type": "target"},
        {"id": "industry", "label": industry["name"], "type": "industry"},
    ]
    edges = [{"from": "target", "to": "industry", "label": "competes in"}]
    lines = [
        "flowchart LR",
        f'  T["{_mermaid_label(target["symbol"])}<br/>Revenue growth: {_pct_label(target.get("revenue_growth_percent"))}<br/>Net margin: {_pct_label(target.get("net_margin_percent"))}<br/>Score: {score:.0f}"]:::target',
        f'  I["{_mermaid_label(industry["name"])}<br/>Median revenue growth: {_pct_label(industry.get("median_revenue_growth_percent"))}<br/>Health: {_mermaid_label(industry["health"])}"]:::industry',
        '  T -->|"competes in"| I',
    ]
    for index, peer in enumerate(peers[:6], 1):
        node_id = f"peer{index}"
        nodes.append({"id": node_id, "label": peer["symbol"], "type": "peer"})
        edges.append({"from": node_id, "to": "industry", "label": "same industry"})
        lines.append(f'  P{index}["{_mermaid_label(peer["symbol"])}<br/>Score: {peer.get("score", 0):.0f}<br/>Revenue growth: {_pct_label(peer.get("revenue_growth_percent"))}"]:::peer')
        lines.append(f'  P{index} -->|"same industry"| I')
    for index, item in enumerate(related[:4], 1):
        node_id = f"related{index}"
        nodes.append({"id": node_id, "label": item["symbol"], "type": "related"})
        edges.append({"from": node_id, "to": "target", "label": item["relation"]})
        lines.append(f'  R{index}["{_mermaid_label(item["symbol"])}<br/>{_mermaid_label(item["relation"])}<br/>Revenue growth: {_pct_label(item.get("revenue_growth_percent"))}"]:::related')
        lines.append(f'  R{index} -->|"{_mermaid_label(item["relation"])}"| T')
    lines.extend(
        [
            "  classDef target fill:#183b56,stroke:#64d2ff,color:#ffffff",
            "  classDef industry fill:#232946,stroke:#f4d35e,color:#ffffff",
            "  classDef peer fill:#123524,stroke:#8bd17c,color:#ffffff",
            "  classDef related fill:#3a233f,stroke:#f38ba8,color:#ffffff",
        ]
    )
    return {"nodes": nodes[:14], "edges": edges[:22], "feedback_loops": 0}, "\n".join(lines)


def _related_company_specs(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw = payload.get("related_companies") or []
    if not isinstance(raw, list):
        raw = str(raw).replace(";", ",").split(",")
    relation = str(payload.get("related_effect") or "related industry").strip()[:40] or "related industry"
    result = []
    for item in raw:
        source = item if isinstance(item, dict) else {"symbol": item}
        try:
            symbol = _safe_symbol(source.get("symbol"))
        except HTTPException:
            continue
        if any(row["symbol"] == symbol for row in result):
            continue
        result.append({"symbol": symbol, "relation": str(source.get("relation") or relation).strip()[:40] or "related industry"})
        if len(result) >= 4:
            break
    return result


def _company_outlook_payload(symbol: str, request: dict[str, Any] | None = None) -> dict[str, Any]:
    request = request or {}
    target_symbol = _safe_symbol(symbol)
    as_of_date = str(request.get("as_of_date") or "").strip()
    manual_industry = str(request.get("industry") or "").strip()[:80]
    target_report = _finance_report_payload(target_symbol, 6, as_of_date)
    target = _outlook_company(target_symbol, target_report)
    industry_name = manual_industry or target["industry"] or "Unclassified industry"
    industry_source = "manual comparable cohort" if manual_industry else "company profile" if target["industry"] else "unclassified"
    explicit_peers = [item for item in _symbol_list(request.get("peers")) if item != target_symbol]
    peer_symbols = explicit_peers[:]
    screener_status: dict[str, str] = {}
    peer_source = "explicit industry cohort" if peer_symbols and manual_industry else "explicit" if peer_symbols else ""
    if not peer_symbols and target["industry"]:
        candidates, screener_status = hub().market_screener({"industry": target["industry"], "limit": 8})
        peer_symbols = [
            item_symbol for item_symbol in _symbol_list([item.get("symbol") for item in candidates], 6)
            if item_symbol != target_symbol
        ]
        peer_source = "provider industry screener" if peer_symbols else ""
    peer_reports = [_outlook_company(peer_symbol, _finance_report_payload(peer_symbol, 4, as_of_date), target["industry"], peer_source) for peer_symbol in peer_symbols[:6]]
    comparable_peers = [
        peer for peer in peer_reports
        if peer.get("same_industry") or peer_source in {"provider industry screener", "explicit industry cohort"}
    ]
    score_peers = comparable_peers or peer_reports
    median_revenue_growth = _median([peer.get("revenue_growth_percent") for peer in score_peers])
    median_income_growth = _median([peer.get("net_income_growth_percent") for peer in score_peers])
    median_margin = _median([peer.get("profit_margin_percent") for peer in score_peers])
    median_free_cash_flow_margin = _median([peer.get("free_cash_flow_margin_percent") for peer in score_peers])
    median_cash_conversion = _median([peer.get("cash_conversion_percent") for peer in score_peers])
    median_debt_to_revenue = _median([peer.get("debt_to_revenue_percent") for peer in score_peers])
    median_current_ratio = _median([peer.get("current_ratio") for peer in score_peers])
    industry_score = (
        _relative_points(median_revenue_growth, 0, 8, 20)
        + _relative_points(median_income_growth, 0, 6, 25)
        + _relative_points(median_margin, 0, 5, 20)
        + (2 if len(score_peers) >= 3 else 0)
    )
    industry_health = "Pressure" if industry_score < 9 else "Stable" if industry_score < 15 else "Supportive"
    industry = {
        "name": industry_name,
        "source": industry_source,
        "median_revenue_growth_percent": median_revenue_growth,
        "median_net_income_growth_percent": median_income_growth,
        "median_net_margin_percent": median_margin,
        "score": round(industry_score, 1),
        "health": industry_health,
        "issues": ([] if score_peers else ["No comparable peer reports were available"]),
        "peer_count": len(score_peers),
    }
    company_score = _fundamental_score(
        target,
        median_revenue_growth,
        median_income_growth,
        median_margin,
        median_free_cash_flow_margin,
        median_cash_conversion,
        median_debt_to_revenue,
        median_current_ratio,
    )
    for peer in peer_reports:
        peer["score"] = _fundamental_score(
            peer,
            median_revenue_growth,
            median_income_growth,
            median_margin,
            median_free_cash_flow_margin,
            median_cash_conversion,
            median_debt_to_revenue,
            median_current_ratio,
        )
    related = []
    related_score = 0.0
    for spec in _related_company_specs(request):
        relation_report = _finance_report_payload(spec["symbol"], 4, as_of_date)
        company = _outlook_company(spec["symbol"], relation_report)
        item = {**company, "relation": spec["relation"]}
        related.append(item)
        growth = item.get("revenue_growth_percent")
        if growth is not None:
            if spec["relation"].casefold() in {"demand support", "customer demand", "complement"}:
                related_score += 5 if growth > 0 else 1
            elif spec["relation"].casefold() in {"cost pressure", "supplier pressure", "substitute"}:
                related_score += 1 if growth > 0 else 4
            else:
                related_score += 2.5
    related_score = min(15.0, related_score)
    target["same_industry"] = True
    preliminary = company_score + industry_score + related_score
    target["score"] = company_score
    ranked = sorted([target, *score_peers], key=lambda item: item.get("score") if item.get("score") is not None else -10_000, reverse=True)
    rank = next((index + 1 for index, item in enumerate(ranked) if item["symbol"] == target_symbol), 1)
    rank_score = 0.0 if len(ranked) <= 1 else round((len(ranked) - rank) / (len(ranked) - 1) * 8, 1)
    source_score = 4 if target["report_years"] >= 3 and len(score_peers) >= 3 else 2 if target["report_years"] >= 2 and score_peers else 0
    missing = list(target_report.get("missing") or [])
    if not score_peers:
        missing.append("same-industry peer reports")
    if not related:
        missing.append("related-industry reports")
    confidence = "High" if target["report_years"] >= 3 and len(score_peers) >= 4 else "Medium" if target["report_years"] >= 2 and len(score_peers) >= 2 else "Low"
    data_quality = 3 if confidence == "High" else 2 if confidence == "Medium" else 0
    final_score = round(_clamp(preliminary + rank_score + source_score + data_quality, 0, 100), 1)
    label, direction = _score_band(final_score)
    graph, mermaid = _outlook_mermaid(target, industry, peer_reports, related, final_score)
    thesis = (
        f"{target_symbol} ranks {rank} of {len(ranked)} on available report growth signals. "
        f"Industry conditions appear {industry_health.casefold()}. "
        f"Cash-flow and balance-sheet measures are included when filed; missing statement evidence lowers confidence."
    )
    simple_words = (
        f"{target_symbol} scores {final_score:.0f}/100. It ranks {rank} out of {len(ranked)} companies using available annual report numbers. "
        f"The {industry_name} outlook looks {industry_health.casefold()}. {thesis.split('. ')[-1]} Confidence: {confidence}."
    )
    payload = {
        "symbol": target_symbol,
        "companies": [target, *peer_reports],
        "industry": industry,
        "related_industries": related,
        "graph": graph,
        "mermaid": mermaid,
        "score": final_score,
        "label": label,
        "direction": direction,
        "rank": rank,
        "score_components": {
            "company_fundamentals": round(company_score, 1),
            "industry_outlook": round(industry_score, 1),
            "related_industry_effect": round(related_score, 1),
            "relative_rank": rank_score,
            "source_and_confidence": round(source_score + data_quality, 1),
        },
        "confidence": confidence,
        "conclusion": thesis,
        "simple_words": simple_words,
        "missing": missing,
        "as_of_date": target_report.get("as_of_date"),
        "provider_status": {"target": target_report.get("provider_status") or {}, "peer_screener": screener_status},
        "peer_source": peer_source or "No peer source available",
    }
    if request.get("save_prediction", True):
        horizon_months = int(request.get("horizon_months") or 12)
        horizon_months = max(3, min(horizon_months, 48))
        prediction_date = _parse_query_date(as_of_date) or date.today()
        record = local_store.save_company_report_prediction(
            {
                "symbol": target_symbol,
                "company_name": target["name"],
                "industry": industry_name,
                "created_at": prediction_date.isoformat() + "T00:00:00Z",
                "horizon_date": (prediction_date + timedelta(days=horizon_months * 30)).isoformat(),
                "model_version": OUTLOOK_MODEL_VERSION,
                "score": final_score,
                "label": label,
                "direction": direction,
                "confidence": confidence,
                "baseline": {
                    "target": target,
                    "peers": [{"symbol": peer["symbol"], "fiscal_date": peer.get("fiscal_date")} for peer in score_peers],
                    "industry": industry,
                    "related_industries": related,
                    "score_components": payload["score_components"],
                    "batch": request.get("batch") if isinstance(request.get("batch"), dict) else {},
                },
                "thesis": thesis,
                "mermaid": mermaid,
            }
        )
        payload["prediction_record"] = {"id": record["id"], "horizon_date": record["horizon_date"], "baseline_fiscal_date": target.get("fiscal_date"), "status": record["actual_direction"]}
    return payload


def _evaluate_prediction(prediction: dict[str, Any]) -> dict[str, Any]:
    baseline = prediction.get("baseline") if isinstance(prediction.get("baseline"), dict) else {}
    baseline_target = baseline.get("target") if isinstance(baseline.get("target"), dict) else {}
    baseline_date = str(baseline_target.get("fiscal_date") or "")
    horizon_date = _parse_query_date(str(prediction.get("horizon_date") or ""))
    report = _finance_report_payload(prediction["symbol"], 6, horizon_date.isoformat() if horizon_date else "")

    def newer_report(rows: list[dict[str, Any]], since_date: str) -> dict[str, Any] | None:
        eligible = []
        for row in rows:
            fiscal_date = str(row.get("fiscal_date") or "")
            available_date = str(row.get("filing_date") or fiscal_date)
            if fiscal_date <= since_date:
                continue
            if horizon_date and available_date > horizon_date.isoformat():
                continue
            eligible.append(row)
        return eligible[0] if eligible else None

    actual = newer_report(report.get("reports") or [], baseline_date)
    if not baseline_date or not actual:
        return local_store.evaluate_company_report_prediction(prediction["id"], {}, "pending", None, "No newer annual report is available yet.")

    peer_rows = baseline.get("peers") if isinstance(baseline.get("peers"), list) else []
    peer_actuals = []
    for peer in peer_rows[:6]:
        if not isinstance(peer, dict) or not peer.get("symbol"):
            continue
        peer_report = _finance_report_payload(str(peer["symbol"]), 6, horizon_date.isoformat() if horizon_date else "")
        row = newer_report(peer_report.get("reports") or [], str(peer.get("fiscal_date") or ""))
        if row and row.get("revenue_growth_percent") is not None and row.get("net_margin_percent") is not None:
            peer_actuals.append({"symbol": peer["symbol"], **row})

    revenue_growth = actual.get("revenue_growth_percent")
    margin_change = None
    if actual.get("net_margin_percent") is not None and baseline_target.get("net_margin_percent") is not None:
        margin_change = actual["net_margin_percent"] - baseline_target["net_margin_percent"]
    peer_median_revenue_growth = _median([row.get("revenue_growth_percent") for row in peer_actuals])
    peer_median_margin = _median([row.get("net_margin_percent") for row in peer_actuals])
    actual = {
        **actual,
        "peer_count": len(peer_actuals),
        "peer_median_revenue_growth_percent": peer_median_revenue_growth,
        "peer_median_net_margin_percent": peer_median_margin,
    }

    if len(peer_actuals) >= 2 and revenue_growth is not None and actual.get("net_margin_percent") is not None:
        revenue_relative = revenue_growth - peer_median_revenue_growth
        margin_relative = actual["net_margin_percent"] - peer_median_margin
        if revenue_relative >= 0 and margin_relative >= 0:
            direction = "positive"
            evaluation = "Revenue growth and net margin were at or above the later peer medians."
        elif revenue_relative < 0 and margin_relative < 0:
            direction = "negative"
            evaluation = "Revenue growth and net margin were both below the later peer medians."
        else:
            direction = "neutral"
            evaluation = "Later report signals were mixed versus peer medians."
    elif revenue_growth is None or margin_change is None:
        direction = "inconclusive"
        evaluation = "The newer report is missing comparable revenue growth or net margin."
    elif revenue_growth > 0 and margin_change >= 0:
        direction = "positive"
        evaluation = "Revenue growth and net margin both improved or held."
    elif revenue_growth < 0 and margin_change < 0:
        direction = "negative"
        evaluation = "Revenue growth and net margin both weakened."
    else:
        direction = "neutral"
        evaluation = "The newer report shows mixed revenue-growth and margin signals."

    if direction == "inconclusive":
        accuracy = None
    elif prediction["direction"] == direction:
        accuracy = 100
    elif direction == "neutral":
        accuracy = 50
    else:
        accuracy = 0
    return local_store.evaluate_company_report_prediction(prediction["id"], actual, direction, accuracy, evaluation)


def _company_outlook_backtest(symbol: str, request: dict[str, Any] | None = None) -> dict[str, Any]:
    request = request or {}
    as_of = _parse_query_date(str(request.get("as_of_date") or ""))
    if not as_of:
        raise ValueError("A historical as-of date is required for a backtest")
    if as_of >= date.today():
        raise ValueError("The historical as-of date must be before today")
    analysis = _company_outlook_payload(symbol, {**request, "as_of_date": as_of.isoformat(), "save_prediction": True})
    prediction_id = analysis.get("prediction_record", {}).get("id")
    prediction = next((item for item in local_store.list_company_report_predictions() if item["id"] == prediction_id), None)
    if not prediction:
        raise ValueError("Backtest prediction was not saved")
    evaluation = _evaluate_prediction(prediction)
    return {"as_of_date": as_of.isoformat(), "analysis": analysis, "evaluation": evaluation, "scorecard": local_store.company_report_scorecard()}


def _batch_prediction_review(predictions: list[dict[str, Any]], phase: str) -> dict[str, Any]:
    evaluated = [item for item in predictions if item.get("accuracy_score") is not None]
    actual_directions = {"positive": 0, "neutral": 0, "negative": 0, "pending": 0, "inconclusive": 0}
    direction_pairs: dict[str, int] = {}
    for item in predictions:
        actual = str(item.get("actual_direction") or "pending")
        actual_directions[actual] = actual_directions.get(actual, 0) + 1
        if item.get("accuracy_score") is not None:
            key = f"predicted_{item.get('direction')}__actual_{actual}"
            direction_pairs[key] = direction_pairs.get(key, 0) + 1
    accuracy = round(sum(float(item["accuracy_score"]) for item in evaluated) / len(evaluated), 1) if evaluated else None
    return {
        "phase": phase,
        "attempted": len(predictions),
        "evaluated": len(evaluated),
        "pending": actual_directions.get("pending", 0),
        "inconclusive": actual_directions.get("inconclusive", 0),
        "accuracy_percent": accuracy,
        "actual_directions": actual_directions,
        "direction_confusion": direction_pairs,
        "calibration_notice": (
            "This batch may be used to assess a pre-declared candidate rule, but it cannot validate a rule tuned on this batch."
            if phase == "calibration"
            else "This is an untouched holdout batch. Do not tune the model using its results."
        ),
    }


def _company_outlook_backtest_batch(request: dict[str, Any] | None = None) -> dict[str, Any]:
    request = request or {}
    as_of = _parse_query_date(str(request.get("as_of_date") or ""))
    if not as_of:
        raise ValueError("A historical as-of date is required for a batch backtest")
    if as_of >= date.today():
        raise ValueError("The historical as-of date must be before today")
    raw_companies = request.get("companies")
    if not isinstance(raw_companies, list) or not raw_companies:
        raise ValueError("Batch backtests require a non-empty companies list")
    if len(raw_companies) > OUTLOOK_BATCH_MAX_COMPANIES:
        raise ValueError(f"A batch can contain at most {OUTLOOK_BATCH_MAX_COMPANIES} companies")
    phase = str(request.get("phase") or "calibration").strip().lower()
    if phase not in {"calibration", "holdout"}:
        raise ValueError("Batch phase must be calibration or holdout")
    batch_number = max(1, int(request.get("batch_number") or 1))
    horizon_months = max(3, min(int(request.get("horizon_months") or 12), 48))
    batch_id = str(request.get("batch_id") or f"{phase}-{as_of.isoformat()}-{horizon_months}m-{batch_number:03d}").strip()[:120]
    results = []
    failures = []
    for item in raw_companies:
        spec = item if isinstance(item, dict) else {"symbol": item}
        try:
            symbol = _safe_symbol(spec.get("symbol"))
            existing = local_store.company_report_prediction_for_batch(batch_id, symbol)
            if existing:
                results.append(
                    {
                        "as_of_date": as_of.isoformat(),
                        "analysis": {"symbol": symbol, "prediction_record": {"id": existing["id"], "status": existing.get("actual_direction")}},
                        "evaluation": existing,
                        "reused": True,
                    }
                )
                continue
            peers = _symbol_list(spec.get("peers"))
            if len(peers) < 2:
                raise ValueError("Each company requires at least two same-industry peers")
            result = _company_outlook_backtest(
                symbol,
                {
                    "as_of_date": as_of.isoformat(),
                    "horizon_months": horizon_months,
                    "peers": peers,
                    "industry": str(spec.get("industry") or "").strip()[:80],
                    "related_companies": spec.get("related_companies") or [],
                    "related_effect": str(spec.get("related_effect") or "").strip()[:40],
                    "batch": {"id": batch_id, "number": batch_number, "phase": phase},
                },
            )
            results.append(result)
        except (HTTPException, ValueError) as exc:
            failures.append({"symbol": str(spec.get("symbol") or "").upper().strip(), "error": str(getattr(exc, "detail", exc))})
    predictions = [item["evaluation"] for item in results if isinstance(item.get("evaluation"), dict)]
    prediction_ids = {
        str(item.get("analysis", {}).get("prediction_record", {}).get("id") or "")
        for item in results
    }
    prediction_ids.discard("")
    return {
        "batch_id": batch_id,
        "batch_number": batch_number,
        "phase": phase,
        "as_of_date": as_of.isoformat(),
        "horizon_months": horizon_months,
        "model_version": OUTLOOK_MODEL_VERSION,
        "results": results,
        "failures": failures,
        "review": _batch_prediction_review(predictions, phase),
        "scorecard": local_store.company_report_scorecard(prediction_ids),
    }


def _stock_market_key(value: Any) -> str:
    text = str(value or "").upper().strip().replace(" ", "").replace("-", "").replace("_", "")
    aliases = {
        "NASDAQGS": "NASDAQ",
        "NASDAQGM": "NASDAQ",
        "NASDAQCM": "NASDAQ",
        "NAS": "NASDAQ",
        "NMS": "NASDAQ",
        "NYSEAMERICAN": "AMEX",
        "NYSEMKT": "AMEX",
        "NYSEARCA": "NYSEARCA",
        "ARCA": "NYSEARCA",
        "AMEX": "AMEX",
        "NYSE": "NYSE",
        "OTC": "OTC",
        "OTCMKTS": "OTC",
        "TASE": "TASE",
        "TLV": "TASE",
        "TELAVIV": "TASE",
    }
    return aliases.get(text, text)


def _quote_market(quote: dict[str, Any]) -> str:
    exchange = _stock_market_key(quote.get("exchange") or quote.get("stock_exchange") or "")
    return exchange if exchange in SUPPORTED_STOCK_MARKETS else ""


def _exact_screener_match(symbol: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    symbol_key = str(symbol or "").upper().strip()
    for row in rows:
        if str(row.get("symbol") or "").upper().strip() == symbol_key:
            return row
    return {}


def _resolve_supported_stock_market(symbol: str, stock_market: str, allow_manual: bool, known_manual: bool) -> tuple[str, dict[str, str]]:
    selected = _stock_market_key(stock_market)
    if allow_manual or known_manual:
        return selected or "MANUAL", {"manual": "accepted"}
    if selected not in SUPPORTED_STOCK_MARKETS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported stock market '{stock_market}'. Supported markets are: {', '.join(sorted(SUPPORTED_STOCK_MARKETS))}",
        )
    if selected == "TASE":
        raise HTTPException(
            status_code=422,
            detail={
                "message": "TASE symbols currently need a defined manual instrument or 'Manual if not found'.",
                "manual_allowed": True,
                "provider_status": {"tase": "manual validation required"},
            },
        )

    market_hub = hub()
    quote, status = market_hub.quote(symbol)
    detected = _quote_market(quote)
    if quote and (quote.get("price") is not None or detected):
        return detected or selected, status

    rows, screener_status = market_hub.market_screener({"query": symbol, "limit": 10})
    status = {**status, **{f"screener_{key}": value for key, value in screener_status.items()}}
    match = _exact_screener_match(symbol, rows)
    if match:
        detected = _stock_market_key(match.get("exchange"))
        if detected in US_STOCK_MARKETS:
            return detected, status
        return selected, status

    raise HTTPException(
        status_code=422,
        detail={
            "message": "Symbol was not found in supported US market data. Enable manual add to save it anyway.",
            "manual_allowed": True,
            "provider_status": status,
        },
    )


@lru_cache(maxsize=1)
def hub() -> MarketDataHub:
    return MarketDataHub(config.market_data, config.db)


def runtime_settings_path() -> Path:
    return data_dir() / "settings.json"


def portfolio_cache_path() -> Path:
    return data_dir() / PORTFOLIO_CACHE_FILE


def portfolio_cache_ttl_seconds() -> int:
    return max(int(config.market_data.get("analysis_cache_ttl_seconds", 900) or 900), 30)


def default_backup_settings() -> dict[str, Any]:
    backup = config.raw.get("backup", {}) if isinstance(config.raw.get("backup"), dict) else {}
    schedule = str(backup.get("schedule") or "45 23 * * *")
    timezone_name = str(backup.get("timezone") or config.alerts.get("timezone") or "UTC")
    return {
        "enabled": bool(backup.get("enabled", True)),
        "schedule": schedule,
        "schedule_config": backup_schedule_config(backup.get("schedule_config"), schedule),
        "missed_policy": str(backup.get("missed_policy") or "wait"),
        "timezone": timezone_name,
        "keep": int(backup.get("keep", 100) or 100),
    }


def backup_schedule_config(raw: Any = None, schedule: str = "45 23 * * *") -> dict[str, Any]:
    if isinstance(raw, dict):
        frequency = str(raw.get("frequency") or "weekly")
        hour = _bounded_int(raw.get("hour"), 23, 0, 23)
        minute = _bounded_int(raw.get("minute"), 45, 0, 59)
        weekdays = _int_list(raw.get("weekdays"), 0, 6)
        month_days = _int_list(raw.get("month_days"), 1, 31)
        if frequency == "monthly":
            return {"frequency": "monthly", "month_days": month_days or [1], "hour": hour, "minute": minute}
        if frequency == "daily":
            return {"frequency": "daily", "hour": hour, "minute": minute}
        return {"frequency": "weekly", "weekdays": weekdays or [0, 2, 4], "hour": hour, "minute": minute}
    return backup_schedule_config_from_cron(schedule)


def backup_schedule_config_from_cron(schedule: str) -> dict[str, Any]:
    parts = str(schedule or "").split()
    if len(parts) != 5:
        return {"frequency": "weekly", "weekdays": [0, 2, 4], "hour": 23, "minute": 45}
    minute, hour, day, _month, weekday = parts
    config_out = {"hour": _bounded_int(hour, 23, 0, 23), "minute": _bounded_int(minute, 45, 0, 59)}
    if day != "*" and weekday == "*":
        return {**config_out, "frequency": "monthly", "month_days": _int_list(day.split(","), 1, 31) or [1]}
    if weekday != "*":
        return {**config_out, "frequency": "weekly", "weekdays": _weekday_list(weekday) or [0, 2, 4]}
    return {**config_out, "frequency": "daily"}


def backup_cron_from_config(schedule_config: dict[str, Any]) -> str:
    config_out = backup_schedule_config(schedule_config)
    minute = config_out["minute"]
    hour = config_out["hour"]
    if config_out["frequency"] == "monthly":
        days = ",".join(str(day) for day in config_out["month_days"])
        return f"{minute} {hour} {days} * *"
    if config_out["frequency"] == "daily":
        return f"{minute} {hour} * * *"
    weekdays = ",".join(WEEKDAY_CRON[day] for day in config_out["weekdays"])
    return f"{minute} {hour} * * {weekdays}"


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return min(max(number, minimum), maximum)


def _bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return min(max(number, minimum), maximum)


def _float(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_list(value: Any, minimum: int, maximum: int) -> list[int]:
    items = value if isinstance(value, list) else str(value or "").split(",")
    numbers = []
    for item in items:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if minimum <= number <= maximum and number not in numbers:
            numbers.append(number)
    return sorted(numbers)


def _weekday_list(value: Any) -> list[int]:
    names = {name: index for index, name in enumerate(WEEKDAY_CRON)}
    names.update({"0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6})
    items = value if isinstance(value, list) else str(value or "").lower().split(",")
    return sorted({names[str(item).strip()] for item in items if str(item).strip() in names})


def load_runtime_settings() -> dict[str, Any]:
    settings = {"backup": default_backup_settings()}
    try:
        backup_preference = local_store.get_preference(BACKUP_SETTINGS_PREF_KEY)
        if isinstance(backup_preference, dict):
            settings["backup"].update(backup_preference)
    except Exception:
        pass
    path = runtime_settings_path()
    if path.exists():
        try:
            saved = json.loads(path.read_text())
            if isinstance(saved.get("backup"), dict):
                settings["backup"].update(saved["backup"])
        except json.JSONDecodeError:
            pass
    return settings


def save_runtime_settings(settings: dict[str, Any]) -> None:
    path = runtime_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, default=str))


def backup_download_path(filename: str) -> Path:
    clean = Path(str(filename or "")).name
    if clean != filename or not clean.startswith("portfolio-data-") or not clean.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid backup filename")
    path = local_store.backup_dir() / clean
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Backup file not found")
    return path


def backup_archive_response() -> Response:
    buffer = io.BytesIO()
    backups = local_store.list_backups()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for backup in backups:
            path = backup_download_path(str(backup.get("filename") or ""))
            archive.write(path, arcname=path.name)
    filename = f"portfolio-backups-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.zip"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def restore_backup_settings_from_preferences() -> None:
    backup_preference = local_store.get_preference(BACKUP_SETTINGS_PREF_KEY)
    if not isinstance(backup_preference, dict):
        return
    settings = load_runtime_settings()
    settings["backup"] = {**default_backup_settings(), **backup_preference}
    save_runtime_settings(settings)
    configure_backup_job()


def write_runtime_backup(keep: int | None = None) -> dict[str, Any]:
    backup = load_runtime_settings()["backup"]
    local_store.set_preference(BACKUP_SETTINGS_PREF_KEY, backup)
    return local_store.write_backup(int(keep or backup.get("keep") or 100))


def configure_backup_job() -> None:
    if scheduler is None:
        return
    try:
        scheduler.remove_job(BACKUP_JOB_ID)
    except Exception:
        pass
    backup = load_runtime_settings()["backup"]
    if not backup.get("enabled", True):
        return
    try:
        trigger = CronTrigger.from_crontab(str(backup.get("schedule") or "45 23 * * *"), timezone=backup.get("timezone") or "UTC")
    except ValueError as exc:
        raise ValueError("Backup schedule must be a 5-field cron expression") from exc
    scheduler.add_job(
        lambda: write_runtime_backup(int(backup.get("keep") or 100)),
        trigger,
        id=BACKUP_JOB_ID,
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=60 * 60 * 24 if backup.get("missed_policy") == "run" else 60,
    )
    maybe_run_missed_backup(backup)


def maybe_run_missed_backup(backup: dict[str, Any]) -> dict[str, Any] | None:
    if not backup.get("enabled", True) or backup.get("missed_policy") != "run":
        return None
    due_at = latest_due_backup_time(backup)
    if not due_at:
        return None
    backups = local_store.list_backups()
    latest = backups[0] if backups else None
    if latest and _parse_backup_modified_at(latest.get("modified_at"), backup.get("timezone") or "UTC") >= due_at:
        return None
    return write_runtime_backup(int(backup.get("keep") or 100))


def latest_due_backup_time(backup: dict[str, Any]) -> datetime | None:
    try:
        tz = ZoneInfo(str(backup.get("timezone") or "UTC"))
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    now = datetime.now(tz)
    config_out = backup_schedule_config(backup.get("schedule_config"), backup.get("schedule") or "")
    scheduled = datetime.combine(now.date(), clock_time(config_out["hour"], config_out["minute"]), tzinfo=tz)
    if scheduled > now:
        return None
    frequency = config_out["frequency"]
    if frequency == "daily":
        return scheduled
    if frequency == "weekly" and now.weekday() in config_out["weekdays"]:
        return scheduled
    if frequency == "monthly" and now.day in config_out["month_days"]:
        return scheduled
    return None


def _parse_backup_modified_at(value: Any, timezone_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.min.replace(tzinfo=timezone.utc)
    try:
        return parsed.astimezone(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError:
        return parsed.astimezone(timezone.utc)


def backup_status() -> dict[str, Any]:
    backup = load_runtime_settings()["backup"]
    job = scheduler.get_job(BACKUP_JOB_ID) if scheduler else None
    backups = local_store.list_backups()
    return {
        **backup,
        "schedule_summary": backup_schedule_summary(backup),
        "directory": str(local_store.backup_dir()),
        "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
        "latest": backups[0] if backups else None,
        "backup_count": len(backups),
        "backups": backups[:10],
    }


def dividend_settings() -> dict[str, Any]:
    raw = config.raw.get("dividends", {}) if isinstance(config.raw.get("dividends"), dict) else {}
    tax_rate = _bounded_float(raw.get("tax_rate"), 0.25, 0, 1)
    start_date = _parse_query_date(str(raw.get("start_date") or "")) or DIVIDEND_DEFAULT_START_DATE
    schedule = str(raw.get("schedule") or "15 8 * * *")
    if len(schedule.split()) != 5:
        schedule = "15 8 * * *"
    return {
        "enabled": bool(raw.get("enabled", True)),
        "tax_rate": tax_rate,
        "start_date": start_date.isoformat(),
        "lookahead_days": max(int(raw.get("lookahead_days") or 180), 1),
        "schedule": schedule,
        "timezone": str(raw.get("timezone") or config.alerts.get("timezone") or "UTC"),
    }


def configure_dividend_job() -> None:
    if scheduler is None:
        return
    try:
        scheduler.remove_job(DIVIDEND_JOB_ID)
    except Exception:
        pass
    settings = dividend_settings()
    if not settings.get("enabled", True):
        return
    trigger = CronTrigger.from_crontab(str(settings["schedule"]), timezone=settings["timezone"])
    scheduler.add_job(
        lambda: process_portfolio_dividends(force_refresh=True),
        trigger,
        id=DIVIDEND_JOB_ID,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 60 * 24,
    )


def dividend_status() -> dict[str, Any]:
    settings = dividend_settings()
    job = scheduler.get_job(DIVIDEND_JOB_ID) if scheduler else None
    return {**settings, "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None}


def process_portfolio_dividends(force_refresh: bool = True) -> dict[str, Any]:
    settings = dividend_settings()
    start_date = _parse_query_date(settings["start_date"]) or DIVIDEND_DEFAULT_START_DATE
    today = date.today()
    to_date = today + timedelta(days=int(settings["lookahead_days"]))
    tax_rate = float(settings["tax_rate"])
    checked = 0
    discovered = 0
    processed = 0
    pending = 0
    skipped = 0
    statuses: dict[str, dict[str, str]] = {}

    holdings = [
        item.holding
        for item in local_store.holdings()
        if item.holding.quantity > 0 and item.holding.account_id and item.holding.asset_class in {"EQUITY", "ETF", "MUTUALFUND"}
    ]
    for holding in holdings:
        checked += 1
        dividends, status = hub().dividends(holding.symbol, force_refresh=force_refresh, to_date=to_date)
        statuses[f"{holding.account_id}:{holding.symbol}"] = status
        for row in dividends:
            event_date = _parse_query_date(str(row.get("date") or ""))
            gross_per_share = _float(row.get("amount"), 0)
            if not event_date or event_date < start_date or event_date > to_date or gross_per_share <= 0:
                continue
            gross = gross_per_share * float(holding.quantity or 0)
            tax = gross * tax_rate
            net = gross - tax
            source_key = ":".join(
                [
                    "dividend",
                    holding.account_id,
                    holding.symbol.upper(),
                    str(holding.stock_market or "").upper(),
                    event_date.isoformat(),
                    f"{gross_per_share:.10f}",
                ]
            )
            event = local_store.record_dividend_event(
                {
                    "event_date": event_date.isoformat(),
                    "symbol": holding.symbol,
                    "stock_market": holding.stock_market,
                    "account_db_id": holding.account_id,
                    "gross_amount": gross,
                    "tax_amount": tax,
                    "net_amount": net,
                    "currency": holding.currency,
                    "source": "dividend_scan",
                    "source_key": source_key,
                    "details": {
                        "gross_per_share": gross_per_share,
                        "shares": holding.quantity,
                        "tax_rate": tax_rate,
                        "asset_class": holding.asset_class,
                        "location": holding.location,
                        "provider_status": status,
                    },
                },
                due=event_date <= today,
            )
            if event.get("skipped"):
                skipped += 1
                continue
            discovered += int(bool(event.get("created")))
            if event.get("status") == "processed":
                processed += 1
            else:
                pending += 1
    if processed:
        clear_portfolio_cache()
    return {
        "settings": settings,
        "checked": checked,
        "discovered": discovered,
        "processed": processed,
        "pending": pending,
        "skipped": skipped,
        "status": statuses,
    }


def backup_schedule_summary(backup: dict[str, Any]) -> str:
    config_out = backup_schedule_config(backup.get("schedule_config"), backup.get("schedule") or "")
    time_label = f"{config_out['hour']:02d}:{config_out['minute']:02d}"
    if config_out["frequency"] == "daily":
        return f"Daily at {time_label}"
    if config_out["frequency"] == "monthly":
        days = ", ".join(str(day) for day in config_out["month_days"])
        return f"Monthly on day {days} at {time_label}"
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    days = ", ".join(names[day] for day in config_out["weekdays"])
    return f"{days} at {time_label}"


def ghostfolio_holdings_synced():
    client = GhostfolioClient(config.db)
    holdings, ghostfolio_status = client.load_holdings()
    if not ghostfolio_status.get("ghostfolio", "").startswith("ok"):
        return holdings, ghostfolio_status, {"accounts": 0, "positions": 0, "updated_positions": 0, "attached_positions": 0}
    account_cash, account_status = client.load_account_cash()
    ghostfolio_status = {**ghostfolio_status, **account_status}
    source_transactions, order_status = client.load_order_transactions() if hasattr(client, "load_order_transactions") else ([], {"source_orders": "not supported"})
    ghostfolio_status = {**ghostfolio_status, **order_status}
    price_history, price_status = client.load_market_history(holdings, HISTORY_START_DATE) if hasattr(client, "load_market_history") else ([], {"source_price_history": "not supported"})
    ghostfolio_status = {**ghostfolio_status, **price_status}
    sync = local_store.import_ghostfolio(holdings, account_cash, source_transactions)
    sync["price_history"] = local_store.import_price_history(price_history)["prices"] if hasattr(local_store, "import_price_history") else 0
    sync["history_pruned"] = local_store.delete_history_before(HISTORY_START_DATE) if hasattr(local_store, "delete_history_before") else {"prices": 0, "account_snapshots": 0}
    local_store.capture_daily_snapshots()
    return holdings, ghostfolio_status, sync


def analyze_all():
    return enriched_local_holdings()


def enriched_local_holdings():
    analyses = local_store.holdings()
    enriched = []
    market_hub = hub()
    for local_analysis in analyses:
        if local_analysis.holding.data_source == "MANUAL":
            enriched.append(local_analysis)
            continue
        provider_analysis = analyze_holding(local_analysis.holding, market_hub)
        if "price history" in provider_analysis.missing and "price history" not in local_analysis.missing:
            provider_analysis.missing = [item for item in provider_analysis.missing if item != "price history"]
            provider_analysis.price_ranges = local_analysis.price_ranges
            provider_analysis.moving_averages = local_analysis.moving_averages
            provider_analysis.support_resistance = local_analysis.support_resistance
            provider_analysis.volume = local_analysis.volume
        provider_analysis.provider_status = {**local_analysis.provider_status, **provider_analysis.provider_status}
        enriched.append(provider_analysis)
    return enriched


def portfolio_payload(force_refresh: bool = False) -> dict[str, Any]:
    global _portfolio_cache
    signature = portfolio_cache_signature()
    now = time.time()
    with _portfolio_cache_lock:
        cached = _portfolio_cache or read_portfolio_cache()
        if (
            not force_refresh
            and cached
            and signature
            and cached.get("signature") == signature
            and float(cached.get("expires_at") or 0) > now
        ):
            _portfolio_cache = cached
            payload = cached.get("payload") or {}
            payload["status"] = {**payload.get("status", {}), "portfolio_cache": "hit"}
            return payload

    analyses = enriched_local_holdings()
    local_status = f"ok ({len(analyses)} local positions)"
    payload = {
        "status": {"local_portfolio": local_status, "portfolio_cache": "refreshed"},
        "count": len(analyses),
        "display_currencies": config.dashboard.get("display_currencies", []),
        "items": [to_dict(item) for item in analyses],
    }
    if signature:
        cache_record = {
            "signature": signature,
            "expires_at": now + portfolio_cache_ttl_seconds(),
            "payload": payload,
        }
        with _portfolio_cache_lock:
            _portfolio_cache = cache_record
            write_portfolio_cache(cache_record)
    return payload


def portfolio_cache_signature() -> str | None:
    if not hasattr(local_store, "change_token"):
        return None
    return f"v6:{local_store.change_token()}"


def read_portfolio_cache() -> dict[str, Any] | None:
    path = portfolio_cache_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def write_portfolio_cache(cache_record: dict[str, Any]) -> None:
    portfolio_cache_path().write_text(json.dumps(cache_record, default=str))


def clear_portfolio_cache() -> None:
    global _portfolio_cache
    with _portfolio_cache_lock:
        _portfolio_cache = None
    try:
        portfolio_cache_path().unlink()
    except OSError:
        pass


@app.on_event("startup")
def startup():
    global scheduler
    local_store.delete_history_before(HISTORY_START_DATE)
    local_store.capture_daily_snapshots()
    if scheduler is None:
        scheduler = start_scheduler(alert_store, _run_portfolio_alerts, config.alerts, local_store.capture_daily_snapshots)
    configure_backup_job()
    configure_dividend_job()


@app.on_event("shutdown")
def shutdown():
    if scheduler:
        scheduler.shutdown(wait=False)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": __version__,
        "config_path": str(config.path),
        "https_port": config.dashboard.get("https_port", 6443),
        "display_currencies": config.dashboard.get("display_currencies", []),
        "cache": hub().cache_status(),
        "local_db": local_store.status(),
    }


@app.get("/api/about")
def about():
    return {
        "name": "Portfolio Analyzer",
        "version": __version__,
        "python": "3.14",
        "features": [
            "Local portfolio database",
            "Manual instruments and transactions",
            "Manual historical prices",
            "Daily history and backups",
            "Market-data cache",
        ],
    }


@app.get("/api/portfolio")
def portfolio(refresh: bool = False):
    return portfolio_payload(force_refresh=refresh)


@app.post("/api/screener")
def screener(criteria: dict[str, Any]):
    results = screen(analyze_all(), criteria or {})
    return {"count": len(results), "items": [to_dict(item) for item in results]}


@app.get("/api/finance-reports/{symbol}")
def finance_report(symbol: str, limit: int = 6):
    return _finance_report_payload(symbol, limit)


@app.get("/api/company-outlook/predictions")
def company_outlook_predictions(symbol: str = ""):
    return {"items": local_store.list_company_report_predictions(symbol), "scorecard": local_store.company_report_scorecard()}


@app.delete("/api/company-outlook/predictions/{prediction_id}")
def delete_company_outlook_prediction(prediction_id: str):
    try:
        return local_store.delete_company_report_prediction(prediction_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/company-outlook/predictions/{prediction_id}/evaluate")
def evaluate_company_outlook_prediction(prediction_id: str):
    prediction = next((item for item in local_store.list_company_report_predictions() if item["id"] == prediction_id), None)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return _evaluate_prediction(prediction)


@app.get("/api/company-outlook/scorecard")
def company_outlook_scorecard():
    return local_store.company_report_scorecard()


@app.post("/api/company-outlook/backtests/batch")
def company_outlook_backtest_batch(payload: dict[str, Any] | None = None):
    try:
        return _company_outlook_backtest_batch(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/company-outlook/{symbol}/backtest")
def company_outlook_backtest(symbol: str, payload: dict[str, Any] | None = None):
    try:
        return _company_outlook_backtest(symbol, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/company-outlook/{symbol}")
def company_outlook(symbol: str, payload: dict[str, Any] | None = None):
    try:
        return _company_outlook_payload(symbol, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/local/options")
def local_options():
    return {
        "account_types": ACCOUNT_TYPES,
        "fund_kinds": FUND_KINDS,
        "asset_classes": ASSET_CLASSES,
        "instrument_types": INSTRUMENT_TYPES,
        "option_types": OPTION_TYPES,
        "issuer_listing_statuses": ISSUER_LISTING_STATUSES,
    }


@app.post("/api/local/import/ghostfolio")
def import_ghostfolio():
    _, ghostfolio_status, sync = ghostfolio_holdings_synced()
    clear_portfolio_cache()
    return {**sync, "source": ghostfolio_status.get("ghostfolio", "not imported")}


@app.post("/api/local/import/source")
def import_source():
    return import_ghostfolio()


@app.get("/api/local/accounts")
def list_local_accounts():
    return {"items": local_store.list_accounts(), "status": local_store.status()}


@app.get("/api/local/brokers")
def list_brokers():
    return {"items": local_store.list_brokers()}


@app.post("/api/local/brokers")
def save_broker(payload: dict[str, Any]):
    try:
        result = local_store.save_broker(payload or {})
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/local/brokers/{broker_id}")
def delete_broker(broker_id: str):
    try:
        deleted = local_store.delete_broker(broker_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Broker not found")
    clear_portfolio_cache()
    return {"deleted": True}


@app.get("/api/local/family-members")
def list_family_members():
    return {"items": local_store.list_family_members()}


@app.post("/api/local/family-members")
def save_family_member(payload: dict[str, Any]):
    try:
        return local_store.save_family_member(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/local/family-members/{member_id}")
def delete_family_member(member_id: str):
    try:
        deleted = local_store.delete_family_member(member_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Family member not found")
    return {"deleted": True}


@app.post("/api/local/accounts")
def save_local_account(payload: dict[str, Any]):
    try:
        result = local_store.save_account(payload or {})
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/local/accounts/{account_id}")
def delete_local_account(account_id: str):
    if not local_store.delete_account(account_id):
        raise HTTPException(status_code=404, detail="Account not found")
    clear_portfolio_cache()
    return {"deleted": True}


@app.get("/api/local/securities")
def list_local_securities():
    return {"items": local_store.list_transactions()}


@app.post("/api/local/securities")
def add_local_security(payload: dict[str, Any]):
    payload = payload or {}
    symbol = str(payload.get("symbol") or "").strip()
    stock_market = str(payload.get("stock_market") or "").strip()
    allow_manual = bool(payload.get("allow_manual"))
    security_id = str(payload.get("security_id") or "").strip()
    known_manual = bool(security_id and local_store.manual_security_by_id(security_id)) or local_store.manual_security_exists(symbol, stock_market)
    if symbol and stock_market and not security_id:
        payload["stock_market"], _status = _resolve_supported_stock_market(symbol, stock_market, allow_manual, known_manual)
    try:
        result = local_store.add_transaction(payload)
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/local/securities/{transaction_id}")
def update_local_security(transaction_id: str, payload: dict[str, Any]):
    payload = payload or {}
    symbol = str(payload.get("symbol") or "").strip()
    stock_market = str(payload.get("stock_market") or "").strip()
    allow_manual = bool(payload.get("allow_manual"))
    security_id = str(payload.get("security_id") or "").strip()
    known_manual = bool(security_id and local_store.manual_security_by_id(security_id)) or local_store.manual_security_exists(symbol, stock_market)
    if symbol and stock_market and not security_id:
        payload["stock_market"], _status = _resolve_supported_stock_market(symbol, stock_market, allow_manual, known_manual)
    try:
        result = local_store.update_transaction(transaction_id, payload)
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc


@app.get("/api/local/manual-securities")
def list_manual_securities():
    return {"items": local_store.list_manual_securities()}


@app.post("/api/local/manual-securities")
def save_manual_security(payload: dict[str, Any]):
    try:
        result = local_store.save_manual_security(payload or {})
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/local/manual-securities/{security_id}")
def delete_manual_security(security_id: str):
    try:
        if not local_store.delete_manual_security(security_id):
            raise HTTPException(status_code=404, detail="Manual instrument not found")
        clear_portfolio_cache()
        return {"deleted": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/local/employee-option-grants")
def list_employee_option_grants():
    return {"items": local_store.list_employee_option_grants()}


@app.post("/api/local/employee-option-grants")
def save_employee_option_grant(payload: dict[str, Any]):
    try:
        result = local_store.save_employee_option_grant(payload or {})
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/local/employee-option-grants/{security_id}")
def update_employee_option_grant(security_id: str, payload: dict[str, Any]):
    try:
        result = local_store.save_employee_option_grant({**(payload or {}), "security_id": security_id})
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc


@app.delete("/api/local/employee-option-grants/{security_id}")
def delete_employee_option_grant(security_id: str):
    try:
        if not local_store.delete_employee_option_grant(security_id):
            raise HTTPException(status_code=404, detail="Employee option grant not found")
        clear_portfolio_cache()
        return {"deleted": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/local/equity-transitions")
def list_equity_transitions():
    return {"items": local_store.list_equity_transitions()}


@app.post("/api/local/manual-securities/{security_id}/link-listing")
def link_employee_option_listing(security_id: str, payload: dict[str, Any]):
    payload = payload or {}
    symbol = str(payload.get("public_symbol") or "").strip()
    market = str(payload.get("public_market") or "").strip()
    if symbol and market:
        payload["public_market"], _status = _resolve_supported_stock_market(
            symbol,
            market,
            bool(payload.get("allow_manual")),
            False,
        )
    try:
        result = local_store.link_employee_option_listing(security_id, payload)
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/local/manual-securities/{security_id}/exercise")
def exercise_employee_option(security_id: str, payload: dict[str, Any]):
    try:
        result = local_store.exercise_employee_option(security_id, payload or {})
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/local/securities/{transaction_id}")
def delete_local_security(transaction_id: str):
    try:
        if not local_store.delete_transaction(transaction_id):
            raise HTTPException(status_code=404, detail="Security transaction not found")
        clear_portfolio_cache()
        return {"deleted": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/local/events")
def list_local_events():
    return {"items": local_store.list_events(), "dividends": dividend_status()}


@app.post("/api/local/events/dividends/run")
def run_dividend_events():
    try:
        result = process_portfolio_dividends(force_refresh=True)
        return {**result, "items": local_store.list_events()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/local/prices")
def list_local_prices():
    return {"items": local_store.list_prices()}


@app.get("/api/security/history")
def security_history(symbol: str, stock_market: str = "", period: str = "1y", date_from: str = "", level_periods: str = ""):
    days_by_period = {"1m": 31, "6m": 183, "1y": 366, "3y": 366 * 3, "5y": 366 * 5}
    days = days_by_period.get(period, days_by_period["1y"])
    requested_level_periods = [item.strip().lower() for item in level_periods.split(",") if item.strip()]
    level_days = [days_by_period[item] for item in requested_level_periods if item in days_by_period]
    analysis_days = max([days, *level_days])
    to_date = date.today()
    period_start = to_date - timedelta(days=days)
    from_date = _clamped_history_start(date_from, HISTORY_START_DATE if not date_from else period_start)
    analysis_from_date = _clamped_history_start((to_date - timedelta(days=analysis_days)).isoformat())
    fetch_from_date = min(from_date, analysis_from_date)
    local_rows = local_store.price_history(symbol, stock_market, fetch_from_date, to_date)
    local_prices = [_local_price_ohlcv(row) for row in local_rows]
    local_chart_prices = [row for row in local_prices if row.date >= from_date]
    if local_store.manual_security_exists(symbol, stock_market):
        return _security_history_response(symbol, stock_market, period, "manual", local_chart_prices, local_prices)
    prices, status = hub().prices(symbol, fetch_from_date, to_date)
    if len(local_prices) >= len(prices):
        return _security_history_response(symbol, stock_market, period, "local", local_chart_prices, local_prices)
    by_date = {row.date.isoformat(): row for row in prices}
    by_date.update({row.date.isoformat(): row for row in local_prices})
    merged = [by_date[day] for day in sorted(by_date)]
    chart_prices = [row for row in merged if row.date >= from_date]
    return _security_history_response(symbol, stock_market, period, "merged", chart_prices, merged, status)


@app.post("/api/local/prices")
def save_local_price(payload: dict[str, Any]):
    try:
        return local_store.save_price(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/local/prices/{price_id}")
def delete_local_price(price_id: str):
    if not local_store.delete_price(price_id):
        raise HTTPException(status_code=404, detail="Price not found")
    return {"deleted": True}


@app.get("/api/local/account-trends")
def local_account_trends(account_id: str = "", account_type: str = "", location: str = "", date_from: str = "", date_to: str = ""):
    from_date = _clamped_history_start(date_from)
    to_date = _parse_query_date(date_to) or date.today()
    if to_date < from_date:
        to_date = from_date
    return local_store.account_trends(
        {
            "account_id": account_id,
            "account_type": account_type,
            "location": location,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        }
    )


@app.get("/api/local/account-snapshots")
def list_account_snapshots(account_id: str = "", date_from: str = "", date_to: str = ""):
    from_date = _clamped_history_start(date_from)
    to_date = _parse_query_date(date_to) or date.today()
    if to_date < from_date:
        to_date = from_date
    return {"items": local_store.list_account_snapshots({"account_id": account_id, "from": from_date.isoformat(), "to": to_date.isoformat()})}


@app.post("/api/local/account-snapshots")
def save_account_snapshot(payload: dict[str, Any]):
    payload = payload or {}
    snapshot_day = _parse_query_date(payload.get("snapshot_date") or payload.get("date") or "")
    if snapshot_day and snapshot_day < HISTORY_START_DATE:
        raise HTTPException(status_code=400, detail=f"Account history starts at {HISTORY_START_DATE.isoformat()}")
    try:
        return local_store.save_account_snapshot(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/local/account-snapshots/capture")
def capture_account_snapshots(payload: dict[str, Any] | None = None):
    snapshot_day = _parse_query_date((payload or {}).get("snapshot_date") or (payload or {}).get("date") or "")
    if snapshot_day and snapshot_day < HISTORY_START_DATE:
        raise HTTPException(status_code=400, detail=f"Account history starts at {HISTORY_START_DATE.isoformat()}")
    return local_store.capture_daily_snapshots(snapshot_day)


@app.delete("/api/local/account-snapshots/{account_id}/{snapshot_date}")
def delete_account_snapshot(account_id: str, snapshot_date: str):
    if not local_store.delete_account_snapshot(account_id, snapshot_date):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"deleted": True}


@app.get("/api/local/reports")
def local_reports(account_id: str = "", account_type: str = "", location: str = ""):
    return local_store.reports({"account_id": account_id, "account_type": account_type, "location": location})


@app.get("/api/local/funds")
def list_local_funds():
    return {"items": local_store.list_funds()}


@app.post("/api/local/funds")
def save_local_fund(payload: dict[str, Any]):
    try:
        result = local_store.save_fund(payload or {})
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/local/funds/{fund_id}/amount-history")
def list_local_fund_amount_history(fund_id: str):
    try:
        items = local_store.list_fund_amount_history(fund_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    fund = next((item for item in local_store.list_funds() if item["id"] == fund_id), None)
    if not fund:
        raise HTTPException(status_code=404, detail="Fund record not found")
    return {"fund": fund, "items": items}


@app.post("/api/local/funds/{fund_id}/amount-history")
def save_local_fund_amount_history(fund_id: str, payload: dict[str, Any]):
    try:
        result = local_store.save_fund_amount_history(fund_id, payload or {})
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/local/funds/{fund_id}/amount-history/{history_id}")
def update_local_fund_amount_history(fund_id: str, history_id: str, payload: dict[str, Any]):
    try:
        result = local_store.save_fund_amount_history(fund_id, payload or {}, history_id)
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/local/funds/{fund_id}/amount-history/{history_id}")
def delete_local_fund_amount_history(fund_id: str, history_id: str):
    if not local_store.delete_fund_amount_history(fund_id, history_id):
        raise HTTPException(status_code=404, detail="Fund history point not found")
    clear_portfolio_cache()
    return {"deleted": True}


@app.post("/api/local/pension-simulate")
def simulate_pension(payload: dict[str, Any]):
    try:
        return local_store.simulate_pension(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/local/funds/{fund_id}")
def delete_local_fund(fund_id: str):
    if not local_store.delete_fund(fund_id):
        raise HTTPException(status_code=404, detail="Fund record not found")
    clear_portfolio_cache()
    return {"deleted": True}


@app.get("/api/fx")
def fx():
    pairs = [item for item in config.dashboard.get("display_currencies", []) if "/" in item]
    quotes = []
    for pair in pairs:
        quote, status = hub().fx(pair)
        quotes.append({"pair": pair, "quote": quote, "status": status})
    return {"quotes": quotes}


def _default_banner_items() -> list[dict[str, str]]:
    return [
        {"label": "USD/ILS", "type": "fx", "symbol": "USD/ILS"},
        {"label": "EUR/ILS", "type": "fx", "symbol": "EUR/ILS"},
    ]


def _configured_banner_items() -> list[dict[str, Any]]:
    items = config.dashboard.get("banner_items") or _default_banner_items()
    return [item for item in items if isinstance(item, dict) and item.get("symbol")]


def _resolve_banner_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved = []
    for item in items[:24]:
        symbol = str(item.get("symbol") or "").strip()
        if not symbol:
            continue
        item_type = str(item.get("type") or ("fx" if "/" in symbol else "quote")).lower()
        if item_type == "fx":
            quote, status = hub().fx(symbol)
            value = quote.get("rate")
            timestamp = quote.get("time")
        else:
            quote, status = hub().quote(symbol)
            value = quote.get("price")
            timestamp = quote.get("time")
        resolved.append(
            {
                "label": item.get("label") or symbol,
                "type": item_type,
                "symbol": symbol,
                "value": value,
                "currency": quote.get("currency"),
                "change": quote.get("change"),
                "changes_percentage": quote.get("changes_percentage"),
                "time": timestamp,
                "status": status,
            }
        )
    return resolved


@app.get("/api/banner")
def banner():
    items = _configured_banner_items()
    return {"configured": items, "items": _resolve_banner_items(items)}


@app.post("/api/banner/resolve")
def resolve_banner(payload: dict[str, Any]):
    items = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    return {"items": _resolve_banner_items(items)}


@app.get("/api/cache")
def cache_status():
    return hub().cache_status()


@app.get("/api/settings")
def settings_status():
    return {
        "cache": hub().cache_status(),
        "local_db": local_store.status(),
        "backup": backup_status(),
        "dividends": dividend_status(),
    }


@app.put("/api/settings/backup")
def update_backup_settings(payload: dict[str, Any]):
    payload = payload or {}
    settings = load_runtime_settings()
    backup = {**default_backup_settings(), **settings.get("backup", {})}
    if "enabled" in payload:
        backup["enabled"] = bool(payload.get("enabled"))
    if "schedule_config" in payload:
        backup["schedule_config"] = backup_schedule_config(payload.get("schedule_config"))
        backup["schedule"] = backup_cron_from_config(backup["schedule_config"])
    if "schedule" in payload:
        schedule = str(payload.get("schedule") or "").strip()
        if len(schedule.split()) != 5:
            raise HTTPException(status_code=400, detail="Backup schedule must be a 5-field cron expression")
        backup["schedule"] = schedule
        backup["schedule_config"] = backup_schedule_config_from_cron(schedule)
    if "missed_policy" in payload:
        policy = str(payload.get("missed_policy") or "wait")
        backup["missed_policy"] = policy if policy in {"wait", "run"} else "wait"
    if "timezone" in payload:
        backup["timezone"] = str(payload.get("timezone") or "UTC").strip() or "UTC"
    if "keep" in payload:
        backup["keep"] = max(int(payload.get("keep") or 1), 1)
    settings["backup"] = backup
    save_runtime_settings(settings)
    local_store.set_preference(BACKUP_SETTINGS_PREF_KEY, backup)
    try:
        configure_backup_job()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return backup_status()


@app.get("/api/settings/client-state")
def get_client_state():
    state = local_store.get_preference(CLIENT_STATE_PREF_KEY, {})
    return {"state": state if isinstance(state, dict) else {}}


@app.put("/api/settings/client-state")
def save_client_state(payload: dict[str, Any]):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Client state must be an object")
    return local_store.set_preference(CLIENT_STATE_PREF_KEY, payload)


@app.get("/api/local/export")
def export_local_data():
    data = local_store.export_data()
    filename = f"portfolio-data-{data['exported_at'][:10]}.json"
    return Response(
        content=json.dumps(data, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/local/import")
def import_local_data(payload: dict[str, Any]):
    try:
        result = local_store.import_data(payload or {})
        restore_backup_settings_from_preferences()
        local_store.capture_daily_snapshots()
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/local/backups")
def list_local_backups():
    return {"backup": backup_status()}


@app.get("/api/local/backups.zip")
def download_local_backups_zip():
    return backup_archive_response()


@app.get("/api/local/backups/{filename}")
def download_local_backup(filename: str):
    path = backup_download_path(filename)
    return FileResponse(path, media_type="application/json", filename=path.name)


@app.post("/api/local/backups")
def run_local_backup():
    backup = load_runtime_settings()["backup"]
    return write_runtime_backup(int(backup.get("keep") or 100))


MARKET_SCREENER_FINANCIAL_FILTERS = {
    "annualNetIncomeMoreThan",
    "profitMarketCapMoreThan",
    "profitMarketCapLowerThan",
    "priceEarningsLowerThan",
    "revenueGrowthMoreThan",
    "netIncomeGrowthMoreThan",
    "netMarginMoreThan",
    "freeCashFlowMoreThan",
    "freeCashFlowYieldMoreThan",
    "debtRevenueLowerThan",
    "currentRatioMoreThan",
}

MARKET_SCREENER_NUMERIC_FILTERS = {
    "priceMoreThan": ("price", "min", "minimum price"),
    "priceLowerThan": ("price", "max", "maximum price"),
    "marketCapMoreThan": ("market_cap", "min", "minimum market cap"),
    "marketCapLowerThan": ("market_cap", "max", "maximum market cap"),
    "dividendYieldMoreThan": ("dividend_yield_percent", "min", "minimum dividend yield"),
    "dividendYieldLowerThan": ("dividend_yield_percent", "max", "maximum dividend yield"),
    "annualNetIncomeMoreThan": ("annual_net_income", "min", "minimum annual net profit"),
    "profitMarketCapMoreThan": ("profit_market_cap_percent", "min", "minimum profit / market cap"),
    "profitMarketCapLowerThan": ("profit_market_cap_percent", "max", "maximum profit / market cap"),
    "priceEarningsLowerThan": ("price_earnings_ratio", "max", "maximum P/E"),
    "revenueGrowthMoreThan": ("revenue_growth_percent", "min", "minimum revenue growth"),
    "netIncomeGrowthMoreThan": ("net_income_growth_percent", "min", "minimum profit growth"),
    "netMarginMoreThan": ("net_margin_percent", "min", "minimum net margin"),
    "freeCashFlowMoreThan": ("free_cash_flow", "min", "minimum free cash flow"),
    "freeCashFlowYieldMoreThan": ("free_cash_flow_yield_percent", "min", "minimum free-cash-flow yield"),
    "debtRevenueLowerThan": ("debt_to_revenue_percent", "max", "maximum debt / revenue"),
    "currentRatioMoreThan": ("current_ratio", "min", "minimum current ratio"),
    "betaLowerThan": ("beta", "max", "maximum beta"),
    "volumeMoreThan": ("volume", "min", "minimum volume"),
}

MARKET_SCREENER_SORT_FIELDS = {
    "market_cap": "market_cap",
    "dividend_yield": "dividend_yield_percent",
    "annual_profit": "annual_net_income",
    "profit_market_cap": "profit_market_cap_percent",
    "revenue_growth": "revenue_growth_percent",
    "profit_growth": "net_income_growth_percent",
    "net_margin": "net_margin_percent",
    "free_cash_flow": "free_cash_flow",
    "price": "price",
    "beta": "beta",
    "symbol": "symbol",
}


def _market_screener_number(criteria: dict[str, Any], key: str) -> float | None:
    return _number_or_none(criteria.get(key))


def _market_screener_needs_financials(criteria: dict[str, Any]) -> bool:
    return bool(str(criteria.get("query") or "").strip()) or any(_market_screener_number(criteria, key) is not None for key in MARKET_SCREENER_FINANCIAL_FILTERS)


def _market_screener_annual_dividend(rows: list[dict[str, Any]]) -> float | None:
    dated: list[tuple[date, float]] = []
    undated: list[float] = []
    cutoff = date.today() - timedelta(days=370)
    for row in rows or []:
        amount = _number_or_none(row.get("amount") or row.get("dividend") or row.get("adjDividend"))
        if amount is None:
            continue
        paid_on = _parse_query_date(str(row.get("date") or row.get("paymentDate") or row.get("exDate") or ""))
        if paid_on:
            dated.append((paid_on, amount))
        else:
            undated.append(amount)
    if dated:
        recent = [amount for paid_on, amount in dated if paid_on >= cutoff]
        return sum(recent) if recent else None
    return sum(undated[:4]) if undated else None


def _enrich_market_screener_item(item: dict[str, Any], provider_hub: MarketDataHub, need_dividend_history: bool) -> tuple[dict[str, Any], bool]:
    enriched = dict(item)
    symbol = str(item.get("symbol") or "").upper().strip()
    if not symbol:
        return enriched, False
    report = _finance_report_payload(symbol, 2)
    latest = report.get("latest") or {}
    profile = report.get("profile") or {}
    price = _number_or_none(enriched.get("price"))
    market_cap = _number_or_none(enriched.get("market_cap"))
    quote: dict[str, Any] = {}
    if price is None or market_cap is None:
        quote, _quote_status = provider_hub.quote(symbol)
        price = price if price is not None else _number_or_none(quote.get("price"))
        market_cap = market_cap if market_cap is not None else _number_or_none(quote.get("market_cap") or quote.get("marketCap"))
    market_cap = market_cap if market_cap is not None else _number_or_none(profile.get("market_cap") or profile.get("marketCap") or profile.get("mktCap") or profile.get("marketCapitalization"))
    shares = _number_or_none(profile.get("shares_outstanding") or profile.get("sharesOutstanding"))
    if market_cap is None and price is not None and shares is not None:
        market_cap = price * shares
    annual_dividend = _number_or_none(enriched.get("dividend"))
    if annual_dividend is None and need_dividend_history:
        dividends, _dividend_status = provider_hub.dividends(symbol)
        annual_dividend = _market_screener_annual_dividend(dividends)
    annual_net_income = _number_or_none(latest.get("net_income"))
    free_cash_flow = _number_or_none(latest.get("free_cash_flow"))
    enriched.update(
        {
            "name": enriched.get("name") or profile.get("name") or quote.get("name"),
            "exchange": enriched.get("exchange") or profile.get("exchange") or quote.get("exchange"),
            "currency": enriched.get("currency") or profile.get("currency") or quote.get("currency") or "USD",
            "sector": enriched.get("sector") or profile.get("sector"),
            "industry": enriched.get("industry") or profile.get("industry"),
            "country": enriched.get("country") or profile.get("country"),
            "beta": _number_or_none(enriched.get("beta")) if _number_or_none(enriched.get("beta")) is not None else _number_or_none(profile.get("beta")),
            "price": price,
            "market_cap": market_cap,
            "annual_dividend": annual_dividend,
            "dividend_yield_percent": (annual_dividend / price * 100) if annual_dividend is not None and price not in (None, 0) else None,
            "fiscal_year": latest.get("fiscal_year"),
            "annual_revenue": _number_or_none(latest.get("revenue")),
            "annual_net_income": annual_net_income,
            "profit_market_cap_percent": (annual_net_income / market_cap * 100) if annual_net_income is not None and market_cap not in (None, 0) else None,
            "price_earnings_ratio": (market_cap / annual_net_income) if annual_net_income is not None and annual_net_income > 0 and market_cap is not None else None,
            "revenue_growth_percent": _number_or_none(latest.get("revenue_growth_percent")),
            "net_income_growth_percent": _number_or_none(latest.get("net_income_growth_percent")),
            "net_margin_percent": _number_or_none(latest.get("net_margin_percent")),
            "free_cash_flow": free_cash_flow,
            "free_cash_flow_yield_percent": (free_cash_flow / market_cap * 100) if free_cash_flow is not None and market_cap not in (None, 0) else None,
            "debt_to_revenue_percent": _number_or_none(latest.get("debt_to_revenue_percent")),
            "current_ratio": _number_or_none(latest.get("current_ratio")),
            "statement_coverage": report.get("statement_coverage") or {},
            "missing": report.get("missing") or [],
        }
    )
    has_financials = annual_net_income is not None or enriched.get("annual_revenue") is not None
    return enriched, has_financials


def _alert_current_price(analysis: Any) -> float | None:
    for period in ["1m", "6m", "1y", "3y", "5y"]:
        value = _number_or_none((analysis.price_ranges.get(period) or {}).get("current"))
        if value is not None:
            return value
    return _number_or_none((analysis.support_resistance.get("1m") or {}).get("current_price"))


def _portfolio_alert_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    analyses = analyze_all()
    grouped: dict[str, dict[str, Any]] = {}
    for analysis in analyses:
        holding = analysis.holding
        asset_class = str(holding.asset_class or holding.asset_sub_class or "").upper()
        if str(holding.account_type or "").upper() == "ESOP" or asset_class in {"RSU", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION"}:
            continue
        symbol = str(holding.symbol or "").upper().strip()
        if not symbol:
            continue
        group = grouped.setdefault(
            symbol,
            {
                "analysis": analysis,
                "name": holding.name or symbol,
                "currency": holding.currency,
                "market_value": 0.0,
                "cost_basis": 0.0,
                "unrealized_profit": 0.0,
                "accounts": set(),
                "missing": set(),
            },
        )
        group["market_value"] += float(holding.market_value or 0)
        group["cost_basis"] += float(holding.cost_basis or 0)
        group["unrealized_profit"] += float(holding.unrealized_profit or 0)
        if holding.account:
            group["accounts"].add(str(holding.account))
        group["missing"].update(analysis.missing or [])
    provider_hub = hub()
    base_currency = str(config.dashboard.get("base_currency") or "ILS").upper()
    provider_errors: list[dict[str, str]] = []
    fx_rates: dict[str, float] = {base_currency: 1.0}
    for currency in sorted({str(group["currency"] or base_currency).upper() for group in grouped.values()}):
        if currency == base_currency:
            continue
        pair = f"{currency}/{base_currency}"
        try:
            quote, _status = provider_hub.fx(pair)
            rate = _number_or_none(quote.get("rate"))
        except Exception as exc:
            rate = None
            provider_errors.append({"symbol": pair, "error": type(exc).__name__})
        if rate is None or rate <= 0:
            if not any(error["symbol"] == pair for error in provider_errors):
                provider_errors.append({"symbol": pair, "error": "missing FX rate"})
            continue
        fx_rates[currency] = rate
    allocation_data_complete = all(str(group["currency"] or base_currency).upper() in fx_rates for group in grouped.values())
    total_market_value = sum(
        max(float(group["market_value"]), 0) * fx_rates.get(str(group["currency"] or base_currency).upper(), 0)
        for group in grouped.values()
    )
    rows: list[dict[str, Any]] = []
    enrichment_errors = 0
    for symbol, group in grouped.items():
        analysis = group["analysis"]
        current_price = _alert_current_price(analysis)
        base = {
            "symbol": symbol,
            "name": group["name"],
            "currency": group["currency"],
            "price": current_price,
            "market_cap": analysis.market_cap,
            "sector": analysis.holding.sector,
            "industry": analysis.industry or analysis.holding.industry,
        }
        try:
            row, _has_financials = _enrich_market_screener_item(base, provider_hub, True)
        except Exception as exc:
            row = base
            enrichment_errors += 1
            provider_errors.append({"symbol": symbol, "error": type(exc).__name__})
        one_year = analysis.price_ranges.get("1y") or {}
        ma30 = analysis.moving_averages.get("30") or {}
        market_cap = _number_or_none(row.get("market_cap"))
        annual_profit = _number_or_none(row.get("annual_net_income"))
        free_cash_flow = _number_or_none(row.get("free_cash_flow"))
        cost_basis = float(group["cost_basis"] or 0)
        currency = str(group["currency"] or base_currency).upper()
        normalized_market_value = float(group["market_value"]) * fx_rates.get(currency, 0)
        row.update(
            {
                "accounts": sorted(group["accounts"]),
                "market_value": float(group["market_value"]),
                "unrealized_profit": float(group["unrealized_profit"]),
                "unrealized_profit_percent": (float(group["unrealized_profit"]) / abs(cost_basis) * 100) if cost_basis else None,
                "holding_allocation_percent": (normalized_market_value / total_market_value * 100) if allocation_data_complete and total_market_value else None,
                "market_cap_millions": market_cap / 1_000_000 if market_cap is not None else None,
                "annual_net_income_millions": annual_profit / 1_000_000 if annual_profit is not None else None,
                "free_cash_flow_millions": free_cash_flow / 1_000_000 if free_cash_flow is not None else None,
                "dividend_growth_percent": analysis.dividend_trend.percent_change,
                "price_vs_ma30_percent": _number_or_none(ma30.get("price_vs_ma_percent")),
                "price_from_high_1y_percent": _number_or_none(one_year.get("percent_from_high")),
                "missing": sorted(set(group["missing"]) | set(row.get("missing") or [])),
            }
        )
        rows.append(row)
    return rows, {
        "portfolio_symbols": len(grouped),
        "enriched_symbols": len(rows) - enrichment_errors,
        "provider_errors": provider_errors,
        "allocation_currency": base_currency,
    }


def _run_portfolio_alerts() -> list[dict[str, Any]]:
    if not any(rule.get("enabled", True) for rule in alert_store.list_rules()):
        return alert_store.evaluate([], {"status": "no enabled rules", "portfolio_symbols": 0})
    try:
        rows, metadata = _portfolio_alert_rows()
        return alert_store.evaluate(rows, metadata)
    except Exception as exc:
        alert_store.record_failure(
            f"Rule check failed: {type(exc).__name__}",
            {"error_type": type(exc).__name__},
        )
        return []


def _market_screener_basic_metrics(item: dict[str, Any]) -> dict[str, Any]:
    row = dict(item)
    price = _number_or_none(row.get("price"))
    annual_dividend = _number_or_none(row.get("annual_dividend") or row.get("dividend"))
    row["annual_dividend"] = annual_dividend
    row["dividend_yield_percent"] = (annual_dividend / price * 100) if annual_dividend is not None and price not in (None, 0) else None
    return row


def _market_screener_matches(item: dict[str, Any], criteria: dict[str, Any]) -> bool:
    include_missing = bool(criteria.get("includeMissing"))
    for criterion, (field, direction, _label) in MARKET_SCREENER_NUMERIC_FILTERS.items():
        threshold = _market_screener_number(criteria, criterion)
        if threshold is None:
            continue
        value = _number_or_none(item.get(field))
        if value is None:
            if not include_missing:
                return False
            continue
        if direction == "min" and value < threshold:
            return False
        if direction == "max" and value > threshold:
            return False
    for criterion, field in [("sector", "sector"), ("industry", "industry"), ("country", "country")]:
        expected = str(criteria.get(criterion) or "").strip().casefold()
        if not expected:
            continue
        actual = str(item.get(field) or "").strip().casefold()
        if not actual and include_missing:
            continue
        if expected not in actual:
            return False
    return True


def _market_screener_sort(items: list[dict[str, Any]], criteria: dict[str, Any]) -> list[dict[str, Any]]:
    raw_sort = str(criteria.get("sortBy") or "market_cap:desc").strip().lower()
    sort_name, _, sort_direction = raw_sort.partition(":")
    field = MARKET_SCREENER_SORT_FIELDS.get(sort_name, "market_cap")
    descending = sort_direction != "asc"
    if field == "symbol":
        return sorted(items, key=lambda item: str(item.get(field) or ""), reverse=descending)
    present = [item for item in items if _number_or_none(item.get(field)) is not None]
    missing = [item for item in items if _number_or_none(item.get(field)) is None]
    present.sort(key=lambda item: float(item[field]), reverse=descending)
    return present + missing


@app.post("/api/market/screener")
def market_screener(criteria: dict[str, Any]):
    criteria = criteria or {}
    requested_limit = min(max(int(_number_or_none(criteria.get("limit")) or 25), 1), 50)
    needs_financials = _market_screener_needs_financials(criteria)
    provider_criteria = {**criteria, "limit": min(max(requested_limit * (3 if needs_financials else 1), 10), 100)}
    provider_hub = hub()
    candidates, status = provider_hub.market_screener(provider_criteria)
    rows = [_market_screener_basic_metrics(item) for item in candidates]
    enrichment_limit = min(len(rows), 15 if needs_financials else 0)
    enriched_count = 0
    financial_rows = 0
    need_dividend_history = bool(str(criteria.get("query") or "").strip()) or any(
        _market_screener_number(criteria, key) is not None for key in {"dividendYieldMoreThan", "dividendYieldLowerThan"}
    )
    for index in range(enrichment_limit):
        rows[index], has_financials = _enrich_market_screener_item(rows[index], provider_hub, need_dividend_history)
        enriched_count += 1
        financial_rows += int(has_financials)
    matched = [item for item in rows if _market_screener_matches(item, criteria)]
    matched = _market_screener_sort(matched, criteria)
    filtered_count = len(matched)
    matched = matched[:requested_limit]
    active_filters = [label for key, (_field, _direction, label) in MARKET_SCREENER_NUMERIC_FILTERS.items() if _market_screener_number(criteria, key) is not None]
    if needs_financials:
        status = {**status, "financial_enrichment": f"ok ({financial_rows}/{enriched_count} with annual statements)"}
    return {
        "count": len(matched),
        "status": status,
        "items": matched,
        "meta": {
            "candidates": len(candidates),
            "matched_before_limit": filtered_count,
            "enriched": enriched_count,
            "financial_rows": financial_rows,
            "missing_financial_rows": max(enriched_count - financial_rows, 0),
            "filters_applied": active_filters,
            "include_missing": bool(criteria.get("includeMissing")),
            "latest_annual_reports": needs_financials,
        },
    }


@app.get("/api/alerts")
def list_alerts():
    rules = alert_store.list_rules()
    runs = alert_store.list_runs()
    job = scheduler.get_job(ALERT_JOB_ID) if scheduler else None
    active_signals = [match for rule in rules if rule.get("enabled", True) for match in rule.get("last_matches") or [] if isinstance(match, dict)]
    return {
        "rules": rules,
        "runs": runs,
        "active_signals": active_signals,
        "options": alert_rule_options(),
        "schedule": {
            "cron": str(config.alerts.get("schedule") or "0 7 * * *"),
            "timezone": str(config.alerts.get("timezone") or "UTC"),
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
        },
    }


@app.post("/api/alerts")
def create_alert(payload: dict[str, Any]):
    try:
        return alert_store.add_rule(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/alerts/{rule_id}")
def update_alert(rule_id: str, payload: dict[str, Any]):
    try:
        rule = alert_store.update_rule(rule_id, payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rule:
        raise HTTPException(status_code=404, detail="Alert not found")
    return rule


@app.delete("/api/alerts/{rule_id}")
def delete_alert(rule_id: str):
    if not alert_store.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"deleted": True}


@app.post("/api/alerts/run")
def run_alerts():
    results = _run_portfolio_alerts()
    return {"results": results, "state": list_alerts()}


web_dir = Path(__file__).resolve().parent.parent / "web"
app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
