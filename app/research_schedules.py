"""Named, owner-bound schedules for existing bounded public research workers.

Rules store choices and sanitized receipts only. Model execution remains in the
existing REST-only workers; this coordinator never supplies a storage tool.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock, Thread
import time
from uuid import uuid4
from zoneinfo import ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException, Request

from .auth import SESSION_COOKIE_NAME
from .scheduling import normalize_schedule, schedule_trigger
from .sovereign_ratings import normalize_country

ENDPOINT = "/api/settings/research-schedules"
PREFERENCE = "research_schedules_v1"
JOB_PREFIX = "research-schedule:"
DATA_TYPES = {"prices", "profile", "company_ratings", "risk_inputs", "country_ratings"}
REFRESH_POLICIES = {"missing", "stale", "refresh_existing"}
MAX_RULES = 32
LEGACY_JOB_IDS = ("ai-missing-data-enrichment", "ai-missing-data-enrichment:open",
                  "ai-missing-data-enrichment:all", "risk-input-retrieval", "country-sovereign-rating-research")
RULE_FIELDS = {"name", "enabled", "data_types", "position_scope", "security_keys", "country_scope", "country_codes",
               "mode", "refresh_policy", "schedule_config", "timezone", "language"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _actor(request):
    actor = getattr(request.state, "auth_user", None)
    if not isinstance(actor, dict):
        raise HTTPException(401, "authentication_required")
    return actor


def _writer(actor):
    if not isinstance(actor, dict) or actor.get("role") not in {"Admin", "Operator"}:
        raise HTTPException(403, "read_only")


class ResearchSchedules:
    def __init__(self, reader, writer, scheduler_getter, auth_getter, portfolio, risk, countries, *,
                 legacy_reader=None, legacy_writer=None, inventory_reader=None, timezone="UTC",
                 worker_factory=Thread, poll_seconds=.25, wait_timeout_seconds=21600):
        self.reader, self.writer, self.scheduler_getter = reader, writer, scheduler_getter
        self.auth_getter, self.portfolio, self.risk, self.countries = auth_getter, portfolio, risk, countries
        self.legacy_reader, self.legacy_writer, self.inventory_reader = legacy_reader, legacy_writer, inventory_reader
        self.timezone, self.worker_factory, self.poll_seconds = timezone, worker_factory, poll_seconds
        self.wait_timeout_seconds = wait_timeout_seconds
        self._lock, self._active, self._configured_ids = RLock(), {}, set()

    def is_migrated(self):
        raw = self.reader()
        return isinstance(raw, dict) and raw.get("schema_version") == 1 and raw.get("migrated") is True

    @staticmethod
    def _legacy_rows(sources):
        runtime = sources.get("runtime") or {}
        collection = runtime.get("ai_enrichment_schedules")
        if isinstance(collection, dict):
            ai = [(scope, raw) for scope, raw in collection.items() if scope in {"open", "all"} and isinstance(raw, dict)]
        else:
            old = runtime.get("ai_enrichment_schedule")
            ai = [(old.get("position_scope", "open"), old)] if isinstance(old, dict) else []
        for scope, raw in ai:
            if scope in {"open", "all"}:
                yield "ai:" + scope, raw, {"name": "Open positions" if scope == "open" else "Open and closed positions",
                    "data_types": ["prices", "profile", "company_ratings"], "position_scope": scope, "refresh_policy": "stale"}
        risk = sources.get("risk_inputs")
        if isinstance(risk, dict) and risk:
            yield "risk_inputs", risk, {"name": "Risk inputs", "data_types": ["risk_inputs"],
                "position_scope": "selected" if risk.get("security_keys") else "open", "refresh_policy": "stale"}
        country = sources.get("country_ratings")
        if isinstance(country, dict) and country:
            yield "country_ratings", country, {"name": "Country credit ratings", "data_types": ["country_ratings"],
                "country_scope": country.get("country_scope", "accounts"), "refresh_policy": "refresh_existing"}

    def _defaults(self):
        return {"name": "", "enabled": False, "data_types": ["risk_inputs"], "position_scope": "open",
            "security_keys": None, "country_scope": "accounts", "country_codes": None, "mode": "api_then_ai",
            "refresh_policy": "stale", "schedule_config": {"frequency": "weekly", "weekdays": [0], "hour": 8, "minute": 0},
            "timezone": self.timezone, "language": "en"}

    def _migrate_row(self, reference, raw, defaults):
        row = {**self._defaults(), **{key: deepcopy(value) for key, value in raw.items() if key in RULE_FIELDS}, **defaults,
            "id": "legacy-" + reference.replace(":", "-"), "owner_id": raw.get("owner_id", ""),
            "revision": 1, "created_at": _now(), "updated_at": _now(), "_legacy_ref": reference,
            "batch_cursor": raw.get("batch_cursor") or 0}
        # Preserve saved recurrence and flags exactly; defaults supply only the
        # target/scope choices absent from the former singleton contracts.
        for field in ("enabled", "schedule_config", "timezone", "language", "mode", "security_keys"):
            if field in raw:
                row[field] = deepcopy(raw[field])
        for field in ("last_run_at", "last_run_code", "last_request_id"):
            if raw.get(field) is not None:
                row[field] = raw[field]
        try:
            row["batch_cursor"] = max(0, int(row["batch_cursor"]))
            self._validate(row, verify_selection=False)
        except (ValueError, TypeError, KeyError, AttributeError, ZoneInfoNotFoundError):
            row.update(enabled=False, migration_code="invalid_schedule")
        return row

    def _load(self):
        raw = self.reader()
        if isinstance(raw, dict) and raw.get("schema_version") == 1 and raw.get("migrated") is True:
            return deepcopy(raw)
        sources = self.legacy_reader() if self.legacy_reader else {}
        raw = {"schema_version": 1, "migrated": True,
            "items": [self._migrate_row(*row) for row in self._legacy_rows(sources or {})]}
        self.writer(raw)
        return deepcopy(raw)

    def _validate(self, row, *, verify_selection=True):
        if (not isinstance(row["name"], str) or not 1 <= len(row["name"].strip()) <= 80
                or type(row["enabled"]) is not bool or row["language"] not in {"en", "he"}
                or not isinstance(row["timezone"], str) or not 1 <= len(row["timezone"]) <= 100
                or not isinstance(row["data_types"], list) or not 1 <= len(row["data_types"]) <= len(DATA_TYPES)
                or any(not isinstance(value, str) or value not in DATA_TYPES for value in row["data_types"])
                or row["position_scope"] not in {"open", "all", "selected"}
                or row["country_scope"] not in {"accounts", "all", "selected"}
                or row["mode"] not in {"api_then_ai", "api", "ai"}
                or row["refresh_policy"] not in REFRESH_POLICIES):
            raise ValueError("invalid_schedule")
        row["name"] = row["name"].strip()
        row["data_types"] = list(dict.fromkeys(row["data_types"]))
        for field, scope in (("security_keys", "position_scope"), ("country_codes", "country_scope")):
            values = row[field]
            if row[scope] == "selected":
                if not isinstance(values, list) or not 1 <= len(values) <= 3 or any(not isinstance(v, str) or not 1 <= len(v.strip()) <= 300 for v in values):
                    raise ValueError("invalid_schedule")
                row[field] = list(dict.fromkeys(value.strip().upper() for value in values))
            else:
                row[field] = None
        if row["country_codes"]:
            normalized = [normalize_country(value) for value in row["country_codes"]]
            if any(value is None for value in normalized):
                raise ValueError("invalid_schedule")
            row["country_codes"] = list(dict.fromkeys(normalized))
        if verify_selection and row["security_keys"] and self.inventory_reader:
            registered = {item["security_key"] for item in self.inventory_reader()}
            if set(row["security_keys"]) - registered:
                raise ValueError("invalid_schedule")
        row["schedule_config"] = normalize_schedule(row["schedule_config"])
        return schedule_trigger(row["schedule_config"], row["timezone"])

    @staticmethod
    def _owned(row, actor):
        # Preserve the project's shared Admin/Operator schedule editing model:
        # saving takes ownership; scheduled execution uses that saving user.
        _writer(actor)

    def _public(self, row, actor=None):
        result = {key: deepcopy(value) for key, value in row.items() if not key.startswith("_") and key != "owner_id"}
        scheduler = self.scheduler_getter()
        job = scheduler.get_job(JOB_PREFIX + row["id"]) if scheduler and hasattr(scheduler, "get_job") else None
        result["next_run"] = job.next_run_time.isoformat() if job and job.next_run_time else None
        result["active"] = row["id"] in self._active
        result["editable"] = bool(actor and actor.get("role") in {"Admin", "Operator"})
        return result

    def status(self, actor=None):
        with self._lock:
            raw = self._load()
            return {"items": [self._public(row, actor) for row in raw["items"]],
                "limits": {"rules": MAX_RULES, "selected_securities": 3, "selected_countries": 3,
                    "model_per_child": 8, "rest_per_child": 8, "web_per_child": 8},
                "busy_policy": "skip_until_next_run", "retry_policy": "manual_or_next_run"}

    def save(self, actor, payload, identifier=None):
        _writer(actor)
        if not isinstance(payload, dict) or set(payload) - RULE_FIELDS - {"expected_revision"}:
            raise HTTPException(400, "invalid_schedule")
        with self._lock:
            raw = self._load()
            row = next((row for row in raw["items"] if row["id"] == identifier), None) if identifier else None
            if identifier and not row:
                raise HTTPException(404, "schedule_not_found")
            if row:
                self._owned(row, actor)
                expected = payload.get("expected_revision")
                if expected is not None and (type(expected) is not int or expected != row.get("revision")):
                    raise HTTPException(409, "schedule_changed")
            elif len(raw["items"]) >= MAX_RULES:
                raise HTTPException(409, "schedule_limit")
            updated = {**(deepcopy(row) if row else self._defaults()),
                **{key: deepcopy(value) for key, value in payload.items() if key in RULE_FIELDS}}
            try:
                self._validate(updated)
            except (ValueError, TypeError, KeyError, AttributeError, ZoneInfoNotFoundError):
                raise HTTPException(400, "invalid_schedule") from None
            updated.update(id=identifier or str(uuid4()), owner_id=actor["id"], revision=(row.get("revision", 0) if row else 0) + 1,
                created_at=row["created_at"] if row else _now(), updated_at=_now())
            if row:
                # Changing selection/freshness starts that rule's own rotation
                # at zero; cadence/name changes retain its cursor.
                if any(row.get(field) != updated.get(field) for field in ("position_scope", "security_keys", "refresh_policy")):
                    updated["batch_cursor"] = 0
                if identifier in self._active:
                    updated["last_run_code"] = "schedule_changed"
                raw["items"][raw["items"].index(row)] = updated
            else:
                updated["batch_cursor"] = 0
                raw["items"].append(updated)
            self.writer(raw)
            self._mirror_legacy(updated)
            self.configure()
            return self._public(updated, actor)

    def delete(self, actor, identifier):
        _writer(actor)
        with self._lock:
            raw = self._load()
            row = next((row for row in raw["items"] if row["id"] == identifier), None)
            if not row:
                raise HTTPException(404, "schedule_not_found")
            self._owned(row, actor)
            raw["items"].remove(row)
            self.writer(raw)
            self._mirror_legacy({**row, "enabled": False})
            self.configure()
            return {"status": "deleted", "id": identifier}

    def _mirror_legacy(self, row):
        if row.get("_legacy_ref") and self.legacy_writer:
            self.legacy_writer(row["_legacy_ref"], deepcopy(row))

    def _merge_legacy(self, reference, incoming, previous):
        """Old editors change their represented controls, not named choices.

        Their projections cannot represent all security scopes or selected
        countries. An unchanged projection must retain that richer selection.
        """
        row = deepcopy(previous)
        for field in ("enabled", "schedule_config", "timezone", "language", "owner_id"):
            if field in incoming:
                row[field] = deepcopy(incoming[field])
        if reference == "risk_inputs":
            if "mode" in incoming:
                row["mode"] = incoming["mode"]
            if "security_keys" in incoming:
                keys = incoming["security_keys"]
                keys = list(dict.fromkeys(value.strip().upper() for value in keys)) if keys is not None else None
                if set(keys or []) != set(previous.get("security_keys") or []):
                    row.update(security_keys=keys, position_scope="selected" if keys else "open", batch_cursor=0)
        elif reference == "country_ratings" and "country_scope" in incoming:
            projected_scope = "all" if previous["country_scope"] == "selected" else previous["country_scope"]
            if incoming["country_scope"] != projected_scope:
                row.update(country_scope=incoming["country_scope"], country_codes=None)
        row.update(revision=previous.get("revision", 0) + 1, updated_at=_now())
        if row["id"] in self._active:
            row["last_run_code"] = "schedule_changed"
        self._validate(row, verify_selection=False)
        return row

    def import_legacy(self, reference):
        """An explicit old-client save edits its mapped rule, never a second job."""
        with self._lock:
            raw = self._load()
            sources = self.legacy_reader() if self.legacy_reader else {}
            source = next((item for item in self._legacy_rows(sources or {}) if item[0] == reference), None)
            if source:
                previous = next((row for row in raw["items"] if row.get("_legacy_ref") == reference), None)
                if previous:
                    row = self._merge_legacy(reference, source[1], previous)
                    raw["items"][raw["items"].index(previous)] = row
                else:
                    row = self._migrate_row(*source)
                    raw["items"].append(row)
                self.writer(raw)
            self.configure()

    def legacy_status(self, reference):
        with self._lock:
            row = next((item for item in self._load()["items"] if item.get("_legacy_ref") == reference), None)
            return self._public(row) if row else None

    def configure(self):
        with self._lock:
            raw = self._load()
            interrupted = False
            for row in raw["items"]:
                if row.get("last_run_code") in {"queued", "running"} and row["id"] not in self._active:
                    row.update(last_run_code="interrupted", last_finished_at=_now())
                    interrupted = True
            if interrupted:
                self.writer(raw)
            scheduler = self.scheduler_getter()
            if not scheduler:
                return
            identifiers = set(LEGACY_JOB_IDS) | self._configured_ids
            if hasattr(scheduler, "get_jobs"):
                identifiers |= {job.id for job in scheduler.get_jobs() if job.id.startswith(JOB_PREFIX)}
            for identifier in identifiers:
                try:
                    scheduler.remove_job(identifier)
                except Exception:
                    pass
            self._configured_ids = set()
            for row in raw["items"]:
                if not row.get("enabled"):
                    continue
                try:
                    trigger = self._validate(deepcopy(row), verify_selection=False)
                except (ValueError, TypeError, KeyError, AttributeError, ZoneInfoNotFoundError):
                    continue
                identifier = JOB_PREFIX + row["id"]
                scheduler.add_job(self.run, trigger, args=[row["id"]], id=identifier, replace_existing=True,
                    max_instances=1, coalesce=True, misfire_grace_time=60)
                self._configured_ids.add(identifier)

    def _receipt(self, identifier, changes, *, owner=None, revision=None, run_id=None):
        with self._lock:
            raw = self._load()
            row = next((row for row in raw["items"] if row["id"] == identifier), None)
            if (row and (owner is None or row.get("owner_id") == owner)
                    and (revision is None or row.get("revision") == revision)
                    and (run_id is None or row.get("last_request_id") == run_id)):
                row.update(deepcopy(changes))
                self.writer(raw)
                return row
        return None

    def _wait(self, manager, child, owner):
        deadline = time.monotonic() + self.wait_timeout_seconds
        while child.get("status") in {"queued", "running"}:
            if time.monotonic() > deadline:
                raise HTTPException(504, "request_limit")
            time.sleep(self.poll_seconds)
            child = manager.get(child["request_id"], owner)
        return child

    def run(self, identifier, actor=None, *, manual=False):
        if manual:
            _writer(actor)
        with self._lock:
            row = next((row for row in self._load()["items"] if row["id"] == identifier), None)
            if not row:
                raise HTTPException(404, "schedule_not_found")
            if not manual and not row.get("enabled"):
                return self._public(row, actor)
            if self._active:
                changes = {"last_skipped_at": _now(), "last_skip_code": "enrichment_busy"}
                if identifier not in self._active:
                    changes.update(last_run_at=_now(), last_run_code="enrichment_busy")
                self._receipt(identifier, changes)
                if manual:
                    raise HTTPException(409, "enrichment_busy")
                return self._public({**row, **changes}, actor)
            run_id = str(uuid4())
            self._active[identifier] = run_id
            row = self._receipt(identifier, {"last_run_at": _now(), "last_run_code": "queued", "last_request_id": run_id,
                "last_jobs": [], "last_finished_at": None})
        def work():
            self._run_rule(deepcopy(row))
        try:
            self.worker_factory(target=work, daemon=True, name="named-research-schedule").start()
        except Exception:
            with self._lock:
                self._active.pop(identifier, None)
            self._receipt(identifier, {"last_run_code": "job_failed", "last_finished_at": _now()})
            raise HTTPException(503, "job_failed") from None
        return self._public(row, actor)

    def _run_rule(self, settings):
        identifier, owner = settings["id"], settings.get("owner_id", "")
        fence = {"owner": owner, "revision": settings.get("revision"), "run_id": settings.get("last_request_id")}
        cleanup, children, code = None, [], "completed"
        try:
            self._validate(settings, verify_selection=False)
            auth = self.auth_getter()
            token, csrf = auth.scheduled_session(owner)
            cleanup = lambda: auth.logout(token)
            headers = {"cookie": f"{SESSION_COOKIE_NAME}={token}", "x-csrf-token": csrf}
            credentials = lambda: (headers, lambda: None)
            self._receipt(identifier, {"last_run_code": "running"}, **fence)
            targets = set(settings["data_types"])
            branches = []
            portfolio_targets = [target for target in settings["data_types"] if target in {"prices", "profile", "company_ratings"}]
            if portfolio_targets:
                branches.append(("portfolio", self.portfolio, lambda: self.portfolio.start(owner, {}, settings["language"],
                    "all" if settings["position_scope"] == "selected" else settings["position_scope"],
                    security_keys=settings["security_keys"], data_types=portfolio_targets,
                    refresh_policy=settings["refresh_policy"], scheduled_credentials=credentials)))
            if "risk_inputs" in targets:
                branches.append(("risk_inputs", self.risk, lambda: self.risk.start(owner, {}, settings["language"],
                    mode=settings["mode"], security_keys=settings["security_keys"],
                    position_scope="all" if settings["position_scope"] == "selected" else settings["position_scope"],
                    refresh_policy=settings["refresh_policy"], batch_offset=int(settings.get("batch_cursor") or 0),
                    scheduled_credentials=credentials)))
            if "country_ratings" in targets:
                branches.append(("country_ratings", self.countries, lambda: self.countries.start(owner, {}, settings["language"],
                    "all" if settings["country_scope"] == "selected" else settings["country_scope"],
                    country_codes=settings["country_codes"], refresh_policy=settings["refresh_policy"], scheduled_credentials=credentials)))
            for target, manager, start in branches:
                with self._lock:
                    current = next((row for row in self._load()["items"] if row["id"] == identifier), None)
                if not current or current.get("owner_id") != owner or current.get("revision") != settings.get("revision"):
                    raise HTTPException(409, "schedule_changed")
                child = self._wait(manager, start(), owner)
                receipt = {key: deepcopy(child.get(key)) for key in ("request_id", "status", "code", "counts", "coverage", "summary")}
                receipt["target"] = target
                children.append(receipt)
                changes = {"last_jobs": children}
                if target == "risk_inputs" and settings["security_keys"] is None:
                    changes["batch_cursor"] = child.get("coverage", {}).get("next_batch_offset", settings.get("batch_cursor", 0))
                self._receipt(identifier, changes, **fence)
                if child.get("status") != "completed":
                    code = child.get("code") or "job_failed"
                    break
        except PermissionError:
            code = "owner_not_authorized"
        except HTTPException as error:
            code = error.detail if isinstance(error.detail, str) else "job_failed"
        except (ValueError, TypeError, KeyError, AttributeError, ZoneInfoNotFoundError):
            code = "invalid_schedule"
        except Exception:
            code = "job_failed"
        finally:
            if cleanup:
                try:
                    cleanup()
                except Exception:
                    if code == "completed":
                        code = "job_failed"
            with self._lock:
                self._active.pop(identifier, None)
            self._receipt(identifier, {"last_run_code": code, "last_finished_at": _now(), "last_jobs": children}, **fence)

    def router(self):
        router = APIRouter(tags=["named research schedules"])
        @router.get(ENDPOINT)
        def status(request: Request):
            return self.status(_actor(request))
        @router.get(ENDPOINT + "/inventory")
        def inventory(request: Request):
            _actor(request)
            allowed = {"security_key", "symbol", "stock_market", "currency", "name", "has_open_position"}
            return {"items": [{key: value for key, value in row.items() if key in allowed}
                for row in (self.inventory_reader() if self.inventory_reader else [])]}
        @router.post(ENDPOINT, status_code=201)
        def create(request: Request, payload: dict):
            return self.save(_actor(request), payload)
        @router.put(ENDPOINT + "/{identifier}")
        def update(identifier: str, request: Request, payload: dict):
            return self.save(_actor(request), payload, identifier)
        @router.delete(ENDPOINT + "/{identifier}")
        def delete(identifier: str, request: Request):
            return self.delete(_actor(request), identifier)
        @router.post(ENDPOINT + "/{identifier}/run", status_code=202)
        def run(identifier: str, request: Request):
            return self.run(identifier, _actor(request), manual=True)
        return router
