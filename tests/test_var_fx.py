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
from app.var_fx import MANAGED_PROVIDER, maintain_fx_histories

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
    history_calls = []
    def history(*args):
        history_calls.append(args)
        return snapshot()
    fake=SimpleNamespace(cached_prices=cached_prices, prices=live, fx=live, fx_history=history)
    monkeypatch.setattr(main,"local_store",store);monkeypatch.setattr(main,"auth_store",auth);monkeypatch.setattr(main,"hub",lambda:fake)
    client=TestClient(main.app,base_url="https://localhost:6443")
    assert client.get('/api/portfolio/var').status_code==401
    session=client.post('/api/auth/login',json={"username":"varqa","password":"Var-Fixture123!"}).json();headers={"X-CSRF-Token":session['csrf_token']}
    missing=client.get('/api/portfolio/var').json()
    assert missing['status']=='unavailable' and missing['var_ils'] is None
    assert any(row['code']=='missing_fx_history' for row in missing['issues'])
    assert history_calls == []
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
    assert len(history_calls) == (1 if role == 'Operator' else 0)
    assert store.change_token()==token
    assert {k:v for k,v in store.export_data()['data'].items() if k!='app_preferences'}=={k:v for k,v in before.items() if k!='app_preferences'}
    assert client.get('/api/portfolio/var?period=invalid').status_code==400


def investment_cash(store, currency="USD", amount=1000, account_type="Investment"):
    return store.save_account({"type": account_type, "account_id": "FX maintenance fixture",
        "currency": currency, "initial_cash": amount,
        "persons": [{"name": "Synthetic", "birth_date": "01/01/1990"}]})


def test_background_fx_seeds_required_currency_persists_and_avoids_repeat_download(tmp_path):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    investment_cash(store)
    investment_cash(store, "EUR", account_type="Bank")
    investment_cash(store, "GBP", amount=0)
    before = deepcopy(store.export_data()["data"])
    token = store.change_token()
    calls = []
    def official(currency, start, end):
        calls.append((currency, start, end))
        return snapshot(currency)
    market = SimpleNamespace(fx_history=official)
    maintain_fx_histories(store, market)
    assert calls == [("USD", TODAY-timedelta(days=1827), TODAY)]
    reloaded = LocalPortfolioStore(store.path)
    histories = load_fx_histories(reloaded)
    assert set(histories) == {"USD"}
    assert histories["USD"]["managed_by"] == MANAGED_PROVIDER
    assert histories["USD"]["revision"] == 1
    maintain_fx_histories(reloaded, market)
    assert len(calls) == 1
    result = main.build_var(reloaded, market, histories)
    assert result["status"] == "ok"
    assert result["var_ils"] == pytest.approx(400)
    assert result["var_without_fx_ils"] == pytest.approx(0)
    assert store.change_token() == token
    assert {k:v for k,v in store.export_data()["data"].items() if k != "app_preferences"} == {
        k:v for k,v in before.items() if k != "app_preferences"}
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    restored.import_data(store.export_data())
    assert load_fx_histories(restored) == histories


def test_managed_fx_refresh_retains_older_observations_and_manual_save_stops_automation(tmp_path):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    investment_cash(store)
    old_day = (TODAY-timedelta(days=2000)).isoformat()
    first = save_fx_history(store, {**snapshot(), "rates":[{"date":old_day,"rate":3.1}],
        "expected_revision":0}, managed_by=MANAGED_PROVIDER)
    # Emulate a prior process's saved official snapshot, without waiting a day.
    import json
    first["updated_at"] = (TODAY-timedelta(days=1)).isoformat()+"T00:00:00Z"
    with store._connect() as conn:
        conn.execute("update app_preferences set value=? where key=?", (json.dumps(first), PREFIX+"USD"))
    maintain_fx_histories(store, SimpleNamespace(fx_history=lambda *args:snapshot()))
    saved = load_fx_histories(store)["USD"]
    assert saved["revision"] == 2
    assert saved["rates"][0] == {"date":old_day,"rate":3.1}
    assert saved["rates"][-1]["date"] == TODAY.isoformat()
    refreshed = refresh_fx_history(store, SimpleNamespace(fx_history=lambda *args:snapshot()),
        {"currency":"USD", "period":"1y", "expected_revision":2})
    assert refreshed["managed_by"] == MANAGED_PROVIDER
    assert refreshed["rates"][0] == {"date":old_day,"rate":3.1}
    refreshed["updated_at"] = (TODAY-timedelta(days=1)).isoformat()+"T00:00:00Z"
    with store._connect() as conn:
        conn.execute("update app_preferences set value=? where key=?", (json.dumps(refreshed), PREFIX+"USD"))
    from app import var_fx
    var_fx._retry_after.pop((str(store.path), "USD"), None)
    maintain_fx_histories(store, SimpleNamespace(fx_history=lambda *args:snapshot()))
    assert load_fx_histories(store)["USD"]["revision"] == 4
    manual = save_fx_history(store, {**snapshot(source="Manual correction", managed_by=MANAGED_PROVIDER), "expected_revision":4})
    assert "managed_by" not in manual  # Client-supplied provenance is ignored.
    calls = []
    def recorded(*args):
        calls.append(args)
        return snapshot()
    maintain_fx_histories(store, SimpleNamespace(fx_history=recorded))
    assert not calls
    assert load_fx_histories(store)["USD"] == manual


def test_automatic_fx_failure_cooldown_recovery_and_revision_race(monkeypatch, tmp_path):
    from app import var_fx
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    investment_cash(store)
    clock = [0]
    monkeypatch.setattr(var_fx, "monotonic", lambda:clock[0])
    attempts = []
    def fail(*args):
        attempts.append(args)
        raise ConnectionError("isolated fixture failure")
    maintain_fx_histories(store, SimpleNamespace(fx_history=fail))
    assert not load_fx_histories(store)
    maintain_fx_histories(store, SimpleNamespace(fx_history=fail))
    assert len(attempts) == 1
    clock[0] = 301
    def raced(*args):
        save_fx_history(store, {**snapshot(source="Concurrent manual correction"), "expected_revision":0})
        return snapshot()
    maintain_fx_histories(store, SimpleNamespace(fx_history=raced))
    saved = load_fx_histories(store)["USD"]
    assert saved["source"] == "Concurrent manual correction"
    assert saved["revision"] == 1 and "managed_by" not in saved
    recovery = LocalPortfolioStore(tmp_path / "recovery.sqlite3")
    investment_cash(recovery)
    maintain_fx_histories(recovery, SimpleNamespace(fx_history=lambda *args:snapshot()))
    assert main.build_var(recovery, SimpleNamespace(), load_fx_histories(recovery))["status"] == "ok"


def test_auto_fx_does_not_replace_invalid_saved_evidence(tmp_path):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    investment_cash(store)
    with store._connect() as conn:
        conn.execute("insert into app_preferences(key,value,updated_at) values(?,?,?)", (PREFIX+"USD", "broken json", "fixture"))
    calls = []
    maintain_fx_histories(store, SimpleNamespace(fx_history=lambda *args:calls.append(args)))
    assert not calls
    assert load_fx_histories(store)["USD"]["invalid"]


def test_background_portfolio_worker_maintains_fx_even_if_analytics_fail(monkeypatch, tmp_path):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    investment_cash(store)
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "hub", lambda:SimpleNamespace(fx_history=lambda *args:snapshot()))
    monkeypatch.setattr(main, "portfolio_cache_signature", lambda:"fx-fixture")
    monkeypatch.setattr(main, "_portfolio_refresh_failure", None)
    monkeypatch.setattr(main, "_portfolio_refresh_progress", None)
    monkeypatch.setattr(main, "_portfolio_refresh_in_progress", False)
    def fail(**kwargs):
        raise RuntimeError("isolated analytics failure")
    monkeypatch.setattr(main, "enriched_local_holdings", fail)
    main._refresh_portfolio_cache()
    assert load_fx_histories(store)["USD"]["managed_by"] == MANAGED_PROVIDER
