"""The public reference is evidence for one country axis, not company FX."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from app.country_currency_reference import CountryCurrencyReference, SIX_CURRENCY_URL, currency_reference_records
from app.local_portfolio import LocalPortfolioStore
from app.risk_input_retrieval import RiskEvidenceResearch
from app.risk_input_sources import extract_proposed_risk_records, extract_risk_records
from app.stress_risk_inputs import StressRiskInputs


def row(country='UNITED STATES OF AMERICA (THE)', currency='USD', *, fund=False):
    return f'<CcyNtry><CtryNm>{country}</CtryNm><CcyNm IsFund="{str(fund).lower()}">Currency</CcyNm><Ccy>{currency}</Ccy><CcyNbr>840</CcyNbr><CcyMnrUnts>2</CcyMnrUnts></CcyNtry>'


def xml(*rows, published='2026-09-17'):
    return f'<?xml version="1.0" encoding="UTF-8"?><ISO_4217 Pblshd="{published}"><CcyTbl>'+''.join(rows)+'</CcyTbl></ISO_4217>'


def source(body=None):
    return {'url':SIX_CURRENCY_URL, 'retrieved_at':datetime.now(timezone.utc).isoformat(),
        'text':body or xml(row(),row(currency='USN',fund=True))}


def test_reference_verifies_only_exact_country_currency_and_exact_row():
    document=source()
    records=extract_risk_records(document,{'country_code':'US'})
    assert len(records)==1
    result=records[0]
    assert (result['field'],result['value'],result['country_code'])==('country_currency','USD','US')
    assert result['evidence_quote']==row()
    assert result['as_of']==result['reference_published_at']=='2026-09-17'
    assert result['units']=='iso4217_currency_code'
    assert result['source_kind']=='standards_public'
    claim={key:deepcopy(result[key]) for key in ('field','value','as_of','units','evidence_quote')}
    assert extract_proposed_risk_records(document,{'country_code':'US'},claim)==records
    for field,value in (('country_currency','EUR'),('currency_exposures',{'USD':1}),('country_code','US')):
        assert extract_proposed_risk_records(document,{'country_code':'US'},{**claim,'field':field,'value':value})==[]
    assert currency_reference_records(document,{'country_code':'IL'})==[]
    assert currency_reference_records(document,{})==[]
    assert currency_reference_records({**document,'url':'https://example.org/forged.xml'},{'country_code':'US'})==[]


def test_reference_never_chooses_first_ordinary_currency_and_rejects_duplicate_tags():
    assert not currency_reference_records(source(xml(row(),row(currency='EUR'))),{'country_code':'US'})
    assert currency_reference_records(source(xml(row(),row())),{'country_code':'US'})[0]['value']=='USD'
    malformed=row().replace('<Ccy>USD</Ccy>','<Ccy>USD</Ccy><Ccy>EUR</Ccy>')
    assert not currency_reference_records(source(xml(malformed)),{'country_code':'US'})
    assert not currency_reference_records(source(xml(row().replace('IsFund="false"','IsFund="unknown"'))),{'country_code':'US'})


def test_publication_cutoff_is_not_the_retrieval_date():
    document=source()
    assert not currency_reference_records(document,{'country_code':'US','captured_at':'2026-09-16T00:00:00Z'})
    assert currency_reference_records(document,{'country_code':'US','captured_at':'2026-09-18T00:00:00Z'})
    assert not currency_reference_records(source(xml(row(),published=(date.today()+timedelta(days=1)).isoformat())),{'country_code':'US'})
    assert not currency_reference_records(source('<!DOCTYPE ISO_4217>'+xml(row())),{'country_code':'US'})


def test_public_cache_preserves_real_dates_on_failure_and_never_redirects():
    calls=[];clock=[0];fail=[False]
    def fetch(request):
        calls.append(request)
        assert str(request.url)==SIX_CURRENCY_URL
        assert 'authorization' not in request.headers
        if fail[0]:
            return httpx.Response(503)
        return httpx.Response(200,text=xml(row()))
    reader=CountryCurrencyReference(transport=httpx.MockTransport(fetch),clock=lambda:clock[0],refresh_seconds=10)
    first=reader.fetch_document(SIX_CURRENCY_URL,{})
    cached=reader.fetch_document(SIX_CURRENCY_URL,{})
    assert len(calls)==1 and cached['reference_cache_status']=='cached'
    assert first['retrieved_at']==cached['retrieved_at']
    fail[0]=True;clock[0]=11
    saved=reader.fetch_document(SIX_CURRENCY_URL,{})
    assert saved['reference_cache_status']=='refresh_failed_using_saved'
    assert saved['retrieved_at']==first['retrieved_at']
    assert saved['reference_published_at']==first['reference_published_at']
    empty=CountryCurrencyReference(transport=httpx.MockTransport(lambda _:httpx.Response(302,headers={'Location':'https://example.com'})))
    with pytest.raises(ValueError,match='currency_reference_unavailable'):
        empty.fetch_document(SIX_CURRENCY_URL,{})


@pytest.fixture
def environment(tmp_path):
    store=LocalPortfolioStore(tmp_path/'risk.sqlite3')
    item={'symbol':'EXM','stock_market':'NASDAQ','currency':'USD','asset_class':'BOND',
        'security_key':'EXM|NASDAQ|USD','issuer_name':'Example Corporation','issuer_identity_verified':True,'has_open_position':True}
    country={'country_code':'US','source_kind':'manual'}
    inputs=StressRiskInputs(store=lambda:store,inventory=lambda:[item],credit=lambda _: {},
        sovereign=lambda _: {},countries=lambda _:deepcopy(country))
    return inputs,item,country


def test_bound_reference_cannot_refresh_market_inputs_or_supply_company_allocation(environment):
    inputs,item,country=environment
    reference=currency_reference_records(source(),{'country_code':'US'})
    old=(date.today()-timedelta(days=30)).isoformat()
    inputs.publish_evidence(item,[{'field':'continuous_yield','value':.04,'as_of':old,'basis':'reported'},
        {'field':'current_spread_bps','value':100,'as_of':old,'basis':'reported'}])
    inputs.publish_evidence(item,reference)
    risk=inputs.read(item)
    assert risk['parameters']['country_currency']=='USD'
    assert risk['parameters']['as_of']==old
    assert risk['currency_exposures'] is None and risk['country_exposures'] is None
    assert 'country_currency' not in inputs.read(item,as_of='2026-09-16')['parameters']
    country['country_code']='IL'
    assert 'country_currency' not in inputs.read(item)['parameters']
    raw=inputs.read(item)
    inputs.update({'security_key':raw['security_key'],'expected_identity':raw['identity_token'],
        'expected_revision':raw['revision'],'parameters':{'country_currency':'ILS','as_of':date.today().isoformat(),'notes':'Explicit currency override'}},{'id':'writer'})
    assert inputs.read(item)['parameters']['country_currency']=='ILS'


def test_research_read_selects_later_official_country_row_and_publishes_within_budget(environment):
    inputs,item,_=environment
    # The desired row lies past the old 40,000-character opening window.
    body=xml(*(row('ISRAEL','ILS') for _ in range(350)),row(),row(currency='USN',fund=True))
    assert body.index('UNITED STATES')>40000
    adapter=CountryCurrencyReference(transport=httpx.MockTransport(lambda _:httpx.Response(200,text=body)))
    research=RiskEvidenceResearch(inputs,lambda:{'max_web_calls':8},reference_reader=adapter)
    candidate={**research.candidates()['items'][0],'_request_id':'request'}
    session=research._session(candidate)
    session._resolver=lambda *_a,**_k:[(2,1,6,'',('93.184.216.34',443))]
    hints=research.research_tool(candidate,'discover',{})['sources']
    reference=next(h for h in hints if h['url']==SIX_CURRENCY_URL)
    initial=research.research_tool(candidate,'read',{'source_id':reference['source_id']})['evidence'][0]
    assert not initial['context_records']
    evidence=research.research_tool(candidate,'read',{'source_id':reference['source_id'],'query':'UNITED STATES'})['evidence'][0]
    record=evidence['context_records'][0]
    assert record['value']=='USD' and evidence['document_window']['start']>40000
    outcomes=research.finalize([], 'owner','request',proposal={'records':[
        {'security_key':item['security_key'],'source_id':evidence['source_id'],'record_id':record['record_id']}]},
        evidence_by_key={item['security_key']:[initial,evidence]},candidates={item['security_key']:candidate})
    assert inputs.read(item)['parameters']['country_currency']=='USD'
    assert outcomes[0]['sources'][0]['reference_published_at']=='2026-09-17'
    assert session.budget.used==2
