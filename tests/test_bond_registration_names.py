"""Imported identifier labels remain missing names; custom labels stay authoritative."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from test_security_enrichment import metadata_application


@pytest.mark.parametrize("name,asset,expected", [
    (" US_121899CH9 ", "BOND", True),
    ("us_121899ch9", "BOND", True),
    ("US121899CH98", "BOND", True),
    ("US_121899CH9 retirement bond", "BOND", False),
    ("My Burlington bond", "BOND", False),
    ("US_121899CH9", "EQUITY", False),
])
def test_generated_bond_name_contract(monkeypatch, name, asset, expected):
    main, _ = metadata_application(monkeypatch)
    assert main._enrichment_name_missing({"symbol": "121899CH9", "secondary_symbol": "US121899CH98",
        "asset_class": asset, "name": name}) is expected
    assert not main._enrichment_name_missing({"symbol": "121899CH0", "asset_class": "BOND", "name": "US_121899CH0"})


@pytest.mark.parametrize("concurrent_rename", [False, True])
def test_verified_name_replaces_only_current_identifier_placeholder(monkeypatch, concurrent_rename):
    main, state = metadata_application(monkeypatch)
    state.holding.update(symbol="121899CH9", secondary_symbol="US121899CH98", name="US_121899CH9",
                         stock_market="MANUAL", asset_class="BOND", location="USA", quantity=1000)
    monkeypatch.setattr(main, "_bond_market_data", lambda *args, **kwargs: None)
    candidate = main._enrichment_candidates()["items"][0]
    assert candidate["needs_name"] is True and candidate["needs_industry"] is False
    assert "profile" in candidate["missing_fields"]
    before = deepcopy(state.holding)
    text = "CUSIP: 121899CH9 Company name: Burlington Northern Railroad"
    source = {"url": "https://bond-profile.example/121899CH9", "text": text,
              "retrieved_at": datetime.now(timezone.utc).isoformat()}
    proposal = {"profiles": [{"security_key": candidate["security_key"], "field": "name",
        "value": "Burlington Northern Railroad", "source_url": source["url"], "evidence_quote": text}]}
    real_validate = main.validate_proposals
    def validate(*args):
        result = real_validate(*args)
        if concurrent_rename:
            state.holding["name"] = "My chosen bond name"
        return result
    monkeypatch.setattr(main, "validate_proposals", validate)
    main._apply_enrichment_proposals(proposal, {candidate["security_key"]: [source]}, {candidate["security_key"]: candidate})
    assert state.holding["name"] == ("My chosen bond name" if concurrent_rename else "Burlington Northern Railroad")
    assert len(state.profiles) == (0 if concurrent_rename else 1)
    assert state.prices == []
    for field in ("symbol", "stock_market", "quantity", "currency", "asset_class"):
        assert state.holding[field] == before[field]
    if not concurrent_rename:
        assert all("profile" not in item["missing_fields"] for item in main._enrichment_candidates()["items"])
