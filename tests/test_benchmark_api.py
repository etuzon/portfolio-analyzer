"""Application-boundary checks with synthetic statements, no live providers."""
from datetime import date
from threading import RLock
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app import main
from app.auth import AuthStore
from app.benchmark import BenchmarkError, load_index, save_index
from app.benchmark_data import benchmark_inputs, benchmark_comparison, refresh_index, save_portfolio_inputs, save_index_inputs
from app.local_portfolio import LocalPortfolioStore


class Store:
    def __init__(self):
        self.prefs = {}
        self._sync_lock = RLock()
        self.accounts = [{"id": "a", "currency": "USD"}, {"id": "b", "currency": "USD"}]
        self.snapshots = [
            {"account_db_id": "a", "snapshot_date": "2024-01-01", "value": 100},
            {"account_db_id": "b", "snapshot_date": "2024-01-01", "value": 200},
            {"account_db_id": "a", "snapshot_date": "2024-12-31", "value": 110},
        ]
    def list_accounts(self): return self.accounts
    def list_account_snapshots(self, _filters): return self.snapshots
    def get_preference(self, key, default=None): return self.prefs.get(key, default)
    def set_preference(self, key, value): self.prefs[key] = value


def portfolio(**kwargs):
    return {"currency": "USD", "source": "Synthetic annual statement", "flows_complete": True,
            "valuations": [{"date": "2024-01-01", "value": 100}, {"date": "2024-12-31", "value": 110}],
            "cash_flows": [], **kwargs}


def index(**kwargs):
    return {"name": "S&P 500", "currency": "USD", "basis": "price", "source": "Synthetic index",
            "levels": [{"date": "2024-01-01", "level": 100}, {"date": "2024-12-31", "level": 120}], **kwargs}


def test_snapshot_suggestions_require_all_accounts_on_identical_dates_and_currency():
    store = Store()
    data = benchmark_inputs(store)
    assert data["dataset"] is None
    assert data["suggested_valuations"] == [{"date": "2024-01-01", "value": 300}]
    assert len(benchmark_inputs(store, "a")["suggested_valuations"]) == 2
    store.accounts[1]["currency"] = "ILS"
    assert benchmark_inputs(store)["suggested_valuations"] == []
    assert benchmark_inputs(store)["suggested_currency"] == ""
    assert benchmark_inputs(store, "a")["suggested_currency"] == "USD"


def test_default_period_uses_saved_boundaries_and_preserves_independent_scopes():
    store = Store()
    save_portfolio_inputs(store, {"account_id": "a", **portfolio()})
    save_index_inputs(store, {"benchmark_id": "sp500", **index()})
    result = benchmark_comparison(store, "a")
    assert result["date_from"] == "2024-01-01" and result["date_to"] == "2024-12-31"
    assert result["result"]["portfolio"]["xirr"]["value"] == pytest.approx(10)
    assert result["result"]["benchmark"]["twrr"]["value"] == pytest.approx(20)
    assert benchmark_comparison(store)["result"]["portfolio"]["status"] == "missing_portfolio"
    assert result["index_dataset"]["id"] == "sp500"


def test_single_observation_remains_editable_with_missing_boundary_explanation():
    store = Store()
    save_portfolio_inputs(store, portfolio(valuations=[{"date": "2024-12-31", "value": 110}]))
    data = benchmark_comparison(store)
    assert data["dataset"]["valuations"] == [{"date": "2024-12-31", "value": 110}]
    assert data["result"]["portfolio"]["status"] == "missing_boundary_valuation"
    with pytest.raises(BenchmarkError):
        benchmark_comparison(store, date_from="2024-12-31", date_to="2024-12-31")


@pytest.mark.parametrize("method,args", [
    (benchmark_inputs, ("missing",)), (benchmark_inputs, ("", "missing")),
    (save_portfolio_inputs, ({"account_id": "missing", **portfolio()},)),
    (save_index_inputs, ({"benchmark_id": "missing", **index()},)),
])
def test_unknown_scopes_never_create_or_read_detached_inputs(method, args):
    store = Store()
    with pytest.raises(BenchmarkError): method(store, *args)
    assert store.prefs == {}


def test_refresh_uses_only_supported_configured_index_adapters_and_sanitizes_errors():
    store = Store()
    save_index_inputs(store, {"benchmark_id": "sp500", **index()})
    before = load_index(store, "sp500")
    def fail(*args): raise RuntimeError("SENSITIVE provider response")
    payload = {"benchmark_id": "sp500", "date_from": "2024-01-01", "date_to": "2024-12-31"}
    hub = SimpleNamespace(providers=[SimpleNamespace(name="financial_modeling_prep", prices=fail)])
    with pytest.raises(BenchmarkError, match="^benchmark_refresh_failed$"): refresh_index(store, hub, payload)
    assert load_index(store, "sp500") == before
    with pytest.raises(BenchmarkError, match="benchmark_provider_not_configured"):
        refresh_index(store, SimpleNamespace(providers=[]), payload)
    with pytest.raises(BenchmarkError, match="benchmark_refresh_unsupported"):
        refresh_index(store, hub, {**payload, "benchmark_id": "ta125"})
    def rows(symbol, start, end):
        assert symbol == "^GSPC" and start.isoformat() == "2023-12-25"
        return [SimpleNamespace(date=date(2024, 1, 1), close=100), SimpleNamespace(date=date(2024, 12, 31), close=120)]
    hub.providers[0].prices = rows
    saved = refresh_index(store, hub, payload)
    assert saved["basis"] == "price" and saved["currency"] == "USD"
    assert "financial_modeling_prep" in saved["source"]


def test_late_provider_refresh_cannot_overwrite_a_new_manual_index_report():
    store = Store()
    def raced(*args):
        save_index(store, "sp500", index(source="New manual evidence"))
        return [SimpleNamespace(date=date(2024, 1, 1), close=100), SimpleNamespace(date=date(2024, 12, 31), close=120)]
    hub = SimpleNamespace(providers=[SimpleNamespace(name="financial_modeling_prep", prices=raced)])
    with pytest.raises(BenchmarkError, match="benchmark_inputs_changed"):
        refresh_index(store, hub, {"benchmark_id": "sp500", "date_from": "2024-01-01", "date_to": "2024-12-31"})
    assert load_index(store, "sp500")["source"] == "New manual evidence"


@pytest.mark.parametrize("role", ["Viewer", "Operator"])
def test_api_auth_readonly_get_persistence_and_validation(monkeypatch, tmp_path, role):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    auth = AuthStore(store.path)
    auth.initialize()
    password = "Benchmark-Fixture123!"
    user = auth.create_user({"username": "benchmarkqa", "first_name": "Fixture", "last_name": "User", "role": role, "password": password})
    with auth._connect() as conn:
        conn.execute("update app_users set must_change_password=0 where id=?", (user["id"],))
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    monkeypatch.setattr(main, "hub", lambda: (_ for _ in ()).throw(AssertionError("GET must use saved data only")))
    client = TestClient(main.app, base_url="https://localhost:6443")
    assert client.get("/api/portfolio/benchmark").status_code == 401
    session = client.post("/api/auth/login", json={"username": "benchmarkqa", "password": password}).json()
    headers = {"X-CSRF-Token": session["csrf_token"]}
    assert client.get("/api/portfolio/benchmark").status_code == 200
    assert client.get("/api/portfolio/benchmark-inputs").json()["dataset"] is None
    assert client.get("/api/portfolio/benchmark?account_id=invalid").status_code == 400
    assert client.get("/api/portfolio/benchmark?date_from=bad").status_code == 400
    expected = 403 if role == "Viewer" else 200
    assert client.put("/api/local/benchmark-portfolio", json=portfolio(), headers=headers).status_code == expected
    assert client.put("/api/local/benchmark-index", json={"benchmark_id": "sp500", **index()}, headers=headers).status_code == expected
    if role == "Viewer":
        assert client.post("/api/portfolio/benchmark/refresh", json={}, headers=headers).status_code == 403
    else:
        saved = client.get("/api/portfolio/benchmark").json()
        assert saved["result"]["portfolio"]["xirr"]["value"] == pytest.approx(10)
        assert client.put("/api/local/benchmark-portfolio", json=portfolio(source=""), headers=headers).status_code == 400
        assert client.get("/api/portfolio/benchmark-inputs").json()["dataset"]["source"] == "Synthetic annual statement"
        exported = store.export_data()
        restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
        restored.import_data(exported)
        assert benchmark_comparison(restored)["result"]["portfolio"]["xirr"]["value"] == pytest.approx(10)
