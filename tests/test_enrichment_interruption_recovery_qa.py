"""Interrupted retrieval can retain independently fetched facts only as allowed."""
from copy import deepcopy
import json

import pytest

from app.llm_assistant import AssistantError
from app.security_enrichment import RestError
from app.security_source_context import context_records
from test_enrichment_mixed_batch_qa import TASE_KEY, configure_batch
from test_research_tools_qa import research_app, run_job, tool, final
from test_security_source_context import TASE, URL


@pytest.mark.parametrize("interruption,expected_reason,should_save", [
    ("assistant-limit", "request_limit", True),
    ("rest-limit", "request_limit", True),
    ("timeout", "planner_timeout", True),
    ("valid-empty", None, False),
    ("generic-error", None, False),
    ("cancelled", None, False),
    ("authentication-expired", None, False),
    ("closed-after-read", "request_limit", False),
    ("api-managed-after-read", "request_limit", False),
])
def test_interruption_retention_through_authenticated_finalizer_and_real_main_writer(
        research_app, monkeypatch, interruption, expected_reason, should_save):
    from app import main
    env = research_app
    candidates = configure_batch(env)
    stock = candidates[1]
    # Exercise the existing API-ownership guard as well as the open-position guard.
    stock["api_data_route"] = {"owner": "ai"}
    api_owner = {"value": "ai"}
    preferences, writes, writer_calls = {}, [], []

    class Store:
        def manual_security(self, symbol, market):
            return deepcopy(next(item for item in candidates if item["symbol"] == symbol))

        def save_security_industry_override(self, payload):
            stock["industry"] = payload["industry"]
            writes.append(("industry", payload["industry"]))

        def save_manual_security(self, payload):
            raise AssertionError("Known names must not change during recovery")

        def save_prices(self, *args, **kwargs):
            raise AssertionError("No price was requested or supported by the final proposal")

        def get_preference(self, key, default):
            return deepcopy(preferences.get(key, default))

        def set_preference(self, key, value):
            preferences[key] = deepcopy(value)

    def inventory(**kwargs):
        items = [deepcopy(item) for item in candidates if item["quantity"] != 0
                 and (item["security_key"] != TASE_KEY or not stock["industry"])]
        return {"items": items, "total_count": len(items), "research_available": True}

    monkeypatch.setattr(main, "local_store", Store())
    monkeypatch.setattr(main, "_enrichment_candidates", inventory)
    monkeypatch.setattr(main, "_security_api_route", lambda *_args: {"owner": api_owner["value"]})
    monkeypatch.setattr(main, "enriched_local_holdings", lambda **_kwargs: [{"holding": deepcopy(item)} for item in candidates])
    monkeypatch.setattr(main, "to_dict", lambda value: value)
    monkeypatch.setattr(main, "_record_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "clear_portfolio_cache", lambda: None)
    env.manager._candidate_reader = inventory
    env.session._fetch = lambda *_args: {"url": URL, "text": TASE}
    original_research = env.manager._research_tool_fetcher

    def research(candidate, action, arguments):
        result = original_research(candidate, action, arguments)
        for source in result.get("evidence", []):
            source["context_records"] = context_records(source, candidate)
        return result

    def writer(*args, **kwargs):
        writer_calls.append(deepcopy(kwargs))
        return main._save_enrichment_outcomes(*args, **kwargs)

    env.manager._research_tool_fetcher = research
    env.manager._outcome_writer = writer

    def read_hint(messages):
        content = next(message["content"] for message in messages if message["role"] == "user")
        supplied = json.loads(content.split("Candidates: ", 1)[1])
        candidate = next(item for item in supplied if item["security_key"] == TASE_KEY)
        return tool("read_security_source", security_key=TASE_KEY, source_id=candidate["source_hints"][0]["source_id"])

    def interrupt_after_fetched_evidence(messages):
        if interruption == "valid-empty":
            return final()
        if interruption == "authentication-expired":
            env.state.expired = True
            return tool("search_security_sources", security_key=TASE_KEY, query="1101534 industry")
        if interruption == "closed-after-read":
            stock["quantity"] = 0
        if interruption == "api-managed-after-read":
            api_owner["value"] = "api"
        if interruption == "rest-limit":
            raise RestError("request_limit")
        if interruption == "timeout":
            raise AssistantError("The local planner timed out")
        if interruption == "generic-error":
            raise AssistantError("The local planner disconnected")
        if interruption == "cancelled":
            raise AssistantError("The operation was cancelled")
        raise AssistantError("The request call limit was reached")

    env.state.responses = [read_hint, interrupt_after_fetched_evidence]
    result = run_job(env)
    if interruption == "authentication-expired":
        assert result["code"] == "authentication_expired" and result["status"] == "failed"
        assert writer_calls == [], "Expired authentication must prevent the saving endpoint from executing"
        assert env.manager._jobs[result["request_id"]].get("_context_recovery_reason") is None
    else:
        assert len(writer_calls) == 1
        assert writer_calls[0].get("context_recovery_reason") == expected_reason
        assert bool(writer_calls[0]["evidence_by_key"].get(TASE_KEY)), "The recovery benchmark requires actual fetched full evidence"
    assert bool(writes) is should_save
    assert stock["name"] == "סלקום"
    if should_save:
        assert writes == [("industry", "ריאלי - מסחר ושרותים - תקשורת ומדיה")]
        outcome = next(item for item in result["outcomes"] if item["security_key"] == TASE_KEY)
        assert outcome["recovery_reason"] == expected_reason
        assert outcome["recovered_from_invalid_proposal"] is False
        assert outcome["evidence_rejected"] is False and outcome["missing_fields"] == []
        assert result["status"] == "failed", "A preserved fact must not hide the request interruption"
    else:
        assert stock["industry"] == ""
        assert not preferences.get("security_enrichment_sources_v1"), "No unsupported provenance may be written"
    assert result["counts"]["model_requests"] <= 5 and result["counts"]["rest_requests"] <= 5
