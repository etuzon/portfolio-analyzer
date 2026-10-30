"""Display exchange evidence without changing a holding's provider-routing key."""
from pathlib import Path
import re
import subprocess


def test_provider_exchange_is_displayed_without_guessing_or_changing_routing():
    source = (Path(__file__).resolve().parents[1] / "web/app.js").read_text()
    functions = []
    for name in ("isProviderName", "holdingMarketKey", "stockMarketDisplay"):
        start = re.search(rf"^function {name}\(", source, re.M).start()
        end = re.search(r"^}", source[start:], re.M).end()
        functions.append(source[start:start + end])
    script = "\n".join(functions) + """
const assert=require('node:assert/strict');
const cleanSourceLabel=value=>String(value).trim();
const optionLabel=value=>value;
const holding={symbol:'FDUS',stock_market:'YAHOO',platform:'YAHOO',data_source:'LOCAL'};
const before=JSON.stringify(holding);
assert.equal(stockMarketDisplay(holding,holdingMarketKey(holding),'Nasdaq'),'NASDAQ');
assert.equal(stockMarketDisplay({...holding,stock_market:'TASE'},'YAHOO','Nasdaq'),'TASE');
assert.equal(stockMarketDisplay(holding,'NYSE','yahoo'),'NYSE');
assert.equal(stockMarketDisplay(holding,'YAHOO',''),'Not available');
assert.equal(stockMarketDisplay({},'',''),'Not available');
assert.equal(holdingMarketKey(holding),'YAHOO');
assert.equal(JSON.stringify(holding),before);
"""
    result = subprocess.run(["node"], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
