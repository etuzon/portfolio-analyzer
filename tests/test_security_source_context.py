"""Source contracts, including raw spans from the verified official TASE page."""
import json

import pytest

from app.security_source_context import _number, context_records, context_supported, supports_context, validate_contextual_observation, validate_contextual_profile


CANDIDATE = {"symbol": "1101534", "secondary_symbol": "IL0011015349", "stock_market": "TASE",
             "asset_class": "STOCK", "currency": "ILS", "quote_unit": "agorot"}
URL = "https://market.tase.co.il/he/market_data/security/1101534/major_data"
# Literal main quote/profile spans from the official public source retrieved
# 07/11/2026; related sections below are deliberately adversarial fixtures.
TASE = """## סלקום נתונים עיקריים

*   1101534

**מניה רגילה** סימול : **סלקם**

ע''ש
*   שער אחרון (באגורות)

**2,901** שינוי

**1.86%**

 עליה
*   **בסיס:**

2,848 **פתיחה:**

2,848 **גבוה:**

2,954 **נמוך:**

2,829
נכון ל- 06/11/2026

*   שווי שוק

**4,901,673 אלפי ₪**
נכון ל- 06/11/2026

## **אודות החברה**

החברה מפעילה רשת טלפונים סלולרית.

## **ענף בבורסה**

ריאלי - מסחר ושרותים - תקשורת ומדיה

###### Chart

## ניירות קשורים

* 9999999
שער אחרון (באגורות) **7,777** נכון ל- 07/11/2026
## חדשות
Published 07/11/2026
"""


def source(text=TASE, url=URL, **kwargs):
    return {"url": url, "text": text, "retrieved_at": "2026-11-07T12:00:00+00:00", **kwargs}


def prices(src=None, candidate=CANDIDATE):
    return [record for record in context_records(src or source(), candidate) if record["kind"] == "price"]


def proposal(record):
    return {key: record[key] for key in ("source_url", "price_input", "price_date", "currency", "quote_unit", "price_basis", "observed_at", "evidence_quote")}


def test_verified_tase_raw_last_context_retains_spans_and_does_not_scale():
    record, = prices()
    assert record["price_input"] == 2901
    assert record["price_date"] == "2026-11-06"
    assert record["currency"] == "ILS"
    assert record["quote_unit"] == "agorot"
    assert record["price_basis"] == "last"
    assert record["observed_at"] is None
    assert record["date_format"] == "dd/mm/yyyy"
    assert record["evidence_quote"] == "שער אחרון (באגורות)\n\n**2,901**"
    assert all(value in TASE for value in record["claims"].values())
    assert validate_contextual_observation(source(), CANDIDATE, proposal(record)) == record


def test_tase_numeric_namespace_matches_leading_zero_without_symbol_special_case():
    assert len(prices(candidate={**CANDIDATE, "symbol": "01101534"})) == 1
    other = source(TASE.replace("1101534", "1234567"), URL.replace("1101534", "1234567"))
    record, = prices(other, {**CANDIDATE, "symbol": "1234567", "secondary_symbol": ""})
    assert record["price_input"] == 2901


@pytest.mark.parametrize("replacement", [
    {"stock_market": "NYSE"}, {"currency": "USD"}, {"quote_unit": "currency"}, {"asset_class": "BOND"},
    {"symbol": "5555555", "secondary_symbol": ""},
])
def test_tase_requires_matching_listing_instrument_currency_and_raw_unit(replacement):
    assert prices(candidate={**CANDIDATE, **replacement}) == []


@pytest.mark.parametrize("text", [
    TASE.replace("*   1101534", "*   9999999"),
    TASE.replace("מניה רגילה", "אגרת חוב"),
    TASE.replace("שער אחרון (באגורות)", "שער אחרון", 1),
    TASE.replace("שער אחרון (באגורות)", "שער אחרון (בשקלים)", 1),
    TASE.replace("**2,901** שינוי", "**2,901**% שינוי", 1),
    TASE.replace("נכון ל- 06/11/2026", "", 1),
    TASE.replace("נכון ל- 06/11/2026", "נכון ל- 31/02/2026", 1),
])
def test_tase_does_not_borrow_identity_units_or_date_from_other_sections(text):
    assert prices(source(text)) == []


def test_tase_quote_card_cannot_borrow_change_agorot_or_related_price():
    text = TASE.replace("שער אחרון (באגורות)\n\n**2,901**", "שער אחרון\n\n**2,901**\nשינוי באגורות 53", 1)
    assert prices(source(text)) == []
    text = TASE.replace("שער אחרון (באגורות)\n\n**2,901**", "לא זמין", 1)
    assert prices(source(text)) == []


@pytest.mark.parametrize("changed", [
    {"price_input": 29.01}, {"price_input": True}, {"price_date": "2026-11-07"},
    {"observed_at": "2026-11-06T13:44:00+02:00"}, {"quote_unit": "currency"},
    {"currency": "USD"}, {"price_basis": "close"}, {"source_url": "https://other.example/"},
    {"evidence_quote": "2,901"},
])
def test_contextual_observation_validates_model_fields_against_raw_record(changed):
    record, = prices()
    assert validate_contextual_observation(source(), CANDIDATE, {**proposal(record), **changed}) is None


def test_profile_values_must_match_main_security_heading_and_labelled_industry():
    profiles = [record for record in context_records(source(), CANDIDATE) if record["kind"] == "profile"]
    assert {record["field"]: record["value"] for record in profiles} == {
        "name": "סלקום", "industry": "ריאלי - מסחר ושרותים - תקשורת ומדיה"}
    for record in profiles:
        item = {key: record[key] for key in ("source_url", "field", "value", "evidence_quote")}
        assert validate_contextual_profile(source(), CANDIDATE, item) == record
        assert validate_contextual_profile(source(), CANDIDATE, {**item, "value": "invented"}) is None


def test_date_locale_contract_is_specific_to_official_hebrew_tase_namespace():
    assert prices(source(url=URL.replace("/he/", "/en/"))) == []
    assert prices(source(url=URL.replace("market.tase.co.il", "portal.example"))) == []


def test_generic_raw_json_requires_explicit_same_object_identity_market_unit_and_iso_date():
    obj = {"symbol": "EXAMPLE", "exchange": "NASDAQ", "currency": "USD", "quoteUnit": "currency", "last": 101.25, "date": "2026-11-06"}
    src = source(json.dumps(obj), "https://example.com/quote", structured_data=[obj])
    candidate = {"symbol": "EXAMPLE", "stock_market": "NASDAQ", "currency": "USD", "quote_unit": "currency"}
    record, = prices(src, candidate)
    assert record["price_input"] == 101.25
    assert record["price_basis"] == "last"
    assert record["evidence_quote"] == '"last": 101.25'
    assert validate_contextual_observation(src, candidate, proposal(record)) == record
    assert prices({**src, "text": "EXAMPLE public headline; script body not preserved"}, candidate) == []
    for change in ({"exchange": "NYSE"}, {"quoteUnit": "percent_of_par"}, {"price_basis": "nav"}, {"date": "06/11/2026"}, {"symbol": "OTHER"}, {"currency": "EUR"}):
        changed = {**obj, **change}
        assert prices(source(json.dumps(changed), "https://example.com/quote", structured_data=[changed]), candidate) == []


def test_json_adjusted_close_and_nav_do_not_become_raw_close():
    candidate = {"symbol": "EXAMPLE", "stock_market": "NASDAQ", "currency": "USD", "quote_unit": "currency"}
    for field in ("adjustedClose", "nav", "yield"):
        obj = {"symbol": "EXAMPLE", "exchange": "NASDAQ", "currency": "USD", "quoteUnit": "currency", field: 100, "date": "2026-11-06"}
        assert prices(source(json.dumps(obj), "https://example.com/quote", structured_data=[obj]), candidate) == []


def test_themarker_stock_profile_uses_explicit_structured_identity_without_price_units():
    obj = {"assetNumber": 1101534, "assetType": "stock", "assetName": "סלקום", "last": 2901}
    src = source("סלקום שער אחרון 2,901 נכון ל: 06.11.2026", "https://finance.themarker.com/stock/1101534", structured_data=[{"asset": obj}])
    record, = context_records(src, CANDIDATE)
    assert record["kind"] == "profile"
    assert record["field"] == "name"
    assert record["value"] == record["evidence_quote"] == "סלקום"
    assert record["claims"]["identity"] == {"path": '$.structured_data[0]["asset"]["assetNumber"]', "value": 1101534}
    assert prices(src) == []
    for changed in ({"assetNumber": 9999999}, {"assetType": "bond"}, {"assetName": "Different Company"}):
        assert context_records({**src, "structured_data": [{**obj, **changed}]}, CANDIDATE) == []
    assert context_records({**src, "url": src["url"].replace("finance.themarker.com", "other.example")}, CANDIDATE) == []


@pytest.mark.parametrize("prefix", ["USD ", "EUR ", "מטבע: דולר אמריקאי ", "מתואם ", "adjusted ", "Adj. Close ", "מספר נייר: 9999999 "])
def test_tase_explicit_quote_card_conflicts_reject_even_when_field_span_looks_valid(prefix):
    conflicting = TASE.replace("שער אחרון (באגורות)", prefix + "שער אחרון (באגורות)", 1)
    assert prices(source(conflicting)) == []


def test_tase_price_checks_do_not_borrow_conflicts_from_market_cap_or_company_description():
    other_sections = TASE.replace("4,901,673 אלפי ₪", "USD 4,901,673", 1).replace(
        "החברה מפעילה", "adjusted USD החברה מפעילה", 1)
    assert len(prices(source(other_sections))) == 1


def test_tase_primary_isin_must_not_contradict_known_candidate_isin():
    text = TASE.replace("###### Chart", "ISIN\n\n**IL0011015349**\n\n###### Chart", 1)
    assert len(prices(source(text))) == 1
    assert context_records(source(text), {**CANDIDATE, "secondary_symbol": "IL0011111111"}) == []
    assert context_records(source(text.replace("IL0011015349", "IL0011111111")), CANDIDATE) == []
    assert context_records(source(), {**CANDIDATE, "secondary_symbol": "IL0011111111"})
    assert context_records(source(text, isin="IL0011111111"), CANDIDATE) == []
    related = TASE.replace("## ניירות קשורים", "## ניירות קשורים\nISIN **IL0011111111**", 1)
    assert len(prices(source(related))) == 1


@pytest.mark.parametrize("conflict", [
    {"adjusted": True}, {"isAdjusted": True}, {"adjusted": "true"},
    {"adjustmentBasis": "split-adjusted"}, {"adjustment_basis": "split-adjusted"},
    {"stock_market": "NYSE"}, {"market": "NYSE"},
    {"quote_currency": "EUR"}, {"quoteCurrency": "EUR"},
    {"rawQuoteUnit": "percent_of_par"}, {"quote_unit": "cents"},
    {"price_basis": "close", "priceBasis": "last"}, {"quote_date": "2026-11-07"},
])
def test_generic_json_checks_all_convention_aliases_and_adjustment_flags(conflict):
    candidate = {"symbol": "TEST", "stock_market": "NASDAQ", "currency": "USD", "quote_unit": "currency"}
    obj = {"symbol": "TEST", "exchange": "NASDAQ", "currency": "USD", "quoteUnit": "currency", "last": 100, "date": "2026-11-06", **conflict}
    assert prices(source(json.dumps(obj), "https://example.com/quote", structured_data=[obj]), candidate) == []


def test_generic_json_matching_aliases_and_explicit_unadjusted_flag_remain_supported():
    candidate = {"symbol": "TEST", "stock_market": "NASDAQ", "currency": "USD", "quote_unit": "currency"}
    obj = {"symbol": "TEST", "exchange": "NASDAQ", "stock_market": "NASDAQ", "currency": "USD", "quote_currency": "USD",
           "quoteUnit": "currency", "rawQuoteUnit": "currency", "last": 100, "date": "2026-11-06", "adjusted": False}
    assert len(prices(source(json.dumps(obj), "https://example.com/quote", structured_data=[obj]), candidate)) == 1


def test_generic_json_known_isin_conflict_is_not_overridden_by_matching_symbol():
    candidate = {"symbol": "TEST", "secondary_symbol": "US0378331005", "stock_market": "NASDAQ", "currency": "USD", "quote_unit": "currency"}
    obj = {"symbol": "TEST", "isin": "US5949181045", "exchange": "NASDAQ", "currency": "USD", "quoteUnit": "currency", "last": 100, "date": "2026-11-06"}
    assert prices(source(json.dumps(obj), "https://example.com/quote", structured_data=[obj]), candidate) == []


def test_nonfinite_and_huge_integer_prices_are_unknown_instead_of_raising():
    assert _number(10 ** 10000) is None
    assert _number(float("inf")) is None
    assert _number("9" * 10000) is None
    assert _number(True) is None


def test_context_provider_recognition_does_not_depend_on_successful_price_parse():
    assert context_supported(source(TASE.replace("שער אחרון (באגורות)", "שער אחרון", 1)))
    assert supports_context(source(), CANDIDATE)
    assert context_supported(source(url="https://finance.themarker.com/stock/1101534"))
    assert context_supported(source("unrecognized", "https://example.com/quote", structured_data=[{"symbol": "TEST", "exchange": "NASDAQ", "currency": "USD", "last": 100}]))
    assert not context_supported(source("unrecognized", "https://example.com/quote", structured_data=[{"@type": "WebSite", "name": "Publisher"}]))
    assert not context_supported(source("plain text", "https://example.com/quote"))
    assert not context_supported(source(url="https://other.example/he/market_data/security/1101534/major_data"))
    assert not context_supported(source(url="https://[invalid"))
