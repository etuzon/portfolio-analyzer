import json
import socket

import httpx
import pytest

from app.security_research_tools import (
    ResearchFailure, ResearchSession, _Document, fetch_research_document, public_source_url,
)
from app.us_market_providers import ProviderFailure, RequestBudget


CANDIDATE = {"security_key": "one", "symbol": "EXAMPLE", "name": "Example Company"}


def resolver(host, port, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


def session(*, budget=None, fetch=None, search=None):
    return ResearchSession({}, budget or RequestBudget(), resolver=resolver,
                           search=search or (lambda query, settings: [{"url": "https://example.com/quote", "title": "Quote", "description": "snippet is not evidence"}]),
                           fetch=fetch or (lambda url, settings: {"url": url, "text": "EXAMPLE Last price 10 USD on 06/11/2026", "links": [{"url": "/history", "title": "History"}]}))


def test_search_read_follow_preserve_provenance_without_snippet_evidence():
    research = session()
    discovery = research.search(CANDIDATE)
    assert discovery["discovery_only"] is True
    assert research.evidence(CANDIDATE) == []
    assert "snippet" not in json.dumps(discovery)
    source_id = discovery["sources"][0]["source_id"]
    page = research.read(CANDIDATE, source_id)
    followed = research.follow(CANDIDATE, source_id, page["links"][0]["link_id"])
    assert page["requested_url"] == page["url"] == "https://example.com/quote"
    assert followed["url"] == "https://example.com/history"
    assert page["retrieved_at"]
    assert len(research.evidence(CANDIDATE)) == 2
    assert research.budget.used == 3


def test_shared_budget_counts_failures_and_refuses_sixth_network_operation():
    attempts = []

    def failing_fetch(url, settings):
        attempts.append(url)
        raise OSError("fixture error")

    research = session(fetch=failing_fetch)
    source_id = research.search(CANDIDATE)["sources"][0]["source_id"]
    for _ in range(4):
        with pytest.raises(ResearchFailure, match="could not be read"):
            research.read(CANDIDATE, source_id)
    with pytest.raises(ProviderFailure) as error:
        research.read(CANDIDATE, source_id)
    assert error.value.code == "request_limit"
    assert research.budget.used == 5
    assert len(attempts) == 4
    assert research.diagnostics["read_failures"] == 4


def test_security_and_request_scopes_reject_forged_source_and_link_ids():
    research = session()
    source_id = research.search(CANDIDATE)["sources"][0]["source_id"]
    for candidate, source in [({**CANDIDATE, "security_key": "two"}, source_id), (CANDIDATE, "https://example.com/")]:
        with pytest.raises(ResearchFailure):
            research.read(candidate, source)
    with pytest.raises(ResearchFailure):
        session().read(CANDIDATE, source_id)
    with pytest.raises(ResearchFailure):
        research.follow(CANDIDATE, source_id, "invented-link")
    assert research.budget.used == 1


@pytest.mark.parametrize("url", [
    "http://example.com/", "https://user:secret@example.com/", "https://localhost/",
    "https://10.0.0.1/", "https://127.0.0.1/", "https://[::1]/", "https://foo.internal/",
    "https://example.com:8443/", "https://example.com\\@127.0.0.1/", "file:///tmp/data",
])
def test_private_and_non_https_source_destinations_are_rejected(url):
    with pytest.raises(ResearchFailure):
        public_source_url(url, resolver=resolver)


def test_mixed_public_private_dns_and_private_reader_final_url_are_rejected():
    def mixed(host, port, **kwargs):
        return resolver(host, port) + [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    with pytest.raises(ResearchFailure):
        public_source_url("https://example.com/", resolver=mixed)
    research = session(fetch=lambda url, settings: {"url": "https://127.0.0.1/private", "text": "not public"})
    source_id = research.search(CANDIDATE)["sources"][0]["source_id"]
    with pytest.raises(ResearchFailure):
        research.read(CANDIDATE, source_id)
    assert research.evidence(CANDIDATE) == []
    assert research.budget.used == 2


def test_unrelated_search_queries_are_rejected_before_network():
    research = session()
    with pytest.raises(ResearchFailure):
        research.search(CANDIDATE, "unrelated private information")
    assert research.budget.used == 0


def test_direct_html_extracts_links_and_data_without_script_as_page_text():
    parser = _Document()
    parser.feed('<main>EXAMPLE Last 10 USD<a href="/history">History</a>'
                '<script type="application/ld+json">{"price":10}</script>'
                '<script>alert("hidden")</script></main>')
    assert parser.links == [{"url": "/history", "title": "History"}]
    assert parser.structured_data == [{"price": 10}]
    assert "hidden" not in " ".join(parser.parts)


def test_rendered_reader_uses_documented_json_and_one_credential_free_request(monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"code": 200, "data": {"url": "https://example.com/quote", "finalUrl": "https://example.com/final",
                              "content": "EXAMPLE Last price 10 USD", "links": {"History": "https://example.com/history"}}})

    client_class = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client_class(transport=httpx.MockTransport(handle), **kwargs))
    document = fetch_research_document("https://example.com/quote", {})
    assert document["url"] == "https://example.com/final"
    assert document["links"] == {"History": "https://example.com/history"}
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://r.jina.ai/https://example.com/quote"
    assert request.headers["x-respond-with"] == "markdown"
    assert request.headers["x-retain-images"] == "none"
    assert request.headers["x-with-generated-alt"] == "false"
    assert not any(key in request.headers for key in ("authorization", "cookie", "x-set-cookie", "x-instruction", "x-json-schema", "x-inject-page-script"))


def test_rendered_reader_does_not_retry_or_fallback_on_block(monkeypatch):
    requests = []
    client_class = httpx.Client

    def handle(request):
        requests.append(request)
        return httpx.Response(429, json={"code": 429})

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client_class(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(ResearchFailure):
        fetch_research_document("https://example.com/quote", {})
    assert len(requests) == 1
