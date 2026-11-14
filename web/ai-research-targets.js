/* Explicit data targets in the main AI window, using the existing risk worker. */
(() => {
  "use strict";
  const el = id => document.getElementById(id);
  const txt = (key, values = {}) => Object.entries(values).reduce((result, [name, value]) => result.replaceAll(`{${name}}`, String(value)), t(key));
  const running = job => ["queued", "running"].includes(job?.status);
  const owner = () => String(typeof currentUser === "function" ? currentUser()?.id || "" : "");
  let view = null;
  function session() {
    if (!view || view.owner !== owner()) {
      clearTimeout(view?.timer);
      view = {owner:owner(),job:null,pending:false,checking:false,message:"",polls:0,timer:null,refreshed:new Set()};
    }
    return view;
  }
  const valid = value => value === view && value.owner === owner();
  const isRisk = () => el("aiResearchTarget")?.value === "risk_inputs";
  const presentation = () => window.RiskInputRetrievalPresentation;
  function dateTime(value, timezone) {
    try {
      const date = new Date(value); if (!Number.isFinite(date.getTime())) return "";
      const parts = new Intl.DateTimeFormat("en-GB",{...(timezone?{timeZone:timezone}:{}),day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(date);
      const part = name => parts.find(item=>item.type===name)?.value;
      return `${part("day")}/${part("month")}/${part("year")} ${part("hour")}:${part("minute")}`;
    } catch { return ""; }
  }
  function refresh() { if (typeof renderAIEnrichment === "function") renderAIEnrichment(); }
  function requestOptions(job = null) {
    if (job?.data_types) return {data_types:job.data_types,refresh_policy:job.refresh_policy || "missing"};
    const target = el("aiResearchTarget")?.value || "portfolio";
    const types = target === "portfolio" ? ["prices","profile","company_ratings"] : [target];
    return {data_types:types,refresh_policy:el("aiResearchRefresh")?.value || "stale"};
  }
  function sourceLink(source, index) {
    try {
      const url = new URL(source.url);
      if (url.protocol !== "https:" || url.username || url.password) return "";
      const date = source.retrieved_at ? dateTime(source.retrieved_at) : "";
      return `<a href="${esc(url.href)}" target="_blank" rel="noopener noreferrer">${esc(txt("Source {number}",{number:index+1}))}</a>${date ? ` · ${esc(txt("Retrieved {date}",{date}))}` : ""}`;
    } catch { return ""; }
  }
  function render() {
    if (!el("aiResearchTarget")) return;
    const s = session(), risk = isRisk(), busy = s.pending || s.checking || running(s.job);
    const marketBusy = Boolean(state.aiEnrichment.pending || state.aiEnrichment.resume);
    const writable = canWrite() && !state.auth.forcedPasswordChange && !currentUser()?.must_change_password;
    el("aiResearchTarget").disabled = !currentUser() || busy || marketBusy;
    el("aiResearchRefresh").disabled = !writable || busy || marketBusy;
    el("aiRiskResearchModeField").hidden = !risk;
    el("aiRiskResearchMode").disabled = !writable || busy;
    el("aiEnrichmentRatingsOnly").closest(".ai-enrichment-mode").hidden = true;
    el("aiEnrichmentScope").textContent = txt("Research follows the selected data types and freshness policy. Open includes long and short positions; All also includes closed positions. Dashboard and Holdings filters do not limit research. Opening this window does not start a job.");
    const currentJob = risk ? s.job : state.aiEnrichment.job;
    el("aiResearchCurrentJob").hidden = !currentJob;
    if (currentJob) {
      const labels = {prices:"Prices",profile:"Company profile",company_ratings:"Company credit ratings",risk_inputs:"Risk inputs"};
      const targets = risk ? txt("Risk inputs") : (currentJob.data_types || ["prices","profile","company_ratings"]).map(type=>txt(labels[type] || "Other data")).join(", ");
      const freshness = txt({missing:"Missing fields",stale:"Missing or stale fields",refresh_existing:"Recheck existing data too"}[currentJob.refresh_policy] || "Missing or stale fields");
      el("aiResearchCurrentJob").textContent = txt("Current request: {targets} · {freshness}",{targets,freshness});
    }
    el("aiRiskResearchPanel").hidden = !risk;
    if (!risk) { el("aiEnrichmentPhase").closest(".ai-enrichment-progress-panel").hidden = false; return; }
    for (const id of ["aiEnrichmentBondScope","aiEnrichmentMarketTitle","aiEnrichmentSummary","aiEnrichmentDetails","aiEnrichmentEmpty","aiCreditRatings","aiEnrichmentResume","aiEnrichmentRetryRatings"]) el(id).hidden = true;
    el("aiEnrichmentPhase").closest(".ai-enrichment-progress-panel").hidden = true;
    for (const id of ["aiEnrichmentStart","aiEnrichmentStartAll"]) {
      el(id).disabled = !writable || busy;
      el(id).title = txt("Research supported risk inputs in this scope. Each run checks up to three securities.");
    }
    el("aiRiskResearchCheck").disabled = s.pending || s.checking || !currentUser();
    const progress = s.job?.progress || {};
    const status = s.message ? txt(s.message) : s.pending ? txt("Starting risk research…") : s.checking ? txt("Loading risk research…")
      : s.job ? txt({queued:"Queued",api:"Checking public APIs…",ai:"Researching missing risk inputs with AI…",completed:"Completed",failed:"Failed"}[progress.stage] || "Running")
      : txt("No risk research has been run yet.");
    el("aiRiskResearchStatus").textContent = [status, progress.total ? txt("{completed} of {total} securities",{completed:fmt(progress.completed || 0,0),total:fmt(progress.total,0)}) : "",progress.current_security?.symbol || "",
      s.job?.status === "failed" ? presentation()?.outcomeMessage(s.job.code) : "",!writable ? txt("AI data updates require Admin or Operator permission.") : ""].filter(Boolean).join(" · ");
    el("aiEnrichmentFooterNote").textContent = txt(busy ? "You can close this window while research continues. Reopen it from Portfolio to see progress." : "You can close this window. Reopen it from Portfolio to view results or start a new request.");
    const bar = el("aiRiskResearchProgress");
    bar.hidden = !running(s.job); bar.max = Math.max(1,progress.total || 1); bar.value = progress.completed || 0;
    const coverage = s.job?.coverage;
    el("aiRiskResearchCoverage").textContent = coverage ? txt("This run includes {selected} of {total} candidates; {remaining} remain outside this batch.",{
      selected:fmt(coverage.selected || 0,0),total:fmt(coverage.total_candidates || 0,0),remaining:fmt(coverage.remaining || 0,0)}) : "";
    el("aiRiskResearchResults").innerHTML = (s.job?.outcomes || []).map(row => {
      const status = txt({updated:"Updated",partial:"Partially updated",unavailable:"Unavailable",not_attempted:"Not attempted"}[row.status] || "Unavailable");
      const method = method => txt({completed:"Completed",updated:"Updated",partial:"Partially updated",failed:"Failed",not_attempted:"Not attempted",unavailable:"Unavailable"}[row[method]?.status] || "Unavailable");
      return `<li><bdi dir="auto">${esc(row.symbol || row.security_key)}</bdi> · <strong>${esc(status)}</strong><p>${esc(presentation()?.outcomeMessage(row.code) || txt("The requested risk inputs remain missing."))}</p>
        <p>${esc(txt("Available inputs"))}: ${esc(presentation()?.fields(row.available_fields) || txt("None"))}</p><p>${esc(txt("Still missing"))}: ${esc(presentation()?.fields(row.missing_fields) || txt("Other required risk inputs"))}</p>
        <p>${esc(txt("Public API"))}: ${esc(method("api"))} · ${esc(txt("AI research"))}: ${esc(method("ai"))}</p><p>${(row.sources || []).map(sourceLink).filter(Boolean).join(" · ")}</p>
        <button type="button" class="secondary compact-button" data-risk-inputs-security-key="${esc(row.security_key || "")}" data-risk-inputs-symbol="${esc(row.symbol || "")}">${esc(txt("Review risk inputs"))}</button></li>`;
    }).join("");
  }
  function accept(s, job) {
    if (!valid(s)) return;
    s.job = job; s.message = "";
    if (job?.mode) el("aiRiskResearchMode").value = job.mode;
    if (job?.refresh_policy) el("aiResearchRefresh").value = job.refresh_policy;
    clearTimeout(s.timer);
    if (running(job)) {
      if (s.polls >= 120) s.message = "Progress checks paused. Select Check progress to resume.";
      else s.timer = setTimeout(() => { if (valid(s)) { s.polls++; check(); } },3000);
    } else if (job?.portfolio_refresh_required && !s.refreshed.has(job.request_id)) {
      s.refreshed.add(job.request_id);
      document.dispatchEvent(new CustomEvent("stress-risk-inputs-changed"));
    }
  }
  async function check({reset=false} = {}) {
    const s = session(); if (s.checking || !currentUser()) return;
    if (reset) s.polls = 0;
    s.checking = true; s.message = ""; refresh();
    try {
      const response = await api(s.job?.request_id ? `/api/securities/risk-inputs/retrieval/${encodeURIComponent(s.job.request_id)}` : "/api/securities/risk-inputs/retrieval/status");
      if (valid(s)) accept(s,s.job?.request_id ? response : response.active_job || response.last_job);
    } catch { if (valid(s)) s.message = "Could not check progress. Select Check progress to retry."; }
    finally { if (valid(s)) { s.checking = false; refresh(); } }
  }
  async function start(scope) {
    const s = session(); if (!canWrite() || s.pending || s.checking || running(s.job)) return;
    const payload = {mode:el("aiRiskResearchMode").value,position_scope:scope,refresh_policy:el("aiResearchRefresh").value,language:state.language};
    s.pending = true; s.message = ""; s.polls = 0; refresh();
    try {
      const job = await api("/api/securities/risk-inputs/retrieval",{method:"POST",body:JSON.stringify(payload)});
      if (valid(s)) accept(s,job);
    } catch {
      if (valid(s)) {
        s.message = "Could not start risk research. Check progress before trying again.";
        try { const response = await api("/api/securities/risk-inputs/retrieval/status"); if (valid(s) && response.active_job) accept(s,response.active_job); } catch { /* Keep retry guidance. */ }
      }
    } finally { if (valid(s)) { s.pending = false; refresh(); } }
  }
  document.addEventListener("change",event => {
    if (event.target.id === "aiResearchTarget") {
      el("aiEnrichmentPhase").closest(".ai-enrichment-progress-panel").hidden = false;
      refresh();
      if (isRisk()) check();
    }
  });
  document.addEventListener("click",event => { if (event.target.closest?.("#aiRiskResearchCheck")) check({reset:true}); });
  window.AIResearchTargets = Object.freeze({isRisk,render,start,requestOptions,open:()=>{session();if(isRisk())check();},reset:()=>{
    clearTimeout(view?.timer); view = null;
    if (el("aiResearchTarget")) { el("aiResearchTarget").value = "portfolio"; el("aiResearchRefresh").value = "stale"; }
  }});
  window.AIResearchFormatting = Object.freeze({dateTime});
})();
