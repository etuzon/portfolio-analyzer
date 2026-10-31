"""Prediction checks must explain pending results beside the user's action."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "web/app.js").read_text()


def run_js(body):
    names = ("resetCompanyOutlookHistoryUi", "companyOutlookEvaluationMessage", "positionCompanyOutlookHelp", "setCompanyOutlookHelpVisible", "updateCompanyOutlookEvaluationUi", "renderCompanyOutlookHistory", "loadCompanyOutlookHistory", "evaluateCompanyOutlookPrediction")
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
const document={body:{},activeElement:{},querySelectorAll:()=>[...cards.values()]};
const makeNode=()=>({textContent:'',disabled:false,hidden:false,classList:{toggle(){}},focus(){document.activeElement=this}});
const cards=new Map(['p1','p2'].map(id=>{
 const feedback=makeNode(),button=makeNode(),remove=makeNode();
 return [id,{dataset:{companyOutlookPrediction:id},setAttribute(key,value){this[key]=value},querySelector(selector){
  return selector==='.outlook-prediction-feedback'?feedback:selector==='[data-evaluate-company-outlook]'?button:remove;
 }}];
}));
const nodes={companyOutlookHistory:{innerHTML:''},companyOutlookScorecard:{innerHTML:''},outlookSymbol:{value:'NEWT'}};
const $=id=>nodes[id];
const record=(id='p1')=>({id,symbol:'NEWT',created_at:'2026-10-31T00:00:00Z',horizon_date:'2027-10-26',score:45,label:'Weak',confidence:'High',actual_direction:'pending',baseline:{target:{fiscal_date:'2025-12-31'}}});
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
 assert.ok(card.querySelector('.outlook-prediction-feedback').textContent.includes('בודק'));
 assert.equal(cards.get('p2').querySelector('[data-evaluate-company-outlook]').disabled,false);
 await evaluateCompanyOutlookPrediction('p1');assert.equal(requests.length,1,'duplicate clicks must not submit twice');
 const result={...record(),evaluation:'No newer annual report is available yet.'};
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
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_failure_and_timeout_are_visible_and_retry_can_finish_successfully():
    run_js(r'''
(async()=>{
 renderCompanyOutlookHistory(data());
 const checking=evaluateCompanyOutlookPrediction('p1');
 requests[0].reject(new Error('private provider credentials'));await checking;
 const card=cards.get('p1');
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
 assert.ok(nodes.companyOutlookHistory.innerHTML.includes('100%'));
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
 assert.ok(html.includes('class="outlook-history-state pending outlook-pending-trigger" tabindex="0" aria-describedby="outlookPendingHelp0"'));
 assert.ok(html.includes('role="tooltip" hidden'));
 assert.ok(!html.includes('<summary')&&!html.includes('<details')&&!html.includes('>i<'));
 assert.ok(html.includes('role="status"')&&html.includes('aria-live="polite"'));
 assert.ok(text.includes('31/10/2026')&&text.includes('26/10/2027'));
 if(language==='he'){
  assert.ok(text.includes('הערכת הדוח הבא')&&text.includes('אינו מפעיל בדיקה אוטומטית'));
  assert.ok(!/Pending|Evaluate|Confidence|Created|No newer|Accuracy|High|Weak/.test(text));
 }else{
  assert.ok(text.includes('Select Evaluate next report to check'));
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
 const trigger=makeNode();trigger.dataset={};trigger.closest=()=>p2;
 trigger.matches=selector=>selector==='.outlook-pending-trigger';
 const panel={hidden:true,style:{},scrollHeight:200,closest:()=>p2};
 const help={querySelector:()=>panel,closest:()=>({getBoundingClientRect:()=>({top:50,bottom:950})})};
 p2.querySelector=selector=>selector==='.outlook-pending-trigger'?trigger:selector==='.outlook-pending-help'?help:originalQuery(selector);
 nodes.companyOutlookHistory.querySelectorAll=()=>panel.hidden?[]:[panel];
 let html=nodes.companyOutlookHistory.innerHTML;
 Object.defineProperty(nodes.companyOutlookHistory,'innerHTML',{
  get:()=>html,
  set:value=>{html=value;document.activeElement=document.body;panel.hidden=true},
 });
 const checking=evaluateCompanyOutlookPrediction('p1');
 trigger.focus();panel.hidden=false;
 const result={...record(),evaluation:'No newer annual report is available yet.'};
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
const help={querySelector:()=>panel,closest:selector=>({getBoundingClientRect:()=>selector==='.modal-card'?{top:50,bottom:950}:header})};
setCompanyOutlookHelpVisible(help,true);
assert.equal(panel.hidden,false);
assert.equal(panel.style.insetBlockStart,'auto','bottom-edge help must open upward');
assert.equal(panel.style.insetBlockEnd,'100%');
header={top:100,bottom:128};positionCompanyOutlookHelp(help);
assert.equal(panel.style.insetBlockStart,'100%','top-edge help must open downward');
header={top:500,bottom:528};panel.scrollHeight=900;positionCompanyOutlookHelp(help);
assert.equal(panel.style.maxHeight,'434px');
assert.equal(panel.style.overflowY,'auto','long descriptions remain scrollable inside the available space');
setCompanyOutlookHelpVisible(help,false);assert.equal(panel.hidden,true);
''')
