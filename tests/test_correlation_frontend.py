import json
from html.parser import HTMLParser
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    script = r'''
const assert = require('node:assert/strict');
const window = {};
''' + (ROOT / "web/i18n.js").read_text() + r'''
const state = {language:'en'};
const t = text => window.PortfolioI18n.translate(text, state.language);
const esc = value => String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const fmt = value => Number(value).toFixed(2);
const formatDate = value => value.split('-').reverse().join('/');
const currencyDisplayLabel = value => value;
const accountLabel = row => row.account_id;
const nodes = {};
for (const id of ['correlationAccount','correlationPeriod','correlationResults','correlationStatus','correlationRecalculate','correlationPairDetails']) nodes[id] = {value:'',innerHTML:'',textContent:'',setAttribute(name,value){this[name]=value;}};
nodes.correlationPeriod.value='1y';
const $ = id => nodes[id];
const document = {addEventListener(){}};
const pending = [];
const api = path => new Promise((resolve,reject)=>pending.push({path,resolve,reject}));
const cell = {value:0,observations:40,status:'ok',from:'2026-09-24',to:'2026-11-03'};
const missing = {...cell,value:null,status:'insufficient_history',observations:0,from:null,to:null};
const data = {status:'partial',asset_count:2,usable_pairs:0,pair_count:1,from:'2025-11-03',to:'2026-11-03',accounts:[{id:'a',type:'Investment',account_id:'One'}],assets:[{symbol:'AAA',stock_market:'NASDAQ',currency:'USD',price_count:41,basis:'adjusted_close',from:'2026-09-24',to:'2026-11-03'},{symbol:'BBB',stock_market:'NASDAQ',currency:'USD',price_count:0,basis:'close',from:null,to:null}],matrix:[[cell,missing],[missing,cell]]};
''' + (ROOT / "web/correlation-ui.js").read_text() + "\n" + body
    result = subprocess.run(["node"], input=script, text=True, cwd=ROOT, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_matrix_numbers_missing_states_dates_and_language_switch():
    run_ui(r'''
correlationView = {...correlationView,status:'ready',data,accounts:data.accounts};
for (const language of ['en','he','en']) {
 state.language=language;renderCorrelation();
 const html=nodes.correlationResults.innerHTML;
 assert.ok(html.includes('0.00'));
 assert.ok(html.includes('03/11/2026'));
 assert.ok(html.includes('24/09/2026'));
 assert.ok(html.includes('scope="row"'));
 assert.ok(html.includes('role="region"'));
 assert.ok(!/NaN|undefined/.test(html));
 if(language==='he') {
   assert.ok(html.includes('לא זמין'));
   assert.ok(!/matching returns|Requested period|saved prices|Unadjusted close|Price history|Unavailable/.test(html));
 } else { assert.ok(html.includes('Unavailable')); assert.ok(!/[א-ת]/.test(html)); }
 correlationView.selected=[0,1];renderCorrelationPair();
 assert.ok(nodes.correlationPairDetails.textContent.includes(t('Fewer than 30 matching return observations.')));
}
''')


def test_loading_races_failure_retry_and_logout_reject_old_responses():
    run_ui(r'''
(async()=>{
 const first=loadCorrelation();
 assert.equal(correlationView.status,'loading');
 assert.equal(nodes.correlationResults['aria-busy'],'true');
 nodes.correlationPeriod.value='3m';
 const second=loadCorrelation();
 assert.ok(pending[1].path.includes('period=3m'));
 pending[1].resolve(data);await second;
 const selected=correlationView.data;
 pending[0].resolve({...data,asset_count:99});await first;
 assert.equal(correlationView.data,selected);
 nodes.correlationAccount.value='a';
 const failed=loadCorrelation();pending[2].reject(new Error('secret-provider-detail'));await failed;
 assert.equal(correlationView.status,'error');
 assert.equal(nodes.correlationAccount.value,'a');
 assert.ok(nodes.correlationStatus.textContent.includes('Recalculate'));
 assert.ok(!nodes.correlationStatus.textContent.includes('secret'));
 const retry=loadCorrelation();pending[3].resolve(data);await retry;
 assert.equal(correlationView.status,'ready');
 assert.equal(nodes.correlationRecalculate.disabled,false);
 const beforeLogout=loadCorrelation();resetCorrelation();pending[4].resolve(data);await beforeLogout;
 assert.equal(correlationView.data,null);
 assert.deepEqual(correlationView.accounts,[]);
})();
''')


def test_matrix_limit_and_small_scope_are_actionable():
    run_ui(r'''
correlationView = {...correlationView,status:'ready',data:{...data,status:'too_many_assets'}};
renderCorrelation();assert.ok(nodes.correlationResults.innerHTML.includes('Choose one account'));
correlationView.data={...data,assets:[]};renderCorrelation();
assert.ok(nodes.correlationResults.innerHTML.includes('At least two'));
''')


def test_all_added_static_modal_and_help_copy_translates():
    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, value):
            if value.strip():
                self.parts.append(value.strip())
    html = (ROOT / "web/index.html").read_text()
    modal = '<div id="correlationModal"' + html.split('<div id="correlationModal"', 1)[1].split('<div id="tradeSimulatorModal"', 1)[0]
    help_entry = html.split('<h3>Correlation Matrix</h3>', 1)[1].split('</article>', 1)[0]
    parser = Text()
    parser.feed(modal + help_entry)
    script = "const window={};\n" + (ROOT / "web/i18n.js").read_text()
    script += f"\nconst parts={json.dumps(parser.parts)};"
    script += "process.stdout.write(JSON.stringify(parts.filter(value=>/[A-Za-z]/.test(value)&&window.PortfolioI18n.translate(value,'he')===value)));"
    result = subprocess.run(["node"], input=script, text=True, capture_output=True, check=True)
    assert json.loads(result.stdout) == []


def test_investment_account_selector_rejects_other_and_untyped_accounts():
    run_ui(r'''
const outside=[{id:'esop-only',type:'ESOP',account_id:'Outside employee account'},{id:'bank-only',type:'Bank',account_id:'Outside bank account'},{id:'pension-only',type:'Long-Term Savings',account_id:'Outside pension account'},{id:'unknown-only',account_id:'Outside untyped account'}];
correlationView={...correlationView,status:"ready",data,accounts:[...data.accounts,...outside]};renderCorrelation();
const html=nodes.correlationAccount.innerHTML;for(const row of outside)assert.ok(!html.includes(row.account_id));
assert.ok(html.includes('All investment accounts'));
''')


def test_removed_account_recovers_to_investment_scope():
    run_ui(r'''
(async()=>{nodes.correlationAccount.value='removed';const old=loadCorrelation();pending[0].reject(new Error('unknown_account'));await new Promise(resolve=>setImmediate(resolve));assert.equal(nodes.correlationAccount.value,'');assert.equal(correlationView.data,null);assert.ok(pending[1].path.includes('account_id='));pending[1].resolve(data);await old;assert.equal(correlationView.status,'ready');})();
''')
