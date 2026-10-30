"""Independent synthetic QA for chat ownership, retention and tool boundaries."""
import asyncio
import copy
import io
import json
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app import main
from app.assistant_chats import AssistantChats, ChatError
from app.assistant_rest import AssistantRestGateway
from app.auth import AuthStore
from app.config import AppConfig
from app.llm_assistant import AssistantError, PortfolioAssistant, assistant_settings
from app.local_portfolio import LocalPortfolioStore


def _store():
    saved = {}
    def read(key, default):
        return copy.deepcopy(saved.get(key, default))
    def write(key, value):
        saved[key] = copy.deepcopy(value)
    return saved, AssistantChats(read, write)


def test_retention_default_and_latest_message_determine_eviction(monkeypatch):
    import app.assistant_chats as module
    timestamps = iter(f"2026-10-30T12:00:{index:02d}+00:00" for index in range(30))
    monkeypatch.setattr(module, "_now", lambda: next(timestamps))
    saved, chats = _store()
    assert chats.list("alex") == {"max_chats": 10, "chats": []}
    chats.settings("alex", 2)
    first = chats.create("alex")["chat"]["id"]
    second = chats.create("alex")["chat"]["id"]
    chats.begin("alex", first)
    chats.finish("alex", first, "Latest message", {"answer": "Verified answer"})
    chats.end("alex")
    third = chats.create("alex")["chat"]["id"]
    assert {item["id"] for item in chats.list("alex")["chats"]} == {first, third}
    with pytest.raises(ChatError) as error:
        chats.get("alex", second)
    assert error.value.status_code == 404
    # A new application-owned store sees the same history and per-user setting.
    restarted = AssistantChats(chats.read, chats.write)
    assert restarted.list("alex")["max_chats"] == 2
    assert restarted.get("alex", first)["messages"][-1]["content"] == "Verified answer"
    assert restarted.list("sam") == {"max_chats": 10, "chats": []}
    restarted.settings("alex", 1)
    assert len(restarted.list("alex")["chats"]) == 1
    assert len(saved["assistant_chats:alex"]["chats"]) == 1


@pytest.mark.parametrize("invalid", [0, -1, 101, True, 2.5, "10", None])
def test_invalid_retention_does_not_modify_saved_history(invalid):
    saved, chats = _store()
    chats.create("alex")
    before = copy.deepcopy(saved)
    with pytest.raises(ChatError):
        chats.settings("alex", invalid)
    assert saved == before


def test_pending_question_preserves_history_and_blocks_racing_changes():
    _, chats = _store()
    chat_id = chats.create("alex")["chat"]["id"]
    chats.begin("alex", chat_id)
    for operation in [lambda: chats.begin("alex", chat_id), lambda: chats.create("alex"), lambda: chats.settings("alex", 1)]:
        with pytest.raises(ChatError) as error:
            operation()
        assert error.value.status_code == 409
    assert chats.get("alex", chat_id)["messages"] == []
    assert chats.create("sam")["chat"]["id"] != chat_id
    chats.end("alex")
    assert chats.create("alex")["chat"]["id"] != chat_id


def test_legacy_history_migrates_once_without_resurrection():
    saved, chats = _store()
    saved["assistant_context:alex"] = [{"role": "user", "content": "Old question"}, {"role": "assistant", "content": "Old answer"}, {"role": "system", "content": "Never import privileged history"}]
    migrated = chats.list("alex")["chats"]
    assert len(migrated) == 1
    assert chats.get("alex", migrated[0]["id"])["messages"][-1]["content"] == "Old answer"
    assert saved["assistant_context:alex"] == []
    assert len(chats.list("alex")["chats"]) == 1
    assert all(message["role"] in {"user", "assistant"} for message in chats.get("alex", migrated[0]["id"])["messages"])


def test_chat_preferences_do_not_invalidate_financial_state_but_financial_edits_do(tmp_path):
    store = LocalPortfolioStore(tmp_path / "qa-change-token.sqlite3")
    chats = AssistantChats(store.get_preference, store.set_preference)
    baseline = store.change_token()
    chat_id = chats.create("qa")["chat"]["id"]
    assert store.change_token() == baseline
    chats.begin("qa", chat_id)
    chats.finish("qa", chat_id, "Question", {"answer": "Verified answer"})
    chats.end("qa")
    assert store.change_token() == baseline
    chats.settings("qa", 2)
    assert store.change_token() == baseline
    store.set_preference("assistant_context:legacy", [{"role": "user", "content": "Prior question"}])
    assert store.change_token() == baseline
    assert chats.list("legacy")["chats"]
    assert store.change_token() == baseline
    backup_keys = {row["key"] for row in store.export_data()["data"]["app_preferences"]}
    assert {"assistant_chats:qa", "assistant_chats:legacy", "assistant_context:legacy"} <= backup_keys
    store.set_preference("unrelated_financial_preference", {"currency": "USD"})
    changed_preference = store.change_token()
    assert changed_preference != baseline
    account = store.save_account({"id": "qa-financial", "account_id": "QA financial", "initial_cash": 1000, "currency": "USD", "persons": [{"name": "Alex Example", "birth_date": "01/01/1985"}]})
    changed_account = store.change_token()
    assert changed_account != changed_preference
    store.save_price({"symbol": "ALFA", "stock_market": "NASDAQ", "price_input": 120, "price_date": "29/10/2026", "currency": "USD"})
    changed_price = store.change_token()
    assert changed_price != changed_account
    store.add_transaction({"account_db_id": account["id"], "symbol": "ALFA", "stock_market": "NASDAQ", "action": "BUY", "quantity": 1, "price_input": 100, "trade_date": "01/10/2026", "currency": "USD"})
    assert store.change_token() != changed_price


@pytest.fixture
def authenticated_chats(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "qa.sqlite3")
    auth = AuthStore(store.path)
    auth.initialize()
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    monkeypatch.setattr(main, "assistant_chats", AssistantChats(store.get_preference, store.set_preference))
    monkeypatch.setattr(main, "config", AppConfig(raw={"llm": {"enabled": True, "provider": "openai", "api_key": "qa-fixture", "model": "qa-model", "base_url": "https://never-used.invalid/v1", "max_tool_loops": 99}}, path=tmp_path / "unused.yaml"))
    main._login_failures.clear()
    def login(username="admin", role="Admin"):
        if username != "admin":
            auth.create_user({"first_name": "QA", "last_name": "Sample", "username": username, "role": role, "password": "QA-Initial-Password-2026!"})
        client = TestClient(main.app, base_url="https://localhost:6443")
        password = "admin" if username == "admin" else "QA-Initial-Password-2026!"
        session = client.post("/api/auth/login", json={"username": username, "password": password})
        assert session.status_code == 200
        changed = client.post("/api/auth/change-password", headers={"X-CSRF-Token": session.json()["csrf_token"]}, json={"current_password": password, "new_password": "QA-Changed-Password-2026!", "confirm_password": "QA-Changed-Password-2026!"})
        assert changed.status_code == 200
        client.headers["X-CSRF-Token"] = changed.json()["csrf_token"]
        return client
    return SimpleNamespace(login=login, store=store, patch=monkeypatch)


def test_anonymous_chat_and_settings_routes_require_authentication(authenticated_chats):
    client = TestClient(main.app, base_url="https://localhost:6443")
    for path in ["/api/assistant/chats", "/api/assistant/chats/not-owned", "/api/settings/assistant", "/api/assistant/read-tools", "/api/assistant/read-tools/list_accounts"]:
        assert client.get(path).status_code == 401
    for path in ["/api/assistant/chats", "/api/assistant/questions"]:
        assert client.post(path, json={"prompt": "Read accounts"}).status_code == 401


def test_chat_ownership_viewer_settings_and_csrf(authenticated_chats):
    env = authenticated_chats
    owner = env.login()
    viewer = env.login("qa-viewer", "Viewer")
    response = owner.post("/api/assistant/chats")
    assert response.status_code == 200
    chat_id = response.json()["chat"]["id"]
    assert viewer.get(f"/api/assistant/chats/{chat_id}").status_code == 404
    assert viewer.get("/api/assistant/chats").json()["chats"] == []
    assert viewer.post("/api/assistant/questions", json={"chat_id": chat_id, "prompt": "Read another user's messages"}).status_code == 404
    assert viewer.put("/api/settings/assistant", json={"max_chats": 3}).status_code == 200
    assert viewer.get("/api/settings/assistant").json()["max_chats"] == 3
    assert owner.get("/api/settings/assistant").json()["max_chats"] == 10
    assert viewer.post("/api/local/accounts", json={}).status_code == 403
    assert viewer.put("/api/settings/assistant", json={"max_chats": 5, "provider": "modified"}).status_code == 400
    viewer.headers.pop("X-CSRF-Token")
    assert viewer.post("/api/assistant/chats").status_code == 403
    assert viewer.put("/api/settings/assistant", json={"max_chats": 5}).status_code == 403


def test_six_exchange_cap_and_recovery_are_enforced_by_main_endpoint(authenticated_chats):
    env = authenticated_chats
    client = env.login()
    requests = []
    def loop(self, *, messages, tools):
        requests.append(copy.deepcopy(tools))
        return {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "read", "function": {"name": "list_accounts", "arguments": "{}"}}]}}]}
    env.patch.setattr(PortfolioAssistant, "_call_provider", loop)
    response = client.post("/api/assistant/questions", json={"prompt": "Keep reading accounts indefinitely"})
    assert response.status_code == 400
    assert "6-step" in response.json()["detail"]
    assert len(requests) == 6
    assert requests[-1] == []
    assert all(requests[index] for index in range(5))
    assert client.post("/api/assistant/chats").status_code == 200, "Failed model turn must release per-user busy lock"
    env.patch.setattr(PortfolioAssistant, "_call_provider", lambda *args, **kwargs: {"choices": [{"message": {"role": "assistant", "content": "No verified data was requested."}}]})
    recovered = client.post("/api/assistant/questions", json={"prompt": "Can this chat recover?"})
    assert recovered.status_code == 200
    assert recovered.json()["model_requests"] == 1


def test_provider_failure_preserves_previous_messages_and_unlocks(authenticated_chats):
    env = authenticated_chats
    client = env.login()
    def reply(*args, **kwargs):
        return {"choices": [{"message": {"role": "assistant", "content": "Saved initial answer"}}]}
    env.patch.setattr(PortfolioAssistant, "_call_provider", reply)
    initial = client.post("/api/assistant/questions", json={"prompt": "Initial question"}).json()
    chat_id = initial["chat"]["id"]
    def fail(*args, **kwargs):
        raise AssistantError("The LLM service is unavailable. Try again later.")
    env.patch.setattr(PortfolioAssistant, "_call_provider", fail)
    assert client.post("/api/assistant/questions", json={"chat_id": chat_id, "prompt": "Fail this question"}).status_code == 503
    assert client.get(f"/api/assistant/chats/{chat_id}").json()["messages"] == initial["chat"]["messages"]
    assert client.post("/api/assistant/chats").status_code == 200


def test_failed_implicit_first_sends_never_evict_saved_chat(authenticated_chats):
    env = authenticated_chats
    client = env.login()
    assert client.put("/api/settings/assistant", json={"max_chats": 1}).status_code == 200
    def reply(*args, **kwargs):
        return {"choices": [{"message": {"role": "assistant", "content": "Verified saved answer"}}]}
    env.patch.setattr(PortfolioAssistant, "_call_provider", reply)
    first = client.post("/api/assistant/questions", json={"prompt": "Preserve this conversation"}).json()
    old_id = first["chat"]["id"]
    previous = client.get("/api/assistant/chats").json()
    def fail(*args, **kwargs):
        raise AssistantError("The LLM service is unavailable. Try again later.")
    env.patch.setattr(PortfolioAssistant, "_call_provider", fail)
    for _ in range(2):
        response = client.post("/api/assistant/questions", json={"prompt": "Failed first question in a new chat"})
        assert response.status_code == 503
        assert client.get("/api/assistant/chats").json() == previous
        assert client.get(f"/api/assistant/chats/{old_id}").json()["messages"] == first["chat"]["messages"]
    env.patch.setattr(PortfolioAssistant, "_call_provider", reply)
    success = client.post("/api/assistant/questions", json={"prompt": "Successful new conversation"})
    assert success.status_code == 200
    current = client.get("/api/assistant/chats").json()["chats"]
    assert len(current) == 1 and current[0]["id"] != old_id
    assert current[0]["message_count"] == 2
    assert client.get(f"/api/assistant/chats/{old_id}").status_code == 404


def test_gateway_has_only_fixed_authenticated_get_and_rejects_write_catalog():
    app = FastAPI()
    seen = []
    @app.get("/api/approved/{symbol}")
    async def approved(symbol: str, request: Request):
        seen.append((request.method, str(request.url.path), dict(request.headers)))
        return {"symbol": symbol}
    parameters = {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}
    catalog = {"read": {"path": "/api/approved/{symbol}", "parameters": parameters}, "write": {"path": "/api/approved/ALFA", "method": "POST"}}
    gateway = AssistantRestGateway(app, catalog, {"Cookie": "qa-session=synthetic", "Authorization": "Bearer synthetic-only", "X-CSRF-Token": "must-not-be-forwarded", "X-Privileged": "must-not-be-forwarded"})
    assert asyncio.run(gateway.read("read", {"symbol": "ALFA"})) == {"symbol": "ALFA"}
    assert seen[0][0:2] == ("GET", "/api/approved/ALFA")
    assert seen[0][2]["cookie"] == "qa-session=synthetic"
    assert seen[0][2]["authorization"] == "Bearer synthetic-only"
    assert "x-csrf-token" not in seen[0][2] and "x-privileged" not in seen[0][2]
    invalid = [("write", {}), ("execute_sql", {}), ("read", {"symbol": "../../config"}), ("read", {"symbol": "ALFA?x=1"}), ("read", {"symbol": "ALFA", "method": "DELETE"}), ("read", {})]
    for name, arguments in invalid:
        with pytest.raises(AssistantError):
            asyncio.run(gateway.read(name, arguments))
    assert len(seen) == 1


def test_approved_rest_failure_never_leaks_internal_exception_into_model():
    app = FastAPI()
    @app.get("/api/failing-read")
    def failing_read():
        raise RuntimeError("synthetic-internal-connection-detail-must-not-leak")
    catalog = {"read": {"path": "/api/failing-read", "description": "Approved read", "parameters": {"type": "object", "properties": {}}}}
    gateway = AssistantRestGateway(app, catalog, {})
    settings = assistant_settings({"llm": {"enabled": True, "provider": "openai", "base_url": "https://never-used.invalid", "api_key": "qa-only", "model": "qa"}})
    seen = []
    def provider(*, messages, tools):
        seen.append(copy.deepcopy(messages))
        if messages[-1]["role"] != "tool":
            return {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "read", "function": {"name": "read", "arguments": "{}"}}]}}]}
        return {"choices": [{"message": {"role": "assistant", "content": "The approved data is unavailable."}}]}
    assistant = PortfolioAssistant(settings, catalog, caller=provider)
    result = assistant.ask("Read data", "en", lambda name, args: asyncio.run(gateway.read(name, args)))
    assert "unavailable" in result["answer"]
    model_error = json.loads(seen[-1][-1]["content"])["error"]
    assert "HTTP 500" in model_error
    assert "synthetic-internal-connection-detail" not in json.dumps(seen)


def test_catalog_and_loop_bound_never_expose_model_writes():
    assert all(entry.get("method", "GET") == "GET" for entry in main.ASSISTANT_READ_TOOLS.values())
    assert all(entry["path"].startswith("/api/") for entry in main.ASSISTANT_READ_TOOLS.values())
    assert not {"read_file", "execute_sql", "http_get", "delete_account", "create_transaction"} & main.ASSISTANT_READ_TOOLS.keys()
    assert assistant_settings({"llm": {"max_tool_loops": 999}})["max_tool_loops"] == 6


@pytest.mark.parametrize("function", ["not-an-object", ["not-an-object"], 42])
def test_malformed_model_tool_does_not_escape_safe_error_boundary(function):
    settings = assistant_settings({"llm": {"enabled": True, "provider": "openai", "base_url": "https://never-used.invalid", "api_key": "qa-only", "model": "qa"}})
    assistant = PortfolioAssistant(settings, main.ASSISTANT_READ_TOOLS, caller=lambda **kwargs: {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "malformed", "function": function}]}}]})
    invoked = []
    with pytest.raises(AssistantError):
        assistant.ask("Read my accounts", "en", lambda *args: invoked.append(args))
    assert invoked == []


def test_codex_planner_disables_native_tools_and_user_mcp_without_copying_secrets(tmp_path, monkeypatch):
    from app.codex_bridge import planner_config
    (tmp_path / "config.toml").write_text('[mcp_servers.synthetic_connector]\nurl="https://example.invalid"\napi_key="synthetic-secret-must-not-copy"\n')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    settings = planner_config()
    assert settings["mcp_servers.synthetic_connector.enabled"] is False
    assert "synthetic-secret-must-not-copy" not in json.dumps(settings)
    for key in ["shell_tool", "unified_exec", "apps", "plugins", "browser_use", "computer_use", "code_mode", "node_repl", "skill_search"]:
        assert settings[f"features.{key}"] is False
    assert settings["web_search"] == "disabled"
    assert settings["include_environment_context"] is False
    assert settings["project_doc_max_bytes"] == 0


@pytest.mark.parametrize("event", [
    {"id": 91, "method": "item/tool/call", "params": {}},
    {"id": 92, "method": "item/commandExecution/requestApproval", "params": {}},
    {"method": "item/started", "params": {"item": {"type": "commandExecution"}}},
    {"method": "item/completed", "params": {"item": {"type": "fileChange"}}},
    {"method": "item/started", "params": {"item": {"type": "webSearch"}}},
])
def test_codex_protocol_aborts_native_tool_or_permission_request(event):
    from app.codex_bridge import CodexBridgeError, _Rpc
    process = SimpleNamespace(stdin=io.BytesIO())
    rpc = _Rpc(process, time.monotonic() + 1)
    rpc.buffer = json.dumps(event).encode() + b"\n"
    with pytest.raises(CodexBridgeError, match="disabled tool"):
        rpc.next()
    if "id" in event:
        rejected = json.loads(process.stdin.getvalue())
        assert rejected["id"] == event["id"]
        assert "error" in rejected
