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
    result = research_sources({"symbol": "QA"}, {}, budget)
    assert result["code"] == "research_unavailable" and result["evidence"] == []
    assert budget.used == 0
