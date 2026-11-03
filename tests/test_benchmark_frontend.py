"""Behavioral checks for benchmark forms, async state, locale and permissions."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    script = r'''
const assert=require('node:assert/strict');
const window={};
''' + (ROOT / "web/i18n.js").read_text() + r'''
const state={language:'en'};
let writer=true;
const canWrite=()=>writer;
const t=s=>window.PortfolioI18n.translate(s,state.language);
const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const decode=s=>String(s??'').replaceAll('&quot;','"').replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&#39;',"'").replaceAll('&amp;','&');
const fmt=(v,n=2)=>Number(v).toFixed(n);
const money=(v,c,n=2)=>`${c} ${Number(v).toFixed(n)}`;
const accountLabel=row=>row.account_id || row.id;
const parseDateInput=value=>{const s=String(value||'');const p=s.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);const iso=p?`${p[3]}-${p[2]}-${p[1]}`:s;if(!/^\d{4}-\d{2}-\d{2}$/.test(iso))return '';const d=new Date(iso+'T00:00:00Z');return Number.isNaN(+d)||d.toISOString().slice(0,10)!==iso?'':iso;};
const formatDate=value=>{const iso=parseDateInput(value);return iso?iso.split('-').reverse().join('/'):value||'';};
const nodes={};
const target={_html:'',get innerHTML(){return this._html},set innerHTML(html){
 this._html=html;for(const id of Object.keys(nodes))if(id!=='benchmarkContent')delete nodes[id];
 for(const match of html.matchAll(/<(input|select|textarea|details|p|button)\b([^>]*\bid="([^"]+)"[^>]*)>/g)){
  const [,tag,attrs,id]=match;const content=['select','textarea'].includes(tag)?html.slice(match.index+match[0].length).split('</'+tag+'>')[0]:'';let value=decode((attrs.match(/\bvalue="([^"]*)"/)||[])[1]||'');
  if(tag==='textarea')value=decode(content);
  if(tag==='select'){const options=[...content.matchAll(/<option\b([^>]*)>(.*?)<\/option>/g)];const selected=options.find(row=>/\bselected\b/.test(row[1]))||options[0];value=decode((selected?.[1].match(/\bvalue="([^"]*)"/)||[])[1]||'');}
  nodes[id]={value,checked:/\bchecked\b/.test(attrs),disabled:/\bdisabled\b/.test(attrs),readOnly:/\breadonly\b/.test(attrs),open:/\bopen\b/.test(attrs),textContent:content,innerHTML:content};
 }
}};
nodes.benchmarkContent=target;
const $=id=>nodes[id];
const listeners={};
const document={addEventListener(type,fn){(listeners[type] ||= []).push(fn);}};
const pending=[];
const api=(path,options={})=>new Promise((resolve,reject)=>pending.push({path,options,resolve,reject}));
const data={accounts:[{id:'a',account_id:'One'},{id:'b',account_id:'Two'}],catalog:[{id:'sp500',name:'S&P 500',currency:'USD'},{id:'ta25',name:'TA-25',valid_to:'2017-02-08'}],dataset:{currency:'USD',source:'statement <safe>',flows_complete:true,valuations:[{date:'2025-01-01',value:1000},{date:'2026-01-01',value:1210}],cash_flows:[]},index_dataset:{name:'S&P 500',currency:'USD',basis:'price',source:'official <safe>',levels:[{date:'2025-01-01',level:100},{date:'2026-01-01',level:110}]},suggested_valuations:[{date:'2025-01-01',value:999}],result:{currency:'USD',date_from:'2025-01-01',date_to:'2026-01-01',portfolio:{xirr:{value:21,status:'ok'},twrr:{value:21,status:'ok'},opening_value:1000,closing_value:1210,net_flows:0,gain:210},benchmark:{xirr:{value:10,status:'ok'},twrr:{value:10,status:'ok'},ending_value:1100,level_dates:[{date:'2025-01-01',level_date:'2024-12-31',level:100}]},chart:[{date:'2025-01-01',portfolio_growth:100,benchmark_growth:100},{date:'2026-01-01',portfolio_growth:121,benchmark_growth:110}]}};
function seed(scope=''){benchmarkView.data=data;benchmarkView.filters={account_id:scope,benchmark_id:'sp500',date_from:'2025-01-01',date_to:'2026-01-01'};benchmarkInitDrafts(data);renderBenchmarkComparison();}
''' + (ROOT / "web/benchmark-ui.js").read_text() + "\n" + body
    result = subprocess.run(["node"], input=script, text=True, cwd=ROOT, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_csv_dates_signs_invalid_duplicates_and_input_filters():
    run_ui(r'''
assert.deepEqual(benchmarkReadCsv('date,value\n01/01/2025,1000\n2026-01-01,1210','value'),data.dataset.valuations);
assert.deepEqual(benchmarkReadCsv('date,amount\n02/01/2025,100\n03/01/2025,-50','amount'),[{date:'2025-01-02',amount:100},{date:'2025-01-03',amount:-50}]);
for(const text of ['date,value\n31/02/2025,1','date,value\n01/01/2025,NaN','date,value\n01/01/2025,','date,value\n01/01/2025,100\n01/01/2025,200'])assert.throws(()=>benchmarkReadCsv(text,'value'));
seed();nodes.benchmarkFrom.value='01/01/2026';nodes.benchmarkTo.value='01/01/2025';assert.equal(benchmarkReadFilters(),false);
assert.ok(nodes.benchmarkStatus.textContent.includes('From before To'));
nodes.benchmarkFrom.value='01/01/2025';nodes.benchmarkTo.value='01/01/2026';assert.equal(benchmarkReadFilters(),true);
''')


def test_render_both_languages_dates_escaped_evidence_and_statuses():
    run_ui(r'''
seed();
for(const language of ['en','he','en']){
 state.language=language;renderBenchmarkComparison();const html=target.innerHTML;
 assert.ok(html.includes('21.00%'));assert.ok(html.includes('10.00%'));assert.ok(html.includes('01/01/2025'));
 assert.ok(html.includes('official &lt;safe&gt;'));assert.ok(!html.includes('official <safe>'));
 assert.ok(html.includes('statement &lt;safe&gt;'));assert.ok(html.includes('31/12/2024'));
 assert.ok(html.includes('role="img"'));assert.ok(html.includes('scope="col"'));
 assert.ok(!html.includes('NaN'));assert.ok(!html.includes('undefined'));
 if(language==='he'){assert.ok(html.includes('תשואה מצטברת'));assert.ok(!html.includes('Portfolio XIRR'));assert.ok(!html.includes('Save portfolio inputs'));}
 else{assert.ok(html.includes('Portfolio XIRR'));assert.ok(!/[א-ת]/.test(html));}
 for(const status of ['incomplete_cash_flows','missing_boundary_valuation','missing_flow_valuation','nonpositive_base','negative_pre_flow_value','numeric_overflow','insufficient_dates','invalid_cash_flow_signs','ambiguous_cash_flows','no_convergence','invalid_cash_flows','currency_mismatch','index_outside_lifetime','missing_index_level','benchmark_overdrawn']){
  const reason=benchmarkReason(status);assert.ok(reason);assert.ok(!reason.includes(status));
  if(language==='he')assert.ok(/[א-ת]/.test(reason));else assert.ok(!/[א-ת]/.test(reason));
 }
}
''')


def test_drafts_are_scoped_and_retained_on_save_failure_and_reload():
    run_ui(r'''
(async()=>{
 seed('a');nodes.benchmarkSource.value='unsaved account A';benchmarkCapture();
 benchmarkView.filters.account_id='b';benchmarkView.data={...data,dataset:{...data.dataset,source:'account B'}};benchmarkInitDrafts(benchmarkView.data);renderBenchmarkComparison();
 assert.equal(nodes.benchmarkSource.value,'account B');assert.equal(benchmarkView.drafts.a.source,'unsaved account A');
 nodes.benchmarkSource.value='unsaved account B';benchmarkCapture();benchmarkView.filters.account_id='a';renderBenchmarkComparison();assert.equal(nodes.benchmarkSource.value,'unsaved account A');
 const saving=benchmarkSave('portfolio');assert.equal(benchmarkView.busy,true);assert.equal(nodes.benchmarkAccount.disabled,true);
 const saved=JSON.parse(pending[0].options.body);assert.equal(saved.account_id,'a');assert.equal(saved.source,'unsaved account A');
 pending[0].reject(new Error('provider secret'));await saving;
 assert.equal(benchmarkView.busy,false);assert.equal(nodes.benchmarkSource.value,'unsaved account A');assert.ok(!target.innerHTML.includes('provider secret'));
 const reload=benchmarkReloadSaved();pending[1].reject(new Error('offline'));await reload;assert.equal(nodes.benchmarkSource.value,'unsaved account A');
 const retry=benchmarkReloadSaved();pending[2].resolve(data);await retry;assert.equal(nodes.benchmarkSource.value,'statement <safe>');assert.equal(benchmarkView.drafts.b.source,'unsaved account B');
})();
''')


def test_requests_race_logout_and_viewer_permissions():
    run_ui(r'''
(async()=>{
 seed();const first=loadBenchmarkComparison();const second=loadBenchmarkComparison();pending[1].resolve(data);await second;
 pending[0].resolve({...data,dataset:{...data.dataset,source:'old response'}});await first;assert.equal(benchmarkView.data.dataset.source,'statement <safe>');
 const stale=loadBenchmarkComparison();resetBenchmarkComparison();pending[2].resolve(data);await stale;assert.equal(benchmarkView.data,null);assert.deepEqual(benchmarkView.drafts,{});
 seed();writer=false;renderBenchmarkComparison();assert.equal(nodes.benchmarkSource.readOnly,true);assert.equal(nodes.benchmarkComplete.disabled,true);
 assert.ok(!target.innerHTML.includes('id="benchmarkRefresh"'));assert.ok(!target.innerHTML.includes('type="submit"'));await benchmarkSave('portfolio');assert.equal(pending.length,3);
})();
''')


def test_save_success_failed_recalculation_and_machine_errors():
    run_ui(r'''
(async()=>{
 seed();const save=benchmarkSave('index');pending[0].resolve({index_dataset:data.index_dataset});await new Promise(r=>setImmediate(r));
 assert.equal(pending[1].path.startsWith('/api/portfolio/benchmark?'),true);pending[1].reject(new Error('offline'));await save;
 assert.ok(benchmarkView.message.startsWith('Saved, but'));assert.equal(nodes.benchmarkIndexSource.value,'official <safe>');
 for(const language of ['en','he']){state.language=language;const reason=benchmarkText(benchmarkFailure({message:'benchmark_provider_not_configured'},'failure'));assert.ok(reason!== 'failure');if(language==='he')assert.ok(/[א-ת]/.test(reason));}
})();
''')


def test_cash_flow_same_day_entries_and_date_edits_survive_language_change():
    run_ui(r'''
assert.deepEqual(benchmarkReadCsv('date,amount\n01/06/2025,100\n01/06/2025,-25','amount'),[{date:'2025-06-01',amount:100},{date:'2025-06-01',amount:-25}]);
seed();nodes.benchmarkFrom.value='01/03/2025';nodes.benchmarkFrom.id='benchmarkFrom';nodes.benchmarkFrom.closest=()=>target;
for(const listener of listeners.input)listener({target:nodes.benchmarkFrom});
state.language='he';renderBenchmarkComparison();assert.equal(nodes.benchmarkFrom.value,'01/03/2025');assert.equal(benchmarkView.periodEdited,true);
''')


def test_initial_portfolio_save_selects_saved_boundaries_unless_period_edited():
    run_ui(r'''
(async()=>{
 seed();nodes.benchmarkValues.value='date,value\n01/01/2024,1000\n31/12/2024,1100';benchmarkCapture();
 const save=benchmarkSave('portfolio');pending[0].resolve({});await new Promise(r=>setImmediate(r));
 assert.ok(pending[1].path.includes('date_from=2024-01-01'));assert.ok(pending[1].path.includes('date_to=2024-12-31'));pending[1].resolve(data);await save;
 benchmarkView.periodEdited=true;benchmarkView.filters.date_from='2025-01-01';benchmarkView.filters.date_to='2026-01-01';renderBenchmarkComparison();
 const again=benchmarkSave('portfolio');pending[2].resolve({});await new Promise(r=>setImmediate(r));assert.ok(pending[3].path.includes('date_from=2025-01-01'));pending[3].resolve(data);await again;
})();
''')
