"""Financial history oracles using explicit synthetic agency announcements."""
from copy import deepcopy

import pytest
from fastapi import HTTPException

from app.credit_rating_service import CreditRatingService, SCHEMA
from app.local_portfolio import LocalPortfolioStore
from app.providers import SqliteCache


@pytest.fixture
def environment(tmp_path):
    candidate = {"security_key": "EXAMPLE|NYSE|USD", "symbol": "EXAMPLE", "stock_market": "NYSE", "currency": "USD",
                 "asset_class": "EQUITY", "asset_sub_class": "STOCK", "issuer_name": "Example Corp.",
                 "issuer_identity_verified": True, "name": "Example Corp.", "has_open_position": True}
    inventory = [candidate]
    cache = SqliteCache(tmp_path / "cache.sqlite", ttl_hours=24)
    store = LocalPortfolioStore(tmp_path / "local.sqlite")
    service = CreditRatingService(cache=lambda: cache, settings=lambda: {}, inventory=lambda: inventory,
                                  research_settings=lambda: {}, manual_store=lambda: store)
    return service, candidate, cache, store, inventory


def publish(service, candidate, day, *, grade="BBB", outlook="Stable", revised=False,
            watch=None, action=True, url="https://www.fitchratings.com/research/synthetic-company"):
    # These synthetic values are test assertions, not ratings of a real issuer.
    intro = "Fitch affirmed " if action else "Fitch reports "
    text = intro + "Example Corporation's Long-Term Issuer Default Rating (IDR) at '" + grade + "'. "
    text += ("Its Outlook was revised to " if revised else "The Outlook is ") + outlook + "."
    if watch:
        text += " Example Corporation was placed on Rating Watch " + watch + "."
    source = {"source_id": "source-synthetic", "url": url, "title": "Fitch Ratings Example Corporation",
              "text": text, "published_at": day, "retrieved_at": "2026-11-13T12:00:00+00:00"}
    rows = service._accept_sources(candidate, [source])
    assert rows
    service.publish(candidate, rows)
    return service.read(candidate)


def fitch(context, collection="ratings"):
    return next(row for row in context[collection] if row["agency"] == "fitch")


def draft(context, **changes):
    return {"security_key": context["security_key"], "agency": "fitch", "status": "rated", "rating": "BB+",
            "entity_name": "Example Corp.", "notes": "Synthetic user assertion", "expected_revision": context["manual_revisions"]["fitch"],
            "expected_identity": context["identity_token"], **changes}


def test_first_observation_is_detected_and_same_grade_affirmation_does_not_reset_marker(environment):
    service, candidate, _, _, _ = environment
    first = publish(service, candidate, "2026-03-01")
    event, = first["rating_history"]
    assert event["event_type"] == "first_observation" and event["date_basis"] == "detected" and event["change_date"] is None
    assert event["rating_date"] == "2026-03-01" and event["new_rating"] == "BBB" and event["previous_rating"] is None
    affirmed = publish(service, candidate, "2026-04-01")
    assert affirmed["rating_history"] == first["rating_history"]
    assert fitch(affirmed)["rating_date"] == "2026-04-01"
    assert fitch(affirmed)["latest_change"] == event


def test_grade_and_forward_changes_keep_independent_dates_and_marker(environment):
    service, candidate, _, _, _ = environment
    first = publish(service, candidate, "2026-03-01")
    revised = publish(service, candidate, "2026-05-01", outlook="Negative", revised=True)
    assert [row["event_type"] for row in revised["rating_history"]].count("outlook_change") == 1
    forward = next(row for row in revised["rating_history"] if row["event_type"] == "outlook_change")
    assert forward["date_basis"] == "agency_action" and forward["change_date"] == "2026-05-01"
    assert fitch(revised)["latest_change"]["event_id"] == fitch(first)["latest_change"]["event_id"]
    changed = publish(service, candidate, "2026-06-01", grade="BBB-", outlook="Negative", watch="Negative")
    event = fitch(changed)["latest_change"]
    assert (event["event_type"], event["previous_rating"], event["new_rating"]) == ("rating_change", "BBB", "BBB-")
    assert event["change_date"] == "2026-06-01" and event["date_basis"] == "agency_action"
    watch = next(row for row in changed["rating_history"] if row["event_type"] == "watch_change")
    assert watch["change_date"] == "2026-06-01" and watch["new_watch"] == "negative"
    assert fitch(changed)["latest_change"]["event_id"] != watch["event_id"]
    repeated = publish(service, candidate, "2026-06-01", grade="BBB-", outlook="Negative", watch="Negative")
    assert repeated["rating_history"] == changed["rating_history"]


def test_observed_grade_change_without_agency_action_date_is_explicitly_detected(environment):
    service, candidate, _, _, _ = environment
    publish(service, candidate, "2026-03-01", action=False)
    changed = publish(service, candidate, "2026-04-01", grade="BBB-", action=False)
    event = fitch(changed)["latest_change"]
    assert event["event_type"] == "rating_change" and event["date_basis"] == "detected" and event["change_date"] is None
    assert event["rating_date"] is None and fitch(changed)["rating_date"] is None


def test_late_older_source_cannot_roll_back_grade_signals_or_history(environment):
    service, candidate, _, _, _ = environment
    current = publish(service, candidate, "2026-07-01", grade="BBB-", outlook="Negative", revised=True)
    older = publish(service, candidate, "2026-01-01", grade="A", outlook="Stable",
                    url="https://www.fitchratings.com/research/older-synthetic-company")
    assert fitch(older)["rating"] == "BBB-" and fitch(older)["outlook"] == "negative"
    assert older["rating_history"] == current["rating_history"]


def test_axis_changes_do_not_invent_grade_change_or_replace_primary_marker(environment):
    service, candidate, _, _, _ = environment
    first = publish(service, candidate, "2026-03-01")
    baseline = service._public_snapshot(candidate)["observations"][0]
    national = {**deepcopy(baseline), "scale": "national", "rating": "BBB(tha)", "rating_raw": "BBB(tha)",
                "source_url": "https://www.fitchratings.com/research/national-synthetic-company"}
    service.publish(candidate, [national])
    context = service.read(candidate)
    assert len(context["rating_history"]) == 2
    assert all(row["event_type"] == "first_observation" for row in context["rating_history"])
    assert fitch(context)["rating"] == "BBB" and fitch(context)["latest_change"] == fitch(first)["latest_change"]


def test_manual_add_edit_clear_are_atomic_user_events_and_preserve_agency_evidence(environment):
    service, candidate, _, store, _ = environment
    public = publish(service, candidate, "2026-03-01")
    token = store.change_token()
    saved = service.save_manual(draft(public), {"username": "operator"})
    assert saved["retrieved_ratings"] == public["retrieved_ratings"]
    assert fitch(saved)["outlook"] == fitch(saved)["watch"] == "unknown"
    event = fitch(saved)["latest_change"]
    assert event["event_type"] == "manual_added" and event["actor"] == "operator" and event["date_basis"] == "manual_entry"
    assert event["change_date"] is None and event["origin"] == "manual"
    before = deepcopy(saved["rating_history"])
    with pytest.raises(HTTPException) as conflict:
        service.save_manual(draft(public), {"username": "other"})
    assert conflict.value.status_code == 409 and service.read(candidate)["rating_history"] == before
    edited = service.save_manual(draft(saved, rating="BB"), {"username": "admin"})
    assert fitch(edited)["latest_change"]["event_type"] == "manual_updated"
    cleared = service.clear_manual(candidate["security_key"], "fitch", 2, edited["identity_token"], actor={"username": "admin"})
    assert fitch(cleared)["rating"] == "BBB" and fitch(cleared)["rating_date"] == "2026-03-01"
    event = fitch(cleared)["latest_change"]
    assert event["event_type"] == "manual_cleared" and event["previous_rating"] == "BB" and event["new_rating"] == "BBB"
    assert event["date_basis"] == "manual_entry" and event["actor"] == "admin"
    assert cleared["retrieved_ratings"] == public["retrieved_ratings"] and store.change_token() == token
    assert [row["detected_at"] for row in cleared["rating_history"]] == sorted(
        [row["detected_at"] for row in cleared["rating_history"]], reverse=True)


def test_history_and_source_baseline_survive_cache_clear_restart_and_backup(environment, tmp_path):
    service, candidate, cache, store, inventory = environment
    public = publish(service, candidate, "2026-03-01")
    with cache._connect() as connection:
        connection.execute("delete from security_snapshot")
    restored = LocalPortfolioStore(tmp_path / "restored.sqlite")
    restored.import_data(store.export_data())
    for local in (LocalPortfolioStore(store.path), restored):
        restarted = CreditRatingService(cache=lambda: cache, settings=lambda: {}, inventory=lambda: inventory,
            research_settings=lambda: {}, manual_store=lambda: local)
        assert restarted.read(candidate) == public
    summary, = service.summaries([candidate["security_key"]])["items"]
    assert "rating_history" not in summary
    latest = fitch(summary)["latest_change"]
    assert latest and all("evidence_quote" not in row for row in latest["sources"])
    assert any(row.get("evidence_quote") for row in public["rating_history"][0]["sources"])


def test_changed_identity_and_unavailable_attempt_do_not_fake_agency_changes(environment):
    service, candidate, _, _, inventory = environment
    first = publish(service, candidate, "2026-03-01")
    service.record_attempt(candidate, ["fitch"], "source_read_failed")
    checked = service.read(candidate)
    assert checked["rating_history"] == first["rating_history"] and fitch(checked)["rating"] == "BBB"
    inventory[0] = {**candidate, "issuer_name": "Example Bank Corporation"}
    assert service.read(inventory[0])["rating_history"] == []
    assert fitch(service.read(inventory[0]))["rating"] is None


def test_zero_web_finalization_keeps_unchecked_state_and_inventory_is_not_child_truncated(environment):
    service, candidate, _, _, inventory = environment
    inventory.extend({**candidate, "symbol": "EXAMPLE" + str(index), "security_key": "EXAMPLE" + str(index) + "|NYSE|USD"}
                     for index in range(1, 5))
    assert len(service.inventory("open")) == 5
    assert len(service.candidates("open")["items"]) == 3
    outcome, = service.finalize([], "owner", "never-researched", proposal={"records": []},
                               candidates={candidate["security_key"]: candidate})
    assert outcome["status"] == "not_attempted" and outcome["attempted"] is False
    assert outcome["verified_agencies"] == []
    assert all(row["status"] == "not_checked" and not row.get("checked_at") for row in service.read(candidate)["ratings"])


def test_full_evidence_bound_retains_new_grade_and_immutable_previous_history(environment):
    service, candidate, _, _, _ = environment
    initial = publish(service, candidate, "2026-01-01", grade="A")
    original = service._public_snapshot(candidate)["observations"][0]
    service.publish(candidate, [{**deepcopy(original), "source_url": "https://www.fitchratings.com/research/old-" + str(index)}
                                for index in range(149)])
    assert len(service._public_snapshot(candidate)["observations"]) == 150
    changed = publish(service, candidate, "2026-10-10", grade="BBB+")
    assert len(service._public_snapshot(candidate)["observations"]) == 150
    assert fitch(changed)["rating"] == "BBB+"
    event = fitch(changed)["latest_change"]
    assert event["event_type"] == "rating_change" and event["previous_rating"] == "A" and event["new_rating"] == "BBB+"
    assert any(row["event_id"] == initial["rating_history"][0]["event_id"] for row in changed["rating_history"])


def test_explicit_document_alias_keeps_existing_canonical_history_axis(environment):
    service, candidate, _, _, _ = environment
    publish(service, candidate, "2026-03-01")
    source = {"source_id": "source-alias", "url": "https://www.fitchratings.com/research/synthetic-alias",
              "title": "Fitch Ratings Example Corporation", "published_at": "2026-04-01",
              "retrieved_at": "2026-11-13T12:00:00+00:00",
              "text": "Example Corporation (EXCO) is the rated company.\n\nFitch raised its Long-Term Issuer Default Rating (IDR) on EXCO to 'BBB+'. The Outlook is Stable."}
    rows = service._accept_sources(candidate, [source])
    assert rows and all(row["entity_name"] == "Example Corp." for row in rows)
    service.publish(candidate, rows)
    context = service.read(candidate)
    assert sum(row["event_type"] == "first_observation" for row in context["rating_history"]) == 1
    event = fitch(context)["latest_change"]
    assert event["event_type"] == "rating_change" and event["previous_rating"] == "BBB" and event["new_rating"] == "BBB+"
    assert any("Example Corporation (EXCO)" in (item.get("evidence_quote") or "") for item in event["sources"])
