"""Scenario evidence is coherent, read-only and preserves unknown inputs."""
from copy import deepcopy
from datetime import datetime, timezone
import time

from fastapi.testclient import TestClient
import pytest

from app import main, risk_history, risk_scenarios
from app.auth import AuthStore
from app.local_portfolio import LocalPortfolioStore


def raw_inputs():
    accounts = [
        {'id': 'investment', 'type': 'Investment', 'currency': 'USD', 'initial_cash': 40},
        {'id': 'bank', 'type': 'Bank', 'currency': 'ILS', 'initial_cash': -20},
        {'id': 'savings', 'type': 'Long-Term Savings', 'currency': 'ILS', 'initial_cash': 0},
        {'id': 'esop', 'type': 'ESOP', 'currency': 'GBP', 'initial_cash': None},
    ]
    items = [{'holding': {'account_id': account_id, 'asset_class': asset, 'currency': currency,
                          'quantity': 2, 'market_value': value}}
             for account_id, asset, currency, value in [
                 ('investment', 'EQUITY', 'USD', 100), ('savings', 'MUTUALFUND', 'ILS', 200),
                 ('bank', 'BOND', 'ILS', 30), ('esop', 'RSU', 'GBP', 500)]]
    transactions = [{'id': 'deposit', 'account_db_id': 'bank', 'action': 'CASH_IN',
                     'quantity': 1, 'price': 5, 'currency': 'ILS', 'trade_date': '2026-11-10'}]
    return {'accounts': accounts, 'items': items, 'transactions': transactions,
            'fx': {'quotes': [{'pair': 'USD/ILS', 'quote': {'rate': 3.5, 'date': '2026-11-10'}}]}}


@pytest.fixture
def scenario_api(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path/'scenario.sqlite3')
    auth = AuthStore(store.path)
    auth.initialize()
    user = auth.create_user({'username': 'scenarioviewer', 'first_name': 'Scenario', 'last_name': 'Viewer',
                             'role': 'Viewer', 'password': 'Scenario-Test-Password!'})
    with auth._connect() as connection:
        connection.execute('update app_users set must_change_password=0 where id=?', (user['id'],))
    raw = raw_inputs()
    now = datetime(2026, 11, 11, 22, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(risk_scenarios, '_now', lambda: now)
    monkeypatch.setattr(main, 'auth_store', auth)
    monkeypatch.setattr(main, 'local_store', store)
    monkeypatch.setattr(main, '_risk_history_guard', lambda: ('saved-revision', 4))
    monkeypatch.setattr(main, '_portfolio_cache', {'signature': 'saved-revision', 'expires_at': time.time() + 3600,
                                                 'payload': {'items': raw['items'], 'refresh_state': 'ready'}})
    monkeypatch.setattr(main, '_portfolio_refresh_in_progress', False)
    monkeypatch.setattr(main, '_portfolio_refresh_failure', None)
    def no_refresh(**kwargs):
        raise AssertionError('scenario context may not start dashboard/provider refresh')
    monkeypatch.setattr(main, 'portfolio_payload', no_refresh)
    monkeypatch.setattr(main, 'schedule_portfolio_refresh', no_refresh)
    monkeypatch.setattr(store, 'list_accounts', lambda: raw['accounts'])
    monkeypatch.setattr(store, 'list_transactions', lambda: raw['transactions'])
    monkeypatch.setattr(main, '_risk_history_saved_fx', lambda *args: deepcopy(raw['fx']))
    main._login_failures.clear()
    client = TestClient(main.app, base_url='https://localhost:6443')
    return client, store, raw


def login(client):
    response = client.post('/api/auth/login', json={'username': 'scenarioviewer', 'password': 'Scenario-Test-Password!'})
    assert response.status_code == 200, response.text


def test_viewer_reads_full_dashboard_context_without_mutation_or_history_registration(scenario_api, monkeypatch):
    client, store, raw = scenario_api
    assert client.get('/api/portfolio/risk-scenarios/context').status_code == 401
    login(client)
    original = deepcopy(raw)
    contexts = deepcopy(risk_history._contexts)
    signature = store.change_token()
    with store._connect() as connection:
        before = connection.execute('select * from app_preferences').fetchall()
    def no_write(*args, **kwargs):
        raise AssertionError('scenario context may not write or register a history token')
    monkeypatch.setattr(store, 'set_preference', no_write)
    monkeypatch.setattr(risk_history, 'create_context', no_write)
    response = client.get('/api/portfolio/risk-scenarios/context?base_currency=ILS')
    assert response.status_code == 200, response.text
    context = response.json()
    assert context['model'] == 'portfolio-risk-v2'
    assert context['source'] == 'saved_evidence'
    assert context['observed_at'] == '2026-11-11T22:30:00Z'
    assert context['date'] == '2026-11-12', 'date follows the same captured instant in Jerusalem'
    assert {a['id'] for a in context['accounts']} == {'investment', 'bank', 'savings'}
    assert {i['holding']['account_id'] for i in context['items']} == {'investment', 'bank', 'savings'}
    assert context['transactions'] == raw['transactions']
    assert context['fx'] == raw['fx']
    assert not {'guard', 'token', 'fingerprint'} & context.keys()
    assert raw == original
    context['accounts'][0]['initial_cash'] = 999
    assert client.get('/api/portfolio/risk-scenarios/context').json()['accounts'][0]['initial_cash'] == 40
    assert risk_history._contexts == contexts
    assert store.change_token() == signature
    with store._connect() as connection:
        assert connection.execute('select * from app_preferences').fetchall() == before


@pytest.mark.parametrize(('change', 'code'), [
    (lambda raw: raw['accounts'][1].update(initial_cash=None), 'risk_context_unknown_cash'),
    (lambda raw: raw['accounts'][1].update(initial_cash=True), 'risk_context_unknown_cash'),
    (lambda raw: raw['accounts'][1].update(currency=''), 'risk_context_missing_fx'),
    (lambda raw: raw['accounts'][2].update(currency=''), 'risk_context_missing_currency'),
    (lambda raw: raw['items'][0]['holding'].update(asset_class=''), 'risk_context_missing_classification'),
    (lambda raw: raw['items'][0]['holding'].update(asset_class='UNKNOWN'), 'risk_context_missing_classification'),
    (lambda raw: raw['items'][0]['holding'].update(account_id='missing'), 'risk_context_unassigned_account'),
    (lambda raw: raw['items'][0]['holding'].update(currency=''), 'risk_context_missing_fx'),
    (lambda raw: raw.update(fx={'quotes': []}), 'risk_context_missing_fx'),
    (lambda raw: raw['transactions'][0].update(quantity=None), 'risk_context_invalid_cash_transaction'),
    (lambda raw: raw['transactions'][0].update(quantity=-1), 'risk_context_invalid_cash_transaction'),
    (lambda raw: raw['transactions'][0].update(price=True), 'risk_context_invalid_cash_transaction'),
    (lambda raw: raw['transactions'][0].update(currency='USD'), 'risk_context_mixed_cash_currencies'),
    (lambda raw: raw['transactions'][0].update(trade_date='invalid'), 'risk_context_invalid_transaction_date'),
    (lambda raw: raw['transactions'][0].update(trade_date='2026-11-10garbage'), 'risk_context_invalid_transaction_date'),
    (lambda raw: raw['transactions'][0].update(trade_date='2026-11-13'), 'risk_context_future_transactions'),
])
def test_unknown_or_unsupported_evidence_is_unavailable(scenario_api, change, code):
    client, store, raw = scenario_api
    login(client)
    change(raw)
    original = deepcopy(raw)
    response = client.get('/api/portfolio/risk-scenarios/context')
    assert response.status_code == 409, response.text
    assert response.json() == {'detail': {'code': code, 'message': code}}
    assert raw == original


@pytest.mark.parametrize('action', ['ADD', 'REMOVE', 'BUY', 'SELL', 'SHORT'])
def test_future_security_activity_is_not_an_as_of_today_context(scenario_api, action):
    client, store, raw = scenario_api
    login(client)
    raw['transactions'].append({'account_db_id': 'savings', 'action': action, 'quantity': 1,
                                'price': 0, 'currency': 'ILS', 'trade_date': '2026-11-13'})
    response = client.get('/api/portfolio/risk-scenarios/context')
    assert response.status_code == 409, response.text
    assert response.json()['detail']['code'] == 'risk_context_future_transactions'


def test_zero_cash_effect_and_today_jerusalem_activity_are_valid(scenario_api):
    client, store, raw = scenario_api
    login(client)
    raw['transactions'][0].update(quantity=0, currency='USD', trade_date='2026-11-12')
    assert client.get('/api/portfolio/risk-scenarios/context').status_code == 200
    response = client.get('/api/portfolio/risk-scenarios/context?base_currency=invalid')
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'risk_context_invalid_currency'


def test_display_format_ledger_date_is_normalized_in_detached_context_only(scenario_api):
    client, store, raw = scenario_api
    login(client)
    raw['transactions'][0]['trade_date'] = '10/11/2026'
    response = client.get('/api/portfolio/risk-scenarios/context')
    assert response.status_code == 200, response.text
    assert response.json()['transactions'][0]['trade_date'] == '2026-11-10'
    assert raw['transactions'][0]['trade_date'] == '10/11/2026'


def test_capture_still_requires_ready_and_unchanged_saved_source(scenario_api, monkeypatch):
    client, store, raw = scenario_api
    login(client)
    main._portfolio_cache['payload']['refresh_state'] = 'loading'
    response = client.get('/api/portfolio/risk-scenarios/context')
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'risk_context_not_ready'
    main._portfolio_cache['payload']['refresh_state'] = 'ready'
    guards = iter([('saved-revision', 4), ('changed-revision', 5)])
    monkeypatch.setattr(main, '_risk_history_guard', lambda: next(guards))
    response = client.get('/api/portfolio/risk-scenarios/context')
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'risk_context_stale'


@pytest.mark.parametrize('state', ['missing', 'expired', 'different_revision', 'refreshing', 'failed'])
def test_unready_saved_cache_does_not_start_provider_refresh(scenario_api, monkeypatch, state):
    client, store, raw = scenario_api
    login(client)
    if state == 'missing':
        monkeypatch.setattr(main, '_portfolio_cache', None)
        monkeypatch.setattr(main, 'read_portfolio_cache', lambda: None)
    elif state == 'expired':
        main._portfolio_cache['expires_at'] = 0
    elif state == 'different_revision':
        main._portfolio_cache['signature'] = 'old-revision'
    elif state == 'refreshing':
        monkeypatch.setattr(main, '_portfolio_refresh_in_progress', True)
    else:
        monkeypatch.setattr(main, '_portfolio_refresh_failure', {'signature': 'saved-revision'})
    response = client.get('/api/portfolio/risk-scenarios/context')
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'risk_context_not_ready'


def test_legacy_invalid_cash_conversion_is_a_structured_unavailable_result(scenario_api):
    client, store, raw = scenario_api
    login(client)
    raw['accounts'][1]['initial_cash'] = 'unknown'
    response = client.get('/api/portfolio/risk-scenarios/context')
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'risk_context_incomplete_values'
