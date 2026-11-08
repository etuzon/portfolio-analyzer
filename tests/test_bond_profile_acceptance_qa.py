"""Independent bond profile oracle from fetched 08/11/2026 public evidence.

The excerpts below are distilled source records, not live network acceptance.
No observation date or supported current valuation is established by them.
"""
from copy import deepcopy

import pytest

from app.security_web_research import validate_proposals


KEY = "121899CH9|MANUAL|USD"
CANDIDATE = {
    "security_key": KEY, "symbol": "121899CH9", "secondary_symbol": "US121899CH98",
    "stock_market": "MANUAL", "currency": "USD", "asset_class": "BOND",
    "missing_fields": ["profile"], "needs_name": True, "needs_industry": False,
}
PUBLIC_URL = "https://public.com/stocks/121899ch9-bond"
PUBLIC_TEXT = "## BRK 3.2% 01/01/2045 (121899CH9)"
TV_URL = "https://www.tradingview.com/symbols/FINRA-BRK3668477/"
TV_TEXT = """# Burlington Northern Railroad Co. 3.2% Jan 1, 2045
## Bond info
Issuer
Burlington Northern Railroad Co.
ISIN
US121899CH98
CUSIP
121899CH9"""


def verify(url, text, value, *, candidate=None, quote=None):
    candidate = candidate or CANDIDATE
    source = {"url": url, "text": text, "retrieved_at": "2026-11-08T17:40:00+00:00"}
    proposal = {"profiles": [{"security_key": KEY, "field": "name", "value": value,
                               "source_url": url, "evidence_quote": quote or text}]}
    return validate_proposals(proposal, {KEY: candidate}, {KEY: [source]})[KEY]


@pytest.mark.parametrize("url,text,value", [
    (PUBLIC_URL, PUBLIC_TEXT, "BRK 3.2% 01/01/2045"),
    (TV_URL, TV_TEXT, "Burlington Northern Railroad Co."),
])
def test_exact_bond_profile_does_not_require_registration_source_as_exchange(url, text, value):
    result = verify(url, text, value)
    assert len(result["profiles"]) == 1
    assert result["profiles"][0]["value"] == value
    assert result["observations"] == [], "A bond name never establishes a current price"


@pytest.mark.parametrize("text", [
    PUBLIC_TEXT.replace("121899CH9", "91282CKD2"),
    TV_TEXT.replace("121899CH9", "91282CKD2").replace("US121899CH98", "US91282CKD29"),
])
def test_different_bond_identity_cannot_supply_this_profile(text):
    value = "BRK 3.2% 01/01/2045" if text.startswith("## BRK") else "Burlington Northern Railroad Co."
    url = PUBLIC_URL if text.startswith("## BRK") else TV_URL
    assert verify(url, text, value)["profiles"] == []


def test_conflicting_explicit_isin_prevents_bond_profile_acceptance():
    assert verify(TV_URL, TV_TEXT.replace("US121899CH98", "US91282CKD29"),
                  "Burlington Northern Railroad Co.")["profiles"] == []


def test_recommended_bond_cusip_does_not_qualify_other_instruments_name():
    text = "## BRK 3.2% 01/01/2045 (91282CKD2)\n## Related instruments\n121899CH9"
    assert verify(PUBLIC_URL, text, "BRK 3.2% 01/01/2045", quote=text.splitlines()[0])["profiles"] == []


def test_nonbond_candidate_does_not_use_bond_identity_conventions():
    candidate = deepcopy(CANDIDATE)
    candidate.update(asset_class="EQUITY", stock_market="NASDAQ")
    assert verify(PUBLIC_URL, PUBLIC_TEXT, "BRK 3.2% 01/01/2045", candidate=candidate)["profiles"] == []
