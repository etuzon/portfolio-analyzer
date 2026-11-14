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
        starting:false,checking:false,job:null,message:"",timer:null,polls:0,refreshed:new Set(),
        schedule:{loaded:false,pending:false,saving:false,dirty:false,saved:null,draft:null,message:"",mounted:false,remount:false}};
    }
    return currentSession;
  };
  const modeLabels = {api_then_ai:"Public API, then AI",api:"Public API only",ai:"AI only"};
  const statusLabels = {queued:"Queued",running:"Running",completed:"Completed",failed:"Failed",updated:"Updated",
    partial:"Partially updated",unavailable:"Unavailable",not_attempted:"Not attempted"};
  const stageLabels = {queued:"Queued",api:"Checking public APIs…",ai:"Researching missing risk inputs with AI…",completed:"Completed",failed:"Failed"};
  const fieldLabels = {issuer_identity:"Issuer identity",issuer_id:"Issuer identity",issuer_name:"Issuer name",issuer_domicile:"Issuer domicile",
    country:"Country exposure",country_code:"Issuer country",country_basis:"Country exposure basis",country_exposure:"Country exposure",filing_sources:"Regulatory filing sources",
    country_rating:"Sovereign rating",credit_rating:"Security credit rating",sovereign_rating:"Sovereign rating",
    country_currency:"Country crisis currency",currency_exposures:"Economic currency exposure",fx:"Economic currency exposure",
    instrument_kind:"Instrument type",bond_kind:"Instrument type",bond_terms:"Bond terms",pricing_model:"Bond pricing model",
    plain_nominal_noncallable:"Plain nominal noncallable bond",zero_coupon_confirmed:"Confirmed zero coupon",bond_maturity:"Redemption date",
    maturity_date:"Redemption date",bond_cashflows:"Future bond payments",cashflows:"Future bond payments",
    bond_yield:"Discount yield",continuous_yield:"Discount yield",current_spread:"Current credit spread",current_spread_bps:"Current credit spread",
    sovereign_currency_basis:"Sovereign rating currency basis",country_sensitivity:"Country spread sensitivity",
    fund_lookthrough:"Underlying fund allocations",parameters_unverified:"Verified instrument terms",parameters_stale:"Current bond pricing evidence",
    parameters_unavailable:"Risk inputs",valuation:"Saved valuation",valuation_stale:"Current valuation",asset_class:"Asset class",
    rating_stale:"Current rating evidence",rating_unverified:"Verified rating evidence"};
  const fields = values => (Array.isArray(values) ? values : []).map(value => text(fieldLabels[String(value).split(":")[0]] || "Other required risk inputs")).join(", ") || text("None");
  const outcomeMessage = code => text({data_found:"Supported risk evidence was saved.",partial_data:"Some evidence was found; remaining inputs stay missing.",
    data_unavailable:"No supported public evidence was found for the requested inputs.",provider_unavailable:"The public source could not be reached. Retry later.",
    ai_unavailable:"AI research is unavailable. Review the configured assistant, then retry.",request_limit:"The request budget was reached. Review saved results before retrying.",
    evidence_rejected:"The retrieved evidence did not meet the validation requirements.",identity_changed:"The security identity changed. Reload candidates before retrying.",
    owner_not_authorized:"The schedule owner no longer has editing permission.",enrichment_busy:"Another research request is active. Check progress before retrying.",
    queued:"The scheduled research request was queued.",invalid_schedule:"The schedule settings could not be used. Reload and review the schedule."}[code] || "The requested risk inputs remain missing.");

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
      const retrieved = source.retrieved_at && typeof formatDateTime === "function" ? text("Retrieved {date}", {date:formatDateTime(source.retrieved_at)}) : "";
      return `<span><a href="${escape(url.href)}" target="_blank" rel="noopener noreferrer">${escape(text("Source {number}", {number:index + 1}))}</a>${retrieved ? ` · ${escape(retrieved)}` : ""}</span>`;
    } catch { return ""; }
  }
  function render() {
    const s = session(), job = s.job, running = activeJob(job), busy = s.loading || s.starting || s.checking;
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
    el("checkRiskRetrieval").disabled = s.checking || s.starting;
    el("checkRiskRetrieval").hidden = !job;
    el("retryRiskRetrieval").hidden = !job || running || !(job.outcomes || []).some(row => row.status !== "updated" || row.missing_fields?.length);
    el("retryRiskRetrieval").disabled = !writable() || busy || running;
    el("riskRetrievalCount").textContent = s.loaded ? text("{count} securities have risk inputs to review", {count:stressRiskNumber(s.items.length,0)}) : "";
    const coverage = job?.coverage;
    el("riskRetrievalCoverage").textContent = coverage ? text("This run includes {selected} of {total} candidates; {remaining} remain outside this batch.", {
      selected:stressRiskNumber(coverage.selected || 0,0),total:stressRiskNumber(coverage.total_candidates || 0,0),remaining:stressRiskNumber(coverage.remaining || 0,0)}) : "";
    const progress = job?.progress || {};
    const stage = stageLabels[progress.stage] || statusLabels[job?.status];
    el("riskRetrievalStatus").textContent = s.loading ? text("Loading risk research…") : s.starting ? text("Starting risk research…")
      : s.message ? text(s.message) : job ? [text(stage || "Running"),
        text("{completed} of {total} securities", {completed:stressRiskNumber(progress.completed || 0,0),total:stressRiskNumber(progress.total || 0,0)}),
        progress.current_security?.symbol || ""].filter(Boolean).join(" · ") : text("No risk research has been run yet.");
    const bar = el("riskRetrievalProgress");
    bar.hidden = !running || !(progress.total > 0); bar.max = Math.max(1,progress.total || 1); bar.value = progress.completed || 0;
    el("riskRetrievalResults").innerHTML = (job?.outcomes || []).map(row => `<li><div class="risk-retrieval-result-heading"><bdi dir="auto">${escape(row.symbol || row.security_key)}</bdi><strong>${escape(text(statusLabels[row.status] || "Unavailable"))}</strong></div>
      <p>${escape(outcomeMessage(row.code))}</p><p>${escape(text("Available inputs"))}: ${escape(fields(row.available_fields))}</p><p>${escape(text("Still missing"))}: ${escape(fields(row.missing_fields))}</p>
      <div class="risk-retrieval-sources">${(row.sources || []).map(sourceLink).filter(Boolean).join(" · ")}</div>
      ${row.security_key ? `<button type="button" class="secondary compact-button" data-risk-inputs-security-key="${escape(row.security_key)}" data-risk-inputs-symbol="${escape(row.symbol || "")}">${escape(text("Review risk inputs"))}</button>` : ""}</li>`).join("");
    renderSchedule(s);
  }
  function acceptJob(s, job) {
    if (!validSession(s)) return;
    s.job = job;
    if (job?.portfolio_refresh_required && !activeJob(job) && !s.refreshed.has(job.request_id)) {
      s.refreshed.add(job.request_id);
      document.dispatchEvent(new CustomEvent("stress-risk-inputs-changed"));
    }
    clearTimeout(s.timer);
    if (activeJob(job)) {
      if (s.polls >= 120) s.message = "Progress checks paused. Select Check progress to resume.";
      else s.timer = setTimeout(() => { if (validSession(s)) { s.polls++; checkProgress(); } },3000);
    }
  }
  async function checkProgress({reset=false} = {}) {
    const s = session(); if (s.checking) return;
    if (reset) s.polls = 0;
    s.checking = true; s.message = ""; render();
    try {
      const response = await api(s.job?.request_id ? `/api/securities/risk-inputs/retrieval/${encodeURIComponent(s.job.request_id)}` : "/api/securities/risk-inputs/retrieval/status");
      if (!validSession(s)) return;
      acceptJob(s, s.job?.request_id ? response : response.active_job || response.last_job);
    } catch { if (validSession(s)) s.message = "Could not check progress. Select Check progress to retry."; }
    finally { if (validSession(s)) { s.checking = false; render(); } }
  }
  async function load() {
    const s = session(); if (s.loading) return;
    capture(); s.loading = true; s.message = ""; render();
    const results = await Promise.allSettled([api("/api/securities/risk-inputs/retrieval/candidates"),api("/api/securities/risk-inputs/retrieval/status")]);
    if (!validSession(s)) return;
    if (results[0].status === "fulfilled") {
      s.items = results[0].value.items || []; s.loaded = true;
      populateSelect(el("riskRetrievalSecurities"),s,s.selected);
      if (s.schedule.loaded) populateSelect(el("riskRetrievalScheduleSecurities"),s,s.schedule.draft?.security_keys || []);
    } else s.message = "Could not load risk candidates. Select Reload to retry.";
    if (results[1].status === "fulfilled") acceptJob(s,results[1].value.active_job || results[1].value.last_job);
    else s.message = "Could not check progress. Select Check progress to retry.";
    s.loading = false; render();
  }
  async function start() {
    const s = session(); if (!writable() || s.starting || s.loading || activeJob(s.job)) return;
    capture();
    if (s.scope === "selected" && (!s.selected.length || s.selected.length > 3)) {
      s.message = "Choose between one and three securities, or use all missing securities."; render(); el("riskRetrievalSecurities").focus(); return;
    }
    s.starting = true; s.message = ""; s.polls = 0; render();
    try {
      const job = await api("/api/securities/risk-inputs/retrieval",{method:"POST",body:JSON.stringify({security_keys:s.scope === "selected" ? s.selected : null,mode:s.mode,language:stressRiskLanguage()})});
      if (validSession(s)) acceptJob(s,job);
    } catch (error) {
      if (validSession(s)) {
        s.message = error.code === "enrichment_busy" ? "Another research request is active. Check progress before retrying." : "Could not start risk research. Check progress before trying again.";
        // A lost response can still represent a running request. Reconcile first.
        try { const status = await api("/api/securities/risk-inputs/retrieval/status"); if (validSession(s) && status.active_job) { s.message = ""; acceptJob(s,status.active_job); } } catch { /* Preserve the retry guidance. */ }
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
    if (event.target.closest?.("#startRiskRetrieval, #retryRiskRetrieval")) start();
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
  new MutationObserver(() => { if (el("riskRetrievalModal") && !el("riskRetrievalModal").hidden) render(); })
    .observe(document.documentElement,{attributes:true,attributeFilter:["lang"]});
  window.RiskInputRetrievalPresentation = Object.freeze({fields,outcomeMessage});
})();
