"""Request-scoped public research tools, with no model or storage access.

The caller owns the REST/model budgets. This controller owns the shared eight
web-operation budget; a rendered-reader request is one application HTTP request,
not a claim about the reader provider's internal asset requests.
"""
from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, field
from html.parser import HTMLParser
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit
from uuid import uuid4

import httpx

from .price_agent import _PageText
from .security_search import search_web, selected_search_provider
from .us_market_providers import RequestBudget


class ResearchFailure(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class WebRequestBudget:
    """AI request budget; independent from ordinary provider refresh limits."""
    limit: int = 8
    timeout_seconds: float = 240
    used: int = 0
    _started: float = field(default_factory=time.monotonic, repr=False)

    def __post_init__(self):
        self.limit = min(8, max(1, int(self.limit)))
        self.timeout_seconds = min(240, max(1, float(self.timeout_seconds)))

    @property
    def remaining(self):
        return max(0, self.limit - self.used)

    @property
    def remaining_seconds(self):
        return max(0, self._started + self.timeout_seconds - time.monotonic())

    def consume(self):
        if not self.remaining:
            raise ResearchFailure("request_limit", "The research web request limit was reached.")
        if not self.remaining_seconds:
            raise ResearchFailure("timeout", "The research request time limit was reached.")
        self.used += 1


def public_source_url(value: Any, *, resolve: bool = True, resolver: Callable | None = None) -> str:
    """Check every destination, including reader-reported final URLs."""
    if not isinstance(value, str) or not 1 <= len(value) <= 2000 or any(ord(c) < 32 for c in value):
        raise ResearchFailure("invalid_source", "The source URL is invalid.")
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if (parsed.scheme != "https" or not host or parsed.username or parsed.password
                or parsed.port not in {None, 443} or "\\" in value
                or host == "localhost" or host.endswith((".localhost", ".local", ".internal"))):
            raise ValueError()
        try:
            if not ipaddress.ip_address(host).is_global:
                raise ValueError()
        except ValueError:
            # A numeric private address must not fall through as a hostname.
            if re.fullmatch(r"[0-9.]+", host) or ":" in host:
                raise ValueError()
        if resolve:
            records = (resolver or socket.getaddrinfo)(host, 443, type=socket.SOCK_STREAM)
            addresses = [record[4][0] for record in records]
            if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
                raise ValueError()
        return urlunsplit(("https", parsed.netloc, parsed.path or "/", parsed.query, ""))
    except (ValueError, OSError, TypeError, IndexError):
        raise ResearchFailure("invalid_source", "Only public HTTPS source URLs are allowed.") from None


class _Document(_PageText):
    def __init__(self):
        super().__init__()
        self.links: list[dict[str, str]] = []
        self.structured_data: list[Any] = []
        self._script: list[str] | None = None
        self._script_size = 0
        self._anchor: dict[str, str] | None = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and isinstance(values.get("href"), str):
            self._anchor = {"url": values["href"], "title": ""}
        if tag == "script" and (values.get("type") == "application/ld+json" or values.get("id") == "__NEXT_DATA__"):
            self._script, self._script_size = [], 0
        super().handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self._anchor is not None and not self.hidden:
            self._anchor["title"] = (self._anchor["title"] + data)[:300]
        if self._script is not None and self._script_size <= 16_000:
            self._script.append(data)
            self._script_size += len(data)
        super().handle_data(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor is not None:
            if len(self.links) < 100:
                self.links.append(self._anchor)
            self._anchor = None
        if tag == "script" and self._script is not None:
            if self._script_size <= 16_000 and len(self.structured_data) < 10:
                try:
                    self.structured_data.append(json.loads("".join(self._script)))
                except ValueError:
                    pass
            self._script = None
        super().handle_endtag(tag)


def _direct_document(url: str, *, compatible: bool = False) -> dict[str, Any]:
    # Pin checked DNS just as the existing public evidence fetcher does.
    from .price_agent import _public_address
    parsed, address = _public_address(url)
    connection = http.client.HTTPSConnection(parsed.hostname, 443, timeout=20, context=ssl.create_default_context())
    connection._create_connection = lambda *_args, **_kwargs: socket.create_connection((address, 443), timeout=20)
    try:
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        headers = {"User-Agent": "PortfolioAnalyzerPriceResearch/1.0", "Accept": "text/html,text/plain,application/json"}
        if compatible:
            headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
                            "Accept-Language": "en-US,en;q=0.9"})
        connection.request("GET", target, headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            raise ResearchFailure("source_read_failed", "The source is unavailable or redirects; select another discovered source.")
        content_type = response.getheader("Content-Type", "").lower()
        if not any(kind in content_type for kind in ("text/html", "text/plain", "application/json")):
            raise ResearchFailure("source_read_failed", "The source is not a supported text page.")
        limit = 2_000_000 if compatible else 1_000_000
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ResearchFailure("source_read_failed", "The source exceeds the evidence size limit.")
        text = raw.decode("utf-8", errors="replace")
        document = {"url": url, "text": text, "links": [], "structured_data": []}
        if "html" in content_type:
            parser = _Document()
            parser.feed(text)
            text = "\n".join(part.strip() for part in parser.parts if part.strip() and part.strip() != "|") if compatible else " ".join(parser.parts)
            document.update(text=text, links=parser.links, structured_data=parser.structured_data)
        elif "application/json" in content_type and len(text) <= 16_000:
            try:
                document["structured_data"] = [json.loads(text)]
            except ValueError:
                pass
        return document
    finally:
        connection.close()


def fetch_research_document(url: str, settings: dict[str, Any]) -> dict[str, Any]:
    """One direct or key-free rendered-reader request, never a fallback loop."""
    # ResearchSession performs the DNS check before this adapter. Repeat syntax
    # checks here so even a direct adapter caller cannot pass a local URL.
    url = public_source_url(url, resolve=False)
    reader = str(settings.get("reader") or "auto").lower()
    parsed = urlsplit(url)
    # Select one compatible transport before the read; never hide retries or
    # fallback requests inside one budget operation. This is HTTP, not JS.
    if reader == "compatible" or reader == "auto" and parsed.hostname in {"www.google.com", "google.com"} and re.fullmatch(r"/finance/(?:beta/)?quote/[^/]+", parsed.path):
        return {**_direct_document(url, compatible=True), "reader": "compatible"}
    if reader == "direct":
        return {**_direct_document(url), "reader": "direct"}
    if reader not in {"auto", "jina"}:
        raise ResearchFailure("reader_not_configured", "Choose auto, jina, direct or compatible for the source reader.")
    headers = {"Accept": "application/json", "X-Respond-With": "markdown", "X-With-Links-Summary": "true",
               "X-Retain-Images": "none", "X-With-Generated-Alt": "false", "X-Timeout": "20",
               "X-No-Cache": "true", "DNT": "1"}
    # Only the public URL is sent. No application identity, credentials, cookies,
    # arbitrary headers, instructions, custom script or model feature is exposed.
    with httpx.Client(timeout=25, follow_redirects=False, trust_env=False) as client:
        with client.stream("GET", "https://r.jina.ai/" + url, headers=headers) as response:
            if response.status_code != 200 or "application/json" not in response.headers.get("content-type", "").lower():
                raise ResearchFailure("source_read_failed", "The rendered source reader is unavailable or blocked.")
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > 1_000_000:
                    raise ResearchFailure("source_read_failed", "The rendered source exceeds the evidence size limit.")
    payload = json.loads(raw)
    data = payload.get("data") if isinstance(payload, dict) and payload.get("code") == 200 else None
    if not isinstance(data, dict) or not isinstance(data.get("url"), str) or not isinstance(data.get("content"), str):
        raise ResearchFailure("source_read_failed", "The rendered source reader returned an invalid document.")
    if data.get("httpStatus", 200) != 200 or public_source_url(data["url"], resolve=False) != url:
        raise ResearchFailure("source_read_failed", "The rendered source reader returned a different or unavailable source.")
    return {"url": data.get("finalUrl") or data["url"], "text": data["content"], "title": data.get("title", ""),
            "links": data.get("links") or {}, "structured_data": [], "reader": "jina"}


class ResearchSession:
    def __init__(self, settings: dict[str, Any], budget: RequestBudget, *, search: Callable | None = None,
                 fetch: Callable | None = None, resolver: Callable | None = None):
        self.settings, self.budget = dict(settings), budget
        self._search, self._fetch, self._resolver = search or search_web, fetch or fetch_research_document, resolver
        self._sources: dict[str, dict[str, Any]] = {}
        self._evidence: dict[str, list[dict[str, Any]]] = {}
        self.diagnostics = {"search_requests": 0, "source_requests": 0, "read_failures": 0}

    @staticmethod
    def _key(candidate):
        key = candidate.get("security_key") if isinstance(candidate, dict) else None
        if not isinstance(key, str) or not key:
            raise ResearchFailure("invalid_request", "The research security is unavailable.")
        return key

    def _add(self, key, url, title=""):
        url = public_source_url(url, resolve=False)
        for source_id, source in self._sources.items():
            if source["key"] == key and source["url"] == url:
                return source_id
        if len(self._sources) >= 500:
            raise ResearchFailure("source_limit", "The discovered-source limit was reached.")
        source_id = "source-" + uuid4().hex
        self._sources[source_id] = {"key": key, "url": url, "title": str(title)[:300]}
        return source_id

    def _source(self, candidate, source_id):
        key = self._key(candidate)
        source = self._sources.get(source_id) if isinstance(source_id, str) else None
        if not source or source["key"] != key:
            raise ResearchFailure("invalid_source", "Select a source discovered for this security in this request.")
        return key, source

    def discover(self, candidate: dict[str, Any]) -> list[dict[str, str]]:
        """Known provider namespace hints are discovery, never verified facts."""
        key = self._key(candidate)
        market = re.sub(r"\s+", "", str(candidate.get("stock_market") or "").upper())
        symbol = str(candidate.get("symbol") or "").strip()
        asset = str(candidate.get("asset_class") or "").upper()
        if market == "PRIVATE":
            return []
        if asset == "BOND" or str(candidate.get("asset_sub_class") or "").upper() == "BOND":
            from .security_identifiers import valid_cusip, valid_isin
            cusips = set()
            for field in ("symbol", "secondary_symbol", "cusip", "isin"):
                identifier = str(candidate.get(field) or "").strip().upper()
                if valid_cusip(identifier):
                    cusips.add(identifier)
                elif identifier.startswith("US") and valid_isin(identifier) and valid_cusip(identifier[2:11]):
                    cusips.add(identifier[2:11])
            # Maintained issuer-document catalog, analogous to the official
            # TASE namespace below. This offering circular lists many stripped
            # components; prefix membership never asserts exact coverage.
            if len(cusips) != 1:
                return []
            cusip = next(iter(cusips))
            hints = []
            if cusip.startswith("88059E"):
                url = "https://s205.q4cdn.com/318912997/files/doc_downloads/irw/tva_bonds/2000-g.pdf"
                title = "TVA 2000 Series G issuer offering document; component identifiers"
                source_id = self._add(key, url, title)
                hints.append({"source_id": source_id, "url": url, "title": title, "discovery_only": True})
            # Public publishes bond pages in an exact-CUSIP namespace. A hint
            # says nothing about this page's existence or evidence quality;
            # only an actual read and exact primary header can supply a name.
            location = re.sub(r"[\W_]+", "", str(candidate.get("location") or "").casefold())
            us_scope = (location in {"us", "usa", "unitedstates", "unitedstatesofamerica"}
                        or market in {"BOND", "MANUAL", "US", "USA", "NYSE", "NASDAQ", "FINRA", "TREASURY"}
                        and str(candidate.get("currency") or "").upper() == "USD")
            if us_scope and cusip.isalnum():
                url = "https://public.com/stocks/" + cusip.lower() + "-bond"
                title = "Public exact-CUSIP bond page; unverified discovery lead"
                source_id = self._add(key, url, title)
                hints.append({"source_id": source_id, "url": url, "title": title, "discovery_only": True})
            return hints
        if market not in {"TASE", "TLV", "TELAVIV"} or asset not in {"EQUITY", "STOCK", "SHARE", "RSU"} or not re.fullmatch(r"[0-9]{5,8}", symbol) or int(symbol) <= 0:
            return []
        url = "https://market.tase.co.il/he/market_data/security/" + str(int(symbol)) + "/major_data"
        source_id = self._add(key, url, "Official TASE security page")
        hints = [{"source_id": source_id, "url": url, "title": "Official TASE security page", "discovery_only": True}]
        # Field-specific alternatives are leads only. They still spend a read
        # and pass the same exact-identity validation as any discovered source.
        for needed, url, title in (
            (candidate.get("needs_industry"), "https://www.globes.co.il/portal/instrument.aspx?quote=TASE:" + str(int(symbol)), "Globes primary security industry"),
            (candidate.get("needs_name"), "https://finance.themarker.com/stock/" + str(int(symbol)), "TheMarker primary security name"),
        ):
            if needed and "profile" in candidate.get("missing_fields", []):
                hints.insert(0, {"source_id": self._add(key, url, title), "url": url, "title": title, "discovery_only": True})
        ticker = str(candidate.get("secondary_symbol") or "").strip().upper()
        if ("profile" in candidate.get("missing_fields", []) and (candidate.get("needs_name") or candidate.get("needs_industry"))
                and re.fullmatch(r"[A-Z][A-Z0-9.-]{0,29}", ticker)):
            url = "https://www.google.com/finance/beta/quote/" + ticker + ":TLV?hl=en"
            title = "Google Finance exact mapped ticker; name and industry"
            hints.insert(0, {"source_id": self._add(key, url, title), "url": url, "title": title, "discovery_only": True})
        return hints

    def search(self, candidate: dict[str, Any], query: str = "", *, provider: str = "auto") -> dict[str, Any]:
        key = self._key(candidate)
        identity = [str(candidate.get(field) or "").strip() for field in ("symbol", "secondary_symbol", "name", "stock_market")]
        query = query or " ".join(value for value in identity if value) + " price date currency company industry"
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 500:
            raise ResearchFailure("invalid_request", "A research query must contain 1 to 500 characters.")
        identifiers = identity[:3]
        from .security_identifiers import valid_cusip
        # Issuer offering tables commonly print the six-character issuer and
        # three-character issue/check portion separately. That exact formatted
        # identifier is the same discovery identity, not a broader query.
        formatted_cusip = any(valid_cusip(value.upper()) and re.search(
            r"(?<!\w)[\"']?" + re.escape(value[:6]) + r"[\"']?\s+[\"']?" + re.escape(value[6:]) + r"[\"']?(?!\w)", query, re.I)
            for value in identifiers)
        if not any(value and value.casefold() in query.casefold() for value in identifiers) and not formatted_cusip:
            raise ResearchFailure("invalid_request", "Keep the security identifier or name in the search query.")
        if provider not in {"auto", "brave", "duckduckgo", "yahoo"}:
            raise ResearchFailure("invalid_request", "Choose an allowed search provider.")
        settings = self.settings if provider == "auto" else {**self.settings, "search_provider": provider}
        self.last_search_provider = selected_search_provider(settings)
        self.budget.consume()
        self.diagnostics["search_requests"] += 1
        rows = self._search(query, settings)
        if not isinstance(rows, list):
            raise ResearchFailure("search_failed", "The search provider returned invalid results.")
        sources = []
        for row in rows[:10]:
            if not isinstance(row, dict):
                continue
            try:
                source_id = self._add(key, row.get("url"), row.get("title", ""))
            except ResearchFailure:
                continue
            source = self._sources[source_id]
            sources.append({"source_id": source_id, "url": source["url"], "title": source["title"]})
        return {"sources": sources, "discovery_only": True, "search_provider": self.last_search_provider, "diagnostics": dict(self.diagnostics)}

    def read(self, candidate: dict[str, Any], source_id: str, *, reader: str | None = None) -> dict[str, Any]:
        if reader is not None and reader not in {"auto", "jina", "direct", "compatible"}:
            raise ResearchFailure("invalid_request", "Choose an allowed page reader.")
        key, source = self._source(candidate, source_id)
        self.budget.consume()
        self.diagnostics["source_requests"] += 1
        try:
            url = public_source_url(source["url"], resolver=self._resolver)
            document = self._fetch(url, self.settings if reader is None else {**self.settings, "reader": reader})
            if not isinstance(document, dict) or not isinstance(document.get("text"), str) or not document["text"].strip():
                raise ResearchFailure("source_read_failed", "The source contains no readable evidence.")
            if re.search(r"\b(?:ERR_BLOCKED_BY_CLIENT|ERR_BLOCKED_BY_RESPONSE)\b", document["text"]):
                raise ResearchFailure("source_read_failed", "The source reader returned a blocked page.")
            actual = public_source_url(document.get("url") or url, resolver=self._resolver)
            links = []
            raw_links = document.get("links") or []
            if isinstance(raw_links, dict):
                raw_links = [{"title": title, "url": target} for title, target in raw_links.items()]
            if not isinstance(raw_links, list):
                raise ResearchFailure("source_read_failed", "The source returned invalid links.")
            for row in raw_links[:100]:
                if isinstance(row, str):
                    row = {"url": row, "title": ""}
                if not isinstance(row, dict) or not isinstance(row.get("url"), str):
                    continue
                try:
                    target = urljoin(actual, row["url"])
                    linked_source = self._add(key, target, row.get("title", ""))
                except (ResearchFailure, ValueError):
                    continue
                link_id = "link-" + uuid4().hex
                source.setdefault("links", {})[link_id] = linked_source
                links.append({"link_id": link_id, "url": self._sources[linked_source]["url"], "title": str(row.get("title") or "")[:300]})
            structured = document.get("structured_data") or []
            if not isinstance(structured, list) or len(json.dumps(structured)) > 16_000:
                structured = []
            evidence = {"source_id": source_id, "url": actual, "requested_url": url,
                        "text": "\n".join(" ".join(line.split()) for line in document["text"].splitlines())[:40_000], "title": str(document.get("title") or source["title"])[:300],
                        "retrieved_at": datetime.now(timezone.utc).isoformat(), "links": links, "structured_data": structured,
                        "locale": str(document.get("locale") or self.settings.get("locale") or "")[:20],
                        "reader": str(document.get("reader") or self.settings.get("reader") or "auto")[:20]}
            self._evidence.setdefault(key, []).append(evidence)
            return evidence
        except (ValueError, OSError, httpx.HTTPError, http.client.HTTPException) as exc:
            self.diagnostics["read_failures"] += 1
            if isinstance(exc, ResearchFailure):
                raise
            raise ResearchFailure("source_read_failed", "The public source could not be read.") from None

    def follow(self, candidate: dict[str, Any], source_id: str, link_id: str, *, reader: str | None = None) -> dict[str, Any]:
        _, source = self._source(candidate, source_id)
        linked_source = source.get("links", {}).get(link_id) if isinstance(link_id, str) else None
        if not linked_source:
            raise ResearchFailure("invalid_source", "Select a link returned by the source in this request.")
        return self.read(candidate, linked_source, reader=reader)

    def evidence(self, candidate: dict[str, Any]) -> list[dict[str, Any]]:
        return list(self._evidence.get(self._key(candidate), []))
