"""An exhausted research budget must not be reported as missing configuration."""
import pytest

from app.security_web_research import research_sources
from app.us_market_providers import RequestBudget


@pytest.mark.parametrize("phase", ["search", "source"])
def test_exhausted_shared_budget_does_not_search_or_fetch_again(phase):
    budget = RequestBudget(limit=1)
    calls = []
    if phase == "search":
        budget.consume()

    def search(*_args):
        calls.append("search")
        return [{"url": "https://exchange.example/qa"}]

    def fetch(_url):
        calls.append("fetch")
        raise AssertionError("The exhausted budget must prevent a fetch")

    result = research_sources({"symbol": "QA"}, {"search_api_key": "synthetic"}, budget,
                              search=search, fetch=fetch)
    assert result == {"evidence": [], "source_status": "request_limit", "code": "request_limit"}
    assert calls == ([] if phase == "search" else ["search"])
    assert budget.used == 1


def test_missing_search_configuration_never_consumes_upstream_budget():
    budget = RequestBudget()
    result = research_sources({"symbol": "QA"}, {"search_provider": "brave"}, budget)
    assert result["code"] == "search_not_configured" and result["evidence"] == []
    assert budget.used == 0


def test_key_free_research_fetches_actual_source_and_never_returns_search_snippet_as_evidence():
    budget = RequestBudget()
    calls = []
    def search(query, key):
        calls.append(("search", query, key))
        return [{"url": "https://exchange.example/fund/5139324", "description": "Invented snippet price 999"}]
    def fetch(url):
        calls.append(("fetch", url))
        return "Actual public source: fund5139324 price100.00 dated06/11/2026"
    result = research_sources({"symbol": "5139324", "stock_market": "TASE"}, {}, budget, search=search, fetch=fetch)
    assert result["code"] == "evidence_found" and result["search_provider"] == "duckduckgo"
    assert result["evidence"][0]["text"].startswith("Actual public source")
    assert "999" not in str(result["evidence"])
    assert "מחיר" in calls[0][1] and calls[0][2] == ""
    assert budget.used == len(calls) == 2


@pytest.mark.parametrize("code", ["search_blocked", "provider_unavailable", "search_not_configured"])
def test_failed_search_is_counted_and_preserves_safe_error_class(code):
    from app.security_search import SearchFailure
    budget = RequestBudget()
    def search(*_args):
        raise SearchFailure(code, "Safe failure")
    result = research_sources({"symbol": "QA"}, {}, budget, search=search, fetch=lambda _: pytest.fail("No source should be fetched after search failure"))
    assert result["code"] == result["source_status"] == code
    assert budget.used == 1


def test_real_empty_search_is_data_unavailable_not_a_configuration_error():
    budget = RequestBudget()
    result = research_sources({"symbol": "QA"}, {}, budget, search=lambda *_: [], fetch=lambda _: pytest.fail("No result URL exists"))
    assert result["code"] == "data_unavailable" and result["evidence"] == []
    assert budget.used == 1


def test_failed_source_reads_are_counted_and_report_provider_failure():
    from app.price_agent import PriceAgentError
    budget = RequestBudget()
    calls = []
    def fetch(url):
        calls.append(url)
        raise PriceAgentError("Source failed")
    result = research_sources({"symbol": "QA"}, {}, budget, search=lambda *_: [{"url": f"https://exchange.example/{i}"} for i in range(3)], fetch=fetch)
    assert result["code"] == "provider_unavailable" and not result["evidence"]
    assert budget.used == 4 and len(calls) == 3
