"""Country automation must preserve the bounded worker and owner boundary."""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.country_rating_schedules import (CountryRatingResearch, CountryRatingSchedules,
                                         JOB_ID, SCHEDULE_ENDPOINT)
from app.sovereign_ratings import country_descriptor


class Deferred:
    callbacks = []

    def __init__(self, target, **_):
        self.callbacks.append(target)

    def start(self):
        pass


class Children:
    def __init__(self):
        self.calls = []
        self.fail_call = None
        self.no_web = False

    def settings(self):
        return {"max_tool_loops": 8, "max_rest_calls": 8, "max_web_calls": 8}

    def start(self, owner, headers, language, scope, *, security_keys):
        self.calls.append((owner, deepcopy(headers), language, scope, security_keys))
        failed = len(self.calls) == self.fail_call
        return {"request_id": "child-" + str(len(self.calls)),
                "status": "failed" if failed else "completed",
                "counts": {"model_requests": 2, "rest_requests": 3, "web_requests": 0 if self.no_web else 1},
                "outcomes": [{"security_key": key, "status": "unavailable" if failed else "updated",
                              "code": "provider_unavailable" if failed else "data_found", "attempted": True,
                              "verified_agencies": ["fitch"]} for key in security_keys]}


def queue():
    Deferred.callbacks = []
    children = Children()
    captured = []

    def inventory(scope):
        captured.append(scope)
        return [country_descriptor(code) for code in (["IL"] if scope == "accounts" else ["IL", "US", "GB", "FR"])]

    research = CountryRatingResearch(children, inventory, worker_factory=Deferred, poll_seconds=0)
    return research, children, captured


def test_all_countries_individually_bounded_no_market_branch_and_account_default():
    research, children, captured = queue()
    job = research.start("owner", {"cookie": "session", "authorization": "token", "irrelevant": "private"}, "he", "all")
    assert job["country_scope"] == "all" and "position_scope" not in job
    Deferred.callbacks.pop(0)()
    result = research.get(job["request_id"], "owner")
    assert result["status"] == "completed" and captured == ["all"]
    assert [item[4] for item in children.calls] == [["COUNTRY:IL"], ["COUNTRY:US"], ["COUNTRY:GB"], ["COUNTRY:FR"]]
    assert all(item[3] == "all" and "irrelevant" not in item[1] for item in children.calls)
    assert result["progress"]["completed"] == result["progress"]["total"] == 4
    assert result["counts"]["max_web_requests"] == 32
    assert result["per_batch_limits"] == {"model": 8, "rest": 8, "web": 8}
    assert result["outcomes"][0]["country_code"] == "IL"
    assert result["summary"]["updated"] == 4
    assert research.status("other") == {"active_job": None, "last_job": None, "items": []}
    second = research.start("owner", {}, "en")
    Deferred.callbacks.pop(0)()
    assert captured[-1] == "accounts" and children.calls[-1][3] == "open"
    assert research.get(second["request_id"], "owner")["summary"]["total_candidates"] == 1


def test_queue_resume_owner_no_overlap_and_explicit_country_selection():
    research, children, _ = queue()
    job = research.start("owner", {}, "en", "all")
    assert research.start("owner", {}, "en", "all")["request_id"] == job["request_id"]
    with pytest.raises(HTTPException) as busy:
        research.start("other", {}, "en", "all")
    assert busy.value.status_code == 409
    children.fail_call = 2
    Deferred.callbacks.pop(0)()
    assert research.get(job["request_id"], "owner")["progress"]["completed"] == 1
    with pytest.raises(HTTPException) as foreign:
        research.get(job["request_id"], "other")
    assert foreign.value.status_code == 404
    research.start("owner", {}, "en", "all", resume_request_id=job["request_id"])
    Deferred.callbacks.pop(0)()
    assert [item[4] for item in children.calls] == [["COUNTRY:IL"], ["COUNTRY:US"], ["COUNTRY:US"], ["COUNTRY:GB"], ["COUNTRY:FR"]]
    single = research.start("owner", {}, "en", "all", country_codes=["GB", "GB"])
    Deferred.callbacks.pop(0)()
    assert research.get(single["request_id"], "owner")["outcomes"][0]["country_code"] == "GB"
    with pytest.raises(HTTPException):
        research.start("owner", {}, "en", country_codes=["ZZ"])


def test_no_public_attempt_is_unchecked_and_scheduled_credentials_revoked():
    research, children, _ = queue()
    children.no_web = True
    revoked = []
    job = research.start("owner", {}, "en", scheduled_credentials=lambda: (
        {"cookie": "short-session", "x-csrf-token": "csrf"}, lambda: revoked.append(True)))
    Deferred.callbacks.pop(0)()
    result = research.get(job["request_id"], "owner")
    assert revoked == [True] and result["status"] == "failed"
    assert result["progress"]["completed"] == 0
    assert result["summary"]["not_attempted"] == 1
    assert not result["outcomes"][0]["attempted"]


def test_explicit_country_outside_scope_is_not_silently_treated_as_success():
    research, children, _ = queue()
    job = research.start("owner", {}, "en", country_codes=["US"])
    Deferred.callbacks.pop(0)()
    result = research.get(job["request_id"], "owner")
    assert result["status"] == "failed" and result["code"] == "invalid_country"
    assert not children.calls


def test_scheduled_session_is_revoked_when_worker_cannot_start():
    class FailedWorker:
        def __init__(self, **_):
            pass

        def start(self):
            raise RuntimeError("cannot start")

    children, revoked = Children(), []
    research = CountryRatingResearch(children, lambda scope: [], worker_factory=FailedWorker)
    with pytest.raises(RuntimeError):
        research.start("owner", {}, "en", scheduled_credentials=lambda: (
            {"cookie": "temporary"}, lambda: revoked.append(True)))
    assert revoked == [True]
    assert research.status("owner")["last_job"]["status"] == "failed"


class Scheduler:
    def __init__(self):
        self.jobs = {}

    def remove_job(self, identifier):
        self.jobs.pop(identifier, None)

    def add_job(self, callback, trigger, **kwargs):
        self.jobs[kwargs["id"]] = SimpleNamespace(callback=callback, trigger=trigger, options=kwargs,
            next_run_time=datetime(2026, 11, 16, 8, tzinfo=timezone.utc))

    def get_job(self, identifier):
        return self.jobs.get(identifier)


class Auth:
    def __init__(self):
        self.owners = []
        self.revoked = []
        self.authorized = True

    def scheduled_session(self, owner):
        if not self.authorized:
            raise PermissionError("changed role")
        self.owners.append(owner)
        return "temporary-session", "csrf"

    def logout(self, token):
        self.revoked.append(token)


def schedules():
    research, children, captured = queue()
    persisted = {}
    scheduler, auth, logs = Scheduler(), Auth(), []

    def write(settings):
        persisted.clear()
        persisted.update(deepcopy(settings))

    service = CountryRatingSchedules(lambda: deepcopy(persisted), write, lambda: scheduler, auth, research,
                                     timezone="Asia/Jerusalem", logger=lambda event, **kwargs: logs.append((event, kwargs)))
    return service, persisted, scheduler, auth, research, logs


OWNER = {"id": "owner", "role": "Operator"}


def test_schedule_opt_in_defaults_validation_owner_hidden_and_reconciliation():
    service, persisted, scheduler, auth, research, logs = schedules()
    assert not service.status()["enabled"] and service.status()["country_scope"] == "accounts"
    service.run()
    assert not auth.owners
    saved = service.update(OWNER, {"enabled": True, "country_scope": "all", "language": "he",
        "schedule_config": {"frequency": "monthly", "month_days": [1, 15], "hour": 9, "minute": 30}})
    assert "owner_id" not in saved and persisted["owner_id"] == "owner"
    assert saved["next_run"] == "2026-11-16T08:00:00+00:00"
    registered = scheduler.jobs[JOB_ID]
    assert str(registered.trigger.timezone) == "Asia/Jerusalem"
    assert registered.options["max_instances"] == 1 and registered.options["coalesce"]
    for payload in ({"enabled": 1}, {"country_scope": "open"}, {"timezone": "Nowhere/Invalid"},
                    {"language": "fr"}, {"owner_id": "other"}, {"schedule_config": {"frequency": "weekly", "weekdays": []}}):
        before = deepcopy(persisted)
        with pytest.raises(HTTPException) as invalid:
            service.update(OWNER, payload)
        assert invalid.value.status_code == 400 and persisted == before
    service.update(OWNER, {"enabled": False})
    assert not scheduler.jobs


def test_schedule_fresh_session_cleanup_busy_and_owner_revocation():
    service, persisted, scheduler, auth, research, logs = schedules()
    service.update(OWNER, {"enabled": True})
    service.run()
    service.run()  # Same active run, no overlapping worker or extra credential.
    assert auth.owners == ["owner"] and len(Deferred.callbacks) == 1
    Deferred.callbacks.pop(0)()
    assert auth.revoked == ["temporary-session"]
    auth.authorized = False
    service.run()
    assert logs[-1][1]["code"] == "owner_not_authorized"
    assert len(Deferred.callbacks) == 0
    latest = research.status("owner")["last_job"]
    assert latest["status"] == "failed" and latest["code"] == "owner_not_authorized"


def test_research_and_schedule_route_permissions_and_private_ownership():
    service, _, _, _, research, _ = schedules()
    app = FastAPI()

    @app.middleware("http")
    async def user(request: Request, call_next):
        role = request.headers.get("X-Test-Role")
        if role:
            request.state.auth_user = {"id": request.headers.get("X-Test-Owner", "owner"), "role": role}
        return await call_next(request)

    app.include_router(research.router())
    app.include_router(service.router())
    with TestClient(app) as client:
        assert client.get(SCHEDULE_ENDPOINT).status_code == 401
        viewer = {"X-Test-Role": "Viewer"}
        operator = {"X-Test-Role": "Operator"}
        assert client.get(SCHEDULE_ENDPOINT, headers=viewer).status_code == 200
        assert client.put(SCHEDULE_ENDPOINT, headers=viewer, json={"enabled": True}).status_code == 403
        endpoint = "/api/countries/credit-ratings"
        assert client.post(endpoint + "/ai", headers=viewer, json={}).status_code == 403
        response = client.post(endpoint + "/ai", headers=operator, json={"country_scope": "all", "country_codes": ["US"]})
        assert response.status_code == 202
        identifier = response.json()["request_id"]
        assert client.get(endpoint + "/ai/" + identifier, headers=viewer).status_code == 200
        assert client.get(endpoint + "/ai/" + identifier, headers={**viewer, "X-Test-Owner": "other"}).status_code == 404
        assert client.post(endpoint + "/ai", headers=operator, json={"language": "fr"}).status_code == 422
