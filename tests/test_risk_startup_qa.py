"""Independent startup acceptance: real auth, raw holdings and a contended cache.

Only the public network boundary is replaced. No financial evidence is created
and no planner is invoked. Every store belongs to the temporary test directory.
"""
import sqlite3
import time
from threading import Event, Lock
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth import AuthStore
from app.local_portfolio import LocalPortfolioStore
from app.providers import MarketDataHub, SqliteCache

PATH = '/api/securities/enrichment/ai'


def _login(auth, suffix, role='Operator'):
    username = 'startup-qa-' + suffix
    initial, changed = 'Synthetic-Initial-2026!', 'Synthetic-Changed-2026!'
    auth.create_user({'username': username, 'first_name': 'Synthetic', 'last_name': 'QA',
                      'role': role, 'password': initial})
    client = TestClient(main.app, base_url='https://localhost:6443')
    response = client.post('/api/auth/login', json={'username': username, 'password': initial})
    assert response.status_code == 200
    response = client.post('/api/auth/change-password',
        headers={'X-CSRF-Token': response.json()['csrf_token']},
        json={'current_password': initial, 'new_password': changed, 'confirm_password': changed})
    assert response.status_code == 200
    return client, {'X-CSRF-Token': response.json()['csrf_token']}


@pytest.fixture
def startup_env(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / 'portfolio.sqlite')
    auth = AuthStore(store.path)
    auth.initialize()
    cache = SqliteCache(tmp_path / 'market.sqlite', ttl_hours=24)
    real_connect = sqlite3.connect
    def bounded_cache_connect(path, *args, **kwargs):
        if str(path) == str(cache.path):
            kwargs['timeout'] = .03
        return real_connect(path, *args, **kwargs)
    monkeypatch.setattr(sqlite3, 'connect', bounded_cache_connect)
    market = MarketDataHub({})
    market.cache = cache
    market.providers = [SimpleNamespace(name='qa_saved_profile')]
    saved_profile = {'name': 'Synthetic Saved Issuer Corporation', 'website': 'https://synthetic.qa.example'}
    cache.set_security_snapshot('qa_saved_profile', 'SQA1', 'profile', saved_profile)
    monkeypatch.setattr(main, 'local_store', store)
    monkeypatch.setattr(main, 'auth_store', auth)
    monkeypatch.setattr(main, 'hub', lambda: market)
    monkeypatch.setattr(main, '_record_log', lambda *a, **k: None)
    # Country follow-up is outside this startup reproduction and must not call AI.
    monkeypatch.setattr(main.portfolio_ai_research, 'country_inventory_reader', lambda *a, **k: [])
    monkeypatch.setattr(main, '_enrichment_assistant_settings', lambda: {'research_concurrency': 5})
    # Analytics are deliberately unavailable: risk inventory must not run them.
    def unavailable_analytics(*a, **k):
        raise sqlite3.OperationalError('synthetic market analytics unavailable')
    monkeypatch.setattr(main, 'enriched_local_holdings', unavailable_analytics)
    accounts = [store.save_account({'type': 'Investment', 'location': 'USA', 'currency': 'USD',
        'username': name, 'initial_cash': 10000, 'persons': [{'name': 'Synthetic', 'birth_date': '01/01/1990'}]})
        for name in ('One', 'Two')]
    def transaction(symbol, action='BUY', market='NYSE', currency='USD', asset='EQUITY', owner=0):
        store.add_transaction({'account_db_id': accounts[owner]['id'], 'action': action, 'symbol': symbol,
            'stock_market': market, 'currency': currency, 'asset_class': asset, 'quantity': 2,
            'price_input': 10, 'trade_date': '2026-01-02' if action == 'SELL' else '2026-01-01', 'allow_manual': True})
    for symbol in ('SQA1', 'SQA2', 'SQA3', 'SQA4', 'SQA5'):
        transaction(symbol)
    transaction('SQASHORT', action='SHORT')
    transaction('SQA1', owner=1)  # Same listing across accounts counts once.
    transaction('SQA1', market='NASDAQ')  # Same ticker on another venue is distinct.
    transaction('SQACLOSED'); transaction('SQACLOSED', action='SELL')
    transaction('SQAPRIVATE', market='PRIVATE')
    transaction('SQAFUND', asset='ETF')
    store.save_manual_security({'symbol': 'SQAUNHELD', 'stock_market': 'NYSE', 'currency': 'USD',
        'asset_class': 'EQUITY', 'name': 'Synthetic unheld', 'location': 'USA'})
    for name in ('portfolio_ai_research', 'risk_input_retrieval', 'risk_evidence_jobs'):
        getattr(main, name)._jobs.clear()
    main._login_failures.clear()
    client, headers = _login(auth, 'owner')
    release, five_arrived = Event(), Event()
    lock = Lock()
    observed = []
    active = [0, 0]
    def public_api(candidate):
        with lock:
            observed.append(candidate['security_key'])
            active[0] += 1
            active[1] = max(active[1], active[0])
            if active[0] == 5:
                five_arrived.set()
        try:
            assert release.wait(12), 'QA did not release synthetic public API boundary'
            return {'records': [], 'sources': [], 'requests': 1, 'status': 'unavailable', 'code': 'data_unavailable'}
        finally:
            with lock:
                active[0] -= 1
    monkeypatch.setattr(main.risk_evidence_research.api_sources, 'fetch', public_api)
    expected = {symbol + '|NYSE|USD' for symbol in ('SQA1', 'SQA2', 'SQA3', 'SQA4', 'SQA5', 'SQASHORT', 'SQAFUND')}
    expected.add('SQA1|NASDAQ|USD')
    env = SimpleNamespace(store=store, auth=auth, cache=cache, client=client, headers=headers,
        release=release, arrived=five_arrived, observed=observed, active=active, expected=expected, saved_profile=saved_profile)
    yield env
    release.set()
    # Ensure all workers finish before pytest rolls back monkeypatches.
    deadline = time.monotonic() + 15
    while any(job['status'] in {'queued', 'running'} for job in main.portfolio_ai_research._jobs.values()) and time.monotonic() < deadline:
        time.sleep(.02)


def _terminal(env, identifier):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        response = env.client.get(PATH + '/' + identifier)
        assert response.status_code == 200
        job = response.json()
        if job['status'] not in {'queued', 'running'}:
            return job
        time.sleep(.02)
    pytest.fail('Risk startup did not reach terminal status')


@pytest.mark.parametrize('scope', ['open', 'all'])
def test_risk_only_reaches_five_real_children_with_market_writer(startup_env, scope):
    env = startup_env
    writer = sqlite3.connect(env.cache.path)
    writer.execute('begin exclusive')
    writer.execute("insert into cache values ('qa-held-writer', ?, '{}')", (time.time(),))
    identifier = None
    try:
        response = env.client.post(PATH, headers=env.headers, json={
            'data_types': ['risk_inputs'], 'risk_mode': 'api', 'position_scope': scope, 'refresh_policy': 'missing'})
        assert response.status_code == 202, response.text
        identifier = response.json()['request_id']
        if not env.arrived.wait(10):
            failed = env.client.get(PATH + '/' + identifier).json()
            pytest.fail(str({'status': failed.get('status'), 'failure': failed.get('failure'),
                             'progress': failed.get('progress'), 'observed': env.observed}))
        running = env.client.get(PATH + '/' + identifier).json()
        expected = env.expected | ({'SQACLOSED|NYSE|USD', 'SQAUNHELD|NYSE|USD'} if scope == 'all' else set())
        assert running['risk_inputs']['progress']['total'] == len(expected)
        assert {row['security_key'] for row in running['risk_inputs']['outcomes']} == expected
        assert running['progress']['stage'] == 'researching_risk_inputs'
        assert env.active[1] == 5
        retained = next(row for row in main.stress_risk_inputs.inventory() if row['security_key'] == 'SQA1|NYSE|USD')
        assert retained['issuer_name'] == env.saved_profile['name']
        assert retained['issuer_identity_verified'] is True
        assert env.cache.get_security_snapshot('qa_saved_profile', 'SQA1', 'profile') == env.saved_profile
        assert running['outcomes'] == []
        assert running['credit_ratings']['outcomes'] == []
    finally:
        writer.rollback()
        writer.close()
        env.release.set()
    if identifier:
        result = _terminal(env, identifier)
        assert result['status'] == 'completed', result.get('failure')
        assert set(env.observed) == expected
        assert all(row['missing_fields'] for row in result['risk_inputs']['outcomes'])
        assert all(row['status'] == 'unavailable' for row in result['risk_inputs']['outcomes'])


def test_risk_start_auth_and_request_ownership(startup_env):
    env = startup_env
    payload = {'data_types': ['risk_inputs'], 'risk_mode': 'api'}
    anonymous = TestClient(main.app, base_url='https://localhost:6443')
    assert anonymous.post(PATH, json=payload).status_code == 401
    viewer, viewer_headers = _login(env.auth, 'viewer', role='Viewer')
    assert viewer.post(PATH, headers=viewer_headers, json=payload).status_code == 403
    assert env.client.post(PATH, json=payload).status_code == 403
    response = env.client.post(PATH, headers=env.headers, json=payload)
    assert response.status_code == 202
    identifier = response.json()['request_id']
    other, _ = _login(env.auth, 'other')
    assert other.get(PATH + '/' + identifier).status_code == 404
    assert other.get(PATH + '/' + identifier + '/diagnostics').status_code == 404
    env.release.set()
    assert _terminal(env, identifier)['status'] == 'completed'
