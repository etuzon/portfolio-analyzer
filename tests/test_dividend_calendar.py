from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
import time

from fastapi.testclient import TestClient
import pytest

from app import main
from app.auth import AuthStore
from app.dividend_calendar import build_dividend_calendar
from app.models import Holding, Ohlcv
from app.providers import FmpProvider, MarketDataHub, SqliteCache

TODAY = date.today()


class Store:
    def __init__(self):
        self.positions = [Holding(symbol=symbol, stock_market="NASDAQ", account_id=account, account_type="Investment", asset_class="EQUITY", quantity=quantity)
                          for symbol, account, quantity in [("AAA","a",2),("AAA","b",200),("BBB","a",3),("CCC","a",4),("EMPTY","a",5)]]
        self.local = {}; self.transactions = []
    def holdings(self):return [SimpleNamespace(holding=h) for h in self.positions]
    def list_accounts(self):return [{"id":"a","account_id":"First"},{"id":"b","account_id":"Second"}]
    def list_transactions(self):return self.transactions
    def manual_security(self,*_args):return None
    def price_history(self,symbol,market,*_args):return self.local.get((symbol,market),[])


@pytest.fixture
def evidence(tmp_path):
    hub=object.__new__(MarketDataHub)
    def network(*_args,**_kwargs):raise AssertionError("Calendar must not contact providers")
    hub.providers=[SimpleNamespace(name="financial_modeling_prep",prices=network,dividends=network),SimpleNamespace(name="yahoo_finance",prices=network,dividends=network)]
    hub.cache=SqliteCache(tmp_path/"market.sqlite3",ttl_hours=1)
    store=Store()
    for symbol,amount,price in [("AAA",1,100),("BBB",5,200),("CCC",.5,50)]:
        offsets=[500,300,200,100,10] if symbol!="BBB" else [500,10]
        rows=[{"date":(TODAY-timedelta(days=days)).isoformat(),"payment_date":(TODAY-timedelta(days=days-7)).isoformat(),"amount":amount} for days in offsets]
        hub.cache.set_security_snapshot("financial_modeling_prep",symbol,"dividends",rows)
        hub.cache.set_prices("financial_modeling_prep",symbol,[Ohlcv(TODAY,price,price,price,price,price/2,1)])
    return store,hub


def result(evidence,**kwargs):return build_dividend_calendar(*evidence,today=TODAY,**kwargs)
def asset(data,symbol):return next(row for row in data["assets"] if row["symbol"]==symbol)


def test_annual_yield_uses_full_trailing_sum_raw_price_and_all_highest_ties(evidence):
    data=result(evidence)
    a,b,c=[asset(data,s) for s in ["AAA","BBB","CCC"]]
    assert a["ttm_dividend_per_share"]==4 and a["annual_yield_percent"]==4
    assert b["ttm_dividend_per_share"]==5 and b["annual_yield_percent"]==2.5
    assert c["annual_yield_percent"]==4
    assert a["highest_yield"] and c["highest_yield"] and not b["highest_yield"]
    assert len([row for row in data["assets"] if row["symbol"]=="AAA"])==1
    assert a["price"]==100  # never adjusted close 50, cost basis or today's quantity
    assert asset(data,"EMPTY")["annual_yield_percent"] is None
    assert asset(data,"EMPTY")["year_dividend_per_share"] is None


def test_payments_ex_dates_future_records_and_historical_year_totals_are_distinct(evidence):
    store,hub=evidence
    existing=hub.cache.get_security_snapshot("financial_modeling_prep","AAA","dividends")
    hub.cache.set_security_snapshot("financial_modeling_prep","AAA","dividends",existing+[
        {"date":"2024-01-10","payment_date":"2024-01-20","amount":1},
        {"date":"2024-04-10","amount":2},
        {"date":"2024-12-25","payment_date":"2025-01-04","amount":3},
        {"date":(TODAY+timedelta(days=30)).isoformat(),"payment_date":(TODAY+timedelta(days=37)).isoformat(),"amount":9},
    ])
    historical=result(evidence,year=2024)
    a=asset(historical,"AAA")
    assert a["year_dividend_per_share"]==3 and a["ttm_dividend_per_share"]==4
    january=next(row for row in historical["events"] if row["date"]=="2024-01-20")
    april=next(row for row in historical["events"] if row["date"]=="2024-04-10")
    assert january["date_type"]=="payment" and april["date_type"]=="ex_date"
    data=result(evidence,year=(TODAY+timedelta(days=37)).year)
    assert any(row["future"] and row["amount_per_share"]==9 for row in data["events"])
    assert asset(data,"AAA")["annual_yield_percent"]==4  # no future dividends in trailing yield


def test_duplicate_records_keep_payment_metadata_without_double_counting(evidence):
    store,hub=evidence
    rows=hub.cache.get_security_snapshot("financial_modeling_prep","AAA","dividends")
    copy=dict(rows[-1]);copy.pop("payment_date")
    hub.cache.set_security_snapshot("financial_modeling_prep","AAA","dividends",rows+[copy,dict(rows[-1])])
    data=result(evidence)
    assert asset(data,"AAA")["ttm_dividend_per_share"]==4
    matching=[row for row in data["events"] if row["asset_id"]=="AAA@NASDAQ" and row["ex_date"]==rows[-1]["date"]]
    assert len(matching)==1 and matching[0]["date_type"]=="payment"


def test_latest_saved_quote_across_providers_overrides_longer_stale_history(evidence):
    store,hub=evidence
    old=[Ohlcv(TODAY-timedelta(days=days),100,100,100,100,100,1) for days in range(20,7,-1)]
    hub.cache.set_prices("financial_modeling_prep","AAA",old)
    # Remove today's primary quote so the regression has an older longest series.
    with hub.cache._connect() as conn:conn.execute("delete from price_cache where provider=? and symbol=? and date=?",("financial_modeling_prep","AAA",TODAY.isoformat()))
    hub.cache.set_prices("yahoo_finance","AAA",[Ohlcv(TODAY,50,50,50,50,50,1)])
    a=asset(result(evidence),"AAA")
    assert a["price"]==50 and a["annual_yield_percent"]==8 and a["highest_yield"]


def test_local_price_override_requires_matching_currency(evidence):
    store,hub=evidence
    store.local[("AAA","NASDAQ")]=[{"price_date":TODAY.isoformat(),"price":400,"currency":"ILS"}]
    a=asset(result(evidence),"AAA")
    assert a["price"]==100 and a["annual_yield_percent"]==4 and a["invalid_prices"]==1
    store.local[("AAA","NASDAQ")][0]["currency"]="USD"
    a=asset(result(evidence),"AAA")
    assert a["price"]==400 and a["annual_yield_percent"]==1 and a["price_source"]=="local"


def test_recorded_income_uses_actual_ledger_amounts_scope_and_separate_currencies(evidence):
    store,hub=evidence
    day=TODAY.isoformat()
    store.transactions=[{"account_db_id":account,"symbol":"AAA","stock_market":"NASDAQ","action":"DIVIDEND","trade_date":day,"quantity":quantity,"price":price,"currency":currency}
                        for account,quantity,price,currency in [("a",2,10,"USD"),("b",3,10,"ILS")]]
    store.transactions.append({**store.transactions[0],"trade_date":(TODAY+timedelta(days=1)).isoformat(),"price":999})
    a=asset(result(evidence),"AAA")
    assert a["recorded_income"]==[{"currency":"ILS","amount":30},{"currency":"USD","amount":20}]
    assert asset(result(evidence,account_id="a"),"AAA")["recorded_income"]==[{"currency":"USD","amount":20}]


def test_ledger_only_dates_are_labeled_and_never_invent_a_per_share_yield(evidence):
    store,hub=evidence
    store.transactions=[{"account_db_id":"a","symbol":"EMPTY","stock_market":"NASDAQ","action":"DIVIDEND","trade_date":TODAY.isoformat(),"quantity":7,"price":3,"currency":"USD"}]
    data=result(evidence);e=next(row for row in data["events"] if row["asset_id"]=="EMPTY@NASDAQ")
    assert e["date_type"]=="ledger" and e["recorded_amount"]==21 and e["amount_per_share"] is None
    assert asset(data,"EMPTY")["annual_yield_percent"] is None


def test_partial_stale_and_missing_inputs_do_not_get_highest_badges(evidence):
    store,hub=evidence
    rows=hub.cache.get_security_snapshot("financial_modeling_prep","AAA","dividends")
    hub.cache.set_security_snapshot("financial_modeling_prep","AAA","dividends",rows[1:])
    with hub.cache._connect() as conn:conn.execute("update security_snapshot set updated_at=? where symbol='CCC'",(time.time()-31*86400,))
    a,c=[asset(result(evidence),s) for s in ["AAA","CCC"]]
    assert a["annual_yield_percent"]==4 and a["history_partial"] and not a["highest_yield"]
    assert c["history_stale"] and not c["highest_yield"]


def test_different_listing_short_derivatives_and_currency_conflicts_are_not_mixed(evidence):
    store,hub=evidence
    store.positions += [Holding(symbol="AAA",stock_market="TASE",asset_class="EQUITY",currency="ILS",account_id="a",quantity=5),
                        Holding(symbol="SHORT",stock_market="NASDAQ",asset_class="EQUITY",quantity=-1),Holding(symbol="OPT",stock_market="NASDAQ",asset_class="OPTION",quantity=1)]
    data=result(evidence)
    tase=next(row for row in data["assets"] if row["stock_market"]=="TASE")
    assert tase["annual_yield_percent"] is None and len(data["excluded"])==2
    store.positions[1].currency="ILS"
    a=next(row for row in result(evidence)["assets"] if row["symbol"]=="AAA" and row["stock_market"]=="NASDAQ")
    assert a["currency_conflict"] and a["annual_yield_percent"] is None


def test_asof_snapshots_reuse_saved_evidence_without_cache_writes(evidence):
    store,hub=evidence
    hub.cache.set_security_snapshot("financial_modeling_prep","AAA","dividends_as_of:2000-01-01",[{"date":"1999-01-01","amount":99}])
    before=hub.cache.path.read_bytes()
    assert asset(result(evidence),"AAA")["ttm_dividend_per_share"]==4
    assert hub.cache.path.read_bytes()==before
    future=(TODAY+timedelta(days=30)).isoformat()
    hub.cache.set_security_snapshot("financial_modeling_prep","AAA",f"dividends_as_of:{future}",[{"date":TODAY.isoformat(),"amount":3}])
    assert asset(result(evidence),"AAA")["ttm_dividend_per_share"]==3


def test_undated_or_invalid_distributions_limit_annual_ranking(evidence):
    store,hub=evidence
    rows=hub.cache.get_security_snapshot("financial_modeling_prep","AAA","dividends")
    hub.cache.set_security_snapshot("financial_modeling_prep","AAA","dividends",rows+[{"amount":2},{"date":TODAY.isoformat(),"amount":"bad"}])
    a=asset(result(evidence),"AAA")
    assert a["ttm_dividend_per_share"]==4 and a["history_partial"] and not a["highest_yield"]
    assert a["undated_records"]==1 and a["invalid_records"]==1


def test_fmp_keeps_payment_and_adjusted_amount_metadata(monkeypatch,tmp_path):
    provider=FmpProvider({"api_key":"fixture"},SqliteCache(tmp_path/"cache.sqlite3",24))
    monkeypatch.setattr(provider,"_get_json",lambda *_args,**_kwargs:[{"date":"2026-01-10","dividend":2,"adjDividend":1,"paymentDate":"2026-01-20"}])
    row=provider.dividends("AAA")[0]
    assert row["date"]=="2026-01-10" and row["amount"]==2
    assert row["payment_date"]=="2026-01-20" and row["adjusted_amount"]==1


def test_api_is_authenticated_and_read_only_for_viewers(evidence,monkeypatch,tmp_path):
    store,hub=evidence;auth=AuthStore(tmp_path/"auth.sqlite3");auth.initialize()
    user=auth.create_user({"username":"dividendviewer","first_name":"Dividend","last_name":"Viewer","role":"Viewer","password":"Dividend-QA123!"})
    with auth._connect() as conn:conn.execute("update app_users set must_change_password=0 where id=?",(user["id"],))
    monkeypatch.setattr(main,"auth_store",auth);monkeypatch.setattr(main,"local_store",store);monkeypatch.setattr(main,"hub",lambda:hub)
    client=TestClient(main.app,base_url="https://localhost:6443")
    assert client.get('/api/portfolio/dividend-calendar').status_code==401
    assert client.post('/api/auth/login',json={"username":"dividendviewer","password":"Dividend-QA123!"}).status_code==200
    assert client.get('/api/portfolio/dividend-calendar').status_code==200
    assert client.get('/api/portfolio/dividend-calendar?year=0').status_code==400
    assert client.get('/api/portfolio/dividend-calendar?account_id=bad').status_code==400
