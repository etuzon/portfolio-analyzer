"""Independent batch acceptance: synthetic ASGI only; no app.main or storage.

The oracle is a five-model/five-REST whole-click ceiling, useful distinct
candidate coverage, and honest per-security attempted/result reporting.
"""
from copy import deepcopy
import json
from types import SimpleNamespace

from fastapi import FastAPI

from app.llm_assistant import AssistantError, PortfolioAssistant, assistant_settings
from app.security_data_routing import route_security
from app.security_enrichment import CATALOG, EnrichmentJobs, RestError
from app.security_web_research import research_sources
from app.us_market_providers import RequestBudget


class DeferredWorker:
    def __init__(self, **kwargs):
        pass

    def start(self):
        pass


def _decision(key, field="auto"):
    return {"choices": [{"message": {"tool_calls": [{"id": key, "function": {
        "name": "fetch_security_information",
        "arguments": json.dumps({"security_key": key, "field": field}),
    }}]}}]}


def _answer():
    return {"choices": [{"message": {"content": '{"observations":[],"profiles":[]}'}}]}


def _batch(monkeypatch, script, *, enabled=True, source_result=None):
    items = [{"security_key": f"{symbol}|TEST|USD", "symbol": symbol,
              "stock_market": "TEST", "currency": "USD", "asset_class": "EQUITY",
              "missing_fields": ["prices"], "available_fields": []}
             for symbol in ("A", "B", "C")]
    app = FastAPI()

    @app.middleware("http")
    async def synthetic_authenticated_operator(request, call_next):
        request.state.auth_user = {"id": "synthetic-owner", "role": "Operator"}
        return await call_next(request)

    fetched, saved = [], []

    def fetch(candidate, field):
        fetched.append(candidate["security_key"])
        if source_result:
            return source_result(candidate)
        return {"evidence": [{"url": "https://evidence.invalid/" + candidate["symbol"],
                              "text": "synthetic identity only", "retrieved_at": "2026-11-07T00:00:00Z"}],
                "source_status": "evidence_found"}

    def save(outcomes, *_args, **_kwargs):
        saved.extend(deepcopy(outcomes))
        return outcomes

    manager = EnrichmentJobs(app,
        lambda: assistant_settings({"llm": {"enabled": enabled, "provider": "openai",
            "api_key": "synthetic", "model": "synthetic", "base_url": "https://never-called.invalid"}}),
        candidate_reader=lambda: {"items": deepcopy(items), "total_count": 3, "research_available": True},
        security_fetcher=fetch, outcome_reader=lambda: [], outcome_writer=save,
        worker_factory=DeferredWorker)
    app.include_router(manager.router())
    responses = iter(script)

    def model(*_args, **_kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(PortfolioAssistant, "_call_provider", model)
    identifier = manager.start("synthetic-owner", {}, "en")["request_id"]
    manager.run(identifier, {}, "en")
    return SimpleNamespace(result=manager.get(identifier, "synthetic-owner"), fetched=fetched, saved=saved)


def test_model_unavailable_does_not_claim_untouched_candidates_were_unavailable(monkeypatch):
    batch = _batch(monkeypatch, [], enabled=False)
    result = batch.result
    assert result["status"] == "failed" and result["code"] == "ai_disabled"
    assert result["progress"]["completed"] == 0
    assert result["summary"]["unavailable"] == 0
    assert result["summary"]["not_attempted"] == 3
    assert all(item["status"] == "not_attempted" and item["attempted"] is False
               for item in result["outcomes"])


def test_later_model_failure_preserves_completed_security_failure_reason(monkeypatch):
    batch = _batch(monkeypatch, [_decision("A|TEST|USD"), AssistantError("synthetic model outage")])
    assert batch.result["code"] == "ai_unavailable"
    outcomes = {item["symbol"]: item for item in batch.result["outcomes"]}
    assert outcomes["A"]["attempted"] is True
    assert outcomes["A"]["code"] == "evidence_rejected"
    assert outcomes["B"]["status"] == outcomes["C"]["status"] == "not_attempted"


def test_repeated_planner_choice_does_not_starve_an_unseen_candidate(monkeypatch):
    batch = _batch(monkeypatch, [
        _decision("A|TEST|USD"), _decision("A|TEST|USD"),
        _decision("B|TEST|USD"), _decision("C|TEST|USD"), _answer(),
    ])
    assert batch.result["counts"]["model_requests"] <= 5
    assert batch.result["counts"]["rest_requests"] <= 5
    assert batch.fetched == ["A|TEST|USD", "B|TEST|USD", "C|TEST|USD"]


def test_repeated_security_with_changed_field_does_not_spend_another_research_slot(monkeypatch):
    # The application route caches by security, independently of field, so this
    # second choice cannot produce any additional evidence for the model.
    batch = _batch(monkeypatch, [
        _decision("A|TEST|USD"), _decision("A|TEST|USD", "prices"),
        _decision("B|TEST|USD"), _decision("C|TEST|USD"), _answer(),
    ])
    assert batch.result["counts"]["model_requests"] <= 5
    assert batch.result["counts"]["rest_requests"] <= 5
    assert batch.fetched == ["A|TEST|USD", "B|TEST|USD", "C|TEST|USD"]


def test_duplicate_failed_http_attempts_still_spend_the_shared_rest_budget(monkeypatch):
    settings = assistant_settings({"llm": {"enabled": True, "provider": "openai",
        "api_key": "synthetic", "model": "synthetic", "base_url": "https://never-called.invalid",
        "max_rest_calls": 3}})
    catalog = deepcopy(CATALOG)
    responses = iter([_decision("A|TEST|USD")] * 3 + [_answer()])
    monkeypatch.setattr(PortfolioAssistant, "_call_provider", lambda *_args, **_kwargs: next(responses))
    failed_attempts = []

    def fail_http(name, arguments):
        failed_attempts.append(arguments["security_key"])
        raise RestError("provider_unavailable")

    result = PortfolioAssistant(settings, catalog).ask("Synthetic bounded lookup", "en", fail_http,
                                                       cache_read_results=True)
    assert failed_attempts == ["A|TEST|USD"] * 3
    assert result["rest_requests"] == 3 and result["model_requests"] == 4


def test_cached_security_does_not_bypass_validation_of_a_changed_field(monkeypatch):
    settings = assistant_settings({"llm": {"enabled": True, "provider": "openai",
        "api_key": "synthetic", "model": "synthetic", "base_url": "https://never-called.invalid"}})
    responses = iter([_decision("A|TEST|USD"), _decision("A|TEST|USD", "arbitrary_sql"), _answer()])
    model_inputs, calls = [], []

    def model(*_args, **kwargs):
        model_inputs.append(deepcopy(kwargs["messages"]))
        return next(responses)

    monkeypatch.setattr(PortfolioAssistant, "_call_provider", model)

    def read(name, arguments):
        calls.append(deepcopy(arguments))
        return {"synthetic_source_result": True}

    result = PortfolioAssistant(settings, deepcopy(CATALOG)).ask("Synthetic bounded lookup", "en", read,
                                                               cache_read_results=True)
    assert calls == [{"security_key": "A|TEST|USD", "field": "auto"}]
    assert result["rest_requests"] == 1 and result["model_requests"] == 3
    assert "error" in json.loads(model_inputs[-1][-1]["content"])


def test_exhausted_upstream_budget_does_not_count_zero_read_candidates_as_checked(monkeypatch):
    def exhausted(candidate):
        first = candidate["symbol"] == "A"
        return {"evidence": [], "source_status": "request_limit", "code": "request_limit",
                "failure_stage": "request_budget", "diagnostics": {
                    "search_requests": 1 if first else 0, "source_requests": 4 if first else 0}}

    batch = _batch(monkeypatch, [_decision(f"{symbol}|TEST|USD") for symbol in ("A", "B", "C")]
                   + [_answer()], source_result=exhausted)
    assert batch.result["counts"]["rest_requests"] == 5
    assert batch.result["counts"]["model_requests"] == 4
    assert batch.result["summary"]["unavailable"] == 1
    assert batch.result["summary"]["not_attempted"] == 2
    assert batch.result["progress"]["completed"] == 1
    assert batch.result["progress"]["total"] == 3
    for outcome in batch.result["outcomes"][1:]:
        assert outcome["status"] == "not_attempted" and outcome["attempted"] is False
        assert "last_attempted_at" not in outcome


def test_five_shared_upstream_reads_cannot_imply_three_securities_were_researched():
    budget = RequestBudget()
    searches, reads = [], []
    candidate = {"symbol": "A", "stock_market": "TEST", "currency": "USD",
                 "missing_fields": ["prices"]}

    def search(query, _key):
        searches.append(query)
        return [{"url": f"https://source{index}.invalid/A"} for index in range(4)]

    def fetch(url):
        reads.append(url)
        return "A exact identity; price loading"

    first = research_sources(candidate, {"search_provider": "duckduckgo"}, budget,
                             search=search, fetch=fetch)
    assert first["code"] == "request_limit" and budget.used == 5
    second = research_sources({**candidate, "symbol": "B"}, {"search_provider": "duckduckgo"}, budget,
                              search=search, fetch=fetch)
    assert second["code"] == "request_limit"
    assert second["diagnostics"]["search_requests"] == second["diagnostics"]["source_requests"] == 0
    assert len(searches) == 1 and len(reads) == 4


def test_treasury_cusip_absence_from_ai_inventory_is_expected_api_ownership():
    # Raw public identity only; this fixture makes no claim about a live holding
    # or the provider's actual current quote coverage for this exact instrument.
    candidate = {"symbol": "91282CKD2", "stock_market": "BOND", "currency": "USD",
                 "location": "USA", "asset_class": "BOND"}
    route = route_security(candidate, {})
    assert route["owner"] == "api" and route["ai_eligible"] is False
    assert route["provider"] == "treasury_direct"
