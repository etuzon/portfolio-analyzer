"""Independent maturity acceptance from synthetic ledgers and actual UI scripts.

All portfolio fixtures use temporary stores. Browser checks load the real page
and scripts in disposable Chromium and replace external I/O with synthetic rows.
"""

import json
import re
import subprocess
import base64
from dataclasses import asdict

import pytest

from app.local_portfolio import LocalPortfolioStore
from test_native_account_history_qa import ROOT, account, chromium
from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_shared_cash_risk_qa import app_functions


def bond(store, **overrides):
    return store.save_manual_security({"symbol": "QABOND", "stock_market": "MANUAL",
        "instrument_type": "BOND", "name": "Synthetic bond", "currency": "USD",
        "location": "USA", **overrides})


def bond_trade(store, owner, security=None, **overrides):
    return store.add_transaction({"account_db_id": owner["id"], "action": "BUY",
        "symbol": "QABOND", "stock_market": "MANUAL", "security_id": (security or {}).get("id", ""),
        "asset_class": "BOND", "currency": "USD", "quantity": 1000,
        "price_input": 98, "trade_date": "2026-01-01", "allow_manual": True, **overrides})


def test_maturity_persists_shared_instrument_and_omission_never_erases(tmp_path):
    store = LocalPortfolioStore(tmp_path / "maturity.sqlite")
    owners = [account(store, "First"), account(store, "Second")]
    security = bond(store, maturity_date="2026-11-07")
    first = bond_trade(store, owners[0], security)
    bond_trade(store, owners[1], security)
    assert store.manual_security_by_id(security["id"])["maturity_date"] == "2026-11-07"
    assert {row["maturity_date"] for row in store.list_transactions()} == {"2026-11-07"}
    assert {row.holding.maturity_date for row in store.holdings()} == {"2026-11-07"}
    # An old caller has no maturity field; both instrument and transaction edits preserve it.
    bond(store, id=security["id"], name="Renamed synthetic bond")
    store.update_transaction(first["id"], {**{key: value for key, value in first.items() if key != "maturity_date"}, "quantity": 800})
    assert {row["maturity_date"] for row in store.list_transactions()} == {"2026-11-07"}
    # Changing the shared date through one transaction updates both accounts.
    bond_trade(store, owners[0], security, quantity=1, maturity_date="2027-03-04")
    assert {row["maturity_date"] for row in store.list_transactions()} == {"2027-03-04"}
    restarted = LocalPortfolioStore(store.path)
    assert {row.holding.maturity_date for row in restarted.holdings()} == {"2027-03-04"}
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite")
    restored.import_data(restarted.export_data())
    assert {row.holding.maturity_date for row in restored.holdings()} == {"2027-03-04"}
    # Explicit clear means unknown, and never creates a redemption/cash movement.
    before = [(row["id"], row["action"], row["quantity"], row["price"]) for row in restored.list_transactions()]
    bond(restored, id=security["id"], maturity_date="")
    assert {row["maturity_date"] for row in restored.list_transactions()} == {""}
    assert [(row["id"], row["action"], row["quantity"], row["price"]) for row in restored.list_transactions()] == before


def test_unregistered_bond_maturity_survives_add_edit_and_isolated_from_derivative_expiry(tmp_path):
    store = LocalPortfolioStore(tmp_path / "maturity.sqlite")
    owner = account(store)
    buy = bond_trade(store, owner, maturity_date="01/01/2000")
    assert store.list_transactions()[0]["maturity_date"] == "2000-01-01"
    store.update_transaction(buy["id"], {**buy, "quantity": 1200})
    assert store.list_transactions()[0]["maturity_date"] == "2000-01-01"
    security = bond(store, maturity_date="2026-11-07")
    assert store.manual_security_by_id(security["id"])["expiration_date"] == ""
    assert store.manual_security_by_id(security["id"])["maturity_date"] == "2026-11-07"
    other = store.save_manual_security({"symbol": "QAFUTURE", "stock_market": "MANUAL",
        "instrument_type": "FUTURE", "currency": "USD", "location": "USA", "expiration_date": "2028-01-03"})
    assert other["expiration_date"] == "2028-01-03"
    assert not other.get("maturity_date")


@pytest.mark.parametrize("raw", ["2026-02-30", "31/02/2026", "2026-13-01", "nonsense", [], {}])
def test_invalid_maturity_is_rejected_atomically(tmp_path, raw):
    store = LocalPortfolioStore(tmp_path / "maturity.sqlite")
    owner = account(store)
    security = bond(store, maturity_date="2026-11-07")
    with pytest.raises((ValueError, TypeError)):
        bond_trade(store, owner, security, maturity_date=raw)
    assert store.list_transactions() == []
    assert store.manual_security_by_id(security["id"])["maturity_date"] == "2026-11-07"
    with pytest.raises((ValueError, TypeError)):
        bond(store, id=security["id"], maturity_date=raw)
    assert store.manual_security_by_id(security["id"])["maturity_date"] == "2026-11-07"


def test_maturity_not_accepted_for_equity(tmp_path):
    store = LocalPortfolioStore(tmp_path / "maturity.sqlite")
    with pytest.raises(ValueError):
        bond(store, instrument_type="STOCK", maturity_date="2026-11-07")


@pytest.mark.parametrize("instant,day,due", [
    ("2026-11-06T21:59:59Z", "2026-11-07", False),
    ("2026-11-06T22:00:00Z", "2026-11-07", True),
    ("2026-11-07T22:00:00Z", "2026-11-07", True),
    ("2026-06-30T20:59:59Z", "2026-07-01", False),
    ("2026-06-30T21:00:00Z", "2026-07-01", True),
])
def test_due_date_uses_jerusalem_and_full_unpriced_portfolio(instant, day, due):
    script = "const assert=require('node:assert/strict');const t=x=>x,fmt=String;\n"
    script += app_functions("validIsoDate", "parseDateInput", "holdingMarketKey", "alarmText", "alarmValue", "formatDate", "bondMaturityAlarms")
    script += "\nconst instant=" + json.dumps(instant) + ",day=" + json.dumps(day) + ";\n"
    script += r'''
const make=(account,extra={})=>({holding:{account_id:account,account:'Synthetic '+account,symbol:'QABOND',stock_market:'MANUAL',asset_class:'BOND',currency:'USD',quantity:1000,maturity_date:day,...extra}});
// The visible dashboard is filtered to nothing; source holdings lack prices.
const state={items:[],allPortfolioItems:[make('a'),make('a'),make('b'),make('closed',{quantity:0}),
make('short',{quantity:-1000}),make('unknown',{maturity_date:''}),make('malformed',{maturity_date:'31/02/2026'}),
make('equity',{asset_class:'EQUITY'}),make('derivative',{asset_class:'OPTION',maturity_date:'',expiration_date:day}),make('future',{maturity_date:'2099-01-01'})],dismissedAlarmIds:[]};
const alarms=bondMaturityAlarms(new Date(instant));
'''
    script += f"assert.equal(alarms.length,{2 if due else 0});\n"
    if due:
        script += r'''
assert.deepEqual(alarms.map(alarm=>alarm.holding.account_id),['a','b']);
assert.ok(alarms.every(alarm=>alarm.kind==='maturity'&&alarm.tone==='red'&&alarm.body.includes('broker statement')));
assert.ok(alarms.every(alarm=>!alarm.meta.includes(day)),'UI date must use dd/mm/yyyy');
state.items=[make('unrelated')];state.dismissedAlarmIds=alarms.map(alarm=>alarm.key);
assert.equal(bondMaturityAlarms(new Date(instant)).length,2);
state.allPortfolioItems[0].holding.quantity=250;state.allPortfolioItems[1].holding.quantity=250;
assert.equal(bondMaturityAlarms(new Date(instant)).length,2,'partial sale leaves action required');
state.allPortfolioItems[0].holding.quantity=0;state.allPortfolioItems[1].holding.quantity=0;
assert.deepEqual(bondMaturityAlarms(new Date(instant)).map(a=>a.holding.account_id),['b']);
'''
    result = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def maturity_browser_ready(tmp_path, chromium, width, language):
    # Reuse the isolated full-page asset loader, then restore the real portfolio
    # loading function so save-triggered invalidation is part of acceptance.
    fixture = cash_browser_document(tmp_path, language)
    source = (ROOT / "web/app.js").read_text()
    start = source.index("async function loadPortfolio(")
    end = start + re.search(r"^}", source[start:], re.M).end()
    real_loader = source[start:end].replace("async function loadPortfolio(", "loadPortfolio = async function(", 1)
    store = LocalPortfolioStore(tmp_path / "browser-fixture.sqlite")
    owner = account(store, "Synthetic Dollar", initial_cash=10000)
    security = bond(store)
    tx = bond_trade(store, owner, security)
    template = json.loads(json.dumps(asdict(store.holdings()[0]), default=str))
    setup = r'''
qa.posts=[];qa.portfolioReads=0;qa.instrument=QA_SECURITY;qa.account=QA_ACCOUNT;qa.rows=[QA_TRANSACTION];qa.template=QA_TEMPLATE;
state.localAccounts=[qa.account];state.localTransactions=structuredClone(qa.rows);state.manualSecurities=[qa.instrument];
state.dashboard=defaultDashboard();state.alertData={active_signals:[]};state.localEvents=[];state.alarmsEventsLoaded=true;
watchPortfolioUpdates=()=>{};loadHeatmap=()=>{};recordRiskHistory=async()=>{};
loadLocalAccounts=async()=>{state.localAccounts=[qa.account];refreshLocalAccountSelects();};
api=async(path,options={})=>{
 qa.calls.push(path);
 if(path==='/api/local/manual-securities'&&options.method==='POST'){
  const payload=JSON.parse(options.body);qa.posts.push({path,payload});
  qa.instrument={...qa.instrument,...payload,id:qa.instrument.id,asset_class:'BOND'};return structuredClone(qa.instrument);
 }
 if(path==='/api/local/manual-securities')return {items:[structuredClone(qa.instrument)]};
 if(path.startsWith('/api/local/securities')&&['POST','PUT'].includes(options.method)){
  const payload=JSON.parse(options.body);qa.posts.push({path,payload});
  if('maturity_date' in payload)qa.instrument.maturity_date=payload.maturity_date;
  const record={...qa.rows[0],...payload,id:options.method==='PUT'?path.split('/').at(-1):'saved-'+qa.posts.length,quantity:Number(payload.quantity),price_input:Number(payload.price_input),price:Number(payload.price_input)/100};
  if(options.method==='PUT')qa.rows=qa.rows.map(row=>row.id===record.id?record:row);else qa.rows.push(record);
  const quantity=qa.rows.reduce((n,row)=>n+(['SELL','REMOVE'].includes(row.action)?-1:1)*Number(row.quantity),0);
  return {...record,position_quantity:quantity,position_closed:quantity===0};
 }
 if(path==='/api/local/securities')return {items:qa.rows.map(row=>({...row,maturity_date:qa.instrument.maturity_date||''}))};
 if(path==='/api/local/accounts')return {items:[qa.account]};
 if(path.startsWith('/api/portfolio')){
  qa.portfolioReads++;const quantity=qa.rows.reduce((n,row)=>n+(['SELL','REMOVE'].includes(row.action)?-1:1)*Number(row.quantity),0);
  const item=structuredClone(qa.template);item.holding.quantity=quantity;item.holding.maturity_date=qa.instrument.maturity_date||'';
  return {items:quantity?[item]:[],count:quantity?1:0,refresh_state:'ready',refresh_pending:false};
 }
 if(path==='/api/fx')return {quotes:[]};
 if(path.includes('account-trends'))return {accounts:[]};
 return {items:[],industries:[]};
};
refreshLocalizedFormOptions();refreshLocalAccountSelects();refreshManualSecuritySelects();
'''.replace("QA_SECURITY", json.dumps(security)).replace("QA_ACCOUNT", json.dumps(owner)).replace("QA_TRANSACTION", json.dumps(tx)).replace("QA_TEMPLATE", json.dumps(template))
    script = tmp_path / "cash-app.js"
    script.write_text(script.read_text() + "\n" + real_loader + ";\n" + setup + "\nqa.maturityReady=true;")
    command, evaluate = chromium
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": fixture.as_uri()})
    browser_wait(evaluate, "window.qa?.maturityReady===true")
    assert evaluate("qa.errors") == []
    return command, evaluate


@pytest.mark.parametrize("width,language", [(1440, "en"), (1440, "he"), (390, "en"), (390, "he")])
def test_browser_maturity_add_edit_persist_alarm_red_action_and_not_clearable(tmp_path, chromium, width, language):
    command, evaluate = maturity_browser_ready(tmp_path, chromium, width, language)
    evaluate("newManualSecurity();$('manualInstrumentType').value='BOND';$('manualInstrumentType').dispatchEvent(new Event('change',{bubbles:true}));$('manualSecuritySymbol').value='QABOND';$('manualSecurityMarket').value='MANUAL';$('manualSecurityName').value='Synthetic bond';$('manualSecurityCurrency').value='USD';$('manualBondMaturityDate').value='31/02/2026';$('saveManualSecurity').click();")
    assert evaluate("qa.posts.length") == 0
    assert evaluate("$('manualBondMaturityDate').validity.valid") is False
    evaluate("$('manualBondMaturityDate').value='07/11/2000';$('manualBondMaturityDate').dispatchEvent(new Event('input',{bubbles:true}));$('saveManualSecurity').click();")
    browser_wait(evaluate, "$('instrumentEditorModal').hidden&&qa.portfolioReads>0&&bondMaturityAlarms().length===1")
    assert evaluate("qa.posts[0].payload.maturity_date") == "2000-11-07"
    evaluate("editManualSecurity(qa.instrument.id);")
    assert evaluate("$('manualBondMaturityDate').value") == "07/11/2000"
    geometry = evaluate("(()=>{const e=$('manualBondMaturityDate'),r=e.getBoundingClientRect();return {left:r.left,right:r.right,width:r.width,visible:!e.closest('[data-bond-maturity-field]').hidden,overflow:document.documentElement.scrollWidth-innerWidth};})()")
    assert geometry["visible"] and geometry["width"] >= 120 and geometry["left"] >= 0 and geometry["right"] <= width and geometry["overflow"] <= 1, geometry
    if language == "he":
        assert "Bond maturity date" not in evaluate("$('manualBondMaturityDate').closest('label').textContent")
        assert evaluate("$('saveManualSecurity').textContent") == "עדכון נייר ערך"
        assert "Editing instrument" not in evaluate("$('manualSecurityStatus').textContent")
    (tmp_path / f"bond-maturity-form-{width}-{language}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    # A metadata-only correction refreshes allPortfolioItems through the actual loader.
    evaluate("$('manualBondMaturityDate').value='01/01/2099';$('saveManualSecurity').click();")
    browser_wait(evaluate, "$('instrumentEditorModal').hidden&&qa.portfolioReads>=2&&bondMaturityAlarms().length===0")
    evaluate("openTransactionEntry({transactionId:qa.rows[0].id});")
    browser_wait(evaluate, "state.transactionEntry?.ready&&!state.transactionEntry?.loading")
    assert evaluate("$('securityBondMaturityDate').value") == "01/01/2099"
    evaluate("$('securityBondMaturityDate').value='07/11/2000';$('saveSecurity').click();")
    browser_wait(evaluate, "$('transactionEntryModal').hidden&&bondMaturityAlarms().length===1")
    assert evaluate("qa.posts.at(-1).payload.maturity_date") == "2000-11-07"
    evaluate("openTransactionEntry({transactionId:qa.rows[0].id});")
    browser_wait(evaluate, "state.transactionEntry?.ready&&!state.transactionEntry?.loading")
    assert evaluate("$('securityBondMaturityDate').value") == "07/11/2000"
    geometry = evaluate("(()=>{const r=$('securityBondMaturityDate').getBoundingClientRect();return {left:r.left,right:r.right,width:r.width};})()")
    assert geometry["width"] >= 120 and geometry["left"] >= 0 and geometry["right"] <= width, geometry
    evaluate("closeModal($('transactionEntryModal'));state.items=[];openModal('alarmsModal');renderAlarms();")
    alarm = evaluate("(()=>{const e=$('alarmsList').querySelector('[data-open-maturity-alarm]');return {text:e.textContent,tone:e.dataset.alarmTone,clear:e.closest('.alarm-entry').querySelector('[data-clear-alarm]')!==null};})()")
    assert alarm["tone"] == "red" and alarm["clear"] is False
    assert "07/11/2000" in alarm["text"]
    assert ("broker statement" if language == "en" else "הברוקר") in alarm["text"]
    assert evaluate("$('alarmsButton').dataset.alarmTone") == "red"
    (tmp_path / f"bond-maturity-alarm-{width}-{language}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    if language == "he":
        for phrase in ["Action required", "Bond maturity", "units are still recorded", "Maturity:"]:
            assert phrase not in evaluate("$('alarmsList').textContent")
    # Bulk clearing and a forged direct clear both preserve the required action.
    evaluate("clearSelectedAlarms({all:true});")
    browser_wait(evaluate, "!state.alarmClearPending")
    evaluate("clearSelectedAlarms({key:alarmClearKey(bondMaturityAlarms()[0])});")
    browser_wait(evaluate, "!state.alarmClearPending")
    assert evaluate("$('alarmsList').querySelectorAll('[data-open-maturity-alarm]').length") == 1
    assert evaluate("$('clearAlarms').disabled&&$('clearMatchingAlarms').disabled")
    assert evaluate("!state.dismissedAlarmIds.some(value=>String(value).startsWith('maturity:'))")
    evaluate("document.querySelector('[data-open-maturity-alarm]').focus();")
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
    browser_wait(evaluate, "!$('positionTransactionsModal').hidden&&$('positionTransactionsRows').querySelectorAll('tr').length===1")
    assert evaluate("state.positionTransactionsDetail.accountId") == evaluate("qa.account.id")
    assert evaluate("$('positionTransactionAction').value") == "SELL"
    assert evaluate("qa.posts.length") == 3  # inspecting never writes or credits cash
    assert evaluate("$('positionTransactionBondMaturityDate').value") == "07/11/2000"
    geometry = evaluate("(()=>{const e=$('positionTransactionBondMaturityDate');e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {left:r.left,right:r.right,width:r.width};})()")
    assert geometry["width"] >= 120 and geometry["left"] >= 0 and geometry["right"] <= width, geometry
    if language == "he":
        assert "Bond maturity date" not in evaluate("$('positionTransactionBondMaturityField').textContent")
        for phrase in ["Add transaction", "Available to sell", "units", "Save"]:
            assert phrase not in evaluate("$('positionTransactionFormTitle').textContent+$('positionTransactionLimit').textContent+$('savePositionTransaction').textContent")
    (tmp_path / f"bond-maturity-action-{width}-{language}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    # Editing through the holding history also exposes and saves the shared date.
    evaluate("editPositionTransaction(qa.rows[0].id);")
    assert evaluate("$('positionTransactionBondMaturityDate').value") == "07/11/2000"
    if language == "he":
        for phrase in ["Edit", "Update", "Editing", "transaction history", "from"]:
            assert phrase not in evaluate("$('positionTransactionFormTitle').textContent+$('positionTransactionLimit').textContent+$('savePositionTransaction').textContent+$('positionTransactionStatus').textContent")
    evaluate("$('positionTransactionBondMaturityDate').value='09/11/2000';$('savePositionTransaction').click();")
    browser_wait(evaluate, "qa.posts.length===4&&bondMaturityAlarms()[0]?.maturityDate==='2000-11-09'")
    # The actual action form writes only the explicit partial/full sales.
    evaluate("$('positionTransactionAction').value='SELL';$('positionTransactionAction').dispatchEvent(new Event('change',{bubbles:true}));$('positionTransactionQuantity').value='250';$('positionTransactionPrice').value='100';$('positionTransactionBondMaturityDate').value='31/02/2026';$('savePositionTransaction').click();")
    assert evaluate("qa.posts.length") == 4
    evaluate("$('positionTransactionBondMaturityDate').value='08/11/2000';$('positionTransactionBondMaturityDate').dispatchEvent(new Event('input',{bubbles:true}));$('savePositionTransaction').click();")
    browser_wait(evaluate, "qa.posts.length===5&&bondMaturityAlarms()[0]?.holding.quantity===750")
    assert evaluate("bondMaturityAlarms()[0].maturityDate") == "2000-11-08"
    assert evaluate("qa.rows.filter(row=>row.action==='SELL').length") == 1
    evaluate("closeModal($('positionTransactionsModal'));state.auth.user.role='Viewer';openModal('alarmsModal');renderAlarms();document.querySelector('[data-open-maturity-alarm]').click();")
    browser_wait(evaluate, "!$('positionTransactionsModal').hidden")
    evaluate("savePositionTransaction();")
    assert evaluate("qa.posts.length") == 5
    evaluate("closeModal($('positionTransactionsModal'));state.auth.user.role='Admin';openModal('alarmsModal');renderAlarms();document.querySelector('[data-open-maturity-alarm]').click();")
    browser_wait(evaluate, "!$('positionTransactionsModal').hidden&&$('positionTransactionAction').value==='SELL'")
    assert evaluate("$('positionTransactionBondMaturityDate').value") == "08/11/2000"
    evaluate("$('positionTransactionQuantity').value='750';$('positionTransactionPrice').value='100';$('savePositionTransaction').click();")
    browser_wait(evaluate, "qa.posts.length===6&&bondMaturityAlarms().length===0")
    assert evaluate("qa.rows.filter(row=>row.action==='SELL').length") == 2
    assert evaluate("qa.rows.every(row=>!['CASH_IN','CASH_OUT','DIVIDEND','INTEREST'].includes(row.action))")
    assert evaluate("qa.errors") == []
