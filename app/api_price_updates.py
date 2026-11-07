"""Pure conversion of identity-qualified API marks to the local price contract.

Only application-owned automatic refresh or authorized finalization persists these records.
The research agent never gets storage access or chooses a unit conversion.
"""
from datetime import date, datetime, timedelta, timezone
import json
import math

from .local_portfolio import normalize_price, _location_key
from .security_identifiers import valid_cusip, valid_isin


def local_bond_contract(candidate, metadata):
    if candidate.get("data_source") not in {"LOCAL", "MANUAL"} or not metadata:
        return False
    if metadata.get("currency") != "USD" or metadata.get("asset_class") != "BOND":
        return False
    if _location_key(metadata.get("location", "")) != "usa":
        return False
    if normalize_price(100, metadata.get("location", ""), "BOND") != 1:
        return False
    identifiers = {str(metadata.get(key) or "").upper() for key in ("symbol", "secondary_symbol")}
    return any(valid_cusip(value) or value.startswith("US") and valid_isin(value) for value in identifiers)


def bond_price_records(candidate, metadata, snapshot, existing, history_start):
    """Use $1 face per recorded local unit; retain actual provider mark basis."""
    if not local_bond_contract(candidate, metadata) or not isinstance(snapshot, dict):
        return []
    if snapshot.get("status") not in {"ok", "partial"} or snapshot.get("cache_status") == "stale":
        return []
    try:
        maturity = (snapshot.get("details") or {}).get("maturity_date")
        if snapshot.get("current_quote_eligible") is False or maturity and date.fromisoformat(maturity) < date.today():
            return []  # Keep historical reference prices without inventing a current mark.
    except (ValueError, TypeError):
        return []
    security = snapshot.get("security") or {}
    identifiers = {str(metadata.get(key) or "").upper() for key in ("symbol", "secondary_symbol")}
    if not identifiers.intersection({security.get("cusip"), security.get("isin")}):
        return []
    try:
        retrieved = datetime.fromisoformat(snapshot["retrieved_at"])
        if retrieved.tzinfo is None or retrieved > datetime.now(timezone.utc) + timedelta(minutes=5):
            return []
    except (ValueError, TypeError, KeyError):
        return []
    occupied = {str(item.get("price_date")) for item in existing}
    records = []
    for item in snapshot.get("items") or []:
        try:
            day = date.fromisoformat(item["price_date"])
        except (ValueError, TypeError, KeyError):
            continue
        if not history_start <= day <= min(date.today(), retrieved.date()) or day.isoformat() in occupied:
            continue
        if item.get("currency") != "USD" or item.get("quote_unit") != "percent_of_par":
            continue
        value = item.get("price")
        basis, side = item.get("price_basis"), item.get("side")
        # Prefer the official daily valuation. If it is unavailable, preserve
        # the source programme side appropriate to the signed local holding.
        if snapshot.get("provider") == "treasury_direct" and item.get("end_of_day_price") is None:
            short = candidate.get("quantity", 0) < 0
            side_value = item.get("programme_purchase_price" if short else "programme_redemption_price")
            if type(side_value) in {int, float} and math.isfinite(side_value) and side_value > 0:
                value = side_value
                basis = "programme_purchase" if short else "programme_redemption"
                side = "programme_purchase_mean" if short else "programme_redemption_bid"
        if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
            continue
        if basis not in {"valuation", "close", "last", "programme_purchase", "programme_redemption"}:
            continue
        source = item.get("source_url") or snapshot.get("source_url")
        if not isinstance(source, str) or not source.startswith("https://"):
            continue
        evidence = {"kind": "price_evidence_v1", "price_basis": basis,
                    "source_url": source, "retrieved_at": retrieved.isoformat(),
                    "observed_at": item.get("observed_at"), "quote_unit": "percent_of_par",
                    "side": side, "accrual_basis": item.get("accrual_basis", "unknown"),
                    "quantity_convention": "USD_1_face_per_recorded_unit", "provider": snapshot.get("provider"),
                    "raw_price": value, "normalization": "raw_price / 100"}
        records.append({**{key: metadata[key] for key in ("symbol", "stock_market", "currency", "asset_class", "location")},
                        "price_input": value, "price_date": day.isoformat(), "source": "api_evidence",
                        "comments": json.dumps(evidence, ensure_ascii=False)})
        occupied.add(day.isoformat())
    # Old history alone cannot resolve the missing-current-price requirement.
    return records if any(date.fromisoformat(row["price_date"]) >= date.today() - timedelta(days=7) for row in records) else []


def fund_price_records(candidate, metadata, snapshot, existing, history_start):
    """Map published ILS fund agorot exactly once, independently of nominal."""
    if (not metadata or candidate.get("data_source") not in {"LOCAL", "MANUAL"}
            or metadata.get("asset_class") not in {"MUTUALFUND", "FUND"}
            or metadata.get("currency") != "ILS"
            or normalize_price(100, metadata.get("location", ""), metadata["asset_class"]) != 1
            or not isinstance(snapshot, dict) or snapshot.get("status") not in {"ok", "partial"}
            or snapshot.get("cache_status") == "stale" or snapshot.get("provider") != "maya"):
        return []
    security = snapshot.get("security") or {}
    identifiers = {str(metadata.get(field) or "").lstrip("0") for field in ("symbol", "secondary_symbol")}
    if (security.get("fund_id") not in identifiers or security.get("deleted") is not False
            or security.get("dollar_denominated") is not False or security.get("is_international") is not False
            or security.get("fund_subtype") != 1):
        return []
    occupied = {str(row.get("price_date")) for row in existing}
    records = []
    try:
        retrieved = datetime.fromisoformat(snapshot["retrieved_at"])
        if retrieved.tzinfo is None or retrieved > datetime.now(timezone.utc) + timedelta(minutes=5):
            return []
    except (ValueError, TypeError, KeyError):
        return []
    for row in snapshot.get("items") or []:
        try:
            day = date.fromisoformat(row["price_date"])
        except (ValueError, TypeError, KeyError):
            continue
        value = row.get("price")
        if (not history_start <= day <= min(date.today(), retrieved.date()) or day.isoformat() in occupied
                or row.get("quote_unit") != "agorot" or row.get("currency") != "ILS"
                or row.get("price_basis") != "redemption" or type(value) not in {float, int}
                or not math.isfinite(value) or value <= 0
                or row.get("source_url") not in {snapshot.get("source_url"), str(snapshot.get("source_url")) + "/history"}):
            continue
        evidence = {"kind": "price_evidence_v1", "provider": "maya", "price_basis": "redemption",
                    "quote_unit": "agorot", "raw_price": value, "observed_at": None,
                    "retrieved_at": retrieved.isoformat(), "source_url": row["source_url"],
                    "normalization": "raw_price / 100", "purchase_price": row.get("purchase_price")}
        records.append({**{key: metadata[key] for key in ("symbol", "stock_market", "currency", "asset_class", "location")},
                        "price_input": value, "price_date": day.isoformat(), "source": "api_evidence",
                        "comments": json.dumps(evidence, ensure_ascii=False)})
        occupied.add(day.isoformat())
    return records if any(date.fromisoformat(row["price_date"]) >= date.today() - timedelta(days=7) for row in records) else []
