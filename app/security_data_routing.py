"""Pure ownership classification for automatic API refresh versus AI research.

This module performs no provider, cache, database or filesystem access. A route
is a refresh/discovery contract, not proof that an exact instrument has data or
that provider-native prices can be used in portfolio valuation.
"""
from __future__ import annotations

import re
import math
from datetime import date
from typing import Any

from .security_identifiers import valid_cusip, valid_isin


FIELDS = ("prices", "profile", "reference", "fundamentals", "dividends")
US_MARKETS = {"US", "USA", "NASDAQ", "NYSE", "NYSEARCA", "ARCA", "AMEX", "NYSEMKT", "BATS", "NMFQS", "MUTF", "OTC", "PINK", "OTCQX", "OTCQB", "TREASURY"}
ISRAEL_MARKETS = {"TASE", "TLV", "TELAVIV"}
_HUB_FIELDS = {
    "alpha_vantage": {"prices", "profile", "fundamentals", "dividends"},
    "financial_modeling_prep": {"prices", "profile", "fundamentals", "dividends"},
    "nasdaq_quote": {"prices", "profile"},  # Current quote, not history.
    "stooq": {"prices"},
    "sec_company_facts": {"profile", "fundamentals"},
    "yahoo_finance": {"prices", "profile", "fundamentals", "dividends"},
}
_KEYED = {"alpha_vantage", "financial_modeling_prep", "finnhub", "eodhd"}
_NEGATIVE_CODES = {"not_found", "unsupported", "unsupported_market"}
_UNAVAILABLE_CODES = {"provider_error", "provider_unavailable", "unavailable", "timeout", "rate_limited", "rate_limit", "request_limit", "invalid_response", "access_denied"}


def _text(value: Any) -> str:
    return str(value or "").strip().upper()


def _region(candidate: dict[str, Any]) -> tuple[bool, bool, str]:
    location = re.sub(r"[\W_]+", "", str(candidate.get("location") or "").casefold())
    market = re.sub(r"\s+", "", _text(candidate.get("stock_market")))
    usa = location in {"us", "usa", "unitedstates", "unitedstatesofamerica", "ארהב", "ארצותהברית"} or market in US_MARKETS
    israel = location in {"israel", "il", "stateofisrael", "ישראל"} or market in ISRAEL_MARKETS
    return usa, israel, market


def _asset(candidate: dict[str, Any]) -> str:
    value = "BOND" if _text(candidate.get("asset_sub_class")) == "BOND" else _text(candidate.get("asset_class"))
    return {"MUTUALFUND": "FUND", "MUTUAL_FUND": "FUND", "STOCK": "EQUITY"}.get(value, value)


def _identifiers(candidate: dict[str, Any]) -> set[str]:
    return {_text(candidate.get(key)) for key in ("symbol", "secondary_symbol", "cusip", "isin", "fund_id") if candidate.get(key)}


def _identity_matches(reference: dict[str, Any], identifiers: set[str]) -> bool:
    security = reference.get("security") if isinstance(reference.get("security"), dict) else {}
    request = reference.get("request") if isinstance(reference.get("request"), dict) else {}
    # A failed lookup's exact request can qualify a negative result. A successful
    # profile's own identifiers must qualify positive identity evidence.
    candidates = {_text(security.get(key)) for key in ("identifier", "cusip", "isin", "ticker", "fund_id") if security.get(key)}
    if candidates:
        return bool(candidates & identifiers)
    return bool(_text(request.get("identifier")) in identifiers)


def _has_dated_price(reference: dict[str, Any]) -> bool:
    rows = list(reference.get("items") or []) if isinstance(reference.get("items"), list) else []
    if isinstance(reference.get("quote"), dict):
        rows.append(reference["quote"])
    for row in rows:
        if not isinstance(row, dict) or type(row.get("price")) not in {int, float}:
            continue
        try:
            if row["price"] < 0 or not math.isfinite(row["price"]):
                continue
            day = row.get("price_date")
            if isinstance(day, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                date.fromisoformat(day)
                return True
        except (ValueError, OverflowError):
            continue
    return False


def _provider_state(provider: str, reference: dict[str, Any] | None, identifiers: set[str]) -> tuple[str, bool, set[str]]:
    if not isinstance(reference, dict) or not _identity_matches(reference, identifiers):
        return "unverified", False, set()
    errors = reference.get("provider_errors") if isinstance(reference.get("provider_errors"), list) else []
    codes = {_text(entry.get("code")).lower() for entry in errors if isinstance(entry, dict) and entry.get("provider") == provider}
    same_provider = reference.get("provider") == provider
    if same_provider:
        codes.add(str(reference.get("refresh_status") or reference.get("status") or "").lower())
    security = reference.get("security")
    own_identifiers = {_text(security.get(key)) for key in ("identifier", "cusip", "isin", "ticker", "fund_id") if isinstance(security, dict) and security.get(key)}
    positively_identified = same_provider and bool(own_identifiers & identifiers)
    if positively_identified:
        available = {"reference"}
        if security.get("name"):
            available.add("profile")
        if _has_dated_price(reference):
            available.add("prices")
        # Keep saved exact evidence owned by its API even through an outage.
        state = "entitlement_required" if codes & {"entitlement_required", "not_configured"} else "provider_unavailable" if codes & _UNAVAILABLE_CODES else "verified"
        return state, True, available
    if codes & {"entitlement_required", "not_configured"}:
        return "entitlement_required", False, set()
    if codes & _UNAVAILABLE_CODES:
        return "provider_unavailable", False, set()
    if codes & _NEGATIVE_CODES:
        return "unsupported", False, set()
    return "unverified", False, set()


def route_security(candidate: dict[str, Any], market_data: dict[str, Any], reference: dict[str, Any] | None = None) -> dict[str, Any]:
    """Classify one listing without probing providers or mutating its input.

    ``market_data`` is the existing market_data YAML section. ``reference`` may
    contain an existing exact lookup snapshot; a generic error, another listing
    or a failed HTTP request never establishes unsupported coverage. Missing
    credentials keep an applicable API route in configuration_required state.
    """
    identifiers = _identifiers(candidate)
    usa, israel, market = _region(candidate)
    asset = _asset(candidate)
    empty_fields = {field: {"state": "unsupported", "providers": []} for field in FIELDS}
    if market == "PRIVATE" or asset in {"PRIVATE_STOCK", "EMPLOYEE_STOCK_OPTION", "STOCK_OPTION", "CASH", "CURRENCY"}:
        return {"owner": "ineligible", "provider": None, "providers": [], "configured": False, "coverage": "unsupported", "reason": "not_public_security", "ai_eligible": False, "fields": empty_fields}
    routes: list[dict[str, Any]] = []

    def add(name: str, fields: set[str], section: dict[str, Any] | None = None, *, key_free: bool = False):
        section = section if isinstance(section, dict) else {}
        enabled = section.get("enabled", True) is not False
        configured = enabled and (key_free or name not in _KEYED or bool(section.get("api_key")))
        state, verified, available = _provider_state(name, reference, identifiers)
        if state == "unsupported":
            coverage = "unsupported"
        else:
            coverage = "verified" if verified else "candidate"
            if not configured and state not in {"entitlement_required", "provider_unavailable"}:
                state = "not_configured" if enabled else "disabled"
        routes.append({"provider": name, "fields": sorted(fields), "configured": configured, "coverage": coverage, "status": state, "verified_fields": sorted(available), "price_scope": "current_quote_only" if name == "nasdaq_quote" else "provider_reported"})

    fund_number = next((value for value in identifiers if re.fullmatch(r"[0-9]{5,8}", value) and int(value) > 0), None)
    if asset == "FUND" and israel and _text(candidate.get("currency")) == "ILS" and fund_number:
        identifiers.add(str(int(fund_number)))
        add("maya", {"prices", "profile", "reference"}, key_free=True)
    elif asset == "BOND":
        # Identifier syntax is not issuer coverage. Finnhub is a category-level
        # discovery route, including unverified agency/strip availability.
        us_bond_scope = usa or market in {"BOND", "MANUAL"} and _text(candidate.get("currency")) == "USD"
        bond_ids = [value for value in identifiers if value.startswith("US") and valid_isin(value) or us_bond_scope and valid_cusip(value)]
        if bond_ids:
            lookup = market_data.get("security_lookup") if isinstance(market_data.get("security_lookup"), dict) else {}
            cusips = [value[2:11] if value.startswith("US") and valid_isin(value) else value for value in bond_ids]
            treasury_verified = _provider_state("treasury_direct", reference, identifiers)[1]
            if treasury_verified or any(value.startswith("912") for value in cusips):
                # 912 is only a conservative discovery hint; the official API
                # must still verify issuer, exact identity and price scope.
                add("treasury_direct", {"prices", "profile", "reference"}, lookup.get("treasury_direct"), key_free=True)
            add("finnhub", {"prices", "profile", "reference"}, lookup.get("finnhub"))
    else:
        ticker = next((value for value in identifiers if re.fullmatch(r"[A-Z][A-Z0-9.^=-]{0,39}", value) and not valid_isin(value) and not valid_cusip(value)), None)
        fund_isin = next((value for value in identifiers if value.startswith("US") and valid_isin(value)), None) if asset in {"ETF", "FUND"} else None
        public_tase = market in ISRAEL_MARKETS and bool(ticker or fund_number)
        public_us = usa and bool(ticker)
        public_us_fund_identifier = usa and bool(ticker or fund_isin)
        if asset in {"EQUITY", "ETF", "FUND"} and (public_us or public_tase or public_us_fund_identifier):
            if asset in {"ETF", "FUND"} and public_us_fund_identifier:
                lookup = market_data.get("security_lookup") if isinstance(market_data.get("security_lookup"), dict) else {}
                add("eodhd", {"prices", "profile", "reference"}, lookup.get("eodhd"))
            names = [market_data.get("primary"), *(market_data.get("fallback") or []), *(market_data.get("experimental_fallback") or [])]
            for name in dict.fromkeys(value for value in names if isinstance(value, str)):
                if not (public_us or public_tase) or name not in _HUB_FIELDS or public_tase and name != "yahoo_finance":
                    continue
                section = market_data.get(name) if isinstance(market_data.get(name), dict) else {}
                # Match MarketDataHub's explicit opt-in for experimental Yahoo.
                if name == "yahoo_finance" and not section.get("enabled"):
                    continue
                fields = set(_HUB_FIELDS[name])
                if asset != "EQUITY":
                    fields.discard("fundamentals")
                add(name, fields, section)

    fields = {}
    for field in FIELDS:
        applicable = [route for route in routes if field in route["fields"]]
        active = [route for route in applicable if route["coverage"] != "unsupported"]
        preferred = next((route for route in active if route["configured"]), active[0] if active else None)
        verified = bool(preferred and field in preferred["verified_fields"])
        state = preferred["status"] if preferred else "unsupported"
        if state == "verified" and not verified:
            state = "unverified"
        fields[field] = {"state": state, "providers": [route["provider"] for route in active], "verified": verified}
    owners = [route for route in routes if route["coverage"] != "unsupported" and set(route["fields"]) & {"prices", "reference"}]
    configured = [route for route in owners if route["configured"]]
    preferred = configured[0] if configured else owners[0] if owners else None
    if preferred:
        reason = "configuration_required" if not configured or all(route["status"] == "entitlement_required" for route in configured) else "provider_unavailable" if all(route["status"] == "provider_unavailable" for route in configured) else "api_coverage_verified" if preferred["coverage"] == "verified" else "api_coverage_unverified"
        owner, coverage = "api", preferred["coverage"]
    else:
        owner, coverage = "ai", "unsupported"
        reason = "api_coverage_unsupported" if routes and all(route["coverage"] == "unsupported" for route in routes) else "no_price_reference_api"
    return {"owner": owner, "provider": preferred["provider"] if preferred else None, "providers": routes, "configured": bool(configured), "coverage": coverage, "reason": reason, "ai_eligible": owner == "ai", "fields": fields}
