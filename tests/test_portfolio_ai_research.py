"""Independent orchestration contract tests with deterministic bounded child jobs."""
from copy import deepcopy

import pytest
from fastapi import HTTPException
from app.portfolio_ai_research import PortfolioAIResearch


class Deferred:
    callbacks=[]
    def __init__(self,target,**kwargs):self.callbacks.append(target)
    def start(self):pass


def row(n):
    return {'security_key':f'QA{n}|NYSE|USD','symbol':f'QA{n}','stock_market':'NYSE','currency':'USD','asset_class':'EQUITY'}


class Children:
    def __init__(self,*,fail_call=None,partial_failure=False,phase=None):
        self.calls=[];self._jobs={};self.fail_call=fail_call;self.partial_failure=partial_failure;self.phase=phase
        self.observed=[]
    def settings(self):return {'max_tool_loops':20,'max_rest_calls':20,'max_web_calls':20,'research_concurrency':2}
    def _outcome_reader(self):return []
    def start(self,owner,headers,language,scope,*,security_keys):
        self.calls.append(deepcopy(security_keys));identifier='child-'+str(len(self.calls))
        failure=self.fail_call==len(self.calls)
        items=[{**row(int(key.split('|')[0][2:])),'status':'updated','code':'data_found','attempted':True,
            'verified_agencies':['fitch'],'agency_statuses':{'moodys':'unavailable','sp':'unavailable','fitch':'rated'}} for key in security_keys]
        if failure:
            items=[{**item,'status':'unavailable','code':'provider_unavailable'} for item in items]
            if self.partial_failure:items[0].update(status='partial',code='partial_data')
        result={'request_id':identifier,'status':'failed' if failure else 'completed','code':'provider_unavailable' if failure else 'data_found',
            'outcomes':items,'counts':{'model_requests':2,'rest_requests':3,'web_requests':1,
              'max_model_requests':8,'max_rest_requests':8,'max_web_requests':8},
            'progress':{'stage':'failed' if failure else 'completed','completed':len(items),'total':len(items),'current_security':None}}
        self._jobs[identifier]=result
        if self.phase:
            return {**deepcopy(result),'status':'running','progress':{'stage':self.phase,'completed':len(items),'total':len(items),'current_security':None}}
        return deepcopy(result)
    def get(self,identifier,owner):
        if hasattr(self,'parent'):
            self.observed.append(deepcopy(self.parent._jobs[self.parent_id]['credit_ratings']['progress']))
        return deepcopy(self._jobs[identifier])


def make(*,fail_call=None,partial_failure=False,phase=None):
    Deferred.callbacks=[]
    market=Children();credit=Children(fail_call=fail_call,partial_failure=partial_failure,phase=phase)
    parent=PortfolioAIResearch(market,credit,lambda scope:{'market_items':[],'credit_items':[row(n) for n in range(1,8)]+[row(1)]},
        worker_factory=Deferred,poll_seconds=0)
    started=parent.start('owner',{'cookie':'synthetic-cookie','x-csrf-token':'synthetic-csrf','untrusted':'private-header'},'en')
    credit.parent=parent;credit.parent_id=started['request_id']
    return parent,credit,started


def test_all_keys_once_bounded_children_and_repeated_start():
    parent,credit,started=make()
    repeated=parent.start('owner',{},'en')
    assert repeated['request_id']==started['request_id'] and len(Deferred.callbacks)==1
    with pytest.raises(HTTPException) as changed:
        parent.start('owner',{},'en','all')
    assert changed.value.status_code==409
    Deferred.callbacks.pop(0)()
    result=parent.get(started['request_id'],'owner')
    assert result['status']=='completed'
    assert all(1<=len(keys)<=3 for keys in credit.calls)
    assert sum(map(len,credit.calls))==7
    assert len({key for batch in credit.calls for key in batch})==7
    assert result['credit_ratings']['progress']['completed']==result['credit_ratings']['progress']['total']==7
    assert result['counts']['rest_requests']==3*len(credit.calls) and result['counts']['max_rest_requests']==8*len(credit.calls)
    assert result['per_batch_limits']=={'model':8,'rest':8,'web':8}
    assert not any(key.startswith('_') for key in result)


def test_failure_resume_reuses_completed_keys_and_owner_scope_boundaries():
    parent,credit,started=make(fail_call=2)
    Deferred.callbacks.pop(0)()
    failed=parent.get(started['request_id'],'owner')
    assert failed['status']=='failed'
    assert len(credit.calls)==2
    completed=set(credit.calls[0])
    assert failed['credit_ratings']['progress']['completed']==len(completed)
    assert failed['credit_ratings']['summary']['not_attempted']==7-len(completed)
    with pytest.raises(HTTPException) as wrong:
        parent.start('other',{},'en',resume_request_id=started['request_id'])
    assert wrong.value.status_code==404
    with pytest.raises(HTTPException) as scope:
        parent.start('owner',{},'en','all',resume_request_id=started['request_id'])
    assert scope.value.status_code==409
    parent.start('owner',{},'en',resume_request_id=started['request_id'])
    assert len(Deferred.callbacks)==1
    parent.start('owner',{},'en',resume_request_id=started['request_id'])
    assert len(Deferred.callbacks)==1
    Deferred.callbacks.pop(0)()
    result=parent.get(started['request_id'],'owner')
    assert result['status']=='completed'
    resumed=[key for keys in credit.calls[2:] for key in keys]
    assert set(resumed)=={row(n)['security_key'] for n in range(1,8)}-completed
    assert len(resumed)==len(set(resumed))
    assert not completed & set(resumed)
    with pytest.raises(HTTPException) as done:
        parent.start('owner',{},'en',resume_request_id=started['request_id'])
    assert done.value.status_code==409


def test_partial_success_in_failed_child_is_preserved_on_resume():
    parent,credit,started=make(fail_call=2,partial_failure=True)
    Deferred.callbacks.pop(0)()
    failed=parent.get(started['request_id'],'owner')
    completed=set(credit.calls[0])|{credit.calls[1][0]}
    assert failed['credit_ratings']['progress']['completed']==len(completed)
    parent.start('owner',{},'en',resume_request_id=started['request_id'])
    Deferred.callbacks.pop(0)()
    assert parent.get(started['request_id'],'owner')['status']=='completed'
    resumed=[key for keys in credit.calls[2:] for key in keys]
    assert set(resumed)=={row(n)['security_key'] for n in range(1,8)}-completed
    assert len(resumed)==len(set(resumed))
    assert not completed & set(resumed)


def test_preflight_does_not_count_as_completed_public_rating_checks():
    parent,credit,started=make(phase='checking_apis')
    Deferred.callbacks.pop(0)()
    assert credit.observed
    assert credit.observed[0]['completed']==0, credit.observed[0]


def test_completed_child_without_any_public_attempt_remains_unchecked_and_resumable():
    parent,credit,started=make()
    original=credit.start
    def no_public(*args,**kwargs):
        result=original(*args,**kwargs)
        result['counts']['web_requests']=0
        credit._jobs[result['request_id']]['counts']['web_requests']=0
        return result
    credit.start=no_public
    Deferred.callbacks.pop(0)()
    result=parent.get(started['request_id'],'owner')
    assert result['status']=='failed'
    assert result['credit_ratings']['progress']['completed']==0
    assert result['credit_ratings']['summary']['not_attempted']==7
    assert all(not row['attempted'] for row in result['credit_ratings']['outcomes'])


class ConcurrentChildren(Children):
    """Real worker threads held at a deterministic public-research boundary."""
    def __init__(self, *, fail_call=None):
        super().__init__(fail_call=fail_call)
        from threading import Event, RLock
        self.lock, self.two_started = RLock(), Event()
        self.releases, self.finished = {}, {}

    def start(self, *args, **kwargs):
        from threading import Event, Thread
        with self.lock:
            terminal = super().start(*args, **kwargs)
            identifier = terminal['request_id']
            release, finished = Event(), Event()
            self.releases[identifier], self.finished[identifier] = release, finished
            self._jobs[identifier] = {**deepcopy(terminal), 'status': 'running'}
            running = deepcopy(self._jobs[identifier])
            if len(self.calls) == 2:
                self.two_started.set()
        def complete():
            if not release.wait(5):
                terminal.update(status='failed', code='fixture_timeout')
            with self.lock:
                self._jobs[identifier] = terminal
            finished.set()
        Thread(target=complete, daemon=True).start()
        return running

    def get(self, identifier, owner):
        with self.lock:
            return deepcopy(self._jobs[identifier])


def wait_job(parent, identifier, predicate):
    import time
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = parent.get(identifier, 'owner')
        if predicate(result):
            return result
        time.sleep(.005)
    raise AssertionError('Concurrent coordinator did not reach expected state')


@pytest.mark.parametrize('branch', ['market', 'credit'])
def test_real_threads_overlap_bounded_jobs_and_publish_out_of_order_results(branch):
    child = ConcurrentChildren()
    inventory = {'market_items': [], 'credit_items': []}
    inventory[branch + '_items'] = [row(n) for n in range(1, 4)]
    parent = PortfolioAIResearch(child if branch == 'market' else Children(),
        child if branch == 'credit' else Children(), lambda *_: inventory, poll_seconds=.005)
    started = parent.start('owner', {}, 'en')
    identifier = started['request_id']
    try:
        assert child.two_started.wait(5), 'Two independent workers must overlap'
        state = wait_job(parent, identifier, lambda value: len(value['current_children']) == 2)
        assert len(child.calls) == 2 and all(len(keys) == 1 for keys in child.calls)
        assert {item['security_key'] for item in state['progress']['current_securities']} == {
            row(1)['security_key'], row(2)['security_key']}
        assert len(parent.diagnostics(identifier, 'owner')['children']) == 2
        assert state['counts']['model_requests'] == 4
        # Complete the second worker while the first remains blocked. The next
        # item must start without waiting for the first item's result.
        child.releases['child-2'].set()
        state = wait_job(parent, identifier, lambda value: len(child.calls) == 3)
        outcomes = state['outcomes'] if branch == 'market' else state['credit_ratings']['outcomes']
        assert outcomes[1]['status'] == 'updated' and outcomes[0]['status'] == 'pending'
        assert state['status'] == 'running'
        for release in list(child.releases.values()):
            release.set()
        result = wait_job(parent, identifier, lambda value: value['status'] == 'completed')
        assert result['counts']['model_requests'] == 6
        assert result['counts']['max_model_requests'] == 24
        assert result['current_children'] == []
    finally:
        for release in list(child.releases.values()):
            release.set()
        wait_job(parent, identifier, lambda value: value['status'] not in {'queued', 'running'})


def test_concurrent_failure_drains_started_work_and_resume_skips_successful_sibling():
    child = ConcurrentChildren(fail_call=1)
    parent = PortfolioAIResearch(Children(), child,
        lambda *_: {'market_items': [], 'credit_items': [row(n) for n in range(1, 4)]}, poll_seconds=.005)
    identifier = parent.start('owner', {}, 'en')['request_id']
    try:
        assert child.two_started.wait(5)
        child.releases['child-1'].set()
        wait_job(parent, identifier, lambda value: len(value['children']) == 1)
        state = parent.get(identifier, 'owner')
        assert state['status'] == 'running' and len(child.calls) == 2
        # The parent must not fail or allow resume while a sibling can save.
        assert parent.start('owner', {}, 'en')['request_id'] == identifier
        child.releases['child-2'].set()
        failed = wait_job(parent, identifier, lambda value: value['status'] == 'failed')
        assert len(child.calls) == 2
        assert failed['credit_ratings']['progress']['completed'] == 1
        assert failed['failure']['security_key'] == row(1)['security_key']
        assert failed['counts']['model_requests'] == 4
        parent.start('owner', {}, 'en', resume_request_id=identifier)
        wait_job(parent, identifier, lambda value: len(child.calls) == 4)
        assert {key for call in child.calls[2:] for key in call} == {row(1)['security_key'], row(3)['security_key']}
        for release in list(child.releases.values()):
            release.set()
        result = wait_job(parent, identifier, lambda value: value['status'] == 'completed')
        assert result['credit_ratings']['progress']['completed'] == 3
    finally:
        for release in list(child.releases.values()):
            release.set()
        wait_job(parent, identifier, lambda value: value['status'] not in {'queued', 'running'})


def test_nested_coordinator_siblings_require_same_parent_disjoint_scope_and_deduplicate_every_active_job():
    Deferred.callbacks = []
    parent = PortfolioAIResearch(Children(), Children(), lambda *_: {}, worker_factory=Deferred)
    first = parent.start('owner', {}, 'en', security_keys=[row(1)['security_key']], parent_request_id='outer')
    second = parent.start('owner', {}, 'en', security_keys=[row(2)['security_key']], parent_request_id='outer')
    repeat = parent.start('owner', {}, 'en', security_keys=[row(2)['security_key']], parent_request_id='outer')
    assert repeat['request_id'] == second['request_id'] != first['request_id']
    assert len(Deferred.callbacks) == 2
    for keys, context in (([row(1)['security_key'], row(2)['security_key']], 'outer'),
                          ([row(2)['security_key']], None),
                          ([row(3)['security_key']], 'different'),
                          ([row(3)['security_key']], 'outer')):
        with pytest.raises(HTTPException) as rejected:
            parent.start('owner', {}, 'en', security_keys=keys, parent_request_id=context)
        assert rejected.value.status_code == 409


@pytest.mark.parametrize('configured,expected', [(None, 5), (1, 1), (3, 3)])
def test_real_threads_use_default_five_or_configured_parallel_window(configured, expected):
    child = ConcurrentChildren()
    settings = {'max_tool_loops': 8, 'max_rest_calls': 8, 'max_web_calls': 8}
    if configured is not None:
        settings['research_concurrency'] = configured
    child.settings = lambda: deepcopy(settings)
    parent = PortfolioAIResearch(child, child,
        lambda *_: {'market_items': [row(n) for n in range(1, 8)], 'credit_items': []}, poll_seconds=.005)
    started = parent.start('owner', {}, 'en')
    identifier = started['request_id']
    try:
        assert started['max_parallel_children'] == expected
        state = wait_job(parent, identifier, lambda value: len(value['current_children']) == expected)
        assert len(child.calls) == expected
        assert len(state['progress']['current_securities']) == expected
        # A settings edit does not alter the running request's frozen window.
        settings['research_concurrency'] = expected + 1
        assert parent.get(identifier, 'owner')['max_parallel_children'] == expected
        def release_until_completed(value):
            with child.lock:
                releases = list(child.releases.values())
            for release in releases:
                release.set()
            return value['status'] == 'completed'
        result = wait_job(parent, identifier, release_until_completed)
        assert len(child.calls) == len({key for keys in child.calls for key in keys}) == 7
        assert result['max_parallel_children'] == expected
    finally:
        def release_until_terminal(value):
            with child.lock:
                releases = list(child.releases.values())
            for release in releases:
                release.set()
            return value['status'] not in {'queued', 'running'}
        wait_job(parent, identifier, release_until_terminal)


def test_nested_country_coordinators_use_configured_admission_limit_and_deduplicate_fifth():
    Deferred.callbacks = []
    child = Children()
    child.settings = lambda: {}  # Production default is five.
    parent = PortfolioAIResearch(child, child, lambda *_: {}, worker_factory=Deferred)
    started = [parent.start('owner', {}, 'en', security_keys=[row(n)['security_key']], parent_request_id='outer')
               for n in range(1, 6)]
    assert len(Deferred.callbacks) == 5
    duplicate = parent.start('owner', {}, 'en', security_keys=[row(5)['security_key']], parent_request_id='outer')
    assert duplicate['request_id'] == started[4]['request_id']
    with pytest.raises(HTTPException) as full:
        parent.start('owner', {}, 'en', security_keys=[row(6)['security_key']], parent_request_id='outer')
    assert full.value.status_code == 409
    assert all(job['max_parallel_children'] == 5 for job in started)
