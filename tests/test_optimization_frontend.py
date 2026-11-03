"""Behavioral checks for allocation assumptions, historical evidence and async recovery."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    script = r'''
const assert=require('node:assert/strict');
const state={language:'en'};let writer=false;
const canWrite=()=>writer;
const t=value=>value;
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const decode=value=>String(value??'').replaceAll('&quot;','"').replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&#39;',"'").replaceAll('&amp;','&');
const fmt=(value,digits=2)=>Number(value).toFixed(digits);
const accountLabel=row=>row.account_id || row.id;
const currencyDisplayLabel=code=>state.language==='he' ? ({USD:'דולר $',ILS:'שקל ₪'}[code]||code) : '$ '+code;
const formatDate=value=>/^\d{4}-\d{2}-\d{2}$/.test(String(value||''))?value.split('-').reverse().join('/'):value||'';
const nodes={},listeners={},pending=[];let datasetInputs=[];
const document={activeElement:null,addEventListener(type,fn){(listeners[type] ||= []).push(fn);},querySelectorAll(selector){return selector==='[data-optimization-return]'?datasetInputs.filter(node=>node.dataset.optimizationReturn):[];},querySelector(){return {remove(){}};}};
const target={_html:'',get innerHTML(){return this._html},set innerHTML(html){
 this._html=html;datasetInputs=[];for(const id of Object.keys(nodes))if(!['optimizationContent','optimizationModal'].includes(id))delete nodes[id];
 for(const match of html.matchAll(/<(input|select|details|p|button|div)\b([^>]*)>/g)){
  const [,tag,attrs]=match,id=(attrs.match(/\bid="([^"]*)"/)||[])[1];
  const content=tag==='select'?html.slice(match.index+match[0].length).split('</select>')[0]:'';
  let value=decode((attrs.match(/\bvalue="([^"]*)"/)||[])[1]||'');
  if(tag==='select'){const options=[...content.matchAll(/<option\b([^>]*)>(.*?)<\/option>/g)];const selected=options.find(row=>/\bselected\b/.test(row[1]))||options[0];value=decode((selected?.[1].match(/\bvalue="([^"]*)"/)||[])[1]||'');}
  const dataset={};for(const entry of attrs.matchAll(/data-optimization-(return|asset|point)="([^"]*)"/g))dataset['optimization'+entry[1][0].toUpperCase()+entry[1].slice(1)]=decode(entry[2]);
  const node={id,value,dataset,checked:/\bchecked\b/.test(attrs),disabled:/\bdisabled\b/.test(attrs),open:/\bopen\b/.test(attrs),textContent:'',focus(){document.activeElement=this;},setSelectionRange(start,end){this.selectionStart=start;this.selectionEnd=end;},closest(){return null;}};
  if(id)nodes[id]=node;if(Object.keys(dataset).length)datasetInputs.push(node);
 }
}};
nodes.optimizationContent=target;nodes.optimizationModal={hidden:false};const $=id=>nodes[id];
const api=(path,options={})=>new Promise((resolve,reject)=>pending.push({path,options,resolve,reject}));
const assets=[{id:'a',symbol:'AAA',stock_market:'NASDAQ',name:'Name <safe>',currency:'USD',eligible:true,status:'ok',price_count:200,adjusted_available:true,basis:'adjusted_close',source:'cached',from:'2023-01-06',to:'2026-01-02',current_weight_percent:60},{id:'b',symbol:'BBB',stock_market:'NYSE',name:'Other & safe',currency:'USD',eligible:true,status:'ok',price_count:190,adjusted_available:false,basis:'close',source:'local',from:'2023-01-06',to:'2026-01-02',current_weight_percent:40}];
const data={accounts:[{id:'acct-a',type:'Investment',account_id:'One'},{id:'acct-b',type:'Investment',account_id:'Two'}],currencies:['USD','ILS'],currency:'USD',period:'3y',assets,excluded:[{symbol:'SHORT',stock_market:'NYSE',reason:'short_position'}],min_observations:26,max_assets:30,as_of:'2026-01-05',from:'2023-01-06',to:'2026-01-02'};
const result={status:'ok',assets:[{...assets[0],historical_return_percent:8,expected_return_percent:8},{...assets[1],historical_return_percent:16,expected_return_percent:16}],current:{weights:[.6,.4],expected_return_percent:11.2,volatility_percent:11,sharpe:.83636},solution:{weights:[.25,.75],expected_return_percent:14,volatility_percent:10,sharpe:1.2},minimum_variance:{weights:[.5,.5],expected_return_percent:12,volatility_percent:8,sharpe:1.25},frontier:[{id:'f0',weights:[.5,.5],expected_return_percent:12,volatility_percent:8,sharpe:1.25},{id:'f1',weights:[.2,.8],expected_return_percent:14.4,volatility_percent:12,sharpe:1.033}],observations:100,from:'2023-01-06',to:'2026-01-02',requested_from:'2023-01-02',requested_to:'2026-01-05',annualization:52,basis:'close',currency:'USD',shrinkage_percent:10,warnings:['unadjusted_prices'],feasible_return_range:{min_percent:8,max_percent:16},covariance_status:'positive_definite',intervals:[{from:'2023-01-06',to:'2023-01-13'},{from:'2023-01-13',to:'2023-01-20'}]};
function seed(){resetOptimization();optimizationView.data=structuredClone(data);optimizationView.config.currency='USD';optimizationView.selected=['a','b'];optimizationView.initialized=true;renderOptimization();}
''' + (ROOT / 'web/optimization-ui.js').read_text() + '\n' + body
    result = subprocess.run(['node'], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_readonly_payload_units_explicit_bounds_and_expected_overrides():
    run_ui(r'''
seed();assert.equal(writer,false);assert.ok(nodes.optimizationRun);
nodes.optimizationMaxWeight.value='60';nodes.optimizationRiskFree.value='2';nodes.optimizationShrinkage.value='25';
datasetInputs.find(node=>node.dataset.optimizationReturn==='a').value='12.5';
const payload=optimizationPayload();assert.equal(payload.max_weight_percent,60);assert.equal(payload.risk_free_rate_percent,2);assert.equal(payload.shrinkage_percent,25);assert.deepEqual(payload.expected_returns,{a:12.5});assert.deepEqual(payload.asset_ids,['a','b']);
for(const field of ['optimizationMaxWeight','optimizationRiskFree','optimizationShrinkage']){const before=nodes[field].value;nodes[field].value='';assert.throws(optimizationPayload);nodes[field].value=before;}
nodes.optimizationMaxWeight.value='40';assert.throws(optimizationPayload,/cap cannot/);nodes.optimizationMaxWeight.value='60';
nodes.optimizationObjective.value='target_return';optimizationCapture();renderOptimization();nodes.optimizationTarget.value='';assert.throws(optimizationPayload,/target return/);nodes.optimizationTarget.value='15';assert.equal(optimizationPayload().target_return_percent,15);
nodes.optimizationRiskFree.value='10001';assert.throws(optimizationPayload,/-10000%/);
''')


def test_render_estimates_weights_localization_and_actual_intervals():
    run_ui(r'''
seed();optimizationView.result=structuredClone(result);
for(const language of ['en','he','en']){
 state.language=language;renderOptimization();const html=target.innerHTML;
 assert.ok(html.includes('14.00%'));assert.ok(html.includes('25.00%'));assert.ok(html.includes('75.00%'));assert.ok(html.includes('-35.00'));assert.ok(html.includes('+35.00'));
 assert.ok(html.includes('Name &lt;safe&gt;'));assert.ok(!html.includes('Name <safe>'));assert.ok(html.includes('06/01/2023'));assert.ok(html.includes('13/01/2023'));
 assert.ok(html.includes('data-optimization-point="0"'));assert.ok(html.includes('role="button"'));assert.ok(html.includes('scope="col"'));assert.ok(!html.includes('NaN'));assert.ok(!html.includes('undefined'));
 if(language==='he'){assert.ok(html.includes('תשואה שנתית מוערכת'));assert.ok(!html.includes('Portfolio weights'));assert.ok(!html.includes('Short position'));}
 else{assert.ok(html.includes('Current weight in this currency'));assert.ok(!/[א-ת]/.test(html));}
}
''')


def test_frontier_inspection_updates_metrics_and_keeps_original_solution():
    run_ui(r'''
seed();optimizationView.result=structuredClone(result);renderOptimization();optimizationChoosePoint('0');assert.equal(optimizationView.activePoint,'0');assert.ok(target.innerHTML.includes('50.00%'));assert.ok(target.innerHTML.includes('12.00%'));assert.ok(nodes.optimizationOriginal);
optimizationChoosePoint('solution');assert.ok(target.innerHTML.includes('25.00%'));assert.deepEqual(optimizationView.result.solution.weights,[.25,.75]);optimizationChoosePoint('99');assert.equal(optimizationView.activePoint,'solution');
''')


def test_unavailable_results_and_machine_reasons_are_localized():
    run_ui(r'''
seed();optimizationView.result={status:'unavailable',reason:'optimization_infeasible_target',assets:[],feasible_return_range:{min_percent:8,max_percent:16}};
for(const language of ['en','he']){
 state.language=language;renderOptimization();assert.ok(target.innerHTML.includes('8.00%'));assert.ok(target.innerHTML.includes('16.00%'));assert.ok(!target.innerHTML.includes('optimization_infeasible_target'));
 for(const code of ['optimization_infeasible_weights','optimization_degenerate_covariance','optimization_infeasible_target','optimization_no_positive_excess_return','optimization_zero_risk_excess_return','optimization_invalid_inputs','optimization_invalid_dimensions','optimization_invalid_covariance','optimization_invalid_objective','optimization_invalid_weight','optimization_target_required','optimization_invalid_frontier','optimization_solver_failed','ineligible_assets','insufficient_common_history','invalid_returns','constant_returns','classification_conflict','unsupported_asset','invalid_position','optimization_unknown_currency']){
  const message=optimizationText(optimizationReason(code));assert.ok(message!==code);if(language==='he')assert.ok(/[א-ת]/.test(message));else assert.ok(!/[א-ת]/.test(message));
 }
 for(const code of ['unadjusted_prices','limited_history','stale_prices','stale_common_history','current_weights_unavailable','singular_covariance']){const message=optimizationText(optimizationWarning(code));if(language==='he')assert.ok(/[א-ת]/.test(message));else assert.ok(!/[א-ת]/.test(message));}
}
''')


def test_calculation_success_failure_preserves_assumptions_and_focus():
    run_ui(r'''
(async()=>{
seed();nodes.optimizationRiskFree.value='2';document.activeElement=nodes.optimizationRun;
const run=runOptimization();assert.equal(optimizationView.calculating,true);assert.equal(nodes.optimizationAccount.disabled,true);assert.equal(pending[0].options.method,'POST');pending[0].resolve(result);await run;assert.equal(optimizationView.calculating,false);assert.equal(document.activeElement.id,'optimizationRun');assert.equal(optimizationView.result.status,'ok');assert.equal(nodes.optimizationRiskFree.value,'2');
const retry=runOptimization();pending[1].reject(new Error('SENSITIVE provider response'));await retry;assert.equal(optimizationView.result,null);assert.equal(nodes.optimizationRiskFree.value,'2');assert.ok(!target.innerHTML.includes('SENSITIVE'));
})();
''')


def test_scope_history_reload_selection_and_override_drafts():
    run_ui(r'''
(async()=>{
seed();datasetInputs.find(node=>node.dataset.optimizationReturn==='a').value='20';optimizationCapture();optimizationView.selected=['a'];optimizationDraft();
const event={target:nodes.optimizationPeriod};event.target.value='1y';for(const listener of listeners.change)listener(event);
assert.equal(pending.length,1);pending[0].resolve({...data,period:'1y'});await new Promise(resolve=>setImmediate(resolve));assert.deepEqual(optimizationView.selected,['a','b']);assert.equal(optimizationView.overrides.a,undefined);
nodes.optimizationPeriod.value='3y';for(const listener of listeners.change)listener({target:nodes.optimizationPeriod});pending[1].resolve(data);await new Promise(resolve=>setImmediate(resolve));assert.deepEqual(optimizationView.selected,['a']);assert.equal(optimizationView.overrides.a,'20');
const reload=loadOptimization();pending[2].reject(new Error('offline'));await reload;assert.deepEqual(optimizationView.selected,['a']);assert.equal(optimizationView.overrides.a,'20');
})();
''')


def test_late_load_or_calculation_cannot_replace_newer_state_or_logout():
    run_ui(r'''
(async()=>{
seed();const first=loadOptimization(),second=loadOptimization();pending[1].resolve(data);await second;pending[0].resolve({...data,assets:[]});await first;assert.equal(optimizationView.data.assets.length,2);
nodes.optimizationRiskFree.value='9';const run=runOptimization();resetOptimization();pending[2].resolve(result);await run;assert.equal(optimizationView.result,null);assert.equal(optimizationView.data,null);assert.deepEqual(optimizationView.selected,[]);assert.equal(optimizationView.config.risk_free_rate_percent,'0');
})();
''')


def test_assumption_and_selection_changes_clear_prior_result():
    run_ui(r'''
seed();optimizationView.result=structuredClone(result);renderOptimization();nodes.optimizationRiskFree.value='3';for(const listener of listeners.input)listener({target:nodes.optimizationRiskFree});assert.equal(optimizationView.result,null);assert.ok(nodes.optimizationStatus.textContent.includes('Inputs changed'));
optimizationView.result=structuredClone(result);const checkbox={dataset:{optimizationAsset:'b'},checked:false};for(const listener of listeners.change)listener({target:checkbox});assert.deepEqual(optimizationView.selected,['a']);assert.equal(optimizationView.result,null);assert.throws(optimizationPayload,/at least two/);
''')


def test_reopening_during_calculation_keeps_pending_operation_recoverable():
    run_ui(r'''
(async()=>{
seed();const run=runOptimization();assert.equal(pending.length,1);await loadOptimization();assert.equal(pending.length,1);assert.equal(optimizationView.calculating,true);pending[0].resolve(result);await run;assert.equal(optimizationView.calculating,false);assert.equal(optimizationView.result.status,'ok');
})();
''')


def test_mobile_weights_have_localized_cell_labels_and_warnings_precede_metrics():
    run_ui(r'''
seed();optimizationView.result=structuredClone(result);
for(const language of ['en','he']){
 state.language=language;renderOptimization();const html=target.innerHTML;
 for(const label of ['Current weight %','Optimized weight %','Change in percentage points'])assert.ok(html.includes('data-label="'+optimizationText(label)+'"'));
 assert.ok(html.includes('class="optimization-weights" role="table"'));assert.ok(html.includes('scope="row" role="rowheader"'));
 assert.ok(html.indexOf(optimizationText(optimizationWarning('unadjusted_prices')))<html.indexOf('class="optimization-kpis"'));
 assert.equal(html.split(optimizationText(optimizationWarning('unadjusted_prices'))).length-1,1);
}
''')



def test_investment_account_selector_rejects_other_and_untyped_accounts():
    run_ui(r'''
const outside=[{id:'esop-only',type:'ESOP',account_id:'Outside employee account'},{id:'bank-only',type:'Bank',account_id:'Outside bank account'},{id:'pension-only',type:'Long-Term Savings',account_id:'Outside pension account'},{id:'unknown-only',account_id:'Outside untyped account'}];
seed();optimizationView.data.accounts.push(...outside);renderOptimization();
const html=target.innerHTML;for(const row of outside)assert.ok(!html.includes(row.account_id));
assert.ok(html.includes('All investment accounts'));
''')


def test_removed_account_clears_old_allocation_and_recovers_to_investments():
    run_ui(r'''
(async()=>{seed();optimizationView.config.account_id='acct-a';optimizationView.overrides={a:999};optimizationView.result=structuredClone(result);const old=loadOptimization();pending[0].reject(new Error('optimization_unknown_account'));await new Promise(resolve=>setImmediate(resolve));assert.equal(optimizationView.config.account_id,'');assert.equal(optimizationView.result,null);assert.equal(optimizationView.data,null);assert.deepEqual(optimizationView.overrides,{});assert.ok(pending[1].path.includes('account_id=&'));pending[1].resolve({...data,accounts:data.accounts.filter(row=>row.id==='acct-b')});await old;assert.equal(optimizationView.data.accounts.length,1);})();
''')
