"""The general action includes public ratings without changing market-data ownership."""
from pathlib import Path

from test_holdings_credit_ratings_frontend import run_ui as run_summary_ui


ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    source = (ROOT / "web/ai-credit-ratings.js").read_text()
    setup = r'''
const fmt=(value)=>String(value);
const aiSecurityKey=h=>[h.symbol,h.stock_market,h.currency].map(v=>String(v||'').trim().toUpperCase()).join('|');
state.auth.user.role='Operator';state.allPortfolioItems=[];
state.aiEnrichment={job:null,pending:false,resume:false};
function creditJob(status='running',extra={}){
 const outcomes=Array.from({length:25},(_,index)=>({security_key:`C${index}|NASDAQ|USD`,symbol:`C${index}`,stock_market:'NASDAQ',currency:'USD',status:'pending',code:'pending',attempted:false,verified_agencies:[],agency_statuses:{moodys:'not_checked',sp:'not_checked',fitch:'not_checked'}}));
 return {request_id:'all-company-ratings',status,position_scope:'all',progress:{stage:'researching_ratings',completed:0,total:25},outcomes:[],credit_ratings:{status,progress:{completed:0,total:25},summary:{total_candidates:25,updated:0,partial:0,unavailable:0,not_attempted:25},outcomes},...extra};
}
'''
    run_summary_ui(source + "\n" + setup + "\n" + body)


def test_all_api_priced_company_outcomes_remain_visible_with_independent_rating_coverage():
    run_ui(r'''
state.allPortfolioItems=Array.from({length:25},(_,index)=>({...row(`C${index}`),api_data_route:{owner:'api'},missing:[]}));
state.allPortfolioItems.push({...state.allPortfolioItems[0],holding:{...state.allPortfolioItems[0].holding,account_id:'other'}});
state.aiEnrichment.job=creditJob();state.aiEnrichment.pending=true;renderAIEnrichmentCreditRatings();
assert.equal(($('aiCreditRatingsResults').innerHTML.match(/data-ai-credit-result=/g)||[]).length,25);
assert.ok($('aiCreditRatingsResults').innerHTML.includes('C24'));
assert.equal($('aiCreditRatingsCounts').textContent,'Rating checks: 0 of 25 company securities');
assert.equal($('aiEnrichmentRetryRatings').hidden,true);assert.equal(requests.length,0,'rendering must not start child jobs');
const job=state.aiEnrichment.job;job.credit_ratings.progress={completed:7,total:25,current_security:{symbol:'C7',stock_market:'NASDAQ',currency:'USD'}};
job.credit_ratings.summary={updated:3,partial:2,unavailable:2,not_attempted:18};
job.credit_ratings.outcomes.slice(0,7).forEach((outcome,index)=>outcome.status=index<3?'updated':index<5?'partial':'unavailable');
renderAIEnrichmentCreditRatings();assert.ok($('aiCreditRatingsCounts').textContent.includes('7 of 25'));assert.ok($('aiCreditRatingsSummary').textContent.includes('Waiting for rating research: 18'));
job.credit_ratings.outcomes.slice(7).forEach(outcome=>outcome.status='not_attempted');renderAIEnrichmentCreditRatings();assert.ok($('aiCreditRatingsSummary').textContent.includes('Not checked: 18'));
assert.ok($('aiCreditRatingsCurrent').textContent.includes('C7'));
''')


def test_pending_not_checked_and_checked_unavailable_stay_distinct_in_both_languages():
    run_ui(r'''
for(const language of ['he','en']){
 state.language=language;state.aiEnrichment.job=creditJob();
 state.aiEnrichment.job.credit_ratings.outcomes=[
  {security_key:'WAIT|NASDAQ|USD',symbol:'WAIT',stock_market:'NASDAQ',currency:'USD',status:'pending',attempted:false,verified_agencies:[],agency_statuses:{}},
  {security_key:'UNTOUCHED|NASDAQ|USD',symbol:'UNTOUCHED',stock_market:'NASDAQ',currency:'USD',status:'not_attempted',attempted:false,verified_agencies:[],agency_statuses:{}},
  {security_key:'CHECKED|NASDAQ|USD',symbol:'CHECKED',stock_market:'NASDAQ',currency:'USD',status:'unavailable',attempted:true,verified_agencies:[],agency_statuses:{moodys:'not_found',sp:'unavailable',fitch:'not_checked'}},
  {security_key:'PART|NASDAQ|USD',symbol:'PART',stock_market:'NASDAQ',currency:'USD',status:'partial',attempted:true,verified_agencies:['moodys'],agency_statuses:{moodys:'rated',sp:'not_found',fitch:'unavailable'}}];
 renderAIEnrichmentCreditRatings();const html=$('aiCreditRatingsResults').innerHTML;
 for(const label of ['Waiting for rating research','Not checked','Checked; no verified rating evidence','Partial rating evidence'])assert.ok(html.includes(t(label)),label);
 assert.ok(html.includes(t('Supported evidence from {count} of 3 agencies').replace('{count}','1')));
 assert.ok(!html.includes(`>${t('Stable')}<`));assert.ok(!html.includes(`>${t('No watch')}<`));assert.ok(!html.includes(`>${t('Unrated')}<`));
 if(language==='he')assert.ok(!/\b(?:pending|not_attempted|unavailable|Verified rating|Waiting for rating research)\b/.test(html));else assert.ok(!/[א-ת]/.test(html));
}
''')


def test_retry_only_offers_remaining_work_on_a_failed_parent_and_honors_permissions():
    run_ui(r'''
state.aiEnrichment.job=creditJob('failed');renderAIEnrichmentCreditRatings();
assert.equal($('aiEnrichmentRetryRatings').hidden,false);assert.equal($('aiEnrichmentRetryRatings').disabled,false);
state.auth.user.role='Viewer';renderAIEnrichmentCreditRatings();assert.equal($('aiEnrichmentRetryRatings').disabled,true);
state.auth.user.role='Operator';state.aiEnrichment.resume=true;renderAIEnrichmentCreditRatings();assert.equal($('aiEnrichmentRetryRatings').hidden,true,'uncertain requests must be polled, not resumed as a new parent');
state.aiEnrichment.resume=false;state.aiEnrichment.job.credit_ratings.summary.not_attempted=0;renderAIEnrichmentCreditRatings();assert.equal($('aiEnrichmentRetryRatings').hidden,true);
''')


def test_interrupted_research_does_not_claim_that_no_research_was_attempted():
    run_ui(r'''
for(const language of ['en','he']){
 state.language=language;
 const interrupted={security_key:'NREF|NASDAQ|USD',symbol:'NREF',stock_market:'NASDAQ',currency:'USD',status:'not_attempted',attempted:true,code:'ai_provider_unavailable',verified_agencies:[],agency_statuses:{}};
 assert.equal(aiCreditRatingsMessage(interrupted),t('This check did not finish. After an interruption, retry the remaining rating checks.'));
 assert.equal(aiCreditRatingsMessage({...interrupted,attempted:false}),t('This security was not researched. After an interruption, retry the remaining rating checks.'));
 state.aiEnrichment.job=creditJob('failed');state.aiEnrichment.job.credit_ratings.outcomes=[interrupted];renderAIEnrichmentCreditRatings();
 const html=$('aiCreditRatingsResults').innerHTML;
 assert.ok(html.includes(t('This check did not finish. After an interruption, retry the remaining rating checks.')));
 assert.ok(!html.includes(t('This security was not researched. After an interruption, retry the remaining rating checks.')));
 assert.ok(!html.includes('ai_provider_unavailable'));
 if(language==='he')assert.ok(!/\b(?:This check|After an interruption|retry the remaining)\b/.test(html));else assert.ok(!/[א-ת]/.test(html));
}
''')


def test_completed_ratings_reload_cache_once_and_old_reads_cannot_replace_new_manual_facts():
    run_ui(r'''
(async()=>{
state.allPortfolioItems=[row('ACME'),row('ACME',{account_id:'other'})];const button=mount();
const entry=creditRatingsEntry();const oldFull=loadSecurityCreditRatings(entry);
const ui=state.aiEnrichment;ui.job=creditJob('completed');
refreshAIEnrichmentCreditRatings(ui.job,ui);assert.equal(requests.length,3,'one previous full read, one summary read and one fresh full read');
refreshAIEnrichmentCreditRatings(ui.job,ui);assert.equal(requests.length,3,'terminal acceptance is idempotent');
const manual=context('ACME','Baa1',{summary_only:false,manual_ratings:[{agency:'moodys',rating:'Baa1'}]});manual.ratings[0].manual_override=true;
requests[2].resolve(manual);await flush();requests[1].resolve({items:[context('ACME','A2')],not_found_keys:[]});await flush();
requests[0].resolve(context('ACME','Aaa',{summary_only:false}));await oldFull;
assert.equal(entry.context.ratings[0].rating,'Baa1');assert.ok(button.innerHTML.includes('>Baa1<'));assert.ok(!button.innerHTML.includes('>Aaa<'));
const before=requests.length;state.aiEnrichment={job:null,pending:false};refreshAIEnrichmentCreditRatings(creditJob('completed'),ui);assert.equal(requests.length,before,'an old user/job cannot refresh the new session');
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_rating_refresh_waits_for_a_manual_save_without_replacing_its_draft():
    run_ui(r'''
state.allPortfolioItems=[];const entry=creditRatingsEntry();const draft={saving:true,values:{rating:'A2',notes:'retained draft'}};entry.manual=draft;
state.aiEnrichment.job=creditJob('completed');refreshAIEnrichmentCreditRatings(state.aiEnrichment.job,state.aiEnrichment,{table:false});
assert.equal(requests.length,0);assert.equal(entry.reloadAfterManual,true);assert.equal(entry.manual,draft);assert.equal(entry.manual.values.rating,'A2');
''')


def test_explicit_fund_subtypes_are_excluded_but_bdc_industry_text_is_not_a_fund_type():
    run_ui(r'''
(async()=>{
const excluded=[];
for(const kind of ['ETF','FUND','MUTUALFUND','MUTUAL_FUND'])for(const fields of [{asset_sub_class:kind},{instrument_type:kind},{asset_sub_class:'STOCK',instrument_type:kind}]){
 const item=row(`FUND${excluded.length}`,fields);excluded.push(item);assert.equal(creditRatingsEligible(item.holding),false);
 assert.ok(holdingCreditRatingsCellHtml(item).includes('Not applicable'));
}
const bdc=row('FDUS',{asset_sub_class:'STOCK',industry:'Closed-End Funds',name:'Fidus Investment Corporation'});
assert.equal(creditRatingsEligible(bdc.holding),true);
const loading=loadHoldingsCreditRatings([...excluded,bdc]);assert.equal(requests.length,1);
assert.deepEqual(new URL(requests[0].path,'https://example.org').searchParams.getAll('security_keys'),['FDUS|NASDAQ|USD']);
requests[0].resolve({items:[context('FDUS')],not_found_keys:[]});await loading;
})().catch(error=>{console.error(error);process.exitCode=1});
''')
