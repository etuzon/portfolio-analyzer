"""Independent observed-history checks; Node fixtures are not real-browser QA."""
from pathlib import Path
import subprocess
import pytest
from app import risk_history
from app.local_portfolio import LocalPortfolioStore
from test_risk_data_gaps_frontend import run_risk
from test_shared_cash_risk_qa import app_functions
from test_trade_simulator import run_simulation

ROOT = Path(__file__).resolve().parents[1]


def history_js(body):
    script = r'''
const assert=require('node:assert/strict');
const state={language:'en',baseCurrency:'USD',auth:{user:{id:'one'}}};
const document={addEventListener(){}};
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const t=value=>value;
const formatDate=value=>value.split('-').reverse().join('/');
const formatDateTime=value=>`${formatDate(value.slice(0,10))} ${value.slice(11,16)}`;
const riskBand=()=>({label:state.language==='he'?'בינוני':'Moderate'});
const target={innerHTML:'',setAttribute(){}};
const $=id=>id==='riskHistoryContent'?target:null;
const riskTooltip=risk=>`score ${risk.score}/100`;
''' + (ROOT/'web/risk-history-ui.js').read_text() + '\n' + body
    result=subprocess.run(['node'], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_daily_selection_and_graph_gaps_preserve_observed_values():
    history_js(r'''
const sample=(date,time,score,accountScore)=>({date,observed_at:`${date}T${time}:00Z`,total:{score},accounts:accountScore===null?[]:[{account_id:'a',risk:{score:accountScore}}]});
const data={items:[sample('2026-11-01','10:00',10,11),sample('2026-11-01','12:00',20,21),sample('2026-11-02','12:00',30,null),sample('2026-11-04','12:00',40,41)]};
const original=JSON.stringify(data);
const total=riskHistoryDailyRows(data,'');
assert.deepEqual(total.map(row=>row.risk.score),[20,30,40]);
assert.deepEqual(riskHistoryDailyRows(data,'a').map(row=>row.risk.score),[21,41]);
assert.deepEqual(riskHistoryDailyRows(data,'unknown'),[]);
const graph=riskHistoryGraph(total,'Total portfolio');
assert.equal((graph.match(/<circle /g)||[]).length,3);
const path=graph.match(/<path d="([^"]*)"/)[1];
assert.equal((path.match(/M/g)||[]).length,2);
assert.equal((path.match(/L/g)||[]).length,1);
for(const value of [0,20,40,60,80,100])assert.ok(graph.includes(`>${value}</text>`));
assert.ok(graph.includes('01/11/2026'));
assert.ok(!graph.includes('%'));
const single=riskHistoryGraph([total[0]],'Total');
assert.equal((single.match(/<circle /g)||[]).length,1);
assert.ok(!single.match(/<path d="[^"]*L/));
assert.equal(JSON.stringify(data),original);
''')


def test_viewer_never_captures_and_old_user_response_cannot_restore_history():
    history_js(r'''
const canWrite=()=>false;
let resolveRequest,calls=0;
const api=()=>{calls++;return new Promise(resolve=>resolveRequest=resolve);};
renderRiskHistory=()=>{};
(async()=>{
 await recordRiskHistory();assert.equal(calls,0);
 const loading=loadRiskHistory();
 await Promise.resolve();
 assert.equal(calls,1);
 state.auth.user={id:'two'};resetRiskHistory();
 resolveRequest({items:[{total:{score:99}}]});await loading;
 assert.equal(riskHistoryView.data,null);
 assert.equal(riskHistoryView.loading,false);
})();
''')


def test_latest_period_request_wins_when_network_results_arrive_out_of_order():
    history_js(r'''
const canWrite=()=>false;
const pending=[];
const api=url=>new Promise(resolve=>pending.push({url,resolve}));
renderRiskHistory=()=>{};
(async()=>{
 const older=loadRiskHistory({capture:false});
 riskHistoryView.days='30';
 const newer=loadRiskHistory({capture:false});
 assert.ok(pending[0].url.includes('days=90'));
 assert.ok(pending[1].url.includes('days=30'));
 pending[1].resolve({items:[],marker:'newer'});await newer;
 pending[0].resolve({items:[],marker:'older'});await older;
 assert.equal(riskHistoryView.data.marker,'newer');
 assert.equal(riskHistoryView.loading,false);
})();
''')


def test_frozen_context_executes_v2_borrowing_and_rollup_arithmetic_without_state_leak():
    functions=app_functions('portfolioRiskSnapshot','accountCashBalance','accountRiskCashValue',
        'riskAllocationForItems','riskAllocationBand','cleanSourceLabel','portfolioItems',
        'isEquityCompHolding','portfolioAccounts','isEquityCompAccount')
    run_simulation(functions+r'''
const document={addEventListener(){}};
const accountHorizonYears=()=>20;
const normalizedAmount=value=>value;
const transactionCashImpact=()=>{throw Error('No transactions in fixture');};
const setCoreFxRates=()=>{state.coreFxRates={};state.fxRates={};};
const accountRecordForHolding=holding=>state.localAccounts.find(row=>row.id===holding.account_id);
state.language='he';state.localAccounts=[account('original')];state.localTransactions=[];
state.coreFxRates={old:1};state.bannerFxRates={banner:2};state.fxRates={old:1,banner:2};
const before=JSON.stringify(state);
''' + (ROOT/'web/risk-history-ui.js').read_text()+r'''
const ctx={base_currency:'USD',accounts:[account('us1','USA',-1000),account('surplus','USA',2000)],transactions:[],items:[stock('HELD',10000)],fx:{quotes:[]}};
const original=JSON.stringify(ctx);
const snapshot=riskHistoryCalculate(ctx);
// Raw v2 arithmetic: combined unlevered S=41.3666667, D/E=1000/11000;
// combined rounds to 45. Account scores 55 and 8, weighted by 10000:2000,
// then total round(.75*45+.25*(55*5/6+8/6)) = 46.
assert.equal(snapshot.total.score,46);
assert.equal(snapshot.total.cash_debt,1000);
assert.equal(snapshot.total.net_equity,11000);
assert.equal(snapshot.accounts.find(row=>row.key==='us1').risk.score,55);
assert.equal(snapshot.accounts.find(row=>row.key==='surplus').risk.score,8);
assert.equal(JSON.stringify(ctx),original);
assert.equal(JSON.stringify(state),before);
''')


def test_malformed_nested_quality_is_rejected_and_legacy_display_does_not_crash():
    malformed=[{'code':'price_history','weight_percent':100,'affected':{}},
        {'code':'price_history','weight_percent':100,'affected':[None]},
        {'code':'holding_metadata','weight_percent':100,'affected':[{'symbol':'AAA','missing_fields':{}}]},
        {'code':'price_history','weight_percent':100,'symbols':{}}]
    for detail in malformed:
        with pytest.raises(risk_history.RiskHistoryError,match='invalid_quality'):
            risk_history._risk({'score':0,'components':{},'quality_details':[detail]})
    run_risk(r'''
const cases=[{code:'price_history',weight_percent:100,affected:{}},
 {code:'price_history',weight_percent:100,affected:[null]},
 {code:'holding_metadata',weight_percent:100,affected:[{symbol:'AAA',missing_fields:{}}]},
 {code:'price_history',weight_percent:100,symbols:{}}];
for(const detail of cases)for(const language of ['en','he']){
 state.language=language;
 const text=riskDataQualityHtml({components:{data_quality:2},quality_details:[detail]});
 assert.ok(text.includes('<details'));
 assert.ok(!text.includes('undefined'));
}
''')


def test_invalid_json_history_preference_is_disclosed(tmp_path):
    store=LocalPortfolioStore(tmp_path/'malformed-history.sqlite3')
    with store._connect() as connection:
        connection.execute('insert into app_preferences(key,value,updated_at) values(?,?,?)',
            (risk_history.PREFIX+'broken','not-json','2026-11-06T12:00:00Z'))
    result=risk_history.list_observations(store,'USD',0)
    assert result['items']==[]
    assert result['invalid_records']==1


def test_history_redraw_preserves_control_focus_and_keeps_reload_focusable():
    history_js(app_functions('preserveRenderedInteraction')+r'''
const currencyDisplayLabel=value=>value;
let html='';
Object.defineProperty(target,'innerHTML',{get(){return html;},set(value){html=value;if(document.activeElement)document.activeElement.isConnected=false;}});
target.contains=()=>true;
for(const [id,tagName] of [['riskHistoryDays','SELECT'],['riskHistoryReload','BUTTON']]){
 const active={tagName,id,attributes:[{name:'id',value:id}],className:'',isConnected:true,closest:()=>null};
 const replacement={getAttribute:name=>name==='id'?id:null,focus(){document.activeElement=this;}};
 target.querySelectorAll=selector=>selector===tagName?[replacement]:[];
 document.activeElement=active;
 riskHistoryView.loading=true;
 renderRiskHistory();
 assert.equal(document.activeElement,replacement);
 assert.ok(html.includes('id="riskHistoryReload" class="secondary" type="button" aria-disabled="true"'));
 assert.ok(!html.includes('type="button" disabled'));
}
''')
