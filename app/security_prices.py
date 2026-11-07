"""Listing-qualified, dated local price overrides and saved market evidence."""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any, Callable, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .local_portfolio import normalize_price


def price_day(value: str) -> date:
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    raise ValueError("Price date must use DD/MM/YYYY or YYYY-MM-DD")


def quote_unit(security: dict[str, Any]) -> str:
    # Derive the convention from the maintained normalizer, including its aliases.
    if normalize_price(100, security["location"], security["asset_class"]) == 1:
        return "agorot" if security["currency"] == "ILS" else "cents"
    return "currency"


class PriceObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    price_input: Annotated[float, Field(gt=0, strict=True)]
    price_date: str
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    quote_unit: Literal["currency", "agorot", "cents"]
    price_basis: Literal["last", "close"]
    source_url: Annotated[str, Field(min_length=8, max_length=2000)]
    evidence_quote: Annotated[str, Field(max_length=4000)] = ""
    observed_at: datetime | None = None
    retrieved_at: datetime

    @field_validator("price_input", mode="before")
    @classmethod
    def numeric_price(cls, value):
        try:
            valid = type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("Price must be a finite positive number")
        return value

    @field_validator("price_date")
    @classmethod
    def dated_price(cls, value):
        day = price_day(value)
        if day > date.today():
            raise ValueError("Future price dates are not supported")
        return day.isoformat()

    @field_validator("source_url")
    @classmethod
    def public_source(cls, value):
        try:
            parts = urlsplit(value)
            if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username or parts.password:
                raise ValueError()
            _ = parts.port
        except ValueError:
            raise ValueError("Source must be an HTTP(S) URL without credentials") from None
        return value

    @field_validator("observed_at", "retrieved_at")
    @classmethod
    def timezone_required(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Evidence timestamps must include a timezone")
        if value is not None and value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Evidence timestamps cannot be in the future")
        return value


class PriceBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: Annotated[str, Field(min_length=1, max_length=80)]
    stock_market: Annotated[str, Field(min_length=1, max_length=80)]
    items: Annotated[list[PriceObservation], Field(min_length=1, max_length=500)]


def _record(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    try:
        evidence = json.loads(row.get("comments") or "{}")
        if isinstance(evidence, dict) and evidence.get("kind") == "price_evidence_v1":
            result["evidence"] = evidence
    except (ValueError, TypeError):
        pass
    result.setdefault("price_basis", (result.get("evidence") or {}).get("price_basis", "unknown"))
    return result


class PriceRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def validated(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                # Nonstandard JSON may contain NaN/Infinity. Do not echo those
                # non-JSON values (or source credentials) into error responses.
                errors = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
                return JSONResponse(status_code=422, content={"detail": errors})

        return validated


def price_router(store: Callable, market_hub: Callable, invalidate: Callable, history_start: date) -> APIRouter:
    router = APIRouter(tags=["security prices"], route_class=PriceRoute)

    def metadata(symbol: str, stock_market: str) -> dict[str, Any]:
        security = store().manual_security(symbol, stock_market)
        if not security:
            raise HTTPException(404, "Unknown security listing; add the security in Securities first")
        fields = ("symbol", "secondary_symbol", "stock_market", "currency", "location", "asset_class", "name", "company_name")
        result = {key: security.get(key, "") for key in fields}
        result["quote_unit"] = quote_unit(result)
        return result

    def read(symbol: str, stock_market: str, date_from: str = "", date_to: str = "") -> dict[str, Any]:
        security = metadata(symbol, stock_market)
        try:
            start = price_day(date_from) if date_from else history_start
            end = price_day(date_to) if date_to else date.today()
            if start < history_start or end > date.today() or start > end:
                raise ValueError("Price range must be ordered, retained, and not in the future")
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        # Read the full retained series so a historical filter cannot change current.
        local = store().price_history(security["symbol"], security["stock_market"], history_start, date.today())
        by_day: dict[str, dict[str, Any]] = {}
        status: dict[str, Any] = {}
        # Unlisted manual securities have no verifiable provider ticker.
        if security.get("secondary_symbol"):
            cached, status = market_hub().cached_prices(
                security["symbol"], history_start, date.today(),
                secondary_symbol=security["secondary_symbol"], stock_market=security["stock_market"],
            )
            for row in cached:
                if row.close is not None and math.isfinite(row.close) and row.close > 0:
                    by_day[row.date.isoformat()] = {
                        "symbol": security["symbol"], "stock_market": security["stock_market"],
                        "currency": security["currency"], "price_date": row.date.isoformat(),
                        "price": row.close, "price_basis": "close", "source": "provider_cache",
                    }
        for row in local:
            if (row.get("currency") == security["currency"] and row.get("asset_class") == security["asset_class"]
                    and row.get("location") == security["location"] and row.get("price", 0) > 0
                    and math.isfinite(row["price"])):
                by_day[row["price_date"]] = _record(row)
        rows = [by_day[day] for day in sorted(by_day) if history_start.isoformat() <= day <= date.today().isoformat()]
        current = rows[-1] if rows else None
        current_status = "missing"
        if current:
            current_status = "stale" if price_day(current["price_date"]) < date.today() - timedelta(days=7) else "dated"
        return {
            "security": security, "items": [row for row in rows if start.isoformat() <= row["price_date"] <= end.isoformat()],
            "current": current, "current_status": current_status, "coverage": "local_and_cached",
            "date_from": start.isoformat(), "date_to": end.isoformat(), "provider_status": status,
            "note": "Latest saved observation, not a live quote. Missing prices are unknown. Provider closes and new overrides are unadjusted; legacy local basis may be unknown. Prices use the security currency; history may be incomplete.",
        }

    @router.get("/api/security/prices")
    def history(symbol: Annotated[str, Query(min_length=1, max_length=80)], stock_market: Annotated[str, Query(min_length=1, max_length=80)], date_from: str = "", date_to: str = ""):
        return read(symbol, stock_market, date_from, date_to)

    @router.get("/api/security/price")
    def current(symbol: Annotated[str, Query(min_length=1, max_length=80)], stock_market: Annotated[str, Query(min_length=1, max_length=80)]):
        result = read(symbol, stock_market)
        return {key: value for key, value in result.items() if key != "items"}

    @router.put("/api/security/prices")
    def update(payload: PriceBatch):
        security = metadata(payload.symbol, payload.stock_market)
        days: set[str] = set()
        records = []
        for item in payload.items:
            if item.currency != security["currency"] or item.quote_unit != security["quote_unit"]:
                raise HTTPException(422, "Currency or quote unit conflicts with the saved security")
            if price_day(item.price_date) < history_start or item.price_date in days:
                raise HTTPException(422, "Price date is outside retention or repeated in the batch")
            if item.observed_at and (item.observed_at.date().isoformat() != item.price_date or item.observed_at > item.retrieved_at):
                raise HTTPException(422, "Observation timestamp must match the price date and precede retrieval")
            if price_day(item.price_date) > item.retrieved_at.date():
                raise HTTPException(422, "Price date cannot follow the evidence retrieval date")
            days.add(item.price_date)
            evidence = {"kind": "price_evidence_v1", **item.model_dump(mode="json", exclude={"price_input", "price_date", "currency"})}
            records.append({
                **security, "price_input": item.price_input, "price_date": item.price_date,
                "source": "web_evidence", "comments": json.dumps(evidence, ensure_ascii=False),
            })
        try:
            saved = store().save_prices(records)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        invalidate()
        return {"security": security, "items": [_record(row) for row in saved], "updated": len(saved)}

    return router
