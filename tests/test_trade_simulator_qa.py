"""Independent financial boundary checks for the whole-basket simulator."""

import pytest

from test_trade_simulator import run_simulation
from test_trade_simulator_frontend import run_ui


def test_duplicate_existing_positions_merge_without_changing_the_source():
    run_simulation('''
const ctx=simulationContext();ctx.items=[stock('NEW',2000),stock('NEW',3000)];
const before=JSON.stringify(ctx);
const result=simulator.simulate(ctx,[trade({action:'SELL',quantity:50,fee:5})],adapters);
assert.equal(result.status,'ok');
assert.equal(result.accounts[0].before.grossExposure,5000);
assert.equal(result.accounts[0].after.grossExposure,0);
assert.equal(result.accounts[0].after.cash,104995);
assert.equal(result.accounts[0].after.netValue,104995);
assert.equal(JSON.stringify(ctx),before);
''')


def test_same_symbol_other_listing_is_not_available_to_sell():
    run_simulation('''
const ctx=simulationContext();
const old=stock('NEW',5000);old.holding.stock_market='NYSE';old.exchange='NYSE';ctx.items=[old];
const result=simulator.simulate(ctx,[trade({action:'SELL',quantity:1})],adapters);
assert.equal(result.status,'invalid');
assert.equal(result.errors[0].reason,'sell_exceeds_holding');
assert.equal(result.total,null);
''')


def test_existing_short_partial_cover_and_full_cover_preserve_signed_equity():
    run_simulation('''
const ctx=simulationContext();ctx.items=[stock('NEW',-2000)];
ctx.accounts[0].initial_cash=102000;
const result=simulator.simulate(ctx,[trade({quantity:5,priceInput:90,fee:2}),trade({id:'finish',quantity:15,priceInput:110,fee:3})],adapters);
assert.equal(result.status,'ok');
assert.equal(result.accounts[0].before.netValue,100000);
assert.equal(result.accounts[0].before.availableCash,null);
assert.equal(result.trades[0].quantityAfter,-15);
assert.equal(result.trades[1].quantityAfter,0);
assert.equal(result.accounts[0].after.shortExposure,0);
assert.equal(result.accounts[0].after.cash,99895);
assert.equal(result.accounts[0].after.netValue,99895);
assert.equal(result.accounts[0].after.availableCash,99895);
''')


def test_full_sale_before_short_keeps_cash_and_exposure_in_row_order():
    run_simulation('''
const ctx=simulationContext();ctx.items=[stock('NEW',2000)];
const result=simulator.simulate(ctx,[trade({action:'SELL',quantity:20}),trade({id:'short',action:'SHORT',quantity:7,fee:1})],adapters);
assert.equal(result.status,'ok');
assert.equal(result.trades[0].quantityAfter,0);
assert.equal(result.trades[1].quantityAfter,-7);
assert.equal(result.accounts[0].after.cash,102699);
assert.equal(result.accounts[0].after.shortExposure,700);
assert.equal(result.accounts[0].after.grossExposure,700);
assert.equal(result.accounts[0].after.netValue,101999);
assert.equal(result.accounts[0].after.availableCash,null);
''')


@pytest.mark.parametrize("action", ["ADD", "REMOVE"])
def test_future_noncash_position_changes_do_not_establish_current_quantities(action):
    run_simulation('''
const ctx=simulationContext();ctx.items=[stock('NEW',1000)];
ctx.transactions=[{account_db_id:'us1',action:'ACTION',quantity:10,price:100,currency:'USD',trade_date:'2027-01-01'}];
const result=simulator.simulate(ctx,[trade({action:'SELL',quantity:1})],adapters);
assert.equal(result.status,'invalid');
assert.equal(result.errors[0].reason,'future_transactions');
'''.replace("ACTION", action))


def test_manual_israeli_bond_execution_uses_existing_agorot_convention():
    run_simulation('''
const ctx=simulationContext();ctx.accounts[0].currency='ILS';ctx.base_currency='ILS';
const security=ctx.securities[0].security;
security.holding.stock_market='MANUAL';security.exchange='MANUAL';
security.holding.currency='ILS';security.holding.location='Israel';security.holding.asset_class='BOND';
ctx.securities[0].stock_market='';
const result=simulator.simulate(ctx,[trade({market:'',priceInput:10000,quantity:1})],adapters);
assert.equal(result.status,'ok');
assert.equal(result.trades[0].price,100);
assert.equal(result.accounts[0].after.cash,99900);
''')


def test_session_reset_discards_late_private_simulation_response():
    run_ui('''
(async()=>{
 tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:'2',priceInput:'',fee:'0'}];
 const calculation=calculateTradeSimulation();
 resetTradeSimulator();
 pending[0].resolve(ctx);await calculation;
 assert.equal(tradeSimulatorRows.length,0);
 assert.equal(tradeSimulatorView,null);
 assert.equal(nodes.tradeSimulatorResults.innerHTML,'');
 assert.equal(nodes.runTradeSimulator.disabled,true);
})();
''')
