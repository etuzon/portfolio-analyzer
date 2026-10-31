"""Financial evidence must retain its period, filing and debt composition."""
from datetime import date

import pytest

from app import providers
from app.providers import MarketDataHub, SecCompanyFactsProvider, SqliteCache


def fact(value, *, end="2024-12-31", start="2024-01-01", filed="2025-02-20", accn="filing-1"):
    row = {"fp": "FY", "fy": 2024, "form": "10-K", "end": end, "filed": filed, "val": value, "accn": accn}
    if start is not None:
        row["start"] = start
    return row


def facts(**concepts):
    return {"facts": {"us-gaap": {name: {"units": {"USD": values}} for name, values in concepts.items()}}}


def parse(raw, as_of=None):
    provider = object.__new__(SecCompanyFactsProvider)
    return provider._fundamentals_from_facts(raw, {}, as_of)["income_statement"]["annualReports"]


def test_annual_filing_does_not_turn_a_quarter_into_annual_revenue():
    annual = fact(1000)
    later_quarter = fact(300, start="2024-10-01", filed="2025-03-01", accn="amendment")
    missing_duration = fact(5000, start=None, filed="2025-04-01")
    report = parse(facts(Revenues=[annual, later_quarter, missing_duration]))[0]
    assert report["totalRevenue"] == 1000
    assert report["periodStart"] == "2024-01-01"
    assert report["filingDate"] == "2025-02-20"


@pytest.mark.parametrize("start", [None, "2024-10-01", "2023-01-01", "invalid"])
def test_unverified_or_nonannual_flow_has_no_annual_report(start):
    assert parse(facts(Revenues=[fact(100, start=start)])) == []


def test_matching_52_week_period_is_an_annual_report():
    report = parse(facts(Revenues=[fact(1000, start="2023-07-30", end="2024-07-27")]))[0]
    assert report["totalRevenue"] == 1000
    assert report["periodStart"] == "2023-07-30"


def test_instant_metrics_join_exact_fiscal_date_without_creating_extra_years():
    reports = parse(facts(
        Revenues=[fact(1000)],
        AssetsCurrent=[fact(50, end="2024-03-31", start=None)],
        LiabilitiesCurrent=[fact(100, start=None)],
    ))
    assert len(reports) == 1
    assert reports[0]["fiscalDateEnding"] == "2024-12-31"
    assert "totalCurrentAssets" not in reports[0]
    assert reports[0]["totalCurrentLiabilities"] == 100


def test_same_calendar_year_annual_periods_remain_separate():
    reports = parse(facts(
        Revenues=[fact(600, start="2023-04-01", end="2024-03-31"), fact(1000)],
        NetIncomeLoss=[fact(60, start="2023-04-01", end="2024-03-31"), fact(100)],
    ))
    assert [(row["fiscalDateEnding"], row["totalRevenue"], row["netIncome"]) for row in reports] == [
        ("2024-03-31", 600, 60), ("2024-12-31", 1000, 100),
    ]


def test_flows_with_different_starts_do_not_form_one_margin():
    report = parse(facts(Revenues=[fact(1000)], NetIncomeLoss=[fact(100, start="2023-12-15")]))[0]
    assert report["totalRevenue"] == 1000
    assert "netIncome" not in report


def test_debt_combines_distinct_matched_components():
    report = parse(facts(
        Revenues=[fact(1000)],
        LongTermDebtCurrent=[fact(100, start=None)],
        LongTermDebtNoncurrent=[fact(900, start=None)],
    ))[0]
    assert report["longTermDebt"] == 1000


def test_reported_total_debt_is_not_added_to_its_components():
    report = parse(facts(
        Revenues=[fact(1000)], LongTermDebt=[fact(1100, start=None)],
        LongTermDebtCurrent=[fact(100, start=None)], LongTermDebtNoncurrent=[fact(900, start=None)],
    ))[0]
    assert report["longTermDebt"] == 1100


@pytest.mark.parametrize("mismatch", ["date", "filing", "accession"])
def test_unmatched_debt_components_do_not_claim_total_debt(mismatch):
    current = fact(100, start=None)
    if mismatch == "date":
        current["end"] = "2024-03-31"
    elif mismatch == "filing":
        current["filed"] = "2025-02-21"
    else:
        current["accn"] = "other-filing"
    report = parse(facts(
        Revenues=[fact(1000)], LongTermDebtCurrent=[current], LongTermDebtNoncurrent=[fact(900, start=None)],
    ))[0]
    assert "longTermDebt" not in report


@pytest.mark.parametrize("component", ["LongTermDebtCurrent", "LongTermDebtNoncurrent"])
def test_one_debt_component_does_not_claim_complete_debt(component):
    report = parse(facts(Revenues=[fact(1000)], **{component: [fact(100, start=None)]}))[0]
    assert "longTermDebt" not in report


def test_debt_uses_latest_complete_revision_and_respects_historical_cutoff():
    raw = facts(
        Revenues=[fact(1000)],
        LongTermDebtCurrent=[fact(100, start=None), fact(110, start=None, filed="2025-03-01", accn="amendment")],
        LongTermDebtNoncurrent=[fact(900, start=None), fact(990, start=None, filed="2025-03-01", accn="amendment")],
    )
    assert parse(raw, date(2025, 2, 28))[0]["longTermDebt"] == 1000
    assert parse(raw)[0]["longTermDebt"] == 1100


def test_reported_total_alone_is_complete_debt():
    report = parse(facts(Revenues=[fact(1000)], LongTermDebt=[fact(1000, start=None)]))[0]
    assert report["longTermDebt"] == 1000


def test_historical_restatement_uses_only_the_available_revision():
    raw = facts(Revenues=[fact(1000), fact(1200, filed="2026-02-01", accn="restatement")])
    assert parse(raw, date(2025, 12, 31))[0]["totalRevenue"] == 1000
    assert parse(raw)[0]["totalRevenue"] == 1200


@pytest.mark.parametrize("value", ["NaN", float("inf"), "-Infinity", True])
def test_nonfinite_and_boolean_financial_values_are_unavailable(value):
    report = parse(facts(Revenues=[fact(1000)], NetIncomeLoss=[fact(value)]))[0]
    assert "netIncome" not in report


def test_financial_revenue_requires_matched_period_and_filing_components():
    report = parse(facts(
        NetIncomeLoss=[fact(100)], InterestIncomeExpenseNet=[fact(200)],
        NoninterestIncome=[fact(50, filed="2025-03-01", accn="other-filing")],
    ))[0]
    assert "totalRevenue" not in report


def legacy_cache_hub(tmp_path, monkeypatch):
    monkeypatch.setattr(providers, "data_dir", lambda: tmp_path)
    hub = MarketDataHub({"primary": "sec_company_facts", "fallback": [], "cache_ttl_hours": 1})
    provider = hub.providers[0]
    hub.cache.set("sec:company-tickers", {"0": {"ticker": "ACME", "cik_str": 1, "title": "Example"}})
    hub.cache.set("sec:companyfacts:0000000001", facts(Revenues=[fact(1000)]))
    old = {"income_statement": {"annualReports": [{"fiscalDateEnding": "2024-12-31", "totalRevenue": 300}]}}
    for kind in ["fundamentals", "fundamentals_as_of:2025-12-31"]:
        hub.cache.set_security_snapshot(provider.name, "ACME", kind, old)
    def unavailable(*args, **kwargs):
        raise providers.ProviderError("Offline fixture")
    monkeypatch.setattr(provider, "fundamentals", unavailable)
    monkeypatch.setattr(provider, "fundamentals_as_of", unavailable)
    return hub


@pytest.mark.parametrize("historical", [False, True])
def test_legacy_normalized_sec_cache_is_reparsed_during_provider_outage(tmp_path, monkeypatch, historical):
    hub = legacy_cache_hub(tmp_path, monkeypatch)
    data, status = hub.fundamentals_as_of("ACME", date(2025, 12, 31)) if historical else hub.fundamentals("ACME")
    assert data["income_statement"]["annualReports"][0]["totalRevenue"] == 1000
    assert data["fundamentals_parser_version"] == providers.SEC_FUNDAMENTALS_PARSER_VERSION
    assert status["sec_company_facts"].startswith("stale")


def test_immediate_cached_view_does_not_resurrect_old_normalized_sec_values(tmp_path, monkeypatch):
    hub = legacy_cache_hub(tmp_path, monkeypatch)
    data, _ = providers.CachedMarketDataHub(hub).fundamentals("ACME")
    assert data["income_statement"]["annualReports"][0]["totalRevenue"] == 1000


def test_legacy_sec_snapshot_without_reconstructable_raw_evidence_is_not_used(tmp_path, monkeypatch):
    hub = legacy_cache_hub(tmp_path, monkeypatch)
    with hub.cache._connect() as connection:
        connection.execute("delete from cache where key=?", ("sec:companyfacts:0000000001",))
    assert hub.fundamentals("ACME")[0] == {}
    assert providers.CachedMarketDataHub(hub).fundamentals("ACME")[0] == {}
