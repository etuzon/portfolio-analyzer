"""Independent acceptance for the rating-aware capital-loss model.

All amounts, legal entities and observations here are synthetic. Expected prices
are calculated from contractual payments and declared scenario shocks; neither
implementation-produced scores nor saved portfolio data are an oracle. The
normal pytest conftest guard must run before importing application modules.
"""
from concurrent.futures import ThreadPoolExecutor
import base64
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import subprocess
import time

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from app import risk_history
from app.local_portfolio import LocalPortfolioStore
from app.stress_risk_inputs import StressRiskInputs, select_rating
from test_native_account_history_qa import chromium
from test_shared_cash_risk_qa import app_functions


ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-11-14"
MATURITY = "2032-11-14"


def opinion(grade="AAA", scope="sovereign", **changes):
    return {**dict(agency="sp", status="rated", rating=grade, scope=scope,
                rating_type="issuer" if scope != "issue" else "senior_unsecured",
                scale="global", term="long_term", verified=True, eligible=True,
                verification_status="verified", source_kind="agency_public",
                fetched_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
                stale=False, outlook="stable", watch="none"), **changes}


def security(symbol="TEST", value=100, *, grade="AAA", kind="sovereign_bond", country="US", currency="USD", account="a"):
    selected = opinion(grade, "sovereign" if kind == "sovereign_bond" else "issue")
    if kind == "sovereign_bond":
        selected["currency_basis"] = "local_currency"
    params = dict(instrument_kind=kind, country_currency=currency, country_basis="economic_exposure", as_of=AS_OF)
    if kind.endswith("bond"):
        params.update(pricing_model="zero_coupon_continuous", maturity_date=MATURITY,
                      zero_coupon_confirmed=True, plain_nominal_noncallable=True,
                      current_spread_bps=45, country_sensitivity=1,
                      sovereign_currency_basis="local_currency")
    return dict(holding=dict(symbol=symbol, stock_market="NYSE", currency=currency,
                             account_id=account, asset_class="BOND" if kind.endswith("bond") else "EQUITY",
                             quantity=value, market_value=value),
                stress_risk=dict(security_key=f"{symbol}|NYSE|{currency}", valuation_date=AS_OF,
                                 issuer_id=f"sovereign:{country}" if kind == "sovereign_bond" else f"legal:{symbol}",
                                 country=dict(country_code=country, basis="economic_exposure"),
                                 parameters=params, currency_exposures={currency: 1},
                                 credit_rating=selected if kind == "corporate_bond" else None,
                                 sovereign_rating=selected if kind == "sovereign_bond" else None,
                                 country_rating=opinion("AAA")))


def node(script):
    result = subprocess.run(["node"], input=script, cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def calculate(items, **options):
    settings = {"baseCurrency": "USD", "asOf": AS_OF, **options}
    return node("const risk=require('./web/stress-risk.js');console.log(JSON.stringify(risk.calculate("
                + json.dumps(items, allow_nan=False) + "," + json.dumps(settings, allow_nan=False) + ")));" )


def elapsed(payment):
    return (date.fromisoformat(payment) - date.fromisoformat(AS_OF)).days / 365.25


def severity(loss_fraction):
    # Positive values use ordinary nearest-integer rounding, including .5 up.
    return math.floor(min(100, max(0, 200 * loss_fraction)) + .5)


@pytest.mark.parametrize("grade,widen,country_widen", [("AAA", .005, .01), ("BBB", .015, .03), ("BB", .03, .05)])
def test_independent_sovereign_prices_include_one_credit_axis(grade, widen, country_widen):
    item = security(grade=grade)
    result = calculate([item])
    prices = {s["name"]: s["pnl"] for s in result["scenarios"]}
    t = elapsed(MATURITY)
    rates_loss = 1 - math.exp(-t * (.02 + .5 * widen))
    own_country_loss = 1 - math.exp(-t * country_widen)
    expected = max(rates_loss, own_country_loss)
    assert result["score"] == severity(expected)
    assert result["loss_pct"] == pytest.approx(100 * expected)
    assert prices["inflation:fixed"] == pytest.approx(-100 * rates_loss)
    assert prices["country_crisis:US"] == pytest.approx(-100 * own_country_loss)
    assert not any(name.startswith("issuer_") for name in prices)
    assert result["rating_evidence"][0]["scope"] == "sovereign"


@pytest.mark.parametrize("grade,widen", [("AAA", .005), ("BBB", .015), ("BB", .03)])
def test_independent_corporate_rating_sensitivity_uses_joint_rates_and_credit(grade, widen):
    # Separate legal borrowers remove the single-name default-like scenario as
    # the binding case. Country rating remains AAA for every borrower.
    items = [security(f"BORROWER{i}", 5, grade=grade, kind="corporate_bond") for i in range(20)]
    result = calculate(items)
    expected_loss = 1 - math.exp(-elapsed(MATURITY) * (.02 + .5 * widen))
    assert result["score"] == severity(expected_loss)
    assert result["loss_pct"] == pytest.approx(100 * expected_loss)
    assert result["worst_scenario"] == "inflation:fixed"


def test_actual_coupon_schedule_drives_price_and_issuer_stress_duration():
    item = security(kind="corporate_bond")
    flows = [{"date": "2027-05-14", "amount": 2}, {"date": "2029-11-14", "amount": 7},
             {"date": "2032-11-14", "amount": 103}]
    p = item["stress_risk"]["parameters"]
    p.update(pricing_model="cashflows_continuous", cashflows=flows, continuous_yield=.037)
    # A misleading maturity must not replace the PV-weighted cash-flow duration.
    p["maturity_date"] = "2099-11-14"
    result = calculate([item])
    pv = lambda shift: sum(c["amount"] * math.exp(-(.037 + shift) * elapsed(c["date"])) for c in flows)
    duration = sum(elapsed(c["date"]) * c["amount"] * math.exp(-.037 * elapsed(c["date"])) for c in flows) / pv(0)
    distress_return = pv(max(.2 / duration, 2 * .005)) / pv(0) - 1
    rate_return = pv(.02 + .5 * .005) / pv(0) - 1
    scenarios = {s["name"]: s for s in result["scenarios"]}
    assert scenarios["issuer_distress:legal:TEST"]["pnl"] == pytest.approx(100 * distress_return)
    assert scenarios["inflation:fixed"]["pnl"] == pytest.approx(100 * rate_return)
    assert result["score"] == severity(-min(distress_return, rate_return))
    assert "assumptions" in result


def test_lc_fc_is_relative_to_obligation_and_issue_grade_has_precedence():
    item = security(grade="BBB", country="IL", currency="ILS")
    m = item["stress_risk"]
    m["sovereign_rating"] = opinion("BBB", "issue", currency_basis="local_currency")
    m["sovereign_ratings"] = {"local_currency": opinion("AAA", currency_basis="local_currency"),
                              "foreign_currency": opinion("BB", currency_basis="foreign_currency")}
    m["parameters"]["sovereign_currency_basis"] = "local_currency"
    for base in ("USD", "ILS"):
        result = calculate([item], baseCurrency=base)
        assert result["score"] is not None
        instrument = next(row for row in result["rating_evidence"] if row["role"] == "instrument_credit")
        assert instrument["scope"] == "issue" and instrument["rating"] == "BBB"
        if base == "ILS":
            # Exact sovereign issue priority applies to its country credit
            # repricing too. The separate FC issuer grade governs crisis FX.
            assert result["score"] == severity(1 - math.exp(-elapsed(MATURITY) * .03))
    m["sovereign_rating"]["currency_basis"] = "foreign_currency"
    wrong_basis = calculate([item])
    assert wrong_basis["score"] is None
    assert "sovereign_currency_basis" in {gap["code"] for gap in wrong_basis["gaps"]}


def test_negative_signals_do_not_change_baseline_or_add_two_downgrades():
    item = security(grade="BBB")
    baseline = calculate([item])
    item["stress_risk"]["sovereign_rating"].update(outlook="negative", watch="negative")
    result = calculate([item])
    one_bucket_loss = 1 - math.exp(-elapsed(MATURITY) * .05)  # BBB -> BB country crisis.
    assert result["score"] == baseline["score"]
    assert result["forward_sensitivity"]["score"] == severity(one_bucket_loss)
    assert result["forward_sensitivity"]["loss_pct"] == pytest.approx(100 * one_bucket_loss)
    assert item["stress_risk"]["sovereign_rating"]["rating"] == "BBB"
    item["stress_risk"]["sovereign_rating"].update(outlook_stale=True, watch_stale=True)
    assert "forward_sensitivity" not in calculate([item])


def test_missing_leg_keeps_denominator_and_recovers_without_fabricated_parameters():
    complete = security("KNOWN", 40)
    unknown = security("UNKNOWN", 60)
    del unknown["stress_risk"]["parameters"]["pricing_model"]
    partial = calculate([complete, unknown])
    assert partial["score"] is None and partial["estimated_score"] is None
    assert partial["net_equity"] == 100
    assert partial["coverage"]["covered_value_percent"] == 40
    assert partial["coverage"]["known_gross_value"] == 100
    assert partial["partial_stress_loss"] > 0
    unknown["stress_risk"]["parameters"]["pricing_model"] = "zero_coupon_continuous"
    assert calculate([complete, unknown])["score"] == calculate([security()])["score"]
    # Explicit couponless confirmation is required even with a maturity date.
    del unknown["stress_risk"]["parameters"]["zero_coupon_confirmed"]
    assert calculate([complete, unknown])["score"] is None


@pytest.mark.parametrize("observed", [None, "2026-11-06", "2026-11-15"])
def test_bond_current_risk_parameters_cannot_be_undated_stale_or_future(observed):
    item = security()
    p = item["stress_risk"]["parameters"]
    if observed is None:
        del p["as_of"]
    else:
        p["as_of"] = observed
    item["stress_risk"]["as_of"] = AS_OF  # Retrieval does not refresh observation.
    result = calculate([item])
    assert result["score"] is None and result["estimated_score"] is None
    assert result["coverage"]["complete"] is False
    assert result["gaps"]


def test_user_parameters_and_manual_grade_never_become_verified_headline():
    item = security(grade="BBB")
    item["stress_risk"]["parameters_verification"] = "user_entered"
    item["stress_risk"]["sovereign_rating"].update(manual_override=True, verified=False,
                                                   verification_status="user_entered", source_kind="manual")
    result = calculate([item])
    assert result["score"] is None and result["estimated_score"] is None
    item["stress_risk"]["parameters"]["assumptions_enabled"] = True
    result = calculate([item])
    assert result["score"] is None and result["estimated_score"] == 33
    assert result["status"] == "estimate"
    assert {a["code"] for a in result["assumptions"]} >= {"manual_rating", "user_parameters"}
    assert all(row.get("verification_status") == "user_entered" for row in result["rating_evidence"]
               if row["role"] in {"instrument_credit", "country_credit"})


def test_same_legal_exposure_and_signed_cash_representations_are_invariant():
    single = security("GOV", 100)
    lots = [security("GOV", 1, account=str(i % 3)) for i in range(100)]
    original = deepcopy(lots)
    a, b = calculate([single]), calculate(lots)
    assert b["score"] == a["score"]
    assert b["stress_loss"] == pytest.approx(a["stress_loss"])
    assert lots == original
    # Cash offsets pooled across accounts do not invent a funding constraint or
    # score blend; debt stays visible even when it has an equal cash offset.
    offset = calculate(lots, cashAccounts=[{"account_id": "bank", "value": 30, "currency": "USD"},
                                           {"account_id": "margin", "value": -30, "currency": "USD"}])
    assert offset["score"] == a["score"]
    assert offset["cash_debt"] == 30 and offset["net_equity"] == 100


def test_signed_foreign_cash_debt_and_multiplicative_fx_use_same_scenario():
    items = [security(f"STOCK{i}", 5, kind="equity", country="DE", currency="EUR") for i in range(20)]
    result = calculate(items, cashAccounts=[{"value": 100, "currency": "USD"}, {"value": -50, "currency": "EUR"}])
    # Recession: equity -40%, EUR -15% -> -49; EUR debt gains 7.5.
    expected_loss = 100 * (1 - .6 * .85) - 50 * .15
    assert result["net_equity"] == 150
    assert result["stress_loss"] == pytest.approx(expected_loss)
    assert result["score"] == severity(expected_loss / 150)
    assert result["funding"]["cash_debt"] == 50
    assert calculate([], cashAccounts=[{"value": 100, "currency": "EUR"}])["score"] == 30
    # An exactly hedged long/short exposure has no market P&L. Its signed net
    # equity is the separately recorded cash rather than gross security value.
    long = security("HEDGE", 50)
    short = security("HEDGE", -50, account="b")
    hedged = calculate([long, short], cash=100)
    assert hedged["score"] == 0 and hedged["net_equity"] == 100


def test_hedge_contribution_is_signed_in_identified_worst_scenario():
    # The market-rate scenario binds, while the short offsets one sixth of the
    # long's loss. Intrinsic long risk and signed contribution are distinct.
    long = security("LONG", 120)
    short = security("SHORT", -20, account="b")
    result = calculate([long, short])
    one_unit_loss = 1 - math.exp(-elapsed(MATURITY) * (.02 + .5 * .005))
    contributions = {row["symbol"]: row for row in result["position_contributions"]}
    assert result["worst_scenario"] == "inflation:fixed"
    assert contributions["LONG"]["pnl"] == pytest.approx(-120 * one_unit_loss)
    assert contributions["LONG"]["loss_contribution_pct"] == pytest.approx(120 * one_unit_loss)
    assert contributions["SHORT"]["pnl"] == pytest.approx(20 * one_unit_loss)
    assert contributions["SHORT"]["loss_contribution_pct"] == pytest.approx(-20 * one_unit_loss)
    assert sum(row["loss_contribution_pct"] for row in contributions.values()) == pytest.approx(result["loss_pct"])


def test_actual_dashboard_and_simulator_share_frozen_inputs_and_cash_fx():
    functions = app_functions("sum", "riskStrictBaseValue", "riskScoreForItems", "portfolioRiskSnapshot",
                              "portfolioAccounts", "isEquityCompAccount", "accountNativeCashBalance",
                              "accountCashBalance", "transactionCashImpact", "cleanSourceLabel")
    items = [security("LONG", 120, currency="EUR", country="DE"),
             security("SHORT", -20, currency="EUR", country="DE", account="b")]
    for item in items:
        item["price_ranges"] = {"1y": {"current": 1, "current_date": AS_OF}}
    accounts = [dict(id="a", type="Investment", currency="EUR", initial_cash=-10),
                dict(id="b", type="Investment", currency="EUR", initial_cash=20)]
    context = dict(items=items, accounts=accounts, transactions=[], fx_quotes=[{"pair": "EUR/USD", "quote": {"rate": 1.25}}],
                   base_currency="USD", calculated_at=AS_OF + "T12:00:00Z",
                   securities=[dict(symbol="LONG", stock_market="NYSE", security=items[0])])
    script = r'''
const PortfolioStressRisk=require('./web/stress-risk.js');
const simulator=require('./web/trade-simulator.js');
const state={baseCurrency:'USD',fxRates:{'EUR/USD':1.25},riskAsOf:'2026-11-14T12:00:00Z',localFunds:[]};
const accountLabel=a=>a.id,accountHorizonYears=()=>null,riskAllocationForItems=()=>({});
''' + functions + "\nconst context=" + json.dumps(context) + r''';
state.localAccounts=context.accounts;state.localTransactions=context.transactions;
const dashboard=portfolioRiskSnapshot(context.items);
const result=simulator.simulate(context,[{id:'draft',accountId:'a',symbol:'LONG',market:'NYSE',action:'BUY',quantity:1,priceInput:'',fee:0}],
 {risk:riskScoreForItems,horizon:()=>null,derivative:()=>false});
console.log(JSON.stringify({dashboard:dashboard.total,simulation:result.total.before.risk,status:result.status}));
'''
    result = node(script)
    assert result["status"] == "ok"
    for field in ("model", "score", "status", "stress_loss", "loss_pct", "net_equity", "cash_debt", "worst_scenario"):
        assert result["dashboard"][field] == result["simulation"][field], field
    assert result["simulation"]["cash_debt"] == 12.5
    assert result["simulation"]["net_equity"] == 137.5


def test_intrinsic_badge_uses_hypothetical_long_for_short_and_ignores_weight():
    items = [security("GOV", value) for value in (1, 100, -100)]
    script = "const PortfolioStressRisk=require('./web/stress-risk.js');const state={baseCurrency:'USD',fxRates:{},riskAsOf:'2026-11-14'};\n"
    script += app_functions("riskStrictBaseValue", "riskScoreForItems")
    script += "const rows=" + json.dumps(items) + ";console.log(JSON.stringify(rows.map(item=>riskScoreForItems([item],{cash:200}).position_risks.get(item).score)));"
    scores = node(script)
    assert scores == [25, 25, 25]


@pytest.fixture
def local_inputs(tmp_path):
    store = LocalPortfolioStore(tmp_path / "qa-risk.sqlite")
    inventory = [dict(security_key="GOV|NYSE|ILS", symbol="GOV", stock_market="NYSE", currency="ILS",
                      asset_class="BOND", asset_sub_class="BOND", issuer_name="Synthetic Sovereign",
                      issuer_identity_verified=True, isin="IL0000000001")]
    credit = {"ratings": []}
    sovereign = {"ratings": [opinion("AA", currency_basis="local_currency"),
                              opinion("BBB", currency_basis="foreign_currency")]}
    country = {"country_code": "IL", "source_kind": "provider_profile"}
    service = StressRiskInputs(store=lambda: store, inventory=lambda: deepcopy(inventory),
                              credit=lambda _: deepcopy(credit), sovereign=lambda _: deepcopy(sovereign),
                              countries=lambda _: deepcopy(country))
    return service, store, inventory, credit, sovereign, country


def local_parameters(**changes):
    return {"instrument_kind": "sovereign_bond", "sovereign_currency_basis": "local_currency",
            "country_code": "IL", "country_currency": "ILS", "country_basis": "economic_exposure",
            "plain_nominal_noncallable": True, "pricing_model": "zero_coupon_continuous",
            "zero_coupon_confirmed": True, "maturity_date": MATURITY, "current_spread_bps": 50,
            "as_of": date.today().isoformat(), "notes": "Synthetic contractual evidence", **changes}


def update_payload(service, **changes):
    current = service.read(service.inventory()[0])
    return dict(security_key=current["security_key"], expected_identity=current["identity_token"],
                expected_revision=current["revision"], parameters=local_parameters(**changes))


def test_cache_bound_rating_selection_honors_issue_and_scope_without_other_axis(local_inputs):
    service, _, inventory, credit, sovereign, _ = local_inputs
    # An old action date is valid with a recent current verification. The exact
    # issue's BBB must win over both issuer AA and the sovereign LC AA fallback.
    credit["ratings"] = [opinion("AA", "issuer", entity_name="Synthetic Sovereign"),
                          opinion("BBB", "issue", rating_date="2018-01-01", currency_basis="local_currency"),
                          opinion("B", "issue", scale="national"),
                          opinion("CCC", "issue", stale=True)]
    service.update(update_payload(service), {"id": "qa"})
    result = service.read(inventory[0])
    assert result["sovereign_rating"]["scope"] == "issue"
    assert result["sovereign_rating"]["rating"] == "BBB"
    assert result["sovereign_ratings"]["foreign_currency"]["rating"] == "BBB"
    assert result["sovereign_rating"]["rating_date"] == "2018-01-01"
    for invalid in (opinion("D", "issue"), opinion("CCC", "issue", status="conflicting"),
                    opinion("BBB", "issue", term="short_term"), opinion("C", "issue", agency="moodys")):
        assert select_rating({"ratings": [invalid]}, inventory[0]) is None


def test_simultaneous_parameter_writes_have_one_winner_and_clear_changes_revision(local_inputs):
    service, _, inventory, *_ = local_inputs
    payload = update_payload(service)
    before = service.revision()
    def attempt(notes):
        copy = deepcopy(payload)
        copy["parameters"]["notes"] = notes
        try:
            return service.update(copy, {"id": "qa"})["revision"]
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as workers:
        result = list(workers.map(attempt, ("First synthetic edit", "Second synthetic edit")))
    assert sorted(result) == [1, 409]
    assert service.revision() != before
    saved = service.read(inventory[0])
    before_clear = service.revision()
    empty = service.update({k: v for k, v in update_payload(service).items() if k != "parameters"}, {"id": "qa"}, clear=True)
    assert empty["revision"] == saved["revision"] + 1 and empty["parameters"] == {}
    assert service.revision() != before_clear
    inventory[0]["isin"] = "IL0000000002"
    with pytest.raises(HTTPException) as error:
        service.update(payload, {"id": "qa"})
    assert error.value.status_code == 409


def test_viewer_can_read_but_neither_change_nor_clear_local_inputs(local_inputs):
    service, _, _, _, _, _ = local_inputs
    app = FastAPI()
    @app.middleware("http")
    async def identity(request, call_next):
        role = request.headers.get("x-role")
        request.state.auth_user = {"id": "synthetic", "role": role} if role else None
        return await call_next(request)
    app.include_router(service.router())
    client = TestClient(app)
    query = "/api/securities/risk-inputs?symbol=GOV&stock_market=NYSE&currency=ILS"
    assert client.get(query).status_code == 401
    assert client.get(query, headers={"x-role": "Viewer"}).status_code == 200
    payload = update_payload(service)
    before = service.revision()
    assert client.put("/api/securities/risk-inputs", json=payload, headers={"x-role": "Viewer"}).status_code == 403
    assert client.request("DELETE", "/api/securities/risk-inputs", json={k: v for k, v in payload.items() if k != "parameters"},
                          headers={"x-role": "Viewer"}).status_code == 403
    assert service.revision() == before


def test_real_parameter_edit_during_snapshot_retries_before_publishing(local_inputs, monkeypatch):
    from app import main
    service, _, inventory, *_ = local_inputs
    first = service.update(update_payload(service), {"id": "synthetic"})
    item = security("GOV", currency="ILS", country="IL")
    original_enrich = service.enrich
    captured = []
    def enrich(items):
        result = original_enrich(items)
        captured.append(result[0]["stress_risk"]["revision"])
        if len(captured) == 1:
            service.update(update_payload(service, current_spread_bps=150), {"id": "synthetic"})
        return result
    monkeypatch.setattr(service, "enrich", enrich)
    monkeypatch.setattr(main, "stress_risk_inputs", service)
    monkeypatch.setattr(main, "portfolio_payload", lambda **_: {"items": [deepcopy(item)]})
    result = main.portfolio()
    assert captured == [first["revision"], first["revision"] + 1]
    assert result["items"][0]["stress_risk"]["parameters"]["current_spread_bps"] == 150
    assert result["risk_revision"] == service.revision()
    assert result["items"][0]["stress_risk"] == service.read(inventory[0])


def test_history_preserves_old_model_estimate_and_raw_evidence_and_rejects_race(tmp_path):
    store = LocalPortfolioStore(tmp_path / "qa-history.sqlite")
    old = dict(id="v2", model="portfolio-risk-v2", source=risk_history.SOURCE,
               observed_at="2026-11-12T10:00:00Z", date="2026-11-12", base_currency="USD", accounts=[],
               total={"score": 31, "components": {k: 0 for k in risk_history._COMPONENTS}})
    store.set_preference(risk_history.PREFIX + "legacy", old)
    item = security("GOV")
    item["stress_risk"]["parameters_verification"] = "user_entered"
    item["stress_risk"]["parameters"]["assumptions_enabled"] = True
    account = {"id": "a", "account_id": "A", "type": "Investment", "currency": "USD", "initial_cash": 0}
    raw = risk_history.canonical_inputs([item], [account], [], {"quotes": []}, "USD")
    raw["guard"] = ("synthetic-source", 1, "risk-1")
    context = risk_history.create_context(store, "qa", "USD", lambda _: deepcopy(raw))
    risk = calculate([item])
    payload = {"token": context["token"], "total": risk, "accounts": [{"account_id": "a", "risk": risk}]}
    with pytest.raises(risk_history.RiskHistoryError) as error:
        risk_history.save_observation(store, "qa", payload, lambda _: deepcopy(raw), lambda: ("synthetic-source", 1, "risk-2"))
    assert str(error.value) == "risk_context_stale"
    observation = risk_history.save_observation(store, "qa", payload, lambda _: deepcopy(raw), lambda: raw["guard"])["observation"]
    assert observation["total"]["status"] == "estimate" and observation["total"]["score"] is None
    assert observation["total"]["estimated_score"] == 25
    frozen = deepcopy(observation)
    raw["items"][0]["stress_risk"]["parameters"]["maturity_date"] = "2040-01-01"
    listed = risk_history.list_observations(store, "USD", 0)
    assert next(row for row in listed["items"] if row["model"] == "portfolio-risk-v3") == frozen
    assert store.get_preference(risk_history.PREFIX + "legacy") == old


def test_known_nonpositive_equity_boundary_can_be_saved_without_fake_coverage(tmp_path):
    store = LocalPortfolioStore(tmp_path / "boundary-history.sqlite")
    item = security()
    del item["stress_risk"]["parameters"]["pricing_model"]
    result = calculate([item], cash=-200)
    assert result["net_equity"] == -100 and result["score"] == 100
    assert result["worst_scenario"] == "nonpositive_equity"
    assert result["coverage"]["complete"] is False and result["gaps"]
    account = {"id": "a", "account_id": "A", "type": "Investment", "currency": "USD", "initial_cash": -200}
    raw = risk_history.canonical_inputs([item], [account], [], {"quotes": []}, "USD")
    raw["guard"] = ("synthetic-boundary", 1, "risk-1")
    context = risk_history.create_context(store, "qa", "USD", lambda _: deepcopy(raw))
    payload = {"token": context["token"], "total": result, "accounts": [{"account_id": "a", "risk": result}]}
    saved = risk_history.save_observation(store, "qa", payload, lambda _: deepcopy(raw), lambda: raw["guard"])
    assert saved["observation"]["total"]["score"] == 100
    assert saved["observation"]["total"]["coverage"]["complete"] is False
    assert saved["observation"]["total"]["gaps"] == result["gaps"]
    for field, replacement in (("net_equity", None), ("net_equity", 1), ("score", 99),
                               ("worst_scenario", "inflation:fixed")):
        malformed = {**result, field: replacement}
        with pytest.raises(risk_history.RiskHistoryError):
            risk_history._risk(malformed, "portfolio-risk-v3")


@pytest.mark.parametrize("valuation_date", [None, "2020-01-01", "2026-11-15"])
def test_invalid_valuation_date_cannot_establish_nonpositive_current_equity(tmp_path, valuation_date):
    item = security()
    if valuation_date is None:
        del item["stress_risk"]["valuation_date"]
    else:
        item["stress_risk"]["valuation_date"] = valuation_date
    # A retrieved timestamp does not make an undated, stale, or future mark a
    # known current valuation for applying the nonpositive-equity boundary.
    item["stress_risk"]["as_of"] = AS_OF
    result = calculate([item], cash=-200)
    assert result["score"] is None and result["estimated_score"] is None
    assert result["status"] == "incomplete" and result["net_equity"] is None
    assert {gap["code"] for gap in result["gaps"]} & {"valuation", "valuation_stale"}
    store = LocalPortfolioStore(tmp_path / "incomplete-history.sqlite")
    account = {"id": "a", "type": "Investment", "currency": "USD", "initial_cash": -200}
    raw = risk_history.canonical_inputs([item], [account], [], {"quotes": []}, "USD")
    raw["guard"] = ("synthetic-incomplete", 1, "risk-1")
    context = risk_history.create_context(store, "qa", "USD", lambda _: deepcopy(raw))
    saved = risk_history.save_observation(store, "qa", {"token": context["token"], "total": result,
        "accounts": [{"account_id": "a", "risk": result}]}, lambda _: deepcopy(raw), lambda: raw["guard"])
    assert saved["observation"]["total"]["score"] is None
    assert saved["observation"]["total"]["coverage"]["covered_value_percent"] is None


def browser_wait(evaluate, expression):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if evaluate(expression):
            return
        time.sleep(.03)
    raise AssertionError("Browser condition did not complete: " + expression)


def browser_document(tmp_path, metadata, language, role="Operator"):
    source = (ROOT / "web/app.js").read_text().replace(
        "initializeApp().catch(reportBackgroundError).finally(revealInitializedApp);", "")
    setup = r'''
window.qa={errors:[],calls:[],pending:[],metadata:QA_METADATA};
window.addEventListener('error',e=>qa.errors.push(e.message));
window.addEventListener('unhandledrejection',e=>qa.errors.push(String(e.reason)));
qa.item=metadata=>({holding:{symbol:'GOV',stock_market:'NYSE',currency:'ILS',quantity:100,market_value:100,asset_class:'BOND',account_id:'a'},stress_risk:{...metadata,valuation_date:'2026-11-14'}});
qa.accounts=[{id:'a',type:'Investment',currency:'ILS',initial_cash:0}];
api=async (path,options={})=>{
 qa.calls.push({path,method:options.method||'GET',body:options.body?JSON.parse(options.body):null});
 if(path.startsWith('/api/securities/risk-inputs?'))return structuredClone(qa.metadata);
 if(path==='/api/securities/risk-inputs')return new Promise((resolve,reject)=>qa.pending.push({resolve,reject}));
 if(path==='/api/portfolio')return {items:[qa.item(qa.metadata)],count:1,risk_as_of:'2026-11-14',refresh_pending:false};
 if(path==='/api/local/accounts')return {items:qa.accounts};
 if(path.startsWith('/api/local/account-trends'))return {accounts:[]};
 return {items:[]};
};
saveDashboardSettings=()=>{};appLog=()=>{};appWarn=()=>{};
state.auth.user={id:'synthetic',username:'synthetic',role:QA_ROLE};
state.baseCurrency='ILS';state.fxRates={};state.riskAsOf='2026-11-14';
state.language=QA_LANGUAGE;state.dashboard=defaultDashboard();
state.items=[];state.localAccounts=qa.accounts;state.localTransactions=[];
$('authOverlay').hidden=true;$('appShell').inert=false;$('appShell').removeAttribute('aria-hidden');
revealInitializedApp();PortfolioI18n.applyToDocument(state.language);PortfolioI18n.observe();
document.addEventListener('stress-risk-inputs-changed',()=>qa.changed=(qa.changed||0)+1);
qa.render=metadata=>{
 const item=qa.item(metadata);
 qa.result=PortfolioStressRisk.calculate([item],{baseCurrency:'ILS',asOf:'2026-11-14'});
 $('analyticsBoard').innerHTML=riskBadge(qa.result)+stressRiskSummaryHtml(qa.result)+stressRiskGapsHtml(qa.result);
};
qa.render(qa.metadata);qa.ready=true;
'''.replace("QA_METADATA", json.dumps(metadata)).replace("QA_ROLE", json.dumps(role)).replace("QA_LANGUAGE", json.dumps(language))
    (tmp_path / "qa-app.js").write_text(source + "\n" + setup)
    page = (ROOT / "web/index.html").read_text()
    page = re.sub(r'<script src="https://[^\"]+"></script>', "", page)
    for relative in re.findall(r'(?:src|href)="/([^"?]+)(?:\?[^\"]*)?"', page):
        asset = ROOT / "web" / relative
        if not asset.exists():
            continue
        if relative == "app.js":
            asset = tmp_path / "qa-app.js"
        elif relative.endswith(".css"):
            target = tmp_path / Path(relative).name
            target.write_text(re.sub(r'@import\s+url\([^)]*\)\s*;', "", asset.read_text()))
            asset = target
        page = re.sub(r'(["\'])/' + re.escape(relative) + r'(?:\?[^"\']*)?(["\'])',
                      lambda match: match[1] + asset.as_uri() + match[2], page)
    document = tmp_path / "qa-stress-risk.html"
    document.write_text(page)
    return document


@pytest.mark.parametrize("language,width", [("en", 1440), ("he", 390)])
def test_actual_backend_to_browser_editor_model_and_serialization_roundtrip(tmp_path, chromium, local_inputs, language, width):
    service, _, inventory, *_ = local_inputs
    saved = service.update(update_payload(service, assumptions_enabled=True), {"id": "synthetic"})
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1080, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": browser_document(tmp_path, saved, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    assert evaluate("qa.errors") == []
    t = elapsed(MATURITY)
    expected_before = severity(1 - math.exp(-t * (.02 + .5 * .0075)))
    assert evaluate("qa.result.score") is None
    assert evaluate("qa.result.estimated_score") == expected_before
    assert "~" + str(expected_before) in evaluate("$('analyticsBoard').innerText")
    evaluate("openStressRiskInputs({security_key:'GOV|NYSE|ILS'})")
    browser_wait(evaluate, "!$('stressRiskInputsModal').hidden&&$('stressRiskPricingModel').value==='zero_coupon_continuous'")
    assert evaluate("$('stressRiskMaturity').value") == "14/11/2032"
    assert evaluate("$('stressRiskSpread').value") == "50"
    assert evaluate("$('saveStressRiskInputs').disabled") is False
    # The editor accepts percent, the persisted model uses decimal continuous
    # yield, and contract cash-flow dates use ISO only on the wire.
    evaluate("$('stressRiskPricingModel').value='cashflows_continuous';$('stressRiskPricingModel').dispatchEvent(new Event('change',{bubbles:true}));$('stressRiskCashflows').value='14/11/2027, 5\\n14/11/2029, 105';$('stressRiskYield').value='4.25';$('saveStressRiskInputs').click()")
    browser_wait(evaluate, "qa.pending.length===1")
    wire = evaluate("qa.calls.findLast(call=>call.method==='PUT').body")
    assert wire["parameters"]["continuous_yield"] == .0425
    assert wire["parameters"]["cashflows"] == [{"date": "2027-11-14", "amount": 5}, {"date": "2029-11-14", "amount": 105}]
    assert wire["expected_identity"] == saved["identity_token"] and wire["expected_revision"] == saved["revision"]
    response = service.update(wire, {"id": "synthetic"})
    evaluate("qa.metadata=" + json.dumps(response) + ";qa.pending.shift().resolve(qa.metadata)")
    browser_wait(evaluate, "qa.changed===1&&!$('saveStressRiskInputs').disabled")
    evaluate("qa.render(qa.metadata)")
    pv = lambda shift: 5 * math.exp(-(.0425 + shift) * elapsed("2027-11-14")) + 105 * math.exp(-(.0425 + shift) * elapsed("2029-11-14"))
    expected_after = severity(1 - pv(.02 + .5 * .0075) / pv(0))
    assert evaluate("qa.result.estimated_score") == expected_after
    browser_wait(evaluate, f"state.riskSnapshot?.total?.estimated_score==={expected_after}")
    assert evaluate("state.items[0].stress_risk.revision") == response["revision"]
    assert evaluate("qa.calls.some(call=>call.path==='/api/portfolio')") is True
    assert evaluate("JSON.parse(JSON.stringify(qa.result)).status") == "estimate"
    assert evaluate("$('stressRiskYield').value") == "4.25"
    modal_text = evaluate("$('stressRiskInputsModal').innerText")
    if language == "he":
        for english in ("Risk inputs", "Continuous discount yield", "Saving risk inputs", "Unknown", "Reload saved inputs"):
            assert english not in modal_text
    else:
        assert not re.search(r"[\u0590-\u05ff]", modal_text)
    bounds = evaluate("(()=>{const d=$('stressRiskInputsModal').querySelector('[role=dialog]');return {left:d.getBoundingClientRect().left,right:d.getBoundingClientRect().right,width:d.clientWidth,scroll:d.scrollWidth};})()")
    assert bounds["left"] >= 0 and bounds["right"] <= width and bounds["scroll"] <= bounds["width"]
    assert evaluate("$('stressRiskYield').clientWidth") >= 100
    assert evaluate("qa.errors") == []
    image = command("Page.captureScreenshot", {"format": "png"})
    (tmp_path / f"stress-inputs-{language}-{width}.png").write_bytes(base64.b64decode(image["data"]))
    # A conflicting save retains the draft and the server's authoritative state.
    evaluate("$('stressRiskNotes').value='Unsaved synthetic draft';$('saveStressRiskInputs').click()")
    browser_wait(evaluate, "qa.pending.length===1")
    evaluate("qa.pending.shift().reject({status:409})")
    browser_wait(evaluate, "!$('saveStressRiskInputs').disabled")
    assert evaluate("$('stressRiskNotes').value") == "Unsaved synthetic draft"
    assert evaluate("$('stressRiskInputsStatus').textContent")
    assert service.read(inventory[0])["parameters"]["notes"] != "Unsaved synthetic draft"
    # Role switching demonstrates the actual editor controls, not just an API
    # assertion. Reload is available to a viewer, writes are disabled.
    evaluate("state.auth.user.role='Viewer';$('reloadStressRiskInputs').click()")
    browser_wait(evaluate, "$('saveStressRiskInputs').disabled&&$('stressRiskNotes').disabled")
    assert evaluate("$('clearStressRiskInputs').disabled") is True
    assert evaluate("$('stressRiskViewerNote').hidden") is False
    writes = evaluate("qa.calls.filter(call=>call.method!=='GET').length")
    evaluate("$('saveStressRiskInputs').click();$('clearStressRiskInputs').click()")
    assert evaluate("qa.calls.filter(call=>call.method!=='GET').length") == writes


def test_browser_editor_ignores_out_of_order_and_old_user_responses(tmp_path, chromium, local_inputs):
    service, _, inventory, *_ = local_inputs
    saved = service.update(update_payload(service), {"id": "synthetic"})
    command, evaluate = chromium
    command("Page.navigate", {"url": browser_document(tmp_path, saved, "en").as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate("qa.reads=[];api=()=>new Promise(resolve=>qa.reads.push(resolve));void openStressRiskInputs({security_key:'OLD|NYSE|ILS'})")
    browser_wait(evaluate, "qa.reads.length===1")
    evaluate("void openStressRiskInputs({security_key:'GOV|NYSE|ILS'})")
    browser_wait(evaluate, "qa.reads.length===2")
    newest = deepcopy(saved)
    newest["parameters"]["notes"] = "Newest synthetic response"
    newest["local_parameters"]["notes"] = "Newest synthetic response"
    evaluate("qa.reads[1](" + json.dumps(newest) + ")")
    browser_wait(evaluate, "$('stressRiskNotes').value==='Newest synthetic response'")
    stale = deepcopy(saved)
    stale["parameters"]["notes"] = "Stale synthetic response"
    stale["local_parameters"]["notes"] = "Stale synthetic response"
    evaluate("qa.reads[0](" + json.dumps(stale) + ")")
    assert evaluate("$('stressRiskNotes').value") == "Newest synthetic response"
    evaluate("void openStressRiskInputs({security_key:'GOV|NYSE|ILS'})")
    browser_wait(evaluate, "qa.reads.length===3")
    evaluate("state.auth.user={id:'second-synthetic',role:'Viewer'};qa.reads[2](" + json.dumps(stale) + ")")
    browser_wait(evaluate, "$('saveStressRiskInputs').disabled")
    assert evaluate("$('stressRiskNotes').value") != "Stale synthetic response"
    assert evaluate("qa.errors") == []
    assert service.read(inventory[0])["parameters"]["notes"] == "Synthetic contractual evidence"


@pytest.mark.parametrize("language", ["en", "he"])
def test_browser_loss_amount_sensitivity_and_signed_holding_contribution(tmp_path, chromium, local_inputs, language):
    service, _, inventory, *_ = local_inputs
    metadata = service.read(inventory[0])
    command, evaluate = chromium
    command("Page.navigate", {"url": browser_document(tmp_path, metadata, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    long, short = security("LONG", 120, grade="BBB"), security("SHORT", -20, grade="BBB", account="b")
    long["stress_risk"]["sovereign_rating"]["negative_signal"] = True
    evaluate("qa.holdings=" + json.dumps([long, short]) + ";qa.portfolio=riskScoreForItems(qa.holdings,{baseCurrency:'USD'});qa.shortRisk=qa.portfolio.position_risks.get(qa.holdings[1]);qa.longRisk=qa.portfolio.position_risks.get(qa.holdings[0]);$('analyticsBoard').innerHTML=stressRiskSummaryHtml(qa.portfolio)+riskBadge(qa.shortRisk)")
    portfolio_text = evaluate("$('analyticsBoard').innerText")
    expected_loss = 100 * (1 - math.exp(-elapsed(MATURITY) * .03))
    assert f"{expected_loss:.2f}" in portfolio_text
    assert "USD" in portfolio_text
    long_tip, short_tip = evaluate("[stressRiskTooltip(qa.longRisk),stressRiskTooltip(qa.shortRisk)]")
    short_contribution = -20 * (1 - math.exp(-elapsed(MATURITY) * .03))
    assert f"{short_contribution:.1f}%" in short_tip
    assert "52/100" in long_tip
    assert evaluate("stressRiskLossAmountText(qa.shortRisk)") == ""
    assert evaluate("stressRiskLossAmountText(qa.longRisk)") == ""
    assert evaluate("qa.shortRisk.intrinsic") is True
    if language == "he":
        for english in ("Modeled loss amount", "Negative rating sensitivity", "Contribution to portfolio stress loss", "baseline", "Estimated"):
            assert english not in portfolio_text + long_tip + short_tip
    else:
        assert not re.search(r"[\u0590-\u05ff]", portfolio_text + long_tip + short_tip)
        assert "Contribution to portfolio stress loss" in short_tip
        assert "Negative rating sensitivity" in long_tip
    assert evaluate("qa.errors") == []


@pytest.mark.parametrize("language", ["en", "he"])
def test_browser_risk_alarms_distinguish_estimates_gaps_and_known_insolvency(tmp_path, chromium, local_inputs, language):
    service, _, _, *_ = local_inputs
    metadata = service.update(update_payload(service, assumptions_enabled=True), {"id": "synthetic"})
    command, evaluate = chromium
    command("Page.navigate", {"url": browser_document(tmp_path, metadata, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate("state.portfolioReady=true;state.portfolioRefreshPending=false;state.portfolioSourceState='ready';state.allPortfolioItems=[qa.item(qa.metadata)];qa.alarms=portfolioRiskAlarms()")
    alarms = evaluate("qa.alarms")
    expected_score = severity(1 - math.exp(-elapsed(MATURITY) * (.02 + .5 * .0075)))
    assert len(alarms) == 2
    assert all(a["level"] == "limited" and a["risk"]["status"] == "estimate" and a["risk"]["score"] is None for a in alarms)
    assert all(a["risk"]["estimated_score"] == expected_score for a in alarms)
    assert all("~" + str(expected_score) in a["body"] for a in alarms)
    evaluate("qa.firstId=riskAlarmDismissalId(qa.alarms[0]);state.allPortfolioItems[0].stress_risk.parameters.current_spread_bps=51;qa.changedAlarms=portfolioRiskAlarms()")
    assert evaluate("qa.changedAlarms[0].risk.estimated_score") == expected_score
    assert evaluate("riskAlarmDismissalId(qa.changedAlarms[0])!==qa.firstId") is True
    evaluate("delete state.allPortfolioItems[0].stress_risk.parameters.pricing_model;qa.alarms=portfolioRiskAlarms()")
    assert evaluate("qa.alarms.length") == 2
    assert evaluate("qa.alarms.every(a=>a.level==='unavailable'&&a.risk.score===null&&a.risk.estimated_score===null)") is True
    evaluate("state.localAccounts[0].initial_cash=-200;qa.alarms=portfolioRiskAlarms()")
    assert evaluate("qa.alarms.every(a=>a.level==='extreme'&&a.risk.score===100&&a.risk.coverage.complete===false)") is True
    evaluate("state.allPortfolioItems[0].stress_risk.valuation_date='2020-01-01';qa.alarms=portfolioRiskAlarms()")
    assert evaluate("qa.alarms.every(a=>a.level==='unavailable'&&a.risk.score===null)") is True
    evaluate("$('alarmsList').innerHTML=qa.alarms.map(renderAlarmListItem).join('')")
    text = evaluate("$('alarmsList').innerText")
    if language == "he":
        for english in ("Complete missing risk", "Risk assessment unavailable", "View risk details", "Modeled", "Estimated"):
            assert english not in text
    else:
        assert not re.search(r"[\u0590-\u05ff]", text)
    assert evaluate("qa.errors") == []


