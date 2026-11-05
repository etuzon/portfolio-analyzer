"""Revisioned, locally saved historical FX evidence for ILS VaR."""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import logging
import math
import re
from threading import Lock
from time import monotonic

from .value_at_risk import build_var

PREFIX = "var_fx_v1:"
MANAGED_PROVIDER = "daily_fx_observations"
DAILY_ORIGIN = "current_fx_quote"
_maintenance_lock = Lock()
_retry_after = {}
logger = logging.getLogger(__name__)


class VarFxError(ValueError):
    pass


def _currency(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{3}", value.strip()) or value.strip().upper() == "ILS":
        raise VarFxError("var_fx_invalid_currency")
    return value.strip().upper()


def _observation_time(value):
    try:
        if not isinstance(value, str) or not value.strip():
            raise ValueError
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise VarFxError("var_fx_current_rate_unavailable") from exc


def normalize_fx(payload, *, today=None, preserve_observations=False):
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
        saved = {"date": day, "rate": float(number)}
        if preserve_observations and row.get("origin") == DAILY_ORIGIN:
            observation_source, observed_at = row.get("source"), row.get("observed_at")
            if not isinstance(observation_source, str) or not observation_source.strip() or len(observation_source) > 100:
                raise VarFxError("var_fx_invalid_rows")
            if _observation_time(observed_at).date() != date.fromisoformat(day):
                raise VarFxError("var_fx_invalid_rows")
            observation_provider = row.get("provider", observation_source)
            if not isinstance(observation_provider, str) or not observation_provider.strip() or len(observation_provider) > 100:
                raise VarFxError("var_fx_invalid_rows")
            saved.update(origin=DAILY_ORIGIN, provider=observation_provider,
                         source=observation_source, observed_at=observed_at)
        rates[day] = saved
    return {"currency": currency, "source": source.strip(),
            "rates": [row for day, row in sorted(rates.items())]}


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
            normalized = normalize_fx(payload, preserve_observations=True)
            if row["key"] != PREFIX + normalized["currency"] or type(payload.get("revision")) is not int or payload["revision"] < 1:
                raise VarFxError("var_fx_invalid_saved_history")
            result[normalized["currency"]] = {**normalized, "revision": payload["revision"], "updated_at": payload.get("updated_at")}
            if payload.get("managed_by") in {MANAGED_PROVIDER, "bank_of_israel_fx"}:
                result[normalized["currency"]]["managed_by"] = payload["managed_by"]
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


def save_fx_history(store, payload, *, managed_by=None):
    # Only server capture may assign automatic provenance. Manual CSV saves
    # deliberately turn submitted dates into protected manual observations.
    normalized = normalize_fx(payload, preserve_observations=managed_by == MANAGED_PROVIDER)
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
            if managed_by == MANAGED_PROVIDER:
                snapshot["managed_by"] = MANAGED_PROVIDER
            conn.execute("""insert into app_preferences(key,value,updated_at) values(?,?,?)
                            on conflict(key) do update set value=excluded.value,updated_at=excluded.updated_at""",
                         (key, json.dumps(snapshot, allow_nan=False), snapshot["updated_at"]))
    return snapshot


def record_current_fx_quote(store, pair, quote, status, *, expected_revision=None):
    """Append an actual observation dated today; never backfill or invent dates."""
    if not isinstance(pair, str) or not re.fullmatch(r"[A-Z]{3}/ILS", pair):
        raise VarFxError("var_fx_invalid_currency")
    currency = _currency(pair.split("/", 1)[0])
    before = load_fx_histories(store).get(currency)
    revision = before["revision"] if before else 0
    if expected_revision is not None and revision != expected_revision:
        raise VarFxError("var_fx_conflict")
    if before and before.get("invalid"):
        raise VarFxError("var_fx_invalid_saved_history")
    providers = [name for name, state in status.items() if state == "ok"] if isinstance(status, dict) else []
    if (not isinstance(quote, dict) or quote.get("pair") != pair or len(providers) != 1
            or not isinstance(providers[0], str) or not providers[0].strip() or len(providers[0]) > 100):
        raise VarFxError("var_fx_current_rate_unavailable")
    stamp = quote.get("time")
    observed = _observation_time(stamp)
    today = date.today()
    instant = observed.replace(tzinfo=observed.tzinfo or timezone.utc)
    if observed.date() != today or (len(stamp.strip()) > 10 and instant > datetime.now(timezone.utc)):
        raise VarFxError("var_fx_current_rate_unavailable")
    rate = quote.get("rate")
    try:
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate <= 0:
            raise ValueError
        rate = float(rate)
    except (TypeError, ValueError, OverflowError) as exc:
        raise VarFxError("var_fx_current_rate_unavailable") from exc
    day = today.isoformat()
    rates = {row["date"]: row for row in (before or {}).get("rates", [])}
    row = {"date": day, "rate": float(rate), "origin": DAILY_ORIGIN,
           "provider": providers[0], "source": providers[0], "observed_at": stamp}
    existing = rates.get(day)
    if existing:
        if existing.get("origin") != DAILY_ORIGIN:
            return before  # An explicit manual observation always has priority.
        old = _observation_time(existing["observed_at"])
        if instant <= old.replace(tzinfo=old.tzinfo or timezone.utc):
            return before
        if row == existing:
            return before
    rates[day] = row
    return save_fx_history(store, {"currency": currency,
        "source": before["source"] if before else "Recorded daily FX quotes",
        "rates": [value for key, value in sorted(rates.items())],
        "expected_revision": revision}, managed_by=MANAGED_PROVIDER)


def refresh_fx_history(store, market_hub, payload):
    """Explicitly record the current quote. No historical download is performed."""
    if not isinstance(payload, dict):
        raise VarFxError("var_fx_invalid_payload")
    currency = _currency(payload.get("currency"))
    expected = _expected(payload)
    before = load_fx_histories(store).get(currency)
    if (before["revision"] if before else 0) != expected:
        raise VarFxError("var_fx_conflict")
    pair = currency + "/ILS"
    try:
        quote, status = market_hub.fx(pair)
    except Exception as exc:
        raise VarFxError("var_fx_refresh_failed") from exc
    return record_current_fx_quote(store, pair, quote, status, expected_revision=expected)


def maintain_fx_histories(store, market_hub):
    """Record current dated FX quotes during background portfolio refresh."""
    if not _maintenance_lock.acquire(blocking=False):
        return
    try:
        histories = load_fx_histories(store)
        required = build_var(store, market_hub, histories)["fx"]
        for meta in required:
            currency = meta["currency"]
            before = histories.get(currency)
            if before and before.get("invalid"):
                continue
            key = (str(store.path), currency)
            if _retry_after.get(key, 0) > monotonic():
                continue
            _retry_after[key] = monotonic() + 300
            try:
                # Capture the revision BEFORE fetching to protect manual edits
                # made while a provider is responding.
                quote, status = market_hub.fx(currency + "/ILS")
                record_current_fx_quote(store, currency + "/ILS", quote, status,
                    expected_revision=before["revision"] if before else 0)
            except Exception as exc:
                logger.warning("Background current FX recording failed for %s: %s", currency, type(exc).__name__)
    finally:
        _maintenance_lock.release()
