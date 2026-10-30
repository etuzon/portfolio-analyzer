from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_commit_and_deploy_script_has_safe_release_gates() -> None:
    script_path = ROOT / "scripts" / "commit-and-deploy.sh"
    script = script_path.read_text(encoding="utf-8")

    assert "git diff --cached --quiet" in script
    assert 'git diff --check -- "${files[@]}"' in script
    assert "./.venv/bin/python -m pytest" in script
    assert 'git add -- "${files[@]}"' in script
    assert 'git commit -m "$message" -- "${files[@]}"' in script
    assert "docker compose up --build -d" in script
    assert "https://localhost:6443/api/health" in script
    assert script.index("./scripts/start-codex-bridge.sh --restart") < script.index('git commit -m "$message"')
