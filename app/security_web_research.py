"""Application-owned web evidence and validation behind approved REST routes.

No model, storage driver or database is used here. The model sees fetched source
text through the REST response; its proposed facts are validated by the server.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import re
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from .price_agent import PriceAgent, PriceAgentError, ITEM_PROPERTIES, fetch_public_source
from .security_search import SearchFailure, search_is_configured, search_web, selected_search_provider
from .us_market_providers import RequestBudget, ProviderFailure
from .price_evidence import _source_records, _observation_currency_matches, _observation_record_matches


def _readable_source_fields(text: str) -> set[str]:
    """Guide discovery using fetched content; final facts still need validation."""
    fields: set[str] = set()
    dated = re.search(r"(?<!\d)(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})(?!\d)", text)
    months = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
    dated = dated or re.search(r"(?<!\w)(?:\d{1,2}\s+" + months + r"\s*,?\s*\d{4}|" + months + r"\s+\d{1,2}\s*,?\s*\d{4})(?!\d)", text, re.I)
    price = re.search(r"(?:\b(?:price|last|close|closing|nav)(?![A-Za-z])|מחיר|שער)\s*(?:[A-Za-zא-ת /()-]{0,35}[:=|–-]?\s*)[₪$€£]?\s*\d", text, re.I)
    if dated and price:
        fields.add("prices")
    label = r"(?:company(?:\s+name)?|issuer|industry|name|שם(?:\s+החברה)?|מנפיק|ענף|תעשייה)"
    for match in re.finditer(r"(?<!\w)" + label + r"(?!\w)\s*(?:[:=–-]\s*)?([^|;\n]{1,200})", text, re.I):
        value = match.group(1).strip()
        if re.search(r"[A-Za-zא-ת]", value) and not re.search(r"\b(?:loading|undefined|null|unavailable|please wait)\b|טוען|בטעינה|לא זמין", value, re.I):
            fields.add("profile")
    return fields


def research_sources(candidate: dict[str, Any], settings: dict[str, Any], budget: RequestBudget, *,
                     search: Callable | None = None, fetch: Callable | None = None) -> dict[str, Any]:
    diagnostics = {"search_requests": 0, "source_requests": 0, "read_failures": 0, "identity_rejections": 0, "empty_pages": 0}
    evidence: list[dict[str, str]] = []

    def unavailable(code, stage):
        return {"evidence": [], "source_status": code, "code": code,
                "failure_stage": stage, "diagnostics": dict(diagnostics)}

    def found():
        return {"evidence": evidence, "source_status": "evidence_found", "code": "evidence_found",
                "search_provider": selected_search_provider(settings), "diagnostics": dict(diagnostics)}

    if not search_is_configured(settings):
        return unavailable("search_not_configured", "search_configuration")
    identity = list(dict.fromkeys(str(candidate.get(field) or "").strip() for field in ("symbol", "secondary_symbol", "name", "stock_market")))
    query = " ".join(part for part in identity if part)[:350]
    market = re.sub(r"\s+", "", str(candidate.get("stock_market") or "").upper())
    asset = re.sub(r"[\W_]+", "", str(candidate.get("asset_class") or "").upper())
    if market in {"TASE", "TLV", "TELAVIV"}:
        if asset in {"FUND", "MUTUALFUND"}:
            terms = "מחיר פדיון שער תאריך"
        elif asset in {"EQUITY", "STOCK", "SHARE"}:
            terms = "מניה שער תאריך אגורות"
        else:
            terms = "מחיר שער תאריך מטבע"
    else:
        terms = "price close observation date currency company industry"
    query += " " + terms
    # Legacy injected test/search callbacks use (query,key). Production selects
    # one provider with no hidden fallback or uncounted retry.
    search_call = (lambda query: search(query, str(settings.get("search_api_key") or ""))) if search else (lambda query: search_web(query, settings))
    fetch = fetch or fetch_public_source

    def discover(search_query):
        budget.consume()
        diagnostics["search_requests"] += 1
        results = search_call(search_query)
        if not isinstance(results, list):
            raise SearchFailure("provider_unavailable", "The search service returned an invalid result list.")
        return results

    try:
        results = discover(query)
    except ProviderFailure as exc:
        code = "request_limit" if exc.code == "request_limit" else "provider_unavailable"
        return unavailable(code, "request_budget" if code == "request_limit" else "search_provider")
    except SearchFailure as exc:
        return unavailable(exc.code, "search_provider")
    except (PriceAgentError, ValueError, OSError):
        return unavailable("provider_unavailable", "search_provider")
    queue: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    host_counts: dict[str, int] = {}
    visited_hosts: set[str] = set()
    shell_hosts: set[str] = set()
    generic_shell_hosts: set[str] = set()
    secondary_used = False
    secondary_failure: tuple[str, str] | None = None
    requested = set(candidate.get("missing_fields") or ("prices", "profile"))
    identifiers = [str(candidate.get(key) or "").strip() for key in ("symbol", "secondary_symbol")]

    def add_results(rows):
        for row in rows:
            url = row.get("url") if isinstance(row, dict) else None
            if not isinstance(url, str):
                continue
            try:
                parsed = urlsplit(url)
                host = (parsed.hostname or "").lower().rstrip(".")
                if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.port not in {None, 443} or not re.fullmatch(r"[a-z0-9.-]+", host):
                    continue
                url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
            except ValueError:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            host_counts[host] = host_counts.get(host, 0) + 1
            queue.append((url, host))

    def exact_identifier_url(url):
        return any(value and re.search(r"(?<![A-Za-z0-9])" + re.escape(value) + r"(?![A-Za-z0-9])", urlsplit(url).path, re.I) for value in identifiers)

    def priority(item):
        return item[1] in visited_hosts, not exact_identifier_url(item[0])

    add_results(results)
    while queue or (shell_hosts and not secondary_used and budget.remaining >= 2):
        # Prefer already-discovered alternative hosts to another shell from
        # the same host, or to spending a request on secondary discovery.
        usable = [(url, host) for url, host in queue if host not in shell_hosts]
        # A generic home page at an instrument URL proves those repeated
        # host results cannot establish the listing. Reserve discovery before
        # spending all remaining reads on name-only links and home pages.
        excluded = next((host for host in generic_shell_hosts if host_counts[host] > 1
                         and (not queue or sum(other == host for _, other in queue) > 1
                              or any(other != host for _, other in queue))), None)
        if any(host not in visited_hosts and exact_identifier_url(url) for url, host in usable):
            excluded = None
        if not usable and not excluded:
            # One remaining page can contain a genuine quote on an otherwise
            # dynamic site. Diversify discovery when multiple untried pages
            # would repeat the shell host, keeping two requests for recovery.
            excluded = next((host for host in shell_hosts if not queue or sum(other == host for _, other in queue) > 1), None)
        if excluded and not secondary_used and budget.remaining >= 2:
            secondary_used = True
            # Preserve identifiers and instrument terms, omitting the
            # English market filter that concentrated primary results.
            fallback = " ".join(dict.fromkeys(value for value in identifiers if value))[:300] + " " + terms + " -site:" + excluded
            try:
                add_results(discover(fallback))
            except ProviderFailure as exc:
                code = "request_limit" if exc.code == "request_limit" else "provider_unavailable"
                secondary_failure = (code, "request_budget" if code == "request_limit" else "search_provider")
            except SearchFailure as exc:
                secondary_failure = (exc.code, "search_provider")
            except (PriceAgentError, ValueError, OSError):
                secondary_failure = ("provider_unavailable", "search_provider")
            if secondary_failure:
                break
            continue
        if not usable:
            usable = list(queue)
        url, host = min(usable, key=priority)
        queue.remove((url, host))
        visited_hosts.add(host)
        try:
            budget.consume()
            diagnostics["source_requests"] += 1
            text = fetch(url)
            if not isinstance(text, str) or not text.strip():
                diagnostics["empty_pages"] += 1
                shell_hosts.add(host)
                generic_shell_hosts.add(host)
                continue
            # Classify exactly the bounded text that will reach the model,
            # rather than a fact present only beyond the evidence limit.
            text = " ".join(text.split())[:30_000]
            # Home pages and JavaScript-only shells are discovery failures,
            # not evidence for this instrument. Try the next result within the
            # same budget rather than giving the model an unrelated page.
            identified = any(value and re.search((r"(?<!\d)" if value.isdigit() else r"(?<![A-Za-z0-9])") + re.escape(value)
                                          + (r"(?!\d)" if value.isdigit() else r"(?![A-Za-z0-9])"), text, re.I)
                       for value in identifiers)
            fields = _readable_source_fields(text) if identified else set()
            if not fields.intersection(requested):
                diagnostics["identity_rejections"] += 1
                # Wrong-instrument pages do not establish that an entire host
                # is a shell; generic home/loading and identity-only pages do.
                if identified or re.search(r"javascript|\bloading\b|\bhome\b|דף הבית|טוען|בטעינה", text, re.I):
                    shell_hosts.add(host)
                    if not identified:
                        generic_shell_hosts.add(host)
                continue
            evidence.append({"url": url, "text": text,
                             "retrieved_at": datetime.now(timezone.utc).isoformat()})
            if "prices" in fields or "prices" not in requested:
                return found()
            # Keep a genuine profile while looking for a dated price when both
            # are requested. Exhaustion must not discard useful profile evidence.
        except ProviderFailure as exc:
            if evidence:
                return found()
            code = "request_limit" if exc.code == "request_limit" else "source_read_failed"
            return unavailable(code, "request_budget" if code == "request_limit" else "source_read")
        except (PriceAgentError, ValueError, OSError):
            diagnostics["read_failures"] += 1
            if not budget.remaining:
                break
    if evidence:
        return found()
    if secondary_failure:
        return unavailable(*secondary_failure)
    if not budget.remaining:
        return unavailable("request_limit", "request_budget")
    if diagnostics["read_failures"]:
        return unavailable("source_read_failed", "source_read")
    if diagnostics["identity_rejections"] or diagnostics["empty_pages"]:
        return unavailable("source_identity_unavailable", "source_identity")
    return unavailable("data_unavailable", "search_results")


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
    if excerpt not in " ".join(source["text"].split()) or value not in excerpt or re.search(r"[<>\r\n]", value):
        raise ValueError("The profile value is not literal source evidence")
    from .security_source_context import validate_contextual_profile, supports_context, bond_profile_identity
    context = validate_contextual_profile(source, candidate, item)
    if context is not None:
        return {**item, "value": value.strip(), "retrieved_at": source["retrieved_at"], "source_context": context}
    if supports_context(source, candidate):
        raise ValueError("The source context did not qualify this profile")
    market = str(candidate.get("stock_market") or "")
    aliases = {"NYSE": ("NYSE", "New York Stock Exchange"), "NASDAQ": ("NASDAQ", 'נאסד"ק', "נאסדק"),
               "TASE": ("TASE", "Tel Aviv Stock Exchange", "הבורסה לניירות ערך בתל אביב")}.get(market.upper(), (market,))
    labels = r"(?:industry|ענף|תעשייה)" if field == "industry" else r"(?:company(?:\s+name)?|issuer|name|שם(?:\s+החברה)?|מנפיק)"
    next_field = r"(?:industry|company(?:\s+name)?|issuer|name|ענף|תעשייה|שם(?:\s+החברה)?|מנפיק)\s*[:=]"
    bond = "BOND" in {str(candidate.get(key) or "").upper() for key in ("asset_class", "asset_sub_class")}
    if bond:
        next_field = "(?:" + next_field + r"|\b(?:CUSIP|ISIN|maturity|coupon|currency)\b)"
    field_end = r"(?=\s*(?:$|[;|]|[.!?](?:\s|$)|" + next_field + r"))"
    for record in _source_records(excerpt):
        def token(term):
            return bool(term) and bool(re.search(r"(?<!\w)" + re.escape(str(term)) + r"(?!\w)", record, re.I))
        bond_identity = bond_profile_identity(candidate, record)
        if bond and not bond_identity:
            continue
        if not bond and (not any(token(candidate.get(key)) for key in ("symbol", "secondary_symbol")) or not any(token(alias) for alias in aliases)):
            continue
        if len(re.findall(r"(?<!\w)(?:NASDAQ|NYSE(?:\s+ARCA)?|TASE|LSE|AMEX)(?!\w)", record, re.I)) > 1:
            continue
        if re.search(r"(?<!\w)" + labels + r"\s*[:=–-]?\s*" + re.escape(value) + field_end, record, re.I):
            return {**item, "value": value.strip(), "retrieved_at": source["retrieved_at"]}
    raise ValueError("The profile-bearing source record does not establish this listing and field")


def parse_research_proposal(proposal: Any) -> dict[str, Any] | None:
    if isinstance(proposal, str):
        if len(proposal) > 32_000:
            return None
        fenced = re.fullmatch(r"\s*```(?:json)?\s*\n(.*?)\n```\s*", proposal, re.S | re.I)
        if fenced:
            proposal = fenced[1]
        try:
            proposal = json.loads(proposal)
        except ValueError:
            return None
    return proposal if isinstance(proposal, dict) and not set(proposal) - {"observations", "profiles", "records"} else None


def recover_context_proposal(candidates: dict[str, dict[str, Any]], evidence_by_key: dict[str, Any]) -> dict[str, Any]:
    """Recover unambiguous fetched facts, never repair or interpret model prose."""
    from .security_source_context import context_records
    groups = {}
    for key, candidate in candidates.items():
        for source in evidence_by_key.get(key, []):
            if not isinstance(source, dict) or not isinstance(source.get("source_id"), str):
                continue
            for record in context_records(source, candidate):
                if record["kind"] == "price" and "prices" in candidate.get("missing_fields", []):
                    group = (key, "prices")
                    value = tuple(record.get(field) for field in ("price_input", "price_date", "currency", "quote_unit", "price_basis", "observed_at"))
                elif (record["kind"] == "profile" and "profile" in candidate.get("missing_fields", [])
                      and candidate.get("needs_" + record["field"], True)):
                    group = (key, record["field"])
                    value = record["value"]
                else:
                    continue
                groups.setdefault(group, []).append((value, {"security_key": key, "source_id": source["source_id"], "record_id": record["record_id"]}))
    return {"records": [entries[0][1] for entries in groups.values()
                        if all(value == entries[0][0] for value, _selection in entries)],
            "observations": [], "profiles": []}


def validate_proposals(proposal: Any, candidates: dict[str, dict[str, Any]], evidence_by_key: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Validate facts, not instructions. The application alone applies results."""
    proposal = parse_research_proposal(proposal)
    if proposal is None:
        return {}
    proposal = {**proposal, "observations": list(proposal.get("observations") or []) if isinstance(proposal.get("observations", []), list) else [],
                "profiles": list(proposal.get("profiles") or []) if isinstance(proposal.get("profiles", []), list) else []}
    output: dict[str, dict[str, Any]] = {}
    choices = proposal.get("records") or []
    seen = set()
    if isinstance(choices, list):
        from .security_source_context import context_records
        for choice in choices[:30]:
            if not isinstance(choice, dict) or set(choice) != {"security_key", "source_id", "record_id"}:
                continue
            if any(not isinstance(choice.get(field), str) for field in choice):
                continue
            key = choice["security_key"]
            if key not in candidates:
                continue
            identity = (key, choice["source_id"], choice["record_id"])
            if identity in seen:
                continue
            seen.add(identity)
            sources = [source for source in evidence_by_key.get(key, []) if isinstance(source, dict)
                       and source.get("source_id") == choice["source_id"] and isinstance(source.get("retrieved_at"), str)]
            matched = next((record for source in sources for record in context_records(source, candidates[key])
                            if record["record_id"] == choice["record_id"]), None)
            if matched is None:
                output.setdefault(key, {"observations": [], "profiles": [], "rejected": True})
                continue
            if matched["kind"] == "price":
                proposal["observations"].append({"security_key": key,
                    **{name: matched[name] for name in ITEM_PROPERTIES}})
            else:
                proposal["profiles"].append({"security_key": key,
                    **{name: matched[name] for name in ("field", "value", "source_url", "evidence_quote")}})
    for field in ("observations", "profiles"):
        proposals = proposal.get(field, [])
        if not isinstance(proposals, list) or len(proposals) > 30:
            continue
        for item in proposals:
            if not isinstance(item, dict) or not isinstance(item.get("security_key"), str) or item["security_key"] not in candidates:
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
                    source = sources.get(item["source_url"])
                    from .security_source_context import validate_contextual_observation, supports_context
                    context = validate_contextual_observation(source, candidate, item)
                    if context is not None:
                        record[field].append({**{name: value for name, value in item.items() if name != "security_key"},
                                              "retrieved_at": source["retrieved_at"], "_source_context": context})
                        continue
                    if source and supports_context(source, candidate):
                        raise ValueError("The source context did not qualify this observation")
                    if not _observation_currency_matches(item, candidate):
                        raise ValueError("The observation's currency or raw unit conflicts with this security")
                    if not _observation_record_matches(item, candidate, observed_day):
                        raise ValueError("The price-bearing source record does not establish this listing")
                    source = sources.get(item["source_url"])
                    excerpt = " ".join(item["evidence_quote"].split())
                    if not source or excerpt not in " ".join(source["text"].split()):
                        raise ValueError("The observation was not fetched during this request")
                    start = source["text"].find(excerpt)
                    context = source["text"][max(0, start - 40):start + len(excerpt)]
                    if re.search(r"\bauction\s+price\b|\b(?:coupon|yield|YTM)\b", context, re.I):
                        raise ValueError("Auction, coupon or yield evidence is not a raw Last/Close price")
                    # Reuse the maintained exact-source, date, numeric and unit
                    # checks; this validator never runs its model or REST loop.
                    validator = PriceAgent({}, lambda *_args, **_kwargs: None)
                    validator._evidence = {url: {**entry, "text": " ".join(entry["text"].split())} for url, entry in sources.items()}
                    records = validator._submission({"items": [{name: value for name, value in item.items() if name != "security_key"}]}, candidate, "", "")
                    record[field].extend(records)
                else:
                    record[field].append(_profile_proposal(item, candidate, sources))
            except (ValueError, TypeError, KeyError, OverflowError):
                record["rejected"] = True
    return output
