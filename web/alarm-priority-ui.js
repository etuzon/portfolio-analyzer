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
    $("alarmRiskDetails").textContent = t("This risk warning no longer applies to the current assessment.");
    data.innerHTML = "";
    return;
  }
  $("alarmRiskTitle").textContent = alarm.title;
  $("alarmRiskDetails").textContent = alarm.risk
    ? `${alarm.body}\n\n${riskTooltip(alarm.risk)}` : alarm.body;
  data.innerHTML = alarm.risk && typeof riskDataQualityHtml === "function" ? riskDataQualityHtml(alarm.risk) : "";
  restore();
}
