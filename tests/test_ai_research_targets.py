"""Freshness and field-selection regressions for existing bounded workers."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.risk_input_retrieval import missing_fields, refresh_fields
from test_risk_input_retrieval import candidate, environment, queue, Deferred


def complete_risk(kind="equity"):
    today = datetime.now(timezone.utc).date()
    return {"revision": 0, "issuer_id": "sec:1513363", "country": {"country_code": "US", "basis": "economic_exposure"},
        "country_rating": {"status": "rated"}, "credit_rating": {"status": "rated"},
        "currency_exposures": {"USD": 1}, "parameters": {"instrument_kind": kind, "country_currency": "USD",
            "maturity_date": (today+timedelta(days=365)).isoformat(), "plain_nominal_noncallable": True,
            "pricing_model": "cashflows_continuous", "cashflows": [{"date": (today+timedelta(days=365)).isoformat(), "amount": 100}],
            "continuous_yield": .04, "current_spread_bps": 100, "country_sensitivity": 1, "as_of": today.isoformat()}}


def test_complete_bond_refresh_requests_variable_and_contractual_evidence():
    item = {**candidate(), "asset_class": "BOND"}
    risk = complete_risk("corporate_bond")
    assert missing_fields(risk, item) == []
    assert {"current_spread", "bond_yield", "bond_cashflows", "bond_maturity", "bond_terms", "country_sensitivity"} <= set(refresh_fields(risk, item))


def test_refresh_existing_runs_ai_even_when_api_phase_leaves_no_gap(environment, monkeypatch):
    retrieval, child, _, _ = queue(environment)
    risk = complete_risk()
    monkeypatch.setattr(retrieval.evidence.inputs, "read", lambda _: deepcopy(risk))
    assert retrieval.evidence.candidates()["items"] == []
    candidates = retrieval.evidence.candidates(refresh_policy="refresh_existing")["items"]
    assert len(candidates) == 1 and candidates[0]["missing_fields"] == []
    assert candidates[0]["refresh_requested"] is True
    job = retrieval.start("owner", {}, "en", mode="api_then_ai", refresh_policy="refresh_existing")
    Deferred.callbacks.pop(0)()
    result = retrieval.get(job["request_id"], "owner")
    assert len(child.calls) == 1
    assert child.calls[0][3]["candidate_options"] == {"refresh_policy": "refresh_existing"}
    assert result["outcomes"][0]["status"] == "unavailable"  # An unchanged complete field is not a new verified update.
    assert result["counts"]["model_requests"] == 8


def test_risk_all_scope_includes_closed_public_entries_but_never_private(environment):
    _, inventory, _ = environment
    inventory[:] = [{**candidate("CLOSED"), "has_open_position": False},
        {**candidate("PRIVATE"), "stock_market": "PRIVATE", "asset_class": "PRIVATE_STOCK"}]
    retrieval, _, _, _ = queue(environment)
    assert retrieval.evidence.candidates()["items"] == []
    rows = retrieval.evidence.candidates(position_scope="all", refresh_policy="refresh_existing")["items"]
    assert [row["symbol"] for row in rows] == ["CLOSED"]


def test_stale_bond_pricing_can_be_selected_separately_from_absent_fields(environment, monkeypatch):
    _, inventory, _ = environment
    inventory[0]["asset_class"] = "BOND"
    retrieval, _, _, _ = queue(environment)
    risk = complete_risk("corporate_bond")
    risk["parameters"]["as_of"] = "2000-01-01"
    monkeypatch.setattr(retrieval.evidence.inputs, "read", lambda _: deepcopy(risk))
    assert missing_fields(risk, inventory[0]) == ["parameters_stale"]
    assert retrieval.evidence.candidates(refresh_policy="missing")["items"] == []
    assert len(retrieval.evidence.candidates(refresh_policy="stale")["items"]) == 1


def test_selected_complete_listing_finishes_without_ai_under_missing_policy(environment, monkeypatch):
    retrieval, child, _, _ = queue(environment)
    monkeypatch.setattr(retrieval.evidence.inputs, "read", lambda _: complete_risk())
    job = retrieval.start("owner", {}, "en", security_keys=[candidate()["security_key"]])
    Deferred.callbacks.pop(0)()
    result = retrieval.get(job["request_id"], "owner")
    assert result["status"] == "completed" and result["coverage"]["selected"] == 0
    assert child.calls == []


def test_active_risk_job_cannot_be_reused_for_another_scope_policy_or_scheduled_rule(environment):
    from fastapi import HTTPException
    retrieval, _, _, _ = queue(environment)
    original = retrieval.start("owner", {}, "en")
    assert retrieval.start("owner", {}, "en")["request_id"] == original["request_id"]
    for changes in ({"position_scope":"all"}, {"refresh_policy":"refresh_existing"},
                    {"scheduled_credentials":lambda:pytest.fail("Busy scheduled job must not create a session")}):
        with pytest.raises(HTTPException) as failure:
            retrieval.start("owner", {}, "en", **changes)
        assert failure.value.status_code == 409


def test_dated_sec_office_address_is_only_a_proxy_and_requires_exact_filing_binding():
    from app.risk_input_sources import extract_risk_records
    url="https://www.sec.gov/Archives/edgar/data/1513363/000119312526449784/fdus-20260930.htm"
    item={**candidate(),"researched_issuer_id":"sec:1513363","source_evidence":[{"field":"filing_sources","value":[{"url":url}]}]}
    source={"url":url,"text":"Fidus Investment Corp\n(Exact Name of Registrant as Specified in its Charter)\n1603 Orrington Avenue\nEvanston, Illinois 60201\n(Address of Principal Executive Offices)(Zip Code)",
        "observation_date":"2026-09-30","retrieved_at":"2026-11-14T10:00:00Z"}
    records=extract_risk_records(source,item)
    fields={row["field"]:row for row in records}
    assert fields["country_code"]["value"]=="US" and fields["country_code"]["as_of"]=="2026-09-30"
    assert fields["country_basis"]["value"]=="issuer_domicile_proxy"
    assert not {"country_currency","currency_exposures"} & set(fields)
    assert "country_code" not in {row["field"] for row in extract_risk_records({**source,"observation_date":None},item)}
    assert not extract_risk_records({**source,"url":url.replace("449784","449785")},item)
    assert "country_code" not in {row["field"] for row in extract_risk_records({**source,"text":source["text"].replace("Principal Executive Offices","Registered Agent")},item)}
