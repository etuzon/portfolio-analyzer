from datetime import date
import sqlite3

import pytest

from app.local_portfolio import LocalPortfolioStore, age_from_birth_date, monthly_pension, normalize_price
from app.models import Holding


def test_market_price_units_are_normalized():
    assert normalize_price(425, "Israel", "EQUITY") == 4.25
    assert normalize_price(98.5, "USA", "BOND") == 0.985
    assert normalize_price(98.5, "United States", "BOND") == 0.985
    assert normalize_price(25, "USA", "EQUITY") == 25


def test_local_portfolio_aggregates_transactions_and_trends(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account(
        {
            "type": "Investment",
            "location": "USA",
            "currency": "USD",
            "initial_cash": 1000,
            "username": "Eyal",
            "account_id": "A1",
            "management_company": "Broker",
        }
    )
    store.add_transaction(
        {
            "account_db_id": account["id"],
            "action": "BUY",
            "symbol": "ABC",
            "stock_market": "NYSE",
            "asset_class": "EQUITY",
            "quantity": 10,
            "price_input": 20,
            "trade_date": "2026-01-01",
            "allow_manual": True,
        }
    )
    store.save_price(
        {
            "symbol": "ABC",
            "stock_market": "NYSE",
            "asset_class": "EQUITY",
            "location": "USA",
            "currency": "USD",
            "price_input": 25,
            "price_date": "2026-01-10",
        }
    )

    holdings = store.holdings()
    assert len(holdings) == 1
    assert holdings[0].holding.market_value == 250
    assert holdings[0].holding.unrealized_profit == 50

    trends = store.account_trends({"account_id": account["id"], "from": "2026-01-01", "to": "2026-01-10"})
    assert trends["accounts"][0]["points"][-1]["value"] == 1050
    assert trends["accounts"][0]["points"][-1]["cash"] == 800
    assert trends["accounts"][0]["points"][-1]["profit_percent"] == 25

    report = store.reports({"account_id": account["id"]})
    assert report["cash"] == 800
    assert report["securities_value"] == 250
    assert report["value"] == 1050


def test_trade_quantity_validation_and_long_position_close(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "Investment", "location": "USA", "currency": "USD", "initial_cash": 1000, "username": "Eyal"})
    base = {
        "account_db_id": account["id"],
        "symbol": "ABC",
        "stock_market": "NYSE",
        "asset_class": "EQUITY",
        "price_input": 10,
        "allow_manual": True,
    }
    store.add_transaction({**base, "action": "BUY", "quantity": 10, "trade_date": "2026-01-01"})

    with pytest.raises(ValueError, match="sell at most 10"):
        store.add_transaction({**base, "action": "SELL", "quantity": 11, "trade_date": "2026-01-02"})

    closed = store.add_transaction({**base, "action": "SELL", "quantity": 10, "price_input": 12, "trade_date": "2026-01-02"})

    assert closed["position_quantity"] == 0
    assert closed["position_closed"] is True
    assert closed["position_side"] == "closed"
    assert store.holdings() == []


def test_short_cover_validation_and_close(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "Investment", "location": "USA", "currency": "USD", "initial_cash": 1000, "username": "Eyal"})
    base = {
        "account_db_id": account["id"],
        "symbol": "XYZ",
        "stock_market": "NASDAQ",
        "asset_class": "EQUITY",
        "price_input": 20,
        "allow_manual": True,
    }
    opened = store.add_transaction({**base, "action": "SHORT", "quantity": 5, "trade_date": "2026-01-01"})
    assert opened["position_quantity"] == -5
    assert opened["position_side"] == "short"

    with pytest.raises(ValueError, match="buy at most 5"):
        store.add_transaction({**base, "action": "BUY", "quantity": 6, "trade_date": "2026-01-02"})

    closed = store.add_transaction({**base, "action": "BUY", "quantity": 5, "price_input": 18, "trade_date": "2026-01-02"})
    assert closed["position_closed"] is True
    assert store.holdings() == []


def test_short_cannot_cross_a_long_position_and_edit_keeps_ledger_valid(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "Investment", "location": "USA", "currency": "USD", "initial_cash": 1000, "username": "Eyal"})
    base = {
        "account_db_id": account["id"],
        "symbol": "ABC",
        "stock_market": "NYSE",
        "asset_class": "EQUITY",
        "price_input": 10,
        "allow_manual": True,
    }
    buy = store.add_transaction({**base, "action": "BUY", "quantity": 10, "trade_date": "2026-01-01"})

    with pytest.raises(ValueError, match="Close the long position"):
        store.add_transaction({**base, "action": "SHORT", "quantity": 1, "trade_date": "2026-01-02"})

    store.add_transaction({**base, "action": "SELL", "quantity": 6, "trade_date": "2026-01-03"})
    with pytest.raises(ValueError, match="sell at most 5"):
        store.update_transaction(buy["id"], {"quantity": 5})


def test_account_update_preserves_transactions(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account(
        {
            "type": "Investment",
            "location": "USA",
            "currency": "USD",
            "initial_cash": 1000,
            "username": "Eyal",
            "account_id": "A1",
            "management_company": "",
        }
    )
    store.add_transaction(
        {
            "account_db_id": account["id"],
            "action": "ADD",
            "symbol": "ABC",
            "stock_market": "NYSE",
            "asset_class": "EQUITY",
            "quantity": 5,
            "price_input": 10,
            "trade_date": "2026-01-01",
            "allow_manual": True,
        }
    )

    updated = store.save_account({**account, "management_company": "ETrade"})

    assert updated["id"] == account["id"]
    assert updated["management_company"] == "ETrade"
    assert len(store.list_transactions()) == 1
    assert store.holdings()[0].holding.market_value == 50


def test_account_history_snapshots_can_override_and_delete_trend_points(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account(
        {
            "type": "Investment",
            "location": "USA",
            "currency": "USD",
            "initial_cash": 1000,
            "username": "Eyal",
            "account_id": "A1",
            "management_company": "Broker",
        }
    )

    saved = store.save_account_snapshot(
        {
            "account_id": account["id"],
            "snapshot_date": "2026-02-01",
            "value": 1234,
            "cash": 100,
            "profit": 44,
            "profit_percent": 3.7,
        }
    )
    assert saved["value"] == 1234
    assert store.status()["snapshots"] == 1

    trends = store.account_trends({"account_id": account["id"], "from": "2026-02-01", "to": "2026-02-01"})
    assert trends["accounts"][0]["points"][0]["value"] == 1234
    assert trends["accounts"][0]["points"][0]["saved"] is True

    assert store.delete_account_snapshot(account["id"], "2026-02-01") is True
    trends = store.account_trends({"account_id": account["id"], "from": "2026-02-01", "to": "2026-02-01"})
    assert trends["accounts"][0]["points"][0]["value"] == 1000


def test_import_updates_source_account_cash(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    holdings = [
        Holding(
            symbol="ABC",
            asset_class="EQUITY",
            data_source="NASDAQ",
            currency="USD",
            quantity=2,
            cost_basis=20,
            market_value=30,
            account="Broker Main",
        )
    ]

    result = store.import_ghostfolio(holdings, [{"account": "Broker Main", "currency": "USD", "cash": 123.45}])
    accounts = store.list_accounts()

    assert result["accounts"] == 1
    assert result["account_cash_updated"] == 1
    assert accounts[0]["initial_cash"] == 123.45

    store.import_ghostfolio(holdings, [{"account": "Broker Main", "currency": "USD", "cash": 500}])
    assert store.list_accounts()[0]["initial_cash"] == 500


def test_source_order_import_preserves_historic_trend_dates(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    holdings = [
        Holding(
            symbol="ABC",
            asset_class="EQUITY",
            data_source="YAHOO",
            currency="USD",
            quantity=2,
            cost_basis=20,
            market_value=30,
            account="Broker Main",
        )
    ]

    result = store.import_ghostfolio(
        holdings,
        [{"account": "Broker Main", "currency": "USD", "cash": 100}],
        [
            {
                "account": "Broker Main",
                "account_currency": "USD",
                "platform": "Broker",
                "action": "ADD",
                "symbol": "ABC",
                "stock_market": "YAHOO",
                "asset_class": "EQUITY",
                "quantity": 2,
                "price": 10,
                "currency": "USD",
                "location": "USA",
                "trade_date": "2026-04-07",
            }
        ],
    )
    transactions = store.list_transactions()
    trends = store.account_trends({"from": "2026-04-14", "to": "2026-04-14"})

    assert result["source_transactions"] == 1
    assert transactions[0]["trade_date"] == "2026-04-07"
    assert trends["accounts"][0]["points"][0]["date"] == "2026-04-14"
    assert trends["accounts"][0]["points"][0]["value"] == 120


def test_source_manual_instrument_import_keeps_profile_name(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    holdings = [
        Holding(
            symbol="5136924",
            asset_class="MUTUALFUND",
            data_source="MANUAL",
            currency="ILS",
            quantity=10,
            cost_basis=100,
            market_value=120,
            account="Broker Main",
        )
    ]

    store.import_ghostfolio(
        holdings,
        [{"account": "Broker Main", "currency": "ILS", "cash": 0}],
        [
            {
                "account": "Broker Main",
                "account_currency": "ILS",
                "action": "ADD",
                "symbol": "5136924",
                "name": "IL_Ayalon_Caspit_Dollar",
                "stock_market": "MANUAL",
                "asset_class": "MUTUALFUND",
                "asset_sub_class": "MUTUALFUND",
                "quantity": 10,
                "price": 10,
                "currency": "ILS",
                "location": "Israel",
                "trade_date": "2026-04-07",
            }
        ],
    )

    analysis = store.holdings()[0]

    assert analysis.holding.name == "IL_Ayalon_Caspit_Dollar"
    assert store.manual_security("5136924", "MANUAL")["name"] == "IL_Ayalon_Caspit_Dollar"


def test_account_trends_align_accounts_for_total_aggregation(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account_a = store.save_account({"type": "Investment", "location": "USA", "currency": "USD", "initial_cash": 10, "username": "A"})
    account_b = store.save_account({"type": "Investment", "location": "USA", "currency": "USD", "initial_cash": 20, "username": "B"})
    store.add_transaction(
        {
            "account_db_id": account_a["id"],
            "action": "ADD",
            "symbol": "AAA",
            "stock_market": "YAHOO",
            "asset_class": "EQUITY",
            "quantity": 1,
            "price_input": 100,
            "trade_date": "2026-04-07",
            "allow_manual": True,
        }
    )
    store.add_transaction(
        {
            "account_db_id": account_b["id"],
            "action": "ADD",
            "symbol": "BBB",
            "stock_market": "YAHOO",
            "asset_class": "EQUITY",
            "quantity": 1,
            "price_input": 200,
            "trade_date": "2026-04-07",
            "allow_manual": True,
        }
    )
    store.save_price({"symbol": "AAA", "stock_market": "YAHOO", "price_input": 110, "price_date": "2026-04-15"})

    trends = store.account_trends({"from": "2026-04-14", "to": "2026-04-16"})
    dates_by_account = [[point["date"] for point in item["points"]] for item in trends["accounts"]]

    assert dates_by_account == [
        ["2026-04-14", "2026-04-15", "2026-04-16"],
        ["2026-04-14", "2026-04-15", "2026-04-16"],
    ]


def test_export_import_and_backup_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account(
        {
            "type": "Investment",
            "location": "USA",
            "currency": "USD",
            "initial_cash": 250,
            "username": "Eyal",
            "account_id": "A1",
            "management_company": "Broker",
        }
    )
    store.save_account_snapshot({"account_id": account["id"], "snapshot_date": "2026-03-01", "value": 300, "cash": 250})
    store.set_preference(
        "client_state",
        {
            "dashboard": {"mode": "expanded", "widgets": [{"id": "asset_mix", "view": "basic", "order": 0}]},
            "table": {"maPeriod": "15"},
            "language": "he",
            "pensionSimulation": {"scenarios": [{"name": "Retire"}]},
        },
    )

    exported = store.export_data()
    backup = store.write_backup()

    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    result = restored.import_data(exported)

    assert exported["counts"]["accounts"] == 1
    assert exported["counts"]["app_preferences"] == 1
    assert result["imported"]["account_snapshots"] == 1
    assert result["imported"]["app_preferences"] == 1
    assert restored.list_accounts()[0]["initial_cash"] == 250
    assert restored.list_account_snapshots()[0]["value"] == 300
    assert restored.get_preference("client_state")["table"]["maPeriod"] == "15"
    assert restored.get_preference("client_state")["pensionSimulation"]["scenarios"][0]["name"] == "Retire"
    assert backup["filename"].startswith("portfolio-data-")
    assert store.list_backups()[0]["filename"] == backup["filename"]


def test_manual_security_metadata_normalizes_id_and_attaches_to_transactions(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account(
        {
            "type": "Investment",
            "location": "USA",
            "currency": "USD",
            "initial_cash": 5000,
            "username": "Eyal",
            "account_id": "A1",
            "management_company": "Broker",
        }
    )
    saved = store.save_manual_security(
        {
            "symbol": "GF_5136924",
            "name": "Covered call",
            "stock_market": "MANUAL",
            "instrument_type": "OPTION",
            "option_type": "CALL",
            "underlying_symbol": "CSCO",
            "expiration_date": "2026-09-18",
            "strike_price": 50,
            "currency": "USD",
            "location": "USA",
        }
    )
    store.add_transaction(
        {
            "account_db_id": account["id"],
            "action": "BUY",
            "symbol": "GF_5136924",
            "stock_market": "MANUAL",
            "quantity": 1,
            "price_input": 2.5,
            "trade_date": "2026-07-30",
        }
    )
    store.save_price(
        {
            "symbol": "GF_5136924",
            "stock_market": "MANUAL",
            "price_input": 3.25,
            "price_date": "2026-07-30",
        }
    )

    tx = store.list_transactions()[0]
    holding = store.holdings()[0].holding

    assert saved["symbol"] == "5136924"
    assert tx["symbol"] == "5136924"
    assert tx["instrument_type"] == "OPTION"
    assert tx["option_type"] == "CALL"
    assert tx["expiration_date"] == "2026-09-18"
    assert holding.symbol == "5136924"
    assert holding.name == "Covered call"
    assert holding.asset_class == "OPTION"
    assert holding.asset_sub_class == "OPTION"
    assert holding.data_source == "MANUAL"
    assert holding.market_value == 3.25


def test_esop_account_supports_rsu_and_stock_options(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account(
        {
            "type": "ESOP",
            "location": "USA",
            "currency": "USD",
            "username": "Equity Plan",
            "account_id": "ESOP-1",
            "management_company": "Employer",
        }
    )
    rsu = store.save_manual_security(
        {
            "symbol": "AAPL-RSU",
            "name": "Apple RSU grant",
            "stock_market": "ESOP",
            "instrument_type": "RSU",
            "currency": "USD",
            "location": "USA",
        }
    )
    option = store.save_manual_security(
        {
            "symbol": "AAPL-OPT-50",
            "name": "Apple stock option grant",
            "stock_market": "ESOP",
            "instrument_type": "STOCK_OPTION",
            "underlying_symbol": "AAPL",
            "option_type": "CALL",
            "expiration_date": "31/12/2030",
            "strike_price": 50,
            "currency": "USD",
            "location": "USA",
        }
    )
    store.add_transaction(
        {
            "account_db_id": account["id"],
            "action": "ADD",
            "symbol": "AAPL-RSU",
            "stock_market": "ESOP",
            "quantity": 10,
            "price_input": 0,
            "vest_date": "31/07/2026",
            "purchase_price": 0,
            "trade_date": "31/07/2026",
        }
    )
    store.add_transaction(
        {
            "account_db_id": account["id"],
            "action": "ADD",
            "symbol": "AAPL-OPT-50",
            "stock_market": "ESOP",
            "quantity": 5,
            "price_input": 130,
            "trade_date": "31/07/2026",
        }
    )

    holdings = {item.holding.symbol: item.holding for item in store.holdings()}

    assert account["type"] == "ESOP"
    assert rsu["asset_class"] == "RSU"
    assert option["asset_class"] == "STOCK_OPTION"
    assert option["contract_multiplier"] == 100
    assert holdings["AAPL-RSU"].account_type == "ESOP"
    assert holdings["AAPL-RSU"].asset_class == "RSU"
    assert holdings["AAPL-OPT-50"].asset_class == "STOCK_OPTION"
    assert holdings["AAPL-OPT-50"].asset_sub_class == "STOCK_OPTION"
    tx = {item["symbol"]: item for item in store.list_transactions()}
    assert tx["AAPL-RSU"]["vest_date"] == "2026-07-31"
    assert tx["AAPL-RSU"]["purchase_price"] == 0
    assert tx["AAPL-OPT-50"]["strike_price"] == 50


def test_free_option_transaction_requires_strike_price(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "ESOP", "location": "USA", "currency": "USD", "username": "Equity Plan"})
    payload = {
        "account_db_id": account["id"],
        "action": "ADD",
        "symbol": "CSCO-OPT",
        "stock_market": "ESOP",
        "asset_class": "STOCK_OPTION",
        "quantity": 100,
        "price_input": 0,
        "trade_date": "31/07/2026",
    }
    try:
        store.add_transaction(payload)
    except ValueError as exc:
        assert "Strike price" in str(exc)
    else:
        raise AssertionError("Stock option transaction should require strike price")

    saved = store.add_transaction({**payload, "strike_price": 42.5, "vest_date": "31/07/2026", "purchase_price": 42.5})
    assert saved["strike_price"] == 42.5
    assert saved["vest_date"] == "2026-07-31"
    assert saved["purchase_price"] == 42.5


def test_manual_securities_round_trip_in_export(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    store.save_manual_security(
        {
            "symbol": "GF_5136924",
            "name": "Manual bond",
            "stock_market": "MANUAL",
            "instrument_type": "BOND",
            "currency": "ILS",
            "location": "Israel",
        }
    )
    exported = store.export_data()
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    restored.import_data(exported)

    assert exported["counts"]["manual_securities"] == 1
    assert restored.list_manual_securities()[0]["symbol"] == "5136924"
    assert restored.list_manual_securities()[0]["instrument_type"] == "BOND"


def test_import_price_history_stores_source_prices_without_renormalizing(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    result = store.import_price_history(
        [
            {
                "symbol": "TRIN",
                "stock_market": "YAHOO",
                "asset_class": "EQUITY",
                "location": "USA",
                "currency": "USD",
                "price": 17.41,
                "price_date": "2026-07-28",
            },
            {
                "symbol": "TRIN",
                "stock_market": "YAHOO",
                "asset_class": "EQUITY",
                "location": "USA",
                "currency": "USD",
                "price": 17.57,
                "price_date": "2026-07-30",
            },
        ]
    )
    rows = store.price_history("TRIN", "YAHOO")

    assert result["prices"] == 2
    assert [row["price_date"] for row in rows] == ["2026-07-28", "2026-07-30"]
    assert rows[0]["price"] == 17.41
    assert rows[0]["price_input"] == 17.41


def test_delete_history_before_prunes_old_price_and_account_history(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "Investment", "location": "USA", "currency": "USD", "username": "A"})
    store.import_price_history(
        [
            {"symbol": "TRIN", "stock_market": "YAHOO", "asset_class": "EQUITY", "location": "USA", "currency": "USD", "price": 1, "price_date": "2026-06-14"},
            {"symbol": "TRIN", "stock_market": "YAHOO", "asset_class": "EQUITY", "location": "USA", "currency": "USD", "price": 2, "price_date": "2026-06-15"},
        ]
    )
    store.save_account_snapshot({"account_id": account["id"], "snapshot_date": "2026-06-14", "value": 1})
    store.save_account_snapshot({"account_id": account["id"], "snapshot_date": "2026-06-15", "value": 2})

    result = store.delete_history_before("2026-06-15")

    assert result == {"prices": 1, "account_snapshots": 1}
    assert [row["price_date"] for row in store.price_history("TRIN", "YAHOO")] == ["2026-06-15"]
    assert [row["snapshot_date"] for row in store.list_account_snapshots()] == ["2026-06-15"]


def test_pension_monthly_estimate_defaults_to_factor_200(tmp_path):
    assert monthly_pension(100000) == 500
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    fund = store.save_fund({"kind": "Pension", "fund_name": "Migdal Pension", "pension_id": "P1", "amount": 100000, "comments": "main"})
    assert fund["fund_name"] == "Migdal Pension"
    assert fund["monthly_estimate"] == 500
    assert store.list_funds()[0]["monthly_estimate"] == 500


def test_non_pension_funds_do_not_have_monthly_estimates(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    provident = store.save_fund({"kind": "Provident Fund", "fund_name": "Provident", "pension_id": "G1", "amount": 199441})
    savings = store.save_fund({"kind": "Savings Fund", "fund_name": "Savings", "pension_id": "S1", "amount": 9605})

    assert provident["monthly_estimate"] is None
    assert savings["monthly_estimate"] is None
    assert [fund["monthly_estimate"] for fund in store.list_funds()] == [None, None]
    assert store.reports()["funds"]["monthly_estimate"] == 0


def test_fund_can_link_to_long_term_account(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "Long-Term Savings", "location": "Israel", "currency": "ILS", "username": "Metav"})

    fund = store.save_fund({"kind": "Pension", "pension_id": "P1", "amount": 100000, "account_id": account["id"]})

    assert fund["account_id"] == account["id"]
    assert "Metav" in fund["account_label"]
    assert fund["account"]["type"] == "Long-Term Savings"


def test_fund_rejects_non_long_term_account_link(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "Investment", "location": "USA", "currency": "USD", "username": "Broker"})

    try:
        store.save_fund({"kind": "Pension", "pension_id": "P1", "amount": 100000, "account_id": account["id"]})
    except ValueError as exc:
        assert "Long-Term Savings" in str(exc)
    else:
        raise AssertionError("Fund should not link to a non-long-term account")


def test_hebrew_text_persists_for_accounts_funds_and_securities(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    account = store.save_account(
        {
            "type": "Long-Term Savings",
            "location": "Israel",
            "currency": "ILS",
            "username": "אייל",
            "account_id": "חשבון-1",
            "management_company": "מיטב",
            "comments": "חשבון לטווח ארוך",
        }
    )
    fund = store.save_fund(
        {
            "kind": "Pension",
            "fund_name": "קרן פנסיה משלימה",
            "pension_id": "פנסיה-123",
            "amount": 100000,
            "account_id": account["id"],
            "comments": "הערת פנסיה",
        }
    )
    security = store.save_manual_security(
        {
            "symbol": "5136924",
            "stock_market": "MANUAL",
            "instrument_type": "MUTUALFUND",
            "name": "איילון כספית דולר",
            "location": "Israel",
            "currency": "ILS",
            "comments": "שם נייר בעברית",
        }
    )

    assert account["username"] == "אייל"
    assert account["account_id"] == "חשבון-1"
    assert account["management_company"] == "מיטב"
    assert account["comments"] == "חשבון לטווח ארוך"
    assert fund["fund_name"] == "קרן פנסיה משלימה"
    assert fund["pension_id"] == "פנסיה-123"
    assert fund["comments"] == "הערת פנסיה"
    assert "מיטב" in fund["account_label"]
    assert security["name"] == "איילון כספית דולר"
    assert security["comments"] == "שם נייר בעברית"


def test_fund_requires_id_and_saved_amount(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    for payload in [
        {"kind": "Pension", "amount": 100000},
        {"kind": "Pension", "pension_id": "P1", "amount": 0},
    ]:
        try:
            store.save_fund(payload)
        except ValueError as exc:
            assert "required" in str(exc)
        else:
            raise AssertionError("Invalid fund should not be saved")


def test_fund_name_export_import_round_trip(tmp_path):
    source = LocalPortfolioStore(tmp_path / "source.sqlite3")
    source.save_fund({"kind": "Provident Fund", "fund_name": "Altshuler", "pension_id": "G1", "amount": 2000})

    target = LocalPortfolioStore(tmp_path / "target.sqlite3")
    target.import_data(source.export_data())

    fund = target.list_funds()[0]
    assert fund["fund_name"] == "Altshuler"
    assert fund["pension_id"] == "G1"
    assert fund["amount"] == 2000


def test_fund_amount_history_crud_updates_current_saved_amount(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    fund = store.save_fund(
        {
            "kind": "Provident Fund",
            "fund_name": "Progress Fund",
            "pension_id": "G-HISTORY",
            "amount": 100000,
            "amount_date": "2026-01-01",
        }
    )

    opening = store.list_fund_amount_history(fund["id"])
    assert [(item["amount_date"], item["amount"]) for item in opening] == [("2026-01-01", 100000)]

    added = store.save_fund_amount_history(
        fund["id"],
        {"amount_date": "2026-03-01", "amount": 125000, "comments": "Quarterly update"},
    )
    assert store.list_funds()[0]["amount"] == 125000
    assert store.list_funds()[0]["history_change"] == 25000
    assert store.list_funds()[0]["history_change_percent"] == 25

    updated = store.save_fund_amount_history(
        fund["id"],
        {"amount_date": "2026-04-01", "amount": 130000, "comments": "Corrected"},
        added["id"],
    )
    assert updated["amount_date"] == "2026-04-01"
    assert updated["amount"] == 130000
    assert store.list_funds()[0]["amount"] == 130000

    assert store.delete_fund_amount_history(fund["id"], updated["id"]) is True
    assert store.list_funds()[0]["amount"] == 100000
    assert [item["amount_date"] for item in store.list_fund_amount_history(fund["id"])] == ["2026-01-01"]


def test_fund_amount_history_rejects_duplicate_dates_and_survives_export(tmp_path):
    source = LocalPortfolioStore(tmp_path / "source.sqlite3")
    fund = source.save_fund({"kind": "Savings Fund", "pension_id": "S-HISTORY", "amount": 5000, "amount_date": "2026-01-01"})
    source.save_fund_amount_history(fund["id"], {"amount_date": "2026-02-01", "amount": 5500})

    with pytest.raises(ValueError, match="already exists"):
        source.save_fund_amount_history(fund["id"], {"amount_date": "2026-02-01", "amount": 5600})

    target = LocalPortfolioStore(tmp_path / "target.sqlite3")
    target.import_data(source.export_data())

    restored = target.list_funds()[0]
    assert restored["amount"] == 5500
    assert restored["history_points"] == 2
    assert [(item["amount_date"], item["amount"]) for item in target.list_fund_amount_history(restored["id"])] == [
        ("2026-01-01", 5000),
        ("2026-02-01", 5500),
    ]


def test_pension_simulation_uses_income_percent_and_factor(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    result = store.simulate_pension(
        {
            "scenarios": [
                {
                    "name": "Base",
                    "kind": "Pension",
                    "current_age": 40,
                    "retire_age": 41,
                    "amount": 1000,
                    "annual_return": 0,
                    "monthly_income": 10000,
                    "contribution_percent": 10,
                    "return_periods": [{"from_age": 40, "to_age": 41, "annual_return": 0}],
                    "factor": 200,
                }
            ]
        }
    )["results"][0]

    assert result["total_deposits"] == 12000
    assert result["final_amount"] == 13000
    assert result["monthly_pension"] == 65


def test_pension_simulation_adds_extra_deposit_to_salary_contribution(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    result = store.simulate_pension(
        {
            "scenarios": [
                {
                    "name": "Salary plus extra",
                    "kind": "Pension",
                    "current_age": 40,
                    "retire_age": 41,
                    "amount": 0,
                    "annual_return": 0,
                    "monthly_income": 10000,
                    "contribution_percent": 10,
                    "monthly_deposit": 250,
                    "return_periods": [{"from_age": 40, "to_age": 41, "annual_return": 0}],
                    "factor": 200,
                }
            ]
        }
    )["results"][0]

    assert result["timeline"][0]["monthly_deposit"] == 1250
    assert result["total_deposits"] == 15000
    assert result["final_amount"] == 15000
    assert result["monthly_pension"] == 75


def test_pension_simulation_deducts_insurance_from_pension_deposit(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    result = store.simulate_pension(
        {
            "scenarios": [
                {
                    "name": "Insurance",
                    "kind": "Pension",
                    "gender": "Male",
                    "current_age": 34,
                    "retire_age": 34 + 1 / 12,
                    "amount": 0,
                    "return_periods": [{"from_age": 34, "to_age": 35, "annual_return": 0}],
                    "income_periods": [
                        {
                            "from_age": 34,
                            "to_age": 35,
                            "monthly_income": 10000,
                            "contribution_percent": 10,
                            "disability_coverage_percent": 75,
                            "spouse_survivors_coverage_percent": 60,
                            "children_survivors_coverage_percent": 40,
                            "survivors_capitalization_factor": 200,
                        }
                    ],
                    "factor": 200,
                }
            ]
        }
    )["results"][0]

    assert round(result["total_gross_deposits"], 2) == 1000
    assert round(result["total_insurance_cost"], 2) == 30.63
    assert round(result["total_deposits"], 2) == 969.37
    assert round(result["final_amount"], 2) == 969.37
    assert round(result["timeline"][0]["insurance_cost"], 2) == 30.63


def test_pension_survivors_insurance_uses_savings_balance_offset(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    result = store.simulate_pension(
        {
            "scenarios": [
                {
                    "name": "Savings offset",
                    "kind": "Pension",
                    "gender": "Female",
                    "current_age": 34,
                    "retire_age": 34 + 1 / 12,
                    "amount": 3_000_000,
                    "return_periods": [{"from_age": 34, "to_age": 35, "annual_return": 0}],
                    "income_periods": [
                        {
                            "from_age": 34,
                            "to_age": 35,
                            "monthly_income": 10000,
                            "contribution_percent": 10,
                            "spouse_survivors_coverage_percent": 60,
                            "children_survivors_coverage_percent": 40,
                            "survivors_capitalization_factor": 200,
                        }
                    ],
                    "factor": 200,
                }
            ]
        }
    )["results"][0]

    assert result["total_insurance_cost"] == 0
    assert result["total_deposits"] == 1000
    assert result["final_amount"] == 3_001_000


def test_pension_insurance_requires_gender(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    try:
        store.simulate_pension(
            {
                "name": "Missing gender",
                "kind": "Pension",
                "current_age": 34,
                "retire_age": 35,
                "amount": 0,
                "return_periods": [{"from_age": 34, "to_age": 35, "annual_return": 0}],
                "income_periods": [
                    {
                        "from_age": 34,
                        "to_age": 35,
                        "monthly_income": 10000,
                        "contribution_percent": 10,
                        "disability_coverage_percent": 75,
                    }
                ],
            }
        )
    except ValueError as exc:
        assert "Gender is required" in str(exc)
    else:
        raise AssertionError("Pension insurance cost should require gender")


def test_pension_simulation_supports_return_periods(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    result = store.simulate_pension(
        {
            "scenarios": [
                {
                    "name": "Rate steps",
                    "kind": "Pension",
                    "current_age": 40,
                    "retire_age": 42,
                    "amount": 1000,
                    "return_periods": [
                        {"from_age": 40, "to_age": 41, "annual_return": 12},
                        {"from_age": 41, "to_age": 42, "annual_return": 0},
                    ],
                    "factor": 200,
                }
            ]
        }
    )["results"][0]

    assert result["return_periods"][0]["annual_return"] == 12
    assert round(result["final_amount"], 2) == 1120
    assert round(result["monthly_pension"], 2) == 5.6
    assert result["timeline"][0]["annual_return"] == 12
    assert result["timeline"][-1]["annual_return"] == 0


def test_pension_simulation_rejects_missing_profit_rate_schedule(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    try:
        store.simulate_pension(
            {
                "name": "Missing rate",
                "kind": "Pension",
                "current_age": 40,
                "retire_age": 41,
                "amount": 1000,
                "factor": 200,
            }
        )
    except ValueError as exc:
        assert "Profit rate schedule is required" in str(exc)
    else:
        raise AssertionError("Missing profit rate schedule should be rejected")


def test_pension_simulation_rejects_invalid_profit_rate_rows(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    invalid_payloads = [
        (
            {"from_age": 41, "to_age": 40, "annual_return": 5},
            "valid from/to ages",
        ),
        (
            {"from_age": 40, "to_age": 41},
            "Annual profit is required",
        ),
        (
            {"from_age": 40, "to_age": 41, "annual_return": "bad"},
            "Annual profit must be numeric",
        ),
    ]
    for row, message in invalid_payloads:
        try:
            store.simulate_pension(
                {
                    "name": "Bad rate",
                    "kind": "Pension",
                    "current_age": 40,
                    "retire_age": 41,
                    "amount": 1000,
                    "return_periods": [row],
                    "factor": 200,
                }
            )
        except ValueError as exc:
            assert message in str(exc)
        else:
            raise AssertionError("Invalid profit rate row should be rejected")


def test_pension_simulation_infers_current_age_from_birth_date(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    current_age = age_from_birth_date("31/07/1990")

    result = store.simulate_pension(
        {
            "scenarios": [
                {
                    "name": "Birth date",
                    "kind": "Pension",
                    "birth_date": "31/07/1990",
                    "retire_age": current_age + 1,
                    "amount": 1000,
                    "annual_return": 0,
                    "monthly_deposit": 100,
                    "return_periods": [{"from_age": current_age, "to_age": current_age + 1, "annual_return": 0}],
                    "factor": 200,
                }
            ]
        }
    )["results"][0]

    assert result["current_age"] == current_age
    assert result["total_deposits"] == 1200
    assert result["final_amount"] == 2200


def test_non_pension_simulation_has_no_factor_or_monthly_pension(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    result = store.simulate_pension(
        {
            "scenarios": [
                {
                    "name": "Provident",
                    "kind": "Provident Fund",
                    "current_age": 40,
                    "retire_age": 41,
                    "amount": 1000,
                    "annual_return": 0,
                    "return_periods": [{"from_age": 40, "to_age": 41, "annual_return": 0}],
                    "factor": 200,
                }
            ]
        }
    )["results"][0]

    assert result["factor"] is None
    assert result["monthly_pension"] is None


def test_pension_simulation_supports_income_periods(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    result = store.simulate_pension(
        {
            "name": "Step income",
            "kind": "Savings Fund",
            "current_age": 30,
            "retire_age": 31,
            "annual_return": 0,
            "return_periods": [{"from_age": 30, "to_age": 31, "annual_return": 0}],
            "income_periods": [
                {"from_age": 30, "to_age": 30.5, "monthly_income": 10000, "contribution_percent": 10},
                {"from_age": 30.5, "to_age": 31, "monthly_deposit": 1500},
            ],
        }
    )["results"][0]

    assert result["total_deposits"] == 15000
    assert result["final_amount"] == 15000
    assert result["monthly_pension"] is None


def test_dates_accept_display_format(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    member = store.save_family_member({"first_name": "Dana", "last_name": "Levi", "gender": "Female", "birth_date": "31/07/1990", "retire_age": 66})
    account = store.save_account(
        {
            "type": "Investment",
            "location": "USA",
            "currency": "USD",
            "username": "A",
            "persons": [member],
        }
    )
    tx = store.add_transaction(
        {
            "account_db_id": account["id"],
            "symbol": "AAA",
            "stock_market": "YAHOO",
            "quantity": 1,
            "price_input": 10,
            "trade_date": "31/07/2026",
        }
    )
    price = store.save_price({"symbol": "AAA", "stock_market": "YAHOO", "price_input": 12, "price_date": "30/07/2026"})

    assert member["birth_date"] == "1990-07-31"
    assert member["name"] == "Dana Levi"
    assert member["first_name"] == "Dana"
    assert member["last_name"] == "Levi"
    assert account["persons"][0]["birth_date"] == "1990-07-31"
    assert tx["trade_date"] == "2026-07-31"
    assert price["price_date"] == "2026-07-30"


def test_family_member_cannot_be_deleted_when_attached_to_account(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    member = store.save_family_member({"name": "Dana Levi", "birth_date": "31/07/1990"})
    store.save_account({"type": "Investment", "location": "USA", "currency": "USD", "persons": [member]})

    try:
        store.delete_family_member(member["id"])
    except ValueError as exc:
        assert "attached" in str(exc)
    else:
        raise AssertionError("Attached family member should not be deleted")

    saved = store.list_family_members()[0]
    assert saved["attached_accounts"] == 1
    assert saved["attached_account_items"][0]["type"] == "Investment"


def test_family_member_update_and_multiple_account_members(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    dana = store.save_family_member({"name": "Dana Katz", "birth_date": "31/07/1990"})
    ron = store.save_family_member({"first_name": "Ron", "last_name": "Cohen", "birth_date": "01/08/1988"})

    updated = store.save_family_member({"id": dana["id"], "first_name": "Dana", "last_name": "Katz", "gender": "Female", "birth_date": "31/07/1990", "retire_age": 66})
    account = store.save_account({"type": "Investment", "location": "USA", "currency": "USD", "persons": [updated, ron]})

    assert updated["id"] == dana["id"]
    assert updated["name"] == "Dana Katz"
    assert updated["first_name"] == "Dana"
    assert updated["last_name"] == "Katz"
    assert updated["retire_age"] == 66
    assert [person["name"] for person in account["persons"]] == ["Dana Katz", "Ron Cohen"]
    assert store.list_family_members()[0]["attached_accounts"] + store.list_family_members()[1]["attached_accounts"] == 2


def test_existing_family_member_names_are_split_on_migration(tmp_path):
    path = tmp_path / "local.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            create table family_members (
                id text primary key,
                name text not null,
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
            insert into family_members (id, name, gender, birth_date, retire_age, comments, created_at)
            values ('member-1', 'Eyal Tuzon', 'Male', '1980-02-18', 67, '', '2026-07-31T00:00:00Z')
            """
        )

    store = LocalPortfolioStore(path)
    member = store.list_family_members()[0]

    assert member["name"] == "Eyal Tuzon"
    assert member["first_name"] == "Eyal"
    assert member["last_name"] == "Tuzon"


def test_broker_crud_and_delete_guard(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    broker = store.save_broker({"name": "IBKR", "country": "USA", "currency": "USD", "comments": "Global broker"})

    assert broker["name"] == "IBKR"
    assert broker["country"] == "USA"
    assert broker["currency"] == "USD"
    assert broker["attached_accounts"] == 0

    updated = store.save_broker({"id": broker["id"], "name": "IBKR", "country": "Israel", "currency": "ILS"})
    assert updated["id"] == broker["id"]
    assert updated["country"] == "Israel"
    assert updated["currency"] == "ILS"

    store.save_account({"type": "Investment", "location": "Israel", "currency": "ILS", "management_company": "IBKR"})
    renamed = store.save_broker({"id": broker["id"], "name": "IBKR Israel", "country": "Israel", "currency": "ILS"})
    assert renamed["attached_accounts"] == 1
    assert store.list_accounts()[0]["management_company"] == "IBKR Israel"

    saved = store.list_brokers()[0]
    assert saved["attached_accounts"] == 1

    try:
        store.delete_broker(broker["id"])
    except ValueError as exc:
        assert "attached" in str(exc)
    else:
        raise AssertionError("Attached broker should not be deleted")


def test_existing_account_brokers_seed_broker_list(tmp_path):
    path = tmp_path / "local.sqlite3"
    store = LocalPortfolioStore(path)
    store.save_account({"type": "Investment", "location": "Israel", "currency": "ILS", "management_company": "Psagot"})

    migrated = LocalPortfolioStore(path)
    brokers = migrated.list_brokers()

    assert len(brokers) == 1
    assert brokers[0]["name"] == "Psagot"
    assert brokers[0]["country"] == "Israel"
    assert brokers[0]["currency"] == "ILS"
    assert brokers[0]["attached_accounts"] == 1


def test_broker_export_import_round_trip(tmp_path):
    source = LocalPortfolioStore(tmp_path / "source.sqlite3")
    source.save_broker({"name": "Leumi Trade", "country": "Israel", "currency": "ILS"})
    data = source.export_data()

    target = LocalPortfolioStore(tmp_path / "target.sqlite3")
    target.import_data(data)

    brokers = target.list_brokers()
    assert len(brokers) == 1
    assert brokers[0]["name"] == "Leumi Trade"
    assert brokers[0]["country"] == "Israel"
    assert brokers[0]["currency"] == "ILS"


def test_company_report_predictions_round_trip_and_scorecard(tmp_path):
    source = LocalPortfolioStore(tmp_path / "source.sqlite3")
    prediction = source.save_company_report_prediction(
        {
            "symbol": "ACME",
            "company_name": "Acme Networks",
            "industry": "Networking",
            "score": 72,
            "label": "Good",
            "direction": "positive",
            "confidence": "Medium",
            "baseline": {"target": {"fiscal_date": "2026-12-31", "revenue_growth_percent": 20}},
            "thesis": "Revenue growth is above the peer median.",
            "mermaid": "flowchart LR\n  T --> I",
        }
    )
    evaluated = source.evaluate_company_report_prediction(
        prediction["id"],
        {"fiscal_date": "2027-12-31", "revenue_growth_percent": 12},
        "positive",
        100,
        "Revenue and margin improved.",
    )

    assert evaluated["accuracy_score"] == 100
    assert source.company_report_scorecard()["accuracy_percent"] == 100
    assert source.company_report_scorecard()["quality_gate"]["passed"] is False
    assert source.company_report_scorecard()["by_industry"] == [{"name": "Networking", "evaluated": 1, "accuracy_percent": 100.0}]
    assert source.company_report_scorecard()["by_model_version"] == [{"name": "report-outlook-v1", "evaluated": 1, "accuracy_percent": 100.0}]
    assert source.company_report_scorecard()["by_confidence"] == [{"name": "Medium", "evaluated": 1, "accuracy_percent": 100.0}]
    assert source.company_report_scorecard()["by_predicted_direction"] == [{"name": "positive", "evaluated": 1, "accuracy_percent": 100.0}]

    target = LocalPortfolioStore(tmp_path / "target.sqlite3")
    target.import_data(source.export_data())
    restored = target.list_company_report_predictions("ACME")

    assert len(restored) == 1
    assert restored[0]["baseline"]["target"]["fiscal_date"] == "2026-12-31"
    assert restored[0]["actual_direction"] == "positive"


def test_pending_company_prediction_remains_unevaluated_after_import(tmp_path):
    source = LocalPortfolioStore(tmp_path / "source.sqlite3")
    source.save_company_report_prediction({"symbol": "ACME", "score": 55, "direction": "neutral", "confidence": "Low"})

    target = LocalPortfolioStore(tmp_path / "target.sqlite3")
    target.import_data(source.export_data())

    restored = target.list_company_report_predictions("ACME")[0]
    assert restored["actual_direction"] == "pending"
    assert restored["accuracy_score"] is None
    assert target.company_report_scorecard()["evaluated"] == 0


def test_company_report_prediction_can_be_deleted(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    first = store.save_company_report_prediction({"symbol": "ACME", "score": 55, "direction": "neutral", "confidence": "Low"})
    store.save_company_report_prediction({"symbol": "OTHER", "score": 65, "direction": "positive", "confidence": "Medium"})

    deleted = store.delete_company_report_prediction(first["id"])

    assert deleted["id"] == first["id"]
    assert deleted["symbol"] == "ACME"
    assert [item["symbol"] for item in store.list_company_report_predictions()] == ["OTHER"]
    assert store.company_report_scorecard()["total"] == 1
    with pytest.raises(ValueError, match="Prediction not found"):
        store.delete_company_report_prediction(first["id"])


def test_company_report_prediction_can_be_found_by_batch_and_symbol(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    saved = store.save_company_report_prediction(
        {
            "symbol": "ACME",
            "score": 55,
            "direction": "neutral",
            "confidence": "Low",
            "baseline": {"batch": {"id": "calibration-001", "number": 1, "phase": "calibration"}},
        }
    )

    found = store.company_report_prediction_for_batch("calibration-001", "acme")

    assert found is not None
    assert found["id"] == saved["id"]
    assert store.company_report_prediction_for_batch("calibration-001", "OTHER") is None


def test_company_report_scorecard_excludes_duplicate_batch_symbol_records(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    payload = {
        "symbol": "ACME",
        "score": 55,
        "direction": "neutral",
        "confidence": "Low",
        "baseline": {"batch": {"id": "calibration-001"}},
    }
    first = store.save_company_report_prediction({**payload, "id": "first", "created_at": "2024-01-01T00:00:00Z"})
    second = store.save_company_report_prediction({**payload, "id": "second", "created_at": "2024-01-02T00:00:00Z"})
    store.evaluate_company_report_prediction(first["id"], {}, "neutral", 100, "First run")
    store.evaluate_company_report_prediction(second["id"], {}, "negative", 0, "Duplicate retry")

    scorecard = store.company_report_scorecard()

    assert scorecard["total"] == 1
    assert scorecard["stored_total"] == 2
    assert scorecard["duplicate_batch_records"] == 1
    assert scorecard["accuracy_percent"] == 0


def _save_private_employee_option(store):
    return store.save_manual_security(
        {
            "company_name": "Private Labs",
            "name": "Private Labs 2024 option grant",
            "listing_status": "PRIVATE",
            "instrument_type": "EMPLOYEE_STOCK_OPTION",
            "grant_id": "GRANT-2024",
            "grant_date": "01/01/2024",
            "vesting_start_date": "01/01/2024",
            "expiration_date": "01/01/2034",
            "strike_price": 2.5,
            "currency": "USD",
            "location": "USA",
        }
    )


def test_private_employee_option_uses_issuer_identity_without_public_market(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    saved = _save_private_employee_option(store)

    assert saved["instrument_type"] == "EMPLOYEE_STOCK_OPTION"
    assert saved["asset_class"] == "EMPLOYEE_STOCK_OPTION"
    assert saved["symbol"].startswith("ESO-")
    assert saved["stock_market"] == "PRIVATE"
    assert saved["listing_status"] == "PRIVATE"
    assert saved["public_symbol"] == ""
    assert saved["public_market"] == ""
    assert saved["company_name"] == "Private Labs"
    assert saved["grant_date"] == "2024-01-01"
    assert saved["vesting_start_date"] == "2024-01-01"
    assert saved["contract_multiplier"] == 1


def test_employee_option_currency_is_limited_to_ils_usd_and_eur(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    def grant(currency, location):
        return store.save_manual_security(
            {
                "company_name": f"{currency} Options Ltd",
                "listing_status": "PRIVATE",
                "instrument_type": "EMPLOYEE_STOCK_OPTION",
                "grant_date": "01/01/2026",
                "vesting_start_date": "01/01/2026",
                "expiration_date": "01/01/2036",
                "strike_price": 1,
                "currency": currency,
                "location": location,
            }
        )

    assert grant("ILS", "Israel")["currency"] == "ILS"
    assert grant("USD", "USA")["currency"] == "USD"
    assert grant("EUR", "France")["currency"] == "EUR"
    with pytest.raises(ValueError, match="currency must be ILS, USD, or EUR"):
        grant("GBP", "United Kingdom")


def test_employee_option_grants_for_same_company_share_issuer_lifecycle(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    first = _save_private_employee_option(store)
    second = store.save_manual_security(
        {
            "company_name": "Private Labs",
            "listing_status": "PRIVATE",
            "instrument_type": "EMPLOYEE_STOCK_OPTION",
            "grant_id": "GRANT-2025",
            "grant_date": "01/01/2025",
            "vesting_start_date": "01/01/2025",
            "expiration_date": "01/01/2035",
            "strike_price": 3.5,
            "currency": "USD",
            "location": "USA",
        }
    )

    assert second["id"] != first["id"]
    assert second["issuer_id"] == first["issuer_id"]

    store.link_employee_option_listing(
        second["id"],
        {"public_symbol": "PLAB", "public_market": "NASDAQ", "listing_date": "01/06/2026"},
    )
    grants = [item for item in store.list_manual_securities() if item["instrument_type"] == "EMPLOYEE_STOCK_OPTION"]
    assert {item["public_symbol"] for item in grants} == {"PLAB"}
    assert {item["listing_status"] for item in grants} == {"PUBLIC"}

    later_grant = store.save_manual_security(
        {
            "company_name": "Private Labs",
            "listing_status": "PRIVATE",
            "instrument_type": "EMPLOYEE_STOCK_OPTION",
            "grant_id": "GRANT-2027",
            "grant_date": "01/01/2027",
            "vesting_start_date": "01/01/2027",
            "expiration_date": "01/01/2037",
            "strike_price": 7,
            "currency": "USD",
            "location": "USA",
        }
    )
    assert later_grant["listing_status"] == "PUBLIC"
    assert later_grant["public_symbol"] == "PLAB"


def test_employee_option_percentage_schedule_is_saved_as_one_transaction(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "ESOP", "location": "USA", "currency": "USD", "username": "Equity Plan"})
    option = _save_private_employee_option(store)

    saved = store.add_transaction(
        {
            "account_db_id": account["id"],
            "action": "ADD",
            "security_id": option["id"],
            "quantity": 4000,
            "price_input": 0,
            "trade_date": "08/08/2026",
            "vesting_schedule": {
                "enabled": True,
                "mode": "PERCENT",
                "vesting_start_date": "01/01/2024",
                "duration_months": 48,
                "cliff_months": 12,
                "cliff_value": 25,
                "interval_months": 3,
                "installment_value": 6.25,
            },
        }
    )

    transactions = store.list_transactions()
    schedule = transactions[0]["vesting_schedule"]
    assert len(transactions) == 1
    assert saved["vesting_schedule"]["enabled"] is True
    assert schedule["mode"] == "PERCENT"
    assert len(schedule["tranches"]) == 13
    assert schedule["tranches"][0] == {
        "sequence": 1,
        "vest_date": "2025-01-01",
        "quantity": 1000.0,
        "cumulative_quantity": 1000.0,
        "cumulative_percent": 25.0,
    }
    assert schedule["tranches"][-1]["vest_date"] == "2028-01-01"
    assert schedule["tranches"][-1]["cumulative_quantity"] == 4000
    assert sum(item["quantity"] for item in schedule["tranches"]) == 4000


def test_employee_option_grant_wizard_crud_is_atomic(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "ESOP", "location": "Israel", "currency": "ILS", "username": "Options"})
    payload = {
        "grant": {
            "company_name": "Wizard Labs",
            "listing_status": "PRIVATE",
            "grant_id": "W-2026",
            "grant_date": "14/05/2026",
            "vesting_start_date": "14/05/2026",
            "expiration_date": "14/05/2036",
            "strike_price": 45.46,
            "currency": "ILS",
            "location": "Israel",
        },
        "vesting": {
            "account_db_id": account["id"],
            "quantity": 4000,
            "vesting_schedule": {
                "enabled": True,
                "mode": "PERCENT",
                "vesting_start_date": "14/05/2026",
                "duration_months": 48,
                "cliff_months": 12,
                "cliff_value": 25,
                "interval_months": 3,
                "installment_value": 6.25,
            },
        },
    }

    created = store.save_employee_option_grant(payload)
    security_id = created["security"]["id"]
    transaction_id = created["transaction"]["id"]
    assert created["transaction"]["vesting_schedule"]["tranches"][0]["vest_date"] == "2027-05-14"
    assert created["transaction"]["vesting_schedule"]["tranches"][-1]["vest_date"] == "2030-05-14"
    assert created["can_edit"] is True
    assert len(store.list_manual_securities()) == 1
    assert len(store.list_transactions()) == 1

    updated = store.save_employee_option_grant(
        {
            **payload,
            "security_id": security_id,
            "transaction_id": transaction_id,
            "grant": {**payload["grant"], "id": security_id, "strike_price": 50},
            "vesting": {
                **payload["vesting"],
                "id": transaction_id,
                "quantity": 2000,
                "vesting_schedule": {
                    **payload["vesting"]["vesting_schedule"],
                    "cliff_value": 50,
                    "installment_value": 25,
                    "duration_months": 18,
                },
            },
        }
    )
    assert updated["security"]["strike_price"] == 50
    assert updated["transaction"]["quantity"] == 2000
    assert len(updated["transaction"]["vesting_schedule"]["tranches"]) == 3
    assert len(store.list_manual_securities()) == 1
    assert len(store.list_transactions()) == 1

    assert store.delete_employee_option_grant(security_id) is True
    assert store.list_manual_securities() == []
    assert store.list_transactions() == []


def test_employee_option_grant_wizard_rolls_back_an_invalid_schedule(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "ESOP", "location": "USA", "currency": "USD"})

    with pytest.raises(ValueError, match="cannot continue after"):
        store.save_employee_option_grant(
            {
                "grant": {
                    "company_name": "Rollback Labs",
                    "listing_status": "PRIVATE",
                    "grant_date": "01/01/2026",
                    "vesting_start_date": "01/01/2026",
                    "expiration_date": "01/06/2027",
                    "strike_price": 1,
                    "currency": "USD",
                    "location": "USA",
                },
                "vesting": {
                    "account_db_id": account["id"],
                    "quantity": 100,
                    "vesting_schedule": {
                        "enabled": True,
                        "mode": "PERCENT",
                        "duration_months": 48,
                        "cliff_months": 12,
                        "cliff_value": 25,
                        "interval_months": 3,
                        "installment_value": 6.25,
                    },
                },
            }
        )

    assert store.list_manual_securities() == []
    assert store.list_transactions() == []


def test_employee_option_absolute_schedule_and_under_vesting_validation(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "ESOP", "location": "USA", "currency": "USD", "username": "Equity Plan"})
    option = _save_private_employee_option(store)
    base = {
        "account_db_id": account["id"],
        "action": "ADD",
        "security_id": option["id"],
        "quantity": 4000,
        "price_input": 0,
        "trade_date": "08/08/2026",
    }

    with pytest.raises(ValueError, match="unvested"):
        store.add_transaction(
            {
                **base,
                "vesting_schedule": {
                    "enabled": True,
                    "mode": "ABSOLUTE",
                    "vesting_start_date": "01/01/2024",
                    "duration_months": 48,
                    "cliff_months": 12,
                    "cliff_value": 1000,
                    "interval_months": 3,
                    "installment_value": 100,
                },
            }
        )

    saved = store.add_transaction(
        {
            **base,
            "vesting_schedule": {
                "enabled": True,
                "mode": "ABSOLUTE",
                "vesting_start_date": "01/01/2024",
                "duration_months": 48,
                "cliff_months": 12,
                "cliff_value": 1000,
                "interval_months": 3,
                "installment_value": 250,
            },
        }
    )
    assert saved["vesting_schedule"]["mode"] == "ABSOLUTE"
    assert [item["quantity"] for item in saved["vesting_schedule"]["tranches"]] == [1000.0] + [250.0] * 12


def test_employee_option_transaction_requires_a_defined_grant(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "ESOP", "location": "USA", "currency": "USD"})

    with pytest.raises(ValueError, match="Define the employee stock option grant"):
        store.add_transaction(
            {
                "account_db_id": account["id"],
                "action": "ADD",
                "symbol": "PRIVATE-GRANT",
                "stock_market": "PRIVATE",
                "asset_class": "EMPLOYEE_STOCK_OPTION",
                "quantity": 100,
                "strike_price": 1,
                "vest_date": "01/01/2027",
            }
        )


def test_employee_option_listing_and_exercise_are_audited_and_atomic(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    account = store.save_account({"type": "ESOP", "location": "USA", "currency": "USD", "username": "Equity Plan"})
    option = _save_private_employee_option(store)
    store.add_transaction(
        {
            "account_db_id": account["id"],
            "action": "ADD",
            "security_id": option["id"],
            "quantity": 4000,
            "price_input": 0,
            "vesting_schedule": {
                "enabled": True,
                "mode": "PERCENT",
                "duration_months": 48,
                "cliff_months": 12,
                "cliff_value": 25,
                "interval_months": 3,
                "installment_value": 6.25,
            },
        }
    )

    with pytest.raises(ValueError, match="at most 1500 vested"):
        store.exercise_employee_option(
            option["id"],
            {"account_db_id": account["id"], "quantity": 1600, "exercise_date": "01/07/2025"},
        )
    assert len(store.list_transactions()) == 1
    assert all(item["instrument_type"] != "PRIVATE_STOCK" for item in store.list_manual_securities())

    private_exercise = store.exercise_employee_option(
        option["id"],
        {"account_db_id": account["id"], "quantity": 1000, "exercise_date": "01/07/2025", "share_cost_basis": 2.5},
    )
    assert private_exercise["target_security"]["instrument_type"] == "PRIVATE_STOCK"
    assert private_exercise["target_security"]["stock_market"] == "PRIVATE"

    listing = store.link_employee_option_listing(
        option["id"],
        {"public_symbol": "PLAB", "public_market": "NASDAQ", "listing_date": "01/06/2026"},
    )
    assert listing["security"]["instrument_type"] == "EMPLOYEE_STOCK_OPTION"
    assert listing["security"]["listing_status"] == "PUBLIC"
    assert listing["security"]["public_symbol"] == "PLAB"

    public_exercise = store.exercise_employee_option(
        option["id"],
        {"account_db_id": account["id"], "quantity": 250, "exercise_date": "01/08/2026", "share_cost_basis": 2.5},
    )
    assert public_exercise["target_security"]["instrument_type"] == "STOCK"
    assert public_exercise["target_security"]["symbol"] == "PLAB"
    assert public_exercise["target_security"]["stock_market"] == "NASDAQ"
    assert [item["transition_type"] for item in store.list_equity_transitions()] == ["EXERCISE", "LISTING_LINK", "EXERCISE"]
    lifecycle_transaction = next(item for item in store.list_transactions() if item["transition_id"])
    with pytest.raises(ValueError, match="read-only"):
        store.update_transaction(lifecycle_transaction["id"], {"quantity": 1})
    with pytest.raises(ValueError, match="read-only"):
        store.delete_transaction(lifecycle_transaction["id"])
    with pytest.raises(ValueError, match="lifecycle history"):
        store.delete_manual_security(option["id"])


def test_employee_option_schedule_round_trips_in_backup(tmp_path):
    source = LocalPortfolioStore(tmp_path / "source.sqlite3")
    account = source.save_account({"type": "ESOP", "location": "USA", "currency": "USD", "username": "Equity Plan"})
    option = _save_private_employee_option(source)
    source.add_transaction(
        {
            "account_db_id": account["id"],
            "action": "ADD",
            "security_id": option["id"],
            "quantity": 4000,
            "price_input": 0,
            "vesting_schedule": {
                "enabled": True,
                "mode": "PERCENT",
                "duration_months": 48,
                "cliff_months": 12,
                "cliff_value": 25,
                "interval_months": 3,
                "installment_value": 6.25,
            },
        }
    )

    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    restored.import_data(source.export_data())

    restored_option = restored.list_manual_securities()[0]
    restored_schedule = restored.list_transactions()[0]["vesting_schedule"]
    assert restored_option["grant_date"] == "2024-01-01"
    assert restored_option["vesting_start_date"] == "2024-01-01"
    assert restored_option["company_name"] == "Private Labs"
    assert restored_schedule["tranches"][-1]["cumulative_quantity"] == 4000
