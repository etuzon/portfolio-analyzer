"""Recorded observations use actual dates and the existing canonical JS model."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]

def run(body):
    setup=r'''
const assert=require('node:assert/strict');
const state={language:'en',baseCurrency:'USD',localAccounts:[{id:'original'}],localTransactions:[],coreFxRates:{original:1},bannerFxRates:{banner:2},fxRates:{original:1},auth:{user:{id:'writer'}}};
const t=value=>value;
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const formatDate=value=>value.split('-').reverse().join('/');
const formatDateTime=value=>formatDate(value.slice(0,10))+' 12:00';
const currencyDisplayLabel=value=>value;
const riskBand=score=>({label:'Risk band'});
const riskTooltip=risk=>'Score '+risk.score;
const document={addEventListener(){}};
const nodes={riskHistoryContent:{innerHTML:'',setAttribute(){}}};
const $=id=>nodes[id];
const setCoreFxRates=data=>{state.coreFxRates={'USD/ILS':data.rate};state.fxRates={...state.coreFxRates,...state.bannerFxRates};};
const portfolioItems=items=>items.filter(row=>row.asset!=='ESOP');
let compute;
const portfolioRiskSnapshot=items=>compute(items);
let writable=true;
const canWrite=()=>writable;
let api;
'''
    source=(ROOT/'web/risk-history-ui.js').read_text()
    result=subprocess.run(['node'],input=setup+source+'\n'+body,text=True,capture_output=True,cwd=ROOT)
    assert result.returncode==0,result.stderr


def test_context_compute_is_canonical_and_restores_state_on_success_and_failure():
    run(r'''
const original=JSON.stringify(state);
const context={base_currency:'ILS',accounts:[{id:'context'}],transactions:[{id:'tx'}],items:[{asset:'EQUITY'},{asset:'ESOP'}],fx:{rate:3.5}};
compute=items=>{assert.equal(items.length,1);assert.equal(state.localAccounts[0].id,'context');assert.equal(state.language,'en');assert.deepEqual(state.fxRates,{'USD/ILS':3.5});return {total:{score:35},accounts:[]};};
assert.equal(riskHistoryCalculate(context).total.score,35);
assert.equal(JSON.stringify(state),original);
compute=()=>{throw Error('invalid source');};
assert.throws(()=>riskHistoryCalculate(context));assert.equal(JSON.stringify(state),original);
''')


def test_daily_account_series_uses_last_actual_observation_and_leaves_absent_account_unknown():
    run(r'''
const sample=(date,time,total,account)=>({id:time,date,observed_at:date+'T'+time+':00Z',total:{score:total},accounts:account===null?[]:[{account_id:'stable-id',account_label:'Renamed',risk:{score:account}}]});
const data={items:[sample('2026-11-01','12:00',35,20),sample('2026-11-01','15:00',40,25),sample('2026-11-03','12:00',45,null)]};
assert.deepEqual(riskHistoryDailyRows(data,'').map(row=>row.risk.score),[40,45]);
assert.deepEqual(riskHistoryDailyRows(data,'stable-id').map(row=>row.risk.score),[25]);
assert.deepEqual(riskHistoryDailyRows(data,'unknown'),[]);
assert.equal(data.items.length,3);
''')


def test_line_graph_has_fixed_score_scale_dots_and_breaks_over_missing_days():
    run(r'''
const rows=[{date:'2026-11-01',observed_at:'2026-11-01T12:00:00Z',risk:{score:0}},{date:'2026-11-02',observed_at:'2026-11-02T12:00:00Z',risk:{score:100}},{date:'2026-11-05',observed_at:'2026-11-05T12:00:00Z',risk:{score:35}}];
const html=riskHistoryGraph(rows,'Total');
assert.equal((html.match(/<circle /g)||[]).length,3);
const path=html.match(/<path d="([^"]*)"/)[1];
assert.equal((path.match(/M/g)||[]).length,2);assert.equal((path.match(/L/g)||[]).length,1);
for(const value of [0,20,40,60,80,100])assert.ok(html.includes('>'+value+'</text>'));
assert.ok(html.includes('01/11/2026'));assert.ok(html.includes('05/11/2026'));assert.ok(!html.includes('%'));
const single=riskHistoryGraph([rows[0]],'Total');assert.ok(!single.match(/<path d="[^"]*L/));
''')


def test_capture_permissions_scope_and_identity_never_record_unrelated_scores():
    run(r'''
(async()=>{
let calls=[];
api=async(path,options)=>{calls.push(path);return {base_currency:'ILS',account_ids:['context'],accounts:[{id:'context'}],transactions:[],items:[],fx:{rate:3.5},token:'fixture'};};
writable=false;await recordRiskHistory();assert.equal(calls.length,0);
writable=true;compute=()=>({total:{score:35,components:{}},accounts:[{key:'other',risk:{score:20}}]});
await recordRiskHistory();assert.equal(calls.length,1);assert.ok(riskHistoryView.captureError);
calls=[];compute=()=>({total:{score:35,components:{}},accounts:[{key:'context',risk:{score:20,components:{}}}]});
api=async(path,options)=>{calls.push(path);if(!options)return {base_currency:'ILS',account_ids:['context'],accounts:[],transactions:[],items:[],fx:{rate:3.5},token:'fixture'};const body=JSON.parse(options.body);assert.equal(body.accounts[0].account_id,'context');assert.equal(body.total.score,35);};
await recordRiskHistory();assert.equal(calls.length,2);assert.equal(riskHistoryView.captureError,'');
})().catch(error=>{console.error(error);process.exit(1);});
''')


def test_history_empty_and_single_point_states_and_range_keep_selected_account():
    run(r'''
riskHistoryView.data={base_currency:'ILS',items:[],accounts:[]};renderRiskHistory();assert.ok(nodes.riskHistoryContent.innerHTML.includes('No observations yet'));
riskHistoryView.account='deleted';riskHistoryView.accountLabel='Old account';renderRiskHistory();assert.ok(nodes.riskHistoryContent.innerHTML.includes('value="deleted" selected'));assert.ok(nodes.riskHistoryContent.innerHTML.includes('Old account'));
riskHistoryView.account='';riskHistoryView.data.items=[{date:'2026-11-01',observed_at:'2026-11-01T12:00:00Z',total:{score:0},accounts:[]}];renderRiskHistory();assert.ok(nodes.riskHistoryContent.innerHTML.includes('Only one observation'));assert.ok(nodes.riskHistoryContent.innerHTML.includes('0/100'));
state.language='he';renderRiskHistory();assert.ok(nodes.riskHistoryContent.innerHTML.includes('קיימת מדידה אחת בלבד'));
''')
