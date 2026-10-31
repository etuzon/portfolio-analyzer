"""Retained SEC reports must refresh online without losing offline evidence."""
from datetime import date

import httpx
import pytest

from app import providers
from app.providers import MarketDataHub, SqliteCache


def sec_facts(include_new=False):
    reports = [{"fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-03-01", "start": "2024-01-01", "end": "2024-12-31", "val": 100}]
    if include_new:
        reports.append({"fy": 2025, "fp": "FY", "form": "10-K", "filed": "2026-03-01", "start": "2025-01-01", "end": "2025-12-31", "val": 120})
    return {"facts": {"us-gaap": {"Revenues": {"units": {"USD": reports}}}}}


def fixture_hub(tmp_path, monkeypatch):
    state = {"now": 2_000_000_000, "new": False, "offline": False, "invalid": False}
    calls = []
    monkeypatch.setattr(providers, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(providers.time, "time", lambda: state["now"])

    def respond(request):
        calls.append(request.url.path)
        if state["offline"]:
            raise httpx.ConnectError("Unavailable", request=request)
        if request.url.path.endswith("company_tickers.json"):
            if state["invalid"] == "tickers":
                return httpx.Response(200, json={"error": "temporary rate limit"})
            return httpx.Response(200, json={"0": {"ticker": "ACME", "cik_str": 1, "title": "Example"}})
        if "/companyfacts/" in request.url.path:
            invalid = state["invalid"]
            if invalid == "taxonomy":
                return httpx.Response(200, json={"facts": {"us-gaap": []}})
            if invalid == "units":
                return httpx.Response(200, json={"facts": {"us-gaap": {"Revenues": {"units": {"USD": {}}}}}})
            return httpx.Response(200, json={} if invalid is True else sec_facts(state["new"]))
        if "/submissions/" in request.url.path:
            return httpx.Response(200, json={"sicDescription": "Example industry", "exchanges": ["Nasdaq"]})
        raise AssertionError(str(request.url))

    client = httpx.Client
    monkeypatch.setattr(providers.httpx, "Client", lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs))
    hub = MarketDataHub({"primary": "sec_company_facts", "fallback": [], "cache_ttl_hours": 1})
    return hub, state, calls


@pytest.mark.parametrize("as_of", [None, date(2027, 1, 1)])
def test_missing_reports_download_persist_and_reuse_after_restart_then_refresh(tmp_path, monkeypatch, as_of):
    hub, state, calls = fixture_hub(tmp_path, monkeypatch)

    def read(current):
        return current.fundamentals_as_of("ACME", as_of) if as_of else current.fundamentals("ACME")

    initial, status = read(hub)
    assert status == {"sec_company_facts": "ok"}
    assert initial["income_statement"]["annualReports"][-1]["fiscalDateEnding"] == "2024-12-31"
    assert any("companyfacts" in path for path in calls)
    calls.clear()
    reopened = MarketDataHub(hub.config)
    state["offline"] = True
    assert read(reopened)[0] == initial
    assert calls == [], "fresh evidence must be reused locally, including after restart"
    state.update(now=state["now"] + 3601, new=True, offline=False)
    updated, status = read(reopened)
    assert updated["income_statement"]["annualReports"][-1]["fiscalDateEnding"] == "2025-12-31"
    assert status == {"sec_company_facts": "ok"}
    assert any("companyfacts" in path for path in calls)
    calls.clear()
    assert read(MarketDataHub(hub.config))[0] == updated
    assert calls == []
    kind = f"fundamentals_as_of:{as_of.isoformat()}" if as_of else "fundamentals"
    assert hub.cache.get_security_snapshot("sec_company_facts", "ACME", kind) == updated


@pytest.mark.parametrize("invalid_response", [False, True, "taxonomy", "units", "tickers"])
def test_failed_refresh_preserves_raw_and_normalized_evidence_then_recovers(tmp_path, monkeypatch, invalid_response):
    hub, state, calls = fixture_hub(tmp_path, monkeypatch)
    initial, _ = hub.fundamentals("ACME")
    key = "sec:companyfacts:0000000001"
    with hub.cache._connect() as connection:
        old = connection.execute("select created_at,value from cache where key=?", (key,)).fetchone()
    state.update(now=state["now"] + 3601, offline=not invalid_response, invalid=invalid_response)
    fallback, status = hub.fundamentals("ACME")
    assert fallback == initial
    assert status["sec_company_facts"].startswith("stale")
    with hub.cache._connect() as connection:
        assert connection.execute("select created_at,value from cache where key=?", (key,)).fetchone() == old
    assert hub.cache.get_security_snapshot("sec_company_facts", "ACME", "fundamentals") == initial
    assert hub.cache.get(key, require_fresh=True) is None
    assert hub.cache.get(key) == sec_facts()
    state.update(offline=False, invalid=False, new=True)
    updated, status = hub.fundamentals("ACME")
    assert status == {"sec_company_facts": "ok"}
    assert updated["income_statement"]["annualReports"][-1]["fiscalDateEnding"] == "2025-12-31"


def test_raw_evidence_supports_new_cutoff_offline_without_lookahead_or_timestamp_reset(tmp_path, monkeypatch):
    hub, state, calls = fixture_hub(tmp_path, monkeypatch)
    state["new"] = True
    hub.fundamentals("ACME")
    state.update(now=state["now"] + 3601, offline=True)
    historical, status = hub.fundamentals_as_of("ACME", date(2025, 10, 1))
    assert status["sec_company_facts"].startswith("stale")
    assert [row["fiscalDateEnding"] for row in historical["income_statement"]["annualReports"]] == ["2024-12-31"]
    assert hub.cache.get("sec:companyfacts:0000000001", require_fresh=True) is None
    assert hub.cache.get("sec:companyfacts:0000000001") == sec_facts(True)


def test_retention_does_not_make_old_evidence_fresh(tmp_path, monkeypatch):
    clock = {"now": 2_000_000_000}
    monkeypatch.setattr(providers.time, "time", lambda: clock["now"])
    cache = SqliteCache(tmp_path / "cache.sqlite3", ttl_hours=1)
    key = "sec:companyfacts:0000000001"
    cache.set(key, sec_facts())
    clock["now"] += 3601
    reopened = SqliteCache(cache.path, ttl_hours=1)
    assert reopened.get(key, require_fresh=True) is None
    assert reopened.get(key) == sec_facts()
