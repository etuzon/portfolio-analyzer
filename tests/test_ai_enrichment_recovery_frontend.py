"""Manual recovery keeps the failed request's frozen scope and saved work."""
import subprocess
from pathlib import Path

from test_shared_cash_risk_qa import app_functions


ROOT = Path(__file__).resolve().parents[1]


def run_node(source):
    result = subprocess.run(["node"], input=source, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_late_resume_response_cannot_restore_a_confirmed_expired_request():
    run_node(r'''
const assert=require('node:assert/strict');
const oldJob={request_id:'expired',status:'failed',position_scope:'all',data_types:['profile']};
const saved=[{symbol:'DONE',status:'updated'}];
const state={auth:{user:{role:'Operator'}},aiEnrichment:{job:oldJob,outcomes:saved,pending:false,resume:false,ratingsOnly:false}};
const currentUser=()=>state.auth.user,canWrite=()=>true,renderAIEnrichment=()=>{},appWarn=()=>{};
let polls=0,accepted=0,resolvePost;
const scheduleAIEnrichmentPoll=()=>polls++,acceptAIEnrichmentJob=()=>accepted++;
const window={AIResearchTargets:{requestOptions:job=>({data_types:job.data_types,refresh_policy:'missing'})}};
const api=async()=>new Promise(resolve=>resolvePost=resolve);
''' + app_functions('expireAIEnrichmentRequest') + "async " + app_functions('requestAIEnrichment') + r'''
(async()=>{
 const pending=requestAIEnrichment('all',{resumeRequestId:'expired'});
 expireAIEnrichmentRequest(state.aiEnrichment);
 resolvePost({...oldJob,status:'queued'});await pending;
 assert.equal(accepted,0);assert.equal(polls,0);
 assert.equal(state.aiEnrichment.job,null);assert.equal(state.aiEnrichment.pending,false);
 assert.equal(state.aiEnrichment.resume,false);assert.equal(state.aiEnrichment.outcomes,saved);
 assert.match(state.aiEnrichment.message,/no longer available/);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_remaining_action_covers_every_branch_without_repeating_checked_gaps():
    run_node(r'''
const assert=require('node:assert/strict');
const button={setAttribute(){}};
const $=()=>button,t=x=>x;
const state={auth:{user:{role:'Operator'},forcedPasswordChange:false},aiEnrichment:{pending:false,resume:false}};
const currentUser=()=>state.auth.user,canWrite=()=>['Operator','Admin'].includes(currentUser()?.role);
''' + app_functions("renderAIEnrichmentRecovery") + r'''
for(const branch of ['market','credit_ratings','risk_inputs','country_ratings']){
 const panel={outcomes:[{status:'updated'},{status:'not_attempted'}]};
 state.aiEnrichment.job={request_id:'stopped',status:'failed',...(branch==='market'?panel:{[branch]:panel})};
 renderAIEnrichmentRecovery();
 assert.equal(button.hidden,false,branch);assert.equal(button.textContent,'Retry remaining checks');
 state.auth.user.role='Viewer';renderAIEnrichmentRecovery();assert.equal(button.disabled,true);
 state.auth.user.role='Operator';state.auth.forcedPasswordChange=true;renderAIEnrichmentRecovery();assert.equal(button.disabled,true);
 state.auth.forcedPasswordChange=false;state.aiEnrichment.resume=true;renderAIEnrichmentRecovery();assert.equal(button.hidden,true);
 state.aiEnrichment.resume=false;panel.outcomes.splice(0,2,{status:'partial',missing_fields:['profile']});
 renderAIEnrichmentRecovery();assert.equal(button.hidden,true,'completed checks with unresolved fields are not unchecked work');
}
state.aiEnrichment.job={request_id:'ratings',status:'failed',ratings_only:true,credit_ratings:{summary:{not_attempted:1}}};
renderAIEnrichmentRecovery();assert.equal(button.textContent,'Retry remaining rating checks');
state.aiEnrichment.job.status='completed';renderAIEnrichmentRecovery();assert.equal(button.hidden,true);
''')


def test_manual_resume_keeps_selected_scope_mode_and_saved_results_while_waiting():
    run_node(r'''
const assert=require('node:assert/strict');
const saved=[{symbol:'DONE',status:'updated'}];
const oldJob={request_id:'frozen',status:'failed',position_scope:'all',data_types:['profile'],refresh_policy:'refresh_existing',risk_mode:'ai',security_keys:['ONE|NASDAQ|USD'],progress:{completed:10,total:27},outcomes:saved};
const state={auth:{user:{role:'Operator'}},aiEnrichment:{job:oldJob,outcomes:saved,pending:false,resume:false,ratingsOnly:false,refreshedJob:'frozen',refreshedRatingsJob:'frozen'}};
const currentUser=()=>state.auth.user,canWrite=()=>true,renderAIEnrichment=()=>{},scheduleAIEnrichmentPoll=()=>{},appWarn=()=>{};
const window={AIResearchTargets:{requestOptions:job=>job?{data_types:job.data_types,refresh_policy:job.refresh_policy}:{data_types:['prices'],refresh_policy:'missing'}}};
let sent,resolvePost;
const api=async(path,options)=>{sent=JSON.parse(options.body);return await new Promise(resolve=>resolvePost=resolve);};
const acceptAIEnrichmentJob=job=>{state.aiEnrichment.job=job;state.aiEnrichment.pending=job.status==='queued';};
''' + "async " + app_functions("requestAIEnrichment") + r'''
(async()=>{
 const pending=requestAIEnrichment('open',{resumeRequestId:'frozen'});
 assert.equal(state.aiEnrichment.job,oldJob);assert.equal(state.aiEnrichment.outcomes,saved);
 assert.equal(state.aiEnrichment.refreshedJob,undefined);assert.equal(state.aiEnrichment.refreshedRatingsJob,undefined);
 assert.deepEqual(state.aiEnrichment.job.progress,{completed:10,total:27});
 assert.deepEqual(sent,{position_scope:'all',ratings_only:false,data_types:['profile'],refresh_policy:'refresh_existing',risk_mode:'ai',security_keys:['ONE|NASDAQ|USD'],resume_request_id:'frozen'});
 resolvePost({...oldJob,status:'queued'});await pending;
 assert.equal(state.aiEnrichment.job.request_id,'frozen');assert.equal(oldJob.status,'failed');
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_uncertain_resume_checks_progress_without_starting_any_work():
    run_node(r'''
const assert=require('node:assert/strict');
const oldJob={request_id:'frozen',status:'failed',position_scope:'all',ratings_only:true};
const state={auth:{user:{role:'Operator'}},aiEnrichment:{job:oldJob,pending:false,resume:true,ratingsOnly:true}};
const currentUser=()=>state.auth.user,canWrite=()=>true,renderAIEnrichment=()=>{},scheduleAIEnrichmentPoll=()=>{},appWarn=()=>{};
const window={AIResearchTargets:{requestOptions(){throw Error('Progress polling must not read new-request options');}}};
let calls=[];
const api=async(path,options)=>{calls.push({path,options});return oldJob;};
const acceptAIEnrichmentJob=job=>{state.aiEnrichment.job=job;state.aiEnrichment.pending=false;state.aiEnrichment.resume=false;};
''' + "async " + app_functions("requestAIEnrichment") + r'''
(async()=>{
 await requestAIEnrichment('open',{resumeRequestId:'frozen'});
 assert.deepEqual(calls,[{path:'/api/securities/enrichment/ai/frozen',options:undefined}]);
 assert.equal(state.aiEnrichment.job,oldJob);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_expired_manual_resume_or_progress_clears_job_without_losing_saved_rows():
    run_node(r'''
const assert=require('node:assert/strict');
const saved=[{symbol:'DONE',status:'updated'}];
const oldJob={request_id:'expired',status:'failed',position_scope:'all',data_types:['profile']};
const state={auth:{user:{role:'Operator'}},aiEnrichment:{}};
const currentUser=()=>state.auth.user,canWrite=()=>true,renderAIEnrichment=()=>{},scheduleAIEnrichmentPoll=()=>{},appWarn=()=>{};
const window={AIResearchTargets:{requestOptions:job=>({data_types:job.data_types,refresh_policy:'missing'})}};
let calls=[];
const api=async(path,options)=>{calls.push({path,options});const error=new Error('enrichment_request_not_found');error.status=404;throw error;};
''' + app_functions("isAIEnrichmentRequestExpired", "expireAIEnrichmentRequest") + "\nasync " + app_functions("requestAIEnrichment") + r'''
(async()=>{
 for(const polling of [false,true]){
  state.aiEnrichment={job:oldJob,outcomes:saved,pending:false,resume:polling,ratingsOnly:false};calls=[];
  await requestAIEnrichment('open',{resumeRequestId:'expired'});
  assert.equal(calls.length,1);assert.equal(calls[0].options?.method,polling?undefined:'POST');
  assert.equal(state.aiEnrichment.job,null);assert.equal(state.aiEnrichment.pending,false);assert.equal(state.aiEnrichment.resume,false);
  assert.equal(state.aiEnrichment.outcomes,saved);
  assert.equal(state.aiEnrichment.message,'The previous AI request is no longer available. Saved results are retained; start a new request.');
 }
 assert.equal(isAIEnrichmentRequestExpired({status:404,message:'Not Found'}),false,'unrelated404doesnotproveexpiration');
 assert.equal(isAIEnrichmentRequestExpired({status:502,code:'enrichment_request_not_found'}),false);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_status_without_any_server_job_discards_stale_polling_state():
    run_node(r'''
const assert=require('node:assert/strict');
const saved=[{symbol:'DONE',status:'updated'}];
const state={aiEnrichment:{job:{request_id:'expired'},outcomes:saved,pending:false,resume:true,version:1}};
const renderAIEnrichment=()=>{};
const api=async()=>({active_job:null,last_job:null,items:[]});
''' + app_functions("expireAIEnrichmentRequest") + "\nasync " + app_functions("loadAIEnrichmentStatus") + r'''
(async()=>{
 await loadAIEnrichmentStatus();
 assert.equal(state.aiEnrichment.job,null);assert.equal(state.aiEnrichment.resume,false);
 assert.equal(state.aiEnrichment.outcomes,saved);
 assert.match(state.aiEnrichment.message,/no longer available/);
})().catch(error=>{console.error(error);process.exitCode=1});
''')
