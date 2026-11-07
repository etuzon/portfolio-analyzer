"""Independent offline acceptance checks derived from exact-listing research rules.

Synthetic HTML exercises the real public-source parser. No network, application
runtime, portfolio database, or model is used by these checks.
"""
from datetime import date
from urllib.parse import urlsplit

import pytest

from app.price_agent import PriceAgentError, fetch_public_source
from app.security_web_research import research_sources, validate_proposals
from app.us_market_providers import RequestBudget


DAY = date.today().isoformat()
URL = "https://public-evidence.example/1101534"
KEY = "1101534|TASE|ILS"
CANDIDATE = {"security_key": KEY, "symbol": "1101534", "stock_market": "TASE",
             "currency": "ILS", "quote_unit": "agorot", "asset_class": "EQUITY",
             "missing_fields": ["prices", "profile"]}
VALID = f"1101534 TASE ILS agorot Close 2901 on {DAY}"


def source_from_html(monkeypatch, markup):
    class Response:
        status = 200
        def getheader(self, name, default=""):
            return "text/html; charset=utf-8" if name == "Content-Type" else default
        def read(self, _limit):
            return markup.encode("utf-8")

    class Connection:
        def __init__(self, *_args, **_kwargs):
            pass
        def request(self, *_args, **_kwargs):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            pass

    monkeypatch.setattr("app.price_agent._public_address", lambda url: (urlsplit(url), "8.8.8.8"))
    monkeypatch.setattr("app.price_agent.http.client.HTTPSConnection", Connection)
    return fetch_public_source(URL)


def proposal(text, **changes):
    return {"security_key": KEY, "price_input": 2901, "price_date": DAY,
            "currency": "ILS", "quote_unit": "agorot", "price_basis": "close",
            "source_url": URL, "observed_at": None, "evidence_quote": text, **changes}


def accepted(text, **changes):
    source = {"url": URL, "text": text, "retrieved_at": DAY + "T00:00:00+00:00"}
    result = validate_proposals({"observations": [proposal(text, **changes)]},
                                {KEY: CANDIDATE}, {KEY: [source]})
    return result.get(KEY, {}).get("observations", [])


def test_raw_dated_single_listing_html_quote_can_support_a_fact(monkeypatch):
    text = source_from_html(monkeypatch, f"<main><p>{VALID}</p></main>")
    records = accepted(text)
    assert len(records) == 1
    assert records[0]["price_input"] == 2901  # Raw agorot, never converted by the model.
    assert records[0]["price_date"] == DAY
    assert records[0]["observed_at"] is None


@pytest.mark.parametrize("tag", ["div", "p", "tr", "li"])
def test_independent_html_records_cannot_lend_identity_to_another_security(monkeypatch, tag):
    markup = (f"<{tag}>1101534 TASE ILS agorot</{tag}>"
              f"<{tag}>1101535 Close 2901 on {DAY}</{tag}>")
    text = source_from_html(monkeypatch, markup)
    assert not accepted(text), "A different security's dated close must never fill 1101534"


def test_identity_bearing_javascript_shell_does_not_hide_next_readable_source():
    urls = [URL + "/shell", URL + "/quote"]
    reads = []
    def fetch(url):
        reads.append(url)
        return "1101534 Loading market data please enable JavaScript" if url == urls[0] else VALID
    budget = RequestBudget()
    result = research_sources(CANDIDATE, {"search_provider": "duckduckgo"}, budget,
        search=lambda *_: [{"url": url} for url in urls], fetch=fetch)
    assert reads == urls
    assert any(VALID in item["text"] for item in result["evidence"])
    assert budget.used == 3


@pytest.mark.parametrize("first_result_count", [1, 2, 3])
def test_secondary_discovery_can_recover_when_first_results_are_javascript_shells(first_result_count):
    calls = []
    first = [URL + "/shell-" + str(index) for index in range(first_result_count)]
    alternate = "https://other-public-evidence.example/1101534"
    def search(query, _key):
        calls.append(("search", query))
        return [{"url": url} for url in first] if len([c for c in calls if c[0] == "search"]) == 1 else [{"url": alternate}]
    def fetch(url):
        calls.append(("fetch", url))
        return VALID if url == alternate else "1101534 Loading market data please enable JavaScript"
    budget = RequestBudget()
    result = research_sources(CANDIDATE, {"search_provider": "duckduckgo"}, budget,
                              search=search, fetch=fetch)
    assert any(item["url"] == alternate and VALID in item["text"] for item in result["evidence"])
    queries = [value for kind, value in calls if kind == "search"]
    assert len(queries) == 2 and queries[0] != queries[1]
    assert budget.used == len(calls) <= 5


def test_failed_source_attempts_spend_shared_budget_and_cannot_reset_it():
    calls = []
    def search(*_):
        calls.append("search")
        return [{"url": URL + "/" + str(index)} for index in range(4)]
    def fetch(_url):
        calls.append("fetch")
        raise PriceAgentError("The public source page could not be read.")
    budget = RequestBudget(limit=2)
    result = research_sources(CANDIDATE, {"search_provider": "duckduckgo"}, budget,
                              search=search, fetch=fetch)
    assert not result["evidence"] and result["code"] == "request_limit"
    assert budget.used == len(calls) == 2
    repeated = research_sources(CANDIDATE, {"search_provider": "duckduckgo"}, budget,
                                search=search, fetch=fetch)
    assert not repeated["evidence"] and repeated["code"] == "request_limit"
    assert budget.used == len(calls) == 2


def test_search_snippets_never_become_fetched_fact_evidence():
    result = research_sources(CANDIDATE, {"search_provider": "duckduckgo"}, RequestBudget(),
        search=lambda *_: [{"url": URL, "description": VALID, "title": VALID}],
        fetch=lambda _: "1101534 Loading market data please enable JavaScript")
    assert all(VALID not in item["text"] for item in result["evidence"])
    assert not accepted("1101534 Loading market data please enable JavaScript")


@pytest.mark.parametrize("changes", [
    {"price_input": 29.01}, {"quote_unit": "currency"}, {"currency": "USD"},
    {"price_date": "1999-01-01"}, {"observed_at": DAY + "T12:00:00+00:00"},
])
def test_literal_raw_price_date_unit_and_timestamp_are_not_model_inferences(changes):
    assert not accepted(VALID, **changes)


@pytest.mark.parametrize("unit", ["אגורות", "באגורות", "(באגורות)"])
def test_hebrew_labelled_raw_quote_preserves_its_explicit_agorot_unit(unit):
    text = f"1101534 TASE שער אחרון {unit} 2901 נכון לתאריך {DAY}"
    records = accepted(text, price_basis="last")
    assert len(records) == 1
    assert records[0]["price_input"] == 2901 and records[0]["quote_unit"] == "agorot"


def test_ambiguous_numeric_source_date_stays_unavailable():
    from app.price_agent import _evidence_dates
    with pytest.raises(PriceAgentError, match="ambiguous"):
        _evidence_dates("1101534 TASE ILS agorot Close 2901 on 06/11/2026")


def test_wrong_explicit_identifier_inside_one_html_block_is_still_rejected(monkeypatch):
    text = source_from_html(monkeypatch,
        f"<p>1101534 TASE ILS agorot 1101535 Close 2901 on {DAY}</p>")
    assert not accepted(text)


def test_supported_named_month_dated_source_is_not_misclassified_as_a_shell():
    text = f"1101534 TASE ILS agorot Close 2901 on {date.today():%d %B %Y}"
    result = research_sources(CANDIDATE, {"search_provider": "duckduckgo"}, RequestBudget(),
        search=lambda *_: [{"url": URL}], fetch=lambda _: text)
    assert result["evidence"] and result["evidence"][0]["text"] == text
    assert accepted(text), "This is an existing supported dated-price format"


def test_supported_literal_profile_without_punctuation_remains_retrievable():
    candidate = {**CANDIDATE, "missing_fields": ["profile"]}
    text = "1101534 TASE Name Cellcom"
    result = research_sources(candidate, {"search_provider": "duckduckgo"}, RequestBudget(),
        search=lambda *_: [{"url": URL}], fetch=lambda _: text)
    assert result["evidence"] and result["evidence"][0]["text"] == text
    item = {"security_key": KEY, "field": "name", "value": "Cellcom",
            "source_url": URL, "evidence_quote": text}
    verified = validate_proposals({"profiles": [item]}, {KEY: candidate}, {KEY: result["evidence"]})
    assert verified[KEY]["profiles"][0]["value"] == "Cellcom"


def test_recorded_mixed_shell_blocked_redirect_results_leave_room_for_recovery():
    # Public result ordering and source outcomes from the bounded 07/11/2026
    # actual-helper preview. The successful alternate page remains synthetic:
    # this replay verifies scheduling, not current public-market availability.
    first = [
        "https://market.tase.co.il/he/market_data/security/1101534",
        "https://market.tase.co.il/he/market_data/security/01101534/otc",
        "https://il.investing.com/equities/cellcom-israel",
        "https://maya.tase.co.il/",
        "https://il.investing.com/equities/cellcom-israel-historical-data",
    ]
    alternate = "https://other-public-evidence.example/1101534"
    calls = []
    def search(query, _key):
        calls.append(("search", query))
        rows = first if sum(kind == "search" for kind, _ in calls) == 1 else [alternate]
        return [{"url": url} for url in rows]
    def fetch(url):
        calls.append(("fetch", url))
        if url == alternate:
            return VALID
        if url.startswith("https://market.tase.co.il/"):
            return "דף הבית - הבורסה לניירות ערך בתל אביב | אתר הבורסה"
        raise PriceAgentError("The source page is unavailable or redirects; select another returned source URL.")
    budget = RequestBudget()
    result = research_sources(CANDIDATE, {"search_provider": "duckduckgo"}, budget,
                              search=search, fetch=fetch)
    assert any(item["url"] == alternate and VALID in item["text"] for item in result["evidence"])
    assert sum(kind == "search" for kind, _ in calls) == 2
    assert budget.used == len(calls) <= 5
    # A second blocked URL from one host must not consume the recovery slot.
    investing = [value for kind, value in calls if kind == "fetch" and urlsplit(value).hostname == "il.investing.com"]
    assert len(investing) <= 1


def test_one_search_response_retains_later_exact_security_sources_and_reads_them(monkeypatch):
    import httpx
    from app.security_search import search_web
    urls = [
        "https://market.tase.co.il/he/market_data/security/1101534",
        "https://market.tase.co.il/he/market_data/security/01101534/otc",
        "https://il.investing.com/equities/cellcom-israel",
        "https://maya.tase.co.il/",
        "https://il.investing.com/equities/cellcom-israel-historical-data",
        "https://sixth-public-evidence.example/company/cellcom",
        "https://later-public-evidence.example/security/1101534",
        "https://eighth-public-evidence.example/security/1101534",
        "https://ninth-public-evidence.example/company/cellcom",
        "https://tenth-public-evidence.example/company/cellcom",
    ]
    markup = "".join(f'<a class="result__a" href="{url}">Public security result</a>' for url in urls)
    http_reads = []
    def handler(request):
        http_reads.append(request)
        return httpx.Response(200, text=markup, headers={"Content-Type": "text/html; charset=UTF-8"})
    original_client = httpx.Client
    monkeypatch.setattr("app.security_search.httpx.Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    discoveries, source_reads = [], []
    def search(query, _key):
        rows = search_web(query, {"search_provider": "duckduckgo"})
        discoveries.extend(row["url"] for row in rows)
        return rows
    def fetch(url):
        source_reads.append(url)
        if url == urls[6]:
            return VALID
        return "דף הבית - הבורסה לניירות ערך בתל אביב | אתר הבורסה"
    budget = RequestBudget()
    result = research_sources(CANDIDATE, {"search_provider": "duckduckgo"}, budget,
                              search=search, fetch=fetch)
    assert discoveries == urls, "One HTTP response must retain all ten bounded discovery alternatives"
    assert len(http_reads) == 1
    assert source_reads == [urls[0], urls[6]], "An unvisited exact-security host must outrank unrelated pages"
    assert result["evidence"][0]["url"] == urls[6]
    assert budget.used == len(http_reads) + len(source_reads) == 3
