"""Independent ISO reference oracles; synthetic fixtures are not live AI proof.

Country/currency rows below reproduce the official SIX list fetched by QA on
16/11/2026 (Pblshd=2026-09-17). In particular, IsFund belongs to CcyNm.
All persistence uses pytest's temporary directory; no runtime portfolio is read.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from app.country_currency_reference import (
    CountryCurrencyReference, SIX_CURRENCY_URL, currency_reference_records,
)
from app.local_portfolio import LocalPortfolioStore
from app.risk_input_retrieval import RiskEvidenceResearch
from app.risk_input_sources import extract_risk_records
from app.security_research_tools import ResearchSession, WebRequestBudget
from app.stress_risk_inputs import StressRiskInputs


PUBLISHED = "2026-09-17"
US = """<CcyNtry><CtryNm>UNITED STATES OF AMERICA (THE)</CtryNm><CcyNm>US Dollar</CcyNm><Ccy>USD</Ccy><CcyNbr>840</CcyNbr><CcyMnrUnts>2</CcyMnrUnts></CcyNtry>"""
US_FUND = """<CcyNtry><CtryNm>UNITED STATES OF AMERICA (THE)</CtryNm><CcyNm IsFund="true">US Dollar (Next day)</CcyNm><Ccy>USN</Ccy><CcyNbr>997</CcyNbr><CcyMnrUnts>2</CcyMnrUnts></CcyNtry>"""
ISRAEL = """<CcyNtry><CtryNm>ISRAEL</CtryNm><CcyNm>New Israeli Sheqel</CcyNm><Ccy>ILS</Ccy><CcyNbr>376</CcyNbr><CcyMnrUnts>2</CcyMnrUnts></CcyNtry>"""
PANAMA = """<CcyNtry><CtryNm>PANAMA</CtryNm><CcyNm>Balboa</CcyNm><Ccy>PAB</Ccy><CcyNbr>590</CcyNbr><CcyMnrUnts>2</CcyMnrUnts></CcyNtry>
<CcyNtry><CtryNm>PANAMA</CtryNm><CcyNm>US Dollar</CcyNm><Ccy>USD</Ccy><CcyNbr>840</CcyNbr><CcyMnrUnts>2</CcyMnrUnts></CcyNtry>"""
PALESTINE = """<CcyNtry><CtryNm>PALESTINE, STATE OF</CtryNm><CcyNm>No universal currency</CcyNm></CcyNtry>"""


def document(rows=None, published=PUBLISHED):
    return f'<ISO_4217 Pblshd="{published}"><CcyTbl>\n{rows or US + US_FUND + ISRAEL + PANAMA + PALESTINE}\n</CcyTbl></ISO_4217>'


def source(text=None, **changes):
    return {"url": SIX_CURRENCY_URL, "text": text or document(),
        "retrieved_at": datetime.now(timezone.utc).isoformat(), **changes}


def reference(country="US", **changes):
    return currency_reference_records(source(), {"country_code": country, **changes})


def public_dns(*_args, **_kwargs):
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


@pytest.fixture
def state(tmp_path):
    store = LocalPortfolioStore(tmp_path / "country-reference-qa.sqlite3")
    item = {"security_key": "QA|NASDAQ|USD", "symbol": "QA", "stock_market": "NASDAQ",
        "currency": "USD", "asset_class": "EQUITY", "name": "QA Issuer",
        "has_open_position": True, "issuer_name": "QA Issuer", "issuer_identity_verified": True}
    association = {"country_code": "US", "source_kind": "manual"}
    inputs = StressRiskInputs(store=lambda: store, inventory=lambda: [item],
        credit=lambda _: {}, sovereign=lambda _: {}, countries=lambda _: deepcopy(association))
    return inputs, item, association


def test_actual_us_row_is_ordinary_usd_and_name_element_fund_is_excluded():
    evidence = source()
    records = currency_reference_records(evidence, {"country_code": "US"})
    assert len(records) == 1
    record = records[0]
    assert {key: record[key] for key in ("field", "value", "country_code", "units", "basis")} == {
        "field": "country_currency", "value": "USD", "country_code": "US",
        "units": "iso4217_currency_code", "basis": "iso4217_country_reference"}
    assert record["reference_currency_number"] == "840"
    assert record["reference_is_fund"] is False
    assert record["evidence_quote"] == US
    assert record["as_of"] == record["reference_published_at"] == PUBLISHED
    assert "USN" not in record["evidence_quote"]
    assert extract_risk_records(evidence, {"country_code": "US"}) == records


@pytest.mark.parametrize("country", ["PA", "PS", "ZZ", None, ""])
def test_multicurrency_universal_currency_gap_or_unknown_country_has_no_default(country):
    assert reference(country) == []


def test_currency_reference_does_not_infer_country_from_listing_or_quote_currency():
    assert currency_reference_records(source(), {"stock_market": "NASDAQ", "currency": "USD"}) == []
    assert reference("IL")[0]["value"] == "ILS"
    assert {record["field"] for record in reference()} == {"country_currency"}


@pytest.mark.parametrize("bad", [
    US.replace("<CcyNbr>840</CcyNbr>", "<CcyNbr>84</CcyNbr>"),
    US.replace("<Ccy>USD</Ccy>", "<Ccy>usd</Ccy>"),
    US.replace("<CcyNm>", '<CcyNm IsFund="unknown">'),
    US.replace("</CcyNtry>", "<Unknown>USD</Unknown></CcyNtry>"),
])
def test_matching_malformed_ordinary_row_prevents_a_partial_reference(bad):
    assert currency_reference_records(source(document(bad + US_FUND)), {"country_code": "US"}) == []


@pytest.mark.parametrize("changes", [
    {"url": "https://issuer.example/iso4217-copy.xml"},
    {"retrieved_at": "2026-11-01T12:00:00"},
    {"retrieved_at": "2099-01-01T00:00:00Z"},
    {"text": document(published="2099-01-01")},
    {"text": '<!DOCTYPE ISO_4217 [<!ENTITY unsafe "USD">]>' + document()},
])
def test_untrusted_source_invalid_dates_or_dtd_are_not_evidence(changes):
    assert currency_reference_records(source(**changes), {"country_code": "US"}) == []


def test_reference_never_uses_publication_after_requested_historical_cutoff():
    assert reference(as_of_date="2026-09-16") == []
    assert reference(as_of_date=PUBLISHED)[0]["value"] == "USD"
    assert reference(captured_at="2026-09-16T23:59:59Z") == []


def test_reference_cache_fallback_keeps_original_publication_and_retrieval_time():
    now, calls, fail = [0], [], [False]
    def fetch(request):
        calls.append(request)
        assert str(request.url) == SIX_CURRENCY_URL
        assert "authorization" not in request.headers and "api_key" not in str(request.url)
        if fail[0]:
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(200, text=document())
    reader = CountryCurrencyReference(transport=httpx.MockTransport(fetch), clock=lambda: now[0], refresh_seconds=10)
    original = reader.fetch_document(SIX_CURRENCY_URL, {})
    cached = reader.fetch_document(SIX_CURRENCY_URL, {})
    fail[0], now[0] = True, 11
    fallback = reader.fetch_document(SIX_CURRENCY_URL, {})
    assert [item["reference_cache_status"] for item in (original, cached, fallback)] == [
        "fresh", "cached", "refresh_failed_using_saved"]
    assert len(calls) == 2
    assert len({item["retrieved_at"] for item in (original, cached, fallback)}) == 1
    assert {item["reference_published_at"] for item in (original, cached, fallback)} == {PUBLISHED}
    assert currency_reference_records(fallback, {"country_code": "US"})[0]["as_of"] == PUBLISHED
    cached["text"] = "mutated by caller"
    now[0] = 0
    assert reader.fetch_document(SIX_CURRENCY_URL, {})["text"] == original["text"]


def test_failed_initial_reference_fetch_stays_unavailable():
    reader = CountryCurrencyReference(transport=httpx.MockTransport(lambda _r: httpx.Response(503)))
    with pytest.raises(ValueError, match="currency_reference_unavailable"):
        reader.fetch_document(SIX_CURRENCY_URL, {})


def test_saved_reference_only_fills_currency_shock_axis_and_never_refreshes_market_date(state, monkeypatch):
    inputs, item, _association = state
    old = (date.today() - timedelta(days=30)).isoformat()
    market = [{"field": field, "value": value, "as_of": old, "basis": "reported",
        "source_kind": "issuer_ir", "source_url": "https://issuer.example/terms", "units": units}
        for field, value, units in (("continuous_yield", .04, "annual_continuous_decimal"),
                                   ("current_spread_bps", 100, "basis_points"))]
    inputs.publish_evidence(item, market)
    inputs.publish_evidence(item, reference())
    monkeypatch.setattr(httpx, "Client", lambda **_k: pytest.fail("Risk reads must be cache only"))
    current = inputs.read(item)
    assert current["parameters"]["country_currency"] == "USD"
    assert current["parameters"]["as_of"] == old
    assert current["currency_exposures"] is None and current["country_exposures"] is None
    assert current["country"]["basis"] == "issuer_domicile_proxy"


def test_saved_reference_is_invalidated_when_country_changes_but_explicit_override_survives(state):
    inputs, item, association = state
    inputs.publish_evidence(item, reference())
    assert inputs.read(item)["parameters"]["country_currency"] == "USD"
    association["country_code"] = "IL"
    changed = inputs.read(item)
    assert "country_currency" not in changed["parameters"]
    # The original evidence stays auditable while excluded from current inputs.
    assert inputs.evidence(item)["fields"]["country_currency"]["country_code"] == "US"
    inputs.update({"security_key": item["security_key"], "expected_identity": changed["identity_token"],
        "expected_revision": changed["revision"], "parameters": {"country_currency": "ILS", "as_of": date.today().isoformat(),
        "notes": "Explicit QA currency override"}}, {"id": "qa"})
    association["country_code"] = "US"
    assert inputs.read(item)["parameters"]["country_currency"] == "ILS"


def test_saved_current_reference_cannot_enter_historical_risk_inputs(state):
    inputs, item, _association = state
    inputs.publish_evidence(item, reference())
    assert "country_currency" not in inputs.read(item, as_of="2026-09-16")["parameters"]
    assert inputs.read(item, as_of=PUBLISHED)["parameters"]["country_currency"] == "USD"


def test_model_must_read_country_row_before_selecting_it_and_finalizer_rechecks_association(state):
    inputs, item, association = state
    researcher = RiskEvidenceResearch(inputs, lambda: {})
    candidate = {**researcher.candidates()["items"][0], "_request_id": "qa-reference-request"}
    # Keep the official US row beyond the first source window, as in the real list.
    xml = document(("\n" * 45000) + US + US_FUND)
    session = ResearchSession({}, WebRequestBudget(8), resolver=public_dns,
        fetch=lambda url, _settings: source(xml))
    researcher._sessions[candidate["_request_id"]] = session
    discovered = researcher.research_tool(candidate, "discover", {})
    lead = next(row for row in discovered["sources"] if row["url"] == SIX_CURRENCY_URL)
    opening = researcher.research_tool(candidate, "read", {"source_id": lead["source_id"]})["evidence"][0]
    assert opening["context_records"] == []
    window = researcher.research_tool(candidate, "read", {"source_id": lead["source_id"],
        "query": "UNITED STATES OF AMERICA"})["evidence"][0]
    record = window["context_records"][0]
    assert record["value"] == "USD" and US in window["text"]
    result = researcher.finalize([], "qa", candidate["_request_id"],
        proposal={"records": [{"security_key": item["security_key"], "source_id": lead["source_id"], "record_id": record["record_id"]}]},
        evidence_by_key={item["security_key"]: [opening]}, candidates={item["security_key"]: candidate})
    assert result[0]["available_fields"] == [] and inputs.evidence(item) == {}
    association["country_code"] = "IL"
    result = researcher.finalize([], "qa", candidate["_request_id"],
        proposal={"records": [{"security_key": item["security_key"], "source_id": lead["source_id"], "record_id": record["record_id"]}]},
        evidence_by_key={item["security_key"]: [window]}, candidates={item["security_key"]: candidate})
    assert result[0]["available_fields"] == [] and inputs.evidence(item) == {}
    association["country_code"] = "US"
    result = researcher.finalize([], "qa", candidate["_request_id"],
        proposal={"records": [{"security_key": item["security_key"], "source_id": lead["source_id"], "record_id": record["record_id"]}]},
        evidence_by_key={item["security_key"]: [window]}, candidates={item["security_key"]: candidate})
    assert result[0]["available_fields"] == ["country_currency"]
    assert inputs.read(item)["parameters"]["country_currency"] == "USD"
    assert session.budget.used == 2


def test_late_report_window_cannot_drop_an_immediate_retraction_beyond_its_edge(state):
    inputs, _item, _association = state
    researcher = RiskEvidenceResearch(inputs, lambda: {})
    url = "https://www.sec.gov/Archives/edgar/data/1234/qa-report.htm"
    candidate = {**researcher.candidates()["items"][0], "_request_id": "qa-edge-retraction",
        "researched_issuer_id": "sec:1234", "researched_issuer_name": "QA Issuer",
        "source_evidence": [{"field": "filing_sources", "value": [{"url": url,
            "as_of": "2026-09-30", "published_at": "2026-11-01"}]}]}
    prefix = "QA Issuer report background.\n" * 3000
    claim = "All our investments are denominated in U.S. dollars."
    text = prefix + claim + " However, not all our investments are denominated in U.S. dollars."
    # Place the complete apparently affirmative sentence at the exact window
    # edge, with its immediately following qualification outside the model view.
    offset = len(prefix) + len(claim) + 1 - 40000
    session = ResearchSession({}, WebRequestBudget(8), resolver=public_dns,
        fetch=lambda fetched, _settings: {"url": fetched, "text": text})
    researcher._sessions[candidate["_request_id"]] = session
    source_id = session._add(candidate["security_key"], url, "QA annual report")
    page = researcher.research_tool(candidate, "read", {"source_id": source_id, "offset": offset})["evidence"][0]
    assert claim in page["text"] and "However" not in page["text"]
    # This demonstrates why validating just the window would be incorrect.
    isolated = researcher._dated_source(page, candidate)
    assert any(row["field"] == "currency_exposures" for row in extract_risk_records(isolated, candidate))
    assert not any(row["field"] == "currency_exposures" for row in page["context_records"])
    full = researcher._validation_source(page, candidate)
    assert "However, not all" in full["text"]
    assert not any(row["field"] == "currency_exposures" for row in extract_risk_records(full, candidate))
