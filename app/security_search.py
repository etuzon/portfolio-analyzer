"""Single-request public search adapters; returned links are discovery, not facts.

Each invocation makes exactly one HTTP request. Provider selection never retries
or switches provider after a failure, so the calling controller owns its budget.
"""
from __future__ import annotations

from html.parser import HTMLParser
import ipaddress
import json
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

import httpx


class SearchFailure(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def selected_search_provider(settings: dict[str, Any]) -> str:
    provider = str(settings.get("search_provider") or "auto").lower()
    if provider not in {"auto", "brave", "duckduckgo", "yahoo"}:
        raise SearchFailure("search_not_configured", "Choose auto, brave, yahoo or duckduckgo for the search provider.")
    if provider == "auto":
        return "brave" if settings.get("search_api_key") else "yahoo"
    return provider


def search_is_configured(settings: dict[str, Any]) -> bool:
    try:
        provider = selected_search_provider(settings)
    except SearchFailure:
        return False
    return provider != "brave" or bool(settings.get("search_api_key"))


def _source_url(value: str) -> str | None:
    """Filter URL syntax here; the source fetcher separately pins public DNS."""
    if not isinstance(value, str) or not 1 <= len(value) <= 2000:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in {None, 443}:
            return None
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "duckduckgo.com", "html.duckduckgo.com", "lite.duckduckgo.com", "search.yahoo.com", "r.search.yahoo.com"} or host.endswith((".localhost", ".local", ".internal", ".duckduckgo.com")):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
    except (ValueError, TypeError):
        return None


class _DuckDuckGoResults(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self.result_anchors = 0
        self._url: str | None = None
        self._title: list[str] = []

    def handle_starttag(self, tag: str, attrs: Any):
        values = dict(attrs)
        if tag != "a" or "result__a" not in str(values.get("class") or "").split():
            return
        self.result_anchors += 1
        self._url = None
        value = str(values.get("href") or "")
        try:
            parsed = urlsplit(urljoin("https://html.duckduckgo.com/html/", value))
        except ValueError:
            return
        if parsed.hostname in {"duckduckgo.com", "html.duckduckgo.com"} and parsed.path == "/l/":
            targets = parse_qs(parsed.query).get("uddg") or []
            value = targets[0] if len(targets) == 1 else ""
        elif parsed.scheme == "https":
            value = urlunsplit(parsed)
        self._url = _source_url(value)
        self._title = []

    def handle_data(self, data: str):
        if self._url:
            self._title.append(data)

    def handle_endtag(self, tag: str):
        if tag == "a" and self._url:
            self.results.append({"url": self._url, "title": " ".join(" ".join(self._title).split())[:300], "description": ""})
            self._url = None
            self._title = []


def parse_duckduckgo_results(page: str) -> list[dict[str, str]]:
    lowered = page.lower()
    if any(marker in lowered for marker in ("anomaly.js", "challenge-form", "anomaly-modal", "bots use duckduckgo", "g-recaptcha", "hcaptcha")):
        raise SearchFailure("search_blocked", "The public search service presented a challenge. Try later or configure another search provider.")
    parser = _DuckDuckGoResults()
    try:
        parser.feed(page)
    except (ValueError, TypeError):
        raise SearchFailure("provider_unavailable", "The public search response could not be read.") from None
    # Reading more links from the same response spends no extra HTTP attempts.
    # Early results often repeat one exchange's JavaScript-only pages; keep
    # enough alternatives for the controller's bounded source selection.
    unique = list({entry["url"]: entry for entry in parser.results}.values())[:10]
    if unique or parser.result_anchors or any(marker in lowered for marker in ("no-results", "no results found", "no more results")):
        return unique
    raise SearchFailure("provider_unavailable", "The public search response contained no recognizable results.")


class _YahooResults(HTMLParser):
    """Organic result headings only; navigation and query echoes are not leads."""
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self.result_anchors = 0
        self._stack: list[tuple[str, set[str]]] = []
        self._url: str | None = None
        self._title: list[str] = []

    def handle_starttag(self, tag: str, attrs: Any):
        values = dict(attrs)
        if tag == "a":
            self._url, self._title = None, []
            if (any("algo" in classes for _tag, classes in self._stack)
                    and any("compTitle" in classes or _tag == "h3" for _tag, classes in self._stack)):
                self.result_anchors += 1
                value = str(values.get("href") or "")
                try:
                    parsed = urlsplit(urljoin("https://search.yahoo.com/", value))
                    if (parsed.scheme == "https" and parsed.hostname == "r.search.yahoo.com"
                            and not parsed.username and not parsed.password and parsed.port in {None, 443}):
                        targets = re.findall(r"/RU=([^/]+)(?=/|$)", parsed.path)
                        value = unquote(targets[0]) if len(targets) == 1 else ""
                    self._url = _source_url(value)
                except ValueError:
                    pass
        if tag not in self._VOID:
            self._stack.append((tag, set(str(values.get("class") or "").split())))

    def handle_startendtag(self, tag: str, attrs: Any):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str):
        if self._url and any(tag == "h3" for tag, _classes in self._stack):
            self._title.append(data)

    def handle_endtag(self, tag: str):
        if tag == "a" and self._url:
            title = " ".join(" ".join(self._title).split())[:300]
            if title:
                self.results.append({"url": self._url, "title": title, "description": ""})
            self._url, self._title = None, []
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                break


def parse_yahoo_results(page: str) -> list[dict[str, str]]:
    lowered = page.lower()
    if any(marker in lowered for marker in ("captcha", "challenge-form", "unusual traffic", "consent-form")):
        raise SearchFailure("search_blocked", "The public search service presented a challenge or consent page. Try later or choose another search provider.")
    parser = _YahooResults()
    try:
        parser.feed(page)
    except (ValueError, TypeError):
        raise SearchFailure("provider_unavailable", "The public search response could not be read.") from None
    unique = list({entry["url"]: entry for entry in parser.results}.values())[:10]
    if unique or parser.result_anchors or any(marker in lowered for marker in ("no results found", "we did not find results for", "no-results")):
        return unique
    raise SearchFailure("provider_unavailable", "The public search response contained no recognizable results.")


def _read_response(response: httpx.Response, *, html: bool) -> bytes:
    if not html and response.status_code in {401, 403}:
        raise SearchFailure("search_not_configured", "Brave rejected the configured search credentials or account access. Check its API key or choose automatic key-free research.")
    if response.status_code in {202, 403, 429}:
        raise SearchFailure("search_blocked", "The search service blocked or rate-limited this request. Try later or configure another provider.")
    if response.status_code != 200:
        raise SearchFailure("provider_unavailable", "The search service is temporarily unavailable.")
    expected = "text/html" if html else "application/json"
    if expected not in response.headers.get("content-type", "").lower():
        raise SearchFailure("provider_unavailable", "The search service returned an unsupported response.")
    raw = bytearray()
    for chunk in response.iter_bytes():
        raw.extend(chunk)
        if len(raw) > 1_000_000:
            raise SearchFailure("provider_unavailable", "The search response exceeded its size limit.")
    return bytes(raw)


def search_web(query: str, settings: dict[str, Any]) -> list[dict[str, str]]:
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 500:
        raise SearchFailure("invalid_request", "A search query must contain 1 to 500 characters.")
    provider = selected_search_provider(settings)
    api_key = str(settings.get("search_api_key") or "")
    if provider == "brave" and not api_key:
        raise SearchFailure("search_not_configured", "Brave search requires a configured API key; choose automatic, Yahoo or DuckDuckGo search to use key-free research.")
    try:
        with httpx.Client(timeout=12, follow_redirects=False, trust_env=False) as client:
            if provider == "yahoo":
                with client.stream("GET", "https://search.yahoo.com/search", params={"p": query}, headers={"User-Agent": "PortfolioAnalyzerPriceResearch/1.0", "Accept": "text/html"}) as response:
                    raw = _read_response(response, html=True)
                return parse_yahoo_results(raw.decode("utf-8", errors="replace"))
            if provider == "duckduckgo":
                with client.stream("GET", "https://html.duckduckgo.com/html/", params={"q": query}, headers={"User-Agent": "PortfolioAnalyzerPriceResearch/1.0", "Accept": "text/html"}) as response:
                    raw = _read_response(response, html=True)
                return parse_duckduckgo_results(raw.decode("utf-8", errors="replace"))
            with client.stream("GET", "https://api.search.brave.com/res/v1/web/search", params={"q": query, "count": 10}, headers={"X-Subscription-Token": api_key, "Accept": "application/json"}) as response:
                raw = _read_response(response, html=False)
            result = json.loads(raw)
            if not isinstance(result, dict) or not isinstance(result.get("web"), dict) or not isinstance(result["web"].get("results"), list):
                raise SearchFailure("provider_unavailable", "The search service returned an invalid result list.")
            output = []
            for row in result["web"]["results"][:10]:
                if isinstance(row, dict) and (url := _source_url(row.get("url"))):
                    output.append({"url": url, "title": str(row.get("title") or "")[:300], "description": str(row.get("description") or "")[:1500]})
            return output
    except (httpx.HTTPError, ValueError) as exc:
        if isinstance(exc, SearchFailure):
            raise
        raise SearchFailure("provider_unavailable", "The public search service is temporarily unavailable.") from None
