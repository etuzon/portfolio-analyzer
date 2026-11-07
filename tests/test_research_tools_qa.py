"""Independent, offline contracts for the explicit application research tools.

Synthetic documents test access and evidence flow, not current market prices.
The in-process authenticated app is a test harness, not a deployed acceptance run.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import io
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest

from app.llm_assistant import AssistantError, PortfolioAssistant, assistant_settings
from app.security_enrichment import EnrichmentJobs, PREFIX, WEB_CATALOG
from app.security_research_tools import ResearchFailure, ResearchSession, public_source_url
from app.us_market_providers import RequestBudget


KEY = "QAEXAMPLE|NASDAQ|USD"
CANDIDATE = {
    "security_key": KEY, "symbol": "QAEXAMPLE", "stock_market": "NASDAQ", "currency": "USD",
    "name": "Synthetic QA Example", "asset_class": "EQUITY", "quote_unit": "currency",
    "price_basis": "last", "missing_fields": ["prices"], "latest_price_date": "2026-11-05",
    "reference": {"listing": "NASDAQ", "quote_unit": "currency"},
}
SOURCE = "https://example.org/qa-security"
HISTORY = "https://example.org/qa-history"


def public_dns(*_args, **_kwargs):
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


def tool(name, **arguments):
    return {"choices": [{"message": {"role": "assistant", "tool_calls": [{
        "id": "qa-call", "function": {"name": name, "arguments": json.dumps({"security_key": KEY, **arguments})},
    }]}}]}


def final():
    return {"choices": [{"message": {"role": "assistant", "content": '{"observations":[],"profiles":[]}'}}]}


def last_result(messages):
    return json.loads(next(message["content"] for message in reversed(messages) if message["role"] == "tool"))


class DeferredWorker:
    def __init__(self, target, args, **_kwargs):
        self.target, self.args = target, args

    def start(self):
        pass

    def run(self):
        self.target(*self.args)


@pytest.fixture
def research_app(monkeypatch):
    app = FastAPI()
    state = SimpleNamespace(http=[], queries=[], reads=[], model=[], saved=[], expired=False,
                            responses=[], source_error=False, zero_operations=False, workers=[])
    users = {"operator": {"id": "qa-owner", "role": "Operator"},
             "other": {"id": "qa-other", "role": "Operator"},
             "viewer": {"id": "qa-viewer", "role": "Viewer"}}

    @app.middleware("http")
    async def authentication(request, call_next):
        state.http.append((request.method, request.url.path, dict(request.headers)))
        owner = users.get(request.headers.get("Authorization", "").removeprefix("Bearer "))
        if owner is None or state.expired:
            return JSONResponse({"detail": "authentication_required"}, 401)
        if request.method == "POST" and request.headers.get("X-CSRF-Token") != "qa-csrf":
            return JSONResponse({"detail": "csrf_required"}, 403)
        request.state.auth_user = owner
        return await call_next(request)

    def search(query, _settings):
        state.queries.append(query)
        return [{"title": "Synthetic listing", "url": SOURCE, "snippet": "Not fetched; not evidence"}]

    def fetch(url, _settings):
        state.reads.append(url)
        if state.source_error:
            raise ResearchFailure("source_read_failed", "Synthetic source failure")
        return {"url": url, "text": "Synthetic QA Example QAEXAMPLE NASDAQ. No price asserted.",
                "links": [{"url": HISTORY, "title": "Price history"}] if url == SOURCE else [],
                "structured_data": [{"@type": "Corporation", "tickerSymbol": "QAEXAMPLE"}]}

    session = ResearchSession({}, RequestBudget(limit=5, timeout_seconds=40), search=search, fetch=fetch, resolver=public_dns)

    def research(candidate, action, arguments):
        if state.zero_operations:
            return {"evidence": [], "source_status": "request_limit",
                    "diagnostics": {"search_requests": 0, "source_requests": 0}}
        try:
            result = getattr(session, action)(candidate, **arguments)
            return {**result, "evidence": session.evidence(candidate),
                    "source_status": "sources_found" if action == "search" else "evidence_found",
                    "diagnostics": dict(session.diagnostics)}
        except ResearchFailure as exc:
            return {"evidence": session.evidence(candidate), "source_status": exc.code,
                    "diagnostics": dict(session.diagnostics)}

    def writer(outcomes, user_id, request_id, **kwargs):
        state.saved.append({"outcomes": deepcopy(outcomes), "owner": user_id, "request_id": request_id, **deepcopy(kwargs)})
        return outcomes

    def worker_factory(**kwargs):
        worker = DeferredWorker(**kwargs)
        state.workers.append(worker)
        return worker

    settings = assistant_settings({"llm": {"enabled": True, "provider": "openai", "base_url": "https://never-called.invalid",
                                          "api_key": "synthetic-qa-api-key", "model": "qa-fixture"}})
    manager = EnrichmentJobs(app, lambda: settings,
        candidate_reader=lambda: {"items": [deepcopy(CANDIDATE)], "total_count": 1, "research_available": True},
        security_fetcher=lambda *_args: pytest.fail("Explicit research must not call legacy black-box fetching"),
        research_tool_fetcher=research, outcome_reader=lambda: [], outcome_writer=writer, worker_factory=worker_factory)
    app.include_router(manager.router())

    def provider(_self, *, messages, tools):
        state.model.append({"messages": deepcopy(messages), "tools": deepcopy(tools)})
        response = state.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response(messages) if callable(response) else response

    monkeypatch.setattr(PortfolioAssistant, "_call_provider", provider)
    return SimpleNamespace(client=TestClient(app), manager=manager, state=state, session=session,
                           headers={"Authorization": "Bearer operator", "X-CSRF-Token": "qa-csrf"})


def run_job(env):
    started = env.client.post(PREFIX + "/ai", headers=env.headers, json={})
    assert started.status_code == 202, started.text
    identifier = started.json()["request_id"]
    env.state.workers[-1].run()
    # Read directly with the ordinary owner method so expiry does not mask the result.
    return env.manager.get(identifier, "qa-owner")


def worker_http(state):
    return [entry for entry in state.http if entry[1].endswith(("/candidates", "/finalize")) or "/web/" in entry[1]]


def test_explicit_search_read_follow_uses_three_shared_research_slots(research_app):
    env = research_app
    def read(messages):
        result = last_result(messages)
        assert result["discovery_only"] is True and result["evidence"] == []
        return tool("read_security_source", source_id=result["sources"][0]["source_id"])
    def follow(messages):
        result = last_result(messages)
        assert result["structured_data"][0]["tickerSymbol"] == "QAEXAMPLE"
        return tool("follow_security_source", source_id=result["source_id"], link_id=result["links"][0]["link_id"])
    env.state.responses = [tool("search_security_sources", query="QAEXAMPLE exact NASDAQ listing"), read, follow, final()]
    result = run_job(env)
    assert result["counts"]["rest_requests"] == len(worker_http(env.state)) == 5
    assert result["counts"]["model_requests"] == len(env.state.model) == 4
    assert env.state.queries == ["QAEXAMPLE exact NASDAQ listing"]
    assert env.state.reads == [SOURCE, HISTORY]
    assert {entry["url"] for entry in env.state.saved[0]["evidence_by_key"][KEY]} == {SOURCE, HISTORY}
    assert result["summary"]["updated"] == result["summary"]["partial"] == 0
    assert result["portfolio_refresh_required"] is False
    assert env.state.model[-1]["tools"] == []
    for call in env.state.model:
        prompt = json.dumps(call["messages"], ensure_ascii=False)
        assert all(text in prompt for text in ("NASDAQ", "currency", "2026-11-05", "untrusted"))
        assert "qa-csrf" not in prompt and "synthetic-qa-api-key" not in prompt
    assert all(entry[2].get("authorization") == "Bearer operator" for entry in worker_http(env.state))


def test_query_refinement_is_not_cached_by_security_alone(research_app):
    env = research_app
    env.state.responses = [tool("search_security_sources", query="QAEXAMPLE identity"),
                           tool("search_security_sources", query="QAEXAMPLE NASDAQ quote convention"),
                           lambda messages: tool("read_security_source", source_id=last_result(messages)["sources"][0]["source_id"]), final()]
    result = run_job(env)
    assert env.state.queries == ["QAEXAMPLE identity", "QAEXAMPLE NASDAQ quote convention"]
    assert env.state.reads == [SOURCE]
    assert result["counts"]["rest_requests"] == len(worker_http(env.state)) == 5


def test_identical_read_choice_reuses_evidence_without_extra_rest_or_source_attempt(research_app):
    env = research_app
    search_call = tool("search_security_sources", query="QAEXAMPLE identity")
    env.state.responses = [search_call, deepcopy(search_call),
        lambda messages: tool("read_security_source", source_id=last_result(messages)["sources"][0]["source_id"]), final()]
    result = run_job(env)
    assert env.state.queries == ["QAEXAMPLE identity"]
    assert env.state.reads == [SOURCE]
    assert result["counts"]["rest_requests"] == len(worker_http(env.state)) == 4
    assert result["counts"]["model_requests"] == 4


def test_failed_unknown_source_attempts_consume_rest_budget_without_fetching(research_app):
    env = research_app
    env.state.responses = [tool("read_security_source", source_id="invented-" + str(index)) for index in range(3)] + [final()]
    result = run_job(env)
    assert result["counts"]["rest_requests"] == len(worker_http(env.state)) == 5
    assert result["counts"]["model_requests"] == len(env.state.model) == 4
    assert env.state.queries == env.state.reads == []
    assert not env.state.saved[0]["evidence_by_key"]
    assert result["summary"]["updated"] == 0


def test_failed_provider_invocation_is_counted_and_does_not_fetch_sources(research_app):
    env = research_app
    env.state.responses = [AssistantError("Synthetic unavailable provider")]
    result = run_job(env)
    assert result["counts"]["model_requests"] == len(env.state.model) == 1
    assert result["counts"]["rest_requests"] == len(worker_http(env.state)) == 2
    assert result["status"] == "failed" and env.state.reads == []


def test_failed_source_read_consumes_attempt_and_never_yields_saved_fact(research_app):
    env = research_app
    env.state.source_error = True
    env.state.responses = [tool("search_security_sources", query="QAEXAMPLE identity"),
        lambda messages: tool("read_security_source", source_id=last_result(messages)["sources"][0]["source_id"]), final()]
    result = run_job(env)
    assert env.state.reads == [SOURCE]
    assert env.session.budget.used == 2
    assert env.session.diagnostics["read_failures"] == 1
    assert result["counts"]["rest_requests"] == len(worker_http(env.state)) == 4
    assert not env.state.saved[0]["evidence_by_key"]
    assert result["summary"]["updated"] == 0


def test_authentication_expiry_aborts_further_model_and_save_work(research_app):
    env = research_app
    def expired_read(messages):
        source_id = last_result(messages)["sources"][0]["source_id"]
        env.state.expired = True
        return tool("read_security_source", source_id=source_id)
    env.state.responses = [tool("search_security_sources", query="QAEXAMPLE identity"), expired_read, final()]
    result = run_job(env)
    assert result["status"] == "failed" and result["code"] == "authentication_expired"
    assert result["counts"]["rest_requests"] == len(worker_http(env.state)) == 4
    assert result["counts"]["model_requests"] == len(env.state.model) == 2
    assert env.state.reads == env.state.saved == []


def test_model_cannot_expand_inventory_to_unselected_security(research_app):
    env = research_app
    env.state.responses = [tool("search_security_sources", security_key="OTHER|NASDAQ|USD", query="OTHER listing")
                           for _ in range(3)] + [final()]
    result = run_job(env)
    assert result["counts"]["rest_requests"] == len(worker_http(env.state)) == 2
    assert result["counts"]["model_requests"] == len(env.state.model) == 4
    assert env.state.queries == env.state.reads == []
    assert not env.state.saved[0]["evidence_by_key"]


def test_zero_source_operations_leave_candidate_unattempted(research_app):
    env = research_app
    env.state.zero_operations = True
    env.state.responses = [tool("search_security_sources", query="QAEXAMPLE identity"), final()]
    result = run_job(env)
    assert result["summary"]["not_attempted"] == 1
    assert result["outcomes"][0]["attempted"] is False
    assert "last_attempted_at" not in result["outcomes"][0]
    assert result["progress"]["completed"] == 0
    assert env.state.queries == env.state.reads == []


def test_search_discovery_alone_never_enters_savable_evidence(research_app):
    env = research_app
    env.state.responses = [tool("search_security_sources", query="QAEXAMPLE identity"), final()]
    result = run_job(env)
    assert env.state.saved[0]["evidence_by_key"] == {}
    assert result["summary"]["updated"] == 0 and result["portfolio_refresh_required"] is False
    assert env.state.reads == []


def test_research_routes_require_job_owner_role_and_running_state(research_app):
    env = research_app
    started = env.client.post(PREFIX + "/ai", headers=env.headers).json()
    identifier = started["request_id"]
    params = {"request_id": identifier, "security_key": KEY, "query": "QAEXAMPLE identity"}
    assert env.client.get(PREFIX + "/web/search", params=params).status_code == 401
    assert env.client.get(PREFIX + "/web/search", params=params, headers={"Authorization": "Bearer viewer"}).status_code == 403
    assert env.client.get(PREFIX + "/web/search", params=params, headers={"Authorization": "Bearer other"}).status_code == 404
    assert env.client.get(PREFIX + "/web/search", params=params, headers=env.headers).status_code == 422
    assert env.state.queries == []
    env.state.responses = [final()]
    env.state.workers[-1].run()
    assert env.client.get(PREFIX + "/web/search", params=params, headers=env.headers).status_code == 422
    assert env.state.queries == []


@pytest.mark.parametrize("arguments", [
    {"source_id": "https://example.org/arbitrary"},
    {"source_id": "invented", "url": "https://127.0.0.1/private"},
])
def test_model_cannot_replace_source_capabilities_with_arbitrary_urls(research_app, arguments):
    env = research_app
    env.state.responses = [tool("read_security_source", **arguments), final()]
    result = run_job(env)
    assert env.state.reads == [] and result["summary"]["updated"] == 0
    assert not env.state.saved[0]["evidence_by_key"]


@pytest.mark.parametrize("url", [
    "http://example.org/", "https://127.0.0.1/", "https://169.254.169.254/",
    "https://[::1]/", "https://localhost/", "https://private.internal/", "file:///etc/passwd",
    "javascript:alert(1)", "https://user:password@example.org/", "https://example.org:8443/",
])
def test_source_url_gate_rejects_private_or_non_https_destinations_without_network(url):
    with pytest.raises(ResearchFailure):
        public_source_url(url, resolver=public_dns)


def test_source_capabilities_are_bound_to_security_and_session():
    reads = []
    session = ResearchSession({}, RequestBudget(),
        search=lambda *_args: [{"url": SOURCE}], fetch=lambda url, _settings: reads.append(url), resolver=public_dns)
    source_id = session.search(CANDIDATE, "QAEXAMPLE identity")["sources"][0]["source_id"]
    different = {**CANDIDATE, "security_key": "OTHER|NASDAQ|USD"}
    with pytest.raises(ResearchFailure):
        session.read(different, source_id)
    second = ResearchSession({}, RequestBudget(), fetch=lambda *_args: pytest.fail("Unknown source must not fetch"), resolver=public_dns)
    with pytest.raises(ResearchFailure):
        second.read(CANDIDATE, source_id)
    with pytest.raises(ResearchFailure):
        session.follow(CANDIDATE, source_id, "invented-link")
    assert reads == [] and session.evidence(CANDIDATE) == []


def test_private_dns_or_reader_final_destination_never_becomes_evidence():
    for private_dns, final_url in ((True, SOURCE), (False, "https://127.0.0.1/private")):
        reads = []
        def resolver(*_args, **_kwargs):
            return [(2, 1, 6, "", ("127.0.0.1" if private_dns else "93.184.216.34", 443))]
        def fetch(url, _settings):
            reads.append(url)
            return {"url": final_url, "text": "Synthetic source text", "links": []}
        budget = RequestBudget()
        session = ResearchSession({}, budget, search=lambda *_args: [{"url": SOURCE}], fetch=fetch, resolver=resolver)
        source_id = session.search(CANDIDATE, "QAEXAMPLE identity")["sources"][0]["source_id"]
        with pytest.raises(ResearchFailure):
            session.read(CANDIDATE, source_id)
        assert reads == ([] if private_dns else [SOURCE])
        assert budget.used == 2 and session.evidence(CANDIDATE) == []


def test_catalog_exposes_only_fixed_rest_read_capabilities():
    assert set(WEB_CATALOG) == {"search_security_sources", "read_security_source", "follow_security_source"}
    for entry in WEB_CATALOG.values():
        assert entry["path"].startswith(PREFIX + "/web/")
        assert entry.get("method", "GET") == "GET"
        assert not {"url", "sql", "path", "command", "headers", "cookies"}.intersection(entry["parameters"]["properties"])


@pytest.mark.parametrize("conflict", ["USD", "Adjusted", "wrong_identity"])
def test_known_provider_rejected_quote_card_cannot_escape_via_legacy_excerpt(conflict):
    """The full validator must preserve the provider adapter's rejection.

    A plausible isolated line after the quote card cannot override the card's
    explicit currency/basis or the provider page's different primary security.
    The numeric amount here is synthetic and makes no current-market claim.
    """
    from app.security_web_research import validate_proposals
    day = date.today()
    key = "1101534|TASE|ILS"
    candidate = {"security_key": key, "symbol": "1101534", "stock_market": "TASE", "currency": "ILS",
                 "asset_class": "EQUITY", "location": "Israel", "quote_unit": "agorot", "missing_fields": ["prices"]}
    excerpt = "1101534 TASE ILS Last 123.45 agorot on " + day.isoformat()
    header_id = "9999999" if conflict == "wrong_identity" else "1101534"
    marker = "" if conflict == "wrong_identity" else conflict
    text = ("## חברה לדוגמה נתונים עיקריים\n* " + header_id + "\nמניה רגילה\n" + marker
            + "\nשער אחרון (באגורות) **123.45**\nנכון ל- " + day.strftime("%d/%m/%Y")
            + "\n## שווי שוק\n" + "Synthetic background without quote claims. " * 5 + "\n" + excerpt)
    source = {"url": "https://market.tase.co.il/he/market_data/security/1101534/major_data", "text": text,
              "retrieved_at": datetime.now(timezone.utc).isoformat()}
    item = {"security_key": key, "price_input": 123.45, "price_date": day.isoformat(), "currency": "ILS",
            "quote_unit": "agorot", "price_basis": "last", "observed_at": None, "source_url": source["url"],
            "evidence_quote": excerpt}
    result = validate_proposals({"observations": [item], "profiles": []}, {key: candidate}, {key: [source]})
    assert result[key]["observations"] == []
    assert result[key]["rejected"] is True


@pytest.mark.parametrize("field_aliases", [{}, {"exchange": "stockMarket", "currency": "currencyCode"}])
@pytest.mark.parametrize("conflict", [{"currency": "EUR"}, {"adjusted": True}, {"symbol": "OTHER"}])
def test_rejected_structured_quote_contract_cannot_escape_via_legacy_excerpt(conflict, field_aliases):
    from app.security_web_research import validate_proposals
    day = date.today().isoformat()
    excerpt = "QAEXAMPLE NASDAQ USD Last 123.45 on " + day
    quote_record = {"symbol": "QAEXAMPLE", "exchange": "NASDAQ", "currency": "USD", "quote_unit": "currency",
                    "price_date": day, "price_basis": "last", "last": 123.45, **conflict}
    quote_record = {field_aliases.get(key, key): value for key, value in quote_record.items()}
    source = {"url": SOURCE, "text": json.dumps(quote_record) + "\n" + "Synthetic background. " * 8 + "\n" + excerpt,
              "structured_data": [quote_record], "retrieved_at": datetime.now(timezone.utc).isoformat()}
    item = {"security_key": KEY, "price_input": 123.45, "price_date": day, "currency": "USD", "quote_unit": "currency",
            "price_basis": "last", "observed_at": None, "source_url": SOURCE, "evidence_quote": excerpt}
    result = validate_proposals({"observations": [item], "profiles": []}, {KEY: CANDIDATE}, {KEY: [source]})
    assert result[KEY]["observations"] == []
    assert result[KEY]["rejected"] is True


def tase_candidate(symbol="1101534", **fields):
    return {**CANDIDATE, "security_key": symbol + "|TASE|ILS", "symbol": symbol,
            "stock_market": "TASE", "currency": "ILS", "quote_unit": "agorot", **fields}


def test_official_hint_registers_no_facts_without_network_or_budget_consumption():
    def forbidden(*_args, **_kwargs):
        pytest.fail("Discovery hints must not perform DNS, search or source HTTP")
    budget = RequestBudget()
    session = ResearchSession({}, budget, search=forbidden, fetch=forbidden, resolver=forbidden)
    candidate = tase_candidate("01101534")
    hint, = session.discover(candidate)
    assert hint["url"] == "https://market.tase.co.il/he/market_data/security/1101534/major_data"
    assert hint["discovery_only"] is True
    assert hint["source_id"].startswith("source-")
    assert session.discover(candidate) == [hint]
    assert session.evidence(candidate) == [] and budget.used == 0
    assert session.diagnostics == {"search_requests": 0, "source_requests": 0, "read_failures": 0}


@pytest.mark.parametrize("changed", [
    {"stock_market": "NASDAQ"}, {"stock_market": "PRIVATE"}, {"asset_class": "PRIVATE_STOCK"},
    {"asset_class": "FUND"}, {"asset_class": "BOND"}, {"asset_class": "EMPLOYEE_STOCK_OPTION"},
    {"symbol": "00000"}, {"symbol": "1234"}, {"symbol": "1101534/../../private"},
    {"symbol": "https://127.0.0.1/"},
])
def test_unsupported_instruments_and_identifier_injection_produce_no_official_hint(changed):
    session = ResearchSession({}, RequestBudget(), resolver=lambda *_args, **_kwargs: pytest.fail("No DNS in discover"))
    assert session.discover(tase_candidate(**changed)) == []
    assert session.budget.used == 0


def test_official_hint_id_requires_same_session_security_and_real_read():
    reads = []
    candidate = tase_candidate()
    session = ResearchSession({}, RequestBudget(), resolver=public_dns,
        fetch=lambda url, _settings: reads.append(url) or {"url": url, "text": "Synthetic fetched source without price claims"})
    hint, = session.discover(candidate)
    other_session = ResearchSession({}, RequestBudget(), resolver=public_dns,
        fetch=lambda *_args: pytest.fail("Another job cannot read a hint capability"))
    with pytest.raises(ResearchFailure):
        other_session.read(candidate, hint["source_id"])
    with pytest.raises(ResearchFailure):
        session.read(tase_candidate("1234567"), hint["source_id"])
    assert session.evidence(candidate) == [] and reads == []
    evidence = session.read(candidate, hint["source_id"])
    assert reads == [hint["url"]] and session.budget.used == 1
    assert session.evidence(candidate) == [evidence]
    assert evidence["text"] == "Synthetic fetched source without price claims"


def test_candidate_rest_supplies_only_three_opaque_hints_without_extra_operations(research_app):
    env = research_app
    candidates = [tase_candidate(str(1101534 + index)) for index in range(4)]
    hint_calls = []
    def hints(candidate):
        hint_calls.append(deepcopy(candidate))
        return env.session.discover(candidate)
    env.manager._source_hint_reader = hints
    env.manager._candidate_reader = lambda: {"items": deepcopy(candidates), "total_count": 4, "research_available": True}
    env.state.responses = [final()]
    result = run_job(env)
    assert [entry["security_key"] for entry in hint_calls] == [entry["security_key"] for entry in candidates[:3]]
    assert all(entry["_request_id"] == result["request_id"] for entry in hint_calls)
    assert result["counts"]["rest_requests"] == len(worker_http(env.state)) == 2
    assert result["counts"]["model_requests"] == len(env.state.model) == 1
    user = next(message for message in env.state.model[0]["messages"] if message["role"] == "user")
    assert user["content"].count('"source_hints"') == 3
    supplied = json.loads(user["content"].split("Candidates: ", 1)[1])
    assert all(len(item["source_hints"]) == 1 and item["source_hints"][0]["discovery_only"] is True
               for item in supplied)
    assert all(item["search_hints"] and all(hint["discovery_only"] is True for hint in item["search_hints"])
               for item in supplied)
    assert env.state.saved[0]["evidence_by_key"] == {}
    assert env.session.budget.used == 0 and env.state.reads == env.state.queries == []
    assert result["summary"]["updated"] == 0


@pytest.mark.parametrize("excluded", [
    {"quantity": 0}, {"stock_market": "PRIVATE"}, {"asset_class": "PRIVATE_STOCK"},
    {"asset_class": "EMPLOYEE_STOCK_OPTION"}, {"asset_class": "STOCK_OPTION"},
])
def test_main_hint_callback_rechecks_closed_and_private_holdings_without_external_calls(monkeypatch, excluded):
    from app import main
    from app import security_research_tools
    candidate = {**tase_candidate(), "quantity": 4, **excluded}
    monkeypatch.setattr(main, "enriched_local_holdings", lambda **_kwargs: [{"holding": deepcopy(candidate)}])
    monkeypatch.setattr(main, "to_dict", lambda value: value)
    monkeypatch.setattr(main, "_enrichment_outcomes", lambda: [])
    monkeypatch.setattr(main, "_security_api_route", lambda *_args: pytest.fail("Excluded holdings must not reach API routing"))
    monkeypatch.setattr(security_research_tools, "ResearchSession", lambda *_args: pytest.fail("Excluded holdings must not create sessions"))
    result = main._enrichment_research_tool({**candidate, "_request_id": "synthetic-hint-job"}, "discover", {})
    assert result == {"evidence": [], "source_status": "not_open"}


def test_main_hint_callback_rechecks_api_ownership_before_session_creation(monkeypatch):
    from app import main
    from app import security_research_tools
    candidate = tase_candidate()
    monkeypatch.setattr(main, "_enrichment_candidates", lambda **_kwargs: {"items": [candidate]})
    monkeypatch.setattr(main, "_security_api_route", lambda *_args: {"owner": "api"})
    monkeypatch.setattr(security_research_tools, "ResearchSession", lambda *_args: pytest.fail("API-owned holdings cannot receive AI source hints"))
    result = main._enrichment_research_tool({**candidate, "_request_id": "synthetic-api-owned"}, "discover", {})
    assert result == {"evidence": [], "source_status": "api_managed"}


def raw_record_selection(*, age_days=0):
    from app.security_source_context import context_records
    day = (datetime.now(timezone.utc).date() - timedelta(days=age_days)).isoformat()
    quote = {"symbol": "QAEXAMPLE", "exchange": "NASDAQ", "currency": "USD", "quote_unit": "currency",
             "price_date": day, "price_basis": "last", "last": 123.45}
    source = {"url": SOURCE, "source_id": "source-current-job", "text": json.dumps(quote),
              "structured_data": [quote], "retrieved_at": datetime.now(timezone.utc).isoformat()}
    record, = context_records(source, CANDIDATE)
    choice = {"security_key": KEY, "source_id": source["source_id"], "record_id": record["record_id"]}
    return source, record, choice


def test_record_selection_recomputes_source_values_and_returns_valid_price_observation():
    from app.security_prices import PriceObservation
    from app.security_web_research import validate_proposals
    source, record, choice = raw_record_selection()
    result = validate_proposals({"records": [choice, deepcopy(choice)]}, {KEY: CANDIDATE}, {KEY: [source]})
    accepted, = result[KEY]["observations"]
    observation = PriceObservation.model_validate({key: value for key, value in accepted.items() if not key.startswith("_")})
    assert observation.price_input == 123.45
    assert observation.currency == "USD" and observation.quote_unit == "currency"
    assert observation.price_basis == "last" and observation.observed_at is None
    assert observation.price_date == source["structured_data"][0]["price_date"]
    assert observation.evidence_quote == '"last": 123.45'
    assert accepted["_source_context"]["record_id"] == record["record_id"]
    assert result[KEY]["rejected"] is False


@pytest.mark.parametrize("changed", [
    {"source_id": "source-previous-job"}, {"record_id": "invented-record"},
    {"price_input": 999999}, {"source_id": []}, {"security_key": {}},
])
def test_record_selection_cannot_supply_old_unknown_or_model_modified_values(changed):
    from app.security_web_research import validate_proposals
    source, _record, choice = raw_record_selection()
    result = validate_proposals({"records": [{**choice, **changed}]}, {KEY: CANDIDATE}, {KEY: [source]})
    assert not any(entry["observations"] or entry["profiles"] for entry in result.values())


def test_record_selection_cannot_reuse_record_from_another_source_or_security():
    from app.security_web_research import validate_proposals
    source, _record, choice = raw_record_selection()
    other_source = {**source, "url": "https://example.org/other-source", "source_id": "source-other"}
    selected_other = {**choice, "source_id": other_source["source_id"]}
    result = validate_proposals({"records": [selected_other]}, {KEY: CANDIDATE}, {KEY: [other_source]})
    assert result[KEY]["observations"] == [] and result[KEY]["rejected"] is True
    other_key = "OTHER|NASDAQ|USD"
    other_candidate = {**CANDIDATE, "symbol": "OTHER", "security_key": other_key}
    result = validate_proposals({"records": [{**choice, "security_key": other_key}]},
                                {other_key: other_candidate}, {other_key: [source]})
    assert result[other_key]["observations"] == [] and result[other_key]["rejected"] is True


@pytest.mark.parametrize("changed", [{"currency": "EUR"}, {"adjusted": True}, {"symbol": "OTHER"}, {"last": 999}])
def test_record_selection_rejects_forged_cached_context_after_fetched_record_changes(changed):
    from app.security_web_research import validate_proposals
    source, record, choice = raw_record_selection()
    raw = {**source["structured_data"][0], **changed}
    source.update(text=json.dumps(raw), structured_data=[raw], context_records=[record])
    result = validate_proposals({"records": [choice]}, {KEY: CANDIDATE}, {KEY: [source]})
    assert result[KEY]["observations"] == [] and result[KEY]["rejected"] is True


@pytest.mark.parametrize("age_days,missing", [(8, ["prices"]), (0, ["profile"])])
def test_record_selection_obeys_observation_staleness_and_current_missing_fields(age_days, missing):
    from app.security_web_research import validate_proposals
    source, _record, choice = raw_record_selection(age_days=age_days)
    result = validate_proposals({"records": [choice]}, {KEY: {**CANDIDATE, "missing_fields": missing}}, {KEY: [source]})
    assert result[KEY]["observations"] == [] and result[KEY]["rejected"] is True


@pytest.mark.parametrize("proposal,valid", [
    ('```json\n{"records": []}\n```', True), ('{"records": []}', True),
    ('Before\n```json\n{"records": []}\n```', False),
    ('```json\n{"records": []}\n```\nAfter', False), ('{"records": [], "execute_sql": "anything"}', False),
])
def test_proposal_parser_accepts_whole_json_fence_only_without_unsupported_keys(proposal, valid):
    from app.security_web_research import parse_research_proposal
    assert (parse_research_proposal(proposal) == {"records": []}) is valid


@pytest.mark.parametrize("provider", ["local_codex", "local_claude"])
@pytest.mark.parametrize("research_mode", [False, True])
def test_local_provider_http_forwards_research_purpose_only_in_research_mode(monkeypatch, provider, research_mode):
    import httpx
    payloads = []
    class Client:
        def __init__(self, **_kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            pass
        def post(self, path, *, json):
            assert path == "/completion"
            payloads.append(deepcopy(json))
            return httpx.Response(200, json=final())
    monkeypatch.setattr(httpx, "Client", Client)
    settings = assistant_settings({"llm": {"provider": provider, "enabled": True}})
    settings["research_mode"] = research_mode
    assistant = PortfolioAssistant(settings, WEB_CATALOG)
    response = assistant._call_provider(messages=[{"role": "system", "content": "Synthetic policy"}], tools=[])
    assert response == final()
    assert payloads[0]["provider"] == provider
    assert payloads[0].get("purpose") == ("security_research" if research_mode else None)


@pytest.mark.parametrize("provider", ["local_codex", "local_claude"])
def test_bridge_uses_dedicated_research_planner_policy_for_both_backends_without_native_calls(monkeypatch, provider):
    from app import claude_bridge, codex_bridge
    seen, statuses = [], []
    def completion(messages, tools, **options):
        seen.append((messages, tools, options))
        return final()
    monkeypatch.setattr(codex_bridge, "codex_completion", completion)
    monkeypatch.setattr(claude_bridge, "claude_completion", completion)
    payload = {"messages": [{"role": "system", "content": "Synthetic research context"}], "tools": [],
               "provider": provider, "purpose": "security_research", "model": "synthetic-model", "reasoning_effort": "medium"}
    body = json.dumps(payload).encode()
    handler = object.__new__(codex_bridge._Handler)
    handler.path, handler.headers = "/completion", {"Content-Length": str(len(body))}
    handler.rfile, handler.wfile = io.BytesIO(body), io.BytesIO()
    handler.send_response = statuses.append
    handler.send_header = lambda *_args: None
    handler.end_headers = lambda: None
    handler.do_POST()
    assert statuses == [200] and len(seen) == 1
    assert seen[0][2]["policy"] == codex_bridge.SECURITY_RESEARCH_PLANNER_POLICY
    assert "nested research proposal object" in seen[0][2]["policy"]
    assert "never a JSON string" in seen[0][2]["policy"]
    assert "no native tools" in seen[0][2]["policy"]
    assert json.loads(handler.wfile.getvalue()) == final()


@pytest.mark.parametrize("through_reader", [False, True])
def test_rendered_industry_field_stops_before_following_navigation_paragraph(through_reader):
    from app.security_source_context import context_records
    from app.security_web_research import validate_proposals
    candidate = tase_candidate(missing_fields=["profile"])
    industry = "ריאלי - מסחר ושרותים - תקשורת ומדיה"
    text = ("## חברת בדיקה נתונים עיקריים\n\n* 1101534\n\n**מניה רגילה**\n\n"
            "שער אחרון (באגורות) **123.45**\n\nנכון ל- 06/11/2026\n\n"
            "## **ענף בבורסה**\n\n" + industry + "\n\n"
            "[פרטי החברה](https://maya.tase.co.il/he/companies/2066)\n\n###### Chart")
    if through_reader:
        session = ResearchSession({}, RequestBudget(), resolver=public_dns,
            fetch=lambda url, _settings: {"url": url, "text": text, "reader": "jina"})
        hint, = session.discover(candidate)
        source = session.read(candidate, hint["source_id"])
    else:
        source = {"url": "https://market.tase.co.il/he/market_data/security/1101534/major_data",
                  "source_id": "source-rendered-industry", "text": text,
                  "retrieved_at": datetime.now(timezone.utc).isoformat()}
    record, = [entry for entry in context_records(source, candidate) if entry.get("field") == "industry"]
    assert record["value"] == industry
    assert "http" not in record["value"] and "פרטי החברה" not in record["value"]
    choice = {"security_key": candidate["security_key"], "source_id": source["source_id"], "record_id": record["record_id"]}
    result = validate_proposals({"records": [choice]}, {candidate["security_key"]: candidate}, {candidate["security_key"]: [source]})
    profile, = result[candidate["security_key"]]["profiles"]
    assert profile["value"] == industry
    assert result[candidate["security_key"]]["rejected"] is False


def test_final_profile_outcome_uses_current_metadata_after_successful_writes(monkeypatch):
    from app import main
    state = {"name": "QAEXAMPLE", "industry": ""}
    preferences = {}
    def inventory(**_kwargs):
        needs_name, needs_industry = state["name"] == "QAEXAMPLE", not state["industry"]
        return {"items": [{**CANDIDATE, **state, "needs_name": needs_name, "needs_industry": needs_industry,
                            "missing_fields": (["profile"] if needs_name or needs_industry else []) + ["fundamentals"]}]}
    class Store:
        def manual_security(self, *_args):
            return {**CANDIDATE, **state, "location": "US"}
        def save_manual_security(self, payload):
            state["name"] = payload["name"]
        def save_security_industry_override(self, payload):
            state["industry"] = payload["industry"]
        def get_preference(self, key, default):
            return preferences.get(key, default)
        def set_preference(self, key, value):
            preferences[key] = value
    monkeypatch.setattr(main, "local_store", Store())
    monkeypatch.setattr(main, "_enrichment_candidates", inventory)
    candidate = inventory()["items"][0]
    text = "QAEXAMPLE NASDAQ Company name: Synthetic Issuer Industry: Software"
    source = {"url": SOURCE, "text": text, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    proposal = {"profiles": [{"security_key": KEY, "field": field, "value": value, "source_url": SOURCE, "evidence_quote": text}
                             for field, value in (("name", "Synthetic Issuer"), ("industry", "Software"))]}
    result = main._apply_enrichment_proposals(proposal, {KEY: [source]}, {KEY: candidate})[KEY]
    assert state == {"name": "Synthetic Issuer", "industry": "Software"}
    assert result["status"] == "partial" and result["missing_fields"] == ["fundamentals"]
    assert result["name"] == "Synthetic Issuer"
    assert result["needs_name"] is False and result["needs_industry"] is False


def exercise_profile_finalizer(env, monkeypatch, document):
    """Offline helper also usable with a sanitized archived public document."""
    from app import main, security_research_tools
    industry = "ריאלי - מסחר ושרותים - תקשורת ומדיה"
    held = {**tase_candidate(), "quantity": 1, "location": "Israel", "name": "1101534", "industry": ""}
    preferences, writes = {}, []
    key = held["security_key"]
    def inventory(**_kwargs):
        needs_name, needs_industry = held["name"] == held["symbol"], not held["industry"]
        item = {**held, "needs_name": needs_name, "needs_industry": needs_industry, "missing_fields": ["profile"]}
        items = [item] if needs_name or needs_industry else []
        return {"items": items, "total_count": len(items), "research_available": True}
    class Store:
        def manual_security(self, *_args):
            return deepcopy(held)
        def save_manual_security(self, payload):
            held["name"] = payload["name"]
            writes.append(("name", payload["name"]))
        def save_security_industry_override(self, payload):
            held["industry"] = payload["industry"]
            writes.append(("industry", payload["industry"]))
        def get_preference(self, preference, default):
            return deepcopy(preferences.get(preference, default))
        def set_preference(self, preference, value):
            preferences[preference] = deepcopy(value)
    session_class = security_research_tools.ResearchSession
    def offline_session(settings, budget):
        return session_class(settings, budget, resolver=public_dns,
                             fetch=lambda *_args: deepcopy(document),
                             search=lambda *_args: pytest.fail("Official source hint avoids discovery HTTP"))
    monkeypatch.setattr(security_research_tools, "ResearchSession", offline_session)
    monkeypatch.setattr(main, "local_store", Store())
    monkeypatch.setattr(main, "_enrichment_candidates", inventory)
    monkeypatch.setattr(main, "_security_api_route", lambda *_args: {"owner": "ai"})
    monkeypatch.setattr(main, "enriched_local_holdings", lambda **_kwargs: [{"holding": deepcopy(held)}])
    monkeypatch.setattr(main, "to_dict", lambda value: value)
    monkeypatch.setattr(main, "_record_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "clear_portfolio_cache", lambda: None)
    env.manager._candidate_reader = inventory
    env.manager._source_hint_reader = lambda candidate: main._enrichment_research_tool(candidate, "discover", {}).get("sources", [])
    env.manager._research_tool_fetcher = main._enrichment_research_tool
    env.manager._outcome_writer = main._save_enrichment_outcomes
    def read_hint(messages):
        user = next(message["content"] for message in messages if message["role"] == "user")
        candidate, = json.loads(user.split("Candidates: ", 1)[1])
        return tool("read_security_source", security_key=key, source_id=candidate["source_hints"][0]["source_id"])
    def select_profiles(messages):
        source, = last_result(messages)["evidence"]
        profiles = [record for record in source["context_records"] if record["kind"] == "profile"]
        assert {record["field"] for record in profiles} == {"name", "industry"}
        proposal = {"records": [{"security_key": key, "source_id": source["source_id"], "record_id": record["record_id"]}
                                for record in profiles]}
        return {"choices": [{"message": {"role": "assistant", "content": json.dumps(proposal)}}]}
    env.state.responses = [read_hint, select_profiles]
    result = run_job(env)
    assert result["status"] == "completed" and result["failure"] is None
    assert result["summary"]["updated"] == 1 and result["summary"]["unavailable"] == 0
    assert held["industry"] == industry and held["name"] != "1101534"
    assert {field for field, _value in writes} == {"name", "industry"}
    assert len(preferences["security_enrichment_sources_v1"]) == 2
    assert result["outcomes"][0]["evidence_rejected"] is False
    assert result["outcomes"][0]["missing_fields"] == []
    assert preferences["security_enrichment_outcomes_v1"][key]["code"] == "data_found"
    assert result["counts"]["rest_requests"] == len(worker_http(env.state)) == 3
    assert result["counts"]["model_requests"] == len(env.state.model) == 2
    assert all(entry[2].get("authorization") == "Bearer operator" for entry in worker_http(env.state))
    return {"job": result, "saved_name": held["name"], "saved_industry": held["industry"],
            "written_fields": [field for field, _value in writes], "provenance_fields": sorted(preferences["security_enrichment_sources_v1"])}


def test_authenticated_finalizer_saves_rendered_name_and_industry_without_navigation_text(research_app, monkeypatch):
    text = ("## חברת בדיקה נתונים עיקריים\n\n* 1101534\n\n**מניה רגילה**\n\n"
            "## **ענף בבורסה**\n\nריאלי - מסחר ושרותים - תקשורת ומדיה\n\n"
            "[פרטי החברה](https://maya.tase.co.il/he/companies/2066)\n\n###### Chart")
    document = {"url": "https://market.tase.co.il/he/market_data/security/1101534/major_data", "text": text, "reader": "jina"}
    exercise_profile_finalizer(research_app, monkeypatch, document)
