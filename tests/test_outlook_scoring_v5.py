from copy import deepcopy
from datetime import date
import json

import pytest

from app import main
from app.local_portfolio import LocalPortfolioStore
from app.outlook_scoring import OUTLOOK_MODEL_VERSION, evaluation_contract


def raw_reports():
    return [{"fiscalDateEnding": f"{year}-12-31", "filingDate": f"{year + 1}-03-01",
        "totalRevenue": 100, "netIncome": 10, "operatingIncome": 20,
        "operatingCashFlow": 10, "capitalExpenditures": 5,
        "longTermDebt": 50, "totalCurrentAssets": 10, "totalCurrentLiabilities": 10}
        for year in (2023, 2024, 2025)]


def report_payload(symbol, rows=None, industry="Industrial components"):
    rows = main._annual_report_rows({"income_statement": {"annualReports": raw_reports() if rows is None else rows}}, 6)
    return {"symbol": symbol, "profile": {"name": symbol, "industry": industry},
        "reports": rows, "latest": rows[0] if rows else {}, "summary": {"years": len(rows)},
        "provider_status": {"fixture": "ok"}, "missing": []}


@pytest.fixture
def research(monkeypatch, tmp_path):
    payloads = {symbol: report_payload(symbol) for symbol in ("T", "P0", "P1")}
    store = LocalPortfolioStore(tmp_path / "predictions.sqlite3")
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "_finance_report_payload", lambda symbol, *a: deepcopy(payloads[symbol]))

    def analyze(**options):
        return main._company_outlook_payload("T", {"peers": ["P0", "P1"],
            "industry": "Industrial components", "as_of_date": "2026-04-01",
            "save_prediction": False, **options})
    return analyze, payloads, store


def test_equal_complete_financial_cohort_is_neutral_with_explicit_tie(research):
    analyze, _, _ = research
    result = analyze()
    assert result["score"] == 50
    assert result["direction"] == "neutral"
    assert result["coverage"]["percent"] == 100
    assert result["rank"] == 1 and result["rank_tied"] is True
    assert result["score_components"]["relative_rank"] == 0
    assert result["score_component_limits"] == {"company_fundamentals": 100}


def test_sparse_evidence_has_no_directional_forecast_or_saved_record(research):
    analyze, payloads, store = research
    for symbol in payloads:
        rows = [{key: value for key, value in row.items() if key in {"fiscalDateEnding", "filingDate", "totalRevenue", "netIncome"}} for row in raw_reports()]
        payloads[symbol] = report_payload(symbol, rows)
    result = analyze(save_prediction=True)
    assert result["score"] is None
    assert result["label"] == "Insufficient data"
    assert result["direction"] == "inconclusive"
    assert result["score_range"]["lower"] < result["score_range"]["upper"]
    assert result["prediction_record"] is None
    assert store.list_company_report_predictions() == []
    assert main._fundamental_score({"net_margin_change_percent": 0}, *([None] * 7)) <= 5


def test_empty_peers_and_related_names_never_create_score_or_coverage_points(research):
    analyze, payloads, _ = research
    original = analyze()
    for symbol in ("EMPTY0", "EMPTY1", "R0", "R1", "R2"):
        payloads[symbol] = report_payload(symbol, [] if symbol.startswith("EMPTY") else raw_reports())
    added = analyze(peers=["P0", "P1", "EMPTY0", "EMPTY1"],
        related_companies=[{"symbol": symbol, "relation": "customer demand"} for symbol in ("R0", "R1", "R2")])
    assert added["score"] == original["score"]
    assert added["coverage"] == original["coverage"]
    assert added["confidence"] == original["confidence"]


def test_only_shared_metric_definitions_determine_comparison(research):
    analyze, payloads, _ = research
    before = analyze()
    for peer in ("P0", "P1"):
        rows = raw_reports()
        for row in rows:
            del row["operatingIncome"]
        payloads[peer] = report_payload(peer, rows)
    assert analyze()["score"] == before["score"]


def test_stale_peers_cannot_supply_a_current_financial_score(research):
    analyze, payloads, _ = research
    for symbol, end in (("T", "2024-12-31"), ("P0", "2024-09-30"), ("P1", "2024-09-30")):
        payloads[symbol]["latest"]["fiscal_date"] = end
    result = analyze(as_of_date="2026-06-15")
    assert result["score"] is None
    assert result["coverage"]["usable_peer_count"] == 0


@pytest.mark.parametrize("industry", ["National Commercial Banks", "Insurance", "Mortgage REIT"])
def test_manual_cohort_cannot_enable_an_unsupported_financial_model(research, industry):
    analyze, payloads, store = research
    payloads["T"]["profile"]["industry"] = industry
    result = analyze(save_prediction=True)
    assert result["score"] is None and result["rank"] is None
    assert result["coverage"]["reason"] == "industry_model_required"
    assert store.list_company_report_predictions() == []


@pytest.mark.parametrize("strong,expected", [(True, 100), (False, 0)])
def test_full_financial_evidence_can_reach_both_score_endpoints(research, strong, expected):
    analyze, payloads, _ = research
    rows = raw_reports()
    rows[-1].update({"totalRevenue": 1000 if strong else 10, "netIncome": 500 if strong else -10,
        "operatingCashFlow": 800 if strong else -100, "capitalExpenditures": 0,
        "longTermDebt": 0 if strong else 1000, "totalCurrentAssets": 1000 if strong else 0})
    payloads["T"] = report_payload("T", rows)
    result = analyze()
    assert result["score"] == expected
    assert result["direction"] == ("positive" if strong else "negative")


def test_annual_normalization_rejects_gaps_duplicates_unknown_availability_and_nonfinite():
    rows = raw_reports()
    rows.pop(1)
    assert main._annual_report_rows({"income_statement": {"annualReports": rows}}, 6)[0]["revenue_growth_percent"] is None
    rows = raw_reports()
    revision = {**rows[-1], "filingDate": "2026-04-01", "totalRevenue": 120}
    normalized = main._annual_report_rows({"income_statement": {"annualReports": [*rows, revision]}}, 6)
    assert len(normalized) == 3
    assert normalized[0]["comparison_fiscal_date"] == "2024-12-31"
    assert normalized[0]["revenue_growth_percent"] == 20
    unknown = {"fiscalDateEnding": "2025-12-31", "totalRevenue": 100, "netIncome": 10}
    assert main._annual_report_rows({"income_statement": {"annualReports": [unknown]}}, 6, date(2026, 4, 1)) == []
    loss = {**raw_reports()[-1], "netIncome": -10, "operatingCashFlow": -20, "capitalExpenditures": 0}
    assert main._annual_report_rows({"income_statement": {"annualReports": [loss]}}, 6)[0]["cash_conversion_percent"] is None
    bad = {**unknown, "totalRevenue": "NaN"}
    normalized = main._annual_report_rows({"income_statement": {"annualReports": [bad]}}, 6)
    json.dumps(normalized, allow_nan=False)
    assert main._relative_points(float("nan"), 0, 12, 20) == 0
    assert main._number_or_none(True) is None


def test_future_cutoff_cannot_admit_a_future_revision():
    original = {"fiscalDateEnding": "2024-12-31", "filingDate": "2025-03-01", "totalRevenue": 100, "netIncome": 10}
    future = {**original, "filingDate": "2035-03-01", "totalRevenue": 999}
    rows = main._annual_report_rows({"income_statement": {"annualReports": [original, future]}}, 6, date(2040, 1, 1))
    assert rows[0]["revenue"] == 100


def test_v5_missing_saved_peer_is_retryable_and_never_switches_target(monkeypatch, tmp_path):
    store = LocalPortfolioStore(tmp_path / "evaluation.sqlite3")
    monkeypatch.setattr(main, "local_store", store)
    prediction = store.save_company_report_prediction({"symbol": "T", "model_version": OUTLOOK_MODEL_VERSION,
        "direction": "positive", "score": 75, "horizon_date": "2026-12-31", "thesis": "Frozen thesis",
        "baseline": {"target": {"fiscal_date": "2024-12-31", "net_margin_percent": 8},
            "peers": [{"symbol": symbol, "fiscal_date": "2024-12-31"} for symbol in ("P0", "P1", "P2")],
            "evaluation_contract": evaluation_contract()}})
    actual = {"fiscal_date": "2025-12-31", "filing_date": "2026-03-01", "revenue_growth_percent": 5, "net_margin_percent": 10}
    peer = {**actual, "revenue_growth_percent": 0, "net_margin_percent": 5}
    missing = set()
    def reports(symbol, *args):
        return {"reports": [] if symbol in missing else [deepcopy(actual if symbol == "T" else peer)], "provider_status": {"fixture": "ok"}}
    monkeypatch.setattr(main, "_finance_report_payload", reports)
    checked = main._evaluate_prediction(prediction)
    assert checked["accuracy_score"] == 100
    missing.add("P1")
    checked = main._evaluate_prediction(prediction)
    assert checked["actual_direction"] == "inconclusive" and checked["accuracy_score"] is None
    assert checked["actual"]["retryable"] is True
    assert all(checked[key] == prediction[key] for key in ("baseline", "score", "direction", "thesis"))
    missing.clear()
    assert main._evaluate_prediction(prediction)["accuracy_score"] == 100


def test_v5_equality_is_neutral_and_uses_next_annual_report(monkeypatch, tmp_path):
    store = LocalPortfolioStore(tmp_path / "evaluation.sqlite3")
    monkeypatch.setattr(main, "local_store", store)
    prediction = store.save_company_report_prediction({"symbol": "T", "model_version": OUTLOOK_MODEL_VERSION,
        "direction": "neutral", "score": 50, "horizon_date": "2026-12-31",
        "baseline": {"target": {"fiscal_date": "2023-12-31", "net_margin_percent": 5},
            "peers": [{"symbol": symbol, "fiscal_date": "2023-12-31"} for symbol in ("P0", "P1")],
            "evaluation_contract": evaluation_contract()}})
    row = {"fiscal_date": "2024-12-31", "filing_date": "2025-03-01", "revenue_growth_percent": 5, "net_margin_percent": 10}
    later = {**row, "fiscal_date": "2025-12-31", "filing_date": "2026-03-01", "revenue_growth_percent": -100}
    monkeypatch.setattr(main, "_finance_report_payload", lambda *args: {"reports": [later, row], "provider_status": {"fixture": "ok"}})
    checked = main._evaluate_prediction(prediction)
    assert checked["actual_direction"] == "neutral"
    assert checked["accuracy_score"] == 100
    assert checked["actual"]["fiscal_date"] == "2024-12-31"
