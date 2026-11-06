"""Independent browser regression for background dashboard DOM replacement.

Synthetic cards run the actual renderer, layout, interaction helpers and CSS.
A separate headless profile never touches an existing user's browser session.
"""

import json
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

from test_shared_cash_risk_qa import app_functions

websockets = pytest.importorskip("websockets.sync.client")


ROOT = Path(__file__).resolve().parents[1]
CHROME = shutil.which("google-chrome") or shutil.which("chromium")


@pytest.mark.skipif(not CHROME, reason="Isolated Chromium required for layout/scroll QA")
@pytest.mark.parametrize("width", [390, 700, 1000, 1440])
def test_poll_redraw_preserves_viewport_list_focus_and_nonoverlapping_cards(tmp_path, width):
    functions = app_functions(
        "withDashboardToolbar", "preserveRenderedInteraction",
        "dashboardScrollPositions", "restoreDashboardScrollPositions",
        "layoutDashboardCards", "observeDashboardLayout", "renderAnalytics",
    )
    setup = r'''
const state={dashboard:{edit:false,area:'investments'},localFunds:[],localAccounts:[]};
const $=id=>document.getElementById(id);
const esc=v=>String(v);
const widgetMeta=()=>({size:'compact'});
const dashboardWidgetToolbar=()=>'';
const renderDashboardControls=()=>{};
const assetMixGroups=()=>[];
const currencyAllocationGroups=()=>[];
const sum=values=>values.reduce((a,b)=>a+b,0);
const ids=['asset_mix','currency','top_holdings','cash_currency','industry_split','bond_currency'];
const visibleDashboardWidgets=()=>ids.map(id=>({id}));
let dashboardLayoutObserver=null,dashboardLayoutFrame=0;
let cardHeight=480,shouldThrow=false;
function syntheticCard(id) {
 return `<div class="chart-card synthetic-card"><div style="height:${cardHeight}px"><h3>${id}</h3><div data-preserve-scroll="${id}" style="height:100px;overflow:auto">`+
 Array.from({length:15},(_,i)=>`<p style="height:30px">Synthetic item ${i} <button id="${id}-${i}">Open</button></p>`).join('')+'</div></div></div>';
}
const renderDonut=()=>syntheticCard('asset_mix');
const renderCurrencyAllocation=()=>syntheticCard('currency');
const renderMiniBars=()=>syntheticCard('top_holdings');
const renderCashByCurrencyBars=()=>syntheticCard('cash_currency');
const renderIndustrySplit=()=>syntheticCard('industry_split');
const renderBondsByCurrency=()=>syntheticCard('bond_currency');
// Heatmap setup reads layout before the packing observer is installed.
function renderHeatmap(){document.getElementById('analyticsBoard').getBoundingClientRect();if(shouldThrow)throw Error('synthetic render failure');}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function overlaps(){const rects=[...$('analyticsBoard').children].map(el=>el.getBoundingClientRect());return rects.some((a,i)=>rects.slice(i+1).some(b=>a.left+1<b.right&&b.left+1<a.right&&a.top+1<b.bottom&&b.top+1<a.bottom));}
(async()=>{
 const result={width:innerWidth,errors:[]};
 try {
 await pause(100);result.width=innerWidth;renderAnalytics([{}]);await pause(120);
 window.scrollTo(0,500);await pause(60);
 result.readingBefore=scrollY;result.readingAfter=[];
 for(let i=0;i<3;i++){renderAnalytics([{}]);await pause(90);result.readingAfter.push(scrollY);}
 $('top_holdings-2').focus({preventScroll:true});
 document.querySelector('[data-preserve-scroll="top_holdings"]').scrollTop=72;
 window.scrollTo(0,500);await pause(60);
 result.before=scrollY;result.after=[];
 for(let i=0;i<3;i++){
  renderAnalytics([{}]);await pause(90);
  result.after.push({y:scrollY,list:document.querySelector('[data-preserve-scroll="top_holdings"]').scrollTop,focus:document.activeElement.id,overlap:overlaps(),minHeight:$('analyticsBoard').style.minHeight});
 }
 cardHeight=740;renderAnalytics([{}]);await pause(90);result.grownOverlap=overlaps();
 cardHeight=280;renderAnalytics([{}]);await pause(90);result.shrunkOverlap=overlaps();
 document.activeElement.blur();
 const lower=document.createElement('section');lower.id='qa-holdings';lower.innerHTML=Array.from({length:40},(_,i)=>`<p style="height:70px">Synthetic holding ${i}</p>`).join('');document.querySelector('main').append(lower);
 window.scrollTo(0,lower.offsetTop+300);await pause(60);result.lowerBefore=lower.getBoundingClientRect().top;
 renderAnalytics([{}]);await pause(90);result.lowerAfter=lower.getBoundingClientRect().top;
 shouldThrow=true;try{renderAnalytics([{}])}catch(error){result.caught=error.message}
 result.afterErrorMinHeight=$('analyticsBoard').style.minHeight;
 }catch(error){result.errors.push(error.stack)}
 const report=document.createElement('pre');report.id='qa-result';report.textContent=JSON.stringify(result);document.body.append(report);
})();
'''
    css = re.sub(r'@import\s+url\("[^"]+"\);', "", (ROOT / "web/styles.css").read_text())
    document = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<link rel="stylesheet" href="styles.css"></head>'
        '<body><main style="padding:20px"><div id="analyticsBoard" class="analytics-board"></div></main>'
        f'<script>{functions}\n{setup}</script></body></html>'
    )
    (tmp_path / "styles.css").write_text(css)
    fixture = tmp_path / "scroll.html"
    fixture.write_text(document)
    process = subprocess.Popen(
        [CHROME, "--headless", "--no-sandbox", "--disable-gpu",
         f"--user-data-dir={tmp_path / 'chrome'}", "--remote-debugging-port=0", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        port_file = tmp_path / "chrome/DevToolsActivePort"
        deadline = time.monotonic() + 10
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert port_file.exists(), "Isolated Chromium did not initialize"
        port = port_file.read_text().splitlines()[0]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list") as response:
            target = next(page for page in json.load(response) if page["type"] == "page")
        with websockets.connect(target["webSocketDebuggerUrl"]) as socket:
            command_id = 0

            def command(method, params=None):
                nonlocal command_id
                command_id += 1
                socket.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
                while True:
                    message = json.loads(socket.recv(timeout=10))
                    if message.get("id") == command_id:
                        assert "error" not in message, message
                        return message["result"]

            command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 600, "deviceScaleFactor": 1, "mobile": False})
            command("Page.navigate", {"url": fixture.as_uri()})
            deadline = time.monotonic() + 10
            report = None
            while not report and time.monotonic() < deadline:
                time.sleep(0.05)
                report = command("Runtime.evaluate", {"expression": "document.getElementById('qa-result')?.textContent", "returnByValue": True})["result"].get("value")
            assert report, "Dashboard browser checks did not complete"
            result = json.loads(report)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    assert not result["errors"], result
    assert result["width"] == width, result
    assert result["before"] > 100, result
    assert result["readingBefore"] > 100, result
    assert all(abs(y - result["readingBefore"]) <= 1 for y in result["readingAfter"]), result
    for snapshot in result["after"]:
        assert abs(snapshot["y"] - result["before"]) <= 1, result
        assert abs(snapshot["list"] - 72) <= 1, result
        assert snapshot["focus"] == "top_holdings-2", result
        assert not snapshot["overlap"], result
        assert snapshot["minHeight"] == "", result
    assert not result["grownOverlap"], result
    assert not result["shrunkOverlap"], result
    assert abs(result["lowerAfter"] - result["lowerBefore"]) <= 1, result
    assert result["caught"] == "synthetic render failure", result
    assert result["afterErrorMinHeight"] == "", result
