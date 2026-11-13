/* User-entered overrides are separate from retrieved agency evidence. */
const MANUAL_CREDIT_GRADES = Object.freeze({
  moodys: ["Aaa", "Aa1", "Aa2", "Aa3", "A1", "A2", "A3", "Baa1", "Baa2", "Baa3", "Ba1", "Ba2", "Ba3", "B1", "B2", "B3", "Caa1", "Caa2", "Caa3", "Ca", "C"],
  sp: ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "SD", "D"],
  fitch: ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "RD", "D"],
});

function manualCreditRecord(context, agency) {
  return (Array.isArray(context?.manual_ratings) ? context.manual_ratings : []).find((row) => row.agency === agency) || null;
}

function manualCreditAgencyName(agency) {
  return { moodys: "Moody’s", sp: "S&P Global Ratings", fitch: "Fitch" }[agency] || agency;
}

function manualCreditIsBond(detail = state.securityDetail) {
  const holding = detail?.item?.holding || detail || {};
  return [detail?.asset_class, detail?.asset_sub_class, holding.asset_class, holding.asset_sub_class].some((value) => ["BOND", "FIXED_INCOME"].includes(String(value || "").toUpperCase()));
}

function manualCreditDraft(entry, agency, isBond = manualCreditIsBond()) {
  const saved = manualCreditRecord(entry.context, agency), policy = entry.context?.manual_policy || {};
  const verified = Boolean(policy.issuer_identity_verified && policy.canonical_issuer_name);
  isBond = isBond || policy.issue_rating_allowed === true;
  return { agency, saving: false, reloading: false, needsReload: false, identityChanged: false, message: "", isBond, issueAllowed: policy.issue_rating_allowed === true,
    expectedIdentity: entry.context.identity_token, expectedRevision: Number(entry.context.manual_revisions?.[agency] || 0),
    values: { status: saved?.status || "rated", rating: saved?.rating || "", outlook: saved?.outlook || "unknown", watch: saved?.watch || "unknown",
      scope: saved?.scope || (isBond && policy.issue_rating_allowed ? "" : "issuer"),
      entity_name: saved?.entity_name || (verified ? policy.canonical_issuer_name : ""), source_url: saved?.source_url || "", notes: saved?.notes || "",
      rating_date: saved?.rating_date ? formatDate(saved.rating_date) : "", outlook_date: saved?.outlook_date ? formatDate(saved.outlook_date) : "", watch_date: saved?.watch_date ? formatDate(saved.watch_date) : "" } };
}

function manualCreditActionsHtml(context, agency) {
  if (!canWrite()) return "";
  const saved = manualCreditRecord(context, agency), ready = context?.identity_token && context?.manual_policy;
  return `<button class="secondary compact-button manual-credit-open" type="button" data-edit-manual-credit="${esc(agency)}" aria-controls="manualCreditEditor"${ready ? "" : " disabled"}>${esc(t(saved ? "Edit manually" : "Add manually"))}</button>`;
}

function manualCreditEvidenceHtml(record, retrieved, agency) {
  const facts = [["Rated entity", record.entity_name || t("Unknown")], ["Identity", t(record.identity_verification === "user_entered" ? "Manual identity" : "Verified issuer identity")],
    ["Entered", record.created_at ? formatDateTime(record.created_at) : t("Unknown")], ["Last updated", record.updated_at ? formatDateTime(record.updated_at) : t("Unknown")],
    ["Updated by", record.updated_by || t("Unknown")], ["Rating/status action date", creditRatingsDate(record.rating_date)]];
  if (record.outlook_date) facts.push(["Outlook date", creditRatingsDate(record.outlook_date)]);
  if (record.watch_date) facts.push(["Watch date", creditRatingsDate(record.watch_date)]);
  const sourceUrl = creditRatingsSourceUrl(record.source_url);
  const original = retrieved || { status: "not_checked", outlook: "unknown", watch: "unknown" };
  const originalStatus = original.status === "rated" ? original.rating || t("Unknown")
    : t({ unrated: "Unrated", withdrawn: "Withdrawn", not_found: "Not found", not_checked: "Not checked", unavailable: "Unavailable", conflicting: "Conflicting evidence" }[original.status] || "Unavailable");
  const originalFacts = `<dl class="manual-credit-retrieved-facts"><div><dt>${esc(t("Credit rating"))}</dt><dd><bdi dir="ltr">${esc(originalStatus)}</bdi>${original.stale ? ` <span class="badge warn">${esc(t("Stale evidence"))}</span>` : ""}</dd></div><div><dt>${esc(t("Outlook"))}</dt><dd>${creditRatingsSignal(original, "outlook")}</dd></div><div><dt>${esc(t("Watch"))}</dt><dd>${creditRatingsSignal(original, "watch")}</dd></div></dl>`;
  return `<details class="credit-rating-evidence" data-credit-disclosure="${esc(agency)}:manual"><summary>${esc(t("Manual entry details"))}</summary><p>${esc(t("User-entered information; the app has not independently verified this rating."))}</p><dl>${facts.map(([label, value]) => `<div><dt>${esc(t(label))}</dt><dd><bdi dir="auto">${esc(value)}</bdi></dd></div>`).join("")}</dl>${record.notes ? `<p class="manual-credit-notes">${esc(t("Notes"))}: ${esc(record.notes)}</p>` : ""}${sourceUrl ? `<p><a href="${esc(sourceUrl)}" target="_blank" rel="noopener noreferrer">${esc(t("User-provided source"))}</a> · ${esc(t("Saved without source verification"))}</p>` : ""}</details><details class="credit-rating-evidence manual-credit-retrieved" data-credit-disclosure="${esc(agency)}:automatic"><summary>${esc(t("Retrieved agency evidence"))}</summary><p>${esc(creditRatingsReason(original.reason_code, original.status) || t("Retrieved evidence is separate from this manual entry."))}</p>${originalFacts}${creditRatingsEvidence(original, agency)}</details>`;
}

function setManualCreditOptions(id, options) {
  const select = $(id), html = options.map(([value, label]) => `<option value="${esc(value)}"${id === "manualCreditGrade" && value ? ' dir="ltr"' : ""}>${esc(label)}</option>`).join("");
  if (select.innerHTML !== html) select.innerHTML = html;
}

function renderManualCreditEditor() {
  const panel = $("manualCreditEditor");
  if (!panel) return;
  const entry = creditRatingsEntry(), editor = entry?.manual;
  document.querySelectorAll("[data-edit-manual-credit]").forEach((button) => {
    button.disabled = !canWrite() || !entry?.context?.identity_token || !entry.context.manual_policy || Boolean(editor?.saving || editor?.reloading);
  });
  panel.hidden = !editor || !canWrite() || $("securityCreditRatings")?.hidden;
  if (panel.hidden) return;
  if (entry.context?.identity_token && editor.expectedIdentity !== entry.context.identity_token) {
    editor.identityChanged = true;
    editor.message = "The security identity changed. Close this editor and start a new entry for the current identity.";
  }
  const policy = entry.context?.manual_policy || {}, value = editor.values, busy = editor.saving || editor.reloading;
  const verified = Boolean(policy.issuer_identity_verified && policy.canonical_issuer_name);
  $("manualCreditEditorTitle").textContent = `${t("Manual rating")} · ${manualCreditAgencyName(editor.agency)}`;
  $("manualCreditSecurity").textContent = [entry.identity.symbol, entry.identity.stock_market, entry.identity.currency].join(" · ");
  setManualCreditOptions("manualCreditStatus", [["rated", t("Rated")], ["unrated", t("Unrated")], ["withdrawn", t("Withdrawn")]]);
  setManualCreditOptions("manualCreditGrade", [["", t("Select rating")], ...MANUAL_CREDIT_GRADES[editor.agency].map((grade) => [grade, grade])]);
  setManualCreditOptions("manualCreditOutlook", ["unknown", "positive", "negative", "stable", "developing"].map((kind) => [kind, creditRatingsDirection(kind)]));
  setManualCreditOptions("manualCreditWatch", ["unknown", "positive", "negative", "developing", "none"].map((kind) => [kind, creditRatingsDirection(kind, true)]));
  setManualCreditOptions("manualCreditScope", editor.isBond
    ? [...(policy.issue_rating_allowed ? [["", t("Select rating scope")]] : []), ["issuer", t("Issuer fallback")], ...(policy.issue_rating_allowed ? [["issue", t("Exact debt issue")]] : [])]
    : [["issuer", t("Issuer rating")]]);
  for (const [id, field] of [["manualCreditStatus", "status"], ["manualCreditGrade", "rating"], ["manualCreditOutlook", "outlook"], ["manualCreditWatch", "watch"], ["manualCreditScope", "scope"],
    ["manualCreditEntity", "entity_name"], ["manualCreditSource", "source_url"], ["manualCreditNotes", "notes"], ["manualCreditRatingDate", "rating_date"], ["manualCreditOutlookDate", "outlook_date"], ["manualCreditWatchDate", "watch_date"]]) {
    const input = $(id);
    if (input.value !== value[field] && document.activeElement !== input) input.value = value[field];
    input.disabled = busy || editor.identityChanged || (field === "rating" || field === "outlook" || field === "watch") && value.status !== "rated"
      || field === "outlook_date" && (value.status !== "rated" || value.outlook === "unknown") || field === "watch_date" && (value.status !== "rated" || value.watch === "unknown");
    input.setAttribute("aria-invalid", String(editor.invalidField === id));
  }
  $("manualCreditEntity").readOnly = verified;
  $("manualCreditEntityHint").textContent = t(verified ? "Verified issuer identity" : "Enter the legal issuer name. This identity will be marked Manual identity.");
  $("manualCreditScopeHint").textContent = t(editor.isBond && !policy.issue_rating_allowed ? "Exact issue entry requires a known ISIN or CUSIP." : "Global scale, long term. Other rating categories are not supported in this editor.");
  $("manualCreditActiveFields").hidden = value.status !== "rated";
  $("manualCreditOutlookDateField").hidden = value.status !== "rated" || value.outlook === "unknown";
  $("manualCreditWatchDateField").hidden = value.status !== "rated" || value.watch === "unknown";
  $("saveManualCreditRating").disabled = busy || editor.needsReload || editor.identityChanged;
  $("saveManualCreditRating").textContent = t(editor.saving ? "Saving…" : "Save manual rating");
  $("clearManualCreditRating").hidden = !manualCreditRecord(entry.context, editor.agency);
  $("clearManualCreditRating").disabled = busy || editor.needsReload || editor.identityChanged;
  $("reloadManualCreditRating").hidden = !editor.needsReload;
  $("reloadManualCreditRating").disabled = busy;
  $("cancelManualCreditRating").disabled = editor.saving;
  $("manualCreditEditorStatus").textContent = editor.message ? t(editor.message) : "";
  panel.setAttribute("aria-busy", String(busy));
}

function openManualCreditRating(agency) {
  const entry = creditRatingsEntry();
  if (!canWrite() || !MANUAL_CREDIT_GRADES[agency] || !entry?.context?.identity_token || !entry.context.manual_policy || entry.manual?.saving || entry.manual?.reloading) return;
  entry.manualDrafts ||= {};
  if (entry.manual) entry.manualDrafts[entry.manual.agency] = entry.manual;
  entry.manual = entry.manualDrafts[agency] || manualCreditDraft(entry, agency);
  entry.manualDrafts[agency] = entry.manual;
  if (entry.manual.expectedIdentity !== entry.context.identity_token) {
    entry.manual.identityChanged = true;
    entry.manual.message = "The security identity changed. Close this editor and start a new entry for the current identity.";
  }
  renderManualCreditEditor();
  $("manualCreditEditor").scrollIntoView?.({ block: "nearest", behavior: "auto" });
  $("manualCreditStatus").focus({ preventScroll: true });
}

function updateManualCreditDraft(target, normalizeDate = false) {
  const entry = creditRatingsEntry(), editor = entry?.manual;
  if (!editor || editor.saving || !canWrite()) return;
  const fields = { manualCreditStatus: "status", manualCreditGrade: "rating", manualCreditOutlook: "outlook", manualCreditWatch: "watch", manualCreditScope: "scope",
    manualCreditEntity: "entity_name", manualCreditSource: "source_url", manualCreditNotes: "notes", manualCreditRatingDate: "rating_date", manualCreditOutlookDate: "outlook_date", manualCreditWatchDate: "watch_date" };
  const field = fields[target.id];
  if (!field) return;
  editor.values[field] = target.value;
  if (normalizeDate && field.endsWith("_date") && parseDateInput(target.value)) target.value = editor.values[field] = formatDate(parseDateInput(target.value));
  if (field === "status" && target.value !== "rated") Object.assign(editor.values, { rating: "", outlook: "unknown", watch: "unknown", outlook_date: "", watch_date: "" });
  if (field === "outlook" && target.value === "unknown") editor.values.outlook_date = "";
  if (field === "watch" && target.value === "unknown") editor.values.watch_date = "";
  if (!editor.needsReload && !editor.identityChanged) editor.message = "";
  editor.invalidField = "";
  renderManualCreditEditor();
}

function manualCreditValidation(editor) {
  const value = editor.values;
  if (!value.entity_name.trim()) return ["Enter the legal issuer name.", "manualCreditEntity"];
  if (!["issuer", "issue"].includes(value.scope)) return ["Select rating scope.", "manualCreditScope"];
  if (value.scope === "issue" && !editor.issueAllowed) return ["Select a supported rating scope for this security.", "manualCreditScope"];
  if (value.status === "rated" && !MANUAL_CREDIT_GRADES[editor.agency].includes(value.rating)) return ["Choose a rating from this agency’s list.", "manualCreditGrade"];
  if (value.status !== "rated" && (value.rating || value.outlook !== "unknown" || value.watch !== "unknown" || value.outlook_date || value.watch_date)) return ["Unrated and Withdrawn entries must have no grade, outlook, watch or signal dates.", "manualCreditStatus"];
  if (value.outlook === "unknown" && value.outlook_date) return ["An outlook action date requires a known outlook.", "manualCreditOutlook"];
  if (value.watch === "unknown" && value.watch_date) return ["A watch action date requires a known watch.", "manualCreditWatch"];
  if (!value.source_url.trim() && !value.notes.trim()) return ["Enter a source URL or a short note.", "manualCreditSource"];
  if (value.source_url.trim()) {
    let valid = false;
    try {
      const url = new URL(value.source_url.trim());
      valid = url.protocol === "https:" && !url.username && !url.password && ![...url.searchParams.keys()].some((key) => /token|password|secret|api[_-]?key|authorization/i.test(key));
    } catch { /* The server also validates public source hosts. */ }
    if (!valid) return ["Enter a public HTTPS source URL without credentials, or use notes.", "manualCreditSource"];
  }
  for (const [field, id] of [["rating_date", "manualCreditRatingDate"], ["outlook_date", "manualCreditOutlookDate"], ["watch_date", "manualCreditWatchDate"]]) {
    if (!value[field].trim()) continue;
    const date = parseDateInput(value[field]);
    if (!date || date > todayString()) return ["Enter a valid action date as dd/mm/yyyy, no later than today.", id];
  }
  return null;
}

function manualCreditError(error) {
  const code = error?.code || error?.message;
  const errors = { manual_rating_conflict: "This manual entry changed. Reload saved ratings and review your draft before saving again.",
    security_identity_changed: "The security identity changed. Reload saved ratings before continuing.",
    manual_invalid_rating: "Choose a rating from this agency’s list.", manual_invalid_grade: "Choose a rating from this agency’s list.",
    manual_invalid_date: "Enter a valid action date as dd/mm/yyyy, no later than today.", manual_invalid_source: "Enter a source URL or a short note.", manual_source_required: "Enter a source URL or a short note.",
    manual_invalid_entity: "Enter the legal issuer name matching this security.", manual_invalid_scope: "Select a supported rating scope for this security." };
  if (error?.status === 403) return "Manual rating updates require Admin or Operator permission.";
  if (error?.status === 401) return "Sign in again before saving a manual rating.";
  if (String(code || "").startsWith("manual_invalid_") && String(code).includes("source")) return "Enter a public HTTPS source URL without credentials, or use notes.";
  if (String(code || "").startsWith("manual_invalid_") && String(code).endsWith("date")) return "Enter a valid action date as dd/mm/yyyy, no later than today.";
  return errors[code] || (error?.status === 422 ? "The manual entry is invalid. Review its grade, identity, source and action dates." : "The manual update could not be confirmed. Reload saved ratings before retrying.");
}

async function persistManualCreditRating(clear = false) {
  const entry = creditRatingsEntry(), editor = entry?.manual;
  if (!canWrite() || !editor || editor.saving || editor.reloading || editor.needsReload || editor.identityChanged) return;
  const validation = clear ? null : manualCreditValidation(editor);
  if (validation) {
    editor.message = validation[0]; editor.invalidField = validation[1]; renderManualCreditEditor();
    const input = $(validation[1]), details = input.closest?.("details");
    if (details) details.open = true;
    input.focus(); return;
  }
  const value = editor.values;
  const payload = { security_key: entry.context.security_key, agency: editor.agency, expected_identity: editor.expectedIdentity, expected_revision: editor.expectedRevision,
    status: value.status, rating: value.status === "rated" ? value.rating : null, outlook: value.status === "rated" ? value.outlook : "unknown", watch: value.status === "rated" ? value.watch : "unknown",
    scope: value.scope, entity_name: value.entity_name.trim(), source_url: value.source_url.trim() || null, notes: value.notes.trim(),
    rating_date: parseDateInput(value.rating_date) || null, outlook_date: value.status === "rated" && value.outlook !== "unknown" ? parseDateInput(value.outlook_date) || null : null,
    watch_date: value.status === "rated" && value.watch !== "unknown" ? parseDateInput(value.watch_date) || null : null };
  editor.saving = true; editor.message = ""; entry.version += 1; entry.loading = false;
  renderManualCreditEditor();
  try {
    const params = new URLSearchParams({ security_key: payload.security_key, agency: payload.agency, expected_identity: payload.expected_identity, expected_revision: String(payload.expected_revision) });
    const context = await creditRatingsRequest(clear ? `/api/securities/credit-ratings/manual?${params}` : "/api/securities/credit-ratings/manual",
      clear ? { method: "DELETE" } : { method: "PUT", body: JSON.stringify(payload) });
    if (!creditRatingsEntryActive(entry) || entry.manual !== editor) return;
    if (context.security_key !== entry.context.security_key || !context.identity_token) throw new Error("invalid_manual_response");
    entry.version += 1; entry.readRevision = (entry.readRevision || 0) + 1; entry.context = context; entry.loading = false;
    if (typeof updateHoldingsCreditRatingsFromOverview === "function") updateHoldingsCreditRatingsFromOverview(context);
    if (clear) { delete entry.manualDrafts?.[editor.agency]; entry.manual = null; entry.message = "Manual override cleared. Retrieved agency evidence is shown."; }
    else {
      entry.manual = manualCreditDraft(entry, editor.agency, editor.isBond);
      entry.manualDrafts ||= {};
      entry.manualDrafts[editor.agency] = entry.manual;
      entry.manual.message = "Manual rating saved. Retrieved agency evidence remains available.";
    }
    renderSecurityCreditRatings();
    if (clear) document.querySelector?.(`[data-edit-manual-credit="${editor.agency}"]`)?.focus({ preventScroll: true });
  } catch (error) {
    if (!creditRatingsEntryActive(entry) || entry.manual !== editor) return;
    editor.message = manualCreditError(error);
    editor.needsReload = error?.status === 409 || !Number.isFinite(error?.status) || error.status >= 500;
  } finally {
    if (creditRatingsEntryActive(entry)) {
      editor.saving = false;
      renderManualCreditEditor();
      if (entry.reloadAfterManual) { entry.reloadAfterManual = false; loadSecurityCreditRatings(entry, { force: true }); }
    }
  }
}

async function reloadManualCreditRating() {
  const entry = creditRatingsEntry(), editor = entry?.manual;
  if (!editor || editor.saving || editor.reloading) return;
  const before = entry.readRevision || 0;
  editor.reloading = true;
  renderManualCreditEditor();
  await loadSecurityCreditRatings(entry, { force: true });
  editor.reloading = false;
  if (!creditRatingsEntryActive(entry) || entry.manual !== editor) return;
  if ((entry.readRevision || 0) === before) editor.message = "Saved ratings could not be reloaded. Your manual draft is retained.";
  else if (entry.context.identity_token !== editor.expectedIdentity) {
    editor.identityChanged = true;
    editor.message = "The security identity changed. Close this editor and start a new entry for the current identity.";
  } else {
    editor.expectedRevision = Number(entry.context.manual_revisions?.[editor.agency] || 0);
    editor.needsReload = false;
    editor.message = "Saved records reloaded. Review your draft before saving again.";
  }
  renderManualCreditEditor();
}

document.addEventListener("input", (event) => { if (event.target.closest?.("#manualCreditEditor")) updateManualCreditDraft(event.target); });
document.addEventListener("change", (event) => { if (event.target.closest?.("#manualCreditEditor")) updateManualCreditDraft(event.target, true); });
document.addEventListener("submit", (event) => { if (event.target.id === "manualCreditForm") { event.preventDefault(); persistManualCreditRating(); } });
document.addEventListener("click", (event) => {
  const agency = event.target.closest?.("[data-edit-manual-credit]")?.dataset.editManualCredit;
  if (agency) openManualCreditRating(agency);
  if (event.target.closest?.("#clearManualCreditRating")) persistManualCreditRating(true);
  if (event.target.closest?.("#reloadManualCreditRating")) reloadManualCreditRating();
  if (event.target.closest?.("#cancelManualCreditRating")) {
    const entry = creditRatingsEntry(), agency = entry?.manual?.agency;
    if (entry?.manual && !entry.manual.saving) { delete entry.manualDrafts?.[agency]; entry.manual = null; renderManualCreditEditor(); document.querySelector?.(`[data-edit-manual-credit="${agency}"]`)?.focus({ preventScroll: true }); }
  }
});
