"""Read-only security exposure and latest observed native-price movement."""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import math

from .optimization_data import ALLOWED_ASSETS, PROVIDER_MARKETS, _class, _history, _positive, _finite_total
from .investment_scope import investments

SUPPORTED_ASSETS = ALLOWED_ASSETS | {"BOND"}


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _unrealized(holdings, price):
    """Recorded remaining cost basis and signed position price P/L, per currency."""
    if price is None or any(not _finite(row.cost_basis) or not _finite(row.quantity) for row in holdings):
        return None
    return _finite_total(row.quantity * price - row.cost_basis if row.quantity >= 0
                         else abs(row.cost_basis) - abs(row.quantity) * price for row in holdings)


def _recorded_exposure(holdings):
    """Use local recorded amounts as estimates, never as observed prices."""
    values, bases = [], set()
    for row in holdings:
        if row.quantity == 0:
            return None, None, "unavailable"
        value, cost = row.market_value, row.cost_basis
        if _finite(value) and value != 0 and value * row.quantity > 0:
            basis = "cost_basis" if _finite(cost) and math.isclose(abs(value), abs(cost)) else "recorded_value"
        elif _finite(cost) and cost != 0:
            value = abs(cost) if row.quantity > 0 else -abs(cost)
            basis = "cost_basis"
        else:
            return None, None, "unavailable"
        values.append(value)
        bases.add(basis)
    return (_finite_total(values), _finite_total(abs(value) for value in values),
            next(iter(bases)) if len(bases) == 1 else "mixed")


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

    def __getattr__(self, key):
        return getattr(self.hub, key)


def stock_heatmap(store, market_hub, fx_histories=None, *, account_id="", today=None, _account_views=True):
    store = investments(store)
    today = today or date.today()
    accounts = store.list_accounts()
    if account_id and account_id not in {row["id"] for row in accounts}:
        raise ValueError("heatmap_unknown_account")
    groups, excluded = {}, []
    for analysis in store.holdings():
        holding = analysis.holding
        if account_id and holding.account_id != account_id:
            continue
        if holding.asset_class not in SUPPORTED_ASSETS:
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
                 "change_percent": None, "gross_value_ils": None, "value_ils": None, "basis": "close",
                 "valuation_basis": "unavailable", "valuation_status": "unavailable",
                 "cost_basis_native": None, "unrealized_pnl_native": None, "unrealized_pnl_ils": None}
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
            history = _history(store, _RecentEvidence(market_hub), asset, date.min, today)[0]
        if asset["name"].strip().upper() == symbol and asset.get("history_identity") == "verified" and callable(getattr(market_hub, "cached_view", None)):
            manual = store.manual_security(symbol, market)
            profile = market_hub.cached_view().profile(symbol, stock_market=asset.get("resolved_stock_market") or market,
                         secondary_symbol=(manual or {}).get("secondary_symbol") or asset["secondary_symbol"])[0]
            name = profile.get("name") or profile.get("company_name")
            profile_currency = str(profile.get("currency") or "").strip().upper()
            if isinstance(name, str) and name.strip() and (not profile_currency or profile_currency == currency):
                asset["name"] = name.strip()
        dates = sorted(history)
        if not dates:
            issues.append("unverified_listing" if market in PROVIDER_MARKETS and asset.get("history_identity") == "local_only" else "missing_price")
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
        structural_ok = not any(code in issues for code in ("classification_conflict", "invalid_position", "unverified_listing", "invalid_value"))
        # Local holding values can themselves come from a rejected local quote.
        # Do not let a fallback bypass currency/class/date qualification. With no
        # price records, the recorded amount/cost remains an explicit estimate.
        recorded_ok = structural_ok and not history and not store.price_history(symbol, market)
        valuation_ok = structural_ok and rate is not None
        per_account = {}
        for row in holdings:
            per_account.setdefault(row.account_id, []).append(row)
        native_price = asset["price"] if asset["price"] is not None and not any(code in issues for code in ("stale_price", "classification_conflict", "invalid_position")) else None
        for key, positions in sorted(per_account.items()):
            quantities = [row.quantity for row in positions]
            quantity = _finite_total(quantities) if quantities_valid else None
            gross = _finite_total(abs(value) for value in quantities) if quantities_valid else None
            basis = "unavailable"
            native_value = native_gross = None
            if structural_ok and quantity is not None and gross is not None:
                if asset["price"] is not None:
                    native_value, native_gross = quantity * asset["price"], gross * asset["price"]
                    basis = "saved_price"
                elif recorded_ok:
                    native_value, native_gross, basis = _recorded_exposure(positions)
                    if native_value is not None and native_gross is not None and "estimated_value" not in issues:
                        issues.append("estimated_value")
            signed_value = native_value * rate if valuation_ok and native_value is not None else None
            gross_value = native_gross * rate if valuation_ok and native_gross is not None else None
            if any(value is not None and not math.isfinite(value) for value in (signed_value, gross_value)):
                signed_value = gross_value = None
                if "invalid_value" not in issues:
                    issues.append("invalid_value")
            cost = _finite_total(row.cost_basis for row in positions) if all(_finite(row.cost_basis) for row in positions) else None
            pnl = _unrealized(positions, native_price)
            pnl_ils = _finite_total([pnl * rate]) if pnl is not None and fx_status == "ok" else None
            asset["accounts"].append({"account_id": key, "quantity": quantity, "gross_value_ils": gross_value, "value_ils": signed_value,
                                      "valuation_basis": basis,
                                      "valuation_status": "unavailable" if gross_value is None else "estimated" if basis != "saved_price"
                                          else "stale" if "stale_price" in issues or fx_status == "stale_fx" else "current",
                                      "cost_basis_native": cost, "unrealized_pnl_native": pnl, "unrealized_pnl_ils": pnl_ils,
                                      "pnl_status": "invalid_cost_basis" if cost is None else "ok" if pnl is not None else "unavailable"})
        for field in ("cost_basis_native", "unrealized_pnl_native", "unrealized_pnl_ils"):
            asset[field] = _finite_total(row[field] for row in asset["accounts"]) if all(row[field] is not None for row in asset["accounts"]) else None
        if all(row["gross_value_ils"] is not None for row in asset["accounts"]):
            asset["gross_value_ils"] = _finite_total(row["gross_value_ils"] for row in asset["accounts"])
            asset["value_ils"] = _finite_total(row["value_ils"] for row in asset["accounts"])
            if asset["gross_value_ils"] is None or asset["value_ils"] is None:
                issues.append("invalid_value")
                asset["gross_value_ils"] = asset["value_ils"] = None
        if asset["gross_value_ils"] is not None:
            bases = {row["valuation_basis"] for row in asset["accounts"]}
            asset["valuation_basis"] = next(iter(bases)) if len(bases) == 1 else "mixed"
            statuses = {row["valuation_status"] for row in asset["accounts"]}
            asset["valuation_status"] = "estimated" if "estimated" in statuses else "stale" if "stale" in statuses else "current"
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
