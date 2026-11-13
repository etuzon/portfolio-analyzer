"""Agency evidence and asynchronous refresh remain distinct and recoverable."""
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    script = "const window = {};\n" + (ROOT / "web/i18n.js").read_text()
    script += r'''
const assert = require('node:assert/strict');
const state = {language:'en',auth:{user:{id:'operator',role:'Operator'},csrfToken:'session-one'},
  securityDetail:{symbol:'ACME',market_key:'NASDAQ',currency:'USD',asset_class:'EQUITY'}};
const nodes = new Map();
const $ = id => {
  if (!nodes.has(id)) nodes.set(id,{id,hidden:false,disabled:false,textContent:'',innerHTML:'',attributes:{},
    setAttribute(key,value){this.attributes[key]=value},querySelectorAll(){return []},querySelector(){return null}});
  return nodes.get(id);
};
const document = {activeElement:null,addEventListener(){}};
const currentUser = () => state.auth.user;
const canWrite = () => ['Admin','Operator'].includes(currentUser()?.role);
const t = text => window.PortfolioI18n.translate(text,state.language);
const formatDate = date => date.split('-').reverse().join('/');
const esc = text => String(text??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const timers = new Map(); let nextTimer = 0;
const setTimeout = callback => {timers.set(++nextTimer,callback);return nextTimer};
const clearTimeout = id => timers.delete(id);
const requests = [];
const api = (path,options={}) => new Promise((resolve,reject)=>requests.push({path,options,resolve,reject}));
const flush = () => new Promise(setImmediate);
const context = (overrides={}) => ({schema_version:'credit-ratings-v1',security_key:'ACME|NASDAQ|USD',symbol:'ACME',
  stock_market:'NASDAQ',currency:'USD',issuer_name:'Acme Corporation',status:'partial',ratings:[
  {agency:'moodys',status:'rated',rating:'A3',scope:'issuer',scale:'global',term:'long_term',rating_type:'issuer_rating',
   entity_name:'Acme Corporation',rating_date:'2026-09-10',outlook:'stable',watch:'unknown',
   observed_at:'2026-11-11',fetched_at:'2026-11-13T09:30:00Z',stale:false,
   sources:[{url:'https://example.org/moodys',fields:['rating','outlook']}],source_url:'https://example.org/moodys'},
  {agency:'sp',status:'not_found',outlook:'unknown',watch:'unknown',reason_code:'not_found'},
  {agency:'fitch',status:'unrated',outlook:'unknown',watch:'none',stale:true}],provider_status:[],...overrides});
''' + (ROOT / "web/security-credit-ratings.js").read_text() + "\n" + body
    result = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT, timeout=15)
    assert result.returncode == 0, result.stderr


def test_three_agencies_preserve_scope_dates_unknowns_and_safe_citations():
    run_ui(r'''
const html=creditRatingsRows(context());
assert.equal((html.match(/<tr>/g)||[]).length,3);
assert.ok(html.indexOf('Moody’s')<html.indexOf('S&amp;P Global Ratings'));
assert.ok(html.indexOf('S&amp;P Global Ratings')<html.indexOf('Fitch'));
assert.match(html,/dir="ltr">A3</);
assert.match(html,/Issuer rating · Global scale · Long term/);
for(const date of ['10/09/2026','11/11/2026','13/11/2026'])assert.ok(html.includes(date),date);
assert.equal((html.match(/href="https:\/\/example.org\/moodys"/g)||[]).length,1,'deduplicate the primary citation');
assert.match(html,/Not found/);assert.match(html,/does not establish that the issuer is unrated/);
assert.match(html,/Unrated/);assert.match(html,/No watch/);assert.match(html,/Stale evidence/);
const empty=creditRatingsRows(null);
assert.equal((empty.match(/Not checked/g)||[]).length,3);
assert.ok(!empty.includes('>Stable<'));assert.ok(!empty.includes('>No watch<'));
assert.ok(!empty.includes('2026'),'missing source dates are never replaced with today');
const bad=context();bad.ratings[0].rating='<img src=x onerror=alert(1)>';
bad.ratings[0].sources=[{url:'javascript:alert(1)'},{url:'https://example.org/valid',fields:'rating'}];
bad.ratings[0].source_url='data:text/html,example';
const safe=creditRatingsRows(bad);assert.ok(!safe.includes('<img'));assert.ok(safe.includes('&lt;img'));
assert.ok(!safe.includes('href="javascript:'));assert.ok(!safe.includes('href="data:'));assert.ok(safe.includes('https://example.org/valid'));
const conflict=creditRatingsRows(context({ratings:[{agency:'sp',status:'conflicting',observations:[
 {agency:'sp',rating:'BBB+',source_url:'https://example.org/conflict-one'},
 {agency:'sp',rating:'BBB-',sources:[{url:'https://example.org/conflict-two'}]},
 {agency:'fitch',source_url:'https://example.org/unrelated'}]}]}));
assert.ok(conflict.includes('https://example.org/conflict-one'));assert.ok(conflict.includes('https://example.org/conflict-two'));
assert.ok(!conflict.includes('https://example.org/unrelated'));assert.ok(!conflict.includes('>BBB+<'));assert.ok(!conflict.includes('>BBB-<'));
''')


def test_hebrew_and_english_statuses_directions_and_reasons_follow_active_language():
    run_ui(r'''
for(const language of ['he','en','he']){
 state.language=language;
 const html=creditRatingsRows(context());
 if(language==='he'){
  for(const label of ['דירוג מאומת','דירוג מנפיק','סולם בינלאומי','טווח ארוך','לא נמצא','ללא דירוג','לא ידוע','ללא מעקב','פרטים ומקורות','מקור 1','אסמכתאות ישנות'])assert.ok(html.includes(label),label);
  assert.ok(!/>\s*(?:Stable|Unknown|No watch|Not found|Unrated|Verified rating|Details and sources)\s*</.test(html));
 }else{
  assert.ok(!/[א-ת]/.test(html));assert.ok(html.includes('Stable'));assert.ok(html.includes('Source 1'));
 }
}
state.language='he';
for(const status of ['rated','unrated','withdrawn','not_found','not_checked','unavailable','conflicting']){
 const html=creditRatingsRows(context({ratings:[{agency:'moodys',status,outlook:'developing',watch:'positive'}]}));
 const visible=html.replace(/<[^>]+>/g,' ').replaceAll('Moody’s','').replaceAll('S&amp;P Global Ratings','').replaceAll('Fitch','');
 assert.ok(!/\b(?:Verified|Withdrawn|Unknown|Developing|Positive|Sources|Rating|Entity)\b/.test(visible),status);
}
''')


def test_rating_workflow_has_no_licensed_provider_prompt_even_for_old_cached_metadata():
    run_ui(r'''
const statuses=['configured','not_configured','entitlement_required','authentication_required','provider_unavailable','data_unavailable','identity_unavailable','rate_limited'];
for(const language of ['en','he']){
 state.language=language;
 const html=creditRatingsProviderStatus(statuses.map(status=>({provider:'spglobal_agency_ratings',configured:status!=='not_configured',status,docs_url:'https://example.org/api'})));
 assert.equal(html,'','retained provider metadata must not prompt for a licensed rating feed');
 for(const code of ['api_not_configured','configuration_required','entitlement_required','access_denied']){
  const reason=creditRatingsReason(code,'unavailable');
  assert.equal(reason,t('Refresh ratings researches public sources with AI. No licensed rating API is required.'));
  if(language==='he')assert.ok(!/\b(?:Refresh|licensed|required)\b/.test(reason));else assert.ok(!/[א-ת]/.test(reason));
 }
}
''')


def test_forward_signals_keep_their_own_verification_dates_and_stale_badges():
    run_ui(r'''
const record={...context().ratings[0],fetched_at:'2026-11-13T09:30:00Z',checked_at:'2026-11-13T10:00:00Z',stale:false,
 outlook:'stable',outlook_fetched_at:'2026-08-01T08:00:00Z',outlook_stale:true,watch:'negative',watch_fetched_at:'2026-11-12T08:00:00Z',watch_stale:false,forward_signal_stale:true};
for(const language of ['en','he','en']){
 state.language=language;
 const evidence=creditRatingsEvidence(record,'Moody’s');
 assert.match(evidence,/<dt>[^<]*<\/dt><dd><bdi dir="auto">01\/08\/2026<\/bdi>/);
 for(const date of ['01/08/2026','12/11/2026','13/11/2026'])assert.ok(evidence.includes(date),date);
 const outlook=creditRatingsSignal(record,'outlook'),watch=creditRatingsSignal(record,'watch');
 assert.ok(outlook.includes('01/08/2026'));assert.ok(!outlook.includes('13/11/2026'),'grade refresh must not redate the retained outlook');
 assert.match(outlook,/class="badge warn"/);assert.ok(!watch.includes('class="badge warn"'),'aggregate stale state must not mark a fresh watch stale');
 if(language==='he'){
  for(const label of ['נבדק לאחרונה','אימות אחרון של תחזית הדירוג','אימות אחרון של מעקב הדירוג'])assert.ok(evidence.includes(label),label);
  assert.ok(outlook.includes('תחזית דירוג ישנה'));assert.ok(!/\b(?:Stale|verified|checked|Stable)\b/.test(outlook));
 }else{
  for(const label of ['Last checked','Outlook last verified','Watch last verified'])assert.ok(evidence.includes(label),label);
  assert.ok(outlook.includes('Stale outlook'));assert.ok(!/[א-ת]/.test(evidence));
 }
}
record.outlook_stale=false;record.watch_stale=true;
assert.ok(!creditRatingsSignal(record,'outlook').includes('badge warn'));
assert.ok(creditRatingsSignal(record,'watch').includes('Stale watch'));
delete record.watch_fetched_at;
assert.ok(creditRatingsSignal(record,'watch').includes('Watch last verified: Unknown'),'a missing signal date never borrows the grade date');
const attempted={agency:'moodys',status:'unavailable',reason_code:'source_read_failed',checked_at:'2026-11-13T10:00:00Z'};
const firstRow=creditRatingsRows(context({ratings:[attempted]})).match(/^<tr>[\s\S]*?<\/tr>/)[0];
assert.ok(firstRow.includes('Unavailable'));assert.ok(firstRow.includes('Last checked'));assert.ok(!firstRow.includes('Not checked'));
''')


def test_ancillary_ratings_stay_in_sources_without_replacing_the_primary_grade():
    run_ui(r'''
const record={agency:'moodys',status:'unavailable',reason_code:'primary_rating_unavailable',rating:null,observations:[
 {agency:'moodys',rating:'Aa1',rating_type:'deposit',scope:'issuer',scale:'global',term:'long_term',entity_name:'Example Bank',rating_date:'2026-10-01',primary_eligible:false,source_url:'https://example.org/deposit'},
 {agency:'moodys',rating:'P-1',rating_type:'issuer',scope:'issuer',scale:'national',term:'short_term',entity_name:'Example Bank',rating_date:'2026-10-02',primary_eligible:false,sources:[{url:'https://example.org/short-term'}]},
 {agency:'fitch',rating:'unrelated-grade',rating_type:'deposit',primary_eligible:false,source_url:'https://example.org/unrelated'}]};
for(const language of ['en','he']){
 state.language=language;
 const row=creditRatingsRows(context({ratings:[record]})).match(/^<tr>[\s\S]*?<\/tr>/)[0];
 const primary=row.match(/<td [\s\S]*?<\/td>/)[0];
 assert.ok(primary.includes('>—<'));assert.ok(!primary.includes('>Aa1<'));assert.ok(!primary.includes('>P-1<'));
 for(const text of ['Aa1','P-1','Example Bank','01/10/2026','02/10/2026','https://example.org/deposit','https://example.org/short-term'])assert.ok(row.includes(text),text);
 assert.ok(!row.includes('unrelated-grade'));assert.ok(!row.includes('https://example.org/unrelated'));
 if(language==='he'){
  for(const label of ['קטגוריות דירוג נוספות','דירוג פיקדונות','הישות המדורגת','תחולת הדירוג','סולם דירוג','טווח דירוג','טווח קצר','סולם מקומי'])assert.ok(row.includes(label),label);
  assert.ok(row.includes('לא אומת דירוג נתמך לטווח ארוך'));
  assert.ok(!/\b(?:Unavailable|Other rating categories|Deposit rating|Long term|Short term)\b/.test(row));
 }else{
  assert.ok(row.includes('Other rating categories'));assert.ok(row.includes('Deposit rating'));assert.ok(!/[א-ת]/.test(row));
 }
}
''')


def test_parent_senior_unsecured_outlook_stays_ancillary_without_borrowing_the_bank_rating():
    run_ui(r'''
const parent={agency:'moodys',status:'unavailable',reason_code:'primary_rating_unavailable',rating:null,outlook:'unknown',watch:'unknown',observations:[
 {agency:'moodys',rating:'A2',rating_type:'senior_unsecured_class',scope:'issuer',scale:'global',term:'long_term',entity_name:'UBS Group AG',primary_eligible:false,
  rating_date:null,observed_at:'2026-11-06',fetched_at:'2026-11-13T09:30:00Z',action_type:'periodic_review',
  outlook:'stable',outlook_date:null,outlook_fetched_at:'2026-08-01T08:00:00Z',outlook_stale:true,watch:'unknown',source_url:'https://example.org/ubs-parent'},
 {agency:'moodys',rating:'Aa2',rating_type:'issuer',scope:'issuer',scale:'global',term:'long_term',entity_name:'UBS AG',primary_eligible:true,
  outlook:'stable',source_url:'https://example.org/ubs-bank'}]};
for(const language of ['en','he']){
 state.language=language;
 const html=creditRatingsRows(context({issuer_name:'UBS Group AG',ratings:[parent]}));
 const row=html.match(/^<tr>[\s\S]*?<\/tr>/)[0],primary=row.match(/<td [\s\S]*?<\/td>/)[0];
 assert.ok(primary.includes('>—<'));assert.ok(!primary.includes('>A2<'));assert.ok(!primary.includes('>Aa2<'));
 assert.ok(row.includes('>A2<'));assert.ok(row.includes('UBS Group AG'));assert.ok(!row.includes('>Aa2<'));assert.ok(!row.includes('UBS AG'));assert.ok(!row.includes('https://example.org/ubs-bank'));
 const ancillary=creditRatingsOtherCategories(parent);
 assert.ok(ancillary.includes('06/11/2026'));assert.ok(ancillary.includes('13/11/2026'));assert.ok(ancillary.includes('01/08/2026'));
 assert.ok(ancillary.includes(`<dt>${t('Rating date')}</dt><dd><bdi dir="auto">${t('Unknown')}</bdi>`),'periodic review date must not become a rating action date');
 assert.ok(ancillary.includes(`<dt>${t('Outlook last verified')}</dt><dd><bdi dir="auto">01/08/2026</bdi>`),'retained outlook verification stays separate from retrieval');
 if(language==='he'){
  for(const label of ['חוב בכיר לא מובטח','קטגוריה ברמת המנפיק','תחזית דירוג','יציב','מעקב דירוג','לא ידוע','סקירה תקופתית','תאריך התצפית במקור','תאריך האחזור','אימות אחרון של תחזית הדירוג'])assert.ok(ancillary.includes(label),label);
  assert.ok(!/\b(?:Stable|Unknown|Senior unsecured debt|Periodic review|Retrieved|issuer|periodic_review)\b/.test(ancillary));
 }else{
  for(const label of ['Senior unsecured debt','Issuer-level category','Stable','Watch','Unknown','Periodic review','Source observation date','Retrieved','Outlook last verified'])assert.ok(ancillary.includes(label),label);
  assert.ok(!/[א-ת]/.test(ancillary));
 }
}
state.language='en';
parent.observations[0].action_type='rating_action';parent.observations[0].rating_date='2026-11-06';
assert.ok(creditRatingsOtherCategories(parent).includes('Source record type: Rating action'));
delete parent.observations[0].outlook_fetched_at;
assert.ok(creditRatingsOtherCategories(parent).includes('<dt>Outlook last verified</dt><dd><bdi dir="auto">Unknown</bdi>'),'a missing outlook verification date is not replaced with the grade retrieval date');
''')


def test_all_canonical_agency_categories_have_specific_localized_labels():
    run_ui(r'''
const categories=['issuer','issuer_default','corporate_family','deposit','senior_unsecured_class','junior_subordinated_class','subordinated_class','preferred_stock_class','viability','issue'];
for(const language of ['en','he']){
 state.language=language;
 for(const rating_type of categories){
  const label=creditRatingsCategory({rating_type});
  assert.notEqual(label,t('Agency rating category'),rating_type);
  assert.ok(!label.includes('_'),rating_type);
  if(language==='he')assert.ok(/[א-ת]/.test(label),rating_type);else assert.ok(!/[א-ת]/.test(label),rating_type);
 }
}
''')


def test_opening_is_cache_only_and_viewers_cannot_start_refresh():
    run_ui(r'''
(async()=>{
 state.auth.user.role='Viewer';openSecurityCreditRatings(state.securityDetail);
 assert.equal(requests.length,1);assert.match(requests[0].path,/^\/api\/securities\/credit-ratings\?/);
 assert.ok(requests[0].path.includes('stock_market=NASDAQ'));assert.equal(requests[0].options.method,undefined);
 requests[0].resolve(context());await flush();
 assert.equal($('refreshSecurityCreditRatings').disabled,true);
 await refreshSecurityCreditRatings();assert.equal(requests.length,1);
 assert.match($('securityCreditRatingsStatus').textContent,/Viewing saved ratings/);
 state.auth.user.role='Operator';renderSecurityCreditRatings();assert.equal($('refreshSecurityCreditRatings').disabled,false);
 state.securityDetail={symbol:'FUND',market_key:'NYSE',currency:'USD',asset_class:'ETF'};
 openSecurityCreditRatings(state.securityDetail);assert.equal($('securityCreditRatings').hidden,true);assert.equal(requests.length,1);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_failed_cache_reads_preserve_evidence_and_old_responses_cannot_replace_new_security():
    run_ui(r'''
(async()=>{
 openSecurityCreditRatings(state.securityDetail);requests[0].resolve(context());await flush();
 const entry=creditRatingsEntry();const saved=entry.context;
 const failed=loadSecurityCreditRatings();requests[1].reject(Error('private provider error'));await failed;
 assert.equal(entry.context,saved);assert.equal($('reloadSecurityCreditRatings').hidden,false);
 assert.ok(!$('securityCreditRatingsStatus').textContent.includes('private provider'));
 const retry=loadSecurityCreditRatings();requests[2].resolve(context());await retry;assert.equal(entry.message,'');
 const old=loadSecurityCreditRatings(entry);
 state.securityDetail={symbol:'NEXT',market_key:'NYSE',currency:'EUR',asset_class:'EQUITY'};
 openSecurityCreditRatings(state.securityDetail);
 requests[4].resolve(context({security_key:'NEXT|NYSE|EUR',issuer_name:'Next Issuer'}));await flush();
 requests[3].resolve(context({issuer_name:'Old Issuer'}));await old;
 assert.equal($('securityCreditRatingsIssuer').textContent,'Issuer: Next Issuer');
 state.auth.user={id:'other-user',role:'Viewer'};state.auth.csrfToken='session-two';
 assert.equal(creditRatingsEntry().context,null,'saved in-memory request state is cleared on user/session change');
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_rating_refresh_polls_and_resumes_same_request_then_reloads_saved_evidence():
    run_ui(r'''
(async()=>{
 openSecurityCreditRatings(state.securityDetail);requests[0].resolve(context());await flush();
 const refresh=refreshSecurityCreditRatings();const duplicate=refreshSecurityCreditRatings();await duplicate;
 assert.equal(requests.length,2);assert.equal(requests[1].path,'/api/securities/credit-ratings/ai');
 assert.equal(requests[1].options.method,'POST');
 assert.deepEqual(JSON.parse(requests[1].options.body),{security_keys:['ACME|NASDAQ|USD'],position_scope:'all'});
 requests[1].resolve({request_id:'ratings-one',status:'running',progress:{stage:'researching',completed:0,total:1}});await refresh;
 const entry=creditRatingsEntry();assert.equal(entry.pending,true);
 assert.ok($('securityCreditRatingsRows').innerHTML.includes('A3'),'refresh retains saved evidence');
 assert.equal($('refreshSecurityCreditRatings').disabled,true);
 const poll=checkCreditRatingsProgress(entry);requests[2].reject(Error('interrupted'));await poll;
 assert.equal(entry.resume,true);assert.equal($('resumeSecurityCreditRatings').hidden,false);
 await refreshSecurityCreditRatings();assert.equal(requests.length,3,'interrupted progress cannot start a second job');
 const resume=checkCreditRatingsProgress(entry);
 assert.equal(requests[3].path,'/api/securities/credit-ratings/ai/ratings-one');
 requests[3].resolve({request_id:'ratings-one',status:'completed',progress:{stage:'completed',completed:1,total:1}});await resume;
 assert.equal(requests.length,5);assert.match(requests[4].path,/^\/api\/securities\/credit-ratings\?/);
 requests[4].resolve(context({ratings:[{agency:'moodys',status:'rated',rating:'A2',outlook:'positive',watch:'unknown'}]}));await flush();
 assert.ok($('securityCreditRatingsRows').innerHTML.includes('A2'));assert.equal(entry.pending,false);assert.equal(entry.resume,false);
 assert.equal($('refreshSecurityCreditRatings').disabled,false);assert.equal(timers.size,0);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_another_securitys_busy_request_is_localized_and_never_attaches_the_running_job():
    run_ui(r'''
(async()=>{
 openSecurityCreditRatings(state.securityDetail);requests[0].resolve(context());await flush();
 const first=refreshSecurityCreditRatings();requests[1].resolve({request_id:'acme-running',status:'running',progress:{stage:'researching'}});await first;
 const firstEntry=creditRatingsEntry();
 state.securityDetail={symbol:'NEXT',market_key:'NYSE',currency:'EUR',asset_class:'EQUITY'};
 openSecurityCreditRatings(state.securityDetail);requests[2].resolve(context({security_key:'NEXT|NYSE|EUR',symbol:'NEXT',stock_market:'NYSE',currency:'EUR'}));await flush();
 const secondEntry=creditRatingsEntry();
 for(const language of ['he','en']){
  state.language=language;
  const busy=refreshSecurityCreditRatings();requests.at(-1).reject(Object.assign(Error('enrichment_busy'),{status:409}));await busy;
  assert.equal(secondEntry.job,null);assert.equal(secondEntry.pending,false);assert.equal(secondEntry.resume,false);
  assert.equal(firstEntry.job.request_id,'acme-running');assert.equal(firstEntry.pending,true);
  const message=$('securityCreditRatingsStatus').textContent;
  assert.equal(message,t('A rating check is already running. Wait for it to finish, then refresh this security.'));
  assert.ok(!message.includes('enrichment_busy'));assert.equal($('resumeSecurityCreditRatings').hidden,true);
  if(language==='he')assert.ok(!/\b(?:rating|running|Wait|security)\b/.test(message));else assert.ok(!/[א-ת]/.test(message));
 }
 const failed=refreshSecurityCreditRatings();requests.at(-1).reject(Object.assign(Error('private server error'),{status:503}));await failed;
 assert.equal(secondEntry.message,'The rating request could not be confirmed. Reload saved ratings, then retry if needed.');
 assert.equal(secondEntry.job,null);assert.equal(firstEntry.job.request_id,'acme-running');
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_help_documents_rating_workflow_in_both_languages():
    run_ui(r'''
const fs=require('node:fs');const html=fs.readFileSync('web/index.html','utf8');
const help=html.slice(html.indexOf('id="helpModal"'),html.indexOf('id="securityDetailModal"'));
const paragraphs=[...help.matchAll(/<p>([^<]*Company credit ratings[^<]*|Opening the overview only reads saved ratings[^<]*|Last checked records a research attempt[^<]*|Credit ratings in Holdings include[^<]*)<\/p>/g)].map(match=>match[1].replaceAll('&amp;','&'));
assert.equal(paragraphs.length,4);
for(const text of paragraphs){const translated=window.PortfolioI18n.translate(text,'he');assert.notEqual(translated,text);assert.ok(/[א-ת]/.test(translated));}
assert.ok(html.includes('/security-credit-ratings.js?v=4'));assert.ok(html.includes('/security-credit-ratings.css?v=2'));
assert.ok(!help.includes('SPGLOBAL_RATINGS_TOKEN'));assert.ok(!help.includes('Administrators configure market_data.credit_ratings'));
''')
