"""Actual auth/REST persistence and legacy compatibility for named schedules."""
from copy import deepcopy
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app import main
from app.research_schedules import ENDPOINT, JOB_PREFIX
from test_scheduling import schedule_environment
from test_portfolio_ai_research_integration import login


def rule(name="Weekly risk", **changes):
    return {"name": name, "data_types": ["risk_inputs"], "enabled": True,
        "schedule_config": {"frequency": "weekly", "weekdays": [0], "hour": 8, "minute": 0},
        "position_scope": "open", "mode": "api_then_ai", "refresh_policy": "stale", **changes}


def test_named_schedule_auth_validation_independent_crud_and_reload(schedule_environment):
    client, auth, session, _ = schedule_environment
    headers = {"X-CSRF-Token": session["csrf_token"]}
    assert TestClient(main.app).get(ENDPOINT).status_code == 401
    assert client.post(ENDPOINT, json=rule()).status_code == 403
    first = client.post(ENDPOINT, headers=headers, json=rule())
    second = client.post(ENDPOINT, headers=headers, json=rule("Monthly ratings", data_types=["company_ratings"],
        schedule_config={"frequency": "monthly", "month_days": [15], "hour": 17, "minute": 20}, position_scope="all"))
    assert first.status_code == second.status_code == 201
    a, b = first.json(), second.json()
    assert a["id"] != b["id"] and "owner_id" not in str([a,b])
    changed = client.put(ENDPOINT+"/"+a["id"], headers=headers, json={"name":"Renamed risk", "expected_revision":a["revision"]})
    assert changed.status_code == 200 and changed.json()["id"] == a["id"]
    assert changed.json()["revision"] == a["revision"]+1
    assert client.put(ENDPOINT+"/"+a["id"], headers=headers, json={"name":"Old draft", "expected_revision":a["revision"]}).status_code == 409
    for payload in ({"data_types":["guess"]},{"position_scope":"selected","security_keys":["1","2","3","4"]},
                    {"country_scope":"selected","country_codes":["??"]},{"schedule_config":{"frequency":"weekly","weekdays":[]}}):
        assert client.put(ENDPOINT+"/"+a["id"], headers=headers, json=payload).status_code == 400
    rows = client.get(ENDPOINT).json()["items"]
    assert next(row for row in rows if row["id"]==b["id"]) == b
    assert client.delete(ENDPOINT+"/"+a["id"], headers=headers).status_code == 200
    assert [row["id"] for row in client.get(ENDPOINT).json()["items"]] == [b["id"]]
    assert "cookie" not in str(main.local_store.get_preference("research_schedules_v1"))
    viewer, viewer_headers = login(auth, role="Viewer", suffix="named-viewer")
    assert viewer.get(ENDPOINT).status_code == 200
    for method, path, payload in (("post",ENDPOINT,rule()),("put",ENDPOINT+"/"+b["id"],{"enabled":False}),
                                 ("delete",ENDPOINT+"/"+b["id"],None),("post",ENDPOINT+"/"+b["id"]+"/run",{})):
        assert getattr(viewer,method)(path,headers=viewer_headers,**({"json":payload} if payload is not None else {})).status_code == 403


def test_old_client_save_updates_one_migrated_rule_without_legacy_job(schedule_environment, monkeypatch):
    client, _, session, _ = schedule_environment
    headers={"X-CSRF-Token":session["csrf_token"]}
    old="/api/settings/ai-enrichment-schedule"
    assert client.put(old,headers=headers,json={"position_scope":"all","enabled":True}).status_code==200
    migrated=client.get(ENDPOINT).json()["items"]
    selected=next(row for row in migrated if row["position_scope"]=="all")
    jobs={}
    class Scheduler:
        def add_job(self,callback,trigger,**options):jobs[options["id"]]=options
        def get_job(self,identifier):return None
        def remove_job(self,identifier):jobs.pop(identifier,None)
        def get_jobs(self):return [SimpleNamespace(id=identifier) for identifier in jobs]
    monkeypatch.setattr(main,"scheduler",Scheduler())
    updated=client.put(old,headers=headers,json={"position_scope":"all","enabled":True,"schedule_config":{"frequency":"hourly","interval":4,"minute":15}})
    assert updated.status_code==200
    after=client.get(ENDPOINT).json()["items"]
    assert [row["id"] for row in after]==[row["id"] for row in migrated]
    assert next(row for row in after if row["id"]==selected["id"])["schedule_config"]["interval"]==4
    assert set(jobs)=={JOB_PREFIX+selected["id"]}


def test_named_scheduled_role_revocation_is_visible_without_child_start(schedule_environment, monkeypatch):
    client, auth, session, _ = schedule_environment
    headers={"X-CSRF-Token":session["csrf_token"]}
    saved=client.post(ENDPOINT,headers=headers,json=rule()).json()
    callbacks=[]
    class Deferred:
        def __init__(self,*,target,**_):self.target=target
        def start(self):callbacks.append(self.target)
    monkeypatch.setattr(main.research_schedules,"worker_factory",Deferred)
    monkeypatch.setattr(main.research_schedules,"_active",{})
    monkeypatch.setattr(main.risk_input_retrieval,"start",lambda *a,**kw:pytest.fail("Revoked owner started research"))
    monkeypatch.setattr(main.research_schedules,"auth_getter",lambda:SimpleNamespace(scheduled_session=lambda _:(_ for _ in ()).throw(PermissionError())))
    assert client.post(ENDPOINT+"/"+saved["id"]+"/run",headers=headers,json={}).status_code==202
    callbacks.pop()()
    row=client.get(ENDPOINT).json()["items"][0]
    assert row["last_run_code"]=="owner_not_authorized" and row["active"] is False


def test_restart_marks_unfinished_run_as_interrupted_without_changing_the_rule(schedule_environment):
    client, _, session, _ = schedule_environment
    headers={"X-CSRF-Token":session["csrf_token"]}
    saved=client.post(ENDPOINT,headers=headers,json=rule()).json()
    raw=main.local_store.get_preference("research_schedules_v1")
    raw["items"][0].update(last_run_code="running",last_request_id="previous-process-run")
    main.local_store.set_preference("research_schedules_v1",raw)
    main.research_schedules.configure()
    row=client.get(ENDPOINT).json()["items"][0]
    assert row["id"]==saved["id"] and row["revision"]==saved["revision"]
    assert row["last_run_code"]=="interrupted" and row["active"] is False


@pytest.mark.parametrize("legacy_endpoint,identifier,seed", [
    ("/api/settings/risk-input-retrieval-schedule", "legacy-risk_inputs", {}),
    ("/api/settings/country-rating-schedule", "legacy-country_ratings", {"country_scope":"all"}),
    ("/api/settings/ai-enrichment-schedule", "legacy-ai-open", {"position_scope":"open"}),
])
def test_legacy_cadence_only_save_preserves_advanced_named_rule_fields(schedule_environment, legacy_endpoint, identifier, seed):
    client, _, session, _ = schedule_environment
    headers={"X-CSRF-Token":session["csrf_token"]}
    assert client.put(legacy_endpoint,headers=headers,json={"enabled":True,**seed}).status_code==200
    migrated=next(row for row in client.get(ENDPOINT).json()["items"] if row["id"]==identifier)
    advanced={"name":"Shared advanced rule", "data_types":["prices","risk_inputs","country_ratings"],
        "position_scope":"all", "refresh_policy":"refresh_existing", "mode":"ai",
        "country_scope":"selected", "country_codes":["US","IL"], "expected_revision":migrated["revision"]}
    assert client.put(ENDPOINT+"/"+identifier,headers=headers,json=advanced).status_code==200
    main.research_schedules._receipt(identifier,{"batch_cursor":9,"last_run_code":"completed","last_request_id":"finished-run",
        "last_run_at":"2026-11-14T10:00:00Z","last_finished_at":"2026-11-14T10:01:00Z","last_jobs":[{"target":"risk_inputs","status":"completed"}]})
    before=next(row for row in client.get(ENDPOINT).json()["items"] if row["id"]==identifier)
    cadence={"frequency":"daily","hour":17,"minute":20}
    assert client.put(legacy_endpoint,headers=headers,json={"schedule_config":cadence,**seed}).status_code==200
    after=next(row for row in client.get(ENDPOINT).json()["items"] if row["id"]==identifier)
    for field in ("id","name","data_types","position_scope","security_keys","refresh_policy","mode","country_scope","country_codes",
                  "batch_cursor","last_run_at","last_finished_at","last_run_code","last_request_id","last_jobs","created_at"):
        assert after[field]==before[field],field
    assert after["revision"]==before["revision"]+1 and after["schedule_config"]["hour"]==17
    assert after["schedule_config"]["minute"]==20


def test_legacy_selection_change_updates_only_its_represented_selection_and_fences_active_run(schedule_environment,monkeypatch):
    client, _, session, _ = schedule_environment
    headers={"X-CSRF-Token":session["csrf_token"]}
    risk_endpoint="/api/settings/risk-input-retrieval-schedule"
    assert client.put(risk_endpoint,headers=headers,json={"enabled":True}).status_code==200
    identifier="legacy-risk_inputs"
    migrated=next(row for row in client.get(ENDPOINT).json()["items"] if row["id"]==identifier)
    assert client.put(ENDPOINT+"/"+identifier,headers=headers,json={"name":"Retain choices","data_types":["risk_inputs","country_ratings"],
        "position_scope":"all","refresh_policy":"refresh_existing","country_scope":"selected","country_codes":["IL"],
        "expected_revision":migrated["revision"]}).status_code==200
    raw=main.local_store.get_preference("research_schedules_v1")
    prior=next(row for row in raw["items"] if row["id"]==identifier)
    prior.update(batch_cursor=9,last_run_code="running",last_request_id="old-run")
    main.local_store.set_preference("research_schedules_v1",raw)
    monkeypatch.setattr(main.research_schedules,"_active",{identifier:"old-run"})
    response=client.put(risk_endpoint,headers=headers,json={"security_keys":["qa|nasdaq|usd"]})
    assert response.status_code==200
    after=next(row for row in client.get(ENDPOINT).json()["items"] if row["id"]==identifier)
    assert after["position_scope"]=="selected" and after["security_keys"]==["QA|NASDAQ|USD"] and after["batch_cursor"]==0
    assert after["country_scope"]=="selected" and after["country_codes"]==["IL"]
    assert after["name"]=="Retain choices" and after["refresh_policy"]=="refresh_existing"
    assert after["last_run_code"]=="schedule_changed" and after["active"] is True
    assert main.research_schedules._receipt(identifier,{"batch_cursor":99,"last_run_code":"completed"},
        owner=prior["owner_id"],revision=prior["revision"],run_id="old-run") is None
    current=next(row for row in client.get(ENDPOINT).json()["items"] if row["id"]==identifier)
    assert current["batch_cursor"]==0 and current["last_run_code"]=="schedule_changed"
