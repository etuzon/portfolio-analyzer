from datetime import date, datetime, timezone
import json
import gzip

import httpx
import pytest

from app.us_market_providers import (
    EodhdFundProvider, FinnhubBondProvider, ProviderFailure, RequestBudget,
    TreasuryDirectProvider,
)


START, END = date(2026, 6, 1), date(2026, 6, 5)
ISIN, CUSIP = "US91282CKD29", "91282CKD2"


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def bond_profile(**changes):
    return {"cusip": CUSIP, "isin": ISIN, "coupon": 4.25, "maturityDate": "2029-02-28",
            "issueDate": "2024-02-29", "paymentFrequency": "Semi-Annual", "offeringPrice": 99.688225,
            "callable": False, "asset": "US Treasury Note", **changes}


def timestamp(day):
    return int(datetime.combine(day, datetime.min.time(), timezone.utc).timestamp())


def test_finnhub_resolves_cusip_then_fetches_close_history_without_assuming_units():
    seen = []
    def handle(request):
        seen.append(request)
        assert request.headers["X-Finnhub-Token"] == "synthetic-key"
        assert "token" not in request.url.params
        if request.url.path.endswith("profile"):
            assert request.url.params["cusip"] == CUSIP
            return httpx.Response(200, json=bond_profile())
        assert request.url.params["isin"] == ISIN
        assert int(request.url.params["from"]) == timestamp(START)
        return httpx.Response(200, json={"s": "ok", "c": [99.25, 99.375], "t": [timestamp(START), timestamp(END)]})
    budget = RequestBudget()
    result = FinnhubBondProvider({"api_key": "synthetic-key"}, client_for(handle)).fetch(CUSIP, "cusip", "bond", START, END, budget)
    assert len(seen) == budget.used == 2
    assert [row["price"] for row in result["items"]] == [99.25, 99.375]
    assert result["items"][0]["quote_unit"] == "unknown"
    assert result["items"][0]["currency"] is None
    assert result["items"][0]["accrual_basis"] == "unknown"
    assert result["details"]["coupon_rate_pct"] == 4.25
    assert result["details"]["payment_frequency_reported"] == "Semi-Annual"
    assert result["details"]["offering_price"] == 99.688225
    assert result["details"]["offering_price_is_current"] is False
    assert "synthetic-key" not in json.dumps(result)


def test_finnhub_accepts_other_corporate_cusip_and_configured_unit_without_hardcode():
    corporate_cusip, corporate_isin = "037833AK6", "US037833AK68"
    def handle(request):
        return httpx.Response(200, json=bond_profile(cusip=corporate_cusip, isin=corporate_isin, currency="USD")) if request.url.path.endswith("profile") else httpx.Response(200, json={"s": "ok", "c": [0, 101.5], "t": [timestamp(START), timestamp(END)]})
    result = FinnhubBondProvider({"api_key": "fixture", "quote_unit": "percent_of_par"}, client_for(handle)).fetch(corporate_cusip, "cusip", "bond", START, END, RequestBudget())
    assert result["security"]["cusip"] == corporate_cusip
    assert result["items"][0]["price"] == 0, "An actual reported defaulted-bond zero differs from missing"
    assert result["items"][1]["quote_unit"] == "percent_of_par"
    assert result["items"][1]["quote_unit_origin"] == "configuration"
    assert result["items"][1]["currency"] == "USD"


@pytest.mark.parametrize("profile", [bond_profile(cusip="000000000"), {}, [], bond_profile(isin=""), bond_profile(isin="US91282CKD20"), bond_profile(isin="US037833AK68")])
def test_bond_identity_failure_never_fetches_history(profile):
    calls = []
    provider = FinnhubBondProvider({"api_key": "fixture"}, client_for(lambda request: calls.append(request) or httpx.Response(200, json=profile)))
    with pytest.raises(ProviderFailure):
        provider.fetch(CUSIP, "cusip", "bond", START, END, RequestBudget())
    assert len(calls) == 1


@pytest.mark.parametrize("prices", [{"s": "ok", "c": [1, 2], "t": [1]}, [], {"s": "surprise"}, {"error": "key fixture invalid"}])
def test_bond_malformed_series_has_safe_error(prices):
    def handle(request):
        return httpx.Response(200, json=bond_profile()) if request.url.path.endswith("profile") else httpx.Response(200, json=prices)
    with pytest.raises(ProviderFailure) as error:
        FinnhubBondProvider({"api_key": "fixture"}, client_for(handle)).fetch(CUSIP, "cusip", "bond", START, END, RequestBudget())
    assert "fixture" not in str(error.value)


def test_no_data_preserves_bond_reference_terms():
    def handle(request):
        return httpx.Response(200, json=bond_profile()) if request.url.path.endswith("profile") else httpx.Response(200, json={"s": "no_data"})
    result = FinnhubBondProvider({"api_key": "fixture"}, client_for(handle)).fetch(CUSIP, "cusip", "bond", START, END, RequestBudget())
    assert result["items"] == []
    assert result["details"]["maturity_date"] == "2029-02-28"


def test_invalid_out_of_range_and_future_bond_prices_are_not_observations():
    def handle(request):
        return httpx.Response(200, json=bond_profile()) if request.url.path.endswith("profile") else httpx.Response(200, text=json.dumps({"s": "ok", "c": [float("nan"), -1, 101, 99], "t": [timestamp(START), timestamp(START), timestamp(date(2027, 1, 1)), timestamp(END)]}), headers={"Content-Type": "application/json"})
    result = FinnhubBondProvider({"api_key": "fixture"}, client_for(handle)).fetch(CUSIP, "cusip", "bond", START, END, RequestBudget())
    assert [row["price"] for row in result["items"]] == [99]


def fund_profile(kind="fund", **general):
    return {"General": {"Code": "SWPPX", "Type": "FUND" if kind == "fund" else "ETF", "Exchange": "NASDAQ", "CurrencyCode": "USD", "ISIN": "US8085098551", "Name": "Example fund", **general},
            "MutualFund_Data": {"Nav": 76.5, "Update_Date": "2026-06-06", "Expense_Ratio": 0.02}}


@pytest.mark.parametrize("identifier,identifier_type", [("SWPPX", "ticker"), ("SWPPX.US", "ticker"), ("US8085098551", "isin")])
def test_fund_fetches_profile_and_native_close_history_without_relabelling_nav(identifier, identifier_type):
    seen = []
    def handle(request):
        seen.append(request)
        if "fundamentals" in request.url.path:
            return httpx.Response(200, json=fund_profile())
        assert request.url.path == "/api/eod/SWPPX.US"
        return httpx.Response(200, json=[{"date": "2026-06-05", "close": 76.25, "adjusted_close": 75, "volume": 0}])
    budget = RequestBudget()
    result = EodhdFundProvider({"api_key": "fixture-key"}, client_for(handle)).fetch(identifier, identifier_type, "fund", START, END, budget)
    assert len(seen) == budget.used == 2
    point = result["items"][0]
    assert point["price"] == 76.25
    assert point["adjusted_close"] == 75
    assert point["quote_unit"] == "currency_per_share"
    assert point["price_basis"] == "close"
    assert result["details"]["Nav"] == 76.5
    assert result["details"]["nav_date_is_confirmed"] is False
    assert "fixture-key" not in json.dumps(result)


@pytest.mark.parametrize("changes", [{"Type": "Common Stock"}, {"Code": "WRONG"}, {"CurrencyCode": ""}, {"Exchange": "LSE"}, {"CUSIP": "91282CKD2"}])
def test_fund_profile_mismatch_prevents_price_fetch(changes):
    seen = []
    provider = EodhdFundProvider({"api_key": "fixture"}, client_for(lambda request: seen.append(request) or httpx.Response(200, json=fund_profile(**changes))))
    with pytest.raises(ProviderFailure):
        provider.fetch("SWPPX", "ticker", "fund", START, END, RequestBudget())
    assert len(seen) == 1


def test_etf_fundamental_sections_are_distinct_from_mutual_fund_nav():
    def handle(request):
        return httpx.Response(200, json={**fund_profile("etf", Code="VTI", Exchange="NYSE ARCA"), "ETF_Data": {"Net_Expense_Ratio": 0.03}}) if "fundamentals" in request.url.path else httpx.Response(200, json=[])
    result = EodhdFundProvider({"api_key": "fixture"}, client_for(handle)).fetch("VTI", "ticker", "etf", START, END, RequestBudget())
    assert result["details"]["Net_Expense_Ratio"] == 0.03
    assert "Nav" not in result["details"]


def test_etf_isin_can_be_confirmed_in_etf_section_and_current_expense_field_is_preserved():
    def handle(request):
        profile = {"General": {"Type": "ETF", "Code": "VTI", "Exchange": "NYSE ARCA", "CurrencyCode": "USD"},
                   "ETF_Data": {"ISIN": "US9229087690", "NetExpenseRatio": 0.0003}}
        return httpx.Response(200, json=profile if "fundamentals" in request.url.path else [])
    result = EodhdFundProvider({"api_key": "fixture"}, client_for(handle)).fetch("US9229087690", "isin", "etf", START, END, RequestBudget())
    assert result["security"]["isin"] == "US9229087690"
    assert result["security"]["ticker"] == "VTI"
    assert result["details"]["NetExpenseRatio"] == 0.0003, "Do not silently convert provider units"


def test_etf_conflicting_general_and_section_isins_are_rejected():
    def handle(request):
        return httpx.Response(200, json={**fund_profile("etf", Code="VTI"), "ETF_Data": {"ISIN": "US9229087690"}})
    budget = RequestBudget()
    with pytest.raises(ProviderFailure) as error:
        EodhdFundProvider({"api_key": "fixture"}, client_for(handle)).fetch("VTI", "ticker", "etf", START, END, budget)
    assert error.value.code == "identity_mismatch"
    assert budget.used == 1


@pytest.mark.parametrize("kind", ["bond", "fund"])
def test_duplicate_provider_days_are_not_silently_last_row_wins(kind):
    def handle(request):
        if "profile" in request.url.path:
            return httpx.Response(200, json=bond_profile())
        if "fundamentals" in request.url.path:
            return httpx.Response(200, json=fund_profile())
        return httpx.Response(200, json={"s": "ok", "c": [99, 100], "t": [timestamp(END), timestamp(END)]} if kind == "bond" else [{"date": END.isoformat(), "close": 99}, {"date": END.isoformat(), "close": 100}])
    provider = FinnhubBondProvider if kind == "bond" else EodhdFundProvider
    with pytest.raises(ProviderFailure, match="duplicate"):
        provider({"api_key": "fixture"}, client_for(handle)).fetch(CUSIP if kind == "bond" else "SWPPX", "cusip" if kind == "bond" else "ticker", kind, START, END, RequestBudget())


@pytest.mark.parametrize("provider,kind,identifier_type", [(FinnhubBondProvider, "bond", "cusip"), (EodhdFundProvider, "fund", "ticker")])
def test_missing_keys_fail_before_any_http_request(provider, kind, identifier_type):
    budget = RequestBudget()
    with pytest.raises(ProviderFailure) as error:
        provider({}, client_for(lambda _: pytest.fail("No HTTP without configured access"))).fetch(CUSIP, identifier_type, kind, START, END, budget)
    assert error.value.code == "not_configured"
    assert budget.used == 0


@pytest.mark.parametrize("status,code", [(401, "access_denied"), (403, "access_denied"), (429, "rate_limited"), (404, "not_found"), (503, "unavailable")])
def test_provider_http_errors_are_controlled_and_consume_failed_attempt(status, code):
    budget = RequestBudget()
    with pytest.raises(ProviderFailure) as error:
        FinnhubBondProvider({"api_key": "secret-key"}, client_for(lambda _: httpx.Response(status, text="secret-key internal failure"))).fetch(CUSIP, "cusip", "bond", START, END, budget)
    assert error.value.code == code
    assert budget.used == 1
    assert "secret-key" not in str(error.value)


def test_gzip_provider_responses_are_decoded_exactly_once():
    def handle(request):
        value = bond_profile() if request.url.path.endswith("profile") else {"s": "ok", "c": [99.25], "t": [timestamp(END)]}
        return httpx.Response(200, content=gzip.compress(json.dumps(value).encode()),
                              headers={"Content-Type": "application/json", "Content-Encoding": "gzip"})
    budget = RequestBudget()
    result = FinnhubBondProvider({"api_key": "fixture"}, client_for(handle)).fetch(CUSIP, "cusip", "bond", START, END, budget)
    assert result["items"][0]["price"] == 99.25
    assert budget.used == 2


def test_provider_budget_hard_ceiling_and_deadline():
    budget = RequestBudget(limit=999)
    for _ in range(5):
        budget.consume()
    with pytest.raises(ProviderFailure) as error:
        budget.consume()
    assert error.value.code == "request_limit" and budget.used == 5
    expired = RequestBudget()
    expired._started -= 50
    with pytest.raises(ProviderFailure) as error:
        expired.consume()
    assert error.value.code == "timeout" and expired.used == 0


def treasury_metadata():
    return [{"cusip": CUSIP, "securityType": "Note", "securityDescription": "5-Year Note", "interestRate": "4.250", "issueDate": "2024-02-29T00:00:00", "maturityDate": "2029-02-28T00:00:00", "frequencyOfInterestPayments": "Semi-Annual", "highYield": "4.320", "floatingRate": "No", "inflationProtected": "No"}]


def treasury_page(day=END, eod="99.50"):
    return f'<h1>Prices For: {day.strftime("%B %d, %Y")}</h1><table><tr><th>CUSIP</th><th>SECURITY TYPE</th><th>RATE</th><th>MATURITY DATE</th><th>CALL DATE</th><th>BUY</th><th>SELL</th><th>END OF DAY</th></tr><tr><td>{CUSIP}</td><td>MARKET BASED NOTE</td><td>4.250%</td><td>02/28/2029</td><td></td><td>99.343750</td><td>99.312500</td><td>{eod}</td></tr></table>'


def test_treasury_public_history_is_bounded_and_keeps_auction_yield_separate():
    seen = []
    def handle(request):
        seen.append(request)
        if "TA_WS" in request.url.path:
            return httpx.Response(200, json=treasury_metadata())
        if request.method == "POST":
            assert b"_csrf=private-form-value" in request.content
            return httpx.Response(302, headers={"location": TreasuryDirectProvider.detail_url})
        if request.url.path.endswith("selectSecurityPriceDate"):
            return httpx.Response(200, text='<form><input name="_csrf" value="private-form-value"></form>')
        return httpx.Response(200, text=treasury_page())
    budget = RequestBudget()
    result = TreasuryDirectProvider(client=client_for(handle)).fetch(CUSIP, "cusip", "bond", START, END, budget)
    assert len(seen) == budget.used == 4
    assert result["details"]["coupon_rate_pct"] == 4.25
    assert result["details"]["auction_high_yield_pct"] == 4.32
    assert result["details"]["auction_yield_is_current"] is False
    assert result["items"][0]["price"] == 99.5
    assert result["items"][0]["quote_unit"] == "percent_of_par"
    assert result["coverage"]["truncated"] is True
    assert result["coverage"]["next_date"] == "2026-06-04"
    assert "private-form-value" not in json.dumps(result)


def test_treasury_does_not_forward_csrf_or_follow_redirect_to_other_host():
    def handle(request):
        if "TA_WS" in request.url.path:
            return httpx.Response(200, json=treasury_metadata())
        if request.method == "POST":
            return httpx.Response(302, headers={"location": "https://attacker.example/prices"})
        return httpx.Response(200, text='<input name="_csrf" value="private-form-value">')
    budget = RequestBudget()
    with pytest.raises(ProviderFailure) as error:
        TreasuryDirectProvider(client=client_for(handle)).fetch(CUSIP, "cusip", "bond", START, END, budget)
    assert error.value.code == "invalid_response"
    assert budget.used == 3


def test_corporate_is_not_relabelled_as_treasury_when_no_official_match():
    budget = RequestBudget()
    with pytest.raises(ProviderFailure) as error:
        TreasuryDirectProvider(client=client_for(lambda _: httpx.Response(200, json=[]))).fetch("037833AK6", "cusip", "bond", START, END, budget)
    assert error.value.code == "not_found"
    assert budget.used == 1


def test_invalid_isin_check_digit_cannot_alias_a_real_treasury_cusip():
    budget = RequestBudget()
    with pytest.raises(ProviderFailure):
        TreasuryDirectProvider(client=client_for(lambda _: pytest.fail("No lookup for invalid ISIN"))).fetch("US91282CKD20", "isin", "bond", START, END, budget)
    assert budget.used == 0


def test_treasury_zero_end_of_day_preserves_programme_prices_without_bidask_relabelling():
    from app.us_market_providers import _TreasuryPage
    page = _TreasuryPage()
    page.feed(treasury_page(eod="0.000000"))
    row = TreasuryDirectProvider()._price_row(page, CUSIP, END)
    assert row["end_of_day_price"] is None
    assert row["raw_end_of_day_price"] == 0
    assert row["end_of_day_status"] == "zero_placeholder"
    assert row["price"] == row["programme_purchase_price"] == 99.343750
    assert row["programme_redemption_price"] == 99.312500
    assert row["price_basis"] == "programme_purchase"
    assert row["side"] == "programme_purchase_mean"


def test_treasury_session_returning_wrong_day_never_invents_request_day():
    def handle(request):
        if "TA_WS" in request.url.path:
            return httpx.Response(200, json=treasury_metadata())
        if request.method == "POST":
            return httpx.Response(200, text=treasury_page(day=date(2026, 6, 4)))
        return httpx.Response(200, text='<input name="_csrf" value="private-form-value">')
    result = TreasuryDirectProvider(client=client_for(handle)).fetch(CUSIP, "cusip", "bond", START, END, RequestBudget())
    assert result["items"] == []
    assert result["coverage"]["next_date"] == END.isoformat()


def test_malformed_treasury_numeric_grouping_does_not_create_a_hundredfold_price():
    from app.us_market_providers import _TreasuryPage
    page = _TreasuryPage()
    text = treasury_page(eod="0").replace("99.343750", "99,34").replace("99.312500", "99,31")
    page.feed(text)
    assert TreasuryDirectProvider()._price_row(page, CUSIP, END) is None
