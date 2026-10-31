"""Prediction checks must explain pending results beside the user's action."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "web/app.js").read_text()


def run_js(body):
    names = ("resetCompanyOutlookHistoryUi", "companyOutlookEvaluationMessage", "companyOutlookCheckStatus", "companyOutlookCanCheck", "companyOutlookUsesCurrentFormula", "companyOutlookHasScore", "companyOutlookEvidenceReason", "companyOutlookRankText", "companyOutlookEvaluationHelp", "companyOutlookScoreHelp", "companyOutlookConfidenceHelp", "companyOutlookDataCoverage", "companyOutlookNarrative", "companyOutlookHistoryThesis", "outlookScoreText", "formatBackupDateTime", "positionCompanyOutlookHelp", "setCompanyOutlookHelpVisible", "updateCompanyOutlookEvaluationUi", "renderCompanyOutlookHistory", "loadCompanyOutlookHistory", "evaluateCompanyOutlookPrediction")
    functions = []
    for name in names:
        start = re.search(rf"^(?:async )?function {name}\(", SOURCE, re.M).start()
        end = start + re.search(r"^}", SOURCE[start:], re.M).end()
        functions.append(SOURCE[start:end])
    script = "const window={};\n" + (ROOT / "web/i18n.js").read_text() + r'''
const assert=require('node:assert/strict');
const state={language:'he',companyOutlookHistory:[],companyOutlookEvaluationUi:{},companyOutlookHistorySymbol:'',companyOutlookHistoryVersion:0};
const t=text=>window.PortfolioI18n.translate(text,state.language);
const fmt=value=>String(value),pct=value=>`${value}%`;
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const formatDate=value=>String(value).slice(0,10).split('-').reverse().join('/');
const document={documentElement:{dir:'rtl'},body:{},activeElement:{},querySelectorAll:()=>[...cards.values()]};
const makeNode=()=>({textContent:'',disabled:false,hidden:false,classList:{toggle(){}},focus(){document.activeElement=this}});
const cards=new Map(['p1','p2','p3'].map(id=>{
 const feedback=makeNode(),button=makeNode(),remove=makeNode(),badge=makeNode(),help=makeNode();
 return [id,{dataset:{companyOutlookPrediction:id},setAttribute(key,value){this[key]=value},querySelector(selector){
  return selector==='.outlook-prediction-feedback'?feedback:selector==='[data-evaluate-company-outlook]'?button:selector==='[data-delete-company-outlook]'?remove:selector==='.outlook-pending-trigger'?badge:selector==='.outlook-pending-description'?help:null;
 }}];
}));
const nodes={companyOutlookHistory:{innerHTML:''},companyOutlookScorecard:{innerHTML:''},outlookSymbol:{value:'NEWT'}};
const $=id=>nodes[id];
const record=(id='p1')=>({id,symbol:id==='p2'?'NREF':'NEWT',created_at:'2026-10-31T00:00:00Z',horizon_date:'2027-10-26',score:45,label:'Weak',confidence:'High',actual_direction:'pending',baseline:{target:{fiscal_date:'2025-12-31'}}});
const data=(items=[record(),record('p2')])=>({items,scorecard:{total:items.length,pending:items.length}});
const requests=[],timers=new Map();let timerId=0;
const setTimeout=callback=>{timers.set(++timerId,callback);return timerId};
const clearTimeout=id=>timers.delete(id);
const flush=()=>new Promise(setImmediate);
const api=(path,options={})=>new Promise((resolve,reject)=>{
 requests.push({path,options,resolve,reject});
 options.signal?.addEventListener('abort',()=>reject(new Error('timeout')),{once:true});
});
''' + "\n".join(functions) + "\n" + body
    completed = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT, timeout=10)
    assert completed.returncode == 0, completed.stderr


def test_check_gives_immediate_per_card_feedback_and_preserves_no_new_report_result():
    run_js(r'''
(async()=>{
 renderCompanyOutlookHistory(data());
 const baseline=JSON.stringify(state.companyOutlookHistory[0].baseline);
 const checking=evaluateCompanyOutlookPrediction('p1');
 const card=cards.get('p1');
 assert.equal(card.querySelector('[data-evaluate-company-outlook]').disabled,true);
 assert.equal(card.querySelector('.outlook-pending-trigger').textContent,'בודק…');
 assert.ok(card.querySelector('.outlook-prediction-feedback').textContent.includes('בודק'));
 assert.equal(cards.get('p2').querySelector('[data-evaluate-company-outlook]').disabled,false);
 await evaluateCompanyOutlookPrediction('p1');assert.equal(requests.length,1,'duplicate clicks must not submit twice');
 const result={...record(),checked_at:'2026-10-31T14:25:00Z',evaluation:'No newer annual report is available yet.'};
 requests[0].resolve(result);await flush();
 assert.equal(requests[1].path,'/api/company-outlook/predictions','preserve current history filter, not the ticker input');
 requests[1].resolve(data([result,record('p2')]));await checking;
 const message=card.querySelector('.outlook-prediction-feedback').textContent;
 assert.ok(message.includes('הבדיקה הושלמה')&&message.includes('לאחר פרסום הדוח הבא'));
 assert.equal(card.querySelector('[data-evaluate-company-outlook]').disabled,false);
 assert.equal(JSON.stringify(state.companyOutlookHistory[0].baseline),baseline);
 state.companyOutlookEvaluationUi={};renderCompanyOutlookHistory(data([result]));
 assert.ok(nodes.companyOutlookHistory.innerHTML.includes('עדיין אין דוח שנתי חדש יותר'),'persisted pending explanation remains visible after reload');
 assert.equal(timers.size,0);
 assert.equal(card.querySelector('.outlook-pending-trigger').textContent,'נבדק — אין דוח חדש');
 assert.ok(nodes.companyOutlookHistory.innerHTML.includes('31/10/2026'));
 assert.ok(nodes.companyOutlookHistory.innerHTML.includes('נבדק לאחרונה'));
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_failure_and_timeout_are_visible_and_retry_can_finish_successfully():
    run_js(r'''
(async()=>{
 renderCompanyOutlookHistory(data());
 const checking=evaluateCompanyOutlookPrediction('p1');
 requests[0].reject(new Error('private provider credentials'));await checking;
 const card=cards.get('p1');
 assert.equal(card.querySelector('.outlook-pending-trigger').textContent,'הבדיקה נכשלה');
 assert.ok(card.querySelector('.outlook-prediction-feedback').textContent.includes('לא ניתן לבדוק'));
 assert.ok(!card.querySelector('.outlook-prediction-feedback').textContent.includes('private'));
 assert.equal(card.querySelector('[data-evaluate-company-outlook]').textContent,'ניסיון נוסף');
 const timeout=evaluateCompanyOutlookPrediction('p1');
 for(const callback of timers.values())callback();await timeout;
 assert.equal(state.companyOutlookEvaluationUi.p1.status,'error');
 const retry=evaluateCompanyOutlookPrediction('p1');
 const result={...record(),actual_direction:'positive',accuracy_score:100,evaluation:'Revenue growth and net margin both improved or held.'};
 requests[2].resolve(result);await flush();requests[3].resolve(data([result,record('p2')]));await retry;
 assert.equal(state.companyOutlookHistory[0].actual_direction,'positive');
 assert.ok(nodes.companyOutlookHistory.innerHTML.includes('100/100'));
 assert.ok(!nodes.companyOutlookHistory.innerHTML.includes('data-evaluate-company-outlook="p1"'));
 assert.ok(card.querySelector('.outlook-prediction-feedback').textContent.includes('השתפרו'));
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_successful_evaluation_is_not_reported_as_failed_when_history_refresh_fails():
    run_js(r'''
(async()=>{
 renderCompanyOutlookHistory(data());
 const checking=evaluateCompanyOutlookPrediction('p1');
 requests[0].resolve({...record(),evaluation:'No newer annual report is available yet.'});await flush();
 requests[1].reject(new Error('history unavailable'));await checking;
 const message=cards.get('p1').querySelector('.outlook-prediction-feedback').textContent;
 assert.ok(message.includes('הבדיקה הושלמה')&&message.includes('לא ניתן לרענן'));
 assert.ok(!message.includes('לא ניתן לבדוק את התחזית'));
 assert.equal(state.companyOutlookEvaluationUi.p1.status,'done');
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_pending_badge_has_localized_tooltip_without_a_separate_info_control():
    run_js(r'''
for(const language of ['he','en','he']){
 state.language=language;
 renderCompanyOutlookHistory(data([{...record(),evaluation:'No newer annual report is available yet.'}]));
 const html=nodes.companyOutlookHistory.innerHTML;
 const text=html.replace(/<[^>]*>/g,'');
 assert.ok(html.includes('class="outlook-history-state checked outlook-pending-trigger outlook-help-trigger" data-outlook-help="status" tabindex="0" aria-describedby="outlookPendingHelp0"'));
 assert.ok(html.includes('role="tooltip" hidden'));
 assert.ok(!html.includes('<summary')&&!html.includes('<details')&&!html.includes('>i<'));
 assert.ok(html.includes('role="status"')&&html.includes('aria-live="polite"'));
 assert.ok(text.includes('31/10/2026')&&text.includes('26/10/2027'));
 if(language==='he'){
  assert.ok(text.includes('נבדק — אין דוח חדש')&&text.includes('הבדיקה מתבצעת ידנית'));
  assert.ok(!/Pending|Evaluate|Confidence|Created|No newer|Accuracy|High|Weak/.test(text));
 }else{
  assert.ok(text.includes('The last check found no newer annual report'));
  assert.ok(!/[א-ת]/.test(text));
 }
}
''')


def test_old_history_response_and_signed_out_evaluation_do_not_replace_current_view():
    run_js(r'''
(async()=>{
 const older=loadCompanyOutlookHistory('NEWT');
 const newer=loadCompanyOutlookHistory('NREF');
 requests[1].resolve(data([{...record('p2'),symbol:'NREF'}]));await newer;
 requests[0].resolve(data());await older;
 assert.equal(state.companyOutlookHistory[0].symbol,'NREF');
 const checking=evaluateCompanyOutlookPrediction('p2');
 resetCompanyOutlookHistoryUi();
 requests[2].resolve({...record('p2'),actual_direction:'positive'});await checking;
 assert.deepEqual(state.companyOutlookEvaluationUi,{});
 assert.equal(requests.length,3,'sign-out must suppress the obsolete history refresh');
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_sign_out_after_post_success_rejects_the_late_history_refresh():
    run_js(r'''
(async()=>{
 renderCompanyOutlookHistory(data());
 const checking=evaluateCompanyOutlookPrediction('p1');
 requests[0].resolve({...record(),actual_direction:'positive',evaluation:'Revenue growth and net margin both improved or held.'});
 await flush();assert.equal(requests.length,2);
 resetCompanyOutlookHistoryUi();
 requests[1].resolve(data());await checking;
 assert.deepEqual(state.companyOutlookHistory,[]);
 assert.equal(state.companyOutlookHistoryData,null);
 assert.equal(nodes.companyOutlookHistory.innerHTML,'');
 assert.deepEqual(state.companyOutlookEvaluationUi,{});
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_a_completed_check_preserves_keyboard_focus_and_open_help_on_another_card():
    run_js(r'''
(async()=>{
 renderCompanyOutlookHistory(data());
 const p2=cards.get('p2'),originalQuery=p2.querySelector.bind(p2);
 const trigger=makeNode();trigger.dataset={outlookHelp:'status'};trigger.closest=()=>p2;
 trigger.matches=selector=>selector==='.outlook-pending-trigger';
 const panel={hidden:true,style:{},scrollHeight:200,closest:selector=>selector==='.outlook-help'?help:p2};
 const help={dataset:{outlookHelp:'status'},getBoundingClientRect:()=>({top:100,bottom:128,left:20,right:100}),querySelector:()=>panel,closest:selector=>({getBoundingClientRect:()=>selector==='.modal-card'?{top:50,bottom:950}:{top:100,bottom:128,left:20,right:500,width:480}})};
 p2.querySelector=selector=>selector==='.outlook-pending-trigger'||selector===`.outlook-help-trigger[data-outlook-help="status"]`?trigger:selector===`.outlook-help[data-outlook-help="status"]`?help:originalQuery(selector);
 nodes.companyOutlookHistory.querySelectorAll=()=>panel.hidden?[]:[panel];
 let html=nodes.companyOutlookHistory.innerHTML;
 Object.defineProperty(nodes.companyOutlookHistory,'innerHTML',{
  get:()=>html,
  set:value=>{html=value;document.activeElement=document.body;panel.hidden=true},
 });
 const checking=evaluateCompanyOutlookPrediction('p1');
 trigger.focus();panel.hidden=false;
 const result={...record(),checked_at:'2026-10-31T14:25:00Z',evaluation:'No newer annual report is available yet.'};
 requests[0].resolve(result);await flush();
 assert.equal(document.activeElement,trigger,'another card retains keyboard focus after the POST update');
 assert.equal(panel.hidden,false);
 requests[1].resolve(data([result,record('p2')]));await checking;
 assert.equal(document.activeElement,trigger,'completion must not steal focus from another card');
 assert.equal(panel.hidden,false);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_pending_help_uses_available_dialog_space_including_bottom_edge_and_long_text():
    run_js(r'''
window.innerHeight=1000;
const panel={hidden:true,scrollHeight:200,style:{}};
let header={top:900,bottom:928};
const help={getBoundingClientRect:()=>({...header,left:20,right:80}),querySelector:()=>panel,closest:selector=>({getBoundingClientRect:()=>selector==='.modal-card'?{top:50,bottom:950}:{...header,left:20,right:500,width:480}})};
setCompanyOutlookHelpVisible(help,true);
assert.equal(panel.hidden,false);
assert.equal(panel.style.insetBlockStart,'auto','bottom-edge help must open upward');
assert.equal(panel.style.insetBlockEnd,'28px');
header={top:100,bottom:128};positionCompanyOutlookHelp(help);
assert.equal(panel.style.insetBlockStart,'28px','top-edge help must open downward');
header={top:500,bottom:528};panel.scrollHeight=900;positionCompanyOutlookHelp(help);
assert.equal(panel.style.maxHeight,'434px');
assert.equal(panel.style.overflowY,'auto','long descriptions remain scrollable inside the available space');
setCompanyOutlookHelpVisible(help,false);assert.equal(panel.hidden,true);
''')


def test_reload_distinguishes_unchecked_legacy_checked_and_dated_checked_predictions():
    run_js(r"""
for(const language of ['he','en']){
 state.language=language;
 const statuses=language==='he'?['טרם הושווה לדוח חדש','נבדק — אין דוח חדש']:['Not compared with a newer report','Checked — no new report'];
 renderCompanyOutlookHistory(data([record()]));
 let html=nodes.companyOutlookHistory.innerHTML;
 assert.ok(html.includes(statuses[0]));assert.ok(!html.includes('<time'));
 const result={...record(),evaluation:'No newer annual report is available yet.'};
 renderCompanyOutlookHistory(data([result]));
 html=nodes.companyOutlookHistory.innerHTML;
 assert.ok(html.includes(statuses[1]));assert.ok(!html.includes('<time'),'legacy checks must not fabricate dates');
 result.checked_at='2026-10-31T14:25:00Z';
 renderCompanyOutlookHistory(data([result]));
 html=nodes.companyOutlookHistory.innerHTML;
 assert.ok(html.includes(statuses[1])&&html.includes('<time datetime="2026-10-31T14:25:00Z">'));
 assert.ok(html.includes(formatBackupDateTime(result.checked_at)));
 assert.match(formatBackupDateTime(result.checked_at),/^31\/10\/2026 \d{2}:\d{2}$/);
 for(const direction of ['positive','neutral','negative','inconclusive']){
  renderCompanyOutlookHistory(data([{...result,actual_direction:direction,accuracy_score:direction==='inconclusive'?null:100}]));
  html=nodes.companyOutlookHistory.innerHTML;
  assert.ok(!html.includes('outlook-pending-trigger'));
  assert.ok(html.includes(t(direction.charAt(0).toUpperCase()+direction.slice(1))));
  assert.equal(html.includes('100/100'),direction!=='inconclusive');
 }
}
""")


def test_cards_explain_analyzed_report_rank_direction_score_and_confidence_without_mutation():
    run_js(r"""
for(const language of ['he','en']){
 state.language=language;
 for(const rank of [1,4,7]){
  const item={...record(),thesis:`NEWT ranks ${rank} of 7 on available report growth signals. Industry conditions appear stable. Cash-flow and balance-sheet measures are included when filed; missing statement evidence lowers confidence.`};
  const original=JSON.stringify(item);
  renderCompanyOutlookHistory(data([item]));
  const html=nodes.companyOutlookHistory.innerHTML;
  assert.equal(JSON.stringify(item),original,'rendering must not rewrite stored prediction evidence');
  assert.ok(html.includes(language==='he'?'הדוח השנתי שנותח':'Analyzed annual report'));
  assert.ok(html.includes('31/12/2025'));
  assert.ok(html.includes(language==='he'?`מקום ${rank} מתוך 7`:`Place ${rank} of 7`));
  assert.ok(html.includes(language==='he'?'1 = החזקה ביותר; 7 = החלשה ביותר':'1 = strongest; 7 = weakest'));
  assert.ok(html.includes(language==='he'?'כבר נותח ליצירת התחזית':'was already analyzed to create this forecast'));
  for(const kind of ['Score','Confidence','Pending'])assert.ok(html.includes(`aria-describedby="outlook${kind}Help0"`));
  assert.equal((html.match(/role="tooltip"/g)||[]).length,3);
  assert.ok(html.includes(t('Analysis data coverage'))&&html.includes(t('Broad')));
  assert.ok(!/רמת ביטחון|רמת הביטחון|Confidence describes/.test(html.replace(/<[^>]*>/g,'')));
  assert.ok(html.includes('data-outlook-help="score" tabindex="0"'));
  assert.ok(html.includes('data-outlook-help="confidence" tabindex="0"'));
  const score=companyOutlookScoreHelp(item),confidence=companyOutlookConfidenceHelp(item);
  assert.ok(score.includes(language==='he'?'נמוך מ־50':'below 50'));
  assert.ok(confidence.includes(language==='he'?'לפחות 3 שנות דוחות':'at least 3 annual report years'));
  assert.ok(confidence.includes(language==='he'?'אינו מבטיח':'does not guarantee'));
  if(language==='he'){
   assert.ok(!/Confidence|Strong|Weak|Industry|Place|Checks/.test(html.replace(/<[^>]*>/g,'')));
  }else{
   assert.ok(!/[א-ת]/.test(html));
  }
 }
 const single={...record(),thesis:'NEWT ranks 1 of 1 on available report growth signals. Industry conditions appear stable. Cash-flow and balance-sheet measures are included when filed; missing statement evidence lowers confidence.'};
 assert.ok(companyOutlookHistoryThesis(single).includes(t('No other companies were available for comparison.')));
 assert.ok(!companyOutlookHistoryThesis(single).includes('1 ='));
}
""")


def test_switching_from_english_to_hebrew_localizes_rank_narrative_before_document_update():
    run_js(r"""
global.Element=class {};
global.Document=class {};
global.DocumentFragment=class {};
global.Node={TEXT_NODE:3};global.NodeFilter={SHOW_ELEMENT:1,SHOW_TEXT:4};
Object.setPrototypeOf(document,Document.prototype);
document.createTreeWalker=()=>({nextNode:()=>null});document.querySelectorAll=()=>[];
window.PortfolioI18n.applyToDocument('en');
state.language='he';
const item={...record(),thesis:'NEWT ranks 7 of 7 on available report growth signals. Industry conditions appear stable. Cash-flow and balance-sheet measures are included when filed; missing statement evidence lowers confidence.'};
renderCompanyOutlookHistory(data([item]));
const text=nodes.companyOutlookHistory.innerHTML.replace(/<[^>]*>/g,'');
assert.ok(text.includes('מצב הענף: יציב'));
assert.ok(!/Stable|High|Weak|Confidence|Industry|Place/.test(text));
""")


def test_check_updates_company_group_and_blocks_duplicate_company_clicks():
    run_js(r"""
(async()=>{
 const siblings=[record(),{...record('p2'),symbol:'NEWT'}, {...record('p3'),symbol:'OTHER'}];
 renderCompanyOutlookHistory(data(siblings));
 const checking=evaluateCompanyOutlookPrediction('p1');
 assert.equal(cards.get('p1').querySelector('[data-evaluate-company-outlook]').disabled,true);
 assert.equal(cards.get('p2').querySelector('[data-evaluate-company-outlook]').disabled,true);
 assert.equal(cards.get('p3').querySelector('[data-evaluate-company-outlook]').disabled,false);
 await evaluateCompanyOutlookPrediction('p2');assert.equal(requests.length,1);
 const checked=siblings.slice(0,2).map(item=>({...item,evaluation:'No newer annual report is available yet.',checked_at:'2026-10-31T14:25:00Z'}));
 requests[0].resolve({...checked[0],checked_predictions:checked,failed_prediction_ids:[]});await flush();
 requests[1].resolve(data([...checked,siblings[2]]));await checking;
 for(const id of ['p1','p2'])assert.equal(cards.get(id).querySelector('.outlook-pending-trigger').textContent,'נבדק — אין דוח חדש');
 assert.equal(state.companyOutlookHistory[2].checked_at,undefined);
 assert.equal(timers.size,0);
})().catch(error=>{console.error(error);process.exitCode=1});
""")


def test_partial_company_check_failure_preserves_prior_result_and_explains_retry():
    run_js(r"""
(async()=>{
 const prior={...record(),checked_at:'2026-01-01T00:00:00Z',evaluation:'No newer annual report is available yet.'};
 const sibling={...record('p2'),symbol:'NEWT'};
 renderCompanyOutlookHistory(data([prior,sibling]));
 const checking=evaluateCompanyOutlookPrediction('p1');
 const checked={...sibling,checked_at:'2026-10-31T14:25:00Z',evaluation:'No newer annual report is available yet.'};
 requests[0].resolve({...prior,checked_predictions:[checked],failed_prediction_ids:['p1']});await flush();
 requests[1].resolve(data([prior,checked]));await checking;
 assert.equal(cards.get('p1').querySelector('.outlook-pending-trigger').textContent,'הבדיקה נכשלה');
 assert.equal(cards.get('p1').querySelector('[data-evaluate-company-outlook]').textContent,'ניסיון נוסף');
 assert.equal(state.companyOutlookHistory[0].checked_at,prior.checked_at);
 assert.equal(cards.get('p2').querySelector('.outlook-pending-trigger').textContent,'נבדק — אין דוח חדש');
})().catch(error=>{console.error(error);process.exitCode=1});
""")
