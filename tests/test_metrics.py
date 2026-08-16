from datetime import date, timedelta

from app.metrics import analyze_holding, confirmed_breakout_signal, moving_averages, percent, price_range_metrics, screen, support_resistance
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
    assert metrics["30"]["slope_percent"] > 0


def test_confirmed_breakout_requires_cross_volume_and_rising_ma30():
    signal = confirmed_breakout_signal(
        {
            "state": "ok",
            "resistance": {"price": 120},
            "previous_price": 119,
            "current_price": 122,
        },
        {"state": "ok", "value": 115, "slope_percent": 0.4},
        {"state": "ok", "relative_20d": 1.6},
    )

    assert signal["state"] == "ok"
    assert signal["signal"] == "confirmed_breakout"
    assert signal["triggered"] is True
    assert signal["score_met"] == signal["score_total"] == 4
    assert all(condition["met"] is True for condition in signal["conditions"].values())


def test_confirmed_breakout_stays_on_watch_when_any_confirmation_fails():
    signal = confirmed_breakout_signal(
        {
            "state": "ok",
            "resistance": {"price": 120},
            "previous_price": 119,
            "current_price": 122,
        },
        {"state": "ok", "value": 115, "slope_percent": 0.4},
        {"state": "ok", "relative_20d": 1.49},
    )

    assert signal["signal"] == "watch"
    assert signal["triggered"] is False
    assert signal["score_met"] == 3
    assert signal["conditions"]["relative_volume"]["met"] is False


def test_confirmed_breakout_reports_missing_inputs_instead_of_guessing():
    signal = confirmed_breakout_signal(
        {"state": "missing"},
        {"state": "missing"},
        {"state": "partial", "relative_20d": None},
    )

    assert signal["state"] == "missing"
    assert signal["signal"] == "missing"
    assert signal["triggered"] is False
    assert "resistance" in signal["missing"]
    assert "MA30" in signal["missing"]
    assert "20-day relative volume" in signal["missing"]


def test_provider_sector_is_applied_before_industry_missing_check():
    class Hub:
        def prices(self, symbol, from_date, to_date, **kwargs):
            return rows(), {"prices": "ok"}

        def fundamentals(self, symbol, **kwargs):
            return {"income_statement": {"annualReports": [
                {"fiscalDateEnding": "2024-12-31", "totalRevenue": 100, "netIncome": 10},
                {"fiscalDateEnding": "2025-12-31", "totalRevenue": 110, "netIncome": 12},
            ]}}, {"fundamentals": "ok"}

        def dividends(self, symbol, **kwargs):
            return [{"date": "2025-06-01", "amount": 0.5}], {"dividends": "ok"}

        def profile(self, symbol, **kwargs):
            return {"sector": "Financial Services"}, {"profile": "ok"}

    result = analyze_holding(Holding(symbol="FDUS"), Hub())

    assert result.industry == "Financial Services"
    assert "industry" not in result.missing


def test_secondary_symbol_and_market_are_passed_for_provider_fallback_and_search():
    calls = []

    class Hub:
        def prices(self, symbol, from_date, to_date, **kwargs):
            calls.append(("prices", symbol, kwargs))
            return rows(), {"prices": "ok"}

        def fundamentals(self, symbol, **kwargs):
            calls.append(("fundamentals", symbol, kwargs))
            return {}, {"fundamentals": "missing"}

        def dividends(self, symbol, **kwargs):
            calls.append(("dividends", symbol, kwargs))
            return [], {"dividends": "missing"}

        def profile(self, symbol, **kwargs):
            calls.append(("profile", symbol, kwargs))
            return {}, {"profile": "missing"}

    holding = Holding(symbol="1101534", secondary_symbol="CEL", name="Cellcom", stock_market="TASE")
    analysis = analyze_holding(holding, Hub())

    assert {symbol for _kind, symbol, _kwargs in calls} == {"1101534"}
    assert all(kwargs == {"secondary_symbol": "CEL", "stock_market": "TASE"} for _kind, _symbol, kwargs in calls)
    assert analysis.holding.symbol == "1101534"
    assert screen([analysis], {"query": "cel"}) == [analysis]


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
