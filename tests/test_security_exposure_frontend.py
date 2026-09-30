import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fund_economic_fx_exposure_is_not_inferred_from_ils_trading_currency():
    source = (ROOT / "web/app.js").read_text()
    functions = []
    for name in ("assetRiskFactor", "economicCurrencyExposure", "currencyAllocationGroups"):
        start = source.index(f"function {name}(")
        end = source.find("\nfunction ", start + 1)
        functions.append(source[start:end if end != -1 else None])
    script = "\n".join(functions) + """
      const state = {baseCurrency: 'ILS'};
      const sum = (values) => values.reduce((total, value) => total + value, 0);
      const normalizedField = (item, field) => item.holding[field];
      const portfolioAccounts = () => [];
      const item = {holding: {asset_class: 'MUTUALFUND', currency: 'ILS', market_value: 1000},
        exposure_profile: {asset_focus: 'money_market', fx_basis: 'reported',
          currency_exposures: [{currency: 'USD', percent: 80}, {currency: 'ILS', percent: 10}],
          fx_policy_limit_percent: 120}};
      const unknown = {holding: {asset_class: 'MUTUALFUND', currency: 'ILS', market_value: 1000}};
      process.stdout.write(JSON.stringify({
        known: currencyAllocationGroups([item]),
        unknown: currencyAllocationGroups([unknown]),
        factor: assetRiskFactor(item)
      }));
    """
    completed = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    result = json.loads(completed.stdout)

    assert {row["label"]: row["value"] for row in result["known"]} == {
        "USD": 800, "ILS": 100, "Unknown": 100,
    }
    assert result["unknown"] == [{"label": "Unknown", "value": 1000}]
    assert result["factor"] == 0.12


def test_named_fx_exposure_is_a_full_allocation_when_no_detailed_split_is_entered():
    source = (ROOT / "web/app.js").read_text()
    start = source.index("function economicCurrencyExposure(")
    end = source.find("\nfunction ", start + 1)
    function = source[start:end if end != -1 else None]
    script = function + """
      const state = {baseCurrency: 'ILS'};
      const sum = (values) => values.reduce((total, value) => total + value, 0);
      const item = {holding: {asset_class: 'MUTUALFUND', currency: 'ILS'},
        exposure_profile: {asset_focus: 'money_market', fx_basis: 'estimated',
          fx_reference_currency: 'USD', currency_exposures: []}};
      process.stdout.write(JSON.stringify(economicCurrencyExposure(item)));
    """
    completed = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    assert json.loads(completed.stdout) == {
        "allocations": [{"currency": "USD", "percent": 100}], "unknownPercent": 0,
    }
