"""Broker create/edit popup state, save recovery, permissions and localization."""
from pathlib import Path
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def function(name):
    source=(ROOT/'web/app.js').read_text()
    start=re.search(r'(?:async )?function '+name+r'\(',source)
    end=re.search(r'^}',source[start.end():],re.M)
    return source[start.start():start.end()+end.end()]


def run_ui(body):
    names=['loadBrokers','renderBrokersList','setBrokerStatus','saveBroker','clearBrokerForm','renderBrokerEditor','newBroker','editBroker','openModal','closeModal']
    script=r'''
const assert=require('node:assert/strict');const window={};
''' +(ROOT/'web/i18n.js').read_text()+r'''
class HTMLElement{
 constructor(id){this.id=id;this.value='';this.textContent='';this.innerHTML='';this.hidden=true;this.disabled=false;this.isConnected=true;this.dataset={};this.attributes={};this.parentElement={append(){}};}
 closest(selector){return this.parentModal || null;}
 setAttribute(key,value){this.attributes[key]=value;}
 removeAttribute(key){delete this.attributes[key];}
 querySelectorAll(){return this.controls || [];}
 querySelector(){return null;}
 focus(){document.activeElement=this;}
}
class HTMLButtonElement extends HTMLElement{}
const nodes={};for(const id of ['brokerName','brokerComments','brokerCountry','brokerCurrency','brokerStatus','brokerEditorStatus','brokersList','brokerEditorTitle','brokerForm','brokersModal','brokerEditorModal'])nodes[id]=new HTMLElement(id);
for(const id of ['newBroker','saveBroker','cancelBrokerEdit','closeBrokerEdit'])nodes[id]=new HTMLButtonElement(id);
nodes.brokersModal.hidden=false;nodes.brokerEditorModal.controls=[nodes.cancelBrokerEdit,nodes.closeBrokerEdit];nodes.newBroker.parentModal=nodes.brokersModal;
const $=id=>nodes[id];let writer=true;const canWrite=()=>writer;
const state={auth:{user:{id:'operator'}},language:'en',brokers:[{id:'b1',name:'Broker <one>',country:'Israel',currency:'ILS',comments:'Saved notes',attached_accounts:2}],editingBrokerId:'',brokerSaving:false,brokerEditorVersion:0};
const t=value=>window.PortfolioI18n.translate(value,state.language);
const document={activeElement:nodes.newBroker,querySelectorAll(){return []},querySelector(){return nodes.newBroker}};
const modalReturnFocus=new Map();const requestAnimationFrame=fn=>fn();
const mountModalHomeLink=()=>{},focusModalDestination=()=>{},refreshBrokerSelects=()=>{};
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const countryDisplayLabel=v=>v,currencyDisplayLabel=v=>v,normalizeAccountCountry=v=>v,preferredCurrencyForLocation=v=>v==='Israel'?'ILS':'USD';
const fmt=v=>String(v);const valueOf=id=>String(nodes[id]?.value || '').trim();
const pending=[];const api=(path,options={})=>new Promise((resolve,reject)=>pending.push({path,options,resolve,reject}));
'''+'\n'.join(function(n) for n in names)+'\n'+body
    result=subprocess.run(['node'],input=script,text=True,capture_output=True)
    assert result.returncode==0,result.stderr


def test_new_edit_cancel_and_keyboard_focus_keep_parent_context_without_requests():
    run_ui(r'''
editBroker('b1',nodes.newBroker);assert.equal(nodes.brokerName.value,'Broker <one>');assert.equal(nodes.brokerCurrency.value,'ILS');assert.equal(nodes.brokerCountry.value,'Israel');assert.equal(state.editingBrokerId,'b1');assert.equal(nodes.brokerEditorTitle.textContent,'Edit broker');assert.equal(nodes.brokerEditorModal.hidden,false);assert.equal(nodes.brokersModal.inert,true);assert.equal(nodes.brokersModal.attributes['aria-hidden'],'true');assert.equal(document.activeElement,nodes.brokerName);
nodes.brokerName.value='Unsaved';closeModal(nodes.brokerEditorModal);assert.equal(nodes.brokersModal.inert,false);assert.equal(nodes.brokersModal.attributes['aria-hidden'],undefined);assert.equal(document.activeElement,nodes.newBroker);assert.equal(state.brokers[0].name,'Broker <one>');assert.equal(nodes.brokerName.value,'');
newBroker();assert.equal(state.editingBrokerId,'');assert.equal(nodes.brokerCountry.value,'USA');assert.equal(nodes.brokerCurrency.value,'USD');assert.equal(nodes.brokerComments.value,'');assert.equal(nodes.brokerEditorTitle.textContent,'New broker');assert.equal(pending.length,0);
closeModal(nodes.brokerEditorModal);editBroker('deleted');assert.equal(nodes.brokerEditorModal.hidden,true);assert.ok(nodes.brokerStatus.textContent.includes('no longer available'));
''')


def test_pending_save_blocks_duplicate_and_close_then_failure_retains_fields():
    run_ui(r'''
(async()=>{editBroker('b1',nodes.newBroker);nodes.brokerName.value='Changed name';nodes.brokerComments.value='Retained draft';const save=saveBroker();assert.equal(state.brokerSaving,true);assert.equal(nodes.saveBroker.disabled,true);assert.equal(nodes.cancelBrokerEdit.disabled,true);closeModal(nodes.brokerEditorModal);assert.equal(nodes.brokerEditorModal.hidden,false);await saveBroker();assert.equal(pending.length,1);const payload=JSON.parse(pending[0].options.body);assert.equal(payload.id,'b1');assert.equal(payload.name,'Changed name');pending[0].reject(new Error('PRIVATE provider body'));await save;assert.equal(nodes.brokerName.value,'Changed name');assert.equal(nodes.brokerComments.value,'Retained draft');assert.equal(state.brokerSaving,false);assert.equal(nodes.saveBroker.disabled,false);assert.ok(nodes.brokerEditorStatus.textContent.includes('retained'));assert.ok(!nodes.brokerEditorStatus.textContent.includes('PRIVATE'));assert.equal(nodes.brokersModal.inert,true);})();
''')


def test_success_updates_list_closes_popup_and_reports_reload_failure_without_undo():
    run_ui(r'''
(async()=>{newBroker();nodes.brokerName.value='New broker value';const save=saveBroker();const payload=JSON.parse(pending[0].options.body);assert.equal(payload.id,undefined);pending[0].resolve({id:'new',name:'New broker value',country:'USA',currency:'USD',comments:''});await new Promise(r=>setImmediate(r));assert.equal(nodes.brokerEditorModal.hidden,true);assert.equal(nodes.brokersModal.inert,false);assert.ok(nodes.brokersList.innerHTML.includes('New broker value'));assert.equal(pending[1].path,'/api/local/brokers');pending[1].reject(new Error('offline'));await save;assert.equal(state.brokers.length,2);assert.ok(nodes.brokerStatus.textContent.includes('saved, but the list'));})();
''')


def test_viewer_and_validation_do_not_open_editor_or_write():
    run_ui(r'''
(async()=>{writer=false;newBroker();editBroker('b1');await saveBroker();assert.equal(nodes.brokerEditorModal.hidden,true);assert.equal(pending.length,0);renderBrokersList();assert.ok(nodes.brokersList.innerHTML.includes('disabled'));writer=true;newBroker();await saveBroker();assert.equal(pending.length,0);assert.ok(nodes.brokerEditorStatus.textContent.includes('Enter a broker name'));assert.equal(document.activeElement,nodes.brokerName);})();
''')


def test_late_save_and_load_cannot_replace_a_new_session_or_new_editor():
    run_ui(r'''
(async()=>{newBroker();nodes.brokerName.value='Private original';const save=saveBroker();clearBrokerForm();state.auth.user={id:'different'};pending[0].resolve({id:'private',name:'Private original'});await save;assert.equal(nodes.brokerName.value,'');assert.equal(state.brokers.length,1);assert.equal(pending.length,1);const read=loadBrokers();state.auth.user={id:'another'};pending[1].resolve({items:[{id:'old',name:'OLD USER'}]});await read;assert.equal(state.brokers.length,1);assert.ok(!nodes.brokersList.innerHTML.includes('OLD USER'));})();
''')


def test_hebrew_titles_status_actions_and_help_translate_and_escape_names():
    run_ui(r'''
state.language='he';newBroker();assert.ok(/[א-ת]/.test(nodes.brokerEditorTitle.textContent));editBroker('b1',nodes.newBroker);state.brokerEditorMessage='Could not save broker. Your entries are retained. Try again.';renderBrokerEditor();assert.ok(/[א-ת]/.test(nodes.brokerEditorStatus.textContent));assert.ok(!nodes.brokerEditorStatus.textContent.includes('Could not'));renderBrokersList();assert.ok(nodes.brokersList.innerHTML.includes('Broker &lt;one&gt;'));assert.ok(!nodes.brokersList.innerHTML.includes('>Edit<'));assert.ok(!nodes.brokersList.innerHTML.includes('>Remove<'));assert.equal(nodes.brokerCurrency.value,'ILS');
''')
    html=(ROOT/'web/index.html').read_text()
    i18n=(ROOT/'web/i18n.js').read_text()
    listing=html.split('<div id="brokersModal"',1)[1].split('<div id="brokerEditorModal"',1)[0]
    editor=html.split('<div id="brokerEditorModal"',1)[1].split('<div id="familyModal"',1)[0]
    assert 'id="newBroker"' in listing and 'id="brokerName"' not in listing
    assert 'id="brokerForm"' in editor and 'id="brokerName"' in editor
    assert 'id="clearBrokerForm"' not in html
    help_section=html.split('<h3>Brokers</h3>',1)[1].split('</article>',1)[0]
    for text in re.findall(r'<p>(.*?)</p>',help_section):
        assert json.dumps(text,ensure_ascii=False)+':' in i18n
