"""Shared pure evidence checks for current and historical raw price research.

These helpers do not fetch sources, run models or access application storage.
"""
from __future__ import annotations

from datetime import date
import re
from typing import Any


def _source_records(text: str) -> list[str]:
    """Separate source records without splitting decimals or issuer suffixes."""
    records, start = [], 0
    boundaries = r"[|;]|[\r\n]+|(?<=[.!?,])\s+|\s+[-–—]\s+"
    for boundary in re.finditer(boundaries, text):
        before = text[:boundary.start()]
        if re.search(r"(?:\b(?:Inc|Corp|Co|Ltd)|\b(?:[A-Za-z]\.)+[A-Za-z])\.$", before, re.I):
            continue
        months = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        if (re.search(r"\b(?:" + months + r"\s+\d{1,2}|\d{1,2}\s+" + months + r"),$", before, re.I)
                and re.match(r"\d{4}(?!\d)", text[boundary.end():])):
            continue
        if re.search(r"\b(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.$", before, re.I):
            continue
        records.append(text[start:boundary.start()].strip())
        start = boundary.end()
    records.append(text[start:].strip())
    return [record for record in records if record]


def _observation_currency_matches(item: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """Keep the price's own currency/unit labels, including conflicting labels.

    Identity text elsewhere in an excerpt cannot turn ``Close EUR 100`` into a
    USD observation, or ``Close ILS 100`` into 100 agorot. Ambiguous mixed-unit
    excerpts are deliberately rejected rather than converted.
    """
    excerpt = item.get("evidence_quote")
    if not isinstance(excerpt, str):
        return False
    expected_currency = str(candidate.get("currency") or "").upper()
    expected_unit = candidate.get("quote_unit") or "currency"
    aliases = {"NIS": "ILS", "US$": "USD"}
    currencies = {aliases.get(match.upper(), match.upper()) for match in re.findall(
        r"(?<!\w)(USD|ILS|NIS|EUR|GBP|CAD|AUD|NZD|JPY|CHF|CNY|HKD|SGD|INR|ZAR|US\$)(?!\w)", excerpt, re.I)}
    if re.search(r"(?<!\w)US\$", excerpt, re.I):
        currencies.add("USD")
    explicit_currency = r"(?<!\w)(?:(?:quote|quoted|trading|price|reporting)\s+)?currency(?:\s+code)?\s*[:=]?\s*([A-Za-z]{3})(?![A-Za-z])"
    for code in re.findall(explicit_currency, excerpt, re.I):
        currencies.add(aliases.get(code.upper(), code.upper()))
    for code in re.findall(r"מטבע(?:\s+(?:מסחר|ציטוט))?\s*[:=]?\s*([A-Za-z]{3})(?![A-Za-z])", excerpt):
        currencies.add(aliases.get(code.upper(), code.upper()))
    currency_names = {
        "USD": r"(?:US|U\.S\.|United States|American)\s+dollars?|דולר(?:ים)?\s+אמריקאי(?:ם)?",
        "EUR": r"euros?|אירו",
        "GBP": r"pounds?\s+sterling|British\s+pounds?|פאונד|לירה\s+שטרלינג",
        "CAD": r"Canadian\s+dollars?|דולר(?:ים)?\s+קנדי(?:ם)?",
        "AUD": r"Australian\s+dollars?",
        "NZD": r"New Zealand\s+dollars?",
        "HKD": r"Hong Kong\s+dollars?",
        "SGD": r"Singapore\s+dollars?",
        "ILS": r"(?:Israeli\s+)?(?:new\s+)?shekels?|שקלים|שקל",
        "JPY": r"(?:Japanese\s+)?yen",
        "CHF": r"Swiss\s+francs?",
        "BRL": r"Brazilian\s+(?:reals?|reais)",
        "EGP": r"Egyptian\s+pounds?",
    }
    currencies.update(code for code, names in currency_names.items()
                      if re.search(r"(?<!\w)(?:" + names + r")(?!\w)", excerpt, re.I))
    currencies.update(currency for symbol, currency in (("€", "EUR"), ("£", "GBP"), ("₪", "ILS")) if symbol in excerpt)
    if currencies - {expected_currency}:
        return False
    units = set()
    if re.search(r"(?<!\w)(?:agorot|agora|אגורות|אגורה)(?!\w)", excerpt, re.I):
        units.add("agorot")
    if re.search(r"(?<!\w)cents?(?!\w)|¢", excerpt, re.I):
        units.add("cents")
    if re.search(r"(?<!\w)(?:pence|penny|pennies|GBX|GBp)(?!\w)", excerpt):
        return False  # Pence have no supported raw-unit mapping here.
    if units - {expected_unit}:
        return False
    # The maintained dated-price parser checks the number, basis and date. Here
    # inspect the same labelled amount for a currency or unit written beside it.
    labels = r"(?<!\w)(?:(?:שער|מחיר)\s+(?:אחרון|נעילה)|last|closing|close|נעילה)\b"
    filler = r"\s*(?:(?:quoted|traded|price|trade|value|at|is|as|of|unadjusted)\s+)*[:=]?\s*"
    measure = r"(?:[A-Z]{3}|US\$|agorot|agora|cents?|אגורות|אגורה|[$€₪£¢])"
    amount = r"(?P<amount>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?![\w,]|\.\d)"
    expression = labels + filler + r"(?P<before>\(?\s*(?:" + measure + r"\s*\)?\s*)*)" + amount + r"(?P<after>\s*(?:" + measure + r"\b|[€₪£¢$]))?"
    for match in re.finditer(expression, excerpt, re.I):
        if float(match["amount"].replace(",", "")) != float(item.get("price_input")):
            continue
        local = " ".join((match["before"] or "", match["after"] or ""))
        # Recognize an explicit local ISO currency even outside the common list.
        local_codes = {aliases.get(code, code) for code in re.findall(r"(?<!\w)[A-Z]{3}(?!\w)", local)}
        if local_codes - {expected_currency}:
            return False
        if "$" in local and expected_currency not in {"USD", "CAD", "AUD", "NZD", "HKD", "SGD"}:
            return False
        local_scaled = bool(re.search(r"agorot|agora|cents?|אגורות|אגורה|¢", local, re.I))
        if expected_unit in {"agorot", "cents"} and local.strip() and not local_scaled:
            return False
    return True


def _observation_record_matches(item: dict[str, Any], candidate: dict[str, Any], observed_day: date) -> bool:
    """Identity and the dated amount must belong to the same source record."""
    from .price_agent import _price_in_dated_quote, _source_identity
    excerpt = item["evidence_quote"]
    # A separate company description or related-stock record cannot lend its
    # identity to another sentence's price. Preserve decimal dots and U.S./U.K.
    # abbreviations; mixed records within one sentence are also rejected.
    records = _source_records(excerpt)
    for index, record in enumerate(records):
        sentences = [record]
        if index + 1 < len(records) and re.match(r"^(?:observed|observation\s+date|quote\s+date|as\s+of)\b", records[index + 1], re.I):
            sentences.append(record + " " + records[index + 1])
        for sentence in sentences:
            if len(re.findall(r"(?<!\w)(?:NASDAQ|NYSE(?:\s+ARCA)?|TASE|LSE|AMEX)(?!\w)", sentence, re.I)) > 1:
                continue
            if (_source_identity(sentence, candidate, candidate.get("quote_unit") or "currency")
                    and _price_in_dated_quote(sentence, observed_day, item["price_input"], item["price_basis"], item["observed_at"])):
                return True
    return False


def _historical_identity_conflicts(item: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """Allow a table header to identify rows, but never override row identity."""
    excerpt = str(item.get("evidence_quote") or "")
    known = {str(candidate.get(field) or "").strip().upper() for field in ("symbol", "secondary_symbol")}
    known.discard("")
    ticker = r"[A-Z0-9][A-Z0-9.^/-]{0,24}"
    venues = r"NASDAQ|NYSE(?:\s+ARCA)?|NYSEARCA|TASE|LSE|AMEX"
    price_labels = r"Last|Closing|Close|שער\s+(?:אחרון|נעילה)|מחיר\s+(?:אחרון|נעילה)|נעילה"
    tokens = re.findall(r"(?<![\w.])(" + ticker + r")\s+(?=\(?\s*(?i:" + venues + "|" + price_labels + r")\b)", excerpt)
    tokens += re.findall(r"(?i:\b(?:symbol|ticker|CUSIP|ISIN)\s*[:=]\s*)([A-Za-z0-9][A-Za-z0-9.^/-]{0,24})", excerpt)
    tokens += re.findall(r"(?i:\b(?:" + venues + r")\s*:\s*)([A-Za-z0-9][A-Za-z0-9.^/-]{0,24})", excerpt)
    non_tickers = {str(candidate.get("currency") or "").upper(), "USD", "US$", "ILS", "NIS", "AGOROT", "AGORA", "CENTS", "CENT"}
    for token in tokens:
        token = token.upper()
        # ISO/numeric dates and standalone day/year columns are ordinary rows,
        # not contradictory security identifiers before a price label.
        if (token in known or token in non_tickers or re.fullmatch(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", token)
                or token.isdigit() and (int(token) <= 31 or 1900 <= int(token) <= 2999)):
            continue
        return True
    expected = re.sub(r"\s+", "", str(candidate.get("stock_market") or "").upper())
    if expected in {"NASDAQ", "NYSE", "NYSEARCA", "TASE", "LSE", "AMEX"}:
        for venue in re.findall(r"(?<!\w)(?:" + venues + r")(?!\w)", excerpt, re.I):
            if re.sub(r"\s+", "", venue.upper()) != expected:
                return True
    return False


