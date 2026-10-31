"""Financial score states must remain honest after rendering and reloading."""
from pathlib import Path
import re

from test_company_outlook_evaluation_frontend import run_js


SOURCE = (Path(__file__).resolve().parents[1] / "web/app.js").read_text()


def run_latest(body):
    start = re.search(r"^function renderCompanyOutlook\(", SOURCE, re.M).start()
    end = start + re.search(r"^}", SOURCE[start:], re.M).end()
    setup = r"""
const renderCompanyOutlookDiagram=()=>{};
for(const id of ['companyOutlookEmpty','companyOutlookResults','companyOutlookStatus','companyOutlookSummary','companyOutlookWords','companyOutlookTable'])nodes[id]={innerHTML:'',textContent:'',hidden:false};
const company=(symbol,score)=>({symbol,name:'',industry:'Computer Communications Equipment',fiscal_date:'2025-12-31',score,revenue_growth_percent:10,operating_margin_percent:15,net_margin_percent:10,free_cash_flow_margin_percent:8,current_ratio:2});
const analysis=()=>({symbol:'NEWT',model_version:'report-outlook-v5',score:67.3,label:'Good',score_status:'scored',direction:'positive',rank:1,ranked_company_count:3,rank_tied:true,confidence:'Medium',coverage:{available_weight:45,total_weight:45,percent:100,usable_peer_count:2,missing_metrics:[]},industry:{health:'Stable',score:50},score_component_limits:{company_fundamentals:100},score_components:{company_fundamentals:67.3},companies:[company('NEWT',67.3),company('PEER',48.2)],related_industries:[],missing:[],peer_source:'explicit industry cohort'});
"""
    run_js(SOURCE[start:end] + setup + body)


def test_insufficient_analysis_does_not_show_zero_or_weak_and_reports_remain_visible():
    run_latest(r"""
for(const language of ['he','en']){
 state.language=language;
 const item={...analysis(),score:null,label:'Insufficient data',score_status:'insufficient',direction:'inconclusive',rank:null,coverage:{available_weight:0,total_weight:45,percent:0,usable_peer_count:0,missing_metrics:['cash_conversion_percent','debt_to_revenue_percent'],reason:'industry_model_required'}};
 const original=JSON.stringify(item);
 renderCompanyOutlook(item);
 assert.equal(JSON.stringify(item),original);
 const summary=nodes.companyOutlookSummary.innerHTML;
 assert.ok(summary.includes(t('Insufficient data'))&&summary.includes('data-outlook-band="insufficient"'));
 assert.ok(!summary.includes('0/100')&&!summary.includes(t('Weak'))&&!summary.includes('1/3'));
 assert.ok(summary.includes(t('Comparison unavailable')));
 assert.ok(nodes.companyOutlookWords.innerHTML.includes(t('No forecast was saved. The available reports and missing measurements are shown below.')));
 assert.ok(nodes.companyOutlookWords.innerHTML.includes(t('This industry needs a specialized scoring model. Its reports remain available for review.')));
 assert.ok(nodes.companyOutlookTable.innerHTML.includes('31/12/2025')&&nodes.companyOutlookTable.innerHTML.includes('PEER'));
 assert.ok(!nodes.companyOutlookTable.innerHTML.includes('0/100'));
 const help=companyOutlookConfidenceHelp(item);
 assert.ok(help.includes(t('Cash conversion'))&&help.includes(t('Debt / revenue')));
 assert.ok(!/cash_conversion_percent|debt_to_revenue_percent/.test(help));
 if(language==='he') assert.ok(!/Insufficient|No forecast|Current ratio|Company signals|FCF margin|Comparison unavailable/.test(summary+nodes.companyOutlookWords.innerHTML+help));
 else assert.ok(!/[א-ת]/.test(summary+nodes.companyOutlookWords.innerHTML+help));
}
""")


def test_current_formula_uses_100_point_financial_scores_and_explicit_tied_rank():
    run_latest(r"""
for(const language of ['he','en']){
 state.language=language;
 const item=analysis();
 renderCompanyOutlook(item);
 assert.ok(nodes.companyOutlookSummary.innerHTML.includes('67.3/100'));
 assert.ok(nodes.companyOutlookSummary.innerHTML.includes(t('Tied {rank}/{count}').replace('{rank}','1').replace('{count}','3')));
 assert.ok(!nodes.companyOutlookSummary.innerHTML.includes(t('Industry score')));
 assert.ok(nodes.companyOutlookSummary.innerHTML.includes(t('Analysis data coverage')));
 const table=nodes.companyOutlookTable.innerHTML;
 assert.ok(table.includes('67.3/100')&&table.includes('48.2/100'));
 assert.ok(!table.includes('149.6/100'));
 const help=companyOutlookScoreHelp(item);
 assert.ok(help.includes(t('Good: 65 to below 80.')));
 assert.ok(help.includes(t('The score compares annual growth, profitability, cash flow and balance-sheet measures with comparable companies. Industry and related-company information is context and does not add points.')));
 const mixed={...item,score:40,label:'Mixed'};
 assert.ok(companyOutlookScoreHelp(mixed).includes(t('Mixed: 35 to below 65.')));
 const legacy={...record(),score:40,label:'Weak'};
 assert.ok(companyOutlookScoreHelp(legacy).includes(t('Weak: below 50.')));
}
""")


def test_retryable_comparison_can_be_checked_again_and_freezes_the_saved_contract():
    run_js(r"""
(async()=>{
 state.language='he';
 const contract={version:'peer-revenue-margin-v1',minimum_peers:2,require_full_cohort:true,revenue_tolerance_pp:1,margin_tolerance_pp:0.5};
 const item={...record(),model_version:'report-outlook-v5',actual_direction:'inconclusive',accuracy_score:null,actual:{retryable:true},baseline:{...record().baseline,model_version:'report-outlook-v5',evaluation_contract:contract,rank:1,rank_tied:true,coverage:{available_weight:45,total_weight:45,percent:100,usable_peer_count:2,missing_metrics:[]}}};
 const sibling={...record('p2'),symbol:item.symbol};
 renderCompanyOutlookHistory(data([item,sibling]));
 const text=nodes.companyOutlookHistory.innerHTML;
 assert.ok(text.includes(t('Comparison data unavailable')));
 assert.ok(text.includes('data-evaluate-company-outlook="p1"'));
 assert.ok(companyOutlookEvaluationHelp(item).includes('0.5'));
 assert.ok(companyOutlookEvaluationHelp(item).includes(t('All comparison companies saved with this forecast must have usable reports.')));
 const original=JSON.stringify(item.baseline);
 const checking=evaluateCompanyOutlookPrediction('p2');
 assert.equal(cards.get('p1').querySelector('[data-evaluate-company-outlook]').disabled,true);
 assert.equal(cards.get('p2').querySelector('[data-evaluate-company-outlook]').disabled,true);
 const result={...item,actual_direction:'positive',accuracy_score:100,actual:{retryable:false},evaluation:'Prediction evaluated'};
 requests[0].resolve({...sibling,checked_predictions:[result,sibling],failed_prediction_ids:[]});
 await flush();requests[1].resolve(data([result,sibling]));await checking;
 assert.equal(JSON.stringify(state.companyOutlookHistory[0].baseline),original);
 const final=nodes.companyOutlookHistory.innerHTML;
 assert.ok(final.includes(t('Evaluation grade'))&&final.includes('100/100'));
 assert.ok(!final.includes('data-evaluate-company-outlook="p1"'));
})().catch(error=>{console.error(error);process.exitCode=1});
""")


def test_unscored_history_and_legacy_records_render_without_mutating_saved_evidence():
    run_js(r"""
for(const language of ['he','en']){
 state.language=language;
 const unscored={...record(),score:null,model_version:'report-outlook-v5',score_status:'insufficient',label:'Insufficient data'};
 const legacy={...record('p2'),actual_direction:'positive',accuracy_score:50};
 const original=JSON.stringify([unscored,legacy]);
 renderCompanyOutlookHistory(data([unscored,legacy]));
 assert.equal(JSON.stringify(state.companyOutlookHistory),original);
 const html=nodes.companyOutlookHistory.innerHTML;
 assert.ok(html.includes(t('Unscored'))&&html.includes(t('Insufficient data')));
 assert.ok(!html.includes('null/100'));
 assert.ok(html.includes('45/100')&&html.includes('50/100'));
 assert.ok(html.includes(t('This saved forecast retains the earlier scoring and evaluation rules. Its evaluation grade is not independent evidence for the current formula.')));
 assert.ok(nodes.companyOutlookScorecard.innerHTML.includes(t('Evaluation grade')));
 assert.ok(!nodes.companyOutlookScorecard.innerHTML.includes(t('75% target met')));
}
""")


def test_current_evaluation_messages_and_validation_reasons_are_localized():
    run_js(r"""
const messages=[
 'The next annual report is missing a comparable period or verified filing date. Check again when the missing report data is available.',
 'The newer annual report is available, but comparable revenue growth, net margin or peer reports are incomplete. Check again when the missing data is available.',
 'Next-annual revenue growth and net margin both exceeded peer medians beyond the saved tolerances.',
 'Next-annual revenue growth and net margin both fell below peer medians beyond the saved tolerances.',
 'Next-annual revenue growth and net margin were mixed or within the saved peer tolerances.',
 'No forecast was issued because comparable baseline evidence is incomplete.',
];
for(const language of ['he','en']){
 state.language=language;
 for(const evaluation of messages){
  const item={...record(),actual_direction:'inconclusive',actual:{retryable:true},evaluation};
  assert.equal(companyOutlookEvaluationMessage(item),t(evaluation));
  assert.equal(companyOutlookCheckStatus(item).help,evaluation);
  if(language==='he')assert.ok(!/[A-Za-z]/.test(companyOutlookEvaluationMessage(item)));
  else assert.ok(!/[א-ת]/.test(companyOutlookEvaluationMessage(item)));
 }
 const result=data();
 result.scorecard.quality_gate={passed:false,eligible_count:0,legacy_count:30,minimum_evaluated_predictions:30,failed_reasons:['insufficient_observations','accuracy_below_target','confidence_bound_below_target']};
 renderCompanyOutlookHistory(result);
 const html=nodes.companyOutlookScorecard.innerHTML;
 assert.ok(html.includes('0/30')&&html.includes(t('Not validated')));
 assert.ok(html.includes(t('Earlier forecasts excluded: {count}.').replace('{count}','30')));
 assert.ok(!/insufficient_observations|accuracy_below_target|confidence_bound_below_target/.test(html));
 if(language==='he')assert.ok(!/More distinct|Validation applies|Not validated/.test(html));
 else assert.ok(!/[א-ת]/.test(html));
}
""")
