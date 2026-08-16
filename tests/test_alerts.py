import json
from dataclasses import replace

import pytest

from app import main
from app.alerts import AlertStore, alert_rule_options
from app.models import Holding, SymbolAnalysis, Trend


def test_alert_store_matches_all_conditions_and_persists_run_history(tmp_path):
    store = AlertStore(tmp_path / "alerts.json")
    rule = store.add_rule(
        {
            "name": "Income at a reasonable valuation",
            "signal": "buy",
            "match_mode": "all",
            "conditions": [
                {"metric": "dividend_yield_percent", "operator": ">", "value": 2.5},
                {"metric": "profit_market_cap_percent", "operator": ">=", "value": 5},
            ],
        }
    )

    results = store.evaluate(
        [
            {
                "symbol": "GOOD",
                "name": "Good Company",
                "dividend_yield_percent": 3.2,
                "profit_market_cap_percent": 6.1,
                "market_value": 1_000,
                "currency": "USD",
            },
            {"symbol": "LOW", "dividend_yield_percent": 2.0, "profit_market_cap_percent": 8.0},
        ],
        {"portfolio_symbols": 2, "provider_errors": []},
    )

    assert [match["symbol"] for match in results[0]["matches"]] == ["GOOD"]
    assert results[0]["matches"][0]["signal"] == "buy"
    assert [reason["metric"] for reason in results[0]["matches"][0]["reasons"]] == [
        "dividend_yield_percent",
        "profit_market_cap_percent",
    ]
    stored = AlertStore(tmp_path / "alerts.json")
    assert stored.list_rules()[0]["id"] == rule["id"]
    assert stored.list_rules()[0]["last_status"] == "1 match"
    assert stored.list_runs()[0]["evaluated_symbols"] == 2
    assert stored.list_runs()[0]["matched_signals"] == 1
    assert stored.list_runs()[0]["metadata"]["portfolio_symbols"] == 2


def test_any_condition_can_match_but_reports_unavailable_rule_data(tmp_path):
    store = AlertStore(tmp_path / "alerts.json")
    store.add_rule(
        {
            "name": "Value watch",
            "signal": "watch",
            "match_mode": "any",
            "conditions": [
                {"metric": "dividend_growth_percent", "operator": ">", "value": 5},
                {"metric": "price_earnings_ratio", "operator": "<", "value": 15},
            ],
        }
    )

    results = store.evaluate(
        [
            {"symbol": "MATCH", "dividend_growth_percent": None, "price_earnings_ratio": 12},
            {"symbol": "NOPE", "dividend_growth_percent": None, "price_earnings_ratio": 20},
        ]
    )

    assert [match["symbol"] for match in results[0]["matches"]] == ["MATCH"]
    assert results[0]["matches"][0]["missing_metrics"] == ["dividend_growth_percent"]
    assert results[0]["rule"]["last_missing_count"] == 2


def test_rule_validation_update_delete_and_legacy_migration(tmp_path):
    path = tmp_path / "alerts.json"
    store = AlertStore(path)
    with pytest.raises(ValueError, match="at least one"):
        store.add_rule({"name": "Empty", "conditions": []})
    with pytest.raises(ValueError, match="Unsupported"):
        store.add_rule({"conditions": [{"metric": "unknown", "operator": ">", "value": 1}]})
    with pytest.raises(ValueError, match="numeric"):
        store.add_rule({"conditions": [{"metric": "current_ratio", "operator": ">", "value": ""}]})

    rule = store.add_rule(
        {
            "name": "Balance sheet",
            "signal": "sell",
            "conditions": [{"metric": "current_ratio", "operator": "<", "value": 1}],
        }
    )
    store.evaluate([{"symbol": "ABC", "current_ratio": 0.7}])
    updated = store.update_rule(
        rule["id"],
        {
            "name": "Balance sheet risk",
            "enabled": False,
            "signal": "sell",
            "match_mode": "all",
            "conditions": [{"metric": "current_ratio", "operator": "<", "value": 0.8}],
        },
    )
    assert updated["enabled"] is False
    assert updated["last_status"] == "1 match"
    assert store.delete_rule(rule["id"]) is True
    assert store.delete_rule(rule["id"]) is False

    path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "legacy",
                        "name": "Old rule",
                        "criteria": {"minProfitMarketCap": "0.04", "minDividendGrowth": "3"},
                    }
                ]
            }
        )
    )
    migrated = store.list_rules()[0]
    assert migrated["conditions"] == [
        {"metric": "profit_market_cap_percent", "operator": ">=", "value": 4.0},
        {"metric": "dividend_growth_percent", "operator": ">=", "value": 3.0},
    ]


def test_alert_options_expose_financial_portfolio_and_market_metrics():
    options = alert_rule_options()
    metrics = {item["key"] for item in options["metrics"]}

    assert {"dividend_yield_percent", "profit_market_cap_percent", "free_cash_flow_yield_percent"} <= metrics
    assert {"holding_allocation_percent", "price_vs_ma30_percent"} <= metrics
    assert {"confirmed_breakout", "relative_volume_20d", "ma30_slope_percent"} <= metrics
    assert {item["key"] for item in options["operators"]} == {">", ">=", "<", "<=", "="}
    assert {item["key"] for item in options["signals"]} == {"buy", "sell", "watch"}


def test_alert_store_persists_background_failure_without_stale_matches(tmp_path):
    store = AlertStore(tmp_path / "alerts.json")
    store.add_rule(
        {
            "name": "Income",
            "signal": "buy",
            "conditions": [{"metric": "dividend_yield_percent", "operator": ">", "value": 2.5}],
        }
    )
    store.evaluate([{"symbol": "ABC", "dividend_yield_percent": 3.0}])

    run = store.record_failure("Rule check failed: ProviderError", {"error_type": "ProviderError"})

    assert run["status"] == "failed"
    assert store.list_rules()[0]["last_matches"] == []
    assert store.list_rules()[0]["last_status"] == "Rule check failed: ProviderError"
    assert store.list_runs()[0]["metadata"] == {"error_type": "ProviderError"}


def test_portfolio_alert_rows_derive_portfolio_and_enriched_metrics(monkeypatch):
    analysis = SymbolAnalysis(
        holding=Holding(
            symbol="CSCO",
            name="Cisco",
            currency="USD",
            market_value=500,
            cost_basis=400,
            unrealized_profit=100,
            account="Brokerage",
            sector="Technology",
        ),
        provider_status={},
        price_ranges={"1m": {"current": 100}, "1y": {"percent_from_high": -12}},
        moving_averages={"30": {"price_vs_ma_percent": 4.5, "slope_percent": 0.35}},
        support_resistance={},
        volume={"relative_20d": 1.7},
        income_trend=Trend(),
        profit_trend=Trend(),
        dividend_trend=Trend(state="ok", percent_change=7.5),
        profit_market_cap_trend=Trend(),
        industry="Network equipment",
        missing=["one source"],
        market_cap=1_000_000_000,
        technical_signals={"confirmed_breakout": {"state": "ok", "triggered": True}},
    )

    def enrich(item, provider_hub, need_dividend_history):
        assert item["price"] == 100
        assert need_dividend_history is True
        return {
            **item,
            "annual_net_income": 50_000_000,
            "free_cash_flow": 70_000_000,
            "dividend_yield_percent": 2.8,
            "profit_market_cap_percent": 5,
            "missing": ["statement field"],
        }, True

    class Hub:
        def fx(self, pair):
            assert pair == "USD/ILS"
            return {"rate": 3.4}, {"test": "ok"}

    rsu_analysis = replace(
        analysis,
        holding=replace(analysis.holding, symbol="RSUGRANT", asset_class="RSU", market_value=10_000),
    )
    monkeypatch.setattr(main, "analyze_all", lambda: [analysis, rsu_analysis])
    monkeypatch.setattr(main, "hub", lambda: Hub())
    monkeypatch.setattr(main, "_enrich_market_screener_item", enrich)

    rows, metadata = main._portfolio_alert_rows()

    assert metadata == {
        "portfolio_symbols": 1,
        "enriched_symbols": 1,
        "provider_errors": [],
        "allocation_currency": "ILS",
    }
    assert rows[0]["market_cap_millions"] == 1_000
    assert rows[0]["annual_net_income_millions"] == 50
    assert rows[0]["free_cash_flow_millions"] == 70
    assert rows[0]["unrealized_profit_percent"] == 25
    assert rows[0]["holding_allocation_percent"] == 100
    assert rows[0]["dividend_growth_percent"] == 7.5
    assert rows[0]["price_vs_ma30_percent"] == 4.5
    assert rows[0]["ma30_slope_percent"] == 0.35
    assert rows[0]["relative_volume_20d"] == 1.7
    assert rows[0]["confirmed_breakout"] == 1.0
    assert rows[0]["price_from_high_1y_percent"] == -12
    assert rows[0]["missing"] == ["one source", "statement field"]
