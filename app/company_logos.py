from __future__ import annotations

import ipaddress
import socket
import time
from collections.abc import Callable
from html.parser import HTMLParser
from threading import Lock, RLock
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from .providers import MarketDataHub


MAX_LOGO_BYTES = 256 * 1024
MAX_ICON_PAGE_BYTES = 512 * 1024
ERROR_RETRY_SECONDS = 24 * 60 * 60
MAX_REDIRECTS = 3


class UnsafeLogoUrl(ValueError):
    pass


class CompanyLogoService:
    def __init__(self, market_hub: MarketDataHub, *, clock: Callable[[], float] = time.time):
        self.hub = market_hub
        self.cache = market_hub.cache
        self.clock = clock
        self._locks_guard = RLock()
        self._locks: dict[tuple[str, str], Lock] = {}

    def get_or_resolve(self, symbol: str, *, secondary_symbol: str = "", stock_market: str = "") -> dict[str, Any]:
        symbol = str(symbol or "").upper()
        stock_market = str(stock_market or "").upper()
        cached = self.cache.get_company_logo(symbol, stock_market)
        if self._is_reusable(cached):
            return cached

        lock = self._lock_for(symbol, stock_market)
        with lock:
            cached = self.cache.get_company_logo(symbol, stock_market)
            if self._is_reusable(cached):
                return cached
            return self._resolve(symbol, secondary_symbol=secondary_symbol, stock_market=stock_market)

    def _is_reusable(self, record: dict[str, Any] | None) -> bool:
        if not record:
            return False
        if record["status"] in {"ready", "missing"}:
            return True
        return self.clock() - float(record["checked_at"]) < ERROR_RETRY_SECONDS

    def _lock_for(self, symbol: str, stock_market: str) -> Lock:
        key = (symbol, stock_market)
        with self._locks_guard:
            return self._locks.setdefault(key, Lock())

    def _resolve(self, symbol: str, *, secondary_symbol: str, stock_market: str) -> dict[str, Any]:
        profile = self.hub.cached_profile(symbol, secondary_symbol=secondary_symbol, stock_market=stock_market)
        status: dict[str, str] = {}
        if not _has_logo_source(profile):
            try:
                profile, status = self.hub.profile(symbol, secondary_symbol=secondary_symbol, stock_market=stock_market)
            except Exception:
                return self._save(symbol, stock_market, "error")

        if not _has_logo_source(profile):
            transient = any(value.startswith("error:") for value in status.values())
            return self._save(symbol, stock_market, "error" if transient else "missing")

        transient_failure = False
        candidates = _direct_logo_urls(profile)
        website = _normalized_website(profile)
        if website:
            try:
                candidates.extend(_discover_icon_urls(website))
            except (httpx.HTTPError, OSError):
                transient_failure = True
            except UnsafeLogoUrl:
                pass
            candidates.extend(_fallback_icon_urls(website))
        candidates = list(dict.fromkeys(candidates))
        for url in candidates:
            try:
                downloaded = _download_logo(url)
            except (httpx.HTTPError, OSError):
                transient_failure = True
                continue
            except UnsafeLogoUrl:
                continue
            if not downloaded:
                continue
            image, mime_type, final_url = downloaded
            return self._save(
                symbol,
                stock_market,
                "ready",
                image=image,
                mime_type=mime_type,
                source_url=_safe_source_url(final_url),
            )
        return self._save(symbol, stock_market, "error" if transient_failure else "missing")

    def _save(
        self,
        symbol: str,
        stock_market: str,
        status: str,
        *,
        image: bytes | None = None,
        mime_type: str = "",
        source_url: str = "",
    ) -> dict[str, Any]:
        self.cache.set_company_logo(
            symbol,
            stock_market,
            status=status,
            image=image,
            mime_type=mime_type,
            source_url=source_url,
            checked_at=self.clock(),
        )
        return self.cache.get_company_logo(symbol, stock_market) or {"status": status}


def _has_logo_source(profile: dict[str, Any]) -> bool:
    return bool(str(profile.get("logo_url") or "").strip() or str(profile.get("website") or "").strip())


def _direct_logo_urls(profile: dict[str, Any]) -> list[str]:
    logo_url = str(profile.get("logo_url") or "").strip()
    return [logo_url] if logo_url else []


def _normalized_website(profile: dict[str, Any]) -> str:
    website = str(profile.get("website") or "").strip()
    if not website:
        return ""
    if "://" not in website:
        website = f"https://{website}"
    parsed = urlsplit(website)
    if parsed.scheme.lower() == "http":
        website = urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))
    return website


def _fallback_icon_urls(website: str) -> list[str]:
    parsed = urlsplit(website)
    origin = urlunsplit((parsed.scheme, parsed.netloc, "/", "", ""))
    return [urljoin(origin, path) for path in ("favicon.ico", "apple-touch-icon.png", "favicon.png")]


class _IconLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "link":
            return
        values = {str(key).casefold(): str(value or "") for key, value in attrs}
        rel = {part.casefold() for part in values.get("rel", "").split()}
        href = values.get("href", "").strip()
        if "icon" in rel and href:
            self.hrefs.append(href)


def _discover_icon_urls(website: str) -> list[str]:
    current = website
    headers = {"User-Agent": "portfolio-analyzer/1.0", "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(timeout=5, follow_redirects=False, headers=headers, trust_env=False) as client:
        for redirect_count in range(MAX_REDIRECTS + 1):
            _validate_public_https_url(current)
            with client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    if redirect_count >= MAX_REDIRECTS:
                        return []
                    location = response.headers.get("location")
                    if not location:
                        return []
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                content_type = str(response.headers.get("content-type") or "").casefold()
                if content_type and "html" not in content_type:
                    return []
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_ICON_PAGE_BYTES:
                        return []
                    chunks.append(chunk)
            parser = _IconLinkParser()
            parser.feed(b"".join(chunks).decode("utf-8", errors="ignore"))
            return list(dict.fromkeys(urljoin(current, href) for href in parser.hrefs))
    return []


def _download_logo(url: str) -> tuple[bytes, str, str] | None:
    current = url
    headers = {"User-Agent": "portfolio-analyzer/1.0", "Accept": "image/png,image/jpeg,image/webp,image/gif,image/x-icon"}
    with httpx.Client(timeout=5, follow_redirects=False, headers=headers, trust_env=False) as client:
        for redirect_count in range(MAX_REDIRECTS + 1):
            _validate_public_https_url(current)
            with client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    if redirect_count >= MAX_REDIRECTS:
                        return None
                    location = response.headers.get("location")
                    if not location:
                        return None
                    current = urljoin(current, location)
                    continue
                if response.status_code in {404, 410}:
                    return None
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > MAX_LOGO_BYTES:
                            return None
                    except ValueError:
                        pass
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_LOGO_BYTES:
                        return None
                    chunks.append(chunk)
                image = b"".join(chunks)
            mime_type = _image_mime_type(image)
            return (image, mime_type, current) if mime_type else None
    return None


def _validate_public_https_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeLogoUrl("Company logos must use a public HTTPS URL")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as exc:
        raise OSError("Company logo host could not be resolved") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise UnsafeLogoUrl("Company logo host does not resolve to a public address")


def _image_mime_type(image: bytes) -> str:
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if image.startswith(b"RIFF") and len(image) >= 12 and image[8:12] == b"WEBP":
        return "image/webp"
    if image.startswith(b"\x00\x00\x01\x00"):
        return "image/x-icon"
    return ""


def _safe_source_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
