"""Independent browser acceptance for bounded Missing risk inputs lists.

Uses the real dashboard assets with synthetic holdings and intercepted APIs.
No runtime portfolio data, private config, or deployed instance is accessed.
"""
import base64
import json

import pytest

from test_native_account_history_qa import ROOT, chromium
from test_account_cash_update_qa import browser_wait
from test_cash_fund_risk_independent_qa import browser_fixture, item, settle


def long_risk_document(tmp_path, language):
    fixture = browser_fixture(tmp_path, language)
    holdings = []
    for account in ("qa-ils", "qa-usd"):
        for number in range(8):
            symbol = f"QA-{account}-{number}-LONG-SECURITY-IDENTIFIER"
            row = item(symbol, 100, kind="corporate_bond", account=account)
            row["stress_risk"]["parameters"]["country_basis"] = "issuer_domicile_proxy"
            row["holding"].update(account_type="Investment", location="Israel",
                                  account=f"Synthetic {account}", cost_basis=100,
                                  unrealized_profit=0)
            holdings.append(row)
    app = tmp_path / "cash-app.js"
    app.write_text(app.read_text() + "\nqa.holdings=" + json.dumps(holdings) + r''';
state.items=state.allPortfolioItems=qa.holdings;
qa.render();qa.scrollFixtureReady=true;
''')
    return fixture


def key(command, name, code):
    for event in ("keyDown", "keyUp"):
        command("Input.dispatchKeyEvent", {"type": event, "key": name,
                                           "code": name, "windowsVirtualKeyCode": code})


def settle_scroll(evaluate):
    # Chromium animates native key and touch scrolling. Wait for stable layout
    # before issuing the next gesture or recording offsets for a redraw.
    evaluate(r'''new Promise(resolve=>{
      let last='',stable=0;const start=performance.now();
      const frame=()=>{const current=JSON.stringify(qa.lists().map(list=>list.scrollTop));
        stable=current===last?stable+1:0;last=current;
        if(stable>=8||performance.now()-start>3000)resolve();else requestAnimationFrame(frame);
      };requestAnimationFrame(frame);
    })''')


@pytest.mark.parametrize("language", ["en", "he"])
@pytest.mark.parametrize("width,height", [(1440, 900), (390, 760), (320, 568)])
def test_long_risk_lists_scroll_without_losing_controls_or_reading_context(
        tmp_path, chromium, language, width, height):
    command, evaluate = chromium
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": height,
            "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": long_risk_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.scrollFixtureReady===true||!!window.qa?.errors?.length")
    assert evaluate("qa.errors") == []
    evaluate(r'''qa.panels=()=>[document.querySelector('.portfolio-risk-summary .stress-risk-gaps'),
      ...document.querySelectorAll('[data-account-summary] .stress-risk-gaps')];
      qa.lists=()=>qa.panels().map(panel=>panel.querySelector('ul'));
      qa.panels().forEach(panel=>panel.open=true);''')
    settle(command)
    geometry = evaluate(r'''qa.lists().map(list=>{
      const panel=list.parentElement, r=list.getBoundingClientRect();
      return {count:list.children.length,h:list.clientHeight,content:list.scrollHeight,
        width:list.clientWidth,contentWidth:list.scrollWidth,viewport:innerHeight,
        keyboard:list.tabIndex,name:list.getAttribute('aria-label'),
        summaryOutside:!list.contains(panel.querySelector('summary')),
        explanationOutside:!list.contains(panel.querySelector('p')),
        actionsOutside:!list.contains(panel.querySelector('.risk-retrieval-actions')),
        actionsBelow:panel.querySelector('.risk-retrieval-actions').getBoundingClientRect().top>=r.bottom,
        pageOverflow:document.documentElement.scrollWidth-innerWidth};})''')
    assert len(geometry) == 3, geometry
    for result in geometry:
        assert result["count"] >= 30 and result["content"] > result["h"] > 100, result
        assert result["h"] < result["viewport"] * .6, result
        assert result["contentWidth"] <= result["width"] + 1, result
        assert result["pageOverflow"] <= 1, result
        assert result["keyboard"] == 0 and result["name"] == (
            "נתוני סיכון חסרים" if language == "he" else "Missing risk inputs"), result
        assert all(result[field] for field in (
            "summaryOutside", "explanationOutside", "actionsOutside", "actionsBelow")), result

    # Native Tab reaches the named scrolling list, and native keys scroll its contents.
    evaluate("qa.panels()[1].querySelector('summary').focus();document.activeElement.scrollIntoView({block:'center'})")
    key(command, "Tab", 9)
    assert evaluate("document.activeElement===qa.lists()[1]")
    key(command, "ArrowDown", 40)
    browser_wait(evaluate, "qa.lists()[1].scrollTop>0")
    settle_scroll(evaluate)
    evaluate("qa.arrowOffset=qa.lists()[1].scrollTop")
    key(command, "PageDown", 34)
    browser_wait(evaluate, "qa.lists()[1].scrollTop>qa.arrowOffset")
    settle_scroll(evaluate)
    assert evaluate("document.activeElement===qa.lists()[1]")
    key(command, "End", 35)
    browser_wait(evaluate, "Math.abs(qa.lists()[1].scrollTop-(qa.lists()[1].scrollHeight-qa.lists()[1].clientHeight))<2")
    settle_scroll(evaluate)
    evaluate("qa.endOffset=qa.lists()[1].scrollTop")
    key(command, "PageUp", 33)
    browser_wait(evaluate, "qa.lists()[1].scrollTop<qa.endOffset")
    settle_scroll(evaluate)
    key(command, "Home", 36)
    browser_wait(evaluate, "qa.lists()[1].scrollTop===0")
    settle_scroll(evaluate)

    # Every entry's review action can be focused and scrolled into view, including the last.
    reachable = evaluate(r'''qa.lists().map(list=>[...list.querySelectorAll('button')].every(button=>{
      button.focus();const r=button.getBoundingClientRect(),p=list.getBoundingClientRect();
      return r.top>=p.top-1&&r.bottom<=p.bottom+1&&r.left>=p.left-1&&r.right<=p.right+1;
    }))''')
    assert all(reachable), reachable

    # The native wheel scrolls the list; outer controls and explanation stay in place.
    evaluate("qa.lists()[1].scrollTop=0;qa.lists()[1].scrollIntoView({block:'center'});qa.wheelBefore=qa.panels()[1].querySelector('summary').getBoundingClientRect().top")
    point = evaluate("(()=>{const r=qa.lists()[1].getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()")
    command("Input.dispatchMouseEvent", {"type": "mouseWheel", **point, "deltaX": 0,
                                        "deltaY": 160})
    browser_wait(evaluate, "qa.lists()[1].scrollTop>0")
    settle_scroll(evaluate)
    assert evaluate("Math.abs(qa.panels()[1].querySelector('summary').getBoundingClientRect().top-qa.wheelBefore)<1")
    if width < 500:
        evaluate("qa.lists()[1].scrollTop=0")
        command("Emulation.setTouchEmulationEnabled", {"enabled": True})
        command("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{**point, "id": 0}]})
        for distance in (30, 90):
            command("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [
                {"x": point["x"], "y": point["y"]-distance, "id": 0}]})
        command("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        browser_wait(evaluate, "qa.lists()[1].scrollTop>0")
        settle_scroll(evaluate)
        command("Emulation.setTouchEmulationEnabled", {"enabled": False})

    # Background redraw keeps the three independent offsets and focused scrolling area.
    evaluate("qa.lists().forEach((list,index)=>list.scrollTop=120+index*170);qa.lists()[2].focus({preventScroll:true});qa.before={offsets:qa.lists().map(list=>list.scrollTop),y:scrollY}")
    for _ in range(3):
        evaluate("qa.render()")
        settle(command)
        assert evaluate("qa.panels().every(panel=>panel.open)")
        assert evaluate("qa.lists().map(list=>list.scrollTop)") == evaluate("qa.before.offsets")
        assert evaluate("document.activeElement===qa.lists()[2]")
        assert evaluate("Math.abs(scrollY-qa.before.y)<=1")

    # Later securities share their market: focus must retain the exact exposure
    # action and exact input-review row, even when one security has several gaps.
    for selector in ("[data-stress-risk-exposure]", "[data-risk-inputs-security-key]"):
        evaluate("qa.review=[...qa.lists()[1].querySelectorAll(" + json.dumps(selector) + ")].at(-1);qa.review.focus();"
                 "qa.focusBefore={text:qa.review.closest('li').textContent,offsets:qa.lists().map(list=>list.scrollTop)};")
        evaluate("qa.render()")
        settle(command)
        assert evaluate("document.activeElement.closest('li')?.textContent") == evaluate("qa.focusBefore.text"), selector
        assert evaluate("qa.lists().map(list=>list.scrollTop)") == evaluate("qa.focusBefore.offsets")

    # The total contains securities also listed in accounts. Its active review
    # control must stay in total rather than switching to a matching account row.
    evaluate(r'''qa.review=[...qa.lists()[0].querySelectorAll('[data-risk-inputs-security-key]')].at(-1);
      qa.review.focus();qa.totalFocus={text:qa.review.closest('li').textContent,
        offsets:qa.lists().map(list=>list.scrollTop)};qa.render();''')
    settle(command)
    assert evaluate("!!document.activeElement.closest('.portfolio-risk-summary')")
    assert evaluate("document.activeElement.closest('li')?.textContent") == evaluate("qa.totalFocus.text")
    assert evaluate("qa.lists().map(list=>list.scrollTop)") == evaluate("qa.totalFocus.offsets")
    evaluate("qa.panels()[0].open=false;qa.panels()[2].open=false;qa.panels()[1].querySelector('summary').focus();qa.render()")
    settle(command)
    assert evaluate("qa.panels().map(panel=>panel.open)") == [False, True, False]

    # A single missing input stays at content height, without an empty fixed panel.
    evaluate(r'''qa.short=document.createElement('div');
      qa.short.innerHTML=stressRiskGapsHtml({gaps:[{code:'cash'}]});
      $('analyticsBoard').append(qa.short);qa.short.querySelector('details').open=true;''')
    short = evaluate("(()=>{const list=qa.short.querySelector('ul');return{h:list.clientHeight,content:list.scrollHeight}})()")
    assert short["h"] == short["content"] and short["h"] < geometry[0]["h"] / 2, short
    assert evaluate("qa.errors") == []
    assert evaluate("qa.writeCount") == 0

    evidence = ROOT / ".runtime/risk-gap-scroll/qa"
    evidence.mkdir(parents=True, exist_ok=True)
    evaluate("qa.short.remove();qa.lists()[1].scrollTop=0;qa.lists()[1].focus();qa.panels()[1].scrollIntoView({block:'center'})")
    settle(command)
    (evidence / f"list-{language}-{width}.png").write_bytes(base64.b64decode(
        command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
