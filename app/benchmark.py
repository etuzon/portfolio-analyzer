"""Cash-flow-aware performance from explicitly complete, dated observations.

Valuations and external cash flows use one declared currency and an end-of-day
flow convention. No transaction, current FX rate, or missing valuation is inferred.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from datetime import date
from math import exp, fsum, isfinite
import re

from .investment_scope import InvestmentStoreView

MAX_ROWS = 10000
MAX_LEVEL_AGE_DAYS = 7
BENCHMARKS = [
    {"id": "sp500", "name": "S&P 500", "currency": "USD", "symbol": "^GSPC"},
    {"id": "ta25", "name": "TA-25", "currency": "ILS", "valid_to": "2017-02-08"},
    {"id": "ta100", "name": "TA-100", "currency": "ILS", "valid_to": "2017-02-08"},
    {"id": "ta35", "name": "TA-35", "currency": "ILS", "valid_from": "2017-02-09"},
    {"id": "ta125", "name": "TA-125", "currency": "ILS", "valid_from": "2017-02-09"},
    {"id": "nasdaq", "name": "Nasdaq Composite", "currency": "USD", "symbol": "^IXIC"},
    {"id": "dow", "name": "Dow Jones Industrial Average", "currency": "USD", "symbol": "^DJI"},
    {"id": "custom", "name": "Other index", "currency": ""},
]


class BenchmarkError(ValueError):
    """Validation code safe to translate in the interface."""


def _day(value, today=None):
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        result = date.fromisoformat(value)
    except (ValueError, TypeError):
        raise BenchmarkError("invalid_date") from None
    if result > (today or date.today()):
        raise BenchmarkError("future_date")
    return result


def _number(value, *, positive=False, nonnegative=False):
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise BenchmarkError("invalid_number") from None
    if isinstance(value, bool) or not isfinite(result) or abs(result) > 1e15:
        raise BenchmarkError("invalid_number")
    if positive and result <= 0 or nonnegative and result < 0:
        raise BenchmarkError("invalid_number")
    return result


def _metadata(payload):
    if not isinstance(payload, dict):
        raise BenchmarkError("invalid_dataset")
    currency = str(payload.get("currency") or "").strip().upper()
    source = str(payload.get("source") or "").strip()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise BenchmarkError("currency_required")
    if not source or len(source) > 500:
        raise BenchmarkError("source_required")
    return {"currency": currency, "source": source}


def _rows(payload, field, *, allow_empty=False):
    rows = payload.get(field, [])
    if not isinstance(rows, list) or len(rows) > MAX_ROWS or not rows and not allow_empty:
        raise BenchmarkError("invalid_rows")
    if any(not isinstance(row, dict) for row in rows):
        raise BenchmarkError("invalid_rows")
    return rows


def normalize_portfolio(payload, today=None):
    result = _metadata(payload)
    values = {}
    for row in _rows(payload, "valuations"):
        day = _day(row.get("date"), today).isoformat()
        if day in values:
            raise BenchmarkError("duplicate_date")
        values[day] = _number(row.get("value"), nonnegative=True)
    flows = defaultdict(list)
    for row in _rows(payload, "cash_flows", allow_empty=True):
        day = _day(row.get("date"), today).isoformat()
        amount = _number(row.get("amount"))
        if amount == 0:
            raise BenchmarkError("zero_cash_flow")
        flows[day].append(amount)
    result.update(flows_complete=payload.get("flows_complete") is True,
                  valuations=[{"date": day, "value": value} for day, value in sorted(values.items())],
                  cash_flows=[{"date": day, "amount": _number(fsum(amounts))} for day, amounts in sorted(flows.items())
                              if fsum(amounts) != 0])
    return result


def normalize_index(payload, today=None):
    result = _metadata(payload)
    name = str(payload.get("name") or "").strip()
    if not name or len(name) > 240:
        raise BenchmarkError("index_name_required")
    basis = payload.get("basis")
    if basis not in {"price", "total_return"}:
        raise BenchmarkError("index_basis_required")
    benchmark_id = str(payload.get("id") or "custom")
    if benchmark_id not in {item["id"] for item in BENCHMARKS}:
        raise BenchmarkError("unknown_benchmark")
    levels = {}
    for row in _rows(payload, "levels"):
        day = _day(row.get("date"), today).isoformat()
        if day in levels:
            raise BenchmarkError("duplicate_date")
        levels[day] = _number(row.get("level"), positive=True)
    result.update(id=benchmark_id, name=name, basis=basis,
                  levels=[{"date": day, "level": value} for day, value in sorted(levels.items())])
    return result


def _metric(value=None, status="ok"):
    return {"value": value, "status": status}


def xirr(cashflows):
    """Annualized Actual/365 IRR, conservatively refusing non-conventional flows.

    More than one sign change can produce multiple roots. We do not select a
    convenient root or silently depend on an initial Newton guess.
    """
    by_day = defaultdict(list)
    try:
        for item in cashflows:
            day, amount = (item["date"], item["amount"]) if isinstance(item, dict) else item
            parsed = day if isinstance(day, date) else date.fromisoformat(day)
            number = float(amount)
            if isinstance(amount, bool) or not isfinite(number):
                return _metric(status="invalid_cash_flows")
            by_day[parsed].append(number)
    except (ValueError, TypeError, KeyError, OverflowError):
        return _metric(status="invalid_cash_flows")
    rows = [(day, fsum(items)) for day, items in sorted(by_day.items()) if fsum(items) != 0]
    if len(rows) < 2 or rows[-1][0] <= rows[0][0]:
        return _metric(status="insufficient_dates")
    signs = [amount > 0 for _, amount in rows]
    if all(signs) or not any(signs):
        return _metric(status="invalid_cash_flow_signs")
    if sum(a != b for a, b in zip(signs, signs[1:])) > 1:
        return _metric(status="ambiguous_cash_flows")
    base = rows[0][0]
    values = [amount for _, amount in rows]
    scale = max(abs(amount) for amount in values)
    values = [amount / scale for amount in values]
    times = [(day - base).days / 365 for day, _ in rows]

    # Solve in log(1+r); exponent normalization prevents overflow for long spans.
    def npv(log_rate):
        powers = [-log_rate * time for time in times]
        pivot = max(powers)
        return fsum(value * exp(power - pivot) for value, power in zip(values, powers))

    left, right = -36.0, 36.0
    fl, fr = npv(left), npv(right)
    if fl == 0 or fr == 0 or fl * fr > 0:
        return _metric(status="no_convergence")
    for _ in range(220):
        midpoint = (left + right) / 2
        fm = npv(midpoint)
        if fm == 0:
            break
        if fm * fl > 0:
            left, fl = midpoint, fm
        else:
            right = midpoint
        if right - left < 1e-13:
            break
    value = (exp(midpoint) - 1) * 100
    return _metric(value) if isfinite(value) and value > -100 else _metric(status="no_convergence")


def _portfolio_result(dataset, start, end):
    empty = {"status": "missing_boundary_valuation", "xirr": _metric(status="missing_boundary_valuation"),
             "twrr": _metric(status="missing_boundary_valuation"), "opening_value": None,
             "closing_value": None, "net_flows": None, "gain": None}
    if dataset is None:
        empty.update(status="missing_portfolio", xirr=_metric(status="missing_portfolio"), twrr=_metric(status="missing_portfolio"))
        return empty, [], []
    values = {row["date"]: row["value"] for row in dataset["valuations"] if start <= row["date"] <= end}
    flows = [row for row in dataset["cash_flows"] if start < row["date"] <= end]
    if start not in values or end not in values:
        return empty, [], flows
    opening, closing = values[start], values[end]
    net = fsum(row["amount"] for row in flows)
    result = {"status": "ok", "opening_value": opening, "closing_value": closing,
              "net_flows": net, "gain": closing - opening - net}
    if not dataset["flows_complete"]:
        result.update(status="incomplete_cash_flows", gain=None, net_flows=None,
                      xirr=_metric(status="incomplete_cash_flows"), twrr=_metric(status="incomplete_cash_flows"))
        return result, [], flows
    irr_flows = [{"date": start, "amount": -opening},
                 *[{"date": row["date"], "amount": -row["amount"]} for row in flows],
                 {"date": end, "amount": closing}]
    result["xirr"] = xirr(irr_flows)
    flow_map = {row["date"]: row["amount"] for row in flows}
    if any(day not in values for day in flow_map):
        result["twrr"] = _metric(status="missing_flow_valuation")
        result["status"] = "partial"
        return result, [], flows
    previous, growth = opening, 1.0
    chart = [{"date": start, "portfolio_growth": 100.0}]
    for day, value in sorted(values.items()):
        if day == start:
            continue
        if previous <= 0:
            result.update(status="partial", twrr=_metric(status="nonpositive_base"))
            return result, [], flows
        before_flow = value - flow_map.get(day, 0)
        if before_flow < 0:
            result.update(status="partial", twrr=_metric(status="negative_pre_flow_value"))
            return result, [], flows
        growth *= before_flow / previous
        if not isfinite(growth):
            result.update(status="partial", twrr=_metric(status="numeric_overflow"))
            return result, [], flows
        chart.append({"date": day, "portfolio_growth": growth * 100})
        previous = value
    result["twrr"] = _metric((growth - 1) * 100)
    return result, chart, flows


def compute_comparison(dataset, index_dataset, date_from, date_to):
    """Compare returns over exact portfolio boundaries and dated index evidence."""
    start, end = _day(date_from).isoformat(), _day(date_to).isoformat()
    if start >= end:
        raise BenchmarkError("invalid_period")
    dataset = normalize_portfolio(dataset) if dataset is not None else None
    index_dataset = normalize_index(index_dataset) if index_dataset is not None else None
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    portfolio, chart, flows = _portfolio_result(dataset, start, end)
    result = {"status": "partial", "currency": (dataset or {}).get("currency"), "date_from": start,
              "date_to": end, "days": days, "annualized_short_period": days < 365,
              "portfolio": portfolio, "chart": chart,
              "benchmark": {"status": "missing_index", "xirr": _metric(status="missing_index"),
                            "twrr": _metric(status="missing_index"), "ending_value": None,
                            "level_dates": []}}
    benchmark = result["benchmark"]

    def unavailable(status):
        benchmark.update(status=status, xirr=_metric(status=status), twrr=_metric(status=status), ending_value=None)
        return result

    if index_dataset is None:
        return result
    benchmark.update({key: index_dataset[key] for key in ("id", "name", "currency", "basis", "source")})
    catalog = next(item for item in BENCHMARKS if item["id"] == index_dataset["id"])
    if catalog.get("valid_to", end) < end or catalog.get("valid_from", start) > start:
        return unavailable("index_outside_lifetime")
    if dataset is None:
        return unavailable("missing_portfolio")
    if dataset["currency"] != index_dataset["currency"]:
        return unavailable("currency_mismatch")
    if portfolio["opening_value"] is None:
        return unavailable("missing_boundary_valuation")
    if not dataset["flows_complete"]:
        return unavailable("incomplete_cash_flows")
    levels = {row["date"]: row["level"] for row in index_dataset["levels"]}
    level_days = sorted(levels)
    used = {}

    def at(day):
        offset = bisect_right(level_days, day) - 1
        if offset < 0:
            return None
        observed = level_days[offset]
        if (date.fromisoformat(day) - date.fromisoformat(observed)).days > MAX_LEVEL_AGE_DAYS:
            return None
        used[day] = observed
        return levels[observed]

    dates = sorted({start, end, *(row["date"] for row in flows)})
    evidence = {day: at(day) for day in dates}
    benchmark["level_dates"] = [{"date": day, "level_date": used.get(day), "level": evidence[day]} for day in dates]
    if any(level is None for level in evidence.values()):
        return unavailable("missing_index_level")
    opening = portfolio["opening_value"]
    units = opening / evidence[start]
    benchmark_flows = [{"date": start, "amount": -opening}]
    for row in flows:
        units += row["amount"] / evidence[row["date"]]
        benchmark_flows.append({"date": row["date"], "amount": -row["amount"]})
        if units < -1e-10:
            return unavailable("benchmark_overdrawn")
        units = max(units, 0)
    ending = units * evidence[end]
    if not isfinite(ending):
        return unavailable("numeric_overflow")
    benchmark_flows.append({"date": end, "amount": ending})
    benchmark.update(status="ok", ending_value=ending, xirr=xirr(benchmark_flows),
                     twrr=_metric((evidence[end] / evidence[start] - 1) * 100))
    # Chart has observed portfolio dates only. Missing index evidence yields gaps.
    for row in chart:
        level = at(row["date"])
        row["benchmark_growth"] = level / evidence[start] * 100 if level is not None else None
    result["status"] = "ok" if portfolio["status"] == "ok" and portfolio["xirr"]["status"] == "ok" else "partial"
    return result


def portfolio_key(account_id=""):
    if account_id:
        return "benchmark_portfolio_v1:" + str(account_id)
    return "benchmark_portfolio_v2:all_investments"


def index_key(benchmark_id):
    if benchmark_id not in {item["id"] for item in BENCHMARKS}:
        raise BenchmarkError("unknown_benchmark")
    return "benchmark_index_v1:" + benchmark_id


def load_portfolio(store, account_id=""):
    saved = store.get_preference(portfolio_key(account_id), None)
    if isinstance(store, InvestmentStoreView) and not account_id and saved is not None:
        if not isinstance(saved, dict) or saved.get("investment_account_ids") != sorted(store.account_ids()):
            return None  # Changing account membership invalidates an aggregate, not its preserved audit data.
    return saved


def save_portfolio(store, payload, account_id=""):
    normalized = normalize_portfolio(payload)
    if isinstance(store, InvestmentStoreView) and not account_id:
        normalized["investment_account_ids"] = sorted(store.account_ids())
    store.set_preference(portfolio_key(account_id), normalized)
    return normalized


def load_index(store, benchmark_id):
    return store.get_preference(index_key(benchmark_id), None)


def save_index(store, benchmark_id, payload):
    key = index_key(benchmark_id)
    if not isinstance(payload, dict):
        raise BenchmarkError("invalid_dataset")
    normalized = normalize_index({**payload, "id": benchmark_id})
    store.set_preference(key, normalized)
    return normalized
