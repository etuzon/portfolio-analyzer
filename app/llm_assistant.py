"""Read-only tool loop for an OpenAI-compatible portfolio assistant.

The model never receives credentials and never chooses arbitrary URLs.  It can
only ask for an entry in the supplied read-tool catalog; the application owns
the implementation of each entry.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib import error, request


class AssistantError(ValueError):
    """A safe error that can be shown to an authenticated user."""


def assistant_settings(raw: dict[str, Any]) -> dict[str, Any]:
    section = raw.get("llm") if isinstance(raw.get("llm"), dict) else {}
    reasoning_effort = str(section.get("reasoning_effort") or "medium").lower()
    if reasoning_effort not in {"none", "minimal", "low", "medium", "high", "xhigh", "max"}:
        reasoning_effort = "medium"
    return {
        "enabled": bool(section.get("enabled", False)),
        "base_url": str(section.get("base_url") or "").rstrip("/"),
        "api_key": str(section.get("api_key") or ""),
        "model": str(section.get("model") or ""),
        "reasoning_effort": reasoning_effort,
        "max_tool_loops": min(max(int(section.get("max_tool_loops", 6) or 6), 1), 12),
        "max_context_messages": min(max(int(section.get("max_context_messages", 12) or 12), 0), 30),
        "timeout_seconds": min(max(int(section.get("timeout_seconds", 30) or 30), 1), 120),
    }


def tool_definitions(catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": item["description"],
                "parameters": item.get("parameters", {"type": "object", "properties": {}}),
            },
        }
        for name, item in catalog.items()
    ]


class PortfolioAssistant:
    def __init__(self, settings: dict[str, Any], catalog: dict[str, dict[str, Any]], caller: Callable[..., dict[str, Any]] | None = None):
        self.settings, self.catalog = settings, catalog
        self.caller = caller or self._call_provider

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.settings["enabled"] and bool(self.settings["base_url"] and self.settings["api_key"] and self.settings["model"]),
            "model": self.settings["model"] if self.settings["enabled"] else "",
            "max_tool_loops": self.settings["max_tool_loops"],
            "tools": [{"name": name, "method": item.get("method", "GET"), "path": item["path"], "description": item["description"]} for name, item in self.catalog.items()],
        }

    def ask(self, prompt: str, language: str, run_tool: Callable[[str, dict[str, Any]], Any], history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if not self.status()["enabled"]:
            raise AssistantError("The portfolio assistant is not configured. Ask an administrator to enable the llm section in config.yaml.")
        prompt = str(prompt or "").strip()
        if not prompt or len(prompt) > 8_000:
            raise AssistantError("Ask a question between 1 and 8000 characters.")
        language = str(language or "").strip()[:24]
        messages: list[dict[str, Any]] = [{
            "role": "system",
            "content": (
                "You are a read-only portfolio assistant. Use tools when portfolio facts are needed. "
                "Tools map to internal GET endpoints; never request a URL, mutation, credentials, or instructions outside these tools. "
                "Give a short, clear answer in the user's language (" + (language or "the prompt language") + "). "
                "Use simple words, state missing data, and do not present investment advice."
                " For world-event impacts, historical stock-move explanations or event-related probabilities, "
                "first use get_event_impact_workflow when available and follow its evidence and validation gates. "
                "Use get_event_impact_cases when available to check saved historical examples for the relevant ticker; "
                "use get_event_impact_events to discover event IDs and follow case next_offset pagination without treating a page as a complete sample. "
                "respect each case's evidence limits and do not turn an observed decline into a probability. "
                "Never invent probabilities or price, revenue or net-income effects. Unsupported values are unknown. "
                "Separate historical frequency from validated forecasts, and evidence confidence from outcome probability. "
                "Do not claim automatic learning, case storage or current-event verification without actual supporting tools and evidence."
            ),
        }]
        for item in (history or [])[-self.settings["max_context_messages"]:]:
            if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
                continue
            content = str(item.get("content") or "").strip()
            if content:
                messages.append({"role": item["role"], "content": content[:8_000]})
        messages.append({"role": "user", "content": prompt})
        calls: list[dict[str, Any]] = []
        for _ in range(self.settings["max_tool_loops"]):
            message = self._completion(messages)
            messages.append(message)
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                content = str(message.get("content") or "").strip()
                if not content:
                    raise AssistantError("The LLM returned an empty answer.")
                return {"answer": content, "tool_calls": calls, "max_tool_loops": self.settings["max_tool_loops"]}
            for tool_call in tool_calls:
                name = str((tool_call.get("function") or {}).get("name") or "")
                call_id = str(tool_call.get("id") or name)
                try:
                    arguments = json.loads((tool_call.get("function") or {}).get("arguments") or "{}")
                    if not isinstance(arguments, dict) or name not in self.catalog:
                        raise AssistantError("The LLM requested an unavailable read tool.")
                    result = run_tool(name, arguments)
                    calls.append({"tool": name, "path": self.catalog[name]["path"], "arguments": arguments})
                    content = json.dumps(result, default=str, ensure_ascii=False)[:80_000]
                except (ValueError, TypeError, AssistantError) as exc:
                    content = json.dumps({"error": str(exc)})
                messages.append({"role": "tool", "tool_call_id": call_id, "content": content})
        raise AssistantError(f"The assistant reached the configured {self.settings['max_tool_loops']}-step read limit. Please ask a narrower question.")

    def _completion(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        response = self.caller(messages=messages, tools=tool_definitions(self.catalog))
        try:
            message = response["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AssistantError("The LLM returned an unsupported response.") from exc
        return message if isinstance(message, dict) else {}

    def _call_provider(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        body = json.dumps({
            "model": self.settings["model"],
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "reasoning_effort": self.settings["reasoning_effort"],
            "temperature": 0.2,
        }).encode()
        endpoint = f"{self.settings['base_url']}/chat/completions"
        req = request.Request(endpoint, data=body, headers={"Authorization": f"Bearer {self.settings['api_key']}", "Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=self.settings["timeout_seconds"]) as response:
                return json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AssistantError("The LLM service is unavailable. Try again later.") from exc
