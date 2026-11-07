"""Historical-price dialog behavior with synthetic REST responses and actual UI."""
import base64

import pytest

from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium


def ready(tmp_path, chromium, width=1440, language="en"):
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": cash_browser_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate(r'''
qa.pricePosts=[];qa.priceMode='ok';qa.priceReads=0;
qa.instrument={id:'synthetic-instrument',symbol:'ILTEST',stock_market:'TASE',asset_class:'EQUITY',instrument_type:'STOCK',location:'Israel',currency:'ILS',name:'Synthetic instrument'};
qa.priceRows=[{id:'manual',symbol:'ILTEST',stock_market:'TASE',asset_class:'EQUITY',currency:'ILS',location:'Israel',price_input:100,price:1,price_date:'2026-11-03',source:'manual',comments:'My <em>literal</em> comment'},
 {id:'api',symbol:'91282CKD2',stock_market:'MANUAL',asset_class:'BOND',location:'USA',currency:'USD',price_input:99.34,price:.9934,price_date:'2026-11-03',source:'api_evidence',comments:JSON.stringify({kind:'price_evidence_v1',provider:'treasury_direct',price_basis:'programme_redemption',side:'programme_redemption_bid',quote_unit:'percent_of_par',source_url:'https://www.treasurydirect.gov/',normalization:'raw_price / 100'})}];
api=async(path,options={})=>{
 if(path==='/api/local/manual-securities')return {items:[qa.instrument]};
 if(path==='/api/local/prices'&&options.method==='POST'){
  const payload=JSON.parse(options.body);qa.pricePosts.push(payload);
  if(qa.priceMode==='error')throw new Error('private raw server error');
  const save=()=>{const row={...payload,id:'saved-price',price_input:Number(payload.price_input),price:Number(payload.price_input)/100,source:'manual'};qa.priceRows.push(row);return row;};
  if(qa.priceMode==='hold')return await new Promise(resolve=>qa.resolvePrice=()=>resolve(save()));
  const result=save();if(qa.priceMode==='reload-error')qa.failPriceReload=true;return result;
 }
 if(path==='/api/local/prices'){qa.priceReads++;if(qa.failPriceReload){qa.failPriceReload=false;throw new Error('synthetic reload error');}return {items:qa.priceRows};}
 return {items:[]};
};
refreshLocalizedFormOptions();openModal('pricesModal');
''')
    browser_wait(evaluate, "qa.priceReads>0&&$('pricesList').children.length===2")
    return command, evaluate


@pytest.mark.parametrize("width,language", [(1440, "en"), (1440, "he"), (390, "en"), (390, "he")])
def test_price_history_opens_cleanly_and_child_entry_preserves_draft_and_saves_once(tmp_path, chromium, width, language):
    command, evaluate = ready(tmp_path, chromium, width, language)
    assert evaluate("$('priceEntryModal').hidden") is True
    assert evaluate("$('priceInput').closest('.modal').id") == "priceEntryModal"
    assert evaluate("$('pricesModal').querySelector('.price-entry-form')===null")
    source = evaluate("$('pricesList').textContent")
    assert "price_evidence_v1" not in source and "raw_price / 100" not in source
    assert "TreasuryDirect" in source
    assert ("Programme redemption price" if language == "en" else "מחיר פדיון בתוכנית האוצר") in source
    assert "My <em>literal</em> comment" in source and evaluate("$('pricesList').querySelectorAll('em').length") == 0
    evaluate("openPriceHistoryForSecurity({priceHistorySymbol:'ILTEST',priceHistoryMarket:'TASE',priceHistoryAsset:'EQUITY',priceHistoryCurrency:'ILS',priceHistoryLocation:'Israel'});$('addHistoricalPrice').click();")
    browser_wait(evaluate, "!$('priceEntryModal').hidden&&document.activeElement.id==='priceInput'")
    assert evaluate("$('pricesModal').inert") is True
    assert evaluate("$('pricesModal').getAttribute('aria-hidden')") == "true"
    assert evaluate("$('priceSymbol').value") == "ILTEST"
    assert evaluate("$('priceInput').value") == ""
    evaluate("$('priceInput').value='1234567.1234';$('priceDate').value='04/11/2026';$('priceComments').value='Draft note';loadLocalPrices();")
    browser_wait(evaluate, "$('priceDate').value==='04/11/2026'")
    evaluate("closeModal($('priceEntryModal'));$('addHistoricalPrice').click();")
    assert evaluate("[$('priceInput').value,$('priceDate').value,$('priceComments').value]") == ["1234567.1234", "04/11/2026", "Draft note"]
    assert ("agorot" if language == "en" else "אגורות") in evaluate("$('priceEntryUnits').textContent")
    geometry = evaluate("(()=>{const card=$('priceEntryModal').querySelector('.modal-card').getBoundingClientRect(),input=$('priceInput').getBoundingClientRect();return {left:card.left,right:card.right,inputWidth:input.width,overflow:document.documentElement.scrollWidth-innerWidth};})()")
    assert geometry["left"] >= 0 and geometry["right"] <= width and geometry["inputWidth"] >= 180 and geometry["overflow"] <= 1, geometry
    (tmp_path / f"price-entry-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    evaluate("qa.priceMode='hold';$('priceEntryForm').requestSubmit();$('priceEntryForm').requestSubmit();")
    browser_wait(evaluate, "qa.pricePosts.length===1&&state.priceEntry.saving")
    assert evaluate("$('savePrice').disabled") is True
    evaluate("closeModal($('priceEntryModal'));")
    assert evaluate("$('priceEntryModal').hidden") is False
    evaluate("qa.resolvePrice();")
    browser_wait(evaluate, "$('priceEntryModal').hidden&&!$('pricesModal').inert&&document.activeElement.id==='addHistoricalPrice'")
    assert evaluate("$('pricesModal').hidden") is False
    assert evaluate("$('priceFocusBar').hidden") is False
    assert evaluate("state.priceFocus.symbol") == "ILTEST"
    assert evaluate("qa.pricePosts[0].price_date") == "2026-11-04"
    assert evaluate("qa.pricePosts[0].price_input") == "1234567.1234"
    browser_wait(evaluate, "$('pricesList').textContent.includes('Draft note')")
    assert evaluate("qa.refreshes") == 1
    evaluate("state.auth.user.role='Viewer';renderCurrentUser();$('addHistoricalPrice').click();savePrice();")
    assert evaluate("$('addHistoricalPrice').disabled") is True
    assert evaluate("$('priceEntryModal').hidden") is True
    assert evaluate("qa.pricePosts.length") == 1 and evaluate("qa.errors") == []


def test_price_validation_failure_and_reload_failure_stay_in_the_correct_dialog(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("$('addHistoricalPrice').click();$('priceEntryForm').requestSubmit();")
    assert evaluate("$('priceSymbol').getAttribute('aria-invalid')") == "true"
    assert evaluate("qa.pricePosts.length") == 0
    evaluate("$('priceSymbol').value='ILTEST';$('priceMarket').value='TASE';$('priceInput').value='-1';$('priceEntryForm').requestSubmit();")
    assert evaluate("$('priceInput').getAttribute('aria-invalid')") == "true"
    assert "zero or more" in evaluate("$('priceEntryStatus').textContent")
    assert evaluate("qa.pricePosts.length") == 0
    evaluate("$('priceInput').value='0';$('priceDate').value='01/01/2099';$('priceEntryForm').requestSubmit();")
    assert evaluate("$('priceDate').getAttribute('aria-invalid')") == "true"
    assert "before today" in evaluate("$('priceEntryStatus').textContent")
    assert evaluate("qa.pricePosts.length") == 0
    evaluate("$('priceSymbol').value='ILTEST';$('priceMarket').value='TASE';$('priceInput').value='12.3456';$('priceDate').value='31/02/2026';$('priceEntryForm').requestSubmit();")
    assert evaluate("$('priceDate').getAttribute('aria-invalid')") == "true"
    assert evaluate("qa.pricePosts.length") == 0
    evaluate("$('priceDate').value='04/11/2026';qa.priceMode='error';$('priceEntryForm').requestSubmit();")
    browser_wait(evaluate, "!state.priceEntry.saving&&qa.pricePosts.length===1")
    assert evaluate("$('priceEntryModal').hidden") is False
    assert evaluate("$('priceInput').value") == "12.3456"
    assert "private raw server" not in evaluate("$('priceEntryStatus').textContent")
    assert "draft" in evaluate("$('priceEntryStatus').textContent")
    evaluate("$('priceInput').value='0';qa.priceMode='reload-error';$('priceEntryForm').requestSubmit();")
    browser_wait(evaluate, "$('priceEntryModal').hidden&&$('priceStatus').textContent.includes('could not reload')")
    assert evaluate("$('pricesModal').hidden") is False
    assert evaluate("qa.pricePosts.at(-1).price_input") == "0"
    assert evaluate("qa.pricePosts.length") == 2 and evaluate("qa.errors") == []
    assert "Redemption price" in evaluate("priceEvidenceText({source:'api_evidence',comments:JSON.stringify({kind:'price_evidence_v1',provider:'maya',price_basis:'redemption',quote_unit:'agorot'})})")


def test_authentication_reset_discards_price_draft_and_unlocks_history_parent(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("$('addHistoricalPrice').click();$('priceInput').value='123';$('priceComments').value='Old draft';showLogin();")
    assert evaluate("$('priceEntryModal').hidden") is True
    assert evaluate("$('pricesModal').inert") is False
    assert evaluate("$('pricesModal').hasAttribute('aria-hidden')") is False
    assert evaluate("$('priceInput').value") == ""
    assert evaluate("$('priceComments').value") == ""
    assert evaluate("state.priceFocus") is None
    evaluate("setAuthenticatedSession({user:{id:'new-owner',username:'new',role:'Operator'},csrf_token:'new-synthetic'});hideAuthOverlay();openModal('pricesModal');$('addHistoricalPrice').click();")
    assert evaluate("$('priceEntryModal').hidden") is False
    assert evaluate("$('priceSymbol').value") == ""
    assert evaluate("qa.pricePosts.length") == 0 and evaluate("qa.errors") == []
