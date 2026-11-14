"""Financial behavior of the actual v3 browser engine, with explicit raw facts."""
import json
import math
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOT = r'''
const assert=require('node:assert/strict');
const risk=require('./web/stress-risk.js');
const rating=(grade='AAA',scope='issuer')=>({status:'rated',rating:grade,scope,scale:'global',term:'long_term',verified:true,stale:false,source_kind:'agency_public',outlook:'stable',watch:'none'});
const stock=(symbol='ONE',value=100,issuer=symbol)=>({holding:{symbol,market_value:value,quantity:value/100,currency:'USD',asset_class:'EQUITY',account_id:'a'},stress_risk:{valuation_date:'2026-11-14',security_key:symbol+'|NASDAQ|USD',issuer_id:issuer,instrument_kind:'equity',country:{country_code:'US',basis:'economic_exposure'},country_rating:rating('AAA','sovereign'),currency_exposures:{USD:1},parameters:{country_currency:'USD'}}});
const bond=(grade='AAA',kind='corporate_bond',value=100,issuer='ISSUER')=>{
 const item=stock(issuer,value,issuer);item.holding.asset_class='BOND';
 item.stress_risk.credit_rating=rating(grade,'issue');
 item.stress_risk.sovereign_rating={...rating(grade,'sovereign'),currency_basis:'local_currency'};
 item.stress_risk.parameters={as_of:'2026-11-14',instrument_kind:kind,country_currency:'USD',country_sensitivity:1,current_spread_bps:50,pricing_model:'zero_coupon_continuous',maturity_date:'2032-11-14',plain_nominal_noncallable:true,zero_coupon_confirmed:true,sovereign_currency_basis:'local_currency'};
 if(kind==='sovereign_bond')item.stress_risk.issuer_id='sovereign:US';
 return item;
};
const calculate=(items,opts={})=>risk.calculate(items,{baseCurrency:'USD',asOf:'2026-11-14',...opts});
const clone=x=>JSON.parse(JSON.stringify(x));
'''


def run_js(body):
    process = subprocess.run(["node"], input=BOOT + body, text=True, capture_output=True, cwd=ROOT)
    assert process.returncode == 0, process.stderr
    return process.stdout


@pytest.mark.parametrize("grade,kind,expected", [
    ("AAA", "corporate_bond", 25), ("BBB", "corporate_bond", 30), ("BB", "corporate_bond", 38),
    ("AAA", "sovereign_bond", 25), ("BBB", "sovereign_bond", 33), ("BB", "sovereign_bond", 52),
])
def test_credit_and_sovereign_repricing_oracles(grade, kind, expected):
    # Twenty separate corporate issuers make the one-issuer scenario smaller;
    # 20 sovereign issues of the same country retain the single sovereign risk.
    out = run_js(f'''
const items=Array.from({{length:20}},(_,i)=>bond({json.dumps(grade)},{json.dumps(kind)},5,'ISSUER'+i));
const result=calculate(items);assert.equal(result.status,'ok');
assert.equal(result.score,{expected},JSON.stringify(result));
assert.ok(!result.scenarios.some(s=>s.name.startsWith('issuer_')) || {json.dumps(kind)}!=='sovereign_bond');
console.log(JSON.stringify({{loss:result.loss_pct}}));
''')
    t = 2192 / 365.25  # Declared ACT/365.25 between fixture dates; no maturity-as-duration shortcut.
    widen = {"AAA": .005, "BBB": .015, "BB": .03}[grade]
    rate_loss = 1 - math.exp(-t * (.02 + .5 * widen))
    country_loss = 1 - math.exp(-t * ({"AAA": .01, "BBB": .03, "BB": .05}[grade] if kind == "sovereign_bond" else max(widen, .01)))
    assert json.loads(out)["loss"] == pytest.approx(max(rate_loss, country_loss) * 100)


def test_missing_bond_information_never_implies_zero_duration_or_zero_credit():
    run_js(r'''
for(const missing of ['maturity_date','zero_coupon_confirmed','current_spread_bps','country_sensitivity']) {
 const item=bond();delete item.stress_risk.parameters[missing];const result=calculate([item]);
 assert.equal(result.score,null,missing);assert.equal(result.status,'incomplete');assert.ok(result.gaps.length);
}
const item=bond();item.stress_risk.credit_rating=null;
assert.equal(calculate([item]).score,null);
item.stress_risk.parameters.instrument_kind='sovereign_bond';item.stress_risk.sovereign_rating=null;
assert.equal(calculate([item]).score,null);
const same=[clone(item),clone(item)];assert.equal(calculate(same).score,null);
''')


def test_same_issuer_lots_accounts_scaling_cash_and_borrowing():
    run_js(r'''
const diversified=Array.from({length:20},(_,i)=>stock('S'+i,5));
assert.equal(calculate(diversified).score,80);
assert.equal(calculate(diversified.map(i=>({...i,holding:{...i.holding,market_value:2.5}})),{cash:50}).score,40);
assert.equal(calculate(diversified.map(i=>({...i,holding:{...i.holding,market_value:6.25}})),{cash:-25}).score,100);
assert.equal(calculate([stock()]).score,100);
const split=Array.from({length:100},(_,i)=>stock('ONE',1,'ONE'));
assert.equal(calculate(split).score,100);
split.forEach((item,i)=>{item.holding.account_id=String(i);});
assert.equal(calculate(split).score,100);
const original=JSON.stringify(split);calculate(split);assert.equal(JSON.stringify(split),original);
const scaled=diversified.map(item=>({...item,holding:{...item.holding,market_value:item.holding.market_value*1000}}));
assert.equal(calculate(scaled).score,calculate(diversified).score);
''')


def test_signed_short_and_foreign_cash_are_not_ignored():
    run_js(r'''
assert.equal(calculate([stock('SHORT',-50)],{cash:150}).score,100);
assert.equal(calculate([],{cashAccounts:[{value:100,currency:'EUR'}]}).score,30);
const r=calculate([],{cashAccounts:[{value:200,currency:'USD'},{value:-100,currency:'EUR'}]});
assert.equal(r.cash_debt,100);assert.equal(r.net_equity,100);assert.equal(r.score,30);
assert.equal(calculate([],{cash:-1}).score,100);
assert.equal(calculate([],{cash:0}).score,0);
assert.equal(calculate([],{cash:100}).score,0);
assert.equal(calculate([],{cash:null}).score,null);
assert.equal(calculate([stock()],{normalizeField:()=>null}).score,null);
''')


def test_nonpositive_equity_requires_fresh_valuation_but_not_complete_credit_inputs():
    run_js(r'''
const item=bond();delete item.stress_risk.credit_rating;
const fresh=calculate([item],{cash:-200});
assert.equal(fresh.score,100);assert.equal(fresh.net_equity,-100);
assert.equal(fresh.coverage.complete,false);
item.stress_risk.valuation_date='2026-10-01';
const stale=calculate([item],{cash:-200});assert.equal(stale.score,null);assert.equal(stale.net_equity,null);
delete item.stress_risk.valuation_date;
assert.equal(calculate([item],{cash:-200}).score,null);
''')


def test_local_foreign_sovereign_basis_is_not_investor_base_currency():
    run_js(r'''
const item=bond('BBB','sovereign_bond');item.holding.currency='ILS';
item.stress_risk.currency_exposures={ILS:1};item.stress_risk.parameters.country_currency='ILS';
item.stress_risk.country.country_code='IL';
// ILS sovereign obligation is still LC for a USD investor.
assert.ok(Number.isFinite(calculate([item]).score));
item.stress_risk.sovereign_rating.currency_basis='foreign_currency';
assert.equal(calculate([item]).score,null);
''')


def test_foreign_currency_country_opinion_does_not_override_local_currency_debt():
    run_js(r'''
const government=bond('AAA','sovereign_bond');
government.stress_risk.sovereign_ratings={local_currency:government.stress_risk.sovereign_rating};
const small=stock('EQUITY',.000001);small.stress_risk.country_rating=rating('BB','sovereign');
small.stress_risk.country_rating.currency_basis='foreign_currency';
assert.equal(calculate([government]).score,25);
assert.equal(calculate([government,small]).score,25);
''')


def test_cashflow_repricing_uses_actual_schedule_and_current_yield():
    run_js(r'''
const item=bond('AAA','sovereign_bond');
item.stress_risk.parameters.pricing_model='cashflows_continuous';
item.stress_risk.parameters.cashflows=[{date:'2027-11-14',amount:5},{date:'2028-11-14',amount:105}];
item.stress_risk.parameters.continuous_yield=.04;
const r=calculate([item]);assert.equal(r.status,'ok');
const times=[365/365.25,731/365.25],amounts=[5,105];
const pv=y=>amounts.reduce((n,a,i)=>n+a*Math.exp(-y*times[i]),0);
const expected=(1-pv(.04+.0225)/pv(.04))*100;
assert.ok(Math.abs(r.loss_pct-expected)<1e-10,JSON.stringify(r));
delete item.stress_risk.parameters.continuous_yield;assert.equal(calculate([item]).score,null);
''')


def test_manual_ratings_require_explicit_estimate_and_negative_signal_is_separate():
    run_js(r'''
const item=bond('BBB','sovereign_bond');
item.stress_risk.sovereign_rating.manual_override=true;
assert.equal(calculate([item]).score,null);
item.stress_risk.parameters.assumptions_enabled=true;
const estimate=calculate([item]);assert.equal(estimate.score,null);assert.equal(estimate.status,'estimate');assert.equal(estimate.estimated_score,33);
const verified=bond('BBB','sovereign_bond');verified.stress_risk.sovereign_rating.negative_signal=true;
const result=calculate([verified]);assert.equal(result.score,33);assert.ok(result.forward_sensitivity.score>=result.score);
assert.equal(verified.stress_risk.sovereign_rating.rating,'BBB');
''')


def test_fund_wrapper_does_not_inherit_manager_rating_or_fake_diversification():
    run_js(r'''
const item=stock('FUND');item.holding.asset_class='ETF';item.stress_risk.parameters.instrument_kind='fund';
item.stress_risk.credit_rating=rating('AAA');
assert.equal(calculate([item]).score,null);
item.stress_risk.lookthrough_verified=true;
item.stress_risk.lookthrough=Array.from({length:20},(_,i)=>({weight:.05,item:stock('S'+i,5)}));
assert.equal(calculate([item]).score,80);
''')
