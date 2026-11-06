/* Presentation of existing rule matches and portfolio-risk-v2 assessments. */
const ALARM_PRIORITY = Object.freeze({ red: 0, amber: 1, green: 2, blue: 3, purple: 4, neutral: 5 });

function alarmAppearance(alarm) {
  if (alarm.kind === "signal") {
    const appearance = {
    sell: { tone: "red", icon: "↓", label: "Sell signal" },
    buy: { tone: "green", icon: "↑", label: "Buy signal" },
    watch: { tone: "amber", icon: "◇", label: "Watch signal" },
    }[alarm.signalType];
    return alarm.incomplete && alarm.signalType !== "sell" ? { ...appearance, tone: "amber", icon: "?" } : appearance;
  }
  if (alarm.kind === "risk") return {
    high: { tone: "red", icon: "!", label: "High risk" },
    extreme: { tone: "red", icon: "!", label: "Extreme risk" },
    elevated: { tone: "amber", icon: "▲", label: "Elevated risk" },
    borrowing: { tone: "amber", icon: "!", label: "Modeled borrowing" },
    limited: { tone: "amber", icon: "?", label: "Limited risk data" },
    unavailable: { tone: "amber", icon: "?", label: "Risk assessment unavailable" },
    updating: { tone: "amber", icon: "↻", label: "Risk assessment updating" },
  }[alarm.level];
  if (alarm.kind === "vesting") return { tone: "purple", icon: "◷", label: "Upcoming vesting" };
  if (alarm.tone === "unconfirmed") return { tone: "amber", icon: "?", label: "Dividend payment unconfirmed" };
  return alarm.event?.status === "pending"
    ? { tone: "blue", icon: "◷", label: "Scheduled dividend" }
    : { tone: "green", icon: "✓", label: "Payment recorded" };
}

function portfolioSignalAlarms() {
  const dismissals = (state.alertClientDismissals || []).filter((entry) => Date.parse(entry.expires_at) > Date.now());
  const groups = new Map();
  for (const signal of state.alertData?.active_signals || []) {
    const symbol = String(signal.symbol || "").trim().toUpperCase();
    const signalType = ["buy", "sell", "watch"].includes(signal.signal) ? signal.signal : "watch";
    if (!symbol || dismissals.some((entry) => entry.symbol === symbol && entry.signal === signalType)) continue;
    // The rule engine identifies signals by symbol and type, including dismissal.
    const key = `${symbol}|${signalType}`;
    if (!groups.has(key)) groups.set(key, { kind: "signal", key, symbol, signalType, matches: [] });
    groups.get(key).matches.push(signal);
  }
  return [...groups.values()].map((alarm) => ({ ...alarm,
    incomplete: alarm.matches.some((match) => match.missing?.length || match.missing_metrics?.length),
    title: alarm.symbol,
    body: alarmText("Matched rules: {count}. Review the evidence before deciding.", { count: new Set(alarm.matches.map((match) => match.rule_id || match.rule_name || "unassigned")).size }),
    meta: [t("View signals"), ...new Set(alarm.matches.map((match) => match.rule_name).filter(Boolean))].join(" · "),
  }));
}

function portfolioRiskAlarms() {
  if (!state.portfolioReady) return [];
  const notice = (level, body) => [{ kind: "risk", key: "risk:assessment", level,
    title: t("Total portfolio risk"), body: t(body), meta: t("View risk details") }];
  if (state.portfolioRefreshPending) return notice("updating", "Risk inputs are still updating. A complete assessment is not available yet.");
  if (state.portfolioSourceState !== "ready") return notice("unavailable", "The latest analytics update is incomplete. Refresh the portfolio to retry.");
  const items = portfolioItems(state.allPortfolioItems || []);
  const accounts = portfolioAccounts();
  const invalid = items.some((item) => {
    const holding = item.holding || {};
    // Manual listings have no provider analytics_state. As on the server,
    // absence is ready once the complete portfolio source is ready.
    return (item.analytics_state !== undefined && item.analytics_state !== "ready")
      || typeof holding.quantity !== "number" || !Number.isFinite(holding.quantity)
      || typeof holding.market_value !== "number" || !Number.isFinite(holding.market_value)
      || (holding.quantity !== 0 && holding.market_value === 0)
      || checkedAccountShareAmount(holding.market_value, holding.currency) === null;
  }) || accounts.some((account) => typeof account.initial_cash !== "number" || !Number.isFinite(account.initial_cash)
    || checkedAccountShareAmount(accountCashBalance(account), account.currency) === null);
  if (invalid) return notice("unavailable", "Complete missing valuations, quantities or currency conversion data before assessing risk.");
  const snapshot = portfolioRiskSnapshot(items);
  const scopes = [{ key: "total", label: t("Total portfolio risk"), risk: snapshot.total },
    ...snapshot.accounts.map((entry) => ({ key: entry.key, label: entry.account, risk: entry.risk }))];
  if (scopes.some(({ risk }) => typeof risk?.score !== "number" || !Number.isFinite(risk.score) || risk.score < 0 || risk.score > 100)) {
    return notice("unavailable", "Complete missing valuations, quantities or currency conversion data before assessing risk.");
  }
  const warnings = scopes.flatMap(({ key, label, risk }) => {
    const band = riskBand(risk.score);
    const level = ["high", "extreme", "elevated"].includes(band.key) ? band.key
      : key !== "total" && Number.isFinite(risk.cash_debt) && risk.cash_debt > 0 ? "borrowing" : "";
    if (!level) return [];
    return [{ kind: "risk", key: `risk:${key}`, level, risk, title: label,
      body: alarmText("Existing risk model: {score}/100. Review the contributing factors.", { score: risk.score }),
      meta: t("View risk details") }];
  });
  if (snapshot.total.quality_details?.length || snapshot.total.components?.data_quality > 0) {
    warnings.push({ kind: "risk", key: "risk:quality", level: "limited", risk: snapshot.total,
      title: t("Total portfolio risk"), body: t("Some model inputs are missing. The calculated score uses the existing data-quality penalty."), meta: t("View risk details") });
  }
  return warnings;
}

function alarmSourceNotes() {
  const notes = [];
  if (state.alarmsLoadFailed) notes.push(t("Event notices could not be updated. Available results are shown; reopen Alarms to retry."));
  if (state.alarmSignalsLoadFailed) notes.push(t("Trading signals could not be updated. Available results are shown; reopen Alarms to retry."));
  if (state.portfolioAlarmLoadFailed) notes.push(t("The portfolio assessment could not be updated. Available results are shown; use Refresh to retry."));
  if (state.alarmsEventsLoaded === false || state.alertData === null || state.portfolioReady === false) notes.push(t("Some alarm sources are still loading."));
  return notes;
}

function renderAlarmPriority(alarms) {
  renderAlarmClearControls(alarms);
  const grouped = new Map();
  for (const alarm of alarms) {
    const appearance = alarmAppearance(alarm);
    const key = appearance.label;
    if (!grouped.has(key)) grouped.set(key, { ...appearance, count: 0, limited: false });
    const group = grouped.get(key);
    group.count += 1;
    group.limited ||= Boolean(alarm.incomplete);
    if (ALARM_PRIORITY[appearance.tone] < ALARM_PRIORITY[group.tone]) {
      group.tone = appearance.tone;
      group.icon = appearance.icon;
    }
  }
  const groups = [...grouped.values()].sort((a, b) => ALARM_PRIORITY[a.tone] - ALARM_PRIORITY[b.tone]);
  const notes = alarmSourceNotes();
  const tone = notes.length && (!groups.length || ALARM_PRIORITY[groups[0].tone] > ALARM_PRIORITY.amber) ? "amber" : groups[0]?.tone || "neutral";
  const description = [alarmText("Alarms: {count}", { count: alarms.length }),
    ...groups.map((group) => `${t(group.label)}: ${group.count}${group.limited ? ` · ${t("Some rule data is unavailable")}` : ""}`), ...notes].join(" · ");
  const button = $("alarmsButton");
  if (button) {
    button.dataset.alarmTone = tone;
    button.title = description;
    button.setAttribute("aria-label", description);
  }
  const symbol = $("alarmsPrioritySymbol");
  if (symbol) symbol.textContent = tone === "red" ? "!" : tone === "amber" ? "?" : groups[0]?.icon || "";
  const summary = $("alarmPrioritySummary");
  if (summary) summary.innerHTML = groups.map((group) => `<span class="alarm-summary-chip" data-alarm-tone="${group.tone}"><span aria-hidden="true">${esc(group.icon)}</span>${esc(t(group.label))}${group.limited ? ` · ${esc(t("Limited data"))}` : ""}<b>${group.count}</b></span>`).join("");
  return notes;
}

function alarmStableEvidence(value) {
  if (Array.isArray(value)) return value.map(alarmStableEvidence).sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map((key) => [key, alarmStableEvidence(value[key])]));
  return typeof value === "number" && !Number.isFinite(value) ? String(value) : value;
}

function alarmModelEvidence(value) {
  // Model summation can differ by floating-point noise after an order-only
  // change. Normalize computed values only; raw financial inputs stay exact.
  if (typeof value === "number" && Number.isFinite(value)) return Number(value.toPrecision(12));
  if (Array.isArray(value)) return value.map(alarmModelEvidence);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, alarmModelEvidence(item)]));
  return value;
}

function riskAlarmDismissalId(alarm) {
  // Preserve financial evidence, including changes hidden by a rounded score.
  // Localized copy, fetch timestamps and presentation order are not evidence.
  const holdings = portfolioItems(state.allPortfolioItems || []).map((item) => {
    const h = item.holding || {};
    return {
      holding: Object.fromEntries(["account_id", "symbol", "stock_market", "currency", "asset_class", "quantity", "market_value", "cost_basis", "country", "sector", "issuer"].map((key) => [key, h[key]])),
      value: checkedAccountShareAmount(h.market_value, h.currency),
      analytics_state: item.analytics_state, missing: item.missing || [],
      industry: industryLabel(item), country: countryLabel(item), issuer: issuerLabel(item),
      asset_factor: assetRiskFactor(item), volatility: volatilityProxy(item),
      exposure: item.exposure_profile ? Object.fromEntries(["asset_focus", "geography", "sector_exposure", "fx_basis", "fx_reference_currency", "currency_exposures", "fx_policy_limit_percent", "as_of"].map((key) => [key, item.exposure_profile[key]])) : null,
    };
  });
  const accounts = portfolioAccounts().map((account) => ({ id: account.id, currency: account.currency,
    initial_cash: account.initial_cash, cash: accountCashBalance(account),
    converted_cash: checkedAccountShareAmount(accountCashBalance(account), account.currency),
    horizon: accountHorizonYears(account) }));
  const risk = alarm.risk || {};
  const evidence = JSON.stringify(alarmStableEvidence({ key: alarm.key, level: alarm.level,
    source_state: state.portfolioSourceState, pending: Boolean(state.portfolioRefreshPending),
    model: alarmModelEvidence({ score: risk.score, components: risk.components, quality_details: risk.quality_details,
      cash_debt: risk.cash_debt, net_equity: risk.net_equity, unlevered_score: risk.unlevered_score }),
    base_currency: state.baseCurrency, holdings, accounts }));
  // Two independent 32-bit accumulators keep local dismissal IDs compact.
  let first = 2166136261, second = 5381;
  for (let index = 0; index < evidence.length; index += 1) {
    first = Math.imul(first ^ evidence.charCodeAt(index), 16777619);
    second = Math.imul(second, 33) ^ evidence.charCodeAt(index);
  }
  const userId = state.auth?.user?.id ?? state.auth?.user?.username ?? "anonymous";
  return `${alarm.key}:user:${userId}:${(first >>> 0).toString(36)}${(second >>> 0).toString(36)}`;
}

function visiblePriorityAlarms() {
  const dismissed = new Set(state.dismissedAlarmIds || []);
  return [...portfolioSignalAlarms(), ...portfolioRiskAlarms().map((alarm) => ({ ...alarm, dismissalId: riskAlarmDismissalId(alarm) }))]
    .filter((alarm) => alarm.kind !== "risk" || !dismissed.has(alarm.dismissalId));
}

function displayedAlarms() {
  const { dividends, vesting } = currentAlarms();
  return [...vesting, ...dividends, ...visiblePriorityAlarms()];
}

function alarmClearKey(alarm) {
  return alarm.kind === "signal" ? `signal:${alarm.key}` : alarm.kind === "risk" ? alarm.dismissalId : alarmDismissalId(alarm);
}

function alarmMatchesClearSelection(alarm) {
  const appearance = alarmAppearance(alarm);
  return (!$("alarmClearColor")?.value || appearance.tone === $("alarmClearColor").value)
    && (!$("alarmClearType")?.value || appearance.label === $("alarmClearType").value);
}

function renderAlarmClearControls(alarms) {
  const colors = { red: "Red", amber: "Amber", green: "Green", blue: "Blue", purple: "Purple", neutral: "Gray" };
  for (const [id, field, emptyLabel] of [["alarmClearColor", "tone", "Any color"], ["alarmClearType", "label", "All types"]]) {
    const select = $(id);
    if (!select) continue;
    const previous = select.value;
    const counts = new Map();
    alarms.forEach((alarm) => { const key = alarmAppearance(alarm)[field]; counts.set(key, (counts.get(key) || 0) + 1); });
    // Keep a selected category after its last alarm is cleared so the action
    // never silently broadens to all remaining alarms.
    if (previous && !counts.has(previous)) counts.set(previous, 0);
    const html = `<option value="">${esc(t(emptyLabel))}</option>` + [...counts.entries()].map(([key, count]) =>
      `<option value="${esc(key)}">${esc(alarmText("{label} ({count})", { label: t(field === "tone" ? colors[key] : key), count }))}</option>`).join("");
    if (select.innerHTML !== html) { select.innerHTML = html; select.value = previous; }
    select.disabled = Boolean(state.alarmClearPending);
  }
  const disabled = !canWrite() || Boolean(state.alarmClearPending);
  if ($("clearMatchingAlarms")) $("clearMatchingAlarms").disabled = disabled || !alarms.some(alarmMatchesClearSelection);
  if ($("clearAlarms")) $("clearAlarms").disabled = disabled || !alarms.length;
  if ($("alarmClearStatus")) $("alarmClearStatus").textContent = state.alarmClearMessage
    ? alarmText(state.alarmClearMessage.template, state.alarmClearMessage.values) : "";
}

function renderAlarmListItem(alarm) {
  const appearance = alarmAppearance(alarm);
  const incomplete = alarm.incomplete ? ` · ${t("Some rule data is unavailable")}` : "";
  const clearLabel = alarmText("Clear alarm: {title} · {type}", { title: alarm.title, type: t(appearance.label) });
  return `<div class="alarm-entry" data-alarm-tone="${appearance.tone}">
    <button class="alarm-item" data-alarm-tone="${appearance.tone}" type="button" ${alarmActionAttributes(alarm)}>
      <span class="alarm-heading"><b>${esc(alarm.title)}</b><span class="alarm-kind"><span aria-hidden="true">${esc(appearance.icon)}</span> ${esc(t(appearance.label))}</span></span>
      <span class="alarm-details"><span class="alarm-body">${esc(alarm.body)}${esc(incomplete)}</span><small class="alarm-meta">${esc(alarm.meta)}</small></span>
    </button>
    <button class="icon-button alarm-clear-one" type="button" data-clear-alarm="${esc(alarmClearKey(alarm))}" aria-label="${esc(clearLabel)}" title="${esc(clearLabel)}"${!canWrite() || state.alarmClearPending ? " disabled" : ""}>×</button>
  </div>`;
}

async function clearSelectedAlarms({ all = false, key = "" } = {}) {
  if (!canWrite() || state.alarmClearPending) return;
  const userId = state.auth?.user?.id;
  const csrfToken = state.auth?.csrfToken;
  const sameSession = () => state.auth?.user?.id === userId && state.auth?.csrfToken === csrfToken;
  const selected = displayedAlarms().filter((alarm) => key ? alarmClearKey(alarm) === key : all || alarmMatchesClearSelection(alarm));
  if (!selected.length) return;
  const focused = document.activeElement;
  const clearControls = [...($("alarmsList")?.querySelectorAll?.("[data-clear-alarm]") || [])];
  const focusedIndex = clearControls.indexOf(focused);
  const adjacentKeys = focusedIndex < 0 ? [] : [...clearControls.slice(focusedIndex + 1), ...clearControls.slice(0, focusedIndex).reverse()]
    .map((button) => button.dataset.clearAlarm);
  const restoreFocus = $("alarmsModal")?.contains(focused);
  state.alarmClearPending = true;
  state.alarmClearMessage = { template: "Clearing alarms…", values: {} };
  renderAlarms();
  let cleared = 0, failed = 0;
  try {
    const local = selected.filter((alarm) => alarm.kind !== "signal");
    if (local.length) {
      const previous = [...(state.dismissedAlarmIds || [])];
      state.dismissedAlarmIds = [...new Set([...previous, ...local.map(alarmClearKey)])];
      try { saveAlarmDismissals(); cleared += local.length; }
      catch { state.dismissedAlarmIds = previous; failed += local.length; }
    }
    // The established dismissal API owns permission, TTL and persistence.
    // Serialize calls because each response contains a full saved-signal state.
    for (const alarm of selected.filter((entry) => entry.kind === "signal")) {
      if (!sameSession()) return;
      try {
        await dismissAlertSignal(alarm.symbol, alarm.signalType);
        if (!sameSession()) return;
        if (portfolioSignalAlarms().some((entry) => entry.key === alarm.key)) failed += 1;
        else cleared += 1;
      } catch { failed += 1; }
    }
    if (!sameSession()) return;
    state.clearedAlarmCount = cleared;
    state.alarmClearMessage = { template: failed ? "Cleared {count} alarms. {failed} could not be cleared; try again." : "Cleared {count} alarms.", values: { count: cleared, failed } };
  } finally {
    if (sameSession()) {
      state.alarmClearPending = false;
      renderAlarms();
      if (restoreFocus && !$("alarmsModal").hidden && !$("alarmsModal").inert
        && (!document.activeElement || document.activeElement === document.body || !document.activeElement.isConnected)) {
        const replacement = focused?.dataset?.clearAlarm
          ? [...$("alarmsList").querySelectorAll("[data-clear-alarm]")].find((button) => button.dataset.clearAlarm === focused.dataset.clearAlarm) : null;
        const remaining = [...($("alarmsList")?.querySelectorAll?.("[data-clear-alarm]") || [])];
        const adjacent = adjacentKeys.map((candidate) => remaining.find((button) => button.dataset.clearAlarm === candidate && !button.disabled)).find(Boolean);
        (replacement || adjacent || (focused?.isConnected && !focused.disabled ? focused : $("alarmClearStatus")))?.focus({ preventScroll: true });
      }
    }
  }
}

if (typeof document !== "undefined") document.addEventListener("change", (event) => {
  if (["alarmClearColor", "alarmClearType"].includes(event.target.id)) renderAlarmClearControls(displayedAlarms());
});
if (typeof document !== "undefined") document.addEventListener("click", (event) => {
  const control = event.target.closest("[data-clear-alarm], #clearMatchingAlarms");
  if (!control) return;
  clearSelectedAlarms({ key: control.dataset.clearAlarm || "" }).catch(() => {
    state.alarmClearMessage = { template: "Alarms could not be cleared. Try again.", values: {} };
    renderAlarms();
  });
});

function alarmActionAttributes(alarm) {
  if (alarm.kind === "signal") return `data-open-signal-alarm="${esc(alarm.symbol)}" data-alarm-signal-type="${esc(alarm.signalType)}"`;
  if (alarm.kind === "risk") return `data-open-risk-alarm="${esc(alarm.key)}"`;
  if (alarm.kind === "vesting") return `data-open-vesting-alarm="${esc(alarm.transactionId)}"`;
  return `data-open-dividend-alarm="${esc(alarm.event.id)}"`;
}

function openSignalAlarm(symbol, signalType) {
  closeModal($("alarmsModal"));
  setResearchSection("signals");
  state.alertRuleFilter = "";
  if (state.alertData) renderAlerts(state.alertData, { signalsOnly: true });
  openModal("researchModal", $("alarmsButton"));
  requestAnimationFrame(() => {
    const card = [...$("alertsSignals").querySelectorAll("[data-alert-chart]")].find((button) => button.dataset.alertChart === symbol && button.closest(`.signal-${signalType}`))?.closest(".signal-card");
    card?.scrollIntoView({ block: "nearest" });
    card?.querySelector("button")?.focus({ preventScroll: true });
  });
}

function openRiskAlarm(key) {
  const alarm = portfolioRiskAlarms().find((item) => item.key === key);
  if (!alarm) { renderAlarms(); return; }
  renderAlarmRiskDetails(alarm);
  openModal("alarmRiskModal", document.activeElement);
  $("alarmRiskModal").dataset.alarmKey = key;
  $("alarmRiskModal").dataset.parentModalId = "alarmsModal";
  $("alarmsModal").inert = true;
  $("alarmsModal").setAttribute("aria-hidden", "true");
  requestAnimationFrame(() => $("alarmRiskModal").querySelector("button[data-close]")?.focus({ preventScroll: true }));
}

function renderAlarmRiskDetails(alarm) {
  const data = $("alarmRiskData");
  const restore = typeof preserveRenderedInteraction === "function" ? preserveRenderedInteraction(data) : () => {};
  if (!alarm) {
    $("alarmRiskTitle").textContent = t("Risk details");
    const current = portfolioRiskAlarms().find((entry) => entry.key === $("alarmRiskModal")?.dataset.alarmKey);
    const cleared = current && (state.dismissedAlarmIds || []).includes(riskAlarmDismissalId(current));
    $("alarmRiskDetails").textContent = t(cleared ? "This risk warning has been cleared for the current assessment." : "This risk warning no longer applies to the current assessment.");
    data.innerHTML = "";
    return;
  }
  $("alarmRiskTitle").textContent = alarm.title;
  $("alarmRiskDetails").textContent = alarm.risk
    ? `${alarm.body}\n\n${riskTooltip(alarm.risk)}` : alarm.body;
  data.innerHTML = alarm.risk && typeof riskDataQualityHtml === "function" ? riskDataQualityHtml(alarm.risk) : "";
  restore();
}
