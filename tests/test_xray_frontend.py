from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def run_ui(body):
    source=r'''
const assert=require('node:assert/strict');const window={};
''' + (ROOT/'web/i18n.js').read_text() + r'''
const state={language:'en'};let editable=false;
const t=value=>window.PortfolioI18n.translate(value,state.language);
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const canWrite=()=>editable;
const fmt=(value)=>String(value);
const formatDate=value=>value.slice(0,10).split('-').reverse().join('/');
const formatDateTime=formatDate;
const parseDateInput=value=>value.split('/').reverse().join('-');
const accountLabel=row=>row.account_id;
const nodes={};const $=id=>nodes[id]||=( {value:'',innerHTML:'',textContent:'',hidden:false,disabled:false,setAttribute(name,value){this[name]=value;}} );
const document={addEventListener(){}};
const pending=[];const api=(path,options)=>new Promise((resolve,reject)=>pending.push({path,options,resolve,reject}));
const fund={symbol:'ONE',stock_market:'NYSE',status:'available',positions:[{account_id:'a',quantity:1}],covered_weight_percent:7.5,constituent_count:1,as_of:'2026-10-30',retrieved_at:'2026-11-03T12:00:00Z',source_name:'Example',source_kind:'local',source_url:'https://example.com/',nested_constituents:0};
const data={account_id:'',accounts:[{id:'a',account_id:'First'}],fund_count:1,funds:[fund],fund_pairs:[],excluded:[],has_shorts:false,overlaps:[{symbol:'AAPL',market:'US',name:'Apple',direct:[{account_id:'a',quantity:2}],funds:[{symbol:'ONE',stock_market:'NYSE',weight_percent:7.5,nested:false}]}]};
''' + (ROOT/'web/xray-ui.js').read_text() + '\n' + body
    result=subprocess.run(['node'],input=source,text=True,capture_output=True,cwd=ROOT)
    assert result.returncode==0,result.stderr


def test_observed_overlap_coverage_and_date_localization():
    run_ui(r'''
xrayView.data=data;
for(const lang of ['en','he','en']){
 state.language=lang;renderXray();const html=$('xrayResults').innerHTML;
 assert.ok(html.includes('7.5%'));assert.ok(html.includes('30/10/2026'));assert.ok(html.includes('03/11/2026'));
 assert.ok(html.includes('Apple'));assert.ok(html.includes('scope="row"'));
 assert.ok(!/NaN|undefined/.test(html));
 if(lang==='he')assert.ok(!/Held directly|Held through|Long|of fund|Retrieved on|Locally entered|Shared securities|reported allocation/.test(html));
 else assert.ok(!/[א-ת]/.test(html));
 assert.equal($('xrayReportEditor').hidden,true);assert.equal($('saveXrayReport').disabled,true);
}
xrayView.data={...data,overlaps:[],funds:[{...fund,status:'missing',as_of:null,retrieved_at:null}]};renderXray();
assert.ok($('xrayResults').innerHTML.includes('overlap unknown'));
''')


def test_scope_response_races_recovery_and_logout_reset():
    run_ui(r'''
(async()=>{
 const first=loadXray();$('xrayAccount').value='a';const second=loadXray();
 pending[1].resolve({...data,account_id:'a'});await second;
 pending[0].resolve({...data,fund_count:99});await first;
 assert.equal(xrayView.data.account_id,'a');assert.equal(xrayView.data.fund_count,1);
 const failure=loadXray();pending[2].reject(new Error('private-provider-message'));await failure;
 assert.ok($('xrayStatus').textContent.includes('Reload'));assert.ok(!$('xrayStatus').textContent.includes('private'));
 assert.equal(xrayView.data.account_id,'a');
 const retry=loadXray();pending[3].resolve({...data,account_id:'a'});await retry;
 assert.equal(xrayView.error,'');
 const late=loadXray();resetXray();pending[4].resolve(data);await late;
 assert.equal(xrayView.data,null);assert.equal($('xrayReportCsv').value,'');
})();
''')


def test_unsaved_drafts_stay_with_their_fund_and_old_editor_requests_are_ignored():
    run_ui(r'''
(async()=>{
 editable=true;xrayView.data=data;const one=xrayFundKey(fund),two=JSON.stringify(['TWO','NYSE']);
 xrayView.target=one;$('xrayFund').value=one;
 $('xrayReportCsv').value='symbol,market,weight_percent\nAAPL,US,7.5';$('xrayReportSource').value='Draft source';
 $('xrayFund').value=two;const load=selectXrayFund();
 assert.equal(xrayView.editorLoading,true);
 $('xrayFund').value=one;await selectXrayFund();
 assert.equal(xrayView.editorLoading,false);assert.equal($('xrayReportSource').value,'Draft source');
 pending[0].resolve({snapshot:{as_of:'2026-10-30',source_name:'Wrong fund',source_url:'',holdings:[]}});await load;
 assert.equal($('xrayReportSource').value,'Draft source');
 assert.ok($('xrayReportCsv').value.includes('7.5'));
 xrayPreview();assert.ok($('xrayPreview').textContent.includes('7.5%'));
})();
''')


def test_save_failure_preserves_draft_and_does_not_publish_a_false_result():
    run_ui(r'''
(async()=>{
 editable=true;xrayView.data=data;xrayView.target=xrayFundKey(fund);$('xrayFund').value=xrayView.target;
 $('xrayReportDate').value='30/10/2026';$('xrayReportSource').value='Example';$('xrayReportCsv').value='symbol,market,weight_percent\nAAPL,US,200';
 const saving=writeXrayReport();assert.equal(xrayView.busy,true);
 pending[0].reject(new Error('xray_invalid_weight'));await saving;
 assert.equal(xrayView.busy,false);assert.ok($('xrayReportCsv').value.includes('200'));
 assert.ok($('xrayReportStatus').textContent.includes('finite percentage'));
 assert.equal(xrayView.data,data);
 const csv='symbol,market,weight_percent,name\nAAPL,US,7.5,"Apple, Inc"\nMSFT,US,5,"Microsoft"';
 $('xrayReportCsv').value=csv;xrayPreview();assert.ok($('xrayPreview').textContent.includes('12.5%'));
 editable=false;await writeXrayReport();assert.equal(pending.length,1);
})();
''')


def test_post_save_reload_failure_retains_draft_and_reports_the_actual_outcome():
    run_ui(r'''
(async()=>{
 editable=true;xrayView.data=data;xrayView.target=xrayFundKey(fund);$('xrayFund').value=xrayView.target;
 $('xrayReportDate').value='30/10/2026';$('xrayReportSource').value='Draft source';$('xrayReportCsv').value='symbol,market,weight_percent\nAAPL,US,7.5';
 const saved=writeXrayReport();pending[0].resolve({snapshot:{}});
 await new Promise(resolve=>setImmediate(resolve));pending[1].reject(new Error('network'));await saved;
 assert.ok($('xrayReportCsv').value.includes('7.5'));assert.equal($('xrayReportSource').value,'Draft source');
 assert.ok($('xrayReportStatus').textContent.includes('Report saved, but'));
 assert.ok(!$('xrayReportStatus').textContent.includes('recalculated'));
 const next=writeXrayReport();pending[2].resolve({snapshot:{}});await new Promise(resolve=>setImmediate(resolve));
 pending[3].resolve(data);await new Promise(resolve=>setImmediate(resolve));pending[4].reject(new Error('network'));await next;
 assert.equal($('xrayReportSource').value,'Draft source');assert.ok($('xrayReportCsv').value.includes('7.5'));
 assert.ok($('xrayReportStatus').textContent.includes('report editor could not reload'));
})();
''')


def test_selected_file_finishes_before_save_and_cannot_reappear_after_logout():
    run_ui(r'''
(async()=>{
 editable=true;xrayView.data=data;xrayView.target=xrayFundKey(fund);$('xrayFund').value=xrayView.target;
 $('xrayReportCsv').value='symbol,market,weight_percent\nAAPL,US,7.5';
 let complete;const reading=readXrayFile({size:20,text:()=>new Promise(resolve=>complete=resolve)});
 assert.equal(xrayView.fileLoading,true);assert.equal($('saveXrayReport').disabled,true);
 await writeXrayReport();assert.equal(pending.length,0);
 complete('symbol,market,weight_percent\nMSFT,US,8');await reading;
 assert.equal(xrayView.fileLoading,false);const save=writeXrayReport();
 assert.ok(JSON.parse(pending[0].options.body).csv_text.includes('MSFT'));
 pending[0].reject(new Error('network'));await save;
 let late;const old=readXrayFile({size:20,text:()=>new Promise(resolve=>late=resolve)});
 resetXray();late('old-file-data');await old;assert.equal($('xrayReportCsv').value,'');
})();
''')


def test_all_xray_static_copy_and_error_messages_translate():
    class Text(HTMLParser):
        def __init__(self):super().__init__();self.parts=[]
        def handle_data(self,value):
            if value.strip():self.parts.append(value.strip())
    html=(ROOT/'web/index.html').read_text()
    modal='<div id="xrayModal"'+html.split('<div id="xrayModal"',1)[1].split('<div id="correlationModal"',1)[0]
    help_entry=html.split('<h3>X-Ray</h3>',1)[1].split('</article>',1)[0]
    parser=Text();parser.feed(modal+help_entry)
    source="const window={};\n"+(ROOT/'web/i18n.js').read_text()
    source+=f"\nconst text={json.dumps(parser.parts)};"
    source+="process.stdout.write(JSON.stringify(text.filter(x=>/[A-Za-z]/.test(x)&&window.PortfolioI18n.translate(x,'he')===x)));"
    result=subprocess.run(['node'],input=source,text=True,capture_output=True,check=True)
    assert json.loads(result.stdout)==[]
    run_ui(r'''
for(const value of Object.values(XRAY_ERRORS))assert.notEqual(window.PortfolioI18n.translate(value,'he'),value);
''')
