"""Prospective observed-equity reconciliation, never a reconstructed return.

Pure financial evidence capture and comparison. No providers, persistence, or
current-account lookups are allowed here: earlier observations stay frozen.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import math
from zoneinfo import ZoneInfo

VERSION = "observed-equity-recorded-flows-v1"
COVERAGE = "recorded_activity_only"
SCOPE = "canonical_non_esop_securities_cash"
MAX_MARK_AGE_DAYS = 7
_CASH_SIGNS = {"BUY": -1, "SELL": 1, "SHORT": 1, "DIVIDEND": 1,
               "INTEREST": 1, "FEE": -1, "CASH_IN": 1, "CASH_OUT": -1}
_ACTIONS = set(_CASH_SIGNS) | {"ADD", "REMOVE"}


def _number(value):
    try:
        return float(value) if type(value) in (int, float) and math.isfinite(value) else None
    except OverflowError:
        return None


def _date(value):
    try:
        return date.fromisoformat(value[:10]) if isinstance(value, str) else None
    except ValueError:
        return None


def _stamp(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else None
        return result.astimezone(timezone.utc) if result and result.tzinfo else None
    except ValueError:
        return None


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _listing(row):
    market = str(row.get("stock_market") or "").strip().upper().replace(" ", "")
    market = {"NASDAQGS": "NASDAQ", "NASDAQGM": "NASDAQ", "NASDAQCM": "NASDAQ",
              "NAS": "NASDAQ", "NMS": "NASDAQ", "TLV": "TASE", "TELAVIV": "TASE",
              "NYSEAMERICAN": "AMEX", "NYSEMKT": "AMEX", "ARCA": "NYSEARCA"}.get(market, market)
    return "|".join((str(row.get("symbol") or "").strip().upper(), market,
                     str(row.get("currency") or "").strip().upper(),
                     str(row.get("asset_class") or "").strip().upper()))


def _fx(quotes, currency, base, day):
    if currency == base:
        return {"currency": currency, "base_currency": base, "rate": 1.0,
                "date": day.isoformat(), "source": "same_currency"}
    # Match the shared browser conversion: an explicit direct pair takes
    # precedence over its inverse when both saved provider observations exist.
    direct = f"{currency}/{base}"
    for row in sorted(quotes, key=lambda row: str(row.get("pair") or "").upper() != direct):
        pair = str(row.get("pair") or "").upper()
        quote = row.get("quote") or {}
        rate = _number(quote.get("rate"))
        if rate is None or rate <= 0 or pair not in {f"{currency}/{base}", f"{base}/{currency}"}:
            continue
        # Existing FX providers call their actual market observation `time`;
        # retrieval/cache timestamps are deliberately not observation evidence.
        observed = next((_date(quote.get(key)) for key in ("date", "observed_at", "as_of", "time") if _date(quote.get(key))), None)
        actual = rate if pair == f"{currency}/{base}" else 1 / rate
        if not math.isfinite(actual) or actual <= 0:
            continue
        return {"currency": currency, "base_currency": base, "rate": actual,
                "date": observed.isoformat() if observed else None,
                "source": quote.get("source") or quote.get("provider") or next(iter(row.get("status") or {}), "saved_fx"),
                "observed_at": quote.get("observed_at") or quote.get("time")}
    return None


def _eligible_fx(evidence, today):
    observed = _date((evidence or {}).get("date"))
    return observed is not None and 0 <= (today - observed).days <= MAX_MARK_AGE_DAYS


def capture(inputs, observed_at, reset_epoch="initial"):
    """Freeze server-held cash, dated marks, ledger identity and saved FX."""
    instant = _stamp(observed_at)
    if instant is None:
        raise ValueError("risk_performance_invalid_observation_time")
    today = instant.astimezone(ZoneInfo("Asia/Jerusalem")).date()
    base = str(inputs.get("base_currency") or "").upper()
    quotes = inputs.get("fx", {}).get("quotes", [])
    items = inputs.get("items", [])
    accounts = []
    for original in inputs.get("accounts", []):
        if str(original.get("type") or "").upper() == "ESOP":
            continue
        identifier = str(original.get("id") or "")
        currency = str(original.get("currency") or "").strip().upper()
        initial = _number(original.get("initial_cash"))
        reasons, evidence, ledger, positions = [], {}, [], {}
        if initial is None or not identifier or not currency:
            reasons.append("missing_valuation")
        account_fx = _fx(quotes, currency, base, today)
        if account_fx:
            evidence[currency] = account_fx
        cash = initial if initial is not None else 0.0
        for transaction in inputs.get("transactions", []):
            if str(transaction.get("account_db_id") or "") != identifier:
                continue
            action = str(transaction.get("action") or "").upper()
            if action not in _ACTIONS:
                continue
            tx_id, day = str(transaction.get("id") or ""), _date(transaction.get("trade_date"))
            quantity, price = _number(transaction.get("quantity")), _number(transaction.get("price"))
            tx_currency = str(transaction.get("currency") or "").upper()
            if not tx_id or day is None or quantity is None or price is None or quantity < 0 or price < 0:
                reasons.append("missing_valuation")
                continue
            if day > today:
                reasons.append("future_activity")
            amount = quantity * price
            if not math.isfinite(amount):
                reasons.append("missing_valuation")
                continue
            impact = _CASH_SIGNS.get(action, 0) * amount
            if impact and tx_currency != currency:
                reasons.append("mixed_transaction_currencies")
            cash += impact
            economics = {key: transaction.get(key) for key in (
                "account_db_id", "action", "trade_date", "currency", "quantity", "price",
                "symbol", "stock_market", "asset_class", "location", "security_id", "source")}
            flow = impact if action in {"CASH_IN", "CASH_OUT"} else 0.0
            flow_fx = _fx(quotes, tx_currency, base, day) if flow else None
            if flow_fx and flow_fx.get("date") != day.isoformat():
                flow_fx = None
            ledger.append({"id": tx_id, "economic_hash": _hash(economics), "action": action,
                           "date": day.isoformat(), "created_at": transaction.get("created_at"),
                           "currency": tx_currency, "quantity": quantity, "price": price,
                           "key": _listing(transaction), "source": transaction.get("source"),
                           "signed_external_flow": flow, "flow_fx_evidence": flow_fx})
        if cash != 0 and not _eligible_fx(account_fx, today):
            reasons.append("missing_fx")
        equity = 0.0 if cash == 0 else cash * account_fx["rate"] if account_fx else None
        for item in items:
            holding = item.get("holding") or {}
            if str(holding.get("account_id") or "") != identifier:
                continue
            value, quantity = _number(holding.get("market_value")), _number(holding.get("quantity"))
            holding_currency = str(holding.get("currency") or "").upper()
            if (value is None or quantity is None or (quantity == 0 and value != 0)
                    or (quantity != 0 and (value == 0 or (value > 0) != (quantity > 0)))):
                reasons.append("missing_valuation")
                continue
            if quantity == 0 and value == 0:
                continue
            fx = _fx(quotes, holding_currency, base, today)
            if not _eligible_fx(fx, today):
                reasons.append("missing_fx")
            if fx:
                evidence[holding_currency] = fx
            metadata = item.get("stress_risk") or {}
            # Enrichment replaces stress metadata; actual server quote dates
            # normally live in the already normalized price-range analysis.
            # Match the latest dated quote to the frozen signed holding value,
            # rather than inventing a date or silently choosing an older match.
            quote_rows = []
            for period in ("5y", "3y", "1y", "6m", "1m"):
                row = (item.get("price_ranges") or {}).get(period) or {}
                if not isinstance(row, dict):
                    continue
                price, day = _number(row.get("current")), _date(row.get("current_date"))
                if price is not None and price > 0 and day and row.get("state") not in {"missing", "pending", "error"}:
                    quote_rows.append((day, price, row))
            latest = max((row[0] for row in quote_rows), default=None)
            matching_day = [row for row in quote_rows if row[0] == latest]
            quote = matching_day[0][2] if matching_day else {}
            marked = latest if matching_day else _date(metadata.get("valuation_date"))
            if matching_day and any(not _same_number(row[1] * quantity, value) for row in matching_day):
                reasons.append("missing_valuation")
            if marked is None:
                reasons.append("missing_valuation")
            elif not 0 <= (today - marked).days <= MAX_MARK_AGE_DAYS or metadata.get("valuation_stale") is True:
                reasons.append("stale_valuation")
            key = _listing(holding)
            mark = {"date": marked.isoformat() if marked else None,
                    "price": value / quantity if quantity else None,
                    "currency": holding_currency, "unit": "normalized_native_currency_per_unit",
                    "source": quote.get("source") or metadata.get("valuation_source") or item.get("price_source") or "saved_portfolio_mark",
                    "observed_at": quote.get("current_observed_at") or metadata.get("valuation_observed_at"),
                    "local_override": quote.get("local_override") is True}
            if key not in positions:
                positions[key] = {"key": key, "quantity": 0.0, "mark": mark}
            elif positions[key]["mark"] != mark:
                reasons.append("valuation_revised")
            positions[key]["quantity"] += quantity
            equity = equity + value * fx["rate"] if equity is not None and fx else None
        if equity is None or not math.isfinite(equity) or not math.isfinite(cash):
            equity = None
            reasons.append("missing_valuation")
        reasons = list(dict.fromkeys(reasons))
        accounts.append({"account_id": identifier, "currency": currency,
                         "account_type": str(original.get("type") or "").upper(),
                         "initial_cash": initial, "equity": equity, "cash": cash if math.isfinite(cash) else None,
                         "status": "unavailable" if reasons else "ok", "reason_codes": reasons,
                         "ledger_rows": ledger, "positions": list(positions.values()),
                         "fx_evidence": list(evidence.values())})
    total_reasons = sorted({reason for account in accounts for reason in account["reason_codes"]})
    total_equity = sum(account["equity"] for account in accounts) if all(account["equity"] is not None for account in accounts) else None
    if total_equity is not None and not math.isfinite(total_equity):
        total_equity = None
        total_reasons.append("missing_valuation")
    return {"version": VERSION, "coverage": COVERAGE, "scope": SCOPE,
            "base_currency": base, "reset_epoch": reset_epoch, "observed_at": observed_at,
            "scope_account_ids": sorted(account["account_id"] for account in accounts),
            "accounts": accounts, "total": {"equity": total_equity,
                "status": "unavailable" if total_reasons else "ok", "reason_codes": total_reasons}}


def _same_number(left, right):
    return _number(left) is not None and _number(right) is not None and math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-8)


def _valid_snapshot(snapshot, observation):
    """Reject malformed saved evidence without dropping its visible risk point.

    Backups can contain legacy or damaged optional comparison metadata. Validate
    the complete nested shape before dereferencing it; treating such a record
    as absent evidence also breaks the comparison rather than bridging over it.
    """
    if (not isinstance(snapshot, dict) or snapshot.get("version") != VERSION
            or snapshot.get("scope") != SCOPE or snapshot.get("coverage") != COVERAGE
            or not isinstance(snapshot.get("reset_epoch"), str) or not snapshot["reset_epoch"]
            or snapshot["reset_epoch"] != observation.get("reset_epoch")):
        return False
    accounts, identifiers, total = (snapshot.get(key) for key in ("accounts", "scope_account_ids", "total"))
    if not isinstance(accounts, list) or not isinstance(identifiers, list) or not isinstance(total, dict):
        return False
    instant = _stamp(snapshot.get("observed_at"))
    if (not isinstance(snapshot.get("base_currency"), str) or instant is None
            or instant != _stamp(observation.get("observed_at"))):
        return False
    base = snapshot["base_currency"]
    today = instant.astimezone(ZoneInfo("Asia/Jerusalem")).date()

    def valuation(row):
        return (isinstance(row, dict) and isinstance(row.get("status"), str)
                and row["status"] in {"ok", "unavailable"}
                and isinstance(row.get("reason_codes"), list)
                and all(isinstance(reason, str) for reason in row["reason_codes"])
                and (row.get("equity") is None or _number(row["equity"]) is not None))

    def fx(row):
        return (isinstance(row, dict) and isinstance(row.get("currency"), str)
                and row.get("base_currency") == base
                and _number(row.get("rate")) is not None and row["rate"] > 0
                and (row.get("date") is None or _date(row["date"]) is not None)
                and (row.get("date") is None or _date(row["date"]) <= today)
                and (_stamp(row.get("observed_at")) is None or _stamp(row["observed_at"]) <= instant)
                and (row.get("currency") != base or _same_number(row["rate"], 1))
                and (row.get("source") != "same_currency" or row.get("currency") == base)
                and isinstance(row.get("source"), str))

    if not valuation(total) or not all(isinstance(identifier, str) and identifier for identifier in identifiers):
        return False
    seen = set()
    for account in accounts:
        if not valuation(account):
            return False
        identifier = account.get("account_id")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            return False
        seen.add(identifier)
        if not isinstance(account.get("currency"), str) or not isinstance(account.get("account_type"), str):
            return False
        if account["account_type"] == "ESOP":
            return False
        if account.get("initial_cash") is not None and _number(account["initial_cash"]) is None:
            return False
        if account.get("cash") is not None and _number(account["cash"]) is None:
            return False
        if not all(isinstance(account.get(key), list) for key in ("ledger_rows", "positions", "fx_evidence")):
            return False
        if not all(fx(row) for row in account["fx_evidence"]):
            return False
        quotes = {row["currency"]: row for row in account["fx_evidence"]}
        if len(quotes) != len(account["fx_evidence"]):
            return False
        ledger_ids, position_keys = set(), set()
        computed_cash = account.get("initial_cash")
        for row in account["ledger_rows"]:
            if (not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]
                    or row["id"] in ledger_ids or not isinstance(row.get("economic_hash"), str)
                    or not isinstance(row.get("action"), str) or row["action"] not in _ACTIONS
                    or _date(row.get("date")) is None
                    or not isinstance(row.get("currency"), str) or not isinstance(row.get("key"), str)
                    or any(_number(row.get(key)) is None for key in ("quantity", "price", "signed_external_flow"))
                    or (row.get("flow_fx_evidence") is not None and not fx(row["flow_fx_evidence"]))):
                return False
            ledger_ids.add(row["id"])
            if account["status"] == "ok" and _date(row["date"]) > today:
                return False
            amount = row["quantity"] * row["price"]
            if row["quantity"] < 0 or row["price"] < 0 or not math.isfinite(amount):
                return False
            expected_flow = amount * (1 if row["action"] == "CASH_IN" else -1 if row["action"] == "CASH_OUT" else 0)
            if not _same_number(row["signed_external_flow"], expected_flow):
                return False
            flow_quote = row.get("flow_fx_evidence")
            if flow_quote and (flow_quote["currency"] != row["currency"] or flow_quote.get("date") != row["date"]):
                return False
            impact = _CASH_SIGNS.get(row["action"], 0) * amount
            if impact and row["currency"] != account["currency"] and account["status"] == "ok":
                return False
            if computed_cash is not None:
                computed_cash += impact
        computed_equity = None
        if account["status"] == "ok":
            if not _same_number(account.get("cash"), computed_cash):
                return False
            cash_quote = quotes.get(account["currency"])
            if computed_cash != 0 and not _eligible_fx(cash_quote, today):
                return False
            computed_equity = computed_cash * cash_quote["rate"] if computed_cash else 0.0
        for row in account["positions"]:
            if (not isinstance(row, dict) or not isinstance(row.get("key"), str) or not row["key"]
                    or row["key"] in position_keys or _number(row.get("quantity")) is None
                    or not isinstance(row.get("mark"), dict)):
                return False
            mark = row["mark"]
            if mark.get("price") is not None and (_number(mark["price"]) is None or mark["price"] <= 0):
                return False
            if mark.get("date") is not None and _date(mark["date"]) is None:
                return False
            parts = row["key"].split("|")
            if (len(parts) != 4 or mark.get("currency") != parts[2]
                    or mark.get("unit") != "normalized_native_currency_per_unit"):
                return False
            if account["status"] == "ok":
                quote = quotes.get(mark["currency"])
                marked = _date(mark.get("date"))
                if (not _eligible_fx(quote, today) or marked is None
                        or not 0 <= (today - marked).days <= MAX_MARK_AGE_DAYS
                        or _number(mark.get("price")) is None):
                    return False
                computed_equity += row["quantity"] * mark["price"] * quote["rate"]
            position_keys.add(row["key"])
        if account["status"] == "ok" and not _same_number(account["equity"], computed_equity):
            return False
    if total["status"] == "ok":
        if any(account["status"] != "ok" for account in accounts):
            return False
        if not _same_number(total["equity"], sum(account["equity"] for account in accounts)):
            return False
    return len(identifiers) == len(seen) and set(identifiers) == seen


def _account_change(beginning, ending, baseline_at, fx_pool):
    """Return recorded external capital and reasons for an account interval."""
    reasons, flows = [], 0.0
    if beginning.get("currency") != ending.get("currency"):
        reasons.append("account_currency_changed")
    if not _same_number(beginning.get("initial_cash"), ending.get("initial_cash")):
        reasons.append("opening_cash_changed")
    if beginning.get("account_type") != ending.get("account_type"):
        reasons.append("scope_changed")
    old = {row["id"]: row for row in beginning.get("ledger_rows", [])}
    current = {row["id"]: row for row in ending.get("ledger_rows", [])}
    if any(identifier not in current or current[identifier].get("economic_hash") != row.get("economic_hash") for identifier, row in old.items()):
        reasons.append("ledger_revised")
    expected = {row["key"]: row["quantity"] for row in beginning.get("positions", [])}
    for identifier, row in current.items():
        if identifier in old:
            continue
        day = _date(row.get("date"))
        baseline_day = baseline_at.astimezone(ZoneInfo("Asia/Jerusalem")).date()
        if day is None or day < baseline_day:
            reasons.append("retroactive_activity")
        elif day == baseline_day:
            created = _stamp(row.get("created_at"))
            if created is None or created <= baseline_at:
                reasons.append("activity_timing_unknown")
        action = row.get("action")
        if action in {"ADD", "REMOVE"}:
            reasons.append("in_kind_flow_unvalued")
        if action in {"BUY", "SELL", "SHORT"}:
            key = row.get("key")
            expected[key] = expected.get(key, 0.0) + row["quantity"] * (1 if action == "BUY" else -1)
        if action in {"CASH_IN", "CASH_OUT"}:
            if row.get("source") == "cash_adjustment":
                reasons.append("unclassified_cash_adjustment")
                continue
            flow = row.get("signed_external_flow")
            evidence = row.get("flow_fx_evidence") or fx_pool.get((row.get("currency"), row.get("date")))
            if _number(flow) is None or not evidence or evidence.get("date") != row.get("date"):
                reasons.append("missing_flow_fx")
            else:
                converted = flow * evidence["rate"]
                if not math.isfinite(converted):
                    reasons.append("missing_flow_fx")
                else:
                    flows += converted
    actual = {row["key"]: row["quantity"] for row in ending.get("positions", [])}
    if any(not _same_number(expected.get(key, 0.0), actual.get(key, 0.0)) for key in expected.keys() | actual.keys()):
        reasons.append("positions_unreconciled")
    old_marks = {row["key"]: row.get("mark") or {} for row in beginning.get("positions", [])}
    for row in ending.get("positions", []):
        old_mark, new_mark = old_marks.get(row["key"]), row.get("mark") or {}
        if not old_mark:
            continue
        older, newer = _date(old_mark.get("date")), _date(new_mark.get("date"))
        if older and newer and newer < older:
            reasons.append("valuation_revised")
        elif older and newer and older == newer and not _same_number(old_mark.get("price"), new_mark.get("price")):
            old_at, new_at = _stamp(old_mark.get("observed_at")), _stamp(new_mark.get("observed_at"))
            if old_at is None or new_at is None or new_at <= old_at:
                reasons.append("valuation_revised")
    old_fx = {row["currency"]: row for row in beginning.get("fx_evidence", [])}
    for evidence in ending.get("fx_evidence", []):
        prior = old_fx.get(evidence["currency"])
        if prior and evidence["source"] != "same_currency" and prior.get("date") == evidence.get("date") and not _same_number(prior.get("rate"), evidence.get("rate")):
            a, b = _stamp(prior.get("observed_at")), _stamp(evidence.get("observed_at"))
            if a is None or b is None or b <= a:
                reasons.append("valuation_revised")
    return flows, list(dict.fromkeys(reasons))


def attach_comparisons(observations, base_currency):
    """Annotate the selected period; never mutate a stored snapshot or fetch data."""
    results = deepcopy(observations)
    states = {}
    fx_pool = {}
    for observation in results:
        captured = observation.get("performance_snapshot")
        snapshot = captured if _valid_snapshot(captured, observation) else {}
        account_map = {row["account_id"]: row for row in snapshot.get("accounts", [])}
        for missing in set(states) - set(account_map) - {None}:
            states.pop(missing, None)
        # Only evidence captured by this endpoint may support its comparison;
        # a later observation must not backfill an earlier missing FX fact.
        for account in snapshot.get("accounts", []):
            for evidence in account.get("fx_evidence", []):
                if _number(evidence.get("rate")) is not None and evidence.get("date"):
                    fx_pool.setdefault((evidence.get("currency"), evidence["date"]), evidence)
            for transaction in account.get("ledger_rows", []):
                evidence = transaction.get("flow_fx_evidence")
                if evidence:
                    fx_pool.setdefault((evidence.get("currency"), evidence.get("date")), evidence)
        scopes = [None, *sorted(account_map)]
        comparisons = {}
        for identifier in scopes:
            source = snapshot.get("total") if identifier is None else account_map[identifier]
            state = states.get(identifier)
            prior = state["observation"] if state else None
            prior_snapshot = prior.get("performance_snapshot") or {} if prior else {}
            beginning = (prior_snapshot.get("total") if identifier is None else next((row for row in prior_snapshot.get("accounts", []) if row["account_id"] == identifier), None)) if prior else None
            reasons = list((source or {}).get("reason_codes") or [])
            if snapshot.get("version") != VERSION or source is None:
                reasons.append("missing_performance_evidence")
            if snapshot.get("base_currency") != base_currency:
                reasons.append("missing_performance_evidence")
            result = {"status": "unavailable", "profit": None, "currency": base_currency,
                      "baseline_date": prior.get("date") if prior else None,
                      "baseline_observed_at": prior.get("observed_at") if prior else None,
                      "baseline_observation_id": prior.get("id") if prior else None,
                      "beginning_equity": beginning.get("equity") if beginning else None,
                      "ending_equity": (source or {}).get("equity"), "recorded_net_flows": None,
                      "segment_id": state["segment_id"] if state else str(observation.get("id") or ""),
                      "reason_codes": [], "coverage": COVERAGE}
            if not reasons and source.get("status") == "ok" and _number(source.get("equity")) is not None:
                if prior is None:
                    result.update(status="baseline", baseline_date=observation.get("date"),
                                  baseline_observed_at=observation.get("observed_at"),
                                  baseline_observation_id=observation.get("id"),
                                  beginning_equity=source["equity"], reason_codes=["baseline_pending"])
                    states[identifier] = {"observation": observation, "segment_id": str(observation.get("id") or "")}
                else:
                    if observation.get("model") != prior.get("model"):
                        reasons.append("model_changed")
                    if snapshot.get("reset_epoch") != prior_snapshot.get("reset_epoch"):
                        reasons.append("reset_epoch_changed")
                    if identifier is None and snapshot.get("scope_account_ids") != prior_snapshot.get("scope_account_ids"):
                        reasons.append("scope_changed")
                    baseline_at = _stamp(prior.get("observed_at"))
                    flows = 0.0
                    if baseline_at is None or beginning is None:
                        reasons.append("missing_performance_evidence")
                    else:
                        old_accounts = {row["account_id"]: row for row in prior_snapshot.get("accounts", [])}
                        for key in account_map if identifier is None else [identifier]:
                            if key not in old_accounts:
                                reasons.append("scope_changed")
                                continue
                            amount, errors = _account_change(old_accounts[key], account_map[key], baseline_at, fx_pool)
                            flows += amount
                            reasons.extend(errors)
                        profit = source["equity"] - beginning["equity"] - flows
                        if not math.isfinite(profit) or not math.isfinite(flows):
                            reasons.append("missing_valuation")
                        if not reasons:
                            result.update(status="recorded", profit=profit, recorded_net_flows=flows)
            else:
                if not reasons:
                    reasons.append("missing_valuation")
            if reasons:
                result["reason_codes"] = list(dict.fromkeys(reasons))
                states.pop(identifier, None)
            comparisons[identifier] = result
        observation["performance"] = {"version": VERSION, "coverage": COVERAGE, "scope": SCOPE,
                                      "total": comparisons[None],
                                      "accounts": [{"account_id": key, **comparisons[key]} for key in sorted(account_map)]}
    return results
