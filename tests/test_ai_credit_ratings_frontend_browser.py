"""Full static UI with synthetic responses only; no real provider or AI work."""
import base64

import pytest

from test_account_cash_update_qa import browser_wait
from test_ai_enrichment_frontend import ready
from test_native_account_history_qa import chromium


@pytest.mark.parametrize("language,width", [("en", 1440), ("he", 1440), ("en", 390), ("he", 390)])
def test_general_action_covers_all_api_priced_stocks_and_resumes_remaining_work(tmp_path, chromium, language, width):
    command, evaluate = ready(tmp_path, chromium, language, width)
    evaluate(r'''
state.allPortfolioItems=Array.from({length:25},(_,index)=>({holding:{symbol:`C${index}`,stock_market:'NASDAQ',currency:'USD',asset_class:'EQUITY'},api_data_route:{owner:'api'},missing:[]}));
state.allPortfolioItems.push({...state.allPortfolioItems[0],holding:{...state.allPortfolioItems[0].holding,account_id:'second-account'}});
qa.credit={status:'running',progress:{completed:0,total:25},summary:{total_candidates:25,updated:0,partial:0,unavailable:0,not_attempted:25},outcomes:state.allPortfolioItems.slice(0,25).map(item=>({...item.holding,security_key:aiSecurityKey(item.holding),status:'pending',code:'pending',attempted:false,verified_agencies:[],agency_statuses:{moodys:'not_checked',sp:'not_checked',fitch:'not_checked'}}))};
qa.originalJob=qa.job;qa.job=()=>({...qa.originalJob(),position_scope:'all',code:'nothing_missing',portfolio_refresh_required:false,credit_ratings:qa.credit});
qa.progress={stage:'researching_ratings',completed:0,total:25,current_security:null};
$('enrichMissingData').click();
''')
    assert evaluate("qa.aiPosts") == 0
    assert ("API-priced stocks" if language == "en" else "כולל מניות שמחירן") in evaluate("$('aiEnrichmentScope').textContent")
    evaluate("$('aiEnrichmentStartAll').click()")
    browser_wait(evaluate, "state.aiEnrichment.pending&&!!qa.poll&&!$('aiCreditRatings').hidden")
    assert evaluate("qa.aiBodies") == [{"position_scope": "all", "ratings_only": False}]
    assert evaluate("$('aiCreditRatingsResults').children.length") == 25
    assert "C24" in evaluate("$('aiCreditRatingsResults').textContent")
    assert evaluate("$('loadingOverlay').hidden&&!$('refresh').disabled")
    assert ("public-source company ratings" if language == "en" else "דירוגי חברות במקורות ציבוריים") in evaluate("$('aiEnrichmentPhase').textContent")
    assert evaluate("$('aiEnrichmentEmpty').hidden"), "no market-data work must not hide or deny rating work"
    evaluate(r'''
qa.credit.progress={completed:7,total:25,current_security:qa.credit.outcomes[7]};qa.credit.summary={total_candidates:25,updated:3,partial:2,unavailable:2,not_attempted:18};
for(let index=0;index<7;index++)Object.assign(qa.credit.outcomes[index],{status:index<3?'updated':index<5?'partial':'unavailable',attempted:true,verified_agencies:index<3?['moodys','sp','fitch']:index<5?['sp']:[],agency_statuses:{moodys:index<3?'rated':'unavailable',sp:index<5?'rated':'not_found',fitch:index<3?'rated':'not_checked'}});
qa.poll();
''')
    browser_wait(evaluate, "$('aiCreditRatingsCounts').textContent.includes('7')")
    text = evaluate("$('aiCreditRatingsResults').textContent")
    assert ("Checked; no verified rating evidence" if language == "en" else "נבדק; אין אסמכתאות דירוג מאומתות") in text
    assert ("Supported evidence from 1 of 3 agencies" if language == "en" else "אסמכתאות נתמכות מ־1 מתוך 3 חברות דירוג") in text
    assert "Stable" not in text and "No watch" not in text
    evaluate("$('aiCreditRatings').scrollIntoView({block:'start'});")
    geometry = evaluate("(()=>{const n=$('aiCreditRatings'),r=n.getBoundingClientRect();return {width:r.width,overflow:document.documentElement.scrollWidth-innerWidth,clipped:n.scrollWidth>n.clientWidth+1}})()")
    assert geometry["overflow"] <= 1 and not geometry["clipped"], geometry
    (tmp_path / f"all-company-rating-progress-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
    evaluate(r'''
qa.originalApi=api;api=async(path,options={})=>path.startsWith('/api/securities/credit-ratings?')?{schema_version:'credit-ratings-v1',security_key:'C7|NASDAQ|USD',symbol:'C7',stock_market:'NASDAQ',currency:'USD',ratings:[],rating_history:[]}:qa.originalApi(path,options);
loadSecurityDetail=async()=>{};
qa.returnButton=$('aiCreditRatingsResults').querySelector('[data-ai-credit-key="C7|NASDAQ|USD"]');qa.returnButton.click();
''')
    browser_wait(evaluate, "!$('securityDetailModal').hidden&&state.securityDetail.symbol==='C7'")
    evaluate("qa.credit.outcomes[7].status='partial';qa.credit.outcomes[7].verified_agencies=['sp'];qa.credit.progress.completed=8;qa.poll()")
    browser_wait(evaluate, "state.aiEnrichment.job.credit_ratings.progress.completed===8")
    assert evaluate("qa.returnButton.isConnected"), "background progress preserves the source button for modal focus return"
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
    evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
    assert evaluate("document.activeElement===qa.returnButton&&!$('aiEnrichmentModal').inert")
    evaluate("qa.jobStatus='failed';qa.progress.stage='failed';qa.credit.status='failed';qa.credit.outcomes.slice(7).forEach(outcome=>outcome.status='not_attempted');qa.poll();")
    browser_wait(evaluate, "!state.aiEnrichment.pending&&!$('aiEnrichmentRetryRatings').hidden")
    evaluate("$('aiEnrichmentRetryRatings').click()")
    browser_wait(evaluate, "qa.aiPosts===2")
    assert evaluate("qa.aiBodies[1]") == {"position_scope": "all", "ratings_only": False, "resume_request_id": "synthetic-job"}
    evaluate("state.auth.user.role='Viewer';renderAIEnrichment()")
    assert evaluate("$('aiEnrichmentRetryRatings').disabled")
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("language,width", [("en", 1440), ("he", 390)])
def test_ratings_only_is_explicit_locked_and_preserved_by_progress_and_remaining_retry(tmp_path, chromium, language, width):
    command, evaluate = ready(tmp_path, chromium, language, width)
    evaluate(r'''
qa.item={holding:{symbol:'FDUS',stock_market:'NASDAQ',currency:'USD',asset_class:'EQUITY'},api_data_route:{owner:'api'},missing:[]};state.allPortfolioItems=[qa.item];
qa.credit={status:'running',progress:{completed:0,total:1},summary:{total_candidates:1,updated:0,partial:0,unavailable:0,not_attempted:1},outcomes:[{...qa.item.holding,security_key:'FDUS|NASDAQ|USD',status:'pending',attempted:false,verified_agencies:[],agency_statuses:{moodys:'not_checked',sp:'not_checked',fitch:'not_checked'}}]};
qa.originalJob=qa.job;qa.job=()=>({...qa.originalJob(),position_scope:'open',ratings_only:qa.aiBodies.at(-1)?.ratings_only||false,portfolio_refresh_required:false,outcomes:[],credit_ratings:qa.credit});
state.aiEnrichment.job={request_id:'previous-market',status:'completed',summary:{updated:1},outcomes:[{symbol:'OLD',stock_market:'NASDAQ',currency:'USD',status:'updated',code:'data_found'}]};
renderAIEnrichment();$('enrichMissingData').click();
''')
    assert evaluate("$('aiEnrichmentRatingsOnly').checked") is False
    assert evaluate("$('aiEnrichmentResults').children.length") == 1
    evaluate("$('aiEnrichmentRatingsOnly').click()")
    assert evaluate("$('aiEnrichmentRatingsOnly').checked") is True
    assert evaluate("$('aiEnrichmentDetails').hidden&&$('aiEnrichmentSummary').hidden&&$('aiEnrichmentEmpty').hidden")
    assert evaluate("qa.aiPosts") == 0
    evaluate("$('aiEnrichmentStart').click()")
    browser_wait(evaluate, "state.aiEnrichment.pending&&!!qa.poll")
    assert evaluate("qa.aiBodies") == [{"position_scope": "open", "ratings_only": True}]
    assert evaluate("$('aiEnrichmentRatingsOnly').disabled&&$('aiEnrichmentRatingsOnly').checked")
    assert evaluate("$('aiEnrichmentDetails').hidden&&$('aiEnrichmentSummary').hidden&&$('aiEnrichmentEmpty').hidden")
    assert evaluate("$('aiCreditRatingsResults').children.length") == 1
    evaluate("qa.apiMode='poll-failure';qa.poll()")
    browser_wait(evaluate, "state.aiEnrichment.resume")
    assert evaluate("$('aiEnrichmentRatingsOnly').disabled")
    evaluate("$('aiEnrichmentResume').click()")
    browser_wait(evaluate, "state.aiEnrichment.pending&&!state.aiEnrichment.resume")
    assert evaluate("qa.aiPosts") == 1
    assert evaluate("$('aiEnrichmentRatingsOnly').checked")
    evaluate("qa.jobStatus='failed';qa.credit.status='failed';qa.credit.outcomes[0].status='not_attempted';qa.poll()")
    browser_wait(evaluate, "!state.aiEnrichment.pending&&!$('aiEnrichmentRetryRatings').hidden")
    status_text = evaluate("$('aiEnrichmentStatus').textContent")
    assert ("Add manually" if language == "en" else "בהוספה ידנית") in status_text
    assert "Prices" not in status_text and "במחירים" not in status_text
    evaluate("$('aiEnrichmentRatingsOnly').click();$('aiEnrichmentRetryRatings').click()")
    browser_wait(evaluate, "qa.aiPosts===2")
    assert evaluate("qa.aiBodies[1]") == {"position_scope": "open", "ratings_only": True, "resume_request_id": "synthetic-job"}
    assert evaluate("$('aiEnrichmentRatingsOnly').checked")
    evaluate("$('aiEnrichmentModal').querySelector('.modal-header').scrollIntoView({block:'start'})")
    (tmp_path / f"ratings-only-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("language,width", [("en", 1865), ("he", 1865), ("en", 1440), ("he", 390)])
def test_history_uses_native_notation_dates_and_distinct_manual_and_forward_events(tmp_path, chromium, language, width):
    command, evaluate = ready(tmp_path, chromium, language, width)
    evaluate(r'''
qa.ratingEvent={event_id:'source-change',agency:'sp',origin:'public_ai',event_type:'rating_change',changed_fields:['rating'],previous_status:'rated',previous_rating:'BBB+',new_status:'rated',new_rating:'AA-',entity_name:'Example Company',scope:'issuer',scale:'global',term:'long_term',rating_type:'issuer',change_date:'2026-11-12',detected_at:'2026-11-13T09:00:00Z',date_basis:'agency_action',sources:[{url:'https://example.org/rating-action'}]};
qa.history=[qa.ratingEvent,{...qa.ratingEvent,event_id:'signal',event_type:'outlook_change',changed_fields:['outlook'],previous_rating:'AA-',new_rating:'AA-',previous_outlook:'stable',new_outlook:'negative',date_basis:'detected',change_date:null},{...qa.ratingEvent,event_id:'manual',origin:'manual',event_type:'manual_updated',actor:'Test operator',date_basis:'manual_entry',change_date:null}];
state.securityDetail={symbol:'ACME',stock_market:'NASDAQ',market_key:'NASDAQ',currency:'USD',asset_class:'EQUITY'};
const entry=creditRatingsEntry();entry.context={security_key:'ACME|NASDAQ|USD',symbol:'ACME',stock_market:'NASDAQ',currency:'USD',issuer_name:'Example Company',ratings:[{agency:'sp',status:'rated',rating:'AA-',scope:'issuer',scale:'global',term:'long_term',outlook:'negative',watch:'unknown',latest_change:qa.ratingEvent}],rating_history:qa.history};
renderSecurityCreditRatings();openModal('securityDetailModal');
''')
    evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
    evaluate("$('securityCreditRatingHistory').querySelector('summary').focus()")
    assert evaluate("document.activeElement===$('securityCreditRatingHistory').querySelector('summary')")
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
    assert evaluate("$('securityCreditRatingHistory').open")
    text = evaluate("$('securityCreditRatingHistoryList').textContent")
    assert "12/11/2026" in text and "13/11/2026" in text
    assert ("Agency action date" if language == "en" else "תאריך פעולת חברת הדירוג") in text
    assert ("Detected at" if language == "en" else "זוהה בתאריך") in text
    assert ("Manual entry updated" if language == "en" else "עודכנה רשומה ידנית") in text
    assert ("Outlook changed" if language == "en" else "תחזית הדירוג השתנתה") in text
    assert evaluate("Array.from($('securityCreditRatingHistoryList').querySelectorAll('.credit-history-transition')).every(n=>getComputedStyle(n).direction==='ltr')")
    assert evaluate("$('securityCreditRatingHistoryList').querySelector('[data-credit-history-event=signal]').querySelector('.credit-history-transition').textContent.replace(/\\s+/g,' ').trim()") == ("Stable → to Negative" if language == "en" else "יציב → אל שלילי")
    evaluate("$('securityCreditRatingHistory').scrollIntoView({block:'start'})")
    assert evaluate("document.documentElement.scrollWidth-innerWidth") <= 1
    (tmp_path / f"rating-history-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
    evaluate(r'''
closeModal($('securityDetailModal'));
const holding={symbol:'ACME',name:'Example Company',stock_market:'NASDAQ',platform:'NASDAQ',currency:'USD',asset_class:'EQUITY',account:'Sample account',account_id:'sample',quantity:1,market_value:10,cost_basis:9};
state.items=state.allPortfolioItems=[{holding,missing:[],price_ranges:{},moving_averages:{},support_resistance:{},api_data_route:{owner:'api'}}];
const cache=holdingsCreditRatingsSession();cache.portfolioVersion=state.portfolioLoadVersion||0;cache.requested.add('ACME|NASDAQ|USD');
const summary=holdingsCreditRatingsEntry('ACME|NASDAQ|USD');summary.state='ready';summary.context={security_key:'ACME|NASDAQ|USD',summary_only:true,ratings:[
 {agency:'moodys',status:'rated',rating:'Aa2',outlook:'stable',watch:'unknown',latest_change:{...qa.ratingEvent,agency:'moodys',previous_rating:'Aa3',new_rating:'Aa2'}},
 {agency:'sp',status:'rated',rating:'AA-',outlook:'negative',watch:'unknown',latest_change:qa.ratingEvent},
 {agency:'fitch',status:'rated',rating:'BBB+',outlook:'stable',watch:'unknown',latest_change:{...qa.ratingEvent,agency:'fitch',previous_rating:'BBB',new_rating:'BBB+',date_basis:'detected',change_date:null}}]};
renderRows(state.items);applyLanguage();renderHoldingsCreditRatings();document.querySelector('.holding-credit-ratings-cell').scrollIntoView({block:'center'});
''')
    table_geometry = evaluate("(()=>{const cell=document.querySelector('.holding-credit-ratings-cell');return {overflow:document.documentElement.scrollWidth-innerWidth,clipped:cell.scrollWidth>cell.clientWidth+1,width:cell.getBoundingClientRect().width,height:cell.getBoundingClientRect().height,changes:cell.querySelectorAll('[data-credit-latest-change]').length}})()")
    assert table_geometry["overflow"] <= 1 and not table_geometry["clipped"] and table_geometry["changes"] == 0, table_geometry
    (tmp_path / f"rating-table-history-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
    assert evaluate("qa.aiPosts") == 0
    assert evaluate("qa.errors") == []
