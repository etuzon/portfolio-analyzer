"""People are listed by default; editors preserve data and prevent duplicate writes."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_people_js(body):
    source = (ROOT / 'web/app.js').read_text()
    names = ('familyMemberById', 'clearFamilyMemberForm', 'familyMemberValidation',
             'renderFamilyMemberEditor', 'setFamilyMemberSaving', 'openFamilyMemberEditor',
             'editFamilyMember', 'saveFamilyMember', 'deleteFamilyMember', 'setFamilyStatus')
    functions = []
    for name in names:
        start = re.search(rf'^(?:async )?function {name}\(', source, re.M).start()
        end = re.search(r'^}', source[start:], re.M).end()
        functions.append(source[start:start + end])
    harness = '''
const assert = require('node:assert/strict');
class Control {
 constructor(id) { this.id=id; this.raw='';this.disabled=false;this.hidden=false;this.attrs={};this.validity={badInput:false};this.isConnected=true; }
 get value() {return this.raw;} set value(value) {this.raw=String(value);}
 setAttribute(key,value) {this.attrs[key]=value;} removeAttribute(key) {delete this.attrs[key];}
 focus() {document.activeElement=this;}
}
const ids=['familyMemberFirstName','familyMemberLastName','familyMemberGender','familyMemberBirthDate',
 'familyMemberRetireAge','familyMemberComments','familyMemberForm','familyMemberModal','familyModal',
 'familyMemberEditorTitle','familyMemberEditorStatus','familyStatus','saveFamilyMember','newFamilyMember'];
const nodes=Object.fromEntries(ids.map(id=>[id,new Control(id)]));
const fields=ids.slice(0,6).map(id=>nodes[id]);
nodes.familyMemberModal.querySelectorAll=()=>[...fields,nodes.saveFamilyMember];
nodes.familyMemberForm.querySelectorAll=()=>fields;
const $=id=>nodes[id];
const document={activeElement:nodes.newFamilyMember};
const requestAnimationFrame=fn=>fn();
let writable=true, closes=0, opens=0, refreshes=0, confirms=0, confirmed=true;
const canWrite=()=>writable;
const window={confirm:()=>{confirms++;return confirmed;}};
const memberLabel=member=>member.first_name;
const state={familyMembers:[{id:'member',first_name:'Dana',last_name:'Levi',gender:'Female',birth_date:'1990-07-31',retire_age:0,comments:'Note',attached_accounts:0}],
 editingFamilyMemberId:'',familyMemberSaving:false,deletingFamilyMemberIds:[]};
const t=value=>value;
const valueOf=id=>nodes[id].value.trim();
const dateValue=id=>/^\\d{2}\\/\\d{2}\\/\\d{4}$/.test(valueOf(id))?valueOf(id).split('/').reverse().join('-'):'';
const setDateField=(id,value)=>{nodes[id].value=value?value.split('-').reverse().join('/'):'';};
const todayString=()=> '2026-10-30';
const openModal=(id,_returnFocus,destination)=>{opens++;nodes[id].hidden=false;nodes[destination.focusId].focus();};
const closeModal=modal=>{closes++;modal.hidden=true;nodes.familyModal.inert=false;};
const renderFamilyMembers=()=>{}, refreshFamilyMemberSelects=()=>{}, refreshReportPersonSelect=()=>{}, renderSimulationPersonOptions=()=>{};
let failRefresh=false;
const loadFamilyMembers=async()=>{refreshes++;if(failRefresh)throw Error('network');};
const loadLocalAccounts=async()=>{refreshes++;};
const requests=[];let api=async(path,options)=>{requests.push({path,options});return {id:'member',...JSON.parse(options.body||'{}')};};
'''
    result = subprocess.run(['node'], input=harness+'\n'.join(functions)+'\n'+body, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_people_default_list_and_labeled_dialog_are_separate():
    html = (ROOT / 'web/index.html').read_text()
    section = html.split('id="familyMembersSection"', 1)[1].split('</section>', 1)[0]
    assert 'id="newFamilyMember"' in section
    assert 'id="familyMembersList"' in section
    assert 'familyMemberFirstName' not in section
    assert 'clearFamilyMemberForm' not in html
    editor = html.split('id="familyMemberModal"', 1)[1].split('id="securitiesModal"', 1)[0]
    assert 'role="dialog" aria-modal="true" aria-labelledby="familyMemberEditorTitle"' in editor
    assert '<form id="familyMemberForm" novalidate>' in editor
    for field in ('FirstName', 'LastName', 'Gender', 'BirthDate', 'RetireAge', 'Comments'):
        assert f'for="familyMember{field}"' in editor


def test_add_edit_optional_values_and_viewer_guards():
    run_people_js('''
const before=JSON.stringify(state.familyMembers);
editFamilyMember('member');
assert.equal(nodes.familyMemberRetireAge.value,'0');
assert.equal(nodes.familyMemberBirthDate.value,'31/07/1990');
assert.equal(nodes.familyMemberEditorTitle.textContent,'Edit person');
assert.equal(nodes.familyModal.inert,true);
assert.equal(document.activeElement,nodes.familyMemberFirstName);
openFamilyMemberEditor();
assert.ok(fields.every(field=>field.value===''),'Add must have no inferred field defaults');
assert.equal(state.editingFamilyMemberId,'');
assert.equal(nodes.familyMemberEditorTitle.textContent,'Add person');
assert.equal(JSON.stringify(state.familyMembers),before);
writable=false;const count=opens;editFamilyMember('member');
assert.equal(opens,count);assert.equal(requests.length,0);
''')


def test_validation_error_retry_and_duplicate_save_preserve_payload():
    run_people_js('''
(async()=>{
 openFamilyMemberEditor();await saveFamilyMember();
 assert.equal(requests.length,0);assert.equal(document.activeElement,nodes.familyMemberFirstName);
 nodes.familyMemberFirstName.value='Dana';nodes.familyMemberBirthDate.value='31/07/1990';
 nodes.familyMemberRetireAge.value='0';nodes.familyMemberComments.value='Keep my note';
 api=async()=>{throw Error('service unavailable');};
 await saveFamilyMember();
 assert.equal(nodes.familyMemberModal.hidden,false);
 assert.equal(nodes.familyMemberComments.value,'Keep my note');
 assert.equal(state.familyMemberSaving,false);
 assert.equal(document.activeElement,nodes.saveFamilyMember);
 let release;
 api=async(path,options)=>{requests.push({path,options});return new Promise(resolve=>{release=resolve;});};
 const pending=saveFamilyMember();await saveFamilyMember();
 assert.equal(requests.length,1);assert.equal(nodes.saveFamilyMember.disabled,true);
 const payload=JSON.parse(requests[0].options.body);
 assert.equal(payload.retire_age,'0');assert.equal(payload.birth_date,'1990-07-31');
 assert.equal(payload.comments,'Keep my note');assert.ok(!Object.hasOwn(payload,'id'));
 failRefresh=true;release({id:'new-person',...payload});await pending;
 assert.equal(requests.length,1);assert.equal(closes,1);assert.equal(refreshes,2);
 assert.equal(state.familyMemberSaving,false);
 assert.ok(nodes.familyStatus.textContent.includes('Person saved.'));
 assert.ok(state.familyMembers.some(member=>member.id==='new-person'));
})().catch(error=>{console.error(error);process.exitCode=1;});
''')


def test_delete_attachment_confirmation_and_duplicate_guards():
    run_people_js('''
(async()=>{
 const member=state.familyMembers[0];member.attached_accounts=1;
 await deleteFamilyMember('member');assert.equal(requests.length,0);assert.equal(confirms,0);
 member.attached_accounts=0;confirmed=false;
 await deleteFamilyMember('member');assert.equal(requests.length,0);assert.equal(state.familyMembers.length,1);
 confirmed=true;let release;
 api=async(path,options)=>{requests.push({path,options});return new Promise(resolve=>{release=resolve;});};
 const pending=deleteFamilyMember('member');await deleteFamilyMember('member');
 assert.equal(requests.length,1);assert.equal(requests[0].options.method,'DELETE');
 release({deleted:true});await pending;
 assert.equal(state.familyMembers.length,0);assert.equal(refreshes,2);
 assert.equal(nodes.familyStatus.textContent,'Person deleted');
 assert.equal(document.activeElement,nodes.newFamilyMember);
})().catch(error=>{console.error(error);process.exitCode=1;});
''')
