"""Independent severe-loss acceptance from synthetic, base-currency raw facts.

Expected amounts below come from the frozen financial equations, not application
scores. Public fund identity evidence is separate from these synthetic amounts.
pytest's normal conftest isolates all stores from runtime data and configuration.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import base64
import json
import math
from pathlib import Path
import subprocess

import pytest

from test_native_account_history_qa import chromium
from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_shared_cash_risk_qa import app_functions


ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-11-14"


def opinion(grade="AA", **changes):
    return {**dict(status="rated", rating=grade, agency="sp", scope="sovereign",
                scale="global", term="long_term", source_kind="agency_public",
                verified=True, stale=False), **changes}


def item(symbol="QA", value=100, *, kind="fund", focus=None, currency="ILS",
         account="a", **metadata):
    asset = "BOND" if kind.endswith("bond") else "EQUITY" if kind == "equity" else "MUTUALFUND"
    result = dict(holding=dict(symbol=symbol, stock_market="QA", currency=currency,
                              quantity=1 if value is None else value, market_value=value,
                              account_id=account, asset_class=asset),
                  stress_risk=dict(security_key=f"{symbol}|QA|{currency}",
                                   valuation_date=AS_OF,
                                   parameters={"instrument_kind": kind}, **metadata))
    if focus:
        result["exposure_profile"] = dict(asset_focus=focus, leverage_type="none",
                                          fx_basis="unhedged", currency_exposures={currency: 1})
    return result


def node(source):
    result = subprocess.run(["node"], input=source, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def calculate(items, *, js_options="", **options):
    settings = {"baseCurrency": "ILS", "asOf": AS_OF, **options}
    return node("const model=require('./web/stress-risk.js');const items="
                + json.dumps(items, allow_nan=False) + ";const options="
                + json.dumps(settings, allow_nan=False) + ";" + js_options
                + "console.log(JSON.stringify(model.calculate(items,options)));" )


def severity(loss, equity):
    return math.floor(min(100, 200 * max(0, loss) / equity) + .5)


def test_conditional_psagot_values_use_nav_loss_and_full_cash_denominator():
    fund_value, cash = 491419 - 38819.65, 38819.65
    fund = item("5139324", fund_value, focus="money_market")
    fund["exposure_profile"].update(as_of="2024-09-24", source_url="https://mayafiles.tase.co.il/rpdf/1618001-1619000/P1618967-00.pdf")
    original = deepcopy(fund)
    result = calculate([fund], cash=cash)
    assert result["status"] == "incomplete" and result["score"] is None
    assert result["provisional_model"] == "portfolio-risk-provisional-v2"
    assert result["provisional_scope"] == "portfolio"
    assert result["provisional_score"] == severity(fund_value * .01, fund_value + cash) == 2
    assert result["provisional_loss"] == pytest.approx(fund_value * .01)
    assert result["provisional_net_equity"] == fund_value + cash
    assert result["provisional_proxy_gross"] == fund_value
    assert result["coverage"]["covered_value_percent"] == pytest.approx(cash / (cash + fund_value) * 100)
    proxy = next(row for row in result["provisional_assumptions"] if row["code"] == "money_market_proxy")
    assert proxy["source_date"] == "2024-09-24" and proxy["loss_fraction"] == .01
    assert any(gap["code"] == "fund_lookthrough" for gap in result["gaps"])
    assert fund == original


@pytest.mark.parametrize("focus,kind,duration,widening", [
    ("government_bond", "sovereign_bond", 5, .02),
    (None, "corporate_bond", 5, .025),
    ("investment_grade_bond", "fund", 5, .015),
    ("high_yield_bond", "fund", 4, .05),
])
def test_bond_proxy_amounts_follow_duration_and_credit_without_fake_agency_grades(focus, kind, duration, widening):
    bond = item(kind=kind, focus=focus)
    result = calculate([bond])
    inflation_loss = -100 * math.expm1(-duration * (.02 + .5 * widening))
    country_loss = -100 * math.expm1(-duration * (.02 if kind == "sovereign_bond" else max(widening, .02)))
    issuer_loss = -100 * math.expm1(-duration * max(.2 / duration, 2 * widening)) if kind == "corporate_bond" else 0
    loss = max(inflation_loss, country_loss, issuer_loss)
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == severity(loss, 100)
    assert not result["rating_evidence"]
    assert any(row["code"] == "bond_duration_proxy" and row["duration_years"] == duration for row in result["provisional_assumptions"])
    if kind != "corporate_bond":
        assert not any(row["name"].startswith("issuer_") for row in result["provisional_scenarios"])


@pytest.mark.parametrize("cash,expected", [(0, 2), (100, 1), (-90, 20), (-99, 100)])
def test_mmf_cash_dilution_and_debt_change_equity_not_missing_evidence_points(cash, expected):
    result = calculate([item(focus="money_market")], cash=cash)
    assert result["provisional_net_equity"] == 100 + cash
    assert result["cash_debt"] == max(0, -cash)
    assert result["provisional_loss"] == pytest.approx(1)
    assert result["provisional_score"] == severity(1, 100 + cash) == expected


def test_foreign_cash_and_mmf_use_compounded_fx_and_nav_shocks():
    cash = calculate([], cashAccounts=[dict(value=100, currency="USD")])
    assert cash["score"] == 30 and cash["stress_loss"] == 15
    fund = calculate([item(currency="USD", focus="money_market")])
    loss = 100 * (1 - (1 - .01) * (1 - .15))
    assert fund["provisional_loss"] == pytest.approx(loss)
    assert fund["provisional_score"] == severity(loss, 100) == 32


def test_mixed_usd_allocation_is_a_joint_scenario_not_a_principal_wipeout():
    holdings = [item("BOND", 33.6, kind="corporate_bond", currency="USD"),
                item("FUND", 29.9, currency="USD", focus="broad_equity")]
    result = calculate(holdings, cashAccounts=[dict(value=36.5, currency="USD")])
    expected = -(33.6 * (math.exp(-5 * .025) * .85 - 1)
                 + 29.9 * (.6 * .85 - 1) + 36.5 * -.15)
    assert result["provisional_net_equity"] == pytest.approx(100)
    assert result["provisional_loss"] == pytest.approx(expected)
    assert result["provisional_score"] == severity(expected, 100) == 57


def test_known_weak_country_is_retained_for_money_fund_and_currency():
    fund = item(focus="money_market", currency="BRL", country={"country_code": "BR", "basis": "economic_exposure"},
                country_rating=opinion("B"))
    fund["stress_risk"]["parameters"]["country_currency"] = "BRL"
    result = calculate([fund])
    expected = 100 * (1 - (1 - .25 * .08) * (1 - .35))
    assert result["provisional_loss"] == pytest.approx(expected)
    assert result["provisional_score"] == severity(expected, 100) == 73


@pytest.mark.parametrize("focus,expected_loss", [(None, 40), ("broad_equity", 40), ("sector_equity", 50)])
def test_fund_manager_is_not_a_concentrated_equity_issuer(focus, expected_loss):
    fund = item(focus=focus, issuer_id="manager:QA")
    result = calculate([fund])
    assert result["provisional_loss"] == pytest.approx(expected_loss)
    assert not any(row["name"].startswith("issuer_") for row in result["provisional_scenarios"])


def test_security_key_concentration_survives_lot_and_account_splitting():
    whole = calculate([item(kind="equity")], cash=100)
    split = calculate([item(value=25, kind="equity", account=str(i)) for i in range(4)], cash=100)
    assert whole["provisional_loss"] == split["provisional_loss"] == pytest.approx(60)
    assert whole["provisional_score"] == split["provisional_score"] == 60


def test_signed_short_and_matched_hedge_keep_directional_risk():
    short = item(value=-100, kind="equity")
    result = calculate([short], cash=200)
    assert result["provisional_loss"] == 100 and result["provisional_score"] == 100
    assert result["provisional_worst_scenario"].startswith("issuer_rally:")
    hedge = calculate([short, item(value=100, kind="equity")], cash=200)
    assert hedge["provisional_loss"] == 0 and hedge["provisional_score"] == 0


@pytest.mark.parametrize("problem", ["value", "cash", "fx", "future", "option", "leverage"])
def test_unknown_monetary_or_nonlinear_scope_is_a_range_not_a_fake_point100(problem):
    fund, options = item(focus="money_market"), dict(cash=100)
    if problem == "value": fund["holding"]["market_value"] = None
    if problem == "cash": options["cash"] = None
    if problem == "fx": options["js_options"] = "options.normalizeField=()=>null;"
    if problem == "future": fund["stress_risk"]["valuation_date"] = "2026-11-15"
    if problem == "option": fund["holding"]["asset_sub_class"] = "OPTION"
    if problem == "leverage": fund["exposure_profile"]["leverage_type"] = "leveraged"
    result = calculate([fund], **options)
    assert result["score"] is None and result["status"] == "incomplete"
    assert result["provisional_scope"] == "known_values"
    assert result["provisional_range"] == {"min": 0, "max": 100}
    assert result["provisional_basis"] == "asset_aware_scenarios"


@pytest.mark.parametrize("mark,code", [("2026-10-01", "stale_valuation"), (None, "undated_valuation")])
def test_reported_finite_stale_or_undated_values_support_only_a_labeled_estimate(mark, code):
    fund = item(focus="money_market")
    fund["stress_risk"]["valuation_date"] = mark
    result = calculate([fund], cash=100)
    assert result["net_equity"] is None and result["score"] is None
    assert result["provisional_scope"] == "portfolio" and result["provisional_net_equity"] == 200
    assert result["provisional_score"] == 1 and result["provisional_loss"] == pytest.approx(1)
    assert any(row["code"] == code for row in result["provisional_assumptions"])


def test_known_and_stale_nonpositive_equity_have_different_claim_boundaries():
    fund = item(focus="money_market")
    current = calculate([fund], cash=-200)
    assert current["score"] == 100 and current["worst_scenario"] == "nonpositive_equity"
    fund["stress_risk"]["valuation_date"] = "2026-10-01"
    stale = calculate([fund], cash=-200)
    assert stale["score"] is None and stale["status"] == "incomplete"
    assert stale["provisional_score"] == 100
    assert stale["provisional_worst_scenario"] == "nonpositive_estimated_equity"


def test_eligible_cashflow_schedule_is_not_discarded_for_an_unrelated_missing_spread():
    bond = item(kind="corporate_bond", issuer_id="legal:QA", credit_rating=opinion(scope="issue"),
                country={"country_code": "IL", "basis": "economic_exposure"}, country_rating=opinion())
    payments = [{"date": "2031-11-14", "amount": 50}, {"date": "2036-11-14", "amount": 1050}]
    bond["stress_risk"]["parameters"].update(
        pricing_model="cashflows_continuous", plain_nominal_noncallable=True,
        continuous_yield=.05, cashflows=payments, country_sensitivity=1,
        country_currency="ILS", as_of=AS_OF)
    legs = [((date.fromisoformat(row["date"]) - date.fromisoformat(AS_OF)).days / 365.25,
             row["amount"]) for row in payments]
    pv = sum(amount * math.exp(-.05 * t) for t, amount in legs)
    duration = sum(t * amount * math.exp(-.05 * t) for t, amount in legs) / pv
    def loss(shift):
        return 100 * (1 - sum(amount * math.exp(-(.05 + shift) * t) for t, amount in legs) / pv)
    expected = max(loss(.02 + .5 * .0075), loss(.015), loss(max(.2 / duration, 2 * .0075)))
    result = calculate([bond])
    assert result["score"] is None and any(row["code"] == "current_spread" for row in result["gaps"])
    assert result["provisional_loss"] == pytest.approx(expected)
    assert not any(row["code"] == "bond_duration_proxy" for row in result["provisional_assumptions"])


@pytest.mark.parametrize("problem", ["derivative_focus", "unsupported_bond", "non_plain_bond"])
def test_explicit_nonlinear_terms_cannot_fall_through_to_an_ordinary_asset_proxy(problem):
    asset = item(focus="derivative") if problem == "derivative_focus" else item(kind="corporate_bond")
    if problem == "unsupported_bond": asset["stress_risk"]["unsupported_bond"] = True
    if problem == "non_plain_bond": asset["stress_risk"]["parameters"]["plain_nominal_noncallable"] = False
    result = calculate([asset], cash=100)
    assert result["score"] is None and result["provisional_scope"] == "known_values"
    assert result["provisional_range"] == {"min": 0, "max": 100}


@pytest.mark.parametrize("focus", ["money_market", "government_bond"])
def test_a_conflicting_fund_profile_never_removes_direct_stock_issuer_risk(focus):
    asset = item(kind="equity", focus=focus)
    result = calculate([asset], cash=100)
    # A direct share remains a share. Fund-only category metadata cannot make
    # its issuer-distress scenario vanish or establish money-market exposure.
    assert result["provisional_scope"] == "portfolio"
    assert result["provisional_loss"] == pytest.approx(60)
    assert result["provisional_score"] == 60
    assert any(row["name"].startswith("issuer_distress:") for row in result["provisional_scenarios"])


def test_names_and_custodian_labels_do_not_establish_a_money_market_class():
    asset = item("CASH-BROKER", issuer_id="manager:Bank")
    asset["holding"].update(name="Money market cash account", account="Bank money market", broker="Cash Broker")
    result = calculate([asset])
    assert result["provisional_loss"] == 40 and result["provisional_score"] == 80
    assert not any(row["code"] == "money_market_proxy" for row in result["provisional_assumptions"])


@pytest.mark.parametrize("grade", ["AAA", "CCC"])
@pytest.mark.parametrize("focus,duration,widening", [("investment_grade_bond", 5, .015), ("high_yield_bond", 4, .05)])
def test_fund_wrapper_rating_cannot_replace_underlying_category_credit_proxy(grade, focus, duration, widening):
    fund = item(focus=focus, issuer_id="manager:QA", credit_rating=opinion(grade, scope="issuer"))
    result = calculate([fund], cash=100)
    loss = max(-100 * math.expm1(-duration * (.02 + .5 * widening)),
               -100 * math.expm1(-duration * max(.02, widening)))
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == severity(loss, 200)
    assert any(row["code"] == "bond_fund_proxy" and row["spread_bps"] == widening * 10000 for row in result["provisional_assumptions"])


def test_fund_manager_domicile_is_not_underlying_economic_country_evidence():
    fund = item(focus="broad_equity", issuer_id="manager:QA",
                country={"country_code": "QA", "basis": "issuer_domicile_proxy"}, country_rating=opinion("CCC"))
    fund["stress_risk"]["parameters"]["country_currency"] = "ILS"
    result = calculate([fund], cash=100)
    assert result["provisional_loss"] == 40 and result["provisional_score"] == 40
    assert any(row["code"] == "country_stress_proxy" for row in result["provisional_assumptions"])


def test_fund_wrapper_bond_terms_are_not_the_underlying_bond_fund_duration():
    fund = item(focus="high_yield_bond")
    fund["stress_risk"]["parameters"].update(
        pricing_model="zero_coupon_continuous", maturity_date="2046-11-14",
        zero_coupon_confirmed=True, plain_nominal_noncallable=True,
        current_spread_bps=50, country_sensitivity=1, as_of=AS_OF)
    result = calculate([fund], cash=100)
    loss = -100 * math.expm1(-4 * .05)
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == severity(loss, 200) == 18
    assert any(row["code"] == "bond_duration_proxy" and row["duration_years"] == 4 for row in result["provisional_assumptions"])


def test_flat_verified_fund_children_keep_same_issuer_alias_when_parent_mark_becomes_stale():
    fund = item(focus="broad_equity")
    children = []
    for symbol, issuer in (("ONE", "sec:123"), ("TWO", "issuer:same legal company")):
        children.append(dict(symbol=symbol, asset_class="EQUITY", currency="ILS", weight=.5,
            stress_risk=dict(security_key=f"{symbol}|QA|ILS", issuer_id=issuer,
                issuer_identity_verified=True, issuer_name_key="same legal company", issuer_legal_jurisdiction="IL",
                country={"country_code": "IL", "basis": "economic_exposure"}, country_rating=opinion(),
                currency_exposures={"ILS": 1}, parameters={"instrument_kind": "equity", "country_currency": "ILS"})))
    fund["stress_risk"].update(lookthrough_verified=True, lookthrough=children)
    verified = calculate([fund], cash=100)
    assert verified["score"] == 60 and verified["stress_loss"] == 60
    fund["stress_risk"]["valuation_date"] = "2026-10-01"
    provisional = calculate([fund], cash=100)
    assert provisional["score"] is None and provisional["provisional_score"] == 60
    assert provisional["provisional_loss"] == 60


@pytest.mark.parametrize("grade,widening", [("AAA", .005), ("BB", .03)])
def test_direct_bond_retains_eligible_issue_credit_while_other_evidence_is_missing(grade, widening):
    bond = item(kind="corporate_bond", credit_rating=opinion(grade, scope="issue"))
    result = calculate([bond])
    loss = max(-100 * math.expm1(-5 * (.02 + .5 * widening)),
               -100 * math.expm1(-5 * max(.2 / 5, 2 * widening)))
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == severity(loss, 100)
    assert not any(row["code"] == "unrated_credit_proxy" for row in result["provisional_assumptions"])


@pytest.mark.parametrize("as_subclass", [False, True])
@pytest.mark.parametrize("alias", ["MONEY_MARKET_FUND", "BOND_FUND", "EQUITY_FUND"])
def test_explicit_fund_class_and_subclass_aliases_preserve_economic_proxy_parity(alias, as_subclass):
    asset = item()
    asset["stress_risk"]["parameters"] = {}
    asset["holding"]["asset_class"] = "UNKNOWN" if as_subclass else alias
    if as_subclass: asset["holding"]["asset_sub_class"] = alias
    result = calculate([asset], cash=100)
    loss = 1 if alias == "MONEY_MARKET_FUND" else -100 * math.expm1(-5 * (.02 + .5 * .025)) if alias == "BOND_FUND" else 40
    assert result["provisional_scope"] == "portfolio"
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == severity(loss, 200)
    assert not any(row["name"].startswith("issuer_") for row in result["provisional_scenarios"])


def test_unenabled_manual_country_sensitivity_cannot_silently_reduce_direct_bond_risk():
    bond = item(kind="corporate_bond", credit_rating=opinion("AAA", scope="issue"),
                country={"country_code": "QA", "basis": "economic_exposure"}, country_rating=opinion("CCC"),
                parameters_verification="user_entered")
    bond["stress_risk"]["parameters"].update(country_sensitivity=0, country_currency="ILS")
    result = calculate([bond])
    loss = -100 * math.expm1(-5 * .12)
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == severity(loss, 100) == 90
    assert any(row["code"] == "country_sensitivity_proxy" for row in result["provisional_assumptions"])


def test_fund_wrapper_country_sensitivity_cannot_override_underlying_category_proxy():
    fund = item(focus="high_yield_bond", country={"country_code": "QA", "basis": "economic_exposure"}, country_rating=opinion("CCC"))
    fund["stress_risk"]["parameters"].update(country_sensitivity=0, country_currency="ILS")
    result = calculate([fund], cash=100)
    loss = -100 * math.expm1(-4 * .12)
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == severity(loss, 200) == 38
    assert any(row["code"] == "country_sensitivity_proxy" for row in result["provisional_assumptions"])


@pytest.mark.parametrize("agency,grade", [("sp", "D"), ("sp", "SD"), ("fitch", "RD"), ("moodys", "C")])
def test_known_default_credit_requires_a_recovery_model_instead_of_an_unrated_spread(agency, grade):
    bond = item(kind="corporate_bond", credit_rating=opinion(grade, agency=agency, scope="issue"))
    result = calculate([bond], cash=100)
    assert result["score"] is None and result["provisional_scope"] == "known_values"
    assert result["provisional_range"] == {"min": 0, "max": 100}


def test_fund_manager_default_does_not_become_underlying_bond_fund_default():
    fund = item(focus="high_yield_bond", credit_rating=opinion("D", scope="issuer"))
    result = calculate([fund], cash=100)
    loss = -100 * math.expm1(-4 * .05)
    assert result["provisional_scope"] == "portfolio"
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == 18


@pytest.mark.parametrize("state_", ["current", "stale", "national", "short_term", "future", "withdrawn"])
def test_cached_default_attachment_preserves_the_model_boundary_only_for_eligible_evidence(tmp_path, state_):
    from app.local_portfolio import LocalPortfolioStore
    from app.stress_risk_inputs import StressRiskInputs
    candidate = dict(security_key="QA|QA|ILS", symbol="QA", stock_market="QA", currency="ILS",
                     asset_class="BOND", issuer_name="Synthetic Legal Issuer", issuer_identity_verified=True)
    rating = opinion("D", scope="issue", rating_type="senior_unsecured",
                     entity_name="Synthetic Legal Issuer", security_key=candidate["security_key"],
                     fetched_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat())
    if state_ == "stale": rating["stale"] = True
    if state_ == "national": rating["scale"] = "national"
    if state_ == "short_term": rating["term"] = "short_term"
    if state_ == "future": rating["fetched_at"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    if state_ == "withdrawn": rating["status"] = "withdrawn"
    original = deepcopy(rating)
    store = LocalPortfolioStore(tmp_path / "default-credit-qa.sqlite3")
    service = StressRiskInputs(store=lambda: store, inventory=lambda: [candidate],
                               credit=lambda _: {"ratings": [deepcopy(rating)]},
                               sovereign=lambda _: {}, countries=lambda _: {})
    attached = service.read(candidate)
    assert attached["credit_rating"] is None
    asset = item(kind="corporate_bond")
    asset["stress_risk"] = {**attached, "valuation_date": AS_OF}
    result = calculate([asset], cash=100)
    if state_ == "current":
        assert result["provisional_scope"] == "known_values"
        assert result["provisional_range"] == {"min": 0, "max": 100}
    else:
        assert result["provisional_scope"] == "portfolio"
        assert result["provisional_loss"] == pytest.approx(-100 * math.expm1(-5 * .05))
    assert rating == original


@pytest.mark.parametrize("mode", ["native_base", "foreign_exposed", "foreign_hedged", "foreign_hedged_with_native_cash"])
def test_sovereign_recovery_attachment_keeps_obligation_and_systemic_currency_axes_separate(tmp_path, mode):
    from app.local_portfolio import LocalPortfolioStore
    from app.stress_risk_inputs import StressRiskInputs
    candidate = dict(security_key="QA|QA|ILS", symbol="QA", stock_market="QA", currency="ILS",
                     asset_class="BOND", issuer_name="Synthetic Sovereign", issuer_identity_verified=True)
    timestamp = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    sovereign = [opinion("AAA", currency_basis="local_currency", fetched_at=timestamp),
                 opinion("D", currency_basis="foreign_currency", fetched_at=timestamp)]
    store = LocalPortfolioStore(tmp_path / "sovereign-recovery-qa.sqlite3")
    service = StressRiskInputs(store=lambda: store, inventory=lambda: [candidate], credit=lambda _: {},
                               sovereign=lambda _: {"ratings": deepcopy(sovereign)},
                               countries=lambda _: {"country_code": "IL", "source_kind": "government_public"})
    service.publish_evidence(candidate, [dict(field=field, value=value, as_of=AS_OF, basis="reported",
        source_kind="government_public", source_url="https://www.treasurydirect.gov/qa-synthetic")
        for field, value in {"instrument_kind": "sovereign_bond", "sovereign_currency_basis": "local_currency",
                             "country_currency": "ILS", "country_basis": "economic_exposure"}.items()])
    attached = service.read(candidate)
    assert attached["requires_recovery_model"] is False
    assert attached["country_requires_recovery_model"] is True
    assert attached["sovereign_rating"]["rating"] == "AAA"
    asset = item(kind="sovereign_bond")
    hedge = mode in {"foreign_hedged", "foreign_hedged_with_native_cash"}
    asset["stress_risk"] = {**attached, "valuation_date": AS_OF,
                             "currency_exposures": {"USD" if hedge else "ILS": 1}}
    base = "ILS" if mode == "native_base" else "USD"
    cash = [dict(value=100, currency="ILS" if mode == "foreign_hedged_with_native_cash" else base)]
    result = calculate([asset], baseCurrency=base, cashAccounts=cash)
    if mode in {"foreign_exposed", "foreign_hedged_with_native_cash"}:
        assert result["provisional_scope"] == "known_values"
        assert result["provisional_range"] == {"min": 0, "max": 100}
    else:
        loss = -100 * math.expm1(-5 * (.02 + .5 * .005))
        assert result["provisional_scope"] == "portfolio"
        assert result["provisional_loss"] == pytest.approx(loss)
        assert result["provisional_score"] == severity(loss, 200) == 11


@pytest.mark.parametrize("opt_in", [False, True])
def test_manual_default_is_not_applied_as_verified_evidence_without_assumption_opt_in(tmp_path, opt_in):
    from app.local_portfolio import LocalPortfolioStore
    from app.stress_risk_inputs import StressRiskInputs
    candidate = dict(security_key="QA|QA|ILS", symbol="QA", stock_market="QA", currency="ILS",
                     asset_class="BOND", issuer_name="Synthetic Legal Issuer", issuer_identity_verified=True)
    timestamp = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    rating = opinion("D", scope="issue", rating_type="senior_unsecured", source_kind="manual",
                     manual_override=True, updated_at=timestamp, entity_name="Synthetic Legal Issuer")
    store = LocalPortfolioStore(tmp_path / "manual-recovery-qa.sqlite3")
    service = StressRiskInputs(store=lambda: store, inventory=lambda: [candidate],
                               credit=lambda _: {"ratings": [deepcopy(rating)]},
                               sovereign=lambda _: {}, countries=lambda _: {})
    if opt_in:
        current = service.read(candidate)
        service.update(dict(security_key=candidate["security_key"], expected_identity=current["identity_token"], expected_revision=0,
            parameters={"instrument_kind": "corporate_bond", "assumptions_enabled": True,
                        "as_of": date.today().isoformat(), "notes": "Synthetic explicit assumption"}), {"id": "qa"})
    attached = service.read(candidate)
    assert attached["credit_rating"] is None
    assert attached["requires_recovery_model"] is opt_in
    asset = item(kind="corporate_bond")
    asset["stress_risk"] = {**attached, "valuation_date": AS_OF}
    result = calculate([asset], cash=100)
    assert result["provisional_scope"] == ("known_values" if opt_in else "portfolio")


@pytest.mark.parametrize("issue_status", ["rated", "withdrawn"])
def test_recovery_source_precedence_uses_an_applicable_issue_before_issuer_fallback(tmp_path, issue_status):
    from app.local_portfolio import LocalPortfolioStore
    from app.stress_risk_inputs import StressRiskInputs
    candidate = dict(security_key="QA|QA|ILS", symbol="QA", stock_market="QA", currency="ILS",
                     asset_class="BOND", issuer_name="Synthetic Legal Issuer", issuer_identity_verified=True)
    timestamp = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    ratings = [opinion("D", scope="issuer", rating_type="issuer", fetched_at=timestamp),
               opinion("AAA", scope="issue", rating_type="senior_unsecured", fetched_at=timestamp, status=issue_status)]
    store = LocalPortfolioStore(tmp_path / "issue-recovery-qa.sqlite3")
    service = StressRiskInputs(store=lambda: store, inventory=lambda: [candidate],
                               credit=lambda _: {"ratings": deepcopy(ratings)}, sovereign=lambda _: {}, countries=lambda _: {})
    attached = service.read(candidate)
    assert attached["requires_recovery_model"] is (issue_status == "withdrawn")
    if issue_status == "rated":
        assert attached["credit_rating"]["rating"] == "AAA"
        assert attached["credit_rating"]["scope"] == "issue"
    else:
        assert attached["credit_rating"] is None


def test_future_performing_issue_cannot_suppress_current_matched_sovereign_recovery_evidence(tmp_path):
    from app.local_portfolio import LocalPortfolioStore
    from app.stress_risk_inputs import StressRiskInputs
    candidate = dict(security_key="QA|QA|ILS", symbol="QA", stock_market="QA", currency="ILS",
                     asset_class="BOND", issuer_name="Synthetic Sovereign", issuer_identity_verified=True)
    timestamp = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    future_issue = opinion("AAA", scope="issue", rating_type="senior_unsecured", fetched_at=timestamp,
                           rating_date=(date.today() + timedelta(days=1)).isoformat())
    sovereign = [opinion("D", currency_basis="local_currency", fetched_at=timestamp),
                 opinion("AAA", currency_basis="foreign_currency", fetched_at=timestamp)]
    store = LocalPortfolioStore(tmp_path / "future-issue-recovery-qa.sqlite3")
    service = StressRiskInputs(store=lambda: store, inventory=lambda: [candidate],
        credit=lambda _: {"ratings": [deepcopy(future_issue)]},
        sovereign=lambda _: {"ratings": deepcopy(sovereign)}, countries=lambda _: {"country_code": "IL"})
    service.publish_evidence(candidate, [dict(field=field, value=value, as_of=AS_OF, basis="reported",
        source_kind="government_public", source_url="https://www.treasurydirect.gov/qa-synthetic")
        for field, value in {"instrument_kind": "sovereign_bond", "sovereign_currency_basis": "local_currency",
                             "country_currency": "ILS", "country_basis": "economic_exposure"}.items()])
    attached = service.read(candidate)
    assert attached["credit_rating"] is None
    assert attached["requires_recovery_model"] is True
    assert attached["recovery_evidence"]["currency_basis"] == "local_currency"
    asset = item(kind="sovereign_bond")
    asset["stress_risk"] = {**attached, "valuation_date": AS_OF}
    result = calculate([asset], cash=100)
    assert result["provisional_scope"] == "known_values"
    assert result["provisional_range"] == {"min": 0, "max": 100}


@pytest.mark.parametrize("focus", ["government_bond", "money_market"])
def test_fund_underlying_economic_country_recovery_is_relevant_even_in_base_currency(tmp_path, focus):
    from app.local_portfolio import LocalPortfolioStore
    from app.stress_risk_inputs import StressRiskInputs
    candidate = dict(security_key="QA|QA|ILS", symbol="QA", stock_market="QA", currency="ILS",
                     asset_class="MUTUALFUND", issuer_name="Synthetic Manager", issuer_identity_verified=True)
    timestamp = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    store = LocalPortfolioStore(tmp_path / "fund-country-recovery-qa.sqlite3")
    service = StressRiskInputs(store=lambda: store, inventory=lambda: [candidate], credit=lambda _: {},
        sovereign=lambda _: {"ratings": [opinion("D", currency_basis="foreign_currency", fetched_at=timestamp)]},
        countries=lambda _: {"country_code": "IL"})
    service.publish_evidence(candidate, [dict(field=field, value=value, as_of=AS_OF, basis="reported",
        source_kind="government_public", source_url="https://www.treasurydirect.gov/qa-synthetic")
        for field, value in {"instrument_kind": "fund", "country_currency": "ILS", "country_basis": "economic_exposure"}.items()])
    attached = service.read(candidate)
    assert attached["requires_recovery_model"] is False
    assert attached["country_requires_recovery_model"] is True
    asset = item(focus=focus)
    asset["stress_risk"] = {**attached, "valuation_date": AS_OF}
    result = calculate([asset], cash=100)
    assert result["provisional_scope"] == "known_values"
    assert result["provisional_range"] == {"min": 0, "max": 100}


@pytest.mark.parametrize("opt_in", [False, True])
def test_unenabled_manual_plain_bond_checkbox_does_not_establish_verified_nonplain_terms(opt_in):
    bond = item(kind="corporate_bond", parameters_verification="user_entered")
    bond["stress_risk"]["parameters"].update(plain_nominal_noncallable=False, assumptions_enabled=opt_in)
    result = calculate([bond], cash=100)
    if opt_in:
        assert result["provisional_scope"] == "known_values"
        assert result["provisional_range"] == {"min": 0, "max": 100}
    else:
        loss = -100 * math.expm1(-5 * .05)
        assert result["provisional_scope"] == "portfolio"
        assert result["provisional_loss"] == pytest.approx(loss)
        assert result["provisional_score"] == severity(loss, 200) == 22


def test_dashboard_wrappers_preserve_bank_cash_exclude_employee_cash_and_disclose_savings_scope():
    functions = app_functions("riskStrictBaseValue", "riskScoreForItems", "portfolioRiskSnapshot", "portfolioAccounts", "isEquityCompAccount")
    asset = item(value=900, focus="money_market")
    result = node("""
const PortfolioStressRisk=require('./web/stress-risk.js');
const state={baseCurrency:'ILS',riskAsOf:'2026-11-14',fxRates:{},localFunds:[{id:'savings',amount:10000000}],
 localAccounts:[{id:'a',type:'Investment',currency:'ILS',initial_cash:100},
 {id:'bank',type:'Bank',currency:'ILS',initial_cash:100},
 {id:'esop',type:'ESOP',currency:'ILS',initial_cash:10000000}]};
const sum=values=>values.reduce((a,b)=>a+b,0),accountNativeCashBalance=account=>account.initial_cash;
const cleanSourceLabel=value=>value,accountLabel=account=>account.id,accountHorizonYears=()=>20,riskAllocationForItems=()=>({});
""" + functions + "\nconst result=portfolioRiskSnapshot(" + json.dumps([asset]) + ");console.log(JSON.stringify(result));")
    risk = result["total"]
    assert risk["provisional_net_equity"] == 1100
    assert risk["provisional_loss"] == pytest.approx(9)
    assert risk["scope"] == "securities_and_cash"
    assert risk["coverage"]["unmodeled_savings_count"] == 1
    assert risk["coverage"]["whole_wealth_available"] is False
    assert {row["key"] for row in result["accounts"]} == {"a", "bank"}


def test_history_client_and_server_retain_the_new_model_metadata_without_mutation():
    from app import risk_history
    risk = calculate([item(focus="money_market")], cash=100)
    script = "const document={addEventListener(){}};\n" + (ROOT / "web/risk-history-ui.js").read_text()
    record = node(script + "\nconsole.log(JSON.stringify(riskHistoryRiskRecord(" + json.dumps(risk) + ")));" )
    validated = risk_history._stress_risk(record)
    for field in risk:
        if field.startswith("provisional_"):
            assert record[field] == risk[field]
            assert validated[field] == risk[field]
    record["provisional_assumptions"][0]["code"] = "changed-later"
    assert validated["provisional_assumptions"] == risk["provisional_assumptions"]


@pytest.mark.parametrize("change", ["bad_formula", "range_without_scope", "bad_range", "boolean_score", "null_equity"])
def test_history_rejects_invalid_or_promoted_v2_monetary_metadata(change):
    from app import risk_history
    risk = calculate([item(focus="money_market")], cash=100)
    if change == "bad_formula": risk["provisional_score"] = 50
    if change == "range_without_scope": risk["provisional_range"] = {"min": 0, "max": 100}
    if change == "bad_range": risk.update(provisional_scope="known_values", provisional_range={"min": 0, "max": 99})
    if change == "boolean_score": risk["provisional_score"] = True
    if change == "null_equity": risk["provisional_net_equity"] = None
    with pytest.raises(risk_history.RiskHistoryError):
        risk_history._stress_risk(risk)


def browser_fixture(tmp_path, language):
    fixture = cash_browser_document(tmp_path, language)
    holdings = [item("5139324", 900, focus="money_market", account="qa-ils"),
                item("QA-BOND", 105, kind="corporate_bond", currency="USD", account="qa-usd"),
                item("QA-FUND", 93.4375, focus="broad_equity", currency="USD", account="qa-usd")]
    # Explicit declared category must survive generic imported fund metadata.
    holdings[0]["holding"]["asset_class"] = "FUND"
    holdings[0]["stress_risk"]["valuation_date"] = "2026-10-01"
    for row in holdings:
        row["holding"].update(account_type="Investment", location="USA", account="QA account",
                              cost_basis=row["holding"]["market_value"], unrealized_profit=0)
    setup = r'''
qa.holdings=QA_HOLDINGS;
state.localAccounts=[
 {id:'qa-ils',username:'QA ILS cash fund',account_id:'QA-ILS',type:'Investment',location:'Israel',currency:'ILS',initial_cash:100,persons:[]},
 {id:'qa-usd',username:'QA USD mixed account',account_id:'QA-USD',type:'Investment',location:'USA',currency:'USD',initial_cash:114.0625,persons:[]}
];
state.localTransactions=[];state.items=state.allPortfolioItems=qa.holdings;
state.baseCurrency='ILS';state.fxRates={'USD/ILS':3.2};state.riskAsOf='2026-11-14';state.localFunds=[];
state.dashboard=defaultDashboard();
state.dashboard.widgets=state.dashboard.widgets.map(widget=>({...widget,view:widget.id==='portfolio_value'?'basic':'hidden'}));
qa.writeCount=0;
api=async(path,options={})=>{
 qa.calls.push(path);if(options.method&&options.method!=='GET')qa.writeCount++;
 if(path.includes('risk-input-retrieval-schedule'))return{enabled:false,mode:'api_then_ai',security_keys:null,timezone:'UTC',schedule_config:{frequency:'weekly',weekdays:[0],hour:8,minute:0}};
 if(path.endsWith('/candidates'))return{items:[{security_key:'5139324|QA|ILS',symbol:'5139324',stock_market:'QA',currency:'ILS'}]};
 return{items:[]};
};
qa.render=()=>{const restore=preservePortfolioViewport();try{renderAnalytics(qa.holdings);PortfolioI18n.applyToDocument(state.language);}finally{restore();}};
qa.render();PortfolioI18n.observe();qa.fixtureReady=true;
'''.replace("QA_HOLDINGS", json.dumps(holdings))
    app = tmp_path / "cash-app.js"
    app.write_text(app.read_text() + "\n" + setup)
    return fixture


def settle(command):
    command("Runtime.evaluate", {"expression": "new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))", "awaitPromise": True})


@pytest.mark.parametrize("language,width", [(language, width) for language in ("en", "he") for width in (1440, 390, 320)])
def test_actual_dashboard_risk_meaning_recovery_and_reading_context(tmp_path, chromium, language, width):
    command, evaluate = chromium
    fixture = browser_fixture(tmp_path, language)
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": fixture.as_uri()})
    browser_wait(evaluate, "window.qa?.fixtureReady===true||!!window.qa?.errors?.length")
    assert evaluate("qa.errors") == []
    settle(command)
    result = evaluate("state.riskSnapshot.accounts.map(row=>({key:row.key,risk:row.risk}))")
    assert next(row["risk"]["provisional_score"] for row in result if row["key"] == "qa-ils") == 2
    assert next(row["risk"]["provisional_score"] for row in result if row["key"] == "qa-usd") == 57
    total = evaluate("state.riskSnapshot.total")
    loss = -(336 * (math.exp(-5 * .025) * .85 - 1) + 299 * (.6 * .85 - 1) + 365 * -.15)
    assert total["provisional_net_equity"] == pytest.approx(2000)
    assert total["provisional_loss"] == pytest.approx(loss)
    assert total["provisional_score"] == severity(loss, 2000) == 29
    evaluate("qa.badge=document.querySelector('[data-account-summary=qa-ils] .risk-badge');qa.badge.scrollIntoView({block:'center'});qa.badge.focus()")
    browser_wait(evaluate, "!$('riskBadgeExplanation').hidden")
    tooltip = evaluate("$('riskBadgeExplanation').textContent")
    assert "9.00" in tooltip and "01/10/2026" in tooltip and "5139324" in tooltip
    assert not any(word in tooltip for word in ("100% of unmodeled", "precautionary ceiling", "undefined", "NaN"))
    if language == "he":
        assert not any(word in tooltip for word in ("Money-market", "Estimate assumptions", "Saved price", "Missing risk inputs", "generic:"))
    else:
        assert not any("א" <= letter <= "ת" for letter in tooltip)
    geometry = evaluate("(()=>{const b=qa.badge.getBoundingClientRect(),c=qa.badge.closest('.account-summary-card').getBoundingClientRect(),p=$('riskBadgeExplanation').getBoundingClientRect();return{contained:b.left>=c.left&&b.right<=c.right,overflow:document.documentElement.scrollWidth-innerWidth,popup:p.left>=0&&p.right<=innerWidth&&p.bottom<=innerHeight}})()")
    assert geometry["contained"] and geometry["overflow"] <= 1 and geometry["popup"], geometry
    evidence = ROOT / ".runtime/cash-fund-risk-fix/qa"
    if evidence.exists():
        (evidence / f"tooltip-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
    if evaluate("$('riskBadgeExplanation').scrollHeight>$('riskBadgeExplanation').clientHeight"):
        command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "End", "code": "End", "windowsVirtualKeyCode": 35})
        assert evaluate("$('riskBadgeExplanation').scrollTop") > 0
        command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Home", "code": "Home", "windowsVirtualKeyCode": 36})
        assert evaluate("$('riskBadgeExplanation').scrollTop") == 0
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
    browser_wait(evaluate, "$('riskBadgeExplanation').hidden")
    center = evaluate("(()=>{const r=qa.badge.getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()")
    command("Emulation.setTouchEmulationEnabled", {"enabled": True})
    for visible in (True, False):
        command("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{**center, "id": 0}]})
        command("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        browser_wait(evaluate, "!$('riskBadgeExplanation').hidden", visible)
    command("Emulation.setTouchEmulationEnabled", {"enabled": False})
    evaluate("qa.gaps=document.querySelector('[data-account-summary=qa-ils] .stress-risk-gaps');qa.gaps.open=true;qa.summary=qa.gaps.querySelector('summary');qa.summary.focus();qa.summary.scrollIntoView({block:'center'});")
    settle(command)
    before = evaluate("({y:scrollY,top:qa.summary.getBoundingClientRect().top})")
    evaluate("for(let i=0;i<3;i++)qa.render()")
    settle(command)
    assert evaluate("document.querySelector('[data-account-summary=qa-ils] .stress-risk-gaps').open")
    assert evaluate("document.activeElement.matches('[data-account-summary=qa-ils] .stress-risk-gaps>summary')")
    after = evaluate("({y:scrollY,top:document.activeElement.getBoundingClientRect().top})")
    assert abs(before["y"] - after["y"]) <= 1 and abs(before["top"] - after["top"]) <= 1, (before, after)
    for mode in ("run", "schedule"):
        evaluate(f"document.querySelector('[data-account-summary=qa-ils] [data-open-risk-input-retrieval={mode}]').click()")
        browser_wait(evaluate, "!$('riskRetrievalModal').hidden&&!$('startRiskRetrieval').disabled")
        assert evaluate("$('riskRetrievalMode').value") == "api_then_ai"
        assert evaluate("[...$('riskRetrievalMode').options].map(row=>row.value)") == ["api_then_ai", "api", "ai"]
        assert evaluate("$('riskRetrievalScheduleDetails').open") is (mode == "schedule")
        evaluate("closeModal($('riskRetrievalModal'))")
    assert evaluate("qa.writeCount") == 0
    assert evaluate("qa.errors") == []
    # Artifacts are synthetic and temporary unless the explicit evidence path is requested.
    if evidence.exists():
        (evidence / f"dashboard-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
