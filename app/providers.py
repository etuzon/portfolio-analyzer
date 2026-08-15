from __future__ import annotations

import csv
import json
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

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
                saved = self.cache.get_security_snapshot(provider.name, provider_symbol, "fundamentals")
                provider_saved = provider_saved or saved
                try:
                    data = provider.fundamentals(provider_symbol)
                except Exception as exc:
                    errors.append(exc)
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
                saved = self.cache.get_security_snapshot(provider.name, provider_symbol, data_type)
                provider_saved = provider_saved or saved
                try:
                    data = provider.fundamentals_as_of(provider_symbol, as_of)
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

    def get(self, key: str) -> Any | None:
        with self._connect() as conn:
            row = conn.execute("select created_at, value from cache where key = ?", (key,)).fetchone()
            if not row:
                return None
            created_at, value = row
            if not _persistent_cache_key(key) and time.time() - float(created_at) > self.ttl_seconds:
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

    def status(self) -> dict[str, Any]:
        size = self.path.stat().st_size if self.path.exists() else 0
        with self._connect() as conn:
            rows = conn.execute("select count(*) from cache").fetchone()[0]
            price_rows = conn.execute("select count(*) from price_cache").fetchone()[0]
            security_snapshots = conn.execute("select count(*) from security_snapshot").fetchone()[0]
            security_symbols = conn.execute("select count(distinct symbol) from security_snapshot").fetchone()[0]
        return {
            "path": str(self.path),
            "entries": rows,
            "price_entries": price_rows,
            "security_snapshots": security_snapshots,
            "security_symbols": security_symbols,
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
        return {"name": overview.get("Name"), "industry": overview.get("Industry"), "sector": overview.get("Sector"), "exchange": overview.get("Exchange"), "market_cap": _float_or_none(overview.get("MarketCapitalization"))}

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
        return [{"date": row.get("date"), "amount": float(row.get("dividend") or row.get("adjDividend") or 0)} for row in rows]

    def profile(self, symbol: str) -> dict[str, Any]:
        self._require_key()
        data = self._get_json(f"{self.base}/profile", {"symbol": symbol, "apikey": self.api_key}, f"fmp:profile:{symbol}")
        profile = data[0] if data else {}
        return {"name": profile.get("companyName"), "industry": profile.get("industry"), "sector": profile.get("sector"), "exchange": profile.get("exchange") or profile.get("exchangeShortName"), "market_cap": _float_or_none(profile.get("mktCap"))}

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

    def quote(self, symbol: str) -> dict[str, Any]:
        normalized = str(symbol or "").upper().strip()
        if not normalized or not all(char.isalnum() or char in ".-" for char in normalized):
            return {}
        cache_key = f"nasdaq:quote:{normalized}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; portfolio-analyzer/1.0)",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/",
        }
        with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
            response = client.get(f"{self.base}/{normalized}/info", params={"assetclass": "stocks"})
            response.raise_for_status()
            payload = response.json()
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
        self.cache.set(cache_key, result)
        return result


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
        data = self.cache.get(cache_key)
        if data is None:
            headers = {"User-Agent": "portfolio-analyzer/1.0 contact@example.local", "Accept": "application/json"}
            with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
                response = client.get(self.base)
                response.raise_for_status()
                data = response.json()
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
        data = self.cache.get(cache_key)
        if data is None:
            with httpx.Client(timeout=20, follow_redirects=True, headers=self._headers()) as client:
                response = client.get(self.tickers_url)
                response.raise_for_status()
                data = response.json()
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
        net_income = _sec_annual_facts(us_gaap, ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"], as_of)
        gross_profit = _sec_annual_facts(us_gaap, ["GrossProfit"], as_of)
        operating_income = _sec_annual_facts(us_gaap, ["OperatingIncomeLoss"], as_of)
        operating_cash_flow = _sec_annual_facts(us_gaap, ["NetCashProvidedByUsedInOperatingActivities"], as_of)
        capital_expenditures = _sec_annual_facts(us_gaap, ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"], as_of)
        cash = _sec_annual_facts(us_gaap, ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"], as_of)
        current_assets = _sec_annual_facts(us_gaap, ["AssetsCurrent"], as_of)
        current_liabilities = _sec_annual_facts(us_gaap, ["LiabilitiesCurrent"], as_of)
        accounts_receivable = _sec_annual_facts(us_gaap, ["AccountsReceivableNetCurrent", "AccountsNotesAndLoansReceivableNetCurrent"], as_of)
        inventory = _sec_annual_facts(us_gaap, ["InventoryNet", "InventoryFinishedGoodsNetOfReserves"], as_of)
        long_term_debt = _sec_annual_facts(us_gaap, ["LongTermDebtCurrent", "LongTermDebtNoncurrent", "LongTermDebt"], as_of)
        interest_expense = _sec_annual_facts(us_gaap, ["InterestExpenseNonoperating", "InterestExpenseDebt"], as_of)
        reports_by_year: dict[int, dict[str, Any]] = {}
        for year, row in revenue.items():
            report = reports_by_year.setdefault(year, {"fiscalDateEnding": row.get("end") or str(year)})
            report["totalRevenue"] = row["val"]
            if row.get("filed"):
                report["filingDate"] = row["filed"]
        for year, row in net_income.items():
            report = reports_by_year.setdefault(year, {"fiscalDateEnding": row.get("end") or str(year)})
            report["netIncome"] = row["val"]
            if row.get("end"):
                report["fiscalDateEnding"] = row["end"]
            if row.get("filed") and str(row["filed"]) > str(report.get("filingDate") or ""):
                report["filingDate"] = row["filed"]
        for field, rows in [
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
            for year, row in rows.items():
                report = reports_by_year.setdefault(year, {"fiscalDateEnding": row.get("end") or str(year)})
                report[field] = row["val"]
                if row.get("end"):
                    report["fiscalDateEnding"] = row["end"]
                if row.get("filed") and str(row["filed"]) > str(report.get("filingDate") or ""):
                    report["filingDate"] = row["filed"]
        reports = [reports_by_year[year] for year in sorted(reports_by_year)]
        return {"income_statement": {"annualReports": reports}, "profile": self.profile(symbol)}

    def profile(self, symbol: str) -> dict[str, Any]:
        ticker = self._ticker_row(symbol)
        if not ticker:
            return {}
        profile = {"name": ticker.get("title")}
        cik = ticker.get("cik")
        if cik:
            facts = self._company_facts(cik)
            us_gaap = facts.get("facts", {}).get("dei", {})
            shares = _sec_latest_fact(us_gaap, ["EntityCommonStockSharesOutstanding"], ["shares"])
            if shares is not None:
                profile["shares_outstanding"] = shares
        return profile

    def _company_facts(self, cik: str) -> dict[str, Any]:
        cache_key = f"sec:companyfacts:{cik}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        with httpx.Client(timeout=20, follow_redirects=True, headers=self._headers()) as client:
            response = client.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
            response.raise_for_status()
            data = response.json()
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

    @staticmethod
    def _price_factor(result: dict[str, Any]) -> float:
        currency = str((result.get("meta") or {}).get("currency") or "").upper()
        return 0.01 if currency == "ILA" else 1.0

    def _summary(self, symbol: str) -> dict[str, Any]:
        data = self._get_json(
            f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}",
            {"modules": "incomeStatementHistory,assetProfile,price,summaryDetail"},
            f"yahoo:summary:{symbol}",
        )
        result = (data.get("quoteSummary", {}).get("result") or [{}])[0]
        return result if isinstance(result, dict) else {}

    def prices(self, symbol: str, from_date: date, to_date: date) -> list[Ohlcv]:
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
        if value in (None, "", "None"):
            return None
        return float(value)
    except (TypeError, ValueError):
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


def _sec_annual_facts(us_gaap: dict[str, Any], concepts: list[str], as_of: date | None = None) -> dict[int, dict[str, Any]]:
    by_year: dict[int, dict[str, Any]] = {}
    for concept in concepts:
        units = us_gaap.get(concept, {}).get("units", {})
        rows = units.get("USD") or units.get("usd") or []
        for row in rows:
            if row.get("fp") != "FY" or row.get("form") not in {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}:
                continue
            filed = _provider_date(row.get("filed"))
            if as_of and (not filed or filed > as_of):
                continue
            end = _provider_date(row.get("end"))
            year = end.year if end else row.get("fy")
            value = _float_or_none(row.get("val"))
            if not year or value is None:
                continue
            year = int(year)
            existing = by_year.get(year)
            if existing and str(existing.get("filed") or "") >= str(row.get("filed") or ""):
                continue
            by_year[year] = {"val": value, "end": row.get("end"), "filed": row.get("filed"), "concept": concept}
    return by_year


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
