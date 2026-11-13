"""Cached rating summaries stay local, correctly scoped and independent of sort."""
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    script = "const window={};\n" + (ROOT / "web/i18n.js").read_text()
    script += r'''
const assert=require('node:assert/strict');
const state={language:'en',portfolioLoadVersion:1,auth:{user:{id:'viewer',role:'Viewer'},csrfToken:'session-one'},
 securityDetail:{symbol:'ACME',market_key:'NASDAQ',currency:'USD',asset_class:'EQUITY'}};
const currentUser=()=>state.auth.user;const canWrite=()=>['Admin','Operator'].includes(currentUser()?.role);
const t=text=>window.PortfolioI18n.translate(text,state.language);
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const formatDate=date=>date.split('-').reverse().join('/');
const holdingMarketKey=h=>h.platform||h.stock_market||h.data_source||'MANUAL';
const stockMarketDisplay=h=>h.stock_market;const dataProviderDisplay=()=> 'Cached provider';
const nodes=new Map(),buttons=[],listeners=[];
const makeNode=()=>({innerHTML:'',textContent:'',hidden:false,disabled:false,dataset:{},attributes:{},
 setAttribute(name,value){this.attributes[name]=value},querySelectorAll(){return []},querySelector(){return null}});
const $=id=>{if(!nodes.has(id))nodes.set(id,makeNode());return nodes.get(id)};
const document={activeElement:null,querySelectorAll:selector=>selector==='[data-holdings-credit-key]'?buttons:[],addEventListener(type,callback){listeners.push(callback)}};
const requests=[];const api=(path,options={})=>new Promise((resolve,reject)=>requests.push({path,options,resolve,reject}));
const timers=new Map();let nextTimer=0;const setTimeout=callback=>{timers.set(++nextTimer,callback);return nextTimer};const clearTimeout=id=>timers.delete(id);
const flush=()=>new Promise(setImmediate);
const openCalls=[];const openSecurityDetail=async(data,button)=>openCalls.push({data,button});
const holding=(symbol='ACME',overrides={})=>({symbol,stock_market:'NASDAQ',platform:'NASDAQ',currency:'USD',asset_class:'EQUITY',name:'Example Company',...overrides});
const row=(symbol,overrides={})=>({holding:holding(symbol,overrides)});
const context=(symbol='ACME',rating='A3',extra={})=>({schema_version:'credit-ratings-v1',summary_only:true,
 security_key:`${symbol}|NASDAQ|USD`,symbol,stock_market:'NASDAQ',currency:'USD',issuer_name:'Example Company',ratings:[
 {agency:'moodys',status:'rated',rating,scope:'issuer',scale:'global',term:'long_term',outlook:'stable',watch:'unknown',stale:false},
 {agency:'sp',status:'rated',rating:'A-',outlook:'negative',watch:'positive',outlook_stale:true,watch_stale:false},
 {agency:'fitch',status:'not_checked',outlook:'unknown',watch:'unknown'}],...extra});
const mount=(symbol='ACME')=>{const button=makeNode();button.dataset={holdingsCreditKey:`${symbol}|NASDAQ|USD`,holdingsCreditSymbol:symbol,securityDetailMarketKey:'NASDAQ',securityDetailCurrency:'USD'};buttons.push(button);return button};
''' + (ROOT / "web/security-credit-ratings.js").read_text() + "\n" + (ROOT / "web/holdings-credit-ratings.js").read_text() + "\n" + body
    result = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT, timeout=15)
    assert result.returncode == 0, result.stderr


def test_one_read_only_batch_deduplicates_accounts_and_does_not_seed_full_overview():
    run_ui(r'''
(async()=>{
const first=mount(),second=mount();document.activeElement=first;
const items=[row('ACME',{account_id:'one'}),row('ACME',{account_id:'two'}),row('NEXT'),row('SPY',{asset_class:'ETF'}),row('OPT',{asset_class:'EQUITY',asset_sub_class:'OPTION'}),row('BAD',{currency:''})];
const loading=loadHoldingsCreditRatings(items);
assert.equal(requests.length,1);const url=new URL(requests[0].path,'https://example.org');
assert.equal(url.pathname,'/api/securities/credit-ratings/summaries');
assert.deepEqual(url.searchParams.getAll('security_keys'),['ACME|NASDAQ|USD','NEXT|NASDAQ|USD']);
assert.equal(requests[0].options.method,undefined);assert.ok(!requests[0].options.body);
assert.equal(first.attributes['aria-busy'],'true');assert.ok(first.innerHTML.includes('Loading…'));
requests[0].resolve({summary_only:true,items:[context(),context('NEXT')],not_found_keys:[]});await loading;
assert.equal(first.innerHTML,second.innerHTML);assert.ok(first.innerHTML.includes('A3'));
assert.equal(document.activeElement,first,'batch updates preserve the existing focusable button');
assert.equal(first.attributes['aria-busy'],'false');assert.deepEqual(creditRatingsSession().entries,{},'a compact response is not a full overview context');
await loadHoldingsCreditRatings(items);await loadHoldingsCreditRatings([...items].reverse());assert.equal(requests.length,1,'redraws/filtering/sorting cannot repeat a batch in the same load generation');
assert.equal(timers.size,0);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_three_agencies_keep_primary_status_forward_fields_and_stale_scope_in_both_languages():
    run_ui(r'''
for(const language of ['he','en']){
state.language=language;const entry={state:'ready',context:context()};const html=holdingsCreditRatingsContent(entry);
for(const name of ['Moody’s','S&amp;P','Fitch'])assert.ok(html.includes(name),name);
assert.ok(html.includes('A3'));assert.ok(html.includes('A-'));assert.ok(html.includes('holding-credit-active-watch'));
assert.equal((html.match(/holding-credit-stale/g)||[]).length,1,'the stale outlook must not mark the fresh watch or grade');
if(language==='he'){
 for(const label of ['תחזית / מעקב','יציב','לא ידוע','שלילי','חיובי','לא נבדק','תחזית דירוג ישנה'])assert.ok(html.includes(label),label);
 assert.ok(!/\b(?:Stable|Unknown|Negative|Positive|Not checked|Stale outlook)\b/.test(html));
}else{assert.ok(!/[א-ת]/.test(html));assert.ok(html.includes('Outlook / Watch'));}
}
state.language='en';
for(const status of ['unrated','withdrawn','not_found','not_checked','unavailable','conflicting']){
 const entry={state:'ready',context:context('ACME','A3',{ratings:[{agency:'moodys',status,rating:status==='conflicting'?'Aaa':null,outlook:'unknown',watch:'unknown'}]})};
 const html=holdingsCreditRatingsContent(entry);assert.ok(!html.includes('>Stable<'));assert.ok(!html.includes('>No watch<'));assert.ok(!html.includes('>Aaa<'));
 assert.ok(html.includes({unrated:'Unrated',withdrawn:'Withdrawn',not_found:'Not found',not_checked:'Not checked',unavailable:'Unavailable',conflicting:'Conflicting evidence'}[status]));
}
const ancillary={state:'ready',context:context('UBS','A3',{ratings:[{agency:'moodys',status:'unavailable',reason_code:'primary_rating_unavailable',observations:[{agency:'moodys',rating:'A2',rating_type:'senior_unsecured_class',primary_eligible:false,outlook:'stable'}]}]})};
const other=holdingsCreditRatingsContent(ancillary);assert.ok(other.includes('Unavailable'));assert.ok(other.includes('Other categories'));assert.ok(!other.includes('>A2<'));
const fallback={state:'ready',context:context('BOND','A3',{ratings:[{agency:'moodys',status:'rated',rating:'A3',issuer_fallback:true,outlook:'stable',watch:'none'}]})};
assert.ok(holdingsCreditRatingsContent(fallback).includes('Issuer rating'));assert.ok(holdingsCreditRatingsDescription(fallback,'BOND').includes('specific debt issue was not verified'));
''')


def test_failed_reads_keep_saved_facts_and_unknown_inventory_is_not_unrated():
    run_ui(r'''
(async()=>{
const button=mount();const first=loadHoldingsCreditRatings([row('ACME')]);requests[0].resolve({items:[context()],not_found_keys:[]});await first;
state.portfolioLoadVersion+=1;const retry=loadHoldingsCreditRatings([row('ACME'),row('MISSING')]);
assert.ok(button.innerHTML.includes('A3'));requests[1].reject(Error('private transport details'));await retry;
assert.ok(button.innerHTML.includes('A3'));assert.equal(button.attributes['aria-busy'],'false');assert.ok(button.title.includes('Open the overview to retry'));assert.ok(!button.title.includes('private transport'));
state.portfolioLoadVersion+=1;const missing=loadHoldingsCreditRatings([row('MISSING')]);requests[2].resolve({items:[],not_found_keys:['MISSING|NASDAQ|USD']});await missing;
const entry=holdingsCreditRatingsEntry('MISSING|NASDAQ|USD');assert.equal(entry.state,'not_found');
assert.ok(holdingsCreditRatingsContent(entry).includes('Unavailable'));assert.ok(!holdingsCreditRatingsContent(entry).includes('Unrated'));
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_full_overview_wins_over_an_older_batch_and_reloads_all_matching_account_rows():
    run_ui(r'''
(async()=>{
const first=mount(),second=mount();const pending=loadHoldingsCreditRatings([row('ACME')]);
updateHoldingsCreditRatingsFromOverview(context('ACME','A2',{summary_only:false}));
requests[0].resolve({items:[context('ACME','A1')],not_found_keys:[]});await pending;
assert.ok(first.innerHTML.includes('>A2<'));assert.equal(first.innerHTML,second.innerHTML);assert.ok(!first.innerHTML.includes('>A1<'));
updateHoldingsCreditRatingsFromOverview(context('ACME','Baa1',{summary_only:true}));assert.ok(first.innerHTML.includes('>A2<'),'projected data cannot masquerade as a new full overview result');
const fullEntry=creditRatingsEntry();const fullLoad=loadSecurityCreditRatings(fullEntry);requests[1].resolve(context('ACME','Aa3',{summary_only:false}));await fullLoad;
assert.equal(fullEntry.context.ratings[0].rating,'Aa3');assert.ok(first.innerHTML.includes('>Aa3<'));assert.equal(first.innerHTML,second.innerHTML);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_portfolio_supersession_and_auth_changes_discard_stale_responses():
    run_ui(r'''
(async()=>{
const button=mount();const old=loadHoldingsCreditRatings([row('ACME')]);state.portfolioLoadVersion+=1;
const newer=loadHoldingsCreditRatings([row('ACME')]);requests[1].resolve({items:[context('ACME','A2')],not_found_keys:[]});await newer;
requests[0].resolve({items:[context('ACME','Baa3')],not_found_keys:[]});await old;assert.ok(button.innerHTML.includes('>A2<'));
state.portfolioLoadVersion+=1;const oldSession=loadHoldingsCreditRatings([row('ACME')]);
state.auth.user={id:'different-user',role:'Viewer'};state.auth.csrfToken='session-two';renderHoldingsCreditRatings();
assert.ok(!button.innerHTML.includes('>A2<'));assert.deepEqual(holdingsCreditRatingsSession().entries,{});
requests[2].resolve({items:[context('ACME','Aaa')],not_found_keys:[]});await oldSession;assert.ok(!button.innerHTML.includes('>Aaa<'));
const refreshed=loadHoldingsCreditRatings([row('ACME')]);state.portfolioLoadVersion+=1;requests[3].resolve({items:[context('ACME','Aa1')],not_found_keys:[]});await refreshed;
assert.equal(button.attributes['aria-busy'],'false','a superseded portfolio failure must not leave permanent rating loading');assert.ok(!button.innerHTML.includes('>Aa1<'));
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_bounded_batches_skip_ineligible_or_incomplete_identities_and_reject_mismatches():
    run_ui(r'''
(async()=>{
const items=Array.from({length:205},(_,index)=>row(`C${index}`));const loading=loadHoldingsCreditRatings(items);
assert.equal(requests.length,2);
const keys=index=>new URL(requests[index].path,'https://example.org').searchParams.getAll('security_keys');
assert.equal(keys(0).length,200);assert.equal(keys(1).length,5);
requests[0].resolve({items:[],not_found_keys:keys(0)});requests[1].resolve({items:[],not_found_keys:keys(1)});await loading;
assert.equal(requests.length,2);state.portfolioLoadVersion+=1;
await loadHoldingsCreditRatings([row('SPY',{asset_class:'ETF'}),row('PRIVATE',{stock_market:'PRIVATE'}),row('NOCCY',{currency:''})]);assert.equal(requests.length,2);
const invalid=loadHoldingsCreditRatings([row('ACME')]);requests[2].resolve({items:[context('ACME','Aaa',{symbol:'OTHER'})],not_found_keys:[]});await invalid;
assert.equal(holdingsCreditRatingsEntry('ACME|NASDAQ|USD').state,'error');assert.equal(holdingsCreditRatingsEntry('ACME|NASDAQ|USD').context,null);
assert.ok(holdingCreditRatingsCellHtml(row('SPY',{asset_class:'ETF'})).includes('Not applicable'));
assert.ok(holdingCreditRatingsCellHtml(row('NOCCY',{currency:''})).includes('A symbol, stock market and currency are required'));
const escaped=holdingCreditRatingsCellHtml(row('ACME',{name:'<img src=x onerror=alert(1)>'}));assert.ok(!escaped.includes('<img'));assert.ok(escaped.includes('&lt;img'));
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_read_only_summary_action_opens_the_same_security_overview():
    run_ui(r'''
(async()=>{
const button=mount();button.dataset.securityDetailAsset='EQUITY';
for(const callback of listeners)callback({target:{closest:selector=>selector==='[data-holdings-credit-key]'?button:null}});
await flush();assert.equal(openCalls.length,1);assert.equal(openCalls[0].data.securityDetailSymbol,'ACME');assert.equal(openCalls[0].button,button);
assert.equal(requests.length,0,'opening dispatch does not start a rating job');
const item=row('ACME',{platform:'YAHOO',stock_market:'NASDAQ'});assert.equal(holdingsCreditRatingsKey(item.holding),'ACME|NASDAQ|USD');
const detail=creditRatingsEntry({symbol:'ACME',currency:'USD',market_key:'YAHOO',item});assert.equal(detail.identity.stock_market,'NASDAQ');
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_help_and_column_structure_keep_rating_readiness_separate_from_core_analytics():
    run_ui(r'''
const fs=require('node:fs');const html=fs.readFileSync('web/index.html','utf8'),app=fs.readFileSync('web/app.js','utf8');
const paragraph=html.match(/<p>(Holdings shows saved Moody’s[\s\S]*?)<\/p>/)[1].replaceAll('&amp;','&');
assert.notEqual(window.PortfolioI18n.translate(paragraph,'he'),paragraph);
assert.ok(paragraph.includes('only reads saved data'));assert.ok(paragraph.includes('this column is not sortable'));assert.ok(paragraph.includes('Include missing'));
const heading=html.match(/<th[^>]*data-holdings-credit-column[^>]*>[\s\S]*?<\/th>/)[0];assert.ok(!heading.includes('data-holdings-sort='));
const table=html.slice(html.indexOf('<table class="holdings-table">'),html.indexOf('<tbody id="rows">'));
assert.ok(table.indexOf('data-holdings-sort-column="dividend"')<table.indexOf('data-holdings-credit-column'));
assert.ok(table.indexOf('data-holdings-credit-column')<table.indexOf('data-holdings-sort-column="technicals"'));
const body=app.slice(app.indexOf('function renderRows('),app.indexOf('function chartPath('));
assert.ok(body.indexOf('data-label="Dividend Trend"')<body.indexOf('holdingCreditRatingsCellHtml(item)'));
assert.ok(body.indexOf('holdingCreditRatingsCellHtml(item)')<body.indexOf('data-label="Support / Resistance"'));
const status=app.slice(app.indexOf('function statusCell('),app.indexOf('function statusCell(')+2000);
assert.ok(status.includes('Analytics available'));assert.ok(status.includes('Credit ratings are shown separately.'));assert.ok(!status.includes('All displayed data available'));
const css=fs.readFileSync('web/holdings-credit-ratings.css','utf8');assert.ok(css.includes('width: 200px'));assert.ok(css.includes('width: 165px'));assert.ok(css.includes('width: 250px'));
''')
