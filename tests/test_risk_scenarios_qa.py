"""Independent risk-sale arithmetic and isolated browser acceptance.

Raw synthetic USD inputs make all component arithmetic reproducible. Browser
fixtures execute the real page, app, model and scenario scripts; API evidence is
synthetic and no signed-in user, runtime data, provider or trading service is used.
"""
import base64
import json
from pathlib import Path
import re
import subprocess
import time

import pytest

from test_native_account_history_qa import chromium
from test_shared_cash_risk_qa import app_functions
from test_trade_planner import ROOT, run_planner_js


def raw_context():
    accounts = [dict(id='a', account_id='A', type='Investment', currency='USD', initial_cash=0),
                dict(id='b', account_id='B', type='Investment', currency='USD', initial_cash=2000),
                dict(id='bank', account_id='Bank', type='Bank', currency='USD', initial_cash=3000)]
    for account in accounts:
        account['persons'] = [dict(age=47, retire_age=67)]
    items = []
    for symbol, account, quantity, industry in [('AAA', 'a', 100, 'Technology'), ('BBB', 'b', 40, 'Finance')]:
        items.append(dict(holding=dict(symbol=symbol, account_id=account, quantity=quantity,
                                       market_value=quantity * 100, currency='USD', stock_market='NASDAQ',
                                       asset_class='EQUITY', industry=industry), industry=industry,
                          missing=[], price_ranges={'1y': dict(current=100, high=120, min=80,
                                                               current_date='2026-11-12')}))
    return dict(accounts=accounts, items=items, model='portfolio-risk-v2', base_currency='USD',
                observed_at='2026-11-12T12:00:00Z', date='2026-11-12', transactions=[], fx={'quotes': []})


def scenario_js(body):
    functions = app_functions('portfolioRiskSnapshot', 'portfolioAccounts', 'isEquityCompAccount',
                              'portfolioItems', 'isEquityCompHolding', 'cleanSourceLabel')
    return run_planner_js(functions + '\nconst raw=' + json.dumps(raw_context()) + r''';
const engine=require('./web/risk-scenarios.js');
const accountHorizonYears=()=>20;
const accountRiskCashValue=a=>a.initial_cash;
const riskAllocationForItems=()=>({});
const accountRecordForHolding=h=>state.localAccounts.find(a=>a.id===h.account_id);
const calculate=c=>{state.localAccounts=c.accounts;return portfolioRiskSnapshot(portfolioItems(c.items));};
(async()=>{
''' + body + r'''
})().catch(error=>{console.error(error);process.exitCode=1;});
''')


def test_independent_raw_sale_oracle_includes_unchanged_bank_and_nonlinear_rollup():
    scenario_js(r'''
const original=JSON.stringify(raw),result=await engine.generate(raw,{calculate});
assert.equal(result.baseline.accounts.length,3);
assert.equal(result.baseline.accounts.find(a=>a.key==='bank').risk.score,8);
assert.equal(result.baseline.total.score,41);
assert.equal(result.scenarios.length,2); // Fewer than default five; no invented holdings.
const source=result.scenarios.find(s=>s.symbol==='AAA');assert.ok(source);
assert.equal(source.amount,5000);
// Derived independently from the ten declared weights and 75/25 rollup:
// gross weights A10000:B6000:Bank3000. At $1000 the combined risk remains41,
// but round(.75*41+.25*(42*10000+41*6000+8*3000)/19000) is40.
const oracle=[[0,50,41],[1000,42,40],[2000,41,39],[2500,41,39],[5000,41,34],[10000,8,29]];
for(const [amount,account,total] of oracle){
 const projected=engine.project(raw,source,amount,{calculate});
 assert.equal(projected.accountAfter.score,account,JSON.stringify({amount,projected}));
 assert.equal(projected.totalAfter.score,total,JSON.stringify({amount,projected}));
 assert.equal(projected.quantity,amount/100);
 assert.equal(projected.cashAfter,amount);
 assert.equal(projected.totalAfter.net_equity,19000);
}
assert.equal(engine.project(raw,source,0,{calculate}).improves,false);
for(const amount of [-1,10001,Infinity,null,''])assert.throws(()=>engine.project(raw,source,amount,{calculate}));
assert.equal(JSON.stringify(raw),original);
''')


def test_scope_ceiling_missing_data_and_candidate_evidence_are_honest():
    scenario_js(r'''
for(const maximum of [1,20]){
 const result=await engine.generate(raw,{calculate,maxScenarios:maximum});
 assert.equal(result.scenarios.length,Math.min(maximum,2));
 for(const row of result.scenarios)assert.ok(row.accountAfter.score<=row.accountBefore.score&&row.totalAfter.score<=row.totalBefore.score&&row.improves);
}
for(const maximum of [0,21,1.5,'5',null]){
 if(maximum===null)continue; // Null opts into the documented default.
 await assert.rejects(engine.generate(raw,{calculate,maxScenarios:maximum}));
}
const scoped=await engine.generate(raw,{calculate,accountId:'b'});
assert.equal(scoped.scenarios.length,1);assert.equal(scoped.scenarios[0].symbol,'BBB');
assert.equal(scoped.baseline.total.score,41);assert.equal(scoped.baseline.accounts.length,3);
for(const change of [c=>c.accounts[2].initial_cash=null,c=>delete c.items[1].holding.quantity,c=>delete c.items[1].holding.market_value,c=>delete c.items[1].holding.asset_class]){
 const missing=structuredClone(raw);change(missing);await assert.rejects(engine.generate(missing,{calculate}));
}
const mismatch=structuredClone(raw);mismatch.items[0].price_ranges['1y'].current=101;
const denied=await engine.generate(mismatch,{calculate});
assert.ok(!denied.scenarios.some(row=>row.symbol==='AAA'));
assert.equal(denied.excluded.find(row=>row.symbol==='AAA').code,'valuation_mismatch');
const stale=structuredClone(raw);stale.items[0].price_ranges['1y'].current_date='2026-01-01';
const dated=await engine.generate(stale,{calculate});
assert.equal(dated.scenarios.find(row=>row.symbol==='AAA').stale,true);
assert.equal(dated.scenarios.find(row=>row.symbol==='AAA').quoteDate,'2026-01-01');
''')


def test_cross_currency_proceeds_are_opt_in_and_preserve_base_equity():
    scenario_js(r'''
const ctx=structuredClone(raw);ctx.accounts[0].currency='EUR';ctx.base_currency='ILS';
ctx.fx.quotes=[{pair:'USD/ILS',quote:{rate:4}},{pair:'ILS/EUR',quote:{rate:.2}}];
const snapshots=[];
const calc=c=>{
 snapshots.push(structuredClone(c));
 const securities=c.items.reduce((n,i)=>n+i.holding.market_value*engine.rateToBase(c,i.holding.currency),0);
 const cash=c.accounts.reduce((n,a)=>n+a.initial_cash*engine.rateToBase(c,a.currency),0);
 return {total:{score:c.items[0].holding.quantity===100?80:70,net_equity:securities+cash,components:{}},accounts:c.accounts.map(a=>({key:a.id,risk:{score:50,components:{}}}))};
};
const blocked=await engine.generate(ctx,{calculate:calc});
assert.equal(blocked.excluded.find(s=>s.symbol==='AAA').code,'conversion_required');
const allowed=await engine.generate(ctx,{calculate:calc,convertProceeds:true});
const a=allowed.scenarios.find(s=>s.symbol==='AAA');assert.ok(a);
const projected=engine.project(ctx,a,1000,{calculate:calc,convertProceeds:true});
// 1USD=4ILS;1EUR=5ILS =>1000USD=800EUR, not1250EUR.
assert.equal(projected.proceedsAccount,800);assert.equal(projected.cashAfter,800);
assert.equal(projected.totalBefore.net_equity,76000);assert.equal(projected.totalAfter.net_equity,76000);
const missing=structuredClone(ctx);missing.fx.quotes=[];
await assert.rejects(engine.generate(missing,{calculate:calc,convertProceeds:true}));
''')


def test_async_regeneration_failure_and_old_user_responses_preserve_coherence():
    script = r'''
const assert=require('node:assert/strict');
const state={baseCurrency:'USD',auth:{user:{id:'one'}}};
const document={addEventListener(){}},$=()=>null;
let generate=async()=>({scenarios:[]});
const window={PortfolioRiskScenarios:{generate:(...args)=>generate(...args)}};
const derivativeHolding=()=>false,riskHistoryCalculate=()=>{};
let requests=[];const api=()=>new Promise((resolve,reject)=>requests.push({resolve,reject}));
const savedMaximum=new Map();const localStorage={getItem:key=>savedMaximum.get(key)??null};
''' + (ROOT/'web/risk-scenarios-ui.js').read_text() + r'''
renderRiskScenarios=()=>{};
(async()=>{
 assert.equal(riskScenarioStoredMaximum(),5);
 savedMaximum.set(riskScenarioStorageKey(),'8');assert.equal(riskScenarioStoredMaximum(),8);
 state.auth.user={id:'another'};assert.equal(riskScenarioStoredMaximum(),5);
 savedMaximum.set(riskScenarioStorageKey(),'21');assert.equal(riskScenarioStoredMaximum(),5);
 state.auth.user={id:'one'};
 const previous={marker:'old'},result={marker:'old',scenarios:[{id:'a',amount:1}]};
 riskScenariosView.context=previous;riskScenariosAccept(result);riskScenariosView.amounts.set('a','2');
 generate=async()=>{throw Error('bad new evidence');};
 const failed=loadRiskScenarios();requests.shift().resolve({marker:'bad'});await failed;
 assert.equal(riskScenariosView.context,previous);assert.equal(riskScenariosView.result,result);
 assert.equal(riskScenariosView.amounts.get('a'),'2');
 generate=async context=>({marker:context.marker,scenarios:[]});
 const older=loadRiskScenarios(),newer=loadRiskScenarios();
 requests[1].resolve({marker:'new'});await newer;requests[0].resolve({marker:'stale'});await older;requests=[];
 assert.equal(riskScenariosView.context.marker,'new');assert.equal(riskScenariosView.result.marker,'new');
 let resolveGenerate;generate=()=>new Promise(resolve=>resolveGenerate=resolve);
 const regenerating=regenerateRiskScenarios();assert.equal(riskScenariosView.loading,true);
 resolveGenerate({scenarios:[{id:'a',amount:100}]});await regenerating;
 assert.equal(riskScenariosView.amounts.get('a'),'100');assert.equal(riskScenariosView.loading,false);
 const oldUser=loadRiskScenarios();state.auth.user={id:'two'};resetRiskScenarios();
 requests.shift().resolve({marker:'old user'});await oldUser;
 assert.equal(riskScenariosView.context,null);assert.equal(riskScenariosView.result,null);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    result=subprocess.run(['node'],input=script,text=True,capture_output=True,cwd=ROOT)
    assert result.returncode==0,result.stderr


def browser_document(tmp_path, language):
    source=(ROOT/'web/app.js').read_text().replace(
        'initializeApp().catch(reportBackgroundError).finally(revealInitializedApp);','')
    setup=r'''
window.qa={errors:[],calls:[],context:QA_CONTEXT};
window.addEventListener('error',e=>qa.errors.push(e.message));
window.addEventListener('unhandledrejection',e=>qa.errors.push(String(e.reason)));
api=async path=>{qa.calls.push(path);if(path.startsWith('/api/portfolio/risk-scenarios/context'))return structuredClone(qa.context);return {items:[]};};
saveDashboardSettings=()=>{};appLog=()=>{};appWarn=()=>{};
state.auth.user={id:'qa',username:'qa',role:'Admin'};state.baseCurrency='USD';state.fxRates={};state.portfolioReady=true;
state.dashboard=defaultDashboard();state.localAccounts=structuredClone(qa.context.accounts);state.localTransactions=[];
state.items=structuredClone(qa.context.items);state.language=QA_LANGUAGE;
$('authOverlay').hidden=true;$('appShell').inert=false;$('appShell').removeAttribute('aria-hidden');revealInitializedApp();
PortfolioI18n.applyToDocument(state.language);PortfolioI18n.observe();
$('analyticsBoard').innerHTML=renderPortfolioValueDashboard(state.items);qa.ready=true;
'''.replace('QA_CONTEXT',json.dumps(raw_context())).replace('QA_LANGUAGE',json.dumps(language))
    (tmp_path/'app.js').write_text(source+'\n'+setup)
    page=(ROOT/'web/index.html').read_text()
    page=re.sub(r'<script src="https://[^\"]+"></script>','',page)
    for relative in re.findall(r'(?:src|href)="/([^"?]+)(?:\?[^\"]*)?"',page):
        asset=ROOT/'web'/relative
        if not asset.exists():continue
        if relative=='app.js':asset=tmp_path/'app.js'
        elif relative.endswith('.css'):
            target=tmp_path/Path(relative).name
            target.write_text(re.sub(r'@import\s+url\([^)]*\)\s*;','',asset.read_text()))
            asset=target
        page=re.sub(r'(["\'])/'+re.escape(relative)+r'(?:\?[^"\']*)?(["\'])',
                    lambda match:match[1]+asset.as_uri()+match[2],page)
    target=tmp_path/'risk-scenarios.html';target.write_text(page)
    return target


def browser_wait(evaluate,expression):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        if evaluate(expression):return
        time.sleep(.03)
    raise AssertionError('Browser condition did not complete: '+expression)


@pytest.mark.parametrize(('language','width'), [('en',1440),('en',390),('he',1440),('he',390)])
def test_browser_actual_model_interaction_localization_keyboard_and_layout(tmp_path,chromium,language,width):
    command,evaluate=chromium
    command('Emulation.setDeviceMetricsOverride',dict(width=width,height=1080,deviceScaleFactor=1,mobile=False))
    command('Page.navigate',{'url':browser_document(tmp_path,language).as_uri()})
    browser_wait(evaluate,'window.qa?.ready===true')
    assert evaluate('qa.errors')==[]
    assert evaluate("document.querySelectorAll('[data-open-risk-scenarios]').length")==3
    evaluate("document.querySelector('[data-open-risk-scenarios=\"\"]').click()")
    browser_wait(evaluate,"document.querySelectorAll('[data-risk-scenario-id]').length===2")
    assert evaluate("$('riskScenariosMax').value")=='5'
    assert evaluate("$('riskScenariosConvert').checked") is False
    assert evaluate('riskScenariosView.result.baseline.total.score')==41
    browser_wait(evaluate,"document.activeElement.id==='riskScenariosTitle'")
    # Keyboard edits execute actual input events and preserve the editor node/focus.
    evaluate("document.querySelector('[data-risk-scenario-id=\"0\"] [data-risk-scenario-amount]').focus()")
    command('Input.dispatchKeyEvent',{'type':'keyDown','key':'a','code':'KeyA','modifiers':2,'windowsVirtualKeyCode':65})
    command('Input.dispatchKeyEvent',{'type':'keyUp','key':'a','code':'KeyA','modifiers':2,'windowsVirtualKeyCode':65})
    command('Input.insertText',{'text':'1000'})
    browser_wait(evaluate,"riskScenariosView.result.scenarios.find(s=>s.id==='0').amount===1000")
    assert evaluate("riskScenariosView.result.scenarios.find(s=>s.id==='0').accountAfter.score")==42
    assert evaluate("riskScenariosView.result.scenarios.find(s=>s.id==='0').totalAfter.score")==40
    assert evaluate("document.activeElement.matches('[data-risk-scenario-amount]')")
    # Background dashboard replacement cannot affect the frozen coherent context.
    evaluate("state.items[0].holding.market_value=999999;state.localAccounts[0].initial_cash=-99999;state.fxRates={'USD/ILS':99};renderRiskScenarios()")
    assert evaluate("document.querySelector('[data-risk-scenario-id=\"0\"] [data-risk-scenario-amount]').value")=='1000'
    assert evaluate('riskScenariosView.context.items[0].holding.market_value')==10000
    evaluate("(()=>{const n=document.querySelector('[data-risk-scenario-id=\"0\"] [data-risk-scenario-amount]');n.value='0';n.dispatchEvent(new Event('input',{bubbles:true}));})()")
    assert evaluate("document.querySelectorAll('[data-risk-scenario-id]').length")==2
    assert evaluate("riskScenariosView.result.scenarios.find(s=>s.id==='0').improves") is False
    assert evaluate("document.querySelector('[data-risk-scenario-id=\"0\"] .risk-scenario-rationale').classList.contains('signal-missing')")
    evaluate("(()=>{const n=document.querySelector('[data-risk-scenario-id=\"0\"] [data-risk-scenario-amount]');n.value='-1';n.dispatchEvent(new Event('input',{bubbles:true}));})()")
    assert evaluate("document.querySelector('[data-risk-scenario-id=\"0\"] [data-risk-scenario-amount]').getAttribute('aria-invalid')")=='true'
    assert evaluate("document.querySelector('[data-risk-scenario-id=\"0\"] [data-risk-scenario-projection]').hidden")
    evaluate("(()=>{const n=document.querySelector('[data-risk-scenario-id=\"0\"] [data-risk-scenario-slider]');n.value='100';n.dispatchEvent(new Event('input',{bubbles:true}));})()")
    assert evaluate("riskScenariosView.result.scenarios.find(s=>s.id==='0').accountAfter.score")==8
    assert evaluate("riskScenariosView.result.scenarios.find(s=>s.id==='0').totalAfter.score")==29
    text=evaluate("$('riskScenariosModal').innerText")
    assert '12/11/2026' in text and '2026-11-12' not in text
    assert '12/11/2026' in evaluate("$('riskScenariosMeta').textContent")
    assert '12.11.2026' not in text
    if language=='he':
        for english in ['Sell amount','Account risk','Saved quote','Maximum scenarios','points','Quantity to sell','Snapshot captured']:
            assert english not in text
        assert 'סיכון' in text
    else:
        assert not re.search(r'[\u0590-\u05ff]',text)
    bounds=evaluate("(()=>{const d=$('riskScenariosModal').querySelector('[role=dialog]');return {left:d.getBoundingClientRect().left,right:d.getBoundingClientRect().right,width:d.clientWidth,scroll:d.scrollWidth};})()")
    assert bounds['left']>=0 and bounds['right']<=width and bounds['scroll']<=bounds['width']
    assert evaluate("[...document.querySelectorAll('[data-risk-scenario-amount]')].every(n=>n.clientWidth>=100)")
    image=command('Page.captureScreenshot',{'format':'png'})
    (tmp_path/f'risk-{language}-{width}.png').write_bytes(base64.b64decode(image['data']))
    # Config controls await actual asynchronous generation and preserve total scope.
    evaluate("$('riskScenariosMax').value='1';$('riskScenariosMax').dispatchEvent(new Event('change',{bubbles:true}))")
    browser_wait(evaluate,"!riskScenariosView.loading&&document.querySelectorAll('[data-risk-scenario-id]').length===1")
    evaluate("$('riskScenariosAccount').value='b';$('riskScenariosAccount').dispatchEvent(new Event('change',{bubbles:true}))")
    browser_wait(evaluate,"!riskScenariosView.loading&&riskScenariosView.result.scenarios[0]?.symbol==='BBB'")
    assert evaluate('riskScenariosView.result.baseline.total.score')==41
    assert evaluate('riskScenariosView.context.accounts.length')==3
    assert evaluate('qa.calls.every(path=>path.startsWith("/api/portfolio/risk-scenarios/context"))')
    assert evaluate('qa.errors')==[]
    # An actual background dashboard redraw replaces the original launch node.
    evaluate("qa.oldOpener=document.querySelector('[data-open-risk-scenarios=\"\"]');$('analyticsBoard').innerHTML=renderPortfolioValueDashboard(state.items)")
    assert evaluate('qa.oldOpener.isConnected') is False
    assert evaluate('riskScenariosView.result.baseline.total.score')==41
    # Escape closes, and the modal returns focus to its replacement launch button.
    command('Input.dispatchKeyEvent',{'type':'keyDown','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
    command('Input.dispatchKeyEvent',{'type':'keyUp','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
    browser_wait(evaluate,"$('riskScenariosModal').hidden")
    browser_wait(evaluate,"document.activeElement.matches('[data-open-risk-scenarios]')")


def test_capture_clock_freezes_derived_age_and_jerusalem_ledger_cutoff():
    scenario_js(r'''
const ctx=structuredClone(raw);ctx.observed_at='2026-11-11T22:30:00Z';ctx.date='2026-11-12';
ctx.accounts[0].persons=[{birth_date:'2000-01-01',retire_age:67}];
for(const item of ctx.items)item.price_ranges['1y'].current_date='2026-11-11';
ctx.transactions=[{account_db_id:'a',action:'CASH_IN',quantity:50,price:1,currency:'USD',trade_date:'2026-11-12'}];
let ages=[];
const calc=c=>{ages.push(c.accounts[0].persons[0].age);return calculate(c);};
const original=JSON.stringify(ctx),result=await engine.generate(ctx,{calculate:calc});
const a=result.scenarios.find(row=>row.symbol==='AAA');assert.ok(a);assert.equal(a.cashBefore,50);
const first=engine.project(ctx,a,1000,{calculate:calc});
const age=ages[0];assert.ok(age>26&&age<27);
const RealDate=Date;globalThis.Date=class extends RealDate{
 constructor(...args){super(...(args.length?args:['2035-01-01T12:00:00Z']));}
 static now(){return RealDate.parse('2035-01-01T12:00:00Z');}
};
const later=engine.project(ctx,a,1000,{calculate:calc});globalThis.Date=RealDate;
assert.equal(later.accountAfter.score,first.accountAfter.score);assert.equal(later.totalAfter.score,first.totalAfter.score);
assert.ok(ages.every(value=>value===age));assert.equal(JSON.stringify(ctx),original);
const future=structuredClone(ctx);future.transactions[0].trade_date='2026-11-13';
await assert.rejects(engine.generate(future,{calculate:calc}),/future_transactions/);
''')
