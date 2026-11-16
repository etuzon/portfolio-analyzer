"""Bounded, contiguous windows retain immutable full validation context."""
import pytest

from app.security_research_tools import ResearchFailure, ResearchSession, WebRequestBudget


CANDIDATE = {"security_key": "example", "symbol": "EXAMPLE", "name": "Example Company"}


def research(fetch):
    return ResearchSession({}, WebRequestBudget(8), fetch=fetch,
        resolver=lambda *_a, **_k: [(2, 1, 6, "", ("93.184.216.34", 443))])


def register(session, url="https://example.org/report"):
    return session._add(CANDIDATE["security_key"], url, "Example Company annual report")


def test_later_section_is_contiguous_and_reuses_the_original_source_snapshot():
    text = "Example Company\nPublished: 01/10/2026\n" + ("Unrelated report text.\n" * 3000)
    text += "Geographic distribution as of 30/09/2026\nCountry | Percentage\nUS | 98.9%\nCanada | 1.1%\n"
    calls = []
    session = research(lambda url, _s: calls.append(url) or {"url": url, "text": text})
    source_id = register(session)
    initial = session.read(CANDIDATE, source_id)
    assert "98.9%" not in initial["text"]
    assert len(initial["text"]) == 40000
    assert initial["document_window"]["truncated"] is True
    section = session.read(CANDIDATE, source_id, query="Geographic distribution")
    start, end = section["document_window"]["start"], section["document_window"]["end"]
    assert start > 40000 and section["text"] == text[start:end]
    assert "Country | Percentage\nUS | 98.9%\nCanada | 1.1%" in section["text"]
    assert "Published:" not in section["text"]
    assert section["document_context"]["opening_text"].startswith("Example Company\nPublished:")
    assert section["document_id"] == initial["document_id"]
    assert section["evidence_id"] != initial["evidence_id"]
    assert section["retrieved_at"] == initial["retrieved_at"]
    assert section["cached_document"] is True and calls == ["https://example.org/report"]
    assert session.budget.used == 2 and session.diagnostics["source_requests"] == 2
    full = session.validation_source(CANDIDATE, source_id, section["document_id"])
    assert full["text"] == text.rstrip("\n") and session.budget.used == 2


def test_long_single_line_cannot_move_a_query_back_before_its_window():
    text = "Example Company\n" + "x" * 75000 + "Later table US 98.9%"
    session = research(lambda url, _s: {"url": url, "text": text})
    section = session.read(CANDIDATE, register(session), query="Later table")
    assert "Later table US 98.9%" in section["text"]
    assert section["document_window"]["start"] > 70000
    assert len(section["text"]) <= 40000


def test_offset_pages_and_next_occurrences_use_absolute_source_positions():
    text = "Example Company\n" + "First TARGET\n" + "padding\n" * 9000 + "Second target\n"
    session = research(lambda url, _s: {"url": url, "text": text})
    source_id = register(session)
    first = session.read(CANDIDATE, source_id, query="target")
    second = session.read(CANDIDATE, source_id, query="TARGET", offset=first["document_window"]["match_end"])
    assert "Second target" in second["text"]
    assert second["document_window"]["match_start"] == text.rindex("target")
    page = session.read(CANDIDATE, source_id, offset=first["document_window"]["next_offset"])
    assert page["document_window"]["start"] == 40000
    assert page["text"] == text.rstrip("\n")[40000:80000]


def test_full_validation_source_is_bound_to_candidate_source_and_session():
    session = research(lambda url, _s: {"url": url, "text": "Example Company public report"})
    source_id = register(session)
    window = session.read(CANDIDATE, source_id)
    other_id = register(session, "https://example.org/other")
    for candidate, source, document in [({**CANDIDATE, "security_key": "other"}, source_id, window["document_id"]),
            (CANDIDATE, other_id, window["document_id"]), (CANDIDATE, source_id, "invented")]:
        with pytest.raises(ResearchFailure):
            session.validation_source(candidate, source, document)
    other = research(lambda *_a: pytest.fail("No network is permitted for validation"))
    with pytest.raises(ResearchFailure):
        other.validation_source(CANDIDATE, source_id, window["document_id"])
    assert session.budget.used == 1


def test_explicit_refresh_preserves_old_snapshot_and_reader_choice_can_fetch_another():
    replies, calls = iter(["Original qualification", "Changed qualification", "Compatible qualification"]), []
    session = research(lambda url, settings: calls.append(settings.get("reader")) or {"url": url, "text": next(replies)})
    source_id = register(session)
    first = session.read(CANDIDATE, source_id)
    second = session.read(CANDIDATE, source_id)
    assert first["document_id"] != second["document_id"]
    assert session.validation_source(CANDIDATE, source_id, first["document_id"])["text"] == "Original qualification"
    assert session.read(CANDIDATE, source_id, query="Changed")["document_id"] == second["document_id"]
    third = session.read(CANDIDATE, source_id, reader="compatible", query="Compatible")
    assert third["cached_document"] is False
    assert calls == [None, None, "compatible"] and session.budget.used == 4


def test_cached_reference_keeps_its_actual_fetch_time_and_status():
    stamp = "2026-01-01T12:00:00+00:00"
    session = research(lambda url, _s: {"url": url, "text": "Official country reference",
        "retrieved_at": stamp, "reader": "official_reference", "reference_cache_status": "refresh_failed_using_saved"})
    source_id = register(session)
    first = session.read(CANDIDATE, source_id, query="country")
    second = session.read(CANDIDATE, source_id, offset=0)
    assert first["retrieved_at"] == second["retrieved_at"] == stamp
    assert second["reader"] == "official_reference"
    assert second["reference_cache_status"] == "refresh_failed_using_saved"


def test_retained_memory_limit_refuses_new_documents_without_evicting_validation():
    replies = iter(["a" * 800000, "b" * 800000, "c" * 800000])
    session = research(lambda url, _s: {"url": url, "text": next(replies)})
    first_id = register(session)
    first = session.read(CANDIDATE, first_id)
    session.read(CANDIDATE, register(session, "https://example.org/two"))
    with pytest.raises(ResearchFailure) as error:
        session.read(CANDIDATE, register(session, "https://example.org/three"))
    assert error.value.code == "source_limit"
    assert session._document_bytes == 1600000
    assert len(session.validation_source(CANDIDATE, first_id, first["document_id"])["text"]) == 800000


def test_per_document_size_is_bytes_and_over_limit_never_yields_partial_validation():
    session = research(lambda url, _s: {"url": url, "text": "א" * 500001})
    with pytest.raises(ResearchFailure) as error:
        session.read(CANDIDATE, register(session))
    assert error.value.code == "source_limit"
    assert session._document_bytes == 0 and session.evidence(CANDIDATE) == []


def test_missing_section_still_consumes_an_operation_without_refetching():
    calls = []
    session = research(lambda url, _s: calls.append(url) or {"url": url, "text": "Example Company"})
    source_id = register(session)
    session.read(CANDIDATE, source_id)
    for _ in range(7):
        with pytest.raises(ResearchFailure) as error:
            session.read(CANDIDATE, source_id, query="absent")
        assert error.value.code == "source_section_not_found"
    with pytest.raises(ResearchFailure):
        session.read(CANDIDATE, source_id, offset=0)
    assert session.budget.used == 8 and len(calls) == 1


@pytest.mark.parametrize("query,offset", [(" ", None), ("x" * 201, None), (1, None), (None, True), (None, -1), (None, 1000001)])
def test_invalid_section_arguments_fail_before_network(query, offset):
    session = research(lambda *_a: pytest.fail("Invalid arguments must not fetch"))
    with pytest.raises(ResearchFailure) as error:
        session.read(CANDIDATE, register(session), query=query, offset=offset)
    assert error.value.code == "invalid_request" and session.budget.used == 0
