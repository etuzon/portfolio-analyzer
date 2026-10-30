"""Behavioral contracts for deduplication, bounded refresh, and account isolation."""
from collections import Counter
from copy import deepcopy
from threading import Event, Thread
import time

from app.models import Holding, SymbolAnalysis, Trend
from app.portfolio_refresh import attach_market_analysis, refresh_positions


def analysis(symbol="FDUS", account="one", quantity=2, cost=40, market="NASDAQ", secondary=""):
    return SymbolAnalysis(
        Holding(symbol=symbol, stock_market=market, secondary_symbol=secondary, quantity=quantity,
                cost_basis=cost, market_value=quantity * 20, account_id=account, account=account,
                asset_class="EQUITY", data_source="LOCAL"),
        {"local": "ok"}, {"5y": {"current": 30, "state": "ok"}}, {}, {}, {},
        Trend(state="ok", current=200), Trend(state="ok", current=20),
        Trend(state="ok", current=2), Trend(state="ok", current=.02), "Banks", [],
    )


def test_duplicate_accounts_refresh_once_per_listing_and_keep_own_values():
    calls, events = [], []
    positions = [analysis(), analysis(account="two", quantity=7, cost=140),
                 analysis(market="TASE", account="three"), analysis(symbol="UNB")]

    def provider(holding, _hub):
        calls.append((holding.symbol, holding.stock_market))
        return analysis(holding.symbol, account="provider", quantity=999, cost=999, market=holding.stock_market)

    rows = refresh_positions(positions, None, provider, lambda *args: events.append(args), 1, deepcopy)
    assert Counter(calls) == Counter({("FDUS", "NASDAQ"): 1, ("FDUS", "TASE"): 1, ("UNB", "NASDAQ"): 1})
    assert [(row.holding.account_id, row.holding.quantity, row.holding.cost_basis, row.holding.market_value) for row in rows] == [
        (row.holding.account_id, row.holding.quantity, row.holding.cost_basis, row.holding.market_value) for row in positions]
    assert len([event for event in events if event[1] == "ready"]) == 3
    rows[0].profit_trend.current = 999
    assert rows[1].profit_trend.current == 20


def test_slow_security_cannot_hold_fast_security_or_batch_open_forever():
    release, events = Event(), []

    def provider(holding, _hub):
        if holding.symbol == "UNB":
            release.wait(2)
        return analysis(holding.symbol)

    started = time.monotonic()
    try:
        rows = refresh_positions([analysis(), analysis("UNB")], None, provider,
                                 lambda *args: events.append(args), .1, deepcopy)
    finally:
        release.set()
    assert time.monotonic() - started < .7
    states = {event[0]: event[1] for event in events}
    assert sorted(states.values()) == ["failed", "ready"]
    assert all(row.profit_trend.current == 20 for row in rows)
    terminal = [event for event in events if event[1] in {"ready", "failed"}]
    time.sleep(.02)
    assert len([event for event in events if event[1] in {"ready", "failed"}]) == len(terminal) == 2


def test_failed_security_keeps_saved_values_and_retry_can_succeed():
    events = []

    def fail(*_args):
        raise ConnectionError("Synthetic provider failure")

    rows = refresh_positions([analysis()], None, fail, lambda *args: events.append(args), 1, deepcopy)
    assert events[-1][1] == "failed"
    assert rows[0].profit_trend.current == 20
    events.clear()
    refresh_positions([analysis()], None, lambda *_args: analysis(), lambda *args: events.append(args), 1, deepcopy)
    assert events[-1][1] == "ready"


def test_secondary_short_preserves_existing_profit_convention():
    result = attach_market_analysis(analysis(quantity=-2, cost=40, secondary="FDUS"), analysis(secondary="FDUS"))
    assert result.holding.market_value == -60
    assert result.holding.unrealized_profit == -20


def test_retry_reuses_running_request_and_keeps_new_account_quantities():
    release, started, calls, output = Event(), Event(), [], []
    hub = object()
    def provider(holding, _hub):
        calls.append(holding.symbol)
        started.set()
        release.wait(2)
        return analysis()
    refresh_positions([analysis()], hub, provider, lambda *_args: None, .05, deepcopy)
    assert started.is_set()
    retry = Thread(target=lambda: output.extend(refresh_positions(
        [analysis(quantity=7, cost=140)], hub, provider, lambda *_args: None, 1, deepcopy)))
    retry.start()
    try:
        time.sleep(.02)
        assert calls == ["FDUS"]
    finally:
        release.set()
        retry.join(2)
    assert not retry.is_alive()
    assert output[0].holding.quantity == 7
    assert output[0].holding.cost_basis == 140
