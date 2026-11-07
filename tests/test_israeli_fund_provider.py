"""Synthetic official-MAYA schema fixtures; no portfolio or database access."""
from copy import deepcopy
from datetime import date, timedelta
import json

import httpx
import pytest

from app.israeli_fund_provider import MayaFundProvider
from app.us_market_providers import ProviderFailure, RequestBudget


TODAY = date.today()
DAY = TODAY - timedelta(days=2)
FUND = "5139324"


def profile():
    return {"fundId": int(FUND), "longName": "Synthetic open fund", "fundType": "קרן פתוחה", "fundTypeId": 1,
            "isin": "IL0051393242", "mutualFundSubType": 1, "isInternational": False, "deleted": False,
            "ratesAsOf": DAY.isoformat(), "redemptionPrice": 108.99, "purchasePrice": 109.01,
            "assetValueAsOf": "2026-09-30T00:00:00", "assetValueNISMillions": 4398.8,
            "features": [{"title": "יחידות הקרן נקובות ב- $", "enabled": False}]}


def history():
    return [{"fundId": "0" + FUND, "tradeDate": DAY.isoformat() + "T00:00:00", "purchasePrice": 109.01, "sellPrice": 108.99},
            {"fundId": "0" + FUND, "tradeDate": (DAY - timedelta(days=1)).isoformat(), "purchasePrice": 108.98, "sellPrice": 108.96}]


def adapter(current=None, rows=None, total="2", status=200, history_status=200):
    calls = []
    def handler(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(status, json=profile() if current is None else current)
        return httpx.Response(history_status, json=history() if rows is None else rows, headers={} if total is None else {"x-total-count": total})
    return MayaFundProvider(client=httpx.Client(transport=httpx.MockTransport(handler))), calls


def fetch(provider, **kwargs):
    return provider.fetch(FUND, TODAY - timedelta(days=10), TODAY, RequestBudget(), **kwargs)


def test_real_schema_two_read_contract_retains_price_type_date_and_source_agorot():
    provider, calls = adapter()
    result = fetch(provider)
    assert len(calls) == result["provider_requests"] == 2
    assert calls[0].url == "https://maya.tase.co.il/api/v1/funds/mutual/5139324"
    assert calls[1].method == "POST"
    assert json.loads(calls[1].content) == {"pageSize": 30, "pageNumber": 1, "fromDate": (TODAY - timedelta(days=10)).isoformat(), "toDate": TODAY.isoformat(), "period": 4}
    quote = result["quote"]
    assert quote["price"] == quote["redemption_price"] == 108.99
    assert quote["purchase_price"] == 109.01 and quote["price_basis"] == "redemption"
    assert quote["price_date"] == DAY.isoformat()  # Never asset-value or retrieval date.
    assert quote["observed_at"] is None and all(row["observed_at"] is None for row in result["items"])
    assert result["retrieved_at"]
    assert quote["quote_unit"] == "agorot" and quote["currency"] == "ILS"
    assert quote["currency_per_unit"] == pytest.approx(1.0899) and quote["normalization_supported"]
    assert result["security"]["dollar_denominated"] is False
    assert result["portfolio_updated"] is False and result["details_scope"].startswith("latest_provider")
    assert result["coverage"]["published_records_complete"] and not result["coverage"]["complete"]
    assert len(result["items"]) == 2


def test_ten_shekel_nominal_fund_quote_is_already_agorot_per_issued_unit():
    # Primary MAYA Meitav5123898 quotes1200.27; its annual report1772610
    # states nominal10ILS. The quoted number is not multiplied by nominal10.
    other = "5123898"
    current = profile(); current.update(fundId=int(other), redemptionPrice=1200.27, purchasePrice=1200.27)
    rows = [{**history()[0], "fundId": "0" + other, "sellPrice": 1200.27, "purchasePrice": 1200.27}]
    provider, _ = adapter(current=current, rows=rows, total="1")
    result = provider.fetch(other, TODAY - timedelta(days=10), TODAY, RequestBudget())
    quote = result["quote"]
    assert quote["currency"] == "ILS" and quote["currency_per_unit"] == pytest.approx(12.0027)
    assert quote["price"] == 1200.27 and quote["quote_unit"] == "agorot"
    assert quote["unit_origin"] == "maya_domestic_ils_fund_price_contract"


def test_purchase_selection_is_explicit_and_not_nav_or_close():
    provider, _ = adapter()
    result = fetch(provider, price_basis="purchase")
    assert result["quote"]["price"] == 109.01 and result["quote"]["price_basis"] == "purchase"
    assert all(row["price_basis"] == "purchase" for row in result["items"])


def test_generic_other_fund_id_has_no_price_or_name_hardcode():
    other = "5119813"
    current = profile(); current.update(fundId=int(other), isin="IL0051198138", longName="Another synthetic open fund", redemptionPrice=119.99, purchasePrice=119.99)
    rows = [{**history()[0], "fundId": "0" + other, "sellPrice": 119.99, "purchasePrice": 119.99}]
    provider, calls = adapter(current=current, rows=rows, total="1")
    result = provider.fetch(other, TODAY - timedelta(days=10), TODAY, RequestBudget())
    assert result["security"]["fund_id"] == other and result["quote"]["price"] == 119.99
    assert calls[0].url.path.endswith(other)


@pytest.mark.parametrize("change", [{"fundId": 5119813}, {"fundTypeId": 2}, {"fundTypeId": True}, {"fundType": "קרן סל"}])
def test_wrong_identity_or_type_never_requests_history(change):
    current = profile(); current.update(change)
    provider, calls = adapter(current=current)
    with pytest.raises(ProviderFailure):fetch(provider)
    assert len(calls) == 1


@pytest.mark.parametrize("change", [{"fundId": "05119813"}, {"tradeDate": "not-a-date"}, {"tradeDate": (TODAY + timedelta(days=1)).isoformat()},
                                   {"sellPrice": True}, {"sellPrice": -1}, {"sellPrice": "108.99"}])
def test_bad_history_identity_date_or_number_is_rejected(change):
    rows = history(); rows[0].update(change)
    provider, _ = adapter(rows=rows)
    with pytest.raises(ProviderFailure):fetch(provider)


def test_duplicate_daily_rows_have_no_arbitrary_revision_selection():
    rows = history(); rows[1] = deepcopy(rows[0])
    provider, _ = adapter(rows=rows)
    with pytest.raises(ProviderFailure):fetch(provider)


def test_current_history_disagreement_is_rejected():
    rows = history(); rows[0]["sellPrice"] = 90
    provider, _ = adapter(rows=rows)
    with pytest.raises(ProviderFailure):fetch(provider)


def test_current_observation_is_retained_when_nonempty_history_lags():
    provider, calls = adapter(rows=[history()[1]], total="1")
    result = fetch(provider)
    assert len(calls) == 2 and result["latest_in_range"]["price_date"] == DAY.isoformat()
    assert len(result["items"]) == 2 and result["items"][-1]["price"] == 108.99
    assert result["coverage"]["history_count"] == 1 and result["coverage"]["current_observation_added"]


@pytest.mark.parametrize("status,code", [(403, "access_denied"), (404, "not_found"), (429, "rate_limited"), (503, "unavailable")])
def test_history_outage_retains_confirmed_current_without_retry(status, code):
    provider, calls = adapter(history_status=status)
    result = fetch(provider)
    assert len(calls) == 2 and result["history_error"] == code and result["status"] == "partial"
    assert len(result["items"]) == 1 and result["latest_in_range"]["price"] == 108.99
    assert result["coverage"]["truncated"] and result["coverage"]["history_count"] == 0


def test_one_remaining_request_keeps_current_evidence_and_reports_missing_history():
    provider, calls = adapter()
    result = provider.fetch(FUND, TODAY - timedelta(days=10), TODAY, RequestBudget(limit=1))
    assert len(calls) == 1 and result["quote"]["price"] == 108.99
    assert result["history_error"] == "request_limit" and result["coverage"]["truncated"]


@pytest.mark.parametrize("total", [None, "900"])
def test_unknown_or_truncated_count_does_not_claim_full_history(total):
    provider, calls = adapter(total=total)
    result = fetch(provider)
    assert len(calls) == 2 and result["status"] == "partial"
    assert result["coverage"]["truncated"] and not result["coverage"]["published_records_complete"]


def test_explicit_historical_request_has_no_current_quote():
    provider, _ = adapter()
    result = provider.fetch(FUND, DAY - timedelta(days=10), DAY, RequestBudget())
    assert result["quote"] is None and result["latest_in_range"]["price"] == 108.99
    assert result["quote_status"] == "missing"


def test_unrelated_asset_value_date_cannot_replace_missing_rates_date():
    current = profile(); current.pop("ratesAsOf")
    provider, _ = adapter(current=current, rows=[], total="0")
    result = fetch(provider)
    assert result["quote"] is None and result["items"] == []


@pytest.mark.parametrize("field,value", [("dollar", True), ("dollar", "false"), ("isInternational", True), ("isInternational", None), ("mutualFundSubType", 2), ("mutualFundSubType", True)])
def test_nonstandard_or_unknown_denomination_keeps_raw_price_without_ils_normalization(field, value):
    current = profile()
    if field == "dollar":current["features"][0]["enabled"] = value
    else:current[field] = value
    provider, _ = adapter(current=current)
    quote = fetch(provider)["quote"]
    assert quote["price"] == 108.99 and quote["quote_unit"] == "unknown" and quote["currency"] is None
    assert "currency_per_unit" not in quote and not quote["normalization_supported"]


@pytest.mark.parametrize("identifier", ["https://example.org", "5139324/../x", "PRIVATE", "0"])
def test_identifier_validation_never_sends_untrusted_paths(identifier):
    provider, calls = adapter()
    with pytest.raises(ProviderFailure):provider.fetch(identifier, DAY, TODAY, RequestBudget())
    assert not calls


def test_provider_access_failure_consumes_only_one_attempt():
    provider, calls = adapter(status=403)
    with pytest.raises(ProviderFailure) as error:fetch(provider)
    assert error.value.code == "access_denied" and len(calls) == 1
