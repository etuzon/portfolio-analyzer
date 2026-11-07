"""Independent alarm acceptance checks with synthetic, non-user portfolio data.

Exercises the actual alarm helper and shared risk calculation. Browser fixtures
use repository HTML/CSS/translation and isolated Chromium; no real user session
or financial API is touched.
"""

import base64
import json
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

from test_shared_cash_risk_qa import app_functions


ROOT = Path(__file__).resolve().parents[1]
CHROME = shutil.which("google-chrome") or shutil.which("chromium")
FUNCTIONS = (
    "t", "alarmText", "alarmValue", "alarmDueText", "eventDaysFromToday",
    "dividendAlarmMessage", "dividendAlarms", "vestingAlarms", "alarmDismissalId",
    "currentAlarms", "clearAlarms", "renderAlarms", "isEquityCompAccount",
    "isEquityCompHolding", "portfolioItems", "portfolioAccounts", "checkedAccountShareAmount",
    "riskBand", "riskScoreForItems", "assetRiskFactor", "derivativeHolding", "diversifiedFund",
    "industryLabel", "issuerLabel", "countryLabel", "economicCurrencyExposure", "volatilityProxy",
    "portfolioRiskSnapshot", "accountCashBalance", "accountRiskCashValue", "accountHorizonYears",
    "personHorizonYears", "cleanSourceLabel", "accountRecordForHolding",
    "currentUser", "canWrite",
)


def source_js():
    return app_functions(*FUNCTIONS) + "\n" + (ROOT / "web/alarm-priority-ui.js").read_text()


SETUP = r'''
const TRANSLATIONS={en:{},he:{}};
const state={language:'en',baseCurrency:'USD',localEvents:[],items:[],allPortfolioItems:[],
 localAccounts:[],localTransactions:[],fxRates:{},dismissedAlarmIds:[],vestingAlertDays:30,
 auth:{user:{role:'Operator'}},portfolioReady:true,portfolioRefreshPending:false,portfolioSourceState:'ready',
 alarmsEventsLoaded:true,alertData:{active_signals:[]},alertClientDismissals:[]};
const sum=values=>values.reduce((a,b)=>a+b,0);
const fmt=n=>String(n);
const money=(n,c,d=2)=>`${c} ${Number(n).toFixed(d)}`;
const normalizedField=(item,field)=>normalizedAmount(item.holding[field],item.holding.currency);
const normalizedAmount=(value,currency)=>checkedAccountShareAmount(value,currency)??Number(value);
const optionLabel=value=>t(value);
const clamp=(v,a,b)=>Math.max(a,Math.min(v,b));
const normalizedVestingAlertDays=v=>Number(v);
const ageFromBirthDate=()=>46;
const formatDate=v=>String(v||'').split('-').reverse().join('/');
const esc=v=>String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const equityCompLots=()=>[];
const riskAllocationForItems=()=>[];
const parseDateInput=v=>/^\d{4}-\d{2}-\d{2}$/.test(String(v||''))?v:'';
const todayString=()=> '2026-11-06';
const saveAlarmDismissals=()=>{};
const transactionCashImpact=tx=>Number(tx.cash_impact||0);
const stock=(symbol='QA',value=10000,account='qa')=>({
 analytics_state:'ready',holding:{symbol,account_id:account,quantity:value/100,market_value:value,
 currency:'USD',stock_market:'NASDAQ',asset_class:'EQUITY',sector:'Technology',industry:'Technology'},
 exchange:'NASDAQ',industry:'Technology',missing:[],
 price_ranges:{'1m':{current:100,current_date:'2026-11-06'},'1y':{current:100,high:120,min:80,current_date:'2026-11-06'}}});
const account=(id='qa',cash=0,type='Investment')=>({id,account_id:id,initial_cash:cash,currency:'USD',type,
 persons:[{age:47,retire_age:67}]});
const event=(overrides={})=>({id:'qa-event',type:'DIVIDEND',symbol:'QA',status:'pending',
 event_date:'2099-11-06',currency:'USD',gross_amount:20,tax_amount:5,net_amount:15,
 details:{gross_per_share:2,shares:10},...overrides});
'''


def run_js(body):
    script = (
        "const assert=require('node:assert/strict');const window={};\n"
        + (ROOT / "web/i18n.js").read_text()
        + r'''
const nodes=Object.fromEntries(['alarmsButton','alarmsCount','alarmsPrioritySymbol','alarmPrioritySummary',
 'alarmsStatus','clearAlarms','alarmSettingsStatus','vestingAlertDays','alarmsList'].map(id=>[id,{
 textContent:'',innerHTML:'',dataset:{},classList:{toggle(){}},setAttribute(k,v){this[k]=v}}]));
const $=id=>nodes[id];
const document={addEventListener(){},activeElement:null};
'''
        + SETUP + source_js() + "\n" + body
    )
    result = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_priority_grouping_dismissal_event_clear_and_source_immutability():
    run_js(r'''
state.localAccounts=[account()];state.allPortfolioItems=[stock()];
state.alertData.active_signals=[
 {symbol:'QA',signal:'buy',rule_name:'Rule A'}, {symbol:'qa',signal:'buy',rule_name:'Rule B'},
 {symbol:'QA',signal:'sell',rule_name:'Rule C'}, {symbol:'WATCH',signal:'watch'}];
state.localEvents=[event(),event({id:'recorded',status:'processed',transaction_id:'tx'})];
const original=JSON.stringify({accounts:state.localAccounts,items:state.allPortfolioItems,
 signals:state.alertData,events:state.localEvents});
const groups=portfolioSignalAlarms();
assert.equal(groups.length,3);assert.equal(groups.find(x=>x.signalType==='buy').matches.length,2);
assert.equal(alarmAppearance(groups.find(x=>x.signalType==='sell')).tone,'red');
assert.equal(alarmAppearance(groups.find(x=>x.signalType==='buy')).tone,'green');
assert.equal(alarmAppearance(groups.find(x=>x.signalType==='watch')).tone,'amber');
renderAlarms();assert.equal(nodes.alarmsButton.dataset.alarmTone,'red');
assert.equal(nodes.alarmsCount.textContent,'7');
clearSelectedAlarms({key:'dividend:qa-event'});clearSelectedAlarms({key:'dividend:recorded'});
assert.equal(nodes.alarmsCount.textContent,'5');
assert.equal(nodes.alarmsButton.dataset.alarmTone,'red');assert.equal(nodes.clearAlarms.disabled,false);
assert.equal(JSON.stringify({accounts:state.localAccounts,items:state.allPortfolioItems,
 signals:state.alertData,events:state.localEvents}),original);
state.alertClientDismissals=[{symbol:'QA',signal:'sell',expires_at:'2099-01-01T00:00:00Z'}];
assert.equal(portfolioSignalAlarms().some(x=>x.signalType==='sell'),false);
state.alertClientDismissals[0].expires_at='2000-01-01T00:00:00Z';
assert.equal(portfolioSignalAlarms().some(x=>x.signalType==='sell'),true);
''')


def test_shared_risk_boundaries_raw_borrowing_and_canonical_unfiltered_scope():
    run_js(r'''
for(const [score,expected] of [[0,'low'],[20,'low'],[21,'moderate'],[40,'moderate'],
 [41,'elevated'],[60,'elevated'],[61,'high'],[80,'high'],[81,'extreme'],[100,'extreme']]){
 assert.equal(riskBand(score).key,expected);
}
state.localAccounts=[account()];state.allPortfolioItems=[stock()];state.items=[];
let alarms=portfolioRiskAlarms();
assert.equal(alarms.length,2);assert.ok(alarms.every(x=>x.risk.score===50&&x.level==='elevated'));
state.localAccounts[0].initial_cash=-1000;
alarms=portfolioRiskAlarms();assert.ok(alarms.every(x=>x.risk.score===55));
state.localAccounts[0].initial_cash=-10000;
alarms=portfolioRiskAlarms();assert.ok(alarms.every(x=>x.risk.score===100&&alarmAppearance(x).tone==='red'));
state.allPortfolioItems.push({...stock('ESOP',100000000,'esop'),analytics_state:'pending'});
state.localAccounts.push(account('esop',-10000000,'ESOP'));
assert.deepEqual(portfolioRiskAlarms().map(x=>x.risk.score),[100,100]);
state.localAccounts=[account('pension',-10,'Long-Term Savings')];state.allPortfolioItems=[];
alarms=portfolioRiskAlarms();assert.equal(alarms.length,2);
assert.ok(alarms.every(x=>x.risk.score===100));
state.localAccounts=[];state.allPortfolioItems=[];
assert.deepEqual(portfolioRiskAlarms(),[]);renderAlarms();
assert.equal(nodes.alarmsButton.dataset.alarmTone,'neutral');
assert.ok(!nodes.alarmsStatus.textContent.match(/safe|risk.free/iu));
''')


def test_missing_inputs_pending_failures_and_recovery_never_claim_clean():
    run_js(r'''
state.localAccounts=[account()];state.allPortfolioItems=[stock()];
const original=structuredClone(state.allPortfolioItems[0]);
for(const mutation of [
 x=>x.analytics_state='pending',x=>x.analytics_state=null,x=>x.holding.quantity=null,x=>x.holding.quantity='100',
 x=>x.holding.market_value=NaN,x=>x.holding.market_value=Infinity,x=>x.holding.market_value=0,
 x=>x.holding.currency='EUR',x=>x.holding.currency=''
]){
 state.allPortfolioItems=[structuredClone(original)];mutation(state.allPortfolioItems[0]);
 const alarms=portfolioRiskAlarms();assert.equal(alarms.length,1);assert.equal(alarms[0].level,'unavailable');
 renderAlarms();assert.equal(nodes.alarmsButton.dataset.alarmTone,'amber');
}
state.allPortfolioItems=[original];state.portfolioRefreshPending=true;
assert.equal(portfolioRiskAlarms()[0].level,'updating');
state.portfolioRefreshPending=false;state.portfolioSourceState='failed';
assert.equal(portfolioRiskAlarms()[0].level,'unavailable');
state.portfolioSourceState='ready';assert.ok(portfolioRiskAlarms().every(x=>x.level==='elevated'));
delete state.allPortfolioItems[0].analytics_state;
assert.ok(portfolioRiskAlarms().every(x=>x.level==='elevated')); // Manual rows omit this optional field.
state.allPortfolioItems=[];state.localAccounts=[];
for(const flag of ['alarmsLoadFailed','alarmSignalsLoadFailed','portfolioAlarmLoadFailed']){
 state[flag]=true;renderAlarms();assert.equal(nodes.alarmsButton.dataset.alarmTone,'amber');
 assert.ok(!nodes.alarmsStatus.textContent.includes('No current alarms.'));state[flag]=false;
}
state.localEvents=[event({status:'processed',transaction_id:'tx'})];
state.portfolioAlarmLoadFailed=true;renderAlarms();
assert.equal(nodes.alarmsButton.dataset.alarmTone,'amber');assert.equal(nodes.alarmsCount.textContent,'1');
state.portfolioAlarmLoadFailed=false;renderAlarms();assert.equal(nodes.alarmsButton.dataset.alarmTone,'green');
state.localEvents=[];
state.alarmsEventsLoaded=false;renderAlarms();assert.equal(nodes.alarmsButton.dataset.alarmTone,'amber');
state.alarmsEventsLoaded=true;state.alertData=null;renderAlarms();assert.equal(nodes.alarmsButton.dataset.alarmTone,'amber');
state.alertData={active_signals:[]};renderAlarms();assert.equal(nodes.alarmsButton.dataset.alarmTone,'neutral');
''')


def test_dividend_evidence_cash_claims_and_bad_status_dates():
    run_js(r'''
for(const status of ['failed','skipped','unknown','',null]){
 const alarm={event:event({status}),...dividendAlarmMessage(event({status}))};
 assert.equal(alarmAppearance(alarm).tone,'amber');
 assert.ok(!alarm.title.includes('payment recorded'));
}
for(const event_date of ['',null,'invalid','2026-02-30','2026-13-01','06/11/2026']){
 for(const status of ['processed','pending']){
  const e=event({event_date,status});assert.equal(alarmAppearance({event:e,...dividendAlarmMessage(e)}).tone,'amber');
 }
}
let e=event({event_date:'2001-11-06'});let message=dividendAlarmMessage(e);
assert.equal(alarmAppearance({event:e,...message}).tone,'amber');assert.ok(!/unpaid/iu.test(message.title+message.body));
e=event();assert.equal(alarmAppearance({event:e,...dividendAlarmMessage(e)}).tone,'blue');
e=event({status:'processed',transaction_id:'tx'});message=dividendAlarmMessage(e);
assert.equal(alarmAppearance({event:e,...message}).tone,'green');assert.match(message.body.replace(/[\u2066-\u2069]/gu,''),/Recorded USD 15.00 in local cash/);
for(const overrides of [{transaction_id:null},{transaction_id:'tx',net_amount:0},{transaction_id:'tx',net_amount:-1}]){
 e=event({status:'processed',...overrides});message=dividendAlarmMessage(e);
 assert.equal(alarmAppearance({event:e,...message}).tone,'green');assert.ok(!/Recorded .* in local cash/.test(message.body));
}
''')


def test_incomplete_buy_stays_amber_and_all_new_appearance_labels_translate():
    run_js(r'''
state.alertData.active_signals=[{symbol:'BUYQA',signal:'buy',missing_metrics:['revenue']}];
assert.equal(alarmAppearance(portfolioSignalAlarms()[0]).tone,'amber');
for(const alarm of [
 {kind:'signal',signalType:'buy'},{kind:'signal',signalType:'sell'},{kind:'signal',signalType:'watch'},
 ...['high','extreme','elevated','borrowing','limited','unavailable','updating'].map(level=>({kind:'risk',level})),
 {kind:'vesting'},{tone:'unconfirmed'},{event:{status:'pending'}},{event:{status:'processed'}}
]){
 const label=alarmAppearance(alarm).label;state.language='he';assert.match(t(label),/[א-ת]/u,label);
 state.language='en';assert.ok(!/[א-ת]/u.test(t(label)),label);
}
''')


def test_incomplete_buy_group_cannot_hide_amber_or_required_opening_cash():
    run_js(r'''
const complete={symbol:'COMPLETE',signal:'buy'};
const incomplete={symbol:'INCOMPLETE',signal:'buy',missing_metrics:['revenue']};
for(const signals of [[complete,incomplete],[incomplete,complete]]){
 state.alertData.active_signals=signals;renderAlarms();
 assert.equal(nodes.alarmsButton.dataset.alarmTone,'amber');
 assert.match(nodes.alarmPrioritySummary.innerHTML,/data-alarm-tone="amber"/u);
 assert.match(nodes.alarmPrioritySummary.innerHTML,/<b>2<\/b>/u);
}
for(const cash of [null,undefined,'',NaN,Infinity,-Infinity]){
 state.localAccounts=[account()];state.localAccounts[0].initial_cash=cash;
 assert.equal(portfolioRiskAlarms()[0].level,'unavailable');
}
state.localAccounts=[account('qa',0)];state.alertData.active_signals=[];
assert.deepEqual(portfolioRiskAlarms(),[]);
''')


def test_unconfirmed_dates_and_statuses_do_not_inflate_scheduled_or_recorded_summary():
    run_js(r'''
state.localEvents=[event({event_date:'2000-01-01'}),event({id:'bad',event_date:'invalid'}),
 event({id:'bad-recorded',status:'processed',event_date:'invalid'}),event({id:'failed',status:'failed'})];
for(const language of ['en','he']){
 state.language=language;renderAlarms();
 assert.equal(nodes.alarmsCount.textContent,'4');
 assert.equal(nodes.alarmsButton.dataset.alarmTone,'amber');
 if(language==='en'){
  assert.ok(!/[1-9]\d* (?:scheduled|recorded) dividend/u.test(nodes.alarmsStatus.textContent));
  assert.match(nodes.alarmPrioritySummary.innerHTML,/Dividend payment unconfirmed/);
  assert.match(nodes.alarmPrioritySummary.innerHTML,/<b>4<\/b>/);
 }else assert.ok(!/[A-Za-z]/u.test(nodes.alarmsStatus.textContent));
}
state.language='en';const message=dividendAlarmMessage(event({status:'processed',transaction_id:'tx'}));
assert.ok(!/Paid /u.test(message.meta));
''')


def test_alarm_help_is_fully_translated_and_matches_financial_claim_boundaries():
    html = (ROOT / 'web/index.html').read_text()
    section = html.split('<h3>Portfolio alarms</h3>',1)[1].split('</article>',1)[0]
    paragraphs = [re.sub(r'<[^>]+>','',text).replace('&amp;','&')
                  for text in re.findall(r'<p>(.*?)</p>',section,re.S)]
    run_js('const paragraphs='+json.dumps(paragraphs)+';'+r'''
state.language='he';
for(const paragraph of paragraphs){assert.notEqual(t(paragraph),paragraph);assert.match(t(paragraph),/[א-ת]/u)}
state.language='en';for(const paragraph of paragraphs)assert.ok(!/[א-ת]/u.test(t(paragraph)));
assert.ok(paragraphs.some(x=>x.includes('does not mean an investment is safe')));
assert.ok(paragraphs.some(x=>x.includes('Clearing hides notices without changing holdings, transactions or risk scores')));
assert.ok(paragraphs.some(x=>x.includes('not that external broker settlement was verified')));
''')


def browser_fixture(directory, language):
    """Build a synthetic fixture using real HTML and the actual click/key handlers."""
    source = (ROOT / "web/app.js").read_text()
    html = (ROOT / "web/index.html").read_text()
    html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
    html = re.sub(r'<link\b[^>]*>', '', html)
    html = html.replace('<head>', '<head><link rel="stylesheet" href="styles.css">')
    html = html.replace(' class="i18n-pending"', '')
    constants = source[source.index('const WRITE_CONTROL_IDS ='):source.index('\nfunction currentUser()')]
    handler_start = source.index('document.addEventListener("keydown", (event) => {', source.index('function closeModal('))
    handler_end = source.index('\n});', source.index('document.addEventListener("click", (event) => {', handler_start)) + 4
    handlers = source[handler_start:handler_end]
    permission_start = source.index('const rolePermissionObserver =')
    permissions = source[permission_start:source.index('\n\nfunction setAppAuthenticationLock', permission_start)]
    extra = app_functions(
        "renderAlerts", "alertRunIsActive", "setResearchSection", "setMobileNavigation",
        "openModal", "closeModal", "mountModalHomeLink", "positionModalHomeLinks",
        "focusModalDestination", "moveWorkspaceTab", "preserveRenderedInteraction",
        "currentUser", "canWrite", "canAdmin", "isWriteControl", "applyRolePermissions", "riskTooltip",
    )
    setup = SETUP.replace('const equityCompLots=()=>[];', "const equityCompLots=kind=>kind==='rsu'?[{symbol:'RSUQA',transactionId:'rsu-qa',quantity:30,vestDate:'2026-11-06'}]:[];") + r'''
const $=id=>document.getElementById(id);
const modalReturnFocus=new Map();
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const scheduleAlertRefresh=()=>{};
const loadAlerts=async()=>renderAlerts(state.alertData,{signalsOnly:true});
const loadEvents=async()=>{};
async function dismissAlertSignal(symbol,signal){
 state.alertClientDismissals.push({symbol,signal,expires_at:'2099-01-01T00:00:00Z'});
 renderAlarms();
}
const loadCompanyOutlookHistory=async()=>{};
const formatDateTime=()=> '06/11/2026';
const alertReasonText=()=>'';
const alertMetric=key=>({label:key});
const renderAlertConditions=()=>{};
const resetAlertForm=()=>{};
state.auth={user:{role:'Viewer'}};state.alertOptions={};state.alertConditions=[];
window.qaErrors=[];window.qaNetwork=[];
window.addEventListener('error',event=>qaErrors.push(event.message));
window.fetch=(...args)=>{qaNetwork.push(args);throw Error('Synthetic fixture prohibits network requests')};
$('authOverlay').hidden=true;$('appShell').inert=false;$('appShell').removeAttribute('aria-hidden');
$('currentUserName').textContent='Synthetic Viewer';$('currentUserRole').textContent='Viewer';
state.localAccounts=[account('qa',-10000)];state.allPortfolioItems=[stock()];
state.alertData={active_signals:[{symbol:'SAME',signal:'buy',rule_name:'Synthetic buy',matched_at:'2026-11-06'},
 {symbol:'SAME',signal:'sell',rule_name:'Synthetic sell',matched_at:'2026-11-06'},
 {symbol:'LONGSYMBOLWITHAVERYLONGUNBROKENNAME',signal:'watch',rule_name:'Synthetic long name '.repeat(5)}],rules:[],runs:[]};
state.localEvents=Array.from({length:99},(_,i)=>event({id:`pending-${i}`}));
state.localEvents.push(event({id:'recorded-local',status:'processed',transaction_id:'recorded-transaction',event_date:'2026-11-06'}));
const label=document.createElement('p');label.textContent='SYNTHETIC QA FIXTURE';label.style.cssText='color:#ffd17a;font-weight:800';
document.querySelector('.workspace').prepend(label);
$('clearAlarms').addEventListener('click',clearAlarms);
renderAlarms();
'''
    setup += f"state.language={json.dumps(language)};window.PortfolioI18n.applyToDocument(state.language);window.PortfolioI18n.observe();applyRolePermissions();\n"
    html = html.replace('</body>', '<script>' + (ROOT / 'web/i18n.js').read_text() + '\n' + setup + source_js() + '\n' + constants + '\n' + extra + '\n' + permissions + '\n' + handlers + '</script></body>')
    # declarations are hoisted, but constants used by renderAlarms must precede setup.
    html = html.replace('renderAlarms();\nstate.language=', 'window.addEventListener("load",()=>{renderAlarms();\nstate.language=')
    html = html.replace('applyRolePermissions();\n', 'applyRolePermissions();});\n')
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'index.html').write_text(html)
    css = re.sub(r'@import\s+url\("[^"]+"\);', '', (ROOT / 'web/styles.css').read_text())
    (directory / 'styles.css').write_text(css)
    return directory / 'index.html'


@pytest.mark.skipif(not CHROME, reason="Isolated Chromium required for alarm layout QA")
@pytest.mark.parametrize('width,language', [(320,'en'),(360,'en'),(320,'he'),(360,'he'),(1440,'he')])
def test_browser_header_modal_navigation_viewer_and_keyboard(tmp_path, width, language):
    websockets = pytest.importorskip('websockets.sync.client')
    fixture = browser_fixture(tmp_path, language)
    process = subprocess.Popen([
        CHROME, '--headless', '--no-sandbox', '--disable-gpu',
        f'--user-data-dir={tmp_path / "chrome"}', '--remote-debugging-port=0', 'about:blank',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        port_file = tmp_path / 'chrome/DevToolsActivePort'
        deadline = time.monotonic() + 10
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert port_file.exists(), 'Isolated Chromium did not initialize'
        port = port_file.read_text().splitlines()[0]
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list') as response:
            target = next(page for page in json.load(response) if page['type'] == 'page')
        with websockets.connect(target['webSocketDebuggerUrl']) as socket:
            command_id = 0

            def command(method, params=None):
                nonlocal command_id
                command_id += 1
                socket.send(json.dumps({'id':command_id,'method':method,'params':params or {}}))
                while True:
                    message = json.loads(socket.recv(timeout=10))
                    if message.get('id') == command_id:
                        assert 'error' not in message, message
                        return message['result']

            def evaluate(expression):
                result = command('Runtime.evaluate', {'expression':expression,'returnByValue':True,'awaitPromise':True})
                assert 'exceptionDetails' not in result, result
                return result['result'].get('value')

            def key(value):
                params={'type':'keyDown','key':value,'code':value,'windowsVirtualKeyCode':{'Enter':13,'Escape':27,'Tab':9}[value]}
                if value == 'Enter':
                    params.update(text='\r',unmodifiedText='\r')
                command('Input.dispatchKeyEvent', params)
                command('Input.dispatchKeyEvent', {'type':'keyUp','key':value,'code':value})

            command('Emulation.setDeviceMetricsOverride', {'width':width,'height':800,'deviceScaleFactor':1,'mobile':False})
            command('Page.navigate', {'url':fixture.as_uri()})
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if evaluate("document.getElementById('alarmsCount')?.textContent==='106'"):
                    break
                time.sleep(.05)
            assert evaluate("$('alarmsCount').textContent") == '106', evaluate('qaErrors')
            assert evaluate('innerWidth') == width
            assert evaluate("$('alarmsButton').dataset.alarmTone") == 'red'
            assert evaluate("$('alarmsButton').disabled") is False
            overflow = evaluate("(()=>{const r=$('alarmsButton').getBoundingClientRect();return {left:r.left,right:r.right,scroll:document.documentElement.scrollWidth,width:innerWidth}})()")
            assert overflow['left'] >= 0 and overflow['right'] <= width, overflow
            assert overflow['scroll'] <= width + 1, overflow
            artifacts = Path('/tmp/alarm-priority-qa');artifacts.mkdir(exist_ok=True)
            (artifacts / f'header-{width}-{language}.png').write_bytes(base64.b64decode(command('Page.captureScreenshot', {'format':'png'})['data']))
            evaluate("$('alarmsButton').focus()")
            assert evaluate("document.activeElement.id") == 'alarmsButton', evaluate("({errors:qaErrors,hidden:$('alarmsButton').getClientRects().length,inert:$('appShell').inert,visibility:getComputedStyle(document.body).visibility})")
            key('Enter');time.sleep(.15)
            assert evaluate("$('alarmsModal').hidden") is False, evaluate('qaErrors')
            geometry = evaluate("(()=>{const c=$('alarmsModal').querySelector('.modal-card');return {client:c.clientWidth,scroll:c.scrollWidth,rows:[...$('alarmsList').children].every(x=>x.scrollWidth<=x.clientWidth+1),input:$('vestingAlertDays').clientWidth,count:$('alarmsCount').textContent}})()")
            (artifacts / f'modal-{width}-{language}.png').write_bytes(base64.b64decode(command('Page.captureScreenshot', {'format':'png'})['data']))
            geometry['overflowing'] = evaluate("(()=>{const c=$('alarmsModal').querySelector('.modal-card'),r=c.getBoundingClientRect();return [...c.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>r.right||e.getBoundingClientRect().left<r.left).slice(0,8).map(e=>({tag:e.tagName,id:e.id,class:e.className,width:e.getBoundingClientRect().width}))})()")
            assert geometry['scroll'] <= geometry['client'] + 1, json.dumps(geometry)
            assert geometry['rows'], geometry
            (artifacts / f'modal-{width}-{language}.png').write_bytes(base64.b64decode(command('Page.captureScreenshot', {'format':'png'})['data']))
            # A same-symbol Buy and Sell are distinct destinations. Background
            # updates must preserve the exact keyboard action, including type.
            for selector in [
                '[data-open-signal-alarm="SAME"][data-alarm-signal-type="buy"]',
                '[data-open-signal-alarm="SAME"][data-alarm-signal-type="sell"]',
                '[data-open-risk-alarm]', '[data-open-vesting-alarm]',
                '[data-open-dividend-alarm="pending-5"]',
            ]:
                focus = evaluate("(()=>{const target=document.querySelector("+json.dumps(selector)+");target.focus();const before=JSON.stringify({...target.dataset});renderAlarms();return {before,after:JSON.stringify({...document.activeElement.dataset})}})()")
                assert focus['after'] == focus['before'], focus
            assert evaluate("document.querySelector('.alarm-settings-disclosure').open") is False
            evaluate("document.querySelector('.alarm-settings-disclosure summary').focus()")
            key('Enter');time.sleep(.05)
            assert evaluate("document.querySelector('.alarm-settings-disclosure').open") is True
            assert evaluate("$('vestingAlertDays').getBoundingClientRect().width") >= 80
            assert evaluate("$('saveAlarmSettings').disabled") is True
            assert evaluate("(()=>{const c=$('alarmsModal').querySelector('.modal-card');return c.scrollWidth<=c.clientWidth+1})()") is True
            (artifacts / f'settings-{width}-{language}.png').write_bytes(base64.b64decode(command('Page.captureScreenshot', {'format':'png'})['data']))
            key('Enter');time.sleep(.05)
            assert evaluate("document.querySelector('.alarm-settings-disclosure').open") is False
            assert evaluate("document.querySelectorAll('.alarm-summary-chip[data-alarm-tone=purple]').length") == 1
            evaluate("document.querySelector('[data-open-signal-alarm=\"LONGSYMBOLWITHAVERYLONGUNBROKENNAME\"]').scrollIntoView({block:'center'})")
            (artifacts / f'long-name-{width}-{language}.png').write_bytes(base64.b64decode(command('Page.captureScreenshot', {'format':'png'})['data']))
            evaluate("$('alarmsModal').querySelector('.modal-card').scrollTop=300;renderAlarms()")
            assert evaluate("$('alarmsModal').querySelector('.modal-card').scrollTop") == 300
            key('Tab');time.sleep(.05)
            assert evaluate("$('alarmsModal').contains(document.activeElement)") is True
            for signal_type in ['sell','buy']:
                evaluate("state.alertRuleFilter='name:Synthetic buy'")
                evaluate(f"document.querySelector('[data-open-signal-alarm=\"SAME\"][data-alarm-signal-type=\"{signal_type}\"]').click()")
                time.sleep(.15)
                assert evaluate("$('researchModal').hidden") is False
                assert evaluate("$('alarmsModal').hidden") is True
                assert evaluate(f"Boolean(document.activeElement.closest('.signal-{signal_type}'))") is True, evaluate('qaErrors')
                assert evaluate("document.activeElement.disabled") is False
                # A delayed saved-results response must retain the destination
                # selected from Alarms, even for the same symbol's other type.
                chart_id = evaluate('document.activeElement.id')
                evaluate('renderAlerts(state.alertData,{signalsOnly:true})')
                assert evaluate('document.activeElement.id') == chart_id
                assert evaluate(f"Boolean(document.activeElement.closest('.signal-{signal_type}'))") is True
                assert evaluate('state.alertRuleFilter') == ''
                assert evaluate("[...document.querySelectorAll('[data-dismiss-alert-signal]')].every(x=>x.disabled)") is True
                key('Escape');time.sleep(.1)
                evaluate("$('alarmsButton').click()");time.sleep(.1)
            evaluate("document.querySelector('[data-open-risk-alarm]').focus();document.activeElement.click()")
            time.sleep(.1)
            assert evaluate("$('alarmRiskModal').hidden") is False
            assert evaluate("$('alarmsModal').inert") is True
            assert evaluate("$('alarmRiskModal').contains(document.activeElement)") is True
            evaluate("state.localAccounts[0].initial_cash=-1000;renderAlarms()")
            assert '55' in evaluate("$('alarmRiskDetails').textContent")
            evaluate("state.localAccounts[0].initial_cash=-10000;renderAlarms()")
            assert '100' in evaluate("$('alarmRiskDetails').textContent")
            key('Escape');time.sleep(.1)
            assert evaluate("$('alarmRiskModal').hidden") is True
            assert evaluate("$('alarmsModal').inert") is False
            assert evaluate("Boolean(document.activeElement.dataset.openRiskAlarm)") is True
            assert evaluate("$('clearAlarms').disabled") is True
            evaluate("(async()=>{state.auth.user.role='Operator';renderAlarms();applyRolePermissions();await clearAlarms()})()")
            assert evaluate("$('alarmsCount').textContent") == '0'
            assert evaluate("$('alarmsButton').dataset.alarmTone") == 'neutral'
            evaluate("state.portfolioRefreshPending=true;renderAlarms()")
            assert evaluate("$('alarmsCount').textContent") == '1'
            evaluate("state.alertData={...state.alertData,active_signals:[{symbol:'NEWBUY',signal:'buy'}]};renderAlerts(state.alertData,{signalsOnly:true})")
            assert evaluate("$('alarmsCount').textContent") == '2'
            assert evaluate("$('alarmsButton').dataset.alarmTone") == 'amber'
            evaluate("state.localAccounts[0].initial_cash=0;state.portfolioRefreshPending=false;renderAlarms()")
            assert evaluate("$('alarmsCount').textContent") == '3'
            assert evaluate("$('alarmsButton').dataset.alarmTone") == 'amber'
            evaluate("state.alarmSignalsLoadFailed=true;state.alarmsLoadFailed=true;renderAlarms()")
            assert evaluate("$('alarmsCount').textContent") == '3'
            status = evaluate("$('alarmsStatus').textContent")
            assert ('reopen Alarms to retry' in status) if language == 'en' else not re.search('[A-Za-z]',status)
            assert evaluate('qaNetwork') == []
            assert evaluate('qaErrors') == []
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill();process.wait(timeout=5)
