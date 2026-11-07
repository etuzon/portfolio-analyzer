"""Independent whole-request eight-call bounds and preserved lower settings."""
from copy import deepcopy

import pytest

from app.security_enrichment import PREFIX, RestError
from app.security_research_tools import ResearchFailure, ResearchSession, WebRequestBudget
from app.security_search import SearchFailure
from test_research_tools_qa import research_app, run_job, tool, final


def configured(env, *, model=8, rest=8):
    original = env.manager.settings
    env.manager.settings = lambda: {**deepcopy(original()), "max_tool_loops": model, "max_rest_calls": rest}


@pytest.mark.parametrize("source_status", ["search_results", "search_blocked"])
def test_six_distinct_research_attempts_use_eight_rest_slots_and_ninth_is_blocked(research_app, source_status):
    env = research_app
    configured(env)
    actions = []

    def research(candidate, action, arguments):
        actions.append((action, deepcopy(arguments)))
        return {"sources": [], "evidence": [], "source_status": source_status,
                "web_requests": len(actions),
                "diagnostics": {"search_requests": len(actions), "source_requests": 0}}

    env.manager._research_tool_fetcher = research
    env.state.responses = [tool("search_security_sources", query=f"QAEXAMPLE exact query {index}") for index in range(6)] + [final()]
    result = run_job(env)
    assert len(actions) == 6, "Inventory and finalization reserve two of eight REST slots"
    assert result["counts"]["rest_requests"] == result["counts"]["max_rest_requests"] == 8
    assert result["counts"]["model_requests"] == 7
    assert result["counts"]["max_model_requests"] == result["counts"]["max_web_requests"] == 8
    assert result["counts"]["web_requests"] == 6
    assert result["status"] == "completed" and result["failure"] is None
    job = env.manager._jobs[result["request_id"]]
    assert any(event.get("step") == "model_response" and event.get("exchange") == 7
               for event in job["_trace"]), "The expanded budget must retain the final raw model response"
    before = len(env.state.http)
    with pytest.raises(RestError) as failure:
        env.manager._request(result["request_id"], env.headers, "GET", PREFIX + "/candidates",
                             params={"request_id": result["request_id"]})
    assert failure.value.code == "request_limit"
    assert len(env.state.http) == before and job["counts"]["rest_requests"] == 8


@pytest.mark.parametrize("configured_limit,expected", [(8, 8), (99, 8), (5, 5)])
def test_nonstop_cached_planner_stops_at_configured_or_hard_model_limit(research_app, configured_limit, expected):
    env = research_app
    configured(env, model=configured_limit, rest=configured_limit)
    # Repeated choices consume model decisions while a cached successful tool
    # result must not consume additional REST or source attempts.
    env.state.responses = [tool("search_security_sources", query="QAEXAMPLE repeated exact query") for _ in range(10)]
    result = run_job(env)
    assert len(env.state.model) == result["counts"]["model_requests"] == expected
    assert result["counts"]["max_model_requests"] == result["counts"]["max_rest_requests"] == expected
    assert result["code"] == "request_limit" and result["status"] == "failed"
    assert result["counts"]["rest_requests"] == 3
    assert len(env.state.queries) == env.session.budget.used == 1
    assert env.state.model[-1]["tools"] == []
    assert len(env.state.responses) == 10 - expected


@pytest.mark.parametrize("configured_limit,expected", [(8, 8), (99, 8), (5, 5)])
def test_failed_public_searches_spend_web_budget_and_next_attempt_makes_no_request(configured_limit, expected):
    attempts = []

    def blocked(query, settings):
        attempts.append(query)
        raise SearchFailure("search_blocked", "Synthetic provider challenge")

    budget = WebRequestBudget(limit=configured_limit)
    session = ResearchSession({}, budget, search=blocked)
    candidate = {"security_key": "QAEXAMPLE|TEST|USD", "symbol": "QAEXAMPLE"}
    for index in range(expected):
        with pytest.raises(SearchFailure) as failure:
            session.search(candidate, f"QAEXAMPLE query {index}")
        assert failure.value.code == "search_blocked"
    assert len(attempts) == budget.used == budget.limit == expected
    with pytest.raises(ResearchFailure) as failure:
        session.search(candidate, "QAEXAMPLE one attempt too many")
    assert failure.value.code == "request_limit"
    assert len(attempts) == budget.used == expected and budget.remaining == 0


def test_public_budget_timeout_is_240_seconds_and_does_not_expand_ordinary_provider_limits(monkeypatch):
    from app import security_research_tools
    from app.us_market_providers import RequestBudget
    budget = WebRequestBudget(limit=99, timeout_seconds=9999)
    assert budget.limit == 8 and budget.timeout_seconds == 240
    provider_budget = RequestBudget(limit=99, timeout_seconds=9999)
    assert provider_budget.limit == 5 and provider_budget.timeout_seconds == 40
    monkeypatch.setattr(security_research_tools.time, "monotonic", lambda: budget._started + 239.99)
    budget.consume()
    assert budget.used == 1
    monkeypatch.setattr(security_research_tools.time, "monotonic", lambda: budget._started + 240)
    with pytest.raises(ResearchFailure) as failure:
        budget.consume()
    assert failure.value.code == "timeout" and budget.used == 1


@pytest.mark.parametrize("value,expected", [(None, 8), (99, 8), (5, 5)])
def test_price_research_settings_have_independent_eight_caps_and_chat_stays_five(value, expected):
    from app.price_agent import price_agent_settings
    from app.llm_assistant import assistant_settings
    section = {} if value is None else {key: value for key in ("max_model_calls", "max_rest_calls", "max_web_calls")}
    settings = price_agent_settings({"price_agent": section})
    assert {settings[key] for key in ("max_model_calls", "max_rest_calls", "max_web_calls")} == {expected}
    chat = assistant_settings({"llm": {"max_tool_loops": 99, "max_rest_calls": 99}})
    assert chat["max_tool_loops"] == chat["max_rest_calls"] == 5
