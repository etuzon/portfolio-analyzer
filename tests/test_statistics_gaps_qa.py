"""Independent dashboard-statistics QA using synthetic, read-only browser state."""

import base64
import re

import pytest

from test_account_cash_update_qa import cash_browser_document, browser_wait, enter
from test_native_account_history_qa import chromium


def statistics_document(tmp_path, language):
    page = cash_browser_document(tmp_path, language)
    setup = r'''
qa.ready=false;qa.calls=[];qa.posts=[];
state.auth.user={id:'qa-viewer',username:'qa-viewer',role:'Viewer'};
state.localAccounts=[];state.localTransactions=[];
state.portfolioReady=true;state.portfolioSourceState='ready';state.portfolioRefreshPending=false;
state.dashboardArea='all';state.alertData={active_signals:[]};state.dividendEvents=[];
const missing=['price history','income','profit','dividend','profit/market cap','industry'];
qa.makeItem=(symbol,account,fields,analytics='ready')=>({
 holding:{symbol,name:symbol,account,account_id:account,quantity:1,market_value:100,
 currency:'USD',asset_class:'EQUITY',stock_market:'NYSE',account_type:'Investment',location:'USA'},
 missing:[...fields],analytics_state:analytics,market_cap:null,industry:'',
 income_trend:{state:fields.includes('income')?'missing':'ok',series:[]},
 profit_trend:{state:fields.includes('profit')?'missing':'ok',series:[]},
 dividend_trend:{state:fields.includes('dividend')?'missing':'ok',series:[]},
 profit_market_cap_trend:{state:fields.includes('profit/market cap')?'missing':'ok',series:[]},
 price_ranges:{},moving_averages:{},support_resistance:{},volume:{},provider_status:{}
});
qa.symbol='QA<&"LONG_'+'S'.repeat(60);
qa.account='Synthetic <&" Account '+'A'.repeat(60);
qa.items=[qa.makeItem(qa.symbol,qa.account,missing),
 qa.makeItem(qa.symbol,'Synthetic Second Account',['dividend']),
 qa.makeItem('COMPLETE','Synthetic Third Account',[])];
qa.render=(items=qa.items)=>{
 state.allPortfolioItems=qa.items;state.filteredItems=items;state.items=items;
 $('analyticsBoard').innerHTML=withDashboardToolbar({id:'portfolio_value'},renderPortfolioValueDashboard(items));
 observeDashboardLayout($('analyticsBoard'));
 window.PortfolioI18n.applyToDocument(state.language);
};
qa.render();qa.ready=true;
'''
    script = tmp_path / "statistics-setup.js"
    script.write_text(setup)
    text = page.read_text().replace("</body>", f'<script src="{script.as_uri()}"></script></body>')
    page.write_text(text)
    return page


@pytest.mark.parametrize("width,language", [(390, "en"), (1440, "en"), (390, "he"), (1440, "he")])
def test_summary_statistics_all_six_labels_and_native_multiline_hover(tmp_path, chromium, width, language):
    command, evaluate = chromium
    fixture = statistics_document(tmp_path, language)
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": fixture.as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate("document.querySelector('.summary-drawer').open=true;document.querySelector('.summary-drawer').scrollIntoView({block:'center'});")
    browser_wait(evaluate, "document.querySelector('.summary-stat').checkVisibility()")
    assert evaluate("qa.errors") == []
    assert evaluate("innerWidth") == width
    stats = evaluate("Array.from(document.querySelectorAll('.summary-stat')).map(el=>({text:el.innerText,title:el.title,label:el.querySelector('span').textContent}))")
    labels = [entry["label"] for entry in stats]
    assert len(labels) == 6, labels
    if language == "he":
        assert all(not any(c.isascii() and c.isalpha() for c in label) for label in labels), labels
        assert all(not re.search(r"[A-Za-z]{3,}", entry["title"]) for entry in stats[:-1]), stats
        assert not re.search(r"[A-Za-z]", gap_detail := stats[-1]["text"]), gap_detail
    else:
        assert labels == ["Risk", "Positions", "Securities", "Equities", "Bonds", "Data gaps"]
    gap = stats[-1]
    assert gap["text"].splitlines()[0] == "7", gap
    assert "\n" in gap["title"], gap
    assert evaluate("qa.symbol") in gap["title"]
    assert evaluate("qa.account") in gap["title"]
    assert "Synthetic Second Account" in gap["title"]
    assert evaluate("document.querySelectorAll('.summary-stat img,.summary-stat script').length") == 0
    assert evaluate("qa.calls.length===0&&qa.posts.length===0")
    shot = command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    (tmp_path / f"statistics-{language}-{width}.png").write_bytes(base64.b64decode(shot["data"]))


@pytest.mark.parametrize("width,language", [(390, "en"), (1440, "en"), (390, "he"), (1440, "he")])
def test_gap_details_keyboard_pointer_scope_states_and_escaping(tmp_path, chromium, width, language):
    command, evaluate = chromium
    fixture = statistics_document(tmp_path, language)
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": fixture.as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate("""qa.items.push(qa.makeItem('QUEUED','Synthetic Loading Account',['income','dividend'],'queued'));
    qa.items.push(qa.makeItem('FAILED','Synthetic Failed Account',['income','dividend'],'failed'));
    qa.items[4].income_trend.state='error';qa.items[4].dividend_trend.state='error';
    qa.render();document.querySelector('.summary-drawer').open=true;
    document.querySelector('[data-data-gaps-scope="portfolio"]').scrollIntoView({block:'center'});
    document.querySelector('[data-data-gaps-scope="portfolio"]').focus();""")
    trigger = "document.querySelector('[data-data-gaps-scope=\"portfolio\"]')"
    assert evaluate(f"{trigger}.tagName") == "BUTTON"
    assert evaluate(f"{trigger}.querySelector('b').textContent") == "7"
    browser_wait(evaluate, "document.activeElement.matches('[data-data-gaps-scope]')")
    enter(command)
    browser_wait(evaluate, "!$('dataGapsModal').hidden")
    contents = evaluate("$('dataGapsContent').innerText")
    for expected in [evaluate("qa.symbol"), evaluate("qa.account"), "Synthetic Second Account", "QUEUED", "FAILED"]:
        assert expected in contents, (expected, contents)
    assert ("zero dividend" if language == "en" else "אין בכך אישור שהדיבידנד הוא אפס") in contents
    if language == "en":
        for expected in ["Price history", "income", "profit", "dividend", "industry", "Loading", "failed"]:
            assert expected.lower() in contents.lower(), (expected, contents)
    else:
        for unexpected in ["No dividend history", "Financial data could not", "Loading financial", "No price history"]:
            assert unexpected not in contents
    assert evaluate("$('dataGapsContent').querySelectorAll('script,img').length") == 0
    browser_wait(evaluate, "$('dataGapsModal').contains(document.activeElement)")
    assert evaluate("$('dataGapsContent').scrollWidth<=$('dataGapsContent').clientWidth+1")
    assert evaluate("qa.calls.length===0&&qa.posts.length===0")
    shot = command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    (tmp_path / f"gap-details-{language}-{width}.png").write_bytes(base64.b64decode(shot["data"]))

    # Every position remains available beyond a top-three preview.
    evaluate("$('dataGapsContent').scrollTop=150;$('dataGapsContent').focus();")
    previous_scroll = evaluate("$('dataGapsContent').scrollTop")
    assert previous_scroll > 0
    evaluate("qa.extra=Array.from({length:5},(_,i)=>qa.makeItem('EXTRA-'+i,'Synthetic Extra Account '+i,['industry']));qa.render([...qa.items,...qa.extra]);")
    browser_wait(evaluate, "$('dataGapsContent').textContent.includes('EXTRA-4')")
    assert evaluate(f"{trigger}.querySelector('b').textContent") == "12"
    assert evaluate("$('dataGapsContent').scrollTop") == previous_scroll
    assert evaluate("document.activeElement===$('dataGapsContent')")

    # Changing the loaded dashboard scope replaces both count and the open reading.
    evaluate("qa.render(filterPortfolioItems(qa.items,{account:'Synthetic Second Account',includeMissing:true}));")
    browser_wait(evaluate, "!$('dataGapsContent').textContent.includes('Synthetic Failed Account')")
    assert evaluate(f"{trigger}.querySelector('b').textContent") == "1"
    assert "Synthetic Second Account" in evaluate("$('dataGapsContent').textContent")
    assert evaluate("qa.account") not in evaluate("$('dataGapsContent').textContent")

    evaluate("$('dataGapsModal').querySelector('[data-close]').click();")
    browser_wait(evaluate, "$('dataGapsModal').hidden")
    evaluate("qa.render([qa.items[2]]);document.querySelector('.summary-drawer').open=true;")
    assert evaluate(f"{trigger}.querySelector('b').textContent") == "0"
    # Pointer activation is the touch/desktop path and must remain available for zero.
    evaluate(f"{trigger}.scrollIntoView({{block:'center'}});")
    point = evaluate(f"(()=>{{const r={trigger}.getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})()")
    if width == 390:
        command("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 1})
        command("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{**point, "id": 1}]})
        command("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    else:
        command("Input.dispatchMouseEvent", {"type": "mousePressed", "button": "left", "clickCount": 1, **point})
        command("Input.dispatchMouseEvent", {"type": "mouseReleased", "button": "left", "clickCount": 1, **point})
    browser_wait(evaluate, "!$('dataGapsModal').hidden")
    assert ("No missing analytics fields" if language == "en" else "אין שדות ניתוח חסרים") in evaluate("$('dataGapsContent').innerText")
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
    browser_wait(evaluate, "$('dataGapsModal').hidden")
    browser_wait(evaluate, "document.activeElement.matches('[data-data-gaps-scope]')")
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": " ", "code": "Space", "windowsVirtualKeyCode": 32, "text": " "})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": " ", "code": "Space", "windowsVirtualKeyCode": 32})
    browser_wait(evaluate, "!$('dataGapsModal').hidden")
    evaluate("qa.render([qa.items[3],qa.items[4]]);")
    assert evaluate(f"{trigger}.querySelector('b').textContent") == "0"
    status_text = evaluate("$('dataGapsContent').innerText")
    assert "QUEUED" in status_text and "FAILED" in status_text
    assert "No missing analytics fields" not in status_text
    assert "אין שדות ניתוח חסרים" not in status_text
    # Even a ready row can contain field-level pending/error evidence.
    evaluate("qa.mixed=qa.makeItem('FIELD-STATES','Synthetic Mixed Account',['income','profit','dividend']);qa.mixed.income_trend.state='pending';qa.mixed.profit_trend.state='error';qa.render([qa.mixed]);")
    browser_wait(evaluate, "$('dataGapsContent').textContent.includes('FIELD-STATES')")
    assert evaluate(f"{trigger}.querySelector('b').textContent") == "1"
    row_status = evaluate("(()=>{const el=document.createElement('div');el.innerHTML=statusCell(qa.mixed);return {count:el.querySelector('strong').textContent,badges:Array.from(el.querySelectorAll('.badge')).map(el=>el.textContent)};})()")
    assert row_status["count"] == ("1 data gaps" if language == "en" else "1 פערי נתונים"), row_status
    assert row_status["badges"] == (["Updating analytics", "Update failed"] if language == "en" else ["מעדכן נתוני ניתוח", "העדכון נכשל"]), row_status

    # The separate Snapshot card uses its own current loaded scope and the same reader.
    evaluate("$('dataGapsModal').querySelector('[data-close]').click();")
    # Closing restores focus on the next animation frame. Finish that real
    # lifecycle before beginning a different control's keyboard interaction.
    browser_wait(evaluate, "$('dataGapsModal').hidden&&document.activeElement===document.querySelector('[data-data-gaps-scope=portfolio]')")
    evaluate("$('analyticsBoard').insertAdjacentHTML('beforeend','<div id=qa-snapshot></div>');$('qa-snapshot').innerHTML=withDashboardToolbar({id:'snapshot'},renderBubbles(qa.items));")
    snapshot_trigger = "document.querySelector('[data-data-gaps-scope=\"snapshot\"]')"
    snapshot = evaluate("Array.from($('qa-snapshot').querySelectorAll('.bubble-stat')).map(el=>({label:el.querySelector('span').textContent,detail:el.querySelector('small').textContent,title:el.title}))")
    assert len(snapshot) == 4, snapshot
    if language == "he":
        assert all(not re.search(r"[A-Za-z]", entry["label"]+entry["detail"]) for entry in snapshot), snapshot
        assert all(not re.search(r"[A-Za-z]", entry["title"]) for entry in snapshot[:-1]), snapshot
    else:
        assert [entry["label"] for entry in snapshot] == ["Positions", "Securities", "Winners", "Data gaps"]
    assert evaluate(f"{snapshot_trigger}.querySelector('strong').textContent") == "7"
    assert "\n" in snapshot[-1]["title"] and evaluate("qa.account") in snapshot[-1]["title"]
    evaluate(f"{snapshot_trigger}.scrollIntoView({{block:'center'}});{snapshot_trigger}.focus();")
    enter(command)
    browser_wait(evaluate, "!$('dataGapsModal').hidden&&$('dataGapsModal').dataset.gapScope==='snapshot'")
    assert evaluate("qa.account") in evaluate("$('dataGapsContent').textContent")
    assert "Synthetic Second Account" in evaluate("$('dataGapsContent').textContent")
    evaluate("$('qa-snapshot').innerHTML=withDashboardToolbar({id:'snapshot'},renderBubbles(filterPortfolioItems(qa.items,{account:'Synthetic Second Account',includeMissing:true})));")
    browser_wait(evaluate, "!$('dataGapsContent').textContent.includes(qa.account)")
    assert evaluate(f"{snapshot_trigger}.querySelector('strong').textContent") == "1"
    assert "Synthetic Second Account" in evaluate("$('dataGapsContent').textContent")
    assert evaluate("qa.errors") == []
    assert evaluate("qa.calls.length===0&&qa.posts.length===0")


@pytest.mark.parametrize("language", ["en", "he"])
def test_amber_alarm_header_retains_warning_without_question_mark(tmp_path, chromium, language):
    command, evaluate = chromium
    command("Page.navigate", {"url": statistics_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate("""qa.alarms=[{kind:'risk',key:'qa-limited',level:'limited',title:t('Total portfolio risk'),
    body:t('Some model inputs are missing. The calculated score uses the existing data-quality penalty.'),meta:t('View risk details')}];
    visiblePriorityAlarms=()=>qa.alarms;dividendAlarms=()=>[];vestingAlarms=()=>[];
    state.alarmsEventsLoaded=true;state.alertData={active_signals:[]};renderAlarms();""")
    header = evaluate("({text:$('alarmsButton').innerText,count:$('alarmsCount').textContent,tone:$('alarmsButton').dataset.alarmTone,label:$('alarmsButton').getAttribute('aria-label'),title:$('alarmsButton').title,list:$('alarmsList').textContent})")
    assert "?" not in header["text"], header
    assert header["count"] == "1" and header["tone"] == "amber", header
    warning = "Limited risk data" if language == "en" else "נתוני סיכון חלקיים"
    assert warning in header["label"] and warning in header["title"], header
    assert ("Some model inputs are missing" if language == "en" else "חלק מנתוני המודל חסרים") in header["list"], header
    assert evaluate("$('alarmsButton').classList.contains('has-alarms')")
    # The existing high-severity symbol is still meaningful.
    evaluate("qa.alarms[0].level='high';renderAlarms();")
    assert evaluate("$('alarmsPrioritySymbol').textContent") == "!"
