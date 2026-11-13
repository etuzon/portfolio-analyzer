/* One user-started enrichment job owns market work and all scoped rating batches. */
function aiCreditRatingsStatus(status) {
  return t({ pending: "Waiting for rating research", updated: "Supported facts saved", partial: "Partial rating evidence",
    unavailable: "Checked; no verified rating evidence", not_attempted: "Not checked" }[status] || "Not checked");
}

function aiCreditRatingsMessage(outcome) {
  if (outcome.status === "pending") return t("Waiting for its public-source rating batch.");
  if (outcome.status === "not_attempted") return t("This security was not researched. After an interruption, retry the remaining rating checks.");
  if (outcome.status === "updated" || outcome.status === "partial") return t("Supported agency facts were saved. Missing agency information remains Unknown.");
  return creditRatingsReason(outcome.code, "") || t("Public sources did not verify supported rating evidence. Unknown does not mean Unrated.");
}

function aiCreditRatingsAgencyStatus(status) {
  return t({ rated: "Verified rating", unrated: "Unrated", withdrawn: "Withdrawn", conflicting: "Conflicting evidence",
    not_found: "Not found", unavailable: "Unavailable", not_checked: "Not checked", pending: "Not checked" }[status] || "Not checked");
}

function renderAIEnrichmentCreditRatings() {
  const section = $("aiCreditRatings"), ui = state.aiEnrichment, ratings = ui.job?.credit_ratings;
  if (!section) return;
  section.hidden = !ratings;
  const retry = $("aiEnrichmentRetryRatings");
  if (retry) {
    retry.hidden = !ratings || ui.pending || ui.resume || ui.job?.status !== "failed" || !(Number(ratings.summary?.not_attempted) > 0);
    retry.disabled = !canWrite() || ui.pending || state.auth.forcedPasswordChange || Boolean(currentUser()?.must_change_password);
    retry.textContent = t("Retry remaining rating checks");
  }
  if (!ratings) return;
  section.setAttribute("aria-busy", String(["queued", "running"].includes(ratings.status)));
  const completed = Number(ratings.progress?.completed), total = Number(ratings.progress?.total);
  const known = Number.isFinite(completed) && completed >= 0 && Number.isFinite(total) && total >= 0;
  $("aiCreditRatingsCounts").textContent = known
    ? t("Rating checks: {completed} of {total} company securities").replace("{completed}", fmt(completed, 0)).replace("{total}", fmt(total, 0)) : t("Rating research is queued.");
  const summary = ratings.summary || {};
  const outcomes = Array.isArray(ratings.outcomes) ? ratings.outcomes : [];
  const waiting = outcomes.filter((outcome) => outcome.status === "pending").length;
  const untouched = outcomes.length ? outcomes.filter((outcome) => outcome.status === "not_attempted").length : summary.not_attempted;
  $("aiCreditRatingsSummary").textContent = [[summary.updated, "Supported facts saved"], [summary.partial, "Partial rating evidence"],
    [summary.unavailable, "Checked; no verified rating evidence"], [waiting, "Waiting for rating research"], [untouched, "Not checked"]]
    .filter(([count]) => Number.isFinite(Number(count))).map(([count, label]) => `${t(label)}: ${fmt(Number(count), 0)}`).join(" · ");
  const current = ratings.status === "running" && ratings.progress?.current_security;
  $("aiCreditRatingsCurrent").hidden = !current;
  $("aiCreditRatingsCurrent").textContent = current ? `${t("Current security")}: ${[current.symbol, current.stock_market, current.currency].filter(Boolean).join(" · ")}` : "";
  const list = $("aiCreditRatingsResults"), focusKey = document.activeElement?.dataset?.aiCreditKey;
  const scrollTop = list.scrollTop;
  const html = outcomes.map((outcome) => {
    const key = outcome.security_key || aiSecurityKey(outcome);
    const item = state.allPortfolioItems.find((entry) => aiSecurityKey(entry.holding) === aiSecurityKey(outcome));
    const identity = [outcome.symbol, outcome.stock_market, outcome.currency].filter(Boolean).join(" · ");
    const verified = Array.isArray(outcome.verified_agencies) ? new Set(outcome.verified_agencies.filter((agency) => ["moodys", "sp", "fitch"].includes(agency))).size : null;
    const coverage = verified === null ? "" : t("Supported evidence from {count} of 3 agencies").replace("{count}", fmt(verified, 0));
    const agencies = [["moodys", "Moody’s"], ["sp", "S&P Global Ratings"], ["fitch", "Fitch"]].map(([agency, label]) =>
      `<span><bdi dir="ltr">${esc(label)}</bdi>: ${esc(aiCreditRatingsAgencyStatus(outcome.agency_statuses?.[agency]))}</span>`).join("");
    return `<li data-ai-credit-result="${esc(key)}"><div class="ai-enrichment-result-heading"><bdi dir="auto">${esc(identity)}</bdi><span class="badge neutral">${esc(aiCreditRatingsStatus(outcome.status))}</span></div><p>${esc(aiCreditRatingsMessage(outcome))}</p>${coverage ? `<p>${esc(coverage)}</p>` : ""}<div class="ai-credit-agencies">${agencies}</div>${item ? `<button class="secondary compact-button" type="button" data-ai-credit-key="${esc(key)}">${esc(t("Open ratings and history"))}</button>` : ""}</li>`;
  }).join("");
  if (list.innerHTML !== html) {
    if (typeof document.createElement === "function") {
      const template = document.createElement("template");
      template.innerHTML = html;
      const existing = new Map([...list.children].map((node) => [node.dataset.aiCreditResult, node]));
      const desired = [...template.content.children];
      desired.forEach((candidate, index) => {
        const key = candidate.dataset.aiCreditResult, row = existing.get(key);
        if (row) {
          if (row.innerHTML !== candidate.innerHTML) {
            const returnButton = row.querySelector("[data-ai-credit-key]");
            row.innerHTML = candidate.innerHTML;
            const replacement = row.querySelector("[data-ai-credit-key]");
            if (returnButton && replacement) {
              returnButton.textContent = replacement.textContent;
              replacement.replaceWith(returnButton);
            }
          }
          if (list.children[index] !== row) list.insertBefore(row, list.children[index] || null);
          existing.delete(key);
        } else list.insertBefore(candidate, list.children[index] || null);
      });
      existing.forEach((row) => row.remove());
    } else list.innerHTML = html;
    list.scrollTop = scrollTop;
    if (focusKey) [...list.querySelectorAll("[data-ai-credit-key]")].find((node) => node.dataset.aiCreditKey === focusKey)?.focus({ preventScroll: true });
  }
  list.hidden = !html;
}

function refreshAIEnrichmentCreditRatings(job, ui, { table = true } = {}) {
  if (!job?.credit_ratings || ["queued", "running"].includes(job.status) || state.aiEnrichment !== ui || ui.refreshedRatingsJob === job.request_id || !currentUser()) return;
  ui.refreshedRatingsJob = job.request_id;
  if (table && typeof holdingsCreditRatingsSession === "function") {
    const cache = holdingsCreditRatingsSession();
    cache.controllers.forEach((controller) => controller.abort());
    cache.controllers.clear(); cache.generation += 1; cache.requested.clear();
    loadHoldingsCreditRatings(state.allPortfolioItems || []).catch(() => {});
  }
  if (state.securityDetail && !$("securityDetailModal")?.hidden && typeof creditRatingsEntry === "function") {
    const entry = creditRatingsEntry();
    if (entry && creditRatingsEligible(state.securityDetail)) loadSecurityCreditRatings(entry, { force: true });
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest?.("[data-ai-credit-key]");
  if (!button) return;
  const item = state.allPortfolioItems.find((entry) => aiSecurityKey(entry.holding) === button.dataset.aiCreditKey);
  if (!item) return;
  const holding = item.holding, marketKey = holdingMarketKey(holding);
  openSecurityDetail({ securityDetailSymbol: holding.symbol, securityDetailMarketKey: marketKey,
    securityDetailStockMarket: holding.stock_market, securityDetailCurrency: holding.currency, securityDetailAsset: holding.asset_class }, button).catch(() => {
    $("status").textContent = t("Could not open the security overview. Try again.");
  });
});
