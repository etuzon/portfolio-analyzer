"""Bounded research receipts. Never copy prompts, source text or exception messages."""
from copy import deepcopy
from datetime import datetime, timezone
import re
import time

EVENT_LIMIT = 200
CHILD_LIMIT = 100
_LABEL = re.compile(r"^[A-Za-z0-9_.:/|^= +\-]{1,300}$")
_COUNTS = {"api_requests", "model_requests", "rest_requests", "web_requests", "max_model_requests",
           "max_rest_requests", "max_web_requests", "search_requests", "source_requests", "read_failures",
           "identity_rejections", "empty_pages", "selected", "completed", "total", "model", "rest", "web"}


def label(value, limit=300):
    return value[:limit] if isinstance(value, str) and _LABEL.fullmatch(value) else None


def counts(value):
    return {key: number for key, number in (value or {}).items()
            if key in _COUNTS and type(number) is int and number >= 0} if isinstance(value, dict) else {}


def failure(value):
    if not isinstance(value, dict):
        return None
    result = {key: clean for key in ("code", "stage", "branch", "error_type", "security_key", "symbol",
                                   "child_request_id", "child_status", "parent_request_id")
              if (clean := label(value.get(key))) is not None}
    if type(value.get("http_status")) is int and 100 <= value["http_status"] <= 599:
        result["http_status"] = value["http_status"]
    result.update(counts(value))
    if isinstance(value.get("child_failure"), dict):
        nested = {key: clean for key in ("code", "stage", "error_type")
                  if (clean := label(value["child_failure"].get(key))) is not None}
        nested.update(counts(value["child_failure"]))
        status = value["child_failure"].get("http_status")
        if type(status) is int and 100 <= status <= 599:
            nested["http_status"] = status
        if nested:
            result["child_failure"] = nested
    return result or None


def snapshot(job, *, branch=None, parent_request_id=None):
    """Safe metadata only; a job's public outcomes may contain fetched evidence."""
    result = {key: label(job.get(key)) for key in ("request_id", "status", "code", "created_at", "finished_at")}
    result["counts"] = counts(job.get("counts"))
    result["failure"] = failure(job.get("failure"))
    progress = job.get("progress") or {}
    current = progress.get("current_security") or {}
    result["progress"] = {**counts(progress), "stage": label(progress.get("stage")),
                          "current_security": {key: clean for key in ("security_key", "symbol", "stock_market", "currency")
                                               if (clean := label(current.get(key))) is not None} or None}
    if branch:
        result["branch"] = branch
    if parent_request_id:
        result["parent_request_id"] = parent_request_id
    elif label(job.get("parent_request_id")):
        result["parent_request_id"] = job["parent_request_id"]
    limits = counts(job.get("per_request_limits") or job.get("per_batch_limits"))
    if limits:
        result["limits"] = limits
    return result


def event(job, writer, name, **fields):
    """Record before finalization, even when the worker cannot reach its save route."""
    started = job.setdefault("_diagnostic_started", time.monotonic())
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "step": name,
             "request_id": job["request_id"], "elapsed_ms": max(0, int((time.monotonic() - started) * 1000)),
             "status": label(job.get("status")), "stage": label((job.get("progress") or {}).get("stage")),
             "counts": counts(job.get("counts"))}
    limits = counts(job.get("per_request_limits") or job.get("per_batch_limits"))
    if limits:
        entry["limits"] = limits
    for key in ("parent_request_id", "child_request_id", "branch", "code", "security_key", "symbol", "action", "tool", "error_type"):
        clean = label(fields.get(key, job.get(key)))
        if clean is not None:
            entry[key] = clean
    if (safe_failure := failure(fields.get("failure"))) is not None:
        entry["failure"] = safe_failure
    for key in ("source_id", "document_id", "link_id", "operation_id"):
        value = fields.get(key)
        if isinstance(value, str) and re.fullmatch(r"(?:source|document|link|operation)-[0-9a-f]{32}", value):
            entry[key] = value
    for key, allowed in (("reader", {"auto", "jina", "direct", "compatible", "official_reference"}),
                         ("reader_engine", {"direct", "rendered"}),
                         ("search_provider", {"yahoo", "duckduckgo", "brave"})):
        if isinstance(fields.get(key), str) and fields[key] in allowed:
            entry[key] = fields[key]
    if isinstance(fields.get("source_counts"), dict):
        entry["source_counts"] = counts(fields["source_counts"])
    for key in ("selected", "available_fields_count", "missing_fields_count", "evidence_count", "source_count", "record_count",
                "context_record_count", "window_start", "window_end"):
        if type(fields.get(key)) is int and fields[key] >= 0:
            entry[key] = fields[key]
    entries = job.setdefault("_diagnostic_events", [])
    entries.append(entry)
    job["_diagnostic_events_total"] = job.get("_diagnostic_events_total", 0) + 1
    del entries[:-EVENT_LIMIT]
    if writer:
        try:
            writer("research_" + name, **deepcopy(entry))
        except Exception:
            pass  # A diagnostic sink cannot change research or authorized saves.


def receipt(job, children=()):
    result = snapshot(job)
    result.update(children=deepcopy(list(children)[-CHILD_LIMIT:]), child_limit=CHILD_LIMIT,
                  children_truncated=len(children) > CHILD_LIMIT,
                  events=deepcopy(job.get("_diagnostic_events", [])), event_limit=EVENT_LIMIT,
                  events_truncated=job.get("_diagnostic_events_total", 0) > EVENT_LIMIT)
    if isinstance(job.get("per_batch_limits"), dict):
        result["per_batch_limits"] = counts(job["per_batch_limits"])
    return result
