from contextlib import contextmanager
from urllib.parse import quote

import httpx
import pytest

from app.price_agent import price_agent_settings
from app.security_search import SearchFailure, parse_duckduckgo_results, parse_yahoo_results, search_is_configured, search_web, selected_search_provider


def result_html(url="https://exchange.example/fund/5139324"):
    return '<html><a class="result__a" href="//duckduckgo.com/l/?uddg=' + quote(url, safe="") + '">Actual fund <b>result</b></a><div class="result__snippet">Price999 is only a snippet</div></html>'


def yahoo_result_html(url="https://exchange.example/security/EXAMPLE", *, title="Actual security result"):
    # Main organic structure retained from the actual public Yahoo response;
    # the result anchor encloses a breadcrumb and h3, unlike the DDG adapter.
    return ('<div class="dd algo algo-sr relsrch Sr"><div class="compTitle options-toggle">'
            '<a href="' + url + '"><div>Publisher breadcrumb</div><h3><span>' + title + '</span></h3></a></div>'
            '<div class="compText"><p>Price999 is only a snippet</p></div></div>')


def client_mock(monkeypatch, handler):
    client = httpx.Client
    calls = []
    def wrapped(request):
        calls.append(request)
        return handler(request)
    monkeypatch.setattr("app.security_search.httpx.Client", lambda **kwargs: client(transport=httpx.MockTransport(wrapped), **kwargs))
    return calls


def test_auto_selects_key_free_without_key_and_brave_with_key(monkeypatch):
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    settings = price_agent_settings({})
    assert settings["search_provider"] == "auto"
    assert selected_search_provider(settings) == "yahoo"
    assert search_is_configured(settings)
    assert selected_search_provider({"search_provider": "auto", "search_api_key": "synthetic"}) == "brave"
    assert not search_is_configured({"search_provider": "brave"})
    assert search_is_configured({"search_provider": "duckduckgo"})
    assert search_is_configured({"search_provider": "yahoo"})


def test_key_free_search_makes_one_fixed_request_and_decodes_real_result_link(monkeypatch):
    calls = client_mock(monkeypatch, lambda _: httpx.Response(200, text=result_html(), headers={"Content-Type": "text/html; charset=UTF-8"}))
    result = search_web("5139324 מחיר פדיון", {"search_provider": "duckduckgo"})
    assert len(calls) == 1
    assert str(calls[0].url).startswith("https://html.duckduckgo.com/html/?q=")
    assert calls[0].url.params["q"] == "5139324 מחיר פדיון"
    assert "X-Subscription-Token" not in calls[0].headers
    assert result == [{"url": "https://exchange.example/fund/5139324", "title": "Actual fund result", "description": ""}]
    assert "999" not in str(result)


def test_auto_key_free_yahoo_search_makes_one_fixed_credential_free_request(monkeypatch):
    calls = client_mock(monkeypatch, lambda _: httpx.Response(200, text=yahoo_result_html(), headers={"Content-Type": "text/html; charset=UTF-8"}))
    result = search_web("EXAMPLE bond", {"search_provider": "auto"})
    assert len(calls) == 1
    assert calls[0].url.host == "search.yahoo.com" and calls[0].url.path == "/search"
    assert dict(calls[0].url.params) == {"p": "EXAMPLE bond"}
    assert not {"authorization", "cookie", "x-subscription-token"} & set(calls[0].headers)
    assert result == [{"url": "https://exchange.example/security/EXAMPLE", "title": "Actual security result", "description": ""}]
    assert "999" not in str(result) and "breadcrumb" not in str(result)


def test_yahoo_unwraps_one_returned_redirect_without_an_extra_request(monkeypatch):
    target = "https://exchange.example/security/EXAMPLE?class=ordinary"
    wrapped = "https://r.search.yahoo.com/_ylt=discovery/RV=2/RU=" + quote(target, safe="") + "/RK=2/RS=opaque/"
    calls = client_mock(monkeypatch, lambda _: httpx.Response(200, text=yahoo_result_html(wrapped), headers={"Content-Type": "text/html"}))
    result = search_web("EXAMPLE", {"search_provider": "yahoo"})
    assert len(calls) == 1 and result[0]["url"] == target


def test_yahoo_navigation_breadcrumb_and_query_echo_cannot_become_results():
    page = ('<title>EXAMPLE bond Yahoo results</title><a href="https://nav.example">EXAMPLE</a>'
            '<h3><a href="https://nav.example">More EXAMPLE searches</a></h3>'
            '<div class="compText">EXAMPLE price999 is only a snippet</div>'
            '<div class="no-results">No results found</div>')
    assert parse_yahoo_results(page) == []


@pytest.mark.parametrize("url", ["http://example.com", "https://127.0.0.1/", "https://10.0.0.2/", "https://localhost/", "https://a.internal/", "https://example.com:8443/", "https://user:pass@example.com/", "https://search.yahoo.com/search?p=EXAMPLE", "https://user:secret@r.search.yahoo.com/RU=https%3A%2F%2Fexample.com/RK=2/"])
def test_yahoo_unsafe_and_internal_result_links_cannot_become_sources(url):
    assert parse_yahoo_results(yahoo_result_html(url)) == []


@pytest.mark.parametrize("status,body,expected", [
    (200, '<form id="challenge-form">challenge</form>', "search_blocked"),
    (200, '<form id="consent-form">consent</form>', "search_blocked"),
    (200, '<title>Unrecognized page</title>', "provider_unavailable"),
    (403, "blocked", "search_blocked"), (429, "rate limit", "search_blocked"),
    (503, "unavailable", "provider_unavailable"),
])
def test_yahoo_failures_do_not_retry_or_switch_provider(monkeypatch, status, body, expected):
    calls = client_mock(monkeypatch, lambda _: httpx.Response(status, text=body, headers={"Content-Type": "text/html"}))
    with pytest.raises(SearchFailure) as error:
        search_web("EXAMPLE", {"search_provider": "yahoo"})
    assert error.value.code == expected
    assert len(calls) == 1 and calls[0].url.host == "search.yahoo.com"


def test_yahoo_deduplicates_and_bounds_organic_results_from_the_same_response():
    markup = "".join(yahoo_result_html("https://exchange.example/security/" + str(index)) for index in range(15))
    assert len(parse_yahoo_results(markup + markup)) == 10


def test_explicit_brave_without_key_does_not_make_request(monkeypatch):
    calls = client_mock(monkeypatch, lambda _: pytest.fail("No key must mean no request"))
    with pytest.raises(SearchFailure) as exc:
        search_web("QA", {"search_provider": "brave"})
    assert exc.value.code == "search_not_configured" and not calls


@pytest.mark.parametrize("provider,status,body,code", [
    ("duckduckgo", 200, '<form id="challenge-form">challenge</form>', "search_blocked"),
    ("duckduckgo", 202, "challenge", "search_blocked"),
    ("duckduckgo", 403, "blocked", "search_blocked"),
    ("duckduckgo", 429, "rate limit", "search_blocked"),
    ("duckduckgo", 503, "unavailable", "provider_unavailable"),
    ("duckduckgo", 200, "unrecognized layout", "provider_unavailable"),
    ("brave", 401, "synthetic-private-credential", "search_not_configured"),
    ("brave", 403, "synthetic-private-credential", "search_not_configured"),
    ("brave", 429, "rate limit", "search_blocked"),
])
def test_provider_failures_are_single_counted_requests_with_safe_distinct_errors(monkeypatch, provider, status, body, code):
    calls = client_mock(monkeypatch, lambda _: httpx.Response(status, text=body, headers={"Content-Type": "text/html" if provider == "duckduckgo" else "application/json"}))
    with pytest.raises(SearchFailure) as exc:
        search_web("QA", {"search_provider": provider, "search_api_key": "synthetic-private-credential"})
    assert exc.value.code == code
    assert "synthetic-private-credential" not in str(exc.value)
    assert len(calls) == 1


def test_empty_results_are_not_provider_or_configuration_failure(monkeypatch):
    calls = client_mock(monkeypatch, lambda _: httpx.Response(200, text='<div class="no-results">No results found</div>', headers={"Content-Type": "text/html"}))
    assert search_web("no such result", {}) == []
    assert len(calls) == 1


def test_redirects_are_not_followed_or_fallback_retried(monkeypatch):
    calls = client_mock(monkeypatch, lambda _: httpx.Response(302, headers={"Location": "https://127.0.0.1/private"}))
    with pytest.raises(SearchFailure) as exc:
        search_web("QA", {})
    assert exc.value.code == "provider_unavailable" and len(calls) == 1


@pytest.mark.parametrize("url", ["http://example.com", "https://127.0.0.1/", "https://10.0.0.2/", "https://localhost/", "https://a.internal/", "https://example.com:8443/", "https://user:pass@example.com/", "https://duckduckgo.com/about"])
def test_unsafe_discovery_links_never_become_source_urls(url):
    assert parse_duckduckgo_results(result_html(url)) == []


def test_arbitrary_anchors_and_snippets_are_not_results():
    page = '<a href="https://exchange.example">navigation</a><div class="result__snippet">QA price100</div><div class="no-results">No results found</div>'
    assert parse_duckduckgo_results(page) == []


def test_brave_uses_same_discovery_contract_and_never_falls_back_on_bad_key(monkeypatch):
    calls = client_mock(monkeypatch, lambda _: httpx.Response(200, json={"web": {"results": [{"url": "https://exchange.example/quote", "title": "Public quote", "description": "Snippet"}]}}))
    result = search_web("QA", {"search_provider": "auto", "search_api_key": "synthetic"})
    assert result[0]["url"] == "https://exchange.example/quote"
    assert len(calls) == 1 and calls[0].url.host == "api.search.brave.com"
    assert calls[0].headers["X-Subscription-Token"] == "synthetic"
