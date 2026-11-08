"""Real socket lifecycle checks; no model or public Internet calls."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest

from app.llm_assistant import AssistantError, PortfolioAssistant, assistant_settings
from app.codex_bridge import bridge_runtime_directory, process_owns_bridge_socket, CodexBridgeError


def launch(path, *, no_cli=False):
    environment = dict(os.environ)
    if no_cli:
        environment["PATH"] = ""
    return subprocess.Popen([sys.executable, "-m", "app.codex_bridge", "--socket", str(path)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment)


def wait_ready(path, process):
    deadline = time.monotonic()+5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail("Bridge exited before health became available")
        try:
            with httpx.Client(transport=httpx.HTTPTransport(uds=str(path)), base_url="http://bridge", timeout=0.2) as client:
                response = client.get("/health")
            if response.status_code == 200:
                return response
        except httpx.HTTPError:
            pass
        time.sleep(0.02)
    pytest.fail("Bridge health did not become available")


def stop(process):
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)


def settings(path):
    return assistant_settings({"llm": {"enabled": True, "provider": "local_codex", "codex_socket": str(path)}})


def test_starter_socket_directory_matches_explicit_and_dotenv_compose_overrides(tmp_path, monkeypatch):
    monkeypatch.delenv("PORTFOLIO_CODEX_DIR", raising=False)
    assert bridge_runtime_directory(tmp_path) == tmp_path/".runtime/portfolio-codex"
    (tmp_path/".env").write_text('UNRELATED_SECRET=never-return-this\nPORTFOLIO_CODEX_DIR="private socket"\n')
    assert bridge_runtime_directory(tmp_path) == tmp_path/"private socket"
    monkeypatch.setenv("PORTFOLIO_CODEX_DIR", "/explicit/bridge")
    assert bridge_runtime_directory(tmp_path) == Path("/explicit/bridge")
    monkeypatch.setenv("PORTFOLIO_CODEX_DIR", "")
    assert bridge_runtime_directory(tmp_path) == tmp_path/".runtime/portfolio-codex"
    monkeypatch.delenv("PORTFOLIO_CODEX_DIR")
    (tmp_path/".env").write_text('PORTFOLIO_CODEX_DIR=${BRIDGE_PARENT}/socket\n')
    with pytest.raises(CodexBridgeError, match="resolved PORTFOLIO_CODEX_DIR"):
        bridge_runtime_directory(tmp_path)


def test_health_and_supervisor_restart_recover_a_killed_bridge_socket(tmp_path):
    path = tmp_path/"bridge.sock"
    first = launch(path)
    try:
        assert wait_ready(path, first).json() == {"status": "ok"}
        assert path.stat().st_mode & 0o777 == 0o600
        assert process_owns_bridge_socket(first.pid, str(path))
        assert not process_owns_bridge_socket(first.pid, str(tmp_path/"another.sock"))
        assert not process_owns_bridge_socket(os.getpid(), str(path))
    finally:
        stop(first)
    assert path.is_socket(), "A crash leaves a stale inode that a supervised restart must recover"
    second = launch(path)
    try:
        assert wait_ready(path, second).status_code == 200
        competitor = launch(path)
        assert competitor.wait(timeout=5) != 0
        assert wait_ready(path, second).status_code == 200
    finally:
        stop(second)


def test_bridge_refuses_to_replace_an_existing_regular_file(tmp_path):
    path = tmp_path/"bridge.sock"
    path.write_text("preserve this file")
    process = launch(path)
    assert process.wait(timeout=5) != 0
    assert path.read_text() == "preserve this file"


def test_missing_bridge_is_identified_before_any_model_or_data_read(tmp_path):
    called = []
    assistant = PortfolioAssistant(settings(tmp_path/"missing.sock"), {}, caller=lambda **_: called.append(True))
    with pytest.raises(AssistantError) as failure:
        assistant.ask("Research this security", "en", lambda *_: pytest.fail("No read is permitted"))
    assert failure.value.code == "ai_bridge_missing"
    assert assistant.status()["unavailable_code"] == "ai_bridge_missing"
    assert called == []


def test_stale_bridge_and_live_provider_failure_have_different_codes(tmp_path):
    path = tmp_path/"bridge.sock"
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(str(path))
    with pytest.raises(AssistantError) as failure:
        PortfolioAssistant(settings(path), {}).ask("Research", "en", lambda *_: {})
    assert failure.value.code == "ai_bridge_unavailable"
    path.unlink()
    process = launch(path, no_cli=True)
    try:
        wait_ready(path, process)
        with pytest.raises(AssistantError) as failure:
            PortfolioAssistant(settings(path), {}).ask("Research", "en", lambda *_: {})
        assert failure.value.code == "ai_provider_unavailable"
        assert "Codex CLI is not installed" in str(failure.value)
    finally:
        stop(process)
