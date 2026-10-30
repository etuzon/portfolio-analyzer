"""Regressions for cached analytics across actual portfolio edits and refresh failures."""
from datetime import date, timedelta
from types import SimpleNamespace
import time
import pytest
from app import main
from app.local_portfolio import LocalPortfolioStore
from app.providers import MarketDataHub, SqliteCache
from app.models import Ohlcv

@pytest.fixture
def env(monkeypatch, tmp_path):
    store = LocalPortfolioStore(tmp_path/'local.sqlite3')
    hub = MarketDataHub.__new__(MarketDataHub)
    hub.config = {'primary':'sec_company_facts', 'fallback':['yahoo_finance'], 'yahoo_finance':{'enabled':True}}
    hub.db_config = {}
    hub.cache = SqliteCache(tmp_path/'market.sqlite3',24)
    hub.providers = hub._build_providers()
    calls=[]
    def offline(*args, **kwargs):
        calls.append(args)
        raise ConnectionError('isolated offline provider')
    for provider in hub.providers:
        for method in ('fundamentals','profile','dividends','prices'):
            monkeypatch.setattr(provider,method,offline)
    for symbol in ('FDUS','FMNB','UNB','BBDC','CMDB'):
        reports = {'income_statement':{'annualReports':[
            {'fiscalDateEnding':'2024-12-31','totalRevenue':100,'netIncome':10},
            {'fiscalDateEnding':'2025-12-31','totalRevenue':200,'netIncome':20}]}}
        hub.cache.set_security_snapshot('sec_company_facts',symbol,'fundamentals',reports)
        if symbol != 'CMDB':
            hub.cache.set_security_snapshot('yahoo_finance',symbol,'dividends',[
                {'date':'2024-06-30','amount':1},{'date':'2025-06-30','amount':2}])
            hub.cache.set_security_snapshot('yahoo_finance',symbol,'profile',{'market_cap':1000,'industry':'Banks'})
        hub.cache.set_prices('yahoo_finance',symbol,[Ohlcv(date.today()-timedelta(days=i),10,12,9,11,11,100) for i in range(35,-1,-1)])
    monkeypatch.setattr(main,'local_store',store)
    monkeypatch.setattr(main,'hub',lambda:hub)
    monkeypatch.setattr(main,'portfolio_cache_path',lambda:tmp_path/'portfolio.json')
    monkeypatch.setattr(main,'_portfolio_cache',None)
    monkeypatch.setattr(main,'_portfolio_refresh_in_progress',False)
    monkeypatch.setattr(main,'_portfolio_refresh_failure',None)
    monkeypatch.setattr(main,'_portfolio_cache_generation',0)
    monkeypatch.setattr(main,'_portfolio_refresh_progress',None)
    monkeypatch.setattr(main,'schedule_portfolio_refresh',lambda:True)
    monkeypatch.setattr(main,'_resolve_supported_stock_market',lambda *a:('NASDAQ',{}))
    account = main.save_local_account({'type':'Investment','location':'USA','currency':'USD','username':'QA','account_id':'QA-1','persons':[{'name':'QA Owner','birth_date':'01/01/1990'}]})
    def add(symbol='FDUS',qty=10):
        return main.add_local_security({'account_db_id':account['id'],'action':'BUY','symbol':symbol,'stock_market':'NASDAQ','asset_class':'EQUITY','quantity':qty,'price_input':20,'trade_date':'2026-01-01','allow_manual':True})
    return SimpleNamespace(store=store,hub=hub,account=account,add=add,tmp=tmp_path,calls=calls)

def assert_financials(item, symbol='FDUS'):
    assert item['income_trend']['current']==200
    assert item['profit_trend']['current']==20
    if symbol != 'CMDB':
        assert item['dividend_trend']['current']==2
        assert item['profit_market_cap_trend']['current']==.02
    else:
        assert item['dividend_trend']['current'] is None
        assert item['profit_market_cap_trend']['current'] is None
        assert item['market_cap'] is None


def test_first_response_reconstructs_available_market_data_without_provider_io(env,monkeypatch):
    for symbol in ('FDUS','FMNB','UNB','BBDC','CMDB'): env.add(symbol)
    # No aggregated portfolio cache exists: saved raw market data alone must work.
    start=time.monotonic()
    result=main.portfolio_payload(defer_enrichment=True)
    assert time.monotonic()-start<2
    assert result['refresh_pending'] is True
    assert env.calls==[], 'deferred response invoked live provider methods'
    for item in result['items']: assert_financials(item,item['holding']['symbol'])


def test_actual_edit_reload_account_edit_add_delete_keep_cached_financials(env):
    tx=env.add()
    seed=main.portfolio_payload(force_refresh=True)
    assert_financials(seed['items'][0])
    env.calls.clear()
    main.update_local_security(tx['id'],{'quantity':3,'price_input':30})
    after=main.portfolio_payload(defer_enrichment=True)
    item=after['items'][0]
    assert item['holding']['quantity']==3
    assert item['holding']['cost_basis']==90
    assert_financials(item)
    main.save_local_account({**env.account,'username':'Changed QA','management_company':'Changed broker'})
    after=main.portfolio_payload(defer_enrichment=True)
    assert 'Changed QA' in after['items'][0]['holding']['account']
    assert_financials(after['items'][0])
    assert env.calls==[], 'edit/reload invoked live provider methods'
    extra=env.add('FMNB',2)
    after=main.portfolio_payload(defer_enrichment=True)
    assert {x['holding']['symbol'] for x in after['items']}=={'FDUS','FMNB'}
    for x in after['items']: assert_financials(x)
    main.delete_local_security(tx['id'])
    after=main.portfolio_payload(defer_enrichment=True)
    assert [x['holding']['symbol'] for x in after['items']]==['FMNB']
    assert_financials(after['items'][0])
    assert env.calls==[], 'edit/reload invoked live provider methods'


def test_worker_does_not_publish_a_payload_for_changed_source_revision(env,monkeypatch):
    tx=env.add()
    original=main.enriched_local_holdings
    def change_during_refresh(**kwargs):
        if kwargs.get("cached_only"):
            return original(**kwargs)
        analyses=original(**kwargs)
        main.update_local_security(tx['id'],{'quantity':4})
        return analyses
    monkeypatch.setattr(main,'enriched_local_holdings',change_during_refresh)
    main._refresh_portfolio_cache()
    cached=main._portfolio_cache
    assert not cached or cached.get('signature')==main.portfolio_cache_signature(), 'worker published invalidated source revision'
    result=main.portfolio_payload(defer_enrichment=True)
    assert result['items'][0]['holding']['quantity']==4
    assert_financials(result['items'][0])


def test_provider_failures_do_not_establish_false_terminal_absence(env,monkeypatch):
    env.add('ABSENT')
    main._refresh_portfolio_cache()
    monkeypatch.setattr(main,'schedule_portfolio_refresh',lambda:False)
    result=main.portfolio_payload(defer_enrichment=True)
    assert result['refresh_state']=='failed', 'all provider failures reported as completed missing data'
    assert result['refresh_pending'] is False
    item=result['items'][0]
    for key in ('income_trend','profit_trend','dividend_trend','profit_market_cap_trend'):
        assert item[key]['state']=='error'
        assert item[key]['current'] is None


def test_failed_worker_retains_saved_evidence_and_explicit_refresh_retries(env,monkeypatch):
    env.add()
    original=main.enriched_local_holdings
    def fail_worker(**kwargs):
        if kwargs.get('cached_only'): return original(**kwargs)
        raise ConnectionError('isolated worker failure')
    monkeypatch.setattr(main,'enriched_local_holdings',fail_worker)
    main._refresh_portfolio_cache()
    monkeypatch.setattr(main,'schedule_portfolio_refresh',lambda:False)
    result=main.portfolio_payload(defer_enrichment=True)
    assert result['refresh_state']=='failed'
    assert result['refresh_pending'] is False
    assert_financials(result['items'][0])
    attempts=[]
    monkeypatch.setattr(main,'schedule_portfolio_refresh',lambda:attempts.append(True) or True)
    retried=main.portfolio(refresh=True)
    assert attempts==[True]
    assert retried['refresh_state']=='refreshing'
    assert retried['refresh_pending'] is True
    assert_financials(retried['items'][0])


def test_tase_listing_does_not_borrow_bare_us_ticker_profile_or_financials(env):
    tx=env.add()
    env.hub.cache.set_security_snapshot('sec_company_facts','FDUS','profile',{'name':'US Fixture Company','sector':'US Fixture Sector','industry':'US Fixture Industry'})
    env.store.update_transaction(tx['id'],{'stock_market':'TASE','currency':'ILS','location':'Israel'})
    main.clear_portfolio_cache()
    result=main.portfolio_payload(defer_enrichment=True)
    item=result['items'][0]
    assert item['income_trend']['current'] is None
    assert item['holding'].get('name')!='US Fixture Company'
    assert item['holding'].get('sector')!='US Fixture Sector'
    assert item.get('industry')!='US Fixture Industry'
    main._refresh_portfolio_cache()
    completed = main.portfolio_payload(defer_enrichment=True)['items'][0]
    assert completed['income_trend']['current'] is None
    assert completed['holding'].get('name') != 'US Fixture Company'
    assert completed.get('industry') != 'US Fixture Industry'

def test_completed_success_with_no_history_is_terminal_missing_not_failure(env,monkeypatch):
    env.add('ABSENT')
    for provider in env.hub.providers:
        for method in ('fundamentals','profile'):
            monkeypatch.setattr(provider,method,lambda *a,**k:{})
        for method in ('dividends','prices'):
            monkeypatch.setattr(provider,method,lambda *a,**k:[])
    main._refresh_portfolio_cache()
    result=main.portfolio_payload(defer_enrichment=True)
    assert result['refresh_state']=='ready'
    assert result['refresh_pending'] is False
    for key in ('income_trend','profit_trend','dividend_trend','profit_market_cap_trend'):
        assert result['items'][0][key]['state']=='missing'
        assert result['items'][0][key]['current'] is None


def test_invalidation_generation_discards_worker_even_with_unchanged_signature(env,monkeypatch):
    env.add()
    original=main.enriched_local_holdings
    def invalidate_during_refresh(**kwargs):
        analyses=original(**kwargs)
        main.clear_portfolio_cache()
        return analyses
    monkeypatch.setattr(main,'enriched_local_holdings',invalidate_during_refresh)
    main._refresh_portfolio_cache()
    assert main._portfolio_cache is None
    assert not main.portfolio_cache_path().exists()


def test_move_transaction_account_and_date_rebuilds_scope_without_losing_evidence(env):
    tx=env.add()
    main.portfolio_payload(force_refresh=True)
    target=main.save_local_account({'type':'Investment','location':'USA','currency':'USD','username':'Target QA','account_id':'QA-2','persons':[{'name':'Other Owner','birth_date':'01/02/1991'}]})
    main.update_local_security(tx['id'],{'account_db_id':target['id'],'trade_date':'01/02/2026','quantity':4,'price_input':25})
    result=main.portfolio_payload(defer_enrichment=True)
    assert len(result['items'])==1
    item=result['items'][0]
    assert item['holding']['account_id']==target['id']
    assert item['holding']['account_id']!=env.account['id']
    assert 'Target QA' in item['holding']['account']
    assert item['holding']['quantity']==4
    assert item['holding']['cost_basis']==100
    assert env.store.list_transactions()[0]['trade_date']=='2026-02-01'
    assert_financials(item)


def test_worker_completion_during_request_returns_completed_data_not_stale_preview(env,monkeypatch):
    env.add()
    main._portfolio_cache={'signature':main.portfolio_cache_signature(),'expires_at':0,'payload':{
        'status':{},'items':[{'holding':{'symbol':'FDUS'},'profit_trend':{'state':'missing','current':None}}]}}
    def finish_existing_worker():
        main._portfolio_cache={'signature':main.portfolio_cache_signature(),'expires_at':time.time()+900,'payload':{
            'status':{},'items':[{'holding':{'symbol':'FDUS'},'profit_trend':{'state':'ok','current':20}}]}}
        main._portfolio_refresh_in_progress=False
        return False
    monkeypatch.setattr(main,'schedule_portfolio_refresh',finish_existing_worker)
    result=main.portfolio_payload(defer_enrichment=True)
    assert result['refresh_pending'] is False
    assert result['items'][0]['profit_trend']['current']==20


def test_completed_security_updates_while_another_security_is_still_running(env,monkeypatch):
    from threading import Event, Thread
    from app.metrics import analyze_holding
    env.add('FDUS');env.add('UNB')
    release = Event()
    def provider(holding, hub):
        if hub is env.hub and holding.symbol == 'UNB':
            release.wait(2)
        result = analyze_holding(holding, env.hub.cached_view())
        if hub is env.hub and holding.symbol == 'FDUS':
            result.profit_trend.current = 999
        return result
    monkeypatch.setattr(main,'analyze_holding',provider)
    monkeypatch.setattr(main,'schedule_portfolio_refresh',lambda:False)
    monkeypatch.setattr(main,'_portfolio_refresh_in_progress',True)
    worker=Thread(target=main._refresh_portfolio_cache)
    worker.start()
    try:
        deadline=time.monotonic()+1.5
        while time.monotonic()<deadline:
            progress=main._portfolio_refresh_progress or {}
            if progress.get('completed') == 1:
                break
            time.sleep(.005)
        payload=main.portfolio_payload(defer_enrichment=True)
        rows={item['holding']['symbol']:item for item in payload['items']}
        assert rows['FDUS']['analytics_state']=='ready'
        assert rows['FDUS']['profit_trend']['current']==999
        assert rows['UNB']['analytics_state']=='updating'
        assert payload['refresh_progress']=={'total':2,'completed':1,'failed':0}
        assert payload['refresh_pending'] is True
    finally:
        release.set();worker.join(3)
    assert not worker.is_alive()


def test_unreadable_aggregate_cache_is_recoverable(monkeypatch):
    def denied():
        raise PermissionError("Synthetic unreadable cache")
    monkeypatch.setattr(main,'portfolio_cache_path',lambda:SimpleNamespace(exists=lambda:True,read_text=denied))
    assert main.read_portfolio_cache() is None
