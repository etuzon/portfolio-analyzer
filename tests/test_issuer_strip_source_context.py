"""Distilled issuer-document contract: a component's issuer is independent of price."""
from copy import deepcopy

import pytest

from app.security_identifiers import us_isin_discovery_hint, valid_isin
from app.security_source_context import context_records
from app.security_web_research import validate_proposals

URL = "https://s205.q4cdn.com/318912997/files/doc_downloads/irw/tva_bonds/2000-g.pdf"
KEY = "88059ESH8|MANUAL|USD"
CANDIDATE = {"security_key": KEY, "symbol": "88059ESH8", "stock_market": "MANUAL", "asset_class": "BOND",
             "currency": "USD", "missing_fields": ["profile"], "needs_name": True}
TEXT = """# U.S.$1,000,000,000 Tennessee Valley Authority 7.125% Global Power Bonds 2000 Series G Due May 1, 2030
The Bonds of the Tennessee Valley Authority (‘‘TVA’’) may be stripped.
If the Bonds are stripped into their separate Interest and Principal Components, the following Common Code, ISIN and CUSIP numbers will apply:

Common Code ISIN CUSIP

Interest Components November 1, 2026 ÏÏÏÏÏÏÏÏÏ 011365051 US88059ESH89 88059E SH8
Principal Component 011365167 US88059FBG54 88059F BG5
"""


def source(text=TEXT, url=URL):
    return {"source_id": "source-primary", "url": url, "text": text, "retrieved_at": "2026-11-08T12:00:00+00:00"}


def test_exact_component_row_binds_only_the_literal_issuer_name():
    raw = source()
    records = context_records(raw, CANDIDATE)
    assert len(records) == 1
    record = records[0]
    assert (record["kind"], record["field"], record["value"]) == ("profile", "name", "Tennessee Valley Authority")
    assert record["evidence_quote"] in TEXT
    assert record["claims"]["component_row"] in TEXT
    assert record["claims"]["issuer_definition"] in TEXT
    assert not any(field in record for field in ("coupon", "maturity_date", "price", "price_input"))
    proposal = {"records": [{"security_key": KEY, "source_id": raw["source_id"], "record_id": record["record_id"]}]}
    verified = validate_proposals(proposal, {KEY: CANDIDATE}, {KEY: [raw]})[KEY]
    assert verified["profiles"][0]["value"] == "Tennessee Valley Authority"
    assert verified["observations"] == []


@pytest.mark.parametrize("changes", [
    {"url": URL.replace("318912997", "other-issuer")},
    {"text": TEXT.replace("US88059ESH89", "US91282CKD29")},
    {"text": TEXT.replace("88059E SH8", "91282C KD2")},
    {"text": TEXT.replace("Interest Components November", "Principal Components November")},
    {"text": TEXT.replace("If the Bonds are stripped", "If other notes are stripped")},
    {"text": TEXT.split("If the Bonds are stripped")[0]},
])
def test_wrong_or_unbound_component_never_inherits_parent_terms(changes):
    raw = source()
    raw.update(changes)
    assert context_records(raw, CANDIDATE) == []


def test_other_asset_cannot_use_the_component_identity_contract():
    candidate = deepcopy(CANDIDATE)
    candidate["asset_class"] = "EQUITY"
    assert context_records(source(), candidate) == []


@pytest.mark.parametrize("cusip,expected", [("88059ESH8", "US88059ESH89"), ("121899CH9", "US121899CH98"), ("88059ESH9", None)])
def test_us_isin_search_spelling_has_a_valid_check_digit_but_is_only_a_hint(cusip, expected):
    assert us_isin_discovery_hint(cusip) == expected
    if expected:
        assert valid_isin(expected)
