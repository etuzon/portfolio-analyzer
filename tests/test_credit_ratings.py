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


def test_live_fdus_corp_name_accepts_captured_fitch_issuer_clause_and_own_outlook():
    # Literal clause from the actual 13/11/2026 ResearchSession capture, not a
    # model-generated observation. The live imported key/name differ from the
    # earlier NASDAQ fixture. Publication metadata is the agency action date.
    company = {"security_key": "FDUS|YAHOO|USD", "symbol": "FDUS", "stock_market": "YAHOO",
               "currency": "USD", "issuer_name": "FIDUS INVESTMENT Corp", "asset_class": "EQUITY"}
    text = "Fitch Ratings has affirmed Fidus Investment Corporation's (FDUS) Long-Term Issuer Default Rating (IDR) at 'BBB-'. The Rating Outlook is Stable."
    src = source(text, title="Fitch Ratings", published_at="2026-10-15",
                 url="https://www.fitchratings.com/research/corporate-finance/fitch-affirms-fidus-investment-corporation-at-bbb-outlook-stable-15-10-2026")
    record, = primary(company, src)
    normalized = normalize_observation(record, company)
    assert (normalized["agency"], normalized["rating"], normalized["outlook"], normalized["watch"]) == ("fitch", "BBB-", "stable", "unknown")
    assert normalized["entity_name"] == "FIDUS INVESTMENT Corp"
    assert normalized["scope"] == "issuer" and normalized["rating_type"] == "issuer_default"
    assert normalized["rating_date"] == normalized["observed_at"] == "2026-10-15"
    assert normalized["outlook_date"] is None and normalized["watch_date"] is None
    assert normalized["claims"]["rating_clause"] in text


@pytest.mark.parametrize("registered,published", [
    ("Example Corp.", "Example Corporation"), ("Example Corporation", "Example Corp."),
    ("Example Inc.", "Example Incorporated"), ("Example Incorporated", "Example Inc."),
    ("Example Ltd.", "Example Limited"), ("Example Limited", "Example Ltd."),
])
def test_legal_form_spellings_match_in_rating_and_forward_clauses(registered, published):
    company = {"security_key": "EXAMPLE", "issuer_name": registered, "asset_class": "EQUITY"}
    text = "13 November 2026\n\nFitch affirmed " + published + "'s Long-Term Issuer Default Rating (IDR) at 'BBB'. Its Outlook is Negative."
    src = source(text, title="Fitch Ratings " + published, url="https://www.fitchratings.com/research/example")
    record, = primary(company, src)
    assert record["rating"] == "BBB" and record["outlook"] == "negative"
    assert normalize_observation(record, company)["entity_name"] == registered


@pytest.mark.parametrize("different", [
    "Example Bank Corporation", "Example Holdings Corporation", "Example Subsidiary Corporation",
    "Example LLC", "Example plc", "Example Corporation OH",
])
def test_legal_spelling_equivalence_never_drops_entity_or_legal_form_tokens(different):
    company = {"security_key": "EXAMPLE", "issuer_name": "Example Corp.", "asset_class": "EQUITY"}
    text = "13 November 2026\n\nFitch affirmed " + different + "'s Long-Term Issuer Default Rating (IDR) at 'AA'. Its Outlook is Stable."
    src = source(text, title="Fitch Ratings " + different, url="https://www.fitchratings.com/research/example")
    assert extract_rating_records(src, company) == []


def test_article_identity_uses_visible_prose_when_share_targets_precede_named_subject():
    company = {"security_key": "BBDC|YAHOO|USD", "issuer_name": "Barings BDC, Inc.", "asset_class": "EQUITY"}
    # The actual Fitch/Jina read puts over 1,800 characters of sharing URLs
    # before the legal subject. Keep raw offsets/evidence, but do not let link
    # targets consume the bounded visible-prose identity check.
    sharing = "[](https://share.example/?url=" + "a" * 2200 + ")\n\n"
    body = "10 Jul 2026\n\nFitch affirmed Barings BDC, Inc.'s (BBDC) Long-Term Issuer Default Rating at 'BBB-\u200c'. Its Outlook is Stable."
    src = source(sharing + body, title="Fitch Affirms Barings BDC", url="https://www.fitchratings.com/research/corporate-finance/example")
    record, = primary(company, src)
    row = normalize_observation(record, company)
    assert (row["rating"], row["rating_type"], row["outlook"], row["watch"]) == ("BBB-", "issuer_default", "stable", "unknown")
    assert row["rating_date"] == row["observed_at"] == "2026-07-10"
    assert row["outlook_date"] is None
    assert record["claims"]["rating_clause"] in src["text"]
    assert row["entity_name"] == "Barings BDC, Inc."


def test_article_link_identity_and_other_entity_do_not_supply_target_rating():
    company = {"security_key": "BBDC|YAHOO|USD", "issuer_name": "Barings BDC, Inc.", "asset_class": "EQUITY"}
    sharing = "[](https://share.example/?name=Barings%20BDC%2C%20Inc.&padding=" + "a" * 2200 + ")\n\n"
    body = "10 Jul 2026\n\nFitch affirmed Barings Private Credit Corporation's Long-Term Issuer Default Rating at 'BBB'. Its Outlook is Stable."
    src = source(sharing + body, title="Fitch Ratings", url="https://www.fitchratings.com/research/corporate-finance/example")
    assert extract_rating_records(src, company) == []
    # Even an explicit link label naming BBDC cannot transfer another named
    # company's clause-bound rating.
    src["text"] = "[Barings BDC, Inc.](https://www.fitchratings.com/entity/example)\n\n" + body
    assert extract_rating_records(src, company) == []


def test_subsidiary_forward_signals_do_not_attach_to_parent_grade():
    text = "6 November 2026\n\nFitch affirmed the Long-Term Issuer Default Rating on JPMorgan Chase & Co. at 'AA-'. JPMorgan Chase Bank, N.A.'s Outlook is Negative and was placed on Rating Watch Negative."
    src = source(text, title="Fitch Ratings", url="https://www.fitchratings.com/research/banks/example")
    record, = primary(src=src)
    assert record["rating"] == "AA-"
    assert record["outlook"] == record["watch"] == "unknown"
    own = source("6 November 2026\n\nFitch affirmed the Long-Term Issuer Default Rating on JPMorgan Chase & Co. at 'AA-'. Its Outlook is Stable.", title="Fitch Ratings", url="https://www.fitchratings.com/research/banks/example")
    record, = primary(src=own)
    assert record["outlook"] == "stable"


def test_source_local_explicit_acronym_binds_edf_but_not_sovereign_or_subsidiary():
    company = {"security_key": "EDF-ISSUER-QA|MANUAL|EUR", "issuer_name": "Electricite de France", "asset_class": "EQUITY",
               "verified_issuer_domains": ["edf.fr"]}
    text = "06 Nov 2026\n\nFitch revised Electricite de France (EDF)'s Outlook to Negative and affirmed their Long-Term Issuer Default Rating (IDR) at 'BBB+'.\n\nFitch affirmed France's Long-Term Issuer Default Rating (IDR) at 'A+'."
    src = source(text, title="Fitch Revises EDF Outlook", url="https://www.edf.fr/investors/fitch-action.pdf")
    record, = primary(company, src)
    normalized = normalize_observation(record, company)
    assert normalized["rating"] == "BBB+" and normalized["outlook"] == "negative"
    assert normalized["entity_name"] == "Electricite de France"
    assert normalized["rating_date"] == normalized["outlook_date"] == "2026-11-06"
    assert normalized["claims"]["source_bound_aliases"] == ["EDF"]
    assert any("Electricite de France (EDF)" in item["evidence_quote"] and item.get("fields") == ["entity_name"]
               for item in normalized["sources"])
    assert "issuer_aliases" not in company
    for wrong in ("EDF Trading", "EDF Trading Limited"):
        assert extract_rating_records(src, {**company, "issuer_name": wrong}) == []
    for partial in ("France", "de France"):
        assert all(row["rating"] != "BBB+" for row in extract_rating_records(src, {**company, "issuer_name": partial}))


def test_explicit_possessive_acronym_definition_keeps_canonical_axis_without_blanket_alias():
    company = {"security_key": "EDF", "issuer_name": "Electricite de France", "asset_class": "EQUITY", "verified_issuer_domains": ["edf.fr"]}
    defined = source("January 14, 2026\n\nElectricite de France S.A.'s (EDF's) operations improved.\n\nS&P raised its issuer credit rating on EDF to 'BBB+'; outlook stable.",
                     title="Electricite de France Upgraded", url="https://www.edf.fr/investors/sp-action.pdf")
    record, = primary(company, defined)
    assert record["entity_name"] == "Electricite de France" and record["rating"] == "BBB+" and record["outlook"] == "stable"
    undefined = {**defined, "text": "January 14, 2026\n\nS&P raised its issuer credit rating on EDF to 'BBB+'."}
    assert extract_rating_records(undefined, company) == []
    wrong = {**defined, "text": "January 14, 2026\n\nEDF Trading Limited (EDF) improved.\n\nS&P raised its issuer credit rating on EDF to 'A'."}
    assert extract_rating_records(wrong, company) == []
    conflicting = {**defined, "text": defined["text"].replace("\n\nS&P raised", "\n\nEDF Trading Limited (EDF) is a separate entity.\n\nS&P raised")}
    assert extract_rating_records(conflicting, company) == []


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


def test_native_sp_action_header_preserves_source_date_without_dating_unchanged_outlook():
    company = {"security_key": "CRC|YAHOO|USD", "symbol": "CRC", "issuer_name": "California Resources Corp", "asset_class": "EQUITY"}
    # Native publication line retained from the accepted official CRC source.
    header = "* 21-Aug-2026 | 14:31 EDT\n\n# Research Update: California Resources Upgraded\n\n"
    body = "California Resources Corp. (CRC) operates in California.\n\nS&P raised its issuer credit rating on CRC to 'BB-' from 'B+'. The outlook is Stable."
    src = source(header + body, title="Research Update: California Resources Upgraded", url="https://www.spglobal.com/ratings/en/regulatory/article/-/view/type/HTML/id/3615977")
    record, = primary(company, src)
    row = normalize_observation(record, company)
    assert row["rating"] == "BB-" and row["entity_name"] == "California Resources Corp"
    assert row["rating_date"] == row["observed_at"] == "2026-08-21"
    assert row["outlook"] == "stable" and row["outlook_date"] is None
    assert row["watch"] == "unknown" and row["watch_date"] is None
    assert validate_observation(record, {**company, "as_of_date": "2026-08-20"}) is None
    future = {**src, "text": src["text"].replace("21-Aug-2026", "14-Nov-2026")}
    future_record, = primary(company, future)
    assert validate_observation(future_record, company) is None
    for invalid in ("31-Feb-2026", "21-Not-2026"):
        invalid_record, = primary(company, {**src, "text": src["text"].replace("21-Aug-2026", invalid)})
        assert invalid_record["rating_date"] is None and invalid_record["observed_at"] is None
    mentioned = {**src, "text": "# Research Update: California Resources Upgraded\n\n" + body
                 + "\n\nThe company scheduled an event on 21-Aug-2026.\n\n## Related research\n* 21-Aug-2026 | 14:31 EDT"}
    mentioned_record, = primary(company, mentioned)
    assert mentioned_record["rating_date"] is None and mentioned_record["observed_at"] is None


def test_native_header_date_belongs_to_owner_title_and_is_unknown_on_ambiguity():
    company = {"security_key": "CRC|YAHOO|USD", "symbol": "CRC", "issuer_name": "California Resources Corp", "asset_class": "EQUITY"}
    body = "The California-based company California Resources Corp. (CRC) operates in California.\n\nS&P raised its issuer credit rating on CRC to 'BB-'. The outlook is Stable."
    title = "Research Update: California Resources Upgraded To"
    own_headline = "# Research Update: California Resources Upgraded To 'BB-' On Improved Regulatory Environment; Outlook Stable\n\n"
    own_date = "* 21-Aug-2026 | 14:31 EDT\n\n"
    unrelated = "* 20-Aug-2026 | 09:00 EDT\n\n# Research Update: Unrelated Company Upgraded\n\n"
    src = source(unrelated + own_headline + body, title=title, url="https://www.spglobal.com/ratings/en/regulatory/article/-/view/type/HTML/id/3615977")
    record, = primary(company, src)
    assert record["rating_date"] is None and record["observed_at"] is None
    owned = {**src, "text": unrelated + own_date + own_headline + body}
    owned_record, = primary(company, owned)
    assert owned_record["rating_date"] == owned_record["observed_at"] == "2026-08-21"
    ambiguous = {**owned, "text": owned["text"] + "\n\n* 20-Aug-2026 | 09:00 EDT\n\n" + own_headline}
    ambiguous_record, = primary(company, ambiguous)
    assert ambiguous_record["rating_date"] is None and ambiguous_record["observed_at"] is None
    for insufficient in ("Research Update", "Research Update: California Resources"):
        insufficient_record, = primary(company, {**owned, "title": insufficient})
        assert insufficient_record["rating_date"] is None and insufficient_record["observed_at"] is None
    different_grade = {**owned, "title": "Research Update: California Resources Upgraded To 'AA-'",
                       "text": own_date + own_headline.replace("'BB-'", "'AA'") + body}
    different_record, = primary(company, different_grade)
    assert different_record["rating_date"] is None and different_record["observed_at"] is None


def test_rithm_owned_native_headline_and_immediate_issuer_outlook_phrase():
    company = {"security_key": "RITM|YAHOO|USD", "symbol": "RITM", "issuer_name": "Rithm Capital Corp.", "asset_class": "EQUITY"}
    body = "S&P raised its issuer credit rating on Rithm Capital Corp. to 'B+' from 'B'. The outlook on the rating is stable. We raised our issue rating on its senior unsecured notes to 'B' from 'B-'."
    src = source(body, title="S&P Rithm Capital Corp.", url="https://spratings.spglobal.com/ratings/en/regulatory/article/-/view/type/HTML/id/3633936")
    record, = primary(company, src)
    row = normalize_observation(record, company)
    assert (row["rating"], row["rating_type"], row["outlook"], row["watch"]) == ("B+", "issuer", "stable", "unknown")
    assert row["rating_date"] is row["observed_at"] is row["outlook_date"] is None
    header = "* 25-Sep-2026 | 14:49 EDT\n\n# Rithm Capital Corp. Upgraded To 'B+' From 'B' On Improved Business Diversification; Outlook Stable\n\n"
    owned = {**src, "title": "Rithm Capital Corp. Upgraded To 'B+' From 'B' On", "text": header + body}
    owned_record, = primary(company, owned)
    owned_row = normalize_observation(owned_record, company)
    assert owned_row["rating_date"] == owned_row["observed_at"] == "2026-09-25"
    assert owned_row["outlook"] == "stable" and owned_row["outlook_date"] is None
    assert validate_observation(owned_record, {**company, "as_of_date": "2026-09-24"}) is None
    unrelated = {**owned, "text": "* 24-Sep-2026 | 14:49 EDT\n\n# Another Company Upgraded To 'B+'\n\n" + body}
    unrelated_record, = primary(company, unrelated)
    assert unrelated_record["rating_date"] is None and unrelated_record["observed_at"] is None


@pytest.mark.parametrize("following", [
    "S&P raised its issuer credit rating on Another Corp. to 'BBB'. The outlook on the rating is stable.",
    "Its senior unsecured debt rating is 'B'. The outlook on the rating is stable.",
    "We assigned an issue rating on its senior unsecured notes at 'B'. The outlook on the rating is stable.",
    "Another Corp.'s outlook on the rating is stable.",
    "The outlook on the rating is not stable.",
    "Analysts say the outlook on the rating is stable.",
    "The outlook on the rating is expected to be stable.",
    "\n\nThe outlook on the rating is stable.",
    "Additional business details. " * 15 + "The outlook on the rating is stable.",
])
def test_rating_outlook_pronoun_cannot_borrow_wrong_issue_entity_or_remote_signal(following):
    company = {"security_key": "RITM|YAHOO|USD", "symbol": "RITM", "issuer_name": "Rithm Capital Corp.", "asset_class": "EQUITY"}
    text = "S&P raised its issuer credit rating on Rithm Capital Corp. to 'B+'. " + following
    src = source(text, title="S&P Rithm Capital Corp.", url="https://spratings.spglobal.com/ratings/en/regulatory/article/-/view/type/HTML/id/3633936")
    record, = primary(company, src)
    assert record["rating"] == "B+" and record["outlook"] == record["watch"] == "unknown"


def test_article_forward_opinions_ignore_unread_related_link_titles():
    company = {"security_key": "RITM|YAHOO|USD", "symbol": "RITM", "issuer_name": "Rithm Capital Corp.", "asset_class": "EQUITY"}
    body = "S&P raised its issuer credit rating on Rithm Capital Corp. to 'B+' from 'B'. The outlook on the rating is stable."
    related = "\n\n#### Related Research\n\n* [Rithm Capital Corp. Outlook Revised To Positive On Increasing Scale](https://www.spglobal.com/ratings/previous-action)"
    src = source(body + related, title="S&P Rithm Capital Corp.", url="https://spratings.spglobal.com/ratings/en/regulatory/article/-/view/type/HTML/id/3633936")
    record, = primary(company, src)
    assert record["outlook"] == "stable" and record["watch"] == "unknown"
    link_only = {**src, "text": body.split(" The outlook", 1)[0]
                 + "\n\n[Rithm Capital Corp.'s Outlook Stable and Rating Watch Negative](https://www.spglobal.com/ratings/unread-action)"}
    link_record, = primary(company, link_only)
    assert link_record["outlook"] == link_record["watch"] == "unknown"


def test_article_linked_old_grade_is_neither_current_fact_nor_pronoun_antecedent():
    company = {"security_key": "RITM|YAHOO|USD", "symbol": "RITM", "issuer_name": "Rithm Capital Corp.", "asset_class": "EQUITY"}
    header = "* 25-Sep-2026 | 14:49 EDT\n\n# Rithm Capital Corp. Upgraded To 'B+' From 'B' On Improved Business Diversification\n\n"
    body = "S&P raised its issuer credit rating on Rithm Capital Corp. to 'B+' from 'B'. The outlook on the rating is stable."
    old = "\n\n* [Rithm Capital Corp.'s issuer credit rating affirmed at 'CCC'; Outlook Positive](https://spratings.spglobal.com/ratings/old), Nov. 14, 2025"
    src = source(header + body + old, title="Rithm Capital Corp. Upgraded To 'B+' From 'B' On", url="https://spratings.spglobal.com/ratings/en/regulatory/article/-/view/type/HTML/id/3633936")
    record, = primary(company, src)
    assert record["rating"] == "B+" and record["outlook"] == "stable"
    assert record["rating_date"] == "2026-09-25"
    assert record["claims"]["rating_clause"] in src["text"]
    only_link = {**src, "text": header + "Rithm Capital Corp. is a financial services company." + old}
    assert primary(company, only_link) == []
    linked_alias = {**src, "text": header + "[Rithm Capital Corp. (RITM)](https://spratings.spglobal.com/ratings/unread)\n\nS&P raised its issuer credit rating on RITM to 'B+'."}
    assert primary(company, linked_alias) == []


def test_literal_issuer_table_anchor_grade_cells_remain_source_bound():
    text = JPM.replace("Long-term issuer rating | A1 | A | AA-", "Long-term issuer rating | [A1](https://ratings.moodys.com/issuer) | [A](https://www.spglobal.com/ratings/issuer) | [AA-](https://www.fitchratings.com/entity/issuer)")
    rows = primary(src=source(text))
    assert {row["agency"]: row["rating"] for row in rows} == {"moodys": "A1", "sp": "A", "fitch": "AA-"}


@pytest.mark.parametrize("label", [
    "Rithm Capital Corp.'s issuer credit rating affirmed at 'CCC'",
    "Rithm Capital Corp. periodic review does not announce a credit rating action",
    "Rithm Capital Corp. national scale rating formerly 'AAA'",
])
def test_linked_article_metadata_cannot_reclassify_current_observation_or_action(label):
    company = {"security_key": "RITM|YAHOO|USD", "symbol": "RITM", "issuer_name": "Rithm Capital Corp.", "asset_class": "EQUITY"}
    old_link = "\n\n[" + label + "](https://spratings.spglobal.com/ratings/old)"
    body = "25 Sep 2026\n\n# Rithm Capital Corp. Credit Profile\n\nRithm Capital Corp.'s issuer credit rating is 'B+'."
    src = source(body + old_link, title="Rithm Capital Corp. Credit Profile", url="https://spratings.spglobal.com/ratings/en/regulatory/article/-/view/type/HTML/id/3633936")
    row, = primary(company, src)
    assert row["rating"] == "B+" and row["scale"] == "global" and row["observed_at"] == "2026-09-25"
    assert row["action_type"] == "rating_observation" and row["rating_date"] is None
    action = {**src, "text": body.replace("Rithm Capital Corp.'s issuer credit rating is", "S&P raised its issuer credit rating on Rithm Capital Corp. to") + old_link}
    action_row, = primary(company, action)
    assert action_row["action_type"] == "rating_action" and action_row["rating_date"] == "2026-09-25"


@pytest.mark.parametrize("archived", [
    "[Archived note](https://www.fitchratings.com/research/fitch-affirms-rithm-at-ccc-01-01-2025)",
    "[](https://www.fitchratings.com/research/fitch-affirms-rithm-at-ccc-01-01-2025)",
    "https://www.fitchratings.com/research/fitch-affirms-rithm-at-ccc-01-01-2025",
    "[Archived note](https://www.fitchratings.com/research/(archive)/fitch-affirms-rithm-at-ccc-01-01-2025)",
])
def test_article_url_targets_and_bare_urls_cannot_supply_financial_action(archived):
    company = {"security_key": "RITM|YAHOO|USD", "symbol": "RITM", "issuer_name": "Rithm Capital Corp.", "asset_class": "EQUITY"}
    body = "25 Sep 2026\n\n# Rithm Capital Corp. Credit Profile\n\nRithm Capital Corp.'s issuer credit rating is 'B+'."
    src = source(body + "\n\n" + archived, title="Rithm Capital Corp. Credit Profile", url="https://spratings.spglobal.com/ratings/en/regulatory/article/-/view/type/HTML/id/3633936")
    row, = primary(company, src)
    assert row["rating"] == "B+" and row["action_type"] == "rating_observation"
    assert row["rating_date"] is None and row["observed_at"] == "2026-09-25"
    assert row["claims"]["rating_clause"] in src["text"]
    action = {**src, "text": src["text"].replace("Rithm Capital Corp.'s issuer credit rating is", "S&P raised its issuer credit rating on Rithm Capital Corp. to")}
    action_row, = primary(company, action)
    assert action_row["action_type"] == "rating_action" and action_row["rating_date"] == "2026-09-25"
    prospective_url = {**src, "text": "https://www.spglobal.com/ratings/old-could-lower-rating\n\n" + body}
    prospective_row, = primary(company, prospective_url)
    assert prospective_row["rating"] == "B+" and prospective_row["action_type"] == "rating_observation"


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
