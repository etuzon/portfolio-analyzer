/* Sovereign evidence is keyed by ISO country, agency and currency basis. */
function sovereignRatingsSession() {
  const owner = currentUser()?.id, token = state.auth?.csrfToken;
  if (!state.sovereignRatings || state.sovereignRatings.owner !== owner || state.sovereignRatings.token !== token) {
    Object.values(state.sovereignRatings?.countries || {}).forEach((entry) => clearTimeout(entry.timer));
    clearTimeout(state.sovereignRatings?.global?.batch?.timer);
    state.sovereignRatings = { owner, token, securities: {}, countries: {}, view: $("countryRatingsModal") && !$("countryRatingsModal").hidden ? "global" : "security", global: { scope: "accounts", selected: "", items: [], loading: false, version: 0, message: "", batch: null }, schedule: { loaded:false, pending:false, dirty:false, message:"", saved:null, draft:null } };
  }
  return state.sovereignRatings;
}
function sovereignSecurityEntry(detail = state.securityDetail) {
  if (!detail?.symbol) return null;
  const session = sovereignRatingsSession();
  const identity = { symbol: detail.symbol, stock_market: detail.item?.holding?.stock_market || detail.market_key || detail.stock_market || "MANUAL", currency: detail.currency || "" };
  const key = Object.values(identity).map((value) => String(value).trim().toUpperCase()).join("|");
  return session.securities[key] ||= { key, identity, country: null, loading: false, saving: false, version: 0, message: "" };
}
function sovereignCountryEntry(code) {
  if (!code) return null;
  const session = sovereignRatingsSession();
  return session.countries[code] ||= { key: code, context: null, basis: "foreign_currency", loading: false, pending: false, starting: false, resume: false, timer: null, polls: 0, version: 0, message: "" };
}
function sovereignEntryActive(entry, country = true) {
  const session = state.sovereignRatings;
  return Boolean(session && currentUser()?.id === session.owner && state.auth?.csrfToken === session.token
    && (country ? session.countries : session.securities)[entry.key] === entry);
}
function sovereignCurrentCountry() { const session=sovereignRatingsSession(); return sovereignCountryEntry(session.view === "global" ? session.global.selected : sovereignSecurityEntry()?.country?.country_code); }
function sovereignCountryLabel(code) {
  const label=state.language === "he" ? `${countryName(code)} ${flagFor(code)}` : `${flagFor(code)} ${countryName(code)}`;
  return state.language === "he" ? bidiIsolate(label,"rtl") : label;
}
function sovereignBasisLabel(value) { return t({ foreign_currency: "Foreign currency", local_currency: "Local currency", unknown: "Unspecified currency basis" }[value] || "Unspecified currency basis"); }
function sovereignManualRecord(entry, agency) { return entry.context?.manual_ratings?.find((row) => row.agency === agency && row.currency_basis === entry.basis); }
function sovereignManualRevision(context, agency, basis) { return Number(context?.manual_revisions?.[`${agency}:${basis}`] || 0); }
function sovereignFilteredContext(entry) {
  const context = entry.context || {};
  return { ...context, ratings: (context.ratings || []).filter((row) => row.currency_basis === entry.basis),
    retrieved_ratings: (context.retrieved_ratings || []).filter((row) => row.currency_basis === entry.basis),
    manual_ratings: (context.manual_ratings || []).filter((row) => row.currency_basis === entry.basis) };
}
function sovereignActionsHtml(context, agency) {
  if (!canWrite()) return "";
  return `<button type="button" class="secondary compact-button manual-credit-open" data-edit-sovereign="${esc(agency)}" aria-controls="sovereignManualEditor"${context.identity_token ? "" : " disabled"}>${esc(t(context.manual_ratings?.some((row) => row.agency === agency) ? "Edit manually" : "Add manually"))}</button>`;
}
function renderSovereignCreditRatings() {
  const panel = $("sovereignCreditRatings"), detail = state.securityDetail;
  if (!panel) return;
  const session=sovereignRatingsSession(), globalView=session.view === "global";
  if (!globalView && !detail) { panel.hidden=true; return; }
  // Funds do not acquire the domicile of their exchange or trading currency.
  panel.hidden = !globalView && !creditRatingsEligible({ ...detail, asset_class: detail.asset_class || "EQUITY" });
  if (panel.hidden) return;
  const security = globalView ? {country:null} : sovereignSecurityEntry(), country = security.country, entry = sovereignCurrentCountry();
  $("sovereignCountryAssignment").hidden=globalView;
  $("sovereignCountryIdentity").hidden=globalView;
  panel.setAttribute("aria-busy", String(security.loading || security.saving || Boolean(entry?.loading || entry?.starting || entry?.pending)));
  const name = country?.country_code ? sovereignCountryLabel(country.country_code) : t("Unknown");
  $("sovereignCountryIdentity").textContent = `${t("Issuer domicile")}: ${name}${country?.country_code ? ` (${country.country_code}) · ${t(country.source_kind === "manual" ? "Manual" : "Issuer profile")}` : ""}`;
  const code = $("sovereignCountryCode");
  if (document.activeElement !== code && !security.countryDraft) code.value = country?.country_code || "";
  code.disabled = !canWrite() || security.loading || security.saving;
  $("saveSovereignCountry").disabled = !canWrite() || security.loading || security.saving || !country?.security_key || security.needsReload || Boolean(entry?.manual?.saving);
  $("saveSovereignCountry").textContent = t(security.saving ? "Saving…" : "Save country");
  $("clearSovereignCountry").hidden = country?.source_kind !== "manual";
  $("clearSovereignCountry").disabled = $("saveSovereignCountry").disabled;
  $("sovereignCreditRatingsContent").hidden = !entry;
  const basis = $("sovereignCurrencyBasis");
  const options = ["foreign_currency", "local_currency", "unknown"].map((value) => `<option value="${value}">${esc(sovereignBasisLabel(value))}</option>`).join("");
  if (basis.innerHTML !== options) basis.innerHTML = options;
  if (entry) basis.value = entry.basis;
  basis.disabled = Boolean(entry?.manual?.saving);
  const busy = Boolean(entry?.starting || entry?.pending);
  $("refreshSovereignRatings").disabled = !canWrite() || !entry?.context?.country_key || entry.loading || busy || entry.resume || Boolean(entry?.manual?.saving) || state.auth?.forcedPasswordChange || currentUser()?.must_change_password;
  $("refreshSovereignRatings").title = t(canWrite() ? "Research Moody’s, S&P Global Ratings and Fitch from public sources with AI." : "Rating updates require Admin or Operator permission.");
  $("resumeSovereignRatings").hidden = !entry?.resume;
  $("resumeSovereignRatings").disabled = busy || Boolean(entry?.loading);
  $("reloadSovereignRatings").disabled = security.loading || security.saving || Boolean(entry?.loading || entry?.manual?.saving);
  let message = security.loading ? "Loading issuer domicile…" : security.message || (entry?.loading ? "Loading saved ratings…" : busy ? "Researching sovereign ratings…" : entry?.message || "");
  if (!message && !entry && !globalView) message = "Issuer domicile is unknown. An Admin or Operator can assign its ISO country code.";
  if (!message && !canWrite()) message = "Viewing saved ratings. Refresh requires Admin or Operator permission.";
  $("sovereignCreditRatingsStatus").textContent = message ? t(message) : "";
  $("sovereignCreditRatingsStatus").hidden = !message;
  if (globalView) renderSovereignGlobal();
  if (!entry) { $("sovereignManualEditor").hidden = true; return; }
  const rows = $("sovereignCreditRatingsRows"), html = creditRatingsRows(sovereignFilteredContext(entry), { actions: sovereignActionsHtml });
  if (rows.innerHTML !== html) {
    const open = new Set([...rows.querySelectorAll("details[open]")].map((node) => node.dataset.creditDisclosure));
    const active = document.activeElement?.dataset?.editSovereign;
    rows.innerHTML = html;
    rows.querySelectorAll("details").forEach((node) => { node.open = open.has(node.dataset.creditDisclosure); });
    if (active) rows.querySelector(`[data-edit-sovereign="${active}"]`)?.focus({ preventScroll: true });
  }
  renderCreditRatingHistory(entry.context, "sovereignRatingHistory");
  renderSovereignManualEditor(entry);
}
async function loadSovereignCountry(entry = sovereignCurrentCountry(), { force = false } = {}) {
  if(entry?.manual?.saving){entry.reloadAfterManual=true;return false;}
  if (!entry || !sovereignEntryActive(entry) || entry.loading && !force || entry.manual?.saving) return false;
  const version = ++entry.version; entry.loading = true;
  renderSovereignCreditRatings();
  try {
    const context = await creditRatingsRequest(`/api/countries/credit-ratings?${new URLSearchParams({country_code: entry.key})}`);
    if (!sovereignEntryActive(entry) || version !== entry.version) return false;
    if (context.country_code !== entry.key || !context.identity_token) throw Error("invalid_country_response");
    entry.context = context; entry.message = "";
    if (entry.manual?.needsReload) {
      if (entry.manual.expectedIdentity !== context.identity_token) entry.manual.identityChanged = true;
      else { entry.manual.expectedRevision = sovereignManualRevision(context, entry.manual.agency, entry.manual.basis); entry.manual.needsReload = false; entry.manual.message = "Saved records reloaded. Review your draft before saving again."; }
    }
    return true;
  } catch {
    if (sovereignEntryActive(entry) && version === entry.version) entry.message = "Saved country ratings could not be loaded. Reload saved ratings to retry.";
    return false;
  } finally {
    if (sovereignEntryActive(entry) && version === entry.version) { entry.loading = false; renderSovereignCreditRatings(); }
  }
}
async function loadSovereignAssignment(security = sovereignSecurityEntry()) {
  if (!security || !sovereignEntryActive(security, false) || security.loading || security.saving) return;
  const version = ++security.version; security.loading = true; renderSovereignCreditRatings();
  try {
    const country = await creditRatingsRequest(`/api/securities/country?${new URLSearchParams(security.identity)}`);
    if (!sovereignEntryActive(security, false) || version !== security.version) return;
    security.country = country; security.message = ""; security.needsReload = false;
    if (country.country_code) loadSovereignCountry(sovereignCountryEntry(country.country_code));
  } catch {
    if (sovereignEntryActive(security, false) && version === security.version) security.message = "Issuer domicile could not be loaded. Reload saved ratings to retry.";
  } finally {
    if (sovereignEntryActive(security, false) && version === security.version) { security.loading = false; renderSovereignCreditRatings(); }
  }
}
function openSovereignCreditRatings(detail) {
  const session=sovereignRatingsSession(); session.view="security";
  const slot=$("sovereignSecuritySlot"), panel=$("sovereignCreditRatings");
  if(slot && panel)slot.after(panel);
  const security = sovereignSecurityEntry(detail); if (!security) return;
  renderSovereignCreditRatings();
  if (!$("sovereignCreditRatings")?.hidden) {
    loadSovereignAssignment(security);
    const entry = sovereignCountryEntry(security.country?.country_code);
    if (entry?.pending) scheduleSovereignPoll(entry);
  }
}
async function persistSovereignAssignment(clear = false) {
  const security = sovereignSecurityEntry(), entry = sovereignCurrentCountry();
  if (!canWrite() || !security?.country?.security_key || security.saving || security.loading || security.needsReload || entry?.manual?.saving) return;
  const code = $("sovereignCountryCode").value.trim().toUpperCase();
  if (!clear && !/^[A-Z]{2}$/.test(code)) { security.message = "Enter a valid two-letter ISO country code."; renderSovereignCreditRatings(); $("sovereignCountryCode").focus(); return; }
  security.saving = true; security.message = ""; renderSovereignCreditRatings();
  const payload = { security_key: security.country.security_key, country_code: code, expected_revision: security.country.revision, expected_identity: security.country.identity_token };
  try {
    const params = new URLSearchParams({security_key: payload.security_key, expected_revision: String(payload.expected_revision),expected_identity:payload.expected_identity});
    const country = await creditRatingsRequest(clear ? `/api/securities/country?${params}` : "/api/securities/country", clear ? {method:"DELETE"} : {method:"PUT",body:JSON.stringify(payload)});
    if (!sovereignEntryActive(security, false)) return;
    if (country.security_key !== security.country.security_key) throw Error("invalid_country_assignment");
    security.country = country; security.countryDraft = false; security.message = "Issuer domicile saved. Country ratings remain separate from company ratings.";
    if (country.country_code) loadSovereignCountry(sovereignCountryEntry(country.country_code));
  } catch (error) {
    if (sovereignEntryActive(security, false)) { security.needsReload = error?.status === 409 || !Number.isFinite(error?.status) || error.status >= 500; security.message = error?.status === 409 ? "The country assignment changed. Reload saved ratings before saving again." : error?.status === 422 ? "Enter a valid two-letter ISO country code." : "The country assignment could not be saved. Reload saved ratings and retry."; }
  } finally { if (sovereignEntryActive(security, false)) { security.saving = false; renderSovereignCreditRatings(); } }
}
function acceptSovereignJob(entry, job) {
  entry.job = job; entry.pending = ["queued", "running"].includes(job.status); entry.resume = false;
  entry.message = entry.pending ? "" : job.status === "failed" ? "Rating research could not finish. Saved evidence is retained; refresh ratings to retry." : "Rating check finished. Unverified agency information remains unknown.";
  if (!entry.pending) loadSovereignCountry(entry, {force:true});
  renderSovereignCreditRatings();
}
function scheduleSovereignPoll(entry) {
  clearTimeout(entry.timer);
  if (!entry.pending || !sovereignEntryActive(entry)) return;
  if (entry.polls >= 120) { entry.pending = false; entry.resume = true; entry.message = "Rating research is taking longer. Check AI progress to read the same request."; renderSovereignCreditRatings(); return; }
  entry.timer = setTimeout(() => checkSovereignProgress(entry), 3000);
}
async function checkSovereignProgress(entry = sovereignCurrentCountry()) {
  if (!entry?.job?.request_id || !sovereignEntryActive(entry)) return;
  clearTimeout(entry.timer); entry.pending = true; entry.resume = false; entry.polls += 1; renderSovereignCreditRatings();
  try {
    const job = await creditRatingsRequest(`/api/countries/credit-ratings/ai/${encodeURIComponent(entry.job.request_id)}`);
    if (!sovereignEntryActive(entry)) return;
    acceptSovereignJob(entry, job); scheduleSovereignPoll(entry);
  } catch { if (sovereignEntryActive(entry)) { entry.pending = false; entry.resume = true; entry.message = "Rating progress could not be loaded. Check AI progress to retry the same request."; renderSovereignCreditRatings(); } }
}
async function refreshSovereignRatings() {
  const entry = sovereignCurrentCountry();
  if (!canWrite() || !entry?.context?.country_key || entry.pending || entry.starting || entry.loading || entry.resume || entry.manual?.saving || state.auth?.forcedPasswordChange || currentUser()?.must_change_password) return;
  entry.starting = true; entry.message = ""; entry.polls = 0; renderSovereignCreditRatings();
  try {
    const job = await creditRatingsRequest("/api/countries/credit-ratings/ai", {method:"POST",body:JSON.stringify({country_scope:"all",country_codes:[entry.key],language:state.language})});
    if (!sovereignEntryActive(entry)) return;
    acceptSovereignJob(entry, job); scheduleSovereignPoll(entry);
  } catch (error) { if (sovereignEntryActive(entry)) entry.message = error?.status === 409 ? "A rating check is already running. Wait for it to finish, then refresh this security." : "The rating request could not be confirmed. Reload saved ratings, then retry if needed."; }
  finally { if (sovereignEntryActive(entry)) { entry.starting = false; renderSovereignCreditRatings(); } }
}
function sovereignManualDraft(entry, agency) {
  const basis = entry.basis, saved = sovereignManualRecord(entry, agency);
  return { agency, basis, saving:false, needsReload:false, message:"", expectedIdentity:entry.context.identity_token, expectedRevision:sovereignManualRevision(entry.context,agency,basis),
    values:{status:saved?.status||"rated",rating:saved?.rating||"",outlook:saved?.outlook||"unknown",watch:saved?.watch||"unknown",scope:"issuer",entity_name:saved?.entity_name||entry.context.country_name||entry.key,source_url:saved?.source_url||"",notes:saved?.notes||"",
      rating_date:saved?.rating_date?formatDate(saved.rating_date):"",outlook_date:saved?.outlook_date?formatDate(saved.outlook_date):"",watch_date:saved?.watch_date?formatDate(saved.watch_date):""} };
}
const SOVEREIGN_MANUAL_FIELDS = {Status:"status",Grade:"rating",Outlook:"outlook",Watch:"watch",Scope:"scope",Entity:"entity_name",Source:"source_url",Notes:"notes",RatingDate:"rating_date",OutlookDate:"outlook_date",WatchDate:"watch_date"};
function sovereignSetOptions(suffix, options) {
  const input = $(`sovereignManual${suffix}`), html = options.map(([value,label])=>`<option value="${esc(value)}">${esc(label)}</option>`).join("");
  if (input.innerHTML !== html) input.innerHTML = html;
}
function renderSovereignManualEditor(entry = sovereignCurrentCountry()) {
  const panel = $("sovereignManualEditor"), editor = entry?.manual;
  panel.hidden = !canWrite() || !editor || editor.basis !== entry.basis;
  if (panel.hidden) return;
  if (editor.expectedIdentity !== entry.context?.identity_token) { editor.identityChanged = true; editor.message = "The country identity changed. Close this editor and start a new entry."; }
  $("sovereignManualEditorTitle").textContent = `${t("Manual rating")} · ${manualCreditAgencyName(editor.agency)}`;
  $("sovereignManualSecurity").textContent = `${sovereignCountryLabel(entry.key)} (${entry.key}) · ${sovereignBasisLabel(editor.basis)}`;
  sovereignSetOptions("Status",["rated","unrated","withdrawn"].map((value)=>[value,t({rated:"Rated",unrated:"Unrated",withdrawn:"Withdrawn"}[value])]));
  sovereignSetOptions("Grade",[["",t("Select rating")],...MANUAL_CREDIT_GRADES[editor.agency].map((value)=>[value,value])]);
  sovereignSetOptions("Outlook",["unknown","positive","negative","stable","developing"].map((value)=>[value,creditRatingsDirection(value)]));
  sovereignSetOptions("Watch",["unknown","positive","negative","developing","none"].map((value)=>[value,creditRatingsDirection(value,true)]));
  sovereignSetOptions("Scope",[["issuer",t("Sovereign credit rating")]]);
  const busy = editor.saving || entry.loading;
  for (const [suffix,field] of Object.entries(SOVEREIGN_MANUAL_FIELDS)) {
    const input = $(`sovereignManual${suffix}`);
    if (document.activeElement !== input && input.value !== editor.values[field]) input.value = editor.values[field];
    input.disabled = busy || editor.identityChanged || ["rating","outlook","watch"].includes(field) && editor.values.status !== "rated";
    input.setAttribute("aria-invalid",String(editor.invalidField === input.id));
  }
  $("sovereignManualEntity").readOnly = true;
  $("sovereignManualEntityHint").textContent = t("Country identity is shared by ISO code.");
  $("sovereignManualScopeHint").textContent = `${t("Global scale")} · ${t("Long term")} · ${sovereignBasisLabel(editor.basis)}`;
  $("sovereignManualActiveFields").hidden = editor.values.status !== "rated";
  $("sovereignManualOutlookDateField").hidden = editor.values.status !== "rated" || editor.values.outlook === "unknown";
  $("sovereignManualWatchDateField").hidden = editor.values.status !== "rated" || editor.values.watch === "unknown";
  $("saveSovereignManualRating").disabled = busy || editor.needsReload || editor.identityChanged;
  $("saveSovereignManualRating").textContent = t(editor.saving?"Saving…":"Save manual rating");
  $("clearSovereignManualRating").hidden = !sovereignManualRecord(entry,editor.agency);
  $("clearSovereignManualRating").disabled = $("saveSovereignManualRating").disabled;
  $("cancelSovereignManualRating").disabled = editor.saving;
  $("reloadSovereignManualRating").hidden = !editor.needsReload;
  $("reloadSovereignManualRating").disabled = busy;
  $("sovereignManualEditorStatus").textContent = editor.message?t(editor.message):"";
  panel.setAttribute("aria-busy",String(busy));
}
function openSovereignManual(agency) {
  const entry = sovereignCurrentCountry();
  if (!canWrite() || !entry?.context?.identity_token || !MANUAL_CREDIT_GRADES[agency] || entry.manual?.saving) return;
  entry.drafts ||= {};
  if (entry.manual) entry.drafts[`${entry.manual.agency}:${entry.manual.basis}`] = entry.manual;
  entry.manual = entry.drafts[`${agency}:${entry.basis}`] ||= sovereignManualDraft(entry,agency);
  renderSovereignCreditRatings(); $("sovereignManualEditor").scrollIntoView?.({block:"nearest"}); $("sovereignManualStatus").focus({preventScroll:true});
}
function updateSovereignManual(target, normalize = false) {
  const entry = sovereignCurrentCountry(), editor = entry?.manual;
  if (!editor || editor.saving || !canWrite()) return;
  const field = SOVEREIGN_MANUAL_FIELDS[target.id.replace(/^sovereignManual/,"")];
  if (!field || field === "entity_name" || field === "scope") return;
  editor.values[field] = target.value;
  if (normalize && field.endsWith("_date") && parseDateInput(target.value)) target.value = editor.values[field] = formatDate(parseDateInput(target.value));
  if (field === "status" && target.value !== "rated") Object.assign(editor.values,{rating:"",outlook:"unknown",watch:"unknown",outlook_date:"",watch_date:""});
  if (field === "outlook" && target.value === "unknown") editor.values.outlook_date = "";
  if (field === "watch" && target.value === "unknown") editor.values.watch_date = "";
  editor.invalidField = ""; if (!editor.needsReload) editor.message = ""; renderSovereignManualEditor(entry);
}
async function persistSovereignManual(clear = false) {
  const entry = sovereignCurrentCountry(), editor = entry?.manual;
  if (!canWrite() || !editor || editor.saving || editor.needsReload || editor.identityChanged || entry.loading || editor.basis !== entry.basis) return;
  const invalid = clear?null:manualCreditValidation(editor);
  if (invalid) { editor.message = invalid[0]; editor.invalidField = invalid[1].replace(/^manualCredit/,"sovereignManual"); renderSovereignManualEditor(entry); const input = $(editor.invalidField); if(input.closest("details"))input.closest("details").open=true; input.focus(); return; }
  const value = editor.values, payload = {country_code:entry.key,agency:editor.agency,currency_basis:editor.basis,expected_identity:editor.expectedIdentity,expected_revision:editor.expectedRevision,
    status:value.status,rating:value.status === "rated"?value.rating:null,outlook:value.status === "rated"?value.outlook:"unknown",watch:value.status === "rated"?value.watch:"unknown",entity_name:value.entity_name,
    source_url:value.source_url.trim()||null,notes:value.notes.trim(),rating_date:parseDateInput(value.rating_date)||null,outlook_date:parseDateInput(value.outlook_date)||null,watch_date:parseDateInput(value.watch_date)||null};
  editor.saving = true; editor.message = ""; entry.version += 1; renderSovereignCreditRatings();
  try {
    const params = new URLSearchParams({country_code:entry.key,agency:editor.agency,currency_basis:editor.basis,expected_identity:editor.expectedIdentity,expected_revision:String(editor.expectedRevision)});
    const context = await creditRatingsRequest(clear?`/api/countries/credit-ratings/manual?${params}`:"/api/countries/credit-ratings/manual",clear?{method:"DELETE"}:{method:"PUT",body:JSON.stringify(payload)});
    if (!sovereignEntryActive(entry) || entry.manual !== editor) return;
    if (context.country_code !== entry.key || !context.identity_token) throw Error("invalid_country_response");
    entry.context = context; entry.version += 1;
    const key = `${editor.agency}:${editor.basis}`;
    if (clear) { delete entry.drafts?.[key]; entry.manual = null; entry.message = "Manual override cleared. Retrieved agency evidence is shown."; }
    else { entry.manual = sovereignManualDraft(entry,editor.agency); entry.drafts[key] = entry.manual; entry.manual.message = "Manual rating saved. Retrieved agency evidence remains available."; }
  } catch (error) {
    if (sovereignEntryActive(entry) && entry.manual === editor) { editor.message = error?.status === 409 ? "This manual entry changed. Reload saved ratings and review your draft before saving again." : manualCreditError(error); editor.needsReload = error?.status === 409 || !Number.isFinite(error?.status) || error.status >= 500; }
  } finally { if (sovereignEntryActive(entry)) { editor.saving = false; renderSovereignCreditRatings(); if (clear && !entry.manual) $("sovereignCreditRatingsRows").querySelector(`[data-edit-sovereign="${editor.agency}"]`)?.focus({preventScroll:true}); if(entry.reloadAfterManual){entry.reloadAfterManual=false;loadSovereignCountry(entry,{force:true});} } }
}
document.addEventListener("submit", (event) => {
  if (event.target.id === "sovereignCountryForm") { event.preventDefault(); persistSovereignAssignment(); }
  if (event.target.id === "sovereignManualForm") { event.preventDefault(); persistSovereignManual(); }
});
document.addEventListener("input", (event) => {
  if (event.target.id === "sovereignCountryCode") { const entry=sovereignSecurityEntry(); if(entry)entry.countryDraft=true; }
  if (event.target.closest?.("#sovereignManualEditor")) updateSovereignManual(event.target);
});
document.addEventListener("change", (event) => {
  if (event.target.id === "sovereignCurrencyBasis") { const entry=sovereignCurrentCountry(); if(entry && !entry.manual?.saving) {entry.basis=event.target.value;renderSovereignCreditRatings();} }
  if (event.target.closest?.("#sovereignManualEditor")) updateSovereignManual(event.target,true);
});
document.addEventListener("click", (event) => {
  const agency=event.target.closest?.("[data-edit-sovereign]")?.dataset.editSovereign;
  if (agency) openSovereignManual(agency);
  if(event.target.closest?.("#refreshSovereignRatings"))refreshSovereignRatings();
  if(event.target.closest?.("#resumeSovereignRatings")){const entry=sovereignCurrentCountry();if(entry && !entry.pending){entry.polls=0;checkSovereignProgress(entry);}}
  if(event.target.closest?.("#reloadSovereignRatings")){if(sovereignRatingsSession().view!=="global")loadSovereignAssignment();const entry=sovereignCurrentCountry();if(entry)loadSovereignCountry(entry,{force:true});}
  if(event.target.closest?.("#clearSovereignCountry"))persistSovereignAssignment(true);
  if(event.target.closest?.("#clearSovereignManualRating"))persistSovereignManual(true);
  if(event.target.closest?.("#reloadSovereignManualRating"))loadSovereignCountry(sovereignCurrentCountry(),{force:true});
  if(event.target.closest?.("#cancelSovereignManualRating")){const entry=sovereignCurrentCountry();if(entry?.manual && !entry.manual.saving){const agency=entry.manual.agency;delete entry.drafts?.[`${agency}:${entry.manual.basis}`];entry.manual=null;renderSovereignCreditRatings();$("sovereignCreditRatingsRows").querySelector(`[data-edit-sovereign="${agency}"]`)?.focus({preventScroll:true});}}
});
function sovereignGlobalActive(view) { const session=sovereignRatingsSession(); return session.global === view; }
function renderSovereignGlobal() {
  const session=sovereignRatingsSession(), view=session.global;
  if (!$('countryRatingsModal'))return;
  $('sovereignResearchScope').value=view.scope;
  $('sovereignScopeHint').hidden=view.scope!=='all';
  $('sovereignResearchScope').disabled=view.loading || Boolean(view.batch?.pending || view.batch?.resume || view.batch?.starting);
  const choice=$('sovereignSelectedCountry');
  const optionsKey=[state.language,...view.items.map(row=>row.country_code)].join('|');
  if(view.optionsKey!==optionsKey){
    choice.innerHTML=(view.items.length?view.items.map((row)=>`<option value="${esc(row.country_code)}">${esc(sovereignCountryLabel(row.country_code))} (${esc(row.country_code)})</option>`):[`<option value="">${esc(t('No countries in this scope'))}</option>`]).join('');
    view.optionsKey=optionsKey;
  }
  choice.value=view.selected;
  choice.disabled=view.loading || !view.items.length || Boolean(sovereignCurrentCountry()?.manual?.saving);
  $('researchCountryScope').disabled=!canWrite() || view.loading || view.loadedScope!==view.scope || !view.items.length || Boolean(view.batch?.pending || view.batch?.resume || view.batch?.starting) || state.auth?.forcedPasswordChange || currentUser()?.must_change_password;
  $('resumeCountryScope').hidden=!view.batch?.resume;
  $('resumeCountryScope').disabled=Boolean(view.batch?.pending);
  $('reloadCountryInventory').disabled=view.loading;
  const remaining=Number(view.batch?.job?.summary?.not_attempted || view.batch?.job?.credit_ratings?.summary?.not_attempted || 0);
  $('retryCountryScope').hidden=!view.batch?.job?.request_id || !remaining || Boolean(view.batch?.pending || view.batch?.starting || view.batch?.resume);
  $('retryCountryScope').disabled=!canWrite() || Boolean(view.batch?.pending || view.batch?.starting || view.batch?.resume);
  let message=view.loading?t('Loading countries…'):view.message?t(view.message):view.items.length?t('Countries in scope: {count}').replace('{count}',String(view.items.length)):t('No countries in this scope');
  if(view.unknownAccountCountries)message+=` · ${t('Accounts with an unknown country: {count}').replace('{count}',String(view.unknownAccountCountries))}`;
  $('countryInventoryStatus').textContent=message;
  const batch=view.batch, job=batch?.job, summary=job?.credit_ratings?.summary || job?.summary, progress=job?.credit_ratings?.progress || job?.progress;
  let status=batch?.message?t(batch.message):batch?.pending?t('Researching sovereign ratings…'):'';
  if(progress && Number.isFinite(Number(progress.total)))status+=`${status?' · ':''}${t('Countries checked: {completed} of {total}').replace('{completed}',String(progress.completed||0)).replace('{total}',String(progress.total||0))}`;
  if(summary && !batch?.pending)status+=`${status?' · ':''}${t('Updated: {updated}; partial: {partial}; unavailable: {unavailable}').replace('{updated}',String(summary.updated||0)).replace('{partial}',String(summary.partial||0)).replace('{unavailable}',String(summary.unavailable||0))}`;
  if(status && job?.country_scope)status=`${t(job.country_scope==='all'?'All countries':'Account countries')} · ${status}`;
  $('countryResearchStatus').textContent=status;$('countryResearchStatus').hidden=!status;
  renderSovereignSchedule();
}
async function loadSovereignInventory() {
  const view=sovereignRatingsSession().global;
  if(view.loading)return;
  const version=++view.version,scope=view.scope;
  if(view.loadedScope!==scope){view.items=[];view.selected='';}
  view.loading=true;view.message='';renderSovereignCreditRatings();
  try{
    const result=await creditRatingsRequest(`/api/countries/credit-ratings/countries?${new URLSearchParams({country_scope:scope})}`);
    if(!sovereignGlobalActive(view)||view.version!==version)return;
    view.items=Array.isArray(result.items)?result.items:[];view.loadedScope=scope;
    view.unknownAccountCountries=Number(result.unknown_account_countries||0);
    if(!view.items.some(row=>row.country_code===view.selected))view.selected=view.items[0]?.country_code||'';
    if(view.selected)loadSovereignCountry(sovereignCountryEntry(view.selected));
  }catch{if(sovereignGlobalActive(view)&&view.version===version)view.message='Countries could not be loaded. Reload countries to retry.';}
  finally{if(sovereignGlobalActive(view)&&view.version===version){view.loading=false;renderSovereignCreditRatings();}}
}
async function openCountryRatings() {
  if(!currentUser() || currentUser().must_change_password)return;
  const session=sovereignRatingsSession();session.view='global';
  $('sovereignGlobalSlot').append($('sovereignCreditRatings'));
  renderSovereignCreditRatings();
  const mobile=window.matchMedia('(max-width: 760px)').matches;
  openModal('countryRatingsModal',mobile?$('navigationToggle'):$('openCountryRatings'),{focusId:'countryRatingsTitle'});
  document.querySelectorAll('.nav-menu[open]').forEach(menu=>{menu.open=false;});
  setMobileNavigation(false);
  loadSovereignInventory();loadSovereignSchedule({preserveDraft:true});
  if(session.global.batch?.pending)scheduleSovereignScopePoll(session.global);
  try{
    const status=await creditRatingsRequest('/api/countries/credit-ratings/status');
    if(!sovereignGlobalActive(session.global)||session.global.batch?.pending||session.global.batch?.starting)return;
    const job=status.active_job||status.last_job;
    if(job){acceptSovereignScopeJob(session.global,job);scheduleSovereignScopePoll(session.global);}
  }catch{/* Saved country browsing remains available when progress cannot be recovered. */}
}
function acceptSovereignScopeJob(view,job) {
  const batch=view.batch||={polls:0};batch.job=job;batch.pending=['queued','running'].includes(job.status);batch.resume=false;
  batch.message=batch.pending?'':job.status==='failed'?'Rating research could not finish. Saved evidence is retained; refresh ratings to retry.':'Rating check finished. Unverified agency information remains unknown.';
  if(!batch.pending){const entry=sovereignCurrentCountry();if(entry)loadSovereignCountry(entry,{force:true});}
  renderSovereignGlobal();
}
function scheduleSovereignScopePoll(view) {
  clearTimeout(view.batch?.timer);
  if(!sovereignGlobalActive(view)||!view.batch?.pending)return;
  if(view.batch.polls>=120){view.batch.pending=false;view.batch.resume=true;view.batch.message='Rating research is taking longer. Check AI progress to read the same request.';renderSovereignGlobal();return;}
  view.batch.timer=setTimeout(()=>checkSovereignScopeProgress(view),3000);
}
async function checkSovereignScopeProgress(view=sovereignRatingsSession().global) {
  const batch=view.batch;if(!batch?.job?.request_id||!sovereignGlobalActive(view))return;
  clearTimeout(batch.timer);batch.pending=true;batch.resume=false;batch.polls+=1;renderSovereignGlobal();
  try{
    const job=await creditRatingsRequest(`/api/countries/credit-ratings/ai/${encodeURIComponent(batch.job.request_id)}`);
    if(!sovereignGlobalActive(view))return;
    acceptSovereignScopeJob(view,job);scheduleSovereignScopePoll(view);
  }catch{if(sovereignGlobalActive(view)){batch.pending=false;batch.resume=true;batch.message='Rating progress could not be loaded. Check AI progress to retry the same request.';renderSovereignGlobal();}}
}
async function researchSovereignScope({resume=false}={}) {
  const view=sovereignRatingsSession().global,previous=view.batch?.job;
  if(!canWrite()||view.loading||!resume&&(view.loadedScope!==view.scope||!view.items.length)||resume&&!previous?.request_id||view.batch?.pending||view.batch?.starting||view.batch?.resume||state.auth?.forcedPasswordChange||currentUser()?.must_change_password)return;
  const payload={country_scope:resume?previous.country_scope:view.scope,language:state.language};
  if(resume){payload.resume_request_id=previous.request_id;if(Array.isArray(previous.country_codes))payload.country_codes=previous.country_codes;}
  view.batch={starting:true,pending:false,resume:false,polls:0,message:'',job:resume?previous:null};const batch=view.batch;renderSovereignGlobal();
  try{
    const job=await creditRatingsRequest('/api/countries/credit-ratings/ai',{method:'POST',body:JSON.stringify(payload)});
    if(!sovereignGlobalActive(view))return;
    acceptSovereignScopeJob(view,job);scheduleSovereignScopePoll(view);
  }catch(error){if(sovereignGlobalActive(view))batch.message=error?.status===409?'A rating check is already running. Wait for it to finish, then refresh this security.':'The rating request could not be confirmed. Reload saved ratings, then retry if needed.';}
  finally{if(sovereignGlobalActive(view)){batch.starting=false;renderSovereignGlobal();}}
}
function captureSovereignScheduleDraft() {
  const schedule=sovereignRatingsSession().schedule, editor=$('countryScheduleEditor');
  const snapshot=window.ScheduleEditor?.snapshot(editor);
  if(snapshot)schedule.draft={...snapshot,country_scope:$('countryScheduleScope').value||'accounts'};
}
function renderSovereignSchedule() {
  if(!window.ScheduleEditor||!$('countryScheduleEditor'))return;
  const schedule=sovereignRatingsSession().schedule,editor=$('countryScheduleEditor');
  const editable=canWrite()&&schedule.loaded&&!schedule.pending;
  if(schedule.renderLanguage!==state.language||schedule.renderEditable!==editable||!schedule.mounted||schedule.remount){
    if(schedule.mounted&&!schedule.remount)captureSovereignScheduleDraft();
    const focused=editor.contains(document.activeElement)?{field:document.activeElement.dataset.scheduleField,value:document.activeElement.value}:null;
    const draft=schedule.draft||schedule.saved||{enabled:false,country_scope:'accounts',timezone:'UTC',schedule_config:{frequency:'weekly',weekdays:[0],hour:8,minute:0}};
    ScheduleEditor.mount(editor,draft,{translate:t,editable,afterEnabled:$('countryScheduleScopeFields')});
    $('countryScheduleScope').value=draft.country_scope||'accounts';
    schedule.renderLanguage=state.language;schedule.renderEditable=editable;schedule.mounted=true;schedule.remount=false;
    if(focused)[...editor.querySelectorAll('[data-schedule-field]')].find(node=>node.dataset.scheduleField===focused.field&&(!['weekdays','month_days'].includes(focused.field)||node.value===focused.value))?.focus({preventScroll:true});
  }
  $('countryScheduleScope').disabled=!editable;
  $('countryScheduleScopeHint').hidden=$('countryScheduleScope').value!=='all';
  $('saveCountrySchedule').disabled=!editable;
  $('reloadCountrySchedule').disabled=schedule.pending;
  const saved=schedule.saved;
  $('countryScheduleSaved').textContent=saved?`${t(saved.country_scope==='all'?'All countries':'Account countries')} · ${ScheduleEditor.summary(saved,t)} · ${aiScheduleNextRun(saved)}`:t('Schedule not loaded');
  $('countryScheduleStatus').textContent=schedule.pending?t(schedule.saving?'Saving schedule…':'Loading schedule…'):schedule.message?t(schedule.message):schedule.dirty?t('Unsaved changes'):'';
}
async function loadSovereignSchedule({preserveDraft=false}={}) {
  const session=sovereignRatingsSession(),schedule=session.schedule;if(schedule.pending)return;
  captureSovereignScheduleDraft();schedule.pending=true;schedule.saving=false;renderSovereignSchedule();
  try{
    const saved=await creditRatingsRequest('/api/settings/country-rating-schedule');
    if(sovereignRatingsSession()!==session)return;
    schedule.saved=saved;schedule.loaded=true;schedule.message='';
    if(!preserveDraft||!schedule.dirty){schedule.draft={...saved,schedule_config:{...saved.schedule_config}};schedule.dirty=false;schedule.remount=true;}
  }catch{if(sovereignRatingsSession()===session)schedule.message='Could not load schedule. Select Reload schedule to retry.';}
  finally{if(sovereignRatingsSession()===session){schedule.pending=false;renderSovereignSchedule();}}
}
async function saveSovereignSchedule() {
  const session=sovereignRatingsSession(),schedule=session.schedule;if(!canWrite()||!schedule.loaded||schedule.pending)return;
  let payload;try{payload={...ScheduleEditor.read($('countryScheduleEditor')),country_scope:$('countryScheduleScope').value,language:state.language};}catch{return;}
  captureSovereignScheduleDraft();schedule.pending=true;schedule.saving=true;renderSovereignSchedule();
  try{
    const saved=await creditRatingsRequest('/api/settings/country-rating-schedule',{method:'PUT',body:JSON.stringify(payload)});
    if(sovereignRatingsSession()!==session)return;
    schedule.saved=saved;schedule.draft={...saved,schedule_config:{...saved.schedule_config}};schedule.dirty=false;schedule.message='Schedule saved.';schedule.remount=true;
  }catch{if(sovereignRatingsSession()===session)schedule.message='Could not save schedule. Review the fields and try again.';}
  finally{if(sovereignRatingsSession()===session){schedule.pending=false;schedule.saving=false;renderSovereignSchedule();}}
}
document.addEventListener('click',event=>{
  if(event.target.closest?.('#openCountryRatings'))openCountryRatings();
  if(event.target.closest?.('#reloadCountryInventory'))loadSovereignInventory();
  if(event.target.closest?.('#researchCountryScope'))researchSovereignScope();
  if(event.target.closest?.('#retryCountryScope'))researchSovereignScope({resume:true});
  if(event.target.closest?.('#resumeCountryScope')){const view=sovereignRatingsSession().global;if(view.batch&&!view.batch.pending){view.batch.polls=0;checkSovereignScopeProgress(view);}}
  if(event.target.closest?.('#reloadCountrySchedule'))loadSovereignSchedule();
  if(event.target.closest?.('#saveCountrySchedule'))saveSovereignSchedule();
});
document.addEventListener('change',event=>{
  const session=sovereignRatingsSession(),view=session.global;
  if(event.target.id==='sovereignResearchScope'&&!view.loading&&!view.batch?.pending&&!view.batch?.resume&&!view.batch?.starting){view.scope=event.target.value;loadSovereignInventory();}
  if(event.target.id==='sovereignSelectedCountry'){view.selected=event.target.value;renderSovereignCreditRatings();if(view.selected)loadSovereignCountry(sovereignCountryEntry(view.selected));}
  if(event.target.closest?.('#countryScheduleEditor')){captureSovereignScheduleDraft();session.schedule.dirty=true;renderSovereignSchedule();}
});
document.addEventListener('input',event=>{if(event.target.closest?.('#countryScheduleEditor')){const session=sovereignRatingsSession();captureSovereignScheduleDraft();session.schedule.dirty=true;renderSovereignSchedule();}});
