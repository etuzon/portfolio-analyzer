"""Risk amount, currency evidence, permissions and async recovery in the UI."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    script = r'''
const assert=require('node:assert/strict');
const state={language:'en'};let writer=true;
const canWrite=()=>writer;const t=value=>value;
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const decode=value=>String(value??'').replaceAll('&quot;','"').replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&#39;',"'").replaceAll('&amp;','&');
const fmt=(value,digits=2)=>Number(value).toFixed(digits);
const money=(value,currency,digits=0)=>`${currency==='ILS'?'₪':'$'} ${Number(value).toFixed(digits)}`;
const currencyDisplayLabel=code=>state.language==='he'?({USD:'דולר $',ILS:'שקל ₪'}[code]||code):({USD:'$ USD',ILS:'₪ ILS'}[code]||code);
const accountLabel=row=>row.account_id||row.id;
const parseDateInput=value=>{const text=String(value||''),match=text.match(/^(\d{2})\/(\d{2})\/(\d{4})$/),iso=match?`${match[3]}-${match[2]}-${match[1]}`:text;if(!/^\d{4}-\d{2}-\d{2}$/.test(iso))return '';const day=new Date(iso+'T00:00:00Z');return Number.isNaN(+day)||day.toISOString().slice(0,10)!==iso?'':iso;};
const formatDate=value=>{const iso=parseDateInput(value);return iso?iso.split('-').reverse().join('/'):value||'';};
const nodes={},listeners={},pending=[];
const document={activeElement:null,addEventListener(type,fn){(listeners[type]||=[]).push(fn);}};
const target={_html:'',get innerHTML(){return this._html},set innerHTML(html){
 this._html=html;for(const id of Object.keys(nodes))if(!['varContent','varModal','varSummaryContent'].includes(id))delete nodes[id];
 for(const match of html.matchAll(/<(input|select|textarea|details|p|button)\b([^>]*\bid="([^"]*)"[^>]*)>/g)){
  const [,tag,attrs,id]=match;const content=['select','textarea'].includes(tag)?html.slice(match.index+match[0].length).split('</'+tag+'>')[0]:'';let value=decode((attrs.match(/\bvalue="([^"]*)"/)||[])[1]||'');
  if(tag==='textarea')value=decode(content);
  if(tag==='select'){const options=[...content.matchAll(/<option\b([^>]*)>(.*?)<\/option>/g)],selected=options.find(row=>/\bselected\b/.test(row[1]))||options[0];value=decode((selected?.[1].match(/\bvalue="([^"]*)"/)||[])[1]||'');}
  nodes[id]={id,value,open:/\bopen\b/.test(attrs),disabled:/\bdisabled\b/.test(attrs),readOnly:/\breadonly\b/.test(attrs),focus(){document.activeElement=this;},textContent:''};
 }
}};
nodes.varContent=target;nodes.varModal={hidden:false};nodes.varSummaryContent={innerHTML:'',setAttribute(){}};
const $=id=>nodes[id];const api=(path,options={})=>new Promise((resolve,reject)=>pending.push({path,options,resolve,reject}));
const fx={currency:'USD',source:'Official <FX>',rates:[{date:'2025-01-01',rate:3.8},{date:'2026-01-01',rate:3.6}],revision:1,updated_at:'2026-01-02T00:00:00Z'};
const data={status:'ok',reason:null,confidence:.95,horizon_days:30,currency:'ILS',var_ils:12000,expected_shortfall_ils:16000,var_without_fx_ils:7000,portfolio_value_ils:240000,sample_count:200,min_samples:100,from:'2025-01-01',to:'2026-01-01',valuation_date:'2026-01-02',accounts:[{id:'one',type:'Investment',account_id:'First'},{id:'two',type:'Investment',account_id:'Second'}],scope_complete:true,assets:[{symbol:'SAFE<asset>',stock_market:'NASDAQ',currency:'USD',quantity:20,value_ils:72000,current_price_date:'2026-01-01',status:'ok'}],cash:[{account_id:'one',currency:'USD',amount:1000,value_ils:3600,fx_date:'2026-01-01'}],fx:[{currency:'USD',source:'Official <FX>',count:400,from:'2025-01-01',to:'2026-01-01',current_rate:3.6,current_date:'2026-01-01',status:'ok'}],issues:[],warnings:['overlapping_scenarios','limited_history','fx_fixing_times'],scenarios:[{from:'2025-01-01',to:'2025-01-31',pnl_ils:-12000,loss_ils:12000},{from:'2025-02-01',to:'2025-03-03',pnl_ils:2000,loss_ils:-2000},{from:'2025-03-01',to:'2025-03-31',pnl_ils:-20000,loss_ils:20000}],currency_exposures:[{currency:'USD',value_ils:75600}],basis:'close',fx_histories:[fx]};
function seed(){resetVar();varView.data=structuredClone(data);varView.accounts=data.accounts;renderVar();}
''' + (ROOT / 'web/var-ui.js').read_text() + '\n' + body
    result = subprocess.run(['node'], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_ils_tail_amounts_and_not_maximum_copy_in_both_languages():
    run_ui(r'''
seed();
for(const language of ['en','he','en']){
 state.language=language;renderVar();const html=target.innerHTML;
 assert.ok(html.includes('₪ 12000'));assert.ok(html.includes('₪ 16000'));assert.ok(html.includes('₪ 240000'));assert.ok(html.includes('₪ 7000'));
 assert.ok(html.includes('01/01/2025'));assert.ok(html.includes('03/03/2025'));assert.ok(html.includes('SAFE&lt;asset&gt;'));assert.ok(!html.includes('SAFE<asset>'));assert.ok(html.includes('Official &lt;FX&gt;'));
 assert.ok(html.includes('role="img"'));assert.ok(html.includes('scope="col"'));assert.ok(html.includes('data-label='));assert.ok(!html.includes('NaN'));assert.ok(!html.includes('undefined'));
 if(language==='he'){assert.ok(html.includes('כ־5%'));assert.ok(html.includes('שקלים'));assert.ok(!html.includes('Current recorded net value'));}
 else{assert.ok(html.includes('about 5% have worse losses'));assert.ok(html.includes('not a guarantee or an absolute maximum'));assert.ok(!/[א-ת]/.test(html));}
}
''')


def test_incomplete_scope_never_displays_a_partial_var_or_zero_as_whole_risk():
    run_ui(r'''
seed();varView.data={...data,status:'unavailable',scope_complete:false,reason:'coverage_incomplete',var_ils:12000,portfolio_value_ils:100,issues:[{code:'missing_fx_history',currency:'USD'}]};renderVar();assert.ok(!target.innerHTML.includes('var-kpis'));assert.ok(target.innerHTML.includes('Whole-scope VaR is unavailable'));assert.ok(!target.innerHTML.includes('₪ 12000'));
varView.data={...data,status:'ok',scope_complete:false};renderVar();assert.ok(!target.innerHTML.includes('var-kpis'));
varView.data={...data,status:'empty',scope_complete:true,var_ils:0};renderVar();assert.ok(!target.innerHTML.includes('var-kpis'));assert.ok(target.innerHTML.includes('No recorded holdings or cash'));
varView.data={...data,status:'ok',scope_complete:true,var_ils:0,warnings:['no_observed_tail_loss']};renderVar();assert.ok(target.innerHTML.includes('₪ 0'));assert.ok(target.innerHTML.includes('does not establish zero future risk'));
''')


def test_error_and_warning_codes_are_localized_and_sanitized():
    run_ui(r'''
for(const language of ['en','he']){state.language=language;for(const code of ['coverage_incomplete','insufficient_monthly_history','invalid_scenarios','unsupported_asset','unsupported_fund','invalid_position','currency_conflict','classification_conflict','missing_price_history','stale_price','missing_fx_history','stale_fx','cash_currency_mismatch','invalid_cash','invalid_valuation','future_transaction','too_many_assets','invalid_fx_history','stale_monthly_history','var_fx_invalid_currency','var_fx_invalid_payload','var_fx_source_required','var_fx_invalid_rows','var_fx_duplicate_date','var_fx_invalid_saved_history','var_fx_revision_required','var_fx_invalid_period','var_fx_refresh_failed','var_invalid_period','var_unknown_account','var_invalid_fx_history','var_invalid_date','var_conflict']){const label=varText(varReason(code));assert.ok(label!==code);if(language==='he')assert.ok(/[א-ת]/.test(label));else assert.ok(!/[א-ת]/.test(label));}for(const code of ['overlapping_scenarios','limited_history','unadjusted_prices','fx_fixing_times','constant_asset_history','no_observed_tail_loss','nominal_ils_cash_only','nonpositive_equity']){const label=varText(varWarning(code));if(language==='he')assert.ok(/[א-ת]/.test(label));else assert.ok(!/[א-ת]/.test(label));}}
assert.equal(varFailure({message:'SENSITIVE provider body'},'safe'),'safe');assert.equal(varFailure({message:'var_unknown_provider_body'},'safe'),'safe');
''')


def test_fx_csv_date_conversion_rate_units_duplicates_and_columns():
    run_ui(r'''
assert.deepEqual(varReadCsv('date,rate\n01/01/2025,3.8\n2026-01-01,3.6'),fx.rates);
for(const text of ['','date,rate\n31/02/2025,3.5','date,rate\n01/01/2025,-3','date,rate\n01/01/2025,0','date,rate\n01/01/2025,Infinity','date,rate\n01/01/2025,NaN','date,rate\n01/01/2025,3\n01/01/2025,4','date,value\n01/01/2025,3'])assert.throws(()=>varReadCsv(text));
''')


def test_viewer_can_calculate_and_inspect_but_cannot_maintain_fx():
    run_ui(r'''
(async()=>{seed();writer=false;renderVar();assert.ok(!nodes.varFxSave);assert.ok(!nodes.varFxRefresh);assert.equal(nodes.varFxSource.readOnly,true);assert.ok(nodes.varReload);await maintainVarFx(false);assert.equal(pending.length,0);const load=loadVar();pending[0].resolve(data);await load;assert.equal(varView.data.var_ils,12000);assert.ok(target.innerHTML.includes('Viewer access'));})();
''')


def test_fx_save_payload_revision_persists_on_success_and_reload_failure():
    run_ui(r'''
(async()=>{seed();nodes.varFxSource.value='New source';nodes.varFxRates.value='date,rate\n01/01/2025,3.7\n01/01/2026,3.4';
const save=maintainVarFx();assert.equal(pending[0].path,'/api/local/var-fx-history');const payload=JSON.parse(pending[0].options.body);assert.equal(payload.expected_revision,1);assert.equal(payload.currency,'USD');assert.equal(payload.rates[0].rate,3.7);
pending[0].resolve({snapshot:{...fx,source:'New source',rates:payload.rates,revision:2}});await new Promise(r=>setImmediate(r));
assert.ok(pending.some(row=>row.path==='/api/portfolio/var?account_id=&period=3y'));const modal=pending.find((row,index)=>index>0&&row.path.startsWith('/api/portfolio/var?')&&row!==pending[1]);assert.ok(modal);modal.reject(new Error('offline'));await save;assert.equal(varView.drafts.USD.expected_revision,2);assert.ok(varView.message.includes('saved, but VaR'));assert.equal(nodes.varFxSource.value,'New source');})();
''')


def test_conflict_and_failed_discard_retain_draft_then_explicit_discard_recovers():
    run_ui(r'''
(async()=>{seed();nodes.varFxSource.value='Retained draft';const save=maintainVarFx();pending[0].reject(new Error('var_conflict'));await save;assert.equal(nodes.varFxSource.value,'Retained draft');assert.equal(varView.drafts.USD.expected_revision,1);assert.ok(varView.message.includes('newer'));
const failed=discardVarFx();pending[1].reject(new Error('offline'));await failed;assert.equal(nodes.varFxSource.value,'Retained draft');
const recover=discardVarFx();pending[2].resolve({...data,fx_histories:[{...fx,revision:2,source:'Latest server'}]});await recover;assert.equal(nodes.varFxSource.value,'Latest server');assert.equal(varView.drafts.USD.expected_revision,2);})();
''')


def test_dirty_refresh_does_not_make_old_draft_overwrite_new_official_history():
    run_ui(r'''
(async()=>{seed();nodes.varFxSource.value='Unsaved manual source';const refresh=maintainVarFx(true);assert.equal(pending[0].path,'/api/portfolio/var/fx-refresh');pending[0].resolve({snapshot:{...fx,revision:2,source:'Fresh official'}});await new Promise(r=>setImmediate(r));const modal=pending.find((row,index)=>index>1&&row.path.startsWith('/api/portfolio/var?'));modal.resolve({...data,fx_histories:[{...fx,revision:2,source:'Fresh official'}]});await refresh;assert.equal(nodes.varFxSource.value,'Unsaved manual source');assert.equal(varView.drafts.USD.expected_revision,1);assert.ok(target.innerHTML.includes('older saved version'));})();
''')


def test_scope_request_race_and_logout_suppress_old_user_data():
    run_ui(r'''
(async()=>{seed();const old=loadVar();nodes.varAccount.value='two';for(const listener of listeners.change)listener({target:nodes.varAccount});assert.equal(pending.length,2);pending[1].resolve({...data,var_ils:22222});await new Promise(r=>setImmediate(r));pending[0].resolve({...data,var_ils:11111});await old;assert.equal(varView.data.var_ils,22222);
nodes.varFxSource.value='PRIVATE draft';const late=loadVar();resetVar();pending[2].resolve(data);await late;assert.equal(varView.data,null);assert.deepEqual(varView.drafts,{});assert.ok(!target.innerHTML.includes('PRIVATE'));})();
''')


def test_dashboard_summary_stays_all_accounts_and_auth_reset_rejects_late_response():
    run_ui(r'''
(async()=>{seed();varView.account_id='two';const summary=loadVarSummary();assert.equal(pending[0].path,'/api/portfolio/var?account_id=&period=3y');pending[0].resolve(data);await summary;assert.ok(nodes.varSummaryContent.innerHTML.includes('₪ 12000'));assert.ok(nodes.varSummaryContent.innerHTML.includes('All investment accounts'));assert.ok(nodes.varSummaryContent.innerHTML.includes('about 5%'));
varSummaryView.data={...data,scope_complete:false};renderVarSummary();assert.ok(!nodes.varSummaryContent.innerHTML.includes('₪ 12000'));
const late=loadVarSummary();resetVar();pending[1].resolve(data);await late;assert.equal(varSummaryView.data,null);assert.ok(!nodes.varSummaryContent.innerHTML.includes('₪ 12000'));})();
''')


def test_finite_extreme_loss_values_cannot_create_invalid_chart_coordinates():
    run_ui(r'''
seed();const html=varHistogram({...data,var_ils:1e307,scenarios:[{from:'2025-01-01',to:'2025-01-31',loss_ils:-1e308},{from:'2025-02-01',to:'2025-03-03',loss_ils:1e308}]});assert.ok(!html.includes('NaN'));assert.ok(!html.includes('Infinity'));assert.ok(html.includes('role="img"'));
''')


def test_investment_account_selector_rejects_other_and_untyped_accounts():
    run_ui(r'''
const outside=[{id:'esop-only',type:'ESOP',account_id:'Outside employee account'},{id:'bank-only',type:'Bank',account_id:'Outside bank account'},{id:'pension-only',type:'Long-Term Savings',account_id:'Outside pension account'},{id:'unknown-only',account_id:'Outside untyped account'}];
seed();varView.accounts.push(...outside);renderVar();
const html=target.innerHTML;for(const row of outside)assert.ok(!html.includes(row.account_id));
assert.ok(html.includes('All investment accounts'));
''')


def test_reclassified_account_cannot_retain_old_risk_result():
    run_ui(r'''
(async()=>{seed();varView.account_id='one';const old=loadVar();pending[0].reject(new Error('var_unknown_account'));await new Promise(resolve=>setImmediate(resolve));assert.equal(varView.account_id,'');assert.equal(varView.data,null);assert.ok(!target.innerHTML.includes('₪ 12000'));assert.ok(pending[1].path.includes('account_id=&'));pending[1].resolve({...data,accounts:data.accounts.filter(row=>row.id==='two'),var_ils:222});await old;assert.equal(varView.data.var_ils,222);})();
''')
