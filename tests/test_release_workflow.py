from pathlib import Path
import subprocess

import pytest
import yaml


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


@pytest.mark.parametrize("selected,allowed", [("skill-link", True), ("skill-folder", False), ("../outside", False)])
def test_release_file_gate_accepts_git_symlinks_but_not_directories_or_parent_paths(tmp_path, selected, allowed):
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    (repo / "skill-folder").mkdir()
    (repo / "skill-folder" / "SKILL.md").write_text("Test skill")
    (repo / "skill-link").symlink_to("skill-folder", target_is_directory=True)
    script = (ROOT / "scripts/commit-and-deploy.sh").read_text()
    marker = 'echo "Checking selected files..."'
    assert marker in script
    # Exercise the real input gate, stopping before tests, commits or deployment.
    preflight = scripts / "preflight.sh"
    preflight.write_text(script.split(marker, 1)[0] + "exit 0\n")
    result = subprocess.run(["bash", str(preflight), "test release", selected], capture_output=True, text=True)
    assert (result.returncode == 0) is allowed, result.stderr


def test_compose_passes_optional_security_research_credentials_to_application():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    environment = compose["services"]["portfolio-analyzer"]["environment"]
    for key in ("BRAVE_SEARCH_API_KEY", "FINNHUB_API_KEY", "EODHD_API_KEY"):
        assert environment[key] == "${" + key + ":-}"
