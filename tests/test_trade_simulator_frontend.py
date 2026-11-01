"""Synthetic browser-contract checks; these do not replace rendered browser QA."""
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    script = "const window = {};\n" + (ROOT / "web/i18n.js").read_text() + r'''
const assert=require('node:assert/strict');
window.PortfolioTradeSimulator=require('./web/trade-simulator.js');
const state={language:'he',localAccounts:[{id:'one',account_id:'A1',type:'Investment',currency:'USD',initial_cash:1000}],localTransactions:[],allPortfolioItems:[],fxRates:[]};
const t=text=>window.PortfolioI18n.translate(text,state.language);
const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const fmt=n=>String(n);
const money=(n,c)=>`${c} ${Number(n).toFixed(2)}`;
const currencyDisplayLabel=c=>c;
const formatDate=value=>value.slice(0,10).split('-').reverse().join('/');
const formatDateTime=formatDate;
const riskBadge=r=>`<span>${r.score}</span>`;
const tradePlannerAccountName=a=>a.account_id;
const riskScoreForItems=()=>({score:10});
const accountHorizonYears=()=>20;
const derivativeHolding=()=>false;
const nodes={};
for(const id of ['tradeSimulatorRows','tradeSimulatorAccount','tradeSimulatorCount','tradeSimulatorAccountNotice','tradeSimulatorResults','runTradeSimulator','clearTradeSimulator','addTradeSimulatorRow','tradeSimulatorForm'])nodes[id]={value:'',innerHTML:'',textContent:'',disabled:false,hidden:false,setAttribute(){},querySelectorAll(){return[];},reset(){}};
const $=id=>nodes[id];
const handlers={};
const document={activeElement:null,addEventListener:(name,handler)=>{(handlers[name]||=[]).push(handler);}};
const security={holding:{symbol:'NEW',stock_market:'NASDAQ',currency:'USD',asset_class:'EQUITY'},price_ranges:{'1m':{current:100,current_date:'2026-10-29'}}};
const ctx={accounts:state.localAccounts,transactions:[],items:[],base_currency:'USD',fx_quotes:[],calculated_at:'2026-10-30T12:00:00Z',securities:[{symbol:'NEW',stock_market:'NASDAQ',security}]};
let calls=0,pending=[];
const api=()=>{calls++;return new Promise((resolve,reject)=>pending.push({resolve,reject}));};
''' + (ROOT / "web/trade-simulator-ui.js").read_text() + "\n" + body
    completed = subprocess.run(["node"], input=script, cwd=ROOT, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr


def test_combined_short_results_are_localized_with_dates_and_unknown_buying_power():
    run_ui(r'''
tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'SHORT',quantity:'2',priceInput:'',fee:'0'}];
const result=window.PortfolioTradeSimulator.simulate(ctx,tradeSimulatorRows,{risk:riskScoreForItems,horizon:accountHorizonYears,derivative:derivativeHolding});
assert.equal(result.status,'ok');
assert.equal(result.accounts[0].after.cash,1200);
assert.equal(result.accounts[0].after.availableCash,null);
for(const language of ['he','en','he']){
 state.language=language;tradeSimulatorView={status:'ready',result};renderTradeSimulator();
 const text=nodes.tradeSimulatorResults.innerHTML.replace(/<[^>]*>/g,'');
 assert.ok(text.includes('29/10/2026'));
 assert.ok(!/undefined|NaN/.test(text));
 if(language==='he'){
  assert.ok(text.includes('כוח הקנייה אינו מאומת'));
  assert.ok(text.includes('סך כל החשבונות'));
  assert.ok(!/Before|After|cash|risk|Short|Calculated|Trade/i.test(text));
 }else{
  assert.ok(text.includes('Buying power unverified'));
  assert.ok(!/[א-ת]/.test(text));
 }
}
''')


def test_source_fingerprint_preserves_results_until_real_change_and_discards_late_response():
    run_ui(r'''
(async()=>{
 tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:'2',priceInput:'',fee:'0'}];
 checkTradeSimulatorInputs();
 const first=calculateTradeSimulation();
 checkTradeSimulatorInputs();
 assert.equal(tradeSimulatorView.status,'loading');
 await calculateTradeSimulation();assert.equal(calls,1);
 state.localAccounts[0].initial_cash=2000;checkTradeSimulatorInputs();
 assert.equal(tradeSimulatorView.status,'stale');
 const second=calculateTradeSimulation();assert.equal(calls,2);
 pending[0].resolve(ctx);await first;assert.equal(tradeSimulatorView.status,'loading');
 pending[1].resolve(ctx);await second;assert.equal(tradeSimulatorView.status,'ready');
 checkTradeSimulatorInputs();assert.equal(tradeSimulatorView.status,'ready');
 assert.equal(tradeSimulatorRows.length,1);
})();
''')


def test_validation_and_transport_failure_preserve_draft_without_exposing_errors():
    run_ui(r'''
(async()=>{
 tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'SELL',quantity:'2',priceInput:'',fee:'0'}];
 const first=calculateTradeSimulation();pending[0].resolve(ctx);await first;
 assert.equal(tradeSimulatorView.result.status,'invalid');
 assert.ok(nodes.tradeSimulatorResults.innerHTML.includes('כמות המכירה'));
 assert.equal(tradeSimulatorRows[0].quantity,'2');
 const retry=calculateTradeSimulation();pending[1].reject(new Error('private provider secret'));await retry;
 assert.equal(tradeSimulatorView.status,'error');
 assert.ok(!nodes.tradeSimulatorResults.innerHTML.includes('private provider secret'));
 assert.equal(tradeSimulatorRows[0].quantity,'2');
 resetTradeSimulator();assert.equal(tradeSimulatorRows.length,0);assert.equal(tradeSimulatorView,null);
})();
''')


def test_trade_limit_and_explicit_price_recovery_are_visible():
    run_ui(r'''
tradeSimulatorRows=Array.from({length:100},(_,index)=>({id:String(index),accountId:'one',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:'1',priceInput:'',fee:'0'}));
renderTradeSimulator();
assert.equal(nodes.addTradeSimulatorRow.disabled,true);
assert.ok(nodes.tradeSimulatorRows.innerHTML.includes('data-simulation-duplicate="0" disabled'));
state.language='en';assert.ok(tradeSimulatorReason('price_unavailable').includes('Enter an execution price'));
assert.ok(tradeSimulatorReason('unknown_account').includes('account assignments'));
''')


def test_entered_price_source_and_account_are_explicit_in_both_languages():
    run_ui(r'''
tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:'2',priceInput:'110',fee:'0'}];
const result=window.PortfolioTradeSimulator.simulate(ctx,tradeSimulatorRows,{risk:riskScoreForItems,horizon:accountHorizonYears,derivative:derivativeHolding});
for(const language of ['en','he']){
 state.language=language;tradeSimulatorView={status:'ready',result};renderTradeSimulator();
 const detail=nodes.tradeSimulatorResults.innerHTML.split('trade-simulator-execution')[1];
 assert.ok(detail.includes('A1'));
 assert.ok(detail.includes(language==='he'?'מחיר ביצוע שהוזן ידנית':'User-entered execution price'));
}
''')


def test_duplicate_action_and_instrument_errors_honor_the_active_language():
    run_ui(r'''
const row={id:'1',accountId:'one',symbol:'CSCO',market:'NASDAQ',action:'BUY',quantity:'1000',priceInput:'101',fee:'0'};
tradeSimulatorRows=[row];
for(const language of ['he','en','he']){
 state.language=language;
 const html=tradeSimulatorRowHtml(row,0);
 assert.ok(html.includes(language==='he'?'שכפול':'Duplicate'));
 if(language==='he') assert.ok(!html.includes('Duplicate'));
 const error=tradeSimulatorReason('unsupported_asset_class');
 assert.ok(error.includes('RSU'));
 assert.ok(!error.includes(language==='he'?'נגזרים':'Derivatives'));
}
''')
