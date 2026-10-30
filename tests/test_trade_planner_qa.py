"""Independent QA for listing evidence, financial validity, and sizing boundaries."""
from datetime import date

import pytest

from app import main
from app.local_portfolio import LocalPortfolioStore
from app.models import Ohlcv
from app.trade_planner import planner_security
from test_trade_planner import run_planner_js


class ListingHub:
    def __init__(self, quote, profile):
        self.quote_data = quote
        self.profile_data = profile

    def quote(self, symbol):
        return self.quote_data, {}

    def profile(self, symbol, **kwargs):
        return self.profile_data, {}

    def prices(self, *args, **kwargs):
        return [Ohlcv(date.today(), 100, 100, 100, 100, 100, 1)], {}


def resolve(quote, profile, market="NASDAQ"):
    return planner_security("EXAMPLE", market, [], ListingHub(quote, profile),
                            main._stock_market_key, main.US_STOCK_MARKETS)


def test_specific_verified_listing_survives_generic_us_quote():
    item, reason = resolve({"exchange": "US", "currency": "USD"},
                           {"exchange": "NASDAQ", "currency": "USD"})
    assert reason is None
    assert item["holding"]["stock_market"] == "NASDAQ"


@pytest.mark.parametrize("other_listing", ["NYSE", "TASE", "LSE"])
def test_conflicting_concrete_exchange_evidence_is_not_a_verified_us_listing(other_listing):
    item, reason = resolve({"exchange": other_listing, "symbol": "EXAMPLE"},
                           {"exchange": "NASDAQ", "currency": "USD"})
    assert item is None
    assert reason == "listing_unverified"


def test_verified_unheld_tase_uses_shekel_currency():
    item, reason = resolve({"exchange": "TLV", "currency": "ILS"},
                           {"exchange": "TASE", "currency": "ILS"}, "TASE")
    assert reason is None
    assert item["holding"]["currency"] == "ILS"
    assert item["price_ranges"]["1m"]["current_date"] == date.today().isoformat()
    assert resolve({"exchange": "TLV", "currency": "USD"}, {}, "TASE") == (None, "listing_unverified")


def test_saved_unheld_tase_preserves_normalized_local_price_and_raw_history(tmp_path):
    store = LocalPortfolioStore(tmp_path / "planner-qa.sqlite3")
    store.save_manual_security({"symbol": "EXAMPLE", "name": "Example", "stock_market": "TASE",
                                "instrument_type": "EQUITY", "asset_class": "EQUITY",
                                "currency": "ILS", "location": "Israel"})
    store.save_price({"symbol": "EXAMPLE", "stock_market": "TASE", "currency": "ILS",
                      "location": "Israel", "asset_class": "EQUITY", "price_input": 12345,
                      "price_date": date.today().isoformat()})
    before = store.price_history("EXAMPLE", "TASE")
    item, reason = planner_security("EXAMPLE", "TASE", [], object(), main._stock_market_key,
                                    main.US_STOCK_MARKETS, local_store=store)
    assert reason is None
    assert item["holding"]["currency"] == "ILS"
    assert item["price_ranges"]["1m"]["current"] == pytest.approx(123.45)
    assert store.price_history("EXAMPLE", "TASE") == before


def test_unsupported_targets_and_hidden_derivative_subclasses_never_get_a_trade():
    run_planner_js('''
for (const asset of ['BOND','RSU','CASH','OPTION','FUTURE','EMPLOYEE_STOCK_OPTION']) {
  const ctx=context();ctx.security.holding.asset_class=asset;
  assert.equal(planner.plan(ctx,request,adapters).reason,'unsupported_instrument',asset);
}
const ctx=context();ctx.security.holding.asset_sub_class='OPTION';
assert.equal(planner.plan(ctx,request,adapters).reason,'unsupported_instrument');
''')


@pytest.mark.parametrize("quantity,value", [(10, -1000), (-10, 1000), (0, 1000)])
def test_inconsistent_position_signs_cannot_inflate_or_distort_the_sizing_base(quantity, value):
    run_planner_js(f'''
const ctx=context();ctx.accounts.push(account('other','USA',100000,'USD','Bank'));
const bad=stock('BAD',{value},'other');bad.holding.quantity={quantity};ctx.items=[bad];
assert.equal(planner.plan(ctx,request,adapters).reason,'valuation_unavailable');
''')


def test_stale_local_valuation_is_repriced_from_recent_quotes_without_mutating_inputs():
    run_planner_js('''
const ctx=context();ctx.accounts.push(account('bank','USA',100000,'USD','Bank'));
const stale=stock('OLD',1000,'bank');stale.holding.quantity=100;ctx.items=[stale];
const before=JSON.stringify(ctx);
const actual=planner.plan(ctx,request,adapters);
assert.equal(actual.status,'ok',JSON.stringify(actual));
assert.equal(JSON.stringify(ctx),before,'planning must preserve saved financial evidence');
const fresh=JSON.parse(before);fresh.items[0].holding.market_value=10000;
const expected=planner.plan(fresh,request,adapters);
assert.equal(actual.recommendation.amount,expected.recommendation.amount);
assert.equal(actual.recommendation.riskAfter,expected.recommendation.riskAfter);
''')


def test_future_debits_and_fees_reduce_cash_while_future_proceeds_cannot_fund_a_trade():
    run_planner_js('''
const tx=(action,quantity,price)=>({account_db_id:'us1',action,quantity,price,currency:'USD',trade_date:'2027-01-01'});
const now=Date.parse(context().calculated_at);
assert.equal(planner.cashBalance(account(),[tx('BUY',100,100),tx('FEE',1,50),tx('SELL',1000,100)],now),89950);
const ctx=context();ctx.accounts[0].initial_cash=100;
ctx.transactions=[tx('SELL',1000,100),tx('DIVIDEND',1,100000)];
assert.equal(planner.plan(ctx,request,adapters).status,'unavailable');
''')


def test_account_choice_is_stable_and_ineligible_or_encumbered_accounts_cannot_win():
    run_planner_js('''
const ctx=context();
ctx.accounts=[account('encumbered','USA',10000000),account('foreign','Israel',10000000),account('fund','USA',10000000,'USD','Long-Term Savings'),account('eligible')];
ctx.items=[stock('SHORT',-1000,'encumbered')];
let result=planner.plan(ctx,request,adapters);
assert.equal(result.status,'ok',JSON.stringify(result));
assert.equal(result.recommendation.account.id,'eligible');
assert.equal(result.excluded.find(e=>e.account.id==='encumbered').reason,'collateral_unverified');
const originalAmount=result.recommendation.amount;
ctx.accounts.reverse();ctx.items.reverse();
result=planner.plan(ctx,request,adapters);
assert.equal(result.recommendation.account.id,'eligible');
assert.equal(result.recommendation.amount,originalAmount);
assert.ok(result.recommendation.cashRemaining>=result.recommendation.reserve);
''')
