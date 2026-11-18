"""Research failures remain inspectable before authenticated finalization."""
from copy import deepcopy
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research_diagnostics import EVENT_LIMIT, event, receipt
from test_portfolio_ai_research import Deferred
from test_portfolio_risk_research import manager
from test_risk_input_retrieval import environment as risk_environment, queue
from test_security_enrichment import environment as enrichment_environment, start


def test_failed_partial_risk_is_preserved_and_retried_with_underlying_child_reason():
    parent, risk, _, _ = manager(fail_call=2)
    events = []
    parent._event_writer = lambda name, **fields: events.append({"event": name, **fields})
    original = risk.start
    def start_child(*args, **kwargs):
        result = original(*args, **kwargs)
        if result["status"] == "failed":
            result.update(code="request_limit", failure={"code":"request_limit","stage":"researching","error_type":"RestError"})
            result["outcomes"][0].update(status="partial",available_fields=["issuer_id"],sources=[{"url":"https://example.test/report"}])
        return result
    risk.start = start_child
    started = parent.start("owner", {}, "en", data_types=["risk_inputs"])
    Deferred.callbacks.pop(0)()
    failed = parent.get(started["request_id"], "owner")
    outcome = failed["risk_inputs"]["outcomes"][1]
    assert outcome["status"] == "partial" and outcome["available_fields"] == ["issuer_id"]
    assert outcome["sources"] and outcome["code"] == "request_limit"
    assert failed["risk_inputs"]["progress"]["completed"] == 1
    assert failed["failure"]["branch"] == "risk" and failed["failure"]["symbol"] == "QA2"
    assert failed["failure"]["child_request_id"] == "risk-2"
    assert failed["failure"]["child_failure"]["stage"] == "researching"
    diagnostic = parent.diagnostics(started["request_id"], "owner")
    assert diagnostic["children"][-1]["failure"]["code"] == "request_limit"
    assert all(type(row["elapsed_ms"]) is int and row["elapsed_ms"] >= 0 for row in diagnostic["events"])
    assert events[-1]["event"] == "research_parent_failed"
    assert "https://example" not in json.dumps(diagnostic)
    parent.start("owner", {}, "en", data_types=["risk_inputs"], resume_request_id=started["request_id"])
    Deferred.callbacks.pop(0)()
    resumed = parent.get(started["request_id"], "owner")
    assert resumed["status"] == "completed"
    assert "diagnostic" not in resumed["risk_inputs"]["outcomes"][1]
    assert sum("QA1|NYSE|USD" in call["keys"] for call in risk.calls) == 1
    assert sum("QA2|NYSE|USD" in call["keys"] for call in risk.calls) == 2


def test_parent_diagnostics_route_is_owner_authenticated_read_only_and_bounded():
    parent, _, _, _ = manager(fail_call=2)
    app = FastAPI()
    @app.middleware("http")
    async def auth(request, call_next):
        actor = request.headers.get("actor")
        if actor:
            request.state.auth_user = {"id":actor,"role":"Viewer"}
        return await call_next(request)
    app.include_router(parent.router())
    started = parent.start("owner", {}, "en", data_types=["risk_inputs"])
    Deferred.callbacks.pop(0)()
    path = "/api/securities/enrichment/ai/" + started["request_id"] + "/diagnostics"
    before = deepcopy(parent.get(started["request_id"], "owner")["counts"])
    client = TestClient(app)
    assert client.get(path).status_code == 401
    assert client.get(path,headers={"actor":"other"}).status_code == 404
    response = client.get(path,headers={"actor":"owner"})
    assert response.status_code == 200 and response.json()["status"] == "failed"
    assert parent.get(started["request_id"], "owner")["counts"] == before
    assert response.json()["event_limit"] == 200


def test_child_failure_before_finalize_is_logged_without_exception_or_credentials(enrichment_environment):
    env = enrichment_environment
    saved = []
    env.manager._event_writer = lambda name, **fields: saved.append({"event":name,**fields})
    identifier = start(env)
    env.state.expired = True
    env.run()
    job = env.manager.get(identifier,"owner")
    assert job["status"] == "failed" and job["code"] == "authentication_expired"
    assert env.state.saved == []
    assert any(row["event"] == "research_stage_failed" for row in saved)
    assert saved[-1]["event"] == "research_child_failed"
    env.state.expired = False
    path = "/api/securities/enrichment/ai/" + identifier + "/diagnostics"
    assert env.client.get(path,headers={"Authorization":"Bearer other"}).status_code == 404
    response = env.client.get(path,headers=env.headers)
    assert response.status_code == 200
    assert response.json()["failure"]["http_status"] == 401
    assert not any(secret in json.dumps(saved) for secret in ("synthetic-csrf", "synthetic-model-secret", "Bearer operator"))


def test_risk_wrapper_keeps_failed_ai_identity_counts_and_stage(risk_environment):
    retrieval, child, _, _ = queue(risk_environment)
    original = child.start
    def failed(*args, **kwargs):
        result = original(*args, **kwargs)
        result.update(status="failed",code="request_limit",failure={"code":"request_limit","stage":"researching","error_type":"RestError"})
        return result
    child.start = failed
    events=[]
    retrieval._event_writer=lambda name,**fields:events.append({"event":name,**fields})
    started=retrieval.start("owner",{},"en")
    from test_risk_input_retrieval import Deferred as RiskDeferred
    RiskDeferred.callbacks.pop(0)()
    job=retrieval.get(started["request_id"],"owner")
    assert job["status"] == "failed" and job["failure"]["stage"] == "researching"
    assert job["failure"]["child_request_id"] == "child"
    assert job["outcomes"][0]["ai"]["failure"]["code"] == "request_limit"
    assert job["outcomes"][0]["ai"]["counts"]["web_requests"] == 8
    assert job["children"][0]["counts"]["model_requests"] == 8
    assert events[-1]["event"] == "research_retrieval_failed"


def test_timeline_drops_untrusted_fields_and_has_fixed_retention():
    job={"request_id":"fixture","status":"running","progress":{"stage":"researching"},"counts":{"rest_requests":1,"password":"never"}}
    for _ in range(EVENT_LIMIT+4):
        event(job,None,"source_finished",prompt="private prompt",error="private error",source_url="https://example.test/private",
              code="source_read_failed",failure={"code":"source_read_failed","message":"secret","http_status":403})
    result=receipt(job)
    assert len(result["events"]) == EVENT_LIMIT and result["events_truncated"]
    assert not any(value in json.dumps(result) for value in ("private prompt","private error","example.test","password","secret"))


def test_risk_logger_emits_only_safe_lifecycle_after_finalization(risk_environment, monkeypatch):
    from app.risk_input_retrieval import CHILD_PREFIX
    retrieval, _, app, _ = queue(risk_environment)
    logged=[]
    manager=retrieval.evidence.manager(app,lambda:{"max_tool_loops":8,"max_rest_calls":8,"max_web_calls":8},
        event_writer=lambda name,**fields:logged.append({"event":name,**fields}))
    app.include_router(manager.router())
    def ask(self,prompt,language,read,*,audit,**kwargs):
        audit("model_request",message_count=1)
        audit("model_response",response={"content":"private-raw-risk-model-content"})
        return {"answer":'{"records":[]}'}
    monkeypatch.setattr("app.security_enrichment.PortfolioAssistant.ask",ask)
    # This is the existing deferred worker helper; execution remains fully offline.
    from test_security_enrichment import DeferredThread
    manager._worker_factory=DeferredThread
    started=manager.start("owner",{},"en",security_keys=[risk_environment[1][0]["security_key"]])
    DeferredThread.workers[-1].run()
    result=manager.get(started["request_id"],"owner")
    assert result["status"] == "completed",result
    assert all(row["event"].startswith("research_") for row in logged)
    assert "private-raw-risk-model-content" not in json.dumps(logged)
    assert not any("response" in row or "arguments" in row or "candidates" in row for row in logged)
    assert {"finalize_started","finalize_written","finalize_completed"} <= {row["step"] for row in logged}
    assert "private-raw-risk-model-content" not in json.dumps(manager.diagnostics(started["request_id"],"owner"))
    assert TestClient(app).get(CHILD_PREFIX+"/ai/"+started["request_id"]+"/diagnostics").status_code == 200


def test_safe_source_operation_receipt_keeps_opaque_ids_reader_and_counts():
    job={"request_id":"fixture","status":"running","progress":{"stage":"researching"},"counts":{}}
    identifier="source-"+"a"*32
    event(job,None,"source_finished",source_id=identifier,operation_id="operation-"+"b"*32,
        document_id="document-"+"c"*32,reader="jina",reader_engine="direct",window_start=20,window_end=200,
        source_counts={"search_requests":1,"source_requests":2,"read_failures":1,"prompt":"never"},
        source_url="https://example.test/private",query="private search text")
    recorded=receipt(job)["events"][-1]
    assert recorded["source_id"] == identifier and recorded["reader"] == "jina"
    assert recorded["source_counts"] == {"search_requests":1,"source_requests":2,"read_failures":1}
    assert recorded["window_start"] == 20 and recorded["window_end"] == 200
    assert not any(value in json.dumps(recorded) for value in ("private", "never", "example.test"))
    event(job,None,"source_finished",source_id="https://example.test/private",reader="private reader")
    assert "source_id" not in receipt(job)["events"][-1] and "reader" not in receipt(job)["events"][-1]


def test_unrelated_report_lines_do_not_repeat_full_document_retraction_scan(monkeypatch):
    from app import risk_input_sources
    checked=[]
    original=risk_input_sources._retracted_context
    def retracted(text,block):
        checked.append(block)
        return original(text,block)
    monkeypatch.setattr(risk_input_sources,"_retracted_context",retracted)
    source={"url":"https://issuer.example/report","observation_date":"2026-09-30","retrieved_at":"2026-11-18T12:00:00Z",
        "text":"Unrelated report prose and figures.\n"*2000+"Economic country currency: USD\n"}
    records=risk_input_sources._literal_risk_records(source,{"asset_class":"EQUITY"})
    assert [(row["field"],row["value"]) for row in records] == [("country_currency","USD")]
    assert checked == ["Economic country currency: USD"]


def test_finalize_reuses_immutable_document_parse_but_preserves_window_visibility(risk_environment,monkeypatch):
    from app import risk_input_retrieval
    from test_risk_input_retrieval import record
    retrieval,_,_,_=queue(risk_environment)
    evidence=retrieval.evidence
    candidate=evidence.candidates(refresh_policy="refresh_existing")["items"][0]
    record_value={**record("issuer_id","sec:1513363"),"record_id":"fixture-record"}
    parsed=[]
    validations=[]
    def extract(source,subject):
        parsed.append((source["document_id"],subject["security_key"]))
        return [record_value]
    def validate(source,subject,request_id):
        validations.append(source["document_id"])
        return {**source,"text":"Complete Exact synthetic source retained document"}
    monkeypatch.setattr(risk_input_retrieval,"extract_risk_records",extract)
    monkeypatch.setattr(evidence,"_validation_source",validate)
    monkeypatch.setattr(evidence,"_rating_records",lambda *args:[])
    monkeypatch.setattr(evidence.inputs,"publish_evidence",lambda *args,**kwargs:None)
    key=candidate["security_key"]
    proposal=json.dumps({"records":[{"security_key":key,"source_id":"fixture-source","record_id":"fixture-record"}]})
    hidden={"source_id":"fixture-source","document_id":"immutable-document","text":"Unrelated window"}
    visible={**hidden,"text":"Exact synthetic source"}
    def finalize(sources):
        return evidence.finalize([],"owner","fixture-request",proposal=proposal,
            evidence_by_key={key:sources},candidates={key:candidate})[0]
    result=finalize([hidden,visible])
    assert result["available_fields"] == ["issuer_id"] and len(parsed)==len(validations)==1
    hidden_result=finalize([hidden,hidden])
    assert hidden_result["available_fields"] == []
    assert len(parsed)==2,"Cache must not cross finalization requests"
    parsed.clear();validations.clear()
    finalize([hidden,{**visible,"document_id":"another-immutable-document"}])
    assert len(parsed)==len(validations)==2,"Different retained document versions require fresh validation"
