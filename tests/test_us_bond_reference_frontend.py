"""Provider-native bond references stay separate from recorded valuation evidence."""
import base64

import pytest

from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium


def ready(tmp_path, chromium, language="en", width=1440):
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": cash_browser_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate(r'''
qa.referenceCalls=[];qa.referencePosts=0;qa.referenceMode='ok';
qa.apiRows=[
 {price_date:'2026-10-27',price:99.34375,currency:'USD',quote_unit:'percent_of_par',price_basis:'valuation',side:'valuation'},
 {price_date:'2026-10-28',price:99.58,currency:'USD',quote_unit:'percent_of_par',price_basis:'programme_purchase',side:'programme_purchase_mean'},
 {price_date:'2026-10-29',price:98.9,currency:'USD',quote_unit:'percent_of_par',price_basis:'programme_redemption',side:'programme_redemption_bid'}
];
qa.snapshot={request:{identifier:'91282CKD2',kind:'bond',date_from:'2026-04-14',date_to:'2026-11-01'},
 security:{kind:'bond',cusip:'91282CKD2',isin:'US91282CKD29',name:'Synthetic Treasury <img src=x onerror=alert(1)>',currency:'USD'},
 provider:'treasury_direct',source_url:'https://www.treasurydirect.gov/TA_WS/securities/search',status:'partial',cache_status:'fetched',quote_status:'missing',
 items:qa.apiRows,quote:null,latest_in_range:qa.apiRows.at(-1),details:{coupon_rate_pct:4.25,maturity_date:'2029-02-28'},
 coverage:{complete:false,first_observation:'2026-10-27',last_observation:'2026-10-29',count:3,next_date:'2026-10-26'},portfolio_updated:false};
qa.localPoints=[{date:'2026-10-28',price:2.25},{date:'2026-10-29',price:2.35}];
qa.localPrices=[{id:'synthetic-local',symbol:'UST2029',stock_market:'MANUAL',asset_class:'BOND',currency:'ILS',location:'USA',price_date:'2026-10-29',price:2.35,price_input:235}];
qa.holding={symbol:'UST2029',secondary_symbol:'91282CKD2',stock_market:'MANUAL',data_source:'MANUAL',asset_class:'FIXED_INCOME',asset_sub_class:'BOND',currency:'ILS',location:'USA',quantity:200,market_value:470,cost_basis:450,unrealized_profit:20,name:'Registered local alias',account:'Synthetic investment'};
qa.item={holding:qa.holding,market_data:qa.snapshot,missing:[],price_ranges:{}};
state.allPortfolioItems=[qa.item];state.localTransactions=[];
api=async(path,options={})=>{
 qa.referenceCalls.push(path);
 if(options.method==='POST'){qa.referencePosts++;throw new Error('No writes allowed');}
 if(path.startsWith('/api/security/market-data')){
  if(qa.referenceMode==='hold')return await new Promise(resolve=>qa.resolveReference=resolve);
  if(qa.referenceMode==='error')throw new Error('private-provider-error-must-not-leak');
  return qa.reply||qa.snapshot;
 }
 if(path.startsWith('/api/security/history'))return {state:qa.historyError?'error':'ok',points:qa.historyError?[]:qa.localPoints,market_data:qa.snapshot};
 if(path==='/api/local/prices')return {items:qa.localPrices};
 return {items:[]};
};
qa.open=()=>openSecurityDetail({securityDetailSymbol:'UST2029',securityDetailMarketKey:'MANUAL',securityDetailStockMarket:'MANUAL',securityDetailProvider:'TreasuryDirect',securityDetailAsset:'FIXED_INCOME',securityDetailCurrency:'ILS',securityDetailLocation:'USA'});
''')
    return command, evaluate


@pytest.mark.parametrize("width,language", [(1440, "en"), (1440, "he"), (390, "en"), (390, "he")])
def test_secondary_bond_reference_native_units_history_and_read_only_refresh(tmp_path, chromium, width, language):
    command, evaluate = ready(tmp_path, chromium, language, width)
    evaluate("qa.open();")
    browser_wait(evaluate, "state.securityDetailLoad?.history==='ready'")
    assert evaluate("$('securityMarketReference').hidden") is False
    assert evaluate("bondReferenceIdentifier(state.securityDetail)") == "91282CKD2"
    assert evaluate("dataProviderDisplay(qa.item,qa.holding,'MANUAL')") == "TreasuryDirect"
    content = evaluate("$('securityMarketReference').textContent")
    assert "98.9" in content and "99.34375" in content
    assert "27/10/2026" in content and "29/10/2026" in content and "28/02/2029" in content
    assert ("USD per 100 USD face value" if language == "en" else "USD לכל 100 USD ערך נקוב") in content
    assert ("4.25% annually" if language == "en" else "4.25% לשנה") in content
    for label in (["Programme purchase price", "Programme redemption bid", "Manual registration", "History contains different quote conventions"] if language == "en"
                  else ["מחיר קנייה בתוכנית האוצר", "הצעת פדיון בתוכנית האוצר", "רישום ידני", "ההיסטוריה כוללת מוסכמות מחיר שונות"]):
        assert label in content
    assert "percent_of_par" not in content and "programme_purchase_mean" not in content
    assert evaluate("$('securityMarketReference').querySelectorAll('img').length") == 0
    assert evaluate("$('securityMarketReference').querySelector('a').href").startswith("https://www.treasurydirect.gov/")
    before = evaluate("JSON.stringify({holding:qa.holding,history:state.securityHistory,prices:state.localPrices})")
    # A source lookup uses the canonical secondary identifier and never writes prices.
    evaluate("$('securityMarketReference').querySelector('[data-bond-reference]').click();")
    browser_wait(evaluate, "!state.securityDetail.referenceLoading")
    assert "identifier=91282CKD2" in evaluate("qa.referenceCalls.at(-1)")
    assert evaluate("JSON.stringify({holding:qa.holding,history:state.securityHistory,prices:state.localPrices})") == before
    assert evaluate("$('detailPriceInput').value") == ""
    assert evaluate("qa.referencePosts") == 0
    evaluate("$('securityMarketReference').querySelector('details').open=true;$('securityMarketReference').scrollIntoView({block:'start'});")
    geometry = evaluate("(()=>{const p=$('securityMarketReference').getBoundingClientRect(),r=$('securityMarketReference').querySelector('.bond-reference-table-wrap');return {left:p.left,right:p.right,overflow:document.documentElement.scrollWidth-innerWidth,tableScroll:r.scrollWidth>r.clientWidth};})()")
    assert geometry["left"] >= 0 and geometry["right"] <= width and geometry["overflow"] <= 1, geometry
    if width == 390:
        assert geometry["tableScroll"] is True
    (tmp_path / f"bond-reference-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    # Earlier pages replace the raw reference table; existing valuation evidence remains intact.
    evaluate("$('securityMarketReference').querySelector('[data-bond-reference-earlier]').click();")
    browser_wait(evaluate, "!state.securityDetail.referenceLoading")
    assert "date_to=2026-10-26" in evaluate("qa.referenceCalls.at(-1)")
    assert evaluate("JSON.stringify({holding:qa.holding,history:state.securityHistory,prices:state.localPrices})") == before
    # Viewer users can read and refresh the same API reference in focused Prices.
    evaluate("state.auth.user.role='Viewer';renderCurrentUser();openPriceHistoryForSecurity({priceHistorySymbol:'UST2029',priceHistoryMarket:'MANUAL',priceHistoryAsset:'FIXED_INCOME',priceHistoryCurrency:'ILS',priceHistoryLocation:'USA'});")
    browser_wait(evaluate, "state.priceFocus?.referenceLoading===false")
    assert evaluate("$('priceMarketReference').hidden") is False
    assert evaluate("$('priceMarketReference').querySelector('[data-bond-reference]').disabled") is False
    assert evaluate("$('priceInput').value") == ""
    assert evaluate("qa.referencePosts") == 0 and evaluate("qa.errors") == []


def test_api_reference_survives_missing_chart_and_failed_refresh_without_guessing_units(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("qa.historyError=true;qa.open();")
    browser_wait(evaluate, "state.securityDetailLoad?.history==='error'")
    assert "99.34375" in evaluate("$('securityMarketReference').textContent")
    assert evaluate("state.securityHistory.length") == 0
    evaluate("qa.reply={status:'provider_error',security:null,items:[],coverage:{complete:false}};$('securityMarketReference').querySelector('[data-bond-reference]').click();")
    browser_wait(evaluate, "!state.securityDetail.referenceLoading")
    assert "99.34375" in evaluate("$('securityMarketReference').textContent")
    assert "stale" in evaluate("$('securityMarketReference').textContent")
    assert "private-provider" not in evaluate("$('securityMarketReference').textContent")
    assert evaluate("bondReferenceUnit({currency:'USD',quote_unit:'unknown'})") == "Unit not specified by source"
    assert evaluate("bondReferenceUnit({quote_unit:'percent_of_par'})") == "Percent of par; face-value currency not specified"
    assert evaluate("bondReferenceURL('javascript:alert(1)')") == ""
    # A US ISIN does not inherit the holding's currency or need a US market label.
    assert evaluate("bondReferenceIdentifier({symbol:'US91282CKD29',asset_sub_class:'BOND',currency:'EUR',stock_market:'MANUAL',location:'Israel'})") == "US91282CKD29"
    assert evaluate("isBondReferenceTarget({symbol:'5139324',asset_class:'MUTUALFUND',currency:'ILS'})") is False
    assert evaluate("qa.errors") == []


def test_slow_reference_result_cannot_update_another_security_or_session(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("qa.open();")
    browser_wait(evaluate, "state.securityDetailLoad?.history==='ready'")
    evaluate("qa.referenceMode='hold';loadBondReference('detail');void 0;")
    browser_wait(evaluate, "typeof qa.resolveReference==='function'")
    evaluate("state.securityDetail={symbol:'OTHER',asset_class:'EQUITY',currency:'USD'};qa.resolveReference(qa.snapshot);")
    browser_wait(evaluate, "state.securityDetail.symbol==='OTHER'")
    assert evaluate("state.securityDetail.market_data||null") is None
    assert evaluate("qa.referencePosts") == 0 and evaluate("qa.errors") == []


@pytest.mark.parametrize("language", ["en", "he"])
def test_matured_bond_keeps_historical_observations_without_current_quote(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    evaluate("qa.snapshot.quote_status='matured';qa.snapshot.quote=null;qa.snapshot.details.maturity_date='2026-10-30';qa.open();")
    browser_wait(evaluate, "state.securityDetailLoad?.history==='ready'")
    content = evaluate("$('securityMarketReference').textContent")
    assert ("This bond has matured. API observations are historical, not a current price." if language == "en" else
            "אג״ח זו הגיעה לפדיון. תצפיות ה־API הן היסטוריות ואינן מחיר נוכחי.") in content
    assert evaluate("$('securityMarketReference').querySelectorAll('tbody tr').length") == 3
    assert "99.34375" in content and "27/10/2026" in content
    assert evaluate("qa.referencePosts") == 0
    assert evaluate("qa.holding.market_value") == 470
    assert evaluate("qa.errors") == []
