from __future__ import annotations

from datetime import date
from typing import Any

from .models import Holding
from .postgres import connect_postgres


class GhostfolioClient:
    def __init__(self, db_config: dict[str, Any]):
        self.db_config = db_config

    def _connect(self):
        return connect_postgres(self.db_config)

    def load_holdings(self) -> tuple[list[Holding], dict[str, str]]:
        if not self.db_config.get("host"):
            return sample_holdings(), {"ghostfolio": "missing config"}

        try:
            with self._connect() as conn:
                tables = self._tables(conn)
                order_table = self._pick(tables, ["Order", "orders", "Activity", "activities"])
                profile_table = self._pick(tables, ["SymbolProfile", "symbol_profiles", "AssetProfile"])
                account_table = self._pick(tables, ["Account", "accounts"])
                platform_table = self._pick(tables, ["Platform", "platforms"])
                if not order_table:
                    return sample_holdings(), {"ghostfolio": "order table not found"}
                rows = self._load_order_rows(conn, order_table, profile_table, account_table, platform_table)
                market_prices = self._load_latest_market_prices(conn) if "MarketData" in tables else {}
                holdings = self._aggregate(rows, market_prices)
                return holdings, {"ghostfolio": f"ok ({len(holdings)} positions)"}
        except Exception as exc:
            return sample_holdings(), {"ghostfolio": f"error: {exc.__class__.__name__}"}

    def load_account_cash(self) -> tuple[list[dict[str, Any]], dict[str, str]]:
        if not self.db_config.get("host"):
            return [], {"ghostfolio_accounts": "missing config"}

        try:
            with self._connect() as conn:
                tables = self._tables(conn)
                account_table = self._pick(tables, ["Account", "accounts"])
                platform_table = self._pick(tables, ["Platform", "platforms"])
                balance_table = self._pick(tables, ["AccountBalance", "account_balances"])
                if not account_table:
                    return [], {"ghostfolio_accounts": "account table not found"}
                rows = self._load_account_cash_rows(conn, account_table, platform_table, balance_table)
                return rows, {"ghostfolio_accounts": f"ok ({len(rows)} accounts)"}
        except Exception as exc:
            return [], {"ghostfolio_accounts": f"error: {exc.__class__.__name__}"}

    def load_order_transactions(self) -> tuple[list[dict[str, Any]], dict[str, str]]:
        if not self.db_config.get("host"):
            return [], {"source_orders": "missing config"}

        try:
            with self._connect() as conn:
                tables = self._tables(conn)
                order_table = self._pick(tables, ["Order", "orders", "Activity", "activities"])
                profile_table = self._pick(tables, ["SymbolProfile", "symbol_profiles", "AssetProfile"])
                account_table = self._pick(tables, ["Account", "accounts"])
                platform_table = self._pick(tables, ["Platform", "platforms"])
                if not order_table:
                    return [], {"source_orders": "order table not found"}
                rows = self._load_order_rows(conn, order_table, profile_table, account_table, platform_table)
        except Exception as exc:
            return [], {"source_orders": f"error: {exc.__class__.__name__}"}

        transactions = []
        for row in rows:
            symbol = str(row.get("symbol") or row.get("order_symbol") or "").upper()
            if not symbol:
                continue
            quantity = abs(float(row.get("quantity") or 0))
            if quantity <= 0:
                continue
            kind = str(row.get("activity_type") or "BUY").upper()
            action = "REMOVE" if kind == "SELL" else "ADD"
            asset_class = _asset_class(row.get("asset_class"), row.get("asset_sub_class"))
            currency = row.get("profile_currency") or row.get("currency") or "USD"
            day = row["trade_date"].date() if hasattr(row.get("trade_date"), "date") else row.get("trade_date")
            transactions.append(
                {
                    "account": str(row.get("account") or ""),
                    "account_currency": str(row.get("account_currency") or currency or "USD").upper(),
                    "platform": str(row.get("platform") or ""),
                    "action": action,
                    "source_type": kind,
                    "symbol": symbol,
                    "name": str(row.get("name") or symbol),
                    "stock_market": str(row.get("stock_market") or row.get("data_source") or "MANUAL").upper(),
                    "asset_class": asset_class,
                    "asset_sub_class": str(row.get("asset_sub_class") or ""),
                    "quantity": quantity,
                    "price": abs(float(row.get("price") or 0)),
                    "currency": str(currency or "USD").upper(),
                    "location": "Israel" if str(currency or "").upper() == "ILS" else "USA",
                    "trade_date": day.isoformat() if hasattr(day, "isoformat") else str(day)[:10],
                    "comments": f"Imported source {kind}",
                }
            )
        return transactions, {"source_orders": f"ok ({len(transactions)} transactions)"}

    def load_market_history(self, holdings: list[Holding], from_date: date | None = None) -> tuple[list[dict[str, Any]], dict[str, str]]:
        if not self.db_config.get("host") or not holdings:
            return [], {"source_price_history": "missing config or no holdings"}
        symbols = sorted({holding.symbol.upper() for holding in holdings if holding.symbol})
        if not symbols:
            return [], {"source_price_history": "no symbols"}

        try:
            with self._connect() as conn:
                tables = self._tables(conn)
                if "MarketData" not in tables:
                    return [], {"source_price_history": "MarketData table not found"}
                args: list[Any] = [symbols]
                from_filter = ""
                if from_date:
                    from_filter = "and date >= %s"
                    args.append(from_date)
                rows = conn.execute(
                    f"""
                    select symbol, "dataSource" as data_source, date, "marketPrice" as market_price
                    from "MarketData"
                    where upper(symbol) = any(%s)
                      and "marketPrice" is not null
                      {from_filter}
                    order by symbol, date
                    """,
                    args,
                ).fetchall()
        except Exception as exc:
            return [], {"source_price_history": f"error: {exc.__class__.__name__}"}

        holdings_by_symbol = {holding.symbol.upper(): holding for holding in holdings if holding.symbol}
        history = []
        for row in rows:
            symbol = str(row.get("symbol") or "").upper()
            holding = holdings_by_symbol.get(symbol)
            if not holding:
                continue
            day = row["date"].date() if hasattr(row.get("date"), "date") else row.get("date")
            history.append(
                {
                    "symbol": symbol,
                    "stock_market": str(row.get("data_source") or holding.stock_market or holding.data_source or "MANUAL").upper(),
                    "asset_class": holding.asset_class,
                    "location": "Israel" if holding.currency == "ILS" else "USA",
                    "currency": holding.currency,
                    "price": float(row.get("market_price") or 0),
                    "price_date": day.isoformat() if hasattr(day, "isoformat") else str(day)[:10],
                    "source": "source_import",
                }
            )
        return history, {"source_price_history": f"ok ({len(history)} prices)"}

    def _tables(self, conn) -> set[str]:
        rows = conn.execute(
            "select table_name from information_schema.tables where table_schema = 'public'"
        ).fetchall()
        return {row["table_name"] for row in rows}

    def _columns(self, conn, table: str) -> set[str]:
        rows = conn.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema = 'public' and table_name = %s
            """,
            (table,),
        ).fetchall()
        return {row["column_name"] for row in rows}

    def _pick(self, tables: set[str], candidates: list[str]) -> str | None:
        for candidate in candidates:
            if candidate in tables:
                return candidate
        return None

    def _q(self, name: str) -> str:
        return '"' + name.replace('"', '""') + '"'

    def _load_order_rows(
        self,
        conn,
        order_table: str,
        profile_table: str | None,
        account_table: str | None,
        platform_table: str | None,
    ):
        order_cols = self._columns(conn, order_table)
        symbol_col = next((c for c in ["symbol", "Symbol", "dataSourceSymbol"] if c in order_cols), None)
        symbol_profile_id_col = next((c for c in ["symbolProfileId", "symbol_profile_id"] if c in order_cols), None)
        quantity_col = next((c for c in ["quantity", "shares"] if c in order_cols), None)
        price_col = next((c for c in ["unitPrice", "price", "unit_price"] if c in order_cols), None)
        currency_col = next((c for c in ["currency", "Currency"] if c in order_cols), None)
        account_id_col = next((c for c in ["accountId", "account_id"] if c in order_cols), None)
        type_col = next((c for c in ["type", "activityType"] if c in order_cols), None)
        fee_col = next((c for c in ["fee", "fees"] if c in order_cols), None)

        if not quantity_col:
            return []

        select_parts = [
            "o.date as trade_date",
            f'o.{self._q(symbol_col)} as order_symbol' if symbol_col else "'' as order_symbol",
            f'o.{self._q(quantity_col)} as quantity',
            f'o.{self._q(price_col)} as price' if price_col else "0 as price",
            f'o.{self._q(currency_col)} as currency' if currency_col else "'USD' as currency",
            f'o.{self._q(type_col)} as activity_type' if type_col else "'BUY' as activity_type",
            f'o.{self._q(fee_col)} as fee' if fee_col else "0 as fee",
        ]
        joins = []

        if profile_table:
            profile_cols = self._columns(conn, profile_table)
            pid = next((c for c in ["id", "symbolProfileId"] if c in profile_cols), None)
            psym = next((c for c in ["symbol", "Symbol", "dataSourceSymbol"] if c in profile_cols), None)
            if pid and symbol_profile_id_col:
                joins.append(f"left join {self._q(profile_table)} p on p.{self._q(pid)} = o.{self._q(symbol_profile_id_col)}")
            elif psym and symbol_col:
                joins.append(f"left join {self._q(profile_table)} p on p.{self._q(psym)} = o.{self._q(symbol_col)}")
            if joins:
                select_parts.extend(
                    [
                        f"p.{self._q(psym)} as symbol" if psym else "'' as symbol",
                        f"p.{self._q(c)} as name" if (c := next((x for x in ["name", "Name"] if x in profile_cols), None)) else "'' as name",
                        f"p.{self._q(c)} as asset_class" if (c := next((x for x in ["assetClass", "asset_class"] if x in profile_cols), None)) else "'UNKNOWN' as asset_class",
                        f"p.{self._q(c)} as asset_sub_class" if (c := next((x for x in ["assetSubClass", "asset_sub_class"] if x in profile_cols), None)) else "'' as asset_sub_class",
                        f"p.{self._q(c)} as data_source" if (c := next((x for x in ["dataSource", "data_source"] if x in profile_cols), None)) else "'' as data_source",
                        f"p.{self._q(c)} as stock_market" if (c := next((x for x in ["stockExchange", "stock_exchange", "exchange", "market", "exchangeCode", "exchange_code"] if x in profile_cols), None)) else "'' as stock_market",
                        f"p.{self._q(c)} as profile_currency" if (c := next((x for x in ["currency", "Currency"] if x in profile_cols), None)) else "'' as profile_currency",
                        f"p.{self._q(c)} as country" if (c := next((x for x in ["country", "countries"] if x in profile_cols), None)) else "null as country",
                        f"p.{self._q(c)} as sector" if (c := next((x for x in ["sector", "sectors"] if x in profile_cols), None)) else "null as sector",
                        f"p.{self._q(c)} as industry" if (c := next((x for x in ["industry", "industries"] if x in profile_cols), None)) else "'' as industry",
                    ]
                )
            else:
                select_parts.extend(["o." + self._q(symbol_col) + " as symbol" if symbol_col else "'' as symbol", "'' as name", "'UNKNOWN' as asset_class", "'' as asset_sub_class", "'' as data_source", "'' as stock_market", "'' as profile_currency", "null as country", "null as sector", "'' as industry"])
        else:
            select_parts.extend(["o." + self._q(symbol_col) + " as symbol" if symbol_col else "'' as symbol", "'' as name", "'UNKNOWN' as asset_class", "'' as asset_sub_class", "'' as data_source", "'' as stock_market", "'' as profile_currency", "null as country", "null as sector", "'' as industry"])

        if account_table and account_id_col:
            account_cols = self._columns(conn, account_table)
            aid = next((c for c in ["id", "accountId"] if c in account_cols), None)
            aname = next((c for c in ["name", "Name"] if c in account_cols), None)
            account_currency = next((c for c in ["currency", "Currency"] if c in account_cols), None)
            platform_id_col = next((c for c in ["platformId", "platform_id"] if c in account_cols), None)
            if aid and aname:
                joins.append(f"left join {self._q(account_table)} a on a.{self._q(aid)} = o.{self._q(account_id_col)}")
                select_parts.append(f"a.{self._q(aname)} as account")
                select_parts.append(f"a.{self._q(account_currency)} as account_currency" if account_currency else "'' as account_currency")
                if platform_table and platform_id_col:
                    platform_cols = self._columns(conn, platform_table)
                    platform_name = next((c for c in ["name", "Name"] if c in platform_cols), None)
                    platform_id = next((c for c in ["id", "platformId"] if c in platform_cols), None)
                    if platform_id and platform_name:
                        joins.append(f"left join {self._q(platform_table)} pl on pl.{self._q(platform_id)} = a.{self._q(platform_id_col)}")
                        select_parts.append(f"pl.{self._q(platform_name)} as platform")
                    else:
                        select_parts.append("'' as platform")
                else:
                    select_parts.append("'' as platform")
            else:
                select_parts.append("'' as account")
                select_parts.append("'' as account_currency")
                select_parts.append("'' as platform")
        else:
            select_parts.append("'' as account")
            select_parts.append("'' as account_currency")
            select_parts.append("'' as platform")

        where = 'where coalesce(o."isDraft", false) = false' if "isDraft" in order_cols else ""
        sql = f"select {', '.join(select_parts)} from {self._q(order_table)} o {' '.join(joins)} {where}"
        return conn.execute(sql).fetchall()

    def _load_account_cash_rows(
        self,
        conn,
        account_table: str,
        platform_table: str | None,
        balance_table: str | None,
    ) -> list[dict[str, Any]]:
        account_cols = self._columns(conn, account_table)
        id_col = next((c for c in ["id", "accountId"] if c in account_cols), None)
        name_col = next((c for c in ["name", "Name"] if c in account_cols), None)
        currency_col = next((c for c in ["currency", "Currency"] if c in account_cols), None)
        balance_col = next((c for c in ["balance", "cashBalance", "cash_balance"] if c in account_cols), None)
        excluded_col = next((c for c in ["isExcluded", "is_excluded"] if c in account_cols), None)
        platform_id_col = next((c for c in ["platformId", "platform_id"] if c in account_cols), None)
        if not id_col:
            return []

        select_parts = [
            f"a.{self._q(id_col)} as source_id",
            f"a.{self._q(name_col)} as account" if name_col else "'' as account",
            f"a.{self._q(currency_col)} as currency" if currency_col else "'USD' as currency",
            f"a.{self._q(balance_col)} as account_balance" if balance_col else "null as account_balance",
            "null as latest_balance",
            "'' as platform",
        ]
        joins = []

        if balance_table:
            balance_cols = self._columns(conn, balance_table)
            balance_account_col = next((c for c in ["accountId", "account_id"] if c in balance_cols), None)
            balance_value_col = next((c for c in ["value", "balance", "cash"] if c in balance_cols), None)
            balance_date_col = next((c for c in ["date", "createdAt", "created_at"] if c in balance_cols), None)
            if balance_account_col and balance_value_col and balance_date_col:
                joins.append(
                    f"""
                    left join (
                        select distinct on ({self._q(balance_account_col)})
                            {self._q(balance_account_col)} as account_id,
                            {self._q(balance_value_col)} as latest_balance
                        from {self._q(balance_table)}
                        order by {self._q(balance_account_col)}, {self._q(balance_date_col)} desc
                    ) ab on ab.account_id = a.{self._q(id_col)}
                    """
                )
                select_parts[4] = "ab.latest_balance as latest_balance"

        if platform_table and platform_id_col:
            platform_cols = self._columns(conn, platform_table)
            platform_name = next((c for c in ["name", "Name"] if c in platform_cols), None)
            platform_id = next((c for c in ["id", "platformId"] if c in platform_cols), None)
            if platform_id and platform_name:
                joins.append(f"left join {self._q(platform_table)} pl on pl.{self._q(platform_id)} = a.{self._q(platform_id_col)}")
                select_parts[5] = f"pl.{self._q(platform_name)} as platform"

        where = f"where coalesce(a.{self._q(excluded_col)}, false) = false" if excluded_col else ""
        rows = conn.execute(
            f"select {', '.join(select_parts)} from {self._q(account_table)} a {' '.join(joins)} {where}"
        ).fetchall()

        accounts = []
        for row in rows:
            cash = row.get("account_balance")
            if cash is None:
                cash = row.get("latest_balance")
            accounts.append(
                {
                    "source_id": str(row.get("source_id") or ""),
                    "account": str(row.get("account") or ""),
                    "platform": str(row.get("platform") or ""),
                    "currency": str(row.get("currency") or "USD").upper(),
                    "cash": float(cash or 0),
                }
            )
        return accounts

    def _load_latest_market_prices(self, conn) -> dict[str, float]:
        rows = conn.execute(
            """
            select distinct on (symbol) symbol, "marketPrice"
            from "MarketData"
            where "marketPrice" is not null
            order by symbol, date desc
            """
        ).fetchall()
        return {str(row["symbol"]).upper(): float(row["marketPrice"]) for row in rows}

    def _aggregate(self, rows: list[dict], market_prices: dict[str, float] | None = None) -> list[Holding]:
        market_prices = market_prices or {}
        by_position: dict[tuple[str, str], Holding] = {}
        for row in rows:
            symbol = str(row.get("symbol") or row.get("order_symbol") or "").upper()
            if not symbol:
                continue
            account = row.get("account") or ""
            key = (symbol, account)
            asset_class = _asset_class(row.get("asset_class"), row.get("asset_sub_class"))
            holding = by_position.setdefault(
                key,
                Holding(
                    symbol=symbol,
                    name=row.get("name") or symbol,
                    asset_class=asset_class,
                    asset_sub_class=str(row.get("asset_sub_class") or ""),
                    data_source=str(row.get("data_source") or ""),
                    stock_market=str(row.get("stock_market") or ""),
                    currency=row.get("profile_currency") or row.get("currency") or "USD",
                    account=account,
                    platform=row.get("platform") or "",
                    country=_first_json_value(row.get("country"), "code"),
                    sector=_first_json_value(row.get("sector"), "name"),
                    industry=row.get("industry") or "",
                ),
            )
            qty = float(row.get("quantity") or 0)
            price = float(row.get("price") or 0)
            fee = float(row.get("fee") or 0)
            kind = str(row.get("activity_type") or "BUY").upper()
            gross = qty * price

            if kind == "BUY":
                holding.quantity += qty
                holding.cost_basis += gross + fee
            elif kind == "SELL":
                average_cost = holding.cost_basis / holding.quantity if holding.quantity else 0
                released_cost = average_cost * qty
                holding.quantity -= qty
                holding.cost_basis -= released_cost
                holding.realized_profit += gross - released_cost - fee
            elif kind in {"DIVIDEND", "INTEREST"}:
                holding.income_received += gross
                holding.realized_profit += gross - fee
            elif kind == "FEE":
                holding.realized_profit -= gross or fee
            elif kind in {"LIABILITY"}:
                holding.cost_basis -= gross

        holdings = [holding for holding in by_position.values() if abs(holding.quantity) > 1e-9]
        for holding in holdings:
            latest_price = market_prices.get(holding.symbol)
            holding.market_value = holding.quantity * latest_price if latest_price is not None else holding.cost_basis
            holding.unrealized_profit = holding.market_value - holding.cost_basis
        return sorted(holdings, key=lambda item: (-abs(item.market_value), item.symbol, item.account))


def _asset_class(asset_class: Any, asset_sub_class: Any) -> str:
    primary = str(asset_class or "UNKNOWN").upper()
    secondary = str(asset_sub_class or "").upper()
    if secondary in {"BOND", "ETF", "MUTUALFUND", "CRYPTOCURRENCY", "CASH"}:
        return secondary
    return primary


def _first_json_value(value: Any, key: str) -> str:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return str(first.get(key) or first.get("name") or first.get("code") or "")
        return str(first or "")
    if isinstance(value, dict):
        return str(value.get(key) or value.get("name") or value.get("code") or "")
    return str(value or "")


def sample_holdings() -> list[Holding]:
    return [
        Holding(symbol="AAPL", name="Apple Inc.", asset_class="EQUITY", currency="USD", quantity=10, market_value=1950, cost_basis=1600, unrealized_profit=350, sector="Technology"),
        Holding(symbol="MSFT", name="Microsoft Corp.", asset_class="EQUITY", currency="USD", quantity=5, market_value=2300, cost_basis=1900, unrealized_profit=400, sector="Technology"),
        Holding(symbol="BND", name="Vanguard Total Bond Market ETF", asset_class="BOND", currency="USD", quantity=20, market_value=1450, cost_basis=1500, unrealized_profit=-50, sector="Fixed Income"),
    ]
