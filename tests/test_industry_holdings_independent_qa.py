"""Industry display aggregation preserves security identity and raw risk rows."""
import subprocess
from test_shared_cash_risk_qa import app_functions


def test_industry_aggregates_cross_account_security_but_keeps_listings_and_derivatives():
    source=app_functions('industryHoldingsBySecurity','industryHoldingHtml','renderIndustrySplit')
    script=source+r'''
const assert=require('node:assert/strict');
const state={language:'en',baseCurrency:'USD',localAccounts:[{id:'a',account_id:'First'},{id:'b',account_id:'Second'}],riskSnapshot:{total:{score:20}}};
const optionLabel=value=>value;
const currencyDisplayLabel=value=>value;
const formatDate=value=>value;
const industryLabel=()=> 'Technology';
const industryDisplayLabel=value=>value;
const holdingMarketKey=h=>h.stock_market;
const normalizedField=(item,field)=>item.holding[field]*(item.holding.currency==='EUR'?4:1);
const sum=values=>values.reduce((a,b)=>a+b,0);
const money=(value,currency)=>`${value} ${currency}`;
const fmt=value=>String(value);
const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const portfolioAccounts=()=>[];
const accountRiskCashValue=()=>0;
const accountHorizonYears=()=>null;
const riskBadge=()=>'';
const colorAt=()=> '#abc';
let riskRows;
const riskScoreForItems=items=>{riskRows=items;return {score:20};};
const stock=(account_id,value,extra={})=>({holding:{symbol:'SAR',name:'Same security',stock_market:'NASDAQ',currency:'USD',asset_class:'EQUITY',quantity:value/100,account_id,market_value:value,...extra}});
const rows=[stock('a',600),stock('b',-400),stock('a',200,{stock_market:'NYSE'}),stock('a',300,{currency:'EUR'}),stock('a',100,{asset_class:'OPTION',option_type:'CALL',strike_price:100}),stock('a',100,{asset_class:'OPTION',option_type:'CALL',strike_price:200})];
const original=JSON.stringify(rows);
const groups=industryHoldingsBySecurity(rows);
assert.equal(groups.length,5);
const aggregate=groups.find(row=>row.accounts.length===2);
assert.equal(aggregate.value,1000);
assert.deepEqual(aggregate.accounts,[{label:'First',quantity:6,value:600},{label:'Second',quantity:-4,value:400}]);
const title=industryHoldingHtml(aggregate);
assert.ok(title.includes('Gross value: 1000 USD'));
assert.ok(title.includes('Account: First · Quantity: 6 · Gross value: 600 USD'));
assert.ok(title.includes('Account: Second · Quantity: -4 · Gross value: 400 USD'));
assert.ok(title.includes('\n'));
const rendered=renderIndustrySplit(rows);
assert.equal((rendered.match(/data-classify-industry-symbol="SAR"/g)||[]).length,5);
assert.ok(rendered.includes('2600 USD'));
assert.equal(riskRows.length,6);
assert.deepEqual(riskRows,rows);
assert.ok(rendered.indexOf('class="industry-holdings"')<rendered.indexOf('class="industry-split-track"'));
assert.equal(JSON.stringify(rows),original);
'''
    result=subprocess.run(['node'],input=script,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
