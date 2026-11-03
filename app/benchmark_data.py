"""Benchmark application boundary: saved inputs, statement suggestions and explicit refresh."""
from __future__ import annotations

from contextlib import nullcontext
from datetime import date, timedelta
import math

from .benchmark import (
    BENCHMARKS, BenchmarkError, compute_comparison, load_index, load_portfolio,
    save_index, save_portfolio,
)

# These documented index identities are supported by the existing configured
# FMP / explicitly enabled Yahoo adapters. Never substitute an ETF for an index.
PROVIDER_SYMBOLS = {"sp500": "^GSPC", "nasdaq": "^IXIC", "dow": "^DJI"}
INDEX_PROVIDERS = {"financial_modeling_prep", "yahoo_finance"}


def catalog():
    rows = BENCHMARKS.values() if isinstance(BENCHMARKS, dict) else BENCHMARKS
    return [{**row, "can_refresh": row["id"] in PROVIDER_SYMBOLS} for row in rows]


def require_scope(store, account_id="", benchmark_id="sp500"):
    accounts = store.list_accounts()
    if not isinstance(account_id, str) or (account_id and account_id not in {row["id"] for row in accounts}):
        raise BenchmarkError("benchmark_unknown_account")
    if not isinstance(benchmark_id, str) or benchmark_id not in {row["id"] for row in catalog()}:
        raise BenchmarkError("benchmark_unknown_index")
    return accounts


def _suggestions(store, accounts, account_id):
    scoped = [row for row in accounts if not account_id or row["id"] == account_id]
    currencies = {str(row.get("currency") or "").upper() for row in scoped}
    currency = next(iter(currencies)) if len(currencies) == 1 else ""
    if not scoped or not currency:
        return [], currency
    # Aggregate only dates with a saved value for EVERY selected account.
    # Current holdings and today's FX cannot reconstruct historical NAV.
    by_date = {}
    ids = {row["id"] for row in scoped}
    for row in store.list_account_snapshots({"account_id": account_id} if account_id else {}):
        aid = row["account_db_id"]
        if aid not in ids:
            continue
        value = row.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            continue
        by_date.setdefault(row["snapshot_date"], {})[aid] = value
    return [{"date": day, "value": math.fsum(values.values())}
            for day, values in sorted(by_date.items()) if values.keys() == ids], currency


def benchmark_inputs(store, account_id="", benchmark_id="sp500"):
    accounts = require_scope(store, account_id, benchmark_id)
    suggestions, currency = _suggestions(store, accounts, account_id)
    return {"accounts": accounts, "catalog": catalog(), "account_id": account_id,
            "benchmark_id": benchmark_id, "dataset": load_portfolio(store, account_id),
            "index_dataset": load_index(store, benchmark_id),
            "suggested_valuations": suggestions, "suggested_currency": currency}


def benchmark_comparison(store, account_id="", benchmark_id="sp500", date_from="", date_to=""):
    inputs = benchmark_inputs(store, account_id, benchmark_id)
    dataset = inputs["dataset"]
    days = [row["date"] for row in (dataset or {}).get("valuations", [])]
    end = date_to or (max(days) if days else date.today().isoformat())
    start = date_from or (min(days) if days else (date.today() - timedelta(days=365)).isoformat())
    # One saved observation is editable evidence, not an unusable dialog.
    # Leave an explicit invalid user range to the calculator's validation.
    if not date_from and start == end:
        start = (date.fromisoformat(end) - timedelta(days=365)).isoformat()
    result = compute_comparison(dataset, inputs["index_dataset"], start, end)
    return {**inputs, "date_from": start, "date_to": end, "result": result}


def save_portfolio_inputs(store, payload):
    account_id = payload.get("account_id", "")
    require_scope(store, account_id)
    return save_portfolio(store, payload, account_id=account_id)


def save_index_inputs(store, payload):
    benchmark_id = payload.get("benchmark_id", "")
    require_scope(store, "", benchmark_id)
    # Bind saved identity to selected catalog entry, never an untrusted id field.
    return save_index(store, benchmark_id, {**payload, "id": benchmark_id})


def refresh_index(store, market_hub, payload):
    benchmark_id = payload.get("benchmark_id", "")
    require_scope(store, "", benchmark_id)
    if benchmark_id not in PROVIDER_SYMBOLS:
        raise BenchmarkError("benchmark_refresh_unsupported")
    try:
        start = date.fromisoformat(payload.get("date_from", ""))
        end = date.fromisoformat(payload.get("date_to", ""))
    except (TypeError, ValueError) as exc:
        raise BenchmarkError("benchmark_invalid_dates") from exc
    if start >= end or end > date.today() or (end - start).days > 36525:
        raise BenchmarkError("benchmark_invalid_dates")
    before = load_index(store, benchmark_id)
    providers = [p for p in market_hub.providers if p.name in INDEX_PROVIDERS]
    if not providers:
        raise BenchmarkError("benchmark_provider_not_configured")
    symbol = PROVIDER_SYMBOLS[benchmark_id]
    for provider in providers:
        try:
            rows = provider.prices(symbol, start - timedelta(days=7), end)
            levels = [{"date": row.date.isoformat(), "level": row.close} for row in rows
                      if start - timedelta(days=7) <= row.date <= end and math.isfinite(row.close) and row.close > 0]
            if len(levels) < 2:
                continue
            lock = getattr(store, "_sync_lock", None)
            with lock if lock is not None else nullcontext():
                if load_index(store, benchmark_id) != before:
                    raise BenchmarkError("benchmark_inputs_changed")
                entry = next(row for row in catalog() if row["id"] == benchmark_id)
                return save_index(store, benchmark_id, {
                    "id": benchmark_id, "name": entry["name"], "currency": "USD", "basis": "price",
                    "source": f"{provider.name}: {symbol}", "levels": levels,
                })
        except BenchmarkError:
            raise
        except Exception:
            # Provider credentials and response bodies never enter API errors.
            continue
    raise BenchmarkError("benchmark_refresh_failed")
