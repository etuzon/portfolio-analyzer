from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import data_dir
from .metrics import screen, to_dict


class AlertStore:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "alerts.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_rules(self) -> list[dict[str, Any]]:
        return self._read().get("rules", [])

    def add_rule(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        rule = {
            "id": str(uuid4()),
            "name": payload.get("name") or "Untitled alert",
            "enabled": bool(payload.get("enabled", True)),
            "criteria": payload.get("criteria") or {},
            "notification": payload.get("notification") or {"channels": ["dashboard"]},
            "created_at": datetime.utcnow().isoformat() + "Z",
            "last_run": None,
            "last_matches": [],
            "last_status": "not run",
        }
        data.setdefault("rules", []).append(rule)
        self._write(data)
        return rule

    def update_rule(self, rule_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        data = self._read()
        for rule in data.setdefault("rules", []):
            if rule["id"] == rule_id:
                for key in ["name", "enabled", "criteria", "notification"]:
                    if key in payload:
                        rule[key] = payload[key]
                self._write(data)
                return rule
        return None

    def delete_rule(self, rule_id: str) -> bool:
        data = self._read()
        before = len(data.setdefault("rules", []))
        data["rules"] = [rule for rule in data["rules"] if rule["id"] != rule_id]
        self._write(data)
        return len(data["rules"]) != before

    def evaluate(self, analyses: list[Any]) -> list[dict[str, Any]]:
        data = self._read()
        results = []
        for rule in data.setdefault("rules", []):
            if not rule.get("enabled", True):
                continue
            matches = screen(analyses, rule.get("criteria") or {})
            rule["last_run"] = datetime.utcnow().isoformat() + "Z"
            rule["last_matches"] = [item.holding.symbol for item in matches]
            rule["last_status"] = "matched" if matches else "no matches"
            results.append({"rule": rule, "matches": [to_dict(item) for item in matches]})
        self._write(data)
        return results

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"rules": []}
        try:
            return json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return {"rules": []}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2, default=str))


def start_scheduler(alert_store: AlertStore, analyze_all, alert_config: dict[str, Any], capture_history=None) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=alert_config.get("timezone") or "UTC")
    expression = alert_config.get("schedule") or "0 7 * * *"
    minute, hour, day, month, day_of_week = expression.split()
    scheduler.add_job(
        lambda: alert_store.evaluate(analyze_all()),
        CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week),
        id="daily-alert-evaluation",
        replace_existing=True,
    )
    if capture_history:
        scheduler.add_job(
            capture_history,
            CronTrigger(minute=55, hour=23),
            id="daily-history-snapshot",
            replace_existing=True,
        )
    scheduler.start()
    return scheduler
