"""Validation requires frozen, distinct forecasts recorded before the outcome."""
import json

import pytest

from app import local_portfolio
from app.local_portfolio import LocalPortfolioStore
from app.outlook_scoring import OUTLOOK_EVALUATION_VERSION, OUTLOOK_MODEL_VERSION, evaluation_contract


def baseline():
    return {
        "model_version": OUTLOOK_MODEL_VERSION, "score_status": "scored",
        "target": {"fiscal_date": "2024-12-31", "filing_date": "2025-02-20"},
        "peers": [{"symbol": "P1", "fiscal_date": "2024-12-31", "filing_date": "2025-02-01"},
                  {"symbol": "P2", "fiscal_date": "2024-12-31", "filing_date": "2025-02-02"}],
        "evaluation_contract": evaluation_contract(),
        "validation_evidence": {"mode": "prospective", "as_of_date": "2025-06-01"},
        "batch": {},
    }


@pytest.fixture
def store_and_clock(tmp_path, monkeypatch):
    clock = {"now": "2025-06-01T12:00:00Z"}
    monkeypatch.setattr(local_portfolio, "_now", lambda: clock["now"])
    return LocalPortfolioStore(tmp_path / "local.sqlite3"), clock


def save_forecast(store, symbol="ACME", **overrides):
    payload = {
        "symbol": symbol, "created_at": "2025-06-01T00:00:00Z", "horizon_date": "2026-06-01",
        "model_version": OUTLOOK_MODEL_VERSION, "score": 70, "label": "Good", "direction": "positive",
        "confidence": "High", "baseline": baseline(), "thesis": "Frozen original forecast",
    }
    payload.update(overrides)
    return store.save_company_report_prediction(payload)


def evaluate(store, clock, record, *, correct=True, grade=None, actual_overrides=None, advance=True):
    if advance:
        clock["now"] = "2026-03-01T12:00:00Z"
    actual = {"fiscal_date": "2025-12-31", "filing_date": "2026-02-20", "evaluation_contract_version": OUTLOOK_EVALUATION_VERSION}
    actual.update(actual_overrides or {})
    return store.evaluate_company_report_prediction(
        record["id"], actual, record["direction"] if correct else "negative",
        (100 if correct else 0) if grade is None else grade, "Fixture evaluation",
    )


def cohort(store, clock, *, count=30, hits=30, payload_changes=None):
    clock["now"] = "2025-06-01T12:00:00Z"
    records = [save_forecast(store, f"S{i}", **(payload_changes or {})) for i in range(count)]
    for index, record in enumerate(records):
        evaluate(store, clock, record, correct=index < hits)
    return records


def test_server_recording_time_is_immutable_and_ignores_client_value(store_and_clock):
    store, clock = store_and_clock
    original = save_forecast(store, recorded_at="2000-01-01T00:00:00Z")
    assert original["recorded_at"] == "2025-06-01T12:00:00Z"
    clock["now"] = "2026-01-01T12:00:00Z"
    changed = save_forecast(store, id=original["id"], created_at="2026-01-01T00:00:00Z", score=99,
                            direction="negative", label="Strong", baseline={"changed": True}, thesis="Changed")
    for field in ["recorded_at", "created_at", "score", "direction", "label", "baseline", "thesis"]:
        assert changed[field] == original[field]


def test_recorded_at_survives_export_import(store_and_clock, tmp_path):
    store, _ = store_and_clock
    original = save_forecast(store)
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    restored.import_data(store.export_data())
    assert restored.list_company_report_predictions()[0]["recorded_at"] == original["recorded_at"]


def test_old_backup_without_recording_time_remains_unverified(store_and_clock, tmp_path):
    store, _ = store_and_clock
    save_forecast(store)
    exported = store.export_data()
    exported["data"]["company_report_predictions"][0].pop("recorded_at")
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    restored.import_data(exported)
    assert restored.list_company_report_predictions()[0]["recorded_at"] == ""
    assert restored.company_report_scorecard()["quality_gate"]["excluded_counts"] == {"unverified_recording_time": 1}


def test_legacy_database_migration_does_not_invent_server_recording_time(store_and_clock):
    store, _ = store_and_clock
    original = save_forecast(store, model_version="report-outlook-v4")
    with store._connect() as connection:
        connection.execute("alter table company_report_predictions drop column recorded_at")
    reopened = LocalPortfolioStore(store.path)
    migrated = reopened.list_company_report_predictions()[0]
    assert migrated["recorded_at"] == ""
    for field in ["score", "direction", "label", "baseline", "thesis", "created_at"]:
        assert migrated[field] == original[field]


def test_thirty_distinct_genuine_prospective_outcomes_can_pass(store_and_clock):
    store, clock = store_and_clock
    cohort(store, clock)
    gate = store.company_report_scorecard()["quality_gate"]
    assert gate["eligible_count"] == 30
    assert gate["validation_accuracy_percent"] == 100
    assert gate["accuracy_lower_bound_percent"] == pytest.approx(88.65, abs=0.01)
    assert gate["passed"] is True
    assert gate["status"] == "validated"
    assert gate["current_model_version"] == OUTLOOK_MODEL_VERSION
    assert gate["failed_reasons"] == []


@pytest.mark.parametrize("hits, passes", [(27, False), (28, True)])
def test_point_accuracy_alone_cannot_pass_the_wilson_bound(store_and_clock, hits, passes):
    store, clock = store_and_clock
    cohort(store, clock, hits=hits)
    gate = store.company_report_scorecard()["quality_gate"]
    assert gate["validation_accuracy_percent"] >= 90
    assert gate["passed"] is passes
    assert ("confidence_bound_below_target" in gate["failed_reasons"]) is not passes


def test_twenty_nine_perfect_observations_still_need_the_minimum_sample(store_and_clock):
    store, clock = store_and_clock
    cohort(store, clock, count=29)
    gate = store.company_report_scorecard()["quality_gate"]
    assert gate["validation_accuracy_percent"] == 100
    assert gate["failed_reasons"] == ["insufficient_observations"]
    assert gate["passed"] is False


def test_repeated_calibration_and_mixed_versions_do_not_validate(store_and_clock):
    store, clock = store_and_clock
    records = []
    for index in range(30):
        saved_baseline = baseline()
        saved_baseline["batch"] = {"id": f"calibration-{index}", "phase": "calibration"}
        records.append(save_forecast(store, model_version="old-v1" if index % 2 else "report-outlook-v4", baseline=saved_baseline))
    for record in records:
        evaluate(store, clock, record)
    scorecard = store.company_report_scorecard()
    assert scorecard["evaluated"] == 30
    assert scorecard["accuracy_percent"] == 100
    assert scorecard["quality_gate"]["eligible_count"] == 0
    assert scorecard["quality_gate"]["legacy_count"] == 30
    assert scorecard["quality_gate"]["passed"] is False


@pytest.mark.parametrize("phase", ["calibration", "holdout"])
def test_batch_phase_labels_cannot_create_prospective_validation(store_and_clock, phase):
    store, clock = store_and_clock
    saved_baseline = baseline()
    saved_baseline["batch"] = {"id": "client-labeled-batch", "phase": phase}
    record = save_forecast(store, baseline=saved_baseline)
    evaluate(store, clock, record)
    gate = store.company_report_scorecard()["quality_gate"]
    assert gate["eligible_count"] == 0
    assert gate["excluded_counts"] == {"batch_or_backtest": 1}


def test_earliest_forecast_defines_an_outcome_across_horizons_and_retries(store_and_clock):
    store, clock = store_and_clock
    original = save_forecast(store, id="original")
    clock["now"] = "2025-06-01T12:01:00Z"
    repeats = [save_forecast(store, id=f"retry-{index}", horizon_date="2027-06-01") for index in range(29)]
    evaluate(store, clock, original, correct=False)
    for record in repeats:
        evaluate(store, clock, record)
    gate = store.company_report_scorecard()["quality_gate"]
    assert gate["eligible_count"] == 1
    assert gate["validation_accuracy_percent"] == 0
    assert gate["excluded_counts"] == {"duplicate_economic_outcome": 29}
    assert gate["passed"] is False
    selected = store.company_report_scorecard({row["id"] for row in repeats})["quality_gate"]
    assert selected["eligible_count"] == 0, "selecting only successful retries must not bypass the global first forecast"


def test_equal_server_timestamps_preserve_insertion_order(store_and_clock):
    store, clock = store_and_clock
    original = save_forecast(store, id="z-original")
    retry = save_forecast(store, id="a-successful-retry")
    evaluate(store, clock, original, correct=False)
    evaluate(store, clock, retry)
    gate = store.company_report_scorecard()["quality_gate"]
    assert gate["eligible_count"] == 1
    assert gate["validation_accuracy_percent"] == 0


def test_same_actual_report_is_one_outcome_across_different_baselines(store_and_clock):
    store, clock = store_and_clock
    older_baseline = baseline()
    older_baseline["target"]["fiscal_date"] = "2024-12-01"
    original = save_forecast(store, id="original", baseline=older_baseline)
    clock["now"] = "2025-06-01T12:01:00Z"
    later = save_forecast(store, id="later")
    evaluate(store, clock, original, correct=False)
    evaluate(store, clock, later)
    gate = store.company_report_scorecard()["quality_gate"]
    assert gate["eligible_count"] == 1
    assert gate["validation_accuracy_percent"] == 0
    assert gate["excluded_counts"] == {"duplicate_economic_outcome": 1}
    assert store.company_report_scorecard({later["id"]})["quality_gate"]["eligible_count"] == 0


def test_pending_oldest_forecast_does_not_let_a_successful_retry_take_its_place(store_and_clock):
    store, clock = store_and_clock
    save_forecast(store, id="original")
    clock["now"] = "2025-06-01T12:01:00Z"
    retry = save_forecast(store, id="retry")
    evaluate(store, clock, retry)
    gate = store.company_report_scorecard()["quality_gate"]
    assert gate["eligible_count"] == 0
    assert gate["excluded_counts"] == {"not_evaluated": 1, "duplicate_economic_outcome": 1}


@pytest.mark.parametrize("mutation, reason", [
    (lambda b: b.update(score_status="insufficient"), "not_scored"),
    (lambda b: b["validation_evidence"].update(mode="historical"), "not_prospective"),
    (lambda b: b["validation_evidence"].update(as_of_date="2024-06-01"), "prediction_date_mismatch"),
    (lambda b: b["evaluation_contract"].update(version="different-question"), "evaluation_contract_mismatch"),
    (lambda b: b["target"].update(filing_date="2025-07-01"), "baseline_filing_after_recorded"),
    (lambda b: b["peers"][0].update(filing_date=None), "unavailable_baseline_filings"),
    (lambda b: b.update(related_industries=[{"filing_date": "2025-07-01"}]), "baseline_filing_after_recorded"),
])
def test_validation_requires_verified_baseline_evidence(store_and_clock, mutation, reason):
    store, clock = store_and_clock
    saved_baseline = baseline()
    mutation(saved_baseline)
    record = save_forecast(store, baseline=saved_baseline)
    evaluate(store, clock, record)
    gate = store.company_report_scorecard()["quality_gate"]
    assert gate["eligible_count"] == 0
    assert gate["excluded_counts"] == {reason: 1}


@pytest.mark.parametrize("overrides, reason", [
    ({"filing_date": "2025-06-01"}, "actual_filing_not_after_recorded"),
    ({"filing_date": None}, "actual_filing_not_after_recorded"),
    ({"evaluation_contract_version": "different-question"}, "evaluation_contract_mismatch"),
    ({"fiscal_date": "2026-12-31"}, "invalid_actual_period"),
])
def test_validation_requires_a_new_observed_outcome_for_the_same_contract(store_and_clock, overrides, reason):
    store, clock = store_and_clock
    record = save_forecast(store)
    evaluate(store, clock, record, actual_overrides=overrides)
    gate = store.company_report_scorecard()["quality_gate"]
    assert gate["eligible_count"] == 0
    assert gate["excluded_counts"] == {reason: 1}


def test_future_outcome_cannot_be_reported_before_its_filing(store_and_clock):
    store, clock = store_and_clock
    record = save_forecast(store)
    evaluate(store, clock, record, advance=False)
    assert store.company_report_scorecard()["quality_gate"]["excluded_counts"] == {"actual_not_observed": 1}


@pytest.mark.parametrize("grade", [50, 0])
def test_partial_credit_or_inconsistent_direction_grade_cannot_validate(store_and_clock, grade):
    store, clock = store_and_clock
    record = save_forecast(store)
    evaluate(store, clock, record, grade=grade)
    assert store.company_report_scorecard()["quality_gate"]["excluded_counts"] == {"non_binary_or_inconsistent_grade": 1}


@pytest.mark.parametrize("score", [None, "NaN", float("inf"), float("-inf"), -1, 101, True])
def test_new_nonfinite_or_out_of_range_scores_are_rejected(store_and_clock, score):
    store, _ = store_and_clock
    with pytest.raises(ValueError, match="score must be a finite number"):
        save_forecast(store, score=score)
    assert store.list_company_report_predictions() == []


@pytest.mark.parametrize("grade", ["NaN", float("inf"), float("-inf"), -1, 101, True])
def test_new_nonfinite_or_out_of_range_grades_are_rejected(store_and_clock, grade):
    store, _ = store_and_clock
    with pytest.raises(ValueError, match="grade must be a finite number"):
        save_forecast(store, accuracy_score=grade)
    record = save_forecast(store)
    with pytest.raises(ValueError, match="grade must be a finite number"):
        store.evaluate_company_report_prediction(record["id"], {}, "positive", grade, "Invalid")
    assert store.list_company_report_predictions()[0]["actual_direction"] == "pending"


def test_new_nonfinite_statement_values_cannot_be_saved_in_json(store_and_clock):
    store, _ = store_and_clock
    evidence = baseline()
    evidence["target"]["revenue"] = float("nan")
    with pytest.raises(ValueError, match="JSON compliant"):
        save_forecast(store, baseline=evidence)
    record = save_forecast(store)
    with pytest.raises(ValueError, match="JSON compliant"):
        store.evaluate_company_report_prediction(record["id"], {"revenue": float("inf")}, "positive", 100, "Invalid")
    assert store.list_company_report_predictions()[0]["actual_direction"] == "pending"


@pytest.mark.parametrize("unsafe", [float("inf"), float("-inf"), "NaN", 150, -1, "invalid"])
def test_invalid_legacy_values_remain_stored_but_are_unavailable_and_json_safe(store_and_clock, tmp_path, unsafe):
    store, _ = store_and_clock
    record = save_forecast(store)
    with store._connect() as connection:
        connection.execute("update company_report_predictions set score=?,accuracy_score=?,actual=? where id=?",
                           (unsafe, unsafe, '{"revenue":NaN}', record["id"]))
        before = tuple(connection.execute("select score,accuracy_score,actual from company_report_predictions where id=?", (record["id"],)).fetchone())
    output = store.list_company_report_predictions()[0]
    assert output["score"] is None
    assert output["accuracy_score"] is None
    assert output["actual"] == {"revenue": None}
    assert output["invalid_financial_fields"] == ["accuracy_score", "actual", "score"]
    scorecard = store.company_report_scorecard()
    assert scorecard["invalid_grade_records"] == 1
    assert scorecard["evaluated"] == 0
    assert scorecard["accuracy_percent"] is None
    json.dumps({"prediction": output, "scorecard": scorecard}, allow_nan=False)
    exported = store.export_data()
    json.dumps(exported, allow_nan=False)
    with store._connect() as connection:
        after = tuple(connection.execute("select score,accuracy_score,actual from company_report_predictions where id=?", (record["id"],)).fetchone())
    assert after == before, "safe presentation and export must not rewrite frozen legacy records"
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite3")
    restored.import_data(exported)
    restored_output = restored.list_company_report_predictions()[0]
    assert restored_output["score"] is None
    assert restored_output["accuracy_score"] is None
    assert restored_output["invalid_financial_fields"] == output["invalid_financial_fields"]


def test_invalid_legacy_grade_is_not_in_the_historic_average(store_and_clock):
    store, clock = store_and_clock
    records = [save_forecast(store, symbol) for symbol in ["FIRST", "SECOND", "INVALID"]]
    evaluate(store, clock, records[0])
    evaluate(store, clock, records[1], correct=False)
    evaluate(store, clock, records[2])
    with store._connect() as connection:
        connection.execute("update company_report_predictions set accuracy_score=? where id=?", (float("inf"), records[2]["id"]))
    scorecard = store.company_report_scorecard()
    assert scorecard["evaluated"] == 2
    assert scorecard["accuracy_percent"] == 50
    assert scorecard["invalid_grade_records"] == 1
    json.dumps(scorecard, allow_nan=False)
