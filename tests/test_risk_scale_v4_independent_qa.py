"""Fifty independent economic acceptance fixtures for nominal stress-loss %.

All holdings, legal entities, opinions and amounts are synthetic. Expected money
loss is derived below from dated cash flows and the frozen economic shocks,
never from application outputs. These are deterministic illustrations, not fifty
independent observations, a backtest, or a probability-calibration exercise.
"""
from copy import deepcopy
from datetime import date
import json
import math
from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-11-14"
CORE_MODEL = "portfolio-risk-v4"
ESTIMATE_MODEL = "portfolio-risk-provisional-v3"


def opinion(grade="AAA", scope="sovereign", basis=None):
    row = dict(status="rated", rating=grade, agency="sp", scope=scope,
               scale="global", term="long_term", source_kind="agency_public",
               verified=True, eligible=True, stale=False, outlook="stable")
    if basis:
        row["currency_basis"] = basis
    return row


def holding(symbol, value, *, kind="equity", currency="ILS", country="IL",
            country_currency=None, grade="AAA", country_grade="AAA",
            issuer=None, account="a", maturity="2032-11-14", basis="local_currency"):
    bond = kind.endswith("bond")
    params = dict(instrument_kind=kind, country_currency=country_currency or currency,
                  country_basis="economic_exposure", as_of=AS_OF,
                  country_sensitivity=1)
    metadata = dict(security_key=f"{symbol}|QA|{currency}", valuation_date=AS_OF,
                    issuer_id=issuer or f"legal:{symbol}",
                    country={"country_code": country, "basis": "economic_exposure"},
                    currency_exposures={currency: 1}, parameters=params,
                    country_rating=opinion(country_grade))
    if bond:
        params.update(pricing_model="zero_coupon_continuous", maturity_date=maturity,
                      zero_coupon_confirmed=True, plain_nominal_noncallable=True,
                      current_spread_bps=45, sovereign_currency_basis=basis)
        if kind == "sovereign_bond":
            metadata["issuer_id"] = f"sovereign:{country}"
            metadata["sovereign_rating"] = opinion(grade, basis=basis)
        else:
            metadata["credit_rating"] = opinion(grade, scope="issue")
    return dict(holding=dict(symbol=symbol, stock_market="QA", currency=currency,
                             quantity=value, market_value=value, account_id=account,
                             asset_class="BOND" if bond else "EQUITY"),
                stress_risk=metadata)


def proxy_fund(symbol, value, focus, *, currency="ILS", account="a", **changes):
    result = holding(symbol, value, currency=currency, account=account, **changes)
    result["holding"]["asset_class"] = "MUTUALFUND"
    result["stress_risk"]["parameters"]["instrument_kind"] = "fund"
    result["exposure_profile"] = dict(asset_focus=focus, leverage_type="none",
                                      fx_basis="unhedged", currency_exposures={currency: 1})
    return result


def diverse(value=100, *, kind="equity", currency="ILS", grade="AAA", **changes):
    return [holding(f"ISSUER{i:02d}", value / 20, kind=kind, currency=currency,
                    grade=grade, **changes) for i in range(20)]


def remaining(maturity):
    return (date.fromisoformat(maturity) - date.fromisoformat(AS_OF)).days / 365.25


def zero_loss(years, shift):
    return -math.expm1(-years * shift)


def cash(value, currency="ILS", account="a"):
    return {"value": value, "currency": currency, "account_id": account}


def fixture(number, name, items=(), *, cash_rows=(), equity=100, loss=0,
            status="ok", scope="portfolio", uncapped=True, base="ILS", **extra):
    return dict(number=number, name=name, items=list(items),
                options=dict(baseCurrency=base, asOf=AS_OF, cashAccounts=list(cash_rows)),
                expected=dict(equity=equity, loss=loss, status=status, scope=scope,
                              loss_pct=(100 * loss / equity if equity > 0 else 0 if equity == 0 and loss == 0 else None) if uncapped else None,
                              **extra))


def fifty_economic_fixtures():
    t1, t6, t10 = map(remaining, ["2027-11-14", "2032-11-14", "2036-11-14"])
    cases = [
        fixture(1, "empty debt-free scope", equity=0),
        fixture(2, "native positive cash", cash_rows=[cash(100)]),
        fixture(3, "foreign positive cash", cash_rows=[cash(100, "USD")], loss=15),
        fixture(4, "debt-only funding boundary", cash_rows=[cash(-100)], equity=-100, loss=None, uncapped=False),
        fixture(5, "same-currency cash and debt cancel FX", cash_rows=[cash(100), cash(100, "USD"), cash(-100, "USD")]),
        fixture(6, "native money market fund", [proxy_fund("MMF", 100, "money_market")], loss=1, status="incomplete"),
        fixture(7, "foreign money market fund", [proxy_fund("MMF", 100, "money_market", currency="USD")], loss=15.85, status="incomplete"),
        fixture(8, "native money market plus equal cash", [proxy_fund("MMF", 100, "money_market")], cash_rows=[cash(100)], equity=200, loss=1, status="incomplete"),
        fixture(9, "native money market with moderate borrowing", [proxy_fund("MMF", 100, "money_market")], cash_rows=[cash(-50)], equity=50, loss=1, status="incomplete"),
        fixture(10, "native money market with one percent equity", [proxy_fund("MMF", 100, "money_market")], cash_rows=[cash(-99)], equity=1, loss=1, status="incomplete"),
        fixture(11, "broad equity fund", [proxy_fund("BROAD", 100, "broad_equity")], loss=40, status="incomplete"),
        fixture(12, "sector equity fund", [proxy_fund("SECTOR", 100, "sector_equity")], loss=50, status="incomplete"),
        fixture(13, "twenty independent equity issuers", diverse(), loss=40),
        fixture(14, "one concentrated equity issuer", [holding("SINGLE", 100)], loss=60),
        fixture(15, "two independent equity issuers", [holding("FIRST", 50), holding("SECOND", 50)], loss=40),
        fixture(16, "two listings of the same legal issuer", [holding("FIRST", 50, issuer="legal:shared"), holding("SECOND", 50, issuer="legal:shared")], loss=60),
        fixture(17, "diversified equities plus equal cash", diverse(), cash_rows=[cash(100)], equity=200, loss=40),
        fixture(18, "ten percent diversified equities", diverse(10), cash_rows=[cash(90)], loss=4),
        fixture(19, "two times diversified equity exposure", diverse(200), cash_rows=[cash(-100)], loss=80),
        fixture(20, "concentrated leveraged loss exceeds equity", [holding("SINGLE", 180)], cash_rows=[cash(-80)], loss=108),
        fixture(21, "single short with cash proceeds", [holding("SHORT", -100)], cash_rows=[cash(200)], loss=100),
        fixture(22, "same issuer matched long and short", [holding("LONG", 100, issuer="legal:shared"), holding("SHORT", -100, issuer="legal:shared")], cash_rows=[cash(100)]),
        fixture(23, "different issuer long and short basis risk", [holding("LONG", 100), holding("SHORT", -100)], cash_rows=[cash(100)], loss=100),
        fixture(24, "sixty-three percent foreign broad equities", [proxy_fund("BROAD", 63, "broad_equity", currency="USD")], cash_rows=[cash(37, "USD")], loss=36.42, status="incomplete"),
        fixture(25, "ninety-four percent foreign broad equities", [proxy_fund("BROAD", 94, "broad_equity", currency="USD")], cash_rows=[cash(6, "USD")], loss=46.96, status="incomplete"),
    ]
    mixed = proxy_fund("MIXED", 100, "broad_equity")
    mixed["stress_risk"]["currency_exposures"] = {"ILS": .5, "USD": .5}
    mixed["exposure_profile"]["currency_exposures"] = {"ILS": .5, "USD": .5}
    cases.extend([
        fixture(26, "half native half foreign economic currency", [mixed], loss=44.5, status="incomplete"),
        fixture(27, "short maturity AAA sovereign", [holding("GOV1", 100, kind="sovereign_bond", maturity="2027-11-14")], loss=100 * zero_loss(t1, .0225)),
        fixture(28, "long maturity AAA sovereign", [holding("GOV10", 100, kind="sovereign_bond", maturity="2036-11-14")], loss=100 * zero_loss(t10, .0225)),
        fixture(29, "long maturity BBB sovereign", [holding("GOV10", 100, kind="sovereign_bond", grade="BBB", maturity="2036-11-14")], loss=100 * zero_loss(t10, .03)),
        fixture(30, "long maturity BB local-currency sovereign", [holding("GOV10", 100, kind="sovereign_bond", grade="BB", country="BR", currency="BRL", maturity="2036-11-14")], base="BRL", loss=100 * zero_loss(t10, .05)),
        fixture(31, "BB foreign-currency sovereign obligation", [holding("GOVFC", 100, kind="sovereign_bond", grade="BB", country="BR", currency="USD", country_currency="BRL", basis="foreign_currency")], loss=100 * max(1 - math.exp(-t6 * .035) * .85, zero_loss(t6, .05))),
    ])
    lc_fc = holding("GOVLC", 100, kind="sovereign_bond", grade="AAA", country="BR", currency="BRL", country_currency="BRL")
    lc_fc["stress_risk"]["sovereign_ratings"] = {
        "local_currency": opinion("AAA", basis="local_currency"),
        "foreign_currency": opinion("BB", basis="foreign_currency"),
    }
    cases.extend([
        fixture(32, "LC AAA credit and FC BB systemic currency", [lc_fc], loss=100 * max(1 - math.exp(-t6 * .0225) * .85, 1 - math.exp(-t6 * .01) * .75)),
        fixture(33, "short sovereign loses in rate rally", [holding("GOVSHORT", -100, kind="sovereign_bond")], cash_rows=[cash(200)], loss=100 * math.expm1(t6 * .0245)),
        fixture(34, "twenty AAA corporate borrowers", diverse(kind="corporate_bond"), loss=100 * zero_loss(t6, .0225)),
        fixture(35, "twenty BBB corporate borrowers", diverse(kind="corporate_bond", grade="BBB"), loss=100 * zero_loss(t6, .0275)),
        fixture(36, "twenty BB corporate borrowers", diverse(kind="corporate_bond", grade="BB"), loss=100 * zero_loss(t6, .035)),
        fixture(37, "single AAA corporate borrower", [holding("CORP", 100, kind="corporate_bond")], loss=100 * zero_loss(1, .2)),
    ])
    coupon = holding("COUPON", 100, kind="corporate_bond")
    payments = [{"date": "2027-05-14", "amount": 2}, {"date": "2029-11-14", "amount": 7}, {"date": "2032-11-14", "amount": 103}]
    coupon["stress_risk"]["parameters"].update(pricing_model="cashflows_continuous", cashflows=payments, continuous_yield=.037)
    pv = lambda shift: sum(flow["amount"] * math.exp(-(.037 + shift) * remaining(flow["date"])) for flow in payments)
    duration = sum(remaining(flow["date"]) * flow["amount"] * math.exp(-.037 * remaining(flow["date"])) for flow in payments) / pv(0)
    coupon_loss = 100 * max(1 - pv(.0225) / pv(0), 1 - pv(max(.2 / duration, .01)) / pv(0))
    cases.extend([
        fixture(38, "coupon dates and PV weighted bond duration", [coupon], loss=coupon_loss),
        fixture(39, "government bond fund duration five proxy", [proxy_fund("GOVFUND", 100, "government_bond")], loss=100 * zero_loss(5, .03), status="incomplete"),
        fixture(40, "investment grade bond fund proxy", [proxy_fund("IGFUND", 100, "investment_grade_bond")], loss=100 * zero_loss(5, .0275), status="incomplete"),
        fixture(41, "high yield bond fund credit dominates", [proxy_fund("HYFUND", 100, "high_yield_bond")], loss=100 * zero_loss(4, .05), status="incomplete"),
    ])
    lookthrough = proxy_fund("LOOKTHROUGH", 100, "broad_equity")
    lookthrough["stress_risk"].update(lookthrough_verified=True, lookthrough=[{"weight": .05, "item": child} for child in diverse()])
    overlap = proxy_fund("OVERLAP", 50, "broad_equity")
    overlap["stress_risk"].update(lookthrough_verified=True, lookthrough=[{"weight": 1, "item": holding("CHILD", 100, issuer="legal:shared")}])
    hedged = proxy_fund("HEDGED", 100, "broad_equity", currency="USD")
    hedged["stress_risk"]["currency_exposures"] = {"ILS": 1}
    hedged["exposure_profile"].update(currency_exposures={"ILS": 1}, fx_basis="hedged")
    cases.extend([
        fixture(42, "verified twenty issuer fund lookthrough", [lookthrough], loss=40),
        fixture(43, "lookthrough overlap with direct legal issuer", [overlap, holding("DIRECT", 50, issuer="legal:shared")], loss=60),
        fixture(44, "foreign quotation with native currency hedge", [hedged], loss=40, status="incomplete"),
        fixture(45, "opposite account stresses pooled coherently", [holding("LONG", 100, issuer="legal:shared", account="long"), holding("SHORT", -100, issuer="legal:shared", account="short")], cash_rows=[cash(200, account="short")], equity=200, loss=0),
        fixture(46, "borrowing preserved alongside another account cash", diverse(), cash_rows=[cash(200, account="deposit"), cash(-100, account="borrower")], equity=200, loss=40, debt=100),
        fixture(47, "weak country money fund and currency", [proxy_fund("WEAKMMF", 100, "money_market", currency="BRL", country="BR", country_grade="B")], loss=36.3, status="incomplete"),
    ])
    missing_credit = holding("UNRATED", 100, kind="corporate_bond")
    del missing_credit["stress_risk"]["credit_rating"]
    stale = proxy_fund("STALE", 100, "broad_equity")
    stale["stress_risk"]["valuation_date"] = "2026-10-01"
    unsupported = holding("OPTION", 100)
    unsupported["holding"]["asset_class"] = "OPTION"
    unsupported["stress_risk"]["parameters"]["instrument_kind"] = "option"
    cases.extend([
        fixture(48, "missing credit opinion is an explicit proxy", [missing_credit], loss=100 * max(zero_loss(t6, .0325), zero_loss(t6, max(.2 / t6, 2 * .025))), status="incomplete"),
        fixture(49, "stale saved mark is a disclosed estimate", [stale], loss=40, status="incomplete"),
        fixture(50, "unsupported option leaves portfolio incomplete", [unsupported], cash_rows=[cash(100)], equity=100, loss=0, status="incomplete", scope="known_values"),
    ])
    assert len(cases) == 50
    assert [case["number"] for case in cases] == list(range(1, 51))
    assert len({case["name"] for case in cases}) == 50
    return cases


CASES = fifty_economic_fixtures()


@pytest.fixture(scope="module")
def results():
    payload = [{"items": case["items"], "options": case["options"]} for case in CASES]
    source = "const model=require('./web/stress-risk.js');const cases=" + json.dumps(payload, allow_nan=False) + ";console.log(JSON.stringify(cases.map(c=>model.calculate(c.items,c.options))));"
    completed = subprocess.run(["node"], cwd=ROOT, input=source, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.mark.parametrize("case", CASES, ids=lambda case: f"{case['number']:02d}-{case['name']}")
def test_fifty_independent_economic_simulations(case, results):
    result, expected = results[case["number"] - 1], case["expected"]
    assert result["model"] == CORE_MODEL
    assert result.get("score_unit") == "percent_capital_loss"
    assert result.get("score_scale") == "stress-loss-percent-v1"
    assert result.get("scenario_horizon") == "instantaneous_revaluation"
    assert result["status"] == expected["status"]
    assert result["cash_debt"] == pytest.approx(sum(max(0, -row["value"]) for row in case["options"]["cashAccounts"]))
    if expected["equity"] <= 0:
        assert result["loss_pct"] is None if expected["equity"] < 0 else result["loss_pct"] == 0
        assert result["score"] == (100 if expected["equity"] < 0 else 0)
        return
    if expected["status"] == "ok":
        equity, loss, loss_pct, score = (result[name] for name in ("net_equity", "stress_loss", "loss_pct", "score"))
    else:
        assert result["score"] is None
        assert result["provisional_model"] == ESTIMATE_MODEL
        assert result["provisional_scope"] == expected["scope"]
        equity, loss, score = (result.get(name) for name in ("provisional_net_equity", "provisional_loss", "provisional_score"))
        loss_pct = result.get("provisional_loss_pct")
        if expected["scope"] == "known_values":
            # Known cash is not evidence about the unknown option payoff.
            assert result["coverage"]["complete"] is False
            # The frozen API permits an internal compatibility-score range.
            # It must not be rendered as a whole-portfolio loss-percent bound;
            # the display contract is checked separately from this money test.
            assert result["score"] is None
            return
    assert equity == pytest.approx(expected["equity"])
    assert loss == pytest.approx(expected["loss"], abs=1e-9)
    assert loss_pct == pytest.approx(expected["loss_pct"], abs=1e-9)
    assert score == math.floor(min(100, expected["loss_pct"]) + .5)
    if "debt" in expected:
        assert result["cash_debt"] == expected["debt"]


def test_fifty_fixture_oracle_covers_plausibility_and_headroom():
    # These comparisons are facts about the frozen economic fixture arithmetic,
    # not a ranking selected from calculated application scores.
    by_number = {case["number"]: case["expected"] for case in CASES}
    assert by_number[2]["loss"] == 0 < by_number[6]["loss"] < by_number[13]["loss"] < by_number[14]["loss"]
    assert by_number[11]["loss"] < by_number[12]["loss"]
    assert by_number[24]["loss_pct"] < by_number[25]["loss_pct"] < 100
    assert by_number[27]["loss"] < by_number[28]["loss"] < by_number[29]["loss"] < by_number[30]["loss"]
    assert by_number[34]["loss"] < by_number[35]["loss"] < by_number[36]["loss"]
    assert by_number[13]["loss_pct"] < by_number[19]["loss_pct"] < by_number[20]["loss_pct"]
    assert by_number[17]["loss_pct"] < by_number[13]["loss_pct"]
    assert by_number[22]["loss"] == by_number[45]["loss"] == 0
    assert by_number[23]["loss"] > by_number[22]["loss"]
    assert by_number[7]["loss"] == pytest.approx(100 * (1 - .99 * .85))


def test_fifty_outputs_roundtrip_history_without_relabeling_legacy_scale(results):
    # pytest's conftest isolation runs before this application import.
    from app.risk_history import _stress_risk

    for fixture_case, raw in zip(CASES, results):
        unchanged = deepcopy(raw)
        saved = _stress_risk(raw, model=CORE_MODEL)
        assert raw == unchanged, fixture_case["number"]
        for field in ("model", "score_unit", "score_scale", "scenario_horizon", "score", "estimated_score", "loss_pct"):
            assert saved.get(field) == raw.get(field), (fixture_case["number"], field)
        if raw.get("provisional_model"):
            for field in ("provisional_model", "provisional_scope", "provisional_loss_pct", "provisional_known_loss_pct"):
                assert saved.get(field) == raw.get(field), (fixture_case["number"], field)

        # Historical v3 stored the original doubled integer and loss percentage.
        # Reading a legacy record must neither rescale it nor label it v4.
        legacy = deepcopy(raw)
        legacy["model"] = "portfolio-risk-v3"
        for field in ("score_unit", "score_scale", "scenario_horizon"):
            legacy.pop(field, None)
        if legacy.get("loss_pct") is not None and legacy.get("score") is not None:
            legacy["score"] = math.floor(min(100, 2 * legacy["loss_pct"]) + .5)
        if legacy.get("provisional_model"):
            legacy["provisional_model"] = "portfolio-risk-provisional-v2"
            loss, equity = legacy.get("provisional_loss"), legacy.get("provisional_net_equity")
            if loss is not None and equity is not None and equity > 0:
                legacy["provisional_score"] = math.floor(min(100, 200 * loss / equity) + .5)
            legacy.pop("provisional_loss_pct", None)
            legacy.pop("provisional_known_loss_pct", None)
        before = deepcopy(legacy)
        saved_legacy = _stress_risk(legacy, model="portfolio-risk-v3")
        assert legacy == before
        assert saved_legacy["model"] == "portfolio-risk-v3"
        assert saved_legacy["score"] == legacy["score"]
        assert saved_legacy.get("provisional_score") == legacy.get("provisional_score")
        assert "score_unit" not in saved_legacy


@pytest.mark.parametrize("index,changes", [
    (12, {"score_unit": "points"}),
    (12, {"score_scale": "doubled-loss-index"}),
    (12, {"scenario_horizon": "annual"}),
    (12, {"score": 80}),
    (12, {"loss_pct": 80}),
    (12, {"loss_pct": True}),
    (19, {"loss_pct": 100}),
    (25, {"provisional_score": 44}),
    (5, {"provisional_model": "portfolio-risk-provisional-v2"}),
    (5, {"estimated_score": 1}),
    (49, {"provisional_loss_pct": 0}),
    (3, {"loss_pct": 100}),
])
def test_history_rejects_cross_scale_or_false_financial_metadata(results, index, changes):
    from app.risk_history import RiskHistoryError, _stress_risk

    raw = deepcopy(results[index])
    raw.update(changes)
    with pytest.raises(RiskHistoryError):
        _stress_risk(raw, model=CORE_MODEL)


def test_current_badges_expose_uncapped_percent_confidence_and_boundaries_in_both_languages(results):
    from test_cash_fund_risk_frontend import run_ui

    body = "const risks=" + json.dumps(results, allow_nan=False) + ";\n" + r"""
const before=JSON.stringify(risks);
for (const language of ['en','he']) {
 state.language=language;
 const severe=stressRiskDisplay(risks[19]);
 assert.equal(severe.fullValue,'108.0%');
 const severeBadge=riskBadge(risks[19]),severeTooltip=riskTooltip(risks[19]);
 assert.ok(severeBadge.includes('108.0%'));
 for(const old of ['/100','Extreme','High risk','Low risk'])assert.ok(!severeBadge.includes(old),old);
 assert.ok(severeTooltip.includes(optionLabel('Stress loss')));
 const mmf=stressRiskDisplay(risks[5]);
 assert.equal(mmf.fullValue,'~1.0%');assert.ok(mmf.automatic&&mmf.provisional);
 assert.ok(riskBadge(risks[5]).includes(optionLabel('Estimate')));
 const boundary=stressRiskDisplay(risks[3]);
 assert.equal(boundary.number,null);assert.equal(boundary.unit,'');
 assert.ok(boundary.nonpositiveEquity);
 assert.equal(boundary.fullValue,optionLabel('Nonpositive equity'));
 assert.ok(!riskTooltip(risks[3]).split('\n')[0].includes('100%'));
 const unknown=stressRiskDisplay(risks[49]);
 assert.equal(unknown.number,null);assert.equal(unknown.unit,'');
 assert.equal(unknown.fullValue,optionLabel('Incomplete'));
 const unknownBadge=riskBadge(risks[49]),unknownTooltip=riskTooltip(risks[49]);
 assert.ok(unknownBadge.includes(optionLabel('Incomplete')));
 const unknownPrimary=unknownBadge.replace(/data-risk-explanation="[^"]*"/g,'');
 assert.ok(!unknownPrimary.includes('0–100')&&!unknownPrimary.includes('~0.0%'));
 assert.ok(unknownTooltip.includes(optionLabel('Known positions only: ~{percent}% scenario loss').replace('{percent}','0.0')));
 const legacy={...risks[12],model:'portfolio-risk-v3',score:80};
 assert.equal(stressRiskDisplay(legacy).fullValue,'80/100');
 assert.ok(riskTooltip(legacy).includes(optionLabel('Legacy stress score')));
 if(language==='he')for(const operational of ['Stress loss','Nonpositive equity','Incomplete','Estimate','Known positions only']) {
  const userText=[severeBadge,severeTooltip,riskBadge(risks[5]),riskBadge(risks[3]),unknownBadge,unknownTooltip].join('\n').replace(/data-risk-badge="[^"]*"/g,'');
  assert.ok(!userText.includes(operational),operational);
 }
}
assert.equal(JSON.stringify(risks),before);
"""
    run_ui(body)


def test_history_graph_separates_legacy_units_and_keeps_uncapped_losses(results):
    source = "const risks=" + json.dumps(results, allow_nan=False) + ";\n" + r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const window={},document={addEventListener(){}},state={language:'en'};
const esc=x=>String(x),t=x=>x,formatDate=x=>x,formatDateTime=x=>x;
""" + (ROOT / "web/risk-history-ui.js").read_text() + r"""
const rows=[
 {model:'portfolio-risk-v3',date:'2026-11-13',observed_at:'2026-11-13T12:00:00Z',risk:{...risks[12],model:'portfolio-risk-v3',score:80}},
 {model:'portfolio-risk-v4',date:'2026-11-14',observed_at:'2026-11-14T12:00:00Z',risk:risks[19]},
 {model:'portfolio-risk-v4',date:'2026-11-15',observed_at:'2026-11-15T12:00:00Z',risk:risks[3]},
 {model:'portfolio-risk-v4',date:'2026-11-16',observed_at:'2026-11-16T12:00:00Z',risk:risks[49]},
];
const html=riskHistoryGraph(rows,'Portfolio');
assert.equal((html.match(/<svg /g)||[]).length,2);
assert.ok(html.includes('Legacy risk index (0–100)')&&html.includes('Stress loss (%)'));
assert.ok(html.includes('80/100')&&html.includes('108.0%'));
assert.ok(!html.includes('100.0%')&&!html.includes('0.0%'));
assert.equal((html.match(/<circle /g)||[]).length,2);
assert.ok(!/d="[^"]*L/.test(html),'No line may link different units, undefined funding, or unknown scope');
console.log('PASS');
"""
    completed = subprocess.run(["node"], cwd=ROOT, input=source, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr


def test_planner_preserves_economic_controls_using_unrounded_loss_percent():
    source = r"""
const assert=require('node:assert/strict'),planner=require('./web/trade-planner.js');
const security={holding:{symbol:'NEW',currency:'USD',stock_market:'NASDAQ',asset_class:'EQUITY',quantity:0,market_value:0,location:'USA'},
 industry:'Technology',missing:[],price_ranges:{'1m':{current:100,current_date:'2026-11-14'},'1y':{current:100,current_date:'2026-11-14'}}};
function plan(before,after,existing=false){
 let calls=0;
 const context={accounts:[{id:'a',account_id:'QA',type:'Investment',location:'USA',currency:'USD',initial_cash:100000}],
  items:existing?[{...security,industry:'Finance',holding:{...security.holding,symbol:'OLD',account_id:'a',quantity:10,market_value:1000}}]:[],
  transactions:[],security,base_currency:'USD',fx_quotes:[],calculated_at:'2026-11-14T12:00:00Z'};
 return planner.plan(context,{action:'BUY',amount:100000},{horizon:()=>20,industry:item=>item.industry,volatility:()=>20,derivative:()=>false,
  risk:()=>{const loss=++calls===1?before:after;return{model:'portfolio-risk-v4',status:'ok',score:Math.round(Math.min(100,loss)),loss_pct:loss};}});
}
assert.equal(planner.POLICY.maxRisk,37.5);
assert.equal(planner.POLICY.maxRiskIncrease,2.5);
assert.equal(planner.POLICY.firstPositionRiskIncrease,12.5);
assert.equal(planner.stressLossPercent({score:100,status:'ok',loss_pct:135}),135);
assert.equal(planner.stressLossPercent({score:38,status:'ok',loss_pct:null}),null);
assert.equal(planner.stressLossPercent({score:null,status:'incomplete',provisional_loss_pct:1}),null);
const tooLarge=plan(10.51,13.02,true),atLimit=plan(10.49,12.99,true);
assert.equal(tooLarge.status,'unavailable','Rawincrease2.51ppmustnotpassbecause rounded11to13looks2points');
assert.ok(tooLarge.excluded.some(row=>row.reason==='risk_limit'));
assert.equal(atLimit.status,'ok','Rawincrease2.50ppmustnotfailbecause rounded10to13looks3points');
assert.equal(atLimit.recommendation.riskAfter,12.99);
assert.equal(atLimit.recommendation.riskUnit,'percent_capital_loss');
assert.equal(plan(37.5,37.5).status,'unavailable');
const amounts=[19.99,20.01,29.99,30.01].map(loss=>plan(loss,loss).recommendation.amount);
assert.deepEqual(amounts,[2000,1500,1500,1000],'Sizecuts20%/30%mustconsume rawpercent at both sides of rounded20/30');
console.log('PASS');
"""
    completed = subprocess.run(["node"], cwd=ROOT, input=source, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr


def test_alerts_apply_raw_percent_thresholds_and_separate_funding_boundary():
    app_source = (ROOT / "web/alarm-priority-ui.js").read_text()
    functions = []
    for name in ("portfolioRiskAlarms", "alarmAppearance"):
        start = app_source.index(f"function {name}(")
        end = start + re.search(r"^}", app_source[start:], re.M).end()
        functions.append(app_source[start:end])
    source = r"""
const assert=require('node:assert/strict');
const state={portfolioReady:true,portfolioRefreshPending:false,portfolioSourceState:'ready',allPortfolioItems:[]};
const t=x=>x,alarmText=(text,values)=>text.replace(/\{(\w+)\}/g,(_,key)=>values[key]);
const portfolioItems=rows=>rows,portfolioAccounts=()=>[];
let current;
const portfolioRiskSnapshot=()=>({total:current,accounts:[]});
""" + "\n".join(functions) + r"""
function alarm(loss){current={model:'portfolio-risk-v4',status:'ok',score:Math.round(Math.min(100,loss)),loss_pct:loss};return portfolioRiskAlarms();}
assert.equal(alarm(20).length,0);
assert.equal(alarm(20.01)[0].level,'stress_watch');
assert.equal(alarm(30)[0].level,'stress_watch');
assert.equal(alarm(30.01)[0].level,'stress_alert');
assert.equal(alarmAppearance(alarm(30.01)[0]).tone,'red');
assert.ok(!/Extreme|High risk/.test(JSON.stringify(alarm(135))));
current={model:'portfolio-risk-v4',status:'ok',score:100,loss_pct:null,net_equity:0,worst_scenario:'nonpositive_equity'};
const funding=portfolioRiskAlarms()[0];
assert.equal(funding.level,'funding');assert.equal(alarmAppearance(funding).tone,'red');
assert.ok(!funding.body.includes('100%'));
current={model:'portfolio-risk-v4',status:'incomplete',score:null,provisional_loss_pct:1,provisional_scope:'portfolio'};
assert.equal(portfolioRiskAlarms()[0].level,'unavailable','Automatic estimate is not a verified sizing/alert input');
console.log('PASS');
"""
    completed = subprocess.run(["node"], cwd=ROOT, input=source, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr


def test_percentage_scale_invariance_avoids_intermediate_overflow_and_rejects_unrepresentable_ratio():
    from app.risk_history import _stress_risk
    from test_cash_fund_risk_frontend import run_ui

    large = proxy_fund("HUGE", 1e308, "broad_equity")
    small = proxy_fund("SMALL", 1, "broad_equity")
    offset = [holding("LONG", 1e307), holding("SHORT", -1e307)]
    payload = [
        {"items": [small], "options": {"baseCurrency": "ILS", "asOf": AS_OF}},
        {"items": [large], "options": {"baseCurrency": "ILS", "asOf": AS_OF}},
        {"items": offset, "options": {"baseCurrency": "ILS", "asOf": AS_OF, "cash": 1e-308}},
    ]
    source = "const model=require('./web/stress-risk.js');const cases=" + json.dumps(payload, allow_nan=False) + r""";
const results=cases.map(c=>model.calculate(c.items,c.options));
function check(value){if(typeof value==='number'&&!Number.isFinite(value))throw Error('Nonfinite derived value');if(value&&typeof value==='object')for(const x of Object.values(value))check(x);}
results.forEach(check);console.log(JSON.stringify(results));
"""
    completed = subprocess.run(["node"], cwd=ROOT, input=source, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    small_risk, large_risk, overflow = json.loads(completed.stdout)
    for risk in (small_risk, large_risk):
        assert risk["provisional_scope"] == "portfolio"
        assert risk["provisional_loss_pct"] == pytest.approx(40)
        assert risk["provisional_score"] == 40
        assert _stress_risk(risk)["provisional_loss_pct"] == pytest.approx(40)
    assert large_risk["provisional_loss"] == pytest.approx(4e307)
    assert overflow["status"] == "incomplete" and overflow["score"] is None
    assert overflow["provisional_scope"] == "known_values"
    assert overflow["provisional_score"] is None and overflow["provisional_loss_pct"] is None
    assert overflow["provisional_known_loss_pct"] is None
    run_ui("const risk=" + json.dumps(large_risk, allow_nan=False) + r""";
for(const language of ['en','he']){state.language=language;const tooltip=riskTooltip(risk);assert.equal(stressRiskDisplay(risk).fullValue,'~40.0%');assert.ok(!tooltip.includes('Infinity')&&!tooltip.includes('NaN'));assert.ok(tooltip.includes('40.0%'));}
""")
