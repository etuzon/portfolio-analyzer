"""Whole-basket financial checks using the actual dashboard risk calculation."""
import json
from datetime import date, datetime, timezone

import pytest
from starlette.requests import Request

from app import main
from app.local_portfolio import LocalPortfolioStore
from app.trade_planner import planner_security
from test_trade_planner import run_planner_js


def run_simulation(body):
    return run_planner_js(r'''
const simulator=require('./web/trade-simulator.js');
const simulationContext=()=>({...context(),securities:[{symbol:'NEW',stock_market:'NASDAQ',security:stock('NEW')}]});
const trade=(overrides={})=>({id:'r1',accountId:'us1',symbol:'NEW',market:'NASDAQ',action:'BUY',quantity:10,priceInput:'',fee:0,...overrides});
''' + body)


def test_basket_reuses_cash_and_quantities_across_rows_and_keeps_accounts_separate():
    run_simulation('''
const ctx=simulationContext();ctx.accounts.push(account('second','USA',5000));
const source=JSON.stringify(ctx);
const result=simulator.simulate(ctx,[trade(),trade({id:'r2',quantity:5}),trade({id:'r3',action:'SELL',quantity:3,fee:2}),trade({id:'r4',accountId:'second',quantity:2})],adapters);
assert.equal(result.status,'ok',JSON.stringify(result));
assert.equal(result.accounts[0].before.cash,100000);
assert.equal(result.accounts[0].after.cash,98798);
assert.equal(result.accounts[0].after.netValue,99998);
assert.equal(result.accounts[1].after.cash,4800);
assert.equal(result.total.after.cash,103598);
assert.equal(result.total.after.netValue,104998);
assert.equal(result.trades[2].quantityAfter,12);
assert.ok(Number.isFinite(result.total.after.risk.score));
assert.equal(JSON.stringify(ctx),source);
''')


def test_listed_rsu_shares_replay_cisco_buy_and_followup_sell_short():
    run_simulation('''
const ctx=simulationContext();ctx.accounts[0].initial_cash=250000;
const security=stock('CSCO',2000);security.holding.asset_class='RSU';
ctx.items=[security];ctx.securities=[{symbol:'CSCO',stock_market:'NASDAQ',security}];
const source=JSON.stringify(ctx);
const buy=trade({symbol:'CSCO',quantity:1000,priceInput:101});
let result=simulator.simulate(ctx,[buy],adapters);
assert.equal(result.status,'ok',JSON.stringify(result));
assert.equal(result.accounts[0].after.cash,149000);
assert.equal(result.accounts[0].after.netValue,251000);
assert.equal(result.trades[0].quantityAfter,1020);
assert.ok(Number.isFinite(result.accounts[0].after.risk.score));
result=simulator.simulate(ctx,[trade({symbol:'CSCO',action:'SELL',quantity:20}),trade({id:'short',symbol:'CSCO',action:'SHORT',quantity:10,priceInput:101})],adapters);
assert.equal(result.status,'ok');
assert.equal(result.accounts[0].after.cash,253010);
assert.equal(result.accounts[0].after.shortExposure,1000);
assert.equal(result.accounts[0].after.availableCash,null);
assert.equal(JSON.stringify(ctx),source);
''')


def test_rsu_class_never_overrides_derivative_subclass_or_esop_account():
    run_simulation('''
const ctx=simulationContext();ctx.securities[0].security.holding.asset_class='RSU';
for(const subclass of ['OPTION','FUTURE','STOCK_OPTION','EMPLOYEE_STOCK_OPTION']){
 ctx.securities[0].security.holding.asset_sub_class=subclass;
 const result=simulator.simulate(ctx,[trade()],adapters);
 assert.equal(result.status,'invalid');assert.equal(result.errors[0].reason,'unsupported_instrument');
}
ctx.securities[0].security.holding.asset_sub_class='';ctx.accounts[0].type='ESOP';
assert.equal(simulator.simulate(ctx,[trade()],adapters).errors[0].reason,'account_type');
ctx.accounts[0].type='Investment';ctx.securities[0].security.holding.asset_class='PRIVATE_STOCK';
assert.equal(simulator.simulate(ctx,[trade()],adapters).errors[0].reason,'unsupported_asset_class');
''')


def test_short_proceeds_preserve_equity_and_do_not_become_buying_power():
    run_simulation('''
const ctx=simulationContext();
let result=simulator.simulate(ctx,[trade({action:'SHORT',quantity:20,fee:3})],adapters);
assert.equal(result.accounts[0].after.cash,101997);
assert.equal(result.accounts[0].after.netValue,99997);
assert.equal(result.accounts[0].after.grossExposure,2000);
assert.equal(result.accounts[0].after.shortExposure,2000);
assert.equal(result.accounts[0].after.availableCash,null);
assert.equal(result.total.after.availableCash,null);
result=simulator.simulate(ctx,[trade({action:'SHORT',quantity:20}),trade({id:'cover',quantity:25})],adapters);
assert.equal(result.accounts[0].after.cash,99500);
assert.equal(result.accounts[0].after.netValue,100000);
assert.equal(result.accounts[0].after.shortExposure,0);
assert.equal(result.trades[1].quantityAfter,5);
''')


@pytest.mark.parametrize("rows,reason", [
    ("[trade({action:'SELL'})]", "sell_exceeds_holding"),
    ("[trade(),trade({action:'SELL',quantity:11})]", "sell_exceeds_holding"),
    ("[trade(),trade({action:'SHORT'})]", "existing_long"),
    ("[trade({quantity:0})]", "invalid_trade"),
    ("[trade({priceInput:'invalid'})]", "invalid_trade"),
    ("[trade({quantity:1e308,priceInput:1e308})]", "invalid_trade"),
    ("[trade({fee:-1})]", "invalid_trade"),
])
def test_invalid_basket_never_publishes_partial_results(rows, reason):
    run_simulation(f'''
const result=simulator.simulate(simulationContext(),{rows},adapters);
assert.equal(result.status,'invalid');
assert.equal(result.errors[0].reason,'{reason}');
assert.equal(result.accounts.length,0);
assert.equal(result.total,null);
''')


def test_saved_valuation_is_distinct_from_execution_and_fees():
    run_simulation('''
const ctx=simulationContext();ctx.items=[stock('NEW',2000)];
const result=simulator.simulate(ctx,[trade({priceInput:120,fee:7})],adapters);
assert.equal(result.accounts[0].before.netValue,102000);
assert.equal(result.accounts[0].after.cash,98793);
assert.equal(result.accounts[0].after.netValue,101793);
assert.equal(result.trades[0].priceDate,null);
assert.equal(result.trades[0].price,120);
''')


def test_execution_price_never_becomes_invented_market_valuation():
    run_simulation('''
const ctx=simulationContext();ctx.securities[0].security.price_ranges={};
const result=simulator.simulate(ctx,[trade({priceInput:120})],adapters);
assert.equal(result.status,'ok');
assert.equal(result.accounts[0].after.cash,98800);
assert.equal(result.accounts[0].after.netValue,null);
assert.equal(result.accounts[0].after.grossExposure,null);
assert.equal(result.accounts[0].after.risk,null);
assert.equal(result.accounts[0].after.reason,'valuation_unavailable');
assert.equal(result.total.after.risk,null);
''')


def test_tase_and_us_bond_input_units_and_multicurrency_totals():
    run_simulation('''
const ctx=simulationContext();ctx.base_currency='ILS';ctx.fx_quotes=[{pair:'USD/ILS',quote:{rate:4}}];
ctx.accounts.push(account('il','Israel',10000,'ILS'));
const israeli=stock('LOCAL',0,'il','Finance','ILS');israeli.holding.stock_market='TASE';israeli.exchange='TASE';
ctx.securities.push({symbol:'LOCAL',stock_market:'TASE',security:israeli});
let result=simulator.simulate(ctx,[trade({accountId:'il',symbol:'LOCAL',market:'TASE',quantity:2,priceInput:12345})],adapters);
assert.equal(result.status,'ok');assert.equal(result.trades[0].price,123.45);
assert.equal(result.accounts[1].after.cash,9753.1);
assert.equal(result.total.before.cash,410000);
assert.equal(result.total.after.cash,409753.1);
const bond=stock('BOND');bond.holding.asset_class='BOND';
assert.equal(simulator.priceDivisor(bond),100);
result=simulator.simulate(ctx,[trade({accountId:'il'})],adapters);
assert.equal(result.errors[0].reason,'account_currency');
''')


def test_missing_evidence_keeps_known_account_cash_and_blocks_unjustified_risk():
    run_simulation('''
const ctx=simulationContext();ctx.accounts.push(account('other','USA',3000));
const missing=stock('OLD',2000,'other');missing.price_ranges={};ctx.items=[missing];
let result=simulator.simulate(ctx,[trade()],adapters);
assert.equal(result.status,'ok');assert.ok(result.accounts[0].after.risk);
assert.equal(result.accounts[1].after.cash,3000);
assert.equal(result.accounts[1].after.netValue,null);
assert.equal(result.accounts[1].after.risk,null);
assert.equal(result.total.after.cash,102000);
assert.equal(result.total.after.netValue,null);
assert.equal(result.total.after.risk,null);
ctx.items=[];ctx.accounts[0].initial_cash=100;
result=simulator.simulate(ctx,[trade()],adapters);
assert.equal(result.accounts[0].after.cash,-900);
assert.equal(result.accounts[0].after.reason,null);
assert.ok(Number.isFinite(result.accounts[0].after.risk.score));
assert.ok(Number.isFinite(result.total.after.risk.score));
ctx.accounts[0].initial_cash=100000;
ctx.transactions=[{account_db_id:'us1',action:'BUY',currency:'ILS',quantity:1,price:10,trade_date:'2026-10-28'}];
result=simulator.simulate(ctx,[trade()],adapters);
assert.equal(result.accounts[0].after.cash,null);
assert.equal(result.total.after.cash,null);
''')


def test_no_fx_no_fake_zero():
    run_simulation('''
const ctx=simulationContext();ctx.base_currency='ILS';
let result=simulator.simulate(ctx,[trade()],adapters);
assert.equal(result.accounts[0].after.cash,99000);
assert.equal(result.accounts[0].after.netValue,100000);
assert.equal(result.total.after.netValue,null);
assert.equal(result.total.after.cash,null);
assert.equal(result.total.after.risk,null);
''')


def test_future_purchase_cannot_create_current_holdings_or_mint_cash(tmp_path):
    store = LocalPortfolioStore(tmp_path / "future.sqlite3")
    account = store.save_account({"type": "Investment", "currency": "USD", "initial_cash": 10000,
                                  "persons": [{"name": "Fixture Owner", "birth_date": "01/01/1980"}]})
    store.add_transaction({"account_db_id": account["id"], "action": "BUY", "symbol": "NEW", "stock_market": "NASDAQ",
                           "quantity": 10, "price_input": 100, "currency": "USD", "trade_date": "01/01/2027"})
    raw = {"accounts": store.list_accounts(), "transactions": store.list_transactions(),
           "items": [main.to_dict(item) for item in store.holdings()]}
    run_simulation('''
const raw=''' + json.dumps(raw) + ''';
const ctx={...simulationContext(),...raw};
const rejected=simulator.simulate(ctx,[trade({accountId:ctx.accounts[0].id,action:'SELL'})],adapters);
assert.equal(rejected.status,'invalid');
assert.equal(rejected.errors[0].reason,'future_transactions');
ctx.accounts.push(account('safe','USA',2000));
const safe=simulator.simulate(ctx,[trade({accountId:'safe',quantity:1})],adapters);
assert.equal(safe.status,'ok');
assert.equal(safe.accounts[0].before.cash,10000);
assert.equal(safe.accounts[0].before.netValue,null);
assert.equal(safe.accounts[1].after.cash,1900);
assert.equal(safe.total.after.risk,null);
''')


def test_unheld_saved_bonds_resolve_without_provider_or_ledger_mutation(tmp_path):
    store = LocalPortfolioStore(tmp_path / "bonds.sqlite3")
    store.save_manual_security({"symbol": "BOND", "name": "Fixture Bond", "stock_market": "NASDAQ",
                                "instrument_type": "BOND", "currency": "USD", "location": "USA"})
    store.save_price({"symbol": "BOND", "stock_market": "NASDAQ", "currency": "USD", "location": "USA",
                      "asset_class": "BOND", "price_input": 12345, "price_date": date.today().isoformat()})
    before = store.price_history("BOND", "NASDAQ")
    resolved, reason = planner_security("BOND", "NASDAQ", [], object(), main._stock_market_key,
                                       main.US_STOCK_MARKETS, store, {"EQUITY", "ETF", "BOND", "MUTUALFUND"})
    assert reason is None
    assert resolved["holding"]["asset_class"] == "BOND"
    assert resolved["price_ranges"]["1m"]["current"] == pytest.approx(123.45)
    assert store.price_history("BOND", "NASDAQ") == before
    assert store.list_transactions() == []


def test_quote_dates_and_unknown_account_attribution_are_honest():
    run_simulation('''
const ctx=simulationContext();for(const range of Object.values(ctx.securities[0].security.price_ranges)) range.current_date='2026-10-01';
const result=simulator.simulate(ctx,[trade()],adapters);
assert.equal(result.warnings[0].reason,'price_stale');
assert.equal(result.trades[0].priceDate,'2026-10-01');
ctx.items=[stock('ORPHAN',500,'missing')];
const orphan=simulator.simulate(ctx,[trade()],adapters);
assert.equal(orphan.total.after.reason,'unknown_account');
assert.equal(orphan.total.after.netValue,null);
''')


def test_context_is_deduplicated_read_only_and_one_snapshot(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "portfolio_cache_signature", lambda: "same")
    monkeypatch.setattr(main, "portfolio_payload", lambda **kw: {"items": [], "refresh_pending": True})
    monkeypatch.setattr(main, "planner_security", lambda symbol, market, *args: (calls.append((symbol, market)) or {"holding": {"symbol": symbol}}, None))
    monkeypatch.setattr(main, "fx", lambda: {"quotes": []})
    monkeypatch.setattr(main, "local_store", type("ReadOnlyStore", (), {"list_accounts": lambda _: [], "list_transactions": lambda _: []})())
    result = main.trade_simulator_context({"securities": [{"symbol": "NEW", "stock_market": "NASDAQ"}] * 2})
    assert calls == [("NEW", "NASDAQ")]
    assert len(result["securities"]) == 1
    assert result["signature"] == "same"
    assert result["refresh_pending"] is True
    request = Request({"type": "http", "method": "POST", "path": "/api/trade-simulator/context", "headers": []})
    assert main._viewer_request_is_read_only(request)


def test_context_http_requires_auth_and_allows_viewer_without_ledger_writes(tmp_path, monkeypatch):
    from test_auth import _auth_environment, _client, _login, _change_password

    auth = _auth_environment(tmp_path, monkeypatch)
    auth.create_user({"first_name": "Fixture", "last_name": "Viewer", "username": "sim-viewer", "password": "fixture-password-1", "role": "Viewer"})
    monkeypatch.setattr(main, "portfolio_cache_signature", lambda: "same")
    monkeypatch.setattr(main, "portfolio_payload", lambda **kw: {"items": []})
    monkeypatch.setattr(main, "planner_security", lambda *args: (None, "listing_unverified"))
    monkeypatch.setattr(main, "fx", lambda: {"quotes": []})
    client = _client()
    payload = {"securities": [{"symbol": "NEW", "stock_market": "NASDAQ"}]}
    assert client.post("/api/trade-simulator/context", json=payload).status_code == 401
    session = _change_password(client, _login(client, "sim-viewer", "fixture-password-1"),
                               "fixture-password-1", "fixture-new-password-1")
    before = main.local_store.list_transactions()
    result = client.post("/api/trade-simulator/context", json=payload, headers={"X-CSRF-Token": session["csrf_token"]})
    assert result.status_code == 200
    assert result.json()["securities"][0]["reason"] == "listing_unverified"
    assert main.local_store.list_transactions() == before


def test_context_rejects_changes_during_initial_snapshot_capture(monkeypatch):
    signatures = iter(["before", "after"])
    monkeypatch.setattr(main, "portfolio_cache_signature", lambda: next(signatures))
    monkeypatch.setattr(main, "portfolio_payload", lambda **kw: {"items": []})
    monkeypatch.setattr(main, "planner_security", lambda *args: (None, "listing_unverified"))
    monkeypatch.setattr(main, "fx", lambda: {"quotes": []})
    monkeypatch.setattr(main, "local_store", type("Store", (), {"list_accounts": lambda _: [], "list_transactions": lambda _: []})())
    with pytest.raises(main.HTTPException) as exc:
        main.trade_simulator_context({"securities": [{"symbol": "NEW"}]})
    assert exc.value.status_code == 409


def test_snapshot_is_private_and_survives_changes_after_capture(monkeypatch):
    accounts = [{"id": "fixture", "type": "Investment", "currency": "USD", "initial_cash": 1000}]
    transactions = [{"account_db_id": "fixture", "action": "BUY", "quantity": 2, "price": 100}]
    items = [{"holding": {"symbol": "NEW", "quantity": 2}}]
    source = {"version": "captured", "lookup_started": False}
    captured_at = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)

    class CaptureClock:
        @staticmethod
        def now(tz):
            assert not source["lookup_started"], "capture time must precede slow lookup"
            return captured_at

    def resolve(symbol, market, saved, *args):
        source.update(version="later", lookup_started=True)
        accounts[0]["initial_cash"] = 5000
        transactions[0]["quantity"] = 20
        items[0]["holding"]["quantity"] = 20
        return saved[0], None

    monkeypatch.setattr(main, "datetime", CaptureClock)
    monkeypatch.setattr(main, "portfolio_cache_signature", lambda: source["version"])
    monkeypatch.setattr(main, "portfolio_payload", lambda **kw: {"items": items})
    monkeypatch.setattr(main, "local_store", type("Store", (), {"list_accounts": lambda _: accounts, "list_transactions": lambda _: transactions})())
    monkeypatch.setattr(main, "planner_security", resolve)
    monkeypatch.setattr(main, "fx", lambda: {"quotes": []})
    result = main.trade_simulator_context({"securities": [{"symbol": "NEW"}]})
    assert result["signature"] == "captured"
    assert result["calculated_at"] == captured_at.isoformat()
    assert result["accounts"][0]["initial_cash"] == 1000
    assert result["transactions"][0]["quantity"] == 2
    assert result["items"][0]["holding"]["quantity"] == 2
    assert result["securities"][0]["security"]["holding"]["quantity"] == 2


@pytest.mark.parametrize("payload", [{}, {"securities": []}, {"securities": [None]}, {"securities": [{"symbol": "bad symbol"}]}, {"securities": [{"symbol": "NEW", "stock_market": "BAD"}]}])
def test_context_validates_before_reading_providers(payload):
    with pytest.raises(main.HTTPException) as exc:
        main.trade_simulator_context(payload)
    assert exc.value.status_code == 422
