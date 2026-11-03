"""Official FX identity, one-unit normalization, persistence and API permissions."""
from copy import deepcopy
from datetime import date, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app import main
from app.auth import AuthStore
from app.local_portfolio import LocalPortfolioStore
from app.providers import BankOfIsraelFxHistoryProvider, ProviderError
from app.var_fx import PREFIX, VarFxError, load_fx_histories, normalize_fx, save_fx_history, refresh_fx_history

TODAY = date.today()


def snapshot(currency="USD", **kwargs):
    return {"currency": currency, "source": "Synthetic official-rate fixture", "rates": [{"date": (TODAY-timedelta(days=i)).isoformat(), "rate": 4*.9**(-i/30)} for i in range(181)], **kwargs}


def test_boi_parser_uses_official_identity_and_normalizes_jpy_per_100_units():
    header = "SERIES_CODE,FREQ,BASE_CURRENCY,COUNTER_CURRENCY,UNIT_MEASURE,DATA_TYPE,DATA_SOURCE,TIME_PERIOD,OBS_VALUE,UNIT_MULT\n"
    good = "RER_JPY_ILS,D,JPY,ILS,ILS,OF00,BOI_MRKT,2026-10-30,1.9822,2\n"
    rows = BankOfIsraelFxHistoryProvider.parse_history(header+good, "JPY", date(2026,10,1), date(2026,11,1))
    assert rows == [{"date":"2026-10-30", "rate":pytest.approx(.019822)}]
    for before, after in [("RER_JPY_ILS,", "OTHER,"), (",D,", ",M,"), (",JPY,", ",USD,"), (",ILS,ILS,", ",USD,ILS,"), (",ILS,OF00,", ",NBRE,OF00,"), (",OF00,", ",LCLIMP,"), (",BOI_MRKT,", ",OTHER,")]:
        contaminated = good.replace(before, after, 1)
        assert BankOfIsraelFxHistoryProvider.parse_history(header+contaminated+good, "JPY", date(2026,10,1), date(2026,11,1)) == rows
    with pytest.raises(ProviderError):
        BankOfIsraelFxHistoryProvider.parse_history(header+good.replace("1.9822", "nan"), "JPY", date(2026,10,1), date(2026,11,1))


@pytest.mark.parametrize("patch,code", [
    ({"currency":"ILS"}, "var_fx_invalid_currency"), ({"currency":"USD/ILS"}, "var_fx_invalid_currency"),
    ({"source":" "}, "var_fx_source_required"), ({"rates":[]}, "var_fx_invalid_rows"),
    ({"rates":[{"date":TODAY.isoformat(),"rate":True}]}, "var_fx_invalid_rows"),
    ({"rates":[{"date":TODAY.isoformat(),"rate":float('inf')}]}, "var_fx_invalid_rows"),
    ({"rates":[{"date":(TODAY+timedelta(days=1)).isoformat(),"rate":4}]}, "var_fx_invalid_rows"),
    ({"rates":[{"date":TODAY.isoformat(),"rate":4},{"date":TODAY.isoformat(),"rate":4}]}, "var_fx_duplicate_date"),
])
def test_manual_fx_validation_is_finite_dated_and_per_foreign_currency(patch, code):
    with pytest.raises(VarFxError, match=f"^{code}$"): normalize_fx(snapshot(**patch))


def test_revisioned_fx_survives_backup_and_does_not_invalidate_portfolio_models(tmp_path):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    baseline = store.change_token()
    first = save_fx_history(store, {**snapshot(), "expected_revision":0})
    assert first["revision"] == 1
    with pytest.raises(VarFxError, match="var_fx_conflict"): save_fx_history(store, {**snapshot(), "expected_revision":0})
    second = save_fx_history(store, {**snapshot(source="Updated source"), "expected_revision":1})
    assert second["revision"] == 2 and store.change_token() == baseline
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    restored.import_data(store.export_data())
    assert load_fx_histories(restored)["USD"] == second


def test_corrupt_unrelated_fx_is_explicit_and_repairable_without_blocking_ils_scope(tmp_path):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    account = store.save_account({"type":"Investment", "account_id":"ILS only", "currency":"ILS", "initial_cash":1000, "persons":[{"name":"Synthetic","birth_date":"01/01/1990"}]})
    with store._connect() as conn:
        conn.execute("insert into app_preferences(key,value,updated_at) values(?,?,?)", (PREFIX+"USD", "broken json", "fixture"))
    histories = load_fx_histories(store)
    assert histories["USD"]["invalid"] and histories["USD"]["revision"] == 0
    result = main.build_var(store, SimpleNamespace(), histories)
    assert result["status"] == "ok" and result["var_ils"] == 0
    repaired = save_fx_history(store, {**snapshot(), "expected_revision":0})
    assert repaired["revision"] == 1 and not load_fx_histories(store)["USD"].get("invalid")


def test_provider_failure_and_delayed_refresh_preserve_newer_manual_history(tmp_path):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    first = save_fx_history(store, {**snapshot(), "expected_revision":0})
    payload = {"currency":"USD", "period":"3y", "expected_revision":1}
    def fail(*args): raise RuntimeError("private provider body")
    with pytest.raises(VarFxError, match="^var_fx_refresh_failed$"):
        refresh_fx_history(store, SimpleNamespace(fx_history=fail), payload)
    assert load_fx_histories(store)["USD"] == first
    def raced(currency, start, end):
        save_fx_history(store, {**snapshot(source="Newer manual correction"), "expected_revision":1})
        return snapshot()
    with pytest.raises(VarFxError, match="^var_fx_conflict$"):
        refresh_fx_history(store, SimpleNamespace(fx_history=raced), payload)
    assert load_fx_histories(store)["USD"]["source"] == "Newer manual correction"


@pytest.mark.parametrize("role", ["Viewer", "Operator"])
def test_authenticated_var_fx_workflow_permissions_cash_and_no_request_provider_io(monkeypatch, tmp_path, role):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    account = store.save_account({"type":"Investment", "account_id":"VaR fixture", "location":"USA", "currency":"USD", "initial_cash":1000, "persons":[{"name":"Synthetic","birth_date":"01/01/1990"}]})
    store.add_transaction({"account_db_id":account["id"], "symbol":"VARQA", "stock_market":"NASDAQ", "asset_class":"EQUITY", "action":"BUY", "quantity":10, "price_input":100, "trade_date":(TODAY-timedelta(days=200)).isoformat()})
    for i in range(181):
        store.save_price({"symbol":"VARQA", "stock_market":"NASDAQ", "asset_class":"EQUITY", "location":"USA", "currency":"USD", "price_input":100, "price_date":(TODAY-timedelta(days=i)).isoformat()})
    auth=AuthStore(store.path);auth.initialize()
    user=auth.create_user({"username":"varqa", "first_name":"Synthetic", "last_name":role, "role":role, "password":"Var-Fixture123!"})
    with auth._connect() as conn: conn.execute("update app_users set must_change_password=0 where id=?", (user["id"],))
    def cached_prices(*args, **kwargs): return [], {}
    def live(*args, **kwargs): raise AssertionError("VaR GET cannot fetch market or FX data")
    fake=SimpleNamespace(cached_prices=cached_prices, prices=live, fx=live, fx_history=lambda *args:snapshot())
    monkeypatch.setattr(main,"local_store",store);monkeypatch.setattr(main,"auth_store",auth);monkeypatch.setattr(main,"hub",lambda:fake)
    client=TestClient(main.app,base_url="https://localhost:6443")
    assert client.get('/api/portfolio/var').status_code==401
    session=client.post('/api/auth/login',json={"username":"varqa","password":"Var-Fixture123!"}).json();headers={"X-CSRF-Token":session['csrf_token']}
    missing=client.get('/api/portfolio/var').json()
    assert missing['status']=='unavailable' and missing['var_ils'] is None
    assert any(row['code']=='missing_fx_history' for row in missing['issues'])
    before=deepcopy(store.export_data()['data']);token=store.change_token()
    body={**snapshot(),"expected_revision":0}
    if role=='Viewer':
        assert client.put('/api/local/var-fx-history',json=body,headers=headers).status_code==403
        assert client.post('/api/portfolio/var/fx-refresh',json={"currency":"USD","expected_revision":0},headers=headers).status_code==403
        save_fx_history(store,body)
    else:
        assert client.put('/api/local/var-fx-history',json=body).status_code==403
        assert client.put('/api/local/var-fx-history',json=body,headers=headers).status_code==200
        assert client.put('/api/local/var-fx-history',json=body,headers=headers).status_code==409
        assert client.post('/api/portfolio/var/fx-refresh',json={"currency":"USD","expected_revision":1},headers=headers).status_code==200
    result=client.get('/api/portfolio/var').json()
    assert result['status']=='ok' and result['portfolio_value_ils']==pytest.approx(4000)
    assert result['var_ils']==pytest.approx(400)
    assert result['var_without_fx_ils']==pytest.approx(0)
    assert store.change_token()==token
    assert {k:v for k,v in store.export_data()['data'].items() if k!='app_preferences'}=={k:v for k,v in before.items() if k!='app_preferences'}
    assert client.get('/api/portfolio/var?period=invalid').status_code==400
