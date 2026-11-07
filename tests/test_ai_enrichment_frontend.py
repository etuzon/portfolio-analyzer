"""Real frontend interaction with synthetic REST responses; no AI or provider calls."""
import base64

import pytest

from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium


def ready(tmp_path, chromium, language="en", width=1440):
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": cash_browser_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate(r'''
qa.aiPosts=0;qa.aiGets=0;qa.logs=[];qa.apiMode='ok';qa.jobStatus='running';
qa.item={holding:{symbol:'91282CKD2',stock_market:'NYSE',currency:'USD'},missing:['price history'],price_ranges:{}};
qa.other={holding:{symbol:'91282CKD2',stock_market:'TASE',currency:'ILS'},missing:['price history'],price_ranges:{}};
state.allPortfolioItems=[qa.item,qa.other];
qa.outcomes=[{symbol:'91282CKD2',stock_market:'NYSE',currency:'USD',status:'partial',code:'partial_data',missing_fields:['price_history']}];
qa.job=()=>({request_id:'synthetic-job',status:qa.jobStatus,summary:{updated:0,partial:1,unavailable:0,not_attempted:0},outcomes:qa.jobStatus==='running'?[]:qa.outcomes,portfolio_refresh_required:qa.jobStatus==='completed'});
qa.nativeTimeout=window.setTimeout;
window.setTimeout=(callback,delay,...args)=>delay===3000?(qa.poll=callback,999999):qa.nativeTimeout(callback,delay,...args);
api=async(path,options={})=>{
 if(options.method==='POST'){
  qa.aiPosts++;if(qa.apiMode==='lost'){qa.apiMode='ok';throw new Error('synthetic raw provider secret');}
  if(qa.apiMode==='hold')return await new Promise(resolve=>qa.resolve=resolve);
  return qa.job();
 }
 qa.aiGets++;
 if(qa.apiMode==='poll-failure'){qa.apiMode='ok';throw new Error('synthetic raw provider secret');}
 return path.endsWith('/status')?{items:qa.outcomes,active_job:qa.active?qa.job():null}:qa.job();
};
appLog=(event,detail)=>qa.logs.push({event,...detail});appWarn=appLog;
renderAIEnrichment();
''')
    return command, evaluate


@pytest.mark.parametrize("width,language", [(1440, "en"), (1440, "he"), (390, "en"), (390, "he")])
def test_ai_single_request_partial_results_tooltips_permissions_and_narrow_layout(tmp_path, chromium, width, language):
    command, evaluate = ready(tmp_path, chromium, language, width)
    evaluate("$('enrichMissingData').click();$('enrichMissingData').click();")
    browser_wait(evaluate, "state.aiEnrichment.pending===true&&qa.aiPosts===1&&!!qa.poll")
    assert evaluate("$('refresh').disabled") is False
    assert evaluate("$('loadingOverlay').hidden") is True
    assert evaluate("$('enrichMissingData').disabled") is True
    assert evaluate("$('aiEnrichmentStatus').textContent") == (
        "AI is researching open holdings. You can keep using the dashboard." if language == "en"
        else "ה־AI מאתר נתונים להחזקות פתוחות. אפשר להמשיך להשתמש בלוח.")
    evaluate("qa.jobStatus='completed';qa.poll();")
    browser_wait(evaluate, "!state.aiEnrichment.pending&&qa.refreshes===1")
    assert evaluate("qa.aiPosts") == 1 and evaluate("qa.aiGets") == 1
    assert evaluate("qa.logs.some(log=>log.code==='partial_data'&&log.symbol==='91282CKD2')")
    assert evaluate("$('aiEnrichmentDetails').hidden") is False
    assert "partial_data" not in evaluate("$('aiEnrichmentResults').textContent")
    expected = "Some data was found" if language == "en" else "נמצאו חלק מהנתונים"
    assert expected in evaluate("$('aiEnrichmentResults').textContent")
    assert evaluate("aiOutcomeMessage({code:'research_unavailable'})") == (
        "Internet research is unavailable. Configure the search service and try again." if language == "en"
        else "חיפוש באינטרנט אינו זמין. הגדירו את שירות החיפוש ונסו שוב.")
    assert evaluate("aiOutcomeMessage({code:'evidence_rejected'})") == (
        "The source did not provide enough verified information." if language == "en"
        else "המקור לא סיפק מספיק מידע מאומת.")
    assert expected in evaluate("dataGapTooltip(qa.item)")
    assert expected not in evaluate("dataGapTooltip(qa.other)")
    # Later manual/provider corrections take precedence over old partial AI outcomes.
    assert ("All displayed data available" if language == "en" else "כל הנתונים המוצגים זמינים") in evaluate("statusCell({...qa.item,missing:[]})")
    assert "partial" not in evaluate("statusCell({...qa.item,missing:[]})")
    evaluate("$('aiEnrichmentDetails').open=true;$('enrichMissingData').scrollIntoView({block:'center'});")
    geometry = evaluate("(()=>{const b=$('enrichMissingData').getBoundingClientRect(),r=$('aiEnrichmentResults').getBoundingClientRect();return {left:b.left,right:b.right,resultLeft:r.left,resultRight:r.right,overflow:document.documentElement.scrollWidth-innerWidth};})()")
    assert geometry["left"] >= 0 and geometry["right"] <= width, geometry
    assert geometry["resultLeft"] >= 0 and geometry["resultRight"] <= width, geometry
    assert geometry["overflow"] <= 1, geometry
    (tmp_path / f"ai-enrichment-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    evaluate("state.auth.user.role='Viewer';renderCurrentUser();$('enrichMissingData').click();")
    assert evaluate("$('enrichMissingData').disabled") is True
    assert evaluate("$('aiEnrichmentAction').tabIndex") == 0
    assert evaluate("qa.aiPosts") == 1
    permission = "Admin or Operator" if language == "en" else "מנהל מערכת או מפעיל"
    assert permission in evaluate("$('aiEnrichmentAction').getAttribute('aria-label')")
    assert evaluate("qa.errors") == []


def test_poll_interruption_and_limit_resume_same_job_without_another_post(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("$('enrichMissingData').click();")
    browser_wait(evaluate, "qa.aiPosts===1&&!!qa.poll")
    evaluate("qa.apiMode='poll-failure';qa.poll();")
    browser_wait(evaluate, "state.aiEnrichment.resume===true")
    assert "synthetic raw" not in evaluate("$('aiEnrichmentStatus').textContent")
    assert evaluate("$('enrichMissingData').textContent") == "Check AI progress"
    evaluate("$('enrichMissingData').click();")
    browser_wait(evaluate, "state.aiEnrichment.pending===true&&!state.aiEnrichment.resume")
    assert evaluate("qa.aiPosts") == 1
    evaluate("state.aiEnrichment.polls=120;scheduleAIEnrichmentPoll();")
    assert evaluate("state.aiEnrichment.resume&&!state.aiEnrichment.pending")
    assert "taking longer" in evaluate("$('aiEnrichmentStatus').textContent")
    evaluate("qa.jobStatus='completed';$('enrichMissingData').click();")
    browser_wait(evaluate, "!state.aiEnrichment.pending&&!state.aiEnrichment.resume")
    assert evaluate("qa.aiPosts") == 1
    assert evaluate("qa.refreshes") == 1
    assert evaluate("qa.errors") == []


def test_lost_post_response_checks_active_job_and_late_session_result_is_discarded(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("qa.apiMode='lost';$('enrichMissingData').click();")
    browser_wait(evaluate, "state.aiEnrichment.resume===true")
    evaluate("qa.active=true;$('enrichMissingData').click();")
    browser_wait(evaluate, "state.aiEnrichment.pending===true&&!state.aiEnrichment.resume")
    assert evaluate("qa.aiPosts") == 1
    assert evaluate("state.aiEnrichment.job.request_id") == "synthetic-job"
    evaluate("resetAIEnrichment();qa.apiMode='hold';$('enrichMissingData').click();")
    browser_wait(evaluate, "typeof qa.resolve==='function'")
    evaluate("resetAIEnrichment();qa.resolve(qa.job());")
    browser_wait(evaluate, "state.aiEnrichment.job===null&&!state.aiEnrichment.pending")
    assert evaluate("state.aiEnrichment.outcomes.length") == 0
    assert evaluate("qa.errors") == []
