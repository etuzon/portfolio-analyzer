"""Independent cash-reconciliation evidence from synthetic raw USD fixtures.

Tests preserve the historical cash anchor, use observable APIs and independent
arithmetic, and never read runtime portfolio data or external import sources.
"""
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth import AuthStore
from app.local_portfolio import LocalPortfolioStore
from test_auth import _change_password, _login
from test_native_account_history_qa import account, transaction, chromium, ROOT


def today():
    return datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat()


@pytest.fixture
def cash_env(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "cash-qa.sqlite")
    auth = AuthStore(store.path)
    auth.initialize()
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    main._login_failures.clear()
    client = TestClient(main.app, base_url="https://localhost:6443", raise_server_exceptions=False)
    session = _change_password(client, _login(client), "admin", "Cash-QA-Password-2026!")
    client.headers["X-CSRF-Token"] = session["csrf_token"]
    owner = account(store)
    return store, client, owner


def path(owner):
    return f"/api/local/accounts/{owner['id']}/cash-balance"


def context(client, owner):
    response = client.get(path(owner))
    assert response.status_code == 200, response.text
    return response.json()


def reconcile(client, owner, target, *, revision=None, request_id=None):
    if revision is None:
        revision = context(client, owner)["cash_revision"]
    intent = {"target_cash": target, "cash_revision": revision, "request_id": request_id or str(uuid4())}
    return client.post(path(owner), json=intent), intent


def security_fixture(store, owner):
    buy = transaction(store, owner)
    store.save_price({"symbol": "QA", "stock_market": "NYSE", "asset_class": "EQUITY", "location": "USA",
                      "currency": "USD", "price_input": 25, "price_date": today()})
    return buy


@pytest.mark.parametrize("target,delta,action", [(500, -300, "CASH_OUT"), (0, -800, "CASH_OUT"),
                                                   (-125.5, -925.5, "CASH_OUT"), (1250, 450, "CASH_IN")])
def test_reconciliation_changes_signed_cash_without_income_or_position(cash_env, target, delta, action):
    store, client, owner = cash_env
    security_fixture(store, owner)
    before = context(client, owner)
    assert before["available"] is True and before["cash"] == 800
    assert before["currency"] == "USD" and before["effective_date"] == today()
    response, intent = reconcile(client, owner, target, revision=before["cash_revision"])
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["cash"] == target and result["delta"] == delta and result["adjusted"] is True
    assert result["request_id"] == intent["request_id"] and result["replayed"] is False
    assert store.list_accounts()[0]["initial_cash"] == 1000
    ledger = store.list_transactions()
    adjustment = next(tx for tx in ledger if tx["id"] == result["transaction_id"])
    assert (adjustment["action"], adjustment["quantity"], adjustment["price"], adjustment["currency"], adjustment["trade_date"]) == (action, abs(delta), 1, "USD", today())
    holdings = store.holdings()
    assert len(holdings) == 1 and holdings[0].holding.quantity == 10
    assert holdings[0].holding.unrealized_profit == 50
    import json
    security_history = store.trade_history({"account_id": owner["id"]}, as_of_date=today())
    assert len(security_history["items"]) == 1
    assert result["transaction_id"] not in json.dumps(security_history)
    report = store.reports({"account_id": owner["id"]})
    assert report["cash"] == target and report["securities_value"] == 250 and report["value"] == target + 250
    points = store.account_trends({"account_id": owner["id"], "from": today(), "to": today()})["accounts"][0]["points"]
    assert points[-1]["cash"] == target and points[-1]["value"] == target + 250
    assert points[-1]["profit"] == 50


def test_cas_noop_and_replay_never_overwrite_a_later_legitimate_balance(cash_env):
    store, client, owner = cash_env
    stale = context(client, owner)["cash_revision"]
    response, first = reconcile(client, owner, 600, revision=stale)
    assert response.status_code == 200, response.text
    second, _ = reconcile(client, owner, -20)
    assert second.status_code == 200
    rows = len(store.list_transactions())
    retry = client.post(path(owner), json=first)
    assert retry.status_code == 200 and retry.json()["replayed"] is True
    assert context(client, owner)["cash"] == -20 and len(store.list_transactions()) == rows
    conflict = client.post(path(owner), json={**first, "target_cash": 601})
    assert conflict.status_code == 409
    stale_response, _ = reconcile(client, owner, 800, revision=stale)
    assert stale_response.status_code == 409
    noop, noop_intent = reconcile(client, owner, -20)
    assert noop.status_code == 200 and noop.json()["adjusted"] is False and noop.json()["delta"] == 0
    assert noop.json()["transaction_id"] is None and len(store.list_transactions()) == rows
    repeated_noop = client.post(path(owner), json=noop_intent)
    assert repeated_noop.status_code == 200 and repeated_noop.json()["adjusted"] is False
    later, _ = reconcile(client, owner, 90)
    assert later.status_code == 200
    replay_noop = client.post(path(owner), json=noop_intent)
    assert replay_noop.status_code == 409 and context(client, owner)["cash"] == 90


def test_unavailable_and_invalid_requests_never_write(cash_env):
    store, client, owner = cash_env
    for value in [None, "", "abc", True, "Infinity", "NaN", [], {}]:
        response, _ = reconcile(client, owner, value)
        assert response.status_code in (400, 422), (value, response.text)
    malformed, payload = reconcile(client, owner, 100)
    assert malformed.status_code == 200
    invalid_uuid = client.post(path(owner), json={**payload, "request_id": "not-a-uuid"})
    assert invalid_uuid.status_code in (400, 422)
    for name in ["mixed", "future", "unknown"]:
        other = account(store, name)
        if name == "mixed":
            transaction(store, other, currency="EUR")
        elif name == "future":
            transaction(store, other, day=(date.fromisoformat(today()) + timedelta(days=1)).isoformat())
        else:
            with sqlite3.connect(store.path) as connection:
                connection.execute("update accounts set initial_cash = 'unknown' where id = ?", (other["id"],))
        result = context(client, other)
        assert result["available"] is False and result["cash"] is None and result["reason"]
        count = len(store.list_transactions())
        response, _ = reconcile(client, other, 1)
        assert response.status_code == 400, response.text
        assert len(store.list_transactions()) == count


def test_auth_csrf_and_viewer_read_only_permissions(cash_env):
    store, client, owner = cash_env
    anonymous = TestClient(main.app, base_url="https://localhost:6443")
    assert anonymous.get(path(owner)).status_code == 401
    assert anonymous.post(path(owner), json={}).status_code == 401
    revision = context(client, owner)["cash_revision"]
    payload = {"target_cash": 900, "cash_revision": revision, "request_id": str(uuid4())}
    assert client.post(path(owner), json=payload, headers={"X-CSRF-Token": ""}).status_code == 403
    for role in ["Viewer", "Operator"]:
        username = role.lower()
        response = client.post("/api/auth/users", json={"first_name": "QA", "last_name": role,
                                "username": username, "password": "QA-Initial-Password-2026!", "role": role})
        assert response.status_code == 200, response.text
        other = TestClient(main.app, base_url="https://localhost:6443")
        session = _change_password(other, _login(other, username, "QA-Initial-Password-2026!"),
                                   "QA-Initial-Password-2026!", "QA-Replaced-Password-2026!")
        other.headers["X-CSRF-Token"] = session["csrf_token"]
        assert other.get(path(owner)).status_code == 200
        result, _ = reconcile(other, owner, 800)
        assert result.status_code == (403 if role == "Viewer" else 200), result.text
    assert context(client, owner)["cash"] == 800


def test_daily_history_refresh_and_later_delete_preserve_manual_evidence(cash_env):
    store, client, owner = cash_env
    original_buy = security_fixture(store, owner)
    day = date.fromisoformat(today())
    before_day = (day - timedelta(days=1)).isoformat()
    manual_day = (day + timedelta(days=1)).isoformat()
    later_day = (day + timedelta(days=2)).isoformat()
    for snapshot_date, source, value, cash in [(before_day, "daily", 777, 555),
                                              (today(), "daily", 1050, 800),
                                              (manual_day, "manual", 2222, 2000),
                                              (later_day, "daily", 1050, 800)]:
        store.save_account_snapshot({"account_id": owner["id"], "snapshot_date": snapshot_date, "source": source,
                                     "value": value, "cash": cash, "profit": 50, "profit_percent": 25})
    saved = {row["snapshot_date"]: row for row in store.list_account_snapshots({"account_id": owner["id"]})}
    response, _ = reconcile(client, owner, 500)
    assert response.status_code == 200, response.text
    changed = {row["snapshot_date"]: row for row in store.list_account_snapshots({"account_id": owner["id"]})}
    for unchanged in [before_day, manual_day]:
        assert changed[unchanged] == saved[unchanged]
    for derived in [today(), later_day]:
        assert (changed[derived]["value"], changed[derived]["cash"], changed[derived]["profit"]) == (750, 500, 50)
    # Correction replay: deleting the original ordinary BUY recomputes cash,
    # while the independent balance correction and manual statement survive.
    assert store.delete_transaction(original_buy["id"]) is True
    final = {row["snapshot_date"]: row for row in store.list_account_snapshots({"account_id": owner["id"]})}
    assert context(client, owner)["cash"] == 700
    assert final[today()]["cash"] == 700 and final[later_day]["cash"] == 700
    assert final[manual_day] == saved[manual_day]
    # A deleted historical BUY also corrects the prior daily computed snapshot.
    assert final[before_day]["cash"] == 1000


def test_history_refresh_failure_rolls_back_ledger_and_retry_intent(cash_env, monkeypatch):
    store, client, owner = cash_env
    before = context(client, owner)
    original = store._refresh_transaction_snapshots
    def fail_after_insert(connection, changes):
        raise RuntimeError("synthetic history refresh failure")
    monkeypatch.setattr(store, "_refresh_transaction_snapshots", fail_after_insert)
    failed, intent = reconcile(client, owner, 400, revision=before["cash_revision"])
    assert failed.status_code == 500
    assert store.list_transactions() == [] and context(client, owner)["cash"] == 1000
    monkeypatch.setattr(store, "_refresh_transaction_snapshots", original)
    retried = client.post(path(owner), json=intent)
    assert retried.status_code == 200, retried.text
    assert retried.json()["replayed"] is False
    assert context(client, owner)["cash"] == 400 and len(store.list_transactions()) == 1


def test_external_cash_import_cannot_reset_local_adjustment_anchor_or_currency(cash_env):
    store, client, owner = cash_env
    owner = store.save_account({**owner, "account_id": "Synthetic Broker"})
    response, _ = reconcile(client, owner, 600)
    assert response.status_code == 200, response.text
    # The empty external holdings list carries only a read-only imported balance.
    result = store.import_external([], [{"account": "Synthetic Broker", "currency": "USD", "cash": 9000}])
    saved = next(row for row in store.list_accounts() if row["id"] == owner["id"])
    assert saved["initial_cash"] == 1000 and context(client, owner)["cash"] == 600
    assert "local" in str(result).lower() and ("cash" in str(result).lower())
    with pytest.raises(ValueError):
        store.save_account({**saved, "currency": "EUR"})
    assert store.list_accounts()[0]["currency"] == "USD" and context(client, owner)["cash"] == 600


def test_every_signed_cash_consumer_replays_the_same_raw_adjustment(cash_env):
    import json
    from app.risk_history import canonical_inputs
    from app.value_at_risk import build_var
    from test_shared_cash_risk_qa import app_functions
    from test_trade_simulator import run_simulation
    store, client, owner = cash_env
    # Cash-only account makes the VaR input directly auditable without price data.
    response, _ = reconcile(client, owner, -125.5)
    assert response.status_code == 200, response.text
    raw_accounts, raw_transactions = store.list_accounts(), store.list_transactions()
    risk_context = canonical_inputs([], raw_accounts, raw_transactions, {"quotes": []}, "USD")
    assert risk_context["account_ids"] == [owner["id"]]
    assert risk_context["transactions"][0]["action"] == "CASH_OUT"
    result = build_var(store, None, {}, today=date.fromisoformat(today()))
    assert len(result["cash"]) == 1 and result["cash"][0]["amount"] == -125.5
    functions = app_functions("transactionCashImpact", "accountCashBalance", "accountNativeCashBalance", "accountCashValue",
                              "accountRiskCashValue", "portfolioRiskSnapshot", "riskAllocationForItems", "riskAllocationBand", "cleanSourceLabel")
    run_simulation(functions + "\nconst rawAccounts=" + json.dumps(raw_accounts) + ";\nconst rawTransactions=" + json.dumps(raw_transactions) + r''';
const portfolioAccounts=()=>state.localAccounts;
const accountRecordForHolding=h=>state.localAccounts.find(a=>a.id===h.account_id);
const accountHorizonYears=()=>20;
const normalizedAmount=value=>value;
const ctx=simulationContext();ctx.accounts=rawAccounts;ctx.transactions=rawTransactions;
ctx.calculated_at=new Date().toISOString();
state.localAccounts=ctx.accounts;state.localTransactions=ctx.transactions;
const owner=rawAccounts[0];
assert.equal(accountCashBalance(owner),-125.5);
assert.equal(accountNativeCashBalance(owner),-125.5);
assert.equal(accountRiskCashValue(owner),-125.5);
assert.equal(accountCashValue(owner),0); // asset-only helper retains its explicit positive-cash domain
assert.equal(planner.cashBalance(owner,rawTransactions,Date.parse(ctx.calculated_at)),-125.5);
const dashboard=portfolioRiskSnapshot([]);
const simulated=simulator.simulate(ctx,[trade({accountId:owner.id,quantity:1})],adapters);
assert.equal(simulated.status,'ok',JSON.stringify(simulated));
assert.equal(simulated.accounts[0].before.cash,-125.5);
assert.equal(simulated.total.before.cash,-125.5);
assert.equal(simulated.total.before.risk.score,100);
assert.equal(dashboard.total.score,simulated.total.before.risk.score);
assert.equal(dashboard.total.cash_debt,125.5);
''')


def test_two_concurrent_reconciliations_commit_only_one_and_survive_store_restart(cash_env):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.local_portfolio import CashBalanceError
    store, client, owner = cash_env
    revision = context(client, owner)["cash_revision"]
    barrier = Barrier(2)
    def write(target):
        payload = {"target_cash": target, "cash_revision": revision, "request_id": str(uuid4())}
        barrier.wait(timeout=5)
        try:
            result = LocalPortfolioStore(store.path).update_account_cash(owner["id"], payload)
            return 200, result, payload
        except CashBalanceError as error:
            return error.status_code, None, payload
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, [500, 600]))
    assert sorted(result[0] for result in results) == [200, 409]
    successful = next(result for result in results if result[0] == 200)
    expected = successful[2]["target_cash"]
    restarted = LocalPortfolioStore(store.path)
    assert restarted.account_cash_balance(owner["id"])["cash"] == expected
    assert len(restarted.list_transactions()) == 1
    replayed = restarted.update_account_cash(owner["id"], successful[2])
    assert replayed["replayed"] is True and replayed["cash"] == expected
    assert len(restarted.list_transactions()) == 1


def cash_browser_document(tmp_path, language):
    import json
    import re
    from pathlib import Path
    source = (ROOT / "web/app.js").read_text().replace(
        "initializeApp().catch(reportBackgroundError).finally(revealInitializedApp);", "")
    setup = r'''
window.qa={errors:[],calls:[],posts:[],revision:1,cash:800,mode:'ok',refreshes:0};
window.addEventListener('error',event=>qa.errors.push(event.message));
window.addEventListener('unhandledrejection',event=>qa.errors.push(String(event.reason)));
api=async(path,options={})=>{
 qa.calls.push(path);
 if(!path.endsWith('/cash-balance'))return {items:[]};
 const context=()=>({account_id:path.includes('qa-bank')?'qa-bank':'qa-dollar',currency:'USD',cash:path.includes('qa-bank')?0:qa.cash,available:true,reason:'',effective_date:'2026-11-06',cash_revision:'r'+qa.revision});
 if(options.method!=='POST')return context();
 const payload=JSON.parse(options.body);qa.posts.push(payload);
 if(qa.mode==='hold')return await new Promise(resolve=>{qa.resolve=()=>{qa.cash=payload.target_cash;qa.revision++;resolve({...context(),adjusted:true,delta:payload.target_cash-800,request_id:payload.request_id,replayed:false});};});
 if(qa.mode==='network'){qa.mode='ok';throw new Error('Synthetic connection interruption');}
 if(qa.mode==='stale'){qa.cash=900;qa.revision++;const e=new Error('Synthetic stale context');e.status=409;e.reason='cash_revision_conflict';throw e;}
 const old=qa.cash;qa.cash=payload.target_cash;qa.revision++;
 state.localTransactions=[{account_db_id:'qa-dollar',action:'BUY',quantity:10,price:20,currency:'USD',trade_date:'2026-01-01'},
 {account_db_id:'qa-dollar',action:qa.cash>=800?'CASH_IN':'CASH_OUT',quantity:Math.abs(qa.cash-800),price:1,currency:'USD',trade_date:'2026-11-06'}];
 return {...context(),adjusted:old!==qa.cash,delta:qa.cash-old,request_id:payload.request_id,replayed:false};
};
loadLocalAccounts=async()=>{qa.refreshes++;};loadPortfolio=async()=>{qa.refreshes++;};
loadFamilyMembers=async()=>{};loadReports=async()=>{};saveDashboardSettings=()=>{};
appLog=()=>{};appWarn=()=>{};
state.auth.user={id:'qa-owner',username:'qa',role:'Admin'};state.auth.csrfToken='synthetic-csrf';
state.localAccounts=[{id:'qa-dollar',username:'Synthetic Dollar',account_id:'QA1',type:'Investment',location:'USA',currency:'USD',initial_cash:1000,persons:[{name:'Synthetic Owner',birth_date:'01/01/1990'}]}];
state.localTransactions=[{account_db_id:'qa-dollar',action:'BUY',quantity:10,price:20,currency:'USD',trade_date:'2026-01-01'}];
state.baseCurrency='USD';state.fxRates={};state.language=QA_LANGUAGE;state.portfolioReady=true;
document.documentElement.lang=state.language;document.documentElement.dir=state.language==='he'?'rtl':'ltr';
$('authOverlay').hidden=true;$('appShell').inert=false;$('appShell').removeAttribute('aria-hidden');revealInitializedApp();
window.PortfolioI18n.applyToDocument(state.language);
for(const [id,values] of Object.entries({editAccountType:['Investment','Bank'],editAccountLocation:['USA','Israel'],editAccountCurrency:['USD','ILS'],editAccountBroker:[''],editAccountFamilyMember:['']}))$(id).innerHTML=values.map(value=>`<option>${value}</option>`).join('');
$('analyticsBoard').innerHTML='<button id="qa-cash-trigger" data-update-account-cash="qa-dollar" data-cash-entry="dashboard">'+t('Update cash')+'</button>';
qa.ready=true;
'''.replace("QA_LANGUAGE", json.dumps(language))
    (tmp_path / "cash-app.js").write_text(source + "\n" + setup)
    page = (ROOT / "web/index.html").read_text()
    page = re.sub(r'<script src="https://[^\"]+"></script>', '', page)
    for relative in re.findall(r'(?:src|href)="/([^"?]+)(?:\?[^\"]*)?"', page):
        asset = ROOT / "web" / relative
        if not asset.exists():
            continue
        if relative == "app.js":
            asset = tmp_path / "cash-app.js"
        elif relative.endswith(".css"):
            target = tmp_path / Path(relative).name
            target.write_text(re.sub(r'@import\s+url\([^)]*\)\s*;', '', asset.read_text()))
            asset = target
        page = re.sub(r'(["\'])/' + re.escape(relative) + r'(?:\?[^"\']*)?(["\'])',
                      lambda match: match[1] + asset.as_uri() + match[2], page)
    fixture = tmp_path / "cash-browser.html"
    fixture.write_text(page)
    return fixture


def browser_wait(evaluate, expression, expected=True):
    import time
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        actual = evaluate(expression)
        if actual == expected:
            return actual
        time.sleep(.03)
    assert evaluate(expression) == expected, expression


def enter(command):
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})


@pytest.mark.parametrize("width,language", [(390, "en"), (1440, "en"), (390, "he"), (1440, "he")])
def test_inline_cash_balance_native_activation_permissions_and_focus(tmp_path, chromium, width, language):
    """Exercise the actual shared cash renderer with the complete stylesheet."""
    import base64
    fixture = cash_browser_document(tmp_path, language)
    command, evaluate = chromium
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": fixture.as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate("window.qaRenderDashboard=()=>withDashboardToolbar({id:'portfolio_value'},renderPortfolioValueDashboard([]));$('analyticsBoard').innerHTML=qaRenderDashboard();window.qaTrigger=()=>document.querySelector('.account-chip [data-update-account-cash]');qaTrigger().scrollIntoView({block:'center'});")
    current_cash = "Current cash" if language == "en" else "מזומן נוכחי"
    update_cash = "Update cash" if language == "en" else "עדכון מזומן"
    assert evaluate("innerWidth") == width
    trigger = evaluate("""(()=>{const e=qaTrigger(),r=e.getBoundingClientRect(),icon=e.querySelector('svg');
      return {tag:e.tagName,text:e.textContent,label:e.getAttribute('aria-label'),buttons:e.querySelectorAll('button').length,
        left:r.left,right:r.right,height:r.height,icon:!!icon,iconOpacity:icon?getComputedStyle(icon).opacity:null,
        iconDisplay:icon?getComputedStyle(icon).display:null,iconHeight:icon?.getBoundingClientRect().height,
        iconWidth:icon?.getBoundingClientRect().width,chipHeight:e.closest('.account-chip').getBoundingClientRect().height,
        tooltip:e.dataset.tooltip||e.title};})()""")
    assert trigger["tag"] == "BUTTON" and trigger["buttons"] == 0, trigger
    assert current_cash in trigger["text"] and "800.00" in trigger["text"], trigger
    assert update_cash not in trigger["text"], trigger
    assert "Synthetic Dollar" in trigger["label"], trigger
    assert trigger["tooltip"] == update_cash, trigger
    assert trigger["icon"] is False, trigger
    assert trigger["chipHeight"] <= 100, trigger
    assert trigger["left"] >= 0 and trigger["right"] <= width and trigger["height"] >= 28, trigger
    evaluate("qaTrigger().focus({preventScroll:true});")
    assert evaluate("document.activeElement===qaTrigger()&&qaTrigger().matches(':focus')"), evaluate("({active:document.activeElement.outerHTML,focus:document.hasFocus(),disabled:qaTrigger().disabled})")
    browser_wait(evaluate, "getComputedStyle(qaTrigger(),'::after').opacity", "1")
    assert update_cash in evaluate("getComputedStyle(qaTrigger(),'::after').content")
    evaluate("qaTrigger().blur();")
    point = evaluate("(()=>{const r=qaTrigger().getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()")
    command("Input.dispatchMouseEvent", {"type": "mouseMoved", **point})
    browser_wait(evaluate, "getComputedStyle(qaTrigger(),'::after').opacity", "1")
    (tmp_path / f"inline-cash-dashboard-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    command("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 0, "y": 0})
    for balance in [38819.65, 0, -125.5]:
        evaluate(f"state.localAccounts[0].initial_cash={balance}+200;$('analyticsBoard').innerHTML=qaRenderDashboard();qaTrigger().scrollIntoView({{block:'center'}});")
        dimensions = evaluate("""(()=>{const e=qaTrigger(),label=e.querySelector('.account-cash-label').getBoundingClientRect(),
          value=e.querySelector('.account-cash-value').getBoundingClientRect(),r=e.getBoundingClientRect();
          return {top:Math.abs(label.top-value.top),width:r.width,height:r.height,overflow:e.scrollWidth-e.clientWidth,
          left:r.left,right:r.right};})()""")
        assert dimensions["top"] <= 2 and dimensions["width"] <= 250 and dimensions["height"] <= 50, dimensions
        assert dimensions["overflow"] <= 1 and dimensions["left"] >= 0 and dimensions["right"] <= width, dimensions
        if balance == 38819.65:
            (tmp_path / f"inline-cash-large-rest-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
            evaluate("qaTrigger().focus({preventScroll:true});")
            browser_wait(evaluate, "getComputedStyle(qaTrigger(),'::after').opacity", "1")
            (tmp_path / f"inline-cash-large-focus-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    evaluate("state.localAccounts[0].initial_cash=1000;$('analyticsBoard').innerHTML=qaRenderDashboard();qaTrigger().scrollIntoView({block:'center'});")
    # Real key events use the browser's native button behavior, including Space.
    for key, code, virtual, text in [("Enter", "Enter", 13, "\r"), (" ", "Space", 32, " ")]:
        evaluate("qaTrigger().focus({preventScroll:true});")
        command("Input.dispatchKeyEvent", {"type": "keyDown", "key": key, "code": code, "windowsVirtualKeyCode": virtual, "text": text})
        command("Input.dispatchKeyEvent", {"type": "keyUp", "key": key, "code": code, "windowsVirtualKeyCode": virtual})
        browser_wait(evaluate, "!$('accountCashModal').hidden&&!$('accountCashTarget').disabled")
        assert evaluate("document.activeElement.id") == "accountCashTarget"
        evaluate("$('accountCashModal').querySelector('button[data-close]').click();")
        browser_wait(evaluate, "document.activeElement===qaTrigger()")
    assert evaluate("qa.posts.length") == 0
    # Tap the balance text on a touch-capable viewport.
    command("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 1})
    point = evaluate("(()=>{qaTrigger().blur();const r=qaTrigger().querySelector('bdi').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()")
    command("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{**point, "radiusX": 1, "radiusY": 1}]})
    command("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    browser_wait(evaluate, "!$('accountCashModal').hidden&&!$('accountCashTarget').disabled")
    # Simulate the real save's dashboard rerender; focus must find the new node.
    evaluate("loadPortfolio=async()=>{$('analyticsBoard').innerHTML=qaRenderDashboard();};$('accountCashTarget').value='750';$('accountCashTarget').dispatchEvent(new Event('input',{bubbles:true}));$('accountCashSave').click();")
    browser_wait(evaluate, "$('accountCashModal').hidden")
    browser_wait(evaluate, "document.activeElement===qaTrigger()")
    assert evaluate("qa.posts.length") == 1 and evaluate("qa.cash") == 750
    # Shared Accounts and Edit account surfaces use the same full-line control.
    evaluate("openModal('accountsModal');setAccountsTab('existing');renderLocalAccountsList();")
    assert evaluate("$('accountsList').querySelector('[data-update-account-cash]').tagName") == "BUTTON"
    assert current_cash in evaluate("$('accountsList').querySelector('[data-update-account-cash]').textContent")
    evaluate("$('accountsList').querySelector('[data-update-account-cash]').focus();$('accountsList').querySelector('[data-update-account-cash]').click();")
    browser_wait(evaluate, "!$('accountCashModal').hidden&&!$('accountCashTarget').disabled")
    evaluate("$('accountCashModal').querySelector('button[data-close]').click();")
    browser_wait(evaluate, "document.activeElement===$('accountsList').querySelector('[data-update-account-cash]')")
    evaluate("closeModal($('accountsModal'));editLocalAccount('qa-dollar');")
    browser_wait(evaluate, "!$('accountEditModal').hidden")
    assert current_cash in evaluate("$('editAccountCash').querySelector('[data-update-account-cash]').textContent")
    evaluate("$('editAccountCash').querySelector('[data-update-account-cash]').focus();")
    (tmp_path / f"inline-cash-edit-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))
    evaluate("closeModal($('accountEditModal'));state.auth.user.role='Viewer';$('analyticsBoard').innerHTML=qaRenderDashboard();renderLocalAccountsList();renderAccountEditCash(state.localAccounts[0]);")
    for selector in [".account-chip .account-current-cash", "#accountsList .account-current-cash", "#editAccountCash .account-current-cash"]:
        assert current_cash in evaluate(f"document.querySelector({selector!r}).textContent")
        assert evaluate(f"document.querySelector({selector!r}).querySelectorAll('button,[data-update-account-cash],svg').length") == 0
        assert evaluate(f"document.querySelector({selector!r}).matches('button,[data-update-account-cash],[tabindex]')") is False
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("width,language", [(390, "en"), (1440, "en"), (390, "he"), (1440, "he")])
def test_real_cash_form_keyboard_retry_stale_cancel_and_field_layout(tmp_path, chromium, width, language):
    import base64
    fixture = cash_browser_document(tmp_path, language)
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 800, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": fixture.as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    assert evaluate("qa.errors") == []
    assert evaluate("innerWidth") == width
    evaluate("$('qa-cash-trigger').focus();$('qa-cash-trigger').click();")
    browser_wait(evaluate, "!$('accountCashModal').hidden&&!$('accountCashTarget').disabled")
    assert evaluate("$('accountCashTarget').value") == "800"
    assert evaluate("document.activeElement.id") == "accountCashTarget"
    assert evaluate("$('accountCashCurrency').value") == "USD"
    assert evaluate("$('accountCashDate').value") == "06/11/2026"
    layout = evaluate("""(()=>{
      const rect=id=>{const r=$(id).getBoundingClientRect();return {width:r.width,top:r.top,bottom:r.bottom,left:r.left,right:r.right};};
      const save=$('accountCashSave'),cancel=save.parentElement.querySelector('[data-close]');
      const a=save.getBoundingClientRect(),b=cancel.getBoundingClientRect();
      return {card:$('accountCashModal').querySelector('.modal-card').getBoundingClientRect().width,
        amount:rect('accountCashTarget'),currency:rect('accountCashCurrency'),date:rect('accountCashDate'),
        actionTop:Math.abs(a.top-b.top),actionGap:Math.min(Math.abs(a.right-b.left),Math.abs(b.right-a.left))};
    })()""")
    assert layout["card"] <= 560, layout  # Includes the complete shared CSS cascade.
    assert 80 <= layout["currency"]["width"] <= 100, layout
    assert 130 <= layout["date"]["width"] <= 150, layout
    assert 220 <= layout["amount"]["width"] <= 300, layout
    assert layout["actionTop"] <= 2 and layout["actionGap"] <= 12, layout
    if width > 1000:
        assert abs(layout["amount"]["bottom"] - layout["currency"]["bottom"]) <= 2, layout
        assert abs(layout["date"]["bottom"] - layout["currency"]["bottom"]) <= 2, layout
    else:
        assert layout["amount"]["bottom"] < layout["currency"]["top"], layout
    evaluate("$('accountCashTarget').value='';$('accountCashTarget').dispatchEvent(new Event('input',{bubbles:true}));")
    assert evaluate("$('accountCashSave').disabled") is True
    evaluate("$('accountCashModal').querySelector('button[data-close]').click();")
    browser_wait(evaluate, "$('accountCashModal').hidden")
    assert evaluate("qa.posts.length") == 0
    browser_wait(evaluate, "document.activeElement.id", "qa-cash-trigger")
    evaluate("$('qa-cash-trigger').click();")
    browser_wait(evaluate, "!$('accountCashTarget').disabled")
    evaluate("$('accountCashTarget').value='-123456789.12';$('accountCashTarget').dispatchEvent(new Event('input',{bubbles:true}));$('accountCashTarget').focus();qa.mode='network';")
    dimensions = evaluate("(()=>{const e=$('accountCashTarget'),r=e.getBoundingClientRect();return {value:e.value,width:r.width,left:r.left,right:r.right,font:getComputedStyle(e).fontSize,overflow:e.scrollWidth-e.clientWidth};})()")
    assert dimensions["value"] == "-123456789.12" and dimensions["width"] >= 220, dimensions
    assert dimensions["left"] >= 0 and dimensions["right"] <= width and dimensions["overflow"] <= 1, dimensions
    cash_screenshot = command("Page.captureScreenshot", {"format": "png"})
    (tmp_path / f"cash-dialog-{language}-{width}.png").write_bytes(base64.b64decode(cash_screenshot["data"]))
    enter(command)
    browser_wait(evaluate, "qa.posts.length", 1)
    browser_wait(evaluate, "!accountCashSaving()")
    assert evaluate("$('accountCashTarget').readOnly") is True
    assert evaluate("$('accountCashSave').disabled") is False
    assert evaluate("document.activeElement.id") == "accountCashStatus"
    first = evaluate("qa.posts[0]")
    evaluate("$('accountCashSave').click();")
    browser_wait(evaluate, "$('accountCashModal').hidden")
    assert evaluate("qa.posts") == [first, first]
    assert evaluate("qa.cash") == -123456789.12
    browser_wait(evaluate, "document.activeElement.id", "qa-cash-trigger")
    # A changed target is a new intent. Stale responses demand explicit review.
    evaluate("$('qa-cash-trigger').click();")
    browser_wait(evaluate, "!$('accountCashTarget').disabled")
    evaluate("qa.mode='stale';$('accountCashTarget').value='0';$('accountCashTarget').dispatchEvent(new Event('input',{bubbles:true}));$('accountCashTarget').focus();")
    enter(command)
    browser_wait(evaluate, "state.accountCash.needsReview")
    assert evaluate("$('accountCashSave').disabled") is True
    assert evaluate("qa.posts[2].request_id") != first["request_id"]
    assert evaluate("document.activeElement.id") == "accountCashStatus"
    evaluate("qa.mode='ok';$('accountCashReload').click();")
    browser_wait(evaluate, "!state.accountCash.needsReview&&!state.accountCash.loading")
    assert evaluate("$('accountCashTarget').value") == "0"
    assert "900" in evaluate("$('accountCashCurrent').textContent")
    evaluate("$('accountCashTarget').focus();")
    enter(command)
    browser_wait(evaluate, "$('accountCashModal').hidden")
    assert evaluate("qa.posts[3].request_id") != evaluate("qa.posts[2].request_id")
    assert evaluate("qa.cash") == 0
    # While a save is pending, Enter and all close paths cannot duplicate or abandon it.
    evaluate("$('qa-cash-trigger').click();")
    browser_wait(evaluate, "!$('accountCashTarget').disabled")
    evaluate("qa.mode='hold';$('accountCashTarget').value='55';$('accountCashTarget').dispatchEvent(new Event('input',{bubbles:true}));$('accountCashTarget').focus();")
    enter(command)
    browser_wait(evaluate, "accountCashSaving()")
    enter(command)
    assert evaluate("qa.posts.length") == 5
    evaluate("$('accountCashModal').querySelector('button[data-close]').click();")
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
    assert evaluate("$('accountCashModal').hidden") is False
    assert evaluate("qa.posts.length") == 5
    evaluate("returnToDashboard();")
    assert evaluate("$('accountCashModal').hidden") is False
    evaluate("qa.mode='ok';qa.resolve();")
    browser_wait(evaluate, "$('accountCashModal').hidden")
    # Actual edit dialog, populated through its production handler.
    evaluate("editLocalAccount('qa-dollar');")
    browser_wait(evaluate, "!$('accountEditModal').hidden")
    fields = evaluate("['editAccountType','editAccountCurrency','editInitialCash','editUsername','editAccountId','editAccountComments'].map(id=>{const e=$(id),r=e.getBoundingClientRect();return {id,width:r.width,left:r.left,right:r.right};})")
    assert all(field["left"] >= 0 and field["right"] <= width for field in fields), fields
    if width > 1000:
        by_id = {field["id"]: field["width"] for field in fields}
        assert by_id["editUsername"] > by_id["editAccountCurrency"]
        assert by_id["editAccountComments"] > by_id["editAccountCurrency"]
    evaluate("$('editInitialCash').value='-123456789.12';")
    assert evaluate("$('editInitialCash').scrollWidth-$('editInitialCash').clientWidth") <= 1
    actions = evaluate("(()=>{const save=$('saveEditAccount'),cancel=save.parentElement.querySelector('[data-close]'),a=save.getBoundingClientRect(),b=cancel.getBoundingClientRect();return {sameParent:save.parentElement===cancel.parentElement,top:Math.abs(a.top-b.top),gap:Math.min(Math.abs(a.right-b.left),Math.abs(b.right-a.left)),buttons:save.parentElement.querySelectorAll('button').length};})()")
    assert actions["sameParent"] and actions["buttons"] == 2 and actions["top"] <= 2 and actions["gap"] <= 20, actions
    summary = evaluate("({text:$('editAccountCash').textContent,balance:accountNativeCashBalance(state.localAccounts[0]),transactions:state.localTransactions})")
    assert summary["balance"] == 0 and "0.00" in summary["text"], summary
    screenshot = command("Page.captureScreenshot", {"format": "png"})
    (tmp_path / f"cash-edit-{language}-{width}.png").write_bytes(base64.b64decode(screenshot["data"]))
    if language == "he":
        text = evaluate("$('accountCashModal').textContent+$('editAccountCash').textContent")
        for english in ["Current cash", "Update cash", "Save current cash", "Reload current cash", "Cancel", "Adjustment:"]:
            assert english not in text
    evaluate("$('editAccountCash').querySelector('[data-update-account-cash]').focus();$('editAccountCash').querySelector('[data-update-account-cash]').click();")
    browser_wait(evaluate, "!$('accountCashModal').hidden&&!$('accountCashTarget').disabled")
    assert evaluate("$('accountEditModal').inert") is True
    evaluate("$('accountCashModal').querySelector('button[data-close]').click();")
    browser_wait(evaluate, "$('accountCashModal').hidden")
    browser_wait(evaluate, "!$('accountEditModal').inert")
    browser_wait(evaluate, "document.activeElement=== $('editAccountCash').querySelector('[data-update-account-cash]')")
    assert evaluate("qa.posts.length") == 5
    evaluate("closeModal($('accountEditModal'));state.localAccounts.push({id:'qa-bank',username:'Synthetic Zero Bank',type:'Bank',location:'USA',currency:'USD',initial_cash:0,persons:[]});state.items=[];const section=document.createElement('section');section.id='qa-zero-dashboard';section.innerHTML=renderPortfolioValueDashboard([]);$('analyticsBoard').append(section);")
    assert evaluate("!!$('qa-zero-dashboard').querySelector('[data-update-account-cash=qa-bank]')")
    evaluate("$('qa-zero-dashboard').querySelector('[data-update-account-cash=qa-bank]').click();")
    browser_wait(evaluate, "!$('accountCashModal').hidden&&!$('accountCashTarget').disabled")
    assert evaluate("$('accountCashTarget').value") == "0"
    assert evaluate("qa.calls.at(-1)") == "/api/local/accounts/qa-bank/cash-balance"
    evaluate("$('accountCashModal').querySelector('button[data-close]').click();")
    browser_wait(evaluate, "$('accountCashModal').hidden")
    assert evaluate("qa.posts.length") == 5
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("account_type", ["Bank", "Long-Term Savings"])
def test_bank_and_long_term_cash_update_agree_with_reports_and_history(cash_env, account_type):
    import json
    import subprocess
    from test_shared_cash_risk_qa import app_functions
    store, client, owner = cash_env
    owner = store.save_account({**owner, "type": account_type})
    response, _ = reconcile(client, owner, -25)
    assert response.status_code == 200, response.text
    assert store.list_accounts()[0]["initial_cash"] == 1000
    assert store.holdings() == []
    report = store.reports({"account_id": owner["id"]})
    assert report["cash"] == -25 and report["value"] == -25
    points = store.account_trends({"account_id": owner["id"], "from": today(), "to": today()})["accounts"][0]["points"]
    assert points[-1]["cash"] == -25 and points[-1]["profit"] == 0
    functions = app_functions("accountCashBalance", "accountNativeCashBalance", "transactionCashImpact", "renderFundsOverviewDashboard", "longTermAccountSeries")
    yesterday = (date.fromisoformat(today()) - timedelta(days=1)).isoformat()
    script = "const assert=require('node:assert/strict');\n" + functions
    script += "\nconst state=" + json.dumps({"baseCurrency": "USD", "localAccounts": store.list_accounts(), "localTransactions": store.list_transactions(), "items": [], "localFunds": [], "accountTrend": {"accounts": []}}) + ";\n"
    script += "\nconst days=" + json.dumps([yesterday, today()]) + ";\n"
    script += r'''
const sum=values=>values.reduce((a,b)=>a+b,0), normalizedAmount=value=>value,normalizedField=(item,key)=>item.holding[key];
const t=value=>value,esc=value=>String(value),accountLabel=a=>a.username,money=value=>String(value);
const renderPensionDashboardTable=()=>'',trendSeriesForAccount=()=>[],emptyLongTermSeries=days=>Object.fromEntries(days.map(day=>[day,0]));
assert.equal(accountCashBalance(state.localAccounts[0]),-25);
assert.equal(accountNativeCashBalance(state.localAccounts[0]),-25);
assert.equal(accountCashBalance(state.localAccounts[0],days[0]),1000);
assert.equal(accountCashBalance(state.localAccounts[0],days[1]),-25);
if(state.localAccounts[0].type==='Long-Term Savings'){
 assert.deepEqual(longTermAccountSeries(days)[0].values,{[days[0]]:1000,[days[1]]:-25});
 assert.ok(renderFundsOverviewDashboard().includes('<b>-25</b> accountHoldingsCash'));
}
'''
    result = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_native_cash_summary_rejects_cash_dates_and_amounts_without_guessing():
    import subprocess
    from test_shared_cash_risk_qa import app_functions
    script = "const assert=require('node:assert/strict'),state={localTransactions:[]},sum=v=>v.reduce((a,b)=>a+b,0);\n"
    script += app_functions("accountCashBalance", "accountNativeCashBalance", "transactionCashImpact")
    script += r'''
const owner={id:'a',currency:'USD',initial_cash:1000};
const valid={account_db_id:'a',action:'CASH_OUT',quantity:300,price:1,currency:'USD',trade_date:'2026-01-01'};
state.localTransactions=[valid];assert.equal(accountNativeCashBalance(owner),700);
for(const change of [{trade_date:''},{trade_date:'bad'},{trade_date:'2026-02-30'},{trade_date:'2999-01-01'},
 {quantity:-300},{price:-1},{quantity:null},{quantity:Infinity},{currency:'EUR'}]){
 state.localTransactions=[{...valid,...change}];
 assert.equal(accountNativeCashBalance(owner),null,JSON.stringify(change));
}
state.localTransactions=[{...valid,action:'ADD',trade_date:'2999-01-01',currency:'EUR'}];
assert.equal(accountNativeCashBalance(owner),1000); // noncash securities do not establish or corrupt raw cash
state.localTransactions=[{...valid,account_db_id:'another',trade_date:'bad'}];
assert.equal(accountNativeCashBalance(owner),1000);
'''
    result = subprocess.run(["node"], input=script, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_cash_context_load_failure_recovers_and_old_reopen_response_cannot_overwrite(tmp_path, chromium):
    fixture = cash_browser_document(tmp_path, "en")
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 800, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": fixture.as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate("qa.originalApi=api;qa.failGet=true;api=async(path,options={})=>{if(qa.failGet&&options.method!=='POST'){qa.failGet=false;throw new Error('Synthetic load failure');}return qa.originalApi(path,options);};$('qa-cash-trigger').click();")
    browser_wait(evaluate, "!state.accountCash.loading")
    assert evaluate("$('accountCashTarget').disabled") is True
    assert evaluate("$('accountCashReload').disabled") is False
    assert "could not be loaded" in evaluate("$('accountCashStatus').textContent")
    evaluate("$('accountCashReload').click();")
    browser_wait(evaluate, "!$('accountCashTarget').disabled")
    assert evaluate("$('accountCashTarget').value") == "800"
    evaluate("$('accountCashModal').querySelector('button[data-close]').click();")
    browser_wait(evaluate, "$('accountCashModal').hidden")
    evaluate("qa.pending=[];api=async()=>await new Promise(resolve=>qa.pending.push(resolve));$('qa-cash-trigger').click();")
    browser_wait(evaluate, "qa.pending.length", 1)
    evaluate("$('accountCashModal').querySelector('button[data-close]').click();$('qa-cash-trigger').click();")
    browser_wait(evaluate, "qa.pending.length", 2)
    evaluate("qa.pending[1]({account_id:'qa-dollar',currency:'USD',cash:222,available:true,reason:'',effective_date:'2026-11-06',cash_revision:'latest'});")
    browser_wait(evaluate, "!$('accountCashTarget').disabled")
    assert evaluate("$('accountCashTarget').value") == "222"
    evaluate("qa.pending[0]({account_id:'qa-dollar',currency:'USD',cash:111,available:true,reason:'',effective_date:'2026-11-06',cash_revision:'old'});")
    assert evaluate("$('accountCashTarget').value") == "222"
    assert evaluate("state.accountCash.context.cash_revision") == "latest"
    assert evaluate("qa.posts.length") == 0 and evaluate("qa.errors") == []
