"""Financial evidence recovery must preserve independent facts conservatively."""
from copy import deepcopy

from app.security_source_context import context_records
from app.security_web_research import recover_context_proposal, validate_proposals
from test_enrichment_mixed_batch_qa import TASE_KEY, mixed_candidates
from test_security_source_context import TASE, URL


def fetched(text=TASE, *, source_id="source-qa-primary", url=URL):
    return {"url": url, "source_id": source_id, "text": text,
            "retrieved_at": "2026-11-07T12:00:00+00:00"}


def selected_records(proposal, evidence, candidate):
    selected = {(entry["source_id"], entry["record_id"]) for entry in proposal["records"]}
    return [record for source in evidence for record in context_records(source, candidate)
            if (source["source_id"], record["record_id"]) in selected]


def test_industry_only_recovery_uses_fetched_source_and_omits_known_name_and_price():
    candidate = mixed_candidates()[1]
    evidence = [fetched()]
    proposal = recover_context_proposal({TASE_KEY: candidate}, {TASE_KEY: evidence})
    records = selected_records(proposal, evidence, candidate)
    assert [(record["kind"], record.get("field"), record.get("value")) for record in records] == [
        ("profile", "industry", "ריאלי - מסחר ושרותים - תקשורת ומדיה")]
    assert proposal["observations"] == proposal["profiles"] == []
    verified = validate_proposals(proposal, {TASE_KEY: candidate}, {TASE_KEY: evidence})
    assert verified[TASE_KEY]["rejected"] is False
    assert verified[TASE_KEY]["observations"] == []
    assert [item["field"] for item in verified[TASE_KEY]["profiles"]] == ["industry"]


def test_conflicting_industries_are_not_recovered_from_either_full_source():
    candidate = mixed_candidates()[1]
    evidence = [fetched(), fetched(TASE.replace("ריאלי - מסחר ושרותים - תקשורת ומדיה", "ריאלי - טכנולוגיה"),
                                  source_id="source-qa-alternate", url=URL.removesuffix("/major_data"))]
    assert all(any(record.get("field") == "industry" for record in context_records(source, candidate)) for source in evidence)
    proposal = recover_context_proposal({TASE_KEY: candidate}, {TASE_KEY: evidence})
    assert proposal == {"records": [], "observations": [], "profiles": []}


def test_conflicting_prices_do_not_discard_matching_industry():
    # This oracle requires ordinary-share price evidence. The production-shaped
    # mixed batch fixture is RSU, whose context contract permits profiles only.
    candidate = {**mixed_candidates()[1], "asset_class": "STOCK", "missing_fields": ["prices", "profile"]}
    evidence = [fetched(), fetched(TASE.replace("**2,901**", "**2,902**"),
                                  source_id="source-qa-alternate", url=URL.removesuffix("/major_data"))]
    assert all(any(record["kind"] == "price" for record in context_records(source, candidate)) for source in evidence)
    proposal = recover_context_proposal({TASE_KEY: candidate}, {TASE_KEY: evidence})
    records = selected_records(proposal, evidence, candidate)
    assert [(record["kind"], record.get("field")) for record in records] == [("profile", "industry")]
    verified = validate_proposals(proposal, {TASE_KEY: candidate}, {TASE_KEY: evidence})
    assert verified[TASE_KEY]["observations"] == []
    assert verified[TASE_KEY]["profiles"][0]["value"] == "ריאלי - מסחר ושרותים - תקשורת ומדיה"


def test_recovery_never_trusts_supplied_context_records_or_cross_security_evidence():
    candidates = mixed_candidates()
    candidate = candidates[1]
    fake = fetched("Loading market information")
    fake["context_records"] = context_records(fetched(), candidate)
    assert fake["context_records"], "The adversarial forged record fixture must be nonempty"
    wrong = fetched(TASE.replace("1101534", "9999999"), source_id="source-qa-other-security",
                    url=URL.replace("1101534", "9999999"))
    proposal = recover_context_proposal({item["security_key"]: item for item in candidates},
                                       {TASE_KEY: [fake, wrong], candidates[0]["security_key"]: [fetched()]})
    assert proposal == {"records": [], "observations": [], "profiles": []}


def test_recovered_selection_is_revalidated_against_authoritative_source_text():
    candidate = mixed_candidates()[1]
    evidence = [fetched()]
    proposal = recover_context_proposal({TASE_KEY: candidate}, {TASE_KEY: evidence})
    changed_evidence = deepcopy(evidence)
    changed_evidence[0]["text"] = "Loading market information"
    verified = validate_proposals(proposal, {TASE_KEY: candidate}, {TASE_KEY: changed_evidence})
    assert verified[TASE_KEY]["rejected"] is True
    assert verified[TASE_KEY]["observations"] == verified[TASE_KEY]["profiles"] == []
