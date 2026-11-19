"""Independent full-backup acceptance for committed and uncommitted WAL state."""
import json
import sqlite3
from types import SimpleNamespace
import zipfile

from app import main
from app.providers import SqliteCache


def test_full_backup_is_self_contained_during_uncommitted_market_writer(tmp_path, monkeypatch):
    data_root = tmp_path / 'data'
    data_root.mkdir()
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('dashboard:\n  base_currency: USD\n')
    monkeypatch.setenv('DATA_DIR', str(data_root))
    monkeypatch.setattr(main, 'config', SimpleNamespace(path=config_path))
    store = main.LocalPortfolioStore(data_root / 'local-portfolio.sqlite3')
    store.set_preference('qa_retained_portfolio', {'source': 'synthetic committed local data'})
    monkeypatch.setattr(main, 'local_store', store)
    cache = SqliteCache(data_root / 'market-cache.sqlite3', ttl_hours=24)
    writer = sqlite3.connect(cache.path)
    writer.execute('pragma wal_autocheckpoint=0')
    writer.execute('pragma wal_checkpoint(truncate)')
    committed = {'name': 'Synthetic Committed Issuer', 'observation_date': '2026-11-01'}
    writer.execute('insert into security_snapshot values (?, ?, ?, ?, ?)',
        ('qa', 'COMMITTED', 'profile', 1, json.dumps(committed)))
    writer.commit()
    wal = data_root / 'market-cache.sqlite3-wal'
    assert wal.exists() and wal.stat().st_size > 0
    writer.execute('begin immediate')
    writer.execute('insert into security_snapshot values (?, ?, ?, ?, ?)',
        ('qa', 'UNCOMMITTED', 'profile', 2, json.dumps({'name': 'Synthetic Pending Issuer'})))
    try:
        result = main.write_full_backup(keep=5)
        archive_path = data_root / 'backups' / result['filename']
        with zipfile.ZipFile(archive_path) as archive:
            assert not any(name.endswith(('-wal', '-shm')) for name in archive.namelist())
            snapshot = archive.read('data/market-cache.sqlite3')
            local_snapshot = archive.read('data/local-portfolio.sqlite3')
        for destination in (':memory:', str(tmp_path / 'restored-market.sqlite3')):
            connection = sqlite3.connect(destination)
            try:
                if destination == ':memory:':
                    connection.deserialize(snapshot)
                else:
                    connection.close()
                    (tmp_path / 'restored-market.sqlite3').write_bytes(snapshot)
                    connection = sqlite3.connect(destination)
                assert connection.execute('pragma integrity_check').fetchone() == ('ok',)
                rows = connection.execute('select symbol, value from security_snapshot').fetchall()
                assert [(symbol, json.loads(value)) for symbol, value in rows] == [('COMMITTED', committed)]
            finally:
                connection.close()
        restored_local_path = tmp_path / 'restored-local.sqlite3'
        restored_local_path.write_bytes(local_snapshot)
        restored_local = main.LocalPortfolioStore(restored_local_path)
        assert restored_local.get_preference('qa_retained_portfolio') == {'source': 'synthetic committed local data'}
        assert store.get_preference('qa_retained_portfolio') == {'source': 'synthetic committed local data'}
        # Backup neither commits nor discards the source transaction.
        assert writer.in_transaction is True
        assert writer.execute('pragma journal_mode').fetchone() == ('wal',)
        assert writer.execute("select count(*) from security_snapshot where symbol='UNCOMMITTED'").fetchone() == (1,)
        assert cache.get_security_snapshot('qa', 'UNCOMMITTED', 'profile') is None
        assert cache.get_security_snapshot('qa', 'COMMITTED', 'profile') == committed
        assert main.inspect_full_backup(archive_path.read_bytes())['contains']['runtime_data_and_caches'] is True
    finally:
        writer.rollback()
        writer.close()
