"""Shared wall-clock recurrence contract for application schedules.

Weekdays use Python/ISO ordering: Monday=0 through Sunday=6. Step cadences
restart each hour (minutes) or day (hours), as displayed by the shared editor.
"""
from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo
from apscheduler.triggers.cron import CronTrigger

FREQUENCIES = {"minutely", "hourly", "daily", "weekly", "monthly"}
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def integer(value: Any, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValueError("Invalid schedule number")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid schedule number") from exc
    if str(number) != str(value).strip() or not minimum <= number <= maximum:
        raise ValueError("Schedule number outside allowed range")
    return number


def normalize_schedule(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("frequency") not in FREQUENCIES:
        raise ValueError("Invalid schedule frequency")
    frequency = raw["frequency"]
    # The editor retains hidden fields when switching cadence. Only validate
    # clock components that participate in the selected recurrence.
    result = {"frequency": frequency,
              "hour": 23 if frequency in {"minutely", "hourly"} else integer(raw.get("hour", 23), 0, 23),
              "minute": 45 if frequency == "minutely" else integer(raw.get("minute", 45), 0, 59)}
    if frequency in {"minutely", "hourly"}:
        result["interval"] = integer(raw.get("interval", 1), 1, 59 if frequency == "minutely" else 23)
    for name, maximum, default in (("weekdays", 6, [0, 2, 4]), ("month_days", 31, [1])):
        if frequency != ("weekly" if name == "weekdays" else "monthly"):
            continue
        values = raw.get(name, default)
        if not isinstance(values, list) or not values:
            raise ValueError("Select at least one schedule day")
        result[name] = sorted({integer(value, 0 if name == "weekdays" else 1, maximum) for value in values})
    return result


def schedule_cron(raw: dict[str, Any]) -> str:
    item = normalize_schedule(raw)
    frequency, minute, hour = item["frequency"], item["minute"], item["hour"]
    if frequency == "minutely":
        return f"*/{item['interval']} * * * *"
    if frequency == "hourly":
        return f"{minute} */{item['interval']} * * *"
    day = ",".join(map(str, item["month_days"])) if frequency == "monthly" else "*"
    weekday = ",".join(WEEKDAYS[value] for value in item["weekdays"]) if frequency == "weekly" else "*"
    return f"{minute} {hour} {day} * {weekday}"


def schedule_trigger(raw: dict[str, Any], timezone_name: str) -> CronTrigger:
    ZoneInfo(timezone_name)
    return CronTrigger.from_crontab(schedule_cron(raw), timezone=timezone_name)


def schedule_from_cron(expression: str) -> dict[str, Any]:
    minute, hour, day, month, weekday = expression.split()
    if month != "*":
        raise ValueError("Unsupported schedule month")
    raw = {"frequency": "daily", "hour": 23 if hour == "*" or hour.startswith("*/") else hour,
           "minute": 45 if minute == "*" or minute.startswith("*/") else minute}
    if hour == "*" and minute == "*":
        raw.update(frequency="minutely", interval=1)
    elif minute.startswith("*/") and hour == "*":
        raw.update(frequency="minutely", interval=minute[2:])
    elif hour == "*" or hour.startswith("*/"):
        raw.update(frequency="hourly", interval=1 if hour == "*" else hour[2:])
    elif day != "*" and weekday == "*":
        raw.update(frequency="monthly", month_days=day.split(","))
    elif weekday != "*" and day == "*":
        raw.update(frequency="weekly", weekdays=[WEEKDAYS.index(value.lower()) if value.lower() in WEEKDAYS else value for value in weekday.split(",")])
    elif day != "*":
        raise ValueError("Unsupported combined day schedule")
    return normalize_schedule(raw)
