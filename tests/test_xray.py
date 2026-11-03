from datetime import date, timedelta
import io
from types import SimpleNamespace
from threading import RLock
import zipfile

from fastapi.testclient import TestClient
import pytest

from app import main
from app.auth import AuthStore
from app.local_portfolio import LocalPortfolioStore
from app.models import Holding
from app.providers import IssuerFundHoldingsProvider, MarketDataHub, ProviderError
from app.xray import XrayError, build_xray, normalize_snapshot, read_snapshot, save_manual_report, snapshot_key


class Store:
    def __init__(self):
        self._sync_lock = RLock()
        self.prefs = {}
        self.positions = [Holding(symbol=s, stock_market=m, asset_class=c, account_id=a, quantity=q) for s,m,c,a,q in [
            ("AAPL","NASDAQ","EQUITY","a",10), ("AAPL","TASE","EQUITY","a",5),
            ("ONE","NYSE","ETF","a",10), ("ONE","NYSE","ETF","b",4),
            ("TWO","NASDAQ","MUTUALFUND","b",20), ("OPT","NASDAQ","OPTION","a",2)]]
    def holdings(self):
        return [SimpleNamespace(holding=h) for h in self.positions]
    def list_accounts(self):
        return [{"id":"a","account_id":"First"},{"id":"b","account_id":"Second"}]
    def get_preference(self,key,default=None):
        return self.prefs.get(key,default)
    def set_preference(self,key,value):
        self.prefs[key]=value


def report(store, symbol="ONE", market="NYSE", csv_text="symbol,market,weight_percent,name\nAAPL,US,7.5,Apple\nMSFT,US,5,Microsoft", **kwargs):
    payload={"symbol":symbol,"stock_market":market,"csv_text":csv_text,"as_of":(date.today()-timedelta(days=1)).isoformat(),"source_name":"Synthetic issuer report","source_url":"https://example.com/report",**kwargs}
    return save_manual_report(store,payload)


def test_direct_fund_and_fund_fund_overlap_use_reported_weights_without_rescaling():
    store=Store()
    report(store)
    report(store,"TWO","NASDAQ",csv_text="symbol,market,weight_percent\nAAPL,US,6\nMSFT,US,8")
    result=build_xray(store)
    apple=result["overlaps"][0]
    assert apple["symbol"]=="AAPL" and len(apple["direct"])==1
    assert apple["direct"][0]["stock_market"]=="NASDAQ"
    assert [row["weight_percent"] for row in apple["funds"]]==[7.5,6]
    assert result["fund_pairs"][0]["observed_overlap_percent"]==11  # min(7.5,6)+min(5,8)
    assert result["fund_pairs"][0]["shared_count"]==2
    assert result["funds"][0]["covered_weight_percent"]==12.5
    assert len(result["funds"][0]["positions"])==2
    assert len(result["excluded"])==1
    assert len(build_xray(store,"a")["overlaps"])==1
    with pytest.raises(XrayError,match="xray_unknown_account"):
        build_xray(store,"missing")


def test_missing_and_old_reports_are_not_inferred_from_index_names():
    store=Store();store.positions[2].name="S&P 500 index Apple Microsoft"
    result=build_xray(store)
    assert result["overlaps"]==[]
    assert all(fund["status"]=="missing" for fund in result["funds"])
    report(store,as_of=(date.today()-timedelta(days=46)).isoformat())
    assert build_xray(store)["funds"][0]["status"]=="stale"
    store.prefs[snapshot_key("ONE","NYSE")]["as_of"]=None
    assert build_xray(store)["funds"][0]["status"]=="undated"


def test_one_us_fund_on_different_trading_venues_is_one_path():
    store=Store()
    store.positions.append(Holding(symbol="ONE",stock_market="NYSEARCA",asset_class="ETF",account_id="b",quantity=3))
    report(store)
    result=build_xray(store)
    assert result["fund_count"]==2
    assert len(result["funds"][0]["positions"])==3
    assert len(result["overlaps"][0]["funds"])==1
    assert read_snapshot(store,"ONE","NYSEARCA")==read_snapshot(store,"ONE","NYSE")


def test_different_market_share_class_and_names_never_match_by_guess():
    store=Store()
    report(store,csv_text="symbol,market,weight_percent,name\nAAPL,TASE,1,WrongUSApple\nGOOGL,US,2,Apple")
    result=build_xray(store)
    assert result["overlaps"][0]["market"]=="TASE"
    assert result["overlaps"][0]["direct"][0]["stock_market"]=="TASE"
    assert len(result["overlaps"])==1


@pytest.mark.parametrize("csv_text,code",[
    ("symbol,weight_percent\nAAPL,7","xray_csv_columns"),
    ("symbol,market,weight_percent\nAAPL,US,nan","xray_invalid_weight"),
    ("symbol,market,weight_percent\nAAPL,US,0","xray_invalid_weight"),
    ("symbol,market,weight_percent\nAAPL,US,-2","xray_invalid_weight"),
    ("symbol,market,weight_percent\nAAPL,US,70\nMSFT,US,40","xray_weight_total"),
    ("symbol,market,weight_percent\nAAPL,US,1\nAAPL,NASDAQ,2","xray_duplicate_constituent"),
    ("symbol,market,weight_percent\nAAPL,,7","xray_invalid_identity"),
    ("symbol,market,weight_percent\nONE,US,10","xray_self_holding"),
    ("symbol,market,weight_percent\nAAPL,US,2,unmapped-column","xray_invalid_rows"),
])
def test_invalid_reports_never_replace_saved_evidence(csv_text,code):
    store=Store();before=report(store)
    with pytest.raises(XrayError,match=code): report(store,csv_text=csv_text)
    assert read_snapshot(store,"ONE","NYSE")==before


@pytest.mark.parametrize("url",["javascript:alert(1)","https://user:password@example.com/a","http://[invalid"])
def test_source_urls_cannot_include_credentials_or_unsafe_schemes(url):
    with pytest.raises(XrayError,match="xray_invalid_source_url"): report(Store(),source_url=url)


def test_manual_source_is_labeled_local_and_dates_are_validated():
    store=Store();snapshot=report(store,source_kind="issuer",as_of=date.today().strftime("%d/%m/%Y"))
    assert snapshot["source_kind"]=="local" and snapshot["as_of"]==date.today().isoformat()
    for day in [None,"31/02/2026",(date.today()+timedelta(days=1)).isoformat()]:
        with pytest.raises(XrayError,match="xray_invalid_date"):report(store,as_of=day)


def test_nested_fund_overlap_is_visible_but_never_expanded_or_double_counted():
    store=Store()
    report(store,csv_text="symbol,market,weight_percent,asset_class\nTWO,US,20,MUTUALFUND")
    report(store,"TWO","NASDAQ")
    result=build_xray(store)
    assert result["funds"][0]["nested_constituents"]==1
    assert [row["symbol"] for row in result["overlaps"]]==["AAPL","TWO"]
    assert len(result["overlaps"][0]["funds"])==1


def _real_store(tmp_path):
    store=LocalPortfolioStore(tmp_path/"portfolio.sqlite3")
    account=store.save_account({"account_id":"Fixture","type":"Investment","persons":[{"name":"Synthetic","birth_date":"01/01/1990"}]})
    for symbol,kind in [("ONE","ETF"),("AAPL","EQUITY")]:
        store.add_transaction({"account_db_id":account["id"],"symbol":symbol,"stock_market":"NYSE","asset_class":kind,"action":"BUY","quantity":1,"price_input":10,"allow_manual":True,"trade_date":date.today().isoformat()})
    return store


def test_report_survives_restart_and_export_import_without_changing_holdings(tmp_path):
    store=_real_store(tmp_path)
    before=store.list_transactions()
    report(store)
    restarted=LocalPortfolioStore(store.path)
    assert build_xray(restarted)["overlaps"][0]["symbol"]=="AAPL"
    assert store.list_transactions()==before
    exported=store.export_data()
    restored=LocalPortfolioStore(tmp_path/"restored.sqlite3")
    restored.import_data(exported)
    assert read_snapshot(restored,"ONE","NYSE")==read_snapshot(store,"ONE","NYSE")


def test_issuer_csv_requires_fund_identity_report_date_and_explicit_percent_units():
    raw='''iShares Core S&P 500 ETF
Fund Holdings as of,"Oct 30, 2026"
Ticker,Name,Asset Class,Exchange,Market Weight
AAPL,Apple,Equity,NASDAQ,7.70
MSFT,Microsoft,Equity,NASDAQ,5.93
USD,Cash,Cash,-,2
OTHER,Other,Equity,TASE,3
'''
    rows,day=IssuerFundHoldingsProvider.parse_ivv(raw)
    assert day=="2026-10-30" and len(rows)==2 and rows[0]["weight_percent"]==7.70
    with pytest.raises(ValueError):IssuerFundHoldingsProvider.parse_ivv(raw.replace("iShares Core S&P 500 ETF","Other ETF"))


def _spy_workbook():
    shared=['Ticker Symbol:','SPY','Holdings:','As of 30-Oct-2026','Name','Ticker','Weight','Apple','AAPL','037833100','USD']
    cells=[[("A",0),("B",1)],[("A",2),("B",3)],[("A",4),("B",5),("E",6)],[("A",7),("B",8),("C",9),("H",10)]]
    rows=[]
    for index,values in enumerate(cells,1):
        content=''.join(f'<c r="{col}{index}" t="s"><v>{value}</v></c>' for col,value in values)
        if index==4:content+='<c r="E4"><v>7.69866</v></c>'
        rows.append(f'<row r="{index}">{content}</row>')
    data=io.BytesIO();ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with zipfile.ZipFile(data,'w') as archive:
        archive.writestr('xl/sharedStrings.xml',f'<sst xmlns="{ns}">'+''.join(f'<si><t>{v}</t></si>' for v in shared)+'</sst>')
        archive.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{ns}"><sheetData>'+''.join(rows)+'</sheetData></worksheet>')
    return data.getvalue()


def test_issuer_spreadsheet_uses_column_references_not_cell_positions():
    rows,day=IssuerFundHoldingsProvider.parse_spy(_spy_workbook())
    assert day=="2026-10-30" and rows[0]["symbol"]=="AAPL"
    assert rows[0]["weight_percent"]==7.69866
    hub=object.__new__(MarketDataHub)
    with pytest.raises(ProviderError,match="unsupported"):hub.fund_holdings("SPY","TASE")


def test_authenticated_viewer_can_read_but_cannot_change_reports(monkeypatch,tmp_path):
    store=_real_store(tmp_path);report(store)
    auth=AuthStore(store.path);auth.initialize()
    user=auth.create_user({"username":"xrayviewer","first_name":"Xray","last_name":"Fixture","role":"Viewer","password":"Xray-Viewer123!"})
    with auth._connect() as conn:conn.execute("update app_users set must_change_password=0 where id=?",(user["id"],))
    monkeypatch.setattr(main,"auth_store",auth);monkeypatch.setattr(main,"local_store",store)
    monkeypatch.setattr(main,"hub",lambda: (_ for _ in ()).throw(AssertionError("GET must not access providers")))
    client=TestClient(main.app,base_url="https://localhost:6443")
    assert client.get('/api/portfolio/xray').status_code==401
    login=client.post('/api/auth/login',json={"username":"xrayviewer","password":"Xray-Viewer123!"}).json()
    assert client.get('/api/portfolio/xray').json()["overlaps"][0]["symbol"]=="AAPL"
    assert client.get('/api/local/fund-holdings?symbol=ONE&stock_market=NYSE').status_code==200
    headers={"X-CSRF-Token":login["csrf_token"]}
    assert client.put('/api/local/fund-holdings',json={},headers=headers).status_code==403
    assert client.post('/api/portfolio/xray/refresh',json={"symbol":"ONE","stock_market":"NYSE"},headers=headers).status_code==403


def test_failed_issuer_refresh_retains_saved_report(monkeypatch):
    store=Store();before=report(store)
    def fail(*_args):raise ProviderError("xray_issuer_failed")
    monkeypatch.setattr(main,"local_store",store);monkeypatch.setattr(main,"hub",lambda:SimpleNamespace(fund_holdings=fail))
    with pytest.raises(main.HTTPException) as error:main.refresh_xray_fund({"symbol":"ONE","stock_market":"NYSE"})
    assert error.value.status_code==502
    assert read_snapshot(store,"ONE","NYSE")==before


def test_late_issuer_response_cannot_overwrite_new_manual_report(monkeypatch):
    store=Store();report(store)
    def raced(*_args):
        report(store,csv_text="symbol,market,weight_percent\nAAPL,US,10")
        return {"holdings":[]}
    monkeypatch.setattr(main,"local_store",store);monkeypatch.setattr(main,"hub",lambda:SimpleNamespace(fund_holdings=raced))
    with pytest.raises(main.HTTPException) as error:main.refresh_xray_fund({"symbol":"ONE","stock_market":"NYSE"})
    assert error.value.status_code==409
    assert read_snapshot(store,"ONE","NYSE")["holdings"][0]["weight_percent"]==10
