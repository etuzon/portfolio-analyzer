"""Revisioned, locally saved historical FX evidence for ILS VaR."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import math
import re

PREFIX = "var_fx_v1:"
PERIODS = {"1y": 365, "3y": 1096, "5y": 1827}


class VarFxError(ValueError):
    pass


def _currency(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{3}", value.strip()) or value.strip().upper() == "ILS":
        raise VarFxError("var_fx_invalid_currency")
    return value.strip().upper()


def normalize_fx(payload, *, today=None):
    if not isinstance(payload, dict):
        raise VarFxError("var_fx_invalid_payload")
    currency = _currency(payload.get("currency"))
    source = payload.get("source")
    if not isinstance(source, str) or not source.strip() or len(source.strip()) > 500:
        raise VarFxError("var_fx_source_required")
    rows = payload.get("rates")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
        raise VarFxError("var_fx_invalid_rows")
    rates, today = {}, today or date.today()
    for row in rows:
        if not isinstance(row, dict):
            raise VarFxError("var_fx_invalid_rows")
        try:
            day = row["date"]
            if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or date.fromisoformat(day) > today:
                raise ValueError
            number = row["rate"]
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number <= 0:
                raise ValueError
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            raise VarFxError("var_fx_invalid_rows") from exc
        if day in rates:
            raise VarFxError("var_fx_duplicate_date")
        rates[day] = float(number)
    return {"currency": currency, "source": source.strip(),
            "rates": [{"date": day, "rate": rate} for day, rate in sorted(rates.items())]}


def load_fx_histories(store):
    with store._connect() as conn:
        rows = conn.execute("select key,value from app_preferences where substr(key,1,?)=?", (len(PREFIX), PREFIX)).fetchall()
    result = {}
    for row in rows:
        currency = row["key"][len(PREFIX):]
        if not re.fullmatch(r"[A-Z]{3}", currency) or currency == "ILS":
            continue
        payload = {}
        try:
            payload = json.loads(row["value"])
            normalized = normalize_fx(payload)
            if row["key"] != PREFIX + normalized["currency"] or type(payload.get("revision")) is not int or payload["revision"] < 1:
                raise VarFxError("var_fx_invalid_saved_history")
            result[normalized["currency"]] = {**normalized, "revision": payload["revision"], "updated_at": payload.get("updated_at")}
        except (ValueError, TypeError, AttributeError):
            # Retain the failed currency as explicit invalid evidence. It must
            # block scopes needing it, without disabling unrelated ILS scopes.
            revision = payload.get("revision") if isinstance(payload, dict) else None
            result[currency] = {"currency": currency, "source": "", "rates": [], "invalid": True,
                                "revision": revision if type(revision) is int and revision > 0 else 0,
                                "updated_at": None}
    return result


def _expected(payload):
    revision = payload.get("expected_revision")
    if type(revision) is not int or revision < 0:
        raise VarFxError("var_fx_revision_required")
    return revision


def save_fx_history(store, payload):
    normalized = normalize_fx(payload)
    expected = _expected(payload)
    key = PREFIX + normalized["currency"]
    with store._sync_lock:
        with store._connect() as conn:
            conn.execute("begin immediate")
            row = conn.execute("select value from app_preferences where key=?", (key,)).fetchone()
            try:
                before = json.loads(row["value"]) if row else None
                revision = before.get("revision") if isinstance(before, dict) else 0
                revision = revision if type(revision) is int and revision > 0 else 0
            except (ValueError, TypeError, AttributeError):
                revision = 0  # Explicit editor replacement can repair corrupt input.
            if revision != expected:
                raise VarFxError("var_fx_conflict")
            snapshot = {**normalized, "revision": expected + 1,
                        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
            conn.execute("""insert into app_preferences(key,value,updated_at) values(?,?,?)
                            on conflict(key) do update set value=excluded.value,updated_at=excluded.updated_at""",
                         (key, json.dumps(snapshot, allow_nan=False), snapshot["updated_at"]))
    return snapshot


def refresh_fx_history(store, market_hub, payload):
    if not isinstance(payload, dict):
        raise VarFxError("var_fx_invalid_payload")
    currency = _currency(payload.get("currency"))
    expected = _expected(payload)
    period = payload.get("period", "3y")
    if not isinstance(period, str) or period not in PERIODS:
        raise VarFxError("var_fx_invalid_period")
    before = load_fx_histories(store).get(currency)
    if (before["revision"] if before else 0) != expected:
        raise VarFxError("var_fx_conflict")
    today = date.today()
    try:
        fetched = market_hub.fx_history(currency, today - timedelta(days=PERIODS[period]), today)
    except Exception as exc:
        raise VarFxError("var_fx_refresh_failed") from exc
    # The selected identity is bound here, and optimistic save detects a new
    # manual report written while the public central-bank request was running.
    if not isinstance(fetched, dict) or fetched.get("currency") != currency:
        raise VarFxError("var_fx_refresh_failed")
    try:
        return save_fx_history(store, {**fetched, "expected_revision": expected})
    except VarFxError as exc:
        if str(exc) == "var_fx_conflict":
            raise
        raise VarFxError("var_fx_refresh_failed") from exc
