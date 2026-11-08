"""Pure, conservative source contexts for instrument-specific fetched evidence.

Context joins are source contracts, never guesses from another widget's units,
publication dates, related instruments, or general exchange conventions.
"""
from __future__ import annotations

from datetime import date
import hashlib
from itertools import islice
import json
import math
import re
from typing import Any
from urllib.parse import urlsplit

from .price_agent import _unsupported_price_basis
from .price_evidence import _observation_currency_matches
from .security_identifiers import valid_cusip, valid_isin


# The exchange's main security page is published at both the listing root and
# its explicit major_data route. Other tabs carry different source contracts.
_TASE_MAIN_PATH = re.compile(r"/he/market_data/security/(\d+)(?:/major_data)?/?")


def _normal(value):
    return " ".join(str(value or "").split())


def _market(value):
    value = re.sub(r"\s+", "", str(value or "").upper())
    return {"TLV": "TASE", "TELAVIV": "TASE", "NYSEARCA": "NYSEARCA"}.get(value, value)


def _same_id(value, expected):
    left, right = str(value or "").strip(), str(expected or "").strip()
    return bool(left and right) and ((left.lstrip("0") or "0") == (right.lstrip("0") or "0")
                                    if left.isdigit() and right.isdigit() else left.upper() == right.upper())


def _number(value):
    try:
        if isinstance(value, str) and re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", value):
            value = float(value.replace(",", ""))
        return float(value) if type(value) in {int, float} and math.isfinite(value) and value > 0 else None
    except (OverflowError, ValueError):
        return None


def _isin_conflicts(source, candidate, text):
    expected = {str(candidate.get(key) or "").upper() for key in ("symbol", "secondary_symbol", "isin")
                if re.fullmatch(r"[A-Za-z]{2}[A-Za-z0-9]{9}\d", str(candidate.get(key) or ""))}
    actual = re.findall(r"\bISIN\b[\s*：:|]*([A-Z]{2}[A-Z0-9]{9}\d)(?!\w)", text, re.I)
    if isinstance(source.get("isin"), str):
        actual.append(source["isin"])
    return bool(expected) and any(value.upper() not in expected for value in actual)


def _explicit_security_numbers(text):
    return re.findall(r"מספר\s+(?:נייר|ני[״\"']?ע)\s*[:：]?\s*\**\s*(\d{5,10})(?!\d)", text)


def _record(source, candidate, kind, excerpt, claims, **fields):
    raw = json.dumps([source["url"], kind, excerpt, fields], ensure_ascii=False, sort_keys=True)
    return {"record_id": "context-" + hashlib.sha256(raw.encode()).hexdigest()[:20], "kind": kind,
            "symbol": candidate.get("symbol"), "stock_market": _market(candidate.get("stock_market")),
            "source_url": source["url"], "evidence_quote": excerpt, "claims": claims, **fields}


def _tase_records(source, candidate):
    parsed = urlsplit(source["url"])
    route = _TASE_MAIN_PATH.fullmatch(parsed.path)
    if parsed.hostname != "market.tase.co.il" or not route or _market(candidate.get("stock_market")) != "TASE":
        return []
    if str(candidate.get("asset_class") or "STOCK").upper() not in {"STOCK", "EQUITY", "SHARE"}:
        return []
    identifier = route[1]
    if not any(_same_id(identifier, candidate.get(key)) for key in ("symbol", "secondary_symbol")):
        return []
    text = source["text"]
    heading = re.search(r"#{1,6}\s+(?:\*\*)?(?P<name>[^#\n]+?)\s+נתונים עיקריים(?:\*\*)?", text)
    if not heading:
        return []
    # Only the main security header supplies identity. The URL/title wrappers
    # and a related-instrument row elsewhere cannot satisfy this requirement.
    header_end = re.search(r"שער אחרון|#{1,6}\s*\*?\*?אודות|שווי שוק", text[heading.end():])
    header = text[heading.start():heading.end() + (header_end.start() if header_end else 1000)]
    explicit_id = re.search(r"(?:\*\s+|מספר\s+(?:נייר|ני[״\"']?ע)\s*[:：]?\s*)0*" + re.escape(str(int(identifier))) + r"(?!\d)", header)
    share_type = re.search(r"מניה רגילה", header)
    header_ids = re.findall(r"(?m)^\s*\*\s+(\d{5,10})(?!\d)", header)
    header_ids += _explicit_security_numbers(header)
    primary_scope = re.split(r"#{1,6}\s*(?:\*\*)?(?:ניירות קשורים|חדשות)|\b(?:related securities|related stocks|news)\b", text[heading.start():], maxsplit=1, flags=re.I)[0]
    if (not explicit_id or not share_type or any(not _same_id(value, identifier) for value in header_ids)
            or _isin_conflicts(source, candidate, primary_scope)):
        return []
    claims = {"identity": explicit_id[0], "instrument_type": share_type[0]}
    output = []
    name = heading["name"].strip(" *")
    if name and len(name) <= 200:
        output.append(_record(source, candidate, "profile", heading[0], claims, field="name", value=name))
    quote_tail = text[heading.end():]
    cutoff = re.search(r"שווי שוק|אודות החברה|ענף בבורסה|תשואות|נתוני עסקאות|ימי מסחר|ניירות קשורים|חדשות|\b(?:related|news)\b", quote_tail, re.I)
    card = quote_tail[:cutoff.start()] if cutoff else quote_tail
    # Inspect the complete quote card, including prefixes before the matched
    # label. No market-cap, company-description or related-widget field can
    # override this card's explicit currency, basis or instrument identity.
    card_conflict = (any(not _same_id(value, identifier) for value in _explicit_security_numbers(card))
                     or bool(re.search(r"(?<!\w)(?:adjusted|מתואם|מתואמת|NAV|yield|coupon|YTM)(?!\w)|percent\s*(?:of\s*)?par|אחוז\s+מערך\s+נקוב", card, re.I)))
    price = re.search(r"(?P<label>שער אחרון\s*\(\s*באגורות\s*\))\s*(?:\*\*|[:|])*\s*(?P<amount>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?:\*\*)?(?![\d,.%])", card)
    if price:
        # Reuse the maintained currency-name/unit vocabulary. Basis checks
        # apply to the selected field and its prefix, excluding the legitimate
        # percentage-change widget that follows this page's Last price.
        card_conflict = (card_conflict or not _observation_currency_matches(
            {"evidence_quote": card, "price_input": _number(price["amount"]) or 1}, candidate)
            or _unsupported_price_basis(card[max(0, price.start() - 120):price.end()]))
    asof = re.search(r"נכון ל\s*[-–]?\s*(\d{2}/\d{2}/\d{4})(?!\d)", card[price.end():]) if price else None
    if (price and asof and not card_conflict and not re.match(r"[\s*]*%", card[price.end():])
            and str(candidate.get("currency") or "").upper() == "ILS" and candidate.get("quote_unit") == "agorot"):
        try:
            day, month, year = map(int, asof[1].split("/"))
            observed_day = date(year, month, day).isoformat()
        except ValueError:
            observed_day = None
        amount = _number(price["amount"])
        if observed_day and amount:
            output.append(_record(source, candidate, "price", price[0], {**claims, "date": asof[0], "unit": price["label"], "basis": "שער אחרון"},
                                  currency="ILS", quote_unit="agorot", price_basis="last", price_input=amount,
                                  price_date=observed_day, observed_at=None, date_format="dd/mm/yyyy"))
    profile_scope = text[heading.end():]
    boundary = re.search(r"#{1,6}\s*(?:\*\*)?(?:חדשות|ניירות קשורים|תשואות|נתוני עסקאות)|\b(?:related securities|related stocks|news)\b", profile_scope, re.I)
    if boundary:
        profile_scope = profile_scope[:boundary.start()]
    industry = re.search(r"#{1,6}[ \t]*(?:\*\*)?ענף בבורסה(?:\*\*)?[ \t]*\n+[ \t]*(?P<value>[^\r\n]+)", profile_scope)
    if industry:
        value = industry["value"].strip(" *\r\n")
        if value and len(value) <= 200 and not re.search(r"[<>\[\]#]|https?://|loading|טוען", value, re.I):
            output.append(_record(source, candidate, "profile", industry[0], claims, field="industry", value=value))
    return output


def _objects(value, depth=0, path="$.structured_data"):
    if depth > 6:
        return
    if isinstance(value, dict):
        yield path, value
        for key, child in list(value.items())[:100]:
            yield from _objects(child, depth + 1, path + "[" + json.dumps(key) + "]")
    elif isinstance(value, list):
        for index, child in enumerate(value[:100]):
            yield from _objects(child, depth + 1, path + "[" + str(index) + "]")


def _json_span(text, key, value):
    # A parsed object alone does not preserve a literal source excerpt. Require
    # the corresponding raw JSON field in the fetched text as well.
    literal = json.dumps(value, ensure_ascii=False)
    pattern = re.escape(json.dumps(key, ensure_ascii=False)) + r"\s*:\s*" + re.escape(literal)
    match = re.search(pattern, text)
    return match[0] if match else None


def _structured_records(source, candidate):
    text, output = source["text"], []
    known = [candidate.get(key) for key in ("symbol", "secondary_symbol", "isin", "cusip")]
    for _, obj in islice(_objects(source.get("structured_data") or []), 500):
        identity = next(((key, value) for key, value in obj.items() if key.lower() in {"symbol", "ticker", "isin", "cusip"}
                         and any(_same_id(value, expected) for expected in known)), None)
        conflicting_symbol = any(key.lower() in {"symbol", "ticker"} and not any(_same_id(value, expected) for expected in known)
                                 for key, value in obj.items())
        def aliases(names):
            return [(key, value) for key, value in obj.items() if re.sub(r"[_-]", "", key).lower() in names]
        markets = aliases({"market", "exchange", "stockmarket"})
        currencies = aliases({"currency", "quotecurrency", "currencycode", "tradingcurrency"})
        units = aliases({"quoteunit", "rawquoteunit", "priceunit"})
        days = aliases({"pricedate", "quotedate", "date"})
        bases = aliases({"pricebasis", "basis"})
        adjustments = aliases({"adjusted", "isadjusted", "priceadjusted", "adjustment", "adjustmentbasis"})
        known_isins = [value for value in known if re.fullmatch(r"[A-Za-z]{2}[A-Za-z0-9]{9}\d", str(value or ""))]
        conflicting_isin = any(key.lower() == "isin" and known_isins and not any(_same_id(value, expected) for expected in known_isins)
                               for key, value in obj.items())
        if (not identity or conflicting_symbol or conflicting_isin or not markets or not currencies or not units or not days
                or any(_market(value) != _market(candidate.get("stock_market")) for _, value in markets)
                or any(value != candidate.get("currency") for _, value in currencies)
                or any(value != candidate.get("quote_unit") or value not in {"currency", "agorot", "cents"} for _, value in units)
                or any(value != days[0][1] for _, value in days)
                or any(not isinstance(value, str) or value not in {"last", "close"} or value != bases[0][1] for _, value in bases)
                or any(value is not False and not (type(value) is int and value == 0)
                       and not (isinstance(value, str) and value.lower() in {"false", "no", "unadjusted"}) for _, value in adjustments)):
            continue
        market, (currency_key, currency), (unit_key, unit), (date_key, day) = markets[0], currencies[0], units[0], days[0]
        try:
            if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
                continue
        except ValueError:
            continue
        identity_span, market_span = _json_span(text, *identity), _json_span(text, *market)
        currency_span = _json_span(text, currency_key, currency)
        unit_span, date_span = _json_span(text, unit_key, unit), _json_span(text, date_key, day)
        if not all((identity_span, market_span, currency_span, unit_span, date_span)):
            continue
        for basis in ("last", "close"):
            if bases and bases[0][1] != basis:
                continue
            amount = _number(obj.get(basis))
            excerpt = _json_span(text, basis, obj.get(basis)) if amount else None
            if amount and excerpt:
                output.append(_record(source, candidate, "price", excerpt,
                                      {"identity": identity_span, "market": market_span, "currency": currency_span, "unit": unit_span, "date": date_span, "basis": excerpt},
                                      currency=currency, quote_unit=unit, price_basis=basis, price_input=amount, price_date=day, observed_at=None))
    return output


def _themarker_profiles(source, candidate):
    parsed = urlsplit(source["url"])
    route = re.fullmatch(r"/stock/(\d+)/?", parsed.path)
    if (parsed.hostname != "finance.themarker.com" or not route or _market(candidate.get("stock_market")) != "TASE"
            or not any(_same_id(route[1], candidate.get(key)) for key in ("symbol", "secondary_symbol"))
            or str(candidate.get("asset_class") or "STOCK").upper() not in {"STOCK", "EQUITY", "SHARE"}):
        return []
    output = []
    for path, obj in islice(_objects(source.get("structured_data") or []), 500):
        type_key = next((key for key in ("assetType", "type") if key in obj), "")
        source_type = str(obj.get(type_key) or "").casefold()
        if not _same_id(obj.get("assetNumber"), route[1]) or source_type not in {"stock", "share", "equity", "מניה", "מניה רגילה"}:
            continue
        name_key = next((key for key in ("assetName", "name") if isinstance(obj.get(key), str)), "")
        name = obj.get(name_key, "")
        if not 1 <= len(name) <= 200 or name not in source["text"] or re.search(r"[<>\r\n]", name):
            continue
        # These are parsed-source claims, explicitly labelled by JSON path;
        # they are never presented as a verbatim JSON excerpt from visible text.
        claims = {"identity": {"path": path + '["assetNumber"]', "value": obj["assetNumber"]},
                  "instrument_type": {"path": path + "[" + json.dumps(type_key) + "]", "value": obj[type_key]},
                  "name": {"path": path + "[" + json.dumps(name_key) + "]", "value": name}}
        output.append(_record(source, candidate, "profile", name, claims, field="name", value=name))
    return output


def bond_profile_identity(candidate, text):
    """A validated debt identifier binds a profile without an exchange name.

    MANUAL records registration origin. This contract qualifies only profile
    facts; price/date/currency/unit validation continues to use its own rules.
    """
    if "BOND" not in {str(candidate.get(key) or "").upper() for key in ("asset_class", "asset_sub_class")}:
        return False
    expected = set()
    for key in ("symbol", "secondary_symbol", "cusip", "isin"):
        value = str(candidate.get(key) or "").upper().strip()
        if valid_cusip(value):
            expected.add(value)
        elif valid_isin(value) and value.startswith("US") and valid_cusip(value[2:11]):
            expected.add(value[2:11])
    if len(expected) != 1:
        return False
    actual = set()
    for value in re.findall(r"(?<!\w)[A-Z0-9*@#]{8}\d(?!\w)", text.upper()):
        if valid_cusip(value):
            actual.add(value)
    for value in re.findall(r"(?<!\w)[A-Z]{2}[A-Z0-9]{9}\d(?!\w)", text.upper()):
        if not valid_isin(value) or not value.startswith("US") or not valid_cusip(value[2:11]):
            return False
        actual.add(value[2:11])
    # Explicit malformed/conflicting IDs may not be discarded as incidental
    # text while a matching identifier elsewhere qualifies the record.
    for label, value in re.findall(r"\b(CUSIP|ISIN)\b[\s*：:|]*([A-Z0-9*@#]+)", text, re.I):
        value = value.upper()
        if (label.upper() == "CUSIP" and (not valid_cusip(value) or value not in expected)
                or label.upper() == "ISIN" and (not valid_isin(value) or not value.startswith("US") or value[2:11] not in expected)):
            return False
    return bool(actual) and actual == expected


def _bond_profiles(source, candidate):
    parsed = urlsplit(source["url"])
    text = source["text"]
    if parsed.hostname == "public.com":
        route = re.fullmatch(r"/(?:stocks/([A-Za-z0-9]{9})-bond|bonds/([A-Za-z0-9]{9}))/?", parsed.path)
        if not route:
            return []
        identifier = route[1] or route[2]
        if not bond_profile_identity(candidate, identifier):
            return []
        # The first instrument heading owns the page; never borrow identity
        # from a later About/Related heading or navigation link.
        heading = re.search(r"(?m)^#{1,3}\s+(?P<value>[^\r\n]{1,200}?)\s+\((?P<id>[A-Za-z0-9]{9})\)\s*$", text)
        if not heading or not bond_profile_identity(candidate, heading[0]) or heading["id"].upper() != identifier.upper():
            return []
        return [_record(source, candidate, "profile", heading[0], {"identity": heading["id"], "field": "instrument heading"},
                        field="name", value=heading["value"].strip())]
    if parsed.hostname in {"www.tradingview.com", "tradingview.com"} and re.fullmatch(r"/symbols/FINRA-[A-Za-z0-9]+/?", parsed.path):
        section = re.search(r"(?m)^#{1,4}\s+(?:\*\*)?Bond info(?:\*\*)?\s*$", text)
        if not section:
            return []
        card = re.split(r"(?m)^#{1,4}\s+", text[section.end():], maxsplit=1)[0]
        issuer = re.search(r"(?m)^\s*(?:\*\*)?Issuer(?:\*\*)?\s*\n+\s*(?P<value>[^\r\n]{1,200})", card)
        if not issuer or not bond_profile_identity(candidate, card):
            return []
        value = issuer["value"].strip(" *")
        if re.search(r"[<>\[\]#]|https?://", value, re.I):
            return []
        return [_record(source, candidate, "profile", card.strip(), {"identity": "bond card CUSIP/ISIN", "field": "Issuer"},
                        field="name", value=value)]
    return []


def _issuer_strip_profiles(source, candidate):
    """TVA's issuer offering documents bind component IDs to their issuer.

    Only the issuer name is returned. Cover coupon and parent maturity are not
    component terms, a price, or evidence that a held position was redeemed.
    """
    parsed = urlsplit(source["url"])
    if (parsed.hostname != "s205.q4cdn.com"
            or not re.fullmatch(r"/318912997/files/doc_downloads/irw/tva_bonds/[^/]+\.pdf", parsed.path, re.I)):
        return []
    text = source["text"]
    cover = re.search(r"(?m)^#\s+U\.S\.\$[\d,]+\s+(?P<issuer>[A-Za-z][A-Za-z &,.]{3,150}?)\s+\d+(?:\.\d+)?%\s+Global Power Bonds[^\r\n]*", text[:1000])
    if not cover or cover["issuer"] != "Tennessee Valley Authority":
        return []
    definition = re.search(r"of the " + re.escape(cover["issuer"]) + r"\s*\([^)]*TVA[^)]*\)", text[:2000])
    scope = re.search(r"If the Bonds are stripped into their separate Interest and Principal Components, the following Common Code, ISIN and CUSIP numbers will apply:", text)
    if not definition or not scope:
        return []
    table = text[scope.end():]
    if not re.match(r"\s*Common Code ISIN CUSIP\s+Interest Components\b", table):
        return []
    table = table.split("Principal Component", 1)[0]
    months = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    pattern = (r"(?P<date>" + months + r"\s+\d{1,2},\s+\d{4})\s+[^A-Za-z\d]*\s*\d{9}\s+"
               r"(?P<isin>US[A-Z0-9]{9}\d)\s+(?P<issuer_code>[A-Z0-9]{6})\s+(?P<issue>[A-Z0-9]{3})(?!\w)")
    output = []
    for row in re.finditer(pattern, table):
        cusip = row["issuer_code"] + row["issue"]
        if not valid_isin(row["isin"]) or row["isin"][2:11] != cusip or not bond_profile_identity(candidate, row["isin"] + " " + cusip):
            continue
        claims = {"issuer_title": cover[0], "issuer_definition": definition[0], "component_section": scope[0],
                  "component_row": row[0], "identity": {"isin": row["isin"], "cusip": cusip}, "component_date": row["date"]}
        output.append(_record(source, candidate, "profile", cover[0], claims, field="name", value=cover["issuer"]))
    return output


def context_records(source: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(source, dict) or not isinstance(candidate, dict) or not all(isinstance(source.get(key), str) for key in ("url", "text")):
        return []
    try:
        parsed = urlsplit(source["url"])
    except ValueError:
        return []
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return []
    return (_tase_records(source, candidate) + _structured_records(source, candidate) + _themarker_profiles(source, candidate)
            + _bond_profiles(source, candidate) + _issuer_strip_profiles(source, candidate))


def context_supported(source: dict[str, Any]) -> bool:
    """A recognized source must not bypass a failed context via legacy checks."""
    if not isinstance(source, dict):
        return False
    # Breadcrumbs, publisher metadata and unrelated schema objects do not own a
    # financial quote. An explicit structured quote contract does, even when a
    # conflicting identifier or unit makes its claimed observation invalid.
    for _, obj in islice(_objects(source.get("structured_data") or []), 500):
        keys = {str(key).lower().replace("_", "") for key in obj}
        if (keys & {"symbol", "ticker", "isin", "cusip"} and keys & {"last", "close"}
                and keys & {"market", "exchange", "stockmarket"} and keys & {"currency", "quotecurrency", "currencycode", "tradingcurrency"}):
            return True
    try:
        parsed = urlsplit(source.get("url") or "")
    except ValueError:
        return False
    return bool(parsed.scheme == "https" and not parsed.username and not parsed.password and (
        parsed.hostname == "market.tase.co.il" and _TASE_MAIN_PATH.fullmatch(parsed.path)
        or parsed.hostname == "finance.themarker.com" and re.fullmatch(r"/stock/\d+/?", parsed.path)))


def supports_context(source: dict[str, Any], candidate=None) -> bool:
    return context_supported(source)


def _matching_context(source, candidate, item, kind):
    if not isinstance(source, dict) or not isinstance(item, dict) or item.get("source_url") != source.get("url"):
        return None
    excerpt = item.get("evidence_quote")
    if not isinstance(excerpt, str) or not 1 <= len(excerpt) <= 2000 or _normal(excerpt) not in _normal(source.get("text")):
        return None
    for record in context_records(source, candidate):
        if record["kind"] != kind or _normal(record["evidence_quote"]) not in _normal(excerpt):
            continue
        fields = ("currency", "quote_unit", "price_basis", "price_date", "observed_at") if kind == "price" else ("field", "value")
        if any(item.get(field) != record.get(field) for field in fields):
            continue
        if kind == "price" and (type(item.get("price_input")) not in {int, float} or item["price_input"] != record["price_input"]):
            continue
        return record
    return None


def validate_contextual_observation(source, candidate, item):
    return _matching_context(source, candidate, item, "price")


def validate_contextual_profile(source, candidate, item):
    return _matching_context(source, candidate, item, "profile")
