"""Independent partial-risk acceptance from synthetic economic facts.

Expectations use the maintained equations and contractual payment dates. No
runtime portfolio, credentials, generated score, or developer verdict is used
as the expected result. The normal pytest conftest isolates application stores.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from app import risk_history
from app.local_portfolio import LocalPortfolioStore
from app.auth import AuthStore
from app.risk_input_retrieval import RiskInputRetrieval
from app.risk_input_sources import extract_risk_records
from app.stress_risk_inputs import StressRiskInputs


ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-11-14"
MATURITY = "2032-11-14"


def agency(grade="AAA", scope="sovereign", **changes):
    return {"status": "rated", "rating": grade, "agency": "sp", "scope": scope,
            "scale": "global", "term": "long_term", "source_kind": "agency_public",
            "verified": True, "stale": False, "currency_basis": "local_currency", **changes}


def position(symbol="UNMODELED", value=100, kind="sovereign_bond", account="a"):
    params = {"instrument_kind": kind, "country_currency": "USD", "as_of": AS_OF,
              "current_spread_bps": 50, "country_sensitivity": 1,
              "pricing_model": "zero_coupon_continuous", "maturity_date": MATURITY,
              "plain_nominal_noncallable": True, "zero_coupon_confirmed": True,
              "sovereign_currency_basis": "local_currency"}
    return {"holding": {"symbol": symbol, "stock_market": "NYSE", "currency": "USD",
                        "quantity": value, "market_value": value,
                        "asset_class": "BOND" if kind.endswith("bond") else "EQUITY", "account_id": account},
            "stress_risk": {"security_key": symbol + "|NYSE|USD", "valuation_date": AS_OF,
                            "issuer_id": "sovereign:US" if kind == "sovereign_bond" else "legal:" + symbol,
                            "country": {"country_code": "US", "basis": "economic_exposure"},
                            "currency_exposures": {"USD": 1}, "country_rating": agency(),
                            "sovereign_rating": agency(), "credit_rating": agency(scope="issue"),
                            "parameters": params}}


def node(script):
    output = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT)
    assert output.returncode == 0, output.stderr
    return json.loads(output.stdout)


def assess(items, **options):
    settings = {"baseCurrency": "USD", "asOf": AS_OF, **options}
    return node("const risk=require('./web/stress-risk.js');console.log(JSON.stringify(risk.calculate("
                + json.dumps(items) + "," + json.dumps(settings) + ")));" )


def severity(loss, equity):
    return math.floor(min(100, 200 * loss / equity) + .5)


def incomplete(position_):
    position_["stress_risk"].pop("sovereign_rating", None)
    position_["stress_risk"].pop("credit_rating", None)
    position_["stress_risk"]["parameters"].pop("maturity_date", None)
    return position_


def test_multiple_gaps_lots_and_accounts_preserve_one_scenario_exposure_without_mutation():
    whole = [incomplete(position())]
    pieces = [incomplete(position(value=25, account=str(i))) for i in range(4)]
    original = deepcopy(pieces)
    for items in (whole, pieces):
        result = assess(items, cash=400)
        assert result["score"] is None and result["estimated_score"] is None
        assert result["status"] == "incomplete" and len(result["gaps"]) >= 2
        loss = 100 * (1 - math.exp(-5 * (.02 + .5 * .02)))
        assert result["provisional_model"] == "portfolio-risk-provisional-v2"
        assert result["provisional_score"] == severity(loss, 500) == 6
        assert result["provisional_loss"] == pytest.approx(loss)
        assert result["provisional_proxy_gross"] == 100
        assert result["provisional_basis"] == "asset_aware_scenarios"
        assert result["coverage"]["covered_value_percent"] == 80
    assert pieces == original


def test_supported_zero_coupon_and_proxy_debt_use_original_equity_and_common_scenario():
    result = assess([position("KNOWN", 60), incomplete(position("UNKNOWN", 40))])
    elapsed = (date.fromisoformat(MATURITY) - date.fromisoformat(AS_OF)).days / 365.25
    known_loss = 60 * (1 - math.exp(-elapsed * (.02 + .5 * .005)))
    assert result["net_equity"] == 100
    proxy_loss = 40 * (1 - math.exp(-5 * (.02 + .5 * .02)))
    assert result["provisional_loss"] == pytest.approx(known_loss + proxy_loss)
    assert result["provisional_score"] == severity(known_loss + proxy_loss, 100) == 26
    assert result["score"] is None


def test_partial_nested_fund_preserves_verified_children_and_proxies_only_the_missing_bond():
    fund = position("WRAPPER", 100, "fund")
    fund["holding"]["asset_class"] = "ETF"
    child = position("NESTED", 60, "fund")
    child["holding"]["asset_class"] = "ETF"
    child["stress_risk"].update(lookthrough_verified=True, lookthrough=[
        {"weight": .5, "item": position("KNOWN", 30, "equity")},
        {"weight": .5, "item": incomplete(position("GAP", 30))}])
    fund["stress_risk"].update(lookthrough_verified=True, lookthrough=[
        {"weight": .4, "item": position("OTHER", 40, "equity")}, {"weight": .6, "item": child}])
    result = assess([fund], cash=400)
    # Reported weights establish 70 equity +30 government debt; unknown bond
    # terms use the duration/credit proxy without wiping out the wrapper.
    assert result["partial_stress_loss"] > 0
    loss = 70 * .4 + 30 * (1 - math.exp(-5 * (-.01 + .02)))
    assert result["provisional_proxy_gross"] == 100
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == severity(loss, 500) == 12


def test_supported_signed_hedge_remains_in_the_common_scenarios():
    long = position("HEDGE", 60, "equity")
    short = position("HEDGE", -60, "equity", "b")
    result = assess([long, short, incomplete(position("UNKNOWN", 40))], cash=200)
    # Equal signed positions in the same issuer offset each scenario exactly.
    assert result["net_equity"] == 240
    loss = 40 * (1 - math.exp(-5 * (.02 + .5 * .02)))
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == severity(loss, 240) == 5


def test_late_foreign_systemic_gap_keeps_strict_gap_and_uses_a_declared_fx_proxy():
    item = position()
    item["stress_risk"].pop("country_rating")
    result = assess([item], baseCurrency="ILS", cash=400)
    assert any(g["code"] == "country_rating" and g.get("detail") == "foreign_currency_fx" for g in result["gaps"])
    elapsed = (date.fromisoformat(MATURITY) - date.fromisoformat(AS_OF)).days / 365.25
    loss = 100 * (1 - .85 * math.exp(-elapsed * (.02 + .5 * .005)))
    assert result["provisional_proxy_gross"] == 100
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["provisional_score"] == severity(loss, 500) == 10
    assert result["score"] is None
    assert result["coverage"]["covered_value_percent"] == 80
    assert result["coverage"]["covered_value"] == 400


def test_unresolved_systemic_fx_opinion_retains_foreign_cash_in_numeric_estimate_not_verified_coverage():
    item = position()
    item["stress_risk"].pop("country_rating")
    result = assess([item], baseCurrency="ILS", cashAccounts=[{"value": 400, "currency": "USD"}])
    elapsed = (date.fromisoformat(MATURITY) - date.fromisoformat(AS_OF)).days / 365.25
    loss = 100 * (1 - .85 * math.exp(-elapsed * (.02 + .5 * .005))) + 400 * .15
    assert result["score"] is None and result["provisional_score"] == severity(loss, 500) == 34
    assert result["provisional_basis"] == "asset_aware_scenarios"
    assert result["provisional_loss"] == pytest.approx(loss)
    assert result["coverage"]["covered_value_percent"] == 0


@pytest.mark.parametrize("cause", ["unknown_value", "stale_value", "future_value", "missing_cash", "short", "nonlinear", "leverage"])
def test_unknown_scope_is_ranged_while_stale_marks_and_linear_shorts_keep_financial_estimates(cause):
    item = incomplete(position())
    options = {"cash": 400}
    if cause == "unknown_value": item["holding"]["market_value"] = None
    elif cause == "stale_value": item["stress_risk"]["valuation_date"] = "2026-11-06"
    elif cause == "future_value": item["stress_risk"]["valuation_date"] = "2026-11-15"
    elif cause == "missing_cash": options["cash"] = None
    elif cause == "short": item["holding"].update(market_value=-100, quantity=-100)
    elif cause == "nonlinear": item["holding"]["asset_sub_class"] = "OPTION"
    elif cause == "leverage": item["exposure_profile"] = {"leverage_type": "leveraged"}
    result = assess([item], **options)
    assert result["score"] is None and result["status"] == "incomplete"
    assert result["provisional_basis"] == "asset_aware_scenarios"
    if cause in {"stale_value", "short"}:
        loss = 100 * (1 - math.exp(-5 * .03)) if cause == "stale_value" else 100 * math.expm1(5 * .025)
        equity = 500 if cause == "stale_value" else 300
        assert result["provisional_scope"] == "portfolio"
        assert result["provisional_loss"] == pytest.approx(loss)
        assert result["provisional_score"] == severity(loss, equity)
    else:
        assert result["provisional_scope"] == "known_values"
        assert result["provisional_range"] == {"min": 0, "max": 100}
    assert result["worst_scenario"] != "nonpositive_equity"


def test_numeric_precedence_preserves_verified_estimate_and_known_boundaries():
    assert assess([])["score"] == 0
    verified = assess([position()])
    assert verified["score"] == 25 and "provisional_score" not in verified
    item = position()
    item["stress_risk"]["sovereign_rating"].update(rating="BBB", manual_override=True)
    item["stress_risk"]["parameters"]["assumptions_enabled"] = True
    estimate = assess([item])
    assert estimate["status"] == "estimate" and estimate["score"] is None
    assert estimate["estimated_score"] == 33 and "provisional_score" not in estimate
    boundary = assess([incomplete(position())], cash=-200)
    assert boundary["score"] == 100 and boundary["gaps"]
    assert boundary["worst_scenario"] == "nonpositive_equity" and "provisional_score" not in boundary


def test_history_keeps_saved_v1_and_current_v2_immutable_without_recalculation(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa-history.sqlite3")
    item = incomplete(position())
    inputs = risk_history.canonical_inputs([item], [{"id": "a", "type": "Investment", "currency": "USD", "initial_cash": 400}], [], {"quotes": []}, "USD")
    inputs["guard"] = ("qa-source", 1)
    capture = lambda _: deepcopy(inputs)
    now = datetime(2026, 11, 14, 10, tzinfo=timezone.utc)
    monkeypatch.setattr(risk_history, "_now", lambda: now)
    old = assess([item], cash=400)
    for field in list(old):
        if field.startswith("provisional_"): del old[field]
    old.update(provisional_model="portfolio-risk-provisional-v1", provisional_score=40,
               provisional_basis="unmodeled_exposure_allowance", provisional_loss=100,
               provisional_unmodeled_gross=100)
    context = risk_history.create_context(store, "qa-author", "USD", capture)
    legacy = risk_history.save_observation(store, "qa-author", {"token": context["token"], "total": old, "accounts": [{"account_id": "a", "risk": old}]}, capture, lambda: inputs["guard"])["observation"]
    monkeypatch.setattr(risk_history, "_now", lambda: now + timedelta(days=1))
    partial = assess([item], cash=400)
    context = risk_history.create_context(store, "qa-author", "USD", capture)
    saved = risk_history.save_observation(store, "qa-author", {"token": context["token"], "total": partial, "accounts": [{"account_id": "a", "risk": partial}]}, capture, lambda: inputs["guard"])["observation"]
    partial["provisional_score"] = 99
    inputs["items"][0]["stress_risk"]["issuer_id"] = "corrected-later"
    rows = risk_history.list_observations(LocalPortfolioStore(store.path), "USD", 0)["items"]
    assert rows[0] == legacy and rows[0]["total"]["provisional_score"] == 40
    assert rows[0]["total"]["provisional_model"] == "portfolio-risk-provisional-v1"
    assert rows[1] == saved and rows[1]["total"]["provisional_score"] == 6
    assert rows[1]["total"]["provisional_model"] == "portfolio-risk-provisional-v2"
    assert rows[1]["total"]["score"] is None
    assert rows[1]["evidence"]["stress_inputs"][0]["inputs"]["issuer_id"] == "sovereign:US"


def test_risk_reduction_rejects_partial_numbers_even_when_they_look_low():
    result = node("""
const scenarios=require('./web/risk-scenarios.js');
const context={model:'portfolio-risk-v3',base_currency:'USD',observed_at:'2026-11-14T10:00:00Z',
 accounts:[{id:'a',type:'Investment',currency:'USD',initial_cash:400}],transactions:[],fx:{quotes:[]},items:[]};
const partial={model:'portfolio-risk-v3',status:'incomplete',score:null,estimated_score:null,provisional_score:0};
scenarios.generate(context,{calculate:()=>({total:partial,accounts:[{key:'a',risk:partial}]})}).then(result=>console.log(JSON.stringify(result)));
""")
    assert result["status"] == "incomplete" and result["scenarios"] == [] and result["eligibleCount"] == 0


def test_history_graph_keeps_verified_explicit_estimate_and_provisional_series_separate():
    script = """
const document={addEventListener(){}};
const state={language:'en'};
const t=x=>x,esc=x=>String(x),formatDate=x=>x.split('-').reverse().join('/'),formatDateTime=x=>x;
""" + (ROOT / "web/risk-history-ui.js").read_text() + """
const sample=(day,risk,model='portfolio-risk-v3')=>({model,date:`2026-11-${day}`,observed_at:`2026-11-${day}T10:00:00Z`,risk});
const verified={status:'ok',score:20};
const explicit={status:'estimate',score:null,estimated_score:25};
const partial={status:'incomplete',score:null,provisional_model:'portfolio-risk-provisional-v1',provisional_score:40};
const current={status:'incomplete',score:null,provisional_model:'portfolio-risk-provisional-v2',provisional_score:6,provisional_scope:'portfolio'};
const rows=[sample('01',verified),sample('02',explicit),sample('03',partial),sample('04',partial),
 sample('05',current),sample('06',current),sample('07',{status:'incomplete',score:null,provisional_model:'portfolio-risk-provisional-v2',provisional_scope:'known_values',provisional_score:0,provisional_range:{min:0,max:100}}),sample('08',verified),sample('09',verified,'portfolio-risk-v2')];
const html=riskHistoryGraph(rows,'QA portfolio');
console.log(JSON.stringify({html,path:html.match(/<path d="([^"]*)"/)[1]}));
"""
    result = node(script)
    assert result["html"].count("<circle ") == 8
    assert result["path"].count("L") == 2
    assert result["path"].count("M") == 6
    assert "~40/100 ⚠ Partial data" in result["html"] and "~25/100" in result["html"]


def test_retrieval_never_attributes_another_sec_issuers_allocations_from_a_name_mention():
    expected_url = "https://www.sec.gov/Archives/edgar/data/1513363/000119312526449784/fdus-20260930.htm"
    candidate = {"security_key": "FDUS|NASDAQ|USD", "symbol": "FDUS", "name": "Fidus Investment Corporation",
                 "issuer_name": "Fidus Investment Corporation", "researched_issuer_id": "sec:1513363",
                 "verified_issuer_domains": ["fdus.com"], "source_evidence": [
                     {"field": "filing_sources", "value": [{"url": expected_url, "as_of": "2026-09-30", "published_at": "2026-11-05"}]}]}
    source = {"url": "https://www.sec.gov/Archives/edgar/data/999999/000099999926000001/other-20260930.htm",
              "source_id": "qa-wrong-issuer", "observation_date": "2026-09-30", "retrieved_at": "2026-11-14T15:45:00Z",
              "text": "OTHER INVESTMENT CORPORATION. We own notes issued by Fidus Investment Corporation. "
                      "All of our investments are denominated in U.S. dollars."}
    assert extract_risk_records(source, candidate) == []


@pytest.mark.parametrize("age,active", [(None, False), (0, True), (550, True), (551, False), (-1, False)])
def test_exact_bound_economic_claim_needs_eligible_observation_date(tmp_path, age, active):
    url = "https://www.sec.gov/Archives/edgar/data/1513363/000119312526449784/fdus-20260930.htm"
    item = {"security_key": "FDUS|NASDAQ|USD", "symbol": "FDUS", "asset_class": "EQUITY",
            "issuer_name": "Fidus Investment Corporation", "researched_issuer_id": "sec:1513363",
            "source_evidence": [{"field": "filing_sources", "value": [{"url": url}]}]}
    source = {"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
              "text": "Fidus Investment Corporation. All our investments are denominated in U.S. dollars."}
    if age is not None:
        source["observation_date"] = (date.today() - timedelta(days=age)).isoformat()
    records = extract_risk_records(source, item)
    assert any(row["field"] == "currency_exposures" for row in records)
    store = LocalPortfolioStore(tmp_path / "qa-source-dates.sqlite3")
    inputs = StressRiskInputs(store=lambda: store, inventory=lambda: [item], credit=lambda _: {}, sovereign=lambda _: {}, countries=lambda _: {})
    inputs.publish_evidence(item, records)
    assert (inputs.read(item)["currency_exposures"] == {"USD": 1}) is active
    # Fetch timestamp and a URL containing a period do not invent as_of.
    saved = next(row for row in inputs.read(item)["source_evidence"] if row["field"] == "currency_exposures")
    assert saved["as_of"] == source.get("observation_date")


def test_public_merge_preserves_user_parameters_newer_observation_and_revision_guard(tmp_path):
    item = {"security_key": "SYN|NYSE|USD", "symbol": "SYN", "asset_class": "BOND"}
    store = LocalPortfolioStore(tmp_path / "qa-merge.sqlite3")
    inputs = StressRiskInputs(store=lambda: store, inventory=lambda: [item], credit=lambda _: {}, sovereign=lambda _: {}, countries=lambda _: {})
    def observed(field, value, as_of):
        return {"field": field, "value": value, "as_of": as_of, "basis": "reported", "source_kind": "government_public",
                "source_url": "https://www.treasurydirect.gov/qa-synthetic", "retrieved_at": datetime.now(timezone.utc).isoformat()}
    older = (date.today() - timedelta(days=10)).isoformat()
    newer = (date.today() - timedelta(days=3)).isoformat()
    inputs.publish_evidence(item, [observed("current_spread_bps", 70, newer), observed("maturity_date", MATURITY, older)])
    raw = inputs.read(item)
    inputs.update({"security_key": item["security_key"], "expected_identity": raw["identity_token"], "expected_revision": 0,
                   "parameters": {"country_sensitivity": .2, "notes": "User supplied", "as_of": date.today().isoformat()}}, {"id": "qa-author"})
    inputs.publish_evidence(item, [observed("current_spread_bps", 100, older), observed("country_sensitivity", .9, newer)], expected_revision=1)
    merged = inputs.read(item)
    assert merged["parameters"]["country_sensitivity"] == .2
    assert merged["parameters"]["current_spread_bps"] == 70
    assert merged["parameters"]["as_of"] == newer
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as conflict:
        inputs.publish_evidence(item, [observed("maturity_date", "2040-11-14", newer)], expected_revision=0)
    assert conflict.value.status_code == 409
    assert inputs.read(item)["parameters"]["maturity_date"] == MATURITY


@pytest.mark.parametrize("failure", ["inventory", "worker_start"])
def test_failed_scheduled_launch_revokes_temporary_owner_credentials(tmp_path, failure):
    store = AuthStore(tmp_path / "qa-auth.sqlite3")
    store.initialize()
    user = store.create_user({"username": "qatemporary", "first_name": "Synthetic", "last_name": "Owner",
                              "role": "Operator", "password": "Synthetic-QA-Password!"})
    with store._connect() as connection:
        connection.execute("update app_users set must_change_password=0 where id=?", (user["id"],))
    def inventory(**_):
        if failure == "inventory": raise ValueError("Synthetic inventory failure")
        return {"items": []}
    class FailedWorker:
        def __init__(self, **_): pass
        def start(self): raise ValueError("Synthetic worker launch failure")
    retrieval = RiskInputRetrieval(SimpleNamespace(candidates=inventory), SimpleNamespace(app=None), None, None, worker_factory=FailedWorker)
    def credentials():
        token, csrf = store.scheduled_session(user["id"])
        return {"cookie": "synthetic=" + token, "x-csrf-token": csrf}, lambda: store.logout(token)
    with pytest.raises(ValueError):
        retrieval.start(user["id"], {}, mode="api", scheduled_credentials=credentials)
    with store._connect() as connection:
        assert connection.execute("select count(*) from auth_sessions where user_id=?", (user["id"],)).fetchone()[0] == 0


@pytest.mark.parametrize("statement,fields", [
    ("All our investments are denominated in U.S. dollars.", {"currency_exposures"}),
    ("All our investments are located in the United States.", {"country_code", "country_basis", "country_currency"}),
    ("As of September 30, 2026, all our investments were denominated in USD.", {"currency_exposures"}),
    ("As of 2026-09-30, all our investments are located in the United States.", {"country_code", "country_basis", "country_currency"}),
    ("Not all our investments are denominated in U.S. dollars.", set()),
    ("Not all our investments are located in the United States.", set()),
    ("It is not true that all our investments are denominated in U.S. dollars.", set()),
    ("Previously, all our investments were denominated in U.S. dollars, but we now have foreign currency investments.", set()),
    ("All our investments are denominated in U.S. dollars except our Canadian loan.", set()),
    ("All our investments are located in the United States except one German borrower.", set()),
    ("If all our investments are denominated in U.S. dollars, the calculation would be simpler.", set()),
    ("We expect that all our investments are denominated in U.S. dollars.", set()),
    ("All our investments were denominated in U.S. dollars until 2023.", set()),
    ("As of December 31, 2025, all our investments are denominated in U.S. dollars.", set()),
    ('Other Corporation stated: "All our investments are denominated in U.S. dollars."', set()),
    ("All our investments are denominated in USD. All our investments are denominated in EUR.", set()),
    ("As of December 31, 2025. All our investments are denominated in USD.", set()),
    ("All our investments are denominated in USD. This is no longer true.", set()),
    ("All our investments are located in the United States. However, one is in Germany.", set()),
])
def test_allocation_evidence_requires_whole_current_affirmative_issuer_context(statement, fields):
    item = {"security_key": "SYN|NYSE|USD", "symbol": "SYN", "issuer_name": "Example Corporation",
            "verified_issuer_domains": ["issuer.example"], "researched_issuer_id": "sec:123"}
    source = {"url": "https://issuer.example/report", "observation_date": "2026-09-30", "retrieved_at": "2026-11-14T10:00:00Z",
              "text": "Example Corporation. " + statement}
    result = extract_risk_records(source, item)
    actual = {row["field"] for row in result} & {"currency_exposures", "country_code", "country_basis", "country_currency"}
    assert actual == fields


@pytest.mark.parametrize("researched", ["both", "one"])
@pytest.mark.parametrize("public_id", ["sec:123", "issuer:example corporation"])
def test_exact_public_issuer_identity_keeps_same_issuer_concentration_across_profile_verification(tmp_path, researched, public_id):
    inventory = [{"security_key": f"{symbol}|NYSE|USD", "symbol": symbol, "stock_market": "NYSE", "currency": "USD", "asset_class": "EQUITY",
                  "issuer_name": "Example Corporation", "issuer_identity_verified": verified,
                  "verified_issuer_domains": ["issuer.example"]} for symbol, verified in [("ONE", True), ("TWO", researched == "one")]]
    store = LocalPortfolioStore(tmp_path / "qa-same-issuer.sqlite3")
    inputs = StressRiskInputs(store=lambda: store, inventory=lambda: inventory, credit=lambda _: {}, sovereign=lambda _: {}, countries=lambda _: {})
    for item in (inventory if researched == "both" else inventory[:1]):
        inputs.publish_evidence(item, [{"field": field, "value": value, "as_of": None, "basis": "reported", "verification_status": "verified",
                                       "source_kind": "regulatory" if public_id.startswith("sec:") else "issuer_ir",
                                       "source_url": "https://data.sec.gov/submissions/CIK0000000123.json" if public_id.startswith("sec:") else "https://issuer.example/report"}
                                      for field, value in [("issuer_id", public_id), ("issuer_name", "Example Corporation")]])
    positions = [position(item["symbol"], 50, "equity") for item in inventory]
    for holding, candidate in zip(positions, inventory):
        identity = inputs.read(candidate)
        # Forward the actual backend identity contract while keeping unrelated
        # synthetic pricing/country facts fixed. Raw IDs need not be rewritten
        # if the captured calculation can resolve their verified aliases.
        holding["stress_risk"].update({key: value for key, value in identity.items() if key.startswith("issuer_")})
    assert inputs.evidence(inventory[0])["fields"]["issuer_id"]["value"] == public_id
    if public_id.startswith("sec:"):
        assert positions[0]["stress_risk"]["issuer_id"] == public_id
    before = deepcopy(positions)
    # Same legal issuer: distress loses60 of100. Artificially separate names
    # would make the40 global recession bind and incorrectly report80.
    result = assess(positions)
    assert result["stress_loss"] == 60 and result["score"] == 100
    assert positions == before


def test_issuer_name_collision_never_merges_distinct_exact_ids_or_guesses_unresearched_listing(tmp_path):
    inventory = [{"security_key": f"{symbol}|NYSE|USD", "symbol": symbol, "stock_market": "NYSE", "currency": "USD", "asset_class": "EQUITY",
                  "issuer_name": "Example Corporation", "issuer_identity_verified": True} for symbol in ["ONE", "TWO", "AMBIGUOUS"]]
    store = LocalPortfolioStore(tmp_path / "qa-ambiguous-issuer.sqlite3")
    inputs = StressRiskInputs(store=lambda: store, inventory=lambda: inventory, credit=lambda _: {}, sovereign=lambda _: {}, countries=lambda _: {})
    for item, cik in zip(inventory, [123, 456]):
        inputs.publish_evidence(item, [{"field": field, "value": value, "as_of": None, "basis": "reported", "verification_status": "verified",
                                       "source_kind": "regulatory", "source_url": f"https://data.sec.gov/submissions/CIK{cik:010d}.json"}
                                      for field, value in [("issuer_id", f"sec:{cik}"), ("issuer_name", "Example Corporation")]])
    assert inputs.read(inventory[0])["issuer_id"] == "sec:123"
    assert inputs.read(inventory[1])["issuer_id"] == "sec:456"
    positions = [position(item["symbol"], value, "equity") for item, value in zip(inventory, [35, 35, 30])]
    for holding, candidate in zip(positions, inventory):
        holding["stress_risk"].update({key: value for key, value in inputs.read(candidate).items() if key.startswith("issuer_")})
    result = assess(positions)
    assert result["score"] is None and result["provisional_score"] == 80
    assert result["coverage"]["covered_value_percent"] == 70
    assert result["provisional_proxy_gross"] == 30
    assert result["provisional_loss"] == 40
    assert any(row["code"] == "security_key_issuer_proxy" for row in result["provisional_assumptions"])
