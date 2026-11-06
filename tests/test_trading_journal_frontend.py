"""Behavioral journal checks for preserved decisions, reviews and recovery."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    script = r'''
const assert=require('node:assert/strict');
const state={language:'en'};let writer=true;
const canWrite=()=>writer;
const t=text=>text;
const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const decode=s=>String(s??'').replaceAll('&quot;','"').replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&#39;',"'").replaceAll('&amp;','&');
const fmt=(v,n=2)=>Number(v).toFixed(n);
const money=(v,c,n=2)=>`${c} ${Number(v).toFixed(n)}`;
const accountLabel=row=>row.account_id || row.id;
const parseDateInput=value=>{const s=String(value||'');const p=s.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);const iso=p?`${p[3]}-${p[2]}-${p[1]}`:s;if(!/^\d{4}-\d{2}-\d{2}$/.test(iso))return '';const d=new Date(iso+'T00:00:00Z');return Number.isNaN(+d)||d.toISOString().slice(0,10)!==iso?'':iso;};
const formatDate=value=>{const iso=parseDateInput(value);return iso?iso.split('-').reverse().join('/'):value||'';};
const formatDateTime=value=>formatDate(value.slice(0,10))+' 12:00';
const nodes={},listeners={},pending=[];
const document={activeElement:null,addEventListener(type,fn){(listeners[type] ||= []).push(fn);}};
const target={_html:'',get innerHTML(){return this._html},set innerHTML(html){
 this._html=html;for(const id of Object.keys(nodes))if(!['tradingJournalContent','tradingJournalModal'].includes(id))delete nodes[id];
 for(const match of html.matchAll(/<(input|select|textarea|details|p|button|div)\b([^>]*\bid="([^"]+)"[^>]*)>/g)){
  const [,tag,attrs,id]=match;const content=['select','textarea'].includes(tag)?html.slice(match.index+match[0].length).split('</'+tag+'>')[0]:'';
  let value=decode((attrs.match(/\bvalue="([^"]*)"/)||[])[1]||'');
  if(tag==='textarea')value=decode(content);
  if(tag==='select'){const options=[...content.matchAll(/<option\b([^>]*)>(.*?)<\/option>/g)];const selected=options.find(row=>/\bselected\b/.test(row[1]))||options[0];value=decode((selected?.[1].match(/\bvalue="([^"]*)"/)||[])[1]||'');}
  nodes[id]={id,value,checked:/\bchecked\b/.test(attrs),disabled:/\bdisabled\b/.test(attrs),readOnly:/\breadonly\b/.test(attrs),open:/\bopen\b/.test(attrs),textContent:content,innerHTML:content,focus(){document.activeElement=this;},setSelectionRange(start,end){this.selectionStart=start;this.selectionEnd=end;},scrollIntoView(){}};
 }
}};
nodes.tradingJournalContent=target;nodes.tradingJournalModal={hidden:true};const $=id=>nodes[id];
const api=(path,options={})=>new Promise((resolve,reject)=>pending.push({path,options,resolve,reject}));
let opened=0;
const openModal=()=>{opened++;nodes.tradingJournalModal.hidden=false;loadTradingJournal();};
const trade={id:'tx-a',account_id:'a',account_label:'Fixture account',symbol:'AAPL',name:'Apple',stock_market:'NASDAQ',currency:'USD',asset_class:'EQUITY',action:'BUY',trade_date:'2025-01-01',quantity:10,price:100};
const second={...trade,id:'tx-b',symbol:'MSFT',action:'SELL',account_id:'b'};
const entry={id:'tx-a',transaction_id:'tx-a',trade:{...trade},created_at:'2025-01-02T12:00:00Z',updated_at:'2025-01-02T12:00:00Z',revision:1,reason:'Original <reason>',thesis:'Risk <thesis>',review_date:'2025-06-01',reason_history:[{reason:'Original <reason>',thesis:'Risk <thesis>',review_date:'2025-06-01',recorded_at:'2025-01-02T12:00:00Z',author:'Fixture'}],reviews:[],review_status:'pending',link_status:'current',current_trade:{...trade},outcome:{status:'ok',price_change_percent:20,last_price:120,last_price_date:'2025-06-01',currency:'USD'}};
const data={items:[entry],transactions:[trade,second],accounts:[{id:'a',type:'Investment',account_id:'First account'},{id:'b',type:'Investment',account_id:'Second account'}],as_of_date:'2025-06-02'};
function seed(){tradingJournalView.data=structuredClone(data);tradingJournalView.selected='tx-a';tradingJournalDraft();renderTradingJournal();}
function choose(id){tradingJournalCapture();tradingJournalView.selected=id;tradingJournalDraft();renderTradingJournal();}
''' + (ROOT / "web/trading-journal-ui.js").read_text() + "\n" + body
    result = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_locales_safe_history_dates_and_saved_price_evidence():
    run_ui(r'''
seed();
for(const language of ['en','he','en']){
 state.language=language;renderTradingJournal();const html=target.innerHTML;
 assert.ok(html.includes('Original &lt;reason&gt;'));assert.ok(!html.includes('Original <reason>'));
 assert.ok(html.includes('Risk &lt;thesis&gt;'));assert.ok(html.includes('01/01/2025'));assert.ok(html.includes('02/01/2025'));assert.ok(html.includes('+20.00'));
 assert.ok(!html.includes('undefined'));assert.ok(!html.includes('NaN'));assert.ok(html.includes('role="status"'));
 if(language==='he'){assert.ok(html.includes('הסיבה המקורית'));assert.ok(!html.includes('Save review'));assert.ok(!html.includes('Not reviewed'));}
 else{assert.ok(html.includes('Original reason'));assert.ok(!/[א-ת]/.test(html));}
 for(const status of ['ok','stale','no_later_price','unsupported_instrument','invalid_trade_price','link_changed','deleted_transaction']){
  const text=tradingJournalOutcome({...entry,outcome:{...entry.outcome,status}});assert.ok(!text.includes(status));
  if(language==='he')assert.ok(/[א-ת]/.test(text));else assert.ok(!/[א-ת]/.test(text));
 }
}
''')


def test_filter_due_account_action_review_and_free_text():
    run_ui(r'''
seed();tradingJournalView.filters.review='due';assert.equal(tradingJournalFiltered().length,1);
tradingJournalView.filters.account='b';assert.equal(tradingJournalFiltered().length,0);
tradingJournalView.filters.account='a';tradingJournalView.filters.action='SELL';assert.equal(tradingJournalFiltered().length,0);
tradingJournalView.filters.action='BUY';tradingJournalView.filters.query='original';assert.equal(tradingJournalFiltered().length,1);
tradingJournalView.filters.query='not found';assert.equal(tradingJournalFiltered().length,0);
tradingJournalView.filters={account:'',action:'',review:'good',query:''};assert.equal(tradingJournalFiltered().length,0);
tradingJournalView.filters.review='pending';assert.equal(tradingJournalFiltered().length,1);
''')


def test_drafts_are_scoped_and_invalid_fields_do_not_send_writes():
    run_ui(r'''
(async()=>{
 seed();nodes.journalReason.value='Unsaved first trade';nodes.journalThesis.value='First thesis';tradingJournalCapture();
 choose('tx-b');assert.equal(nodes.journalReason.value,'');nodes.journalReason.value='Unsaved second trade';tradingJournalCapture();
 choose('tx-a');assert.equal(nodes.journalReason.value,'Unsaved first trade');assert.equal(nodes.journalThesis.value,'First thesis');
 nodes.journalReviewDate.value='31/02/2025';await saveTradingJournal();assert.equal(pending.length,0);assert.ok(tradingJournalView.message.includes('valid review date'));
 nodes.journalReviewDate.value='';nodes.journalReason.value='  ';await saveTradingJournal();assert.equal(pending.length,0);assert.ok(tradingJournalView.message.includes('Enter why'));
 nodes.journalReason.value='Reason';nodes.journalRating.value='good';nodes.journalReviewNotes.value='';await saveTradingJournal('review');assert.equal(pending.length,0);assert.ok(tradingJournalView.message.includes('lessons'));
})();
''')


def test_conflict_preserves_draft_then_discard_adopts_saved_version_only_on_success():
    run_ui(r'''
(async()=>{
 seed();nodes.journalReason.value='Unsaved corrected reason';nodes.journalReviewDate.value='03/07/2025';
 const save=saveTradingJournal();assert.equal(tradingJournalView.busy,true);assert.equal(nodes.journalTransaction.disabled,true);
 const payload=JSON.parse(pending[0].options.body);assert.equal(payload.expected_revision,1);assert.equal(payload.review_date,'2025-07-03');
 pending[0].reject(new Error('journal_conflict'));await save;
 assert.equal(nodes.journalReason.value,'Unsaved corrected reason');assert.ok(tradingJournalView.message.includes('changed elsewhere'));
 const failed=discardTradingJournalDraft();pending[1].reject(new Error('SENSITIVE raw failure'));await failed;
 assert.equal(nodes.journalReason.value,'Unsaved corrected reason');assert.ok(!target.innerHTML.includes('SENSITIVE'));
 const reloaded=discardTradingJournalDraft();pending[2].resolve({...data,items:[{...entry,revision:2,reason:'New server reason'}]});await reloaded;
 assert.equal(nodes.journalReason.value,'New server reason');assert.equal(tradingJournalDraft().expected_revision,2);
 assert.equal(tradingJournalView.drafts['tx-a'].reason,'New server reason');
})();
''')


def test_review_save_success_reload_failure_keeps_reason_draft_and_clears_saved_review():
    run_ui(r'''
(async()=>{
 seed();nodes.journalReason.value='Unsaved revision';nodes.journalReviewNotes.value='A measured lesson';nodes.journalRating.value='mixed';
 const saving=saveTradingJournal('review');assert.equal(pending[0].path,'/api/local/trading-journal/tx-a/reviews');
 assert.deepEqual(JSON.parse(pending[0].options.body),{expected_revision:1,rating:'mixed',notes:'A measured lesson'});
 const reviewed={...entry,revision:2,review_status:'mixed',reviews:[{rating:'mixed',notes:'A measured lesson',recorded_at:'2025-06-02T12:00:00Z',author:'Fixture'}]};
 pending[0].resolve({entry:reviewed});await new Promise(r=>setImmediate(r));
 assert.equal(pending[1].path,'/api/local/trading-journal');pending[1].reject(new Error('offline'));await saving;
 assert.ok(tradingJournalView.message.startsWith('Saved, but'));assert.equal(nodes.journalReason.value,'Unsaved revision');
 assert.equal(nodes.journalReviewNotes.value,'');assert.equal(nodes.journalRating.value,'');assert.equal(tradingJournalDraft().expected_revision,2);
 assert.equal(tradingJournalView.data.items[0].reviews.length,1);assert.equal(tradingJournalView.data.items[0].review_status,'mixed');
})();
''')


def test_reason_save_retains_original_and_uses_new_revision_after_reload():
    run_ui(r'''
(async()=>{
 seed();nodes.journalReason.value='Revised reason';
 const save=saveTradingJournal();const saved={...entry,reason:'Revised reason',revision:2,reason_history:[...entry.reason_history,{reason:'Revised reason',recorded_at:'2025-06-02T12:00:00Z',author:'Fixture'}]};
 pending[0].resolve({entry:saved});await new Promise(r=>setImmediate(r));pending[1].resolve({...data,items:[saved]});await save;
 assert.equal(tradingJournalView.message,'Saved.');assert.equal(nodes.journalReason.value,'Revised reason');assert.equal(tradingJournalDraft().expected_revision,2);
 assert.ok(target.innerHTML.includes('Original &lt;reason&gt;'));assert.ok(target.innerHTML.includes('Revised reason'));
})();
''')


def test_stale_requests_logout_permissions_and_shortcut_single_load():
    run_ui(r'''
(async()=>{
 openTradingJournal('tx-b');assert.equal(opened,1);assert.equal(pending.length,1);assert.equal(tradingJournalView.selected,'tx-b');
 pending[0].resolve(data);await new Promise(r=>setImmediate(r));assert.equal(nodes.journalTransaction.value,'tx-b');
 const first=loadTradingJournal();const second=loadTradingJournal();pending[2].resolve(data);await second;pending[1].resolve({...data,items:[]});await first;
 assert.equal(tradingJournalView.data.items.length,1);
 const late=loadTradingJournal();resetTradingJournal();pending[3].resolve(data);await late;assert.equal(tradingJournalView.data,null);assert.deepEqual(tradingJournalView.drafts,{});
 seed();writer=false;renderTradingJournal();assert.equal(nodes.journalReason.readOnly,true);assert.equal(nodes.journalRating.disabled,true);
 assert.ok(!target.innerHTML.includes('type="submit"'));await saveTradingJournal();assert.equal(pending.length,4);
})();
''')


def test_changed_deleted_trade_and_localized_machine_errors():
    run_ui(r'''
seed();tradingJournalView.data.items[0].link_status='changed';tradingJournalView.data.items[0].current_trade={...trade,price:150};renderTradingJournal();
assert.ok(target.innerHTML.includes('trade changed'));assert.ok(target.innerHTML.includes('150.0000'));assert.ok(target.innerHTML.includes('100.0000'));
tradingJournalView.data.items[0].link_status='deleted';tradingJournalView.data.transactions=[];renderTradingJournal();assert.ok(target.innerHTML.includes('transaction was deleted'));assert.equal(nodes.journalTransaction.value,'tx-a');
for(const language of ['en','he']){
 state.language=language;
 for(const code of ['journal_conflict','journal_reason_required','journal_invalid_date','journal_invalid_rating','journal_review_notes_required','journal_invalid_transaction','journal_not_found','journal_history_limit','journal_entry_limit']){
  const message=tradingJournalText(tradingJournalFailure(new Error(code),'fallback'));assert.notEqual(message,'fallback');assert.ok(!message.includes(code));
  assert.equal(/[א-ת]/.test(message),language==='he');
 }
}
''')


def test_review_requires_explicit_assessment_and_write_focus_is_restored():
    run_ui(r'''
(async()=>{
 seed();nodes.tradingJournalModal.hidden=false;
 assert.equal(nodes.journalRating.value,'');nodes.journalReviewNotes.value='A lesson';
 await saveTradingJournal('review');assert.equal(pending.length,0);assert.ok(tradingJournalView.message.includes('Choose Good'));
 nodes.journalReason.value='Changed reason';nodes.journalSaveReason.focus();
 const saving=saveTradingJournal();pending[0].reject(new Error('offline'));await saving;
 assert.equal(document.activeElement.id,'journalSaveReason');assert.equal(nodes.journalReason.value,'Changed reason');
 nodes.journalRating.value='bad';nodes.journalReviewNotes.value='A lesson';nodes.journalSaveReview.focus();
 const review=saveTradingJournal('review');pending[1].reject(new Error('offline'));await review;
 assert.equal(document.activeElement.id,'journalSaveReview');
 assert.ok(target.innerHTML.includes('Due for review'));
})();
''')


def test_investment_account_selector_rejects_other_and_untyped_accounts():
    run_ui(r'''
const outside=[{id:'esop-only',type:'ESOP',account_id:'Outside employee account'},{id:'bank-only',type:'Bank',account_id:'Outside bank account'},{id:'pension-only',type:'Long-Term Savings',account_id:'Outside pension account'},{id:'unknown-only',account_id:'Outside untyped account'}];
data.accounts.push(...outside);seed();renderTradingJournal();
const html=target.innerHTML;for(const row of outside)assert.ok(!html.includes(row.account_id));
assert.ok(html.includes('All investment accounts'));
''')


def test_reclassified_journal_account_cannot_reappear_through_captured_trade():
    run_ui(r'''
(async()=>{seed();const privateTrade={...trade,id:'tx-outside',account_id:'esop',account_label:'Excluded employee account'};const privateEntry={...entry,id:'tx-outside',trade:privateTrade,reason:'PRIVATE employee reasoning'};tradingJournalView.selected=privateTrade.id;tradingJournalView.drafts[privateTrade.id]={reason:'PRIVATE excluded draft'};tradingJournalView.filters.account='esop';const load=loadTradingJournal();pending[0].resolve({...data,accounts:[...data.accounts,{id:'esop',type:'ESOP',account_id:'Excluded employee account'}],transactions:[...data.transactions,privateTrade],items:[...data.items,privateEntry]});await load;assert.equal(tradingJournalView.filters.account,'');assert.equal(tradingJournalView.selected,'');assert.ok(!tradingJournalView.drafts['tx-outside']);assert.ok(tradingJournalView.drafts['tx-a']);assert.ok(!target.innerHTML.includes('PRIVATE'));assert.ok(!target.innerHTML.includes('Excluded employee account'));})();
''')


def test_recorded_trade_picker_is_visible_scrollable_and_retains_selection_and_scroll():
    run_ui(r'''
seed();
assert.ok(target.innerHTML.includes('id="journalTransaction" size="6"'));
assert.equal(nodes.journalTransaction.value,'tx-a');
nodes.journalTransaction.scrollTop=84;
nodes.journalTransaction.value='tx-b';
for(const handler of listeners.change)handler({target:nodes.journalTransaction});
assert.equal(tradingJournalView.selected,'tx-b');
assert.equal(nodes.journalTransaction.value,'tx-b');
assert.equal(nodes.journalTransaction.scrollTop,84);
assert.ok(nodes.journalReason);
tradingJournalView.selected='';renderTradingJournal();
assert.equal(nodes.journalTransaction.value,'');
assert.ok(target.innerHTML.includes('<option value="" selected>'));
state.language='he';renderTradingJournal();
assert.ok(target.innerHTML.includes('בחירת עסקה רשומה'));
assert.ok(target.innerHTML.includes('id="journalTransaction" size="6"'));
tradingJournalView.busy=true;renderTradingJournal();
assert.equal(nodes.journalTransaction.disabled,true);
''')
