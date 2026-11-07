"""Independent synthetic evidence for account-currency history and cash labels.

Browser fixtures use the real page and scripts in disposable Chromium profiles;
they neither access runtime portfolio state nor attach to a user's browser.
"""

import base64
import json
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

from app.local_portfolio import LocalPortfolioStore
from test_shared_cash_risk_qa import app_functions


ROOT = Path(__file__).resolve().parents[1]
CHROME = shutil.which("google-chrome") or shutil.which("chromium")


def account(store, name="Dollar", currency="USD", initial_cash=1000):
    return store.save_account({"type": "Investment", "location": "USA", "currency": currency,
                               "username": name, "initial_cash": initial_cash,
                               "persons": [{"name": "Synthetic Owner", "birth_date": "01/01/1990"}]})


def transaction(store, owner, action="BUY", currency="USD", quantity=10,
                price=20, day="2026-01-01", symbol="QA"):
    return store.add_transaction({"account_db_id": owner["id"], "action": action,
                                  "symbol": symbol, "stock_market": "NYSE", "asset_class": "EQUITY",
                                  "currency": currency, "quantity": quantity, "price_input": price,
                                  "trade_date": day, "allow_manual": True})


def trend(store, owner, start="2026-01-01", end="2026-01-10"):
    return store.account_trends({"account_id": owner["id"], "from": start, "to": end})["accounts"][0]["points"]


def test_computed_native_history_uses_account_units_and_keeps_existing_arithmetic(tmp_path):
    store = LocalPortfolioStore(tmp_path / "qa.sqlite")
    owner = account(store)
    transaction(store, owner)
    store.save_price({"symbol": "QA", "stock_market": "NYSE", "asset_class": "EQUITY",
                      "location": "USA", "currency": "USD", "price_input": 25, "price_date": "2026-01-10"})
    points = trend(store, owner)
    assert points[-1]["value"] == 1050  # 1000 - 10*20 + 10*25
    assert points[-1]["cash"] == 800
    assert points[-1]["profit"] == 50
    assert points[-1]["profit_percent"] == 25
    assert all(p["native_currency"] == "USD" and p["native_available"] for p in points)
    assert all(p["native_provenance"] == "computed_single_currency" for p in points)


def test_nonzero_foreign_transactions_disable_native_since_trade_even_after_close(tmp_path):
    store = LocalPortfolioStore(tmp_path / "qa.sqlite")
    owner = account(store)
    transaction(store, owner, quantity=1, currency="EUR", day="2026-01-03")
    transaction(store, owner, action="SELL", quantity=1, currency="EUR", day="2026-01-05")
    points = trend(store, owner)
    assert points[0]["native_available"] is True
    assert all(not p["native_available"] for p in points[1:])
    assert all(p["native_unavailable_reason"] == "mixed_transaction_currencies" for p in points[1:])


def test_tiny_nonzero_foreign_quantity_can_move_material_cash(tmp_path):
    store = LocalPortfolioStore(tmp_path / "qa.sqlite")
    owner = account(store)
    transaction(store, owner, quantity=1e-10, price=1e12, currency="EUR", day="2026-01-03")
    points = trend(store, owner)
    assert points[-1]["cash"] == 900
    assert points[-1]["native_available"] is False


def test_manual_and_daily_snapshot_provenance_and_forward_filled_flags(tmp_path):
    store = LocalPortfolioStore(tmp_path / "qa.sqlite")
    owner = account(store)
    transaction(store, owner, quantity=1, currency="EUR", day="2026-01-02")
    for day, source, value in [("2026-01-03", "daily", 1010), ("2026-01-05", "manual", 1050),
                               ("2026-01-07", "manual", 1250)]:
        store.save_account_snapshot({"account_id": owner["id"], "snapshot_date": day,
                                     "source": source, "value": value, "cash": value - 250,
                                     "profit": 50, "profit_percent": 25})
    other = account(store, "Other")
    store.save_account_snapshot({"account_id": other["id"], "snapshot_date": "2026-01-04",
                                 "value": 20, "cash": 20, "profit": 0})
    result = store.account_trends({"from": "2026-01-01", "to": "2026-01-10"})
    points = {p["date"]: p for entry in result["accounts"] if entry["account"]["id"] == owner["id"] for p in entry["points"]}
    assert points["2026-01-03"]["native_available"] is False
    assert points["2026-01-04"]["native_available"] is False
    assert points["2026-01-04"]["native_unavailable_reason"] == "mixed_transaction_currencies"
    for day in ["2026-01-05", "2026-01-07"]:
        assert points[day]["native_available"] is True
        assert points[day]["native_provenance"] == "recorded_account_currency"
        assert points[day]["profit"] == 50  # 200 external balance movement is not 200 additional P/L
    assert points["2026-01-07"]["value"] - points["2026-01-05"]["value"] == 200
    assert points["2026-01-10"]["native_available"] is False


def test_native_groups_gaps_and_fx_invariance_from_raw_numbers():
    script = "const assert=require('node:assert/strict');\n"
    script += "const state={baseCurrency:'ILS',fxRates:{'USD/ILS':4}};const t=x=>x;\n"
    script += app_functions("sum", "addCurrencyAmount", "reportAmount", "historyCurrencyOptions", "historyCurrencySelection",
                            "historyPointAmount", "historyLinePath", "trendSeriesForAccount", "aggregateTrendAccounts")
    script += r'''
const point=(date,value,valid=true)=>({date,value,cash:20,profit:5,native_currency:'USD',native_available:valid});
const a={account:{id:'a',currency:'USD'},points:[point('2026-01-01',100),point('2026-01-02',110,false),point('2026-01-03',120)]};
const b={account:{id:'b',currency:'USD'},points:[point('2026-01-01',200),point('2026-01-02',210),point('2026-01-03',220)]};
const c={account:{id:'c',currency:'ILS'},points:[{...point('2026-01-01',10000),native_currency:'ILS'}]};
assert.equal(historyCurrencySelection([a],'').mode,'native:USD');
assert.equal(historyCurrencySelection([a,b,c],'').mode,'base');
const group=historyCurrencySelection([a,b,c],'native:USD');
assert.deepEqual(group.accounts.map(e=>e.account.id),['a','b']);
assert.equal(group.currency,'USD');
const native=aggregateTrendAccounts(group.accounts,group.mode);
assert.deepEqual(native.map(p=>p.value),[300,null,340]);
assert.deepEqual(aggregateTrendAccounts([a,b,c],'native:USD').map(p=>p.value),[300,null,340]);
assert.equal((historyLinePath(native,(p,i)=>i,v=>v).match(/M /g)||[]).length,2);
assert.equal((historyLinePath(native,(p,i)=>i,v=>v).match(/L /g)||[]).length,0);
assert.deepEqual(trendSeriesForAccount(a,'native:USD').map(p=>p.value),[100,null,120]);
state.fxRates={'USD/ILS':5};
assert.deepEqual(aggregateTrendAccounts(group.accounts,group.mode).map(p=>p.value),[300,null,340]);
assert.deepEqual(trendSeriesForAccount(a,'base').map(p=>p.value),[500,550,600]);
state.baseCurrency='USD';state.fxRates={};
assert.deepEqual(aggregateTrendAccounts(group.accounts,group.mode).map(p=>p.value),[300,null,340]);
for(const raw of [null,undefined,'',NaN,Infinity]) assert.equal(historyPointAmount({...a.points[0],value:raw},'value','USD','native:USD'),null);
assert.equal(historyPointAmount({...a.points[0],value:0},'value','USD','native:USD'),0);
assert.equal(historyPointAmount(a.points[0],'value','EUR','native:EUR'),null);
'''
    result = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_native_cash_keeps_signed_zero_and_rejects_unknown_or_mixed_units():
    script = "const assert=require('node:assert/strict');const state={localTransactions:[]};\n"
    script += app_functions("sum", "transactionCashImpact", "accountCashBalance", "accountNativeCashBalance")
    script += r'''
const a={id:'a',currency:'USD',initial_cash:0};
assert.equal(accountNativeCashBalance(a),0);
assert.equal(accountNativeCashBalance({...a,initial_cash:-123.45}),-123.45);
for(const initial_cash of [undefined,null,'',false,NaN,Infinity]) assert.equal(accountNativeCashBalance({...a,initial_cash}),null);
assert.equal(accountNativeCashBalance({...a,currency:''}),null);
state.localTransactions=[{account_db_id:'a',action:'BUY',quantity:1,price:100,currency:'USD',trade_date:'2026-01-01'}];
assert.equal(accountNativeCashBalance(a),-100);
state.localTransactions[0].currency='ILS';
assert.equal(accountNativeCashBalance(a),null);
state.localTransactions.push({account_db_id:'a',action:'SELL',quantity:1,price:100,currency:'ILS',trade_date:'2026-01-01'});
assert.equal(accountNativeCashBalance(a),null); // closing does not repair unknown conversion evidence
state.localTransactions=[{account_db_id:'a',action:'BUY',quantity:1e-10,price:1e12,currency:'EUR',trade_date:'2026-01-01'}];
assert.equal(accountNativeCashBalance(a),null);
state.localTransactions=[{account_db_id:'a',action:'ADD',quantity:1,price:100,currency:'EUR'}];
assert.equal(accountNativeCashBalance(a),0); // foreign noncash holdings do not change raw account cash
state.localTransactions=[{account_db_id:'a',action:'BUY',quantity:0,price:100,currency:'EUR'}];
assert.equal(accountNativeCashBalance(a),0);
'''
    result = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def browser_document(tmp_path, language):
    source = (ROOT / "web/app.js").read_text().replace(
        "initializeApp().catch(reportBackgroundError).finally(revealInitializedApp);", "")
    setup = r'''
window.qa={errors:[],calls:[]};
window.addEventListener('error',event=>qa.errors.push(event.message));
window.addEventListener('unhandledrejection',event=>qa.errors.push(String(event.reason)));
api=async(path)=>{qa.calls.push(path);return {items:[]};};
saveDashboardSettings=()=>{};appLog=()=>{};appWarn=()=>{};
loadLocalAccounts=async()=>{};loadFamilyMembers=async()=>{};loadReports=async()=>{};
state.auth.user={id:'qa',username:'qa',role:'admin'};
state.baseCurrency='ILS';state.fxRates={'USD/ILS':4};state.portfolioReady=true;
state.dashboard=defaultDashboard();state.dashboard.accountTrendAccountId='usd';state.dashboard.accountTrendCurrencyMode='';
state.localAccounts=[
 {id:'usd',username:'Dollar <img src=x onerror=alert(1)> "quoted"',type:'Investment',currency:'USD',initial_cash:1000,persons:[]},
 {id:'zero',username:'Zero',type:'Investment',currency:'ILS',initial_cash:0,persons:[]},
 {id:'debt',username:'Debt',type:'Investment',currency:'USD',initial_cash:-123.45,persons:[]},
 {id:'missing',username:'Unknown',type:'Investment',currency:'USD',persons:[]},
 {id:'mixed',username:'Mixed',type:'Investment',currency:'USD',initial_cash:1000,persons:[]},
 {id:'esop',username:'ESOP excluded',type:'ESOP',currency:'USD',initial_cash:555,persons:[]}
];
state.localTransactions=[
 {account_db_id:'usd',action:'BUY',quantity:10,price:20,currency:'USD',trade_date:'2026-01-01'},
 {account_db_id:'mixed',action:'BUY',quantity:1,price:100,currency:'ILS',trade_date:'2026-01-01'},
 {account_db_id:'mixed',action:'SELL',quantity:1,price:100,currency:'ILS',trade_date:'2026-01-01'}
];
const qp=(date,value,cash,valid=true,currency='USD')=>({date,value,cash,profit:50,profit_percent:25,native_currency:currency,native_available:valid});
state.accountTrend={accounts:[
 {account:state.localAccounts[0],points:[qp('2026-01-01',1050,800),qp('2026-01-02',1150,900,false),qp('2026-01-03',1250,1000)]},
 {account:{id:'usd2',username:'Second dollar',currency:'USD'},points:[qp('2026-01-01',200,100),qp('2026-01-02',210,110),qp('2026-01-03',220,120)]},
 {account:state.localAccounts[1],points:[qp('2026-01-01',10000,9000,true,'ILS'),qp('2026-01-02',10100,9100,true,'ILS'),qp('2026-01-03',10200,9200,true,'ILS')]}
]};
state.language=QA_LANGUAGE;
document.documentElement.lang=state.language;document.documentElement.dir=state.language==='he'?'rtl':'ltr';
$('authOverlay').hidden=true;$('appShell').inert=false;$('appShell').removeAttribute('aria-hidden');revealInitializedApp();
window.PortfolioI18n.applyToDocument(state.language);
const board=$('analyticsBoard');
board.innerHTML=withDashboardToolbar({id:'account_trend',view:'basic'},renderAccountValueTrend());
observeDashboardLayout(board);
board.before(Object.assign(document.createElement('div'),{style:'height:700px'}));
board.after(Object.assign(document.createElement('div'),{style:'height:1500px'}));
const value=document.createElement('section');value.id='qa-value';value.innerHTML=renderPortfolioValueDashboard([]);board.after(value);
window.PortfolioI18n.applyToDocument(state.language);
qa.ready=true;
'''.replace("QA_LANGUAGE", json.dumps(language))
    (tmp_path / "app.js").write_text(source + "\n" + setup)
    page = (ROOT / "web/index.html").read_text()
    page = re.sub(r'<script src="https://[^\"]+"></script>', '', page)
    for relative in re.findall(r'(?:src|href)="/([^"?]+)(?:\?[^\"]*)?"', page):
        asset = ROOT / "web" / relative
        if not asset.exists():
            continue
        if relative == "app.js":
            asset = tmp_path / "app.js"
        elif relative.endswith(".css"):
            target = tmp_path / Path(relative).name
            target.write_text(re.sub(r'@import\s+url\([^;]+;', '', asset.read_text()))
            asset = target
        page = re.sub(r'(["\'])/' + re.escape(relative) + r'(?:\?[^"\']*)?(["\'])',
                      lambda match: match[1] + asset.as_uri() + match[2], page)
    fixture = tmp_path / "native-history.html"
    fixture.write_text(page)
    return fixture


@pytest.fixture
def chromium(tmp_path):
    if not CHROME:
        pytest.skip("Isolated Chromium required")
    websockets = pytest.importorskip("websockets.sync.client")
    profile = tmp_path / "isolated-chromium"
    process = subprocess.Popen([CHROME, "--headless", "--no-sandbox", "--disable-gpu",
                                f"--user-data-dir={profile}", "--remote-debugging-port=0", "about:blank"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        port_file = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 10
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert port_file.exists(), "Disposable Chromium failed to start"
        port = port_file.read_text().splitlines()[0]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list") as response:
            target = next(item for item in json.load(response) if item["type"] == "page")
        with websockets.connect(target["webSocketDebuggerUrl"]) as socket:
            command_id = 0

            def command(method, params=None):
                nonlocal command_id
                command_id += 1
                socket.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
                while True:
                    message = json.loads(socket.recv(timeout=10))
                    if message.get("id") == command_id:
                        assert "error" not in message, message
                        return message["result"]

            def evaluate(expression):
                response = command("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
                assert "exceptionDetails" not in response, response
                return response["result"].get("value")

            yield command, evaluate
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.parametrize("language", ["en", "he"])
def test_portfolio_value_tooltip_lists_only_investment_accounts_without_changing_totals(tmp_path, chromium, language):
    command, evaluate = chromium
    command("Page.navigate", {"url": browser_document(tmp_path, language).as_uri()})
    deadline = time.monotonic() + 15
    while not evaluate("window.qa?.ready || window.qa?.errors?.length") and time.monotonic() < deadline:
        time.sleep(.05)
    assert evaluate("qa.errors") == []
    evaluate('''
state.localTransactions=[];
state.localAccounts=[
 {id:'invest',username:'Investment primary',type:'Investment',currency:'USD',initial_cash:1000,persons:[]},
 {id:'zero',username:'Investment zero',type:'Investment',currency:'ILS',initial_cash:0,persons:[]},
 {id:'negative',username:'Investment debt',type:'Investment',currency:'USD',initial_cash:-100,persons:[]},
 {id:'unknown',username:'Investment unknown',type:'Investment',currency:'USD',persons:[]},
 {id:'bank',username:'Excluded bank',type:'Bank',currency:'ILS',initial_cash:200,persons:[]},
 {id:'savings',username:'Excluded savings',type:'Long-Term Savings',currency:'USD',initial_cash:50,persons:[]},
 {id:'untyped',username:'Excluded untyped',type:'',currency:'ILS',initial_cash:25,persons:[]},
 {id:'employee',username:'Excluded employee',type:'ESOP',currency:'USD',initial_cash:9000,persons:[]}
];
$('qa-value').innerHTML=renderPortfolioValueDashboard([]);
''')
    tooltip = evaluate("$('qa-value').querySelector('.balance-value').title")
    for account in ["Investment primary", "Investment zero", "Investment debt", "Investment unknown"]:
        assert account in tooltip
    for account in ["Excluded bank", "Excluded savings", "Excluded untyped", "Excluded employee"]:
        assert account not in tooltip
    # Existing full non-ESOP cash = (1000 - 100 + 50) USD * 4 + 200 + 25 ILS.
    assert "4,025" in evaluate("$('qa-value').querySelector('.balance-value').textContent")
    assert all("4,025" in line for line in [tooltip.splitlines()[0], tooltip.splitlines()[2]])
    assert "0.00" in tooltip and re.search(r"-[^\d\n]*100\.00", tooltip)
    assert ("Not available" if language == "en" else "לא זמין") in tooltip
    assert evaluate("$('qa-value').querySelector('.balance-value').getAttribute('aria-label')") == tooltip
    # Once the final Investment account disappears, the account section disappears too.
    evaluate("state.localAccounts=state.localAccounts.filter(a=>a.type!=='Investment');$('qa-value').innerHTML=renderPortfolioValueDashboard([]);")
    tooltip = evaluate("$('qa-value').querySelector('.balance-value').title")
    assert ("Cash by account" if language == "en" else "מזומן לפי חשבון") not in tooltip
    assert "425" in evaluate("$('qa-value').querySelector('.balance-value').textContent")
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("width,language", [(390, "en"), (1440, "en"), (390, "he"), (1440, "he")])
def test_history_currency_browser_interaction_and_native_cash_tooltip(tmp_path, chromium, width, language):
    fixture = browser_document(tmp_path, language)
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 700, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": fixture.as_uri()})
    deadline = time.monotonic() + 15
    while not evaluate("window.qa?.ready || window.qa?.errors?.length") and time.monotonic() < deadline:
        time.sleep(.05)
    assert evaluate("window.qa?.errors") == []
    assert evaluate("qa.ready") is True
    assert evaluate("innerWidth") == width
    assert evaluate("$('dashboardAccountTrendCurrency').value") == "native:USD"
    assert evaluate("document.querySelector('[data-widget=account_trend] svg').getAttribute('aria-label')").endswith("USD")
    assert evaluate("document.querySelectorAll('[data-widget=account_trend] .account-trend-controls select').length") == 2
    assert evaluate("document.querySelector('[data-widget=account_trend] .chart-subtitle').textContent").count("1,250") == 1
    # Real keyboard selection runs the production delegated change handler.
    before = evaluate("(()=>{const e=$('dashboardAccountTrendCurrency');e.scrollIntoView({block:'center'});e.focus({preventScroll:true});return {y:scrollY,calls:qa.calls.length};})()")
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "End", "code": "End", "windowsVirtualKeyCode": 35})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "End", "code": "End", "windowsVirtualKeyCode": 35})
    assert evaluate("$('dashboardAccountTrendCurrency').value") == "base"
    assert evaluate("document.activeElement.id") == "dashboardAccountTrendCurrency"
    assert abs(evaluate("scrollY") - before["y"]) <= 1
    assert evaluate("qa.calls.length") == before["calls"]
    assert evaluate("document.querySelector('[data-widget=account_trend] svg').getAttribute('aria-label')").endswith("ILS")
    evaluate("$('dashboardAccountTrendCurrency').value='native:USD';$('dashboardAccountTrendCurrency').dispatchEvent(new Event('change',{bubbles:true}));")
    assert evaluate("selectedTrendPoints().map(p=>p.value)") == [1050, None, 1250]
    evaluate("$('dashboardAccountTrendAccount').value='total';$('dashboardAccountTrendAccount').dispatchEvent(new Event('change',{bubbles:true}));$('dashboardAccountTrendCurrency').value='native:USD';$('dashboardAccountTrendCurrency').dispatchEvent(new Event('change',{bubbles:true}));")
    assert evaluate("selectedTrendPoints().map(p=>p.value)") == [1250, None, 1470]
    assert evaluate("document.querySelector('[data-widget=account_trend] .chart-subtitle').textContent").count("1,470") == 1
    controls = evaluate("[...document.querySelectorAll('.account-trend-controls select')].map(e=>{const r=e.getBoundingClientRect();return {width:r.width,left:r.left,right:r.right};})")
    assert all(r["width"] > 120 and r["left"] >= 0 and r["right"] <= width for r in controls), controls
    tooltip = evaluate("document.querySelector('#qa-value .balance-value').title")
    assert 'Dollar <img src=x onerror=alert(1)> "quoted"' in tooltip
    assert evaluate("document.querySelectorAll('#qa-value img[src=x]').length") == 0
    assert "800.00" in tooltip and re.search(r"-[^\d\n]*123\.45", tooltip) and "0.00" in tooltip
    unavailable = "Not available" if language == "en" else "לא זמין"
    assert re.search((r"Unknown" if language == "en" else "לא ידוע") + r"[^\n]*" + unavailable, tooltip)
    assert re.search((r"Mixed" if language == "en" else "מעורב") + r"[^\n]*" + unavailable, tooltip)
    assert "ESOP excluded" not in tooltip
    assert ("Cash by account" if language == "en" else "מזומן לפי חשבון") in tooltip
    assert evaluate("document.querySelector('#qa-value .balance-value').getAttribute('aria-label')") == tooltip
    screenshot = command("Page.captureScreenshot", {"format": "png"})
    (tmp_path / "dashboard-native-history.png").write_bytes(base64.b64decode(screenshot["data"]))
    # Reports use the same currency model, with explicit recorded P/L amount.
    evaluate("openModal('reportsModal');renderAccountTrend({accounts:[state.accountTrend.accounts[0]]});")
    assert evaluate("$('reportHistoryCurrency').value") == "native:USD"
    evaluate("document.querySelector('[data-report-metric=profit]').click();")
    assert evaluate("document.querySelector('[data-report-metric=profit]').getAttribute('aria-pressed')") == "true"
    contrast = evaluate(r'''(()=>{
 const style=getComputedStyle(document.querySelector('[data-report-metric=profit]'));
 const light=color=>{const rgb=color.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]};
 const a=light(style.color),b=light(style.backgroundColor);
 return {ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),color:style.color,background:style.backgroundColor};
})()''')
    assert contrast["ratio"] >= 4.5, contrast
    assert evaluate("$('accountTrendChart').querySelectorAll('circle title').length") == 2
    assert evaluate("[...$('accountTrendChart').querySelectorAll('circle title')].map(e=>e.textContent).every(t=>t.includes('50.00'))")
    before_report = evaluate("(()=>{const e=$('reportHistoryCurrency');e.scrollIntoView({block:'center'});e.focus({preventScroll:true});const m=e.closest('.modal-card');return {scroll:m.scrollTop,calls:qa.calls.length};})()")
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "End", "code": "End", "windowsVirtualKeyCode": 35})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "End", "code": "End", "windowsVirtualKeyCode": 35})
    assert evaluate("$('reportHistoryCurrency').value") == "base"
    assert evaluate("document.activeElement.id") == "reportHistoryCurrency"
    assert abs(evaluate("$('reportHistoryCurrency').closest('.modal-card').scrollTop") - before_report["scroll"]) <= 1
    assert evaluate("qa.calls.length") == before_report["calls"]
    assert evaluate("$('accountTrendChart').querySelectorAll('circle title').length") == 3
    assert evaluate("[...$('accountTrendChart').querySelectorAll('circle title')].map(e=>e.textContent).every(t=>t.includes('200.00'))")
    assert evaluate("$('accountTrendChart').textContent.includes('01/01/2026')")
    evaluate("renderAccountTrend(state.accountTrend);$('reportHistoryCurrency').value='native:USD';$('reportHistoryCurrency').dispatchEvent(new Event('change',{bubbles:true}));")
    assert evaluate("$('accountTrendChart').querySelectorAll('.report-trend-account').length") == 2
    assert evaluate("$('accountTrendChart').querySelectorAll('circle title').length") == 5
    assert evaluate("[...$('accountTrendChart').querySelectorAll('path')].some(e=>(e.getAttribute('d').match(/M /g)||[]).length===2)")
    screenshot = command("Page.captureScreenshot", {"format": "png"})
    (tmp_path / "report-native-history.png").write_bytes(base64.b64decode(screenshot["data"]))
    if language == "he":
        text = evaluate("document.querySelector('[data-widget=account_trend]').textContent + $('accountTrendChart').textContent")
        for phrase in ["Currency display", "Recorded P/L", "Account value trend", "Not available", "Dashboard currency"]:
            assert phrase not in text
    assert evaluate("qa.errors") == []
