"""Routing is pure: provider failures and missing access never become AI work."""
from copy import deepcopy

import pytest

from app.security_data_routing import route_security


def security(**overrides):
    return {"symbol": "AAPL", "stock_market": "NASDAQ", "asset_class": "EQUITY", "currency": "USD", "location": "USA", "missing_fields": ["prices", "profile"], **overrides}


def bond(**overrides):
    return security(**{"symbol": "121899CH9", "stock_market": "BOND", "asset_class": "BOND", **overrides})


def test_israeli_numeric_ils_fund_is_key_free_maya_route_without_network_or_config():
    result = route_security(security(symbol="5139324", stock_market="TASE", asset_class="MUTUALFUND", location="Israel", currency="ILS"), {})
    assert result["owner"] == "api" and result["configured"] is True
    assert result["provider"] == "maya" and result["coverage"] == "candidate"
    assert result["reason"] == "api_coverage_unverified" and not result["ai_eligible"]
    assert result["fields"]["prices"]["state"] == "unverified"
    assert result["fields"]["dividends"]["state"] == "unsupported"


def test_corporate_bond_requires_finnhub_configuration_instead_of_ai():
    result = route_security(bond(), {})
    assert result["owner"] == "api" and result["provider"] == "finnhub"
    assert result["configured"] is False and result["reason"] == "configuration_required"
    assert result["coverage"] == "candidate" and not result["ai_eligible"]
    assert all(route["provider"] != "treasury_direct" for route in result["providers"])


@pytest.mark.parametrize("identifier", ["88059ESH8", "121899CH9"])
def test_agency_and_corporate_identifiers_are_discovery_candidates_not_treasury_or_verified(identifier):
    result = route_security(bond(symbol=identifier), {"security_lookup": {"finnhub": {"api_key": "synthetic"}}})
    assert result["owner"] == "api" and result["configured"] is True
    assert result["provider"] == "finnhub" and result["coverage"] == "candidate"
    assert result["fields"]["prices"]["verified"] is False


def test_treasury_prefix_is_only_a_discovery_hint_not_exact_coverage():
    result = route_security(bond(symbol="91282CJL6"), {})
    assert result["owner"] == "api" and result["provider"] == "treasury_direct"
    assert result["configured"] is True and result["coverage"] == "candidate"
    assert result["reason"] == "api_coverage_unverified"


@pytest.mark.parametrize("code", ["timeout", "rate_limited", "provider_error", "invalid_response", "entitlement_required"])
def test_configured_provider_failures_never_reclassify_a_listing_as_ai(code):
    config = {"security_lookup": {"finnhub": {"api_key": "synthetic-private-key"}}}
    reference = {"request": {"identifier": "121899CH9"}, "status": "provider_error", "provider_errors": [{"provider": "finnhub", "code": code}]}
    result = route_security(bond(), config, reference)
    assert result["owner"] == "api" and not result["ai_eligible"]
    assert result["reason"] == ("configuration_required" if code == "entitlement_required" else "provider_unavailable")
    assert "synthetic-private-key" not in str(result)


def test_exact_provider_not_found_without_alternative_can_enable_ai():
    reference = {"request": {"identifier": "121899CH9"}, "status": "not_found", "provider_errors": [{"provider": "finnhub", "code": "not_found"}]}
    result = route_security(bond(), {"security_lookup": {"finnhub": {"api_key": "synthetic"}}}, reference)
    assert result["owner"] == "ai" and result["ai_eligible"]
    assert result["reason"] == "api_coverage_unsupported"


def test_provider_not_found_for_another_identifier_does_not_disable_current_api_route():
    reference = {"request": {"identifier": "88059ESH8"}, "provider_errors": [{"provider": "finnhub", "code": "not_found"}]}
    result = route_security(bond(), {"security_lookup": {"finnhub": {"api_key": "synthetic"}}}, reference)
    assert result["owner"] == "api" and result["coverage"] == "candidate"


def test_generic_not_found_without_provenance_does_not_establish_unsupported():
    result = route_security(bond(), {}, {"status": "not_found"})
    assert result["owner"] == "api" and result["reason"] == "configuration_required"


def test_a_negative_provider_does_not_remove_another_applicable_api():
    reference = {"request": {"identifier": "91282CJL6"}, "provider_errors": [{"provider": "treasury_direct", "code": "not_found"}]}
    result = route_security(bond(symbol="91282CJL6"), {}, reference)
    assert result["owner"] == "api" and result["provider"] == "finnhub"
    assert result["reason"] == "configuration_required" and result["coverage"] == "candidate"


def test_exact_positive_reference_establishes_only_fields_present_even_when_stale():
    reference = {"provider": "finnhub", "status": "stale", "refresh_status": "provider_error", "security": {"cusip": "121899CH9", "name": "Example bond"}, "details": {"maturity_date": "2030-01-01"}, "items": []}
    result = route_security(bond(), {"security_lookup": {"finnhub": {"api_key": "synthetic"}}}, reference)
    assert result["owner"] == "api" and result["coverage"] == "verified"
    assert result["reason"] == "provider_unavailable"
    assert result["fields"]["reference"]["verified"] is True
    assert result["fields"]["prices"]["verified"] is False


def test_a_wrong_profile_cannot_be_verified_by_echoing_the_requested_identifier():
    reference = {"provider": "finnhub", "status": "partial", "request": {"identifier": "121899CH9"}, "security": {"cusip": "88059ESH8"}, "items": [{"price": 100}]}
    result = route_security(bond(), {"security_lookup": {"finnhub": {"api_key": "synthetic"}}}, reference)
    assert result["coverage"] == "candidate"
    assert not result["fields"]["prices"]["verified"]


def test_verified_reference_with_undated_price_does_not_claim_verified_price_field():
    reference = {"provider": "finnhub", "status": "partial", "security": {"cusip": "121899CH9"}, "items": [{"price": 100.0}]}
    config = {"security_lookup": {"finnhub": {"api_key": "synthetic"}}}
    result = route_security(bond(), config, reference)
    assert result["fields"]["reference"]["verified"]
    assert result["fields"]["prices"] == {"state": "unverified", "providers": ["finnhub"], "verified": False}
    reference["items"][0]["price_date"] = "2026-11-06"
    result = route_security(bond(), config, reference)
    assert result["fields"]["prices"]["verified"]


def test_supported_stock_route_stays_api_even_when_only_profile_is_missing():
    config = {"primary": "stooq"}
    result = route_security(security(missing_fields=["profile"]), config)
    assert result["owner"] == "api" and result["provider"] == "stooq"
    assert result["fields"]["profile"]["state"] == "unsupported"


def test_missing_key_for_selected_stock_provider_is_configuration_required_not_ai():
    result = route_security(security(), {"primary": "alpha_vantage"})
    assert result["owner"] == "api" and not result["configured"]
    assert result["reason"] == "configuration_required"


def test_disabled_known_api_requires_enablement_instead_of_spending_ai():
    result = route_security(bond(), {"security_lookup": {"finnhub": {"enabled": False, "api_key": "synthetic"}}})
    assert result["owner"] == "api" and not result["configured"]
    assert result["reason"] == "configuration_required"


def test_tase_listing_does_not_get_us_only_stooq_or_nasdaq_provider():
    result = route_security(security(symbol="1234567", stock_market="TASE", location="Israel", currency="ILS"), {"primary": "stooq", "fallback": ["nasdaq_quote", "sec_company_facts"]})
    assert result["owner"] == "ai" and not result["providers"]


def test_explicitly_enabled_yahoo_can_own_tase_equity_without_claiming_verified_data():
    result = route_security(security(symbol="1234567", stock_market="TASE", location="Israel", currency="ILS"), {"primary": "yahoo_finance", "yahoo_finance": {"enabled": True}})
    assert result["owner"] == "api" and result["provider"] == "yahoo_finance"
    assert result["coverage"] == "candidate"


def test_plain_numeric_ils_security_does_not_imply_a_maya_fund():
    result = route_security(security(symbol="5139324", stock_market="MANUAL", location="Israel", currency="ILS", asset_class="EQUITY"), {})
    assert result["owner"] == "ai" and not result["providers"]


@pytest.mark.parametrize("asset", ["FUND", "ETF"])
@pytest.mark.parametrize("configured", [False, True])
def test_us_fund_isin_without_ticker_uses_eodhd_and_never_ticker_providers(asset, configured):
    config = {"primary": "stooq", "fallback": ["alpha_vantage"], "alpha_vantage": {"api_key": "synthetic"},
              "security_lookup": {"eodhd": {"api_key": "synthetic"} if configured else {}}}
    candidate = security(symbol="US8085098551", stock_market="MANUAL", asset_class=asset)
    result = route_security(candidate, config)
    assert result["owner"] == "api" and result["provider"] == "eodhd"
    assert result["coverage"] == "candidate" and result["configured"] is configured
    assert result["reason"] == ("api_coverage_unverified" if configured else "configuration_required")
    assert [route["provider"] for route in result["providers"]] == ["eodhd"]


@pytest.mark.parametrize("snapshot_number,verified", [("5139324", True), ("5139325", False)])
def test_leading_zero_fund_number_only_matches_the_same_canonical_fund(snapshot_number, verified):
    candidate = security(symbol="05139324", stock_market="TASE", asset_class="FUND", location="Israel", currency="ILS")
    reference = {"provider": "maya", "status": "partial", "request": {"identifier": "05139324"},
                 "security": {"fund_id": snapshot_number, "name": "Public fund"}}
    result = route_security(candidate, {}, reference)
    assert result["owner"] == "api" and result["provider"] == "maya"
    assert result["coverage"] == ("verified" if verified else "candidate")
    assert result["fields"]["reference"]["verified"] is verified


def test_invalid_overlong_numeric_fund_identifier_is_not_silently_stripped_into_a_route():
    candidate = security(symbol="0005139324", stock_market="TASE", asset_class="FUND", location="Israel", currency="ILS")
    result = route_security(candidate, {})
    assert result["owner"] == "ai" and not result["providers"]


@pytest.mark.parametrize("asset,market", [("PRIVATE_STOCK", "PRIVATE"), ("EMPLOYEE_STOCK_OPTION", "MANUAL"), ("CASH", "US")])
def test_nonpublic_assets_are_ineligible_for_automatic_public_research(asset, market):
    result = route_security(security(asset_class=asset, stock_market=market), {"primary": "stooq"})
    assert result["owner"] == "ineligible" and not result["ai_eligible"]


def test_pure_classification_preserves_inputs():
    candidate, config = security(), {"primary": "financial_modeling_prep", "financial_modeling_prep": {"api_key": "private"}}
    before = deepcopy((candidate, config))
    route_security(candidate, config)
    assert (candidate, config) == before
