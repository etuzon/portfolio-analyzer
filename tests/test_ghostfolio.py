from app.ghostfolio import _asset_class, _first_json_value


def test_asset_class_preserves_bonds_from_subclass():
    assert _asset_class("FIXED_INCOME", "BOND") == "BOND"
    assert _asset_class("EQUITY", "STOCK") == "EQUITY"


def test_first_json_value_handles_ghostfolio_weighted_lists():
    assert _first_json_value([{"code": "US", "weight": 1}], "code") == "US"
    assert _first_json_value([{"name": "Financial Services", "weight": 1}], "name") == "Financial Services"
