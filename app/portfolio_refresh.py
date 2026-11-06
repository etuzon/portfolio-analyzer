"""Bounded, deduplicated market refreshes independent of account quantities."""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from copy import deepcopy
from datetime import date
import json
import math
import time
from threading import RLock


# Reuse a bounded pool across retries: timed-out network calls cannot create
# another unbounded set of threads when a user requests another refresh.
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="security-refresh")
_INFLIGHT = {}
_INFLIGHT_LOCK = RLock()
PRICE_ANALYSIS_FIELDS = ("price_ranges", "moving_averages", "support_resistance", "volume")


def security_key(holding) -> str:
    return json.dumps([(holding.get(field, "") if isinstance(holding, dict) else getattr(holding, field, "")) for field in (
        "symbol", "secondary_symbol", "stock_market", "currency", "asset_class", "asset_sub_class", "data_source"
    )], separators=(",", ":"))


def _finite_number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def valuation_quote(price_ranges):
    """A usable normalized quote and its actual observation date, if known."""
    candidates = []
    for period in ("5y", "3y", "1y", "6m", "1m"):
        quote = (price_ranges or {}).get(period) or {}
        current, observed = quote.get("current"), quote.get("current_date")
        if not _finite_number(current) or current < 0 or quote.get("state") in {"missing", "pending", "error"}:
            continue
        if not isinstance(observed, str) or len(observed) != 10:
            continue
        try:
            day = date.fromisoformat(observed)
        except ValueError:
            continue
        if day <= date.today():
            candidates.append((day, current))
    return max(candidates, key=lambda quote: quote[0]) if candidates else None


def prefer_recorded_prices(recorded_ranges, market_ranges):
    recorded, market = valuation_quote(recorded_ranges), valuation_quote(market_ranges)
    return recorded is not None and (market is None or recorded[0] > market[0])


def revalue_holding(holding, price_ranges):
    """Apply an already normalized quote to this account's recorded position.

    Shared by completed analyses and serialized progress overlays. Market data
    belongs to a listing; quantities, basis, realized P/L and income do not.
    """
    get = holding.get if isinstance(holding, dict) else lambda key: getattr(holding, key, None)
    if get("data_source") == "MANUAL" and not get("secondary_symbol"):
        return
    quote = valuation_quote(price_ranges)
    quantity, basis = get("quantity"), get("cost_basis")
    if quote is None or not all(_finite_number(value) for value in (quantity, basis)):
        return
    current = quote[1]
    value = quantity * current
    unrealized = value - basis if quantity >= 0 else abs(basis) - abs(quantity) * current
    if not _finite_number(value) or not _finite_number(unrealized):
        return
    if isinstance(holding, dict):
        holding.update(market_value=value, unrealized_profit=unrealized)
    else:
        holding.market_value, holding.unrealized_profit = value, unrealized


def attach_market_analysis(local, market):
    result = deepcopy(market)
    holding = deepcopy(local.holding)
    if not holding.name or holding.name.upper() == holding.symbol.upper():
        holding.name = market.holding.name or holding.name
    holding.sector = holding.sector or market.holding.sector
    holding.industry = market.industry or holding.industry
    result.holding = holding
    result.provider_status = {**local.provider_status, **result.provider_status}
    if prefer_recorded_prices(local.price_ranges, result.price_ranges) or (
        "price history" in result.missing and "price history" not in local.missing
    ):
        result.missing = [key for key in result.missing if key != "price history"]
        for key in PRICE_ANALYSIS_FIELDS:
            setattr(result, key, deepcopy(getattr(local, key)))
    revalue_holding(holding, result.price_ranges)
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
