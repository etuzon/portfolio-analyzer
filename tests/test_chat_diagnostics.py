"""Independent API acceptance checks for chat correlation and log administration."""
import json
import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import AppConfig
from app.llm_assistant import AssistantError, PortfolioAssistant
from test_assistant_security import authenticated_chats


@pytest.fixture
def diagnostic_chat_env(authenticated_chats):
    env = authenticated_chats
    env.patch.setattr(main, "_diagnostics_instance", None)
    try:
        yield env
    finally:
        if main._diagnostics_instance is not None:
            main._diagnostics_instance.close()


def _logs(env, component="chat"):
    path = env.store.path.parent / "logs" / f"{component}.log"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def _provider_answer(answer="QA verified response", status="answered"):
    return {"choices": [{"message": {"role": "assistant", "content": json.dumps({"answer": answer, "support_status": status})}}]}


def _id(response):
    identifier = response.headers["X-Request-ID"]
    assert str(UUID(identifier)) == identifier
    return identifier


def test_logging_settings_admin_permissions_persistence_and_financial_independence(diagnostic_chat_env):
    env = diagnostic_chat_env
    anonymous = TestClient(main.app, base_url="https://localhost:6443")
    assert anonymous.get("/api/settings/logging").status_code == 401
    admin = env.login()
    viewer = env.login("qa-log-viewer", "Viewer")
    assert viewer.get("/api/settings/logging").status_code == 403
    assert viewer.put("/api/settings/logging", json={"max_files": 2, "max_size_mb": 1}).status_code == 403
    defaults = admin.get("/api/settings/logging")
    assert defaults.status_code == 200
    assert defaults.json()["max_files"] == 10
    assert defaults.json()["max_size_mb"] == 10
    baseline = env.store.change_token()
    saved = admin.put("/api/settings/logging", json={"max_files": 3, "max_size_mb": 1})
    assert saved.status_code == 200
    assert env.store.change_token() == baseline
    assert env.store.get_preference("logging_settings")["max_files"] == 3
    main._diagnostics_instance.close()
    main._diagnostics_instance = None
    restarted = admin.get("/api/settings/logging")
    assert restarted.json()["max_files"] == 3
    assert restarted.json()["max_size_mb"] == 1
    admin.headers.pop("X-CSRF-Token")
    assert admin.put("/api/settings/logging", json={"max_files": 2, "max_size_mb": 1}).status_code == 403


@pytest.mark.parametrize("payload", [
    {"max_files": 0, "max_size_mb": 10},
    {"max_files": 101, "max_size_mb": 10},
    {"max_files": True, "max_size_mb": 10},
    {"max_files": "10", "max_size_mb": 10},
    {"max_files": 2.5, "max_size_mb": 10},
    {"max_files": 10, "max_size_mb": 0},
    {"max_files": 10, "max_size_mb": 1025},
    {"max_files": 10, "max_size_mb": True},
    {"max_files": 10},
    {"max_files": 10, "max_size_mb": 10, "directory": "/tmp/should-not-be-accepted"},
])
def test_logging_settings_invalid_payloads_preserve_saved_settings(diagnostic_chat_env, payload):
    env = diagnostic_chat_env
    admin = env.login()
    before = admin.get("/api/settings/logging").json()
    assert admin.put("/api/settings/logging", json=payload).status_code in {400, 422}
    after = admin.get("/api/settings/logging").json()
    assert before == after


@pytest.mark.parametrize("language", ["en", "he"])
def test_unsupported_reply_is_localized_and_correlated_to_logs(diagnostic_chat_env, language):
    env = diagnostic_chat_env
    client = env.login()
    env.patch.setattr(PortfolioAssistant, "_call_provider", lambda *a, **k: _provider_answer("QA model claims it updated the database", "unsupported"))
    response = client.post("/api/assistant/questions", json={"prompt": "Modify a database table", "language": language})
    assert response.status_code == 200
    request_id = _id(response)
    answer = response.json()["answer"]
    assert request_id in answer
    assert "QA model claims" not in answer
    assert bool(re.search(r"[\u0590-\u05ff]", answer)) == (language == "he")
    assert response.json()["chat"]["messages"][-1]["content"] == answer
    events = [row for row in _logs(env) if row["request_id"] == request_id]
    assert {row["event"] for row in events} >= {"request_received", "model_request", "model_response", "request_completed"}
    assert all(row["request_id"] == request_id for row in events)


@pytest.mark.parametrize("language", ["en", "he"])
def test_provider_failure_has_localized_uuid_and_redacted_error_log(diagnostic_chat_env, language):
    env = diagnostic_chat_env
    client = env.login()
    def fail(*args, **kwargs):
        raise AssistantError("The LLM service is unavailable; password=qa error private.")
    env.patch.setattr(PortfolioAssistant, "_call_provider", fail)
    response = client.post("/api/assistant/questions", json={"prompt": "Read my accounts", "language": language})
    assert response.status_code == 503
    request_id = _id(response)
    body = json.dumps(response.json(), ensure_ascii=False)
    assert request_id in body
    assert "qa error private" not in body
    assert bool(re.search(r"[\u0590-\u05ff]", body)) == (language == "he")
    events = [row for row in _logs(env) if row["request_id"] == request_id]
    assert {row["event"] for row in events} >= {"request_received", "model_request", "request_failed"}
    assert "qa error private" not in json.dumps(events)
    assert client.post("/api/assistant/chats").status_code == 200


def test_tool_and_model_roundtrips_share_request_uuid(diagnostic_chat_env):
    env = diagnostic_chat_env
    client = env.login()
    replies = iter([
        {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "qa-call", "function": {"name": "list_accounts", "arguments": "{}"}}]}}]},
        _provider_answer(),
    ])
    env.patch.setattr(PortfolioAssistant, "_call_provider", lambda *a, **k: next(replies))
    response = client.post("/api/assistant/questions", json={"prompt": "Read my account inventory", "language": "en"})
    assert response.status_code == 200
    request_id = _id(response)
    events = [row for row in _logs(env) if row["request_id"] == request_id]
    names = [row["event"] for row in events if row["event"] != "context_loaded"]
    assert names == ["request_received", "model_request", "model_response", "tool_request", "tool_response", "model_request", "model_response", "request_completed"]
    http_events = [row for row in _logs(env, "http") if row["request_id"] == request_id]
    assert any(row["path"] == "/api/assistant/questions" for row in http_events)
    assert any(row["path"] == "/api/local/accounts" for row in http_events)


def test_invalid_tool_request_failure_is_logged_and_safe_reply_recovers(diagnostic_chat_env):
    env = diagnostic_chat_env
    client = env.login()
    replies = iter([
        {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "qa-call", "function": {"name": "list_accounts", "arguments": "[1]"}}]}}]},
        _provider_answer(),
    ])
    env.patch.setattr(PortfolioAssistant, "_call_provider", lambda *a, **k: next(replies))
    response = client.post("/api/assistant/questions", json={"prompt": "Read my accounts", "language": "en"})
    assert response.status_code == 200
    events = [row for row in _logs(env) if row["request_id"] == _id(response)]
    assert "tool_failed" in {row["event"] for row in events}


@pytest.mark.parametrize("scenario,status,code", [
    ("invalid_prompt", 400, "assistant_invalid_request"),
    ("invalid_chat_id", 400, "assistant_invalid_request"),
    ("empty_model_response", 502, "assistant_invalid_response"),
    ("source_only_model_response", 502, "assistant_invalid_response"),
    ("unexpected_exception", 500, "assistant_failed"),
])
def test_hebrew_validation_and_unexpected_failures_have_searchable_uuid(diagnostic_chat_env, scenario, status, code):
    env = diagnostic_chat_env
    client = env.login()
    payload = {"prompt": "Read accounts", "language": "he"}
    if scenario == "invalid_prompt":
        payload["prompt"] = " "
    elif scenario == "invalid_chat_id":
        payload["chat_id"] = "a" * 81
    elif scenario == "empty_model_response":
        env.patch.setattr(PortfolioAssistant, "_call_provider", lambda *a, **k: {"choices": [{"message": {"content": ""}}]})
    elif scenario == "source_only_model_response":
        env.patch.setattr(PortfolioAssistant, "_call_provider", lambda *a, **k: _provider_answer("Sources: GET /api/local/accounts"))
    else:
        def fail(*args, **kwargs):
            raise RuntimeError("password=qa unexpected private")
        env.patch.setattr(PortfolioAssistant, "_call_provider", fail)
    response = client.post("/api/assistant/questions", json=payload)
    assert response.status_code == status
    detail = response.json()["detail"]
    assert detail["code"] == code
    assert detail["request_id"] == _id(response)
    assert detail["request_id"] in detail["message"]
    assert re.search(r"[\u0590-\u05ff]", detail["message"])
    events = [row for row in _logs(env) if row["request_id"] == detail["request_id"]]
    assert "request_failed" in {row["event"] for row in events}
    assert "qa unexpected private" not in json.dumps(events)


def test_answer_removes_source_footers_preserves_facts_and_does_not_mark_unknown_as_unsupported(diagnostic_chat_env):
    env = diagnostic_chat_env
    client = env.login()
    env.patch.setattr(PortfolioAssistant, "_call_provider", lambda *a, **k: _provider_answer("The value on 30/10/2026 is unknown.\nSources: GET /api/local/accounts\nמקור: נתוני יישום"))
    response = client.post("/api/assistant/questions", json={"prompt": "Read the missing value", "language": "en"})
    assert response.status_code == 200
    assert response.json()["answer"] == "The value on 30/10/2026 is unknown."
    assert response.json()["support_status"] == "answered"
    assert response.json()["chat"]["messages"][-1]["content"] == response.json()["answer"]


def test_readonly_assistant_catalog_cannot_access_logs_or_logging_settings():
    for name, tool in main.ASSISTANT_READ_TOOLS.items():
        assert "logging" not in name.lower()
        assert not tool["path"].startswith(("/api/settings/logging", "/api/logs", "/api/admin/logs"))


def test_local_bridge_failure_cause_is_redacted_in_log_and_hidden_from_localized_ui(diagnostic_chat_env):
    import httpx
    env = diagnostic_chat_env
    client = env.login()
    class FakeBridgeClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, path, json):
            assert path == "/completion"
            return httpx.Response(503, json={"error": {"type": "CodexBridgeError", "message": "Local Codex timed out. password=qa-bridge-private"}})
    env.patch.setattr(httpx, "Client", FakeBridgeClient)
    env.patch.setattr(main, "config", AppConfig(raw={"llm": {"enabled": True, "provider": "local_codex"}}, path=env.store.path.parent / "unused.yaml"))
    env.patch.setattr(PortfolioAssistant, "status", lambda self: {"enabled": True})
    response = client.post("/api/assistant/questions", json={"prompt": "Read accounts", "language": "he"})
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["request_id"] == _id(response)
    assert "timed out" not in detail["message"]
    assert "qa-bridge-private" not in detail["message"]
    assert re.search(r"[\u0590-\u05ff]", detail["message"])
    errors = [row for row in _logs(env) if row["request_id"] == detail["request_id"] and row["event"] == "request_failed"]
    assert len(errors) == 1
    assert "Local Codex timed out" in errors[0]["error"]
    assert "qa-bridge-private" not in json.dumps(errors)
