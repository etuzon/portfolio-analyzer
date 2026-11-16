"""Public ISO 4217 country-reference evidence, separate from company FX exposure.

Fetching is explicit and budgeted by ResearchSession. Scoring never calls this
adapter. The shared cache contains only a public source document and its dates.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import re
from threading import RLock
import time
import xml.etree.ElementTree as ET

import httpx

from .sovereign_ratings import normalize_country

SIX_CURRENCY_URL = 'https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml'
MAX_DOCUMENT_BYTES = 1_000_000
# Operational refresh interval, not an expiry for currency facts or market data.
REFERENCE_REFRESH_SECONDS = 24 * 60 * 60


def _country(value):
    if not isinstance(value, str):
        return None
    return normalize_country(re.sub(r'\s*\(THE\)\s*$', '', value.strip(), flags=re.I))


def _published(text):
    if (not isinstance(text, str) or len(text.encode('utf-8')) > MAX_DOCUMENT_BYTES
            or re.search(r'<!DOCTYPE|<!ENTITY', text, re.I)):
        raise ValueError('invalid_currency_reference')
    root = ET.fromstring(text)
    if root.tag != 'ISO_4217' or root.find('CcyTbl') is None:
        raise ValueError('invalid_currency_reference')
    published = date.fromisoformat(root.attrib.get('Pblshd', ''))
    if published > datetime.now(timezone.utc).date():
        raise ValueError('future_currency_reference')
    return root, published.isoformat()


class CountryCurrencyReference:
    def __init__(self, *, transport=None, clock=time.monotonic, refresh_seconds=REFERENCE_REFRESH_SECONDS):
        self.transport, self.clock, self.refresh_seconds = transport, clock, refresh_seconds
        self._lock, self._snapshot, self._checked = RLock(), None, None

    def fetch_document(self, url, settings):
        if url != SIX_CURRENCY_URL:
            from .security_research_tools import fetch_research_document
            return fetch_research_document(url, settings)
        with self._lock:
            stamp = self.clock()
            if self._snapshot and self._checked is not None and stamp - self._checked < self.refresh_seconds:
                return {**deepcopy(self._snapshot), 'reference_cache_status': 'cached'}
            try:
                with httpx.Client(timeout=20, follow_redirects=False, trust_env=False, transport=self.transport) as client:
                    with client.stream('GET', SIX_CURRENCY_URL, headers={'Accept': 'application/xml,text/xml'}) as response:
                        response.raise_for_status()
                        content = bytearray()
                        for chunk in response.iter_bytes():
                            content.extend(chunk)
                            if len(content) > MAX_DOCUMENT_BYTES:
                                raise ValueError('currency_reference_too_large')
                raw = content.decode('utf-8-sig')
                _, published = _published(raw)
                snapshot = {'url': SIX_CURRENCY_URL, 'text': raw,
                    'title': 'SIX ISO 4217 current currency list', 'reader': 'official_reference',
                    'retrieved_at': datetime.now(timezone.utc).isoformat(),
                    'reference_published_at': published, 'links': [], 'structured_data': []}
                self._snapshot, self._checked = snapshot, stamp
                return {**deepcopy(snapshot), 'reference_cache_status': 'fresh'}
            except (httpx.HTTPError, UnicodeError, ValueError, ET.ParseError):
                # Failure cannot refresh a saved source's retrieval/publication
                # date. No verified cache means the field stays unavailable.
                if self._snapshot:
                    return {**deepcopy(self._snapshot), 'reference_cache_status': 'refresh_failed_using_saved'}
                raise ValueError('currency_reference_unavailable') from None


def currency_reference_records(source, candidate):
    """Return only an unambiguous currency for the already resolved country."""
    if source.get('url') != SIX_CURRENCY_URL:
        return []
    code = normalize_country(candidate.get('country_code'))
    if not code:
        return []
    text = source.get('text') or ''
    try:
        root, published = _published(text)
        cutoff = str(candidate.get('as_of_date') or candidate.get('captured_at') or '')[:10]
        if cutoff and published > date.fromisoformat(cutoff).isoformat():
            return []
        retrieved = datetime.fromisoformat(str(source.get('retrieved_at') or '').replace('Z', '+00:00'))
        if retrieved.tzinfo is None or retrieved > datetime.now(timezone.utc):
            return []
    except (ValueError, TypeError, ET.ParseError):
        return []
    ordinary = {}
    malformed = False
    xml_rows = re.findall(r'<CcyNtry\b[^>]*>.*?</CcyNtry\s*>', text, re.S)
    if len(xml_rows) != len(root.findall('./CcyTbl/CcyNtry')):
        return []
    for element, quote in zip(root.findall('./CcyTbl/CcyNtry'), xml_rows):
        if _country(element.findtext('CtryNm')) != code:
            continue
        name = element.find('CcyNm')
        flag = name.attrib.get('IsFund', 'false').lower() if name is not None else ''
        if flag == 'true':
            continue
        currency, numeric = element.findtext('Ccy'), element.findtext('CcyNbr')
        tags = [child.tag for child in element]
        if (set(tags) - {'CtryNm','CcyNm','Ccy','CcyNbr','CcyMnrUnts'}
                or any(tags.count(tag) != 1 for tag in ('CtryNm','CcyNm','Ccy','CcyNbr'))
                or flag != 'false' or name is None or not (name.text or '').strip()
                or not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency)
                or not isinstance(numeric, str) or not re.fullmatch(r'[0-9]{3}', numeric)):
            malformed = True
            continue
        ordinary.setdefault(currency, (element, quote))
    if malformed or len(ordinary) != 1:
        return []
    currency, (element, quote) = next(iter(ordinary.items()))
    record = {'field': 'country_currency', 'value': currency, 'country_code': code,
        'basis': 'iso4217_country_reference', 'units': 'iso4217_currency_code',
        'source_url': SIX_CURRENCY_URL, 'source_kind': 'standards_public',
        'as_of': published, 'reference_published_at': published,
        'retrieved_at': source['retrieved_at'], 'verification_status': 'verified',
        'evidence_quote': quote, 'reference_country_name': element.findtext('CtryNm'),
        'reference_currency_name': element.findtext('CcyNm'),
        'reference_currency_number': element.findtext('CcyNbr'), 'reference_is_fund': False,
        'reference_cache_status': source.get('reference_cache_status', 'fresh')}
    record['record_id'] = 'risk-reference-' + hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()[:24]
    return [record]
