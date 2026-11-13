"""Normal AuthStore integration of all-position public-source rating research.

The common conftest guard isolates app imports; each test also owns its stores.
The model/public reader doubles exercise actual authenticated child REST tools.
"""
from copy import deepcopy
import json
from threading import Event
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from app import main, credit_ratings_api
from app.auth import AuthStore
from app.local_portfolio import LocalPortfolioStore
from app.providers import SqliteCache
from app.security_research_tools import ResearchSession, WebRequestBudget
from app.llm_assistant import PortfolioAssistant, assistant_settings

PATH='/api/securities/enrichment'


def login(auth,role='Operator',suffix='one'):
    username='qa-'+suffix
    auth.create_user({'username':username,'first_name':'Synthetic','last_name':'Reviewer','role':role,'password':'Initial-Synthetic-2026!'})
    client=TestClient(main.app,base_url='https://localhost:6443')
    signed=client.post('/api/auth/login',json={'username':username,'password':'Initial-Synthetic-2026!'})
    assert signed.status_code==200
    changed=client.post('/api/auth/change-password',headers={'X-CSRF-Token':signed.json()['csrf_token']},
        json={'current_password':'Initial-Synthetic-2026!','new_password':'Changed-Synthetic-2026!','confirm_password':'Changed-Synthetic-2026!'})
    assert changed.status_code==200
    return client,{'X-CSRF-Token':changed.json()['csrf_token']}


def poll(client,request_id,timeout=20):
    limit=time.monotonic()+timeout
    while time.monotonic()<limit:
        response=client.get(PATH+'/ai/'+request_id)
        assert response.status_code==200,response.text
        result=response.json()
        if result['status'] not in {'queued','running'}:
            return result
        time.sleep(.01)
    raise AssertionError('Parent workflow did not reach terminal status within isolated deterministic timeout')


@pytest.fixture
def env(tmp_path,monkeypatch):
    store=LocalPortfolioStore(tmp_path/'local.sqlite')
    auth=AuthStore(store.path);auth.initialize()
    cache=SqliteCache(tmp_path/'market.sqlite',ttl_hours=24)
    owners=[store.save_account({'type':'Investment','location':'USA','currency':'USD','username':name,'initial_cash':10000,
        'persons':[{'name':'Synthetic Owner','birth_date':'01/01/1990'}]}) for name in ('One','Two')]
    def transact(symbol,*,owner=0,action='BUY',quantity=2,day='2026-01-01',asset='EQUITY',market='NYSE',currency='USD'):
        return store.add_transaction({'account_db_id':owners[owner]['id'],'action':action,'symbol':symbol,
            'stock_market':market,'asset_class':asset,'currency':currency,'quantity':quantity,'price_input':10,
            'trade_date':day,'allow_manual':True})
    for symbol in ('QA1','QA2','QA3','QA4','QA5','QA6'):
        transact(symbol)
    transact('QASHORT',action='SHORT')
    transact('QA1',owner=1)
    transact('QACLOSED');transact('QACLOSED',action='SELL',day='2026-01-02')
    transact('QAPRIVATE',market='PRIVATE')
    transact('QAFUND',asset='ETF')
    store.save_manual_security({'symbol':'QAUNHELD','stock_market':'NYSE','asset_class':'EQUITY','currency':'USD','name':'Unheld Synthetic Corporation','location':'USA'})
    def profile(symbol,**kwargs):
        return {'name':'Synthetic '+symbol+' Corporation','website':'https://'+symbol.lower()+'.qa.example','industry':'Software'}
    monkeypatch.setattr(main,'local_store',store)
    monkeypatch.setattr(main,'auth_store',auth)
    monkeypatch.setattr(main,'hub',lambda:SimpleNamespace(cache=cache,cached_profile=profile))
    monkeypatch.setattr(main,'_record_log',lambda *args,**kwargs:None)
    monkeypatch.setattr(main,'clear_portfolio_cache',lambda:None)
    monkeypatch.setattr(main,'enriched_local_holdings',lambda *,cached_only=False,include_closed=False:store.holdings(include_closed=include_closed))
    monkeypatch.setattr(main,'_security_api_route',lambda _: {'owner':'api','provider':'synthetic-ordinary-price-api'})
    monkeypatch.setattr(main,'_bond_market_data',lambda *args,**kwargs:None)
    monkeypatch.setattr(main,'_us_fund_market_data',lambda *args,**kwargs:None)
    settings=assistant_settings({'llm':{'enabled':True,'provider':'openai','api_key':'synthetic-model-fixture-token','base_url':'https://never-called.invalid','model':'fixture'}})
    settings.update(max_tool_loops=8,max_rest_calls=8,max_web_calls=8)
    monkeypatch.setattr(main,'_enrichment_assistant_settings',lambda:settings)
    service=main.credit_rating_service
    monkeypatch.setattr(service,'_research_settings',lambda:{'search_provider':'auto','max_web_calls':8})
    monkeypatch.setattr(service,'_settings',lambda:{'verification_ttl_days':30,'spglobal':{'enabled':True,'bearer_token':'synthetic-licensed-token-must-not-be-used'}})
    def forbidden(*args,**kwargs):
        raise AssertionError('A licensed credit-rating API was invoked by public-source AI')
    monkeypatch.setattr(credit_ratings_api,'fetch',forbidden)
    sources=[];sessions={};model_messages=[];arrived=Event();release=Event()
    def get_session(candidate):
        request_id=candidate['_request_id']
        if request_id not in sessions:
            def fetch(url,settings):
                symbol=urlsplit(url).hostname.split('.')[0].upper();sources.append(symbol)
                text="Credit Ratings\nSynthetic "+symbol+" Corporation\n | Moody's | S&P | Fitch\nOutlook | Stable | Stable | Stable\nLong-term issuer rating | A1 | A | A\nSynthetic "+symbol+" Corporation Credit Ratings\n"
                return {'url':url,'title':'Synthetic issuer evidence','text':text}
            sessions[request_id]=ResearchSession({'search_provider':'auto'},WebRequestBudget(8),fetch=fetch,
                resolver=lambda *args,**kwargs:[(2,1,6,'',('93.184.216.34',443))])
        return sessions[request_id]
    monkeypatch.setattr(service,'_session',get_session)
    def model(self,*,messages,tools):
        model_messages.append(deepcopy(messages))
        assert {tool['function']['name'] for tool in tools}=={'search_security_sources','read_security_source','follow_security_source'}
        assert 'synthetic-licensed-token-must-not-be-used' not in json.dumps(messages)
        assert 'synthetic-model-fixture-token' not in json.dumps(messages)
        arrived.set();assert release.wait(5),'QA test failed to release deterministic model'
        active=[job for job in main.credit_rating_jobs._jobs.values() if job['status']=='running']
        assert len(active)==1,'Unexpected concurrent credit child jobs'
        job=active[0]
        for key,candidate in job['_candidates'].items():
            if not job['_evidence_by_key'].get(key):
                hints=candidate['source_hints'];assert hints,key
                return {'choices':[{'message':{'tool_calls':[{'id':'read-'+candidate['symbol'],
                    'function':{'name':'read_security_source','arguments':json.dumps({'security_key':key,'source_id':hints[0]['source_id']})}}]}}]}
        records=[{'security_key':key,'source_id':src['source_id'],'record_id':record['record_id']}
            for key,evidence in job['_evidence_by_key'].items() for src in evidence['evidence'] for record in src['context_records']]
        return {'choices':[{'message':{'content':json.dumps({'records':records})}}]}
    monkeypatch.setattr(PortfolioAssistant,'_call_provider',model)
    # All managers are process-local; this test module never attaches to live service state.
    for name in ('portfolio_ai_research','security_enrichment','credit_rating_jobs'):
        manager=getattr(main,name,None)
        if manager is not None and hasattr(manager,'_jobs'):manager._jobs.clear()
    main._login_failures.clear()
    client,headers=login(auth)
    return SimpleNamespace(store=store,auth=auth,service=service,client=client,headers=headers,
        sources=sources,model_messages=model_messages,arrived=arrived,release=release,
        expected={symbol+'|NYSE|USD' for symbol in ('QA1','QA2','QA3','QA4','QA5','QA6','QASHORT')})


def test_general_action_covers_all_unique_open_api_priced_stocks_through_normal_auth(env):
    candidate=env.service.candidate('QA1|NYSE|USD');context=env.service.read(candidate)
    saved=env.client.put('/api/securities/credit-ratings/manual',headers=env.headers,json={
        'security_key':candidate['security_key'],'agency':'fitch','status':'rated','rating':'BB+',
        'entity_name':candidate['issuer_name'],'notes':'Synthetic preserved manual opinion',
        'expected_identity':context['identity_token'],'expected_revision':0})
    assert saved.status_code==200,saved.text
    started=env.client.post(PATH+'/ai',headers=env.headers,json={'position_scope':'open'})
    assert started.status_code==202,started.text
    request_id=started.json()['request_id']
    assert env.arrived.wait(5)
    repeated=env.client.post(PATH+'/ai',headers=env.headers,json={'position_scope':'open'})
    assert repeated.status_code==202 and repeated.json()['request_id']==request_id
    env.release.set()
    result=poll(env.client,request_id)
    assert result['status']=='completed',result.get('failure')
    assert result['ratings_only'] is False
    ratings=result['credit_ratings']
    outcomes=ratings['outcomes']
    assert {row['security_key'] for row in outcomes}==env.expected
    assert len(outcomes)==len(env.expected)==7
    assert ratings['summary']['total_candidates']==7
    assert all(row['attempted'] for row in outcomes)
    assert all(set(row['verified_agencies'])=={'moodys','sp','fitch'} for row in outcomes)
    assert all(row['status']=='updated' for row in outcomes)
    assert len(env.sources)==7 and len(set(env.sources))==7
    for job in main.credit_rating_jobs._jobs.values():
        assert job['summary']['selected']<=3
        for axis in ('model','rest','web'):
            assert job['counts'][axis+'_requests']<=job['counts']['max_'+axis+'_requests']<=8
    context=env.service.read(candidate)
    assert next(r for r in context['ratings'] if r['agency']=='fitch')['rating']=='BB+'
    assert next(r for r in context['retrieved_ratings'] if r['agency']=='fitch')['rating']=='A'
    assert result['outcomes']==[], 'Ordinary API market-data route should remain separate from rating coverage'


def test_scope_and_real_auth_boundaries(env):
    anonymous=TestClient(main.app,base_url='https://localhost:6443')
    assert anonymous.post(PATH+'/ai',json={}).status_code==401
    viewer,viewer_headers=login(env.auth,role='Viewer',suffix='viewer')
    assert viewer.post(PATH+'/ai',headers=viewer_headers,json={}).status_code==403
    assert env.client.post(PATH+'/ai',json={}).status_code==403
    assert env.client.post(PATH+'/ai',headers=env.headers,json={'position_scope':'invalid'}).status_code==422
    env.release.set()
    started=env.client.post(PATH+'/ai',headers=env.headers,json={'position_scope':'all'})
    assert started.status_code==202,started.text
    identifier=started.json()['request_id']
    other,_=login(env.auth,suffix='other')
    assert other.get(PATH+'/ai/'+identifier).status_code==404
    result=poll(env.client,identifier)
    assert {row['security_key'] for row in result['credit_ratings']['outcomes']}==env.expected|{'QACLOSED|NYSE|USD'}
    assert 'QAUNHELD|NYSE|USD' not in {row['security_key'] for row in result['credit_ratings']['outcomes']}


def test_ratings_only_skips_market_inventory_and_children_and_locks_active_mode(env,monkeypatch):
    def forbidden_market_inventory(*args,**kwargs):
        raise AssertionError('Ratings-only research consulted the price/profile inventory')
    monkeypatch.setattr(main,'_ai_enrichment_candidates',forbidden_market_inventory)
    started=env.client.post(PATH+'/ai',headers=env.headers,json={'position_scope':'open','ratings_only':True})
    assert started.status_code==202,started.text
    request_id=started.json()['request_id']
    assert started.json()['ratings_only'] is True
    assert env.arrived.wait(5)
    changed=env.client.post(PATH+'/ai',headers=env.headers,json={'position_scope':'open','ratings_only':False})
    assert changed.status_code==409
    repeated=env.client.post(PATH+'/ai',headers=env.headers,json={'position_scope':'open','ratings_only':True})
    assert repeated.status_code==202 and repeated.json()['request_id']==request_id
    env.release.set()
    result=poll(env.client,request_id)
    assert result['status']=='completed' and result['ratings_only'] is True
    assert result['outcomes']==[] and result['summary']['total_candidates']==0
    assert {row['security_key'] for row in result['credit_ratings']['outcomes']}==env.expected
    assert not main.security_enrichment._jobs
    child_records=main.portfolio_ai_research._jobs[request_id]['_children']
    assert len(child_records)==7 and all(child['branch']=='credit' for child in child_records)
    for axis in ('model','rest','web'):
        assert result['counts'][axis+'_requests']==sum(child['job']['counts'][axis+'_requests'] for child in child_records)
    assert result['counts']['max_model_requests']==56 and result['counts']['web_requests']==7


def test_ratings_only_payload_validation_and_resume_mode_do_not_restart_completed_work(env,monkeypatch):
    for invalid in (None,{},[],'not-a-boolean'):
        rejected=env.client.post(PATH+'/ai',headers=env.headers,json={'ratings_only':invalid})
        assert rejected.status_code==422
    def forbidden_market_inventory(*args,**kwargs):
        raise AssertionError('Ratings-only research consulted the price/profile inventory')
    monkeypatch.setattr(main,'_ai_enrichment_candidates',forbidden_market_inventory)
    # A model configuration failure leaves public research unattempted. Resume
    # must preserve its captured mode; it cannot silently add market work.
    settings=deepcopy(main._enrichment_assistant_settings());settings['enabled']=False
    monkeypatch.setattr(main,'_enrichment_assistant_settings',lambda:settings)
    started=env.client.post(PATH+'/ai',headers=env.headers,json={'position_scope':'open','ratings_only':True})
    assert started.status_code==202
    request_id=started.json()['request_id']
    result=poll(env.client,request_id)
    assert result['status']=='failed' and result['credit_ratings']['summary']['not_attempted']==7
    before=len(main.credit_rating_jobs._jobs)
    changed=env.client.post(PATH+'/ai',headers=env.headers,json={
        'position_scope':'open','ratings_only':False,'resume_request_id':request_id})
    assert changed.status_code==409
    assert len(main.credit_rating_jobs._jobs)==before and not main.security_enrichment._jobs


def test_company_inventory_excludes_fund_subtypes_even_with_broad_equity_class(monkeypatch):
    common={'stock_market':'NYSE','currency':'USD','asset_class':'EQUITY','name':'Synthetic fund or company'}
    registered=[{**common,'symbol':'FUND'+str(n),'instrument_type':kind} for n,kind in enumerate(('ETF','FUND','MUTUALFUND','MUTUAL_FUND'))]
    registered += [{**common,'symbol':'SUBFUND'+str(n),'asset_sub_class':kind} for n,kind in enumerate(('ETF','FUND','MUTUALFUND','MUTUAL_FUND'))]
    registered.append({**common,'symbol':'FDUS','instrument_type':'STOCK','name':'Fidus Investment Corporation'})
    monkeypatch.setattr(main,'local_store',SimpleNamespace(list_manual_securities=lambda:registered,holdings=lambda **kwargs:[]))
    monkeypatch.setattr(main,'hub',lambda:SimpleNamespace(cached_profile=lambda symbol,**kwargs:
        {'name':'Fidus Investment Corporation','industry':'Closed-End Funds'} if symbol=='FDUS' else {}))
    assert {candidate['symbol'] for candidate in main._credit_rating_inventory()}=={'FDUS'}


def test_bond_issuer_trust_requires_exact_controlled_provenance_and_preserves_manual_issue(tmp_path,monkeypatch):
    from app.credit_rating_service import CreditRatingService
    from app.manual_credit_ratings import manual_policy
    common={'stock_market':'MANUAL','currency':'USD','asset_class':'BOND','instrument_type':'BOND'}
    records=[{**common,'symbol':'121899CH9','name':'BRK3.2%01/01/2045'},
        {**common,'symbol':'91282CKD2','name':'Synthetic Treasury holding'}]
    refs={
        '121899CH9':{'provider':'finnhub','source_url':'https://finnhub.io/api/v1/bond/profile',
            'security':{'identifier':'121899CH9','cusip':'121899CH9','issuer':'BRK3.2%01/01/2045'}},
        '91282CKD2':{'provider':'treasury_direct','source_url':'https://www.treasurydirect.gov/TA_WS/securities/91282CKD2',
            'security':{'identifier':'91282CKD2','cusip':'91282CKD2','issuer':'United States Department of the Treasury'}}}
    monkeypatch.setattr(main,'local_store',SimpleNamespace(list_manual_securities=lambda:records,holdings=lambda **kwargs:[]))
    monkeypatch.setattr(main,'hub',lambda:SimpleNamespace(cached_profile=lambda *args,**kwargs:{}))
    def cached_reference(candidate,*,cache_only=False):
        assert cache_only
        return deepcopy(refs[candidate['symbol']])
    monkeypatch.setattr(main,'_bond_market_data',cached_reference)
    inventory={candidate['symbol']:candidate for candidate in main._credit_rating_inventory()}
    informal,treasury=inventory['121899CH9'],inventory['91282CKD2']
    assert informal['issuer_name']=='BRK3.2%01/01/2045' and not informal['issuer_identity_verified']
    assert manual_policy(informal)['canonical_issuer_name'] is None and manual_policy(informal)['issue_rating_allowed']
    assert treasury['issuer_identity_verified'] and manual_policy(treasury)['canonical_issuer_name']=='United States Department of the Treasury'
    for invalid in ({'source_url':'https://treasurydirect.gov.example.org/fixture'},
                    {'security':{**refs['91282CKD2']['security'],'identifier':'121899CH9'}}):
        saved=deepcopy(refs['91282CKD2']);refs['91282CKD2'].update(invalid)
        assert not next(candidate for candidate in main._credit_rating_inventory() if candidate['symbol']=='91282CKD2')['issuer_identity_verified']
        refs['91282CKD2']=saved
    cache=SqliteCache(tmp_path/'market.sqlite',ttl_hours=24);store=LocalPortfolioStore(tmp_path/'manual.sqlite')
    service=CreditRatingService(cache=lambda:cache,settings=lambda:{},inventory=lambda:list(inventory.values()),
        research_settings=lambda:{},manual_store=lambda:store)
    context=service.read(informal)
    saved=service.save_manual({'security_key':informal['security_key'],'agency':'fitch','status':'rated','rating':'BBB+',
        'scope':'issue','entity_name':'Synthetic verified-by-user legal issuer',
        'notes':'Independent synthetic manual QA, not a reported financial fact',
        'expected_identity':context['identity_token'],'expected_revision':0},{'username':'qa-operator'})
    manual=next(row for row in saved['ratings'] if row['agency']=='fitch')
    assert manual['entity_id']=='121899CH9' and manual['scope']=='issue' and manual['identity_verification']=='user_entered'
    assert manual['source_kind']=='manual' and all(row['status']=='not_checked' for row in saved['retrieved_ratings'])


def test_public_openapi_uses_parent_ratings_mode_schema_and_retains_child_rest_routes():
    schema=main.app.openapi()
    start=schema['paths'][PATH+'/ai']['post']['requestBody']['content']['application/json']['schema']
    assert '#/components/schemas/PortfolioResearchStart' in json.dumps(start)
    mode=schema['components']['schemas']['PortfolioResearchStart']['properties']['ratings_only']
    assert mode['type']=='boolean' and mode['default'] is False
    def expanded(routes):
        for route in routes:
            nested=getattr(route,'original_router',None)
            if nested is not None:
                yield from expanded(nested.routes)
            else:
                yield route
    effective=list(expanded(main.app.routes))
    for suffix,method in (('/ai','POST'),('/ai/{request_id}','GET'),('/status','GET')):
        routes=[route for route in effective if getattr(route,'path',None)==PATH+suffix and method in getattr(route,'methods',set())]
        assert len(routes)==1
    for suffix in ('/candidates','/web/search','/web/read','/web/follow'):
        assert any(getattr(route,'path',None)==PATH+suffix for route in effective)
