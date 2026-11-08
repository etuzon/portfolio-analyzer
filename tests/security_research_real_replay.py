"""Opt-in live AI/source acceptance replay with synthetic authenticated inventory.

Runs the production EnrichmentJobs REST routes, planner bridge, search, reader and
proposal validator. Default mode uses in-memory inventory/persistence. --main
runs actual application auth, inventory and persistence in an isolated temporary
portfolio with synthetic configuration. Runtime data and private config stay out.

PORTFOLIO_CODEX_SOCKET="$PWD/.runtime/portfolio-codex/bridge.sock" \
  ./.venv/bin/python tests/security_research_real_replay.py [--main] [tase|bond|tva|mixed|us_bonds]
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from app.llm_assistant import assistant_settings
from app.price_agent import price_agent_settings
from app.security_enrichment import EnrichmentJobs, PREFIX
from app.security_research_tools import ResearchSession, WebRequestBudget
from app.security_source_context import context_records
from app.security_web_research import validate_proposals

CASES = {
    "tase": {"security_key": "1101534|TASE|ILS", "symbol": "1101534", "stock_market": "TASE", "currency": "ILS",
             "asset_class": "EQUITY", "quote_unit": "agorot", "name": "Cellcom Israel", "industry": "",
             "missing_fields": ["profile"], "needs_name": False, "needs_industry": True},
    "bond": {"security_key": "121899CH9|MANUAL|USD", "symbol": "121899CH9", "secondary_symbol": "",
             "stock_market": "MANUAL", "currency": "USD", "asset_class": "BOND", "quote_unit": "cents",
             "name": "US_121899CH9", "industry": "", "missing_fields": ["profile"], "needs_name": True, "needs_industry": False},
    "tva": {"security_key": "88059ESH8|MANUAL|USD", "symbol": "88059ESH8", "stock_market": "MANUAL", "currency": "USD",
            "asset_class": "BOND", "quote_unit": "cents", "name": "US_88059ESH8", "industry": "",
            "missing_fields": ["profile"], "needs_name": True, "needs_industry": False},
}


def run(case="tase"):
    candidate = deepcopy(CASES[case])
    socket_path = os.environ.get("PORTFOLIO_CODEX_SOCKET") or str(Path(__file__).resolve().parents[1]/".runtime/portfolio-codex/bridge.sock")
    settings = assistant_settings({"llm": {"enabled": True, "provider": "local_codex", "codex_socket": socket_path,
                                           "model": "gpt-6.1-sol", "reasoning_effort": "medium"}})
    settings.update(max_tool_loops=8, max_rest_calls=8, max_web_calls=8)
    source_settings = price_agent_settings({})
    sessions, saved, verified_facts, trace = {}, [], [], []
    app = FastAPI()
    token, csrf = "synthetic-live-replay-operator", "synthetic-live-replay-csrf"
    @app.middleware("http")
    async def authenticate(request, next_handler):
        if request.headers.get("authorization") != "Bearer " + token:
            return JSONResponse({"detail": "authentication_required"}, 401)
        request.state.auth_user = {"id": "synthetic-live-reviewer", "role": "Operator"}
        if request.method not in {"GET", "HEAD"} and request.headers.get("x-csrf-token") != csrf:
            return JSONResponse({"detail": "forbidden"}, 403)
        return await next_handler(request)
    def session(item):
        return sessions.setdefault(item["_request_id"], ResearchSession(source_settings, WebRequestBudget()))
    def hints(item):
        return session(item).discover(item)
    def research(item, action, args):
        controller = session(item)
        try:
            if action == "search":
                result = controller.search(item, args["query"], provider=args.get("provider", "auto"))
                return {**result, "evidence": [], "source_status": "search_results", "web_requests": controller.budget.used}
            source = (controller.read(item, args["source_id"]) if action == "read" else
                      controller.follow(item, args["source_id"], args["link_id"]))
            source["context_records"] = context_records(source, item)[:30]
            # Same bounded transport contract as the application source route.
            while len(json.dumps(source, ensure_ascii=False)) > 70000 and source.get("links"):
                source["links"].pop()
            return {"evidence": [source], "source_status": "evidence_found", "diagnostics": dict(controller.diagnostics),
                    "web_requests": controller.budget.used}
        except (ValueError, OSError, TimeoutError) as exc:
            return {"evidence": [], "source_status": getattr(exc, "code", "source_read_failed"),
                    "diagnostics": dict(controller.diagnostics), "web_requests": controller.budget.used}
    def finalizer(outcomes, user_id, request_id, *, proposal=None, evidence_by_key=None, candidates=None, **_):
        verified = validate_proposals(proposal, candidates, evidence_by_key or {})
        for outcome in outcomes:
            result = verified.get(outcome["security_key"], {})
            facts = result.get("profiles", []) + result.get("observations", [])
            verified_facts.extend(facts)
            if facts:
                outcome.update(status="updated", code="data_found", available_fields=["profile"], missing_fields=[])
        saved.extend(deepcopy(outcomes))
        return outcomes
    manager = EnrichmentJobs(app, lambda: settings,
        candidate_reader=lambda: {"items": [deepcopy(candidate)], "total_count": 1, "research_available": True,
                                  "configured_search_providers": ["yahoo", "duckduckgo"]},
        security_fetcher=lambda *_: {}, source_hint_reader=hints, research_tool_fetcher=research,
        outcome_reader=lambda: deepcopy(saved), outcome_writer=finalizer,
        event_writer=lambda event, **fields: trace.append({"event": event, **fields}))
    app.include_router(manager.router())
    headers = {"Authorization": "Bearer " + token, "X-CSRF-Token": csrf}
    with TestClient(app) as client:
        assert client.post(PREFIX+"/ai", json={}).status_code == 401
        started = client.post(PREFIX+"/ai", headers=headers, json={})
        started.raise_for_status()
        request_id = started.json()["request_id"]
        deadline = time.monotonic()+300
        while time.monotonic() < deadline:
            result = client.get(PREFIX+"/ai/"+request_id, headers=headers).json()
            if result["status"] not in {"queued", "running"}:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Live replay did not finish within 300 seconds")
    readable = [{"url": row["url"], "retrieved_at": row["retrieved_at"], "reader": row["reader"],
                 "text_length": len(row["text"]), "context_records": len(row.get("context_records", []))}
                for controller in sessions.values() for row in controller.evidence(candidate)]
    output = {"case": case, "fixture": "synthetic inventory and persistence; actual authenticated production REST coordinator, model and Internet",
              "job": result, "verified_facts": verified_facts, "fetched_sources": readable,
              "decisions": [row.get("response") for row in trace if row.get("step") == "model_response"]}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return bool(verified_facts)

def run_main(case="tase"):
    """Actual app auth, inventory, tool wiring, validation and temp persistence."""
    if "app.main" in sys.modules:
        raise RuntimeError("Main replay requires a fresh process for store isolation")
    candidates = ([deepcopy(CASES[key]) for key in ("tase", "bond", "tva")] if case == "mixed" else
                  [deepcopy(CASES[key]) for key in ("bond", "tva")] if case == "us_bonds" else [deepcopy(CASES[case])])
    if case in {"mixed", "us_bonds"}:
        # The third recorded bond remains API-owned, outside the three AI candidates.
        candidates.append({"symbol": "91282CKD2", "secondary_symbol": "", "stock_market": "MANUAL",
                           "currency": "USD", "asset_class": "BOND", "name": "US_91282CKD2"})
    socket_path = os.environ.get("PORTFOLIO_CODEX_SOCKET") or str(Path(__file__).resolve().parents[1]/".runtime/portfolio-codex/bridge.sock")
    with tempfile.TemporaryDirectory(prefix="portfolio-live-app-replay-") as directory:
        # Set both guards before application imports; never read private config.
        os.environ["DATA_DIR"] = directory
        config_path = Path(directory)/"synthetic-config.yaml"
        config_path.write_text(json.dumps({"market_data": {"primary": "none", "fallback": [], "experimental_fallback": [],
            "security_lookup": {"finnhub": {"api_key": "synthetic-unused-provider-key"}}},
            "llm": {"enabled": True, "provider": "local_codex", "codex_socket": socket_path},
            "price_agent": {"provider": "codex", "model": "gpt-6.1-sol", "reasoning_effort": "medium",
                            "max_model_calls": 8, "max_rest_calls": 8, "max_web_calls": 8}}))
        os.environ["CONFIG_PATH"] = str(config_path)
        from app import main
        import logging
        logging.disable(logging.INFO)
        store = main.local_store
        for index, candidate in enumerate(candidates):
            equity = candidate["asset_class"] == "EQUITY"
            account_id = "synthetic-live-" + str(index)
            store.save_account({"id": account_id, "account_id": "Synthetic live acceptance " + str(index), "currency": candidate["currency"],
                "location": "Israel" if equity else "USA", "initial_cash": 0,
                "persons": [{"name": "Synthetic Reviewer", "birth_date": "01/01/1980"}]})
            security = store.save_manual_security({**candidate, "instrument_type": "STOCK" if equity else "BOND",
                                                   "location": "Israel" if equity else "USA", "manual_only": True})
            store.add_transaction({"account_db_id": account_id, "security_id": security["id"],
                "symbol": candidate["symbol"], "stock_market": candidate["stock_market"], "asset_class": candidate["asset_class"],
                "location": security["location"], "currency": candidate["currency"], "action": "BUY", "quantity": 1,
                "price_input": 1, "trade_date": "01/11/2026"})
            if candidate["symbol"] in {"121899CH9", "88059ESH8"}:
                # Synthetic setup mirrors the actual user's cached denied access.
                # No provider call uses the synthetic key above.
                from datetime import datetime, timezone
                main.hub().cache.set_security_snapshot("security_lookup", candidate["symbol"], "security-coverage-v1:bond",
                    {"request": {"identifier": candidate["symbol"]}, "status": "provider_error",
                     "retrieved_at": datetime.now(timezone.utc).isoformat(),
                     "provider_errors": [{"provider": "finnhub", "code": "entitlement_required"}]})
        def ledger():
            fields = ("id", "account_db_id", "action", "symbol", "stock_market", "asset_class", "quantity",
                      "price_input", "price", "currency", "location", "trade_date", "source", "comments", "security_id")
            return {"transactions": [{field: row.get(field) for field in fields} for row in store.list_transactions()],
                    "cash": {account["id"]: store.account_cash_balance(account["id"]) for account in store.list_accounts()},
                    "quantities": {row.holding.symbol: row.holding.quantity for row in store.holdings()}}
        before = ledger()
        inventory = main._ai_enrichment_candidates()
        client = TestClient(main.app, base_url="https://localhost:6443")
        assert client.post(PREFIX+"/ai", json={}).status_code == 401
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        login.raise_for_status()
        session = login.json()
        changed = client.post("/api/auth/change-password", headers={"X-CSRF-Token": session["csrf_token"]},
            json={"current_password": "admin", "new_password": "Synthetic-Live-Replay-2026!", "confirm_password": "Synthetic-Live-Replay-2026!"})
        changed.raise_for_status()
        client.headers["X-CSRF-Token"] = changed.json()["csrf_token"]
        treasury = None
        if case == "us_bonds":
            from datetime import date, timedelta
            params = {"identifier": "91282CKD2", "kind": "bond", "provider": "treasury_direct",
                      "date_from": (date.today()-timedelta(days=7)).isoformat(), "date_to": date.today().isoformat()}
            before_read = store.list_prices()
            response = client.get("/api/security/market-data", params=params)
            response.raise_for_status()
            snapshot = response.json()
            after_read = store.list_prices()
            assert before_read == after_read, "The reference-data GET must not save portfolio prices"
            assert snapshot.get("security", {}).get("cusip") == "91282CKD2", snapshot
            assert snapshot["provider"] == "treasury_direct" and snapshot["provider_requests"] <= 5
            api_candidate = next(item for item in main._automatic_price_inventory() if item["symbol"] == "91282CKD2")
            # The exact application-owned write used by normal API refresh,
            # supplied with the actual authenticated REST observation above.
            saved = main._apply_automatic_security_prices(api_candidate, snapshot)
            assert saved > 0, "A supported Treasury observation must reach normalized local price history"
            reloaded = client.get("/api/security/market-data", params={**params, "cache_only": True})
            reloaded.raise_for_status()
            cached = reloaded.json()
            assert cached["provider_requests"] == 0
            treasury = {"response": snapshot, "cached_reload": cached, "saved_price_observations": saved,
                        "prices_before_reference_read": before_read, "prices_after_reference_read": after_read}
        started = client.post(PREFIX+"/ai", json={})
        started.raise_for_status()
        request_id = started.json()["request_id"]
        deadline = time.monotonic()+300
        while time.monotonic() < deadline:
            status = client.get(PREFIX+"/ai/"+request_id)
            status.raise_for_status()
            result = status.json()
            if result["status"] not in {"queued", "running"}:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Live main replay did not finish within 300 seconds")
        facts = store.get_preference("security_enrichment_sources_v1", {})
        persisted = {"security": store.manual_security(candidates[0]["symbol"], candidates[0]["stock_market"]),
                     "securities": [store.manual_security(item["symbol"], item["stock_market"]) for item in candidates],
                     "industry_overrides": store.list_security_industry_overrides(), "prices": store.list_prices(),
                     "profile_provenance": facts, "saved_outcomes": client.get(PREFIX+"/status").json()}
        job = main.security_enrichment._job(request_id)
        sources = [{"url": source["url"], "text_length": len(source["text"]), "retrieved_at": source["retrieved_at"],
                    "reader": source.get("reader"), "context_records": len(source.get("context_records", []))}
                   for value in job["_evidence_by_key"].values() for source in value["evidence"]]
        after = ledger()
        assert before == after, "Research must not change transactions, quantities or cash"
        portfolio = main._serialized_portfolio_payload(main.enriched_local_holdings(cached_only=True), "synthetic acceptance reload")
        print(json.dumps({"case": case, "mode": "actual main app authenticated REST and persistence, synthetic isolated temp portfolio/config only",
                          "job": result, "persisted": persisted, "fetched_sources": sources,
                          "initial_ai_inventory": inventory, "ledger_before": before, "ledger_after": after,
                          "treasury_api": treasury, "reloaded_portfolio": portfolio,
                          "decisions": [entry.get("response") for entry in job["_trace"] if entry.get("step") == "model_response"]}, ensure_ascii=False, indent=2, default=str))
        client.close()
        if case in {"mixed", "us_bonds"}:
            keys = {item["security_key"] for item in inventory["items"]}
            saved_keys = {key.rsplit("|", 1)[0] for key in facts}
            bonds = {item["holding"]["symbol"] for item in portfolio["items"] if item["holding"]["asset_class"] == "BOND"}
            assert bonds == {"88059ESH8", "91282CKD2", "121899CH9"}
            return keys <= saved_keys and result["summary"]["not_attempted"] == 0
        return bool(facts or persisted["prices"])

if __name__ == "__main__":
    case = next((value for value in sys.argv[1:] if value != "--main"), "tase")
    raise SystemExit(0 if (run_main(case) if "--main" in sys.argv else run(case)) else 1)
