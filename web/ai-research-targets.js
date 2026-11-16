/* One parent request owns every selected data type and its bounded child jobs. */
(() => {
  "use strict";
  const el = id => document.getElementById(id);
  const txt = (key, values = {}) => Object.entries(values).reduce((result, [name, value]) => result.replaceAll(`{${name}}`, String(value)), t(key));
  const running = job => ["queued", "running"].includes(job?.status);
  const presentation = () => window.RiskInputRetrievalPresentation;
  const isRisk = () => el("aiResearchTarget")?.value === "risk_inputs";
  const riskTargets = types => (types || []).includes("risk_inputs");
  function dateTime(value, timezone) {
    try {
      const date = new Date(value); if (!Number.isFinite(date.getTime())) return "";
      const parts = new Intl.DateTimeFormat("en-GB",{...(timezone?{timeZone:timezone}:{}),day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(date);
      const part = name => parts.find(item=>item.type===name)?.value;
      return `${part("day")}/${part("month")}/${part("year")} ${part("hour")}:${part("minute")}`;
    } catch { return ""; }
  }
  function requestOptions(job = null) {
    if (job?.data_types) return {data_types:job.data_types,refresh_policy:job.refresh_policy || "missing",
      ...(riskTargets(job.data_types)?{risk_mode:job.risk_mode || "api_then_ai"}:{})};
    const target = el("aiResearchTarget")?.value || "portfolio";
    const types = target === "portfolio" ? ["prices","profile","company_ratings","risk_inputs","country_ratings"] : [target];
    return {data_types:types,refresh_policy:el("aiResearchRefresh")?.value || "stale",
      ...(riskTargets(types)?{risk_mode:el("aiRiskResearchMode")?.value || "api_then_ai"}:{})};
  }
  function sourceLink(source, index) {
    try {
      const url = new URL(source.url || source.source_url);
      if (url.protocol !== "https:" || url.username || url.password) return "";
      const observed = source.as_of || source.observation_date;
      const observation = observed ? txt("Observed {date}",{date:/^\d{4}-\d{2}-\d{2}/.test(String(observed))?String(observed).slice(0,10).split("-").reverse().join("/"):dateTime(observed).split(" ")[0]}) : "";
      const retrieved = source.retrieved_at ? txt("Retrieved {date}",{date:dateTime(source.retrieved_at)}) : "";
      return `<a href="${esc(url.href)}" target="_blank" rel="noopener noreferrer">${esc(txt("Source {number}",{number:index+1}))}</a>${[observation,retrieved].filter(Boolean).map(value=>` · ${esc(value)}`).join("")}`;
    } catch { return ""; }
  }
  function unresolvedCount(job) {
    const rows = job?.outcomes || [];
    return rows.filter(row => row.missing_fields?.length || (!Array.isArray(row.missing_fields) && ["partial","unavailable","not_attempted","pending"].includes(row.status))).length;
  }
  function completionText(job) {
    if (!job) return txt("No risk research has been run yet.");
    if (running(job)) return txt("Research in progress");
    if (job.status === "failed") return txt("Research stopped");
    const count = unresolvedCount(job);
    return count === 1 ? txt("Research finished; one security still has missing risk inputs.") : count ? txt("Research finished; {count} securities still have missing risk inputs.",{count:fmt(count,0)})
      : txt("Research finished; no missing risk inputs remain in the checked scope.");
  }
  function replaceResults(list, html) {
    if (!list || list.innerHTML === html) return;
    const scrollTop = list.scrollTop;
    const focusedKey = document.activeElement?.getAttribute?.("data-risk-inputs-security-key");
    list.innerHTML = html; list.scrollTop = scrollTop;
    if (focusedKey) [...list.querySelectorAll("[data-risk-inputs-security-key]")].find(node=>node.getAttribute("data-risk-inputs-security-key")===focusedKey)?.focus({preventScroll:true});
  }
  const uiChecking = () => Boolean(state.aiEnrichment.checking);
  function renderRisk(job, parent) {
    const section = el("aiRiskResearchPanel");
    if (!section) return;
    section.hidden = !job && !isRisk();
    if (section.hidden) return;
    section.setAttribute("aria-busy",String(running(parent)));
    const progress = job?.progress || {};
    const message = running(parent) ? txt(parent?.progress?.stage === "researching_country_ratings" ? "Researching public-source country ratings" : parent?.progress?.stage === "researching_risk_inputs" ? "Researching risk inputs" : "Risk research is queued.") : completionText(job);
    el("aiRiskResearchStatus").textContent = [message,progress.total?txt("{completed} of {total} securities",{completed:fmt(progress.completed || 0,0),total:fmt(progress.total,0)}):"",progress.current_security?.symbol || ""].filter(Boolean).join(" · ");
    const bar = el("aiRiskResearchProgress");
    bar.hidden = !running(parent) || !(progress.total > 0); bar.max = Math.max(1,progress.total || 1); bar.value = progress.completed || 0;
    el("aiRiskResearchCheck").disabled = !currentUser() || !parent?.request_id || uiChecking();
    const coverage = job?.coverage;
    const total = coverage?.total_candidates ?? progress.total;
    el("aiRiskResearchCoverage").textContent = Number.isFinite(total) ? txt("Eligible securities in this request: {count}",{count:fmt(total,0)}) : "";
    replaceResults(el("aiRiskResearchResults"),(job?.outcomes || []).map(row => {
      const status = txt({pending:"Waiting for research",updated:"Updated",partial:"Partially updated",unavailable:"Unavailable",not_attempted:"Not attempted"}[row.status] || "Unavailable");
      const method = name => txt({queued:"Queued",running:"Running",completed:"Completed",updated:"Updated",partial:"Partially updated",failed:"Failed",not_attempted:"Not attempted",unavailable:"Unavailable"}[row[name]?.status] || "Not attempted");
      const missing = Array.isArray(row.missing_fields) ? presentation()?.fields(row.missing_fields) : txt("Other required risk inputs");
      return `<li><bdi dir="auto">${esc(row.symbol || row.security_key)}</bdi> · <strong>${esc(status)}</strong><p>${esc(presentation()?.outcomeMessage(row.code) || txt("The requested risk inputs remain missing."))}</p>
        <p>${esc(txt("Available inputs"))}: ${esc(presentation()?.fields(row.available_fields) || txt("None"))}</p><p>${esc(txt("Still missing"))}: ${esc(missing || txt("None"))}</p>
        <p>${esc(txt("Public API"))}: ${esc(method("api"))} · ${esc(txt("AI research"))}: ${esc(method("ai"))}</p><p>${(row.sources || []).map(sourceLink).filter(Boolean).join(" · ")}</p>
        <button type="button" class="secondary compact-button" data-risk-inputs-security-key="${esc(row.security_key || "")}" data-risk-inputs-symbol="${esc(row.symbol || "")}">${esc(txt("Review risk inputs"))}</button></li>`;
    }).join(""));
  }
  function renderCountries(job) {
    const section = el("aiCountryResearchPanel");
    if (!section) return;
    section.hidden = !job; if (!job) return;
    section.setAttribute("aria-busy",String(running(job)));
    const progress = job.progress || {};
    el("aiCountryResearchStatus").textContent = txt("Country checks: {completed} of {total}",{completed:fmt(progress.completed || 0,0),total:fmt(progress.total || 0,0)});
    replaceResults(el("aiCountryResearchResults"),(job.outcomes || []).map(row=>{
      const code=row.country_code || "";
      const name=typeof sovereignCountryLabel === "function"?sovereignCountryLabel(code):code;
      const status=txt({pending:"Waiting for research",updated:"Supported facts saved",partial:"Partial rating evidence",unavailable:"Checked; no verified rating evidence",not_attempted:"Not checked"}[row.status] || "Not checked");
      return `<li><bdi dir="auto">${esc(name)}</bdi> · <strong>${esc(status)}</strong>${row.code && typeof creditRatingsReason === "function"?`<p>${esc(creditRatingsReason(row.code, ""))}</p>`:""}<p>${(row.sources || []).map(sourceLink).filter(Boolean).join(" · ")}</p></li>`;
    }).join(""));
  }
  function render() {
    if (!el("aiResearchTarget")) return;
    const ui=state.aiEnrichment, job=ui.job, busy=ui.pending || ui.resume;
    const writable=canWrite() && !state.auth.forcedPasswordChange && !currentUser()?.must_change_password;
    el("aiResearchTarget").disabled=!currentUser() || busy;
    el("aiResearchRefresh").disabled=!writable || busy;
    const target=el("aiResearchTarget").value;
    el("aiRiskResearchModeField").hidden=!["portfolio","risk_inputs"].includes(target);
    el("aiRiskResearchMode").disabled=!writable || busy;
    el("aiEnrichmentRatingsOnly").closest(".ai-enrichment-mode").hidden=true;
    el("aiEnrichmentScope").textContent=txt("The complete portfolio update includes prices, company profiles, company ratings, risk inputs and country ratings. Research checks every eligible security in the chosen scope in bounded batches. Opening this window does not start a job.");
    el("aiResearchCurrentJob").hidden=!job;
    if (job) {
      const labels={prices:"Prices",profile:"Company profile",company_ratings:"Company credit ratings",risk_inputs:"Risk inputs",country_ratings:"Country credit ratings"};
      const targets=(job.data_types || ["prices","profile","company_ratings"]).map(type=>txt(labels[type] || "Other data")).join(", ");
      const freshness=txt({missing:"Missing fields",stale:"Missing or stale fields",refresh_existing:"Recheck existing data too"}[job.refresh_policy] || "Missing or stale fields");
      el("aiResearchCurrentJob").textContent=txt("Current request: {targets} · {freshness}",{targets,freshness});
    }
    const hasRisk = riskTargets(job?.data_types) || Boolean(job?.risk_inputs?.outcomes?.length || job?.risk_inputs?.progress?.total > 0);
    const hasCountries = hasRisk || job?.data_types?.includes("country_ratings") || Boolean(job?.country_ratings?.outcomes?.length || job?.country_ratings?.progress?.total > 0);
    renderRisk(hasRisk ? job?.risk_inputs : null,hasRisk ? job : null);
    renderCountries(hasCountries ? job?.country_ratings : null);
  }
  async function check() {
    const ui=state.aiEnrichment, version=ui.version;
    if (!currentUser() || !ui.job?.request_id || ui.checking) return;
    ui.checking=true;renderAIEnrichment();
    try {
      const job=await api(`/api/securities/enrichment/ai/${encodeURIComponent(ui.job.request_id)}`);
      if (state.aiEnrichment !== ui || ui.version !== version) return;
      acceptAIEnrichmentJob(job); scheduleAIEnrichmentPoll();
    } catch {
      if (state.aiEnrichment === ui && ui.version === version) {ui.message="Could not check progress. Select Check progress to retry.";renderAIEnrichment();}
    } finally {if(state.aiEnrichment===ui){ui.checking=false;renderAIEnrichment();}}
  }
  document.addEventListener("change",event=>{if(event.target.id==="aiResearchTarget")renderAIEnrichment();});
  document.addEventListener("click",event=>{if(event.target.closest?.("#aiRiskResearchCheck"))check();});
  window.AIResearchTargets=Object.freeze({isRisk,render,requestOptions,completionText,unresolvedCount,open:render,start:scope=>requestAIEnrichment(scope),reset:()=>{
    if(el("aiResearchTarget")){el("aiResearchTarget").value="portfolio";el("aiResearchRefresh").value="stale";}
  }});
  window.AIResearchFormatting=Object.freeze({dateTime});
})();
