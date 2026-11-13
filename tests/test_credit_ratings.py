"""Independent source facts and adversarial identity/date/provenance cases."""
from copy import deepcopy
import json

import pytest

from app.credit_ratings import (
    extract_rating_records, is_primary_observation, normalize_agency,
    infer_rating_axis, normalize_grade, normalize_observation, normalize_outlook, normalize_watch,
    validate_observation,
)


PARENT = {"security_key": "NYSE:JPM", "symbol": "JPM", "issuer_name": "JPMorgan Chase & Co.", "asset_class": "EQUITY", "verified_issuer_domains": ["jpmorganchase.com"]}
BANK = {**PARENT, "issuer_name": "JPMorgan Chase Bank, N.A."}
JPM = """## Credit Ratings
JPMorgan Chase & Co.
 | Moody's | S&P | Fitch
Outlook | Stable | Stable | Stable
Long-term issuer rating | A1 | A | AA-
Short-term issuer rating | P-1 | A-1 | F1+
Senior Unsecured | A1 | A | AA-
JPMorgan Chase & Co. Credit Ratings

JPMorgan Chase Bank, N.A.
 | Moody's | S&P | Fitch
Outlook | Stable | Stable | Stable
Long-term issuer rating | Aa2 | AA- | AA
Short-term issuer rating | P-1 | A-1+ | F1+
Long-term domestic deposits | Aa1 | N/A | AA+
JPMorgan Chase Bank, N.A. Credit Ratings
"""


def source(text=JPM, **kwargs):
    return {"source_id": "source-jpm", "url": "https://www.jpmorganchase.com/ir/fixed-income",
            "title": "Fixed Income Information", "text": text,
            "retrieved_at": "2026-11-13T10:00:00+00:00", **kwargs}


def primary(candidate=PARENT, src=None):
    return [record for record in extract_rating_records(src or source(), candidate) if is_primary_observation(record)]


def test_literal_parent_table_three_agencies_never_inherits_bank_and_dates_remain_null():
    rows = primary()
    assert {row["agency"]: row["rating"] for row in rows} == {"moodys": "A1", "sp": "A", "fitch": "AA-"}
    assert len(rows) == 3
    for row in rows:
        normalized = normalize_observation(row, PARENT)
        assert normalized["entity_name"] == "JPMorgan Chase & Co."
        assert normalized["outlook"] == "stable"
        assert normalized["watch"] == "unknown"
        assert normalized["rating_date"] is None
        assert normalized["observed_at"] is None
        assert "_source" not in normalized
        assert row["evidence_quote"] in JPM


def test_bank_is_a_separate_legal_entity_and_deposit_is_ancillary():
    rows = primary(BANK)
    assert {row["agency"]: row["rating"] for row in rows} == {"moodys": "Aa2", "sp": "AA-", "fitch": "AA"}
    all_rows = extract_rating_records(source(), BANK)
    deposits = [row for row in all_rows if row["rating_type"] == "deposit"]
    assert deposits and all(not is_primary_observation(row) for row in deposits)
    conflicting_name = {**PARENT, "name": BANK["issuer_name"]}
    assert {row["rating"] for row in primary(conflicting_name)} == {"A1", "A", "AA-"}


def test_record_id_is_stable_and_forged_grade_date_source_and_id_are_rejected():
    record = primary()[0]
    assert record["record_id"] == primary()[0]["record_id"]
    for field, value in [("rating", "Aaa"), ("rating_date", "2026-11-13"), ("record_id", "invented"), ("source_url", "https://example.com/")]:
        changed = {**record, field: value}
        assert validate_observation(changed, PARENT) is None
    assert validate_observation(record, BANK) is None


def test_missing_outlook_is_unknown_and_explicit_nr_is_not_search_failure():
    text = JPM.split("JPMorgan Chase Bank", 1)[0].replace("Outlook | Stable | Stable | Stable\n", "").replace("Long-term issuer rating | A1 | A | AA-", "Long-term issuer rating | NR | A | AA-")
    rows = {row["agency"]: row for row in primary(src=source(text))}
    assert rows["moodys"]["status"] == "unrated" and rows["moodys"]["rating"] is None
    assert all(row["outlook"] == "unknown" for row in rows.values())
    assert extract_rating_records(source("No search results"), PARENT) == []


def test_flattened_cells_keep_literal_evidence_and_parent_identity():
    flat = JPM.replace(" | ", "\n").replace("|", "\n")
    rows = primary(src=source(flat))
    assert {row["agency"]: row["rating"] for row in rows} == {"moodys": "A1", "sp": "A", "fitch": "AA-"}
    for row in rows:
        assert row["evidence_quote"] in flat
        assert normalize_observation(row, PARENT)["rating_date"] is None


def licensed_source(**changes):
    record = {"kind": "credit_rating", "agency": "sp", "status": "rated", "rating": "A",
              "scope": "issuer", "scale": "global", "term": "long_term", "rating_type": "issuer",
              "entity_name": "JPMorgan Chase & Co.", "entity_id": "entity-1", "rating_date": "2026-06-01",
              "outlook": "stable", "watch": "unknown", "observed_at": "2026-11-13"}
    record.update(changes)
    response = {"legalName": record["entity_name"], "rating": record["rating"], "ratingDate": record["rating_date"], "outlook": record["outlook"]}
    return source(json.dumps(response), url="https://xpressapi.marketplace.spglobal.com/agencyratings/api/v1/issuer",
                  _licensed_api=True, provider="spglobal_agency_ratings", structured_data=[record])


def test_only_server_bound_licensed_api_records_can_use_structured_claims():
    src = licensed_source()
    record, = extract_rating_records(src, PARENT)
    assert normalize_observation(record, PARENT)["source_kind"] == "licensed_api"
    public = deepcopy(src)
    public.pop("_licensed_api")
    assert extract_rating_records(public, PARENT) == []
    wrong_provider = {**src, "provider": "remote_jsonld"}
    assert extract_rating_records(wrong_provider, PARENT) == []
    wrong_entity = licensed_source(entity_name="JPMorgan Chase Bank, N.A.")
    assert extract_rating_records(wrong_entity, PARENT) == []


def test_future_effective_date_rejected_not_replaced_by_fetch_date():
    src = licensed_source(rating_date="2027-01-01")
    record, = extract_rating_records(src, PARENT)
    assert validate_observation(record, PARENT) is None


def test_api_forward_fields_require_literal_support_and_unicode_json_is_decoded():
    src = licensed_source()
    src["structured_data"][0]["outlook"] = "negative"
    assert extract_rating_records(src, PARENT) == []
    edf = {"security_key": "EDF", "issuer_name": "Électricité de France SA", "asset_class": "EQUITY"}
    src = licensed_source(entity_name=edf["issuer_name"])
    record, = extract_rating_records(src, edf)
    assert normalize_observation(record, edf)["entity_name"] == edf["issuer_name"]


def test_signal_dates_and_currency_basis_preserved_and_cutoff_checked_independently():
    src = licensed_source(outlook_date="2026-06-01", currency_basis="LOCAL")
    record, = extract_rating_records(src, PARENT)
    normalized = normalize_observation(record, PARENT)
    assert normalized["outlook_date"] == "2026-06-01"
    assert normalized["currency_basis"] == "local_currency"
    src["text"] = src["text"][:-1] + ', "outlookDate":"2027-01-01"}'
    src["structured_data"][0]["outlook_date"] = "2027-01-01"
    record, = extract_rating_records(src, PARENT)
    assert validate_observation(record, PARENT) is None


def test_exact_licensed_issue_binding_accepts_informal_bond_name_only_for_bound_identifier():
    bond = {"security_key": "CUSIP:91282CKD2", "symbol": "91282CKD2", "name": "Treasury 2029", "asset_class": "BOND"}
    src = licensed_source(entity_name="United States of America", scope="issue", rating_type="issue", rating="AA+")
    assert extract_rating_records(src, bond) == []
    src["_request_binding"] = {"security_key": bond["security_key"], "scope": "issue", "identifier_type": "CUSIP9", "identifier_value": "91282CKD2"}
    record, = extract_rating_records(src, bond)
    assert normalize_observation(record, bond)["entity_name"] == "United States of America"
    src["_request_binding"]["identifier_value"] = "000000000"
    assert extract_rating_records(src, bond) == []


def test_global_and_short_term_scales_are_not_interchangeable():
    assert normalize_grade("Baa1", "Moody's") == "Baa1"
    assert normalize_grade("AA-", "Fitch") == "AA-"
    assert normalize_grade("P-1", "Moody's", term="short_term") == "P-1"
    assert normalize_grade("ilAA+", "S&P", scale="national") == "ilAA+"
    assert normalize_grade("Aaa.il", "Moody's", scale="national") == "Aaa.il"
    for grade, agency in [("P-1", "moodys"), ("AAA(tha)", "fitch"), ("Aa2", "sp"), ("NR", "sp")]:
        with pytest.raises(ValueError):
            normalize_grade(grade, agency)
    assert normalize_grade("SD", "S&P") == "SD"
    assert normalize_grade("RD", "Fitch") == "RD"


def test_forward_vocabulary_is_directional_without_probability_or_double_counting():
    assert normalize_agency("S&P Global Ratings") == "sp"
    assert normalize_outlook(None) == "unknown"
    assert normalize_outlook("Negative Outlook") == "negative"
    assert normalize_outlook("Rating Outlook Stable") == "stable"
    assert normalize_watch(None) == "unknown"
    assert normalize_watch("on review for downgrade") == "negative"
    assert normalize_watch("evolving") == "developing"
    assert normalize_watch("not on watch") == "none"
    assert normalize_watch("On review for possible downgrade") == "negative"


def test_native_type_resolves_global_axis_but_untyped_and_national_are_not_global():
    axis = infer_rating_axis("Long-Term Issuer Credit Rating", "S&P", "A")
    assert axis == {"scope": "issuer", "rating_type": "issuer", "scale": "global", "term": "long_term"}
    assert infer_rating_axis("LT Issuer Default Rating", "Fitch", "AA-")["scale"] == "global"
    assert infer_rating_axis("ST Issuer Rating", "Moody's", "P-1")["term"] == "short_term"
    assert infer_rating_axis("Rating", "Fitch", "AAA")["scale"] is None
    assert infer_rating_axis("Long-Term Issuer Rating", "S&P", "ilAAA")["scale"] == "national"
    with pytest.raises(ValueError):
        infer_rating_axis("Long-Term Issuer Rating", "Fitch", "AAA(tha)", scale="global")
    assert infer_rating_axis("Long-Term Issuer Rating", "S&P", "NR")["scale"] == "global"
    assert infer_rating_axis("Long-Term Issuer Rating", "Fitch", None, status="withdrawn")["scale"] == "global"
    assert infer_rating_axis("Rating", "Fitch", None, status="withdrawn")["scale"] is None


def test_agency_article_binds_each_rating_clause_to_its_own_legal_entity():
    text = "6 November 2026\n\nFitch has affirmed JPMorgan Chase & Co.'s Long-Term Issuer Default Rating (IDR) at 'AA-' and JPMorgan Chase Bank, N.A.'s Long-Term Issuer Default Rating (IDR) at 'AA'. The outlook is Stable."
    src = source(text, title="Fitch Affirms JPMorgan Chase & Co.", url="https://www.fitchratings.com/research/banks/example")
    assert {row["rating"] for row in primary(src=src)} == {"AA-"}
    assert {row["rating"] for row in primary(BANK, src)} == {"AA"}


def test_subsidiary_forward_signals_do_not_attach_to_parent_grade():
    text = "6 November 2026\n\nFitch affirmed the Long-Term Issuer Default Rating on JPMorgan Chase & Co. at 'AA-'. JPMorgan Chase Bank, N.A.'s Outlook is Negative and was placed on Rating Watch Negative."
    src = source(text, title="Fitch Ratings", url="https://www.fitchratings.com/research/banks/example")
    record, = primary(src=src)
    assert record["rating"] == "AA-"
    assert record["outlook"] == record["watch"] == "unknown"
    own = source("6 November 2026\n\nFitch affirmed the Long-Term Issuer Default Rating on JPMorgan Chase & Co. at 'AA-'. Its Outlook is Stable.", title="Fitch Ratings", url="https://www.fitchratings.com/research/banks/example")
    record, = primary(src=own)
    assert record["outlook"] == "stable"


def test_national_article_symbol_is_never_truncated_into_a_global_symbol():
    src = source("13 January 2026\n\nMoody's has affirmed JPMorgan Chase & Co.'s long-term issuer rating at 'Aaa.il' on the national scale. The outlook is Stable.", title="Moody's JPMorgan Chase", url="https://ratings.moodys.com/ratings-news/example")
    assert extract_rating_records(src, PARENT) == []


@pytest.mark.parametrize("symbol", ["(P)A2", "(P) A2", "A2(sf)", "A2(hyb)"])
def test_unsupported_qualifiers_are_never_stripped_or_misread_as_country_scales(symbol):
    src = source("13 January 2026\n\nMoody's has affirmed JPMorgan Chase & Co.'s " + symbol + " long-term issuer rating.", title="Moody's JPMorgan Chase", url="https://ratings.moodys.com/ratings-news/example")
    assert extract_rating_records(src, PARENT) == []
    with pytest.raises(ValueError):
        normalize_grade(symbol, "Moody's", scale="national")
    assert infer_rating_axis("Long-Term Issuer Rating", "Moody's", symbol)["scale"] is None


def test_periodic_review_and_rating_action_dates_are_distinct_without_ignoring_outlook():
    edf = {"security_key": "EDF", "issuer_name": "Electricite de France", "issuer_aliases": ["EDF"], "asset_class": "EQUITY", "verified_issuer_domains": ["edf.fr"]}
    periodic = source("13 Jan 2026\n\nMoody's periodic review: Electricite de France's Baa1 long term issuer rating, with stable outlook.", title="Moody's Periodic Review Electricite de France", url="https://www.edf.fr/investors/moodys-review.pdf")
    record, = primary(edf, periodic)
    normalized = normalize_observation(record, edf)
    assert normalized["rating"] == "Baa1" and normalized["outlook"] == "stable"
    assert normalized["observed_at"] == "2026-01-13"
    assert normalized["rating_date"] is None and normalized["outlook_date"] is None
    action = source("January 14, 2026\n\nS&P Global Ratings raised its issuer credit rating on EDF to 'BBB+'; outlook stable.", title="Electricite de France Rating Action", url="https://www.edf.fr/investors/sp-action.pdf")
    record, = primary(edf, action)
    assert normalize_observation(record, edf)["rating_date"] == "2026-01-14"


def test_outlook_revision_retains_new_signal_not_old_from_signal():
    edf = {"security_key": "EDF", "issuer_name": "Electricite de France", "asset_class": "EQUITY", "verified_issuer_domains": ["edf.fr"]}
    text = "06 Nov 2026\n\nFitch affirms Electricite de France's Long-Term Issuer Default Rating (IDR) at 'BBB+' and revised its Outlook to Negative from Stable."
    src = source(text, title="Fitch Ratings Electricite de France", url="https://www.edf.fr/investors/fitch-action.pdf")
    record, = primary(edf, src)
    normalized = normalize_observation(record, edf)
    assert normalized["outlook"] == "negative" and normalized["outlook_date"] == "2026-11-06"


def test_agency_dateline_and_joined_periodic_publication_date_keep_independent_meaning():
    edf = {"security_key": "EDF", "issuer_name": "Electricite de France", "issuer_aliases": ["EDF"], "asset_class": "EQUITY", "verified_issuer_domains": ["edf.fr"]}
    text = "Fitch Ratings - Barcelona - 06 Nov 2026: Fitch revised Electricite de France (EDF)'s Outlook to Negative and affirmed their Long-Term Issuer Default Rating (IDR) at 'BBB+'."
    src = source(text, title="Fitch revises EDF Outlook", url="https://www.edf.fr/investors/fitch.pdf")
    record, = primary(edf, src)
    normalized = normalize_observation(record, edf)
    assert normalized["observed_at"] == "2026-11-06"
    assert normalized["rating_date"] == normalized["outlook_date"] == "2026-11-06"
    periodic = source("13 Jan 2026 Paris, January 13, 2026 -- Moody's periodic review. Electricite de France's Baa1 long term issuer rating, stable outlook.", title="Moody's Periodic Review", url="https://www.edf.fr/investors/moodys.pdf")
    record, = primary(edf, periodic)
    normalized = normalize_observation(record, edf)
    assert normalized["observed_at"] == "2026-01-13"
    assert normalized["rating_date"] is None and normalized["outlook_date"] is None


def test_wrapped_legal_name_clause_is_supported_but_future_hypothetical_grade_is_not_current():
    company = {"security_key": "ABC", "issuer_name": "Example Corp.", "asset_class": "EQUITY"}
    current = source("13 November 2026\n\nS&P raised its issuer credit rating on\nExample Corp. to 'BBB+'; outlook stable.", title="S&P Example Corp.", url="https://www.spglobal.com/ratings/example")
    record, = primary(company, current)
    assert record["rating"] == "BBB+" and record["claims"]["rating_clause"] in current["text"]
    future = source("13 November 2026\n\nS&P could raise its issuer credit rating on Example Corp. to 'A'.", title="S&P Example Corp.", url="https://www.spglobal.com/ratings/example")
    assert primary(company, future) == []


def test_arbitrary_https_host_is_discovery_only_until_server_establishes_primary_authority():
    src = source(url="https://unverified.example/ratings")
    assert extract_rating_records(src, PARENT) == []
    # A remote nested assertion does not grant server authority.
    src["structured_data"] = [{"_issuer_source_verified": True}]
    assert extract_rating_records(src, PARENT) == []
    src["_issuer_source_verified"] = True
    assert len(primary(src=src)) == 3


def test_typed_agency_detail_list_excludes_operating_bank_snapshot_history_and_sovereign():
    company = {"security_key": "UBS", "issuer_name": "UBS Group AG", "asset_class": "EQUITY", "verified_issuer_domains": ["ubs.com"]}
    # Native headings match the captured report; the historical and sovereign
    # decoys test that only the exact legal-entity detail section owns a grade.
    text = """UBS Group AG
Ratings Score Snapshot
Issuer credit rating
A+/Stable/A-1
Holding company ICR
A-/Stable/A-2
Ratings Detail
UBS Group AG
Issuer Credit Rating A-/Stable/A-2
Issuer Credit Ratings History
01-Jan-2000 AAA/Negative/A-1
Sovereign Rating
Otherland AAA/Stable/A-1
Related Entities
UBS AG
Issuer Credit Rating A+/Stable/A-1
"""
    src = source(text, title="S&P Global Ratings", url="https://www.ubs.com/investors/sp-report.pdf", published_at="2026-10-19")
    row, = primary(company, src)
    assert row["rating"] == "A-" and row["outlook"] == "stable"
    assert row["rating_date"] is None and row["observed_at"] == "2026-10-19"


def test_fitch_detail_list_keeps_named_company_idr_and_separates_sovereign_rows():
    company = {"security_key": "UBS", "issuer_name": "UBS Group AG", "asset_class": "EQUITY", "verified_issuer_domains": ["ubs.com"]}
    text = """Fitch Ratings
Ratings
UBS Group AG
Long-Term IDR A+
Short-Term IDR F1
Sovereign Risk (Otherland)
Long-Term Foreign-Currency IDR AAA
Outlooks
Long-Term Foreign-Currency IDR Stable
Sovereign Long-Term Foreign-Currency IDR Negative
ESG and Climate
"""
    src = source(text, title="Fitch Ratings Report", url="https://www.ubs.com/investors/fitch-report.pdf", published_at="2026-05-06")
    row, = primary(company, src)
    assert row["rating"] == "A+" and row["outlook"] == "stable"
    assert row["rating_date"] is None


def test_company_senior_debt_fact_is_retained_without_becoming_issuer_or_issue_rating():
    company = {"security_key": "UBS", "issuer_name": "UBS Group AG", "asset_class": "EQUITY", "verified_issuer_domains": ["ubs.com"]}
    text = "3 November 2026\n\nUBS Group AG's A2 senior unsecured debt rating has a stable outlook."
    src = source(text, title="Moody's Credit Opinion", url="https://www.ubs.com/investors/moodys-report.pdf")
    record, = extract_rating_records(src, company)
    normalized = normalize_observation(record, company)
    assert normalized["rating"] == "A2" and normalized["rating_type"] == "senior_unsecured_class"
    assert normalized["primary_eligible"] is False and normalized["scope"] == "issuer"
    assert normalized["rating_date"] is None and normalized["outlook"] == "stable"


@pytest.mark.parametrize("url", ["http://example.com/", "https://user:secret@example.com/", "https://127.0.0.1/", "https://example.com/?api_key=secret"])
def test_unsafe_provenance_url_cannot_create_records(url):
    assert extract_rating_records(source(url=url), PARENT) == []
