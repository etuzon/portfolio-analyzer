"""Investment analytics must never infer account eligibility from stock labels."""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.investment_scope import InvestmentStoreView, investments
from app.models import Holding, Ohlcv
from app.correlation import portfolio_correlation
from app.dividend_calendar import build_dividend_calendar
from app.xray import XrayError, build_xray, require_fund
from app.benchmark import BenchmarkError
from app.benchmark_data import benchmark_inputs

TODAY = date(2026, 11, 3)


class Store:
    def __init__(self):
        self.accounts = [{"id":"i","type":"Investment","currency":"USD"},
                         {"id":"e","type":"ESOP","currency":"USD"},
                         {"id":"b","type":"Bank","currency":"USD"},
                         {"id":"l","type":"Long-Term Savings","currency":"USD"},
                         {"id":"u","currency":"USD"}]
        # Spoofing holding.account_type is deliberately insufficient.
        self.positions = [Holding(symbol=key.upper(),account_id=key,stock_market="NASDAQ",asset_class="ETF",account_type="Investment",quantity=10)
                          for key in ["i","e","b","l","u","missing"]]
        self.prefs = {}
    def list_accounts(self): return self.accounts
    def holdings(self): return [SimpleNamespace(holding=h) for h in self.positions]
    def list_transactions(self): return [{"id":r.account_id,"account_db_id":r.account_id} for r in self.positions]
    def list_funds(self): return [{"account_id":r.account_id} for r in self.positions]
    def list_account_snapshots(self,*args): return [{"account_db_id":r.account_id,"snapshot_date":"2026-11-01","value":100} for r in self.positions]
    def get_preference(self,key,default=None): return self.prefs.get(key,default)
    def set_preference(self,key,value): self.prefs[key]=value
    def manual_security(self,*args): return None
    def price_history(self,*args): return []


class Hub:
    def cached_prices(self,*args,**kwargs):
        return [Ohlcv(TODAY-timedelta(days=i),10,10,10,10,10,1) for i in range(40)],{}
    def cached_view(self): return self
    def dividend_calendar(self,*args,**kwargs): return {"items":[],"provider":None,"updated_at":None}
    def latest_price(self,*args,**kwargs): return None


def test_authoritative_account_type_filters_every_financial_collection_and_tracks_reclassification():
    raw=Store();view=investments(raw)
    assert isinstance(view,InvestmentStoreView) and investments(view) is view
    assert [a['id'] for a in view.list_accounts()]==['i']
    assert [a.holding.account_id for a in view.holdings()]==['i']
    assert [a['account_db_id'] for a in view.list_transactions()]==['i']
    assert [a['account_db_id'] for a in view.list_account_snapshots({})]==['i']
    assert [a['account_id'] for a in view.list_funds()]==['i']
    view.set_preference('saved',1);assert raw.prefs['saved']==1
    raw.accounts[0]['type']='ESOP'
    assert view.list_accounts()==view.holdings()==view.list_transactions()==[]


def test_correlation_xray_dividends_and_benchmark_include_only_investments():
    raw=Store();hub=Hub()
    assert [r['symbol'] for r in portfolio_correlation(raw,hub,today=TODAY)['assets']]==['I']
    xray=build_xray(raw,today=TODAY)
    assert xray['fund_count']==1 and [r['symbol'] for r in xray['funds']]==['I']
    dividends=build_dividend_calendar(raw,hub,today=TODAY)
    assert [r['symbol'] for r in dividends['assets']]==['I']
    benchmark=benchmark_inputs(raw)
    assert [r['id'] for r in benchmark['accounts']]==['i']
    assert benchmark['suggested_valuations']==[{'date':'2026-11-01','value':100}]
    assert raw.accounts[1]['type']=='ESOP'  # no source mutation


def test_stale_holding_account_label_cannot_override_authoritative_investment_account():
    raw=Store()
    raw.positions[0].account_type='ESOP'
    data=build_dividend_calendar(raw,Hub(),today=TODAY)
    assert [row['symbol'] for row in data['assets']]==['I']


@pytest.mark.parametrize('account_id',['e','b','l','u','missing'])
def test_explicit_excluded_account_ids_cannot_bypass_scope(account_id):
    raw=Store();hub=Hub()
    with pytest.raises(ValueError,match='unknown_account'): portfolio_correlation(raw,hub,account_id=account_id)
    with pytest.raises(ValueError,match='unknown_dividend_account'): build_dividend_calendar(raw,hub,account_id=account_id)
    with pytest.raises(XrayError,match='xray_unknown_account'): build_xray(raw,account_id=account_id)
    with pytest.raises(BenchmarkError,match='benchmark_unknown_account'): benchmark_inputs(raw,account_id)
    with pytest.raises(XrayError,match='xray_fund_not_held'): require_fund(raw,account_id.upper(),'NASDAQ')
