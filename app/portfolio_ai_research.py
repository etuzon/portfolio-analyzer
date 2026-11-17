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
MARKET_TYPES = {"prices", "profile"}
DATA_TYPES = MARKET_TYPES | {"company_ratings", "risk_inputs", "country_ratings"}
BRANCH_FIELDS = {"credit": "credit_ratings", "risk": "risk_inputs", "country": "country_ratings"}
REFRESH_POLICIES = {"missing", "stale", "refresh_existing"}


def _now():
    return datetime.now(timezone.utc).isoformat()


class PortfolioResearchStart(EnrichmentStart):
    resume_request_id: str | None = Field(default=None, min_length=1, max_length=100)
    ratings_only: StrictBool = False
    data_types: list[str] | None = Field(default=None, min_length=1, max_length=5)
    refresh_policy: str = "missing"
    risk_mode: str = "api_then_ai"


class PortfolioAIResearch:
    def __init__(self, market_jobs, credit_jobs, inventory_reader, *, risk_jobs=None, country_jobs=None,
                 country_inventory_reader=None, worker_factory=Thread, poll_seconds=0.25):
        self.market_jobs, self.credit_jobs = market_jobs, credit_jobs
        self.inventory_reader, self._worker_factory = inventory_reader, worker_factory
        self.risk_jobs, self.country_jobs = risk_jobs, country_jobs
        self.country_inventory_reader = country_inventory_reader
        self.poll_seconds = poll_seconds
        self._lock, self._jobs = RLock(), {}

    @staticmethod
    def _public(job):
        return deepcopy({**{key: value for key, value in job.items() if not key.startswith("_")},
                         "security_keys": job.get("_security_keys")})

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
        return MAX_SELECTED if branch == "market" else 1

    @staticmethod
    def _branch(job, branch):
        return job if branch == "market" else job[BRANCH_FIELDS[branch]]

    def _capture_auxiliary(self, job, branch):
        """Capture after prerequisite research, so new identity/country facts count."""
        if branch in job["_captured_branches"]:
            return
        if branch == "risk":
            rows = self.risk_jobs.evidence.candidates(position_scope=job["position_scope"],
                security_keys=job["_security_keys"], refresh_policy=job["refresh_policy"])["items"]
        else:
            rows = self.country_inventory_reader(job["position_scope"], security_keys=job["_security_keys"],
                refresh_policy=job["refresh_policy"]) if self.country_inventory_reader else []
        unique = {row["security_key"]: {name: deepcopy(row.get(name)) for name in
            (*IDENTITY_FIELDS, "country_code", "country_name")} for row in rows}
        job["_targets"][branch] = list(unique.values())
        panel = self._branch(job, branch)
        panel["outcomes"] = [{**row, "status": "pending", "code": "queued", "attempted": False}
                             for row in unique.values()]
        panel["summary"] = self._summary(panel["outcomes"])
        panel["progress"]["total"] = len(unique)
        panel["coverage"] = {"total_candidates": len(unique), "selected": len(unique), "remaining": 0, "truncated": False}
        job["_captured_branches"].add(branch)

    def _recount(self, job, active=None):
        children = [item["job"] for item in job["_children"]]
        if active and active["request_id"] not in {row["request_id"] for row in children}:
            children.append(active)
        limits = job["per_batch_limits"]
        for field in ("model", "rest", "web"):
            job["counts"][field + "_requests"] = sum(int(child.get("counts", {}).get(field + "_requests", 0)) for child in children)
            job["counts"]["max_" + field + "_requests"] = job["_planned_children"] * limits[field]

    def _capture(self, job):
        options = deepcopy(job.get("_candidate_options") or {})
        if job["ratings_only"]:
            options["ratings_only"] = True
        captured = self.inventory_reader(job["position_scope"], **options)
        selected = set(job["_security_keys"] or [])
        for branch, field in (("market", "market_items"), ("credit", "credit_items")):
            unique = {}
            enabled = bool(set(job["data_types"]) & MARKET_TYPES) if branch == "market" else "company_ratings" in job["data_types"]
            for original in (captured.get(field, []) if enabled else []):
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
              resume_request_id=None, scheduled_credentials=None, ratings_only=False,
              data_types=None, refresh_policy="missing", risk_mode="api_then_ai"):
        if type(ratings_only) is not bool:
            raise HTTPException(422, "invalid_research_mode")
        if position_scope not in {"open", "all"}:
            raise HTTPException(422, "invalid_position_scope")
        if (data_types is not None and (not isinstance(data_types, list) or not data_types
                or any(not isinstance(value, str) or value not in DATA_TYPES for value in data_types))
                or refresh_policy not in REFRESH_POLICIES or risk_mode not in {"api_then_ai", "api", "ai"}):
            raise HTTPException(422, "invalid_research_mode")
        options = {"data_types": list(dict.fromkeys(data_types))} if data_types is not None else {}
        if refresh_policy != "missing":
            options["refresh_policy"] = refresh_policy
        effective_types = list(dict.fromkeys(data_types)) if data_types is not None else (["company_ratings"] if ratings_only else
            ["prices", "profile", "company_ratings"] + (["risk_inputs", "country_ratings"] if self.risk_jobs else []))
        if ratings_only and any(value != "company_ratings" for value in effective_types):
            raise HTTPException(422, "invalid_research_mode")
        ratings_only = effective_types == ["company_ratings"]
        if security_keys is not None and (not security_keys or len(security_keys) > MAX_SELECTED
                or any(not isinstance(key, str) or not key.strip() or len(key) > 300 for key in security_keys)):
            raise HTTPException(422, "invalid_enrichment_candidate")
        if security_keys is not None:
            security_keys = list(dict.fromkeys(key.strip().upper() for key in security_keys))
        with self._lock:
            active = next((job for job in self._jobs.values()
                if job["_user_id"] == user_id and job["status"] in {"queued", "running"}), None)
            if active:
                if scheduled_credentials is not None or active["position_scope"] != position_scope or active["ratings_only"] != ratings_only or active.get("_candidate_options", {}) != options or active.get("risk_mode", "api_then_ai") != risk_mode or set(active["_security_keys"] or []) != set(security_keys or []) or (
                        resume_request_id and active["request_id"] != resume_request_id):
                    raise HTTPException(409, "enrichment_busy")
                return self._public(active)
            if sum(job["status"] in {"queued", "running"} for job in self._jobs.values()) >= 2:
                raise HTTPException(409, "enrichment_busy")
            if resume_request_id:
                job = self._owned(resume_request_id, user_id)
                if job["position_scope"] != position_scope or job["ratings_only"] != ratings_only or job.get("_candidate_options", {}) != options or job.get("risk_mode", "api_then_ai") != risk_mode or set(job["_security_keys"] or []) != set(security_keys or []):
                    raise HTTPException(409, "enrichment_scope_changed")
                if job["status"] != "failed":
                    raise HTTPException(409, "nothing_to_resume")
                job.update(status="queued", code="queued", failure=None, finished_at=None)
                for row in job["outcomes"] + [r for field in BRANCH_FIELDS.values() for r in job[field]["outcomes"]]:
                    if row["status"] == "not_attempted":
                        row.update(status="pending", code="queued")
                job["credit_ratings"]["status"] = "queued"
            else:
                settings = self.market_jobs.settings()
                limits = {kind: min(8, max(1, int(settings.get(field, 8)))) for kind, field in
                          (("model", "max_tool_loops"), ("rest", "max_rest_calls"), ("web", "max_web_calls"))}
                job = {"request_id": str(uuid4()), "position_scope": position_scope, "ratings_only": ratings_only,
                    "data_types": effective_types, "refresh_policy": refresh_policy, "risk_mode": risk_mode, "status": "queued", "code": "queued",
                    "created_at": _now(), "finished_at": None, "failure": None, "outcomes": [], "summary": self._summary([]),
                    "counts": {}, "per_batch_limits": limits, "coverage": {"inventory_truncated": False, "listed_candidates": 0},
                    "progress": {"stage": "queued", "completed": 0, "total": 0, "current_security": None},
                    "portfolio_refresh_required": False,
                    "credit_ratings": {"status": "queued", "progress": {"completed": 0, "total": 0, "current_security": None},
                        "summary": self._summary([]), "outcomes": []},
                    "_user_id": user_id, "_security_keys": list(dict.fromkeys(security_keys)) if security_keys else None,
                    "_candidate_options": options,
                    "_targets": {branch: [] for branch in ("market", *BRANCH_FIELDS)},
                    "_done": {branch: set() for branch in ("market", *BRANCH_FIELDS)},
                    "_children": [], "_planned_children": 0, "_captured": False, "_captured_branches": set()}
                for field in ("risk_inputs", "country_ratings"):
                    job[field] = {"status": "queued", "progress": {"completed": 0, "total": 0, "current_security": None},
                        "summary": self._summary([]), "outcomes": []}
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
        panel = self._branch(parent, branch)
        outcomes = panel["outcomes"]
        returned = {row["security_key"]: row for row in child.get("outcomes", []) if row.get("security_key")}
        for row in outcomes:
            if row["security_key"] not in {item["security_key"] for item in batch}:
                continue
            result = returned.get(row["security_key"])
            if branch == "risk" and not result and child["status"] == "completed" and child.get("coverage", {}).get("selected") == 0:
                result = {"status": "updated", "code": "nothing_missing", "attempted": False,
                          "available_fields": [], "missing_fields": [], "sources": []}
            public_attempted = branch not in {"credit", "country"} or int(child.get("counts", {}).get("web_requests", 0)) > 0
            completed = bool(public_attempted and result and (child["status"] == "completed" or result.get("status") in {"updated", "partial"}))
            if completed:
                row.update(deepcopy(result))
                parent["_done"][branch].add(row["security_key"])
            else:
                row.update(status="not_attempted", code="check_incomplete", attempted=bool(public_attempted and result and result.get("attempted")))
        parent["_children"].append({"branch": branch, "job": deepcopy(child)})
        panel["summary"] = self._summary(outcomes)
        if branch != "market":
            panel["progress"]["completed"] = len(parent["_done"][branch])
        parent["portfolio_refresh_required"] |= bool(child.get("portfolio_refresh_required"))
        self._recount(parent)

    def _start_child(self, parent, branch, manager, batch, headers, language):
        keys = [row["security_key"] for row in batch]
        if branch == "risk":
            return manager.start(parent["_user_id"], headers, language[:2], security_keys=keys,
                position_scope=parent["position_scope"], refresh_policy=parent["refresh_policy"], mode=parent["risk_mode"])
        if branch == "country":
            return manager.start(parent["_user_id"], headers, language[:2], "all",
                country_codes=[key.removeprefix("COUNTRY:") for key in keys], refresh_policy=parent["refresh_policy"])
        options = {}
        if branch == "market" and parent.get("_candidate_options"):
            options["candidate_options"] = {"data_types": [value for value in parent["data_types"] if value in MARKET_TYPES],
                                            "refresh_policy": parent["refresh_policy"]}
        return manager.start(parent["_user_id"], headers, language, parent["position_scope"], security_keys=keys, **options)

    def _refresh_risk_outcomes(self, parent):
        if not self.risk_jobs:
            return
        from .risk_input_retrieval import missing_fields
        for row in parent["risk_inputs"]["outcomes"]:
            if row["security_key"] not in parent["_done"]["risk"]:
                continue
            if row.get("code") in {"identity_changed", "risk_input_identity_changed"}:
                continue
            candidate = self.risk_jobs.evidence.inputs.candidate(row["security_key"])
            current = self.risk_jobs.evidence.inputs.read(candidate)
            needed = missing_fields(current, candidate)
            if "country_rating" in row.get("missing_fields", []) and "country_rating" not in needed:
                row["available_fields"] = sorted(set(row.get("available_fields", [])) | {"country_rating"})
            row["missing_fields"] = needed
            row["status"] = "updated" if not needed else "partial" if row.get("available_fields") else "unavailable"
            if row["status"] != "unavailable":
                row["code"] = "data_found" if not needed else "partial_data"
        panel = parent["risk_inputs"]
        panel["summary"] = self._summary(panel["outcomes"])

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
            branches = [("market", self.market_jobs), ("credit", self.credit_jobs)]
            if "risk_inputs" in parent["data_types"]:
                if self.risk_jobs is None:
                    raise HTTPException(503, "risk_research_unavailable")
                branches.append(("risk", self.risk_jobs))
            if set(parent["data_types"]) & {"risk_inputs", "country_ratings"}:
                if self.country_jobs is None:
                    raise HTTPException(503, "country_research_unavailable")
                branches.append(("country", self.country_jobs))
            for branch, manager in branches:
                if branch in {"risk", "country"}:
                    with self._lock:
                        self._capture_auxiliary(parent, branch)
                with self._lock:
                    remaining = sum((len(self._pending(parent, name)) + self._batch_size(name) - 1) // self._batch_size(name)
                                    for name, _ in branches)
                    parent["_planned_children"] = len(parent["_children"]) + remaining
                    parent["coverage"]["listed_candidates"] = sum(map(len, parent["_targets"].values()))
                    self._recount(parent)
                pending = self._pending(parent, branch)
                stage = {"market": "researching_market_data", "credit": "researching_ratings",
                         "risk": "researching_risk_inputs", "country": "researching_country_ratings"}[branch]
                panel = self._branch(parent, branch)
                with self._lock:
                    parent["progress"].update(stage=stage, completed=len(parent["_done"][branch]),
                        total=len(parent["_targets"][branch]), current_security=None)
                    if branch != "market":
                        panel["status"] = "running"
                size = self._batch_size(branch)
                for offset in range(0, len(pending), size):
                    batch = pending[offset:offset + size]
                    child = self._start_child(parent, branch, manager, batch, headers, language)
                    while child["status"] in {"queued", "running"}:
                        with self._lock:
                            self._recount(parent, child)
                            progress = child.get("progress") or {}
                            # Preflight/model phases are not completed checks.
                            # Count a security only after its child finalizes.
                            completed = len(parent["_done"][branch])
                            parent["progress"].update(completed=completed, current_security=deepcopy(progress.get("current_security")))
                            if branch != "market":
                                panel["progress"].update(completed=completed, current_security=deepcopy(progress.get("current_security")))
                        time.sleep(self.poll_seconds)
                        child = manager.get(child["request_id"], parent["_user_id"])
                    with self._lock:
                        self._accept_child(parent, branch, batch, child)
                        parent["progress"].update(completed=len(parent["_done"][branch]), current_security=None)
                    if child["status"] != "completed":
                        raise HTTPException(502, child.get("code") or "check_incomplete")
                    if any(row["security_key"] not in parent["_done"][branch] for row in batch):
                        raise HTTPException(502, "public_research_not_attempted" if branch in {"credit", "country"} and
                            not int(child.get("counts", {}).get("web_requests", 0)) else "check_incomplete")
                with self._lock:
                    if branch != "market":
                        panel["status"] = "completed"
                        panel["progress"]["current_security"] = None
            with self._lock:
                self._refresh_risk_outcomes(parent)
                parent["credit_ratings"]["status"] = "completed"
                parent["credit_ratings"]["progress"]["current_security"] = None
                empty = not any(parent["_targets"].values())
                unresolved = any(row.get("missing_fields") or row.get("status") in {"partial", "unavailable"}
                    for field in BRANCH_FIELDS.values() for row in parent[field]["outcomes"])
                parent.update(status="completed", code="nothing_missing" if empty else "research_partial" if unresolved else "research_complete", finished_at=_now())
                parent["progress"]["stage"] = "completed"
        except Exception as error:
            code = error.detail if isinstance(error, HTTPException) and isinstance(error.detail, str) else "check_incomplete"
            with self._lock:
                for row in parent["outcomes"] + [r for field in BRANCH_FIELDS.values() for r in parent[field]["outcomes"]]:
                    if row["status"] == "pending":
                        row.update(status="not_attempted", code=code, attempted=False)
                for field in BRANCH_FIELDS.values():
                    if parent[field]["status"] != "completed":
                        parent[field]["status"] = "failed"
                    parent[field]["summary"] = self._summary(parent[field]["outcomes"])
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
                resume_request_id=payload.resume_request_id if payload else None, ratings_only=payload.ratings_only if payload else False,
                data_types=payload.data_types if payload else None, refresh_policy=payload.refresh_policy if payload else "missing",
                risk_mode=payload.risk_mode if payload else "api_then_ai")
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
