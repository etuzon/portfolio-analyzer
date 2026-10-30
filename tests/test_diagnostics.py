"""Independent acceptance checks for redacted, bounded, durable component logs."""
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from app.diagnostics import COMPONENTS, TRACE_ID, Diagnostics, Redactor, ZipLogHandler


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("text,private", [
    ('{"tool_arguments": "{\\"password\\": \\"qa-serialized-private\\"}"}', "qa-serialized-private"),
    ('{"password": "qa-json-private"}', "qa-json-private"),
    ("password=qa first second", "second"),
    ("Authorization: Bearer qa-bearer-private", "qa-bearer-private"),
    ("Cookie: session_id=qa-cookie-private; another=qa-second-cookie", "qa-second-cookie"),
    ("https://qa-user:qa-url-private@example.invalid/resource", "qa-url-private"),
    ("https://qa-user-token-private@example.invalid/resource", "qa-user-token-private"),
    ("https://example.invalid/?access_token=qa-query-private&sort=date", "qa-query-private"),
    ("postgresql://qa-user:qa-db-private@example.invalid/database", "qa-db-private"),
    ("session_token=qa-session-private", "qa-session-private"),
    ("auth_token=qa-auth-private", "qa-auth-private"),
    ("id_token=qa-id-private", "qa-id-private"),
    ("client_secret=qa-client-private", "qa-client-private"),
    ("credential=qa-credential-private", "qa-credential-private"),
    ('password: "qa one \\"quoted\\" second"', "second"),
])
def test_free_text_secret_redaction(text, private):
    assert private not in Redactor().text(text)


def test_nested_credentials_and_configured_values_are_redacted():
    redactor = Redactor({"provider": {"api_key": "qa-configured-private"}, "sources": [{"password": "qa-database-private"}]})
    raw = {"tool": {"arguments": {"password": "qa-nested-private", "api_key": "qa-key-private", "safe": "The value qa-configured-private failed"}}, "error": "qa-database-private"}
    cleaned = json.dumps(redactor.clean(raw))
    assert all(secret not in cleaned for secret in ("qa-configured-private", "qa-database-private", "qa-nested-private", "qa-key-private"))
    assert "The value" in cleaned


@pytest.mark.parametrize("password", ["q7!", "a", "7"])
def test_short_known_configuration_password_is_redacted_from_free_text(password):
    redactor = Redactor({"external_import": {"db": {"password": password}}})
    assert redactor.text(f"upstream rejected {password}") == "upstream rejected [REDACTED]"
    reference = "a67f5020-72ab-4cba-98e4-487db75d53fe"
    assert redactor.text(reference) == reference


@pytest.mark.parametrize("field", ["__Host-portfolio_session", "X-CSRF-Token", "session", "csrf", "private_key", "private-key"])
def test_session_csrf_private_key_redaction_in_plain_and_serialized_values(field):
    redactor = Redactor()
    private = "qa-extended-private-value"
    request_id = "a67f5020-72ab-4cba-98e4-487db75d53fe"
    payload = {"request_id": request_id, "tool_arguments": {field: private}}
    for value in (payload, json.dumps(payload), json.dumps({"arguments": json.dumps(payload)}), f"{field}={private}\nrequest_id={request_id}"):
        cleaned = redactor.clean(value)
        encoded = json.dumps(cleaned)
        assert private not in encoded
        assert request_id in encoded


@pytest.mark.parametrize("kind", ["PRIVATE KEY", "RSA PRIVATE KEY", "EC PRIVATE KEY"])
def test_pem_private_key_blocks_redacted_from_plain_and_serialized_text(kind):
    redactor = Redactor()
    private = "qa-synthetic-pem-private-body"
    key = f"-----BEGIN {kind}-----\n{private}\n-----END {kind}-----"
    for value in (key, {"result": key}, json.dumps({"result": key}), "tool result: " + json.dumps(key)):
        assert private not in json.dumps(redactor.clean(value))


def test_rotated_zip_keeps_redacted_session_csrf_and_private_key_data_with_uuid(tmp_path):
    diagnostics = Diagnostics(tmp_path)
    request_id = "a67f5020-72ab-4cba-98e4-487db75d53fe"
    credentials = {"__Host-portfolio_session": "qa-session-zip-private", "X-CSRF-Token": "qa-csrf-zip-private", "private_key": "qa-key-zip-private"}
    try:
        diagnostics.event("chat", "request_received", request_id=request_id, arguments=credentials, serialized_arguments=json.dumps(credentials), result="-----BEGIN PRIVATE KEY-----\nqa-pem-zip-private\n-----END PRIVATE KEY-----")
        diagnostics.handlers["chat"].doRollover()
        diagnostics.event("chat", "request_completed", request_id=request_id)
        with zipfile.ZipFile(tmp_path / "chat.log.1.zip") as archive:
            text = archive.read("chat.log").decode("utf-8")
        record = json.loads(text)
        assert record["request_id"] == request_id
        assert record["event"] == "request_received"
        assert all(private not in text for private in (*credentials.values(), "qa-pem-zip-private"))
        assert _records(tmp_path / "chat.log")[0]["request_id"] == request_id
    finally:
        diagnostics.close()


def _emit(handler, text):
    handler.emit(logging.LogRecord("qa", logging.INFO, "", 0, text, (), None))


def test_default_component_settings_and_separate_chat_file(tmp_path, capsys):
    diagnostics = Diagnostics(tmp_path)
    try:
        settings = diagnostics.settings()
        assert settings["max_files"] == 10
        assert settings["max_size_mb"] == 10
        assert set(settings["components"]) == set(COMPONENTS)
        marker = TRACE_ID.set("qa-trace-id")
        try:
            diagnostics.event("chat", "request_received", prompt="QA chat prompt")
            diagnostics.event("portfolio", "portfolio_updated")
        finally:
            TRACE_ID.reset(marker)
        assert _records(tmp_path / "chat.log")[0]["request_id"] == "qa-trace-id"
        assert "QA chat prompt" not in (tmp_path / "application.log").read_text()
        assert "QA chat prompt" not in capsys.readouterr().out
        assert _records(tmp_path / "portfolio.log")[0]["event"] == "portfolio_updated"
        assert all(handler.maxBytes == 10 * 1024 * 1024 for handler in diagnostics.handlers.values())
    finally:
        diagnostics.close()


def test_rotation_keeps_ten_total_files_and_zip_oldest_is_removed(tmp_path):
    path = tmp_path / "chat.log"
    handler = ZipLogHandler(path, max_bytes=150, max_files=10)
    try:
        for index in range(24):
            _emit(handler, f"event-{index:02d} " + "x" * 110)
        files = sorted(tmp_path.iterdir())
        assert len(files) == 10
        assert {item.name for item in files} == {"chat.log", *(f"chat.log.{n}.zip" for n in range(1, 10))}
        assert "event-23" in path.read_text()
        with zipfile.ZipFile(tmp_path / "chat.log.1.zip") as archive:
            assert archive.namelist() == ["chat.log"]
            assert "event-22" in archive.read("chat.log").decode()
        with zipfile.ZipFile(tmp_path / "chat.log.9.zip") as archive:
            assert "event-14" in archive.read("chat.log").decode()
        assert all(item.stat().st_mode & 0o077 == 0 for item in files)
    finally:
        handler.close()


def test_rotation_counts_unicode_bytes_and_one_file_configuration(tmp_path):
    path = tmp_path / "chat.log"
    handler = ZipLogHandler(path, max_bytes=99, max_files=1)
    try:
        for index in range(12):
            _emit(handler, f"{index}:" + "שלום" * 5)
            assert path.stat().st_size <= 99
        assert list(tmp_path.iterdir()) == [path]
        assert "11:" in path.read_text()
        assert not any(line.startswith("0:") for line in path.read_text().splitlines())
    finally:
        handler.close()


def test_lower_retention_and_size_apply_immediately_on_restart(tmp_path):
    # Model valid artifacts left by a previous process, independently of its writer.
    (tmp_path / "chat.log").write_bytes(b"x" * (2 * 1024 * 1024))
    for index in range(1, 10):
        with zipfile.ZipFile(tmp_path / f"chat.log.{index}.zip", "w") as archive:
            archive.writestr("chat.log", f"old-{index}")
    diagnostics = Diagnostics(tmp_path, max_files=3, max_size_mb=1)
    try:
        assert len(list(tmp_path.glob("chat.log*"))) <= 3
        assert (tmp_path / "chat.log").stat().st_size <= 1024 * 1024
        diagnostics.configure(1, 1)
        assert [item.name for item in tmp_path.glob("chat.log*")] == ["chat.log"]
    finally:
        diagnostics.close()


def test_missing_active_file_recovers_on_startup_and_large_events_stay_bounded(tmp_path):
    with zipfile.ZipFile(tmp_path / "chat.log.1.zip", "w") as archive:
        archive.writestr("chat.log", "older record")
    diagnostics = Diagnostics(tmp_path, max_size_mb=1)
    try:
        diagnostics.event("chat", "large_response", result=["שלום" * 20000] * 20)
        assert (tmp_path / "chat.log").stat().st_size <= 1024 * 1024
        assert _records(tmp_path / "chat.log")[0]["truncated"] is True
    finally:
        diagnostics.close()


@pytest.mark.parametrize("files,size", [(0, 10), (101, 10), (True, 10), (2.5, 10), ("10", 10), (10, 0), (10, 1025), (10, True), (10, "10")])
def test_invalid_settings_rejected_without_reconfiguring(tmp_path, files, size):
    diagnostics = Diagnostics(tmp_path)
    try:
        previous = diagnostics.settings()
        with pytest.raises(ValueError):
            diagnostics.configure(files, size)
        assert diagnostics.settings() == previous
    finally:
        diagnostics.close()


def test_component_logger_follows_replaced_manager(tmp_path, monkeypatch):
    logger = logging.getLogger("app")
    monkeypatch.setattr(logger, "handlers", [])
    monkeypatch.setattr(logger, "propagate", False)
    first = Diagnostics(tmp_path / "first")
    second = Diagnostics(tmp_path / "second")
    try:
        first.install()
        first.close()
        second.install()
        logger.warning("qa-after-manager-replacement")
        assert "qa-after-manager-replacement" in (second.directory / "application.log").read_text()
        assert "qa-after-manager-replacement" not in (first.directory / "application.log").read_text()
    finally:
        first.close()
        second.close()


def test_failed_handler_reconfiguration_closes_partial_handlers_and_preserves_writer(tmp_path, monkeypatch):
    import app.diagnostics as module
    diagnostics = Diagnostics(tmp_path)
    original = module.ZipLogHandler
    created = []
    def fail_after_two(*args, **kwargs):
        if len(created) == 2:
            raise OSError("QA simulated full volume")
        handler = original(*args, **kwargs)
        created.append(handler)
        return handler
    monkeypatch.setattr(module, "ZipLogHandler", fail_after_two)
    try:
        previous = diagnostics.settings()
        with pytest.raises(OSError):
            diagnostics.configure(2, 1)
        assert diagnostics.settings() == previous
        assert all(handler._closed for handler in created)
        diagnostics.event("application", "after_failed_reconfigure")
        assert _records(tmp_path / "application.log")[-1]["event"] == "after_failed_reconfigure"
    finally:
        diagnostics.close()


def test_events_survive_process_exit_without_python_cleanup(tmp_path):
    script = "\n".join([
        "import os, sys",
        "from pathlib import Path",
        "from app.diagnostics import Diagnostics",
        "manager = Diagnostics(Path(sys.argv[1]))",
        "manager.event('chat', 'before_hard_exit', request_id='qa-crash-correlation')",
        "os._exit(37)",
    ])
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=False)
    assert result.returncode == 37
    assert _records(tmp_path / "chat.log")[0]["request_id"] == "qa-crash-correlation"
    restarted = Diagnostics(tmp_path)
    try:
        restarted.event("chat", "after_restart")
        assert [row["event"] for row in _records(tmp_path / "chat.log")] == ["before_hard_exit", "after_restart"]
    finally:
        restarted.close()
