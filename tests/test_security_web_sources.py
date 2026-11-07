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
    assert result["evidence"] == [] and result["source_status"] == result["code"] == "request_limit"
    assert result["failure_stage"] == "request_budget"
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
    assert result["code"] == "source_read_failed" and not result["evidence"]
    assert budget.used == 4 and len(calls) == 3
    assert result["failure_stage"] == "source_read"
    assert result["diagnostics"] == {"search_requests": 1, "source_requests": 3, "read_failures": 3, "identity_rejections": 0, "empty_pages": 0}


@pytest.mark.parametrize("market", ["TASE", "TLV", "TELAVIV", "Tel Aviv"])
@pytest.mark.parametrize("asset", ["EQUITY", "STOCK", "SHARE"])
def test_israeli_share_queries_use_stock_terms_instead_of_fund_redemption(market, asset):
    queries = []
    budget = RequestBudget()
    result = research_sources({"symbol": "1101534", "stock_market": market, "asset_class": asset, "currency": "ILS"}, {}, budget,
                              search=lambda query, _key: queries.append(query) or [], fetch=lambda _: pytest.fail("No source links returned"))
    assert "1101534" in queries[0] and "מניה שער תאריך אגורות" in queries[0]
    assert "פדיון" not in queries[0]
    assert result["code"] == "data_unavailable" and budget.used == 1


@pytest.mark.parametrize("asset", ["FUND", "MUTUALFUND", "MUTUAL_FUND"])
def test_only_real_fund_types_use_fund_redemption_search_terms(asset):
    queries = []
    research_sources({"symbol": "5139324", "stock_market": "TLV", "asset_class": asset}, {}, RequestBudget(),
                     search=lambda query, _key: queries.append(query) or [])
    assert "מחיר פדיון" in queries[0] and "מניה" not in queries[0]


@pytest.mark.parametrize("asset", ["BOND", "UNKNOWN", "", "ETF"])
def test_other_or_unknown_numeric_tase_types_do_not_inherit_fund_assumptions(asset):
    queries = []
    research_sources({"symbol": "1234567", "stock_market": "TASE", "asset_class": asset}, {}, RequestBudget(),
                     search=lambda query, _key: queries.append(query) or [])
    assert "מחיר שער תאריך מטבע" in queries[0]
    assert "פדיון" not in queries[0] and "מניה" not in queries[0]


@pytest.mark.parametrize("text,empty,identity", [("", 1, 0), ("Please enable JavaScript", 0, 1), ("Another security 9999999", 0, 1)])
def test_source_shell_or_wrong_identity_is_distinct_from_source_access_failure(text, empty, identity):
    result = research_sources({"symbol": "1101534", "stock_market": "TASE", "asset_class": "EQUITY"}, {}, RequestBudget(),
                              search=lambda *_: [{"url": "https://exchange.example/share/1101534"}], fetch=lambda _: text)
    assert result["code"] == "source_identity_unavailable" and not result["evidence"]
    assert result["failure_stage"] == "source_identity"
    assert result["diagnostics"]["empty_pages"] == empty
    assert result["diagnostics"]["identity_rejections"] == identity
    assert result["diagnostics"]["read_failures"] == 0


def test_source_failures_and_shells_do_not_stop_the_next_matching_page_or_leak_details():
    from app.price_agent import PriceAgentError
    calls = []
    def fetch(url):
        calls.append(url)
        if url.endswith("blocked"):
            raise PriceAgentError("private-token https://private.example/")
        if url.endswith("shell"):
            return "Enable JavaScript"
        return "Public source identifies security1101534; no dated price has been established."
    budget = RequestBudget()
    result = research_sources({"symbol": "1101534", "stock_market": "TASE", "asset_class": "EQUITY"}, {}, budget,
                              search=lambda *_: [{"url": "https://exchange.example/" + path} for path in ("blocked", "shell", "real")], fetch=fetch)
    assert result["code"] == "evidence_found" and budget.used == len(calls) + 1 == 4
    assert "private" not in str(result)
    assert result["diagnostics"] == {"search_requests": 1, "source_requests": 3, "read_failures": 1, "identity_rejections": 1, "empty_pages": 0}
    # This is source evidence only; research_sources never proposes or saves a price.
    assert not any(key in result for key in ("price", "price_input", "updated", "saved"))
