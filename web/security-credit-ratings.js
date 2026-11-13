/* Agency evidence stays separate from portfolio risk and valuation calculations. */
function creditRatingsSession() {
  const owner = currentUser()?.id, token = state.auth?.csrfToken;
  if (!state.creditRatings || state.creditRatings.owner !== owner || state.creditRatings.token !== token) {
    if (state.creditRatings) Object.values(state.creditRatings.entries).forEach((entry) => clearTimeout(entry.timer));
    state.creditRatings = { owner, token, entries: {} };
  }
  return state.creditRatings;
}

function creditRatingsEntry(detail = state.securityDetail) {
  if (!detail?.symbol) return null;
  const session = creditRatingsSession();
  const identity = { symbol: detail.symbol, stock_market: detail.item?.holding?.stock_market || detail.market_key || detail.stock_market || "MANUAL", currency: detail.currency || "" };
  const key = [identity.symbol, identity.stock_market, identity.currency].map((value) => String(value).trim().toUpperCase()).join("|");
  if (!session.entries[key]) session.entries[key] = { key, identity, context: null, loading: false, pending: false, starting: false,
    resume: false, job: null, message: "", polls: 0, version: 0, timer: null };
  return session.entries[key];
}

function creditRatingsEligible(security = {}) {
  const asset = String(security.asset_class || "").toUpperCase();
  const kinds = [security.asset_sub_class, security.instrument_type].map((value) => String(value || "").toUpperCase());
  return Boolean(security.symbol) && ["EQUITY", "FIXED_INCOME", "STOCK", "BOND", "RSU"].includes(asset)
    && !kinds.some((kind) => ["OPTION", "FUTURE", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION", "ETF", "FUND", "MUTUALFUND", "MUTUAL_FUND"].includes(kind))
    && String(security.stock_market || security.market_key || "").toUpperCase() !== "PRIVATE";
}

function creditRatingsEntryActive(entry) {
  const session = state.creditRatings;
  return Boolean(session && currentUser()?.id === session.owner && state.auth?.csrfToken === session.token && session.entries[entry.key] === entry);
}

function creditRatingsIsManual(record) {
  return record?.manual_override === true || record?.source_kind === "manual";
}

function creditRatingsReason(code, status) {
  return t({
    not_checked: "This agency has not been checked yet.",
    not_found: "No matching public rating was found. This does not establish that the issuer is unrated.",
    rating_not_found: "No matching public rating was found. This does not establish that the issuer is unrated.",
    explicitly_unrated: "The source explicitly identifies this entity as unrated.",
    withdrawn: "The agency has withdrawn this rating.",
    conflicting: "Sources conflict. Review the evidence before using this rating.",
    conflicting_evidence: "Sources conflict. Review the evidence before using this rating.",
    primary_rating_unavailable: "No supported long-term issuer or issue rating was verified. Other rating categories remain in the sources.",
    evidence_rejected: "The available source did not verify the agency, entity, rating and date together.",
    stale: "Saved evidence is old. Refresh ratings to check for newer agency information.",
    stale_evidence: "Saved evidence is old. Refresh ratings to check for newer agency information.",
    api_not_configured: "Refresh ratings researches public sources with AI. No licensed rating API is required.",
    configuration_required: "Refresh ratings researches public sources with AI. No licensed rating API is required.",
    entitlement_required: "Refresh ratings researches public sources with AI. No licensed rating API is required.",
    access_denied: "Refresh ratings researches public sources with AI. No licensed rating API is required.",
    rate_limited: "The provider rate limit was reached. Try again later.",
    source_read_failed: "A source page could not be read. Refresh ratings to try again.",
    research_unavailable: "Internet research is unavailable. Configure the search service and try again.",
    search_not_configured: "The selected search service requires configuration. Choose automatic search or configure its key.",
    bridge_unavailable: "The AI connection is unavailable. An administrator can restore the host bridge, then retry.",
    authentication_expired: "Sign in again before continuing AI research.",
    research_incomplete: "The research limit was reached before all agency information could be verified.",
    unsupported_instrument: "Company credit ratings are available for supported company shares and bonds.",
    unsupported_security: "Company credit ratings are available for supported company shares and bonds.",
  }[code] || {
    not_checked: "This agency has not been checked yet.",
    not_found: "No matching public rating was found. This does not establish that the issuer is unrated.",
    unrated: "The source explicitly identifies this entity as unrated.",
    withdrawn: "The agency has withdrawn this rating.",
    conflicting: "Sources conflict. Review the evidence before using this rating.",
    unavailable: "The agency rating could not be verified. Saved evidence is retained.",
  }[status] || "");
}

function creditRatingsDate(value) {
  const date = String(value || "").match(/^\d{4}-\d{2}-\d{2}/)?.[0];
  return date ? formatDate(date) : t("Unknown");
}

function creditRatingsDirection(value, watch = false) {
  return t({ positive: "Positive", negative: "Negative", stable: "Stable", developing: "Developing",
    none: watch ? "No watch" : "Unknown", unknown: "Unknown" }[value] || "Unknown");
}

function creditRatingsSourceUrl(value) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : "";
  } catch { return ""; }
}

function creditRatingsCategory(record) {
  return t({ sovereign: "Sovereign credit rating", sovereign_rating: "Sovereign credit rating", sovereign_issuer: "Sovereign credit rating", issuer: "Issuer credit rating", issuer_default: "Issuer default rating", issuer_rating: "Issuer rating", issuer_credit_rating: "Issuer credit rating", issuer_default_rating: "Issuer default rating",
    long_term_issuer_credit_rating: "Issuer credit rating", long_term_issuer_default_rating: "Issuer default rating",
    corporate_family: "Corporate family rating", deposit: "Deposit rating", issue: "Issue rating",
    senior_unsecured: "Senior unsecured debt", senior_unsecured_class: "Senior unsecured debt", senior_secured: "Senior secured debt",
    subordinated: "Subordinated debt", subordinated_class: "Subordinated debt", junior_subordinated_class: "Junior subordinated debt",
    preferred_stock_class: "Preferred stock rating", viability: "Viability / baseline credit assessment",
    "Issuer Rating": "Issuer rating", "Issuer Credit Rating": "Issuer credit rating", "Issuer Default Rating": "Issuer default rating",
    "Senior Unsecured": "Senior unsecured debt", "Senior Secured": "Senior secured debt" }[record.rating_type] || "Agency rating category");
}

function creditRatingsOtherCategories(record) {
  const observations = (Array.isArray(record.observations) ? record.observations : [])
    .filter((item) => item?.agency === record.agency && item.primary_eligible === false);
  if (!observations.length) return "";
  return `<div class="credit-rating-other"><strong>${esc(t("Other rating categories"))}</strong><ul>${observations.map((item) => {
    const scope = t({ issuer: "Issuer-level category", issue: "Specific debt issue" }[item.scope] || "Unknown");
    const scale = t({ global: "Global scale", national: "National scale" }[item.scale] || "Unknown");
    const term = t({ long_term: "Long term", short_term: "Short term" }[item.term] || "Unknown");
    const sources = [...(Array.isArray(item.sources) ? item.sources : []), ...(item.source_url ? [{ url: item.source_url }] : [])];
    const urls = [...new Set(sources.map((source) => creditRatingsSourceUrl(source.url)).filter(Boolean))];
    const dates = [["Rating date", creditRatingsDate(item.rating_date)], ["Source observation date", creditRatingsDate(item.observed_at)],
      ["Retrieved", creditRatingsDate(item.fetched_at)]];
    if (item.checked_at) dates.push(["Last checked", creditRatingsDate(item.checked_at)]);
    if (item.outlook_fetched_at || item.outlook && item.outlook !== "unknown") dates.push(["Outlook last verified", creditRatingsDate(item.outlook_fetched_at)]);
    if (item.watch_fetched_at || item.watch && item.watch !== "unknown") dates.push(["Watch last verified", creditRatingsDate(item.watch_fetched_at)]);
    if (item.outlook_date) dates.push(["Outlook date", creditRatingsDate(item.outlook_date)]);
    if (item.watch_date) dates.push(["Watch date", creditRatingsDate(item.watch_date)]);
    const sourceContext = item.action_type ? { periodic_review: "Periodic review", rating_action: "Rating action", rating_observation: "Rating observation" }[item.action_type] || "Other source record"
      : item.snapshot_kind ? { issuer_rating_table: "Published rating table" }[item.snapshot_kind] || "Other source record" : "";
    return `<li><div><bdi dir="ltr">${esc(item.rating || "—")}</bdi> · ${esc(creditRatingsCategory(item))}</div>
      <p>${esc(t("Rated entity"))}: <bdi dir="auto">${esc(item.entity_name || t("Unknown"))}</bdi></p>
      <p>${esc(t("Rating scope"))}: ${esc(scope)} · ${esc(t("Rating scale"))}: ${esc(scale)} · ${esc(t("Rating term"))}: ${esc(term)}</p>
      <dl class="credit-rating-other-signals"><div><dt>${esc(t("Outlook"))}</dt><dd>${creditRatingsSignal(item, "outlook")}</dd></div><div><dt>${esc(t("Watch"))}</dt><dd>${creditRatingsSignal(item, "watch")}</dd></div></dl>
      ${sourceContext ? `<p>${esc(t("Source record type"))}: ${esc(t(sourceContext))}</p>` : ""}
      <dl>${dates.map(([label, value]) => `<div><dt>${esc(t(label))}</dt><dd><bdi dir="auto">${esc(value)}</bdi></dd></div>`).join("")}</dl>
      ${urls.length ? `<div class="credit-rating-sources">${urls.map((url, index) => `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(t("Source {number}").replace("{number}", String(index + 1)))}</a>`).join("")}</div>` : ""}</li>`;
  }).join("")}</ul></div>`;
}

function creditRatingsEvidence(record, agency) {
  const scope = { issuer: "Issuer rating", issue: "Issue rating", sovereign: "Sovereign credit rating" }[record.scope] || "Unknown";
  const scale = { global: "Global scale", national: "National scale" }[record.scale] || "Unknown";
  const term = { long_term: "Long term", short_term: "Short term" }[record.term] || "Unknown";
  const details = [["Rated entity", record.entity_name || t("Unknown")], ["Rating scope", t(scope)], ["Rating scale", t(scale)],
    ["Rating term", t(term)], ["Rating date", creditRatingsDate(record.rating_date)],
    ["Source observation date", creditRatingsDate(record.observed_at)], ["Retrieved", creditRatingsDate(record.fetched_at)]];
  if (record.entity_id) details.splice(1, 0, ["Entity identifier", record.entity_id]);
  if (record.rating_type) details.splice(4, 0, ["Rating category", creditRatingsCategory(record)]);
  if (record.currency_basis) details.push(["Rating currency basis", t({ local_currency: "Local currency", foreign_currency: "Foreign currency",
    local: "Local currency", foreign: "Foreign currency" }[record.currency_basis] || "Unknown")]);
  if (record.checked_at) details.push(["Last checked", creditRatingsDate(record.checked_at)]);
  if (record.outlook_fetched_at) details.push(["Outlook last verified", creditRatingsDate(record.outlook_fetched_at)]);
  if (record.watch_fetched_at) details.push(["Watch last verified", creditRatingsDate(record.watch_fetched_at)]);
  if (record.outlook_date) details.push(["Outlook date", creditRatingsDate(record.outlook_date)]);
  if (record.watch_date) details.push(["Watch date", creditRatingsDate(record.watch_date)]);
  const hasAlternateEvidence = record.status === "conflicting" || record.reason_code === "primary_rating_unavailable";
  const evidenceRecords = [record, ...(hasAlternateEvidence && Array.isArray(record.observations)
    ? record.observations.filter((item) => item.agency === record.agency && (record.status === "conflicting" || item.primary_eligible === false)) : [])];
  const sources = evidenceRecords.flatMap((item) => [...(Array.isArray(item.sources) ? item.sources : []),
    ...(item.source_url ? [{ url: item.source_url }] : [])]);
  const seen = new Set();
  const links = sources.flatMap((source) => {
    const url = creditRatingsSourceUrl(source.url);
    if (!url || seen.has(url)) return [];
    seen.add(url);
    const fields = (Array.isArray(source.fields) ? source.fields : []).map((field) => ({ rating: "Credit rating", outlook: "Outlook", watch: "Watch", rating_date: "Rating date" })[field]).filter(Boolean);
    const label = t("Source {number}").replace("{number}", String(seen.size));
    return [`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(`${agency}: ${label}`)}">${esc(label)}</a>${fields.length ? ` <span>(${fields.map((field) => esc(t(field))).join(", ")})</span>` : ""}`];
  });
  return `<details class="credit-rating-evidence" data-credit-disclosure="${esc(agency)}:evidence"><summary>${esc(t("Details and sources"))}</summary><dl>${details.map(([label, value]) => `<div><dt>${esc(t(label))}</dt><dd><bdi dir="auto">${esc(value)}</bdi></dd></div>`).join("")}</dl>${links.length ? `<div class="credit-rating-sources">${links.map((link) => `<span>${link}</span>`).join("")}</div>` : `<p>${esc(t("No verified source saved."))}</p>`}${creditRatingsOtherCategories(record)}</details>`;
}

function creditRatingsSignal(record, field) {
  const value = creditRatingsDirection(record[field], field === "watch");
  const stale = !creditRatingsIsManual(record) && record[`${field}_stale`] === true;
  const label = field === "watch" ? "Stale watch" : "Stale outlook";
  const dateLabel = field === "watch" ? "Watch last verified" : "Outlook last verified";
  return `<div class="credit-rating-signal"><span>${esc(value)}</span>${stale ? `<span class="badge warn" title="${esc(`${t(dateLabel)}: ${creditRatingsDate(record[`${field}_fetched_at`])}`)}">${esc(t(label))}</span>` : ""}</div>`;
}

function creditRatingsRows(context, options = {}) {
  const agencies = [["moodys", "Moody’s"], ["sp", "S&P Global Ratings"], ["fitch", "Fitch"]];
  return agencies.map(([key, agency]) => {
    const record = (Array.isArray(context?.ratings) ? context.ratings : []).find((item) => item.agency === key) || { status: "not_checked", outlook: "unknown", watch: "unknown" };
    const manual = creditRatingsIsManual(record);
    const label = { rated: manual ? "Manual rating" : "Verified rating", unrated: "Unrated", withdrawn: "Withdrawn", not_found: "Not found", not_checked: "Not checked",
      unavailable: "Unavailable", conflicting: "Conflicting evidence" }[record.status] || "Unavailable";
    const scope = [{ issuer: "Issuer rating", issue: "Issue rating", sovereign: "Sovereign credit rating" }[record.scope], { global: "Global scale", national: "National scale" }[record.scale],
      { long_term: "Long term", short_term: "Short term" }[record.term]].filter(Boolean).map((label) => t(label)).join(" · ");
    const reason = manual ? t("User-entered information; the app has not independently verified this rating.") : creditRatingsReason(record.reason_code, record.status);
    const original = (Array.isArray(context?.retrieved_ratings) ? context.retrieved_ratings : []).find((item) => item.agency === key);
    const evidence = manual && typeof manualCreditEvidenceHtml === "function" ? manualCreditEvidenceHtml(record, original, agency) : creditRatingsEvidence(record, agency);
    const action = options.actions ? options.actions(context, key) : typeof manualCreditActionsHtml === "function" ? manualCreditActionsHtml(context, key) : "";
    return `<tr><th scope="row"><bdi dir="ltr">${esc(agency)}</bdi></th>
      <td data-label="${esc(t("Credit rating"))}"><div class="credit-rating-value"><bdi class="credit-rating-symbol" dir="ltr">${esc(record.rating || "—")}</bdi><span class="badge neutral">${esc(t(label))}</span>${manual && record.status !== "rated" ? `<span class="badge credit-manual-badge">${esc(t("Manual"))}</span>` : ""}${record.stale ? `<span class="badge warn">${esc(t(manual ? "Old manual entry" : "Stale evidence"))}</span>` : ""}${manual && record.identity_verification === "user_entered" ? `<span class="badge credit-manual-badge">${esc(t("Manual identity"))}</span>` : ""}</div>${scope ? `<span class="credit-rating-scope">${esc(scope)}</span>` : ""}${reason ? `<p class="credit-rating-reason">${esc(reason)}</p>` : ""}</td>
      <td data-label="${esc(t("Outlook"))}">${creditRatingsSignal(record, "outlook")}</td>
      <td data-label="${esc(t("Watch"))}">${creditRatingsSignal(record, "watch")}</td>
      <td data-label="${esc(t("Evidence"))}">${evidence}${action}</td></tr>`;
  }).join("");
}

function creditRatingsProviderStatus(providers) {
  // Retained cached provider metadata does not make a licensed feed a prerequisite.
  return "";
}

function creditRatingsAvailability(context, editable = canWrite()) {
  if (!context) return "";
  const rows = Array.isArray(context.retrieved_ratings) ? context.retrieved_ratings : Array.isArray(context.ratings) ? context.ratings : [];
  const unchecked = rows.length && rows.every((row) => row.status === "not_checked");
  const incomplete = rows.some((row) => ["not_checked", "unavailable", "not_found", "conflicting"].includes(row.status));
  const messages = [];
  if (unchecked) messages.push(t("No retrieved rating checks are saved. Unknown does not mean Unrated."));
  else if (incomplete) messages.push(t("Some agency information has not been verified. Unknown does not establish that the issuer is unrated."));
  if (unchecked || incomplete) messages.push(t(editable
    ? "Choose Refresh ratings to research public sources, or Add manually to record your own information."
    : "An Admin or Operator can research ratings or add a manual entry."));
  messages.push(t("Ratings use public-source AI research. An available AI connection and Internet search are required; no licensed rating API is required."));
  return messages.join(" ");
}

function renderSecurityCreditRatings() {
  const panel = $("securityCreditRatings"), detail = state.securityDetail;
  if (!panel || !detail) return;
  const supported = creditRatingsEligible({ ...detail, asset_class: detail.asset_class || "EQUITY" });
  panel.hidden = !supported;
  if (!supported) return;
  const entry = creditRatingsEntry(detail), context = entry.context;
  const busy = entry.pending || entry.starting;
  panel.setAttribute("aria-busy", String(entry.loading || busy));
  $("securityCreditRatingsIssuer").textContent = context?.issuer_name ? `${t("Issuer")}: ${context.issuer_name}` : "";
  $("securityCreditRatingsIssuer").hidden = !context?.issuer_name;
  const availability = $("securityCreditRatingsAvailability");
  if (availability) {
    availability.textContent = creditRatingsAvailability(context);
    availability.hidden = !availability.textContent;
  }
  const content = $("securityCreditRatingsRows"), html = creditRatingsRows(context);
  if (content.innerHTML !== html) {
    const openDisclosures = new Set([...content.querySelectorAll("details[open]")].map((node) => node.dataset.creditDisclosure));
    const focusedSummary = [...content.querySelectorAll("summary")].indexOf(document.activeElement);
    content.innerHTML = html;
    content.querySelectorAll("details").forEach((node) => { if (openDisclosures.has(node.dataset.creditDisclosure)) node.open = true; });
    if (focusedSummary >= 0) content.querySelectorAll("summary")[focusedSummary]?.focus({ preventScroll: true });
  }
  const providerHtml = creditRatingsProviderStatus(context?.provider_status);
  const providers = $("securityCreditRatingsProviders");
  providers.hidden = true;
  if (providers.innerHTML !== providerHtml) {
    const wasOpen = providers.querySelector("details")?.open;
    providers.innerHTML = providerHtml;
    if (wasOpen && providers.querySelector("details")) providers.querySelector("details").open = true;
  }
  const refresh = $("refreshSecurityCreditRatings");
  refresh.disabled = !canWrite() || entry.loading || busy || entry.resume || !context?.security_key;
  refresh.textContent = t("Refresh ratings");
  refresh.title = !canWrite() ? t("Rating updates require Admin or Operator permission.") : t("Research Moody’s, S&P Global Ratings and Fitch from public sources with AI.");
  const resume = $("resumeSecurityCreditRatings");
  resume.hidden = !entry.resume;
  resume.disabled = entry.loading || busy;
  resume.textContent = t("Check AI progress");
  const reload = $("reloadSecurityCreditRatings");
  reload.hidden = !entry.message || busy || entry.resume;
  reload.disabled = entry.loading;
  reload.textContent = t("Reload saved ratings");
  const phases = { queued: "Waiting to start", checking_apis: "Preparing public-source rating research", researching: "Researching agency ratings",
    saving: "Saving verified ratings", completed: "Rating check finished", failed: "Rating check stopped" };
  const phase = entry.job?.progress?.stage || (busy ? "queued" : "");
  let message = entry.loading ? t("Loading saved ratings…") : busy ? t(phases[phase] || "Research in progress")
    : entry.message ? t(entry.message) : !canWrite() ? t("Viewing saved ratings. Refresh requires Admin or Operator permission.") : "";
  const total = Number(entry.job?.progress?.total), completed = Number(entry.job?.progress?.completed);
  const knownProgress = busy && Number.isFinite(completed) && completed >= 0 && Number.isFinite(total) && total > 0;
  if (knownProgress) message += ` · ${t("Checked {completed} of {total} securities in this phase").replace("{completed}", String(completed)).replace("{total}", String(total))}`;
  const status = $("securityCreditRatingsStatus");
  if (status.textContent !== message) status.textContent = message;
  status.hidden = !message;
  $("securityCreditRatingsScope").textContent = t("Issuer ratings assess a company; issue ratings assess a specific debt obligation. Outlook and watch are agency assessments. Missing evidence stays unknown.");
  if (typeof renderManualCreditEditor === "function") renderManualCreditEditor();
  if (typeof renderCreditRatingHistory === "function") renderCreditRatingHistory(context);
}

async function creditRatingsRequest(path, options = {}) {
  const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 30000);
  try { return await api(path, { ...options, signal: controller.signal }); }
  finally { clearTimeout(timeout); }
}

async function loadSecurityCreditRatings(entry = creditRatingsEntry(), { force = false } = {}) {
  if (entry?.manual?.saving) { entry.reloadAfterManual = true; return; }
  if (!entry || !creditRatingsEntryActive(entry) || (entry.loading && !force)) return;
  const version = ++entry.version;
  entry.loading = true;
  renderSecurityCreditRatings();
  try {
    const context = await creditRatingsRequest(`/api/securities/credit-ratings?${new URLSearchParams(entry.identity)}`);
    if (!creditRatingsEntryActive(entry) || entry.version !== version) return;
    entry.context = context;
    entry.readRevision = (entry.readRevision || 0) + 1;
    if (typeof updateHoldingsCreditRatingsFromOverview === "function") updateHoldingsCreditRatingsFromOverview(context);
    if (entry.message === "Saved ratings could not be loaded. Reload saved ratings to retry.") entry.message = "";
  } catch {
    if (creditRatingsEntryActive(entry) && entry.version === version) entry.message = "Saved ratings could not be loaded. Reload saved ratings to retry.";
  } finally {
    if (creditRatingsEntryActive(entry) && entry.version === version) { entry.loading = false; renderSecurityCreditRatings(); }
  }
}

function acceptCreditRatingsJob(entry, job) {
  entry.job = job;
  entry.pending = ["queued", "running"].includes(job.status);
  entry.resume = false;
  entry.message = entry.pending ? "" : job.status === "failed" ? "Rating research could not finish. Saved evidence is retained; refresh ratings to retry."
    : "Rating check finished. Unverified agency information remains unknown.";
  renderSecurityCreditRatings();
  if (!entry.pending) loadSecurityCreditRatings(entry, { force: true });
}

function scheduleCreditRatingsPoll(entry) {
  clearTimeout(entry.timer);
  if (!entry.pending || !creditRatingsEntryActive(entry)) return;
  if (entry.polls >= 120) {
    entry.pending = false; entry.resume = true;
    entry.message = "Rating research is taking longer. Check AI progress to read the same request.";
    renderSecurityCreditRatings();
    return;
  }
  entry.timer = setTimeout(() => checkCreditRatingsProgress(entry), 3000);
}

async function checkCreditRatingsProgress(entry = creditRatingsEntry()) {
  if (!entry?.job?.request_id || !creditRatingsEntryActive(entry)) return;
  clearTimeout(entry.timer);
  entry.pending = true; entry.resume = false; entry.message = ""; entry.polls += 1;
  renderSecurityCreditRatings();
  try {
    const job = await creditRatingsRequest(`/api/securities/credit-ratings/ai/${encodeURIComponent(entry.job.request_id)}`);
    if (!creditRatingsEntryActive(entry)) return;
    acceptCreditRatingsJob(entry, job);
    scheduleCreditRatingsPoll(entry);
  } catch {
    if (!creditRatingsEntryActive(entry)) return;
    entry.pending = false; entry.resume = true;
    entry.message = "Rating progress could not be loaded. Check AI progress to retry the same request.";
    renderSecurityCreditRatings();
  }
}

async function refreshSecurityCreditRatings() {
  const entry = creditRatingsEntry();
  if (!entry || !canWrite() || entry.loading || entry.pending || entry.starting || entry.resume || !entry.context?.security_key
    || state.auth?.forcedPasswordChange || currentUser()?.must_change_password) return;
  entry.starting = true; entry.message = ""; entry.polls = 0; entry.job = null;
  renderSecurityCreditRatings();
  try {
    const job = await creditRatingsRequest("/api/securities/credit-ratings/ai", { method: "POST",
      body: JSON.stringify({ security_keys: [entry.context.security_key], position_scope: "all" }) });
    if (!creditRatingsEntryActive(entry)) return;
    acceptCreditRatingsJob(entry, job);
    scheduleCreditRatingsPoll(entry);
  } catch (error) {
    if (creditRatingsEntryActive(entry)) entry.message = error?.status === 409
      ? "A rating check is already running. Wait for it to finish, then refresh this security."
      : "The rating request could not be confirmed. Reload saved ratings, then retry if needed.";
  } finally {
    if (creditRatingsEntryActive(entry)) { entry.starting = false; renderSecurityCreditRatings(); }
  }
}

function openSecurityCreditRatings(detail) {
  const entry = creditRatingsEntry(detail);
  if (!entry) return;
  renderSecurityCreditRatings();
  if ($("securityCreditRatings").hidden) return;
  loadSecurityCreditRatings(entry);
  if (entry.pending) scheduleCreditRatingsPoll(entry);
}

document.addEventListener("click", (event) => {
  if (event.target.closest("#refreshSecurityCreditRatings")) refreshSecurityCreditRatings();
  if (event.target.closest("#reloadSecurityCreditRatings")) loadSecurityCreditRatings();
  if (event.target.closest("#resumeSecurityCreditRatings")) {
    const entry = creditRatingsEntry();
    if (entry && !entry.pending) { entry.polls = 0; checkCreditRatingsProgress(entry); }
  }
});
