"""No-registration primary APIs and literal primary-source risk observations.

The adapters never use provider keys. Auction yields, reporting currencies and
issuer addresses are deliberately not economic exposure/current market inputs.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit

import httpx

from .credit_ratings import _entity
from .security_identifiers import valid_cusip, valid_isin

SEC_TICKERS = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
TREASURY = "https://www.treasurydirect.gov/TA_WS/securities/search"
US_MARKETS = {"NASDAQ", "NYSE", "NYSEARCA", "AMEX", "NYSEAMERICAN"}
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
US_STATE_NAMES = ("Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska",
    "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas",
    "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming", "District of Columbia")
SOURCE_FIELDS = frozenset({"issuer_id", "issuer_name", "country_code", "country_basis", "country_currency",
    "currency_exposures", "instrument_kind", "maturity_date", "plain_nominal_noncallable", "zero_coupon_confirmed",
    "sovereign_currency_basis", "pricing_model"})


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
        "verification_status":"verified", "units":"fraction" if field == "currency_exposures" else "contractual_date" if field == "maturity_date" else "identity_or_classification"}
    if _day(source.get("published_at")):
        record["published_at"] = source["published_at"]
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
                           and str(r.get("exchange") or "").upper() == market]
                if len(matches) != 1:
                    return {**result, "code":"source_identity_unavailable"}
                cik = str(int(matches[0]["cik"])).zfill(10)
                payload, url = get(SEC_SUBMISSIONS.format(cik=cik))
                tickers = [str(v).upper() for v in payload.get("tickers", [])]
                exchanges = [str(v).upper() for v in payload.get("exchanges", [])]
                if str(int(payload.get("cik"))) != str(int(cik)) or symbol not in tickers or market not in exchanges or not payload.get("name"):
                    return {**result, "code":"source_identity_unavailable"}
                source = {"url":url, "retrieved_at":now(), "source_kind":"regulatory", "text":json.dumps({
                    k:payload.get(k) for k in ("cik","name","tickers","exchanges","addresses")})}
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
    host = (urlsplit(str(source.get("url") or "")).hostname or "").lower().removeprefix("www.")
    domains = {str(v).lower().removeprefix("www.") for v in candidate.get("verified_issuer_domains", [])}
    if host not in domains and not (host == "sec.gov" or host.endswith(".sec.gov") or host == "treasurydirect.gov" or host.endswith(".treasurydirect.gov")):
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
                if (str(int(payload.get("cik"))) != cik
                        or str(candidate.get("symbol") or "").upper() not in [str(v).upper() for v in payload.get("tickers",[])]
                        or str(candidate.get("stock_market") or "").upper() not in [str(v).upper() for v in payload.get("exchanges",[])]) or not payload.get("name"):
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
    observed = source.get("observation_date")
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
    for statement, quote, explicitly_dated, current in _current_allocation_statements(text, observed):
        if re.search(r"\b(?:not|except|excluding|other than|no longer)\b", statement, re.I):
            if re.search(r"\bdenominated\b", statement, re.I):
                currency_conflict = True
            if re.search(r"\b(?:located|based|domiciled)\b", statement, re.I):
                country_conflict = True
        if not current:
            continue
        currency = re.fullmatch(r"All (?:of )?our (?:investments|loans|portfolio investments) (are|were) denominated in (.+)", statement, re.I)
        if currency and (currency[1].lower() == "are" or explicitly_dated):
            if re.fullmatch(r"(?:U\.S\. dollars|US dollars|United States dollars|USD)", currency[2], re.I):
                currency_quotes.append(quote)
            else:
                currency_conflict = True
        country = re.fullmatch(r"(?:All (?:of )?our (?:investments|portfolio companies|loans)|100(?:\.0+)?% of our (?:investments|portfolio)) (are|is|were|was) (?:located|based|domiciled) in (.+)", statement, re.I)
        if country and (country[1].lower() in {"are", "is"} or explicitly_dated):
            if re.fullmatch(r"(?:the )?(?:United States|U\.S\.?)", country[2], re.I):
                country_quotes.append(quote)
            else:
                country_conflict = True
    if currency_quotes and not currency_conflict:
        records.append(_record("currency_exposures", {"USD":1},
            {**public, "evidence_quote":currency_quotes[0]}, as_of=observed, basis="reported_investment_currency"))
    if country_quotes and not country_conflict:
        source_quote = {**public,"evidence_quote":country_quotes[0]}
        records += [_record(field,value,source_quote,as_of=observed,basis="reported_allocation") for field,value in (
            ("country_code","US"),("country_basis","economic_exposure"),("country_currency","USD"))]
    return records
