#!/usr/bin/env python3
"""Run one bounded price research request from the host's signed-in AI CLI."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_config
from app.price_agent import PriceAgent, PriceAgentError, make_rest_client, price_agent_settings


def input_date(value: str) -> str:
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            pass
    raise argparse.ArgumentTypeError("Use dd/mm/yyyy for dates.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Research and update one security's prices using the configured Codex or Claude Code CLI. Each request has hard five-call model and REST ceilings, including failures.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--stock-market", required=True)
    parser.add_argument("--date-from", type=input_date, default="")
    parser.add_argument("--date-to", type=input_date, default="")
    parser.add_argument("--config", help="YAML file; defaults to CONFIG_PATH or config.yaml.")
    parser.add_argument("--ca-file", help="Trusted certificate file for the local HTTPS service.")
    parser.add_argument("--dry-run", action="store_true", help="Research and validate a proposal without writing prices.")
    args = parser.parse_args()
    if args.config:
        if not Path(args.config).is_file():
            parser.error("The specified configuration file does not exist.")
        os.environ["CONFIG_PATH"] = args.config
    agent = None
    try:
        settings = price_agent_settings(load_config().raw)
        # Prerequisites are checked before spending any application or model calls.
        if not settings["search_api_key"]:
            raise PriceAgentError("Set BRAVE_SEARCH_API_KEY or price_agent.search.api_key to enable internet search.")
        rest = make_rest_client(settings["base_url"], os.getenv("PORTFOLIO_API_TOKEN", ""), ca_file=args.ca_file)
        agent = PriceAgent(settings, rest)
        result = agent.run(args.symbol, args.stock_market, date_from=args.date_from, date_to=args.date_to, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] in {"updated", "dry_run"} else 2
    except (PriceAgentError, OSError) as exc:
        result = {"status": "failed", "error": str(exc)}
        if agent:
            result.update(agent.budget.counts())
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
