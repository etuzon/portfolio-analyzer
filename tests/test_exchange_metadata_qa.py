"""Independent exchange metadata QA with synthetic providers and isolated caches."""
from copy import deepcopy
from types import SimpleNamespace
import time

import pytest

from app import main
from app.config import AppConfig
from app.local_portfolio import LocalPortfolioStore
from app.metrics import analyze_holding, to_dict
from app.models import Holding
from app.portfolio_refresh import attach_market_analysis, security_key
from test_financial_loading import env as financial_env


class SyntheticProfileHub:
    def __init__(self, exchange='Nasdaq'):
        self.exchange = exchange
        self.calls = []

    def prices(self, *args, **kwargs):
        self.calls.append(('prices', kwargs))
        return [], {'synthetic': 'missing'}

    def fundamentals(self, *args, **kwargs):
        self.calls.append(('fundamentals', kwargs))
        return {}, {'synthetic': 'missing'}

    def dividends(self, *args, **kwargs):
        self.calls.append(('dividends', kwargs))
        return [], {'synthetic': 'missing'}

    def profile(self, *args, **kwargs):
        self.calls.append(('profile', kwargs))
        return {'exchange': self.exchange, 'name': 'Synthetic company', 'industry': 'Financial services'}, {'synthetic': 'ok'}


def _holding():
    return Holding(symbol='FDUS', stock_market='YAHOO', platform='YAHOO', data_source='LOCAL', currency='USD', account_id='qa-owner', quantity=8, market_value=960, cost_basis=800)


def _analysis(exchange='Nasdaq'):
    return analyze_holding(_holding(), SyntheticProfileHub(exchange))


@pytest.fixture
def exchange_env(monkeypatch, tmp_path):
    store = LocalPortfolioStore(tmp_path / 'qa.sqlite3')
    cache_calls = []
    def cached_profile(symbol, **context):
        cache_calls.append((symbol, context))
        return {'exchange': 'Nasdaq', 'industry': 'Financial services'}
    hub = SimpleNamespace(cached_profile=cached_profile)
    monkeypatch.setattr(main, 'local_store', store)
    monkeypatch.setattr(main, 'hub', lambda: hub)
    monkeypatch.setattr(main, 'config', AppConfig(raw={}, path=tmp_path/'unused.yaml'))
    monkeypatch.setattr(main, 'portfolio_cache_path', lambda: tmp_path/'portfolio.json')
    monkeypatch.setattr(main, '_portfolio_cache', None)
    monkeypatch.setattr(main, '_portfolio_refresh_in_progress', False)
    monkeypatch.setattr(main, '_portfolio_refresh_failure', None)
    monkeypatch.setattr(main, '_portfolio_refresh_progress', None)
    monkeypatch.setattr(main, 'schedule_portfolio_refresh', lambda: True)
    return SimpleNamespace(store=store, patch=monkeypatch, hub=hub, calls=cache_calls)


def test_profile_exchange_survives_metrics_attach_and_serialization_without_rewriting_identity(exchange_env):
    local = _analysis('')
    market_hub = SyntheticProfileHub(' Nasdaq ')
    market = analyze_holding(deepcopy(local.holding), market_hub)
    assert market.exchange == 'Nasdaq'
    assert all(context == {'stock_market':'YAHOO', 'secondary_symbol':''} for _, context in market_hub.calls)
    before = deepcopy(local.holding)
    attached = attach_market_analysis(local, market)
    assert attached.exchange == 'Nasdaq'
    assert attached.holding == before
    assert attached.holding is not local.holding
    payload = main._serialized_portfolio_payload([attached], 'synthetic')
    item = payload['items'][0]
    assert item['exchange'] == 'Nasdaq'
    assert {key:item['holding'][key] for key in ('stock_market','platform','data_source')} == {'stock_market':'YAHOO','platform':'YAHOO','data_source':'LOCAL'}
    assert item['holding']['quantity'] == 8
    assert item['holding']['market_value'] == 960


def test_saved_profile_exchange_is_in_first_cached_response_and_reload_without_provider_io(exchange_env):
    env = exchange_env
    old = _analysis('')
    env.patch.setattr(main, 'enriched_local_holdings', lambda **kwargs: [deepcopy(old)])
    token = env.store.change_token()
    # Simulate an aggregate saved by the previous schema, with no exchange field.
    old_item = to_dict(old)
    old_item.pop('exchange')
    main.write_portfolio_cache({'signature': 'v7:'+token, 'expires_at':time.time()+3600, 'payload':{'items':[old_item]}})
    first = main.portfolio_payload(defer_enrichment=True)
    assert first['items'][0]['exchange'] == 'Nasdaq'
    assert first['items'][0]['holding']['stock_market'] == 'YAHOO'
    assert first['refresh_pending'] is True
    assert env.calls
    assert env.store.change_token() == token
    # Publish and reload the new aggregate from disk with the process cache empty.
    main.write_portfolio_cache({'signature':main.portfolio_cache_signature(),'expires_at':time.time()+3600,'payload':first})
    env.patch.setattr(main,'_portfolio_cache',None)
    env.patch.setattr(main,'enriched_local_holdings',lambda **kwargs:pytest.fail('Valid saved aggregate should not rebuild'))
    env.patch.setattr(main,'hub',lambda:pytest.fail('Valid aggregate reload should not access providers'))
    reloaded = main.portfolio_payload(defer_enrichment=True)
    assert reloaded['status']['portfolio_cache'] == 'hit'
    assert reloaded['items'][0]['exchange'] == 'Nasdaq'
    assert reloaded['items'][0]['holding']['stock_market'] == 'YAHOO'


def test_true_unknown_exchange_stays_unknown_and_does_not_invent_a_listing(exchange_env):
    env = exchange_env
    env.patch.setattr(main,'hub',lambda:SimpleNamespace(cached_profile=lambda *args,**kwargs:{}))
    item = main._serialized_portfolio_payload([_analysis('')], 'synthetic')['items'][0]
    assert item['exchange'] == ''
    assert item['holding']['stock_market'] == 'YAHOO'
    assert item['holding']['platform'] == 'YAHOO'
    assert item['holding']['data_source'] == 'LOCAL'


def test_ready_progress_result_copies_exchange_while_other_securities_are_still_loading(exchange_env):
    env = exchange_env
    analysis = _analysis('')
    baseline = {'items':[to_dict(analysis)]}
    completed = to_dict(_analysis('Nasdaq'))
    key = security_key(analysis.holding)
    env.patch.setattr(main,'_portfolio_refresh_progress',{'total':2,'completed':1,'failed':0,'states':{key:'ready'},'results':{key:completed}})
    result = main._portfolio_loading_state(baseline, 'refreshing')
    assert result['refresh_pending'] is True
    assert result['items'][0]['analytics_state'] == 'ready'
    assert result['items'][0]['exchange'] == 'Nasdaq'
    assert result['items'][0]['holding']['stock_market'] == 'YAHOO'


def test_real_saved_market_cache_reconstructs_exchange_on_cold_and_reloaded_response(financial_env):
    env = financial_env
    transaction = env.add()
    env.store.update_transaction(transaction['id'], {'stock_market':'YAHOO'})
    env.hub.cache.set_security_snapshot('sec_company_facts','FDUS','profile',{'exchange':'Nasdaq','market_cap':1000,'industry':'Financial services'})
    before = deepcopy(env.store.list_transactions())
    token = env.store.change_token()
    result = main.portfolio_payload(defer_enrichment=True)
    item = result['items'][0]
    assert item['exchange'] == 'Nasdaq'
    assert item['holding']['stock_market'] == 'YAHOO'
    assert env.calls == [], 'Deferred cached exchange enrichment must not invoke live provider methods'
    assert env.store.list_transactions() == before
    assert env.store.change_token() == token
    # A second browser request can reconstruct the same saved evidence without
    # waiting for provider refresh or an aggregate cache to be published.
    again = main.portfolio_payload(defer_enrichment=True)
    assert again['items'][0]['exchange'] == 'Nasdaq'
    assert again['items'][0]['holding']['stock_market'] == 'YAHOO'
    assert env.calls == []


def test_approved_assistant_summary_exposes_exchange_without_rewriting_filter_identity(exchange_env):
    env = exchange_env
    item = to_dict(_analysis('Nasdaq'))
    env.patch.setattr(main,'portfolio_payload',lambda **kwargs:{'items':[deepcopy(item)]})
    result = main.assistant_portfolio_summary(symbol='FDUS',stock_market='YAHOO',limit=25,offset=0)
    assert result['items'][0]['exchange'] == 'Nasdaq'
    assert result['items'][0]['holding']['stock_market'] == 'YAHOO'
    assert main.assistant_portfolio_summary(symbol='FDUS',stock_market='NASDAQ',limit=25,offset=0)['items'] == []


def test_ui_uses_exchange_after_real_holding_venue_and_never_displays_provider_as_venue():
    from pathlib import Path
    import re
    import subprocess
    source=(Path(__file__).resolve().parents[1]/'web/app.js').read_text()
    functions=[]
    for name in ('isProviderName','cleanSourceLabel','stockMarketDisplay'):
        start=re.search(rf'^function {name}\(',source,re.M).start()
        end=re.search(r'^}',source[start:],re.M).end()
        functions.append(source[start:start+end])
    script="const assert=require('node:assert/strict');const optionLabel=value=>value;\n"+'\n'.join(functions)+'''
const h={stock_market:'YAHOO',platform:'YAHOO',data_source:'LOCAL'};
assert.equal(stockMarketDisplay(h,'YAHOO','Nasdaq'),'NASDAQ');
assert.equal(stockMarketDisplay({...h,stock_market:'NYSE'},'YAHOO','Nasdaq'),'NYSE');
assert.equal(stockMarketDisplay(h,'YAHOO',''),'Not available');
assert.equal(stockMarketDisplay(h,'YAHOO','yahoo_finance'),'Not available');
assert.equal(h.stock_market,'YAHOO');
'''
    result=subprocess.run(['node'],input=script,text=True,capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr
