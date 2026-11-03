"""Independent closed-form and evidence-boundary checks for ILS historical VaR."""
from copy import deepcopy
from datetime import date, timedelta
import math
from types import SimpleNamespace

from fastapi.responses import JSONResponse
import pytest

from app.models import Holding, Ohlcv
from app.local_portfolio import LocalPortfolioStore
from app.value_at_risk import VarError, build_var, loss_statistics

TODAY = date(2026, 11, 3)


def prices(monthly_ratio=1.0, *, days=180, last=100, end=TODAY, adjusted_factor=1.0, day_filter=lambda day: True):
    result = []
    for i in range(days+1):
        day = end-timedelta(days=days-i)
        if not day_filter(day): continue
        value = last*monthly_ratio**((i-days)/30)
        result.append(Ohlcv(day, value, value, value, value, value*adjusted_factor, 1))
    return result


def fx(monthly_ratio=.9, **kwargs):
    return {"currency": "USD", "source": "Synthetic daily FX evidence", "rates": [
        {"date": row.date.isoformat(), "rate": row.close} for row in prices(monthly_ratio,last=4,**kwargs)]}


def holding(symbol="AAA", **kwargs):
    return Holding(symbol=symbol, stock_market=kwargs.pop("stock_market", "NASDAQ"), currency=kwargs.pop("currency", "USD"),
                   quantity=kwargs.pop("quantity", 10), account_id=kwargs.pop("account_id", "a"), asset_class=kwargs.pop("asset_class", "EQUITY"), **kwargs)


class Store:
    def __init__(self, holdings=None, *, accounts=None, transactions=None, funds=None, local=None, manual=None):
        self.positions = holdings if holdings is not None else [holding()]
        self.accounts = accounts if accounts is not None else [{"id": "a", "type":"Investment", "account_id": "Synthetic account", "currency": "USD", "initial_cash": 0}]
        self.transactions = transactions or []
        self.funds = funds or []
        self.local = local or {}
        self.manual = manual or {}
    def holdings(self): return [SimpleNamespace(holding=row) for row in self.positions]
    def list_accounts(self): return deepcopy(self.accounts)
    def list_transactions(self): return deepcopy(self.transactions)
    def list_funds(self): return deepcopy(self.funds)
    def manual_security(self, symbol, market): return self.manual.get(symbol)
    def price_history(self, symbol, market, start, end): return [row for row in self.local.get(symbol,[]) if start.isoformat() <= row["price_date"] <= end.isoformat()]


class Hub:
    def __init__(self, histories=None): self.histories = histories if histories is not None else {"AAA":prices()}; self.calls=[]
    def cached_prices(self, symbol, start, end, **context):
        self.calls.append((symbol,context))
        return [row for row in self.histories.get(symbol,[]) if start<=row.date<=end], {"synthetic":"cached"}
    def prices(self,*a,**k): raise AssertionError("VaR must not fetch prices")
    def fx(self,*a,**k): raise AssertionError("VaR must not fetch latest FX")


def calculate(store=None, hub=None, snapshots=None, **kwargs):
    return build_var(store or Store(), hub or Hub(), {"USD":fx()} if snapshots is None else snapshots, today=TODAY, **kwargs)


def test_flat_usd_stock_loses_in_ils_when_dollar_falls():
    result = calculate()
    assert result["status"]=="ok" and result["scope_complete"]
    assert result["portfolio_value_ils"]==pytest.approx(4000)
    assert result["sample_count"]==151
    assert result["var_ils"]==pytest.approx(400)
    assert result["expected_shortfall_ils"]==pytest.approx(400)
    assert result["var_without_fx_ils"]==pytest.approx(0)
    assert "constant_asset_history" in result["warnings"]
    assert all(row["loss_ils"]==pytest.approx(400) for row in result["scenarios"])
    assert all((date.fromisoformat(row["to"])-date.fromisoformat(row["from"])).days==30 for row in result["scenarios"])


def test_price_and_fx_losses_compound_instead_of_adding_percentages():
    result=calculate(hub=Hub({"AAA":prices(.9)}))
    # 90% of the stock price × 90% USD/ILS = 81%, a 19% ILS loss.
    assert result["var_ils"]==pytest.approx(760)
    assert result["var_without_fx_ils"]==pytest.approx(400)
    assert result["expected_shortfall_ils"]==pytest.approx(760)


def test_ils_stock_needs_no_fx_history_and_keeps_its_recorded_units():
    store=Store([holding(stock_market="TASE",currency="ILS")], accounts=[{"id":"a", "type":"Investment","currency":"ILS","initial_cash":0}])
    result=calculate(store,Hub({"AAA":prices(.9)}),snapshots={})
    assert result["status"]=="ok" and result["fx"]==[]
    assert result["portfolio_value_ils"]==pytest.approx(1000)
    assert result["var_ils"]==pytest.approx(100)


@pytest.mark.parametrize("amount,monthly_ratio,loss",[(1000,.9,400),(-1000,1.1,400)])
def test_foreign_cash_and_borrowing_have_currency_risk(amount,monthly_ratio,loss):
    store=Store([], accounts=[{"id":"a", "type":"Investment","currency":"USD","initial_cash":amount}])
    result=calculate(store,snapshots={"USD":fx(monthly_ratio)})
    assert result["status"]=="ok" and result["var_ils"]==pytest.approx(loss)
    assert result["var_without_fx_ils"]==0
    if amount<0: assert "nonpositive_equity" in result["warnings"]


def test_ils_cash_has_zero_nominal_price_var_without_inventing_a_sample():
    result=calculate(Store([],accounts=[{"id":"a", "type":"Investment","currency":"ILS","initial_cash":10000}]),snapshots={})
    assert result["status"]=="ok" and result["var_ils"]==0 and result["portfolio_value_ils"]==10000
    assert result["sample_count"]==0 and result["warnings"]==["nominal_ils_cash_only"]
    empty=calculate(Store([],accounts=[]),snapshots={})
    assert empty["status"]=="empty" and empty["var_ils"]==0
    assert "nominal_ils_cash_only" not in empty["warnings"]


def test_signed_stock_risk_and_cash_hedge_are_joint_not_summed_independent_vars():
    store=Store([holding(quantity=-10)],accounts=[{"id":"a", "type":"Investment","currency":"USD","initial_cash":1000}])
    result=calculate(store,snapshots={"USD":fx(.9)})
    assert result["status"]=="ok" and result["portfolio_value_ils"]==pytest.approx(0)
    assert result["var_ils"]==pytest.approx(0,abs=1e-9)
    assert all(row["loss_ils"]==pytest.approx(0,abs=1e-9) for row in result["scenarios"])
    short=calculate(Store([holding(quantity=-10)]),Hub({"AAA":prices(1.1)}),{"USD":fx(1)})
    assert short["var_ils"]==pytest.approx(400)


def test_empirical_quantile_and_fractional_five_percent_tail_are_exact():
    result=loss_statistics(list(range(20)))
    assert result["var_ils"]==18 and result["expected_shortfall_ils"]==19
    result=loss_statistics(list(range(21)))
    assert result["var_ils"]==19
    assert result["expected_shortfall_ils"]==pytest.approx((20+.05*19)/1.05)
    ties=loss_statistics([100]*19+[200])
    assert ties["var_ils"]==100 and ties["expected_shortfall_ils"]==200
    gains=loss_statistics(list(range(-20,0)))
    assert gains["var_ils"]==gains["expected_shortfall_ils"]==0
    assert gains["raw_var_ils"]==-2 and gains["raw_expected_shortfall_ils"]==-1


def test_exact_common_monthly_endpoints_preserve_joint_currency_co_movement():
    a=prices(.98,days=400,day_filter=lambda day:day.weekday()<5)
    b=prices(1.03,days=400,day_filter=lambda day:day.weekday() in {0,1,2,3,6})
    fx_rows=fx(.99,days=400,day_filter=lambda day:day.weekday()<5)
    store=Store([holding("AAA"),holding("BBB",stock_market="TASE",currency="ILS")])
    result=calculate(store,Hub({"AAA":a,"BBB":b}),{"USD":fx_rows})
    common={r.date for r in a}&{r.date for r in b}&{date.fromisoformat(r["date"]) for r in fx_rows["rates"]}
    expected=[(end-timedelta(days=30),end) for end in sorted(common) if end-timedelta(days=30) in common]
    assert result["sample_count"]==len(expected) and result["status"]=="ok"
    assert [(r["from"],r["to"]) for r in result["scenarios"]]==[(a.isoformat(),b.isoformat()) for a,b in expected]
    # Every scenario uses today's values but the same historical date shocks.
    assert result["var_ils"]==pytest.approx(max(0,4000*(1-.98*.99)+1000*(1-1.03)))


def test_missing_one_currency_or_position_blocks_both_var_and_full_portfolio_total():
    missing=calculate(snapshots={})
    assert missing["status"]=="unavailable" and missing["var_ils"] is None and missing["portfolio_value_ils"] is None
    assert {r["code"] for r in missing["issues"]}=={"missing_fx_history"}
    store=Store([holding(),holding("MISSING",currency="ILS",stock_market="TASE")])
    incomplete=calculate(store)
    assert incomplete["portfolio_value_ils"] is None and incomplete["var_ils"] is None
    assert any(r["code"]=="missing_price_history" for r in incomplete["issues"])
    assert incomplete["assets"][0]["value_ils"]==pytest.approx(4000)


@pytest.mark.parametrize("code,store",[
    ("unsupported_asset",Store([holding(asset_class="OPTION")])),
    ("unsupported_fund",Store(funds=[{"id":"fund","account_id":"a","amount":10000}])),
    ("cash_currency_mismatch",Store(transactions=[{"account_db_id":"a","action":"BUY","quantity":1,"price":100,"currency":"ILS"}])),
    ("future_transaction",Store(transactions=[{"account_db_id":"a","action":"ADD","trade_date":(TODAY+timedelta(days=1)).isoformat()}])),
])
def test_uncovered_or_inconsistent_book_is_not_a_partial_portfolio_headline(code,store):
    result=calculate(store)
    assert result["var_ils"] is None and result["portfolio_value_ils"] is None and not result["scope_complete"]
    assert any(row["code"]==code for row in result["issues"])
    if code=="cash_currency_mismatch":assert result["cash"][0]["amount"] is None and result["cash"][0]["value_ils"] is None


def test_scope_can_narrow_a_complete_account_away_from_an_unsupported_fund():
    store=Store(accounts=[{"id":"a", "type":"Investment","currency":"USD","initial_cash":0},{"id":"b", "type":"Investment","currency":"ILS","initial_cash":0}],funds=[{"account_id":"b","amount":5000}])
    assert calculate(store)["var_ils"] is None
    assert calculate(store,account_id="a")["status"]=="ok"
    with pytest.raises(VarError,match="var_unknown_account"):calculate(store,account_id="missing")


def test_cash_model_matches_recorded_trade_actions_in_account_currency():
    tx={"account_db_id":"a","currency":"USD","quantity":1,"trade_date":"2026-01-01"}
    store=Store(transactions=[{**tx,"action":"BUY","price":500},{**tx,"action":"SELL","price":200},{**tx,"action":"FEE","price":20},{**tx,"action":"DIVIDEND","price":10}],accounts=[{"id":"a", "type":"Investment","currency":"USD","initial_cash":1000}])
    result=calculate(store)
    assert result["cash"][0]["amount"]==690
    assert result["portfolio_value_ils"]==pytest.approx((1000+690)*4)
    assert result["var_ils"]==pytest.approx((1000+690)*4*.1)


def test_stale_current_price_and_fx_do_not_claim_next_month_loss():
    result=calculate(hub=Hub({"AAA":prices(end=TODAY-timedelta(days=8))}))
    assert result["var_ils"] is None and any(row["code"]=="stale_price" for row in result["issues"])
    result=calculate(snapshots={"USD":fx(end=TODAY-timedelta(days=8))})
    assert result["var_ils"] is None and any(row["code"]=="stale_fx" for row in result["issues"])


def test_insufficient_exact_monthly_samples_and_stale_shared_samples_are_unavailable():
    result=calculate(hub=Hub({"AAA":prices(days=100)}),snapshots={"USD":fx(days=100)})
    assert result["reason"]=="insufficient_monthly_history" and result["sample_count"]==71
    assert result["var_ils"] is None
    a=[r for r in prices(end=TODAY-timedelta(days=20)) if r.date!=TODAY-timedelta(days=30)]
    a.extend(prices(days=0))
    snapshot=fx(end=TODAY-timedelta(days=20));snapshot["rates"]=[r for r in snapshot["rates"] if r["date"]!=(TODAY-timedelta(days=30)).isoformat()];snapshot["rates"].extend(fx(days=0)["rates"])
    result=calculate(hub=Hub({"AAA":a}),snapshots={"USD":snapshot})
    assert result["var_ils"] is None and any(r["code"]=="stale_monthly_history" for r in result["issues"])


def test_adjusted_histories_are_never_spliced_with_raw_local_overrides():
    hub=Hub({"AAA":prices(.99,adjusted_factor=.5),"BBB":prices(.98,adjusted_factor=.25)})
    store=Store([holding(),holding("BBB")])
    adjusted=calculate(store,hub)
    raw_point=hub.histories["AAA"][50]
    store.local={"AAA":[{"price_date":raw_point.date.isoformat(),"price":raw_point.close,"currency":"USD","asset_class":"EQUITY"}]}
    raw=calculate(store,hub)
    assert adjusted["basis"]=="adjusted_close" and raw["basis"]=="close"
    assert raw["var_ils"]==pytest.approx(adjusted["var_ils"])
    assert "unadjusted_prices" in raw["warnings"]


def test_listing_currency_identity_conflicts_and_wrong_local_quotes_are_not_inferred():
    store=Store([holding(),holding(currency="ILS",account_id="b")],accounts=[{"id":"a", "type":"Investment","currency":"USD","initial_cash":0},{"id":"b", "type":"Investment","currency":"ILS","initial_cash":0}])
    result=calculate(store)
    assert any(row["code"]=="currency_conflict" for row in result["issues"]) and result["var_ils"] is None
    manual=Store(manual={"AAA":{"secondary_symbol":""}},local={"AAA":[{"price_date":row.date.isoformat(),"price":row.close,"currency":"ILS","asset_class":"EQUITY"} for row in prices()]})
    result=calculate(manual)
    assert any(row["code"]=="missing_price_history" for row in result["issues"])


@pytest.mark.parametrize("change",[{}, {"currency":"EUR"}, {"source":""}, {"rates":[{"date":"bad","rate":4}]}, {"rates":[{"date":TODAY.isoformat(),"rate":4},{"date":TODAY.isoformat(),"rate":5}]}])
def test_invalid_fx_snapshots_do_not_create_constant_or_fabricated_history(change):
    snapshot={**fx(),**change} if change else {}
    result=calculate(snapshots={"USD":snapshot})
    assert result["var_ils"] is None and any(row["code"] in {"invalid_fx_history","missing_fx_history"} for row in result["issues"])
    assert JSONResponse(result).status_code==200


def test_overflow_cash_quantities_and_values_remain_json_safe_unavailable():
    for store in [Store([holding(quantity=float("inf"))]),Store([holding(quantity=1e308)]),Store([holding(quantity=1e308),holding(quantity=1e308)]),Store([],accounts=[{"id":"a", "type":"Investment","currency":"USD","initial_cash":float("nan")}])]:
        result=calculate(store)
        assert result["status"]=="unavailable" and result["var_ils"] is None
        assert JSONResponse(result).status_code==200
    invalid=calculate(Store([],accounts=[{"id":"a", "type":"Investment","currency":"USD","initial_cash":None}]))
    assert invalid["cash"][0]["amount"] is None


def test_read_only_input_objects_and_saved_evidence_are_unchanged():
    store,hub,snapshots=Store(),Hub(),{"USD":fx()}
    before=deepcopy((store.__dict__,hub.histories,snapshots))
    result=calculate(store,hub,snapshots)
    assert result["status"]=="ok"
    assert (store.__dict__,hub.histories,snapshots)==before
    assert JSONResponse(result).status_code==200


def test_actual_local_ledger_prices_and_financial_revision_are_read_only(tmp_path):
    store=LocalPortfolioStore(tmp_path/"portfolio.sqlite3")
    account=store.save_account({"account_id":"Synthetic local account","type":"Investment","currency":"USD","location":"USA","initial_cash":0,
                               "persons":[{"name":"Synthetic","birth_date":"01/01/1990"}]})
    store.add_transaction({"account_db_id":account["id"],"action":"ADD","symbol":"AAA","stock_market":"NASDAQ","asset_class":"EQUITY",
                           "quantity":10,"price_input":100,"trade_date":(TODAY-timedelta(days=180)).isoformat()})
    for row in prices():
        store.save_price({"symbol":"AAA","stock_market":"NASDAQ","asset_class":"EQUITY","currency":"USD","location":"USA",
                          "price_input":row.close,"price_date":row.date.isoformat()})
    before=store.export_data()["data"];token=store.change_token()
    result=build_var(store,Hub(),{"USD":fx()},today=TODAY)
    assert result["status"]=="ok" and result["var_ils"]==pytest.approx(400)
    assert store.export_data()["data"]==before and store.change_token()==token


@pytest.mark.parametrize("values",[[],[True],[float("nan")],[float("inf")],["bad"]])
def test_invalid_scenario_values_fail_with_controlled_error(values):
    with pytest.raises(VarError,match="var_invalid_scenarios"):loss_statistics(values)


def test_input_period_and_fx_container_validation():
    with pytest.raises(VarError,match="var_invalid_period"):calculate(period="all")
    with pytest.raises(VarError,match="var_invalid_fx_history"):build_var(Store(),Hub(),None,today=TODAY)
