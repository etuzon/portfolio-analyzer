"""Independent static-reference and maturity-bound acceptance.

Amounts are synthetic100-unit books. Only public exact-CUSIP reference facts are
retained; actual portfolio quantities/accounts/cash stay in ignored artifacts.
The conservative maturity bound is not coupon duration or observed market yield.
"""
from copy import deepcopy
from datetime import date, datetime, timezone
import base64
import json
import math
from types import SimpleNamespace

import pytest

from test_cash_fund_risk_independent_qa import AS_OF, calculate, node, opinion
from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium
from test_shared_cash_risk_qa import app_functions
from app import risk_history, risk_scenarios
from app.local_portfolio import LocalPortfolioStore


MATURITY = "2029-02-28"
BOUND = (date.fromisoformat(MATURITY) - date.fromisoformat(AS_OF)).days / 365.25


def reference_bond():
    return {
        "holding": {"symbol": "91282CKD2", "stock_market": "MANUAL", "currency": "USD",
                    "asset_class": "BOND", "asset_sub_class": "", "quantity": 1,
                    "market_value": 100, "account_id": "synthetic-account"},
        "price_ranges": {"1m": {"current": 100, "current_date": AS_OF}},
        "stress_risk": {"security_key": "91282CKD2|MANUAL|USD", "parameters": {}, "valuation_date": AS_OF},
        "market_data": {
            "schema_version": "security-market-data-v2", "provider": "treasury_direct", "status": "partial",
            "request": {"identifier": "91282CKD2", "identifier_type": "cusip", "kind": "bond"},
            "security": {"identifier": "91282CKD2", "cusip": "91282CKD2", "currency": "USD",
                         "kind": "bond", "issuer": "United States Department of the Treasury"},
            "details": {"security_type": "Note", "coupon_rate_pct": 4.25,
                        "maturity_date": MATURITY, "issue_date": "2024-02-29",
                        "floating_rate": False, "inflation_protected": False,
                        "auction_high_yield_pct": 4.32, "auction_yield_is_current": False},
            "source_url": "https://www.treasurydirect.gov/TA_WS/securities/search?cusip=91282CKD2&format=json",
            "retrieved_at": "2026-11-14T10:00:00Z",
            "details_scope": "latest_provider_profile_not_historical_point_in_time",
        },
    }


def assumptions(result, code):
    return [r for r in result["provisional_assumptions"] if r["code"] == code]


def test_exact_partial_reference_supports_only_labeled_government_and_maturity_proxies():
    bond = reference_bond()
    before = deepcopy(bond)
    result = calculate([bond], baseCurrency="USD", cash=100)
    expected_loss = -100 * math.expm1(-BOUND * (.02 + .5 * .02))
    assert BOUND == pytest.approx(837 / 365.25)
    assert result["score"] is None and result["status"] == "incomplete"
    assert result["provisional_scope"] == "portfolio"
    assert result["provisional_loss"] == pytest.approx(expected_loss)
    assert result["provisional_score"] == math.floor(100 * expected_loss / 200 + .5 + 1e-10)
    assert result["provisional_worst_scenario"] == "inflation:fixed"
    assert result["provisional_net_equity"] == 200
    assert not any(r["name"].startswith("issuer_") for r in result["provisional_scenarios"])
    bound = assumptions(result, "bond_duration_maturity_bound")
    assert len(bound) == 1 and bound[0]["duration_years"] == BOUND
    assert bound[0]["maturity_date"] == MATURITY
    assert bound[0]["reference_retrieved_at"] == bond["market_data"]["retrieved_at"]
    assert bound[0]["source_url"] == bond["market_data"]["source_url"]
    assert not bound[0].get("source_date")  # retrieval is not quote observation
    facts = assumptions(result, "government_bond_proxy")[0]["reference_facts"]
    assert facts["identifier"] == "91282CKD2" and facts["currency"] == "USD"
    assert facts["issuer"] == "United States Department of the Treasury"
    assert facts["security_type"] == "Note" and facts["floating_rate"] is False and facts["inflation_protected"] is False
    assert assumptions(result, "unrated_credit_proxy")[0]["spread_bps"] == 200
    assert assumptions(result, "credit_tightening_omitted")
    assert not result["rating_evidence"]
    assert bond == before


@pytest.mark.parametrize("part,key,value", [
    ("security", "cusip", "000000000"),
    ("security", "currency", "EUR"),
    ("security", "issuer", "A Fund Manager"),
    ("request", "identifier", "000000000"),
    ("reference", "source_url", "http://www.treasurydirect.gov/TA_WS/securities/search"),
    ("reference", "source_url", "https://www.treasurydirect.gov.example.com/TA_WS/securities/search"),
    ("reference", "source_url", "https://example.com/TA_WS/securities/search"),
    ("reference", "retrieved_at", "2026-11-15T00:00:00Z"),
    ("reference", "retrieved_at", "not-a-date"),
    ("reference", "provider", "manual"),
    ("reference", "status", "error"),
])
def test_ineligible_reference_never_promotes_identity_or_verified_duration(part, key, value):
    bond = reference_bond()
    target = bond["market_data"] if part == "reference" else bond["market_data"][part]
    target[key] = value
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert not assumptions(result, "government_bond_proxy")
    assert not assumptions(result, "bond_duration_maturity_bound")
    # Lack of a usable static reference does not invent a contraindication.
    assert result["provisional_scope"] == "portfolio"
    expected_issuer_loss = -100 * math.expm1(-5 * max(.2 / 5, 2 * .025))
    assert result["provisional_loss"] == pytest.approx(expected_issuer_loss)
    assert any(r["name"].startswith("issuer_distress:") for r in result["provisional_scenarios"])


@pytest.mark.parametrize("field,value", [("floating_rate", True), ("inflation_protected", True),
                                         ("callable", True), ("noncallable", False),
                                         ("security_type", "Fund"), ("plain_nominal_noncallable", False)])
def test_trusted_known_unsupported_reference_payoff_is_range_not_ordinary_debt(field, value):
    bond = reference_bond()
    bond["market_data"]["details"][field] = value
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert result["score"] is None and result["status"] == "incomplete"
    assert result["provisional_scope"] == "known_values"
    assert result["provisional_range"] == {"min": 0, "max": 100}
    assert result["provisional_net_equity"] == 100  # supported cash subset only
    assert not result["provisional_loss"]
    assert not assumptions(result, "government_bond_proxy")
    assert not assumptions(result, "bond_duration_maturity_bound")


@pytest.mark.parametrize("field,value", [("floating_rate", None), ("inflation_protected", None),
                                         ("security_type", None), ("security_type", "Unknown")])
def test_missing_plain_terms_keep_known_sovereign_identity_but_withhold_verified_maturity_bound(field, value):
    # Missing evidence is not a known contraindication. Finance froze the
    # generic-sovereign fallback separately from known unsupported payoffs.
    bond = reference_bond()
    bond["market_data"]["details"][field] = value
    result = calculate([bond], baseCurrency="USD", cash=100)
    expected_loss = -100 * math.expm1(-5 * (.02 + .5 * .02))
    assert result["provisional_scope"] == "portfolio"
    assert assumptions(result, "government_bond_proxy")
    assert assumptions(result, "unrated_credit_proxy")[0]["spread_bps"] == 200
    assert assumptions(result, "bond_duration_proxy")[0]["duration_years"] == 5
    assert not assumptions(result, "bond_duration_maturity_bound")
    assert not any(r["name"].startswith("issuer_") for r in result["provisional_scenarios"])
    assert result["provisional_loss"] == pytest.approx(expected_loss)


@pytest.mark.parametrize("field,value", [("floating_rate", True), ("inflation_protected", True),
                                         ("callable", True), ("noncallable", False)])
def test_unbound_unsupported_reference_cannot_poison_another_holding(field, value):
    bond = reference_bond()
    bond["market_data"]["details"][field] = value
    bond["market_data"]["security"]["cusip"] = "000000000"
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert result["provisional_scope"] == "portfolio"
    assert not assumptions(result, "government_bond_proxy")


@pytest.mark.parametrize("asset,kind", [("EQUITY", "equity"), ("RSU", "equity"), ("ETF", "fund"), ("MUTUALFUND", "fund")])
def test_stock_or_fund_wrapper_reference_does_not_create_direct_treasury(asset, kind):
    bond = reference_bond()
    bond["holding"]["asset_class"] = asset
    bond["stress_risk"]["parameters"]["instrument_kind"] = kind
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert not assumptions(result, "government_bond_proxy")
    assert not assumptions(result, "bond_duration_maturity_bound")
    assert result["provisional_loss"] == (60 if asset in ("EQUITY", "RSU") else 40)
    assert any(r["name"].startswith("issuer_") for r in result["provisional_scenarios"]) == (asset in ("EQUITY", "RSU"))


@pytest.mark.parametrize("maturity,expected_duration", [("2039-02-28", 5), ("2029-02-28", BOUND)])
def test_maturity_bound_never_increases_default_five_year_proxy(maturity, expected_duration):
    bond = reference_bond()
    bond["market_data"]["details"]["maturity_date"] = maturity
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert assumptions(result, "bond_duration_proxy")[0]["duration_years"] == expected_duration
    assert bool(assumptions(result, "bond_duration_maturity_bound")) == (expected_duration < 5)


@pytest.mark.parametrize("maturity", [AS_OF, "2020-01-01"])
def test_matured_exact_reference_needs_payoff_model(maturity):
    bond = reference_bond()
    bond["market_data"]["details"]["maturity_date"] = maturity
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert result["provisional_scope"] == "known_values"
    assert result["provisional_range"] == {"min": 0, "max": 100}


@pytest.mark.parametrize("enabled", [False, True])
def test_manual_maturity_alone_never_claims_verified_duration_bound(enabled):
    bond = reference_bond()
    del bond["market_data"]
    bond["stress_risk"].update(parameters_verification="user_entered",
        parameter_provenance={"verification_status": "user_entered"},
        parameters={"instrument_kind": "corporate_bond", "maturity_date": MATURITY,
                    "plain_nominal_noncallable": True, "assumptions_enabled": enabled})
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert not assumptions(result, "bond_duration_maturity_bound")
    assert assumptions(result, "bond_duration_proxy")[0]["duration_years"] == 5


def test_verified_plain_terms_can_bound_proxy_without_claiming_coupon_duration():
    bond = reference_bond()
    del bond["market_data"]
    bond["stress_risk"].update(parameters_verification="verified",
        parameter_provenance={"verification_status": "verified", "source_url": "https://issuer.example/public-terms"},
        parameters={"instrument_kind": "corporate_bond", "maturity_date": MATURITY,
                    "plain_nominal_noncallable": True})
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert assumptions(result, "bond_duration_maturity_bound")[0]["duration_years"] == BOUND
    assert result["score"] is None


@pytest.mark.parametrize("field,value", [("auction_high_yield_pct", 99.9), ("coupon_rate_pct", 0)])
def test_auction_yield_or_coupon_field_alone_never_creates_current_yield_or_zero_repricer(field, value):
    bond = reference_bond()
    before = calculate([bond], baseCurrency="USD", cash=100)
    bond["market_data"]["details"][field] = value
    after = calculate([bond], baseCurrency="USD", cash=100)
    assert after["score"] is None and not after["rating_evidence"]
    assert after["provisional_scenarios"] == before["provisional_scenarios"]
    # An observed static coupon stays in the evidence, while model method and
    # all numerical results remain invariant. Zero coupon needs affirmative
    # supported repricer inputs, not a solitary raw field.
    for r in assumptions(after, "government_bond_proxy"):
        assert r["reference_facts"]["coupon_rate_pct"] == bond["market_data"]["details"]["coupon_rate_pct"]
    normalized = deepcopy(after["provisional_assumptions"])
    for r in normalized:
        if "reference_facts" in r:
            r["reference_facts"]["coupon_rate_pct"] = 4.25
    assert normalized == before["provisional_assumptions"]


@pytest.mark.parametrize("basis,defaulted,expected_range", [("local_currency", True, True),
                                                          ("foreign_currency", True, False),
                                                          ("local_currency", False, False)])
def test_derived_us_local_obligation_preserves_matched_recovery_axis(basis, defaulted, expected_range):
    bond = reference_bond()
    bond["stress_risk"]["country"] = {"country_code": "US", "basis": "economic_exposure"}
    bond["stress_risk"]["sovereign_ratings"] = {basis: opinion("D" if defaulted else "AAA", currency_basis=basis)}
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert (result["provisional_scope"] == "known_values") == expected_range


def test_exact_performing_issue_wins_over_us_local_issuer_recovery_fallback():
    bond = reference_bond()
    bond["stress_risk"].update(country={"country_code": "US", "basis": "economic_exposure"},
        credit_rating=opinion("AA", scope="issue"),
        sovereign_ratings={"local_currency": opinion("D", currency_basis="local_currency")})
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert result["provisional_scope"] == "portfolio"
    assert not assumptions(result, "recovery_model_required")
    assert not assumptions(result, "unrated_credit_proxy")


@pytest.mark.parametrize("issue_changes", [
    {"rating_date": "2026-11-15"}, {"fetched_at": "2026-11-15"},
    {"stale": True}, {"scale": "national"}, {"term": "short_term"},
    {"status": "withdrawn"}, {"source_kind": "manual", "verified": False},
])
def test_ineligible_issue_cannot_suppress_current_matched_local_sovereign_recovery(issue_changes):
    bond = reference_bond()
    bond["stress_risk"].update(country={"country_code": "US", "basis": "economic_exposure"},
        credit_rating=opinion("AA", scope="issue", **issue_changes),
        sovereign_ratings={"local_currency": opinion("D", currency_basis="local_currency")})
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert result["provisional_scope"] == "known_values"
    assert result["provisional_range"] == {"min": 0, "max": 100}
    assert assumptions(result, "recovery_model_required")


@pytest.mark.parametrize("default_issue", [False, True])
def test_issue_arrays_keep_issue_priority_for_the_derived_sovereign(default_issue):
    bond = reference_bond()
    bond["stress_risk"].update(country={"country_code": "US", "basis": "economic_exposure"},
        credit_rating=[opinion("AAA" if default_issue else "D", scope="issuer"),
                       opinion("D" if default_issue else "AA", scope="issue")],
        sovereign_ratings={"local_currency": opinion("AAA" if default_issue else "D", currency_basis="local_currency")})
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert (result["provisional_scope"] == "known_values") == default_issue


def test_exact_us_reference_does_not_import_another_countrys_grade_or_recovery():
    bond = reference_bond()
    bond["stress_risk"].update(country={"country_code": "BR", "basis": "issuer_domicile_proxy"},
        sovereign_ratings={"local_currency": opinion("D", currency_basis="local_currency"),
                           "foreign_currency": opinion("D", currency_basis="foreign_currency")},
        country_requires_recovery_model=True)
    result = calculate([bond], baseCurrency="USD", cash=100)
    assert result["provisional_scope"] == "portfolio"
    assert not assumptions(result, "recovery_model_required")
    assert assumptions(result, "unrated_credit_proxy")[0]["spread_bps"] == 200


def test_json_roundtrip_and_intrinsic_wrapper_preserve_bound_reference_without_mutation():
    bond = reference_bond()
    setup = """
const PortfolioStressRisk=require('./web/stress-risk.js');
const state={baseCurrency:'USD',riskAsOf:'2026-11-14',fxRates:{},riskRevision:'qa'};
"""
    result = node(setup + app_functions("riskStrictBaseValue", "riskScoreForItems") +
                  "const original=" + json.dumps(bond) + ";const saved=JSON.stringify(original);const restored=JSON.parse(saved);" + """
const risk=riskScoreForItems([restored],{cash:100});
const intrinsic=risk.position_risks.get(restored);
console.log(JSON.stringify({whole:risk.provisional_score,loss:risk.provisional_loss,
 intrinsic:intrinsic.provisional_score,intrinsicAssumptions:intrinsic.provisional_assumptions,
 unchanged:JSON.stringify(original)===saved&&JSON.stringify(restored)===saved}));
""")
    expected_loss = -100 * math.expm1(-BOUND * .03)
    assert result["whole"] == math.floor(100 * expected_loss / 200 + .5 + 1e-10)
    assert result["loss"] == pytest.approx(expected_loss)
    assert result["intrinsic"] == math.floor(expected_loss + .5 + 1e-10)
    assert any(r["code"] == "bond_duration_maturity_bound" for r in result["intrinsicAssumptions"])
    assert result["unchanged"]


def test_issued_contexts_preserve_reference_and_detect_reference_changes_before_history_write(tmp_path):
    store = LocalPortfolioStore(tmp_path / "synthetic-reference-history.sqlite3")
    bond = reference_bond()
    inputs = risk_history.canonical_inputs([bond], [{"id": "synthetic-account", "type": "Investment",
        "currency": "USD", "initial_cash": 100}], [], {"quotes": []}, "USD")
    inputs["guard"] = ("qa-reference-source", 1, "qa-risk-revision")
    capture = lambda _: deepcopy(inputs)
    context = risk_history.create_context(store, "qa-author", "USD", capture)
    scenario = risk_scenarios.create_context("USD", capture)
    assert context["items"][0]["market_data"] == scenario["items"][0]["market_data"] == bond["market_data"]
    assert json.loads(json.dumps(context))["items"][0]["market_data"] == bond["market_data"]
    risk = calculate(context["items"], baseCurrency="USD", cash=100)
    assert risk["provisional_score"] == math.floor(100 * (-100 * math.expm1(-BOUND * .03)) / 200 + .5 + 1e-10)
    payload = {"token": context["token"], "total": risk,
               "accounts": [{"account_id": "synthetic-account", "risk": risk}]}
    saved = risk_history.save_observation(store, "qa-author", payload, capture, lambda: inputs["guard"])["observation"]
    frozen = deepcopy(saved)
    stored_proxy = next(x for x in saved["total"]["provisional_assumptions"] if x["code"] == "government_bond_proxy")
    assert stored_proxy["reference_facts"]["identifier"] == "91282CKD2"
    assert stored_proxy["reference_facts"]["floating_rate"] is False
    assert stored_proxy["maturity_date"] == MATURITY
    # Returned frozen contexts do not share references with live capture.
    scenario["items"][0]["market_data"]["details"]["maturity_date"] = "2040-01-01"
    assert inputs["items"][0]["market_data"]["details"]["maturity_date"] == MATURITY
    inputs["items"][0]["market_data"]["details"]["maturity_date"] = "2030-02-28"
    changed = risk_history.create_context(store, "qa-author", "USD", capture)
    assert changed["fingerprint"] != context["fingerprint"]
    with pytest.raises(risk_history.RiskHistoryError, match="risk_context_stale"):
        risk_history.save_observation(store, "qa-author", payload, capture, lambda: inputs["guard"])
    displayed = risk_history.list_observations(store, "USD", 0)["items"]
    assert len(displayed) == 1
    assert {key: value for key, value in displayed[0].items() if key != "performance"} == {
        key: value for key, value in frozen.items() if key != "performance_snapshot"}
    with store._connect() as connection:
        stored = connection.execute("select value from app_preferences where key glob ? and json_extract(value,'$.id')=?",
                                    (risk_history.PREFIX + "*", frozen["id"])).fetchone()
    assert json.loads(stored["value"]) == frozen


def test_actual_backend_serialization_keeps_cached_reference_without_fetch_write_or_price_replacement(tmp_path, monkeypatch):
    from app import main
    from app.config import AppConfig
    from app.models import Holding, SymbolAnalysis, Trend
    from app.security_market_data import SecurityMarketData

    bond = reference_bond()
    reference = deepcopy(bond["market_data"])
    reference["quote"] = {"price": 999999, "price_date": AS_OF, "currency": "USD", "quote_unit": "percent_of_par"}
    class FrozenClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 14, 12, tzinfo=timezone.utc)
    reads = []
    class ReadonlyCache:
        def get_security_snapshot(self, provider, symbol, datatype):
            reads.append((provider, symbol, datatype))
            return deepcopy(reference) if (provider, symbol, datatype) == ("security_lookup", "91282CKD2", "security-market-data-v2:latest:bond") else None
        def set_security_snapshot(self, *args):
            pytest.fail("Risk display must not write reference cache")
    store = SimpleNamespace(list_security_industry_overrides=lambda: [], list_security_exposure_profiles=lambda: [], list_prices=lambda: [])
    hub = SimpleNamespace(cache=ReadonlyCache(), cached_profile=lambda *args, **kwargs: {})
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "hub", lambda: hub)
    monkeypatch.setattr(main, "datetime", FrozenClock)
    monkeypatch.setattr(main, "config", AppConfig(raw={}, path=tmp_path / "unused-public-config.yaml"))
    monkeypatch.setattr(SecurityMarketData, "_providers", lambda *args: pytest.fail("Saved reference display must not fetch providers"))
    analysis = SymbolAnalysis(holding=Holding(**bond["holding"]), provider_status={}, price_ranges=bond["price_ranges"],
        moving_averages={}, support_resistance={}, volume={}, income_trend=Trend(), profit_trend=Trend(),
        dividend_trend=Trend(), profit_market_cap_trend=Trend(), industry="Bonds", missing=[])
    before = deepcopy(analysis)
    payload = main._serialized_portfolio_payload([analysis], "synthetic")
    restored = json.loads(json.dumps(payload))["items"][0]
    assert restored["holding"]["market_value"] == 100 and restored["holding"]["quantity"] == 1
    assert restored["market_data"]["security"] == reference["security"]
    assert restored["market_data"]["details"] == reference["details"]
    assert restored["market_data"]["quote"]["price"] == 999999
    assert restored["market_data"]["provider_requests"] == 0 and restored["market_data"]["portfolio_updated"] is False
    assert ("security_lookup", "91282CKD2", "security-market-data-v2:latest:bond") in reads
    result = calculate([restored], baseCurrency="USD", cash=100)
    assert result["provisional_loss"] == pytest.approx(-100 * math.expm1(-BOUND * .03))
    assert assumptions(result, "bond_duration_maturity_bound")
    assert analysis == before


@pytest.mark.parametrize("language,width", [(lang, width) for lang in ("en", "he") for width in (1440, 390, 320)])
def test_actual_renderer_treasury_bound_is_estimated_dated_and_readable(tmp_path, chromium, language, width):
    fixture = cash_browser_document(tmp_path, language)
    bond = reference_bond()
    bond["holding"].update(account="Synthetic Treasury", account_type="Investment", location="USA",
                            cost_basis=100, unrealized_profit=0)
    bond.update(industry="Bonds", exchange="MANUAL", missing=[])
    setup = """
qa.holdings=[REFERENCE_BOND];
state.localAccounts=[{id:'synthetic-account',username:'Synthetic Treasury',type:'Investment',
 currency:'USD',initial_cash:100,persons:[]}];
state.localTransactions=[];state.items=state.allPortfolioItems=qa.holdings;
state.baseCurrency='USD';state.fxRates={};state.riskAsOf='2026-11-14';state.localFunds=[];
state.dashboard=defaultDashboard();
state.dashboard.widgets=state.dashboard.widgets.map(w=>({...w,view:w.id==='portfolio_value'?'basic':'hidden'}));
qa.render=()=>{const restore=preservePortfolioViewport();try{renderAnalytics(qa.holdings);PortfolioI18n.applyToDocument(state.language);}finally{restore();}};
qa.render();PortfolioI18n.observe();qa.fixtureReady=true;
""".replace("REFERENCE_BOND", json.dumps(bond))
    app = tmp_path / "cash-app.js"
    app.write_text(app.read_text() + "\n" + setup)
    command, evaluate = chromium
    command("Emulation.setFocusEmulationEnabled", {"enabled": True})
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": fixture.as_uri()})
    browser_wait(evaluate, "window.qa?.fixtureReady===true||!!window.qa?.errors?.length")
    assert evaluate("qa.errors") == []
    risk = evaluate("state.riskSnapshot.accounts[0].risk")
    expected_loss = -100 * math.expm1(-BOUND * .03)
    assert risk["score"] is None and risk["provisional_loss"] == pytest.approx(expected_loss)
    expected_score = math.floor(100 * expected_loss / 200 + .5 + 1e-10)
    assert risk["provisional_score"] == expected_score
    evaluate("qa.badge=document.querySelector('[data-account-summary=synthetic-account] .risk-badge');qa.badge.scrollIntoView({block:'center'});qa.badge.focus()")
    browser_wait(evaluate, "!$('riskBadgeExplanation').hidden")
    assert evaluate("qa.badge.querySelector('b bdi').textContent") == str(expected_score)
    exact_loss = f"~{100 * expected_loss / 200:.2f}%"
    badge_text = evaluate("qa.badge.innerText")
    assert "~" not in badge_text and "%" not in badge_text
    assert exact_loss in evaluate("$('riskBadgeExplanation').innerText")
    assert evaluate("qa.badge.scrollWidth<=qa.badge.clientWidth+1")
    assert "⚠" in evaluate("qa.badge.textContent")
    lines = evaluate("stressRiskProxyAssumptionLines(state.riskSnapshot.accounts[0].risk).join('\\n')")
    for text in ["Sensitivity proxy capped by verified remaining maturity", "This bound does not establish actual coupon duration.",
                 "Reference retrieval date", "Maturity date"]:
        assert evaluate("optionLabel(" + json.dumps(text) + ")") in lines
    assert "28/02/2029" in lines and "14/11/2026" in lines
    assert evaluate("optionLabel('Source observation date')") not in lines
    assert "2029-02-28" not in lines and "2026-11-14T" not in lines
    if language == "he":
        assert not any(label in lines for label in ["Sensitivity proxy", "Reference retrieval", "Maturity date", "actual coupon duration"])
    geometry = evaluate("(()=>{const r=$('riskBadgeExplanation').getBoundingClientRect();return{left:r.left,right:r.right,bottom:r.bottom,overflow:document.documentElement.scrollWidth-innerWidth}})()")
    assert geometry["left"] >= 0 and geometry["right"] <= width and geometry["bottom"] <= 1000
    assert geometry["overflow"] <= 1
    if evaluate("$('riskBadgeExplanation').scrollHeight>$('riskBadgeExplanation').clientHeight"):
        command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "End", "code": "End", "windowsVirtualKeyCode": 35})
        assert evaluate("$('riskBadgeExplanation').scrollTop") > 0
        command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Home", "code": "Home", "windowsVirtualKeyCode": 36})
        assert evaluate("$('riskBadgeExplanation').scrollTop") == 0
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
    browser_wait(evaluate, "$('riskBadgeExplanation').hidden")
    assert evaluate("qa.errors") == []
