"""Account history/report valuation follows dated evidence without rewriting it."""
from copy import deepcopy
from dataclasses import asdict
from datetime import date, timedelta
import asyncio
import time

import pytest

from app import main
from app.local_portfolio import LocalPortfolioStore


TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture
def valued_account(tmp_path):
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite")
    account = store.save_account({"type": "Investment", "location": "USA", "currency": "USD",
                                  "username": "Synthetic Owner", "initial_cash": 1000,
                                  "persons": [{"name": "Synthetic Owner", "birth_date": "01/01/1990"}]})
    store.add_transaction({"account_db_id": account["id"], "action": "BUY", "symbol": "QA",
                           "stock_market": "NYSE", "asset_class": "EQUITY", "currency": "USD",
                           "quantity": 10, "price_input": 40, "allow_manual": True,
                           "trade_date": (TODAY - timedelta(days=3)).isoformat()})
    store.save_price({"symbol": "QA", "stock_market": "NYSE", "asset_class": "EQUITY",
                      "location": "USA", "currency": "USD", "price_input": 50,
                      "price_date": YESTERDAY.isoformat()})
    items = [{"holding": asdict(store.holdings()[0].holding),
              "price_ranges": {"5y": {"state": "ok", "current": 30, "current_date": TODAY.isoformat()}}}]
    return store, account, items


def points(store, account, items):
    result = store.account_trends({"account_id": account["id"], "from": YESTERDAY.isoformat(),
                                   "to": TODAY.isoformat()}, valuation_items=items)
    return {p["date"]: p for p in result["accounts"][0]["points"]}


def test_dated_provider_valuation_reconciles_current_report_and_daily_history_without_rewrite(valued_account):
    store, account, items = valued_account
    store.capture_daily_snapshots(YESTERDAY)
    store.capture_daily_snapshots(TODAY)
    before = store.export_data()["data"]
    history = points(store, account, items)
    assert history[YESTERDAY.isoformat()]["value"] == 1100  # no lookahead
    assert history[TODAY.isoformat()]["value"] == 900  # 600 cash + 10*30
    assert history[TODAY.isoformat()]["profit"] == -100
    assert history[TODAY.isoformat()]["profit_percent"] == -25
    assert history[TODAY.isoformat()]["cash"] == 600
    assert history[TODAY.isoformat()]["native_available"]
    report = store.reports({"account_id": account["id"]}, valuation_items=items)
    assert (report["value"], report["profit"], report["securities_value"]) == (900, -100, 300)
    assert report["account_details"][0]["value"] == 900
    saved = store.list_account_snapshots({"account_id": account["id"]}, valuation_items=items)
    assert saved[0]["value"] == 900 and saved[0]["recomputed"]
    assert store.export_data()["data"] == before


def test_edit_delete_and_reload_local_quotes_recompute_daily_points(valued_account):
    store, account, _items = valued_account
    store.capture_daily_snapshots(YESTERDAY)
    before = store.list_account_snapshots()
    quote = store.list_prices()[0]
    store.save_price({**quote, "price_input": 45})
    reopened = LocalPortfolioStore(store.path)
    assert points(reopened, account, [])[YESTERDAY.isoformat()]["value"] == 1050
    reopened.delete_price(quote["id"])
    assert points(reopened, account, [])[YESTERDAY.isoformat()]["value"] == 1000
    assert reopened.list_account_snapshots() == before


@pytest.mark.parametrize("source", ["manual", "external_import"])
def test_recorded_observations_survive_read_recomputation_and_daily_capture(valued_account, source):
    store, account, items = valued_account
    store.save_account_snapshot({"account_id": account["id"], "snapshot_date": TODAY.isoformat(),
                                 "value": 1234, "cash": 600, "profit": 234, "source": source})
    before = store.list_account_snapshots()
    assert points(store, account, items)[TODAY.isoformat()]["value"] == 1234
    assert store.reports(valuation_items=items)["value"] == 900
    assert store.capture_daily_snapshots(TODAY)["snapshots"] == 0
    assert store.list_account_snapshots(valuation_items=items) == before


@pytest.mark.parametrize("price,observed,expected", [
    (30, YESTERDAY, 900),  # provider wins same-date tie
    (30, YESTERDAY-timedelta(days=1), 1100),  # newer saved mark wins
    (0, TODAY, 600),
    (-1, TODAY, 1100),
    (float("nan"), TODAY, 1100),
    (float("inf"), TODAY, 1100),
    (30, TODAY+timedelta(days=1), 1100),
])
def test_quote_date_precedence_and_invalid_evidence(valued_account, price, observed, expected):
    store, account, items = valued_account
    items[0]["price_ranges"]["5y"].update(current=price, current_date=observed.isoformat())
    assert points(store, account, items)[TODAY.isoformat()]["value"] == expected
    assert store.reports(valuation_items=items)["value"] == expected


def test_api_report_trend_table_and_pdf_share_cached_dashboard_evidence(valued_account, monkeypatch):
    store, account, items = valued_account
    store.capture_daily_snapshots(TODAY)
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "_portfolio_refresh_in_progress", False)
    monkeypatch.setattr(main, "_portfolio_refresh_failure", None)
    monkeypatch.setattr(main, "_portfolio_cache", {"signature": main.portfolio_cache_signature(),
        "expires_at": time.time()+3600, "payload": {"items": items}})
    monkeypatch.setattr(main, "enriched_local_holdings", lambda **_kw: pytest.fail("warm read must not fetch providers"))
    before = deepcopy(store.export_data()["data"])
    assert main.local_reports(account_id=account["id"])["value"] == 900
    assert main.local_account_trends(account_id=account["id"], date_from=TODAY.isoformat())["accounts"][0]["points"][-1]["value"] == 900
    assert main.list_account_snapshots(account_id=account["id"], date_from=TODAY.isoformat())["items"][0]["value"] == 900
    view = main.local_report_view(account_id=account["id"], date_from=TODAY.isoformat())
    assert view["report"]["value"] == view["trend"]["accounts"][0]["points"][-1]["value"] == view["snapshots"]["items"][0]["value"] == 900
    captured = {}
    def pdf(report, trend, **_options):
        captured.update(report=report, trend=trend)
        return b"%PDF-1.7\nsynthetic"
    monkeypatch.setattr(main, "build_portfolio_report_pdf", pdf)
    main.local_reports_pdf(account_id=account["id"], date_from=TODAY.isoformat())
    assert captured["report"]["value"] == captured["trend"]["accounts"][0]["points"][-1]["value"] == 900
    assert store.export_data()["data"] == before


def test_live_read_retries_a_source_change_before_returning(valued_account, monkeypatch):
    store, account, items = valued_account
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "portfolio_payload", lambda **_kw: {"items": items})
    calls = []
    def reader(evidence):
        calls.append(1)
        result = store.reports(valuation_items=evidence)
        if len(calls) == 1:
            store.save_account({**account, "initial_cash": 1200})
        return result
    assert main._with_local_valuation(reader)["value"] == 1100
    assert len(calls) == 2


def test_legacy_current_aggregate_rebuilds_without_future_local_quote(valued_account, monkeypatch):
    store, account, items = valued_account
    store.save_price({"symbol": "QA", "stock_market": "NYSE", "asset_class": "EQUITY",
                      "location": "USA", "currency": "USD", "price_input": 500,
                      "price_date": (TODAY+timedelta(days=1)).isoformat()})
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "_portfolio_cache", {"signature": f"v10:{store.change_token()}",
        "expires_at": time.time()+3600, "payload": {"items": [{"holding": {"market_value": 5000}}]}})
    monkeypatch.setattr(main, "_portfolio_refresh_in_progress", False)
    monkeypatch.setattr(main, "_portfolio_refresh_failure", None)
    monkeypatch.setattr(main, "schedule_portfolio_refresh", lambda: False)
    monkeypatch.setattr(main, "_serialized_portfolio_payload", lambda rows, _status: {"items": [{"holding": asdict(row.holding)} for row in rows]})
    calls = []
    def local_only(**options):
        calls.append(options)
        return store.holdings()
    monkeypatch.setattr(main, "enriched_local_holdings", local_only)
    before = store.export_data()["data"]
    result = main.portfolio_payload(defer_enrichment=True)
    assert calls == [{"cached_only": True}]
    assert result["items"][0]["holding"]["market_value"] == 500
    assert store.reports()["value"] == 1100
    assert store.export_data()["data"] == before


def test_report_view_reads_market_evidence_once_and_retries_entire_bundle(valued_account, monkeypatch):
    store, account, items = valued_account
    store.capture_daily_snapshots(TODAY)
    monkeypatch.setattr(main, "local_store", store)
    payload_calls = []
    def payload(**_options):
        payload_calls.append(1)
        return {"items": items}
    monkeypatch.setattr(main, "portfolio_payload", payload)
    original = store.reports
    report_calls = []
    def reports(*args, **options):
        result = original(*args, **options)
        report_calls.append(1)
        if len(report_calls) == 1:
            store.save_account({**account, "initial_cash": 1200})
        return result
    monkeypatch.setattr(store, "reports", reports)
    view = main.local_report_view(account_id=account["id"], date_from=TODAY.isoformat())
    assert len(payload_calls) == len(report_calls) == 2
    assert view["report"]["value"] == view["trend"]["accounts"][0]["points"][-1]["value"] == view["snapshots"]["items"][0]["value"] == 1100


def test_authenticated_mcp_reports_accounts_and_trends_use_same_current_evidence(valued_account, tmp_path, monkeypatch):
    from test_mcp_server import _environment, _issue, _mcp_client
    from app.mcp_server import create_portfolio_mcp_server
    from fastapi import FastAPI
    store, account, items = valued_account
    _other_store, auth = _environment(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "local_store", store)
    evidence_calls = []
    def payload(**options):
        evidence_calls.append(options)
        return {"items": items}
    monkeypatch.setattr(main, "portfolio_payload", payload)
    auth.set_mcp_access_mode("read_only")
    token = _issue(auth)
    # A streamable HTTP manager has one lifetime. Use an isolated authenticated
    # server so this journey cannot consume the application's test lifetime.
    server = create_portfolio_mcp_server(lambda: auth, lambda: store, lambda: None, main._with_local_valuation)
    app = FastAPI()
    app.mount("/mcp", server.streamable_http_app(streamable_http_path="/", json_response=True, stateless_http=True))
    monkeypatch.setattr(main, "app", app)
    before = store.export_data()["data"]
    async def scenario():
        async with server.session_manager.run():
            async with _mcp_client(token) as client:
                accounts = await client.call_tool("list_portfolio_accounts", {"account_type": "Investment"})
                report = await client.call_tool("get_portfolio_report", {"account_id": account["id"]})
                trend = await client.call_tool("get_account_trends", {"account_id": account["id"],
                    "date_from": TODAY.strftime("%d/%m/%Y"), "date_to": TODAY.strftime("%d/%m/%Y")})
                empty = await client.call_tool("get_portfolio_report", {"account_type": "Bank"})
                assert not any(result.is_error for result in (accounts, report, trend, empty))
                assert accounts.structured_content["items"][0]["value"] == report.structured_content["value"] == trend.structured_content["accounts"][0]["points"][-1]["value"] == 900
                assert trend.structured_content["accounts"][0]["points"][-1]["date"] == TODAY.strftime("%d/%m/%Y")
                assert empty.structured_content["accounts"] == empty.structured_content["value"] == 0
    asyncio.run(scenario())
    assert evidence_calls == [{"defer_enrichment": True}]*4
    assert store.export_data()["data"] == before


def test_standalone_mcp_factory_keeps_local_only_default(valued_account, monkeypatch):
    from app import mcp_server
    store, account, _items = valued_account
    monkeypatch.setattr(mcp_server, "_mcp_user", lambda *_args, **_options: {"role": "Viewer"})
    server = mcp_server.create_portfolio_mcp_server(lambda: None, lambda: store, lambda: None)
    async def scenario():
        result = await server.call_tool("get_portfolio_report", {"account_id": account["id"]})
        assert not result.is_error
        assert result.structured_content["value"] == 1100
    asyncio.run(scenario())
