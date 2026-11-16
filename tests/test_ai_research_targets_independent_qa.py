"""Independent frontend contracts for explicit AI targets and safe retries."""
from pathlib import Path
import subprocess

from test_shared_cash_risk_qa import app_functions


ROOT = Path(__file__).resolve().parents[1]


def node(source):
    completed = subprocess.run(["node"], input=source, cwd=ROOT, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr


def test_retry_preserves_failed_job_targets_and_refresh_policy_after_controls_change():
    node(r'''
const assert=require('node:assert/strict');
const oldJob={request_id:'failed-profile-job',position_scope:'all',ratings_only:false,data_types:['profile'],refresh_policy:'refresh_existing',status:'failed'};
const state={auth:{user:{id:'synthetic',role:'Operator'},forcedPasswordChange:false},aiEnrichment:{job:oldJob,pending:false,resume:false,ratingsOnly:false,message:'',timer:null,polls:0}};
const currentUser=()=>state.auth.user,canWrite=()=>true,renderAIEnrichment=()=>{},scheduleAIEnrichmentPoll=()=>{},appWarn=()=>{};
const window={AIResearchTargets:{isRisk:()=>false,requestOptions:job=>job?{data_types:job.data_types,refresh_policy:job.refresh_policy}:{data_types:['prices'],refresh_policy:'missing'}}};
let sent;
const api=async(path,options)=>{sent=JSON.parse(options.body);return {...oldJob,status:'queued'};};
const acceptAIEnrichmentJob=job=>state.aiEnrichment.job=job;
''' + "async " + app_functions("requestAIEnrichment") + r'''
(async()=>{
 await requestAIEnrichment('all',{resumeRequestId:oldJob.request_id});
 assert.deepEqual(sent,{position_scope:'all',ratings_only:false,data_types:['profile'],refresh_policy:'refresh_existing',resume_request_id:'failed-profile-job'});
 assert.equal(oldJob.status,'failed');
})().catch(error=>{console.error(error);process.exit(1);});
''')


def test_main_risk_target_uses_parent_scope_and_mode_and_preserves_retry_options():
    node(r'''
const assert=require('node:assert/strict');
const nodes={aiResearchTarget:{value:'risk_inputs'},aiResearchRefresh:{value:'refresh_existing'},aiRiskResearchMode:{value:'ai'}};
const document={getElementById:id=>nodes[id],addEventListener(){},dispatchEvent(){throw Error('An old session cannot publish UI refresh events');}};
const state={language:'he',auth:{user:{id:'synthetic',role:'Operator'},forcedPasswordChange:false},aiEnrichment:{ratingsOnly:false}};
const currentUser=()=>state.auth.user,canWrite=()=>true,t=x=>x;
const window={};const renderAIEnrichment=()=>{};
let scope;
const requestAIEnrichment=async value=>{scope=value;};
''' + (ROOT / "web/ai-research-targets.js").read_text() + r'''
(async()=>{
 assert.deepEqual(window.AIResearchTargets.requestOptions(),{data_types:['risk_inputs'],refresh_policy:'refresh_existing',risk_mode:'ai'});
 await window.AIResearchTargets.start('all');
 assert.equal(scope,'all');
 const old={data_types:['risk_inputs'],refresh_policy:'missing',risk_mode:'api'};
 assert.deepEqual(window.AIResearchTargets.requestOptions(old),old);
 window.AIResearchTargets.reset();
 assert.deepEqual(window.AIResearchTargets.requestOptions(),{data_types:['prices','profile','company_ratings','risk_inputs','country_ratings'],refresh_policy:'stale',risk_mode:'ai'});
})().catch(error=>{console.error(error);process.exit(1);});
''')


def test_bound_primary_office_address_is_only_a_domicile_proxy_not_an_economic_allocation():
    from app.risk_input_sources import extract_risk_records

    url = "https://www.sec.gov/Archives/edgar/data/1513363/000119312526449784/fdus-20260930.htm"
    candidate = dict(symbol="FDUS", stock_market="NASDAQ", name="Fidus Investment Corporation",
                     researched_issuer_name="Fidus Investment Corporation", researched_issuer_id="sec:1513363",
                     source_evidence=[dict(field="filing_sources", value=[dict(url=url, as_of="2026-09-30", published_at="2026-11-05")])])
    header = "Fidus Investment Corporation\n(Exact Name of Registrant as Specified in its Charter)\nCayman Islands\n(Jurisdiction of Incorporation)\n1603 Orrington Avenue, Suite 1005\nEvanston, Illinois 60201\n(Address of Principal Executive Offices) (Zip Code)"
    source = dict(url=url, text=header, observation_date="2026-09-30", published_at="2026-11-05", retrieved_at="2026-11-14T10:00:00Z")
    rows = extract_risk_records(source, candidate)
    fields = {row["field"]: row for row in rows}
    assert fields["country_code"]["value"] == "US"
    assert fields["country_code"]["basis"] == "issuer_domicile_proxy"
    assert fields["country_basis"]["value"] == "issuer_domicile_proxy"
    assert fields["country_code"]["as_of"] == "2026-09-30"
    assert "currency_exposures" not in fields and "country_currency" not in fields
    for invalid in [
        {**source, "url": url.replace("/1513363/", "/9999999/")},
        {**source, "url": url.replace("fdus-20260930.htm", "unbound-report.htm")},
        {**source, "text": "UNITED STATES SECURITIES AND EXCHANGE COMMISSION Washington, DC 20549\nFidus Investment Corporation\n(Exact Name of Registrant as Specified in its Charter)\nLondon, United Kingdom\n(Address of Principal Executive Offices)"},
    ]:
        values = {row["field"] for row in extract_risk_records(invalid, candidate)}
        assert not values & {"country_code", "country_basis", "country_currency", "currency_exposures"}
