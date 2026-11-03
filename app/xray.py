"""Fund-constituent overlap from sourced snapshots; never infer index membership."""
from __future__ import annotations

import csv
import io
import math
import re
from datetime import date, datetime, timezone
from itertools import combinations
from urllib.parse import urlsplit

US_MARKETS = {"US", "NASDAQ", "NYSE", "NYSEARCA", "AMEX", "OTC"}
FUNDS = {"ETF", "MUTUALFUND"}
DIRECT = {"EQUITY", "RSU", "PRIVATE_STOCK"}
MAX_ROWS = 5000


class XrayError(ValueError):
    pass


def market_scope(market):
    market = str(market or "").strip().upper()
    if market in US_MARKETS:
        return "US"
    return "TASE" if market in {"TASE", "TLV", "TELAVIV"} else market


def snapshot_key(symbol, market):
    return f"xray_holdings_v1:{market_scope(market)}:{str(symbol).strip().upper()}"


def held_funds(store):
    return {(h.symbol.upper(), market_scope(h.stock_market)): h for a in store.holdings()
            if (h := a.holding).asset_class.upper() in FUNDS and abs(h.quantity) > 1e-9}


def require_fund(store, symbol, market):
    key = (str(symbol or "").strip().upper(), market_scope(market))
    fund = held_funds(store).get(key)
    if fund is None:
        raise XrayError("xray_fund_not_held")
    return fund


def read_snapshot(store, symbol, market):
    return store.get_preference(snapshot_key(symbol, market), None)


def normalize_snapshot(rows, *, as_of, source_name, source_url="", source_kind="local", today=None):
    today = today or date.today()
    try:
        day = date.fromisoformat(as_of) if as_of else None
    except (ValueError, TypeError):
        try:
            day = datetime.strptime(str(as_of), "%d/%m/%Y").date()
        except ValueError as exc:
            raise XrayError("xray_invalid_date") from exc
    if (source_kind == "local" and day is None) or (day and day > today):
        raise XrayError("xray_invalid_date")
    source_name = str(source_name or "").strip()
    source_url = str(source_url or "").strip()
    if not source_name or len(source_name) > 240:
        raise XrayError("xray_source_required")
    try:
        url = urlsplit(source_url)
    except ValueError as exc:
        raise XrayError("xray_invalid_source_url") from exc
    if source_url and (url.scheme not in {"http", "https"} or not url.netloc or url.username or url.password or len(source_url) > 1000):
        raise XrayError("xray_invalid_source_url")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise XrayError("xray_invalid_rows")
    cleaned, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise XrayError("xray_invalid_rows")
        symbol = str(row.get("symbol") or "").strip().upper()
        market = market_scope(row.get("market"))
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9 .^=-]{0,79}", symbol) or not re.fullmatch(r"[A-Z0-9_-]{1,40}", market):
            raise XrayError("xray_invalid_identity")
        try:
            weight = float(row.get("weight_percent"))
        except (TypeError, ValueError) as exc:
            raise XrayError("xray_invalid_weight") from exc
        if not math.isfinite(weight) or not 0 < weight <= 100:
            raise XrayError("xray_invalid_weight")
        if (symbol, market) in seen:
            raise XrayError("xray_duplicate_constituent")
        seen.add((symbol, market))
        asset_class = str(row.get("asset_class") or "UNKNOWN").strip().upper()
        if asset_class not in {"EQUITY", "ETF", "MUTUALFUND", "UNKNOWN"}:
            raise XrayError("xray_invalid_rows")
        cleaned.append({"symbol": symbol, "market": market, "weight_percent": weight,
                        "name": str(row.get("name") or "").strip()[:160], "asset_class": asset_class})
    total = math.fsum(row["weight_percent"] for row in cleaned)
    if total > 100.000001:
        raise XrayError("xray_weight_total")
    return {"holdings": cleaned, "as_of": day.isoformat() if day else None,
            "source_name": source_name, "source_url": source_url, "source_kind": source_kind,
            "covered_weight_percent": round(total, 6), "retrieved_at": datetime.now(timezone.utc).isoformat()}


def save_manual_report(store, payload):
    fund = require_fund(store, payload.get("symbol"), payload.get("stock_market"))
    content = payload.get("csv_text")
    if not isinstance(content, str) or len(content.encode("utf-8")) > 1_000_000:
        raise XrayError("xray_invalid_csv")
    try:
        reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")), strict=True)
        if not {"symbol", "market", "weight_percent"} <= set(reader.fieldnames or []):
            raise XrayError("xray_csv_columns")
        rows = []
        for row in reader:
            if None in row or len(rows) >= MAX_ROWS:
                raise XrayError("xray_invalid_rows")
            rows.append(row)
    except csv.Error as exc:
        raise XrayError("xray_invalid_csv") from exc
    snapshot = normalize_snapshot(rows, as_of=payload.get("as_of"), source_name=payload.get("source_name"), source_url=payload.get("source_url"))
    if any(row["symbol"] == fund.symbol.upper() and row["market"] == market_scope(fund.stock_market) for row in snapshot["holdings"]):
        raise XrayError("xray_self_holding")
    with store._sync_lock:
        require_fund(store, fund.symbol, fund.stock_market)
        store.set_preference(snapshot_key(fund.symbol, fund.stock_market), snapshot)
    return snapshot


def build_xray(store, account_id="", today=None):
    today = today or date.today()
    accounts = store.list_accounts()
    if account_id and account_id not in {row["id"] for row in accounts}:
        raise XrayError("xray_unknown_account")
    holdings = [a.holding for a in store.holdings() if abs(a.holding.quantity) > 1e-9
                and (not account_id or a.holding.account_id == account_id)]
    funds, direct, excluded = {}, {}, []
    for h in holdings:
        if h.asset_class.upper() in FUNDS:
            funds.setdefault((h.symbol.upper(), market_scope(h.stock_market)), []).append(h)
            direct.setdefault((h.symbol.upper(), market_scope(h.stock_market)), []).append(h)
        elif h.asset_class.upper() in DIRECT:
            direct.setdefault((h.symbol.upper(), market_scope(h.stock_market)), []).append(h)
        else:
            excluded.append({"symbol": h.symbol, "stock_market": h.stock_market, "asset_class": h.asset_class})
    by_security, coverage, maps = {}, [], {}
    fund_scopes = {(s, market_scope(m)) for s, m in funds}
    for (symbol, market), positions in sorted(funds.items()):
        snapshot = read_snapshot(store, symbol, market)
        reported = snapshot.get("holdings", []) if snapshot else []
        report_day = date.fromisoformat(snapshot["as_of"]) if snapshot and snapshot.get("as_of") else None
        meta = {"symbol": symbol, "stock_market": market, "name": positions[0].name,
                "positions": [{"account_id": h.account_id, "quantity": h.quantity} for h in positions],
                "status": "missing" if not snapshot else "undated" if not report_day else "stale" if (today - report_day).days > 45 else "available",
                "as_of": snapshot.get("as_of") if snapshot else None,
                "retrieved_at": snapshot.get("retrieved_at") if snapshot else None,
                "source_name": snapshot.get("source_name") if snapshot else None,
                "source_url": snapshot.get("source_url") if snapshot else None,
                "source_kind": snapshot.get("source_kind") if snapshot else None,
                "covered_weight_percent": snapshot.get("covered_weight_percent", 0) if snapshot else 0,
                "constituent_count": len(reported)}
        nested = 0
        mapping = {}
        for row in reported:
            key = (row["symbol"], row["market"])
            # Identify nested funds only with explicit class or a held listing;
            # unknown classes remain disclosed rather than guessed from names.
            is_nested = row.get("asset_class") in FUNDS or key in fund_scopes
            nested += bool(is_nested)
            mapping[key] = row["weight_percent"]
            exposure = by_security.setdefault(key, {"symbol": row["symbol"], "market": row["market"], "name": row.get("name", ""), "funds": []})
            exposure["funds"].append({"symbol": symbol, "stock_market": market, "weight_percent": row["weight_percent"], "nested": is_nested})
        meta["nested_constituents"] = nested
        maps[(symbol, market)] = mapping
        coverage.append(meta)
    overlaps = []
    for key, exposure in sorted(by_security.items()):
        positions = direct.get(key, [])
        if len(exposure["funds"]) + bool(positions) < 2:
            continue
        overlaps.append({**exposure, "direct": [{"symbol": h.symbol, "stock_market": h.stock_market,
                         "account_id": h.account_id, "quantity": h.quantity} for h in positions]})
    pairs = []
    for left, right in combinations(sorted(maps), 2):
        shared = maps[left].keys() & maps[right].keys()
        if shared:
            pairs.append({"left": {"symbol": left[0], "stock_market": left[1]},
                          "right": {"symbol": right[0], "stock_market": right[1]},
                          "shared_count": len(shared), "observed_overlap_percent": round(math.fsum(min(maps[left][key], maps[right][key]) for key in shared), 6)})
    overlaps.sort(key=lambda row: (not bool(row["direct"]), -len(row["funds"]), row["symbol"]))
    return {"accounts": accounts, "funds": coverage, "overlaps": overlaps, "fund_pairs": pairs,
            "fund_count": len(funds), "direct_count": len(direct), "excluded": excluded,
            "has_shorts": any(h.quantity < 0 for h in holdings), "account_id": account_id}
