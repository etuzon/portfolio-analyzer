"""The signal chart paints independently of ledger requests and can recover."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "web/app.js").read_text()


def run_loader(body):
    start = SOURCE.index("async function loadSecurityDetail(")
    end = start + re.search(r"^}", SOURCE[start:], re.M).end()
    script = r'''
const assert=require('node:assert/strict');
const state={securityDetail:{symbol:'NREF',market_key:'MANUAL'},securityChartPeriod:'1y',
 securityChartStartDate:'2026-04-14',localTransactions:[],localPrices:[],securityHistory:[],securityHistoryMeta:{}};
const requests=[],renders=[],timers=new Map();let timerId=0;
const setTimeout=callback=>{timers.set(++timerId,callback);return timerId};
const clearTimeout=id=>timers.delete(id);
const flush=()=>new Promise(setImmediate);
const api=(path,{signal})=>new Promise((resolve,reject)=>{
 requests.push({path,resolve,reject});
 signal.addEventListener('abort',()=>reject(new Error('timeout')),{once:true});
});
const renderSecurityDetail=()=>renders.push({symbol:state.securityDetail.symbol,
 history:structuredClone(state.securityHistory),load:{...state.securityDetailLoad}});
''' + SOURCE[start:end] + "\n" + body
    completed = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT, timeout=10)
    assert completed.returncode == 0, completed.stderr


def test_history_paints_before_slow_or_failed_transaction_details():
    run_loader(r'''
(async()=>{
 const loading=loadSecurityDetail();
 assert.equal(renders[0].symbol,'NREF');
 assert.equal(renders[0].load.history,'loading');
 requests[2].resolve({points:[{date:'2026-10-30',price:11}]});await flush();
 assert.equal(state.securityHistory[0].price,11);
 assert.equal(renders.at(-1).load.history,'ready');
 assert.equal(renders.at(-1).load.transactions,'loading');
 requests[0].reject(new Error('private provider details'));
 requests[1].resolve({items:[]});await loading;
 assert.equal(state.securityDetailLoad.transactions,'error');
 assert.equal(state.securityDetailLoad.history,'ready');
 assert.equal(state.securityHistory[0].price,11);
 assert.equal(timers.size,0);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_chart_failure_then_retry_and_genuine_empty_history_are_distinct_states():
    run_loader(r'''
(async()=>{
 const first=loadSecurityDetail();
 requests[0].resolve({items:[]});requests[1].resolve({items:[]});requests[2].reject(new Error('secret provider exception'));
 await first;assert.equal(state.securityDetailLoad.history,'error');
 const retry=loadSecurityDetail();
 assert.equal(state.securityDetailLoad.history,'loading');
 requests[3].resolve({items:[]});requests[4].resolve({items:[]});requests[5].resolve({points:[]});
 await retry;
 assert.equal(state.securityDetailLoad.history,'ready');
 assert.deepEqual(state.securityHistory,[]);
 const recovered=loadSecurityDetail();
 requests[6].resolve({items:[]});requests[7].resolve({items:[]});requests[8].resolve({points:[{date:'2026-10-30',price:12}]});
 await recovered;assert.equal(state.securityHistory[0].price,12);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_old_symbol_and_period_responses_cannot_overwrite_a_newer_chart():
    run_loader(r'''
(async()=>{
 const first=loadSecurityDetail();
 state.securityChartPeriod='1m';
 const newerPeriod=loadSecurityDetail();
 requests[3].resolve({items:[]});requests[4].resolve({items:[]});requests[5].resolve({points:[{date:'2026-10-30',price:20}]});
 await newerPeriod;
 requests[0].resolve({items:[{symbol:'old'}]});requests[1].resolve({items:[{symbol:'old'}]});requests[2].resolve({points:[{price:10}]});
 await first;assert.equal(state.securityHistory[0].price,20);assert.deepEqual(state.localTransactions,[]);
 const oldSymbol=loadSecurityDetail();
 state.securityDetail={symbol:'NEWT',market_key:'NASDAQ'};
 const newSymbol=loadSecurityDetail();
 requests[9].resolve({items:[]});requests[10].resolve({items:[]});requests[11].resolve({points:[{date:'2026-10-30',price:30}]});
 await newSymbol;
 requests[6].resolve({items:[]});requests[7].resolve({items:[]});requests[8].resolve({points:[{price:15}]});
 await oldSymbol;assert.equal(state.securityHistory[0].price,30);
 assert.equal(state.securityDetail.symbol,'NEWT');
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_timeout_leaves_a_recoverable_error_instead_of_permanent_loading():
    run_loader(r'''
(async()=>{
 const loading=loadSecurityDetail();
 for(const callback of timers.values())callback();
 await loading;
 assert.ok(Object.values(state.securityDetailLoad).every(status=>status==='error'));
 assert.equal(timers.size,0);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_http_success_with_provider_failure_is_retryable_not_genuine_missing_history():
    run_loader(r'''
(async()=>{
 const loading=loadSecurityDetail();
 requests[0].resolve({items:[]});requests[1].resolve({items:[]});
 requests[2].resolve({points:[],state:'error',status:{yahoo_finance:'stale (saved local history; TimeoutError)'}});
 await loading;
 assert.equal(state.securityDetailLoad.history,'error');
 assert.deepEqual(state.securityHistory,[]);
})().catch(error=>{console.error(error);process.exitCode=1});
''')
