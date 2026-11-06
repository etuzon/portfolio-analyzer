"""Independent native/ILS P&L renderer checks against raw saved FX fixtures."""

import base64
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

from test_alarm_priority_qa import CHROME
from test_shared_cash_risk_qa import app_functions


ROOT = Path(__file__).resolve().parents[1]


def run_js(body):
    script = r'''
const assert=require('node:assert/strict');
const window={};
const PortfolioTradePlanner=require('./web/trade-planner.js');
const TRANSLATIONS={en:{},he:{}};
const state={language:'en',baseCurrency:'USD',fxRates:{}};
const sum=values=>values.reduce((a,b)=>a+b,0);
const money=(value,currency,digits=2)=>`${currency} ${value.toFixed(digits)}`;
const fmt=(value,digits=0)=>value.toFixed(digits);
const optionLabel=value=>t(value);
const currencyDisplayLabel=value=>value;
const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const holding=(symbol,amount,currency)=>({holding:{symbol,unrealized_profit:amount,currency}});
const tips=html=>[...html.matchAll(/<g\b[^>]*aria-label="([^"]*)"[^>]*>/g)].map(match=>match[1]);
'''
    script += (ROOT / 'web/i18n.js').read_text()
    script += app_functions('t', 'renderProfitBars') + '\n' + body
    result = subprocess.run(['node'], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_native_ils_base_usd_base_inverse_cross_rates_and_source_immutability():
    run_js(r'''
const items=[holding('USDGAIN',100,'USD'),holding('EURLOSS',-40,'EUR'),holding('NATIVEILS',70,'ILS')];
const original=JSON.stringify(items);
state.fxRates={'USD/ILS':3.5,'EUR/USD':1.25};
let html=renderProfitBars(items),titles=tips(html);
assert.match(html,/Total P\/L USD 70 · Chart currency: USD/);
assert.match(titles.find(x=>x.startsWith('USDGAIN\n')),/Local P\/L: USD 100.00\nConverted to ILS: ILS 350.00/);
assert.match(titles.find(x=>x.startsWith('EURLOSS\n')),/Local P\/L: EUR -40.00\nConverted to ILS: ILS -175.00/);
assert.match(titles.find(x=>x.startsWith('NATIVEILS\n')),/Local P\/L: ILS 70.00\nConverted to ILS: ILS 70.00/);
state.baseCurrency='ILS';state.fxRates={'ILS/USD':1/3.5,'EUR/ILS':4.375};
html=renderProfitBars(items);
assert.match(html,/Total P\/L ILS 245 · Chart currency: ILS/);
assert.match(tips(html).find(x=>x.startsWith('USDGAIN\n')),/ILS 350.00/);
assert.equal(JSON.stringify(items),original);
''')


def test_positive_negative_zero_missing_amount_currency_and_conversion():
    run_js(r'''
state.fxRates={'USD/ILS':3.5};
let html=renderProfitBars([holding('GAIN',10,'USD'),holding('LOSS',-20,'USD'),holding('ZERO',0,'USD')]);
assert.match(html,/Total P\/L USD -10/);
assert.match(tips(html)[0],/^LOSS\n/); // Sort uses the signed base value's magnitude.
assert.equal((html.match(/fill="#ff5f6d"/g)||[]).length,1);
assert.equal((html.match(/fill="#726dff"/g)||[]).length,2);
assert.match(tips(html).find(x=>x.startsWith('ZERO\n')),/USD 0.00\nConverted to ILS: ILS 0.00/);
state.fxRates={};html=renderProfitBars([holding('USD',10,'USD')]);
assert.match(html,/Total P\/L USD 10/);
assert.match(tips(html)[0],/Converted to ILS: Not available/);
for(const bad of [null,undefined,'',NaN,Infinity]){
 html=renderProfitBars([holding('GOOD',10,'USD'),holding('MISSING',bad,'USD')]);
 assert.equal(tips(html).length,1);
 assert.match(html,/Total P\/L Not available/);
 assert.match(html,/Holdings with unavailable P\/L or chart-currency conversion are omitted/);
 assert.ok(!/NaN|Infinity/.test(html));
}
for(const currency of ['',null,'EUR']){
 html=renderProfitBars([holding('UNKNOWN',10,currency)]);
 assert.equal(tips(html).length,0);assert.match(html,/Total P\/L Not available/);
}
for(const rate of [0,-3.5,NaN,Infinity]){
 state.fxRates={'USD/ILS':rate};html=renderProfitBars([holding('USD',10,'USD')]);
 assert.match(tips(html)[0],/Converted to ILS: Not available/);
}
''')


def test_tooltip_and_help_claims_translate_in_both_locales():
    run_js(r'''
state.fxRates={'USD/ILS':3.5};
for(const language of ['he','en','he']){
 state.language=language;const html=renderProfitBars([holding('QA',-12.5,'USD')]);
 const title=tips(html)[0];
 if(language==='he'){
  assert.match(title,/רווח\/הפסד במטבע הנייר: USD -12.50/);
  assert.match(title,/המרה לשקלים: ILS -43.75/);
  assert.ok(!/Local P\/L|Converted to ILS|historical FX/.test(title));
 }else{
  assert.match(title,/Local P\/L: USD -12.50/);
  assert.match(title,/Converted to ILS: ILS -43.75/);
  assert.ok(!/[א-ת]/u.test(title));
 }
 assert.match(html, /role="tooltip"/);
}
''')


@pytest.mark.skipif(not CHROME, reason='Isolated Chromium required')
@pytest.mark.parametrize('width,language', [(390, 'he'), (1440, 'en')])
def test_browser_profit_hover_keyboard_escape_and_redraw_identity(tmp_path, width, language):
    websockets = pytest.importorskip('websockets.sync.client')
    source = (ROOT / 'web/app.js').read_text()
    functions = app_functions('t', 'renderProfitBars', 'showProfitChartTooltip',
                             'hideProfitChartTooltip', 'preserveRenderedInteraction')
    listeners = source[source.index('document.addEventListener("pointerover", showProfitChartTooltip)'):
                       source.index('\nfunction renderRadialRings')]
    setup = r'''
const state={language:'en',baseCurrency:'USD',fxRates:{'USD/ILS':3.5,'EUR/USD':1.25}};
const TRANSLATIONS={en:{},he:{}};
const sum=values=>values.reduce((a,b)=>a+b,0),fmt=n=>String(n);
const money=(n,c,d=2)=>`${c} ${n.toFixed(d)}`;
const optionLabel=v=>t(v),currencyDisplayLabel=v=>v;
const esc=v=>String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const items=[{holding:{symbol:'FIRST',account_id:'qa',stock_market:'NASDAQ',currency:'USD',unrealized_profit:100}},
 {holding:{symbol:'SECOND',account_id:'qa',stock_market:'NASDAQ',currency:'EUR',unrealized_profit:-40}}];
function redraw(){const board=document.getElementById('board');const restore=preserveRenderedInteraction(board);board.innerHTML=renderProfitBars(items);restore();}
'''
    script = (ROOT / 'web/i18n.js').read_text() + '\n' + (ROOT / 'web/trade-planner.js').read_text()
    script += '\n' + setup + '\n' + functions + '\n' + listeners
    script += '\nstate.language=' + json.dumps(language) + ';redraw();window.PortfolioI18n.applyToDocument(state.language);window.PortfolioI18n.observe();'
    css = re.sub(r'@import\s+url\("[^"]+"\);', '', (ROOT / 'web/styles.css').read_text())
    (tmp_path / 'styles.css').write_text(css)
    fixture = tmp_path / 'profit.html'
    fixture.write_text('<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="styles.css"><main id="board" style="margin:24px;max-width:650px"></main><script>' + script + '</script>')
    process = subprocess.Popen([CHROME, '--headless', '--no-sandbox', '--disable-gpu',
        f'--user-data-dir={tmp_path / "chrome"}', '--remote-debugging-port=0', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        port_file = tmp_path / 'chrome/DevToolsActivePort'
        deadline = time.monotonic() + 10
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert port_file.exists()
        port = port_file.read_text().splitlines()[0]
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list') as response:
            target = next(page for page in json.load(response) if page['type'] == 'page')
        with websockets.connect(target['webSocketDebuggerUrl']) as socket:
            command_id = 0

            def command(method, params):
                nonlocal command_id
                command_id += 1
                socket.send(json.dumps({'id': command_id, 'method': method, 'params': params}))
                while True:
                    result = json.loads(socket.recv(timeout=10))
                    if result.get('id') == command_id:
                        assert 'error' not in result, result
                        return result['result']

            def evaluate(expression):
                result = command('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                assert 'exceptionDetails' not in result, result
                return result['result'].get('value')

            def key(value):
                command('Input.dispatchKeyEvent', {'type':'keyDown','key':value,'code':value,
                    'windowsVirtualKeyCode':{'Tab':9,'Escape':27}[value]})
                command('Input.dispatchKeyEvent', {'type':'keyUp','key':value,'code':value})

            command('Emulation.setDeviceMetricsOverride', {'width':width,'height':700,'deviceScaleFactor':1,'mobile':False})
            command('Page.navigate', {'url':fixture.as_uri()})
            deadline = time.monotonic() + 10
            while not evaluate("document.querySelectorAll('[data-profit-holding-key]').length===2") and time.monotonic() < deadline:
                time.sleep(.05)
            key('Tab');key('Tab')
            assert 'SECOND' in evaluate('document.activeElement.getAttribute("aria-label")')
            assert evaluate('document.getElementById("profitChartTooltip").hidden') is False
            text = evaluate('document.getElementById("profitChartTooltip").textContent')
            assert 'EUR -40.00' in text and 'ILS -175.00' in text
            identity = evaluate('document.activeElement.dataset.profitHoldingKey')
            evaluate('items[0].holding.unrealized_profit=1;redraw()')
            assert evaluate('document.activeElement.dataset.profitHoldingKey') == identity
            assert evaluate('document.getElementById("profitChartTooltip").hidden') is False
            if language == 'he':
                assert not re.search(r'Gain|Loss|Unrealized', evaluate('document.querySelector(".chart-header").textContent'))
            key('Escape')
            assert evaluate('document.getElementById("profitChartTooltip").hidden') is True
            point = evaluate("(()=>{const r=document.activeElement.querySelector('rect').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
            command('Input.dispatchMouseEvent', {'type':'mouseMoved',**point})
            assert evaluate('document.getElementById("profitChartTooltip").hidden') is False
            assert evaluate('document.documentElement.scrollWidth<=innerWidth') is True
            artifacts=Path('/tmp/alarm-priority-qa');artifacts.mkdir(exist_ok=True)
            (artifacts / f'profit-tooltip-{width}-{language}.png').write_bytes(base64.b64decode(command('Page.captureScreenshot', {'format':'png'})['data']))
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill();process.wait(timeout=5)
