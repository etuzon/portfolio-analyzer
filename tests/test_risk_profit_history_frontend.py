"""Risk/P&L presentation boundaries using server-derived comparison fixtures."""

from test_risk_history_frontend import run


def test_current_chart_uses_rounded_score_and_retains_uncapped_and_small_loss():
    run(r'''
const row=(day,score,loss)=>({id:day,model:'portfolio-risk-v4',date:'2026-11-'+day,observed_at:'2026-11-'+day+'T12:00:00Z',risk:{score,loss_pct:loss,net_equity:100,status:'ok'}});
const rows=[row('01',21,20.6),row('02',100,220),row('03',0,.004)];
const graph=riskHistoryGraph(rows,'Total');
assert.equal((graph.match(/<circle /g)||[]).length,3);
assert.ok(graph.includes('Stress-loss score: 21'));
assert.ok(graph.includes('20.60%') && graph.includes('220.00%') && graph.includes('0.0040%'));
assert.ok(!graph.includes('21/100'));
for(const value of [0,20,40,60,80,100])assert.ok(graph.includes('>'+value+'</text>'));
assert.equal(riskHistoryLossText({score:0,loss_pct:.00001}),'<0.0001%');
assert.equal(riskHistoryLossText({score:100,loss_pct:100,net_equity:-1}),'Unavailable');
''')


def test_daily_representative_retains_actual_same_day_baseline_and_account_scope():
    run(r'''
const baseline={status:'baseline',profit:null,currency:'ILS',baseline_date:'2026-11-01',baseline_observed_at:'2026-11-01T06:00:00Z',baseline_observation_id:'morning',segment_id:'total'};
const observed={...baseline,status:'recorded',profit:10};
const sample=(id,time,performance)=>({id,model:'portfolio-risk-v4',date:'2026-11-01',observed_at:'2026-11-01T'+time+':00Z',total:{score:21,loss_pct:20.6},performance:{total:performance,accounts:[{account_id:'zero',...performance,profit:performance.status==='recorded'?0:null}]},accounts:[]});
const data={items:[sample('morning','06:00',baseline),sample('afternoon','13:00',observed)]};
const rows=riskHistoryDailyRows(data,'');
assert.equal(rows.length,1);assert.equal(rows[0].id,'afternoon');assert.equal(rows[0].performance.profit,10);
assert.ok(riskHistoryBaselineText(rows[0].performance).startsWith('01/11/2026'));
assert.notEqual(riskHistoryBaselineText(rows[0].performance),riskHistoryObservedAt(rows[0].observed_at));
const zero=riskHistoryDailyRows(data,'zero');
assert.equal(zero.length,1);assert.equal(zero[0].risk,null);assert.equal(zero[0].performance.profit,0);
assert.equal(riskHistoryScoreText(zero[0]),'Risk unavailable');
assert.deepEqual(riskHistoryDailyRows(data,'missing'),[]);
''')


def test_profit_chart_never_plots_baseline_and_breaks_between_server_segments():
    run(r'''
const row=(day,status,profit,segment='one')=>({id:day,model:'portfolio-risk-v4',date:'2026-11-'+day,observed_at:'2026-11-'+day+'T12:00:00Z',risk:{score:21},performance:{status,profit,currency:'ILS',segment_id:segment,baseline_observation_id:segment,baseline_observed_at:'2026-11-01T12:00:00Z',reason_codes:status==='baseline'?['baseline_pending']:[]}});
const rows=[row('01','baseline',null),row('02','recorded',10),row('03','recorded',20),row('04','unavailable',null),row('05','recorded',-5,'two')];
const html=riskHistoryProfitGraph(rows,'Total');
assert.equal((html.match(/<circle /g)||[]).length,3);
const path=html.match(/<path d="([^"]*)"/)[1];
assert.equal((path.match(/M/g)||[]).length,2);assert.equal((path.match(/L/g)||[]).length,1);
assert.ok(html.includes('+10.00 ILS') && html.includes('-5.00 ILS'));
assert.equal(riskHistoryProfitNumber(rows[0].performance),null);
assert.ok(!riskHistoryProfitText(rows[0].performance).includes('0.00'));
assert.ok(riskHistoryPerformanceReasons({status:'unavailable',reason_codes:['ledger_revised']})[0].includes('changed or removed'));
''')


def test_reset_same_user_and_currency_change_fence_context_before_publication():
    run(r'''
(async()=>{
let resolveContext,calls=[];
api=(path)=>{calls.push(path);return new Promise(resolve=>resolveContext=resolve);};
const context={base_currency:'USD',account_ids:[],accounts:[],transactions:[],items:[],fx:{rate:3.5},token:'old'};
const old=recordRiskHistory();
resetRiskHistory();resolveContext(context);await old;
assert.equal(calls.length,1);assert.equal(riskHistoryView.captureError,'');
calls=[];const currency=recordRiskHistory();state.baseCurrency='ILS';resolveContext(context);await currency;
assert.equal(calls.length,1);assert.equal(riskHistoryView.captureError,'');
calls=[];const session=recordRiskHistory();state.auth.csrfToken='new-session';resolveContext(context);await session;
assert.equal(calls.length,1);assert.equal(riskHistoryView.captureError,'');
})().catch(error=>{console.error(error);process.exit(1);});
''')
