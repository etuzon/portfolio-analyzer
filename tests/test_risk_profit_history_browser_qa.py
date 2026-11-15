"""Independent real-renderer checks with disposable synthetic-only Chromium.

These tests exercise the actual HTML, complete CSS and delegated controls. They
do not attach to the user's browser or read a runtime portfolio/source database.
"""
import base64
import json

import pytest

from test_account_cash_update_qa import browser_wait
from test_native_account_history_qa import chromium
from test_risk_scale_v4_browser_qa import fixture_page, press, click


def prospective_history():
    """Observable UI fixtures derived from the independent raw money oracle."""
    rows = []
    definitions = [
        ("baseline", "2026-11-14", 36, 36.42, "baseline", None, None, "baseline", "baseline", []),
        ("earned", "2026-11-15", 47, 46.96, "recorded", 70, 80, "baseline", "baseline", []),
        ("gap", "2026-11-16", 0, 0.49, "unavailable", None, None, "baseline", "gap", ["ledger_revised"]),
        ("new-baseline", "2026-11-17", 100, 100.001, "baseline", None, None, "new-baseline", "new-baseline", []),
        ("loss", "2026-11-18", 100, 220, "recorded", -25, -15, "new-baseline", "new-baseline", []),
    ]
    for identifier, day, score, raw, status, total_profit, account_profit, baseline, segment, reasons in definitions:
        risk = dict(model="portfolio-risk-v4", score=score, loss_pct=raw, stress_loss=raw * 10,
                    net_equity=1000, status="ok", score_unit="percent_capital_loss",
                    score_scale="stress-loss-percent-v1", scenario_horizon="instantaneous_revaluation",
                    coverage={"complete": True}, components={}, scenarios=[], gaps=[])
        baseline_day = "2026-11-17" if baseline == "new-baseline" else "2026-11-14"
        comparison = dict(status=status, currency="USD", baseline_observation_id=baseline,
                          baseline_date=baseline_day, baseline_observed_at=baseline_day + "T09:00:00Z",
                          segment_id=segment, reason_codes=reasons, beginning_equity=3000,
                          ending_equity=2970 if identifier == "earned" else 2975,
                          recorded_net_flows=-100 if identifier == "earned" else 0,
                          coverage="recorded_activity_only")
        rows.append(dict(id=identifier, date=day, observed_at=day + "T12:00:00Z",
                         base_currency="USD", model="portfolio-risk-v4", total=risk,
                         accounts=[dict(account_id="a", account_label="Synthetic A", risk=risk)],
                         performance=dict(version="observed-equity-recorded-flows-v1",
                                          coverage="recorded_activity_only",
                                          total={**comparison, "profit": total_profit},
                                          accounts=[dict(account_id="a", **comparison, profit=account_profit)])))
    return dict(model="portfolio-risk-v4", models=["portfolio-risk-v4"], base_currency="USD",
                reset_at="2026-11-14T08:00:00Z", accounts=[dict(id="a", label="Synthetic A")],
                items=rows, truncated=False, invalid_records=0)


@pytest.mark.parametrize("language", ["en", "he"])
@pytest.mark.parametrize("width", [1440, 1280, 1024, 390])
def test_changed_risk_headers_sort_and_cells_keep_visible_values(tmp_path, chromium, language, width):
    page = fixture_page(tmp_path, language)
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000,
                                                   "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": page.as_uri()})
    browser_wait(evaluate, "window.qa?.browserReady===true||!!window.qa?.errors?.length")
    assert evaluate("qa.errors") == []
    evaluate("""
qa.holdings.forEach(item=>{item.price_ranges={};item.moving_averages={};item.support_resistance={};item.missing=[];});
renderRows(qa.holdings);PortfolioI18n.applyToDocument(state.language);
""")
    evaluate("document.fonts.ready.then(()=>true)")
    metrics = evaluate("""(()=>{
const nodes=Array.from(document.querySelectorAll('[data-holdings-sort-column=risk], [data-holdings-sort=risk], .holding-risk-cell, .holding-risk-cell .risk-badge'));
return{width:innerWidth,scroll:document.documentElement.scrollWidth,
 fontStatus:document.fonts.status,
 nodes:nodes.map(e=>{const r=e.getBoundingClientRect(),c=getComputedStyle(e);return{tag:e.tagName,text:e.innerText,client:e.clientWidth,scroll:e.scrollWidth,width:r.width,display:c.display,overflow:c.overflow,textOverflow:c.textOverflow};}),
 scores:Array.from(document.querySelectorAll('.risk-badge.risk-stress b bdi')).map(e=>e.textContent),
 mobile:{label:$('holdingsMobileSort').options.namedItem?.('risk')?.text || Array.from($('holdingsMobileSort').options).find(o=>o.value==='risk')?.text,
 display:getComputedStyle($('holdingsMobileSort')).display,client:$('holdingsMobileSort').clientWidth,scroll:$('holdingsMobileSort').scrollWidth}};
})()""")
    assert metrics["width"] == width
    assert metrics["scroll"] <= width, metrics
    assert metrics["fontStatus"] == "loaded"
    for node in metrics["nodes"]:
        if node["width"] > 0:
            assert node["scroll"] <= node["client"] + 1, node
            assert node["textOverflow"] != "ellipsis", node
    assert metrics["scores"] and all(score.isdecimal() for score in metrics["scores"])
    if width == 390:
        assert metrics["mobile"]["client"] > 0
        assert metrics["mobile"]["scroll"] <= metrics["mobile"]["client"] + 1
    # Keyboard activation goes through the production sort change/click handler.
    if width == 390:
        evaluate("$('holdingsMobileSort').scrollIntoView({block:'center'});$('holdingsMobileSort').focus()")
        press(command, "Home", "Home", 36)
        for _ in range(3):
            press(command, "ArrowDown", "ArrowDown", 40)
    else:
        evaluate("document.querySelector('[data-holdings-sort=risk]').scrollIntoView({block:'center'});document.querySelector('[data-holdings-sort=risk]').focus()")
        press(command, "Enter", "Enter", 13, "\r")
    browser_wait(evaluate, "holdingsTableSort.key==='risk'")
    assert evaluate("qa.errors") == []
    (tmp_path / "risk-columns.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    (tmp_path / "risk-columns.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": True})["data"]))


@pytest.mark.parametrize("language", ["en", "he"])
@pytest.mark.parametrize("width", [1440, 1280, 1024, 390])
def test_prospective_history_risk_money_gaps_selection_and_retry_in_real_page(tmp_path, chromium, language, width):
    page = fixture_page(tmp_path, language)
    command, evaluate = chromium
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000,
                                                   "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": page.as_uri()})
    browser_wait(evaluate, "window.qa?.browserReady===true||!!window.qa?.errors?.length")
    assert evaluate("qa.errors") == []
    evaluate("qa.history=" + json.dumps(prospective_history()) + ";state.baseCurrency='USD';")
    evaluate("""
qa.historyMode='ok';const previousAPI=api;
api=async(path,options={})=>{
 if(path.startsWith('/api/portfolio/risk-history') && !options.method){
  qa.calls.push(path);
  if(qa.historyMode==='hold')return await new Promise(resolve=>qa.resolveHistory=()=>resolve(qa.history));
  if(qa.historyMode==='fail')throw Error('Synthetic read interruption');
  return qa.history;
 }
 return previousAPI(path,options);
};
""")
    if width == 390:
        click(command, evaluate, "#navigationToggle")
        browser_wait(evaluate, "$('navigationToggle').getAttribute('aria-expanded')==='true'")
    click(command, evaluate, 'details:has([data-modal="riskHistoryModal"]) > summary')
    browser_wait(evaluate, "document.querySelector('[data-modal=riskHistoryModal]').closest('details').open")
    click(command, evaluate, '[data-modal="riskHistoryModal"]')
    browser_wait(evaluate, "!$('riskHistoryModal').hidden&&$('riskHistoryContent').querySelectorAll('svg').length===2")
    evaluate("document.fonts.ready.then(()=>true)")
    text = evaluate("$('riskHistoryContent').innerText")
    assert "220.00%" in text and "0.49%" in text
    assert evaluate("$('riskHistoryContent').querySelector('[data-risk-history-row=gap] .risk-badge b bdi').textContent") == "0"
    assert evaluate("$('riskHistoryContent').querySelector('[data-risk-history-row=gap] .risk-badge').innerText") == "0"
    assert evaluate("$('riskHistoryContent').querySelector('[data-risk-history-row=gap] .risk-history-number').textContent") == "0.49%"
    assert evaluate("$('riskHistoryContent').querySelector('[data-risk-history-row=loss] .risk-badge b bdi').textContent") == "100"
    assert evaluate("$('riskHistoryContent').querySelector('[data-risk-history-row=loss] .risk-badge').innerText") == "100"
    assert evaluate("$('riskHistoryContent').querySelector('[data-risk-history-row=loss] .risk-history-number').textContent") == "220.00%"
    near_cap = evaluate("$('riskHistoryContent').querySelector('[data-risk-history-row=new-baseline] .risk-history-number').textContent")
    assert near_cap.startswith(">") or float(near_cap.removesuffix("%")) > 100, near_cap
    assert "+70.00 USD" in text and "-25.00 USD" in text
    assert "14/11/2026" in text and "18/11/2026" in text
    assert ("Waiting for a later observation" if language == "en" else "למדידה מאוחרת יותר") in text
    if language == "he":
        for operational in ["Waiting for", "Baseline", "Scenario loss", "Recorded net cash flows", "Reload"]:
            assert operational not in text
    assert evaluate("$('riskHistoryContent').querySelectorAll('.risk-history-profit circle').length") == 2
    profit_path = evaluate("$('riskHistoryContent').querySelector('.risk-history-profit path').getAttribute('d')")
    assert profit_path.count("M") == 2 and "L" not in profit_path
    assert evaluate("Array.from($('riskHistoryContent').querySelectorAll('svg')).map(e=>e.getAttribute('aria-label'))")[1].endswith("(USD)")
    # Both chart groups select the same observation through actual key events.
    evaluate("$('riskHistoryScorePoint-loss').scrollIntoView({block:'center'});$('riskHistoryScorePoint-loss').focus()")
    press(command, "Home", "Home", 36)
    assert evaluate("riskHistoryView.selectedObservation") == "baseline"
    assert evaluate("$('riskHistoryReadout').innerText").find("+70.00") == -1
    press(command, "ArrowRight", "ArrowRight", 39)
    assert evaluate("riskHistoryView.selectedObservation") == "earned"
    assert "+70.00 USD" in evaluate("$('riskHistoryReadout').innerText")
    assert evaluate("$('riskHistoryProfitPoint-earned').getAttribute('aria-pressed')") == "true"
    # The actual selector handler switches from pooled to per-account P&L.
    evaluate("$('riskHistoryAccount').scrollIntoView({block:'center'});$('riskHistoryAccount').focus()")
    press(command, "Home", "Home", 36)
    press(command, "ArrowDown", "ArrowDown", 40)
    browser_wait(evaluate, "riskHistoryView.account==='a'")
    assert "+80.00 USD" in evaluate("$('riskHistoryContent').querySelector('[data-risk-history-row=earned]').innerText")
    assert evaluate("document.activeElement.id") == "riskHistoryAccount"
    # Pending and failed reloads keep the saved view interactive and focusable.
    evaluate("qa.historyMode='hold'")
    click(command, evaluate, "#riskHistoryReload")
    browser_wait(evaluate, "riskHistoryView.loading===true&&typeof qa.resolveHistory==='function'")
    assert evaluate("$('riskHistoryContent').querySelectorAll('svg').length") == 2
    assert evaluate("document.activeElement.id") == "riskHistoryReload"
    assert evaluate("$('riskHistoryReload').disabled") is False
    evaluate("qa.historyMode='ok';qa.resolveHistory()")
    browser_wait(evaluate, "riskHistoryView.loading===false")
    evaluate("qa.historyMode='fail'")
    click(command, evaluate, "#riskHistoryReload")
    browser_wait(evaluate, "riskHistoryView.loading===false&&Boolean(riskHistoryView.error)")
    assert ("Could not load" if language == "en" else "לא ניתן לטעון") in evaluate("$('riskHistoryContent').innerText")
    assert evaluate("$('riskHistoryContent').querySelectorAll('svg').length") == 2
    evaluate("qa.historyMode='ok'")
    click(command, evaluate, "#riskHistoryReload")
    browser_wait(evaluate, "riskHistoryView.loading===false&&!riskHistoryView.error")
    geometry = evaluate("""(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,
 charts:Array.from($('riskHistoryContent').querySelectorAll('svg')).map(e=>{const r=e.getBoundingClientRect();return{left:r.left,right:r.right,width:r.width,texts:Array.from(e.querySelectorAll('text')).map(n=>{const t=n.getBoundingClientRect();return{text:n.textContent,left:t.left,right:t.right};})};}),
 cells:Array.from($('riskHistoryContent').querySelectorAll('th,.risk-history-number,.risk-history-date-button,.risk-badge')).map(e=>({text:e.innerText,client:e.clientWidth,scroll:e.scrollWidth})),
 region:$('riskHistoryContent').querySelector('.table-wrap').getAttribute('role')}))()""")
    assert geometry["width"] == width and geometry["scroll"] <= width
    assert geometry["region"] == "region"
    for chart in geometry["charts"]:
        assert 0 <= chart["left"] < chart["right"] <= width
        for label in chart["texts"]:
            assert chart["left"] - 1 <= label["left"] <= label["right"] <= chart["right"] + 1, label
    for cell in geometry["cells"]:
        assert cell["scroll"] <= cell["client"] + 1, cell
    assert evaluate("qa.errors") == []
    assert evaluate("qa.illegalPosts") == []
    (tmp_path / "history-behavior.json").write_text(json.dumps(dict(language=language, width=width,
        text=text, profit_path=profit_path, geometry=geometry), indent=2, ensure_ascii=False))
    (tmp_path / "history-behavior.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": True})["data"]))
