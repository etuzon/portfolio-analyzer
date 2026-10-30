"""Application-owned, per-user chat history. This store is never an LLM tool."""
from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable
from uuid import uuid4


class ChatError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class AssistantChats:
    def __init__(self, read: Callable, write: Callable):
        self.read, self.write = read, write
        self.lock = RLock()
        self.pending: set[str] = set()
        self.pending_new: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(user_id: str) -> str:
        return f"assistant_chats:{user_id}"

    def _load(self, user_id: str) -> dict[str, Any]:
        data = self.read(self._key(user_id), None)
        if isinstance(data, dict) and isinstance(data.get("chats"), list):
            return data
        data = {"max_chats": 10, "chats": []}
        legacy = self.read(f"assistant_context:{user_id}", [])
        messages = [
            {"role": item["role"], "content": str(item.get("content") or "")[:8_000], "created_at": _now()}
            for item in legacy if isinstance(item, dict) and item.get("role") in {"user", "assistant"}
        ] if isinstance(legacy, list) else []
        if messages:
            chat = self._new_chat()
            chat["messages"] = messages
            chat["title"] = next((m["content"][:80] for m in messages if m["role"] == "user"), "")
            data["chats"].append(chat)
            self.write(self._key(user_id), data)
            # Remove the migrated duplicate, so clearing new history cannot resurrect it.
            self.write(f"assistant_context:{user_id}", [])
        return data

    @staticmethod
    def _new_chat() -> dict[str, Any]:
        now = _now()
        return {"id": str(uuid4()), "title": "", "created_at": now, "updated_at": now, "messages": []}

    @staticmethod
    def _summary(data: dict[str, Any]) -> dict[str, Any]:
        return {
            "max_chats": data["max_chats"],
            "chats": [
                {**{key: chat[key] for key in ("id", "title", "created_at", "updated_at")}, "message_count": len(chat["messages"])}
                for chat in sorted(data["chats"], key=lambda item: (item["updated_at"], item["id"]), reverse=True)
            ],
        }

    @staticmethod
    def _find(data: dict[str, Any], chat_id: str) -> dict[str, Any]:
        chat = next((item for item in data["chats"] if item["id"] == chat_id), None)
        if chat is None:
            raise ChatError("Chat not found. Reload your chat history.", 404)
        return chat

    @staticmethod
    def _prune(data: dict[str, Any]) -> None:
        data["chats"] = sorted(data["chats"], key=lambda item: (item["updated_at"], item["id"]), reverse=True)[:data["max_chats"]]

    def list(self, user_id: str) -> dict[str, Any]:
        with self.lock:
            return self._summary(self._load(user_id))

    def get(self, user_id: str, chat_id: str) -> dict[str, Any]:
        with self.lock:
            return self._find(self._load(user_id), chat_id)

    def _ensure_idle(self, user_id: str) -> None:
        if user_id in self.pending:
            raise ChatError("A question is already running. Wait for its answer.", 409)

    def create(self, user_id: str) -> dict[str, Any]:
        with self.lock:
            self._ensure_idle(user_id)
            data = self._load(user_id)
            chat = self._new_chat()
            data["chats"].append(chat)
            self._prune(data)
            self.write(self._key(user_id), data)
            return {"chat": chat, **self._summary(data)}

    def settings(self, user_id: str, max_chats: Any) -> dict[str, Any]:
        if type(max_chats) is not int or not 1 <= max_chats <= 100:
            raise ChatError("Maximum saved chats must be a whole number between 1 and 100.")
        with self.lock:
            self._ensure_idle(user_id)
            data = self._load(user_id)
            data["max_chats"] = max_chats
            self._prune(data)
            self.write(self._key(user_id), data)
            return self._summary(data)

    def begin(self, user_id: str, chat_id: str | None) -> dict[str, Any]:
        with self.lock:
            self._ensure_idle(user_id)
            if not chat_id:
                # An implicit first chat is committed only with a successful
                # reply. Repeated provider failures must not evict saved chats.
                chat = self._new_chat()
                self.pending_new[user_id] = chat
            else:
                chat = self._find(self._load(user_id), chat_id)
            self.pending.add(user_id)
            return chat

    def finish(self, user_id: str, chat_id: str, prompt: str, result: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            data = self._load(user_id)
            new_chat = self.pending_new.get(user_id)
            if new_chat and new_chat["id"] == chat_id:
                data["chats"].append(new_chat)
            chat = self._find(data, chat_id)
            now = _now()
            chat["messages"].extend([
                {"role": "user", "content": prompt, "created_at": now},
                {"role": "assistant", "content": result["answer"], "created_at": now, "tool_calls": result.get("tool_calls", []), "support_status": result.get("support_status", "answered"), "request_id": result.get("request_id", "")},
            ])
            if not chat["title"]:
                chat["title"] = " ".join(prompt.split())[:80]
            chat["updated_at"] = now
            self._prune(data)
            self.write(self._key(user_id), data)
            return {"chat": chat, **self._summary(data)}

    def end(self, user_id: str) -> None:
        with self.lock:
            self.pending.discard(user_id)
            self.pending_new.pop(user_id, None)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
