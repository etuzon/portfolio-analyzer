"""Bounded, read-only adapters for US bonds, mutual funds and ETFs.

These adapters retain provider quote conventions. They do not write positions,
transactions or normalized portfolio prices, and never infer a par-unit mapping.
"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
import json
import math
import re
import time
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from .security_identifiers import valid_cusip, valid_isin


class ProviderFailure(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class RequestBudget:
    limit: int = 5
    timeout_seconds: float = 35
    used: int = 0
    _started: float = field(default_factory=time.monotonic, repr=False)

    def __post_init__(self):
        self.limit = min(max(int(self.limit), 1), 5)
        self.timeout_seconds = min(max(float(self.timeout_seconds), 1), 40)

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def remaining_seconds(self) -> float:
        return max(0, self.timeout_seconds - (time.monotonic() - self._started))

    def consume(self):
        if not self.remaining:
            raise ProviderFailure("request_limit", "The provider request limit was reached.")
        if not self.remaining_seconds:
            raise ProviderFailure("timeout", "The provider request time budget was reached.")
        self.used += 1


def _number(value: Any, *, nonnegative: bool = False) -> float | None:
    if isinstance(value, bool) or value in (None, "", "null", "N/A", "—", "-"):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) and (not nonnegative or number >= 0) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _day(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return None


def _text(value: Any) -> str | None:
    return value.strip()[:1000] if isinstance(value, str) and value.strip() else None


def _unique_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dates = [item["price_date"] for item in items]
    if len(set(dates)) != len(dates):
        raise ProviderFailure("invalid_response", "The provider returned duplicate daily observations without a revision rule.")
    return sorted(items, key=lambda item: item["price_date"])


def _treasury_number(value: str) -> float | None:
    value = value.strip()
    if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", value):
        return None
    return _number(value.replace(",", ""), nonnegative=True)


class _Adapter:
    name = "base"
    allowed_host = ""

    def __init__(self, config: dict[str, Any] | None = None, client: httpx.Client | None = None):
        self.config, self.client = config or {}, client

    def _client_context(self):
        return nullcontext(self.client) if self.client is not None else httpx.Client(
            timeout=8, follow_redirects=False, trust_env=False,
            headers={"User-Agent": "portfolio-analyzer/1.0", "Accept": "application/json,text/html"},
        )

    def _request(self, client, budget: RequestBudget, method: str, url: str, **kwargs) -> httpx.Response:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname != self.allowed_host or parts.username or parts.password:
            raise ProviderFailure("invalid_source", "The provider route is unavailable.")
        budget.consume()
        try:
            with client.stream(method, url, follow_redirects=False,
                               timeout=min(8, budget.remaining_seconds or 0.1), **kwargs) as response:
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 4_000_000:
                        raise ProviderFailure("response_limit", "The provider response exceeded the size limit.")
                # iter_bytes() has already decoded transfer compression. Do not
                # attach the original encoding/length and decode it a second time.
                headers = {key: value for key, value in response.headers.items()
                           if key.lower() not in {"content-encoding", "content-length", "transfer-encoding"}}
                result = httpx.Response(response.status_code, content=bytes(body), headers=headers,
                                        request=response.request)
            if result.status_code in (401, 403):
                raise ProviderFailure("access_denied", "The provider denied access. Check the configured key and subscription.")
            if result.status_code == 429:
                raise ProviderFailure("rate_limited", "The provider rate limit was reached.")
            if result.status_code == 404:
                raise ProviderFailure("not_found", "The provider did not find this security.")
            if result.status_code >= 400:
                raise ProviderFailure("unavailable", "The provider request is unavailable.")
            return result
        except (httpx.HTTPError, OSError) as exc:
            # URLs may contain provider credentials; never expose native errors.
            raise ProviderFailure("unavailable", "The provider request is unavailable.") from None

    def _json(self, client, budget, url, **kwargs):
        response = self._request(client, budget, "GET", url, **kwargs)
        if response.is_redirect:
            raise ProviderFailure("invalid_response", "The provider returned an unexpected redirect.")
        try:
            value = response.json()
        except ValueError:
            raise ProviderFailure("invalid_response", "The provider returned invalid data.") from None
        if isinstance(value, dict) and (value.get("error") or value.get("Error Message")):
            raise ProviderFailure("unavailable", "The provider could not supply this data.")
        return value


def _coverage(items, start: date, end: date, *, truncated=False, next_date=None):
    return {
        "requested_from": start.isoformat(), "requested_to": end.isoformat(),
        "first_date": items[0]["price_date"] if items else None,
        "last_date": items[-1]["price_date"] if items else None,
        "count": len(items), "truncated": truncated, "next_date": next_date,
        "complete": False,
        "note": "Observed records only; missing dates are not filled and full trading-calendar coverage is not established.",
    }


def _item(day: str, price: float, currency: str | None, unit: str, basis: str, source: str, **extra):
    return {"price_date": day, "price": price, "currency": currency,
            "quote_unit": unit, "price_basis": basis, "accrual_basis": "unknown",
            "side": "unknown", "adjustment_basis": "unadjusted",
            "source_url": source, "observed_at": None, **extra}


class FinnhubBondProvider(_Adapter):
    name = "finnhub"
    allowed_host = "api.finnhub.io"
    base_url = "https://api.finnhub.io/api/v1"

    def fetch(self, identifier: str, identifier_type: str, kind: str, from_date: date,
              to_date: date, budget: RequestBudget) -> dict[str, Any]:
        if kind != "bond" or identifier_type not in {"cusip", "isin", "figi"}:
            raise ProviderFailure("unsupported", "Finnhub bond data requires a CUSIP, ISIN or FIGI.")
        key = str(self.config.get("api_key") or "")
        if not key:
            raise ProviderFailure("not_configured", "Configure market_data.security_lookup.finnhub.api_key for bond data.")
        configured_currency = self.config.get("quote_currency")
        if configured_currency is not None:
            if not isinstance(configured_currency, str) or not re.fullmatch(r"[A-Za-z]{3}", configured_currency.strip()):
                raise ProviderFailure("not_configured", "Configure a three-letter Finnhub bond quote currency or omit it.")
            configured_currency = configured_currency.strip().upper()
        identifier = identifier.upper()
        headers = {"X-Finnhub-Token": key}
        profile_url, prices_url = self.base_url + "/bond/profile", self.base_url + "/bond/price"
        with self._client_context() as client:
            profile = self._json(client, budget, profile_url, params={identifier_type: identifier}, headers=headers)
            if not isinstance(profile, dict) or not profile:
                raise ProviderFailure("not_found", "The provider did not find this bond.")
            isin = str(profile.get("isin") or "").upper()
            reported_cusip = str(profile.get("cusip") or "").upper()
            # The documented profile example leaves CUSIP empty. A verified US
            # ISIN carries that same checked CUSIP; it is an identity alias,
            # never evidence for the security's currency or price convention.
            cusip = reported_cusip or (isin[2:11] if isin.startswith("US") and valid_isin(isin) and valid_cusip(isin[2:11]) else "")
            matched = cusip if identifier_type == "cusip" else str(profile.get(identifier_type) or "").upper()
            if matched != identifier:
                raise ProviderFailure("identity_mismatch", "The provider returned a different or unverified bond identity.")
            if not valid_isin(isin):
                raise ProviderFailure("missing_identifier", "The provider did not supply the ISIN required for price history.")
            if cusip and (not valid_cusip(cusip) or (isin.startswith("US") and isin[2:11] != cusip)):
                raise ProviderFailure("identity_mismatch", "The provider returned inconsistent bond identifiers.")
            raw_currency = profile.get("currency")
            if raw_currency in (None, ""):
                raw_currency = profile.get("currencyCode")
            if raw_currency not in (None, ""):
                if not isinstance(raw_currency, str) or not re.fullmatch(r"[A-Za-z]{3}", raw_currency.strip()):
                    raise ProviderFailure("invalid_response", "The provider returned an invalid bond currency.")
                currency = raw_currency.strip().upper()
                if configured_currency and currency != configured_currency:
                    raise ProviderFailure("invalid_response", "The reported bond currency conflicts with the configured source contract.")
                currency_origin = "provider_profile"
            else:
                currency = configured_currency
                currency_origin = "configuration" if currency else "unverified"
            prices = self._json(client, budget, prices_url, headers=headers, params={
                "isin": isin,
                "from": int(datetime.combine(from_date, datetime.min.time(), timezone.utc).timestamp()),
                "to": int(datetime.combine(to_date + timedelta(days=1), datetime.min.time(), timezone.utc).timestamp()) - 1,
            })
        if not isinstance(prices, dict) or prices.get("s") not in {"ok", "no_data"}:
            raise ProviderFailure("invalid_response", "The provider returned an invalid bond price series.")
        configured_unit = self.config.get("quote_unit", "unknown")
        unit = configured_unit if configured_unit in {"percent_of_par", "currency_per_unit"} else "unknown"
        security = {"identifier": identifier, "identifier_type": identifier_type, "kind": "bond",
                    "cusip": cusip or None, "isin": isin, "figi": _text(profile.get("figi")),
                    "cusip_origin": "provider_profile" if reported_cusip else "validated_us_isin" if cusip else "unverified",
                    "name": _text(profile.get("name") or profile.get("asset")), "currency": currency,
                    "currency_origin": currency_origin,
                    "venue": "US bond market", "market_scope": "US government and TRACE corporate/144A provider coverage"}
        items, rejected = [], 0
        closes, timestamps = prices.get("c") or [], prices.get("t") or []
        if not isinstance(closes, list) or not isinstance(timestamps, list) or len(closes) != len(timestamps) or len(closes) > 20_000:
            raise ProviderFailure("invalid_response", "The provider returned mismatched bond price arrays.")
        for close, timestamp in zip(closes, timestamps):
            value = _number(close, nonnegative=True)
            try:
                if type(timestamp) not in (int, float) or not math.isfinite(timestamp):
                    raise ValueError()
                day = datetime.fromtimestamp(timestamp, timezone.utc).date()
            except (ValueError, OSError, OverflowError):
                rejected += 1
                continue
            if value is None or not from_date <= day <= to_date or day > date.today():
                rejected += 1
                continue
            items.append(_item(day.isoformat(), value, currency, unit, "close", prices_url,
                               quote_unit_origin="configuration" if unit != "unknown" else "unverified",
                               currency_origin=currency_origin))
        items = _unique_items(items)
        maturity = _day(profile.get("maturityDate"))
        past_maturity = bool(maturity and date.fromisoformat(maturity) < date.today())
        maturity_status = "past_maturity" if past_maturity else "not_past_maturity" if maturity else "unknown"
        details = {
            "coupon_rate_pct": _number(profile.get("coupon")),
            "maturity_date": maturity, "maturity_status": maturity_status,
            "issue_date": _day(profile.get("issueDate")),
            "payment_frequency_reported": _text(profile.get("paymentFrequency")),
            "offering_price": _number(profile.get("offeringPrice")), "offering_price_is_current": False,
            "first_coupon_date": _day(profile.get("firstCouponDate")),
            "callable": profile.get("callable") if type(profile.get("callable")) is bool else None,
            "coupon_type": _text(profile.get("couponType")), "bond_type": _text(profile.get("bondType")),
            "debt_type": _text(profile.get("debtType")), "security_level": _text(profile.get("securityLevel")),
            "original_offering": _number(profile.get("originalOffering")),
            "amount_outstanding": _number(profile.get("amountOutstanding")),
            "source_url": profile_url,
        }
        warnings = ["Government prices are end-of-day; TRACE corporate/144A prices may be delayed. No executable live quote is established.",
                    "Clean/dirty accrual basis is not established by this provider response."]
        if unit == "unknown" or currency is None:
            warnings.append("Source quote unit or currency is unverified; do not apply this raw series to portfolio valuation.")
        if past_maturity:
            warnings.append("The published maturity date has passed. Actual dated history is retained; neither a current quote, redemption price nor settlement cash is invented.")
        if rejected:
            warnings.append(f"Rejected {rejected} invalid or out-of-range price records.")
        return {"provider": self.name, "security": security, "items": items, "details": details,
                "maturity_status": maturity_status, "current_quote_eligible": not past_maturity,
                "source_url": profile_url, "coverage": _coverage(items, from_date, to_date), "warnings": warnings}


class EodhdFundProvider(_Adapter):
    name = "eodhd"
    allowed_host = "eodhd.com"
    base_url = "https://eodhd.com/api"

    def fetch(self, identifier: str, identifier_type: str, kind: str, from_date: date,
              to_date: date, budget: RequestBudget) -> dict[str, Any]:
        if kind not in {"fund", "etf"} or identifier_type not in {"ticker", "isin"}:
            raise ProviderFailure("unsupported", "EODHD fund data requires the exact US ticker or fund ISIN.")
        key = str(self.config.get("api_key") or "")
        if not key:
            raise ProviderFailure("not_configured", "Configure market_data.security_lookup.eodhd.api_key for fund data.")
        identifier = identifier.upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,24}", identifier):
            raise ProviderFailure("invalid_identifier", "The provider identifier is invalid.")
        requested = identifier if identifier_type == "isin" or identifier.endswith(".US") else identifier + ".US"
        profile_url = self.base_url + "/v1.1/fundamentals/" + requested
        params = {"api_token": key, "fmt": "json"}
        with self._client_context() as client:
            profile = self._json(client, budget, profile_url, params={**params, "filter": "General,MutualFund_Data,ETF_Data"})
            general = profile.get("General") if isinstance(profile, dict) else None
            if not isinstance(general, dict) or not general:
                raise ProviderFailure("not_found", "The provider did not find this fund.")
            instrument_type = str(general.get("Type") or "").upper()
            actual_kind = "etf" if instrument_type == "ETF" else "fund" if instrument_type in {"FUND", "MUTUAL FUND"} else None
            if actual_kind != kind:
                raise ProviderFailure("identity_mismatch", "The provider returned a different instrument type.")
            fund_data = profile.get("MutualFund_Data") if kind == "fund" else profile.get("ETF_Data")
            fund_data = fund_data if isinstance(fund_data, dict) else {}
            general_isin = str(general.get("ISIN") or "").upper().strip()
            section_isin = str(fund_data.get("ISIN") or "").upper().strip()
            isin = general_isin or section_isin
            cusip = str(general.get("CUSIP") or "").upper().strip()
            if ((general_isin and section_isin and general_isin != section_isin)
                    or (isin and not valid_isin(isin)) or (cusip and not valid_cusip(cusip))
                    or (isin.startswith("US") and cusip and isin[2:11] != cusip)):
                raise ProviderFailure("identity_mismatch", "The provider returned conflicting or invalid fund identifiers.")
            code = str(general.get("Code") or "").upper()
            if identifier_type == "isin":
                identity_matches = isin == identifier
            else:
                identity_matches = code == identifier.removesuffix(".US")
            if not identity_matches or not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,19}", code):
                raise ProviderFailure("identity_mismatch", "The provider returned a different or unverified fund identity.")
            venue = str(general.get("Exchange") or "").upper().replace(" ", "")
            if venue not in {"US", "NASDAQ", "NYSE", "NYSEARCA", "ARCA", "BATS", "AMEX", "NYSEMKT", "NMFQS", "MUTF", "OTC", "PINK", "OTCQX", "OTCQB"}:
                raise ProviderFailure("unsupported_market", "The fund response does not establish a US listing.")
            currency = str(general.get("CurrencyCode") or "").upper()
            if not re.fullmatch(r"[A-Z]{3}", currency):
                raise ProviderFailure("missing_currency", "The fund response did not establish its quote currency.")
            prices_url = self.base_url + "/eod/" + code + ".US"
            prices = self._json(client, budget, prices_url, params={**params, "from": from_date.isoformat(),
                               "to": to_date.isoformat(), "period": "d", "order": "a"})
        if not isinstance(prices, list) or len(prices) > 20_000:
            raise ProviderFailure("invalid_response", "The provider returned an invalid fund price series.")
        items, rejected = [], 0
        for row in prices:
            day = _day(row.get("date")) if isinstance(row, dict) else None
            value = _number(row.get("close"), nonnegative=True) if isinstance(row, dict) else None
            if not day or value is None or not from_date.isoformat() <= day <= to_date.isoformat() or day > date.today().isoformat():
                rejected += 1
                continue
            item = _item(day, value, currency, "currency_per_share", "close", prices_url)
            item["accrual_basis"] = "not_applicable"
            item["adjusted_close"] = _number(row.get("adjusted_close"), nonnegative=True)
            item["adjusted_close_basis"] = "provider_adjusted"
            item["volume"] = _number(row.get("volume"), nonnegative=True)
            items.append(item)
        items = _unique_items(items)
        detail_fields = ("Nav", "Prev_Close_Price", "Update_Date", "Portfolio_Net_Assets", "Share_Class_Net_Assets",
                         "Inception_Date", "Currency", "Domicile", "Yield", "Yield_YTD", "Expense_Ratio", "Expense_Ratio_Date") if kind == "fund" else (
                         "Net_Assets", "NetExpenseRatio", "Net_Expense_Ratio", "AnnualHoldingsTurnover", "TotalAssets", "Yield", "Inception_Date", "ISIN", "Company_Name", "Domicile", "ETF_Name")
        details = {key: fund_data.get(key) for key in detail_fields if isinstance(fund_data.get(key), (str, int, float, bool, type(None)))}
        details = {key: value for key, value in details.items() if not isinstance(value, float) or math.isfinite(value)}
        details["source_url"] = profile_url
        details["nav_date_is_confirmed"] = False
        details["note"] = "Fundamental update dates are not automatically NAV valuation dates. Historical close is retained as close, not relabelled NAV."
        warnings = ["Historical close is provider-reported end-of-day data, not an executable live quote or a guaranteed NAV series."]
        if rejected:
            warnings.append(f"Rejected {rejected} invalid or out-of-range price records.")
        return {"provider": self.name, "security": {"identifier": identifier, "identifier_type": identifier_type,
                "kind": kind, "ticker": code, "provider_symbol": code + ".US", "name": _text(general.get("Name")),
                "isin": isin or None, "cusip": cusip or None,
                "venue": _text(general.get("Exchange")), "currency": currency, "fund_family": _text(general.get("Fund_Family"))},
                "items": items, "details": details, "source_url": profile_url.replace(key, "[redacted]"),
                "coverage": _coverage(items, from_date, to_date), "warnings": warnings}


class _TreasuryPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.csrf = ""
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "input" and values.get("name") == "_csrf":
            self.csrf = values.get("value", "")
        elif tag == "tr":
            self._row = []
        elif tag in {"td", "th"}:
            self._cell = []

    def handle_data(self, data):
        self.text.append(data)
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self._cell is not None:
            if self._row is not None:
                self._row.append(" ".join(" ".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


class TreasuryDirectProvider(_Adapter):
    name = "treasury_direct"
    allowed_host = "www.treasurydirect.gov"
    base_url = "https://www.treasurydirect.gov"
    form_url = base_url + "/GA-FI/FedInvest/selectSecurityPriceDate"
    detail_url = base_url + "/GA-FI/FedInvest/securityPriceDetail"

    def fetch(self, identifier: str, identifier_type: str, kind: str, from_date: date,
              to_date: date, budget: RequestBudget) -> dict[str, Any]:
        if kind != "bond" or identifier_type not in {"cusip", "isin"}:
            raise ProviderFailure("unsupported", "TreasuryDirect supports Treasury CUSIPs and matching US ISINs.")
        identifier = identifier.upper()
        if identifier_type == "isin":
            if not identifier.startswith("US") or not valid_isin(identifier):
                raise ProviderFailure("unsupported", "TreasuryDirect cannot identify this ISIN.")
            cusip = identifier[2:11]
        else:
            cusip = identifier
        if not valid_cusip(cusip) or not re.fullmatch(r"[A-Z0-9]{9}", cusip):
            raise ProviderFailure("invalid_identifier", "The Treasury CUSIP is invalid.")
        metadata_url = self.base_url + "/TA_WS/securities/search"
        warnings = []
        with self._client_context() as client:
            records = self._json(client, budget, metadata_url, params={"cusip": cusip, "format": "json"})
            records = records if isinstance(records, list) else []
            records = [row for row in records if isinstance(row, dict) and row.get("cusip") == cusip]
            if not records:
                raise ProviderFailure("not_found", "TreasuryDirect did not find this Treasury security. Corporate bonds require a bond provider.")
            row = max(records, key=lambda value: str(value.get("issueDate") or ""))
            security = {"identifier": identifier, "identifier_type": identifier_type, "kind": "bond", "cusip": cusip,
                        "isin": identifier if identifier_type == "isin" else None, "currency": "USD",
                        "name": "U.S. Treasury " + str(row.get("securityDescription") or row.get("securityType") or "security"),
                        "issuer": "United States Department of the Treasury", "venue": "US Treasury market"}
            details = {"coupon_rate_pct": _number(row.get("interestRate")), "maturity_date": _day(row.get("maturityDate")),
                       "issue_date": _day(row.get("issueDate")), "payment_frequency_reported": _text(row.get("frequencyOfInterestPayments")),
                       "security_type": _text(row.get("securityType")), "original_term": _text(row.get("originalSecurityTerm")),
                       "floating_rate": {"Yes": True, "No": False}.get(row.get("floatingRate")),
                       "inflation_protected": {"Yes": True, "No": False}.get(row.get("inflationProtected")),
                       "auction_high_yield_pct": _number(row.get("highYield")), "auction_yield_is_current": False,
                       "source_url": metadata_url}
            # Public daily files are one HTTP form submission per date. Preserve
            # the budget and report continuation rather than looping over years.
            items = []
            next_date = None
            requested_days = []
            cursor = to_date
            while cursor >= from_date and len(requested_days) < 6:
                if cursor.weekday() < 5:
                    requested_days.append(cursor)
                cursor -= timedelta(days=1)
            if budget.remaining >= 3 and requested_days:
                form = self._request(client, budget, "GET", self.form_url)
                parser = _TreasuryPage()
                parser.feed(form.text)
                if not parser.csrf:
                    warnings.append("The Treasury price form could not be read; reference data remains available.")
                else:
                    for index, day in enumerate(requested_days):
                        if budget.remaining < 2:
                            next_date = day.isoformat()
                            break
                        page = self._request(client, budget, "POST", self.form_url,
                                             data={"priceDate": day.isoformat(), "submit": "Show Prices", "_csrf": parser.csrf})
                        if page.is_redirect:
                            target = urljoin(str(page.url), page.headers.get("location", ""))
                            if target != self.detail_url:
                                raise ProviderFailure("invalid_response", "The Treasury price form redirected to an unexpected route.")
                            page = self._request(client, budget, "GET", target)
                        fetched = _TreasuryPage()
                        fetched.feed(page.text)
                        actual_day = self._page_day(fetched)
                        if actual_day != day:
                            warnings.append("The Treasury response did not establish the requested observation date; its prices were omitted.")
                            next_date = day.isoformat()
                            break
                        item = self._price_row(fetched, cusip, day)
                        if item:
                            items.append(item)
                        if fetched.csrf:
                            parser.csrf = fetched.csrf
                        if index == len(requested_days) - 1 and day > from_date:
                            next_date = (day - timedelta(days=1)).isoformat()
            elif requested_days:
                next_date = requested_days[0].isoformat()
                warnings.append("The request budget left reference data only; price dates require a subsequent request.")
        items.sort(key=lambda value: value["price_date"])
        if next_date:
            warnings.append("The free Treasury source supplies daily files. The requested history is partial; use the returned next date or configure a history provider.")
        warnings.append("Treasury programme buy/sell fields are not generic market bid/ask labels; end-of-day valuation prices are returned separately.")
        warnings.append("The Treasury file is published for market-based Treasury special securities; values are reference/programme prices, not broker execution quotes.")
        return {"provider": self.name, "security": security, "items": items, "details": details,
                "source_url": metadata_url, "coverage": _coverage(items, from_date, to_date, truncated=bool(next_date), next_date=next_date),
                "warnings": warnings}

    @staticmethod
    def _page_day(page: _TreasuryPage) -> date | None:
        text = " ".join(" ".join(page.text).split())
        match = re.search(r"Prices\s+For\s*:?\s*([A-Za-z]+\s+\d{1,2},\s*\d{4})", text, re.I)
        if match:
            try:
                return datetime.strptime(match.group(1), "%B %d, %Y").date()
            except ValueError:
                pass
        return None

    def _price_row(self, page: _TreasuryPage, cusip: str, day: date) -> dict[str, Any] | None:
        for cells in page.rows:
            if not cells or cells[0].strip() != cusip:
                continue
            # Header detection keeps the source's programme-specific columns
            # distinct. Never infer the last cell is a closing price.
            header = next((row for row in page.rows if any("CUSIP" in cell.upper() for cell in row)), [])
            normalized = [" ".join(value.lower().split()) for value in header]
            positions = {value: index for index, value in enumerate(normalized)}
            eod_position = next((index for value, index in positions.items() if "end of day" in value or "end-of-day" in value), None)
            if eod_position is None or eod_position >= len(cells):
                return None
            value = _treasury_number(cells[eod_position])
            buy_position, sell_position = positions.get("buy"), positions.get("sell")
            buy = _treasury_number(cells[buy_position]) if buy_position is not None and buy_position < len(cells) else None
            sell = _treasury_number(cells[sell_position]) if sell_position is not None and sell_position < len(cells) else None
            # This daily Treasury programme file uses zero placeholders when a
            # price is unavailable, unlike a reported corporate-bond default.
            eod, buy, sell = (number if number is not None and number > 0 else None for number in (value, buy, sell))
            if eod is None and buy is None and sell is None:
                return None
            price, basis, side = ((eod, "valuation", "valuation") if eod is not None else
                                  (buy, "programme_purchase", "programme_purchase_mean") if buy is not None else
                                  (sell, "programme_redemption", "programme_redemption_bid"))
            return _item(day.isoformat(), price, "USD", "percent_of_par", basis, self.detail_url,
                         side=side, source_price_date_requested=day.isoformat(),
                         end_of_day_price=eod, raw_end_of_day_price=value,
                         end_of_day_status="zero_placeholder" if value == 0 else "available" if eod is not None else "missing",
                         programme_purchase_price=buy, programme_redemption_price=sell)
        return None
