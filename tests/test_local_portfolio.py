from datetime import date
import sqlite3

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
