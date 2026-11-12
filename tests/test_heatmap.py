from copy import deepcopy
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.heatmap import stock_heatmap
from app.models import Holding, Ohlcv

TODAY = date(2026, 11, 3)


def holding(symbol="AAA", **kwargs):
    return Holding(symbol=symbol, account_id=kwargs.pop("account_id", "a"),
                   stock_market=kwargs.pop("stock_market", "NASDAQ"), currency=kwargs.pop("currency", "USD"),
                   asset_class=kwargs.pop("asset_class", "EQUITY"), quantity=kwargs.pop("quantity", 10), **kwargs)


def prices(values=(100, 110), days=(1, 0)):
    return [Ohlcv(TODAY-timedelta(days=day), value, value, value, value, value/2, 1)
            for value, day in zip(values, days)]


class Store:
    def __init__(self, positions=None, local=None, manual=None):
        self.positions = [holding()] if positions is None else positions
        self.local, self.manual = local or [], manual
    def holdings(self): return [SimpleNamespace(holding=row) for row in self.positions]
    def list_accounts(self): return [{"id":"a", "type":"Investment", "account_id":"First"}, {"id":"b", "type":"Investment", "account_id":"Second"}]
    def manual_security(self, *args): return self.manual
    def price_history(self, *args): return deepcopy(self.local)


class Hub:
    def __init__(self, rows=None): self.rows=prices() if rows is None else rows; self.calls=[]
    def cached_prices(self, *args, **kwargs): self.calls.append(kwargs); return self.rows, {}
    def prices(self, *args, **kwargs): raise AssertionError("No download allowed")
    def fx(self, *args, **kwargs): raise AssertionError("No FX download allowed")


def calc(store=None, hub=None, fx=None, **kwargs):
    return stock_heatmap(store or Store(), hub or Hub(), {"USD":{"source":"Fixture", "rates":[{"date":TODAY.isoformat(),"rate":4}]}} if fx is None else fx, today=TODAY, **kwargs)


def test_combined_same_listing_uses_gross_exposure_without_netting_accounts():
    result=calc(Store([holding(), holding(account_id="b", quantity=-4)]))
    asset,=result["assets"]
    assert asset["quantity"]==6 and asset["gross_quantity"]==14
    assert asset["gross_value_ils"]==6160 and asset["value_ils"]==2640
    assert [row["gross_value_ils"] for row in asset["accounts"]]==[4400,1760]
    assert asset["change_percent"]==pytest.approx(10)
    assert asset["basis"]=="close" and asset["status"]=="ok"


def test_per_account_has_same_dates_move_and_only_its_own_exposure():
    store=Store([holding(),holding(account_id="b",quantity=20)])
    result=calc(store,account_id="b")
    asset,=result["assets"]
    assert asset["gross_value_ils"]==8800 and asset["quantity"]==20
    assert asset["accounts"][0]["account_id"]=="b"
    assert asset["previous_date"]=="2026-11-02" and asset["price_date"]=="2026-11-03"
    with pytest.raises(ValueError,match="heatmap_unknown_account"): calc(store,account_id="unknown")


def test_market_currency_identity_and_disallowed_assets_are_not_merged():
    result=calc(Store([holding(),holding(stock_market="TASE",currency="ILS"),holding(currency="EUR"),holding("OPTION",asset_class="OPTION")]))
    assert len(result["assets"])==3 and len({row["id"] for row in result["assets"]})==3
    assert result["excluded"][0]["symbol"]=="OPTION"
    assert result["excluded"][0]["reason"]=="unsupported_asset"
    eur=next(row for row in result["assets"] if row["currency"]=="EUR")
    assert eur["gross_value_ils"] is None and "missing_price" in eur["issues"]


@pytest.mark.parametrize("fx,code",[({},"missing_fx"),({"USD":{"rates":[{"date":"2026-10-01","rate":4}]}},"stale_fx")])
def test_missing_fx_prevents_size_but_last_known_fx_can_size_a_marked_holding(fx,code):
    asset,=calc(fx=fx)["assets"]
    assert code in asset["issues"]
    if code == "missing_fx":
        assert asset["gross_value_ils"] is None
    else:
        assert asset["gross_value_ils"] == 4400
        assert asset["valuation_status"] == "stale"
    assert asset["change_percent"]==pytest.approx(10)


@pytest.mark.parametrize('short_basis',[400,-400])
def test_unrealized_profit_is_signed_and_scoped_without_netting_costs(short_basis):
    store=Store([holding(cost_basis=1000),holding(account_id='b',quantity=-4,cost_basis=short_basis)])
    asset,=calc(store)['assets']
    assert asset['unrealized_pnl_native']==pytest.approx(60)
    assert asset['unrealized_pnl_ils']==pytest.approx(240)
    assert [row['unrealized_pnl_native'] for row in asset['accounts']]==[100,-40]
    assert [row['unrealized_pnl_ils'] for row in asset['accounts']]==[400,-160]
    short,=calc(store,account_id='b')['assets']
    assert short['quantity']==-4 and short['unrealized_pnl_native']==-40


@pytest.mark.parametrize('basis',[float('nan'),float('inf'),True])
def test_invalid_cost_basis_does_not_hide_a_priced_holding_or_invent_profit(basis):
    asset,=calc(Store([holding(cost_basis=basis)]))['assets']
    assert asset['gross_value_ils']==4400
    assert asset['cost_basis_native'] is None and asset['unrealized_pnl_native'] is None
    assert asset['unrealized_pnl_ils'] is None
    assert asset['accounts'][0]['pnl_status']=='invalid_cost_basis'


def test_native_profit_remains_available_without_fx_but_stale_quotes_have_no_profit():
    asset,=calc(Store([holding(cost_basis=1000)]),fx={})['assets']
    assert asset['unrealized_pnl_native']==100 and asset['unrealized_pnl_ils'] is None
    stale,=calc(Store([holding(cost_basis=1000)]),Hub(prices(days=(10,9))))['assets']
    assert stale['unrealized_pnl_native'] is None and stale['unrealized_pnl_ils'] is None


def test_bonds_use_saved_normalized_per_unit_prices_and_recorded_basis():
    local=[{'currency':'USD','asset_class':'BOND','price_date':'2026-11-02','price':1.0},
           {'currency':'USD','asset_class':'BOND','price_date':'2026-11-03','price':1.02}]
    store=Store([holding('SYNTHBOND',asset_class='BOND',stock_market='MANUAL',quantity=100,cost_basis=100)],local,manual={})
    result=calc(store,Hub([]))
    asset,=result['assets']
    assert not result['excluded'] and asset['asset_class']=='BOND'
    assert asset['price']==1.02 and asset['gross_value_ils']==408
    assert asset['change_percent']==pytest.approx(2)
    assert asset['unrealized_pnl_native']==pytest.approx(2)
    assert asset['unrealized_pnl_ils']==pytest.approx(8)


def test_verified_cached_company_name_fills_missing_name_without_replacing_user_name():
    hub=Hub()
    hub.cached_view=lambda:SimpleNamespace(profile=lambda *args,**kwargs:({'exchange':'Nasdaq','currency':'USD','name':'Synthetic issuer <company>'},{}))
    asset,=calc(Store([holding(stock_market='YAHOO')]),hub)['assets']
    assert asset['name']=='Synthetic issuer <company>'
    named,=calc(Store([holding(stock_market='YAHOO',name='Recorded name')]),hub)['assets']
    assert named['name']=='Recorded name'
    hub.cached_view=lambda:SimpleNamespace(profile=lambda *args,**kwargs:({'exchange':'Nasdaq','currency':'EUR','name':'Unrelated issuer'},{}))
    missing,=calc(Store([holding(stock_market='YAHOO')]),hub)['assets']
    assert missing['name']=='AAA' and missing['gross_value_ils'] is None


@pytest.mark.parametrize("rows,code",[(prices(days=(10,9)),"stale_price"),(prices(days=(20,0)),"sparse_prices"),(prices(values=(100,),days=(0,)),"missing_previous_price"),([],"missing_price")])
def test_missing_or_stale_price_never_invents_zero_change(rows,code):
    asset,=calc(hub=Hub(rows))["assets"]
    assert asset["change_percent"] is None and code in asset["issues"]
    if code == "missing_price": assert asset["gross_value_ils"] is None
    else: assert asset["gross_value_ils"] is not None


def test_actual_ils_fund_without_prices_and_old_us_bond_keep_known_gross_weights(tmp_path):
    from app.local_portfolio import LocalPortfolioStore
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    def account(currency, location):
        return store.save_account({"type":"Investment", "account_id":"Synthetic heatmap",
            "location":location, "currency":currency,
            "persons":[{"name":"Synthetic", "birth_date":"01/01/1990"}]})
    ils, usd = account("ILS", "Israel"), account("USD", "USA")
    store.add_transaction({"account_db_id":ils["id"], "symbol":"5139324", "stock_market":"TASE",
        "asset_class":"MUTUALFUND", "action":"BUY", "quantity":100,
        "price_input":1000, "trade_date":"2026-11-02"})
    store.add_transaction({"account_db_id":usd["id"], "symbol":"SYNTHBOND", "stock_market":"MANUAL",
        "asset_class":"BOND", "action":"BUY", "quantity":1000,
        "price_input":70, "trade_date":"2026-07-01"})
    store.save_price({"symbol":"SYNTHBOND", "stock_market":"MANUAL", "asset_class":"BOND",
        "location":"USA", "currency":"USD", "price_input":75, "price_date":"2026-07-31"})
    before, token = store.export_data(), store.change_token()
    result = calc(store, Hub([]))
    fund = next(row for row in result["assets"] if row["symbol"] == "5139324")
    bond = next(row for row in result["assets"] if row["symbol"] == "SYNTHBOND")
    assert fund["gross_value_ils"] == 1000
    assert fund["valuation_basis"] == "cost_basis" and fund["valuation_status"] == "estimated"
    assert fund["price"] is None and fund["change_percent"] is None
    assert fund["unrealized_pnl_native"] is None and "estimated_value" in fund["issues"]
    assert bond["price"] == .75 and bond["gross_value_ils"] == 3000
    assert bond["price_date"] == "2026-07-31" and bond["valuation_status"] == "stale"
    assert bond["change_percent"] is None and bond["unrealized_pnl_native"] is None
    total = sum(row["gross_value_ils"] for row in result["assets"])
    assert fund["gross_value_ils"] / total == .25 and bond["gross_value_ils"] / total == .75
    assert result["account_assets"][ils["id"]][0]["gross_value_ils"] == 1000
    assert not result["excluded"]
    assert store.export_data()["data"] == before["data"] and store.change_token() == token


def test_last_known_bond_price_keeps_absolute_short_and_long_exposure():
    local=[{"currency":"USD","asset_class":"BOND","price_date":"2026-07-31","price":.75}]
    positions=[holding("BOND",stock_market="MANUAL",asset_class="BOND",quantity=1000),
               holding("BOND",account_id="b",stock_market="MANUAL",asset_class="BOND",quantity=-500)]
    bond,=calc(Store(positions,local),Hub([]))["assets"]
    assert bond["gross_value_ils"] == 4500 and bond["value_ils"] == 1500
    assert bond["valuation_status"] == "stale" and bond["change_percent"] is None


@pytest.mark.parametrize("asset_class", ["EQUITY", "STOCK", "RSU", "ETF", "MUTUALFUND", "BOND"])
def test_recorded_values_can_size_each_supported_security_without_a_quote(asset_class):
    position=holding(asset_class=asset_class,market_value=250,cost_basis=200)
    asset,=calc(Store([position]),Hub([]))["assets"]
    assert asset["gross_value_ils"] == 1000
    assert asset["valuation_basis"] == "recorded_value" and asset["valuation_status"] == "estimated"
    assert asset["price"] is None and asset["change_percent"] is None
    assert asset["unrealized_pnl_native"] is None


@pytest.mark.parametrize("price_patch", [{"currency":"EUR"},{"asset_class":"ETF"},{"price_date":"2026-11-04"},{"price":-1}])
def test_recorded_fallback_cannot_bypass_rejected_local_price_evidence(price_patch):
    local=[{"currency":"USD","asset_class":"EQUITY","price_date":"2026-11-03","price":100,**price_patch}]
    asset,=calc(Store([holding(market_value=1000,cost_basis=900)],local),Hub([]))["assets"]
    assert asset["gross_value_ils"] is None and asset["valuation_status"] == "unavailable"
    assert asset["change_percent"] is None and "estimated_value" not in asset["issues"]


def test_recorded_value_never_replaces_missing_fx_or_identity_conflicts():
    position=holding(market_value=1000,cost_basis=900)
    asset,=calc(Store([position]),Hub([]),fx={})["assets"]
    assert asset["gross_value_ils"] is None and "missing_fx" in asset["issues"]
    conflicting=calc(Store([position,holding(account_id="b",asset_class="ETF",market_value=1000)]),Hub([]))
    assert conflicting["assets"][0]["gross_value_ils"] is None
    assert "classification_conflict" in conflicting["assets"][0]["issues"]


def test_zero_quantity_with_residual_cost_cannot_invent_exposure():
    asset,=calc(Store([holding(quantity=0,market_value=1000,cost_basis=1000)]),Hub([]))["assets"]
    assert asset["gross_value_ils"] is None and asset["value_ils"] is None
    assert asset["valuation_status"] == "unavailable" and asset["change_percent"] is None


def test_local_raw_override_never_mixes_adjusted_values_and_normalized_ils_no_fx():
    local=[{"currency":"ILS","asset_class":"EQUITY","price_date":"2026-11-02","price":2},
           {"currency":"ILS","asset_class":"EQUITY","price_date":"2026-11-03","price":2.2}]
    asset,=calc(Store([holding(currency="ILS",stock_market="TASE")],local,manual={}),Hub([]),fx={})["assets"]
    assert asset["gross_value_ils"]==22 and asset["change_percent"]==pytest.approx(10)
    assert asset["basis"]=="close"


def test_fx_snapshot_validates_pair_date_rate_and_uses_newest_observation():
    cache=SimpleNamespace(get_security_snapshot=lambda provider,pair,kind:{"pair":pair,"time":"2026-11-03 12:00:00","rate":3})
    hub=Hub();hub.cache=cache;hub.providers=[SimpleNamespace(name="cached_fixture")]
    result=calc(hub=hub,fx={"USD":{"rates":[{"date":"2026-11-02","rate":4},{"date":"2026-11-04","rate":999}]}})
    assert result["assets"][0]["gross_value_ils"]==3300
    assert result["fx"][0]["source"]=="cached_fixture"
    cache.get_security_snapshot=lambda *a:{"pair":"EUR/ILS","time":"2026-11-03","rate":3}
    assert calc(hub=hub,fx={})["assets"][0]["gross_value_ils"] is None


@pytest.mark.parametrize("quantity",[float('nan'),float('inf'),1e308])
def test_invalid_and_overflow_exposure_never_returns_nonfinite_amount(quantity):
    asset,=calc(Store([holding(quantity=quantity)]))["assets"]
    assert asset["gross_value_ils"] is None
    assert set(asset["issues"]) & {"invalid_position","invalid_value"}


def test_empty_scope_and_classification_conflict():
    assert calc(Store([]))["status"]=="empty"
    asset,=calc(Store([holding(),holding(asset_class="ETF",account_id="b")]))["assets"]
    assert "classification_conflict" in asset["issues"] and asset["gross_value_ils"] is None


@pytest.mark.parametrize("exchange,currency,accepted",[("Nasdaq",None,True),("NYSE","USD",True),("NYSE","EUR",False),(None,None,False),("LSE","USD",False)])
def test_import_source_label_uses_only_verified_saved_exchange_metadata(exchange,currency,accepted):
    hub=Hub()
    hub.cached_view=lambda:SimpleNamespace(profile=lambda *args,**kwargs:({"exchange":exchange,"currency":currency},{}))
    result=calc(Store([holding(stock_market="YAHOO")]),hub)
    asset,=result['assets']
    if accepted:
        assert asset['gross_value_ils']==4400 and asset['change_percent']==pytest.approx(10)
        assert asset['resolved_stock_market']==exchange.upper()
        assert all(call['stock_market']==exchange.upper() for call in hub.calls)
    else:
        assert asset['gross_value_ils'] is None and asset['change_percent'] is None
        assert 'unverified_listing' in asset['issues'] and not hub.calls


def test_investment_account_membership_controls_holdings_not_stale_holding_labels():
    store=Store([holding(account_id='a',account_type='ESOP'),holding('OUTSIDE',account_id='b',account_type='Investment')])
    store.list_accounts=lambda:[{'id':'a','type':'Investment'},{'id':'b','type':'ESOP'}]
    result=calc(store)
    assert [row['id'] for row in result['accounts']]==['a']
    assert [row['symbol'] for row in result['assets']]==['AAA']
    assert list(result['account_assets'])==['a']
    with pytest.raises(ValueError,match='heatmap_unknown_account'): calc(store,account_id='b')


@pytest.mark.parametrize("bad",[holding(account_id="b",quantity=float('nan')),holding(account_id="b",asset_class="ETF")])
def test_single_account_and_panels_are_independent_of_other_accounts_bad_data(bad):
    store=Store([holding(),bad])
    combined=calc(store)
    assert combined['assets'][0]['gross_value_ils'] is None
    assert combined['account_assets']['a']==calc(store,account_id='a')['assets']
    assert combined['account_assets']['a'][0]['gross_value_ils']==4400


def test_recent_quote_reader_prefers_latest_saved_date_over_longer_old_history(tmp_path):
    from app.providers import MarketDataHub, SqliteCache
    cache=SqliteCache(tmp_path/'cache.sqlite3',24)
    cache.set_prices('alpha_vantage','AAA',prices(values=[80]*13,days=range(20,7,-1)))
    cache.set_prices('financial_modeling_prep','AAA',prices())
    hub=MarketDataHub.__new__(MarketDataHub)
    hub.cache=cache
    hub.providers=[SimpleNamespace(name='alpha_vantage'),SimpleNamespace(name='financial_modeling_prep')]
    result=calc(hub=hub)
    asset,=result['assets']
    assert asset['price_date']==TODAY.isoformat() and asset['price']==110
    assert asset['gross_value_ils']==4400 and asset['change_percent']==pytest.approx(10)


def test_authenticated_viewer_can_read_and_filter_without_mutating_portfolio(monkeypatch,tmp_path):
    from fastapi.testclient import TestClient
    from app import main
    from app.auth import AuthStore
    from app.local_portfolio import LocalPortfolioStore

    store=LocalPortfolioStore(tmp_path/'portfolio.sqlite3')
    account=store.save_account({"type":"Investment","account_id":"Heatmap fixture","location":"Israel","currency":"ILS","initial_cash":1000,"persons":[{"name":"Synthetic","birth_date":"01/01/1990"}]})
    store.add_transaction({"account_db_id":account["id"],"symbol":"HEATQA","stock_market":"TASE","asset_class":"EQUITY","action":"BUY","quantity":10,"price_input":100,"trade_date":TODAY.isoformat()})
    for day,amount in [(TODAY-timedelta(days=1),100),(TODAY,110)]:
        store.save_price({"symbol":"HEATQA","stock_market":"TASE","asset_class":"EQUITY","location":"Israel","currency":"ILS","price_input":amount,"price_date":day.isoformat()})
    auth=AuthStore(store.path);auth.initialize()
    user=auth.create_user({"username":"heatqa","first_name":"Synthetic","last_name":"Viewer","role":"Viewer","password":"Heat-Fixture123!"})
    with auth._connect() as conn: conn.execute('update app_users set must_change_password=0 where id=?',(user['id'],))
    monkeypatch.setattr(main,'local_store',store);monkeypatch.setattr(main,'auth_store',auth);monkeypatch.setattr(main,'hub',lambda:Hub([]))
    # The HTTP route uses the same fixed observation date as this fixture.
    monkeypatch.setattr(main, 'stock_heatmap', lambda *args, **kwargs: stock_heatmap(*args, today=TODAY, **kwargs))
    client=TestClient(main.app,base_url='https://localhost:6443')
    assert client.get('/api/portfolio/heatmap').status_code==401
    assert client.post('/api/auth/login',json={"username":"heatqa","password":"Heat-Fixture123!"}).status_code==200
    before=deepcopy(store.export_data()['data'])
    result=client.get('/api/portfolio/heatmap').json()
    asset,=result['assets']
    assert result['status']=='ok' and asset['gross_value_ils']==11
    assert asset['change_percent']==pytest.approx(10)
    assert client.get('/api/portfolio/heatmap',params={'account_id':account['id']}).json()['assets']==result['assets']
    assert client.get('/api/portfolio/heatmap?account_id=missing').status_code==400
    assert store.export_data()['data']==before
