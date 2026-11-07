"""Independent behavioral checks of signed cash in the shared 0–100 model.

Model checks execute the actual dashboard risk function and simulator. Static
tooltip checks execute actual localization; these do not establish browser QA.
"""

import re

from test_trade_simulator import run_simulation
from test_trade_planner import ROOT


def app_functions(*names):
    source = (ROOT / "web/app.js").read_text()
    result = []
    for name in names:
        start = source.index(f"function {name}(")
        end = re.search(r"^}", source[start:], re.M).end()
        result.append(source[start:start + end])
    return "\n".join(result)


def test_fixed_holdings_risk_increases_as_cash_crosses_into_borrowing():
    run_simulation(r'''
const items=[stock('HELD',10000)];
const original=JSON.stringify(items);
const balances=[10000,2500,1000,500,100,0,-1,-100,-1000,-3000,-8000,-10000,-12000];
const scores=balances.map(cash=>adapters.risk(items,{cash,horizonYears:20}).score);
for(let index=0;index<scores.length;index++) {
 assert.ok(Number.isInteger(scores[index])&&scores[index]>=0&&scores[index]<=100,JSON.stringify({balances,scores}));
 if(index) assert.ok(scores[index]>=scores[index-1],JSON.stringify({balances,scores}));
}
assert.ok(scores[balances.indexOf(-3000)]>scores[balances.indexOf(0)]);
assert.equal(scores[balances.indexOf(-10000)],100);
assert.equal(scores.at(-1),100);
assert.equal(JSON.stringify(items),original);
''')


def test_debt_without_holdings_is_extreme_and_cash_only_is_numeric():
    run_simulation(r'''
for(const cash of [0,100,10000]) {
 const risk=adapters.risk([],{cash,horizonYears:20});
 assert.ok(Number.isInteger(risk.score)&&risk.score>=0&&risk.score<=100);
}
assert.equal(adapters.risk([],{cash:0,horizonYears:20}).score,0);
assert.equal(adapters.risk([],{cash:-1,horizonYears:20}).score,100);
assert.equal(adapters.risk([],{cash:-10000,horizonYears:20}).score,100);
const short=stock('SHORT',-1000);
assert.equal(adapters.risk([short],{cash:500,horizonYears:20}).score,100);
''')


def test_declared_v2_borrowing_adjustment_uses_net_equity_and_keeps_gross_cash():
    run_simulation(r'''
const items=[stock('HELD',10000)];
// One USD equity: 16 concentration + 9.1 asset mix + 7 industry +
// 7 low-cash + 6 2/3 volatility + 4 issuer, with a 20-year horizon.
const ordinary=adapters.risk(items,{cash:0,horizonYears:20});
const borrowed=adapters.risk(items,{cash:-1000,horizonYears:20});
assert.equal(ordinary.score,50);
assert.equal(borrowed.model,'portfolio-risk-v2');
assert.equal(borrowed.cash_debt,1000);
assert.equal(borrowed.net_equity,9000);
assert.ok(Math.abs(borrowed.unlevered_score-49.766666666666666)<1e-10);
assert.ok(Math.abs(borrowed.components.borrowing-(49.766666666666666/9))<1e-10);
assert.equal(borrowed.score,55);
// Net 1000 comprises 2000 positive cash and 1000 debt in separate accounts.
const combined=adapters.risk(items,{cash:1000,cashDebt:1000,horizonYears:20});
assert.equal(combined.cash_debt,1000);
assert.equal(combined.net_equity,11000);
assert.ok(Math.abs(combined.cash_pct-100/6)<1e-10);
assert.equal(combined.score,45);
// A supplied aggregate cannot understate an actual negative balance.
assert.equal(adapters.risk(items,{cash:-1000,cashDebt:100,horizonYears:20}).score,55);
''')


def test_simulator_cash_deficit_preserves_numeric_account_and_total_risk():
    run_simulation(r'''
const ctx=simulationContext();ctx.accounts[0].initial_cash=100;
const original=JSON.stringify(ctx);
const result=simulator.simulate(ctx,[trade()],adapters);
assert.equal(result.status,'ok');
assert.equal(result.accounts[0].after.cash,-900);
assert.equal(result.accounts[0].after.cashDeficit,900);
assert.equal(result.accounts[0].after.netValue,100);
assert.ok(Number.isFinite(result.accounts[0].after.risk.score));
assert.ok(result.accounts[0].after.risk.score>result.accounts[0].before.risk.score);
assert.ok(Number.isFinite(result.total.after.risk.score));
assert.equal(result.accounts[0].after.unavailableReasons.risk,null);
assert.deepEqual(result.total.after.blockedAccounts,[]);
assert.equal(JSON.stringify(ctx),original);
const captured=JSON.stringify(result);
ctx.accounts[0].initial_cash=900000;ctx.securities[0].security.price_ranges['1m'].current=1;
assert.equal(JSON.stringify(result),captured);
''')


def test_positive_combined_cash_cannot_conceal_a_borrowing_account():
    run_simulation(r'''
const ctx=simulationContext();ctx.accounts[0].initial_cash=-1000;
ctx.accounts.push(account('surplus','USA',2000));ctx.items=[stock('HELD',10000)];
const borrowed=simulator.simulate(ctx,[trade({quantity:1})],adapters);
assert.equal(borrowed.total.before.cash,1000);
assert.ok(Number.isFinite(borrowed.total.before.risk.score));
assert.equal(borrowed.accounts[0].before.cashDeficit,1000);
assert.equal(borrowed.total.before.cashDeficit,1000);
const clean=JSON.parse(JSON.stringify(ctx));clean.accounts[0].initial_cash=0;clean.accounts[1].initial_cash=1000;
const unborrowed=simulator.simulate(clean,[trade({quantity:1})],adapters);
assert.equal(unborrowed.total.before.cash,borrowed.total.before.cash);
assert.equal(unborrowed.total.before.netValue,borrowed.total.before.netValue);
assert.ok(borrowed.total.before.risk.score>unborrowed.total.before.risk.score,
 JSON.stringify({borrowed:borrowed.total.before.risk,unborrowed:unborrowed.total.before.risk}));
''')


def test_higher_execution_cost_keeps_valuation_fixed_and_raises_simulated_risk():
    run_simulation(r'''
const ctx=simulationContext();ctx.accounts[0].initial_cash=1000;ctx.items=[stock('HELD',10000)];
const costs=[100,500,1000,1500,3000,8000,12000];
const results=costs.map(priceInput=>simulator.simulate(ctx,[trade({quantity:1,priceInput})],adapters));
const risks=results.map(result=>result.accounts[0].after.risk.score);
for(let index=0;index<results.length;index++) {
 const snapshot=results[index].accounts[0].after;
 assert.equal(snapshot.cash,1000-costs[index]);
 assert.equal(snapshot.grossExposure,10100);
 assert.equal(snapshot.netValue,11100-costs[index]);
 assert.ok(Number.isInteger(risks[index]));
 if(index)assert.ok(risks[index]>=risks[index-1],JSON.stringify(risks));
}
assert.ok(risks[4]>risks[2]);
assert.equal(risks.at(-1),100);
''')


def test_genuine_missing_inputs_still_block_risk_without_hiding_known_account():
    run_simulation(r'''
for(const missing of ['cash','price','fx']) {
 const ctx=simulationContext();ctx.accounts[0].initial_cash=100;
 ctx.accounts.push(account('unknown','USA',1000,missing==='fx'?'ILS':'USD'));
 if(missing==='cash')ctx.accounts[1].initial_cash=null;
 if(missing==='price') {const item=stock('UNKNOWN',2000,'unknown');item.price_ranges={};ctx.items.push(item);}
 const result=simulator.simulate(ctx,[trade()],adapters);
 assert.equal(result.status,'ok');
 assert.ok(Number.isFinite(result.accounts[0].after.risk.score));
 assert.equal(result.accounts[1].after.risk,null);
 assert.equal(result.total.after.risk,null);
 assert.deepEqual(result.total.after.blockedAccounts.map(a=>a.accountId),['unknown']);
}
''')


def test_dashboard_and_simulator_use_same_account_and_total_scores():
    functions = app_functions(
        "portfolioRiskSnapshot", "accountCashBalance", "accountCashValue", "accountRiskCashValue",
        "riskAllocationForItems", "riskAllocationBand", "cleanSourceLabel",
    )
    run_simulation(functions + r'''
const portfolioAccounts=()=>state.localAccounts;
const accountRecordForHolding=h=>state.localAccounts.find(a=>a.id===h.account_id);
const accountHorizonYears=()=>20;
const normalizedAmount=(value,currency)=>currency==='ILS'?value/4:value;
const transactionCashImpact=()=>{throw new Error('This fixture has no transactions');};
for(const balances of [[1000,2000],[0,2000],[-1000,2000],[-10000,1000]]) {
 const ctx=simulationContext();ctx.accounts[0].initial_cash=balances[0];
 ctx.accounts.push(account('second','USA',balances[1]));
 ctx.items=[stock('HELD',10000),stock('OTHER',4000,'second','Finance')];
 state.localAccounts=ctx.accounts;state.localTransactions=[];
 const dashboard=portfolioRiskSnapshot(ctx.items);
 const simulation=simulator.simulate(ctx,[trade({quantity:1})],adapters);
 assert.equal(simulation.status,'ok');
 assert.equal(dashboard.total.score,simulation.total.before.risk.score,JSON.stringify({balances,dashboard,simulation}));
 for(const account of simulation.accounts) {
  assert.equal(dashboard.accounts.find(a=>String(a.key)===String(account.account.id)).risk.score,account.before.risk.score);
 }
}
// A deficit-only account must enter dashboard risk even with no holding row.
const ctx=simulationContext();ctx.accounts[0].initial_cash=-1000;
ctx.accounts.push(account('second','USA',2000));
state.localAccounts=ctx.accounts;state.localTransactions=[];
const dashboard=portfolioRiskSnapshot([]);
const simulated=simulator.simulate(ctx,[trade({accountId:'second',quantity:1})],adapters);
assert.equal(dashboard.accounts.find(a=>a.key==='us1').risk.score,100);
assert.equal(dashboard.total.score,simulated.total.before.risk.score);
// Debt must be converted to base currency before aggregation and weighting.
ctx.accounts[0].initial_cash=-4000;ctx.accounts[0].currency='ILS';
ctx.fx_quotes=[{pair:'USD/ILS',quote:{rate:4}}];
const convertedDashboard=portfolioRiskSnapshot([]);
const convertedSimulation=simulator.simulate(ctx,[trade({accountId:'second',quantity:1})],adapters);
assert.equal(convertedDashboard.total.cash_debt,1000);
assert.equal(convertedSimulation.total.before.risk.cash_debt,1000);
assert.equal(convertedDashboard.total.score,convertedSimulation.total.before.risk.score);
''')


def test_actual_risk_tooltip_explains_borrowing_in_both_languages():
    functions = app_functions("riskTooltip", "riskBand")
    i18n = (ROOT / "web/i18n.js").read_text()
    run_simulation("const window={};\n" + i18n + "\n" + functions + r'''
const optionLabel=text=>window.PortfolioI18n.translate(text,state.language);
const risk=adapters.risk([stock('HELD',10000)],{cash:-1000,horizonYears:20});
for(const language of ['en','he','en']) {
 state.language=language;
 const tooltip=riskTooltip(risk);
 assert.ok(tooltip.split('\n')[0].includes('55')&&!tooltip.split('\n')[0].includes('/100'),tooltip);
 assert.ok(!/undefined|NaN|null/.test(tooltip),tooltip);
 if(language==='en') {
  assert.ok(/borrow|debt/i.test(tooltip),tooltip);
  assert.ok(!/[א-ת]/.test(tooltip),tooltip);
 } else {
  assert.ok(/אשראי|הלווא|חוב/.test(tooltip),tooltip);
  assert.ok(!/[a-z]/i.test(tooltip),tooltip);
 }
}
''')
