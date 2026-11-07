"""Raw quote evidence must retain its currency, scale and current date."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.security_web_research import validate_proposals


def validate(text, *, age=1, currency="USD", unit="currency", market="NASDAQ", asset_class="EQUITY"):
    key, url = "QA|" + market + "|" + currency, "https://exchange.example/qa"
    day = (date.today() - timedelta(days=age)).isoformat()
    text = text.format(day=day)
    candidate = {"security_key": key, "symbol": "QA", "stock_market": market,
                 "currency": currency, "quote_unit": unit, "asset_class": asset_class,
                 "location": "Israel" if market == "TASE" else "USA", "missing_fields": ["prices"]}
    observation = {"security_key": key, "price_input": 123.45, "price_date": day,
                   "currency": currency, "quote_unit": unit, "price_basis": "close",
                   "source_url": url, "observed_at": None, "evidence_quote": text}
    source = {"url": url, "text": text, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    result = validate_proposals({"observations": [observation]}, {key: candidate}, {key: [source]})[key]
    return result


@pytest.mark.parametrize("text", [
    "QA NASDAQ USD reporting. Close EUR 123.45 on {day}",
    "QA NASDAQ USD reporting. Close 123.45 EUR on {day}",
    "QA NASDAQ USD reporting. Close €123.45 on {day}",
    "QA NASDAQ USD reporting. Close cents 123.45 on {day}",
    "QA NASDAQ USD Close 123.45 on {day}. Quote currency: BRL.",
    "QA NASDAQ USD Close 123.45 on {day}. trading currency: brl.",
    "QA NASDAQ USD reporting Close 123.45 on {day} in euros",
    "QA NASDAQ USD reporting Close 123.45 on {day} in Canadian dollars",
    "QA NASDAQ USD reporting Close 123.45 on {day} in pounds sterling",
])
def test_currency_and_unit_from_another_field_cannot_override_price_label(text):
    result = validate(text)
    assert result["observations"] == [] and result["rejected"]


def test_dollar_price_cannot_be_saved_as_euros():
    result = validate("QA NASDAQ EUR reporting. Close $123.45 on {day}", currency="EUR")
    assert result["observations"] == [] and result["rejected"]


def test_us_dollar_prefix_cannot_be_saved_as_canadian_dollars():
    result = validate("QA NASDAQ CAD reporting. Close US$123.45 on {day}", currency="CAD")
    assert result["observations"] == [] and result["rejected"]


def test_ils_price_cannot_be_saved_as_agorot_from_header_label():
    result = validate("QA TASE ILS agorot reporting. Close ILS 123.45 on {day}",
                      currency="ILS", unit="agorot", market="TASE")
    assert result["observations"] == [] and result["rejected"]


@pytest.mark.parametrize("text,kwargs", [
    ("QA NASDAQ USD Close USD 123.45 on {day}", {}),
    ("QA NASDAQ USD Close 123.45 USD on {day}", {}),
    ("QA NASDAQ USD Close 123.45 on {day}", {}),
    ("QA NASDAQ US dollars Close 123.45 on {day}", {}),
    ("QA NASDAQ U.S. dollars Close 123.45 on {day}", {}),
    ("QA NASDAQ USD Close 123.45. Observed {day}", {}),
    ("QA TASE ILS Close agorot 123.45 on {day}", {"currency": "ILS", "unit": "agorot", "market": "TASE"}),
])
def test_matching_raw_currency_and_scale_remain_unchanged(text, kwargs):
    result = validate(text, **kwargs)
    assert len(result["observations"]) == 1 and not result["rejected"]
    assert result["observations"][0]["price_input"] == 123.45


def test_named_month_date_comma_preserves_its_observation_record():
    day = (date.today() - timedelta(days=1)).strftime("%B %d, %Y")
    result = validate(f"QA NASDAQ USD Close USD 123.45 on {day}")
    assert len(result["observations"]) == 1 and not result["rejected"]


@pytest.mark.parametrize("age,accepted", [(0, True), (2, True), (7, True), (8, False), (365, False), (-1, False)])
def test_current_enrichment_seven_calendar_day_boundary(age, accepted):
    result = validate("QA NASDAQ USD Close USD 123.45 on {day}", age=age)
    assert bool(result["observations"]) is accepted
    assert result["rejected"] is (not accepted)


@pytest.mark.parametrize("text", [
    "QA NASDAQ USD company profile. OTHER NASDAQ USD Close 123.45 on {day}",
    "QA NASDAQ USD company profile; OTHER NASDAQ USD Close 123.45 on {day}",
    "QA NASDAQ USD company profile OTHER NASDAQ USD Close 123.45 on {day}",
    "QA NASDAQ USD company profile | OTHER Close 123.45 on {day}",
    "QA NASDAQ USD company profile, OTHER Close 123.45 on {day}",
])
def test_another_record_cannot_borrow_identity_for_its_price(text):
    result = validate(text)
    assert result["observations"] == [] and result["rejected"]


@pytest.mark.parametrize("value", ["Tech", "Technology"])
def test_profile_value_must_preserve_whole_labeled_value(value):
    key, url = "QA|NASDAQ|USD", "https://exchange.example/qa"
    text = "QA NASDAQ Industry: Technology Services"
    candidate = {"security_key": key, "symbol": "QA", "stock_market": "NASDAQ", "missing_fields": ["profile"]}
    source = {"url": url, "text": text, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    profile = {"security_key": key, "field": "industry", "value": value, "source_url": url, "evidence_quote": text}
    result = validate_proposals({"profiles": [profile]}, {key: candidate}, {key: [source]})[key]
    assert result["profiles"] == [] and result["rejected"]


@pytest.mark.parametrize("basis", ["NAV", "Net Asset Value", "Redemption price", "Purchase price", "Auction price", "Coupon", "Yield"])
def test_fund_dealing_values_and_bond_terms_cannot_be_relabelled_close(basis):
    result = validate("QA NASDAQ USD " + basis + " Close USD 123.45 on {day}", asset_class="MUTUALFUND")
    assert result["observations"] == [] and result["rejected"]


@pytest.mark.parametrize("field,value", [("name", "Other Incorporated"), ("industry", "Software")])
def test_other_company_profile_cannot_borrow_requested_listing(field, value):
    key, url = "QA|NASDAQ|USD", "https://exchange.example/qa"
    text = "QA NASDAQ company profile. OTHER NASDAQ Company name: Other Incorporated Industry: Software"
    candidate = {"security_key": key, "symbol": "QA", "stock_market": "NASDAQ", "missing_fields": ["profile"]}
    source = {"url": url, "text": text, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    profile = {"security_key": key, "field": field, "value": value, "source_url": url, "evidence_quote": text}
    result = validate_proposals({"profiles": [profile]}, {key: candidate}, {key: [source]})[key]
    assert result["profiles"] == [] and result["rejected"]


def test_issuer_inc_suffix_does_not_separate_its_profile_fields():
    key, url = "QA|NASDAQ|USD", "https://exchange.example/qa"
    text = "QA NASDAQ Company name: QA Holdings Inc. Industry: Technology Services."
    candidate = {"security_key": key, "symbol": "QA", "stock_market": "NASDAQ", "missing_fields": ["profile"]}
    source = {"url": url, "text": text, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    profiles = [{"security_key": key, "field": field, "value": value, "source_url": url, "evidence_quote": text}
                for field, value in (("name", "QA Holdings Inc."), ("industry", "Technology Services"))]
    result = validate_proposals({"profiles": profiles}, {key: candidate}, {key: [source]})[key]
    assert len(result["profiles"]) == 2 and not result["rejected"]
