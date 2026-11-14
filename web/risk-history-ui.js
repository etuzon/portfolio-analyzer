/* Recorded dashboard-client assessments. Values are never backfilled or recalculated. */
let riskHistoryView = { version:0, data:null, account:"", accountLabel:"", days:"90", loadedDays:null, loading:false, error:"", captureError:"", selectedObservation:"" };
let riskHistoryCaptureTask = null;
let riskHistoryCaptureScope = null;
let riskHistoryCaptureGeneration = 0;
const RISK_HISTORY_HE = {
  "Risk history":"היסטוריית סיכון", "Total portfolio":"כל התיק", "Account":"חשבון", "Last 30 days":"30 הימים האחרונים", "Last 90 days":"90 הימים האחרונים", "Last year":"השנה האחרונה", "All history":"כל ההיסטוריה", "Period":"תקופה", "Reload":"טעינה מחדש", "Loading risk history…":"טוען היסטוריית סיכון…", "Could not load risk history. Use Reload to retry.":"לא ניתן לטעון את היסטוריית הסיכון. לחצו על טעינה מחדש כדי לנסות שוב.", "No observations yet. Recording begins with the first saved dashboard assessment.":"אין עדיין מדידות. ההיסטוריה מתחילה מהערכת הסיכון הראשונה שנשמרה מלוח הבקרה.", "No observations for this account and period.":"אין מדידות לחשבון ולתקופה שנבחרו.", "Only one observation is available.":"קיימת מדידה אחת בלבד.", "Score":"ציון", "Observed at":"מועד המדידה", "Risk details":"פירוט הסיכון", "Daily observations":"מדידות יומיות", "Risk score (0–100)":"ציון סיכון (0–100)", "Base currency":"מטבע בסיס", "Model":"מודל", "Latest observation per day; days without observations remain gaps.":"המדידה האחרונה בכל יום; ימים ללא מדידות נשארים כפערים בגרף.", "Recorded model assessments, excluding employee equity. Holdings filters do not change this history.":"הערכות מודל סיכון שנשמרו, ללא תגמול הוני לעובדים. מסנני ההחזקות אינם משנים היסטוריה זו.", "The browser calculates the existing model. History is saved when an Admin or Operator loads a completed dashboard; Viewers can read saved history.":"הדפדפן מחשב את המודל הקיים. ההיסטוריה נשמרת כשמנהל או מפעיל טוען לוח בקרה שהשלים את הטעינה; צופים יכולים לקרוא היסטוריה שמורה.", "A current observation could not be saved. Wait for analytics to finish or refresh the dashboard, then Reload.":"לא ניתן לשמור מדידה נוכחית. המתינו לסיום טעינת הניתוח או רעננו את לוח הבקרה, ואז לחצו על טעינה מחדש.", "Older observations are omitted from this view.":"מדידות ישנות יותר אינן מוצגות בתצוגה זו.", "Some stored observations could not be read.":"לא ניתן לקרוא חלק מהמדידות השמורות.", "Saved FX is used for recorded assessments. Current badges may use newer or different FX.":"ההערכות השמורות משתמשות בשערי מטבע שמורים. סמלי הסיכון הנוכחיים עשויים להשתמש בשערים חדשים או שונים.", "Current data issues":"פערי הנתונים הנוכחיים", "Limited data":"נתונים מוגבלים", "No risk data gaps":"אין פערים בנתוני הסיכון"
};
function riskHistoryText(text) { return state.language === "he" ? RISK_HISTORY_HE[text] || t(text) : text; }
function riskHistoryEsc(text) { return esc(riskHistoryText(text)); }
function riskHistoryScaleHeading(text) { return riskHistoryEsc(text).replaceAll('0–100','<bdi dir="ltr">0–100</bdi>'); }
function resetRiskHistory() {
  riskHistoryCaptureGeneration++;
  riskHistoryView = {version:riskHistoryView.version+1,data:null,account:"",accountLabel:"",days:"90",loadedDays:null,loading:false,error:"",captureError:"",selectedObservation:""};
  riskHistoryCaptureTask = null;
  riskHistoryCaptureScope = null;
}
function riskHistoryRiskRecord(risk) {
  if (["portfolio-risk-v3", "portfolio-risk-v4"].includes(risk.model)) {
    const fields=["model","score_unit","score_scale","scenario_horizon","status","score","estimated_score","provisional_model","provisional_score","provisional_basis","provisional_loss","provisional_loss_pct","provisional_known_loss_pct","provisional_unmodeled_gross","provisional_net_equity","provisional_proxy_gross","provisional_assumptions","provisional_scope","provisional_range","provisional_worst_scenario","provisional_scenarios","loss_pct","stress_loss","worst_scenario","net_equity","cash_debt","cash_pct","components","quality_details","gaps","assumptions","coverage","funding","scenarios","rating_evidence","forward_sensitivity","as_of","source_revision"];
    return Object.fromEntries(fields.filter(key=>risk[key] !== undefined).map(key=>[key,risk[key]]));
  }
  const result = { score:risk.score, components:risk.components || {}, quality_details:risk.quality_details || [], drivers:risk.drivers || [] };
  for (const field of ["cash_pct","cash_debt","net_equity","unlevered_score"]) if (Number.isFinite(risk[field])) result[field]=risk[field];
  return result;
}
function riskHistoryCalculate(context) {
  const fields=["baseCurrency","fxRates","coreFxRates","bannerFxRates","localAccounts","localTransactions","language","riskAsOf","riskRevision","localFunds"];
  const previous=Object.fromEntries(fields.map(key=>[key,state[key]]));
  try {
    state.baseCurrency=context.base_currency;
    state.localAccounts=context.accounts;
    state.localTransactions=context.transactions;
    state.riskAsOf=context.observed_at;
    state.riskRevision=context.fingerprint;
    state.localFunds=context.unmodeled_funds || [];
    state.language="en"; // Freeze stable driver text; presentation translates at read time.
    state.bannerFxRates={};
    setCoreFxRates(context.fx);
    return portfolioRiskSnapshot(portfolioItems(context.items));
  } finally { for (const field of fields) state[field]=previous[field]; }
}
async function recordRiskHistory() {
  if (!canWrite()) return;
  const scope={generation:riskHistoryCaptureGeneration,userId:state.auth?.user?.id,currency:state.baseCurrency || "ILS",session:state.auth?.csrfToken};
  const isCurrent=()=>scope.generation===riskHistoryCaptureGeneration && scope.userId===state.auth?.user?.id
    && scope.currency===(state.baseCurrency || "ILS") && scope.session===state.auth?.csrfToken;
  if (riskHistoryCaptureTask && riskHistoryCaptureScope && Object.keys(scope).every(key=>scope[key]===riskHistoryCaptureScope[key])) return riskHistoryCaptureTask;
  const task=(async()=>{
    try {
      const context=await api(`/api/portfolio/risk-history/context?base_currency=${encodeURIComponent(scope.currency)}`);
      if (!isCurrent()) return;
      const snapshot=riskHistoryCalculate(context);
      const expected=[...context.account_ids].sort(), actual=snapshot.accounts.map(row=>row.key).sort();
      if (JSON.stringify(expected)!==JSON.stringify(actual)) throw new Error("scope");
      if (!isCurrent()) return;
      await api("/api/portfolio/risk-history", {method:"POST",body:JSON.stringify({token:context.token,total:riskHistoryRiskRecord(snapshot.total),accounts:snapshot.accounts.map(row=>({account_id:row.key,risk:riskHistoryRiskRecord(row.risk)}))})});
      if(isCurrent())riskHistoryView.captureError="";
    } catch {
      if(isCurrent())riskHistoryView.captureError="A current observation could not be saved. Wait for analytics to finish or refresh the dashboard, then Reload.";
    }
  })();
  riskHistoryCaptureTask=task;
  riskHistoryCaptureScope=scope;
  try { await task; } finally { if(riskHistoryCaptureTask===task){riskHistoryCaptureTask=null;riskHistoryCaptureScope=null;} }
}
async function loadRiskHistory({capture=true}={}) {
  const version=++riskHistoryView.version,userId=state.auth?.user?.id,days=riskHistoryView.days,currency=state.baseCurrency || "ILS";
  riskHistoryView.loading=true;riskHistoryView.error="";renderRiskHistory();
  try {
    if(capture)await recordRiskHistory();
    const params=new URLSearchParams({base_currency:currency,days});
    const data=await api(`/api/portfolio/risk-history?${params}`);
    if(version!==riskHistoryView.version || userId!==state.auth?.user?.id || currency!==(state.baseCurrency || 'ILS'))return;
    riskHistoryView.data=data;
    riskHistoryView.loadedDays=days;
  } catch { if(version===riskHistoryView.version && userId===state.auth?.user?.id && currency===(state.baseCurrency || 'ILS'))riskHistoryView.error="Could not load risk history. Use Reload to retry."; }
  finally { if(version===riskHistoryView.version && userId===state.auth?.user?.id){riskHistoryView.loading=false;renderRiskHistory();} }
}
function riskHistoryDailyRows(data,account) {
  const days=new Map();
  for(const sample of data?.items || []) {
    const performance=account ? sample.performance?.accounts?.find(row=>row.account_id===account) : sample.performance?.total;
    const risk=(account ? sample.accounts?.find(row=>row.account_id===account)?.risk : sample.total) || performance?.risk || null;
    if(!risk && !performance)continue;
    const key=`${sample.date}|${sample.model}`;
    const previous=days.get(key);
    if(!previous || sample.observed_at>previous.observed_at)days.set(key,{...sample,risk,performance});
  }
  return [...days.values()].sort((a,b)=>a.date.localeCompare(b.date)||a.observed_at.localeCompare(b.observed_at));
}
function riskHistoryLegacyGraph(rows,label) {
  if(!rows.length)return "";
  const models=[...new Set(rows.map(row=>row.model))];
  if(models.length>1)return models.map(model=>`<section class="risk-history-model"><h4>${esc(model)} · ${riskHistoryEsc(model === "portfolio-risk-v4" ? "Stress loss (%)" : "Legacy risk index (0–100)")}</h4>${riskHistoryGraph(rows.filter(row=>row.model===model),label)}</section>`).join("");
  const current=models[0]==="portfolio-risk-v4";
  const width=920,height=300,left=48,right=20,top=20,bottom=48;
  const times=rows.map(row=>Date.parse(`${row.date}T00:00:00Z`));
  const min=times[0],max=times.at(-1),span=max-min;
  const points=rows.map((row,index)=>{
    const ranged=["portfolio-risk-provisional-v2","portfolio-risk-provisional-v3"].includes(row.risk.provisional_model) && row.risk.provisional_scope==="known_values";
    const point=Number.isFinite(row.risk.score)?row.risk.score:Number.isFinite(row.risk.estimated_score)?row.risk.estimated_score:ranged?null:row.risk.provisional_score;
    const value=current ? Number.isFinite(point) ? Number.isFinite(row.risk.loss_pct) ? row.risk.loss_pct : !ranged ? row.risk.provisional_loss_pct : null : null : point;
    return {...row,index,value,x:span?left+(times[index]-min)/span*(width-left-right):width/2};
  });
  const ceiling=current ? Math.max(100,...points.map(point=>Number.isFinite(point.value)?Math.ceil(point.value/20)*20:0)) : 100;
  points.forEach(point=>{point.y=Number.isFinite(point.value)?top+(ceiling-point.value)/ceiling*(height-top-bottom):null;});
  if(!points.some(p=>p.y!==null))return "";
  let path="";
  points.forEach((point,index)=>{
    if(point.y===null)return;
    const previous=points[index-1];
    const linked=previous?.y!==null && previous && point.model===previous.model && point.risk.status===previous.risk.status
      && point.risk.provisional_model===previous.risk.provisional_model && times[index]-times[index-1]===86400000;
    path+=`${linked?"L":"M"}${point.x.toFixed(2)},${point.y.toFixed(2)} `;
  });
  const ticks=Array.from({length:6},(_,index)=>ceiling*index/5).map(score=>{const y=top+(ceiling-score)/ceiling*(height-top-bottom);return `<line x1="${left}" x2="${width-right}" y1="${y}" y2="${y}" class="risk-history-grid"/><text x="${left-10}" y="${y+4}" text-anchor="end">${Number(score.toFixed(1))}${current?"%":""}</text>`;}).join("");
  const dots=points.filter(p=>p.y!==null).map(point=>{
    const provisional=!Number.isFinite(point.risk.score) && !Number.isFinite(point.risk.estimated_score) && Number.isFinite(point.risk.provisional_score);
    const description=`${riskHistoryObservedAt(point.observed_at)}\n${riskHistoryText("Model")}: ${point.model}\n${riskHistoryText(current?"Stress loss":"Legacy risk index")}: ${point.risk.status==="estimate" || provisional?"~":""}${current?point.value.toFixed(1):point.value}${current?"%":"/100"}${provisional?` ⚠ ${riskHistoryText("Partial data")}`:""}`;
    return `<circle cx="${point.x}" cy="${point.y}" r="4" tabindex="0" aria-label="${esc(description)}"><title>${esc(description)}</title></circle>`;
  }).join("");
  const indices=[...new Set([0,Math.floor((points.length-1)/2),points.length-1])];
  return `<div class="risk-history-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(`${label}: ${riskHistoryText(current?"Stress loss (%)":"Legacy risk index (0–100)")}`)}"><g>${ticks}<path d="${path}" class="risk-history-line"/>${dots}${indices.map(index=>`<text x="${points[index].x}" y="${height-16}" text-anchor="middle">${esc(formatDate(points[index].date))}</text>`).join("")}</g></svg></div>`;
}
function riskHistoryObservedAt(value) {
  const date=new Date(value);
  if(Number.isNaN(date.getTime()))return String(value || '');
  const parts=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Jerusalem',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).formatToParts(date).map(part=>[part.type,part.value]));
  return `${parts.day}/${parts.month}/${parts.year} ${parts.hour}:${parts.minute}`;
}
function riskHistoryNumber(value,digits=1) {
  return new Intl.NumberFormat(state.language==='he'?'he-IL':'en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits}).format(value);
}
function riskHistoryLossValue(risk) {
  if(!risk)return null;
  const automatic=['portfolio-risk-provisional-v2','portfolio-risk-provisional-v3'].includes(risk.provisional_model)
    && !Number.isFinite(risk.score) && !Number.isFinite(risk.estimated_score);
  if(automatic && (risk.provisional_scope==='known_values' || risk.provisional_range))return null;
  const equity=automatic?risk.provisional_net_equity:risk.net_equity;
  if(Number.isFinite(equity) && equity<=0)return null;
  if(typeof stressRiskLossPercent==='function')return stressRiskLossPercent(risk);
  const value=automatic?risk.provisional_loss_pct:risk.loss_pct;
  return Number.isFinite(value) && value>=0?value:null;
}
function riskHistoryLossText(risk) {
  const value=riskHistoryLossValue(risk);
  if(value===null)return riskHistoryText('Unavailable');
  const prefix=!Number.isFinite(risk?.score)?'~':'';
  if(typeof stressRiskExactPercent==='function')return `${prefix}${stressRiskExactPercent(value)}`;
  if(value>0 && value<0.0001)return `${prefix}<0.0001%`;
  const digits=value>0 && value<0.01?4:2;
  return `${prefix}${riskHistoryNumber(value,digits)}%`;
}
function riskHistoryScoreValue(risk,model) {
  if(!risk)return null;
  if(model==='portfolio-risk-v4' && typeof stressRiskDisplay==='function') {
    const display=stressRiskDisplay({...risk,model});
    return display.unknownScope || display.nonpositiveEquity || display.rawLossPct===null?null:display.compatibilityScore;
  }
  const automatic=['portfolio-risk-provisional-v2','portfolio-risk-provisional-v3'].includes(risk.provisional_model);
  if(automatic && (risk.provisional_scope==='known_values' || risk.provisional_range))return null;
  if(model==='portfolio-risk-v4') {
    const equity=automatic && !Number.isFinite(risk.score) && !Number.isFinite(risk.estimated_score)?risk.provisional_net_equity:risk.net_equity;
    if(Number.isFinite(equity) && equity<=0)return null;
  }
  const value=Number.isFinite(risk.score)?risk.score:Number.isFinite(risk.estimated_score)?risk.estimated_score:risk.provisional_score;
  return Number.isFinite(value) && value>=0 && value<=100?value:null;
}
function riskHistoryScoreText(row) {
  const value=riskHistoryScoreValue(row.risk,row.model);
  if(value===null)return riskHistoryText('Risk unavailable');
  const estimated=!Number.isFinite(row.risk?.score);
  return `${estimated?'~':''}${riskHistoryNumber(value,0)}${row.model==='portfolio-risk-v4'?'':'/100'}`;
}
function riskHistoryObservationKey(row) { return String(row.id || `${row.observed_at}|${row.model || ''}`); }
function riskHistoryBaselineText(performance) {
  return performance?.baseline_observed_at?riskHistoryObservedAt(performance.baseline_observed_at)
    : performance?.baseline_date?formatDate(performance.baseline_date):'';
}
function riskHistoryProfitNumber(performance) {
  return performance?.status==='recorded' && typeof performance.profit==='number' && Number.isFinite(performance.profit)?performance.profit:null;
}
function riskHistoryProfitText(performance) {
  const value=riskHistoryProfitNumber(performance);
  return value===null?riskHistoryText(performance?.status==='baseline'?'Waiting for a later observation':'Unavailable')
    : `${value>0?'+':''}${riskHistoryNumber(value,2)} ${performance.currency || ''}`.trim();
}
function riskHistoryPerformanceReasons(performance) {
  const reasons={
    baseline_pending:'A later comparable observation is needed to measure P&L.',
    missing_performance_evidence:'This observation has no saved P&L evidence.',
    missing_valuation:'Required saved valuations are missing.',
    stale_valuation:'Saved valuations are too old for this comparison.',
    missing_flow_fx:'An exchange rate from a cash-flow date is missing.',
    ledger_revised:'Previously recorded transactions were changed or removed.',
    retroactive_activity:'Activity was added with a date before the baseline.',
    in_kind_flow_unvalued:'A transfer of securities has no verified transfer-date value.',
    positions_unreconciled:'Position changes do not reconcile with recorded transactions.',
    opening_cash_changed:'The account opening cash changed.',
    account_currency_changed:'The account currency changed.',
    scope_changed:'The accounts included in this comparison changed.',
    model_changed:'The risk model changed.',
    reset_epoch_changed:'History was restarted.',
    unclassified_cash_adjustment:'A cash adjustment has not been classified as a capital flow or investment activity.',
    activity_timing_unknown:'The timing of new activity relative to the baseline is unknown.',
    valuation_revised:'A valuation from the baseline or an earlier date was revised.'
  };
  if(!performance)return [riskHistoryText(reasons.missing_performance_evidence)];
  const codes=Array.isArray(performance.reason_codes)?performance.reason_codes:[];
  if(performance.status==='baseline' && !codes.length)return [riskHistoryText(reasons.baseline_pending)];
  const result=[...new Set(codes.map(code=>riskHistoryText(reasons[code] || 'Comparable P&L inputs are unavailable.')))];
  return result.length?result:riskHistoryProfitNumber(performance)!==null?[]:[riskHistoryText('Comparable P&L inputs are unavailable.')];
}
function riskHistoryPlot(rows,points,{label,minimum,maximum,profit=false,linked}) {
  if(!points.some(point=>Number.isFinite(point.value)))return '';
  const target=typeof $==='function'?$('riskHistoryContent'):null;
  const width=Math.max(320,Math.min(920,target?.clientWidth || 920)),height=218,left=76,right=16,top=18,bottom=40;
  const times=rows.map(row=>Date.parse(`${row.date}T00:00:00Z`));
  const start=Math.min(...times),end=Math.max(...times),span=end-start;
  const xFor=index=>span?left+(times[index]-start)/span*(width-left-right):left+(width-left-right)/2;
  const yFor=value=>top+(maximum-value)/(maximum-minimum)*(height-top-bottom);
  const selected=riskHistoryView.selectedObservation || riskHistoryObservationKey(rows.at(-1));
  let path='';
  points.forEach((point,index)=>{
    point.x=xFor(index);point.y=Number.isFinite(point.value)?yFor(point.value):null;
    if(point.y===null)return;
    const previous=points[index-1];
    const connects=previous && previous.y!==null && times[index]-times[index-1]===86400000 && linked(rows[index-1],rows[index]);
    path+=`${connects?'L':'M'}${point.x.toFixed(2)},${point.y.toFixed(2)} `;
  });
  const axis=value=>profit?new Intl.NumberFormat(state.language==='he'?'he-IL':'en-US',{notation:'compact',maximumFractionDigits:1}).format(value):riskHistoryNumber(value,0);
  const ticks=Array.from({length:6},(_,index)=>minimum+(maximum-minimum)*index/5).map(value=>{
    const y=yFor(value);
    return `<line x1="${left}" x2="${width-right}" y1="${y}" y2="${y}" class="${Math.abs(value)<1e-10?'risk-history-zero':'risk-history-grid'}"/><text x="${left-10}" y="${y+4}" text-anchor="end">${esc(axis(value))}</text>`;
  }).join('');
  const focusIndex=points.findIndex((point,index)=>point.y!==null && riskHistoryObservationKey(rows[index])===selected);
  const firstPoint=points.findIndex(point=>point.y!==null);
  const circle=points.map((point,index)=>point.y===null?'':`<circle id="riskHistory${profit?'Profit':'Score'}Point-${esc(encodeURIComponent(riskHistoryObservationKey(rows[index])))}" data-risk-history-point="${esc(riskHistoryObservationKey(rows[index]))}" class="${riskHistoryObservationKey(rows[index])===selected?'is-active':''}" cx="${point.x}" cy="${point.y}" r="4.5" role="button" aria-pressed="${riskHistoryObservationKey(rows[index])===selected}" tabindex="${index===(focusIndex<0?firstPoint:focusIndex)?'0':'-1'}" aria-label="${esc(point.description)}"><title>${esc(point.description)}</title></circle>`).join('');
  const indices=[...new Set(width<600?[0,rows.length-1]:[0,Math.floor((rows.length-1)/2),rows.length-1])];
  const dates=indices.map((index,position)=>`<text x="${xFor(index)}" y="${height-12}" text-anchor="${indices.length===1?'middle':position===0?'start':position===indices.length-1?'end':'middle'}">${esc(formatDate(rows[index].date))}</text>`).join('');
  const selectedIndex=rows.findIndex(row=>riskHistoryObservationKey(row)===selected);
  const cursorX=selectedIndex<0?left:xFor(selectedIndex);
  return `<div class="risk-history-chart${profit?' risk-history-profit':''}"><svg viewBox="0 0 ${width} ${height}" data-risk-history-start="${start}" data-risk-history-end="${end}" role="group" aria-label="${esc(label)}"><g>${ticks}<line class="risk-history-cursor" data-risk-history-cursor x1="${cursorX}" x2="${cursorX}" y1="${top}" y2="${height-bottom}"${selectedIndex<0?' visibility="hidden"':''}/><path d="${path}" class="risk-history-line"/>${circle}${dates}</g></svg></div>`;
}
function riskHistoryGraph(rows,label) {
  if(!rows.length)return '';
  const models=[...new Set(rows.map(row=>row.model))];
  if(models.length>1)return models.map(model=>`<section class="risk-history-model"><h4>${esc(model)} · ${riskHistoryScaleHeading(model==='portfolio-risk-v4'?'Stress-loss score (0–100)':'Legacy risk index (0–100)')}</h4>${riskHistoryGraph(rows.filter(row=>row.model===model),label)}</section>`).join('');
  if(models[0]!=='portfolio-risk-v4')return riskHistoryLegacyGraph(rows.filter(row=>row.risk),label);
  const points=rows.map(row=>({value:riskHistoryScoreValue(row.risk,row.model),description:[riskHistoryObservedAt(row.observed_at),`${riskHistoryText('Stress-loss score')}: ${riskHistoryScoreText(row)}`,`${riskHistoryText('Scenario loss (%)')}: ${riskHistoryLossText(row.risk)}`,!Number.isFinite(row.risk?.score)?riskHistoryText('Estimate'):''].filter(Boolean).join('\n')}));
  return riskHistoryPlot(rows,points,{label:`${label}: ${riskHistoryText('Stress-loss score (0–100)')}`,minimum:0,maximum:100,linked:(previous,current)=>previous.model===current.model && previous.base_currency===current.base_currency && previous.reset_epoch===current.reset_epoch && previous.risk?.status===current.risk?.status && previous.risk?.provisional_model===current.risk?.provisional_model && (!previous.performance?.segment_id && !current.performance?.segment_id || previous.performance?.segment_id===current.performance?.segment_id)});
}
function riskHistoryProfitGraph(rows,label) {
  const points=rows.map(row=>({value:riskHistoryProfitNumber(row.performance),description:[riskHistoryObservedAt(row.observed_at),`${riskHistoryText('P&L after recorded cash flows')}: ${riskHistoryProfitText(row.performance)}`,`${riskHistoryText('Baseline')}: ${riskHistoryBaselineText(row.performance)}`].join('\n')}));
  const values=points.map(point=>point.value).filter(value=>Number.isFinite(value));
  if(!values.length)return `<p class="risk-history-chart-empty">${riskHistoryEsc(rows.some(row=>row.performance?.status==='baseline')?'A later comparable observation is needed to measure P&L.':'No comparable P&L observations. Review the reasons in the table.')}</p>`;
  const low=Math.min(0,...values),high=Math.max(0,...values),span=high-low,padding=span?span*.1:1;
  const currency=rows.find(row=>row.performance?.currency)?.performance.currency || state.baseCurrency;
  return riskHistoryPlot(rows,points,{label:`${label}: ${riskHistoryText('P&L after recorded cash flows')} (${currency})`,minimum:low<0?low-padding:0,maximum:high>0?high+padding:low<0?0:padding,profit:true,
    linked:(previous,current)=>previous.performance?.status==='recorded' && current.performance?.status==='recorded' && Boolean(current.performance.segment_id) && previous.performance.segment_id===current.performance.segment_id && previous.performance.baseline_observation_id===current.performance.baseline_observation_id && previous.performance.currency===current.performance.currency});
}
function riskHistoryReadout(row) {
  if(!row)return '';
  const baseline=riskHistoryBaselineText(row.performance),reasons=riskHistoryPerformanceReasons(row.performance);
  return `<strong class="risk-history-readout-date"><bdi>${esc(riskHistoryObservedAt(row.observed_at))}</bdi></strong><span>${riskHistoryEsc(row.model==='portfolio-risk-v4'?'Stress-loss score':'Legacy risk index')}: <strong><bdi>${esc(riskHistoryScoreText(row))}</bdi></strong></span><span>${riskHistoryEsc('Scenario loss (%)')}: <strong><bdi>${esc(riskHistoryLossText(row.risk))}</bdi></strong></span><span>${riskHistoryEsc('P&L after recorded cash flows')}: <strong${riskHistoryProfitNumber(row.performance)===null?' class="risk-history-pending"':''}><bdi>${esc(riskHistoryProfitText(row.performance))}</bdi></strong></span>${baseline?`<small>${riskHistoryEsc('Baseline')}: <bdi>${esc(baseline)}</bdi></small>`:''}${reasons.length?`<small>${esc(reasons.join(' '))}</small>`:''}`;
}
function selectRiskHistoryObservation(key) {
  const rows=riskHistoryDailyRows(riskHistoryView.data,riskHistoryView.account),row=rows.find(row=>riskHistoryObservationKey(row)===key);
  if(!row)return;
  riskHistoryView.selectedObservation=key;
  const readout=$('riskHistoryReadout');if(readout)readout.innerHTML=riskHistoryReadout(row);
  const target=$('riskHistoryContent');
  target?.querySelectorAll('[data-risk-history-point]').forEach(node=>{const selected=node.getAttribute('data-risk-history-point')===key;node.classList.toggle('is-active',selected);node.setAttribute('aria-pressed',String(selected));node.setAttribute('tabindex',selected?'0':'-1');});
  target?.querySelectorAll('[data-risk-history-row]').forEach(node=>node.classList.toggle('is-active',node.getAttribute('data-risk-history-row')===key));
  target?.querySelectorAll('svg').forEach(svg=>{
    const cursor=svg.querySelector('[data-risk-history-cursor]');
    const point=[...svg.querySelectorAll('[data-risk-history-point]')].find(node=>node.getAttribute('data-risk-history-point')===key);
    if(cursor){
      const start=Number(svg.getAttribute('data-risk-history-start')),end=Number(svg.getAttribute('data-risk-history-end')),time=Date.parse(`${row.date}T00:00:00Z`),width=svg.viewBox.baseVal.width;
      const x=point?point.getAttribute('cx'):end===start?76+(width-92)/2:76+(time-start)/(end-start)*(width-92);
      cursor.setAttribute('visibility',time>=start && time<=end?'visible':'hidden');cursor.setAttribute('x1',x);cursor.setAttribute('x2',x);
      if(!point)svg.querySelector('[data-risk-history-point]')?.setAttribute('tabindex','0');
    }
  });
}
function riskHistorySummary(rows) {
  const row=rows.at(-1);if(!row)return '';
  const baseline=riskHistoryBaselineText(row.performance);
  return `<div class="risk-history-summary"><div><h3>${riskHistoryEsc(row.model==='portfolio-risk-v4'?'Latest stress-loss score':'Latest legacy risk index')}</h3><strong><bdi>${esc(riskHistoryScoreText(row))}</bdi></strong><small>${riskHistoryEsc('Scenario loss (%)')}: <bdi>${esc(riskHistoryLossText(row.risk))}</bdi>${riskHistoryScoreValue(row.risk,row.model)!==null && !Number.isFinite(row.risk?.score)?` · ${riskHistoryEsc('Estimate')}`:''}</small><small><bdi>${esc(riskHistoryObservedAt(row.observed_at))}</bdi></small></div><div><h3>${riskHistoryEsc('P&L after recorded cash flows')}</h3><strong${riskHistoryProfitNumber(row.performance)===null?' class="risk-history-pending"':''}><bdi>${esc(riskHistoryProfitText(row.performance))}</bdi></strong>${baseline?`<small>${riskHistoryEsc('Baseline')}: <bdi>${esc(baseline)}</bdi></small>`:''}<small>${esc(riskHistoryPerformanceReasons(row.performance).join(' '))}</small></div></div>`;
}
function riskHistoryTableRows(rows,label) {
  return rows.slice().reverse().map(row=>{
    const risk=row.risk?{...row.risk,model:row.model,base_currency:row.base_currency}:null;
    const baseline=riskHistoryBaselineText(row.performance),reasons=riskHistoryPerformanceReasons(row.performance);
    const comparisonDetails=[['Beginning net equity',row.performance?.beginning_equity],['Ending net equity',row.performance?.ending_equity],['Recorded net cash flows',row.performance?.recorded_net_flows]].filter(([,value])=>typeof value==='number' && Number.isFinite(value));
    const evidence=[risk?riskTooltip({...risk,label}):riskHistoryText('Risk unavailable'),...comparisonDetails.map(([name,value])=>`${riskHistoryText(name)}: ${riskHistoryNumber(value,2)} ${row.performance?.currency || row.base_currency || ''}`)].join('\n');
    return `<tr data-risk-history-row="${esc(riskHistoryObservationKey(row))}"${riskHistoryObservationKey(row)===riskHistoryView.selectedObservation?' class="is-active"':''}><td><button type="button" id="riskHistoryDate-${esc(encodeURIComponent(riskHistoryObservationKey(row)))}" class="risk-history-date-button" data-risk-history-select="${esc(riskHistoryObservationKey(row))}"><bdi>${esc(riskHistoryObservedAt(row.observed_at))}</bdi></button></td><td>${risk?riskBadge(risk):riskHistoryEsc('Risk unavailable')}<small>${esc(row.model || '')}</small></td><td><bdi class="risk-history-number">${esc(riskHistoryLossText(risk))}</bdi></td><td><bdi${riskHistoryProfitNumber(row.performance)!==null?' class="risk-history-number"':''}>${esc(riskHistoryProfitText(row.performance))}</bdi>${baseline?`<small>${riskHistoryEsc('Baseline')}: <bdi>${esc(baseline)}</bdi></small>`:''}</td><td>${reasons.length?`<p class="section-note">${esc(reasons.join(' '))}</p>`:''}<details id="riskHistoryDetails-${esc(encodeURIComponent(riskHistoryObservationKey(row)))}"><summary>${riskHistoryEsc('Observation details')}</summary><pre class="risk-history-details">${esc(evidence)}</pre></details>${risk && typeof riskDataQualityHtml==='function'?riskDataQualityHtml(risk):''}</td></tr>`;
  }).join('');
}
function renderRiskHistory() {
  const target=$("riskHistoryContent");if(!target)return;
  const restore=typeof preserveRenderedInteraction === "function" ? preserveRenderedInteraction(target) : ()=>{};
  const view=riskHistoryView,data=view.data;
  const selected=view.account;
  const accounts=[...(data?.accounts || [])];
  if(selected && !accounts.some(row=>row.id===selected)) accounts.push({id:selected,label:view.accountLabel || selected});
  const label=selected ? accounts.find(row=>row.id===selected)?.label || selected : riskHistoryText("Total portfolio");
  const rows=riskHistoryDailyRows(data,selected);
  target.setAttribute("aria-busy",String(view.loading));
  if(!rows.some(row=>riskHistoryObservationKey(row)===view.selectedObservation))view.selectedObservation=rows.length?riskHistoryObservationKey(rows.at(-1)):'';
  const activeRow=rows.find(row=>riskHistoryObservationKey(row)===view.selectedObservation);
  const previousPeriod=data && view.loadedDays!==null && view.loadedDays!==view.days;
  target.innerHTML=`<div class="risk-history-controls"><label class="field"><span>${riskHistoryEsc('Account')}</span><select id="riskHistoryAccount"><option value="">${riskHistoryEsc('Total portfolio')}</option>${accounts.map(row=>`<option value="${esc(row.id)}"${selected===row.id?' selected':''}>${esc(row.label)}</option>`).join('')}</select></label><label class="field"><span>${riskHistoryEsc('Period')}</span><select id="riskHistoryDays">${[['30','Last 30 days'],['90','Last 90 days'],['365','Last year'],['0','All history']].map(([value,text])=>`<option value="${value}"${view.days===value?' selected':''}>${riskHistoryEsc(text)}</option>`).join('')}</select></label><button id="riskHistoryReload" class="secondary" type="button"${view.loading?' aria-disabled="true"':''}>${riskHistoryEsc('Reload')}</button></div>
    <p class="section-note">${riskHistoryEsc('Compare earlier scenario scores with later P&L. These observations do not validate a return forecast.')}</p>
    <p class="section-note risk-history-metadata"><span>${riskHistoryEsc('Reporting currency')}: <bdi>${esc(typeof currencyDisplayLabel==='function'?currencyDisplayLabel(data?.base_currency || state.baseCurrency):data?.base_currency || state.baseCurrency)}</bdi></span>${data?.reset_at?`<span>${riskHistoryEsc('Recording started')}: <bdi>${esc(riskHistoryObservedAt(data.reset_at))}</bdi></span>`:''}</p>
    <p class="status-line" role="status" aria-live="polite">${riskHistoryEsc(view.loading?'Loading risk history…':view.error || view.captureError)}</p>
    ${previousPeriod?`<p class="section-note" role="status">${riskHistoryEsc('Showing the previously loaded period until the selected period loads.')}</p>`:''}
    ${!rows.length?`<p class="empty"${!data?' hidden':''}>${riskHistoryEsc(data?.items?.length?'No observations for this account and period.':'No observations yet. Recording begins with the first saved dashboard assessment.')}</p>`:`${riskHistorySummary(rows)}<section class="risk-history-plot"><h3>${riskHistoryScaleHeading(rows.some(row=>row.model==='portfolio-risk-v4')?'Stress-loss score (0–100)':'Legacy risk index (0–100)')}</h3>${riskHistoryGraph(rows,label) || `<p class="risk-history-chart-empty">${riskHistoryEsc('No supported risk scores for these observations.')}</p>`}<p class="section-note">${riskHistoryEsc('The score rounds scenario loss and is capped at 100. Exact loss percentages can exceed 100%.')}</p></section><section class="risk-history-plot"><h3>${riskHistoryEsc('P&L after recorded cash flows')} · <bdi>${esc(data?.base_currency || state.baseCurrency)}</bdi></h3>${riskHistoryProfitGraph(rows,label)}<p class="section-note">${riskHistoryEsc('Change in saved net equity after recorded deposits and withdrawals. Unrecorded activity may affect this amount.')}</p></section><div id="riskHistoryReadout" class="risk-history-readout" role="status" aria-live="polite">${riskHistoryReadout(activeRow)}</div><p class="section-note">${riskHistoryEsc(rows.length===1 && data?.items?.length===1?'Only one observation is available.':'Latest observation per day; days without observations remain gaps.')} ${riskHistoryEsc('Select a chart point or a table date to compare the same observation across both charts.')}</p><div class="table-wrap" role="region" aria-label="${riskHistoryEsc('Daily observations')}" tabindex="0"><table><caption>${riskHistoryEsc('Daily observations')} · ${esc(label)}</caption><colgroup><col class="risk-history-date-col"><col class="risk-history-score-col"><col class="risk-history-loss-col"><col class="risk-history-profit-col"><col></colgroup><thead><tr><th scope="col">${riskHistoryEsc('Observed at')}</th><th scope="col">${riskHistoryEsc('Stress-loss score')}</th><th scope="col">${riskHistoryEsc('Scenario loss (%)')}</th><th scope="col">${riskHistoryEsc('P&L after recorded cash flows')}</th><th scope="col">${riskHistoryEsc('Observation details')}</th></tr></thead><tbody>${riskHistoryTableRows(rows,label)}</tbody></table></div>`}
    ${data?.invalid_records?`<p class="section-note">${riskHistoryEsc('Some stored observations could not be read.')}</p>`:''}${data?.truncated?`<p class="section-note">${riskHistoryEsc('Older observations are omitted from this view.')}</p>`:''}<p class="section-note">${riskHistoryEsc('Employee equity and savings without underlying allocations are excluded. Holdings filters do not change this history.')}</p><p class="section-note">${riskHistoryEsc('Saved prices and exchange rates remain attached to each observation. Reload retries capture; Admins and Operators can record, and Viewers can read history.')}</p>`;
  restore();
}
document.addEventListener("change",event=>{
  if(event.target.id==="riskHistoryAccount"){riskHistoryView.account=event.target.value;riskHistoryView.accountLabel=riskHistoryView.data?.accounts?.find(row=>row.id===event.target.value)?.label || "";riskHistoryView.selectedObservation='';renderRiskHistory();$("riskHistoryAccount")?.focus();}
  if(event.target.id==="riskHistoryDays"){riskHistoryView.days=event.target.value;riskHistoryView.selectedObservation='';loadRiskHistory({capture:false});}
});
document.addEventListener('click',event=>{
  if(event.target.closest?.('#riskHistoryReload') && !riskHistoryView.loading)loadRiskHistory();
  const point=event.target.closest?.('[data-risk-history-point],[data-risk-history-select]');
  if(point)selectRiskHistoryObservation(point.getAttribute('data-risk-history-point') || point.getAttribute('data-risk-history-select'));
});
for(const name of ['focusin','pointerover'])document.addEventListener(name,event=>{
  const point=event.target.closest?.('[data-risk-history-point]');
  if(point)selectRiskHistoryObservation(point.getAttribute('data-risk-history-point'));
});
document.addEventListener('keydown',event=>{
  const point=event.target.closest?.('[data-risk-history-point]');if(!point)return;
  if(event.key==='Enter' || event.key===' '){event.preventDefault();selectRiskHistoryObservation(point.getAttribute('data-risk-history-point'));return;}
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  const points=[...point.closest('svg').querySelectorAll('[data-risk-history-point]')],index=points.indexOf(point);
  const next=event.key==='Home'?0:event.key==='End'?points.length-1:Math.max(0,Math.min(points.length-1,index+(event.key==='ArrowLeft'?-1:1)));
  event.preventDefault();points[next]?.focus();
});
if(typeof window!=='undefined')window.addEventListener?.('resize',()=>{
  if($('riskHistoryModal')?.hidden===false)renderRiskHistory();
});
