"""Research scope discovery must not depend on market analytics/cache locks."""
from dataclasses import dataclass
import sqlite3
from types import SimpleNamespace

import pytest
from app import main
from app.models import Holding
from app.providers import SqliteCache


@dataclass
class StoredPosition:
    holding: Holding


def position(symbol, quantity=1, market='NYSE', asset='EQUITY', currency='USD'):
    return StoredPosition(Holding(symbol=symbol, quantity=quantity, stock_market=market,
                                  asset_class=asset, currency=currency))


@pytest.mark.parametrize('category', ['risk_inputs', 'country_ratings'])
def test_auxiliary_only_inventory_survives_exclusive_market_cache_writer(tmp_path, monkeypatch, category):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    path=tmp_path/'market-cache.sqlite3'
    SqliteCache(path, ttl_hours=24)
    rows=[position('SYNTHETIC')]
    monkeypatch.setattr(main, 'local_store', SimpleNamespace(holdings=lambda **_: rows))
    original_connect=sqlite3.connect
    def short_connect(*args, **kwargs):
        kwargs['timeout']=.02
        return original_connect(*args, **kwargs)
    monkeypatch.setattr(sqlite3, 'connect', short_connect)
    with original_connect(path) as writer:
        writer.execute('begin exclusive')
        try:
            assert main._portfolio_ai_inventory(data_types=[category], refresh_policy='stale') == {
                'market_items': [], 'credit_items': []}
        finally:
            writer.rollback()


@pytest.mark.parametrize('scope', ['open', 'all'])
def test_scope_keys_use_recorded_positions_without_market_analytics(monkeypatch, scope):
    rows=[position('LONG'), position('SHORT', -2), position('CLOSED', 0),
          position('LONG'), position('LONG', currency='ILS'),
          position('CASH', asset='CASH'), position('PRIVATE', market='PRIVATE'),
          position('EMPLOYEE', asset='EMPLOYEE_STOCK_OPTION')]
    calls=[]
    def holdings(**options):
        calls.append(options)
        return rows if options.get('include_closed') else [row for row in rows if row.holding.quantity]
    monkeypatch.setattr(main, 'local_store', SimpleNamespace(holdings=holdings))
    def forbidden(*args, **kwargs):
        raise AssertionError('Research scope depends on market analytics')
    monkeypatch.setattr(main, 'hub', forbidden)
    monkeypatch.setattr(main, 'enriched_local_holdings', forbidden)
    expected={'LONG|NYSE|USD', 'SHORT|NYSE|USD', 'LONG|NYSE|ILS'}
    if scope=='all': expected.add('CLOSED|NYSE|USD')
    assert main._enrichment_scope_keys(scope)==expected
    expected_options = {'include_closed': True} if scope == 'all' else {}
    assert calls == [expected_options]
