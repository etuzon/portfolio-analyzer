from __future__ import annotations

import socket

import pytest

from app import company_logos, main
from app.company_logos import CompanyLogoService, UnsafeLogoUrl
from app.providers import SqliteCache


class FakeHub:
    def __init__(self, cache: SqliteCache, profile: dict | None = None, status: dict | None = None):
        self.cache = cache
        self.profile_result = profile or {}
        self.status_result = status or {"provider": "missing"}
        self.profile_calls = 0

    def cached_profile(self, symbol, **kwargs):
        return {}

    def profile(self, symbol, **kwargs):
        self.profile_calls += 1
        return self.profile_result, self.status_result


def test_company_logo_is_downloaded_once_and_reused_from_sqlite(monkeypatch, tmp_path):
    path = tmp_path / "market-cache.sqlite3"
    first_hub = FakeHub(SqliteCache(path, ttl_hours=24), {"logo_url": "https://cdn.example/logo.png"}, {"provider": "ok"})
    downloads = []

    def fake_download(url):
        downloads.append(url)
        return b"\x89PNG\r\n\x1a\nlogo", "image/png", url

    monkeypatch.setattr(company_logos, "_download_logo", fake_download)
    first = CompanyLogoService(first_hub).get_or_resolve("aapl", stock_market="nasdaq")

    reopened_hub = FakeHub(SqliteCache(path, ttl_hours=24))
    second = CompanyLogoService(reopened_hub).get_or_resolve("AAPL", stock_market="NASDAQ")

    assert first["status"] == "ready"
    assert second["image"] == b"\x89PNG\r\n\x1a\nlogo"
    assert first_hub.profile_calls == 1
    assert reopened_hub.profile_calls == 0
    assert downloads == ["https://cdn.example/logo.png"]


def test_missing_company_logo_is_negatively_cached(monkeypatch, tmp_path):
    hub = FakeHub(SqliteCache(tmp_path / "market-cache.sqlite3", ttl_hours=24))
    monkeypatch.setattr(company_logos, "_download_logo", lambda url: pytest.fail("no URL should be downloaded"))
    service = CompanyLogoService(hub)

    assert service.get_or_resolve("UNKNOWN")["status"] == "missing"
    assert service.get_or_resolve("UNKNOWN")["status"] == "missing"
    assert hub.profile_calls == 1


def test_transient_logo_error_is_retried_after_one_day(monkeypatch, tmp_path):
    now = [1000.0]
    hub = FakeHub(
        SqliteCache(tmp_path / "market-cache.sqlite3", ttl_hours=24),
        {"logo_url": "https://cdn.example/logo.png"},
        {"provider": "ok"},
    )
    monkeypatch.setattr(company_logos, "_download_logo", lambda url: (_ for _ in ()).throw(OSError("offline")))
    service = CompanyLogoService(hub, clock=lambda: now[0])

    assert service.get_or_resolve("AAPL")["status"] == "error"
    assert service.get_or_resolve("AAPL")["status"] == "error"
    assert hub.profile_calls == 1

    now[0] += company_logos.ERROR_RETRY_SECONDS + 1
    assert service.get_or_resolve("AAPL")["status"] == "error"
    assert hub.profile_calls == 2


def test_company_website_declared_icon_is_preferred_over_guessed_paths(monkeypatch, tmp_path):
    hub = FakeHub(
        SqliteCache(tmp_path / "market-cache.sqlite3", ttl_hours=24),
        {"website": "https://www.fdus.com"},
        {"provider": "ok"},
    )
    discovered = "https://www.fdus.com/assets/fidus-icon.png"
    monkeypatch.setattr(company_logos, "_discover_icon_urls", lambda website: [discovered])
    monkeypatch.setattr(
        company_logos,
        "_download_logo",
        lambda url: (b"\x89PNG\r\n\x1a\nlogo", "image/png", url) if url == discovered else None,
    )

    result = CompanyLogoService(hub).get_or_resolve("FDUS")

    assert result["status"] == "ready"
    assert result["source_url"] == discovered


def test_logo_url_validation_rejects_private_hosts_and_non_https(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))])

    with pytest.raises(UnsafeLogoUrl):
        company_logos._validate_public_https_url("https://internal.example/logo.png")
    with pytest.raises(UnsafeLogoUrl):
        company_logos._validate_public_https_url("http://public.example/logo.png")


def test_company_logo_api_serves_cached_bytes_or_blank(monkeypatch):
    class Service:
        def __init__(self, result):
            self.result = result

        def get_or_resolve(self, *args, **kwargs):
            return self.result

    monkeypatch.setattr(main, "company_logo_service", lambda: Service({"status": "ready", "image": b"logo", "mime_type": "image/png"}))
    response = main.company_logo("AAPL", "NASDAQ")
    assert response.body == b"logo"
    assert response.media_type == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"

    monkeypatch.setattr(main, "company_logo_service", lambda: Service({"status": "missing"}))
    assert main.company_logo("UNKNOWN").status_code == 404
