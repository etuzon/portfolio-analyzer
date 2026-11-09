"""Real HTTPS/browser/API/SQLite valuation journey with offline synthetic providers.

No scripts, fetches, APIs, or EventSource handlers are replaced in the browser.
The disposable server uses its own configuration, databases, logs and TLS key.
Synthetic USD/ILS=1 makes the ILS dashboard headline directly checkable.
"""
import json
import os
import socket
import ssl
import subprocess
import time
import urllib.request

import pytest

from test_native_account_history_qa import chromium, ROOT


SERVER = r'''
from datetime import date, timedelta
import json, socket, sys
from pathlib import Path
import uvicorn
from app import main
from app.models import Ohlcv
from app.providers import MarketDataHub, SqliteCache

directory, port = Path(sys.argv[1]), int(sys.argv[2])
today = date.today()
control = directory/'provider.json'
class SyntheticProvider:
    name = 'yahoo_finance'
    def check(self):
        if json.loads(control.read_text()).get('failed'):
            raise ConnectionError('synthetic offline provider failure')
    def prices(self, symbol, start, end):
        self.check()
        price = json.loads(control.read_text()).get('price',3.31)
        return [Ohlcv(today,price,price,price,price,price,100)]
    def profile(self, symbol):
        self.check()
        return {'name':'Synthetic LOAN','exchange':'Nasdaq','industry':'Banks','market_cap':100000}
    def fundamentals(self, symbol):
        self.check()
        return {'income_statement':{'annualReports':[{'fiscalDateEnding':'2025-12-31','totalRevenue':200,'netIncome':20}]}}
    def dividends(self, symbol, *args, **kwargs):
        self.check()
        return [{'date':'2025-06-30','amount':1}]
    def fx(self, pair):
        return {'rate':1,'time':today.isoformat()}
provider = SyntheticProvider()
market = MarketDataHub.__new__(MarketDataHub)
market.config = {'primary':'yahoo_finance','fallback':[]}
market.db_config = {}
market.cache = SqliteCache(directory/'market.sqlite3',24)
market.providers = [provider]
market.cache.set_prices('yahoo_finance','LOAN',provider.prices('LOAN',today,today))
for kind in ('profile','fundamentals','dividends'):
    market.cache.set_security_snapshot('yahoo_finance','LOAN',kind,getattr(provider,kind)('LOAN'))
market.cache.set_company_logo('LOAN','NASDAQ',status='missing')
main.hub = lambda:market
main._refresh_portfolio_fx_history = lambda:None
store = main.local_store
owner = store.save_account({'type':'Investment','location':'USA','currency':'USD','username':'Synthetic QA',
    'initial_cash':9309.97,'persons':[{'name':'Synthetic Owner','birth_date':'01/01/1990'}]})
tx = store.add_transaction({'account_db_id':owner['id'],'action':'BUY','symbol':'LOAN','stock_market':'NASDAQ',
    'asset_class':'EQUITY','quantity':900,'price_input':4.27,'currency':'USD','trade_date':(today-timedelta(days=10)).isoformat(),'allow_manual':True})
store.save_price({'symbol':'LOAN','stock_market':'NASDAQ','asset_class':'EQUITY','location':'USA','currency':'USD',
    'price_input':4.22,'price_date':(today-timedelta(days=1)).isoformat()})
store.set_preference('client_state',{'language':'en'})
main.auth_store.initialize()
(directory/'seed.json').write_text(json.dumps({'transaction':tx,'account':owner}))
# Forbid any accidental external network in the server, including logo adapters.
original_connect = socket.socket.connect
def isolated_connect(self, address):
    if isinstance(address,tuple) and address[0] not in ('127.0.0.1','::1','localhost'):
        raise RuntimeError('external network forbidden by synthetic E2E fixture')
    return original_connect(self,address)
socket.socket.connect = isolated_connect
uvicorn.run(main.app,host='127.0.0.1',port=port,lifespan='off',log_level='warning',
    ssl_keyfile=str(directory/'key.pem'),ssl_certfile=str(directory/'cert.pem'))
'''


@pytest.fixture
def live_valuation_server(tmp_path):
    directory = tmp_path/'server'
    directory.mkdir()
    (directory/'provider.json').write_text(json.dumps({'failed':False}))
    config = directory/'config.yaml'
    config.write_text('market_data:\n  primary: yahoo_finance\n  fallback: []\ndashboard:\n  display_currencies: [USD/ILS]\n  banner_items:\n    - {label: USD/ILS, type: fx, symbol: USD/ILS}\n')
    script = directory/'server.py'
    script.write_text(SERVER)
    cert = subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                           '-subj','/CN=localhost','-keyout',str(directory/'key.pem'),'-out',str(directory/'cert.pem')],
                          capture_output=True,text=True)
    assert cert.returncode == 0, cert.stderr
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0))
        port = listener.getsockname()[1]
    server_env = {**os.environ,'DATA_DIR':str(directory),'CONFIG_PATH':str(config),'PYTHONPATH':str(ROOT)}
    output = (directory/'server.log').open('w')
    process = subprocess.Popen([str(ROOT/'.venv/bin/python'),str(script),str(directory),str(port)],
                               cwd=ROOT,env=server_env,stdout=output,stderr=output)
    url = f'https://127.0.0.1:{port}'
    try:
        deadline = time.monotonic()+15
        while time.monotonic()<deadline:
            try:
                with urllib.request.urlopen(url+'/api/health',context=ssl._create_unverified_context(),timeout=.3) as response:
                    if response.status == 200:
                        break
            except Exception:
                if process.poll() is not None:
                    pytest.fail((directory/'server.log').read_text())
                time.sleep(.05)
        else:
            pytest.fail('Disposable HTTPS server did not start: '+(directory/'server.log').read_text())
        yield url,directory
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        output.close()


def test_authenticated_real_dashboard_refresh_reload_edit_and_failure_retry(live_valuation_server,chromium,tmp_path):
    url,directory = live_valuation_server
    command,evaluate = chromium
    command('Security.setIgnoreCertificateErrors',{'ignore':True})
    command('Network.enable')
    command('Network.setBlockedURLs',{'urls':['https://fonts.googleapis.com/*','https://fonts.gstatic.com/*','https://cdn.jsdelivr.net/*','https://cdnjs.cloudflare.com/*']})
    command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
    command('Page.navigate',{'url':url})

    def wait(expression,timeout=15):
        deadline = time.monotonic()+timeout
        last = None
        while time.monotonic()<deadline:
            last = evaluate('Boolean('+expression+')')
            if last:
                return last
            time.sleep(.05)
        pytest.fail(f'Browser condition timed out: {expression}; last={last}; '+str(evaluate('document.body.innerText.slice(0,3000)')))

    def dashboard(value,profit,quantity,total):
        wait(f'document.querySelector("#rows .value-cell strong")?.textContent.includes("{value}")')
        assert quantity in evaluate('document.querySelector("#rows .units-history-link").textContent')
        assert profit in evaluate('document.querySelector("#rows .value-cell b").textContent')
        assert evaluate('document.querySelector("#rows .value-cell b").classList.contains("negative")')
        assert total in evaluate('document.querySelector(".portfolio-summary-value .balance-value").textContent')
        raw = evaluate('(async()=>{const response=await fetch("/api/portfolio");return (await response.json()).items[0].holding;})()')
        expected_value = float(value.replace(',',''))
        expected_basis = 3843 if quantity == '900' else 3416
        assert raw['market_value'] == pytest.approx(expected_value)
        assert raw['cost_basis'] == pytest.approx(expected_basis)
        assert raw['unrealized_profit'] == pytest.approx(expected_value-expected_basis)
        cash = evaluate('(async()=>{const p=await (await fetch("/api/portfolio")).json();const id=p.items[0].holding.account_id;return (await (await fetch(`/api/local/accounts/${id}/cash-balance`)).json()).cash;})()')
        assert cash == pytest.approx(5466.97 if quantity == '900' else 5893.97)
        assert cash + raw['market_value'] == pytest.approx(expected_value + (5466.97 if quantity == '900' else 5893.97))

    def screenshot(name):
        import base64
        (tmp_path/name).write_bytes(base64.b64decode(command('Page.captureScreenshot',{'format':'png'})['data']))

    def refresh():
        evaluate('document.querySelector("#refresh").click()')
        wait('!state.portfolioRefreshPending && document.querySelector("#status").textContent.includes("portfolio positions")')

    wait('document.querySelector("#loginUsername") && typeof signIn === "function"')
    evaluate('document.querySelector("#authLanguage").value="en";document.querySelector("#authLanguage").dispatchEvent(new Event("change",{bubbles:true}));document.querySelector("#loginUsername").value="admin";document.querySelector("#loginPassword").value="admin";document.querySelector("#loginButton").click()')
    wait('document.querySelector("#passwordChangeForm").hidden === false')
    evaluate('document.querySelector("#currentPassword").value="admin";document.querySelector("#newPassword").value="Synthetic-QA-Password-2026!";document.querySelector("#confirmPassword").value="Synthetic-QA-Password-2026!";document.querySelector("#changePasswordSubmit").click()')
    dashboard('2,979','864','900','8,446')
    wait('state.portfolioRefreshPending === false')
    screenshot('valuation-900-summary.png')
    evaluate('document.querySelector("#rows .value-cell").scrollIntoView({block:"center"})')
    screenshot('valuation-900-holding.png')
    evaluate('window.scrollTo(0,0)')
    # The exact displayed 900-share outcome follows browser->real API->real SQLite.
    sources = evaluate('(async()=>{const read=async p=>(await (await fetch(p)).json()).items;return {accounts:await read("/api/local/accounts"),transactions:await read("/api/local/securities"),prices:await read("/api/local/prices")};})()')
    refresh()
    dashboard('2,979','864','900','8,446')
    command('Page.reload',{'ignoreCache':True})
    dashboard('2,979','864','900','8,446')
    after = evaluate('(async()=>{const read=async p=>(await (await fetch(p)).json()).items;return {accounts:await read("/api/local/accounts"),transactions:await read("/api/local/securities"),prices:await read("/api/local/prices")};})()')
    assert after == sources, 'Refresh/reload changed saved ledger, prices or account cash inputs'
    assert '5,466.97' in evaluate('document.querySelector(".portfolio-summary-value .balance-value").title')
    # A newer provider observation changes real visible values after Refresh.
    (directory/'provider.json').write_text(json.dumps({'failed':False,'price':3.50}))
    evaluate('document.querySelector("#refresh").click()')
    dashboard('3,150','693','900','8,617')
    command('Page.reload',{'ignoreCache':True})
    dashboard('3,150','693','900','8,617')
    (directory/'provider.json').write_text(json.dumps({'failed':False,'price':3.31}))
    evaluate('document.querySelector("#refresh").click()')
    dashboard('2,979','864','900','8,446')
    # Edit the real transaction using the production editor and save handler.
    evaluate('document.querySelector("[data-modal=securitiesModal]:not([data-securities-workflow])").click()')
    wait('!document.querySelector("#securitiesModal").hidden')
    wait('document.querySelector("[data-edit-security]")')
    evaluate('document.querySelector("[data-edit-security]").click()')
    wait('document.querySelector("#securityQuantity").value === "900" && !document.querySelector("#transactionEntryModal").hidden && state.transactionEntry.ready')
    evaluate('document.querySelector("#securityQuantity").value="800";document.querySelector("#securityQuantity").dispatchEvent(new Event("input",{bubbles:true}));document.querySelector("#saveSecurity").click()')
    wait('document.querySelector("#transactionEntryModal").hidden')
    dashboard('2,648','768','800','8,542')
    evaluate('document.querySelector("#securitiesModal [data-close]").click()')
    wait('state.portfolioRefreshPending === false')
    # A failed refresh retains the last usable quote and exposes a retry action.
    (directory/'provider.json').write_text(json.dumps({'failed':True}))
    evaluate('document.querySelector("#refresh").click()')
    wait('state.portfolioSourceState === "failed" && !state.portfolioRefreshPending')
    dashboard('2,648','768','800','8,542')
    assert 'Refresh' in evaluate('document.querySelector("#status").textContent')
    (directory/'provider.json').write_text(json.dumps({'failed':False}))
    evaluate('document.querySelector("#refresh").click()')
    wait('state.portfolioSourceState === "ready" && !state.portfolioRefreshPending')
    dashboard('2,648','768','800','8,542')
    command('Page.reload',{'ignoreCache':True})
    dashboard('2,648','768','800','8,542')
    # Save a reviewable visual artifact under pytest's isolated task directory.
    screenshot('valuation-e2e.png')
    evaluate('document.querySelector("#rows .value-cell").scrollIntoView({block:"center"})')
    screenshot('valuation-800-holding.png')
    assert evaluate('innerWidth') == 1440
