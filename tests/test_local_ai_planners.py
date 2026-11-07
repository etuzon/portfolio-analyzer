import asyncio
import json

import pytest
from fastapi import FastAPI

from app import claude_bridge, codex_bridge
from app.assistant_rest import AssistantRestGateway
from app.llm_assistant import AssistantError, PortfolioAssistant, assistant_settings


DECISION = {"action": "answer", "tool": "", "arguments": "", "answer": "Unknown", "support_status": "answered"}


def test_claude_one_turn_planner_forwards_model_effort_and_disables_tools(monkeypatch):
    seen = {}
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_CHILD_SESSION", "parent-session")
    monkeypatch.setenv("CLAUDE_CODE_EFFORT_LEVEL", "high")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-cli-auth")
    class Process:
        pid = 123456789
        returncode = 0
        def __init__(self, command, **kwargs):
            seen.update(command=command, options=kwargs)
            self.output = kwargs["stdout"]
        def communicate(self, body, timeout):
            seen.update(body=json.loads(body), timeout=timeout)
            self.output.write(json.dumps({"structured_output": DECISION}).encode())
        def wait(self, timeout):
            return 0
    monkeypatch.setattr(claude_bridge.shutil, "which", lambda name: "/fixture/claude")
    monkeypatch.setattr(claude_bridge.subprocess, "Popen", Process)
    monkeypatch.setattr(claude_bridge.os, "killpg", lambda *_: None)
    response = claude_bridge.claude_completion([{"role": "user", "content": "Price?"}], [], model="sonnet", reasoning_effort="medium", timeout=10)
    assert response["choices"][0]["message"]["content"] == "Unknown"
    command = seen["command"]
    for flag, value in {"--max-turns": "1", "--tools": "", "--model": "sonnet", "--effort": "medium", "--setting-sources": "", "--permission-mode": "dontAsk"}.items():
        assert command[command.index(flag) + 1] == value
    assert "--strict-mcp-config" in command and "--no-session-persistence" in command
    assert json.loads(command[command.index("--mcp-config") + 1]) == {"mcpServers": {}}
    assert json.loads(command[command.index("--settings") + 1])["disableAllHooks"] is True
    assert seen["body"] == {"conversation": [{"role": "user", "content": "Price?"}], "allowed_read_tools": []}
    assert seen["timeout"] == 10
    assert seen["options"]["start_new_session"] is True
    environment = seen["options"]["env"]
    assert not {"CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_EFFORT_LEVEL"} & environment.keys()
    assert environment["ANTHROPIC_API_KEY"] == "synthetic-cli-auth"
    assert environment["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == "1"


def test_codex_one_turn_planner_passes_model_effort_and_has_no_native_tools(monkeypatch):
    sent, commands = [], []
    class Process:
        pid = 123456789
        def __init__(self, command, **kwargs):
            commands.append(command)
        def wait(self, timeout):
            return 0
    class Rpc:
        def __init__(self, *_):
            self.events = iter([
                {"method": "item/completed", "params": {"item": {"type": "agentMessage", "text": json.dumps(DECISION)}}},
                {"method": "turn/completed", "params": {"turn": {"status": "completed"}}},
            ])
        def send(self, message):
            sent.append(message)
        def result(self, identifier):
            return {"thread": {"id": "fixture-thread"}} if identifier == 2 else {}
        def next(self):
            return next(self.events)
    monkeypatch.setattr(codex_bridge.shutil, "which", lambda name: "/fixture/codex")
    monkeypatch.setattr(codex_bridge.subprocess, "Popen", Process)
    monkeypatch.setattr(codex_bridge.os, "killpg", lambda *_: None)
    monkeypatch.setattr(codex_bridge, "_Rpc", Rpc)
    response = codex_bridge.codex_completion([], [], model="gpt-6.1-sol", reasoning_effort="medium")
    assert response["choices"][0]["message"]["content"] == "Unknown"
    starts = [message for message in sent if message.get("method") == "turn/start"]
    assert len(starts) == 1
    assert starts[0]["params"]["effort"] == "medium"
    thread = next(message for message in sent if message.get("method") == "thread/start")["params"]
    assert thread["config"]["model"] == "gpt-6.1-sol"
    assert thread["config"]["web_search"] == "disabled"
    assert thread["config"]["features.shell_tool"] is False
    assert thread["dynamicTools"] == []
    assert 'model="gpt-6.1-sol"' in commands[0]


def test_rest_budget_counts_failures_and_blocks_sixth_attempt():
    app = FastAPI()
    requests = []
    @app.get("/api/fails")
    def fails():
        requests.append(True)
        from fastapi import HTTPException
        raise HTTPException(503)
    gateway = AssistantRestGateway(app, {"get": {"path": "/api/fails"}}, {}, max_calls=999)
    for _ in range(5):
        with pytest.raises(AssistantError, match="HTTP 503"):
            asyncio.run(gateway.read("get", {}))
    with pytest.raises(AssistantError, match="REST request limit"):
        asyncio.run(gateway.read("get", {}))
    assert len(requests) == gateway.calls == 5


def test_chat_respects_lower_rest_limit_and_answers_after_failed_read():
    settings = assistant_settings({"llm": {"provider": "openai", "enabled": True, "base_url": "https://fixture.invalid", "api_key": "fixture", "model": "fixture", "max_rest_calls": 1}})
    model_calls, rest_calls = [], []
    def model(*, messages, tools):
        model_calls.append(tools)
        if tools:
            return {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "read", "function": {"name": "get", "arguments": "{}"}}]}}]}
        return {"choices": [{"message": {"role": "assistant", "content": "Price unavailable"}}]}
    def rest(*_):
        rest_calls.append(True)
        raise AssistantError("Unavailable")
    result = PortfolioAssistant(settings, {"get": {"path": "/api/fixture", "description": "Read"}}, caller=model).ask("Price?", "en", rest)
    assert result["rest_requests"] == len(rest_calls) == 1
    assert result["model_requests"] == len(model_calls) == 2
    assert model_calls[-1] == []


@pytest.mark.parametrize("provider,expected", [("codex", "local_codex"), ("claude", "local_claude"), ("local_claude", "local_claude")])
def test_yaml_cli_selection_and_default_call_ceilings(provider, expected):
    settings = assistant_settings({"llm": {"provider": provider, "max_tool_loops": 999, "max_rest_calls": 999}})
    assert settings["provider"] == expected
    assert settings["enabled"] is True
    assert settings["max_tool_loops"] == settings["max_rest_calls"] == 5
