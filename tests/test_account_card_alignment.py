"""Account-card layout using actual rendering/CSS and synthetic cash-only accounts."""
import base64

import pytest

from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium


@pytest.mark.parametrize("width,language", [(1440, "en"), (1440, "he"), (390, "en"), (390, "he")])
def test_account_rows_align_with_optional_currency_and_bottom_gap_disclosure(tmp_path, chromium, width, language):
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": cash_browser_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    assert evaluate("$('dashboardHome').textContent.trim()") == ""
    assert evaluate("$('dashboardHome').children.length") == 1
    assert evaluate("$('dashboardHome').getAttribute('aria-label')") == (
        "Return to dashboard" if language == "en" else "חזרה לתיק ההשקעות")
    assert evaluate("$('dashboardHome').getBoundingClientRect().width") >= 44
    evaluate("$('dashboardHome').focus();")
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
    browser_wait(evaluate, "document.activeElement.id==='dashboardTitle'")
    assert evaluate("$('dashboardTitle').classList.contains('sr-only')")
    evaluate("$('status').textContent=t('Financial data could not be updated. Use Refresh to retry.');")
    browser_wait(evaluate, "!$('status').classList.contains('sr-only')")
    evaluate("$('status').textContent='9 '+t('portfolio positions')+' · '+t('Analytics updated');")
    browser_wait(evaluate, "$('status').classList.contains('sr-only')")
    evaluate("$('status').textContent='9 '+t('portfolio positions')+' · '+t('Financial data could not be updated. Use Refresh to retry.');")
    browser_wait(evaluate, "!$('dashboardNotice').hidden&&$('status').classList.contains('sr-only')")
    evaluate("$('status').textContent='9 '+t('portfolio positions')+' · '+t('Analytics updated');")
    browser_wait(evaluate, "$('dashboardNotice').hidden")
    evaluate('''
state.baseCurrency='ILS';state.fxRates={'USD/ILS':4};state.localTransactions=[];
state.localAccounts=[
 {id:'native',username:'Synthetic investment account with a longer name',type:'Investment',currency:'USD',initial_cash:10000,persons:[]},
 {id:'base',username:'Synthetic base account',type:'Investment',currency:'ILS',initial_cash:5000,persons:[]}
];
qa.originalSnapshot=portfolioRiskSnapshot;
portfolioRiskSnapshot=items=>{const snapshot=qa.originalSnapshot(items);snapshot.accounts[0].risk.components.data_quality=2;return snapshot;};
$('analyticsBoard').innerHTML=withDashboardToolbar({id:'portfolio_value'},renderPortfolioValueDashboard([]));
window.PortfolioI18n.applyToDocument(state.language);
qa.cards=()=>[...document.querySelectorAll('.account-summary-card')];
qa.geometry=()=>qa.cards().map(card=>{
 const y=selector=>card.querySelector(selector).getBoundingClientRect().top;
 const box=card.getBoundingClientRect();return {left:box.left,right:box.right,
   name:y('.account-summary-name'),label:y('.account-summary-balance>span'),value:y('.account-summary-balance>strong'),
   native:y('.account-summary-local'),cash:y('.account-current-cash'),metrics:y('.account-summary-metrics'),
   allocation:y('.account-summary-allocation'),footer:y('.account-summary-footer')};
});
''')
    geometry = evaluate("qa.geometry()")
    assert len(geometry) == 2
    assert all(card["left"] >= 0 and card["right"] <= width for card in geometry), geometry
    assert evaluate("qa.cards().every(card=>card.lastElementChild.classList.contains('account-summary-footer'))")
    assert evaluate("qa.cards()[0].querySelector('.risk-data-quality').closest('.account-summary-footer')!==null")
    assert evaluate("qa.cards()[1].querySelector('.account-summary-local').getAttribute('aria-hidden')") == "true"
    assert evaluate("Number(getComputedStyle(qa.cards()[0].querySelector('.account-summary-balance>span')).fontWeight)") >= 800
    if width == 1440:
        for row in ["name", "label", "value", "native", "cash", "metrics", "allocation", "footer"]:
            assert abs(geometry[0][row] - geometry[1][row]) <= 1, (row, geometry)
    else:
        assert geometry[1]["name"] > geometry[0]["footer"]
    evaluate("qa.cards()[0].querySelector('.risk-data-quality').open=true;")
    expanded = evaluate("qa.geometry()")
    for index in range(2 if width == 1440 else 1):
        for row in ["label", "value", "native", "cash", "metrics", "allocation", "footer"]:
            assert abs(expanded[index][row] - geometry[index][row]) <= 1, (row, geometry, expanded)
    evaluate("qa.cards()[0].scrollIntoView({block:'center'});")
    (tmp_path / f"account-cards-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("width,language", [(1440, "en"), (1440, "he"), (390, "en"), (390, "he")])
def test_market_cost_chart_keeps_rotated_labels_inside_a_compact_card(tmp_path, chromium, width, language):
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": cash_browser_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate('''
qa.chartItems=['5139324','CMRE','CRI','91282CKD2','LONG.SYMBOL.12345'].map((symbol,index)=>({holding:{symbol,currency:'USD',market_value:10000-index*1000,cost_basis:8000-index*500}}));
$('analyticsBoard').innerHTML=withDashboardToolbar({id:'market_cost'},renderMarketCostBars(qa.chartItems));
window.PortfolioI18n.applyToDocument(state.language);
''')
    geometry = evaluate('''(()=>{const card=document.querySelector('.comparison-card'),svg=card.querySelector('svg'),c=card.getBoundingClientRect(),s=svg.getBoundingClientRect(),labels=[...svg.querySelectorAll('text')].map(e=>e.getBoundingClientRect());return {cardHeight:c.height,svgHeight:s.height,gap:c.bottom-Math.max(...labels.map(e=>e.bottom)),inside:labels.every(r=>r.top>=s.top&&r.bottom<=s.bottom+1&&r.left>=s.left&&r.right<=s.right),left:c.left,right:c.right};})()''')
    assert geometry["inside"], geometry
    assert geometry["gap"] <= 36, geometry
    assert geometry["svgHeight"] <= 240, geometry
    assert geometry["left"] >= 0 and geometry["right"] <= width, geometry
    (tmp_path / f"market-cost-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    assert evaluate("qa.errors") == []
