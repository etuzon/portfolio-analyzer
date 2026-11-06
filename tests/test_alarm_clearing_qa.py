"""Independent acceptance checks for individual and grouped alarm dismissal."""

import base64
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

from test_alarm_priority_qa import CHROME, SETUP, browser_fixture, source_js


ROOT = Path(__file__).resolve().parents[1]


def dismissal_function():
    source = (ROOT / "web/app.js").read_text()
    start = source.index("async function dismissAlertSignal(")
    end = re.search(r"^}", source[start:], re.M).end()
    return source[start:start + end]


def run_qa(body):
    setup = SETUP.replace("const saveAlarmDismissals=()=>{};", "let saved=[];let saveAlarmDismissals=()=>saved.push([...state.dismissedAlarmIds]);")
    script = "const assert=require('node:assert/strict');const window={};\n" + (ROOT / "web/i18n.js").read_text() + r'''
const document={activeElement:null,body:{},addEventListener(){},querySelectorAll:()=>[]};
const nodes=Object.fromEntries(['alarmsButton','alarmsCount','alarmsPrioritySymbol','alarmPrioritySummary',
 'alarmsStatus','clearAlarms','alarmSettingsStatus','vestingAlertDays','alarmsList','alarmClearColor',
 'alarmClearType','clearMatchingAlarms','alarmClearStatus','alarmsModal','alertSignalStatus'].map(id=>[id,{
 value:'',textContent:'',innerHTML:'',dataset:{},hidden:false,contains:()=>false,
 classList:{toggle(){}},setAttribute(k,v){this[k]=v},focus(){document.activeElement=this}}]));
const $=id=>nodes[id];
const formatDateTime=value=>value;
const renderAlerts=data=>{state.alertData=data;renderAlarms()};
let requests=[],activeRequests=0,maxActiveRequests=0,failSymbols=new Set();
async function api(path,options){
 assert.equal(path,'/api/alerts/dismiss');const payload=JSON.parse(options.body);requests.push(payload);
 maxActiveRequests=Math.max(maxActiveRequests,++activeRequests);
 await Promise.resolve();activeRequests--;
 if(failSymbols.has(payload.symbol))throw Error('synthetic dismissal failure');
 return {dismissed:true,expires_at:'2099-01-01T00:00:00Z',state:{...state.alertData,active_signals:state.alertData.active_signals.filter(signal=>!(signal.symbol.toUpperCase()===payload.symbol&&signal.signal===payload.signal))}};
}
''' + setup + source_js() + "\n" + dismissal_function() + "\n(async()=>{\n" + body + "\nconsole.log('completed')})().catch(error=>{console.error(error);process.exitCode=1});"
    result = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert "completed" in result.stdout


def test_color_and_type_intersection_clear_incomplete_buy_without_other_amber_or_buy():
    run_qa(r'''
state.localAccounts=[account()];state.allPortfolioItems=[stock()];
state.alertData.active_signals=[{symbol:'COMPLETE',signal:'buy'},{symbol:'LIMITED',signal:'buy',missing:['price']},{symbol:'WATCH',signal:'watch'}];
renderAlarms();
nodes.alarmClearColor.value='amber';nodes.alarmClearType.value='Buy signal';
assert.deepEqual(displayedAlarms().filter(alarmMatchesClearSelection).map(alarm=>alarm.symbol),['LIMITED']);
await clearSelectedAlarms();
assert.deepEqual(requests,[{symbol:'LIMITED',signal:'buy'}]);
assert.deepEqual(portfolioSignalAlarms().map(alarm=>alarm.symbol).sort(),['COMPLETE','WATCH']);
assert.equal(portfolioRiskAlarms().length,2);
assert.equal(nodes.alarmClearColor.value,'amber');assert.equal(nodes.alarmClearType.value,'Buy signal');
assert.equal(nodes.clearMatchingAlarms.disabled,true,'zero-result intersection must not broaden after clearing');
assert.match(nodes.alarmClearStatus.textContent,/Cleared 1 alarms/);
''')


def test_single_event_and_type_groups_do_not_change_records_or_other_types():
    run_qa(r'''
state.localEvents=[event({id:'first'}),event({id:'second'}),event({id:'recorded',status:'processed',transaction_id:'recorded-tx'})];
const original=JSON.stringify(state.localEvents);
renderAlarms();const target=displayedAlarms().find(alarm=>alarm.event?.id==='first');
await clearSelectedAlarms({key:alarmClearKey(target)});
assert.deepEqual(displayedAlarms().map(alarm=>alarm.event?.id).sort(),['recorded','second']);
nodes.alarmClearType.value='Scheduled dividend';await clearSelectedAlarms();
assert.deepEqual(displayedAlarms().map(alarm=>alarm.event?.id),['recorded']);
assert.equal(JSON.stringify(state.localEvents),original);
assert.equal(saved.length,2);assert.equal(state.dismissedAlarmIds.length,2);
assert.ok(nodes.alarmsList.innerHTML.includes('data-clear-alarm='));
assert.ok(nodes.alarmsList.innerHTML.includes('aria-label="Clear alarm:'));
''')


def test_color_only_clears_all_red_kinds_and_leaves_other_colors():
    run_qa(r'''
state.localAccounts=[account('qa',-10000)];state.allPortfolioItems=[stock()];
state.alertData.active_signals=[{symbol:'SELL',signal:'sell'},{symbol:'BUY',signal:'buy'},{symbol:'WATCH',signal:'watch'}];
state.localEvents=[event()];nodes.alarmClearColor.value='red';
const selected=displayedAlarms().filter(alarmMatchesClearSelection);assert.equal(selected.length,3);
await clearSelectedAlarms();assert.ok(displayedAlarms().every(alarm=>alarmAppearance(alarm).tone!=='red'));
assert.deepEqual(portfolioSignalAlarms().map(alarm=>alarm.key).sort(),['BUY|buy','WATCH|watch']);
assert.equal(currentAlarms().dividends.length,1);assert.deepEqual(requests,[{symbol:'SELL',signal:'sell'}]);
''')


def test_signal_identity_expiry_partial_failure_and_serial_backend_ownership():
    run_qa(r'''
state.alertData.active_signals=[{symbol:'SAME',signal:'buy',rule_name:'one'},{symbol:'same',signal:'buy',rule_name:'two'},
 {symbol:'SAME',signal:'sell'},{symbol:'FAIL',signal:'watch'}];
state.localEvents=[event()];failSymbols.add('FAIL');
await clearSelectedAlarms({all:true});
assert.equal(maxActiveRequests,1);assert.equal(requests.length,3,'one backend call per symbol/type, not per matching rule');
assert.deepEqual(portfolioSignalAlarms().map(alarm=>alarm.key),['FAIL|watch']);
assert.equal(state.localEvents.length,1);assert.equal(currentAlarms().dividends.length,0);
assert.match(nodes.alarmClearStatus.textContent,/Cleared 3 alarms\. 1 could not be cleared/);
assert.ok(nodes.alarmsList.innerHTML.includes('FAIL'));
assert.equal(state.alertClientDismissals.length,2);assert.ok(state.alertClientDismissals.every(entry=>entry.expires_at==='2099-01-01T00:00:00Z'));
state.alertData.active_signals.push({symbol:'SAME',signal:'buy'});
assert.ok(!portfolioSignalAlarms().some(alarm=>alarm.key==='SAME|buy'));
state.alertClientDismissals.find(entry=>entry.signal==='buy').expires_at='2000-01-01T00:00:00Z';
assert.ok(portfolioSignalAlarms().some(alarm=>alarm.key==='SAME|buy'));
''')


def test_risk_dismissal_stable_reload_language_order_and_changes_with_raw_same_score_evidence():
    run_qa(r'''
state.localAccounts=[account('qa',-10000)];state.allPortfolioItems=[stock(),stock('SECOND',20)];
const initial=visiblePriorityAlarms().filter(alarm=>alarm.kind==='risk');assert.ok(initial.length);
const originalScore=initial[0].risk.score;
await clearSelectedAlarms({all:true});assert.equal(visiblePriorityAlarms().length,0);
const dismissed=[...state.dismissedAlarmIds];
state.allPortfolioItems=structuredClone(state.allPortfolioItems).reverse();state.localAccounts=structuredClone(state.localAccounts);
for(const language of ['he','en','he']){state.language=language;renderAlarms();assert.equal(visiblePriorityAlarms().length,0);assert.deepEqual(state.dismissedAlarmIds,dismissed)}
state.localAccounts[0].initial_cash=-10001;
let changed=visiblePriorityAlarms().filter(alarm=>alarm.kind==='risk');
assert.ok(changed.length);assert.equal(changed[0].risk.score,originalScore,'changed raw debt must reappear even if score remains100');
await clearSelectedAlarms({all:true});assert.equal(visiblePriorityAlarms().length,0);
state.allPortfolioItems[0].holding.quantity+=.001;
assert.ok(visiblePriorityAlarms().length,'changed units must reappear without a rounded-score change');
await clearSelectedAlarms({all:true});
state.allPortfolioItems[0].missing.push('dividend history');
assert.ok(visiblePriorityAlarms().length,'changed evidence coverage must reappear');
await clearSelectedAlarms({all:true});state.portfolioSourceState='failed';
assert.ok(visiblePriorityAlarms().some(alarm=>alarm.level==='unavailable'));
''')


def test_risk_dismissal_reappears_when_effective_fx_changes():
    run_qa(r'''
state.baseCurrency='ILS';state.fxRates={'USD/ILS':3.5};
state.localAccounts=[account('qa',-10000)];state.allPortfolioItems=[stock()];
await clearSelectedAlarms({all:true});assert.equal(visiblePriorityAlarms().length,0);
state.fxRates['USD/ILS']=3.51;
assert.ok(visiblePriorityAlarms().length,'changed conversion evidence must reappear');
''')


def test_reordering_decimal_holdings_preserves_acknowledgement_but_raw_small_change_does_not():
    run_qa(r'''
state.localAccounts=[account('qa',-12345.67)];state.allPortfolioItems=Array.from({length:27},(_,index)=>stock(`RAW${index}`,(index+1)*137.12345));
let alarm=portfolioRiskAlarms()[0];assert.ok(alarm);const first=riskAlarmDismissalId(alarm);
state.allPortfolioItems.reverse();alarm=portfolioRiskAlarms().find(entry=>entry.key===alarm.key);
assert.equal(riskAlarmDismissalId(alarm),first,'presentation ordering is not new financial evidence');
state.allPortfolioItems[0].holding.market_value+=1e-10;
assert.notEqual(riskAlarmDismissalId(portfolioRiskAlarms().find(entry=>entry.key===alarm.key)),first,'raw evidence must not be rounded away');
''')


def test_risk_acknowledgement_does_not_hide_the_same_risk_for_another_user():
    run_qa(r'''
state.auth.user.id='first';state.localAccounts=[account('qa',-10000)];state.allPortfolioItems=[stock()];
await clearSelectedAlarms({all:true});assert.equal(visiblePriorityAlarms().length,0);
state.auth.user={id:'second',role:'Operator'};
assert.ok(visiblePriorityAlarms().length,'risk acknowledgements belong to the current user');
''')


def test_dismissal_result_after_session_change_cannot_mutate_new_session():
    run_qa(r'''
state.auth.user.id='first';state.auth.csrfToken='first-token';state.alertData.active_signals=[{symbol:'QA',signal:'sell'}];
let release;api=async()=>new Promise(resolve=>release=resolve);
const work=clearSelectedAlarms({all:true});assert.ok(state.alarmClearPending);
state.auth.user={id:'second',role:'Viewer'};state.auth.csrfToken='second-token';
state.alarmClearPending=false;state.alarmClearMessage=null;
release({dismissed:true,expires_at:'2099-01-01T00:00:00Z',state:{active_signals:[]}});await work;
assert.deepEqual(state.alertData.active_signals,[{symbol:'QA',signal:'sell'}]);
assert.equal(state.alertClientDismissals.length,0);assert.equal(state.alarmClearMessage,null);
assert.equal(state.alarmClearPending,false);
''')


def test_viewer_no_mutations_and_local_save_failure_retains_alarm_and_source_failures():
    run_qa(r'''
state.localEvents=[event()];state.alertData.active_signals=[{symbol:'QA',signal:'sell'}];
state.auth.user.role='Viewer';renderAlarms();const original=JSON.stringify(state.localEvents);
await clearSelectedAlarms({all:true});assert.equal(requests.length,0);assert.equal(saved.length,0);assert.equal(state.dismissedAlarmIds.length,0);
assert.equal(nodes.clearMatchingAlarms.disabled,true);assert.equal(nodes.clearAlarms.disabled,true);
assert.ok(nodes.alarmsList.innerHTML.includes(' disabled'));
state.auth.user.role='Operator';state.alertData.active_signals=[];
saveAlarmDismissals=()=>{throw Error('synthetic storage failure')};await clearSelectedAlarms({all:true});
assert.equal(currentAlarms().dividends.length,1);assert.match(nodes.alarmClearStatus.textContent,/Cleared 0 alarms\. 1 could not/);
saveAlarmDismissals=()=>{};state.alarmsLoadFailed=true;state.alarmSignalsLoadFailed=true;
await clearSelectedAlarms({all:true});assert.equal(displayedAlarms().length,0);
assert.match(nodes.alarmsStatus.textContent,/Event notices could not be updated/);assert.match(nodes.alarmsStatus.textContent,/Trading signals could not be updated/);
assert.equal(JSON.stringify(state.localEvents),original);
''')


def test_new_controls_and_feedback_are_localized_with_accessible_individual_names():
    run_qa(r'''
state.localEvents=[event()];state.alertData.active_signals=[{symbol:'QA',signal:'sell'}];
for(const language of ['he','en']){
 state.language=language;renderAlarms();const labels=(nodes.alarmClearColor.innerHTML+nodes.alarmClearType.innerHTML).replace(/<[^>]*>/gu,'');
 if(language==='he'){assert.ok(/[א-ת]/u.test(labels));assert.ok(!/Any color|All types|Sell signal|Scheduled dividend|Red|Blue/.test(labels));assert.match(nodes.alarmsList.innerHTML,/aria-label="[^"]*[א-ת]/u)}
 else{assert.ok(!/[א-ת]/u.test(labels));assert.ok(nodes.alarmsList.innerHTML.includes('aria-label="Clear alarm:'))}
}
''')


@pytest.mark.skipif(not CHROME, reason="Isolated Chromium required")
@pytest.mark.parametrize("width,language", [(320, "en"), (320, "he"), (1440, "en"), (1440, "he")])
def test_browser_individual_keyboard_and_combined_groups_leave_source_records_intact(tmp_path, width, language):
    websockets = pytest.importorskip("websockets.sync.client")
    fixture = browser_fixture(tmp_path, language)
    additions = dismissal_function() + r'''
window.qaDismissRequests=[];
async function api(path,options){
 if(path!=='/api/alerts/dismiss')throw Error('Unexpected synthetic endpoint');
 const payload=JSON.parse(options.body);qaDismissRequests.push(payload);
 return {dismissed:true,expires_at:'2099-01-01T00:00:00Z',state:{...state.alertData,active_signals:state.alertData.active_signals.filter(signal=>!(signal.symbol===payload.symbol&&signal.signal===payload.signal))}};
}
'''
    page, count = re.subn(r"(?:const dismissAlertSignal=async\(symbol,signal\)=>|async function dismissAlertSignal\(symbol,signal\))\{.*?\n};?", "", fixture.read_text(), flags=re.S)
    assert count == 1, "Expected the shared browser fixture's transport-only dismissal stub"
    fixture.write_text(page.replace("</body>", "<script>" + additions + "</script></body>"))
    process = subprocess.Popen([CHROME, "--headless", "--no-sandbox", "--disable-gpu",
        f"--user-data-dir={tmp_path / 'chrome'}", "--remote-debugging-port=0", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        port_file = tmp_path / "chrome/DevToolsActivePort"
        deadline = time.monotonic() + 10
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert port_file.exists()
        port = port_file.read_text().splitlines()[0]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list") as response:
            target = next(item for item in json.load(response) if item["type"] == "page")
        with websockets.connect(target["webSocketDebuggerUrl"]) as socket:
            command_id = 0

            def command(method, params=None):
                nonlocal command_id
                command_id += 1
                socket.send(json.dumps({"id":command_id,"method":method,"params":params or {}}))
                while True:
                    response = json.loads(socket.recv(timeout=10))
                    if response.get("id") == command_id:
                        assert "error" not in response, response
                        return response["result"]

            def evaluate(expression, await_promise=False):
                response = command("Runtime.evaluate", {"expression":expression,"returnByValue":True,"awaitPromise":await_promise})
                assert "exceptionDetails" not in response, response
                return response["result"].get("value")

            def settle():
                evaluate("new Promise(resolve=>setTimeout(resolve,80))", True)

            def choose(identifier, value):
                evaluate(f"$({json.dumps(identifier)}).value={json.dumps(value)};$({json.dumps(identifier)}).dispatchEvent(new Event('change',{{bubbles:true}}))")

            command("Emulation.setDeviceMetricsOverride", {"width":width,"height":700,"deviceScaleFactor":1,"mobile":False})
            command("Page.navigate", {"url":fixture.as_uri()})
            deadline = time.monotonic() + 10
            while not evaluate("document.getElementById('alarmsCount')?.textContent==='106'") and time.monotonic() < deadline:
                time.sleep(.05)
            assert evaluate("qaErrors") == []
            evaluate("$('alarmsButton').click()")
            settle()
            assert evaluate("$('alarmsModal').hidden") is False
            assert evaluate("$('clearAlarms').disabled&&$('clearMatchingAlarms').disabled") is True
            assert evaluate("[...document.querySelectorAll('[data-clear-alarm]')].every(button=>button.disabled)") is True
            assert evaluate("!$('alarmClearColor').disabled&&!$('alarmClearType').disabled") is True
            evaluate("state.auth.user={id:'qa-editor',role:'Operator'};renderAlarms();applyRolePermissions();qaRaw=JSON.stringify({events:state.localEvents,holdings:state.allPortfolioItems,accounts:state.localAccounts})")
            choose("alarmClearColor", "amber");choose("alarmClearType", "Watch signal")
            artifacts = Path("/tmp/alarm-clearing-qa")
            artifacts.mkdir(exist_ok=True)
            (artifacts / f"alarms-{width}-{language}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format":"png"})["data"]))
            evaluate("$('alarmsModal').querySelector('.modal-card').scrollTop=300;$('clearMatchingAlarms').focus({preventScroll:true})")
            evaluate("$('clearMatchingAlarms').click()")
            settle()
            assert evaluate("qaDismissRequests") == [{"symbol":"LONGSYMBOLWITHAVERYLONGUNBROKENNAME","signal":"watch"}]
            assert evaluate("$('clearMatchingAlarms').disabled") is True
            # Explicitly removing a summary chip and row can change scroll
            # anchoring. It must retain the popup rather than reset its reader.
            assert evaluate("$('alarmsModal').querySelector('.modal-card').scrollTop") > 0
            assert evaluate("$('alarmsModal').contains(document.activeElement)") is True
            assert evaluate("$('alarmClearType').value") == "Watch signal"
            choose("alarmClearColor", "red");choose("alarmClearType", "Sell signal")
            evaluate("$('clearMatchingAlarms').click()")
            settle()
            assert evaluate("portfolioSignalAlarms().map(alarm=>alarm.key)") == ["SAME|buy"]
            assert evaluate("visiblePriorityAlarms().filter(alarm=>alarm.kind==='risk').length") == 2
            # Native keyboard activation on one specific event's separate ×.
            evaluate("qaEventKey='dividend:pending-50';[...document.querySelectorAll('[data-clear-alarm]')].find(button=>button.dataset.clearAlarm===qaEventKey).focus();qaBeforeIndividualScroll=$('alarmsModal').querySelector('.modal-card').scrollTop")
            command("Input.dispatchKeyEvent", {"type":"keyDown","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"text":"\r","unmodifiedText":"\r"})
            command("Input.dispatchKeyEvent", {"type":"keyUp","key":"Enter","code":"Enter"})
            settle()
            assert evaluate("currentAlarms().dividends.some(alarm=>alarm.event.id==='pending-50')") is False, evaluate("({focus:document.activeElement.outerHTML,pending:state.alarmClearPending,message:state.alarmClearMessage,errors:qaErrors})")
            assert evaluate("document.activeElement.dataset.clearAlarm") == "dividend:pending-51"
            assert evaluate("qaBeforeIndividualScroll>100&&$('alarmsModal').querySelector('.modal-card').scrollTop>100") is True
            assert evaluate("$('alarmsModal').contains(document.activeElement)") is True
            assert evaluate("$('alarmsModal').hidden") is False
            assert evaluate("$('eventsModal').hidden") is True
            choose("alarmClearColor", "");choose("alarmClearType", "Scheduled dividend")
            evaluate("$('clearMatchingAlarms').click()")
            settle()
            assert evaluate("currentAlarms().dividends.map(alarm=>alarm.event.id)") == ["recorded-local"]
            assert evaluate("$('clearMatchingAlarms').disabled") is True
            layout = evaluate("(()=>{const card=$('alarmsModal').querySelector('.modal-card');return {width:innerWidth,overflow:card.scrollWidth>card.clientWidth,small:[...card.querySelectorAll('[data-clear-alarm]')].some(button=>button.getBoundingClientRect().width<40),sizes:[...card.querySelectorAll('[data-clear-alarm]')].map(button=>({width:button.getBoundingClientRect().width,height:button.getBoundingClientRect().height})),names:[...card.querySelectorAll('[data-clear-alarm]')].map(button=>button.getAttribute('aria-label'))}})()")
            assert layout["width"] == width and not layout["overflow"] and not layout["small"], layout
            assert all(layout["names"]), layout
            if language == "he":
                labels = evaluate("$('alarmClearColor').textContent+$('alarmClearType').textContent+$('clearMatchingAlarms').textContent+$('clearAlarms').textContent")
                assert not re.search(r"Any color|All types|Scheduled dividend|Sell signal|Clear matching|Clear all", labels)
            evaluate("$('clearAlarms').click()")
            settle()
            assert evaluate("$('alarmsCount').textContent") == "0"
            assert evaluate("qaDismissRequests.length") == 3
            assert evaluate("JSON.stringify({events:state.localEvents,holdings:state.allPortfolioItems,accounts:state.localAccounts})===qaRaw") is True
            assert evaluate("qaErrors") == []
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill();process.wait(timeout=5)
