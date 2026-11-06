"""Independent browser coverage of a complete portfolio snapshot replacement.

Uses the real page, all local scripts, CSS, loader and renderers. Only transport,
authentication bootstrap and unrelated heatmap/risk persistence are isolated.
All values are synthetic; no runtime portfolio or signed-in browser is used.
"""

import asyncio
import json
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CHROME = shutil.which("google-chrome") or shutil.which("chromium")


def test_edit_during_snapshot_build_is_not_marked_already_observed(monkeypatch):
    from app import main
    from app.portfolio_notifications import PortfolioNotifications

    notifications = PortfolioNotifications()
    monkeypatch.setattr(main, "_portfolio_notifications", notifications)

    def build_snapshot(**_kwargs):
        snapshot = {"items": [{"holding": {"quantity": 10}}]}
        # Another edit arrives after this response's source read, before return.
        notifications.notify()
        return snapshot

    monkeypatch.setattr(main, "portfolio_payload", build_snapshot)
    payload = main.portfolio()
    assert payload["items"][0]["holding"]["quantity"] == 10
    assert payload["update_revision"] < notifications.revision, "The browser must detect the edit newer than this snapshot"


def test_progress_notifications_are_metadata_only_and_release_disconnected_subscribers(monkeypatch):
    from app import main
    from app.portfolio_notifications import PortfolioNotifications

    notifications = PortfolioNotifications()
    monkeypatch.setattr(main, "_portfolio_notifications", notifications)
    monkeypatch.setattr(main, "_portfolio_refresh_in_progress", True)
    monkeypatch.setattr(main, "_portfolio_refresh_failure", None)
    monkeypatch.setattr(main, "_portfolio_cache", None)
    monkeypatch.setattr(main, "_portfolio_cache_generation", 7)
    monkeypatch.setattr(main, "_portfolio_refresh_progress", {"total": 2, "completed": 0, "failed": 0})

    def forbidden(*_args, **_kwargs):
        raise AssertionError("A progress notification performed full portfolio/provider work")

    monkeypatch.setattr(main, "portfolio_payload", forbidden)
    monkeypatch.setattr(main, "hub", forbidden)

    class Request:
        async def is_disconnected(self):
            return False

    async def check():
        response = await main.portfolio_updates(Request())
        iterator = response.body_iterator
        first = json.loads((await anext(iterator)).removeprefix("data: "))
        assert first == {"generation": 7, "update_revision": 0, "refresh_state": "refreshing", "refresh_pending": True,
                         "refresh_progress": {"total": 2, "completed": 0, "failed": 0}}
        assert len(notifications._listeners) == 1
        next_message = asyncio.create_task(anext(iterator))
        await asyncio.sleep(0)
        main._portfolio_refresh_progress.update(completed=2, failed=1)
        main._portfolio_refresh_in_progress = False
        main._portfolio_refresh_failure = {"message": "synthetic failure"}
        await asyncio.to_thread(notifications.notify)
        final = json.loads((await asyncio.wait_for(next_message, timeout=1)).removeprefix("data: "))
        assert final["refresh_state"] == "failed" and not final["refresh_pending"]
        assert final["update_revision"] > first["update_revision"]
        assert final["refresh_progress"] == {"total": 2, "completed": 2, "failed": 1}
        await iterator.aclose()
        assert not notifications._listeners
        main._portfolio_refresh_in_progress = True
        response = await main.portfolio_updates(Request())
        iterator = response.body_iterator
        await anext(iterator)
        blocked = asyncio.create_task(anext(iterator))
        await asyncio.sleep(0)
        blocked.cancel()
        with pytest.raises(asyncio.CancelledError):
            await blocked
        assert not notifications._listeners

    asyncio.run(check())


@pytest.mark.skipif(not CHROME, reason="Isolated Chromium required")
@pytest.mark.parametrize("width", [390, 1440])
def test_whole_portfolio_reload_preserves_holdings_reading_and_editing(tmp_path, width):
    websockets = pytest.importorskip("websockets.sync.client")
    source = (ROOT / "web/app.js").read_text()
    source = source.replace("initializeApp().catch(reportBackgroundError).finally(revealInitializedApp);", "")
    setup = r'''
window.qa={errors:[],calls:[]};
window.addEventListener('error',event=>qa.errors.push(event.message));
window.addEventListener('unhandledrejection',event=>qa.errors.push(String(event.reason)));
const qaAccount={id:'qa-account',name:'QA',type:'Investment',currency:'USD',cash_balance:1000,persons:[]};
let qaQuantity=10,qaPending=false,qaRevision=1,qaAccountName='QA';
window.EventSource=class {
 static CLOSED=2;
 constructor(path){this.path=path;this.readyState=1;(qa.sources ||= []).push(this);}
 close(){this.readyState=2;}
 emit(data){this.onmessage?.({data:JSON.stringify(data)});}
};
function qaItems(){return Array.from({length:45},(_,index)=>({
 holding:{symbol:`QA_${String(index).padStart(3,'0')}`,name:`Synthetic holding ${index}`,account_id:'qa-account',account:qaAccountName,account_type:'Investment',stock_market:'NASDAQ',currency:'USD',asset_class:'EQUITY',quantity:qaQuantity,cost_basis:200,market_value:300,unrealized_profit:100},
 price_ranges:{'1y':{state:'ok',low:20,high:40,current:30}},moving_averages:{'30':{state:'ok',value:27}},support_resistance:{'1y':{state:'missing'}},
 profit_trend:{state:'ok',current:1000000},dividend_trend:{state:'ok',current:2},missing:[],status:{},industry:`Industry ${index}`
}));}
api=async(path)=>{
 qa.calls.push(path);
 if(path.startsWith('/api/portfolio'))return {items:qaItems(),count:45,status:{},update_revision:qaRevision,refresh_pending:qaPending,refresh_state:qaPending?'refreshing':'ready'};
 if(path.includes('account-trends'))return {accounts:[]};
 if(path==='/api/local/accounts')return {items:[qaAccount]};
 if(path==='/api/fx')return {quotes:[]};
 return {items:[],industries:[]};
};
loadHeatmap=()=>{};
recordRiskHistory=async()=>{};
appLog=()=>{};appWarn=()=>{};
state.auth.user={id:'qa',username:'qa',role:'admin'};
state.language='en';state.baseCurrency='USD';
state.dashboard=defaultDashboard();
state.dashboard.widgets.forEach(widget=>widget.view=['portfolio_value','industry_split','top_holdings'].includes(widget.id)?'basic':'hidden');
$('authOverlay').hidden=true;$('appShell').inert=false;$('appShell').removeAttribute('aria-hidden');
document.documentElement.lang='en';document.documentElement.dir='ltr';revealInitializedApp();
window.PortfolioI18n.applyToDocument('en');
window.qaLoad=async()=>{await loadPortfolio();await new Promise(resolve=>setTimeout(resolve,200));};
window.qaReady=qaLoad().then(()=>{qa.ready=true}).catch(error=>qa.errors.push(error.stack));
'''
    (tmp_path / "app.js").write_text(source + "\n" + setup)
    page = (ROOT / "web/index.html").read_text()
    page = re.sub(r'<script src="https://[^\"]+"></script>', '', page)
    for relative in re.findall(r'(?:src|href)="/([^"?]+)(?:\?[^\"]*)?"', page):
        asset = ROOT / "web" / relative
        if not asset.exists():
            continue
        if relative == "app.js":
            asset = tmp_path / "app.js"
        elif relative.endswith(".css"):
            css_target = tmp_path / Path(relative).name
            css_target.write_text(re.sub(r'@import\s+url\([^;]+;', '', asset.read_text()))
            asset = css_target
        page = re.sub(r'(["\'])/' + re.escape(relative) + r'(?:\?[^"\']*)?(["\'])', lambda match: match[1] + asset.as_uri() + match[2], page)
    fixture = tmp_path / "whole-portfolio.html"
    fixture.write_text(page)
    process = subprocess.Popen([CHROME, "--headless", "--no-sandbox", "--disable-gpu",
        f"--user-data-dir={tmp_path / 'chrome'}", "--remote-debugging-port=0", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        port_file = tmp_path / "chrome/DevToolsActivePort"
        deadline = time.monotonic() + 10
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert port_file.exists(), "Isolated Chromium failed to start"
        port = port_file.read_text().splitlines()[0]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list") as response:
            target = next(item for item in json.load(response) if item["type"] == "page")
        with websockets.connect(target["webSocketDebuggerUrl"]) as socket:
            command_id = 0

            def command(method, params=None):
                nonlocal command_id
                command_id += 1
                socket.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
                while True:
                    response = json.loads(socket.recv(timeout=10))
                    if response.get("id") == command_id:
                        assert "error" not in response, response
                        return response["result"]

            def evaluate(expression, await_promise=False):
                response = command("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": await_promise})
                assert "exceptionDetails" not in response, response
                return response["result"].get("value")

            command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 700, "deviceScaleFactor": 1, "mobile": False})
            command("Page.navigate", {"url": fixture.as_uri()})
            deadline = time.monotonic() + 15
            while not evaluate("window.qa?.ready || window.qa?.errors?.length") and time.monotonic() < deadline:
                time.sleep(.05)
            assert evaluate("window.qa?.errors") == [], evaluate("window.qa")
            assert evaluate("qa.ready") is True
            assert evaluate("innerWidth") == width
            assert evaluate("document.querySelectorAll('#rows tr').length") == 45
            before = evaluate(r'''(()=>{
 $('query').value='QA';state.portfolioFilterCriteria=criteriaFromForm();applyFilter();
 document.querySelector('.nav-menu').open=true;
 const list=document.querySelector('[data-preserve-scroll="industry-split"]');if(list)list.scrollTop=70;
 const row=$('rows').children[10];const button=row.querySelector('button.symbol');button.focus({preventScroll:true});
 row.scrollIntoView({block:'center'});
 return {y:scrollY,top:row.getBoundingClientRect().top,key:row.dataset.portfolioPosition,focus:button.dataset.securityDetailSymbol,list:list?.scrollTop};
})()''')
            assert before["y"] > 100, before
            for quantity in (11, 12, 13):
                evaluate(f"qaQuantity={quantity};qaLoad()", True)
                after = evaluate(r'''(()=>{const row=[...$('rows').children].find(row=>row.dataset.portfolioPosition===document.activeElement.closest('[data-portfolio-position]')?.dataset.portfolioPosition);return {y:scrollY,top:row?.getBoundingClientRect().top,key:row?.dataset.portfolioPosition,focus:document.activeElement.dataset.securityDetailSymbol,list:document.querySelector('[data-preserve-scroll="industry-split"]')?.scrollTop,query:$('query').value,details:document.querySelector('.nav-menu').open,quantity:state.items[0].holding.quantity,errors:qa.errors};})()''')
                assert after["errors"] == [], after
                assert after["key"] == before["key"], after
                assert after["focus"] == before["focus"], after
                assert abs(after["y"] - before["y"]) <= 1, {"before": before, "after": after}
                assert abs(after["top"] - before["top"]) <= 1, {"before": before, "after": after}
                assert after["list"] == before["list"], after
                assert after["query"] == "QA" and after["details"], after
                assert after["quantity"] == quantity, after
            evaluate("$('query').focus({preventScroll:true});$('query').setSelectionRange(0,1);qaLoad()", True)
            assert evaluate("({focus:document.activeElement.id,start:$('query').selectionStart,end:$('query').selectionEnd,value:$('query').value})") == {"focus":"query","start":0,"end":1,"value":"QA"}

            # A real loader invocation starts the worker watch. Notifications
            # may update status, but neither holdings nor charts may be replaced.
            evaluate("qaPending=true;qaLoad()", True)
            before_events = evaluate(r'''(()=>{
 const row=$('rows').children[10];row.querySelector('button.symbol').focus({preventScroll:true});row.scrollIntoView({block:'center'});
 qa.originalRow=row;qa.originalCard=$('analyticsBoard').firstElementChild;qa.source=qa.sources.at(-1);
 return {y:scrollY,top:row.getBoundingClientRect().top,calls:qa.calls.length,requests:qa.calls.filter(path=>path.startsWith('/api/portfolio')).length};
})()''')
            evaluate(r'''(async()=>{
 for(let completed=1;completed<=3;completed++)qa.source.emit({update_revision:++qaRevision,generation:7,refresh_state:'refreshing',refresh_pending:true,refresh_progress:{total:4,completed,failed:0}});
 await new Promise(resolve=>setTimeout(resolve,1700));
})()''', True)
            assert evaluate("qa.calls.length") == before_events["calls"]
            assert evaluate("qa.originalRow.isConnected&&qa.originalCard.isConnected") is True
            assert evaluate("scrollY") == before_events["y"]
            assert "3/4" in evaluate("$('status').textContent")
            evaluate(r'''(async()=>{
 qaPending=false;qaQuantity=14;
 const message={update_revision:++qaRevision,generation:7,refresh_state:'ready',refresh_pending:false,refresh_progress:{total:4,completed:4,failed:0}};
 qa.source.emit(message);qa.source.emit(message);
 await new Promise(resolve=>setTimeout(resolve,250));
})()''', True)
            assert evaluate("qa.calls.filter(path=>path.startsWith('/api/portfolio')).length") == before_events["requests"] + 1
            assert evaluate("state.items[0].holding.quantity") == 14
            assert evaluate("document.activeElement.dataset.securityDetailSymbol") == before["focus"]
            final_view = evaluate("({y:scrollY,top:document.activeElement.closest('tr').getBoundingClientRect().top})")
            assert abs(final_view["top"] - before_events["top"]) <= 1, {"before":before_events,"after":final_view}
            idle_calls = evaluate("qa.calls.length")
            evaluate(r'''(async()=>{
 qa.sources.at(-1).emit({update_revision:qaRevision,generation:7,refresh_state:'ready',refresh_pending:false,refresh_progress:{total:4,completed:4,failed:0}});
 await new Promise(resolve=>setTimeout(resolve,1700));
})()''', True)
            assert evaluate("qa.calls.length") == idle_calls
            evaluate("qa.sources.at(-1).onerror()")
            assert "Connection interrupted" in evaluate("$('status').textContent")
            evaluate("qa.sources.at(-1).onopen?.()")
            evaluate("qa.sources.at(-1).emit({update_revision:qaRevision,generation:7,refresh_state:'ready',refresh_pending:false,refresh_progress:{total:4,completed:4,failed:0}})")
            assert "Connection interrupted" not in evaluate("$('status').textContent")
            assert evaluate("qa.calls.length") == idle_calls
            evaluate(r'''(async()=>{
 qaQuantity=15;qa.sources.at(-1).emit({update_revision:++qaRevision,generation:8,refresh_state:'ready',refresh_pending:false,refresh_progress:{total:0,completed:0,failed:0}});
 await new Promise(resolve=>setTimeout(resolve,250));
})()''', True)
            assert evaluate("state.items[0].holding.quantity") == 15
            assert evaluate("qa.calls.filter(path=>path.startsWith('/api/portfolio')).length") == before_events["requests"] + 2
            evaluate("$('query').focus({preventScroll:true})")
            command("Input.dispatchKeyEvent", {"type":"keyDown","key":"Tab","code":"Tab","windowsVirtualKeyCode":9})
            command("Input.dispatchKeyEvent", {"type":"keyUp","key":"Tab","code":"Tab"})
            keyboard_target = evaluate("document.activeElement.id")
            assert keyboard_target and keyboard_target != "query"
            evaluate("qaLoad()", True)
            assert evaluate("document.activeElement.id") == keyboard_target
            evaluate("$('account').value='QA';applyFilter();qaAccountName='OTHER';qaLoad()", True)
            assert evaluate("$('account').value") == "QA", "A disappearing account must not silently broaden the selected filter"
            assert evaluate("$('rows').children.length") == 0
            evaluate("applyFilter()")
            assert evaluate("$('rows').children.length") == 0, "Applying again must retain the unavailable filter value"
            assert evaluate("qa.errors") == []
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill();process.wait(timeout=5)
