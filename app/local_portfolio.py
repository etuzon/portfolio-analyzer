from __future__ import annotations

import sqlite3
from contextlib import nullcontext
from threading import RLock
from dataclasses import asdict
from datetime import date, datetime, timedelta
import hashlib
import json
import math
import calendar
from pathlib import Path
import tempfile
from typing import Any
from uuid import uuid4

import yaml

from .config import data_dir
from .metrics import moving_averages, price_range_metrics, support_resistance, technical_signals, volume_metrics
from .models import Holding, Ohlcv, SymbolAnalysis, Trend


ACCOUNT_TYPES = ["Investment", "Long-Term Savings", "Bank", "ESOP"]
SINGLE_OWNER_ACCOUNT_TYPES = {"Long-Term Savings", "ESOP"}
EXTERNAL_IMPORT_SOURCE = "external_import"
FUND_KINDS = ["Pension", "Provident Fund", "Savings Fund"]
ASSET_CLASSES = [
    "EQUITY",
    "ETF",
    "MUTUALFUND",
    "BOND",
    "OPTION",
    "FUTURE",
    "RSU",
    "EMPLOYEE_STOCK_OPTION",
    "PRIVATE_STOCK",
    "STOCK_OPTION",
]
INSTRUMENT_TYPES = [
    "STOCK",
    "ETF",
    "MUTUALFUND",
    "BOND",
    "OPTION",
    "FUTURE",
    "EMPLOYEE_STOCK_OPTION",
    "PRIVATE_STOCK",
    "STOCK_OPTION",
]
OPTION_TYPES = ["CALL", "PUT"]
ISSUER_LISTING_STATUSES = ["PRIVATE", "PUBLIC"]
SUPPORTED_MANAGEMENT_CURRENCIES = {"ILS", "USD", "EUR"}
EXPOSURE_ASSET_FOCUSES = {
    "money_market", "government_bond", "investment_grade_bond", "high_yield_bond",
    "broad_equity", "single_country_equity", "sector_equity", "multi_asset",
    "real_estate", "commodity", "derivative", "other",
}
COMPANY_OUTLOOK_ACCURACY_TARGET_PERCENT = 75.0
COMPANY_OUTLOOK_MIN_EVALUATED_PREDICTIONS = 30
TRANSACTION_ACTIONS = ["ADD", "REMOVE", "BUY", "SELL", "SHORT", "DIVIDEND", "INTEREST", "FEE"]
PENSION_INSURANCE_RATES_PATH = Path(__file__).resolve().parent.parent / "reference-data" / "pension-insurance-rates.yaml"
PENSION_INSURANCE_RATES: dict[int, dict[str, Any]] | None = None
EXPORT_TABLES = {
    "app_preferences": ["key", "value", "updated_at"],
    "brokers": ["id", "name", "country", "currency", "comments", "created_at"],
    "family_members": ["id", "name", "first_name", "last_name", "gender", "birth_date", "retire_age", "comments", "created_at"],
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
    "issuers": [
        "id",
        "company_name",
        "listing_status",
        "public_symbol",
        "public_market",
        "currency",
        "location",
        "listing_date",
        "restriction_end_date",
        "manual_share_value",
        "valuation_date",
        "comments",
        "created_at",
        "updated_at",
    ],
    "manual_securities": [
        "id",
        "symbol",
        "secondary_symbol",
        "name",
        "stock_market",
        "asset_class",
        "instrument_type",
        "option_type",
        "underlying_symbol",
        "expiration_date",
        "strike_price",
        "contract_multiplier",
        "issuer_id",
        "grant_id",
        "grant_date",
        "vesting_start_date",
        "tax_scheme",
        "early_exercise_allowed",
        "currency",
        "location",
        "comments",
        "created_at",
    ],
    "security_industry_overrides": ["symbol", "stock_market", "industry", "created_at", "updated_at"],
    "security_exposure_profiles": ["symbol", "stock_market", "profile_json", "created_at", "updated_at"],
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
        "vest_date",
        "purchase_price",
        "strike_price",
        "security_id",
        "transition_id",
        "vesting_schedule",
        "currency",
        "location",
        "trade_date",
        "source",
        "comments",
        "created_at",
    ],
    "equity_transitions": [
        "id",
        "transition_type",
        "source_security_id",
        "target_security_id",
        "account_db_id",
        "quantity",
        "conversion_ratio",
        "effective_date",
        "details",
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
    "funds": ["id", "kind", "fund_name", "pension_id", "amount", "factor", "account_id", "birth_date", "persons", "comments", "created_at"],
    "fund_amount_history": ["id", "fund_id", "amount_date", "amount", "source", "comments", "created_at", "updated_at"],
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
    "events": [
        "id",
        "type",
        "event_date",
        "symbol",
        "stock_market",
        "account_db_id",
        "gross_amount",
        "tax_amount",
        "net_amount",
        "currency",
        "source",
        "source_key",
        "status",
        "transaction_id",
        "details",
        "created_at",
        "updated_at",
    ],
    "company_report_predictions": [
        "id",
        "symbol",
        "company_name",
        "industry",
        "created_at",
        "horizon_date",
        "model_version",
        "score",
        "label",
        "direction",
        "confidence",
        "baseline",
        "thesis",
        "mermaid",
        "actual",
        "actual_direction",
        "accuracy_score",
        "evaluation",
        "evaluated_at",
    ],
}


class LocalPortfolioStore:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "local-portfolio.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sync_lock = RLock()
        self._init_db()
        self.normalize_source_data()

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
                    create table if not exists app_preferences (
                        key text primary key,
                        value text not null,
                        updated_at text not null
                    )
                    """
                )
                conn.execute(
                    """
                    create table if not exists brokers (
                        id text primary key,
                        name text not null unique,
                        country text not null,
                        currency text not null,
                        comments text not null default '',
                        created_at text not null
                    )
                    """
                )
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
                    create table if not exists family_members (
                        id text primary key,
                        name text not null,
                        first_name text not null default '',
                        last_name text not null default '',
                        gender text not null default '',
                        birth_date text not null,
                        retire_age real,
                        comments text not null default '',
                        created_at text not null
                    )
                    """
                )
                conn.execute(
                    """
                    create table if not exists issuers (
                        id text primary key,
                        company_name text not null,
                        listing_status text not null default 'PRIVATE',
                        public_symbol text not null default '',
                        public_market text not null default '',
                        currency text not null default 'USD',
                        location text not null default 'USA',
                        listing_date text not null default '',
                        restriction_end_date text not null default '',
                        manual_share_value real not null default 0,
                        valuation_date text not null default '',
                        comments text not null default '',
                        created_at text not null,
                        updated_at text not null
                    )
                    """
                )
                conn.execute(
                    """
                    create table if not exists manual_securities (
                        id text primary key,
                        symbol text not null,
                        secondary_symbol text not null default '',
                        name text not null default '',
                        stock_market text not null,
                        asset_class text not null,
                        instrument_type text not null,
                        option_type text not null default '',
                        underlying_symbol text not null default '',
                        expiration_date text not null default '',
                        strike_price real not null default 0,
                        contract_multiplier real not null default 1,
                        issuer_id text not null default '',
                        grant_id text not null default '',
                        grant_date text not null default '',
                        vesting_start_date text not null default '',
                        tax_scheme text not null default '',
                        early_exercise_allowed integer not null default 0,
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
                    create table if not exists security_industry_overrides (
                        symbol text not null,
                        stock_market text not null default '',
                        industry text not null,
                        created_at text not null,
                        updated_at text not null,
                        primary key(symbol, stock_market)
                    )
                    """
                )
                conn.execute(
                    """
                    create table if not exists security_exposure_profiles (
                        symbol text not null,
                        stock_market text not null default '',
                        profile_json text not null,
                        created_at text not null,
                        updated_at text not null,
                        primary key(symbol, stock_market)
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
                        vest_date text not null default '',
                        purchase_price real not null default 0,
                        strike_price real not null default 0,
                        security_id text not null default '',
                        transition_id text not null default '',
                        vesting_schedule text not null default '{}',
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
                    create table if not exists equity_transitions (
                        id text primary key,
                        transition_type text not null,
                        source_security_id text not null default '',
                        target_security_id text not null default '',
                        account_db_id text not null default '',
                        quantity real not null default 0,
                        conversion_ratio real not null default 1,
                        effective_date text not null,
                        details text not null default '{}',
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
                        fund_name text not null default '',
                        pension_id text not null,
                        amount real not null,
                        factor real not null default 200,
                        account_id text not null default '',
                        birth_date text not null default '',
                        persons text not null default '[]',
                        comments text not null default '',
                        created_at text not null
                    )
                    """
                )
                conn.execute(
                    """
                    create table if not exists fund_amount_history (
                        id text primary key,
                        fund_id text not null references funds(id) on delete cascade,
                        amount_date text not null,
                        amount real not null,
                        source text not null default 'manual',
                        comments text not null default '',
                        created_at text not null,
                        updated_at text not null,
                        unique(fund_id, amount_date)
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
                conn.execute(
                    """
                    create table if not exists events (
                        id text primary key,
                        type text not null,
                        event_date text not null,
                        symbol text not null default '',
                        stock_market text not null default '',
                        account_db_id text not null default '',
                        gross_amount real not null default 0,
                        tax_amount real not null default 0,
                        net_amount real not null default 0,
                        currency text not null default '',
                        source text not null default '',
                        source_key text not null unique,
                        status text not null default 'pending',
                        transaction_id text not null default '',
                        details text not null default '{}',
                        created_at text not null,
                        updated_at text not null
                    )
                    """
                )
                conn.execute(
                    """
                    create table if not exists company_report_predictions (
                        id text primary key,
                        symbol text not null,
                        company_name text not null default '',
                        industry text not null default '',
                        created_at text not null,
                        horizon_date text not null,
                        model_version text not null,
                        score real not null,
                        label text not null,
                        direction text not null,
                        confidence text not null,
                        baseline text not null,
                        thesis text not null,
                        mermaid text not null,
                        actual text not null default '{}',
                        actual_direction text not null default 'pending',
                        accuracy_score real,
                        evaluation text not null default '',
                        evaluated_at text not null default ''
                    )
                    """
                )
                conn.execute("create index if not exists idx_account_snapshots_date on account_snapshots(snapshot_date)")
                conn.execute("create index if not exists idx_fund_amount_history_date on fund_amount_history(fund_id, amount_date)")
                conn.execute("create index if not exists idx_events_date on events(event_date)")
                conn.execute("create index if not exists idx_events_status on events(status)")
                conn.execute("create index if not exists idx_equity_transitions_source on equity_transitions(source_security_id, effective_date)")
                conn.execute("create index if not exists idx_company_report_predictions_symbol on company_report_predictions(symbol, created_at desc)")
                self._ensure_column(conn, "accounts", "persons", "text not null default '[]'")
                self._ensure_column(conn, "family_members", "first_name", "text not null default ''")
                self._ensure_column(conn, "family_members", "last_name", "text not null default ''")
                self._ensure_column(conn, "funds", "birth_date", "text not null default ''")
                self._ensure_column(conn, "funds", "persons", "text not null default '[]'")
                self._ensure_column(conn, "funds", "fund_name", "text not null default ''")
                self._ensure_column(conn, "funds", "account_id", "text not null default ''")
                self._ensure_column(conn, "transactions", "vest_date", "text not null default ''")
                self._ensure_column(conn, "transactions", "purchase_price", "real not null default 0")
                self._ensure_column(conn, "transactions", "strike_price", "real not null default 0")
                self._ensure_column(conn, "transactions", "security_id", "text not null default ''")
                self._ensure_column(conn, "transactions", "transition_id", "text not null default ''")
                self._ensure_column(conn, "transactions", "vesting_schedule", "text not null default '{}'")
                self._ensure_column(conn, "manual_securities", "issuer_id", "text not null default ''")
                self._ensure_column(conn, "manual_securities", "secondary_symbol", "text not null default ''")
                self._ensure_column(conn, "manual_securities", "grant_id", "text not null default ''")
                self._ensure_column(conn, "manual_securities", "grant_date", "text not null default ''")
                self._ensure_column(conn, "manual_securities", "vesting_start_date", "text not null default ''")
                self._ensure_column(conn, "manual_securities", "tax_scheme", "text not null default ''")
                self._ensure_column(conn, "manual_securities", "early_exercise_allowed", "integer not null default 0")
                conn.execute("create index if not exists idx_manual_securities_issuer on manual_securities(issuer_id)")
                conn.execute("create index if not exists idx_transactions_security on transactions(security_id)")
                self._split_existing_family_names(conn)
                self._normalize_existing_symbols(conn)
                self._migrate_equity_instruments(conn)
                self._seed_brokers_from_accounts(conn)
                self._seed_fund_amount_history(conn)
        except sqlite3.OperationalError as exc:
            if "readonly" not in str(exc).lower():
                raise

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"pragma table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"alter table {table} add column {column} {definition}")

    def _split_existing_family_names(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("select id, name, first_name, last_name from family_members").fetchall()
        for row in rows:
            if row["first_name"] or row["last_name"]:
                continue
            first_name, last_name = _split_person_name(row["name"])
            conn.execute(
                "update family_members set first_name = ?, last_name = ? where id = ?",
                (first_name, last_name, row["id"]),
            )

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
        conn.execute(
            """
            update manual_securities
            set secondary_symbol = substr(secondary_symbol, 4)
            where upper(substr(secondary_symbol, 1, 3)) = 'GF_'
            """
        )

    def _migrate_equity_instruments(self, conn: sqlite3.Connection) -> None:
        """Add stable identities without rewriting legacy grant symbols or transactions."""
        # RSU describes how shares were granted, not the underlying security.
        # Keep transaction.asset_class as RSU while migrating the reusable
        # instrument definition to an ordinary stock.
        conn.execute(
            """
            update manual_securities
            set instrument_type = 'STOCK', asset_class = 'EQUITY'
            where instrument_type = 'RSU' or asset_class = 'RSU'
            """
        )
        rows = conn.execute(
            """
            select * from manual_securities
            where instrument_type in ('STOCK_OPTION', 'EMPLOYEE_STOCK_OPTION', 'PRIVATE_STOCK')
              and trim(issuer_id) = ''
            order by created_at, id
            """
        ).fetchall()
        now = _now()
        non_public_markets = {"", "PRIVATE", "MANUAL", "LOCAL", "UNKNOWN", "N/A", "NONE", "ESOP"}
        for row in rows:
            issuer_id = str(uuid4())
            market = str(row["stock_market"] or "").upper().strip()
            underlying = _clean_security_symbol(row["underlying_symbol"])
            listing_status = "PUBLIC" if underlying and market not in non_public_markets else "PRIVATE"
            public_symbol = underlying if listing_status == "PUBLIC" else ""
            public_market = market if listing_status == "PUBLIC" else ""
            company_name = str(row["name"] or underlying or row["symbol"] or "Private company").strip()
            conn.execute(
                """
                insert into issuers
                  (id, company_name, listing_status, public_symbol, public_market, currency, location,
                   listing_date, restriction_end_date, manual_share_value, valuation_date, comments, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, '', '', 0, '', 'Migrated from an existing employee equity instrument', ?, ?)
                """,
                (issuer_id, company_name, listing_status, public_symbol, public_market, row["currency"], row["location"], now, now),
            )
            conn.execute("update manual_securities set issuer_id = ? where id = ?", (issuer_id, row["id"]))
        conn.execute(
            """
            update transactions
            set security_id = coalesce((
              select s.id from manual_securities s
              where s.symbol = transactions.symbol and s.stock_market = transactions.stock_market
              limit 1
            ), '')
            where trim(security_id) = ''
            """
        )
        conn.execute(
            """
            update manual_securities
            set vesting_start_date = grant_date
            where instrument_type = 'EMPLOYEE_STOCK_OPTION'
              and trim(vesting_start_date) = ''
              and trim(grant_date) != ''
            """
        )

    def _seed_brokers_from_accounts(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            select management_company, location, currency
            from accounts
            where trim(management_company) != ''
            group by lower(management_company)
            order by management_company
            """
        ).fetchall()
        for row in rows:
            country = _broker_country(row["location"])
            currency = str(row["currency"] or _currency_for_location(country)).upper().strip()
            if currency not in {"USD", "ILS", "EUR"}:
                currency = _currency_for_location(country)
            conn.execute(
                """
                insert into brokers
                  (id, name, country, currency, comments, created_at)
                values
                  (:id, :name, :country, :currency, '', :created_at)
                on conflict(name) do nothing
                """,
                {
                    "id": str(uuid4()),
                    "name": str(row["management_company"] or "").strip(),
                    "country": country,
                    "currency": currency,
                    "created_at": _now(),
                },
            )

    def _seed_fund_amount_history(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            select f.id, f.amount, f.created_at
            from funds f
            where not exists (select 1 from fund_amount_history h where h.fund_id = f.id)
            """
        ).fetchall()
        for row in rows:
            created_at = str(row["created_at"] or _now())
            amount_date = (_parse_date(created_at) or date.today()).isoformat()
            now = _now()
            conn.execute(
                """
                insert into fund_amount_history
                  (id, fund_id, amount_date, amount, source, comments, created_at, updated_at)
                values (?, ?, ?, ?, 'opening_balance', 'Initial saved amount', ?, ?)
                """,
                (str(uuid4()), row["id"], amount_date, float(row["amount"] or 0), created_at, now),
            )

    def normalize_source_data(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    "update transactions set source = ? where source like '%_import' and source <> ?",
                    (EXTERNAL_IMPORT_SOURCE, EXTERNAL_IMPORT_SOURCE),
                )
                conn.execute(
                    "update price_history set source = ? where source like '%_import' and source <> ?",
                    (EXTERNAL_IMPORT_SOURCE, EXTERNAL_IMPORT_SOURCE),
                )
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
                "security_industry_overrides": conn.execute("select count(*) from security_industry_overrides").fetchone()[0],
                "security_exposure_profiles": conn.execute("select count(*) from security_exposure_profiles").fetchone()[0],
                "issuers": conn.execute("select count(*) from issuers").fetchone()[0],
                "equity_transitions": conn.execute("select count(*) from equity_transitions").fetchone()[0],
                "brokers": conn.execute("select count(*) from brokers").fetchone()[0],
                "funds": conn.execute("select count(*) from funds").fetchone()[0],
                "fund_amount_history": conn.execute("select count(*) from fund_amount_history").fetchone()[0],
                "snapshots": conn.execute("select count(*) from account_snapshots").fetchone()[0],
                "events": conn.execute("select count(*) from events").fetchone()[0],
                "company_report_predictions": conn.execute("select count(*) from company_report_predictions").fetchone()[0],
                "app_preferences": conn.execute("select count(*) from app_preferences").fetchone()[0],
            }

    def get_preference(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute("select value from app_preferences where key = ?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return default

    def set_preference(self, key: str, value: Any) -> dict[str, Any]:
        clean_key = str(key or "").strip()
        if not clean_key:
            raise ValueError("Preference key is required")
        encoded = json.dumps(value if value is not None else {}, default=str)
        updated_at = _now()
        with self._sync_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    insert into app_preferences (key, value, updated_at)
                    values (?, ?, ?)
                    on conflict(key) do update set
                      value = excluded.value,
                      updated_at = excluded.updated_at
                    """,
                    (clean_key, encoded, updated_at),
                )
        return {"key": clean_key, "value": value if value is not None else {}, "updated_at": updated_at}

    def export_data(self) -> dict[str, Any]:
        with self._connect() as conn:
            data = {
                table: [_dict(row) for row in conn.execute(f"select {', '.join(columns)} from {table}").fetchall()]
                for table, columns in EXPORT_TABLES.items()
            }
        return {
            "version": 3,
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
        validate_portfolio_ownership(prepared["accounts"], prepared["funds"], sync_fund_persons=True)
        with self._sync_lock:
            with self._connect() as conn:
                conn.execute("delete from equity_transitions")
                conn.execute("delete from fund_amount_history")
                conn.execute("delete from account_snapshots")
                conn.execute("delete from events")
                conn.execute("delete from company_report_predictions")
                conn.execute("delete from funds")
                conn.execute("delete from price_history")
                conn.execute("delete from transactions")
                conn.execute("delete from security_industry_overrides")
                conn.execute("delete from security_exposure_profiles")
                conn.execute("delete from manual_securities")
                conn.execute("delete from issuers")
                conn.execute("delete from accounts")
                conn.execute("delete from family_members")
                conn.execute("delete from brokers")
                conn.execute("delete from app_preferences")
                for table in ["app_preferences", "brokers", "family_members", "accounts", "issuers", "manual_securities", "security_industry_overrides", "security_exposure_profiles", "transactions", "equity_transitions", "price_history", "funds", "fund_amount_history", "account_snapshots", "events", "company_report_predictions"]:
                    columns = EXPORT_TABLES[table]
                    placeholders = ", ".join([":" + column for column in columns])
                    conn.executemany(
                        f"insert into {table} ({', '.join(columns)}) values ({placeholders})",
                        prepared[table],
                    )
                self._migrate_equity_instruments(conn)
                self._seed_fund_amount_history(conn)
                for fund_row in conn.execute("select id from funds").fetchall():
                    self._sync_fund_amount_from_history(conn, fund_row["id"])
        return {"imported": {table: len(rows) for table, rows in prepared.items()}}

    def _clean_import_row(self, row: Any, columns: list[str]) -> dict[str, Any]:
        if not isinstance(row, dict):
            raise ValueError("Backup rows must be objects")
        record = {column: row.get(column) for column in columns}
        if columns == EXPORT_TABLES["app_preferences"]:
            value = record.get("value")
            return {
                "key": str(record.get("key") or "").strip(),
                "value": value if isinstance(value, str) else json.dumps(value if value is not None else {}, default=str),
                "updated_at": str(record.get("updated_at") or _now()),
            }
        for key in ["id", "key", "account_db_id", "fund_id", "issuer_id", "security_id", "transition_id", "source_security_id", "target_security_id", "symbol", "secondary_symbol", "stock_market", "asset_class", "instrument_type", "option_type", "underlying_symbol", "public_symbol", "public_market", "currency", "location", "trade_date", "price_date", "amount_date", "snapshot_date", "event_date", "effective_date", "expiration_date", "vest_date", "grant_id", "grant_date", "vesting_start_date", "tax_scheme", "listing_status", "listing_date", "restriction_end_date", "valuation_date", "transition_type", "source_key", "transaction_id", "status", "company_name", "industry", "horizon_date", "model_version", "label", "direction", "confidence", "actual_direction", "evaluation", "evaluated_at"]:
            if key in record and record[key] is not None:
                record[key] = str(record[key])
        if "symbol" in record:
            record["symbol"] = _clean_security_symbol(record["symbol"])
        if "secondary_symbol" in record:
            record["secondary_symbol"] = _clean_security_symbol(record["secondary_symbol"])
        if "underlying_symbol" in record:
            record["underlying_symbol"] = _clean_security_symbol(record["underlying_symbol"])
        if "value" in record:
            record["value"] = record["value"] if isinstance(record.get("value"), str) else json.dumps(record.get("value") if record.get("value") is not None else {}, default=str)
        for key in ["type", "name", "first_name", "last_name", "gender", "username", "account_id", "management_company", "comments", "source", "kind", "fund_name", "pension_id", "created_at", "updated_at", "birth_date", "vest_date", "country", "currency", "details", "vesting_schedule", "baseline", "thesis", "mermaid", "actual", "issuer_id", "security_id", "transition_id", "source_security_id", "target_security_id", "grant_id", "grant_date", "vesting_start_date", "tax_scheme", "listing_date", "restriction_end_date", "valuation_date", "public_symbol", "public_market", "secondary_symbol"]:
            if key in record:
                default_text = "{}" if key in {"details", "vesting_schedule", "actual"} else ""
                value = record.get(key)
                record[key] = value if isinstance(value, str) else json.dumps(value if value is not None else {}, default=str) if default_text else str(value or "")
        if "first_name" in record and "last_name" in record and not (record["first_name"] or record["last_name"]):
            record["first_name"], record["last_name"] = _split_person_name(record.get("name"))
            record["name"] = _full_person_name(record["first_name"], record["last_name"]) or record.get("name", "")
        if "persons" in record:
            record["persons"] = json.dumps(_clean_persons(record.get("persons")))
        for key in ["initial_cash", "quantity", "price_input", "price", "amount", "factor", "value", "cash", "profit", "profit_percent", "strike_price", "purchase_price", "contract_multiplier", "manual_share_value", "conversion_ratio", "early_exercise_allowed", "retire_age", "gross_amount", "tax_amount", "net_amount", "score"]:
            if key in record:
                record[key] = _number(record.get(key), 0)
        if "listing_status" in record and not record.get("listing_status"):
            record["listing_status"] = "PRIVATE"
        if "updated_at" in record and not record.get("updated_at"):
            record["updated_at"] = str(record.get("created_at") or _now())
        if "accuracy_score" in record and record.get("accuracy_score") is not None:
            record["accuracy_score"] = _number(record.get("accuracy_score"), 0)
        return record

    def list_company_report_predictions(self, symbol: str = "") -> list[dict[str, Any]]:
        symbol_key = _clean_security_symbol(symbol)
        with self._connect() as conn:
            if symbol_key:
                rows = conn.execute(
                    "select * from company_report_predictions where symbol = ? order by created_at desc",
                    (symbol_key,),
                ).fetchall()
            else:
                rows = conn.execute("select * from company_report_predictions order by created_at desc").fetchall()
        return [self._company_report_prediction_out(row) for row in rows]

    def company_report_prediction_for_batch(self, batch_id: str, symbol: str) -> dict[str, Any] | None:
        normalized_batch_id = str(batch_id or "").strip()
        normalized_symbol = _clean_security_symbol(symbol)
        if not normalized_batch_id or not normalized_symbol:
            return None
        for prediction in self.list_company_report_predictions(normalized_symbol):
            baseline = prediction.get("baseline") if isinstance(prediction.get("baseline"), dict) else {}
            batch = baseline.get("batch") if isinstance(baseline.get("batch"), dict) else {}
            if str(batch.get("id") or "").strip() == normalized_batch_id:
                return prediction
        return None

    def save_company_report_prediction(self, payload: dict[str, Any]) -> dict[str, Any]:
        symbol = _clean_security_symbol(payload.get("symbol"))
        if not symbol:
            raise ValueError("Prediction symbol is required")
        direction = str(payload.get("direction") or "neutral").lower()
        if direction not in {"positive", "neutral", "negative"}:
            raise ValueError("Prediction direction must be positive, neutral, or negative")
        confidence = str(payload.get("confidence") or "Low").title()
        if confidence not in {"High", "Medium", "Low"}:
            raise ValueError("Prediction confidence must be High, Medium, or Low")
        score = max(0, min(100, _number(payload.get("score"), 0)))
        record = {
            "id": str(payload.get("id") or uuid4()),
            "symbol": symbol,
            "company_name": str(payload.get("company_name") or "").strip(),
            "industry": str(payload.get("industry") or "").strip(),
            "created_at": str(payload.get("created_at") or _now()),
            "horizon_date": _date_string(payload.get("horizon_date") or date.today() + timedelta(days=365)),
            "model_version": str(payload.get("model_version") or "report-outlook-v1"),
            "score": score,
            "label": str(payload.get("label") or "Mixed").strip(),
            "direction": direction,
            "confidence": confidence,
            "baseline": json.dumps(payload.get("baseline") if isinstance(payload.get("baseline"), dict) else {}, default=str),
            "thesis": str(payload.get("thesis") or "").strip(),
            "mermaid": str(payload.get("mermaid") or "").strip(),
            "actual": json.dumps(payload.get("actual") if isinstance(payload.get("actual"), dict) else {}, default=str),
            "actual_direction": str(payload.get("actual_direction") or "pending").lower(),
            "accuracy_score": payload.get("accuracy_score"),
            "evaluation": str(payload.get("evaluation") or "").strip(),
            "evaluated_at": str(payload.get("evaluated_at") or ""),
        }
        with self._connect() as conn:
            conn.execute(
                """
                insert into company_report_predictions
                  (id, symbol, company_name, industry, created_at, horizon_date, model_version, score, label, direction, confidence, baseline, thesis, mermaid, actual, actual_direction, accuracy_score, evaluation, evaluated_at)
                values
                  (:id, :symbol, :company_name, :industry, :created_at, :horizon_date, :model_version, :score, :label, :direction, :confidence, :baseline, :thesis, :mermaid, :actual, :actual_direction, :accuracy_score, :evaluation, :evaluated_at)
                on conflict(id) do update set
                  actual = excluded.actual,
                  actual_direction = excluded.actual_direction,
                  accuracy_score = excluded.accuracy_score,
                  evaluation = excluded.evaluation,
                  evaluated_at = excluded.evaluated_at
                """,
                record,
            )
            row = conn.execute("select * from company_report_predictions where id = ?", (record["id"],)).fetchone()
        return self._company_report_prediction_out(row or record)

    def evaluate_company_report_prediction(self, prediction_id: str, actual: dict[str, Any], actual_direction: str, accuracy_score: float | None, evaluation: str) -> dict[str, Any]:
        direction = str(actual_direction or "pending").lower()
        if direction not in {"positive", "neutral", "negative", "pending", "inconclusive"}:
            raise ValueError("Invalid actual direction")
        with self._connect() as conn:
            row = conn.execute("select * from company_report_predictions where id = ?", (prediction_id,)).fetchone()
            if not row:
                raise ValueError("Prediction not found")
            conn.execute(
                """
                update company_report_predictions
                set actual = ?, actual_direction = ?, accuracy_score = ?, evaluation = ?, evaluated_at = ?
                where id = ?
                """,
                (
                    json.dumps(actual if isinstance(actual, dict) else {}, default=str),
                    direction,
                    accuracy_score,
                    str(evaluation or "").strip(),
                    _now() if direction not in {"pending", "inconclusive"} else "",
                    prediction_id,
                ),
            )
            updated = conn.execute("select * from company_report_predictions where id = ?", (prediction_id,)).fetchone()
        return self._company_report_prediction_out(updated)

    def delete_company_report_prediction(self, prediction_id: str) -> dict[str, Any]:
        normalized_id = str(prediction_id or "").strip()
        if not normalized_id:
            raise ValueError("Prediction not found")
        with self._connect() as conn:
            row = conn.execute("select * from company_report_predictions where id = ?", (normalized_id,)).fetchone()
            if not row:
                raise ValueError("Prediction not found")
            conn.execute("delete from company_report_predictions where id = ?", (normalized_id,))
        return self._company_report_prediction_out(row)

    def company_report_scorecard(self, prediction_ids: set[str] | None = None) -> dict[str, Any]:
        stored_rows = self.list_company_report_predictions()
        if prediction_ids is not None:
            stored_rows = [item for item in stored_rows if item.get("id") in prediction_ids]
        rows = []
        seen_batch_symbols: set[tuple[str, str]] = set()
        duplicate_batch_records = 0
        for item in stored_rows:
            baseline = item.get("baseline") if isinstance(item.get("baseline"), dict) else {}
            batch = baseline.get("batch") if isinstance(baseline.get("batch"), dict) else {}
            batch_id = str(batch.get("id") or "").strip()
            key = (batch_id, str(item.get("symbol") or ""))
            if batch_id and key in seen_batch_symbols:
                duplicate_batch_records += 1
                continue
            if batch_id:
                seen_batch_symbols.add(key)
            rows.append(item)
        evaluated = [item for item in rows if item.get("accuracy_score") is not None]
        average = round(sum(float(item["accuracy_score"]) for item in evaluated) / len(evaluated), 1) if evaluated else None
        by_symbol: dict[str, list[float]] = {}
        by_industry: dict[str, list[float]] = {}
        by_model_version: dict[str, list[float]] = {}
        by_horizon_months: dict[str, list[float]] = {}
        by_confidence: dict[str, list[float]] = {}
        by_direction: dict[str, list[float]] = {}
        for item in evaluated:
            by_symbol.setdefault(item["symbol"], []).append(float(item["accuracy_score"]))
            if item.get("industry"):
                by_industry.setdefault(item["industry"], []).append(float(item["accuracy_score"]))
            by_model_version.setdefault(str(item.get("model_version") or "unknown"), []).append(float(item["accuracy_score"]))
            horizon_date = _date_string(item.get("horizon_date"))
            created_date = _date_string(str(item.get("created_at") or "")[:10])
            try:
                horizon_months = max(0, round((date.fromisoformat(horizon_date) - date.fromisoformat(created_date)).days / 30))
            except ValueError:
                horizon_months = 0
            by_horizon_months.setdefault(f"{horizon_months} months" if horizon_months else "unknown", []).append(float(item["accuracy_score"]))
            by_confidence.setdefault(str(item.get("confidence") or "unknown"), []).append(float(item["accuracy_score"]))
            by_direction.setdefault(str(item.get("direction") or "unknown"), []).append(float(item["accuracy_score"]))
        aggregate = lambda groups: [
            {"name": name, "evaluated": len(scores), "accuracy_percent": round(sum(scores) / len(scores), 1)}
            for name, scores in sorted(groups.items())
        ]
        validation_passed = bool(
            len(evaluated) >= COMPANY_OUTLOOK_MIN_EVALUATED_PREDICTIONS
            and average is not None
            and average >= COMPANY_OUTLOOK_ACCURACY_TARGET_PERCENT
        )
        return {
            "total": len(rows),
            "stored_total": len(stored_rows),
            "duplicate_batch_records": duplicate_batch_records,
            "evaluated": len(evaluated),
            "pending": len([item for item in rows if item.get("actual_direction") == "pending"]),
            "accuracy_percent": average,
            "quality_gate": {
                "target_accuracy_percent": COMPANY_OUTLOOK_ACCURACY_TARGET_PERCENT,
                "minimum_evaluated_predictions": COMPANY_OUTLOOK_MIN_EVALUATED_PREDICTIONS,
                "passed": validation_passed,
                "status": "validated" if validation_passed else "not validated",
            },
            "by_symbol": aggregate(by_symbol),
            "by_industry": aggregate(by_industry),
            "by_model_version": aggregate(by_model_version),
            "by_horizon": aggregate(by_horizon_months),
            "by_confidence": aggregate(by_confidence),
            "by_predicted_direction": aggregate(by_direction),
        }

    def _company_report_prediction_out(self, row: Any) -> dict[str, Any]:
        item = _dict(row)
        for key in ["baseline", "actual"]:
            try:
                item[key] = json.loads(item.get(key) or "{}")
            except (TypeError, json.JSONDecodeError):
                item[key] = {}
        item["score"] = float(item.get("score") or 0)
        if item.get("accuracy_score") is not None:
            item["accuracy_score"] = float(item["accuracy_score"])
        return item

    def backup_dir(self) -> Path:
        path = data_dir() / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def sqlite_snapshot_bytes(self) -> bytes:
        """Return a transactionally consistent SQLite snapshot for full backups."""
        snapshot_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="portfolio-snapshot-", suffix=".sqlite3", delete=False) as snapshot:
                snapshot_path = Path(snapshot.name)
            with self._sync_lock:
                with self._connect() as source, sqlite3.connect(snapshot_path) as target:
                    source.backup(target)
            return snapshot_path.read_bytes()
        finally:
            if snapshot_path is not None:
                try:
                    snapshot_path.unlink()
                except OSError:
                    pass

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
        paths = [
            path
            for pattern in ("portfolio-full-*.zip", "portfolio-data-*.json")
            for path in backup_dir.glob(pattern)
        ]
        for path in sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True):
            stat = path.stat()
            backups.append(
                {
                    "filename": path.name,
                    "path": str(path),
                    "type": "full" if path.suffix.lower() == ".zip" else "data",
                    "size_kb": round(stat.st_size / 1024, 1),
                    "modified_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
                }
            )
        return backups

    def list_accounts(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select * from accounts order by management_company, username, account_id").fetchall()
            accounts = []
            for row in rows:
                account = self._account_out(row)
                account.update(self._account_deletion_state(conn, row["id"]))
                accounts.append(account)
        return accounts

    def _account_deletion_state(self, conn: sqlite3.Connection, account_db_id: str) -> dict[str, Any]:
        counts = {
            "transactions": conn.execute("select count(*) from transactions where account_db_id = ?", (account_db_id,)).fetchone()[0],
            "funds": conn.execute("select count(*) from funds where account_id = ?", (account_db_id,)).fetchone()[0],
            "account_snapshots": conn.execute("select count(*) from account_snapshots where account_db_id = ?", (account_db_id,)).fetchone()[0],
            "events": conn.execute("select count(*) from events where account_db_id = ?", (account_db_id,)).fetchone()[0],
            "equity_transitions": conn.execute("select count(*) from equity_transitions where account_db_id = ?", (account_db_id,)).fetchone()[0],
        }
        return {
            "attachment_counts": counts,
            "attached_records": sum(counts.values()),
            "can_delete": not any(counts.values()),
        }

    def list_brokers(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select * from brokers order by name").fetchall()
        return [self._broker_out(row) for row in rows]

    def save_broker(self, payload: dict[str, Any]) -> dict[str, Any]:
        country = _broker_country(payload.get("country") or payload.get("location"))
        currency = str(payload.get("currency") or _currency_for_location(country)).upper().strip()
        record = {
            "id": str(payload.get("id") or uuid4()),
            "name": str(payload.get("name") or "").strip(),
            "country": country,
            "currency": currency,
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": str(payload.get("created_at") or _now()),
        }
        if not record["name"]:
            raise ValueError("Broker name is required")
        if record["currency"] not in {"USD", "ILS", "EUR"}:
            raise ValueError("Broker currency must be ILS, USD, or EUR")
        with self._connect() as conn:
            existing = conn.execute("select * from brokers where id = ?", (record["id"],)).fetchone()
            if existing:
                old_name = str(existing["name"] or "").strip()
                if old_name and old_name.lower() != record["name"].lower():
                    conn.execute(
                        """
                        update accounts
                        set management_company = :name
                        where lower(management_company) = lower(:old_name)
                        """,
                        {"name": record["name"], "old_name": old_name},
                    )
                conn.execute(
                    """
                    update brokers
                    set name = :name,
                        country = :country,
                        currency = :currency,
                        comments = :comments
                    where id = :id
                    """,
                    record,
                )
                row = conn.execute("select * from brokers where id = ?", (record["id"],)).fetchone()
            else:
                conn.execute(
                    """
                    insert into brokers
                      (id, name, country, currency, comments, created_at)
                    values
                      (:id, :name, :country, :currency, :comments, :created_at)
                    on conflict(name) do update set
                      country = excluded.country,
                      currency = excluded.currency,
                      comments = excluded.comments
                    """,
                    record,
                )
                row = conn.execute("select * from brokers where name = ?", (record["name"],)).fetchone()
        return self._broker_out(row or record)

    def broker_account_count(self, broker_name: str) -> int:
        name = str(broker_name or "").strip()
        if not name:
            return 0
        with self._connect() as conn:
            return int(conn.execute("select count(*) from accounts where lower(management_company) = lower(?)", (name,)).fetchone()[0])

    def delete_broker(self, broker_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("select * from brokers where id = ?", (broker_id,)).fetchone()
            if not row:
                return False
            broker = self._broker_out(row)
            if broker["attached_accounts"]:
                raise ValueError("Broker is attached to at least one account")
            conn.execute("delete from brokers where id = ?", (broker_id,))
        return True

    def list_family_members(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select * from family_members order by name, birth_date").fetchall()
        return [self._family_member_out(row) for row in rows]

    def save_family_member(self, payload: dict[str, Any]) -> dict[str, Any]:
        first_name = str(payload.get("first_name") or "").strip()
        last_name = str(payload.get("last_name") or "").strip()
        if not first_name and not last_name:
            first_name, last_name = _split_person_name(payload.get("name"))
        name = _full_person_name(first_name, last_name)
        record = {
            "id": str(payload.get("id") or uuid4()),
            "name": name,
            "first_name": first_name,
            "last_name": last_name,
            "gender": str(payload.get("gender") or "").strip(),
            "birth_date": _clean_birth_date(payload.get("birth_date") or payload.get("birthday")),
            "retire_age": _optional_number(payload.get("retire_age")),
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": str(payload.get("created_at") or _now()),
        }
        if not record["first_name"]:
            raise ValueError("Family member first name is required")
        if not record["birth_date"]:
            raise ValueError("Family member birthday is required")
        with self._connect() as conn:
            conn.execute(
                """
                insert into family_members
                  (id, name, first_name, last_name, gender, birth_date, retire_age, comments, created_at)
                values
                  (:id, :name, :first_name, :last_name, :gender, :birth_date, :retire_age, :comments, :created_at)
                on conflict(id) do update set
                  name = excluded.name,
                  first_name = excluded.first_name,
                  last_name = excluded.last_name,
                  gender = excluded.gender,
                  birth_date = excluded.birth_date,
                  retire_age = excluded.retire_age,
                  comments = excluded.comments
                """,
                record,
            )
            self._sync_family_member_to_accounts(conn, record)
        return self._family_member_out(record)

    def family_member_account_count(self, member_id: str) -> int:
        return len(self.family_member_accounts(member_id))

    def family_member_accounts(self, member_id: str) -> list[dict[str, Any]]:
        account_refs = []
        for account in self.list_accounts():
            if any(str(person.get("member_id") or person.get("id") or "") == str(member_id) for person in account.get("persons", [])):
                account_refs.append(
                    {
                        "id": account["id"],
                        "label": _account_label(account),
                        "type": account.get("type", ""),
                        "currency": account.get("currency", ""),
                    }
                )
        return account_refs

    def _sync_family_member_to_accounts(self, conn: sqlite3.Connection, member: dict[str, Any]) -> None:
        member_id = str(member.get("id") or "")
        if not member_id:
            return
        rows = conn.execute("select id, persons from accounts").fetchall()
        for row in rows:
            persons = _clean_persons(row["persons"])
            changed = False
            for person in persons:
                if str(person.get("member_id") or person.get("id") or "") != member_id:
                    continue
                person.update(
                    {
                        "member_id": member_id,
                        "name": member["name"],
                        "first_name": member["first_name"],
                        "last_name": member["last_name"],
                        "gender": member.get("gender", ""),
                        "birth_date": member["birth_date"],
                        "age": age_from_birth_date(member["birth_date"]),
                    }
                )
                if member.get("retire_age") is not None:
                    person["retire_age"] = member["retire_age"]
                else:
                    person.pop("retire_age", None)
                changed = True
            if changed:
                conn.execute("update accounts set persons = ? where id = ?", (json.dumps(persons), row["id"]))

    def delete_family_member(self, member_id: str) -> bool:
        if self.family_member_account_count(member_id):
            raise ValueError("Family member is attached to at least one account")
        with self._connect() as conn:
            before = conn.execute("select count(*) from family_members where id = ?", (member_id,)).fetchone()[0]
            conn.execute("delete from family_members where id = ?", (member_id,))
        return bool(before)

    def save_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        account_id = str(payload.get("id") or uuid4())
        location = str(payload.get("location") or "USA").strip()
        account_type = _choice(payload.get("type"), ACCOUNT_TYPES, "Investment")
        persons = _validated_account_persons(account_type, payload.get("persons"))
        record = {
            "id": account_id,
            "type": account_type,
            "location": location,
            "currency": str(payload.get("currency") or _currency_for_location(location)).upper().strip(),
            "initial_cash": _number(payload.get("initial_cash"), 0),
            "username": str(payload.get("username") or "").strip(),
            "account_id": str(payload.get("account_id") or "").strip(),
            "management_company": str(payload.get("management_company") or "").strip(),
            "persons": json.dumps(persons),
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": str(payload.get("created_at") or _now()),
        }
        with self._connect() as conn:
            conn.execute(
                """
                insert into accounts
                  (id, type, location, currency, initial_cash, username, account_id, management_company, persons, comments, created_at)
                values
                  (:id, :type, :location, :currency, :initial_cash, :username, :account_id, :management_company, :persons, :comments, :created_at)
                on conflict(id) do update set
                  type = excluded.type,
                  location = excluded.location,
                  currency = excluded.currency,
                  initial_cash = excluded.initial_cash,
                  username = excluded.username,
                  account_id = excluded.account_id,
                  management_company = excluded.management_company,
                  persons = excluded.persons,
                  comments = excluded.comments
                """,
                record,
            )
            if record["type"] == "Long-Term Savings":
                conn.execute("update funds set persons = ?, birth_date = ? where account_id = ?", (record["persons"], persons[0]["birth_date"], record["id"]))
            row = conn.execute("select * from accounts where id = ?", (record["id"],)).fetchone()
        return self._account_out(row or record)

    def delete_account(self, account_db_id: str) -> bool:
        with self._connect() as conn:
            before = conn.execute("select count(*) from accounts where id = ?", (account_db_id,)).fetchone()[0]
            if before:
                deletion_state = self._account_deletion_state(conn, account_db_id)
                if not deletion_state["can_delete"]:
                    attached = ", ".join(
                        f"{name}={count}"
                        for name, count in deletion_state["attachment_counts"].items()
                        if count
                    )
                    raise ValueError(f"Account has attached data and cannot be removed: {attached}")
            conn.execute("delete from accounts where id = ?", (account_db_id,))
        return bool(before)

    def list_manual_securities(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select s.*,
                       i.company_name,
                       i.listing_status,
                       i.public_symbol,
                       i.public_market,
                       i.listing_date,
                       i.restriction_end_date,
                       i.manual_share_value,
                       i.valuation_date
                from manual_securities s
                left join issuers i on i.id = s.issuer_id
                order by coalesce(i.company_name, s.name), s.grant_date, s.symbol
                """
            ).fetchall()
            items = []
            for row in rows:
                item = _dict(row)
                item.update(self._manual_security_deletion_state(conn, item))
                items.append(item)
        return items

    def list_security_industry_overrides(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select symbol, stock_market, industry, created_at, updated_at
                from security_industry_overrides
                order by symbol, stock_market
                """
            ).fetchall()
        return [_dict(row) for row in rows]

    def list_security_exposure_profiles(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select symbol, stock_market, profile_json, created_at, updated_at "
                "from security_exposure_profiles order by symbol, stock_market"
            ).fetchall()
        return [
            {**_dict(row), "profile": json.loads(row["profile_json"])}
            for row in rows
        ]

    def save_security_exposure_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        symbol = str(payload.get("symbol") or "").strip().upper()
        stock_market = str(payload.get("stock_market") or "").strip().upper()
        if not symbol or len(symbol) > 80 or len(stock_market) > 80:
            raise ValueError("A valid security symbol and market are required")
        profile = payload.get("profile")
        if not isinstance(profile, dict):
            raise ValueError("Exposure profile must be an object")
        asset_focus = str(profile.get("asset_focus") or "").strip()
        if asset_focus and asset_focus not in EXPOSURE_ASSET_FOCUSES:
            raise ValueError("Choose a supported underlying asset type")
        fx_basis = str(profile.get("fx_basis") or "unknown").strip()
        if fx_basis not in {"unknown", "reported", "estimated"}:
            raise ValueError("Currency exposure source must be reported, estimated, or unknown")
        fx_reference_currency = str(profile.get("fx_reference_currency") or "").strip().upper()
        if fx_reference_currency and (len(fx_reference_currency) != 3 or not fx_reference_currency.isalpha()):
            raise ValueError("Reference FX currency must be a three-letter code")
        exposures = profile.get("currency_exposures") or []
        if not isinstance(exposures, list) or len(exposures) > 12:
            raise ValueError("Currency exposures must be a list of at most 12 currencies")
        if fx_basis == "unknown" and exposures:
            raise ValueError("Choose a source before entering currency exposures")
        cleaned_exposures = []
        seen_currencies = set()
        for exposure in exposures:
            if not isinstance(exposure, dict):
                raise ValueError("Each currency exposure must be an object")
            currency = str(exposure.get("currency") or "").strip().upper()
            if len(currency) != 3 or not currency.isalpha() or currency in seen_currencies:
                raise ValueError("Currency codes must be unique three-letter codes")
            try:
                percent = float(exposure.get("percent"))
            except (TypeError, ValueError) as exc:
                raise ValueError("Currency exposure percent must be a number") from exc
            if not math.isfinite(percent) or percent <= 0 or percent > 100:
                raise ValueError("Currency exposure percent must be between 0 and 100")
            seen_currencies.add(currency)
            cleaned_exposures.append({"currency": currency, "percent": percent})
        if sum(entry["percent"] for entry in cleaned_exposures) > 100.00001:
            raise ValueError("Currency exposure percentages cannot exceed 100")
        limit = profile.get("fx_policy_limit_percent")
        if limit not in (None, ""):
            try:
                limit = float(limit)
            except (TypeError, ValueError) as exc:
                raise ValueError("Policy limit must be a number") from exc
            if not math.isfinite(limit) or limit < 0 or limit > 1000:
                raise ValueError("Policy limit must be between 0 and 1000")
        else:
            limit = None
        as_of = str(profile.get("as_of") or "").strip()
        if as_of:
            try:
                date.fromisoformat(as_of)
            except ValueError as exc:
                raise ValueError("Exposure date must be a valid date") from exc
        if fx_basis == "reported" and cleaned_exposures and not as_of:
            raise ValueError("Reported currency exposures require an information date")
        def short_text(key: str) -> str:
            value = str(profile.get(key) or "").strip()
            if len(value) > 240:
                raise ValueError(f"{key} is too long")
            return value
        geography = short_text("geography")
        sector_exposure = short_text("sector_exposure")
        if asset_focus == "single_country_equity" and not geography:
            raise ValueError("A single-country equity profile requires an underlying country")
        if asset_focus == "sector_equity" and not sector_exposure:
            raise ValueError("A sector equity profile requires an underlying sector")
        cleaned_profile = {
            "asset_focus": asset_focus,
            "geography": geography,
            "sector_exposure": sector_exposure,
            "fx_basis": fx_basis,
            "fx_reference_currency": fx_reference_currency,
            "currency_exposures": cleaned_exposures,
            "fx_policy_limit_percent": limit,
            "source_note": short_text("source_note"),
            "as_of": as_of,
        }
        now = _now()
        with self._sync_lock:
            with self._connect() as conn:
                conn.execute(
                    """insert into security_exposure_profiles
                       (symbol, stock_market, profile_json, created_at, updated_at)
                       values (?, ?, ?, ?, ?)
                       on conflict(symbol, stock_market) do update set
                         profile_json = excluded.profile_json, updated_at = excluded.updated_at""",
                    (symbol, stock_market, json.dumps(cleaned_profile), now, now),
                )
        return {"symbol": symbol, "stock_market": stock_market, "profile": cleaned_profile, "updated_at": now}

    def delete_security_exposure_profile(self, symbol: str, stock_market: str = "") -> bool:
        clean_symbol = str(symbol or "").strip().upper()
        clean_market = str(stock_market or "").strip().upper()
        if not clean_symbol:
            raise ValueError("Security symbol is required")
        with self._sync_lock:
            with self._connect() as conn:
                deleted = conn.execute(
                    "delete from security_exposure_profiles where symbol = ? and stock_market = ?",
                    (clean_symbol, clean_market),
                ).rowcount
        return bool(deleted)

    def save_security_industry_override(self, payload: dict[str, Any]) -> dict[str, Any]:
        symbol = str(payload.get("symbol") or "").strip().upper()
        stock_market = str(payload.get("stock_market") or "").strip().upper()
        industry = str(payload.get("industry") or "").strip()
        if not symbol:
            raise ValueError("Security symbol is required")
        if not industry:
            raise ValueError("Industry is required")
        now = _now()
        with self._sync_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    insert into security_industry_overrides (symbol, stock_market, industry, created_at, updated_at)
                    values (?, ?, ?, ?, ?)
                    on conflict(symbol, stock_market) do update set
                      industry = excluded.industry,
                      updated_at = excluded.updated_at
                    """,
                    (symbol, stock_market, industry, now, now),
                )
                row = conn.execute(
                    """
                    select symbol, stock_market, industry, created_at, updated_at
                    from security_industry_overrides
                    where symbol = ? and stock_market = ?
                    """,
                    (symbol, stock_market),
                ).fetchone()
        return _dict(row)

    def delete_security_industry_override(self, symbol: str, stock_market: str = "") -> bool:
        clean_symbol = str(symbol or "").strip().upper()
        clean_market = str(stock_market or "").strip().upper()
        if not clean_symbol:
            raise ValueError("Security symbol is required")
        with self._sync_lock:
            with self._connect() as conn:
                before = conn.execute(
                    "select count(*) from security_industry_overrides where symbol = ? and stock_market = ?",
                    (clean_symbol, clean_market),
                ).fetchone()[0]
                conn.execute(
                    "delete from security_industry_overrides where symbol = ? and stock_market = ?",
                    (clean_symbol, clean_market),
                )
        return bool(before)

    def _manual_security_deletion_state(
        self,
        conn: sqlite3.Connection,
        security: dict[str, Any] | sqlite3.Row,
    ) -> dict[str, Any]:
        security_id = str(security["id"] or "")
        symbol = str(security["symbol"] or "")
        secondary_symbol = str(security["secondary_symbol"] or "")
        stock_market = str(security["stock_market"] or "")
        counts = {
            "transactions": conn.execute(
                """
                select count(*) from transactions
                where security_id = ?
                   or (trim(security_id) = '' and symbol = ? and stock_market = ?)
                """,
                (security_id, symbol, stock_market),
            ).fetchone()[0],
            "price_history": conn.execute(
                "select count(*) from price_history where symbol in (?, ?) and stock_market = ?",
                (symbol, secondary_symbol, stock_market),
            ).fetchone()[0],
            "events": conn.execute(
                "select count(*) from events where symbol in (?, ?) and stock_market = ?",
                (symbol, secondary_symbol, stock_market),
            ).fetchone()[0],
            "equity_transitions": conn.execute(
                """
                select count(*) from equity_transitions
                where source_security_id = ? or target_security_id = ?
                """,
                (security_id, security_id),
            ).fetchone()[0],
        }
        return {
            "attachment_counts": counts,
            "attached_records": sum(counts.values()),
            "can_delete": not any(counts.values()),
        }

    def save_manual_security(
        self,
        payload: dict[str, Any],
        *,
        _conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        requested_instrument_type = str(payload.get("instrument_type") or "").upper().strip()
        instrument_type = "STOCK" if requested_instrument_type == "RSU" else _choice(
            requested_instrument_type,
            INSTRUMENT_TYPES,
            "STOCK",
        )
        asset_class = _asset_class_for_instrument(instrument_type, payload.get("asset_class"))
        location = str(payload.get("location") or "USA").strip()
        currency = str(payload.get("currency") or _currency_for_location(location)).upper().strip()
        option_type = str(payload.get("option_type") or "").upper().strip()
        expiration_date = _optional_date_string(payload.get("expiration_date"))
        is_employee_option = instrument_type == "EMPLOYEE_STOCK_OPTION"
        is_legacy_option_grant = instrument_type == "STOCK_OPTION"
        is_exchange_option = instrument_type == "OPTION"
        is_option = is_employee_option or is_legacy_option_grant or is_exchange_option
        grant_date = _optional_date_string(payload.get("grant_date"))
        vesting_start_date = _optional_date_string(payload.get("vesting_start_date")) or grant_date
        issuer_id = str(payload.get("issuer_id") or "").strip()
        security_id = str(payload.get("id") or uuid4())
        existing = self.manual_security_by_id(security_id) if payload.get("id") else None

        if is_employee_option:
            if currency not in SUPPORTED_MANAGEMENT_CURRENCIES:
                raise ValueError("Employee stock-option currency must be ILS, USD, or EUR")
            company_name = str(payload.get("company_name") or payload.get("issuer_name") or payload.get("name") or "").strip()
            if not company_name:
                raise ValueError("Company name is required for employee stock options")
            if not grant_date:
                raise ValueError("Grant date is required for employee stock options")
            if not vesting_start_date:
                raise ValueError("Vesting start date is required for employee stock options")
            if not expiration_date:
                raise ValueError("Expiration date is required for employee stock options")
            if _number(payload.get("strike_price"), 0) <= 0:
                raise ValueError("Strike price must be greater than zero for employee stock options")
            issuer_existing: dict[str, Any] = {}
            lookup_issuer_id = issuer_id or str((existing or {}).get("issuer_id") or "")
            with self._connect() as conn:
                if lookup_issuer_id:
                    issuer_row = conn.execute("select * from issuers where id = ?", (lookup_issuer_id,)).fetchone()
                else:
                    issuer_row = conn.execute(
                        """
                        select * from issuers
                        where lower(trim(company_name)) = lower(trim(?))
                          and currency = ? and location = ?
                        order by created_at
                        limit 1
                        """,
                        (company_name, currency, location),
                    ).fetchone()
                if issuer_row:
                    issuer_existing = _dict(issuer_row)
            listing_status = _choice(
                payload.get("listing_status") or issuer_existing.get("listing_status"),
                ISSUER_LISTING_STATUSES,
                "PRIVATE",
            )
            if str(issuer_existing.get("listing_status") or "").upper() == "PUBLIC":
                listing_status = "PUBLIC"
            public_symbol = _clean_security_symbol(payload.get("public_symbol") or payload.get("underlying_symbol") or payload.get("symbol"))
            public_market = str(payload.get("public_market") or payload.get("stock_market") or "").upper().strip()
            if listing_status == "PUBLIC":
                public_symbol = public_symbol or _clean_security_symbol(issuer_existing.get("public_symbol"))
                public_market = public_market or str(issuer_existing.get("public_market") or "").upper().strip()
            if listing_status == "PUBLIC" and (not public_symbol or not public_market):
                raise ValueError("Public symbol and stock market are required for a public company")
            if listing_status == "PRIVATE":
                public_symbol = ""
                public_market = ""
            issuer_id = lookup_issuer_id or str(issuer_existing.get("id") or uuid4())
            now = _now()
            share_value_input = payload.get("manual_share_value")
            manual_share_value = _number(
                share_value_input,
                _number(issuer_existing.get("manual_share_value"), 0),
            )
            if manual_share_value < 0:
                raise ValueError("Manual share value cannot be negative")
            valuation_date = _optional_date_string(payload.get("valuation_date")) or str(issuer_existing.get("valuation_date") or "")
            if manual_share_value > 0 and not valuation_date:
                raise ValueError("Valuation date is required when a manual share value is entered")
            issuer_record = {
                "id": issuer_id,
                "company_name": company_name,
                "listing_status": listing_status,
                "public_symbol": public_symbol,
                "public_market": public_market,
                "currency": currency,
                "location": location,
                "listing_date": _optional_date_string(payload.get("listing_date")) or str(issuer_existing.get("listing_date") or ""),
                "restriction_end_date": _optional_date_string(payload.get("restriction_end_date")) or str(issuer_existing.get("restriction_end_date") or ""),
                "manual_share_value": manual_share_value,
                "valuation_date": valuation_date,
                "comments": str(payload.get("issuer_comments") or issuer_existing.get("comments") or "").strip(),
                "created_at": str(issuer_existing.get("created_at") or now),
                "updated_at": now,
            }
            option_type = "CALL"
            symbol = str((existing or {}).get("symbol") or f"ESO-{security_id[:8].upper()}")
            stock_market = "PRIVATE"
            underlying_symbol = public_symbol
            multiplier_default = 1
        else:
            issuer_record = None
            symbol = _clean_security_symbol(payload.get("symbol"))
            secondary_symbol = _clean_security_symbol(payload.get("secondary_symbol"))
            stock_market = str(payload.get("stock_market") or "").upper().strip()
            underlying_symbol = _clean_security_symbol(payload.get("underlying_symbol"))
            multiplier_default = 100 if (is_exchange_option or is_legacy_option_grant) else 1

        if is_employee_option:
            secondary_symbol = ""
        if secondary_symbol and secondary_symbol == symbol:
            raise ValueError("Secondary symbol must be different from the primary symbol")

        if is_exchange_option or is_legacy_option_grant:
            option_type = _choice(option_type, OPTION_TYPES, "CALL")
            if not underlying_symbol:
                raise ValueError("Underlying symbol is required for options")
            if not expiration_date:
                raise ValueError("Expiration date is required for options")
            if _number(payload.get("strike_price"), 0) <= 0:
                raise ValueError("Strike price must be greater than zero for options")
        elif instrument_type == "FUTURE" and not expiration_date:
            raise ValueError("Expiration date is required for futures")
        elif not is_employee_option:
            option_type = ""
        record = {
            "id": security_id,
            "symbol": symbol,
            "secondary_symbol": secondary_symbol,
            "name": str(payload.get("name") or "").strip(),
            "stock_market": stock_market,
            "asset_class": asset_class,
            "instrument_type": instrument_type,
            "option_type": option_type,
            "underlying_symbol": underlying_symbol,
            "expiration_date": expiration_date,
            "strike_price": _number(payload.get("strike_price"), 0),
            "contract_multiplier": _number(payload.get("contract_multiplier"), multiplier_default) or multiplier_default,
            "issuer_id": issuer_id,
            "grant_id": str(payload.get("grant_id") or "").strip(),
            "grant_date": grant_date,
            "vesting_start_date": vesting_start_date,
            "tax_scheme": str(payload.get("tax_scheme") or "").strip(),
            "early_exercise_allowed": int(bool(payload.get("early_exercise_allowed"))),
            "currency": currency,
            "location": location,
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": str(payload.get("created_at") or (existing or {}).get("created_at") or _now()),
        }
        if not record["symbol"]:
            raise ValueError("Symbol is required")
        if not record["stock_market"]:
            raise ValueError("Stock market is required")
        if not record["name"]:
            if is_employee_option:
                grant_label = f" {record['grant_id']}" if record["grant_id"] else ""
                record["name"] = f"{issuer_record['company_name']}{grant_label} employee options"
            else:
                record["name"] = record["symbol"]
        connection_scope = nullcontext(_conn) if _conn is not None else self._connect()
        with connection_scope as conn:
            symbol_conflict = conn.execute(
                """
                select id from manual_securities
                where stock_market = ? and id != ?
                  and (
                    secondary_symbol = ?
                    or (? != '' and (symbol = ? or secondary_symbol = ?))
                  )
                limit 1
                """,
                (record["stock_market"], record["id"], record["symbol"], record["secondary_symbol"], record["secondary_symbol"], record["secondary_symbol"]),
            ).fetchone()
            if symbol_conflict:
                raise ValueError("Another instrument already uses one of these symbols on this stock market")
            if issuer_record:
                conn.execute(
                    """
                    insert into issuers
                      (id, company_name, listing_status, public_symbol, public_market, currency, location,
                       listing_date, restriction_end_date, manual_share_value, valuation_date, comments, created_at, updated_at)
                    values
                      (:id, :company_name, :listing_status, :public_symbol, :public_market, :currency, :location,
                       :listing_date, :restriction_end_date, :manual_share_value, :valuation_date, :comments, :created_at, :updated_at)
                    on conflict(id) do update set
                      company_name = excluded.company_name,
                      listing_status = excluded.listing_status,
                      public_symbol = excluded.public_symbol,
                      public_market = excluded.public_market,
                      currency = excluded.currency,
                      location = excluded.location,
                      listing_date = excluded.listing_date,
                      restriction_end_date = excluded.restriction_end_date,
                      manual_share_value = excluded.manual_share_value,
                      valuation_date = excluded.valuation_date,
                      comments = excluded.comments,
                      updated_at = excluded.updated_at
                    """,
                    issuer_record,
                )
            if existing:
                identity_changed = (
                    str(existing.get("symbol") or "") != record["symbol"]
                    or str(existing.get("stock_market") or "") != record["stock_market"]
                )
                deletion_state = self._manual_security_deletion_state(conn, existing)
                if identity_changed and not deletion_state["can_delete"]:
                    raise ValueError("Symbol and stock market cannot change while the instrument is in use")
                duplicate = conn.execute(
                    """
                    select id from manual_securities
                    where symbol = ? and stock_market = ? and id != ?
                    limit 1
                    """,
                    (record["symbol"], record["stock_market"], record["id"]),
                ).fetchone()
                if duplicate:
                    raise ValueError("Another instrument already uses this symbol and stock market")
                conn.execute(
                    """
                    update manual_securities
                    set symbol = :symbol,
                        secondary_symbol = :secondary_symbol,
                        name = :name,
                        stock_market = :stock_market,
                        asset_class = :asset_class,
                        instrument_type = :instrument_type,
                        option_type = :option_type,
                        underlying_symbol = :underlying_symbol,
                        expiration_date = :expiration_date,
                        strike_price = :strike_price,
                        contract_multiplier = :contract_multiplier,
                        issuer_id = :issuer_id,
                        grant_id = :grant_id,
                        grant_date = :grant_date,
                        vesting_start_date = :vesting_start_date,
                        tax_scheme = :tax_scheme,
                        early_exercise_allowed = :early_exercise_allowed,
                        currency = :currency,
                        location = :location,
                        comments = :comments
                    where id = :id
                    """,
                    record,
                )
            else:
                conn.execute(
                    """
                    insert into manual_securities
                      (id, symbol, secondary_symbol, name, stock_market, asset_class, instrument_type, option_type, underlying_symbol,
                       expiration_date, strike_price, contract_multiplier, issuer_id, grant_id, grant_date,
                       vesting_start_date, tax_scheme, early_exercise_allowed, currency, location, comments, created_at)
                    values
                      (:id, :symbol, :secondary_symbol, :name, :stock_market, :asset_class, :instrument_type, :option_type, :underlying_symbol,
                       :expiration_date, :strike_price, :contract_multiplier, :issuer_id, :grant_id, :grant_date,
                       :vesting_start_date, :tax_scheme, :early_exercise_allowed, :currency, :location, :comments, :created_at)
                    on conflict(symbol, stock_market) do update set
                      secondary_symbol = excluded.secondary_symbol,
                      name = excluded.name,
                      asset_class = excluded.asset_class,
                      instrument_type = excluded.instrument_type,
                      option_type = excluded.option_type,
                      underlying_symbol = excluded.underlying_symbol,
                      expiration_date = excluded.expiration_date,
                      strike_price = excluded.strike_price,
                      contract_multiplier = excluded.contract_multiplier,
                      issuer_id = excluded.issuer_id,
                      grant_id = excluded.grant_id,
                      grant_date = excluded.grant_date,
                      vesting_start_date = excluded.vesting_start_date,
                      tax_scheme = excluded.tax_scheme,
                      early_exercise_allowed = excluded.early_exercise_allowed,
                      currency = excluded.currency,
                      location = excluded.location,
                      comments = excluded.comments
                    """,
                    record,
                )
        if _conn is not None:
            return {
                **record,
                **({
                    "company_name": issuer_record["company_name"],
                    "listing_status": issuer_record["listing_status"],
                    "public_symbol": issuer_record["public_symbol"],
                    "public_market": issuer_record["public_market"],
                    "listing_date": issuer_record["listing_date"],
                    "restriction_end_date": issuer_record["restriction_end_date"],
                    "manual_share_value": issuer_record["manual_share_value"],
                    "valuation_date": issuer_record["valuation_date"],
                } if issuer_record else {}),
            }
        return self.manual_security_by_id(record["id"]) or self.manual_security(record["symbol"], record["stock_market"]) or record

    def delete_manual_security(self, security_id: str) -> bool:
        with self._connect() as conn:
            security = conn.execute("select * from manual_securities where id = ?", (security_id,)).fetchone()
            before = bool(security)
            if security:
                deletion_state = self._manual_security_deletion_state(conn, security)
                if not deletion_state["can_delete"]:
                    attached = ", ".join(
                        f"{name}={count}"
                        for name, count in deletion_state["attachment_counts"].items()
                        if count
                    )
                    raise ValueError(f"Instrument has attached data or lifecycle history and cannot be removed: {attached}")
            conn.execute("delete from manual_securities where id = ?", (security_id,))
        return before

    def list_employee_option_grants(self) -> list[dict[str, Any]]:
        securities = [
            item for item in self.list_manual_securities()
            if item.get("instrument_type") == "EMPLOYEE_STOCK_OPTION"
        ]
        transactions = self.list_transactions()
        with self._connect() as conn:
            transition_rows = conn.execute(
                """
                select source_security_id, target_security_id
                from equity_transitions
                where trim(source_security_id) != '' or trim(target_security_id) != ''
                """
            ).fetchall()
        lifecycle_ids = {
            str(security_id)
            for row in transition_rows
            for security_id in (row["source_security_id"], row["target_security_id"])
            if str(security_id or "").strip()
        }
        grants: list[dict[str, Any]] = []
        for security in securities:
            related = [tx for tx in transactions if tx.get("security_id") == security["id"]]
            setup_transactions = [
                tx for tx in related
                if tx.get("action") == "ADD" and not str(tx.get("transition_id") or "").strip()
            ]
            setup_transaction = min(
                setup_transactions,
                key=lambda tx: (str(tx.get("created_at") or ""), str(tx.get("id") or "")),
                default=None,
            )
            has_lifecycle_history = security["id"] in lifecycle_ids or any(
                str(tx.get("transition_id") or "").strip() for tx in related
            )
            simple_setup = len(related) <= 1 and (not related or setup_transaction is not None)
            grants.append(
                {
                    "security": security,
                    "transaction": setup_transaction,
                    "activity_count": len(related),
                    "has_lifecycle_history": has_lifecycle_history,
                    "can_edit": not has_lifecycle_history and simple_setup,
                    "can_delete": not has_lifecycle_history and simple_setup,
                }
            )
        return grants

    def employee_option_grant(self, security_id: Any) -> dict[str, Any] | None:
        key = str(security_id or "").strip()
        if not key:
            return None
        return next(
            (grant for grant in self.list_employee_option_grants() if grant["security"]["id"] == key),
            None,
        )

    def save_employee_option_grant(self, payload: dict[str, Any]) -> dict[str, Any]:
        grant_payload = dict(payload.get("grant") or {})
        vesting_payload = dict(payload.get("vesting") or {})
        security_id = str(payload.get("security_id") or grant_payload.get("id") or "").strip()
        transaction_id = str(payload.get("transaction_id") or vesting_payload.get("id") or "").strip()
        if security_id:
            grant_payload["id"] = security_id
        grant_payload["instrument_type"] = "EMPLOYEE_STOCK_OPTION"
        account = self._account(vesting_payload.get("account_db_id"))
        if str(account.get("type") or "").upper() != "ESOP":
            raise ValueError("Choose an ESOP account for the employee option grant")

        with self._connect() as conn:
            if security_id:
                existing_security = conn.execute(
                    "select instrument_type from manual_securities where id = ?",
                    (security_id,),
                ).fetchone()
                if not existing_security:
                    raise ValueError("Employee option grant not found")
                if existing_security["instrument_type"] != "EMPLOYEE_STOCK_OPTION":
                    raise ValueError("The selected instrument is not an employee option grant")
                lifecycle_count = conn.execute(
                    """
                    select count(*) from equity_transitions
                    where source_security_id = ? or target_security_id = ?
                    """,
                    (security_id, security_id),
                ).fetchone()[0]
                if lifecycle_count:
                    raise ValueError("A grant with exercise or listing history cannot be edited")

            existing_transaction = None
            if transaction_id:
                existing_transaction = conn.execute(
                    "select * from transactions where id = ?",
                    (transaction_id,),
                ).fetchone()
                if not existing_transaction:
                    raise ValueError("Employee option vesting record not found")
                if str(existing_transaction["transition_id"] or "").strip():
                    raise ValueError("Lifecycle-generated transactions are read-only")
                if security_id and existing_transaction["security_id"] != security_id:
                    raise ValueError("The vesting record does not belong to this employee option grant")

            security = self.save_manual_security(grant_payload, _conn=conn)
            merged_vesting = {
                **(_dict(existing_transaction) if existing_transaction else {}),
                **vesting_payload,
                "id": transaction_id or str(uuid4()),
                "account_db_id": account["id"],
                "action": "ADD",
                "security_id": security["id"],
                "symbol": security["symbol"],
                "stock_market": security["stock_market"],
                "asset_class": "EMPLOYEE_STOCK_OPTION",
                "price_input": 0,
                "strike_price": security["strike_price"],
                "trade_date": vesting_payload.get("trade_date") or security["grant_date"],
                "created_at": str(
                    (existing_transaction["created_at"] if existing_transaction else "") or _now()
                ),
            }
            transaction = self._transaction_record(
                merged_vesting,
                account=account,
                metadata=security,
            )
            position_quantity = self._validate_position_ledger(
                conn,
                transaction,
                exclude_id=transaction_id,
            )
            if existing_transaction:
                self._update_transaction_record(conn, transaction)
            else:
                self._insert_transaction(conn, transaction)

        saved = self.employee_option_grant(security["id"])
        if not saved:
            raise ValueError("Employee option grant could not be loaded after saving")
        saved["position_quantity"] = position_quantity
        return saved

    def delete_employee_option_grant(self, security_id: str) -> bool:
        key = str(security_id or "").strip()
        with self._connect() as conn:
            security = conn.execute(
                "select instrument_type from manual_securities where id = ?",
                (key,),
            ).fetchone()
            if not security:
                return False
            if security["instrument_type"] != "EMPLOYEE_STOCK_OPTION":
                raise ValueError("The selected instrument is not an employee option grant")
            lifecycle_count = conn.execute(
                """
                select count(*) from equity_transitions
                where source_security_id = ? or target_security_id = ?
                """,
                (key, key),
            ).fetchone()[0]
            transactions = conn.execute(
                "select id, action, transition_id from transactions where security_id = ?",
                (key,),
            ).fetchall()
            simple_setup = len(transactions) <= 1 and all(
                tx["action"] == "ADD" and not str(tx["transition_id"] or "").strip()
                for tx in transactions
            )
            if lifecycle_count or not simple_setup:
                raise ValueError(
                    "This grant has exercise or additional activity. Remove that activity before deleting the grant"
                )
            conn.execute("delete from transactions where security_id = ?", (key,))
            conn.execute("delete from manual_securities where id = ?", (key,))
        return True

    def manual_security(self, symbol: Any, stock_market: Any) -> dict[str, Any] | None:
        symbol_key = _clean_security_symbol(symbol)
        market_key = str(stock_market or "").upper().strip()
        if not symbol_key or not market_key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                select s.*, i.company_name, i.listing_status, i.public_symbol, i.public_market,
                       i.listing_date, i.restriction_end_date, i.manual_share_value, i.valuation_date
                from manual_securities s
                left join issuers i on i.id = s.issuer_id
                where (s.symbol = ? or s.secondary_symbol = ?) and s.stock_market = ?
                order by case when s.symbol = ? then 0 else 1 end
                limit 1
                """,
                (symbol_key, symbol_key, market_key, symbol_key),
            ).fetchone()
        return _dict(row) if row else None

    def manual_security_by_id(self, security_id: Any) -> dict[str, Any] | None:
        key = str(security_id or "").strip()
        if not key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                select s.*, i.company_name, i.listing_status, i.public_symbol, i.public_market,
                       i.listing_date, i.restriction_end_date, i.manual_share_value, i.valuation_date
                from manual_securities s
                left join issuers i on i.id = s.issuer_id
                where s.id = ?
                """,
                (key,),
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
                       s.secondary_symbol,
                       s.instrument_type,
                       s.option_type,
                       s.underlying_symbol,
                       s.expiration_date,
                       s.strike_price as instrument_strike_price,
                       s.contract_multiplier,
                       s.issuer_id,
                       s.grant_id,
                       s.grant_date,
                       s.vesting_start_date,
                       s.tax_scheme,
                       s.early_exercise_allowed,
                       i.company_name,
                       i.listing_status,
                       i.public_symbol,
                       i.public_market,
                       i.listing_date,
                       i.restriction_end_date,
                       i.manual_share_value,
                       i.valuation_date
                from transactions t
                join accounts a on a.id = t.account_db_id
                left join manual_securities s
                  on s.id = t.security_id
                  or (trim(t.security_id) = '' and s.symbol = t.symbol and s.stock_market = t.stock_market)
                left join issuers i on i.id = s.issuer_id
                order by t.trade_date desc, t.created_at desc
                """
            ).fetchall()
        items = []
        for row in rows:
            item = _dict(row)
            if not item.get("strike_price") and item.get("instrument_strike_price"):
                item["strike_price"] = item["instrument_strike_price"]
            item.pop("instrument_strike_price", None)
            item["vesting_schedule"] = _json_object(item.get("vesting_schedule"))
            items.append(item)
        return items

    def add_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = self._transaction_record(payload)
        with self._connect() as conn:
            position_quantity = self._validate_position_ledger(conn, record)
            self._insert_transaction(conn, record)
        return self._transaction_with_position_status(record, position_quantity)

    def _transaction_record(
        self,
        payload: dict[str, Any],
        *,
        account: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        account = account or self._account(payload.get("account_db_id"))
        action = _choice(payload.get("action"), TRANSACTION_ACTIONS, "BUY")
        symbol = _clean_security_symbol(payload.get("symbol"))
        stock_market = str(payload.get("stock_market") or "").upper().strip()
        security_id = str(payload.get("security_id") or "").strip()
        if metadata is None:
            metadata = self.manual_security_by_id(security_id) if security_id else self.manual_security(symbol, stock_market)
        if security_id and not metadata:
            raise ValueError("Defined instrument not found")
        if metadata:
            security_id = str(metadata.get("id") or security_id)
            symbol = str(metadata.get("symbol") or symbol)
            stock_market = str(metadata.get("stock_market") or stock_market)
        asset_class = str(payload.get("asset_class") or (metadata or {}).get("asset_class") or "EQUITY").upper().strip()
        quantity = abs(_number(payload.get("quantity"), 0))
        price_input = _number(payload.get("price_input"), 0)
        purchase_price = _number(payload.get("purchase_price"), 0)
        strike_price = _number(payload.get("strike_price"), _number((metadata or {}).get("strike_price"), 0))
        location = str(payload.get("location") or (metadata or {}).get("location") or account["location"] or "USA").strip()
        currency = str(payload.get("currency") or (metadata or {}).get("currency") or account["currency"] or _currency_for_location(location)).upper().strip()
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero")
        if price_input < 0:
            raise ValueError("Price cannot be negative")
        if purchase_price < 0:
            raise ValueError("Purchase price cannot be negative")
        if strike_price < 0:
            raise ValueError("Strike price cannot be negative")
        instrument_type = str((metadata or {}).get("instrument_type") or asset_class).upper().strip()
        if instrument_type == "EMPLOYEE_STOCK_OPTION" and not metadata:
            raise ValueError("Define the employee stock option grant before adding its transaction")
        if instrument_type == "EMPLOYEE_STOCK_OPTION" and action not in {"ADD", "REMOVE"}:
            raise ValueError("Employee stock option transactions must use Add or Remove; use Exercise for share conversion")
        if instrument_type in {"OPTION", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION"} and strike_price <= 0:
            raise ValueError("Strike price is required for options")
        trade_date = _date_string(payload.get("trade_date") or (metadata or {}).get("grant_date"))
        vest_date = _optional_date_string(payload.get("vest_date"))
        raw_schedule = _json_object(payload.get("vesting_schedule"))
        schedule: dict[str, Any] = {}
        if raw_schedule.get("enabled"):
            if instrument_type != "EMPLOYEE_STOCK_OPTION":
                raise ValueError("Vesting schedules are available for employee stock options")
            if action != "ADD":
                raise ValueError("A vesting schedule can only be saved when adding an employee option grant")
            schedule = _build_vesting_schedule(
                raw_schedule,
                quantity,
                (metadata or {}).get("vesting_start_date") or (metadata or {}).get("grant_date") or trade_date,
            )
            vest_date = ""
            expiration = _parse_date((metadata or {}).get("expiration_date"))
            final_vest = _parse_date(schedule["tranches"][-1]["vest_date"])
            if expiration and final_vest and final_vest > expiration:
                raise ValueError("The vesting schedule cannot continue after the option expiration date")
        elif instrument_type == "EMPLOYEE_STOCK_OPTION" and action == "ADD" and not vest_date:
            raise ValueError("Choose a vest date or configure a vesting schedule")
        record = {
            "id": str(payload.get("id") or uuid4()),
            "account_db_id": account["id"],
            "action": action,
            "symbol": symbol,
            "stock_market": stock_market,
            "asset_class": asset_class,
            "quantity": quantity,
            "price_input": price_input,
            "price": price_input if action in {"DIVIDEND", "INTEREST", "FEE"} else normalize_price(price_input, location, asset_class),
            "vest_date": vest_date,
            "purchase_price": purchase_price,
            "strike_price": strike_price,
            "security_id": security_id,
            "transition_id": str(payload.get("transition_id") or "").strip(),
            "vesting_schedule": json.dumps(schedule, separators=(",", ":")),
            "currency": currency,
            "location": location,
            "trade_date": trade_date,
            "source": str(payload.get("source") or "manual").strip(),
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": str(payload.get("created_at") or _now()),
        }
        if not record["symbol"]:
            raise ValueError("Symbol is required")
        if not record["stock_market"]:
            raise ValueError("Stock market is required")
        return record

    def _insert_transaction(self, conn: sqlite3.Connection, record: dict[str, Any]) -> None:
        conn.execute(
            """
            insert into transactions
              (id, account_db_id, action, symbol, stock_market, asset_class, quantity, price_input, price,
               vest_date, purchase_price, strike_price, security_id, transition_id, vesting_schedule,
               currency, location, trade_date, source, comments, created_at)
            values
              (:id, :account_db_id, :action, :symbol, :stock_market, :asset_class, :quantity, :price_input, :price,
               :vest_date, :purchase_price, :strike_price, :security_id, :transition_id, :vesting_schedule,
               :currency, :location, :trade_date, :source, :comments, :created_at)
            """,
            record,
        )

    def _update_transaction_record(self, conn: sqlite3.Connection, record: dict[str, Any]) -> None:
        conn.execute(
            """
            update transactions
            set account_db_id = :account_db_id,
                action = :action,
                symbol = :symbol,
                stock_market = :stock_market,
                asset_class = :asset_class,
                quantity = :quantity,
                price_input = :price_input,
                price = :price,
                vest_date = :vest_date,
                purchase_price = :purchase_price,
                strike_price = :strike_price,
                security_id = :security_id,
                transition_id = :transition_id,
                vesting_schedule = :vesting_schedule,
                currency = :currency,
                location = :location,
                trade_date = :trade_date,
                source = :source,
                comments = :comments
            where id = :id
            """,
            record,
        )

    def _position_transactions(
        self,
        conn: sqlite3.Connection,
        account_db_id: str,
        symbol: str,
        stock_market: str,
        exclude_id: str = "",
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            select * from transactions
            where account_db_id = ? and symbol = ? and stock_market = ? and id != ?
            order by trade_date, created_at, id
            """,
            (account_db_id, symbol, stock_market, exclude_id),
        ).fetchall()
        return [_dict(row) for row in rows]

    def _validate_position_ledger(
        self,
        conn: sqlite3.Connection,
        record: dict[str, Any] | None = None,
        *,
        account_db_id: str = "",
        symbol: str = "",
        stock_market: str = "",
        exclude_id: str = "",
    ) -> float:
        if record:
            account_db_id = record["account_db_id"]
            symbol = record["symbol"]
            stock_market = record["stock_market"]
        transactions = self._position_transactions(conn, account_db_id, symbol, stock_market, exclude_id)
        if record:
            transactions.append(record)
        transactions.sort(key=lambda tx: (str(tx.get("trade_date") or ""), str(tx.get("created_at") or ""), str(tx.get("id") or "")))

        position_quantity = 0.0
        epsilon = 1e-9
        for tx in transactions:
            action = str(tx.get("action") or "").upper()
            quantity = abs(_number(tx.get("quantity"), 0))
            if action == "BUY":
                if position_quantity < -epsilon and quantity > abs(position_quantity) + epsilon:
                    raise ValueError(f"You can buy at most {abs(position_quantity):g} units to close this short")
                position_quantity += quantity
            elif action == "SELL":
                if position_quantity <= epsilon:
                    raise ValueError("Sell is only available for a long position")
                if quantity > position_quantity + epsilon:
                    raise ValueError(f"You can sell at most {position_quantity:g} units")
                position_quantity -= quantity
            elif action == "SHORT":
                if position_quantity > epsilon:
                    raise ValueError("Close the long position with Sell before adding a short")
                position_quantity -= quantity
            elif action == "ADD":
                position_quantity += quantity
            elif action == "REMOVE":
                if position_quantity > epsilon:
                    position_quantity -= min(quantity, position_quantity)
                elif position_quantity < -epsilon:
                    position_quantity += min(quantity, abs(position_quantity))
            if abs(position_quantity) <= epsilon:
                position_quantity = 0.0
        return position_quantity

    @staticmethod
    def _transaction_with_position_status(record: dict[str, Any], position_quantity: float) -> dict[str, Any]:
        quantity = 0.0 if abs(position_quantity) <= 1e-9 else position_quantity
        return {
            **record,
            "vesting_schedule": _json_object(record.get("vesting_schedule")),
            "position_quantity": quantity,
            "position_closed": quantity == 0,
            "position_side": "closed" if quantity == 0 else "long" if quantity > 0 else "short",
        }

    def update_transaction(self, transaction_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            existing = conn.execute("select * from transactions where id = ?", (transaction_id,)).fetchone()
        if not existing:
            raise ValueError("Security transaction not found")
        if str(existing["transition_id"] or "").strip():
            raise ValueError("Lifecycle-generated transactions are read-only")
        merged = {**_dict(existing), **(payload or {}), "id": transaction_id, "created_at": existing["created_at"]}
        record = self._transaction_record(merged)
        with self._connect() as conn:
            old_key = (existing["account_db_id"], existing["symbol"], existing["stock_market"])
            new_key = (record["account_db_id"], record["symbol"], record["stock_market"])
            position_quantity = self._validate_position_ledger(conn, record, exclude_id=transaction_id)
            if old_key != new_key:
                self._validate_position_ledger(
                    conn,
                    account_db_id=old_key[0],
                    symbol=old_key[1],
                    stock_market=old_key[2],
                    exclude_id=transaction_id,
                )
            self._update_transaction_record(conn, record)
        return self._transaction_with_position_status(record, position_quantity)

    def delete_transaction(self, transaction_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("select transition_id from transactions where id = ?", (transaction_id,)).fetchone()
            if row and str(row["transition_id"] or "").strip():
                raise ValueError("Lifecycle-generated transactions are read-only")
            before = int(bool(row))
            conn.execute("delete from transactions where id = ?", (transaction_id,))
        return bool(before)

    def list_equity_transitions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select e.*, source.name as source_name, target.name as target_name
                from equity_transitions e
                left join manual_securities source on source.id = e.source_security_id
                left join manual_securities target on target.id = e.target_security_id
                order by e.effective_date desc, e.created_at desc
                """
            ).fetchall()
        items = []
        for row in rows:
            item = _dict(row)
            item["details"] = _json_object(item.get("details"))
            items.append(item)
        return items

    def link_employee_option_listing(self, security_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        security = self.manual_security_by_id(security_id)
        if not security or security.get("instrument_type") != "EMPLOYEE_STOCK_OPTION":
            raise ValueError("Employee stock option grant not found")
        issuer_id = str(security.get("issuer_id") or "")
        if not issuer_id:
            raise ValueError("Employee stock option issuer is missing")
        public_symbol = _clean_security_symbol(payload.get("public_symbol"))
        public_market = str(payload.get("public_market") or "").upper().strip()
        if not public_symbol or not public_market:
            raise ValueError("Public symbol and stock market are required")
        listing_date = _optional_date_string(payload.get("listing_date"))
        if not listing_date:
            raise ValueError("Listing date is required")
        restriction_end_date = _optional_date_string(payload.get("restriction_end_date"))
        now = _now()
        transition_id = str(uuid4())
        with self._connect() as conn:
            issuer = conn.execute("select * from issuers where id = ?", (issuer_id,)).fetchone()
            if not issuer:
                raise ValueError("Employee stock option issuer not found")
            unchanged = (
                issuer["listing_status"] == "PUBLIC"
                and issuer["public_symbol"] == public_symbol
                and issuer["public_market"] == public_market
                and issuer["listing_date"] == listing_date
                and issuer["restriction_end_date"] == restriction_end_date
            )
            if not unchanged:
                conn.execute(
                    """
                    update issuers
                    set listing_status = 'PUBLIC', public_symbol = ?, public_market = ?, listing_date = ?,
                        restriction_end_date = ?, updated_at = ?
                    where id = ?
                    """,
                    (public_symbol, public_market, listing_date, restriction_end_date, now, issuer_id),
                )
                conn.execute(
                    "update manual_securities set underlying_symbol = ? where issuer_id = ? and instrument_type = 'EMPLOYEE_STOCK_OPTION'",
                    (public_symbol, issuer_id),
                )
                conn.execute(
                    """
                    insert into equity_transitions
                      (id, transition_type, source_security_id, target_security_id, account_db_id,
                       quantity, conversion_ratio, effective_date, details, created_at)
                    values (?, 'LISTING_LINK', ?, '', '', 0, 1, ?, ?, ?)
                    """,
                    (
                        transition_id,
                        security_id,
                        listing_date,
                        json.dumps({"public_symbol": public_symbol, "public_market": public_market, "restriction_end_date": restriction_end_date}, separators=(",", ":")),
                        now,
                    ),
                )
        return {
            "security": self.manual_security_by_id(security_id),
            "transition_id": "" if unchanged else transition_id,
            "unchanged": unchanged,
        }

    def _employee_option_available(
        self,
        conn: sqlite3.Connection,
        security: dict[str, Any],
        account_db_id: str,
        as_of: date,
    ) -> tuple[float, float]:
        rows = conn.execute(
            """
            select * from transactions
            where account_db_id = ?
              and (security_id = ? or (trim(security_id) = '' and symbol = ? and stock_market = ?))
            order by trade_date, created_at, id
            """,
            (account_db_id, security["id"], security["symbol"], security["stock_market"]),
        ).fetchall()
        lots: list[dict[str, Any]] = []
        for raw in rows:
            tx = _dict(raw)
            action = str(tx.get("action") or "").upper()
            quantity = abs(_number(tx.get("quantity"), 0))
            if action in {"ADD", "BUY"}:
                schedule = _json_object(tx.get("vesting_schedule"))
                tranches = schedule.get("tranches") if isinstance(schedule.get("tranches"), list) else []
                if tranches:
                    for tranche in tranches:
                        tranche_quantity = _number((tranche or {}).get("quantity"), 0)
                        if tranche_quantity > 0:
                            lots.append({"quantity": tranche_quantity, "vest_date": _parse_date((tranche or {}).get("vest_date"))})
                else:
                    lots.append({"quantity": quantity, "vest_date": _parse_date(tx.get("vest_date"))})
                continue
            if action not in {"REMOVE", "SELL"}:
                continue
            remaining = quantity
            for lot in lots:
                if remaining <= 1e-9:
                    break
                used = min(float(lot["quantity"]), remaining)
                lot["quantity"] -= used
                remaining -= used
        current = sum(max(float(lot["quantity"]), 0) for lot in lots)
        if bool(security.get("early_exercise_allowed")):
            return current, current
        vested = sum(
            max(float(lot["quantity"]), 0)
            for lot in lots
            if lot.get("vest_date") and lot["vest_date"] <= as_of
        )
        return current, vested

    def exercise_employee_option(self, security_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        security = self.manual_security_by_id(security_id)
        if not security or security.get("instrument_type") != "EMPLOYEE_STOCK_OPTION":
            raise ValueError("Employee stock option grant not found")
        account = self._account(payload.get("account_db_id"))
        quantity = _number(payload.get("quantity"), 0)
        ratio = _number(payload.get("share_ratio"), 1) or 1
        effective_date = _parse_date(payload.get("exercise_date"))
        if quantity <= 0:
            raise ValueError("Exercise quantity must be greater than zero")
        if ratio <= 0:
            raise ValueError("Share ratio must be greater than zero")
        if not effective_date:
            raise ValueError("Exercise date is required")
        expiration = _parse_date(security.get("expiration_date"))
        if expiration and effective_date > expiration:
            raise ValueError("Employee stock options cannot be exercised after expiration")
        issuer_id = str(security.get("issuer_id") or "")
        if not issuer_id:
            raise ValueError("Employee stock option issuer is missing")
        listing_status = str(security.get("listing_status") or "PRIVATE")
        if listing_status == "PUBLIC":
            symbol = _clean_security_symbol(security.get("public_symbol"))
            market = str(security.get("public_market") or "").upper().strip()
            if not symbol or not market:
                raise ValueError("Public issuer symbol and stock market are required before exercise")
            target_type = "STOCK"
        else:
            symbol = f"PVT-{issuer_id[:8].upper()}"
            market = "PRIVATE"
            target_type = "PRIVATE_STOCK"
        share_quantity = quantity * ratio
        share_cost_basis = _number(payload.get("share_cost_basis"), _number(security.get("strike_price"), 0) / ratio)
        if share_cost_basis < 0:
            raise ValueError("Share cost basis cannot be negative")
        transition_id = str(uuid4())
        source_record = self._transaction_record(
            {
                "account_db_id": account["id"],
                "action": "REMOVE",
                "security_id": security_id,
                "quantity": quantity,
                "price_input": 0,
                "strike_price": security.get("strike_price"),
                "trade_date": effective_date.isoformat(),
                "transition_id": transition_id,
                "source": "employee_option_exercise",
                "comments": str(payload.get("comments") or "Employee stock option exercise").strip(),
            }
        )
        # Reject invalid exercises before creating their destination share instrument.
        # Availability is checked again in the transaction below to keep the paired
        # ledger entries protected if another local write occurs in between.
        with self._connect() as conn:
            current, vested = self._employee_option_available(conn, security, account["id"], effective_date)
            if quantity > current + 1e-9:
                raise ValueError(f"You can exercise at most {current:g} remaining options")
            if quantity > vested + 1e-9:
                raise ValueError(f"You can exercise at most {vested:g} vested options on this date")
            self._validate_position_ledger(conn, source_record)
        target_security = self.save_manual_security(
            {
                "symbol": symbol,
                "name": f"{security.get('company_name') or security.get('name') or symbol} shares",
                "stock_market": market,
                "instrument_type": target_type,
                "issuer_id": issuer_id,
                "currency": security.get("currency"),
                "location": security.get("location"),
                "comments": "Shares acquired by exercising employee stock options",
            }
        )
        target_record = self._transaction_record(
            {
                "account_db_id": account["id"],
                "action": "ADD",
                "security_id": target_security["id"],
                "quantity": share_quantity,
                "price_input": share_cost_basis,
                "trade_date": effective_date.isoformat(),
                "transition_id": transition_id,
                "source": "employee_option_exercise",
                "comments": str(payload.get("comments") or "Shares acquired from employee stock options").strip(),
            }
        )
        now = _now()
        with self._connect() as conn:
            current, vested = self._employee_option_available(conn, security, account["id"], effective_date)
            if quantity > current + 1e-9:
                raise ValueError(f"You can exercise at most {current:g} remaining options")
            if quantity > vested + 1e-9:
                raise ValueError(f"You can exercise at most {vested:g} vested options on this date")
            source_position = self._validate_position_ledger(conn, source_record)
            self._validate_position_ledger(conn, target_record)
            self._insert_transaction(conn, source_record)
            self._insert_transaction(conn, target_record)
            conn.execute(
                """
                insert into equity_transitions
                  (id, transition_type, source_security_id, target_security_id, account_db_id,
                   quantity, conversion_ratio, effective_date, details, created_at)
                values (?, 'EXERCISE', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transition_id,
                    security_id,
                    target_security["id"],
                    account["id"],
                    quantity,
                    ratio,
                    effective_date.isoformat(),
                    json.dumps({"share_quantity": share_quantity, "share_cost_basis": share_cost_basis}, separators=(",", ":")),
                    now,
                ),
            )
        return {
            "transition_id": transition_id,
            "source_security": self.manual_security_by_id(security_id),
            "target_security": self.manual_security_by_id(target_security["id"]),
            "option_quantity_exercised": quantity,
            "share_quantity_acquired": share_quantity,
            "remaining_option_quantity": source_position,
            "effective_date": effective_date.isoformat(),
        }

    def list_events(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select e.*, a.username, a.account_id, a.management_company
                from events e
                left join accounts a on a.id = e.account_db_id
                order by e.event_date desc, e.created_at desc
                """
            ).fetchall()
        return [self._event_out(row) for row in rows]

    def record_dividend_event(self, payload: dict[str, Any], due: bool) -> dict[str, Any]:
        source_key = str(payload.get("source_key") or "").strip()
        if not source_key:
            raise ValueError("Dividend event source key is required")
        now = _now()
        event_id = str(payload.get("id") or uuid4())
        details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
        event = {
            "id": event_id,
            "type": "DIVIDEND",
            "event_date": _date_string(payload.get("event_date")),
            "symbol": _clean_security_symbol(payload.get("symbol")),
            "stock_market": str(payload.get("stock_market") or "").upper().strip(),
            "account_db_id": str(payload.get("account_db_id") or "").strip(),
            "gross_amount": _number(payload.get("gross_amount"), 0),
            "tax_amount": _number(payload.get("tax_amount"), 0),
            "net_amount": _number(payload.get("net_amount"), 0),
            "currency": str(payload.get("currency") or "").upper().strip(),
            "source": str(payload.get("source") or "dividend_scan").strip(),
            "source_key": source_key,
            "status": "processed" if due else "pending",
            "transaction_id": "",
            "details": json.dumps(details, default=str, separators=(",", ":")),
            "created_at": now,
            "updated_at": now,
        }
        if not event["account_db_id"]:
            raise ValueError("Dividend event account is required")
        if not event["symbol"]:
            raise ValueError("Dividend event symbol is required")
        if event["gross_amount"] <= 0:
            raise ValueError("Dividend gross amount must be greater than zero")

        transaction = None
        if due and event["net_amount"] > 0:
            shares = max(_number(details.get("shares"), 0), 1)
            transaction = self._transaction_record(
                {
                    "account_db_id": event["account_db_id"],
                    "action": "DIVIDEND",
                    "symbol": event["symbol"],
                    "stock_market": event["stock_market"],
                    "asset_class": str(details.get("asset_class") or "EQUITY"),
                    "quantity": shares,
                    "price_input": event["net_amount"] / shares,
                    "currency": event["currency"],
                    "location": str(details.get("location") or "USA"),
                    "trade_date": event["event_date"],
                    "source": event["source"],
                    "comments": f"Dividend event {source_key}",
                }
            )
            event["transaction_id"] = transaction["id"]

        with self._sync_lock:
            with self._connect() as conn:
                existing = conn.execute("select * from events where source_key = ?", (source_key,)).fetchone()
                if existing and existing["status"] == "processed":
                    return {**self._event_out(existing), "created": False, "skipped": True}
                if transaction:
                    self._insert_transaction(conn, transaction)
                if existing:
                    event["id"] = existing["id"]
                    event["created_at"] = existing["created_at"]
                conn.execute(
                    """
                    insert into events
                      (id, type, event_date, symbol, stock_market, account_db_id, gross_amount, tax_amount, net_amount, currency, source, source_key, status, transaction_id, details, created_at, updated_at)
                    values
                      (:id, :type, :event_date, :symbol, :stock_market, :account_db_id, :gross_amount, :tax_amount, :net_amount, :currency, :source, :source_key, :status, :transaction_id, :details, :created_at, :updated_at)
                    on conflict(source_key) do update set
                      event_date = excluded.event_date,
                      symbol = excluded.symbol,
                      stock_market = excluded.stock_market,
                      account_db_id = excluded.account_db_id,
                      gross_amount = excluded.gross_amount,
                      tax_amount = excluded.tax_amount,
                      net_amount = excluded.net_amount,
                      currency = excluded.currency,
                      source = excluded.source,
                      status = excluded.status,
                      transaction_id = excluded.transaction_id,
                      details = excluded.details,
                      updated_at = excluded.updated_at
                    """,
                    event,
                )
                row = conn.execute("select * from events where source_key = ?", (source_key,)).fetchone()
        return {**self._event_out(row or event), "created": not bool(existing), "skipped": False}

    def list_prices(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select * from price_history order by price_date desc, symbol").fetchall()
        return [_dict(row) for row in rows]

    def price_history(self, symbol: Any, stock_market: Any, from_date: date | None = None, to_date: date | None = None) -> list[dict[str, Any]]:
        symbol_key = _clean_security_symbol(symbol)
        market_key = str(stock_market or "").upper().strip()
        metadata = self.manual_security(symbol_key, market_key)
        primary_symbol = _clean_security_symbol((metadata or {}).get("symbol") or symbol_key)
        secondary_symbol = _clean_security_symbol((metadata or {}).get("secondary_symbol"))
        aliases = [item for item in [secondary_symbol, primary_symbol] if item]
        aliases = list(dict.fromkeys(aliases))
        if not aliases or not market_key:
            return []
        placeholders = ", ".join("?" for _item in aliases)
        args: list[Any] = [*aliases, market_key]
        where = f"where symbol in ({placeholders}) and stock_market = ?"
        if from_date:
            where += " and price_date >= ?"
            args.append(from_date.isoformat())
        if to_date:
            where += " and price_date <= ?"
            args.append(to_date.isoformat())
        with self._connect() as conn:
            rows = conn.execute(
                f"select * from price_history {where} order by price_date, case when symbol = ? then 1 else 0 end",
                [*args, primary_symbol],
            ).fetchall()
        by_date = {str(row["price_date"]): _dict(row) for row in rows}
        return [by_date[day] for day in sorted(by_date)]

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
        scoped_account_filter = any(
            str(filters.get(key) or "").strip()
            for key in ("account_type", "location", "person_id", "person_name")
        )
        from_date = _parse_date(filters.get("from") or filters.get("date_from"))
        to_date = _parse_date(filters.get("to") or filters.get("date_to"))
        if account_id:
            where.append("s.account_db_id = ?")
            args.append(account_id)
        elif scoped_account_filter:
            account_ids = [item["id"] for item in self._filtered_accounts(filters)]
            if account_ids:
                placeholders = ", ".join("?" for _ in account_ids)
                where.append(f"s.account_db_id in ({placeholders})")
                args.extend(account_ids)
            else:
                where.append("0 = 1")
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
        account_id = str(payload.get("account_id") or "").strip()
        if not account_id:
            raise ValueError("Long-term account is required")
        with self._connect() as conn:
            account = conn.execute("select * from accounts where id = ?", (account_id,)).fetchone()
        if not account:
            raise ValueError("Long-term account not found")
        if account["type"] != "Long-Term Savings":
            raise ValueError("Fund can only be linked to a Long-Term Savings account")
        account_persons = _validated_account_persons(account["type"], account["persons"])
        record = {
            "id": str(payload.get("id") or uuid4()),
            "kind": _choice(payload.get("kind"), FUND_KINDS, "Pension"),
            "fund_name": str(payload.get("fund_name") or payload.get("name") or "").strip(),
            "pension_id": str(payload.get("pension_id") or "").strip(),
            "amount": _number(payload.get("amount"), 0),
            "factor": _number(payload.get("factor"), 200) or 200,
            "account_id": account_id,
            "birth_date": account_persons[0]["birth_date"],
            "persons": json.dumps(account_persons),
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": str(payload.get("created_at") or _now()),
        }
        if not record["pension_id"]:
            raise ValueError("Fund ID is required")
        if record["amount"] <= 0:
            raise ValueError("Saved amount is required")
        with self._sync_lock:
            with self._connect() as conn:
                existing = conn.execute("select * from funds where id = ?", (record["id"],)).fetchone()
                conn.execute(
                    """
                    insert into funds
                      (id, kind, fund_name, pension_id, amount, factor, account_id, birth_date, persons, comments, created_at)
                    values
                      (:id, :kind, :fund_name, :pension_id, :amount, :factor, :account_id, :birth_date, :persons, :comments, :created_at)
                    on conflict(id) do update set
                      kind = excluded.kind,
                      fund_name = excluded.fund_name,
                      pension_id = excluded.pension_id,
                      amount = excluded.amount,
                      factor = excluded.factor,
                      account_id = excluded.account_id,
                      birth_date = excluded.birth_date,
                      persons = excluded.persons,
                      comments = excluded.comments
                    """,
                    record,
                )
                amount_changed = not existing or float(existing["amount"] or 0) != float(record["amount"])
                if amount_changed:
                    amount_date = _date_string(payload.get("amount_date") or payload.get("date"))
                    now = _now()
                    conn.execute(
                        """
                        insert into fund_amount_history
                          (id, fund_id, amount_date, amount, source, comments, created_at, updated_at)
                        values (?, ?, ?, ?, 'fund_update', 'Saved amount update', ?, ?)
                        on conflict(fund_id, amount_date) do update set
                          amount = excluded.amount,
                          source = excluded.source,
                          comments = excluded.comments,
                          updated_at = excluded.updated_at
                        """,
                        (str(uuid4()), record["id"], amount_date, record["amount"], now, now),
                    )
                row = conn.execute("select * from funds where id = ?", (record["id"],)).fetchone()
        return self._fund_out(row or record)

    def list_fund_amount_history(self, fund_id: str) -> list[dict[str, Any]]:
        clean_fund_id = str(fund_id or "").strip()
        with self._connect() as conn:
            fund = conn.execute("select id from funds where id = ?", (clean_fund_id,)).fetchone()
            if not fund:
                raise ValueError("Fund record not found")
            rows = conn.execute(
                "select * from fund_amount_history where fund_id = ? order by amount_date, created_at",
                (clean_fund_id,),
            ).fetchall()
        return [_dict(row) for row in rows]

    def save_fund_amount_history(self, fund_id: str, payload: dict[str, Any], history_id: str = "") -> dict[str, Any]:
        clean_fund_id = str(fund_id or "").strip()
        amount = _optional_number(payload.get("amount"))
        if amount is None or amount <= 0:
            raise ValueError("Saved amount must be greater than zero")
        amount_date = _optional_date_string(payload.get("amount_date") or payload.get("date"))
        if not amount_date:
            raise ValueError("History date is required")
        if date.fromisoformat(amount_date) > date.today():
            raise ValueError("History date cannot be in the future")
        now = _now()
        record = {
            "id": str(history_id or payload.get("id") or uuid4()),
            "fund_id": clean_fund_id,
            "amount_date": amount_date,
            "amount": amount,
            "source": str(payload.get("source") or "manual").strip(),
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": str(payload.get("created_at") or now),
            "updated_at": now,
        }
        try:
            with self._sync_lock:
                with self._connect() as conn:
                    fund = conn.execute("select id from funds where id = ?", (clean_fund_id,)).fetchone()
                    if not fund:
                        raise ValueError("Fund record not found")
                    existing = conn.execute("select * from fund_amount_history where id = ?", (record["id"],)).fetchone()
                    if history_id and not existing:
                        raise ValueError("Fund history point not found")
                    if existing and existing["fund_id"] != clean_fund_id:
                        raise ValueError("Fund history point does not belong to this fund")
                    if existing:
                        record["created_at"] = existing["created_at"]
                        conn.execute(
                            """
                            update fund_amount_history
                            set amount_date = :amount_date,
                                amount = :amount,
                                source = :source,
                                comments = :comments,
                                updated_at = :updated_at
                            where id = :id and fund_id = :fund_id
                            """,
                            record,
                        )
                    else:
                        conn.execute(
                            """
                            insert into fund_amount_history
                              (id, fund_id, amount_date, amount, source, comments, created_at, updated_at)
                            values
                              (:id, :fund_id, :amount_date, :amount, :source, :comments, :created_at, :updated_at)
                            """,
                            record,
                        )
                    self._sync_fund_amount_from_history(conn, clean_fund_id)
                    row = conn.execute("select * from fund_amount_history where id = ?", (record["id"],)).fetchone()
        except sqlite3.IntegrityError as exc:
            if "unique" in str(exc).lower():
                raise ValueError("A saved amount already exists for this date") from exc
            raise
        return _dict(row or record)

    def delete_fund_amount_history(self, fund_id: str, history_id: str) -> bool:
        clean_fund_id = str(fund_id or "").strip()
        clean_history_id = str(history_id or "").strip()
        with self._sync_lock:
            with self._connect() as conn:
                before = conn.execute(
                    "select count(*) from fund_amount_history where id = ? and fund_id = ?",
                    (clean_history_id, clean_fund_id),
                ).fetchone()[0]
                conn.execute(
                    "delete from fund_amount_history where id = ? and fund_id = ?",
                    (clean_history_id, clean_fund_id),
                )
                if before:
                    self._sync_fund_amount_from_history(conn, clean_fund_id)
        return bool(before)

    def _sync_fund_amount_from_history(self, conn: sqlite3.Connection, fund_id: str) -> None:
        latest = conn.execute(
            """
            select amount
            from fund_amount_history
            where fund_id = ?
            order by amount_date desc, updated_at desc
            limit 1
            """,
            (fund_id,),
        ).fetchone()
        if latest:
            conn.execute("update funds set amount = ? where id = ?", (float(latest["amount"] or 0), fund_id))

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
            factor = (_number(scenario.get("factor"), 200) or 200) if kind == "Pension" else None
            default_annual_return = _number(scenario.get("annual_return"), _number(scenario.get("annual_return_percent"), 0))
            amount = _number(scenario.get("amount"), _number(scenario.get("current_amount"), 0))
            sex = _insurance_sex(scenario.get("gender") or scenario.get("sex"))
            scenario_name = str(scenario.get("name") or f"Scenario {index}").strip()
            try:
                periods = _income_periods(scenario, current_age, retire_age)
                return_periods = _return_periods(scenario, current_age, retire_age)
            except ValueError as exc:
                raise ValueError(f"{scenario_name}: {exc}") from None
            timeline = []
            total_deposits = 0.0
            total_gross_deposits = 0.0
            total_insurance_cost = 0.0
            months = int(round((retire_age - current_age) * 12))
            for month in range(months):
                age = current_age + month / 12
                period = _period_for_age(periods, age) or {}
                return_period = _period_for_age(return_periods, age) or {}
                annual_return_pct = _number(return_period.get("annual_return"), default_annual_return)
                annual_return = annual_return_pct / 100
                monthly_return = (1 + annual_return) ** (1 / 12) - 1 if annual_return > -1 else -1
                income = _number(period.get("monthly_income"), _number(scenario.get("monthly_income"), 0))
                contribution_percent = _number(period.get("contribution_percent"), _number(scenario.get("contribution_percent"), 0))
                salary_contribution = income * contribution_percent / 100 if income > 0 and contribution_percent > 0 else 0
                extra_deposit = _number(period.get("monthly_deposit"), _number(scenario.get("monthly_deposit"), 0))
                gross_monthly_deposit = salary_contribution + extra_deposit
                insurance_cost = _pension_insurance_cost(period, age, sex, income, amount) if kind == "Pension" else 0
                monthly_deposit = gross_monthly_deposit - insurance_cost
                if monthly_return == -1:
                    amount = 0
                else:
                    amount = amount * (1 + monthly_return) + monthly_deposit
                total_deposits += monthly_deposit
                total_gross_deposits += gross_monthly_deposit
                total_insurance_cost += insurance_cost
                if month == 0 or (month + 1) % 12 == 0 or month == months - 1:
                    timeline.append(
                        {
                            "age": round(current_age + (month + 1) / 12, 2),
                            "amount": amount,
                            "monthly_deposit": monthly_deposit,
                            "gross_monthly_deposit": gross_monthly_deposit,
                            "insurance_cost": insurance_cost,
                            "annual_return": annual_return_pct,
                        }
                    )
            monthly_payout = monthly_pension(amount, factor or 200) if kind == "Pension" else None
            results.append(
                {
                    "name": scenario_name,
                    "kind": kind,
                    "birth_date": birth_date,
                    "current_age": current_age,
                    "retire_age": retire_age,
                    "gender": str(scenario.get("gender") or scenario.get("sex") or "").strip(),
                    "years": retire_age - current_age,
                    "annual_return": default_annual_return,
                    "return_periods": return_periods,
                    "starting_amount": _number(scenario.get("amount"), _number(scenario.get("current_amount"), 0)),
                    "total_deposits": total_deposits,
                    "total_gross_deposits": total_gross_deposits,
                    "total_insurance_cost": total_insurance_cost,
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
            transactions = [tx for tx in transactions if not _is_external_import_source(tx["source"])]
        positions: dict[tuple[str, str, str], dict[str, Any]] = {}
        for tx in sorted(transactions, key=lambda item: item["trade_date"]):
            key = (tx["account_db_id"], tx["symbol"], tx["stock_market"])
            position = positions.setdefault(
                key,
                {
                    "account": accounts.get(tx["account_db_id"]),
                    "symbol": tx["symbol"],
                    "secondary_symbol": tx.get("secondary_symbol") or "",
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

    def enrich_external_holdings(self, holdings: list[Holding]) -> list[Holding]:
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
        filtered = [item for item in holdings if item.holding.account_id in account_ids]
        cash_by_account = {row["id"]: float(row["initial_cash"] or 0) for row in account_rows}
        for tx in self.list_transactions():
            if tx["account_db_id"] in cash_by_account:
                cash_by_account[tx["account_db_id"]] += _cash_delta(tx)
        by_type: dict[str, float] = {}
        by_location: dict[str, float] = {}
        by_account: dict[str, dict[str, Any]] = {}
        accounts_by_id = {row["id"]: row for row in account_rows}
        account_details: dict[str, dict[str, Any]] = {}
        for account in account_rows:
            cash = cash_by_account.get(account["id"], 0)
            by_type[account["type"] or "Unknown"] = by_type.get(account["type"] or "Unknown", 0) + cash
            by_location[account["location"] or "Unknown"] = by_location.get(account["location"] or "Unknown", 0) + cash
            account_name = _account_label(account)
            by_account[account_name or account["id"]] = {"value": cash, "profit": 0, "cash": cash, "currency": account["currency"]}
            account_details[account["id"]] = {
                "id": account["id"],
                "label": account_name or account["id"],
                "type": account["type"],
                "location": account["location"],
                "currency": account["currency"],
                "management_company": account.get("management_company") or "",
                "username": account.get("username") or "",
                "account_id": account.get("account_id") or "",
                "persons": list(account.get("persons") or []),
                "cash": cash,
                "securities_value": 0.0,
                "value": cash,
                "profit": 0.0,
                "holdings": [],
                "funds": [],
            }
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
            account_detail = account_details.get(holding.account_id)
            if account_detail is not None:
                holding_profit = holding.unrealized_profit + holding.realized_profit
                account_detail["securities_value"] += holding.market_value
                account_detail["value"] += holding.market_value
                account_detail["profit"] += holding_profit
                account_detail["holdings"].append(
                    {
                        "symbol": holding.symbol,
                        "name": holding.name or holding.symbol,
                        "asset_class": holding.asset_class,
                        "quantity": holding.quantity,
                        "market_value": holding.market_value,
                        "profit": holding_profit,
                        "currency": holding.currency or account_detail["currency"],
                    }
                )
        funds = [item for item in self.list_funds() if item.get("account_id") in account_ids]
        for fund in funds:
            if fund.get("account_id") in account_details:
                account_details[fund["account_id"]]["funds"].append(fund)
        for detail in account_details.values():
            detail["holdings"].sort(key=lambda item: (-abs(float(item["market_value"] or 0)), item["symbol"]))
        cash = sum(cash_by_account.values())
        securities_value = sum(item.holding.market_value for item in filtered)
        person_id = str(filters.get("person_id") or "").strip()
        person_name = str(filters.get("person_name") or "").strip()
        if person_id and not person_name:
            person_name = next(
                (item["name"] for item in self.list_family_members() if item.get("id") == person_id),
                "",
            )
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
            "account_details": list(account_details.values()),
            "scope": {
                "account_id": str(filters.get("account_id") or ""),
                "account_type": str(filters.get("account_type") or ""),
                "location": str(filters.get("location") or ""),
                "person_id": person_id,
                "person_name": person_name,
                "entire_portfolio": not any(
                    str(filters.get(key) or "").strip()
                    for key in ("account_id", "account_type", "location", "person_id", "person_name")
                ),
            },
            "funds": {
                "count": len(funds),
                "amount": sum(item["amount"] for item in funds),
                "monthly_estimate": sum(_number(item.get("monthly_estimate"), 0) for item in funds),
                "items": funds,
            },
        }

    def import_external(
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
            holdings_by_key: dict[tuple[str, str], list[Holding]] = {}
            for holding in holdings:
                holdings_by_key.setdefault(_source_account_key(holding.account, holding.currency), []).append(holding)
            transactions_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for transaction in source_transactions:
                key = _source_account_key(transaction.get("account"), transaction.get("account_currency") or transaction.get("currency"))
                transactions_by_key.setdefault(key, []).append(transaction)

            accounts_by_key: dict[tuple[str, str], dict[str, Any]] = {}
            skipped_accounts: list[dict[str, Any]] = []
            updated_account_cash = 0
            imported_positions = 0
            updated_positions = 0
            attached_positions = 0
            imported_source_transactions = 0
            accepted_symbols: set[str] = set()

            all_keys = sorted(set(cash_by_account) | set(holdings_by_key) | set(transactions_by_key))
            for key in all_keys:
                cash_item = cash_by_account.get(key, {})
                source_holding = (holdings_by_key.get(key) or [None])[0]
                source_transaction = (transactions_by_key.get(key) or [None])[0]
                source_account = (
                    cash_item.get("account")
                    or (source_holding.account if source_holding else "")
                    or (source_transaction.get("account") if source_transaction else "")
                )
                source_currency = key[1]
                source_platform = (
                    cash_item.get("platform")
                    or (source_holding.platform if source_holding else "")
                    or (source_transaction.get("platform") if source_transaction else "")
                )
                clean_account = _clean_source_label(source_account)
                account = self._account_by_external(clean_account, source_currency)
                reason = ""
                if not account:
                    reason = "account_not_found"
                else:
                    try:
                        _validated_account_persons(account.get("type"), account.get("persons"))
                    except ValueError:
                        reason = "account_owner_required"
                if reason:
                    skipped_accounts.append(
                        {
                            "account": clean_account or "Unnamed source account",
                            "currency": source_currency,
                            "platform": _clean_source_label(source_platform),
                            "required_account_id": clean_account or "account",
                            "existing_account_id": account.get("id", "") if account else "",
                            "reason": reason,
                            "cash": _number(cash_item.get("cash"), 0),
                            "has_cash": bool(cash_item),
                            "positions": len(holdings_by_key.get(key, [])),
                            "transactions": len(transactions_by_key.get(key, [])),
                        }
                    )
                    continue
                accounts_by_key[key] = account
                if cash_item and abs(float(account.get("initial_cash") or 0) - _number(cash_item.get("cash"), 0)) > 1e-9:
                    with self._connect() as conn:
                        conn.execute("update accounts set initial_cash = ? where id = ?", (_number(cash_item.get("cash"), 0), account["id"]))
                    accounts_by_key[key] = self._account_out(self._account(account["id"]))
                    updated_account_cash += 1

            if source_transactions:
                updated_positions = self._delete_imported_positions_for_accounts({account["id"] for account in accounts_by_key.values()})
                for tx in source_transactions:
                    key = _source_account_key(tx.get("account"), tx.get("account_currency") or tx.get("currency"))
                    account = accounts_by_key.get(key)
                    if not account:
                        continue
                    clean_symbol = _clean_security_symbol(tx.get("symbol"))
                    accepted_symbols.add(clean_symbol)
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
                            "source": EXTERNAL_IMPORT_SOURCE,
                            "comments": tx.get("comments") or "Imported source order",
                        }
                    )
                    imported_source_transactions += 1

            for holding in holdings:
                key = _source_account_key(holding.account, holding.currency)
                account = accounts_by_key.get(key)
                if not account:
                    continue
                clean_symbol = _clean_security_symbol(holding.symbol)
                accepted_symbols.add(clean_symbol)
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
                            "source": EXTERNAL_IMPORT_SOURCE,
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
                            "source": EXTERNAL_IMPORT_SOURCE,
                        }
                    )
                imported_positions += 1
                attached_positions += 1
            return {
                "accounts": 0,
                "account_cash_updated": updated_account_cash,
                "positions": imported_positions,
                "updated_positions": updated_positions,
                "attached_positions": attached_positions,
                "source_transactions": imported_source_transactions,
                "skipped_accounts": skipped_accounts,
                "skipped_positions": sum(item["positions"] for item in skipped_accounts),
                "skipped_transactions": sum(item["transactions"] for item in skipped_accounts),
                "skipped_cash_accounts": sum(1 for item in skipped_accounts if item["has_cash"]),
                "accepted_symbols": sorted(accepted_symbols),
                "partial": bool(skipped_accounts),
            }

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
        return self._account_out(row) if row else None

    def _has_imported_position(self, account_db_id: str, symbol: str) -> bool:
        with self._connect() as conn:
            count = conn.execute(
                "select count(*) from transactions where account_db_id = ? and symbol = ? and source like '%_import'",
                (account_db_id, symbol),
            ).fetchone()[0]
        return bool(count)

    def _delete_imported_position(self, account_db_id: str, symbol: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "delete from transactions where account_db_id = ? and symbol = ? and source like '%_import'",
                (account_db_id, symbol),
            )

    def _delete_imported_positions_for_accounts(self, account_ids: set[str]) -> int:
        if not account_ids:
            return 0
        placeholders = ", ".join("?" for _ in account_ids)
        values = sorted(account_ids)
        with self._connect() as conn:
            count = conn.execute(
                f"select count(*) from transactions where source like '%_import' and account_db_id in ({placeholders})",
                values,
            ).fetchone()[0]
            conn.execute(
                f"delete from transactions where source like '%_import' and account_db_id in ({placeholders})",
                values,
            )
        return int(count)

    def _filtered_accounts(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        accounts = self.list_accounts()
        account_id = str(filters.get("account_id") or "")
        account_type = str(filters.get("account_type") or "")
        location = str(filters.get("location") or "")
        person_id = str(filters.get("person_id") or "").strip()
        person_name = " ".join(str(filters.get("person_name") or "").split()).casefold()
        if account_id:
            accounts = [item for item in accounts if item["id"] == account_id]
        if account_type:
            accounts = [item for item in accounts if item["type"] == account_type]
        if location:
            location_key = _location_key(location)
            accounts = [item for item in accounts if _location_key(item["location"]) == location_key]
        if person_id or person_name:
            accounts = [
                account
                for account in accounts
                if any(
                    (person_id and str(person.get("member_id") or "") == person_id)
                    or (
                        person_name
                        and " ".join(str(person.get("name") or "").split()).casefold() == person_name
                    )
                    for person in account.get("persons") or []
                )
            ]
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
        elif action in {"DIVIDEND", "INTEREST"}:
            position["realized_profit"] += _cash_delta(tx)
        elif action == "FEE":
            position["realized_profit"] -= float(tx["quantity"] or 0) * float(tx["price"] or 0)

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
            secondary_symbol=position.get("secondary_symbol") or "",
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
        ma_metrics = moving_averages(prices)
        level_metrics = support_resistance(prices)
        volume = volume_metrics(prices)
        analysis = SymbolAnalysis(
            holding=holding,
            provider_status={"local_portfolio": "ok", **({"manual_security": "manual prices only"} if position.get("is_manual_security") else {})},
            price_ranges=price_range_metrics(prices),
            moving_averages=ma_metrics,
            support_resistance=level_metrics,
            volume=volume,
            income_trend=Trend(message="No local income statements"),
            profit_trend=Trend(message="No local company profit statements"),
            dividend_trend=Trend(message="No local dividend history"),
            profit_market_cap_trend=Trend(message="No local market cap data"),
            industry="",
            missing=[] if prices else ["price history"],
            technical_signals=technical_signals(ma_metrics, level_metrics, volume),
        )
        analysis.missing.extend(["income", "profit", "dividend", "profit/market cap", "industry"])
        return analysis

    def _prices(self, symbol: str, stock_market: str, asset_class: str, location: str, currency: str, up_to: date | None = None) -> list[Ohlcv]:
        rows = self.price_history(symbol, stock_market, to_date=up_to)
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
        item["monthly_estimate"] = monthly_pension(item["amount"], item["factor"]) if item.get("kind") == "Pension" else None
        with self._connect() as conn:
            history_rows = conn.execute(
                "select amount_date, amount from fund_amount_history where fund_id = ? order by amount_date, created_at",
                (item["id"],),
            ).fetchall()
        if history_rows:
            first = history_rows[0]
            latest = history_rows[-1]
            change = float(latest["amount"] or 0) - float(first["amount"] or 0)
            item["history_points"] = len(history_rows)
            item["history_first_date"] = first["amount_date"]
            item["history_latest_date"] = latest["amount_date"]
            item["history_change"] = change
            item["history_change_percent"] = change / abs(float(first["amount"] or 0)) * 100 if float(first["amount"] or 0) else None
        else:
            item["history_points"] = 0
            item["history_first_date"] = None
            item["history_latest_date"] = None
            item["history_change"] = None
            item["history_change_percent"] = None
        item["account"] = None
        item["account_label"] = ""
        if item.get("account_id"):
            with self._connect() as conn:
                account = conn.execute("select * from accounts where id = ?", (item["account_id"],)).fetchone()
            if account:
                item["account"] = self._account_out(account)
                item["account_label"] = _account_label(item["account"])
                item["persons"] = list(item["account"]["persons"])
                item["birth_date"] = item["persons"][0]["birth_date"] if item["persons"] else ""
        if item["account"] is None:
            item["persons"] = _clean_persons(item.get("persons"))
        return item

    def _event_out(self, row) -> dict[str, Any]:
        item = _dict(row)
        details = item.get("details")
        if isinstance(details, str):
            try:
                item["details"] = json.loads(details) if details else {}
            except json.JSONDecodeError:
                item["details"] = {}
        account_bits = [item.get("management_company"), item.get("username"), item.get("account_id")]
        item["account_label"] = " ".join(_clean_source_label(value) for value in account_bits if _clean_source_label(value))
        return item

    def _account_out(self, row) -> dict[str, Any]:
        item = _dict(row)
        item["persons"] = _clean_persons(item.get("persons"))
        return item

    def _broker_out(self, row) -> dict[str, Any]:
        item = _dict(row)
        item["country"] = _broker_country(item.get("country"))
        item["currency"] = str(item.get("currency") or _currency_for_location(item["country"])).upper().strip()
        item["attached_accounts"] = self.broker_account_count(item.get("name", ""))
        return item

    def _family_member_out(self, row) -> dict[str, Any]:
        item = _dict(row)
        if not item.get("first_name") and not item.get("last_name"):
            item["first_name"], item["last_name"] = _split_person_name(item.get("name"))
        item["name"] = _full_person_name(item.get("first_name"), item.get("last_name")) or str(item.get("name") or "").strip()
        item["birth_date"] = _clean_birth_date(item.get("birth_date"))
        item["retire_age"] = _optional_number(item.get("retire_age"))
        item["age"] = age_from_birth_date(item["birth_date"])
        attached_accounts = self.family_member_accounts(item["id"]) if item.get("id") else []
        item["attached_accounts"] = len(attached_accounts)
        item["attached_account_items"] = attached_accounts
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
    birth_date = _parse_date(value)
    if not birth_date:
        raise ValueError("Birth date must use DD/MM/YYYY")
    today = on_date or date.today()
    if birth_date > today:
        raise ValueError("Birth date cannot be in the future")
    return round((today - birth_date).days / 365.2425, 2)


def _clean_birth_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = _parse_date(text)
    if not parsed:
        raise ValueError("Birth date must use DD/MM/YYYY")
    if parsed > date.today():
        raise ValueError("Birth date cannot be in the future")
    return parsed.isoformat()


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
        first_name = str(item.get("first_name") or "").strip()
        last_name = str(item.get("last_name") or "").strip()
        if not first_name and not last_name:
            first_name, last_name = _split_person_name(item.get("name") or f"Person {index}")
        name = _full_person_name(first_name, last_name) or f"Person {index}"
        person = {
            "name": name,
            "first_name": first_name or name,
            "last_name": last_name,
            "birth_date": birth_date,
            "age": age_from_birth_date(birth_date),
        }
        member_id = str(item.get("member_id") or item.get("id") or "").strip()
        if member_id:
            person["member_id"] = member_id
        gender = str(item.get("gender") or "").strip()
        if gender:
            person["gender"] = gender
        retire_age = _optional_number(item.get("retire_age"))
        if retire_age is not None:
            person["retire_age"] = retire_age
        persons.append(person)
    return persons


def _validated_account_persons(account_type: Any, value: Any) -> list[dict[str, Any]]:
    clean_type = _choice(account_type, ACCOUNT_TYPES, "Investment")
    persons = _clean_persons(value)
    if not persons:
        raise ValueError("Every account must be assigned to at least one person")
    if clean_type in SINGLE_OWNER_ACCOUNT_TYPES and len(persons) != 1:
        raise ValueError(f"{clean_type} accounts must be assigned to exactly one person")
    return persons


def validate_portfolio_ownership(
    accounts: list[dict[str, Any]],
    funds: list[dict[str, Any]],
    *,
    sync_fund_persons: bool = False,
) -> None:
    accounts_by_id: dict[str, dict[str, Any]] = {}
    for account in accounts:
        persons = _validated_account_persons(account.get("type"), account.get("persons"))
        accounts_by_id[str(account.get("id") or "")] = {**account, "persons": persons}
        if sync_fund_persons:
            account["persons"] = json.dumps(persons)
    for fund in funds:
        account_id = str(fund.get("account_id") or "").strip()
        if not account_id:
            raise ValueError("Every pension or fund record must be linked to a Long-Term Savings account")
        account = accounts_by_id.get(account_id)
        if not account:
            raise ValueError("A pension or fund record is linked to a missing account")
        if account.get("type") != "Long-Term Savings":
            raise ValueError("A pension or fund record must use a Long-Term Savings account")
        owner = _validated_account_persons(account.get("type"), account.get("persons"))[0]
        if sync_fund_persons:
            fund["persons"] = json.dumps([owner])
            fund["birth_date"] = owner["birth_date"]


def _split_person_name(value: Any) -> tuple[str, str]:
    parts = str(value or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def _full_person_name(first_name: Any, last_name: Any) -> str:
    return " ".join(part for part in [str(first_name or "").strip(), str(last_name or "").strip()] if part)


def _income_periods(scenario: dict[str, Any], current_age: float, retire_age: float) -> list[dict[str, Any]]:
    raw = scenario.get("income_periods")
    explicit_schedule = "income_periods" in scenario
    if not isinstance(raw, list) or not raw:
        if explicit_schedule:
            _validate_period_coverage([], current_age, retire_age, "Salary")
        raw = [
            {
                "from_age": current_age,
                "to_age": retire_age,
                "monthly_income": scenario.get("monthly_income"),
                "contribution_percent": scenario.get("contribution_percent"),
                "monthly_deposit": scenario.get("monthly_deposit"),
                "disability_coverage_percent": scenario.get("disability_coverage_percent"),
                "spouse_survivors_coverage_percent": scenario.get("spouse_survivors_coverage_percent"),
                "children_survivors_coverage_percent": scenario.get("children_survivors_coverage_percent"),
                "survivors_capitalization_factor": scenario.get("survivors_capitalization_factor"),
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
                "disability_coverage_percent": item.get("disability_coverage_percent"),
                "spouse_survivors_coverage_percent": item.get("spouse_survivors_coverage_percent"),
                "children_survivors_coverage_percent": item.get("children_survivors_coverage_percent"),
                "survivors_capitalization_factor": item.get("survivors_capitalization_factor"),
            }
        )
    periods = sorted(periods, key=lambda item: item["from_age"])
    _validate_period_coverage(periods, current_age, retire_age, "Salary")
    return periods


def _load_pension_insurance_rates() -> dict[int, dict[str, Any]]:
    global PENSION_INSURANCE_RATES
    if PENSION_INSURANCE_RATES is not None:
        return PENSION_INSURANCE_RATES
    if not PENSION_INSURANCE_RATES_PATH.exists():
        raise ValueError("Pension insurance rates file is missing")
    data = yaml.safe_load(PENSION_INSURANCE_RATES_PATH.read_text()) or {}
    rows = data.get("rates") or []
    PENSION_INSURANCE_RATES = {int(row["age"]): row for row in rows if isinstance(row, dict) and row.get("age") is not None}
    return PENSION_INSURANCE_RATES


def _insurance_sex(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"male", "m", "man", "זכר", "גבר"}:
        return "male"
    if text in {"female", "f", "woman", "נקבה", "אישה", "אשה"}:
        return "female"
    return None


def _pension_insurance_cost(period: dict[str, Any], age: float, sex: str | None, insured_salary: float, savings_balance: float) -> float:
    if insured_salary <= 0:
        return 0.0
    disability_coverage = max(_number(period.get("disability_coverage_percent"), 0), 0)
    spouse_survivors_coverage = max(_number(period.get("spouse_survivors_coverage_percent"), 0), 0)
    children_survivors_coverage = max(_number(period.get("children_survivors_coverage_percent"), 0), 0)
    if not any([disability_coverage, spouse_survivors_coverage, children_survivors_coverage]):
        return 0.0
    if sex not in {"male", "female"}:
        raise ValueError("Gender is required for pension insurance cost")
    completed_age = math.floor(age)
    rate_row = _load_pension_insurance_rates().get(completed_age)
    if not rate_row:
        raise ValueError(f"Pension insurance rate is missing for age {completed_age}")
    disability_rate = _number(rate_row.get(f"disability_{sex}"), 0)
    survivors_rate = _number(rate_row.get(f"survivors_{sex}"), 0)
    disability_factor = 0.95 * (disability_coverage / 75) if disability_coverage > 0 else 0
    disability_cost = (insured_salary * disability_factor * disability_rate) / 1000
    survivors_coverage = (spouse_survivors_coverage + children_survivors_coverage) / 100
    capitalization_factor = _number(period.get("survivors_capitalization_factor"), 200) or 200
    net_capital_at_risk = max((insured_salary * survivors_coverage * capitalization_factor) - max(savings_balance, 0), 0)
    survivors_cost = (net_capital_at_risk * survivors_rate) / 100000 if survivors_coverage > 0 else 0
    return disability_cost + survivors_cost


def _return_periods(scenario: dict[str, Any], current_age: float, retire_age: float) -> list[dict[str, Any]]:
    raw = scenario.get("return_periods")
    if not isinstance(raw, list) or not raw:
        _validate_period_coverage([], current_age, retire_age, "Return")
    periods = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        from_age = _number(item.get("from_age"), current_age)
        to_age = _number(item.get("to_age"), retire_age)
        if to_age <= from_age:
            raise ValueError("Profit rate row needs valid from/to ages")
        raw_return = item.get("annual_return", item.get("annual_return_percent"))
        if raw_return in (None, ""):
            raise ValueError("Annual profit is required")
        try:
            annual_return = float(raw_return)
        except (TypeError, ValueError):
            raise ValueError("Annual profit must be numeric") from None
        periods.append(
            {
                "from_age": max(from_age, current_age),
                "to_age": min(to_age, retire_age),
                "annual_return": annual_return,
            }
        )
    periods = sorted(periods, key=lambda item: item["from_age"])
    _validate_period_coverage(periods, current_age, retire_age, "Return")
    return periods


def _schedule_age_label(value: float) -> str:
    return f"{round(float(value), 2):g}"


def _validate_period_coverage(
    periods: list[dict[str, Any]],
    current_age: float,
    retire_age: float,
    schedule_name: str,
) -> None:
    tolerance = 1e-6
    cursor = current_age
    relevant_periods = [
        period
        for period in periods
        if _number(period.get("to_age"), 0) > current_age + tolerance
        and _number(period.get("from_age"), retire_age) < retire_age - tolerance
    ]
    if not relevant_periods:
        raise ValueError(
            f"{schedule_name} schedule is missing ages "
            f"{_schedule_age_label(current_age)}–{_schedule_age_label(retire_age)}"
        )
    for period in relevant_periods:
        from_age = max(_number(period.get("from_age"), current_age), current_age)
        to_age = min(_number(period.get("to_age"), retire_age), retire_age)
        if from_age > cursor + tolerance:
            raise ValueError(
                f"{schedule_name} schedule is missing ages "
                f"{_schedule_age_label(cursor)}–{_schedule_age_label(from_age)}"
            )
        if from_age < cursor - tolerance:
            overlap_to = min(cursor, to_age)
            raise ValueError(
                f"{schedule_name} schedule has overlapping periods at ages "
                f"{_schedule_age_label(from_age)}–{_schedule_age_label(overlap_to)}"
            )
        cursor = max(cursor, to_age)
    if cursor < retire_age - tolerance:
        raise ValueError(
            f"{schedule_name} schedule is missing ages "
            f"{_schedule_age_label(cursor)}–{_schedule_age_label(retire_age)}"
        )


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
    if text.casefold().startswith("import-"):
        text = text[len("import-"):]
    return " ".join(text.split()).strip(" -")


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
        "EMPLOYEE_STOCK_OPTION": "EMPLOYEE_STOCK_OPTION",
        "PRIVATE_STOCK": "PRIVATE_STOCK",
        "STOCK_OPTION": "STOCK_OPTION",
    }
    requested_text = str(requested or "").upper().strip()
    if requested_text in ASSET_CLASSES and instrument_type not in mapping:
        return requested_text
    return mapping.get(instrument_type, requested_text if requested_text in ASSET_CLASSES else "EQUITY")


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + int(months)
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _build_vesting_schedule(payload: dict[str, Any], total_quantity: float, default_start: Any) -> dict[str, Any]:
    mode = str(payload.get("mode") or "PERCENT").upper().strip()
    if mode not in {"PERCENT", "ABSOLUTE"}:
        raise ValueError("Vesting schedule mode must be percentage or option units")
    start = _parse_date(payload.get("vesting_start_date") or default_start)
    if not start:
        raise ValueError("Vesting start date is required")
    duration_months = int(_number(payload.get("duration_months"), 48))
    cliff_months = int(_number(payload.get("cliff_months"), 12))
    interval_months = int(_number(payload.get("interval_months"), 3))
    cliff_value = _number(payload.get("cliff_value"), 25)
    installment_value = _number(payload.get("installment_value"), 6.25)
    if total_quantity <= 0:
        raise ValueError("Total option quantity must be greater than zero")
    if duration_months < 1 or duration_months > 600:
        raise ValueError("Vesting duration must be between 1 and 600 months")
    if cliff_months < 0 or cliff_months > duration_months:
        raise ValueError("Cliff months must be between 0 and the vesting duration")
    if interval_months < 1 or interval_months > duration_months:
        raise ValueError("Recurring vesting interval must be between 1 month and the vesting duration")
    if cliff_value <= 0:
        raise ValueError("Cliff vesting amount must be greater than zero")
    if mode == "PERCENT" and cliff_value > 100:
        raise ValueError("Cliff vesting percentage cannot exceed 100%")

    def quantity_for(value: float) -> float:
        return total_quantity * value / 100 if mode == "PERCENT" else value

    epsilon = max(1e-8, abs(total_quantity) * 1e-10)
    cliff_quantity = quantity_for(cliff_value)
    if cliff_quantity > total_quantity + epsilon:
        raise ValueError("Cliff vesting amount cannot exceed the total option quantity")
    tranches: list[dict[str, Any]] = []
    vested = 0.0

    def add_tranche(month_offset: int, requested_quantity: float) -> None:
        nonlocal vested
        amount = min(requested_quantity, total_quantity - vested)
        if amount <= epsilon:
            return
        vested = min(total_quantity, vested + amount)
        rounded_amount = round(amount, 8)
        rounded_cumulative = round(vested, 8)
        tranches.append(
            {
                "sequence": len(tranches) + 1,
                "vest_date": _add_months(start, month_offset).isoformat(),
                "quantity": rounded_amount,
                "cumulative_quantity": rounded_cumulative,
                "cumulative_percent": round(rounded_cumulative / total_quantity * 100, 6),
            }
        )

    add_tranche(cliff_months, cliff_quantity)
    if vested < total_quantity - epsilon:
        if installment_value <= 0:
            raise ValueError("Recurring vesting amount must be greater than zero")
        if mode == "PERCENT" and installment_value > 100:
            raise ValueError("Recurring vesting percentage cannot exceed 100%")
        installment_quantity = quantity_for(installment_value)
        month_offset = cliff_months + interval_months
        while vested < total_quantity - epsilon and month_offset <= duration_months:
            add_tranche(month_offset, installment_quantity)
            month_offset += interval_months
    if vested < total_quantity - epsilon:
        missing = total_quantity - vested
        unit = "%" if mode == "PERCENT" else "options"
        raise ValueError(
            f"Vesting schedule leaves {missing:g} options unvested by month {duration_months}; adjust the recurring {unit} or duration"
        )
    if not tranches:
        raise ValueError("Vesting schedule must contain at least one tranche")
    return {
        "enabled": True,
        "mode": mode,
        "vesting_start_date": start.isoformat(),
        "duration_months": duration_months,
        "cliff_months": cliff_months,
        "cliff_value": cliff_value,
        "interval_months": interval_months,
        "installment_value": installment_value,
        "total_quantity": round(total_quantity, 8),
        "tranches": tranches,
    }


def _source_account_key(account: Any, currency: Any) -> tuple[str, str]:
    return (_clean_source_label(account).casefold(), str(currency or "USD").upper().strip())


def _is_external_import_source(value: Any) -> bool:
    return str(value or "").strip().lower().endswith("_import")


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _number(value: Any, default: float = 0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_string(value: Any) -> str:
    parsed = _parse_date(value)
    return (parsed or date.today()).isoformat()


def _optional_date_string(value: Any) -> str:
    if not value:
        return ""
    parsed = _parse_date(value)
    if not parsed:
        raise ValueError("Date must use DD/MM/YYYY")
    return parsed.isoformat()


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
    text = str(value).strip()
    if "/" in text:
        parts = text.split("/")
        if len(parts) == 3:
            try:
                day, month, year = (int(part) for part in parts)
                return date(year, month, day)
            except ValueError:
                return None
    try:
        return date.fromisoformat(text[:10])
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


def _broker_country(location: Any) -> str:
    key = _location_key(str(location or "USA"))
    if key == "israel":
        return "Israel"
    if key == "usa":
        return "USA"
    return "USA"


def _cash_delta(tx: dict[str, Any]) -> float:
    value = float(tx["quantity"] or 0) * float(tx["price"] or 0)
    if tx["action"] == "BUY":
        return -value
    if tx["action"] in {"SELL", "SHORT", "DIVIDEND", "INTEREST"}:
        return value
    if tx["action"] == "FEE":
        return -value
    return 0.0


def _ratio_percent(value: float | None, basis: float | None) -> float | None:
    if value is None or basis in (None, 0):
        return None
    return (value / abs(basis)) * 100


def to_dict(item: SymbolAnalysis) -> dict[str, Any]:
    return asdict(item)
