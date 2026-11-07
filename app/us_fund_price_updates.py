"""Pure application of verified US fund/ETF closes to local share-price units.

This module returns proposed application records; it never fetches, saves,
changes positions, or substitutes fundamental NAV for reported market closes.
"""
from datetime import date, datetime, timedelta, timezone
import json
import math
import re
from urllib.parse import urlsplit

from .local_portfolio import _location_key, normalize_price
from .security_identifiers import valid_cusip, valid_isin


_US_VENUES = {"US", "NASDAQ", "NYSE", "NYSEARCA", "ARCA", "BATS", "AMEX", "NYSEMKT", "NMFQS", "MUTF", "OTC", "PINK", "OTCQX", "OTCQB"}


def _ticker(value):
    value = str(value or "").upper().strip().removesuffix(".US")
    return value if re.fullmatch(r"[A-Z0-9][A-Z0-9_.-]{0,39}", value) and ".." not in value else ""


def _matches(metadata, security):
    values = {str(metadata.get(field) or "").upper().strip() for field in ("symbol", "secondary_symbol")} - {""}
    ticker = _ticker(security.get("ticker"))
    isin = str(security.get("isin") or "").upper().strip()
    cusip = str(security.get("cusip") or "").upper().strip()
    if not ticker or isin and not valid_isin(isin) or cusip and not valid_cusip(cusip):
        return False
    if isin.startswith("US") and cusip and isin[2:11] != cusip:
        return False
    provider_symbol = security.get("provider_symbol")
    if provider_symbol and str(provider_symbol).upper() != ticker + ".US":
        return False
    # A checked, explicitly supplied ISIN is a share-class constraint. Do not
    # override a conflicting one merely because another ticker happens to match.
    metadata_isins = {value for value in values if valid_isin(value)}
    if metadata_isins and metadata_isins != {isin}:
        return False
    if any(re.fullmatch(r"US[A-Z0-9]{9}\d", value) and not valid_isin(value) for value in values):
        return False
    return bool(isin and isin in values or any(_ticker(value) == ticker for value in values if not valid_isin(value)))


def us_fund_price_records(candidate, metadata, snapshot, existing, history_start):
    """Map raw unadjusted EODHD closes to currency per recorded local share."""
    if not isinstance(metadata, dict) or not isinstance(snapshot, dict):
        return []
    required = {"symbol", "stock_market", "currency", "asset_class", "location"}
    if not required <= metadata.keys() or candidate.get("data_source") not in {"LOCAL", "MANUAL"}:
        return []
    asset = metadata.get("asset_class")
    if (asset not in {"ETF", "MUTUALFUND", "FUND"} or _location_key(metadata.get("location")) != "usa"
            or normalize_price(100, metadata["location"], asset) != 100
            or snapshot.get("provider") != "eodhd" or snapshot.get("status") not in {"ok", "partial"}
            or snapshot.get("cache_status") == "stale"):
        return []
    security = snapshot.get("security")
    if not isinstance(security, dict):
        return []
    expected_kind = "etf" if asset == "ETF" else "fund"
    currency = metadata.get("currency")
    if (security.get("kind") != expected_kind or security.get("currency") != currency
            or not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency)
            or str(security.get("venue") or "").upper().replace(" ", "") not in _US_VENUES
            or not _matches(metadata, security)):
        return []
    try:
        retrieved = datetime.fromisoformat(snapshot["retrieved_at"])
        if retrieved.tzinfo is None or retrieved > datetime.now(timezone.utc) + timedelta(minutes=5):
            return []
    except (ValueError, TypeError, KeyError):
        return []
    rows = snapshot.get("items")
    if not isinstance(rows, list):
        return []
    ticker = _ticker(security["ticker"])
    occupied = {str(row.get("price_date")) for row in existing}
    seen, records = set(), []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            day = date.fromisoformat(row["price_date"])
        except (ValueError, TypeError, KeyError):
            continue
        if day in seen:
            return []  # Conflicting revisions have no automatic selection rule.
        seen.add(day)
        value = row.get("price")
        try:
            numeric = type(value) in {int, float} and math.isfinite(value) and value > 0
        except OverflowError:
            numeric = False
        if (not numeric or not history_start <= day <= min(date.today(), retrieved.date())
                or day.isoformat() in occupied or row.get("currency") != currency
                or row.get("quote_unit") != "currency_per_share" or row.get("price_basis") != "close"
                or row.get("adjustment_basis") != "unadjusted"):
            continue
        source = row.get("source_url")
        try:
            parts = urlsplit(source)
            verified_source = (parts.scheme == "https" and parts.hostname == "eodhd.com"
                               and parts.path == f"/api/eod/{ticker}.US" and not parts.query and not parts.fragment
                               and not parts.username and not parts.password and parts.port in {None, 443})
        except (TypeError, ValueError):
            verified_source = False
        if not verified_source:
            continue
        observed = row.get("observed_at")
        if observed is not None:
            try:
                observed_time = datetime.fromisoformat(observed)
                if observed_time.tzinfo is None or observed_time > retrieved:
                    continue
            except (ValueError, TypeError):
                continue
        evidence = {"kind": "price_evidence_v1", "provider": "eodhd", "price_basis": "close",
                    "quote_unit": "currency_per_share", "currency": currency, "raw_price": value,
                    "adjustment_basis": "unadjusted", "source_url": source,
                    "observed_at": observed, "retrieved_at": retrieved.isoformat(),
                    "normalization": "raw_price", "quantity_convention": "recorded_fund_or_etf_shares"}
        records.append({**{key: metadata[key] for key in required}, "price_input": value,
                        "price_date": day.isoformat(), "source": "api_evidence",
                        "comments": json.dumps(evidence, ensure_ascii=False)})
    return records if any(date.fromisoformat(row["price_date"]) >= date.today() - timedelta(days=7) for row in records) else []
