"""Licensed Agency Ratings API discovery and bounded, read-only retrieval.

The endpoint and response fields are the public S&P Global Agency Ratings
OpenAPI contract. Data access still requires the corresponding entitlements.
No request credentials or provider error bodies are returned to the browser.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any

import httpx
from .us_market_providers import ProviderFailure

BASE = "https://xpressapi.marketplace.spglobal.com/agencyratings"
DOCS = "https://xpressapi.marketplace.spglobal.com/swagger/?urls.primaryName=agencyratings"
PROVIDER = "spglobal_agency_ratings"
AGENCIES = ("moodys", "sp", "fitch")


def registry(settings: dict) -> list[dict]:
    cfg = settings.get("spglobal", {})
    configured = bool(cfg.get("enabled", True) and cfg.get("bearer_token"))
    return [{"provider": PROVIDER, "configured": configured,
             "status": "disabled" if not cfg.get("enabled", True) else "configured" if configured else "not_configured",
             "agencies": list(AGENCIES), "docs_url": DOCS,
             "entitlement_required": True,
             "supports": ["issuer", "issue", "rating", "outlook", "watch"]}]


def _date(value):
    if not value:
        return None
    text = str(value).strip()[:10]
    try:
        from datetime import date
        parsed = date.fromisoformat(text)
        return parsed.isoformat()  # Domain cutoff validation rejects future facts.
    except ValueError:
        return None


def _legal(value):
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    return " ".join(word for word in text.split() if word not in {
        "inc", "incorporated", "corp", "corporation", "company", "co", "ltd", "limited", "the"})


def _entity_matches(candidate, entity_name, scope):
    # An exact issue query binds the instrument, not the user's informal issuer
    # abbreviation. Stock issuer data still needs a legal-name match to avoid
    # silently substituting a bank/subsidiary for its holding company.
    if scope == "issue":
        return True
    expected = candidate.get("issuer_name") or candidate.get("name")
    if not expected or str(expected).upper() in {str(candidate.get("symbol", "")).upper(), ""}:
        return False
    return bool(_legal(expected) and _legal(expected) == _legal(entity_name))


def _observations(payload, candidate, scope):
    """Map the documented agency-specific arrays without joining legal entities."""
    from .credit_ratings import infer_rating_axis, normalize_currency_basis, normalize_outlook, normalize_watch
    schemas = {
        "sp": ("s&pRatingsData", "s&pData", "ratingType", "rxEntityId"),
        "moodys": ("moodysRatingsData", "moodysData", "ratingTypeText", "moodysOrgId"),
        "fitch": ("fitchRatingsData", "fitchData", "ratingTypeName", "fitchIssuerId"),
    }
    results = payload.get("results", []) if isinstance(payload, dict) else []
    output = []
    for result in results if isinstance(results, list) else []:
        if not isinstance(result, dict):
            continue
        if str(result.get("identifierValue", "")).strip().upper() != str(candidate["_api_identifier"]).upper():
            continue
        for agency, (entities_key, ratings_key, type_key, id_key) in schemas.items():
            entities = result.get(entities_key) or []
            for entity in entities if isinstance(entities, list) else []:
                if not isinstance(entity, dict) or not _entity_matches(candidate, entity.get("entityLegalName"), scope):
                    continue
                raw_rows = entity.get(ratings_key) or []
                if not isinstance(raw_rows, list):
                    continue
                outlook_rows = [r for r in raw_rows if isinstance(r, dict)
                                and "outlook" in str(r.get(type_key, "")).casefold()]
                for raw in raw_rows[:100]:
                    if not isinstance(raw, dict) or not isinstance(raw.get("ratingValue"), str):
                        continue
                    kind = str(raw.get(type_key) or raw.get("ratingClassText") or "")
                    if "outlook" in kind.lower() or "watch" in kind.lower():
                        continue
                    grade_text = raw["ratingValue"].strip()
                    action = str(raw.get("ratingAction") or "").strip().casefold()
                    status = ("withdrawn" if grade_text.casefold() in {"wr", "wd", "withdrawn"}
                              or action in {"withdrawn", "withdrawal", "rating withdrawal", "rating withdrawn", "wd", "wr"}
                              else "unrated" if grade_text.casefold() in {"nr", "n.r.", "not rated", "unrated"} else "rated")
                    outlook, watch = "unknown", "unknown"
                    outlook_date = watch_date = None
                    used_rows = [raw]
                    if agency == "sp":
                        forward = str(raw.get("creditWatchOutlookIndicator") or "").lower()
                        if "watch" in forward:
                            watch = normalize_watch(raw.get("creditWatchOutlookValue"))
                            watch_date = _date(raw.get("creditWatchOutlookDate"))
                        elif "outlook" in forward:
                            outlook = normalize_outlook(raw.get("creditWatchOutlookValue"))
                            outlook_date = _date(raw.get("creditWatchOutlookDate"))
                    elif agency == "moodys":
                        alert = str(raw.get("watchlistDirectionText") or "")
                        if "outlook" in alert.casefold():
                            outlook = normalize_outlook(alert)
                            outlook_date = _date(raw.get("watchlistDate"))
                        elif alert:
                            watch = normalize_watch(alert)
                            watch_date = _date(raw.get("watchlistDate"))
                        if outlook == "unknown":
                            candidates = {normalize_outlook(r.get("ratingValue")) for r in outlook_rows}
                            candidates.discard("unknown")
                            if len(candidates) == 1:
                                outlook = candidates.pop()
                                used_rows.extend(r for r in outlook_rows if normalize_outlook(r.get("ratingValue")) == outlook)
                                dates = {_date(r.get("ratingDate")) for r in used_rows[1:] if r.get("ratingDate")}
                                if len(dates) == 1:
                                    outlook_date = dates.pop()
                    else:
                        alert = str(raw.get("ratingAlertDescription") or "")
                        if "watch" in alert.casefold():
                            watch = normalize_watch(alert)
                        elif "outlook" in alert.casefold():
                            outlook = normalize_outlook(alert)
                    scope_text = " ".join(str(raw.get(k) or "") for k in (type_key, "currencyCapdText", "ratingClassText"))
                    try:
                        axis = infer_rating_axis(kind, agency, grade_text, context=scope_text, status=status)
                    except ValueError:
                        continue
                    # The exact issue endpoint binds the queried instrument;
                    # it cannot turn an issuer-only row into that issue's grade.
                    if axis["scope"] != scope or not axis["scale"] or not axis["term"]:
                        continue
                    output.append({"kind": "credit_rating", "agency": agency, "status": status,
                        "rating": grade_text if status == "rated" else None, **axis,
                        "currency_basis": normalize_currency_basis(raw.get("currencyCapdText")),
                        "entity_name": entity.get("entityLegalName"), "entity_id": str(entity.get(id_key) or "") or None,
                        "rating_date": _date(raw.get("ratingDate") or raw.get("ratingEffectiveDate")),
                        "outlook": outlook, "watch": watch, "outlook_date": outlook_date, "watch_date": watch_date,
                        "security_key": candidate["security_key"], "source_kind": "licensed_api",
                        "evidence_quote": json.dumps(entity, ensure_ascii=False),
                        "response_originalrecord": {"entity": {k: entity.get(k) for k in ("entityLegalName", id_key, "issueId", "instrumentId")}, "ratings": used_rows},
                    })
    return output


def fetch(candidate: dict, settings: dict, budget, *, transport=None) -> dict[str, Any]:
    cfg = settings.get("spglobal", {})
    meta = registry(settings)[0]
    if not meta["configured"]:
        return {"sources": [], "provider_status": [meta]}
    from .security_identifiers import valid_cusip, valid_isin
    symbol = str(candidate.get("symbol") or "").upper()
    secondary = str(candidate.get("secondary_symbol") or "").upper()
    bond = "BOND" in {str(candidate.get(k) or "").upper() for k in ("asset_class", "asset_sub_class")}
    identifier = next((x for x in (symbol, secondary) if valid_cusip(x) or valid_isin(x)), None) if bond else symbol
    if not identifier:
        return {"sources": [], "provider_status": [{**meta, "status": "identity_unavailable"}]}
    scope = "issue" if bond else "issuer"
    identifier_type = ("CUSIP9" if valid_cusip(identifier) else "ISIN") if bond else "TICKER"
    url = BASE + "/api/v1/" + scope
    params = {"identifierType": identifier_type, "identifierValues": identifier,
              "creditRatingAgency": "S&P + MOODY'S + FITCH"}
    try:
        budget.consume()
        with httpx.Client(timeout=min(20, max(0.1, budget.remaining_seconds)), transport=transport,
                          follow_redirects=False, trust_env=False) as client:
            response = client.get(url, params=params, headers={"Authorization": "Bearer " + str(cfg["bearer_token"]), "Accept": "application/json"})
        if response.status_code != 200:
            status = ("authentication_required" if response.status_code == 401 else "entitlement_required" if response.status_code == 403
                      else "rate_limited" if response.status_code == 429 else "provider_unavailable")
            return {"sources": [], "provider_status": [{**meta, "status": status}]}
        payload = response.json()
        source = {"source_id": "api-agency-ratings", "url": url, "title": "S&P Global Agency Ratings",
                  "text": json.dumps(payload, ensure_ascii=False)[:120_000],
                  "retrieved_at": datetime.now(timezone.utc).isoformat(), "_licensed_api": True,
                  "_request_binding": {"security_key": candidate["security_key"], "scope": scope,
                                       "identifier_type": identifier_type, "identifier_value": identifier},
                  "provider": PROVIDER, "structured_data": _observations(payload, {**candidate, "_api_identifier": identifier}, scope)}
        return {"sources": [source], "provider_status": [{**meta, "status": "ok" if source["structured_data"] else "data_unavailable"}]}
    except (httpx.HTTPError, ProviderFailure, ValueError, TypeError, KeyError):
        return {"sources": [], "provider_status": [{**meta, "status": "provider_unavailable"}]}
