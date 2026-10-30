"""Redacted, durable component diagnostics with bounded ZIP rotation."""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
from threading import RLock
from typing import Any
import zipfile
from contextvars import ContextVar


COMPONENTS = ("application", "http", "portfolio", "market-data", "auth", "chat")
TRACE_ID: ContextVar[str] = ContextVar("application_trace_id", default="")
SENSITIVE = re.compile(r"password|passwd|passphrase|token|secret|credential|authorization|cookie|session|csrf|private[_-]?key|api[_-]?key|connection[_-]?string", re.I)
_ASSIGNMENT = re.compile(r'''(?ix)
    (\b[\w.-]*(?:password|passwd|passphrase|api[_-]?key|token|secret|credential|authorization|cookie|connection[_-]?string|session|csrf|private[_-]?key|סיסמה|סיסמא)[\w.-]*\b)
    (["']?\s*(?:[:=]|\bis\b|היא)\s*)
    (?:"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|[^\n;&]+)
''')


class Redactor:
    def __init__(self, config: dict[str, Any] | None = None):
        self.secrets: set[str] = set()
        self._collect(config or {})

    def _collect(self, value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if SENSITIVE.search(str(key)) and isinstance(item, str) and item:
                    self.secrets.add(item)
                elif isinstance(item, (dict, list)):
                    self._collect(item)
        elif isinstance(value, list):
            for item in value:
                self._collect(item)

    def text(self, value: str) -> str:
        from urllib.parse import unquote
        if value.lstrip().startswith(("{", "[")):
            try:
                structured = json.loads(value)
            except (ValueError, RecursionError):
                structured = None
            if isinstance(structured, (dict, list)):
                return json.dumps(self.clean(structured), ensure_ascii=False, default=str)
        for secret in sorted(self.secrets, key=len, reverse=True):
            if len(secret) >= 4:
                value = value.replace(secret, "[REDACTED]")
            else:
                # Short external-source credentials are valid too. Match them
                # as standalone values so unrelated UUIDs remain searchable.
                value = re.sub(r"(?<!\w)" + re.escape(secret) + r"(?!\w)", "[REDACTED]", value)
        value = re.sub(r"([?&])([^=&\s]+)=([^&\s]+)", lambda match: match[1] + match[2] + "=[REDACTED]" if SENSITIVE.search(unquote(match[2])) else match[0], value)
        value = re.sub(r"(?im)\b(?:set-cookie|cookie)\s*:[^\n]*", "Cookie: [REDACTED]", value)
        value = re.sub(r"(?i)(https?://)[^\s/@]+@", r"\1[REDACTED]@", value)
        value = re.sub(r"-----BEGIN (?:[A-Z ]*PRIVATE KEY)-----.*?-----END (?:[A-Z ]*PRIVATE KEY)-----", "[REDACTED PRIVATE KEY]", value, flags=re.S)
        # Model arguments can contain JSON serialized inside a string, including
        # an additional escaped-quote layer. Scrub that representation too.
        value = re.sub(r'''(?ix)(["\\]*\b[\w.-]*(?:password|passwd|passphrase|api[_-]?key|token|secret|credential|authorization|cookie|session|csrf|private[_-]?key)[\w.-]*["\\]*\s*:\s*["\\]*)([^"\\\n]+)''', r"\1[REDACTED]", value)
        value = re.sub(r"(?i)\bBearer\s+[^\s,;\"']+", "Bearer [REDACTED]", value)
        value = re.sub(r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s\"']+", "[REDACTED CONNECTION]", value)
        value = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{12,}|eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,})\b", "[REDACTED]", value)
        return _ASSIGNMENT.sub(lambda match: match[1] + match[2] + "[REDACTED]", value)

    def clean(self, value: Any, depth: int = 0) -> Any:
        if depth > 12:
            return "[DEPTH LIMIT]"
        if isinstance(value, dict):
            return {str(key): "[REDACTED]" if SENSITIVE.search(str(key)) else self.clean(item, depth + 1) for key, item in list(value.items())[:200]}
        if isinstance(value, (list, tuple)):
            return [self.clean(item, depth + 1) for item in value[:200]]
        if isinstance(value, str):
            text = self.text(value)
            return text if len(text) <= 65_536 else text[:65_536] + " [TRUNCATED]"
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return self.text(str(value))[:65_536]


class RedactingFormatter(logging.Formatter):
    def __init__(self, formatter: logging.Formatter, redactor: Redactor):
        super().__init__()
        self.original, self.redactor = formatter, redactor

    def format(self, record: logging.LogRecord) -> str:
        return self.redactor.text(self.original.format(record))


class ZipLogHandler(RotatingFileHandler):
    def __init__(self, path: Path, max_bytes: int, max_files: int):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        super().__init__(path, maxBytes=max_bytes, backupCount=max_files - 1, encoding="utf-8")
        self.namer = lambda filename: filename + ".zip"
        self.rotator = self._zip
        Path(self.baseFilename).chmod(0o600)

    @staticmethod
    def _zip(source: str, destination: str) -> None:
        target = Path(destination)
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(source, arcname=Path(source).name)
            temporary.chmod(0o600)
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
            temporary.replace(target)
            Path(source).unlink()
        finally:
            temporary.unlink(missing_ok=True)

    def shouldRollover(self, record: logging.LogRecord) -> bool:
        self.stream.seek(0, os.SEEK_END)
        return self.stream.tell() > 0 and self.stream.tell() + len((self.format(record) + "\n").encode("utf-8")) > self.maxBytes

    def doRollover(self) -> None:
        if self.backupCount == 0:
            self.stream.close()
            self.stream = self._open_truncated()
        else:
            super().doRollover()
        Path(self.baseFilename).chmod(0o600)

    def _open_truncated(self):
        return open(self.baseFilename, "w", encoding="utf-8")

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        if self.stream:
            self.stream.flush()
            os.fsync(self.stream.fileno())


class ComponentHandler(logging.Handler):
    def __init__(self, manager: "Diagnostics"):
        super().__init__()
        self.manager = manager

    def emit(self, record: logging.LogRecord) -> None:
        component = "application"
        if record.name.startswith(("app.providers", "httpx", "httpcore")):
            component = "market-data"
        elif record.name.startswith("app.auth"):
            component = "auth"
        elif record.name.startswith(("app.local_portfolio", "app.portfolio_refresh")):
            component = "portfolio"
        self.manager.event(component, "component_message", level=record.levelno, logger=record.name, message=record.getMessage(), exception=logging.Formatter().formatException(record.exc_info) if record.exc_info else None)


class Diagnostics:
    def __init__(self, directory: Path, *, max_files: int = 10, max_size_mb: int = 10, config: dict[str, Any] | None = None):
        self.directory = directory
        self.lock = RLock()
        self.redactor = Redactor(config)
        self.handlers: dict[str, ZipLogHandler] = {}
        self.configure(max_files, max_size_mb)

    def configure(self, max_files: int, max_size_mb: int) -> None:
        if type(max_files) is not int or not 1 <= max_files <= 100:
            raise ValueError("Log file count must be between 1 and 100.")
        if type(max_size_mb) is not int or not 1 <= max_size_mb <= 1024:
            raise ValueError("Log file size must be between 1 and 1024 MB.")
        with self.lock:
            pending = {}
            try:
                for name in COMPONENTS:
                    pending[name] = ZipLogHandler(self.directory / f"{name}.log", max_size_mb * 1024 * 1024, max_files)
            except Exception:
                for handler in pending.values():
                    handler.close()
                raise
            for handler in self.handlers.values():
                handler.close()
            self.max_files, self.max_size_mb = max_files, max_size_mb
            self.handlers = pending
            for name, handler in self.handlers.items():
                # Apply lower retention immediately, including leftovers after a crash.
                for path in self.directory.glob(f"{name}.log.*.zip"):
                    match = re.fullmatch(re.escape(name) + r"\.log\.(\d+)\.zip", path.name)
                    if match and int(match[1]) >= max_files:
                        path.unlink()
                if Path(handler.baseFilename).stat().st_size > handler.maxBytes:
                    handler.doRollover()

    def settings(self) -> dict[str, Any]:
        return {"max_files": self.max_files, "max_size_mb": self.max_size_mb, "directory": str(self.directory), "components": list(COMPONENTS)}

    def event(self, component: str, event: str, *, level: int = logging.INFO, **fields: Any) -> None:
        from datetime import datetime, timezone
        if component not in COMPONENTS:
            component = "application"
        data = self.redactor.clean({"timestamp": datetime.now(timezone.utc).isoformat(), "level": logging.getLevelName(level), "component": component, "event": event, "request_id": TRACE_ID.get(), **fields})
        encoded = json.dumps(data, ensure_ascii=False, default=str)
        with self.lock:
            handler = self.handlers[component]
            if len(encoded.encode("utf-8")) + 1 > handler.maxBytes:
                data = {key: data.get(key) for key in ("timestamp", "level", "component", "event", "request_id")}
                data["truncated"] = True
                encoded = json.dumps(data, ensure_ascii=False)
            record = logging.LogRecord(f"diagnostics.{component}", level, "", 0, encoded, (), None)
            try:
                handler.emit(record)
            except OSError:
                # The UUID remains searchable in container logs on storage failure.
                print(json.dumps({"event": "diagnostic_write_failed", "request_id": data.get("request_id"), "component": component}), file=sys.stderr, flush=True)
        if component == "chat":
            # Detailed prompts/results stay in chat.log; container logs get correlation only.
            print(json.dumps({"event": event, "component": "chat", "request_id": data.get("request_id"), "status": data.get("status")}), flush=True)

    def install(self) -> None:
        logging.raiseExceptions = False
        component_handler = ComponentHandler(self)
        for name in ("app", "uvicorn.error"):
            target = logging.getLogger(name)
            existing = [handler for handler in target.handlers if isinstance(handler, ComponentHandler)]
            for handler in existing:
                handler.manager = self
            if not existing:
                target.addHandler(component_handler)
        # Redact after formatting, preserving Uvicorn's positional access-log arguments.
        for name in ("", "uvicorn", "uvicorn.access", "uvicorn.error", "httpx", "httpcore", "app"):
            for handler in logging.getLogger(name).handlers:
                if isinstance(handler, ComponentHandler):
                    continue
                formatter = handler.formatter or logging.Formatter("%(message)s")
                if isinstance(formatter, RedactingFormatter):
                    formatter.redactor = self.redactor
                else:
                    handler.setFormatter(RedactingFormatter(formatter, self.redactor))

    def close(self) -> None:
        for handler in self.handlers.values():
            handler.close()
