"""Manual agency records are explicit, reversible and protected from old reads."""
import json
from pathlib import Path
import re
import subprocess

from test_holdings_credit_ratings_frontend import run_ui as run_summary_ui


ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    app = (ROOT / "web/app.js").read_text()
    helpers = []
    for name in ("parseDateInput", "validIsoDate"):
        start = app.index(f"function {name}(")
        end = start + re.search(r"^}", app[start:], re.M).end()
        helpers.append(app[start:end])
    ids = re.findall(r'id="((?:manualCredit|saveManualCredit|clearManualCredit|cancelManualCredit|reloadManualCredit)[^"]*)"', (ROOT / "web/index.html").read_text())
    setup = r'''
state.auth.user.role='Operator';
function todayString(){return '2026-11-13'}
function formatDateTime(value){return `${formatDate(value.slice(0,10))} ${value.slice(11,16)}`}
for(const id of FORM_IDS){const node=$(id);node.id=id;node.value='';node.focus=()=>{document.activeElement=node};node.scrollIntoView=()=>{};}
function baseContext(extra={}){
 const retrieved=context().ratings;
 return context('ACME','A3',{summary_only:false,identity_token:'a'.repeat(64),manual_revisions:{moodys:0,sp:0,fitch:0},
 manual_policy:{scale:'global',term:'long_term',canonical_issuer_name:'Example Company',issuer_identity_verified:true,issue_rating_allowed:false},
 manual_ratings:[],retrieved_ratings:retrieved,...extra});
}
function manualContext(rating='A2',revision=1,extra={}){
 const base=baseContext();
 const manual={agency:'moodys',status:'rated',rating,outlook:'unknown',watch:'unknown',scope:'issuer',scale:'global',term:'long_term',
  rating_type:'issuer',entity_name:'Example Company',rating_date:null,outlook_date:null,watch_date:null,source_url:null,notes:'Operator statement',
  manual_override:true,source_kind:'manual',verification_status:'user_entered',identity_verification:'verified_identity',
  created_at:'2026-11-01T08:00:00Z',updated_at:'2026-11-13T09:30:00Z',updated_by:'synthetic-editor',revision,fetched_at:null,...extra};
 return {...base,manual_revisions:{moodys:revision,sp:0,fitch:0},manual_ratings:[manual],ratings:[manual,...base.retrieved_ratings.filter(row=>row.agency!=='moodys')]};
}
function prepare(context=baseContext()){const entry=creditRatingsEntry();entry.context=context;$('securityCreditRatings').hidden=false;return entry}
function change(id,value){const input=$(id);input.value=value;updateManualCreditDraft(input,true)}
function validDraft(){change('manualCreditGrade','A2');change('manualCreditNotes','A statement checked by the portfolio editor')}
'''.replace("FORM_IDS", json.dumps(ids))
    run_summary_ui("\n".join(helpers) + "\n" + (ROOT / "web/manual-credit-ratings.js").read_text() + "\n" + setup + "\n" + body)


def test_new_entry_does_not_copy_retrieved_grade_outlook_or_dates_and_keeps_agency_drafts():
    run_ui(r'''
const entry=prepare();openManualCreditRating('moodys');
assert.equal(entry.manual.values.rating,'');assert.equal(entry.manual.values.outlook,'unknown');assert.equal(entry.manual.values.watch,'unknown');
for(const field of ['rating_date','outlook_date','watch_date'])assert.equal(entry.manual.values[field],'');
assert.equal(entry.manual.values.entity_name,'Example Company');assert.equal($('manualCreditEntity').readOnly,true);
assert.equal(entry.manual.expectedIdentity,'a'.repeat(64));assert.equal(entry.manual.expectedRevision,0);
assert.equal($('manualCreditEditor').hidden,false);assert.equal(document.activeElement.id,'manualCreditStatus');assert.equal(requests.length,0);
validDraft();openManualCreditRating('sp');assert.equal(entry.manual.values.rating,'');openManualCreditRating('moodys');assert.equal(entry.manual.values.rating,'A2');
assert.equal(entry.manual.values.notes,'A statement checked by the portfolio editor');
const empty=prepare(baseContext({manual_policy:{scale:'global',term:'long_term',canonical_issuer_name:null,issuer_identity_verified:false,issue_rating_allowed:false}}));
empty.manual=null;empty.manualDrafts={};openManualCreditRating('fitch');assert.equal(empty.manual.values.entity_name,'');assert.equal($('manualCreditEntity').readOnly,false);
assert.ok($('manualCreditEntityHint').textContent.includes('Manual identity'));
''')


def test_native_grade_controls_and_options_remain_ltr_in_hebrew():
    html = (ROOT / "web/index.html").read_text()
    assert re.search(r'<select\b[^>]*id="manualCreditGrade"[^>]*dir="ltr"', html)
    run_ui(r'''
state.language='he';prepare();
for(const [agency,grade] of [['sp','BBB+'],['sp','AA-'],['moodys','Aa2']]){
 openManualCreditRating(agency);change('manualCreditGrade',grade);
 assert.equal($('manualCreditGrade').value,grade);
 assert.ok($('manualCreditGrade').innerHTML.includes(`<option value="${grade}" dir="ltr">${grade}</option>`));
}
''')


def test_status_and_signal_changes_clear_inactive_fields_without_inventing_dates():
    run_ui(r'''
const entry=prepare();openManualCreditRating('moodys');validDraft();
change('manualCreditOutlook','stable');change('manualCreditOutlookDate','12/11/2026');change('manualCreditWatch','negative');change('manualCreditWatchDate','11/11/2026');
change('manualCreditRatingDate','10/11/2026');change('manualCreditStatus','unrated');
assert.equal(entry.manual.values.rating,'');assert.equal(entry.manual.values.outlook,'unknown');assert.equal(entry.manual.values.watch,'unknown');
assert.equal(entry.manual.values.outlook_date,'');assert.equal(entry.manual.values.watch_date,'');assert.equal(entry.manual.values.rating_date,'10/11/2026');
assert.equal($('manualCreditActiveFields').hidden,true);assert.equal($('manualCreditGrade').disabled,true);assert.equal($('manualCreditOutlookDateField').hidden,true);
change('manualCreditStatus','rated');assert.equal(entry.manual.values.outlook,'unknown');assert.equal(entry.manual.values.rating,'');
change('manualCreditOutlook','positive');change('manualCreditOutlookDate','12/11/2026');change('manualCreditOutlook','unknown');assert.equal(entry.manual.values.outlook_date,'');
change('manualCreditWatch','none');change('manualCreditWatchDate','12/11/2026');change('manualCreditWatch','unknown');assert.equal(entry.manual.values.watch_date,'');
''')


def test_fixed_income_scope_is_explicit_and_exact_issue_requires_policy_permission():
    run_ui(r'''
state.securityDetail.asset_class='FIXED_INCOME';const entry=prepare();openManualCreditRating('moodys');
assert.equal(entry.manual.isBond,true);assert.equal(entry.manual.values.scope,'issuer');assert.ok($('manualCreditScope').innerHTML.includes('Issuer fallback'));
assert.ok(!$('manualCreditScope').innerHTML.includes('Exact debt issue'));entry.manual.values.scope='issue';assert.ok(manualCreditValidation(entry.manual)[0].includes('supported rating scope'));
entry.manual=null;entry.manualDrafts={};entry.context=baseContext({manual_policy:{...entry.context.manual_policy,issue_rating_allowed:true}});openManualCreditRating('moodys');
assert.equal(entry.manual.values.scope,'');assert.ok($('manualCreditScope').innerHTML.includes('Exact debt issue'));change('manualCreditScope','issue');validDraft();assert.equal(manualCreditValidation(entry.manual),null);
''')


def test_validation_preserves_unknowns_and_rejects_wrong_agency_dates_or_credentials():
    run_ui(r'''
(async()=>{
const entry=prepare();openManualCreditRating('moodys');
await persistManualCreditRating();assert.equal(requests.length,0);assert.ok(entry.manual.message.includes('agency’s list'));
validDraft();entry.manual.values.rating='AAA';assert.ok(manualCreditValidation(entry.manual)[0].includes('agency’s list'));
entry.manual.values.rating='A2';change('manualCreditRatingDate','14/11/2026');await persistManualCreditRating();assert.equal(requests.length,0);assert.ok(entry.manual.message.includes('no later than today'));
change('manualCreditRatingDate','');change('manualCreditSource','https://example.org/?api_key=private');await persistManualCreditRating();assert.equal(requests.length,0);assert.ok(entry.manual.message.includes('without credentials'));
change('manualCreditSource','http://example.org/source');assert.ok(manualCreditValidation(entry.manual)[0].includes('HTTPS'));
change('manualCreditSource','');entry.manual.values.outlook_date='12/11/2026';assert.ok(manualCreditValidation(entry.manual)[0].includes('known outlook'));
entry.manual.values.outlook_date='';entry.manual.values.status='withdrawn';entry.manual.values.rating='A2';assert.ok(manualCreditValidation(entry.manual)[0].includes('Unrated and Withdrawn'));
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_save_is_revision_bound_whole_override_and_wins_over_old_overview_and_table_reads():
    run_ui(r'''
(async()=>{
const entry=prepare();const first=mount(),second=mount();const batch=loadHoldingsCreditRatings([row('ACME')]);const oldRead=loadSecurityCreditRatings(entry);
openManualCreditRating('moodys');validDraft();const saving=persistManualCreditRating();
const put=requests.at(-1);assert.equal(put.options.method,'PUT');assert.equal(put.path,'/api/securities/credit-ratings/manual');
const payload=JSON.parse(put.options.body);assert.equal(payload.security_key,'ACME|NASDAQ|USD');assert.equal(payload.expected_identity,'a'.repeat(64));assert.equal(payload.expected_revision,0);
assert.equal(payload.rating,'A2');assert.equal(payload.outlook,'unknown');assert.equal(payload.watch,'unknown');assert.equal(payload.rating_date,null);assert.equal(payload.outlook_date,null);assert.equal(payload.watch_date,null);
await persistManualCreditRating();assert.equal(requests.length,3,'duplicate save must not create another write');
put.resolve(manualContext());await saving;
requests[1].resolve(baseContext());requests[0].resolve({summary_only:true,items:[baseContext()],not_found_keys:[]});await Promise.all([batch,oldRead]);
assert.equal(entry.context.ratings[0].rating,'A2');assert.equal(entry.context.ratings[0].outlook,'unknown');assert.equal(entry.context.retrieved_ratings[0].rating,'A3');assert.equal(entry.context.retrieved_ratings[0].outlook,'stable');
assert.ok(first.innerHTML.includes('A2'));assert.ok(first.innerHTML.includes('Manual'));assert.equal(first.innerHTML,second.innerHTML);
assert.equal(entry.manual.expectedRevision,1);assert.ok(entry.manual.message.includes('Manual rating saved'));
const manualRow=$('securityCreditRatingsRows').innerHTML.match(/^<tr>[\s\S]*?<\/tr>/)[0];
assert.ok(!manualRow.includes('>Verified rating</span></div>'),'the manual row must not acquire retrieved verification styling');
const original=manualRow.slice(manualRow.indexOf('manual-credit-retrieved-facts'));
assert.ok(original.includes('>A3<'));assert.ok(original.includes('>Stable<'));assert.ok(original.includes('>Unknown<'));
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_clear_is_distinct_from_blank_save_and_restores_retrieved_freshness_and_tombstone():
    run_ui(r'''
(async()=>{
const saved=manualContext();saved.retrieved_ratings[0].stale=true;const entry=prepare(saved);const button=mount();openManualCreditRating('moodys');
assert.equal(entry.manual.values.rating,'A2');change('manualCreditGrade','');await persistManualCreditRating();assert.equal(requests.length,0,'blank grade is not a clear operation');
const clearing=persistManualCreditRating(true);const request=requests[0];assert.equal(request.options.method,'DELETE');
const params=new URL(request.path,'https://example.org').searchParams;assert.equal(params.get('expected_revision'),'1');assert.equal(params.get('expected_identity'),'a'.repeat(64));
const restored={...baseContext(),manual_revisions:{moodys:2,sp:0,fitch:0}};restored.ratings[0].stale=true;restored.retrieved_ratings[0].stale=true;
request.resolve(restored);await clearing;
assert.equal(entry.manual,null);assert.equal(entry.context.manual_ratings.length,0);assert.equal(entry.context.ratings[0].rating,'A3');assert.equal(entry.context.ratings[0].outlook,'stable');
assert.equal(entry.context.ratings[0].stale,true);assert.ok(button.innerHTML.includes('A3'));assert.ok(!button.innerHTML.includes('>Manual<'));
openManualCreditRating('moodys');assert.equal(entry.manual.expectedRevision,2);assert.equal(entry.manual.values.rating,'');
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_conflict_reload_retains_draft_and_identity_change_requires_a_new_entry():
    run_ui(r'''
(async()=>{
const entry=prepare();openManualCreditRating('moodys');validDraft();const saving=persistManualCreditRating();
requests[0].reject(Object.assign(Error('manual_rating_conflict'),{status:409}));await saving;
assert.equal(entry.manual.values.rating,'A2');assert.equal(entry.manual.needsReload,true);assert.equal($('saveManualCreditRating').disabled,true);
change('manualCreditNotes','Updated local draft');assert.ok(entry.manual.message.includes('Reload saved ratings'),'editing keeps the required conflict recovery visible');
const reloading=reloadManualCreditRating();requests[1].resolve(manualContext('Baa1',3));await reloading;
assert.equal(entry.manual.values.rating,'A2');assert.equal(entry.manual.expectedRevision,3);assert.equal(entry.manual.needsReload,false);assert.ok(entry.manual.message.includes('Review your draft'));
const next=persistManualCreditRating();assert.equal(JSON.parse(requests[2].options.body).expected_revision,3);requests[2].reject(Object.assign(Error('security_identity_changed'),{status:409}));await next;
const identityReload=reloadManualCreditRating();requests[3].resolve(baseContext({identity_token:'b'.repeat(64)}));await identityReload;
assert.equal(entry.manual.values.rating,'A2');assert.equal(entry.manual.identityChanged,true);assert.equal($('saveManualCreditRating').disabled,true);assert.ok(entry.manual.message.includes('start a new entry'));
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_reloading_cannot_switch_agencies_or_leave_a_retained_draft_permanently_busy():
    run_ui(r'''
(async()=>{
const entry=prepare();openManualCreditRating('moodys');validDraft();const editor=entry.manual;editor.needsReload=true;
const reload=reloadManualCreditRating();assert.equal(editor.reloading,true);openManualCreditRating('sp');assert.equal(entry.manual,editor);
requests[0].resolve(baseContext());await reload;assert.equal(editor.reloading,false);openManualCreditRating('sp');assert.equal(entry.manual.agency,'sp');
openManualCreditRating('moodys');assert.equal(entry.manual.values.rating,'A2');
const interrupted=reloadManualCreditRating();entry.manual=null;requests[1].resolve(baseContext());await interrupted;assert.equal(editor.reloading,false,'even a dismissed editor releases its captured reload flag');
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_background_identity_change_preserves_the_draft_and_requires_a_new_entry():
    run_ui(r'''
const entry=prepare();openManualCreditRating('moodys');validDraft();const editor=entry.manual;
const values=JSON.stringify(editor.values);
entry.context=baseContext({identity_token:'b'.repeat(64),manual_policy:{scale:'global',term:'long_term',canonical_issuer_name:'New Canonical Company',issuer_identity_verified:true,issue_rating_allowed:false}});
renderSecurityCreditRatings();
assert.equal(editor.identityChanged,true);assert.equal(JSON.stringify(editor.values),values,'a background identity read must not rewrite the draft');
assert.equal($('saveManualCreditRating').disabled,true);assert.equal($('clearManualCreditRating').disabled,true);
assert.ok($('manualCreditEditorStatus').textContent.includes('start a new entry'));
change('manualCreditNotes','Preserved after identity update');assert.ok($('manualCreditEditorStatus').textContent.includes('start a new entry'));
''')


def test_manual_provenance_and_unknown_reasons_are_localized_without_claiming_agency_verification():
    run_ui(r'''
for(const language of ['he','en']){
 state.language=language;const context=manualContext(null,1,{status:'unrated',notes:'My <script>note</script>',identity_verification:'user_entered',stale:true,outlook_stale:true});
 const html=creditRatingsRows(context),first=html.match(/^<tr>[\s\S]*?<\/tr>/)[0];
 assert.ok(!first.includes('Verified rating'));assert.ok(!first.includes('The source explicitly identifies this entity as unrated.'));assert.ok(!first.includes('<script>'));assert.ok(first.includes('&lt;script&gt;'));
 const compact=holdingsCreditRatingsContent({state:'ready',context});
 if(language==='he'){
  for(const label of ['ידני','ללא דירוג','זהות ידנית','רשומה ידנית ישנה','אסמכתאות דירוג שאוחזרו','עודכן על ידי'])assert.ok(first.includes(label),label);
  assert.ok(!/\b(?:Manual|Unrated|Verified|Retrieved|Updated by)\b/.test(first));assert.ok(compact.includes('ידני'));
 }else{assert.ok(first.includes('Manual'));assert.ok(first.includes('Old manual entry'));assert.ok(!/[א-ת]/.test(first));}
 const empty=baseContext({ratings:['moodys','sp','fitch'].map(agency=>({agency,status:'not_checked',outlook:'unknown',watch:'unknown'})),retrieved_ratings:['moodys','sp','fitch'].map(agency=>({agency,status:'not_checked'})),provider_status:[{configured:false,status:'not_configured'}]});
 const reason=creditRatingsAvailability(empty,true);assert.ok(reason.includes(t('No retrieved rating checks are saved. Unknown does not mean Unrated.')));assert.ok(reason.includes(t('Choose Refresh ratings to research public sources, or Add manually to record your own information.')));
 assert.ok(reason.includes(t('Ratings use public-source AI research. An available AI connection and Internet search are required; no licensed rating API is required.')));
}
''')


def test_viewer_and_session_guards_prevent_writes_and_late_old_user_results():
    run_ui(r'''
(async()=>{
const entry=prepare();state.auth.user.role='Viewer';openManualCreditRating('moodys');assert.equal(entry.manual,undefined);assert.equal(manualCreditActionsHtml(entry.context,'moodys'),'');await persistManualCreditRating();assert.equal(requests.length,0);
state.auth.user.role='Operator';openManualCreditRating('moodys');validDraft();const saving=persistManualCreditRating();
state.auth.user={id:'other-user',role:'Viewer'};state.auth.csrfToken='session-two';creditRatingsSession();holdingsCreditRatingsSession();
requests[0].resolve(manualContext());await saving;assert.deepEqual(creditRatingsSession().entries,{});assert.deepEqual(holdingsCreditRatingsSession().entries,{});
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_cached_reload_deferred_during_manual_save_does_not_erase_the_new_entry():
    run_ui(r'''
(async()=>{
const entry=prepare();openManualCreditRating('moodys');validDraft();const saving=persistManualCreditRating();
await loadSecurityCreditRatings(entry,{force:true});assert.equal(requests.length,1);assert.equal(entry.reloadAfterManual,true);
requests[0].resolve(manualContext());await saving;assert.equal(requests.length,2,'a queued cache read resumes after the manual save');
requests[1].resolve(manualContext());await flush();assert.equal(entry.context.ratings[0].source_kind,'manual');assert.equal(entry.context.ratings[0].rating,'A2');
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_manual_help_and_native_grade_lists_match_the_financial_contract():
    run_ui(r'''
const fs=require('node:fs'),html=fs.readFileSync('web/index.html','utf8');
for(const pattern of [/To enter your own agency assessment[\s\S]*?<\/p>/,/Supply a public HTTPS source URL[\s\S]*?<\/p>/]){
 const text=html.match(pattern)[0].replace(/<\/p>$/,'').replaceAll('&amp;','&');assert.notEqual(window.PortfolioI18n.translate(text,'he'),text);
}
assert.ok(!MANUAL_CREDIT_GRADES.moodys.includes('AAA'));assert.ok(!MANUAL_CREDIT_GRADES.sp.includes('RD'));assert.ok(MANUAL_CREDIT_GRADES.fitch.includes('RD'));
assert.ok(html.includes('id="manualCreditForm" novalidate'));assert.ok(html.includes('id="manualCreditRatingDate" class="date-field"'));
''')
    source = (ROOT / "web/manual-credit-ratings.js").read_text()
    block = source[source.index("const MANUAL_CREDIT_GRADES"):source.index("function manualCreditRecord")]
    result = subprocess.run(["node"], input=block + "\nconsole.log(JSON.stringify(MANUAL_CREDIT_GRADES));", text=True, capture_output=True, check=True)
    from app.credit_ratings import _LONG
    assert json.loads(result.stdout) == {agency: list(grades) for agency, grades in _LONG.items()}
