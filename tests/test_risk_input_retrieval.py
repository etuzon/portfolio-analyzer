"""Bounded retrieval, source identity, provenance and owner-bound automation."""
from copy import deepcopy
from datetime import date, timedelta
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
import httpx
import pytest

from app.local_portfolio import LocalPortfolioStore
from app.risk_input_sources import PublicRiskAPIs, SEC_TICKERS, extract_risk_records
from app.risk_input_retrieval import (RiskEvidenceResearch, RiskInputRetrieval, RiskInputRetrievalSchedules,
    PREFIX, SCHEDULE_ENDPOINT, missing_fields)
from app.stress_risk_inputs import StressRiskInputs


def candidate(symbol="FDUS"):
    return dict(symbol=symbol,stock_market="NASDAQ",currency="USD",asset_class="EQUITY",name="Fidus Investment Corp",
        issuer_name="Fidus Investment Corp",issuer_identity_verified=False,security_key=symbol+"|NASDAQ|USD",has_open_position=True)


def record(field,value,as_of=None,basis="reported"):
    return dict(field=field,value=value,as_of=as_of,basis=basis,source_url="https://data.sec.gov/submissions/CIK0001513363.json",
        source_kind="regulatory",retrieved_at="2026-11-14T10:00:00Z",verification_status="verified",evidence_quote="Exact synthetic source",units="identity_or_classification")


@pytest.fixture
def environment(tmp_path):
    store=LocalPortfolioStore(tmp_path/"risk.sqlite3")
    inventory=[candidate()]
    inputs=StressRiskInputs(store=lambda:store,inventory=lambda:inventory,credit=lambda _: {},sovereign=lambda _: {},countries=lambda _: {})
    return store,inventory,inputs


def test_sec_adapter_no_key_matches_ticker_exchange_and_never_promotes_domicile():
    requests=[]
    def fetch(request):
        requests.append(request)
        assert "authorization" not in request.headers and "api_key" not in str(request.url)
        if str(request.url)==SEC_TICKERS:
            return httpx.Response(200,json={"fields":["cik","name","ticker","exchange"],"data":[[1513363,"FIDUS INVESTMENT Corp","FDUS","Nasdaq"]]})
        return httpx.Response(200,json={"cik":1513363,"name":"FIDUS INVESTMENT Corp","tickers":["FDUS"],"exchanges":["Nasdaq"],
            "addresses":{"business":{"stateOrCountry":"IL"}}})
    result=PublicRiskAPIs(transport=httpx.MockTransport(fetch)).fetch(candidate())
    assert result["requests"]==2 and result["status"]=="updated"
    fields={r["field"]:r for r in result["records"]}
    assert fields["issuer_id"]["value"]=="sec:1513363"
    assert fields["country_basis"]["value"]=="issuer_domicile_proxy"
    assert "currency_exposures" not in fields and "country_currency" not in fields
    other=candidate();other["stock_market"]="NYSE"
    assert PublicRiskAPIs(transport=httpx.MockTransport(fetch)).fetch(other)["records"]==[]


def test_treasury_rejects_future_issues_and_never_turns_auction_yield_into_current_yield():
    item={**candidate("912797QJ9"),"asset_class":"BOND"}
    today=date.today()
    raw={"cusip":"912797QJ9","issueDate":today.isoformat(),"maturityDate":(today+timedelta(days=90)).isoformat(),
        "securityType":"Bill","floatingRate":"No","inflationProtected":"No","highYield":"4.5"}
    result=PublicRiskAPIs(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=[raw]))).fetch(item)
    fields={r["field"]:r["value"] for r in result["records"]}
    assert fields["zero_coupon_confirmed"] is True and fields["instrument_kind"]=="sovereign_bond"
    assert "continuous_yield" not in fields and "current_spread_bps" not in fields
    raw["inflationProtected"]="Yes"
    fields={r["field"] for r in PublicRiskAPIs(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=[raw]))).fetch(item)["records"]}
    assert "plain_nominal_noncallable" not in fields
    assert "unsupported_bond" in fields
    raw["issueDate"]=(today+timedelta(days=1)).isoformat()
    assert not PublicRiskAPIs(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=[raw]))).fetch(item)["records"]


def test_source_allocations_need_actual_recent_observation_not_fetch_time(environment):
    _,inventory,inputs=environment
    source={"url":"https://www.sec.gov/Archives/edgar/data/1513363/report.htm","retrieved_at":"2026-11-14T10:00:00Z",
        "text":"Fidus Investment Corp. All our investments are denominated in U.S. dollars. All our investments are located in the United States."}
    bound={**inventory[0],"researched_issuer_id":"sec:1513363","source_evidence":[{"field":"filing_sources","value":[{"url":source["url"]}]}]}
    records=extract_risk_records(source,bound)
    inputs.publish_evidence(inventory[0],records)
    assert inputs.read(inventory[0])["currency_exposures"] is None
    assert inputs.read(inventory[0])["country"].get("country_code") is None
    for delta,active in ((0,True),(551,False),(-1,False)):
        dated={**source,"observation_date":(date.today()-timedelta(days=delta)).isoformat()}
        fresh_store=LocalPortfolioStore(inputs._store().path.parent/f"dated{delta}.sqlite3")
        fresh=StressRiskInputs(store=lambda:fresh_store,inventory=lambda:inventory,credit=lambda _: {},sovereign=lambda _: {},countries=lambda _: {})
        fresh.publish_evidence(inventory[0],extract_risk_records(dated,bound))
        assert bool(fresh.read(inventory[0])["currency_exposures"]) is active


@pytest.mark.parametrize("statement", [
    "Not all our investments are denominated in U.S. dollars.",
    "It is not true that all our investments are denominated in U.S. dollars.",
    "All our investments are denominated in U.S. dollars except our Canadian loan.",
    "Previously, all our investments were denominated in U.S. dollars, but we now have foreign currency investments.",
    "If all our investments are denominated in U.S. dollars, the calculation would be simpler.",
    "We expect that all our investments are denominated in U.S. dollars.",
    "All our investments were denominated in U.S. dollars until 2023.",
    "As of December 31, 2025, all our investments are denominated in U.S. dollars.",
    "As of December 31, 2025. All our investments are denominated in U.S. dollars.",
    "All our investments are denominated in U.S. dollars. This is no longer true.",
    "All our investments are denominated in U.S. dollars. Not all our investments are denominated in U.S. dollars.",
    "All our investments are denominated in U.S. dollars. All our investments are denominated in euros.",
    "Not all our investments are located in the United States.",
    "All our investments are located in the United States except one German borrower.",
    "All our investments are located in the United States. However, one is in Germany.",
    'Other Corporation stated: "All our investments are denominated in U.S. dollars."',
])
def test_qualified_historical_or_retracted_source_claim_does_not_create_full_allocation(statement):
    source = {"url":"https://issuer.example/report", "retrieved_at":"2026-11-14T10:00:00Z",
              "observation_date":"2026-09-30", "text":"Example Corporation. " + statement}
    candidate = {"symbol":"EXAMPLE", "name":"Example Corporation", "verified_issuer_domains":["issuer.example"]}
    records = extract_risk_records(source, candidate)
    assert not {row["field"] for row in records} & {"currency_exposures", "country_code", "country_basis", "country_currency"}


@pytest.mark.parametrize("date_prefix,verb", [("", "are"), ("As of 2026-09-30, ", "were"),
    ("As of September 30, 2026. ", "were")])
def test_current_unqualified_source_assertions_keep_exact_observation_date(date_prefix, verb):
    source = {"url":"https://issuer.example/report", "retrieved_at":"2026-11-14T10:00:00Z",
              "observation_date":"2026-09-30", "text":f"Example Corporation. {date_prefix}All our investments {verb} denominated in U.S. dollars."}
    candidate = {"symbol":"EXAMPLE", "name":"Example Corporation", "verified_issuer_domains":["issuer.example"]}
    records = extract_risk_records(source, candidate)
    allocation = next(row for row in records if row["field"] == "currency_exposures")
    assert allocation["value"] == {"USD":1}
    assert allocation["as_of"] == "2026-09-30"


def test_static_manual_edit_does_not_refresh_inherited_market_observation(environment):
    store,inventory,inputs=environment
    today=date.today().isoformat();old=(date.today()-timedelta(days=30)).isoformat()
    before=store.change_token()
    inputs.publish_evidence(inventory[0],[record("current_spread_bps",100,old),record("continuous_yield",.04,old)])
    assert store.change_token()==before
    raw=inputs.read(inventory[0])
    inputs.update({"security_key":raw["security_key"],"expected_identity":raw["identity_token"],"expected_revision":0,
        "parameters":{"notes":"Static terms only","as_of":today}}, {"id":"writer"})
    assert inputs.read(inventory[0])["parameters"]["as_of"]==old
    with pytest.raises(HTTPException):
        inputs.publish_evidence(inventory[0],[record("issuer_id","sec:1513363")],expected_revision=0)


def test_main_publication_notifies_risk_revision_without_evicting_market_cache(environment,monkeypatch):
    from app import main
    store,inventory,_=environment
    inputs=main.stress_risk_inputs
    for field,value in (("_store",lambda:store),("_inventory",lambda:inventory),("_credit",lambda _: {}),
                        ("_sovereign",lambda _: {}),("_countries",lambda _: {})):
        monkeypatch.setattr(inputs,field,value)
    notified=[]
    monkeypatch.setattr(main._portfolio_notifications,"notify",lambda:notified.append(True))
    monkeypatch.setattr(main,"clear_portfolio_cache",lambda:pytest.fail("Risk evidence must not evict market quotes"))
    monkeypatch.setattr(main.risk_evidence_research,"api_sources",SimpleNamespace(fetch=lambda _:{
        "records":[record("issuer_id","sec:1513363")],"sources":[],"requests":1,"status":"updated","code":"data_found"}))
    before_value,before_risk=store.change_token(),inputs.revision()
    main.risk_evidence_research.public_api(main.risk_evidence_research.candidates()["items"][0])
    assert notified==[True]
    assert store.change_token()==before_value and inputs.revision()!=before_risk


def test_public_domicile_proxy_retains_explicit_country_association(environment,monkeypatch):
    _,inventory,inputs=environment
    inputs.publish_evidence(inventory[0],[record("country_code","US",basis="issuer_domicile_proxy"),
        record("country_basis","issuer_domicile_proxy",basis="issuer_domicile_proxy")])
    monkeypatch.setattr(inputs,"_countries",lambda _: {"country_code":"IL","source_kind":"manual"})
    assert inputs.read(inventory[0])["country"]["country_code"]=="IL"
    assert inputs.evidence(inventory[0])["fields"]["country_code"]["value"]=="US"


def test_sec_other_issuer_mention_and_unbound_filing_cannot_supply_risk_claims():
    item={**candidate(),"researched_issuer_id":"sec:1513363","source_evidence":[{"field":"filing_sources","value":[{"url":"https://www.sec.gov/Archives/edgar/data/1513363/owned.htm"}]}]}
    source={"url":"https://www.sec.gov/Archives/edgar/data/999999/other.htm","retrieved_at":"2026-11-14T10:00:00Z",
        "text":"OTHER INVESTMENT CORPORATION. Fidus Investment Corp is a competitor. All our investments are denominated in U.S. dollars."}
    assert extract_risk_records(source,item)==[]
    source["url"]="https://www.sec.gov/Archives/edgar/data/1513363/not-in-manifest.htm"
    assert extract_risk_records(source,item)==[]


class Deferred:
    callbacks=[]
    def __init__(self,target,**_):
        self.callbacks.append(target)
    def start(self):
        pass


def queue(environment,*,api=None):
    _,inventory,inputs=environment
    app=FastAPI();authorized=[True]
    @app.middleware("http")
    async def auth(request,call_next):
        if authorized[0]:
            request.state.auth_user={"id":request.headers.get("owner","owner"),"role":request.headers.get("role","Operator")}
        return await call_next(request)
    class Child:
        def __init__(self):self.app=app;self.calls=[]
        def start(self,owner,headers,language,**selection):
            self.calls.append((owner,headers,language,selection))
            return {"request_id":"child","status":"completed","counts":{"model_requests":8,"rest_requests":8,"web_requests":8},"outcomes":[]}
    child=Child()
    evidence=RiskEvidenceResearch(inputs,lambda:{},api_sources=api or SimpleNamespace(fetch=lambda _:{"records":[],"sources":[],"requests":1,"status":"unavailable","code":"provider_unavailable"}))
    retrieval=RiskInputRetrieval(evidence,child,None,None,worker_factory=Deferred,poll_seconds=0)
    app.include_router(retrieval.router())
    Deferred.callbacks=[]
    return retrieval,child,app,authorized


def test_api_falls_through_to_one_shared_budget_ai_and_batches_rotate(environment):
    _,inventory,_=environment
    inventory[:]=[candidate("SEC"+str(i)) for i in range(5)]
    retrieval,child,_,_=queue(environment)
    selections=[]
    for _ in range(2):
        job=retrieval.start("owner",{},"en")
        Deferred.callbacks.pop(0)()
        result=retrieval.get(job["request_id"],"owner")
        selections.append([r["symbol"] for r in result["outcomes"]])
        assert result["coverage"]["selected"]==3 and result["coverage"]["remaining"]==2
        assert result["counts"]=={"api_requests":3,"model_requests":8,"rest_requests":8,"web_requests":8}
    assert selections==[["SEC0","SEC1","SEC2"],["SEC3","SEC4","SEC0"]]
    assert len(child.calls)==2 and all(len(c[3]["security_keys"])==3 for c in child.calls)


def test_api_evidence_stays_private_and_three_target_ai_prompt_fits_existing_limit(environment,monkeypatch):
    _,inventory,inputs=environment
    inventory[:]=[candidate("SEC"+str(i)) for i in range(3)]
    for item in inventory:
        rows=[record("issuer_id","sec:1513363"),record("issuer_name","Fidus Investment Corp"),record("country_code","US"),record("country_basis","issuer_domicile_proxy")]
        for row in rows:
            row["evidence_quote"]="Actual original source context retained. "*200
        inputs.publish_evidence(item,rows)
    retrieval,_,app,_=queue(environment)
    captured=[]
    def ask(self,prompt,*args,**kwargs):
        captured.append(prompt)
        assert len(prompt)<=8000
        return {"answer":'{"records":[]}'}
    monkeypatch.setattr("app.security_enrichment.PortfolioAssistant.ask",ask)
    manager=retrieval.evidence.manager(app,lambda:{"max_tool_loops":8,"max_rest_calls":8,"max_web_calls":8})
    app.include_router(manager.router())
    retrieval.ai_jobs=manager
    job=retrieval.start("owner",{},"en",mode="ai")
    Deferred.callbacks.pop(0)()
    assert retrieval.get(job["request_id"],"owner")["status"]=="completed"
    assert len(captured)==1 and "Actual original source context retained" not in captured[0]
    assert len(inputs.evidence(inventory[0])["fields"]["issuer_id"]["evidence_quote"])>6000


def test_owner_revocation_prevents_api_publication_and_viewer_cannot_start(environment):
    retrieval,_,app,authorized=queue(environment)
    def source(_):
        authorized[0]=False
        return {"records":[record("issuer_id","sec:1513363")],"sources":[],"requests":1,"status":"updated","code":"data_found"}
    retrieval.evidence.api_sources=SimpleNamespace(fetch=source)
    job=retrieval.start("owner",{},"en",mode="api")
    Deferred.callbacks.pop(0)()
    assert retrieval.get(job["request_id"],"owner")["code"]=="owner_not_authorized"
    assert retrieval.evidence.inputs.evidence(candidate())=={}
    authorized[0]=True
    with TestClient(app) as client:
        assert client.post(PREFIX,json={},headers={"role":"Viewer"}).status_code==403
        assert client.get(PREFIX+"/"+job["request_id"],headers={"owner":"other"}).status_code==404


def test_scheduled_credentials_close_when_inventory_capture_fails(environment,monkeypatch):
    retrieval,_,_,_=queue(environment)
    revoked=[]
    def failed(**_):raise ValueError("Unavailable source inventory")
    monkeypatch.setattr(retrieval.evidence,"candidates",failed)
    with pytest.raises(ValueError):
        retrieval.start("owner",{},"en",scheduled_credentials=lambda: ({},lambda:revoked.append(True)))
    assert revoked==[True]


def test_missing_fields_matches_coupon_and_corporate_current_requirements():
    item={**candidate(),"asset_class":"BOND"}
    risk={"parameters":{"instrument_kind":"corporate_bond","pricing_model":"cashflows_continuous","as_of":"2000-01-01"}}
    assert {"bond_yield","country_sensitivity","parameters_stale"}<=set(missing_fields(risk,item))


def test_schedule_bounds_rotation_and_revoked_owner_are_visible():
    saved={}
    auth=SimpleNamespace(scheduled_session=lambda _: (_ for _ in ()).throw(PermissionError()),logout=lambda _:None)
    retrieval=SimpleNamespace(start=lambda *a,**kw: kw["scheduled_credentials"]())
    schedules=RiskInputRetrievalSchedules(lambda:deepcopy(saved),lambda value:saved.update(value),lambda:None,auth,retrieval)
    settings=schedules.update({"id":"owner","role":"Operator"},{"enabled":True})
    assert settings["schedule_config"]["frequency"]=="weekly"
    schedules.run()
    assert schedules.status()["last_run_code"]=="owner_not_authorized"
    for payload in ({"schedule_config":{"frequency":"minutely","interval":1}},{"security_keys":["a","b","c","d"]}):
        with pytest.raises(HTTPException):
            schedules.update({"id":"owner","role":"Operator"},payload)
