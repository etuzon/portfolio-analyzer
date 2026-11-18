"""Opt-in real HTTPS/auth/model/Internet risk-research acceptance.

Uses an empty temporary portfolio, populated only through authenticated REST.
It never imports application stores or reads private config/runtime data.
Run from the repository or /app in the deployed container. Exactly one parent
research request is started; no automatic retries or request-budget resets.
"""
from __future__ import annotations

import argparse
import importlib.util
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace

import httpx


def execute(output, attempt, runner=None):
    root = Path.cwd()
    socket_path = os.environ.get("PORTFOLIO_CODEX_SOCKET")
    if not socket_path:
        container_socket = Path("/run/portfolio-codex/bridge.sock")
        socket_path = str(container_socket if container_socket.exists() else root / ".runtime/portfolio-codex/bridge.sock")
    if not Path(socket_path).is_socket():
        raise RuntimeError("The configured application AI bridge socket is unavailable")
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    password = "Synthetic-Isolated-Risk-REST-2026!"
    with TemporaryDirectory(prefix="portfolio-risk-real-") as directory:
        temporary = Path(directory)
        config = temporary / "synthetic-config.yaml"
        config.write_text(json.dumps({
            "market_data": {"primary": "none", "fallback": [], "experimental_fallback": []},
            "llm": {"enabled": True, "provider": "local_codex", "codex_socket": socket_path},
            "price_agent": {"provider": "codex", "max_model_calls": 8, "max_rest_calls": 8, "max_web_calls": 8}}))
        environment = {**os.environ, "DATA_DIR": str(temporary / "data"), "CONFIG_PATH": str(config)}
        cert, key = temporary / "cert.pem", temporary / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=localhost", "-keyout", str(key), "-out", str(cert)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
        with (output.parent / f"attempt-{attempt}-server.log").open("w") as logs:
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                        "--port", str(port), "--ssl-keyfile", str(key), "--ssl-certfile", str(cert)],
                                       cwd=root, env=environment, stdout=logs, stderr=subprocess.STDOUT)
            try:
                with httpx.Client(base_url=f"https://127.0.0.1:{port}", verify=False, timeout=30) as client:
                    for _ in range(100):
                        try:
                            if client.get("/api/health").status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        if process.poll() is not None:
                            raise RuntimeError("Isolated application failed to start; inspect the private server log")
                        time.sleep(.1)
                    else:
                        raise RuntimeError("Isolated HTTPS health check timed out")

                    def call(method, path, body=None):
                        response = client.request(method, path, json=body)
                        if response.status_code >= 400:
                            # Synthetic app only. Never include credentials or headers.
                            raise RuntimeError(f"REST {method} {path.split('?')[0]} returned {response.status_code}")
                        return response.json()

                    assert client.get("/api/securities/enrichment/status").status_code == 401
                    login = call("POST", "/api/auth/login", {"username": "admin", "password": "admin"})
                    client.headers["X-CSRF-Token"] = login["csrf_token"]
                    changed = call("POST", "/api/auth/change-password", {"current_password": "admin",
                        "new_password": password, "confirm_password": password})
                    client.headers["X-CSRF-Token"] = changed["csrf_token"]
                    account = call("POST", "/api/local/accounts", {"account_id": "isolated-rest-acceptance",
                        "username": "Isolated REST acceptance", "type": "Investment", "location": "USA",
                        "currency": "USD", "initial_cash": 0,
                        "persons": [{"name": "Synthetic Reviewer", "birth_date": "01/01/1980"}]})
                    security = call("POST", "/api/local/manual-securities", {"symbol": "BBDC", "stock_market": "NYSE",
                        "currency": "USD", "asset_class": "EQUITY", "instrument_type": "STOCK", "location": "USA",
                        "name": "Barings BDC, Inc.", "manual_only": True})
                    call("POST", "/api/local/securities", {"account_db_id": account["id"], "security_id": security["id"],
                        "symbol": "BBDC", "stock_market": "NYSE", "currency": "USD", "asset_class": "EQUITY",
                        "location": "USA", "action": "BUY", "quantity": 1, "price_input": 1,
                        "trade_date": datetime.now(timezone.utc).strftime("%d/%m/%Y"), "allow_manual": True})
                    call("PUT", "/api/settings/api-access", {"mode": "read_write"})
                    credential = call("POST", "/api/auth/token", {"username": "admin", "password": password})
                    client.headers.pop("X-CSRF-Token", None)
                    client.cookies.clear()
                    client.headers["Authorization"] = "Bearer " + credential["access_token"]
                    payload = {"data_types": ["risk_inputs"], "position_scope": "open", "refresh_policy": "stale",
                               "risk_mode": "api_then_ai", "security_keys": ["BBDC|NYSE|USD"]}
                    runner = Path(runner) if runner else root / "scripts/research-risk-inputs.py"
                    if runner.is_file():
                        spec = importlib.util.spec_from_file_location("risk_rest_runner", runner)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        options = SimpleNamespace(request_id=None, resume_request_id=None, position_scope="open",
                            security_key=["BBDC|NYSE|USD"], refresh_policy="stale", mode="api_then_ai", wait_timeout=900, poll_interval=2)
                        observed = module.run(client, options, emit=lambda row: print(json.dumps({"attempt":attempt, **row}), flush=True))
                        job = observed["job"]
                    else:
                        raise RuntimeError("REST runner source is required for the actual replay")
                    identifier = job["request_id"]
                    risk = call("GET", "/api/securities/risk-inputs?symbol=BBDC&stock_market=NYSE&currency=USD")
                    diagnostics = call("GET", "/api/securities/enrichment/ai/" + identifier + "/diagnostics")
                    leaf_diagnostics = []
                    children = list(diagnostics.get("children", []))
                    while children:
                        child = children.pop(0)
                        children.extend(child.get("children", []))
                        if child.get("branch") == "risk_ai":
                            leaf_diagnostics.append(call("GET", "/api/securities/risk-inputs/research/ai/" + child["request_id"] + "/diagnostics"))
                    sources = risk.get("source_evidence", [])
                    reference = next((row for row in sources if row.get("field") == "country_currency"), {})
                    checks = {"research_completed": job["status"] == "completed", "issuer_identity": risk.get("issuer_id") == "sec:1379785",
                              "country_currency": (risk.get("parameters") or {}).get("country_currency") == "USD",
                              "reference_units": reference.get("units") == "iso4217_currency_code",
                              "reference_basis": reference.get("basis") == "iso4217_country_reference",
                              "reference_date": reference.get("as_of") == "2026-09-17",
                              "domicile_is_proxy": (risk.get("country") or {}).get("basis") == "issuer_domicile_proxy",
                              "economic_fx_remains_unknown": risk.get("currency_exposures") is None}
                    receipt = {"attempt": attempt, "environment": "synthetic portfolio; actual deployed/local application HTTPS, auth, model, Internet and REST persistence",
                               "payload": payload, "job": job, "saved_risk_inputs": risk, "diagnostics": diagnostics,
                               "leaf_diagnostics": leaf_diagnostics, "checks": checks}
                    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    with os.fdopen(descriptor, "w") as handle:
                        json.dump(receipt, handle, indent=2)
                    print(json.dumps({"attempt": attempt, "request_id": identifier, "checks": checks, "status": job["status"], "code": job.get("code"), "receipt": str(output)}), flush=True)
                    return all(checks.values())
            finally:
                lifecycle = temporary / "data/logs/market-data.log"
                if lifecycle.is_file():
                    retained = output.parent / f"attempt-{attempt}-lifecycle.jsonl"
                    descriptor = os.open(retained, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    with lifecycle.open(errors="replace") as source, os.fdopen(descriptor, "w") as target:
                        for line in source:
                            try:
                                row = json.loads(line)
                            except ValueError:
                                continue
                            if str(row.get("event", "")).startswith("research_"):
                                target.write(json.dumps(row) + "\n")
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--attempt", type=int, choices=range(1, 7), required=True)
    parser.add_argument("--runner", help="REST runner source path when executing inside the deployed container.")
    args = parser.parse_args()
    raise SystemExit(0 if execute(args.output, args.attempt, args.runner) else 2)
