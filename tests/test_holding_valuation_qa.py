"""Independent valuation regression oracle; synthetic listings and isolated stores."""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import time

import pytest

from app import main
from app.metrics import to_dict
from app.models import Holding, Ohlcv, SymbolAnalysis, Trend
from app.portfolio_refresh import attach_market_analysis, refresh_positions, security_key
from test_financial_loading import env


def quote(price=3.31, day=None):
    return {"state": "partial", "current": price,
            "current_date": (day or date.today()).isoformat()}


def position(quantity=900, basis=3843, price=4.22, day=None, **fields):
    holding = Holding(symbol="QA", stock_market="NASDAQ", data_source="LOCAL",
                      quantity=quantity, cost_basis=basis, market_value=quantity * price,
                      unrealized_profit=quantity * price - basis, realized_profit=57,
                      income_received=23, **fields)
    return SymbolAnalysis(holding, {}, {"5y": quote(price, day or date.today()-timedelta(days=2))},
                          {}, {}, {}, Trend(), Trend(), Trend(), Trend(), "", [])


def market(price=3.31, day=None):
    result = position(quantity=1, basis=1)
    result.price_ranges = {"5y": quote(price, day)}
    return result


def preserved(original, result):
    for field in ("quantity", "cost_basis", "realized_profit", "income_received",
                  "currency", "account_id", "symbol", "stock_market"):
        assert getattr(result.holding, field) == getattr(original.holding, field)


def test_raw_900_share_case_has_current_value_and_preserves_owned_evidence():
    local, provider = position(), market()
    before = deepcopy((local, provider))
    result = attach_market_analysis(local, provider)
    assert result.holding.market_value == pytest.approx(2979)
    assert result.holding.unrealized_profit == pytest.approx(-864)
    preserved(local, result)
    assert (local, provider) == before


@pytest.mark.parametrize("basis", [3843, -3843])
def test_short_value_and_profit_do_not_depend_on_legacy_basis_sign(basis):
    result = attach_market_analysis(position(quantity=-900, basis=basis), market())
    assert result.holding.market_value == pytest.approx(-2979)
    assert result.holding.unrealized_profit == pytest.approx(864)


def test_valid_zero_price_is_a_real_mark():
    result = attach_market_analysis(position(), market(0))
    assert result.holding.market_value == 0
    assert result.holding.unrealized_profit == -3843


@pytest.mark.parametrize("bad", [None, True, False, "3.31", -1, float("nan"), float("inf"), -float("inf")])
def test_bad_provider_prices_keep_latest_valid_local_evidence(bad):
    local = position()
    result = attach_market_analysis(local, market(bad))
    assert result.holding.market_value == local.holding.market_value
    assert result.holding.unrealized_profit == local.holding.unrealized_profit


@pytest.mark.parametrize("day", [None, "", "invalid", (date.today()+timedelta(days=1)).isoformat()])
def test_undated_malformed_and_future_provider_marks_are_ineligible(day):
    local, provider = position(), market()
    provider.price_ranges["5y"]["current_date"] = day
    result = attach_market_analysis(local, provider)
    assert result.holding.market_value == local.holding.market_value


def test_newer_saved_mark_wins_over_older_provider_mark():
    local = position(price=3.31, day=date.today())
    result = attach_market_analysis(local, market(4.22, date.today()-timedelta(days=1)))
    assert result.holding.market_value == pytest.approx(2979)
    assert result.price_ranges["5y"]["current"] == 3.31


def test_latest_eligible_available_range_is_used_when_five_year_range_is_missing():
    provider = market()
    provider.price_ranges = {"1m": quote(3.31), "5y": {"state":"missing"}}
    result = attach_market_analysis(position(), provider)
    assert result.holding.market_value == pytest.approx(2979)


@pytest.mark.parametrize("asset,currency,location", [
    ("EQUITY", "USD", "USA"), ("EQUITY", "ILS", "Israel"),
    ("BOND", "ILS", "Israel"), ("OPTION", "USD", "USA"),
])
def test_already_normalized_quote_is_multiplied_only_by_owned_quantity(asset,currency,location):
    local = position(currency=currency, location=location)
    local.holding.asset_class = asset
    result = attach_market_analysis(local, market())
    assert result.holding.market_value == pytest.approx(2979)
    preserved(local, result)


def test_primary_only_manual_position_remains_manually_valued():
    local = position()
    local.holding.data_source = "MANUAL"
    result = attach_market_analysis(local, market())
    assert result.holding.market_value == local.holding.market_value


def test_progress_overlay_values_each_account_using_its_own_quantity_and_basis(monkeypatch):
    first = position(account_id="one")
    second = position(quantity=100, basis=500, account_id="two")
    completed = to_dict(attach_market_analysis(first, market()))
    key = security_key(first.holding)
    monkeypatch.setattr(main, "_portfolio_refresh_progress", {
        "total":2,"completed":1,"failed":0,"states":{key:"ready"},"results":{key:completed}})
    payload = main._portfolio_loading_state({"items":[to_dict(first), to_dict(second)]}, "refreshing")
    assert payload["refresh_pending"] is True
    rows = payload["items"]
    assert rows[0]["holding"]["market_value"] == pytest.approx(2979)
    assert rows[1]["holding"]["market_value"] == pytest.approx(331)
    assert rows[1]["holding"]["unrealized_profit"] == pytest.approx(-169)
    assert rows[1]["holding"]["cost_basis"] == 500


def test_real_cached_first_load_revalues_without_rewriting_saved_evidence(env):
    transaction = env.add(qty=900)
    env.store.update_transaction(transaction["id"], {"price_input":4.27})
    env.store.save_price({"symbol":"FDUS","stock_market":"NASDAQ","asset_class":"EQUITY",
                          "location":"USA","currency":"USD","price_input":4.22,
                          "price_date":(date.today()-timedelta(days=1)).isoformat()})
    env.hub.cache.set_prices("yahoo_finance", "FDUS", [Ohlcv(date.today(),3.31,3.31,3.31,3.31,3.31,100)])
    sources = deepcopy((env.store.list_transactions(), env.store.list_prices(), env.store.list_accounts()))
    token = env.store.change_token()
    raw_cache = hashlib.sha256((env.tmp/"market.sqlite3").read_bytes()).digest()
    saved = env.store.holdings()[0].holding
    assert saved.market_value == pytest.approx(3798)
    assert saved.cost_basis == pytest.approx(3843)
    result = main.portfolio_payload(defer_enrichment=True)["items"][0]["holding"]
    assert result["market_value"] == pytest.approx(2979)
    assert result["unrealized_profit"] == pytest.approx(-864)
    assert result["quantity"] == 900
    assert result["cost_basis"] == pytest.approx(3843)
    assert env.calls == []
    assert (env.store.list_transactions(),env.store.list_prices(),env.store.list_accounts()) == sources
    assert env.store.change_token() == token
    assert hashlib.sha256((env.tmp/"market.sqlite3").read_bytes()).digest() == raw_cache


@pytest.mark.parametrize("mode", ["synchronous", "worker", "legacy_aggregate"])
def test_repricing_survives_refresh_modes_and_aggregate_reload(env, monkeypatch, mode):
    transaction = env.add(qty=900)
    env.store.update_transaction(transaction["id"], {"price_input":4.27})
    env.store.save_price({"symbol":"FDUS","stock_market":"NASDAQ","price_input":4.22,
                          "price_date":(date.today()-timedelta(days=1)).isoformat()})
    env.hub.cache.set_prices("yahoo_finance", "FDUS", [Ohlcv(date.today(),3.31,3.31,3.31,3.31,3.31,100)])
    sources = deepcopy((env.store.list_transactions(),env.store.list_prices(),env.store.list_accounts()))
    if mode == "synchronous":
        result = main.portfolio_payload(force_refresh=True)
    elif mode == "worker":
        main._refresh_portfolio_cache()
        result = main.portfolio_payload()
    else:
        old = {"items":[to_dict(env.store.holdings()[0])]}
        main.write_portfolio_cache({"signature":f"v9:{env.store.change_token()}",
                                    "expires_at":time.time()+3600,"payload":old})
        result = main.portfolio_payload(defer_enrichment=True)
    holding = result["items"][0]["holding"]
    assert holding["market_value"] == pytest.approx(2979)
    assert holding["unrealized_profit"] == pytest.approx(-864)
    assert (env.store.list_transactions(),env.store.list_prices(),env.store.list_accounts()) == sources
    if mode != "legacy_aggregate":
        monkeypatch.setattr(main,"_portfolio_cache",None)
        monkeypatch.setattr(main,"enriched_local_holdings",lambda **_kwargs:pytest.fail("valid aggregate reload rebuilt"))
        reloaded = main.portfolio_payload()["items"][0]["holding"]
        assert reloaded["market_value"] == pytest.approx(2979)
        assert reloaded["unrealized_profit"] == pytest.approx(-864)


def test_failed_provider_fallback_reprices_from_available_cache_and_retry_revalues_each_owner():
    positions = [position(account_id="one"), position(quantity=100,basis=500,account_id="two")]
    def fail(*_args):
        raise ConnectionError("synthetic offline")
    events = []
    failed = refresh_positions(positions,object(),fail,lambda *args:events.append(args),1,
                               lambda local:attach_market_analysis(local,market()))
    assert events[-1][1] == "failed"
    assert [row.holding.market_value for row in failed] == pytest.approx([2979,331])
    assert [row.holding.unrealized_profit for row in failed] == pytest.approx([-864,-169])
    retried = refresh_positions(positions,object(),lambda *_args:market(4),lambda *_args:None,1,deepcopy)
    assert [row.holding.market_value for row in retried] == [3600,400]
    assert [row.holding.unrealized_profit for row in retried] == [-243,-100]
