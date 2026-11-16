"""A general AI update must cover risk evidence across its entire chosen scope."""
from copy import deepcopy

import pytest
from fastapi import HTTPException

from app.portfolio_ai_research import PortfolioAIResearch
from test_portfolio_ai_research import Children, Deferred, row
from test_ai_research_targets import complete_risk


class RiskChildren:
    def __init__(self, count=7, *, unresolved=False, fail_call=None):
        self.rows = [row(n) for n in range(1, count + 1)]
        self.values = {r['security_key']: complete_risk() for r in self.rows}
        for value in self.values.values():
            value.pop('issuer_id')
            value.pop('country_rating')
        self.unresolved, self.fail_call, self.calls = unresolved, fail_call, []
        self.evidence = self
        self.inputs = self

    def candidates(self, *, position_scope, security_keys=None, refresh_policy='missing'):
        return {'items': [deepcopy(r) for r in self.rows if not security_keys or r['security_key'] in security_keys]}

    def candidate(self, key):
        return next(r for r in self.rows if r['security_key'] == key)

    def read(self, candidate):
        return deepcopy(self.values[candidate['security_key']])

    def start(self, owner, headers, language, *, security_keys, position_scope, refresh_policy, mode):
        assert len(security_keys) <= 3
        assert 'untrusted' not in headers
        self.calls.append({'keys': security_keys, 'scope': position_scope, 'policy': refresh_policy, 'mode': mode})
        failed = len(self.calls) == self.fail_call
        outcomes = []
        for key in security_keys:
            if not failed:
                self.values[key]['issuer_id'] = 'issuer:' + key
                if self.unresolved:
                    self.values[key].pop('currency_exposures', None)
            outcomes.append({**self.candidate(key), 'status': 'unavailable' if failed else 'partial',
                'code': 'provider_unavailable' if failed else 'partial_data', 'attempted': True,
                'available_fields': [] if failed else ['issuer_id'],
                'missing_fields': ['country_rating'], 'sources': []})
        return {'request_id': 'risk-' + str(len(self.calls)), 'status': 'failed' if failed else 'completed',
            'code': 'provider_unavailable' if failed else 'completed', 'outcomes': outcomes,
            'counts': {'model_requests': 2, 'rest_requests': 3, 'web_requests': 1},
            'portfolio_refresh_required': not failed}


class CountryChildren:
    def __init__(self, risk):
        self.risk, self.calls = risk, []

    def start(self, owner, headers, language, scope, *, country_codes, refresh_policy):
        self.calls.append(country_codes)
        for value in self.risk.values.values():
            value['country_rating'] = {'status': 'rated'}
        return {'request_id': 'country-1', 'status': 'completed', 'outcomes': [
            {'security_key': 'COUNTRY:' + code, 'country_code': code, 'status': 'updated', 'attempted': True}
            for code in country_codes], 'counts': {'model_requests': 2, 'rest_requests': 2, 'web_requests': 1}}


def manager(*, unresolved=False, fail_call=None):
    Deferred.callbacks = []
    risk = RiskChildren(unresolved=unresolved, fail_call=fail_call)
    countries = CountryChildren(risk)
    captures = []
    def country_inventory(scope, **options):
        # Country discovery happens after all selected security research.
        captures.append(len(risk.calls))
        return [{'security_key': 'COUNTRY:US', 'country_code': 'US'}]
    parent = PortfolioAIResearch(Children(), Children(), lambda scope, **opts: {'market_items': [], 'credit_items': []},
        risk_jobs=risk, country_jobs=countries, country_inventory_reader=country_inventory,
        worker_factory=Deferred, poll_seconds=0)
    return parent, risk, countries, captures


def test_general_update_covers_every_risk_subject_then_dependent_countries():
    parent, risk, countries, captures = manager()
    started = parent.start('owner', {'untrusted': 'private-header'}, 'en')
    assert set(started['data_types']) == {'prices', 'profile', 'company_ratings', 'risk_inputs', 'country_ratings'}
    Deferred.callbacks.pop(0)()
    result = parent.get(started['request_id'], 'owner')
    assert result['status'] == 'completed', result.get('failure')
    assert result['code'] == 'research_complete'
    assert [key for call in risk.calls for key in call['keys']] == [r['security_key'] for r in risk.rows]
    assert captures == [7] and countries.calls == [['US']]
    assert result['risk_inputs']['progress'] == {'completed': 7, 'total': 7, 'current_security': None}
    assert result['risk_inputs']['coverage']['remaining'] == 0
    assert all(r['missing_fields'] == [] and r['status'] == 'updated' for r in result['risk_inputs']['outcomes'])
    assert all('country_rating' in r['available_fields'] for r in result['risk_inputs']['outcomes'])
    assert result['portfolio_refresh_required'] is True
    assert result['counts']['max_web_requests'] == 8 * 8


def test_risk_only_selection_still_researches_dependent_country_and_retains_real_gaps():
    parent, risk, countries, _ = manager(unresolved=True)
    selected = [risk.rows[2]['security_key']]
    started = parent.start('owner', {}, 'he', data_types=['risk_inputs'], security_keys=selected,
                           risk_mode='ai', refresh_policy='stale')
    Deferred.callbacks.pop(0)()
    result = parent.get(started['request_id'], 'owner')
    assert result['status'] == 'completed' and result['code'] == 'research_partial'
    assert risk.calls == [{'keys': selected, 'scope': 'open', 'policy': 'stale', 'mode': 'ai'}]
    assert countries.calls == [['US']]
    assert result['risk_inputs']['outcomes'][0]['missing_fields'] == ['fx']
    assert result['risk_inputs']['summary']['partial'] == 1
    assert result['risk_inputs']['coverage']['selected'] == 1


def test_risk_failure_resume_does_not_repeat_successful_subjects_or_lose_scope():
    parent, risk, _, _ = manager(fail_call=2)
    started = parent.start('owner', {}, 'en', data_types=['risk_inputs'], risk_mode='api')
    Deferred.callbacks.pop(0)()
    failed = parent.get(started['request_id'], 'owner')
    assert failed['status'] == 'failed'
    assert failed['risk_inputs']['progress']['completed'] == 1
    with pytest.raises(HTTPException) as changed:
        parent.start('owner', {}, 'en', data_types=['risk_inputs'], risk_mode='ai', resume_request_id=started['request_id'])
    assert changed.value.status_code == 409
    parent.start('owner', {}, 'en', data_types=['risk_inputs'], risk_mode='api', resume_request_id=started['request_id'])
    Deferred.callbacks.pop(0)()
    result = parent.get(started['request_id'], 'owner')
    assert result['status'] == 'completed'
    assert sum(risk.rows[0]['security_key'] in call['keys'] for call in risk.calls) == 1
    assert len(risk.calls) == 8


def test_market_only_request_does_not_start_risk_or_country_research():
    parent, risk, countries, captures = manager()
    started = parent.start('owner', {}, 'en', data_types=['prices'])
    Deferred.callbacks.pop(0)()
    assert parent.get(started['request_id'], 'owner')['status'] == 'completed'
    assert risk.calls == countries.calls == captures == []
    with pytest.raises(HTTPException):
        parent.start('owner', {}, 'en', risk_mode='arbitrary')


def test_default_general_request_runs_risk_and_country_through_normal_auth(env, monkeypatch):
    from app import main
    from test_portfolio_ai_research_integration import poll, PATH
    risk = RiskChildren()
    countries = CountryChildren(risk)
    monkeypatch.setattr(main.portfolio_ai_research, 'risk_jobs', risk)
    monkeypatch.setattr(main.portfolio_ai_research, 'country_jobs', countries)
    monkeypatch.setattr(main.portfolio_ai_research, 'country_inventory_reader',
        lambda scope, **opts: [{'security_key': 'COUNTRY:US', 'country_code': 'US'}])
    env.release.set()
    rejected = env.client.post(PATH + '/ai', headers=env.headers, json={'risk_mode': 'invent'})
    assert rejected.status_code == 422
    started = env.client.post(PATH + '/ai', headers=env.headers, json={})
    assert started.status_code == 202
    assert set(started.json()['data_types']) == {'prices', 'profile', 'company_ratings', 'risk_inputs', 'country_ratings'}
    result = poll(env.client, started.json()['request_id'])
    assert result['status'] == 'completed', result.get('failure')
    assert len(result['credit_ratings']['outcomes']) == 7
    assert len(result['risk_inputs']['outcomes']) == 7 and countries.calls == [['US']]
    assert result['risk_inputs']['summary']['updated'] == 7
    assert result['country_ratings']['summary']['updated'] == 1


# The fixture supplies isolated stores, real AuthStore and bounded credit REST
# tools; its deterministic public source/model doubles remain explicit above.
from test_portfolio_ai_research_integration import env


def test_unsupported_bond_and_unavailable_underlying_never_report_complete():
    from app.risk_input_retrieval import missing_fields
    bond = complete_risk('corporate_bond')
    assert 'unsupported_instrument' in missing_fields({**bond, 'unsupported_bond': True}, {'asset_class': 'BOND'})
    assert 'unsupported_instrument' in missing_fields({**bond, 'requires_recovery_model': True}, {'asset_class': 'BOND'})
    assert 'parameters_unavailable' in missing_fields({**complete_risk(), 'error': 'missing_source'}, {'asset_class': 'EQUITY'})
    fund = {'parameters': {'instrument_kind': 'fund'}, 'lookthrough_verified': True, 'lookthrough': [
        {'weight': 1, 'item': {'holding': {'asset_class': 'EQUITY'}, 'stress_risk': complete_risk()}}]}
    assert missing_fields(fund, {'asset_class': 'ETF'}) == []
    fund['lookthrough'][0]['item']['stress_risk']['error'] = 'missing_source'
    assert {'fund_lookthrough', 'parameters_unavailable'} <= set(missing_fields(fund, {'asset_class': 'ETF'}))


def test_equity_subclass_does_not_replace_primary_asset_kind():
    from app.risk_input_retrieval import missing_fields
    risk = complete_risk()
    assert missing_fields(risk, {'asset_class': 'EQUITY', 'asset_sub_class': 'REIT'}) == []
    mismatched = {**risk, 'parameters': {**risk['parameters'], 'instrument_kind': 'fund'}}
    assert 'asset_class' in missing_fields(mismatched, {'asset_class': 'EQUITY'})
