"""Public MAYA fund observations, with source basis and units kept explicit.

The official site currently uses these routes itself. They are public website
interfaces, not a promised stable or complete market-data subscription. Standard
domestic ILS fund prices are quoted in agorot per issued unit. A fund's nominal
denomination does not multiply this quoted price. No portfolio storage is accessed.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import math
import re
from typing import Any

from .us_market_providers import _Adapter, ProviderFailure, RequestBudget


BASE_URL = "https://maya.tase.co.il"


def _identifier(value: Any) -> str:
    text = str(value).strip()
    if not re.fullmatch(r"[0-9]{5,8}", text) or int(text) <= 0:
        raise ProviderFailure("missing_identifier", "An exact Israeli fund number is required.")
    return str(int(text))


def _date(value: Any) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T[0-9:.+Z-]+)?", value):
        raise ProviderFailure("invalid_response", "The fund observation has no valid date.")
    try:
        result = date.fromisoformat(value[:10])
    except ValueError:
        raise ProviderFailure("invalid_response", "The fund observation has no valid date.") from None
    if result > date.today():
        raise ProviderFailure("invalid_response", "Future fund observations are unsupported.")
    return result


def _price(value: Any) -> float | None:
    if value is None:
        return None
    if type(value) not in {int, float}:
        raise ProviderFailure("invalid_response", "Invalid fund price.")
    try:
        if not math.isfinite(value) or value < 0:
            raise ValueError()
    except (ValueError, OverflowError):
        raise ProviderFailure("invalid_response", "Invalid fund price.") from None
    return float(value)


class MayaFundProvider(_Adapter):
    name = "maya"
    allowed_host = "maya.tase.co.il"

    def _history(self, client, budget, url, identifier, start, end, observation):
        response = self._request(client, budget, "POST", url,
            json={"pageSize": 30, "pageNumber": 1, "fromDate": start.isoformat(), "toDate": end.isoformat(), "period": 4})
        if response.is_redirect:
            raise ProviderFailure("invalid_response", "The fund source returned an unexpected redirect.")
        try:
            raw_rows = response.json()
        except ValueError:
            raise ProviderFailure("invalid_response", "The fund source returned invalid history.") from None
        if not isinstance(raw_rows, list) or len(raw_rows) > 30:
            raise ProviderFailure("invalid_response", "The fund source returned invalid history.")
        total = None
        total_text = response.headers.get("x-total-count")
        if total_text is not None:
            if not re.fullmatch(r"\d+", total_text):
                raise ProviderFailure("invalid_response", "The fund history count is invalid.")
            total = int(total_text)
            if total < len(raw_rows):
                raise ProviderFailure("invalid_response", "The fund history count is inconsistent.")
        rows, seen = [], set()
        for raw in raw_rows:
            if not isinstance(raw, dict) or _identifier(raw.get("fundId")) != identifier:
                raise ProviderFailure("identity_mismatch", "The source returned another fund's history.")
            item = observation(raw)
            if item is None:
                continue
            day = date.fromisoformat(item["price_date"])
            if not start <= day <= end:
                continue
            if day in seen:
                raise ProviderFailure("invalid_response", "Duplicate fund dates have no revision rule.")
            seen.add(day)
            rows.append(item)
        return rows, total, total is None or total > len(raw_rows)

    def fetch(self, fund_id: str, start: date, end: date, budget: RequestBudget, *,
              price_basis: str = "redemption") -> dict[str, Any]:
        """Fetch current identity and one bounded history page (at most two reads).

        Redemption is the explicit default valuation policy for held funds;
        purchase remains separately available. This adapter never labels either
        field NAV or an exchange close. Additional historical pages can be
        requested by the application with a separate, bounded lookup.
        """
        identifier = _identifier(fund_id)
        if not isinstance(start, date) or not isinstance(end, date) or start > end or end > date.today():
            raise ValueError("Fund price dates must be ordered and not in the future")
        if price_basis not in {"redemption", "purchase"}:
            raise ValueError("Choose redemption or purchase fund prices")
        current_url = f"{BASE_URL}/api/v1/funds/mutual/{identifier}"
        history_url = current_url + "/history"
        with self._client_context() as client:
            profile = self._json(client, budget, current_url)
            if not isinstance(profile, dict) or _identifier(profile.get("fundId")) != identifier:
                raise ProviderFailure("identity_mismatch", "The source returned another fund.")
            if type(profile.get("fundTypeId")) is not int or profile.get("fundTypeId") != 1 or profile.get("fundType") != "קרן פתוחה":
                raise ProviderFailure("unsupported", "The source did not identify an open mutual fund.")
            # This exact published feature says denomination, unlike exposure.
            dollar_features = [entry.get("enabled") for entry in profile.get("features") or []
                               if isinstance(entry, dict) and entry.get("title") == "יחידות הקרן נקובות ב- $"]
            dollars = dollar_features[0] if len(dollar_features) == 1 and type(dollar_features[0]) is bool else None
            ordinary_ils = (dollars is False and profile.get("isInternational") is False
                            and type(profile.get("mutualFundSubType")) is int and profile.get("mutualFundSubType") == 1)

            def observation(row: dict[str, Any], *, current: bool = False) -> dict[str, Any] | None:
                day = _date(row.get("ratesAsOf") if current else row.get("tradeDate"))
                purchase = _price(row.get("purchasePrice"))
                redemption = _price(row.get("redemptionPrice") if current else row.get("sellPrice"))
                selected = redemption if price_basis == "redemption" else purchase
                if selected is None:
                    return None
                item = {"price": selected, "price_date": day.isoformat(), "price_basis": price_basis,
                        "quote_unit": "agorot" if ordinary_ils else "unknown", "currency": "ILS" if ordinary_ils else None,
                        "purchase_price": purchase, "redemption_price": redemption,
                        "side": price_basis, "adjustment_basis": "source_published_not_total_return",
                        "source_url": current_url if current else history_url,
                        "provider": self.name, "observed_at": None,
                        "unit_origin": "maya_domestic_ils_fund_price_contract" if ordinary_ils else "unqualified_source_unit",
                        "normalization_supported": ordinary_ils}
                if ordinary_ils:
                    normalized = selected / 100
                    if not math.isfinite(normalized):
                        raise ProviderFailure("invalid_response", "The normalized fund price is not finite.")
                    item["currency_per_unit"] = normalized
                return item

            current = observation(profile, current=True) if profile.get("ratesAsOf") else None
            rows, total, truncated = [], None, True
            history_error = None
            if budget.remaining:
                try:
                    rows, total, truncated = self._history(client, budget, history_url, identifier, start, end, observation)
                except ProviderFailure as exc:
                    if exc.code not in {"access_denied", "rate_limited", "not_found", "unavailable", "timeout", "request_limit"}:
                        raise
                    history_error = exc.code
            else:
                history_error = "request_limit"
            history_count = len(rows)
            added_current = False
            if current and start <= date.fromisoformat(current["price_date"]) <= end:
                match = next((row for row in rows if row["price_date"] == current["price_date"]), None)
                if match and (match["purchase_price"], match["redemption_price"]) != (current["purchase_price"], current["redemption_price"]):
                    raise ProviderFailure("invalid_response", "Current and historical fund prices disagree.")
                if not match:
                    rows.append(current)
                    added_current = True
            rows.sort(key=lambda row: row["price_date"])
            latest = rows[-1] if rows else None
            quote = current if end == date.today() else None
            deleted = profile.get("deleted") is True
            return {"provider": self.name, "status": "partial" if truncated or not rows else "ok",
                    "security": {"fund_id": identifier, "isin": profile.get("isin"), "name": profile.get("longName") or profile.get("name"),
                                 "kind": "fund", "deleted": deleted, "dollar_denominated": dollars,
                                 "is_international": profile.get("isInternational"), "fund_subtype": profile.get("mutualFundSubType")},
                    "items": rows, "quote": quote, "latest_in_range": latest,
                    "quote_status": "missing" if quote is None else "stale" if (date.today() - date.fromisoformat(quote["price_date"])).days > 7 else "dated",
                    "details": profile, "details_scope": "latest_provider_profile_not_historical_point_in_time",
                    "coverage": {"complete": False, "published_records_complete": not truncated,
                                 "requested_from": start.isoformat(), "requested_to": end.isoformat(),
                                 "count": len(rows), "total_available": total, "truncated": truncated,
                                 "history_count": history_count, "current_observation_added": added_current,
                                 "next_page": 2 if truncated and total else None,
                                 "first_observation": rows[0]["price_date"] if rows else None,
                                 "last_observation": latest["price_date"] if latest else None},
                    "source_url": current_url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "provider_requests": budget.used, "history_error": history_error, "portfolio_updated": False,
                    "warnings": ["Redemption and purchase are fund valuation bases, not exchange Last/Close or total-return prices.",
                                 "Only qualified standard domestic ILS fund quotes are normalized as agorot; other denominations retain unknown units."]}


# Descriptive alias for callers discovering the Israeli-specific adapter.
IsraeliFundProvider = MayaFundProvider
