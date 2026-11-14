"""Dated local model inputs and cache-only, identity-bound credit evidence.

This module does not fetch providers, calculate prices, or write an import source.
User assumptions remain separate from verified agency opinions.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import math
from typing import Callable

from fastapi import APIRouter, HTTPException, Request

from .credit_ratings import _entity, _url, is_primary_observation, normalize_grade
from .security_enrichment import security_key
from .sovereign_ratings import normalize_country


MODEL = "portfolio-risk-v3"
PREFIX = "stress-risk-inputs-v1:"
EVIDENCE_PREFIX = "stress-risk-evidence-v1:"
PARAMETERS = frozenset({"instrument_kind", "pricing_model", "maturity_date", "cashflows",
    "continuous_yield", "current_spread_bps", "country_sensitivity", "sovereign_currency_basis",
    "country_code", "country_currency", "country_basis", "plain_nominal_noncallable", "zero_coupon_confirmed",
    "assumptions_enabled", "as_of", "source_url", "notes"})
_KINDS = {"equity", "fund", "corporate_bond", "sovereign_bond"}
_MOODYS = {"Aaa":"AAA", "Aa1":"AA", "Aa2":"AA", "Aa3":"AA", "A1":"A", "A2":"A", "A3":"A",
    "Baa1":"BBB", "Baa2":"BBB", "Baa3":"BBB", "Ba1":"BB", "Ba2":"BB", "Ba3":"BB",
    "B1":"B", "B2":"B", "B3":"B", "Caa1":"CCC", "Caa2":"CCC", "Caa3":"CCC", "Ca":"CCC"}
_BUCKETS = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()).hexdigest()


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _day(value, field):
    if not isinstance(value, str):
        raise ValueError("risk_input_invalid_" + field)
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        try:
            return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
        except ValueError:
            raise ValueError("risk_input_invalid_" + field) from None


def normalize_parameters(value):
    if not isinstance(value, dict) or set(value) - PARAMETERS:
        raise ValueError("risk_input_invalid_parameters")
    result = {key: deepcopy(val) for key, val in value.items() if val is not None and val != ""}
    if not result:
        return {}
    for key, allowed in (("instrument_kind", _KINDS),
                         ("pricing_model", {"zero_coupon_continuous", "cashflows_continuous"}),
                         ("country_basis", {"issuer_domicile_proxy", "economic_exposure", "not_applicable"}),
                         ("sovereign_currency_basis", {"local_currency", "foreign_currency"})):
        if key in result and result[key] not in allowed:
            raise ValueError("risk_input_invalid_" + key)
    for key in ("continuous_yield", "current_spread_bps", "country_sensitivity"):
        if key in result and not _number(result[key]):
            raise ValueError("risk_input_invalid_" + key)
    if result.get("current_spread_bps", 0) < 0:
        raise ValueError("risk_input_invalid_current_spread_bps")
    if not 0 <= result.get("country_sensitivity", 0) <= 1:
        raise ValueError("risk_input_invalid_country_sensitivity")
    for key in ("plain_nominal_noncallable", "zero_coupon_confirmed", "assumptions_enabled"):
        if key in result and type(result[key]) is not bool:
            raise ValueError("risk_input_invalid_" + key)
    for key in ("as_of", "maturity_date"):
        if key in result:
            result[key] = _day(result[key], key)
    if not result.get("as_of") or result["as_of"] > date.today().isoformat():
        raise ValueError("risk_input_invalid_as_of")
    for key, limit in (("source_url", 2500), ("notes", 2000)):
        if key in result and (not isinstance(result[key], str) or len(result[key]) > limit):
            raise ValueError("risk_input_invalid_" + key)
    if not result.get("source_url") and not str(result.get("notes") or "").strip():
        raise ValueError("risk_input_source_required")
    if result.get("source_url"):
        result["source_url"] = _url(result["source_url"])
    if "country_code" in result:
        result["country_code"] = normalize_country(result["country_code"])
        if not result["country_code"]:
            raise ValueError("risk_input_invalid_country_code")
    if "country_currency" in result:
        currency = result["country_currency"]
        if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise ValueError("risk_input_invalid_country_currency")
        result["country_currency"] = currency.upper()
    if "cashflows" in result:
        flows = result["cashflows"]
        if not isinstance(flows, list) or not 1 <= len(flows) <= 1000:
            raise ValueError("risk_input_invalid_cashflows")
        prepared = []
        for flow in flows:
            if (not isinstance(flow, dict) or set(flow) != {"date", "amount"}
                    or not _number(flow.get("amount")) or flow["amount"] <= 0):
                raise ValueError("risk_input_invalid_cashflows")
            prepared.append({"date": _day(flow["date"], "cashflow_date"), "amount": flow["amount"]})
        result["cashflows"] = sorted(prepared, key=lambda row: row["date"])
    return result


def rating_bucket(row):
    try:
        grade = normalize_grade(row.get("rating"), row.get("agency"), "long_term", "global")
    except (ValueError, TypeError):
        return None
    if row.get("agency") == "moodys":
        return _MOODYS.get(grade)
    # Defaulted debt requires its own recovery/market-price analysis.
    if grade in {"D", "SD", "RD"}:
        return None
    base = grade.rstrip("+-")
    return base if base in _BUCKETS else "CCC" if base in {"CC", "C"} else None


def select_rating(response, candidate=None, *, basis=None, sovereign=False, allow_manual=False):
    """Conservative comparable verified opinions; manual overlays never verify facts."""
    eligible = []
    for row in (response or {}).get("ratings", []):
        manual = bool(row.get("manual_override") or row.get("source_kind") == "manual")
        if (row.get("status") != "rated" or row.get("scale") != "global" or row.get("term") != "long_term"
                or row.get("stale") or manual and not allow_manual):
            continue
        if not manual and row.get("source_kind") not in {"agency_public", "issuer_ir", "regulatory", "government_public", "licensed_api"}:
            continue
        try:
            verified_at = datetime.fromisoformat(str((row.get("updated_at") if manual else row.get("fetched_at")) or "").replace("Z", "+00:00"))
            if verified_at.tzinfo is None:
                verified_at = verified_at.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if verified_at > datetime.now(timezone.utc):
            continue
        if sovereign:
            if row.get("scope") != "sovereign" or row.get("currency_basis") != basis:
                continue
        elif not is_primary_observation(row, candidate):
            continue
        bucket = rating_bucket(row)
        if bucket:
            eligible.append({**deepcopy(row), "bucket": bucket})
    if not eligible:
        return None
    if not sovereign and candidate and "BOND" in {str(candidate.get(k) or "").upper() for k in ("asset_class", "asset_sub_class")}:
        issues = [row for row in eligible if row.get("scope") == "issue"]
        eligible = issues or eligible
    chosen = max(eligible, key=lambda row: _BUCKETS.index(row["bucket"]))
    estimated = any(row.get("manual_override") or row.get("source_kind") == "manual" for row in eligible)
    fields = ("agency", "rating", "bucket", "scope", "scale", "term", "rating_type", "entity_name", "entity_id",
              "currency_basis", "rating_date", "fetched_at", "source_url", "source_kind", "outlook", "watch",
              "outlook_stale", "watch_stale", "issuer_fallback", "manual_override", "updated_at", "notes", "manual_revision")
    return {**{key: chosen.get(key) for key in fields}, "verified": not estimated, "eligible": True,
            "eligible_for_estimate": estimated, "verification_status": "user_entered" if estimated else "verified",
            "status": "rated", "stale": False,
            "forward_signal_stale": bool(chosen.get("forward_signal_stale")),
            "negative_signal": any(row.get("outlook") == "negative" and not row.get("outlook_stale")
                                   or row.get("watch") == "negative" and not row.get("watch_stale") for row in eligible),
            "comparable_agencies": sorted({row["agency"] for row in eligible})}


class StressRiskInputs:
    def __init__(self, *, store: Callable, inventory: Callable, credit: Callable, sovereign: Callable,
                 countries: Callable):
        self._store, self._inventory, self._credit, self._sovereign, self._countries = store, inventory, credit, sovereign, countries

    def inventory(self):
        return list({row["security_key"]: deepcopy(row) for row in self._inventory()}.values())

    def candidate(self, key):
        key = str(key or "").strip().upper()
        row = next((row for row in self.inventory() if row["security_key"].upper() == key), None)
        if row is None:
            raise HTTPException(404, "risk_input_security_not_found")
        return row

    @staticmethod
    def identity(candidate):
        return _digest({key: candidate.get(key) for key in ("security_key", "asset_class", "asset_sub_class",
            "issuer_name", "issuer_identity_verified", "isin", "cusip")})

    @staticmethod
    def preference_key(candidate):
        return PREFIX + _digest(candidate["security_key"])

    def _saved(self, candidate):
        saved = self._store().get_preference(self.preference_key(candidate))
        return saved if isinstance(saved, dict) and saved.get("identity_token") == self.identity(candidate) else {}

    def evidence(self, candidate):
        saved = self._store().get_preference(EVIDENCE_PREFIX + _digest(candidate["security_key"]))
        return deepcopy(saved) if isinstance(saved, dict) and saved.get("identity_token") == self.identity(candidate) else {}

    def publish_evidence(self, candidate, records, *, expected_revision=None):
        """Application-only publication of independently validated source facts.

        No public endpoint accepts free-form facts. Research workers submit only
        request-bound source/record IDs; their application finalizer validates
        the fetched source before reaching this method.
        """
        current = self.candidate(candidate["security_key"])
        identity = self.identity(candidate)
        if self.identity(current) != identity:
            raise HTTPException(409, "risk_input_identity_changed")
        evidence_key = EVIDENCE_PREFIX + _digest(candidate["security_key"])
        manual_key = self.preference_key(current)
        def transform(saved):
            manual = saved.get(manual_key) or {}
            if expected_revision is not None and int(manual.get("revision") or 0) != expected_revision:
                raise HTTPException(409, "risk_input_revision_conflict")
            prior = saved.get(evidence_key) or {}
            prior = prior if prior.get("identity_token") == identity else {}
            fields = deepcopy(prior.get("fields") or {})
            for record in records:
                field = record["field"]
                previous = fields.get(field)
                # A new read does not make an older observation newer.
                if previous and (previous.get("as_of") or "") > (record.get("as_of") or ""):
                    continue
                fields[field] = deepcopy(record)
            result = {"identity_token": identity, "fields": fields,
                "revision": int(prior.get("revision") or 0) + 1,
                "updated_at": datetime.now(timezone.utc).isoformat()}
            return {manual_key: saved.get(manual_key), evidence_key: result}
        self._store().update_preferences([manual_key, evidence_key], transform)
        return self.evidence(current)

    def read(self, candidate, *, as_of=None):
        saved = self._saved(candidate)
        evidence = self.evidence(candidate)
        fields = evidence.get("fields") or {}
        researched = {}
        for key,row in fields.items():
            # A literal allocation from an undated/old filing can be retained
            # as evidence without becoming a current economic allocation.
            if row.get("basis") in {"reported_investment_currency", "reported_allocation"}:
                try:
                    observed = date.fromisoformat(row.get("as_of") or "")
                    if not 0 <= (date.today()-observed).days <= 550:
                        continue
                except ValueError:
                    continue
            researched[key] = deepcopy(row.get("value"))
        supplied_params = deepcopy(saved.get("parameters") or {})
        params = {key: value for key, value in researched.items() if key in PARAMETERS}
        params.update(supplied_params)
        market_dates = [supplied_params.get("as_of") if key in supplied_params and (key not in researched or supplied_params[key] != researched[key]) else fields.get(key, {}).get("as_of")
                        for key in ("continuous_yield", "current_spread_bps") if key in params]
        if market_dates:
            # Editing notes/static terms cannot refresh an inherited old yield
            # or spread. Only replacing that exact market field changes its date.
            if all(isinstance(value,str) and value for value in market_dates):
                params["as_of"] = min(market_dates)
            else:
                params.pop("as_of",None)
        country = self._countries(candidate) or {}
        if (country.get("source_kind") == "manual" and "country_code" not in supplied_params
                and params.get("country_basis") == "issuer_domicile_proxy"):
            # A public address is the same domicile axis as this explicit
            # association; it must not silently replace the user's override.
            params.pop("country_code",None)
        code = params.get("country_code")
        if code:
            country = {**country, "country_code": code, "source_kind": "risk_input_assumption" if "country_code" in supplied_params else fields.get("country_code", {}).get("source_kind"),
                       "basis": params.get("country_basis") or "issuer_domicile_proxy"}
        code = country.get("country_code")
        public = self._credit(candidate) or {}
        sovereign = self._sovereign(code) if code else {}
        sovereign_ratings = {basis: select_rating(sovereign, basis=basis, sovereign=True)
                             for basis in ("local_currency", "foreign_currency")}
        sovereign_estimates = {basis: select_rating(sovereign, basis=basis, sovereign=True, allow_manual=True)
                              for basis in ("local_currency", "foreign_currency")}
        credit = select_rating(public, candidate)
        credit_estimate = select_rating(public, candidate, allow_manual=True)
        # Exact independently bound issuer IDs must group every matching
        # holding consistently, regardless of earlier profile coverage.
        issuer_id = researched.get("issuer_id") or (_entity(candidate.get("issuer_name")) if candidate.get("issuer_identity_verified") else None)
        if params.get("instrument_kind") == "sovereign_bond" and code:
            issuer_id = "sovereign:" + code
        basis = params.get("sovereign_currency_basis")
        sovereign_selected = (credit if params.get("instrument_kind") == "sovereign_bond"
                              and credit and credit.get("scope") == "issue" else sovereign_ratings.get(basis))
        sovereign_estimate = (credit_estimate if params.get("instrument_kind") == "sovereign_bond"
                             and credit_estimate and credit_estimate.get("scope") == "issue" else sovereign_estimates.get(basis))
        gaps = []
        if not issuer_id:
            gaps.append({"code": "issuer_identity"})
        if not code:
            gaps.append({"code": "country_exposure"})
        if not params:
            gaps.append({"code": "risk_parameters"})
        return {"model": MODEL, "security_key": candidate["security_key"], "identity_token": self.identity(candidate),
            "revision": int(saved.get("revision") or 0), "parameters": params,
            "local_parameters": supplied_params,
            "researched_parameters": {key:deepcopy(value) for key,value in researched.items() if key in PARAMETERS},
            "parameters_verification": "user_entered" if supplied_params else "verified" if params else "not_available",
            "parameter_provenance": {"source_kind": "user_entered" if supplied_params else "public_source", "verification_status": "user_entered" if supplied_params else "verified", "as_of": params.get("as_of"),
                "source_url": params.get("source_url"), "notes": params.get("notes"),
                "updated_at": saved.get("updated_at")},
            "issuer_id": issuer_id, "issuer_name": candidate.get("issuer_name") or researched.get("issuer_name"),
            "issuer_identity_verified": bool(candidate.get("issuer_identity_verified") or researched.get("issuer_id")),
            "issuer_name_key": _entity(researched.get("issuer_name") or (candidate.get("issuer_name") if candidate.get("issuer_identity_verified") else None)) or None,
            "currency_exposures": deepcopy(researched.get("currency_exposures")),
            "unsupported_bond": researched.get("unsupported_bond") is True,
            "source_evidence": deepcopy(list(fields.values())), "evidence_revision": evidence.get("revision", 0),
            "country": {**country, "basis": params.get("country_basis") or "issuer_domicile_proxy"},
            "credit_rating": credit, "sovereign_ratings": sovereign_ratings,
            "sovereign_rating": sovereign_selected, "country_rating": sovereign_ratings.get("foreign_currency"),
            "credit_rating_estimate": credit_estimate, "sovereign_ratings_estimate": sovereign_estimates,
            "sovereign_rating_estimate": sovereign_estimate, "country_rating_estimate": sovereign_estimates.get("foreign_currency"),
            "as_of": as_of or datetime.now(timezone.utc).date().isoformat(), "gaps": gaps,
            "fingerprint": _digest([self.identity(candidate), saved, evidence, public.get("ratings", []), sovereign.get("ratings", []), country])}

    def update(self, payload, actor, *, clear=False):
        if not isinstance(payload, dict):
            raise HTTPException(422, "risk_input_invalid_request")
        allowed = {"security_key", "expected_identity", "expected_revision"} | (set() if clear else {"parameters"})
        if set(payload) - allowed or type(payload.get("expected_revision")) is not int or payload["expected_revision"] < 0:
            raise HTTPException(422, "risk_input_invalid_request")
        candidate = self.candidate(payload.get("security_key"))
        identity = self.identity(candidate)
        if payload.get("expected_identity") != identity:
            raise HTTPException(409, "risk_input_identity_changed")
        try:
            params = {} if clear else normalize_parameters(payload.get("parameters"))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        def edit(saved):
            saved = saved if isinstance(saved, dict) and saved.get("identity_token") == identity else {}
            revision = int(saved.get("revision") or 0)
            if revision != payload["expected_revision"]:
                raise HTTPException(409, "risk_input_revision_conflict")
            return {"identity_token": identity, "revision": revision + 1, "parameters": params,
                "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": actor.get("id")}
        self._store().update_preference(self.preference_key(candidate), edit)
        return self.read(candidate)

    def enrich(self, items):
        out = deepcopy(items)
        named = any(all((item.get("holding") or {}).get(field) for field in ("symbol", "stock_market", "currency")) for item in out)
        inventory = {row["security_key"]: row for row in self.inventory()} if named else {}
        memo = {}
        for item in out:
            holding = item.get("holding") or {}
            key = security_key(holding)
            candidate = inventory.get(key)
            if candidate:
                if key not in memo:
                    memo[key] = self.read(candidate)
                item["stress_risk"] = deepcopy(memo[key])
            else:
                item["stress_risk"] = {"model": MODEL, "security_key": key, "parameters": {},
                    "gaps": [{"code": "risk_input_security_identity"}]}
        return out

    def revision(self):
        """Separate from valuation cache token, including previously excluded annotations."""
        store = self._store()
        if not hasattr(store, "export_data"):
            return ""
        data = store.export_data().get("data", {})
        preferences = [row for row in data.get("app_preferences", []) if str(row.get("key") or "").startswith(
            (PREFIX, EVIDENCE_PREFIX, "manual-credit-ratings-v1:", "credit-rating-history-v1:", "sovereign-credit-ratings-v1:", "security-country-v1:"))]
        # Public rating service publication retains its canonical snapshot in these
        # preferences. Source annotations do not trigger market-data refetches.
        return _digest([preferences, data.get("security_exposure_profiles", []),
            [(row["security_key"], self.read(row)["fingerprint"]) for row in self.inventory()]])

    def router(self):
        router = APIRouter(tags=["stress risk inputs"])
        def user(request, write=False):
            actor = getattr(request.state, "auth_user", None)
            if not isinstance(actor, dict):
                raise HTTPException(401, "authentication_required")
            if write and actor.get("role") not in {"Admin", "Operator"}:
                raise HTTPException(403, "read_only")
            return actor
        @router.get("/api/securities/risk-inputs")
        def read(request: Request, symbol: str, stock_market: str, currency: str):
            user(request)
            return self.read(self.candidate("|".join((symbol, stock_market, currency))))
        @router.put("/api/securities/risk-inputs")
        def update(request: Request, payload: dict):
            return self.update(payload, user(request, True))
        @router.delete("/api/securities/risk-inputs")
        def clear(request: Request, payload: dict):
            return self.update(payload, user(request, True), clear=True)
        return router
