"""Independent price-unit acceptance with real Chromium and synthetic REST.

The raw UI prices deliberately remain unchanged when the unit changes. These
tests do not read portfolio runtime data or call external import sources.
"""
import base64
import json
import subprocess

import pytest

from test_account_cash_update_qa import browser_wait
from app.local_portfolio import normalize_price
from test_native_account_history_qa import ROOT, chromium
from test_transaction_entry_frontend_qa import key, ready as transaction_ready
from test_price_entry_frontend import ready as historical_ready


def ready(tmp_path, chromium, width=1440, language="en"):
    command, evaluate = transaction_ready(tmp_path, chromium, width, language)
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    evaluate(r'''
qa.instruments=[qa.instrument,
 {id:'qa-bond',symbol:'91282TEST',stock_market:'MANUAL',asset_class:'BOND',instrument_type:'BOND',location:'USA',currency:'USD',name:'Synthetic bond'},
 {id:'qa-israel',symbol:'ILTEST',stock_market:'TASE',asset_class:'EQUITY',instrument_type:'STOCK',location:'Israel',currency:'ILS',name:'Synthetic local equity'}];
qa.previousApi=api;api=async(path,options={})=>path==='/api/local/manual-securities'?{items:qa.instruments}:qa.previousApi(path,options);
state.manualSecurities=qa.instruments;
state.localAccounts.push({...state.localAccounts[0],id:'qa-ils',location:'Israel',currency:'ILS',username:'Synthetic shekel'});
refreshLocalAccountSelects();refreshManualSecuritySelects();
qa.select=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}));};
qa.units=id=>{const input=$(id),label=input.closest('label');return {value:input.value,label:label?.innerText||'',title:input.title,
 descriptions:(input.getAttribute('aria-describedby')||'').split(/\s+/).filter(Boolean).map(id=>$(id)?.textContent||'').join(' '),
 labelTitle:label?.querySelector('[title]')?.title||''};};
qa.new().click();
''')
    # Data readiness precedes the modal's animation-frame initial focus.
    # Begin keyboard checks only after that user-visible opening has completed.
    browser_wait(evaluate, "state.transactionEntry.ready&&document.activeElement.id==='securityAccount'")
    return command, evaluate


def unit_text(evaluate, input_id):
    details = evaluate(f"qa.units('{input_id}')")
    assert details["descriptions"], details
    assert details["title"] or details["labelTitle"], details
    return " ".join(details[key] for key in ("label", "title", "descriptions", "labelTitle"))


def assert_tooltip_fits(evaluate, info_id, viewport):
    box = evaluate("""(()=>{const e=$('""" + info_id + """');let anchor=e;while(getComputedStyle(anchor).position==='static'&&anchor.parentElement)anchor=anchor.parentElement;
      const r=anchor.getBoundingClientRect(),s=getComputedStyle(e,'::after');
      const w=parseFloat(s.width)+(s.boxSizing==='border-box'?0:parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)+parseFloat(s.borderLeftWidth)+parseFloat(s.borderRightWidth));
      const left=s.left==='auto'?r.right-parseFloat(s.right)-w:r.left+parseFloat(s.left),card=e.closest('.modal-card').getBoundingClientRect();
      const h=parseFloat(s.height)+(s.boxSizing==='border-box'?0:parseFloat(s.paddingTop)+parseFloat(s.paddingBottom)+parseFloat(s.borderTopWidth)+parseFloat(s.borderBottomWidth));
      const top=s.top==='auto'?r.bottom-parseFloat(s.bottom)-h:r.top+parseFloat(s.top);
      return {left,right:left+w,top,bottom:top+h,cardLeft:card.left,cardRight:card.right,cardTop:card.top,cardBottom:card.bottom};})()""")
    assert box['left'] >= max(0, box['cardLeft']) - 1 and box['right'] <= min(viewport, box['cardRight']) + 1, box
    assert box['top'] >= max(0, box['cardTop']) - 1 and box['bottom'] <= box['cardBottom'] + 1, box


def test_unit_module_matches_actual_backend_scaling_and_does_not_change_values():
    contexts = []
    for location in ['USA', 'us', 'u.s.', 'u.s.a.', 'United States', 'United States of America',
                     'Israel', 'il', 'State of Israel', 'Germany']:
        for asset in ['EQUITY', 'BOND', 'BOND_FUND']:
            for currency in ['USD', 'ILS', 'EUR']:
                for action in ['BUY', 'SELL', 'DIVIDEND', 'INTEREST', 'FEE']:
                    context = dict(location=location, assetClass=asset, currency=currency, action=action)
                    normalized = 100 if action in ['DIVIDEND', 'INTEREST', 'FEE'] else normalize_price(100, location, asset)
                    expected = ('US cents' if currency == 'USD' else 'Agorot' if currency == 'ILS' else 'Hundredths of {currency}') if normalized == 1 else ('US dollars' if currency == 'USD' else '{currency} per unit')
                    contexts.append([context, expected])
    script = "const assert=require('node:assert/strict');const units=require('./web/price-input-units.js');\n"
    script += "const cases=" + json.dumps(contexts) + ";\n"
    script += r'''
for(const [context,expected] of cases){const before=JSON.stringify(context);assert.equal(units.describe(context).unitKey,expected,JSON.stringify(context));assert.equal(JSON.stringify(context),before);}
const input={value:'100',setAttribute(name,value){this[name]=value;}},unit={},info={dataset:{},setAttribute(name,value){this[name]=value;}},hint={id:'raw-hint'};
units.bind({input,unit,info,hint},{location:'USA',currency:'USD',assetClass:'BOND'},x=>x);
assert.equal(input.value,'100');assert.equal(input['aria-describedby'],'raw-hint');assert.equal(input.title,hint.textContent);assert.equal(info.dataset.tooltip,hint.textContent);
'''
    subprocess.run(['node'], input=script, text=True, check=True, capture_output=True, cwd=ROOT)


@pytest.mark.parametrize("width,language", [(1440, "en"), (390, "en"), (1440, "he"), (390, "he")])
def test_transaction_units_follow_instrument_account_action_and_keep_draft(tmp_path, chromium, width, language):
    command, evaluate = ready(tmp_path, chromium, width, language)
    evaluate("$('securityPrice').value='1234567.1234';qa.select('securityKnownInstrument','qa-equity');")
    assert ("dollars" if language == "en" else "דולר") in unit_text(evaluate, "securityPrice")
    evaluate("qa.select('securityKnownInstrument','qa-bond');")
    assert ("cents" if language == "en" else "סנט") in unit_text(evaluate, "securityPrice")
    assert "100" in unit_text(evaluate, "securityPrice")
    evaluate("qa.select('securityAccount','qa-ils');")
    assert ("cents" if language == "en" else "סנט") in unit_text(evaluate, "securityPrice")
    for action in ["DIVIDEND", "INTEREST", "FEE"]:
        evaluate(f"qa.select('securityAction','{action}');")
        text = unit_text(evaluate, "securityPrice")
        assert ("dollars" if language == "en" else "דולר") in text, text
        assert ("cents" if language == "en" else "סנט") not in text, text
    evaluate("qa.select('securityAction','SELL');qa.select('securityKnownInstrument','qa-israel');")
    assert ("agorot" if language == "en" else "אגורות") in unit_text(evaluate, "securityPrice")
    evaluate("qa.select('securityKnownInstrument','');qa.select('securityAccount','qa-dollar');")
    assert ("agorot" if language == "en" else "אגורות") in unit_text(evaluate, "securityPrice")
    evaluate("qa.select('securityAccount','qa-ils');")
    evaluate("qa.select('securityKnownInstrument','');$('securitySymbol').value='FREE_QA';$('securityMarket').value='NASDAQ';qa.select('securityAssetClass','EQUITY');")
    assert ("agorot" if language == "en" else "אגורות") in unit_text(evaluate, "securityPrice")
    evaluate("qa.select('securityAccount','qa-dollar');")
    assert ("dollars" if language == "en" else "דולר") in unit_text(evaluate, "securityPrice")
    assert evaluate("$('securityPrice').value") == "1234567.1234"
    geometry = evaluate("(()=>{const input=$('securityPrice'),r=input.getBoundingClientRect(),card=qa.entry().querySelector('.modal-card').getBoundingClientRect();return {width:r.width,overflow:document.documentElement.scrollWidth-innerWidth,left:card.left,right:card.right};})()")
    assert geometry['width'] >= 140 and geometry['overflow'] <= 1 and geometry['left'] >= 0 and geometry['right'] <= width, geometry
    evaluate("qa.select('securityKnownInstrument','qa-bond');")
    evaluate("$('securityPrice').focus();")
    assert evaluate("document.activeElement.id") == "securityPrice"
    evaluate("$('securityPriceUnitInfo').scrollIntoView({block:'center'});")
    key(command, 'Tab', shift=True)
    assert evaluate("document.activeElement.id") == "securityPriceUnitInfo"
    browser_wait(evaluate, "getComputedStyle($('securityPriceUnitInfo'),'::after').opacity", "1")
    assert_tooltip_fits(evaluate, "securityPriceUnitInfo", width)
    assert evaluate("getComputedStyle($('securityPriceUnitInfo'),'::after').content").strip('"')
    evaluate("$('securityPriceUnitInfo').blur();")
    point = evaluate("(()=>{const r=$('securityPriceUnitInfo').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()")
    command("Input.dispatchMouseEvent", {"type": "mouseMoved", **point})
    browser_wait(evaluate, "getComputedStyle($('securityPriceUnitInfo'),'::after').opacity", "1")
    (tmp_path / f"price-units-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})['data']))
    assert evaluate("qa.txPosts.length") == 0
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("width,language", [(1440, "en"), (390, "en"), (1440, "he"), (390, "he")])
def test_position_buy_sell_history_units_and_edit_preserve_raw_price(tmp_path, chromium, width, language):
    command, evaluate = ready(tmp_path, chromium, width, language)
    evaluate(r'''
closeModal(qa.entry());closeModal($('securitiesModal'));
qa.positionContext={positionAction:'SELL',positionHistorySymbol:'91282TEST',positionHistoryMarket:'MANUAL',
 positionHistoryAccountId:'qa-dollar',positionHistoryAccount:'Synthetic Dollar',positionHistoryCurrency:'USD',
 positionHistoryQuantity:'8000',positionHistoryAsset:'BOND',positionHistoryLocation:'USA'};
openPositionTransactionHistory(qa.positionContext);
''')
    browser_wait(evaluate, "!$('positionTransactionsModal').hidden")
    assert ("cents" if language == 'en' else "סנט") in unit_text(evaluate, "positionTransactionPrice")
    evaluate("$('positionTransactionPrice').value='100';qa.select('positionTransactionAction','BUY');")
    assert ("cents" if language == 'en' else "סנט") in unit_text(evaluate, "positionTransactionPrice")
    evaluate("qa.rows.push({id:'qa-position-edit',account_db_id:'qa-dollar',security_id:'qa-bond',action:'SELL',symbol:'91282TEST',stock_market:'MANUAL',asset_class:'BOND',location:'USA',currency:'USD',quantity:8000,price_input:100,price:1,trade_date:'2026-11-04'});state.localTransactions=qa.rows;editPositionTransaction('qa-position-edit');")
    assert evaluate("$('positionTransactionPrice').value") == '100'
    assert ("cents" if language == 'en' else "סנט") in unit_text(evaluate, "positionTransactionPrice")
    evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
    evaluate("$('positionTransactionPriceUnitInfo').scrollIntoView({block:'center'});$('positionTransactionPriceUnitInfo').focus();")
    assert evaluate("document.activeElement.id") == "positionTransactionPriceUnitInfo"
    browser_wait(evaluate, "getComputedStyle($('positionTransactionPriceUnitInfo'),'::after').opacity", "1")
    assert_tooltip_fits(evaluate, "positionTransactionPriceUnitInfo", width)
    (tmp_path / f"position-price-units-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})['data']))
    geometry = evaluate("(()=>{const r=$('positionTransactionPrice').getBoundingClientRect();return {left:r.left,right:r.right,width:r.width,overflow:document.documentElement.scrollWidth-innerWidth};})()")
    assert geometry['left'] >= 0 and geometry['right'] <= width and geometry['width'] >= 140 and geometry['overflow'] <= 1, geometry
    assert evaluate("qa.txPosts.length") == 0
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("width,language", [(1440, "en"), (390, "en"), (1440, "he"), (390, "he")])
def test_historical_price_unit_hint_tracks_location_currency_and_asset(tmp_path, chromium, width, language):
    command, evaluate = historical_ready(tmp_path, chromium, width, language)
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    evaluate(r'''
qa.select=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}));};
qa.units=id=>{const input=$(id),label=input.closest('label');return {value:input.value,label:label?.innerText||'',title:input.title,
 descriptions:(input.getAttribute('aria-describedby')||'').split(/\s+/).filter(Boolean).map(id=>$(id)?.textContent||'').join(' '),
 labelTitle:label?.querySelector('[title]')?.title||''};};
$('addHistoricalPrice').click();$('priceInput').value='100';qa.select('priceLocation','USA');qa.select('priceAssetClass','BOND');
''')
    assert ("cents" if language == 'en' else "סנט") in unit_text(evaluate, "priceInput")
    evaluate("qa.select('priceAssetClass','EQUITY');")
    assert ("dollars" if language == 'en' else "דולר") in unit_text(evaluate, "priceInput")
    evaluate("qa.select('priceLocation','Israel');")
    assert ("agorot" if language == 'en' else "אגורות") in unit_text(evaluate, "priceInput")
    assert evaluate("$('priceInput').value") == '100'
    evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
    evaluate("$('priceInputUnitInfo').scrollIntoView({block:'center'});$('priceInputUnitInfo').focus();")
    assert evaluate("document.activeElement.id") == "priceInputUnitInfo"
    browser_wait(evaluate, "getComputedStyle($('priceInputUnitInfo'),'::after').opacity", "1")
    assert_tooltip_fits(evaluate, "priceInputUnitInfo", width)
    (tmp_path / f"historic-price-units-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})['data']))
    assert evaluate("qa.pricePosts.length") == 0
    assert evaluate("qa.errors") == []


def test_unit_language_change_and_bond_save_preserve_entered_payload(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("qa.select('securityKnownInstrument','qa-bond');$('securityQuantity').value='8000';$('securityPrice').value='100';$('securityDate').value='04/11/2026';")
    assert "cents" in unit_text(evaluate, "securityPrice")
    evaluate("state.language='he';applyLanguage();")
    text = unit_text(evaluate, "securityPrice")
    assert "סנט" in text and "cents" not in text, text
    evaluate("state.language='en';applyLanguage();")
    text = unit_text(evaluate, "securityPrice")
    assert "cents" in text and not any('\u0590' <= char <= '\u05ff' for char in text), text
    assert evaluate("$('securityPrice').value") == "100"
    evaluate("$('saveSecurity').click();")
    browser_wait(evaluate, "qa.txPosts.length===1&&qa.entry().hidden")
    payload = evaluate("qa.txPosts[0].payload")
    assert payload['price_input'] == "100" and payload['quantity'] == "8000" and payload['security_id'] == 'qa-bond', payload
    assert not any('hint' in key.lower() or 'tooltip' in key.lower() for key in payload), payload
    assert evaluate("qa.errors") == []
