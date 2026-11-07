"""Independent offline reproduction of the reported mixed three-security click.

These tests establish request contracts and local application behavior. They do
not establish that the default Codex provider retrieves these facts at runtime.
"""
from copy import deepcopy
import json

import pytest

from app.security_source_context import context_records
from app.security_research_tools import ResearchFailure
from test_research_tools_qa import research_app, run_job, tool, final, last_result
from test_security_source_context import TASE, URL


TASE_KEY = "1101534|TASE|ILS"


def mixed_candidates():
    def bond(symbol):
        return {"security_key": symbol + "|MANUAL|USD", "symbol": symbol,
                "stock_market": "MANUAL", "currency": "USD", "asset_class": "BOND", "location": "USA",
                "name": "Known bond", "quantity": 1000, "quote_unit": "currency",
                "missing_fields": ["prices"], "available_fields": [],
                "needs_name": False, "needs_industry": False}
    return [bond("88059ESH8"),
            {"security_key": TASE_KEY, "symbol": "1101534", "secondary_symbol": "CEL",
             "stock_market": "TASE", "currency": "ILS", "asset_class": "STOCK",
             "name": "סלקום", "industry": "", "quantity": 1, "location": "Israel",
             "quote_unit": "agorot", "missing_fields": ["profile"], "available_fields": [],
             "needs_name": False, "needs_industry": True},
            bond("121899CH9")]


def configure_batch(env):
    candidates = mixed_candidates()
    env.manager._candidate_reader = lambda: {"items": deepcopy(candidates), "total_count": 3,
                                              "research_available": True}
    env.manager._source_hint_reader = env.session.discover
    return candidates


def test_mixed_batch_final_turn_preserves_machine_readable_proposal_contract(research_app):
    """The last system instruction must preserve the research JSON contract."""
    env = research_app
    configure_batch(env)
    # Spend exactly the three permitted research operations; no external calls.
    env.state.responses = [
        tool("search_security_sources", security_key=TASE_KEY, query="1101534 industry"),
        tool("search_security_sources", security_key=TASE_KEY, query="1101534 ענף"),
        tool("search_security_sources", security_key=TASE_KEY, query="סלקום ענף בבורסה"),
        final(),
    ]
    result = run_job(env)
    assert result["counts"]["rest_requests"] == 5
    assert result["counts"]["model_requests"] == 4
    messages = env.state.model[-1]["messages"]
    last_system = next(message["content"] for message in reversed(messages) if message["role"] == "system")
    assert "JSON" in last_system and "records" in last_system, (
        "At the shared limit, the final system instruction must demand the same "
        "research proposal JSON, including an empty records array for unknowns; "
        "a prose unknowns instruction produces proposal_invalid.")


@pytest.mark.parametrize("nested_answer", [False, True, "malformed"],
                         ids=["serialized-answer", "nested-bridge-answer", "malformed-final-recovery"])
def test_mixed_batch_industry_only_finalization_preserves_known_name_and_bond_prices(research_app, monkeypatch, nested_answer):
    """Select only the missing industry from fetched full official source text."""
    from app import main
    env = research_app
    candidates = configure_batch(env)
    stock = candidates[1]
    writes, preferences = [], {}

    class Store:
        def manual_security(self, symbol, market):
            return deepcopy(next(item for item in candidates if item["symbol"] == symbol))

        def save_security_industry_override(self, payload):
            stock["industry"] = payload["industry"]
            writes.append(("industry", payload["industry"]))

        def save_manual_security(self, payload):
            raise AssertionError("An already known name must not be overwritten")

        def save_prices(self, *args, **kwargs):
            raise AssertionError("No bond or price proposal was supported")

        def get_preference(self, key, default):
            return deepcopy(preferences.get(key, default))

        def set_preference(self, key, value):
            preferences[key] = deepcopy(value)

    def inventory(**kwargs):
        return {"items": [deepcopy(item) for item in candidates
                          if item["security_key"] != TASE_KEY or not stock["industry"]],
                "total_count": 3 if not stock["industry"] else 2, "research_available": True}

    monkeypatch.setattr(main, "local_store", Store())
    monkeypatch.setattr(main, "_enrichment_candidates", inventory)
    document = {"url": URL, "text": TASE, "retrieved_at": "2026-11-07T12:00:00+00:00"}

    def fetch(url, settings):
        env.state.reads.append(url)
        assert url == URL
        return deepcopy(document)

    env.session._fetch = fetch
    original_research = env.manager._research_tool_fetcher

    def research(candidate, action, arguments):
        result = original_research(candidate, action, arguments)
        for source in result.get("evidence", []):
            source["context_records"] = context_records(source, candidate)
        return result

    def writer(outcomes, owner, request_id, **kwargs):
        applied = main._apply_enrichment_proposals(kwargs["proposal"], kwargs["evidence_by_key"], kwargs["candidates"])
        return [{**item, **applied.get(item["security_key"], {})} for item in outcomes]

    env.manager._research_tool_fetcher = research
    env.manager._outcome_writer = writer

    def read_hint(messages):
        user = next(message["content"] for message in messages if message["role"] == "user")
        supplied = json.loads(user.split("Candidates: ", 1)[1])
        assert {item["symbol"] for item in supplied} == {"88059ESH8", "1101534", "121899CH9"}
        supplied_stock = next(item for item in supplied if item["security_key"] == TASE_KEY)
        assert supplied_stock["needs_name"] is False and supplied_stock["needs_industry"] is True
        for item in supplied:
            if item["asset_class"] == "BOND":
                assert all(hint["url"] != URL and hint["discovery_only"] is True
                           for hint in item.get("source_hints", []))
        hint, = supplied_stock["source_hints"]
        assert hint["url"] == URL
        return tool("read_security_source", security_key=TASE_KEY, source_id=hint["source_id"])

    def select_industry(messages):
        source, = last_result(messages)["evidence"]
        record, = [record for record in source["context_records"]
                   if record["kind"] == "profile" and record["field"] == "industry"]
        proposal = {"records": [{"security_key": TASE_KEY, "source_id": source["source_id"],
                                  "record_id": record["record_id"]}], "observations": [], "profiles": []}
        if nested_answer == "malformed":
            return {"choices": [{"message": {"content": "Unverified model prose: bond prices are unknown."}}]}
        if nested_answer:
            from app.codex_bridge import decision_response
            return decision_response({"action": "answer", "tool": "", "arguments": "",
                                      "answer": proposal, "support_status": "answered"}, [], research=True)
        return {"choices": [{"message": {"content": json.dumps({"answer": json.dumps(proposal),
                                                                  "support_status": "answered"})}}]}

    env.state.responses = [read_hint, select_industry]
    result = run_job(env)
    if nested_answer == "malformed":
        assert result["status"] == "failed" and result["code"] == "proposal_invalid"
        assert result["failure"]["code"] == "proposal_invalid"
    else:
        assert result["status"] == "completed" and result["failure"] is None, json.dumps(result, ensure_ascii=False)
    assert result["summary"]["updated"] == 1 and result["summary"]["not_attempted"] == 2
    outcomes = {item["symbol"]: item for item in result["outcomes"]}
    assert outcomes["1101534"]["missing_fields"] == []
    assert outcomes["1101534"]["evidence_rejected"] is False
    assert outcomes["1101534"]["recovered_from_invalid_proposal"] is (nested_answer == "malformed")
    assert all(outcomes[symbol]["attempted"] is False for symbol in ("88059ESH8", "121899CH9"))
    assert stock["name"] == "סלקום"
    assert writes == [("industry", "ריאלי - מסחר ושרותים - תקשורת ומדיה")]
    assert env.state.queries == [] and env.state.reads == [URL]
    assert result["counts"]["model_requests"] == 2 and result["counts"]["rest_requests"] == 3


def test_mixed_batch_search_hints_are_instrument_specific_unverified_leads(research_app):
    env = research_app
    configure_batch(env)
    env.state.responses = [final()]
    run_job(env)
    user = next(message["content"] for message in env.state.model[0]["messages"] if message["role"] == "user")
    supplied = json.loads(user.split("Candidates: ", 1)[1])
    for item in supplied:
        hints = item["search_hints"]
        assert hints and all(hint["discovery_only"] is True for hint in hints)
        queries = " ".join(hint["query"] for hint in hints)
        assert (item.get("secondary_symbol") or item["symbol"]) in queries
        if item["asset_class"] == "BOND":
            assert item["symbol"] in queries and "bond" in queries.lower()
            assert "MANUAL" not in queries and "TASE" not in queries and "1101534" not in queries
        else:
            assert "industry" in queries and "price" not in queries
    assert env.session.budget.used == 0 and env.state.reads == env.state.queries == []


def test_mixed_batch_bond_cannot_read_stock_hint_even_in_same_request(research_app):
    env = research_app
    candidates = mixed_candidates()
    hint, = env.session.discover(candidates[1])
    with pytest.raises(ResearchFailure) as failure:
        env.session.read(candidates[0], hint["source_id"])
    assert failure.value.code == "invalid_source"
    assert env.session.budget.used == 0
    assert env.state.reads == [] and env.session.evidence(candidates[0]) == []


def test_enrichment_retains_redacted_raw_model_response_only_after_authenticated_finalization(research_app, monkeypatch, tmp_path):
    from app import main
    from app.diagnostics import Diagnostics
    env = research_app
    configure_batch(env)
    diagnostics = Diagnostics(tmp_path, config={"llm": {"api_key": "qa-configured-private"}})
    monkeypatch.setattr(main, "_diagnostics", lambda: diagnostics)
    env.manager._event_writer = lambda event, **fields: main._record_log("market-data", event, **fields)
    original_writer = env.manager._outcome_writer

    def writer(*args, **kwargs):
        assert (tmp_path / "market-data.log").read_text() == "", "Audit persistence belongs to finalization"
        return original_writer(*args, **kwargs)

    env.manager._outcome_writer = writer
    raw = "Unverified 1101534 research; api_key=qa-free-text-private; qa-configured-private"
    env.state.responses = [tool("search_security_sources", security_key=TASE_KEY,
                                query="1101534 industry api_key=qa-query-private"),
                           {"choices": [{"message": {"content": raw}}]}]
    try:
        result = run_job(env)
        text = (tmp_path / "market-data.log").read_text()
        rows = [json.loads(line) for line in text.splitlines()]
        assert result["code"] == "proposal_invalid"
        assert rows and all(row["request_id"] == result["request_id"] for row in rows)
        final_response = [row for row in rows if row["step"] == "model_response"][-1]
        assert "Unverified 1101534 research" in final_response["response"]["content"]
        assert "[REDACTED]" in final_response["response"]["content"]
        assert {"model_request", "model_response", "tool_request", "tool_response"} <= {row["step"] for row in rows}
        assert all(secret not in text for secret in ("qa-free-text-private", "qa-configured-private",
                                                     "qa-query-private", "qa-csrf", "synthetic-qa-api-key"))
        assert "_trace" not in result
        before = len(rows)
        response = env.client.post("/api/securities/enrichment/ai/" + result["request_id"] + "/finalize",
                                   headers=env.headers, json={"proposal": raw})
        assert response.status_code == 200
        assert len((tmp_path / "market-data.log").read_text().splitlines()) == before
    finally:
        diagnostics.close()
