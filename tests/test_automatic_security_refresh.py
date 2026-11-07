from threading import Event, Lock
import time

from app.automatic_security_refresh import AutomaticSecurityRefresh


def candidate(index=0, **overrides):
    return {"security_key": f"security-{index}", "quantity": 1, **overrides}


def test_sliding_window_processes_all_candidates_beyond_the_ai_three_cap():
    runner = AutomaticSecurityRefresh()
    state = {"active": 0, "max_active": 0}
    lock = Lock()
    fetched, applied = [], []
    def fetch(item):
        with lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
            fetched.append(item["security_key"])
        time.sleep(.003)
        with lock:
            state["active"] -= 1
        return {"price": 100}
    try:
        result = runner.run([candidate(i) for i in range(11)], fetch, lambda item, snapshot: applied.append(item["security_key"]) or 2, timeout_seconds=1)
        assert result["total"] == result["checked"] == result["updated"] == 11
        assert result["accepted"] == 22 and result["remaining"] == result["failed"] == 0
        assert len(set(fetched)) == len(set(applied)) == 11
        assert state["max_active"] <= 3
    finally:
        runner._pool.shutdown(wait=True)


def test_slow_fetch_does_not_prevent_fast_siblings_or_allow_late_writes():
    runner = AutomaticSecurityRefresh()
    release, started = Event(), Event()
    applied = []
    def fetch(item):
        if item["security_key"] == "security-0":
            started.set()
            release.wait(1)
        return {"price": 100}
    try:
        beginning = time.monotonic()
        result = runner.run([candidate(i) for i in range(8)], fetch, lambda item, _: applied.append(item["security_key"]) or True, timeout_seconds=.08)
        assert started.is_set() and time.monotonic() - beginning < .4
        assert result["checked"] == result["updated"] == 7
        assert result["timed_out"] == result["remaining"] == 1
        assert "security-0" not in applied
        release.set()
        runner._pool.shutdown(wait=True)
        assert len(applied) == 7
    finally:
        release.set()
        runner._pool.shutdown(wait=True)


def test_retry_reuses_ongoing_fetch_and_applies_current_candidate_only():
    runner = AutomaticSecurityRefresh(max_workers=1)
    release, started = Event(), Event()
    fetched, applied = [], []
    def fetch(item):
        fetched.append(item["quantity"])
        started.set()
        release.wait(1)
        return {"price": 100}
    try:
        first = runner.run([candidate(quantity=1)], fetch, lambda *_: False, timeout_seconds=.01)
        assert started.wait(.3) and first["timed_out"] == 1
        second = runner.run([candidate(quantity=2)], fetch, lambda *_: False, timeout_seconds=.01)
        assert second["timed_out"] == 1 and fetched == [1]
        def apply(item, snapshot):
            applied.append((item["quantity"], snapshot["price"]))
            return True
        # Release during the next run, so it subscribes to the existing request.
        from threading import Timer
        timer = Timer(.01, release.set)
        timer.start()
        third = runner.run([candidate(quantity=3)], fetch, apply, timeout_seconds=.5)
        timer.join()
        assert fetched == [1] and applied == [(3, 100)]
        assert third["updated"] == 1
    finally:
        release.set()
        runner._pool.shutdown(wait=True)


def test_previous_timeout_cannot_create_an_unbounded_executor_backlog():
    runner = AutomaticSecurityRefresh(max_workers=1)
    release, started = Event(), Event()
    fetched = []
    def fetch(item):
        fetched.append(item["security_key"])
        started.set()
        release.wait(1)
        return {}
    try:
        runner.run([candidate()], fetch, lambda *_: True, timeout_seconds=.01)
        assert started.wait(.3)
        result = runner.run([candidate(i) for i in range(1, 10)], fetch, lambda *_: True, timeout_seconds=.01)
        assert fetched == ["security-0"]
        assert result["remaining"] == 9 and result["checked"] == 0
        assert len(runner._inflight) == 1
    finally:
        release.set()
        runner._pool.shutdown(wait=True)


def test_cancellation_prevents_application_of_finished_and_future_results():
    runner = AutomaticSecurityRefresh()
    stop, release = Event(), Event()
    applied = []
    def fetch(item):
        stop.set()
        release.wait(.1)
        return {"price": 100}
    try:
        result = runner.run([candidate(i) for i in range(8)], fetch, lambda item, _: applied.append(item) or True, cancelled=stop.is_set, timeout_seconds=.5)
        assert result["cancelled"] and result["checked"] == 0
        release.set()
        runner._pool.shutdown(wait=True)
        assert not applied
    finally:
        release.set()
        runner._pool.shutdown(wait=True)


def test_fetch_and_apply_errors_do_not_stop_other_securities_or_expose_messages():
    runner = AutomaticSecurityRefresh()
    def fetch(item):
        if item["security_key"] == "security-0":
            raise RuntimeError("https://private.example/?api_key=secret")
        return {}
    def apply(item, snapshot):
        if item["security_key"] == "security-1":
            raise ValueError("private-token")
        return 1
    try:
        result = runner.run([candidate(i) for i in range(5)], fetch, apply, timeout_seconds=.5)
        assert result["checked"] == 5 and result["updated"] == 3 and result["failed"] == 2
        assert result["remaining"] == 0
        assert {entry["error_type"] for entry in result["diagnostics"]} == {"RuntimeError", "ValueError"}
        assert "private" not in str(result) and "secret" not in str(result)
    finally:
        runner._pool.shutdown(wait=True)


def test_duplicate_keys_are_fetched_and_applied_once_per_run():
    runner = AutomaticSecurityRefresh()
    fetched, applied = [], []
    try:
        result = runner.run([candidate(), candidate(quantity=2)], lambda item: fetched.append(item) or {}, lambda item, _: applied.append(item) or True)
        assert result["total"] == result["checked"] == 1
        assert len(fetched) == len(applied) == 1 and applied[0]["quantity"] == 2
    finally:
        runner._pool.shutdown(wait=True)


def test_expired_or_precancelled_runs_start_no_provider_work():
    runner = AutomaticSecurityRefresh()
    fetched = []
    try:
        first = runner.run([candidate()], lambda item: fetched.append(item), lambda *_: True, timeout_seconds=0)
        second = runner.run([candidate()], lambda item: fetched.append(item), lambda *_: True, cancelled=lambda: True)
        assert not fetched
        assert first["remaining"] == second["remaining"] == 1
        assert second["cancelled"]
    finally:
        runner._pool.shutdown(wait=True)
