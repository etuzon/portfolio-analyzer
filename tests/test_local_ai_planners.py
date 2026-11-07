import asyncio
import json

import pytest
from fastapi import FastAPI

from app import claude_bridge, codex_bridge
from app.assistant_rest import AssistantRestGateway
from app.llm_assistant import AssistantError, PortfolioAssistant, assistant_settings


DECISION = {"action": "answer", "tool": "", "arguments": "", "answer": "Unknown", "support_status": "answered"}
RESEARCH_PROPOSAL = {"records": [{"security_key": "1101534|TASE|ILS", "source_id": "source-public", "record_id": "context-public"}],
                     "observations": [], "profiles": []}
RESEARCH_DECISION = {**DECISION, "answer": RESEARCH_PROPOSAL}


@pytest.mark.parametrize("research", [False, True])
def test_claude_one_turn_planner_forwards_model_effort_and_disables_tools(monkeypatch, research):
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
            self.output.write(json.dumps({"structured_output": RESEARCH_DECISION if research else DECISION}).encode())
        def wait(self, timeout):
            return 0
    monkeypatch.setattr(claude_bridge.shutil, "which", lambda name: "/fixture/claude")
    monkeypatch.setattr(claude_bridge.subprocess, "Popen", Process)
    monkeypatch.setattr(claude_bridge.os, "killpg", lambda *_: None)
    response = claude_bridge.claude_completion([{"role": "user", "content": "Price?"}], [], model="sonnet", reasoning_effort="medium", timeout=10,
        policy=codex_bridge.SECURITY_RESEARCH_PLANNER_POLICY if research else None)
    content = response["choices"][0]["message"]["content"]
    assert (json.loads(content) if research else content) == (RESEARCH_PROPOSAL if research else "Unknown")
    command = seen["command"]
    for flag, value in {"--max-turns": "1", "--tools": "", "--model": "sonnet", "--effort": "medium", "--setting-sources": "", "--permission-mode": "dontAsk"}.items():
        assert command[command.index(flag) + 1] == value
    assert "--strict-mcp-config" in command and "--no-session-persistence" in command
    assert json.loads(command[command.index("--mcp-config") + 1]) == {"mcpServers": {}}
    assert json.loads(command[command.index("--settings") + 1])["disableAllHooks"] is True
    assert json.loads(command[command.index("--json-schema") + 1]) == codex_bridge.decision_schema([], research=research)
    assert seen["body"] == {"conversation": [{"role": "user", "content": "Price?"}], "allowed_read_tools": []}
    assert seen["timeout"] == 10
    assert seen["options"]["start_new_session"] is True
    environment = seen["options"]["env"]
    assert not {"CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_EFFORT_LEVEL"} & environment.keys()
    assert environment["ANTHROPIC_API_KEY"] == "synthetic-cli-auth"
    assert environment["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == "1"


@pytest.mark.parametrize("research", [False, True])
def test_codex_one_turn_planner_passes_model_effort_and_has_no_native_tools(monkeypatch, research):
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
                {"method": "item/completed", "params": {"item": {"type": "agentMessage", "text": json.dumps(RESEARCH_DECISION if research else DECISION)}}},
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
    response = codex_bridge.codex_completion([], [], model="gpt-6.1-sol", reasoning_effort="medium",
        policy=codex_bridge.SECURITY_RESEARCH_PLANNER_POLICY if research else None)
    content = response["choices"][0]["message"]["content"]
    assert (json.loads(content) if research else content) == (RESEARCH_PROPOSAL if research else "Unknown")
    starts = [message for message in sent if message.get("method") == "turn/start"]
    assert len(starts) == 1
    assert starts[0]["params"]["effort"] == "medium"
    assert starts[0]["params"]["outputSchema"] == codex_bridge.decision_schema([], research=research)
    thread = next(message for message in sent if message.get("method") == "thread/start")["params"]
    assert thread["config"]["model"] == "gpt-6.1-sol"
    assert thread["config"]["web_search"] == "disabled"
    assert thread["config"]["features.shell_tool"] is False
    assert thread["dynamicTools"] == []
    assert 'model="gpt-6.1-sol"' in commands[0]


def test_research_schema_requires_typed_arrays_and_no_unknown_fields_at_every_object():
    from app.price_agent import ITEM_PROPERTIES
    schema = codex_bridge.decision_schema([], research=True)
    proposal = schema["properties"]["answer"]
    assert proposal["type"] == "object"
    assert set(proposal["required"]) == {"records", "observations", "profiles"}
    observation = schema["$defs"]["_ResearchObservation"]
    assert set(observation["properties"]) == {"security_key", *ITEM_PROPERTIES}
    def check(value):
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value["additionalProperties"] is False
                assert set(value["required"]) == set(value["properties"])
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
    check(schema)
    assert codex_bridge.decision_schema([])["properties"]["answer"] == {"type": "string"}


@pytest.mark.parametrize("answer", [
    "I could not find enough information.", json.dumps(RESEARCH_PROPOSAL),
    {"records": []}, {**RESEARCH_PROPOSAL, "execute_sql": "untrusted"},
    {**RESEARCH_PROPOSAL, "records": [{"security_key": "one", "source_id": "source", "record_id": "record", "price": 1}]},
    {**RESEARCH_PROPOSAL, "records": [{"security_key": "one", "source_id": "source", "record_id": None}]},
    {**RESEARCH_PROPOSAL, "observations": ["untrusted"]},
    {**RESEARCH_PROPOSAL, "profiles": [{"security_key": "one", "field": "forecast", "value": "guess", "source_url": "https://example.com", "evidence_quote": "guess"}]},
])
def test_research_decision_refuses_prose_strings_and_malformed_nested_proposals(answer):
    with pytest.raises(codex_bridge.CodexBridgeError, match="invalid structured research decision"):
        codex_bridge.decision_response({**DECISION, "answer": answer}, [], research=True)


def test_research_read_decision_remains_one_named_tool_with_no_direct_write():
    tools = [{"function": {"name": "read_security_source"}}]
    decision = {**RESEARCH_DECISION, "action": "read", "tool": "read_security_source", "arguments": '{"source_id":"source-public"}',
                "answer": {"records": [], "observations": [], "profiles": []}}
    message = codex_bridge.decision_response(decision, tools, research=True)["choices"][0]["message"]
    call, = message["tool_calls"]
    assert "content" not in message
    assert call["function"] == {"name": "read_security_source", "arguments": '{"source_id":"source-public"}'}
    with pytest.raises(codex_bridge.CodexBridgeError, match="invalid decision"):
        codex_bridge.decision_response({**decision, "tool": "save_prices"}, tools, research=True)


def test_research_observation_keeps_raw_number_and_source_fields_for_application_validation():
    observation = {"security_key": "1101534|TASE|ILS", "price_input": 2901, "price_date": "2026-11-06",
                   "currency": "ILS", "quote_unit": "agorot", "price_basis": "last", "observed_at": None,
                   "source_url": "https://market.tase.co.il/he/market_data/security/1101534", "evidence_quote": "שער אחרון 2901"}
    proposal = {"records": [], "observations": [observation], "profiles": []}
    message = codex_bridge.decision_response({**DECISION, "answer": proposal}, [], research=True)["choices"][0]["message"]
    assert json.loads(message["content"]) == proposal
    for invalid in ({"price_input": True}, {"price_input": "2901"}, {"price_input": float("nan")}, {"quote_unit": "percent_of_par"}, {"price_basis": "nav"}):
        with pytest.raises(codex_bridge.CodexBridgeError, match="invalid structured research decision"):
            codex_bridge.decision_response({**DECISION, "answer": {**proposal, "observations": [{**observation, **invalid}]}}, [], research=True)


def test_research_transport_refuses_oversize_proposal_instead_of_truncating_json():
    profile = {"security_key": "one", "field": "industry", "value": "Industry", "source_url": "https://example.com/quote", "evidence_quote": "x" * 2000}
    proposal = {"records": [], "observations": [], "profiles": [profile] * 20}
    with pytest.raises(codex_bridge.CodexBridgeError, match="exceeds the response limit"):
        codex_bridge.decision_response({**DECISION, "answer": proposal}, [], research=True)


def test_custom_host_price_runner_answer_contract_remains_a_plain_string():
    content = json.dumps({"items": [{"price": "host-specific-envelope"}]})
    assert codex_bridge.decision_response({**DECISION, "answer": content}, [])["choices"][0]["message"]["content"] == content


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
