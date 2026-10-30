"""Read-only trade-planning context. Sizing uses the dashboard's shared risk model."""
from copy import deepcopy
from datetime import date, timedelta

from .metrics import price_range_metrics
from .models import Ohlcv


def planner_security(symbol, market, items, market_hub, normalize_market, us_markets, local_store=None):
    matches = [item for item in items if item.get("holding", {}).get("symbol", "").upper() == symbol]
    if market:
        matches = [item for item in matches if normalize_market(item.get("holding", {}).get("stock_market")) == market
                   or normalize_market(item.get("exchange")) == market]
    identities = {(item["holding"].get("currency"), normalize_market(item["holding"].get("stock_market"))) for item in matches}
    if len(identities) > 1:
        return None, "ambiguous_listing"
    if matches:
        return deepcopy(matches[0]), None
    # Saved local instruments (including TASE) can be planned before they are
    # held. Keep their normalized prices and listing/currency identity intact.
    if local_store is not None and market:
        instrument = local_store.manual_security(symbol, market)
        if instrument and instrument.get("asset_class") in {"EQUITY", "ETF"}:
            history = local_store.price_history(symbol, market, to_date=date.today())
            prices = [Ohlcv(date.fromisoformat(row["price_date"]), *([float(row["price"])] * 5), 0)
                      for row in history if row.get("currency") == instrument.get("currency")]
            return {"holding": {"symbol": instrument["symbol"], "name": instrument.get("name") or symbol,
                                "stock_market": market, "currency": instrument["currency"],
                                "asset_class": instrument["asset_class"], "quantity": 0, "market_value": 0},
                    "exchange": market, "price_ranges": price_range_metrics(prices), "missing": []}, None
    # A user-entered exchange or USD currency alone is not listing evidence.
    quote, _ = market_hub.quote(symbol)
    profile, _ = market_hub.profile(symbol, stock_market=market)
    supported = {*us_markets, "TASE"}
    listings = {normalize_market(value) for value in (quote.get("exchange"), profile.get("exchange"))}
    verified = listings & supported
    if len(verified) != 1:
        return None, "listing_unverified"
    detected = next(iter(verified))
    generic = {"", "US", "USA", "SEC", "YAHOO", "MANUAL"}
    if any(listing not in generic and listing != detected for listing in listings):
        return None, "listing_unverified"
    currency = str(quote.get("currency") or profile.get("currency") or ("USD" if detected in us_markets else "")).upper()
    if ((market and detected != market)
            or (detected == "TASE" and currency != "ILS")
            or (detected in us_markets and currency != "USD")
            or (quote.get("symbol") and str(quote["symbol"]).upper() != symbol)):
        return None, "listing_unverified"
    prices, _ = market_hub.prices(symbol, date.today() - timedelta(days=370), date.today(), stock_market=detected)
    ranges = price_range_metrics(prices)
    return {
        "holding": {"symbol": symbol, "name": quote.get("name") or profile.get("name") or symbol,
                    "asset_class": "EQUITY", "stock_market": detected, "currency": currency,
                    "quantity": 0, "market_value": 0, "sector": profile.get("sector") or "",
                    "industry": profile.get("industry") or ""},
        "exchange": detected, "industry": profile.get("industry") or "",
        "price_ranges": ranges, "missing": [],
    }, None
