"""Independent orchestration acceptance: real threads, no AI/provider calls."""
from copy import deepcopy
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.country_rating_schedules import CountryRatingResearch
from app.portfolio_ai_research import PortfolioAIResearch
from app.risk_input_retrieval import RiskInputRetrieval
from app.security_enrichment import EnrichmentJobs
from app.sovereign_ratings import country_descriptor
from test_parallel_research_qa import ControlledChildren as BaseControlledChildren, eventually, security


class ControlledChildren(BaseControlledChildren):
    def release_all(self):
        with self.lock:
            releases = list(self.releases.values())
        for release in releases:
            release.set()


def finish_parent(manager, started, release):
    def finished():
        release()
        return manager.get(started['request_id'], 'qa-owner')['status'] not in {'queued', 'running'}
    eventually(finished)
    result = manager.get(started['request_id'], 'qa-owner')
    assert result['status'] == 'completed', result.get('failure')


@pytest.mark.parametrize('configured,expected', [(None, 5), (1, 1), (3, 3), (7, 7)])
def test_actual_parent_worker_window_defaults_and_custom_configuration(configured, expected):
    children = ControlledChildren()
    settings = {} if configured is None else {'research_concurrency': configured}
    children.settings = lambda: dict(settings)
    parent = PortfolioAIResearch(children, children,
        lambda _, **options: {'market_items': [security(n) for n in range(9)], 'credit_items': []}, poll_seconds=.002)
    started = parent.start('qa-owner', {}, 'en', data_types=['prices'])
    try:
        eventually(lambda: len(children.calls) == expected)
        eventually(lambda: len(parent.get(started['request_id'], 'qa-owner')['current_children']) == expected)
        observed = parent.get(started['request_id'], 'qa-owner')
        assert observed['max_parallel_children'] == expected
        assert len(observed['current_children']) == expected
        assert observed['per_batch_limits'] == {'model': 8, 'rest': 8, 'web': 8}
        assert len(children.calls) == expected
        # The parent captures the value at start instead of following mutations.
        settings['research_concurrency'] = 1 if expected != 1 else 5
        children.releases['1'].set()
        eventually(lambda: len(children.calls) == expected + 1)
        assert parent.get(started['request_id'], 'qa-owner')['max_parallel_children'] == expected
        finish_parent(parent, started, children.release_all)
    finally:
        children.release_all()


def test_failed_parent_resume_keeps_original_configured_window():
    children = ControlledChildren()
    settings = {'research_concurrency': 3}
    children.settings = lambda: dict(settings)
    parent = PortfolioAIResearch(children, children,
        lambda _, **options: {'market_items': [], 'credit_items': [security(n) for n in range(6)]}, poll_seconds=.002)
    started = parent.start('qa-owner', {}, 'en', data_types=['company_ratings'])
    try:
        eventually(lambda: len(children.calls) == 3)
        children.failures.add('1')
        children.release_all()
        eventually(lambda: parent.get(started['request_id'], 'qa-owner')['status'] == 'failed')
        settings['research_concurrency'] = 1
        resumed = parent.start('qa-owner', {}, 'en', data_types=['company_ratings'], resume_request_id=started['request_id'])
        assert resumed['max_parallel_children'] == 3
        eventually(lambda: len(children.calls) == 6)
        finish_parent(parent, resumed, children.release_all)
    finally:
        children.release_all()


def block_actual_worker(manager, monkeypatch, keys_field):
    releases = {}
    entered = []
    def run(identifier, headers, language):
        release = Event()
        with manager._lock:
            job = manager._jobs[identifier]
            job['status'] = 'running'
            releases[identifier] = release
            entered.append(identifier)
        try:
            assert release.wait(8)
        finally:
            with manager._lock:
                job['status'] = 'completed'
                job['counts']['web_requests'] = 1
                job['outcomes'] = [{'security_key': key, 'status': 'updated', 'attempted': True}
                                   for key in job[keys_field]]
    monkeypatch.setattr(manager, 'run', run)
    def release_all():
        for release in list(releases.values()):
            release.set()
    return entered, release_all


def test_five_country_coordinators_reach_five_actual_leaf_workers(monkeypatch):
    countries = [country_descriptor(code) for code in ['US', 'IL', 'DE', 'FR', 'GB', 'CA']]
    leaves = EnrichmentJobs(None, lambda: {}, candidate_reader=lambda **_: {}, security_fetcher=lambda *_: {},
        outcome_reader=lambda: [], outcome_writer=lambda *_: [])
    entered, release = block_actual_worker(leaves, monkeypatch, '_security_keys')
    country = CountryRatingResearch(leaves, lambda *_, **__: deepcopy(countries), poll_seconds=.002)
    parent = PortfolioAIResearch(SimpleNamespace(settings=lambda: {}), object(),
        lambda *_, **__: {'market_items': [], 'credit_items': []}, country_jobs=country,
        country_inventory_reader=lambda *_, **__: deepcopy(countries), poll_seconds=.002)
    started = parent.start('qa-owner', {}, 'en', data_types=['country_ratings'])
    try:
        eventually(lambda: len(entered) == 5)
        eventually(lambda: len(parent.get(started['request_id'], 'qa-owner')['current_children']) == 5)
        assert len(country._jobs) == 5
        assert len(leaves._jobs) == 5
        finish_parent(parent, started, release)
        assert len(entered) == 6
    finally:
        release()


@pytest.mark.parametrize('configured', [1, 5, 7])
def test_risk_manager_admission_obeys_configuration_with_actual_threads(monkeypatch, configured):
    rows = [security(n) for n in range(configured + 1)]
    evidence = SimpleNamespace(candidates=lambda **kw: {'items': [row for row in rows if row['security_key'] in kw['security_keys']]})
    ai = SimpleNamespace(settings=lambda: {'research_concurrency': configured})
    manager = RiskInputRetrieval(evidence, ai, None, None)
    entered, release = block_actual_worker(manager, monkeypatch, 'security_keys')
    try:
        jobs = [manager.start('qa-owner', {}, 'en', security_keys=[row['security_key']], parent_request_id='parent')
                for row in rows[:configured]]
        eventually(lambda: len(entered) == configured)
        with pytest.raises(HTTPException) as error:
            manager.start('qa-owner', {}, 'en', security_keys=[rows[-1]['security_key']], parent_request_id='parent')
        assert error.value.status_code == 409
        assert manager.start('qa-owner', {}, 'en', security_keys=[rows[0]['security_key']], parent_request_id='parent')['request_id'] == jobs[0]['request_id']
        with pytest.raises(HTTPException) as error:
            manager.get(jobs[0]['request_id'], 'wrong-owner')
        assert error.value.status_code == 404
    finally:
        release()


def test_actual_app_settings_propagate_price_agent_concurrency(monkeypatch):
    from app import main
    raw = deepcopy(main.config.raw)
    raw['price_agent'] = {**raw.get('price_agent', {}), 'research_concurrency': 7}
    monkeypatch.setattr(main, 'config', SimpleNamespace(raw=raw))
    assert main._enrichment_assistant_settings()['research_concurrency'] == 7
    assert main.security_enrichment.settings()['research_concurrency'] == 7
    assert main.credit_rating_jobs.settings()['research_concurrency'] == 7
