from __future__ import annotations

import csv
import io
import json
import math
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .config import data_dir
from .models import Ohlcv
from .postgres import connect_postgres


class ProviderError(RuntimeError):
    pass


PERSISTENT_CACHE_PREFIXES = (
    "sec:companyfacts:",
    "sec:company-tickers",
    "yahoo:dividends:",
    "yahoo:chart:div:",
)

SEC_FUNDAMENTALS_PARSER_VERSION = "sec-periods-v2"


def _usable_fundamentals_snapshot(provider: Any, saved: Any) -> Any | None:
    # Reparse retained raw SEC facts after a parser change instead of serving
    # ratios built by an earlier period/debt interpretation during an outage.
    if getattr(provider, "name", "") == "sec_company_facts":
        if not isinstance(saved, dict) or saved.get("fundamentals_parser_version") != SEC_FUNDAMENTALS_PARSER_VERSION:
            return None
    return saved


def _provider_symbol_candidates(
    provider_name: str,
    primary_symbol: str,
    secondary_symbol: str = "",
    stock_market: str = "",
) -> list[str]:
    symbols: list[str] = []
    for value in (primary_symbol, secondary_symbol):
        symbol = str(value or "").strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)

    market = str(stock_market or "").strip().upper().replace(" ", "")
    if market in {"TASE", "TLV", "TELAVIV"} and provider_name in {"sec_company_facts", "nasdaq_quote", "stooq"}:
        # These adapters resolve bare US listings; a matching ticker is not
        # evidence for an Israeli security, even during a background refresh.
        return []
    if provider_name != "yahoo_finance" or market not in {"TASE", "TLV", "TELAVIV"}:
        return symbols

    yahoo_symbols: list[str] = []
    for symbol in symbols:
        if symbol.endswith(".TA"):
            yahoo_symbol = symbol
        elif symbol.endswith(":TLV") or symbol.endswith(":TASE"):
            yahoo_symbol = f"{symbol.rsplit(':', 1)[0]}.TA"
        else:
            yahoo_symbol = f"{symbol}.TA"
        if yahoo_symbol not in yahoo_symbols:
            yahoo_symbols.append(yahoo_symbol)
    return yahoo_symbols


class MarketDataHub:
    def __init__(self, config: dict[str, Any], db_config: dict[str, Any] | None = None):
        self.config = config
        self.db_config = db_config or {}
        self.cache = SqliteCache(
            data_dir() / "market-cache.sqlite3",
            int(config.get("cache_ttl_hours", 24)),
            int(config.get("max_cache_mb", 1000)),
        )
        self.providers = self._build_providers()

    def _build_providers(self) -> list[MarketDataProvider]:
        providers: list[MarketDataProvider] = []
        names = [self.config.get("primary")] + list(self.config.get("fallback", []))
        names += list(self.config.get("experimental_fallback", []))
        for name in [n for n in names if n]:
            if name == "alpha_vantage":
                provider_config = self.config.get("alpha_vantage", {})
                if provider_config.get("api_key"):
                    providers.append(AlphaVantageProvider(provider_config, self.cache))
            elif name == "financial_modeling_prep":
                provider_config = self.config.get("financial_modeling_prep", {})
                if provider_config.get("api_key"):
                    providers.append(FmpProvider(provider_config, self.cache))
            elif name == "frankfurter_fx":
                providers.append(FrankfurterFxProvider({}, self.cache))
            elif name == "nasdaq_quote":
                providers.append(NasdaqQuoteProvider({}, self.cache))
            elif name == "stooq":
                providers.append(StooqProvider({}, self.cache))
            elif name == "sec_company_facts":
                providers.append(SecCompanyFactsProvider({}, self.cache))
            elif name == "external_import_market_data":
                providers.append(ExternalImportMarketDataProvider(self.db_config, self.cache))
            elif name == "yahoo_finance" and self.config.get("yahoo_finance", {}).get("enabled"):
                providers.append(YahooChartProvider({}, self.cache))
            elif name == "google_finance" and self.config.get("google_finance", {}).get("enabled"):
                providers.append(UnsupportedProvider("google_finance", "Google Finance has no supported backend API"))
        return providers

    def fund_holdings(self, symbol: str, stock_market: str):
        """Explicit refresh of a supported listing's official issuer download."""
        if stock_market.upper() not in {"NASDAQ", "NYSE", "NYSEARCA", "AMEX", "US"}:
            raise ProviderError("xray_issuer_unsupported")
        return IssuerFundHoldingsProvider({}, self.cache).fund_holdings(symbol.upper())

    def prices(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
        *,
        secondary_symbol: str = "",
        stock_market: str = "",
    ) -> tuple[list[Ohlcv], dict[str, str]]:
        status = {}
        best_prices: list[Ohlcv] = []
        for provider in self.providers:
            saved_prices: list[Ohlcv] = []
            errors: list[Exception] = []
            live_found = False
            for provider_symbol in _provider_symbol_candidates(provider.name, symbol, secondary_symbol, stock_market):
                candidate_saved = self.cache.get_prices(provider.name, provider_symbol, from_date, to_date)
                if _price_score(candidate_saved, from_date, to_date) > _price_score(saved_prices, from_date, to_date):
                    saved_prices = candidate_saved
                try:
                    prices = provider.prices(provider_symbol, from_date, to_date)
                except Exception as exc:
                    errors.append(exc)
                    continue
                if prices:
                    status[provider.name] = "ok"
                    self.cache.set_prices(provider.name, provider_symbol, prices)
                    if _price_score(prices, from_date, to_date) > _price_score(best_prices, from_date, to_date):
                        best_prices = prices
                    live_found = True
                    break
            if live_found:
                continue
            if saved_prices:
                error_suffix = f"; {errors[-1].__class__.__name__}" if errors else ""
                status[provider.name] = f"stale (saved local history{error_suffix})"
                if _price_score(saved_prices, from_date, to_date) > _price_score(best_prices, from_date, to_date):
                    best_prices = saved_prices
            elif errors:
                status[provider.name] = f"error: {errors[-1].__class__.__name__}"
            else:
                status[provider.name] = "missing"
        return best_prices, status or {"providers": "none configured"}

    def cached_prices(
        self, symbol: str, from_date: date, to_date: date, *, secondary_symbol: str = "", stock_market: str = "",
    ) -> tuple[list[Ohlcv], dict[str, str]]:
        return CachedMarketDataHub(self).prices(symbol, from_date, to_date, secondary_symbol, stock_market)

    def fundamentals(
        self,
        symbol: str,
        *,
        secondary_symbol: str = "",
        stock_market: str = "",
    ) -> tuple[dict[str, Any], dict[str, str]]:
        status = {}
        saved_fallback: dict[str, Any] | None = None
        for provider in self.providers:
            provider_saved: dict[str, Any] | None = None
            errors: list[Exception] = []
            for provider_symbol in _provider_symbol_candidates(provider.name, symbol, secondary_symbol, stock_market):
                saved = _usable_fundamentals_snapshot(provider, self.cache.get_security_snapshot(provider.name, provider_symbol, "fundamentals"))
                provider_saved = provider_saved or saved
                try:
                    data = provider.fundamentals(provider_symbol)
                except Exception as exc:
                    errors.append(exc)
                    cached_reader = getattr(provider, "cached_fundamentals", None)
                    if provider_saved is None and callable(cached_reader):
                        provider_saved = cached_reader(provider_symbol) or None
                    continue
                if data:
                    status[provider.name] = "ok"
                    self.cache.set_security_snapshot(provider.name, provider_symbol, "fundamentals", data)
                    return data, status
            if provider_saved is not None:
                error_suffix = f"; {errors[-1].__class__.__name__}" if errors else ""
                status[provider.name] = f"stale (saved local history{error_suffix})"
                saved_fallback = saved_fallback or provider_saved
            elif errors:
                status[provider.name] = f"error: {errors[-1].__class__.__name__}"
            else:
                status[provider.name] = "missing"
        if saved_fallback is not None:
            return saved_fallback, status
        if not self._has_fundamental_provider():
            status["fundamentals_api"] = "missing Alpha Vantage or FMP API key"
        return {}, status or {"providers": "none configured"}

    def fundamentals_as_of(
        self,
        symbol: str,
        as_of: date,
        *,
        secondary_symbol: str = "",
        stock_market: str = "",
    ) -> tuple[dict[str, Any], dict[str, str]]:
        status = {}
        data_type = f"fundamentals_as_of:{as_of.isoformat()}"
        saved_fallback: dict[str, Any] | None = None
        for provider in self.providers:
            provider_saved: dict[str, Any] | None = None
            errors: list[Exception] = []
            for provider_symbol in _provider_symbol_candidates(provider.name, symbol, secondary_symbol, stock_market):
                saved = _usable_fundamentals_snapshot(provider, self.cache.get_security_snapshot(provider.name, provider_symbol, data_type))
                provider_saved = provider_saved or saved
                try:
                    data = provider.fundamentals_as_of(provider_symbol, as_of)
                except Exception as exc:
                    errors.append(exc)
                    cached_reader = getattr(provider, "cached_fundamentals", None)
                    if provider_saved is None and callable(cached_reader):
                        provider_saved = cached_reader(provider_symbol, as_of) or None
                    continue
                if data:
                    status[provider.name] = "ok"
                    self.cache.set_security_snapshot(provider.name, provider_symbol, data_type, data)
                    return data, status
            if provider_saved is not None:
                error_suffix = f"; {errors[-1].__class__.__name__}" if errors else ""
                status[provider.name] = f"stale (saved local history{error_suffix})"
                saved_fallback = saved_fallback or provider_saved
            elif errors:
                status[provider.name] = f"error: {errors[-1].__class__.__name__}"
            else:
                status[provider.name] = "missing"
        if saved_fallback is not None:
            return saved_fallback, status
        if not self._has_fundamental_provider():
            status["fundamentals_api"] = "missing Alpha Vantage or FMP API key"
        return {}, status or {"providers": "none configured"}

    def dividends(
        self,
        symbol: str,
        force_refresh: bool = False,
        to_date: date | None = None,
        *,
        secondary_symbol: str = "",
        stock_market: str = "",
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        status = {}
        data_type = f"dividends_as_of:{to_date.isoformat()}" if to_date else "dividends"
        saved_fallback: list[dict[str, Any]] | None = None
        for provider in self.providers:
            provider_saved: list[dict[str, Any]] | None = None
            errors: list[Exception] = []
            for provider_symbol in _provider_symbol_candidates(provider.name, symbol, secondary_symbol, stock_market):
                saved = self.cache.get_security_snapshot(provider.name, provider_symbol, data_type)
                provider_saved = provider_saved or saved
                try:
                    data = provider.dividends(provider_symbol, force_refresh=force_refresh, to_date=to_date)
                except Exception as exc:
                    errors.append(exc)
                    continue
                if data:
                    status[provider.name] = "ok"
                    self.cache.set_security_snapshot(provider.name, provider_symbol, data_type, data)
                    return data, status
            if provider_saved is not None:
                error_suffix = f"; {errors[-1].__class__.__name__}" if errors else ""
                status[provider.name] = f"stale (saved local history{error_suffix})"
                saved_fallback = saved_fallback or provider_saved
            elif errors:
                status[provider.name] = f"error: {errors[-1].__class__.__name__}"
            else:
                status[provider.name] = "missing"
        if saved_fallback is not None:
            return saved_fallback, status
        if not self._has_fundamental_provider():
            status["dividend_api"] = "missing Alpha Vantage or FMP API key"
        return [], status or {"providers": "none configured"}

    def profile(
        self,
        symbol: str,
        *,
        secondary_symbol: str = "",
        stock_market: str = "",
    ) -> tuple[dict[str, Any], dict[str, str]]:
        status = {}
        live_merged: dict[str, Any] = {}
        saved_merged: dict[str, Any] = {}
        for provider in self.providers:
            provider_saved: dict[str, Any] = {}
            errors: list[Exception] = []
            live_found = False
            for provider_symbol in _provider_symbol_candidates(provider.name, symbol, secondary_symbol, stock_market):
                saved = self.cache.get_security_snapshot(provider.name, provider_symbol, "profile")
                if isinstance(saved, dict):
                    provider_saved.update({key: value for key, value in saved.items() if value not in (None, "")})
                try:
                    data = provider.profile(provider_symbol)
                except Exception as exc:
                    errors.append(exc)
                    continue
                if data:
                    status[provider.name] = "ok"
                    self.cache.set_security_snapshot(provider.name, provider_symbol, "profile", data)
                    live_merged.update({key: value for key, value in data.items() if value not in (None, "")})
                    live_found = True
                    break
            if live_found:
                continue
            if provider_saved:
                error_suffix = f"; {errors[-1].__class__.__name__}" if errors else ""
                status[provider.name] = f"stale (saved local history{error_suffix})"
                saved_merged.update(provider_saved)
            elif errors:
                status[provider.name] = f"error: {errors[-1].__class__.__name__}"
            else:
                status[provider.name] = "missing"
        return {**saved_merged, **live_merged}, status or {"providers": "none configured"}

    def cached_profile(
        self,
        symbol: str,
        *,
        secondary_symbol: str = "",
        stock_market: str = "",
    ) -> dict[str, Any]:
        return self.cached_view().profile(symbol, secondary_symbol=secondary_symbol, stock_market=stock_market)[0]

    def cached_recent_prices(self, symbol: str, from_date: date, to_date: date, **context):
        """Newest dated saved series for quote views, independent of coverage scoring."""
        return self.cached_view().recent_prices(symbol, from_date, to_date, **context)

    def cached_view(self) -> CachedMarketDataHub:
        """Read saved market evidence without invoking any provider or cache writes."""
        return CachedMarketDataHub(self)

    def fx(self, pair: str) -> tuple[dict[str, Any], dict[str, str]]:
        status = {}
        saved_fallback: dict[str, Any] | None = None
        for provider in self.providers:
            saved = self.cache.get_security_snapshot(provider.name, pair, "fx")
            try:
                data = provider.fx(pair)
                if data:
                    status[provider.name] = "ok"
                    self.cache.set_security_snapshot(provider.name, pair, "fx", data)
                    return data, status
                if saved is not None:
                    status[provider.name] = "stale (saved local history)"
                    saved_fallback = saved_fallback or saved
                else:
                    status[provider.name] = "missing"
            except Exception as exc:
                if saved is not None:
                    status[provider.name] = f"stale (saved local history; {exc.__class__.__name__})"
                    saved_fallback = saved_fallback or saved
                else:
                    status[provider.name] = f"error: {exc.__class__.__name__}"
        return saved_fallback or {}, status or {"providers": "none configured"}

    def fx_history(self, currency: str, from_date: date, to_date: date) -> dict[str, Any]:
        """Explicit download of official historical ILS representative rates."""
        return BankOfIsraelFxHistoryProvider({}, self.cache).history(currency, from_date, to_date)

    def quote(self, symbol: str) -> tuple[dict[str, Any], dict[str, str]]:
        status = {}
        saved_fallback: dict[str, Any] | None = None
        for provider in self.providers:
            saved = self.cache.get_security_snapshot(provider.name, symbol, "quote")
            try:
                data = provider.quote(symbol)
                if data:
                    status[provider.name] = "ok"
                    self.cache.set_security_snapshot(provider.name, symbol, "quote", data)
                    return data, status
                if saved is not None:
                    status[provider.name] = "stale (saved local history)"
                    saved_fallback = saved_fallback or saved
                else:
                    status[provider.name] = "missing"
            except Exception as exc:
                if saved is not None:
                    status[provider.name] = f"stale (saved local history; {exc.__class__.__name__})"
                    saved_fallback = saved_fallback or saved
                else:
                    status[provider.name] = f"error: {exc.__class__.__name__}"
        if saved_fallback is not None:
            return saved_fallback, status
        if not self.config.get("financial_modeling_prep", {}).get("api_key"):
            status["financial_modeling_prep"] = "missing API key"
        return {}, status or {"providers": "none configured"}

    def market_screener(self, criteria: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
        status = {}
        for provider in self.providers:
            try:
                data = provider.market_screener(criteria)
                if data:
                    status[provider.name] = "ok"
                    return data, status
                status[provider.name] = "missing"
            except Exception as exc:
                status[provider.name] = f"error: {exc.__class__.__name__}"
        query = str(criteria.get("query") or "").strip().upper()
        if query:
            try:
                data = SecCompanyTickerProvider({}, self.cache).market_screener(criteria)
                if data:
                    status["sec_company_tickers"] = "ok"
                    return data, status
                status["sec_company_tickers"] = "missing"
            except Exception as exc:
                status["sec_company_tickers"] = f"error: {exc.__class__.__name__}"
        if query and all(char.isalnum() or char in ".-^=" for char in query):
            try:
                quote = StooqProvider({}, self.cache).quote(query)
                if quote:
                    status["stooq"] = "ok"
                    return [
                        {
                            "symbol": quote.get("symbol") or query,
                            "name": quote.get("name") or "",
                            "exchange": quote.get("exchange") or "US",
                            "currency": quote.get("currency") or "USD",
                            "price": quote.get("price"),
                            "market_cap": None,
                            "sector": None,
                            "industry": None,
                            "beta": None,
                            "dividend": None,
                        }
                    ], status
                status["stooq"] = "missing"
            except Exception as exc:
                status["stooq"] = f"error: {exc.__class__.__name__}"
        if not self.config.get("financial_modeling_prep", {}).get("api_key"):
            status["financial_modeling_prep"] = "missing API key"
        return [], status or {"providers": "none configured"}

    def cache_status(self) -> dict[str, Any]:
        return self.cache.status()

    def _has_fundamental_provider(self) -> bool:
        return bool(
            self.config.get("alpha_vantage", {}).get("api_key")
            or self.config.get("financial_modeling_prep", {}).get("api_key")
            or self.config.get("yahoo_finance", {}).get("enabled")
        )


class CachedMarketDataHub:
    """Provider-shaped, read-only view used for immediate dashboard analytics."""

    def __init__(self, hub: MarketDataHub):
        self.hub = hub

    def _candidates(self, provider: Any, symbol: str, secondary_symbol: str, stock_market: str) -> list[str]:
        candidates = _provider_symbol_candidates(provider.name, symbol, secondary_symbol, stock_market)
        if stock_market.upper().replace(" ", "") in {"TASE", "TLV", "TELAVIV"}:
            # Bare tickers in SEC/US caches cannot establish an Israeli listing.
            return [value for value in candidates if value.endswith(".TA")] if provider.name == "yahoo_finance" else []
        return candidates

    def _snapshot(self, kind: str, symbol: str, secondary_symbol: str = "", stock_market: str = ""):
        for provider in self.hub.providers:
            for candidate in self._candidates(provider, symbol, secondary_symbol, stock_market):
                saved = self.hub.cache.get_security_snapshot(provider.name, candidate, kind)
                if kind == "fundamentals":
                    saved = _usable_fundamentals_snapshot(provider, saved)
                    if saved is None and callable(getattr(provider, "cached_fundamentals", None)):
                        saved = provider.cached_fundamentals(candidate)
                if saved:
                    return saved, {provider.name: "cached"}
        return ([] if kind == "dividends" else {}), {"cache": "pending"}

    def fundamentals(self, symbol: str, **context):
        return self._snapshot("fundamentals", symbol, **context)

    def dividends(self, symbol: str, **context):
        return self._snapshot("dividends", symbol, **context)

    def dividend_calendar(self, symbol: str, secondary_symbol: str = "", stock_market: str = ""):
        """Saved evidence only; future scan snapshots may include declared dates."""
        for provider in self.hub.providers:
            for candidate in self._candidates(provider, symbol, secondary_symbol, stock_market):
                saved = self.hub.cache.get_dividend_snapshot(provider.name, candidate)
                if saved:
                    return {**saved, "provider": provider.name}
        return {"items": [], "provider": None, "updated_at": None}

    def latest_price(self, symbol: str, from_date: date, to_date: date, secondary_symbol: str = "", stock_market: str = ""):
        latest = None
        for provider in self.hub.providers:
            for candidate in self._candidates(provider, symbol, secondary_symbol, stock_market):
                for row in self.hub.cache.get_prices(provider.name, candidate, from_date, to_date):
                    if math.isfinite(row.close) and row.close > 0 and (latest is None or row.date > latest["date"]):
                        latest = {"date": row.date, "close": row.close, "provider": provider.name}
        return latest

    def recent_prices(self, symbol: str, from_date: date, to_date: date, secondary_symbol: str = "", stock_market: str = ""):
        best, best_key, status = [], None, {}
        for provider in self.hub.providers:
            for candidate in self._candidates(provider, symbol, secondary_symbol, stock_market):
                saved = [row for row in self.hub.cache.get_prices(provider.name, candidate, from_date, to_date)
                         if from_date <= row.date <= to_date and math.isfinite(row.close) and row.close > 0]
                if saved:
                    status[provider.name] = "cached"
                    key = (max(row.date for row in saved), len(saved))
                    if best_key is None or key > best_key:
                        best, best_key = saved, key
        return best, status or {"cache": "pending"}

    def profile(self, symbol: str, secondary_symbol: str = "", stock_market: str = ""):
        merged, status = {}, {}
        for provider in self.hub.providers:
            for candidate in self._candidates(provider, symbol, secondary_symbol, stock_market):
                saved = self.hub.cache.get_security_snapshot(provider.name, candidate, "profile")
                if isinstance(saved, dict):
                    merged.update({key: value for key, value in saved.items() if value not in (None, "")})
                    status[provider.name] = "cached"
        return merged, status or {"cache": "pending"}

    def prices(self, symbol: str, from_date: date, to_date: date, secondary_symbol: str = "", stock_market: str = ""):
        best, status = [], {}
        for provider in self.hub.providers:
            for candidate in self._candidates(provider, symbol, secondary_symbol, stock_market):
                saved = self.hub.cache.get_prices(provider.name, candidate, from_date, to_date)
                if _price_score(saved, from_date, to_date) > _price_score(best, from_date, to_date):
                    best = saved
                if saved:
                    status[provider.name] = "cached"
        return best, status or {"cache": "pending"}


class SqliteCache:
    def __init__(self, path: Path, ttl_hours: int, max_mb: int = 1000):
        self.path = path
        self.ttl_seconds = ttl_hours * 3600
        self.max_bytes = max(1, max_mb) * 1024 * 1024
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.execute("pragma journal_mode=delete")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists cache (
                    key text primary key,
                    created_at real not null,
                    value text not null
                )
                """
            )
            conn.execute("create index if not exists idx_cache_created_at on cache(created_at)")
            conn.execute(
                """
                create table if not exists price_cache (
                    provider text not null,
                    symbol text not null,
                    date text not null,
                    open real not null,
                    high real not null,
                    low real not null,
                    close real not null,
                    adjusted_close real not null,
                    volume real not null,
                    primary key (provider, symbol, date)
                )
                """
            )
            conn.execute("create index if not exists idx_price_cache_lookup on price_cache(provider, symbol, date)")
            conn.execute(
                """
                create table if not exists price_meta (
                    provider text not null,
                    symbol text not null,
                    last_checked text not null,
                    primary key (provider, symbol)
                )
                """
            )
            conn.execute(
                """
                create table if not exists security_snapshot (
                    provider text not null,
                    symbol text not null,
                    data_type text not null,
                    updated_at real not null,
                    value text not null,
                    primary key (provider, symbol, data_type)
                )
                """
            )
            conn.execute("create index if not exists idx_security_snapshot_symbol on security_snapshot(symbol, data_type)")
            conn.execute(
                """
                create table if not exists company_logos (
                    symbol text not null,
                    stock_market text not null default '',
                    status text not null,
                    mime_type text not null default '',
                    image blob,
                    source_url text not null default '',
                    checked_at real not null,
                    primary key (symbol, stock_market)
                )
                """
            )

    def get(self, key: str, *, require_fresh: bool = False) -> Any | None:
        with self._connect() as conn:
            row = conn.execute("select created_at, value from cache where key = ?", (key,)).fetchone()
            if not row:
                return None
            created_at, value = row
            persistent = _persistent_cache_key(key)
            if time.time() - float(created_at) > self.ttl_seconds and (require_fresh or not persistent):
                # Retained evidence stays available to local/offline readers;
                # online providers must still check its refresh interval.
                if not persistent:
                    conn.execute("delete from cache where key = ?", (key,))
                return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: Any) -> None:
        payload = json.dumps(value, default=str, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                "insert or replace into cache (key, created_at, value) values (?, ?, ?)",
                (key, time.time(), payload),
            )
        self._prune()

    def get_prices(self, provider: str, symbol: str, from_date: date, to_date: date) -> list[Ohlcv]:
        normalized_symbol = symbol.upper()
        with self._connect() as conn:
            rows = conn.execute(
                """
                select date, open, high, low, close, adjusted_close, volume
                from price_cache
                where provider = ?
                  and symbol = ?
                  and date >= ?
                  and date <= ?
                order by date
                """,
                (provider, normalized_symbol, from_date.isoformat(), to_date.isoformat()),
            ).fetchall()
        return [_ohlcv_from_tuple(row) for row in rows]

    def set_prices(self, provider: str, symbol: str, rows: list[Ohlcv]) -> None:
        if not rows:
            return
        normalized_symbol = symbol.upper()
        with self._connect() as conn:
            conn.executemany(
                """
                insert or replace into price_cache
                  (provider, symbol, date, open, high, low, close, adjusted_close, volume)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        provider,
                        normalized_symbol,
                        row.date.isoformat(),
                        row.open,
                        row.high,
                        row.low,
                        row.close,
                        row.adjusted_close,
                        row.volume,
                    )
                    for row in rows
                ],
            )

    def price_bounds(self, provider: str, symbol: str) -> tuple[date, date] | None:
        normalized_symbol = symbol.upper()
        with self._connect() as conn:
            row = conn.execute(
                """
                select min(date), max(date)
                from price_cache
                where provider = ? and symbol = ?
                """,
                (provider, normalized_symbol),
            ).fetchone()
        if not row or not row[0] or not row[1]:
            return None
        return date.fromisoformat(row[0]), date.fromisoformat(row[1])

    def get_prices_checked(self, provider: str, symbol: str) -> date | None:
        normalized_symbol = symbol.upper()
        with self._connect() as conn:
            row = conn.execute(
                "select last_checked from price_meta where provider = ? and symbol = ?",
                (provider, normalized_symbol),
            ).fetchone()
        return date.fromisoformat(row[0]) if row and row[0] else None

    def set_prices_checked(self, provider: str, symbol: str, checked_date: date) -> None:
        normalized_symbol = symbol.upper()
        with self._connect() as conn:
            conn.execute(
                """
                insert or replace into price_meta (provider, symbol, last_checked)
                values (?, ?, ?)
                """,
                (provider, normalized_symbol, checked_date.isoformat()),
            )

    def get_security_snapshot(self, provider: str, symbol: str, data_type: str) -> Any | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select value
                from security_snapshot
                where provider = ? and symbol = ? and data_type = ?
                """,
                (provider, str(symbol or "").upper(), data_type),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None

    def set_security_snapshot(self, provider: str, symbol: str, data_type: str, value: Any) -> None:
        if value in (None, {}, []):
            return
        payload = json.dumps(value, default=str, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                """
                insert or replace into security_snapshot
                  (provider, symbol, data_type, updated_at, value)
                values (?, ?, ?, ?, ?)
                """,
                (provider, str(symbol or "").upper(), data_type, time.time(), payload),
            )

    def get_dividend_snapshot(self, provider: str, symbol: str) -> dict[str, Any] | None:
        # Do not let a historical as-of query supersede present-day evidence.
        # Reading this retained snapshot never prunes or writes the cache.
        with self._connect() as conn:
            rows = conn.execute(
                "select data_type, updated_at, value from security_snapshot "
                "where provider = ? and symbol = ? and (data_type = 'dividends' or data_type like 'dividends_as_of:%') "
                "order by updated_at desc",
                (provider, str(symbol or "").upper()),
            ).fetchall()
        for kind, updated_at, raw in rows:
            if kind != "dividends" and kind.split(":", 1)[-1] < date.today().isoformat():
                continue
            try:
                items = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(items, list) and items:
                return {"items": items, "updated_at": float(updated_at)}
        return None

    def get_company_logo(self, symbol: str, stock_market: str = "") -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select status, mime_type, image, source_url, checked_at
                from company_logos
                where symbol = ? and stock_market = ?
                """,
                (str(symbol or "").upper(), str(stock_market or "").upper()),
            ).fetchone()
        if not row:
            return None
        return {
            "status": row[0],
            "mime_type": row[1],
            "image": row[2],
            "source_url": row[3],
            "checked_at": float(row[4]),
        }

    def set_company_logo(
        self,
        symbol: str,
        stock_market: str,
        *,
        status: str,
        mime_type: str = "",
        image: bytes | None = None,
        source_url: str = "",
        checked_at: float | None = None,
    ) -> None:
        if status not in {"ready", "missing", "error"}:
            raise ValueError("Unsupported company logo status")
        if status == "ready" and (not image or not mime_type):
            raise ValueError("A ready company logo requires image bytes and a MIME type")
        with self._connect() as conn:
            conn.execute(
                """
                insert or replace into company_logos
                  (symbol, stock_market, status, mime_type, image, source_url, checked_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(symbol or "").upper(),
                    str(stock_market or "").upper(),
                    status,
                    mime_type,
                    image,
                    source_url,
                    time.time() if checked_at is None else checked_at,
                ),
            )

    def status(self) -> dict[str, Any]:
        size = self.path.stat().st_size if self.path.exists() else 0
        with self._connect() as conn:
            rows = conn.execute("select count(*) from cache").fetchone()[0]
            price_rows = conn.execute("select count(*) from price_cache").fetchone()[0]
            security_snapshots = conn.execute("select count(*) from security_snapshot").fetchone()[0]
            security_symbols = conn.execute("select count(distinct symbol) from security_snapshot").fetchone()[0]
            company_logos = conn.execute("select count(*) from company_logos where status = 'ready'").fetchone()[0]
            missing_company_logos = conn.execute("select count(*) from company_logos where status = 'missing'").fetchone()[0]
        return {
            "path": str(self.path),
            "entries": rows,
            "price_entries": price_rows,
            "security_snapshots": security_snapshots,
            "security_symbols": security_symbols,
            "company_logos": company_logos,
            "missing_company_logos": missing_company_logos,
            "size_mb": round(size / 1024 / 1024, 3),
            "max_mb": round(self.max_bytes / 1024 / 1024, 3),
            "ttl_hours": round(self.ttl_seconds / 3600, 2),
        }

    def _prune(self) -> None:
        if not self.path.exists() or self.path.stat().st_size <= self.max_bytes:
            return
        target = int(self.max_bytes * 0.9)
        with self._connect() as conn:
            while self.path.stat().st_size > target:
                keys = [row[0] for row in conn.execute("select key from cache order by created_at limit 250").fetchall()]
                if not keys:
                    break
                conn.executemany("delete from cache where key = ?", [(key,) for key in keys])
                conn.commit()
            conn.execute("vacuum")


class MarketDataProvider:
    name = "base"

    def __init__(self, config: dict[str, Any], cache: SqliteCache):
        self.config = config
        self.cache = cache

    def _get_json(self, url: str, params: dict[str, Any], cache_key: str, force_refresh: bool = False) -> Any:
        cached = self.cache.get(cache_key) if not force_refresh else None
        if cached is not None:
            return cached
        headers = {"User-Agent": "portfolio-analyzer/1.0"}
        with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        self.cache.set(cache_key, data)
        return data

    def prices(self, symbol: str, from_date: date, to_date: date) -> list[Ohlcv]:
        return []

    def fundamentals(self, symbol: str) -> dict[str, Any]:
        return {}

    def fundamentals_as_of(self, symbol: str, as_of: date) -> dict[str, Any]:
        return self.fundamentals(symbol)

    def dividends(self, symbol: str, force_refresh: bool = False, to_date: date | None = None) -> list[dict[str, Any]]:
        return []

    def profile(self, symbol: str) -> dict[str, Any]:
        return {}

    def fx(self, pair: str) -> dict[str, Any]:
        return {}

    def quote(self, symbol: str) -> dict[str, Any]:
        return {}

    def market_screener(self, criteria: dict[str, Any]) -> list[dict[str, Any]]:
        return []


def _cached_or_fetch_prices(
    cache: SqliteCache,
    provider: str,
    symbol: str,
    from_date: date,
    to_date: date,
    fetch_fn,
) -> list[Ohlcv]:
    cached = cache.get_prices(provider, symbol, from_date, to_date)
    bounds = cache.price_bounds(provider, symbol)
    last_checked = cache.get_prices_checked(provider, symbol)
    starts_near_request = bool(bounds and bounds[0] <= from_date + timedelta(days=7))

    if cached and starts_near_request and last_checked and last_checked >= to_date:
        return cached

    if cached and starts_near_request and bounds:
        fetch_start = bounds[1] + timedelta(days=1)
    else:
        fetch_start = from_date

    if fetch_start <= to_date:
        fetched = fetch_fn(fetch_start, to_date)
        cache.set_prices(provider, symbol, fetched)
    cache.set_prices_checked(provider, symbol, to_date)
    return cache.get_prices(provider, symbol, from_date, to_date)


class IssuerFundHoldingsProvider(MarketDataProvider):
    """Parse issuer-published files with explicit identities, dates and units."""
    name = "issuer_fund_holdings"
    SOURCES = {
        "IVV": "https://www.ishares.com/us/products/239726/ishares-core-s-p-500-etf/latest-holdings.csv",
        "SPY": "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx",
    }

    def fund_holdings(self, symbol):
        from .xray import normalize_snapshot
        url = self.SOURCES.get(symbol)
        if not url:
            raise ProviderError("xray_issuer_unsupported")
        try:
            with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": "portfolio-analyzer/1.0"}) as client:
                response = client.get(url)
                response.raise_for_status()
            if len(response.content) > 5_000_000:
                raise ValueError("report too large")
            rows, as_of = self.parse_ivv(response.text) if symbol == "IVV" else self.parse_spy(response.content)
            snapshot = normalize_snapshot(rows, as_of=as_of, source_name="iShares" if symbol == "IVV" else "State Street",
                                          source_url=url, source_kind="issuer")
        except Exception as exc:
            # Do not expose network exceptions or credentials in diagnostics.
            raise ProviderError("xray_issuer_failed") from exc
        self.cache.set_security_snapshot(self.name, symbol, "fund_holdings", snapshot)
        return snapshot

    @staticmethod
    def parse_ivv(content):
        rows = list(csv.reader(content.lstrip("\ufeff").splitlines()))
        if not rows or rows[0] != ["iShares Core S&P 500 ETF"]:
            raise ValueError("fund identity mismatch")
        as_of = datetime.strptime(next(r[1] for r in rows if r and r[0] == "Fund Holdings as of"), "%b %d, %Y").date().isoformat()
        start = next(i for i, r in enumerate(rows) if r and r[0] == "Ticker")
        result = []
        us_exchanges = {"NASDAQ", "NYSE", "Cboe BZX", "New York Stock Exchange Inc.", "NYSE Arca", "Nyse Mkt Llc", "Cboe BZX formerly BATS"}
        for values in rows[start + 1:]:
            row = dict(zip(rows[start], values))
            if row.get("Asset Class") != "Equity" or row.get("Exchange") not in us_exchanges:
                continue
            if row.get("Market Weight") in {None, "", "-"}:
                continue
            weight = float(row["Market Weight"])
            if weight > 0:
                result.append({"symbol": row["Ticker"], "market": "US", "weight_percent": weight, "name": row["Name"], "asset_class": "EQUITY"})
        return result, as_of

    @staticmethod
    def parse_spy(content):
        import io
        import re
        import zipfile
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(info.file_size for info in archive.infolist()) > 25_000_000:
                raise ValueError("report too large")
            strings = ["".join(item.itertext()) for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", ns)]
            rows = []
            for row in ET.fromstring(archive.read("xl/worksheets/sheet1.xml")).findall(".//m:row", ns):
                cells = {}
                for cell in row.findall("m:c", ns):
                    value = cell.find("m:v", ns)
                    text = value.text if value is not None else ""
                    if cell.get("t") == "s" and text:
                        text = strings[int(text)]
                    cells[re.sub(r"\d", "", cell.get("r", ""))] = text
                rows.append(cells)
        if not any(r.get("A") == "Ticker Symbol:" and r.get("B") == "SPY" for r in rows):
            raise ValueError("fund identity mismatch")
        reported = next(r["B"] for r in rows if r.get("A") == "Holdings:")
        as_of = datetime.strptime(reported.removeprefix("As of "), "%d-%b-%Y").date().isoformat()
        start = next(i for i, r in enumerate(rows) if r.get("A") == "Name" and r.get("B") == "Ticker" and r.get("E") == "Weight")
        result = []
        for row in rows[start + 1:]:
            ticker = row.get("B") or ""
            if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,19}", ticker) or not re.fullmatch(r"[A-Z0-9]{9}", row.get("C") or "") or row.get("H") != "USD":
                continue
            weight = float(row["E"])
            if weight > 0:
                result.append({"symbol": ticker, "market": "US", "weight_percent": weight, "name": row.get("A", "")})
        return result, as_of


class AlphaVantageProvider(MarketDataProvider):
    name = "alpha_vantage"
    base = "https://www.alphavantage.co/query"

    @property
    def api_key(self) -> str:
        return self.config.get("api_key") or ""

    def _require_key(self):
        if not self.api_key:
            raise ProviderError("missing Alpha Vantage API key")

    def prices(self, symbol: str, from_date: date, to_date: date) -> list[Ohlcv]:
        self._require_key()
        cached = self.cache.get_prices(self.name, symbol, from_date, to_date)
        last_checked = self.cache.get_prices_checked(self.name, symbol)
        if cached and last_checked and last_checked >= to_date:
            return cached
        data = self._get_json(
            self.base,
            {"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": symbol, "outputsize": "full", "apikey": self.api_key},
            f"av:prices:{symbol}",
            force_refresh=not (last_checked and last_checked >= to_date),
        )
        series = data.get("Time Series (Daily)", {})
        rows = sorted(
            [
                Ohlcv(
                    date=date.fromisoformat(day),
                    open=float(row["1. open"]),
                    high=float(row["2. high"]),
                    low=float(row["3. low"]),
                    close=float(row["4. close"]),
                    adjusted_close=float(row["5. adjusted close"]),
                    volume=float(row["6. volume"]),
                )
                for day, row in series.items()
                if from_date <= date.fromisoformat(day) <= to_date
            ],
            key=lambda item: item.date,
        )
        if rows:
            self.cache.set_prices(self.name, symbol, rows)
            self.cache.set_prices_checked(self.name, symbol, to_date)
            return self.cache.get_prices(self.name, symbol, from_date, to_date)
        return cached

    def fundamentals(self, symbol: str) -> dict[str, Any]:
        self._require_key()
        income = self._get_json(self.base, {"function": "INCOME_STATEMENT", "symbol": symbol, "apikey": self.api_key}, f"av:income:{symbol}")
        overview = self._get_json(self.base, {"function": "OVERVIEW", "symbol": symbol, "apikey": self.api_key}, f"av:overview:{symbol}")
        return {"income_statement": income, "overview": overview}

    def dividends(self, symbol: str, force_refresh: bool = False, to_date: date | None = None) -> list[dict[str, Any]]:
        self._require_key()
        data = self._get_json(
            self.base,
            {"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": symbol, "outputsize": "full", "apikey": self.api_key},
            f"av:prices:{symbol}",
            force_refresh=force_refresh,
        )
        return [
            {"date": day, "amount": float(row.get("7. dividend amount", 0) or 0)}
            for day, row in data.get("Time Series (Daily)", {}).items()
            if float(row.get("7. dividend amount", 0) or 0) > 0
        ]

    def profile(self, symbol: str) -> dict[str, Any]:
        fundamentals = self.fundamentals(symbol)
        overview = fundamentals.get("overview", {})
        return {"name": overview.get("Name"), "industry": overview.get("Industry"), "sector": overview.get("Sector"), "exchange": overview.get("Exchange"), "market_cap": _float_or_none(overview.get("MarketCapitalization")), "website": overview.get("OfficialSite")}

    def fx(self, pair: str) -> dict[str, Any]:
        self._require_key()
        src, dst = pair.split("/", 1)
        data = self._get_json(
            self.base,
            {"function": "CURRENCY_EXCHANGE_RATE", "from_currency": src, "to_currency": dst, "apikey": self.api_key},
            f"av:fx:{pair}",
        )
        quote = data.get("Realtime Currency Exchange Rate", {})
        return {"pair": pair, "rate": _float_or_none(quote.get("5. Exchange Rate")), "time": quote.get("6. Last Refreshed")}


class BankOfIsraelFxHistoryProvider(MarketDataProvider):
    name = "bank_of_israel_fx"
    base = "https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/EXR/1.0/"

    @staticmethod
    def parse_history(text: str, currency: str, from_date: date, to_date: date) -> list[dict[str, Any]]:
        """Keep official levels only and normalize quotes per ONE foreign unit."""
        rates = {}
        for row in csv.DictReader(io.StringIO(text.lstrip("\ufeff"))):
            if (row.get("SERIES_CODE") != f"RER_{currency}_ILS" or row.get("FREQ") != "D"
                    or row.get("BASE_CURRENCY") != currency or row.get("COUNTER_CURRENCY") != "ILS"
                    or row.get("UNIT_MEASURE") != "ILS" or row.get("DATA_TYPE") != "OF00"
                    or row.get("DATA_SOURCE") != "BOI_MRKT"):
                continue
            try:
                day = date.fromisoformat(row["TIME_PERIOD"])
                multiplier = int(row["UNIT_MULT"])
                if not 0 <= multiplier <= 6:
                    raise ValueError
                # BOI's JPY quote is ILS per 100 JPY (UNIT_MULT=2).
                rate = float(row["OBS_VALUE"]) / (10 ** multiplier)
                if not math.isfinite(rate) or rate <= 0:
                    raise ValueError
            except (ValueError, KeyError, TypeError, OverflowError) as exc:
                raise ProviderError("var_fx_refresh_failed") from exc
            if from_date <= day <= to_date:
                if day in rates and rates[day] != rate:
                    raise ProviderError("var_fx_refresh_failed")
                rates[day] = rate
        if not rates:
            raise ProviderError("var_fx_refresh_failed")
        return [{"date": day.isoformat(), "rate": rate} for day, rate in sorted(rates.items())]

    def history(self, currency: str, from_date: date, to_date: date) -> dict[str, Any]:
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency) or currency == "ILS":
            raise ProviderError("var_fx_invalid_currency")
        try:
            with httpx.Client(timeout=25, follow_redirects=True) as client:
                response = client.get(self.base, params={"c[BASE_CURRENCY]": currency, "c[COUNTER_CURRENCY]": "ILS",
                    "c[DATA_TYPE]": "OF00", "format": "csv", "startPeriod": from_date.isoformat(), "endPeriod": to_date.isoformat()})
                response.raise_for_status()
            return {"currency": currency, "source": "Bank of Israel representative rates",
                    "rates": self.parse_history(response.text, currency, from_date, to_date)}
        except Exception as exc:
            raise ProviderError("var_fx_refresh_failed") from exc


class FrankfurterFxProvider(MarketDataProvider):
    name = "frankfurter_fx"
    base = "https://api.frankfurter.dev/v2/rate"

    def _pair_rate(self, src: str, dst: str, day: date | None = None) -> tuple[float | None, str | None]:
        params = {"date": day.isoformat()} if day else {}
        cache_key = f"frankfurter:fx:{src}:{dst}:{day.isoformat() if day else 'latest'}"
        url = f"{self.base}/{src}/{dst}"
        try:
            data = self._get_json(url, params, cache_key)
        except httpx.HTTPError:
            data = self._get_json(url, params, cache_key, force_refresh=True)
        return _float_or_none(data.get("rate")), data.get("date")

    def fx(self, pair: str) -> dict[str, Any]:
        src, dst = pair.upper().split("/", 1)
        current, timestamp = self._pair_rate(src, dst)
        if current is None:
            return {}
        previous = None
        try:
            current_day = date.fromisoformat(str(timestamp)) if timestamp else date.today()
            for offset in range(1, 8):
                candidate_rate, candidate_day = self._pair_rate(src, dst, current_day - timedelta(days=offset))
                if candidate_rate is not None and str(candidate_day or "") < current_day.isoformat():
                    previous = candidate_rate
                    break
        except Exception:
            previous = None
        change = current - previous if current is not None and previous not in (None, 0) else None
        changes_percentage = (change / abs(previous) * 100) if change is not None else None
        return {"pair": f"{src}/{dst}", "rate": current, "time": timestamp, "change": change, "changes_percentage": changes_percentage}


class FmpProvider(MarketDataProvider):
    name = "financial_modeling_prep"
    base = "https://financialmodelingprep.com/stable"

    @property
    def api_key(self) -> str:
        return self.config.get("api_key") or ""

    def _require_key(self):
        if not self.api_key:
            raise ProviderError("missing FMP API key")

    def prices(self, symbol: str, from_date: date, to_date: date) -> list[Ohlcv]:
        self._require_key()

        def fetch(start: date, end: date) -> list[Ohlcv]:
            data = self._get_json(
                f"{self.base}/historical-price-eod/full",
                {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat(), "apikey": self.api_key},
                f"fmp:prices:{symbol}:{start}:{end}",
            )
            rows = data if isinstance(data, list) else data.get("historical", [])
            return sorted(
                [
                    Ohlcv(date=date.fromisoformat(row["date"]), open=float(row["open"]), high=float(row["high"]), low=float(row["low"]), close=float(row["close"]), adjusted_close=float(row.get("adjClose") or row["close"]), volume=float(row.get("volume") or 0))
                    for row in rows
                ],
                key=lambda item: item.date,
            )

        return _cached_or_fetch_prices(self.cache, self.name, symbol, from_date, to_date, fetch)

    def fundamentals(self, symbol: str) -> dict[str, Any]:
        self._require_key()
        income = self._get_json(f"{self.base}/income-statement", {"symbol": symbol, "period": "annual", "limit": 6, "apikey": self.api_key}, f"fmp:income:{symbol}")
        profile = self._get_json(f"{self.base}/profile", {"symbol": symbol, "apikey": self.api_key}, f"fmp:profile:{symbol}")
        return {"income_statement": {"annualReports": income}, "profile": profile[0] if profile else {}}

    def dividends(self, symbol: str, force_refresh: bool = False, to_date: date | None = None) -> list[dict[str, Any]]:
        self._require_key()
        data = self._get_json(f"{self.base}/dividends", {"symbol": symbol, "apikey": self.api_key}, f"fmp:dividends:{symbol}", force_refresh=force_refresh)
        rows = data if isinstance(data, list) else data.get("historical", [])
        normalized = []
        for row in rows:
            item = {"date": row.get("date"), "amount": float(row.get("dividend") or row.get("adjDividend") or 0)}
            if row.get("adjDividend") is not None:
                item["adjusted_amount"] = row["adjDividend"]
            for source, target in (("paymentDate", "payment_date"), ("recordDate", "record_date"), ("declarationDate", "declaration_date")):
                if row.get(source):
                    item[target] = row[source]
            normalized.append(item)
        return normalized

    def profile(self, symbol: str) -> dict[str, Any]:
        self._require_key()
        data = self._get_json(f"{self.base}/profile", {"symbol": symbol, "apikey": self.api_key}, f"fmp:profile:{symbol}")
        profile = data[0] if data else {}
        return {"name": profile.get("companyName"), "industry": profile.get("industry"), "sector": profile.get("sector"), "exchange": profile.get("exchange") or profile.get("exchangeShortName"), "market_cap": _float_or_none(profile.get("mktCap")), "website": profile.get("website"), "logo_url": profile.get("image")}

    def quote(self, symbol: str) -> dict[str, Any]:
        self._require_key()
        data = self._get_json(f"{self.base}/quote", {"symbol": symbol, "apikey": self.api_key}, f"fmp:quote:{symbol}")
        row = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}
        if not row:
            return {}
        return {
            "symbol": row.get("symbol") or symbol,
            "name": row.get("name"),
            "price": _float_or_none(row.get("price")),
            "change": _float_or_none(row.get("change")),
            "changes_percentage": _float_or_none(row.get("changesPercentage")),
            "exchange": row.get("exchange") or row.get("exchangeShortName"),
            "time": row.get("timestamp"),
        }

    def market_screener(self, criteria: dict[str, Any]) -> list[dict[str, Any]]:
        self._require_key()
        query = str(criteria.get("query") or "").strip()
        exchange = str(criteria.get("exchange") or "").strip()
        if query:
            params = {"query": query, "apikey": self.api_key}
            if exchange:
                params["exchange"] = exchange
            data = self._get_json(f"{self.base}/search-symbol", params, f"fmp:search:{query}:{exchange}")
        else:
            params = {
                "limit": int(criteria.get("limit") or 50),
            }
            for source, target in [
                ("exchange", "exchange"),
                ("sector", "sector"),
                ("industry", "industry"),
                ("country", "country"),
                ("marketCapMoreThan", "marketCapMoreThan"),
                ("marketCapLowerThan", "marketCapLowerThan"),
                ("priceMoreThan", "priceMoreThan"),
                ("priceLowerThan", "priceLowerThan"),
                ("betaMoreThan", "betaMoreThan"),
                ("betaLowerThan", "betaLowerThan"),
                ("volumeMoreThan", "volumeMoreThan"),
                ("dividendMoreThan", "dividendMoreThan"),
            ]:
                value = criteria.get(source)
                if value not in (None, ""):
                    params[target] = value
            cache_params = dict(params)
            params["apikey"] = self.api_key
            data = self._get_json(f"{self.base}/company-screener", params, f"fmp:screener:{json.dumps(cache_params, sort_keys=True)}")

        rows = data if isinstance(data, list) else []
        return [
            {
                "symbol": row.get("symbol"),
                "name": row.get("companyName") or row.get("name"),
                "exchange": row.get("exchange") or row.get("exchangeShortName") or exchange,
                "currency": row.get("currency"),
                "price": _float_or_none(row.get("price")),
                "market_cap": _float_or_none(row.get("marketCap")),
                "sector": row.get("sector"),
                "industry": row.get("industry"),
                "country": row.get("country"),
                "beta": _float_or_none(row.get("beta")),
                "volume": _float_or_none(row.get("volume")),
                "dividend": _float_or_none(row.get("lastAnnualDividend") or row.get("dividend")),
            }
            for row in rows
            if row.get("symbol")
        ]


class NasdaqQuoteProvider(MarketDataProvider):
    name = "nasdaq_quote"
    base = "https://api.nasdaq.com/api/quote"

    def _nasdaq_json(self, url: str, params: dict[str, Any], cache_key: str) -> dict[str, Any]:
        cached = self.cache.get(cache_key)
        if isinstance(cached, dict):
            return cached
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; portfolio-analyzer/1.0)",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/",
        }
        with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        if isinstance(payload, dict):
            self.cache.set(cache_key, payload)
            return payload
        return {}

    def quote(self, symbol: str) -> dict[str, Any]:
        normalized = str(symbol or "").upper().strip()
        if not normalized or not all(char.isalnum() or char in ".-" for char in normalized):
            return {}
        payload = self._nasdaq_json(
            f"{self.base}/{normalized}/info",
            {"assetclass": "stocks"},
            f"nasdaq:quote-payload:{normalized}",
        )
        data = payload.get("data") if isinstance(payload, dict) else {}
        primary = data.get("primaryData") if isinstance(data, dict) else {}
        price = _float_or_none(str(primary.get("lastSalePrice") or "").replace("$", "").replace(",", ""))
        if price is None:
            return {}
        result = {
            "symbol": data.get("symbol") or normalized,
            "name": data.get("companyName"),
            "price": price,
            "currency": "USD",
            "change": _float_or_none(str(primary.get("netChange") or "").replace("+", "").replace(",", "")),
            "changes_percentage": _float_or_none(str(primary.get("percentageChange") or "").replace("%", "").replace("+", "").replace(",", "")),
            "exchange": data.get("exchange") or ("NASDAQ" if data.get("isNasdaqListed") else "US"),
            "time": primary.get("lastTradeTimestamp"),
        }
        return result

    def profile(self, symbol: str) -> dict[str, Any]:
        normalized = str(symbol or "").upper().strip()
        if not normalized or not all(char.isalnum() or char in ".-" for char in normalized):
            return {}
        payload = self._nasdaq_json(
            f"https://api.nasdaq.com/api/company/{normalized}/company-profile",
            {},
            f"nasdaq:profile:{normalized}",
        )
        data = payload.get("data") if isinstance(payload, dict) else {}
        if not isinstance(data, dict):
            return {}

        def value(key: str) -> Any:
            field = data.get(key)
            return field.get("value") if isinstance(field, dict) else field

        return {
            "name": value("CompanyName"),
            "industry": value("Industry"),
            "sector": value("Sector"),
            "website": value("CompanyUrl"),
        }


class StooqProvider(MarketDataProvider):
    name = "stooq"

    def prices(self, symbol: str, from_date: date, to_date: date) -> list[Ohlcv]:
        def fetch(start: date, end: date) -> list[Ohlcv]:
            cache_key = f"stooq:prices:{symbol}:{start}:{end}"
            cached = self.cache.get(cache_key)
            if cached is not None:
                return [_ohlcv_from_dict(row) for row in cached]
            stooq_symbol = symbol.lower()
            url = f"https://stooq.com/q/d/l/?s={stooq_symbol}.us&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d"
            with httpx.Client(timeout=20, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
            rows = []
            for row in csv.DictReader(response.text.splitlines()):
                if row.get("Close") and row.get("Close") != "N/D":
                    rows.append(
                        Ohlcv(
                            date=date.fromisoformat(row["Date"]),
                            open=float(row["Open"]),
                            high=float(row["High"]),
                            low=float(row["Low"]),
                            close=float(row["Close"]),
                            adjusted_close=float(row["Close"]),
                            volume=float(row.get("Volume") or 0),
                        )
                    )
            self.cache.set(cache_key, [item.__dict__ for item in rows])
            return rows

        return _cached_or_fetch_prices(self.cache, self.name, symbol, from_date, to_date, fetch)

    def quote(self, symbol: str) -> dict[str, Any]:
        prices = self.prices(symbol, date.today() - timedelta(days=14), date.today())
        if not prices:
            return {}
        latest = prices[-1]
        return {
            "symbol": symbol.upper(),
            "price": latest.close,
            "currency": "USD",
            "exchange": "US",
            "time": latest.date.isoformat(),
        }


class SecCompanyTickerProvider(MarketDataProvider):
    name = "sec_company_tickers"
    base = "https://www.sec.gov/files/company_tickers.json"

    def market_screener(self, criteria: dict[str, Any]) -> list[dict[str, Any]]:
        query = str(criteria.get("query") or "").strip().upper()
        if not query:
            return []
        limit = int(criteria.get("limit") or 50)
        cache_key = "sec:company-tickers"
        data = self.cache.get(cache_key, require_fresh=True)
        if not _valid_sec_tickers(data):
            headers = {"User-Agent": "portfolio-analyzer/1.0 contact@example.local", "Accept": "application/json"}
            with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
                response = client.get(self.base)
                response.raise_for_status()
                data = response.json()
            if not _valid_sec_tickers(data):
                raise ProviderError("SEC ticker data unavailable")
            self.cache.set(cache_key, data)
        rows = data.values() if isinstance(data, dict) else data
        matches = []
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            name = str(row.get("title") or "")
            if ticker == query or ticker.startswith(query) or query in name.upper():
                matches.append(
                    {
                        "symbol": ticker,
                        "name": name,
                        "exchange": "SEC",
                        "currency": "USD",
                        "price": None,
                        "market_cap": None,
                        "sector": None,
                        "industry": None,
                        "beta": None,
                        "dividend": None,
                    }
                )
            if len(matches) >= limit:
                break
        return matches


class SecCompanyFactsProvider(MarketDataProvider):
    name = "sec_company_facts"
    tickers_url = "https://www.sec.gov/files/company_tickers.json"

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": "portfolio-analyzer/1.0 contact@example.local", "Accept": "application/json"}

    def _ticker_row(self, symbol: str) -> dict[str, Any]:
        cache_key = "sec:company-tickers"
        data = self.cache.get(cache_key, require_fresh=True)
        if not _valid_sec_tickers(data):
            with httpx.Client(timeout=20, follow_redirects=True, headers=self._headers()) as client:
                response = client.get(self.tickers_url)
                response.raise_for_status()
                data = response.json()
            if not _valid_sec_tickers(data):
                raise ProviderError("SEC ticker data unavailable")
            self.cache.set(cache_key, data)
        rows = data.values() if isinstance(data, dict) else data
        target = symbol.upper()
        for row in rows:
            if str(row.get("ticker") or "").upper() == target:
                cik = str(row.get("cik_str") or "").zfill(10)
                return {**row, "cik": cik}
        return {}

    def fundamentals(self, symbol: str) -> dict[str, Any]:
        return self._fundamentals(symbol)

    def fundamentals_as_of(self, symbol: str, as_of: date) -> dict[str, Any]:
        return self._fundamentals(symbol, as_of)

    def _fundamentals(self, symbol: str, as_of: date | None = None) -> dict[str, Any]:
        ticker = self._ticker_row(symbol)
        cik = ticker.get("cik")
        if not cik:
            return {}
        facts = self._company_facts(cik)
        data = self._fundamentals_from_facts(facts, self.profile(symbol), as_of)
        return data if data["income_statement"]["annualReports"] else {}

    def cached_fundamentals(self, symbol: str, as_of: date | None = None) -> dict[str, Any]:
        """Rebuild a requested cutoff from retained evidence after a failed refresh."""
        tickers = self.cache.get("sec:company-tickers") or {}
        if not _valid_sec_tickers(tickers):
            return {}
        rows = tickers.values() if isinstance(tickers, dict) else tickers
        ticker = next((row for row in rows if str(row.get("ticker") or "").upper() == symbol.upper()), {})
        cik = str(ticker.get("cik_str") or "").zfill(10)
        facts = self.cache.get(f"sec:companyfacts:{cik}")
        if not ticker or not _valid_sec_company_facts(facts):
            return {}
        profile = self.cache.get_security_snapshot(self.name, symbol, "profile") or {"name": ticker.get("title")}
        data = self._fundamentals_from_facts(facts, profile, as_of)
        return data if data["income_statement"]["annualReports"] else {}

    def _fundamentals_from_facts(self, facts: dict[str, Any], profile: dict[str, Any], as_of: date | None) -> dict[str, Any]:
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        revenue = _sec_annual_facts(
            us_gaap,
            [
                "Revenues",
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "SalesRevenueNet",
                "GrossInvestmentIncomeOperating",
                "InvestmentIncomeNet",
            ],
            as_of,
        )
        financial_revenue = _sec_financial_revenue(us_gaap, as_of)
        for period_end, row in financial_revenue.items():
            revenue.setdefault(period_end, row)
        net_income = _sec_annual_facts(us_gaap, ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"], as_of)
        gross_profit = _sec_annual_facts(us_gaap, ["GrossProfit"], as_of)
        operating_income = _sec_annual_facts(us_gaap, ["OperatingIncomeLoss"], as_of)
        operating_cash_flow = _sec_annual_facts(us_gaap, ["NetCashProvidedByUsedInOperatingActivities"], as_of)
        capital_expenditures = _sec_annual_facts(us_gaap, ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"], as_of)
        cash = _sec_annual_facts(us_gaap, ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"], as_of, instant=True)
        current_assets = _sec_annual_facts(us_gaap, ["AssetsCurrent"], as_of, instant=True)
        current_liabilities = _sec_annual_facts(us_gaap, ["LiabilitiesCurrent"], as_of, instant=True)
        accounts_receivable = _sec_annual_facts(us_gaap, ["AccountsReceivableNetCurrent", "AccountsNotesAndLoansReceivableNetCurrent"], as_of, instant=True)
        inventory = _sec_annual_facts(us_gaap, ["InventoryNet", "InventoryFinishedGoodsNetOfReserves"], as_of, instant=True)
        long_term_debt = _sec_long_term_debt(us_gaap, as_of)
        interest_expense = _sec_annual_facts(us_gaap, ["InterestExpenseNonoperating", "InterestExpenseDebt"], as_of)
        reports_by_period: dict[str, dict[str, Any]] = {}
        # Only an observed annual income period establishes an annual report.
        # Standalone interim balance-sheet facts must not create extra years.
        for period_end in sorted(set(revenue) | set(net_income)):
            anchor = revenue.get(period_end) or net_income[period_end]
            reports_by_period[period_end] = {"fiscalDateEnding": period_end, "periodStart": anchor["start"]}
        for field, rows in [
            ("totalRevenue", revenue),
            ("netIncome", net_income),
            ("grossProfit", gross_profit),
            ("operatingIncome", operating_income),
            ("operatingCashFlow", operating_cash_flow),
            ("capitalExpenditures", capital_expenditures),
            ("cashAndCashEquivalents", cash),
            ("totalCurrentAssets", current_assets),
            ("totalCurrentLiabilities", current_liabilities),
            ("netReceivables", accounts_receivable),
            ("inventory", inventory),
            ("longTermDebt", long_term_debt),
            ("interestExpense", interest_expense),
        ]:
            for period_end, row in rows.items():
                report = reports_by_period.get(period_end)
                if report is None or (row.get("start") and row["start"] != report["periodStart"]):
                    continue
                report[field] = row["val"]
                if row.get("filed") and str(row["filed"]) > str(report.get("filingDate") or ""):
                    report["filingDate"] = row["filed"]
        reports = [reports_by_period[period_end] for period_end in sorted(reports_by_period)]
        return {"income_statement": {"annualReports": reports}, "profile": profile,
                "fundamentals_parser_version": SEC_FUNDAMENTALS_PARSER_VERSION}

    def profile(self, symbol: str) -> dict[str, Any]:
        ticker = self._ticker_row(symbol)
        if not ticker:
            return {}
        profile = {"name": ticker.get("title")}
        cik = ticker.get("cik")
        if cik:
            try:
                metadata = self._company_submissions(cik)
            except (httpx.HTTPError, ValueError):
                metadata = {}
            profile.update({key: value for key, value in {
                "industry": metadata.get("sicDescription"),
                "sic": metadata.get("sic"),
                "exchange": next(iter(metadata.get("exchanges") or []), None),
                "profile_source": f"https://data.sec.gov/submissions/CIK{cik}.json",
            }.items() if value})
            facts = self._company_facts(cik)
            us_gaap = facts.get("facts", {}).get("dei", {})
            shares = _sec_latest_fact(us_gaap, ["EntityCommonStockSharesOutstanding"], ["shares"])
            if shares is not None:
                profile["shares_outstanding"] = shares
        return profile

    def _company_submissions(self, cik: str) -> dict[str, Any]:
        cache_key = f"sec:submissions:{cik}"
        cached = self.cache.get(cache_key)
        if isinstance(cached, dict):
            return cached
        with httpx.Client(timeout=20, follow_redirects=True, headers=self._headers()) as client:
            response = client.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
            response.raise_for_status()
            data = response.json()
        self.cache.set(cache_key, data)
        return data

    def market_screener(self, criteria: dict[str, Any]) -> list[dict[str, Any]]:
        sic = str(criteria.get("sic") or "")
        if not sic.isdigit() or len(sic) != 4:
            return []
        cache_key = f"sec:industry-cohort:{sic}"
        rows = self.cache.get(cache_key)
        if rows is None:
            with httpx.Client(timeout=20, follow_redirects=True, headers=self._headers()) as client:
                response = client.get("https://www.sec.gov/cgi-bin/browse-edgar", params={
                    "action": "getcompany", "SIC": sic, "owner": "exclude", "count": 100, "output": "atom",
                })
                response.raise_for_status()
            root = ET.fromstring(response.content)
            ciks = {node.text.zfill(10) for node in root.findall(".//{*}company-info/{*}cik") if node.text}
            # Resolve only exchange-listed tickers; private filers are not peers.
            self._ticker_row(str(criteria.get("exclude_symbol") or ""))
            tickers = self.cache.get("sec:company-tickers") or {}
            rows = [{"symbol": item["ticker"], "name": item.get("title"),
                     "industry": criteria.get("industry"), "sic": sic}
                    for item in (tickers.values() if isinstance(tickers, dict) else tickers)
                    if str(item.get("cik_str") or "").zfill(10) in ciks]
            self.cache.set(cache_key, rows)
        excluded = str(criteria.get("exclude_symbol") or "").upper()
        return [row for row in rows if row["symbol"] != excluded][:int(criteria.get("limit") or 6)]

    def _company_facts(self, cik: str) -> dict[str, Any]:
        cache_key = f"sec:companyfacts:{cik}"
        cached = self.cache.get(cache_key, require_fresh=True)
        if _valid_sec_company_facts(cached):
            return cached
        with httpx.Client(timeout=20, follow_redirects=True, headers=self._headers()) as client:
            response = client.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
            response.raise_for_status()
            data = response.json()
        if not _valid_sec_company_facts(data):
            raise ProviderError("SEC company facts unavailable")
        self.cache.set(cache_key, data)
        return data


class ExternalImportMarketDataProvider(MarketDataProvider):
    name = "external_import_market_data"

    def __init__(self, db_config: dict[str, Any], cache: SqliteCache):
        super().__init__({}, cache)
        self.db_config = db_config

    def _connect(self):
        if not self.db_config.get("host"):
            raise ProviderError("missing external import DB config")
        return connect_postgres(self.db_config)

    def prices(self, symbol: str, from_date: date, to_date: date) -> list[Ohlcv]:
        def fetch(start: date, end: date) -> list[Ohlcv]:
            cache_key = f"external_import:prices:{symbol}:{start}:{end}"
            cached = self.cache.get(cache_key)
            if cached is not None:
                return [_ohlcv_from_dict(row) for row in cached]
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    select date, "marketPrice"
                    from "MarketData"
                    where upper(symbol) = upper(%s)
                      and date >= %s
                      and date <= %s
                      and "marketPrice" is not null
                    order by date
                    """,
                    (symbol, start, end),
                ).fetchall()
            prices = []
            for row in rows:
                day = row["date"].date() if hasattr(row["date"], "date") else row["date"]
                price = float(row["marketPrice"])
                prices.append(Ohlcv(date=day, open=price, high=price, low=price, close=price, adjusted_close=price, volume=0))
            self.cache.set(cache_key, [item.__dict__ for item in prices])
            return prices

        return _cached_or_fetch_prices(self.cache, self.name, symbol, from_date, to_date, fetch)

    def dividends(self, symbol: str, force_refresh: bool = False, to_date: date | None = None) -> list[dict[str, Any]]:
        return []

    def profile(self, symbol: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select name, sectors
                from "SymbolProfile"
                where upper(symbol) = upper(%s)
                limit 1
                """,
                (symbol,),
            ).fetchone()
        if not row:
            return {}
        sector = ""
        sectors = row.get("sectors")
        if isinstance(sectors, list) and sectors:
            sector = str(sectors[0].get("name") or "")
        return {"name": row.get("name"), "sector": sector}

    def fx(self, pair: str) -> dict[str, Any]:
        symbol = pair.replace("/", "").upper()
        with self._connect() as conn:
            row = conn.execute(
                """
                select date, "marketPrice"
                from "MarketData"
                where upper(symbol) in (upper(%s), upper(%s))
                  and "marketPrice" is not null
                order by date desc
                limit 1
                """,
                (symbol, f"{symbol}=X"),
            ).fetchone()
        if not row:
            return {}
        return {"pair": pair, "rate": float(row["marketPrice"]), "time": row["date"].isoformat()}

    def quote(self, symbol: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select date, "marketPrice"
                from "MarketData"
                where upper(symbol) = upper(%s)
                  and "marketPrice" is not null
                order by date desc
                limit 1
                """,
                (symbol,),
            ).fetchone()
        if not row:
            return {}
        return {"symbol": symbol, "price": float(row["marketPrice"]), "time": row["date"].isoformat()}


class YahooChartProvider(MarketDataProvider):
    name = "yahoo_finance"

    def __init__(self, config: dict[str, Any], cache: SqliteCache):
        super().__init__(config, cache)
        self._summary_unauthorized = False

    @staticmethod
    def _price_factor(result: dict[str, Any]) -> float:
        currency = str((result.get("meta") or {}).get("currency") or "").upper()
        return 0.01 if currency == "ILA" else 1.0

    def _refresh_slot(self, symbol: str, data_type: str) -> bool:
        """Allow one first-use refresh and one 23:20 Israel refresh per day."""
        now = datetime.now(ZoneInfo("Asia/Jerusalem"))
        slot = "scheduled" if (now.hour, now.minute) >= (23, 20) else "first-use"
        key = f"yahoo:refresh-window:{now.date().isoformat()}:{slot}:{data_type}:{symbol.upper()}"
        if self.cache.get(key) is not None:
            return False
        self.cache.set(key, True)
        return True

    def _summary(self, symbol: str) -> dict[str, Any]:
        if self._summary_unauthorized:
            return {}
        saved = self.cache.get_security_snapshot(self.name, symbol, "summary")
        if not self._refresh_slot(symbol, "summary"):
            return saved if isinstance(saved, dict) else {}
        try:
            data = self._get_json(
                f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}",
                {"modules": "incomeStatementHistory,assetProfile,price,summaryDetail"},
                f"yahoo:summary:{symbol}",
                force_refresh=True,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                self._summary_unauthorized = True
            raise
        result = (data.get("quoteSummary", {}).get("result") or [{}])[0]
        result = result if isinstance(result, dict) else {}
        self.cache.set_security_snapshot(self.name, symbol, "summary", result)
        return result

    def prices(self, symbol: str, from_date: date, to_date: date) -> list[Ohlcv]:
        cached = self.cache.get_prices(self.name, symbol, from_date, to_date)
        if not self._refresh_slot(symbol, "prices"):
            return cached

        def fetch(start: date, end: date) -> list[Ohlcv]:
            cache_key = f"yahoo:prices:{symbol}:{start}:{end}"
            cached = self.cache.get(cache_key)
            if cached is not None:
                return [_ohlcv_from_dict(row) for row in cached]
            period1 = int(time.mktime(start.timetuple()))
            period2 = int(time.mktime((end + timedelta(days=1)).timetuple()))
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            data = self._get_json(url, {"period1": period1, "period2": period2, "interval": "1d", "events": "div"}, cache_key)
            result = (data.get("chart", {}).get("result") or [{}])[0]
            price_factor = self._price_factor(result)
            timestamps = result.get("timestamp") or []
            quote = (result.get("indicators", {}).get("quote") or [{}])[0]
            adj = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose") or quote.get("close") or []
            rows = []
            for idx, ts in enumerate(timestamps):
                close = _at(quote.get("close"), idx)
                if close is None:
                    continue
                rows.append(
                    Ohlcv(
                        date=date.fromtimestamp(ts),
                        open=float(_at(quote.get("open"), idx) or close) * price_factor,
                        high=float(_at(quote.get("high"), idx) or close) * price_factor,
                        low=float(_at(quote.get("low"), idx) or close) * price_factor,
                        close=float(close) * price_factor,
                        adjusted_close=float(_at(adj, idx) or close) * price_factor,
                        volume=float(_at(quote.get("volume"), idx) or 0),
                    )
                )
            self.cache.set(cache_key, [item.__dict__ for item in rows])
            return rows

        return _cached_or_fetch_prices(self.cache, self.name, symbol, from_date, to_date, fetch)

    def dividends(self, symbol: str, force_refresh: bool = False, to_date: date | None = None) -> list[dict[str, Any]]:
        cache_key = f"yahoo:dividends:{symbol}"
        cached = self.cache.get(cache_key) if not force_refresh else None
        if cached is not None:
            return cached
        to_date = to_date or date.today()
        from_date = to_date - timedelta(days=366 * 10)
        period1 = int(time.mktime(from_date.timetuple()))
        period2 = int(time.mktime((to_date + timedelta(days=1)).timetuple()))
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        data = self._get_json(url, {"period1": period1, "period2": period2, "interval": "1d", "events": "div"}, f"yahoo:chart:div:{symbol}", force_refresh=force_refresh)
        result = (data.get("chart", {}).get("result") or [{}])[0]
        price_factor = self._price_factor(result)
        dividends = result.get("events", {}).get("dividends", {})
        rows = [
            {"date": date.fromtimestamp(item["date"]).isoformat(), "amount": float(item.get("amount") or 0) * price_factor}
            for item in dividends.values()
            if item.get("date") and item.get("amount")
        ]
        rows.sort(key=lambda item: item["date"])
        self.cache.set(cache_key, rows)
        return rows

    def fundamentals(self, symbol: str) -> dict[str, Any]:
        summary = self._summary(symbol)
        income_rows = summary.get("incomeStatementHistory", {}).get("incomeStatementHistory") or []
        reports = []
        for row in income_rows:
            fiscal_date = row.get("endDate", {}).get("fmt") or row.get("endDate", {}).get("raw")
            revenue = _yahoo_raw(row.get("totalRevenue"))
            net_income = _yahoo_raw(row.get("netIncome"))
            if fiscal_date and (revenue is not None or net_income is not None):
                reports.append({"fiscalDateEnding": str(fiscal_date), "totalRevenue": revenue, "netIncome": net_income})
        return {"income_statement": {"annualReports": reports}, "profile": self.profile(symbol)}

    def profile(self, symbol: str) -> dict[str, Any]:
        summary = self._summary(symbol)
        asset = summary.get("assetProfile") or {}
        price = summary.get("price") or {}
        currency = str(_yahoo_value(price.get("currency")) or "").upper()
        return {
            "name": _yahoo_value(price.get("longName")) or _yahoo_value(price.get("shortName")),
            "industry": asset.get("industry"),
            "sector": asset.get("sector"),
            "website": asset.get("website"),
            "exchange": _yahoo_value(price.get("exchangeName")) or _yahoo_value(price.get("fullExchangeName")) or _yahoo_value(price.get("exchange")),
            "currency": "ILS" if currency == "ILA" else currency,
            "market_cap": _yahoo_raw(price.get("marketCap")),
        }


class UnsupportedProvider(MarketDataProvider):
    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message

    def prices(self, symbol: str, from_date: date, to_date: date) -> list[Ohlcv]:
        raise ProviderError(self.message)


def _float_or_none(value: Any) -> float | None:
    try:
        if isinstance(value, bool) or value in (None, "", "None"):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _price_score(prices: list[Ohlcv], from_date: date, to_date: date) -> tuple[int, int, int]:
    if not prices:
        return (0, 0, 0)
    sorted_prices = sorted(prices, key=lambda item: item.date)
    starts_near_request = int(sorted_prices[0].date <= from_date + timedelta(days=14))
    ends_near_request = int(sorted_prices[-1].date >= to_date - timedelta(days=7))
    return (len(sorted_prices), starts_near_request, ends_near_request)


def _persistent_cache_key(key: str) -> bool:
    return any(key.startswith(prefix) for prefix in PERSISTENT_CACHE_PREFIXES)


def _valid_sec_tickers(data: Any) -> bool:
    if not isinstance(data, (dict, list)) or not data:
        return False
    rows = data.values() if isinstance(data, dict) else data
    return all(isinstance(row, dict) and isinstance(row.get("ticker"), str) and row["ticker"].strip()
               and str(row.get("cik_str") or "").isdigit() for row in rows)


def _valid_sec_company_facts(data: Any) -> bool:
    facts = data.get("facts") if isinstance(data, dict) else None
    if not isinstance(facts, dict) or not facts or not any(facts.values()):
        return False
    for taxonomy in facts.values():
        if not isinstance(taxonomy, dict):
            return False
        for fact in taxonomy.values():
            units = fact.get("units") if isinstance(fact, dict) else None
            if not isinstance(units, dict):
                return False
            if any(not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows) for rows in units.values()):
                return False
    return True


def _yahoo_raw(value: Any) -> float | None:
    if isinstance(value, dict):
        return _float_or_none(value.get("raw"))
    return _float_or_none(value)


def _yahoo_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("fmt") or value.get("longFmt") or value.get("raw")
    return value


def _provider_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _sec_fact_rows(
    us_gaap: dict[str, Any], concepts: list[str], as_of: date | None = None, *, instant: bool = False,
) -> list[dict[str, Any]]:
    """Return valid monetary facts with their actual period and filing context."""
    selected = []
    for priority, concept in enumerate(concepts):
        units = us_gaap.get(concept, {}).get("units", {})
        for row in units.get("USD") or units.get("usd") or []:
            if row.get("fp") != "FY" or row.get("form") not in {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}:
                continue
            filed = _provider_date(row.get("filed"))
            end = _provider_date(row.get("end"))
            if not filed or not end or filed < end or (as_of and filed > as_of):
                continue
            start = _provider_date(row.get("start"))
            if instant:
                if row.get("start") not in (None, ""):
                    continue
            elif not start or not 335 <= (end - start).days + 1 <= 395:
                # A fact in an annual filing may cover a quarter, a transition
                # period, or several years. FY alone does not prove duration.
                continue
            value = _float_or_none(row.get("val"))
            if value is None:
                continue
            selected.append({"val": value, "start": start.isoformat() if start else None,
                             "end": end.isoformat(), "filed": filed.isoformat(),
                             "concept": concept, "accn": str(row.get("accn") or ""), "priority": priority})
    return selected


def _sec_annual_facts(
    us_gaap: dict[str, Any], concepts: list[str], as_of: date | None = None, *, instant: bool = False,
) -> dict[str, dict[str, Any]]:
    by_period: dict[str, dict[str, Any]] = {}
    for row in _sec_fact_rows(us_gaap, concepts, as_of, instant=instant):
        existing = by_period.get(row["end"])
        selection = (row["filed"], -row["priority"], row["accn"])
        previous = (existing["filed"], -existing["priority"], existing["accn"]) if existing else None
        if previous is None or selection > previous:
            by_period[row["end"]] = row
    return by_period


def _sec_matched_components(
    us_gaap: dict[str, Any], left_concepts: list[str], right_concepts: list[str],
    as_of: date | None = None, *, instant: bool = False, nonnegative: bool = False,
) -> dict[str, dict[str, Any]]:
    """Combine only observations from one period and filing, retaining revisions."""
    sides = []
    for concepts in (left_concepts, right_concepts):
        side = {}
        for row in _sec_fact_rows(us_gaap, concepts, as_of, instant=instant):
            key = (row["start"], row["end"], row["filed"], row["accn"])
            if key not in side or row["priority"] < side[key]["priority"]:
                side[key] = row
        sides.append(side)
    combined: dict[str, dict[str, Any]] = {}
    for key in sides[0].keys() & sides[1].keys():
        left, right = sides[0][key], sides[1][key]
        if nonnegative and (left["val"] < 0 or right["val"] < 0):
            continue
        total = _float_or_none(left["val"] + right["val"])
        if total is None:
            continue
        candidate = {**left, "val": total, "concept": left["concept"] + "+" + right["concept"]}
        existing = combined.get(left["end"])
        if existing is None or (candidate["filed"], candidate["accn"]) > (existing["filed"], existing["accn"]):
            combined[left["end"]] = candidate
    return combined


def _sec_long_term_debt(us_gaap: dict[str, Any], as_of: date | None = None) -> dict[str, dict[str, Any]]:
    # LongTermDebt includes current and noncurrent maturities. Do not add
    # components to that total, or substitute only the current maturities.
    totals = _sec_annual_facts(us_gaap, ["LongTermDebt"], as_of, instant=True)
    components = _sec_matched_components(us_gaap, ["LongTermDebtCurrent"], ["LongTermDebtNoncurrent"], as_of, instant=True, nonnegative=True)
    for period_end, candidate in components.items():
        existing = totals.get(period_end)
        if existing is None or candidate["filed"] > existing["filed"]:
            totals[period_end] = candidate
    return {period_end: row for period_end, row in totals.items() if row["val"] >= 0}


def _sec_financial_revenue(us_gaap: dict[str, Any], as_of: date | None = None) -> dict[str, dict[str, Any]]:
    """Build reported annual bank income only from matched financial components."""
    return _sec_matched_components(
        us_gaap, ["InterestIncomeExpenseNet"], ["NoninterestIncome", "NonoperatingIncomeExpense"], as_of,
    )


def _sec_latest_fact(facts: dict[str, Any], concepts: list[str], unit_names: list[str]) -> float | None:
    latest: dict[str, Any] | None = None
    for concept in concepts:
        units = facts.get(concept, {}).get("units", {})
        for unit_name in unit_names:
            for row in units.get(unit_name, []) or []:
                value = _float_or_none(row.get("val"))
                if value is None:
                    continue
                if latest and str(latest.get("filed") or latest.get("end") or "") >= str(row.get("filed") or row.get("end") or ""):
                    continue
                latest = row
    return _float_or_none(latest.get("val")) if latest else None


def _at(values, idx):
    if not values or idx >= len(values):
        return None
    return values[idx]


def _ohlcv_from_dict(row: dict[str, Any]) -> Ohlcv:
    return Ohlcv(
        date=date.fromisoformat(str(row["date"])),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        adjusted_close=float(row["adjusted_close"]),
        volume=float(row["volume"]),
    )


def _ohlcv_from_tuple(row) -> Ohlcv:
    return Ohlcv(
        date=date.fromisoformat(str(row[0])),
        open=float(row[1]),
        high=float(row[2]),
        low=float(row[3]),
        close=float(row[4]),
        adjusted_close=float(row[5]),
        volume=float(row[6]),
    )
