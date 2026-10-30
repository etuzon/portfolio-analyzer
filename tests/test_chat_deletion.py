"""Independent synthetic QA for deleting one user's saved chat history."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from fastapi.testclient import TestClient
import pytest

from app import main
from app.assistant_chats import AssistantChats, ChatError
from app.llm_assistant import PortfolioAssistant
from app.local_portfolio import LocalPortfolioStore
from test_assistant_security import authenticated_chats


def _new(client):
    response = client.post("/api/assistant/chats")
    assert response.status_code == 200, response.text
    return response.json()["chat"]["id"]


def test_deletes_only_selected_chat_and_persists_after_restart(tmp_path):
    path = tmp_path / "deletion.sqlite3"
    store = LocalPortfolioStore(path)
    chats = AssistantChats(store.get_preference, store.set_preference)
    chats.settings("owner", 3)
    ids = [chats.create("owner")["chat"]["id"] for _ in range(3)]
    for index, chat_id in enumerate(ids):
        chats.begin("owner", chat_id)
        chats.finish("owner", chat_id, f"Question {index}", {"answer": f"Answer {index}"})
        chats.end("owner")
    other_id = chats.create("other")["chat"]["id"]
    before = {chat_id: copy.deepcopy(chats.get("owner", chat_id)) for chat_id in ids}
    baseline_token = store.change_token()
    result = chats.delete("owner", ids[1])
    assert result == {"deleted": True, "chat_id": ids[1], **chats.list("owner")}
    assert result["max_chats"] == 3
    assert {item["id"] for item in result["chats"]} == {ids[0], ids[2]}
    assert all("messages" not in item for item in result["chats"])
    assert store.change_token() == baseline_token
    restarted_store = LocalPortfolioStore(path)
    restarted = AssistantChats(restarted_store.get_preference, restarted_store.set_preference)
    with pytest.raises(ChatError) as missing:
        restarted.get("owner", ids[1])
    assert missing.value.status_code == 404
    for chat_id in (ids[0], ids[2]):
        assert restarted.get("owner", chat_id) == before[chat_id]
    assert restarted.get("other", other_id)["id"] == other_id
    assert restarted.list("owner")["max_chats"] == 3
    backup = {row["key"]: row["value"] for row in restarted_store.export_data()["data"]["app_preferences"]}
    assert ids[1] not in backup["assistant_chats:owner"]
    replacement = restarted.create("owner")["chat"]["id"]
    assert {item["id"] for item in restarted.list("owner")["chats"]} == {ids[0], ids[2], replacement}


def test_delete_last_migrated_chat_does_not_resurrect_legacy_history(tmp_path):
    store = LocalPortfolioStore(tmp_path / "legacy.sqlite3")
    store.set_preference("assistant_context:owner", [{"role": "user", "content": "Old question"}, {"role": "assistant", "content": "Old answer"}])
    chats = AssistantChats(store.get_preference, store.set_preference)
    chat_id = chats.list("owner")["chats"][0]["id"]
    assert chats.delete("owner", chat_id) == {"deleted": True, "chat_id": chat_id, "max_chats": 10, "chats": []}
    restarted = AssistantChats(store.get_preference, store.set_preference)
    assert restarted.list("owner") == {"max_chats": 10, "chats": []}
    with pytest.raises(ChatError) as repeated:
        restarted.delete("owner", chat_id)
    assert repeated.value.status_code == 404
    assert restarted.create("owner")["chat"]["id"] != chat_id


def test_delete_requires_authentication_csrf_and_ownership(authenticated_chats):
    env = authenticated_chats
    owner = env.login()
    viewer = env.login("delete-viewer", "Viewer")
    chat_id = _new(owner)
    path = f"/api/assistant/chats/{chat_id}"
    assert TestClient(main.app, base_url="https://localhost:6443").delete(path).status_code == 401
    before = owner.get("/api/assistant/chats").json()
    assert viewer.delete(path).status_code == 404
    assert viewer.delete("/api/assistant/chats/unknown-id").status_code == 404
    assert owner.get("/api/assistant/chats").json() == before
    valid_csrf = owner.headers.pop("X-CSRF-Token")
    for headers in ({}, {"X-CSRF-Token": "wrong-token"}):
        rejected = owner.delete(path, headers=headers)
        assert rejected.status_code == 403
        assert rejected.json()["detail"]["code"] == "csrf_failed"
    owner.headers["X-CSRF-Token"] = valid_csrf
    assert owner.get(path).status_code == 200
    assert owner.delete(path).status_code == 200
    assert owner.delete(path).status_code == 404


def test_viewer_can_delete_own_chat_but_cannot_delete_financial_data(authenticated_chats):
    viewer = authenticated_chats.login("self-service-viewer", "Viewer")
    chat_id = _new(viewer)
    assert viewer.delete(f"/api/assistant/chats/{chat_id}").json()["deleted"] is True
    assert viewer.delete("/api/local/accounts/not-owned").status_code == 403


def test_read_only_rest_token_self_service_does_not_grant_financial_writes(authenticated_chats):
    owner = authenticated_chats.login()
    chat_id = _new(owner)
    assert owner.put("/api/settings/api-access", json={"mode": "read_only"}).status_code == 200
    issued = owner.post("/api/auth/token", json={"username": "admin", "password": "QA-Changed-Password-2026!"})
    assert issued.status_code == 200
    bearer = TestClient(main.app, base_url="https://localhost:6443", headers={"Authorization": f"Bearer {issued.json()['access_token']}"})
    response = bearer.delete(f"/api/assistant/chats/{chat_id}")
    assert response.status_code == 200, response.text
    denied = bearer.delete("/api/local/accounts/not-owned")
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "api_read_only"


def test_pending_question_blocks_all_own_deletions_and_preserves_history(authenticated_chats):
    env = authenticated_chats
    owner = env.login()
    other = env.login("concurrent-viewer", "Viewer")
    current, saved = _new(owner), _new(owner)
    other_id = _new(other)
    entered, release = Event(), Event()
    def blocked_answer(*args, **kwargs):
        entered.set()
        assert release.wait(10), "QA must release synthetic provider"
        return {"choices": [{"message": {"role": "assistant", "content": "Synthetic verified answer"}}]}
    env.patch.setattr(PortfolioAssistant, "_call_provider", blocked_answer)
    before = owner.get(f"/api/assistant/chats/{saved}").json()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(owner.post, "/api/assistant/questions", json={"chat_id": current, "prompt": "Hold this question"})
        try:
            assert entered.wait(10)
            for chat_id in (current, saved):
                response = owner.delete(f"/api/assistant/chats/{chat_id}")
                assert response.status_code == 409, response.text
            assert owner.get(f"/api/assistant/chats/{saved}").json() == before
            assert other.delete(f"/api/assistant/chats/{other_id}").status_code == 200
        finally:
            release.set()
        assert pending.result(timeout=10).status_code == 200
    assert owner.delete(f"/api/assistant/chats/{current}").status_code == 200
    assert owner.get(f"/api/assistant/chats/{saved}").json() == before


def test_successful_deletion_is_audited_without_llm_or_financial_cache_changes(authenticated_chats):
    env = authenticated_chats
    client = env.login()
    chat_id = _new(client)
    def no_provider(*args, **kwargs):
        pytest.fail("Deleting saved history must not contact an LLM")
    env.patch.setattr(PortfolioAssistant, "_call_provider", no_provider)
    before_token = env.store.change_token()
    before_generation = main._portfolio_cache_generation
    result = client.delete(f"/api/assistant/chats/{chat_id}")
    assert result.status_code == 200
    assert env.store.change_token() == before_token
    assert main._portfolio_cache_generation == before_generation
    events = [json.loads(line) for file in (env.store.path.parent / "logs").glob("chat*.log") for line in file.read_text().splitlines()]
    deletions = [event for event in events if event.get("event") == "chat_deleted"]
    assert len(deletions) == 1
    assert deletions[0]["chat_id"] == chat_id
    assert deletions[0]["user_id"] == client.get("/api/auth/session").json()["user"]["id"]
    assert not any("delete" in name.casefold() or "chats" in spec["path"] for name, spec in main.ASSISTANT_READ_TOOLS.items())
    assert client.get("/api/assistant/read-tools").status_code == 200


def test_repeated_concurrent_delete_is_atomic_and_cannot_remove_another_chat(authenticated_chats):
    owner = authenticated_chats.login()
    target, survivor = _new(owner), _new(owner)
    before = owner.get(f"/api/assistant/chats/{survivor}").json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: owner.delete(f"/api/assistant/chats/{target}"), range(2)))
    assert sorted(result.status_code for result in results) == [200, 404]
    assert owner.get(f"/api/assistant/chats/{survivor}").json() == before
    assert {chat["id"] for chat in owner.get("/api/assistant/chats").json()["chats"]} == {survivor}
