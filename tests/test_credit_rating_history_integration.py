"""Independent history persistence, migration, projection and identity boundaries."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest
from app.credit_rating_service import CreditRatingService, SCHEMA
from app.local_portfolio import LocalPortfolioStore
from app.providers import SqliteCache

URL = "https://www.fitchratings.com/research/corporate-finance/synthetic-qa-observation"


CANDIDATE = {"security_key": "QACO|NYSE|USD", "symbol": "QACO", "stock_market": "NYSE", "currency": "USD",
    "asset_class": "EQUITY", "asset_sub_class": "STOCK", "name": "Synthetic QA Corporation",
    "issuer_name": "Synthetic QA Corporation", "issuer_identity_verified": True, "has_open_position": True}


@pytest.fixture
def env(tmp_path):
    cache = SqliteCache(tmp_path / "market.sqlite", ttl_hours=24)
    store = LocalPortfolioStore(tmp_path / "portfolio.sqlite")
    inventory = [deepcopy(CANDIDATE)]
    service = CreditRatingService(cache=lambda: cache, settings=lambda: {"verification_ttl_days": 30},
        inventory=lambda: inventory, research_settings=lambda: {"search_provider": "auto", "max_web_calls": 8},
        manual_store=lambda: store)
    return service, inventory[0], inventory, cache, store


def observation(candidate, grade="A", *, day="2026-01-01", url=URL, outlook="stable", watch="none", **changes):
    fetched = datetime.now(timezone.utc).isoformat()
    quote = f"Synthetic QA data: {candidate['issuer_name']} issuer rating {grade}; Outlook {outlook}; Watch {watch}; action date {day or 'unspecified'}."
    return {"agency": "fitch", "status": "rated", "rating": grade, "scope": "issuer", "scale": "global",
        "term": "long_term", "rating_type": "issuer_default", "entity_name": candidate["issuer_name"],
        "outlook": outlook, "watch": watch, "rating_date": day, "outlook_date": None, "watch_date": None,
        "observed_at": day, "fetched_at": fetched, "source_url": url, "source_kind": "agency_public",
        "primary_eligible": True, "action_type": "rating_action", "sources": [{"url": url, "title": "Synthetic QA evidence", "evidence_quote": quote,
            "fetched_at": fetched, "source_kind": "agency_public"}], **changes}


def history(service, candidate):
    context = service.read(candidate)
    assert isinstance(context.get("rating_history"), list), "History missing from cache-only full context"
    return context["rating_history"]


def fitch(service, candidate):
    return next(r for r in service.read(candidate)["ratings"] if r["agency"] == "fitch")


def event(service, candidate, kind):
    rows = [r for r in history(service, candidate) if r.get("event_type") == kind]
    assert len(rows) == 1, (kind, rows)
    return rows[0]


def test_summary_retains_compact_change_without_full_evidence_history(env):
    service,candidate,_,_,_=env
    service.publish(candidate,[observation(candidate)])
    service.publish(candidate,[observation(candidate,"BBB+",day="2026-02-02")])
    summary=service.summaries([candidate["security_key"]])["items"][0]
    assert "rating_history" not in summary
    row=next(r for r in summary["ratings"] if r["agency"]=="fitch")
    assert row["latest_change"]["previous_rating"]=="A" and row["latest_change"]["new_rating"]=="BBB+"
    assert "evidence_quote" not in json.dumps(summary)


def test_two_service_instances_deduplicate_same_public_fact_and_manual_conflicts_atomically(env):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi import HTTPException
    service,candidate,inventory,cache,store=env
    other=CreditRatingService(cache=lambda:SqliteCache(cache.path,ttl_hours=24),settings=lambda:{},inventory=lambda:inventory,
        research_settings=lambda:{},manual_store=lambda:LocalPortfolioStore(store.path))
    same=observation(candidate)
    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(lambda target:target.publish(candidate,[deepcopy(same)]),(service,other)))
    assert len(history(service,candidate))==1
    ctx=service.read(candidate)
    payload={'security_key':candidate['security_key'],'agency':'fitch','status':'rated','rating':'BBB+',
        'entity_name':candidate['issuer_name'],'expected_identity':ctx['identity_token'],'expected_revision':0,'notes':'Synthetic concurrency QA'}
    def save(target):
        try:
            target.save_manual(deepcopy(payload),{'username':'qa-concurrent'});return 200
        except HTTPException as error:return error.status_code
    with ThreadPoolExecutor(max_workers=2) as workers:
        results=list(workers.map(save,(service,other)))
    assert sorted(results)==[200,409]
    assert len([row for row in history(service,candidate) if row['event_type']=='manual_added'])==1


def test_existing_cached_grade_migrates_on_next_write_and_get_remains_read_only(env):
    from app.credit_rating_service import _binding
    service,candidate,_,cache,store=env
    original=observation(candidate)
    seeded={'schema_version':SCHEMA,'_binding':_binding(candidate),'observations':[original],
        'provider_status':[],'attempts':{},'fetched_at':original['fetched_at']}
    cache.set_security_snapshot('credit_ratings',candidate['security_key'],SCHEMA,deepcopy(seeded))
    before=store.export_data()['data']['app_preferences']
    assert fitch(service,candidate)['rating']=='A' and history(service,candidate)==[]
    assert store.export_data()['data']['app_preferences']==before
    assert cache.get_security_snapshot('credit_ratings',candidate['security_key'],SCHEMA)==seeded
    service.publish(candidate,[observation(candidate,'A-',day='2026-02-02')])
    changed=event(service,candidate,'rating_change')
    assert (changed['previous_rating'],changed['new_rating'])==('A','A-')
    first=event(service,candidate,'first_observation')
    assert first['new_rating']=='A' and first['sources'][0]['evidence_quote']==original['sources'][0]['evidence_quote']


def test_same_symbol_other_market_currency_never_shares_history(env):
    service,candidate,inventory,_,_=env
    alternate={**candidate,'stock_market':'TASE','currency':'ILS','security_key':'QACO|TASE|ILS'}
    inventory.append(alternate)
    service.publish(candidate,[observation(candidate)])
    assert history(service,alternate)==[] and fitch(service,alternate)['status']=='not_checked'
    service.publish(alternate,[observation(alternate,'BBB+')])
    assert event(service,candidate,'first_observation')['new_rating']=='A'
    assert event(service,alternate,'first_observation')['new_rating']=='BBB+'
    assert event(service,candidate,'first_observation')['event_id']!=event(service,alternate,'first_observation')['event_id']


def test_undated_source_conflict_does_not_invent_grade_change_and_resolution_is_noop(env):
    service,candidate,_,_,_=env
    service.publish(candidate,[observation(candidate,day=None)])
    first=event(service,candidate,'first_observation')
    service.publish(candidate,[observation(candidate,'BBB',day=None,url=URL+'-conflicting')])
    assert fitch(service,candidate)['status']=='conflicting' and fitch(service,candidate)['rating'] is None
    assert not [row for row in history(service,candidate) if row['event_type']=='rating_change']
    service.publish(candidate,[observation(candidate,'A',day=None,url=URL+'-conflicting')])
    assert fitch(service,candidate)['rating']=='A'
    assert len(history(service,candidate))==1 and fitch(service,candidate)['latest_change']['event_id']==first['event_id']


def test_full_observation_cache_does_not_discard_newly_verified_grade_change(env):
    service,candidate,_,_,_=env
    # Bounded current evidence may evict old source rows, but the next verified
    # current opinion and its prior/new history transition must remain visible.
    old=[observation(candidate,url=URL+'-'+str(index)) for index in range(150)]
    service.publish(candidate,old)
    assert fitch(service,candidate)['rating']=='A'
    changed=observation(candidate,'BBB+',day='2026-10-10',url=URL+'-new-current')
    assert service.publish(candidate,[changed])
    assert fitch(service,candidate)['rating']=='BBB+'
    event_row=event(service,candidate,'rating_change')
    assert (event_row['previous_rating'],event_row['new_rating'])==('A','BBB+')
