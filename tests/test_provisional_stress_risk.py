"""Asset-aware estimates preserve strict unknowns and immutable v1 history."""
import json
import math

import pytest

from app.risk_history import RiskHistoryError, _stress_risk
from test_stress_risk_model import run_js


@pytest.mark.parametrize("cash,expected", [(0, 16), (400, 3), (900, 2)])
def test_missing_bond_rating_retains_number_without_inventing_credit(cash, expected):
    output = run_js(f"""
const item=bond('BBB','sovereign_bond');delete item.stress_risk.sovereign_rating;
delete item.stress_risk.credit_rating;
const r=calculate([item],{{cash:{cash}}});
assert.equal(r.status,'incomplete');assert.equal(r.score,null);
assert.equal(r.provisional_model,'portfolio-risk-provisional-v3');
assert.equal(r.provisional_score,{expected});
assert.equal(r.provisional_basis,'asset_aware_scenarios');
assert.equal(r.provisional_scope,'portfolio');
assert.equal(r.provisional_proxy_gross,100);
assert.ok(r.provisional_assumptions.some(a=>a.code==='unrated_credit_proxy'&&a.spread_bps===200));
console.log(JSON.stringify(r));
""")
    saved = _stress_risk(json.loads(output))
    assert saved["score"] is None
    assert saved["provisional_score"] == expected
    assert saved["provisional_loss"] == pytest.approx(100 * (1 - math.exp(-(2192 / 365.25) * .03)))


def test_actual_and_proxy_duration_share_common_scenarios_and_equity():
    result = json.loads(run_js("""
const known=bond('AAA','sovereign_bond',60,'KNOWN');
const missing=bond('BBB','corporate_bond',40,'MISSING');
delete missing.stress_risk.parameters.maturity_date;
console.log(JSON.stringify(calculate([known,missing])));
"""))
    loss = (60 * (1 - math.exp(-(2192 / 365.25) * .0225))
            + 40 * (1 - math.exp(-5 * .0275)))
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == math.floor(100 * loss / 100 + .5 + 1e-10)
    assert result["score"] is None
    assert result["net_equity"] == 100


def test_verified_lookthrough_uses_child_proxies_without_charging_parent():
    run_js("""
const fund=stock('FUND',100);fund.holding.asset_class='ETF';
fund.stress_risk.parameters.instrument_kind='fund';
fund.stress_risk.lookthrough_verified=true;
const missing=stock('MISSING',50);delete missing.stress_risk.country_rating;
fund.stress_risk.lookthrough=[{weight:.5,item:stock('KNOWN',50)},
 {weight:.5,item:missing}];
const r=calculate([fund],{cash:400});
assert.equal(r.provisional_score,8);assert.equal(r.provisional_loss,40);
assert.equal(r.provisional_proxy_gross,100);assert.equal(r.score,null);
""")


def test_known_cash_and_diversified_equities_remain_supported():
    run_js("""
const known=Array.from({length:20},(_,i)=>stock('KNOWN'+i,3));
const fund=stock('FUND',40);fund.holding.asset_class='ETF';
fund.stress_risk.parameters.instrument_kind='fund';
const r=calculate([...known,fund],{cash:100});
assert.equal(r.net_equity,200);assert.ok(Math.abs(r.provisional_loss-40)<1e-10);
assert.equal(r.provisional_score,20);assert.equal(r.score,null);
""")


def test_late_country_currency_gap_is_excluded_from_displayed_input_coverage():
    run_js("""
const item=bond('AAA','sovereign_bond');
item.holding.currency='EUR';item.stress_risk.currency_exposures={EUR:1};
item.stress_risk.parameters.country_currency='EUR';
item.stress_risk.country.country_code='DE';item.stress_risk.issuer_id='sovereign:DE';
item.stress_risk.country_rating=null;
item.stress_risk.sovereign_ratings={local_currency:item.stress_risk.sovereign_rating};
const r=calculate([item]);
assert.equal(r.status,'incomplete');assert.equal(r.coverage.covered_value,0);
assert.equal(r.coverage.covered_value_percent,0);assert.equal(r.provisional_proxy_gross,100);
assert.equal(r.provisional_scope,'portfolio');
const bondLoss=100*(1-Math.exp(-(2192/365.25)*.0225)*.85);
assert.ok(Math.abs(r.provisional_loss-bondLoss)<1e-10);
const withBaseCash=calculate([item],{cash:100});
assert.equal(withBaseCash.coverage.covered_value_percent,50);
const withForeignCash=calculate([item],{cashAccounts:[{value:100,currency:'EUR'}]});
assert.equal(withForeignCash.coverage.covered_value_percent,0);
assert.equal(withForeignCash.provisional_basis,'asset_aware_scenarios');
assert.equal(withForeignCash.provisional_scope,'portfolio');
assert.ok(Math.abs(withForeignCash.provisional_loss-bondLoss-15)<1e-10);
""")


@pytest.mark.parametrize("change,options", [
    ("item.holding.market_value=null", "{cash:400}"),
    ("item.stress_risk.valuation_date='2027-01-01'", "{cash:400}"),
    ("", "{cash:null}"),
    ("", "{normalizeField:()=>null,cash:400}"),
    ("item.holding.asset_class='FUTURE'", "{cash:400}"),
    ("item.exposure_profile={leverage_type:'leveraged'}", "{cash:400}"),
])
def test_unknown_scope_or_unsupported_payoff_shows_range_without_forced_score(change, options):
    output = run_js(f"""
const item=bond('AAA','sovereign_bond');{change};
const r=calculate([item],{options});
assert.equal(r.score,null);assert.equal(r.status,'incomplete');
assert.equal(r.provisional_basis,'asset_aware_scenarios');
assert.equal(r.provisional_scope,'known_values');
assert.deepEqual(r.provisional_range,{{min:0,max:100}});
assert.notEqual(r.worst_scenario,'nonpositive_equity');
console.log(JSON.stringify(r));
""")
    record = json.loads(output)
    saved = _stress_risk(record)
    assert saved["provisional_range"] == {"min": 0, "max": 100}
    assert saved["score"] is None


@pytest.mark.parametrize("mark,code", [("2026-10-01", "stale_valuation"), (None, "undated_valuation")])
def test_reported_last_known_values_support_dated_estimate(mark, code):
    result = json.loads(run_js(f"""
const item=bond('AAA','sovereign_bond');item.stress_risk.valuation_date={json.dumps(mark)};
console.log(JSON.stringify(calculate([item],{{cash:400}})));
"""))
    assert result["score"] is None and result["net_equity"] is None
    assert result["provisional_scope"] == "portfolio"
    assert result["provisional_net_equity"] == 500
    assert result["provisional_score"] == 3
    assert any(row["code"] == code for row in result["provisional_assumptions"])
    assert _stress_risk(result)["provisional_score"] == 3


def test_short_plain_bond_keeps_signed_rally_exposure_instead_of_ceiling():
    result = json.loads(run_js("""
const item=bond('AAA','sovereign_bond',-100);delete item.stress_risk.parameters.maturity_date;
console.log(JSON.stringify(calculate([item],{cash:500})));
"""))
    loss = 100 * math.expm1(5 * (.02 + .005))
    assert result["provisional_scope"] == "portfolio"
    assert result["provisional_net_equity"] == 400
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == math.floor(100 * loss / 400 + .5 + 1e-10)


def test_distinct_gaps_do_not_charge_same_holding_multiple_times_or_per_lot():
    run_js("""
const missing=bond('BBB','sovereign_bond');
delete missing.stress_risk.sovereign_rating;
delete missing.stress_risk.credit_rating;
delete missing.stress_risk.parameters.maturity_date;
delete missing.stress_risk.parameters.current_spread_bps;
const r=calculate([missing],{cash:900});assert.equal(r.provisional_score,1);
const duplicate=clone(missing);duplicate.holding.market_value=50;
const duplicateResult=calculate([duplicate,clone(duplicate)],{cash:900});
assert.equal(duplicateResult.provisional_score,1);
assert.equal(duplicateResult.provisional_proxy_gross,100);
assert.equal(calculate([duplicate,duplicate],{cash:900}).provisional_score,1);
const lots=Array.from({length:10},(_,i)=>{
 const item=clone(missing);item.holding.account_id='A'+i;
 item.holding.market_value=10;return item;
});
assert.equal(calculate(lots,{cash:900}).provisional_score,1);
assert.equal(r.provisional_proxy_gross,100);
""")


def test_verified_boundaries_and_explicit_estimates_keep_original_contract():
    run_js("""
assert.equal(calculate([bond('BBB','sovereign_bond')]).score,16);
const missing=bond();delete missing.stress_risk.credit_rating;
const boundary=calculate([missing],{cash:-200});
assert.equal(boundary.score,100);assert.equal(boundary.provisional_score,undefined);
assert.equal(calculate([],{cash:0}).score,0);
const estimate=bond('BBB','sovereign_bond');
estimate.stress_risk.sovereign_rating.manual_override=true;
estimate.stress_risk.parameters.assumptions_enabled=true;
const r=calculate([estimate]);assert.equal(r.estimated_score,16);
assert.equal(r.score,null);assert.equal(r.provisional_score,undefined);
""")


@pytest.mark.parametrize("invalid", [
    {"provisional_model": "other"}, {"provisional_score": True},
    {"provisional_score": 101}, {"provisional_score": 99},
    {"provisional_loss": None}, {"provisional_unmodeled_gross": -1},
    {"provisional_loss": 99}, {"provisional_basis": "guessed_rating"},
    {"status": "ok", "score": 40},
])
def test_history_rejects_malformed_or_promoted_provisional_assessments(invalid):
    record = dict(model="portfolio-risk-v3", status="incomplete", score=None,
                  provisional_model="portfolio-risk-provisional-v1", provisional_score=40,
                  provisional_basis="unmodeled_exposure_allowance", provisional_loss=100,
                  provisional_unmodeled_gross=100, net_equity=500,
                  coverage={"complete": False, "covered_value_percent": 80})
    with pytest.raises(RiskHistoryError):
        _stress_risk({**record, **invalid})
