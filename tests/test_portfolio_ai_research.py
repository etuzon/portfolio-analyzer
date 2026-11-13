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
    def settings(self):return {'max_tool_loops':20,'max_rest_calls':20,'max_web_calls':20}
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
