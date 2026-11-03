"""Observable heatmap values, account scope, accessible detail and asynchronous recovery."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    script = r'''
const assert=require('node:assert/strict');
const state={language:'en'};
const t=value=>value;
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const fmt=(value,digits=2)=>Number(value).toFixed(digits);
const money=(value,currency,digits=0)=>`${currency==='ILS'?'₪':currency} ${Number(value).toFixed(digits)}`;
const currencyDisplayLabel=value=>value;
const accountLabel=row=>row.account_id||row.id;
const formatDate=value=>value.split('-').reverse().join('/');
const nodes={},listeners={},pending=[];
const document={activeElement:null,addEventListener(type,fn){(listeners[type]||=[]).push(fn);}};
const target={_html:'',get innerHTML(){return this._html},set innerHTML(value){this._html=value;for(const id of ['heatmapAccount','heatmapLayout','heatmapSelection'])delete nodes[id];for(const m of value.matchAll(/<(select|section)\b[^>]*\bid="([^"]*)"[^>]*>/g)){const id=m[2];nodes[id]={id,innerHTML:'',focus(){document.activeElement=this;}};}},setAttribute(key,value){this[key]=value;},querySelectorAll(){return [];}};
nodes.heatmapContent=target;
const $=id=>nodes[id];
const api=(path,options={})=>new Promise((resolve,reject)=>pending.push({path,options,resolve,reject}));
const row=(account_id,quantity,gross_value_ils)=>({account_id,quantity,gross_value_ils,value_ils:gross_value_ils===null?null:Math.sign(quantity)*gross_value_ils});
const a={id:'A|NASDAQ|USD',symbol:'AAA',name:'Alpha <company>',stock_market:'NASDAQ',currency:'USD',asset_class:'EQUITY',quantity:5,gross_quantity:15,gross_value_ils:6000,value_ils:2000,price:110,price_date:'2026-11-03',previous_price:100,previous_date:'2026-11-02',change_percent:10,basis:'close',source:'local',status:'ok',issues:[],accounts:[row('one',10,4000),row('two',-5,2000)]};
const b={...a,id:'B|TASE|ILS',symbol:'BBB',name:'Beta',stock_market:'TASE',currency:'ILS',asset_class:'ETF',quantity:20,gross_quantity:20,gross_value_ils:4000,value_ils:4000,change_percent:null,previous_price:null,previous_date:null,status:'partial',issues:['missing_previous_price'],accounts:[row('two',20,4000)]};
const c={...a,id:'C|NASDAQ|EUR',symbol:'CCC',currency:'EUR',asset_class:'MUTUAL_FUND',gross_value_ils:null,value_ils:null,change_percent:-1,status:'partial',issues:['missing_fx'],accounts:[row('one',10,null)]};
const data={accounts:[{id:'one',account_id:'First'},{id:'two',account_id:'Second'},{id:'empty',account_id:'Empty'}],assets:[a,b,c],as_of:'2026-11-03',excluded:[{symbol:'BOND',stock_market:'TASE',account_id:'two',reason:'unsupported_asset'}],fx:[{currency:'USD',rate:4,date:'2026-11-03',source:'Saved <rates>',status:'ok'}]};
function seed(){resetHeatmap();heatmapView.data=structuredClone(data);renderHeatmap();}
''' + (ROOT / 'web/heatmap-ui.js').read_text() + '\n' + body
    result = subprocess.run(['node'], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_combined_gross_values_account_filters_and_missing_coverage():
    run_ui(r'''
seed();let html=target.innerHTML;
assert.ok(html.includes('₪ 10000.00'));
assert.ok(html.includes('Long and short exposure'));
assert.ok(html.includes('Holdings without a tile'));
assert.ok(html.includes('The total covers priced holdings only'));
assert.ok(html.includes('No change / unavailable'));
assert.ok(html.includes('data-heatmap-asset="0"'));
assert.ok(html.includes('All listings and values'));
assert.ok(!html.includes('NaN'));assert.ok(!html.includes('undefined'));
assert.ok(!html.includes('Alpha <company>'));
const combined=heatmapScope();assert.equal(combined[0].quantity,5);assert.equal(combined[0].gross_quantity,15);assert.equal(combined[0].gross_value_ils,6000);
heatmapView.account_id='one';renderHeatmap();html=target.innerHTML;
assert.ok(html.includes('₪ 4000.00'));assert.equal(heatmapScope().length,2);assert.equal(heatmapScope()[0].quantity,10);assert.equal(heatmapExcluded().length,0);
heatmapView.account_id='two';renderHeatmap();assert.equal(heatmapScope()[0].quantity,-5);assert.equal(heatmapScope()[0].gross_value_ils,2000);assert.ok(target.innerHTML.includes('Short exposure'));assert.ok(target.innerHTML.includes('₪ 6000.00'));
heatmapView.account_id='empty';renderHeatmap();assert.ok(target.innerHTML.includes('No stock or fund holdings'));assert.ok(!target.innerHTML.includes('heatmap-canvas'));
''')


def test_click_details_preserves_identity_dates_signed_breakdown_and_escapes():
    run_ui(r'''
seed();heatmapView.selected={id:a.id,account_id:''};renderHeatmapSelection();let html=nodes.heatmapSelection.innerHTML;
assert.ok(html.includes('03/11/2026'));assert.ok(html.includes('02/11/2026'));assert.ok(html.includes('+10.00%'));assert.ok(html.includes('60.00%'));assert.ok(html.includes('Alpha &lt;company&gt;'));assert.ok(!html.includes('Alpha <company>'));assert.ok(html.includes('-5.0000'));assert.ok(html.includes('First'));assert.ok(html.includes('Second'));assert.ok(html.includes('₪ 6000.00'));assert.ok(html.includes('₪ 2000.00'));
heatmapView.selected={id:a.id,account_id:'two'};renderHeatmapSelection();html=nodes.heatmapSelection.innerHTML;assert.ok(html.includes('33.33%'));assert.ok(!html.includes('First'));assert.ok(html.includes('Short exposure'));
heatmapView.selected={id:b.id,account_id:''};renderHeatmapSelection();html=nodes.heatmapSelection.innerHTML;assert.ok(html.includes('A previous price observation is missing.'));assert.ok(html.includes('Unavailable'));assert.ok(!html.includes('>0.00%</bdi>'));
''')


def test_treemap_area_represents_gross_values_without_small_position_inflation():
    run_ui(r'''
const inputs=[{id:'a',gross_value_ils:6000},{id:'b',gross_value_ils:3999},{id:'c',gross_value_ils:1}];
const rectangles=heatmapRectangles(inputs);assert.equal(rectangles.length,3);
for(const rect of rectangles){const actual=rect.width*rect.height/10000;assert.ok(Math.abs(actual-rect.asset.gross_value_ils/10000)<1e-12);for(const key of ['x','y','width','height'])assert.ok(Number.isFinite(rect[key]));assert.ok(rect.x>=0&&rect.y>=0&&rect.x+rect.width<=100.000001&&rect.y+rect.height<=100.000001);}
assert.equal(heatmapRectangles([{id:'zero',gross_value_ils:0}]).length,0);
const extreme=heatmapRectangles([{id:'x',gross_value_ils:1e308},{id:'y',gross_value_ils:1e308}]);assert.equal(extreme.length,2);for(const r of extreme)assert.ok(Number.isFinite(r.width*r.height));
seed();heatmapView.layout='accounts';renderHeatmap();assert.ok(target.innerHTML.includes('Each account panel is scaled independently'));assert.ok(target.innerHTML.includes('data-heatmap-account="two"'));assert.ok(target.innerHTML.includes('No positions'));assert.ok(target.innerHTML.includes('role="group"'));assert.ok(target.innerHTML.includes('aria-label='));
''')


def test_switch_languages_translates_operational_copy_and_sanitizes_reasons():
    run_ui(r'''
seed();
for(const language of ['en','he','en']){
 state.language=language;heatmapView.selected={id:a.id,account_id:''};renderHeatmap();const html=target.innerHTML+nodes.heatmapSelection.innerHTML;
 if(language==='he'){assert.ok(html.includes('מפת חום'));assert.ok(html.includes('חשיפה ברוטו'));assert.ok(!/Gross value|Short exposure|No change|Latest price|Source|Stock Heatmap|Fund|By account|All accounts|priced listings/.test(html));}
 else{assert.ok(html.includes('Gross value'));assert.ok(!/[א-ת]/.test(html));}
 assert.ok(html.includes('Saved &lt;rates&gt;'));assert.ok(html.includes('03/11/2026'));
}
for(const code of ['missing_price','stale_price','missing_previous_price','sparse_prices','missing_fx','stale_fx','invalid_position','classification_conflict','invalid_value','unsupported_asset','provider-secret']){state.language='he';const label=heatmapText(heatmapReason(code));assert.ok(/[א-ת]/.test(label));assert.ok(!label.includes(code));}
''')


def test_loading_failure_keeps_scoped_result_retry_and_logout_reject_late_result():
    run_ui(r'''
(async()=>{
 seed();heatmapView.account_id='two';
 const first=loadHeatmap();assert.equal(target['aria-busy'],'true');assert.equal(pending[0].path,'/api/portfolio/heatmap');assert.ok(target.innerHTML.includes('₪ 6000.00'));
 const second=loadHeatmap();pending[1].resolve({...data,as_of:'2026-11-02'});await second;pending[0].resolve({...data,as_of:'2026-10-01'});await first;assert.equal(heatmapView.data.as_of,'2026-11-02');assert.equal(heatmapView.account_id,'two');
 const failed=loadHeatmap();pending[2].reject(new Error('PRIVATE CREDENTIAL'));await failed;assert.ok(target.innerHTML.includes('Previous saved result shown'));assert.ok(target.innerHTML.includes('Reload saved data'));assert.ok(!target.innerHTML.includes('PRIVATE'));
 const retry=loadHeatmap();pending[3].resolve(data);await retry;assert.equal(heatmapView.error,false);assert.equal(target['aria-busy'],'false');
 const beforeLogout=loadHeatmap();resetHeatmap();pending[4].resolve(data);await beforeLogout;assert.equal(heatmapView.data,null);assert.equal(heatmapView.account_id,'');assert.ok(!target.innerHTML.includes('AAA'));
})();
''')


def test_scope_and_layout_events_select_tiles_without_writing_or_network_reload():
    run_ui(r'''
seed();for(const listener of listeners.change)listener({target:{id:'heatmapAccount',value:'two'}});assert.equal(heatmapView.account_id,'two');assert.equal(document.activeElement.id,'heatmapAccount');assert.equal(pending.length,0);
for(const listener of listeners.change)listener({target:{id:'heatmapLayout',value:'accounts'}});assert.equal(heatmapView.layout,'accounts');assert.equal(document.activeElement.id,'heatmapLayout');
const button={dataset:{heatmapAsset:'0',heatmapAccount:'two'}};for(const listener of listeners.click)listener({target:{closest:selector=>selector==='[data-heatmap-asset]'?button:null}});assert.deepEqual(heatmapView.selected,{id:a.id,account_id:'two'});assert.ok(nodes.heatmapSelection.innerHTML.includes('Short exposure'));assert.equal(pending.length,0);
''')


def test_independent_account_assets_override_unusable_combined_listing():
    run_ui(r'''
seed();heatmapView.data.assets[0].gross_value_ils=null;heatmapView.data.assets[0].accounts[0].gross_value_ils=null;heatmapView.data.assets[0].issues=['classification_conflict'];heatmapView.data.account_assets={one:[{...structuredClone(a),accounts:[row('one',10,4000)],quantity:10,gross_quantity:10,gross_value_ils:4000,value_ils:4000,issues:[]}],two:[]};
heatmapView.account_id='one';renderHeatmap();assert.equal(heatmapScope().length,1);assert.equal(heatmapScope()[0].gross_value_ils,4000);assert.ok(target.innerHTML.includes('₪ 4000.00'));assert.ok(!target.innerHTML.includes('Holdings without a tile'));
heatmapView.selected={id:a.id,account_id:'one'};renderHeatmapSelection();assert.ok(!nodes.heatmapSelection.innerHTML.includes('classifications conflict'));
state.language='he';assert.equal(heatmapFxSource('external_import_market_data'),'נתוני שוק ממקור מיובא');assert.equal(heatmapFxSource('bank_of_israel_fx'),'בנק ישראל');assert.equal(heatmapFxSource('My exact citation'),'My exact citation');
''')


def test_dashboard_cell_keeps_account_view_selection_and_recovers_interaction():
    run_ui(r'''
seed();heatmapView.account_id='two';heatmapView.layout='accounts';heatmapView.selected={id:a.id,account_id:'two'};
let captures=0,restores=0;globalThis.preserveRenderedInteraction=node=>{assert.equal(node,target);captures++;return()=>restores++;};
for(const language of ['en','he']){state.language=language;const card=renderDashboardHeatmap();assert.ok(card.includes('class="chart-card portfolio-heatmap-card"'));assert.ok(card.includes('id="heatmapContent"'));assert.ok(!card.includes('role="dialog"'));assert.ok(!card.includes('data-modal='));assert.ok(card.includes(language==='he'?'מפת חום של מניות התיק':'Portfolio stocks heatmap'));
 renderHeatmap();assert.equal(heatmapView.account_id,'two');assert.equal(heatmapView.layout,'accounts');assert.deepEqual(heatmapView.selected,{id:a.id,account_id:'two'});assert.ok(nodes.heatmapSelection.innerHTML.includes(language==='he'?'חשיפה בחסר':'Short exposure'));assert.ok(target.innerHTML.includes('<details id="heatmapMethod"'));assert.ok(!target.innerHTML.includes('<details id="heatmapMethod" class="heatmap-method" open'));}
assert.equal(captures,2);assert.equal(restores,2);
''')
