"""Application-owned public-AI credit evidence, manual overrides and history.

The AI coordinator receives only the fixed REST tools. This application layer
owns inventory, public-source reads, evidence validation and cache publication.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from threading import RLock
from typing import Callable
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query, Request

from . import credit_rating_history as history
from .security_enrichment import EnrichmentJobs, WEB_RESEARCH_POLICY, security_key
from .security_research_tools import ResearchSession, ResearchFailure, WebRequestBudget, search_query_matches_identity
from .security_search import SearchFailure, search_is_configured
from .us_market_providers import ProviderFailure
from .manual_credit_ratings import (
    MANUAL_SCHEMA, manual_identity, manual_policy, manual_preconditions, normalize_manual, preference_key,
)

PREFIX = "/api/securities/credit-ratings"
SCHEMA = "credit-ratings-v1"
AGENCIES = ("moodys", "sp", "fitch")
SUMMARY_FIELDS = frozenset({
    "agency", "status", "reason_code", "rating", "rating_raw", "scope", "scale", "term", "rating_type",
    "entity_name", "entity_id", "rating_date", "outlook", "watch", "outlook_date", "watch_date",
    "observed_at", "fetched_at", "checked_at", "stale", "outlook_stale", "watch_stale", "forward_signal_stale",
    "outlook_fetched_at", "watch_fetched_at", "forward_signal_checked_at", "issuer_fallback", "primary_eligible",
    "record_id", "source_url", "source_kind", "action_type", "snapshot_kind", "currency_basis",
    "manual_override", "manual_revision", "revision", "verification_status", "identity_verification",
    "created_at", "updated_at", "updated_by", "staleness_basis",
    "latest_change",
})

# Verified official issuer namespaces are discovery leads only, just like the
# existing TASE and issuer-document hints. Each refresh must actually read the
# page and validate its exact legal entity; the catalog contains no ratings.
ISSUER_SOURCES = (
    ("JPMorgan Chase & Co.", "https://www.jpmorganchase.com/ir/fixed-income"),
    ("Electricite de France", "https://www.edf.fr/en/the-edf-group/dedicated-sections/investors/debt/ratings"),
    ("Electricité de France", "https://www.edf.fr/en/the-edf-group/dedicated-sections/investors/debt/ratings"),
    ("EDF", "https://www.edf.fr/en/the-edf-group/dedicated-sections/investors/debt/ratings"),
    ("UBS Group AG", "https://www.ubs.com/global/en/investor-relations/investors/bondholder-information/ratings.html"),
)

# Agency action pages are discovery leads, never issuer-owned domains or stored
# grades. The normal bounded read must independently establish every fact.
AGENCY_SOURCE_LEADS = (
    ("Fidus Investment Corporation", "https://www.fitchratings.com/research/corporate-finance/fitch-affirms-fidus-investment-corporation-at-bbb-outlook-stable-15-10-2026"),
    ("Fidus Investment Corp", "https://www.fitchratings.com/research/corporate-finance/fitch-affirms-fidus-investment-corporation-at-bbb-outlook-stable-15-10-2026"),
    ("Barings BDC, Inc.", "https://www.fitchratings.com/entity/barings-bdc-inc-96883397"),
    ("Barings BDC, Inc.", "https://www.fitchratings.com/research/corporate-finance/fitch-affirms-barings-bdc-at-bbb-outlook-stable-10-07-2026"),
)

POLICY = WEB_RESEARCH_POLICY + (
    " This task is COMPANY CREDIT RATINGS, not prices, stock recommendations or financial-ratio scores. "
    "Research Moody's, S&P Global Ratings and Fitch independently for the exact supplied legal issuer or bond issue. "
    "Include the exact supplied registered symbol in every search query, together with the requested issuer and rating fields. "
    "Find agency credit rating, outlook and review/watch independently; never assume Stable or Not Rated from absence. "
    "Prefer current official agency statements or issuer investor-relations debt/credit-rating tables. "
    "Parent companies, banks and subsidiaries can have different ratings. Never transfer one entity's rating to another. "
    "A bond's exact issue rating differs from issuer, senior unsecured class, deposit, CFR, short-term or national-scale ratings. "
    "Use the existing shared budgets; a single issuer table may establish several agencies. "
    "Read the actual source. Search snippets, remembered grades and analyst buy/sell recommendations are not evidence. "
    "A page marked source_authority=unverified is a discovery lead; use its links or another official source, not an unsupported rating claim. "
    "Source dates may be absent: retrieval time is never the rating-action date. Outlook is an agency opinion, not a forecast grade. "
    "Return records:[{security_key,source_id,record_id}] selecting credit_rating context_records actually returned by read. "
    "Do not invent record IDs or raw grades. If a useful source has no compatible records, use a remaining source/read within the same limits. "
    "Keep every agency/source independently supported and leave unverifiable fields unknown."
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _stamp(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _binding(candidate):
    fields = {k: str(candidate.get(k) or "").strip() for k in
              ("symbol", "secondary_symbol", "isin", "cusip", "stock_market", "currency", "asset_class", "asset_sub_class",
               "name", "issuer_name", "legal_entity_name", "issuer_aliases", "verified_issuer_domains")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def _slot(agency):
    return {"agency": agency, "status": "not_checked", "reason_code": "not_checked",
        "rating": None, "scope": None, "scale": None, "term": None, "rating_type": None,
        "entity_name": None, "entity_id": None, "rating_date": None,
        "outlook": "unknown", "watch": "unknown", "outlook_date": None, "watch_date": None,
        "observed_at": None, "fetched_at": None, "source_url": None, "sources": [], "stale": False}


def _axes(row):
    from .credit_ratings import _entity
    # Agency-vendor IDs are provenance, not separate legal entities. Literal
    # legal names remain exact after punctuation/diacritic normalization.
    return (_entity(row.get("entity_name")),) + tuple(row.get(k) for k in
        ("scope", "scale", "term", "rating_type", "currency_basis"))


def select_observation(rows, candidate, *, include_ancillary=False):
    """Select a display opinion without merging unlike debt/entity classes."""
    if not rows:
        return None
    from .credit_ratings import is_primary_observation
    all_rows = rows
    rows = rows if include_ancillary else [row for row in rows if is_primary_observation(row, candidate)]
    if not rows:
        return {**_slot(all_rows[0]["agency"]), "status": "unavailable", "reason_code": "primary_rating_unavailable",
                "observations": all_rows, "sources": [source for row in all_rows for source in row.get("sources", [])]}
    bond = "BOND" in {str(candidate.get(k) or "").upper() for k in ("asset_class", "asset_sub_class")}
    desired = "issue" if bond else "issuer"
    def priority(row):
        kind = str(row.get("rating_type") or "").casefold()
        primary = any(x in kind for x in ("issuer", "idr", "long-term", "long term"))
        return (row.get("scope") == desired, row.get("scale") == "global", row.get("term") == "long_term", primary)
    best = max(priority(row) for row in rows)
    eligible = [r for r in rows if priority(r) == best]
    latest = sorted(eligible, key=lambda r: (r.get("rating_date") or "", r.get("fetched_at") or ""), reverse=True)[0]
    same_axis = [row for row in eligible if _axes(row) == _axes(latest)]
    def conflict():
        return {**_slot(latest["agency"]), "status": "conflicting", "reason_code": "conflicting_evidence",
                "entity_name": latest.get("entity_name"), "scope": latest.get("scope"), "observations": all_rows,
                "sources": [source for row in same_axis for source in row.get("sources", [])]}
    # Only the exact same rating axis can conflict. Undated statements cannot
    # silently be discarded as older merely because another source has a date.
    for other in same_axis:
        incompatible = other.get("status") != latest.get("status") or other.get("rating") != latest.get("rating")
        if incompatible and (not other.get("rating_date") or not latest.get("rating_date")
                             or other["rating_date"] == latest["rating_date"]):
            return conflict()
    selected = deepcopy(latest)
    sources = deepcopy(selected.get("sources", []))
    for field in ("outlook", "watch"):
        signals = [row for row in same_axis if row.get("status") == selected.get("status") == "rated"
                   and row.get("rating") == selected.get("rating") and row.get(field) not in {None, "unknown"}]
        if not signals:
            selected.update({field: "unknown", field + "_date": None})
            continue
        chosen = max(signals, key=lambda row: (row.get(field + "_date") or "", row.get("fetched_at") or ""))
        for other in signals:
            if other[field] != chosen[field] and (not other.get(field + "_date") or not chosen.get(field + "_date")
                    or other[field + "_date"] == chosen[field + "_date"]):
                return conflict()
        selected[field] = chosen[field]
        selected[field + "_date"] = chosen.get(field + "_date")
        selected[field + "_fetched_at"] = chosen.get(field + "_fetched_at") or chosen.get("fetched_at")
        sources.extend({**source, "fields": [field]} for source in chosen.get("sources", []))
    selected["sources"] = list({(source["url"], source.get("fetched_at"), source.get("evidence_quote"),
                                 tuple(source.get("fields", []))): source for source in sources}.values())
    return {**selected, "issuer_fallback": bool(bond and latest.get("scope") != "issue"), "observations": all_rows}


class CreditRatingService:
    def __init__(self, *, cache: Callable, settings: Callable, inventory: Callable,
                 research_settings: Callable, api_transport=None, manual_store: Callable | None = None):
        self._cache, self._settings, self._inventory = cache, settings, inventory
        self._research_settings = research_settings
        self._api_transport = api_transport
        self._manual_store = manual_store
        self._lock = RLock()
        self._sessions = {}
        self._api_status = {}
        self._outcomes = {}
        self._history_memory = {}
        self._research_attempts = {}

    def candidate(self, key):
        return next((item for item in self._inventory() if item["security_key"] == key), None)

    def inventory(self, position_scope="open", security_keys=None):
        """Full cache-only scope for explicit bounded child scheduling."""
        if position_scope not in {"open", "all"}:
            raise HTTPException(422, "invalid_position_scope")
        items = self._inventory()
        if position_scope == "open":
            items = [item for item in items if item.get("has_open_position")]
        if security_keys:
            selected = set(security_keys)
            items = [item for item in items if item["security_key"] in selected]
        return list({item["security_key"]: deepcopy(item) for item in items}.values())

    def _manual_snapshot(self, candidate):
        identity = manual_identity(candidate, _binding(candidate))
        saved = self._manual_store().get_preference(preference_key(candidate, identity)) if self._manual_store else None
        return self._manual_value(candidate, saved)

    @staticmethod
    def _manual_value(candidate, saved):
        identity = manual_identity(candidate, _binding(candidate))
        if not isinstance(saved, dict) or saved.get("identity_token") != identity or saved.get("schema_version") != MANUAL_SCHEMA:
            saved = {"schema_version": MANUAL_SCHEMA, "identity_token": identity, "records": {}, "revisions": {}}
        return deepcopy(saved)

    def _history_key(self, candidate):
        return history.preference_key(candidate["security_key"], manual_identity(candidate, _binding(candidate)))

    def _history_value(self, candidate, saved):
        return history.snapshot(saved, manual_identity(candidate, _binding(candidate)))

    def _history_snapshot(self, candidate):
        key = self._history_key(candidate)
        saved = self._manual_store().get_preference(key) if self._manual_store else self._history_memory.get(key)
        return self._history_value(candidate, saved)

    def _update_preferences(self, keys, transform):
        if self._manual_store:
            return self._manual_store().update_preferences(keys, transform)
        current = {key: deepcopy(self._history_memory.get(key)) for key in keys}
        changed = transform(current)
        self._history_memory.update(deepcopy(changed))
        return changed

    def _public_snapshot(self, candidate, retained=None):
        retained = self._history_snapshot(candidate) if retained is None else retained
        durable = retained.get("public_snapshot")
        if isinstance(durable, dict) and durable.get("_binding") == _binding(candidate):
            return deepcopy(durable)
        cached = self._cache().get_security_snapshot("credit_ratings", candidate["security_key"], SCHEMA)
        return deepcopy(cached) if isinstance(cached, dict) and cached.get("_binding") == _binding(candidate) else {}

    @staticmethod
    def _agency_rows(candidate, public):
        return {agency: select_observation([row for row in public.get("observations", []) if row.get("agency") == agency], candidate)
                or _slot(agency) for agency in AGENCIES}

    def _record_public(self, candidate, retained, public, stamp):
        retained = history.record_public(retained, public.get("observations", []),
            lambda rows: select_observation(rows, candidate, include_ancillary=True), stamp)
        retained["public_snapshot"] = deepcopy(public)
        return retained

    def read(self, candidate):
        """Cache-only read; retain original agency dates and provenance."""
        key = candidate.get("security_key") or security_key(candidate)
        with self._lock:
            retained = self._history_snapshot(candidate)
            saved = self._public_snapshot(candidate, retained)
            manual = self._manual_snapshot(candidate)
        matching = isinstance(saved, dict) and saved.get("_binding") == _binding(candidate)
        observations = saved.get("observations", []) if matching else []
        rows = []
        ttl = max(1, int(self._settings().get("verification_ttl_days", 30)))
        now = datetime.now(timezone.utc)
        def freshness(original):
            row = deepcopy(original)
            checked = _stamp(row.get("fetched_at"))
            row["stale"] = bool(checked and now - checked > timedelta(days=ttl))
            for field in ("outlook", "watch"):
                verified = _stamp(row.get(field + "_fetched_at") or row.get("fetched_at"))
                row[field + "_stale"] = bool(row.get(field) not in {None, "unknown"} and verified
                    and now - verified > timedelta(days=ttl))
            row["forward_signal_stale"] = row["outlook_stale"] or row["watch_stale"]
            return row
        for agency in AGENCIES:
            selected = select_observation([r for r in observations if r.get("agency") == agency], candidate)
            row = {**_slot(agency), **(deepcopy(selected) if selected else {})}
            if selected and row["status"] in {"rated", "unrated", "withdrawn"}:
                row["reason_code"] = {"unrated": "explicitly_unrated", "withdrawn": "withdrawn"}.get(row["status"], "data_found")
            attempt = saved.get("attempts", {}).get(agency, {}) if matching else {}
            if attempt:
                row["checked_at"] = attempt.get("checked_at")
                if not selected:
                    row.update(status="unavailable", reason_code=attempt.get("reason_code", "data_unavailable"))
            row = freshness(row)
            if "observations" in row:
                row["observations"] = [freshness(item) for item in row["observations"]]
            row["latest_change"] = history.latest_change(retained, row, include_manual=False)
            rows.append(row)
        retrieved = rows
        effective, manual_rows, revisions = [], [], {}
        for row in retrieved:
            agency = row["agency"]
            revisions[agency] = int(manual.get("revisions", {}).get(agency, 0))
            user_row = deepcopy(manual.get("records", {}).get(agency))
            if user_row:
                entered = _stamp(user_row.get("updated_at"))
                user_row.update(stale=bool(entered and now - entered > timedelta(days=ttl)),
                    outlook_stale=False, watch_stale=False, forward_signal_stale=False,
                    manual_revision=revisions[agency])
                user_row["latest_change"] = history.latest_change(retained, user_row)
                manual_rows.append(deepcopy(user_row))
                effective.append(user_row)
            else:
                effective.append({**deepcopy(row), "manual_revision": revisions[agency],
                                  "latest_change": history.latest_change(retained, row)})
        known = sum(row["status"] in {"rated", "unrated", "withdrawn"} for row in effective)
        response = {"schema_version": SCHEMA, "security_key": key,
            **{k: candidate.get(k, "") for k in ("symbol", "stock_market", "currency")},
            "issuer_name": candidate.get("issuer_name") or candidate.get("name") or "",
            "status": "ok" if known == 3 else "partial" if known else "unavailable",
            "ratings": effective, "retrieved_ratings": retrieved, "manual_ratings": manual_rows,
            "manual_revisions": revisions, "identity_token": manual["identity_token"],
            "manual_policy": manual_policy(candidate),
            "rating_history": deepcopy(sorted(retained["events"], key=lambda entry: entry["detected_at"], reverse=True)),
            "retrieval_mode": "public_ai", "provider_status": [],
            "fetched_at": saved.get("fetched_at") if matching else None}
        return response

    def summaries(self, keys):
        """One inventory capture and cache-only financial summaries for the table.

        Long source excerpts remain available in the single-security overview;
        the projection is never a replacement for its complete source context.
        """
        if len(keys) > 200 or any(not isinstance(key, str) or not key.strip() or len(key) > 300 for key in keys):
            raise HTTPException(422, "invalid_credit_rating_keys")
        requested = list(dict.fromkeys(key.strip().upper() for key in keys))
        if not requested:
            return {"items": [], "not_found_keys": [], "summary_only": True}
        wanted = set(requested)
        inventory = {item["security_key"]: item for item in self._inventory() if item["security_key"] in wanted}
        def compact(row):
            result = {key: deepcopy(value) for key, value in row.items() if key in SUMMARY_FIELDS}
            if "latest_change" in result:
                result["latest_change"] = history.compact_change(result["latest_change"])
            if row.get("sources"):
                result["sources"] = [{key: source[key] for key in ("url", "title", "fields", "fetched_at", "source_kind")
                                      if key in source} for source in row["sources"]]
            if "observations" in row:
                result["observations"] = [compact(item) for item in row["observations"]]
            return result
        items = []
        for key in requested:
            if key not in inventory:
                continue
            response = self.read(inventory[key])
            response.pop("rating_history", None)
            items.append({**response, "ratings": [compact(row) for row in response["ratings"]],
                          "retrieved_ratings": [compact(row) for row in response["retrieved_ratings"]],
                          "manual_ratings": [compact(row) for row in response["manual_ratings"]], "summary_only": True})
        return {"items": items, "not_found_keys": [key for key in requested if key not in inventory], "summary_only": True}

    @staticmethod
    def missing(response):
        return [row["agency"] for row in response.get("retrieved_ratings", response["ratings"]) if row["status"] not in {"rated", "unrated", "withdrawn"}
                or row.get("stale") or row.get("forward_signal_stale")
                or row["status"] == "rated" and row.get("outlook") in {None, "unknown"} and row.get("watch") in {None, "unknown"}]

    @staticmethod
    def agency_coverage(response):
        rows = response.get("retrieved_ratings", [])
        return {"verified_agencies": [row["agency"] for row in rows if row["status"] in history.KNOWN],
                "agency_statuses": {row["agency"]: row["status"] for row in rows}}

    def save_manual(self, payload, actor):
        if not self._manual_store:
            raise HTTPException(503, "manual_rating_store_unavailable")
        key = payload.get("security_key")
        if not isinstance(key, str) or not key.strip() or len(key) > 300:
            raise HTTPException(422, "manual_invalid_security_key")
        candidate = self.candidate(key.strip().upper())
        if not candidate:
            raise HTTPException(404, "security_not_found")
        try:
            _, _, expected_identity = manual_preconditions(payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        # An unchanged old draft belongs to its captured issuer. Reject that
        # stale identity before judging the old name against the new issuer.
        if expected_identity != manual_identity(candidate, _binding(candidate)):
            raise HTTPException(409, "security_identity_changed")
        agency = payload.get("agency")
        if agency not in AGENCIES:
            raise HTTPException(422, "manual_invalid_agency")
        if type(payload.get("expected_revision")) is not int or payload["expected_revision"] < 0:
            raise HTTPException(422, "manual_invalid_revision")
        if not isinstance(payload.get("expected_identity"), str) or not re.fullmatch(r"[0-9a-f]{64}", payload["expected_identity"]):
            raise HTTPException(422, "manual_invalid_identity")
        with self._lock:
            current = self.candidate(candidate["security_key"])
            if not current or _binding(current) != _binding(candidate):
                raise HTTPException(409, "security_identity_changed")
            identity = manual_identity(current, _binding(current))
            manual_key = preference_key(current, identity)
            history_key = self._history_key(current)
            def edit(values):
                snapshot = self._manual_value(current, values[manual_key])
                if payload["expected_identity"] != snapshot["identity_token"]:
                    raise HTTPException(409, "security_identity_changed")
                revision = int(snapshot.get("revisions", {}).get(agency, 0))
                if payload["expected_revision"] != revision:
                    raise HTTPException(409, "manual_rating_conflict")
                try:
                    record = normalize_manual(payload, current)
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc
                stamp = _now()
                previous = snapshot["records"].get(agency) or {}
                retained = self._history_value(current, values[history_key])
                public = self._public_snapshot(current, retained)
                retained = self._record_public(current, retained, public, stamp)
                before = previous or self._agency_rows(current, public)[agency]
                record.update(revision=revision + 1, created_at=previous.get("created_at") or stamp,
                    updated_at=stamp, updated_by=str(actor.get("username") or actor.get("id") or ""))
                snapshot["records"][agency] = record
                snapshot["revisions"][agency] = revision + 1
                retained = history.record_manual(retained, before, record, stamp, actor=record["updated_by"])
                return {manual_key: snapshot, history_key: retained}
            self._update_preferences([manual_key, history_key], edit)
            return self.read(current)

    def clear_manual(self, key, agency, expected_revision, expected_identity, actor=None):
        if not self._manual_store:
            raise HTTPException(503, "manual_rating_store_unavailable")
        if agency not in AGENCIES:
            raise HTTPException(422, "manual_invalid_agency")
        if not isinstance(key, str) or not key.strip() or len(key) > 300:
            raise HTTPException(422, "manual_invalid_security_key")
        if type(expected_revision) is not int or expected_revision < 0:
            raise HTTPException(422, "manual_invalid_revision")
        candidate = self.candidate(key.strip().upper())
        if not candidate:
            raise HTTPException(404, "security_not_found")
        with self._lock:
            current = self.candidate(candidate["security_key"])
            if not current or _binding(current) != _binding(candidate):
                raise HTTPException(409, "security_identity_changed")
            identity = manual_identity(current, _binding(current))
            manual_key = preference_key(current, identity)
            history_key = self._history_key(current)
            def edit(values):
                snapshot = self._manual_value(current, values[manual_key])
                if expected_identity != snapshot["identity_token"]:
                    raise HTTPException(409, "security_identity_changed")
                revision = int(snapshot.get("revisions", {}).get(agency, 0))
                if expected_revision != revision:
                    raise HTTPException(409, "manual_rating_conflict")
                before = snapshot["records"].pop(agency, None)
                snapshot["revisions"][agency] = revision + 1
                retained = self._history_value(current, values[history_key])
                public = self._public_snapshot(current, retained)
                if before:
                    stamp = _now()
                    retained = self._record_public(current, retained, public, stamp)
                    retained = history.record_manual(retained, before, self._agency_rows(current, public)[agency], stamp,
                        actor=str((actor or {}).get("username") or (actor or {}).get("id") or ""), clearing=True)
                return {manual_key: snapshot, history_key: retained}
            self._update_preferences([manual_key, history_key], edit)
            return self.read(current)

    def _accept_sources(self, candidate, sources):
        from .credit_ratings import extract_rating_records, normalize_observation
        accepted = []
        for original in sources:
            source = self._authorize_source(candidate, original)
            for record in extract_rating_records(source, candidate):
                try:
                    accepted.append(normalize_observation(record, candidate, source=source))
                except ValueError:
                    continue
        return accepted

    def _authorize_source(self, candidate, source):
        """Establish issuer ownership in the application, never from page JSON."""
        from .credit_ratings import _matches_entity
        result = deepcopy(source)
        result.pop("_issuer_source_verified", None)
        domains = set(candidate.get("verified_issuer_domains") or [])
        domains.update(urlsplit(url).hostname for entity, url in ISSUER_SOURCES if _matches_entity(entity, candidate))
        host = (urlsplit(str(result.get("url") or "")).hostname or "").lower().rstrip(".")
        if host and any(host == str(domain).lower().rstrip(".")
                        or host.endswith("." + str(domain).lower().rstrip(".")) for domain in domains if domain):
            result["_issuer_source_verified"] = True
        return result

    @staticmethod
    def _merge_public(saved, observations, started_at):
        def identity(row):
            return (_axes(row), row["agency"], row.get("source_url"))
        by_identity = {identity(row): deepcopy(row) for row in saved.get("observations", [])}
        changed = False
        accepted_keys = set()
        for row in observations:
            row_identity = identity(row)
            previous = by_identity.get(row_identity)
            same_axis = [value for value in by_identity.values()
                         if _axes(value) == _axes(row) and value["agency"] == row["agency"]]
            newest_read = max(same_axis, key=lambda value: value.get("fetched_at") or "", default=None)
            if newest_read and started_at and (_stamp(newest_read.get("fetched_at")) or datetime.min.replace(tzinfo=timezone.utc)) > (_stamp(started_at) or datetime.min.replace(tzinfo=timezone.utc)):
                continue  # A later request already published this axis.
            # A late read of an older publication/action is historical evidence,
            # not permission to roll back the current source facts or signals.
            published = str(row.get("observed_at") or row.get("rating_date") or "")[:10]
            dated = [value for value in same_axis if value.get("observed_at") or value.get("rating_date")]
            latest = max(dated, key=lambda value: str(value.get("observed_at") or value.get("rating_date"))[:10], default=None)
            if latest and published and published < str(latest.get("observed_at") or latest.get("rating_date"))[:10]:
                continue
            actions = [value["rating_date"] for value in same_axis if value.get("rating_date")]
            if actions and row.get("rating_date") and row["rating_date"] < max(actions):
                if any((value.get("rating"), value.get("status")) != (row.get("rating"), row.get("status")) for value in same_axis):
                    continue
            merged = deepcopy(row)
            # Keep the last supported grade action date on an unchanged grade;
            # a newer outlook-only report may repeat an older grade action.
            if previous and (previous.get("rating"), previous.get("status")) == (merged.get("rating"), merged.get("status")):
                if previous.get("rating_date") and (not merged.get("rating_date") or merged["rating_date"] < previous["rating_date"]):
                    merged["rating_date"] = previous["rating_date"]
            for field in ("outlook", "watch"):
                if merged.get(field) not in {None, "unknown"}:
                    merged[field + "_fetched_at"] = merged.get("fetched_at")
            if previous and merged.get("rating") == previous.get("rating") and merged.get("status") == previous.get("status") == "rated":
                for field in ("outlook", "watch"):
                    if previous.get(field + "_date") and merged.get(field + "_date") and merged[field + "_date"] < previous[field + "_date"]:
                        for suffix in ("", "_date", "_fetched_at"):
                            merged[field + suffix] = previous.get(field + suffix)
                for field in ("outlook", "watch", "outlook_date", "watch_date"):
                    if merged.get(field) in {None, "unknown"} and previous.get(field) not in {None, "unknown"}:
                        merged[field] = previous[field]
                        if field in {"outlook", "watch"}:
                            merged[field + "_fetched_at"] = previous.get(field + "_fetched_at") or previous.get("fetched_at")
                retained = [field for field in ("outlook", "watch") if merged.get(field) != row.get(field)
                            or merged.get(field + "_date") != row.get(field + "_date")]
                if retained:
                    older_sources = [{**source, "fields": retained} for source in previous.get("sources", [])
                                     if not source.get("fields") or set(source["fields"]) & set(retained)]
                    all_sources = older_sources + merged.get("sources", [])
                    merged["sources"] = list({(item["url"], item.get("fetched_at"), item.get("evidence_quote")): item for item in all_sources}.values())[-12:]
                    merged["forward_signal_checked_at"] = previous.get("forward_signal_checked_at") or previous.get("fetched_at")
            if merged != previous:
                changed = True
                by_identity[row_identity] = merged
                accepted_keys.add(row_identity)
        # The evidence bound must never discard the observation just accepted.
        # Prefer this publication's rows, then the most recent retained source
        # evidence. Historical events keep their own immutable source excerpts.
        bounded = sorted(by_identity.values(), key=lambda value: (
            identity(value) in accepted_keys,
            str(value.get("observed_at") or value.get("rating_date") or "")[:10],
            value.get("rating_date") or "", value.get("fetched_at") or ""), reverse=True)[:150]
        return bounded, changed

    def publish(self, candidate, observations, provider_status=None, *, started_at=None):
        """Persist source baseline/history locally before projecting the cache."""
        current = self.candidate(candidate["security_key"])
        if not current or _binding(current) != _binding(candidate) or (
                candidate.get("_position_scope") == "open" and not current.get("has_open_position")):
            return False
        with self._lock:
            current = self.candidate(candidate["security_key"])
            if not current or _binding(current) != _binding(candidate) or (
                    candidate.get("_position_scope") == "open" and not current.get("has_open_position")):
                return False
            history_key = self._history_key(current)
            changed = False
            def edit(values):
                nonlocal changed
                retained = self._history_value(current, values[history_key])
                saved = self._public_snapshot(current, retained)
                stamp = _now()
                retained = self._record_public(current, retained, saved, stamp)
                accepted, changed = self._merge_public(saved, observations, started_at)
                public = {"schema_version": SCHEMA, "_binding": _binding(current), "observations": accepted,
                          "provider_status": [], "retrieval_mode": "public_ai", "attempts": saved.get("attempts", {}),
                          "fetched_at": stamp if changed else saved.get("fetched_at")}
                retained = self._record_public(current, retained, public, stamp)
                return {history_key: retained}
            updated = self._update_preferences([history_key], edit)
            self._cache().set_security_snapshot("credit_ratings", current["security_key"], SCHEMA,
                                               updated[history_key]["public_snapshot"])
            return changed

    def record_attempt(self, candidate, agencies, reason_code):
        current = self.candidate(candidate["security_key"])
        if not current or _binding(current) != _binding(candidate):
            return
        with self._lock:
            history_key = self._history_key(current)
            def edit(values):
                retained = self._history_value(current, values[history_key])
                saved = self._public_snapshot(current, retained)
                saved.update(schema_version=SCHEMA, _binding=_binding(current), provider_status=[], retrieval_mode="public_ai")
                attempts = saved.setdefault("attempts", {})
                stamp = _now()
                for agency in agencies:
                    if agency in AGENCIES:
                        attempts[agency] = {"checked_at": stamp, "reason_code": reason_code}
                return {history_key: self._record_public(current, retained, saved, stamp)}
            updated = self._update_preferences([history_key], edit)
            self._cache().set_security_snapshot("credit_ratings", current["security_key"], SCHEMA,
                                               updated[history_key]["public_snapshot"])

    def check_apis(self, candidate, budget):
        """Compatibility seam: credit retrieval never invokes a licensed feed."""
        return [], []

    def candidates(self, position_scope="open", security_keys=None):
        """Selected public-source research, independent of other API coverage."""
        settings = self._research_settings()
        inventory = self.inventory(position_scope, security_keys)[:3]
        items, preflight = [], []
        for original in inventory:
            candidate = {**original, "captured_at": _now(), "_binding": _binding(original), "_position_scope": position_scope}
            response = self.read(candidate)
            missing = list(AGENCIES)  # An explicit public check covers every requested agency.
            coverage = self.agency_coverage(response)
            candidate.update(missing_fields=["credit_ratings"], missing_agencies=missing,
                requested_agencies=list(AGENCIES), available_fields=[], retrieval_mode="public_ai")
            items.append(candidate)
            preflight.append({**candidate, "status": "unavailable", "code": "data_unavailable",
                "research_eligible": True, "provider_status": [], **coverage})
        return {"items": items, "total_count": len(items), "truncated": False,
                "research_available": search_is_configured(settings), "preflight_outcomes": preflight,
                "configured_search_providers": ["yahoo", "duckduckgo"] + (["brave"] if settings.get("search_api_key") else [])}

    def _session(self, candidate):
        key = str(candidate.get("_request_id") or "")
        if not key:
            raise ResearchFailure("invalid_request", "A research request is required.")
        with self._lock:
            if key not in self._sessions:
                cfg = self._research_settings()
                self._sessions[key] = ResearchSession(cfg, WebRequestBudget(cfg.get("max_web_calls", 8)))
            for old in list(self._sessions)[:-100]:
                self._sessions.pop(old, None)
                self._research_attempts.pop(old, None)
            return self._sessions[key]

    def research_tool(self, candidate, action, arguments):
        current = self.candidate(candidate["security_key"])
        if not current or _binding(candidate) != _binding(current) or (
                candidate.get("_position_scope") == "open" and not current.get("has_open_position")):
            return {"evidence": [], "source_status": "not_open"}
        session = self._session(candidate)
        previous_operations = session.budget.used
        try:
            if action == "discover":
                from .credit_ratings import _matches_entity
                leads = [(url, "Official issuer credit ratings; unverified discovery lead")
                         for entity, url in ISSUER_SOURCES if _matches_entity(entity, current)]
                leads.extend((url, "Official agency research; unverified discovery lead")
                             for entity, url in AGENCY_SOURCE_LEADS if _matches_entity(entity, current))
                # Previously validated source URLs and provider website fields
                # provide useful discovery when a public search is blocked.
                for row in self.read(current)["retrieved_ratings"]:
                    leads.extend((src["url"], src.get("title") or "Previously verified credit-rating source")
                                 for src in row.get("sources", []) if src.get("url"))
                for field in ("issuer_website", "website"):
                    if current.get(field):
                        leads.append((current[field], "Issuer website; unverified discovery lead"))
                sources = []
                seen = set()
                for url, title in leads:
                    if url in seen:
                        continue
                    try:
                        source_id = session._add(current["security_key"], url, title)
                    except ResearchFailure:
                        continue
                    seen.add(url)
                    sources.append({"source_id": source_id, "url": url, "title": title, "discovery_only": True})
                return {"sources": sources[:8], "evidence": [], "source_status": "sources_found", "web_requests": session.budget.used}
            if action == "search":
                query = arguments["query"]
                if isinstance(query, str) and query.strip() and not search_query_matches_identity(query, candidate):
                    # Discovery remains bound to this registered security even
                    # when the model omits a legal suffix. Preserve its full
                    # query; the shared reader enforces length/budgets and all
                    # source facts still require exact issuer/issue identity.
                    query = str(candidate.get("symbol") or "") + " " + query
                result = session.search(candidate, query, provider=arguments.get("provider", "auto"))
                return {**result, "evidence": [], "source_status": "search_results", "web_requests": session.budget.used}
            if action == "read":
                source = session.read(candidate, arguments["source_id"], reader=arguments.get("reader"))
            elif action == "follow":
                source = session.follow(candidate, arguments["source_id"], arguments["link_id"], reader=arguments.get("reader"))
            else:
                raise ResearchFailure("invalid_request", "Invalid research operation.")
            from .credit_ratings import extract_rating_records, validate_observation, source_authority
            source = self._authorize_source(candidate, source)
            records = [record for record in extract_rating_records(source, candidate)
                       if validate_observation(record, candidate, source=source) is not None]
            source["source_authority"] = source_authority(source, candidate) or "unverified"
            source["context_records"] = [{k: deepcopy(v) for k, v in record.items() if not k.startswith("_")} for record in records]
            return {"evidence": [source], "source_status": "evidence_found", "diagnostics": dict(session.diagnostics), "web_requests": session.budget.used}
        except (ResearchFailure, SearchFailure, ProviderFailure, ValueError, OSError, TimeoutError) as exc:
            result = {"evidence": [], "source_status": getattr(exc, "code", "source_read_failed"),
                      "diagnostics": dict(session.diagnostics), "web_requests": session.budget.used}
            if action == "search" and result["source_status"] == "invalid_request":
                result["recovery_guidance"] = (
                    "Include the exact registered symbol " + repr(str(candidate.get("symbol") or "")[:80])
                    + " in the search query, or the full stored legal name including its suffix; keep the requested issuer. "
                    "Correct the query within the remaining request budgets."
                )
            return result
        finally:
            if session.budget.used > previous_operations:
                with self._lock:
                    self._research_attempts.setdefault(str(candidate.get("_request_id") or ""), set()).add(candidate["security_key"])

    def finalize(self, outcomes, user_id, request_id, *, proposal=None, evidence_by_key=None, candidates=None, **kwargs):
        from .credit_ratings import extract_rating_records, normalize_observation
        from .security_web_research import parse_research_proposal
        parsed = parse_research_proposal(proposal) or {}
        choices = parsed.get("records") or []
        selected = set()
        if isinstance(choices, list):
            for choice in choices[:30]:
                if isinstance(choice, dict) and set(choice) == {"security_key", "source_id", "record_id"} and all(isinstance(x, str) for x in choice.values()):
                    selected.add((choice["security_key"], choice["source_id"], choice["record_id"]))
        finalized = []
        by_key = {row["security_key"]: row for row in outcomes}
        for key, candidate in (candidates or {}).items():
            current = self.candidate(key)
            if not current or _binding(current) != _binding(candidate) or (
                    candidate.get("_position_scope") == "open" and not current.get("has_open_position")):
                finalized.append({**candidate, "status": "not_attempted", "code": "not_open", "attempted": False,
                                  "available_fields": [], "missing_fields": []})
                continue
            accepted = []
            for original in (evidence_by_key or {}).get(key, []):
                source = self._authorize_source(candidate, original)
                for record in extract_rating_records(source, candidate):
                    identity = (key, source.get("source_id"), record.get("record_id"))
                    if identity not in selected:
                        continue
                    try:
                        accepted.append(normalize_observation(record, candidate, source=source))
                    except ValueError:
                        continue
            changed = bool(accepted and self.publish(candidate, accepted, started_at=candidate.get("captured_at")))
            response = self.read(candidate)
            missing = self.missing(response)
            previous = by_key.get(key, {})
            attempted = bool(accepted or (evidence_by_key or {}).get(key)
                             or key in self._research_attempts.get(request_id, set()))
            if attempted:
                self.record_attempt(candidate, candidate.get("requested_agencies", AGENCIES),
                                    "evidence_rejected" if selected and not accepted else "data_unavailable" if missing else "data_found")
                response = self.read(candidate)
                missing = self.missing(response)
            status = ("not_attempted" if not attempted else "updated" if changed and not missing
                      else "partial" if changed or previous.get("available_fields") else "unavailable")
            row = {**candidate, "status": status, "attempted": attempted,
                "code": "research_incomplete" if not attempted else "data_found" if status == "updated" else "partial_data" if status == "partial" else previous.get("code", "data_unavailable"),
                "available_fields": ["credit_ratings"] if changed or previous.get("available_fields") else [],
                "missing_fields": ["credit_ratings"] if missing else [], "missing_agencies": missing,
                "last_attempted_at": _now(), "retrieval_mode": "public_ai", **self.agency_coverage(response)}
            finalized.append(row)
            with self._lock:
                self._outcomes[key] = deepcopy(row)
        return finalized

    def outcome_reader(self):
        with self._lock:
            return deepcopy(list(self._outcomes.values()))

    def manager(self, app, assistant_settings, *, event_writer=None, worker_factory=None):
        options = {} if worker_factory is None else {"worker_factory": worker_factory}
        manager = EnrichmentJobs(app, assistant_settings, candidate_reader=self.candidates,
            security_fetcher=lambda *_: {"evidence": [], "source_status": "data_unavailable"},
            outcome_reader=self.outcome_reader, outcome_writer=self.finalize,
            source_hint_reader=lambda candidate: self.research_tool(candidate, "discover", {}).get("sources", []),
            research_tool_fetcher=self.research_tool, prefix=PREFIX, research_policy=POLICY,
            research_metadata={"issuer_name", "missing_agencies", "requested_agencies", "captured_at"},
            discovery_subject="credit ratings Moody's S&P Fitch outlook issuer investor relations",
            refresh_portfolio_on_update=False, selection_reader=True, event_writer=event_writer, **options)
        for definition in manager._web_catalog.values():
            definition["description"] += " For credit ratings, inspect exact issuer/issue agency rating/outlook/watch context records; do not research price quotes."
        return manager

    def router(self):
        router = APIRouter(tags=["company credit ratings"])

        def editor(request):
            actor = getattr(request.state, "auth_user", None)
            if not isinstance(actor, dict):
                raise HTTPException(401, "authentication_required")
            if actor.get("role") not in {"Admin", "Operator"}:
                raise HTTPException(403, "read_only")
            return actor

        @router.put(PREFIX + "/manual")
        def save_manual(request: Request, payload: dict):
            return self.save_manual(payload, editor(request))

        @router.delete(PREFIX + "/manual")
        def clear_manual(request: Request, security_key: str, agency: str,
                         expected_revision: int = Query(ge=0), expected_identity: str = Query(min_length=64, max_length=64)):
            actor = editor(request)
            return self.clear_manual(security_key, agency, expected_revision, expected_identity, actor=actor)

        @router.get(PREFIX + "/summaries")
        def summaries(request: Request, security_keys: list[str] = Query(default=[], max_length=200)):
            if not isinstance(getattr(request.state, "auth_user", None), dict):
                raise HTTPException(401, "authentication_required")
            return self.summaries(security_keys)

        @router.get(PREFIX)
        def read(symbol: str, request: Request, stock_market: str = "", currency: str = ""):
            if not isinstance(getattr(request.state, "auth_user", None), dict):
                raise HTTPException(401, "authentication_required")
            key = security_key({"symbol": symbol, "stock_market": stock_market, "currency": currency})
            candidate = self.candidate(key)
            if not candidate:
                raise HTTPException(404, "security_not_found")
            return self.read(candidate)

        @router.get(PREFIX + "/providers")
        def providers(request: Request):
            if not isinstance(getattr(request.state, "auth_user", None), dict):
                raise HTTPException(401, "authentication_required")
            return {"retrieval_mode": "public_ai", "items": [{"provider": "public_ai", "configured": True,
                "status": "available", "agencies": list(AGENCIES),
                "supports": ["issuer", "issue", "rating", "outlook", "watch"]}]}

        return router
