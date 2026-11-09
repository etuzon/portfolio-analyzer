"""Independent behavior checks for instrument browsing and editor recovery."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    source = (ROOT / 'web/app.js').read_text()
    names = ['filteredManualSecurities', 'renderManualSecuritiesList', 'loadManualSecurities',
             'clearManualSecurityForm', 'newManualSecurity', 'editManualSecurity',
             'saveManualSecurity', 'persistManualSecurity', 'applyInstrumentToForm', 'openModal', 'closeModal']
    functions = []
    for name in names:
        match = re.search(r'(?:async )?function ' + name + r'\([^\n]*\)[^{\n]*\{[\s\S]*?\n}', source)
        assert match, name
        functions.append(match.group())
    harness = r'''
const assert=require('node:assert/strict');
class HTMLElement {constructor(id){this.id=id;this.value='';this.hidden=false;this.disabled=false;this.dataset={};this.isConnected=true;this.attributes={};this.parentElement={append(){}};this.classList={};} closest(){return this.parentModal||null} setAttribute(k,v){this.attributes[k]=v} removeAttribute(k){delete this.attributes[k]} querySelector(){return null} focus(){document.activeElement=this}}
const nodes=new Proxy({}, {get(target,key){return target[key] ||= new HTMLElement(key)}});const $=id=>nodes[id];
const document={activeElement:null,querySelectorAll(){return []},querySelector(){return null}};
const state={language:'en',manualSecurities:[],localAccounts:[],editingManualSecurityId:'',auth:{user:{role:'Operator'}}};
const canWrite=()=>state.auth.user.role==='Operator';const modalReturnFocus=new Map();const requestAnimationFrame=fn=>fn();const mountModalHomeLink=()=>{};const focusModalDestination=()=>{};
const SUPPORTED_MANAGEMENT_CURRENCIES=['USD','ILS','EUR'];const optionLabel=x=>x;const t=x=>x;const esc=x=>String(x??'').replaceAll('<','&lt;').replaceAll('"','&quot;');const fmt=(x,d)=>Number(x).toFixed(d);const money=fmt;const formatDate=x=>x;const currencyDisplayLabel=x=>x;
let loadLocalAccounts=async()=>{};let loadLocalSecurities=async()=>{};const toggleTransactionCompFields=()=>{};const loadEmployeeOptionGrants=async()=>{};const employeeOptionsWorkflowActive=()=>Boolean(state.employeeMode);const manualSecurityAttachmentRows=()=>[];const toggleManualInstrumentFields=()=>{};const refreshManualSecuritySelects=()=>{};const loadPortfolio=async()=>{};const cleanSecuritySymbol=x=>String(x||'').trim().toUpperCase();const valueOf=id=>$(id).value;const dateValue=valueOf;const setDateField=(id,v)=>{$(id).value=v};const setCompanyLocationOptions=()=>{};const instrumentById=id=>state.manualSecurities.find(x=>x.id===id);
let wizard='';const setSecuritiesWorkflow=workflow=>{wizard=workflow};const editEmployeeOptionGrant=id=>{wizard+=':'+id};
const pending=[];const api=(path,options={})=>new Promise((resolve,reject)=>pending.push({path,options,resolve,reject}));
const items=[{id:'a',name:'Alpha',symbol:'ZZZ',secondary_symbol:'ALT',instrument_type:'STOCK',currency:'USD'}, {id:'b',name:'Beta',symbol:'AAA',instrument_type:'MUTUALFUND',currency:'USD'}, {id:'c',name:'Gamma',symbol:'CCC',instrument_type:'OPTION',currency:'USD'}, {id:'d',name:'Delta',symbol:'ESO',company_name:'Employer',grant_id:'G-77',instrument_type:'EMPLOYEE_STOCK_OPTION',currency:'USD'}];
function seed(){state.manualSecurities=structuredClone(items);$('instrumentEditorModal').hidden=true;$('securitiesModal').hidden=true;$('instrumentCatalogModal').hidden=false;$('newManualSecurity').parentModal=$('instrumentCatalogModal');document.activeElement=$('newManualSecurity');$('manualSecurityCurrency').value='USD';$('manualInstrumentType').value='STOCK';}
''' + '\n'.join(functions) + '\n' + body
    result = subprocess.run(['node'], input=harness, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_loaded_instruments_filter_and_sort_without_requests_or_source_mutation():
    run_ui(r'''
seed();const before=JSON.stringify(state.manualSecurities);
const ids=(q='',type='',sort='name',dir='asc')=>filteredManualSecurities(state.manualSecurities,q,type,sort,dir).map(x=>x.id);
assert.deepEqual(ids(),['a','b','d','c']);assert.deepEqual(ids('','','name','desc'),['c','d','b','a']);
assert.deepEqual(ids('','','symbol','asc'),['b','c','d','a']);assert.deepEqual(ids('','','symbol','desc'),['a','d','c','b']);
assert.deepEqual(ids('','','type','asc'),['d','b','c','a']);assert.deepEqual(ids('','','type','desc'),['a','c','b','d']);
for(const query of [' alpha ','zzz','alt'])assert.deepEqual(ids(query),['a']);
for(const query of ['g-77','employer'])assert.deepEqual(ids(query),['d']);
assert.deepEqual(ids('','OPTION'),['c']);assert.deepEqual(ids('alpha','OPTION'),[]);
assert.deepEqual(ids('unknown'),[]);assert.equal(pending.length,0);assert.equal(JSON.stringify(state.manualSecurities),before);
$('manualSecurityQuery').value='missing';renderManualSecuritiesList();assert.match($('manualSecuritiesList').innerHTML,/No instruments match/);assert.match($('manualSecurityListStatus').textContent,/0 \/ 4/);assert.equal(pending.length,0);
''')


def test_new_edit_cancel_and_employee_grant_route_preserve_identity_and_focus():
    run_ui(r'''
seed();newManualSecurity();assert.equal($('instrumentEditorModal').hidden,false);assert.equal($('instrumentCatalogModal').inert,true);assert.equal($('instrumentCatalogModal').attributes['aria-hidden'],'true');assert.equal(document.activeElement.id,'manualSecuritySymbol');
$('manualSecurityName').value='Unsaved draft';closeModal($('instrumentEditorModal'));assert.equal(pending.length,0);assert.equal($('instrumentEditorModal').hidden,true);assert.equal($('instrumentCatalogModal').inert,false);assert.equal(document.activeElement.id,'newManualSecurity');
const edit=new HTMLElement('edit-a');edit.parentModal=$('instrumentCatalogModal');document.activeElement=edit;editManualSecurity('a');assert.equal(state.editingManualSecurityId,'a');assert.equal($('manualSecuritySymbol').value,'ZZZ');assert.equal($('manualSecurityName').value,'Alpha');assert.equal(document.activeElement.id,'manualSecurityName');closeModal($('instrumentEditorModal'));assert.equal(document.activeElement,edit);
editManualSecurity('d');assert.equal(wizard,'employee-options');assert.equal($('instrumentCatalogModal').hidden,true);assert.equal($('securitiesModal').hidden,false);assert.equal($('instrumentEditorModal').hidden,true);
state.auth.user.role='Viewer';newManualSecurity();editManualSecurity('a');assert.equal($('instrumentEditorModal').hidden,true);
''')


def test_failed_save_and_failed_refresh_retain_form_and_allow_safe_retry():
    run_ui(r'''
(async()=>{seed();newManualSecurity();$('manualSecurityName').value='Retained draft';$('manualSecuritySymbol').value='NEW';
const failed=saveManualSecurity();assert.equal($('saveManualSecurity').disabled,true);assert.equal(pending.length,1);closeModal($('instrumentEditorModal'));assert.equal($('instrumentEditorModal').hidden,false);pending[0].reject(Error('fixture failure'));await assert.rejects(failed);assert.equal($('manualSecurityName').value,'Retained draft');assert.equal($('saveManualSecurity').disabled,false);assert.equal($('instrumentEditorModal').hidden,false);
const refreshFailure=saveManualSecurity();pending[1].resolve({id:'saved-1',symbol:'NEW'});await Promise.resolve();assert.equal(pending[2].path,'/api/local/manual-securities');pending[2].reject(Error('fixture refresh failure'));await assert.rejects(refreshFailure);assert.equal(state.editingManualSecurityId,'saved-1');assert.equal($('manualSecurityName').value,'Retained draft');assert.equal($('instrumentEditorModal').hidden,false);
const retry=saveManualSecurity();assert.equal(JSON.parse(pending[3].options.body).id,'saved-1');pending[3].resolve({id:'saved-1',symbol:'NEW'});await Promise.resolve();pending[4].resolve({items:[...items,{id:'saved-1',symbol:'NEW',name:'Retained draft',instrument_type:'STOCK'}]});await retry;assert.equal(state.manualSecurities.length,5);assert.equal($('instrumentEditorModal').hidden,true);assert.equal($('instrumentCatalogModal').inert,false);assert.equal(document.activeElement.id,'newManualSecurity');})();
''')


def test_duplicate_save_clicks_and_read_only_save_do_not_create_requests():
    run_ui(r'''
(async()=>{seed();newManualSecurity();const first=saveManualSecurity();const second=saveManualSecurity();await second;assert.equal(pending.length,1);pending[0].reject(Error('failure'));await assert.rejects(first);state.auth.user.role='Viewer';await saveManualSecurity();assert.equal(pending.length,1);})();
''')


def test_catalog_use_prefills_only_after_transaction_dependencies_finish():
    run_ui(r'''
(async()=>{
seed();state.manualSecurities[0].stock_market='NYSE';state.manualSecurities[0].asset_class='EQUITY';
let finishLoad;
loadLocalSecurities=()=>new Promise(resolve=>{finishLoad=()=>{$('securityKnownInstrument').value='';$('securitySymbol').value='';resolve();};});
$('securityKnownInstrument').value='';
openModal('securitiesModal',null,{instrumentId:'a'});
assert.equal($('securityKnownInstrument').value,'');
finishLoad();await new Promise(resolve=>setImmediate(resolve));
assert.equal($('securityKnownInstrument').value,'a');assert.equal($('securitySymbol').value,'ZZZ');assert.equal($('securityMarket').value,'NYSE');assert.equal($('securityAssetClass').value,'EQUITY');assert.equal(document.activeElement.id,'securityQuantity');
})();
''')


def test_late_catalog_destination_cannot_overwrite_a_newer_transaction_opening():
    run_ui(r'''
(async()=>{
seed();const loads=[];
loadLocalSecurities=()=>new Promise((resolve,reject)=>loads.push({resolve,reject}));
openModal('securitiesModal',null,{instrumentId:'a'});
closeModal($('securitiesModal'));
openModal('securitiesModal',null,{instrumentId:'b'});
loads[1].resolve();await new Promise(resolve=>setImmediate(resolve));
assert.equal($('securityKnownInstrument').value,'b');assert.equal($('securitySymbol').value,'AAA');
loads[0].resolve();await new Promise(resolve=>setImmediate(resolve));
assert.equal($('securityKnownInstrument').value,'b');assert.equal($('securitySymbol').value,'AAA');
// A superseded request failure must not publish an error in a fresh dialog.
openModal('securitiesModal',null,{instrumentId:'a'});
closeModal($('securitiesModal'));
openModal('securitiesModal',null,{instrumentId:'b'});
loads[3].resolve();await new Promise(resolve=>setImmediate(resolve));
$('securityStatus').textContent='newer request';loads[2].reject(Error('superseded'));await new Promise(resolve=>setImmediate(resolve));
assert.equal($('securityStatus').textContent,'newer request');assert.equal($('securityKnownInstrument').value,'b');
})();
''')


def test_late_catalog_grant_destination_cannot_open_the_previous_grant_editor():
    run_ui(r'''
(async()=>{
seed();state.employeeMode=true;const loads=[];
loadLocalSecurities=()=>new Promise(resolve=>loads.push(resolve));
openModal('securitiesModal',null,{employeeOptionSecurityId:'grant-a'});
closeModal($('securitiesModal'));
openModal('securitiesModal',null,{employeeOptionSecurityId:'grant-b'});
loads[1]();await new Promise(resolve=>setImmediate(resolve));assert.equal(wizard,':grant-b');
loads[0]();await new Promise(resolve=>setImmediate(resolve));assert.equal(wizard,':grant-b');
})();
''')


def test_transaction_and_employee_loading_failures_use_actionable_summaries():
    run_ui(r'''
(async()=>{
seed();loadLocalSecurities=async()=>{throw Error('raw provider or account details');};
openModal('securitiesModal');await new Promise(resolve=>setImmediate(resolve));
assert.equal($('securityStatus').textContent,'Could not load transactions. Reopen Transactions to retry.');
state.employeeMode=true;
openModal('securitiesModal');await new Promise(resolve=>setImmediate(resolve));
assert.equal($('employeeOptionListStatus').textContent,'Could not load employee option grants. Reopen Employee Stock Options to retry.');
})();
''')
