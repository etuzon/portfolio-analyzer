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
qa.progress={stage:'checking_apis',completed:0,total:0,current_security:null};
qa.item={holding:{symbol:'91282CKD2',stock_market:'NYSE',currency:'USD'},missing:['price history'],price_ranges:{}};
qa.other={holding:{symbol:'91282CKD2',stock_market:'TASE',currency:'ILS'},missing:['price history'],price_ranges:{}};
state.allPortfolioItems=[qa.item,qa.other];
qa.outcomes=[{symbol:'91282CKD2',stock_market:'NYSE',currency:'USD',status:'partial',code:'partial_data',missing_fields:['price_history']}];
qa.job=()=>({request_id:'synthetic-job',status:qa.jobStatus,progress:qa.progress,summary:{updated:0,partial:1,unavailable:0,not_attempted:0},outcomes:qa.jobStatus==='running'?[]:qa.outcomes,portfolio_refresh_required:qa.jobStatus==='completed'});
qa.nativeTimeout=window.setTimeout;
window.setTimeout=(callback,delay,...args)=>delay===3000?(qa.poll=callback,999999):qa.nativeTimeout(callback,delay,...args);
api=async(path,options={})=>{
 if(options.method==='POST'){
  qa.aiPosts++;if(qa.apiMode==='lost'){qa.apiMode='ok';throw new Error('synthetic raw provider secret');}
  if(qa.apiMode==='hold')return await new Promise(resolve=>qa.resolve=resolve);
  return qa.job();
 }
 qa.aiGets++;
 if(qa.apiMode==='expired'){showLogin();const error=new Error('synthetic authentication expired');error.status=401;throw error;}
 if(qa.apiMode==='poll-failure'){qa.apiMode='ok';throw new Error('synthetic raw provider secret');}
 return path.endsWith('/status')?{items:qa.outcomes,active_job:qa.active?qa.job():null}:qa.job();
};
appLog=(event,detail)=>qa.logs.push({event,...detail});appWarn=appLog;
qa.originalAIAction=$('enrichMissingData');ensureHierarchicalNav();ensureHierarchicalNav();
renderAIEnrichment();
''')
    return command, evaluate


@pytest.mark.parametrize("language,width", [("en", 1440), ("he", 390)])
def test_three_bonds_remain_visible_when_only_two_use_ai(tmp_path, chromium, language, width):
    command, evaluate = ready(tmp_path, chromium, language, width)
    evaluate(r'''
qa.bond=(symbol,owner,asset='BOND')=>({holding:{symbol,stock_market:'MANUAL',currency:'USD',
 asset_class:asset,asset_sub_class:'BOND',quantity:1000,market_value:990,cost_basis:1000,
 account:'Synthetic investment'},api_data_route:{owner},missing:['price history'],price_ranges:{}});
state.allPortfolioItems=[qa.bond('88059ESH8','ai'),qa.bond('91282CKD2','api','FIXED_INCOME'),qa.bond('121899CH9','ai'),
 {holding:{symbol:'1101534',stock_market:'TASE',currency:'ILS',asset_class:'EQUITY',quantity:1}}];
qa.outcomes=state.allPortfolioItems.filter(item=>item.api_data_route?.owner==='ai').map(item=>({...item.holding,status:'not_attempted',code:'ai_bridge_missing'}));
state.aiEnrichment.job={request_id:'bridge-offline',status:'failed',code:'ai_bridge_missing',
 progress:{stage:'failed',completed:0,total:2},summary:{not_attempted:2},outcomes:qa.outcomes};
renderAIEnrichment();openModal('aiEnrichmentModal');
''')
    scope = evaluate("$('aiEnrichmentBondScope').textContent")
    assert "3" in scope and "91282CKD2" in scope
    assert ("not the full holdings list" if language == "en" else "אינן רשימת ההחזקות המלאה") in scope
    assert ("remain in Holdings" if language == "en" else "מופיעות בהחזקות") in scope
    assert evaluate("$('aiEnrichmentResults').querySelectorAll('li').length") == 2
    assert "91282CKD2" not in evaluate("$('aiEnrichmentResults').textContent")
    assert evaluate("state.allPortfolioItems.filter(item=>isBondHolding(item.holding)).length") == 3
    assert evaluate("bondsByCurrencyData(state.allPortfolioItems)[0].positions") == 3
    assert evaluate("$('aiEnrichmentStatus').textContent") == (
        "The host AI bridge is not running. An administrator must start it, then start a new request." if language == "en"
        else "שירות ה־AI המארח אינו פועל. מנהל מערכת צריך להפעיל אותו, ואז יש להתחיל בקשה חדשה.")
    assert ("while research continues" if language == "en" else "בזמן האיתור") not in evaluate("$('aiEnrichmentFooterNote').textContent")
    # Separate accounts do not inflate the popup's unique-security count.
    evaluate("state.allPortfolioItems.push({...state.allPortfolioItems[0],holding:{...state.allPortfolioItems[0].holding,account:'Other synthetic account'}});renderAIEnrichment();")
    assert "3" in evaluate("$('aiEnrichmentBondScope').textContent")
    assert evaluate("bondsByCurrencyData(state.allPortfolioItems)[0].positions") == 4
    assert evaluate("document.documentElement.scrollWidth-innerWidth") <= 1
    (tmp_path / f"three-bonds-ai-scope-{language}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("language", ["en", "he"])
def test_access_denied_route_and_source_failure_need_explicit_new_request(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    evaluate(r'''
qa.item.api_data_route={owner:'ai',provider:'finnhub',reason:'api_access_denied',coverage:'access_denied',configured:false};
qa.oldOutcome={...qa.item.holding,status:'unavailable',code:'source_read_failed',available_fields:[],missing_fields:['prices']};
state.aiEnrichment.job={request_id:'completed-before-query-fix',status:'completed',code:'data_unavailable',
  progress:{stage:'completed',completed:1,total:1},summary:{updated:0,partial:0,unavailable:1,not_attempted:0},outcomes:[qa.oldOutcome]};
state.aiEnrichment.outcomes=[qa.oldOutcome];state.aiEnrichment.pending=false;
renderAIEnrichment();renderAIEnrichment();
''')
    assert evaluate("qa.aiPosts") == 0
    hint = evaluate("securityDataRouteHint(qa.item)")
    assert ("API access denied" if language == "en" else "הגישה ל־API נדחתה") in hint
    message = evaluate("aiOutcomeMessage({code:'source_read_failed'})")
    assert ("could not be read" if language == "en" else "לא ניתן") in message
    assert "source_read_failed" not in evaluate("$('aiEnrichmentResults').textContent")
    evaluate("$('enrichMissingData').click();")
    assert evaluate("qa.aiPosts") == 0
    assert evaluate("$('aiEnrichmentModal').hidden") is False
    evaluate("$('aiEnrichmentStart').click();")
    browser_wait(evaluate, "qa.aiPosts===1&&state.aiEnrichment.pending===true")
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("width,language", [(1440, "en"), (1440, "he"), (390, "en"), (390, "he")])
def test_ai_single_request_partial_results_tooltips_permissions_and_narrow_layout(tmp_path, chromium, width, language):
    command, evaluate = ready(tmp_path, chromium, language, width)
    assert evaluate("$('enrichMissingData')===qa.originalAIAction&&document.querySelectorAll('#enrichMissingData').length===1")
    assert evaluate("$('enrichMissingData').closest('.nav-menu')===document.querySelector('.nav-menu')")
    assert evaluate("$('enrichMissingData').parentElement.lastElementChild===$('enrichMissingData')")
    assert evaluate("!document.querySelector('.header-status').contains($('enrichMissingData'))")
    evaluate("if(matchMedia('(max-width:760px)').matches)setMobileNavigation(true);$('enrichMissingData').closest('details').open=true;$('enrichMissingData').focus();")
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
    evaluate("$('enrichMissingData').click();")
    browser_wait(evaluate, "state.aiEnrichment.pending===true&&qa.aiPosts===1&&!!qa.poll")
    assert evaluate("$('refresh').disabled") is False
    assert evaluate("$('loadingOverlay').hidden") is True
    assert evaluate("$('aiEnrichmentModal').hidden") is False
    assert evaluate("$('enrichMissingData').disabled") is False
    assert evaluate("$('aiEnrichmentStart').disabled") is True
    assert evaluate("$('aiEnrichmentProgress').hasAttribute('value')") is False
    assert evaluate("$('aiEnrichmentPhase').textContent") == ("Checking AI eligibility" if language == "en" else "בודק התאמה לאיתור בעזרת AI")
    assert evaluate("$('aiEnrichmentStatus').textContent") == (
        "Researching eligible holdings. You can keep using the dashboard." if language == "en"
        else "מאתר נתונים להחזקות מתאימות. אפשר להמשיך להשתמש בלוח.")
    # Closing and reopening keeps the running job, its timer and the original menu listener.
    evaluate("closeModal($('aiEnrichmentModal'));ensureHierarchicalNav();$('enrichMissingData').click();")
    assert evaluate("qa.aiPosts") == 1
    evaluate("qa.progress={stage:'researching',completed:1,total:3,current_security:qa.item.holding};qa.poll();")
    browser_wait(evaluate, "$('aiEnrichmentProgress').value===1&&$('aiEnrichmentProgress').max===3")
    assert "91282CKD2" in evaluate("$('aiEnrichmentCurrentSecurity').textContent")
    assert ("Checked 1 of 3" if language == "en" else "נבדקו 1 מתוך 3") in evaluate("$('aiEnrichmentCounts').textContent")
    assert "%" not in evaluate("$('aiEnrichmentCounts').textContent")
    (tmp_path / f"ai-enrichment-running-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    evaluate("qa.jobStatus='completed';qa.progress={stage:'completed',completed:1,total:1,current_security:null};qa.poll();")
    browser_wait(evaluate, "!state.aiEnrichment.pending&&qa.refreshes===1")
    assert evaluate("qa.aiPosts") == 1 and evaluate("qa.aiGets") == 2
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
    assert evaluate("aiOutcomeMessage({code:'provider_timeout'})") == (
        "The source check took longer than expected. Saved data is retained; use Refresh or try again later." if language == "en"
        else "בדיקת המקור נמשכה זמן רב מהצפוי. הנתונים השמורים נשמרים; השתמשו ברענון או נסו שוב מאוחר יותר.")
    assert evaluate("aiOutcomeMessage({code:'bond_reference_only'})") == (
        "API bond reference data is available. Portfolio valuation still requires a defined quantity/face-value convention." if language == "en"
        else "נתוני ייחוס לאג״ח זמינים מה־API. חישוב שווי ההחזקה עדיין דורש הגדרה של מוסכמת הכמות והערך הנקוב.")
    assert expected in evaluate("dataGapTooltip(qa.item)")
    assert expected not in evaluate("dataGapTooltip(qa.other)")
    # Later manual/provider corrections take precedence over old partial AI outcomes.
    assert ("All displayed data available" if language == "en" else "כל הנתונים המוצגים זמינים") in evaluate("statusCell({...qa.item,missing:[]})")
    assert "partial" not in evaluate("statusCell({...qa.item,missing:[]})")
    evaluate("$('aiEnrichmentTitle').scrollIntoView({block:'start'});")
    geometry = evaluate("(()=>{const b=$('aiEnrichmentModal').querySelector('.modal-card').getBoundingClientRect(),r=$('aiEnrichmentResults').getBoundingClientRect();return {left:b.left,right:b.right,resultLeft:r.left,resultRight:r.right,overflow:document.documentElement.scrollWidth-innerWidth};})()")
    assert geometry["left"] >= 0 and geometry["right"] <= width, geometry
    assert geometry["resultLeft"] >= 0 and geometry["resultRight"] <= width, geometry
    assert geometry["overflow"] <= 1, geometry
    (tmp_path / f"ai-enrichment-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    evaluate("closeModal($('aiEnrichmentModal'));state.auth.user.role='Viewer';renderCurrentUser();ensureHierarchicalNav();$('enrichMissingData').click();$('aiEnrichmentStart').click();")
    assert evaluate("$('enrichMissingData').disabled") is False
    assert evaluate("$('aiEnrichmentModal').hidden") is False
    assert evaluate("$('aiEnrichmentStart').disabled") is True
    assert evaluate("$('aiEnrichmentAction').tabIndex") == 0
    assert evaluate("qa.aiPosts") == 1
    permission = "Admin or Operator" if language == "en" else "מנהל מערכת או מפעיל"
    assert permission in evaluate("$('aiEnrichmentAction').getAttribute('aria-label')")
    # Reopening a completed job remains read-only until a new request is chosen explicitly.
    evaluate("state.auth.user.role='Operator';renderCurrentUser();closeModal($('aiEnrichmentModal'));$('enrichMissingData').click();")
    assert evaluate("qa.aiPosts") == 1
    evaluate("$('aiEnrichmentStart').click();")
    browser_wait(evaluate, "qa.aiPosts===2")
    assert evaluate("qa.errors") == []


def test_poll_interruption_and_limit_resume_same_job_without_another_post(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("$('enrichMissingData').click();")
    browser_wait(evaluate, "qa.aiPosts===1&&!!qa.poll")
    evaluate("qa.apiMode='poll-failure';qa.poll();")
    browser_wait(evaluate, "state.aiEnrichment.resume===true")
    assert "synthetic raw" not in evaluate("$('aiEnrichmentStatus').textContent")
    assert evaluate("$('aiEnrichmentStart').textContent") == "Check AI progress"
    evaluate("$('aiEnrichmentStart').click();")
    browser_wait(evaluate, "state.aiEnrichment.pending===true&&!state.aiEnrichment.resume")
    assert evaluate("qa.aiPosts") == 1
    evaluate("state.aiEnrichment.polls=120;scheduleAIEnrichmentPoll();")
    assert evaluate("state.aiEnrichment.resume&&!state.aiEnrichment.pending")
    assert "taking longer" in evaluate("$('aiEnrichmentStatus').textContent")
    evaluate("qa.jobStatus='completed';$('aiEnrichmentStart').click();")
    browser_wait(evaluate, "!state.aiEnrichment.pending&&!state.aiEnrichment.resume")
    assert evaluate("qa.aiPosts") == 1
    assert evaluate("qa.refreshes") == 1
    assert evaluate("qa.errors") == []


def test_lost_post_response_checks_active_job_and_late_session_result_is_discarded(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("qa.apiMode='lost';$('enrichMissingData').click();")
    browser_wait(evaluate, "state.aiEnrichment.resume===true")
    evaluate("qa.active=true;$('aiEnrichmentStart').click();")
    browser_wait(evaluate, "state.aiEnrichment.pending===true&&!state.aiEnrichment.resume")
    assert evaluate("qa.aiPosts") == 1
    assert evaluate("state.aiEnrichment.job.request_id") == "synthetic-job"
    evaluate("resetAIEnrichment();qa.apiMode='hold';$('enrichMissingData').click();")
    browser_wait(evaluate, "typeof qa.resolve==='function'")
    evaluate("resetAIEnrichment();qa.resolve(qa.job());")
    browser_wait(evaluate, "state.aiEnrichment.job===null&&!state.aiEnrichment.pending")
    assert evaluate("state.aiEnrichment.outcomes.length") == 0
    assert evaluate("qa.errors") == []


def test_language_rebuild_retains_opener_focus_and_expired_session_clears_popup(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("$('enrichMissingData').closest('details').open=true;$('enrichMissingData').focus();state.language='he';applyLanguage();")
    assert evaluate("$('enrichMissingData')===qa.originalAIAction")
    assert evaluate("document.querySelectorAll('#enrichMissingData').length") == 1
    assert evaluate("document.activeElement.id") == "enrichMissingData"
    assert evaluate("$('enrichMissingData').textContent") == "איתור נתונים חסרים בעזרת AI"
    evaluate("$('enrichMissingData').click();")
    browser_wait(evaluate, "qa.aiPosts===1&&!!qa.poll")
    evaluate("qa.apiMode='expired';qa.poll();")
    browser_wait(evaluate, "currentUser()===null&&$('aiEnrichmentModal').hidden")
    assert evaluate("state.aiEnrichment.job") is None
    assert evaluate("state.aiEnrichment.outcomes.length") == 0
    assert evaluate("$('enrichMissingData').disabled") is True
    assert evaluate("qa.aiPosts") == 1
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("language", ["en", "he"])
def test_api_routes_exclude_old_ai_outcomes_and_explain_setup_retry_and_empty_batch(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    evaluate('''
qa.item.api_data_route={owner:'api',provider:'finnhub',configured:false,coverage:'candidate',reason:'configuration_required'};
qa.other.api_data_route={owner:'ai',configured:false,coverage:'unsupported',reason:'no_price_reference_api'};
state.aiEnrichment.outcomes=qa.outcomes;
renderAIEnrichment();
''')
    assert evaluate("$('aiEnrichmentDetails').hidden") is True
    hint = evaluate("dataGapTooltip(qa.item)")
    assert ("API configuration required" if language == "en" else "נדרשת הגדרת API") in hint
    assert "Finnhub" in hint
    assert ("Last AI research" if language == "en" else "איתור AI אחרון") not in hint
    assert evaluate("aiOutcomeFor(qa.item)===undefined")
    evaluate("qa.item.api_data_route={owner:'api',provider:'finnhub',configured:true,coverage:'candidate',reason:'provider_unavailable'};")
    assert ("API update unavailable" if language == "en" else "עדכון ה־API אינו זמין") in evaluate("securityDataRouteHint(qa.item)")
    evaluate("qa.item.api_data_route.reason='api_coverage_unsupported';qa.item.api_data_route.coverage='unsupported';")
    assert ("API coverage unavailable" if language == "en" else "כיסוי ה־API אינו זמין") in evaluate("securityDataRouteHint(qa.item)")
    evaluate("qa.item.api_data_route.reason='api_coverage_verified';qa.item.api_data_route.coverage='verified';")
    assert ("Automatic API refresh route" if language == "en" else "מסלול עדכון API אוטומטי") in evaluate("securityDataRouteHint(qa.item)")
    # Current and saved API outcomes are removed after routing changes, even when a prior request listed them.
    evaluate("state.aiEnrichment.job={...qa.job(),status:'completed',outcomes:qa.outcomes};renderAIEnrichment();")
    assert evaluate("$('aiEnrichmentResults').children.length") == 0
    evaluate("qa.other.api_data_route.owner='ai';state.aiEnrichment.job.outcomes=[{...qa.outcomes[0],stock_market:'TASE',currency:'ILS'}];renderAIEnrichment();")
    assert evaluate("$('aiEnrichmentResults').children.length") == 1
    assert ("No supported price/reference API route" if language == "en" else "אין מסלול API נתמך למחירים או לנתוני ייחוס") in evaluate("securityDataRouteHint(qa.other)")
    assert evaluate("aiOutcomeMessage({code:'api_managed'})") == (
        "This security uses automatic API updates. Use dashboard Refresh; AI research is not used." if language == "en" else
        "נייר זה משתמש בעדכוני API אוטומטיים. השתמשו ברענון הלוח; לא מופעל חיפוש AI.")
    evaluate("state.aiEnrichment.job={...qa.job(),status:'completed',code:'nothing_missing',outcomes:[],progress:{stage:'completed',completed:0,total:0}};renderAIEnrichment();$('enrichMissingData').click();closeModal($('aiEnrichmentModal'));$('enrichMissingData').click();")
    assert evaluate("qa.aiPosts") == 0
    assert evaluate("$('aiEnrichmentSummary').hidden&&$('aiEnrichmentEmpty').hidden&&$('aiEnrichmentProgress').hidden")
    assert evaluate("$('aiEnrichmentPhase').textContent") == ("No AI research needed" if language == "en" else "אין צורך בחיפוש AI")
    assert ("normal dashboard update flow" if language == "en" else "בעדכוני לוח הבקרה הרגילים") in evaluate("$('aiEnrichmentStatus').textContent")
    assert evaluate("qa.errors") == []
