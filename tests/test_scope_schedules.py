"""Per-scope schedule persistence, migration and scheduler reconciliation."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from types import SimpleNamespace

from app import main
from test_scheduling import schedule_environment

ENDPOINT = '/api/settings/ai-enrichment-schedule'


def save(client, session, scope, **changes):
    return client.put(ENDPOINT, headers={'X-CSRF-Token': session['csrf_token']},
                      json={'position_scope': scope, 'enabled': True, **changes})


def indexed(response):
    return {item['position_scope']: item for item in response.json()['items']}


def test_scope_updates_preserve_other_settings_and_exclude_private_owner(schedule_environment):
    client, auth, session, path = schedule_environment
    first = save(client, session, 'open', timezone='Asia/Jerusalem', language='he',
                 schedule_config={'frequency': 'weekly', 'hour': 8, 'minute': 10, 'weekdays': [0, 3]})
    assert first.status_code == 200
    before = indexed(first)['open']
    second = save(client, session, 'all', timezone='America/New_York', language='en',
                  schedule_config={'frequency': 'monthly', 'hour': 20, 'minute': 15, 'month_days': [1, 15]})
    assert second.status_code == 200
    assert indexed(second)['open'] == before
    assert all('owner_id' not in row for row in indexed(second).values())
    assert 'owner_id' not in second.json()
    disk = json.loads((path / 'settings.json').read_text())
    assert set(disk['ai_enrichment_schedules']) == {'open', 'all'}
    assert disk['ai_enrichment_schedules']['open']['owner_id'] == auth.list_users()[0]['id']
    assert client.get(ENDPOINT).json()['position_scope'] == 'all'  # Singleton compatibility.
    assert client.get(ENDPOINT, params={'position_scope': 'open'}).json()['schedule_config'] == before['schedule_config']
    assert client.get(ENDPOINT, params={'position_scope': 'invalid'}).status_code == 400
    # Disable only open; the all cadence survives both partial update and reload.
    assert save(client, session, 'open', enabled=False).status_code == 200
    rows = indexed(client.get(ENDPOINT))
    assert rows['open']['enabled'] is False
    assert rows['all']['enabled'] is True
    assert rows['all']['schedule_config']['frequency'] == 'monthly'


def test_legacy_all_schedule_is_not_copied_to_open(schedule_environment):
    client, auth, session, path = schedule_environment
    legacy = {'enabled': True, 'position_scope': 'all', 'timezone': 'UTC',
              'owner_id': auth.list_users()[0]['id'], 'language': 'he',
              'schedule_config': {'frequency': 'hourly', 'interval': 3, 'minute': 5}}
    (path / 'settings.json').write_text(json.dumps({'ai_enrichment_schedule': legacy}))
    rows = indexed(client.get(ENDPOINT))
    assert rows['all']['enabled'] is True and rows['all']['schedule_config']['interval'] == 3
    assert rows['open']['enabled'] is False
    assert save(client, session, 'open', timezone='Asia/Jerusalem').status_code == 200
    migrated = json.loads((path / 'settings.json').read_text())['ai_enrichment_schedules']
    assert migrated['all']['owner_id'] == legacy['owner_id']
    assert migrated['all']['language'] == 'he'
    assert migrated['all']['schedule_config'] == main.normalize_schedule(legacy['schedule_config'])
    # An authoritative empty collection does not resurrect a stale legacy row.
    main.save_runtime_settings({'ai_enrichment_schedules': {}, 'ai_enrichment_schedule': legacy})
    assert not any(row['enabled'] for row in indexed(client.get(ENDPOINT)).values())


def test_concurrent_scope_saves_keep_both_rows(schedule_environment):
    client, auth, session, path = schedule_environment
    ready = Barrier(2)
    def write(scope, hour):
        ready.wait()
        return save(client, session, scope, schedule_config={'frequency': 'daily', 'hour': hour, 'minute': 0})
    with ThreadPoolExecutor(max_workers=2) as workers:
        requests = [workers.submit(write, 'open', 4), workers.submit(write, 'all', 19)]
        assert all(request.result().status_code == 200 for request in requests)
    rows = indexed(client.get(ENDPOINT))
    assert rows['open']['schedule_config']['hour'] == 4
    assert rows['all']['schedule_config']['hour'] == 19
    assert all(row['enabled'] for row in rows.values())


def test_two_jobs_preserve_separate_scope_timezone_and_callback(schedule_environment, monkeypatch):
    client, auth, session, path = schedule_environment
    registered = {main.AI_ENRICHMENT_JOB_ID: 'legacy'}
    class Scheduler:
        def remove_job(self, identifier): registered.pop(identifier, None)
        def add_job(self, callback, trigger, **kwargs):
            registered[kwargs['id']] = (callback, trigger, kwargs)
        def get_job(self, identifier): return None
    monkeypatch.setattr(main, 'scheduler', Scheduler())
    assert save(client, session, 'open', timezone='Asia/Jerusalem').status_code == 200
    assert save(client, session, 'all', timezone='America/New_York',
                schedule_config={'frequency': 'monthly', 'month_days': [31], 'hour': 12, 'minute': 0}).status_code == 200
    assert set(registered) == {main.ai_enrichment_job_id('open'), main.ai_enrichment_job_id('all')}
    for scope, zone in [('open', 'Asia/Jerusalem'), ('all', 'America/New_York')]:
        callback, trigger, options = registered[main.ai_enrichment_job_id(scope)]
        assert callback is main.run_scheduled_ai_enrichment
        assert options['args'] == [scope] and options['max_instances'] == 1 and options['coalesce']
        assert str(trigger.timezone) == zone
    assert save(client, session, 'open', enabled=False).status_code == 200
    assert set(registered) == {main.ai_enrichment_job_id('all')}


def test_next_run_status_is_per_scope(schedule_environment, monkeypatch):
    client, auth, session, path = schedule_environment
    first, second = datetime(2026, 12, 1, 8, tzinfo=timezone.utc), datetime(2027, 1, 1, 8, tzinfo=timezone.utc)
    jobs = {main.ai_enrichment_job_id('open'): SimpleNamespace(next_run_time=first),
            main.ai_enrichment_job_id('all'): SimpleNamespace(next_run_time=second)}
    monkeypatch.setattr(main, 'scheduler', SimpleNamespace(get_job=lambda identifier: jobs.get(identifier)))
    rows = indexed(client.get(ENDPOINT))
    assert rows['open']['next_run'] == first.isoformat()
    assert rows['all']['next_run'] == second.isoformat()


def test_callback_reads_current_scope_owner_and_honors_disablement(schedule_environment, monkeypatch):
    client, auth, session, path = schedule_environment
    assert save(client, session, 'open', language='he').status_code == 200
    assert save(client, session, 'all', language='en').status_code == 200
    calls = []
    def start(owner, credentials, language, scope, **kwargs):
        calls.append((owner, language, scope))
    monkeypatch.setattr(main.portfolio_ai_research, 'start', start)
    main.run_scheduled_ai_enrichment('open')
    main.run_scheduled_ai_enrichment('all')
    assert [(row[1], row[2]) for row in calls] == [('he', 'open'), ('en', 'all')]
    assert save(client, session, 'open', enabled=False).status_code == 200
    main.run_scheduled_ai_enrichment('open')
    assert len(calls) == 2
