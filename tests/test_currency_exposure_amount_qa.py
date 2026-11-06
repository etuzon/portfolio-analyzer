"""Independent raw-fixture checks for economic currency exposure amounts."""

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _functions(*names):
    source = (ROOT / "web/app.js").read_text()
    snippets = []
    for name in names:
        start = re.search(rf"^function {name}\(", source, re.M).start()
        end = re.search(r"^}", source[start:], re.M).end()
        snippets.append(source[start : start + end])
    return "\n".join(snippets)


def _run(checks):
    script = """
const assert = require('node:assert/strict');
const PortfolioTradePlanner = require('./web/trade-planner.js');
global.window = {};
global.navigator = {language: 'en-US'};
const state = {baseCurrency:'ILS',language:'en',fxRates:{'USD/ILS':4},localAccounts:[],localTransactions:[]};
const OPTION_LABELS = {};
const HEBREW_CURRENCY_NAMES = {ILS:'שקל חדש',USD:'דולר אמריקאי',EUR:'אירו'};
const portfolioAccounts = () => state.localAccounts;
const colorAt = index => ['#8b5cf6','#ec4899','#fb923c','#60a5fa','#34d399','#facc15'][index];
"""
    script += "\n" + (ROOT / "web/i18n.js").read_text() + "\n"
    script += _functions(
        "locale", "optionLabel", "bidiIsolate", "currencySymbol", "currencyName",
        "currencyDisplayLabel", "esc", "fmt", "money", "sum", "normalizedAmount",
        "normalizedField", "checkedAccountShareAmount", "economicCurrencyExposure",
        "accountCashBalance", "accountNativeCashBalance", "accountCashValue", "transactionCashImpact",
        "currencyAllocationGroups", "renderDonut", "renderCurrencyAllocation",
    )
    script += r"""
const fund = (value, currency='ILS', allocations=[{currency:'USD',percent:80},{currency:'ILS',percent:20}]) => ({
  holding:{asset_class:'MUTUALFUND',currency,market_value:value},
  exposure_profile:{fx_basis:'reported',currency_exposures:allocations},
});
const legend = html => html.split('<div class="donut-legend">')[1];
const amountTexts = html => [...html.matchAll(/<bdi class="currency-exposure-amount" dir="auto">([^<]*)<\/bdi>/g)].map(match=>match[1]);
"""
    completed = subprocess.run(["node"], input=script + checks, capture_output=True, text=True, cwd=ROOT)
    assert completed.returncode == 0, completed.stderr


def test_economic_amount_uses_allocation_value_and_current_direct_or_inverse_fx():
    _run("""
for (const rates of [{'USD/ILS':4},{'ILS/USD':0.25}]) {
  state.fxRates=rates;
  const groups=currencyAllocationGroups([fund(1000)]);
  assert.deepEqual(Object.fromEntries(groups.map(row=>[row.label,row.value])),{USD:800,ILS:200});
  const html=renderCurrencyAllocation(groups,1000);
  assert.deepEqual(amountTexts(html),['$200','₪200']);
  assert.match(legend(html),/USD[^<]*80%/);
  assert.match(legend(html),/ILS[^<]*20%/);
}
state.fxRates={'USD/ILS':5};
assert.deepEqual(amountTexts(renderCurrencyAllocation(currencyAllocationGroups([fund(1000)]),1000)),['$160','₪200']);
// A USD-traded holding with EUR economic exposure is converted once to base,
// then to EUR. Its amount must not be its USD quote value or cash balance.
state.fxRates={'USD/ILS':4,'EUR/ILS':5};
assert.deepEqual(amountTexts(renderCurrencyAllocation(currencyAllocationGroups([fund(100,'USD',[{currency:'EUR',percent:100}])]),400)),['€80']);
""")


def test_missing_or_invalid_fx_never_becomes_a_fabricated_local_amount():
    _run("""
for(const raw of [undefined,null,false,true,[],[4],{},'',0,-1,Infinity,NaN]) {
  state.fxRates={'USD/ILS':raw};
  const baseGroups=currencyAllocationGroups([fund(1000)]);
  const baseHtml=renderCurrencyAllocation(baseGroups,1000);
  assert.equal(amountTexts(baseHtml)[0],'Not available',`base→USD raw ${String(raw)}`);
  const sourceGroups=currencyAllocationGroups([fund(100,'USD',[{currency:'ILS',percent:100}])]);
  assert.equal(amountTexts(renderCurrencyAllocation(sourceGroups,100))[0],'Not available',`USD→base raw ${String(raw)}`);
}
state.fxRates={};
const mixed=currencyAllocationGroups([fund(100,'USD',[{currency:'ILS',percent:100}]),fund(100,'ILS',[{currency:'ILS',percent:100}])]);
assert.equal(amountTexts(renderCurrencyAllocation(mixed,200))[0],'Not available');
state.fxRates={'USD/ILS':0,'ILS/USD':0.25};
assert.equal(amountTexts(renderCurrencyAllocation(currencyAllocationGroups([fund(1000)]),1000))[0],'$200');
state.fxRates={};state.language='he';
const he=renderCurrencyAllocation(currencyAllocationGroups([fund(1000)]),1000);
assert.equal(amountTexts(he)[0],'לא זמין');
assert.ok(!legend(he).includes('Not available'));
state.language='en';
for(const value of [null,undefined,false,'100',NaN,Infinity]) {
  const html=renderCurrencyAllocation([{label:'ILS',value}],100);
  assert.equal(amountTexts(html)[0],'Not available',`malformed base amount ${String(value)}`);
}
""")


def test_aggregate_amounts_are_labeled_base_equivalent_and_zero_is_known():
    _run("""
state.fxRates={};
assert.deepEqual(amountTexts(renderCurrencyAllocation([{label:'USD',value:0}],0)),['$0']);
const unknown=currencyAllocationGroups([{holding:{asset_class:'MUTUALFUND',currency:'ILS',market_value:1000}}]);
assert.deepEqual(amountTexts(renderCurrencyAllocation(unknown,1000)),['Base equivalent: ₪1,000']);
const unknownMissingSource=currencyAllocationGroups([{holding:{asset_class:'MUTUALFUND',currency:'EUR',market_value:1000}}]);
assert.deepEqual(amountTexts(renderCurrencyAllocation(unknownMissingSource,1000)),['Base equivalent: Not available']);
const rows=[['ILS',500],['USD',400],['EUR',300],['GBP',200],['JPY',100],['CAD',50]].map(([label,value])=>({label,value}));
state.fxRates={'USD/ILS':4,'EUR/ILS':5,'GBP/ILS':5};
let html=renderCurrencyAllocation(rows,1550);
assert.equal(amountTexts(html).at(-1),'Base equivalent: ₪150');
assert.match(legend(html),/Other currencies[^<]*10%/);
rows[5].amountUnavailable=true;
assert.equal(amountTexts(renderCurrencyAllocation(rows,1550)).at(-1),'Base equivalent: Not available');
state.language='he';html=renderCurrencyAllocation(unknown,1000);
assert.match(amountTexts(html)[0],/שווי במטבע הבסיס/);
assert.ok(!legend(html).includes('Base equivalent'));
""")


def test_cash_is_included_once_and_other_donuts_are_unchanged():
    _run("""
state.localAccounts=[{id:'usd-account',currency:'USD',initial_cash:50}];state.fxRates={'USD/ILS':4};
const groups=currencyAllocationGroups([fund(1000)]);
assert.deepEqual(Object.fromEntries(groups.map(row=>[row.label,row.value])),{USD:1000,ILS:200});
assert.deepEqual(amountTexts(renderCurrencyAllocation(groups,1200)),['$250','₪200']);
const html=renderDonut([{label:'Cash',value:1000},{label:'Bonds',value:1000}],'Asset mix','50%',2000);
assert.deepEqual(amountTexts(html),[]);
assert.match(legend(html),/Cash 50% · ₪1,000/);
assert.match(legend(html),/Bonds 50%/);
""")


def test_mixed_currency_cash_is_unavailable_until_the_transaction_is_corrected():
    _run("""
state.localAccounts=[{id:'usd-account',currency:'USD',initial_cash:1000}];
state.localTransactions=[{account_db_id:'usd-account',action:'BUY',quantity:1,price:100,currency:'ILS',trade_date:'2026-01-01'}];
// Legacy totals subtract the raw100. The new local amount must not endorse
// this as USD900 because the debit is denominated in ILS.
let groups=currencyAllocationGroups([]);
let html=renderCurrencyAllocation(groups,3600);
assert.deepEqual(amountTexts(html),['Not available']);
assert.ok(!html.includes('$900'));
assert.ok(!html.includes('₪3,600'));
state.language='he';
assert.deepEqual(amountTexts(renderCurrencyAllocation(groups,3600)),['לא זמין']);
// Correcting its currency restores the deterministicUSD900 amount.
state.language='en';state.localTransactions[0].currency='USD';
groups=currencyAllocationGroups([]);
assert.deepEqual(amountTexts(renderCurrencyAllocation(groups,3600)),['$900']);
// Another account's transaction must not poison this account's amount.
state.localTransactions.push({account_db_id:'other',action:'BUY',quantity:1,price:100,currency:'ILS',trade_date:'2026-01-01'});
assert.deepEqual(amountTexts(renderCurrencyAllocation(currencyAllocationGroups([]),3600)),['$900']);
""")
