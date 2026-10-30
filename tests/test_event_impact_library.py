import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1] / "app" / "workflows"


def records():
    return [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "cases").glob("*.yaml"))]


def test_historical_library_has_resolvable_sources_and_no_fitted_probabilities():
    cases = records()
    assert len({r["case"]["id"] for r in cases}) == len(cases)
    for record in cases:
        case = record["case"]
        sources = {source["id"] for source in record["sources"]}
        assert set(case["source_ids"]) <= sources
        assert case["verified_outcomes"]
        for outcome in case["verified_outcomes"]:
            assert set(outcome["source_ids"]) <= sources
            if outcome.get("measurement_basis") == "source_reported_percentage_not_recomputed":
                assert outcome["baseline_value"] is None
                assert outcome["end_value"] is None
                assert outcome["window_end"]
                assert outcome["reported_precision"]
            elif outcome["metric"] in {"stock_return", "index_return"}:
                actual = 100 * (outcome["end_value"] / outcome["baseline_value"] - 1)
                assert abs(actual - outcome["change_pct"]) < 1e-7
        assert record["learning_status"]["eligible_as_population_probability_sample"] is False
        assert record["learning_status"]["model_updated"] is False
        assert all(p["estimate_pct"] is None for p in record["probabilities"])


def test_exposure_maps_reference_existing_cases_and_include_contrasting_outcomes():
    cases = records()
    case_ids = {record["case"]["id"] for record in cases}
    events = {record["case"]["event_id"] for record in cases}
    for path in (ROOT / "patterns").glob("*.yaml"):
        pattern = yaml.safe_load(path.read_text())
        assert set(pattern["event_ids"]) <= events
        assert set(pattern.get("case_ids", [])) <= case_ids
        matched = [r for r in cases if r["case"]["event_id"] in pattern["event_ids"]]
        assert set(pattern["observed_symbols"]) <= {r["case"]["symbol"] for r in matched}
        for record in matched:
            if record["case"].get("pattern_ids"):
                assert pattern["id"] in record["case"]["pattern_ids"]
                assert set(record["case"].get("channel_ids", [])) <= {c["id"] for c in pattern["reason_to_exposure"]}
    by_event = {}
    for record in cases:
        values = [m["change_pct"] for m in record["case"]["verified_outcomes"] if m.get("change_pct") is not None and m["metric"] in {"stock_return", "index_return"}]
        by_event.setdefault(record["case"]["event_id"], []).extend(values)
    assert sum(any(x > 0 for x in values) and any(x < 0 for x in values) for values in by_event.values()) >= 4


def test_later_company_results_are_not_daily_event_returns_or_hindsight_forecasts():
    cases = records()
    delta = next(r for r in cases if r["case"]["id"] == "dal-financials-covid-global-selloff-2020-03-16")
    metrics = {m["metric"]: m for m in delta["case"]["verified_outcomes"]}
    revenue, profit = metrics["revenue"], metrics["net_income"]
    assert abs(revenue["change_pct"] - 100 * (17095 / 47007 - 1)) < 1e-7
    assert profit["baseline_value"] > 0 > profit["end_value"]
    assert profit["change_pct"] is None
    assert profit["absolute_change"] == -17152
    assert all(m["evidence_available_after_market_event"] and not m["event_attributable"] for m in metrics.values())
    covid_events = [r for r in cases if r["learning_status"].get("event_family_id") == "covid19-pandemic"]
    assert len({r["case"]["event_id"] for r in covid_events}) == 2


def test_assistant_can_page_through_all_evidence_without_tool_payload_truncation():
    from app import main

    index = main.event_impact_events()
    assert len(json.dumps(index, ensure_ascii=False, default=str)) < 80_000
    seen = []
    offset = 0
    while offset is not None:
        page = main.event_impact_cases(limit=5, offset=offset)
        assert len(json.dumps(page, ensure_ascii=False, default=str)) < 80_000
        assert page["offset"] == offset
        assert page["count"] <= 5
        seen.extend(r["case"]["id"] for r in page["items"])
        next_offset = page["next_offset"]
        assert next_offset is None or next_offset > offset
        offset = next_offset
    assert len(seen) == len(set(seen)) == index["case_count"] == len(records())
    assert main.event_impact_cases(offset=len(seen))["next_offset"] is None
