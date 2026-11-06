"""Frozen, observed dashboard risk assessments; never reconstruct past risk.

The existing browser model computes scores from a server-issued coherent context.
These records deliberately say client-calculated: validation is not recomputation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
import secrets
from threading import RLock
from typing import Any, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

from .local_portfolio import _cash_delta

MODEL = "portfolio-risk-v2"
SOURCE = "dashboard_client_calculated"
PREFIX = "risk_history_v1:"
CONTEXT_TTL = timedelta(minutes=10)
MAX_CONTEXTS = 1024
MAX_READ = 10000
_COMPONENTS = {"concentration", "asset_mix", "currency", "industry", "cash", "derivatives", "volatility", "horizon", "issuer_country", "data_quality", "borrowing"}
_lock = RLock()
_contexts: dict[str, dict[str, Any]] = {}


class RiskHistoryError(ValueError):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str).encode()
    except (TypeError, ValueError):
        raise RiskHistoryError("risk_context_incomplete_values", 409) from None
    return hashlib.sha256(encoded).hexdigest()


def _number(value: Any) -> float | None:
    try:
        return float(value) if type(value) in (int, float) and math.isfinite(value) else None
    except (ValueError, OverflowError):
        return None


def _currency(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{3}", value):
        raise RiskHistoryError("risk_history_invalid_currency")
    return value


def account_label(account: dict) -> str:
    return " · ".join(str(account.get(key) or "").strip() for key in ("management_company", "username", "account_id") if account.get(key)) or str(account.get("id") or "")


def canonical_inputs(items: list, accounts: list, transactions: list, fx: dict, base_currency: str) -> dict:
    """Match portfolioItems/portfolioAccounts without introducing a new scope."""
    base_currency = _currency(base_currency)
    non_esop = [deepcopy(account) for account in accounts if str(account.get("type") or "").upper() != "ESOP"]
    by_id = {str(account["id"]): account for account in non_esop}
    all_by_id = {str(account["id"]): account for account in accounts}
    rows = []
    account_ids: set[str] = set()
    for item in items:
        holding = item.get("holding") or {}
        account_id = str(holding.get("account_id") or "")
        asset = str(holding.get("asset_class") or holding.get("asset_sub_class") or "").upper()
        if (str(all_by_id.get(account_id, {}).get("type") or "").upper() == "ESOP"
                or str(holding.get("account_type") or "").upper() == "ESOP"
                or asset in {"RSU", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION"}):
            continue
        if account_id not in by_id:
            raise RiskHistoryError("risk_context_unassigned_account", 409)
        rows.append(deepcopy(item))
        account_ids.add(account_id)
    txs = [deepcopy(tx) for tx in transactions if str(tx.get("account_db_id") or "") in by_id]
    rates = {}
    for quote in fx.get("quotes", []):
        value = _number((quote.get("quote") or {}).get("rate"))
        if value is not None and value > 0:
            rates[quote.get("pair")] = value
    def require_fx(currency, value):
        if not value:
            return
        if not currency:
            raise RiskHistoryError("risk_context_missing_fx", 409)
        if currency != base_currency and not (rates.get(f"{currency}/{base_currency}") or rates.get(f"{base_currency}/{currency}")):
            raise RiskHistoryError("risk_context_missing_fx", 409)
    for item in rows:
        holding = item["holding"]
        value = _number(holding.get("market_value"))
        if value is None or _number(holding.get("quantity")) is None or (holding["quantity"] != 0 and value == 0):
            raise RiskHistoryError("risk_context_incomplete_values", 409)
        require_fx(holding.get("currency"), value)
    for account in non_esop:
        cash = float(account.get("initial_cash") or 0) + sum(_cash_delta(tx) for tx in txs if str(tx.get("account_db_id")) == str(account["id"]))
        if not math.isfinite(cash):
            raise RiskHistoryError("risk_context_incomplete_values", 409)
        if cash:
            account_ids.add(str(account["id"]))
        require_fx(account.get("currency"), cash)
    return {"model": MODEL, "base_currency": base_currency, "items": rows, "accounts": non_esop,
            "transactions": txs, "fx": deepcopy(fx), "account_ids": sorted(account_ids)}


def create_context(store, user_id: str, base_currency: str, capture: Callable[[str], dict]) -> dict:
    inputs = capture(_currency(base_currency))
    now = _now()
    context = {**deepcopy(inputs), "fingerprint": _digest({key: value for key, value in inputs.items() if key != "guard"}),
               "observed_at": _timestamp(now), "date": now.astimezone(ZoneInfo("Asia/Jerusalem")).date().isoformat()}
    token = secrets.token_urlsafe(32)
    with _lock:
        for key in list(_contexts):
            if _contexts[key]["expires_at"] <= now:
                del _contexts[key]
        if len(_contexts) >= MAX_CONTEXTS:
            del _contexts[next(iter(_contexts))]
        _contexts[token] = {"user_id": user_id, "path": str(store.path), "expires_at": now + CONTEXT_TTL, "context": context}
    return deepcopy({key: value for key, value in {**context, "token": token, "source": SOURCE}.items() if key != "guard"})


def _risk(value: Any) -> dict:
    if not isinstance(value, dict) or type(value.get("score")) is not int or not 0 <= value["score"] <= 100:
        raise RiskHistoryError("risk_history_invalid_score")
    components = value.get("components")
    if not isinstance(components, dict) or not (
        set(components) == _COMPONENTS
        or (value["score"] == 0 and components == {})
        or (value["score"] == 100 and components == {"borrowing": 100})
    ):
        raise RiskHistoryError("risk_history_invalid_components")
    if any(_number(number) is None or not 0 <= number <= 100 for number in components.values()):
        raise RiskHistoryError("risk_history_invalid_components")
    quality = value.get("quality_details", [])
    if not isinstance(quality, list) or len(quality) > 100 or any(not isinstance(row, dict) for row in quality):
        raise RiskHistoryError("risk_history_invalid_quality")
    for detail in quality:
        for field in ("weight_percent", "points_before_cap"):
            if field in detail and (_number(detail[field]) is None or detail[field] < 0):
                raise RiskHistoryError("risk_history_invalid_quality")
        if "symbols" in detail and (not isinstance(detail["symbols"], list) or any(not isinstance(symbol, str) for symbol in detail["symbols"])):
            raise RiskHistoryError("risk_history_invalid_quality")
        if "affected" in detail:
            if not isinstance(detail["affected"], list) or any(not isinstance(row, dict) for row in detail["affected"]):
                raise RiskHistoryError("risk_history_invalid_quality")
            for affected in detail["affected"]:
                for field in ("symbol", "stock_market", "account_id"):
                    if field in affected and not isinstance(affected[field], str):
                        raise RiskHistoryError("risk_history_invalid_quality")
                if "missing_fields" in affected and (not isinstance(affected["missing_fields"], list) or any(not isinstance(field, str) for field in affected["missing_fields"])):
                    raise RiskHistoryError("risk_history_invalid_quality")
    try:
        if len(json.dumps(quality, allow_nan=False)) > 65536:
            raise RiskHistoryError("risk_history_invalid_quality")
    except (TypeError, ValueError):
        raise RiskHistoryError("risk_history_invalid_quality") from None
    result = {"score": value["score"], "components": deepcopy(components), "quality_details": deepcopy(quality)}
    for field in ("cash_pct", "cash_debt", "net_equity", "unlevered_score"):
        if field in value:
            if _number(value[field]) is None:
                raise RiskHistoryError("risk_history_invalid_metadata")
            result[field] = value[field]
    if "drivers" in value:
        drivers = value["drivers"]
        if not isinstance(drivers, list) or len(drivers) > 30 or any(not isinstance(driver, str) or len(driver) > 1000 for driver in drivers):
            raise RiskHistoryError("risk_history_invalid_metadata")
        result["drivers"] = list(drivers)
    return result


def save_observation(store, user_id: str, payload: Any, capture: Callable[[str], dict], guard: Callable[[], Any], current_fx: Callable[[dict], dict] | None = None) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("token"), str):
        raise RiskHistoryError("risk_history_context_required")
    with _lock, store._sync_lock:
        entry = _contexts.get(payload["token"])
        if not entry or entry["user_id"] != user_id or entry["path"] != str(store.path):
            raise RiskHistoryError("risk_context_expired", 409)
        if entry["expires_at"] <= _now():
            del _contexts[payload["token"]]
            raise RiskHistoryError("risk_context_expired", 409)
        context = entry["context"]
        current = capture(context["base_currency"])
        if current.get("guard") != context.get("guard") or _digest({key: value for key, value in current.items() if key != "guard"}) != context["fingerprint"]:
            raise RiskHistoryError("risk_context_stale", 409)
        total = _risk(payload.get("total"))
        raw_accounts = payload.get("accounts")
        if not isinstance(raw_accounts, list) or len(raw_accounts) != len(context["account_ids"]):
            raise RiskHistoryError("risk_history_invalid_accounts")
        ids = [row.get("account_id") for row in raw_accounts if isinstance(row, dict)]
        if len(ids) != len(raw_accounts) or any(not isinstance(value, str) for value in ids) or len(set(ids)) != len(ids) or set(ids) != set(context["account_ids"]):
            raise RiskHistoryError("risk_history_invalid_accounts")
        by_id = {account["id"]: account for account in context["accounts"]}
        accounts = [{"account_id": row["account_id"], "account_label": account_label(by_id[row["account_id"]]), "risk": _risk(row.get("risk"))} for row in raw_accounts]
        # A SQLite write reservation prevents local financial writes from racing
        # the final revision check and immutable observation publication.
        with store._connect() as connection:
            connection.execute("begin immediate")
            if guard() != context.get("guard") or (current_fx is not None and _digest(current_fx(context)) != _digest(context["fx"])):
                raise RiskHistoryError("risk_context_stale", 409)
            dedup = _digest([context["fingerprint"], context["date"]])
            key = PREFIX + dedup
            existing = connection.execute("select value from app_preferences where key=?", (key,)).fetchone()
            if existing:
                return {"saved": False, "observation": json.loads(existing["value"])}
            observation = {"id": str(uuid4()), "observed_at": context["observed_at"], "date": context["date"], "model": MODEL,
                           "source": SOURCE, "base_currency": context["base_currency"], "fingerprint": context["fingerprint"], "total": total, "accounts": accounts,
                           "evidence": {"fx": deepcopy(context["fx"]), "position_count": len(context["items"]),
                                        "source_signature": context["guard"][0], "generation": context["guard"][1],
                                        "scope": "canonical_non_esop"}}
            connection.execute("insert into app_preferences(key,value,updated_at) values(?,?,?)", (key, json.dumps(observation, allow_nan=False), context["observed_at"]))
        return {"saved": True, "observation": observation}


def list_observations(store, base_currency: str, days: int = 90) -> dict:
    base_currency = _currency(base_currency)
    if type(days) is not int or not 0 <= days <= 3660:
        raise RiskHistoryError("risk_history_invalid_days")
    cutoff = (_now().astimezone(ZoneInfo("Asia/Jerusalem")).date() - timedelta(days=days - 1)).isoformat() if days else "0000-01-01"
    with store._connect() as connection:
        # SQL caps the read, but old observations remain in the local database.
        rows = connection.execute("""select value from app_preferences where key glob ? and json_valid(value)
            and json_extract(value,'$.model')=? and json_extract(value,'$.base_currency')=?
            and json_extract(value,'$.date')>=? order by updated_at desc,key desc limit ?""",
            (PREFIX + "*", MODEL, base_currency, cutoff, MAX_READ + 1)).fetchall()
        malformed_json = connection.execute("select count(*) from app_preferences where key glob ? and not json_valid(value)", (PREFIX + "*",)).fetchone()[0]
    observations = []
    invalid_records = int(malformed_json)
    for row in rows:
        try:
            value = json.loads(row["value"])
        except (TypeError, ValueError):
            invalid_records += 1
            continue
        try:
            if (not isinstance(value, dict) or value.get("source") != SOURCE
                    or not all(isinstance(value.get(key), str) for key in ("id", "date", "observed_at"))
                    or not isinstance(value.get("accounts"), list)):
                raise ValueError()
            datetime.fromisoformat(value["observed_at"].replace("Z", "+00:00"))
            datetime.strptime(value["date"], "%Y-%m-%d")
            _risk(value.get("total"))
            for account in value["accounts"]:
                if not isinstance(account, dict) or not isinstance(account.get("account_id"), str) or not isinstance(account.get("account_label"), str):
                    raise ValueError()
                _risk(account.get("risk"))
        except (TypeError, ValueError):
            invalid_records += 1
            continue
        if value.get("model") == MODEL and value.get("base_currency") == base_currency and value.get("date", "") >= cutoff:
            observations.append(value)
    observations.sort(key=lambda value: (value["observed_at"], value["id"]))
    labels = {}
    for observation in observations:
        for account in observation.get("accounts", []):
            labels[account["account_id"]] = account["account_label"]
    for account in store.list_accounts():
        if str(account.get("type") or "").upper() != "ESOP":
            labels[str(account["id"])] = account_label(account)
    return {"model": MODEL, "base_currency": base_currency, "source": SOURCE, "items": observations[-MAX_READ:],
            "accounts": [{"id": key, "label": labels[key]} for key in sorted(labels)], "truncated": len(rows) > MAX_READ, "invalid_records": invalid_records}
