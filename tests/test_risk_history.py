"""Observed-risk storage and source-coherence behavior, using raw local fixtures."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient
import pytest

from app import main, risk_history
from app.auth import AuthStore
from app.local_portfolio import LocalPortfolioStore


def fixture_inputs():
    return risk_history.canonical_inputs(
        [{'holding': {'account_id': 'a', 'asset_class': 'EQUITY', 'currency': 'USD', 'quantity': 1, 'market_value': 100}}],
        [{'id': 'a', 'account_id': 'Account 1', 'type': 'Investment', 'currency': 'USD', 'initial_cash': 10},
         {'id': 'esop', 'type': 'ESOP', 'currency': 'USD', 'initial_cash': 500},
         {'id': 'empty', 'type': 'Bank', 'currency': 'ILS', 'initial_cash': 0}], [],
        {'quotes': [{'pair': 'USD/ILS', 'quote': {'rate': 3.5, 'date': '2026-11-06'}}]}, 'ILS')


def score(value=30):
    return {'score': value, 'components': {name: 0 for name in risk_history._COMPONENTS},
            'quality_details': [{'code': 'price_history', 'symbols': ['ABC']}],
            'cash_debt': 0, 'net_equity': 385, 'drivers': ['Test input']}


def payload(context, value=30):
    return {'token': context['token'], 'total': score(value), 'accounts': [{'account_id': 'a', 'risk': score(value)}]}


def environment(tmp_path):
    store = LocalPortfolioStore(tmp_path/'history.sqlite3')
    inputs = {**fixture_inputs(), 'guard': ('source-v1', 1)}
    return store, inputs, lambda currency: deepcopy(inputs)


def test_observed_history_is_immutable_deduplicated_daily_and_survives_restart(tmp_path, monkeypatch):
    store, inputs, capture = environment(tmp_path)
    now = datetime(2026, 11, 6, 10, tzinfo=timezone.utc)
    monkeypatch.setattr(risk_history, '_now', lambda: now)
    signature = store.change_token()
    context = risk_history.create_context(store, 'writer', 'ILS', capture)
    result = risk_history.save_observation(store, 'writer', payload(context), capture, lambda: inputs['guard'])
    assert result['saved'] is True
    assert result['observation']['source'] == 'dashboard_client_calculated'
    assert result['observation']['accounts'][0]['account_label'] == 'Account 1'
    assert store.change_token() == signature, 'observations must not invalidate financial source caches'
    again = risk_history.create_context(store, 'writer', 'ILS', capture)
    duplicate = risk_history.save_observation(store, 'writer', payload(again, 90), capture, lambda: inputs['guard'])
    assert duplicate == {'saved': False, 'observation': result['observation']}
    assert store.change_token() == signature
    monkeypatch.setattr(risk_history, '_now', lambda: now + timedelta(days=1))
    next_day = risk_history.create_context(store, 'writer', 'ILS', capture)
    assert risk_history.save_observation(store, 'writer', payload(next_day, 40), capture, lambda: inputs['guard'])['saved']
    fresh_store = LocalPortfolioStore(store.path)
    history = risk_history.list_observations(fresh_store, 'ILS', 0)
    assert [row['total']['score'] for row in history['items']] == [30, 40]
    assert history['accounts'] == [{'id': 'a', 'label': 'Account 1'}]
    assert risk_history.list_observations(fresh_store, 'USD', 0)['items'] == []


def test_context_rejects_source_fx_and_final_publication_races(tmp_path):
    store, inputs, capture = environment(tmp_path)
    context = risk_history.create_context(store, 'writer', 'ILS', capture)
    for change in ('signature', 'generation', 'fx'):
        modified = deepcopy(inputs)
        if change == 'signature': modified['guard'] = ('new-source', 1)
        elif change == 'generation': modified['guard'] = ('source-v1', 2)
        else: modified['fx']['quotes'][0]['quote']['rate'] = 4
        with pytest.raises(risk_history.RiskHistoryError, match='risk_context_stale'):
            risk_history.save_observation(store, 'writer', payload(context), lambda _: modified, lambda: modified['guard'])
    # Source changes after capture but before the transactional write reservation.
    with pytest.raises(risk_history.RiskHistoryError, match='risk_context_stale'):
        risk_history.save_observation(store, 'writer', payload(context), capture, lambda: ('source-v2', 1))
    assert risk_history.list_observations(store, 'ILS', 0)['items'] == []


def test_context_is_bound_to_author_database_and_expiry(tmp_path, monkeypatch):
    store, inputs, capture = environment(tmp_path)
    now = datetime(2026, 11, 6, 10, tzinfo=timezone.utc)
    monkeypatch.setattr(risk_history, '_now', lambda: now)
    context = risk_history.create_context(store, 'writer', 'ILS', capture)
    for actual_store, author in ((store, 'other'), (LocalPortfolioStore(tmp_path/'other.sqlite3'), 'writer')):
        with pytest.raises(risk_history.RiskHistoryError, match='risk_context_expired'):
            risk_history.save_observation(actual_store, author, payload(context), capture, lambda: inputs['guard'])
    monkeypatch.setattr(risk_history, '_now', lambda: now + risk_history.CONTEXT_TTL)
    with pytest.raises(risk_history.RiskHistoryError, match='risk_context_expired'):
        risk_history.save_observation(store, 'writer', payload(context), capture, lambda: inputs['guard'])


def test_invalid_scores_accounts_and_metadata_never_create_observations(tmp_path):
    store, inputs, capture = environment(tmp_path)
    context = risk_history.create_context(store, 'writer', 'ILS', capture)
    for value in (True, 1.5, -1, 101, float('nan')):
        with pytest.raises(risk_history.RiskHistoryError):
            risk_history.save_observation(store, 'writer', payload(context, value), capture, lambda: inputs['guard'])
    for update in ({'accounts': []}, {'accounts': [{'account_id': 'esop', 'risk': score()}]},
                   {'total': {**score(), 'components': {'concentration': float('inf')}}},
                   {'total': {**score(), 'net_equity': float('nan')}},
                   {'total': {**score(), 'quality_details': [{'code': 'x'*66000}]}}):
        with pytest.raises(risk_history.RiskHistoryError):
            risk_history.save_observation(store, 'writer', {**payload(context), **update}, capture, lambda: inputs['guard'])
    assert risk_history.list_observations(store, 'ILS', 0)['items'] == []


def test_scope_and_required_fx_match_dashboard_without_native_value_fallback():
    data = fixture_inputs()
    assert data['account_ids'] == ['a']
    assert {row['id'] for row in data['accounts']} == {'a', 'empty'}
    for fx in ({'quotes': []}, {'quotes': [{'pair': 'USD/ILS', 'quote': {'rate': 0}}]}):
        with pytest.raises(risk_history.RiskHistoryError, match='risk_context_missing_fx'):
            risk_history.canonical_inputs(data['items'], data['accounts'], data['transactions'], fx, 'ILS')
    reverse = {'quotes': [{'pair': 'ILS/USD', 'quote': {'rate': 1/3.5}}]}
    assert risk_history.canonical_inputs(data['items'], data['accounts'], [], reverse, 'ILS')['account_ids'] == ['a']
    bad = deepcopy(data['items']); bad[0]['holding']['account_id'] = ''
    with pytest.raises(risk_history.RiskHistoryError, match='risk_context_unassigned_account'):
        risk_history.canonical_inputs(bad, data['accounts'], [], data['fx'], 'ILS')
    # True empty and debt-only model shapes are valid, without invented components.
    assert risk_history._risk({'score': 0, 'components': {}})['score'] == 0
    assert risk_history._risk({'score': 100, 'components': {'borrowing': 100}})['score'] == 100


def test_context_publication_ignores_loading_failed_and_changed_capture(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path/'context.sqlite3')
    monkeypatch.setattr(main, 'local_store', store)
    monkeypatch.setattr(main, '_risk_history_saved_fx', lambda *args: {'quotes': []})
    for payload in ({'refresh_pending': True}, {'refresh_state': 'failed'}, {'items': [{'analytics_state': 'failed'}]}):
        monkeypatch.setattr(main, 'portfolio_payload', lambda **kwargs: payload)
        with pytest.raises(risk_history.RiskHistoryError, match='risk_context_not_ready'):
            main._risk_history_inputs('ILS')
    monkeypatch.setattr(main, 'portfolio_payload', lambda **kwargs: {'items': [], 'refresh_state': 'ready'})
    guards = iter([('before', 1), ('after', 1)])
    monkeypatch.setattr(main, '_risk_history_guard', lambda: next(guards))
    with pytest.raises(risk_history.RiskHistoryError, match='risk_context_stale'):
        main._risk_history_inputs('ILS')


def test_api_history_viewer_reads_only_and_writer_csrf_capture(tmp_path, monkeypatch):
    store, inputs, capture = environment(tmp_path)
    auth = AuthStore(store.path); auth.initialize()
    for username, role in [('historyviewer', 'Viewer'), ('historywriter', 'Operator')]:
        user = auth.create_user({'username': username, 'first_name': 'Risk', 'last_name': role, 'role': role, 'password': 'History-Test-Password!'})
        with auth._connect() as connection:
            connection.execute('update app_users set must_change_password=0 where id=?', (user['id'],))
    monkeypatch.setattr(main, 'auth_store', auth)
    monkeypatch.setattr(main, 'local_store', store)
    monkeypatch.setattr(main, '_risk_history_inputs', capture)
    monkeypatch.setattr(main, '_risk_history_guard', lambda: inputs['guard'])
    monkeypatch.setattr(main, '_risk_history_saved_fx', lambda *args: deepcopy(inputs['fx']))
    main._login_failures.clear()
    client = TestClient(main.app, base_url='https://localhost:6443')
    assert client.get('/api/portfolio/risk-history').status_code == 401
    session = client.post('/api/auth/login', json={'username': 'historyviewer', 'password': 'History-Test-Password!'}).json()
    assert client.get('/api/portfolio/risk-history').status_code == 200
    context = client.get('/api/portfolio/risk-history/context').json()
    assert client.post('/api/portfolio/risk-history', json=payload(context), headers={'X-CSRF-Token': session['csrf_token']}).status_code == 403
    session = client.post('/api/auth/login', json={'username': 'historywriter', 'password': 'History-Test-Password!'}).json()
    context = client.get('/api/portfolio/risk-history/context').json()
    assert client.post('/api/portfolio/risk-history', json=payload(context)).status_code == 403
    saved = client.post('/api/portfolio/risk-history', json=payload(context), headers={'X-CSRF-Token': session['csrf_token']})
    assert saved.status_code == 200, saved.text
    assert saved.json()['saved'] is True
    assert client.get('/api/portfolio/risk-history', params={'days': 0}).json()['items'][0]['total']['score'] == 30


def test_jerusalem_day_cutoff_and_corrupted_imported_history_are_explicit(tmp_path, monkeypatch):
    store, inputs, capture = environment(tmp_path)
    now = datetime(2026, 11, 6, 22, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(risk_history, '_now', lambda: now)
    context = risk_history.create_context(store, 'writer', 'ILS', capture)
    assert context['date'] == '2026-11-07'
    saved = risk_history.save_observation(store, 'writer', payload(context), capture, lambda: inputs['guard'])['observation']
    assert saved['evidence']['fx']['quotes'][0]['quote']['rate'] == 3.5
    damaged = {**saved, 'id': 'corrupt', 'total': {'score': 'unknown', 'components': {}}}
    store.set_preference(risk_history.PREFIX + 'corrupt', damaged)
    history = risk_history.list_observations(store, 'ILS', 1)
    assert len(history['items']) == 1
    assert history['invalid_records'] == 1


def test_final_fx_recheck_rejects_quote_changed_after_full_context_capture(tmp_path):
    store, inputs, capture = environment(tmp_path)
    context = risk_history.create_context(store, 'writer', 'ILS', capture)
    changed = deepcopy(inputs['fx']); changed['quotes'][0]['quote']['rate'] = 3.8
    with pytest.raises(risk_history.RiskHistoryError, match='risk_context_stale'):
        risk_history.save_observation(store, 'writer', payload(context), capture, lambda: inputs['guard'], lambda _: changed)
    assert risk_history.list_observations(store, 'ILS', 0)['items'] == []


def test_current_accounts_stay_selectable_without_observations_in_selected_range(tmp_path, monkeypatch):
    store, inputs, capture = environment(tmp_path)
    monkeypatch.setattr(store, 'list_accounts', lambda: [
        {'id': 'current', 'account_id': 'No recent observations', 'type': 'Investment'},
        {'id': 'esop', 'account_id': 'Excluded', 'type': 'ESOP'},
    ])
    history = risk_history.list_observations(store, 'ILS', 1)
    assert history['accounts'] == [{'id': 'current', 'label': 'No recent observations'}]
    assert history['items'] == []


def test_context_fx_reads_only_saved_cache_and_excludes_esop(tmp_path, monkeypatch):
    from types import SimpleNamespace
    calls = []
    class Provider:
        name = 'fake'
        def fx(self, pair):
            raise AssertionError('risk observation must never perform provider FX I/O')
    class Cache:
        def get_security_snapshot(self, provider, pair, kind):
            calls.append(pair)
            return {'pair': pair, 'rate': 3.5, 'time': '2026-11-06'} if pair == 'USD/ILS' else None
    monkeypatch.setattr(main, 'hub', lambda: SimpleNamespace(providers=[Provider()], cache=Cache()))
    items = [{'holding': {'account_id': 'esop', 'asset_class': 'EQUITY', 'currency': 'GBP'}},
             {'holding': {'account_id': 'cash', 'asset_class': 'EQUITY', 'currency': 'USD'}}]
    accounts = [{'id': 'esop', 'type': 'ESOP', 'currency': 'GBP'}, {'id': 'cash', 'type': 'Investment', 'currency': 'USD'}]
    result = main._risk_history_saved_fx('ILS', items, accounts)
    assert result['quotes'] == [{'pair': 'USD/ILS', 'quote': {'pair': 'USD/ILS', 'rate': 3.5, 'time': '2026-11-06'}, 'status': {'fake': 'saved_evidence'}}]
    assert 'GBP/ILS' not in calls and 'ILS/GBP' not in calls
