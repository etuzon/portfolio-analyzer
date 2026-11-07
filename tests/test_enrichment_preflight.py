"""Slow ordinary APIs must not discard the AI request's eligible inventory."""
from threading import Event
import time

from app.enrichment_preflight import ApiPreflight
from test_security_enrichment import environment, start, job


def candidate(symbol="A"):
    return {"security_key": symbol + "|NASDAQ|USD", "symbol": symbol,
            "missing_fields": ["prices", "profile"]}


def test_slow_preflight_returns_missing_fields_and_reuses_ongoing_work():
    runner = ApiPreflight(max_workers=1)
    release, started = Event(), Event()
    calls = []

    def slow(item):
        calls.append(item["symbol"])
        started.set()
        release.wait(2)
        return {**item, "status": "updated", "code": "data_found"}

    try:
        beginning = time.monotonic()
        first = runner.run([candidate()], slow, timeout_seconds=.01)
        assert started.wait(.5)
        assert time.monotonic() - beginning < .5
        second = runner.run([candidate()], slow, timeout_seconds=.01)
        assert calls == ["A"]
        for result in (first, second):
            assert result[0]["code"] == "provider_timeout"
            assert result[0]["missing_fields"] == ["prices", "profile"]
            assert result[0]["available_fields"] == []
        blocked = runner.run([candidate("B")], slow, timeout_seconds=.01)
        assert blocked[0]["diagnostic"]["error_type"] == "ProviderWorkInProgress"
        assert calls == ["A"]  # Retries cannot build an unbounded queued backlog.
    finally:
        release.set()
        runner._pool.shutdown(wait=True)


def test_finished_api_evidence_is_kept_while_a_different_source_times_out():
    runner = ApiPreflight(max_workers=2)
    release = Event()

    def fetch(item):
        if item["symbol"] == "B":
            release.wait(2)
        return {**item, "status": "updated", "code": "data_found"}

    try:
        result = runner.run([candidate(), candidate("B")], fetch, timeout_seconds=.02)
        assert [item["code"] for item in result] == ["data_found", "provider_timeout"]
    finally:
        release.set()
        runner._pool.shutdown(wait=True)


def test_application_error_is_distinguished_and_does_not_expose_exception_text():
    runner = ApiPreflight(max_workers=1)

    def broken(item):
        raise RuntimeError("synthetic-private-provider-key")

    try:
        result = runner.run([candidate()], broken, timeout_seconds=.5)
        assert result[0]["code"] == "job_failed"
        assert result[0]["diagnostic"]["error_type"] == "RuntimeError"
        assert "synthetic-private-provider-key" not in str(result)
    finally:
        runner._pool.shutdown(wait=True)


def test_bounded_api_work_returns_inventory_before_rest_deadline_and_reports_missing_search(environment, monkeypatch):
    import app.security_enrichment as coordinator
    env = environment
    runner = ApiPreflight(max_workers=1)
    release = Event()
    item = env.state.items[0]

    def blocked_source(candidate):
        release.wait(2)
        return {**candidate, "status": "updated", "code": "data_found"}

    def inventory():
        return {"items": [item], "total_count": 1, "research_available": False,
                "preflight_outcomes": runner.run([item], blocked_source, timeout_seconds=.005)}

    env.manager._candidate_reader = inventory
    env.manager._outcome_writer = lambda outcomes, user_id, request_id, **kwargs: outcomes
    original_deadline = coordinator.anyio.fail_after
    monkeypatch.setattr(coordinator.anyio, "fail_after", lambda seconds, **kwargs: original_deadline(min(seconds, .15), **kwargs))
    try:
        identifier = start(env)
        env.run()
        result = job(env, identifier)
        assert result["status"] == "completed" and result["summary"]["total_candidates"] == 1, result
        assert result["outcomes"][0]["code"] == "research_unavailable"
        assert result["outcomes"][0]["diagnostic"]["error_type"] == "TimeoutError"
        assert result["counts"]["model_requests"] == 0
        assert result["counts"]["rest_requests"] == 2
        assert not env.state.model_messages
    finally:
        release.set()
        runner._pool.shutdown(wait=True)
