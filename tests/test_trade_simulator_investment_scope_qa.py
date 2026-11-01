"""Independent checks for investment-only simulation scope and honest unknowns.

Model checks use the dashboard's real risk functions. UI checks use its real
scripts in a synthetic DOM and do not establish live browser layout behavior.
"""

from copy import deepcopy

import pytest

from app import main

from test_trade_simulator import run_simulation
from test_trade_simulator_frontend import run_ui


def test_context_filters_known_noninvestment_sources_but_preserves_orphan_evidence(monkeypatch):
    accounts = [
        {"id": "investment", "type": "Investment", "initial_cash": 5000, "currency": "USD"},
        {"id": "pension", "type": "Long-Term Savings", "initial_cash": None, "currency": "ILS"},
        {"id": "bank", "type": "Bank", "initial_cash": 90000, "currency": "USD"},
        {"id": "esop", "type": "ESOP", "initial_cash": None, "currency": "USD"},
    ]
    transactions = [{"account_db_id": account["id"], "action": "BUY"} for account in accounts]
    items = [{"holding": {"account_id": account["id"], "symbol": account["id"].upper()}} for account in accounts]
    items.append({"holding": {"account_id": "unknown", "symbol": "ORPHAN"}})
    original = deepcopy((accounts, transactions, items))
    looked_up = []

    def resolve(symbol, market, evidence, *args):
        looked_up.append(deepcopy(evidence))
        return {"holding": {"symbol": symbol}}, None

    monkeypatch.setattr(main, "portfolio_cache_signature", lambda: "frozen")
    monkeypatch.setattr(main, "portfolio_payload", lambda **kw: {"items": items})
    monkeypatch.setattr(main, "local_store", type("ReadOnly", (), {
        "list_accounts": lambda _: accounts,
        "list_transactions": lambda _: transactions,
    })())
    monkeypatch.setattr(main, "planner_security", resolve)
    monkeypatch.setattr(main, "hub", lambda: object())
    monkeypatch.setattr(main, "fx", lambda: {"quotes": []})
    result = main.trade_simulator_context({"securities": [{"symbol": "NEW", "stock_market": "NASDAQ"}]})
    assert [account["id"] for account in result["accounts"]] == ["investment"]
    assert [row["account_db_id"] for row in result["transactions"]] == ["investment"]
    assert [item["holding"]["symbol"] for item in result["items"]] == ["INVESTMENT", "ORPHAN"]
    assert looked_up == [items]
    assert (accounts, transactions, items) == original


@pytest.mark.parametrize("excluded_type", ["Bank", "Long-Term Savings", "ESOP"])
def test_excluded_account_evidence_cannot_change_investment_results(excluded_type):
    run_simulation('''
const ctx=simulationContext();ctx.items=[stock('HELD',5000)];
const expected=simulator.simulate(ctx,[trade()],adapters);
ctx.accounts.push(account('excluded','Israel',null,'ILS',EXCLUDED_TYPE));
const excluded=stock('EXCLUDED',900000,'excluded','Finance','ILS');
excluded.holding.asset_sub_class='OPTION';excluded.price_ranges={};
ctx.items.push(excluded);
ctx.transactions.push({account_db_id:'excluded',action:'BUY',currency:'EUR',quantity:1,price:100,trade_date:'2027-01-01'});
const source=JSON.stringify(ctx);
const actual=simulator.simulate(ctx,[trade()],adapters);
assert.equal(actual.status,'ok');
assert.deepEqual(actual.accounts.map(a=>a.account.id),['us1']);
assert.deepEqual(actual.total,expected.total);
assert.deepEqual(actual.accounts,expected.accounts);
assert.deepEqual(actual.warnings,expected.warnings);
assert.ok(Number.isFinite(actual.total.after.risk.score));
assert.equal(JSON.stringify(ctx),source);
'''.replace("EXCLUDED_TYPE", repr(excluded_type)))


def test_excluded_stale_quotes_do_not_warn_inside_investment_scope():
    run_simulation('''
const ctx=simulationContext();
ctx.accounts.push(account('pension','USA',10000,'USD','Long-Term Savings'));
const excluded=stock('STALE_PENSION',50000,'pension');
for(const quote of Object.values(excluded.price_ranges))quote.current_date='2025-01-01';
ctx.items=[excluded];
const result=simulator.simulate(ctx,[trade()],adapters);
assert.equal(result.status,'ok');
assert.deepEqual(result.warnings,[]);
assert.equal(result.total.before.netValue,100000);
assert.equal(result.total.after.netValue,100000);
''')


def test_unchanged_investment_accounts_stay_in_results_and_weighted_total():
    run_simulation('''
const ctx=simulationContext();ctx.accounts.push(account('unchanged','USA',5000));
ctx.accounts.push(account('bank','USA',999999,'USD','Bank'));
ctx.items=[stock('UNCHANGED',2000,'unchanged','Finance')];
const result=simulator.simulate(ctx,[trade({fee:3})],adapters);
assert.deepEqual(result.accounts.map(a=>a.account.id),['us1','unchanged']);
assert.equal(result.accounts[1].after.cash,5000);
assert.equal(result.accounts[1].after.netValue,7000);
assert.equal(result.total.before.cash,105000);
assert.equal(result.total.before.netValue,107000);
assert.equal(result.total.after.cash,103997);
assert.equal(result.total.after.netValue,106997);
const projected=[stock('NEW',1000),stock('UNCHANGED',2000,'unchanged','Finance')];
const combined=adapters.risk(projected,{cash:103997,baseCurrency:'USD',horizonYears:20});
const weighted=(result.accounts[0].after.risk.score*99997+result.accounts[1].after.risk.score*7000)/106997;
assert.equal(result.total.after.risk.score,Math.round(.75*combined.score+.25*weighted));
''')


def test_missing_investment_evidence_still_blocks_total_without_hiding_known_accounts():
    run_simulation('''
const ctx=simulationContext();ctx.accounts.push(account('incomplete','USA',5000));
ctx.accounts.push(account('pension','USA',null,'USD','Long-Term Savings'));
const missing=stock('MISSING',2000,'incomplete');missing.price_ranges={};ctx.items=[missing];
const result=simulator.simulate(ctx,[trade()],adapters);
assert.equal(result.status,'ok');
assert.deepEqual(result.accounts.map(a=>a.account.id),['us1','incomplete']);
assert.ok(Number.isFinite(result.accounts[0].after.risk.score));
assert.equal(result.accounts[1].after.cash,5000);
assert.equal(result.accounts[1].after.netValue,null);
assert.equal(result.accounts[1].after.risk,null);
assert.equal(result.total.after.cash,104000);
assert.equal(result.total.after.netValue,null);
assert.equal(result.total.after.risk,null);
assert.equal(result.total.after.reason,'valuation_unavailable');
''')


def test_excluding_pension_does_not_invent_required_investment_fx_or_account_owner():
    run_simulation('''
const ctx=simulationContext();ctx.base_currency='ILS';
ctx.accounts.push(account('pension','Israel',900000,'ILS','Long-Term Savings'));
let result=simulator.simulate(ctx,[trade()],adapters);
assert.equal(result.accounts[0].after.netValue,100000);
assert.equal(result.total.after.netValue,null);
assert.equal(result.total.after.risk,null);
assert.equal(result.total.after.reason,'fx_unavailable');
ctx.base_currency='USD';ctx.items=[stock('UNASSIGNED',500,'missing-account')];
result=simulator.simulate(ctx,[trade()],adapters);
assert.equal(result.total.after.netValue,null);
assert.equal(result.total.after.risk,null);
assert.equal(result.total.after.reason,'unknown_account');
''')


def test_metric_reasons_identify_missing_security_and_blocking_investment_account():
    run_simulation('''
const ctx=simulationContext();ctx.accounts.push(account('incomplete','USA',5000));
const missing=stock('UNPRICED',2000,'incomplete');missing.price_ranges={};ctx.items=[missing];
const result=simulator.simulate(ctx,[trade()],adapters);
const accountResult=result.accounts.find(a=>a.account.id==='incomplete').after;
assert.equal(accountResult.cash,5000);
assert.equal(accountResult.unavailableReasons.cash,null);
assert.equal(accountResult.unavailableReasons.netValue,'valuation_unavailable');
assert.equal(accountResult.unavailableReasons.risk,'valuation_unavailable');
assert.ok(accountResult.issues.some(i=>i.symbol==='UNPRICED'&&i.reason==='price_missing'));
assert.equal(result.total.after.unavailableReasons.risk,'valuation_unavailable');
assert.ok(result.total.after.blockedAccounts.some(a=>a.accountId==='incomplete'&&a.reason==='valuation_unavailable'));
''')


@pytest.mark.parametrize("field,reason", [
    ("currency", "holding_currency_missing"),
    ("asset_class", "holding_class_missing"),
])
def test_saved_price_does_not_disguise_missing_holding_currency_or_classification(field, reason):
    run_simulation('''
const ctx=simulationContext();const incomplete=stock('INCOMPLETE',1000);
delete incomplete.holding.FIELD;ctx.items=[incomplete];
const result=simulator.simulate(ctx,[trade()],adapters);
assert.equal(result.status,'ok');
assert.equal(result.accounts[0].after.cash,99000);
assert.equal(result.accounts[0].after.netValue,null);
assert.equal(result.accounts[0].after.risk,null);
assert.ok(result.accounts[0].after.issues.some(i=>i.symbol==='INCOMPLETE'&&i.reason===REASON));
assert.equal(result.total.after.risk,null);
'''.replace("FIELD", field).replace("REASON", repr(reason)))


def test_account_cash_deficit_blocks_total_risk_even_when_total_cash_is_positive():
    run_simulation('''
const ctx=simulationContext();ctx.accounts[0].initial_cash=1000;
ctx.accounts.push(account('healthy','USA',50000));
ctx.accounts.push(account('pension','USA',999999,'USD','Long-Term Savings'));
const result=simulator.simulate(ctx,[trade({quantity:20})],adapters);
const deficit=result.accounts.find(a=>a.account.id==='us1').after;
assert.equal(deficit.cash,-1000);
assert.equal(deficit.netValue,1000);
assert.equal(deficit.cashDeficit,1000);
assert.equal(deficit.unavailableReasons.cash,null);
assert.equal(deficit.unavailableReasons.risk,'negative_cash');
assert.equal(result.total.after.cash,49000);
assert.equal(result.total.after.netValue,51000);
assert.equal(result.total.after.risk,null);
assert.equal(result.total.after.reason,'negative_cash');
const blocked=result.total.after.blockedAccounts.find(a=>a.accountId==='us1');
assert.equal(blocked.reason,'negative_cash');
assert.equal(blocked.cashDeficit,1000);
assert.equal(blocked.currency,'USD');
''')


def test_short_collateral_reason_explains_unknown_buying_power_without_erasing_equity():
    run_simulation('''
const ctx=simulationContext();
const result=simulator.simulate(ctx,[trade({action:'SHORT',quantity:2})],adapters);
const after=result.accounts[0].after;
assert.equal(after.cash,100200);
assert.equal(after.netValue,100000);
assert.equal(after.shortExposure,200);
assert.equal(after.availableCash,null);
assert.equal(after.unavailableReasons.cash,null);
assert.equal(after.unavailableReasons.netValue,null);
assert.equal(after.unavailableReasons.availableCash,'collateral_unverified');
assert.equal(result.total.after.unavailableReasons.availableCash,'collateral_unverified');
''')


def test_scope_label_is_explicit_in_both_languages_and_excluded_accounts_are_absent():
    run_ui('''
tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:'2',priceInput:'',fee:'0'}];
const mixed=JSON.parse(JSON.stringify(ctx));
mixed.accounts.push({id:'pension',account_id:'PENSION_FIXTURE',type:'Long-Term Savings',currency:'USD',initial_cash:null});
const result=window.PortfolioTradeSimulator.simulate(mixed,tradeSimulatorRows,{risk:riskScoreForItems,horizon:accountHorizonYears,derivative:derivativeHolding});
for(const language of ['en','he']){
 state.language=language;tradeSimulatorView={status:'ready',result};renderTradeSimulator();
 const html=nodes.tradeSimulatorResults.innerHTML;
 const text=html.replace(/<[^>]*>/g,'');
 assert.ok(!text.includes('PENSION_FIXTURE'));
 assert.ok(language==='he'?text.includes('השקעה'):/investment/i.test(text));
 assert.ok(!/undefined|NaN/.test(text));
 if(language==='he')assert.ok(!/Investment|Before|After|Total/.test(text));
 else assert.ok(!/[א-ת]/.test(text));
}
''')


def test_rendered_unknowns_name_missing_holding_and_deficit_account_in_both_languages():
    run_ui('''
const mixed=JSON.parse(JSON.stringify(ctx));mixed.accounts[0].initial_cash=100;
mixed.accounts.push({id:'missing',account_id:'MISSING_FIXTURE_ACCOUNT',type:'Investment',currency:'USD',initial_cash:500});
mixed.items=[{holding:{account_id:'missing',symbol:'UNPRICED_FIXTURE',quantity:10,currency:'USD',asset_class:'EQUITY',stock_market:'NASDAQ'},price_ranges:{}}];
tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:'2',priceInput:'',fee:'0'}];
const result=window.PortfolioTradeSimulator.simulate(mixed,tradeSimulatorRows,{risk:riskScoreForItems,horizon:accountHorizonYears,derivative:derivativeHolding});
for(const language of ['en','he']){
 state.language=language;tradeSimulatorView={status:'ready',result};renderTradeSimulator();
 const text=nodes.tradeSimulatorResults.innerHTML.replace(/<[^>]*>/g,'');
 assert.ok(text.includes('UNPRICED_FIXTURE'));
 assert.ok(text.includes('MISSING_FIXTURE_ACCOUNT'));
 assert.ok(text.includes('USD 100.00'));
 assert.ok(!/undefined|NaN/.test(text));
 if(language==='en'){
  assert.ok(/deficit/i.test(text));
  assert.ok(/missing|cannot be valued/i.test(text));
  assert.ok(!text.includes('Not available'));
  assert.ok(!/[א-ת]/.test(text));
 }else{
  assert.ok(/חוסר|מחסור|גירעון|גרעון/.test(text));
  assert.ok(!/Cash deficit|Missing holding|Not available|Before|After/.test(text));
 }
}
''')
