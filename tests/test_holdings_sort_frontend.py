"""Holdings ordering uses raw values, filtered rows, and accessible local controls."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_node(script):
    result = subprocess.run(['node'], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_stable_missing_last_numeric_locale_and_currency_aware_ordering():
    run_node(r'''
const assert = require('node:assert/strict');
const sort = require('./web/holdings-sort.js');
const row = (symbol, value, currency='ILS') => ({holding:{symbol, market_value:value, currency},
  profit_trend:{state:'ok',percent_change:value}, dividend_trend:{state:'ok',percent_change:value}});
const rows = [row('Ten',10),row('Two',2),row('Negative',-4),row('Missing',null),row('Equal',2),row('Zero',0),row('FX',2,'USD'),row('No FX',1,'JPY')];
const original = JSON.stringify(rows);
const context = {language:'en', maPeriod:'30', account:h=>h.account, status:i=>i.status,
  risk:i=>i.risk, amount:(value,currency)=>currency==='ILS'?value:currency==='USD'?value*3.5:null};
const symbols = (key,direction='asc',items=rows) => sort.sortRows(items,{key,direction},context).map(i=>i.holding.symbol);
assert.deepEqual(symbols('value'),['Negative','Zero','Two','Equal','FX','Ten','Missing','No FX']);
assert.deepEqual(symbols('value','desc'),['Ten','FX','Two','Equal','Zero','Negative','Missing','No FX']);
assert.equal(JSON.stringify(rows),original);
assert.notEqual(sort.sortRows(rows,{},context),rows);
assert.equal(sort.sortRows(rows,{key:'value',direction:'asc'},context)[2],rows[1]);
for(const value of [null,undefined,NaN,Infinity,-Infinity,'100',false]) {
 const unknown=row('Unknown',value);
 assert.equal(sort.valueFor(unknown,'value',context),null);
}
assert.deepEqual(symbols('security','asc',[row('Sec10',1),row('sec2',1)]),['sec2','Sec10']);
context.language='he';
assert.deepEqual(symbols('security','asc',[row('תמר',1),row('אביב',1),row('ברק',1)]),['אביב','ברק','תמר']);
for(const key of ['income','dividend']) {
 assert.deepEqual(symbols(key,'asc',[row('Growth',10),row('Loss',-30),row('Flat',0)]),['Loss','Flat','Growth']);
 for(const state of ['missing','pending','error']) {
   const item=row('Unavailable',900); item[key==='income'?'profit_trend':'dividend_trend'].state=state;
   assert.equal(sort.valueFor(item,key,context),null);
 }
}
const item = row('Mapped',100,'USD');
item.price_ranges={'1y':{state:'partial',high:10,min:2,low:999}};
item.support_resistance={'1y':{state:'ok',support:{price:4},resistance:{price:9}}};
item.moving_averages={'30':{state:'ok',value:6},'90':{state:'ok',value:8}};
item.risk=0; item.holding.unrealized_profit=-3;
for(const [key,expected] of [['high',35],['low',7],['support',14],['resistance',31.5],['ma',21],['risk',0],['profit',-10.5]])
 assert.equal(sort.valueFor(item,key,context),expected,key);
context.maPeriod='90'; assert.equal(sort.valueFor(item,'ma',context),28);
item.support_resistance['1y'].state='missing';
for(const key of ['support','resistance','ma']) assert.equal(sort.valueFor(item,key,context),null);
item.price_ranges['1y'].state='pending';
for(const key of ['high','low']) assert.equal(sort.valueFor(item,key,context),null);
''')


def test_header_clicks_toggle_filtered_rows_and_retain_order_on_background_redraw():
    source = (ROOT/'web/app.js').read_text()
    controller = source[source.index('let holdingsTableSort ='):source.index('function renderRows(items)')]
    run_node(r'''
const assert = require('node:assert/strict');
const HoldingsSort = require('./web/holdings-sort.js');
const state = {language:'en',baseCurrency:'ILS',tableMaPeriod:'30'};
const t=value=>state.language==='he'?`עברית ${value}`:value;
const cleanSourceLabel=value=>value;
const reportAmount=(value,currency)=>currency==='ILS'?value:null;
const dataGapDetails=()=>[];
const headings = [];
const buttons = ['security','risk','value','profit','high','low','income','dividend','support','resistance','ma','status'].map(key=>{
 const heading={attrs:{},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];}};
 headings.push(heading);
 return {dataset:{holdingsSort:key,sortLabel:key},attrs:{},arrow:{},
  setAttribute(k,v){this.attrs[k]=v;},querySelector(){return this.arrow;},closest(selector){return selector==='th'?heading:this;}};
});
let click;
const mobileEvents={};
const mobileSort={value:'',addEventListener(type,callback){mobileEvents[type]=callback;}};
const mobileDirection={attrs:{},addEventListener(type,callback){mobileEvents.direction=callback;},setAttribute(k,v){this.attrs[k]=v;}};
const document={querySelector(){return {addEventListener(type,callback){assert.equal(type,'click');click=callback;}};},
 getElementById(id){return id==='holdingsMobileSort'?mobileSort:id==='holdingsMobileSortDirection'?mobileDirection:null;},
 querySelectorAll(selector){return selector.includes('th[')?headings:buttons;}};
let displayed;
function renderRows(items) {holdingsTableRows=[...items];displayed=sortHoldingsRows(items);updateHoldingsSortHeaders();}
''' + controller + r'''
const a={holding:{symbol:'A',market_value:10,currency:'ILS'}};
const b={holding:{symbol:'B',market_value:2,currency:'ILS'}};
const filtered=[b,a];
renderRows(filtered);
const value=buttons.find(b=>b.dataset.holdingsSort==='value');
const activate=button=>click({target:{closest(){return button;}}});
activate(value); assert.deepEqual(displayed,[a,b]);
assert.equal(mobileSort.value,'value');assert.equal(mobileDirection.disabled,false);
assert.equal(value.arrow.textContent,'↓');assert.equal(value.attrs['aria-pressed'],'true');
assert.equal(headings[2].attrs['aria-sort'],'descending');
assert.match(value.attrs['aria-label'],/Ascending/);
activate(value); assert.deepEqual(displayed,[b,a]);assert.equal(value.arrow.textContent,'↑');
renderRows([a,b]); assert.deepEqual(displayed,[b,a]); // finished background snapshot retains selection
assert.deepEqual(filtered,[b,a]);
const security=buttons[0];activate(security);assert.deepEqual(displayed,[a,b]);
assert.equal(headings[2].attrs['aria-sort'],undefined);
assert.equal(headings[0].attrs['aria-sort'],'ascending');
assert.equal(value.attrs['aria-pressed'],'false');
state.language='he';updateHoldingsSortHeaders();assert.match(security.attrs['aria-label'],/עברית/);
mobileEvents.change({target:{value:'value'}});assert.deepEqual(displayed,[a,b]);
assert.match(mobileDirection.textContent,/Descending/);
mobileEvents.direction();assert.deepEqual(displayed,[b,a]);
assert.equal(headings[2].attrs['aria-sort'],'ascending');
mobileEvents.change({target:{value:''}});assert.deepEqual(displayed,[a,b]);
assert.equal(mobileDirection.disabled,true);assert.equal(headings[2].attrs['aria-sort'],undefined);
resetHoldingsSort();assert.equal(headings[0].attrs['aria-sort'],undefined);
assert.equal(security.arrow.textContent,'↕');assert.deepEqual(holdingsTableRows,[]);
''')
    render_body = source[source.index('function renderRows(items)'):source.index('function chartPath(')]
    assert 'holdingsTableRows = [...items]' in render_body
    assert 'items = sortHoldingsRows(items)' in render_body
    assert 'preserveRenderedInteraction' in render_body
    assert 'bindCompanyLogoImages' in render_body
    assert not re.search(r'\b(?:api|fetch|loadPortfolio)\(', controller)


def test_every_holdings_column_has_keyboard_sort_controls_and_help_documents_units():
    html = (ROOT/'web/index.html').read_text()
    table = html[html.index('<table class="holdings-table">'):html.index('<tbody id="rows">')]
    headings = re.findall(r'<th\b.*?</th>', table, re.S)
    assert len(headings) == 9
    for heading in headings:
        assert 'scope="col"' in heading
        assert 'data-holdings-sort-column=' in heading
        assert 'data-holdings-sort=' in heading
        for button in re.findall(r'<button\b[^>]+>', heading):
            assert 'type="button"' in button
    assert html.index('/holdings-sort.js') < html.index('/app.js')
    assert '/holdings-sort.css' in html
    assert 'Missing values or required FX stay last in either direction.' in html
    assert 'Keyboard users can focus a sort button and press Enter or Space.' in html
    assert 'On small screens, use Sort by and the direction button above the holding cards; Original order clears sorting.' in html
    mobile = html[html.index('<div class="holdings-mobile-sort">'):html.index('<div class="table-wrap holdings-table-wrap"')]
    assert 'for="holdingsMobileSort"' in mobile
    assert 'id="holdingsMobileSortDirection"' in mobile
    keys = set(re.findall(r'data-holdings-sort="([^"]+)"', table))
    assert keys == set(re.findall(r'<option value="([^"]+)">', mobile))
    css = (ROOT/'web/holdings-sort.css').read_text()
    assert '.holdings-mobile-sort { display: none; }' in css
    assert '@media (max-width: 760px)' in css
