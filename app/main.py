from __future__ import annotations

import json
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
from fastapi.staticfiles import StaticFiles

from . import __version__
from .alerts import AlertStore, start_scheduler
from .config import data_dir, load_config
from .ghostfolio import GhostfolioClient
from .local_portfolio import ACCOUNT_TYPES, ASSET_CLASSES, FUND_KINDS, INSTRUMENT_TYPES, OPTION_TYPES, LocalPortfolioStore
from .metrics import analyze_holding, screen, to_dict
from .providers import MarketDataHub


app = FastAPI(title="Portfolio Analyzer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

config = load_config()
alert_store = AlertStore()
local_store = LocalPortfolioStore()
scheduler = None
BACKUP_JOB_ID = "local-data-backup"
WEEKDAY_CRON = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PORTFOLIO_CACHE_FILE = "portfolio-analysis-cache.json"
HISTORY_START_DATE = date(2026, 4, 14)
_portfolio_cache_lock = RLock()
_portfolio_cache: dict[str, Any] | None = None


def _parse_query_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _clamped_history_start(value: str, fallback: date | None = None) -> date:
    requested = _parse_query_date(value) or fallback or HISTORY_START_DATE
    return max(requested, HISTORY_START_DATE)


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
        "keep": int(backup.get("keep", 30) or 30),
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
        lambda: local_store.write_backup(int(backup.get("keep") or 30)),
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
    return local_store.write_backup(int(backup.get("keep") or 30))


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
        "backups": backups[:10],
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
        scheduler = start_scheduler(alert_store, analyze_all, config.alerts, local_store.capture_daily_snapshots)
    configure_backup_job()


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


@app.get("/api/local/options")
def local_options():
    return {
        "account_types": ACCOUNT_TYPES,
        "fund_kinds": FUND_KINDS,
        "asset_classes": ASSET_CLASSES,
        "instrument_types": INSTRUMENT_TYPES,
        "option_types": OPTION_TYPES,
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


@app.post("/api/local/accounts")
def save_local_account(payload: dict[str, Any]):
    try:
        return local_store.save_account(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/local/accounts/{account_id}")
def delete_local_account(account_id: str):
    if not local_store.delete_account(account_id):
        raise HTTPException(status_code=404, detail="Account not found")
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
    known_manual = local_store.manual_security_exists(symbol, stock_market)
    if symbol and not allow_manual and not known_manual:
        quote, status = hub().quote(symbol)
        if not quote.get("price"):
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Symbol was not found through configured providers. Enable manual add to save it anyway.",
                    "manual_allowed": True,
                    "provider_status": status,
                },
            )
    try:
        return local_store.add_transaction(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/local/manual-securities")
def list_manual_securities():
    return {"items": local_store.list_manual_securities()}


@app.post("/api/local/manual-securities")
def save_manual_security(payload: dict[str, Any]):
    try:
        return local_store.save_manual_security(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/local/manual-securities/{security_id}")
def delete_manual_security(security_id: str):
    if not local_store.delete_manual_security(security_id):
        raise HTTPException(status_code=404, detail="Manual instrument not found")
    return {"deleted": True}


@app.delete("/api/local/securities/{transaction_id}")
def delete_local_security(transaction_id: str):
    if not local_store.delete_transaction(transaction_id):
        raise HTTPException(status_code=404, detail="Security transaction not found")
    return {"deleted": True}


@app.get("/api/local/prices")
def list_local_prices():
    return {"items": local_store.list_prices()}


@app.get("/api/security/history")
def security_history(symbol: str, stock_market: str = "", period: str = "1y", date_from: str = ""):
    days_by_period = {"1m": 31, "1y": 366, "3y": 366 * 3, "5y": 366 * 5}
    days = days_by_period.get(period, days_by_period["1y"])
    to_date = date.today()
    period_start = to_date - timedelta(days=days)
    from_date = _clamped_history_start(date_from, HISTORY_START_DATE if not date_from else period_start)
    local_rows = local_store.price_history(symbol, stock_market, from_date, to_date)
    if local_store.manual_security_exists(symbol, stock_market):
        return {
            "symbol": symbol,
            "stock_market": stock_market,
            "period": period,
            "source": "manual",
            "points": [{"date": row["price_date"], "price": row["price"], "price_input": row["price_input"]} for row in local_rows],
        }
    prices, status = hub().prices(symbol, from_date, to_date)
    provider_points = [{"date": row.date.isoformat(), "price": row.adjusted_close} for row in prices]
    local_points = [{"date": row["price_date"], "price": row["price"], "price_input": row["price_input"]} for row in local_rows]
    if len(local_points) >= len(provider_points):
        return {"symbol": symbol, "stock_market": stock_market, "period": period, "source": "local", "points": local_points}
    by_date = {point["date"]: point for point in provider_points}
    by_date.update({point["date"]: point for point in local_points})
    return {
        "symbol": symbol,
        "stock_market": stock_market,
        "period": period,
        "source": "merged",
        "status": status,
        "points": [by_date[day] for day in sorted(by_date)],
    }


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
        return local_store.save_fund(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    try:
        configure_backup_job()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return backup_status()


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
        local_store.capture_daily_snapshots()
        clear_portfolio_cache()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/local/backups")
def list_local_backups():
    return {"backup": backup_status()}


@app.post("/api/local/backups")
def run_local_backup():
    backup = load_runtime_settings()["backup"]
    return local_store.write_backup(int(backup.get("keep") or 30))


@app.post("/api/market/screener")
def market_screener(criteria: dict[str, Any]):
    items, status = hub().market_screener(criteria or {})
    return {"count": len(items), "status": status, "items": items}


@app.get("/api/alerts")
def list_alerts():
    return {"rules": alert_store.list_rules()}


@app.post("/api/alerts")
def create_alert(payload: dict[str, Any]):
    return alert_store.add_rule(payload or {})


@app.put("/api/alerts/{rule_id}")
def update_alert(rule_id: str, payload: dict[str, Any]):
    rule = alert_store.update_rule(rule_id, payload or {})
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
    return {"results": alert_store.evaluate(analyze_all())}


web_dir = Path(__file__).resolve().parent.parent / "web"
app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
