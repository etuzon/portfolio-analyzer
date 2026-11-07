"""Application-owned web evidence and validation behind approved REST routes.

No model, storage driver or database is used here. The model sees fetched source
text through the REST response; its proposed facts are validated by the server.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import re
from typing import Any, Callable

from .price_agent import PriceAgent, PriceAgentError, ITEM_PROPERTIES, brave_search, fetch_public_source
from .us_market_providers import RequestBudget, ProviderFailure
from .price_evidence import _source_records, _observation_currency_matches, _observation_record_matches


def research_sources(candidate: dict[str, Any], settings: dict[str, Any], budget: RequestBudget, *,
                     search: Callable | None = None, fetch: Callable | None = None) -> dict[str, Any]:
    key = str(settings.get("search_api_key") or "")
    if not key:
        return {"evidence": [], "source_status": "research_unavailable", "code": "research_unavailable"}
    query = " ".join(str(candidate.get(field) or "") for field in ("symbol", "secondary_symbol", "name", "stock_market"))
    query = query.strip()[:350] + " price close observation date currency company industry"
    search = search or brave_search
    fetch = fetch or fetch_public_source
    try:
        budget.consume()
        results = search(query, key)
    except ProviderFailure as exc:
        code = "request_limit" if exc.code == "request_limit" else "provider_unavailable"
        return {"evidence": [], "source_status": code, "code": code}
    except (PriceAgentError, ValueError, OSError):
        return {"evidence": [], "source_status": "research_unavailable", "code": "research_unavailable"}
    if not isinstance(results, list):
        return {"evidence": [], "source_status": "provider_unavailable", "code": "provider_unavailable"}
    # Return a real source page, never a search snippet. A failed first URL may
    # use the next search result, within the same shared upstream budget.
    for result in results[:3]:
        url = result.get("url") if isinstance(result, dict) else None
        if not isinstance(url, str):
            continue
        try:
            budget.consume()
            text = fetch(url)
            if not isinstance(text, str) or not text.strip():
                continue
            return {"evidence": [{"url": url, "text": " ".join(text.split())[:30_000],
                                   "retrieved_at": datetime.now(timezone.utc).isoformat()}],
                    "source_status": "evidence_found", "code": "evidence_found"}
        except ProviderFailure as exc:
            code = "request_limit" if exc.code == "request_limit" else "provider_unavailable"
            return {"evidence": [], "source_status": code, "code": code}
        except (PriceAgentError, ValueError, OSError):
            if not budget.remaining:
                break
    code = "request_limit" if not budget.remaining else "data_unavailable"
    return {"evidence": [], "source_status": code, "code": code}


def _profile_proposal(item: dict[str, Any], candidate: dict[str, Any], sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if set(item) != {"security_key", "field", "value", "source_url", "evidence_quote"}:
        raise ValueError("Unsupported profile fields")
    field, value, excerpt = item["field"], item["value"], item["evidence_quote"]
    source = sources.get(item["source_url"])
    if field not in {"name", "industry"} or not isinstance(value, str) or not 1 <= len(value.strip()) <= 200:
        raise ValueError("Unsupported profile value")
    if "profile" not in candidate.get("missing_fields", []):
        raise ValueError("This profile was not missing")
    if not source or not isinstance(excerpt, str) or not 1 <= len(excerpt) <= 2000:
        raise ValueError("Missing fetched evidence")
    excerpt = " ".join(excerpt.split())
    if excerpt not in source["text"] or value not in excerpt or re.search(r"[<>\r\n]", value):
        raise ValueError("The profile value is not literal source evidence")
    market = str(candidate.get("stock_market") or "")
    aliases = {"NYSE": ("NYSE", "New York Stock Exchange"), "NASDAQ": ("NASDAQ", 'נאסד"ק', "נאסדק"),
               "TASE": ("TASE", "Tel Aviv Stock Exchange", "הבורסה לניירות ערך בתל אביב")}.get(market.upper(), (market,))
    labels = r"(?:industry|ענף|תעשייה)" if field == "industry" else r"(?:company(?:\s+name)?|issuer|name|שם(?:\s+החברה)?|מנפיק)"
    next_field = r"(?:industry|company(?:\s+name)?|issuer|name|ענף|תעשייה|שם(?:\s+החברה)?|מנפיק)\s*[:=]"
    field_end = r"(?=\s*(?:$|[;|]|[.!?](?:\s|$)|" + next_field + r"))"
    for record in _source_records(excerpt):
        def token(term):
            return bool(term) and bool(re.search(r"(?<!\w)" + re.escape(str(term)) + r"(?!\w)", record, re.I))
        if not any(token(candidate.get(key)) for key in ("symbol", "secondary_symbol")) or not any(token(alias) for alias in aliases):
            continue
        if len(re.findall(r"(?<!\w)(?:NASDAQ|NYSE(?:\s+ARCA)?|TASE|LSE|AMEX)(?!\w)", record, re.I)) > 1:
            continue
        if re.search(r"(?<!\w)" + labels + r"\s*[:=–-]?\s*" + re.escape(value) + field_end, record, re.I):
            return {**item, "value": value.strip(), "retrieved_at": source["retrieved_at"]}
    raise ValueError("The profile-bearing source record does not establish this listing and field")


def validate_proposals(proposal: Any, candidates: dict[str, dict[str, Any]], evidence_by_key: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Validate facts, not instructions. The application alone applies results."""
    if isinstance(proposal, str):
        if len(proposal) > 32_000:
            return {}
        try:
            proposal = json.loads(proposal)
        except ValueError:
            return {}
    if not isinstance(proposal, dict) or set(proposal) - {"observations", "profiles"}:
        return {}
    output: dict[str, dict[str, Any]] = {}
    for field in ("observations", "profiles"):
        proposals = proposal.get(field, [])
        if not isinstance(proposals, list) or len(proposals) > 30:
            continue
        for item in proposals:
            if not isinstance(item, dict) or item.get("security_key") not in candidates:
                continue
            key = item["security_key"]
            candidate = candidates[key]
            sources = {entry["url"]: entry for entry in evidence_by_key.get(key, [])
                       if isinstance(entry, dict) and all(isinstance(entry.get(name), str) for name in ("url", "text", "retrieved_at"))}
            record = output.setdefault(key, {"observations": [], "profiles": [], "rejected": False})
            try:
                if field == "observations":
                    if "prices" not in candidate.get("missing_fields", []):
                        raise ValueError("The price was not missing")
                    if set(item) != {"security_key", *ITEM_PROPERTIES}:
                        raise ValueError("Unsupported price fields")
                    observed_day = date.fromisoformat(item["price_date"])
                    if not date.today() - timedelta(days=7) <= observed_day <= date.today():
                        raise ValueError("Current enrichment requires an observation from the last seven calendar days")
                    if not _observation_currency_matches(item, candidate):
                        raise ValueError("The observation's currency or raw unit conflicts with this security")
                    if not _observation_record_matches(item, candidate, observed_day):
                        raise ValueError("The price-bearing source record does not establish this listing")
                    source = sources.get(item["source_url"])
                    excerpt = " ".join(item["evidence_quote"].split())
                    if not source or excerpt not in source["text"]:
                        raise ValueError("The observation was not fetched during this request")
                    start = source["text"].find(excerpt)
                    context = source["text"][max(0, start - 40):start + len(excerpt)]
                    if re.search(r"\bauction\s+price\b|\b(?:coupon|yield|YTM)\b", context, re.I):
                        raise ValueError("Auction, coupon or yield evidence is not a raw Last/Close price")
                    # Reuse the maintained exact-source, date, numeric and unit
                    # checks; this validator never runs its model or REST loop.
                    validator = PriceAgent({}, lambda *_args, **_kwargs: None)
                    validator._evidence = sources
                    records = validator._submission({"items": [{name: value for name, value in item.items() if name != "security_key"}]}, candidate, "", "")
                    record[field].extend(records)
                else:
                    record[field].append(_profile_proposal(item, candidate, sources))
            except (ValueError, TypeError, KeyError, OverflowError):
                record["rejected"] = True
    return output
