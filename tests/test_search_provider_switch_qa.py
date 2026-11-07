"""Independent provider choice, budget and captured organic-result contracts."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import httpx
import pytest

from app.security_enrichment import PREFIX
from app.security_enrichment import WEB_CATALOG
from app.security_search import SearchFailure, parse_yahoo_results, selected_search_provider
from test_research_tools_qa import CANDIDATE, KEY, SOURCE, research_app, tool, final, run_job
from test_security_search import client_mock


def test_explicit_provider_switch_spends_shared_budget_and_identical_full_choice_is_cached(research_app, monkeypatch):
    from app import main, security_research_tools
    env = research_app
    settings = {"search_provider": "duckduckgo", "search_api_key": ""}
    calls = []

    def search(query, current_settings):
        calls.append((query, deepcopy(current_settings)))
        if selected_search_provider(current_settings) == "duckduckgo":
            raise SearchFailure("search_blocked", "Synthetic search challenge")
        return [{"url": SOURCE, "title": "Public listing lead"}]

    env.session.settings = deepcopy(settings)
    env.session._search = search
    def session_factory(_settings, budget):
        env.session.budget = budget
        return env.session

    monkeypatch.setattr(security_research_tools, "ResearchSession", session_factory)
    monkeypatch.setattr(main, "_enrichment_candidates", lambda **_kwargs: {"items": [deepcopy(CANDIDATE)]})
    monkeypatch.setattr(main, "_security_api_route", lambda *_args: {"owner": "ai"})
    env.manager._research_tool_fetcher = main._enrichment_research_tool
    query = "QAEXAMPLE exact listing"
    env.state.responses = [tool("search_security_sources", query=query),
                           tool("search_security_sources", query=query, provider="yahoo"),
                           tool("search_security_sources", query=query, provider="yahoo"), final()]
    result = run_job(env)
    assert [selected_search_provider(settings) for _, settings in calls] == ["duckduckgo", "yahoo"]
    assert len(calls) == env.session.budget.used == 2
    assert env.session.settings == settings, "Per-call provider choice must not mutate configured settings"
    assert result["counts"]["rest_requests"] == 4 and result["counts"]["model_requests"] == 4
    assert result["counts"]["web_requests"] == 2
    responses = [entry for entry in env.manager._jobs[result["request_id"]]["_web_responses"].values()]
    assert {(entry["source_status"], entry["search_provider"]) for entry in responses} == {
        ("search_blocked", "duckduckgo"), ("search_results", "yahoo")}
    assert result["summary"]["updated"] == result["summary"]["partial"] == 0
    assert env.state.reads == [] and env.session.evidence(CANDIDATE) == []


def test_unsupported_search_provider_is_rejected_by_authenticated_rest_before_research(research_app):
    env = research_app
    started = env.client.post(PREFIX + "/ai", headers=env.headers, json={}).json()
    identifier = started["request_id"]
    env.manager._jobs[identifier].update(status="running", _candidates={KEY: deepcopy(CANDIDATE)})
    response = env.client.get(PREFIX + "/web/search", headers=env.headers,
                              params={"request_id": identifier, "security_key": KEY,
                                      "query": "QAEXAMPLE listing", "provider": "arbitrary-network"})
    assert response.status_code == 422
    assert env.session.budget.used == 0 and env.state.queries == []


def test_captured_yahoo_results_preserve_exact_cusip_organic_leads_without_nav_or_query_echo():
    page = (Path(__file__).parent / "fixtures/yahoo_121899ch9_organic.html").read_text()
    result = parse_yahoo_results(page)
    expected = {"https://atlantisdatasolutions.com/bond-lookup", "https://public.com/stocks/121899ch9-bond",
                "https://fintel.io/s/us/121899ch9", "https://bondbyisin.com/", "https://ifindbonds.com/",
                "https://www.finra.org/finra-data/fixed-income/bond", "https://cbonds.com/bonds/"}
    assert {entry["url"] for entry in result} == expected
    assert all(entry["description"] == "" for entry in result), "Indexed snippets remain discovery, never evidence"
    assert "121899CH9" in next(entry["title"] for entry in result if "fintel.io" in entry["url"])


def test_yahoo_unwraps_result_redirect_locally_and_excludes_surrounding_navigation():
    target = "https://public.com/stocks/121899ch9-bond"
    page = ('<nav><a href="https://outside.example/navigation">121899CH9 bond</a></nav>'
            '<div class="algo"><p><a href="https://outside.example/query-echo">query echo</a></p>'
            '<div class="compTitle"><a href="https://r.search.yahoo.com/_ylt=synthetic/RU='
            + quote(target, safe="") + '/RK=2/RS=synthetic"><h3>Exact 121899CH9 bond</h3></a></div>'
            '<a href="https://outside.example/footer">footer</a></div>')
    assert parse_yahoo_results(page) == [{"url": target, "title": "Exact 121899CH9 bond", "description": ""}]


@pytest.mark.parametrize("status,body,code", [(202, "challenge", "search_blocked"),
                                             (429, "rate limit", "search_blocked"),
                                             (200, '<form id="challenge-form"></form>', "search_blocked"),
                                             (503, "outage", "provider_unavailable")])
def test_yahoo_failure_is_one_http_attempt_without_hidden_provider_fallback(monkeypatch, status, body, code):
    from app.security_search import search_web
    calls = client_mock(monkeypatch, lambda _: httpx.Response(status, text=body, headers={"Content-Type": "text/html"}))
    with pytest.raises(SearchFailure) as failure:
        search_web("121899CH9 bond", {"search_provider": "yahoo"})
    assert failure.value.code == code
    assert len(calls) == 1 and calls[0].url.host == "search.yahoo.com"


def configured_inventory(env, monkeypatch, key=""):
    from app import main
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.setattr(main, "config", SimpleNamespace(raw={"price_agent": {"search": {"provider": "auto", "api_key": key}}}))
    monkeypatch.setattr(main, "_enrichment_candidates", lambda **_kwargs: {"items": [deepcopy(CANDIDATE)]})
    monkeypatch.setattr(main, "_security_api_route", lambda *_args: {"owner": "ai"})
    env.manager._candidate_reader = main._ai_enrichment_candidates


@pytest.mark.parametrize("has_key", [False, True])
def test_actual_candidate_inventory_advertises_only_configured_providers_without_secrets(research_app, monkeypatch, has_key):
    env = research_app
    configured_inventory(env, monkeypatch, "qa-private-brave-key" if has_key else "")
    env.state.responses = [final()]
    result = run_job(env)
    expected = ["auto", "yahoo", "duckduckgo"] + (["brave"] if has_key else [])
    search_tool = next(item for item in env.state.model[0]["tools"]
                       if item["function"]["name"] == "search_security_sources")
    assert search_tool["function"]["parameters"]["properties"]["provider"]["enum"] == expected
    assert "setup only, not an availability guarantee" in env.state.model[0]["messages"][-1]["content"]
    assert "qa-private-brave-key" not in str(env.state.model)
    assert set(WEB_CATALOG["search_security_sources"]["parameters"]["properties"]["provider"]["enum"]) == {
        "auto", "yahoo", "duckduckgo", "brave"}, "Per-request narrowing must not mutate the shared catalog"
    assert result["counts"]["rest_requests"] == 2 and env.session.budget.used == 0


@pytest.mark.parametrize("provider", ["yahoo", "duckduckgo"])
def test_key_free_inventory_keeps_explicit_alternative_search_providers_usable(research_app, monkeypatch, provider):
    env = research_app
    configured_inventory(env, monkeypatch)
    env.state.responses = [tool("search_security_sources", query="QAEXAMPLE alternate listing source", provider=provider), final()]
    result = run_job(env)
    assert env.session.last_search_provider == provider
    assert env.state.queries == ["QAEXAMPLE alternate listing source"]
    assert result["counts"]["rest_requests"] == 3 and env.session.budget.used == 1


def test_unconfigured_brave_choice_is_rejected_before_rest_or_public_attempt(research_app, monkeypatch):
    env = research_app
    configured_inventory(env, monkeypatch)
    env.state.responses = [tool("search_security_sources", query="QAEXAMPLE listing", provider="brave"), final()]
    result = run_job(env)
    assert env.state.queries == [] and env.session.budget.used == 0
    assert result["counts"]["rest_requests"] == 2
