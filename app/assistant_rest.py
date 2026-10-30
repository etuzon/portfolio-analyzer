"""The LLM's only data boundary: validated GET requests to fixed app routes."""
from __future__ import annotations

import math
import re
from typing import Any

import httpx

from .llm_assistant import AssistantError


def validate_arguments(arguments: Any, schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise AssistantError("Read tool arguments must be an object.")
    properties = schema.get("properties", {})
    if set(arguments) - set(properties) or set(schema.get("required", [])) - set(arguments):
        raise AssistantError("The read tool received unsupported or missing arguments.")
    for key, value in arguments.items():
        rule = properties[key]
        kind = rule.get("type")
        valid = {
            "string": isinstance(value, str) and len(value) <= 500,
            "integer": type(value) is int,
            "number": type(value) in {int, float} and math.isfinite(value),
            "boolean": type(value) is bool,
        }.get(kind, False)
        if not valid or ("enum" in rule and value not in rule["enum"]):
            raise AssistantError("The read tool received an invalid argument.")
        if kind in {"number", "integer"} and (
            ("minimum" in rule and value < rule["minimum"]) or ("maximum" in rule and value > rule["maximum"])
        ):
            raise AssistantError("The read tool argument is outside its allowed range.")
    return arguments


class AssistantRestGateway:
    def __init__(self, app: Any, catalog: dict[str, Any], headers: dict[str, str]):
        self.app, self.catalog = app, catalog
        # Reuse the caller's authentication, never a privileged service identity.
        self.headers = {key: value for key, value in headers.items() if key.lower() in {"authorization", "cookie"}}

    async def read(self, name: str, arguments: dict[str, Any]) -> Any:
        entry = self.catalog.get(name)
        if not entry or entry.get("method", "GET") != "GET":
            raise AssistantError("The LLM requested an unavailable read tool.")
        arguments = dict(validate_arguments(arguments, entry.get("parameters", {})))
        path = entry["path"]
        if not path.startswith("/api/") or any(token in path for token in ("..", "?", "#", "\\")):
            raise AssistantError("The read tool route is unavailable.")
        for key in re.findall(r"\{([a-z_]+)\}", path):
            value = str(arguments.pop(key, "")).strip()
            if not re.fullmatch(r"[A-Za-z0-9_^.=-]+", value) or ".." in value:
                raise AssistantError("The read tool received an invalid identifier.")
            path = path.replace("{" + key + "}", value)
        # In-process HTTP still passes through FastAPI routing, validation and
        # authentication. No external hosts, redirects, SQL or write verbs exist.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False), base_url="https://portfolio-internal", follow_redirects=False) as client:
            try:
                # Bound provider-backed GETs as part of the per-message budget.
                import anyio
                with anyio.fail_after(40):
                    response = await client.get(path, params=arguments, headers=self.headers)
                if response.status_code != 200:
                    raise AssistantError(f"Approved data request failed (HTTP {response.status_code}).")
                return response.json()
            except (httpx.HTTPError, ValueError, TimeoutError) as exc:
                if isinstance(exc, AssistantError):
                    raise
                raise AssistantError("The approved data request is unavailable.") from exc
