"""Independent acceptance tests: controlled real worker threads, no provider access."""
from copy import deepcopy
from threading import Event, RLock, Thread
import time

from app.portfolio_ai_research import PortfolioAIResearch


def security(n):
    return {"security_key": f"QA{n}|NYSE|USD", "symbol": f"QA{n}", "stock_market": "NYSE", "currency": "USD"}


def eventually(predicate):
    until = time.monotonic() + 5
    while time.monotonic() < until:
        result = predicate()
        if result:
            return result
        time.sleep(.005)
    raise AssertionError("Controlled worker did not reach required state")


class ControlledChildren:
    def __init__(self):
        self.jobs = {}
        self.calls = []
        self.releases = {}
        self.failures = set()
        self.lock = RLock()
        self.threads = []

    def settings(self):
        return {"max_tool_loops": 8, "max_rest_calls": 8, "max_web_calls": 8, "research_concurrency": 2}

    def _outcome_reader(self):
        return []

    def start(self, owner, headers, language, scope, *, security_keys, **options):
        assert len(security_keys) == 1
        with self.lock:
            identifier = str(len(self.calls) + 1)
            self.calls.append(security_keys[0])
            release = self.releases[identifier] = Event()
            self.jobs[identifier] = {"request_id": identifier, "status": "running", "outcomes": [],
                "counts": {"web_requests": 1}, "progress": {"stage": "researching", "completed": 0, "total": 1}}
        def finish():
            assert release.wait(8)
            with self.lock:
                failed = identifier in self.failures
                self.jobs[identifier].update(status="failed" if failed else "completed", code="provider_unavailable" if failed else "data_found",
                    outcomes=[{"security_key": security_keys[0], "status": "unavailable" if failed else "updated", "attempted": True}])
        thread = Thread(target=finish, daemon=True)
        self.threads.append(thread)
        thread.start()
        return self.get(identifier, owner)

    def get(self, identifier, owner):
        with self.lock:
            return deepcopy(self.jobs[identifier])

    def release_all(self):
        for release in list(self.releases.values()):
            release.set()
        for thread in self.threads:
            thread.join(1)


def test_parallel_window_out_of_order_progress_and_branch_dependency():
    market, credit = ControlledChildren(), ControlledChildren()
    parent = PortfolioAIResearch(market, credit,
        lambda scope: {"market_items": [security(n) for n in (1, 2, 3)], "credit_items": [security(4)]}, poll_seconds=.002)
    request = parent.start("qa-owner", {}, "en")
    status = lambda: parent.get(request["request_id"], "qa-owner")
    try:
        eventually(lambda: len(market.calls) == 2)
        assert not credit.calls
        assert status()["progress"]["completed"] == 0
        assert len(status()["progress"]["current_securities"]) == 2
        market.releases["2"].set()
        eventually(lambda: len(market.calls) == 3)
        assert status()["progress"]["completed"] == 1
        assert {row["security_key"] for row in status()["progress"]["current_securities"]} == {security(1)["security_key"], security(3)["security_key"]}
        assert not credit.calls
        market.release_all()
        eventually(lambda: len(credit.calls) == 1)
        credit.release_all()
        eventually(lambda: status()["status"] == "completed")
        assert status()["progress"]["current_securities"] == []
    finally:
        market.release_all()
        credit.release_all()


def test_failure_drains_running_sibling_and_resume_skips_its_success():
    credit = ControlledChildren()
    parent = PortfolioAIResearch(ControlledChildren(), credit,
        lambda scope: {"market_items": [], "credit_items": [security(n) for n in (1, 2, 3, 4)]}, poll_seconds=.002)
    request = parent.start("qa-owner", {}, "en")
    status = lambda: parent.get(request["request_id"], "qa-owner")
    try:
        eventually(lambda: len(credit.calls) == 2)
        credit.failures.add("1")
        credit.releases["1"].set()
        eventually(lambda: len(status()["children"]) == 1)
        assert status()["status"] == "running"
        assert len(credit.calls) == 2
        credit.releases["2"].set()
        eventually(lambda: status()["status"] == "failed")
        assert status()["credit_ratings"]["progress"]["completed"] == 1
        assert status()["progress"]["current_securities"] == []
        parent.start("qa-owner", {}, "en", resume_request_id=request["request_id"])
        eventually(lambda: len(credit.calls) == 4)
        assert security(2)["security_key"] not in credit.calls[2:]
        credit.release_all()
        eventually(lambda: len(credit.calls) == 5)
        credit.release_all()
        eventually(lambda: status()["status"] == "completed")
        assert set(credit.calls[2:]) == {security(n)["security_key"] for n in (1, 3, 4)}
    finally:
        credit.release_all()


def test_poll_error_must_not_orphan_an_already_running_child():
    class BrokenPoll(ControlledChildren):
        def get(self, identifier, owner):
            # start() obtains its initial running snapshot before the parent's
            # first poll; only the later coordinator read fails once.
            calls = getattr(self, "reads", {})
            calls[identifier] = calls.get(identifier, 0) + 1
            self.reads = calls
            if identifier == "1" and calls[identifier] == 2:
                raise RuntimeError("synthetic temporary polling failure")
            return super().get(identifier, owner)

    credit = BrokenPoll()
    parent = PortfolioAIResearch(ControlledChildren(), credit,
        lambda scope: {"market_items": [], "credit_items": [security(1), security(2), security(3)]}, poll_seconds=.002)
    request = parent.start("qa-owner", {}, "en")
    status = lambda: parent.get(request["request_id"], "qa-owner")
    try:
        eventually(lambda: len(credit.calls) == 2)
        credit.releases["2"].set()
        # Wait for the sibling to finalize, then the unresolved child must
        # still belong to the running parent until its own worker exits.
        eventually(lambda: credit.jobs["2"]["status"] == "completed")
        time.sleep(.03)
        assert status()["status"] == "running", "Polling failure orphaned a running child"
        assert len(credit.calls) == 2
        credit.releases["1"].set()
        eventually(lambda: status()["status"] == "failed")
        assert status()["credit_ratings"]["progress"]["completed"] == 2
    finally:
        credit.release_all()


def test_parallel_finalization_preserves_profile_provenance_in_isolated_sqlite(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timezone
    from threading import Barrier
    from app import main
    from app.local_portfolio import LocalPortfolioStore

    store = LocalPortfolioStore(tmp_path / "qa.sqlite")
    candidates = [{**security(n), "asset_class": "EQUITY", "location": "US", "name": f"QA{n}",
                   "missing_fields": ["profile"], "needs_industry": True, "needs_name": False} for n in range(1, 9)]
    for candidate in candidates:
        store.save_manual_security(candidate)
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "_enrichment_candidates", lambda **_: {"items": deepcopy(candidates)})
    monkeypatch.setattr(main, "_enrichment_scope_keys", lambda _: {row["security_key"] for row in candidates})
    monkeypatch.setattr(main, "_record_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "clear_portfolio_cache", lambda: None)
    original_read = store.get_preference
    def slow_read(*args, **kwargs):
        value = original_read(*args, **kwargs)
        time.sleep(.003)
        return value
    monkeypatch.setattr(store, "get_preference", slow_read)
    barrier = Barrier(len(candidates))
    def save(candidate):
        key = candidate["security_key"]
        text = f"{candidate['symbol']} NYSE Industry: Software"
        source = {"url": "https://example.invalid/" + candidate["symbol"], "text": text,
                  "retrieved_at": datetime.now(timezone.utc).isoformat()}
        proposal = {"profiles": [{"security_key": key, "field": "industry", "value": "Software",
                                 "source_url": source["url"], "evidence_quote": text}]}
        barrier.wait(timeout=5)
        return main._save_enrichment_outcomes([{**candidate, "status": "unavailable", "code": "data_unavailable", "attempted": True}],
            "qa-owner", key, proposal=proposal, candidates={key: candidate}, evidence_by_key={key: [source]})
    with ThreadPoolExecutor(max_workers=len(candidates)) as workers:
        results = list(workers.map(save, candidates))
    assert all(result[0]["available_fields"] == ["profile"] for result in results)
    assert set(original_read("security_enrichment_sources_v1", {})) == {row["security_key"] + "|industry" for row in candidates}
    assert set(original_read("security_enrichment_outcomes_v1", {})) == {row["security_key"] for row in candidates}
    assert {row["industry"] for row in store.list_security_industry_overrides()} == {"Software"}
