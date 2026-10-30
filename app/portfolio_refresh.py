"""Bounded, deduplicated market refreshes independent of account quantities."""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from copy import deepcopy
import json
import time
from threading import RLock


# Reuse a bounded pool across retries: timed-out network calls cannot create
# another unbounded set of threads when a user requests another refresh.
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="security-refresh")
_INFLIGHT = {}
_INFLIGHT_LOCK = RLock()


def security_key(holding) -> str:
    return json.dumps([(holding.get(field, "") if isinstance(holding, dict) else getattr(holding, field, "")) for field in (
        "symbol", "secondary_symbol", "stock_market", "currency", "asset_class", "asset_sub_class", "data_source"
    )], separators=(",", ":"))


def attach_market_analysis(local, market):
    result = deepcopy(market)
    holding = deepcopy(local.holding)
    if not holding.name or holding.name.upper() == holding.symbol.upper():
        holding.name = market.holding.name or holding.name
    holding.sector = holding.sector or market.holding.sector
    holding.industry = market.industry or holding.industry
    result.holding = holding
    result.provider_status = {**local.provider_status, **result.provider_status}
    if "price history" in result.missing and "price history" not in local.missing:
        result.missing = [key for key in result.missing if key != "price history"]
        for key in ("price_ranges", "moving_averages", "support_resistance", "volume"):
            setattr(result, key, deepcopy(getattr(local, key)))
    current = (result.price_ranges.get("5y") or {}).get("current")
    if holding.secondary_symbol and current is not None and current > 0:
        holding.market_value = holding.quantity * current
        if holding.quantity >= 0:
            holding.unrealized_profit = holding.market_value - holding.cost_basis
        else:
            average = abs(holding.cost_basis / holding.quantity) if holding.quantity else 0
            holding.unrealized_profit = abs(holding.quantity) * (average - current)
    return result


def refresh_positions(analyses, hub, analyze, progress, timeout_seconds, fallback, cancelled=lambda: False):
    groups = {}
    for local in analyses:
        if local.holding.data_source == "MANUAL" and not local.holding.secondary_symbol:
            continue
        groups.setdefault(security_key(local.holding), []).append(local)
    total = len(groups)
    deadline = time.monotonic() + max(0.01, timeout_seconds)
    for key in groups:
        progress(key, "queued", None, total)

    def run(key, local):
        if cancelled() or time.monotonic() >= deadline:
            raise TimeoutError("Security refresh deadline exceeded")
        progress(key, "updating", None, total)
        return analyze(deepcopy(local.holding), hub)

    def release_future(cache_key, future):
        with _INFLIGHT_LOCK:
            if _INFLIGHT.get(cache_key) is future:
                _INFLIGHT.pop(cache_key, None)

    pending = {}
    for key, values in groups.items():
        cache_key = (id(hub), key)
        with _INFLIGHT_LOCK:
            future = _INFLIGHT.get(cache_key)
            if future is None or future.done():
                future = _POOL.submit(run, key, values[0])
                _INFLIGHT[cache_key] = future
                future.add_done_callback(lambda done, cache_key=cache_key: release_future(cache_key, done))
            else:
                # Reuse a still-running provider request after a timed-out
                # batch. Its market evidence is independent of quantities.
                progress(key, "updating", None, total)
            pending[future] = key
    results = {}
    while pending:
        if cancelled():
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        completed, _ = wait(pending, timeout=min(remaining, 0.25), return_when=FIRST_COMPLETED)
        if not completed:
            continue
        for future in completed:
            key = pending.pop(future)
            try:
                market = future.result()
                results[key] = market
                progress(key, "ready", attach_market_analysis(groups[key][0], market), total)
            except Exception:
                progress(key, "failed", None, total)
    for future, key in pending.items():
        future.cancel()
        progress(key, "failed", None, total)
    return [attach_market_analysis(local, results[security_key(local.holding)])
            if security_key(local.holding) in results else fallback(local) if security_key(local.holding) in groups else local
            for local in analyses]
