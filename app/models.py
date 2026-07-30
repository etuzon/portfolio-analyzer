from dataclasses import dataclass, field
from datetime import date
from typing import Literal


MetricState = Literal["ok", "stale", "partial", "missing", "error"]
TrendDirection = Literal["up", "down", "flat", "missing"]


@dataclass
class Holding:
    symbol: str
    name: str = ""
    asset_class: str = "UNKNOWN"
    asset_sub_class: str = ""
    data_source: str = ""
    stock_market: str = ""
    currency: str = "USD"
    quantity: float = 0
    cost_basis: float = 0
    market_value: float = 0
    realized_profit: float = 0
    unrealized_profit: float = 0
    income_received: float = 0
    account: str = ""
    account_id: str = ""
    account_type: str = ""
    platform: str = ""
    location: str = ""
    country: str = ""
    sector: str = ""
    industry: str = ""


@dataclass
class Ohlcv:
    date: date
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    volume: float


@dataclass
class Trend:
    state: MetricState = "missing"
    direction: TrendDirection = "missing"
    current: float | None = None
    previous: float | None = None
    percent_change: float | None = None
    series: list[dict] = field(default_factory=list)
    message: str = ""


@dataclass
class SymbolAnalysis:
    holding: Holding
    provider_status: dict[str, str]
    price_ranges: dict[str, dict]
    moving_averages: dict[str, dict]
    support_resistance: dict[str, dict]
    volume: dict
    income_trend: Trend
    profit_trend: Trend
    dividend_trend: Trend
    profit_market_cap_trend: Trend
    industry: str
    missing: list[str]
    market_cap: float | None = None
