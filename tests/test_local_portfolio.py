from datetime import date

from app.local_portfolio import LocalPortfolioStore, monthly_pension, normalize_price
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

    exported = store.export_data()
    backup = store.write_backup()

    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    result = restored.import_data(exported)

    assert exported["counts"]["accounts"] == 1
    assert result["imported"]["account_snapshots"] == 1
    assert restored.list_accounts()[0]["initial_cash"] == 250
    assert restored.list_account_snapshots()[0]["value"] == 300
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
    fund = store.save_fund({"kind": "Pension", "pension_id": "P1", "amount": 100000, "comments": "main"})
    assert fund["monthly_estimate"] == 500
    assert store.list_funds()[0]["monthly_estimate"] == 500


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
                    "factor": 200,
                }
            ]
        }
    )["results"][0]

    assert result["total_deposits"] == 12000
    assert result["final_amount"] == 13000
    assert result["monthly_pension"] == 65


def test_pension_simulation_supports_income_periods(tmp_path):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")

    result = store.simulate_pension(
        {
            "name": "Step income",
            "kind": "Savings Fund",
            "current_age": 30,
            "retire_age": 31,
            "annual_return": 0,
            "income_periods": [
                {"from_age": 30, "to_age": 30.5, "monthly_income": 10000, "contribution_percent": 10},
                {"from_age": 30.5, "to_age": 31, "monthly_deposit": 1500},
            ],
        }
    )["results"][0]

    assert result["total_deposits"] == 15000
    assert result["final_amount"] == 15000
    assert result["monthly_pension"] is None
