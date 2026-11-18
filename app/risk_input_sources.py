"""No-registration primary APIs and literal primary-source risk observations.

The adapters never use provider keys. Auction yields, reporting currencies and
issuer addresses are deliberately not economic exposure/current market inputs.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import math
import re
from urllib.parse import urlsplit

import httpx

from .credit_ratings import _entity
from .security_identifiers import valid_cusip, valid_isin

SEC_TICKERS = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
TREASURY = "https://www.treasurydirect.gov/TA_WS/securities/search"
US_MARKETS = {"NASDAQ", "NYSE", "NYSEARCA", "AMEX", "NYSEAMERICAN", "YAHOO"}
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
US_STATE_NAMES = ("Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska",
    "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas",
    "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming", "District of Columbia")
SOURCE_FIELDS = frozenset({"issuer_id", "issuer_name", "country_code", "country_basis", "country_currency",
    "currency_exposures", "instrument_kind", "maturity_date", "plain_nominal_noncallable", "zero_coupon_confirmed",
    "sovereign_currency_basis", "pricing_model", "country_exposures", "continuous_yield", "current_spread_bps",
    "country_sensitivity", "cashflows", "fund_holdings"})

_CURRENCIES = {"usd":"USD", "u.s. dollars":"USD", "us dollars":"USD", "united states dollars":"USD",
    "eur":"EUR", "euro":"EUR", "euros":"EUR", "gbp":"GBP", "pounds sterling":"GBP", "sterling":"GBP",
    "ils":"ILS", "israeli shekels":"ILS", "new israeli shekels":"ILS", "chf":"CHF", "swiss francs":"CHF",
    "cad":"CAD", "canadian dollars":"CAD", "aud":"AUD", "australian dollars":"AUD", "jpy":"JPY",
    "japanese yen":"JPY", "cny":"CNY", "renminbi":"CNY", "sek":"SEK", "nok":"NOK", "dkk":"DKK",
    "nzd":"NZD", "hkd":"HKD", "sgd":"SGD"}
_QUALIFIED = re.compile(r"\b(?:not|except|excluding|other than|no longer|historical|previously|formerly|hypothetical|withdrawn|retracted|superseded|"
    r"pro\s*forma|illustrative|target|expected|forecast|intends?|would|could)\b", re.I)


def _currency(value):
    return _CURRENCIES.get(str(value).strip().casefold())


def _dated_value(value):
    value = str(value).strip().rstrip(".,;")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


_DATE_TEXT = r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})"


def _observation_date(source, text):
    """An explicit field/section date can bind a claim; a footer date cannot."""
    bound = _day(source.get("observation_date"))
    if source.get("observation_date") and not bound:
        return None
    dates = {_dated_value(match[1]) for match in re.finditer(r"\bAs (?:of|at)\s+(" + _DATE_TEXT + r")", text, re.I)} - {None}
    # A table's own explicit date/period cannot be relabelled with the report's
    # newer date merely because its heading omits the words 'as of'. Maturity
    # and payment dates are contractual future dates and are handled elsewhere.
    if not re.search(r"\b(?:Maturity|redemption|payment schedule|cash flow schedule)\b",text,re.I):
        local = {_dated_value(match[0]) for match in re.finditer(_DATE_TEXT,text)} - {None}
        if local and bound and local != {bound}:
            return None
    if len(dates) > 1 or dates and bound and dates != {bound}:
        return None
    observed = next(iter(dates)) if dates else bound
    return _day(observed)


def _tables(text):
    """Keep field labels, units and current-period column with their table rows."""
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if "|" not in lines[index]:
            index += 1
            continue
        start = index
        while index < len(lines) and "|" in lines[index] and lines[index].strip():
            index += 1
        raw = lines[start:index]
        rows = [[cell.strip().strip("*") for cell in line.strip().strip("|").split("|")] for line in raw]
        rows = [row for row in rows if row and not all(re.fullmatch(r"[:\- ]*", value) for value in row)]
        if len(rows) > 1:
            preceding = []
            for line in reversed(lines[max(0,start-3):start]):
                if "|" in line or not line.strip() and preceding:
                    break
                if line.strip():
                    preceding.append(line)
            prefix = "\n".join(reversed(preceding))
            yield prefix + "\n" + "\n".join(raw), rows


def _percent(value, percent_header=False):
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(%)?", str(value).strip())
    if not match or not (match[2] or percent_header):
        return None
    number = float(match[1]) / 100
    return number if math.isfinite(number) and 0 <= number <= 1 else None


def _retracted_context(text, block):
    """An adjacent qualification belongs to the observation, across blank lines.

    A model must not make an obsolete table current by quoting only its rows.
    Keep this local to the block so an unrelated document footer is not treated
    as a withdrawal of every fact in the filing.
    """
    normalized = " ".join(text.split())
    value = " ".join(block.split())
    start = normalized.find(value)
    if start < 0:
        return True
    following = normalized[start+len(value):].lstrip()[:500]
    if re.match(r"(?:However|Except|Excluding|Other than|But)\b",following,re.I):
        return True
    return bool(re.search(r"\b(?:table|allocation|exposure|holdings|schedule|terms|data|figures|information|above|preceding)\b"
        r"[^.!?]{0,250}\b(?:withdrawn|retracted|superseded|incorrect|invalid|must not be used|no longer (?:valid|accurate))\b",following,re.I))


def _same_value(a, b):
    # JSON boolean values must never pass as numeric 0/1.
    if type(a) is bool or type(b) is bool:
        return type(a) is type(b) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_same_value(a[key], b[key]) for key in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same_value(x,y) for x,y in zip(a,b))
    if type(a) in (int,float) and type(b) in (int,float):
        return math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=0,abs_tol=1e-10)
    return type(a) is type(b) and a == b


def _fund_table_bound(block, candidate):
    token = str(candidate.get("symbol") or "").strip()
    if not token:
        return False
    # A manager's name/website identifies the publisher, not the product. The
    # table's own heading must identify this exact fund or share class.
    heading = block.split("|",1)[0]
    labels = re.findall(r"(?im)^\s*(?:Fund|Ticker|Symbol|ISIN|Security(?: identifier| number)?)\s*[:#]\s*([^\n]+)",heading)
    if labels:
        return bool(re.search(r"(?<![A-Za-z0-9_])"+re.escape(token)+r"(?![A-Za-z0-9_])",labels[-1],re.I))
    identifiers = [line.strip() for line in heading.splitlines() if re.fullmatch(r"[A-Z0-9_][A-Z0-9_.=-]{1,79}",line.strip())]
    return bool(identifiers and identifiers[-1].upper() == token.upper())


def _issue_section(text, candidate, source):
    tokens = {str(candidate.get(key) or "").strip().upper() for key in ("cusip","isin","symbol","secondary_symbol")}
    tokens = {token for token in tokens if valid_cusip(token) or valid_isin(token)}
    if not tokens:
        return None
    headers = list(re.finditer(r"(?im)^\s*\|?\s*(?:CUSIP|ISIN)(?:\s+(?:number|code))?\s*[:|#]?\s*([A-Za-z0-9]{9,12})\b[^\n]*",text))
    if headers:
        matches = [(index,match) for index,match in enumerate(headers) if match[1].upper() in tokens]
        if not matches:
            return None
        # Keep only this exact issue's declared section. A token mentioned in
        # another issue's prose or an annual report index does not bind terms.
        sections = [text[match.start():headers[index+1].start() if index+1 < len(headers) else len(text)] for index,match in matches]
        if any({value.upper() for value in re.findall(r"\b[A-Z0-9]{9,12}\b",section)
                if valid_cusip(value) or valid_isin(value)}-tokens for section in sections):
            return None
        return "\n".join(sections)
    # A verified issue-specific URL may bind a document without an issue label.
    path = urlsplit(str(source.get("url") or "")).path
    if not any(re.search(r"(?<![A-Za-z0-9])"+re.escape(token)+r"(?![A-Za-z0-9])",path,re.I) for token in tokens):
        return None
    mentioned = {value.upper() for value in re.findall(r"\b[A-Z0-9]{9,12}\b",text)
        if valid_cusip(value) or valid_isin(value)}
    return text if not mentioned-tokens else None


def _literal_risk_records(source, candidate):
    """Parse supported source-local labels, never numeric tokens out of context.

    A source table is deliberately not normalized to 100%. Comparative columns,
    partial holdings, revenue geography and a reporting currency remain unknown.
    """
    from .sovereign_ratings import normalize_country
    text = str(source.get("text") or "")
    bond = str(candidate.get("asset_class") or "").upper() == "BOND"
    fund = str(candidate.get("asset_class") or "").upper() in {"ETF","MUTUALFUND","FUND"}
    if bond:
        text = _issue_section(text,candidate,source)
        if text is None:
            return []
    records = []
    # Explicit economic-country/currency labels are independent of an issuer's
    # address, reporting currency and place of listing.
    lines = text.splitlines()
    for index,raw_line in enumerate(lines):
        line = re.sub(r"\s*\|\s*",": ",raw_line.strip().strip("|").strip()).rstrip(".")
        country_match = re.fullmatch(r"(?:Economic country|Country economic exposure)\s*:\s*(.+)",line,re.I)
        currency_match = re.fullmatch(r"(?:Economic country currency|Country currency)\s*:\s*(.+)",line,re.I)
        if fund or not (country_match or currency_match):
            continue
        observed = _observation_date(source,"\n".join(lines[max(0,index-3):index+1]))
        if not observed or _QUALIFIED.search(line) or _retracted_context(text,raw_line):
            continue
        public = {**source,"evidence_quote":raw_line}
        if country_match and (code := normalize_country(country_match[1])):
            records += [_record(field,value,public,as_of=observed,basis="reported_allocation") for field,value in
                (("country_code",code),("country_basis","economic_exposure"))]
        if currency_match and (currency := _currency(currency_match[1])):
            records.append(_record("country_currency",currency,public,as_of=observed,basis="reported_allocation"))
    for block, rows in _tables(text):
        observed = _observation_date(source,block)
        if (not observed or _QUALIFIED.search(block) or _retracted_context(text,block)
                or fund and not _fund_table_bound(block,candidate)):
            continue
        header = " ".join(rows[0]).casefold()
        context = block.split("|",1)[0].casefold() + " " + header
        if len(rows[0]) != 2 or any(len(row) != 2 for row in rows):
            continue
        if re.search(r"revenue|sales|reporting currency|presentation currency|financial statements",context):
            continue
        percent_header = bool(re.search(r"%|percent",rows[0][1],re.I))
        currency_table = bool(re.search(r"(?:economic|investment|portfolio).*currency|currency.*(?:exposure|denomination|allocation)",context))
        country_table = bool(re.search(r"(?:economic|investment|portfolio).*countr|countr.*(?:exposure|allocation)",context))
        holdings_table = bool(re.search(r"(?:complete|all).*?(?:fund )?holdings|(?:complete|all).*?constituents",context))
        if currency_table or country_table or holdings_table:
            allocations = {}
            valid = True
            for label, amount in rows[1:]:
                if label.casefold() in {"total", "total portfolio", "total investments"}:
                    if _percent(amount,percent_header) != 1:
                        valid = False
                    continue
                key = _currency(label) if currency_table else normalize_country(label) if country_table else label.strip()
                weight = _percent(amount,percent_header)
                if not key or key in allocations or weight is None:
                    valid = False
                    break
                allocations[key] = weight
            if not valid or not allocations or not math.isclose(math.fsum(allocations.values()),1,abs_tol=1e-8):
                continue
            public = {**source,"evidence_quote":block}
            if currency_table:
                records.append(_record("currency_exposures",allocations,public,as_of=observed,basis="reported_investment_currency"))
            elif country_table:
                records.append(_record("country_exposures",allocations,public,as_of=observed,basis="reported_allocation"))
                if len(allocations) == 1:
                    code = next(iter(allocations))
                    records += [_record(field,value,public,as_of=observed,basis="reported_allocation") for field,value in
                        (("country_code",code),("country_basis","economic_exposure"))]
            else:
                if all(re.fullmatch(r"[A-Z0-9][A-Z0-9.^= -]{0,79}",key) for key in allocations):
                    records.append(_record("fund_holdings",[{"identifier":key,"weight":weight} for key,weight in allocations.items()],
                        public,as_of=observed,basis="reported_fund_holdings"))

    # A currency of contractual bond cash flows is an economic exposure. An
    # equity's financial-statement or listing currency is not.
    observed = _observation_date(source,text)
    if not bond:
        return records
    # Positive assertions only. A source's explicit nonlinear terms override
    # ordinary debt descriptions elsewhere in the document.
    if re.search(r"\b(?:callable|convertible|floating[ -]rate|inflation[ -]linked|index[ -]linked)\s*:\s*(?:yes|true)\b",text,re.I):
        records.append(_record("unsupported_bond",True,source,as_of=observed))
    for raw_line in text.splitlines():
        line = raw_line.strip().strip("|").strip()
        if not line or _QUALIFIED.search(line) or _retracted_context(text,raw_line):
            continue
        clean = re.sub(r"\s*\|\s*",": ",line).strip().rstrip(".")
        public = {**source,"evidence_quote":raw_line}
        match = re.fullmatch(r"(?:Maturity(?: date)?|Final redemption date)\s*:\s*("+_DATE_TEXT+r")",clean,re.I)
        if match and (maturity := _dated_value(match[1])):
            records.append(_record("maturity_date",maturity,public,as_of=observed))
        for field,label,unit,scale in (
            ("current_spread_bps",r"Current (?:credit )?spread",r"(?:bps|basis points)",1),
            ("continuous_yield",r"(?:Annual )?continuously compounded (?:discount )?yield",r"(?:%|percent)",.01),
            ("country_sensitivity",r"Country spread sensitivity(?: \(kappa\))?",r"(?:fraction|coefficient)",1)):
            value = re.fullmatch(label+r"\s*:\s*(-?[0-9]+(?:\.[0-9]+)?)\s*"+unit,clean,re.I)
            if value and observed:
                number = float(value[1])*scale
                if math.isfinite(number) and (field == "continuous_yield" or number >= 0) and (field != "country_sensitivity" or number <= 1):
                    records.append(_record(field,number,public,as_of=observed))
        value = re.fullmatch(r"(?:Contractual (?:payment |cash flow )?currency|Bond denomination currency)\s*:\s*(.+)",clean,re.I)
        if value and (currency := _currency(value[1])):
            records.append(_record("currency_exposures",{currency:1},public,as_of=observed,basis="contractual_cashflow_currency"))
        classifications = (
            (r"Instrument (?:kind|type)\s*:\s*corporate bond","instrument_kind","corporate_bond"),
            (r"Instrument (?:kind|type)\s*:\s*sovereign bond","instrument_kind","sovereign_bond"),
            (r"(?:Plain nominal noncallable|Fixed nominal noncallable)\s*:\s*(?:yes|true)","plain_nominal_noncallable",True),
            (r"Zero[ -]coupon(?: confirmed)?\s*:\s*(?:yes|true)","zero_coupon_confirmed",True),
            (r"Sovereign currency basis\s*:\s*local[ _-]currency","sovereign_currency_basis","local_currency"),
            (r"Sovereign currency basis\s*:\s*foreign[ _-]currency","sovereign_currency_basis","foreign_currency"))
        for pattern,field,value in classifications:
            if re.fullmatch(pattern,clean,re.I):
                records.append(_record(field,value,public,as_of=observed))
    # Do not accept a partial coupon table as the full future payment schedule.
    for block,rows in _tables(text):
        if not re.search(r"complete (?:remaining |future )?(?:contractual )?(?:cash flow|payment) schedule.*(?:including redemption|including principal)",block,re.I):
            continue
        if _QUALIFIED.search(block) or _retracted_context(text,block) or len(rows[0]) != 2 or not re.search(r"date",rows[0][0],re.I) or not re.search(r"amount",rows[0][1],re.I):
            continue
        flows = []
        for row in rows[1:]:
            if len(row) != 2 or not (day := _dated_value(row[0])) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?",row[1]):
                flows = []
                break
            amount = float(row[1])
            if not math.isfinite(amount) or amount <= 0:
                flows=[]
                break
            flows.append({"date":day,"amount":amount})
        if flows:
            records.append(_record("cashflows",sorted(flows,key=lambda row:row["date"]),{**source,"evidence_quote":block},as_of=observed))
    values = {record["field"]:record["value"] for record in records}
    if values.get("zero_coupon_confirmed") is True:
        records.append(_record("pricing_model","zero_coupon_continuous",source,as_of=observed))
    elif values.get("cashflows"):
        records.append(_record("pricing_model","cashflows_continuous",source,as_of=observed))
    return records


def now():
    return datetime.now(timezone.utc).isoformat()


def _day(value):
    try:
        result = date.fromisoformat(str(value)[:10])
        return result.isoformat() if result <= date.today() else None
    except ValueError:
        return None


def _record(field, value, source, *, as_of=None, basis="reported"):
    record = {"field":field, "value":value, "source_url":source["url"],
        "source_kind":source.get("source_kind", "regulatory"), "retrieved_at":source["retrieved_at"],
        "as_of":as_of, "basis":basis, "evidence_quote":source.get("evidence_quote") or source["text"][:2000],
        "verification_status":"verified", "units":({"currency_exposures":"fraction", "country_exposures":"fraction",
            "fund_holdings":"fraction", "maturity_date":"contractual_date", "cashflows":"contractual_cashflows",
            "current_spread_bps":"basis_points", "continuous_yield":"annual_continuous_decimal",
            "country_sensitivity":"fraction"}.get(field,"identity_or_classification"))}
    if _day(source.get("published_at")):
        record["published_at"] = source["published_at"]
    if source.get("source_listing"):
        record["source_listing"] = source["source_listing"]
    record["record_id"] = "risk-" + hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()[:24]
    return record


def no_registration_fields(candidate):
    market = re.sub(r"[^A-Z]", "", str(candidate.get("stock_market") or "").upper())
    asset = str(candidate.get("asset_class") or "").upper()
    if asset in {"EQUITY", "RSU"} and market in US_MARKETS:
        return ["issuer_identity", "issuer_domicile"]
    if asset == "BOND" and _cusip(candidate):
        return ["issuer_identity", "bond_kind", "bond_maturity", "bond_terms", "sovereign_currency_basis"]
    return []


def _cusip(candidate):
    values = set()
    for key in ("symbol", "secondary_symbol", "cusip", "isin"):
        value = str(candidate.get(key) or "").upper()
        if valid_cusip(value):
            values.add(value)
        elif value.startswith("US") and valid_isin(value) and valid_cusip(value[2:11]):
            values.add(value[2:11])
    return next(iter(values)) if len(values) == 1 else None


class PublicRiskAPIs:
    def __init__(self, *, transport=None):
        self.transport = transport

    def fetch(self, candidate):
        result = {"records":[], "sources":[], "status":"unavailable", "code":"no_public_api", "requests":0}
        def get(url, params=None):
            result["requests"] += 1
            with httpx.Client(timeout=15, follow_redirects=False, trust_env=False, transport=self.transport,
                headers={"User-Agent":"portfolio-analyzer/1.0 contact@example.local", "Accept":"application/json"}) as client:
                response = client.get(url,params=params)
                response.raise_for_status()
                if len(response.content) > 5_000_000:
                    raise ValueError("source_limit")
                return response.json(), str(response.url)
        try:
            asset = str(candidate.get("asset_class") or "").upper()
            if asset in {"EQUITY", "RSU"} and no_registration_fields(candidate):
                index, _ = get(SEC_TICKERS)
                columns = index.get("fields", [])
                rows = [dict(zip(columns,row)) for row in index.get("data", [])]
                symbol = str(candidate.get("symbol") or "").upper()
                market = str(candidate.get("stock_market") or "").upper()
                matches = [r for r in rows if str(r.get("ticker") or "").upper() == symbol
                           and (market == "YAHOO" or str(r.get("exchange") or "").upper() == market)]
                if len(matches) != 1:
                    return {**result, "code":"source_identity_unavailable"}
                cik = str(int(matches[0]["cik"])).zfill(10)
                payload, url = get(SEC_SUBMISSIONS.format(cik=cik))
                tickers = [str(v).upper() for v in payload.get("tickers", [])]
                exchanges = [str(v).upper() for v in payload.get("exchanges", [])]
                resolved_market = str(matches[0].get("exchange") or "").upper()
                if (str(int(payload.get("cik"))) != str(int(cik)) or (symbol,resolved_market) not in set(zip(tickers,exchanges))
                        or not payload.get("name")):
                    return {**result, "code":"source_identity_unavailable"}
                source = {"url":url, "retrieved_at":now(), "source_kind":"regulatory", "text":json.dumps({
                    k:payload.get(k) for k in ("cik","name","tickers","exchanges","addresses")}),
                    "source_listing":{"ticker":symbol,"exchange":resolved_market}}
                records = [_record("issuer_id","sec:"+str(int(cik)),source), _record("issuer_name",payload["name"],source)]
                recent = (payload.get("filings") or {}).get("recent") or {}
                filing_sources=[]
                for index,form in enumerate(recent.get("form", [])):
                    if form not in {"10-K", "10-Q"}:
                        continue
                    try:
                        accession=recent["accessionNumber"][index]
                        document=recent["primaryDocument"][index]
                        observed=_day(recent["reportDate"][index])
                        published=_day(recent["filingDate"][index])
                        if not observed or not published or not re.fullmatch(r"[0-9-]+",accession) or not re.fullmatch(r"[A-Za-z0-9_.-]+",document):
                            continue
                        filing_sources.append({"url":f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-','')}/{document}",
                            "as_of":observed,"published_at":published,"form":form,"accession":accession})
                    except (KeyError,IndexError,TypeError):
                        continue
                    if len(filing_sources)==2:
                        break
                if filing_sources:
                    records.append(_record("filing_sources",filing_sources,source))
                address = (payload.get("addresses") or {}).get("business") or {}
                if address.get("stateOrCountry") in US_STATES:
                    records += [_record("country_code","US",source,basis="issuer_domicile_proxy"),
                                _record("country_basis","issuer_domicile_proxy",source,basis="issuer_domicile_proxy")]
            elif asset == "BOND" and (cusip := _cusip(candidate)):
                rows, url = get(TREASURY,{"cusip":cusip,"format":"json"})
                rows = [r for r in rows if isinstance(r,dict) and r.get("cusip") == cusip and _day(r.get("issueDate"))] if isinstance(rows,list) else []
                if not rows:
                    return {**result,"code":"data_unavailable"}
                row = max(rows,key=lambda r:r["issueDate"])
                source = {"url":url,"retrieved_at":now(),"source_kind":"government_public","text":json.dumps(row)}
                observed = _day(row.get("issueDate"))
                records = [_record("issuer_id","sovereign:US",source,as_of=observed),
                    _record("issuer_name","United States Department of the Treasury",source,as_of=observed),
                    _record("instrument_kind","sovereign_bond",source,as_of=observed),
                    _record("country_code","US",source,as_of=observed),
                    _record("country_basis","economic_exposure",source,as_of=observed),
                    _record("country_currency","USD",source,as_of=observed),
                    _record("sovereign_currency_basis","local_currency",source,as_of=observed)]
                maturity = str(row.get("maturityDate") or "")[:10]
                try:
                    records.append(_record("maturity_date",date.fromisoformat(maturity).isoformat(),source,as_of=observed))
                except ValueError:
                    pass
                if (row.get("securityType") == "Bill" and row.get("floatingRate") == "No"
                        and row.get("inflationProtected") == "No"):
                    records += [_record(field,value,source,as_of=observed) for field,value in (
                        ("plain_nominal_noncallable",True),("zero_coupon_confirmed",True),("pricing_model","zero_coupon_continuous"))]
                if any(row.get(field) == "Yes" for field in ("floatingRate","inflationProtected","callable")):
                    records.append(_record("unsupported_bond",True,source,as_of=observed))
            else:
                return result
            result.update(records=records,sources=[{**source,"fields":[r["field"] for r in records]}],status="updated",code="data_found")
            return result
        except (httpx.HTTPError,ValueError,TypeError,KeyError,OverflowError):
            return {**result,"code":"provider_unavailable"}


def _current_allocation_statements(text, observed):
    """Whole issuer statements only; an embedded 'all' is not an allocation.

    Keep U.S. dollars together when splitting sentences. A dated comparative
    must match the report's bound observation date; bare past-tense statements
    and quoted, conditional or qualified substrings cannot supply current facts.
    """
    normalized = re.sub(r"\s+", " ", text).strip()
    quotes = re.split(r"(?<=[.!?])\s+(?![Dd]ollars\b)(?=[A-Z])", normalized)
    context_date = None
    for index, quote in enumerate(quotes):
        statement = quote.strip().rstrip(".!?").strip()
        explicit_date = False
        dated = re.fullmatch(r"As (?:of|at) (\d{4}-\d{2}-\d{2}|[A-Za-z]+ \d{1,2},? \d{4}|\d{1,2} [A-Za-z]+ \d{4})(?:,? (.+))?", statement, re.I)
        if dated:
            value = dated[1].replace(",", "")
            parsed = None
            for fmt in ("%Y-%m-%d", "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y"):
                try:
                    parsed = datetime.strptime(value, fmt).date().isoformat()
                    break
                except ValueError:
                    pass
            context_date = parsed or "unknown"
            if context_date != str(observed or "")[:10] or not dated[2]:
                continue
            statement, explicit_date = dated[2], True
        elif context_date is not None:
            if context_date != str(observed or "")[:10]:
                continue
            explicit_date = True
        if re.search(r"\b(?:historical|previously|formerly|comparative|hypothetical)\b", statement, re.I):
            context_date = "ambiguous"
        following = quotes[index + 1] if index + 1 < len(quotes) else ""
        retracted = bool(re.search(r"\b(?:no longer|not true|not all|however|except|excluding|other than|but|not necessarily)\b", following, re.I))
        yield statement, quote.strip(), explicit_date, context_date != "ambiguous" and not retracted


def extract_risk_records(source, candidate):
    """Select literal observations; no AI-authored numeric facts are accepted."""
    from .country_currency_reference import SIX_CURRENCY_URL, currency_reference_records
    if source.get("url") == SIX_CURRENCY_URL:
        return currency_reference_records(source, candidate)
    if source.get("published_at") and not _day(source["published_at"]):
        return []
    host = (urlsplit(str(source.get("url") or "")).hostname or "").lower().removeprefix("www.")
    domains = {str(v).lower().removeprefix("www.") for v in candidate.get("verified_issuer_domains", [])}
    if not any(host == domain or host.endswith("."+domain) for domain in domains if domain) and not (host == "sec.gov" or host.endswith(".sec.gov") or host == "treasurydirect.gov" or host.endswith(".treasurydirect.gov")):
        return []
    text = str(source.get("text") or "")
    source_issuer=None
    source_legal=None
    bound_filing=False
    if host == "sec.gov" or host.endswith(".sec.gov"):
        path=urlsplit(str(source.get("url") or "")).path
        issuer=str(candidate.get("researched_issuer_id") or "")
        if match:=re.fullmatch(r"/submissions/CIK([0-9]{10})\.json",path):
            # Submissions JSON can itself establish a new exact ticker/exchange
            # binding. A generic filing mentioning the name cannot.
            try:
                prefix=text.split('"filings"',1)[0].rstrip(" \n\t,:")
                payload=json.loads(prefix+"}" if '"filings"' in text else text)
                cik=str(int(match[1]))
                market = str(candidate.get("stock_market") or "").upper()
                symbol = str(candidate.get("symbol") or "").upper()
                listings = list(zip([str(v).upper() for v in payload.get("tickers",[])],[str(v).upper() for v in payload.get("exchanges",[])]))
                matching = [(ticker,exchange) for ticker,exchange in listings if ticker == symbol and (market == "YAHOO" or exchange == market)]
                if str(int(payload.get("cik"))) != cik or len(matching) != 1 or not payload.get("name"):
                    return []
                source_issuer,source_legal="sec:"+cik,payload["name"]
            except (ValueError,TypeError,KeyError):
                return []
        else:
            match=re.match(r"/Archives/edgar/data/([0-9]+)/",path,re.I)
            manifests=[filing for row in candidate.get("source_evidence",[]) if row.get("field")=="filing_sources" for filing in row.get("value",[])]
            if (not match or issuer != "sec:"+str(int(match[1]))
                    or not any(filing.get("url")==source.get("url") for filing in manifests)):
                return []
            bound_filing=True
    legal = next((value for value in (candidate.get("researched_issuer_name"),candidate.get("issuer_name"),candidate.get("name"))
        if len(_entity(value))>=6 and _entity(value)!=_entity(candidate.get("symbol")) and _entity(value) in _entity(text)),None)
    legal=source_legal or legal
    if not legal:
        return []
    public = {**source,"source_kind":"regulatory" if "sec.gov" in host else "issuer_ir"}
    observed = source.get("observation_date") or _observation_date(source,text)
    records = [_record("issuer_id",source_issuer or candidate.get("researched_issuer_id") or "issuer:"+_entity(legal),public),_record("issuer_name",legal,public)]
    if bound_filing and _day(observed):
        # A dated registrant cover-page address supplies an explicit domicile
        # proxy only. It says nothing about investment-country/currency weights.
        states = "|".join(re.escape(value) for value in sorted([*US_STATES, *US_STATE_NAMES], key=len, reverse=True))
        address = re.search(r"\b[A-Za-z][A-Za-z .'-]{1,80},[ \t]*(?:" + states
            + r")[ \t]+[0-9]{5}(?:-[0-9]{4})?\s*\(\s*Address of Principal Executive Offices\s*\)(?:\s*\(\s*Zip Code\s*\))?",
            text[:12000], re.I)
        if address:
            prefix = text[max(0,address.start()-2000):address.start()]
            if _entity(legal) in _entity(prefix) and re.search(r"Exact Name of Registrant", prefix, re.I):
                quote = {**public, "evidence_quote": address[0]}
                records += [_record(field,value,quote,as_of=observed,basis="issuer_domicile_proxy") for field,value in (
                    ("country_code","US"),("country_basis","issuer_domicile_proxy"))]
    # Only full affirmative first-person statements qualify. Regex searching
    # for an embedded 'all' would turn 'not all', exceptions and history into
    # fabricated 100% allocations. Different current all-portfolio statements
    # within the same source also cannot establish a consistent full allocation.
    currency_quotes, country_quotes = [], []
    currency_conflict = country_conflict = False
    # A legal-name heading is a document boundary even without punctuation.
    # Do not introduce boundaries inside arbitrary qualified issuer statements.
    allocation_text = "\n".join(line+"." if _entity(line) == _entity(legal) and not line.rstrip().endswith((".","!","?")) else line
        for line in text.splitlines())
    fund = str(candidate.get("asset_class") or "").upper() in {"ETF","MUTUALFUND","FUND"}
    for statement, quote, explicitly_dated, current in _current_allocation_statements(allocation_text, observed):
        if fund:
            # First-person prose from the manager is not a fund-specific
            # allocation. Fund facts require their exact identified table.
            continue
        if re.search(r"\b(?:not|except|excluding|other than|no longer)\b", statement, re.I):
            if re.search(r"\bdenominated\b", statement, re.I):
                currency_conflict = True
            if re.search(r"\b(?:located|based|domiciled)\b", statement, re.I):
                country_conflict = True
        if not current:
            continue
        currency = re.fullmatch(r"All (?:of )?our (?:investments|loans|portfolio investments) (are|were) denominated in (.+)", statement, re.I)
        if currency and (currency[1].lower() == "are" or explicitly_dated):
            if code := _currency(currency[2]):
                currency_quotes.append((quote,code))
            else:
                currency_conflict = True
        country = re.fullmatch(r"(?:All (?:of )?our (?:investments|portfolio companies|loans)|100(?:\.0+)?% of our (?:investments|portfolio)) (are|is|were|was) (?:located|based|domiciled) in (.+)", statement, re.I)
        if country and (country[1].lower() in {"are", "is"} or explicitly_dated):
            from .sovereign_ratings import normalize_country
            name = re.sub(r"^the\s+","",country[2],flags=re.I)
            code = "US" if re.fullmatch(r"U\.S\.?",name,re.I) else normalize_country(name)
            if code:
                country_quotes.append((quote,code))
            else:
                country_conflict = True
    if currency_quotes and not currency_conflict and len({code for _,code in currency_quotes}) == 1:
        records.append(_record("currency_exposures", {currency_quotes[0][1]:1},
            {**public, "evidence_quote":currency_quotes[0][0]}, as_of=observed, basis="reported_investment_currency"))
    if country_quotes and not country_conflict and len({code for _,code in country_quotes}) == 1:
        code = country_quotes[0][1]
        source_quote = {**public,"evidence_quote":country_quotes[0][0]}
        records += [_record(field,value,source_quote,as_of=observed,basis="reported_allocation") for field,value in (
            ("country_code",code),("country_basis","economic_exposure"))]
        if code == "US":
            records.append(_record("country_currency","USD",source_quote,as_of=observed,basis="reported_allocation"))
    records.extend(_literal_risk_records(public,candidate))
    if any(row["field"] == "country_basis" and row["value"] == "economic_exposure" for row in records):
        records = [row for row in records if not (row["field"] in {"country_code","country_basis"}
            and row.get("basis") == "issuer_domicile_proxy")]
    # Conflicting source-local facts cannot be resolved by whichever row the
    # model happens to select or the order in which a document was parsed.
    conflicting = {field for field in {row["field"] for row in records}
        if len({json.dumps(row["value"],sort_keys=True) for row in records if row["field"] == field}) > 1}
    if "country_code" in conflicting:
        conflicting |= {"country_basis","country_currency"}
    if any(row["field"] == "unsupported_bond" and row["value"] is True for row in records):
        conflicting |= {"plain_nominal_noncallable","zero_coupon_confirmed","pricing_model","cashflows"}
    return list({row["record_id"]:row for row in records if row["field"] not in conflicting}.values())


def extract_proposed_risk_records(source, candidate, proposal):
    """Reparse an exact fetched quotation; model-authored facts never verify it.

    The planner can identify a source section and its units, but the application
    supplies the value only if source-local labels independently reproduce it.
    This method has no network or storage access.
    """
    if isinstance(proposal,list):
        return [row for claim in proposal[:100] for row in extract_proposed_risk_records(source,candidate,claim)]
    if not isinstance(proposal,dict) or proposal.get("security_key") != candidate.get("security_key") or proposal.get("source_id") != source.get("source_id"):
        return []
    field = proposal.get("field")
    quote = proposal.get("evidence_quote")
    if field not in SOURCE_FIELDS or not isinstance(quote,str) or not 10 <= len(quote) <= 12000:
        return []
    raw_text = str(source.get("text") or "")
    text = " ".join(raw_text.split())
    normalized = " ".join(quote.split())
    start = text.find(normalized)
    if start < 0:
        return []
    from .country_currency_reference import SIX_CURRENCY_URL, currency_reference_records
    if source.get("url") == SIX_CURRENCY_URL:
        return [record for record in currency_reference_records(source,candidate)
            if field == "country_currency" and proposal.get("value") == record["value"]
            and proposal.get("units") == record["units"] and proposal.get("as_of") == record["as_of"]
            and " ".join(record["evidence_quote"].split()) == normalized]
    # Reject quotations cut out of the middle of a qualified assertion.
    before = text[:start].rstrip()
    after = text[start+len(normalized):].lstrip()
    raw_match = re.search(r"\s+".join(re.escape(part) for part in quote.split()),raw_text)
    starts_line = bool(raw_match and not raw_text[:raw_match.start()].rsplit("\n",1)[-1].strip())
    ends_line = bool(raw_match and not raw_text[raw_match.end():].split("\n",1)[0].strip())
    if before and before[-1].isalnum() and not starts_line or after and after[0].isalnum() and normalized[-1:].isalnum() and not ends_line:
        return []
    full = extract_risk_records(source,candidate)
    if not any(row["field"] == "issuer_id" for row in full):
        return []
    observed = _observation_date(source,quote)
    if not observed or proposal.get("as_of") != observed:
        return []
    units = proposal.get("units")
    value = proposal.get("value")
    if field in {"currency_exposures","country_exposures"}:
        if units not in {"fraction","percent"} or not isinstance(value,dict):
            return []
        if units == "percent":
            if any(type(number) not in (int,float) or not math.isfinite(number) for number in value.values()):
                return []
            value = {key:number/100 for key,number in value.items()}
    elif field == "continuous_yield":
        if units == "annual_continuous_percent" and type(value) in (int,float) and math.isfinite(value):
            value /= 100
        elif units != "annual_continuous_decimal":
            return []
    elif units != {"current_spread_bps":"basis_points","country_sensitivity":"fraction",
            "fund_holdings":"fraction","cashflows":"contractual_cashflows","maturity_date":"contractual_date"}.get(field,"identity_or_classification"):
        return []
    # Require the exact field to be supported by the complete document as well
    # as by the selected quote, so removing an adjacent retraction cannot help.
    matches = [row for row in full if row["field"] == field and row.get("as_of") == observed and _same_value(row["value"],value)]
    if not matches:
        return []
    # Retain the full source-local evidence selected by the server parser.
    return matches
