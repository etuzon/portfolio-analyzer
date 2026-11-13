"""Sovereign identity, source/basis binding and local history acceptance."""
from copy import deepcopy
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from app.local_portfolio import LocalPortfolioStore
from app.providers import SqliteCache
from app.sovereign_ratings import (COUNTRIES, country_descriptor, extract_rating_records,
    normalize_country, normalize_observation)
from app.sovereign_rating_service import PREFIX, SovereignRatingService


MOODYS = ("New York, January 30, 2026 -- Moody's Ratings (Moody's) has today changed the outlook "
    "on the Government of Israel to stable from negative. Concurrently, we have affirmed Israel's "
    "Baa1 long-term local and foreign-currency issuer ratings. We have also affirmed the Baa1 local "
    "and foreign-currency senior unsecured ratings, while the foreign-currency senior unsecured "
    "shelf ratings have been affirmed at (P)Baa1.")


def source(text=MOODYS, **changes):
    return {"source_id": "source-israel", "url": "https://ratings.moodys.com/ratings-news/458577",
        "title": "Moody's Ratings changes Israel outlook", "text": text,
        "published_at": "2026-01-30", "retrieved_at": "2026-11-13T12:00:00+00:00", **changes}


@pytest.fixture
def environment(tmp_path):
    inventory = [{**country_descriptor("IL"), "has_open_position": True},
                 {**country_descriptor("US"), "has_open_position": False}]
    cache = SqliteCache(tmp_path / "cache.sqlite", ttl_hours=24)
    store = LocalPortfolioStore(tmp_path / "local.sqlite")
    service = SovereignRatingService(cache=lambda: cache, settings=lambda: {},
        inventory=lambda: inventory, research_settings=lambda: {"max_web_calls": 8}, manual_store=lambda: store)
    return service, inventory, cache, store


def row(context, agency="moodys", basis="foreign_currency", collection="ratings"):
    return next(item for item in context[collection] if item["agency"] == agency and item["currency_basis"] == basis)


def draft(context, **changes):
    return {"country_code": context["country_code"], "agency": "moodys", "currency_basis": "foreign_currency",
        "status": "rated", "rating": "A3", "notes": "Synthetic manual assertion",
        "expected_revision": context["manual_revisions"]["moodys:foreign_currency"],
        "expected_identity": context["identity_token"], **changes}


def test_catalog_is_explicit_country_identity_without_currency_or_listing_inference():
    assert len(COUNTRIES) == 249
    assert {normalize_country(value) for value in ("USA", "US", "United States", "United States of America")} == {"US"}
    assert normalize_country("ישראל") == "IL"
    assert normalize_country("GBP") is None and normalize_country("NYSE") is None and normalize_country("ZZ") is None
    assert country_descriptor("Canada")["security_key"] == "COUNTRY:CA"
    assert country_descriptor("Puerto Rico")["sovereign_identity"] is False


def test_primary_moodys_source_declares_both_currency_bases_and_independent_action_dates():
    candidate = country_descriptor("IL")
    rows = extract_rating_records(source(), candidate)
    assert {item["currency_basis"] for item in rows} == {"foreign_currency", "local_currency"}
    assert all(item["rating"] == "Baa1" and item["scope"] == "sovereign" for item in rows)
    assert all(item["outlook"] == "stable" and item["watch"] == "unknown" for item in rows)
    assert all(item["rating_date"] == item["outlook_date"] == "2026-01-30" for item in rows)
    verified = normalize_observation(rows[0], candidate, source=source())
    assert verified["fetched_at"] == "2026-11-13T12:00:00+00:00"
    assert verified["sources"][0]["source_kind"] == "agency_public"


def test_native_moodys_city_dateline_is_action_date_but_body_history_dates_are_not():
    candidate = country_descriptor("IL")
    src = source(published_at=None)
    assert all(item["rating_date"] == item["outlook_date"] == "2026-01-30" for item in extract_rating_records(src, candidate))
    src["text"] = "Moody's affirmed Israel's Baa1 long-term issuer ratings. Historical context: January 30, 2026 was an event date."
    rows = extract_rating_records(src, candidate)
    assert rows and rows[0]["observed_at"] is None and rows[0]["rating_date"] is None


def test_unread_link_date_does_not_become_source_publication_or_action_date():
    text = "[Archived release\n30 Jan 2026\n](https://ratings.moodys.com/archived)\nMoody's affirmed Israel's Baa1 long-term local and foreign-currency issuer ratings."
    rows = extract_rating_records(source(text, published_at=None), country_descriptor("IL"))
    assert rows and all(item["rating_date"] is None and item["observed_at"] is None for item in rows)


@pytest.mark.parametrize("target", ["Germany", "Israel Electric Corporation"])
def test_outlook_with_another_named_owner_is_not_a_sovereign_forward_opinion(target):
    text = "Moody's affirmed Israel's Baa1 long-term local and foreign-currency issuer ratings. The outlook is negative for " + target + "."
    rows = extract_rating_records(source(text), country_descriptor("IL"))
    assert rows and all(item["outlook"] == "unknown" and item["outlook_date"] is None for item in rows)


def test_watch_with_another_named_owner_is_not_transferred_to_the_sovereign():
    text = "Fitch affirmed Israel's Long-Term Foreign-Currency Issuer Default Rating at 'A'; Rating Watch Negative for Germany."
    rows = extract_rating_records(source(text, url="https://www.fitchratings.com/research/sovereigns/israel"), country_descriptor("IL"))
    assert rows and rows[0]["watch"] == "unknown"


@pytest.mark.parametrize("phrase,expected", [
    ("and placed the rating on Rating Watch Negative", "2026-01-30"),
    ("and maintained the existing Rating Watch Negative", None),
])
def test_watch_action_date_requires_explicit_placement_on_that_opinion(phrase, expected):
    text = "30 Jan 2026\n\nFitch Ratings affirmed Israel's Long-Term Foreign-Currency Issuer Default Rating at 'A' " + phrase + "."
    rows = extract_rating_records(source(text, url="https://www.fitchratings.com/research/sovereigns/israel", published_at=None), country_descriptor("IL"))
    assert rows and rows[0]["watch"] == "negative" and rows[0]["watch_date"] == expected


@pytest.mark.parametrize("text", [
    "Moody's affirmed Israel Electric Corporation's Baa1 long-term local and foreign-currency issuer ratings.",
    "Moody's affirmed Bank of Israel's Baa1 long-term local and foreign-currency issuer ratings.",
    "Moody's affirmed Insurance Company of Israel's Baa1 long-term local and foreign-currency issuer ratings.",
    "Moody's affirmed Example Holdings of Israel's Baa1 long-term local and foreign-currency issuer ratings.",
    "insurance company of Israel's Baa1 long-term local and foreign-currency issuer ratings.",
    "Moody's could affirm Israel's Baa1 long-term local and foreign-currency issuer ratings.",
    "Moody's previously affirmed Israel's Baa1 long-term local and foreign-currency issuer ratings.",
    "Moody's affirmed Israel's (P)Baa1 long-term local and foreign-currency issuer ratings.",
    "Moody's affirmed Israel's Long-Term Foreign-Currency Issuer Rating at 'Baa1(P)'.",
    "Moody's affirmed Israel's Long-Term Local-Currency Issuer Rating at 'A1' on the national scale.",
    "Moody's affirmed Israel's Baa1 short-term local and foreign-currency issuer ratings.",
    "Moody's affirmed Israel's Baa1 country ceiling.",
    "[Moody's affirmed Israel's Baa1 long-term local and foreign-currency issuer ratings.](https://ratings.moodys.com/unread)",
])
def test_company_conditional_ceiling_shortterm_and_unread_link_are_not_sovereign_facts(text):
    assert extract_rating_records(source(text), country_descriptor("IL")) == []


def test_local_foreign_and_unspecified_do_not_cross_copy_and_sp_slash_is_longterm_only():
    candidate = country_descriptor("IL")
    fitch = source("Fitch Ratings has affirmed Israel's Long-Term Foreign-Currency Issuer Default Rating (IDR) at 'A'. The Outlook is Negative.",
                   url="https://www.fitchratings.com/research/sovereigns/israel", title="Fitch Israel")
    rows = extract_rating_records(fitch, candidate)
    assert len(rows) == 1 and rows[0]["currency_basis"] == "foreign_currency" and rows[0]["outlook"] == "negative"
    sp = source("S&P Global Ratings affirmed its 'A/A-1' long- and short-term foreign and local currency sovereign credit ratings on Israel.",
                url="https://www.spglobal.com/ratings/israel", title="S&P Israel")
    rows = extract_rating_records(sp, candidate)
    assert {item["rating"] for item in rows} == {"A"}
    assert {item["currency_basis"] for item in rows} == {"foreign_currency", "local_currency"}
    unspecified = source("Moody's affirmed Israel's Baa1 long-term issuer ratings.")
    assert extract_rating_records(unspecified, candidate)[0]["currency_basis"] == "unknown"


def test_unverified_secondary_and_wrong_country_government_cannot_authorize_facts():
    candidate = country_descriptor("IL")
    for url in ("https://example.com/israel", "https://www.treasury.gov/israel"):
        assert extract_rating_records(source(url=url), candidate) == []
    assert extract_rating_records(source(discovery_only=True), candidate) == []
    assert extract_rating_records(source(), country_descriptor("US")) == []
    assert extract_rating_records(source(_licensed_api=True), candidate) == []


@pytest.mark.parametrize("name", ["Israel", "State of Israel", "Government of Israel"])
def test_whole_sovereign_subject_keeps_country_and_official_government_names(name):
    rows = extract_rating_records(source("Moody's affirmed " + name + "'s Baa1 long-term local and foreign-currency issuer ratings."), country_descriptor("IL"))
    assert len(rows) == 2 and all(item["entity_name"] == "Israel" for item in rows)


def test_territorial_issuer_is_not_relabelled_sovereign_without_explicit_agency_category():
    candidate = country_descriptor("PR")
    assert extract_rating_records(source("Moody's affirmed Puerto Rico's Ba1 long-term issuer ratings."), candidate) == []
    rows = extract_rating_records(source("Moody's affirmed Puerto Rico's Ba1 long-term sovereign credit ratings."), candidate)
    assert rows and rows[0]["scope"] == "sovereign"


def test_forged_record_and_future_dates_cannot_pass_validation():
    candidate = country_descriptor("IL")
    record = extract_rating_records(source(), candidate)[0]
    with pytest.raises(ValueError):
        normalize_observation({**record, "rating": "Aaa"}, candidate, source=source())
    with pytest.raises(ValueError):
        normalize_observation(record, {**candidate, "as_of_date": "2025-12-31"}, source=source())


def test_cache_only_nine_slots_publish_history_and_restart(environment):
    service, inventory, cache, store = environment
    candidate = inventory[0]
    initial = service.read(candidate)
    assert len(initial["ratings"]) == 9 and all(item["status"] == "not_checked" for item in initial["ratings"])
    accepted = service._accept_sources(candidate, [source()])
    assert len(accepted) == 2 and service.publish(candidate, accepted)
    context = service.read(candidate)
    assert row(context)["rating"] == row(context, basis="local_currency")["rating"] == "Baa1"
    assert row(context, basis="unknown")["rating"] is None
    assert len(context["rating_history"]) == 2
    assert all(event["event_type"] == "first_observation" and event["date_basis"] == "detected" and event["change_date"] is None for event in context["rating_history"])
    assert service.publish(candidate, accepted) is False
    assert service.read(candidate)["rating_history"] == context["rating_history"]
    restarted = SovereignRatingService(cache=lambda: cache, settings=lambda: {}, inventory=lambda: inventory,
        research_settings=lambda: {}, manual_store=lambda: store)
    assert restarted.read(candidate) == service.read(candidate)
    assert cache.get_security_snapshot("credit_ratings", candidate["country_key"], "credit-ratings-v1") is None


def test_manual_per_basis_cas_confidence_history_and_clear_restore(environment):
    service, inventory, _, _ = environment
    candidate = inventory[0]
    service.publish(candidate, service._accept_sources(candidate, [source()]))
    before = service.read(candidate)
    updated = service.save_manual(draft(before), {"username": "operator"})
    assert row(updated)["rating"] == "A3" and row(updated)["verification_status"] == "user_entered"
    assert row(updated, basis="local_currency")["rating"] == "Baa1"
    assert row(updated)["latest_change"]["event_type"] == "manual_added"
    assert row(updated, basis="local_currency")["latest_change"]["event_type"] == "first_observation"
    assert updated["manual_revisions"]["moodys:foreign_currency"] == 1
    with pytest.raises(HTTPException) as exc:
        service.save_manual(draft(before), {"username": "operator"})
    assert exc.value.status_code == 409
    cleared = service.clear_manual("IL", "moodys", "foreign_currency", 1, before["identity_token"], actor={"username": "operator"})
    assert row(cleared)["rating"] == "Baa1" and not row(cleared).get("manual_override")
    assert row(cleared)["latest_change"]["event_type"] == "manual_cleared"
    assert len(cleared["rating_history"]) == 4


@pytest.mark.parametrize("changes", [
    {"currency_basis": "USD"}, {"scope": "issuer"}, {"scale": "national"}, {"term": "short_term"},
    {"rating": "A+"}, {"entity_name": "Israel Electric Corporation"}, {"notes": ""},
    {"rating_date": "2099-01-01"}, {"expected_revision": True}, {"untrusted": "fact"},
    {"status": "unrated", "rating": "A3"}, {"outlook": "guess"},
])
def test_manual_rejects_unsupported_or_invalid_assertions(environment, changes):
    service, inventory, _, _ = environment
    with pytest.raises(HTTPException) as exc:
        service.save_manual(draft(service.read(inventory[0]), **changes), {"username": "operator"})
    assert exc.value.status_code == 422
    assert service.read(inventory[0])["rating_history"] == []


def test_identity_revision_and_open_scope_recheck_prevent_stale_publication(environment):
    service, inventory, _, _ = environment
    captured = deepcopy(inventory[0])
    accepted = service._accept_sources(captured, [source()])
    inventory[0]["country_aliases"].append("A changed trust boundary")
    assert service.publish(captured, accepted) is False
    with pytest.raises(HTTPException) as exc:
        service.save_manual(draft({**service.read(captured), "identity_token": "0" * 64}), {})
    assert exc.value.status_code == 409
    fresh = deepcopy(inventory[0])
    fresh["_position_scope"] = "open"
    inventory[0]["has_open_position"] = False
    assert service.publish(fresh, accepted) is False


def test_new_older_publication_never_rolls_back_known_grade(environment):
    service, inventory, _, _ = environment
    candidate = inventory[0]
    service.publish(candidate, service._accept_sources(candidate, [source()]))
    older = source(MOODYS.replace("Baa1", "A2"), published_at="2025-01-30", text_unused="")
    service.publish(candidate, service._accept_sources(candidate, [older]))
    assert row(service.read(candidate))["rating"] == "Baa1"


def test_country_dedup_and_account_scope_do_not_create_security_or_currency_copies(environment):
    service, inventory, _, _ = environment
    inventory.append(deepcopy(inventory[0]))
    assert [item["country_code"] for item in service.inventory("open")] == ["IL"]
    assert {item["country_code"] for item in service.inventory("all")} == {"IL", "US"}
    assert service.candidate("COUNTRY:US")["country_code"] == "US"


def test_auth_permissions_cache_only_reads_and_manual_writes(environment):
    service, _, _, _ = environment
    app = FastAPI()
    @app.middleware("http")
    async def auth(request, call_next):
        role = request.headers.get("x-test-role")
        if role:
            request.state.auth_user = {"role": role, "username": "test"}
        return await call_next(request)
    app.include_router(service.router())
    client = TestClient(app)
    assert client.get(PREFIX, params={"country_code": "IL"}).status_code == 401
    context = client.get(PREFIX, params={"country_code": "IL"}, headers={"x-test-role": "Viewer"}).json()
    assert client.put(PREFIX + "/manual", json=draft(context), headers={"x-test-role": "Viewer"}).status_code == 403
    assert client.put(PREFIX + "/manual", json=draft(context), headers={"x-test-role": "Operator"}).status_code == 200
    summary = client.get(PREFIX + "/summaries", params={"country_codes": "IL"}, headers={"x-test-role": "Viewer"})
    assert summary.status_code == 200 and summary.json()["items"][0]["country_code"] == "IL"
    assert client.get(PREFIX + "/catalog", headers={"x-test-role": "Viewer"}).status_code == 200
