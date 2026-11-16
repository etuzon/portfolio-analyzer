"""User-facing scope and honest completion contracts for portfolio AI updates."""
from pathlib import Path
import subprocess

from test_shared_cash_risk_qa import app_functions

ROOT = Path(__file__).resolve().parents[1]


def node(script):
    result = subprocess.run(["node"], input=script, cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def targets(body):
    return r'''
const assert=require('node:assert/strict');
const nodes={aiResearchTarget:{value:'portfolio'},aiResearchRefresh:{value:'stale'},aiRiskResearchMode:{value:'api_then_ai'}};
const handlers={};const document={getElementById:id=>nodes[id],addEventListener:(type,handler)=>handlers[type]=handler};
const state={aiEnrichment:{},auth:{user:{id:'qa',role:'Operator'}},language:'en'};
const window={},t=x=>x,fmt=x=>String(x);
''' + (ROOT / "web/ai-research-targets.js").read_text() + body


def test_default_ai_update_covers_risk_and_country_ratings_with_existing_data():
    node(targets(r'''
assert.deepEqual(window.AIResearchTargets.requestOptions(),{
 data_types:['prices','profile','company_ratings','risk_inputs','country_ratings'],refresh_policy:'stale',risk_mode:'api_then_ai'});
nodes.aiResearchTarget.value='profile';
assert.deepEqual(window.AIResearchTargets.requestOptions(),{data_types:['profile'],refresh_policy:'stale'});
nodes.aiResearchTarget.value='risk_inputs';nodes.aiRiskResearchMode.value='api';
assert.deepEqual(window.AIResearchTargets.requestOptions(),{data_types:['risk_inputs'],refresh_policy:'stale',risk_mode:'api'});
'''))


def test_finished_research_distinguishes_unknown_fields_from_saved_updates():
    node(targets(r'''
const completion=window.AIResearchTargets.completionText;
assert.match(completion({status:'completed',outcomes:[{status:'updated',missing_fields:[]}]}),/no missing risk inputs remain/);
assert.match(completion({status:'completed',outcomes:[{status:'partial',missing_fields:['fx']},{status:'unavailable',missing_fields:['fund_lookthrough']},{status:'updated',missing_fields:[]}]}),/2 securities still have missing risk inputs/);
assert.equal(completion({status:'running',outcomes:[]}), 'Research in progress');
assert.equal(completion({status:'failed',outcomes:[]}), 'Research stopped');
assert.equal(window.AIResearchTargets.unresolvedCount({outcomes:[{status:'not_attempted'}]}),1);
'''))


def test_reopening_parent_ai_results_restores_finished_risk_request():
    node(r'''
const assert=require('node:assert/strict');
const state={aiEnrichment:{outcomes:[],version:2}};
const last={request_id:'risk-parent',status:'completed',risk_inputs:{outcomes:[{symbol:'QA',missing_fields:['fx']}]}};
const api=async()=>({items:[],active_job:null,last_job:last});
let accepted;
const acceptAIEnrichmentJob=job=>accepted=job,renderAIEnrichment=()=>{},scheduleAIEnrichmentPoll=()=>{};
''' + "async " + app_functions("loadAIEnrichmentStatus") + r'''
(async()=>{await loadAIEnrichmentStatus();assert.equal(accepted,last);})().catch(error=>{console.error(error);process.exit(1);});
''')


def test_old_parent_progress_cannot_replace_new_user_session():
    node(targets(r'''
let resolve,accepted=0;
const old={job:{request_id:'old'},version:1};state.aiEnrichment=old;
const currentUser=()=>({id:'qa'}),api=async()=>new Promise(done=>resolve=done);
const acceptAIEnrichmentJob=()=>{accepted++;};
const scheduleAIEnrichmentPoll=()=>{},renderAIEnrichment=()=>{};
(async()=>{
 handlers.click({target:{closest:()=>true}});
 await Promise.resolve();
 assert.equal(old.checking,true);
 state.aiEnrichment={job:{request_id:'new'},version:2};
 resolve({request_id:'old',status:'completed',portfolio_refresh_required:true});
 await new Promise(setImmediate);
 assert.equal(accepted,0);
 assert.equal(state.aiEnrichment.job.request_id,'new');
})().catch(error=>{console.error(error);process.exit(1);});
'''))
