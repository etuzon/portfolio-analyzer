/* Named schedules share the application's recurrence editor and bounded jobs. */
(() => {
  "use strict";
  const ENDPOINT = "/api/settings/research-schedules";
  const el = id => document.getElementById(id);
  const txt = key => t(key);
  const actor = () => String(typeof currentUser === "function" ? currentUser()?.id || "" : "");
  const types = {prices:"Prices",profile:"Company profile",company_ratings:"Company credit ratings",risk_inputs:"Risk inputs",country_ratings:"Country credit ratings"};
  const codes = {queued:"Queued",running:"Running",completed:"Completed",enrichment_busy:"Skipped because research is busy",
    interrupted:"The app restarted during research. Review saved results and run the schedule again.",
    owner_not_authorized:"The schedule owner no longer has editing permission.",invalid_schedule:"The schedule settings could not be used. Reload and review the schedule.",
    ai_unavailable:"AI research is unavailable. Review the configured assistant, then retry.",schedule_changed:"The schedule changed during research. Review it before retrying.",
    request_limit:"The request budget was reached. Review saved results before retrying.",check_incomplete:"Some research checks could not finish. Review results before retrying.",
    public_research_not_attempted:"Some research checks could not finish. Review results before retrying."};
  let current = null;
  function session() {
    if (!current || current.actor !== actor()) {
      clearTimeout(current?.timer);
      current = {actor:actor(),rows:[],inventory:[],countries:[],loaded:false,pending:false,loading:false,version:0,message:"",draft:null,editing:null,dirty:false,timer:null,polls:0,inventoryLoaded:false};
      if (el("researchScheduleForm")) el("researchScheduleForm").hidden = true;
    }
    return current;
  }
  const valid = s => s === current && s.actor === actor();
  const writable = () => canWrite() && !state.auth.forcedPasswordChange && !currentUser()?.must_change_password;
  const selected = id => [...el(id).selectedOptions].map(option => option.value);
  function defaults() {
    return {name:"",enabled:false,data_types:["risk_inputs"],position_scope:"open",security_keys:null,country_scope:"accounts",country_codes:null,
      mode:"api_then_ai",refresh_policy:"stale",timezone:state.backupSettings?.timezone || "UTC",language:state.language,
      schedule_config:{frequency:"weekly",weekdays:[0],hour:8,minute:0}};
  }
  function capture() {
    const s = session();
    if (!s.draft || el("researchScheduleForm").hidden) return;
    const recurrence = ScheduleEditor.snapshot(el("researchScheduleEditor")) || {};
    s.draft = {...s.draft,...recurrence,name:el("researchScheduleName").value,
      data_types:[...el("researchScheduleTargets").querySelectorAll("input:checked")].map(input=>input.value),
      refresh_policy:el("researchScheduleRefresh").value,position_scope:el("researchScheduleSecurityScope").value,
      country_scope:el("researchScheduleCountryScope").value,mode:el("researchScheduleMode").value,
      security_keys:selected("researchScheduleSecurities"),country_codes:selected("researchScheduleCountries")};
  }
  function scopeLabel(row) {
    const result = [];
    if ((row.data_types || []).some(type => type !== "country_ratings")) {
      result.push(txt({open:"Open positions",all:"Open and closed positions",selected:"Selected securities"}[row.position_scope] || "Open positions"));
      if (row.position_scope === "selected") result.push((row.security_keys || []).map(key=>key.split("|").join(" · ")).join(", "));
    }
    if ((row.data_types || []).includes("country_ratings")) {
      result.push(txt({accounts:"Countries linked to accounts",all:"All countries",selected:"Selected countries"}[row.country_scope] || "Countries linked to accounts"));
      if (row.country_scope === "selected") result.push((row.country_codes || []).map(code=>countryName(code)).join(", "));
    }
    return result.join(" · ");
  }
  function renderList() {
    const s = session();
    const container = el("researchScheduleList"); if (!container) return;
    const focus = document.activeElement?.closest?.("[data-research-schedule-action]");
    const restore = focus ? {id:focus.dataset.ruleId,action:focus.dataset.researchScheduleAction} : null;
    container.innerHTML = s.rows.length ? s.rows.map(row => {
      const last = row.last_run_code ? txt(codes[row.last_run_code] || "Research failed. Review prerequisites and retry.") : txt("Not run yet");
      const date = row.last_run_at ? window.AIResearchFormatting?.dateTime(row.last_run_at,row.timezone) : "";
      const disabled = !writable() || s.pending;
      return `<article class="ai-research-schedule-row" data-rule-id="${esc(row.id)}"><h4>${esc(row.name)} · ${esc(txt(row.active ? "Running" : row.enabled ? "Enabled" : "Paused"))}</h4>
        <p>${esc((row.data_types || []).map(type=>txt(types[type] || "Other data")).join(", "))} · ${esc(scopeLabel(row))}</p>
        <p>${esc(ScheduleEditor.summary(row,txt))}</p><p>${esc(txt({missing:"Missing fields",stale:"Missing or stale fields",refresh_existing:"Recheck existing data too"}[row.refresh_policy] || "Missing or stale fields"))}${row.data_types?.includes("risk_inputs") ? ` · ${esc(txt({api_then_ai:"Public API, then AI",api:"Public API only",ai:"AI only"}[row.mode] || "Public API, then AI"))}` : ""}</p>
        <p>${esc(typeof aiScheduleNextRun === "function" ? aiScheduleNextRun(row) : "")}</p>
        <p>${esc(txt("Last scheduled result"))}: ${esc(last)}${date ? ` · ${esc(date)}` : ""}</p>
        <div class="modal-toolbar">${[["edit","Edit"],["run","Run now"],["delete","Delete"]].map(([action,label])=>`<button type="button" class="secondary compact-button" data-research-schedule-action="${action}" data-rule-id="${esc(row.id)}"${disabled || action === "run" && row.active ? " disabled" : ""}>${esc(txt(label))}</button>`).join("")}</div></article>`;
    }).join("") : `<p class="section-note">${esc(txt(s.loaded ? "No research schedules yet. Add a schedule to choose its data and timing." : "Loading schedules…"))}</p>`;
    el("newResearchSchedule").disabled = !writable() || s.pending || !s.loaded;
    el("reloadResearchSchedules").disabled = s.pending;
    el("researchSchedulesStatus").textContent = s.pending ? txt("Loading schedules…") : s.message ? txt(s.message) : "";
    if (restore) [...container.querySelectorAll("[data-research-schedule-action]")].find(button=>button.dataset.ruleId===restore.id && button.dataset.researchScheduleAction===restore.action)?.focus({preventScroll:true});
  }
  function setFormBusy(busy) {
    el("researchScheduleForm").querySelectorAll("input,select,button").forEach(control=>{control.disabled=busy || !writable();});
  }
  function syncFields() {
    const targets = [...el("researchScheduleTargets").querySelectorAll("input:checked")].map(input=>input.value);
    const securities = targets.some(type=>type !== "country_ratings"), countries = targets.includes("country_ratings");
    el("researchScheduleSecurityScopeField").hidden = !securities;
    el("researchScheduleSecuritiesField").hidden = !securities || el("researchScheduleSecurityScope").value !== "selected";
    el("researchScheduleCountryScopeField").hidden = !countries;
    el("researchScheduleCountriesField").hidden = !countries || el("researchScheduleCountryScope").value !== "selected";
    el("researchScheduleModeField").hidden = !targets.includes("risk_inputs");
  }
  function populate(select, rows, values, key, label) {
    select.replaceChildren();
    const chosen = new Set(values || []);
    for (const row of rows) { const option = document.createElement("option"); option.value = key(row); option.textContent = label(row); option.selected = chosen.has(option.value); select.append(option); }
    for (const value of chosen) if (![...select.options].some(option=>option.value===value)) {
      const option = document.createElement("option"); option.value = value; option.textContent = value; option.selected = true; select.append(option);
    }
  }
  function mountForm({focus=false} = {}) {
    const s = session(), draft = s.draft; if (!draft) return;
    el("researchScheduleForm").hidden = false;
    el("researchScheduleFormTitle").textContent = txt(s.editing ? "Edit research schedule" : "New research schedule");
    el("researchScheduleName").value = draft.name || "";
    el("researchScheduleRefresh").value = draft.refresh_policy || "stale";
    el("researchScheduleSecurityScope").value = draft.position_scope || "open";
    el("researchScheduleCountryScope").value = draft.country_scope || "accounts";
    el("researchScheduleMode").value = draft.mode || "api_then_ai";
    el("researchScheduleTargets").querySelectorAll("input").forEach(input=>{input.checked=(draft.data_types || []).includes(input.value);});
    populate(el("researchScheduleSecurities"),s.inventory,draft.security_keys,row=>row.security_key,row=>`${row.symbol} · ${row.stock_market} · ${row.currency}`);
    populate(el("researchScheduleCountries"),s.countries,draft.country_codes,row=>row.country_code,row=>countryName(row.country_code));
    ScheduleEditor.mount(el("researchScheduleEditor"),draft,{translate:txt,editable:writable() && !s.pending});
    syncFields(); setFormBusy(s.pending);
    if (focus) el("researchScheduleName").focus();
  }
  async function load({preserveDraft=true,background=false} = {}) {
    const s = session(); if (s.pending || s.loading || !currentUser()) return;
    const focused=document.activeElement, focusId=focused?.id, scheduleField=focused?.dataset.scheduleField, focusValue=focused?.value;
    if (preserveDraft && !background) capture();
    const version=s.version;s.loading=true;
    if(!background){s.pending=true;s.message="";renderList();setFormBusy(true);}
    const results = await Promise.allSettled(background?[api(ENDPOINT)]:[api(ENDPOINT),api(ENDPOINT+"/inventory"),api("/api/countries/credit-ratings/countries?country_scope=all")]);
    if (!valid(s)) return;
    s.loading=false;
    if(s.version!==version)return;
    if (results[0].status === "fulfilled") { s.rows=results[0].value.items || []; s.loaded=true;
      if(!background && s.editing && s.draft && !s.dirty){const row=s.rows.find(row=>row.id===s.editing);if(row)s.draft=structuredClone(row);}}
    else s.message = "Could not load schedules. Select Reload schedules to retry.";
    if (results[1]?.status === "fulfilled") { s.inventory=results[1].value.items || []; s.inventoryLoaded=true; }
    if (results[2]?.status === "fulfilled") s.countries=results[2].value.items || [];
    if (results[1]?.status === "rejected" || results[2]?.status === "rejected") s.message = "Some selections could not be loaded. Reload schedules before choosing securities or countries.";
    if(!background)s.pending=false;renderList();
    if (!background && s.draft) {mountForm();
      if(focusId)el(focusId)?.focus({preventScroll:true});else if(scheduleField)[...el("researchScheduleEditor").querySelectorAll("[data-schedule-field]")].find(control=>control.dataset.scheduleField===scheduleField && (!["weekdays","month_days"].includes(scheduleField) || control.value===focusValue))?.focus({preventScroll:true});}
    clearTimeout(s.timer);
    if (s.rows.some(row=>row.active) && s.polls++ < 120) s.timer=setTimeout(()=>{if(valid(s))load({background:true});},4000);
  }
  function edit(identifier=null) {
    const s = session(); if (!writable() || s.pending) return;
    if (s.dirty && !confirm(txt("Discard unsaved schedule changes?"))) return;
    const row = identifier ? s.rows.find(row=>row.id===identifier) : null;
    s.editing=identifier; s.draft=structuredClone(row || defaults()); s.dirty=false;
    el("researchScheduleError").textContent=""; mountForm({focus:true});
  }
  async function save(event) {
    event.preventDefault(); const s=session(); if(!writable() || s.pending || !s.draft) return;
    capture();
    let recurrence;
    try { recurrence=ScheduleEditor.read(el("researchScheduleEditor")); }
    catch(error) {el("researchScheduleError").textContent=txt(error.message);return;}
    const draft=s.draft, targets=draft.data_types || [];
    if(!draft.name.trim() || !targets.length) {el("researchScheduleError").textContent=txt("Enter a schedule name and choose at least one data type.");if(!draft.name.trim())el("researchScheduleName").focus();else el("researchScheduleTargets").querySelector("input")?.focus();return;}
    if(targets.some(type=>type!=="country_ratings") && draft.position_scope==="selected" && (!draft.security_keys?.length || draft.security_keys.length>3)) {el("researchScheduleError").textContent=txt("Choose between one and three securities.");el("researchScheduleSecurities").focus();return;}
    if(targets.includes("country_ratings") && draft.country_scope==="selected" && (!draft.country_codes?.length || draft.country_codes.length>3)) {el("researchScheduleError").textContent=txt("Choose between one and three countries.");el("researchScheduleCountries").focus();return;}
    const payload={...recurrence,name:draft.name.trim(),data_types:targets,refresh_policy:draft.refresh_policy,mode:draft.mode,language:state.language,
      position_scope:targets.some(type=>type!=="country_ratings")?draft.position_scope:"open",security_keys:draft.position_scope==="selected"?draft.security_keys:null,
      country_scope:targets.includes("country_ratings")?draft.country_scope:"accounts",country_codes:draft.country_scope==="selected"?draft.country_codes:null,
      ...(s.editing?{expected_revision:draft.revision}: {})};
    s.version++;s.pending=true;setFormBusy(true);el("researchScheduleError").textContent=txt("Saving schedule…");
    try {
      const row=await api(s.editing?`${ENDPOINT}/${encodeURIComponent(s.editing)}`:ENDPOINT,{method:s.editing?"PUT":"POST",body:JSON.stringify(payload)});
      if(!valid(s))return;
      const index=s.rows.findIndex(item=>item.id===row.id);if(index>=0)s.rows[index]=row;else s.rows.push(row);
      s.editing=row.id;s.draft=structuredClone(row);s.dirty=false;s.message="Schedule saved.";
      el("researchScheduleError").textContent=txt("Schedule saved.");
    } catch {if(valid(s))el("researchScheduleError").textContent=txt("Could not save schedule. Your changes are kept. Reopen Edit to review a changed schedule before retrying.");}
    finally {if(valid(s)){s.pending=false;setFormBusy(false);renderList();el("saveResearchSchedule").focus({preventScroll:true});}}
  }
  async function action(identifier,action) {
    const s=session();if(!writable() || s.pending)return;
    if(action==="edit"){edit(identifier);return;}
    if(action==="delete" && !confirm(txt("Delete this research schedule?")))return;
    s.version++;s.pending=true;s.message="";renderList();setFormBusy(true);
    try {
      await api(`${ENDPOINT}/${encodeURIComponent(identifier)}${action==="run"?"/run":""}`,{method:action==="run"?"POST":"DELETE",...(action==="run"?{body:"{}"}:{})});
      if(!valid(s))return;
      if(action==="delete"){
        s.rows=s.rows.filter(row=>row.id!==identifier);
        if(s.editing===identifier){s.draft=null;s.editing=null;s.dirty=false;el("researchScheduleForm").hidden=true;}
        s.message="Schedule deleted.";
      }else{s.message="The scheduled research request was queued.";s.polls=0;}
    }catch{if(valid(s))s.message=action==="run"?"Could not start scheduled research. A busy run is skipped; retry with Run now or wait for its next time.":"Could not delete schedule. Reload schedules and try again.";}
    finally{if(valid(s)){s.pending=false;renderList();setFormBusy(false);if(action==="delete")el("newResearchSchedule").focus({preventScroll:true});if(action==="run")load();}}
  }
  document.addEventListener("submit",event=>{if(event.target.id==="researchScheduleForm")save(event);});
  document.addEventListener("click",event=>{
    const button=event.target.closest?.("[data-research-schedule-action]");if(button)action(button.dataset.ruleId,button.dataset.researchScheduleAction);
    if(event.target.closest?.("#newResearchSchedule"))edit();
    if(event.target.closest?.("#reloadResearchSchedules"))load();
    if(event.target.closest?.("#cancelResearchSchedule")){const s=session();if(!s.dirty || confirm(txt("Discard unsaved schedule changes?"))){s.draft=null;s.dirty=false;s.editing=null;el("researchScheduleForm").hidden=true;el("newResearchSchedule").focus({preventScroll:true});}}
  });
  for(const type of ["input","change"])document.addEventListener(type,event=>{
    if(event.target.closest?.("#researchScheduleForm") && !session().pending){capture();session().dirty=true;el("researchScheduleError").textContent=txt("Unsaved changes");syncFields();}
  });
  new MutationObserver(()=>{
    if(!el("aiEnrichmentModal") || el("aiEnrichmentModal").hidden)return;
    const focus=document.activeElement?.id;capture();renderList();if(session().draft)mountForm();if(focus)el(focus)?.focus({preventScroll:true});
  }).observe(document.documentElement,{attributes:true,attributeFilter:["lang"]});
  window.AIResearchSchedules=Object.freeze({open:()=>{session();renderList();load();},reset:()=>{clearTimeout(current?.timer);current=null;},render:renderList});
})();
