/* Frozen, independent risk-reduction alternatives. No trade or portfolio writes. */
let riskScenariosView = {
  version: 0, context: null, result: null, accountId: "", maxScenarios: 5,
  convertProceeds: false, loading: false, error: "", maximumError: false, maximumDraft: null, amounts: new Map(), errors: new Map(),
};

function riskScenarioText(key, replacements = {}) {
  return Object.entries(replacements).reduce((text, [name, value]) => text.replaceAll(`{${name}}`, String(value)), t(key));
}
function riskScenarioAccountLabel(account) {
  return [account?.management_company, account?.username, account?.account_id].filter(Boolean).join(" · ") || account?.label || String(account?.id || t("Account"));
}
function riskScenarioError(code) {
  return t({
    invalid_amount: "Enter a valid sell amount of zero or more.",
    amount_exceeds_holding: "The sell amount cannot exceed the saved holding value.",
    missing_fx: "A required exchange rate is missing. Refresh portfolio data and try again.",
    context_unavailable: "Risk scenarios are unavailable with the current saved data. Refresh portfolio data and try again.",
  }[code] || "Could not calculate this scenario. Review the amount or refresh scenarios to try again.");
}
function riskScenarioStorageKey() { return `riskScenariosMax:${state.auth?.user?.id || ""}`; }
function riskScenarioStoredMaximum() {
  try {
    const value = Number(localStorage.getItem(riskScenarioStorageKey()));
    return Number.isInteger(value) && value >= 1 && value <= 20 ? value : 5;
  } catch { return 5; }
}
function resetRiskScenarios() {
  riskScenariosView = { version: riskScenariosView.version + 1, context: null, result: null,
    accountId: "", maxScenarios: 5, convertProceeds: false, loading: false, error: "", maximumError: false, maximumDraft: null, amounts: new Map(), errors: new Map() };
  if ($("riskScenariosResults")) $("riskScenariosResults").replaceChildren();
}

function openRiskScenarios(accountId = "", opener) {
  riskScenariosView.accountId = String(accountId || "");
  riskScenariosView.maxScenarios = riskScenarioStoredMaximum();
  riskScenariosView.convertProceeds = false;
  riskScenariosView.maximumError = false;
  riskScenariosView.maximumDraft = null;
  riskScenariosView.context = null;
  riskScenariosView.result = null;
  riskScenariosView.amounts = new Map();
  riskScenariosView.errors = new Map();
  $("riskScenariosModal").dataset.riskScenarioOpenerAccount = String(accountId || "");
  openModal("riskScenariosModal", opener, { focusId: "riskScenariosTitle" });
  loadRiskScenarios();
}

function riskScenariosOptions() {
  const view = riskScenariosView;
  return { calculate: riskHistoryCalculate, maxScenarios: view.maxScenarios,
    accountId: view.accountId, convertProceeds: view.convertProceeds, derivative: derivativeHolding };
}
function riskScenariosAccept(result) {
  const view = riskScenariosView;
  view.result = result;
  view.amounts = new Map((result.scenarios || []).map(scenario => [String(scenario.id), String(scenario.amount)]));
  view.errors = new Map();
}
async function loadRiskScenarios() {
  const view = riskScenariosView;
  const version = ++view.version, userId = state.auth?.user?.id;
  view.loading = true;
  view.error = "";
  renderRiskScenarios();
  try {
    const context = await api(`/api/portfolio/risk-scenarios/context?base_currency=${encodeURIComponent(state.baseCurrency || "ILS")}`);
    if (version !== riskScenariosView.version || view !== riskScenariosView || userId !== state.auth?.user?.id) return;
    const cancelled = () => version !== riskScenariosView.version || view !== riskScenariosView || userId !== state.auth?.user?.id;
    const result = await window.PortfolioRiskScenarios.generate(context, { ...riskScenariosOptions(), cancelled });
    if (version !== riskScenariosView.version || view !== riskScenariosView || userId !== state.auth?.user?.id) return;
    view.context = context;
    riskScenariosAccept(result);
  } catch (error) {
    if (version !== riskScenariosView.version || view !== riskScenariosView || userId !== state.auth?.user?.id) return;
    const contextErrors = {
      risk_context_unknown_cash: "Account cash is incomplete. Review account cash in Accounts, then refresh portfolio data and scenarios.",
      risk_context_missing_currency: "A currency or saved exchange rate is missing. Complete the data, refresh the portfolio and retry.",
      risk_context_missing_fx: "A currency or saved exchange rate is missing. Complete the data, refresh the portfolio and retry.",
      risk_context_missing_classification: "A holding classification is missing. Complete security details, refresh the portfolio and retry.",
      risk_context_future_transactions: "Future transactions prevent a current-position scenario. Review transaction dates and retry.",
      risk_context_invalid_cash_transaction: "Recorded cash or transaction details are inconsistent. Review Transactions, refresh the portfolio and retry.",
      risk_context_mixed_cash_currencies: "Recorded cash or transaction details are inconsistent. Review Transactions, refresh the portfolio and retry.",
      risk_context_invalid_transaction_date: "Recorded cash or transaction details are inconsistent. Review Transactions, refresh the portfolio and retry.",
      risk_context_invalid_transaction: "Recorded cash or transaction details are inconsistent. Review Transactions, refresh the portfolio and retry.",
      risk_context_not_ready: "Refresh portfolio data, wait for analytics to finish, then refresh scenarios.",
      risk_context_stale: "Refresh portfolio data, wait for analytics to finish, then refresh scenarios.",
      risk_context_incomplete_values: "A holding valuation or account link is missing. Complete the data, refresh the portfolio and retry.",
      risk_context_unassigned_account: "A holding valuation or account link is missing. Complete the data, refresh the portfolio and retry.",
    };
    view.error = contextErrors[error.code] || "Could not load risk scenarios. Your current scenarios are kept. Select Refresh scenarios to retry.";
  } finally {
    if (version === riskScenariosView.version && view === riskScenariosView && userId === state.auth?.user?.id) {
      view.loading = false;
      renderRiskScenarios();
    }
  }
}
async function regenerateRiskScenarios() {
  const view = riskScenariosView;
  if (!view.context || view.loading) return;
  const version = ++view.version, userId = state.auth?.user?.id, context = view.context;
  const cancelled = () => version !== riskScenariosView.version || view !== riskScenariosView || userId !== state.auth?.user?.id;
  view.loading = true;
  view.error = "";
  renderRiskScenarios();
  try {
    const result = await window.PortfolioRiskScenarios.generate(context, { ...riskScenariosOptions(), cancelled });
    if (cancelled()) return;
    riskScenariosAccept(result);
  } catch (error) {
    if (cancelled()) return;
    view.error = "Could not calculate risk scenarios. Your current scenarios are kept. Select Refresh scenarios to retry.";
  } finally {
    if (!cancelled()) {
      view.loading = false;
      renderRiskScenarios();
    }
  }
}
function riskScenarioScore(risk) {
  const value = typeof risk === "number" ? risk : risk?.score;
  return Number.isFinite(value) ? value : null;
}
function riskScenarioComparison(label, beforeRisk, afterRisk) {
  const before = riskScenarioScore(beforeRisk), after = riskScenarioScore(afterRisk);
  if (before === null || after === null) return `<div class="risk-scenario-comparison"><span>${esc(t(label))}</span><strong>${esc(t("Not available"))}</strong></div>`;
  const delta = after - before;
  const deltaLabel = riskScenarioText("{change} points", { change: `${delta > 0 ? "+" : ""}${fmt(delta, 0)}` });
  return `<div class="risk-scenario-comparison"><span>${esc(t(label))}</span><div class="risk-scenario-scores"><bdi>${esc(fmt(before, 0))}</bdi><span aria-hidden="true">${state.language === "he" ? "←" : "→"}</span><strong dir="ltr"><bdi>${esc(fmt(after, 0))}</bdi><small>/100</small></strong><small class="${delta < 0 ? "down" : delta > 0 ? "up" : "neutral"}"><bdi>${esc(deltaLabel)}</bdi></small></div></div>`;
}
function riskScenarioProjection(scenario) {
  const reasons = {
    concentration: "Concentration", asset_mix: "Asset mix", currency: "Currency exposure", industry: "Industry concentration",
    cash: "Cash buffer", derivatives: "Options, futures and leverage", volatility: "Volatility", horizon: "Investment horizon",
    issuer_country: "Issuer and country concentration", data_quality: "Missing data", borrowing: "Borrowing adjustment",
  };
  const changes = (scenario.reasons || []).filter(key => reasons[key]).map(key => t(reasons[key]));
  const rationale = scenario.improves
    ? changes.length ? riskScenarioText("Lower modeled components: {components}", { components: changes.join(", ") }) : t("This amount lowers at least one modeled risk score.")
    : t("This amount raises at least one risk score or leaves both unchanged.");
  const quantity = Number.isFinite(scenario.quantity) ? fmt(scenario.quantity, 8) : t("Not available");
  const cash = Number.isFinite(scenario.cashBefore) && Number.isFinite(scenario.cashAfter)
    ? `${money(scenario.cashBefore, scenario.accountCurrency)} ${state.language === "he" ? "←" : "→"} ${money(scenario.cashAfter, scenario.accountCurrency)}` : t("Not available");
  const proceeds = Number.isFinite(scenario.proceedsAccount) ? money(scenario.proceedsAccount, scenario.accountCurrency) : t("Not available");
  return `<p class="risk-scenario-rationale${scenario.improves ? "" : " signal-missing"}">${esc(rationale)}</p>
    <div class="risk-scenario-comparisons">${riskScenarioComparison("Account risk", scenario.accountBefore, scenario.accountAfter)}${riskScenarioComparison("Total portfolio risk", scenario.totalBefore, scenario.totalAfter)}</div>
    <dl class="risk-scenario-facts"><div><dt>${esc(t("Quantity to sell"))}</dt><dd><bdi>${esc(quantity)}</bdi></dd></div><div><dt>${esc(t("Estimated proceeds to account"))}</dt><dd><bdi>${esc(proceeds)}</bdi></dd></div><div><dt>${esc(t("Account cash before and after"))}</dt><dd><bdi>${esc(cash)}</bdi></dd></div></dl>
    ${scenario.converted ? `<p class="section-note">${esc(t("Proceeds are converted to the account currency using the captured exchange rate."))}</p>` : ""}`;
}
function riskScenarioCard(scenario, index) {
  const id = String(scenario.id), view = riskScenariosView;
  const amount = view.amounts.get(id) ?? String(scenario.amount);
  const percent = scenario.maxAmount > 0 ? Math.min(100, Math.max(0, Number(amount) / scenario.maxAmount * 100)) : 0;
  const inputId = `riskScenarioAmount-${index}`, sliderId = `riskScenarioPercent-${index}`, errorId = `riskScenarioError-${index}`;
  const errorCode = view.errors.get(id);
  const error = errorCode ? riskScenarioError(errorCode) : "";
  const quote = scenario.quoteDate ? `${t("Saved quote date")}: ${formatDate(scenario.quoteDate)}` : t("Saved quote date unavailable");
  return `<article class="risk-scenario-card" data-risk-scenario-id="${esc(id)}"><header class="risk-scenario-heading"><div><h3>${esc(riskScenarioText("Sell {symbol}", { symbol: scenario.symbol }))}</h3><p><bdi dir="auto">${esc(scenario.label || scenario.symbol)}</bdi> · <bdi dir="auto">${esc(scenario.accountLabel || riskScenarioAccountLabel(view.context?.accounts?.find(account => String(account.id) === String(scenario.accountId))))}</bdi></p></div></header>
    <div class="risk-scenario-editor"><label class="field risk-scenario-amount" for="${inputId}"><span>${esc(t("Sell amount"))} · <bdi>${esc(currencyDisplayLabel(scenario.currency))}</bdi></span><input id="${inputId}" data-risk-scenario-amount type="number" inputmode="decimal" step="any" min="0" max="${esc(scenario.maxAmount)}" value="${esc(amount)}" dir="ltr" aria-describedby="${errorId}"${view.loading ? " disabled" : ""}${error ? ' aria-invalid="true"' : ""}/></label>
      <label class="field risk-scenario-slider" for="${sliderId}"><span>${esc(t("Percentage of holding to sell"))}: <bdi data-risk-scenario-percent-label>${esc(fmt(Number.isFinite(percent) ? percent : 0, 1))}%</bdi></span><input id="${sliderId}" data-risk-scenario-slider type="range" min="0" max="100" step="1" value="${esc(Number.isFinite(percent) ? percent : 0)}" aria-valuetext="${esc(fmt(Number.isFinite(percent) ? percent : 0, 1))}%"${view.loading ? " disabled" : ""}/></label></div>
    <p id="${errorId}" data-risk-scenario-error class="risk-scenario-error" role="alert"${error ? "" : " hidden"}>${esc(error || "")}</p>
    <div data-risk-scenario-projection${error ? " hidden" : ""}>${riskScenarioProjection(scenario)}</div>
    <p class="section-note">${esc(quote)}${scenario.stale ? ` · ${esc(t("Saved price is stale; the scenario uses that saved price."))}` : ""}</p></article>`;
}
function renderRiskScenarios() {
  const target = $("riskScenariosResults");
  if (!target) return;
  const view = riskScenariosView, result = view.result;
  const restore = typeof preserveRenderedInteraction === "function" ? preserveRenderedInteraction(target) : () => {};
  const select = $("riskScenariosAccount");
  const accounts = (view.context?.accounts || state.localAccounts || []).filter(account => String(account.type).toUpperCase() === "INVESTMENT");
  const selectedKnown = !view.accountId || accounts.some(account => String(account.id) === view.accountId);
  select.innerHTML = `<option value="">${esc(t("All investment accounts"))}</option>${accounts.map(account => `<option value="${esc(account.id)}">${esc(riskScenarioAccountLabel(account))}</option>`).join("")}${selectedKnown ? "" : `<option value="${esc(view.accountId)}">${esc(t("Selected account is unavailable"))}</option>`}`;
  select.value = view.accountId;
  select.disabled = view.loading;
  $("riskScenariosMax").value = view.maximumDraft ?? view.maxScenarios;
  if (view.maximumError) $("riskScenariosMax").setAttribute("aria-invalid", "true");
  else $("riskScenariosMax").removeAttribute("aria-invalid");
  $("riskScenariosMax").disabled = view.loading;
  $("riskScenariosConvert").checked = view.convertProceeds;
  $("riskScenariosConvert").disabled = view.loading;
  $("riskScenariosRefresh").disabled = view.loading;
  $("riskScenariosStatus").textContent = t(view.loading ? "Loading risk scenarios…" : view.maximumError ? "Choose a maximum from 1 to 20 scenarios." : view.error || "");
  target.setAttribute("aria-busy", String(view.loading));
  const timestamp = view.context?.observed_at || result?.observed_at || view.context?.calculated_at;
  $("riskScenariosMeta").textContent = timestamp ? `${t("Snapshot captured")}: ${new Intl.DateTimeFormat("en-GB", { day:"2-digit", month:"2-digit", year:"numeric", hour:"2-digit", minute:"2-digit" }).format(new Date(timestamp))} · ${t("Each scenario is an independent alternative from this snapshot.")}` : t("Each scenario is an independent alternative from the same snapshot.");
  if (!result) {
    target.innerHTML = view.loading || view.error ? "" : `<p class="empty">${esc(t("Refresh scenarios to explore changes to the recorded portfolio."))}</p>`;
  } else {
    const scenarios = result.scenarios || [];
    const baseline = riskScenarioScore(result.baseline?.total);
    target.innerHTML = `${baseline === null ? "" : `<p class="risk-scenario-baseline">${esc(t("Captured total portfolio risk"))}: <bdi>${esc(fmt(baseline, 0))}/100</bdi></p>`}
      <p class="section-note">${esc(riskScenarioText("Scenarios shown: {count}. Maximum: {maximum}.", { count: fmt(scenarios.length, 0), maximum: fmt(view.maxScenarios, 0) }))}</p>
      ${scenarios.length ? scenarios.map(riskScenarioCard).join("") : `<p class="empty">${esc(t(selectedKnown ? "No supported sell scenario lowers the modeled risk for this scope." : "The selected account is unavailable. Choose another account."))}</p>`}
      ${result.excluded?.length ? `<details class="risk-scenario-exclusions"><summary>${esc(t("Holdings without a supported scenario"))} (${esc(fmt(result.excluded.length, 0))})</summary><ul>${result.excluded.map(row => `<li><bdi dir="auto">${esc(row.symbol || t("Security"))}</bdi>: ${esc(riskScenarioExclusion(row.code))}</li>`).join("")}</ul></details>` : ""}`;
  }
  restore();
}
function riskScenarioExclusion(code) {
  return t({
    missing_price: "A saved price is missing.", price_unavailable: "A saved price is missing.", missing_quantity: "The held quantity is unavailable.", valuation_unavailable: "The holding valuation is unavailable.", valuation_mismatch: "The saved price and holding valuation do not agree.", missing_fx: "A required exchange rate is missing.",
    currency_mismatch: "Enable proceeds conversion to explore this holding.", conversion_required: "Enable proceeds conversion to explore this holding.",
    unsupported_instrument: "This instrument is not supported for sell scenarios.", long_positions_only: "This position is not an available long holding.", not_long: "This position is not an available long holding.",
    invalid_cash: "The recorded account cash is unavailable.", cash_unavailable: "The recorded account cash is unavailable.", future_transactions: "Future transactions prevent a current-position scenario.",
  }[code] || "The saved data does not support a sell scenario for this holding.");
}
function updateRiskScenarioAmount(card, source) {
  const view = riskScenariosView;
  if (!view.context || view.loading) return;
  const id = card.dataset.riskScenarioId;
  const index = view.result?.scenarios?.findIndex(row => String(row.id) === id) ?? -1;
  if (index < 0) return;
  const previous = view.result.scenarios[index];
  const input = card.querySelector("[data-risk-scenario-amount]"), slider = card.querySelector("[data-risk-scenario-slider]");
  let raw = input.value;
  if (source.matches("[data-risk-scenario-slider]")) {
    const percent = Number(slider.value);
    raw = String(percent === 100 ? previous.maxAmount : Number((previous.maxAmount * percent / 100).toPrecision(12)));
    input.value = raw;
  }
  view.amounts.set(id, raw);
  const errorNode = card.querySelector("[data-risk-scenario-error]"), projection = card.querySelector("[data-risk-scenario-projection]");
  try {
    if (raw.trim() === "" || !Number.isFinite(Number(raw)) || Number(raw) < 0) throw new Error("invalid_amount");
    if (Number(raw) > previous.maxAmount) throw new Error("amount_exceeds_holding");
    const scenario = window.PortfolioRiskScenarios.project(view.context, previous, Number(raw), { ...riskScenariosOptions(), baseline: view.result.baseline });
    view.result.scenarios[index] = scenario;
    view.errors.delete(id);
    input.removeAttribute("aria-invalid");
    errorNode.hidden = true;
    errorNode.textContent = "";
    projection.innerHTML = riskScenarioProjection(scenario);
    projection.hidden = false;
    const percent = scenario.maxAmount > 0 ? scenario.amount / scenario.maxAmount * 100 : 0;
    slider.value = String(percent);
    slider.setAttribute("aria-valuetext", `${fmt(percent, 1)}%`);
    card.querySelector("[data-risk-scenario-percent-label]").textContent = `${fmt(percent, 1)}%`;
  } catch (error) {
    const message = riskScenarioError(error.message);
    view.errors.set(id, error.message);
    input.setAttribute("aria-invalid", "true");
    errorNode.textContent = message;
    errorNode.hidden = false;
    projection.hidden = true;
  }
}
document.addEventListener("input", event => {
  if (event.target.matches?.("[data-risk-scenario-amount], [data-risk-scenario-slider]")) {
    const card = event.target.closest("[data-risk-scenario-id]");
    if (card) updateRiskScenarioAmount(card, event.target);
  }
});
document.addEventListener("change", event => {
  if (event.target.id === "riskScenariosMax") {
    const value = Number(event.target.value);
    if (event.target.value.trim() === "" || !Number.isInteger(value) || value < 1 || value > 20) {
      riskScenariosView.maximumError = true;
      riskScenariosView.maximumDraft = event.target.value;
      event.target.setAttribute("aria-invalid", "true");
      $("riskScenariosStatus").textContent = t("Choose a maximum from 1 to 20 scenarios.");
      return;
    }
    event.target.removeAttribute("aria-invalid");
    riskScenariosView.maximumError = false;
    riskScenariosView.maximumDraft = null;
    riskScenariosView.maxScenarios = value;
    try { localStorage.setItem(riskScenarioStorageKey(), String(value)); } catch { /* The current session still applies the selected maximum. */ }
    regenerateRiskScenarios();
  } else if (event.target.id === "riskScenariosAccount") {
    riskScenariosView.accountId = event.target.value;
    regenerateRiskScenarios();
  } else if (event.target.id === "riskScenariosConvert") {
    riskScenariosView.convertProceeds = event.target.checked;
    regenerateRiskScenarios();
  }
});
document.addEventListener("click", event => {
  if (event.target.closest?.("#riskScenariosRefresh")) loadRiskScenarios();
});
