"""Independent consumer acceptance from raw ledger and exact-listing facts.

These synthetic cases execute the real planner, shared risk wrapper/core and
simulator. Expected equity follows signed assets plus ledger cash; collateral is
a spending reservation. No runtime portfolio or corrected live score is inferred.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from test_shared_cash_risk_qa import app_functions


ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-11-14T12:00:00Z"


def stock(symbol, value=0, *, market="NASDAQ", currency="USD", asset="EQUITY", issuer=None):
    country = "IL" if market == "TASE" else "US"
    return {
        "holding": {"symbol": symbol, "account_id": "a", "quantity": value / 100, "market_value": value,
                    "currency": currency, "stock_market": market, "asset_class": asset,
                    "location": "Israel" if country == "IL" else "USA", "sector": "Energy", "industry": "Energy"},
        "exchange": market, "industry": "Energy", "missing": [],
        "stress_risk": {"security_key": f"{symbol}|{market}|{currency}", "valuation_date": AS_OF[:10],
            "issuer_id": issuer or f"legal:{symbol}|{market}|{currency}|{asset}",
            "country": {"country_code": country, "basis": "economic_exposure"},
            "country_rating": {"status": "rated", "rating": "AAA", "agency": "sp", "scope": "sovereign",
                "scale": "global", "term": "long_term", "verified": True, "stale": False,
                "source_kind": "agency_public", "currency_basis": "foreign_currency"},
            "currency_exposures": {currency: 1}, "parameters": {"instrument_kind": "equity", "country_currency": "ILS" if country == "IL" else "USD"}},
        "price_ranges": {"1m": {"current": 100, "current_date": AS_OF[:10]},
                         "1y": {"current": 100, "current_date": AS_OF[:10], "min": 95, "high": 110}},
    }


def account(identifier="a", cash=40000, type_="Investment"):
    return dict(id=identifier, account_id=identifier, type=type_, location="USA", currency="USD", initial_cash=cash)


def context(*, base="USD", cash=40000, items=None, security=None):
    return dict(accounts=[account(cash=cash)], transactions=[], items=items or [],
                security=security or stock("NEW"), base_currency=base,
                fx_quotes=[] if base == "USD" else [{"pair": "USD/ILS", "quote": {"rate": 4}}],
                calculated_at=AS_OF)


def node(source):
    result = subprocess.run(["node"], input=source, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def execute(ctx, action="BUY", amount=10000):
    setup = """
const planner=require('./web/trade-planner.js'),simulator=require('./web/trade-simulator.js');
const PortfolioStressRisk=require('./web/stress-risk.js');
const state={baseCurrency:ctx.base_currency,riskAsOf:ctx.calculated_at,fxRates:{}};
const calls=[];
const adapters={horizon:()=>20,industry:item=>item.industry,volatility:()=>20,derivative:()=>false,
 risk:(items,options)=>{const result=riskScoreForItems(items,options);calls.push({items:JSON.parse(JSON.stringify(items)),
 cash:options.cash,equity:result.net_equity,score:result.score,loss_pct:result.loss_pct,loss:result.stress_loss,
 provisional:result.provisional_score});return result;}};
const before=JSON.stringify(ctx),plan=planner.plan(ctx,request,adapters),planCalls=calls.splice(0);
let simulation=null;
if(plan.status==='ok'){
 const h=ctx.security.holding,rec=plan.recommendation;
 simulation=simulator.simulate({...ctx,securities:[{symbol:h.symbol,stock_market:h.stock_market,security:ctx.security}]},
  [{id:'t',accountId:rec.account.id,symbol:h.symbol,market:h.stock_market,action:request.action,
    quantity:rec.quantity,priceInput:'',fee:rec.feeAllowance}],adapters);
}
console.log(JSON.stringify({plan,planCalls,simulation,sourceUnchanged:JSON.stringify(ctx)===before}));
"""
    return node("const ctx=" + json.dumps(ctx) + ";const request=" + json.dumps(dict(action=action, amount=amount)) + ";\n"
                + app_functions("riskStrictBaseValue", "riskScoreForItems") + setup)


@pytest.mark.parametrize("action", ["BUY", "SHORT"])
@pytest.mark.parametrize("base,rate", [("USD", 1), ("ILS", 4)])
def test_planner_projection_preserves_equity_except_fee_and_matches_simulator(action, base, rate):
    ctx = context(base=base, items=[stock("OLD", 60000)])
    ctx["security"]["industry"] = ctx["security"]["holding"]["industry"] = ctx["security"]["holding"]["sector"] = "Technology"
    original = deepcopy(ctx)
    result = execute(ctx, action)
    assert result["plan"]["status"] == "ok", result
    rec = result["plan"]["recommendation"]
    notional, fee = rec["quantity"] * 100, rec["quantity"]
    ledger_cash = 40000 + (notional if action == "SHORT" else -notional) - fee
    expected_equity = (100000 - fee) * rate
    after = result["planCalls"][-1]
    assert after["cash"] == pytest.approx(ledger_cash * rate)
    assert after["equity"] == pytest.approx(expected_equity)
    assert rec["feeAllowance"] == fee
    assert rec["riskBefore"] == pytest.approx(36)
    assert rec["riskAfter"] == pytest.approx(100 * 36000 * rate / expected_equity)
    assert after["loss"] == pytest.approx(60000 * .6 * rate)
    # Spending policy keeps collateral aside; the shared risk denominator uses
    # the full ledger assets and signed short liability.
    assert rec["cashRemaining"] == pytest.approx(40000 - notional * (2 if action == "SHORT" else 1) - fee)
    if action == "SHORT":
        assert rec["collateral"] == 2 * notional
        assert ledger_cash - rec["cashRemaining"] == pytest.approx(3 * notional)
    simulation = result["simulation"]
    assert simulation["status"] == "ok", simulation
    projected = simulation["accounts"][0]["after"]
    assert projected["cash"] == pytest.approx(ledger_cash)
    assert projected["risk"]["net_equity"] == pytest.approx(expected_equity)
    assert projected["risk"]["loss_pct"] == rec["riskAfter"]
    assert result["sourceUnchanged"] and ctx == original


def test_actual_issuer_risk_triggers_quantity_halving_and_recomputes_its_fee():
    # Two share classes of one legal issuer. Bank cash enlarges the liquid
    # portfolio sizing base; the Investment account's initial NAV is100000.
    ctx = context(cash=75000, items=[stock("CLASS-A", 25000, issuer="sec:123")],
                  security=stock("CLASS-B", issuer="sec:123"))
    ctx["accounts"].append(account("bank", 900000, "Bank"))
    result = execute(ctx, amount=10000)
    assert result["plan"]["status"] == "ok", result
    rec = result["plan"]["recommendation"]
    # Initial50shares=5000: 100*18000/E99950 =18.009%, exceeding15%+2.5pp.
    # Halved25shares=2500: 100*16500/E99975 =16.504%, so the fee is25.
    assert rec["quantity"] == 25 and rec["amount"] == 2500 and rec["feeAllowance"] == 25
    assert [row["equity"] for row in result["planCalls"]] == [100000, 99950, 99975]
    assert [row["score"] for row in result["planCalls"]] == [15, 18, 17]
    assert rec["riskAfter"] == pytest.approx(100 * 16500 / 99975)
    assert rec["riskBefore"] == 15
    assert rec["riskAfter"] <= rec["riskBefore"] + 2.5
    assert rec["cashRemaining"] == 72475
    assert result["simulation"]["accounts"][0]["after"]["risk"]["net_equity"] == 99975
    assert result["sourceUnchanged"]


@pytest.mark.parametrize("difference", ["symbol", "market", "currency", "asset"])
@pytest.mark.parametrize("action", ["BUY", "SHORT"])
def test_projection_keeps_distinct_listings_currencies_assets_and_symbols_separate(difference, action):
    held, target = stock("SAME", 1000), stock("SAME")
    ctx = context(cash=100000, security=target)
    if difference == "symbol": held = stock("OTHER", 1000)
    elif difference == "market": held = stock("SAME", 4000, market="TASE", currency="ILS")
    elif difference == "currency": held = stock("SAME", 1000, currency="EUR")
    elif difference == "asset":
        held = stock("SAME", 1000, asset="ETF")
        held["stress_risk"]["parameters"]["instrument_kind"] = "fund"
        held["stress_risk"].update(lookthrough_verified=True,
            lookthrough=[{"weight": 1, "item": stock("UNDERLYING", 1000)}])
    ctx["items"] = [held]
    ctx["fx_quotes"] = [{"pair": "USD/ILS", "quote": {"rate": 4}}, {"pair": "EUR/USD", "quote": {"rate": 1.2}}]
    result = execute(ctx, action, amount=2000)
    assert result["plan"]["status"] == "ok", result
    rec = result["plan"]["recommendation"]
    after = result["planCalls"][-1]
    assert len(after["items"]) == 2
    assert after["items"][0]["holding"] == held["holding"]
    new = after["items"][1]["holding"]
    assert (new["symbol"], new["stock_market"], new["currency"], new["asset_class"]) == ("SAME", "NASDAQ", "USD", "EQUITY")
    assert new["quantity"] == rec["quantity"] * (-1 if action == "SHORT" else 1)
    held_base = 1000 if difference == "market" else 1200 if difference == "currency" else 1000
    assert after["equity"] == pytest.approx(100000 + held_base - rec["feeAllowance"])
    simulation = result["simulation"]
    assert simulation["status"] == "ok"
    assert simulation["accounts"][0]["after"]["risk"]["net_equity"] == pytest.approx(after["equity"])
    assert simulation["accounts"][0]["after"]["risk"]["loss_pct"] == rec["riskAfter"]
    assert result["sourceUnchanged"]


@pytest.mark.parametrize("market", ["NASDAQ", "NASDAQGS", "NMS"])
def test_normalized_same_listing_updates_existing_buy_and_blocks_short_over_its_long(market):
    held, target = stock("SAME", 1000, market=market, issuer="legal:SAME"), stock("SAME", issuer="legal:SAME")
    ctx = context(cash=100000, items=[held], security=target)
    buy = execute(ctx, "BUY", amount=2000)
    assert buy["plan"]["status"] == "ok", buy
    rec = buy["plan"]["recommendation"]
    rows = buy["planCalls"][-1]["items"]
    assert len(rows) == 1 and rows[0]["holding"]["quantity"] == 10 + rec["quantity"]
    assert rows[0]["holding"]["market_value"] == 1000 + rec["amount"]
    short = execute(ctx, "SHORT", amount=2000)
    assert short["plan"]["status"] == "unavailable"
    assert short["plan"]["excluded"][0]["reason"] == "existing_long"
    assert buy["sourceUnchanged"] and short["sourceUnchanged"]


@pytest.mark.parametrize("language", ["en", "he"])
@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_actual_risk_accessor_sorts_displayed_point_precedence_and_keeps_ranges_last(language, direction):
    boot = """
const HoldingsSort=require('./web/holdings-sort.js');
const state={language:LANGUAGE,baseCurrency:'USD',riskSnapshot:{total:{position_risks:new Map()}}};
const window={},document={addEventListener(){}},cleanSourceLabel=x=>x,holdingsStatusSortLabel=()=>'',reportAmount=x=>x;
let holdingsTableSort={key:'risk',direction:DIRECTION};
""".replace("LANGUAGE", json.dumps(language)).replace("DIRECTION", json.dumps(direction))
    result = node(boot + (ROOT / "web/stress-risk-ui.js").read_text() + app_functions("sortHoldingsRows") + """
const auto=n=>({model:'portfolio-risk-v4',score:null,status:'incomplete',provisional_model:'portfolio-risk-provisional-v3',provisional_scope:'portfolio',provisional_score:n,provisional_loss_pct:n});
const risks={A83:auto(83),RANGE:{...auto(0),provisional_scope:'known_values',provisional_range:{min:0,max:100}},
 EX25:{...auto(99),status:'estimate',estimated_score:25,loss_pct:25},A7a:auto(7),V30:{...auto(99),status:'ok',score:30,loss_pct:30},
 A7b:auto(7),ZERO:{...auto(99),score:0,loss_pct:0,status:'ok'},MISSING:{model:'portfolio-risk-v4',score:null,status:'incomplete'},LEGACY10:{score:10}};
const rows=Object.keys(risks).map(symbol=>({holding:{symbol}})),before=JSON.stringify({risks,rows});
rows.forEach(row=>state.riskSnapshot.total.position_risks.set(row,risks[row.holding.symbol]));
console.log(JSON.stringify({order:sortHoldingsRows(rows).map(row=>row.holding.symbol),unchanged:JSON.stringify({risks,rows})===before}));
""")
    expected = (["ZERO", "A7a", "A7b", "LEGACY10", "EX25", "V30", "A83"] if direction == "asc"
                else ["A83", "V30", "EX25", "LEGACY10", "A7a", "A7b", "ZERO"])
    assert result["order"] == expected + ["RANGE", "MISSING"]
    assert result["unchanged"]
