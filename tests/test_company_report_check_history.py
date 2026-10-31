"""Report availability checks remain distinguishable from forecast scoring."""
import sqlite3

import pytest

from app import local_portfolio, main
from app.local_portfolio import LocalPortfolioStore
from app.providers import MarketDataHub, SqliteCache
from fastapi import HTTPException


def save_prediction(store, **overrides):
    return store.save_company_report_prediction({
        "symbol": "ACME", "score": 55, "direction": "neutral", "confidence": "Low",
        "baseline": {"target": {"fiscal_date": "2025-12-31", "net_margin_percent": 10}},
        "horizon_date": "2027-12-31", **overrides,
    })


@pytest.mark.parametrize("direction,accuracy", [("pending", None), ("inconclusive", None), ("positive", 100), ("neutral", 50), ("negative", 0)])
def test_completed_checks_keep_their_time_without_changing_scoring(tmp_path, monkeypatch, direction, accuracy):
    path = tmp_path / "source.sqlite3"
    store = LocalPortfolioStore(path)
    prediction = save_prediction(store)
    baseline = prediction["baseline"]
    assert prediction["checked_at"] == ""
    monkeypatch.setattr(local_portfolio, "_now", lambda: "2026-10-31T14:25:00Z")
    result = store.evaluate_company_report_prediction(prediction["id"], {}, direction, accuracy, "Result")
    assert result["checked_at"] == "2026-10-31T14:25:00Z"
    assert result["evaluated_at"] == ("" if accuracy is None else result["checked_at"])
    assert result["baseline"] == baseline
    assert result["actual_direction"] == direction
    assert result["accuracy_score"] == accuracy
    assert store.company_report_scorecard()["evaluated"] == (accuracy is not None)
    assert LocalPortfolioStore(path).list_company_report_predictions()[0]["checked_at"] == result["checked_at"]
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    restored.import_data(store.export_data())
    assert restored.list_company_report_predictions()[0] == result


def test_no_report_retry_and_provider_failure_preserve_last_completed_check(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "source.sqlite3")
    prediction = save_prediction(store)
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "_finance_report_payload", lambda *args: {
        "reports": [{"fiscal_date": "2025-12-31"}], "provider_status": {"fixture": "ok"},
    })
    monkeypatch.setattr(local_portfolio, "_now", lambda: "2026-10-31T14:25:00Z")
    checked = main.evaluate_company_outlook_prediction(prediction["id"])["checked_predictions"][0]
    assert checked["evaluation"] == "No newer annual report is available yet."
    assert checked["checked_at"] == "2026-10-31T14:25:00Z"
    assert checked["actual_direction"] == "pending"
    assert checked["accuracy_score"] is None
    assert store.company_report_scorecard()["evaluated"] == 0
    monkeypatch.setattr(local_portfolio, "_now", lambda: "2026-11-01T16:30:00Z")
    checked = main.evaluate_company_outlook_prediction(prediction["id"])["checked_predictions"][0]
    assert checked["checked_at"] == "2026-11-01T16:30:00Z"

    def provider_failure(*args):
        raise RuntimeError("Unavailable")

    monkeypatch.setattr(main, "_finance_report_payload", provider_failure)
    with pytest.raises(RuntimeError):
        main.evaluate_company_outlook_prediction(prediction["id"])
    assert store.list_company_report_predictions()[0] == checked
    assert main.company_outlook_predictions()["items"][0] == checked


@pytest.mark.parametrize("saved_fallback", [False, True])
def test_real_provider_errors_never_become_successful_no_report_checks(tmp_path, monkeypatch, saved_fallback):
    class OfflineProvider:
        name = "offline"

        def fundamentals_as_of(self, *args):
            raise RuntimeError("Unavailable")

    cache = SqliteCache(tmp_path / "market.sqlite3", ttl_hours=24)
    hub = MarketDataHub.__new__(MarketDataHub)
    hub.config = {}
    hub.providers = [OfflineProvider()]
    hub.cache = cache
    if saved_fallback:
        cache.set_security_snapshot("offline", "ACME", "fundamentals_as_of:2027-12-31", {
            "income_statement": {"annualReports": [{"fiscalDateEnding": "2025-12-31", "totalRevenue": 100}]},
        })
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    prediction = save_prediction(store)
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "hub", lambda: hub)
    with pytest.raises(HTTPException) as error:
        main.evaluate_company_outlook_prediction(prediction["id"])
    assert error.value.status_code == 503
    assert store.list_company_report_predictions()[0] == prediction


@pytest.mark.parametrize("reports,status,code", [
    ([], {"provider": "ok"}, 503),
    ([], {"providers": "none configured"}, 503),
    ([{"fiscal_date": "2025-12-31"}], {"provider": "missing"}, 503),
    ([{"fiscal_date": "2025-12-31"}], {"provider": "error: RuntimeError", "fallback": "ok"}, None),
])
def test_empty_or_unavailable_reports_do_not_claim_no_newer_report(tmp_path, monkeypatch, reports, status, code):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    prediction = save_prediction(store)
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "_finance_report_payload", lambda *args: {"reports": reports, "provider_status": status})
    if code:
        with pytest.raises(HTTPException) as error:
            main.evaluate_company_outlook_prediction(prediction["id"])
        assert error.value.status_code == code
        assert store.list_company_report_predictions()[0] == prediction
    else:
        result = main.evaluate_company_outlook_prediction(prediction["id"])
        assert result["checked_at"]


def test_unavailable_baseline_does_not_claim_a_report_availability_check(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    prediction = save_prediction(store, baseline={})
    monkeypatch.setattr(main, "local_store", store)
    with pytest.raises(HTTPException) as error:
        main.evaluate_company_outlook_prediction(prediction["id"])
    assert error.value.status_code == 422
    assert store.list_company_report_predictions()[0] == prediction


def test_legacy_schema_and_backups_do_not_invent_check_timestamps(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    store = LocalPortfolioStore(path)
    save_prediction(store, evaluation="No newer annual report is available yet.")
    with sqlite3.connect(path) as conn:
        conn.execute("alter table company_report_predictions drop column checked_at")
    migrated = LocalPortfolioStore(path)
    result = migrated.list_company_report_predictions()[0]
    assert result["evaluation"] == "No newer annual report is available yet."
    assert result["checked_at"] == ""
    backup = migrated.export_data()
    backup["data"]["company_report_predictions"][0].pop("checked_at")
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    restored.import_data(backup)
    assert restored.list_company_report_predictions()[0] == result


def test_company_check_updates_pending_siblings_and_preserves_other_symbols_and_evaluated_rows(tmp_path, monkeypatch):
    path = tmp_path / 'company.sqlite3'
    store = LocalPortfolioStore(path)
    first = save_prediction(store)
    second = save_prediction(store)
    other = save_prediction(store, symbol='OTHER')
    completed = save_prediction(store, actual_direction='positive', accuracy_score=100, evaluation='Earlier result', checked_at='2026-01-01T12:00:00Z')
    calls = []
    def reports(symbol, limit, cutoff):
        calls.append((symbol, cutoff))
        return {'reports':[{'fiscal_date':'2025-12-31'}], 'provider_status':{'fixture':'ok'}}
    monkeypatch.setattr(main, 'local_store', store)
    monkeypatch.setattr(main, '_finance_report_payload', reports)
    monkeypatch.setattr(local_portfolio, '_now', lambda:'2026-10-31T14:25:00Z')
    result = main.evaluate_company_outlook_prediction(first['id'])
    assert {item['id'] for item in result['checked_predictions']} == {first['id'], second['id']}
    assert result['failed_prediction_ids'] == []
    assert calls == [('ACME','2027-12-31')]
    restored = {item['id']:item for item in LocalPortfolioStore(path).list_company_report_predictions()}
    for original in [first, second]:
        assert restored[original['id']]['checked_at'] == '2026-10-31T14:25:00Z'
        assert restored[original['id']]['baseline'] == original['baseline']
    assert restored[other['id']] == other
    assert restored[completed['id']] == completed


def test_company_check_uses_each_forecasts_baseline_cutoff_and_direction(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / 'company.sqlite3')
    base = {'target':{'fiscal_date':'2024-12-31','net_margin_percent':10}}
    positive = save_prediction(store, baseline=base, direction='positive')
    negative = save_prediction(store, baseline=base, direction='negative')
    newer_baseline = save_prediction(store)
    earlier_cutoff = save_prediction(store, baseline=base, horizon_date='2025-06-30')
    calls = []
    def reports(symbol, limit, cutoff):
        calls.append((symbol, cutoff))
        return {'reports':[
            {'fiscal_date':'2025-12-31','filing_date':'2026-03-01','revenue_growth_percent':10,'net_margin_percent':12},
            {'fiscal_date':'2024-12-31','filing_date':'2025-03-01','revenue_growth_percent':5,'net_margin_percent':10},
        ],'provider_status':{'fixture':'ok'}}
    monkeypatch.setattr(main, 'local_store', store)
    monkeypatch.setattr(main, '_finance_report_payload', reports)
    result = main.evaluate_company_outlook_prediction(positive['id'])
    rows = {item['id']:item for item in result['checked_predictions']}
    assert rows[positive['id']]['accuracy_score'] == 100
    assert rows[negative['id']]['accuracy_score'] == 0
    assert rows[newer_baseline['id']]['actual_direction'] == 'pending'
    assert rows[earlier_cutoff['id']]['actual_direction'] == 'pending'
    assert len(calls) == 2
    assert all(item['checked_at'] for item in rows.values())


def test_company_check_processes_valid_siblings_even_when_clicked_forecast_fails(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / 'company.sqlite3')
    invalid = save_prediction(store, baseline={})
    valid = save_prediction(store)
    monkeypatch.setattr(main, 'local_store', store)
    monkeypatch.setattr(main, '_finance_report_payload', lambda *args:{'reports':[{'fiscal_date':'2025-12-31'}], 'provider_status':{'fixture':'ok'}})
    result = main.evaluate_company_outlook_prediction(invalid['id'])
    assert result['failed_prediction_ids'] == [invalid['id']]
    assert [item['id'] for item in result['checked_predictions']] == [valid['id']]
    rows = {item['id']:item for item in store.list_company_report_predictions()}
    assert rows[invalid['id']] == invalid
    assert rows[valid['id']]['checked_at']


def test_company_check_shares_secondary_provider_failures_without_rewriting_old_checks(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / 'company.sqlite3')
    selected = save_prediction(store)
    failed = [save_prediction(store, horizon_date='2025-06-30',checked_at='2026-01-01T00:00:00Z',evaluation='Earlier check') for _ in range(2)]
    calls = []
    def reports(symbol,limit,cutoff):
        calls.append(cutoff)
        if cutoff == '2025-06-30':
            raise HTTPException(status_code=503,detail='Unavailable')
        return {'reports':[{'fiscal_date':'2025-12-31'}], 'provider_status':{'fixture':'ok'}}
    monkeypatch.setattr(main, 'local_store', store)
    monkeypatch.setattr(main, '_finance_report_payload', reports)
    result = main.evaluate_company_outlook_prediction(selected['id'])
    assert set(result['failed_prediction_ids']) == {item['id'] for item in failed}
    assert len(calls) == 2
    rows = {item['id']:item for item in store.list_company_report_predictions()}
    for original in failed:
        assert rows[original['id']] == original
