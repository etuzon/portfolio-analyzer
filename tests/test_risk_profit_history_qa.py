"""Independent prospective P&L history acceptance from synthetic raw money.

No developer-calculated profit or application risk engine is used as the oracle.
Tests use temporary stores only; runtime portfolio state is never read or reset.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from app import risk_history
from app.local_portfolio import LocalPortfolioStore


AS_OF = datetime(2026, 11, 14, 9, tzinfo=timezone.utc)


def qa_account(identifier="a", cash=1000, currency="USD", kind="Investment"):
    return dict(id=identifier, account_id=identifier, username=f"Synthetic {identifier}",
                type=kind, currency=currency, initial_cash=cash, location="USA")


def qa_transaction(identifier, action, amount, *, account="a", quantity=None,
                   price=None, day="2026-11-14", created="2026-11-14T10:00:00Z",
                   currency="USD", symbol="QA", source="local"):
    return dict(id=identifier, account_db_id=account, action=action,
                quantity=amount if quantity is None else quantity,
                price=1 if price is None else price,
                trade_date=day, created_at=created, currency=currency,
                symbol=symbol if action in {"BUY", "SELL", "SHORT", "ADD", "REMOVE"} else "",
                stock_market="QA", asset_class="EQUITY", source=source)


def qa_holding(value, *, account="a", quantity=10, currency="USD",
               day="2026-11-14", symbol="QA"):
    return dict(holding=dict(account_id=account, symbol=symbol, stock_market="QA",
                             asset_class="EQUITY", quantity=quantity,
                             market_value=value, currency=currency),
                stress_risk=dict(valuation_date=day, security_key=f"{symbol}|QA|{currency}"),
                quote=dict(date=day, price=value / quantity if quantity else 0))


def qa_inputs(accounts=None, items=None, transactions=None, fx=None, base="USD"):
    result = risk_history.canonical_inputs(items or [], accounts or [qa_account()],
                                         transactions or [], fx or {"quotes": []}, base)
    return {**result, "guard": ("synthetic-read-only-source", 1, "qa-risk-evidence")}


def qa_payload(context):
    # Risk is intentionally incomplete: observed-equity evidence is independent
    # of whether scenario-specific rating/issuer metadata is complete.
    risk = dict(model=risk_history.MODEL, **risk_history.SCORE_METADATA,
                status="incomplete", score=None, coverage={"complete": False})
    return dict(token=context["token"], total=deepcopy(risk),
                accounts=[dict(account_id=identifier, risk=deepcopy(risk))
                          for identifier in context["account_ids"]])


def qa_save(store, monkeypatch, inputs, when=AS_OF):
    monkeypatch.setattr(risk_history, "_now", lambda: when)
    capture = lambda _: deepcopy(inputs)
    context = risk_history.create_context(store, "qa-writer", inputs["base_currency"], capture)
    return risk_history.save_observation(store, "qa-writer", qa_payload(context),
                                         capture, lambda: inputs["guard"])["observation"]


def qa_history(store, account="", days=0, base="USD"):
    observations = risk_history.list_observations(store, base, days)["items"]
    return [row["performance"]["total"] if not account else next(
        item for item in row["performance"]["accounts"] if item["account_id"] == account)
            for row in observations]


def test_raw_v4_money_and_rounding_validator_keeps_small_and_uncapped_loss():
    """0/100 rounding neither erases a small loss nor bounds leveraged loss."""
    for raw_percent, expected_score in [(0.49, 0), (36.42, 36), (46.96, 47), (220, 100)]:
        record = dict(model=risk_history.MODEL, **risk_history.SCORE_METADATA,
                      score=expected_score, status="ok", net_equity=1000,
                      stress_loss=raw_percent * 10, loss_pct=raw_percent,
                      coverage={"complete": True})
        original = deepcopy(record)
        result = risk_history._stress_risk(record)
        assert result["score"] == expected_score
        assert result["stress_loss"] == pytest.approx(raw_percent * 10)
        assert result["loss_pct"] == raw_percent
        assert record == original


def test_server_equity_recorded_flows_total_and_accounts_survive_reload(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-money.sqlite")
    accounts = [qa_account("a", 400), qa_account("b", 2000)]
    beginning = qa_inputs(accounts, [qa_holding(600)])
    before = qa_save(store, monkeypatch, beginning)
    first = qa_history(store)[0]
    assert first["status"] == "baseline"
    assert first["profit"] is None
    assert first["currency"] == "USD"
    activity = [qa_transaction("deposit-a", "CASH_IN", 200, day="2026-11-15", created="2026-11-15T10:00:00Z"),
                qa_transaction("withdrawal-b", "CASH_OUT", 300, account="b", day="2026-11-15", created="2026-11-15T10:00:00Z"),
                qa_transaction("fee-b", "FEE", 10, account="b", day="2026-11-15", created="2026-11-15T10:00:00Z")]
    ending = qa_inputs(accounts, [qa_holding(680, day="2026-11-15")], activity)
    after = qa_save(store, monkeypatch, ending, AS_OF + timedelta(days=1, hours=2))
    original_before = deepcopy(before)
    reloaded = LocalPortfolioStore(store.path)
    for identifier, profit, beginning_equity, ending_equity, flows in [
        ("a", 80, 1000, 1280, 200), ("b", -10, 2000, 1690, -300),
        ("", 70, 3000, 2970, -100),
    ]:
        value = qa_history(reloaded, identifier)[-1]
        assert value["status"] == "recorded", value
        assert value["profit"] == pytest.approx(profit)
        assert value["beginning_equity"] == beginning_equity
        assert value["ending_equity"] == ending_equity
        assert value["recorded_net_flows"] == flows
        assert value["baseline_observation_id"] == before["id"]
        assert value["baseline_date"] == "2026-11-14"
    assert before == original_before
    # Neither browser-submitted risk equity nor UI values establish performance.
    assert after["total"]["score"] is None


@pytest.mark.parametrize("action,quantity,price,begin_cash,begin_value,end_cash,end_value,profit", [
    ("BUY", 10, 100, 1000, 0, 0, 1000, 0),
    ("SELL", 10, 106, 0, 1000, 1060, 0, 60),
    ("SHORT", 10, 100, 1000, 0, 2000, -1000, 0),
    ("DIVIDEND", 1, 20, 1000, 0, 1020, 0, 20),
    ("INTEREST", 1, 3, 1000, 0, 1003, 0, 3),
    ("FEE", 1, 5, 1000, 0, 995, 0, -5),
])
def test_closed_holdings_internal_trades_and_income_are_counted_once(
        tmp_path, monkeypatch, action, quantity, price, begin_cash, begin_value,
        end_cash, end_value, profit):
    store = LocalPortfolioStore(tmp_path / "qa-internal.sqlite")
    account = qa_account(cash=begin_cash)
    baseline_items = [qa_holding(begin_value)] if begin_value else []
    qa_save(store, monkeypatch, qa_inputs([account], baseline_items))
    tx = qa_transaction("new-activity", action, 0, quantity=quantity, price=price,
                        day="2026-11-15", created="2026-11-15T10:00:00Z")
    end_quantity = -quantity if action == "SHORT" else quantity
    ending_items = [qa_holding(end_value, quantity=end_quantity, day="2026-11-15")] if end_value else []
    qa_save(store, monkeypatch, qa_inputs([account], ending_items, [tx]), AS_OF + timedelta(days=1, hours=2))
    result = qa_history(store, "a")[-1]
    assert result["status"] == "recorded", result
    assert result["ending_equity"] == pytest.approx(end_cash + end_value)
    assert result["recorded_net_flows"] == 0
    assert result["profit"] == pytest.approx(profit)


@pytest.mark.parametrize("defect,expected_reason", [
    ("opening-cash", "opening_cash_changed"),
    ("ledger-edit", "ledger_revised"),
    ("ledger-delete", "ledger_revised"),
    ("retroactive", "retroactive_activity"),
    ("in-kind-add", "in_kind_flow_unvalued"),
    ("unreconciled-quantity", "positions_unreconciled"),
    ("unknown-same-day-time", "activity_timing_unknown"),
    ("unclassified-cash-adjustment", "unclassified_cash_adjustment"),
])
def test_corrections_and_unvalued_flows_produce_gap_instead_of_profit(
        tmp_path, monkeypatch, defect, expected_reason):
    store = LocalPortfolioStore(tmp_path / "qa-gap.sqlite")
    beginning_account = qa_account(cash=1000)
    ending_account = deepcopy(beginning_account)
    beginning_items, ending_items, initial_txs, ending_txs = [], [], [], []
    when = AS_OF + timedelta(days=1, hours=2)
    if defect == "opening-cash":
        ending_account["initial_cash"] = 1100
    elif defect in {"ledger-edit", "ledger-delete"}:
        initial_txs = [qa_transaction("old-income", "DIVIDEND", 5, day="2026-11-13", created="2026-11-13T10:00:00Z")]
        ending_txs = [] if defect == "ledger-delete" else [{**initial_txs[0], "quantity": 10}]
    elif defect == "retroactive":
        ending_txs = [qa_transaction("late-deposit", "CASH_IN", 100, day="2026-11-13", created="2026-11-15T10:00:00Z")]
    elif defect == "in-kind-add":
        ending_items = [qa_holding(100, day="2026-11-15")]
        ending_txs = [qa_transaction("in-kind", "ADD", 0, quantity=10, price=5, day="2026-11-15", created="2026-11-15T10:00:00Z")]
    elif defect == "unreconciled-quantity":
        beginning_items = [qa_holding(1000)]
        ending_items = [qa_holding(1100, quantity=11, day="2026-11-15")]
    elif defect == "unknown-same-day-time":
        ending_txs = [qa_transaction("same-day", "CASH_IN", 100, created="")]
        when = AS_OF + timedelta(hours=3)
    elif defect == "unclassified-cash-adjustment":
        ending_txs = [qa_transaction("cash-correction", "CASH_IN", 100, source="cash_adjustment", day="2026-11-15", created="2026-11-15T10:00:00Z")]
    qa_save(store, monkeypatch, qa_inputs([beginning_account], beginning_items, initial_txs))
    qa_save(store, monkeypatch, qa_inputs([ending_account], ending_items, ending_txs), when)
    for account in ("", "a"):
        result = qa_history(store, account)[-1]
        assert result["status"] == "unavailable", result
        assert result["profit"] is None
        assert expected_reason in result["reason_codes"]


def test_transfer_legs_are_adjusted_at_each_account_boundary_and_cancel_in_total(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-transfer.sqlite")
    accounts = [qa_account("a", 1280), qa_account("b", 1690)]
    qa_save(store, monkeypatch, qa_inputs(accounts))
    activity = [qa_transaction("transfer-a", "CASH_IN", 150, day="2026-11-15", created="2026-11-15T10:00:00Z"),
                qa_transaction("transfer-b", "CASH_OUT", 150, account="b", day="2026-11-15", created="2026-11-15T10:00:00Z")]
    qa_save(store, monkeypatch, qa_inputs(accounts, transactions=activity), AS_OF + timedelta(days=1, hours=2))
    for account, flows, equity in [("a", 150, 1430), ("b", -150, 1540), ("", 0, 2970)]:
        value = qa_history(store, account)[-1]
        assert value["status"] == "recorded", value
        assert value["recorded_net_flows"] == flows
        assert value["ending_equity"] == equity
        assert value["profit"] == 0


def test_registered_zero_account_stays_in_total_scope_and_new_scope_breaks_only_total(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-scope.sqlite")
    accounts = [qa_account("a", 1000), qa_account("zero", 0)]
    qa_save(store, monkeypatch, qa_inputs(accounts))
    qa_save(store, monkeypatch, qa_inputs(accounts + [qa_account("new", 200)]), AS_OF + timedelta(days=1))
    total = qa_history(store)[-1]
    assert total["status"] == "unavailable" and total["profit"] is None
    assert "scope_changed" in total["reason_codes"]
    unaffected = qa_history(store, "a")[-1]
    assert unaffected["status"] == "recorded" and unaffected["profit"] == 0


def test_account_disappearance_breaks_its_segment_while_unaffected_account_continues(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-disappearing-account.sqlite")
    a, b = qa_account("a", 1000), qa_account("b", 500)
    first = qa_save(store, monkeypatch, qa_inputs([a, b]))
    qa_save(store, monkeypatch, qa_inputs([b]), AS_OF + timedelta(days=1))
    qa_save(store, monkeypatch, qa_inputs([a, b]), AS_OF + timedelta(days=2))
    final = risk_history.list_observations(store, "USD", 0)["items"][-1]["performance"]
    affected = next(row for row in final["accounts"] if row["account_id"] == "a")
    unaffected = next(row for row in final["accounts"] if row["account_id"] == "b")
    assert affected["status"] in {"baseline", "unavailable"}, affected
    assert affected["profit"] is None
    assert affected.get("baseline_observation_id") != first["id"] or affected["status"] == "unavailable"
    assert unaffected["status"] == "recorded" and unaffected["profit"] == 0
    assert unaffected["baseline_observation_id"] == first["id"]


def test_unknown_opening_cash_and_stale_mark_do_not_become_zero_profit(tmp_path, monkeypatch):
    for defect in ("unknown-cash", "stale-mark"):
        store = LocalPortfolioStore(tmp_path / f"{defect}.sqlite")
        baseline = qa_inputs([qa_account(cash=1000)], [qa_holding(100)])
        qa_save(store, monkeypatch, baseline)
        ending = qa_inputs([qa_account(cash=None if defect == "unknown-cash" else 1000)],
                           [qa_holding(100, day="2026-11-01" if defect == "stale-mark" else "2026-11-15")])
        qa_save(store, monkeypatch, ending, AS_OF + timedelta(days=1))
        result = qa_history(store, "a")[-1]
        assert result["status"] == "unavailable", result
        assert result["profit"] is None
        assert result["reason_codes"]


def test_period_uses_first_eligible_saved_point_inside_period_without_backfill(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-period.sqlite")
    accounts = [qa_account()]
    first = qa_save(store, monkeypatch, qa_inputs(accounts))
    tx1 = qa_transaction("income-1", "DIVIDEND", 10, day="2026-11-15", created="2026-11-15T10:00:00Z")
    qa_save(store, monkeypatch, qa_inputs(accounts, transactions=[tx1]), AS_OF + timedelta(days=1, hours=2))
    tx2 = qa_transaction("income-2", "DIVIDEND", 20, day="2026-11-20", created="2026-11-20T10:00:00Z")
    last = qa_save(store, monkeypatch, qa_inputs(accounts, transactions=[tx1, tx2]), AS_OF + timedelta(days=6, hours=2))
    full = qa_history(store)[-1]
    assert full["status"] == "recorded" and full["profit"] == 30
    assert full["baseline_observation_id"] == first["id"]
    limited = qa_history(store, days=5)
    assert len(limited) == 1
    assert limited[0]["status"] == "baseline" and limited[0]["profit"] is None
    assert limited[0]["baseline_observation_id"] == last["id"]
    assert limited[0]["baseline_date"] == "2026-11-20"


def test_client_cannot_forge_observed_profit_or_equity_and_reads_do_not_rewrite_evidence(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-server-evidence.sqlite")
    inputs = qa_inputs([qa_account(cash=1000)])
    signature = store.change_token()
    monkeypatch.setattr(risk_history, "_now", lambda: AS_OF)
    capture = lambda _: deepcopy(inputs)
    context = risk_history.create_context(store, "qa-writer", "USD", capture)
    payload = {**qa_payload(context), "performance": {"profit": 999999, "total_equity": 999999},
               "performance_snapshot": {"total_equity": 999999}}
    saved = risk_history.save_observation(store, "qa-writer", payload, capture, lambda: inputs["guard"])["observation"]
    with store._connect() as connection:
        original = [tuple(row) for row in connection.execute(
            "select key,value,updated_at from app_preferences where key glob ? order by key", (risk_history.PREFIX + "*",)).fetchall()]
    assert store.change_token() == signature
    first = qa_history(store)[0]
    assert first["profit"] is None
    assert first.get("ending_equity") in (1000, None)
    qa_history(LocalPortfolioStore(store.path), "a")
    with store._connect() as connection:
        after = [tuple(row) for row in connection.execute(
            "select key,value,updated_at from app_preferences where key glob ? order by key", (risk_history.PREFIX + "*",)).fetchall()]
    assert after == original
    assert "999999" not in json.dumps(saved)


def test_invalid_intermediate_observation_cannot_be_erased_by_later_display_selection(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-segment.sqlite")
    first = qa_save(store, monkeypatch, qa_inputs([qa_account(cash=1000)]))
    qa_save(store, monkeypatch, qa_inputs([qa_account(cash=2000)]), AS_OF + timedelta(hours=2))
    qa_save(store, monkeypatch, qa_inputs([qa_account(cash=2100)]), AS_OF + timedelta(hours=3))
    records = qa_history(store)
    assert len(records) == 3
    assert records[1]["status"] == "unavailable"
    assert "opening_cash_changed" in records[1]["reason_codes"]
    # A later display representative must retain the break; it cannot claim
    # 1100 of investment profit by bridging the opening-balance corrections.
    assert records[-1]["profit"] is None
    assert records[-1]["status"] in {"baseline", "unavailable"}
    assert records[-1].get("baseline_observation_id") != first["id"] or records[-1]["status"] == "unavailable"


def qa_fx(rate, day, pair="USD/ILS"):
    return {"quotes": [{"pair": pair, "quote": {"rate": rate, "date": day},
                         "status": {"synthetic": "saved_evidence"}}]}


def test_foreign_flow_reuses_frozen_exact_day_fx_and_keeps_fx_revaluation_profit(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-flow-fx.sqlite")
    account = qa_account(cash=100, currency="USD")
    qa_save(store, monkeypatch, qa_inputs([account], fx=qa_fx(3, "2026-11-14"), base="ILS"))
    deposit = qa_transaction("foreign-deposit", "CASH_IN", 10, day="2026-11-15", created="2026-11-15T10:00:00Z")
    qa_save(store, monkeypatch, qa_inputs([account], transactions=[deposit],
            fx=qa_fx(3.2, "2026-11-15"), base="ILS"), AS_OF + timedelta(days=1, hours=2))
    qa_save(store, monkeypatch, qa_inputs([account], transactions=[deposit],
            fx=qa_fx(3.3, "2026-11-16"), base="ILS"), AS_OF + timedelta(days=2, hours=2))
    result = qa_history(store, "a", base="ILS")[-1]
    assert result["status"] == "recorded", result
    assert result["currency"] == "ILS"
    assert result["beginning_equity"] == 300
    assert result["ending_equity"] == 363
    assert result["recorded_net_flows"] == 32  # USD10 at the dated3.2 flow observation.
    assert result["profit"] == pytest.approx(31)  # 363-300-32, not30 using endpoint FX.


def test_missing_flow_day_fx_cannot_be_substituted_by_endpoint_rate(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-no-flow-fx.sqlite")
    account = qa_account(cash=100, currency="USD")
    qa_save(store, monkeypatch, qa_inputs([account], fx=qa_fx(3, "2026-11-14"), base="ILS"))
    deposit = qa_transaction("foreign-deposit", "CASH_IN", 10, day="2026-11-15", created="2026-11-15T10:00:00Z")
    qa_save(store, monkeypatch, qa_inputs([account], transactions=[deposit],
            fx=qa_fx(3.3, "2026-11-16"), base="ILS"), AS_OF + timedelta(days=2, hours=2))
    result = qa_history(store, "a", base="ILS")[-1]
    assert result["status"] == "unavailable" and result["profit"] is None
    assert "missing_flow_fx" in result["reason_codes"]


def test_later_discovered_flow_fx_never_backfills_an_older_unavailable_comparison(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-fx-no-lookahead.sqlite")
    account = qa_account(cash=100, currency="USD")
    qa_save(store, monkeypatch, qa_inputs([account], fx=qa_fx(3, "2026-11-14"), base="ILS"))
    deposit = qa_transaction("foreign-deposit", "CASH_IN", 10, day="2026-11-15", created="2026-11-15T10:00:00Z")
    qa_save(store, monkeypatch, qa_inputs([account], transactions=[deposit],
            fx=qa_fx(3.3, "2026-11-16"), base="ILS"), AS_OF + timedelta(days=2, hours=2))
    before = qa_history(store, "a", base="ILS")[-1]
    assert before["profit"] is None and "missing_flow_fx" in before["reason_codes"]
    qa_save(store, monkeypatch, qa_inputs([account], transactions=[deposit],
            fx=qa_fx(3.2, "2026-11-15"), base="ILS"), AS_OF + timedelta(days=3, hours=2))
    after = qa_history(store, "a", base="ILS")[-2]
    assert after == before


def test_registered_foreign_zero_account_requires_no_fx_when_it_has_no_exposure(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-foreign-zero.sqlite")
    accounts = [qa_account(cash=1000), qa_account("foreign-zero", 0, "JPY")]
    qa_save(store, monkeypatch, qa_inputs(accounts))
    activity = qa_transaction("income", "DIVIDEND", 10, day="2026-11-15", created="2026-11-15T10:00:00Z")
    qa_save(store, monkeypatch, qa_inputs(accounts, transactions=[activity]), AS_OF + timedelta(days=1, hours=2))
    value = qa_history(store)[-1]
    assert value["status"] == "recorded", value
    assert value["profit"] == 10


@pytest.mark.parametrize("opening,income", [(0, 10), (-100, 40)])
def test_money_profit_does_not_require_positive_beginning_equity(tmp_path, monkeypatch, opening, income):
    store = LocalPortfolioStore(tmp_path / "qa-nonpositive.sqlite")
    account = qa_account(cash=opening)
    qa_save(store, monkeypatch, qa_inputs([account]))
    activity = qa_transaction("earned-interest", "INTEREST", income,
                              day="2026-11-15", created="2026-11-15T10:00:00Z")
    qa_save(store, monkeypatch, qa_inputs([account], transactions=[activity]), AS_OF + timedelta(days=1, hours=2))
    result = qa_history(store, "a")[-1]
    assert result["status"] == "recorded", result
    assert result["profit"] == income
    assert "profit_percent" not in result


def test_explicit_reset_deletes_exact_risk_prefix_preserves_source_and_fences_persisted_epoch(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-reset.sqlite")
    monkeypatch.setattr(risk_history, "_contexts", {})
    monkeypatch.setattr(risk_history, "_now", lambda: AS_OF)
    preserved = {
        "manual-credit-ratings-v1:QA": {"rating": "AAA"},
        "credit-rating-history-v1:QA": [{"rating": "AA"}],
        "sovereign-credit-ratings-v1:US": {"rating": "AAA"},
        "security-country-v1:QA": {"country_code": "US"},
        "stress-risk-inputs-v1:QA": {"duration": 3},
        "risk_input_retrieval_schedule": {"enabled": False},
        "unrelated-user-preference": {"value": 42},
        "risk_history_v10:other-namespace": {"preserve": True},
        "riskXhistoryYv1:sql-like-wildcard-trap": {"preserve": True},
        "risk_history_v1-without-colon": {"preserve": True},
    }
    for key, value in preserved.items():
        store.set_preference(key, value)
    owner = store.save_account(dict(type="Investment", location="USA", currency="USD",
                                   username="Synthetic reset owner", initial_cash=1000,
                                   persons=[dict(name="Synthetic owner", birth_date="01/01/1990")]))
    store.add_transaction(dict(account_db_id=owner["id"], action="BUY", symbol="RESETQA",
                               stock_market="QA", asset_class="EQUITY", currency="USD",
                               quantity=1, price_input=10, trade_date="2026-11-13", allow_manual=True))
    store.save_price(dict(symbol="RESETQA", stock_market="QA", asset_class="EQUITY", currency="USD",
                          location="USA", price_input=12, price_date="2026-11-14"))
    inputs = qa_inputs()
    capture = lambda _: deepcopy(inputs)
    context = risk_history.create_context(store, "qa-writer", "USD", capture)
    pending = deepcopy(risk_history._contexts[context["token"]])
    risk_history.save_observation(store, "qa-writer", qa_payload(context), capture, lambda: inputs["guard"])
    store.set_preference(risk_history.PREFIX + "legacy-v2", {"model": "portfolio-risk-v2"})
    store.set_preference(risk_history.PREFIX + "legacy-v3", {"model": "portfolio-risk-v3"})
    with store._connect() as connection:
        connection.execute("insert into app_preferences(key,value,updated_at) values(?,?,?)",
                           (risk_history.PREFIX + "corrupt-json", "not-json", "2026-11-14T09:00:00Z"))
        source_before = {table: [tuple(row) for row in connection.execute(f"select * from {table} order by rowid").fetchall()]
                         for table in ("accounts", "transactions", "price_history")}
    signature = store.change_token()
    risk_history.reset_history(store, user_id="qa-writer")
    with store._connect() as connection:
        assert connection.execute("select count(*) from app_preferences where key glob ?", (risk_history.PREFIX + "*",)).fetchone()[0] == 0
        source_after = {table: [tuple(row) for row in connection.execute(f"select * from {table} order by rowid").fetchall()]
                        for table in ("accounts", "transactions", "price_history")}
    assert source_after == source_before
    assert {key: store.get_preference(key) for key in preserved} == preserved
    assert store.change_token() == signature
    # Reintroducing the old in-memory token simulates another process that did
    # not see the reset. Persisted epoch, not only local token cleanup, must win.
    risk_history._contexts[context["token"]] = pending
    with pytest.raises(risk_history.RiskHistoryError) as rejected:
        risk_history.save_observation(LocalPortfolioStore(store.path), "qa-writer", qa_payload(context),
                                      capture, lambda: inputs["guard"])
    assert rejected.value.status == 409
    assert risk_history.list_observations(store, "USD", 0)["items"] == []
    new = qa_save(store, monkeypatch, inputs, AS_OF + timedelta(minutes=1))
    reloaded = LocalPortfolioStore(store.path)
    saved = risk_history.list_observations(reloaded, "USD", 0)
    assert len(saved["items"]) == 1 and saved["items"][0]["id"] == new["id"]
    assert saved["items"][0]["performance"]["total"]["status"] == "baseline"


def test_reset_api_requires_admin_and_csrf_and_rejects_pre_reset_operator_context(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from app.auth import AuthStore

    store = LocalPortfolioStore(tmp_path / "qa-reset-permissions.sqlite")
    auth = AuthStore(store.path)
    auth.initialize()
    for name, role in [("qa-admin", "Admin"), ("qa-operator", "Operator"), ("qa-viewer", "Viewer")]:
        user = auth.create_user(dict(username=name, first_name="Synthetic", last_name=role,
                                     role=role, password="Synthetic-QA-Password!"))
        with auth._connect() as connection:
            connection.execute("update app_users set must_change_password=0 where id=?", (user["id"],))
    inputs = qa_inputs()
    monkeypatch.setattr(main, "auth_store", auth)
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "_risk_history_inputs", lambda _: deepcopy(inputs))
    monkeypatch.setattr(main, "_risk_history_guard", lambda: inputs["guard"])
    monkeypatch.setattr(main, "_risk_history_saved_fx", lambda *args: deepcopy(inputs["fx"]))
    main._login_failures.clear()
    client = TestClient(main.app, base_url="https://localhost:6443")
    assert client.delete("/api/portfolio/risk-history").status_code == 401
    saved_context = None
    for role in ("viewer", "operator"):
        session = client.post("/api/auth/login", json=dict(username=f"qa-{role}", password="Synthetic-QA-Password!")).json()
        response = client.delete("/api/portfolio/risk-history", headers={"X-CSRF-Token": session["csrf_token"]})
        assert response.status_code == 403
        if role == "operator":
            saved_context = client.get("/api/portfolio/risk-history/context", params={"base_currency": "USD"}).json()
    admin = client.post("/api/auth/login", json=dict(username="qa-admin", password="Synthetic-QA-Password!")).json()
    assert client.delete("/api/portfolio/risk-history").status_code == 403
    before = risk_history.history_epoch(store)
    response = client.delete("/api/portfolio/risk-history", headers={"X-CSRF-Token": admin["csrf_token"]})
    assert response.status_code == 200
    assert risk_history.history_epoch(store)["id"] != before["id"]
    operator = client.post("/api/auth/login", json=dict(username="qa-operator", password="Synthetic-QA-Password!")).json()
    rejected = client.post("/api/portfolio/risk-history", json=qa_payload(saved_context),
                           headers={"X-CSRF-Token": operator["csrf_token"]})
    assert rejected.status_code == 409
    assert client.get("/api/portfolio/risk-history", params={"base_currency": "USD", "days": 0}).json()["items"] == []


@pytest.mark.parametrize("corruption", ["snapshot-type", "accounts-null", "account-without-id",
    "ledger-null", "ledger-entry-type", "positions-dict", "position-mark-type",
    "fx-entry-type", "fx-rate-bool", "duplicate-account", "total-equity-bool",
    "pooled-equity-mismatch", "wrong-scope", "flow-sign", "flow-fx-base", "flow-fx-currency",
    "future-ledger-status-forged"])
def test_corrupt_performance_evidence_is_a_visible_gap_and_never_crashes_or_bridges(tmp_path, monkeypatch, corruption):
    store = LocalPortfolioStore(tmp_path / "qa-corrupt-performance.sqlite")
    inputs = qa_inputs()
    base = "ILS" if corruption in {"flow-fx-base", "flow-fx-currency"} else "USD"
    if base == "ILS":
        inputs = qa_inputs([qa_account(cash=100)], fx=qa_fx(3, "2026-11-14"), base=base)
    first = qa_save(store, monkeypatch, inputs)
    if corruption in {"flow-sign", "flow-fx-base", "flow-fx-currency"}:
        deposit = qa_transaction("fresh-capital", "CASH_IN", 10 if base == "ILS" else 50,
                                 day="2026-11-15", created="2026-11-15T08:00:00Z")
        inputs = qa_inputs([qa_account(cash=100 if base == "ILS" else 1000)], transactions=[deposit],
                           fx=qa_fx(3.2, "2026-11-15") if base == "ILS" else None, base=base)
    elif corruption == "future-ledger-status-forged":
        activity = qa_transaction("future-income", "DIVIDEND", 10,
                                  day="2026-11-16", created="2026-11-15T08:00:00Z")
        inputs = qa_inputs(transactions=[activity])
    middle = qa_save(store, monkeypatch, inputs, AS_OF + timedelta(days=1))
    if corruption == "snapshot-type":
        middle["performance_snapshot"] = "broken"
    elif corruption == "accounts-null":
        middle["performance_snapshot"]["accounts"] = None
    elif corruption == "account-without-id":
        middle["performance_snapshot"]["accounts"] = [{}]
    elif corruption == "ledger-null":
        middle["performance_snapshot"]["accounts"][0]["ledger_rows"] = None
    elif corruption == "ledger-entry-type":
        middle["performance_snapshot"]["accounts"][0]["ledger_rows"] = ["broken"]
    elif corruption == "positions-dict":
        middle["performance_snapshot"]["accounts"][0]["positions"] = {}
    elif corruption == "position-mark-type":
        middle["performance_snapshot"]["accounts"][0]["positions"] = [dict(key="QA|QA|USD|EQUITY", quantity=1, mark=[])]
    elif corruption == "fx-entry-type":
        middle["performance_snapshot"]["accounts"][0]["fx_evidence"] = [None]
    elif corruption == "fx-rate-bool":
        middle["performance_snapshot"]["accounts"][0]["fx_evidence"][0]["rate"] = True
    elif corruption == "duplicate-account":
        middle["performance_snapshot"]["accounts"].append(deepcopy(middle["performance_snapshot"]["accounts"][0]))
    elif corruption == "total-equity-bool":
        middle["performance_snapshot"]["total"]["equity"] = True
    elif corruption == "pooled-equity-mismatch":
        # The only account contains1000, so a pooled999999 is contradictory
        # evidence and cannot establish998999 of observed investment profit.
        middle["performance_snapshot"]["total"]["equity"] = 999999
    elif corruption == "wrong-scope":
        middle["performance_snapshot"]["scope"] = "unsupported_foreign_scope"
    elif corruption == "flow-sign":
        # CASH_IN50 is +50 capital, never-50; equity1050 therefore has zero P&L.
        middle["performance_snapshot"]["accounts"][0]["ledger_rows"][0]["signed_external_flow"] = -50
    elif corruption == "flow-fx-base":
        middle["performance_snapshot"]["accounts"][0]["ledger_rows"][0]["flow_fx_evidence"]["base_currency"] = "EUR"
    elif corruption == "flow-fx-currency":
        middle["performance_snapshot"]["accounts"][0]["ledger_rows"][0]["flow_fx_evidence"]["currency"] = "JPY"
    elif corruption == "future-ledger-status-forged":
        middle["performance_snapshot"]["accounts"][0].update(status="ok", reason_codes=[])
        middle["performance_snapshot"]["total"].update(status="ok", reason_codes=[])
    with store._connect() as connection:
        connection.execute("update app_preferences set value=? where key glob ? and json_extract(value,'$.id')=?",
                           (json.dumps(middle), risk_history.PREFIX + "*", middle["id"]))
    qa_save(store, monkeypatch, inputs, AS_OF + timedelta(days=2))
    result = risk_history.list_observations(store, base, 0)
    assert len(result["items"]) == 3
    corrupted = next(row for row in result["items"] if row["id"] == middle["id"])
    assert corrupted["performance"]["total"]["status"] == "unavailable"
    assert corrupted["performance"]["total"]["profit"] is None
    assert "missing_performance_evidence" in corrupted["performance"]["total"]["reason_codes"]
    last = result["items"][-1]["performance"]["total"]
    assert last["profit"] is None
    assert last["baseline_observation_id"] != first["id"]
    account_last = result["items"][-1]["performance"]["accounts"][0]
    assert account_last["profit"] is None
    assert account_last["baseline_observation_id"] != first["id"]


@pytest.mark.parametrize("quantity,begin_value,invalid_value", [(-10, -100, 100), (10, 100, -100)])
def test_sign_inconsistent_security_value_cannot_manufacture_observed_profit(
        tmp_path, monkeypatch, quantity, begin_value, invalid_value):
    store = LocalPortfolioStore(tmp_path / "qa-signed-valuations.sqlite")
    accounts = [qa_account(cash=1000)]
    qa_save(store, monkeypatch, qa_inputs(accounts, [qa_holding(begin_value, quantity=quantity)]))
    qa_save(store, monkeypatch, qa_inputs(accounts, [qa_holding(invalid_value, quantity=quantity, day="2026-11-15")]),
            AS_OF + timedelta(days=1))
    for account in ("", "a"):
        result = qa_history(store, account)[-1]
        assert result["status"] == "unavailable", result
        assert result["profit"] is None
        assert result["reason_codes"]


@pytest.mark.parametrize("matching_quote", [True, False])
def test_real_enriched_portfolio_quote_shape_requires_dated_matching_mark_without_invented_metadata(
        tmp_path, monkeypatch, matching_quote):
    store = LocalPortfolioStore(tmp_path / "qa-real-quote-shape.sqlite")
    accounts = [qa_account(cash=0)]

    def item(value, quote, day):
        return dict(holding=dict(account_id="a", symbol="QA", stock_market="QA", asset_class="EQUITY",
                                 quantity=1, currency="USD", market_value=value),
                    stress_risk={"security_key": "QA|QA|USD", "parameters": {}},
                    price_ranges={"1y": {"current": quote, "current_date": day}})

    # Actual enrich() emits risk metadata separately from the dated portfolio
    # quote. It need not copy valuation_date into stress_risk.
    qa_save(store, monkeypatch, qa_inputs(accounts, [item(100, 100, "2026-11-14")]))
    qa_save(store, monkeypatch, qa_inputs(accounts, [item(110, 110 if matching_quote else 100, "2026-11-15")]),
            AS_OF + timedelta(days=1))
    for account in ("", "a"):
        result = qa_history(store, account)[-1]
        if matching_quote:
            assert result["status"] == "recorded", result
            assert result["beginning_equity"] == 100
            assert result["ending_equity"] == 110
            assert result["profit"] == 10
        else:
            assert result["status"] == "unavailable", result
            assert result["profit"] is None


def test_actual_provider_fx_time_field_supports_observed_currency_revaluation(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-real-provider-fx.sqlite")
    account = qa_account(cash=100, currency="USD")
    # AlphaVantage, Frankfurter and manual provider FX snapshots expose `time`,
    # which remains the source observation date when returned from saved cache.
    def provider_fx(rate, day):
        return {"quotes": [dict(pair="USD/ILS", quote=dict(rate=rate, time=day),
                                 status={"synthetic-provider": "saved_evidence"})]}
    qa_save(store, monkeypatch, qa_inputs([account], fx=provider_fx(3, "2026-11-14"), base="ILS"))
    qa_save(store, monkeypatch, qa_inputs([account], fx=provider_fx(3.3, "2026-11-15"), base="ILS"),
            AS_OF + timedelta(days=1))
    result = qa_history(store, "a", base="ILS")[-1]
    assert result["status"] == "recorded", result
    assert result["beginning_equity"] == 300
    assert result["ending_equity"] == 330
    assert result["profit"] == 30


def test_direct_fx_pair_has_same_priority_as_dashboard_with_inconsistent_inverse_quotes(tmp_path, monkeypatch):
    import subprocess
    from test_shared_cash_risk_qa import app_functions

    source = "const state={baseCurrency:'ILS',fxRates:{'ILS/USD':.25,'USD/ILS':3.5}};\n"
    source += app_functions("normalizedAmount") + "\nconst before=normalizedAmount(100,'USD');state.fxRates={'ILS/USD':.20,'USD/ILS':3.6};console.log(JSON.stringify([before,normalizedAmount(100,'USD')]));"
    frontend = subprocess.run(["node"], input=source, text=True, capture_output=True)
    assert frontend.returncode == 0, frontend.stderr
    assert json.loads(frontend.stdout) == [350, 360]
    store = LocalPortfolioStore(tmp_path / "qa-direct-fx-priority.sqlite")
    account = qa_account(cash=100, currency="USD")
    def rates(direct, inverse, day):
        return {"quotes": [dict(pair="ILS/USD", quote=dict(rate=inverse, time=day), status={"inverse": "saved_evidence"}),
                           dict(pair="USD/ILS", quote=dict(rate=direct, time=day), status={"direct": "saved_evidence"})]}
    # Runtime sorts the ILS/USD pair before USD/ILS. Dashboard conversion prefers
    # its explicit USD/ILS3.5 rate over reciprocal1/.25=4 regardless of row order.
    qa_save(store, monkeypatch, qa_inputs([account], fx=rates(3.5, .25, "2026-11-14"), base="ILS"))
    qa_save(store, monkeypatch, qa_inputs([account], fx=rates(3.6, .20, "2026-11-15"), base="ILS"),
            AS_OF + timedelta(days=1))
    result = qa_history(store, "a", base="ILS")[-1]
    assert result["status"] == "recorded", result
    assert result["beginning_equity"] == 350
    assert result["ending_equity"] == 360
    assert result["profit"] == 10
