"""Local sovereign opinions, manual overlays, history and bounded public AI.

The security-shaped keys are an internal adapter to the existing research job
coordinator. No company rating, portfolio value or risk formula is modified.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re

from fastapi import APIRouter, HTTPException, Query, Request

from . import credit_rating_history as history
from .credit_rating_service import CreditRatingService, _now, _stamp, select_observation
from .credit_ratings import _entity, _url, normalize_grade
from .manual_credit_ratings import _date, _text
from .security_enrichment import EnrichmentJobs, WEB_RESEARCH_POLICY
from .security_research_tools import ResearchFailure, search_query_matches_identity
from .security_search import SearchFailure, search_is_configured
from .us_market_providers import ProviderFailure
from .sovereign_ratings import (AGENCIES, CURRENCY_BASES, COUNTRIES, SOURCE_LEADS,
    binding, country_descriptor, extract_rating_records, normalize_country,
    normalize_observation, slot, source_authority)

PREFIX = "/api/countries/credit-ratings"
SCHEMA = "sovereign-credit-ratings-v1"
POLICY = WEB_RESEARCH_POLICY + (
    " This task is SOVEREIGN COUNTRY CREDIT RATINGS, not company ratings or prices. "
    "Research Moody's, S&P Global Ratings and Fitch independently for the exact supplied country. "
    "Keep long-term global sovereign issuer ratings distinct from company, bank, bond issue, "
    "country ceiling, short-term and national-scale ratings. Local-currency and foreign-currency "
    "opinions are separate; only assign both when the source explicitly states both. "
    "Unknown ratings, outlooks, watches and action dates must stay unknown, not Not Rated or Stable. "
    "Read official agency or verified government debt sources; snippets and remembered facts are not evidence. "
    "A source's retrieval date is not an agency action date. Do not infer a country from exchange or currency. "
    "Return records:[{security_key,source_id,record_id}] selecting sovereign_credit_rating context_records "
    "returned by read. Never supply a raw grade or invent a record ID. Keep existing shared request limits."
)
MANUAL_FIELDS = {"country_code", "country_key", "security_key", "agency", "currency_basis", "status", "rating",
    "outlook", "watch", "entity_name", "rating_date", "outlook_date", "watch_date", "source_url", "notes",
    "scope", "scale", "term", "expected_revision", "expected_identity"}


def _axis_key(agency, basis):
    return agency + ":" + basis


def _select(rows, candidate):
    # Company selector is safe only after partitioning by sovereign currency
    # basis; include_ancillary avoids pretending sovereign is a company issuer.
    return select_observation(rows, candidate, include_ancillary=True)


def _latest(retained, row):
    scoped = {**retained, "events": [event for event in retained.get("events", [])
        if event.get("agency") == row.get("agency") and event.get("currency_basis") == row.get("currency_basis")]}
    return history.latest_change(scoped, row)


class SovereignRatingService(CreditRatingService):
    """Use the existing research session and merge rules with separate stores."""

    def candidate(self, key):
        code = normalize_country(str(key).removeprefix("COUNTRY:"))
        return next((deepcopy(item) for item in self._inventory() if item.get("country_code") == code), None)

    def _keys(self, candidate):
        identity = binding(candidate)
        root = SCHEMA + ":" + candidate["country_key"] + ":" + identity
        return root + ":manual", root + ":history", identity

    def _manual(self, candidate, saved=None):
        key, _, identity = self._keys(candidate)
        if saved is None:
            saved = self._manual_store().get_preference(key) if self._manual_store else self._history_memory.get(key)
        if not isinstance(saved, dict) or saved.get("identity_token") != identity:
            saved = {"identity_token": identity, "records": {}, "revisions": {}}
        return deepcopy(saved)

    def _retained(self, candidate, saved=None):
        _, key, identity = self._keys(candidate)
        if saved is None:
            saved = self._manual_store().get_preference(key) if self._manual_store else self._history_memory.get(key)
        return history.snapshot(saved, identity)

    def _public(self, candidate, retained):
        saved = retained.get("public_snapshot")
        if not isinstance(saved, dict):
            saved = self._cache().get_security_snapshot("sovereign_credit_ratings", candidate["country_key"], SCHEMA)
        return deepcopy(saved) if isinstance(saved, dict) and saved.get("_binding") == binding(candidate) else {}

    def _record(self, candidate, retained, public, stamp):
        result = history.record_public(retained, public.get("observations", []), lambda rows: _select(rows, candidate), stamp)
        result["public_snapshot"] = deepcopy(public)
        return result

    def read(self, candidate):
        with self._lock:
            retained = self._retained(candidate)
            public = self._public(candidate, retained)
            manual = self._manual(candidate)
        now = datetime.now(timezone.utc)
        ttl = timedelta(days=max(1, int(self._settings().get("verification_ttl_days", 30))))
        retrieved, effective, manual_rows, revisions = [], [], [], {}
        for agency in AGENCIES:
            for basis in CURRENCY_BASES:
                axis = _axis_key(agency, basis)
                selected = _select([row for row in public.get("observations", [])
                    if row.get("agency") == agency and row.get("currency_basis") == basis], candidate)
                row = {**slot(agency, basis), **(selected or {})}
                attempt = public.get("attempts", {}).get(agency)
                if selected and row["status"] in history.KNOWN:
                    row["reason_code"] = {"rated": "data_found", "unrated": "explicitly_unrated", "withdrawn": "withdrawn"}[row["status"]]
                if attempt:
                    row["checked_at"] = attempt["checked_at"]
                    if not selected:
                        row.update(status="unavailable", reason_code=attempt["reason_code"])
                stamp = _stamp(row.get("fetched_at"))
                row["stale"] = bool(stamp and now - stamp > ttl)
                for field in ("outlook", "watch"):
                    signal_stamp = _stamp(row.get(field + "_fetched_at") or row.get("fetched_at"))
                    row[field + "_stale"] = bool(row.get(field) not in {None, "unknown"} and signal_stamp and now - signal_stamp > ttl)
                row["forward_signal_stale"] = row["outlook_stale"] or row["watch_stale"]
                row["latest_change"] = _latest({**retained, "events": [e for e in retained["events"] if e.get("origin") == "public_ai"]}, row)
                retrieved.append(row)
                revision = int(manual["revisions"].get(axis, 0))
                revisions[axis] = revision
                overlay = deepcopy(manual["records"].get(axis))
                if overlay:
                    entered = _stamp(overlay.get("updated_at"))
                    overlay.update(manual_revision=revision, stale=bool(entered and now - entered > ttl))
                    overlay["latest_change"] = _latest(retained, overlay)
                    manual_rows.append(overlay)
                    effective.append(overlay)
                else:
                    effective.append({**deepcopy(row), "manual_revision": revision, "latest_change": _latest(retained, row)})
        known_agencies = {row["agency"] for row in effective if row["status"] in history.KNOWN}
        return {"schema_version": SCHEMA, **{key: candidate[key] for key in ("country_key", "country_code", "country_name", "security_key")},
            "status": "ok" if len(known_agencies) == 3 else "partial" if known_agencies else "unavailable",
            "ratings": effective, "retrieved_ratings": retrieved, "manual_ratings": manual_rows,
            "manual_revisions": revisions, "identity_token": manual["identity_token"],
            "manual_policy": {"scope": "sovereign", "scale": "global", "term": "long_term",
                "currency_bases": list(CURRENCY_BASES), "country_identity_verified": True},
            "rating_history": sorted(deepcopy(retained["events"]), key=lambda row: row["detected_at"], reverse=True),
            "retrieval_mode": "public_ai", "provider_status": [], "fetched_at": public.get("fetched_at")}

    def summaries(self, codes):
        if len(codes) > 249 or any(not isinstance(code, str) or not normalize_country(code) for code in codes):
            raise HTTPException(422, "invalid_country_codes")
        requested = list(dict.fromkeys(normalize_country(code) for code in codes))
        items, missing = [], []
        for code in requested:
            candidate = self.candidate(code)
            if candidate:
                response = self.read(candidate)
                response.pop("rating_history", None)
                for collection in ("ratings", "retrieved_ratings", "manual_ratings"):
                    for row in response[collection]:
                        row.pop("evidence_quote", None)
                        row.pop("observations", None)
                        row["sources"] = [{k: v for k, v in source.items() if k != "evidence_quote"} for source in row.get("sources", [])]
                        row["latest_change"] = history.compact_change(row.get("latest_change"))
                items.append(response)
            else:
                missing.append(code)
        return {"items": items, "not_found_codes": missing, "summary_only": True}

    @staticmethod
    def _preconditions(payload):
        if not isinstance(payload, dict) or set(payload) - MANUAL_FIELDS:
            raise HTTPException(422, "manual_invalid_fields")
        agency, basis = payload.get("agency"), payload.get("currency_basis")
        if agency not in AGENCIES:
            raise HTTPException(422, "manual_invalid_agency")
        if basis not in CURRENCY_BASES:
            raise HTTPException(422, "manual_invalid_currency_basis")
        revision, identity = payload.get("expected_revision"), payload.get("expected_identity")
        if type(revision) is not int or revision < 0:
            raise HTTPException(422, "manual_invalid_revision")
        if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{64}", identity):
            raise HTTPException(422, "manual_invalid_identity")
        return agency, basis, revision, identity

    @staticmethod
    def _normalize_manual(payload, candidate):
        status = _text(payload, "status", 12, required=True)
        if status not in history.KNOWN:
            raise ValueError("manual_invalid_status")
        if any(payload.get(field, expected) != expected for field, expected in (("scope", "sovereign"), ("scale", "global"), ("term", "long_term"))):
            raise ValueError("manual_invalid_scope")
        entity = _text(payload, "entity_name", 300) or candidate["country_name"]
        if _entity(entity) not in {_entity(name) for name in [candidate["country_name"], *candidate.get("country_aliases", [])]}:
            raise ValueError("manual_invalid_entity")
        raw = _text(payload, "rating", 80)
        try:
            grade = normalize_grade(raw, payload["agency"]) if status == "rated" else None
        except ValueError as exc:
            raise ValueError("manual_invalid_rating") from exc
        if status != "rated" and raw:
            raise ValueError("manual_invalid_rating")
        outlook = _text(payload, "outlook", 12) or "unknown"
        watch = _text(payload, "watch", 12) or "unknown"
        if outlook not in {"unknown", "positive", "negative", "stable", "developing"}:
            raise ValueError("manual_invalid_outlook")
        if watch not in {"unknown", "none", "positive", "negative", "developing"}:
            raise ValueError("manual_invalid_watch")
        if status != "rated" and (outlook != "unknown" or watch != "unknown"):
            raise ValueError("manual_invalid_forward_status")
        source = _text(payload, "source_url", 2500)
        notes = _text(payload, "notes", 1000)
        if not source and not notes:
            raise ValueError("manual_source_required")
        if source:
            try:
                source = _url(source)
            except ValueError as exc:
                raise ValueError("manual_invalid_source_url") from exc
        dates = {key: _date(payload, key) for key in ("rating_date", "outlook_date", "watch_date")}
        if dates["outlook_date"] and outlook == "unknown" or dates["watch_date"] and watch == "unknown":
            raise ValueError("manual_invalid_date")
        return {**slot(payload["agency"], payload["currency_basis"]), "status": status, "rating": grade,
            "rating_raw": grade, "entity_name": candidate["country_name"], "entity_id": candidate["country_code"],
            "country_code": candidate["country_code"], "outlook": outlook, "watch": watch, **dates,
            "source_url": source or None, "notes": notes, "manual_override": True, "source_kind": "manual",
            "verification_status": "user_entered", "identity_verification": "country_identity_verified",
            "staleness_basis": "manual_updated_at", "reason_code": "manual_entry", "observed_at": None,
            "sources": [{"url": source, "source_kind": "manual", "verification_status": "user_entered"}] if source else []}

    def save_manual(self, payload, actor):
        return self._edit_manual(payload, actor)

    def clear_manual(self, key, agency, currency_basis, expected_revision, expected_identity, actor=None):
        return self._edit_manual({"country_code": key, "agency": agency, "currency_basis": currency_basis,
            "expected_revision": expected_revision, "expected_identity": expected_identity}, actor or {}, clearing=True)

    def _edit_manual(self, payload, actor, clearing=False):
        if not self._manual_store:
            raise HTTPException(503, "manual_rating_store_unavailable")
        agency, basis, expected_revision, expected_identity = self._preconditions(payload)
        candidate = self.candidate(payload.get("country_code") or payload.get("country_key") or payload.get("security_key"))
        if not candidate:
            raise HTTPException(404, "country_not_found")
        with self._lock:
            current = self.candidate(candidate["country_key"])
            if not current or binding(current) != binding(candidate) or expected_identity != binding(current):
                raise HTTPException(409, "country_identity_changed")
            manual_key, history_key, _ = self._keys(current)
            axis = _axis_key(agency, basis)
            def edit(values):
                manual = self._manual(current, values[manual_key])
                revision = int(manual["revisions"].get(axis, 0))
                if revision != expected_revision:
                    raise HTTPException(409, "manual_rating_conflict")
                retained = self._retained(current, values[history_key])
                public = self._public(current, retained)
                stamp = _now()
                retained = self._record(current, retained, public, stamp)
                previous = manual["records"].get(axis)
                public_row = _select([row for row in public.get("observations", [])
                    if row.get("agency") == agency and row.get("currency_basis") == basis], current) or slot(agency, basis)
                if clearing:
                    manual["records"].pop(axis, None)
                    after = public_row
                else:
                    try:
                        after = self._normalize_manual(payload, current)
                    except ValueError as exc:
                        raise HTTPException(422, str(exc)) from exc
                    after.update(revision=revision + 1, created_at=(previous or {}).get("created_at") or stamp,
                        updated_at=stamp, updated_by=str(actor.get("username") or actor.get("id") or ""))
                    manual["records"][axis] = after
                manual["revisions"][axis] = revision + 1
                if not clearing or previous:
                    retained = history.record_manual(retained, previous or public_row, after, stamp,
                        actor=str(actor.get("username") or actor.get("id") or ""), clearing=clearing)
                return {manual_key: manual, history_key: retained}
            self._update_preferences([manual_key, history_key], edit)
            return self.read(current)

    def _accept_sources(self, candidate, sources):
        accepted = []
        for source in sources:
            for record in extract_rating_records(source, candidate):
                try:
                    accepted.append(normalize_observation(record, candidate, source=source))
                except ValueError:
                    pass
        return accepted

    def publish(self, candidate, observations, provider_status=None, *, started_at=None):
        with self._lock:
            current = self.candidate(candidate["country_key"])
            if not current or binding(candidate) != binding(current) or candidate.get("_position_scope") == "open" and not current.get("has_open_position"):
                return False
            _, key, _ = self._keys(current)
            changed = False
            def edit(values):
                nonlocal changed
                retained = self._retained(current, values[key])
                previous = self._public(current, retained)
                stamp = _now()
                retained = self._record(current, retained, previous, stamp)
                accepted, changed = self._merge_public(previous, observations, started_at)
                public = {"schema_version": SCHEMA, "_binding": binding(current), "observations": accepted,
                    "fetched_at": stamp if changed else previous.get("fetched_at"), "attempts": previous.get("attempts", {})}
                return {key: self._record(current, retained, public, stamp)}
            updated = self._update_preferences([key], edit)
            self._cache().set_security_snapshot("sovereign_credit_ratings", current["country_key"], SCHEMA, updated[key]["public_snapshot"])
            return changed

    def record_attempt(self, candidate, agencies, reason_code):
        with self._lock:
            current = self.candidate(candidate["country_key"])
            if not current or binding(candidate) != binding(current):
                return
            _, key, _ = self._keys(current)
            def edit(values):
                retained = self._retained(current, values[key])
                public = self._public(current, retained)
                stamp = _now()
                public.update(schema_version=SCHEMA, _binding=binding(current))
                for agency in agencies:
                    if agency in AGENCIES:
                        public.setdefault("attempts", {})[agency] = {"checked_at": stamp, "reason_code": reason_code}
                return {key: self._record(current, retained, public, stamp)}
            self._update_preferences([key], edit)

    @staticmethod
    def missing(response):
        return [agency for agency in AGENCIES if not any(row["agency"] == agency and row["status"] in history.KNOWN
            and not row.get("stale") and not row.get("forward_signal_stale") for row in response["retrieved_ratings"])]

    @staticmethod
    def agency_coverage(response):
        known = [agency for agency in AGENCIES if any(row["agency"] == agency and row["status"] in history.KNOWN for row in response["retrieved_ratings"])]
        return {"verified_agencies": known, "agency_statuses": {agency: "rated" if agency in known else "unavailable" for agency in AGENCIES}}

    def candidates(self, position_scope="open", security_keys=None):
        inventory = self.inventory(position_scope, security_keys)[:3]
        items = [{**item, "captured_at": _now(), "_binding": binding(item), "_position_scope": position_scope,
            "missing_fields": ["credit_ratings"], "missing_agencies": list(AGENCIES), "requested_agencies": list(AGENCIES),
            "available_fields": [], "retrieval_mode": "public_ai"} for item in inventory]
        settings = self._research_settings()
        return {"items": items, "total_count": len(items), "truncated": False,
            "research_available": search_is_configured(settings), "configured_search_providers": ["yahoo", "duckduckgo"],
            "preflight_outcomes": [{**item, "status": "unavailable", "code": "data_unavailable", "research_eligible": True,
                                    "provider_status": [], **self.agency_coverage(self.read(item))} for item in items]}

    def research_tool(self, candidate, action, arguments):
        current = self.candidate(candidate["country_key"])
        if not current or binding(candidate) != binding(current) or candidate.get("_position_scope") == "open" and not current.get("has_open_position"):
            return {"evidence": [], "source_status": "not_open"}
        session = self._session(candidate)
        before = session.budget.used
        try:
            if action == "discover":
                leads = list(SOURCE_LEADS.get(current["country_code"], []))
                for row in self.read(current)["retrieved_ratings"]:
                    leads += [source["url"] for source in row.get("sources", []) if source.get("url")]
                sources = [{"source_id": session._add(current["security_key"], url, "Official sovereign rating discovery lead"),
                    "url": url, "title": "Official sovereign rating discovery lead", "discovery_only": True} for url in dict.fromkeys(leads)]
                return {"sources": sources[:8], "evidence": [], "source_status": "sources_found", "web_requests": session.budget.used}
            if action == "search":
                query = arguments["query"]
                if not search_query_matches_identity(query, candidate):
                    query = candidate["country_name"] + " " + query
                return {**session.search(candidate, query, provider=arguments.get("provider", "auto")),
                        "evidence": [], "source_status": "search_results", "web_requests": session.budget.used}
            if action == "read":
                source = session.read(candidate, arguments["source_id"], reader=arguments.get("reader"))
            elif action == "follow":
                source = session.follow(candidate, arguments["source_id"], arguments["link_id"], reader=arguments.get("reader"))
            else:
                raise ResearchFailure("invalid_request", "Invalid research operation.")
            records = []
            for row in extract_rating_records(source, candidate):
                try:
                    normalize_observation(row, candidate, source=source)
                    records.append(row)
                except ValueError:
                    pass
            source.update(source_authority=source_authority(source, candidate) or "unverified", context_records=records)
            return {"evidence": [source], "source_status": "evidence_found", "diagnostics": dict(session.diagnostics), "web_requests": session.budget.used}
        except (ResearchFailure, SearchFailure, ProviderFailure, ValueError, OSError, TimeoutError) as exc:
            return {"evidence": [], "source_status": getattr(exc, "code", "source_read_failed"),
                    "diagnostics": dict(session.diagnostics), "web_requests": session.budget.used}
        finally:
            if session.budget.used > before:
                self._research_attempts.setdefault(str(candidate.get("_request_id") or ""), set()).add(candidate["security_key"])

    def finalize(self, outcomes, user_id, request_id, *, proposal=None, evidence_by_key=None, candidates=None, **kwargs):
        from .security_web_research import parse_research_proposal
        parsed = parse_research_proposal(proposal) or {}
        choices = parsed.get("records") or []
        selected = {(row["security_key"], row["source_id"], row["record_id"]) for row in choices[:30]
            if isinstance(row, dict) and set(row) == {"security_key", "source_id", "record_id"} and all(isinstance(value, str) for value in row.values())}
        finalized = []
        for key, candidate in (candidates or {}).items():
            current = self.candidate(key)
            if not current or binding(current) != binding(candidate) or candidate.get("_position_scope") == "open" and not current.get("has_open_position"):
                finalized.append({**candidate, "status": "not_attempted", "code": "not_open", "attempted": False,
                    "available_fields": [], "missing_fields": []})
                continue
            accepted = []
            for source in (evidence_by_key or {}).get(key, []):
                for record in extract_rating_records(source, candidate):
                    if (key, source.get("source_id"), record["record_id"]) in selected:
                        try:
                            accepted.append(normalize_observation(record, candidate, source=source))
                        except ValueError:
                            pass
            changed = bool(accepted and self.publish(candidate, accepted, started_at=candidate.get("captured_at")))
            attempted = bool(accepted or (evidence_by_key or {}).get(key) or key in self._research_attempts.get(request_id, set()))
            if attempted:
                self.record_attempt(candidate, AGENCIES, "data_found" if accepted else "evidence_rejected" if selected else "data_unavailable")
            response = self.read(candidate)
            missing = self.missing(response)
            known = any(row["status"] in history.KNOWN for row in response["retrieved_ratings"])
            status = "not_attempted" if not attempted else "updated" if changed and not missing else "partial" if known else "unavailable"
            outcome = {**candidate, "status": status, "attempted": attempted,
                "code": "research_incomplete" if not attempted else "data_found" if status == "updated" else "partial_data" if known else "data_unavailable",
                "available_fields": ["credit_ratings"] if known else [], "missing_fields": ["credit_ratings"] if missing else [],
                "missing_agencies": missing, "last_attempted_at": _now(), "retrieval_mode": "public_ai", **self.agency_coverage(response)}
            finalized.append(outcome)
            with self._lock:
                self._outcomes[key] = deepcopy(outcome)
        return finalized

    def manager(self, app, assistant_settings, *, event_writer=None, worker_factory=None):
        options = {} if worker_factory is None else {"worker_factory": worker_factory}
        return EnrichmentJobs(app, assistant_settings, candidate_reader=self.candidates,
            security_fetcher=lambda *_: {"evidence": [], "source_status": "data_unavailable"},
            outcome_reader=self.outcome_reader, outcome_writer=self.finalize,
            source_hint_reader=lambda candidate: self.research_tool(candidate, "discover", {}).get("sources", []),
            research_tool_fetcher=self.research_tool, prefix=PREFIX, research_policy=POLICY,
            research_metadata={"country_code", "country_name", "country_key", "missing_agencies", "requested_agencies", "captured_at"},
            discovery_subject="sovereign country credit ratings Moody's S&P Fitch long-term outlook",
            refresh_portfolio_on_update=False, selection_reader=True, event_writer=event_writer, **options)

    def router(self):
        router = APIRouter(tags=["sovereign credit ratings"])
        def actor(request, editing=False):
            user = getattr(request.state, "auth_user", None)
            if not isinstance(user, dict):
                raise HTTPException(401, "authentication_required")
            if editing and user.get("role") not in {"Admin", "Operator"}:
                raise HTTPException(403, "read_only")
            return user

        @router.get(PREFIX + "/catalog")
        def catalog(request: Request):
            actor(request)
            return {"items": [{"country_code": row["code"], "country_name": row["name"]} for row in COUNTRIES]}

        @router.get(PREFIX + "/summaries")
        def summaries(request: Request, country_codes: list[str] = Query(default=[])):
            actor(request)
            return self.summaries(country_codes)

        @router.get(PREFIX)
        def read(request: Request, country_code: str):
            actor(request)
            candidate = self.candidate(country_code)
            if not candidate:
                raise HTTPException(404, "country_not_found")
            return self.read(candidate)

        @router.put(PREFIX + "/manual")
        def save_manual(request: Request, payload: dict):
            return self.save_manual(payload, actor(request, True))

        @router.delete(PREFIX + "/manual")
        def clear_manual(request: Request, country_code: str, agency: str, currency_basis: str,
                         expected_revision: int = Query(ge=0), expected_identity: str = Query(min_length=64, max_length=64)):
            return self.clear_manual(country_code, agency, currency_basis, expected_revision, expected_identity, actor(request, True))

        return router
