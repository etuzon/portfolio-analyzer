"""Regression spans from actual rendered public pages retrieved 08/11/2026."""
from copy import deepcopy

import pytest

from app.security_source_context import context_records
from app.security_web_research import validate_proposals

CANDIDATE = {"security_key": "1101534|TASE|ILS", "symbol": "1101534", "stock_market": "TASE",
             "asset_class": "EQUITY", "currency": "ILS", "missing_fields": ["profile"],
             "needs_name": True, "needs_industry": True}
THEMARKER = """## סלקום

למידע נוסף על המניה

סלקום מפעילה רשת טלפונים סלולרית ומספקת עי נטוויזן שירותי אינטרנט וטלפוניה

שער 2,901.00

% שינוי 1.86

שינוי באג׳52.97

נכון ל:06.11.2026, 11:45

סוג נייר:מניה רגילה מספר נייר:1101534

*   [סלקום (ניו יורק)](https://finance.themarker.com/stock/126.1.CEL)
"""
GLOBES = """# מניית סלקום

CELLCOM

מניה 1101534 תל-אביב NIS סוף יום

שער
2,901

### תיאור חברה

**סלקום ישראל בע"מ**

**ענף:**[מסחר ושירותים מניות והמירים](https://www.globes.co.il/portal/quotes/commerce-services)

**תת-ענף:**[חברות תקשורת ומדיה](https://www.globes.co.il/portal/quotes/commerce-services?industrysectorid=197)

### חדשות סלקום
"""


def source(kind):
    return {"url": "https://finance.themarker.com/stock/1101534" if kind == "name" else
            "https://www.globes.co.il/portal/instrument.aspx?quote=TASE:1101534",
            "text": THEMARKER if kind == "name" else GLOBES, "structured_data": [],
            "source_id": "rendered", "retrieved_at": "2026-11-08T12:00:00+00:00"}


@pytest.mark.parametrize("asset_class", ["EQUITY", "RSU"])
@pytest.mark.parametrize("kind,value", [("name", "סלקום"), ("industry", "חברות תקשורת ומדיה")])
def test_actual_rendered_primary_profile_reaches_final_proposal_validation(kind, value, asset_class):
    candidate = {**CANDIDATE, "asset_class": asset_class}
    src = source(kind)
    record, = context_records(src, candidate)
    assert record["kind"] == "profile" and record["field"] == kind and record["value"] == value
    proposal = {"records": [{"security_key": CANDIDATE["security_key"], "source_id": src["source_id"], "record_id": record["record_id"]}]}
    result = validate_proposals(proposal, {CANDIDATE["security_key"]: candidate}, {CANDIDATE["security_key"]: [src]})
    assert not result[CANDIDATE["security_key"]]["rejected"]
    assert result[CANDIDATE["security_key"]]["profiles"][0]["value"] == value
    assert result[CANDIDATE["security_key"]]["observations"] == []


@pytest.mark.parametrize("kind", ["name", "industry"])
@pytest.mark.parametrize("mutation", ["wrong_url", "wrong_card", "wrong_market", "wrong_asset", "related_only", "duplicate_card"])
def test_profiles_cannot_borrow_identity_or_fields(kind, mutation):
    src, candidate = source(kind), deepcopy(CANDIDATE)
    if mutation == "wrong_url":
        src["url"] = src["url"].replace("1101534", "1234567")
    elif mutation == "wrong_card":
        src["text"] = src["text"].replace("1101534", "1234567")
    elif mutation == "wrong_market":
        candidate["stock_market"] = "NASDAQ"
    elif mutation == "wrong_asset":
        candidate["asset_class"] = "BOND"
    elif mutation == "duplicate_card":
        src["text"] += src["text"]
    else:
        if kind == "name":
            src["text"] = src["text"].replace("סוג נייר:", "* [related](https://example.com)\nסוג נייר:")
        else:
            src["text"] = src["text"].replace("**תת-ענף:", "### ניירות קשורים\n**תת-ענף:")
    assert context_records(src, candidate) == []


@pytest.mark.parametrize('kind', ['name', 'industry'])
@pytest.mark.parametrize('conflict', ['מספר נייר:9999999', 'ISIN IL0011111111'])
def test_conflicting_primary_identity_is_rejected(kind, conflict):
    src = source(kind)
    candidate = {**CANDIDATE, 'secondary_symbol': 'IL0011015349'}
    anchor = 'סוג נייר:מניה רגילה מספר נייר:1101534' if kind == 'name' else 'מניה 1101534 תל-אביב NIS סוף יום'
    src['text'] = src['text'].replace(anchor, anchor + '\n' + conflict)
    assert context_records(src, candidate) == []
