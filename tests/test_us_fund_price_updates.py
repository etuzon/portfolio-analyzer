"""Raw synthetic US fund/ETF contracts; no provider or portfolio access."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json

import pytest

from app.local_portfolio import normalize_price
from app.us_fund_price_updates import us_fund_price_records


ISIN = "US8085098551"
TODAY = date.today()


def fixture(asset="MUTUALFUND", symbol="SWPPX"):
    metadata = {"symbol": symbol, "secondary_symbol": "", "stock_market": "MANUAL", "location": "USA", "asset_class": asset, "currency": "USD"}
    candidate = {**metadata, "data_source": "LOCAL", "quantity": 10}
    row = {"price_date": (TODAY - timedelta(days=1)).isoformat(), "price": 87.25, "currency": "USD",
           "quote_unit": "currency_per_share", "price_basis": "close", "adjustment_basis": "unadjusted",
           "source_url": "https://eodhd.com/api/eod/SWPPX.US", "observed_at": None, "adjusted_close": 71.5}
    snapshot = {"provider": "eodhd", "status": "partial", "cache_status": "fresh", "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "security": {"kind": "etf" if asset == "ETF" else "fund", "ticker": "SWPPX", "provider_symbol": "SWPPX.US", "isin": ISIN, "venue": "NASDAQ", "currency": "USD"},
                "items": [row], "details": {"Nav": 99.5, "nav_date_is_confirmed": False}}
    return candidate, metadata, snapshot


def records(candidate, metadata, snapshot, existing=()):
    return us_fund_price_records(candidate, metadata, snapshot, list(existing), date(2020, 1, 1))


@pytest.mark.parametrize("asset", ["ETF", "FUND", "MUTUALFUND"])
@pytest.mark.parametrize("symbol", ["SWPPX", "SWPPX.US", ISIN])
def test_raw_close_by_ticker_or_checked_isin_applies_without_dividing_by_100(asset, symbol):
    candidate, metadata, snapshot = fixture(asset, symbol)
    before = deepcopy(snapshot)
    rows = records(candidate, metadata, snapshot)
    assert len(rows) == 1 and rows[0]["price_input"] == 87.25
    assert normalize_price(rows[0]["price_input"], metadata["location"], asset) == 87.25
    assert candidate["quantity"] * rows[0]["price_input"] == 872.5
    evidence = json.loads(rows[0]["comments"])
    assert evidence["price_basis"] == "close" and evidence["adjustment_basis"] == "unadjusted"
    assert evidence["quote_unit"] == "currency_per_share" and evidence["normalization"] == "raw_price"
    assert evidence["observed_at"] is None and snapshot == before


def test_registered_local_alias_can_match_exact_secondary_ticker():
    candidate, metadata, snapshot = fixture(symbol="LOCAL_FUND")
    metadata["secondary_symbol"] = "SWPPX.US"
    assert records(candidate, metadata, snapshot)


@pytest.mark.parametrize("change", [{"data_source": "IMPORT"}, {"data_source": "MIXED"}, {"data_source": ""}])
def test_unknown_or_imported_share_contract_is_not_assumed(change):
    candidate, metadata, snapshot = fixture(); candidate.update(change)
    assert records(candidate, metadata, snapshot) == []


@pytest.mark.parametrize("change", [{"location": "Israel"}, {"location": "France"}, {"currency": "EUR"}, {"asset_class": "BOND"}, {"symbol": "OTHER"}, {"symbol": "US8085098552"}])
def test_incompatible_listing_metadata_rejects_application(change):
    candidate, metadata, snapshot = fixture(); metadata.update(change)
    assert records(candidate, metadata, snapshot) == []


@pytest.mark.parametrize("change", [{"kind": "bond"}, {"venue": "LSE"}, {"currency": "EUR"}, {"isin": "US8085098552"}, {"provider_symbol": "SWPPX.LSE"}, {"ticker": "OTHER"}])
def test_mismatched_provider_identity_kind_currency_or_market_is_rejected(change):
    candidate, metadata, snapshot = fixture(); snapshot["security"].update(change)
    assert records(candidate, metadata, snapshot) == []


def test_matching_ticker_cannot_bypass_another_explicit_share_class_isin():
    candidate, metadata, snapshot = fixture(symbol="US037833AK68")
    metadata["secondary_symbol"] = "SWPPX"
    assert records(candidate, metadata, snapshot) == []


@pytest.mark.parametrize("change", [{"provider": "other"}, {"status": "provider_error"}, {"status": "stale"}, {"cache_status": "stale"}])
def test_unavailable_stale_or_other_provider_snapshots_are_not_applied(change):
    candidate, metadata, snapshot = fixture(); snapshot.update(change)
    assert records(candidate, metadata, snapshot) == []


@pytest.mark.parametrize("change", [{"price_basis": "nav"}, {"price_basis": "redemption"}, {"price_basis": "last"}, {"adjustment_basis": "provider_adjusted"}, {"adjustment_basis": "unknown"}, {"quote_unit": "agorot"}, {"quote_unit": "unknown"}, {"currency": "EUR"}, {"price": True}, {"price": 0}, {"price": float("nan")}, {"price": 10 ** 400}])
def test_invalid_number_basis_or_unit_does_not_substitute_nav_or_adjusted_close(change):
    candidate, metadata, snapshot = fixture(); snapshot["items"][0].update(change)
    assert records(candidate, metadata, snapshot) == []


@pytest.mark.parametrize("url", ["http://eodhd.com/api/eod/SWPPX.US", "https://eodhd.com/api/eod/OTHER.US", "https://other.example/api/eod/SWPPX.US", "https://eodhd.com/api/eod/SWPPX.US?api_token=secret", "https://name:secret@eodhd.com/api/eod/SWPPX.US"])
def test_source_must_match_verified_provider_listing_without_credentials(url):
    candidate, metadata, snapshot = fixture(); snapshot["items"][0]["source_url"] = url
    assert records(candidate, metadata, snapshot) == []


@pytest.mark.parametrize("age,accepted", [(7, True), (8, False), (-1, False)])
def test_current_action_uses_actual_observation_day(age, accepted):
    candidate, metadata, snapshot = fixture(); snapshot["items"][0]["price_date"] = (TODAY - timedelta(days=age)).isoformat()
    assert bool(records(candidate, metadata, snapshot)) is accepted


def test_existing_manual_same_day_and_newer_price_are_untouched():
    candidate, metadata, snapshot = fixture()
    day = snapshot["items"][0]["price_date"]
    existing = [{"price_date": day, "price_input": 91, "source": "manual"}, {"price_date": TODAY.isoformat(), "price_input": 92}]
    assert records(candidate, metadata, snapshot, existing) == []
    assert existing[0]["price_input"] == 91
    rows = records(candidate, metadata, snapshot, existing[1:])
    assert rows[0]["price_input"] == 87.25
    assert max(existing[1:] + rows, key=lambda row: row["price_date"])["price_input"] == 92


def test_duplicate_observation_days_have_no_automatic_revision_selection():
    candidate, metadata, snapshot = fixture()
    snapshot["items"].append({**snapshot["items"][0], "price": 88})
    assert records(candidate, metadata, snapshot) == []


def test_retrieval_timestamp_cannot_predate_observation():
    candidate, metadata, snapshot = fixture()
    snapshot["retrieved_at"] = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    assert records(candidate, metadata, snapshot) == []
