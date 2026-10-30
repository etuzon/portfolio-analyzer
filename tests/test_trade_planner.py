"""Behavioral sizing checks against the dashboard's actual risk model."""
import json
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

from app import main
from app.models import Ohlcv
from app.trade_planner import planner_security

ROOT = Path(__file__).resolve().parents[1]


def run_planner_js(body):
    source = (ROOT / "web/app.js").read_text()
    names = ("riskScoreForItems", "assetRiskFactor", "derivativeHolding", "diversifiedFund", "industryLabel", "issuerLabel", "countryLabel", "economicCurrencyExposure", "volatilityProxy")
    functions = []
    for name in names:
        start = source.index(f"function {name}(")
        end = re.search(r"^}", source[start:], re.M).end()
        functions.append(source[start:start + end])
    script = "\n".join(functions) + r'''
const assert = require('node:assert/strict');
const planner = require('./web/trade-planner.js');
const state = {baseCurrency:'USD'};
const sum = values => values.reduce((a,b)=>a+b,0);
const fmt = n => String(n);
const clamp = (v,a,b) => Math.max(a,Math.min(v,b));
const normalizedField = (item,field) => item.holding[field];
const stock = (symbol, value=0, account='us1', sector='Technology', currency='USD') => ({
 holding:{symbol, account_id:account, quantity:value/100, market_value:value,
   currency, stock_market:'NASDAQ', asset_class:'EQUITY', sector, industry:sector},
 exchange:'NASDAQ', industry:sector, missing:[],
 price_ranges:{'1m':{current:100,current_date:'2026-10-29'},'1y':{current:100,high:120,min:80,current_date:'2026-10-29'}}});
const account = (id='us1', location='USA', cash=100000, currency='USD', type='Investment') =>
 ({id, account_id:id, location, initial_cash:cash, currency, type});
const context = () => ({accounts:[account()], transactions:[], items:[], security:stock('NEW'),
 base_currency:'USD', fx_quotes:[], calculated_at:'2026-10-30T12:00:00Z'});
const adapters = {risk:riskScoreForItems,horizon:()=>20,industry:industryLabel,volatility:volatilityProxy,derivative:derivativeHolding};
const request = {action:'BUY', amount:''};
''' + body
    result = subprocess.run(["node"], input=script, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_cash_only_account_can_receive_a_conservative_first_purchase():
    run_planner_js('''
const result=planner.plan(context(),request,adapters);
assert.equal(result.status,'ok',JSON.stringify(result));
const rec=result.recommendation;
assert.ok(rec.amount>0 && rec.amount<=2000);
assert.ok(rec.cashRemaining>=rec.reserve);
assert.ok(rec.riskAfter<=75);
assert.equal(rec.quantity*100,rec.amount);
''')


def test_us_restriction_and_account_type_are_hard_filters():
    run_planner_js('''
const ctx=context();
ctx.accounts=[account('israel','Israel'),account('unknown',''),account('retirement','USA',100000,'USD','Long-Term Savings'),account('esop','USA',100000,'USD','ESOP'),account('us','US')];
const result=planner.plan(ctx,request,adapters);
assert.equal(result.status,'ok',JSON.stringify(result));
assert.equal(result.recommendation.account.id,'us');
assert.equal(result.excluded.find(e=>e.account.id==='israel').reason,'account_country');
assert.equal(result.excluded.find(e=>e.account.id==='unknown').reason,'account_country');
assert.equal(result.excluded.find(e=>e.account.id==='esop').reason,'account_type');
''')


def test_requested_budget_is_ceiling_and_fx_is_explicit():
    run_planner_js('''
const ctx=context();
ctx.base_currency='ILS'; ctx.fx_quotes=[{pair:'USD/ILS',quote:{rate:4}}];
const result=planner.plan(ctx,{action:'BUY',amount:1400,amountCurrency:'ILS'},adapters);
assert.equal(result.status,'ok',JSON.stringify(result));
assert.equal(result.requested,350);
assert.ok(result.recommendation.amount<=350 && result.recommendation.amount>0);
ctx.fx_quotes=[];
assert.equal(planner.plan(ctx,request,adapters).reason,'fx_unavailable');
for(const amount of [0,-1,'no',Infinity]) assert.equal(planner.plan(context(),{action:'BUY',amount},adapters).reason,'invalid_request');
assert.equal(planner.plan(context(),{action:'BUY',amount:10},adapters).status,'unavailable');
''')


def test_missing_stale_and_ambiguous_data_never_becomes_zero_or_buying_power():
    run_planner_js('''
const ctx=context();
ctx.security.price_ranges['1m'].current_date='2026-01-01';
ctx.security.price_ranges['1y'].current_date='2026-01-01';
assert.equal(planner.plan(ctx,request,adapters).reason,'price_unavailable');
ctx.security=stock('NEW'); ctx.security.exchange=''; ctx.security.holding.stock_market='YAHOO';
assert.equal(planner.plan(ctx,request,adapters).reason,'listing_unverified');
ctx.security=stock('NEW');ctx.items=[stock('OLD',1000)];delete ctx.items[0].price_ranges;
assert.equal(planner.plan(ctx,request,adapters).reason,'valuation_unavailable');
ctx.items=[];ctx.transactions=[{account_db_id:'us1',action:'BUY',quantity:1,price:10,currency:'ILS'}];
assert.equal(planner.plan(ctx,request,adapters).reason,'cash_unverified');
''')


def test_existing_global_concentration_can_block_every_account():
    run_planner_js('''
const ctx=context();ctx.accounts.push(account('us2'));
ctx.items=[stock('NEW',30000)];
const result=planner.plan(ctx,request,adapters);
assert.equal(result.status,'unavailable');
assert.ok(result.excluded.every(e=>['stock_account_limit','stock_portfolio_limit'].includes(e.reason)));
''')


def test_short_budget_reserves_collateral_and_never_uses_sale_proceeds():
    run_planner_js('''
const ctx=context();ctx.accounts.push(account('us2'));ctx.items=[stock('NEW',1000,'us2')];
const original=JSON.stringify(ctx);
const result=planner.plan(ctx,{action:'SHORT',amount:1000},adapters);
assert.equal(result.status,'ok',JSON.stringify(result));
const rec=result.recommendation;
assert.equal(rec.account.id,'us1');
assert.equal(rec.collateral,rec.amount*2);
assert.ok(Math.abs(rec.cashRemaining-(rec.cash-rec.collateral-rec.feeAllowance))<0.0001);
assert.ok(rec.cashRemaining>=rec.reserve);
assert.equal(result.excluded.find(e=>e.account.id==='us2').reason,'existing_long');
assert.equal(JSON.stringify(ctx),original);
''')


def test_cash_ledger_reduces_purchase_budget_and_does_not_use_future_income():
    run_planner_js('''
const tx=(action,quantity,price,trade_date='2026-10-29')=>({account_db_id:'us1',action,quantity,price,currency:'USD',trade_date});
assert.equal(planner.cashBalance(account(),[tx('BUY',10,100),tx('SELL',2,100),tx('DIVIDEND',10,1),tx('FEE',1,5),tx('INTEREST',1,1000,'2027-01-01')],Date.parse(context().calculated_at)),99205);
const ctx=context();ctx.accounts[0].initial_cash=100;ctx.transactions=[tx('BUY',2,100)];
assert.equal(planner.plan(ctx,request,adapters).status,'unavailable');
''')


def test_planning_context_rejects_concurrent_ledger_changes(monkeypatch):
    signatures = iter(["old", "new"])
    monkeypatch.setattr(main, "portfolio_cache_signature", lambda: next(signatures))
    monkeypatch.setattr(main, "portfolio_payload", lambda **kw: {"items": []})
    monkeypatch.setattr(main, "planner_security", lambda *args: (None, "listing_unverified"))
    monkeypatch.setattr(main, "fx", lambda: {"quotes": []})
    monkeypatch.setattr(main, "local_store", type("Store", (), {"list_accounts": lambda _: [], "list_transactions": lambda _: []})())
    with pytest.raises(main.HTTPException) as exc:
        main.trade_planner_context("AAPL")
    assert exc.value.status_code == 409


def test_unheld_stock_requires_verified_listing_and_dated_provider_prices():
    class Hub:
        def quote(self, symbol):
            return {"exchange": "NASDAQ", "price": 123}, {}

        def profile(self, symbol, **kwargs):
            return {"name": "Example", "industry": "Technology"}, {}

        def prices(self, *args, **kwargs):
            day = date.today() - timedelta(days=1)
            return [Ohlcv(day, 120, 124, 119, 123, 123, 100)], {}

    security, reason = planner_security("NEW", "NASDAQ", [], Hub(), main._stock_market_key, main.US_STOCK_MARKETS)
    assert reason is None
    assert security["price_ranges"]["1m"]["current"] == 123
    assert security["price_ranges"]["1m"]["current_date"] == (date.today() - timedelta(days=1)).isoformat()
    assert planner_security("NEW", "NYSE", [], Hub(), main._stock_market_key, main.US_STOCK_MARKETS) == (None, "listing_unverified")
