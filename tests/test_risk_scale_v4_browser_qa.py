"""Independent full-renderer journeys with disposable synthetic-only browsers.

The real app builds the dashboard from the raw economic fixtures. No user's
browser, signed-in session, runtime database or external provider is accessed.
"""
import base64
from copy import deepcopy
import json
from pathlib import Path

import pytest

from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium
from test_risk_scale_v4_independent_qa import CASES


def fixture_page(tmp_path, language):
    page = cash_browser_document(tmp_path, language)
    source = tmp_path / "cash-app.js"
    selected = []
    accounts = []
    for number, identifier in [(20, "qa-leveraged"), (6, "qa-mmf"), (4, "qa-debt"), (50, "qa-unknown")]:
        case = deepcopy(CASES[number - 1])
        for item in case["items"]:
            item["holding"].update(account_id=identifier, account=identifier, account_type="Investment", location="Israel")
            if number == 50:
                item["holding"]["symbol"] = "QAOPTION"
                item["stress_risk"]["security_key"] = "QAOPTION|QA|ILS"
        selected.extend(case["items"])
        accounts.append(dict(id=identifier, username=identifier, account_id=identifier, type="Investment",
                             location="Israel", currency="ILS", persons=[],
                             initial_cash=sum(row["value"] for row in case["options"]["cashAccounts"])))
    setup = "\nqa.holdings=" + json.dumps(selected) + ";\nstate.localAccounts=" + json.dumps(accounts) + ";\n" + r"""
state.localTransactions=[];state.localFunds=[];
state.items=state.allPortfolioItems=qa.holdings;
state.baseCurrency='ILS';state.fxRates={};state.riskAsOf='2026-11-14';
state.portfolioReady=true;state.portfolioSourceState='ready';state.portfolioRefreshPending=false;
state.dashboard=defaultDashboard();
state.dashboard.widgets=state.dashboard.widgets.map(widget=>({...widget,view:widget.id==='portfolio_value'?'basic':'hidden'}));
qa.before=JSON.stringify({holdings:qa.holdings,accounts:state.localAccounts,transactions:state.localTransactions});
qa.illegalPosts=[];
const legacy=PortfolioStressRisk.calculate([{holding:{symbol:'LEGACY',stock_market:'QA',currency:'ILS',account_id:'qa-leveraged',asset_class:'EQUITY',market_value:100,quantity:100},
 stress_risk:{security_key:'LEGACY|QA|ILS',valuation_date:'2026-11-14',issuer_id:'legal:LEGACY',country:{country_code:'IL',basis:'economic_exposure'},country_rating:{status:'rated',rating:'AAA',agency:'sp',scope:'sovereign',scale:'global',term:'long_term',verified:true,source_kind:'agency_public'},currency_exposures:{ILS:1},parameters:{instrument_kind:'equity',country_currency:'ILS'}}}],{baseCurrency:'ILS',asOf:'2026-11-14'});
legacy.model='portfolio-risk-v3';legacy.score=80;legacy.loss_pct=40;legacy.stress_loss=40;legacy.as_of='2026-11-13';
delete legacy.score_unit;delete legacy.score_scale;delete legacy.scenario_horizon;
qa.render=()=>{renderAnalytics(qa.holdings);PortfolioI18n.applyToDocument(state.language);};
qa.render();
const current=state.riskSnapshot.accounts.find(row=>row.key==='qa-leveraged').risk;
qa.history={model:'portfolio-risk-v4',models:['portfolio-risk-v3','portfolio-risk-v4'],base_currency:'ILS',
 accounts:[{id:'qa-leveraged',label:'qa-leveraged'}],items:[
 {model:'portfolio-risk-v3',date:'2026-11-13',observed_at:'2026-11-13T12:00:00Z',base_currency:'ILS',total:legacy,accounts:[{account_id:'qa-leveraged',risk:legacy}]},
 {model:'portfolio-risk-v4',date:'2026-11-14',observed_at:'2026-11-14T12:00:00Z',base_currency:'ILS',total:current,accounts:[{account_id:'qa-leveraged',risk:current}]}]};
recordRiskHistory=async()=>{};
api=async(path,options={})=>{
 qa.calls.push(path);
 if(options.method&&options.method!=='GET'){qa.illegalPosts.push({path,method:options.method});throw Error('QA blocks state mutation');}
 if(path.startsWith('/api/portfolio/risk-history'))return qa.history;
 if(path.startsWith('/api/securities/risk-inputs'))return{security_key:'QAOPTION|QA|ILS',identity_token:'qa-only',revision:0,parameters:{},local_parameters:{}};
 return{items:[]};
};
qa.events=[];for(const eventName of ['pointerover','focusin','click','scroll'])document.addEventListener(eventName,event=>qa.events.push({type:event.type,target:event.target?.outerHTML?.slice(0,180),at:performance.now()}),true);
PortfolioI18n.observe();qa.browserReady=true;
"""
    source.write_text(source.read_text() + setup)
    return page


def click(command, evaluate, selector):
    evaluate("document.querySelector(" + json.dumps(selector) + ").scrollIntoView({behavior:'instant',block:'center'})")
    evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
    geometry = evaluate("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");if(!e)throw Error('Missing test control');const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,t=document.elementFromPoint(x,y);return{x,y,hit:e===t||e.contains(t),target:t?.outerHTML.slice(0,250)};})()")
    assert geometry.pop("hit"), (selector, geometry)
    geometry.pop("target")
    command("Input.dispatchMouseEvent", {"type": "mouseMoved", **geometry})
    evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
    probe = evaluate("(()=>{const e=document.querySelector(" + json.dumps(selector) + "),p=$('riskBadgeExplanation'),r=e.getBoundingClientRect(),s=p.getBoundingClientRect(),c=getComputedStyle(p),x=" + str(geometry["x"]) + ",y=" + str(geometry["y"]) + ",hit=document.elementFromPoint(x,y);const probe={selector:" + json.dumps(selector) + ",x,y,badge:{left:r.left,right:r.right,top:r.top,bottom:r.bottom},popup:{left:s.left,right:s.right,top:s.top,bottom:s.bottom,hidden:p.hidden},style:{boxSizing:c.boxSizing,minHeight:c.minHeight,maxHeight:c.maxHeight},sameControl:e===hit||e.contains(hit),hit:hit?.outerHTML.slice(0,250)};(qa.clickProbes??=[]).push(probe);return probe;})()")
    assert probe["sameControl"], probe
    command("Input.dispatchMouseEvent", {"type": "mousePressed", **geometry, "button": "left", "clickCount": 1})
    command("Input.dispatchMouseEvent", {"type": "mouseReleased", **geometry, "button": "left", "clickCount": 1})


def press(command, key, code, key_code, text=None):
    event = {"key": key, "code": code, "windowsVirtualKeyCode": key_code}
    if text is not None:
        event["text"] = text
    command("Input.dispatchKeyEvent", {"type": "keyDown", **event})
    command("Input.dispatchKeyEvent", {"type": "keyUp", **event})


def tap(command, evaluate, selector):
    evaluate("document.querySelector(" + json.dumps(selector) + ").scrollIntoView({behavior:'instant',block:'center'})")
    evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
    point = evaluate("(()=>{const r=document.querySelector(" + json.dumps(selector) + ").getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};})()")
    command("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{**point, "radiusX": 1, "radiusY": 1, "force": 1}]})
    command("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


@pytest.mark.parametrize("language,width", [("en", 1440), ("he", 1440), ("en", 390), ("he", 390)])
def test_dashboard_badges_gaps_history_and_recovery_use_real_renderers(tmp_path, chromium, language, width):
    page = fixture_page(tmp_path, language)
    command, evaluate = chromium
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": page.as_uri()})
    browser_wait(evaluate, "window.qa?.browserReady===true||!!window.qa?.errors?.length")
    assert evaluate("qa.errors") == []
    badges = evaluate("Array.from(document.querySelectorAll('[data-account-summary]')).map(card=>({id:card.dataset.accountSummary,text:card.querySelector('.risk-badge')?.innerText,label:card.querySelector('.risk-badge')?.getAttribute('aria-label')}))")
    by_id = {row["id"]: row for row in badges}
    assert "108.0%" in by_id["qa-leveraged"]["text"]
    assert "~1.0%" in by_id["qa-mmf"]["text"]
    assert "100%" not in by_id["qa-debt"]["text"]
    assert ("Nonpositive equity" if language == "en" else "הון נטו שאינו חיובי") in by_id["qa-debt"]["text"]
    assert ("Incomplete" if language == "en" else "לא שלם") in by_id["qa-unknown"]["text"]
    assert "0–100" not in by_id["qa-unknown"]["text"]
    geometry = evaluate("(()=>({viewport:innerWidth,scroll:document.documentElement.scrollWidth,badges:Array.from(document.querySelectorAll('[data-account-summary] .risk-badge')).map(b=>{const r=b.getBoundingClientRect();return{text:b.innerText,client:b.clientWidth,scroll:b.scrollWidth,left:r.left,right:r.right};})}))()")
    assert geometry["viewport"] == width and geometry["scroll"] <= width
    for badge in geometry["badges"]:
        assert badge["scroll"] <= badge["client"] + 1, badge
        assert badge["left"] >= 0 and badge["right"] <= width, badge
    (tmp_path / "dashboard.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})["data"]))

    selector = '[data-account-summary="qa-leveraged"] .risk-badge'
    click(command, evaluate, selector)
    (tmp_path / "after-badge-click.json").write_text(json.dumps(evaluate("({hidden:$('riskBadgeExplanation').hidden,text:$('riskBadgeExplanation').innerText,active:document.activeElement.outerHTML,events:qa.events,clickProbes:qa.clickProbes,errors:qa.errors})"),ensure_ascii=False,indent=2))
    browser_wait(evaluate, "!$('riskBadgeExplanation').hidden")
    assert "108.0%" in evaluate("$('riskBadgeExplanation').innerText")
    popup = evaluate("(()=>{const p=$('riskBadgeExplanation'),r=p.getBoundingClientRect();return{left:r.left,right:r.right,top:r.top,bottom:r.bottom,text:p.innerText};})()")
    assert 0 <= popup["left"] <= popup["right"] <= width
    assert 0 <= popup["top"] < popup["bottom"] <= 1000
    trigger = evaluate("(()=>{const r=document.querySelector(" + json.dumps(selector) + ").getBoundingClientRect();return{left:r.left,right:r.right,top:r.top,bottom:r.bottom};})()")
    assert popup["right"] <= trigger["left"] or popup["left"] >= trigger["right"] or popup["bottom"] <= trigger["top"] or popup["top"] >= trigger["bottom"], (popup, trigger)
    if evaluate("$('riskBadgeExplanation').scrollHeight>$('riskBadgeExplanation').clientHeight"):
        press(command, "PageDown", "PageDown", 34)
        browser_wait(evaluate, "$('riskBadgeExplanation').scrollTop>0")
        press(command, "Home", "Home", 36)
        browser_wait(evaluate, "$('riskBadgeExplanation').scrollTop===0")
    press(command, "Escape", "Escape", 27)
    browser_wait(evaluate, "$('riskBadgeExplanation').hidden")
    assert evaluate("document.activeElement.matches('[data-account-summary=qa-leveraged] .risk-badge')")
    press(command, "Enter", "Enter", 13, "\r")
    browser_wait(evaluate, "!$('riskBadgeExplanation').hidden")
    press(command, "Escape", "Escape", 27)
    browser_wait(evaluate, "$('riskBadgeExplanation').hidden")
    assert evaluate("document.activeElement.matches('[data-account-summary=qa-leveraged] .risk-badge')")
    if width == 390:
        press(command, "Tab", "Tab", 9)
        assert not evaluate("document.activeElement.matches('[data-account-summary=qa-leveraged] .risk-badge')")
        press(command, "Escape", "Escape", 27)
        browser_wait(evaluate, "$('riskBadgeExplanation').hidden")
        command("Emulation.setTouchEmulationEnabled", {"enabled": True})
        tap(command, evaluate, selector)
        browser_wait(evaluate, "!$('riskBadgeExplanation').hidden")
        assert "108.0%" in evaluate("$('riskBadgeExplanation').innerText")
        tap(command, evaluate, selector)
        browser_wait(evaluate, "$('riskBadgeExplanation').hidden")
        command("Emulation.setTouchEmulationEnabled", {"enabled": False})

    unknown_summary = '[data-account-summary="qa-unknown"] .stress-risk-gaps > summary'
    click(command, evaluate, unknown_summary)
    browser_wait(evaluate, "document.querySelector('[data-account-summary=qa-unknown] .stress-risk-gaps').open")
    action = '[data-account-summary="qa-unknown"] [data-risk-inputs-security-key]'
    assert evaluate("document.querySelector(" + json.dumps(action) + ")!==null")
    click(command, evaluate, action)
    browser_wait(evaluate, "!$('stressRiskInputsModal').hidden")
    browser_wait(evaluate, "$('stressRiskInputsTitle')===document.activeElement")
    assert evaluate("$('stressRiskInputsSecurity').innerText") == "QAOPTION"
    click(command, evaluate, '#stressRiskInputsModal button[data-close]')
    browser_wait(evaluate, "$('stressRiskInputsModal').hidden")
    browser_wait(evaluate, "document.activeElement.matches('[data-risk-inputs-security-key]')")

    # Actual application modal navigation and asynchronous reload, not only the
    # chart helper. The fixture supplies read-only synthetic saved records.
    if width == 390:
        click(command, evaluate, '#navigationToggle')
        browser_wait(evaluate, "$('navigationToggle').getAttribute('aria-expanded')==='true'")
    click(command, evaluate, 'details:has([data-modal="riskHistoryModal"]) > summary')
    browser_wait(evaluate, "document.querySelector('[data-modal=riskHistoryModal]').closest('details').open")
    click(command, evaluate, '[data-modal="riskHistoryModal"]')
    browser_wait(evaluate, "!$('riskHistoryModal').hidden&&$('riskHistoryContent').querySelectorAll('svg').length===2")
    history = evaluate("$('riskHistoryContent').innerText")
    assert "108.0%" in history and "80/100" in history
    assert "13/11/2026" in history and "14/11/2026" in history
    assert evaluate("$('riskHistoryContent').querySelectorAll('svg circle').length") == 2
    assert evaluate("$('riskHistoryContent').querySelectorAll('.risk-history-model').length") == 2
    click(command, evaluate, '#riskHistoryReload')
    browser_wait(evaluate, "$('riskHistoryContent').querySelectorAll('svg circle').length===2")
    (tmp_path / "history.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})["data"]))
    click(command, evaluate, '#riskHistoryModal button[data-close]')
    browser_wait(evaluate, "$('riskHistoryModal').hidden")
    assert evaluate("qa.errors") == []
    assert evaluate("qa.illegalPosts") == []
    assert evaluate("JSON.stringify({holdings:qa.holdings,accounts:state.localAccounts,transactions:state.localTransactions})===qa.before")
    (tmp_path / "browser-metrics.json").write_text(json.dumps(dict(language=language, width=width, badges=badges, geometry=geometry, popup=popup, history=history), ensure_ascii=False, indent=2))
