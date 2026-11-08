"""Exercise release monitoring without running tests/builds/deployment."""
from pathlib import Path
import importlib.util
import json
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('code', [0, 7])
def test_quiet_monitor_waits_preserves_status_and_bounds_output(tmp_path, code):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    original = (ROOT / 'scripts/commit-and-deploy.sh').read_text()
    prefix = original.split('if (( $# < 2 )); then', 1)[0]
    script = scripts / 'commit-and-deploy.sh'
    script.write_text(prefix + f'for number in {{1..150}}; do echo "line $number"; done\nexit {code}\n')
    result = subprocess.run(['bash', str(script), '--quiet', 'message', 'file'], capture_output=True, text=True)
    assert result.returncode == code
    logs = list((tmp_path / '.runtime/releases').glob('*.log'))
    assert len(logs) == 1 and len(logs[0].read_text().splitlines()) == 150
    assert logs[0].stat().st_mode & 0o077 == 0
    output = result.stdout + result.stderr
    assert 'line 150' in output and 'line 1\n' not in output
    assert len(output.splitlines()) <= (8 if code == 0 else 44)
    if code:
        assert 'exit 7' in output


def load_verifier():
    spec = importlib.util.spec_from_file_location('release_verifier', ROOT / 'scripts/verify-deployment.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verifier_reads_committed_sources_and_deletions_not_dirty_worktree(tmp_path, monkeypatch):
    subprocess.run(['git', 'init', '--quiet', str(tmp_path)], check=True)
    (tmp_path / 'web').mkdir()
    (tmp_path / 'web/app.js').write_text('committed')
    subprocess.run(['git', '-C', str(tmp_path), 'add', 'web/app.js'], check=True)
    subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--quiet', '-m', 'fixture'], check=True)
    (tmp_path / 'web/app.js').write_text('dirty')
    monkeypatch.chdir(tmp_path)
    module = load_verifier()
    expected = module.expected_files(['web/app.js', 'app/deleted.py', 'config.yaml', 'data/cache.py', 'scripts/test.py'])
    assert expected == {'web/app.js': module.hashlib.sha256(b'committed').hexdigest(), 'app/deleted.py': None}
    with pytest.raises(ValueError):
        module.expected_files(['web/../../config.yaml'])


@pytest.mark.parametrize('matches', [True, False])
def test_served_asset_mismatch_fails_release_check(monkeypatch, matches):
    module = load_verifier()
    body = b'committed asset'
    monkeypatch.setattr(module, 'expected_files', lambda paths: {'web/app.js': module.hashlib.sha256(body).hexdigest()})
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        assert json.loads(kwargs['input'])['web/app.js'] == module.hashlib.sha256(body).hexdigest()
    monkeypatch.setattr(module.subprocess, 'run', run)
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return body if matches else b'old asset'
    class Opener:
        def open(self, url, timeout):
            assert url == 'https://localhost:6443/app.js' and timeout == 15
            return Response()
    monkeypatch.setattr(module.urllib.request, 'build_opener', lambda *args: Opener())
    if matches:
        module.verify(['web/app.js'])
    else:
        with pytest.raises(ValueError, match='Served asset differs'):
            module.verify(['web/app.js'])
    assert commands[0][:5] == ['docker', 'compose', 'exec', '-T', 'portfolio-analyzer']
