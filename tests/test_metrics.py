from datetime import date, timedelta

from app.metrics import moving_averages, percent, price_range_metrics, screen, support_resistance
from app.models import Holding, Ohlcv, SymbolAnalysis, Trend


def rows(count=40):
    start = date.today() - timedelta(days=count)
    return [
        Ohlcv(
            date=start + timedelta(days=i),
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100 + i,
            adjusted_close=100 + i,
            volume=1000 + i,
        )
        for i in range(count)
    ]


def test_percent_handles_zero_previous():
    assert percent(10, 0) is None
    assert round(percent(110, 100), 2) == 10


def test_price_ranges_emit_recent_periods():
    metrics = price_range_metrics(rows())
    assert metrics["1m"]["state"] == "ok"
    assert metrics["6m"]["state"] == "partial"
    assert metrics["1m"]["high"] > metrics["1m"]["min"]


def test_support_resistance_emits_configured_periods_and_current_prices():
    metrics = support_resistance(rows())

    assert set(metrics) >= {"1m", "6m", "1y", "3y", "5y"}
    assert metrics["1m"]["state"] == "ok"
    assert metrics["1m"]["current_price"] > metrics["1m"]["previous_price"]


def test_moving_average_windows():
    metrics = moving_averages(rows())
    assert metrics["7"]["state"] == "ok"
    assert metrics["30"]["state"] == "ok"


def test_screen_filters_account_currency_and_dividend_growth():
    item = SymbolAnalysis(
        holding=Holding(symbol="BBDC", account="Schwab Eyal", currency="USD", market_value=2500),
        provider_status={},
        price_ranges={},
        moving_averages={},
        support_resistance={},
        volume={},
        income_trend=Trend(direction="flat"),
        profit_trend=Trend(direction="up", percent_change=12),
        dividend_trend=Trend(direction="up", percent_change=5),
        profit_market_cap_trend=Trend(direction="flat"),
        industry="Financial Services",
        missing=[],
    )
    assert screen([item], {"account": "Schwab", "currency": "USD", "minDividendGrowth": "4"}) == [item]
    assert screen([item], {"account": "ETrade"}) == []


def test_screen_filters_support_resistance_distance_and_cross_direction():
    item = SymbolAnalysis(
        holding=Holding(symbol="BBDC", account="Schwab Eyal", currency="USD", market_value=2500),
        provider_status={},
        price_ranges={},
        moving_averages={},
        support_resistance={
            "1y": {
                "state": "ok",
                "support": {"price": 100},
                "resistance": {"price": 120},
                "previous_price": 99,
                "current_price": 101,
            }
        },
        volume={},
        income_trend=Trend(direction="flat"),
        profit_trend=Trend(direction="up", percent_change=12),
        dividend_trend=Trend(direction="up", percent_change=5),
        profit_market_cap_trend=Trend(direction="flat"),
        industry="Financial Services",
        missing=[],
    )

    assert screen([item], {"technicalPeriod": "1y", "technicalLevel": "support", "technicalDirection": "cross_up", "technicalDistancePct": "2"}) == [item]
    assert screen([item], {"technicalPeriod": "1y", "technicalLevel": "resistance", "technicalDirection": "cross_down", "technicalDistancePct": "2"}) == []
