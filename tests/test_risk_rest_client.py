"""Independent offline contracts for the REST-only support runner.

MockTransport validates request semantics; these tests do not establish live
model, Internet or private-portfolio retrieval success.
"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest


@pytest.fixture(scope="module")
def runner():
    path = Path(__file__).resolve().parents[1] / "scripts/research-risk-inputs.py"
    spec = importlib.util.spec_from_file_location("risk_rest_client_qa", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def options(**overrides):
    return SimpleNamespace(**(dict(request_id=None, resume_request_id=None, position_scope="open",
        security_key=[], refresh_policy="stale", mode="api_then_ai", wait_timeout=10, poll_interval=1) | overrides))


def job(status="completed", **overrides):
    return dict(request_id="qa-job", status=status, code="research_partial", data_types=["risk_inputs"],
        position_scope="all", security_keys=["BBDC|NYSE|USD"], refresh_policy="refresh_existing", risk_mode="ai",
        counts={"model_requests":3,"rest_requests":4,"web_requests":1},
        progress={"stage":"completed","completed":1,"total":1},
        risk_inputs={"outcomes":[{"security_key":"BBDC|NYSE|USD"}]}) | overrides


def transport(responses, trace):
    def handle(request):
        trace.append({"method":request.method,"path":request.url.path,"query":dict(request.url.params),
            "body":json.loads(request.content) if request.content and request.content != b"null" else None})
        method, path, result = responses.pop(0)
        assert (request.method, request.url.path) == (method, path), trace[-1]
        return result(request) if callable(result) else httpx.Response(200, json=result)
    return httpx.MockTransport(handle)


def test_one_start_polls_and_reloads_nested_diagnostics_and_saved_evidence(runner):
    trace = []
    leaf = {"branch":"risk_ai","request_id":"qa-ai"}
    responses = [
        ("POST",runner.PREFIX+"/ai",job("queued")),
        ("GET",runner.PREFIX+"/ai/qa-job",job("running")),
        ("GET",runner.PREFIX+"/ai/qa-job",job()),
        ("GET",runner.PREFIX+"/ai/qa-job/diagnostics",{"request_id":"qa-job","children":[
            {"branch":"risk","request_id":"qa-wrapper","children":[leaf]}, leaf,
            {"branch":"credit","request_id":"qa-credit"}]}),
        ("GET","/api/securities/risk-inputs/research/ai/qa-ai/diagnostics",{"request_id":"qa-ai","events":[]}),
        ("GET","/api/securities/risk-inputs",{"parameters":{"country_currency":"USD"}}),
    ]
    with httpx.Client(base_url="https://example.test", transport=transport(responses, trace)) as client:
        result = runner.run(client, options(security_key=["BBDC|NYSE|USD"]), sleep=lambda _: None)
    assert not responses and sum(row["method"] == "POST" for row in trace) == 1
    assert trace[0]["body"] == {"data_types":["risk_inputs"],"position_scope":"open","security_keys":["BBDC|NYSE|USD"],
                               "refresh_policy":"stale","risk_mode":"api_then_ai"}
    assert trace[-1]["query"] == {"symbol":"BBDC","stock_market":"NYSE","currency":"USD"}
    assert result["saved_risk_inputs"][0]["parameters"]["country_currency"] == "USD"
    assert result["child_diagnostics"] == [{"request_id":"qa-ai","events":[]}]


def test_observe_failed_request_never_restarts(runner):
    trace = []
    responses = [("GET",runner.PREFIX+"/ai/qa-job",job("failed")),
        ("GET",runner.PREFIX+"/ai/qa-job/diagnostics",{"request_id":"qa-job"}),
        ("GET","/api/securities/risk-inputs",{"parameters":{}})]
    with httpx.Client(base_url="https://example.test", transport=transport(responses, trace)) as client:
        result = runner.run(client, options(request_id="qa-job"))
    assert not responses and result["status"] == "failed"
    assert all(row["method"] == "GET" for row in trace)


def test_resume_keeps_original_selection_scope_mode_and_freshness(runner):
    trace = []
    responses = [("GET",runner.PREFIX+"/ai/qa-job",job("failed")),
        ("POST",runner.PREFIX+"/ai",job("queued")), ("GET",runner.PREFIX+"/ai/qa-job",job()),
        ("GET",runner.PREFIX+"/ai/qa-job/diagnostics",{}), ("GET","/api/securities/risk-inputs",{})]
    with httpx.Client(base_url="https://example.test", transport=transport(responses, trace)) as client:
        runner.run(client, options(resume_request_id="qa-job",mode="api",refresh_policy="missing",
            security_key=["OTHER|MANUAL|ILS"]), sleep=lambda _: None)
    assert trace[1]["body"] == {"resume_request_id":"qa-job","position_scope":"all","security_keys":["BBDC|NYSE|USD"],
                               "data_types":["risk_inputs"],"refresh_policy":"refresh_existing","risk_mode":"ai"}
    assert not responses and sum(row["method"] == "POST" for row in trace) == 1


def test_observation_timeout_retains_id_without_restart_or_cancellation(runner):
    trace = []
    responses = [("POST",runner.PREFIX+"/ai",job("running"))]
    with httpx.Client(base_url="https://example.test", transport=transport(responses, trace)) as client:
        result = runner.run(client, options(wait_timeout=0), sleep=lambda _: None, monotonic=lambda: 0)
    assert not responses and result["status"] == "pending" and result["request_id"] == "qa-job"
    assert len(trace) == 1


@pytest.mark.parametrize("status,body,expected", [
    (401,{"detail":{"code":"invalid_token","message":"synthetic private secret"}},"invalid_token"),
    (500,{"detail":"synthetic private password=never-print-this"},"rest_request_failed"),
])
def test_error_responses_are_safe_and_never_retried(runner, status, body, expected):
    trace = []
    responses = [("POST",runner.PREFIX+"/ai",lambda _: httpx.Response(status,json=body))]
    with httpx.Client(base_url="https://example.test", transport=transport(responses, trace)) as client:
        with pytest.raises(runner.RunError) as raised:
            runner.run(client, options())
    assert raised.value.code == expected and raised.value.status == status
    assert "private" not in str(raised.value)
    assert len(trace) == 1 and not responses


def test_transport_failure_has_no_hidden_retry_or_exception_message(runner):
    trace = []
    def timeout(request):
        trace.append(request.method)
        raise httpx.ReadTimeout("synthetic private transport detail",request=request)
    with httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(runner.RunError) as raised:
            runner.run(client, options())
    assert raised.value.code == "rest_transport_failed" and "private" not in str(raised.value)
    assert trace == ["POST"]


@pytest.mark.parametrize("previous", [job("completed"),job("failed",data_types=["prices"])])
def test_resume_rejects_completed_or_nonrisk_request(runner, previous):
    with pytest.raises(runner.RunError) as raised:
        runner.frozen_resume(previous)
    assert raised.value.code == "failed_risk_request_required"


def test_token_and_receipt_files_are_private_and_symlink_writes_rejected(runner, tmp_path):
    token = tmp_path / "token"
    token.write_text("qa-synthetic-token")
    token.chmod(0o644)
    with pytest.raises(runner.RunError) as raised:
        runner.credential(token)
    assert raised.value.code == "token_file_must_be_private"
    token.chmod(0o600)
    assert runner.credential(token) == "qa-synthetic-token"
    output = tmp_path / "receipt.json"
    runner.write_receipt(output, {"status":"completed"})
    assert output.stat().st_mode & 0o777 == 0o600
    alias = tmp_path / "alias.json"
    alias.symlink_to(output)
    with pytest.raises(runner.RunError) as raised:
        runner.write_receipt(alias, {"status":"failed"})
    assert raised.value.code == "receipt_symlink_not_allowed"
