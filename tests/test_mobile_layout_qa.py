"""Independent responsive acceptance using disposable Chromium and synthetic state.

Real markup/CSS/scripts are loaded; startup/auth/network and external fonts are
isolated by the existing cash fixture. This is layout/interaction evidence, not
a live authenticated journey or physical iOS/Android browser certification.
"""

import base64
import json
from pathlib import Path

import pytest

from test_account_cash_update_qa import cash_browser_document, browser_wait
from test_native_account_history_qa import chromium, ROOT  # noqa: F401


VIEWPORTS = [(width, language) for width in (320, 360, 390, 430, 760, 1280, 1440) for language in ("en", "he")]


def load(tmp_path, chromium, width, language, height=700):
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": cash_browser_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    assert evaluate("innerWidth") == width
    assert evaluate("document.documentElement.dir") == ("rtl" if language == "he" else "ltr")
    assert evaluate("qa.errors") == []
    return command, evaluate


@pytest.mark.parametrize("width,language", VIEWPORTS)
def test_dashboard_and_holdings_fit_with_readable_scrollable_values(tmp_path, chromium, width, language):
    _, evaluate = load(tmp_path, chromium, width, language)
    evaluate("""
state.dashboard=defaultDashboard();
state.accountTrend={accounts:[]};
$('analyticsBoard').innerHTML=withDashboardToolbar({id:'portfolio_value',view:'basic'},renderPortfolioValueDashboard([]))+withDashboardToolbar({id:'account_trend',view:'basic'},renderAccountValueTrend());
observeDashboardLayout($('analyticsBoard'));
$('rows').innerHTML='<tr>'+Array.from({length:9},(_,i)=>'<td data-label="QA value"><span dir="ltr">'+(i===0?'SYNTHETIC QA':'1,234,567.89 USD')+'</span></td>').join('')+'</tr>';
window.PortfolioI18n.applyToDocument(state.language);
""")
    layout = evaluate("""(()=>{
const board=$('analyticsBoard').getBoundingClientRect(),wrap=document.querySelector('.holdings-table-wrap'),r=wrap.getBoundingClientRect();
return {document:document.documentElement.scrollWidth,board:{left:board.left,right:board.right},table:{left:r.left,right:r.right,client:wrap.clientWidth,scroll:wrap.scrollWidth,overflow:getComputedStyle(wrap).overflowX},cards:[...$('analyticsBoard').children].map(e=>({width:e.getBoundingClientRect().width,scroll:e.scrollWidth,client:e.clientWidth}))};})()""")
    assert layout["document"] <= width + 1, layout
    assert layout["board"]["left"] >= -1 and layout["board"]["right"] <= width + 1, layout
    assert all(c["scroll"] <= c["client"] + 1 for c in layout["cards"]), layout
    assert layout["table"]["left"] >= -1 and layout["table"]["right"] <= width + 1, layout
    assert layout["table"]["overflow"] in ("auto", "scroll"), layout
    # Direction-aware native scrolling must expose the final complete value.
    last = evaluate("""(()=>{const wrap=document.querySelector('.holdings-table-wrap'),cell=$('rows').lastElementChild.lastElementChild;cell.scrollIntoView({block:'center',inline:'end'});const r=cell.getBoundingClientRect(),w=wrap.getBoundingClientRect();return {left:r.left,right:r.right,wrapLeft:w.left,wrapRight:w.right,text:cell.textContent,valueWidth:cell.firstElementChild.getBoundingClientRect().width,cellWidth:r.width,document:document.documentElement.scrollWidth};})()""")
    assert last["left"] >= last["wrapLeft"] - 2 and last["right"] <= last["wrapRight"] + 2, last
    assert last["valueWidth"] <= last["cellWidth"], last
    assert last["text"] == "1,234,567.89 USD"
    assert last["document"] <= width + 1, last
    assert evaluate("qa.errors") == []
    evaluate("scrollTo(0,0);")
    screenshot(command=chromium[0], name=f"dashboard-{width}-{language}")


@pytest.mark.parametrize("width,language", VIEWPORTS)
def test_navigation_reaches_last_action_and_preserves_desktop(tmp_path, chromium, width, language):
    command, evaluate = load(tmp_path, chromium, width, language)
    if width <= 760:
        assert evaluate("getComputedStyle($('navigationToggle')).display") != "none"
        assert evaluate("getComputedStyle($('appNavigation')).display") == "none"
        evaluate("$('navigationToggle').click();document.querySelectorAll('.nav-menu').forEach(e=>e.open=true);")
        assert evaluate("$('navigationToggle').getAttribute('aria-expanded')") == "true"
        # The final launcher must remain reachable even when categories grow tall.
        result = evaluate("""(()=>{const e=$('openAssistant');e.scrollIntoView({block:'center'});e.focus({preventScroll:true});const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,visible:document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)===e};})()""")
        assert 0 <= result["top"] and result["bottom"] <= 700 and result["visible"], result
        assert result["left"] >= 0 and result["right"] <= width, result
        # Escape closes one category first, then the mobile navigation.
        evaluate("document.querySelectorAll('.nav-menu').forEach(e=>e.open=false);")
        # Escape closes navigation and restores the toggle as keyboard target.
        command("Input.dispatchKeyEvent", {"type":"keyDown", "key":"Escape", "code":"Escape", "windowsVirtualKeyCode":27})
        command("Input.dispatchKeyEvent", {"type":"keyUp", "key":"Escape", "code":"Escape", "windowsVirtualKeyCode":27})
        assert evaluate("$('navigationToggle').getAttribute('aria-expanded')") == "false"
        assert evaluate("document.activeElement.id") == "navigationToggle"
    else:
        assert evaluate("getComputedStyle($('navigationToggle')).display") == "none"
        assert evaluate("getComputedStyle($('appNavigation')).display") != "none"
        evaluate("document.querySelector('.nav-menu summary').click();")
        assert evaluate("document.querySelector('.nav-menu').open") is True
    assert evaluate("document.querySelectorAll('.nav-menu').length") == 7
    assert evaluate("document.documentElement.scrollWidth") <= width + 1
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("width,language", VIEWPORTS)
def test_cash_dialog_bounds_numeric_value_and_keyboard_cancel(tmp_path, chromium, width, language):
    command, evaluate = load(tmp_path, chromium, width, language)
    evaluate("$('qa-cash-trigger').focus();$('qa-cash-trigger').click();")
    browser_wait(evaluate, "!$('accountCashModal').hidden&&!$('accountCashTarget').disabled")
    assert evaluate("document.activeElement.id") == "accountCashTarget"
    evaluate("$('accountCashTarget').value='-1234567.89';$('accountCashTarget').dispatchEvent(new Event('input',{bubbles:true}));")
    assert evaluate("$('accountCashTarget').value") == "-1234567.89"
    controls = evaluate("""['accountCashTarget','accountCashCurrency','accountCashDate','accountCashSave'].map(id=>{const e=$(id);e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect(),c=getComputedStyle(e);return {id,left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,font:parseFloat(c.fontSize)};})""")
    assert all(c["left"] >= -1 and c["right"] <= width+1 and c["top"] >= -1 and c["bottom"] <= 701 for c in controls), controls
    amount = controls[0]
    assert amount["width"] >= 200, controls
    if width <= 760:
        assert all(c["font"] >= 16 for c in controls if c["id"] != "accountCashSave"), controls
    assert evaluate("$('accountCashCurrency').value") == "USD"
    assert evaluate("$('accountCashDate').value") == "06/11/2026"
    command("Input.dispatchKeyEvent", {"type":"keyDown", "key":"Escape", "code":"Escape", "windowsVirtualKeyCode":27})
    command("Input.dispatchKeyEvent", {"type":"keyUp", "key":"Escape", "code":"Escape", "windowsVirtualKeyCode":27})
    browser_wait(evaluate, "$('accountCashModal').hidden")
    assert evaluate("qa.posts.length") == 0
    browser_wait(evaluate, "document.activeElement.id==='qa-cash-trigger'")
    assert evaluate("qa.errors") == []


def screenshot(command, name):
    directory=Path('/tmp/portfolio-mobile-qa')
    directory.mkdir(exist_ok=True)
    result=command('Page.captureScreenshot', {'format':'png'})
    (directory / (name+'.png')).write_bytes(base64.b64decode(result['data']))


@pytest.mark.parametrize('width,height,language', [(320,700,'en'),(320,700,'he'),(700,390,'en'),(700,390,'he'),(1440,900,'en'),(1440,900,'he')])
def test_secondary_dialogs_and_real_table_scroll(tmp_path, chromium, width, height, language):
    command, evaluate=load(tmp_path,chromium,width,language,height)
    if width <= 760:
        evaluate("$('navigationToggle').click();document.querySelectorAll('.nav-menu').forEach(e=>e.open=true);$('openAssistant').scrollIntoView({block:'center'});")
        visible=evaluate("(()=>{const e=$('openAssistant'),r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,hit:document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)===e};})()")
        assert visible['top']>=0 and visible['bottom']<=height and visible['hit'],visible
        screenshot(command,f'navigation-{width}x{height}-{language}')
        evaluate("setMobileNavigation(false);")
    # Open real dialog structure while keeping unrelated data requests synthetic.
    for modal_id in ('settingsModal','helpModal','assistantModal'):
        evaluate(f"openModal('{modal_id}');")
        bounds=evaluate(f"""(()=>{{const m=$('{modal_id}'),c=m.querySelector('.modal-card'),r=c.getBoundingClientRect();return {{left:r.left,right:r.right,top:r.top,bottom:r.bottom,client:c.clientWidth,scroll:c.scrollWidth,controls:[...c.querySelectorAll('input:not([type=checkbox]):not([type=radio]),select,textarea')].filter(e=>e.getClientRects().length).map(e=>{{const r=e.getBoundingClientRect();return {{id:e.id,left:r.left,right:r.right,width:r.width}};}})}};}})()""")
        screenshot(command,f'{modal_id}-{width}x{height}-{language}')
        assert bounds['left']>=-1 and bounds['right']<=width+1, (modal_id,bounds)
        assert bounds['top'] >= (52 if width<=760 else -1) and bounds['bottom']<=height+1, (modal_id,bounds)
        assert bounds['scroll']<=bounds['client']+1,(modal_id,bounds)
        assert all(c['left']>=-1 and c['right']<=width+1 for c in bounds['controls']),(modal_id,bounds)
        if modal_id=='assistantModal' and height<450:
            # Wheel/touch scrolling must expose Send without script-forced hidden scrolling.
            evaluate("$('assistantModal').querySelector('.modal-card').scrollTop=0;")
            center=evaluate("(()=>{const r=$('assistantModal').querySelector('.modal-card').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()")
            for _ in range(3):
                command('Input.dispatchMouseEvent',{'type':'mouseWheel','x':center['x'],'y':center['y'],'deltaX':0,'deltaY':300})
                evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            send=evaluate("(()=>{const e=$('askAssistant'),r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,hit:document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)===e};})()")
            assert send['top']>=0 and send['bottom']<=height and send['hit'],send
        if modal_id=='assistantModal':
            for selector in ('#assistantPrompt','#askAssistant','.section-head [data-close]'):
                target=evaluate("(()=>{const e=$('assistantModal').querySelector("+json.dumps(selector)+");e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,hit:document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)===e};})()")
                assert target['top']>=0 and target['bottom']<=height and target['hit'],(selector,target)
        screenshot(command,f'{modal_id}-{width}x{height}-{language}')
        evaluate(f"closeModal($('{modal_id}'));")
    # The actual position-history table remains a table and scrolls separately.
    evaluate("""
const wrap=document.querySelector('.transaction-history-wrap');
document.querySelector('.workspace').append(wrap);
$('positionTransactionsRows').innerHTML='<tr>'+Array.from({length:8},(_,i)=>'<td><span dir="ltr">'+(i===0?'10/11/2026':'1,234,567.89 USD')+'</span></td>').join('')+'</tr>';
""")
    table=evaluate("""(()=>{const w=document.querySelector('.transaction-history-wrap'),cell=$('positionTransactionsRows').lastElementChild.lastElementChild;cell.scrollIntoView({block:'center',inline:'end'});const r=cell.getBoundingClientRect(),b=w.getBoundingClientRect();return {client:w.clientWidth,scroll:w.scrollWidth,left:r.left,right:r.right,wrapLeft:b.left,wrapRight:b.right,overflow:getComputedStyle(w).overflowX,document:document.documentElement.scrollWidth};})()""")
    assert table['document']<=width+1,table
    assert table['overflow'] in ('auto','scroll'),table
    assert table['left']>=table['wrapLeft']-2 and table['right']<=table['wrapRight']+2,table
    if width<=760:
        assert table['scroll']>table['client'],table
    assert evaluate('qa.errors')==[]


@pytest.mark.parametrize('language',['en','he'])
def test_desktop_to_phone_resize_preserves_unsaved_numeric_value(tmp_path,chromium,language):
    command,evaluate=load(tmp_path,chromium,1440,language)
    evaluate("$('qa-cash-trigger').click();")
    browser_wait(evaluate,"!$('accountCashModal').hidden&&!$('accountCashTarget').disabled")
    evaluate("$('accountCashTarget').value='-1234567.89';$('accountCashTarget').dispatchEvent(new Event('input',{bubbles:true}));")
    command('Emulation.setDeviceMetricsOverride',{'width':320,'height':700,'deviceScaleFactor':1,'mobile':False})
    browser_wait(evaluate,'innerWidth===320')
    assert evaluate("$('accountCashTarget').value")=='-1234567.89'
    assert evaluate('qa.posts.length')==0
    assert evaluate("(()=>{const r=$('accountCashTarget').getBoundingClientRect();return r.left>=0&&r.right<=320;})()")
    assert evaluate('qa.errors')==[]


@pytest.mark.parametrize('width,language',[(1280,'en'),(1280,'he'),(1440,'en'),(1440,'he')])
def test_desktop_computed_layout_unchanged_by_phone_rules(tmp_path,chromium,width,language):
    _,evaluate=load(tmp_path,chromium,width,language)
    evaluate("openModal('settingsModal');")
    measure="""JSON.stringify([...document.querySelectorAll('.sidebar,#appNavigation,.workspace,#settingsModal .modal-card,#settingsModal input,#settingsModal select')].map(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return {id:e.id,x:r.x,y:r.y,width:r.width,height:r.height,display:s.display,columns:s.gridTemplateColumns,font:s.fontSize,padding:s.padding};}))"""
    before=evaluate(measure)
    original_css=(ROOT/'web/styles.css').read_text()
    baseline_css=original_css.split('/* Phone layout stays below the existing desktop/navigation breakpoint. */')[0]
    # Local file stylesheets disallow CSSOM rule access; use equivalent inline CSS.
    evaluate("document.querySelector('link[href*=styles]').disabled=true;window.qaStyle=document.createElement('style');qaStyle.textContent="+json.dumps(original_css)+";document.head.append(qaStyle);")
    assert evaluate(measure)==before
    evaluate("qaStyle.textContent="+json.dumps(baseline_css))
    assert evaluate(measure)==before
