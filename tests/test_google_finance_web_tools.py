"""Actual Google Finance rendered text shape; no live networking in regressions."""
import io
import json
from copy import deepcopy
from urllib.parse import urlsplit

import pytest

from app.security_research_tools import ResearchSession, WebRequestBudget, fetch_research_document, ResearchFailure
from app.security_source_context import context_records
from app.security_web_research import validate_proposals

URL = 'https://www.google.com/finance/beta/quote/CEL:TLV?hl=en'
CANDIDATE = {'security_key':'1101534|TASE|ILS','symbol':'1101534','secondary_symbol':'CEL',
             'stock_market':'TASE','currency':'ILS','asset_class':'RSU','name':'סלקום',
             'missing_fields':['profile'],'needs_name':False,'needs_industry':True}
TEXT = '''Cellcom Israel Ltd (CEL) Stock Price & News - Google Finance
Finance
CEL
Research
CEL:TLV
check_indeterminate_small
Add to list
Cellcom Israel Ltd
ILA 2,901.00
About Cellcom Israel Ltd
CEO
Eli Adadi
Sector
Communication Services
Industry
Telecommunications
Website
cellcom.co.il
Previous reports
All values in ILS
'''


def source(text=TEXT, url=URL):
    return {'url':url,'text':text,'source_id':'google-primary','retrieved_at':'2026-11-08T19:55:00+00:00','structured_data':[]}


def test_primary_industry_validates_with_exact_existing_ticker_mapping_only():
    src=source()
    record,=[r for r in context_records(src,CANDIDATE) if r.get('field')=='industry']
    proposal={'records':[{'security_key':CANDIDATE['security_key'],'source_id':src['source_id'],'record_id':record['record_id']}]}
    result=validate_proposals(proposal,{CANDIDATE['security_key']:CANDIDATE},{CANDIDATE['security_key']:[src]})
    accepted=result[CANDIDATE['security_key']]
    assert [(p['field'],p['value']) for p in accepted['profiles']]==[('industry','Telecommunications')]
    assert accepted['observations']==[] and not accepted['rejected']
    assert CANDIDATE['name']=='סלקום' and CANDIDATE['asset_class']=='RSU'


@pytest.mark.parametrize('changes', [{'secondary_symbol':''},{'secondary_symbol':'OTHER'},{'stock_market':'NYSE'},
                                     {'asset_class':'EMPLOYEE_STOCK_OPTION'},{'asset_class':'PRIVATE_STOCK'}])
def test_unverified_listing_or_private_grant_cannot_borrow_profile(changes):
    assert context_records(source(),{**CANDIDATE,**changes})==[]


@pytest.mark.parametrize('change', ['wrong_url','wrong_listing','foreign_primary','foreign_about','duplicate_industry','industry_only_after_reports'])
def test_related_or_ambiguous_source_sections_cannot_supply_industry(change):
    src=source()
    if change=='wrong_url': src['url']=URL.replace('CEL:','OTHER:')
    elif change=='wrong_listing': src['text']=TEXT.replace('CEL:TLV','OTHER:TLV')
    elif change=='foreign_primary': src['text']=TEXT.replace('CEL:TLV','CEL:TLV\nOTHER:NASDAQ')
    elif change=='foreign_about': src['text']=TEXT.replace('Industry\nTelecommunications\n','').replace('Previous reports','About Other Company\nIndustry\nWrong industry\nPrevious reports')
    elif change=='duplicate_industry':src['text']=TEXT.replace('Website','Industry\nOther industry\nWebsite')
    else:src['text']=TEXT.replace('Industry\nTelecommunications\n','').replace('Previous reports','Previous reports\nIndustry\nWrong industry')
    assert not [r for r in context_records(src,CANDIDATE) if r.get('field')=='industry']


def test_reader_modes_are_explicit_charged_and_do_not_mutate_configuration():
    used=[]
    def fetch(url,settings):
        used.append(settings['reader']);return source()
    session=ResearchSession({'reader':'jina'},WebRequestBudget(),fetch=fetch,resolver=lambda *args,**kwargs:[(2,1,6,'',('93.184.216.34',443))])
    hints=session.discover(CANDIDATE)
    assert hints[0]['url']==URL and session.budget.used==0
    for mode in ['compatible','direct']:
        session.read(CANDIDATE,hints[0]['source_id'],reader=mode)
    assert session.budget.used==2 and used==['compatible','direct'] and session.settings['reader']=='jina'
    with pytest.raises(ResearchFailure):session.read(CANDIDATE,hints[0]['source_id'],reader='shell')
    assert session.budget.used==2


@pytest.mark.parametrize('size,success', [(1_300_000,True),(2_000_001,False)])
def test_compatible_html_reader_has_bounded_body_no_cookies_and_no_script_execution(monkeypatch,size,success):
    from app import price_agent,security_research_tools as module
    body=('<script>'+('x'*size)+'</script><div>Industry</div><div>Telecommunications</div>').encode()
    calls=[]
    monkeypatch.setattr(price_agent,'_public_address',lambda url:(urlsplit(url),'93.184.216.34'))
    class Response:
        status=200
        def getheader(self,key,default=''):return 'text/html'
        def read(self,limit):return body[:limit]
    class Connection:
        def __init__(self,*args,**kwargs):pass
        def request(self,method,path,headers):calls.append((method,path,headers))
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr(module.http.client,'HTTPSConnection',Connection)
    if success:
        document=fetch_research_document(URL,{'reader':'auto'})
        assert document['reader']=='compatible' and document['text']=='Industry\nTelecommunications'
    else:
        with pytest.raises(ResearchFailure,match='size limit'):fetch_research_document(URL,{'reader':'auto'})
    assert len(calls)==1 and calls[0][0]=='GET'
    headers=calls[0][2]
    assert 'Mozilla' in headers['User-Agent'] and not {'Cookie','Authorization'}&headers.keys()
