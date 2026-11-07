"""Automatic, identity-qualified US bond/fund research without portfolio edits."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import re
from typing import Annotated, Any, Callable, Literal

from fastapi import APIRouter, HTTPException, Query

from .security_prices import PriceRoute, price_day
from .security_identifiers import valid_cusip, valid_isin


KINDS = Literal["bond", "fund", "etf"]
IDENTIFIER_TYPES = Literal["auto", "cusip", "isin", "ticker"]
PROVIDERS = Literal["auto", "finnhub", "eodhd", "treasury_direct"]
SNAPSHOT_VERSION = "security-market-data-v2"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def apply_maturity_guard(result: dict[str, Any]) -> dict[str, Any]:
    """Recheck calendar-dependent current eligibility on every cache read."""
    if (result.get("request") or {}).get("kind") != "bond" and (result.get("security") or {}).get("kind") != "bond":
        return result
    maturity = (result.get("details") or {}).get("maturity_date")
    try:
        matured = bool(maturity and date.fromisoformat(maturity) < date.today())
    except (ValueError, TypeError):
        matured = False
    if matured or result.get("current_quote_eligible") is False:
        result.update(quote=None, quote_status="matured", maturity_status="past_maturity", current_quote_eligible=False)
    return result


def normalize_identifier(identifier: str, identifier_type: str, kind: str) -> tuple[str, str]:
    value = identifier.upper().strip()
    if identifier_type == "auto":
        if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", value):
            identifier_type = "isin"
        elif re.fullmatch(r"[A-Z0-9*@#]{8}[0-9]", value):
            identifier_type = "cusip"
        else:
            identifier_type = "ticker"
    patterns = {"cusip": r"[A-Z0-9*@#]{8}[0-9]", "isin": r"[A-Z]{2}[A-Z0-9]{9}[0-9]", "ticker": r"[A-Z0-9][A-Z0-9.\-]{0,39}"}
    if identifier_type not in patterns or not re.fullmatch(patterns[identifier_type], value) or ".." in value:
        raise ValueError("Use an exact CUSIP, ISIN or fund ticker without a URL or path")
    if kind == "bond" and identifier_type == "ticker":
        raise ValueError("Bond lookup requires a CUSIP or ISIN")
    if (identifier_type == "cusip" and not valid_cusip(value)) or (identifier_type == "isin" and not valid_isin(value)):
        raise ValueError("The security identifier check digit is invalid")
    return value, identifier_type


def lookup_range(date_from: str, date_to: str) -> tuple[date, date]:
    end = price_day(date_to) if date_to else date.today()
    start = price_day(date_from) if date_from else end - timedelta(days=31)
    if start > end or end > date.today() or start < date(1970, 1, 1):
        raise ValueError("Price dates must be ordered, on or after 01/01/1970, and not in the future")
    if (end - start).days > 366 * 30:
        raise ValueError("Request no more than 30 years of price history at a time")
    return start, end


def _setting_number(value: Any, default: int, low: int, high: int) -> int:
    try:
        result = int(value)
    except (ValueError, TypeError, OverflowError):
        return default
    return min(max(result, low), high)


class SecurityMarketData:
    def __init__(self, config: dict[str, Any], cache: Any, *, providers: dict[str, Any] | None = None):
        section = config.get("security_lookup") or {}
        self.settings = section if isinstance(section, dict) else {}
        self.cache = cache
        self.provider_limit = _setting_number(self.settings.get("max_provider_requests", 5), 5, 1, 5)
        self.ttl_seconds = _setting_number(self.settings.get("cache_ttl_hours", 24), 24, 1, 168) * 3600
        self._injected_providers = providers

    def _providers(self, kind: str, selected: str) -> list[tuple[str, Any]]:
        from .us_market_providers import EodhdFundProvider, FinnhubBondProvider, TreasuryDirectProvider
        names = (["finnhub", "treasury_direct"] if kind == "bond" else ["eodhd"]) if selected == "auto" else [selected]
        if self._injected_providers is not None:
            return [(name, self._injected_providers[name]) for name in names if name in self._injected_providers]
        constructors = {"finnhub": FinnhubBondProvider, "eodhd": EodhdFundProvider, "treasury_direct": TreasuryDirectProvider}
        result = []
        for name in names:
            section = self.settings.get(name) or {}
            section = section if isinstance(section, dict) else {}
            if section.get("enabled", True) is False:
                continue
            if name != "treasury_direct" and not section.get("api_key"):
                continue
            result.append((name, constructors[name](section)))
        return result

    def fetch(self, identifier: str, kind: str, identifier_type: str = "auto", provider: str = "auto", *,
              date_from: str = "", date_to: str = "", refresh: bool = False, cache_only: bool = False) -> dict[str, Any]:
        from .us_market_providers import ProviderFailure, RequestBudget
        identifier, identifier_type = normalize_identifier(identifier, identifier_type, kind)
        start, end = lookup_range(date_from, date_to)
        if kind not in {"bond", "fund", "etf"} or provider not in {"auto", "finnhub", "eodhd", "treasury_direct"}:
            raise ValueError("Unsupported security kind or data provider")
        if refresh and cache_only:
            raise ValueError("Choose either refresh or cache_only")
        request = {"identifier": identifier, "identifier_type": identifier_type, "kind": kind,
                   "provider": provider, "date_from": start.isoformat(), "date_to": end.isoformat()}
        contracts = {name: {field: (self.settings.get(name) or {}).get(field)
                            for field in ("enabled", "quote_unit", "quote_currency")}
                     for name in ("finnhub", "treasury_direct", "eodhd")
                     if isinstance(self.settings.get(name) or {}, dict)}
        key = SNAPSHOT_VERSION + ":" + hashlib.sha256(json.dumps({"request": request, "contracts": contracts}, sort_keys=True).encode()).hexdigest()
        saved = self.cache.get_security_snapshot("security_lookup", identifier, key)
        if isinstance(saved, dict) and saved.get("schema_version") != SNAPSHOT_VERSION:
            saved = None
        if saved:
            try:
                fresh = (_now() - datetime.fromisoformat(saved["retrieved_at"])).total_seconds() < self.ttl_seconds
            except (ValueError, TypeError, KeyError):
                fresh = False
            if (fresh and not refresh) or cache_only:
                if kind == "bond" and not cache_only and saved.get("provider") and saved.get("security"):
                    self.cache.set_security_snapshot("security_lookup", identifier, SNAPSHOT_VERSION + ":latest:" + kind, saved)
                return apply_maturity_guard({**deepcopy(saved), "cache_status": "fresh" if fresh else "stale", "provider_requests": 0,
                        **({"status": "stale"} if not fresh else {})})
        if cache_only:
            return self._empty(request, "missing", "cache_empty", 0)
        candidates = self._providers(kind, provider)
        if not candidates:
            result = self._empty(request, "not_configured", "provider_configuration_required", 0)
            return self._fallback(saved, result)
        budget = RequestBudget(self.provider_limit)
        errors = []
        best = None
        for name, adapter in candidates:
            if budget.remaining <= 0:
                break
            try:
                payload = adapter.fetch(identifier, identifier_type, kind, start, end, budget)
                result = self._response(payload, request, name, start, end, budget.used)
                if best is None or len(result["items"]) > len(best["items"]):
                    best = result
                if result["items"]:
                    break
            except ProviderFailure as exc:
                # Exception text and transport URLs may contain provider credentials.
                allowed = {"not_configured", "not_found", "unsupported", "entitlement_required", "rate_limited", "provider_error", "invalid_response", "request_limit"}
                code = {"access_denied": "entitlement_required", "identity_mismatch": "invalid_response",
                        "missing_identifier": "invalid_response", "invalid_source": "invalid_response",
                        "response_limit": "invalid_response"}.get(exc.code, exc.code)
                code = code if code in allowed else "provider_error"
                errors.append({"provider": name, "code": code})
            except (ValueError, TypeError, KeyError, OverflowError):
                errors.append({"provider": name, "code": "invalid_response"})
        if best:
            best["provider_requests"] = budget.used
            best["provider_errors"] = errors
            if saved and not best["items"] and saved.get("items"):
                return self._fallback(saved, best)
            if (saved and errors and not best["coverage"].get("complete")
                    and len(saved.get("items") or []) > len(best["items"])):
                # A bounded fallback during a primary outage must not replace
                # richer saved history or splice another provider's price basis.
                return self._fallback(saved, best)
            self.cache.set_security_snapshot("security_lookup", identifier, key, best)
            if kind == "bond" and best.get("provider") and best.get("security"):
                self.cache.set_security_snapshot("security_lookup", identifier, SNAPSHOT_VERSION + ":latest:" + kind, best)
            return best
        codes = {entry["code"] for entry in errors}
        status = "not_found" if codes and codes <= {"not_found", "unsupported"} else "provider_error"
        if codes and codes <= {"not_configured", "entitlement_required"}:
            status = "not_configured"
        result = self._empty(request, status, "data_unavailable", budget.used)
        result["provider_errors"] = errors
        return self._fallback(saved, result)

    def _empty(self, request, status, reason, calls):
        return {"schema_version": SNAPSHOT_VERSION, "request": request, "status": status, "reason": reason,
                "security": None, "items": [], "latest_in_range": None, "quote": None, "details": {},
                "coverage": {"complete": False}, "cache_status": "missing", "retrieved_at": _now().isoformat(),
                "provider_requests": calls, "max_provider_requests": self.provider_limit,
                "portfolio_updated": False}

    def _fallback(self, saved, failure):
        if saved:
            return apply_maturity_guard({**deepcopy(saved), "status": "stale", "cache_status": "stale",
                    "refresh_status": failure["status"], "provider_errors": failure.get("provider_errors", []),
                    "provider_requests": failure["provider_requests"], "reason": "refresh_unavailable_saved_evidence"})
        return failure

    def _response(self, payload, request, name, start, end, calls):
        from .us_market_providers import ProviderFailure
        if not isinstance(payload, dict) or not isinstance(payload.get("security"), dict):
            raise ProviderFailure("invalid_response", "The provider did not identify a security")
        security = payload["security"]
        if security.get("kind") and security["kind"] != request["kind"]:
            raise ProviderFailure("invalid_response", "The provider returned another instrument type")
        matched = str(security.get(request["identifier_type"]) or "").upper()
        expected = request["identifier"]
        # US fund ticker spelling may carry the provider's .US suffix.
        if request["identifier_type"] == "ticker":
            matched, expected = matched.removesuffix(".US"), expected.removesuffix(".US")
        if matched != expected:
            raise ProviderFailure("invalid_response", "The provider returned another security")
        rows = []
        seen = set()
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                raise ProviderFailure("invalid_response", "Invalid price observation")
            day = date.fromisoformat(item["price_date"])
            if not start <= day <= end:
                continue
            number = item.get("price")
            try:
                valid = type(number) in {int, float} and math.isfinite(number) and number >= 0
            except OverflowError:
                valid = False
            if not valid or day in seen:
                raise ProviderFailure("invalid_response", "Invalid or repeated price observation")
            seen.add(day)
            rows.append({**item, "price_date": day.isoformat(), "provider": name,
                         "quote_unit": item.get("quote_unit") or "unknown", "price_basis": item.get("price_basis") or "unknown",
                         "adjustment_basis": item.get("adjustment_basis") or "unknown", "observed_at": item.get("observed_at")})
        rows.sort(key=lambda item: item["price_date"])
        if len(rows) > 12_000:
            raise ProviderFailure("invalid_response", "The provider returned too much history")
        latest = rows[-1] if rows else None
        coverage = dict(payload.get("coverage") or {})
        coverage.setdefault("complete", False)
        coverage.update(requested_from=start.isoformat(), requested_to=end.isoformat(),
                        first_observation=rows[0]["price_date"] if rows else None,
                        last_observation=latest["price_date"] if latest else None, count=len(rows))
        result = self._empty(request, "ok" if rows and coverage["complete"] else "partial", "provider_data", calls)
        result.update(security=deepcopy(security), items=rows, latest_in_range=latest,
                      quote=latest if end == date.today() else None, details=payload.get("details") or {},
                      coverage=coverage, provider=name, source_url=payload.get("source_url"),
                      warnings=payload.get("warnings") or [], cache_status="fetched",
                      details_scope="latest_provider_profile_not_historical_point_in_time",
                      note="Provider research data. Quote units and price bases are explicit; no portfolio prices, quantities or cash were changed. Latest in range is not necessarily a live quote.")
        maturity = (payload.get("details") or {}).get("maturity_date")
        try:
            past_maturity = bool(maturity and date.fromisoformat(maturity) < date.today())
        except (ValueError, TypeError):
            past_maturity = False
        if request["kind"] == "bond" and (past_maturity or payload.get("current_quote_eligible") is False):
            result.update(quote=None, quote_status="matured", maturity_status="past_maturity", current_quote_eligible=False)
        result["quote_status"] = ("missing" if result["quote"] is None else
                                  "stale" if date.fromisoformat(latest["price_date"]) < date.today() - timedelta(days=7) else "dated")
        if result.get("maturity_status") == "past_maturity":
            result["quote_status"] = "matured"
        return result


def security_market_router(service: Callable[[], SecurityMarketData], on_reference_update: Callable[[], Any] | None = None) -> APIRouter:
    router = APIRouter(tags=["security market data"], route_class=PriceRoute)

    @router.get("/api/security/market-data")
    def market_data(identifier: Annotated[str, Query(min_length=1, max_length=80)], kind: KINDS,
                    identifier_type: IDENTIFIER_TYPES = "auto", provider: PROVIDERS = "auto",
                    date_from: str = "", date_to: str = "", refresh: bool = False, cache_only: bool = False):
        try:
            result = service().fetch(identifier, kind, identifier_type, provider,
                                     date_from=date_from, date_to=date_to, refresh=refresh, cache_only=cache_only)
            if (on_reference_update and kind == "bond" and not cache_only and result.get("provider") and result.get("security")
                    and result.get("status") in {"ok", "partial"}):
                on_reference_update()
            return result
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    return router
