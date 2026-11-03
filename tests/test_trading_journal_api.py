"""Authenticated journal use and boundaries with an isolated synthetic ledger."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient
import pytest

from app import main
from app.auth import AuthStore
from app.local_portfolio import LocalPortfolioStore
from app.trading_journal import journal_payload


@pytest.fixture
def context(monkeypatch, tmp_path):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite3")
    account = store.save_account({"type": "Investment", "account_id": "Journal fixture", "currency": "USD", "location": "USA",
                                  "persons": [{"name": "Synthetic", "birth_date": "01/01/1990"}]})
    common = {"account_db_id": account["id"], "symbol": "JOURNALQA", "stock_market": "NASDAQ", "asset_class": "EQUITY", "quantity": 2, "price_input": 100}
    buy = store.add_transaction({**common, "action": "BUY", "trade_date": "2025-01-01"})
    sell = store.add_transaction({**common, "action": "SELL", "trade_date": "2025-03-01", "price_input": 120})
    auth = AuthStore(store.path)
    auth.initialize()
    monkeypatch.setattr(main, "auth_store", auth)
    monkeypatch.setattr(main, "local_store", store)
    def forbid(*args, **kwargs): raise AssertionError("Journal operations cannot fetch market data or clear financial analytics")
    monkeypatch.setattr(main, "hub", forbid)
    monkeypatch.setattr(main, "clear_portfolio_cache", forbid)
    def client(role):
        username = "journal" + role.lower()
        user = auth.create_user({"username": username, "first_name": "Synthetic", "last_name": role, "role": role, "password": "Journal-Fixture123!"})
        with auth._connect() as conn:
            conn.execute("update app_users set must_change_password=0 where id=?", (user["id"],))
        api = TestClient(main.app, base_url="https://localhost:6443")
        session = api.post("/api/auth/login", json={"username": username, "password": "Journal-Fixture123!"}).json()
        return api, {"X-CSRF-Token": session["csrf_token"]}
    return store, account, buy, sell, client


def test_operator_records_reason_revisits_reviews_and_recovers_after_conflict(context, tmp_path):
    store, account, buy, sell, login = context
    api, headers = login("Operator")
    assert store.holdings() == []  # Fully sold security must remain journal-able.
    data = api.get("/api/local/trading-journal").json()
    assert {row["id"] for row in data["transactions"]} == {buy["id"], sell["id"]}
    baseline = store.change_token()
    financial = {key: deepcopy(value) for key, value in store.export_data()["data"].items() if key != "app_preferences"}
    payload = {"transaction_id": buy["id"], "expected_revision": 0, "reason": "A durable thesis", "thesis": "Reconsider if earnings deteriorate", "review_date": "2025-06-01", "author": "FORGED"}
    first = api.put("/api/local/trading-journal", json=payload, headers=headers).json()["entry"]
    assert first["reason_history"][0]["author"] == "journaloperator"
    assert first["revision"] == 1
    assert api.put("/api/local/trading-journal", json=payload, headers=headers).status_code == 409
    updated = api.put("/api/local/trading-journal", json={**payload, "expected_revision": 1, "reason": "Updated after more evidence"}, headers=headers).json()["entry"]
    assert len(updated["reason_history"]) == 2 and updated["reason_history"][0]["reason"] == "A durable thesis"
    review_path = f'/api/local/trading-journal/{buy["id"]}/reviews'
    assert api.post(review_path, json={"expected_revision": 2, "rating": [], "notes": "Invalid"}, headers=headers).status_code == 400
    reviewed = api.post(review_path, json={"expected_revision": 2, "rating": "mixed", "notes": "Good reasoning, poor timing"}, headers=headers).json()["entry"]
    assert reviewed["review_status"] == "mixed" and reviewed["revision"] == 3
    assert reviewed["reason_history"] == updated["reason_history"]
    assert api.post(review_path, json={"expected_revision": 2, "rating": "good", "notes": "Stale draft"}, headers=headers).status_code == 409
    assert api.get("/api/local/trading-journal?review_status=mixed").json()["items"][0]["reviews"][0]["notes"] == "Good reasoning, poor timing"
    assert api.get("/api/local/trading-journal?review_status=bad").json()["items"] == []
    assert store.change_token() == baseline
    assert {key: value for key, value in store.export_data()["data"].items() if key != "app_preferences"} == financial
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    restored.import_data(store.export_data())
    assert journal_payload(restored)["items"][0]["reviews"] == reviewed["reviews"]
    # Actual financial inputs still change the financial revision.
    store.save_price({"symbol": "JOURNALQA", "stock_market": "NASDAQ", "asset_class": "EQUITY", "currency": "USD", "location": "USA", "price_input": 130, "price_date": "2025-04-01"})
    assert store.change_token() != baseline


def test_anonymous_viewer_write_permissions_and_csrf(context):
    store, account, buy, sell, login = context
    anonymous = TestClient(main.app, base_url="https://localhost:6443")
    assert anonymous.get("/api/local/trading-journal").status_code == 401
    viewer, headers = login("Viewer")
    assert viewer.get("/api/local/trading-journal").status_code == 200
    payload = {"transaction_id": buy["id"], "reason": "Why", "expected_revision": 0}
    assert viewer.put("/api/local/trading-journal", json=payload, headers=headers).status_code == 403
    assert viewer.post(f'/api/local/trading-journal/{buy["id"]}/reviews', json={}, headers=headers).status_code == 403
    operator, _headers = login("Operator")
    assert operator.put("/api/local/trading-journal", json=payload).status_code == 403
    assert journal_payload(store)["items"] == []


def test_api_validation_does_not_damage_saved_notes(context):
    _, account, buy, _, login = context
    api, headers = login("Admin")
    first = api.put("/api/local/trading-journal", json={"transaction_id": buy["id"], "expected_revision": 0, "reason": "Keep original"}, headers=headers)
    assert first.status_code == 200
    for patch in [{"reason": ""}, {"thesis": "x" * 5001}, {"review_date": "31/02/2025"}, {"expected_revision": True}]:
        assert api.put("/api/local/trading-journal", json={"transaction_id": buy["id"], "expected_revision": 1, "reason": "Attempted overwrite", **patch}, headers=headers).status_code == 400
    assert api.get("/api/local/trading-journal?account_id=missing").status_code == 400
    assert api.get("/api/local/trading-journal?action=DIVIDEND").status_code == 400
    assert api.get("/api/local/trading-journal?review_status=automatic_good").status_code == 400
    assert api.post("/api/local/trading-journal/missing/reviews", json={"expected_revision": 0, "rating": "good", "notes": "Missing entry"}, headers=headers).status_code == 404
    assert api.get("/api/local/trading-journal").json()["items"][0]["reason"] == "Keep original"


def test_browser_api_keeps_simulation_plans_valid_for_journal_notes_only():
    source = (Path(__file__).resolve().parents[1] / "web/app.js").read_text()
    function = source[source.index("async function api("):source.index("\nfunction assistantUi(")]
    script = """
const assert=require('node:assert/strict');
const state={auth:{csrfToken:'synthetic'}};
let invalidations=0;const logs=[];
const invalidateTradePlans=()=>invalidations++;
const appLog=(...args)=>logs.push(args);const appWarn=appLog;
const fetch=async()=>({ok:true,status:200,json:async()=>({saved:true})});
""" + function + """
(async()=>{
await api('/api/local/trading-journal',{method:'PUT',body:JSON.stringify({reason:'PRIVATE NOTES'})});
await api('/api/local/trading-journal/fixture/reviews',{method:'POST',body:JSON.stringify({notes:'PRIVATE REVIEW'})});
assert.equal(invalidations,0);
await api('/api/local/prices',{method:'PUT'});assert.equal(invalidations,1);
assert.ok(!JSON.stringify(logs).includes('PRIVATE'));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(["node"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
