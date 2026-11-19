"""Independent status-observation QA in disposable Chromium.

Production HTML, localization and handlers run against synthetic API receipts
and a virtual clock. These tests do not establish Internet research success or
attach to a signed-in browser, runtime database or private configuration.
"""
import base64

import pytest

from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium
from test_risk_scale_v4_browser_qa import press


def ready(tmp_path, chromium, language="en", width=1440):
    command, evaluate = chromium
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000,
                                                   "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": cash_browser_document(tmp_path, language).as_uri()})
    command("Page.bringToFront")
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate(r'''
qa.nativeTimeout=window.setTimeout;qa.nativeClear=window.clearTimeout;
qa.clock=0;qa.timerId=1000000;qa.timers=new Map();qa.delays=[];
window.setTimeout=(callback,delay,...args)=>{
 if(delay>=1000){const id=++qa.timerId;qa.timers.set(id,{callback:()=>callback(...args),due:qa.clock+delay,delay});qa.delays.push(delay);return id;}
 return qa.nativeTimeout.call(window,callback,delay,...args);
};
window.clearTimeout=id=>qa.timers.delete(id)||qa.nativeClear.call(window,id);
qa.now=Date.now;Date.now=()=>qa.now()+qa.clock;
qa.flush=()=>new Promise(resolve=>qa.nativeTimeout.call(window,resolve,0));
qa.advance=async()=>{
 const entry=[...qa.timers].sort((a,b)=>a[1].due-b[1].due)[0];
 if(!entry)return false;
 qa.timers.delete(entry[0]);qa.clock=entry[1].due;entry[1].callback();await qa.flush();return true;
};
qa.rows=Array.from({length:27},(_,i)=>({security_key:`QA${i}|NYSE|USD`,symbol:`QA${i}`,stock_market:'NYSE',currency:'USD'}));
qa.job={request_id:'independent-27',status:'running',code:'running',data_types:['risk_inputs'],
 progress:{stage:'researching_risk_inputs',completed:8,total:27,current_security:{symbol:'QA8'}},
 risk_inputs:{status:'running',progress:{completed:8,total:27,current_security:{symbol:'QA8'}},
 summary:{total_candidates:27},outcomes:[{...qa.rows[0],status:'partial',code:'partial_data',available_fields:['issuer_identity'],missing_fields:['fx']}]}};
qa.reads=[];qa.writes=[];qa.readMode='ok';qa.riskChanges=0;
document.addEventListener('stress-risk-inputs-changed',()=>qa.riskChanges++);
api=async(path,options={})=>{
 const method=options.method||'GET';
 if(method!=='GET'){qa.writes.push({path,method,body:JSON.parse(options.body||'{}')});return structuredClone(qa.job);}
 if(path.startsWith('/api/settings/'))return{enabled:false,mode:'api_then_ai',security_keys:null,timezone:'UTC',schedule_config:{frequency:'weekly',weekdays:[0],hour:8,minute:0}};
 if(path.includes('/candidates'))return{items:structuredClone(qa.rows)};
 qa.reads.push(path);
 if(qa.readMode==='transient'){qa.readMode='ok';throw new TypeError('synthetic private transport detail');}
 if(qa.readMode==='hold')return await new Promise((resolve,reject)=>{
  qa.resolveRead=resolve;options.signal?.addEventListener('abort',()=>reject(new DOMException('Synthetic request aborted','AbortError')),{once:true});
 });
 if(qa.readMode==='unauthorized'){const error=new Error('synthetic private authentication detail');error.status=401;throw error;}
 if(qa.readMode==='forbidden'){const error=new Error('synthetic private authorization detail');error.status=403;throw error;}
 return path.endsWith('/status')?{active_job:structuredClone(qa.job),last_job:structuredClone(qa.job)}:structuredClone(qa.job);
};
qa.trigger=document.querySelector('[data-open-risk-input-retrieval="run"]')||document.querySelector('[data-open-risk-input-retrieval]');
qa.trigger.click();
''')
    browser_wait(evaluate, "!$('riskRetrievalModal').hidden&&!$('checkRiskRetrieval').disabled")
    assert evaluate("qa.errors") == []
    return command, evaluate


@pytest.mark.parametrize("language,width", [("en", 1440), ("he", 390)])
def test_long_running_job_stays_observable_without_false_progress_or_duplicate_research(
        tmp_path, chromium, language, width):
    command, evaluate = ready(tmp_path, chromium, language, width)
    assert evaluate("$('riskRetrievalProgress').value") == 8
    assert evaluate("$('riskRetrievalProgress').max") == 27
    assert evaluate("$('startRiskRetrieval').disabled") is True
    assert evaluate("qa.writes") == []
    for _ in range(140):
        assert evaluate("qa.advance()"), "An active request must keep scheduling status reads"
    assert evaluate("qa.reads.length") >= 141
    assert evaluate("qa.clock") > 360000
    assert evaluate("qa.delays.some(delay=>delay>=15000)")
    assert evaluate("$('riskRetrievalProgress').value") == 8, "Elapsed time must not imply completed checks"
    status = evaluate("$('riskRetrievalStatus').textContent")
    assert "8" in status and "27" in status and "QA8" in status
    assert "paused" not in status.lower() and "הושהו" not in status
    assert "private" not in status
    assert evaluate("qa.writes") == []
    assert evaluate("$('loadingOverlay').hidden&&!$('refresh').disabled")
    assert evaluate("document.documentElement.scrollWidth-innerWidth") <= 1
    assert evaluate("$('riskRetrievalStatus').getAttribute('aria-live')") == "polite"
    evaluate("$('checkRiskRetrieval').scrollIntoView({block:'center'});$('checkRiskRetrieval').focus()")
    assert evaluate("document.activeElement.id") == "checkRiskRetrieval"
    reads = evaluate("qa.reads.length")
    press(command, "Enter", "Enter", 13, "\r")
    browser_wait(evaluate, f"qa.reads.length>{reads}&&!$('checkRiskRetrieval').disabled")
    assert evaluate("qa.writes") == []
    (tmp_path / f"risk-observation-{language}-{width}.png").write_bytes(base64.b64decode(
        command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
    if language == "he":
        visible = evaluate("$('riskRetrievalModal').innerText")
        for phrase in ["Check progress", "Researching risk inputs", "securities", "automatically", "All missing securities"]:
            assert phrase not in visible


@pytest.mark.parametrize("language", ["en", "he"])
def test_status_failure_retries_same_job_and_terminal_state_releases_controls(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    evaluate("qa.readMode='transient';qa.advance()")
    assert evaluate("$('startRiskRetrieval').disabled") is True
    assert evaluate("$('checkRiskRetrieval').disabled") is False
    assert evaluate("$('riskRetrievalProgress').value") == 8
    notice = evaluate("$('riskRetrievalStatus').textContent")
    assert "private" not in notice
    assert ("retry" if language == "en" else "שוב") in notice.lower()
    before = evaluate("qa.reads.length")
    assert evaluate("qa.advance()"), "A transient status read failure must schedule another observation"
    browser_wait(evaluate, f"qa.reads.length>{before}&&!$('checkRiskRetrieval').disabled")
    assert evaluate("qa.reads.every(path=>path.endsWith('/status')||path.endsWith('/independent-27'))")
    assert evaluate("qa.writes") == []
    evaluate("qa.job.status='completed';qa.job.progress={stage:'completed',completed:27,total:27};qa.job.risk_inputs.status='completed';qa.job.risk_inputs.progress={completed:27,total:27};qa.job.portfolio_refresh_required=true;qa.advance()")
    browser_wait(evaluate, "!$('startRiskRetrieval').disabled")
    assert evaluate("$('riskRetrievalProgress').hidden") is True
    assert evaluate("qa.riskChanges") == 1
    assert evaluate("qa.timers.size") == 0
    evaluate("$('checkRiskRetrieval').click()")
    browser_wait(evaluate, "!$('checkRiskRetrieval').disabled")
    assert evaluate("qa.riskChanges") == 1
    assert evaluate("qa.writes") == []
    assert evaluate("qa.errors") == []


def test_close_and_reopen_pause_reads_and_keep_same_request(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    before = evaluate("qa.reads.length")
    evaluate("closeModal($('riskRetrievalModal'))")
    evaluate("qa.advance()")
    assert evaluate("qa.reads.length") == before
    assert evaluate("qa.timers.size") == 0
    evaluate("qa.trigger.click()")
    browser_wait(evaluate, f"qa.reads.length>{before}&&!$('checkRiskRetrieval').disabled")
    assert evaluate("$('riskRetrievalProgress').value") == 8
    assert evaluate("qa.timers.size") > 0
    assert evaluate("qa.writes") == []
    assert evaluate("qa.errors") == []


def test_hidden_tab_resumes_observation_without_duplicate_request(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    before = evaluate("qa.reads.length")
    evaluate("qa.hidden=true;Object.defineProperty(document,'hidden',{configurable:true,get:()=>qa.hidden});Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>qa.hidden?'hidden':'visible'});document.dispatchEvent(new Event('visibilitychange'))")
    evaluate("qa.advance()")
    assert evaluate("qa.reads.length") == before
    assert evaluate("qa.timers.size") == 0
    evaluate("qa.hidden=false;document.dispatchEvent(new Event('visibilitychange'))")
    browser_wait(evaluate, f"qa.reads.length>{before}&&!$('checkRiskRetrieval').disabled")
    assert evaluate("qa.timers.size") > 0
    assert evaluate("qa.writes") == []


def test_hung_status_read_is_bounded_and_manual_recovery_reads_same_request(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("qa.readMode='hold';$('checkRiskRetrieval').click()")
    browser_wait(evaluate, "typeof qa.resolveRead==='function'")
    assert evaluate("$('checkRiskRetrieval').disabled") is True
    for _ in range(3):
        evaluate("qa.advance()")
        if not evaluate("$('checkRiskRetrieval').disabled"):
            break
    assert evaluate("$('checkRiskRetrieval').disabled") is False
    assert evaluate("$('startRiskRetrieval').disabled") is True
    assert "private" not in evaluate("$('riskRetrievalStatus').textContent")
    evaluate("qa.readMode='ok';$('checkRiskRetrieval').click()")
    browser_wait(evaluate, "!$('checkRiskRetrieval').disabled")
    assert evaluate("$('riskRetrievalProgress').value") == 8
    assert evaluate("qa.writes") == []
    # A timed-out read must not overwrite a later, completed observation.
    evaluate("qa.job.status='completed';qa.job.progress={stage:'completed',completed:27,total:27};qa.job.risk_inputs.status='completed';qa.job.risk_inputs.progress={completed:27,total:27};$('checkRiskRetrieval').click()")
    browser_wait(evaluate, "!$('startRiskRetrieval').disabled")
    evaluate("qa.resolveRead({...qa.job,status:'running'});qa.flush()")
    assert evaluate("$('startRiskRetrieval').disabled") is False
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("mode", ["unauthorized", "forbidden"])
def test_auth_failure_stops_automatic_reads_and_preserves_saved_results(tmp_path, chromium, mode):
    _, evaluate = ready(tmp_path, chromium)
    evaluate(f"qa.readMode={mode!r};qa.advance()")
    before = evaluate("qa.reads.length")
    for _ in range(3):
        evaluate("qa.advance()")
    assert evaluate("qa.reads.length") == before
    assert evaluate("$('riskRetrievalResults').children.length") == 1
    assert evaluate("qa.writes") == []
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("language", ["en", "he"])
def test_dependent_country_stage_uses_matching_counts_and_keeps_risk_evidence(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    evaluate("qa.job.risk_inputs.status='completed';qa.job.risk_inputs.progress={completed:27,total:27};qa.job.progress={stage:'researching_country_ratings',completed:1,total:2,current_security:{symbol:'US'}};qa.advance()")
    status = evaluate("$('riskRetrievalStatus').textContent")
    assert ("1 of 2 countries" if language == "en" else "1 מתוך 2 מדינות") in status
    assert "US" in status
    assert "27" not in status
    assert evaluate("$('riskRetrievalProgress').value") == 1
    assert evaluate("$('riskRetrievalProgress').max") == 2
    assert evaluate("$('riskRetrievalResults').children.length") == 1
    assert evaluate("$('startRiskRetrieval').disabled") is True
    assert evaluate("qa.writes") == []


def test_failed_terminal_job_stops_polling_and_viewer_can_only_observe(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("state.auth.user.role='Viewer';qa.job.status='failed';qa.job.progress.stage='failed';qa.advance()")
    assert evaluate("$('riskRetrievalViewerNote').hidden") is False
    assert evaluate("$('startRiskRetrieval').disabled&&$('retryRiskRetrieval').disabled")
    assert evaluate("$('riskRetrievalMode').disabled&&$('riskRetrievalScope').disabled")
    assert evaluate("$('checkRiskRetrieval').disabled") is False
    assert evaluate("qa.timers.size") == 0
    evaluate("$('startRiskRetrieval').click();$('retryRiskRetrieval').click();$('checkRiskRetrieval').click()")
    browser_wait(evaluate, "!$('checkRiskRetrieval').disabled")
    assert evaluate("qa.writes") == []
    evaluate("state.auth.user.role='Operator';$('checkRiskRetrieval').click()")
    browser_wait(evaluate, "!$('startRiskRetrieval').disabled&&!$('retryRiskRetrieval').disabled")
    assert evaluate("qa.timers.size") == 0


@pytest.mark.parametrize("language", ["en", "he"])
def test_full_scope_copy_and_affected_help_match_observation_behavior(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    option = evaluate("$('riskRetrievalScope').options[0].textContent")
    assert option == ("All missing securities" if language == "en" else "כל ניירות הערך החסרים")
    assert "3" not in option
    help_text = evaluate("[...document.querySelectorAll('p')].find(e=>e.textContent.includes(" + repr(
        "While this window is visible" if language == "en" else "כל עוד החלון גלוי") + ")).textContent")
    if language == "en":
        for phrase in ["returning resumes checks on the same request", "retry automatically", "completed countries", "research finished does not mean all inputs were found"]:
            assert phrase in help_text
    else:
        for phrase in ["אותה בקשה", "ניסיון חוזר אוטומטי", "מדינות שבדיקתן הושלמה", "אינו אומר שכל הנתונים נמצאו"]:
            assert phrase in help_text
        for phrase in ["Research", "Check progress", "automatically"]:
            assert phrase not in help_text


@pytest.mark.parametrize('language', ['en', 'he'])
def test_preparation_and_failed_inventory_do_not_report_zero_of_zero(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    evaluate("qa.job.progress={stage:'capturing_inventory',completed:0,total:0};qa.job.risk_inputs.progress={completed:0,total:0};qa.job.risk_inputs.outcomes=[];qa.job.risk_inputs.coverage={total_candidates:0};$('checkRiskRetrieval').click()")
    browser_wait(evaluate, "!$('checkRiskRetrieval').disabled")
    status = evaluate("$('riskRetrievalStatus').textContent")
    assert ('Preparing research inventory' if language == 'en' else 'מכין את רשימת') in status
    assert '0' not in status
    assert evaluate("$('riskRetrievalCoverage').textContent") == ''
    evaluate("qa.job.status='failed';qa.job.code='check_incomplete';qa.job.failure={stage:'capturing_inventory',code:'check_incomplete',error_type:'OperationalError'};qa.job.progress.stage='failed';$('checkRiskRetrieval').click()")
    browser_wait(evaluate, "!$('checkRiskRetrieval').disabled")
    assert '0' not in evaluate("$('riskRetrievalStatus').textContent")
    failure = evaluate("$('riskRetrievalFailure').textContent")
    assert ('No securities were checked' if language == 'en' else 'לא נבדקו ניירות') in failure
    assert evaluate("$('retryRiskRetrieval').disabled") is False
    assert evaluate('qa.writes') == []
