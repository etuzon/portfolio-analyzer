"""Independent raw-contract tests for automatic API price application.

Synthetic evidence and memory-only stores: no portfolio databases or network.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

from app.api_price_updates import bond_price_records
from app.local_portfolio import normalize_price

CUSIP = '91282CKD2'


def raw_contract():
    metadata = {'symbol': CUSIP, 'stock_market': 'MANUAL', 'currency': 'USD', 'asset_class': 'BOND', 'location': 'USA'}
    candidate = {**metadata, 'data_source': 'LOCAL', 'quantity': 1000}
    row = {'price_date': (date.today()-timedelta(days=1)).isoformat(), 'price': 98.5, 'currency': 'USD',
           'quote_unit': 'percent_of_par', 'price_basis': 'valuation', 'side': 'valuation', 'source_url': 'https://www.treasurydirect.gov/'}
    snapshot = {'status': 'partial', 'cache_status': 'fresh', 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'security': {'kind': 'bond', 'cusip': CUSIP, 'currency': 'USD'}, 'provider': 'treasury_direct', 'items': [row]}
    return candidate, metadata, snapshot


def records(candidate,metadata,snapshot,existing=()):
    return bond_price_records(candidate,metadata,snapshot,list(existing),date(2020,1,1))


def test_raw_per_hundred_becomes_one_face_unit_price_once_with_provenance():
    candidate,metadata,snapshot=raw_contract()
    before=deepcopy(snapshot)
    rows=records(candidate,metadata,snapshot)
    assert len(rows)==1 and rows[0]['price_input']==98.5
    assert normalize_price(rows[0]['price_input'],'USA','BOND')==.985
    assert candidate['quantity']*normalize_price(rows[0]['price_input'],'USA','BOND')==985
    evidence=json.loads(rows[0]['comments'])
    assert evidence['raw_price']==98.5 and evidence['quote_unit']=='percent_of_par'
    assert evidence['price_basis']=='valuation' and evidence['side']=='valuation'
    assert evidence['quantity_convention']=='USD_1_face_per_recorded_unit'
    assert snapshot==before and snapshot['status']=='partial'


@pytest.mark.parametrize('change',[
    {'data_source':'IMPORT'}, {'data_source':'EXTERNAL'}, {'data_source':''},
])
def test_imported_or_unknown_quantity_contract_is_reference_only(change):
    candidate,metadata,snapshot=raw_contract();candidate.update(change)
    assert records(candidate,metadata,snapshot)==[]


@pytest.mark.parametrize('change',[
    {'currency':'EUR'}, {'asset_class':'OTHER','asset_sub_class':'BOND'}, {'location':'France'},
    {'symbol':'5139324'},
])
def test_currency_primary_asset_location_and_identifier_must_support_mapping(change):
    candidate,metadata,snapshot=raw_contract();metadata.update(change)
    assert records(candidate,metadata,snapshot)==[]


def test_existing_dates_are_untouched_and_newer_current_remains_current():
    candidate,metadata,snapshot=raw_contract()
    old=snapshot['items'][0]['price_date']
    existing=[{'price_date':old,'price_input':107},{'price_date':date.today().isoformat(),'price_input':108}]
    assert records(candidate,metadata,snapshot,existing)==[]
    rows=records(candidate,metadata,snapshot,existing[1:])
    assert len(rows)==1 and rows[0]['price_date']==old
    assert max(existing[1:]+rows,key=lambda r:r['price_date'])['price_input']==108
    assert existing[0]['price_input']==107


@pytest.mark.parametrize('age,accepted',[(7,True),(8,False),(-1,False)])
def test_fresh_current_requirement_uses_observation_day_not_retrieval(age,accepted):
    candidate,metadata,snapshot=raw_contract()
    snapshot['items'][0]['price_date']=(date.today()-timedelta(days=age)).isoformat()
    assert bool(records(candidate,metadata,snapshot)) is accepted


@pytest.mark.parametrize('change',[{'status':'stale'},{'cache_status':'stale'},{'security':{'kind':'bond','cusip':'037833AK6','currency':'USD'}}])
def test_stale_or_other_identity_never_applies(change):
    candidate,metadata,snapshot=raw_contract();snapshot.update(change)
    assert records(candidate,metadata,snapshot)==[]


@pytest.mark.parametrize('change',[{'price':0},{'price':True},{'price':float('nan')},{'quote_unit':'currency_per_unit'},{'currency':'EUR'},{'price_basis':'yield'}])
def test_unverified_numeric_scale_currency_or_basis_remains_reference_only(change):
    candidate,metadata,snapshot=raw_contract();snapshot['items'][0].update(change)
    assert records(candidate,metadata,snapshot)==[]

from test_us_bond_portfolio_reference import bond_application


@pytest.fixture
def staged_bond(bond_application,monkeypatch):
    main,state=bond_application
    state.local_rows=[]
    state.saved_prices=[]
    state.preferences={}
    original=main.local_store
    class Store:
        manual_security=original.manual_security
        price_history=original.price_history
        def save_prices(self,rows,*,only_missing=False):
            state.only_missing=only_missing
            if only_missing:
                occupied={row['price_date'] for row in state.local_rows}
                rows=[row for row in rows if row['price_date'] not in occupied]
            state.saved_prices.extend(deepcopy(rows))
            return [{**row,'price':normalize_price(row['price_input'],row['location'],row['asset_class'])} for row in rows]
        def set_preference(self,name,value):state.preferences[name]=deepcopy(value)
    monkeypatch.setattr(main,'local_store',Store())
    monkeypatch.setattr(main,'enriched_local_holdings',lambda **_:[{'holding':deepcopy(state.security)}])
    monkeypatch.setattr(main,'_enrichment_outcomes',lambda:[])
    monkeypatch.setattr(main,'_record_log',lambda *_a,**_k:None)
    monkeypatch.setattr(main,'security_enrichment',SimpleNamespace(get=lambda *_a:{}))
    candidate={**state.security,'security_key':CUSIP+'|MANUAL|USD','missing_fields':['prices','reference']}
    monkeypatch.setattr(main,'_enrichment_candidates',lambda **_:{'items':[deepcopy(candidate)] if state.security['quantity'] else []})
    return main,state,candidate


def test_preflight_get_stages_only_and_authorized_finalizer_applies_once(staged_bond):
    main,state,candidate=staged_bond
    outcome=main._enrichment_fetch_security(candidate,'auto')
    assert outcome['code']=='api_price_ready' and outcome['research_eligible'] is False
    assert state.saved_prices==[] and len(state.calls)==1
    result=main._save_enrichment_outcomes([outcome],'qa-owner','qa-request')
    assert len(state.saved_prices)==1 and len(state.calls)==1  # Finalize reads cache only.
    assert state.only_missing is True
    saved=state.saved_prices[0]
    assert saved['price_input']==99.34
    assert normalize_price(saved['price_input'],saved['location'],saved['asset_class'])==pytest.approx(.9934)
    assert json.loads(saved['comments'])['quote_unit']=='percent_of_par'
    assert result[0]['code']=='data_found' and 'prices' in result[0]['available_fields']


def test_close_after_staging_prevents_actual_price_write(staged_bond):
    main,state,candidate=staged_bond
    outcome=main._enrichment_fetch_security(candidate,'auto')
    state.security['quantity']=0
    result=main._save_enrichment_outcomes([outcome],'qa-owner','qa-request')
    assert state.saved_prices==[] and len(state.calls)==1
    assert result[0]['status']=='not_attempted' and result[0]['code']=='not_open'


def test_currency_contract_changed_after_staging_prevents_save(staged_bond):
    main,state,candidate=staged_bond
    outcome=main._enrichment_fetch_security(candidate,'auto')
    state.security['currency']='EUR'
    result=main._save_enrichment_outcomes([outcome],'qa-owner','qa-request')
    assert state.saved_prices==[] and result[0]['code']!='data_found'


def test_manual_price_added_after_staging_is_not_overwritten(staged_bond):
    main,state,candidate=staged_bond
    outcome=main._enrichment_fetch_security(candidate,'auto')
    day=next(iter(state.cache.saved.values()))['items'][0]['price_date']
    state.local_rows=[{'price_date':day,'price_input':107,'price':1.07}]
    main._save_enrichment_outcomes([outcome],'qa-owner','qa-request')
    assert state.saved_prices==[] and state.local_rows[0]['price_input']==107


def test_close_during_final_cache_read_is_rechecked_before_write(staged_bond,monkeypatch):
    main,state,candidate=staged_bond
    outcome=main._enrichment_fetch_security(candidate,'auto')
    original=main._bond_market_data
    def closing_read(*args,**kwargs):
        result=original(*args,**kwargs)
        state.security['quantity']=0
        return result
    monkeypatch.setattr(main,'_bond_market_data',closing_read)
    result=main._save_enrichment_outcomes([outcome],'qa-owner','qa-request')
    assert state.saved_prices==[], 'A position closed before the final application-owned write'
    assert result[0]['code']!='data_found'


@pytest.mark.parametrize('quantity,raw,basis,side',[(1000,99.34,'programme_redemption','programme_redemption_bid'),(-1000,99.35,'programme_purchase','programme_purchase_mean')])
def test_programme_fallback_uses_actual_signed_side_not_generic_bid_ask(quantity,raw,basis,side):
    candidate,metadata,snapshot=raw_contract();candidate['quantity']=quantity
    snapshot['items'][0].update(end_of_day_price=None,programme_purchase_price=99.35,programme_redemption_price=99.34)
    row=records(candidate,metadata,snapshot)[0]
    evidence=json.loads(row['comments'])
    assert row['price_input']==raw and evidence['price_basis']==basis and evidence['side']==side


@pytest.mark.parametrize('quantity,basis,side',[(1000,'programme_purchase','programme_purchase_mean'),(-1000,'programme_redemption','programme_redemption_bid')])
def test_available_opposite_side_retains_its_actual_basis_under_fallback_policy(quantity,basis,side):
    candidate,metadata,snapshot=raw_contract();candidate['quantity']=quantity
    snapshot['items'][0].update(end_of_day_price=None,price_basis=basis,side=side)
    row=records(candidate,metadata,snapshot)[0]
    assert row['price_input']==98.5
    evidence=json.loads(row['comments'])
    assert evidence['price_basis']==basis and evidence['side']==side


def test_actual_short_candidate_keeps_signed_quantity_for_reference_side_policy(bond_application,monkeypatch):
    main,state=bond_application
    state.security['quantity']=-6
    monkeypatch.setattr(main,'enriched_local_holdings',lambda **_:[{'holding':deepcopy(state.security),'missing':['price history'],'price_ranges':{}}])
    monkeypatch.setattr(main,'_enrichment_outcomes',lambda:[])
    candidate=main._enrichment_candidates()['items'][0]
    assert candidate['quantity']==-6
    snapshot=main._bond_market_data(candidate)
    rows=records(candidate,state.security,snapshot)
    assert rows[0]['price_input']==99.35 and json.loads(rows[0]['comments'])['side']=='programme_purchase_mean'

from app.api_price_updates import fund_price_records


def fund_contract():
    candidate,metadata,snapshot=raw_contract()
    metadata.update(symbol='5139324',stock_market='TASE',currency='ILS',asset_class='MUTUALFUND',location='Israel')
    candidate.update(metadata)
    snapshot.update(provider='maya',source_url='https://maya.tase.co.il/api/v1/funds/mutual/5139324',
                    security={'fund_id':'5139324','kind':'fund','deleted':False,'dollar_denominated':False,'is_international':False,'fund_subtype':1})
    snapshot['items'][0].update(price=108.99,quote_unit='agorot',currency='ILS',price_basis='redemption',side='redemption',
        source_url=snapshot['source_url'],observed_at=None)
    return candidate,metadata,snapshot


def fund_records(candidate,metadata,snapshot,existing=()):
    return fund_price_records(candidate,metadata,snapshot,list(existing),date(2020,1,1))


def test_domestic_fund_redemption_agorot_is_not_stock_close_or_nominal_multiple():
    candidate,metadata,snapshot=fund_contract()
    snapshot['details']={'nominal_value':10}
    snapshot['items'][0]['price']=1200.27
    rows=fund_records(candidate,metadata,snapshot)
    assert rows[0]['price_input']==1200.27
    assert normalize_price(rows[0]['price_input'],'Israel','MUTUALFUND')==pytest.approx(12.0027)
    evidence=json.loads(rows[0]['comments'])
    assert evidence['price_basis']=='redemption' and evidence['quote_unit']=='agorot' and evidence['observed_at'] is None


@pytest.mark.parametrize('change',[{'fund_id':'5119813'},{'deleted':True},{'dollar_denominated':True},{'dollar_denominated':None},{'is_international':True}])
def test_other_deleted_foreign_or_unknown_fund_cannot_receive_ils_price(change):
    candidate,metadata,snapshot=fund_contract();snapshot['security'].update(change)
    assert fund_records(candidate,metadata,snapshot)==[]


@pytest.mark.parametrize('change',[{'quote_unit':'unknown'},{'currency':None},{'price_basis':'purchase'},{'price_basis':'close'},{'price':True}])
def test_unqualified_fund_quote_never_becomes_supported_redemption(change):
    candidate,metadata,snapshot=fund_contract();snapshot['items'][0].update(change)
    assert fund_records(candidate,metadata,snapshot)==[]


def test_fund_preserves_same_day_manual_observation_and_newer_current():
    candidate,metadata,snapshot=fund_contract()
    day=snapshot['items'][0]['price_date']
    existing=[{'price_date':day,'price_input':123},{'price_date':date.today().isoformat(),'price_input':124}]
    assert fund_records(candidate,metadata,snapshot,existing)==[]
    assert existing[0]['price_input']==123 and existing[1]['price_input']==124


@pytest.fixture
def staged_fund(staged_bond,monkeypatch):
    main,state,candidate=staged_bond
    _,metadata,snapshot=fund_contract()
    state.security.update(metadata)
    candidate.update(metadata,security_key='5139324|TASE|ILS',missing_fields=['prices'])
    state.fund_reads=[]
    state.fund_snapshot=snapshot
    def fund_data(identifier,**kwargs):
        state.fund_reads.append((identifier,kwargs))
        return deepcopy(state.fund_snapshot)
    monkeypatch.setattr(main,'_israeli_fund_data',fund_data)
    return main,state,candidate


def test_fund_get_stages_without_key_or_model_then_finalize_saves_actual_redemption(staged_fund):
    main,state,candidate=staged_fund
    outcome=main._enrichment_fetch_security(candidate,'auto')
    assert outcome['code']=='api_price_ready' and outcome['research_eligible'] is False and state.saved_prices==[]
    result=main._save_enrichment_outcomes([outcome],'qa-owner','qa-request')
    assert len(state.saved_prices)==1 and result[0]['code']=='data_found'
    row=state.saved_prices[0]
    assert row['price_input']==108.99 and normalize_price(row['price_input'],'Israel','MUTUALFUND')==pytest.approx(1.0899)
    assert json.loads(row['comments'])['price_basis']=='redemption'
    assert state.fund_reads[-1][1].get('cache_only') is True
    assert state.calls==[]  # A numeric fund never went to the stock or US-bond provider.


def test_closed_fund_between_get_and_finalize_has_no_save(staged_fund):
    main,state,candidate=staged_fund
    outcome=main._enrichment_fetch_security(candidate,'auto')
    state.security['quantity']=0
    result=main._save_enrichment_outcomes([outcome],'qa-owner','qa-request')
    assert state.saved_prices==[] and result[0]['code']=='not_open'


def test_fund_becoming_foreign_currency_between_get_and_finalize_has_no_save(staged_fund):
    main,state,candidate=staged_fund
    outcome=main._enrichment_fetch_security(candidate,'auto')
    state.security['currency']='USD'
    result=main._save_enrichment_outcomes([outcome],'qa-owner','qa-request')
    assert state.saved_prices==[] and result[0]['code']!='data_found'


@pytest.mark.parametrize('source,age,current_age,expected',[
    ('api_evidence',1,1,'treasury_direct'),
    ('api_evidence',2,1,None),
    ('manual',1,1,None),
])
def test_valuation_provider_badge_requires_same_actual_api_mark_day_and_value(bond_application,monkeypatch,source,age,current_age,expected):
    main,state=bond_application
    row={**state.security,'source':source,'price_date':(date.today()-timedelta(days=age)).isoformat(),
         'price':.985,'comments':json.dumps({'kind':'price_evidence_v1','provider':'treasury_direct'})}
    monkeypatch.setattr(main.local_store,'list_prices',lambda:[row],raising=False)
    item={'holding':deepcopy(state.security),'price_ranges':{'1y':{'current':.985,'current_date':(date.today()-timedelta(days=current_age)).isoformat()}}}
    result=main._serialized_portfolio_payload([item],'cached')['items'][0]
    assert result.get('valuation_price_provider')==expected
    assert state.calls==[]


def test_atomic_only_missing_preserves_manual_row_added_after_provider_read(tmp_path):
    from app.local_portfolio import LocalPortfolioStore
    store=LocalPortfolioStore(tmp_path/'synthetic-only-missing.sqlite3')
    candidate,metadata,snapshot=raw_contract()
    staged=records(candidate,metadata,snapshot)
    day=staged[0]['price_date']
    # A user fills the date after the provider's missing-date read, before save.
    manual=store.save_price({**metadata,'price_input':107,'price_date':day,'source':'manual','comments':'User supplied while research was running'})
    earlier={**staged[0],'price_date':(date.fromisoformat(day)-timedelta(days=1)).isoformat(),'price_input':98}
    saved=store.save_prices(staged+[earlier],only_missing=True)
    assert len(saved)==1 and saved[0]['price_date']==earlier['price_date']
    rows=store.price_history(CUSIP,'MANUAL')
    current=next(row for row in rows if row['price_date']==day)
    assert current['id']==manual['id'] and current['price_input']==107 and current['source']=='manual'
    assert current['comments']=='User supplied while research was running'
    # Existing manual-edit callers retain their explicit replacement behavior.
    replaced=store.save_prices([{**metadata,'price_input':108,'price_date':day,'source':'manual'}])
    assert replaced[0]['price_input']==108


def test_atomic_zero_write_race_does_not_count_a_price_update(staged_bond,monkeypatch):
    main,state,candidate=staged_bond
    outcome=main._enrichment_fetch_security(candidate,'auto')
    def concurrent_manual_fill(rows,*,only_missing=False):
        assert only_missing is True
        state.local_rows=[{'price_date':row['price_date'],'price_input':107,'source':'manual'} for row in rows]
        return []
    monkeypatch.setattr(main.local_store,'save_prices',concurrent_manual_fill)
    result=main._save_enrichment_outcomes([outcome],'qa-owner','qa-request')
    assert state.saved_prices==[] and state.local_rows[0]['price_input']==107
    assert result[0]['status']=='not_attempted' and result[0]['code']=='already_available'
    assert result[0]['attempted'] is False and result[0]['available_fields']==[]
