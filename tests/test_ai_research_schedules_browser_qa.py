"""Independent actual-page target/schedule journeys with synthetic API receipts.

Disposable Chromium covers interaction and rendering. These controlled API
receipts do not establish actual Internet/model retrieval, which has its own gate.
"""
import base64
import json

import pytest

from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium
from test_risk_scale_v4_browser_qa import click, press


def fixture(tmp_path, language):
    page = cash_browser_document(tmp_path, language)
    source = tmp_path / "cash-app.js"
    source.write_text(source.read_text() + r'''
qa.rules=[
 {id:'weekly-risk',revision:1,name:'QA A',enabled:true,data_types:['risk_inputs'],position_scope:'open',security_keys:null,country_scope:'accounts',country_codes:null,mode:'api_then_ai',refresh_policy:'stale',schedule_config:{frequency:'weekly',weekdays:[0],hour:8,minute:15},timezone:'UTC',language:'en',next_run:'2026-11-20T08:15:00Z',editable:true,active:false},
 {id:'daily-risk',revision:1,name:'QA B',enabled:true,data_types:['risk_inputs'],position_scope:'all',security_keys:null,country_scope:'accounts',country_codes:null,mode:'api',refresh_policy:'refresh_existing',schedule_config:{frequency:'daily',hour:16,minute:20},timezone:'UTC',language:'en',next_run:'2026-11-20T16:20:00Z',editable:true,active:false}
];
qa.ruleBodies=[];qa.riskBodies=[];qa.marketBodies=[];qa.confirmations=[];qa.rulesMode='ok';qa.retrieval=null;
confirm=text=>{qa.confirmations.push(text);return true;};
api=async(path,options={})=>{
 qa.calls.push(path);const method=options.method || 'GET',body=options.body?JSON.parse(options.body):{};
 const endpoint='/api/settings/research-schedules';
 if(path===endpoint+'/inventory')return{items:[{security_key:'QA|NASDAQ|USD',symbol:'QA',stock_market:'NASDAQ',currency:'USD'}]};
 if(path.startsWith('/api/countries/credit-ratings/countries'))return{items:[{country_code:'US'},{country_code:'IL'}]};
 if(path===endpoint && method==='GET')return{items:structuredClone(qa.rules)};
 if(path.startsWith(endpoint) && method!=='GET'){
  qa.ruleBodies.push({path,method,body});
  if(qa.rulesMode==='fail'){qa.rulesMode='ok';throw Error('Synthetic save interruption');}
  if(method==='POST' && path===endpoint){const row={...body,id:'added-'+qa.rules.length,revision:1,editable:true,active:false,next_run:'2026-11-21T23:59:00Z'};qa.rules.push(row);return structuredClone(row);}
  const id=path.slice(endpoint.length+1),row=qa.rules.find(row=>row.id===id);
  if(method==='PUT'){if(body.expected_revision!==row.revision){const e=Error('Synthetic revision conflict');e.status=409;throw e;}Object.assign(row,body,{revision:row.revision+1});return structuredClone(row);}
  if(method==='DELETE'){qa.rules=qa.rules.filter(row=>row.id!==id);return{status:'deleted',id};}
  return{status:'queued'};
 }
 if(path==='/api/securities/enrichment/status')return{items:[]};
 if(path==='/api/securities/enrichment/ai' && method==='POST'){
  qa.marketBodies.push(body);return{request_id:'market',status:'completed',code:'completed',position_scope:body.position_scope,data_types:body.data_types,refresh_policy:body.refresh_policy,ratings_only:body.ratings_only,outcomes:[],summary:{total_candidates:0},progress:{stage:'completed',completed:0,total:0},portfolio_refresh_required:false};
 }
 if(path.startsWith('/api/securities/risk-inputs/retrieval')){
  if(method==='POST'){
   qa.riskBodies.push(body);qa.retrieval={request_id:'risk-qa',status:'running',code:'running',mode:body.mode,refresh_policy:body.refresh_policy,progress:{stage:'ai',completed:0,total:1,current_security:{symbol:'QA'}},coverage:{selected:1,total_candidates:4,remaining:3},outcomes:[]};return structuredClone(qa.retrieval);
  }
  if(path.endsWith('/status'))return{active_job:qa.retrieval,last_job:null};
  return structuredClone(qa.retrieval);
 }
 return{items:[]};
};
state.allPortfolioItems=[];renderAIEnrichment();PortfolioI18n.observe();qa.aiReady=true;
''')
    return page


def choose(command, evaluate, selector, value):
    index = evaluate("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");e.scrollIntoView({block:'center'});e.focus();return Array.from(e.options).findIndex(o=>o.value===" + json.dumps(value) + ");})()")
    assert index >= 0, (selector, value)
    press(command, "Home", "Home", 36)
    for _ in range(index):
        press(command, "ArrowDown", "ArrowDown", 40)


def enter_text(command, evaluate, selector, text):
    evaluate("document.querySelector(" + json.dumps(selector) + ").scrollIntoView({block:'center'});document.querySelector(" + json.dumps(selector) + ").focus();document.querySelector(" + json.dumps(selector) + ").select()")
    command("Input.insertText", {"text": text})


@pytest.mark.parametrize("language", ["en", "he"])
@pytest.mark.parametrize("width", [1440, 1280, 1024, 390])
def test_main_ai_risk_target_and_independent_named_schedule_forms(tmp_path, chromium, language, width):
    command, evaluate = chromium
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000,
                                                   "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": fixture(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.aiReady===true||!!window.qa?.errors?.length")
    assert evaluate("qa.errors") == []
    if width == 390:
        click(command, evaluate, "#navigationToggle")
    click(command, evaluate, "details:has(#enrichMissingData)>summary")
    click(command, evaluate, "#enrichMissingData")
    browser_wait(evaluate, "!$('aiEnrichmentModal').hidden&&$('researchScheduleList').querySelectorAll('article').length===2")
    assert evaluate("qa.riskBodies.length+qa.marketBodies.length+qa.ruleBodies.length") == 0
    choose(command, evaluate, "#aiResearchTarget", "risk_inputs")
    browser_wait(evaluate, "!$('aiRiskResearchPanel').hidden&&!$('aiRiskResearchCheck').disabled")
    choose(command, evaluate, "#aiResearchRefresh", "refresh_existing")
    choose(command, evaluate, "#aiRiskResearchMode", "ai")
    click(command, evaluate, "#aiEnrichmentStartAll")
    browser_wait(evaluate, "qa.riskBodies.length===1")
    assert evaluate("qa.riskBodies[0]") == dict(mode="ai", position_scope="all",
                                               refresh_policy="refresh_existing", language=language)
    assert evaluate("$('aiRiskResearchProgress').hidden") is False
    evaluate("qa.retrieval.status='completed';qa.retrieval.progress={stage:'completed',completed:1,total:1};qa.retrieval.outcomes=[{security_key:'QA|NASDAQ|USD',symbol:'QA',status:'partial',code:'partial_data',available_fields:['issuer_identity'],missing_fields:['fx'],api:{status:'not_attempted'},ai:{status:'completed'},sources:[{url:'https://issuer.example/report',retrieved_at:'2026-11-14T10:00:00Z'}]}]")
    click(command, evaluate, "#aiRiskResearchCheck")
    browser_wait(evaluate, "$('aiRiskResearchResults').children.length===1&&!$('aiRiskResearchCheck').disabled")
    risk_text = evaluate("$('aiRiskResearchPanel').innerText")
    assert "14/11/2026" in risk_text
    if language == "he":
        for label in ["Partially updated", "Available inputs", "Still missing", "AI research", "Completed"]:
            assert label not in risk_text
    choose(command, evaluate, "#aiResearchTarget", "profile")
    choose(command, evaluate, "#aiResearchRefresh", "missing")
    click(command, evaluate, "#aiEnrichmentStart")
    browser_wait(evaluate, "qa.marketBodies.length===1")
    assert evaluate("qa.marketBodies[0].data_types") == ["profile"]
    assert evaluate("qa.marketBodies[0].refresh_policy") == "missing"
    assert evaluate("qa.riskBodies.length") == 1

    click(command, evaluate, "#researchSchedules>summary")
    click(command, evaluate, "#newResearchSchedule")
    browser_wait(evaluate, "!$('researchScheduleForm').hidden")
    assert evaluate("document.activeElement.id") == "researchScheduleName"
    enter_text(command, evaluate, "#researchScheduleName", "QA independent rule")
    click(command, evaluate, '#researchScheduleEditor [data-schedule-field="enabled"]')
    choose(command, evaluate, '#researchScheduleEditor [data-schedule-field="frequency"]', "daily")
    enter_text(command, evaluate, '#researchScheduleEditor [data-schedule-field="hour"]', "23")
    enter_text(command, evaluate, '#researchScheduleEditor [data-schedule-field="minute"]', "59")
    choose(command, evaluate, "#researchScheduleRefresh", "refresh_existing")
    choose(command, evaluate, "#researchScheduleMode", "api")
    choose(command, evaluate, "#researchScheduleSecurityScope", "all")
    first_rule = evaluate("JSON.stringify(qa.rules[0])")
    second_rule = evaluate("JSON.stringify(qa.rules[1])")
    click(command, evaluate, "#saveResearchSchedule")
    browser_wait(evaluate, "qa.rules.length===3&&!$('saveResearchSchedule').disabled")
    body = evaluate("qa.ruleBodies.at(-1).body")
    assert body["name"] == "QA independent rule"
    assert body["data_types"] == ["risk_inputs"] and body["position_scope"] == "all"
    assert body["refresh_policy"] == "refresh_existing" and body["mode"] == "api"
    assert body["enabled"] is True
    assert body["schedule_config"]["frequency"] == "daily"
    assert body["schedule_config"]["hour"] == 23 and body["schedule_config"]["minute"] == 59
    assert evaluate("JSON.stringify(qa.rules[0])") == first_rule
    assert evaluate("JSON.stringify(qa.rules[1])") == second_rule
    assert evaluate("document.activeElement.id") == "saveResearchSchedule"
    # Failed saves keep the edited rule and valid original rules intact.
    enter_text(command, evaluate, "#researchScheduleName", "QA retained draft")
    evaluate("qa.rulesMode='fail'")
    click(command, evaluate, "#saveResearchSchedule")
    browser_wait(evaluate, "!$('saveResearchSchedule').disabled&&$('researchScheduleError').textContent.length>0")
    assert evaluate("$('researchScheduleName').value") == "QA retained draft"
    assert ("Could not save" if language == "en" else "לא ניתן לשמור") in evaluate("$('researchScheduleError').textContent")
    click(command, evaluate, "#saveResearchSchedule")
    browser_wait(evaluate, "qa.rules[2].name==='QA retained draft'")
    click(command, evaluate, '[data-rule-id="added-2"] [data-research-schedule-action="delete"]')
    browser_wait(evaluate, "qa.rules.length===2&&$('researchScheduleForm').hidden")
    assert evaluate("JSON.stringify(qa.rules[0])") == first_rule
    assert evaluate("JSON.stringify(qa.rules[1])") == second_rule
    assert evaluate("qa.confirmations.length") == 1
    assert evaluate("document.activeElement.id") == "newResearchSchedule"
    if language == "he":
        for label in ["Research schedules", "Recheck existing data too", "Public API only", "Run now", "Last scheduled result"]:
            assert label not in evaluate("$('researchSchedules').innerText")
    # Keep stable widths on every visible new input, including hour/minute.
    click(command, evaluate, '[data-rule-id="weekly-risk"] [data-research-schedule-action="edit"]')
    metrics = evaluate("""(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,fields:Array.from(document.querySelectorAll('#aiResearchOptions input,#aiResearchOptions select,#researchScheduleForm input,#researchScheduleForm select')).filter(e=>e.getBoundingClientRect().width>0).map(e=>({id:e.id||e.dataset.scheduleField||e.type,value:e.value,client:e.clientWidth,scroll:e.scrollWidth,left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right}))}))()""")
    assert metrics["width"] == width and metrics["scroll"] <= width
    for field in metrics["fields"]:
        assert field["scroll"] <= field["client"] + 1, field
        assert 0 <= field["left"] <= field["right"] <= width, field
    assert evaluate("qa.errors") == []
    (tmp_path / "ai-schedule-metrics.json").write_text(json.dumps(dict(language=language, width=width,
        metrics=metrics, risk_text=risk_text, saved_body=body), indent=2, ensure_ascii=False))
    (tmp_path / "ai-schedules.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": True})["data"]))


def test_explicit_reload_refreshes_clean_saved_fields_but_dirty_draft_keeps_original_revision(tmp_path, chromium):
    command, evaluate = chromium
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    command("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000,
                                                   "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": fixture(tmp_path, "en").as_uri()})
    browser_wait(evaluate, "window.qa?.aiReady===true||!!window.qa?.errors?.length")
    click(command, evaluate, "details:has(#enrichMissingData)>summary")
    click(command, evaluate, "#enrichMissingData")
    browser_wait(evaluate, "!$('aiEnrichmentModal').hidden&&$('researchScheduleList').querySelectorAll('article').length===2")
    click(command, evaluate, "#researchSchedules>summary")
    click(command, evaluate, '[data-rule-id="weekly-risk"] [data-research-schedule-action="edit"]')
    assert evaluate("$('researchScheduleMode').value") == "api_then_ai"
    # Another editor changes the saved source/scope. A clean explicit Reload
    # must show those values before advancing the revision used for next save.
    evaluate("Object.assign(qa.rules[0],{revision:2,mode:'ai',position_scope:'all',refresh_policy:'refresh_existing'})")
    click(command, evaluate, "#reloadResearchSchedules")
    browser_wait(evaluate, "!$('reloadResearchSchedules').disabled")
    assert evaluate("$('researchScheduleMode').value") == "ai"
    assert evaluate("$('researchScheduleSecurityScope').value") == "all"
    assert evaluate("$('researchScheduleRefresh').value") == "refresh_existing"
    enter_text(command, evaluate, "#researchScheduleName", "Unsaved retained name")
    evaluate("Object.assign(qa.rules[0],{revision:3,mode:'api'})")
    click(command, evaluate, "#reloadResearchSchedules")
    browser_wait(evaluate, "!$('reloadResearchSchedules').disabled")
    assert evaluate("$('researchScheduleName').value") == "Unsaved retained name"
    assert evaluate("$('researchScheduleMode').value") == "ai"
    click(command, evaluate, "#saveResearchSchedule")
    browser_wait(evaluate, "!$('saveResearchSchedule').disabled")
    assert evaluate("qa.ruleBodies.at(-1).body.expected_revision") == 2
    assert evaluate("qa.rules[0].mode") == "api"
    assert "Could not save" in evaluate("$('researchScheduleError').innerText")
    click(command, evaluate, '[data-rule-id="weekly-risk"] [data-research-schedule-action="edit"]')
    assert evaluate("$('researchScheduleMode').value") == "api"
    enter_text(command, evaluate, "#researchScheduleName", "Fresh reviewed name")
    click(command, evaluate, "#saveResearchSchedule")
    browser_wait(evaluate, "qa.rules[0].name==='Fresh reviewed name'")
    assert evaluate("qa.ruleBodies.at(-1).body.expected_revision") == 3
    assert evaluate("qa.rules[0].mode") == "api"
    assert evaluate("qa.errors") == []
