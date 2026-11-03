"""Read-only stock/fund exposure and latest observed native-price movement."""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
import math

from .optimization_data import ALLOWED_ASSETS, _class, _history, _positive, _finite_total


def _fx_evidence(market_hub, histories, currencies, today):
    """Use dated snapshots only. Reading a heatmap never calls an FX provider."""
    result = {}
    for currency in sorted(currencies - {"ILS"}):
        candidates = []
        for row in histories.get(currency, {}).get("rates", []):
            candidates.append((row.get("date"), row.get("rate"), histories[currency].get("source", "")))
        cache = getattr(market_hub, "cache", None)
        if cache is not None:
            for provider in getattr(market_hub, "providers", []):
                pair = f"{currency}/ILS"
                saved = cache.get_security_snapshot(provider.name, pair, "fx")
                if isinstance(saved, dict) and saved.get("pair") == pair:
                    candidates.append((str(saved.get("time") or "")[:10], saved.get("rate"), provider.name))
        valid = []
        for day, rate, source in candidates:
            try:
                observed = date.fromisoformat(day)
            except (TypeError, ValueError):
                continue
            if observed <= today and (number := _positive(rate)) is not None:
                valid.append((observed, number, source))
        last = max(valid, key=lambda row: row[0]) if valid else None
        result[currency] = {"currency": currency, "date": last[0].isoformat() if last else None,
                            "rate": last[1] if last else None, "source": last[2] if last else "",
                            "status": "missing_fx" if not last else "stale_fx" if (today-last[0]).days > 7 else "ok"}
    return result


class _RecentEvidence:
    def __init__(self, hub):
        self.hub = hub

    def cached_prices(self, *args, **kwargs):
        reader = getattr(self.hub, "cached_recent_prices", self.hub.cached_prices)
        return reader(*args, **kwargs)


def stock_heatmap(store, market_hub, fx_histories=None, *, account_id="", today=None, _account_views=True):
    today = today or date.today()
    accounts = store.list_accounts()
    if account_id and account_id not in {row["id"] for row in accounts}:
        raise ValueError("heatmap_unknown_account")
    groups, excluded = {}, []
    for analysis in store.holdings():
        holding = analysis.holding
        if account_id and holding.account_id != account_id:
            continue
        if holding.asset_class not in ALLOWED_ASSETS:
            excluded.append({"symbol": holding.symbol, "account_id": holding.account_id,
                             "asset_class": holding.asset_class, "reason": "unsupported_asset"})
            continue
        key = (holding.symbol.strip().upper(), holding.stock_market.strip().upper(), str(holding.currency or "").strip().upper())
        groups.setdefault(key, []).append(holding)
    fx = _fx_evidence(market_hub, fx_histories or {}, {key[2] for key in groups}, today)
    assets = []
    for (symbol, market, currency), holdings in sorted(groups.items()):
        classes = {_class(row.asset_class) for row in holdings}
        asset = {"id": sha256(repr((symbol, market, currency)).encode()).hexdigest()[:20],
                 "symbol": symbol, "stock_market": market, "currency": currency,
                 "name": holdings[0].name or symbol, "asset_class": _class(holdings[0].asset_class),
                 "secondary_symbol": holdings[0].secondary_symbol, "issues": [], "accounts": [],
                 "price": None, "price_date": None, "previous_price": None, "previous_date": None,
                 "change_percent": None, "gross_value_ils": None, "value_ils": None, "basis": "close"}
        issues = asset["issues"]
        if len(classes) > 1:
            issues.append("classification_conflict")
        quantities_valid = all(isinstance(row.quantity, (float, int)) and not isinstance(row.quantity, bool) and math.isfinite(row.quantity) for row in holdings)
        asset["quantity"] = _finite_total(row.quantity for row in holdings) if quantities_valid else None
        asset["gross_quantity"] = _finite_total(abs(row.quantity) for row in holdings) if quantities_valid else None
        if not quantities_valid or asset["quantity"] is None or asset["gross_quantity"] is None:
            issues.append("invalid_position")
        # Share the existing listing/currency qualification; use raw closes for
        # both valuation and movement so local raw overrides never mix scales.
        history = {}
        if "classification_conflict" not in issues:
            history = _history(store, _RecentEvidence(market_hub), asset, today-timedelta(days=45), today)[0]
        dates = sorted(history)
        if not dates:
            issues.append("missing_price")
        else:
            last = dates[-1]
            asset.update(price=history[last], price_date=last.isoformat())
            if (today-last).days > 7:
                issues.append("stale_price")
            if len(dates) < 2:
                issues.append("missing_previous_price")
            else:
                previous = dates[-2]
                asset.update(previous_price=history[previous], previous_date=previous.isoformat())
                if (last-previous).days > 7:
                    issues.append("sparse_prices")
                elif "stale_price" not in issues:
                    change = (history[last]/history[previous]-1)*100
                    if math.isfinite(change):
                        asset["change_percent"] = change
                    else:
                        issues.append("invalid_value")
        rate = 1.0 if currency == "ILS" else fx.get(currency, {}).get("rate")
        fx_status = "ok" if currency == "ILS" else fx.get(currency, {}).get("status", "missing_fx")
        if fx_status != "ok":
            issues.append(fx_status)
        valuation_ok = not any(code in issues for code in ("classification_conflict", "invalid_position", "missing_price", "stale_price", "missing_fx", "stale_fx", "invalid_value"))
        per_account = {}
        for row in holdings:
            per_account.setdefault(row.account_id, []).append(row.quantity)
        for key, quantities in sorted(per_account.items()):
            quantity = _finite_total(quantities) if quantities_valid else None
            gross = _finite_total(abs(value) for value in quantities) if quantities_valid else None
            signed_value = quantity*asset["price"]*rate if valuation_ok and quantity is not None else None
            gross_value = gross*asset["price"]*rate if valuation_ok and gross is not None else None
            if any(value is not None and not math.isfinite(value) for value in (signed_value, gross_value)):
                signed_value = gross_value = None
                if "invalid_value" not in issues:
                    issues.append("invalid_value")
            asset["accounts"].append({"account_id": key, "quantity": quantity, "gross_value_ils": gross_value, "value_ils": signed_value})
        if all(row["gross_value_ils"] is not None for row in asset["accounts"]):
            asset["gross_value_ils"] = _finite_total(row["gross_value_ils"] for row in asset["accounts"])
            asset["value_ils"] = _finite_total(row["value_ils"] for row in asset["accounts"])
            if asset["gross_value_ils"] is None or asset["value_ils"] is None:
                issues.append("invalid_value")
                asset["gross_value_ils"] = asset["value_ils"] = None
        # _history's weekly optimizer eligibility is irrelevant to two quotes.
        for key in ("eligible", "status", "basis", "from", "to", "adjusted_available"):
            asset.pop(key, None)
        asset.update(status="partial" if issues else "ok", basis="close")
        assets.append(asset)
    account_assets = {}
    if _account_views and not account_id:
        for account in accounts:
            account_assets[account["id"]] = stock_heatmap(store, market_hub, fx_histories, account_id=account["id"], today=today, _account_views=False)["assets"]
    return {"status": "empty" if not assets else "partial" if any(row["issues"] for row in assets) else "ok",
            "as_of": today.isoformat(), "currency": "ILS", "account_id": account_id,
            "accounts": accounts, "assets": assets, "account_assets": account_assets,
            "excluded": excluded, "fx": list(fx.values())}
