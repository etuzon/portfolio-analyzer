/* Shared read-only planner for Securities and buy-signal cards. */
const tradePlannerViews = new Map();
let tradePlannerRequestVersion = 0;
let tradePlannerDashboardFingerprint = null;

function tradePlannerReason(reason) {
  return t({
    invalid_request: "Enter a stock and a positive amount, or leave the amount empty.",
    ambiguous_listing: "This symbol has multiple listings. Choose its market in Securities.",
    listing_unverified: "The stock listing could not be verified. Check the symbol and market.",
    unsupported_instrument: "The planner supports listed stocks and ETFs only.",
    price_unavailable: "A dated price from the last 7 days is required. Refresh analytics or add a recent local price, then retry.",
    valuation_unavailable: "Update the holdings listed below before calculating a trade amount.",
    fx_unavailable: "A required exchange rate is unavailable. Check display currencies and refresh.",
    cash_unverified: "Spendable cash cannot be verified from the ledger. Check balances and transactions in other currencies.",
    no_cash: "No positive cash is available for this trade.",
    account_type: "Only investment accounts are considered for trading.",
    account_country: "The account country must match the stock listing. US stocks require a US account.",
    account_currency: "The account must hold cash in the stock currency; currency conversion is not assumed.",
    collateral_unverified: "Existing shorts or derivatives may tie up cash as collateral.",
    existing_long: "Sell the existing long position before opening a short in this account.",
    risk_limit: "The modeled risk limit leaves no room for this trade.",
    cash_reserve: "Cash reserve and the estimated fee buffer limit the amount.",
    stock_account_limit: "The account stock concentration limit leaves less than one share of room.",
    stock_portfolio_limit: "The portfolio stock concentration limit leaves less than one share of room.",
    sector_account_limit: "The account sector concentration limit leaves less than one share of room.",
    sector_portfolio_limit: "The portfolio sector concentration limit leaves less than one share of room.",
    risk_sizing: "Risk-adjusted sizing leaves less than one share of room.",
    requested_amount: "The requested amount is too small to buy one whole share.",
    no_suitable_account: "No suitable account and amount available.",
  }[reason] || "No suitable account and amount available.");
}

function tradePlannerAccountName(account) {
  return [account.management_company, account.account_id || account.username].filter(Boolean).join(" · ") || t("Account");
}

function tradePlannerIssuesHtml(issues) {
  if (!issues?.length) return "";
  const labels = { price_missing: "No saved price", price_date_missing: "The saved price has no date",
    price_stale: "The saved price is older than 7 days", price_in_future: "The saved price is dated in the future",
    invalid_valuation: "Quantity and recorded value are inconsistent", fx_unavailable: "Required exchange rate unavailable" };
  const list = issues.map((issue) => {
    const label = t(labels[issue.reason] || "No saved price");
    const account = issue.account ? ` · <bdi>${esc(tradePlannerAccountName(issue.account))}</bdi>` : "";
    const day = issue.price_date ? ` · ${esc(t("Last saved price"))}: <bdi>${esc(formatDate(issue.price_date))}</bdi>` : "";
    const repair = issue.manual && ["price_missing", "price_date_missing", "price_stale", "price_in_future"].includes(issue.reason)
      ? `<button class="secondary compact-button" type="button" data-price-history-symbol="${esc(issue.symbol)}" data-price-history-market="${esc(issue.stock_market)}" data-price-history-asset="${esc(issue.asset_class)}" data-price-history-currency="${esc(issue.currency)}" data-price-history-location="${esc(issue.location)}">${esc(t("Update saved price"))}</button>` : "";
    return `<li><div><bdi><b>${esc(issue.symbol)}</b></bdi>${account}<br>${esc(label)}${day}</div>${repair}</li>`;
  }).join("");
  return `<ul class="trade-plan-issues">${list}</ul>${issues.some((issue) => issue.manual) ? `<p>${esc(t("Manual securities need a recent price entered in Prices. Refresh does not fetch prices for them. Save a real quote with its actual date, then recalculate."))}</p>` : `<p>${esc(t("Refresh analytics, then recalculate. A missing price date cannot be inferred from the cache update time."))}</p>`}`;
}

function tradePlannerResultHtml(view) {
  if (!view) return "";
  if (view.status === "loading") return `<p role="status">${esc(t("Checking accounts, cash and risk…"))}</p>`;
  if (view.status === "error") return `<p role="status" class="signal-missing">${esc(t("Could not calculate an account suggestion. Your inputs are kept. Try again."))}</p>`;
  if (view.status === "stale") return `<p role="status">${esc(t("Portfolio inputs changed. Recalculate the account suggestion."))}</p>`;
  const result = view.result;
  const exclusions = (result.excluded || []).map(({ account, reason }) => `<li><bdi>${esc(tradePlannerAccountName(account))}</bdi>: ${esc(tradePlannerReason(reason))}</li>`).join("");
  if (result.status !== "ok") return `<p role="status" class="signal-missing">${esc(tradePlannerReason(result.reason))}</p>${tradePlannerIssuesHtml(result.issues)}${exclusions ? `<details><summary>${esc(t("Accounts checked"))}</summary><ul>${exclusions}</ul></details>` : ""}`;
  const rec = result.recommendation, short = result.action === "SHORT";
  const cash = (amount) => `<bdi>${esc(money(amount, rec.currency))}</bdi>`;
  const fact = (label, value) => `<div><dt>${esc(t(label))}</dt><dd>${value}</dd></div>`;
  const limit = t({ cash_reserve: "Cash reserve", stock_account_limit: "Account stock limit", stock_portfolio_limit: "Portfolio stock limit",
    sector_account_limit: "Account sector limit", sector_portfolio_limit: "Portfolio sector limit", risk_sizing: "Risk-adjusted sizing", requested_amount: "Requested amount", risk_limit: "Projected risk" }[rec.limit]);
  const alternatives = (result.alternatives || []).map((item) => `<li><bdi>${esc(tradePlannerAccountName(item.account))}</bdi>: <bdi>${esc(money(item.amount, item.currency))}</bdi> · ${esc(t("Projected risk"))} <bdi>${item.riskAfter}/100</bdi></li>`).join("");
  return `<div class="trade-plan-heading" role="status"><span>${esc(t(short ? "Conditional short estimate" : "Suggested purchase"))}</span>
    <strong><bdi>${esc(tradePlannerAccountName(rec.account))}</bdi> · ${cash(rec.amount)}</strong>
    <span><bdi>${esc(result.symbol)}</bdi> · ${esc(fmt(rec.quantity, 0))} ${esc(t("whole shares"))} · ${esc(t("Quote date"))}: <bdi>${esc(formatDate(result.quote.date))}</bdi> · ${esc(currencyDisplayLabel(rec.currency))}</span></div>
    ${result.requested !== null ? `<p>${esc(t("Requested amount"))}: ${cash(result.requested)}${rec.amount < result.requested ? ` · ${esc(t("Reduced to fit the limits and whole shares."))}` : ""}</p>` : ""}
    <dl class="trade-plan-facts">
      ${fact("Recorded cash", cash(rec.cash))}${fact("Cash reserve", cash(rec.reserve))}
      ${fact(short ? "Cash after modeled collateral and fee buffer" : "Cash after purchase and fee buffer", cash(rec.cashRemaining))}
      ${fact("Account risk before → after", `<bdi dir="ltr">${rec.riskBefore}/100 → ${rec.riskAfter}/100</bdi>`)}
      ${fact("Stock weight before → after", `<bdi dir="ltr">${esc(fmt(rec.weightBefore, 1))}% → ${esc(fmt(rec.weightAfter, 1))}%</bdi>`)}
      ${short ? fact("Modeled collateral", cash(rec.collateral)) : ""}
    </dl>
    <p>${esc(t("Amount limited by"))}: ${esc(limit)}. ${esc(t("Accounts are ranked by projected risk, stock and sector exposure, and fit to the requested amount."))}</p>
    ${short ? `<p class="signal-missing">${esc(t("Broker short permission, share availability, and margin requirements are unverified. The model reserves 200% of short exposure from existing cash and does not spend short-sale proceeds."))}</p>` : ""}
    <details><summary>${esc(t("Sizing rules and other accounts"))}</summary>
      <p>${esc(t("Model defaults: keep at least 10% of account value and 20% of current cash; raise the value reserve to 20% for shorts, higher risk or a short horizon. Allow 1% of trade value for fees and slippage."))}</p>
      <p>${esc(t("Buy limits: stock 10% per account and 5% of the liquid portfolio. Short limits: 2.5% and 2%. Sector limits: 30% per account and 25% of the liquid portfolio. Retirement and ESOP assets are excluded from this sizing base."))}</p>
      <p>${esc(t("Starting trade size is the smallest of 5% of account value, 2% of portfolio value and 25% of cash. Higher risk, volatility, shorts, unknown sector or missing/short retirement horizon reduce it. Modeled risk may rise by at most 5 points and may not exceed 75/100."))}</p>
      <p>${esc(t("For a cash-only account, the first position may raise modeled risk by up to 25 points because industry, issuer and volatility risk components start with the first holding. The 75/100 ceiling still applies."))}</p>
      <p>${esc(t("Retirement horizon is a proxy, not your stated investment goal or risk tolerance. Recorded cash is not confirmed broker buying power. Quotes and FX are saved estimates; taxes and actual broker fees are not modeled."))}</p>
      <p>${esc(t("Holdings are valued using their recent saved quotes for this estimate; the recorded portfolio is unchanged."))}</p>
      ${rec.unknownSector ? `<p class="signal-missing">${esc(t("Sector is unknown; the proposed amount was reduced."))}</p>` : ""}
      ${rec.horizon === null ? `<p>${esc(t("Account horizon is unknown; the proposed amount was reduced."))}</p>` : ""}
      ${alternatives ? `<p>${esc(t("Other eligible accounts"))}</p><ul>${alternatives}</ul>` : ""}
      ${exclusions ? `<p>${esc(t("Excluded accounts"))}</p><ul>${exclusions}</ul>` : ""}
    </details>
    <p class="trade-plan-note">${esc(t("Estimate only; no order placed. Separate suggestions reuse the same cash and are alternatives, not a combined spending plan."))} ${esc(t("Calculated"))}: <bdi>${esc(formatDateTime(result.calculatedAt))}</bdi></p>
    ${result.refreshPending ? `<p class="signal-missing">${esc(t("Analytics are updating. Recalculate after the update for the latest estimate."))}</p>` : ""}`;
}

function tradePlannerSignalAction(signal, index) {
  if (signal.signal !== "buy") return "";
  const key = JSON.stringify([signal.rule_id, signal.symbol]);
  const view = tradePlannerViews.get(key);
  return `<button class="secondary compact-button" type="button" data-trade-signal="${esc(key)}" data-trade-symbol="${esc(signal.symbol)}" aria-controls="tradeSignalResult${index}" aria-expanded="${Boolean(view)}"${view?.status === "loading" ? " disabled" : ""}>${esc(t(view ? "Recalculate account & amount" : "Suggest account & amount"))}</button>`;
}

function tradePlannerSignalPanel(signal, index) {
  if (signal.signal !== "buy") return "";
  const key = JSON.stringify([signal.rule_id, signal.symbol]), view = tradePlannerViews.get(key);
  return `<section id="tradeSignalResult${index}" class="trade-plan-result" data-trade-result="${esc(key)}" aria-label="${esc(t("Account recommendation"))}" aria-live="polite" aria-busy="${view?.status === "loading"}"${view ? "" : " hidden"}>${tradePlannerResultHtml(view)}</section>`;
}

function renderTradePlannerViews() {
  document.querySelectorAll("[data-trade-result]").forEach((panel) => {
    const view = tradePlannerViews.get(panel.dataset.tradeResult);
    panel.hidden = !view;
    panel.setAttribute("aria-busy", String(view?.status === "loading"));
    panel.innerHTML = tradePlannerResultHtml(view);
  });
  document.querySelectorAll("[data-trade-signal]").forEach((button) => {
    const view = tradePlannerViews.get(button.dataset.tradeSignal);
    button.disabled = view?.status === "loading";
    button.setAttribute("aria-expanded", String(Boolean(view)));
    button.textContent = t(view ? "Recalculate account & amount" : "Suggest account & amount");
  });
  const button = $("suggestTradeAccount");
  if (button) button.disabled = tradePlannerViews.get("manual")?.status === "loading";
}

function invalidateTradePlans() {
  for (const [key, view] of tradePlannerViews) {
    if (view.status !== "stale") tradePlannerViews.set(key, { status: "stale" });
  }
  renderTradePlannerViews();
}

function resetTradePlannerViews() {
  tradePlannerViews.clear();
  tradePlannerDashboardFingerprint = null;
  renderTradePlannerViews();
}

function checkTradePlannerInputs() {
  const fingerprint = JSON.stringify([state.localAccounts, state.localTransactions, state.items, state.fxRates]);
  if (tradePlannerDashboardFingerprint !== null && tradePlannerDashboardFingerprint !== fingerprint) invalidateTradePlans();
  tradePlannerDashboardFingerprint = fingerprint;
}

async function calculateTradePlan(key, request) {
  if (tradePlannerViews.get(key)?.status === "loading") return;
  const version = ++tradePlannerRequestVersion;
  tradePlannerViews.set(key, { status: "loading", version });
  renderTradePlannerViews();
  try {
    const params = new URLSearchParams({ symbol: request.symbol, stock_market: request.market || "" });
    const context = await api(`/api/trade-planner/context?${params}`);
    if (tradePlannerViews.get(key)?.version !== version) return;
    const result = window.PortfolioTradePlanner.plan(context, request, {
      risk: riskScoreForItems, horizon: accountHorizonYears, industry: industryLabel,
      volatility: volatilityProxy, derivative: derivativeHolding,
    });
    tradePlannerViews.set(key, { status: "ready", result });
  } catch {
    if (tradePlannerViews.get(key)?.version !== version) return;
    tradePlannerViews.set(key, { status: "error" });
  }
  renderTradePlannerViews();
}

function suggestManualTradeAccount() {
  const form = $("tradePlannerForm");
  if (!form.reportValidity()) return;
  calculateTradePlan("manual", { symbol: $("tradePlanSymbol").value.trim().toUpperCase(),
    market: $("tradePlanMarket").value.trim(), action: $("tradePlanAction").value,
    amount: $("tradePlanAmount").value, amountCurrency: $("tradePlanCurrency").value });
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-trade-signal]");
  if (button) calculateTradePlan(button.dataset.tradeSignal, { symbol: button.dataset.tradeSymbol, action: "BUY", amount: "" });
});
document.addEventListener("submit", (event) => {
  if (event.target.id !== "tradePlannerForm") return;
  event.preventDefault();
  suggestManualTradeAccount();
});
document.addEventListener("input", (event) => {
  if (!event.target.closest("#tradePlannerForm")) return;
  tradePlannerViews.delete("manual");
  renderTradePlannerViews();
});
document.addEventListener("change", (event) => {
  if (!event.target.closest("#tradePlannerForm")) return;
  tradePlannerViews.delete("manual");
  renderTradePlannerViews();
});
