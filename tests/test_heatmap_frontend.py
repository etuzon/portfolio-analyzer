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
const data={accounts:[{id:'one',type:'Investment',account_id:'First'},{id:'two',type:'Investment',account_id:'Second'},{id:'empty',type:'Investment',account_id:'Empty'}],assets:[a,b,c],as_of:'2026-11-03',excluded:[{symbol:'OPTION',stock_market:'TASE',account_id:'two',reason:'unsupported_asset'}],fx:[{currency:'USD',rate:4,date:'2026-11-03',source:'Saved <rates>',status:'ok'}]};
function seed(){resetHeatmap();heatmapView.data=structuredClone(data);renderHeatmap();}
''' + (ROOT / 'web/heatmap-ui.js').read_text() + '\n' + body
    result = subprocess.run(['node'], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_combined_gross_values_account_filters_and_missing_coverage():
    run_ui(r'''
seed();let html=target.innerHTML;
assert.ok(html.includes('₪ 10000.00'));
assert.ok(html.includes('Long and short exposure'));
assert.ok(html.includes('Holdings not shown on the map'));
assert.ok(html.includes('Weights cover known gross holdings only'));
assert.ok(html.includes('Small change'));
assert.ok(html.includes('Unavailable'));
assert.ok(html.includes('data-heatmap-asset="0"'));
assert.ok(html.includes('All listings and values'));
assert.ok(!html.includes('NaN'));assert.ok(!html.includes('undefined'));
assert.ok(!html.includes('Alpha <company>'));
const combined=heatmapScope();assert.equal(combined[0].quantity,5);assert.equal(combined[0].gross_quantity,15);assert.equal(combined[0].gross_value_ils,6000);
heatmapView.account_id='one';renderHeatmap();html=target.innerHTML;
assert.ok(html.includes('₪ 4000.00'));assert.equal(heatmapScope().length,2);assert.equal(heatmapScope()[0].quantity,10);assert.equal(heatmapExcluded().length,0);
heatmapView.account_id='two';renderHeatmap();assert.equal(heatmapScope()[0].quantity,-5);assert.equal(heatmapScope()[0].gross_value_ils,2000);assert.ok(target.innerHTML.includes('Short exposure'));assert.ok(target.innerHTML.includes('₪ 6000.00'));
heatmapView.account_id='empty';renderHeatmap();assert.ok(target.innerHTML.includes('No holdings match the selected asset types'));assert.ok(!target.innerHTML.includes('heatmap-canvas'));
''')


def test_legend_is_last_and_requested_explanatory_copy_is_absent_in_both_languages():
    run_ui(r'''
seed();heatmapView.data.assets[0].valuation_status='stale';
for(const language of ['en','he']){
 state.language=language;renderHeatmap();const html=target.innerHTML;
 for(const phrase of [
  'Area: gross ILS value · Color: latest observed price move',
  'Includes older or estimated values. Select a security to inspect its basis and dates.',
  'Select a security in the map or list for prices, dates and account holdings.'
 ])assert.ok(!html.includes(heatmapText(phrase)));
 assert.ok(html.includes('<legend class="sr-only">'+heatmapText('Asset types')+'</legend>'));
 const legend=html.lastIndexOf('<div class="heatmap-legend"');
 assert.ok(legend>html.indexOf('id="heatmapMethod"'));
 assert.ok(legend>html.indexOf('class="heatmap-all-list"'));
 assert.ok(html.slice(legend).endsWith('</small></div>'));
 for(const label of ['Fall','Small change','Unavailable','Rise'])assert.ok(html.slice(legend).includes(heatmapText(label)));
 assert.ok(html.slice(legend).includes(heatmapText('Muted blue: −0.1% to below 0%. Brighter blue: 0% to +0.2%, inclusive.')));
 assert.ok(heatmapTooltipHtml(heatmapScope()[0]).includes(heatmapText('Stale')));
}
''')


def test_click_details_preserves_identity_dates_signed_breakdown_and_escapes():
    run_ui(r'''
seed();heatmapView.selected={id:a.id,account_id:''};renderHeatmapSelection();let html=nodes.heatmapSelection.innerHTML;
assert.ok(html.includes('03/11/2026'));assert.ok(html.includes('02/11/2026'));assert.ok(html.includes('+10.00%'));assert.ok(html.includes('60.00%'));assert.ok(html.includes('Alpha &lt;company&gt;'));assert.ok(!html.includes('Alpha <company>'));assert.ok(html.includes('-5.0000'));assert.ok(html.includes('First'));assert.ok(html.includes('Second'));assert.ok(html.includes('₪ 6000.00'));assert.ok(html.includes('₪ 2000.00'));
heatmapView.selected={id:a.id,account_id:'two'};renderHeatmapSelection();html=nodes.heatmapSelection.innerHTML;assert.ok(html.includes('33.33%'));assert.ok(!html.includes('First'));assert.ok(html.includes('Short exposure'));
heatmapView.selected={id:b.id,account_id:''};renderHeatmapSelection();html=nodes.heatmapSelection.innerHTML;assert.ok(html.includes('A previous price observation is missing.'));assert.ok(html.includes('Unavailable'));assert.ok(!html.includes('>0.00%</bdi>'));
''')


def test_supported_fund_and_bond_without_moves_keep_weights_in_tooltip():
    run_ui(r'''
seed();
const fund={...a,id:'fund',symbol:'5139324',name:'Recorded fund',asset_class:'MUTUALFUND',currency:'ILS',stock_market:'TASE',quantity:100,gross_quantity:100,price:null,price_date:null,previous_price:null,previous_date:null,change_percent:null,gross_value_ils:1000,value_ils:1000,valuation_basis:'cost_basis',valuation_status:'estimated',unrealized_pnl_native:9999,unrealized_pnl_ils:9999,issues:['missing_price','estimated_value'],accounts:[{...row('one',100,1000),valuation_basis:'cost_basis',valuation_status:'estimated'}]};
const bond={...a,id:'bond',symbol:'BOND',asset_class:'BOND',quantity:1000,gross_quantity:1000,price:.75,price_date:'2026-07-31',change_percent:null,gross_value_ils:3000,value_ils:3000,valuation_basis:'saved_price',valuation_status:'stale',issues:['stale_price'],accounts:[{...row('two',1000,3000),valuation_basis:'saved_price',valuation_status:'stale'}]};
heatmapView.data.assets=[fund,bond];heatmapView.data.excluded=[];
for(const language of ['en','he']){
 state.language=language;renderHeatmap();const tiles=heatmapTileMap(heatmapScope());
 assert.equal((tiles.match(/class="heatmap-tile"/g)||[]).length,2);
 const visibleTiles=tiles.replace(/aria-label="[^"]*"/g,'');
 assert.ok(!visibleTiles.includes('25.0%'));assert.ok(!visibleTiles.includes('75.0%'));
 assert.ok(!visibleTiles.includes('class="heatmap-tile-change"'));
 assert.ok(!visibleTiles.includes(language==='he'?'לא זמין':'Unavailable'));
 assert.ok(visibleTiles.includes('5139324'));assert.ok(visibleTiles.includes('₪ 1000.00'));
 assert.ok(heatmapTooltipHtml(fund).includes(language==='he'?'לא זמין':'Unavailable'));
 const weight=language==='he'?'משקל':'weight';
 assert.ok(heatmapTooltipHtml(fund).includes(`25.0% ${weight}`));
 assert.ok(heatmapTooltipHtml(bond).includes(`75.0% ${weight}`));
 assert.ok(!heatmapListing(fund).includes(`25.0% ${weight}`));
 assert.equal((tiles.match(/background:#353942/g)||[]).length,2);
 assert.ok(!target.innerHTML.includes('heatmap-unsized'));
 const tooltip=heatmapTooltipHtml(fund);assert.ok(tooltip.includes(language==='he'?'אומדן לפי עלות':'Cost-based estimate'));assert.ok(!tooltip.includes('9999'));
 heatmapView.selected={id:'bond',account_id:''};renderHeatmapSelection();assert.ok(nodes.heatmapSelection.innerHTML.includes('31/07/2026'));
}
for(const language of ['en','he']){
 state.language=language;
 for(const asset_class of ['EQUITY','STOCK','RSU','ETF','MUTUALFUND','BOND']){
  const priced={...a,asset_class};
  const tooltip=heatmapTooltipHtml(priced,[priced,b]);
  assert.ok(tooltip.includes(language==='he'?'60.0% משקל':'60.0% weight'));
  assert.ok(tooltip.includes('+10.00%'));
  heatmapView.data.assets=[priced,b];
  const visibleTiles=heatmapTileMap([priced,b]).replace(/aria-label="[^"]*"/g,'');
  assert.ok(visibleTiles.includes('+10.00%'));assert.ok(!visibleTiles.includes('60.0%'));
 }
}
heatmapView.data.assets=[fund,bond];
state.language='en';const accountTooltip=heatmapTooltipHtml(bond,[bond]);assert.ok(accountTooltip.includes('100.0% weight'));assert.ok(!accountTooltip.includes('75.0% weight'));
heatmapView.categories={stocks:true,bonds:false,funds:true};renderHeatmap();assert.deepEqual(heatmapScope().map(row=>row.id),['fund']);
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
heatmapView.account_id='one';renderHeatmap();assert.equal(heatmapScope().length,1);assert.equal(heatmapScope()[0].gross_value_ils,4000);assert.ok(target.innerHTML.includes('₪ 4000.00'));assert.ok(!target.innerHTML.includes('Holdings not shown on the map'));
heatmapView.selected={id:a.id,account_id:'one'};renderHeatmapSelection();assert.ok(!nodes.heatmapSelection.innerHTML.includes('classifications conflict'));
state.language='he';assert.equal(heatmapFxSource('external_import_market_data'),'נתוני שוק ממקור מיובא');assert.equal(heatmapFxSource('bank_of_israel_fx'),'בנק ישראל');assert.equal(heatmapFxSource('Recorded daily FX quotes'),'שערי מטבע יומיים שנשמרו');assert.equal(heatmapFxSource('My exact citation'),'My exact citation');
''')


def test_dashboard_cell_keeps_account_view_selection_and_recovers_interaction():
    run_ui(r'''
seed();heatmapView.account_id='two';heatmapView.layout='accounts';heatmapView.selected={id:a.id,account_id:'two'};
let captures=0,restores=0;globalThis.preserveRenderedInteraction=node=>{assert.equal(node,target);captures++;return()=>restores++;};
for(const language of ['en','he']){state.language=language;const card=renderDashboardHeatmap();assert.ok(card.includes('class="chart-card portfolio-heatmap-card"'));assert.ok(card.includes('id="heatmapContent"'));assert.ok(!card.includes('role="dialog"'));assert.ok(!card.includes('data-modal='));assert.ok(card.includes(language==='he'?'מפת חום של מניות התיק':'Portfolio stocks heatmap'));
 renderHeatmap();assert.equal(heatmapView.account_id,'two');assert.equal(heatmapView.layout,'accounts');assert.deepEqual(heatmapView.selected,{id:a.id,account_id:'two'});assert.ok(nodes.heatmapSelection.innerHTML.includes(language==='he'?'חשיפה בחסר':'Short exposure'));assert.ok(target.innerHTML.includes('<details id="heatmapMethod"'));assert.ok(!target.innerHTML.includes('<details id="heatmapMethod" class="heatmap-method" open'));}
assert.equal(captures,2);assert.equal(restores,2);
''')


def test_investment_account_selector_rejects_other_and_untyped_accounts():
    run_ui(r'''
const outside=[{id:'esop-only',type:'ESOP',account_id:'Outside employee account'},{id:'bank-only',type:'Bank',account_id:'Outside bank account'},{id:'pension-only',type:'Long-Term Savings',account_id:'Outside pension account'},{id:'unknown-only',account_id:'Outside untyped account'}];
seed();heatmapView.data.accounts.push(...outside);renderHeatmap();
const html=target.innerHTML;for(const row of outside)assert.ok(!html.includes(row.account_id));
assert.ok(html.includes('All investment accounts'));
''')


def test_verified_import_exchange_is_shown_and_unverified_reason_is_localized():
    run_ui(r'''
assert.ok(heatmapLabel({...a,stock_market:'YAHOO',resolved_stock_market:'NASDAQ'}).includes('NASDAQ'));
assert.ok(!heatmapLabel({...a,stock_market:'YAHOO'}).includes('YAHOO'));
state.language='he';assert.equal(heatmapText(heatmapReason('unverified_listing')),'נדרשים נתוני בורסה שמורים כדי לזהות את הנייר המיובא הזה.');
''')


def test_asset_checkboxes_filter_all_account_and_grouped_totals_and_empty_choice():
    run_ui(r'''
seed();const bond={...structuredClone(a),id:'bond',symbol:'BOND',asset_class:'BOND',quantity:2,gross_value_ils:500,value_ils:500,accounts:[row('one',2,500)]};heatmapView.data.assets.push(bond);
assert.deepEqual(heatmapCategories(),{stocks:true,bonds:true,funds:true});assert.equal(heatmapScope().length,4);renderHeatmap();assert.ok(target.innerHTML.includes('id="heatmapCategory-stocks" data-heatmap-category="stocks" checked'));assert.ok(target.innerHTML.includes('id="heatmapCategory-bonds" data-heatmap-category="bonds" checked'));
for(const category of ['stocks','bonds','funds'])for(const listener of listeners.change)listener({target:{id:`heatmapCategory-${category}`,checked:false}});
assert.equal(heatmapScope().length,0);assert.ok(target.innerHTML.includes('Choose Stocks, Bonds or Funds'));assert.ok(!target.innerHTML.includes('heatmap-canvas'));
for(const listener of listeners.change)listener({target:{id:'heatmapCategory-bonds',checked:true}});assert.deepEqual(heatmapScope().map(asset=>asset.symbol),['BOND']);assert.ok(target.innerHTML.includes('₪ 500.00'));assert.ok(!target.innerHTML.includes('₪ 10000.00'));assert.equal(heatmapValueFraction(heatmapScope()[0],heatmapScope()),100);
heatmapView.layout='accounts';renderHeatmap();assert.ok(target.innerHTML.includes('data-heatmap-account="one"'));assert.deepEqual(heatmapCategories(),{stocks:false,bonds:true,funds:false});assert.equal(pending.length,0);
heatmapView.data.account_assets={one:[bond,structuredClone(a)]};heatmapView.account_id='one';assert.deepEqual(heatmapScope().map(asset=>asset.symbol),['BOND']);
state.language='he';heatmapView.categories={stocks:false,bonds:false,funds:false};renderHeatmap();assert.ok(target.innerHTML.includes('בחרו מניות, אג״ח או קרנות'));assert.ok(!target.innerHTML.includes('Choose Stocks'));
''')


def test_multiline_popup_and_click_detail_show_localized_native_and_converted_pnl():
    run_ui(r'''
seed();Object.assign(heatmapView.data.assets[0].accounts[0],{cost_basis_native:500,unrealized_pnl_native:600,unrealized_pnl_ils:2400});Object.assign(heatmapView.data.assets[0].accounts[1],{cost_basis_native:400,unrealized_pnl_native:-150,unrealized_pnl_ils:-600});const asset=heatmapScope()[0];assert.equal(asset.unrealized_pnl_native,450);assert.equal(asset.unrealized_pnl_ils,1800);
for(const language of ['en','he']){state.language=language;const html=heatmapTooltipHtml(asset);assert.ok(html.includes('Alpha &lt;company&gt;'));assert.ok(html.includes('USD 450.00'));assert.ok(html.includes('₪ 1800.00'));assert.ok(html.includes('USD 110.00'));assert.ok(html.includes('03/11/2026'));assert.ok(html.includes('5.0000'));assert.ok(html.includes('15.0000'));assert.ok(html.includes('First'));assert.ok(html.includes('Second'));assert.ok(!html.includes('NaN'));if(language==='he'){assert.ok(html.includes('רווח / הפסד לא ממומש'));assert.ok(html.includes('המרה לשקלים'));assert.ok(!/Unrealized|Converted|Accounts|Observed price/.test(html));}else assert.ok(html.includes('Unrealized profit / loss'));heatmapView.selected={id:asset.id,account_id:''};renderHeatmapSelection();assert.ok(nodes.heatmapSelection.innerHTML.includes('USD 450.00'));assert.ok(nodes.heatmapSelection.innerHTML.includes('₪ 1800.00'));}
asset.unrealized_pnl_native=null;asset.unrealized_pnl_ils=null;state.language='en';assert.ok(heatmapTooltipHtml(asset).includes('Unavailable'));assert.ok(!heatmapTooltipHtml(asset).includes('USD 0.00'));
''')


def test_popup_is_viewport_clamped_keyboard_described_and_escape_does_not_move_focus():
    run_ui(r'''
seed();globalThis.window={innerWidth:390,innerHeight:300};const popupListeners={};const popup={hidden:true,style:{},setAttribute(k,v){this[k]=v;},addEventListener(type,fn){popupListeners[type]=fn;},getBoundingClientRect(){return {width:360,height:250};}};document.createElement=()=>popup;document.body={appendChild(node){assert.equal(node,popup);}};const button={dataset:{heatmapAsset:'0',heatmapAccount:''},isConnected:true,attrs:{},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];},getBoundingClientRect(){return {left:380,right:390,top:290,bottom:300};}};document.activeElement=button;showHeatmapTooltip(button);assert.equal(button.attrs['aria-describedby'],'heatmapTooltip');assert.equal(popup.role,'tooltip');assert.equal(popup.hidden,false);assert.equal(popup.style.left,'22px');assert.equal(popup.style.top,'32px');assert.ok(popup.innerHTML.includes('First'));
popupListeners.pointerenter();assert.equal(heatmapTooltipHovered,true);for(const listener of listeners.focusout)listener({target:button});assert.equal(popup.hidden,false);
let prevented=false,stopped=false;for(const listener of listeners.keydown)listener({key:'Escape',preventDefault(){prevented=true;},stopImmediatePropagation(){stopped=true;}});assert.equal(popup.hidden,true);assert.equal(popup.innerHTML,'');assert.equal(button.attrs['aria-describedby'],undefined);assert.equal(document.activeElement,button);assert.equal(prevented,true);assert.equal(stopped,true);
state.language='he';showHeatmapTooltip(button);assert.equal(popup.dir,'rtl');hideHeatmapTooltip();assert.equal(popup.hidden,true);
''')


def test_label_font_fits_dimensions_and_hides_secondary_text_before_primary():
    run_ui(r'''
function rectangle(width,height,symbolLength=12){const button={clientWidth:width,clientHeight:height,dataset:{},size:16,style:{setProperty(k,v){button.size=parseInt(v);}},querySelector(selector){if(selector==='.heatmap-tile-label')return label;return rows[selector.replace('.heatmap-tile-','')];}};const lengths={symbol:symbolLength,change:6,value:8,direction:19},rows={};for(const [key,length] of Object.entries(lengths)){rows[key]={get clientWidth(){return width-8;},get scrollWidth(){return key==='symbol'&&button.dataset.heatmapLabelMode?.endsWith('-wrap')?width-8:length*button.size*(key==='value'||key==='direction'?.48:.6);}};}const label={get scrollWidth(){return width;},get scrollHeight(){const mode=button.dataset.heatmapLabelMode,count=mode==='full'?4:mode?.startsWith('compact')?2:1,wrappedLines=mode?.endsWith('-wrap')?Math.ceil(symbolLength*button.size*.6/(width-8)):1;return 8+(count+wrappedLines-1)*(button.size*1.15)+(count-1)*2;}};return button;}
const full=rectangle(220,110);heatmapFitLabel(full);assert.equal(full.dataset.heatmapLabelMode,'full');assert.equal(full.size,16);
const small=rectangle(100,34);heatmapFitLabel(small);assert.equal(small.dataset.heatmapLabelMode,'compact');assert.ok(small.size>=9&&small.size<16);
const thin=rectangle(100,21);heatmapFitLabel(thin);assert.equal(thin.dataset.heatmapLabelMode,'symbol');
const longSymbol=rectangle(93,159,16);heatmapFitLabel(longSymbol);assert.equal(longSymbol.dataset.heatmapLabelMode,'compact-wrap');assert.equal(longSymbol.size,16);
const tiny=rectangle(12,8);heatmapFitLabel(tiny);assert.equal(tiny.dataset.heatmapLabelMode,'none');assert.equal(tiny.clientWidth,12);assert.equal(tiny.clientHeight,8);
''')


def test_asset_type_icons_distinguish_bonds_and_funds_from_stocks():
    run_ui(r'''
seed();
assert.equal(heatmapTypeIcon(a),'');
for(const asset_class of ['ETF','MUTUALFUND','MUTUAL_FUND']){
 const asset={...a,asset_class};
 assert.ok(heatmapTypeIcon(asset).includes('data-heatmap-type="funds"'));
 const tile=heatmapTileMap([asset]);
 assert.ok(tile.includes('heatmap-type-icon'));
 assert.ok(tile.includes(`<title>${heatmapClass(asset)}</title>`));
 assert.ok(heatmapButtonLabel(asset,[asset]).includes(heatmapClass(asset)));
}
const bond={...a,asset_class:'BOND'};
assert.ok(heatmapTypeIcon(bond).includes('data-heatmap-type="bonds"'));
assert.ok(heatmapTileMap([bond]).includes('<title>Bond</title>'));
assert.ok(target.innerHTML.includes('data-heatmap-type="funds"'));
assert.ok(target.innerHTML.includes('data-heatmap-type="bonds"'));
state.language='he';
assert.ok(heatmapTypeIcon(bond).includes('<title>אג״ח</title>'));
''')


def test_small_changes_are_blue_and_unavailable_stays_gray_without_inventing_zero():
    run_ui(r'''
seed();
assert.equal(heatmapColor(0),'#245F91');
assert.equal(heatmapColor(-0),'#245F91');
for(const value of [-.1,-.09999,-.01])assert.equal(heatmapColor(value),'#3B5278');
for(const value of [0,.1,.19999,.2])assert.equal(heatmapColor(value),'#245F91');
assert.equal(heatmapColor(-.100001),'#a12e43');
assert.equal(heatmapColor(.200001),'#207158');
assert.equal(heatmapColor((100.2 / 100 - 1) * 100),'#245F91');
assert.equal(heatmapColor((99.9 / 100 - 1) * 100),'#3B5278');
for(const value of [null,undefined,NaN,Infinity,'0'])assert.equal(heatmapColor(value),'#353942');
assert.equal(heatmapColor(0.01),heatmapColor(0));
assert.notEqual(heatmapColor(-0.01),heatmapColor(0));
const unchanged={...a,change_percent:0};
const missing={...b,change_percent:null};
const unchangedTile=heatmapTileMap([unchanged]);
const missingTile=heatmapTileMap([missing]);
assert.ok(unchangedTile.includes('background:#245F91'));
assert.ok(unchangedTile.includes('>0.00%</bdi>'));
assert.ok(missingTile.includes('background:#353942'));
assert.ok(!missingTile.includes('>0.00%</bdi>'));
state.language='he';renderHeatmap();
assert.ok(target.innerHTML.includes('שינוי קטן'));
assert.ok(target.innerHTML.includes('לא זמין'));
''')


def test_three_color_bands_use_exact_symmetric_thresholds_and_readable_white_labels():
    run_ui(r'''
const positive=['#207158','#216452','#24463f'];
const negative=['#a12e43','#7b2737','#542b35'];
for(const sign of [-1,1]){
 const palette=sign>0?positive:negative;
 for(const [value,index] of [[.3,0],[.999999,0],[1,1],[2.999999,1],[3,2],[1000,2]])assert.equal(heatmapColor(sign*value),palette[index]);
 assert.equal(new Set([.3,.99,1,2.99,3,100].map(value=>heatmapColor(sign*value))).size,3);
}
const luminance=hex=>hex.slice(1).match(/../g).map(x=>parseInt(x,16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
for(const color of [...positive,...negative,heatmapColor(0),heatmapColor(null)])assert.ok(1.05/(luminance(color)+.05)>=4.5,color);
for(const palette of [positive,negative])assert.ok(luminance(palette[0])>luminance(palette[1])&&luminance(palette[1])>luminance(palette[2]),'Larger moves must have darker shades');
seed();for(const language of ['en','he']){
 state.language=language;renderHeatmap();
 assert.ok(target.innerHTML.includes(heatmapText('Three levels in either direction: under 1%, 1% to under 3%, and 3% or more.')));
}
''')
