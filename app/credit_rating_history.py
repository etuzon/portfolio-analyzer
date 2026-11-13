"""Durable credit evidence and typed changes; no portfolio or risk calculation."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from .credit_ratings import _entity

SCHEMA = "credit-rating-history-v1"
KNOWN = {"rated", "unrated", "withdrawn"}
AXIS_FIELDS = ("scope", "scale", "term", "rating_type", "currency_basis")
VALUE_FIELDS = ("rating", "status", "outlook", "watch")


def preference_key(security_key, identity):
    return f"{SCHEMA}:{security_key}:{identity}"


def snapshot(value, identity):
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA or value.get("identity_token") != identity:
        return {"schema_version": SCHEMA, "identity_token": identity, "events": [], "baselines": {}, "public_snapshot": None}
    return deepcopy(value)


def axis(row):
    # The enclosing preference identity also binds the exact security key and
    # identified issue. Agency-vendor organization IDs are not issue IDs.
    return (row.get("agency"), _entity(row.get("entity_name")), *(row.get(key) for key in AXIS_FIELDS))


def axis_key(row):
    return json.dumps(axis(row), ensure_ascii=False, separators=(",", ":"))


def _sources(row):
    sources = [{key: deepcopy(value) for key, value in source.items()
                if key in {"url", "title", "evidence_quote", "fetched_at", "source_kind", "fields", "verification_status"}}
               for source in row.get("sources", []) if isinstance(source, dict)]
    if not sources and row.get("source_url"):
        sources = [{"url": row["source_url"], "fetched_at": row.get("fetched_at"),
                    "source_kind": row.get("source_kind"), "evidence_quote": row.get("evidence_quote")}]
    return sources


def event(origin, event_type, before, after, detected_at, changed_fields, *, actor=None):
    before, after = before or {}, after or {}
    identity = after if after.get("entity_name") else before
    action_field = {"rating_change": "rating_date", "outlook_change": "outlook_date", "watch_change": "watch_date"}.get(event_type)
    action_date = after.get(action_field) if origin == "public_ai" and action_field else None
    result = {"agency": identity.get("agency"), "origin": origin, "event_type": event_type,
              "changed_fields": list(changed_fields), "detected_at": detected_at,
              "date_basis": "manual_entry" if origin == "manual" else "agency_action" if action_date else "detected",
              "change_date": action_date, "actor": actor,
              "entity_name": identity.get("entity_name"), **{key: identity.get(key) for key in AXIS_FIELDS},
              "sources": _sources(after) or _sources(before),
              **{key: after.get(key) for key in ("rating_date", "outlook_date", "watch_date")}}
    for field in VALUE_FIELDS:
        result["previous_" + field] = before.get(field)
        result["new_" + field] = after.get(field)
    material = json.dumps(result, sort_keys=True, ensure_ascii=False, default=str)
    result["event_id"] = "credit-event-" + hashlib.sha256(material.encode()).hexdigest()[:24]
    return result


def record_public(value, observations, select, detected_at):
    """Compare selected source facts on each exact axis, including ancillary.

    The caller supplies the same source-selection rules used for the current
    display. Conflicting or unsupported observations never establish a change.
    """
    result = deepcopy(value)
    groups = {}
    for row in observations:
        if row.get("status") in KNOWN:
            groups.setdefault(axis_key(row), []).append(row)
    for key, rows in groups.items():
        current = select(rows)
        if not current or current.get("status") not in KNOWN:
            continue
        previous = result["baselines"].get(key)
        if previous is None:
            result["events"].append(event("public_ai", "first_observation", None, current, detected_at, ["rating", "status"]))
        else:
            grade_fields = [field for field in ("rating", "status") if previous.get(field) != current.get(field)]
            if grade_fields:
                result["events"].append(event("public_ai", "rating_change", previous, current, detected_at, grade_fields))
            for field in ("outlook", "watch"):
                # Missing evidence is not an agency withdrawal of a signal.
                if current.get(field) not in {None, "unknown"} and previous.get(field) != current.get(field):
                    result["events"].append(event("public_ai", field + "_change", previous, current, detected_at, [field]))
        result["baselines"][key] = deepcopy(current)
    return result


def record_manual(value, before, after, detected_at, *, actor, clearing=False):
    result = deepcopy(value)
    event_type = "manual_cleared" if clearing else "manual_updated" if before and before.get("manual_override") else "manual_added"
    fields = [field for field in (*VALUE_FIELDS, "entity_name", *AXIS_FIELDS, "rating_date", "outlook_date", "watch_date", "source_url", "notes")
              if (before or {}).get(field) != (after or {}).get(field)]
    result["events"].append(event("manual", event_type, before, after, detected_at, fields, actor=actor))
    return result


def latest_change(value, row, *, include_manual=True):
    candidates = [entry for entry in value.get("events", []) if entry.get("agency") == row.get("agency")]
    manual = [entry for entry in candidates if entry.get("origin") == "manual"]
    if row.get("manual_override"):
        return deepcopy(max(manual, key=lambda entry: entry["detected_at"], default=None))
    public = [entry for entry in candidates if entry.get("origin") == "public_ai"
              and entry.get("event_type") in {"first_observation", "rating_change"} and axis(entry) == axis(row)]
    cleared = [entry for entry in manual if include_manual and entry.get("event_type") == "manual_cleared"]
    return deepcopy(max(public + cleared, key=lambda entry: entry["detected_at"], default=None))


def compact_change(value):
    if not isinstance(value, dict):
        return None
    result = deepcopy(value)
    result["sources"] = [{key: item for key, item in source.items() if key != "evidence_quote"}
                         for source in result.get("sources", [])]
    return result
