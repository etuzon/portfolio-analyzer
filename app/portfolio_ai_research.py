"""Application-owned queue of bounded market-data and public-rating jobs.

The coordinator never calls a model. Each child retains its existing REST-only
planner, authentication, validation and per-request call ceilings.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock, Thread
import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, StrictBool

from .security_enrichment import EnrichmentStart, MAX_SELECTED

PREFIX = "/api/securities/enrichment"
AGENCIES = ("moodys", "sp", "fitch")
IDENTITY_FIELDS = ("security_key", "symbol", "stock_market", "currency", "name", "asset_class", "asset_sub_class")


def _now():
    return datetime.now(timezone.utc).isoformat()


class PortfolioResearchStart(EnrichmentStart):
    resume_request_id: str | None = Field(default=None, min_length=1, max_length=100)
    ratings_only: StrictBool = False


class PortfolioAIResearch:
    def __init__(self, market_jobs, credit_jobs, inventory_reader, *, worker_factory=Thread, poll_seconds=0.25):
        self.market_jobs, self.credit_jobs = market_jobs, credit_jobs
        self.inventory_reader, self._worker_factory = inventory_reader, worker_factory
        self.poll_seconds = poll_seconds
        self._lock, self._jobs = RLock(), {}

    @staticmethod
    def _public(job):
        return deepcopy({key: value for key, value in job.items() if not key.startswith("_")})

    def _owned(self, identifier, owner):
        job = self._jobs.get(identifier)
        if not job or job["_user_id"] != owner:
            raise HTTPException(404, "enrichment_request_not_found")
        return job

    def get(self, identifier, owner):
        with self._lock:
            if identifier in self._jobs:
                return self._public(self._owned(identifier, owner))
        # Internal child URLs and requests started before this coordinator was
        # introduced retain the original owner/authentication contract.
        return self.market_jobs.get(identifier, owner)

    @staticmethod
    def _summary(rows):
        return {"total_candidates": len(rows), "selected": len(rows), **{
            status: sum(row.get("status") == status for row in rows)
            for status in ("updated", "partial", "unavailable", "not_attempted")}}

    def _pending(self, job, branch):
        return [row for row in job["_targets"][branch] if row["security_key"] not in job["_done"][branch]]

    @staticmethod
    def _batch_size(branch):
        # A shared three-issuer budget can be spent entirely on its first
        # company. Give every issuer an explicit, bounded public research job.
        return 1 if branch == "credit" else MAX_SELECTED

    def _recount(self, job, active=None):
        children = [item["job"] for item in job["_children"]]
        if active and active["request_id"] not in {row["request_id"] for row in children}:
            children.append(active)
        limits = job["per_batch_limits"]
        for field in ("model", "rest", "web"):
            job["counts"][field + "_requests"] = sum(int(child.get("counts", {}).get(field + "_requests", 0)) for child in children)
            job["counts"]["max_" + field + "_requests"] = job["_planned_children"] * limits[field]

    def _capture(self, job):
        captured = self.inventory_reader(job["position_scope"], ratings_only=True) if job["ratings_only"] else self.inventory_reader(job["position_scope"])
        selected = set(job["_security_keys"] or [])
        for branch, field in (("market", "market_items"), ("credit", "credit_items")):
            unique = {}
            for original in ([] if branch == "market" and job["ratings_only"] else captured.get(field, [])):
                key = original.get("security_key")
                if key and (not selected or key in selected):
                    unique.setdefault(key, {name: deepcopy(original.get(name)) for name in IDENTITY_FIELDS})
            job["_targets"][branch] = list(unique.values())
        job["outcomes"] = [{**row, "status": "pending", "code": "queued", "attempted": False}
                           for row in job["_targets"]["market"]]
        credit = job["credit_ratings"]
        credit["outcomes"] = [{**row, "status": "pending", "code": "queued", "attempted": False,
            "verified_agencies": [], "agency_statuses": {agency: "not_checked" for agency in AGENCIES}}
            for row in job["_targets"]["credit"]]
        credit["progress"]["total"] = len(credit["outcomes"])
        credit["summary"] = self._summary(credit["outcomes"])
        job["summary"] = self._summary(job["outcomes"])
        job["captured_at"] = _now()
        job["_captured"] = True

    def start(self, user_id, headers, language, position_scope="open", *, security_keys=None,
              resume_request_id=None, scheduled_credentials=None, ratings_only=False):
        if type(ratings_only) is not bool:
            raise HTTPException(422, "invalid_research_mode")
        if position_scope not in {"open", "all"}:
            raise HTTPException(422, "invalid_position_scope")
        if security_keys is not None and (not security_keys or len(security_keys) > MAX_SELECTED
                or any(not isinstance(key, str) or not key.strip() or len(key) > 300 for key in security_keys)):
            raise HTTPException(422, "invalid_enrichment_candidate")
        if security_keys is not None:
            security_keys = list(dict.fromkeys(key.strip().upper() for key in security_keys))
        with self._lock:
            active = next((job for job in self._jobs.values()
                if job["_user_id"] == user_id and job["status"] in {"queued", "running"}), None)
            if active:
                if active["position_scope"] != position_scope or active["ratings_only"] != ratings_only or set(active["_security_keys"] or []) != set(security_keys or []) or (
                        resume_request_id and active["request_id"] != resume_request_id):
                    raise HTTPException(409, "enrichment_busy")
                return self._public(active)
            if sum(job["status"] in {"queued", "running"} for job in self._jobs.values()) >= 2:
                raise HTTPException(409, "enrichment_busy")
            if resume_request_id:
                job = self._owned(resume_request_id, user_id)
                if job["position_scope"] != position_scope or job["ratings_only"] != ratings_only or set(job["_security_keys"] or []) != set(security_keys or []):
                    raise HTTPException(409, "enrichment_scope_changed")
                if job["status"] != "failed" or job["_captured"] and not any(self._pending(job, branch) for branch in ("market", "credit")):
                    raise HTTPException(409, "nothing_to_resume")
                job.update(status="queued", code="queued", failure=None, finished_at=None)
                for row in job["outcomes"] + job["credit_ratings"]["outcomes"]:
                    if row["status"] == "not_attempted":
                        row.update(status="pending", code="queued")
                job["credit_ratings"]["status"] = "queued"
            else:
                settings = self.market_jobs.settings()
                limits = {kind: min(8, max(1, int(settings.get(field, 8)))) for kind, field in
                          (("model", "max_tool_loops"), ("rest", "max_rest_calls"), ("web", "max_web_calls"))}
                job = {"request_id": str(uuid4()), "position_scope": position_scope, "ratings_only": ratings_only, "status": "queued", "code": "queued",
                    "created_at": _now(), "finished_at": None, "failure": None, "outcomes": [], "summary": self._summary([]),
                    "counts": {}, "per_batch_limits": limits, "coverage": {"inventory_truncated": False, "listed_candidates": 0},
                    "progress": {"stage": "queued", "completed": 0, "total": 0, "current_security": None},
                    "portfolio_refresh_required": False,
                    "credit_ratings": {"status": "queued", "progress": {"completed": 0, "total": 0, "current_security": None},
                        "summary": self._summary([]), "outcomes": []},
                    "_user_id": user_id, "_security_keys": list(dict.fromkeys(security_keys)) if security_keys else None,
                    "_targets": {"market": [], "credit": []}, "_done": {"market": set(), "credit": set()},
                    "_children": [], "_planned_children": 0, "_captured": False}
                self._jobs[job["request_id"]] = job
                completed = [key for key, value in self._jobs.items() if value["status"] not in {"queued", "running"}]
                for key in completed[:-97]:
                    self._jobs.pop(key, None)
            cleanup = None
            if scheduled_credentials is not None:
                try:
                    headers, cleanup = scheduled_credentials()
                except Exception:
                    job.update(status="failed", code="owner_not_authorized", failure={"code": "owner_not_authorized"}, finished_at=_now())
                    raise
            forwarded = {key: value for key, value in headers.items() if key.lower() in {"cookie", "authorization", "x-csrf-token"}}
        cleaned = False
        def cleanup_once():
            nonlocal cleaned
            if cleanup and not cleaned:
                cleaned = True
                cleanup()
        def work():
            try:
                self.run(job["request_id"], forwarded, language)
            finally:
                cleanup_once()
        try:
            self._worker_factory(target=work, daemon=True, name="portfolio-ai-research").start()
        except Exception:
            cleanup_once()
            with self._lock:
                job.update(status="failed", code="job_failed", failure={"code": "job_failed"}, finished_at=_now())
            raise
        with self._lock:
            return self._public(job)

    def _accept_child(self, parent, branch, batch, child):
        outcomes = parent["outcomes"] if branch == "market" else parent["credit_ratings"]["outcomes"]
        returned = {row["security_key"]: row for row in child.get("outcomes", []) if row.get("security_key")}
        for row in outcomes:
            if row["security_key"] not in {item["security_key"] for item in batch}:
                continue
            result = returned.get(row["security_key"])
            public_attempted = branch != "credit" or int(child.get("counts", {}).get("web_requests", 0)) > 0
            completed = bool(public_attempted and result and (child["status"] == "completed" or result.get("status") in {"updated", "partial"}))
            if completed:
                row.update(deepcopy(result))
                parent["_done"][branch].add(row["security_key"])
            else:
                row.update(status="not_attempted", code="check_incomplete", attempted=bool(public_attempted and result and result.get("attempted")))
        parent["_children"].append({"branch": branch, "job": deepcopy(child)})
        parent["summary"] = self._summary(parent["outcomes"])
        parent["credit_ratings"]["summary"] = self._summary(parent["credit_ratings"]["outcomes"])
        parent["credit_ratings"]["progress"]["completed"] = len(parent["_done"]["credit"])
        parent["portfolio_refresh_required"] |= bool(child.get("portfolio_refresh_required"))
        self._recount(parent)

    def run(self, identifier, headers, language):
        with self._lock:
            parent = self._jobs[identifier]
            parent.update(status="running", code="running")
        try:
            if not parent["_captured"]:
                # This is trusted application inventory capture, not a model
                # tool or a financial-data callback from an AI planner.
                captured = deepcopy(parent)
                self._capture(captured)
                with self._lock:
                    for key in ("_targets", "outcomes", "credit_ratings", "summary", "captured_at", "_captured"):
                        parent[key] = captured[key]
            with self._lock:
                remaining = sum((len(self._pending(parent, branch)) + self._batch_size(branch) - 1) // self._batch_size(branch)
                                for branch in ("market", "credit"))
                parent["_planned_children"] = len(parent["_children"]) + remaining
                parent["coverage"]["listed_candidates"] = len(parent["_targets"]["market"]) + len(parent["_targets"]["credit"])
                self._recount(parent)
            for branch, manager in (("market", self.market_jobs), ("credit", self.credit_jobs)):
                pending = self._pending(parent, branch)
                stage = "researching_market_data" if branch == "market" else "researching_ratings"
                with self._lock:
                    parent["progress"].update(stage=stage, completed=len(parent["_done"][branch]),
                        total=len(parent["_targets"][branch]), current_security=None)
                    if branch == "credit":
                        parent["credit_ratings"]["status"] = "running"
                size = self._batch_size(branch)
                for offset in range(0, len(pending), size):
                    batch = pending[offset:offset + size]
                    child = manager.start(parent["_user_id"], headers, language, parent["position_scope"],
                                          security_keys=[row["security_key"] for row in batch])
                    while child["status"] in {"queued", "running"}:
                        with self._lock:
                            self._recount(parent, child)
                            progress = child.get("progress") or {}
                            # Preflight/model phases are not completed checks.
                            # Count a security only after its child finalizes.
                            completed = len(parent["_done"][branch])
                            parent["progress"].update(completed=completed, current_security=deepcopy(progress.get("current_security")))
                            if branch == "credit":
                                parent["credit_ratings"]["progress"].update(completed=completed, current_security=deepcopy(progress.get("current_security")))
                        time.sleep(self.poll_seconds)
                        child = manager.get(child["request_id"], parent["_user_id"])
                    with self._lock:
                        self._accept_child(parent, branch, batch, child)
                        parent["progress"].update(completed=len(parent["_done"][branch]), current_security=None)
                    if child["status"] != "completed":
                        raise RuntimeError("child_incomplete")
                    if any(row["security_key"] not in parent["_done"][branch] for row in batch):
                        raise HTTPException(502, "public_research_not_attempted" if branch == "credit" and
                            not int(child.get("counts", {}).get("web_requests", 0)) else "check_incomplete")
            with self._lock:
                parent["credit_ratings"]["status"] = "completed"
                parent["credit_ratings"]["progress"]["current_security"] = None
                empty = not any(parent["_targets"].values())
                parent.update(status="completed", code="nothing_missing" if empty else "research_complete", finished_at=_now())
                parent["progress"]["stage"] = "completed"
        except Exception as error:
            code = error.detail if isinstance(error, HTTPException) and isinstance(error.detail, str) else "check_incomplete"
            with self._lock:
                for row in parent["outcomes"] + parent["credit_ratings"]["outcomes"]:
                    if row["status"] == "pending":
                        row.update(status="not_attempted", code=code, attempted=False)
                parent["credit_ratings"]["status"] = "failed"
                parent["credit_ratings"]["summary"] = self._summary(parent["credit_ratings"]["outcomes"])
                parent["summary"] = self._summary(parent["outcomes"])
                parent.update(status="failed", code=code, failure={"code": code}, finished_at=_now())
                parent["progress"]["stage"] = "failed"

    def router(self):
        router = APIRouter(tags=["portfolio AI research"])
        def user(request):
            owner = getattr(request.state, "auth_user", None)
            if not isinstance(owner, dict):
                raise HTTPException(401, "authentication_required")
            return owner
        @router.post(PREFIX + "/ai", status_code=202)
        def start(request: Request, payload: PortfolioResearchStart | None = None):
            owner = user(request)
            if owner.get("role") not in {"Admin", "Operator"}:
                raise HTTPException(403, "read_only")
            return self.start(owner["id"], dict(request.headers), request.headers.get("Accept-Language", "en")[:24],
                payload.position_scope if payload else "open", security_keys=payload.security_keys if payload else None,
                resume_request_id=payload.resume_request_id if payload else None, ratings_only=payload.ratings_only if payload else False)
        @router.get(PREFIX + "/ai/{request_id}")
        def status(request_id: str, request: Request):
            return self.get(request_id, user(request)["id"])
        @router.get(PREFIX + "/status")
        def outcomes(request: Request):
            owner = user(request)
            with self._lock:
                jobs = [job for job in self._jobs.values() if job["_user_id"] == owner["id"]]
                active = next((job for job in reversed(jobs) if job["status"] in {"queued", "running"}), None)
                latest = jobs[-1] if jobs else None
                return {"active_job": self._public(active) if active else None,
                        "last_job": self._public(latest) if latest else None,
                        "items": deepcopy(latest["outcomes"]) if latest else self.market_jobs._outcome_reader(),
                        "credit_ratings": deepcopy(latest["credit_ratings"]) if latest else None}
        return router
