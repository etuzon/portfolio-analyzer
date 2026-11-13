"""Application-owned credit-rating cache, API-first checks and AI REST evidence.

The AI coordinator receives only the fixed REST tools. This application layer
owns inventory, public-source reads, evidence validation and cache publication.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from threading import RLock
from typing import Callable
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query, Request

from . import credit_ratings_api
from .security_enrichment import EnrichmentJobs, WEB_RESEARCH_POLICY, security_key
from .security_research_tools import ResearchSession, ResearchFailure, WebRequestBudget
from .security_search import SearchFailure, search_is_configured
from .us_market_providers import ProviderFailure, RequestBudget

PREFIX = "/api/securities/credit-ratings"
SCHEMA = "credit-ratings-v1"
AGENCIES = ("moodys", "sp", "fitch")
SUMMARY_FIELDS = frozenset({
    "agency", "status", "reason_code", "rating", "rating_raw", "scope", "scale", "term", "rating_type",
    "entity_name", "entity_id", "rating_date", "outlook", "watch", "outlook_date", "watch_date",
    "observed_at", "fetched_at", "checked_at", "stale", "outlook_stale", "watch_stale", "forward_signal_stale",
    "outlook_fetched_at", "watch_fetched_at", "forward_signal_checked_at", "issuer_fallback", "primary_eligible",
    "record_id", "source_url", "source_kind", "action_type", "snapshot_kind", "currency_basis",
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

POLICY = WEB_RESEARCH_POLICY + (
    " This task is COMPANY CREDIT RATINGS, not prices, stock recommendations or financial-ratio scores. "
    "Research Moody's, S&P Global Ratings and Fitch independently for the exact supplied legal issuer or bond issue. "
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


def select_observation(rows, candidate):
    """Select a display opinion without merging unlike debt/entity classes."""
    if not rows:
        return None
    from .credit_ratings import is_primary_observation
    all_rows = rows
    rows = [row for row in rows if is_primary_observation(row, candidate)]
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
                 research_settings: Callable, api_transport=None):
        self._cache, self._settings, self._inventory = cache, settings, inventory
        self._research_settings = research_settings
        self._api_transport = api_transport
        self._lock = RLock()
        self._sessions = {}
        self._api_status = {}
        self._outcomes = {}

    def candidate(self, key):
        return next((item for item in self._inventory() if item["security_key"] == key), None)

    def read(self, candidate):
        """Cache-only read; retain original agency dates and provenance."""
        key = candidate.get("security_key") or security_key(candidate)
        saved = self._cache().get_security_snapshot("credit_ratings", key, SCHEMA)
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
            rows.append(row)
        known = sum(row["status"] in {"rated", "unrated", "withdrawn"} for row in rows)
        response = {"schema_version": SCHEMA, "security_key": key,
            **{k: candidate.get(k, "") for k in ("symbol", "stock_market", "currency")},
            "issuer_name": candidate.get("issuer_name") or candidate.get("name") or "",
            "status": "ok" if known == 3 else "partial" if known else "unavailable",
            "ratings": rows, "provider_status": deepcopy(saved.get("provider_status", [])) if matching else credit_ratings_api.registry(self._settings()),
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
            items.append({**response, "ratings": [compact(row) for row in response["ratings"]], "summary_only": True})
        return {"items": items, "not_found_keys": [key for key in requested if key not in inventory], "summary_only": True}

    @staticmethod
    def missing(response):
        return [row["agency"] for row in response["ratings"] if row["status"] not in {"rated", "unrated", "withdrawn"}
                or row.get("stale") or row.get("forward_signal_stale")
                or row["status"] == "rated" and row.get("outlook") in {None, "unknown"} and row.get("watch") in {None, "unknown"}]

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

    def publish(self, candidate, observations, provider_status=None, *, started_at=None):
        """Recheck identity and publication freshness under one cache lock."""
        current = self.candidate(candidate["security_key"])
        if not current or _binding(current) != _binding(candidate) or (
                candidate.get("_position_scope") == "open" and not current.get("has_open_position")):
            return False
        with self._lock:
            current = self.candidate(candidate["security_key"])
            if not current or _binding(current) != _binding(candidate) or (
                    candidate.get("_position_scope") == "open" and not current.get("has_open_position")):
                return False
            saved = self._cache().get_security_snapshot("credit_ratings", candidate["security_key"], SCHEMA)
            saved = saved if isinstance(saved, dict) and saved.get("_binding") == _binding(current) else {}
            existing = saved.get("observations", [])
            def identity(row):
                return (_axes(row), row["agency"], row.get("source_url"))
            by_identity = {identity(r): deepcopy(r) for r in existing}
            changed = False
            for row in observations:
                row_identity = identity(row)
                previous = by_identity.get(row_identity)
                same_axis = [value for value in by_identity.values()
                             if _axes(value) == _axes(row) and value["agency"] == row["agency"]]
                latest_axis = max(same_axis, key=lambda value: value.get("fetched_at") or "", default=None)
                if latest_axis and started_at and (_stamp(latest_axis.get("fetched_at")) or datetime.min.replace(tzinfo=timezone.utc)) > (_stamp(started_at) or datetime.min.replace(tzinfo=timezone.utc)):
                    continue
                if previous and started_at and (_stamp(previous.get("fetched_at")) or datetime.min.replace(tzinfo=timezone.utc)) > (_stamp(started_at) or datetime.min.replace(tzinfo=timezone.utc)):
                    continue  # A later verified refresh won while this one ran.
                if previous and previous.get("rating_date") and row.get("rating_date") and row["rating_date"] < previous["rating_date"]:
                    continue
                # Retain missing individual fields rather than overwriting
                # supported outlook/watch facts with inferred defaults.
                merged = deepcopy(row)
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
                        # Two reads of one URL can contain different facts.
                        # Preserve the original excerpt and fetch date for a
                        # retained signal, not merely a link to today's page.
                        older_sources = [{**source, "fields": retained} for source in previous.get("sources", [])
                                         if not source.get("fields") or set(source["fields"]) & set(retained)]
                        all_sources = older_sources + merged.get("sources", [])
                        merged["sources"] = list({(s["url"], s.get("fetched_at"), s.get("evidence_quote")): s for s in all_sources}.values())[-12:]
                        merged["forward_signal_checked_at"] = previous.get("forward_signal_checked_at") or previous.get("fetched_at")
                by_identity[row_identity] = merged
                changed = True
            self._cache().set_security_snapshot("credit_ratings", current["security_key"], SCHEMA,
                {"schema_version": SCHEMA, "_binding": _binding(current), "observations": list(by_identity.values())[:150],
                 "provider_status": provider_status if provider_status is not None else saved.get("provider_status", []),
                 "attempts": saved.get("attempts", {}),
                 "fetched_at": _now() if changed else saved.get("fetched_at")})
            return changed

    def record_attempt(self, candidate, agencies, reason_code):
        current = self.candidate(candidate["security_key"])
        if not current or _binding(current) != _binding(candidate):
            return
        with self._lock:
            saved = self._cache().get_security_snapshot("credit_ratings", candidate["security_key"], SCHEMA)
            saved = saved if isinstance(saved, dict) and saved.get("_binding") == _binding(current) else {}
            saved.update(schema_version=SCHEMA, _binding=_binding(current))
            attempts = saved.setdefault("attempts", {})
            for agency in agencies:
                if agency in AGENCIES:
                    attempts[agency] = {"checked_at": _now(), "reason_code": reason_code}
            self._cache().set_security_snapshot("credit_ratings", candidate["security_key"], SCHEMA, saved)

    def check_apis(self, candidate, budget):
        checked = credit_ratings_api.fetch(candidate, self._settings(), budget, transport=self._api_transport)
        accepted = self._accept_sources(candidate, checked["sources"])
        self.publish(candidate, accepted, checked["provider_status"])
        return accepted, checked["provider_status"]

    def candidates(self, position_scope="open", security_keys=None):
        """Selected API preflight is application logic, never model DB access."""
        settings = self._research_settings()
        budget = RequestBudget(5)
        inventory = self._inventory()
        if position_scope == "open":
            inventory = [item for item in inventory if item.get("has_open_position")]
        if security_keys:
            inventory = [item for item in inventory if item["security_key"] in security_keys]
        inventory = inventory[:3]
        items, preflight = [], []
        for original in inventory:
            candidate = {**original, "captured_at": _now(), "_binding": _binding(original), "_position_scope": position_scope}
            accepted, api_status = self.check_apis(candidate, budget)
            response = self.read(candidate)
            missing = self.missing(response)
            # An explicit refresh rechecks public evidence if no entitled API
            # supplied a new observation; existing saved data remains visible.
            if not accepted:
                missing = list(AGENCIES)
            candidate.update(missing_fields=["credit_ratings"] if missing else [],
                missing_agencies=missing, requested_agencies=list(AGENCIES), available_fields=["credit_ratings"] if accepted else [])
            items.append(candidate)
            preflight.append({**candidate, "status": "updated" if accepted and not missing else "partial" if accepted else "unavailable",
                "code": "data_found" if accepted and not missing else "partial_data" if accepted else "data_unavailable",
                "research_eligible": bool(missing), "provider_status": api_status})
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
            return self._sessions[key]

    def research_tool(self, candidate, action, arguments):
        current = self.candidate(candidate["security_key"])
        if not current or _binding(candidate) != _binding(current) or (
                candidate.get("_position_scope") == "open" and not current.get("has_open_position")):
            return {"evidence": [], "source_status": "not_open"}
        session = self._session(candidate)
        try:
            if action == "discover":
                from .credit_ratings import _matches_entity
                leads = [(url, "Official issuer credit ratings; unverified discovery lead")
                         for entity, url in ISSUER_SOURCES if _matches_entity(entity, current)]
                # Previously validated source URLs and provider website fields
                # provide useful discovery when a public search is blocked.
                for row in self.read(current)["ratings"]:
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
                result = session.search(candidate, arguments["query"], provider=arguments.get("provider", "auto"))
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
            return {"evidence": [], "source_status": getattr(exc, "code", "source_read_failed"),
                    "diagnostics": dict(session.diagnostics), "web_requests": session.budget.used}

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
            self.record_attempt(candidate, candidate.get("requested_agencies", AGENCIES),
                                "evidence_rejected" if selected and not accepted else "data_unavailable" if missing else "data_found")
            status = "updated" if changed and not missing else "partial" if changed or previous.get("available_fields") else "unavailable"
            row = {**candidate, "status": status, "attempted": True,
                "code": "data_found" if status == "updated" else "partial_data" if status == "partial" else previous.get("code", "data_unavailable"),
                "available_fields": ["credit_ratings"] if changed or previous.get("available_fields") else [],
                "missing_fields": ["credit_ratings"] if missing else [], "missing_agencies": missing,
                "last_attempted_at": _now()}
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
            return {"items": credit_ratings_api.registry(self._settings())}

        return router
