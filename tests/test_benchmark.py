"""Independent numerical examples for cash-flow-aware portfolio performance."""
from copy import deepcopy
from datetime import date

import pytest

from app.benchmark import (BENCHMARKS, BenchmarkError, compute_comparison, load_index,
                           load_portfolio, normalize_index, normalize_portfolio,
                           save_index, save_portfolio, xirr)

START, MID, END = "2023-01-01", "2023-07-02", "2024-01-01"


def portfolio(values=None, flows=None, **extra):
    result = {"currency": "USD", "source": "Broker statement", "flows_complete": True,
              "valuations": [{"date": day, "value": value} for day, value in
                             (values or [(START, 100), (END, 121)])],
              "cash_flows": [{"date": day, "amount": amount} for day, amount in (flows or [])]}
    result.update(extra)
    return result


def index(levels=None, **extra):
    result = {"name": "Example benchmark", "source": "Official index file", "currency": "USD",
              "basis": "total_return", "levels": [{"date": day, "level": level} for day, level in
                                                   (levels or [(START, 100), (END, 110)])]}
    result.update(extra)
    return result


def compare(p=None, b=None, start=START, end=END):
    return compute_comparison(p or portfolio(), b or index(), start, end)


def test_no_flow_one_year_returns_and_benchmark_matching_cash():
    result = compare()
    assert result["portfolio"]["xirr"]["value"] == pytest.approx(21)
    assert result["portfolio"]["twrr"]["value"] == pytest.approx(21)
    assert result["benchmark"]["xirr"]["value"] == pytest.approx(10)
    assert result["benchmark"]["twrr"]["value"] == pytest.approx(10)
    assert result["benchmark"]["ending_value"] == pytest.approx(110)
    assert result["portfolio"]["gain"] == 21
    assert result["annualized_short_period"] is False
    assert result["chart"][0] == {"date": START, "portfolio_growth": 100, "benchmark_growth": 100}
    assert result["chart"][-1]["portfolio_growth"] == pytest.approx(121)


def test_deposit_not_a_return_and_same_flow_benchmark():
    p = portfolio([(START, 100), (MID, 160), (END, 176)], [(MID, 50)])
    b = index([(START, 100), (MID, 110), (END, 121)])
    result = compare(p, b)
    # First interval 110/100 -1=10%; second 176/160-1=10%.
    assert result["portfolio"]["twrr"]["value"] == pytest.approx(21)
    # Same benchmark return trajectory means same terminal wealth and IRR.
    assert result["benchmark"]["ending_value"] == pytest.approx(176)
    assert result["benchmark"]["xirr"]["value"] == pytest.approx(result["portfolio"]["xirr"]["value"])
    assert result["portfolio"]["net_flows"] == 50
    assert result["portfolio"]["gain"] == 26


def test_withdrawal_is_external_cashflow_not_loss():
    p = portfolio([(START, 100), (MID, 60), (END, 66)], [(MID, -50)])
    result = compare(p, index([(START, 100), (MID, 110), (END, 121)]))
    assert result["portfolio"]["twrr"]["value"] == pytest.approx(21)
    assert result["benchmark"]["ending_value"] == pytest.approx(66)
    assert result["portfolio"]["net_flows"] == -50
    assert result["portfolio"]["gain"] == 16


def test_missing_flow_value_does_not_turn_dietz_into_exact_twrr():
    result = compare(portfolio(flows=[(MID, 50)]), index([(START, 100), (MID, 100), (END, 110)]))
    assert result["portfolio"]["xirr"]["value"] is not None
    assert result["portfolio"]["twrr"] == {"value": None, "status": "missing_flow_valuation"}
    assert result["chart"] == []


def test_flow_completeness_is_required_even_with_no_recorded_flows():
    result = compare(portfolio(flows_complete=False))
    assert result["portfolio"]["xirr"]["status"] == "incomplete_cash_flows"
    assert result["portfolio"]["twrr"]["value"] is None
    assert result["portfolio"]["gain"] is None
    assert result["benchmark"]["xirr"]["value"] is None


def test_missing_exact_boundary_not_forward_filled():
    result = compare(portfolio([(START, 100), ("2023-12-31", 121)]))
    assert result["portfolio"]["xirr"]["status"] == "missing_boundary_valuation"
    assert result["benchmark"]["ending_value"] is None


def test_start_date_flows_excluded_as_opening_balance_already_contains_them():
    result = compare(portfolio(flows=[(START, 80)]))
    assert result["portfolio"]["net_flows"] == 0
    assert result["portfolio"]["xirr"]["value"] == pytest.approx(21)


def test_end_date_flow_is_subtracted_before_final_return():
    result = compare(portfolio([(START, 100), (END, 150)], [(END, 50)]))
    assert result["portfolio"]["xirr"]["value"] == pytest.approx(0, abs=1e-9)
    assert result["portfolio"]["twrr"]["value"] == pytest.approx(0)


def test_full_withdrawal_at_end_is_valid_twrr_and_xirr():
    p = portfolio([(START, 100), (END, 0)], [(END, -110)])
    result = compare(p)
    assert result["portfolio"]["twrr"]["value"] == pytest.approx(10)
    assert result["portfolio"]["xirr"]["value"] == pytest.approx(10)
    assert result["benchmark"]["ending_value"] == pytest.approx(0, abs=1e-9)


def test_closed_account_then_reentry_cannot_link_zero_base():
    p = portfolio([(START, 100), (MID, 0), (END, 50)], [(MID, -100), (END, 50)])
    result = compare(p, index([(START, 100), (MID, 100), (END, 100)]))
    assert result["portfolio"]["twrr"]["status"] == "nonpositive_base"
    assert result["portfolio"]["xirr"]["value"] == pytest.approx(0, abs=1e-9)


def test_currency_mismatch_does_not_use_current_fx_or_imply_comparable():
    result = compare(b=index(currency="ILS"))
    assert result["portfolio"]["twrr"]["value"] == pytest.approx(21)
    assert result["benchmark"]["status"] == "currency_mismatch"
    assert result["benchmark"]["xirr"]["value"] is None


def test_prior_index_observation_weekend_is_disclosed_and_future_forbidden():
    b = index([("2022-12-30", 100), ("2023-12-29", 110)])
    result = compare(b=b)
    assert result["benchmark"]["twrr"]["value"] == pytest.approx(10)
    assert result["benchmark"]["level_dates"][0]["level_date"] == "2022-12-30"
    future_only = index([("2023-01-02", 100), (END, 110)])
    assert compare(b=future_only)["benchmark"]["status"] == "missing_index_level"


def test_stale_index_level_not_used_at_flow_date():
    p = portfolio([(START, 100), (MID, 150), (END, 150)], [(MID, 50)])
    assert compare(p)["benchmark"]["status"] == "missing_index_level"


def test_benchmark_cannot_fund_a_withdrawal_larger_than_its_wealth():
    p = portfolio([(START, 100), (MID, 10), (END, 20)], [(MID, -150)])
    b = index([(START, 100), (MID, 110), (END, 120)])
    result = compare(p, b)
    assert result["portfolio"]["twrr"]["value"] is not None
    assert result["benchmark"]["status"] == "benchmark_overdrawn"


def test_legacy_indices_not_silently_replaced_with_successors():
    assert compare(b=index(id="ta25", currency="USD"))["benchmark"]["status"] == "index_outside_lifetime"
    assert compare(b=index(id="ta100", currency="USD"))["benchmark"]["status"] == "index_outside_lifetime"
    assert {row["id"] for row in BENCHMARKS} == {"sp500", "ta25", "ta100", "ta35", "ta125", "nasdaq", "dow", "custom"}


def test_daily_short_period_marks_xirr_as_annualized():
    result = compare(portfolio([(START, 100), ("2023-01-02", 100.1)]),
                     index([(START, 100), ("2023-01-02", 100.1)]), end="2023-01-02")
    assert result["annualized_short_period"] is True
    assert result["portfolio"]["twrr"]["value"] == pytest.approx(.1)
    assert result["portfolio"]["xirr"]["value"] == pytest.approx((1.001**365-1)*100)


def test_actual_365_leap_year_convention():
    result = xirr([("2020-01-01", -100), ("2021-01-01", 110)])
    assert result["value"] == pytest.approx((1.1**(365/366)-1)*100)


def test_ambiguous_cashflows_do_not_select_a_guessed_root():
    # -100,+230,-132 annual cash flows have IRRs 10% and20%.
    result = xirr([("2021-01-01", -100), ("2022-01-01", 230), ("2023-01-01", -132)])
    assert result == {"value": None, "status": "ambiguous_cash_flows"}


@pytest.mark.parametrize("flows,status", [
    ([(START, -100), (START, 110)], "insufficient_dates"),
    ([(START, 100), (END, 110)], "invalid_cash_flow_signs"),
    ([(START, -100), (END, 0)], "insufficient_dates"),
    ([(START, float("nan")), (END, 1)], "invalid_cash_flows"),
])
def test_xirr_unavailable_is_not_zero(flows, status):
    assert xirr(flows) == {"value": None, "status": status}


def test_missing_input_is_unavailable_not_invented():
    result = compute_comparison(None, None, START, END)
    assert result["portfolio"]["status"] == "missing_portfolio"
    assert result["benchmark"]["status"] == "missing_index"


def test_cashflows_same_day_net_and_zero_net_cancels():
    p = portfolio(flows=[(MID, 20), (MID, -5)])
    assert normalize_portfolio(p)["cash_flows"] == [{"date": MID, "amount": 15}]
    p["cash_flows"][1]["amount"] = -20
    assert normalize_portfolio(p)["cash_flows"] == []


@pytest.mark.parametrize("mutate,code", [
    (lambda p: p.update(currency=""), "currency_required"),
    (lambda p: p.update(source=""), "source_required"),
    (lambda p: p.update(valuations=[]), "invalid_rows"),
    (lambda p: p["valuations"].append(p["valuations"][0]), "duplicate_date"),
    (lambda p: p["valuations"][0].update(value=True), "invalid_number"),
    (lambda p: p["valuations"][0].update(value=float("inf")), "invalid_number"),
    (lambda p: p["valuations"][0].update(value=-1), "invalid_number"),
    (lambda p: p["valuations"][0].update(date="01/01/2023"), "invalid_date"),
    (lambda p: p["valuations"][0].update(date="2999-01-01"), "future_date"),
    (lambda p: p.update(cash_flows=[{"date": MID,"amount": 0}]), "zero_cash_flow"),
    (lambda p: p.update(cash_flows=[None]), "invalid_rows"),
])
def test_bad_portfolio_inputs_rejected(mutate, code):
    p = portfolio()
    mutate(p)
    with pytest.raises(BenchmarkError, match=code):
        normalize_portfolio(p)


@pytest.mark.parametrize("change,code", [
    ({"levels": [{"date": START, "level": 0}]}, "invalid_number"),
    ({"basis": "adjusted"}, "index_basis_required"),
    ({"name": ""}, "index_name_required"),
    ({"id": "invented"}, "unknown_benchmark"),
])
def test_bad_index_inputs_rejected(change, code):
    with pytest.raises(BenchmarkError, match=code):
        value = index()
        value.update(change)
        normalize_index(value)


def test_preference_persistence_scopes_and_normalizes_without_mutating_inputs():
    class Store:
        def __init__(self): self.data = {}
        def get_preference(self, key, default=None): return deepcopy(self.data.get(key, default))
        def set_preference(self, key, value): self.data[key] = deepcopy(value)
    store = Store()
    p = portfolio()
    original = deepcopy(p)
    save_portfolio(store, p, "account-A")
    assert load_portfolio(store, "account-A") == p
    assert load_portfolio(store, "account-B") is None
    assert load_portfolio(store) is None
    save_index(store, "sp500", index())
    assert load_index(store, "sp500")["id"] == "sp500"
    assert p == original
    with pytest.raises(BenchmarkError): save_index(store, "made-up", index())


def test_aggregate_cash_flow_obeys_saved_number_limits():
    value = portfolio(flows=[(MID, 1e15), (MID, 1e15)])
    with pytest.raises(BenchmarkError, match="invalid_number"):
        normalize_portfolio(value)


def test_missing_flow_valuation_still_gives_correct_money_weighted_return():
    # Terminal wealth is exactly the future value of both investments at10%.
    mid_fraction = (date.fromisoformat(END) - date.fromisoformat(MID)).days / 365
    end_value = 100 * 1.1 + 50 * (1.1 ** mid_fraction)
    value = portfolio([(START, 100), (END, end_value)], [(MID, 50)])
    result = compare(value, index([(START,100),(MID,100),(END,110)]))
    assert result["portfolio"]["xirr"]["value"] == pytest.approx(10)
    assert result["portfolio"]["twrr"]["status"] == "missing_flow_valuation"


def test_legacy_last_day_is_accepted_without_substitution():
    start, end = "2016-02-08", "2017-02-08"
    p = portfolio([(start,100),(end,110)], currency="ILS")
    b = index([(start,100),(end,110)], id="ta25", currency="ILS")
    result = compare(p,b,start,end)
    assert result["benchmark"]["status"] == "ok"
    assert result["benchmark"]["id"] == "ta25"
