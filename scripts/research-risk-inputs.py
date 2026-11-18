#!/usr/bin/env python3
"""Start, resume or inspect risk research through authenticated REST only."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import ssl
import stat
import sys
import time
from urllib.parse import urlsplit

import httpx


PREFIX = "/api/securities/enrichment"
ACTIVE = {"queued", "running"}


class RunError(Exception):
    def __init__(self, code, status=None):
        self.code, self.status = code, status
        super().__init__(code)


def credential(path=None):
    if path:
        source = Path(path)
        if stat.S_IMODE(source.stat().st_mode) & 0o077:
            raise RunError("token_file_must_be_private")
        value = source.read_text().strip()
    else:
        value = os.environ.get("PORTFOLIO_API_TOKEN", "").strip()
    if not value:
        raise RunError("api_token_required")
    if not re.fullmatch(r"[A-Za-z0-9._~+/=-]{1,512}", value):
        raise RunError("invalid_api_token_format")
    return value


def base_url(value):
    parsed = urlsplit(value)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (parsed.scheme != "https" and not (parsed.scheme == "http" and local)
            or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise argparse.ArgumentTypeError("Use an HTTPS application origin, or HTTP on loopback.")
    return value.rstrip("/")


def identifier(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise argparse.ArgumentTypeError("Use the request ID returned by the application.")
    return value


def request(client, method, path, payload=None):
    try:
        response = client.request(method, path, json=payload)
    except httpx.HTTPError:
        raise RunError("rest_transport_failed") from None
    if not response.is_success:
        try:
            detail = response.json().get("detail")
            code = detail.get("code") if isinstance(detail, dict) else detail
        except (ValueError, AttributeError):
            code = None
        if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9_:-]{1,100}", code):
            code = "rest_request_failed"
        raise RunError(code, response.status_code)
    try:
        body = response.json()
    except ValueError:
        raise RunError("invalid_rest_response") from None
    if not isinstance(body, dict):
        raise RunError("invalid_rest_response")
    return body


def frozen_resume(job):
    if job.get("status") != "failed" or "risk_inputs" not in job.get("data_types", []):
        raise RunError("failed_risk_request_required")
    return {"resume_request_id": job["request_id"], "position_scope": job.get("position_scope", "open"),
            "security_keys": job.get("security_keys"), "data_types": job["data_types"],
            "refresh_policy": job.get("refresh_policy", "missing"), "risk_mode": job.get("risk_mode", "api_then_ai")}


def progress(job):
    current = job.get("progress") or {}
    return {"request_id": job.get("request_id"), "status": job.get("status"), "code": job.get("code"),
            "stage": current.get("stage"), "completed": current.get("completed", 0), "total": current.get("total", 0),
            "current_security": current.get("current_security"), "counts": job.get("counts", {})}


def run(client, args, *, sleep=time.sleep, monotonic=time.monotonic, emit=None):
    """One explicit start/resume; observation never restarts failed work."""
    if args.request_id or args.resume_request_id:
        previous = request(client, "GET", PREFIX + "/ai/" + (args.request_id or args.resume_request_id))
        job = request(client, "POST", PREFIX + "/ai", frozen_resume(previous)) if args.resume_request_id else previous
    else:
        job = request(client, "POST", PREFIX + "/ai", {
            "data_types": ["risk_inputs"], "position_scope": args.position_scope,
            "security_keys": args.security_key or None, "refresh_policy": args.refresh_policy, "risk_mode": args.mode})
    job_id = identifier(str(job.get("request_id", "")))
    deadline, last = monotonic() + args.wait_timeout, None
    while True:
        observation = progress(job)
        if observation != last and emit:
            emit(observation)
        last = observation
        if job.get("status") not in ACTIVE:
            break
        if monotonic() >= deadline:
            # The running request remains available for --request-id. No retry.
            return {"status": "pending", "request_id": job_id, "job": job}
        sleep(min(args.poll_interval, max(0, deadline - monotonic())))
        job = request(client, "GET", PREFIX + "/ai/" + job_id)
    receipt = {"status": job["status"], "request_id": job_id, "job": job,
               "diagnostics": request(client, "GET", PREFIX + "/ai/" + job_id + "/diagnostics"), "saved_risk_inputs": []}
    receipt["child_diagnostics"] = []
    children = list(receipt["diagnostics"].get("children", []))
    seen = set()
    while children and len(seen) < 100:
        child = children.pop(0)
        children.extend(child.get("children", []))
        child_id = child.get("request_id")
        if child.get("branch") == "risk_ai" and child_id not in seen:
            seen.add(child_id)
            receipt["child_diagnostics"].append(request(client, "GET",
                "/api/securities/risk-inputs/research/ai/" + identifier(str(child_id)) + "/diagnostics"))
    # Reload accepted evidence using the same initiating identity. A terminal
    # research status alone does not demonstrate that a requested fact was saved.
    for row in (job.get("risk_inputs") or {}).get("outcomes", []):
        key = row.get("security_key")
        if key:
            identity = str(key).rsplit("|", 2)
            if len(identity) != 3:
                raise RunError("invalid_security_identity")
            receipt["saved_risk_inputs"].append(request(client, "GET", "/api/securities/risk-inputs?" +
                str(httpx.QueryParams(dict(zip(("symbol", "stock_market", "currency"), identity))))))
    return receipt


def write_receipt(path, receipt):
    target = Path(path)
    if target.is_symlink():
        raise RunError("receipt_symlink_not_allowed")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        os.fchmod(handle.fileno(), 0o600)
        json.dump(receipt, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--url", type=base_url, default="https://localhost:6443")
    result.add_argument("--token-file", help="Private token file; otherwise use PORTFOLIO_API_TOKEN. Credentials are never printed.")
    trust = result.add_mutually_exclusive_group()
    trust.add_argument("--ca-file", help="Certificate that signs the application HTTPS endpoint.")
    trust.add_argument("--insecure", action="store_true", help="Accept the established local self-signed HTTPS service.")
    action = result.add_mutually_exclusive_group()
    action.add_argument("--request-id", type=identifier, help="Observe this existing request without starting another.")
    action.add_argument("--resume-request-id", type=identifier, help="Explicitly resume failed work with its frozen settings.")
    result.add_argument("--security-key", action="append", default=[], help="Exact listing key; repeat for up to three listings. Omit for all eligible securities.")
    result.add_argument("--mode", choices=["api_then_ai", "api", "ai"], default="api_then_ai")
    result.add_argument("--position-scope", choices=["open", "all"], default="open")
    result.add_argument("--refresh-policy", choices=["missing", "stale", "refresh_existing"], default="stale")
    result.add_argument("--wait-timeout", type=float, default=900, help="Maximum observation seconds; does not cancel or restart work.")
    result.add_argument("--poll-interval", type=float, default=5)
    result.add_argument("--output", help="Save full status, diagnostics and reloaded risk evidence to a private JSON receipt.")
    return result


def main(argv=None):
    options = parser()
    args = options.parse_args(argv)
    if len(args.security_key) > 3 or any(not key or len(key) > 300 for key in args.security_key):
        options.error("Choose one to three exact listing keys, or omit them for all eligible securities.")
    if not 1 <= args.poll_interval <= 60 or not 0 <= args.wait_timeout <= 86400:
        options.error("Use a poll interval of 1–60 seconds and a wait timeout of 0–86400 seconds.")
    try:
        token = credential(args.token_file)
        verify = False if args.insecure else ssl.create_default_context(cafile=args.ca_file)
        with httpx.Client(base_url=args.url, headers={"Authorization": "Bearer " + token, "Accept-Language": "en"},
                          verify=verify, follow_redirects=False, timeout=30) as client:
            receipt = run(client, args, emit=lambda row: print(json.dumps(row, ensure_ascii=False), flush=True))
        if args.output:
            write_receipt(args.output, receipt)
        print(json.dumps({"status": receipt["status"], "request_id": receipt["request_id"],
                          "receipt": str(args.output) if args.output else None,
                          "failure": receipt["job"].get("failure"),
                          "risk_summary": (receipt["job"].get("risk_inputs") or {}).get("summary", {})}, ensure_ascii=False))
        return 0 if receipt["status"] == "completed" else 2
    except (RunError, OSError) as error:
        print(json.dumps({"status": "failed", "code": getattr(error, "code", "local_file_error"),
                          "http_status": getattr(error, "status", None)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
