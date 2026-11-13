"""Explicit issuer domicile associations, separate from listing and currency."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt

PREFIX = "security-country-v1:"


class CountryAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    security_key: str = Field(min_length=1, max_length=300)
    country_code: str = Field(min_length=2, max_length=2)
    expected_revision: StrictInt = Field(ge=0)
    expected_identity: str = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=1000)


class SecurityCountries:
    def __init__(self, *, store, inventory, normalize_country, country_descriptor):
        self.store, self.inventory = store, inventory
        self.normalize_country, self.country_descriptor = normalize_country, country_descriptor

    def candidate(self, key):
        key = str(key).strip().upper()
        row = next((row for row in self.inventory() if row["security_key"].upper() == key), None)
        if row is None:
            raise HTTPException(404, "security_not_found")
        return row

    @staticmethod
    def identity(row):
        fields = {name: row.get(name) for name in ("security_key", "issuer_name", "issuer_identity_verified")}
        return hashlib.sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()

    @staticmethod
    def preference_key(row):
        return PREFIX + hashlib.sha256(row["security_key"].encode()).hexdigest()

    def read(self, row):
        saved = self.store().get_preference(self.preference_key(row))
        saved = saved if isinstance(saved, dict) else {}
        identity = self.identity(row)
        override = self.normalize_country(saved.get("country_code")) if saved.get("identity_token") == identity else None
        code = override or self.normalize_country(row.get("issuer_country"))
        descriptor = self.country_descriptor(code) if code else None
        return {"security_key": row["security_key"], "country_code": code,
                "country_name": descriptor.get("country_name") if descriptor else None,
                "source_kind": "manual" if override else "provider_profile" if code else "unknown",
                "identity_token": identity, "revision": saved.get("revision", 0),
                "notes": saved.get("notes", "") if override else "",
                "updated_at": saved.get("updated_at"), "updated_by": saved.get("updated_by")}

    def update(self, row, code, revision, identity, user, notes=""):
        if identity != self.identity(row):
            raise HTTPException(409, "country_identity_changed")
        if code is not None:
            code = self.normalize_country(code)
            if not code or not self.country_descriptor(code):
                raise HTTPException(422, "unsupported_country")
        def edit(current):
            current = current or {}
            if current.get("revision", 0) != revision:
                raise HTTPException(409, "country_revision_conflict")
            return {"identity_token": identity, "revision": revision + 1, "country_code": code,
                    "notes": notes, "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": user.get("username") or user["id"]}
        self.store().update_preference(self.preference_key(row), edit)
        return self.read(row)

    def countries(self, scope="open"):
        grouped = {}
        for row in self.inventory():
            if scope == "open" and not row.get("has_open_position"):
                continue
            association = self.read(row)
            code = association["country_code"]
            if code:
                descriptor = deepcopy(self.country_descriptor(code))
                current = grouped.setdefault(code, {**descriptor, "has_open_position": False, "security_keys": []})
                current["has_open_position"] |= bool(row.get("has_open_position"))
                current["security_keys"].append(row["security_key"])
        return sorted(grouped.values(), key=lambda row: row["country_code"])

    def router(self):
        router = APIRouter(tags=["security country"])
        def user(request, edit=False):
            owner = getattr(request.state, "auth_user", None)
            if not isinstance(owner, dict):
                raise HTTPException(401, "authentication_required")
            if edit and owner.get("role") not in {"Admin", "Operator"}:
                raise HTTPException(403, "read_only")
            return owner
        @router.get("/api/securities/country")
        def read(request: Request, symbol: str, stock_market: str, currency: str):
            user(request)
            return self.read(self.candidate("|".join((symbol, stock_market, currency))))
        @router.put("/api/securities/country")
        def update(request: Request, payload: CountryAssignment):
            owner = user(request, True)
            return self.update(self.candidate(payload.security_key), payload.country_code, payload.expected_revision,
                               payload.expected_identity, owner, payload.notes)
        @router.delete("/api/securities/country")
        def clear(request: Request, security_key: str, expected_revision: int, expected_identity: str):
            owner = user(request, True)
            if expected_revision < 0:
                raise HTTPException(422, "invalid_revision")
            return self.update(self.candidate(security_key), None, expected_revision, expected_identity, owner)
        return router
