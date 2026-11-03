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
    def list_accounts(self): return [{"id":"a", "account_id":"First"}, {"id":"b", "account_id":"Second"}]
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
    result=calc(Store([holding(),holding(stock_market="TASE",currency="ILS"),holding(currency="EUR"),holding("BOND",asset_class="BOND")]))
    assert len(result["assets"])==3 and len({row["id"] for row in result["assets"]})==3
    assert result["excluded"][0]["symbol"]=="BOND"
    assert result["excluded"][0]["reason"]=="unsupported_asset"
    eur=next(row for row in result["assets"] if row["currency"]=="EUR")
    assert eur["gross_value_ils"] is None and "missing_price" in eur["issues"]


@pytest.mark.parametrize("fx,code",[({},"missing_fx"),({"USD":{"rates":[{"date":"2026-10-01","rate":4}]}},"stale_fx")])
def test_missing_fx_prevents_size_but_native_price_move_remains(fx,code):
    asset,=calc(fx=fx)["assets"]
    assert asset["gross_value_ils"] is None and code in asset["issues"]
    assert asset["change_percent"]==pytest.approx(10)


@pytest.mark.parametrize("rows,code",[(prices(days=(10,9)),"stale_price"),(prices(days=(20,0)),"sparse_prices"),(prices(values=(100,),days=(0,)),"missing_previous_price"),([],"missing_price")])
def test_missing_or_stale_price_never_invents_zero_change(rows,code):
    asset,=calc(hub=Hub(rows))["assets"]
    assert asset["change_percent"] is None and code in asset["issues"]
    if code in {"stale_price","missing_price"}: assert asset["gross_value_ils"] is None
    else: assert asset["gross_value_ils"] is not None


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
