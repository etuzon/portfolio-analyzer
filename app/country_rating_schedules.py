"""Owner-bound sovereign research queue and opt-in wall-clock automation.

The trusted queue captures country identities, never financial inputs. Every
country is researched by the existing bounded, authenticated REST-only worker.
"""
from __future__ import annotations

from copy import deepcopy
from threading import RLock, Thread
from zoneinfo import ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .auth import SESSION_COOKIE_NAME
from .portfolio_ai_research import PortfolioAIResearch
from .scheduling import normalize_schedule, schedule_trigger
from .security_enrichment import MAX_SELECTED
from .sovereign_ratings import country_descriptor, normalize_country

PREFIX = "/api/countries/credit-ratings"
SCHEDULE_ENDPOINT = "/api/settings/country-rating-schedule"
JOB_ID = "country-sovereign-rating-research"
SCOPES = {"accounts": "open", "all": "all"}


def _scope(value):
    if not isinstance(value, str) or value not in SCOPES:
        raise HTTPException(422, "invalid_country_scope")
    return value


def _user(request):
    owner = getattr(request.state, "auth_user", None)
    if not isinstance(owner, dict):
        raise HTTPException(401, "authentication_required")
    return owner


def _writer(owner):
    if not isinstance(owner, dict):
        raise HTTPException(401, "authentication_required")
    if owner.get("role") not in {"Admin", "Operator"}:
        raise HTTPException(403, "read_only")
    return owner


class CountryResearchStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    country_scope: str = "accounts"
    country_codes: list[str] | None = Field(default=None, min_length=1, max_length=MAX_SELECTED)
    resume_request_id: str | None = Field(default=None, min_length=1, max_length=100)
    language: str | None = None


class _NoMarketJobs:
    def __init__(self, settings):
        self.settings = settings


class CountryRatingResearch(PortfolioAIResearch):
    """Reuse the tested queue, with one bounded sovereign-only child per country."""

    def __init__(self, child_jobs, inventory_reader, assistant_settings=None, *,
                 worker_factory=Thread, poll_seconds=0.25):
        self.country_inventory_reader = inventory_reader
        settings = assistant_settings or child_jobs.settings

        def inventory(position_scope, **_):
            captured = inventory_reader("accounts" if position_scope == "open" else "all")
            items = captured.get("items", []) if isinstance(captured, dict) else captured
            return {"market_items": [], "credit_items": items}

        super().__init__(_NoMarketJobs(settings), child_jobs, inventory,
                         worker_factory=worker_factory, poll_seconds=poll_seconds)

    def _capture(self, job):
        super()._capture(job)
        captured = {row["security_key"] for row in job["_targets"]["credit"]}
        if set(job["_security_keys"] or []) - captured:
            # Explicit country requests must not silently succeed with an empty
            # selection when the caller chose an incompatible account scope.
            raise HTTPException(422, "invalid_country")

    @staticmethod
    def _public(job):
        result = PortfolioAIResearch._public(job)
        result["country_codes"] = [str(key).removeprefix("COUNTRY:") for key in job["_security_keys"]] if job.get("_security_keys") else None
        result["country_scope"] = "accounts" if result.pop("position_scope") == "open" else "all"
        result.pop("ratings_only", None)
        credit = result["credit_ratings"]
        for row in credit["outcomes"]:
            descriptor = country_descriptor(str(row.get("security_key", "")).removeprefix("COUNTRY:"))
            if descriptor:
                row.update(country_code=descriptor["country_code"], country_name=descriptor["country_name"])
        result["outcomes"] = deepcopy(credit["outcomes"])
        result["summary"] = deepcopy(credit["summary"])
        result["progress"].update(deepcopy(credit["progress"]))
        return result

    def start(self, user_id, headers, language, country_scope="accounts", *, country_codes=None,
              resume_request_id=None, scheduled_credentials=None):
        country_scope = _scope(country_scope)
        keys = None
        if country_codes is not None:
            if not isinstance(country_codes, list) or not country_codes or len(country_codes) > MAX_SELECTED:
                raise HTTPException(422, "invalid_country")
            codes = [normalize_country(value) for value in country_codes]
            if any(code is None for code in codes):
                raise HTTPException(422, "invalid_country")
            keys = ["COUNTRY:" + code for code in dict.fromkeys(codes)]
        with self._lock:
            # The queue may span the full country catalog. A second owner or
            # changed scope must not overlap an already running catalog sweep.
            if any(job["status"] in {"queued", "running"} and job["_user_id"] != user_id
                   for job in self._jobs.values()):
                raise HTTPException(409, "enrichment_busy")
            return super().start(user_id, headers, language, SCOPES[country_scope], security_keys=keys,
                resume_request_id=resume_request_id, scheduled_credentials=scheduled_credentials, ratings_only=True)

    def get(self, identifier, owner):
        with self._lock:
            return self._public(self._owned(identifier, owner))

    def status(self, owner):
        with self._lock:
            jobs = [job for job in self._jobs.values() if job["_user_id"] == owner]
            active = next((job for job in reversed(jobs) if job["status"] in {"queued", "running"}), None)
            latest = jobs[-1] if jobs else None
            return {"active_job": self._public(active) if active else None,
                    "last_job": self._public(latest) if latest else None,
                    "items": self._public(latest)["outcomes"] if latest else []}

    def router(self):
        router = APIRouter(tags=["sovereign rating research"])

        @router.post(PREFIX + "/ai", status_code=202)
        def start(request: Request, payload: CountryResearchStart | None = None):
            owner = _writer(_user(request))
            payload = payload or CountryResearchStart()
            language = payload.language or request.headers.get("Accept-Language", "en")[:24]
            if payload.language is not None and payload.language not in {"en", "he"}:
                raise HTTPException(422, "invalid_language")
            return self.start(owner["id"], dict(request.headers), language, payload.country_scope,
                              country_codes=payload.country_codes, resume_request_id=payload.resume_request_id)

        @router.get(PREFIX + "/ai/{request_id}")
        def get(request_id: str, request: Request):
            return self.get(request_id, _user(request)["id"])

        @router.get(PREFIX + "/status")
        def status(request: Request):
            return self.status(_user(request)["id"])

        return router


class CountryRatingSchedules:
    def __init__(self, settings_reader, settings_writer, scheduler_getter, auth_store, research, *,
                 timezone="UTC", logger=None):
        self.settings_reader, self.settings_writer = settings_reader, settings_writer
        self.scheduler_getter, self.auth_store, self.research = scheduler_getter, auth_store, research
        self.timezone, self.logger, self._lock = timezone, logger, RLock()

    def settings(self, raw=None):
        raw = self.settings_reader() if raw is None else raw
        raw = raw if isinstance(raw, dict) else {}
        return {"enabled": raw.get("enabled") is True,
                "country_scope": raw.get("country_scope", "accounts"),
                "schedule_config": deepcopy(raw.get("schedule_config") or {"frequency": "weekly", "weekdays": [0], "hour": 8, "minute": 0}),
                "timezone": raw.get("timezone") or self.timezone,
                "language": raw.get("language", "en"), "owner_id": raw.get("owner_id", "")}

    def status(self):
        result = self.settings()
        result.pop("owner_id", None)
        scheduler = self.scheduler_getter()
        job = scheduler.get_job(JOB_ID) if scheduler else None
        result["next_run"] = job.next_run_time.isoformat() if job and job.next_run_time else None
        return result

    @staticmethod
    def _validate(settings):
        if type(settings["enabled"]) is not bool or settings["language"] not in {"en", "he"}:
            raise ValueError("Invalid schedule")
        if settings["country_scope"] not in SCOPES or not isinstance(settings["timezone"], str):
            raise ValueError("Invalid schedule")
        settings["schedule_config"] = normalize_schedule(settings["schedule_config"])
        return schedule_trigger(settings["schedule_config"], settings["timezone"])

    def update(self, owner, payload):
        owner = _writer(owner)
        if not isinstance(payload, dict) or set(payload) - {"enabled", "country_scope", "schedule_config", "timezone", "language"}:
            raise HTTPException(400, "invalid_schedule")
        with self._lock:
            settings = self.settings()
            settings.update(deepcopy(payload))
            try:
                self._validate(settings)
            except (ValueError, TypeError, KeyError, ZoneInfoNotFoundError) as exc:
                raise HTTPException(400, "invalid_schedule") from exc
            settings["owner_id"] = owner["id"]
            self.settings_writer(settings)
            self.configure()
            return self.status()

    def _skipped(self, code):
        if self.logger:
            self.logger("country_rating_schedule_skipped", code=code)

    def configure(self):
        with self._lock:
            scheduler = self.scheduler_getter()
            if scheduler is None:
                return
            try:
                scheduler.remove_job(JOB_ID)
            except Exception:
                pass
            settings = self.settings()
            if settings["enabled"]:
                try:
                    trigger = self._validate(settings)
                except (ValueError, TypeError, KeyError, ZoneInfoNotFoundError):
                    self._skipped("invalid_schedule")
                    return
                scheduler.add_job(self.run, trigger, id=JOB_ID, replace_existing=True,
                                  max_instances=1, coalesce=True, misfire_grace_time=60)

    def run(self):
        settings = self.settings()
        if not settings["enabled"]:
            return

        def credentials():
            token, csrf = self.auth_store.scheduled_session(settings["owner_id"])
            return ({"cookie": f"{SESSION_COOKIE_NAME}={token}", "x-csrf-token": csrf},
                    lambda: self.auth_store.logout(token))

        try:
            self._validate(settings)
            self.research.start(settings["owner_id"], {}, settings["language"], settings["country_scope"],
                                scheduled_credentials=credentials)
        except PermissionError:
            self._skipped("owner_not_authorized")
        except HTTPException as exc:
            self._skipped("busy" if exc.status_code == 409 else "request_failed")
        except (ValueError, TypeError, KeyError, ZoneInfoNotFoundError):
            self._skipped("invalid_schedule")

    def router(self):
        router = APIRouter(tags=["sovereign rating schedule"])

        @router.get(SCHEDULE_ENDPOINT)
        def get(request: Request):
            _user(request)
            return self.status()

        @router.put(SCHEDULE_ENDPOINT)
        def update(request: Request, payload: dict):
            return self.update(_user(request), payload)

        return router
