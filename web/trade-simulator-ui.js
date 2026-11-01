/* A draft-only combined trading scenario. No ledger writes or broker orders. */
let tradeSimulatorRows = [];
let tradeSimulatorView = null;
let tradeSimulatorVersion = 0;
let tradeSimulatorNextId = 1;
let tradeSimulatorFingerprint = null;

function tradeSimulatorReason(reason) {
  return t({
    invalid_request: "Check the account, security, action and positive quantity.",
    invalid_trade: "Check the account, security, action and positive quantity.",
    invalid_quantity: "Enter a positive quantity.",
    invalid_price: "Enter a positive execution price or leave it empty for the saved quote.",
    invalid_fee: "Enter a fee of zero or more in the account currency.",
    account_missing: "Choose an existing investment account.",
    account_not_found: "Choose an existing investment account.",
    account_type: "Choose an investment account for simulated trades.",
    unknown_account: "Some holdings are not linked to an existing account. Check their account assignments.",
    unsupported_instrument: "This instrument cannot be simulated. Derivatives are not supported.",
    unsupported_asset_class: "Simulation supports shares, including RSU shares, ETFs, bonds and mutual funds in investment accounts.",
    listing_unverified: "The security listing could not be verified. Check symbol and market.",
    ambiguous_listing: "This symbol has multiple listings. Enter its market.",
    price_unavailable: "Enter an execution price for this trade, or add a dated saved quote in Prices and retry.",
    price_missing: "A saved price and its date are required. Update Prices and retry.",
    price_stale: "Saved prices are older than 7 days. Update Prices for a current estimate.",
    fx_unavailable: "Required exchange rate unavailable. Update currencies and retry.",
    cash_unverified: "Cash cannot be verified from the account ledger. Check its currencies and transactions.",
    account_currency: "Account and security currencies must match. Currency conversion is not assumed.",
    insufficient_quantity: "Sell quantity exceeds the projected long holding in this account.",
    insufficient_holdings: "Sell quantity exceeds the projected long holding in this account.",
    sell_exceeds_holding: "Sell quantity exceeds the projected long holding in this account.",
    existing_long: "Sell the projected long holding before opening a short in this account.",
    negative_cash: "Projected cash is negative. Broker borrowing and buying power are unverified.",
    future_transactions: "Future-dated trades make current holdings uncertain. Check transaction dates before simulating this account.",
    insufficient_cash: "Projected cash is negative. Broker borrowing and buying power are unverified.",
    valuation_unavailable: "Some holdings cannot be valued. Update their saved prices and retry.",
    collateral_unverified: "Buying power is unknown because shorts or derivatives may require collateral.",
  }[reason] || "Some inputs cannot be verified. Check this trade, account ledger and saved prices, then retry.");
}

function tradeSimulatorAccountOptions(selected = "") {
  const accounts = (state.localAccounts || []).filter((account) => String(account.type).toUpperCase() === "INVESTMENT");
  return `<option value="">${esc(t("Choose account"))}</option>` + accounts.map((account) =>
    `<option value="${esc(account.id)}"${String(account.id) === String(selected) ? " selected" : ""}>${esc(tradePlannerAccountName(account))} · ${esc(currencyDisplayLabel(account.currency))}</option>`).join("");
}

function tradeSimulatorActions(selected) {
  return ["BUY", "SELL", "SHORT"].map((action) => `<option value="${action}"${selected === action ? " selected" : ""}>${esc(t({ BUY: "Buy", SELL: "Sell", SHORT: "Short" }[action]))}</option>`).join("");
}

function invalidateTradeSimulator() {
  tradeSimulatorVersion += 1;
  if (tradeSimulatorView) tradeSimulatorView = { status: "stale" };
  renderTradeSimulatorResult();
}

function resetTradeSimulator() {
  tradeSimulatorRows = [];
  tradeSimulatorView = null;
  tradeSimulatorVersion += 1;
  tradeSimulatorFingerprint = null;
  $("tradeSimulatorForm")?.reset();
  renderTradeSimulator();
}

function checkTradeSimulatorInputs() {
  const fingerprint = JSON.stringify([state.localAccounts, state.localTransactions, state.allPortfolioItems || state.items, state.fxRates]);
  if (tradeSimulatorFingerprint !== null && tradeSimulatorFingerprint !== fingerprint) invalidateTradeSimulator();
  tradeSimulatorFingerprint = fingerprint;
}

function tradeSimulatorRowHtml(row, index) {
  const field = (name, label, content) => `<label class="management-field"><span>${esc(t(label))}</span>${content}</label>`;
  const input = (name, value, min, placeholder = "") => `<input data-simulation-field="${name}" type="number" min="${min}" step="any" inputmode="decimal" value="${esc(value)}"${placeholder ? ` placeholder="${esc(t(placeholder))}"` : ""} ${["quantity", "fee"].includes(name) ? "required" : ""} />`;
  return `<article class="trade-simulator-row" data-simulation-row="${esc(row.id)}" aria-label="${esc(t("Simulated trade"))} ${index + 1}">
    <div class="trade-simulator-row-heading"><b><bdi dir="ltr">${esc(row.symbol)}${row.market ? ` · ${esc(row.market)}` : ""}</bdi></b><div class="trade-simulator-row-actions">
      <button type="button" class="secondary compact-button" data-simulation-duplicate="${esc(row.id)}"${tradeSimulatorRows.length >= 100 ? " disabled" : ""}>${esc(t("Duplicate"))}</button>
      <button type="button" class="secondary compact-button" data-simulation-remove="${esc(row.id)}" aria-label="${esc(t("Remove simulated trade"))} ${index + 1}">${esc(t("Remove"))}</button></div></div>
    <div class="trade-simulator-row-fields">
      ${field("accountId", "Account", `<select data-simulation-field="accountId" required>${tradeSimulatorAccountOptions(row.accountId)}</select>`)}
      ${field("action", "Action", `<select data-simulation-field="action">${tradeSimulatorActions(row.action)}</select>`)}
      ${field("quantity", "Quantity", input("quantity", row.quantity, "0.00000001"))}
      ${field("priceInput", "Execution price (optional)", input("priceInput", row.priceInput, "0.00000001", "Saved quote"))}
      ${field("fee", "Fee in account currency", input("fee", row.fee, "0"))}
    </div><p class="trade-simulator-row-error" data-simulation-error="${esc(row.id)}" role="alert" hidden></p>
  </article>`;
}

function renderTradeSimulator() {
  if (!$("tradeSimulatorRows")) return;
  const accountSelect = $("tradeSimulatorAccount");
  const selected = accountSelect.value;
  accountSelect.innerHTML = tradeSimulatorAccountOptions(selected);
  const editor = document.activeElement?.closest?.("[data-simulation-row]");
  const editing = editor ? { id: editor.dataset.simulationRow, field: document.activeElement.dataset.simulationField } : null;
  $("tradeSimulatorRows").innerHTML = tradeSimulatorRows.length
    ? tradeSimulatorRows.map(tradeSimulatorRowHtml).join("")
    : `<p class="empty compact-empty">${esc(t("Add trades to compare account cash, value and risk together."))}</p>`;
  if (editing) [...$("tradeSimulatorRows").querySelectorAll("[data-simulation-row]")]
    .find((row) => row.dataset.simulationRow === editing.id)?.querySelector(`[data-simulation-field="${editing.field}"]`)?.focus({ preventScroll: true });
  $("tradeSimulatorCount").textContent = t("Trades in scenario: {count}").replace("{count}", tradeSimulatorRows.length);
  $("addTradeSimulatorRow").disabled = tradeSimulatorRows.length >= 100;
  $("tradeSimulatorAccountNotice").hidden = (state.localAccounts || []).some((account) => String(account.type).toUpperCase() === "INVESTMENT");
  renderTradeSimulatorResult();
}

function tradeSimulatorSnapshotHtml(snapshot, currency) {
  const cash = (value) => Number.isFinite(value) ? `<bdi>${esc(money(value, currency))}</bdi>` : esc(t("Not available"));
  const fact = (label, value) => `<div><dt>${esc(t(label))}</dt><dd>${value}</dd></div>`;
  return `<dl class="trade-simulator-facts">
    ${fact("Recorded cash", cash(snapshot?.cash))}
    ${fact("Net account value", cash(snapshot?.netValue))}
    ${fact("Gross security exposure", cash(snapshot?.grossExposure))}
    ${fact("Short exposure", cash(snapshot?.shortExposure))}
    ${fact("Available cash estimate", snapshot?.availableCash === null ? esc(t("Buying power unverified")) : cash(snapshot?.availableCash))}
    ${fact("Risk", snapshot?.risk ? riskBadge(snapshot.risk) : esc(t("Not available")))}
  </dl>${snapshot?.reason ? `<p class="signal-missing">${esc(tradeSimulatorReason(snapshot.reason))}</p>` : ""}`;
}

function renderTradeSimulatorResult() {
  const panel = $("tradeSimulatorResults");
  if (!panel) return;
  const loading = tradeSimulatorView?.status === "loading";
  $("runTradeSimulator").disabled = loading || !tradeSimulatorRows.length;
  $("clearTradeSimulator").disabled = !tradeSimulatorRows.length;
  panel.setAttribute("aria-busy", String(loading));
  $("tradeSimulatorRows").querySelectorAll("[data-simulation-error]").forEach((node) => { node.hidden = true; node.textContent = ""; });
  if (!tradeSimulatorView) { panel.innerHTML = ""; return; }
  if (loading) { panel.innerHTML = `<p role="status">${esc(t("Calculating combined account cash and risk…"))}</p>`; return; }
  if (tradeSimulatorView.status === "stale") { panel.innerHTML = `<p role="status">${esc(t("Scenario or portfolio inputs changed. Simulate again to update the results."))}</p>`; return; }
  if (tradeSimulatorView.status === "error") { panel.innerHTML = `<p role="alert">${esc(t("Could not calculate the simulation. Your trades are kept. Try again."))}</p>`; return; }
  const result = tradeSimulatorView.result;
  const errors = result.errors || [];
  for (const error of errors) {
    const node = [...$("tradeSimulatorRows").querySelectorAll("[data-simulation-error]")].find((node) => node.dataset.simulationError === String(error.rowId));
    if (node) { node.hidden = false; node.textContent += `${node.textContent ? " " : ""}${tradeSimulatorReason(error.reason)}`; }
  }
  if (result.status !== "ok") { panel.innerHTML = `<p role="alert">${esc(t("Review the highlighted trades and simulate again."))}</p><ul>${errors.map((error) => `<li>${esc(tradeSimulatorReason(error.reason))}</li>`).join("")}</ul>`; return; }
  const comparison = (label, before, after, currency, total = false) => `<article class="trade-simulator-comparison${total ? " trade-simulator-total" : ""}"><h3>${esc(label)} <small>${esc(currencyDisplayLabel(currency))}</small></h3><div class="trade-simulator-before-after"><section><h4>${esc(t("Before"))}</h4>${tradeSimulatorSnapshotHtml(before, currency)}</section><section><h4>${esc(t("After"))}</h4>${tradeSimulatorSnapshotHtml(after, currency)}</section></div></article>`;
  const warnings = (result.warnings || []).map((warning) => `<li>${warning.symbol ? `<bdi dir="ltr">${esc(warning.symbol)}</bdi>: ` : ""}${esc(tradeSimulatorReason(warning.reason))}${warning.date ? ` · <bdi>${esc(formatDate(warning.date))}</bdi>` : ""}</li>`).join("");
  const accountNames = new Map((result.accounts || []).map((entry) => [String(entry.account.id), tradePlannerAccountName(entry.account)]));
  panel.innerHTML = `<p role="status">${esc(t("Scenario calculated. Your recorded portfolio is unchanged."))}</p>
    ${result.total ? comparison(t("All accounts total"), result.total.before, result.total.after, result.baseCurrency, true) : ""}
    ${(result.accounts || []).map((entry) => comparison(tradePlannerAccountName(entry.account), entry.before, entry.after, entry.account.currency)).join("")}
    <details class="trade-simulator-execution"><summary>${esc(t("Trade calculations"))}</summary><ol>${(result.trades || []).map((trade) => `<li><bdi dir="ltr">${esc(trade.symbol)}</bdi> · <bdi>${esc(accountNames.get(String(trade.accountId)) || t("Account"))}</bdi> · ${esc(t({ BUY: "Buy", SELL: "Sell", SHORT: "Short" }[trade.action]))} · <bdi>${esc(fmt(Number(trade.quantity), 8))}</bdi> · ${esc(t(trade.priceDate ? "Execution price" : "User-entered execution price"))}: <bdi>${esc(money(trade.price, trade.currency))}</bdi>${trade.priceDate ? ` · ${esc(t("Saved quote date"))}: <bdi>${esc(formatDate(trade.priceDate))}</bdi>` : ""} · ${esc(t("Cash change"))}: <bdi>${esc(money(trade.cashImpact, trade.currency))}</bdi></li>`).join("")}</ol></details>
    ${warnings ? `<ul class="signal-missing">${warnings}</ul>` : ""}
    ${result.refreshPending ? `<p class="signal-missing">${esc(t("Analytics are updating. Simulate again after the update for the latest saved data."))}</p>` : ""}
    <p class="trade-plan-note">${esc(t("Calculated"))}: <bdi>${esc(formatDateTime(result.calculatedAt))}</bdi></p>`;
}

async function calculateTradeSimulation() {
  if (!tradeSimulatorRows.length || tradeSimulatorView?.status === "loading") return;
  const version = ++tradeSimulatorVersion;
  const trades = tradeSimulatorRows.map((row) => ({ ...row }));
  tradeSimulatorView = { status: "loading" };
  renderTradeSimulatorResult();
  try {
    const context = await api("/api/trade-simulator/context", { method: "POST", body: JSON.stringify({ securities: trades.map((row) => ({ symbol: row.symbol, stock_market: row.market })) }) });
    if (version !== tradeSimulatorVersion) return;
    const result = window.PortfolioTradeSimulator.simulate(context, trades, { risk: riskScoreForItems, horizon: accountHorizonYears, derivative: derivativeHolding });
    tradeSimulatorView = { status: "ready", result };
  } catch {
    if (version !== tradeSimulatorVersion) return;
    tradeSimulatorView = { status: "error" };
  }
  renderTradeSimulatorResult();
}

document.addEventListener("submit", (event) => {
  if (event.target.id !== "tradeSimulatorForm") return;
  event.preventDefault();
  if (!event.target.reportValidity()) return;
  if (tradeSimulatorRows.length >= 100) return;
  tradeSimulatorRows.push({ id: String(tradeSimulatorNextId++), accountId: $("tradeSimulatorAccount").value,
    symbol: $("tradeSimulatorSymbol").value.trim().toUpperCase(), market: $("tradeSimulatorMarket").value.trim().toUpperCase(),
    action: $("tradeSimulatorAction").value, quantity: $("tradeSimulatorQuantity").value,
    priceInput: $("tradeSimulatorPrice").value, fee: $("tradeSimulatorFee").value });
  invalidateTradeSimulator();
  renderTradeSimulator();
  $("tradeSimulatorSymbol").focus();
});
document.addEventListener("input", (event) => {
  const rowNode = event.target.closest?.("[data-simulation-row]");
  if (!rowNode || !event.target.dataset.simulationField) return;
  const row = tradeSimulatorRows.find((row) => row.id === rowNode.dataset.simulationRow);
  if (!row) return;
  row[event.target.dataset.simulationField] = event.target.value;
  invalidateTradeSimulator();
});
document.addEventListener("change", (event) => {
  const rowNode = event.target.closest?.("[data-simulation-row]");
  if (!rowNode || !event.target.dataset.simulationField) return;
  const row = tradeSimulatorRows.find((row) => row.id === rowNode.dataset.simulationRow);
  if (!row) return;
  row[event.target.dataset.simulationField] = event.target.value;
  invalidateTradeSimulator();
});
document.addEventListener("click", (event) => {
  if (event.target.closest?.("#runTradeSimulator")) calculateTradeSimulation();
  if (event.target.closest?.("#clearTradeSimulator")) { resetTradeSimulator(); $("tradeSimulatorSymbol")?.focus(); }
  const remove = event.target.closest?.("[data-simulation-remove]");
  const duplicate = event.target.closest?.("[data-simulation-duplicate]");
  if (!remove && !duplicate) return;
  if (remove) tradeSimulatorRows = tradeSimulatorRows.filter((row) => row.id !== remove.dataset.simulationRemove);
  let duplicatedId = null;
  if (duplicate && tradeSimulatorRows.length < 100) { const row = tradeSimulatorRows.find((row) => row.id === duplicate.dataset.simulationDuplicate); if (row) { duplicatedId = String(tradeSimulatorNextId++); tradeSimulatorRows.push({ ...row, id: duplicatedId }); } }
  invalidateTradeSimulator();
  renderTradeSimulator();
  if (duplicatedId) [...$("tradeSimulatorRows").querySelectorAll("[data-simulation-row]")].find((row) => row.dataset.simulationRow === duplicatedId)?.querySelector('[data-simulation-field="accountId"]')?.focus();
  else $("runTradeSimulator")?.focus();
});
