/* Read cached company ratings without joining the valuation or risk models. */
function holdingsCreditRatingsSession() {
  const owner = currentUser()?.id, token = state.auth?.csrfToken;
  if (!state.holdingsCreditRatings || state.holdingsCreditRatings.owner !== owner || state.holdingsCreditRatings.token !== token) {
    state.holdingsCreditRatings?.controllers.forEach((controller) => controller.abort());
    state.holdingsCreditRatings = { owner, token, entries: {}, requested: new Set(), controllers: new Set(), portfolioVersion: null, generation: 0 };
  }
  return state.holdingsCreditRatings;
}

function holdingsCreditRatingsActive(cache) {
  return state.holdingsCreditRatings === cache && currentUser()?.id === cache.owner && state.auth?.csrfToken === cache.token;
}

function holdingsCreditRatingsKey(holding = {}) {
  return [holding.symbol, holding.stock_market || holdingMarketKey(holding), holding.currency]
    .map((value) => String(value || "").trim().toUpperCase()).join("|");
}

function holdingsCreditRatingsIdentityValid(holding = {}) {
  return [holding.symbol, holding.stock_market, holding.currency].every((value) => String(value || "").trim());
}

function holdingsCreditRatingsEntry(key) {
  const cache = holdingsCreditRatingsSession();
  if (!cache.entries[key]) cache.entries[key] = { context: null, state: "idle", revision: 0 };
  return cache.entries[key];
}

function holdingsCreditRatingStatus(record = {}) {
  if (record.status === "rated") return record.rating || t("Unknown");
  return t({ unrated: "Unrated", withdrawn: "Withdrawn", not_found: "Not found", not_checked: "Not checked",
    unavailable: "Unavailable", conflicting: "Conflicting evidence" }[record.status] || "Not checked");
}

function holdingsCreditRatingDescriptionValue(record = {}) {
  const value = holdingsCreditRatingStatus(record);
  // Keep native symbols such as AA-, BBB+ and Aa2 intact inside RTL prose.
  return record.status === "rated" && record.rating ? `\u2066${value}\u2069` : value;
}

function holdingsCreditRatingEntity(value) {
  const forms={corp:"corporation",inc:"incorporated",ltd:"limited"};
  return (String(value || "").normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replaceAll("&", " and ").match(/[\p{L}\p{N}]+/gu) || [])
    .map((word)=>Object.hasOwn(forms,word) ? forms[word] : word).join(" ");
}

function holdingsCreditRatingTone(record = {}) {
  const change=record.latest_change, grades=typeof MANUAL_CREDIT_GRADES === "undefined" ? null : MANUAL_CREDIT_GRADES[record.agency];
  if (record.status !== "rated" || record.primary_eligible === false || creditRatingsIsManual(record) || record.identity_verification === "user_entered"
    || !change || change.origin !== "public_ai" || change.event_type !== "rating_change"
    || change.previous_status !== "rated" || change.new_status !== "rated" || change.new_rating !== record.rating
    || change.agency !== record.agency || record.scale !== "global" || record.term !== "long_term" || !record.scope || !record.rating_type
    || !holdingsCreditRatingEntity(record.entity_name) || holdingsCreditRatingEntity(record.entity_name) !== holdingsCreditRatingEntity(change.entity_name)
    || ["scope","scale","term","rating_type","currency_basis"].some((field)=>(record[field] ?? null) !== (change[field] ?? null)) || !grades) return "unchanged";
  // Missing exact debt identity cannot establish a comparable issue transition.
  if (record.scope === "issue" && !["isin","cusip"].some((field)=>record[field] && record[field] === change[field])) return "unchanged";
  const previous=grades.indexOf(change.previous_rating), current=grades.indexOf(change.new_rating);
  return previous < 0 || current < 0 || current === previous ? "unchanged" : current < previous ? "upgrade" : "downgrade";
}

function holdingsCreditRatingToneLabel(record) {
  return t({upgrade:"Agency rating upgraded",downgrade:"Agency rating downgraded",unchanged:"No comparable agency grade change"}[holdingsCreditRatingTone(record)]);
}

function holdingsCreditRatingsContent(entry) {
  const agencies = [["moodys", "Moody’s"], ["sp", "S&P"], ["fitch", "Fitch"]];
  const rows = Array.isArray(entry.context?.ratings) ? entry.context.ratings : [];
  const pending = entry.state === "loading" && !entry.context;
  const unavailable = ["error", "not_found"].includes(entry.state) && !entry.context;
  const staleMark = (label) => `<span class="holding-credit-stale" aria-label="${esc(t(label))}" title="${esc(t(label))}">!</span>`;
  return `<span class="holding-credit-legend">${esc(t("Outlook / Watch"))}</span>${agencies.map(([key, name]) => {
    const record = rows.find((row) => row.agency === key) || { status: unavailable ? "unavailable" : "not_checked", outlook: "unknown", watch: "unknown" };
    const manual = creditRatingsIsManual(record);
    const status = pending ? t("Loading…") : holdingsCreditRatingStatus(record);
    const category = record.issuer_fallback ? t("Issuer rating")
      : record.status === "unavailable" && (record.reason_code === "primary_rating_unavailable"
        || Array.isArray(record.observations) && record.observations.some((row) => row.agency === key && row.primary_eligible === false)) ? t("Other categories") : "";
    const extra = [manual && t("Manual"), manual && record.identity_verification === "user_entered" && t("Manual identity"), category].filter(Boolean).join(" · ");
    const tone = !pending && record.status === "rated" && record.rating ? holdingsCreditRatingTone(record) : "";
    return `<span class="holding-credit-agency"><bdi class="holding-credit-agency-name" dir="ltr">${esc(name)}</bdi><span class="holding-credit-opinion"><span class="holding-credit-grade${tone ? ` holding-credit-grade-${tone}` : ""}"${tone ? ` data-credit-grade-tone="${tone}"` : ""}><bdi dir="auto">${esc(status)}</bdi>${record.stale ? staleMark(manual ? "Old manual entry" : "Stale evidence") : ""}</span>${pending ? "" : `<span class="holding-credit-forward"><span title="${esc(`${t("Outlook")}: ${creditRatingsDirection(record.outlook)}`)}">${esc(creditRatingsDirection(record.outlook))}${!manual && record.outlook_stale ? staleMark("Stale outlook") : ""}</span><span class="holding-credit-divider" aria-hidden="true">/</span><span${["positive", "negative", "developing"].includes(record.watch) ? ' class="holding-credit-active-watch"' : ""} title="${esc(`${t("Watch")}: ${creditRatingsDirection(record.watch, true)}`)}">${esc(creditRatingsDirection(record.watch, true))}${!manual && record.watch_stale ? staleMark("Stale watch") : ""}</span></span>`}${extra ? `<span class="holding-credit-category">${esc(extra)}</span>` : ""}</span></span>`;
  }).join("")}`;
}

function holdingsCreditRatingsDescription(entry, symbol) {
  const lines = [t("Credit ratings for {symbol}").replace("{symbol}", symbol)];
  if (entry.state === "loading") lines.push(t("Loading saved ratings…"));
  if (entry.state === "error") lines.push(t("Saved ratings could not be loaded. Open the overview to retry."));
  if (entry.state === "not_found") lines.push(t("This security could not be matched to saved rating information."));
  for (const [key, name] of [["moodys", "Moody’s"], ["sp", "S&P Global Ratings"], ["fitch", "Fitch"]]) {
    const record = (Array.isArray(entry.context?.ratings) ? entry.context.ratings : []).find((row) => row.agency === key)
      || { status: ["error", "not_found"].includes(entry.state) ? "unavailable" : "not_checked" };
    lines.push(`${name}: ${holdingsCreditRatingDescriptionValue(record)}${record.status === "rated" && record.rating ? ` · ${holdingsCreditRatingToneLabel(record)}` : ""} · ${t("Outlook")}: ${creditRatingsDirection(record.outlook)} · ${t("Watch")}: ${creditRatingsDirection(record.watch, true)}`);
    const manual = creditRatingsIsManual(record);
    const reason = manual ? t("User-entered information; the app has not independently verified this rating.") : creditRatingsReason(record.reason_code, record.status);
    if (reason) lines.push(reason);
    if (record.issuer_fallback) lines.push(t("Issuer rating fallback; the specific debt issue was not verified."));
    if (manual) lines.push(`${t("Manual")} · ${t("Last updated")}: ${creditRatingsDate(record.updated_at)} · ${t("Updated by")}: ${record.updated_by || t("Unknown")}`);
    if (record.stale) lines.push(t(manual ? "Old manual entry" : "Stale evidence"));
    if (!manual && record.outlook_stale) lines.push(`${t("Stale outlook")} · ${t("Outlook last verified")}: ${creditRatingsDate(record.outlook_fetched_at)}`);
    if (!manual && record.watch_stale) lines.push(`${t("Stale watch")} · ${t("Watch last verified")}: ${creditRatingsDate(record.watch_fetched_at)}`);
    if (record.reason_code === "primary_rating_unavailable") lines.push(t("No supported long-term issuer or issue rating was verified. Other rating categories remain in the sources."));
    if (record.latest_change && typeof creditRatingLatestChangeText === "function") lines.push(creditRatingLatestChangeText(record.latest_change));
  }
  const availability = creditRatingsAvailability(entry.context);
  if (availability) lines.push(availability);
  lines.push(t("Open the security overview for rating scope, dates and sources."));
  return lines.join("\n");
}

function holdingCreditRatingsCellHtml(item) {
  const holding = item.holding || {};
  if (!creditRatingsEligible(holding)) {
    const unsupported = ["ETF", "FUND", "MUTUALFUND", "MUTUAL_FUND", "OPTION", "FUTURE", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION", "PRIVATE"]
      .some((kind) => [holding.asset_class, holding.asset_sub_class, holding.instrument_type, holding.stock_market].some((value) => String(value || "").toUpperCase() === kind));
    return `<td class="holding-credit-ratings-cell" data-label="${esc(t("Credit ratings"))}"><span class="holding-credit-inapplicable" title="${esc(t(unsupported ? "Company credit ratings do not apply to this instrument." : "A supported security type is required for company credit ratings."))}">${esc(t(unsupported ? "Not applicable" : "Unavailable"))}</span></td>`;
  }
  if (!holdingsCreditRatingsIdentityValid(holding)) return `<td class="holding-credit-ratings-cell" data-label="${esc(t("Credit ratings"))}"><span class="holding-credit-inapplicable" title="${esc(t("A symbol, stock market and currency are required for saved company ratings."))}">${esc(t("Unavailable"))}</span></td>`;
  const key = holdingsCreditRatingsKey(holding), entry = holdingsCreditRatingsEntry(key);
  const marketKey = holdingMarketKey(holding), description = holdingsCreditRatingsDescription(entry, holding.symbol);
  const infoLabel=t("Rating changes and dates for {symbol}").replace("{symbol}",holding.symbol);
  return `<td class="holding-credit-ratings-cell" data-label="${esc(t("Credit ratings"))}"><div class="holding-credit-ratings-layout"><button class="holding-credit-ratings" type="button" data-holdings-credit-key="${esc(key)}" data-holdings-credit-symbol="${esc(holding.symbol)}" data-security-detail-market-key="${esc(marketKey)}" data-security-detail-stock-market="${esc(stockMarketDisplay(holding, marketKey, item.exchange))}" data-security-detail-provider="${esc(dataProviderDisplay(item, holding, marketKey))}" data-security-detail-asset="${esc(holding.asset_class)}" data-security-detail-currency="${esc(holding.currency)}" data-security-detail-location="${esc(holding.country || holding.location || "")}" data-security-detail-name="${esc(holding.name || holding.symbol)}" aria-haspopup="dialog" aria-controls="securityDetailModal" aria-busy="${entry.state === "loading"}" aria-label="${esc(description)}" title="${esc(description)}">${holdingsCreditRatingsContent(entry)}</button><button class="holding-credit-history-info" type="button" data-holdings-credit-info="${esc(key)}" data-explanation="${esc(description)}" aria-label="${esc(infoLabel)}" aria-describedby="riskBadgeExplanation">ⓘ</button></div></td>`;
}

function renderHoldingsCreditRatings() {
  const cache = holdingsCreditRatingsSession();
  document.querySelectorAll("[data-holdings-credit-key]").forEach((button) => {
    const entry = cache.entries[button.dataset.holdingsCreditKey] || { context: null, state: "idle" };
    const html = holdingsCreditRatingsContent(entry);
    if (button.innerHTML !== html) button.innerHTML = html;
    const description = holdingsCreditRatingsDescription(entry, button.dataset.holdingsCreditSymbol);
    button.title = description;
    button.setAttribute("aria-label", description);
    button.setAttribute("aria-busy", String(entry.state === "loading"));
    const info=button.parentElement?.querySelector("[data-holdings-credit-info]");
    if(info){info.dataset.explanation=description; const label=t("Rating changes and dates for {symbol}").replace("{symbol}",button.dataset.holdingsCreditSymbol);info.setAttribute("aria-label",label);}
  });
}

async function loadHoldingsCreditRatings(items) {
  if (!currentUser()) return;
  const cache = holdingsCreditRatingsSession(), version = state.portfolioLoadVersion || 0;
  if (cache.portfolioVersion !== version) {
    cache.controllers.forEach((controller) => controller.abort());
    cache.controllers.clear();
    cache.portfolioVersion = version;
    cache.generation += 1;
    cache.requested.clear();
  }
  const generation = cache.generation;
  const keys = [...new Set((items || []).map((item) => item.holding || {}).filter((holding) => creditRatingsEligible(holding) && holdingsCreditRatingsIdentityValid(holding)).map(holdingsCreditRatingsKey))]
    .filter((key) => !cache.requested.has(key));
  if (!keys.length) return;
  const revisions = new Map();
  keys.forEach((key) => {
    cache.requested.add(key);
    const entry = holdingsCreditRatingsEntry(key);
    entry.state = "loading";
    revisions.set(key, ++entry.revision);
  });
  renderHoldingsCreditRatings();
  const chunks = [];
  for (let index = 0; index < keys.length; index += 200) chunks.push(keys.slice(index, index + 200));
  await Promise.all(chunks.map(async (chunk) => {
    const params = new URLSearchParams();
    chunk.forEach((key) => params.append("security_keys", key));
    const controller = new AbortController();
    cache.controllers.add(controller);
    const timeout = setTimeout(() => controller.abort(), 30000);
    const current = () => holdingsCreditRatingsActive(cache) && cache.generation === generation && (state.portfolioLoadVersion || 0) === version;
    try {
      const response = await api(`/api/securities/credit-ratings/summaries?${params}`, { signal: controller.signal });
      if (!current()) return;
      const found = new Map((Array.isArray(response.items) ? response.items : []).map((item) => [item.security_key, item]));
      const missing = new Set(Array.isArray(response.not_found_keys) ? response.not_found_keys : []);
      chunk.forEach((key) => {
        const entry = cache.entries[key];
        if (entry.revision !== revisions.get(key)) return;
        if (found.has(key) && holdingsCreditRatingsKey(found.get(key)) === key) { entry.context = found.get(key); entry.state = "ready"; }
        else if (missing.has(key)) { entry.context = null; entry.state = "not_found"; }
        else entry.state = "error";
      });
    } catch {
      if (!current()) return;
      chunk.forEach((key) => {
        const entry = cache.entries[key];
        if (entry.revision === revisions.get(key)) entry.state = "error";
      });
    } finally {
      clearTimeout(timeout);
      cache.controllers.delete(controller);
      if (holdingsCreditRatingsActive(cache) && cache.generation === generation && !current()) {
        chunk.forEach((key) => {
          const entry = cache.entries[key];
          if (entry.revision === revisions.get(key) && entry.state === "loading") entry.state = "error";
        });
        renderHoldingsCreditRatings();
      }
      if (current()) renderHoldingsCreditRatings();
    }
  }));
}

function updateHoldingsCreditRatingsFromOverview(context) {
  if (!context?.security_key || context.summary_only === true) return;
  const cache = holdingsCreditRatingsSession(), entry = holdingsCreditRatingsEntry(context.security_key);
  entry.context = context;
  entry.state = "ready";
  entry.revision += 1;
  if (holdingsCreditRatingsActive(cache)) renderHoldingsCreditRatings();
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-holdings-credit-key]");
  if (!button) return;
  openSecurityDetail({ ...button.dataset, securityDetailSymbol: button.dataset.holdingsCreditSymbol }, button).catch(() => {
    $("status").textContent = t("Could not open the security overview. Try again.");
  });
});
