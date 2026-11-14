"""Risk input provenance, normalized units, persistence and revision boundaries."""
from copy import deepcopy
from datetime import date, timedelta
import json
from types import SimpleNamespace
from pathlib import Path
import subprocess

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from app.local_portfolio import LocalPortfolioStore
from app.stress_risk_inputs import MODEL, StressRiskInputs, normalize_parameters, select_rating
from app import risk_history


def rating(grade="BBB", **updates):
    return {"agency":"sp", "rating":grade, "status":"rated", "scope":"issuer", "rating_type":"issuer",
        "scale":"global", "term":"long_term", "stale":False, "fetched_at":"2026-11-14T00:00:00Z",
        "source_kind":"issuer_ir", "entity_name":"Exact Legal Issuer", **updates}


@pytest.fixture
def environment(tmp_path):
    store = LocalPortfolioStore(tmp_path / 'risk.sqlite3')
    inventory=[dict(security_key="BOND|NYSE|USD",symbol="BOND",stock_market="NYSE",currency="USD",
        asset_class="BOND",asset_sub_class="BOND",issuer_name="Exact Legal Issuer",issuer_identity_verified=True)]
    public={"ratings":[rating()]}
    sovereign={"ratings":[rating("AA",scope="sovereign",currency_basis="local_currency",source_kind="agency_public"),
        rating("A",scope="sovereign",currency_basis="foreign_currency",source_kind="agency_public")]}
    country={"country_code":"IL", "source_kind":"provider_profile"}
    service=StressRiskInputs(store=lambda:store,inventory=lambda:inventory,credit=lambda _:deepcopy(public),
        sovereign=lambda _:deepcopy(sovereign),countries=lambda _:deepcopy(country))
    return service,store,inventory,public,sovereign,country


def parameters(**updates):
    return dict(instrument_kind="sovereign_bond",pricing_model="zero_coupon_continuous",
        maturity_date=(date.today()+timedelta(days=2191)).isoformat(),current_spread_bps=100,
        sovereign_currency_basis="foreign_currency",zero_coupon_confirmed=True,
        plain_nominal_noncallable=True,as_of=date.today().isoformat(),notes="User checked legal terms",**updates)


def update(service, **params):
    current=service.read(service.inventory()[0])
    return service.update(dict(security_key=current["security_key"],expected_identity=current["identity_token"],
        expected_revision=current["revision"],parameters=parameters(**params)),{"id":"writer"})


def test_parameters_persist_with_units_and_never_verify_user_or_agency_facts(environment):
    service,store,inventory,*_=environment
    saved=update(service,continuous_yield=.05,country_currency="ils")
    assert saved["parameters"]["continuous_yield"]==.05
    assert saved["parameters"]["current_spread_bps"]==100
    assert saved["parameters"]["country_currency"]=="ILS"
    assert saved["parameter_provenance"]["verification_status"]=="user_entered"
    assert saved["sovereign_rating"]["bucket"]=="A"
    assert saved["issuer_id"]=="sovereign:IL"
    restarted=StressRiskInputs(store=lambda:LocalPortfolioStore(store.path),inventory=lambda:inventory,
        credit=service._credit,sovereign=service._sovereign,countries=service._countries)
    assert restarted.read(inventory[0])["parameters"]==saved["parameters"]


def test_revision_conflicts_identity_rebind_and_clear_are_preserved(environment):
    service,store,inventory,*_=environment
    before=service.read(inventory[0]);first=update(service)
    with pytest.raises(HTTPException) as e:
        service.update(dict(security_key=before['security_key'],expected_identity=before['identity_token'],expected_revision=0,parameters=parameters()),{"id":"writer"})
    assert e.value.status_code==409
    cleared=service.update(dict(security_key=first['security_key'],expected_identity=first['identity_token'],expected_revision=first['revision']),{"id":"writer"},clear=True)
    assert cleared['parameters']=={} and cleared['revision']==2
    with pytest.raises(HTTPException):
        service.update(dict(security_key=first['security_key'],expected_identity=first['identity_token'],expected_revision=first['revision']),{"id":"writer"},clear=True)
    update(service)
    inventory[0]['issuer_name']='Other Legal Issuer'
    assert service.read(inventory[0])['parameters']=={}
    with pytest.raises(HTTPException) as e:
        service.update(dict(security_key=first['security_key'],expected_identity=first['identity_token'],expected_revision=3,parameters=parameters()),{"id":"writer"})
    assert e.value.status_code==409


@pytest.mark.parametrize('field,value',[('continuous_yield',True),('current_spread_bps',-1),
    ('country_sensitivity',1.1),('country_sensitivity',False),('continuous_yield',float('nan')),
    ('continuous_yield',float('inf')),('plain_nominal_noncallable','true'),('zero_coupon_confirmed',1),
    ('as_of','2099-01-01'),('maturity_date','wrong'),('sovereign_currency_basis','USD'),
    ('instrument_kind','Treasury'),('pricing_model','duration'),('country_code','ZZ'),
    ('country_currency','NIS!'),('cashflows',[{'date':'2030-01-01','amount':True}])])
def test_invalid_financial_inputs_rejected_without_store_change(environment,field,value):
    service,store,*_=environment
    old=service.revision()
    params=parameters();params[field]=value
    current=service.read(service.inventory()[0])
    with pytest.raises(HTTPException) as e:
        service.update(dict(security_key=current['security_key'],expected_identity=current['identity_token'],expected_revision=0,parameters=params),{'id':'writer'})
    assert e.value.status_code==422 and service.revision()==old


def test_rating_selection_excludes_incomparable_stale_manual_and_default(environment):
    service,_,inventory,*_=environment
    rows=[rating('AA'),rating('BBB',agency='fitch',rating_type='issuer_default'),rating('B+',scope='issue'),
        rating('CCC',scale='national'),rating('CCC',stale=True),rating('CCC',manual_override=True),
        rating('CCC',term='short_term'),rating('CCC',scope='issuer',rating_type='deposit'),rating('D')]
    chosen=select_rating({'ratings':rows},inventory[0])
    assert chosen['bucket']=='B' and chosen['scope']=='issue'
    assert select_rating({'ratings':[rating('CCC',manual_override=True)]},inventory[0]) is None
    assert select_rating({'ratings':[rating('C',agency='moodys')]},inventory[0]) is None
    assert select_rating({'ratings':[rating('BBB',scope='sovereign',currency_basis='unknown')]},basis='foreign_currency',sovereign=True) is None
    assert service.read(inventory[0])['country']['country_code']=='IL'


def test_manual_effective_rating_is_estimate_only_with_preserved_provenance(environment):
    service,_,inventory,public,sovereign,*_=environment
    manual=rating('BB',source_kind='manual',manual_override=True,updated_at='2026-11-14T00:00:00Z',notes='User entry')
    public['ratings']=[manual]
    selected=service.read(inventory[0])
    assert selected['credit_rating'] is None
    estimate=selected['credit_rating_estimate']
    assert estimate['bucket']=='BB' and estimate['verified'] is False
    assert estimate['eligible_for_estimate'] is True and estimate['verification_status']=='user_entered'
    assert estimate['notes']=='User entry' and estimate['manual_override'] is True
    assert select_rating({'ratings':[{**manual,'scale':'national'}]},inventory[0],allow_manual=True) is None
    assert select_rating({'ratings':[{**manual,'status':'withdrawn'}]},inventory[0],allow_manual=True) is None
    assert select_rating({'ratings':[{**manual,'updated_at':'2099-01-01T00:00:00Z'}]},inventory[0],allow_manual=True) is None


def test_model_revision_changes_for_params_rating_country_and_clears(environment):
    service,store,inventory,public,sovereign,country=environment
    initial=service.revision();update(service)
    modified=service.revision();assert modified!=initial
    public['ratings'][0]['rating']='BB'
    new=service.revision();assert new!=modified
    sovereign['ratings'][1]['rating']='BBB'
    assert service.revision()!=new
    old=service.revision();country['country_code']='US';assert service.revision()!=old
    old=service.revision();inventory[0]['issuer_name']='New entity';assert service.revision()!=old


def test_input_routes_enforce_role_and_local_only(environment):
    service,store,*_=environment
    app=FastAPI()
    @app.middleware('http')
    async def actor(request,call_next):
        role=request.headers.get('x-role')
        request.state.auth_user={'id':'writer','role':role} if role else None
        return await call_next(request)
    app.include_router(service.router());client=TestClient(app)
    query='?symbol=BOND&stock_market=NYSE&currency=USD'
    assert client.get('/api/securities/risk-inputs'+query).status_code==401
    current=client.get('/api/securities/risk-inputs'+query,headers={'x-role':'Viewer'}).json()
    data=dict(security_key=current['security_key'],expected_identity=current['identity_token'],expected_revision=0,parameters=parameters())
    assert client.put('/api/securities/risk-inputs',json=data,headers={'x-role':'Viewer'}).status_code==403
    assert client.put('/api/securities/risk-inputs',json=data,headers={'x-role':'Operator'}).status_code==200
    assert client.get('/api/securities/risk-inputs'+query,headers={'x-role':'Viewer'}).json()['revision']==1


def test_v3_incomplete_history_keeps_v2_immutable_and_new_rating_inputs(tmp_path):
    store=LocalPortfolioStore(tmp_path/'history.sqlite3')
    account=dict(id='test',type='Investment',location='Israel',currency='ILS',initial_cash=100,account_id='test')
    old={'id':'old','observed_at':'2026-11-12T10:00:00Z','date':'2026-11-12','model':'portfolio-risk-v2',
        'base_currency':'ILS','source':risk_history.SOURCE,'accounts':[],
        'total':{'score':31,'components':{k:0 for k in risk_history._COMPONENTS}}}
    store.set_preference(risk_history.PREFIX+'legacy',old)
    inputs=risk_history.canonical_inputs([], [account], [], {'quotes':[]},'ILS')
    inputs['guard']=('source',1,'credit-revision')
    capture=lambda _:deepcopy(inputs)
    context=risk_history.create_context(store,'writer','ILS',capture)
    risk={'model':MODEL,'score':None,'status':'incomplete','components':{'stress_loss':0},
          'coverage':{'covered_value_percent':0,'complete':False},'gaps':[{'code':'credit_rating'}]}
    result=risk_history.save_observation(store,'writer',{'token':context['token'],'total':risk,'accounts':[{'account_id':account['id'],'risk':risk}]},capture,lambda:inputs['guard'])
    assert result['observation']['model']==MODEL and result['observation']['total']['score'] is None
    assert result['observation']['evidence']['risk_revision']=='credit-revision'
    history=risk_history.list_observations(store,'ILS',0)
    assert {row['model'] for row in history['items']}=={MODEL,'portfolio-risk-v2'}
    assert store.get_preference(risk_history.PREFIX+'legacy')==old


def test_v3_partial_never_becomes_numeric_and_nested_nonfinite_rejected():
    with pytest.raises(risk_history.RiskHistoryError):
        risk_history._risk({'model':MODEL,'status':'incomplete','score':0},MODEL)
    with pytest.raises(risk_history.RiskHistoryError):
        risk_history._risk({'model':MODEL,'status':'ok','score':30,'scenarios':[{'pnl':float('nan')}]},MODEL)


def test_portfolio_retries_changed_risk_inputs_before_publishing(monkeypatch):
    from app import main
    revisions=iter(['old','new','new','new'])
    captures=[]
    def enrich(items):
        version='old' if not captures else 'new'
        captures.append(version)
        return [{**row,'stress_risk':{'source_revision':version}} for row in items]
    fake=SimpleNamespace(revision=lambda:next(revisions),enrich=enrich)
    monkeypatch.setattr(main,'stress_risk_inputs',fake)
    monkeypatch.setattr(main,'portfolio_payload',lambda **kwargs:{'items':[{'holding':{'symbol':'TEST'}}]})
    result=main.portfolio()
    assert captures==['old','new']
    assert result['risk_revision']=='new'
    assert result['items'][0]['stress_risk']['source_revision']=='new'
    assert result['risk_model']==MODEL
    assert result['risk_as_of']==date.today().isoformat()


def test_portfolio_does_not_publish_unstable_risk_sources(monkeypatch):
    from app import main
    revisions=iter(['a','b','c','d'])
    fake=SimpleNamespace(revision=lambda:next(revisions),enrich=lambda items:deepcopy(items))
    monkeypatch.setattr(main,'stress_risk_inputs',fake)
    monkeypatch.setattr(main,'portfolio_payload',lambda **kwargs:{'items':[]})
    with pytest.raises(HTTPException) as error:
        main.portfolio()
    assert error.value.status_code==409 and error.value.detail=='portfolio_changed'


def test_actual_engine_insolvency_with_missing_bond_parameters_roundtrips_history(tmp_path):
    store=LocalPortfolioStore(tmp_path/'insolvent.sqlite3')
    account=dict(id='a',type='Investment',currency='ILS',initial_cash=-200,account_id='margin')
    item={'holding':{'account_id':'a','symbol':'BOND','asset_class':'BOND','currency':'ILS','quantity':1,'market_value':100},
          'stress_risk':{'valuation_date':'2026-11-14'}}
    program="""const risk=require('./web/stress-risk.js');
const result=risk.calculate(JSON.parse(process.argv[1]),{baseCurrency:'ILS',asOf:'2026-11-14',cashAccounts:[{value:-200,currency:'ILS'}]});
process.stdout.write(JSON.stringify(result));"""
    process=subprocess.run(['node','-e',program,json.dumps([item])],cwd=Path(__file__).resolve().parents[1],text=True,capture_output=True)
    assert process.returncode==0,process.stderr
    risk=json.loads(process.stdout)
    assert risk['score']==100 and risk['status']=='ok' and risk['net_equity']==-100
    assert risk['worst_scenario']=='nonpositive_equity'
    assert risk['coverage']['complete'] is False and risk['gaps']
    capture_data=risk_history.canonical_inputs([item],[account],[],{'quotes':[]},'ILS')
    capture_data['guard']=('source',1,'risk-facts')
    capture=lambda _:deepcopy(capture_data)
    context=risk_history.create_context(store,'writer','ILS',capture)
    result=risk_history.save_observation(store,'writer',{'token':context['token'],'total':risk,
        'accounts':[{'account_id':'a','risk':risk}]},capture,lambda:capture_data['guard'])
    assert result['saved'] is True
    stored=risk_history.list_observations(store,'ILS',0)['items'][0]['total']
    assert stored['score']==100 and stored['coverage']['complete'] is False
    assert stored['coverage']==risk['coverage'] and stored['gaps']==risk['gaps']
    for change in ({'score':99},{'net_equity':1},{'net_equity':None},{'worst_scenario':'inflation'}):
        with pytest.raises(risk_history.RiskHistoryError):
            risk_history._risk({**risk,**change},MODEL)


def test_unknown_coverage_percentage_preserved_only_for_incomplete_results():
    risk={'model':MODEL,'status':'incomplete','score':None,'components':{},
          'coverage':{'covered_value_percent':None,'complete':False},'gaps':[{'code':'valuation'}]}
    assert risk_history._risk(risk,MODEL)['coverage']['covered_value_percent'] is None
    assert risk_history._risk({**risk,'status':'unavailable'},MODEL)['score'] is None
    for change in ({'status':'ok','score':0},{'status':'estimate','estimated_score':0},
                   {'coverage':{'covered_value_percent':None,'complete':True}}):
        with pytest.raises(risk_history.RiskHistoryError):
            risk_history._risk({**risk,**change},MODEL)
