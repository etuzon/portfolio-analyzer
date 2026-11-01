"""Independent financial and frozen-snapshot checks for the simulator.

UI checks execute the actual scripts in a synthetic DOM, not a real browser.
"""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import main
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


def test_pending_snapshot_survives_account_market_fx_and_background_updates():
    run_ui('''
(async()=>{
 tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:'2',priceInput:'',fee:'0'}];
 const captured=JSON.parse(JSON.stringify(ctx));
 const calculation=calculateTradeSimulation();
 state.localAccounts[0].initial_cash=4000;
 state.localTransactions=[{account_db_id:'one',action:'DEPOSIT',amount:3000}];
 state.allPortfolioItems=[{holding:{symbol:'NEW',quantity:100,market_value:20000}}];
 state.fxRates=[{pair:'USD/ILS',quote:{rate:9}}];
 state.baseCurrency='ILS';state.refreshPending=true;state.portfolioRefreshState='refreshing';
 renderTradeSimulator();
 assert.equal(tradeSimulatorView.status,'loading');
 assert.equal(nodes.runTradeSimulator.disabled,true);
 pending[0].resolve(captured);await calculation;
 assert.equal(tradeSimulatorView.status,'ready');
 assert.equal(tradeSimulatorView.result.accounts[0].before.cash,1000);
 assert.equal(tradeSimulatorView.result.accounts[0].after.cash,800);
 assert.equal(tradeSimulatorView.result.total.after.netValue,1000);
 assert.equal(tradeSimulatorView.result.baseCurrency,'USD');
 assert.equal(Number(tradeSimulatorView.result.trades[0].quantity),2);
 assert.equal(calls,1);
})();
''')


def test_actual_dashboard_load_preserves_pending_and_completed_simulation():
    source = (Path(__file__).resolve().parents[1] / "web/app.js").read_text()
    start = source.index("let portfolioEnrichmentRetryTimer")
    end = source.index("\nasync function loadLocalOptions", start)
    run_ui('''
const HISTORY_START_DATE='2020-01-01';
const todayString=()=> '2026-11-01';
const setTimeout=()=> 17;
const clearTimeout=()=>{};
const setLoading=()=>{};
const appLog=()=>{};
const appWarn=()=>{};
const portfolioItems=items=>items;
const isEquityCompAccount=()=>false;
const populateOptions=()=>{};
const renderPortfolio=()=>renderTradeSimulator();
const renderMacroScenario=()=>{};
const hasActivePortfolioFilter=()=>false;
const setCoreFxRates=data=>{state.fxRates=data.quotes;};
nodes.status={textContent:''};nodes.macroScenarioModal={hidden:true};
async function dashboardRefresh(cash,refreshPending){
 const offset=pending.length;
 const update=loadPortfolio();
 pending[offset].resolve({count:1,items:[{holding:{symbol:'NEW',quantity:cash/10,market_value:cash}}],refresh_pending:refreshPending});
 pending[offset+1].resolve({accounts:[]});
 pending[offset+2].resolve({quotes:[{pair:'USD/ILS',quote:{rate:cash/100}}]});
 pending[offset+3].resolve({items:[{id:'one',account_id:'A1',type:'Investment',currency:'USD',initial_cash:cash}]});
 pending[offset+4].resolve({items:[{account_db_id:'one',action:'DEPOSIT',amount:cash-1000}]});
 pending[offset+5].resolve({items:[],industries:[]});
 await update;
 assert.equal(state.localAccounts[0].initial_cash,cash);
}
(async()=>{
 tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:'2',priceInput:'',fee:'0'}];
 const captured=JSON.parse(JSON.stringify(ctx));
 const calculation=calculateTradeSimulation();
 await dashboardRefresh(4000,true);
 assert.equal(tradeSimulatorView.status,'loading');
 await dashboardRefresh(6000,false);
 assert.equal(tradeSimulatorView.status,'loading');
 pending[0].resolve(captured);await calculation;
 assert.equal(tradeSimulatorView.status,'ready');
 assert.equal(tradeSimulatorView.result.accounts[0].before.cash,1000);
 const result=JSON.stringify(tradeSimulatorView.result);
 await dashboardRefresh(9000,false);
 assert.equal(tradeSimulatorView.status,'ready');
 assert.equal(JSON.stringify(tradeSimulatorView.result),result);
})();
''', integration_source=source[start:end])


def test_actual_modal_reopen_keeps_snapshot_while_loading_changed_accounts():
    source = (Path(__file__).resolve().parents[1] / "web/app.js").read_text()
    start = source.index("function openModal(")
    end = source.index("\nfunction closeModal(", start)
    run_ui('''
const HTMLElement=class {};
const modalReturnFocus=new Map();
const mountModalHomeLink=()=>{};
const focusModalDestination=()=>{};
nodes.tradeSimulatorModal={hidden:true};nodes.tradeSimulatorStatus={textContent:''};
let accountLoad;
const loadLocalAccounts=()=>accountLoad=api('/api/local/accounts').then(data=>{state.localAccounts=data.items;});
(async()=>{
 tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:'2',priceInput:'',fee:'0'}];
 const captured=JSON.parse(JSON.stringify(ctx));
 const calculation=calculateTradeSimulation();
 openModal('tradeSimulatorModal');
 pending[1].resolve({items:[{id:'one',account_id:'A1',type:'Investment',currency:'USD',initial_cash:9000}]});
 await accountLoad;await Promise.resolve();
 assert.equal(tradeSimulatorView.status,'loading');
 pending[0].resolve(captured);await calculation;
 const frozen=JSON.stringify(tradeSimulatorView.result);
 nodes.tradeSimulatorModal.hidden=true;
 openModal('tradeSimulatorModal');pending[2].resolve({items:[]});
 await accountLoad;await Promise.resolve();
 assert.equal(tradeSimulatorView.status,'ready');
 assert.equal(JSON.stringify(tradeSimulatorView.result),frozen);
 assert.equal(tradeSimulatorView.result.accounts[0].before.cash,1000);
 assert.equal(tradeSimulatorRows[0].quantity,'2');
})();
''', integration_source=source[start:end])


def test_completed_snapshot_survives_refresh_language_change_and_deleted_live_account():
    run_ui('''
(async()=>{
 tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:'2',priceInput:'',fee:'0'}];
 const calculation=calculateTradeSimulation();pending[0].resolve(JSON.parse(JSON.stringify(ctx)));await calculation;
 const frozen=JSON.stringify(tradeSimulatorView.result);
 state.localAccounts=[];state.localTransactions=[];state.allPortfolioItems=[];
 state.fxRates=[{pair:'USD/ILS',quote:{rate:9}}];state.baseCurrency='ILS';
 for(const language of ['en','he','en']){
  state.language=language;state.portfolioRefreshState='ready';renderTradeSimulator();
  assert.equal(tradeSimulatorView.status,'ready');
  assert.equal(JSON.stringify(tradeSimulatorView.result),frozen);
  const text=nodes.tradeSimulatorResults.innerHTML.replace(/<[^>]*>/g,'');
  assert.ok(text.includes('30/10/2026'));
  assert.ok(text.includes('A1'));
  if(language==='en'){
   assert.ok(text.includes('Snapshot captured'));
   assert.ok(text.includes('frozen'));assert.ok(!/[א-ת]/.test(text));
  }else{
   assert.ok(!/Snapshot captured|Before|After|frozen|Simulate trades|Calculated/.test(text));
  }
 }
 assert.equal(calls,1);
})();
''')


def test_explicit_simulate_refreshes_context_and_preserves_original_result_values():
    run_ui('''
(async()=>{
 tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:'2',priceInput:'',fee:'0'}];
 const first=calculateTradeSimulation();pending[0].resolve(JSON.parse(JSON.stringify(ctx)));await first;
 const previous=tradeSimulatorView.result;
 const nextContext=JSON.parse(JSON.stringify(ctx));nextContext.accounts[0].initial_cash=2000;
 nextContext.securities[0].security.price_ranges['1m'].current=150;
 nextContext.calculated_at='2026-11-01T14:20:00Z';
 const second=calculateTradeSimulation();assert.equal(calls,2);
 pending[1].resolve(nextContext);await second;
 assert.equal(tradeSimulatorView.result.accounts[0].before.cash,2000);
 assert.equal(tradeSimulatorView.result.accounts[0].after.cash,1700);
 assert.equal(tradeSimulatorView.result.trades[0].price,150);
 assert.equal(tradeSimulatorView.result.calculatedAt,'2026-11-01T14:20:00Z');
 assert.equal(previous.accounts[0].before.cash,1000);
 assert.equal(previous.accounts[0].after.cash,800);
})();
''')


@pytest.mark.parametrize("late_outcome", ["resolve(ctx)", "reject(new Error('private provider error'))"])
def test_basket_edit_invalidates_old_response_even_after_new_calculation_finishes(late_outcome):
    run_ui('''
(async()=>{
 tradeSimulatorRows=[{id:'1',accountId:'one',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:'2',priceInput:'',fee:'0'}];
 const first=calculateTradeSimulation();
 const edited={dataset:{simulationField:'quantity'},value:'3',closest:()=>({dataset:{simulationRow:'1'}})};
 for(const handler of handlers.input) handler({target:edited});
 assert.equal(tradeSimulatorView.status,'stale');
 assert.equal(nodes.runTradeSimulator.disabled,false);
 const second=calculateTradeSimulation();pending[1].resolve(ctx);await second;
 assert.equal(tradeSimulatorView.status,'ready');
 assert.equal(tradeSimulatorView.result.accounts[0].after.cash,700);
 const current=JSON.stringify(tradeSimulatorView.result);
 pending[0].LATE_OUTCOME;await first;
 assert.equal(tradeSimulatorView.status,'ready');
 assert.equal(JSON.stringify(tradeSimulatorView.result),current);
 assert.equal(tradeSimulatorRows[0].quantity,'3');
})();
'''.replace("LATE_OUTCOME", late_outcome))


@pytest.mark.parametrize("change_phase", ["listing_lookup", "fx_lookup"])
def test_coherent_backend_snapshot_survives_later_ledger_changes(monkeypatch, change_phase):
    live = {
        "signature": "captured-ledger",
        "accounts": [{"id": "one", "type": "Investment", "initial_cash": 1000}],
        "transactions": [],
    }
    snapshot = {"items": [{"holding": {"symbol": "NEW", "quantity": 2}}], "refresh_pending": True}
    entered_lookup = []

    class Store:
        def list_accounts(self):
            return deepcopy(live["accounts"])

        def list_transactions(self):
            return deepcopy(live["transactions"])

    def update_live_ledger():
        live["signature"] = "new-ledger"
        live["accounts"][0]["initial_cash"] = 9000
        live["transactions"].append({"action": "DEPOSIT", "amount": 8000})

    def lookup(*args):
        entered_lookup.append(datetime.now(timezone.utc))
        if change_phase == "listing_lookup":
            update_live_ledger()
        return {"holding": {"symbol": "NEW"}}, None

    def quotes():
        if change_phase == "fx_lookup":
            update_live_ledger()
        return {"quotes": [{"pair": "USD/ILS", "quote": {"rate": 4}}]}

    monkeypatch.setattr(main, "local_store", Store())
    monkeypatch.setattr(main, "portfolio_cache_signature", lambda: live["signature"])
    monkeypatch.setattr(main, "portfolio_payload", lambda **kw: deepcopy(snapshot))
    monkeypatch.setattr(main, "planner_security", lookup)
    monkeypatch.setattr(main, "hub", lambda: object())
    monkeypatch.setattr(main, "fx", quotes)
    result = main.trade_simulator_context({"securities": [{"symbol": "NEW", "stock_market": "NASDAQ"}]})
    assert result["signature"] == "captured-ledger"
    assert result["accounts"][0]["initial_cash"] == 1000
    assert result["transactions"] == []
    assert result["items"] == snapshot["items"]
    assert result["refresh_pending"] is True
    assert datetime.fromisoformat(result["calculated_at"]) <= entered_lookup[0]
    assert result["fx_quotes"][0]["quote"]["rate"] == 4
    assert live["signature"] == "new-ledger"
