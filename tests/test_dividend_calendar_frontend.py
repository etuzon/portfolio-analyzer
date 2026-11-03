from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def run_ui(body):
    source="const window={};\n"+(ROOT/'web/i18n.js').read_text()+r'''
const assert=require('node:assert/strict');const state={language:'en'};
const t=text=>window.PortfolioI18n.translate(text,state.language);
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const fmt=value=>String(value);const money=(value,currency)=>`${currency} ${value}`;
const formatDate=value=>value.slice(0,10).split('-').reverse().join('/');
const accountLabel=row=>row.account_id;const providerDisplayName=()=> 'FMP';
const nodes={};const $=id=>nodes[id]||=({value:'',innerHTML:'',textContent:'',disabled:false,setAttribute(name,value){this[name]=value;}});
const document={addEventListener(){}};const pending=[];const api=path=>new Promise((resolve,reject)=>pending.push({path,resolve,reject}));
const year=new Date().getFullYear();
const a={id:'AAA@NASDAQ',symbol:'AAA',stock_market:'NASDAQ',name:'Alpha',currency:'USD',year_dividend_per_share:4,year_payment_count:4,ttm_dividend_per_share:4,annual_yield_percent:4,price:100,price_date:'2026-11-03',history_partial:false,history_stale:false,price_stale:false,currency_conflict:false,invalid_prices:0,rankable:true,highest_yield:true,source:'financial_modeling_prep',fetched_date:'2026-11-03',history_from:'2024-01-01',history_to:'2026-11-01',invalid_records:0,undated_records:0,recorded_income:[{currency:'USD',amount:20}]};
const b={...a,id:'BBB@NASDAQ',symbol:'BBB',year_dividend_per_share:5,year_payment_count:1,ttm_dividend_per_share:5,annual_yield_percent:2.5,price:200,highest_yield:false};
const c={...a,id:'EMPTY@NASDAQ',symbol:'EMPTY',year_dividend_per_share:null,ttm_dividend_per_share:null,annual_yield_percent:null,price:null,rankable:false,highest_yield:false,source:null,recorded_income:[]};
const data={year,account_id:'',accounts:[{id:'a',type:'Investment',account_id:'First'}],available_years:[year-1,year],ttm_from:'2025-11-03',ttm_to:'2026-11-03',assets:[a,b,c],excluded:[],events:[{id:'a1',asset_id:a.id,date:`${year}-01-20`,date_type:'payment',amount_per_share:1,currency:'USD',future:false},{id:'b1',asset_id:b.id,date:`${year}-01-10`,date_type:'ex_date',amount_per_share:5,currency:'USD',future:false},{id:'c1',asset_id:c.id,date:`${year}-02-10`,date_type:'ledger',recorded_amount:10,amount_per_share:null,currency:'USD',future:false}]};
''' +(ROOT/'web/dividend-calendar-ui.js').read_text()+'\n'+body
    result=subprocess.run(['node'],input=source,text=True,capture_output=True,cwd=ROOT)
    assert result.returncode==0,result.stderr


def test_calendar_annual_yield_emphasis_and_payment_labels_in_both_languages():
    run_ui(r'''
dividendCalendarView.data=data;
for(const language of ['en','he','en']){
 state.language=language;renderDividendCalendar();const html=$('dividendCalendarResults').innerHTML;
 assert.equal((html.match(/class="dividend-month"/g)||[]).length,12);
 assert.ok(html.includes('AAA')&&html.includes('4%')&&html.includes('2.5%'));
 assert.ok(html.includes('03/11/2026'));assert.ok(!/NaN|undefined/.test(html));
 const dotFor=id=>Number(html.slice(html.indexOf(`data-dividend-calendar-event="${id}"`)).match(/--yield-size:([\d.]+)px/)[1]);
 // The $1 quarterly stock has larger annual yield than the $5 annual payer.
 assert.ok(dotFor('a1')>dotFor('b1'));
 assert.ok(html.includes('unknown-yield'));assert.ok(html.includes('highest-yield'));
 if(language==='he')assert.ok(!/Annual yield|Annual dividend|Payment date|payment date|Recorded ledger|Highest annual|Known year|No recorded income/.test(html));
 else assert.ok(!/[א-ת]/.test(html));
 dividendCalendarView.selected='a1';renderDividendCalendarDetails();
 assert.ok($('dividendCalendarDetails').innerHTML.includes('USD 1'));
 assert.ok($('dividendCalendarDetails').innerHTML.includes('USD 4'));
}
''')


def test_account_year_races_failure_retry_and_logout_do_not_publish_stale_data():
    run_ui(r'''
(async()=>{
 const first=loadDividendCalendar();$('dividendCalendarAccount').value='a';const second=loadDividendCalendar();
 assert.equal(dividendCalendarView.loading,true);
 pending[1].resolve({...data,account_id:'a'});await second;
 pending[0].resolve({...data,year:1999});await first;assert.equal(dividendCalendarView.data.account_id,'a');
 const failure=loadDividendCalendar();pending[2].reject(new Error('secret-provider-message'));await failure;
 assert.ok($('dividendCalendarStatus').textContent.includes('Reload'));
 assert.ok(!$('dividendCalendarStatus').textContent.includes('secret'));assert.ok($('dividendCalendarResults').innerHTML.includes('AAA'));
 $('dividendCalendarYear').value=String(year-1);const past=loadDividendCalendar();
 assert.equal($('dividendCalendarResults').innerHTML,'');pending[3].resolve({...data,account_id:'a',year:year-1});await past;
 assert.ok($('dividendCalendarResults').innerHTML.includes('This comparison stays current'));
 const late=loadDividendCalendar();resetDividendCalendar();pending[4].resolve(data);await late;
 assert.equal(dividendCalendarView.data,null);assert.equal($('dividendCalendarResults').innerHTML,'');
})();
''')


def test_missing_and_partial_values_are_explained_without_fake_zero_yields():
    run_ui(r'''
dividendCalendarView.data={...data,assets:[{...c,history_partial:true,price_stale:true,history_stale:true}],events:[data.events[2]]};
renderDividendCalendar();const html=$('dividendCalendarResults').innerHTML;
assert.ok(html.includes('Annual yield unavailable'));assert.ok(html.includes('Partial dividend history'));
assert.ok(!html.includes('0%'));assert.ok(!html.includes('highest-yield'));
dividendCalendarView.data={...data,assets:[],events:[]};renderDividendCalendar();
assert.ok($('dividendCalendarResults').innerHTML.includes('No eligible long'));
''')


def test_static_calendar_and_help_copy_translates():
    class Text(HTMLParser):
        def __init__(self):super().__init__();self.parts=[]
        def handle_data(self,value):
            if value.strip():self.parts.append(value.strip())
    html=(ROOT/'web/index.html').read_text()
    modal='<div id="dividendCalendarModal"'+html.split('<div id="dividendCalendarModal"',1)[1].split('<div id="xrayModal"',1)[0]
    help_entry=html.split('<h3>Dividend Calendar</h3>',1)[1].split('</article>',1)[0]
    parser=Text();parser.feed(modal+help_entry)
    source="const window={};\n"+(ROOT/'web/i18n.js').read_text()+f'\nconst parts={json.dumps(parser.parts)};'
    source+="process.stdout.write(JSON.stringify(parts.filter(x=>/[A-Za-z]/.test(x)&&window.PortfolioI18n.translate(x,'he')===x)));"
    result=subprocess.run(['node'],input=source,text=True,capture_output=True,check=True)
    assert json.loads(result.stdout)==[]


def test_investment_account_selector_rejects_other_and_untyped_accounts():
    run_ui(r'''
const outside=[{id:'esop-only',type:'ESOP',account_id:'Outside employee account'},{id:'bank-only',type:'Bank',account_id:'Outside bank account'},{id:'pension-only',type:'Long-Term Savings',account_id:'Outside pension account'},{id:'unknown-only',account_id:'Outside untyped account'}];
data.accounts.push(...outside);dividendCalendarView.data=data;renderDividendCalendar();
const html=nodes.dividendCalendarAccount.innerHTML;for(const row of outside)assert.ok(!html.includes(row.account_id));
assert.ok(html.includes('All investment accounts'));
''')


def test_removed_account_recovers_to_investment_scope():
    run_ui(r'''
(async()=>{$('dividendCalendarAccount').value='removed';const old=loadDividendCalendar();pending[0].reject(new Error('unknown_dividend_account'));await new Promise(resolve=>setImmediate(resolve));assert.equal(nodes.dividendCalendarAccount.value,'');assert.equal(dividendCalendarView.data,null);pending[1].resolve(data);await old;assert.equal(dividendCalendarView.data.assets.length,3);})();
''')
