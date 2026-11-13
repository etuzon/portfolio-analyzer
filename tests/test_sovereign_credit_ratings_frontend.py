"""Synthetic browser evidence for sovereign identity, separated currency bases and schedules."""
import base64

import pytest

from test_account_cash_update_qa import browser_wait
from test_ai_enrichment_frontend import ready
from test_native_account_history_qa import chromium


def country_ready(tmp_path, chromium, language="en", width=1440):
    command, evaluate = ready(tmp_path, chromium, language, width)
    evaluate(r'''
qa.countryCalls=[];qa.countryMode='ok';qa.countryAssignment={security_key:'ACME|NASDAQ|USD',country_code:'IL',country_name:'Israel',source_kind:'provider_profile',revision:0,identity_token:'security-country'};qa.countryJobStatus='running';qa.countryProgress={completed:0,total:2,stage:'researching'};
qa.countryContext=(code='IL')=>({country_code:code,country_key:'COUNTRY:'+code,country_name:code==='IL'?'Israel':'United States',identity_token:'country:'+code,manual_revisions:{},ratings:[
 {agency:'sp',currency_basis:'foreign_currency',rating:'A-',status:'rated',scope:'sovereign',scale:'global',term:'long_term',outlook:'negative',watch:'unknown'},
 {agency:'sp',currency_basis:'local_currency',rating:'AA',status:'rated',scope:'sovereign',scale:'global',term:'long_term',outlook:'stable',watch:'unknown'},
 {agency:'fitch',currency_basis:'unknown',rating:'BBB+',status:'rated',scope:'sovereign',scale:'global',term:'long_term',outlook:'unknown',watch:'unknown'}],retrieved_ratings:[],manual_ratings:[],rating_history:[
 {event_id:'country-change',agency:'sp',origin:'public_ai',event_type:'rating_change',changed_fields:['rating'],previous_status:'rated',previous_rating:'BBB+',new_status:'rated',new_rating:'A-',entity_name:'Israel',scope:'sovereign',scale:'global',term:'long_term',currency_basis:'foreign_currency',change_date:'2026-11-12',detected_at:'2026-11-13T09:00:00Z',date_basis:'agency_action',sources:[{url:'https://example.org/sovereign'}]}]});
qa.countryJob=()=>({request_id:'country-job',status:qa.countryJobStatus,country_scope:'accounts',progress:qa.countryProgress,summary:{updated:1,partial:1,unavailable:0},outcomes:[]});
qa.countrySchedule={enabled:false,country_scope:'accounts',timezone:'Asia/Jerusalem',schedule_config:{frequency:'weekly',interval:1,hour:8,minute:0,weekdays:[0],month_days:[1]},next_run:null};
api=async(path,options={})=>{
 qa.countryCalls.push({path,options});
 if(path.startsWith('/api/countries/credit-ratings/countries')){if(qa.countryMode==='inventory-failure')throw Error('private provider');return {items:qa.countryEmpty?[]:qa.countryCatalogAll&&path.includes('country_scope=all')?Array.from(new Set([...REGION_CODES,'PS'])).map(country_code=>({country_code,country_name:countryName(country_code)})):[{country_code:'IL',country_name:'Israel'},{country_code:'US',country_name:'United States'}],country_scope:new URL('https://example.org'+path).searchParams.get('country_scope'),unknown_account_countries:1};}
 if(path==='/api/countries/credit-ratings/status')return {active_job:null,last_job:null};
 if(path==='/api/settings/country-rating-schedule'){
  if(options.method==='PUT'){if(qa.countryMode==='schedule-failure')throw Error('private provider');qa.countrySchedule={...JSON.parse(options.body),next_run:'2026-11-16T06:00:00Z'};}
  return structuredClone(qa.countrySchedule);
 }
 if(path.startsWith('/api/securities/country')){
  if(options.method==='PUT'||options.method==='DELETE'){
   if(qa.countryMode==='assignment-conflict'){const e=Error('private provider');e.status=409;throw e;}
   const payload=options.body?JSON.parse(options.body):{};
   qa.countryAssignment={...qa.countryAssignment,country_code:options.method==='DELETE'?'IL':payload.country_code,source_kind:options.method==='DELETE'?'provider_profile':'manual',revision:qa.countryAssignment.revision+1};
  }
  return structuredClone(qa.countryAssignment);
 }
 if(path.includes('/manual')){
  if(qa.countryMode==='manual-conflict'){const error=Error('private provider');error.status=409;throw error;}
  const payload=options.body?JSON.parse(options.body):Object.fromEntries(new URL('https://example.org'+path).searchParams);
  const context=qa.countryContext(payload.country_code);
  if(options.method!=='DELETE'){const row={...payload,source_kind:'manual',manual_override:true,created_at:'2026-11-13T08:00:00Z',updated_at:'2026-11-13T08:00:00Z',updated_by:'Synthetic operator',scope:'sovereign',scale:'global',term:'long_term'};context.manual_ratings=[row];context.ratings=context.ratings.filter(r=>r.agency!==row.agency||r.currency_basis!==row.currency_basis).concat([row]);context.manual_revisions[`${row.agency}:${row.currency_basis}`]=1;}
  return context;
 }
 if(path.includes('/ai')){
  if(qa.countryMode==='poll-failure'&&options.method!=='POST'){qa.countryMode='ok';throw Error('private provider');}
  return qa.countryJob();
 }
 if(path.startsWith('/api/countries/credit-ratings?')){
  if(qa.countryMode==='read-failure')throw Error('private provider');
  return qa.countryContext(new URL('https://example.org'+path).searchParams.get('country_code'));
 }
 return {items:[]};
};
$('openCountryRatings').click();
''')
    browser_wait(evaluate, "!$('countryRatingsModal').hidden&&!!sovereignCurrentCountry()?.context&&!sovereignCurrentCountry().loading&&sovereignRatingsSession().schedule.loaded&&!sovereignRatingsSession().schedule.pending")
    return command, evaluate


@pytest.mark.parametrize("language,width", [("en", 1440), ("he", 1440), ("en", 390), ("he", 390)])
def test_country_browsing_separates_bases_history_manual_and_read_only(tmp_path, chromium, language, width):
    command, evaluate = country_ready(tmp_path, chromium, language, width)
    assert evaluate("$('sovereignResearchScope').value") == "accounts"
    assert evaluate("$('sovereignCountryAssignment').hidden")
    assert evaluate("qa.countryCalls.filter(c=>c.options.method==='POST').length") == 0
    assert evaluate("$('sovereignCreditRatingsRows').querySelectorAll('tr').length") == 3
    assert evaluate("$('sovereignCreditRatingsRows').textContent.includes('A-')")
    assert not evaluate("$('sovereignCreditRatingsRows').textContent.includes('AA')")
    evaluate("$('sovereignCurrencyBasis').value='local_currency';$('sovereignCurrencyBasis').dispatchEvent(new Event('change',{bubbles:true}))")
    assert evaluate("$('sovereignCreditRatingsRows').textContent.includes('AA')")
    assert not evaluate("$('sovereignCreditRatingsRows').textContent.includes('A-')")
    evaluate("$('sovereignCurrencyBasis').value='unknown';$('sovereignCurrencyBasis').dispatchEvent(new Event('change',{bubbles:true}))")
    assert evaluate("$('sovereignCreditRatingsRows').textContent.includes('BBB+')")
    evaluate("$('sovereignRatingHistory').open=true;$('sovereignRatingHistory').scrollIntoView({block:'center'})")
    text = evaluate("$('sovereignRatingHistoryList').textContent")
    assert "12/11/2026" in text and "13/11/2026" in text
    assert ("Foreign currency" if language == "en" else "מטבע חוץ") in text
    evaluate("$('sovereignCurrencyBasis').value='foreign_currency';$('sovereignCurrencyBasis').dispatchEvent(new Event('change',{bubbles:true}));$('sovereignCreditRatingsRows').querySelector('[data-edit-sovereign=sp]').click()")
    assert evaluate("!$('sovereignManualEditor').hidden&&document.activeElement===$('sovereignManualStatus')")
    evaluate(r'''
$('sovereignManualGrade').value='AAA';$('sovereignManualGrade').dispatchEvent(new Event('change',{bubbles:true}));
$('sovereignManualNotes').value='Synthetic local assessment';$('sovereignManualNotes').dispatchEvent(new Event('input',{bubbles:true}));
$('sovereignManualRatingDate').value='12/11/2026';$('sovereignManualRatingDate').dispatchEvent(new Event('change',{bubbles:true}));
$('saveSovereignManualRating').click();
''')
    browser_wait(evaluate, "!!sovereignCurrentCountry().context.manual_ratings.length&&!sovereignCurrentCountry().manual.saving")
    payload = evaluate("JSON.parse(qa.countryCalls.find(c=>c.path==='/api/countries/credit-ratings/manual').options.body)")
    assert payload["country_code"] == "IL" and payload["currency_basis"] == "foreign_currency"
    assert payload["rating"] == "AAA" and payload["rating_date"] == "2026-11-12"
    assert payload["expected_revision"] == 0 and payload["expected_identity"] == "country:IL"
    evaluate("$('sovereignManualEditor').scrollIntoView({block:'center'});")
    assert evaluate("$('sovereignManualGrade').getBoundingClientRect().width") >= 140
    evaluate("$('sovereignManualNotes').focus({preventScroll:true});qa.manualTop=$('sovereignManualNotes').getBoundingClientRect().top;for(let i=0;i<3;i++)renderSovereignCreditRatings()")
    assert evaluate("document.activeElement===$('sovereignManualNotes')&&Math.abs($('sovereignManualNotes').getBoundingClientRect().top-qa.manualTop)<1")
    geometry = evaluate("(()=>{const p=$('countryRatingsModal').querySelector('.modal-card');return {overflow:document.documentElement.scrollWidth-innerWidth,clipped:p.scrollWidth>p.clientWidth+1}})()")
    assert geometry["overflow"] <= 1 and not geometry["clipped"], geometry
    (tmp_path / f"sovereign-manual-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
    evaluate("$('clearSovereignManualRating').click()")
    browser_wait(evaluate, "!sovereignCurrentCountry().manual")
    assert evaluate("$('sovereignCreditRatingsRows').textContent.includes('A-')")
    evaluate("state.auth.user.role='Viewer';renderSovereignCreditRatings()")
    assert evaluate("$('refreshSovereignRatings').disabled&&$('researchCountryScope').disabled&&$('saveCountrySchedule').disabled")
    assert evaluate("!$('sovereignCreditRatingsRows').querySelector('[data-edit-sovereign]')")
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("language,width", [("en", 1440), ("he", 390)])
def test_schedule_defaults_explicit_scope_failure_draft_and_nonblocking_progress(tmp_path, chromium, language, width):
    command, evaluate = country_ready(tmp_path, chromium, language, width)
    assert not evaluate("$('countryScheduleEditor').querySelector('[data-schedule-field=enabled]').checked")
    assert evaluate("$('countryScheduleScope').value") == "accounts"
    evaluate(r'''
$('countryRatingSchedule').open=true;
$('countryScheduleEditor').querySelector('[data-schedule-field=enabled]').click();
$('countryScheduleScope').value='all';$('countryScheduleScope').dispatchEvent(new Event('change',{bubbles:true}));
$('countryScheduleEditor').querySelector('[data-schedule-field=hour]').value='13';$('countryScheduleEditor').querySelector('[data-schedule-field=hour]').dispatchEvent(new Event('input',{bubbles:true}));
qa.countryMode='schedule-failure';$('saveCountrySchedule').click();
''')
    browser_wait(evaluate, "!sovereignRatingsSession().schedule.pending&&sovereignRatingsSession().schedule.message.includes('Could not save')")
    assert evaluate("$('countryScheduleScope').value") == "all"
    assert evaluate("$('countryScheduleEditor').querySelector('[data-schedule-field=hour]').value") == "13"
    assert "private provider" not in evaluate("$('countryScheduleStatus').textContent")
    evaluate("qa.countryMode='ok';$('saveCountrySchedule').click()")
    browser_wait(evaluate, "!sovereignRatingsSession().schedule.pending&&!sovereignRatingsSession().schedule.dirty")
    saved = evaluate("qa.countrySchedule")
    assert saved["enabled"] and saved["country_scope"] == "all" and saved["schedule_config"]["hour"] == 13
    assert evaluate("$('countryScheduleSaved').textContent.includes('16/11/2026')")
    assert evaluate("qa.countryCalls.filter(c=>c.options.method==='POST').length") == 0
    evaluate("$('researchCountryScope').click()")
    browser_wait(evaluate, "sovereignRatingsSession().global.batch?.pending")
    assert evaluate("JSON.parse(qa.countryCalls.find(c=>c.path==='/api/countries/credit-ratings/ai').options.body)") == {"country_scope": "accounts", "language": language}
    assert evaluate("$('loadingOverlay').hidden&&!$('refresh').disabled")
    evaluate("qa.countryMode='poll-failure';qa.poll()")
    browser_wait(evaluate, "sovereignRatingsSession().global.batch?.resume")
    posts = evaluate("qa.countryCalls.filter(c=>c.options.method==='POST').length")
    evaluate("$('resumeCountryScope').click()")
    browser_wait(evaluate, "sovereignRatingsSession().global.batch.pending")
    assert evaluate("qa.countryCalls.filter(c=>c.options.method==='POST').length") == posts
    evaluate("qa.countryJobStatus='completed';qa.countryProgress.completed=2;qa.poll()")
    browser_wait(evaluate, "!sovereignRatingsSession().global.batch.pending")
    evaluate("$('countryRatingSchedule').scrollIntoView({block:'start'})")
    (tmp_path / f"sovereign-schedule-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
    assert evaluate("qa.errors") == []


def test_empty_accounts_never_expand_to_all_and_auth_change_discards_saved_evidence(tmp_path, chromium):
    _, evaluate = country_ready(tmp_path, chromium)
    evaluate("qa.countryEmpty=true;$('reloadCountryInventory').click()")
    browser_wait(evaluate, "!sovereignRatingsSession().global.loading&&sovereignRatingsSession().global.items.length===0")
    assert evaluate("$('researchCountryScope').disabled&&$('sovereignCreditRatingsContent').hidden")
    assert evaluate("sovereignRatingsSession().global.scope") == "accounts"
    evaluate("state.auth.user={id:'different-user',role:'Viewer'};state.auth.csrfToken='different-session';renderSovereignCreditRatings()")
    assert evaluate("Object.keys(sovereignRatingsSession().countries).length") == 0
    assert evaluate("qa.errors") == []


def test_manual_conflict_preserves_draft_requires_reload_and_keeps_country_identity(tmp_path, chromium):
    _, evaluate = country_ready(tmp_path, chromium)
    evaluate(r'''
$('sovereignCreditRatingsRows').querySelector('[data-edit-sovereign=sp]').click();
$('sovereignManualGrade').value='AAA';$('sovereignManualGrade').dispatchEvent(new Event('change',{bubbles:true}));
$('sovereignManualNotes').value='Keep this draft';$('sovereignManualNotes').dispatchEvent(new Event('input',{bubbles:true}));
qa.countryMode='manual-conflict';$('saveSovereignManualRating').click();
''')
    browser_wait(evaluate, "sovereignCurrentCountry().manual.needsReload&&!sovereignCurrentCountry().manual.saving")
    assert evaluate("$('saveSovereignManualRating').disabled&&!$('reloadSovereignManualRating').hidden")
    assert evaluate("$('sovereignManualGrade').value") == "AAA"
    assert evaluate("$('sovereignManualNotes').value") == "Keep this draft"
    assert "private provider" not in evaluate("$('sovereignManualEditorStatus').textContent")
    evaluate("qa.countryMode='ok';$('reloadSovereignManualRating').click()")
    browser_wait(evaluate, "!sovereignCurrentCountry().manual.needsReload&&!sovereignCurrentCountry().loading")
    assert evaluate("$('sovereignManualGrade').value") == "AAA"
    assert evaluate("$('sovereignManualNotes').value") == "Keep this draft"
    assert not evaluate("$('saveSovereignManualRating').disabled")
    evaluate("qa.countryMode='read-failure';$('reloadSovereignRatings').click()")
    browser_wait(evaluate, "!sovereignCurrentCountry().loading&&sovereignCurrentCountry().message.includes('could not')")
    assert evaluate("$('sovereignCreditRatingsRows').textContent.includes('A-')")
    assert evaluate("$('sovereignManualNotes').value") == "Keep this draft"
    assert evaluate("qa.errors") == []


def test_security_domicile_correction_and_clear_use_cas_and_shared_country_evidence(tmp_path, chromium):
    _, evaluate = country_ready(tmp_path, chromium)
    evaluate(r'''
closeModal($('countryRatingsModal'));
state.securityDetail={symbol:'ACME',stock_market:'NASDAQ',market_key:'NASDAQ',currency:'USD',asset_class:'EQUITY'};
openSovereignCreditRatings(state.securityDetail);openModal('securityDetailModal');
''')
    browser_wait(evaluate, "!sovereignSecurityEntry().loading&&!!sovereignSecurityEntry().country")
    assert evaluate("$('sovereignCreditRatings').parentElement===$('securityDetailModal').querySelector('.modal-card')&&!$('sovereignCountryAssignment').hidden")
    assert evaluate("sovereignCurrentCountry()===sovereignRatingsSession().countries.IL")
    evaluate(r'''
$('sovereignCountryAssignment').open=true;
$('sovereignCountryCode').value='Z';$('sovereignCountryCode').dispatchEvent(new Event('input',{bubbles:true}));$('saveSovereignCountry').click();
''')
    assert not evaluate("qa.countryCalls.some(c=>c.path==='/api/securities/country'&&c.options.method==='PUT')")
    evaluate("$('sovereignCountryCode').value='us';$('sovereignCountryCode').dispatchEvent(new Event('input',{bubbles:true}));$('saveSovereignCountry').click()")
    browser_wait(evaluate, "!sovereignSecurityEntry().saving&&sovereignSecurityEntry().country.country_code==='US'")
    payload = evaluate("JSON.parse(qa.countryCalls.find(c=>c.path==='/api/securities/country'&&c.options.method==='PUT').options.body)")
    assert payload == {"security_key": "ACME|NASDAQ|USD", "country_code": "US", "expected_revision": 0, "expected_identity": "security-country"}
    assert evaluate("!$('clearSovereignCountry').hidden")
    evaluate("qa.countryMode='assignment-conflict';$('clearSovereignCountry').click()")
    browser_wait(evaluate, "!sovereignSecurityEntry().saving&&sovereignSecurityEntry().needsReload")
    assert evaluate("$('saveSovereignCountry').disabled")
    evaluate("qa.countryMode='ok';$('reloadSovereignRatings').click()")
    browser_wait(evaluate, "!sovereignSecurityEntry().loading&&!sovereignSecurityEntry().needsReload")
    evaluate("$('clearSovereignCountry').click()")
    browser_wait(evaluate, "!sovereignSecurityEntry().saving&&sovereignSecurityEntry().country.country_code==='IL'")
    assert evaluate("$('clearSovereignCountry').hidden")
    assert evaluate("qa.errors") == []


def test_all_country_inventory_is_explicit_counted_and_does_not_start_ai(tmp_path, chromium):
    _, evaluate = country_ready(tmp_path, chromium)
    evaluate("qa.countryMode='inventory-failure';qa.countryCatalogAll=true;$('sovereignResearchScope').value='all';$('sovereignResearchScope').dispatchEvent(new Event('change',{bubbles:true}))")
    browser_wait(evaluate, "!sovereignRatingsSession().global.loading&&sovereignRatingsSession().global.message.includes('could not')")
    assert evaluate("$('researchCountryScope').disabled&&$('sovereignCreditRatingsContent').hidden")
    assert evaluate("sovereignRatingsSession().global.items.length") == 0
    evaluate("qa.countryMode='ok';qa.countryBefore=performance.now();$('reloadCountryInventory').click()")
    browser_wait(evaluate, "!sovereignRatingsSession().global.loading&&sovereignRatingsSession().global.items.length===249")
    assert evaluate("$('sovereignSelectedCountry').options.length") == 249
    assert "249" in evaluate("$('countryInventoryStatus').textContent")
    assert not evaluate("$('sovereignScopeHint').hidden")
    assert evaluate("qa.countryCalls.filter(c=>c.options.method==='POST').length") == 0
    evaluate("qa.scopeRenderStart=performance.now();for(let i=0;i<10;i++)renderSovereignGlobal();qa.scopeRenderElapsed=performance.now()-qa.scopeRenderStart")
    assert evaluate("qa.scopeRenderElapsed") < 250
    assert evaluate("qa.errors") == []


def test_remaining_country_retry_preserves_captured_scope_and_country_selection(tmp_path, chromium):
    _, evaluate = country_ready(tmp_path, chromium)
    evaluate(r'''
qa.stopped={request_id:'country-stopped',status:'failed',country_scope:'all',country_codes:['IL'],progress:{completed:0,total:1},summary:{updated:0,partial:0,unavailable:0,not_attempted:1},outcomes:[{country_code:'IL',status:'not_attempted'}]};
acceptSovereignScopeJob(sovereignRatingsSession().global,qa.stopped);
''')
    assert not evaluate("$('retryCountryScope').hidden")
    evaluate("$('retryCountryScope').click()")
    browser_wait(evaluate, "sovereignRatingsSession().global.batch?.pending")
    payload = evaluate("JSON.parse(qa.countryCalls.find(c=>c.path==='/api/countries/credit-ratings/ai').options.body)")
    assert payload == {"country_scope": "all", "country_codes": ["IL"], "resume_request_id": "country-stopped", "language": "en"}
    assert evaluate("$('sovereignResearchScope').value") == "accounts"
    assert evaluate("$('retryCountryScope').hidden")
    assert evaluate("qa.errors") == []


def test_language_change_keeps_drafts_and_closing_returns_to_current_navigation(tmp_path, chromium):
    command, evaluate = country_ready(tmp_path, chromium)
    evaluate(r'''
$('countryRatingSchedule').open=true;
$('countryScheduleEditor').querySelector('[data-schedule-field=enabled]').click();
$('countryScheduleScope').value='all';$('countryScheduleScope').dispatchEvent(new Event('change',{bubbles:true}));
$('countryScheduleEditor').querySelector('[data-schedule-field=hour]').value='17';$('countryScheduleEditor').querySelector('[data-schedule-field=hour]').dispatchEvent(new Event('input',{bubbles:true}));
$('sovereignCreditRatingsRows').querySelector('[data-edit-sovereign=sp]').click();
$('sovereignManualGrade').value='AAA';$('sovereignManualGrade').dispatchEvent(new Event('change',{bubbles:true}));
$('sovereignManualNotes').value='Retain language draft';$('sovereignManualNotes').dispatchEvent(new Event('input',{bubbles:true}));
state.language='he';applyLanguage();
''')
    assert evaluate("$('sovereignManualGrade').value") == "AAA"
    assert evaluate("$('sovereignManualNotes').value") == "Retain language draft"
    assert evaluate("$('countryScheduleScope').value") == "all"
    assert evaluate("$('countryScheduleEditor').querySelector('[data-schedule-field=hour]').value") == "17"
    assert "מדינות" in evaluate("$('countryRatingsTitle').textContent")
    assert "ישראל" in evaluate("$('sovereignSelectedCountry').selectedOptions[0].textContent")
    evaluate("state.language='en';applyLanguage()")
    assert evaluate("$('countryRatingsTitle').textContent") == "Country ratings"
    assert evaluate("$('sovereignManualNotes').value") == "Retain language draft"
    assert evaluate("$('countryScheduleEditor').querySelector('[data-schedule-field=hour]').value") == "17"
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
    browser_wait(evaluate, "$('countryRatingsModal').hidden&&document.activeElement===$('openCountryRatings')")
    assert evaluate("qa.errors") == []
