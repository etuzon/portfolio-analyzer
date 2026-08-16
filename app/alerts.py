from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import data_dir


ALERT_JOB_ID = "daily-alert-evaluation"
ALERT_SIGNALS = {
    "buy": "Buy signal",
    "sell": "Sell signal",
    "watch": "Watch signal",
}
ALERT_OPERATORS = {
    ">": "Greater than",
    ">=": "Greater than or equal",
    "<": "Less than",
    "<=": "Less than or equal",
    "=": "Equal to",
}
ALERT_METRICS = {
    "dividend_yield_percent": {"label": "Dividend yield", "unit": "%", "group": "Income", "digits": 2},
    "dividend_growth_percent": {"label": "Dividend growth", "unit": "%", "group": "Income", "digits": 1},
    "market_cap_millions": {"label": "Market cap", "unit": "M", "group": "Valuation", "digits": 0},
    "annual_net_income_millions": {"label": "Annual net profit", "unit": "M", "group": "Statements", "digits": 0},
    "profit_market_cap_percent": {"label": "Profit / market cap", "unit": "%", "group": "Valuation", "digits": 2},
    "price_earnings_ratio": {"label": "Price / earnings", "unit": "×", "group": "Valuation", "digits": 2},
    "revenue_growth_percent": {"label": "Revenue growth", "unit": "%", "group": "Statements", "digits": 1},
    "net_income_growth_percent": {"label": "Profit growth", "unit": "%", "group": "Statements", "digits": 1},
    "net_margin_percent": {"label": "Net margin", "unit": "%", "group": "Statements", "digits": 1},
    "free_cash_flow_millions": {"label": "Free cash flow", "unit": "M", "group": "Cash flow", "digits": 0},
    "free_cash_flow_yield_percent": {"label": "Free-cash-flow yield", "unit": "%", "group": "Cash flow", "digits": 2},
    "debt_to_revenue_percent": {"label": "Debt / revenue", "unit": "%", "group": "Balance sheet", "digits": 1},
    "current_ratio": {"label": "Current ratio", "unit": "ratio", "group": "Balance sheet", "digits": 2},
    "unrealized_profit_percent": {"label": "Holding unrealized P/L", "unit": "%", "group": "Portfolio", "digits": 1},
    "holding_allocation_percent": {"label": "Portfolio allocation", "unit": "%", "group": "Portfolio", "digits": 1},
    "price_vs_ma30_percent": {"label": "Price vs MA 30", "unit": "%", "group": "Market", "digits": 1},
    "ma30_slope_percent": {"label": "MA 30 slope", "unit": "%", "group": "Market", "digits": 2},
    "relative_volume_20d": {"label": "Relative volume vs 20D", "unit": "×", "group": "Market", "digits": 2},
    "confirmed_breakout": {"label": "Confirmed resistance breakout", "unit": "1=yes", "group": "Market", "digits": 0},
    "price_from_high_1y_percent": {"label": "Price from 1Y high", "unit": "%", "group": "Market", "digits": 1},
}


def alert_rule_options() -> dict[str, Any]:
    return {
        "metrics": [{"key": key, **value} for key, value in ALERT_METRICS.items()],
        "operators": [{"key": key, "label": label} for key, label in ALERT_OPERATORS.items()],
        "signals": [{"key": key, "label": label} for key, label in ALERT_SIGNALS.items()],
        "match_modes": [
            {"key": "all", "label": "Match all conditions"},
            {"key": "any", "label": "Match any condition"},
        ],
    }


class AlertStore:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "alerts.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def list_rules(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._normalize_stored_rule(rule) for rule in self._read().get("rules", [])]

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            runs = self._read().get("runs", [])
        return list(reversed(runs[-max(1, min(int(limit or 20), 100)) :]))

    def add_rule(self, payload: dict[str, Any]) -> dict[str, Any]:
        rule = self._validated_rule(payload, rule_id=str(uuid4()), created_at=_now())
        with self._lock:
            data = self._read()
            data.setdefault("rules", []).append(rule)
            self._write(data)
        return rule

    def update_rule(self, rule_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            data = self._read()
            rules = data.setdefault("rules", [])
            for index, stored in enumerate(rules):
                if stored.get("id") != rule_id:
                    continue
                merged = {**stored, **payload, "id": rule_id, "created_at": stored.get("created_at") or _now()}
                updated = self._validated_rule(merged, rule_id=rule_id, created_at=merged["created_at"])
                for key in ["last_run", "last_matches", "last_status", "last_missing_count"]:
                    if key in stored:
                        updated[key] = stored[key]
                rules[index] = updated
                self._write(data)
                return updated
        return None

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            data = self._read()
            before = len(data.setdefault("rules", []))
            data["rules"] = [rule for rule in data["rules"] if rule.get("id") != rule_id]
            changed = len(data["rules"]) != before
            if changed:
                self._write(data)
            return changed

    def evaluate(self, rows: list[dict[str, Any]], metadata: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        run_at = _now()
        safe_rows = [row for row in rows if isinstance(row, dict) and str(row.get("symbol") or "").strip()]
        results: list[dict[str, Any]] = []
        with self._lock:
            data = self._read()
            for stored_rule in data.setdefault("rules", []):
                rule = self._normalize_stored_rule(stored_rule)
                stored_rule.update(rule)
                if not rule.get("enabled", True):
                    continue
                conditions = rule.get("conditions") or []
                if not conditions:
                    stored_rule["last_run"] = run_at
                    stored_rule["last_matches"] = []
                    stored_rule["last_status"] = "Needs at least one condition"
                    stored_rule["last_missing_count"] = 0
                    results.append({"rule": dict(stored_rule), "matches": []})
                    continue
                matches: list[dict[str, Any]] = []
                missing_count = 0
                for row in safe_rows:
                    match, reasons, missing_metrics = self._matches_rule(row, rule)
                    missing_count += int(bool(missing_metrics))
                    if match:
                        matches.append(self._match_out(row, rule, reasons, missing_metrics, run_at))
                stored_rule["last_run"] = run_at
                stored_rule["last_matches"] = matches
                stored_rule["last_status"] = f"{len(matches)} match{'es' if len(matches) != 1 else ''}" if matches else "No matches"
                stored_rule["last_missing_count"] = missing_count
                results.append({"rule": dict(stored_rule), "matches": matches})
            run = {
                "id": str(uuid4()),
                "run_at": run_at,
                "status": "completed",
                "evaluated_symbols": len(safe_rows),
                "matched_signals": sum(len(result["matches"]) for result in results),
                "rules_evaluated": len(results),
                "rule_results": [
                    {
                        "rule_id": result["rule"].get("id"),
                        "name": result["rule"].get("name"),
                        "signal": result["rule"].get("signal"),
                        "matches": [item.get("symbol") for item in result["matches"]],
                    }
                    for result in results
                ],
                "metadata": metadata or {},
            }
            runs = data.setdefault("runs", [])
            runs.append(run)
            data["runs"] = runs[-100:]
            self._write(data)
        return results

    def record_failure(self, error: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        run_at = _now()
        message = str(error or "Rule check failed")[:200]
        with self._lock:
            data = self._read()
            enabled_rules = 0
            for stored_rule in data.setdefault("rules", []):
                rule = self._normalize_stored_rule(stored_rule)
                stored_rule.update(rule)
                if not rule.get("enabled", True):
                    continue
                enabled_rules += 1
                stored_rule["last_run"] = run_at
                stored_rule["last_matches"] = []
                stored_rule["last_status"] = message
            run = {
                "id": str(uuid4()),
                "run_at": run_at,
                "status": "failed",
                "evaluated_symbols": 0,
                "matched_signals": 0,
                "rules_evaluated": enabled_rules,
                "rule_results": [],
                "error": message,
                "metadata": metadata or {},
            }
            runs = data.setdefault("runs", [])
            runs.append(run)
            data["runs"] = runs[-100:]
            self._write(data)
        return run

    def _matches_rule(self, row: dict[str, Any], rule: dict[str, Any]) -> tuple[bool, list[dict[str, Any]], list[str]]:
        checks: list[dict[str, Any]] = []
        missing_metrics: list[str] = []
        for condition in rule.get("conditions") or []:
            metric = condition["metric"]
            raw_value = row.get(metric)
            value = _number(raw_value)
            if value is None:
                missing_metrics.append(metric)
                checks.append({"metric": metric, "operator": condition["operator"], "threshold": condition["value"], "value": None, "matched": False})
                continue
            matched = _compare(value, condition["operator"], float(condition["value"]))
            checks.append({"metric": metric, "operator": condition["operator"], "threshold": condition["value"], "value": value, "matched": matched})
        matches = [check["matched"] for check in checks]
        passed = all(matches) if rule.get("match_mode") == "all" else any(matches)
        reasons = [check for check in checks if check["matched"]]
        return bool(checks and passed), reasons, missing_metrics

    def _match_out(
        self,
        row: dict[str, Any],
        rule: dict[str, Any],
        reasons: list[dict[str, Any]],
        missing_metrics: list[str],
        run_at: str,
    ) -> dict[str, Any]:
        return {
            "symbol": str(row.get("symbol") or "").upper(),
            "name": str(row.get("name") or row.get("symbol") or ""),
            "signal": rule.get("signal") or "watch",
            "rule_id": rule.get("id"),
            "rule_name": rule.get("name"),
            "matched_at": run_at,
            "accounts": row.get("accounts") or [],
            "market_value": _number(row.get("market_value")),
            "currency": str(row.get("currency") or ""),
            "reasons": reasons,
            "missing_metrics": missing_metrics,
            "missing": row.get("missing") or [],
        }

    def _validated_rule(self, payload: dict[str, Any], rule_id: str, created_at: str) -> dict[str, Any]:
        name = str(payload.get("name") or "Untitled signal rule").strip()[:120]
        signal = str(payload.get("signal") or "watch").lower()
        if signal not in ALERT_SIGNALS:
            raise ValueError("Signal must be buy, sell, or watch")
        match_mode = str(payload.get("match_mode") or "all").lower()
        if match_mode not in {"all", "any"}:
            raise ValueError("Match mode must be all or any")
        conditions = self._validated_conditions(payload.get("conditions"))
        if not conditions:
            raise ValueError("Add at least one financial condition")
        return {
            "id": rule_id,
            "name": name,
            "enabled": bool(payload.get("enabled", True)),
            "signal": signal,
            "scope": "portfolio",
            "match_mode": match_mode,
            "conditions": conditions,
            "notification": payload.get("notification") if isinstance(payload.get("notification"), dict) else {"channels": ["dashboard"]},
            "created_at": created_at,
            "last_run": payload.get("last_run"),
            "last_matches": payload.get("last_matches") if isinstance(payload.get("last_matches"), list) else [],
            "last_status": str(payload.get("last_status") or "Not run"),
            "last_missing_count": int(_number(payload.get("last_missing_count")) or 0),
        }

    def _validated_conditions(self, raw_conditions: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_conditions, list):
            return []
        conditions: list[dict[str, Any]] = []
        for raw in raw_conditions[:12]:
            if not isinstance(raw, dict):
                continue
            metric = str(raw.get("metric") or "").strip()
            operator = str(raw.get("operator") or ">").strip()
            value = _number(raw.get("value"))
            if metric not in ALERT_METRICS:
                raise ValueError(f"Unsupported alert metric: {metric or 'blank'}")
            if operator not in ALERT_OPERATORS:
                raise ValueError(f"Unsupported alert operator: {operator}")
            if value is None:
                raise ValueError("Every alert condition needs a numeric value")
            conditions.append({"metric": metric, "operator": operator, "value": value})
        return conditions

    def _normalize_stored_rule(self, stored: dict[str, Any]) -> dict[str, Any]:
        rule = dict(stored)
        rule.setdefault("signal", "watch")
        rule.setdefault("scope", "portfolio")
        rule.setdefault("match_mode", "all")
        if not isinstance(rule.get("conditions"), list):
            rule["conditions"] = _legacy_conditions(rule.get("criteria"))
        rule.setdefault("last_matches", [])
        rule.setdefault("last_status", "Not run")
        rule.setdefault("last_missing_count", 0)
        return rule

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"rules": [], "runs": []}
        try:
            value = json.loads(self.path.read_text())
            return value if isinstance(value, dict) else {"rules": [], "runs": []}
        except (json.JSONDecodeError, OSError):
            return {"rules": [], "runs": []}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2, default=str))


def start_scheduler(alert_store: AlertStore, evaluate_alerts: Callable[[], Any], alert_config: dict[str, Any], capture_history=None) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=alert_config.get("timezone") or "UTC")
    expression = alert_config.get("schedule") or "0 7 * * *"
    trigger = CronTrigger.from_crontab(expression, timezone=alert_config.get("timezone") or "UTC")
    scheduler.add_job(evaluate_alerts, trigger, id=ALERT_JOB_ID, replace_existing=True, max_instances=1, coalesce=True)
    if capture_history:
        scheduler.add_job(
            capture_history,
            CronTrigger(minute=55, hour=23),
            id="daily-history-snapshot",
            replace_existing=True,
        )
    scheduler.start()
    return scheduler


def _legacy_conditions(criteria: Any) -> list[dict[str, Any]]:
    if not isinstance(criteria, dict):
        return []
    conditions: list[dict[str, Any]] = []
    profit_market_cap = _number(criteria.get("minProfitMarketCap"))
    if profit_market_cap is not None:
        conditions.append({"metric": "profit_market_cap_percent", "operator": ">=", "value": profit_market_cap * 100})
    dividend_growth = _number(criteria.get("minDividendGrowth"))
    if dividend_growth is not None:
        conditions.append({"metric": "dividend_growth_percent", "operator": ">=", "value": dividend_growth})
    return conditions


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    return math.isclose(value, threshold, rel_tol=1e-9, abs_tol=1e-9)


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
