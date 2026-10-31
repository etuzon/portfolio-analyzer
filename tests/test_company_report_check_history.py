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
    checked = main.evaluate_company_outlook_prediction(prediction["id"])
    assert checked["evaluation"] == "No newer annual report is available yet."
    assert checked["checked_at"] == "2026-10-31T14:25:00Z"
    assert checked["actual_direction"] == "pending"
    assert checked["accuracy_score"] is None
    assert store.company_report_scorecard()["evaluated"] == 0
    monkeypatch.setattr(local_portfolio, "_now", lambda: "2026-11-01T16:30:00Z")
    checked = main.evaluate_company_outlook_prediction(prediction["id"])
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
