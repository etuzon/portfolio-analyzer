/* Public-source risk evidence research and its shared scheduled workflow. */
(() => {
  let currentSession = null;
  const el = id => document.getElementById(id);
  const text = (key, values) => stressRiskText(key, values);
  const escape = value => stressRiskEscape(value);
  const actor = () => String(typeof currentUser === "function" ? currentUser()?.id || currentUser()?.username || "" : "");
  const writable = () => typeof canWrite === "function" && canWrite();
  const activeJob = job => ["queued", "running"].includes(job?.status);
  const validSession = value => value === currentSession && value.actor === actor();
  const session = () => {
    if (!currentSession || currentSession.actor !== actor()) {
      if (currentSession?.timer) clearTimeout(currentSession.timer);
      currentSession = {actor:actor(),mode:"api_then_ai",scope:"all",selected:[],items:[],loaded:false,loading:false,
        starting:false,checking:false,job:null,message:"",timer:null,polls:0,pollingBlocked:false,refreshed:new Set(),
        schedule:{loaded:false,pending:false,saving:false,dirty:false,saved:null,draft:null,message:"",mounted:false,remount:false}};
    }
    return currentSession;
  };
  const modeLabels = {api_then_ai:"Public API, then AI",api:"Public API only",ai:"AI only"};
  const statusLabels = {pending:"Waiting for research",queued:"Queued",running:"Running",completed:"Completed",failed:"Failed",updated:"Updated",
    partial:"Partially updated",unavailable:"Unavailable",not_attempted:"Not attempted"};
  const stageLabels = {queued:"Queued",api:"Checking public APIs…",ai:"Researching missing risk inputs with AI…",researching_market_data:"Researching missing market data",researching_ratings:"Researching public-source company ratings",researching_risk_inputs:"Researching risk inputs",researching_country_ratings:"Researching public-source country ratings",completed:"Research finished",failed:"Failed"};
  const fieldLabels = {issuer_identity:"Issuer identity",issuer_id:"Issuer identity",issuer_name:"Issuer name",issuer_domicile:"Issuer domicile",
    country:"Country exposure",country_code:"Issuer country",country_basis:"Country exposure basis",country_exposure:"Country exposure",country_exposures:"Country exposure",filing_sources:"Regulatory filing sources",
    country_rating:"Sovereign rating",credit_rating:"Security credit rating",sovereign_rating:"Sovereign rating",
    country_currency:"Country crisis currency",currency_exposures:"Economic currency exposure",fx:"Economic currency exposure",
    instrument_kind:"Instrument type",bond_kind:"Instrument type",bond_terms:"Bond terms",pricing_model:"Bond pricing model",
    plain_nominal_noncallable:"Plain nominal noncallable bond",zero_coupon_confirmed:"Confirmed zero coupon",bond_maturity:"Redemption date",
    maturity_date:"Redemption date",bond_cashflows:"Future bond payments",cashflows:"Future bond payments",
    bond_yield:"Discount yield",continuous_yield:"Discount yield",current_spread:"Current credit spread",current_spread_bps:"Current credit spread",
    sovereign_currency_basis:"Sovereign rating currency basis",country_sensitivity:"Country spread sensitivity",
    fund_lookthrough:"Underlying fund allocations",fund_holdings:"Underlying fund holdings",lookthrough:"Underlying fund allocations",parameters_unverified:"Verified instrument terms",parameters_stale:"Current bond pricing evidence",
    parameters_unavailable:"Risk inputs",valuation:"Saved valuation",valuation_stale:"Current valuation",asset_class:"Asset class",
    rating_stale:"Current rating evidence",rating_unverified:"Verified rating evidence"};
  const fields = values => (Array.isArray(values) ? values : []).map(value => text(fieldLabels[String(value).split(":")[0]] || "Other required risk inputs")).join(", ") || text("None");
  const outcomeMessage = code => text({data_found:"Supported risk evidence was saved.",partial_data:"Some evidence was found; remaining inputs stay missing.",
    data_unavailable:"No supported public evidence was found for the requested inputs.",fund_underlying_inputs_missing:"Fund holdings were found; some underlying risk inputs remain missing.",provider_unavailable:"The public source could not be reached. Retry later.",
    ai_unavailable:"AI research is unavailable. Review the configured assistant, then retry.",request_limit:"The request budget was reached. Review saved results before retrying.",
    ai_provider_timeout:"The AI check timed out. Saved results are retained; retry the remaining checks.",
    ai_provider_unavailable:"The AI connection is unavailable. Check the assistant connection, then retry the remaining checks.",
    ai_provider_busy:"The AI service is busy. Saved results are retained; retry the remaining checks later.",
    authentication_expired:"The session expired. Sign in again before retrying.",
    proposal_invalid:"The AI response could not be verified. Saved results are retained; retry the remaining checks.",
    check_incomplete:"Research stopped before this check finished. Saved results are retained; retry the remaining checks.",
    job_failed:"The research request failed. Open request diagnostics for the failure details.",
    evidence_rejected:"The retrieved evidence did not meet the validation requirements.",identity_changed:"The security identity changed. Reload candidates before retrying.",
    owner_not_authorized:"The schedule owner no longer has editing permission.",enrichment_busy:"Another research request is active. Check progress before retrying.",
    queued:"Waiting for its bounded research batch.",invalid_schedule:"The schedule settings could not be used. Reload and review the schedule."}[code] || "The requested risk inputs remain missing.");

  const selectionValues = container => [...(container?.querySelectorAll("input:checked") || [])].map(input => input.value);
  function capture() {
    const s = session();
    if (el("riskRetrievalMode")) s.mode = el("riskRetrievalMode").value;
    if (el("riskRetrievalScope")) s.scope = el("riskRetrievalScope").value;
    if (el("riskRetrievalSecurities")) s.selected = selectionValues(el("riskRetrievalSecurities"));
  }
  function populateSelect(select, s, values = []) {
    if (!select) return;
    const selected = new Set(values);
    select.replaceChildren();
    for (const item of s.items) {
      const label = document.createElement("label"), input = document.createElement("input"), identity = document.createElement("bdi");
      input.type = "checkbox"; input.value = item.security_key; input.checked = selected.has(item.security_key);
      identity.textContent = `${item.symbol || item.name || item.security_key} · ${item.stock_market || ""} · ${item.currency || ""}`;
      identity.dir = "auto";
      label.append(input,identity); select.append(label);
    }
  }
  function sourceLink(source, index) {
    try {
      const url = new URL(source.url);
      if (!["https:","http:"].includes(url.protocol) || url.username || url.password) return "";
      const reference = source.basis === "iso4217_country_reference";
      const observed = String(reference ? source.reference_published_at || source.as_of || "" : source.as_of || source.observation_date || "").slice(0,10);
      const observation = /^\d{4}-\d{2}-\d{2}$/.test(observed) ? text(reference ? "Reference list published {date}" : "Observed {date}",{date:observed.split("-").reverse().join("/")}) : "";
      const retrieved = source.retrieved_at && typeof formatDateTime === "function" ? text("Retrieved {date}", {date:formatDateTime(source.retrieved_at)}) : "";
      const saved = reference && source.reference_cache_status === "refresh_failed_using_saved" ? text("Reference refresh failed; using saved list.") : "";
      return `<span><a href="${escape(url.href)}" target="_blank" rel="noopener noreferrer">${escape(text("Source {number}", {number:index + 1}))}</a>${[observation,retrieved,saved].filter(Boolean).map(value=>` · ${escape(value)}`).join("")}</span>`;
    } catch { return ""; }
  }
  function flattenJob(job) {
    if (!job?.risk_inputs) return job;
    const branch = job.risk_inputs;
    return {...branch,request_id:job.request_id,status:job.status,code:job.code,
      failure:job.failure,
      progress:{...(branch.progress || {}),...(activeJob(job) ? job.progress || {} : {}),stage:job.progress?.stage || job.status},
      coverage:branch.coverage || {total_candidates:branch.progress?.total || 0,selected:branch.progress?.total || 0,remaining:0},
      portfolio_refresh_required:job.portfolio_refresh_required};
  }
  const isParentJob = job => Boolean(job?.data_types?.includes("risk_inputs")
    || job?.risk_inputs?.outcomes?.length || job?.risk_inputs?.progress?.total > 0);
  function chooseJob(response) {
    return [response?.active_job,response?.last_job].find(isParentJob) || null;
  }
  async function statusRequest(path) {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(),15000);
    try { return await api(path,{signal:controller.signal}); }
    finally { clearTimeout(timeout); }
  }
  async function readStatus() {
    const response=await statusRequest("/api/securities/enrichment/status");
    const parent=chooseJob(response);
    if(parent)return parent;
    // Read an in-flight request created by the previous bounded UI as well.
    const legacy=await statusRequest("/api/securities/risk-inputs/retrieval/status");
    return legacy.active_job || legacy.last_job;
  }
  function render() {
    const s = session(), job = flattenJob(s.job), running = activeJob(job), busy = s.loading || s.starting || s.checking;
    if (!el("riskRetrievalModal")) return;
    el("riskRetrievalViewerNote").hidden = writable();
    el("riskRetrievalMode").value = s.mode;
    el("riskRetrievalScope").value = s.scope;
    el("riskRetrievalSelectedField").hidden = s.scope !== "selected";
    for (const id of ["riskRetrievalMode","riskRetrievalScope","riskRetrievalSecurities"]) {
      el(id).disabled = !writable() || busy || running;
      for (const control of el(id).querySelectorAll("input")) control.disabled = !writable() || busy || running;
    }
    el("startRiskRetrieval").disabled = !writable() || !s.loaded || busy || running || (s.scope === "selected" && !s.selected.length);
    el("reloadRiskRetrieval").disabled = busy;
    el("checkRiskRetrieval").disabled = busy;
    el("checkRiskRetrieval").hidden = !job;
    el("retryRiskRetrieval").hidden = !job || running || !(job.status === "failed" || (job.outcomes || []).some(row => row.status !== "updated" || row.missing_fields?.length));
    el("retryRiskRetrieval").textContent = text(job?.status === "failed" && isParentJob(s.job) ? "Retry remaining checks" : "Retry missing inputs");
    el("retryRiskRetrieval").disabled = !writable() || busy || running;
    el("riskRetrievalFailure").hidden = job?.status !== "failed";
    el("riskRetrievalFailure").textContent = job?.status === "failed" ? outcomeMessage(job.failure?.code || job.code) : "";
    el("riskRetrievalDiagnostics").hidden = !job?.request_id || !isParentJob(s.job);
    el("riskRetrievalRequestId").textContent = job?.request_id ? text("Request ID: {request_id}",{request_id:job.request_id}) : "";
    el("riskRetrievalDiagnosticsLink").href = job?.request_id ? `/api/securities/enrichment/ai/${encodeURIComponent(job.request_id)}/diagnostics` : "#";
    el("riskRetrievalCount").textContent = s.loaded ? text("{count} securities have risk inputs to review", {count:stressRiskNumber(s.items.length,0)}) : "";
    const coverage = job?.coverage;
    el("riskRetrievalCoverage").textContent = coverage ? isParentJob(s.job) ? text("Eligible securities in this request: {count}",{count:stressRiskNumber(coverage.total_candidates || 0,0)}) : text("This run includes {selected} of {total} candidates; {remaining} remain outside this batch.", {
      selected:stressRiskNumber(coverage.selected || 0,0),total:stressRiskNumber(coverage.total_candidates || 0,0),remaining:stressRiskNumber(coverage.remaining || 0,0)}) : "";
    const progress = job?.progress || {};
    const stage = job?.status === "completed" && window.AIResearchTargets ? AIResearchTargets.completionText(job) : text(stageLabels[progress.stage] || statusLabels[job?.status] || "Running");
    const jobStatus = [stage,
      text(progress.stage === "researching_country_ratings" ? "{completed} of {total} countries" : "{completed} of {total} securities", {completed:stressRiskNumber(progress.completed || 0,0),total:stressRiskNumber(progress.total || 0,0)}),
      progress.current_security?.symbol || ""].filter(Boolean).join(" · ");
    el("riskRetrievalStatus").textContent = s.loading ? text("Loading risk research…") : s.starting ? text("Starting risk research…")
      : job ? s.message ? `${text(s.message)} ${text("Last known progress: {progress}",{progress:jobStatus})}` : jobStatus
        : s.message ? text(s.message) : text("No risk research has been run yet.");
    const bar = el("riskRetrievalProgress");
    bar.hidden = !running || !(progress.total > 0); bar.max = Math.max(1,progress.total || 1); bar.value = progress.completed || 0;
    const resultList = el("riskRetrievalResults"), scrollTop = resultList.scrollTop;
    const focusKey = document.activeElement?.getAttribute?.("data-risk-inputs-security-key");
    const resultHtml = (job?.outcomes || []).map(row => `<li><div class="risk-retrieval-result-heading"><bdi dir="auto">${escape(row.symbol || row.security_key)}</bdi><strong>${escape(text(statusLabels[row.status] || "Unavailable"))}</strong></div>
      <p>${escape(outcomeMessage(row.code))}</p><p>${escape(text("Available inputs"))}: ${escape(fields(row.available_fields))}</p><p>${escape(text("Still missing"))}: ${escape(fields(row.missing_fields))}</p>
      <div class="risk-retrieval-sources">${(row.sources || []).map(sourceLink).filter(Boolean).join(" · ")}</div>
      ${row.security_key ? `<button type="button" class="secondary compact-button" data-risk-inputs-security-key="${escape(row.security_key)}" data-risk-inputs-symbol="${escape(row.symbol || "")}">${escape(text("Review risk inputs"))}</button>` : ""}</li>`).join("");
    if(resultList.innerHTML !== resultHtml){
      resultList.innerHTML = resultHtml;resultList.scrollTop = scrollTop;
      if(focusKey)[...resultList.querySelectorAll("[data-risk-inputs-security-key]")].find(node=>node.getAttribute("data-risk-inputs-security-key")===focusKey)?.focus({preventScroll:true});
    }
    renderSchedule(s);
  }
  const researchVisible = () => !el("riskRetrievalModal")?.hidden && document.visibilityState !== "hidden";
  function scheduleProgress(s) {
    clearTimeout(s.timer); s.timer = null;
    if (!validSession(s) || !activeJob(s.job) || s.pollingBlocked || !researchVisible()) return;
    // Full-scope research can outlast a bounded child. Keep reading that same
    // request, reducing status traffic after six minutes instead of stopping.
    s.timer = setTimeout(() => {
      s.timer = null;
      if (validSession(s) && researchVisible()) { s.polls++; checkProgress(); }
    },s.polls < 120 ? 3000 : 15000);
  }
  function acceptJob(s, job) {
    if (!validSession(s)) return;
    s.job = job;
    if (job?.portfolio_refresh_required && !activeJob(job) && !s.refreshed.has(job.request_id)) {
      s.refreshed.add(job.request_id);
      document.dispatchEvent(new CustomEvent("stress-risk-inputs-changed"));
    }
    s.pollingBlocked = false;
    scheduleProgress(s);
  }
  async function checkProgress({reset=false} = {}) {
    const s = session(); if (s.checking || s.loading || s.starting) return;
    clearTimeout(s.timer); s.timer = null;
    if (reset) { s.polls = 0; s.pollingBlocked = false; }
    s.checking = true; s.message = ""; render();
    try {
      const response = s.job?.request_id ? await statusRequest(`${isParentJob(s.job)?"/api/securities/enrichment/ai":"/api/securities/risk-inputs/retrieval"}/${encodeURIComponent(s.job.request_id)}`) : await readStatus();
      if (!validSession(s)) return;
      acceptJob(s, response);
    } catch (error) {
      if (validSession(s)) {
        s.pollingBlocked = [401,403].includes(error.status);
        s.message = activeJob(s.job) && !s.pollingBlocked ? "Could not check progress. Retrying automatically…" : "Could not check progress. Select Check progress to retry.";
      }
    }
    finally { if (validSession(s)) { s.checking = false; scheduleProgress(s); render(); } }
  }
  async function load() {
    const s = session(); if (s.loading || s.checking || s.starting) return;
    clearTimeout(s.timer); s.timer = null;
    capture(); s.loading = true; s.message = ""; render();
    const results = await Promise.allSettled([api("/api/securities/risk-inputs/retrieval/candidates?refresh_policy=stale"),readStatus()]);
    if (!validSession(s)) return;
    if (results[0].status === "fulfilled") {
      s.items = results[0].value.items || []; s.loaded = true;
      populateSelect(el("riskRetrievalSecurities"),s,s.selected);
      if (s.schedule.loaded) populateSelect(el("riskRetrievalScheduleSecurities"),s,s.schedule.draft?.security_keys || []);
    } else s.message = "Could not load risk candidates. Select Reload to retry.";
    if (results[1].status === "fulfilled") acceptJob(s,results[1].value);
    else {
      s.pollingBlocked = [401,403].includes(results[1].reason?.status);
      s.message = activeJob(s.job) && !s.pollingBlocked ? "Could not check progress. Retrying automatically…" : "Could not check progress. Select Check progress to retry.";
    }
    s.loading = false; scheduleProgress(s); render();
  }
  async function start({retry=false} = {}) {
    const s = session(); if (!writable() || s.starting || s.loading || activeJob(s.job)) return;
    capture();
    const resume = retry && s.job?.status === "failed" && isParentJob(s.job);
    if (!resume && s.scope === "selected" && (!s.selected.length || s.selected.length > 3)) {
      s.message = "Choose between one and three securities, or use all missing securities."; render(); el("riskRetrievalSecurities").focus(); return;
    }
    s.starting = true; s.message = ""; s.polls = 0; render();
    try {
      const payload = resume ? {resume_request_id:s.job.request_id,security_keys:s.job.security_keys || null,
        data_types:s.job.data_types,position_scope:s.job.position_scope || "open",refresh_policy:s.job.refresh_policy || "missing",risk_mode:s.job.risk_mode || "api_then_ai"}
        : {security_keys:s.scope === "selected" ? s.selected : null,data_types:["risk_inputs"],position_scope:"open",refresh_policy:"stale",risk_mode:s.mode};
      const job = await api("/api/securities/enrichment/ai",{method:"POST",body:JSON.stringify(payload)});
      if (validSession(s)) acceptJob(s,job);
    } catch (error) {
      if (validSession(s)) {
        s.message = error.code === "enrichment_busy" ? "Another research request is active. Check progress before retrying." : "Could not start risk research. Check progress before trying again.";
        // A lost response can still represent a running request. Reconcile first.
        try { const active = await readStatus(); if (validSession(s) && activeJob(active)) { s.message = ""; acceptJob(s,active); } } catch { /* Preserve the retry guidance. */ }
      }
    } finally { if (validSession(s)) { s.starting = false; render(); } }
  }

  function captureSchedule(s) {
    if (!s.schedule.mounted || !window.ScheduleEditor) return;
    const snapshot = ScheduleEditor.snapshot(el("riskRetrievalScheduleEditor"));
    if (!snapshot) return;
    const selected = selectionValues(el("riskRetrievalScheduleSecurities"));
    s.schedule.draft = {...snapshot,mode:el("riskRetrievalScheduleMode").value,
      security_keys:el("riskRetrievalScheduleScope").value === "selected" ? selected : null};
  }
  function renderSchedule(s) {
    const view = s.schedule, editor = el("riskRetrievalScheduleEditor");
    if (!editor || !window.ScheduleEditor) return;
    const editable = writable() && view.loaded && !view.pending;
    if (!view.mounted || view.remount || view.language !== stressRiskLanguage() || view.editable !== editable) {
      if (view.mounted && !view.remount) captureSchedule(s);
      const draft = view.draft || {enabled:false,mode:"api_then_ai",security_keys:null,timezone:"UTC",schedule_config:{frequency:"weekly",weekdays:[0],hour:8,minute:0}};
      ScheduleEditor.mount(editor,draft,{translate:key=>text(key),editable});
      const frequency = editor.querySelector('[data-schedule-field="frequency"]');
      for (const option of [...frequency.options]) if (!["daily","weekly","monthly"].includes(option.value)) option.remove();
      el("riskRetrievalScheduleMode").value = draft.mode || "api_then_ai";
      el("riskRetrievalScheduleScope").value = Array.isArray(draft.security_keys) ? "selected" : "all";
      populateSelect(el("riskRetrievalScheduleSecurities"),s,draft.security_keys || []);
      view.mounted = true; view.remount = false; view.language = stressRiskLanguage(); view.editable = editable;
    }
    for (const control of editor.querySelectorAll("input,select")) {
      if (!editable) control.disabled = true;
    }
    for (const id of ["riskRetrievalScheduleMode","riskRetrievalScheduleScope","riskRetrievalScheduleSecurities"]) {
      el(id).disabled = !editable;
      for (const control of el(id).querySelectorAll("input")) control.disabled = !editable;
    }
    el("riskRetrievalScheduleSelectedField").hidden = el("riskRetrievalScheduleScope").value !== "selected";
    el("saveRiskRetrievalSchedule").disabled = !editable;
    el("reloadRiskRetrievalSchedule").disabled = view.pending;
    el("riskRetrievalScheduleSaved").textContent = view.saved ? `${text(modeLabels[view.saved.mode] || modeLabels.api_then_ai)} · ${ScheduleEditor.summary(view.saved,key=>text(key))} · ${typeof aiScheduleNextRun === "function" ? aiScheduleNextRun(view.saved) : ""}` : text("Schedule not loaded");
    el("riskRetrievalScheduleLastResult").textContent = view.saved?.last_run_code ? `${text("Last scheduled result")}: ${outcomeMessage(view.saved.last_run_code)}` : "";
    el("riskRetrievalScheduleStatus").textContent = view.pending ? text(view.saving ? "Saving schedule…" : "Loading schedule…") : view.message ? text(view.message) : view.dirty ? text("Unsaved changes") : "";
  }
  async function loadSchedule({preserveDraft=false} = {}) {
    const s = session(), view = s.schedule; if (view.pending) return;
    captureSchedule(s); view.pending = true; view.saving = false; view.message = ""; render();
    try {
      const saved = await api("/api/settings/risk-input-retrieval-schedule");
      if (!validSession(s)) return;
      view.saved = saved; view.loaded = true;
      if (!preserveDraft || !view.dirty) { view.draft = structuredClone(saved); view.dirty = false; }
      view.remount = true;
    } catch { if (validSession(s)) view.message = "Could not load schedule. Select Reload schedule to retry."; }
    finally { if (validSession(s)) { view.pending = false; render(); } }
  }
  async function saveSchedule() {
    const s = session(), view = s.schedule; if (!writable() || view.pending || !view.loaded) return;
    let payload;
    try { payload = ScheduleEditor.read(el("riskRetrievalScheduleEditor")); } catch { return; }
    captureSchedule(s);
    const keys = view.draft.security_keys;
    if (Array.isArray(keys) && (!keys.length || keys.length > 3)) {
      view.message = "Choose between one and three securities, or use all missing securities."; render(); el("riskRetrievalScheduleSecurities").focus(); return;
    }
    payload = {...payload,security_keys:keys,mode:view.draft.mode,language:stressRiskLanguage()};
    view.pending = true; view.saving = true; view.message = ""; render();
    try {
      const saved = await api("/api/settings/risk-input-retrieval-schedule",{method:"PUT",body:JSON.stringify(payload)});
      if (!validSession(s)) return;
      view.saved = saved; view.draft = structuredClone(saved); view.dirty = false; view.message = "Schedule saved."; view.remount = true;
    } catch { if (validSession(s)) view.message = "Could not save schedule. Review the fields and try again."; }
    finally { if (validSession(s)) { view.pending = false; view.saving = false; render(); } }
  }
  function open(trigger, scheduleOnly = false) {
    openModal("riskRetrievalModal",trigger);
    el("riskRetrievalScheduleDetails").open = scheduleOnly;
    render();
    load(); loadSchedule({preserveDraft:true});
    (scheduleOnly ? el("riskRetrievalScheduleDetails").querySelector("summary") : el("riskRetrievalTitle")).focus({preventScroll:true});
  }
  document.addEventListener("click", event => {
    const trigger = event.target.closest?.("[data-open-risk-input-retrieval]");
    if (trigger) open(trigger,trigger.dataset.openRiskInputRetrieval === "schedule");
    if (event.target.closest?.("#startRiskRetrieval")) start();
    if (event.target.closest?.("#retryRiskRetrieval")) start({retry:true});
    if (event.target.closest?.("#reloadRiskRetrieval")) load();
    if (event.target.closest?.("#checkRiskRetrieval")) checkProgress({reset:true});
    if (event.target.closest?.("#reloadRiskRetrievalSchedule")) loadSchedule();
    if (event.target.closest?.("#saveRiskRetrievalSchedule")) saveSchedule();
  });
  document.addEventListener("change", event => {
    if (event.target.closest?.("#riskRetrievalRunFields")) { capture(); render(); }
    if (event.target.closest?.("#riskRetrievalScheduleDetails") && !session().schedule.pending) {
      const s = session(); captureSchedule(s); s.schedule.dirty = true; render();
    }
  });
  document.addEventListener("input", event => {
    if (event.target.closest?.("#riskRetrievalScheduleDetails") && !session().schedule.pending) {
      const s = session(); captureSchedule(s); s.schedule.dirty = true;
      el("riskRetrievalScheduleStatus").textContent = text("Unsaved changes");
    }
  });
  function visibilityChanged() {
    const s = currentSession;
    if (!s || !validSession(s)) return;
    clearTimeout(s.timer); s.timer = null;
    if (researchVisible() && activeJob(s.job) && !s.pollingBlocked && !s.loading && !s.checking && !s.starting) checkProgress();
  }
  document.addEventListener("visibilitychange",visibilityChanged);
  new MutationObserver(visibilityChanged).observe(el("riskRetrievalModal"),{attributes:true,attributeFilter:["hidden"]});
  new MutationObserver(() => { if (el("riskRetrievalModal") && !el("riskRetrievalModal").hidden) render(); })
    .observe(document.documentElement,{attributes:true,attributeFilter:["lang"]});
  window.RiskInputRetrievalPresentation = Object.freeze({fields,outcomeMessage,flattenJob});
})();
