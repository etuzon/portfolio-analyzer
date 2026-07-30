from __future__ import annotations

import sqlite3
from threading import RLock
from dataclasses import asdict
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import data_dir
from .metrics import moving_averages, price_range_metrics, support_resistance, volume_metrics
from .models import Holding, Ohlcv, SymbolAnalysis, Trend


ACCOUNT_TYPES = ["Investment", "Long-Term Savings", "Bank"]
FUND_KINDS = ["Pension", "Provident Fund", "Savings Fund"]
ASSET_CLASSES = ["EQUITY", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE"]
INSTRUMENT_TYPES = ["STOCK", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE"]
OPTION_TYPES = ["CALL", "PUT"]
EXPORT_TABLES = {
    "accounts": [
        "id",
        "type",
        "location",
        "currency",
        "initial_cash",
        "username",
        "account_id",
        "management_company",
        "persons",
        "comments",
        "created_at",
    ],
    "manual_securities": [
        "id",
        "symbol",
        "name",
        "stock_market",
        "asset_class",
        "instrument_type",
        "option_type",
        "underlying_symbol",
        "expiration_date",
        "strike_price",
        "contract_multiplier",
        "currency",
        "location",
        "comments",
        "created_at",
    ],
    "transactions": [
        "id",
        "account_db_id",
        "action",
        "symbol",
        "stock_market",
        "asset_class",
        "quantity",
        "price_input",
        "price",
        "currency",
        "location",
        "trade_date",
        "source",
        "comments",
        "created_at",
    ],
    "price_history": [
        "id",
        "symbol",
        "stock_market",
        "asset_class",
        "location",
        "currency",
        "price_input",
        "price",
        "price_date",
        "source",
        "comments",
        "created_at",
    ],
    "funds": ["id", "kind", "pension_id", "amount", "factor", "birth_date", "persons", "comments", "created_at"],
    "account_snapshots": [
        "account_db_id",
        "snapshot_date",
        "value",
        "cash",
        "profit",
        "profit_percent",
        "source",
        "created_at",
        "updated_at",
    ],
}


class LocalPortfolioStore:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "local-portfolio.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sync_lock = RLock()
        self._init_db()
        self.remove_source_branding()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys=on")
        conn.execute("pragma busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute("pragma journal_mode=wal")
                conn.execute(
                    """
                    create table if not exists accounts (
                        id text primary key,
                        type text not null,
                        location text not null,
                        currency text not null,
                        initial_cash real not null default 0,
                        username text not null default '',
                        account_id text not null default '',
                        management_company text not null default '',
                        persons text not null default '[]',
                        comments text not null default '',
                        created_at text not null
                    )
                    """
                )
                conn.execute(
                    """
                    create table if not exists manual_securities (
                        id text primary key,
                        symbol text not null,
                        name text not null default '',
                        stock_market text not null,
                        asset_class text not null,
                        instrument_type text not null,
                        option_type text not null default '',
                        underlying_symbol text not null default '',
                        expiration_date text not null default '',
                        strike_price real not null default 0,
                        contract_multiplier real not null default 1,
                        currency text not null,
                        location text not null,
                        comments text not null default '',
                        created_at text not null,
                        unique(symbol, stock_market)
                    )
                    """
                )
                conn.execute(
                    """
                    create table if not exists transactions (
                        id text primary key,
                        account_db_id text not null references accounts(id) on delete cascade,
                        action text not null,
                        symbol text not null,
                        stock_market text not null,
                        asset_class text not null,
                        quantity real not null,
                        price_input real not null,
                        price real not null,
                        currency text not null,
                        location text not null,
                        trade_date text not null,
                        source text not null default 'manual',
                        comments text not null default '',
                        created_at text not null
                    )
                    """
                )
                conn.execute(
                    """
                    create table if not exists price_history (
                        id text primary key,
                        symbol text not null,
                        stock_market text not null,
                        asset_class text not null,
                        location text not null,
                        currency text not null,
                        price_input real not null,
                        price real not null,
                        price_date text not null,
                        source text not null default 'manual',
                        comments text not null default '',
                        created_at text not null,
                        unique(symbol, stock_market, price_date)
                    )
                    """
                )
                conn.execute(
                    """
                    create table if not exists funds (
                        id text primary key,
                        kind text not null,
                        pension_id text not null,
                        amount real not null,
                        factor real not null default 200,
                        birth_date text not null default '',
                        persons text not null default '[]',
                        comments text not null default '',
                        created_at text not null
                    )
                    """
                )
                conn.execute(
                    """
                    create table if not exists account_snapshots (
                        account_db_id text not null references accounts(id) on delete cascade,
                        snapshot_date text not null,
                        value real not null,
                        cash real not null default 0,
                        profit real not null default 0,
                        profit_percent real not null default 0,
                        source text not null default 'manual',
                        created_at text not null,
                        updated_at text not null,
                        primary key (account_db_id, snapshot_date)
                    )
                    """
                )
                conn.execute("create index if not exists idx_account_snapshots_date on account_snapshots(snapshot_date)")
                self._ensure_column(conn, "accounts", "persons", "text not null default '[]'")
                self._ensure_column(conn, "funds", "birth_date", "text not null default ''")
                self._ensure_column(conn, "funds", "persons", "text not null default '[]'")
                self._normalize_existing_symbols(conn)
        except sqlite3.OperationalError as exc:
            if "readonly" not in str(exc).lower():
                raise

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"pragma table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"alter table {table} add column {column} {definition}")

    def _normalize_existing_symbols(self, conn: sqlite3.Connection) -> None:
        for table in ["manual_securities", "transactions", "price_history"]:
            conn.execute(
                f"""
                update {table}
                set symbol = substr(symbol, 4)
                where upper(symbol) like 'GF\\_%' escape '\\'
                  and not exists (
                    select 1
                    from {table} existing
                    where existing.symbol = substr({table}.symbol, 4)
                      and existing.stock_market = {table}.stock_market
                  )
                """
            )

    def remove_source_branding(self) -> None:
        try:
            with self._connect() as conn:
                rows = conn.execute("select id, username, account_id, management_company, comments from accounts").fetchall()
                for row in rows:
                    updates = {
                        "username": _clean_source_label(row["username"]),
                        "account_id": _clean_source_label(row["account_id"]),
                        "management_company": _clean_source_label(row["management_company"]),
                        "comments": _clean_source_label(row["comments"]).replace("Imported from", "Imported"),
                    }
                    if any(updates[key] != row[key] for key in updates):
                        conn.execute(
                            """
                            update accounts
                            set username = ?, account_id = ?, management_company = ?, comments = ?
                            where id = ?
                            """,
                            (updates["username"], updates["account_id"], updates["management_company"], updates["comments"], row["id"]),
                        )
        except sqlite3.OperationalError as exc:
            if "readonly" not in str(exc).lower():
                raise

    def status(self) -> dict[str, Any]:
        with self._connect() as conn:
            return {
                "path": str(self.path),
                "accounts": conn.execute("select count(*) from accounts").fetchone()[0],
                "transactions": conn.execute("select count(*) from transactions").fetchone()[0],
                "prices": conn.execute("select count(*) from price_history").fetchone()[0],
                "manual_securities": conn.execute("select count(*) from manual_securities").fetchone()[0],
                "funds": conn.execute("select count(*) from funds").fetchone()[0],
                "snapshots": conn.execute("select count(*) from account_snapshots").fetchone()[0],
            }

    def export_data(self) -> dict[str, Any]:
        with self._connect() as conn:
            data = {
                table: [_dict(row) for row in conn.execute(f"select {', '.join(columns)} from {table}").fetchall()]
                for table, columns in EXPORT_TABLES.items()
            }
        return {
            "version": 1,
            "exported_at": _now(),
            "kind": "portfolio-analyzer-local-data",
            "data": data,
            "counts": {table: len(rows) for table, rows in data.items()},
        }

    def change_token(self) -> str:
        data = self.export_data()["data"]
        encoded = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def import_data(self, payload: dict[str, Any], mode: str = "replace") -> dict[str, Any]:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if not isinstance(data, dict):
            raise ValueError("Backup data is required")
        if mode != "replace":
            raise ValueError("Only replace import mode is supported")
        prepared = {
            table: [self._clean_import_row(row, columns) for row in data.get(table, [])]
            for table, columns in EXPORT_TABLES.items()
        }
        with self._sync_lock:
            with self._connect() as conn:
                conn.execute("delete from account_snapshots")
                conn.execute("delete from funds")
                conn.execute("delete from price_history")
                conn.execute("delete from transactions")
                conn.execute("delete from manual_securities")
                conn.execute("delete from accounts")
                for table in ["accounts", "manual_securities", "transactions", "price_history", "funds", "account_snapshots"]:
                    columns = EXPORT_TABLES[table]
                    placeholders = ", ".join([":" + column for column in columns])
                    conn.executemany(
                        f"insert into {table} ({', '.join(columns)}) values ({placeholders})",
                        prepared[table],
                    )
        return {"imported": {table: len(rows) for table, rows in prepared.items()}}

    def _clean_import_row(self, row: Any, columns: list[str]) -> dict[str, Any]:
        if not isinstance(row, dict):
            raise ValueError("Backup rows must be objects")
        record = {column: row.get(column) for column in columns}
        for key in ["id", "account_db_id", "symbol", "stock_market", "asset_class", "instrument_type", "option_type", "underlying_symbol", "currency", "location", "trade_date", "price_date", "snapshot_date", "expiration_date"]:
            if key in record and record[key] is not None:
                record[key] = str(record[key])
        if "symbol" in record:
            record["symbol"] = _clean_security_symbol(record["symbol"])
        if "underlying_symbol" in record:
            record["underlying_symbol"] = _clean_security_symbol(record["underlying_symbol"])
        for key in ["type", "name", "username", "account_id", "management_company", "comments", "source", "kind", "pension_id", "created_at", "updated_at", "birth_date"]:
            if key in record:
                record[key] = str(record.get(key) or "")
        if "persons" in record:
            record["persons"] = json.dumps(_clean_persons(record.get("persons")))
        for key in ["initial_cash", "quantity", "price_input", "price", "amount", "factor", "value", "cash", "profit", "profit_percent", "strike_price", "contract_multiplier"]:
            if key in record:
                record[key] = _number(record.get(key), 0)
        return record

    def backup_dir(self) -> Path:
        path = data_dir() / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_backup(self, keep: int = 30) -> dict[str, Any]:
        backup_dir = self.backup_dir()
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        path = backup_dir / f"portfolio-data-{timestamp}.json"
        data = self.export_data()
        path.write_text(json.dumps(data, indent=2, default=str))
        backups = self.list_backups()
        keep_count = max(int(keep or 0), 1)
        for backup in backups[keep_count:]:
            try:
                Path(backup["path"]).unlink()
            except OSError:
                pass
        return {"path": str(path), "filename": path.name, "counts": data["counts"], "created_at": data["exported_at"]}

    def list_backups(self) -> list[dict[str, Any]]:
        backup_dir = self.backup_dir()
        backups = []
        for path in sorted(backup_dir.glob("portfolio-data-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            stat = path.stat()
            backups.append(
                {
                    "filename": path.name,
                    "path": str(path),
                    "size_kb": round(stat.st_size / 1024, 1),
                    "modified_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
                }
            )
        return backups

    def list_accounts(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select * from accounts order by management_company, username, account_id").fetchall()
        return [self._account_out(row) for row in rows]

    def save_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        account_id = str(payload.get("id") or uuid4())
        location = str(payload.get("location") or "USA").strip()
        record = {
            "id": account_id,
            "type": _choice(payload.get("type"), ACCOUNT_TYPES, "Investment"),
            "location": location,
            "currency": str(payload.get("currency") or _currency_for_location(location)).upper().strip(),
            "initial_cash": _number(payload.get("initial_cash"), 0),
            "username": str(payload.get("username") or "").strip(),
            "account_id": str(payload.get("account_id") or "").strip(),
            "management_company": str(payload.get("management_company") or "").strip(),
            "persons": json.dumps(_clean_persons(payload.get("persons"))),
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": str(payload.get("created_at") or _now()),
        }
        if not record["account_id"]:
            record["account_id"] = account_id[:8]
        with self._connect() as conn:
            conn.execute(
                """
                insert or replace into accounts
                  (id, type, location, currency, initial_cash, username, account_id, management_company, persons, comments, created_at)
                values
                  (:id, :type, :location, :currency, :initial_cash, :username, :account_id, :management_company, :persons, :comments, :created_at)
                """,
                record,
            )
        return self._account_out(record)

    def delete_account(self, account_db_id: str) -> bool:
        with self._connect() as conn:
            before = conn.execute("select count(*) from accounts where id = ?", (account_db_id,)).fetchone()[0]
            conn.execute("delete from accounts where id = ?", (account_db_id,))
        return bool(before)

    def list_manual_securities(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select *
                from manual_securities
                order by stock_market, symbol
                """
            ).fetchall()
        return [_dict(row) for row in rows]

    def save_manual_security(self, payload: dict[str, Any]) -> dict[str, Any]:
        instrument_type = _choice(payload.get("instrument_type"), INSTRUMENT_TYPES, "STOCK")
        asset_class = _asset_class_for_instrument(instrument_type, payload.get("asset_class"))
        location = str(payload.get("location") or "USA").strip()
        currency = str(payload.get("currency") or _currency_for_location(location)).upper().strip()
        option_type = str(payload.get("option_type") or "").upper().strip()
        expiration_date = ""
        if payload.get("expiration_date"):
            expiration_date = _date_string(payload.get("expiration_date"))
        if instrument_type == "OPTION":
            option_type = _choice(option_type, OPTION_TYPES, "CALL")
            if not str(payload.get("underlying_symbol") or "").strip():
                raise ValueError("Underlying symbol is required for options")
            if not expiration_date:
                raise ValueError("Expiration date is required for options")
            if _number(payload.get("strike_price"), 0) <= 0:
                raise ValueError("Strike price must be greater than zero for options")
        elif instrument_type == "FUTURE" and not expiration_date:
            raise ValueError("Expiration date is required for futures")
        else:
            option_type = ""
        multiplier_default = 100 if instrument_type == "OPTION" else 1
        record = {
            "id": str(payload.get("id") or uuid4()),
            "symbol": _clean_security_symbol(payload.get("symbol")),
            "name": str(payload.get("name") or "").strip(),
            "stock_market": str(payload.get("stock_market") or "").upper().strip(),
            "asset_class": asset_class,
            "instrument_type": instrument_type,
            "option_type": option_type,
            "underlying_symbol": str(payload.get("underlying_symbol") or "").upper().strip(),
            "expiration_date": expiration_date,
            "strike_price": _number(payload.get("strike_price"), 0),
            "contract_multiplier": _number(payload.get("contract_multiplier"), multiplier_default) or multiplier_default,
            "currency": currency,
            "location": location,
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": str(payload.get("created_at") or _now()),
        }
        if not record["symbol"]:
            raise ValueError("Symbol is required")
        if not record["stock_market"]:
            raise ValueError("Stock market is required")
        if not record["name"]:
            record["name"] = record["symbol"]
        with self._connect() as conn:
            conn.execute(
                """
                insert into manual_securities
                  (id, symbol, name, stock_market, asset_class, instrument_type, option_type, underlying_symbol, expiration_date, strike_price, contract_multiplier, currency, location, comments, created_at)
                values
                  (:id, :symbol, :name, :stock_market, :asset_class, :instrument_type, :option_type, :underlying_symbol, :expiration_date, :strike_price, :contract_multiplier, :currency, :location, :comments, :created_at)
                on conflict(symbol, stock_market) do update set
                  name = excluded.name,
                  asset_class = excluded.asset_class,
                  instrument_type = excluded.instrument_type,
                  option_type = excluded.option_type,
                  underlying_symbol = excluded.underlying_symbol,
                  expiration_date = excluded.expiration_date,
                  strike_price = excluded.strike_price,
                  contract_multiplier = excluded.contract_multiplier,
                  currency = excluded.currency,
                  location = excluded.location,
                  comments = excluded.comments
                """,
                record,
            )
        return self.manual_security(record["symbol"], record["stock_market"]) or record

    def delete_manual_security(self, security_id: str) -> bool:
        with self._connect() as conn:
            before = conn.execute("select count(*) from manual_securities where id = ?", (security_id,)).fetchone()[0]
            conn.execute("delete from manual_securities where id = ?", (security_id,))
        return bool(before)

    def manual_security(self, symbol: Any, stock_market: Any) -> dict[str, Any] | None:
        symbol_key = _clean_security_symbol(symbol)
        market_key = str(stock_market or "").upper().strip()
        if not symbol_key or not market_key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "select * from manual_securities where symbol = ? and stock_market = ?",
                (symbol_key, market_key),
            ).fetchone()
        return _dict(row) if row else None

    def manual_security_exists(self, symbol: Any, stock_market: Any) -> bool:
        return self.manual_security(symbol, stock_market) is not None

    def list_transactions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select t.*, a.username, a.account_id, a.management_company,
                       s.name as security_name,
                       s.instrument_type,
                       s.option_type,
                       s.underlying_symbol,
                       s.expiration_date,
                       s.strike_price,
                       s.contract_multiplier
                from transactions t
                join accounts a on a.id = t.account_db_id
                left join manual_securities s on s.symbol = t.symbol and s.stock_market = t.stock_market
                order by t.trade_date desc, t.created_at desc
                """
            ).fetchall()
        return [_dict(row) for row in rows]

    def add_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        account = self._account(payload.get("account_db_id"))
        action = _choice(payload.get("action"), ["ADD", "REMOVE", "BUY", "SELL", "SHORT"], "BUY")
        symbol = _clean_security_symbol(payload.get("symbol"))
        stock_market = str(payload.get("stock_market") or "").upper().strip()
        metadata = self.manual_security(symbol, stock_market)
        asset_class = str(payload.get("asset_class") or (metadata or {}).get("asset_class") or "EQUITY").upper().strip()
        quantity = abs(_number(payload.get("quantity"), 0))
        price_input = _number(payload.get("price_input"), 0)
        location = str(payload.get("location") or (metadata or {}).get("location") or account["location"] or "USA").strip()
        currency = str(payload.get("currency") or (metadata or {}).get("currency") or account["currency"] or _currency_for_location(location)).upper().strip()
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero")
        if price_input < 0:
            raise ValueError("Price cannot be negative")
        record = {
            "id": str(uuid4()),
            "account_db_id": account["id"],
            "action": action,
            "symbol": symbol,
            "stock_market": stock_market,
            "asset_class": asset_class,
            "quantity": quantity,
            "price_input": price_input,
            "price": normalize_price(price_input, location, asset_class),
            "currency": currency,
            "location": location,
            "trade_date": _date_string(payload.get("trade_date")),
            "source": str(payload.get("source") or "manual").strip(),
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": _now(),
        }
        if not record["symbol"]:
            raise ValueError("Symbol is required")
        if not record["stock_market"]:
            raise ValueError("Stock market is required")
        with self._connect() as conn:
            conn.execute(
                """
                insert into transactions
                  (id, account_db_id, action, symbol, stock_market, asset_class, quantity, price_input, price, currency, location, trade_date, source, comments, created_at)
                values
                  (:id, :account_db_id, :action, :symbol, :stock_market, :asset_class, :quantity, :price_input, :price, :currency, :location, :trade_date, :source, :comments, :created_at)
                """,
                record,
            )
        return record

    def delete_transaction(self, transaction_id: str) -> bool:
        with self._connect() as conn:
            before = conn.execute("select count(*) from transactions where id = ?", (transaction_id,)).fetchone()[0]
            conn.execute("delete from transactions where id = ?", (transaction_id,))
        return bool(before)

    def list_prices(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select * from price_history order by price_date desc, symbol").fetchall()
        return [_dict(row) for row in rows]

    def price_history(self, symbol: Any, stock_market: Any, from_date: date | None = None, to_date: date | None = None) -> list[dict[str, Any]]:
        symbol_key = _clean_security_symbol(symbol)
        market_key = str(stock_market or "").upper().strip()
        args: list[Any] = [symbol_key, market_key]
        where = "where symbol = ? and stock_market = ?"
        if from_date:
            where += " and price_date >= ?"
            args.append(from_date.isoformat())
        if to_date:
            where += " and price_date <= ?"
            args.append(to_date.isoformat())
        with self._connect() as conn:
            rows = conn.execute(f"select * from price_history {where} order by price_date", args).fetchall()
        return [_dict(row) for row in rows]

    def save_price(self, payload: dict[str, Any]) -> dict[str, Any]:
        symbol = _clean_security_symbol(payload.get("symbol"))
        stock_market = str(payload.get("stock_market") or "").upper().strip()
        metadata = self.manual_security(symbol, stock_market)
        location = str(payload.get("location") or (metadata or {}).get("location") or "USA").strip()
        asset_class = str(payload.get("asset_class") or (metadata or {}).get("asset_class") or "EQUITY").upper().strip()
        currency = str(payload.get("currency") or (metadata or {}).get("currency") or _currency_for_location(location)).upper().strip()
        record = {
            "id": str(payload.get("id") or uuid4()),
            "symbol": symbol,
            "stock_market": stock_market,
            "asset_class": asset_class,
            "location": location,
            "currency": currency,
            "price_input": _number(payload.get("price_input"), 0),
            "price": normalize_price(_number(payload.get("price_input"), 0), location, asset_class),
            "price_date": _date_string(payload.get("price_date")),
            "source": str(payload.get("source") or "manual").strip(),
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": str(payload.get("created_at") or _now()),
        }
        if not record["symbol"]:
            raise ValueError("Symbol is required")
        if not record["stock_market"]:
            raise ValueError("Stock market is required")
        with self._connect() as conn:
            conn.execute(
                """
                insert into price_history
                  (id, symbol, stock_market, asset_class, location, currency, price_input, price, price_date, source, comments, created_at)
                values
                  (:id, :symbol, :stock_market, :asset_class, :location, :currency, :price_input, :price, :price_date, :source, :comments, :created_at)
                on conflict(symbol, stock_market, price_date) do update set
                  asset_class = excluded.asset_class,
                  location = excluded.location,
                  currency = excluded.currency,
                  price_input = excluded.price_input,
                  price = excluded.price,
                  source = excluded.source,
                  comments = excluded.comments
                """,
                record,
            )
        return record

    def import_price_history(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        records = []
        for row in rows:
            symbol = _clean_security_symbol(row.get("symbol"))
            stock_market = str(row.get("stock_market") or "").upper().strip()
            if not symbol or not stock_market:
                continue
            location = str(row.get("location") or "USA").strip()
            asset_class = str(row.get("asset_class") or "EQUITY").upper().strip()
            currency = str(row.get("currency") or _currency_for_location(location)).upper().strip()
            price = _number(row.get("price"), 0)
            if price <= 0:
                continue
            records.append(
                {
                    "id": str(row.get("id") or uuid4()),
                    "symbol": symbol,
                    "stock_market": stock_market,
                    "asset_class": asset_class,
                    "location": location,
                    "currency": currency,
                    "price_input": _number(row.get("price_input"), denormalize_price(price, location, asset_class)),
                    "price": price,
                    "price_date": _date_string(row.get("price_date")),
                    "source": str(row.get("source") or "source_import").strip(),
                    "comments": str(row.get("comments") or "").strip(),
                    "created_at": str(row.get("created_at") or _now()),
                }
            )
        if not records:
            return {"prices": 0}
        with self._connect() as conn:
            conn.executemany(
                """
                insert into price_history
                  (id, symbol, stock_market, asset_class, location, currency, price_input, price, price_date, source, comments, created_at)
                values
                  (:id, :symbol, :stock_market, :asset_class, :location, :currency, :price_input, :price, :price_date, :source, :comments, :created_at)
                on conflict(symbol, stock_market, price_date) do update set
                  asset_class = excluded.asset_class,
                  location = excluded.location,
                  currency = excluded.currency,
                  price_input = excluded.price_input,
                  price = excluded.price,
                  source = excluded.source,
                  comments = excluded.comments
                """,
                records,
            )
        return {"prices": len(records)}

    def delete_history_before(self, cutoff: date | str) -> dict[str, int]:
        day = _parse_date(cutoff)
        if not day:
            raise ValueError("Valid cutoff date is required")
        with self._connect() as conn:
            price_count = conn.execute("select count(*) from price_history where price_date < ?", (day.isoformat(),)).fetchone()[0]
            snapshot_count = conn.execute("select count(*) from account_snapshots where snapshot_date < ?", (day.isoformat(),)).fetchone()[0]
            conn.execute("delete from price_history where price_date < ?", (day.isoformat(),))
            conn.execute("delete from account_snapshots where snapshot_date < ?", (day.isoformat(),))
        return {"prices": int(price_count), "account_snapshots": int(snapshot_count)}

    def delete_price(self, price_id: str) -> bool:
        with self._connect() as conn:
            before = conn.execute("select count(*) from price_history where id = ?", (price_id,)).fetchone()[0]
            conn.execute("delete from price_history where id = ?", (price_id,))
        return bool(before)

    def list_account_snapshots(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        args: list[Any] = []
        where = []
        account_id = str(filters.get("account_id") or "")
        from_date = _parse_date(filters.get("from") or filters.get("date_from"))
        to_date = _parse_date(filters.get("to") or filters.get("date_to"))
        if account_id:
            where.append("s.account_db_id = ?")
            args.append(account_id)
        if from_date:
            where.append("s.snapshot_date >= ?")
            args.append(from_date.isoformat())
        if to_date:
            where.append("s.snapshot_date <= ?")
            args.append(to_date.isoformat())
        where_sql = "where " + " and ".join(where) if where else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                select s.*, a.type, a.location, a.currency, a.username, a.account_id, a.management_company
                from account_snapshots s
                join accounts a on a.id = s.account_db_id
                {where_sql}
                order by s.snapshot_date desc, a.management_company, a.username, a.account_id
                """,
                args,
            ).fetchall()
        return [self._snapshot_out(row) for row in rows]

    def save_account_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        account = self._account(payload.get("account_db_id") or payload.get("account_id"))
        value = _number(payload.get("value"), 0)
        cash = _number(payload.get("cash"), 0)
        profit = _number(payload.get("profit"), value - cash)
        basis = abs(value - cash - profit)
        record = {
            "account_db_id": account["id"],
            "snapshot_date": _date_string(payload.get("snapshot_date") or payload.get("date")),
            "value": value,
            "cash": cash,
            "profit": profit,
            "profit_percent": _number(payload.get("profit_percent"), _ratio_percent(profit, basis) or 0),
            "source": str(payload.get("source") or "manual").strip(),
            "created_at": str(payload.get("created_at") or _now()),
            "updated_at": _now(),
        }
        with self._connect() as conn:
            conn.execute(
                """
                insert into account_snapshots
                  (account_db_id, snapshot_date, value, cash, profit, profit_percent, source, created_at, updated_at)
                values
                  (:account_db_id, :snapshot_date, :value, :cash, :profit, :profit_percent, :source, :created_at, :updated_at)
                on conflict(account_db_id, snapshot_date) do update set
                  value = excluded.value,
                  cash = excluded.cash,
                  profit = excluded.profit,
                  profit_percent = excluded.profit_percent,
                  source = excluded.source,
                  updated_at = excluded.updated_at
                """,
                record,
            )
        return self.list_account_snapshots({"account_id": account["id"], "from": record["snapshot_date"], "to": record["snapshot_date"]})[0]

    def delete_account_snapshot(self, account_db_id: str, snapshot_date: str) -> bool:
        with self._connect() as conn:
            before = conn.execute(
                "select count(*) from account_snapshots where account_db_id = ? and snapshot_date = ?",
                (account_db_id, snapshot_date),
            ).fetchone()[0]
            conn.execute(
                "delete from account_snapshots where account_db_id = ? and snapshot_date = ?",
                (account_db_id, snapshot_date),
            )
        return bool(before)

    def capture_daily_snapshots(self, snapshot_date: date | str | None = None) -> dict[str, Any]:
        day = _parse_date(snapshot_date) or date.today()
        saved = 0
        for account in self.list_accounts():
            points = self._computed_trend_for_account(account, day, day)
            if not points:
                continue
            point = points[-1]
            self.save_account_snapshot(
                {
                    "account_id": account["id"],
                    "snapshot_date": day.isoformat(),
                    "value": point["value"],
                    "cash": point["cash"],
                    "profit": point["profit"],
                    "profit_percent": point["profit_percent"],
                    "source": "daily",
                }
            )
            saved += 1
        return {"date": day.isoformat(), "snapshots": saved}

    def list_funds(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select * from funds order by kind, pension_id").fetchall()
        return [self._fund_out(row) for row in rows]

    def save_fund(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = {
            "id": str(payload.get("id") or uuid4()),
            "kind": _choice(payload.get("kind"), FUND_KINDS, "Pension"),
            "pension_id": str(payload.get("pension_id") or "").strip(),
            "amount": _number(payload.get("amount"), 0),
            "factor": _number(payload.get("factor"), 200) or 200,
            "birth_date": _clean_birth_date(payload.get("birth_date") or payload.get("birthday")),
            "persons": json.dumps(_clean_persons(payload.get("persons"))),
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": str(payload.get("created_at") or _now()),
        }
        if not record["pension_id"]:
            record["pension_id"] = record["id"][:8]
        with self._connect() as conn:
            conn.execute(
                """
                insert or replace into funds
                  (id, kind, pension_id, amount, factor, birth_date, persons, comments, created_at)
                values
                  (:id, :kind, :pension_id, :amount, :factor, :birth_date, :persons, :comments, :created_at)
                """,
                record,
            )
        return {**self._fund_out(record), "monthly_estimate": monthly_pension(record["amount"], record["factor"])}

    def simulate_pension(self, payload: dict[str, Any]) -> dict[str, Any]:
        scenarios = payload.get("scenarios")
        if not isinstance(scenarios, list):
            scenarios = [payload]
        results = []
        for index, scenario in enumerate(scenarios, start=1):
            if not isinstance(scenario, dict):
                continue
            kind = _choice(scenario.get("kind"), FUND_KINDS, "Pension")
            current_age = _number(scenario.get("current_age"), _number(scenario.get("age"), 0))
            birth_date = _clean_birth_date(scenario.get("birth_date") or scenario.get("birthday") or scenario.get("person_birth_date"))
            if current_age <= 0 and birth_date:
                current_age = age_from_birth_date(birth_date)
            retire_age = _number(scenario.get("retire_age"), _number(scenario.get("retirement_age"), 0))
            if current_age <= 0:
                raise ValueError("Current age is required")
            if retire_age <= current_age:
                raise ValueError("Retirement age must be greater than current age")
            factor = _number(scenario.get("factor"), 200) or 200
            annual_return = _number(scenario.get("annual_return"), _number(scenario.get("annual_return_percent"), 0)) / 100
            monthly_return = (1 + annual_return) ** (1 / 12) - 1 if annual_return > -1 else -1
            amount = _number(scenario.get("amount"), _number(scenario.get("current_amount"), 0))
            periods = _income_periods(scenario, current_age, retire_age)
            timeline = []
            total_deposits = 0.0
            months = int(round((retire_age - current_age) * 12))
            for month in range(months):
                age = current_age + month / 12
                period = _period_for_age(periods, age) or {}
                income = _number(period.get("monthly_income"), _number(scenario.get("monthly_income"), 0))
                contribution_percent = _number(period.get("contribution_percent"), _number(scenario.get("contribution_percent"), 0))
                monthly_deposit = _number(period.get("monthly_deposit"), _number(scenario.get("monthly_deposit"), 0))
                if monthly_deposit <= 0 and income > 0 and contribution_percent > 0:
                    monthly_deposit = income * contribution_percent / 100
                if monthly_return == -1:
                    amount = 0
                else:
                    amount = amount * (1 + monthly_return) + monthly_deposit
                total_deposits += monthly_deposit
                if month == 0 or (month + 1) % 12 == 0 or month == months - 1:
                    timeline.append(
                        {
                            "age": round(current_age + (month + 1) / 12, 2),
                            "amount": amount,
                            "monthly_deposit": monthly_deposit,
                        }
                    )
            monthly_payout = monthly_pension(amount, factor) if kind == "Pension" else None
            results.append(
                {
                    "name": str(scenario.get("name") or f"Scenario {index}").strip(),
                    "kind": kind,
                    "birth_date": birth_date,
                    "current_age": current_age,
                    "retire_age": retire_age,
                    "years": retire_age - current_age,
                    "annual_return": annual_return * 100,
                    "starting_amount": _number(scenario.get("amount"), _number(scenario.get("current_amount"), 0)),
                    "total_deposits": total_deposits,
                    "final_amount": amount,
                    "investment_gain": amount - total_deposits - _number(scenario.get("amount"), _number(scenario.get("current_amount"), 0)),
                    "factor": factor,
                    "monthly_pension": monthly_payout,
                    "timeline": timeline,
                }
            )
        return {"results": results}

    def delete_fund(self, fund_id: str) -> bool:
        with self._connect() as conn:
            before = conn.execute("select count(*) from funds where id = ?", (fund_id,)).fetchone()[0]
            conn.execute("delete from funds where id = ?", (fund_id,))
        return bool(before)

    def holdings(self, include_imported: bool = True) -> list[SymbolAnalysis]:
        accounts = {row["id"]: row for row in self.list_accounts()}
        transactions = self.list_transactions()
        if not include_imported:
            transactions = [tx for tx in transactions if tx["source"] != "ghostfolio_import"]
        positions: dict[tuple[str, str, str], dict[str, Any]] = {}
        for tx in sorted(transactions, key=lambda item: item["trade_date"]):
            key = (tx["account_db_id"], tx["symbol"], tx["stock_market"])
            position = positions.setdefault(
                key,
                {
                    "account": accounts.get(tx["account_db_id"]),
                    "symbol": tx["symbol"],
                    "stock_market": tx["stock_market"],
                    "asset_class": tx["asset_class"],
                    "security_name": tx.get("security_name") or tx["symbol"],
                    "instrument_type": tx.get("instrument_type") or "",
                    "option_type": tx.get("option_type") or "",
                    "underlying_symbol": tx.get("underlying_symbol") or "",
                    "expiration_date": tx.get("expiration_date") or "",
                    "strike_price": tx.get("strike_price") or 0,
                    "contract_multiplier": tx.get("contract_multiplier") or 1,
                    "is_manual_security": bool(tx.get("instrument_type")),
                    "currency": tx["currency"],
                    "location": tx["location"],
                    "quantity": 0.0,
                    "cost_basis": 0.0,
                    "realized_profit": 0.0,
                },
            )
            self._apply_tx(position, tx)
        analyses = []
        for position in positions.values():
            if abs(position["quantity"]) <= 1e-9:
                continue
            analyses.append(self._analysis(position))
        return analyses

    def account_trends(self, filters: dict[str, Any]) -> dict[str, Any]:
        from_date = _parse_date(filters.get("from")) or (date.today() - timedelta(days=365))
        to_date = _parse_date(filters.get("to")) or date.today()
        accounts = self._filtered_accounts(filters)
        points_by_account = []
        for account in accounts:
            points = self._trend_for_account(account, from_date, to_date)
            if points:
                points_by_account.append({"account": account, "points": points})
        all_dates = sorted({point["date"] for item in points_by_account for point in item["points"]})
        if all_dates:
            for item in points_by_account:
                item["points"] = _fill_trend_dates(item["points"], all_dates)
        return {"from": from_date.isoformat(), "to": to_date.isoformat(), "accounts": points_by_account}

    def enrich_ghostfolio_holdings(self, holdings: list[Holding]) -> list[Holding]:
        for holding in holdings:
            account = self._account_by_external(holding.account, holding.currency)
            if not account:
                continue
            holding.account_id = account["id"]
            holding.account_type = account["type"]
            holding.location = account["location"]
            if not holding.platform:
                holding.platform = account["management_company"]
        return holdings

    def reports(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        filters = filters or {}
        holdings = self.holdings()
        account_rows = self._filtered_accounts(filters)
        account_ids = {row["id"] for row in account_rows}
        filtered = [item for item in holdings if item.holding.account_id in account_ids or not account_ids]
        cash_by_account = {row["id"]: float(row["initial_cash"] or 0) for row in account_rows}
        for tx in self.list_transactions():
            if tx["account_db_id"] in cash_by_account:
                cash_by_account[tx["account_db_id"]] += _cash_delta(tx)
        by_type: dict[str, float] = {}
        by_location: dict[str, float] = {}
        by_account: dict[str, dict[str, Any]] = {}
        accounts_by_id = {row["id"]: row for row in account_rows}
        for account in account_rows:
            cash = cash_by_account.get(account["id"], 0)
            by_type[account["type"] or "Unknown"] = by_type.get(account["type"] or "Unknown", 0) + cash
            by_location[account["location"] or "Unknown"] = by_location.get(account["location"] or "Unknown", 0) + cash
            account_name = _account_label(account)
            by_account[account_name or account["id"]] = {"value": cash, "profit": 0, "cash": cash, "currency": account["currency"]}
        for item in filtered:
            holding = item.holding
            by_type[holding.account_type or "Unknown"] = by_type.get(holding.account_type or "Unknown", 0) + holding.market_value
            by_location[holding.location or "Unknown"] = by_location.get(holding.location or "Unknown", 0) + holding.market_value
            account = accounts_by_id.get(holding.account_id, {})
            bucket = by_account.setdefault(
                holding.account,
                {"value": cash_by_account.get(holding.account_id, 0), "profit": 0, "cash": cash_by_account.get(holding.account_id, 0), "currency": holding.currency or account.get("currency")},
            )
            bucket["value"] += holding.market_value
            bucket["profit"] += holding.unrealized_profit + holding.realized_profit
        funds = self.list_funds()
        cash = sum(cash_by_account.values())
        securities_value = sum(item.holding.market_value for item in filtered)
        return {
            "local_db": self.status(),
            "accounts": len(account_rows),
            "holdings": len(filtered),
            "cash": cash,
            "securities_value": securities_value,
            "value": cash + securities_value,
            "profit": sum(item.holding.unrealized_profit + item.holding.realized_profit for item in filtered),
            "by_type": by_type,
            "by_location": by_location,
            "by_account": by_account,
            "funds": {
                "count": len(funds),
                "amount": sum(item["amount"] for item in funds),
                "monthly_estimate": sum(item["monthly_estimate"] for item in funds),
                "items": funds,
            },
        }

    def import_ghostfolio(
        self,
        holdings: list[Holding],
        account_cash: list[dict[str, Any]] | None = None,
        source_transactions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        with self._sync_lock:
            account_cash = account_cash or []
            source_transactions = source_transactions or []
            cash_by_account = {
                _source_account_key(item.get("account"), item.get("currency")): item
                for item in account_cash
                if item.get("account")
            }
            accounts_by_key: dict[tuple[str, str], dict[str, Any]] = {}
            imported_accounts = 0
            updated_account_cash = 0
            imported_positions = 0
            updated_positions = 0
            attached_positions = 0
            imported_source_transactions = 0

            for item in cash_by_account.values():
                account, created, cash_updated = self._save_imported_account(
                    item.get("account"),
                    item.get("currency"),
                    item.get("cash"),
                    item.get("platform"),
                )
                accounts_by_key[_source_account_key(item.get("account"), item.get("currency"))] = account
                imported_accounts += int(created)
                updated_account_cash += int(cash_updated)

            if source_transactions:
                updated_positions = self._delete_all_imported_positions()
                for tx in source_transactions:
                    key = _source_account_key(tx.get("account"), tx.get("account_currency") or tx.get("currency"))
                    account = accounts_by_key.get(key) or self._account_by_external(_clean_source_label(tx.get("account")), key[1])
                    if not account:
                        account, created, cash_updated = self._save_imported_account(
                            tx.get("account"),
                            tx.get("account_currency") or tx.get("currency"),
                            cash_by_account.get(key, {}).get("cash", 0),
                            tx.get("platform"),
                        )
                        imported_accounts += int(created)
                        updated_account_cash += int(cash_updated)
                    accounts_by_key[key] = account
                    clean_symbol = _clean_security_symbol(tx.get("symbol"))
                    stock_market = str(tx.get("stock_market") or "MANUAL").upper().strip()
                    location = str(tx.get("location") or ("Israel" if str(tx.get("currency") or "").upper() == "ILS" else "USA"))
                    asset_class = str(tx.get("asset_class") or "EQUITY").upper().strip()
                    price = abs(_number(tx.get("price"), 0))
                    if stock_market == "MANUAL":
                        self.save_manual_security(
                            {
                                "symbol": clean_symbol,
                                "name": tx.get("name") or clean_symbol,
                                "stock_market": stock_market,
                                "asset_class": asset_class,
                                "instrument_type": tx.get("asset_sub_class") or asset_class,
                                "currency": tx.get("currency") or account["currency"],
                                "location": location,
                                "comments": "Imported source profile",
                            }
                        )
                    self.add_transaction(
                        {
                            "account_db_id": account["id"],
                            "action": tx.get("action") or "ADD",
                            "symbol": clean_symbol,
                            "stock_market": stock_market,
                            "asset_class": asset_class,
                            "quantity": tx.get("quantity"),
                            "price_input": denormalize_price(price, location, asset_class),
                            "currency": tx.get("currency") or account["currency"],
                            "location": location,
                            "trade_date": tx.get("trade_date"),
                            "source": "ghostfolio_import",
                            "comments": tx.get("comments") or "Imported source order",
                        }
                    )
                    imported_source_transactions += 1

            for holding in holdings:
                key = _source_account_key(holding.account, holding.currency)
                account = accounts_by_key.get(key) or self._account_by_external(holding.account, holding.currency)
                if not account:
                    account, created, cash_updated = self._save_imported_account(
                        holding.account,
                        holding.currency,
                        cash_by_account.get(key, {}).get("cash", 0),
                        holding.platform,
                    )
                    imported_accounts += int(created)
                    updated_account_cash += int(cash_updated)
                accounts_by_key[key] = account
                clean_symbol = _clean_security_symbol(holding.symbol)
                if not source_transactions and self._has_imported_position(account["id"], clean_symbol):
                    self._delete_imported_position(account["id"], clean_symbol)
                    updated_positions += 1
                price = abs(holding.cost_basis / holding.quantity) if holding.quantity else 0
                location = "Israel" if holding.currency == "ILS" else "USA"
                if not source_transactions:
                    self.add_transaction(
                        {
                            "account_db_id": account["id"],
                            "action": "ADD",
                            "symbol": clean_symbol,
                            "stock_market": holding.stock_market or holding.data_source or "MANUAL",
                            "asset_class": holding.asset_class,
                            "quantity": abs(holding.quantity),
                            "price_input": denormalize_price(price, location, holding.asset_class),
                            "currency": holding.currency,
                            "location": location,
                            "trade_date": date.today().isoformat(),
                            "source": "ghostfolio_import",
                            "comments": f"Imported quantity {holding.quantity}",
                        }
                    )
                if holding.market_value and holding.quantity:
                    self.save_price(
                        {
                            "symbol": clean_symbol,
                            "stock_market": holding.stock_market or holding.data_source or "MANUAL",
                            "asset_class": holding.asset_class,
                            "location": location,
                            "currency": holding.currency,
                            "price_input": denormalize_price(abs(holding.market_value / holding.quantity), location, holding.asset_class),
                            "price_date": date.today().isoformat(),
                            "source": "ghostfolio_import",
                        }
                    )
                imported_positions += 1
                attached_positions += 1
            return {
                "accounts": imported_accounts,
                "account_cash_updated": updated_account_cash,
                "positions": imported_positions,
                "updated_positions": updated_positions,
                "attached_positions": attached_positions,
                "source_transactions": imported_source_transactions,
            }

    def _save_imported_account(
        self,
        source_account: Any,
        currency: Any,
        cash: Any,
        platform: Any = "",
    ) -> tuple[dict[str, Any], bool, bool]:
        clean_account = _clean_source_label(source_account) or "Imported"
        account_currency = str(currency or "USD").upper().strip()
        account = self._account_by_external(clean_account, account_currency)
        imported_cash = _number(cash, 0)
        if account:
            if abs(float(account.get("initial_cash") or 0) - imported_cash) > 1e-9:
                with self._connect() as conn:
                    conn.execute("update accounts set initial_cash = ? where id = ?", (imported_cash, account["id"]))
                account = self._account(account["id"])
                return account, False, True
            return account, False, False

        account = self.save_account(
            {
                "type": "Investment",
                "location": "Israel" if account_currency == "ILS" else "USA",
                "currency": account_currency,
                "initial_cash": imported_cash,
                "username": clean_account,
                "account_id": f"import-{clean_account}",
                "management_company": _clean_source_label(platform) or "Imported",
                "comments": "Imported",
            }
        )
        return account, True, bool(imported_cash)

    def _account(self, account_db_id: Any) -> dict[str, Any]:
        if not account_db_id:
            raise ValueError("Account is required")
        with self._connect() as conn:
            row = conn.execute("select * from accounts where id = ?", (str(account_db_id),)).fetchone()
        if not row:
            raise ValueError("Account not found")
        return _dict(row)

    def _account_by_external(self, username: str, currency: str) -> dict[str, Any] | None:
        clean_id = _clean_source_label(username) or "account"
        external_id = f"import-{clean_id}"
        with self._connect() as conn:
            row = conn.execute(
                "select * from accounts where account_id in (?, ?) and currency = ?",
                (external_id, clean_id, currency or "USD"),
            ).fetchone()
        return _dict(row) if row else None

    def _has_imported_position(self, account_db_id: str, symbol: str) -> bool:
        with self._connect() as conn:
            count = conn.execute(
                "select count(*) from transactions where account_db_id = ? and symbol = ? and source = 'ghostfolio_import'",
                (account_db_id, symbol),
            ).fetchone()[0]
        return bool(count)

    def _delete_imported_position(self, account_db_id: str, symbol: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "delete from transactions where account_db_id = ? and symbol = ? and source = 'ghostfolio_import'",
                (account_db_id, symbol),
            )

    def _delete_all_imported_positions(self) -> int:
        with self._connect() as conn:
            count = conn.execute("select count(*) from transactions where source = 'ghostfolio_import'").fetchone()[0]
            conn.execute("delete from transactions where source = 'ghostfolio_import'")
        return int(count)

    def _filtered_accounts(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        accounts = self.list_accounts()
        account_id = str(filters.get("account_id") or "")
        account_type = str(filters.get("account_type") or "")
        location = str(filters.get("location") or "")
        if account_id:
            accounts = [item for item in accounts if item["id"] == account_id]
        if account_type:
            accounts = [item for item in accounts if item["type"] == account_type]
        if location:
            location_key = _location_key(location)
            accounts = [item for item in accounts if _location_key(item["location"]) == location_key]
        return accounts

    def _apply_tx(self, position: dict[str, Any], tx: dict[str, Any]) -> None:
        qty = tx["quantity"]
        price = tx["price"]
        action = tx["action"]
        if action == "ADD":
            position["quantity"] += qty
            position["cost_basis"] += qty * price
        elif action == "BUY":
            current_qty = position["quantity"]
            if current_qty < 0:
                covered = min(qty, abs(current_qty))
                average = abs(position["cost_basis"] / current_qty) if current_qty else 0
                position["quantity"] += covered
                position["cost_basis"] += average * covered
                position["realized_profit"] += (average - price) * covered
                qty -= covered
            if qty > 0:
                position["quantity"] += qty
                position["cost_basis"] += qty * price
        elif action == "SHORT":
            position["quantity"] -= qty
            position["cost_basis"] -= qty * price
        elif action == "SELL":
            current_qty = position["quantity"]
            if current_qty > 0:
                released = min(qty, current_qty)
                average = position["cost_basis"] / current_qty if current_qty else 0
                position["quantity"] -= released
                position["cost_basis"] -= average * released
                position["realized_profit"] += (price - average) * released
                qty -= released
            if qty > 0:
                position["quantity"] -= qty
                position["cost_basis"] -= qty * price
        elif action == "REMOVE":
            current_qty = position["quantity"]
            if current_qty > 0:
                released = min(qty, current_qty)
                average = position["cost_basis"] / current_qty if current_qty else 0
                position["quantity"] -= released
                position["cost_basis"] -= average * released
            elif current_qty < 0:
                covered = min(qty, abs(current_qty))
                average = abs(position["cost_basis"] / current_qty) if current_qty else 0
                position["quantity"] += covered
                position["cost_basis"] += average * covered

    def _analysis(self, position: dict[str, Any]) -> SymbolAnalysis:
        account = position["account"] or {}
        prices = self._prices(position["symbol"], position["stock_market"], position["asset_class"], position["location"], position["currency"])
        latest = prices[-1].adjusted_close if prices else abs(position["cost_basis"] / position["quantity"]) if position["quantity"] else 0
        quantity = position["quantity"]
        market_value = quantity * latest
        if quantity >= 0:
            unrealized = market_value - position["cost_basis"]
        else:
            average = abs(position["cost_basis"] / quantity) if quantity else 0
            unrealized = abs(quantity) * (average - latest)
        account_name = _account_label(account)
        holding = Holding(
            symbol=position["symbol"],
            name=position.get("security_name") or position["symbol"],
            asset_class=position["asset_class"],
            asset_sub_class=position.get("instrument_type") or "",
            data_source="MANUAL" if position.get("is_manual_security") else "LOCAL",
            stock_market=position["stock_market"],
            currency=position["currency"],
            quantity=quantity,
            cost_basis=position["cost_basis"],
            market_value=market_value,
            realized_profit=position["realized_profit"],
            unrealized_profit=unrealized,
            account=account_name or position["stock_market"],
            account_id=account.get("id", ""),
            account_type=account.get("type", ""),
            platform=position["stock_market"],
            location=account.get("location") or position["location"],
            country=position["location"],
            sector="",
            industry="",
        )
        analysis = SymbolAnalysis(
            holding=holding,
            provider_status={"local_portfolio": "ok", **({"manual_security": "manual prices only"} if position.get("is_manual_security") else {})},
            price_ranges=price_range_metrics(prices),
            moving_averages=moving_averages(prices),
            support_resistance=support_resistance(prices),
            volume=volume_metrics(prices),
            income_trend=Trend(message="No local income statements"),
            profit_trend=Trend(message="No local company profit statements"),
            dividend_trend=Trend(message="No local dividend history"),
            profit_market_cap_trend=Trend(message="No local market cap data"),
            industry="",
            missing=[] if prices else ["price history"],
        )
        analysis.missing.extend(["income", "profit", "dividend", "profit/market cap", "industry"])
        return analysis

    def _prices(self, symbol: str, stock_market: str, asset_class: str, location: str, currency: str, up_to: date | None = None) -> list[Ohlcv]:
        args: list[Any] = [symbol, stock_market]
        where = "where symbol = ? and stock_market = ?"
        if up_to:
            where += " and price_date <= ?"
            args.append(up_to.isoformat())
        with self._connect() as conn:
            rows = conn.execute(
                f"select * from price_history {where} order by price_date",
                args,
            ).fetchall()
        return [
            Ohlcv(
                date=date.fromisoformat(row["price_date"]),
                open=float(row["price"]),
                high=float(row["price"]),
                low=float(row["price"]),
                close=float(row["price"]),
                adjusted_close=float(row["price"]),
                volume=0,
            )
            for row in rows
        ]

    def _trend_for_account(self, account: dict[str, Any], from_date: date, to_date: date) -> list[dict[str, Any]]:
        computed = self._computed_trend_for_account(account, from_date, to_date)
        snapshots = self._snapshot_points(account["id"], from_date, to_date)
        by_date = {point["date"]: point for point in computed}
        for point in snapshots:
            by_date[point["date"]] = point
        return [by_date[day] for day in sorted(by_date)]

    def _computed_trend_for_account(self, account: dict[str, Any], from_date: date, to_date: date) -> list[dict[str, Any]]:
        with self._connect() as conn:
            transactions = [_dict(row) for row in conn.execute(
                "select * from transactions where account_db_id = ? and trade_date <= ? order by trade_date",
                (account["id"], to_date.isoformat()),
            ).fetchall()]
            price_dates = [
                date.fromisoformat(row[0])
                for row in conn.execute(
                    """
                    select distinct p.price_date
                    from price_history p
                    join transactions t on t.symbol = p.symbol and t.stock_market = p.stock_market
                    where t.account_db_id = ? and p.price_date between ? and ?
                    order by p.price_date
                    """,
                    (account["id"], from_date.isoformat(), to_date.isoformat()),
                ).fetchall()
            ]
        dates = sorted({from_date, to_date, *price_dates, *[date.fromisoformat(tx["trade_date"]) for tx in transactions if from_date <= date.fromisoformat(tx["trade_date"]) <= to_date]})
        points = []
        for day in dates:
            positions: dict[tuple[str, str], dict[str, Any]] = {}
            cash = float(account["initial_cash"] or 0)
            for tx in transactions:
                if date.fromisoformat(tx["trade_date"]) > day:
                    continue
                cash += _cash_delta(tx)
                key = (tx["symbol"], tx["stock_market"])
                position = positions.setdefault(
                    key,
                    {
                        "symbol": tx["symbol"],
                        "stock_market": tx["stock_market"],
                        "asset_class": tx["asset_class"],
                        "location": tx["location"],
                        "currency": tx["currency"],
                        "quantity": 0.0,
                        "cost_basis": 0.0,
                        "realized_profit": 0.0,
                    },
                )
                self._apply_tx(position, tx)
            value = cash
            basis = 0.0
            realized = 0.0
            unrealized = 0.0
            for position in positions.values():
                if abs(position["quantity"]) <= 1e-9:
                    continue
                prices = self._prices(position["symbol"], position["stock_market"], position["asset_class"], position["location"], position["currency"], day)
                latest = prices[-1].adjusted_close if prices else abs(position["cost_basis"] / position["quantity"]) if position["quantity"] else 0
                value += position["quantity"] * latest
                basis += position["cost_basis"]
                realized += position["realized_profit"]
                if position["quantity"] >= 0:
                    unrealized += position["quantity"] * latest - position["cost_basis"]
                else:
                    average = abs(position["cost_basis"] / position["quantity"]) if position["quantity"] else 0
                    unrealized += abs(position["quantity"]) * (average - latest)
            profit = realized + unrealized
            points.append(
                {
                    "date": day.isoformat(),
                    "value": value,
                    "cash": cash,
                    "profit": profit,
                    "profit_percent": _ratio_percent(profit, abs(basis)) or 0,
                }
            )
        return points

    def _snapshot_points(self, account_db_id: str, from_date: date, to_date: date) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select snapshot_date, value, cash, profit, profit_percent
                from account_snapshots
                where account_db_id = ? and snapshot_date between ? and ?
                order by snapshot_date
                """,
                (account_db_id, from_date.isoformat(), to_date.isoformat()),
            ).fetchall()
        return [
            {
                "date": row["snapshot_date"],
                "value": float(row["value"]),
                "cash": float(row["cash"]),
                "profit": float(row["profit"]),
                "profit_percent": float(row["profit_percent"]),
                "saved": True,
            }
            for row in rows
        ]

    def _fund_out(self, row) -> dict[str, Any]:
        item = _dict(row)
        item["persons"] = _clean_persons(item.get("persons"))
        if not item["persons"] and item.get("birth_date"):
            item["persons"] = [{"name": "Person 1", "birth_date": item["birth_date"], "age": age_from_birth_date(item["birth_date"])}]
        item["monthly_estimate"] = monthly_pension(item["amount"], item["factor"])
        return item

    def _account_out(self, row) -> dict[str, Any]:
        item = _dict(row)
        item["persons"] = _clean_persons(item.get("persons"))
        return item

    def _snapshot_out(self, row) -> dict[str, Any]:
        item = _dict(row)
        account = {
            "id": item["account_db_id"],
            "type": item.pop("type", ""),
            "location": item.pop("location", ""),
            "currency": item.pop("currency", ""),
            "username": item.pop("username", ""),
            "account_id": item.pop("account_id", ""),
            "management_company": item.pop("management_company", ""),
        }
        item["account"] = account
        item["account_label"] = _account_label(account) or item["account_db_id"]
        return item


def normalize_price(price_input: float, location: str, asset_class: str) -> float:
    location_key = _location_key(location)
    if location_key == "israel":
        return price_input / 100
    if location_key == "usa" and asset_class.upper() == "BOND":
        return price_input / 100
    return price_input


def denormalize_price(price: float, location: str, asset_class: str) -> float:
    location_key = _location_key(location)
    if location_key == "israel":
        return price * 100
    if location_key == "usa" and asset_class.upper() == "BOND":
        return price * 100
    return price


def monthly_pension(amount: float, factor: float = 200) -> float:
    return amount / (factor or 200)


def age_from_birth_date(value: str, on_date: date | None = None) -> float:
    birth_date = date.fromisoformat(value)
    today = on_date or date.today()
    if birth_date > today:
        raise ValueError("Birth date cannot be in the future")
    return round((today - birth_date).days / 365.2425, 2)


def _clean_birth_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("Birth date must use YYYY-MM-DD") from exc
    if parsed > date.today():
        raise ValueError("Birth date cannot be in the future")
    return text


def _clean_persons(value: Any) -> list[dict[str, Any]]:
    raw = value
    if isinstance(value, str):
        try:
            raw = json.loads(value) if value.strip() else []
        except json.JSONDecodeError:
            raw = []
    if not isinstance(raw, list):
        raw = []
    persons = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        birth_date = _clean_birth_date(item.get("birth_date") or item.get("birthday"))
        if not birth_date:
            continue
        name = str(item.get("name") or f"Person {index}").strip() or f"Person {index}"
        persons.append({"name": name, "birth_date": birth_date, "age": age_from_birth_date(birth_date)})
    return persons


def _income_periods(scenario: dict[str, Any], current_age: float, retire_age: float) -> list[dict[str, Any]]:
    raw = scenario.get("income_periods")
    if not isinstance(raw, list) or not raw:
        raw = [
            {
                "from_age": current_age,
                "to_age": retire_age,
                "monthly_income": scenario.get("monthly_income"),
                "contribution_percent": scenario.get("contribution_percent"),
                "monthly_deposit": scenario.get("monthly_deposit"),
            }
        ]
    periods = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        from_age = _number(item.get("from_age"), current_age)
        to_age = _number(item.get("to_age"), retire_age)
        if to_age <= from_age:
            continue
        periods.append(
            {
                "from_age": max(from_age, current_age),
                "to_age": min(to_age, retire_age),
                "monthly_income": item.get("monthly_income"),
                "contribution_percent": item.get("contribution_percent"),
                "monthly_deposit": item.get("monthly_deposit"),
            }
        )
    return sorted(periods, key=lambda item: item["from_age"])


def _period_for_age(periods: list[dict[str, Any]], age: float) -> dict[str, Any] | None:
    return next((period for period in periods if period["from_age"] <= age < period["to_age"]), None)


def _dict(row) -> dict[str, Any]:
    return dict(row)


def _account_label(account: dict[str, Any]) -> str:
    parts = [_clean_source_label(account.get("management_company")), _clean_source_label(account.get("username")), _clean_source_label(account.get("account_id"))]
    unique = []
    for part in [item for item in parts if item]:
        if part not in unique:
            unique.append(part)
    return " ".join(unique).strip()


def _clean_source_label(value: Any) -> str:
    text = str(value or "").strip()
    for prefix in ("Ghostfolio-", "ghostfolio-"):
        if text.startswith(prefix):
            text = "import-" + text[len(prefix):]
    return " ".join(text.replace("Ghostfolio", "").replace("ghostfolio", "").replace("import-", "").split()).strip(" -")


def _clean_security_symbol(value: Any) -> str:
    text = str(value or "").upper().strip()
    if text.startswith("GF_"):
        text = text[3:]
    return text


def _asset_class_for_instrument(instrument_type: str, requested: Any = "") -> str:
    mapping = {
        "STOCK": "EQUITY",
        "ETF": "ETF",
        "MUTUALFUND": "MUTUALFUND",
        "BOND": "BOND",
        "OPTION": "OPTION",
        "FUTURE": "FUTURE",
    }
    requested_text = str(requested or "").upper().strip()
    if requested_text in ASSET_CLASSES and instrument_type not in mapping:
        return requested_text
    return mapping.get(instrument_type, requested_text if requested_text in ASSET_CLASSES else "EQUITY")


def _source_account_key(account: Any, currency: Any) -> tuple[str, str]:
    return (_clean_source_label(account).casefold(), str(currency or "USD").upper().strip())


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _number(value: Any, default: float = 0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _date_string(value: Any) -> str:
    parsed = _parse_date(value)
    return (parsed or date.today()).isoformat()


def _fill_trend_dates(points: list[dict[str, Any]], dates: list[str]) -> list[dict[str, Any]]:
    by_date = {point["date"]: point for point in points}
    last: dict[str, Any] | None = None
    filled = []
    for day in dates:
        point = by_date.get(day)
        if point:
            last = point
            filled.append(point)
            continue
        if not last:
            continue
        filled.append({**last, "date": day, "carried": True})
    return filled


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _choice(value: Any, choices: list[str], default: str) -> str:
    text = str(value or default).strip()
    normalized = {item.lower(): item for item in choices}
    return normalized.get(text.lower(), default)


def _location_key(location: str) -> str:
    text = str(location or "").strip().lower()
    if text in {"usa", "us", "u.s.", "u.s.a.", "united states", "united states of america"}:
        return "usa"
    if text in {"israel", "il", "state of israel"}:
        return "israel"
    return text


def _currency_for_location(location: str) -> str:
    return "ILS" if _location_key(location) == "israel" else "USD"


def _cash_delta(tx: dict[str, Any]) -> float:
    value = float(tx["quantity"] or 0) * float(tx["price"] or 0)
    if tx["action"] == "BUY":
        return -value
    if tx["action"] in {"SELL", "SHORT"}:
        return value
    return 0.0


def _ratio_percent(value: float | None, basis: float | None) -> float | None:
    if value is None or basis in (None, 0):
        return None
    return (value / abs(basis)) * 100


def to_dict(item: SymbolAnalysis) -> dict[str, Any]:
    return asdict(item)
