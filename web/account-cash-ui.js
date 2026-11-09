/* Local current-cash reconciliation. The server owns cash and ledger rules. */
function accountCashUi() {
  const owner = currentUser()?.id, token = state.auth?.csrfToken;
  if (!state.accountCash || state.accountCash.owner !== owner || state.accountCash.token !== token) {
    state.accountCash = { owner, token, accountId: "", context: null, loading: false, saving: false, saved: false,
      draft: "", pendingRequest: null, needsReview: false, message: "", returnFocus: null, entry: "" };
  }
  return state.accountCash;
}

function accountCashSessionActive(ui) {
  return state.accountCash === ui && currentUser()?.id === ui.owner && state.auth?.csrfToken === ui.token;
}

function accountCashSaving() {
  const ui = state.accountCash;
  return Boolean(ui && accountCashSessionActive(ui) && ui.saving);
}

function accountCashSummaryHtml(account, { button = true, compact = false, entry = "accounts" } = {}) {
  if (!account) return "";
  const value = accountNativeCashBalance(account);
  const tone = value === null ? "unavailable" : value > 0 ? "positive" : value < 0 ? "negative" : "zero";
  const amount = value === null ? t("Not available") : money(value, account.currency, 2);
  const name = accountLabel(account);
  const label = `${esc(t("Current cash"))}:`;
  const balance = `<bdi dir="ltr">${esc(amount)}</bdi>`;
  const editable = button && canWrite();
  const content = editable
    ? `<button class="account-cash-edit ux-tooltip" type="button" data-update-account-cash="${esc(account.id)}" data-cash-entry="${esc(entry)}" aria-label="${esc(`${t("Update cash for {account}").replace("{account}", name)}. ${t("Current cash")}: ${amount}`)}" aria-haspopup="dialog" aria-controls="accountCashModal" title="" data-tooltip="${esc(t("Update cash"))}"><span class="account-cash-label">${label}</span><span class="account-cash-value">${balance}</span></button>`
    : `<span class="account-cash-readonly">${label} ${balance}</span>`;
  return `<span class="account-current-cash cash-${tone}${compact ? " account-current-cash-compact" : ""}">${content}</span>`;
}

function renderAccountEditCash(account) {
  const root = $("editAccountCash");
  if (root) root.innerHTML = accountCashSummaryHtml(account, { entry: "edit" });
}

function accountCashReturnFocus() {
  const ui = state.accountCash;
  if (!ui) return null;
  if (ui.returnFocus?.isConnected) return ui.returnFocus;
  return [...document.querySelectorAll("[data-update-account-cash]")].find((button) =>
    button.dataset.updateAccountCash === ui.accountId && button.dataset.cashEntry === ui.entry && button.getClientRects().length) || null;
}

function accountCashReason(reason) {
  return t({
    missing_account_currency: "Set the account currency before updating cash.",
    invalid_initial_cash: "The opening cash balance is unknown. Correct it in Edit account before updating current cash.",
    invalid_cash_transaction_date: "A cash-affecting entry has an invalid date. Correct the entry before updating cash.",
    future_cash_transactions: "Future cash-affecting entries prevent a current cash adjustment. Review their dates first.",
    mixed_cash_currencies: "Cash entries in different currencies cannot establish a single-currency balance. Reconcile the entries first.",
    invalid_cash_transaction: "A cash-affecting entry has an invalid amount. Correct the entry before updating cash.",
    cash_revision_conflict: "The account cash changed. Reload current cash and review your target before saving again.",
    request_id_conflict: "This update request conflicts with an earlier request. Reload current cash and review your target.",
    invalid_target_cash: "Enter a finite cash amount. Zero and negative balances are allowed.",
    invalid_request_id: "This update request could not be validated. Reload current cash and try again.",
  }[reason] || "Current cash could not be established. Review the account and its cash entries, then reload.");
}

function renderAccountCash() {
  const ui = accountCashUi(), context = ui.context;
  const busy = ui.loading || ui.saving;
  const available = context?.available === true && Number.isFinite(context.cash) && Boolean(context.currency) && Boolean(context.cash_revision);
  $("accountCashCurrent").textContent = available ? money(context.cash, context.currency, 2) : t("Not available");
  $("accountCashCurrency").value = context?.currency || "";
  $("accountCashDate").value = context?.effective_date ? formatDate(context.effective_date) : "";
  const input = $("accountCashTarget");
  if (input.value !== ui.draft) input.value = ui.draft;
  input.disabled = !available || busy || !canWrite() || ui.needsReview || ui.saved;
  input.readOnly = Boolean(ui.pendingRequest);
  const raw = String(ui.draft).trim(), target = raw === "" ? null : Number(raw);
  const valid = target !== null && Number.isFinite(target);
  const difference = valid && available ? target - context.cash : null;
  $("accountCashDifference").textContent = available && valid
    ? t("Adjustment: {amount}").replace("{amount}", `${difference > 0 ? "+" : ""}${money(difference, context.currency, 2)}`) : t("Enter the current balance you want to record.");
  $("accountCashSave").disabled = !available || !valid || busy || !canWrite() || ui.needsReview || ui.saved;
  $("accountCashSave").textContent = t(ui.saving ? "Saving cash…" : ui.pendingRequest ? "Retry cash update" : "Save");
  $("accountCashReload").disabled = busy;
  $("accountCashModal").querySelectorAll("button[data-close]").forEach((button) => { button.disabled = ui.saving; });
  const message = ui.loading ? t("Loading current cash…") : ui.message ? typeof ui.message === "object"
    ? ui.message.reason ? accountCashReason(ui.message.reason) : t(ui.message.fallback) : t(ui.message)
    : !available && context ? accountCashReason(context.reason) : !canWrite() ? t("Cash updates require editing permission.") : "";
  $("accountCashStatus").textContent = message;
  $("accountCashForm").setAttribute("aria-busy", String(busy));
}

async function loadAccountCash({ preserveTarget = false } = {}) {
  const ui = accountCashUi();
  if (!ui.accountId || ui.saving || ui.loading) return;
  const accountId = ui.accountId, version = (ui.loadVersion || 0) + 1;
  ui.loadVersion = version;
  ui.loading = true; ui.message = "";
  renderAccountCash();
  try {
    const context = await api(`/api/local/accounts/${encodeURIComponent(accountId)}/cash-balance`);
    if (!accountCashSessionActive(ui) || ui.loadVersion !== version || ui.accountId !== accountId || $("accountCashModal").hidden) return;
    ui.context = context;
    ui.pendingRequest = null; ui.needsReview = false; ui.saved = false;
    if (!preserveTarget || ui.draft.trim() === "") ui.draft = context.available && Number.isFinite(context.cash) ? String(context.cash) : "";
    ui.message = preserveTarget && context.available ? "Current cash reloaded. Review the target and adjustment before saving." : "";
  } catch (error) {
    if (!accountCashSessionActive(ui) || ui.loadVersion !== version || ui.accountId !== accountId) return;
    ui.message = "Current cash could not be loaded. Reload current cash to retry.";
  } finally {
    if (accountCashSessionActive(ui) && ui.loadVersion === version && ui.accountId === accountId) { ui.loading = false; renderAccountCash(); }
  }
}

async function openAccountCash(accountId, returnFocus = document.activeElement) {
  if (accountCashSaving()) return;
  const account = (state.localAccounts || []).find((entry) => String(entry.id) === String(accountId));
  if (!account) return;
  const ui = accountCashUi();
  Object.assign(ui, { accountId: String(accountId), context: null, loading: false, saving: false, saved: false,
    draft: "", pendingRequest: null, needsReview: false, message: "", returnFocus,
    entry: returnFocus?.dataset?.cashEntry || "" });
  $("accountCashAccount").textContent = accountLabel(account);
  const parent = returnFocus?.closest?.(".modal:not([hidden])");
  openModal("accountCashModal", returnFocus);
  if (parent && parent.id !== "accountCashModal") {
    $("accountCashModal").dataset.parentModalId = parent.id;
    parent.inert = true; parent.setAttribute("aria-hidden", "true");
  }
  renderAccountCash();
  await loadAccountCash();
  if (accountCashSessionActive(ui) && !$("accountCashModal").hidden) {
    const target = $("accountCashTarget");
    (target.disabled ? $("accountCashStatus") : target).focus({ preventScroll: true });
    if (!target.disabled) target.select();
  }
}

async function saveAccountCash(event) {
  event?.preventDefault();
  const ui = accountCashUi(), context = ui.context;
  if (ui.saving || ui.loading || ui.saved || ui.needsReview || !canWrite() || !context?.available) return;
  const raw = String($("accountCashTarget").value).trim();
  if (!raw || !Number.isFinite(Number(raw))) {
    ui.message = !raw && !$("accountCashTarget").validity.badInput ? "Enter a cash balance." : "Enter a finite cash amount. Zero and negative balances are allowed.";
    renderAccountCash(); $("accountCashTarget").focus({ preventScroll: true }); return;
  }
  ui.draft = raw;
  if (!ui.pendingRequest) ui.pendingRequest = { target_cash: Number(raw), cash_revision: context.cash_revision, request_id: crypto.randomUUID() };
  ui.saving = true; ui.message = ""; renderAccountCash();
  try {
    const result = await api(`/api/local/accounts/${encodeURIComponent(ui.accountId)}/cash-balance`, { method: "POST", body: JSON.stringify(ui.pendingRequest) });
    if (!accountCashSessionActive(ui)) return;
    ui.context = result; ui.saved = true; ui.pendingRequest = null;
    const updates = await Promise.allSettled([loadLocalAccounts({ renderDashboard: false }), loadPortfolio()]);
    if (!accountCashSessionActive(ui)) return;
    const account = (state.localAccounts || []).find((entry) => String(entry.id) === ui.accountId);
    if (account && String(state.editingAccountId) === String(account.id)) renderAccountEditCash(account);
    if (updates.some((entry) => entry.status === "rejected")) {
      ui.message = "Cash was saved. Some displayed totals could not reload. Close and use Refresh to retry.";
    } else {
      ui.saving = false;
      const message = t("Cash updated for {account}.").replace("{account}", account ? accountLabel(account) : $("accountCashAccount").textContent);
      if ($("accountsStatus")) $("accountsStatus").textContent = message;
      if ($("status")) $("status").textContent = message;
      closeModal($("accountCashModal"));
    }
  } catch (error) {
    if (!accountCashSessionActive(ui)) return;
    if (error.status === 409) {
      ui.needsReview = true;
      ui.message = { reason: error.reason, fallback: "The account cash changed. Reload current cash and review your target before saving again." };
    } else if (error.status >= 400 && error.status < 500) {
      ui.pendingRequest = null;
      ui.message = { reason: error.reason, fallback: "Cash could not be updated. Check the entered amount and reload current cash." };
      if ([401, 403].includes(error.status) || error.reason && error.reason !== "invalid_target_cash") ui.needsReview = true;
    } else {
      ui.message = "The save outcome is unknown. Retry cash update sends the same request safely, or reload current cash before changing the target.";
    }
  } finally {
    if (accountCashSessionActive(ui)) {
      ui.saving = false;
      if (!$("accountCashModal").hidden) { renderAccountCash(); $("accountCashStatus").focus({ preventScroll: true }); }
    }
  }
}

if (typeof document !== "undefined") {
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-update-account-cash]");
    if (button && !button.disabled) openAccountCash(button.dataset.updateAccountCash, button).catch(() => {});
    if (event.target.closest("#accountCashReload")) loadAccountCash({ preserveTarget: true }).catch(() => {});
  });
  document.addEventListener("input", (event) => {
    if (event.target.id !== "accountCashTarget") return;
    const ui = accountCashUi();
    if (ui.pendingRequest || ui.saving) return;
    ui.draft = event.target.value; ui.message = ""; renderAccountCash();
  });
  document.addEventListener("submit", (event) => {
    if (event.target.id === "accountCashForm") saveAccountCash(event).catch(() => {});
  });
}
