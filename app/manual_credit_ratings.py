"""User-authored agency opinions, distinct from independently read evidence."""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import re

from .credit_ratings import _entity, _matches_entity, _url, normalize_grade
from .security_identifiers import valid_cusip, valid_isin

MANUAL_SCHEMA = "manual-credit-ratings-v1"
AGENCIES = ("moodys", "sp", "fitch")
FIELDS = frozenset({
    "security_key", "agency", "status", "rating", "outlook", "watch", "scope", "entity_name",
    "rating_date", "outlook_date", "watch_date", "source_url", "notes", "scale", "term",
    "expected_revision", "expected_identity",
})


def is_bond(candidate):
    return bool({str(candidate.get(key) or "").upper() for key in ("asset_class", "asset_sub_class")}
                & {"BOND", "FIXED_INCOME"})


def issue_identifier(candidate):
    for key in ("isin", "cusip", "symbol", "secondary_symbol"):
        value = str(candidate.get(key) or "").strip().upper()
        if valid_isin(value) or valid_cusip(value):
            return value
    return None


def manual_policy(candidate):
    canonical = candidate.get("issuer_name") or candidate.get("legal_entity_name") or ""
    verified = bool(candidate.get("issuer_identity_verified") and canonical
                    and _entity(canonical) != _entity(candidate.get("symbol")))
    return {"scale": "global", "term": "long_term", "issuer_identity_verified": verified,
            "canonical_issuer_name": canonical if verified else None,
            "issue_rating_allowed": bool(is_bond(candidate) and issue_identifier(candidate))}


def manual_identity(candidate, source_binding):
    # Identity trust can change without a display-name change. It must also
    # invalidate an old editor and never promote a user's assertion to evidence.
    return hashlib.sha256(json.dumps({"source_binding": source_binding,
        "policy": manual_policy(candidate)}, sort_keys=True).encode()).hexdigest()


def preference_key(candidate, identity):
    return f"{MANUAL_SCHEMA}:{candidate['security_key']}:{identity}"


def _text(payload, key, limit, *, required=False):
    value = payload.get(key)
    if value is None:
        value = ""
    if not isinstance(value, str) or len(value) > limit or re.search(r"[\x00-\x08\x0b-\x1f\x7f]", value):
        raise ValueError("manual_invalid_" + key)
    value = value.strip()
    if required and not value:
        raise ValueError("manual_invalid_" + key)
    return value


def _date(payload, key):
    value = _text(payload, key, 10)
    if not value:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            parsed = date.fromisoformat(value)
        elif re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
            parsed = datetime.strptime(value, "%d/%m/%Y").date()
        else:
            raise ValueError()
        if parsed > datetime.now(timezone.utc).date():
            raise ValueError()
    except ValueError as exc:
        raise ValueError("manual_invalid_date") from exc
    return parsed.isoformat()


def manual_preconditions(payload):
    if not isinstance(payload, dict) or set(payload) - FIELDS:
        raise ValueError("manual_invalid_fields")
    agency = _text(payload, "agency", 12, required=True)
    if agency not in AGENCIES:
        raise ValueError("manual_invalid_agency")
    revision = payload.get("expected_revision")
    if type(revision) is not int or revision < 0:
        raise ValueError("manual_invalid_revision")
    identity = _text(payload, "expected_identity", 64, required=True)
    if not re.fullmatch(r"[0-9a-f]{64}", identity):
        raise ValueError("manual_invalid_identity")
    return agency, revision, identity


def normalize_manual(payload, candidate):
    if (str(candidate.get("stock_market") or "").upper() == "PRIVATE"
            or str(candidate.get("asset_class") or "").upper() not in {"EQUITY", "STOCK", "RSU", "BOND", "FIXED_INCOME"}
            or str(candidate.get("asset_sub_class") or "").upper() in {"OPTION", "FUTURE", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION", "ETF", "FUND", "MUTUALFUND", "MUTUAL_FUND"}
            or str(candidate.get("instrument_type") or "").upper() in {"OPTION", "FUTURE", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION", "ETF", "FUND", "MUTUALFUND", "MUTUAL_FUND"}):
        raise ValueError("manual_unsupported_security")
    agency, _, _ = manual_preconditions(payload)
    status = _text(payload, "status", 12, required=True)
    if status not in {"rated", "unrated", "withdrawn"}:
        raise ValueError("manual_invalid_status")
    if payload.get("scale", "global") != "global" or payload.get("term", "long_term") != "long_term":
        raise ValueError("manual_invalid_scope")
    raw_grade = _text(payload, "rating", 80)
    if status == "rated":
        try:
            grade = normalize_grade(raw_grade, agency)
        except ValueError as exc:
            raise ValueError("manual_invalid_rating") from exc
    else:
        if raw_grade:
            raise ValueError("manual_invalid_rating")
        grade = None
    outlook = _text(payload, "outlook", 12) or "unknown"
    watch = _text(payload, "watch", 12) or "unknown"
    if outlook not in {"unknown", "positive", "negative", "stable", "developing"}:
        raise ValueError("manual_invalid_outlook")
    if watch not in {"unknown", "none", "positive", "negative", "developing"}:
        raise ValueError("manual_invalid_watch")
    if status != "rated" and (outlook != "unknown" or watch != "unknown"):
        raise ValueError("manual_invalid_forward_status")
    policy = manual_policy(candidate)
    scope = _text(payload, "scope", 12) or "issuer"
    if scope not in {"issuer", "issue"} or scope == "issue" and not policy["issue_rating_allowed"]:
        raise ValueError("manual_invalid_scope")
    entity = _text(payload, "entity_name", 300, required=True)
    if not _entity(entity) or not policy["issuer_identity_verified"] and _entity(entity) == _entity(candidate.get("symbol")):
        raise ValueError("manual_invalid_entity")
    if policy["issuer_identity_verified"] and not _matches_entity(entity, {
            "issuer_name": policy["canonical_issuer_name"], "issuer_aliases": candidate.get("issuer_aliases", [])}):
        raise ValueError("manual_invalid_entity")
    source_url = _text(payload, "source_url", 2500)
    notes = _text(payload, "notes", 1000)
    if not source_url and not notes:
        raise ValueError("manual_source_required")
    if source_url:
        try:
            source_url = _url(source_url)
        except ValueError as exc:
            raise ValueError("manual_invalid_source_url") from exc
    dates = {key: _date(payload, key) for key in ("rating_date", "outlook_date", "watch_date")}
    if (dates["outlook_date"] and outlook == "unknown") or (dates["watch_date"] and watch == "unknown"):
        raise ValueError("manual_invalid_date")
    return {"agency": agency, "status": status, "rating": grade, "rating_raw": grade,
            "outlook": outlook, "watch": watch, "scope": scope, "scale": "global", "term": "long_term",
            "rating_type": "issue" if scope == "issue" else "issuer_default" if agency == "fitch" else "issuer",
            "entity_name": entity, "entity_id": issue_identifier(candidate) if scope == "issue" else None,
            "issuer_fallback": bool(is_bond(candidate) and scope == "issuer"),
            "source_url": source_url or None, "notes": notes,
            "identity_verification": "verified_identity" if policy["issuer_identity_verified"] else "user_entered",
            "source_kind": "manual", "manual_override": True, "verification_status": "user_entered",
            "reason_code": "manual_entry", "fetched_at": None, "verified_at": None,
            "observed_at": None, "primary_eligible": True, "staleness_basis": "manual_updated_at",
            "sources": [{"url": source_url, "source_kind": "manual", "fetched_at": None,
                         "verification_status": "user_entered"}] if source_url else [], **dates}
