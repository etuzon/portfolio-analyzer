/* Recorded dashboard-client assessments. Values are never backfilled or recalculated. */
let riskHistoryView = { version:0, data:null, account:"", days:"90", loading:false, error:"", captureError:"" };
let riskHistoryCaptureTask = null;
const RISK_HISTORY_HE = {
  "Risk history":"היסטוריית סיכון", "Total portfolio":"כל התיק", "Account":"חשבון", "Last 30 days":"30 הימים האחרונים", "Last 90 days":"90 הימים האחרונים", "Last year":"השנה האחרונה", "All history":"כל ההיסטוריה", "Period":"תקופה", "Reload":"טעינה מחדש", "Loading risk history…":"טוען היסטוריית סיכון…", "Could not load risk history. Use Reload to retry.":"לא ניתן לטעון את היסטוריית הסיכון. לחצו על טעינה מחדש כדי לנסות שוב.", "No observations yet. Recording begins with the first saved dashboard assessment.":"אין עדיין מדידות. ההיסטוריה מתחילה מהערכת הסיכון הראשונה שנשמרה מלוח הבקרה.", "No observations for this account and period.":"אין מדידות לחשבון ולתקופה שנבחרו.", "Only one observation is available.":"קיימת מדידה אחת בלבד.", "Score":"ציון", "Observed at":"מועד המדידה", "Risk details":"פירוט הסיכון", "Daily observations":"מדידות יומיות", "Risk score (0–100)":"ציון סיכון (0–100)", "Base currency":"מטבע בסיס", "Model":"מודל", "Latest observation per day; days without observations remain gaps.":"המדידה האחרונה בכל יום; ימים ללא מדידות נשארים כפערים בגרף.", "Recorded model assessments, excluding employee equity. Holdings filters do not change this history.":"הערכות מודל סיכון שנשמרו, ללא תגמול הוני לעובדים. מסנני ההחזקות אינם משנים היסטוריה זו.", "The browser calculates the existing model. History is saved when an Admin or Operator loads a completed dashboard; Viewers can read saved history.":"הדפדפן מחשב את המודל הקיים. ההיסטוריה נשמרת כשמנהל או מפעיל טוען לוח בקרה שהשלים את הטעינה; צופים יכולים לקרוא היסטוריה שמורה.", "A current observation could not be saved. Wait for analytics to finish or refresh the dashboard, then Reload.":"לא ניתן לשמור מדידה נוכחית. המתינו לסיום טעינת הניתוח או רעננו את לוח הבקרה, ואז לחצו על טעינה מחדש.", "Older observations are omitted from this view.":"מדידות ישנות יותר אינן מוצגות בתצוגה זו.", "Some stored observations could not be read.":"לא ניתן לקרוא חלק מהמדידות השמורות.", "Saved FX is used for recorded assessments. Current badges may use newer or different FX.":"ההערכות השמורות משתמשות בשערי מטבע שמורים. סמלי הסיכון הנוכחיים עשויים להשתמש בשערים חדשים או שונים.", "Current data issues":"פערי הנתונים הנוכחיים", "Limited data":"נתונים מוגבלים", "No risk data gaps":"אין פערים בנתוני הסיכון"
};
function riskHistoryText(text) { return state.language === "he" ? RISK_HISTORY_HE[text] || t(text) : text; }
function riskHistoryEsc(text) { return esc(riskHistoryText(text)); }
function resetRiskHistory() {
  riskHistoryView = {version:riskHistoryView.version+1,data:null,account:"",days:"90",loading:false,error:"",captureError:""};
  riskHistoryCaptureTask = null;
}
function riskHistoryRiskRecord(risk) {
  if (risk.model === "portfolio-risk-v3") {
    const fields=["model","status","score","estimated_score","loss_pct","stress_loss","worst_scenario","net_equity","cash_debt","cash_pct","components","quality_details","gaps","assumptions","coverage","funding","scenarios","rating_evidence","forward_sensitivity","as_of","source_revision"];
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
  if (riskHistoryCaptureTask) return riskHistoryCaptureTask;
  const userId=state.auth?.user?.id;
  const task=(async()=>{
    try {
      const context=await api(`/api/portfolio/risk-history/context?base_currency=${encodeURIComponent(state.baseCurrency || "ILS")}`);
      if (userId!==state.auth?.user?.id) return;
      const snapshot=riskHistoryCalculate(context);
      const expected=[...context.account_ids].sort(), actual=snapshot.accounts.map(row=>row.key).sort();
      if (JSON.stringify(expected)!==JSON.stringify(actual)) throw new Error("scope");
      await api("/api/portfolio/risk-history", {method:"POST",body:JSON.stringify({token:context.token,total:riskHistoryRiskRecord(snapshot.total),accounts:snapshot.accounts.map(row=>({account_id:row.key,risk:riskHistoryRiskRecord(row.risk)}))})});
      if(userId===state.auth?.user?.id)riskHistoryView.captureError="";
    } catch {
      if(userId===state.auth?.user?.id)riskHistoryView.captureError="A current observation could not be saved. Wait for analytics to finish or refresh the dashboard, then Reload.";
    }
  })();
  riskHistoryCaptureTask=task;
  try { await task; } finally { if(riskHistoryCaptureTask===task)riskHistoryCaptureTask=null; }
}
async function loadRiskHistory({capture=true}={}) {
  const version=++riskHistoryView.version,userId=state.auth?.user?.id;
  riskHistoryView.loading=true;riskHistoryView.error="";renderRiskHistory();
  try {
    if(capture)await recordRiskHistory();
    const params=new URLSearchParams({base_currency:state.baseCurrency || "ILS",days:riskHistoryView.days});
    const data=await api(`/api/portfolio/risk-history?${params}`);
    if(version!==riskHistoryView.version || userId!==state.auth?.user?.id)return;
    riskHistoryView.data=data;
  } catch { if(version===riskHistoryView.version && userId===state.auth?.user?.id)riskHistoryView.error="Could not load risk history. Use Reload to retry."; }
  finally { if(version===riskHistoryView.version && userId===state.auth?.user?.id){riskHistoryView.loading=false;renderRiskHistory();} }
}
function riskHistoryDailyRows(data,account) {
  const days=new Map();
  for(const sample of data?.items || []) {
    const risk=account ? sample.accounts?.find(row=>row.account_id===account)?.risk : sample.total;
    if(!risk)continue;
    const key=`${sample.date}|${sample.model}`;
    const previous=days.get(key);
    if(!previous || sample.observed_at>previous.observed_at)days.set(key,{...sample,risk});
  }
  return [...days.values()].sort((a,b)=>a.date.localeCompare(b.date)||a.observed_at.localeCompare(b.observed_at));
}
function riskHistoryGraph(rows,label) {
  if(!rows.length)return "";
  const width=920,height=300,left=48,right=20,top=20,bottom=48;
  const times=rows.map(row=>Date.parse(`${row.date}T00:00:00Z`));
  const min=times[0],max=times.at(-1),span=max-min;
  const points=rows.map((row,index)=>{
    const value=Number.isFinite(row.risk.score)?row.risk.score:row.risk.estimated_score;
    return {...row,index,value,x:span?left+(times[index]-min)/span*(width-left-right):width/2,y:Number.isFinite(value)?top+(100-value)/100*(height-top-bottom):null};
  });
  if(!points.some(p=>p.y!==null))return "";
  let path="";
  points.forEach((point,index)=>{
    if(point.y===null)return;
    const previous=points[index-1];
    const linked=previous?.y!==null && previous && point.model===previous.model && point.risk.status===previous.risk.status && times[index]-times[index-1]===86400000;
    path+=`${linked?"L":"M"}${point.x.toFixed(2)},${point.y.toFixed(2)} `;
  });
  const ticks=[0,20,40,60,80,100].map(score=>{const y=top+(100-score)/100*(height-top-bottom);return `<line x1="${left}" x2="${width-right}" y1="${y}" y2="${y}" class="risk-history-grid"/><text x="${left-10}" y="${y+4}" text-anchor="end">${score}</text>`;}).join("");
  const dots=points.filter(p=>p.y!==null).map(point=>{
    const description=`${formatDateTime(point.observed_at)}\n${riskHistoryText("Model")}: ${point.model}\n${riskHistoryText("Score")}: ${point.risk.status==="estimate"?"~":""}${point.value}/100`;
    return `<circle cx="${point.x}" cy="${point.y}" r="4" tabindex="0" aria-label="${esc(description)}"><title>${esc(description)}</title></circle>`;
  }).join("");
  const indices=[...new Set([0,Math.floor((points.length-1)/2),points.length-1])];
  return `<div class="risk-history-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(`${label}: ${riskHistoryText("Risk score (0–100)")}`)}"><g>${ticks}<path d="${path}" class="risk-history-line"/>${dots}${indices.map(index=>`<text x="${points[index].x}" y="${height-16}" text-anchor="middle">${esc(formatDate(points[index].date))}</text>`).join("")}</g></svg></div>`;
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
  target.innerHTML=`<div class="risk-history-controls"><label class="field"><span>${riskHistoryEsc("Account")}</span><select id="riskHistoryAccount"><option value="">${riskHistoryEsc("Total portfolio")}</option>${accounts.map(row=>`<option value="${esc(row.id)}"${selected===row.id?" selected":""}>${esc(row.label)}</option>`).join("")}</select></label><label class="field"><span>${riskHistoryEsc("Period")}</span><select id="riskHistoryDays">${[["30","Last 30 days"],["90","Last 90 days"],["365","Last year"],["0","All history"]].map(([value,text])=>`<option value="${value}"${view.days===value?" selected":""}>${riskHistoryEsc(text)}</option>`).join("")}</select></label><button id="riskHistoryReload" class="secondary" type="button"${view.loading?' aria-disabled="true"':""}>${riskHistoryEsc("Reload")}</button></div>
    <p class="section-note">${riskHistoryEsc("Recorded model assessments, excluding employee equity. Holdings filters do not change this history.")}</p><p class="section-note">${riskHistoryEsc("Saved FX is used for recorded assessments. Current badges may use newer or different FX.")}</p><p class="section-note">${riskHistoryEsc("Base currency")}: ${esc(currencyDisplayLabel(data?.base_currency || state.baseCurrency))} · ${riskHistoryEsc("Model")}: ${esc(data?.model || "portfolio-risk-v3")} · ${esc(t("Models use different scales. Lines do not connect across models."))}</p>
    <p class="status-line" role="status" aria-live="polite">${riskHistoryEsc(view.loading?"Loading risk history…":view.error || view.captureError)}</p>
    ${!rows.length?`<p class="empty">${riskHistoryEsc(data?.items?.length?"No observations for this account and period.":"No observations yet. Recording begins with the first saved dashboard assessment.")}</p>`:`${riskHistoryGraph(rows,label)}<p class="section-note">${riskHistoryEsc(rows.length===1?"Only one observation is available.":"Latest observation per day; days without observations remain gaps.")}</p><div class="table-wrap"><table><caption>${riskHistoryEsc("Daily observations")} · ${esc(label)}</caption><thead><tr><th>${riskHistoryEsc("Observed at")}</th><th>${riskHistoryEsc("Score")}</th><th>${riskHistoryEsc("Risk details")}</th></tr></thead><tbody>${rows.slice().reverse().map(row=>`<tr><td><bdi>${esc(formatDateTime(row.observed_at))}</bdi></td><td>${riskBadge({...row.risk,model:row.model,base_currency:row.base_currency})}<small>${esc(row.model)}</small></td><td><details><summary>${riskHistoryEsc("Risk details")}</summary><pre class="risk-history-details">${esc(riskTooltip({...row.risk,label,model:row.model,base_currency:row.base_currency}))}</pre></details>${typeof riskDataQualityHtml==="function"?riskDataQualityHtml({...row.risk,model:row.model}):""}</td></tr>`).join("")}</tbody></table></div>`}
    ${data?.invalid_records?`<p class="section-note">${riskHistoryEsc("Some stored observations could not be read.")}</p>`:""}${data?.truncated?`<p class="section-note">${riskHistoryEsc("Older observations are omitted from this view.")}</p>`:""}<p class="section-note">${riskHistoryEsc("The browser calculates the existing model. History is saved when an Admin or Operator loads a completed dashboard; Viewers can read saved history.")}</p>`;
  restore();
}
document.addEventListener("change",event=>{
  if(event.target.id==="riskHistoryAccount"){riskHistoryView.account=event.target.value;riskHistoryView.accountLabel=riskHistoryView.data?.accounts?.find(row=>row.id===event.target.value)?.label || "";renderRiskHistory();$("riskHistoryAccount")?.focus();}
  if(event.target.id==="riskHistoryDays"){riskHistoryView.days=event.target.value;loadRiskHistory({capture:false});}
});
document.addEventListener("click",event=>{if(event.target.closest?.("#riskHistoryReload") && !riskHistoryView.loading)loadRiskHistory();});
