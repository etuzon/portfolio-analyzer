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
        return "Public source identifies security1101534 TASE ILS agorot Close 2901 on 06/11/2026."
    budget = RequestBudget()
    result = research_sources({"symbol": "1101534", "stock_market": "TASE", "asset_class": "EQUITY"}, {}, budget,
                              search=lambda *_: [{"url": "https://exchange.example/" + path} for path in ("blocked", "shell", "real")], fetch=fetch)
    assert result["code"] == "evidence_found" and budget.used == len(calls) + 1 == 4
    assert "private" not in str(result)
    assert result["diagnostics"] == {"search_requests": 1, "source_requests": 3, "read_failures": 1, "identity_rejections": 1, "empty_pages": 0}
    # This is source evidence only; research_sources never proposes or saves a price.
    assert not any(key in result for key in ("price", "price_input", "updated", "saved"))


def test_fallback_prioritizes_exact_identifier_urls_on_distinct_hosts_with_one_shared_budget():
    calls = []
    def search(query, _key):
        calls.append(('search', query))
        if len([call for call in calls if call[0] == 'search']) == 1:
            return [{'url': f'https://shell.example/1101534/{index}'} for index in range(5)]
        return [{'url': url} for url in (
            'https://first.example/stock/1101534',
            'https://name-only.example/equities/company',
            'https://another-name.example/instrument/27648',
            'https://last.example/quote/1101534',
        )]
    def fetch(url):
        calls.append(('fetch', url))
        if 'shell.example' in url:
            return 'דף הבית - הבורסה לניירות ערך בתל אביב | אתר הבורסה'
        if 'first.example' in url:
            from app.price_agent import PriceAgentError
            raise PriceAgentError('The source page is unavailable.')
        return '1101534 TASE שער אחרון באגורות 2901 בתאריך 06/11/2026'
    budget = RequestBudget()
    result = research_sources({'symbol': '1101534', 'stock_market': 'TASE', 'asset_class': 'EQUITY', 'missing_fields': ['prices', 'profile']},
                              {}, budget, search=search, fetch=fetch)
    assert result['code'] == 'evidence_found'
    assert result['evidence'][0]['url'] == 'https://last.example/quote/1101534'
    assert calls[2] == ('search', '1101534 מניה שער תאריך אגורות -site:shell.example')
    assert [value for kind, value in calls if kind == 'fetch'] == [
        'https://shell.example/1101534/0', 'https://first.example/stock/1101534', 'https://last.example/quote/1101534']
    assert budget.used == len(calls) == 5
    assert result['diagnostics']['search_requests'] == 2
    assert result['diagnostics']['read_failures'] == 1


def test_profile_source_is_retained_while_a_separate_dated_price_is_sought():
    urls = ['https://profile.example/1101534', 'https://quote.example/1101534']
    def fetch(url):
        return ('1101534 TASE Company name: Cellcom | Industry: Telecommunications' if url == urls[0]
                else '1101534 TASE ILS agorot Close 2901 on 06/11/2026')
    budget = RequestBudget()
    result = research_sources({'symbol': '1101534', 'missing_fields': ['prices', 'profile']}, {}, budget,
                              search=lambda *_: [{'url': url} for url in urls], fetch=fetch)
    assert [row['url'] for row in result['evidence']] == urls
    assert budget.used == 3


def test_profile_only_request_does_not_spend_budget_looking_for_a_price():
    budget = RequestBudget()
    result = research_sources({'symbol': '1101534', 'missing_fields': ['profile']}, {}, budget,
                              search=lambda *_: [{'url': f'https://source.example/{index}'} for index in range(4)],
                              fetch=lambda _: '1101534 TASE Company name: Cellcom')
    assert result['code'] == 'evidence_found' and budget.used == 2


def test_unique_host_sources_are_tried_before_duplicate_host_and_fourth_result_can_win():
    urls = ['https://same.example/first', 'https://same.example/second',
            'https://other.example/third', 'https://last.example/fourth']
    reads = []
    def fetch(url):
        reads.append(url)
        return ('1101534 TASE ILS agorot Close 2901 on 06/11/2026' if url == urls[3]
                else 'Another security 9999999')
    result = research_sources({'symbol': '1101534'}, {}, RequestBudget(),
                              search=lambda *_: [{'url': url} for url in urls + [urls[0]]], fetch=fetch)
    assert result['code'] == 'evidence_found'
    assert reads == [urls[0], urls[2], urls[3]]


def test_identity_without_price_or_profile_never_becomes_evidence():
    result = research_sources({'symbol': '1101534'}, {}, RequestBudget(),
                              search=lambda *_: [{'url': 'https://source.example/1101534'}],
                              fetch=lambda _: 'Public source identifies security1101534; no dated price has been established.')
    assert result['code'] == 'source_identity_unavailable' and not result['evidence']


def test_fallback_is_not_attempted_unless_budget_can_also_read_a_source():
    calls = []
    def search(*_):
        calls.append('search')
        return [{'url': f'https://shell.example/{index}'} for index in range(4)]
    def fetch(_):
        calls.append('fetch')
        return 'דף הבית'
    budget = RequestBudget(limit=3)
    result = research_sources({'symbol': '1101534'}, {}, budget, search=search, fetch=fetch)
    assert result['code'] == 'request_limit'
    assert calls == ['search', 'fetch', 'fetch']
    assert budget.used == 3
