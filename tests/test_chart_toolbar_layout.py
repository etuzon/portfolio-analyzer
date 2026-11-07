"""Compact chart controls and readable P/L annotations with actual dashboard CSS."""
import base64
import json

import pytest

from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium


def ready(tmp_path, chromium, width, language):
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": cash_browser_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    return command, evaluate


@pytest.mark.parametrize("width,language", [(1440, "en"), (1440, "he"), (390, "en"), (390, "he")])
def test_heatmap_uses_bounded_account_view_and_adjacent_reload(tmp_path, chromium, width, language):
    command, evaluate = ready(tmp_path, chromium, width, language)
    evaluate('''
resetHeatmap();heatmapView.data={accounts:[{id:'synthetic',type:'Investment',account_id:'Synthetic account with a long recognizable name'}],assets:[],excluded:[],fx:[]};
heatmapView.account_id='synthetic';
$('analyticsBoard').innerHTML=withDashboardToolbar({id:'stock_heatmap'},renderDashboardHeatmap());renderHeatmap();observeDashboardLayout($('analyticsBoard'));
''')
    geometry = evaluate('''(()=>{const rect=id=>{const r=$(id).getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width}};
return {account:rect('heatmapAccount'),view:rect('heatmapLayout'),reload:rect('heatmapReload'),overflow:document.documentElement.scrollWidth-innerWidth};})()''')
    account, view, reload = (geometry[name] for name in ["account", "view", "reload"])
    assert account["width"] > view["width"] + 10 and account["width"] <= 300, geometry
    assert view["width"] <= 220 and reload["width"] <= 42, geometry
    assert abs(view["bottom"] - reload["bottom"]) <= 1, geometry
    if width == 1440:
        assert abs(account["bottom"] - view["bottom"]) <= 1, geometry
    else:
        assert account["bottom"] < view["top"], geometry
    assert all(field["left"] >= 0 and field["right"] <= width for field in [account, view, reload]), geometry
    assert geometry["overflow"] <= 1, geometry
    assert evaluate("$('heatmapReload').closest('.heatmap-controls')!==null&&document.querySelectorAll('#heatmapReload').length===1")
    assert evaluate("$('heatmapContent').lastElementChild.classList.contains('heatmap-legend')")
    assert evaluate("$('heatmapContent').querySelector('legend').classList.contains('sr-only')")
    (tmp_path / f"compact-heatmap-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("width,language", [(1440, "en"), (1440, "he"), (390, "en"), (390, "he")])
@pytest.mark.parametrize("values", [[-8492, 5000, -25, 100], [-1000000 + index * 100000 for index in range(10)], [1000000 - index * 100000 for index in range(10)]], ids=["boundary-loss", "ten-losses", "ten-gains"])
def test_profit_numbers_clear_all_bars_and_symbol_labels_without_clipping(tmp_path, chromium, width, language, values):
    command, evaluate = ready(tmp_path, chromium, width, language)
    evaluate('''
state.baseCurrency='ILS';state.fxRates={};
qa.chartItems=VALUES.map((value,index)=>({holding:{symbol:index===0?'LONG.SYMBOL.12345':'SECURITY'+index,stock_market:'NYSE',account_id:'synthetic',currency:'ILS',unrealized_profit:value}}));
$('analyticsBoard').innerHTML=withDashboardToolbar({id:'profit'},renderProfitBars(qa.chartItems));observeDashboardLayout($('analyticsBoard'));
'''.replace("VALUES", json.dumps(values)))
    geometry = evaluate('''(()=>{const svg=document.querySelector('.profit-chart-card svg'),s=svg.getBoundingClientRect();
const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}};
const labels=[...svg.querySelectorAll('.profit-value-label')].map(rect),bars=[...svg.querySelectorAll('rect')].map(rect),symbols=[...svg.querySelectorAll('.tilted-axis-label')].map(rect);
const overlaps=(a,b)=>a.left<b.right-.5&&a.right>b.left+.5&&a.top<b.bottom-.5&&a.bottom>b.top+.5;
const viewport=document.querySelector('.profit-chart-scroll').getBoundingClientRect();
return {inside:[...labels,...symbols].every(r=>r.left>=s.left-1&&r.right<=s.right+1&&r.top>=s.top-1&&r.bottom<=s.bottom+1),firstVisible:bars[0].left>=viewport.left&&bars[0].right<=viewport.right,barOverlap:labels.some(a=>bars.some(b=>overlaps(a,b))),symbolOverlap:labels.some(a=>symbols.some(b=>overlaps(a,b))),labelOverlap:labels.some((a,i)=>labels.slice(i+1).some(b=>overlaps(a,b))),count:labels.length,overflow:document.documentElement.scrollWidth-innerWidth};})()''')
    assert geometry["inside"] and not geometry["barOverlap"] and not geometry["symbolOverlap"] and not geometry["labelOverlap"], geometry
    assert geometry["count"] == len(values) and geometry["overflow"] <= 1, geometry
    assert geometry["firstVisible"], geometry
    (tmp_path / f"profit-labels-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("width,language", [(1440, "en"), (1440, "he"), (390, "en"), (390, "he")])
def test_heatmap_discrete_color_bands_keep_readable_labels_and_bottom_legend(tmp_path, chromium, width, language):
    command, evaluate = ready(tmp_path, chromium, width, language)
    evaluate('''
resetHeatmap();
heatmapView.data={accounts:[{id:'synthetic',type:'Investment',account_id:'Synthetic'}],assets:[-.25,-1,-3,.25,1,3,0,null].map((change,index)=>({
 id:'COLOR'+index,symbol:'COLOR'+index,name:'Synthetic color fixture',stock_market:'NASDAQ',currency:'USD',asset_class:'EQUITY',
 gross_value_ils:1000,value_ils:1000,quantity:10,gross_quantity:10,price:10,previous_price:9,price_date:'2026-11-07',previous_date:'2026-11-06',
 change_percent:change,valuation_status:'ok',valuation_basis:'saved_price',status:'ok',issues:[],accounts:[{account_id:'synthetic',quantity:10,gross_value_ils:1000,value_ils:1000}]
})),excluded:[],fx:[]};
$('analyticsBoard').innerHTML=withDashboardToolbar({id:'stock_heatmap'},renderDashboardHeatmap());renderHeatmap();observeDashboardLayout($('analyticsBoard'));
''')
    geometry = evaluate(r'''(()=>{
const tiles=[...document.querySelectorAll('.heatmap-tile')];
const luminance=rgb=>rgb.match(/[\d.]+/g).slice(0,3).map(x=>Number(x)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
return {colors:tiles.map(e=>getComputedStyle(e).backgroundColor),contrast:tiles.map(e=>{const c=getComputedStyle(e);return (luminance(c.color)+.05)/(luminance(c.backgroundColor)+.05)}),title:document.querySelector('.heatmap-legend').title,legendLast:$('heatmapContent').lastElementChild.classList.contains('heatmap-legend'),overflow:document.documentElement.scrollWidth-innerWidth};})()''')
    assert len(geometry["colors"]) == len(set(geometry["colors"])) == 8, geometry
    assert min(geometry["contrast"]) >= 4.5, geometry
    assert ("Three levels" if language == "en" else "שלוש דרגות") in geometry["title"], geometry
    assert geometry["legendLast"] and geometry["overflow"] <= 1, geometry
    evaluate("$('heatmapContent').closest('.portfolio-heatmap-card').scrollIntoView({block:'start'});")
    (tmp_path / f"heatmap-three-bands-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    assert evaluate("qa.errors") == []
