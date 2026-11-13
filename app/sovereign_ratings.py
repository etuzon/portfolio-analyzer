"""Sourced sovereign opinions, kept separate from corporate and issue ratings.

Country identities use the bundled ISO 3166-1 catalog (Debian iso-codes).
Country codes, stock-market locations and trading currencies are never inferred.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .credit_ratings import (_AGENCY_PATTERNS, _DATE_PATTERN, _GRADE_TOKEN, _article_link_spans, _legal_subject,
    _date, _entity, _plain, _publication, _timestamp, _url, normalize_grade,
    normalize_outlook, normalize_watch)

AGENCIES = ("moodys", "sp", "fitch")
CURRENCY_BASES = ("foreign_currency", "local_currency", "unknown")
COUNTRIES = json.loads(Path(__file__).with_name("country_catalog.json").read_text())
_CATALOG = {row["code"]: row for row in COUNTRIES}
_ALIASES = {"USA": "US", "UK": "GB", "United States of America": "US", "Russia": "RU",
            "South Korea": "KR", "North Korea": "KP", "Taiwan": "TW", "Türkiye": "TR",
            "Turkey": "TR", "Vietnam": "VN", "Czech Republic": "CZ", "ישראל": "IL",
            "ארצות הברית": "US"}
for _row in COUNTRIES:
    for _alias in [_row["code"], _row["alpha3"], _row["name"], *_row["aliases"]]:
        if _alias:
            _ALIASES[_alias] = _row["code"]
_LOOKUP = {_entity(key): value for key, value in _ALIASES.items()}
# Independent state identities: UN members plus Holy See and State of Palestine.
# ISO additionally contains territories. A territorial issuer opinion needs an
# explicit agency sovereign classification before entering this sovereign model.
SOVEREIGN_CODES = frozenset("""AD AE AF AG AL AM AO AR AT AU AZ BA BB BD BE BF BG BH BI BJ BN BO BR BS BT BW BY BZ
CA CD CF CG CH CI CL CM CN CO CR CU CV CY CZ DE DJ DK DM DO DZ EC EE EG ER ES ET FI FJ FM FR GA GB GD GE GH
GM GN GQ GR GT GW GY HN HR HT HU ID IE IL IN IQ IR IS IT JM JO JP KE KG KH KI KM KN KP KR KW KZ LA LB LC LI
LK LR LS LT LU LV LY MA MC MD ME MG MH MK ML MM MN MR MT MU MV MW MX MY MZ NA NE NG NI NL NO NP NR NZ OM
PA PE PG PH PK PL PT PW PY QA RO RS RU RW SA SB SC SD SE SG SI SK SL SM SN SO SR SS ST SV SY SZ TD TG TH TJ
TL TM TN TO TR TT TV TZ UA UG US UY UZ VA VC VE VN VU WS YE ZA ZM ZW PS""".split())


def normalize_country(value):
    if not isinstance(value, str) or not value.strip():
        return None
    return _LOOKUP.get(_entity(value))


def country_descriptor(value):
    code = normalize_country(value)
    if not code:
        return None
    row = _CATALOG[code]
    aliases = [name for name in dict.fromkeys([row["name"], *row["aliases"],
        *(name for name, item in _ALIASES.items() if item == code and len(name) > 3)]) if name]
    # These are sovereign names, not commercial issuer aliases.
    aliases += ["Government of " + row["name"], "State of " + row["name"]]
    if code == "US":
        aliases += ["United States", "United States of America", "U.S."]
    return {"country_code": code, "country_name": row["name"], "country_aliases": list(dict.fromkeys(aliases)),
            "sovereign_identity": code in SOVEREIGN_CODES,
            "country_key": "COUNTRY:" + code, "security_key": "COUNTRY:" + code,
            "symbol": code, "name": row["name"], "has_open_position": True}


# Discovery leads contain no grades. Facts require the normal bounded source read.
SOURCE_LEADS = {"IL": ["https://ratings.moodys.com/ratings-news/458577",
    "https://www.gov.il/BlobFolder/news/press_31012026/he/PressReleases_files_Rating_Action-Moodys-Ratings-changes-Israels-30Jan2026-PR_518117.pdf"]}
GOVERNMENT_DOMAINS = {"IL": ("gov.il",), "US": ("treasury.gov",), "GB": ("dmo.gov.uk",),
    "DE": ("deutsche-finanzagentur.de",), "FR": ("aft.gouv.fr",), "SG": ("mas.gov.sg",),
    "CA": ("canada.ca",), "AU": ("aofm.gov.au",), "JP": ("mof.go.jp",), "CH": ("efv.admin.ch",)}


def source_authority(source, candidate):
    if source.get("_licensed_api") or source.get("discovery_only"):
        return None
    try:
        host = urlsplit(_url(source.get("url"))).hostname.lower()
    except (AttributeError, ValueError):
        return None
    for domain in ("moodys.com", "spglobal.com", "fitchratings.com"):
        if host == domain or host.endswith("." + domain):
            return "agency_public"
    for domain in GOVERNMENT_DOMAINS.get(candidate.get("country_code"), ()):
        if host == domain or host.endswith("." + domain):
            return "government_public"
    return None


def binding(candidate):
    data = {key: candidate.get(key) for key in ("country_code", "country_name", "country_aliases", "sovereign_identity")}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def slot(agency, basis):
    return {"agency": agency, "currency_basis": basis, "scope": "sovereign", "scale": "global",
        "term": "long_term", "rating_type": "sovereign_issuer", "rating": None, "status": "not_checked",
        "reason_code": "not_checked", "outlook": "unknown", "watch": "unknown", "sources": [],
        "rating_date": None, "outlook_date": None, "watch_date": None, "stale": False}


def _bases(text):
    local = bool(re.search(r"\blocal(?:[ -]currency)?\b", text, re.I))
    foreign = bool(re.search(r"\bforeign(?:[ -]currency)?\b", text, re.I))
    return (["foreign_currency"] if foreign else []) + (["local_currency"] if local else []) or ["unknown"]


def _forward_values(signal, names):
    """Forward opinions with an explicit trailing owner belong to that owner."""
    patterns = (
        r"\boutlook\s+(?:(?:is|remains|was)\s+)?(?:(?:revised|changed)\s+)?(?:to\s+)?(?P<value>positive|negative|stable|developing)\b",
        r"\b(?P<value>positive|negative|stable|developing)\s+outlook\b",
    )
    allowed = {_entity(name).removeprefix("the ") for name in names}
    values = []
    for pattern in patterns:
        for match in re.finditer(pattern, signal, re.I):
            tail = re.split(r"[.;]", signal[match.end():], maxsplit=1)[0]
            owner = re.match(r"\s+(?:for|on|of)\s+(.+?)\s*$", tail, re.I)
            if owner and _entity(owner[1]).removeprefix("the ") not in allowed:
                continue
            values.append(match["value"])
    return values


def _make(source, candidate, agency, grade, basis, excerpt, observed, *, action=False,
          outlook="unknown", watch="unknown", outlook_action=False, watch_action=False, status="rated"):
    rating = normalize_grade(grade, agency) if status == "rated" else None
    fields = {**slot(agency, basis), "status": status, "rating": rating, "rating_raw": grade,
        "entity_name": candidate["country_name"], "country_code": candidate["country_code"],
        "country_key": candidate["country_key"], "entity_id": candidate["country_code"],
        "observed_at": observed, "rating_date": _date(observed) if action else None,
        "outlook": outlook, "watch": watch,
        "outlook_date": _date(observed) if outlook_action else None,
        "watch_date": _date(observed) if watch_action else None,
        "source_url": source["url"], "source_id": source.get("source_id"),
        "source_kind": source_authority(source, candidate), "evidence_quote": excerpt,
        "primary_eligible": True, "action_type": "rating_action" if action else "rating_observation"}
    material = json.dumps(fields, sort_keys=True, ensure_ascii=False)
    return {**fields, "record_id": "sovereign-" + hashlib.sha256(material.encode()).hexdigest()[:24],
            "kind": "sovereign_credit_rating", "security_key": candidate["security_key"]}


def extract_rating_records(source, candidate):
    """Bind a literal grade to a named sovereign and declared long-term axis.

    Unread article links, country ceilings, short-term ratings, debt issues,
    corporate names and conditional/historical grades cannot establish facts.
    """
    if not source_authority(source, candidate) or not isinstance(source.get("text"), str):
        return []
    text = source["text"][:50000]
    chars = list(text)
    for start, end in _article_link_spans(text):
        chars[start:end] = ["\n" if c == "\n" else " " for c in chars[start:end]]
    prose = _plain("".join(chars))
    observed = _publication(source, "".join(chars))
    if not observed:
        # Public Moody's releases use "New York, January 30, 2026 --
        # Moody's Ratings ...". This is the agency-owned article dateline,
        # unlike an event date mentioned in the report's historical discussion.
        dateline = re.search(r"(?m)^[ \t]*[A-Z][A-Za-z .-]{1,60},\s*(" + _DATE_PATTERN
            + r")\s*[-–—]{1,2}\s*(?:Moody['’]s(?:\s+Ratings)?|Fitch(?:\s+Ratings)?|S&P(?:\s+Global(?:\s+Ratings)?)?)\b", "".join(chars)[:6000])
        observed = _date(dateline[1]) if dateline else None
    names = sorted({name for name in candidate.get("country_aliases", []) + [candidate["country_name"]]
                    if len(name) > 2}, key=len, reverse=True)
    subject = r"(?:" + "|".join(re.escape(name) for name in names) + r")"
    long = r"long[ -]term"
    currency = r"(?:(?:local|foreign)(?:[ -]currency)?(?:\s+and\s+(?:local|foreign)(?:[ -]currency)?)?\s+)?"
    label = long + r"\s+" + currency + r"(?:sovereign\s+(?:credit\s+)?|issuer\s+(?:default\s+|credit\s+)?)(?:rating|ratings|IDR)\b"
    patterns = [
        # Moody's: affirmed Israel's Baa1 long-term local and foreign-currency issuer ratings.
        re.compile(r"(?P<subject>" + subject + r")[’']s\s+(?P<grade>" + _GRADE_TOKEN + r")\s+(?P<label>" + label + r")", re.I),
        # Fitch: Israel's Long-Term Foreign-Currency Issuer Default Rating ... at A.
        re.compile(r"(?P<subject>" + subject + r")[’']s\s+(?P<label>" + label + r")(?:\s*\([A-Z]+\))?\s+(?:at|to|of|is)\s*['\"‘’]?(?P<grade>" + _GRADE_TOKEN + r")(?![\w+-])", re.I),
        # S&P: long-term ... sovereign credit ratings on Israel to A.
        re.compile(r"(?P<label>" + label + r")\s+(?:on|of)\s+(?P<subject>" + subject + r")\s+(?:at|to|of|is)\s*['\"‘’]?(?P<grade>" + _GRADE_TOKEN + r")(?![\w+-])", re.I),
        # S&P: affirmed its A ... long-term ... sovereign credit ratings on Israel.
        re.compile(r"['\"‘’](?P<grade>" + _GRADE_TOKEN + r")(?:/[A-Z0-9+-]+)?['\"‘’]\s+(?P<label>long(?:[ -]term|-)(?:\s+and\s+short[ -]term)?\s+" + currency + r"sovereign\s+(?:credit\s+)?ratings?)\s+(?:on|of)\s+(?P<subject>" + subject + r")(?!\w)", re.I),
    ]
    # Retain sentence punctuation in the original prose for subject binding.
    # Named country possessives/on clauses above bind the rated subject exactly.
    records = []
    for pattern in patterns:
        for match in pattern.finditer(prose):
            if match.start() and prose[match.start() - 1].isalnum():
                continue
            if candidate["country_code"] not in SOVEREIGN_CODES and "sovereign" not in match["label"].lower():
                continue
            # A country-name suffix is not a sovereign subject: Bank of Israel,
            # Insurance Company of Israel and Government Holdings of Israel
            # have their own legal identities. Bind the complete named subject
            # using the same maintained legal-subject parser as company facts.
            subject_prefix = prose[max(0, match.start("subject") - 400):match.end("subject")]
            complete_subject = _legal_subject(subject_prefix).removeprefix("the ")
            if complete_subject not in {_entity(name).removeprefix("the ") for name in names}:
                continue
            before_subject = prose[max(0, match.start("subject") - 100):match.start("subject")]
            if match.start("subject") == match.start() and re.search(r"\bof\s+$", before_subject, re.I):
                continue
            start = max(0, prose.rfind(". ", 0, match.start()) + 2)
            end = prose.find(". ", match.end())
            end = min(len(prose), match.end() + 500) if end < 0 else end + 1
            clause = prose[start:end]
            if re.search(r"\b(?:could|may|might|would|previously|formerly|historical|expected to)\b", clause, re.I):
                continue
            # Literal agency qualifiers and a national-scale declaration cannot
            # be stripped off and relabelled as an unqualified global grade.
            suffix = prose[match.end("grade"):match.end("grade") + 80]
            if re.match(r"['\"‘’]?\s*\([^)]{1,20}\)", suffix) or re.match(r"\.[A-Za-z]{2,4}\b", suffix):
                continue
            if re.search(r"\bnational[ -]scale\b|\bon\s+the\s+national\s+scale\b", clause, re.I):
                continue
            agencies = [agency for agency, regex in _AGENCY_PATTERNS.items() if regex.search(clause)]
            if not agencies:
                host = urlsplit(source["url"]).hostname or ""
                agencies = [agency for agency, domain in (("moodys", "moodys.com"), ("sp", "spglobal.com"), ("fitch", "fitchratings.com"))
                            if host == domain or host.endswith("." + domain)]
            if not agencies:
                agencies = [agency for agency, regex in _AGENCY_PATTERNS.items()
                            if regex.search(str(source.get("title") or "") + " " + prose[:800])]
            if len(set(agencies)) != 1:
                continue
            # A nearby next sentence is eligible only as this opinion's forward
            # signal, not an unrelated country/company sentence.
            tail = prose[match.end():min(len(prose), end + 250)]
            signal = clause
            # A separately named sovereign outlook action may precede the grade
            # sentence (the usual Moody's announcement format). Bind the whole
            # country phrase, never a document-wide anonymous outlook.
            named_signal = re.compile(r"(?:chang(?:es|ed)|revis(?:es|ed))\s+(?:the\s+|its\s+)?outlook\s+(?:on|of|for)\s+(?:the\s+)?"
                + subject + r"\s+to\s+(?:positive|negative|stable|developing)(?:\s+from\s+\w+)?", re.I)
            named = list(named_signal.finditer(prose))
            if len(named) == 1:
                signal += " " + named[0][0]
            first_tail = tail.split(". ", 2)
            if len(first_tail) > 1 and re.match(r"(?:The |Its |The rating )?(?:outlook|Outlook|CreditWatch|Rating Watch)", first_tail[1]):
                signal += " " + first_tail[1]
            out = _forward_values(signal, names)
            out += re.findall(r"\boutlook\s+(?:on|of|for)\s+(?:the\s+)?" + subject + r"\s+to\s+(positive|negative|stable|developing)\b", signal, re.I)
            outlook = normalize_outlook(out[0]) if len({s.lower() for s in out}) == 1 else "unknown"
            watch_match = re.search(r"(?:CreditWatch|Rating Watch|review for)\s+(positive|negative|developing|upgrade|downgrade)", signal, re.I)
            if watch_match:
                watch_tail = re.split(r"[.;]", signal[watch_match.end():], maxsplit=1)[0]
                owner = re.match(r"\s+(?:for|on|of)\s+(.+?)\s*$", watch_tail, re.I)
                if owner and _entity(owner[1]).removeprefix("the ") not in {_entity(name).removeprefix("the ") for name in names}:
                    watch_match = None
            watch = normalize_watch(watch_match[1]) if watch_match else "unknown"
            watch_action = bool(watch != "unknown" and re.search(
                r"\bplac(?:ed|es)\s+(?:(?:the|its)\s+)?(?:rating\s+)?on\s+(?:Rating Watch|CreditWatch)\b",
                signal, re.I))
            action = bool(re.search(r"\b(?:affirm(?:s|ed)?|assign(?:s|ed)|upgrad(?:es|ed)|downgrad(?:es|ed)|rais(?:es|ed)|lower(?:s|ed))\b", clause, re.I))
            outlook_action = bool(outlook != "unknown" and re.search(r"(?:chang(?:es|ed)|revis(?:es|ed))\s+(?:its\s+|the\s+)?outlook", signal, re.I))
            for basis in _bases(match["label"]):
                try:
                    records.append(_make(source, candidate, agencies[0], match["grade"], basis, signal, observed,
                        action=action, outlook=outlook, watch=watch, outlook_action=outlook_action, watch_action=watch_action))
                except ValueError:
                    continue
    return list({row["record_id"]: row for row in records}.values())


def normalize_observation(record, candidate, *, source):
    fetched = _timestamp(source.get("retrieved_at"))
    if not fetched:
        raise ValueError("Source retrieval timestamp is required")
    rows = [row for row in extract_rating_records(source, candidate) if row["record_id"] == record.get("record_id")]
    if len(rows) != 1 or any(record.get(key) != value for key, value in rows[0].items()):
        raise ValueError("Sovereign record was not extracted from this source")
    row = deepcopy(rows[0])
    cutoff = _date(candidate.get("as_of_date")) or _date(fetched)
    if any(row.get(key) and str(row[key])[:10] > cutoff for key in ("observed_at", "rating_date", "outlook_date", "watch_date")):
        raise ValueError("Sovereign observation is after the research cutoff")
    row.update(fetched_at=fetched, verification_status="source_verified", sources=[{
        "url": source["url"], "title": str(source.get("title") or "")[:300],
        "source_kind": row["source_kind"], "fetched_at": fetched, "evidence_quote": row["evidence_quote"]}])
    return row
