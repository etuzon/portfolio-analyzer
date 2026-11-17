"""Independent interrupted-parent recovery checks; disposable data and browsers only."""
from copy import deepcopy
import base64
import json
import subprocess
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.portfolio_ai_research import PortfolioAIResearch
from app.codex_bridge import CodexBridgeError
from app.llm_assistant import AssistantError, PortfolioAssistant, assistant_settings
from test_account_cash_update_qa import browser_wait
from test_ai_enrichment_frontend import ready
from test_assistant_security import authenticated_chats
from test_chat_diagnostics import diagnostic_chat_env
from test_native_account_history_qa import chromium
from test_risk_scale_v4_browser_qa import press


@pytest.mark.parametrize("data_type", ["profile", "risk_inputs", "country_ratings"])
@pytest.mark.parametrize("language,width", [("en", 1440), ("he", 390)])
def test_stopped_nonrating_parent_exposes_explicit_retry_without_discarding_results(
        tmp_path, chromium, data_type, language, width):
    command, evaluate = ready(tmp_path, chromium, language, width)
    evaluate(r'''
qa.kind=QA_KIND;
qa.rows=Array.from({length:27},(_,index)=>({security_key:`QA${index}|NYSE|USD`,symbol:`QA${index}`,stock_market:'NYSE',currency:'USD',
 status:index<10?'updated':'not_attempted',code:index<10?'data_found':'ai_provider_unavailable',attempted:index<10,
 available_fields:index<10?['profile']:[],missing_fields:index<10?[]:['profile']}));
qa.stopped={request_id:'stopped-parent',position_scope:'all',ratings_only:false,data_types:[qa.kind],refresh_policy:'refresh_existing',risk_mode:'ai',
 status:'failed',code:'ai_provider_unavailable',progress:{stage:'failed',completed:10,total:27},
 counts:{model_requests:8,rest_requests:4,web_requests:3,max_model_requests:8,max_rest_requests:8,max_web_requests:8},
 summary:{updated:10,not_attempted:17},outcomes:qa.kind==='profile'?qa.rows:[],portfolio_refresh_required:false};
if(qa.kind!=='profile')qa.stopped[qa.kind]={status:'failed',progress:{completed:10,total:27},outcomes:qa.rows,summary:{updated:10,not_attempted:17,total_candidates:27}};
state.aiEnrichment.job=qa.stopped;state.aiEnrichment.outcomes=qa.stopped.outcomes;state.aiEnrichment.pending=false;state.aiEnrichment.resume=false;
qa.savedRows=JSON.stringify(qa.rows);qa.originalApi=api;
api=async(path,options={})=>{
 if(path==='/api/securities/enrichment/status')return {items:qa.stopped.outcomes,last_job:qa.stopped};
 if(path==='/api/securities/enrichment/ai'&&options.method==='POST'){
  qa.aiPosts++;qa.aiBodies.push(JSON.parse(options.body));return await new Promise(resolve=>qa.resolveRetry=resolve);
 }
 return qa.originalApi(path,options);
};
renderAIEnrichment();$('enrichMissingData').click();
'''.replace("QA_KIND", json.dumps(data_type)))
    browser_wait(evaluate, "state.aiEnrichment.job?.request_id==='stopped-parent'")
    assert evaluate("qa.aiPosts") == 0, "Viewing stopped results must never launch more research"
    assert evaluate("$('aiEnrichmentRetryRatings').hidden") is False
    assert evaluate("$('aiEnrichmentRetryRatings').disabled") is False
    assert evaluate("$('aiEnrichmentProgress').value") == 10
    assert evaluate("$('aiEnrichmentProgress').max") == 27
    message = evaluate("$('aiEnrichmentStatus').textContent")
    assert not any(term in message.lower() for term in ("sign-in", "sign in", "התחברות")), message
    assert evaluate("JSON.stringify(qa.rows)===qa.savedRows")
    assert evaluate("$('loadingOverlay').hidden&&!$('refresh').disabled")
    # A different next-request selection cannot change this parent's retry.
    evaluate(r'''
$('aiResearchTarget').value='prices';$('aiResearchTarget').dispatchEvent(new Event('change',{bubbles:true}));
$('aiResearchRefresh').value='missing';$('aiResearchRefresh').dispatchEvent(new Event('change',{bubbles:true}));
$('aiEnrichmentRetryRatings').scrollIntoView({block:'center'});$('aiEnrichmentRetryRatings').focus();
''')
    assert evaluate("document.activeElement===$('aiEnrichmentRetryRatings')")
    assert evaluate("document.documentElement.scrollWidth-innerWidth") <= 1
    (tmp_path / f"stopped-retry-{data_type}-{language}-{width}.png").write_bytes(base64.b64decode(
        command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
    press(command, "Enter", "Enter", 13, "\r")
    browser_wait(evaluate, "qa.aiPosts===1")
    assert evaluate("qa.aiBodies[0]") == {
        "position_scope": "all", "ratings_only": False, "data_types": [data_type],
        "refresh_policy": "refresh_existing", "risk_mode": "ai",
        "resume_request_id": "stopped-parent",
    }
    assert evaluate("state.aiEnrichment.job?.request_id") == "stopped-parent"
    assert evaluate("state.aiEnrichment.job.progress.completed") == 10
    assert evaluate("state.aiEnrichment.job.counts.model_requests") == 8
    assert evaluate("JSON.stringify(qa.rows)===qa.savedRows")
    evaluate("qa.resolveRetry({...qa.stopped,status:'queued',code:'queued'});")
    browser_wait(evaluate, "state.aiEnrichment.pending&&!!qa.poll")
    assert evaluate("$('aiEnrichmentRetryRatings').hidden||$('aiEnrichmentRetryRatings').disabled")
    assert evaluate("qa.aiPosts") == 1
    assert evaluate("qa.errors") == []


def test_stopped_retry_permissions_and_uncertain_request_remain_read_only(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate(r'''
state.aiEnrichment.job={request_id:'stopped-parent',status:'failed',position_scope:'open',data_types:['profile'],refresh_policy:'missing',
 progress:{stage:'failed',completed:0,total:1},outcomes:[{symbol:'QA',stock_market:'NYSE',currency:'USD',status:'not_attempted'}]};
for(const role of ['Viewer','Operator']){
 state.auth.user.role=role;state.auth.forcedPasswordChange=role==='Operator';renderAIEnrichment();
 if(!$('aiEnrichmentRetryRatings').hidden&&!$('aiEnrichmentRetryRatings').disabled)throw Error('Retry must honor current permissions');
 $('aiEnrichmentRetryRatings').click();
}
state.auth.user.role='Operator';state.auth.forcedPasswordChange=false;state.aiEnrichment.resume=true;renderAIEnrichment();
if(!$('aiEnrichmentRetryRatings').hidden)throw Error('Uncertain parent must be checked, not duplicated');
''')
    assert evaluate("qa.aiPosts") == 0
    evaluate("$('aiEnrichmentResume').click()")
    browser_wait(evaluate, "qa.aiGets>0")
    assert evaluate("qa.aiPosts") == 0
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("language", ["en", "he"])
def test_timeout_busy_and_unknown_causes_are_distinct_localized_and_require_manual_action(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    values = evaluate(r'''
state.aiEnrichment.job={request_id:'stopped',status:'failed',data_types:['profile'],progress:{stage:'failed',completed:0,total:1},
 outcomes:[{symbol:'QA',stock_market:'NYSE',currency:'USD',status:'not_attempted'}]};
['ai_provider_timeout','ai_provider_busy','ai_provider_unavailable'].map(code=>{
 state.aiEnrichment.job.code=code;renderAIEnrichment();
 if($('aiEnrichmentRetryRatings').hidden)throw Error('Stopped checks require an explicit recovery action');
 return $('aiEnrichmentStatus').textContent;
});
''')
    assert len(set(values)) == 3
    assert ("timed out" if language == "en" else "חרגה מהזמן") in values[0]
    assert ("busy" if language == "en" else "עמוס") in values[1]
    assert all(("Saved results" if language == "en" else "התוצאות השמורות") in value for value in values)
    assert all(not any(term in value.lower() for term in ("sign-in", "sign in", "התחברות")) for value in values)
    if language == "he":
        assert not any(term in " ".join(values) for term in ("Saved", "retry", "checks", "service"))
    assert evaluate("qa.aiPosts") == 0
    evaluate("state.aiEnrichment.job.status='completed';renderAIEnrichment();")
    assert evaluate("$('aiEnrichmentRetryRatings').hidden")
    evaluate("state.aiEnrichment.job.status='failed';state.aiEnrichment.job.outcomes=[];state.aiEnrichment.job.progress={completed:1,total:1};renderAIEnrichment();")
    assert evaluate("$('aiEnrichmentRetryRatings').hidden"), "No remaining work means no resume action"


def test_selected_scope_reaches_retry_and_same_parent_refreshes_newly_saved_results(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate(r'''
qa.selected=['QA1|NYSE|USD','QA2|NYSE|USD'];
qa.savedJob={request_id:'selected-parent',status:'failed',code:'ai_provider_timeout',position_scope:'all',
 data_types:['profile'],refresh_policy:'stale',risk_mode:'api',security_keys:qa.selected,portfolio_refresh_required:true,
 progress:{stage:'failed',completed:1,total:2},outcomes:[
  {security_key:qa.selected[0],symbol:'QA1',stock_market:'NYSE',currency:'USD',status:'updated'},
  {security_key:qa.selected[1],symbol:'QA2',stock_market:'NYSE',currency:'USD',status:'not_attempted'}]};
state.aiEnrichment.job=qa.savedJob;state.aiEnrichment.refreshedJob=state.aiEnrichment.refreshedRatingsJob='selected-parent';
qa.refreshes=0;qa.beforeApi=api;
api=async(path,options={})=>{
 if(path==='/api/securities/enrichment/ai'&&options.method==='POST'){
  qa.aiPosts++;qa.aiBodies.push(JSON.parse(options.body));return {...qa.savedJob,status:'completed',code:'research_complete',
    progress:{stage:'completed',completed:2,total:2},outcomes:qa.savedJob.outcomes.map(row=>({...row,status:'updated'}))};
 }
 return qa.beforeApi(path,options);
};
renderAIEnrichment();$('aiEnrichmentRetryRatings').click();
''')
    browser_wait(evaluate, "qa.aiPosts===1&&qa.refreshes===1")
    assert evaluate("qa.aiBodies[0].security_keys") == ["QA1|NYSE|USD", "QA2|NYSE|USD"]
    assert evaluate("qa.aiBodies[0].risk_mode") == "api"
    assert evaluate("qa.aiBodies[0].resume_request_id") == "selected-parent"
    assert evaluate("state.aiEnrichment.job.outcomes.every(row=>row.status==='updated')")
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("route", ["POST", "GET", "poll", "riskGET", "status"])
@pytest.mark.parametrize("language", ["en", "he"])
def test_expired_in_memory_parent_retains_saved_outcomes_and_requires_explicit_new_request(
        tmp_path, chromium, route, language):
    _, evaluate = ready(tmp_path, chromium, language)
    evaluate(r'''
qa.expiryRoute=QA_ROUTE;qa.postsBeforeExpiry=0;qa.getsBeforeExpiry=0;
qa.savedRows=[{symbol:'SAVED',stock_market:'NYSE',currency:'USD',status:'updated',code:'data_found',
 available_fields:['profile'],missing_fields:[]}];
state.allPortfolioItems=[{holding:qa.savedRows[0],api_data_route:{owner:'ai'},missing:[]}];
state.aiEnrichment.outcomes=qa.savedRows;
state.aiEnrichment.job={request_id:'expired-parent',status:'failed',code:'ai_provider_timeout',position_scope:'all',
 data_types:['profile'],refresh_policy:'missing',risk_mode:'api_then_ai',progress:{stage:'failed',completed:1,total:2},
 outcomes:[...qa.savedRows,{symbol:'PENDING',stock_market:'NYSE',currency:'USD',status:'not_attempted'}]};
if(qa.expiryRoute==='riskGET'){
 state.aiEnrichment.job.data_types=['risk_inputs'];
 state.aiEnrichment.job.risk_inputs={status:'failed',progress:{completed:1,total:2},outcomes:state.aiEnrichment.job.outcomes};
}
state.aiEnrichment.pending=qa.expiryRoute==='poll';state.aiEnrichment.resume=qa.expiryRoute==='GET';
qa.beforeExpiry=JSON.stringify(qa.savedRows);
api=async(path,options={})=>{
 if(path==='/api/securities/enrichment/status')return {items:qa.savedRows,active_job:null,last_job:null};
 if(options.method==='POST')qa.postsBeforeExpiry++;else qa.getsBeforeExpiry++;
 const error=new Error('raw private provider failure');error.status=404;error.code='enrichment_request_not_found';throw error;
};
renderAIEnrichment();
if(qa.expiryRoute==='POST')$('aiEnrichmentRetryRatings').click();
else if(qa.expiryRoute==='GET')$('aiEnrichmentResume').click();
else if(qa.expiryRoute==='poll'){scheduleAIEnrichmentPoll();qa.poll();}
else if(qa.expiryRoute==='riskGET')$('aiRiskResearchCheck').click();
else loadAIEnrichmentStatus();
'''.replace("QA_ROUTE", json.dumps(route)))
    browser_wait(evaluate, "!state.aiEnrichment.job&&!state.aiEnrichment.pending&&!state.aiEnrichment.resume")
    assert evaluate("JSON.stringify(state.aiEnrichment.outcomes)===qa.beforeExpiry")
    assert "SAVED" in evaluate("$('aiEnrichmentResults').textContent")
    assert evaluate("$('aiEnrichmentResume').hidden&&$('aiEnrichmentRetryRatings').hidden")
    assert evaluate("!$('aiEnrichmentStart').disabled&&!$('aiEnrichmentStartAll').disabled")
    notice = evaluate("$('aiEnrichmentStatus').textContent")
    assert ("new request" if language == "en" else "בקשה חדשה") in notice
    assert "raw private" not in notice
    assert evaluate("qa.postsBeforeExpiry") == (1 if route == "POST" else 0)
    assert evaluate("qa.getsBeforeExpiry") == (1 if route in {"GET", "poll", "riskGET"} else 0)
    assert evaluate("qa.errors") == []


def test_unknown_transport_failure_preserves_parent_and_checks_progress_without_duplicate_post(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate(r'''
qa.transportPosts=0;qa.transportGets=0;
qa.stopped={request_id:'uncertain-parent',status:'failed',code:'ai_provider_timeout',position_scope:'all',data_types:['profile'],
 refresh_policy:'stale',progress:{stage:'failed',completed:1,total:2},outcomes:[{symbol:'SAVED',stock_market:'NYSE',currency:'USD',status:'updated'},
 {symbol:'PENDING',stock_market:'NYSE',currency:'USD',status:'not_attempted'}]};
state.aiEnrichment.job=qa.stopped;state.aiEnrichment.outcomes=qa.stopped.outcomes;
api=async(path,options={})=>{
 if(options.method==='POST'){qa.transportPosts++;throw new TypeError('synthetic network disconnect');}
 qa.transportGets++;return qa.stopped;
};
renderAIEnrichment();$('aiEnrichmentRetryRatings').click();
''')
    browser_wait(evaluate, "state.aiEnrichment.resume&&!state.aiEnrichment.pending")
    assert evaluate("state.aiEnrichment.job.request_id") == "uncertain-parent"
    assert evaluate("state.aiEnrichment.job.progress.completed") == 1
    assert evaluate("$('aiEnrichmentRetryRatings').hidden&&!$('aiEnrichmentResume').hidden")
    evaluate("$('aiEnrichmentResume').click()")
    browser_wait(evaluate, "qa.transportGets===1&&!state.aiEnrichment.resume")
    assert evaluate("qa.transportPosts") == 1
    assert evaluate("state.aiEnrichment.job.request_id") == "uncertain-parent"
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("source", ["poll", "POST"])
def test_late_response_cannot_restore_a_confirmed_expired_parent(tmp_path, chromium, source):
    _, evaluate = ready(tmp_path, chromium)
    evaluate(r'''
qa.lateSource=QA_SOURCE;qa.latePosts=0;qa.lateGets=0;
qa.lateJob={request_id:'late-parent',status:'failed',code:'ai_provider_timeout',position_scope:'open',data_types:['profile'],
 progress:{stage:'failed',completed:0,total:1},outcomes:[{symbol:'QA',stock_market:'NYSE',currency:'USD',status:'not_attempted'}]};
state.aiEnrichment.job=qa.lateJob;state.aiEnrichment.pending=qa.lateSource==='poll';
api=async(path,options={})=>{
 if(path.endsWith('/status'))return {items:[],active_job:null,last_job:null};
 if(options.method==='POST')qa.latePosts++;else qa.lateGets++;
 return await new Promise(resolve=>qa.resolveLate=resolve);
};
renderAIEnrichment();
if(qa.lateSource==='poll'){scheduleAIEnrichmentPoll();qa.poll();}
else $('aiEnrichmentRetryRatings').click();
true;
'''.replace("QA_SOURCE", json.dumps(source)))
    browser_wait(evaluate, "!!qa.resolveLate")
    evaluate("loadAIEnrichmentStatus()")
    assert evaluate("!state.aiEnrichment.job&&!state.aiEnrichment.pending&&!state.aiEnrichment.resume")
    evaluate("qa.resolveLate({...qa.lateJob,status:'running'});new Promise(resolve=>qa.nativeTimeout.call(window,resolve,0));")
    assert evaluate("!state.aiEnrichment.job&&!state.aiEnrichment.pending&&!state.aiEnrichment.resume")
    assert evaluate("qa.latePosts") == (1 if source == "POST" else 0)
    assert evaluate("qa.lateGets") == (1 if source == "poll" else 0)
    assert evaluate("qa.errors") == []


def test_actual_claude_process_deadline_is_typed_and_does_not_disclose_process_output(monkeypatch):
    from app import claude_bridge

    class Process:
        pid = 999999
        returncode = None

        def communicate(self, payload, timeout):
            assert timeout == .01
            raise subprocess.TimeoutExpired("isolated planner", timeout, output=b"secret stdout", stderr=b"secret stderr")

        def wait(self, **_):
            self.returncode = 0

    monkeypatch.setattr(claude_bridge.shutil, "which", lambda _: "/synthetic/claude")
    monkeypatch.setattr(claude_bridge.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(claude_bridge.os, "killpg", lambda *_: None)
    with pytest.raises(CodexBridgeError) as stopped:
        claude_bridge.claude_completion([], [], timeout=.01)
    assert stopped.value.code == "ai_provider_timeout"
    assert "secret" not in str(stopped.value)


@pytest.mark.parametrize("cause,code,canonical", [
    ("Local Codex timed out. private-tail-without-secret-label", "ai_provider_timeout", "Local Codex timed out."),
    ("Claude Code planning turn timed out. private-tail-without-secret-label", "ai_provider_timeout", "Claude Code planning turn timed out."),
    ("prefix Local Codex timed out. private-tail-without-secret-label", "ai_provider_unavailable", None),
    ("local Codex timed out. private-tail-without-secret-label", "ai_provider_unavailable", None),
    ({"message": "Local Codex timed out. private-tail-without-secret-label"}, "ai_provider_unavailable", None),
])
def test_legacy_timeout_recognition_retains_only_fixed_diagnostic_text(monkeypatch, cause, code, canonical):
    original = httpx.Client
    transport = httpx.MockTransport(lambda _: httpx.Response(503, json={"error": {"message": cause}}))
    monkeypatch.setattr(httpx, "Client", lambda **_: original(transport=transport, base_url="http://codex-local"))
    assistant = PortfolioAssistant(assistant_settings({"llm": {"provider": "local_codex"}}), {})
    with pytest.raises(AssistantError) as failure:
        assistant._call_provider(messages=[], tools=[])
    assert failure.value.code == code
    assert "private-tail-without-secret-label" not in str(failure.value)
    if canonical:
        assert canonical in str(failure.value)


@pytest.mark.parametrize("provider,canonical", [
    ("local_codex", "Local Codex timed out."),
    ("local_claude", "Claude Code planning turn timed out."),
])
def test_legacy_timeout_tail_never_reaches_protected_chat_logs_or_ui(diagnostic_chat_env, provider, canonical):
    from app import main
    from app.config import AppConfig

    env = diagnostic_chat_env
    client = env.login()
    tail = "unstructured-private-provider-diagnostic"

    class BridgeClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, path, json):
            assert path == "/completion"
            return httpx.Response(503, json={"error": {"message": canonical + " " + tail}})

    env.patch.setattr(httpx, "Client", BridgeClient)
    env.patch.setattr(main, "config", AppConfig(raw={"llm": {"enabled": True, "provider": provider}},
                                                path=env.store.path.parent / "unused.yaml"))
    env.patch.setattr(PortfolioAssistant, "status", lambda self: {"enabled": True})
    response = client.post("/api/assistant/questions", json={"prompt": "Read accounts", "language": "he"})
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "assistant_unavailable"
    assert tail not in response.text and canonical not in response.text
    events = [json.loads(line) for line in (env.store.path.parent / "logs/chat.log").read_text().splitlines()]
    failures = [event for event in events if event["event"] == "request_failed" and event["request_id"] == detail["request_id"]]
    assert len(failures) == 1 and canonical in failures[0]["error"]
    assert tail not in json.dumps(events), "Fixed legacy causes must not retain an arbitrary untrusted tail in protected logs"


class Deferred:
    callbacks = []

    def __init__(self, target, **_kwargs):
        self.callbacks.append(target)

    def start(self):
        pass


def item(number, *, country=False):
    return {"security_key": f"COUNTRY:C{number}" if country else f"QA{number}|NYSE|USD",
            "symbol": f"QA{number}", "stock_market": "NYSE", "currency": "USD", "asset_class": "EQUITY"}


class BoundedChildren:
    """A deterministic child stops once, after returning one independent fact."""

    def __init__(self, rows, *, stop=False):
        self.rows, self.stop, self.calls, self.jobs = rows, stop, [], {}
        self.evidence = SimpleNamespace(candidates=lambda **_: {"items": deepcopy(rows)})

    def settings(self):
        return {"max_tool_loops": 8, "max_rest_calls": 8, "max_web_calls": 8}

    def start(self, owner, headers, language, scope="open", **options):
        keys = options.get("security_keys") or ["COUNTRY:" + code for code in options["country_codes"]]
        self.calls.append(deepcopy({"scope": scope, **options}))
        failure = self.stop and len(self.calls) == 2
        rows = [{**next(row for row in self.rows if row["security_key"] == key),
                 "status": "not_attempted" if failure else "updated", "attempted": not failure,
                 "code": "ai_provider_unavailable" if failure else "data_found", "missing_fields": [],
                 "sources": [{"url": "https://example.org/verified", "quote": "preserved source fact"}]} for key in keys]
        identifier = "child-" + str(len(self.calls))
        result = {"request_id": identifier, "status": "failed" if failure else "completed",
                  "code": "ai_provider_unavailable" if failure else "data_found", "outcomes": rows,
                  "counts": {"model_requests": 8 if failure else 2, "rest_requests": 3, "web_requests": 1,
                             "max_model_requests": 8, "max_rest_requests": 8, "max_web_requests": 8}}
        self.jobs[identifier] = result
        return deepcopy(result)


@pytest.mark.parametrize("branch,data_type", [("market", "profile"), ("risk", "risk_inputs"), ("country", "country_ratings")])
def test_manual_resume_retains_finished_work_counts_and_frozen_contract(branch, data_type):
    Deferred.callbacks = []
    rows = [item(index, country=branch == "country") for index in range(7)]
    target = BoundedChildren(rows, stop=True)
    unused = BoundedChildren([])
    parent = PortfolioAIResearch(target if branch == "market" else unused, unused,
        lambda *_, **__: {"market_items": rows if branch == "market" else [], "credit_items": []},
        risk_jobs=target if branch == "risk" else None, country_jobs=target if branch == "country" else unused,
        country_inventory_reader=lambda *_, **__: rows if branch == "country" else [],
        worker_factory=Deferred, poll_seconds=0)
    # No financial formula is exercised by these coordination fixtures.
    parent._refresh_risk_outcomes = lambda _: None
    contract = {"data_types": [data_type], "refresh_policy": "refresh_existing", "risk_mode": "ai"}
    started = parent.start("owner", {}, "he", "all", **contract)
    Deferred.callbacks.pop(0)()
    failed = parent.get(started["request_id"], "owner")
    assert failed["status"] == "failed"
    panel = failed if branch == "market" else failed[{"risk": "risk_inputs", "country": "country_ratings"}[branch]]
    saved = deepcopy([row for row in panel["outcomes"] if row["status"] == "updated"])
    assert saved and panel["progress"]["completed"] == len(saved)
    prior_counts = deepcopy(failed["counts"])
    prior_calls = len(target.calls)
    for changed in ({"data_types": ["prices"]}, {"refresh_policy": "missing"}, {"risk_mode": "api"}):
        with pytest.raises(HTTPException) as rejected:
            parent.start("owner", {}, "he", "all", resume_request_id=started["request_id"], **{**contract, **changed})
        assert rejected.value.status_code == 409
    with pytest.raises(HTTPException) as wrong_owner:
        parent.start("other", {}, "he", "all", resume_request_id=started["request_id"], **contract)
    assert wrong_owner.value.status_code == 404
    queued = parent.start("owner", {}, "he", "all", resume_request_id=started["request_id"], **contract)
    assert queued["counts"] == prior_counts
    assert queued["per_batch_limits"] == {"model": 8, "rest": 8, "web": 8}
    parent.start("owner", {}, "he", "all", resume_request_id=started["request_id"], **contract)
    assert len(Deferred.callbacks) == 1, "Repeated clicks must not schedule duplicate workers"
    Deferred.callbacks.pop(0)()
    completed = parent.get(started["request_id"], "owner")
    assert completed["status"] == "completed"
    after_panel = completed if branch == "market" else completed[{"risk": "risk_inputs", "country": "country_ratings"}[branch]]
    assert all(row in after_panel["outcomes"] for row in saved), "A retry cannot replace completed sourced facts"
    resumed = [key for call in target.calls[prior_calls:] for key in
               (call.get("security_keys") or ["COUNTRY:" + code for code in call["country_codes"]])]
    assert not {row["security_key"] for row in saved} & set(resumed)
    assert len(resumed) == len(set(resumed)) == 7 - len(saved)
    for axis in ("model", "rest", "web"):
        assert completed["counts"][axis + "_requests"] >= prior_counts[axis + "_requests"]
        assert completed["counts"][axis + "_requests"] == sum(child["job"]["counts"][axis + "_requests"]
                                                              for child in parent._jobs[started["request_id"]]["_children"])
    assert len(target.calls) == len(target.jobs), "A manual retry creates bounded child jobs rather than resetting them"


def test_public_selection_snapshot_is_copied_and_owner_bound_on_manual_resume():
    Deferred.callbacks = []
    rows = [item(index) for index in range(2)]
    target, unused = BoundedChildren(rows, stop=True), BoundedChildren([])
    parent = PortfolioAIResearch(unused, unused, lambda *_, **__: {"market_items": [], "credit_items": []},
        risk_jobs=target, country_jobs=unused, country_inventory_reader=lambda *_, **__: [],
        worker_factory=Deferred, poll_seconds=0)
    parent._refresh_risk_outcomes = lambda _: None
    keys = [row["security_key"] for row in rows]
    options = {"data_types": ["risk_inputs"], "refresh_policy": "stale", "risk_mode": "ai", "security_keys": keys}
    started = parent.start("owner", {}, "en", "all", **options)
    assert started["security_keys"] == keys
    started["security_keys"].append("UNAUTHORIZED|NYSE|USD")
    assert parent.get(started["request_id"], "owner")["security_keys"] == keys
    Deferred.callbacks.pop(0)()
    assert parent.get(started["request_id"], "owner")["status"] == "failed"
    with pytest.raises(HTTPException) as missing_selection:
        parent.start("owner", {}, "en", "all", resume_request_id=started["request_id"], **{**options, "security_keys": None})
    assert missing_selection.value.status_code == 409
    with pytest.raises(HTTPException) as unauthorized:
        parent.get(started["request_id"], "other")
    assert unauthorized.value.status_code == 404
    parent.start("owner", {}, "en", "all", resume_request_id=started["request_id"], **options)
    Deferred.callbacks.pop(0)()
    assert parent.get(started["request_id"], "owner")["status"] == "completed"
    assert target.calls[-1]["security_keys"] == [keys[1]], "Only the unfinished selected security is repeated"
