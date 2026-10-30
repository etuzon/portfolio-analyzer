"""Behavioral regressions for long refreshes, transport recovery and stale responses."""
from pathlib import Path
import subprocess
import re
import json

SOURCE=Path(__file__).resolve().parents[1] / 'web/app.js'

def run_js(body):
    source=SOURCE.read_text()
    start=source.index('let portfolioEnrichment')
    end=source.index('\nasync function loadLocalOptions',start)
    script=source[start:end]+'''\nconst assert=require('node:assert/strict');
const nodes={};
const $=(id)=>nodes[id] ||= {hidden:true};
const state={items:[],baseCurrency:'USD'};
const HISTORY_START_DATE='2020-01-01';
const todayString=()=> '2026-10-30';
let loadingBalance=0;
const setLoading=(active)=>{loadingBalance+=active?1:-1;};
const setCoreFxRates=()=>{};
const appLog=()=>{};
const appWarn=()=>{};
const optionLabel=(x)=>x;
const t=(x)=>x;
const portfolioItems=(items)=>items;
const isEquityCompAccount=()=>false;
const populateOptions=()=>{};
const renderPortfolio=()=>{};
const renderMacroScenario=()=>{};
const hasActivePortfolioFilter=()=>false;
const pending=new Map();let timerCounter=0;
const setTimeout=(callback)=>{pending.set(++timerCounter,callback);return timerCounter;};
const clearTimeout=(id)=>pending.delete(id);
const window={setTimeout,clearTimeout};
const otherApi=async(path)=>path.includes('account-trends') ? {accounts:[]} : {items:[],quotes:[]};
const payload=(qty,pendingFlag=false)=>({count:1,items:[{holding:{symbol:'FDUS',quantity:qty}}],status:{portfolio_cache:'fixture'},refresh_pending:pendingFlag});
async function tick(){assert.equal(pending.size,1,'loading must retain exactly one scheduled retry');const [id,callback]=pending.entries().next().value;pending.delete(id);await callback();await new Promise(resolve=>setImmediate(resolve));}
'''+body
    result=subprocess.run(['node'],input=script,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    assert 'completed' in result.stdout, 'async regression did not reach its terminal assertion'


def test_continues_loading_after_forty_pending_responses():
    run_js('''
let calls=0;
const api=async(path)=>path.startsWith('/api/portfolio') ? payload(++calls,calls<=45) : otherApi(path);
(async()=>{await loadPortfolio();for(let i=0;i<45;i++)await tick();assert.equal(calls,46);assert.equal(state.items[0].holding.quantity,46);assert.equal(pending.size,0);console.log('completed');})().catch(error=>{console.error(error);process.exitCode=1;});
''')


def test_transient_transport_failure_keeps_retrying_until_completion():
    run_js('''
let calls=0;
const api=async(path)=>{if(!path.startsWith('/api/portfolio'))return otherApi(path);++calls;if(calls===2)throw new Error('temporary disconnect');return payload(calls,calls<3);};
(async()=>{await loadPortfolio();await tick();await tick();assert.equal(calls,3);assert.equal(state.items[0].holding.quantity,3);assert.equal(pending.size,0);console.log('completed');})().catch(error=>{console.error(error);process.exitCode=1;});
''')


def test_manual_refresh_keeps_polling_and_terminal_failure_offers_retry():
    run_js('''
let calls=0;const paths=[];
const api=async(path)=>{
 if(!path.startsWith('/api/portfolio'))return otherApi(path);
 paths.push(path);calls++;
 return calls<3?payload(12,true):{...payload(12),refresh_state:'failed'};
};
(async()=>{
 await loadPortfolio({refresh:true});await tick();await tick();
 assert.ok(paths[0].includes('refresh=true'));assert.equal(paths[1],'/api/portfolio');
 assert.equal(state.items[0].holding.quantity,12);assert.equal(pending.size,0);
 assert.ok($('status').textContent.includes('Use Refresh to retry'));
 console.log('completed');
})().catch(error=>{console.error(error);process.exitCode=1;});
''')


def test_late_old_response_does_not_replace_new_transaction_state():
    run_js('''
let calls=0;let firstResolve,secondResolve;
const api=async(path)=>{if(!path.startsWith('/api/portfolio'))return otherApi(path);return new Promise(resolve=>{if(++calls===1)firstResolve=resolve;else secondResolve=resolve;});};
(async()=>{const old=loadPortfolio();const current=loadPortfolio();secondResolve(payload(20));await current;firstResolve(payload(10));await old;assert.equal(state.items[0].holding.quantity,20,'old response replaced more recent portfolio reload');console.log('completed');})().catch(error=>{console.error(error);process.exitCode=1;});
''')


def test_overlapping_requests_release_loading_state_for_every_started_request():
    run_js('''
let calls=0;let firstResolve,secondResolve;
const api=async(path)=>{if(!path.startsWith('/api/portfolio'))return otherApi(path);return new Promise(resolve=>{if(++calls===1)firstResolve=resolve;else secondResolve=resolve;});};
(async()=>{const old=loadPortfolio();const current=loadPortfolio();secondResolve(payload(20));await current;firstResolve(payload(10));await old;assert.equal(loadingBalance,0,'a superseded request leaked the active loading count');console.log('completed');})().catch(error=>{console.error(error);process.exitCode=1;});
''')


def functions(*names):
    source=SOURCE.read_text()
    results=[]
    for name in names:
        start=re.search(rf'^function {name}\(',source,re.M).start()
        end=re.search(r'^}',source[start:],re.M).end()
        results.append(source[start:start+end])
    return '\n'.join(results)


def test_pending_and_failed_metrics_do_not_display_missing_zero_or_complete():
    script=functions('analyticsStateCell','trendCell','rangeCell','technicalsCell','statusCell','renderCompleteness')+"""
const assert=require('node:assert/strict');const t=x=>x;const esc=x=>String(x);const colorAt=()=> 'blue';
for(const state of ['pending','error']){
 const trend=trendCell({state},'Net profit');
 const range=rangeCell({state},'USD');
 const levels=technicalsCell({state},{},'USD',30);
 for(const html of [trend,range,levels]){
  assert.ok(!html.includes('Missing'));assert.ok(!html.includes('$0'));
  assert.ok(html.includes(state==='pending'?'Loading':'could not be updated'));
 }
}
assert.ok(statusCell({analytics_state:'refreshing',missing:[]}).includes('Updating analytics'));
assert.ok(!statusCell({analytics_state:'refreshing',missing:[]}).includes('All displayed data available'));
const coverage=renderCompleteness([{missing:[],price_ranges:{'1y':{state:'pending'}},profit_trend:{state:'pending'},dividend_trend:{state:'pending'}}]);
assert.ok(!coverage.includes('100%'));assert.ok(coverage.includes('0%'));
"""
    result=subprocess.run(['node'],input=script,text=True,capture_output=True)
    assert result.returncode==0,result.stderr


def test_financial_refresh_states_are_localized():
    labels=['Loading financial data','Loading price history','Financial data could not be updated','Price history could not be updated',
            'Update failed','Updating analytics','Updating analytics in the background',
            'Connection interrupted. Retrying the analytics update.','Financial data could not be updated. Use Refresh to retry.',
            'Analytics updated','portfolio positions','portfolio positions matched',
            'Saved data · awaiting update','Saved data · updating','Awaiting update','securities completed',
            'securities updated','Update finished','updates failed. Use Refresh to retry.']
    js='const window={};'+(SOURCE.parent/'i18n.js').read_text()+'\nconst labels='+json.dumps(labels)+";console.log(JSON.stringify(labels.map(x=>window.PortfolioI18n.translate(x,'he'))));"
    result=subprocess.run(['node'],input=js,text=True,capture_output=True,check=True)
    assert all(re.search('[א-ת]',label) and not re.search('[A-Za-z]',label) for label in json.loads(result.stdout))


def test_dashboard_replacement_preserves_expanded_stats_and_row_keyboard_focus():
    script=functions('preserveRenderedInteraction')+"""
const assert=require('node:assert/strict');
const document={activeElement:null};let restored=false;
const attrs=[{name:'data-security-detail-symbol',value:'FDUS'},{name:'data-security-detail-market-key',value:'NASDAQ'},{name:'data-position-action',value:'SELL'}];
const oldButton={tagName:'BUTTON',className:'symbol',attributes:attrs,isConnected:true,
 closest:()=>({dataset:{portfolioPosition:'account-fdus'}})};
const other={dataset:{portfolioPosition:'other-stock'},querySelectorAll:()=>[]};
const newButton={tagName:'BUTTON',className:'symbol',getAttribute:name=>attrs.find(a=>a.name===name)?.value,
 focus:options=>{assert.equal(options.preventScroll,true);restored=true;document.activeElement=newButton;}};
const buyButton={...newButton,getAttribute:name=>name==='data-position-action'?'BUY':newButton.getAttribute(name),focus:()=>{throw Error('focus changed Sell to Buy');}};
const row={dataset:{portfolioPosition:'account-fdus'},querySelectorAll:()=>[buyButton,newButton]};
let nodes=[{open:true,className:'summary-drawer',id:''}];
const root={contains:node=>node===oldButton,querySelectorAll:selector=>selector==='details'?nodes:[other,row]};
document.activeElement=oldButton;
const restore=preserveRenderedInteraction(root);
oldButton.isConnected=false;document.activeElement={tagName:'BODY'};
nodes=[{open:false,className:'summary-drawer',id:''}];
restore();assert.equal(nodes[0].open,true);assert.equal(restored,true);
assert.equal(document.activeElement,newButton,'focus follows its stock identity, not its old row index');
"""
    result=subprocess.run(['node'],input=script,text=True,capture_output=True)
    assert result.returncode==0,result.stderr


def test_unique_security_progress_and_partial_failure_are_reported_truthfully():
    run_js('''
let calls=0;
const api=async(path)=>{
 if(!path.startsWith('/api/portfolio'))return otherApi(path);
 calls++;
 return {...payload(12,calls===1),refresh_state:calls===1?'refreshing':'failed',
  refresh_progress:{total:2,completed:calls===1?1:2,failed:calls===1?0:1}};
};
(async()=>{
 await loadPortfolio();assert.ok($('status').textContent.includes('1/2 securities completed'));
 await tick();assert.equal(pending.size,0);assert.ok($('status').textContent.includes('1/2 securities updated'));
 assert.ok($('status').textContent.includes('1 updates failed'));assert.ok(!$('status').textContent.includes('Analytics updated'));
 console.log('completed');
})().catch(error=>{console.error(error);process.exitCode=1;});
''')


def test_hebrew_mobile_labels_and_dividend_unit_use_shared_localization():
    source=(SOURCE.parent/'i18n.js').read_text()
    assert '"data-label"' in re.search(r'const TRANSLATABLE_ATTRIBUTES = (.*);',source).group(1)
    script='const window={};'+source+"\nconst assert=require('node:assert/strict');"+functions('formatMetricValue')+"""
const t=x=>window.PortfolioI18n.translate(x,'he');const money=()=> '2.00';
const result=formatMetricValue(2,'dividend','USD');
assert.ok(result.includes('מניה'));assert.ok(!result.includes('share'));
"""
    result=subprocess.run(['node'],input=script,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
