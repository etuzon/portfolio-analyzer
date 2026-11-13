"""Source-bound company/issue credit-rating facts; no risk-score calculation.

The model may select an extracted record ID. It cannot supply a grade. Public
JSON-LD cannot authorize licensed API facts. Source retrieval and final display
selection belong to the service layer; these helpers never perform I/O.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import html
import ipaddress
import json
import re
import unicodedata
from typing import Any
from urllib.parse import parse_qs, urlsplit


AGENCIES = ("moodys", "sp", "fitch")
STATUSES = frozenset({"rated", "unrated", "withdrawn", "not_found", "not_checked", "unavailable", "conflicting"})
OUTLOOKS = frozenset({"positive", "negative", "stable", "developing", "unknown"})
WATCHES = frozenset({"positive", "negative", "developing", "none", "unknown"})
_AGENCY_PATTERNS = {
    "moodys": re.compile(r"\bMoody(?:['’]s|s)?\b", re.I),
    "sp": re.compile(r"(?<!\w)(?:S\s*&\s*P(?:\s+Global)?|Standard\s*(?:&|and)\s*Poor['’]?s)(?!\w)", re.I),
    "fitch": re.compile(r"\bFitch(?:\s+Ratings)?\b", re.I),
}
_LONG = {
    "moodys": ("Aaa", "Aa1", "Aa2", "Aa3", "A1", "A2", "A3", "Baa1", "Baa2", "Baa3", "Ba1", "Ba2", "Ba3", "B1", "B2", "B3", "Caa1", "Caa2", "Caa3", "Ca", "C"),
    "sp": ("AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "SD", "D"),
    "fitch": ("AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "RD", "D"),
}
_SHORT = {"moodys": ("P-1", "P-2", "P-3", "NP"),
          "sp": ("A-1+", "A-1", "A-2", "A-3", "B", "C", "SD", "D"),
          "fitch": ("F1+", "F1", "F2", "F3", "B", "C", "RD", "D")}
_GRADE_TOKEN = r"(?:Aaa|Aa[123]|A[123]|Baa[123]|Ba[123]|B[123]|Caa[123]|Ca|AAA|AA[+-]?|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?|CCC[+-]?|CC|C|SD|RD|D|P-[123]|A-[123]\+?|F[123]\+?|NP)"
_DATE_PATTERN = (r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|"
                 r"\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{4}|"
                 r"\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{4}|"
                 r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2},?\s+\d{4})")
_FIELDS = ("agency", "status", "rating", "scope", "scale", "term", "rating_type", "entity_name", "entity_id", "rating_date", "outlook", "outlook_date", "watch", "watch_date", "currency_basis", "observed_at")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _plain(value: Any) -> str:
    value = html.unescape(str(value or "")).replace("−", "-").replace("–", "-")
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    return _text(re.sub(r"[*_`#]+", "", value))


def _article_link_spans(text):
    """Whole inline links and bare URLs, retaining the original offsets."""
    spans, brackets = [], []
    index = 0
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == "[":
            brackets.append(index)
        elif text[index] == "]" and brackets:
            start = brackets.pop()
            if text[index + 1:index + 2] == "(":
                end, depth, angle = index + 2, 1, False
                while end < len(text):
                    char = text[end]
                    if char == "\\":
                        end += 2
                        continue
                    if char == "<":
                        angle = True
                    elif char == ">":
                        angle = False
                    elif not angle and char == "(":
                        depth += 1
                    elif not angle and char == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    end += 1
                if depth == 0:
                    spans.append((start, end + 1))
                    index = end + 1
                    continue
        index += 1
    spans.extend(match.span() for match in re.finditer(r"https?://[^\s<>]+", text, re.I))
    return spans


def _inside_link(match, spans):
    return any(start <= match.start() and match.end() <= end for start, end in spans)


def normalize_agency(value: Any) -> str:
    compact = re.sub(r"[^a-z]", "", str(value or "").lower())
    if compact in {"moodys", "moody", "moodysratings", "moodysinvestorsservice", "moodysinvestorservice"}:
        return "moodys"
    if compact in {"sp", "spglobal", "spglobalratings", "standardpoors", "standardandpoors", "sandp"}:
        return "sp"
    if compact in {"fitch", "fitchratings"}:
        return "fitch"
    raise ValueError("Unknown credit-rating agency")


def normalize_grade(value: Any, agency: Any, term: str = "long_term", scale: str = "global") -> str:
    agency = normalize_agency(agency)
    if not isinstance(value, str) or not 1 <= len(value) <= 80:
        raise ValueError("A literal credit-rating symbol is required")
    grade = _plain(value).strip(" '\"‘’“”")
    if _unsupported_qualifier(grade):
        raise ValueError("Qualified/provisional credit rating is unsupported")
    if term not in {"long_term", "short_term"} or scale not in {"global", "national"}:
        raise ValueError("Unknown rating scale or term")
    if scale == "national":
        bases = sorted((_LONG if term == "long_term" else _SHORT)[agency], key=len, reverse=True)
        national = r"(?:[A-Za-z]{2,3})?(?:" + "|".join(re.escape(base) for base in bases) + r")(?:\([A-Za-z]{2,4}\)|\.[A-Za-z]{2,4})?"
        if not re.fullmatch(national, grade):
            raise ValueError("Unsupported national-scale rating symbol")
        return grade
    mapping = {symbol.casefold(): symbol for symbol in (_LONG if term == "long_term" else _SHORT)[agency]}
    if grade.casefold() not in mapping:
        raise ValueError("Symbol does not belong to this agency's declared global scale and term")
    return mapping[grade.casefold()]


def _unsupported_qualifier(value):
    return bool(re.search(r"\(\s*(?:P|EXP|PI|PRELIM(?:INARY)?|SF|HYB)\s*\)", _plain(value), re.I))


def normalize_outlook(value: Any) -> str:
    value = _plain(value).casefold()
    value = re.sub(r"^(?:rating\s+)?outlook\s*[:=-]?\s*|\s+(?:rating\s+)?outlook$", "", value).strip()
    return {"positive": "positive", "pos": "positive", "negative": "negative", "neg": "negative",
            "stable": "stable", "sta": "stable", "developing": "developing", "dev": "developing",
            "evolving": "developing"}.get(value, "unknown")


def normalize_watch(value: Any) -> str:
    value = _plain(value).casefold()
    if value in {"none", "not on watch", "no watch", "not under review", "no rating watch", "not on creditwatch"}:
        return "none"
    value = re.sub(r"^(?:on\s+)?(?:rating\s+watch|creditwatch|watch|(?:on\s+|under\s+)?review\s+for)\s*[:=-]?\s*", "", value)
    value = value.removeprefix("possible ")
    if value in {"positive", "pos", "upgrade", "review for upgrade", "on review for upgrade", "rating watch positive", "creditwatch positive"}:
        return "positive"
    if value in {"negative", "neg", "downgrade", "review for downgrade", "on review for downgrade", "rating watch negative", "creditwatch negative"}:
        return "negative"
    if value in {"developing", "evolving", "direction uncertain", "review direction uncertain", "on review direction uncertain", "rating watch evolving", "creditwatch developing"}:
        return "developing"
    return "unknown"


def normalize_currency_basis(value: Any) -> str | None:
    value = re.sub(r"[ _-]+", "", _plain(value).casefold())
    if value in {"local", "lc", "localcurrency"}:
        return "local_currency"
    if value in {"foreign", "fc", "foreigncurrency"}:
        return "foreign_currency"
    return None


def _date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    value = _text(value)
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        pass
    value = value.replace(".", "")
    for fmt in ("%d/%m/%Y", "%d-%b-%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _timestamp(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value).isoformat()
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.isoformat()
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        day = _date(value)
        return day


def _entity(value: Any) -> str:
    value = unicodedata.normalize("NFKD", _plain(value)).casefold().replace("&", " and ")
    value = "".join(char for char in value if not unicodedata.combining(char))
    # These are spellings of the same legal form, not removable stop words.
    # Apply the same expansion to source clauses and candidate names so that
    # parent/bank/holdings and other substantive identity tokens remain bound.
    forms = {"corp": "corporation", "inc": "incorporated", "ltd": "limited"}
    return " ".join(forms.get(word, word) for word in re.findall(r"[^\W_]+", value, re.UNICODE))


def _names(candidate: dict[str, Any]) -> set[str]:
    # Legal-entity identity wins over a looser display/security name.
    names = [next((candidate.get(key) for key in ("legal_entity_name", "issuer_name", "name")
                   if isinstance(candidate.get(key), str) and candidate[key].strip()), None)]
    aliases = candidate.get("issuer_aliases") or []
    if isinstance(aliases, list):
        names.extend(value for value in aliases if isinstance(value, str))
    return {_entity(name) for name in names if isinstance(name, str) and len(_entity(name)) >= 3}


def _matches_entity(name: str, candidate: dict[str, Any]) -> bool:
    return _entity(name) in _names(candidate)


def _legal_subject(value):
    """The complete named subject, never an arbitrary suffix of its name."""
    value = value.rstrip().rstrip(")]").rstrip()
    introductions = list(re.finditer(r"\b(?:affirm(?:s|ed)?|revis(?:es|ed)|assign(?:s|ed)|upgrad(?:es|ed)|downgrad(?:es|ed)|raised|lowered)\s+|\bIn our view,\s*", value, re.I))
    if introductions:
        tail = value[introductions[-1].end():].strip()
        if tail and not re.search(r"[()\[\]]|['’]s|\b(?:rating|outlook|at|to|their|its)\b", tail, re.I):
            return _entity(tail)
    words = list(re.finditer(r"[^\W_]+(?:['’][^\W_]+)*", value, re.UNICODE))
    if not words:
        return ""
    particles = {"de", "du", "des", "of", "the", "and", "la", "le", "van", "von", "del", "da", "di"}
    selected = []
    boundary = len(value)
    for word in reversed(words):
        literal = word[0]
        if not re.fullmatch(r"[\s,.&-]*", value[word.end():boundary]):
            break
        named = any(char.isupper() for char in literal) or (literal.isalpha() and literal.lower() == literal.upper())
        if not named and literal.casefold() not in particles:
            break
        selected.append(word)
        boundary = word.start()
    selected.reverse()
    while selected and selected[0][0] in {"of", "and"}:
        selected.pop(0)
    return _entity(value[selected[0].start():selected[-1].end()]) if selected else ""


def _article_aliases(text, candidate):
    """Only an explicit source-local legal-name (ACRONYM) definition binds.

    Do not infer an alias from a ticker or an unrelated heading. Optional S.A.
    is accepted here as a literal legal-form extension of an already named
    issuer, never removed from the general legal-entity comparison.
    """
    bindings, conflicting_aliases = [], set()
    names = _names(candidate)
    excluded = {"IDR", "ICR", "SCP", "SACP", "FFO", "DCF", "EBITDA", "GRE", "LT", "ST",
                "SA", "S.A.", "AG", "PLC", "LLC", "INC", "CORP", "CO", "LTD"}
    excluded.update(value.upper() for values in _LONG.values() for value in values)
    pattern = r"\(\s*['\"‘“]?(?P<alias>[A-Z][A-Z0-9&.-]{1,15})(?:['’]s)?['\"’”]?\s*\)"
    links = _article_link_spans(text)
    for match in re.finditer(pattern, text[:8000]):
        if _inside_link(match, links):
            continue
        alias = match["alias"]
        if alias in excluded:
            continue
        prefix = text[max(0, match.start() - 300):match.start()].rstrip()
        prefix = re.sub(r"['’]s$", "", prefix).rstrip()
        normalized = _legal_subject(prefix)
        targets = [name for name in names if normalized == name
                   or len(name.split()) >= 3 and normalized in {name + " s a", name + " sa"}]
        if not targets:
            if normalized and normalized != _entity(alias):
                conflicting_aliases.add(alias)
            continue
        # Retain the literal definition, separately from the canonical issuer
        # used as the comparable axis and history identity.
        definition = text[max(0, match.start() - 300):match.end()]
        bindings.append((alias, definition))
    aliases = [alias for alias, _ in bindings if alias not in conflicting_aliases]
    definitions = [definition for alias, definition in bindings if alias not in conflicting_aliases]
    if not aliases:
        return candidate, []
    return {**candidate, "issuer_aliases": list(candidate.get("issuer_aliases") or []) + aliases,
            "_source_bound_aliases": aliases}, definitions


def _url(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 2500:
        raise ValueError("Source URL is required")
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Source must be credential-free HTTPS")
        if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}:
            raise ValueError("Private source URL")
        try:
            if not ipaddress.ip_address(parsed.hostname).is_global:
                raise ValueError("Private source URL")
        except ValueError as exc:
            if "Private" in str(exc):
                raise
        if any(re.search(r"(?:token|password|secret|api[_-]?key|authorization)", key, re.I) for key in parse_qs(parsed.query)):
            raise ValueError("Source URLs must not contain credentials")
    except (TypeError, ValueError) as exc:
        raise ValueError("Unsafe source URL") from exc
    return value


def source_authority(source: dict[str, Any], candidate: dict[str, Any]) -> str | None:
    """Primary-source qualification from server-owned provenance only."""
    try:
        host = (urlsplit(_url(source.get("url"))).hostname or "").lower()
    except (AttributeError, ValueError):
        return None
    if source.get("_licensed_api") is True:
        return ("licensed_api" if source.get("provider") == "spglobal_agency_ratings"
                and host == "xpressapi.marketplace.spglobal.com" else None)
    if any(host == domain or host.endswith("." + domain) for domain in ("moodys.com", "spglobal.com", "fitchratings.com")):
        return "agency_public"
    if any(host == domain or host.endswith("." + domain) for domain in ("sec.gov", "magna.isa.gov.il", "maya.tase.co.il")):
        return "regulatory"
    if source.get("_issuer_source_verified") is True:
        return "issuer_ir"
    domains = candidate.get("verified_issuer_domains") or []
    if isinstance(domains, list):
        for domain in domains:
            if not isinstance(domain, str):
                continue
            try:
                domain = urlsplit(domain).hostname if "://" in domain else domain
            except ValueError:
                continue
            if not isinstance(domain, str):
                continue
            domain = domain.lower().strip(".")
            if domain and (host == domain or host.endswith("." + domain)):
                return "issuer_ir"
    return None


def _kind(label: str) -> tuple[str, str, str] | None:
    label = _plain(label).casefold().replace("-", " ")
    term = "short_term" if "short term" in label or re.search(r"\bST\b", label, re.I) else "long_term"
    if "outlook" in label or "watch" in label or label in {"date", "rating date"}:
        return None
    if "issuer default" in label or re.search(r"\bIDR\b", label, re.I):
        return "issuer", term, "issuer_default"
    if "issuer" in label or "corporate credit" in label:
        return "issuer", term, "issuer"
    if "corporate family" in label:
        return "issuer", term, "corporate_family"
    if "deposit" in label:
        return "issuer", term, "deposit"
    if "senior unsecured" in label:
        return "issuer", term, "senior_unsecured_class"
    if "junior subordinated" in label:
        return "issuer", term, "junior_subordinated_class"
    if "subordinated" in label:
        return "issuer", term, "subordinated_class"
    if "preferred" in label:
        return "issuer", term, "preferred_stock_class"
    if "viability" in label or "baseline credit" in label:
        return "issuer", term, "viability"
    if "issue" in label or "bond" in label:
        return "issue", term, "issue"
    return None


def infer_rating_axis(raw_type: Any, agency: Any, rating: Any, *, scale: Any = None,
                      term: Any = None, context: Any = "", status: Any = None) -> dict[str, Any]:
    """Resolve documented native types; an untyped symbol cannot imply an axis."""
    agency = normalize_agency(agency)
    label = _plain(raw_type)
    details = label + " " + _plain(context)
    kind = _kind(label)
    result = {"scope": kind[0] if kind else None, "rating_type": kind[2] if kind else None,
              "scale": None, "term": None}
    declared_term = _plain(term).casefold().replace("-", "_").replace(" ", "_")
    if declared_term in {"long_term", "lt", "long"}:
        result["term"] = "long_term"
    elif declared_term in {"short_term", "st", "short"}:
        result["term"] = "short_term"
    elif re.search(r"\bshort[ _-]*term\b|\bST\b", details, re.I):
        result["term"] = "short_term"
    elif re.search(r"\blong[ _-]*term\b|\bLT\b", details, re.I):
        result["term"] = "long_term"
    declared_scale = _plain(scale).casefold()
    national = bool(re.search(r"\bnational\b", details, re.I))
    # A standard symbol with a national country marker must not enter global
    # aggregation even when an upstream generic type omitted the word National.
    grade = _plain(rating)
    if _unsupported_qualifier(grade):
        return result
    if re.search(r"\([A-Za-z]{2,4}\)$|\.[A-Za-z]{2,4}$|^(?:il|mx|br|za|tw|ra|ua|co)(?=[A-Z])", grade):
        national = True
    if national:
        if declared_scale == "global":
            raise ValueError("National rating conflicts with a global scale declaration")
        result["scale"] = "national"
    elif declared_scale in {"global", "national"}:
        result["scale"] = declared_scale
    elif re.search(r"\bglobal\b|\binternational\b", details, re.I):
        result["scale"] = "global"
    elif kind and kind[2] in {"issuer", "issuer_default", "issue"} and result["term"]:
        # These explicit native issuer/IDR/issue labels refer to the standard
        # agency scale unless a national label/symbol says otherwise.
        symbol_status, _symbol = _status_grade(str(rating or ""))
        if status in {"unrated", "withdrawn"} or symbol_status in {"unrated", "withdrawn"}:
            result["scale"] = "global"
        else:
            try:
                normalize_grade(rating, agency, result["term"], "global")
            except ValueError:
                pass
            else:
                result["scale"] = "global"
    return result


def is_primary_observation(record: dict[str, Any], candidate: dict[str, Any] | None = None) -> bool:
    if record.get("scale") != "global" or record.get("term") != "long_term":
        return False
    bond = candidate and "BOND" in {str(candidate.get(key) or "").upper() for key in ("asset_class", "asset_sub_class")}
    if bond and record.get("scope") == "issue":
        return True
    return record.get("scope") == "issuer" and record.get("rating_type") in {"issuer", "issuer_default"}


def _make_record(source, candidate, fields, excerpt, claims, **extra):
    canonical = {key: fields.get(key) for key in _FIELDS}
    if canonical["status"] not in STATUSES or canonical["scope"] not in {"issuer", "issue"}:
        raise ValueError("Invalid rating status or scope")
    if canonical["scale"] not in {"global", "national"} or canonical["term"] not in {"long_term", "short_term"}:
        raise ValueError("Invalid rating scale or term")
    if not isinstance(canonical["entity_name"], str) or not 1 <= len(canonical["entity_name"]) <= 300:
        raise ValueError("Rated legal entity is required")
    if not isinstance(canonical["rating_type"], str) or not 1 <= len(canonical["rating_type"]) <= 150:
        raise ValueError("Explicit rating type is required")
    for field in ("rating_date", "outlook_date", "watch_date"):
        if canonical[field] not in (None, "") and not _date(canonical[field]):
            raise ValueError("Invalid explicit " + field)
        canonical[field] = _date(canonical[field])
    if canonical["observed_at"] not in (None, "") and not _timestamp(canonical["observed_at"]):
        raise ValueError("Invalid explicit observation date")
    canonical.update(outlook=normalize_outlook(canonical.get("outlook")), watch=normalize_watch(canonical.get("watch")))
    canonical["currency_basis"] = normalize_currency_basis(canonical.get("currency_basis"))
    canonical["observed_at"] = _timestamp(canonical.get("observed_at"))
    canonical["agency"] = normalize_agency(canonical["agency"])
    rating_raw = fields.get("rating") if canonical["status"] == "rated" else None
    if canonical["status"] == "rated":
        canonical["rating"] = normalize_grade(canonical["rating"], canonical["agency"], canonical["term"], canonical["scale"])
    else:
        canonical["rating"] = None
    material = {**canonical, "source_url": source["url"], "evidence_quote": excerpt, **extra}
    record_id = "credit-" + hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:24]
    return {"record_id": record_id, "kind": "credit_rating", **canonical,
            "source_id": source.get("source_id"), "source_url": source["url"],
            "security_key": candidate.get("security_key"), "evidence_quote": excerpt,
            "claims": claims, "fetched_at": source.get("retrieved_at"),
            "rating_raw": rating_raw,
            "source_kind": source_authority(source, candidate),
            "_source": source, **extra}


def _cells(line: str) -> list[str]:
    return [_plain(cell) for cell in line.strip().strip("|").split("|")]


def _entity_before(lines: list[str], index: int, candidate: dict[str, Any]) -> tuple[str, int] | None:
    for at in range(index - 1, max(-1, index - 16), -1):
        value = _plain(lines[at]).strip(" :|")
        if not value or set(value) <= {"-", ":", "|", " "}:
            continue
        value = re.sub(r"\s+Credit Ratings?$", "", value, flags=re.I)
        if _matches_entity(value, candidate):
            return value, at
        # A nearer legal-entity heading terminates the search. It must never
        # inherit a rating from a preceding parent/bank/broker-dealer block.
        if (re.search(r"\b(?:bank|inc|plc|llc|corporation|company|co\.?|s\.?a\.?|n\.?a\.?)\b", value, re.I)
                and not _kind(value) and not re.search(r"outlook|rating|Moody|Fitch|S&P", value, re.I)):
            return None
    return None


def _status_grade(value: str) -> tuple[str, str | None]:
    cleaned = _plain(value).strip(" '\"‘’“”")
    if cleaned.casefold() in {"nr", "n.r.", "not rated", "unrated"}:
        return "unrated", None
    if cleaned.casefold() in {"wr", "wd", "withdrawn", "rating withdrawn", "ratings withdrawn"}:
        return "withdrawn", None
    return "rated", cleaned


def _table_records(source, candidate):
    lines = source["text"].splitlines()
    output = []
    for index, line in enumerate(lines):
        if "|" not in line:
            continue
        cells = _cells(line)
        columns = {}
        for col, cell in enumerate(cells):
            found = [key for key, pattern in _AGENCY_PATTERNS.items() if pattern.search(cell)]
            if len(found) == 1:
                columns[col] = found[0]
        if len(set(columns.values())) < 2:
            continue
        if len(columns) == len(cells) and min(columns) == 0:
            # Some text readers omit the empty top-left cell of an IR table.
            columns = {col + 1: agency for col, agency in columns.items()}
        owner = _entity_before(lines, index, candidate)
        if not owner:
            continue
        name, start = owner
        rows = []
        for at in range(index + 1, min(len(lines), index + 36)):
            row = _cells(lines[at]) if "|" in lines[at] else []
            if row and set("".join(row)) <= {"-", ":", " "}:
                continue
            if len(row) < max(columns) + 1:
                if rows and _plain(lines[at]):
                    break
                continue
            rows.append((at, row))
        if not rows:
            continue
        end = rows[-1][0]
        original = source.get("_original_source")
        spans = source.get("_line_spans")
        if isinstance(original, dict) and isinstance(spans, list):
            original_lines = original["text"].splitlines()
            excerpt = "\n".join(original_lines[spans[start][0]:spans[end][1] + 1])
            source_for_record = original
        else:
            excerpt = "\n".join(lines[start:end + 1])
            source_for_record = source
        if len(excerpt) > 12000:
            continue
        outlooks, watches, dates, outlook_dates, watch_dates = {}, {}, {}, {}, {}
        for _at, row in rows:
            label = row[0].casefold()
            for col, agency in columns.items():
                if "date" in label and "outlook" in label:
                    outlook_dates[agency] = _date(row[col])
                elif "date" in label and any(word in label for word in ("watch", "review")):
                    watch_dates[agency] = _date(row[col])
                elif "outlook" in label:
                    outlooks[agency] = normalize_outlook(row[col])
                elif any(word in label for word in ("watch", "review")):
                    watches[agency] = normalize_watch(row[col])
                if re.fullmatch(r"(?:rating|rating action|effective) date", label):
                    dates[agency] = _date(row[col])
        for at, row in rows:
            kind = _kind(row[0])
            if not kind:
                continue
            scope, term, rating_type = kind
            # A generic debt-class row does not establish one exact ISIN/CUSIP.
            if scope == "issue":
                continue
            for col, agency in columns.items():
                status, grade = _status_grade(row[col])
                try:
                    fields = dict(agency=agency, status=status, rating=grade, scope=scope,
                                  scale="national" if "national" in row[0].casefold() else "global",
                                  term=term, rating_type=rating_type, entity_name=name, entity_id=None,
                                  rating_date=dates.get(agency), outlook=outlooks.get(agency, "unknown"),
                                  outlook_date=outlook_dates.get(agency), watch=watches.get(agency, "unknown"),
                                  watch_date=watch_dates.get(agency), currency_basis=None, observed_at=None)
                    def literal_line(number):
                        return "\n".join(original_lines[spans[number][0]:spans[number][1] + 1]) if isinstance(original, dict) and isinstance(spans, list) else lines[number]
                    output.append(_make_record(source_for_record, candidate, fields, excerpt,
                                               {"entity": literal_line(start), "agency_columns": literal_line(index), "rating_row": literal_line(at)},
                                               snapshot_kind="issuer_rating_table"))
                except ValueError:
                    continue
    return output


def _flattened_table_source(source):
    """Restore cell boundaries only for a literal three-agency line sequence."""
    raw_lines = source["text"].splitlines()
    indexed = [(number, line) for number, line in enumerate(raw_lines) if _plain(line)]
    lines = [line for _number, line in indexed]
    converted = []
    spans = []
    index = 0
    changed = False
    while index < len(lines):
        agencies = []
        for line in lines[index:index + 3]:
            found = [key for key, pattern in _AGENCY_PATTERNS.items() if pattern.fullmatch(_plain(line))]
            if len(found) != 1:
                break
            agencies.append(found[0])
        if len(agencies) == 3 and len(set(agencies)) == 3:
            converted.append(" | " + " | ".join(lines[index:index + 3]))
            spans.append((indexed[index][0], indexed[index + 2][0]))
            index += 3
            while index + 3 < len(lines):
                label = _plain(lines[index])
                if not (_kind(label) or re.search(r"outlook|watch|review|rating date", label, re.I)):
                    break
                values = [_plain(value) for value in lines[index + 1:index + 4]]
                converted.append(label + " | " + " | ".join(values))
                spans.append((indexed[index][0], indexed[index + 3][0]))
                index += 4
            changed = True
        else:
            converted.append(lines[index])
            spans.append((indexed[index][0], indexed[index][0]))
            index += 1
    return {**source, "text": "\n".join(converted), "_original_source": source, "_line_spans": spans} if changed else None


def _publication(source, text):
    explicit = source.get("published_at") or source.get("publication_date") or source.get("observed_at")
    if explicit and _timestamp(explicit):
        return _timestamp(explicit)
    # S&P public action pages put the native date/time immediately before
    # their article title. A dated event or related-reference line elsewhere
    # in the body does not establish this document's publication date.
    headers = re.compile(
        r"(?im)^[ \t]*(?:\*[ \t]+)?(?P<day>" + _DATE_PATTERN + r")[ \t]*\|[ \t]*"
        r"(?:[01]?\d|2[0-3]):[0-5]\d[ \t]+(?:UTC|GMT|EST|EDT|CST|CDT|MST|MDT|PST|PDT)[ \t]*\r?\n"
        r"(?:[ \t]*\r?\n)*[ \t]*#[ \t]+(?P<headline>[^\r\n]+)")
    owner = re.sub(r"\s*\|\s*S\s*&\s*P(?:\s+Global)?\s+Ratings\s*$", "", str(source.get("title") or ""), flags=re.I)
    title_words = lambda value: re.findall(r"[^\W_]+|[+-]", _plain(value).casefold())
    owner_words = title_words(owner)
    actions = {"upgraded", "downgraded", "affirmed", "assigned", "revised", "raised", "lowered", "placed", "withdrawn"}
    # A truncated title can identify its longer headline only after supplying
    # a named subject and action. Generic/name-only prefixes are ambiguous.
    prefix_length = 2 if owner_words[:2] == ["research", "update"] else 0
    meaningful = any(index > prefix_length and word in actions for index, word in enumerate(owner_words))
    owned_dates = {_timestamp(header["day"]) for header in headers.finditer(text[:5000])
                   if meaningful and title_words(header["headline"])[:len(owner_words)] == owner_words}
    if owned_dates:
        return next(iter(owned_dates)) if len(owned_dates) == 1 else None
    found = re.search(r"(?im)^\s*(?:published\s*[:：]?\s*)?(" + _DATE_PATTERN + r")\s*$", text[:5000])
    if found:
        return _timestamp(found[1])
    # Agency-authored datelines establish publication, not an arbitrary event
    # date mentioned later in the report or a footer copyright year.
    dateline = re.search(
        r"(?im)^\s*(?:Fitch(?:\s+Ratings)?|Moody['’]s(?:\s+Ratings)?|S&P(?:\s+Global(?:\s+Ratings)?)?)"
        r"\s*[-–—]\s*[^\n-]{1,100}\s*[-–—]\s*(" + _DATE_PATTERN + r")\s*:", text[:5000])
    if dateline:
        return _timestamp(dateline[1])
    # PDF readers can join the document date and city dateline into one line,
    # e.g. "13 Jan 2026 Paris, January 13, 2026 -- Moody's ...".
    joined = re.search(r"(?im)^\s*(" + _DATE_PATTERN + r")(?=\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?,\s)", text[:5000])
    if joined:
        return _timestamp(joined[1])
    report = re.search(r"\b(?:Rating Report|Credit Opinion|Research Update)\s*\|\s*(" + _DATE_PATTERN + r")\s+(?:fitchratings\.com|spglobal\.com|moodys\.com)", text[:12000], re.I)
    return _timestamp(report[1]) if report else None


def _document_agency(source):
    host = (urlsplit(source["url"]).hostname or "").lower()
    for domain, agency in (("moodys.com", "moodys"), ("spglobal.com", "sp"), ("fitchratings.com", "fitch")):
        if host == domain or host.endswith("." + domain):
            return agency
    publisher = _plain(source.get("title")) + "\n" + source["text"][:8000]
    domains = {"moodys": r"ratings\.moodys\.com", "sp": r"spglobal\.com/ratings(?:direct)?", "fitch": r"fitchratings\.com"}
    present = [agency for agency, pattern in _AGENCY_PATTERNS.items()
               if pattern.search(publisher) or re.search(domains[agency], publisher, re.I)]
    return present[0] if len(present) == 1 else None


def _typed_rating_sections(source, candidate):
    """Agency report rating lists with an explicit legal-entity section.

    A report's title alone does not own its score snapshot. Detailed lists are
    separately scoped, and history, sovereign and related-entity rows cannot
    supply the named company's grade.
    """
    agency = _document_agency(source)
    if agency not in {"sp", "fitch"}:
        return []
    raw_lines = source["text"].splitlines()
    lines = [(index, _plain(line).lstrip("> ")) for index, line in enumerate(raw_lines) if _plain(line)]
    output = []
    in_ratings = False
    for number, (raw_index, value) in enumerate(lines):
        if re.fullmatch(r"Ratings(?: Detail(?:.*)?)?", value, re.I):
            in_ratings = True
            continue
        if not in_ratings or not _matches_entity(value, candidate):
            continue
        entries = []
        forwards = []
        mode = "ratings"
        end_index = raw_index
        for next_index, (position, line) in enumerate(lines[number + 1:number + 45], number + 1):
            if re.match(r"Issuer Credit Ratings History|Ratings History|Related Entities|Contacts|ESG and Climate", line, re.I):
                break
            if re.match(r"Sovereign(?: Risk| Rating)?\b", line, re.I):
                if agency == "sp":
                    break
                mode = "sovereign"
                continue
            if line.casefold() == "outlooks":
                mode = "outlooks"
                continue
            if (re.search(r"\b(?:AG|plc|LLC|Inc\.|Bank|N\.A\.)$", line)
                    and not _matches_entity(line, candidate) and not _kind(line)):
                break
            if mode == "sovereign" or line.casefold().startswith("sovereign"):
                continue
            end_index = position
            combined = line
            row_end_index = position
            if re.fullmatch(r"Issuer Credit Rating|(?:Long|Short)[ -]Term(?: (?:Foreign|Local)[ -]Currency)? (?:IDR|Issuer Default Rating)", line, re.I):
                if next_index + 1 < len(lines):
                    combined += " " + lines[next_index + 1][1]
                    end_index = lines[next_index + 1][0]
                    row_end_index = end_index
            literal_row = "\n".join(raw_lines[position:row_end_index + 1])
            if agency == "sp":
                match = re.fullmatch(r"Issuer Credit Rating\s+(?P<long>" + _GRADE_TOKEN + r")/(?P<outlook>Stable|Positive|Negative|Developing|--)/(?P<short>" + _GRADE_TOKEN + r"|NR)", combined, re.I)
                if match:
                    entries.append({"label": "Issuer Credit Rating", "rating": match["long"], "term": "long_term", "type": "issuer", "basis": None,
                                    "outlook": normalize_outlook(match["outlook"]), "row": literal_row})
                    if match["short"].upper() != "NR":
                        entries.append({"label": "Issuer Credit Rating", "rating": match["short"], "term": "short_term", "type": "issuer", "basis": None,
                                        "outlook": "unknown", "row": literal_row})
            else:
                match = re.fullmatch(r"(?P<label>(?:Long|Short)[ -]Term(?: (?:Foreign|Local)[ -]Currency)? (?:IDR|Issuer Default Rating))\s+(?P<value>[^\s]+)", combined, re.I)
                if not match:
                    continue
                kind = _kind(match["label"])
                basis = "foreign_currency" if "foreign" in match["label"].casefold() else "local_currency" if "local" in match["label"].casefold() else None
                if mode == "outlooks":
                    signal = normalize_outlook(match["value"])
                    if signal != "unknown":
                        forwards.append({"term": kind[1], "basis": basis, "outlook": signal, "row": literal_row})
                else:
                    entries.append({"label": match["label"], "rating": match["value"], "term": kind[1], "type": "issuer_default", "basis": basis,
                                    "outlook": "unknown", "row": literal_row})
        excerpt = "\n".join(raw_lines[raw_index:end_index + 1])
        if not entries or len(excerpt) > 10000:
            continue
        for entry in entries:
            if agency == "fitch":
                eligible = [signal for signal in forwards if signal["term"] == entry["term"]
                            and (entry["basis"] is None or signal["basis"] == entry["basis"])]
                signals = {signal["outlook"] for signal in eligible}
                if len(signals) == 1:
                    entry["outlook"] = signals.pop()
            fields = dict(agency=agency, status="rated", rating=entry["rating"], scope="issuer", scale="global",
                          term=entry["term"], rating_type=entry["type"], entity_name=value, entity_id=None,
                          rating_date=None, outlook=entry["outlook"], outlook_date=None, watch="unknown", watch_date=None,
                          currency_basis=entry["basis"], observed_at=_publication(source, source["text"]))
            try:
                output.append(_make_record(source, candidate, fields, excerpt,
                                           {"entity": raw_lines[raw_index], "rating_row": entry["row"], "forward_rows": [row["row"] for row in forwards]},
                                           snapshot_kind="agency_ratings_detail", action_type="rating_observation"))
            except ValueError:
                continue
    return output


def _explicit_outlook_action(text, candidate, observed, periodic, rating_matches=(), expected=None):
    if periodic or not observed:
        return None
    patterns = (
        r"\b(?:revis(?:es|ed)|chang(?:es|ed)|assign(?:s|ed)|affirm(?:s|ed)|maintain(?:s|ed))\b[^.;\n]{0,180}?\b(?P<label>outlook)\s+(?:to|at|as)\s+(?P<grade>positive|negative|stable|developing)\b",
        r"\b(?P<label>outlook)\s+(?:was\s+)?(?:revis(?:es|ed)|chang(?:es|ed)|assign(?:s|ed)|affirm(?:s|ed)|maintain(?:s|ed))\s+(?:to|at|as)?\s*(?P<grade>positive|negative|stable|developing)\b",
    )
    links = _article_link_spans(text)
    for pattern in patterns:
        for match in re.finditer(pattern, text[:12000], re.I):
            if _inside_link(match, links):
                continue
            paragraph_start = text.rfind("\n\n", 0, match.start()) + 2
            if (_forward_clause_is_bound(text, match, candidate, rating_matches)
                    and (expected is None or normalize_outlook(match["grade"]) == expected)):
                return _date(observed)
    return None


def _clause_subject_match(text, match, paragraph_start, candidate):
    """Return True/False for an explicit subject, None for an unbound pronoun."""
    names = _names(candidate)
    label_end, grade_start = match.end("label"), match.start("grade")
    if label_end < grade_start:
        tail = text[label_end:grade_start]
        subject = re.search(r"\b(?:on|for|of)\s+(.+?)\s+(?:at|to|is)\s*['\"‘’]?\s*$", tail, re.I | re.S)
        if subject:
            named = _entity(subject[1].strip(" '\"‘’"))
            if named not in {"it", "the company", "the issuer", "the group"}:
                return named in names
    clause_start = min(match.start("label"), match.start("grade"))
    prefix = text[paragraph_start:clause_start]
    masked = re.sub(r"\b(?:Inc\.|Co\.|Corp\.|Ltd\.|S\.A\.|N\.A\.)",
                    lambda item: item[0].replace(".", " "), prefix, flags=re.I)
    boundary = max(masked.rfind("."), masked.rfind("!"), masked.rfind("?"))
    prefix = prefix[boundary + 1:]
    adjacent = _legal_subject(prefix)
    if adjacent in names:
        return True
    if re.search(r"\b(?:Bank|Inc\.|Co\.|Corp\.|Ltd\.|LLC|plc|S\.A\.|N\.A\.|AG)\s*$", prefix, re.I):
        return False
    for possessive in reversed(list(re.finditer(r"['’]s\b", prefix, re.I))):
        left = _legal_subject(prefix[max(0, possessive.start() - 300):possessive.start()])
        last = left.split()[-1:]
        if last and last[0] in {"moody", "company", "issuer", "group", "it", "government"}:
            continue
        return left in names
    return None


def _clause_entity_matches(text, match, paragraph_start, candidate):
    return _clause_subject_match(text, match, paragraph_start, candidate) is True


def _forward_clause_is_bound(text, match, candidate, rating_matches, agency=None):
    if _plain(match["label"]).casefold() == "outlook on the rating":
        boundary = text.rfind("\n\n", 0, match.start())
        start = boundary + 2 if boundary >= 0 else 0
        nearest = max((item for item in rating_matches if start <= item.start() and item.end() <= match.start()
                       and match.start() - item.end() <= 250), key=lambda item: item.end(), default=None)
        if nearest is None:
            return False
        kind = _kind(nearest["label"])
        if not kind or kind[0] != "issuer" or kind[1] != "long_term" or kind[2] not in {"issuer", "issuer_default"}:
            return False
        if re.search(r"\bshort[ -]term\b", text[max(start, nearest.start() - 60):nearest.start()], re.I):
            return False
        try:
            normalize_grade(nearest["grade"], agency, term="long_term", scale="global")
        except ValueError:
            return False
        if _clause_subject_match(text, nearest, start, candidate) is not True:
            return False
        # This pronoun owns only the immediately preceding issuer action,
        # with an optional prior grade, not another issue/entity or paragraph.
        between = _plain(text[nearest.end():match.start("label")])
        return bool(re.fullmatch(r"['\"‘’“”]?\s*(?:from\s+['\"‘’“”]?" + _GRADE_TOKEN
                                 + r"['\"‘’“”]?)?\s*[.;]\s*(?:the|its)?", between, re.I))
    start = text.rfind("\n\n", 0, match.start()) + 2
    direct = _clause_subject_match(text, match, start, candidate)
    if direct is not None:
        return direct
    # A headline explicitly naming the company and rating action owns its
    # semicolon-separated outlook. This cannot borrow another entity's title.
    line_start = text.rfind("\n", 0, match.start()) + 1
    prefix = _entity(text[line_start:match.start("label")])
    for name in _names(candidate):
        if prefix.startswith(name + " ") and re.match(r"(?:upgraded|downgraded|affirmed|assigned|rating)\b", prefix[len(name) + 1:]):
            return True
    # Resolve "the/its outlook" from the nearest preceding rating clause,
    # rather than any name appearing in a 900-character neighborhood.
    prior = sorted((item for item in rating_matches if item.end() <= match.start()
                    and match.start() - item.end() <= 1500), key=lambda item: item.end(), reverse=True)
    if prior:
        nearest = prior[0]
        between = text[nearest.end():match.start("label")]
        if re.search(r"\b[A-Z][A-Za-z& ,.-]{1,90}\b(?:Bank|Inc\.|Corp\.|N\.A\.|AG)\b", between):
            return False
        prior_start = text.rfind("\n\n", 0, nearest.start()) + 2
        return _clause_subject_match(text, nearest, prior_start, candidate) is True
    return False


def _article_records(source, candidate):
    text = source["text"]
    agency = _document_agency(source)
    # Article links/URLs remain discovery leads. Mask the complete spans at
    # original offsets so older grades, URL slugs and pronouns are not facts.
    # Table extraction has its own literal cell rules and is unchanged here.
    prose_chars = list(text[:40000])
    for start, end in _article_link_spans(text[:40000]):
        prose_chars[start:end] = [char if char in "\r\n" else " " for char in prose_chars[start:end]]
    prose = "".join(prose_chars)
    # Reader Markdown can put thousands of characters of invisible sharing
    # targets before the article. Bound the visible prose, while retaining the
    # original text/offsets for clause identity and literal source evidence.
    visible = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", prose)
    heading = _plain(source.get("title")) + "\n" + _plain(visible)[:1800]
    if not agency:
        return []
    canonical_name = next((candidate.get(key) for key in ("legal_entity_name", "issuer_name", "name")
                           if isinstance(candidate.get(key), str) and candidate[key].strip()), None)
    candidate, definitions = _article_aliases(text, candidate)
    names = _names(candidate)
    heading_normal = " " + _entity(heading) + " "
    matched = next((name for name in sorted(names, key=len, reverse=True) if " " + name + " " in heading_normal), None)
    if not matched:
        return []
    # The article must explicitly name the target legal entity/verified alias
    # near its rating subject; an unrelated security mention is not identity.
    entity_name = canonical_name
    if not entity_name:
        return []
    observed = _publication(source, prose)
    periodic = bool(re.search(r"periodic review", prose[:12000], re.I))
    no_action = periodic or bool(re.search(r"does not (?:constitute|announce) (?:a|any) (?:credit )?rating action", prose[:12000], re.I))
    output = []
    labels = r"(?:long[ -]term\s+)?(?:issuer(?:\s+default)?(?:\s+credit)?\s+rating(?:s)?|IDR|ICR|corporate[ -]family\s+rating|senior\s+unsecured\s+(?:debt\s+)?rating)"
    patterns = [
        re.compile(r"(?P<label>" + labels + r")(?:\s*\([A-Z]+\))?[^.;]{0,230}?\b(?:at|to|of|is)\s*['\"‘’]?\s*(?P<grade>" + _GRADE_TOKEN + r")(?![A-Za-z0-9+-]|\.[A-Za-z]|\([A-Za-z])", re.I),
        re.compile(r"(?<![A-Za-z0-9])(?P<grade>" + _GRADE_TOKEN + r")(?![A-Za-z0-9+-]|\.[A-Za-z]|\([A-Za-z])\s*['\"‘’]?\s+(?P<label>" + labels + r")", re.I),
    ]
    # Legal-name abbreviation periods do not terminate a financial sentence.
    # Replace them with spaces only in the scan buffer, preserving raw offsets.
    scan = re.sub(r"\b(?:Inc\.|Co\.|Corp\.|Ltd\.|S\.A\.|N\.A\.)",
                  lambda item: item[0].replace(".", " "), prose, flags=re.I)
    rating_matches = [match for pattern in patterns for match in pattern.finditer(scan)]
    outlook_pattern = re.compile(r"\b(?P<label>outlook)\s+(?:from\s+(?:positive|negative|stable|developing)\s+to\s+|(?:(?:is|remains|was|of)\s+)?(?:(?:revised|changed|assigned)\s+)?(?:to\s+)?)(?P<grade>positive|negative|stable|developing)\b", re.I)
    rating_outlook = re.compile(r"\b(?P<label>outlook\s+on\s+the\s+rating)\s+is\s+(?P<grade>positive|negative|stable|developing)\b", re.I)
    reverse_outlook = re.compile(r"\b(?P<grade>positive|negative|stable|developing)\s+(?P<label>outlook)\b", re.I)
    watch_pattern = re.compile(r"(?P<label>CreditWatch|Rating Watch|on review for|under review for)\s*[:;,]?\s*(?:with\s+)?(?P<grade>positive|negative|developing|evolving|upgrade|downgrade|direction uncertain)", re.I)
    outlook_matches = [match for pattern in (outlook_pattern, reverse_outlook, rating_outlook) for match in pattern.finditer(prose)
                       if _forward_clause_is_bound(prose, match, candidate, rating_matches, agency)]
    watch_matches = [match for match in watch_pattern.finditer(prose)
                     if _forward_clause_is_bound(prose, match, candidate, rating_matches)]
    outlook_values = {normalize_outlook(match["grade"]) for match in outlook_matches}
    watch_values = {normalize_watch(match["grade"]) for match in watch_matches}
    bound_outlook = next(iter(outlook_values)) if len(outlook_values) == 1 else "unknown"
    bound_watch = next(iter(watch_values)) if len(watch_values) == 1 else "unknown"
    for match in rating_matches:
            kind = _kind(match["label"])
            if not kind:
                continue
            scope, term, rating_type = kind
            if scope != "issuer":
                continue
            paragraph_start = text.rfind("\n\n", 0, match.start()) + 2
            paragraph_end = text.find("\n\n", match.end())
            paragraph_end = len(text) if paragraph_end < 0 else paragraph_end
            paragraph = prose[paragraph_start:paragraph_end]
            paragraph_identity = " " + _entity(paragraph) + " "
            if not any(" " + name + " " in paragraph_identity for name in names):
                continue
            if not _clause_entity_matches(prose, match, paragraph_start, candidate):
                continue
            start = max(0, match.start() - 700)
            end = min(len(text), match.end() + 900)
            excerpt = text[start:end]
            prose_excerpt = prose[start:end]
            # Reject old grades after "from" and explicit prospective grades.
            prefix = prose[max(start, match.start() - 80):match.start()]
            grade_prefix = prose[max(0, match.start("grade") - 30):match.start("grade")]
            if re.search(r"\(\s*(?:P|EXP|PI|PRELIM(?:INARY)?|SF|HYB)\s*\)\s*$", grade_prefix, re.I):
                continue
            clause = prose[match.start():match.end()]
            if re.search(r"\b(?:could|may|would|might|hypothetical|prospective|expected to)\b", prefix + clause, re.I):
                continue
            if re.search(r"\b(?:previously|formerly|historical(?:ly)?)\b", prefix, re.I):
                continue
            action = "periodic_review" if periodic else ("rating_action" if not no_action and re.search(r"\b(?:affirm(?:s|ed)?|upgrad(?:es|ed)|downgrad(?:es|ed)|rais(?:es|ed)|lower(?:s|ed)|assign(?:s|ed))\b", prose_excerpt, re.I) else "rating_observation")
            fields = dict(agency=agency, status="rated", rating=match["grade"], scope=scope,
                          scale="national" if "national scale" in prose_excerpt.casefold() else "global",
                          term=term, rating_type=rating_type, entity_name=entity_name, entity_id=None,
                          rating_date=_date(observed) if action == "rating_action" else None,
                          outlook=bound_outlook, watch=bound_watch, observed_at=observed)
            fields["outlook_date"] = _explicit_outlook_action(prose, candidate, observed, no_action, rating_matches, bound_outlook) if bound_outlook != "unknown" else None
            fields["watch_date"] = _date(observed) if bound_watch != "unknown" and re.search(r"plac(?:ed|es)\s+(?:on|under)|on review for", prose_excerpt, re.I) else None
            fields["currency_basis"] = ("foreign_currency" if re.search(r"foreign[ -]currency", match["label"], re.I)
                                        else "local_currency" if re.search(r"local[ -]currency", match["label"], re.I) else None)
            try:
                literal_alias = next((alias for alias in candidate.get("issuer_aliases", []) if _entity(alias) == matched), entity_name)
                claims = {"rating_clause": text[match.start():match.end()], "entity_alias": literal_alias}
                if definitions:
                    claims["entity_definitions"] = definitions
                    claims["source_bound_aliases"] = candidate.get("_source_bound_aliases", [])
                output.append(_make_record(source, candidate, fields, excerpt, claims, action_type=action))
            except ValueError:
                continue
    return output


def _licensed_records(source, candidate):
    if source.get("_licensed_api") is not True or source.get("provider") != "spglobal_agency_ratings":
        return []
    if (urlsplit(source["url"]).hostname or "").lower() != "xpressapi.marketplace.spglobal.com":
        return []
    output = []
    for row in source.get("structured_data") or []:
        if not isinstance(row, dict) or row.get("kind") != "credit_rating":
            continue
        if row.get("security_key") is not None and row["security_key"] != candidate.get("security_key"):
            continue
        if not isinstance(row.get("entity_name"), str) or not row["entity_name"].strip():
            continue
        binding = source.get("_request_binding")
        exact_issue = False
        if isinstance(binding, dict) and row.get("scope") == "issue":
            identifier = str(binding.get("identifier_value") or "").strip().upper()
            identifier_type = binding.get("identifier_type")
            expected = {str(candidate.get(key) or "").strip().upper() for key in ("isin", "cusip", "symbol", "secondary_symbol")}
            exact_issue = bool(
                isinstance(candidate.get("security_key"), str) and candidate["security_key"]
                and binding.get("security_key") == candidate["security_key"]
                and binding.get("scope") == "issue"
                and identifier_type in {"ISIN", "CUSIP9"}
                and identifier in expected
                and re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d" if identifier_type == "ISIN" else r"[A-Z0-9*@#]{9}", identifier)
            )
        if _names(candidate) and not _matches_entity(row["entity_name"], candidate) and not exact_issue:
            continue
        excerpt = row.get("evidence_quote") or source["text"]
        if not isinstance(excerpt, str) or not 1 <= len(excerpt) <= 16000 or _text(excerpt) not in _text(source["text"]):
            continue
        original = row.get("response_originalrecord")
        if original is not None:
            try:
                if len(json.dumps(original, ensure_ascii=False, allow_nan=False)) > 16000:
                    continue
            except (ValueError, TypeError):
                continue
        try:
            decoded = json.loads(excerpt)
        except (TypeError, ValueError):
            continue
        literal_values = []
        def literals(value, depth=0):
            if depth > 12 or len(literal_values) > 2000:
                return
            if isinstance(value, str):
                literal_values.append(value)
            elif isinstance(value, dict):
                for nested in value.values():
                    literals(nested, depth + 1)
            elif isinstance(value, list):
                for nested in value:
                    literals(nested, depth + 1)
        literals(original if original is not None else decoded)
        literal_text = "\n".join(literal_values)
        # The I/O owner has already verified request identifiers; the domain
        # layer still requires the literal entity and grade in the response.
        if _entity(row["entity_name"]) not in _entity(literal_text):
            continue
        if row.get("status", "rated") == "rated" and not re.search(r"(?<![A-Za-z0-9])" + re.escape(str(row.get("rating") or "")) + r"(?![A-Za-z0-9])", literal_text, re.I):
            continue
        if row.get("status") == "unrated" and not any(_plain(value).casefold() in {"nr", "n.r.", "not rated", "unrated"} for value in literal_values):
            continue
        if row.get("status") == "withdrawn" and not any(re.search(r"\b(?:withdrawn|withdrawal|WR|WD)\b", value, re.I) for value in literal_values):
            continue
        if row.get("status", "rated") not in {"rated", "unrated", "withdrawn"}:
            continue
        outlook = normalize_outlook(row.get("outlook"))
        watch = normalize_watch(row.get("watch"))
        if outlook != "unknown" and not any(normalize_outlook(value) == outlook for value in literal_values):
            continue
        if watch != "unknown" and not any(normalize_watch(value) == watch for value in literal_values):
            continue
        if any(row.get(field) not in (None, "") and not any(_date(value) == _date(row[field]) for value in literal_values)
               for field in ("rating_date", "outlook_date", "watch_date")):
            continue
        fields = {**{key: row.get(key) for key in _FIELDS}, "status": row.get("status", "rated"),
                  "outlook": row.get("outlook", "unknown"), "watch": row.get("watch", "unknown")}
        if fields["status"] not in STATUSES or fields["scope"] not in {"issuer", "issue"}:
            continue
        try:
            output.append(_make_record(source, candidate, fields, excerpt, {"vendor_entity": row["entity_name"], "vendor_grade": row.get("rating")},
                                       response_originalrecord=original))
        except ValueError:
            continue
    return output


def extract_rating_records(source: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract supported literal contexts from a fetched source, never snippets."""
    if not isinstance(source, dict) or not isinstance(candidate, dict):
        return []
    if not isinstance(source.get("text"), str) or not source["text"].strip() or source.get("discovery_only"):
        return []
    try:
        _url(source.get("url"))
    except ValueError:
        return []
    if source_authority(source, candidate) is None:
        return []
    if source.get("_licensed_api") is True:
        records = _licensed_records(source, candidate)
    else:
        records = _table_records(source, candidate)
        flattened = _flattened_table_source(source)
        if flattened:
            for record in _table_records(flattened, candidate):
                # Each field remains bound to its original literal cell spans.
                record["_source"] = source
                record["_flattened"] = True
                records.append(record)
        records += _typed_rating_sections(source, candidate)
        records += _article_records(source, candidate)
    unique = {}
    for record in records:
        unique.setdefault(record["record_id"], record)
    return list(unique.values())


def normalize_observation(record: dict[str, Any], candidate: dict[str, Any], *, source: dict[str, Any] | None = None) -> dict[str, Any]:
    """Re-derive a selected context; reject invented IDs, values and dates."""
    if not isinstance(record, dict) or not isinstance(candidate, dict):
        raise ValueError("Invalid rating observation")
    source = source if source is not None else record.get("_source")
    if not isinstance(source, dict):
        raise ValueError("A source-bound rating record is required")
    fetched = _timestamp(source.get("retrieved_at"))
    if not fetched:
        raise ValueError("Source retrieval timestamp is required")
    matches = [item for item in extract_rating_records(source, candidate) if item["record_id"] == record.get("record_id")]
    if len(matches) != 1:
        raise ValueError("Rating record was not extracted from this candidate/source")
    canonical = matches[0]
    if any(record.get(key) != canonical.get(key) for key in _FIELDS):
        raise ValueError("Rating fields do not match the literal source record")
    if record.get("source_url") != source.get("url") or record.get("source_id") != source.get("source_id"):
        raise ValueError("Rating source identity was changed")
    cutoff = _date(candidate.get("as_of_date")) or _date(fetched)
    if any(day and cutoff and day > cutoff for day in (_date(canonical.get(field)) for field in ("rating_date", "outlook_date", "watch_date", "observed_at"))):
        raise ValueError("Rating observation is after the research cutoff")
    result = {key: canonical.get(key) for key in _FIELDS}
    result.update(record_id=canonical["record_id"], source_url=source["url"], fetched_at=fetched,
                  rating_raw=canonical.get("rating_raw"),
                  stale=bool(source.get("stale", False)), source_kind=canonical["source_kind"],
                  evidence_quote=canonical["evidence_quote"], claims=canonical["claims"],
                  sources=[{"url": source["url"], "title": str(source.get("title") or "")[:300],
                            "evidence_quote": canonical["evidence_quote"], "fetched_at": fetched,
                            "source_kind": canonical["source_kind"]}],
                  primary_eligible=is_primary_observation(canonical, candidate))
    for definition in canonical.get("claims", {}).get("entity_definitions", []):
        if definition and definition in source["text"]:
            result["sources"].append({"url": source["url"], "title": str(source.get("title") or "")[:300],
                                      "evidence_quote": definition, "fetched_at": fetched,
                                      "source_kind": canonical["source_kind"], "fields": ["entity_name"]})
    for key in ("action_type", "snapshot_kind"):
        if key in canonical:
            result[key] = canonical[key]
    return result


def validate_observation(record: dict[str, Any], candidate: dict[str, Any], *, source: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        return normalize_observation(record, candidate, source=source)
    except (TypeError, ValueError):
        return None
