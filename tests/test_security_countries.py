from copy import deepcopy

import pytest
from fastapi import HTTPException

from app.local_portfolio import LocalPortfolioStore
from app.security_countries import SecurityCountries
from app.sovereign_ratings import normalize_country, country_descriptor


def test_domicile_override_is_explicit_revisioned_and_does_not_change_valuation(tmp_path):
    store = LocalPortfolioStore(tmp_path / "countries.sqlite")
    row = {"security_key": "EXAMPLE|NYSE|USD", "issuer_name": "Example Corporation",
           "issuer_identity_verified": True, "issuer_country": "United Kingdom",
           "location": "USA", "currency": "USD", "has_open_position": True}
    service = SecurityCountries(store=lambda: store, inventory=lambda: [row],
        normalize_country=normalize_country, country_descriptor=country_descriptor)
    original = deepcopy(row)
    token = store.change_token()
    before = service.read(row)
    assert before["country_code"] == "GB" and before["source_kind"] == "provider_profile"
    updated = service.update(row, "IL", 0, before["identity_token"], {"id": "operator"})
    assert updated["country_code"] == "IL" and updated["source_kind"] == "manual"
    with pytest.raises(HTTPException) as error:
        service.update(row, "US", 0, before["identity_token"], {"id": "operator"})
    assert error.value.status_code == 409
    row["issuer_country"] = "Canada"
    assert service.read(row)["country_code"] == "IL"
    cleared = service.update(row, None, 1, before["identity_token"], {"id": "operator"})
    assert cleared["country_code"] == "CA" and cleared["revision"] == 2
    row["issuer_country"] = original["issuer_country"]
    assert row == original and store.change_token() == token


def test_unknown_country_never_uses_currency_or_listing_and_entity_changes_fence_edits(tmp_path):
    store = LocalPortfolioStore(tmp_path / "countries.sqlite")
    row = {"security_key": "EXAMPLE|NYSE|USD", "issuer_name": "Example Corporation",
           "location": "USA", "currency": "USD", "issuer_country": "Europe"}
    service = SecurityCountries(store=lambda: store, inventory=lambda: [row],
        normalize_country=normalize_country, country_descriptor=country_descriptor)
    old = service.read(row)
    assert old["country_code"] is None and old["source_kind"] == "unknown"
    row["issuer_name"] = "Other Company"
    with pytest.raises(HTTPException) as error:
        service.update(row, "IL", 0, old["identity_token"], {"id": "operator"})
    assert error.value.status_code == 409
