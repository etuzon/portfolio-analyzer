const HISTORY_START_DATE = "2026-04-14";

const state = {
  items: [],
  accountTrend: { accounts: [] },
  dashboard: null,
  bannerItems: [],
  configuredBannerItems: [],
  historySnapshots: [],
  fxRates: {},
  baseCurrency: "ILS",
  localAccounts: [],
  manualSecurities: [],
  localTransactions: [],
  localPrices: [],
  priceFocus: null,
  securityDetail: null,
  securityChartPeriod: "1y",
  securityChartStartDate: HISTORY_START_DATE,
  securityHistory: [],
  localFunds: [],
  localAccountPersons: [],
  fundPersons: [],
  pensionIncomePeriods: [],
  pensionScenarios: [],
  pensionSimulationResults: [],
  localOptions: {
    account_types: ["Investment", "Long-Term Savings", "Bank"],
    fund_kinds: ["Pension", "Provident Fund", "Savings Fund"],
    asset_classes: ["EQUITY", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE"],
    instrument_types: ["STOCK", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE"],
    option_types: ["CALL", "PUT"],
  },
  optionsReady: false,
  tableMaPeriod: "30",
  backupSettings: null,
  riskSnapshot: null,
};

const $ = (id) => document.getElementById(id);

const DASHBOARD_WIDGETS = [
  { id: "account_trend", title: "Account value trend", view: "basic", size: "wide" },
  { id: "market_cost", title: "Market vs cost basis", view: "basic", size: "wide" },
  { id: "asset_mix", title: "Asset mix", view: "basic", size: "compact" },
  { id: "top_holdings", title: "Top holdings", view: "basic", size: "compact" },
  { id: "coverage", title: "Provider data coverage", view: "expanded", size: "medium" },
  { id: "currency", title: "Currency allocation", view: "expanded", size: "medium" },
  { id: "profit", title: "Unrealized P/L by holding", view: "expanded", size: "wide" },
  { id: "snapshot", title: "Portfolio snapshot", view: "expanded", size: "wide" },
];

const DASHBOARD_STORAGE_KEY = "portfolioAnalyzer.dashboard";
const DASHBOARD_ACCOUNT_STORAGE_KEY = "portfolioAnalyzer.dashboard.accountTrend";
const TABLE_SETTINGS_STORAGE_KEY = "portfolioAnalyzer.tableSettings";
const DASHBOARD_SECTIONS = [
  { view: "basic", label: "Glance" },
  { view: "expanded", label: "Full" },
  { view: "hidden", label: "Hidden" },
];

const REGION_CODES = "AF AX AL DZ AS AD AO AI AQ AG AR AM AW AU AT AZ BS BH BD BB BY BE BZ BJ BM BT BO BQ BA BW BV BR IO BN BG BF BI CV KH CM CA KY CF TD CL CN CX CC CO KM CG CD CK CR CI HR CU CW CY CZ DK DJ DM DO EC EG SV GQ ER EE SZ ET FK FO FJ FI FR GF PF TF GA GM GE DE GH GI GR GL GD GP GU GT GG GN GW GY HT HM VA HN HK HU IS IN ID IR IQ IE IM IL IT JM JP JE JO KZ KE KI KP KR KW KG LA LV LB LS LR LY LI LT LU MO MG MW MY MV ML MT MH MQ MR MU YT MX FM MD MC MN ME MS MA MZ MM NA NR NP NL NC NZ NI NE NG NU NF MK MP NO OM PK PW PS PA PG PY PE PH PN PL PT PR QA RE RO RU RW BL SH KN LC MF PM VC WS SM ST SA SN RS SC SL SG SX SK SI SB SO ZA GS SS ES LK SD SR SJ SE CH SY TW TJ TZ TH TL TG TK TO TT TN TR TM TC TV UG UA AE GB US UM UY UZ VU VE VN VG VI WF EH YE ZM ZW".split(" ");
const FALLBACK_CURRENCIES = "USD ILS EUR GBP JPY CHF CAD AUD NZD CNY HKD SGD INR KRW MXN BRL ARS CLP COP ZAR AED SAR TRY PLN CZK HUF SEK NOK DKK ISK RUB UAH RON BGN HRK RSD THB IDR MYR PHP VND TWD ILS".split(" ");
const countryNames = typeof Intl.DisplayNames === "function" ? new Intl.DisplayNames([navigator.language || "en"], { type: "region" }) : null;

function flagFor(code) {
  return code.replace(/./g, (char) => String.fromCodePoint(127397 + char.charCodeAt(0)));
}

function countryName(code) {
  try {
    return countryNames?.of(code) || code;
  } catch {
    return code;
  }
}

function currencySymbol(code) {
  try {
    const part = new Intl.NumberFormat(undefined, { style: "currency", currency: code, currencyDisplay: "narrowSymbol" })
      .formatToParts(0)
      .find((item) => item.type === "currency");
    return part?.value || code;
  } catch {
    return code;
  }
}

function bannerValueSymbol(item) {
  if (item.type === "fx") {
    const base = String(item.symbol || "").split("/")[0];
    return base ? currencySymbol(base) : "";
  }
  return item.currency ? currencySymbol(item.currency) : "";
}

function changeArrow(value) {
  const number = Number(value || 0);
  if (number > 0) return "▲";
  if (number < 0) return "▼";
  return "▬";
}

function acronym(value, max = 3) {
  const text = String(value || "").replace(/[^A-Za-z0-9 ]/g, " ").trim();
  const words = text.split(/\s+/).filter(Boolean);
  if (!words.length) return "IDX";
  if (words.length === 1) return words[0].slice(0, max).toUpperCase();
  return words.map((word) => word[0]).join("").slice(0, max).toUpperCase();
}

function indexBadge(item) {
  const text = `${item.label || ""} ${item.symbol || ""}`.toLowerCase();
  if (/(nasdaq|ixic|ndx|qqq)/.test(text)) return "NQ";
  if (/(s&p|sp500|gspc|spx|inx)/.test(text)) return "S&P";
  if (/(dow|dji|dia)/.test(text)) return "DOW";
  if (/(russell|rut|iwm)/.test(text)) return "RUT";
  if (/(vix)/.test(text)) return "VIX";
  if (/(ta-?35|tase)/.test(text)) return "TA";
  if (/(dax)/.test(text)) return "DAX";
  if (/(ftse)/.test(text)) return "FT";
  if (/(nikkei|n225)/.test(text)) return "NK";
  return acronym(item.label || item.symbol, 3);
}

function commodityIcon(item) {
  const text = `${item.label || ""} ${item.symbol || ""}`.toLowerCase();
  if (/(gold|xau|gc)/.test(text)) {
    return `<div class="instrument-icon commodity-icon commodity-gold" title="Gold">
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <circle cx="25" cy="20" r="13"></circle>
        <path d="M13 31h21l4 8H9z"></path>
        <path d="M20 16h10M18 22h14"></path>
      </svg>
    </div>`;
  }
  if (/(silver|xag|si)/.test(text)) {
    return `<div class="instrument-icon commodity-icon commodity-silver" title="Silver">
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <circle cx="24" cy="22" r="14"></circle>
        <path d="M15 35h18l3 6H12z"></path>
        <path d="M18 22h12M21 16h9"></path>
      </svg>
    </div>`;
  }
  if (/(oil|brent|wti|cl)/.test(text)) {
    return `<div class="instrument-icon commodity-icon commodity-oil" title="Oil">
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <path d="M24 6c8 10 13 17 13 25a13 13 0 0 1-26 0c0-8 5-15 13-25z"></path>
        <path d="M27 17c3 5 5 9 5 13"></path>
      </svg>
    </div>`;
  }
  if (/(gas|natural|ng)/.test(text)) {
    return `<div class="instrument-icon commodity-icon commodity-gas" title="Natural gas">
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <path d="M25 5c4 8-3 10 4 17 3-4 5-7 4-12 6 7 10 14 10 22a17 17 0 0 1-34 0c0-8 6-15 16-27z"></path>
        <path d="M24 25c4 4 6 8 6 12a6 6 0 0 1-12 0c0-4 2-8 6-12z"></path>
      </svg>
    </div>`;
  }
  if (/(copper|hg)/.test(text)) {
    return `<div class="instrument-icon commodity-icon commodity-copper" title="Copper">
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <circle cx="24" cy="19" r="12"></circle>
        <path d="M24 31v11M17 37h14"></path>
      </svg>
    </div>`;
  }
  return `<div class="instrument-icon commodity-icon commodity-generic" title="Commodity">
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <path d="M11 33h26l4 8H7z"></path>
      <path d="M16 25h16l3 8H13z"></path>
      <path d="M20 17h8l4 8H16z"></path>
    </svg>
  </div>`;
}

function bannerIconHtml(item) {
  const type = String(item.type || "").toLowerCase();
  if (type === "fx") {
    const [base, quote] = String(item.symbol || "").split("/");
    const code = base || quote || item.symbol || "";
    return `<div class="instrument-icon currency-icon" title="${esc(item.symbol || "Currency")}">
      <b>${esc(currencySymbol(code))}</b>
      <small>${esc(code)}</small>
    </div>`;
  }
  if (type === "commodity") return commodityIcon(item);
  if (type === "index") {
    const badge = indexBadge(item);
    return `<div class="instrument-icon index-icon" title="${esc(item.label || item.symbol || "Index")}">
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <path d="M9 35h30"></path>
        <path d="M11 31l8-9 7 5 11-14"></path>
        <circle cx="19" cy="22" r="2"></circle>
        <circle cx="37" cy="13" r="2"></circle>
      </svg>
      <b>${esc(badge)}</b>
    </div>`;
  }
  return `<div class="instrument-icon quote-icon" title="${esc(item.label || item.symbol || "Quote")}"><b>${esc(acronym(item.symbol || item.label, 2))}</b></div>`;
}

function currencyCodes() {
  if (Intl.supportedValuesOf) {
    try {
      return Intl.supportedValuesOf("currency");
    } catch {
      return FALLBACK_CURRENCIES;
    }
  }
  return FALLBACK_CURRENCIES;
}

function preferredCurrencyForLocation(location) {
  const text = String(location || "").trim().toLowerCase();
  if (["israel", "il", "state of israel"].includes(text)) return "ILS";
  if (["usa", "us", "u.s.", "u.s.a.", "united states", "united states of america"].includes(text)) return "USD";
  return "";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      message = data.detail?.message || data.detail || message;
    } catch {
      // Keep the HTTP status text when the API returns no JSON body.
    }
    throw new Error(message);
  }
  return response.json();
}

let loadingRequests = 0;

function setLoading(active, detail = "Reading cached analytics") {
  const overlay = $("loadingOverlay");
  if (!overlay) return;
  loadingRequests = Math.max(0, loadingRequests + (active ? 1 : -1));
  $("loadingDetail").textContent = detail;
  overlay.hidden = loadingRequests === 0;
  $("refresh")?.classList.toggle("is-loading", loadingRequests > 0);
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  })[char]);
}

function fmt(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "∅";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function money(value, currency = "USD", digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "∅";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: digits,
    }).format(Number(value));
  } catch {
    return `${esc(currency)} ${fmt(value, digits)}`;
  }
}

function compactMoney(value, currency = "USD") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "∅";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency || "USD",
      notation: "compact",
      maximumFractionDigits: 2,
    }).format(Number(value));
  } catch {
    return `${esc(currency)} ${compactNumber(value)}`;
  }
}

function pct(value) {
  if (value === null || value === undefined) return "∅";
  return `${fmt(value)}%`;
}

function compactNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "Not available";
  return new Intl.NumberFormat(undefined, {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function sum(values) {
  return values.reduce((total, value) => total + Number(value || 0), 0);
}

function normalizedField(item, field) {
  const h = item.holding;
  const value = Number(h[field] || 0);
  const currency = h.currency || state.baseCurrency;
  if (currency === state.baseCurrency) return value;
  const direct = state.fxRates[`${currency}/${state.baseCurrency}`];
  if (direct) return value * direct;
  const reverse = state.fxRates[`${state.baseCurrency}/${currency}`];
  if (reverse) return value / reverse;
  return value;
}

function normalizedAmount(value, currency) {
  const number = Number(value || 0);
  if (!currency || currency === state.baseCurrency) return number;
  const direct = state.fxRates[`${currency}/${state.baseCurrency}`];
  if (direct) return number * direct;
  const reverse = state.fxRates[`${state.baseCurrency}/${currency}`];
  if (reverse) return number / reverse;
  return number;
}

function groupValues(items, keyFn, valueFn = (item) => normalizedField(item, "market_value")) {
  return Object.entries(items.reduce((groups, item) => {
    const key = keyFn(item) || "Unknown";
    groups[key] = (groups[key] || 0) + valueFn(item);
    return groups;
  }, {}))
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
}

function colorAt(index) {
  return ["#21a7ff", "#2ee59d", "#ffae18", "#8c86ff", "#f5f6fb", "#00c2a8", "#5f67ff"][index % 7];
}

function defaultDashboard() {
  return {
    mode: "basic",
    edit: false,
    accountTrendAccountId: "total",
    widgets: DASHBOARD_WIDGETS.map((widget, index) => ({ id: widget.id, view: widget.view, order: index })),
  };
}

function loadDashboardSettings() {
  const base = defaultDashboard();
  try {
    const saved = JSON.parse(localStorage.getItem(DASHBOARD_STORAGE_KEY) || "{}");
    const savedWidgets = new Map((saved.widgets || []).map((widget) => [widget.id, widget]));
    base.mode = ["basic", "expanded"].includes(saved.mode) ? saved.mode : base.mode;
    base.edit = false;
    base.accountTrendAccountId = saved.accountTrendAccountId || localStorage.getItem(DASHBOARD_ACCOUNT_STORAGE_KEY) || base.accountTrendAccountId;
    base.widgets = DASHBOARD_WIDGETS.map((widget, index) => {
      const savedWidget = savedWidgets.get(widget.id) || {};
      return {
        id: widget.id,
        view: ["basic", "expanded", "hidden"].includes(savedWidget.view) ? savedWidget.view : widget.view,
        order: Number.isFinite(Number(savedWidget.order)) ? Number(savedWidget.order) : index,
      };
    }).sort((a, b) => a.order - b.order);
  } catch {
    // Ignore corrupt saved layout and fall back to the default dashboard.
  }
  state.dashboard = base;
}

function saveDashboardSettings() {
  if (!state.dashboard) return;
  localStorage.setItem(DASHBOARD_STORAGE_KEY, JSON.stringify(state.dashboard));
}

function loadTableSettings() {
  try {
    const settings = JSON.parse(localStorage.getItem(TABLE_SETTINGS_STORAGE_KEY) || "{}");
    if (["7", "15", "30"].includes(String(settings.maPeriod))) {
      state.tableMaPeriod = String(settings.maPeriod);
    }
  } catch {
    state.tableMaPeriod = "30";
  }
}

function saveTableSettings() {
  localStorage.setItem(TABLE_SETTINGS_STORAGE_KEY, JSON.stringify({ maPeriod: state.tableMaPeriod }));
}

function normalizeDashboardOrders() {
  if (!state.dashboard) return;
  DASHBOARD_SECTIONS.forEach((section) => {
    state.dashboard.widgets
      .filter((widget) => widget.view === section.view)
      .sort((a, b) => a.order - b.order)
      .forEach((widget, index) => { widget.order = index; });
  });
}

function widgetMeta(id) {
  return DASHBOARD_WIDGETS.find((widget) => widget.id === id) || DASHBOARD_WIDGETS[0];
}

function visibleDashboardWidgets() {
  const dashboard = state.dashboard || defaultDashboard();
  return dashboard.widgets
    .filter((widget) => widget.view === "basic" || (dashboard.mode === "expanded" && widget.view === "expanded"))
    .sort((a, b) => a.order - b.order);
}

function dashboardWidgetConfig(id) {
  const dashboard = state.dashboard || defaultDashboard();
  return dashboard.widgets.find((widget) => widget.id === id);
}

function setDashboardWidgetView(id, view) {
  const widget = dashboardWidgetConfig(id);
  if (!widget) return;
  const changed = widget.view !== view;
  widget.view = view;
  if (changed) {
    const sectionWidgets = state.dashboard.widgets.filter((item) => item.view === view && item.id !== id);
    widget.order = sectionWidgets.length ? Math.max(...sectionWidgets.map((item) => Number(item.order || 0))) + 1 : 0;
  }
  normalizeDashboardOrders();
  saveDashboardSettings();
  renderAnalytics(state.items || []);
}

function moveDashboardWidget(id, direction) {
  const source = dashboardWidgetConfig(id);
  if (!source) return;
  const widgets = (state.dashboard || defaultDashboard()).widgets
    .filter((widget) => widget.view === source.view)
    .sort((a, b) => a.order - b.order);
  const index = widgets.findIndex((widget) => widget.id === id);
  const swapIndex = index + direction;
  if (index < 0 || swapIndex < 0 || swapIndex >= widgets.length) return;
  [widgets[index].order, widgets[swapIndex].order] = [widgets[swapIndex].order, widgets[index].order];
  normalizeDashboardOrders();
  saveDashboardSettings();
  renderAnalytics(state.items || []);
}

function setDashboardMode(mode) {
  state.dashboard.mode = mode;
  saveDashboardSettings();
  renderAnalytics(state.items || []);
}

function setDashboardEdit(editing) {
  state.dashboard.edit = editing;
  saveDashboardSettings();
  renderAnalytics(state.items || []);
}

function resetDashboard() {
  state.dashboard = defaultDashboard();
  saveDashboardSettings();
  renderAnalytics(state.items || []);
}

function reorderDashboardWidgets(sourceId, targetId) {
  if (!sourceId || !targetId || sourceId === targetId) return;
  const source = dashboardWidgetConfig(sourceId);
  const target = dashboardWidgetConfig(targetId);
  if (!source || !target) return;
  source.view = target.view;
  const widgets = state.dashboard.widgets
    .filter((widget) => widget.view === target.view && widget.id !== sourceId)
    .sort((a, b) => a.order - b.order);
  const targetIndex = widgets.findIndex((widget) => widget.id === targetId);
  widgets.splice(targetIndex, 0, source);
  widgets.forEach((widget, index) => { widget.order = index; });
  normalizeDashboardOrders();
  saveDashboardSettings();
  renderAnalytics(state.items || []);
}

function appendDashboardWidgetToSection(sourceId, view) {
  const source = dashboardWidgetConfig(sourceId);
  if (!source || !DASHBOARD_SECTIONS.some((section) => section.view === view)) return;
  source.view = view;
  const sectionWidgets = state.dashboard.widgets.filter((widget) => widget.view === view && widget.id !== sourceId);
  source.order = sectionWidgets.length ? Math.max(...sectionWidgets.map((widget) => Number(widget.order || 0))) + 1 : 0;
  normalizeDashboardOrders();
  saveDashboardSettings();
  renderAnalytics(state.items || []);
}

function renderDashboardEditor(renderers) {
  return DASHBOARD_SECTIONS.map((section) => {
    const widgets = state.dashboard.widgets
      .filter((widget) => widget.view === section.view)
      .sort((a, b) => a.order - b.order);
    return `
      <div class="dashboard-section" data-dashboard-section="${esc(section.view)}">
        <div class="dashboard-section-head">
          <h3>${esc(section.label)}</h3>
          <span>${widgets.length} graphs</span>
        </div>
        <div class="dashboard-section-grid">
          ${widgets.length ? widgets.map((widget) => withDashboardToolbar(widget, renderers[widget.id]())).join("") : '<div class="empty">Drop graphs here</div>'}
        </div>
      </div>
    `;
  }).join("");
}

function renderDashboardControls() {
  const dashboard = state.dashboard || defaultDashboard();
  document.querySelectorAll("[data-dashboard-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.dashboardMode === dashboard.mode);
  });
  const editButton = $("dashboardEdit");
  if (editButton) {
    editButton.textContent = dashboard.edit ? "Done" : "Edit";
    editButton.classList.toggle("active", dashboard.edit);
  }
}

function dashboardWidgetToolbar(widget) {
  const meta = widgetMeta(widget.id);
  if (!state.dashboard?.edit) return "";
  return `
    <div class="dashboard-widget-toolbar">
      <span class="dashboard-drag-handle" title="Drag to move">☰</span>
      <div class="widget-placement" role="group" aria-label="${esc(meta.title)} placement">
        <button type="button" data-dashboard-set-view="${esc(widget.id)}" data-view="basic" class="${widget.view === "basic" ? "active" : ""}" title="Show in glance view">Glance</button>
        <button type="button" data-dashboard-set-view="${esc(widget.id)}" data-view="expanded" class="${widget.view === "expanded" ? "active" : ""}" title="Show in full view">Full</button>
        <button type="button" data-dashboard-set-view="${esc(widget.id)}" data-view="hidden" class="${widget.view === "hidden" ? "active" : ""}" title="Hide this card">Hidden</button>
      </div>
      <button class="icon-button mini-icon" type="button" data-dashboard-move="${esc(widget.id)}" data-direction="-1" title="Move up" aria-label="Move ${esc(meta.title)} up">↑</button>
      <button class="icon-button mini-icon" type="button" data-dashboard-move="${esc(widget.id)}" data-direction="1" title="Move down" aria-label="Move ${esc(meta.title)} down">↓</button>
    </div>
  `;
}

function withDashboardToolbar(widget, html) {
  const meta = widgetMeta(widget.id);
  const size = meta.size || "medium";
  const editClass = state.dashboard?.edit ? " dashboard-editing" : "";
  const draggable = state.dashboard?.edit ? ' draggable="true"' : "";
  return html.replace(
    /<div class="chart-card ([^"]*)">/,
    `<div class="chart-card $1 dashboard-widget dashboard-widget-${esc(size)}${editClass}" data-widget="${esc(widget.id)}"${draggable} style="order:${Number(widget.order || 0)}">${dashboardWidgetToolbar(widget)}`,
  );
}

function signedMoney(value, currency = "USD") {
  const prefix = Number(value) > 0 ? "+" : "";
  return `${prefix}${money(value, currency)}`;
}

function groupByCurrency(items, field) {
  return items.reduce((totals, item) => {
    const currency = item.holding.currency || "USD";
    totals[currency] = (totals[currency] || 0) + Number(item.holding[field] || 0);
    return totals;
  }, {});
}

function groupByAccount(items) {
  return Object.values(items.reduce((groups, item) => {
    const holding = item.holding;
    const account = cleanSourceLabel(holding.account) || "Unassigned";
    const group = groups[account] || {
      account,
      value: 0,
      profit: 0,
      localValues: {},
      symbols: [],
      currencies: new Set(),
      type: holding.account_type || "",
      location: holding.location || "",
    };
    const currency = holding.currency || state.baseCurrency;
    group.value += normalizedField(item, "market_value");
    group.profit += normalizedField(item, "unrealized_profit");
    group.localValues[currency] = (group.localValues[currency] || 0) + Number(holding.market_value || 0);
    group.symbols.push(holding.symbol);
    group.currencies.add(currency);
    groups[account] = group;
    return groups;
  }, {})).map((group) => ({ ...group, currencies: [...group.currencies] }));
}

function accountCashValue(account) {
  if (!account) return 0;
  return Math.max(0, normalizedAmount(account.initial_cash, account.currency));
}

function accountRecordForHolding(holding) {
  return state.localAccounts.find((account) => account.id === holding.account_id)
    || state.localAccounts.find((account) => cleanSourceLabel(accountLabel(account)) === cleanSourceLabel(holding.account));
}

function assetRiskFactor(item) {
  const h = item.holding || {};
  const asset = String(h.asset_class || h.asset_sub_class || "").toUpperCase();
  const instrument = String(h.asset_sub_class || "").toUpperCase();
  const symbol = String(h.symbol || "").toUpperCase();
  if (["OPTION", "FUTURE"].includes(asset) || ["OPTION", "FUTURE"].includes(instrument)) return 1;
  if (symbol.includes("3X") || symbol.includes("2X") || symbol.includes("LEVERAGED")) return 1;
  if (asset === "BOND") return 0.35;
  if (asset === "ETF" || asset === "MUTUALFUND") return 0.45;
  if (asset === "EQUITY") return 0.65;
  if (["CRYPTO", "COMMODITY", "OTHER"].includes(asset)) return 0.85;
  return 0.7;
}

function clamp(value, min, max) {
  return Math.min(Math.max(Number(value || 0), min), max);
}

function holdingValuePct(item, totalValue) {
  return totalValue > 0 ? Math.abs(normalizedField(item, "market_value")) / totalValue * 100 : 0;
}

function derivativeHolding(item) {
  const h = item.holding || {};
  const asset = String(h.asset_class || "").toUpperCase();
  const instrument = String(h.asset_sub_class || "").toUpperCase();
  const symbol = String(h.symbol || "").toUpperCase();
  return ["OPTION", "FUTURE"].includes(asset) || ["OPTION", "FUTURE"].includes(instrument) || symbol.includes("3X") || symbol.includes("2X") || symbol.includes("LEVERAGED");
}

function diversifiedFund(item) {
  const h = item.holding || {};
  const asset = String(h.asset_class || "").toUpperCase();
  const symbol = String(h.symbol || "").toUpperCase();
  const industry = String(item.industry || h.industry || h.sector || "").toLowerCase();
  if (!["ETF", "MUTUALFUND"].includes(asset)) return false;
  if (derivativeHolding(item)) return false;
  if (industry.includes("sector") || industry.includes("industry")) return false;
  return !/(ARKK|SOXX|XLK|XLE|XLF|XLV|XLI|XLY|XLP|XLU|XLB|XLC|XBI|KWEB|TAN|ICLN|SMH)/.test(symbol);
}

function industryLabel(item) {
  const h = item.holding || {};
  if (diversifiedFund(item)) return "Diversified fund";
  return String(item.industry || h.industry || h.sector || "").trim();
}

function issuerLabel(item) {
  const h = item.holding || {};
  return String(h.symbol || h.name || "Unknown").trim().toUpperCase();
}

function countryLabel(item) {
  const h = item.holding || {};
  return String(h.country || h.location || h.currency || "Unknown").trim();
}

function volatilityProxy(item) {
  const h = item.holding || {};
  const range = item.price_ranges?.["1y"] || {};
  const high = Number(range.high || 0);
  const low = Number(range.min || 0);
  const current = Number(range.current || h.market_value / Math.max(Math.abs(Number(h.quantity || 0)), 1) || 0);
  if (high > 0 && low > 0 && current > 0 && high >= low) {
    return clamp(((high - low) / current) * 100, 0, 120);
  }
  if (derivativeHolding(item)) return 90;
  const asset = String(h.asset_class || "").toUpperCase();
  if (asset === "BOND") return 14;
  if (asset === "ETF" || asset === "MUTUALFUND") return diversifiedFund(item) ? 24 : 36;
  if (asset === "EQUITY") return 48;
  return 55;
}

function personHorizonYears(person) {
  const age = Number(person?.age || ageFromBirthDate(person?.birth_date));
  if (!age) return null;
  return Math.max(0, 67 - age);
}

function accountHorizonYears(account) {
  const horizons = (account?.persons || []).map(personHorizonYears).filter((value) => value !== null);
  if (horizons.length) return Math.min(...horizons);
  if (account?.type === "Long-Term Savings") return 15;
  return null;
}

function riskBand(score) {
  if (score <= 20) return { key: "low", label: "Low", symbol: "●" };
  if (score <= 40) return { key: "moderate", label: "Moderate", symbol: "◆" };
  if (score <= 60) return { key: "elevated", label: "Elevated", symbol: "▲" };
  if (score <= 80) return { key: "high", label: "High", symbol: "⬟" };
  return { key: "extreme", label: "Extreme", symbol: "!" };
}

function riskBadge(risk, compact = false) {
  if (!risk) return "";
  const band = riskBand(risk.score);
  return `<span class="risk-badge risk-${band.key}" title="${esc(riskTooltip(risk))}">
    <span class="risk-symbol" aria-hidden="true">${esc(band.symbol)}</span>
    <b>${esc(risk.score)}</b>${compact ? "" : `<span>${esc(band.label)}</span>`}
  </span>`;
}

function riskTooltip(risk) {
  const parts = risk.components || {};
  const drivers = (risk.drivers || []).slice(0, 5).join("; ") || "No dominant driver";
  return [
    `${risk.label || "Risk"} score ${risk.score}/100 (${riskBand(risk.score).label}). Min 0, max 100.`,
    "Advanced formula: concentration + asset mix + currency + industry + cash + options/futures/leverage + volatility + horizon suitability + issuer/country + data quality.",
    `Components: concentration ${fmt(parts.concentration, 1)}/16, asset ${fmt(parts.asset_mix, 1)}/14, currency ${fmt(parts.currency, 1)}/10, industry ${fmt(parts.industry, 1)}/10, cash ${fmt(parts.cash, 1)}/7, derivatives ${fmt(parts.derivatives, 1)}/10, volatility ${fmt(parts.volatility, 1)}/10, horizon ${fmt(parts.horizon, 1)}/10, issuer/country ${fmt(parts.issuer_country, 1)}/8, data ${fmt(parts.data_quality, 1)}/5.`,
    `Drivers: ${drivers}.`,
  ].join("\n");
}

function riskScoreForItems(items, options = {}) {
  const rows = items || [];
  const label = options.label || "Portfolio risk";
  const cash = Math.max(0, Number(options.cash || 0));
  const horizonYears = options.horizonYears ?? null;
  const values = rows.map((item) => Math.abs(normalizedField(item, "market_value"))).filter((value) => value > 0);
  const holdingsValue = sum(values);
  const totalValue = holdingsValue + cash;
  if (totalValue <= 0) {
    return { label, score: 0, components: {}, drivers: ["No account value"], position_risks: new Map() };
  }

  const topPositionPct = values.length ? Math.max(...values) / totalValue * 100 : 0;
  const hhi = rows.reduce((total, item) => {
    const pct = Math.abs(normalizedField(item, "market_value")) / totalValue * 100;
    return total + pct * pct;
  }, 0);
  const concentration = Math.min(topPositionPct / 40, 1) * 10 + Math.min(hhi / 2500, 1) * 6;

  const weightedAsset = rows.reduce((total, item) => total + Math.abs(normalizedField(item, "market_value")) * assetRiskFactor(item), cash * 0.05);
  const assetMix = totalValue ? weightedAsset / totalValue * 14 : 0;

  const currencyTotals = rows.reduce((totals, item) => {
    const currency = item.holding.currency || state.baseCurrency;
    totals[currency] = (totals[currency] || 0) + Math.abs(normalizedField(item, "market_value"));
    return totals;
  }, {});
  if (cash) {
    const cashCurrency = options.cashCurrency || state.baseCurrency;
    currencyTotals[cashCurrency] = (currencyTotals[cashCurrency] || 0) + cash;
  }
  const foreignValues = Object.entries(currencyTotals).filter(([currency]) => currency !== state.baseCurrency).map(([, value]) => value);
  const nonBaseCurrencyPct = sum(foreignValues) / totalValue * 100;
  const largestForeignCurrencyPct = (foreignValues.length ? Math.max(...foreignValues) : 0) / totalValue * 100;
  const currency = Math.min(nonBaseCurrencyPct / 80, 1) * 7 + Math.min(largestForeignCurrencyPct / 60, 1) * 3;

  const industryRows = rows.filter((item) => Math.abs(normalizedField(item, "market_value")) > 0);
  const industryTotals = industryRows.reduce((totals, item) => {
    const industry = industryLabel(item);
    if (!industry) return totals;
    totals[industry] = (totals[industry] || 0) + Math.abs(normalizedField(item, "market_value"));
    return totals;
  }, {});
  const industryHhi = Object.values(industryTotals).reduce((total, value) => {
    const pct = Number(value || 0) / Math.max(holdingsValue, 1) * 100;
    return total + pct * pct;
  }, 0);
  const missingIndustryPct = holdingsValue ? industryRows
    .filter((item) => !industryLabel(item))
    .reduce((total, item) => total + Math.abs(normalizedField(item, "market_value")), 0) / holdingsValue * 100 : 0;
  const industry = Math.min(industryHhi / 3000, 1) * 7 + missingIndustryPct / 100 * 3;

  const cashPct = cash / totalValue * 100;
  const cashScore = cashPct >= 5 && cashPct <= 20 ? 0 : cashPct < 5 ? (5 - cashPct) / 5 * 5 : Math.min((cashPct - 20) / 50, 1) * 2;

  const derivativesValue = rows
    .filter(derivativeHolding)
    .reduce((total, item) => total + Math.abs(normalizedField(item, "market_value")), 0);
  const derivativePct = derivativesValue / totalValue * 100;
  const hasShort = rows.some((item) => Number(item.holding.quantity || 0) < 0);
  const derivatives = Math.min(derivativePct / 25, 1) * 8 + (hasShort ? 2 : 0);

  const weightedVolatility = rows.reduce((total, item) => total + Math.abs(normalizedField(item, "market_value")) * volatilityProxy(item), 0);
  const avgVolatilityPct = holdingsValue ? weightedVolatility / holdingsValue : 0;
  const volatility = Math.min(avgVolatilityPct / 60, 1) * 10;

  const riskyAssetPct = totalValue ? rows
    .filter((item) => assetRiskFactor(item) >= 0.65 || derivativeHolding(item))
    .reduce((total, item) => total + Math.abs(normalizedField(item, "market_value")), 0) / totalValue * 100 : 0;
  let horizon = 0;
  if (horizonYears !== null && horizonYears !== undefined) {
    const shortHorizonPressure = horizonYears < 3 ? 1 : horizonYears < 7 ? (7 - horizonYears) / 4 : 0;
    const longHorizonUnderRisk = horizonYears > 15 && riskyAssetPct < 35 ? Math.min((35 - riskyAssetPct) / 35, 1) * 0.35 : 0;
    horizon = Math.min((shortHorizonPressure * (riskyAssetPct / 100) + longHorizonUnderRisk) * 10, 10);
  }

  const issuerTotals = rows.reduce((totals, item) => {
    const issuer = issuerLabel(item);
    const fundLookThroughWeight = diversifiedFund(item) ? 0.35 : 1;
    totals[issuer] = (totals[issuer] || 0) + Math.abs(normalizedField(item, "market_value")) * fundLookThroughWeight;
    return totals;
  }, {});
  const countryTotals = rows.reduce((totals, item) => {
    const country = countryLabel(item);
    totals[country] = (totals[country] || 0) + Math.abs(normalizedField(item, "market_value"));
    return totals;
  }, {});
  const largestIssuerPct = holdingsValue ? Math.max(0, ...Object.values(issuerTotals)) / holdingsValue * 100 : 0;
  const largestCountryPct = holdingsValue ? Math.max(0, ...Object.values(countryTotals)) / holdingsValue * 100 : 0;
  const issuerCountry = Math.min(largestIssuerPct / 35, 1) * 4 + Math.max(0, Math.min((largestCountryPct - 55) / 35, 1)) * 4;

  const missingPricePct = holdingsValue ? rows.filter((item) => (item.missing || []).includes("price history")).reduce((total, item) => total + Math.abs(normalizedField(item, "market_value")), 0) / holdingsValue * 100 : 0;
  const missingClassPct = holdingsValue ? rows.filter((item) => !item.holding.asset_class || !item.holding.currency).reduce((total, item) => total + Math.abs(normalizedField(item, "market_value")), 0) / holdingsValue * 100 : 0;
  const dataQuality = missingPricePct / 100 * 2 + missingIndustryPct / 100 * 1.5 + missingClassPct / 100 * 1.5;

  const components = {
    concentration,
    asset_mix: assetMix,
    currency,
    industry,
    cash: cashScore,
    derivatives,
    volatility,
    horizon,
    issuer_country: issuerCountry,
    data_quality: dataQuality,
  };
  const score = Math.min(Math.max(Math.round(sum(Object.values(components))), 0), 100);
  const drivers = [
    topPositionPct > 25 ? `Top holding ${fmt(topPositionPct, 1)}%` : "",
    nonBaseCurrencyPct > 40 ? `Foreign currency ${fmt(nonBaseCurrencyPct, 1)}%` : "",
    derivativePct > 0 ? `Options/futures/leverage ${fmt(derivativePct, 1)}%` : "",
    avgVolatilityPct > 35 ? `1Y volatility proxy ${fmt(avgVolatilityPct, 1)}%` : "",
    horizonYears !== null && horizonYears !== undefined ? `Horizon ${fmt(horizonYears, 1)} years` : "",
    largestIssuerPct > 25 ? `Issuer concentration ${fmt(largestIssuerPct, 1)}%` : "",
    largestCountryPct > 70 ? `Country concentration ${fmt(largestCountryPct, 1)}%` : "",
    cashPct < 5 ? `Low cash ${fmt(cashPct, 1)}%` : cashPct > 20 ? `High cash ${fmt(cashPct, 1)}%` : "",
    missingIndustryPct > 20 ? `Missing industry ${fmt(missingIndustryPct, 1)}%` : "",
  ].filter(Boolean);
  const positionRisks = new Map(rows.map((item) => {
    const valuePct = Math.abs(normalizedField(item, "market_value")) / totalValue * 100;
    const itemVolatility = volatilityProxy(item);
    const itemScore = Math.min(Math.round(valuePct * 0.65 + assetRiskFactor(item) * 20 + itemVolatility / 120 * 15 + (derivativeHolding(item) ? 15 : 0) + ((item.missing || []).length ? 6 : 0)), 100);
    return [item, {
      label: `${item.holding.symbol} holding risk`,
      score: itemScore,
      components,
      drivers: [
        `Holding weight ${fmt(valuePct, 1)}%`,
        `Asset factor ${fmt(assetRiskFactor(item), 2)}`,
        `1Y volatility proxy ${fmt(itemVolatility, 1)}%`,
        diversifiedFund(item) ? "ETF/fund treated as diversified proxy" : "",
        derivativeHolding(item) ? "Option/future/leveraged instrument" : "",
        ...(item.missing || []).slice(0, 2).map((label) => `Missing ${label}`),
      ].filter(Boolean),
    }];
  }));
  return { label, score, components, drivers, position_risks: positionRisks, cash_pct: cashPct };
}

function portfolioRiskSnapshot(items) {
  const accountsById = Object.fromEntries(state.localAccounts.map((account) => [account.id, account]));
  const itemsByAccount = items.reduce((groups, item) => {
    const key = item.holding.account_id || cleanSourceLabel(item.holding.account) || "Unassigned";
    groups[key] = groups[key] || [];
    groups[key].push(item);
    return groups;
  }, {});
  const accountRisks = Object.entries(itemsByAccount).map(([key, rows]) => {
    const account = accountsById[key] || accountRecordForHolding(rows[0].holding);
    const cash = accountCashValue(account);
    const value = sum(rows.map((item) => Math.abs(normalizedField(item, "market_value")))) + cash;
    const horizonYears = accountHorizonYears(account);
    return {
      key,
      account: cleanSourceLabel(rows[0].holding.account) || account?.account_id || "Unassigned",
      value,
      horizonYears,
      risk: riskScoreForItems(rows, { label: `${cleanSourceLabel(rows[0].holding.account) || "Account"} risk`, cash, cashCurrency: account?.currency, horizonYears }),
    };
  });
  const combinedCash = sum(state.localAccounts.map(accountCashValue));
  const portfolioHorizons = state.localAccounts.map(accountHorizonYears).filter((value) => value !== null);
  const portfolioHorizonYears = portfolioHorizons.length ? Math.min(...portfolioHorizons) : null;
  const combinedRisk = riskScoreForItems(items, { label: "Total portfolio risk", cash: combinedCash, horizonYears: portfolioHorizonYears });
  const holdingsValue = sum(items.map((item) => Math.abs(normalizedField(item, "market_value"))));
  const cashValue = combinedCash;
  const nav = holdingsValue + cashValue || 1;
  const weightedAccountScore = accountRisks.reduce((total, entry) => {
    return total + entry.risk.score * (entry.value / nav);
  }, 0);
  const score = Math.min(Math.max(Math.round(0.75 * combinedRisk.score + 0.25 * weightedAccountScore), 0), 100);
  const totalRisk = { ...combinedRisk, score, label: "Total portfolio risk" };
  return { total: totalRisk, accounts: accountRisks };
}

function cleanSourceLabel(value) {
  const legacyName = String.fromCharCode(71, 104, 111, 115, 116, 102, 111, 108, 105, 111);
  return String(value || "").replace(new RegExp(legacyName, "gi"), "").replace(/import-/gi, "").replace(/\s+/g, " ").trim().replace(/^[\s-]+|[\s-]+$/g, "");
}

function providerDisplayName(value) {
  const key = String(value || "").toLowerCase().replace(/[.\s-]+/g, "_");
  const names = {
    yahoo: "Yahoo",
    yahoo_finance: "Yahoo",
    google: "Google",
    google_finance: "Google",
    alpha_vantage: "Alpha Vantage",
    financial_modeling_prep: "FMP",
    fmp: "FMP",
    stooq: "Stooq",
    sec_company_facts: "SEC",
    sec_company_tickers: "SEC",
    external_import_market_data: "Import DB",
    local: "Local",
    manual: "Manual",
  };
  return names[key] || cleanSourceLabel(value);
}

function isProviderName(value) {
  const key = String(value || "").toLowerCase().replace(/[.\s-]+/g, "_");
  return [
    "yahoo",
    "yahoo_finance",
    "google",
    "google_finance",
    "alpha_vantage",
    "financial_modeling_prep",
    "fmp",
    "stooq",
    "sec_company_facts",
    "sec_company_tickers",
    "external_import_market_data",
    "local",
  ].includes(key);
}

function holdingMarketKey(h) {
  return h.platform || h.stock_market || h.data_source || "MANUAL";
}

function stockMarketDisplay(h, marketKey = "") {
  const candidate = h.stock_market && !isProviderName(h.stock_market) ? h.stock_market : (!isProviderName(marketKey) ? marketKey : "");
  return candidate ? cleanSourceLabel(candidate).toUpperCase() : "Unknown";
}

function dataProviderDisplay(item, h, marketKey = "") {
  if (isProviderName(marketKey)) return providerDisplayName(marketKey);
  if (h.data_source && h.data_source !== "LOCAL") return providerDisplayName(h.data_source);
  const ok = Object.entries(item.provider_status || {}).find(([key, value]) => value === "ok" && key.includes("."));
  return ok ? providerDisplayName(ok[0].split(".").pop()) : providerDisplayName(h.data_source || "local");
}

function bestCurrencyTotal(totals) {
  const entries = Object.entries(totals);
  if (!entries.length) return ["USD", 0];
  return entries.sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))[0];
}

function trendClass(direction) {
  if (direction === "up") return "up";
  if (direction === "down") return "down";
  return "neutral";
}

function changeClass(value) {
  const number = Number(value || 0);
  if (number > 0) return "up";
  if (number < 0) return "down";
  return "neutral";
}

function changeText(value) {
  const number = Number(value || 0);
  if (number > 0) return "Up";
  if (number < 0) return "Down";
  return "Flat";
}

function trendText(direction) {
  if (direction === "up") return "Up";
  if (direction === "down") return "Down";
  if (direction === "flat") return "Flat";
  return "Missing";
}

function seriesDate(trend, offset) {
  const series = trend?.series || [];
  const row = series[series.length - offset];
  return row?.date || "";
}

function formatMetricValue(value, kind, currency) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "Not available";
  if (kind === "dividend") return `${money(value, currency, 2)} / share`;
  if (kind === "percent") return pct(Number(value) * 100);
  return compactNumber(value);
}

function trendCell(trend, label, { kind = "number", currency = "USD", marketCap = null } = {}) {
  if (!trend || trend.state === "missing") {
    const message = trend?.message || `Provider did not return enough ${label.toLowerCase()} history`;
    return `<div class="metric-cell missing-state" title="${esc(message)}">
      <div class="metric-head">
        <span class="metric-name">${esc(label)}</span>
        <span class="metric-pill warn">Missing</span>
      </div>
      <div class="metric-row"><span>Status</span><b>Missing data</b></div>
      ${marketCap ? `<div class="metric-row"><span>Market cap</span><b>${compactMoney(marketCap, currency)}</b></div>` : ""}
      <small>${esc(message)}</small>
    </div>`;
  }
  const currentDate = seriesDate(trend, 1);
  const previousDate = seriesDate(trend, 2);
  const percentClass = changeClass(trend.percent_change);
  return `<div class="metric-cell">
    <div class="metric-head">
      <span class="metric-name">${esc(label)}</span>
      <span class="metric-pill ${percentClass}">${esc(changeText(trend.percent_change))}</span>
    </div>
    <div class="metric-row"><span>Current</span><b>${esc(formatMetricValue(trend.current, kind, currency))}</b>${currentDate ? `<em>${esc(currentDate)}</em>` : ""}</div>
    <div class="metric-row"><span>Previous</span><b>${esc(formatMetricValue(trend.previous, kind, currency))}</b>${previousDate ? `<em>${esc(previousDate)}</em>` : ""}</div>
    <div class="metric-row"><span>Change</span><b class="${percentClass}">${pct(trend.percent_change)}</b></div>
    ${marketCap ? `<div class="metric-row"><span>Market cap</span><b>${compactMoney(marketCap, currency)}</b></div>` : ""}
  </div>`;
}

function rangeCell(range, currency) {
  if (range.state !== "ok" && range.state !== "partial") {
    return `<div class="metric-cell missing-state">
      <div class="metric-head">
        <span class="metric-name">Price range</span>
        <span class="metric-pill warn">Missing</span>
      </div>
      <div class="metric-row"><span>Status</span><b>No price history</b></div>
      <small>${esc(range.message || "Provider has no 1Y price data")}</small>
    </div>`;
  }
  return `<div class="metric-cell">
    <div class="metric-head">
      <span class="metric-name">High / Low</span>
      ${range.state === "partial" ? '<span class="metric-pill warn">Partial</span>' : '<span class="metric-pill ok">Complete</span>'}
    </div>
    <div class="metric-row"><span>High</span><b>${money(range.high, currency)}</b>${range.high_date ? `<em>${esc(range.high_date)}</em>` : ""}</div>
    <div class="metric-row"><span>Low</span><b>${money(range.min, currency)}</b>${range.min_date ? `<em>${esc(range.min_date)}</em>` : ""}</div>
    ${range.state === "partial" ? `<small class="warn-text">${esc(range.message)}</small>` : ""}
  </div>`;
}

function technicalsCell(sr, movingAverage, currency, maPeriod) {
  if (sr.state !== "ok") {
    return `<div class="metric-cell missing-state">
      <div class="metric-head">
        <span class="metric-name">Technicals</span>
        <span class="metric-pill warn">Missing</span>
      </div>
      <div class="metric-row"><span>Status</span><b>No levels</b></div>
      <small>${esc(sr.message || "Not enough price history for support/resistance")}</small>
    </div>`;
  }
  return `<div class="metric-cell">
    <div class="metric-head">
      <span class="metric-name">Support / resistance</span>
      <span class="metric-pill ok">Ready</span>
    </div>
    <div class="metric-row"><span>Support</span><b>${money(sr.support.price, currency)}</b></div>
    <div class="metric-row"><span>Resistance</span><b>${money(sr.resistance.price, currency)}</b></div>
    <div class="metric-row"><span>MA ${esc(maPeriod)}</span><b>${movingAverage.state === "ok" ? money(movingAverage.value, currency, 2) : esc(movingAverage.message || "Not available")}</b></div>
  </div>`;
}

function providerStatusText(providerStatus) {
  return Object.entries(providerStatus || {})
    .map(([provider, value]) => `${provider}: ${value}`)
    .join("; ");
}

function providerStatusHint(providerStatus) {
  const entries = Object.entries(providerStatus || {});
  const okProviders = [...new Set(entries
    .filter(([, value]) => String(value).toLowerCase() === "ok")
    .map(([key]) => providerDisplayName(key.split(".").pop())))];
  const failedProviders = [...new Set(entries
    .filter(([, value]) => String(value).toLowerCase().includes("error"))
    .map(([key]) => providerDisplayName(key.split(".").pop())))];
  const missingKeyProviders = [...new Set(entries
    .filter(([, value]) => String(value).toLowerCase().includes("api key"))
    .map(([key]) => providerDisplayName(key.split(".").pop())))];
  if (okProviders.length) return `Data from ${okProviders.slice(0, 2).join(", ")}${okProviders.length > 2 ? ` +${okProviders.length - 2}` : ""}`;
  if (missingKeyProviders.length) return `Missing key: ${missingKeyProviders.slice(0, 2).join(", ")}`;
  if (failedProviders.length) return `Fallback failed: ${failedProviders.slice(0, 2).join(", ")}`;
  const values = entries.map(([, value]) => String(value));
  if (values.some((value) => value.toLowerCase().includes("missing"))) return "Some provider fields missing";
  return "";
}

function statusCell(item) {
  const providerText = providerStatusText(item.provider_status);
  const providerHint = providerStatusHint(item.provider_status);
  if (!item.missing.length) {
    return `<div class="status-cell" title="${esc(providerText || "All displayed metrics are available")}">
      <span class="badge ok">All displayed data available</span>
      ${providerHint ? `<small>${esc(providerHint)}</small>` : ""}
    </div>`;
  }
  const visible = item.missing.slice(0, 3);
  const hiddenCount = Math.max(0, item.missing.length - visible.length);
  return `<div class="status-cell" title="${esc(`${item.missing.join(", ")}${providerText ? `; ${providerText}` : ""}`)}">
    <strong>${item.missing.length} data gaps</strong>
    <div class="status-badges">
      ${visible.map((m) => `<span class="badge warn">${esc(m)}</span>`).join("")}
      ${hiddenCount ? `<span class="badge warn">+${hiddenCount} more</span>` : ""}
    </div>
    ${providerHint ? `<small>${esc(providerHint)}</small>` : ""}
  </div>`;
}

function criteriaFromForm() {
  return {
    query: $("query").value.trim(),
    account: $("account").value,
    accountType: $("accountType").value,
    location: $("locationFilter").value.trim(),
    assetClass: $("assetClass").value,
    currency: $("currency").value,
    sector: $("sector").value.trim(),
    minHoldingValue: $("minHoldingValue").value,
    maxHoldingValue: $("maxHoldingValue").value,
    includeMissing: $("includeMissing").checked,
  };
}

function setSelectOptions(id, values, label) {
  const select = $(id);
  const current = select.value;
  select.innerHTML = `<option value="">${label}</option>` + values
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b))
    .map((value) => `<option value="${esc(value)}">${esc(value)}</option>`)
    .join("");
  select.value = values.includes(current) ? current : "";
}

function setOptions(id, values, label = "") {
  const select = $(id);
  if (!select) return;
  const current = select.value;
  select.innerHTML = (label ? `<option value="">${esc(label)}</option>` : "") + values.map((value) => `<option value="${esc(value)}">${esc(value)}</option>`).join("");
  if (values.includes(current)) select.value = current;
}

function setCurrencyOptions(id) {
  const select = $(id);
  if (!select) return;
  const current = select.value;
  const codes = [...new Set(currencyCodes())].sort();
  select.innerHTML = codes.map((code) => `<option value="${esc(code)}">${esc(currencySymbol(code))} ${esc(code)}</option>`).join("");
  select.value = codes.includes(current) ? current : (codes.includes("USD") ? "USD" : codes[0]);
}

function syncCurrencyFromLocation(locationId, currencyId) {
  const currency = preferredCurrencyForLocation(valueOf(locationId));
  const select = $(currencyId);
  if (currency && select && [...select.options].some((option) => option.value === currency)) {
    select.value = currency;
  }
}

function populateStaticOptions() {
  $("countryOptions").innerHTML = REGION_CODES
    .map((code) => {
      const name = countryName(code);
      return `<option value="${esc(name)}" label="${esc(flagFor(code))} ${esc(name)}"></option>`;
    })
    .join("");
  ["localAccountCurrency", "priceCurrency", "manualSecurityCurrency"].forEach(setCurrencyOptions);
  const assetClasses = state.localOptions.asset_classes || ["EQUITY", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE"];
  setOptions("localAccountType", state.localOptions.account_types);
  setOptions("reportAccountType", state.localOptions.account_types, "Any account type");
  setOptions("fundKind", state.localOptions.fund_kinds);
  setOptions("securityAssetClass", assetClasses);
  setOptions("priceAssetClass", assetClasses);
  setOptions("manualInstrumentType", state.localOptions.instrument_types || ["STOCK", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE"]);
  setOptions("manualOptionType", state.localOptions.option_types || ["CALL", "PUT"]);
  $("localAccountLocation").value = "USA";
  $("manualSecurityLocation").value = "USA";
  $("priceLocation").value = "USA";
  $("securityDate").value = todayString();
  $("priceDate").value = todayString();
  $("historyDate").value = todayString();
  $("historyDate").min = HISTORY_START_DATE;
  $("reportTo").value = todayString();
  $("reportFrom").min = HISTORY_START_DATE;
  $("reportFrom").value = HISTORY_START_DATE;
  if ($("securityChartStartDate")) $("securityChartStartDate").min = HISTORY_START_DATE;
  toggleManualInstrumentFields();
}

function todayString() {
  return new Date().toISOString().slice(0, 10);
}

function clampedHistoryDate(value) {
  const dateValue = String(value || "").slice(0, 10);
  return dateValue && dateValue > HISTORY_START_DATE ? dateValue : HISTORY_START_DATE;
}

function startDateForPeriod(period) {
  const days = { "1m": 31, "1y": 366, "3y": 366 * 3, "5y": 366 * 5 }[period] || 366;
  return clampedHistoryDate(new Date(Date.now() - days * 86400000).toISOString().slice(0, 10));
}

function populateOptions(items) {
  setSelectOptions("account", [...new Set(items.map((item) => item.holding.account))], "Any account");
  setSelectOptions("currency", [...new Set(items.map((item) => item.holding.currency))], "Any currency");
  setSelectOptions("accountType", [...new Set(items.map((item) => item.holding.account_type)), ...state.localOptions.account_types], "Any account type");
  state.optionsReady = true;
}

function missingStats(items) {
  const counts = items.reduce((totals, item) => {
    item.missing.forEach((label) => {
      totals[label] = (totals[label] || 0) + 1;
    });
    return totals;
  }, {});
  const topLabels = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([label, count]) => `${label}: ${count}`)
    .join("; ");
  return {
    total: items.reduce((sum, item) => sum + item.missing.length, 0),
    positions: items.filter((item) => item.missing.length).length,
    topLabels,
  };
}

function renderSummary(items) {
  state.riskSnapshot = portfolioRiskSnapshot(items);
  const primaryValue = sum(items.map((item) => normalizedField(item, "market_value")));
  const primaryProfit = sum(items.map((item) => normalizedField(item, "unrealized_profit")));
  const accountTotals = groupByAccount(items).sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
  const symbols = new Set(items.map((item) => item.holding.symbol)).size;
  const bonds = items.filter((item) => item.holding.asset_class === "BOND").length;
  const equities = items.filter((item) => item.holding.asset_class === "EQUITY").length;
  const gaps = missingStats(items);

  $("balanceValue").textContent = money(primaryValue, state.baseCurrency);
  $("profitBadge").className = `delta ${primaryProfit > 0 ? "up" : primaryProfit < 0 ? "down" : "neutral"}`;
  $("profitBadge").textContent = `Holding Profit ${signedMoney(primaryProfit, state.baseCurrency)}`;
  $("profitBadge").title = `Holding profit converted to ${state.baseCurrency} using displayed FX rates when available`;
  $("currencyBreakdown").innerHTML = accountTotals
    .map((account) => {
      const accountRisk = state.riskSnapshot.accounts.find((entry) => entry.account === account.account)?.risk;
      const symbolsText = account.symbols.slice(0, 12).join(", ");
      const more = account.symbols.length > 12 ? `, +${account.symbols.length - 12} more` : "";
      const localAmounts = Object.entries(account.localValues || {})
        .filter(([currency]) => currency !== state.baseCurrency)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([currency, value]) => money(value, currency, 0));
      const localLine = localAmounts.length ? `<small>${esc(localAmounts.join(" · "))}</small>` : "";
      const title = `Account: ${account.account}; ${account.type || "Account"}${account.location ? ` · ${account.location}` : ""}; Securities: ${symbolsText}${more}; Source currencies: ${account.currencies.join(", ")}`;
      return `<span class="account-chip" title="${esc(title)}"><b>${esc(account.account)}</b><span class="account-chip-values"><strong>${money(account.value, state.baseCurrency, 0)}</strong>${localLine}</span>${riskBadge(accountRisk, true)}</span>`;
    })
    .join("");

  $("summary").innerHTML = [
    ["Risk", state.riskSnapshot.total.score, riskTooltip(state.riskSnapshot.total), riskBand(state.riskSnapshot.total.score).label, riskBadge(state.riskSnapshot.total, true)],
    ["Positions", items.length, "Number of open positions shown after filters"],
    ["Securities", symbols, "Unique security symbols"],
    ["Equities", equities, "Open equity positions"],
    ["Bonds", bonds, "Open bond positions"],
    ["Data gaps", gaps.total, gaps.topLabels || "No missing analytics fields", `${gaps.positions}/${items.length} positions`],
  ].map(([label, value, tooltip, detail]) => `
    <div class="stat" title="${esc(tooltip || "")}">
      ${detail && String(detail).includes("risk-badge") ? detail : `<b>${esc(value)}</b>`}
      <span>${esc(label)}</span>
      ${detail && !String(detail).includes("risk-badge") ? `<small>${esc(detail)}</small>` : ""}
    </div>
  `).join("");
}

function renderFundsOverview() {
  const frame = $("fundsOverview");
  if (!frame) return;
  const funds = state.localFunds || [];
  const longTermAccountItems = (state.items || []).filter((item) => item.holding.account_type === "Long-Term Savings");
  const longTermAccounts = new Set(longTermAccountItems.map((item) => item.holding.account).filter(Boolean));
  const securitiesValue = sum(longTermAccountItems.map((item) => normalizedField(item, "market_value")));
  const amount = sum(funds.map((fund) => fund.amount)) + securitiesValue;
  const monthly = sum(funds.map((fund) => fund.monthly_estimate));
  const fundTitle = funds.map((fund) => `${fund.kind} ${fund.pension_id}: saved ${fmt(fund.amount, 0)}, monthly ${fmt(fund.monthly_estimate, 0)}`).join("; ");
  const accountTitle = [...longTermAccounts].join(", ");
  const title = [accountTitle ? `Long-term accounts: ${accountTitle}` : "", fundTitle].filter(Boolean).join("; ");
  frame.innerHTML = `
    <div>
      <p class="eyebrow">Long-term savings</p>
      <h2>Pension accounts and funds</h2>
    </div>
    <div class="funds-overview-stats" title="${esc(title || "No pension fund records")}">
      <span><b>${esc(longTermAccounts.size)}</b> accounts</span>
      <span><b>${esc(funds.length)}</b> funds</span>
      <span><b>${money(amount, state.baseCurrency, 0)}</b> saved</span>
      <span title="Estimated monthly pension payout from saved fund records. Formula: amount / factor."><b>${fmt(monthly, 0)}</b> monthly estimate</span>
    </div>
    <button class="secondary" type="button" data-modal="fundsModal">Manage</button>
  `;
}

function renderRows(items) {
  $("count").textContent = `${items.length} shown`;
  $("rows").innerHTML = items.map((item) => {
    const h = item.holding;
    const range = item.price_ranges["1y"] || {};
    const maPeriod = state.tableMaPeriod || "30";
    const movingAverage = item.moving_averages[maPeriod] || {};
    const sr = item.support_resistance["1y"] || {};
    const marketKey = holdingMarketKey(h);
    const market = stockMarketDisplay(h, marketKey);
    const provider = dataProviderDisplay(item, h, marketKey);
    const securityName = String(h.name || "").trim();
    const companyLine = securityName || String(h.symbol || "").trim();
    const industry = String(item.industry || h.industry || h.sector || "").trim();
    const industryLine = `<div class="security-industry">Industry: ${esc(industry || "Not available")}</div>`;
    const marketLine = `${h.asset_class || "Asset"} · ${h.currency || ""} · Market: ${market} · API: ${provider}`;
    const rowRisk = state.riskSnapshot?.total?.position_risks?.get(item);
    return `<tr>
      <td data-label="Security"><div class="security-cell"><button class="symbol security-history-link" type="button" data-security-detail-symbol="${esc(h.symbol)}" data-security-detail-market-key="${esc(marketKey)}" data-security-detail-stock-market="${esc(market)}" data-security-detail-provider="${esc(provider)}" data-security-detail-asset="${esc(h.asset_class)}" data-security-detail-currency="${esc(h.currency)}" data-security-detail-location="${esc(h.country || h.location || "")}" title="Open security overview">${esc(h.symbol)}</button><div class="security-name">${esc(companyLine)}</div>${industryLine}<div class="sub security-meta">${esc(marketLine)}</div></div></td>
      <td data-label="Account"><div>${esc(cleanSourceLabel(h.account) || "∅")}</div><div class="sub">${esc(cleanSourceLabel(h.account_type || h.location || h.sector || ""))}</div></td>
      <td data-label="Risk">${riskBadge(rowRisk)}</td>
      <td data-label="Value / P&L"><div class="value-cell"><strong>${money(h.market_value, h.currency)}</strong><span>${fmt(h.quantity, 3)} units</span><b class="${Number(h.unrealized_profit) >= 0 ? "positive" : "negative"}">${signedMoney(h.unrealized_profit, h.currency)}</b></div></td>
      <td data-label="1Y High / Low">${rangeCell(range, h.currency)}</td>
      <td data-label="Net income">${trendCell(item.profit_trend, "Net income", { currency: h.currency, marketCap: item.market_cap })}</td>
      <td data-label="Dividend Trend">${trendCell(item.dividend_trend, "Annual dividend", { kind: "dividend", currency: h.currency })}</td>
      <td data-label="Support / Resistance">${technicalsCell(sr, movingAverage, h.currency, maPeriod)}</td>
      <td data-label="Data Status">${statusCell(item)}</td>
    </tr>`;
  }).join("");
}

function chartPath(values, width, height, pad = 14) {
  if (!values.length) return { line: "", area: "", points: [] };
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((value, index) => {
    const x = values.length === 1 ? width / 2 : pad + (index / (values.length - 1)) * (width - pad * 2);
    const y = height - pad - ((value - min) / span) * (height - pad * 2);
    return [x, y, value];
  });
  const line = points.map(([x, y], index) => `${index ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = `${line} L ${points.at(-1)[0].toFixed(1)} ${height - pad} L ${points[0][0].toFixed(1)} ${height - pad} Z`;
  return { line, area, points };
}

function linePath(points, xFn, yFn) {
  return points.map((point, index) => `${index ? "L" : "M"} ${xFn(point, index).toFixed(1)} ${yFn(point, index).toFixed(1)}`).join(" ");
}

function addCurrencyAmount(bucket, currency, value) {
  const code = currency || state.baseCurrency;
  bucket[code] = (bucket[code] || 0) + Number(value || 0);
}

function aggregateTrendAccounts(accounts) {
  const byDate = {};
  accounts.forEach((account) => {
    (account.points || []).forEach((point) => {
      const currency = account.account.currency || state.baseCurrency;
      const bucket = byDate[point.date] || { date: point.date, value: 0, cash: 0, profit: 0, value_by_currency: {}, cash_by_currency: {}, profit_by_currency: {} };
      bucket.value += normalizedAmount(point.value, currency);
      bucket.cash += normalizedAmount(point.cash, currency);
      bucket.profit += normalizedAmount(point.profit, currency);
      addCurrencyAmount(bucket.value_by_currency, currency, point.value);
      addCurrencyAmount(bucket.cash_by_currency, currency, point.cash);
      addCurrencyAmount(bucket.profit_by_currency, currency, point.profit);
      byDate[point.date] = bucket;
    });
  });
  return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));
}

function trendAccountOptions() {
  return [{ id: "total", label: "All accounts" }].concat((state.accountTrend.accounts || []).map((account) => ({
    id: account.account.id,
    label: accountLabel(account.account),
  })));
}

function selectedTrendPoints() {
  const selected = state.dashboard?.accountTrendAccountId || "total";
  if (selected === "total") return aggregateTrendAccounts(state.accountTrend.accounts || []);
  const account = (state.accountTrend.accounts || []).find((item) => item.account.id === selected);
  return trendSeriesForAccount(account);
}

function trendSeriesForAccount(account) {
  if (!account) return [];
  const currency = account.account.currency || state.baseCurrency;
  return (account.points || []).map((point) => ({
    ...point,
    value: normalizedAmount(point.value, currency),
    cash: normalizedAmount(point.cash, currency),
    profit: normalizedAmount(point.profit, currency),
    value_by_currency: { [currency]: Number(point.value || 0) },
    cash_by_currency: { [currency]: Number(point.cash || 0) },
    profit_by_currency: { [currency]: Number(point.profit || 0) },
  })).sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

function localTrendAmount(point, field) {
  const values = point?.[`${field}_by_currency`] || {};
  return Object.entries(values)
    .filter(([currency]) => currency !== state.baseCurrency)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([currency, value]) => money(value, currency, 0))
    .join(" · ");
}

function trendAmount(point, field) {
  const base = money(point?.[field], state.baseCurrency, 0);
  const local = localTrendAmount(point, field);
  return local ? `${base} (${local})` : base;
}

function renderAccountValueTrend() {
  const accounts = state.accountTrend.accounts || [];
  const options = trendAccountOptions();
  if (!accounts.length) {
    return `
      <div class="chart-card account-trend-card">
        <div class="chart-header">
          <div class="chart-title">Account value trend</div>
        </div>
        <div class="empty">No account history in this date range</div>
      </div>`;
  }
  if (!options.some((option) => option.id === state.dashboard.accountTrendAccountId)) {
    state.dashboard.accountTrendAccountId = "total";
  }
  const points = selectedTrendPoints();
  if (!points.length) {
    return `
      <div class="chart-card account-trend-card">
        <div class="chart-header">
          <div class="chart-title">Account value trend</div>
          <select data-account-trend-select title="Account trend source">
            ${options.map((option) => `<option value="${esc(option.id)}"${option.id === state.dashboard.accountTrendAccountId ? " selected" : ""}>${esc(option.label)}</option>`).join("")}
          </select>
        </div>
        <div class="empty">No account history in this date range</div>
      </div>`;
  }
  const width = 640;
  const height = 230;
  const padLeft = 76;
  const padRight = 22;
  const padTop = 22;
  const padBottom = 42;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;
  const accountSeries = state.dashboard.accountTrendAccountId === "total"
    ? accounts.map((account) => ({
      id: account.account.id,
      label: accountLabel(account.account),
      points: trendSeriesForAccount(account),
    })).filter((series) => series.points.length)
    : [];
  const selectedLabel = options.find((option) => option.id === state.dashboard.accountTrendAccountId)?.label || "All accounts";
  const valueNumbers = points.map((point) => Number(point.value || 0));
  const cashNumbers = points.map((point) => Number(point.cash || 0)).filter((value) => Math.abs(value) > 0.0001);
  const accountValueNumbers = accountSeries.flatMap((series) => series.points.map((point) => Number(point.value || 0)));
  const domainValues = valueNumbers.concat(cashNumbers, accountValueNumbers);
  const rawMin = Math.min(...domainValues);
  const rawMax = Math.max(...domainValues, 1);
  const rawSpan = rawMax - rawMin || Math.max(Math.abs(rawMax), 1);
  const min = rawMin >= 0 ? Math.max(0, rawMin - rawSpan * 0.08) : rawMin - rawSpan * 0.08;
  const max = rawMax + rawSpan * 0.08;
  const allCashZero = !cashNumbers.length;
  const x = (_point, index) => padLeft + (index / Math.max(1, points.length - 1)) * plotWidth;
  const yValue = (value) => padTop + plotHeight - ((Number(value || 0) - min) / (max - min || 1)) * plotHeight;
  const y = (point, field) => field === "cash" && allCashZero ? height - padBottom : yValue(point[field]);
  const valuePath = linePath(points, x, (point) => y(point, "value"));
  const cashPath = linePath(points, x, (point) => y(point, "cash"));
  const yTicks = [max, min + (max - min) * 0.67, min + (max - min) * 0.33, min];
  const xTicks = points.length <= 3
    ? points
    : [points[0], points[Math.floor((points.length - 1) / 2)], points.at(-1)];
  const accountPaths = accountSeries.map((series, index) => {
    const path = linePath(series.points, (_point, pointIndex) => x(_point, pointIndex), (point) => yValue(point.value));
    return `<path class="account-trend-account-line" d="${path}" fill="none" stroke="${colorAt(index)}"></path>`;
  }).join("");
  const last = points.at(-1) || {};
  const latestTooltip = `${selectedLabel}\nLatest total amount: ${trendAmount(last, "value")}\nLatest cash: ${trendAmount(last, "cash")}\nDate: ${last.date || ""}`;
  const valueMarkers = points.map((point, index) => {
    const cx = x(point, index);
    const cy = y(point, "value");
    const tooltip = `${point.date}\n${selectedLabel}\nTotal amount: ${trendAmount(point, "value")}`;
    return `
      <circle class="trend-hit" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="18" fill="transparent">
        <title>${esc(tooltip)}</title>
      </circle>
      <circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="3.5" fill="#21a7ff">
        <title>${esc(tooltip)}</title>
      </circle>
    `;
  }).join("");
  const cashMarkers = points.map((point, index) => {
    const cx = x(point, index);
    const cy = y(point, "cash");
    const tooltip = `${point.date}\n${selectedLabel}\nCash: ${trendAmount(point, "cash")}`;
    return `
      <circle class="trend-hit" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="18" fill="transparent">
        <title>${esc(tooltip)}</title>
      </circle>
      <circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="3" fill="#ffae18">
        <title>${esc(tooltip)}</title>
      </circle>
    `;
  }).join("");
  return `
    <div class="chart-card account-trend-card">
      <div class="chart-header">
        <div>
          <div class="chart-title">Account value trend</div>
          <small class="chart-subtitle">${esc(selectedLabel)} · Value ${esc(trendAmount(last, "value"))} · Cash ${esc(trendAmount(last, "cash"))}</small>
        </div>
        <div class="chart-legend">
          <span><i style="background:#21a7ff"></i>Total amount</span>
          <span><i style="background:#ffae18"></i>Cash</span>
          <select data-account-trend-select title="Account trend source">
            ${options.map((option) => `<option value="${esc(option.id)}"${option.id === state.dashboard.accountTrendAccountId ? " selected" : ""}>${esc(option.label)}</option>`).join("")}
          </select>
        </div>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Historic account total amount and cash">
        <defs>
          <linearGradient id="accountTrendFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stop-color="#21a7ff" stop-opacity="0.28" />
            <stop offset="100%" stop-color="#21a7ff" stop-opacity="0" />
          </linearGradient>
        </defs>
        ${yTicks.map((tick) => {
          const tickY = yValue(tick);
          return `
            <line class="chart-grid" x1="${padLeft}" y1="${tickY.toFixed(1)}" x2="${width - padRight}" y2="${tickY.toFixed(1)}"></line>
            <text class="axis-label y-axis-label" x="${padLeft - 8}" y="${(tickY + 3).toFixed(1)}">${money(tick, state.baseCurrency, 0)}</text>
          `;
        }).join("")}
        <text class="axis-title" x="16" y="${padTop + plotHeight / 2}" transform="rotate(-90 16 ${padTop + plotHeight / 2})">Amount</text>
        <line class="axis-line" x1="${padLeft}" y1="${height - padBottom}" x2="${width - padRight}" y2="${height - padBottom}"></line>
        <line class="axis-line" x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${height - padBottom}"></line>
        <path d="${valuePath} L ${x(points.at(-1) || {}, points.length - 1).toFixed(1)} ${height - padBottom} L ${padLeft} ${height - padBottom} Z" fill="url(#accountTrendFill)"></path>
        ${accountPaths}
        <path d="${valuePath}" fill="none" stroke="#21a7ff" stroke-width="4" stroke-linejoin="round"></path>
        <path d="${cashPath}" fill="none" stroke="#ffae18" stroke-width="3" stroke-linejoin="round" stroke-dasharray="7 6"></path>
        <path class="trend-hit-line" d="${valuePath}" fill="none">
          <title>${esc(latestTooltip)}</title>
        </path>
        <path class="trend-hit-line" d="${cashPath}" fill="none">
          <title>${esc(`${selectedLabel}\nCash line\nLatest cash: ${trendAmount(last, "cash")}\nDate: ${last.date || ""}`)}</title>
        </path>
        ${valueMarkers}
        ${cashMarkers}
        ${xTicks.map((point, index) => {
          const pointIndex = points.findIndex((item) => item.date === point.date);
          const tickX = x(point, pointIndex);
          const anchor = index === 0 ? "start" : index === xTicks.length - 1 ? "end" : "middle";
          return `<text class="axis-label" x="${tickX.toFixed(1)}" y="${height - 12}" text-anchor="${anchor}">${esc(point.date || "")}</text>`;
        }).join("")}
        <text class="axis-title" x="${padLeft + plotWidth / 2}" y="${height - 2}">Date</text>
      </svg>
    </div>`;
}

function renderMarketCostBars(items) {
  const top = [...items].sort((a, b) => normalizedField(b, "market_value") - normalizedField(a, "market_value")).slice(0, 7);
  const width = 360;
  const height = 170;
  const padX = 24;
  const padTop = 22;
  const padBottom = 30;
  const plotHeight = height - padTop - padBottom;
  const rows = top.map((item) => ({
    symbol: item.holding.symbol,
    market: Math.max(0, normalizedField(item, "market_value")),
    cost: Math.max(0, normalizedField(item, "cost_basis")),
    localMarket: Math.max(0, Number(item.holding.market_value || 0)),
    localCost: Math.max(0, Number(item.holding.cost_basis || 0)),
    currency: item.holding.currency || state.baseCurrency,
  }));
  const max = Math.max(...rows.flatMap((row) => [row.market, row.cost]), 1);
  const groupWidth = (width - padX * 2) / Math.max(rows.length, 1);
  const barWidth = Math.min(14, Math.max(6, groupWidth * 0.24));
  const gap = Math.min(5, Math.max(3, groupWidth * 0.08));
  const baseline = height - padBottom;
  const barHeight = (value) => {
    if (!value) return 0;
    return Math.max(3, (value / max) * plotHeight);
  };
  return `
    <div class="chart-card area-card comparison-card">
      <div class="chart-header">
        <div class="chart-title">Market vs cost basis</div>
        <div class="chart-legend" aria-hidden="true">
          <span><i class="market-key"></i>Market</span>
          <span><i class="cost-key"></i>Cost</span>
        </div>
      </div>
      <svg viewBox="0 0 360 170" role="img" aria-label="Market value compared with cost basis">
        <defs>
          <linearGradient id="barMarket" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stop-color="#8c86ff" />
            <stop offset="100%" stop-color="#5b58f6" />
          </linearGradient>
          <linearGradient id="barCost" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stop-color="#f5f6fb" />
            <stop offset="100%" stop-color="#d9dde8" />
          </linearGradient>
        </defs>
        <line class="chart-grid" x1="${padX}" y1="${padTop}" x2="${width - padX}" y2="${padTop}"></line>
        <line class="chart-grid" x1="${padX}" y1="${padTop + plotHeight / 2}" x2="${width - padX}" y2="${padTop + plotHeight / 2}"></line>
        <line class="axis-line" x1="${padX}" y1="${baseline}" x2="${width - padX}" y2="${baseline}"></line>
        ${rows.map((row, index) => {
          const center = padX + groupWidth * index + groupWidth / 2;
          const marketHeight = barHeight(row.market);
          const costHeight = barHeight(row.cost);
          const marketX = center - barWidth - gap / 2;
          const costX = center + gap / 2;
          const localTooltip = row.currency !== state.baseCurrency
            ? `\nLocal market: ${money(row.localMarket, row.currency, 0)}\nLocal cost: ${money(row.localCost, row.currency, 0)}`
            : "";
          const tooltip = `${row.symbol}\nMarket: ${money(row.market, state.baseCurrency, 0)}\nCost: ${money(row.cost, state.baseCurrency, 0)}${localTooltip}`;
          return `
            <g>
              <title>${esc(tooltip)}</title>
              <rect class="comparison-bar market-bar" x="${marketX.toFixed(1)}" y="${(baseline - marketHeight).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${marketHeight.toFixed(1)}" rx="4" fill="url(#barMarket)"></rect>
              <rect class="comparison-bar cost-bar" x="${costX.toFixed(1)}" y="${(baseline - costHeight).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${costHeight.toFixed(1)}" rx="4" fill="url(#barCost)"></rect>
              <text x="${center.toFixed(1)}" y="164">${esc(row.symbol.slice(0, 5))}</text>
            </g>
          `;
        }).join("")}
      </svg>
    </div>`;
}

function renderDonut(groups, title, centerLabel, total, centerSub = ["TOP", "ASSET"]) {
  const circumference = 2 * Math.PI * 42;
  let offset = 0;
  return `
    <div class="chart-card donut-card">
      <div class="chart-title">${esc(title)}</div>
      <svg viewBox="0 0 130 130" role="img" aria-label="${esc(title)}">
        <circle cx="65" cy="65" r="42" fill="none" stroke="#202a3f" stroke-width="14"></circle>
        ${groups.slice(0, 6).map((group, index) => {
          const dash = total ? (group.value / total) * circumference : 0;
          const circle = `<circle cx="65" cy="65" r="42" fill="none" stroke="${colorAt(index)}" stroke-width="14" stroke-dasharray="${dash.toFixed(1)} ${(circumference - dash).toFixed(1)}" stroke-dashoffset="${(-offset).toFixed(1)}" transform="rotate(-90 65 65)"></circle>`;
          offset += dash;
          return circle;
        }).join("")}
        <circle cx="65" cy="65" r="28" fill="#171c24" stroke="#2f3848" stroke-width="2"></circle>
        <text x="65" y="60" class="donut-center">${esc(centerLabel)}</text>
        <text x="65" y="76" class="donut-sub">${esc(centerSub[0] || "")}</text>
        <text x="65" y="88" class="donut-sub">${esc(centerSub[1] || "")}</text>
      </svg>
      <div class="donut-legend">
        ${groups.slice(0, 3).map((group, index) => `
          <span><i style="background:${colorAt(index)}"></i>${esc(group.label)} ${Math.round(group.value / total * 100)}%</span>
        `).join("")}
      </div>
    </div>`;
}

function renderCurrencyAllocation(groups, total) {
  const topPercent = Math.round((groups[0]?.value || 0) / total * 100);
  return renderDonut(groups, "Currency allocation", `${topPercent}%`, total, ["TOP", "CURRENCY"]);
}

function renderMiniBars(items) {
  const top = [...items].sort((a, b) => normalizedField(b, "market_value") - normalizedField(a, "market_value")).slice(0, 12);
  const max = Math.max(...top.map((item) => normalizedField(item, "market_value")), 1);
  return `
    <div class="chart-card bars-card">
      <div class="chart-header">
        <div class="chart-title">Top holdings</div>
        <div class="chart-legend" aria-hidden="true">
          <span><i style="background:#21a7ff"></i>Market value</span>
        </div>
      </div>
      <div class="mini-bars">
        ${top.map((item, index) => {
          const value = normalizedField(item, "market_value");
          const localValue = Number(item.holding.market_value || 0);
          const currency = item.holding.currency || state.baseCurrency;
          const localTooltip = currency !== state.baseCurrency ? `\nLocal value: ${money(localValue, currency, 0)}` : "";
          const tooltip = `${item.holding.symbol}\nMarket value: ${money(value, state.baseCurrency, 0)}${localTooltip}`;
          return `<div class="mini-bar-wrap" title="${esc(tooltip)}">
            <div class="mini-bar" style="height:${Math.max(6, (value / max) * 112)}px;background:${colorAt(index)}"></div>
            <span>${String(index + 1).padStart(2, "0")}</span>
          </div>`;
        }).join("")}
      </div>
      <div class="mini-bars-legend">
        ${top.slice(0, 6).map((item, index) => `
          <span title="${esc(item.holding.symbol)}"><i style="background:${colorAt(index)}"></i>${String(index + 1).padStart(2, "0")} ${esc(item.holding.symbol.slice(0, 8))}</span>
        `).join("")}
      </div>
    </div>`;
}

function renderCompleteness(items) {
  const total = items.length;
  const metrics = [
    ["Price history", "price history", "#21a7ff"],
    ["Profit trend", "profit", "#ffae18"],
    ["Dividend trend", "dividend", "#9b4dff"],
  ].map(([label, missingLabel]) => {
    const ok = items.filter((item) => !item.missing.includes(missingLabel)).length;
    return { label, ok, total, percent: total ? Math.round((ok / total) * 100) : 0 };
  });
  return `
    <div class="chart-card meters-card">
      <div class="chart-title">Provider data coverage</div>
      <div class="coverage-list">
        ${metrics.map((metric, index) => `
          <div class="coverage-row" title="${esc(`${metric.ok} of ${metric.total} positions have ${metric.label.toLowerCase()} data`)}">
            <div class="coverage-row-head">
              <span>${esc(metric.label)}</span>
              <b>${metric.percent}%</b>
            </div>
            <div class="coverage-bar">
              <i style="width:${metric.percent}%;--bar-color:${colorAt(index)}"></i>
            </div>
            <small>${metric.ok}/${metric.total} positions with data</small>
          </div>
        `).join("")}
      </div>
    </div>`;
}

function renderProfitBars(items) {
  const top = [...items]
    .sort((a, b) => Math.abs(normalizedField(b, "unrealized_profit")) - Math.abs(normalizedField(a, "unrealized_profit")))
    .slice(0, 10);
  const total = sum(items.map((item) => normalizedField(item, "unrealized_profit")));
  const maxAbs = Math.max(...top.map((item) => Math.abs(normalizedField(item, "unrealized_profit"))), 1);
  const width = 430;
  const height = 200;
  const padLeft = 38;
  const padRight = 26;
  const baseline = 102;
  const topGuide = 42;
  const bottomGuide = 158;
  const barSlot = (width - padLeft - padRight) / Math.max(1, top.length);
  const barWidth = Math.min(22, Math.max(8, barSlot * 0.54));
  const gainColor = "#726dff";
  const lossColor = "#ff5f6d";
  return `
    <div class="chart-card line-card">
      <div class="chart-header">
        <div class="chart-title">Unrealized P/L by holding</div>
        <div class="chart-legend"><span><i style="background:${gainColor}"></i>Gain</span><span><i style="background:${lossColor}"></i>Loss</span></div>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Unrealized profit and loss by holding">
        <line x1="${padLeft}" y1="${topGuide}" x2="${width - padRight}" y2="${topGuide}"></line>
        <line x1="${padLeft}" y1="${baseline}" x2="${width - padRight}" y2="${baseline}" class="axis-line"></line>
        <line x1="${padLeft}" y1="${bottomGuide}" x2="${width - padRight}" y2="${bottomGuide}"></line>
        <text x="${padLeft}" y="24" class="profit-total">Total ${fmt(total, 0)}</text>
        ${top.map((item, index) => {
          const value = normalizedField(item, "unrealized_profit");
          const localValue = Number(item.holding.unrealized_profit || 0);
          const currency = item.holding.currency || state.baseCurrency;
          const localTooltip = currency !== state.baseCurrency ? `\nLocal P/L: ${money(localValue, currency, 0)}` : "";
          const tooltip = `${item.holding.symbol}\nUnrealized P/L: ${money(value, state.baseCurrency, 0)}${localTooltip}`;
          const barHeight = Math.max(3, Math.abs(value) / maxAbs * 56);
          const x = padLeft + index * barSlot + (barSlot - barWidth) / 2;
          const y = value >= 0 ? baseline - barHeight : baseline;
          const color = value >= 0 ? gainColor : lossColor;
          const labelY = value >= 0 ? Math.max(topGuide - 8, y - 8) : Math.min(bottomGuide + 18, y + barHeight + 16);
          return `
          <g>
            <title>${esc(tooltip)}</title>
            <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="4" fill="${color}" opacity="${value >= 0 ? "1" : "0.94"}"></rect>
            <text x="${(x + barWidth / 2).toFixed(1)}" y="${labelY.toFixed(1)}">${fmt(value, 0)}</text>
          </g>
        `;
        }).join("")}
        ${top.map((item, index) => `<text x="${(padLeft + index * barSlot + barSlot / 2).toFixed(1)}" y="184">${esc(item.holding.symbol.slice(0, 5))}</text>`).join("")}
      </svg>
    </div>`;
}

function renderRadialRings(groups, total) {
  return `
    <div class="chart-card rings-card">
      <div class="chart-title">Currency allocation</div>
      <svg viewBox="0 0 210 170" role="img" aria-label="Currency allocation rings">
        ${groups.slice(0, 5).map((group, index) => {
          const r = 66 - index * 10;
          const circumference = 2 * Math.PI * r;
          const dash = total ? (group.value / total) * circumference : 0;
          return `
            <circle cx="105" cy="85" r="${r}" fill="none" stroke="#202a3f" stroke-width="8"></circle>
            <circle cx="105" cy="85" r="${r}" fill="none" stroke="${colorAt(index)}" stroke-width="8" stroke-dasharray="${dash.toFixed(1)} ${(circumference - dash).toFixed(1)}" transform="rotate(-90 105 85)"></circle>
            <text x="28" y="${28 + index * 17}">${esc(group.label)}</text>
            <text x="150" y="${28 + index * 17}">${Math.round((group.value / total) * 100)}%</text>
          `;
        }).join("")}
      </svg>
    </div>`;
}

function renderBubbles(items) {
  const symbols = new Set(items.map((item) => item.holding.symbol)).size;
  const positive = items.filter((item) => Number(item.holding.unrealized_profit) > 0).length;
  const gaps = missingStats(items);
  return `
    <div class="chart-card bubbles-card">
      ${[
        ["Positions", items.length, "#21a7ff", "holdings"],
        ["Securities", symbols, "#21a7ff", "unique symbols"],
        ["Winners", positive, "#ffae18", "positive P/L"],
        ["Data gaps", gaps.total, "#9b4dff", `${gaps.positions}/${items.length} positions`],
      ].map(([label, value, color, detail]) => `
        <div class="bubble-stat" style="--bubble-color:${color}" title="${esc(label === "Data gaps" ? (gaps.topLabels || "No missing analytics fields") : detail)}">
          <span>${esc(label)}</span>
          <i aria-hidden="true"><strong>${esc(value)}</strong></i>
          <small>${esc(detail)}</small>
        </div>
      `).join("")}
    </div>`;
}

function renderAnalytics(items) {
  const board = $("analyticsBoard");
  if (!board) return;
  if (!state.dashboard) loadDashboardSettings();
  renderDashboardControls();
  if (!items.length) {
    board.innerHTML = '<div class="empty">No portfolio data</div>';
    return;
  }
  const total = sum(items.map((item) => normalizedField(item, "market_value"))) || 1;
  const assetGroups = groupValues(items, (item) => item.holding.asset_class);
  const currencyGroups = groupValues(items, (item) => item.holding.currency);
  const renderers = {
    account_trend: () => renderAccountValueTrend(),
    market_cost: () => renderMarketCostBars(items),
    asset_mix: () => renderDonut(assetGroups, "Asset mix", `${Math.round((assetGroups[0]?.value || 0) / total * 100)}%`, total),
    top_holdings: () => renderMiniBars(items),
    coverage: () => renderCompleteness(items),
    currency: () => renderCurrencyAllocation(currencyGroups, total),
    profit: () => renderProfitBars(items),
    snapshot: () => renderBubbles(items),
  };
  if (state.dashboard.edit) {
    board.innerHTML = renderDashboardEditor(renderers);
    return;
  }
  const visible = visibleDashboardWidgets();
  board.innerHTML = visible.length
    ? visible.map((widget) => withDashboardToolbar(widget, renderers[widget.id]())).join("")
    : '<div class="empty">No dashboard graphs selected</div>';
}

function renderPortfolio(items) {
  renderSummary(items);
  renderFundsOverview();
  renderAnalytics(items);
  renderRows(items);
}

function valueOf(id) {
  return $(id)?.value?.trim() || "";
}

function accountLabel(account) {
  const parts = [account.management_company, account.username, account.account_id]
    .map(cleanSourceLabel)
    .filter(Boolean)
    .filter((value, index, values) => values.indexOf(value) === index);
  return parts.join(" · ") || account.id;
}

function accountOptionHtml(account) {
  return `<option value="${esc(account.id)}">${esc(accountLabel(account))}</option>`;
}

function isImportedAccount(account) {
  return String(account.account_id || "").startsWith("import-") || String(account.source || "").includes("import") || String(account.comments || "").toLowerCase().includes("imported");
}

function refreshLocalAccountSelects() {
  const accountOptions = '<option value="">All local accounts</option>' + state.localAccounts.map(accountOptionHtml).join("");
  ["securityAccount", "reportAccount"].forEach((id) => {
    const select = $(id);
    if (!select) return;
    const current = select.value;
    select.innerHTML = id === "securityAccount" ? state.localAccounts.map(accountOptionHtml).join("") : accountOptions;
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  });
  const historySelect = $("historyAccount");
  if (historySelect) {
    const current = historySelect.value;
    historySelect.innerHTML = '<option value="">Choose account</option>' + state.localAccounts.map(accountOptionHtml).join("");
    if ([...historySelect.options].some((option) => option.value === current)) historySelect.value = current;
  }
}

async function loadLocalAccounts() {
  const data = await api("/api/local/accounts");
  state.localAccounts = data.items || [];
  refreshLocalAccountSelects();
  const importedAccounts = state.localAccounts.filter(isImportedAccount).length;
  const manualAccounts = state.localAccounts.length - importedAccounts;
  $("accountsSummary").innerHTML = [
    ["Imported accounts", importedAccounts, "Accounts synced from the configured import source and protected from manual delete here"],
    ["Manual accounts", manualAccounts, "Accounts created directly in this dashboard"],
    ["Attached securities", data.sync?.attached_positions ?? data.status?.transactions ?? 0, "Imported securities linked to local account records"],
    ["Local DB records", data.status?.transactions ?? 0, "Stored security transactions and imported position links"],
  ].map(([label, value, tooltip]) => `<div class="stat" title="${esc(tooltip)}"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join("");
  $("accountsList").innerHTML = state.localAccounts.length ? state.localAccounts.map((account) => `
    <div class="stack-item management-item">
      <b>${esc(accountLabel(account))}</b>
      <span>${esc(account.type)} · ${esc(account.location)} · ${esc(account.currency)} · ${isImportedAccount(account) ? "Imported" : "Manual"}</span>
      ${isImportedAccount(account) ? '<span class="badge ok" title="Synced from the configured import source. Refresh with Sync import.">Synced</span>' : `<button class="secondary compact-button" type="button" data-delete-account="${esc(account.id)}" title="Remove this manual account and its local transactions">Remove</button>`}
      <div class="sub">Initial cash ${fmt(account.initial_cash)}${(account.persons || []).length ? ` · ${(account.persons || []).map(personLabel).map(esc).join(" · ")}` : ""} · ${esc(cleanSourceLabel(account.comments) || "No comments")}</div>
    </div>
  `).join("") : '<div class="empty">No local accounts yet</div>';
  renderPersonLists();
}

async function saveLocalAccount() {
  const payload = {
    type: valueOf("localAccountType"),
    location: valueOf("localAccountLocation") || "USA",
    currency: valueOf("localAccountCurrency") || "USD",
    initial_cash: valueOf("localInitialCash") || 0,
    username: valueOf("localUsername"),
    account_id: valueOf("localAccountId"),
    management_company: valueOf("localManagementCompany"),
    persons: state.localAccountPersons.map((person) => ({ ...person })),
    comments: valueOf("localAccountComments"),
  };
  await api("/api/local/accounts", { method: "POST", body: JSON.stringify(payload) });
  $("accountsStatus").textContent = "Account saved";
  ["localInitialCash", "localUsername", "localAccountId", "localManagementCompany", "localAccountComments"].forEach((id) => { $(id).value = ""; });
  state.localAccountPersons = [];
  renderPersonLists();
  await loadLocalAccounts();
  await loadPortfolio();
}

async function importSourceToLocal() {
  $("accountsStatus").textContent = "Importing holdings";
  const result = await api("/api/local/import/source", { method: "POST", body: "{}" });
  $("accountsStatus").textContent = `Imported ${result.positions} positions and ${result.accounts} accounts`;
  await loadLocalAccounts();
  await loadLocalSecurities();
  await loadLocalPrices();
  await loadPortfolio();
}

function transactionCashImpact(tx) {
  const value = Number(tx.quantity || 0) * Number(tx.price || 0);
  if (tx.action === "BUY") return -value;
  if (tx.action === "SELL" || tx.action === "SHORT") return value;
  return 0;
}

function cleanSecuritySymbol(value) {
  const text = String(value || "").trim().toUpperCase();
  return text.startsWith("GF_") ? text.slice(3) : text;
}

function instrumentLabel(item) {
  const name = item.name && item.name !== item.symbol ? ` · ${item.name}` : "";
  const derivative = item.instrument_type === "OPTION"
    ? ` · ${item.option_type} ${fmt(item.strike_price, 4)} · exp ${item.expiration_date}`
    : item.instrument_type === "FUTURE"
      ? ` · exp ${item.expiration_date}`
      : "";
  return `${item.symbol}${name} · ${item.instrument_type}${derivative}`;
}

function instrumentById(id) {
  return state.manualSecurities.find((item) => item.id === id);
}

function refreshManualSecuritySelects() {
  const options = '<option value="">Free symbol / not defined</option>' + state.manualSecurities
    .map((item) => `<option value="${esc(item.id)}">${esc(instrumentLabel(item))}</option>`)
    .join("");
  ["securityKnownInstrument", "priceKnownInstrument"].forEach((id) => {
    const select = $(id);
    if (!select) return;
    const current = select.value;
    select.innerHTML = options;
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  });
}

function applyInstrumentToForm(item, prefix) {
  if (!item) return;
  $(`${prefix}Symbol`).value = item.symbol;
  $(`${prefix}Market`).value = item.stock_market;
  $(`${prefix}AssetClass`).value = item.asset_class;
  if (prefix === "price") {
    $("priceLocation").value = item.location || "USA";
    $("priceCurrency").value = item.currency || "USD";
  }
  if (prefix === "security") {
    $("securityAllowManual").checked = true;
  }
}

function fillPriceFormFromFocus() {
  const focus = state.priceFocus;
  if (!focus) return;
  $("priceSymbol").value = cleanSecuritySymbol(focus.symbol);
  $("priceMarket").value = focus.stock_market || "MANUAL";
  $("priceAssetClass").value = focus.asset_class || "EQUITY";
  $("priceLocation").value = focus.location || "USA";
  $("priceCurrency").value = focus.currency || "USD";
  $("priceDate").value = todayString();
}

function renderPriceFocusBar() {
  const bar = $("priceFocusBar");
  if (!bar) return;
  const focus = state.priceFocus;
  bar.hidden = !focus;
  if (!focus) {
    bar.innerHTML = "";
    return;
  }
  bar.innerHTML = `
    <span>Editing history for <b>${esc(focus.symbol)}</b> · ${esc(focus.stock_market || "MANUAL")} · ${esc(focus.asset_class || "")} · ${esc(focus.currency || "")}</span>
    <button class="secondary compact-button" type="button" data-clear-price-focus>Show all prices</button>
  `;
}

function priceMatchesFocus(price) {
  const focus = state.priceFocus;
  if (!focus) return true;
  return cleanSecuritySymbol(price.symbol) === cleanSecuritySymbol(focus.symbol)
    && String(price.stock_market || "").toUpperCase() === String(focus.stock_market || "").toUpperCase();
}

function openPriceHistoryForSecurity(dataset) {
  state.priceFocus = {
    symbol: cleanSecuritySymbol(dataset.priceHistorySymbol || dataset.securityDetailSymbol),
    stock_market: String(dataset.priceHistoryMarket || dataset.securityDetailMarketKey || "MANUAL").toUpperCase(),
    asset_class: dataset.priceHistoryAsset || dataset.securityDetailAsset || "EQUITY",
    currency: dataset.priceHistoryCurrency || dataset.securityDetailCurrency || "USD",
    location: dataset.priceHistoryLocation || dataset.securityDetailLocation || "USA",
  };
  fillPriceFormFromFocus();
  openModal("pricesModal");
}

function securityMatches(item, symbol, market) {
  const h = item.holding || item;
  return cleanSecuritySymbol(h.symbol) === cleanSecuritySymbol(symbol)
    && String(holdingMarketKey(h)).toUpperCase() === String(market || "").toUpperCase();
}

function transactionMatchesSecurity(tx, detail) {
  return cleanSecuritySymbol(tx.symbol) === cleanSecuritySymbol(detail.symbol)
    && String(tx.stock_market || "").toUpperCase() === String(detail.market_key || detail.stock_market || "").toUpperCase();
}

function priceMatchesSecurity(price, detail) {
  return cleanSecuritySymbol(price.symbol) === cleanSecuritySymbol(detail.symbol)
    && String(price.stock_market || "").toUpperCase() === String(detail.market_key || detail.stock_market || "").toUpperCase();
}

async function openSecurityDetail(dataset) {
  const symbol = cleanSecuritySymbol(dataset.securityDetailSymbol);
  const marketKey = String(dataset.securityDetailMarketKey || "MANUAL").toUpperCase();
  const item = state.items.find((candidate) => securityMatches(candidate, symbol, marketKey));
  const h = item?.holding || {};
  state.securityDetail = {
    item,
    symbol,
    market_key: marketKey,
    stock_market: dataset.securityDetailStockMarket || stockMarketDisplay(h, marketKey),
    data_provider: dataset.securityDetailProvider || dataProviderDisplay(item || {}, h, marketKey),
    asset_class: dataset.securityDetailAsset || h.asset_class || "EQUITY",
    currency: dataset.securityDetailCurrency || h.currency || "USD",
    location: dataset.securityDetailLocation || h.country || h.location || "USA",
  };
  state.securityChartStartDate = clampedHistoryDate(state.securityChartStartDate);
  if ($("securityChartStartDate")) $("securityChartStartDate").value = state.securityChartStartDate;
  $("detailPriceDate").value = todayString();
  $("detailPriceInput").value = "";
  $("detailPriceComments").value = "";
  openModal("securityDetailModal");
  await loadSecurityDetail();
}

async function loadSecurityDetail() {
  const detail = state.securityDetail;
  if (!detail) return;
  const params = new URLSearchParams({
    symbol: detail.symbol,
    stock_market: detail.market_key,
    period: state.securityChartPeriod || "1y",
  });
  if (state.securityChartStartDate) params.set("date_from", state.securityChartStartDate);
  const [transactions, prices, history] = await Promise.all([
    api("/api/local/securities"),
    api("/api/local/prices"),
    api(`/api/security/history?${params}`),
  ]);
  state.localTransactions = transactions.items || [];
  state.localPrices = prices.items || [];
  state.securityHistory = history.points || [];
  renderSecurityDetail();
}

function renderSecurityDetail() {
  const detail = state.securityDetail;
  if (!detail) return;
  const h = detail.item?.holding || {};
  $("securityDetailTitle").textContent = `${detail.symbol} overview`;
  $("securityDetailOverview").innerHTML = [
    ["Name", h.name || detail.symbol],
    ["Stock market", detail.stock_market, "The exchange/market where the security trades. This is not the API provider."],
    ["Data provider", detail.data_provider, "Where the market data was read from."],
    ["Type", h.asset_class || detail.asset_class],
    ["Currency", h.currency || detail.currency],
    ["Quantity", fmt(h.quantity || 0, 4)],
    ["Market value", money(h.market_value || 0, h.currency || detail.currency)],
    ["Cost basis", money(h.cost_basis || 0, h.currency || detail.currency)],
    ["Holding profit (open)", signedMoney(h.unrealized_profit || 0, h.currency || detail.currency), "Profit/loss on the quantity still held. It changes with the current price."],
    ["Closed profit", signedMoney(h.realized_profit || 0, h.currency || detail.currency), "Profit/loss already recorded by sell, cover, dividend, interest, or fee transactions."],
    ["Account", cleanSourceLabel(h.account || "")],
  ].map(([label, value, title]) => `<div class="security-kpi" title="${esc(title || "")}"><span>${esc(label)}</span><b>${esc(value || "∅")}</b></div>`).join("");
  const txs = state.localTransactions.filter((tx) => transactionMatchesSecurity(tx, detail));
  $("securityDetailTransactions").innerHTML = txs.length ? txs.map((tx) => `
    <div class="stack-item management-item">
      <b>${esc(tx.action)} ${fmt(tx.quantity, 4)}</b>
      <span>${esc(tx.trade_date)} · input ${fmt(tx.price_input, 4)} · ${esc(tx.currency)} ${fmt(tx.price, 4)}</span>
      <div class="sub">${transactionCashImpact(tx) ? `Cash ${signedMoney(transactionCashImpact(tx), tx.currency)}` : "No cash movement"} · ${esc(cleanSourceLabel(tx.management_company || ""))} ${esc(cleanSourceLabel(tx.account_id || ""))}${tx.comments ? ` · ${esc(cleanSourceLabel(tx.comments))}` : ""}</div>
    </div>
  `).join("") : '<div class="empty">No transactions for this security</div>';
  const prices = state.localPrices.filter((price) => priceMatchesSecurity(price, detail));
  $("securityDetailPrices").innerHTML = prices.length ? prices.map((price) => `
    <div class="stack-item management-item">
      <b>${esc(price.price_date)}</b>
      <span>${fmt(price.price_input, 4)} · ${esc(price.currency)} ${fmt(price.price, 4)}</span>
      <button class="secondary compact-button" type="button" data-delete-price="${esc(price.id)}">Remove</button>
      <div class="sub">${esc(price.asset_class)} · ${esc(price.location)}${price.comments ? ` · ${esc(price.comments)}` : ""}</div>
    </div>
  `).join("") : '<div class="empty">No saved price history for this security</div>';
  renderSecurityChart();
}

function renderSecurityChart() {
  document.querySelectorAll("[data-security-chart-period]").forEach((button) => {
    button.classList.toggle("active", button.dataset.securityChartPeriod === state.securityChartPeriod);
  });
  if ($("securityChartStartDate")) $("securityChartStartDate").value = clampedHistoryDate(state.securityChartStartDate);
  const frame = $("securityDetailChart");
  const points = (state.securityHistory || [])
    .map((point) => ({ date: point.date, price: Number(point.price || 0) }))
    .filter((point) => point.date && Number.isFinite(point.price) && point.price > 0);
  if (!points.length) {
    frame.innerHTML = '<div class="empty">No price history for this period</div>';
    return;
  }
  const width = 760;
  const height = 230;
  const padTop = 24;
  const padRight = 30;
  const padBottom = 36;
  const padLeft = 58;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;
  const min = Math.min(...points.map((point) => point.price));
  const max = Math.max(...points.map((point) => point.price));
  const span = max - min || 1;
  const mid = min + span / 2;
  const x = (index) => padLeft + (index / Math.max(points.length - 1, 1)) * plotWidth;
  const y = (price) => padTop + ((max - price) / span) * plotHeight;
  const d = points.map((point, index) => `${index ? "L" : "M"} ${x(index).toFixed(1)} ${y(point.price).toFixed(1)}`).join(" ");
  const first = points[0];
  const middle = points[Math.floor((points.length - 1) / 2)];
  const middleX = x(Math.floor((points.length - 1) / 2));
  const last = points.at(-1);
  const change = last.price - first.price;
  const changePct = first.price ? (change / Math.abs(first.price)) * 100 : 0;
  const cls = change > 0 ? "positive" : change < 0 ? "negative" : "neutral";
  const lastX = x(points.length - 1);
  const lastY = y(last.price);
  const calloutWidth = 108;
  const calloutHeight = 36;
  const calloutX = Math.max(padLeft + 4, Math.min(width - padRight - calloutWidth, lastX - calloutWidth - 10));
  const calloutY = lastY < height / 2
    ? Math.min(height - padBottom - calloutHeight - 4, lastY + 18)
    : Math.max(padTop + 4, lastY - calloutHeight - 18);
  const calloutTextColor = change > 0 ? "#45e38a" : change < 0 ? "#ff5b73" : "#58a6ff";
  frame.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Security price history">
      ${[max, mid, min].map((value) => `<line x1="${padLeft}" y1="${y(value).toFixed(1)}" x2="${width - padRight}" y2="${y(value).toFixed(1)}" stroke="#1e2835" stroke-dasharray="5 7" />`).join("")}
      <line x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${height - padBottom}" stroke="#344052" />
      <line x1="${padLeft}" y1="${height - padBottom}" x2="${width - padRight}" y2="${height - padBottom}" stroke="#344052" />
      <line x1="${middleX.toFixed(1)}" y1="${height - padBottom}" x2="${middleX.toFixed(1)}" y2="${(height - padBottom + 5).toFixed(1)}" stroke="#344052" />
      ${[max, mid, min].map((value) => `<text x="${padLeft - 8}" y="${(y(value) + 4).toFixed(1)}" fill="#9cacc2" font-size="11" font-weight="700" text-anchor="end">${esc(fmt(value, 4))}</text>`).join("")}
      <path d="${d}" fill="none" stroke="#21a7ff" stroke-width="3" />
      <g data-security-hover-marker hidden>
        <line data-security-hover-line x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${height - padBottom}" stroke="#8fb7e8" stroke-width="1" stroke-dasharray="4 5" opacity="0.75" />
        <circle data-security-hover-point cx="${padLeft}" cy="${height - padBottom}" r="4.5" fill="#f7f9ff" stroke="#21a7ff" stroke-width="2" />
      </g>
      <circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="4" fill="#ffb21a" />
      <rect x="${calloutX.toFixed(1)}" y="${calloutY.toFixed(1)}" width="${calloutWidth}" height="${calloutHeight}" rx="7" fill="#0b1018" stroke="#2d3543" opacity="0.96" />
      <text x="${(calloutX + calloutWidth - 9).toFixed(1)}" y="${(calloutY + 15).toFixed(1)}" fill="#dce7ff" font-size="13" font-weight="800" text-anchor="end">${esc(fmt(last.price, 4))}</text>
      <text x="${(calloutX + calloutWidth - 9).toFixed(1)}" y="${(calloutY + 30).toFixed(1)}" fill="${calloutTextColor}" font-size="11" font-weight="800" text-anchor="end">${esc(signedMoney(change, state.securityDetail?.currency || "USD"))} · ${esc(changePct.toFixed(2))}%</text>
      <text x="${padLeft}" y="${height - 10}" fill="#9cacc2" font-size="11" font-weight="700">${esc(first.date)}</text>
      <text x="${middleX.toFixed(1)}" y="${height - 10}" fill="#9cacc2" font-size="11" font-weight="700" text-anchor="middle">${esc(middle.date)}</text>
      <text x="${width - padRight}" y="${height - 10}" fill="#9cacc2" font-size="11" font-weight="700" text-anchor="end">${esc(last.date)}</text>
      <rect data-security-chart-hitbox x="${padLeft}" y="${padTop}" width="${plotWidth}" height="${plotHeight}" fill="transparent" />
    </svg>
    <div class="chart-hover-tip" hidden></div>
    <div class="sub ${cls}">${points.length} price points</div>
  `;
  attachSecurityChartHover(frame, points, { width, height, padLeft, padRight, padTop, padBottom, plotWidth, plotHeight, min, max });
}

function attachSecurityChartHover(frame, points, dims) {
  const svg = frame.querySelector("svg");
  const hitbox = frame.querySelector("[data-security-chart-hitbox]");
  const marker = frame.querySelector("[data-security-hover-marker]");
  const line = frame.querySelector("[data-security-hover-line]");
  const point = frame.querySelector("[data-security-hover-point]");
  const tip = frame.querySelector(".chart-hover-tip");
  if (!svg || !hitbox || !marker || !line || !point || !tip) return;
  const xFor = (index) => dims.padLeft + (index / Math.max(points.length - 1, 1)) * dims.plotWidth;
  const yFor = (price) => dims.padTop + ((dims.max - price) / (dims.max - dims.min || 1)) * dims.plotHeight;
  const hide = () => {
    marker.setAttribute("hidden", "");
    tip.hidden = true;
  };
  hitbox.addEventListener("mouseleave", hide);
  hitbox.addEventListener("mousemove", (event) => {
    const rect = svg.getBoundingClientRect();
    const svgX = ((event.clientX - rect.left) / rect.width) * dims.width;
    const ratio = Math.max(0, Math.min(1, (svgX - dims.padLeft) / dims.plotWidth));
    const index = Math.round(ratio * (points.length - 1));
    const selected = points[index];
    if (!selected) return;
    const px = xFor(index);
    const py = yFor(selected.price);
    marker.removeAttribute("hidden");
    line.setAttribute("x1", px.toFixed(1));
    line.setAttribute("x2", px.toFixed(1));
    point.setAttribute("cx", px.toFixed(1));
    point.setAttribute("cy", py.toFixed(1));
    tip.hidden = false;
    tip.innerHTML = `<b>${esc(selected.date)}</b><span>${esc(money(selected.price, state.securityDetail?.currency || "USD", 4))}</span>`;
    const tipLeft = Math.max(8, Math.min(rect.width - tip.offsetWidth - 8, (px / dims.width) * rect.width - tip.offsetWidth / 2));
    const tipTop = Math.max(8, Math.min(rect.height - tip.offsetHeight - 8, (py / dims.height) * rect.height - tip.offsetHeight - 12));
    tip.style.left = `${tipLeft}px`;
    tip.style.top = `${tipTop}px`;
  });
}

async function saveSecurityDetailPrice() {
  const detail = state.securityDetail;
  if (!detail) return;
  const payload = {
    symbol: detail.symbol,
    stock_market: detail.market_key,
    asset_class: detail.asset_class,
    location: detail.location || "USA",
    currency: detail.currency || "USD",
    price_input: valueOf("detailPriceInput"),
    price_date: valueOf("detailPriceDate") || todayString(),
    comments: valueOf("detailPriceComments"),
  };
  await api("/api/local/prices", { method: "POST", body: JSON.stringify(payload) });
  $("securityDetailStatus").textContent = "Price history saved";
  $("detailPriceInput").value = "";
  $("detailPriceComments").value = "";
  await loadSecurityDetail();
  await loadPortfolio();
}

function toggleManualInstrumentFields() {
  const type = valueOf("manualInstrumentType") || "STOCK";
  const isOption = type === "OPTION";
  const isDerivative = isOption || type === "FUTURE";
  document.querySelectorAll("[data-derivative-field]").forEach((node) => { node.hidden = !isDerivative; });
  document.querySelectorAll("[data-option-field]").forEach((node) => { node.hidden = !isOption; });
  if (isOption && !valueOf("manualContractMultiplier")) $("manualContractMultiplier").value = "100";
  if (!isDerivative) {
    ["manualUnderlyingSymbol", "manualExpirationDate", "manualStrikePrice", "manualContractMultiplier"].forEach((id) => { $(id).value = ""; });
  }
}

async function loadManualSecurities() {
  const data = await api("/api/local/manual-securities");
  state.manualSecurities = data.items || [];
  refreshManualSecuritySelects();
  const list = $("manualSecuritiesList");
  if (!list) return;
  list.innerHTML = state.manualSecurities.length ? state.manualSecurities.map((item) => `
    <div class="stack-item management-item">
      <b>${esc(item.symbol)}</b>
      <span>${esc(item.name || item.symbol)} · ${esc(item.instrument_type)} · ${esc(item.stock_market)} · ${esc(item.currency)}</span>
      <button class="secondary compact-button" type="button" data-use-manual-security="${esc(item.id)}">Use</button>
      <button class="secondary compact-button" type="button" data-delete-manual-security="${esc(item.id)}">Remove</button>
      <div class="sub">${esc(item.asset_class)}${item.underlying_symbol ? ` · Underlying ${esc(item.underlying_symbol)}` : ""}${item.option_type ? ` · ${esc(item.option_type)}` : ""}${item.expiration_date ? ` · Exp ${esc(item.expiration_date)}` : ""}${item.strike_price ? ` · Strike ${fmt(item.strike_price, 4)}` : ""}${item.contract_multiplier ? ` · Multiplier ${fmt(item.contract_multiplier, 4)}` : ""}${item.comments ? ` · ${esc(item.comments)}` : ""}</div>
    </div>
  `).join("") : '<div class="empty">No defined instruments yet</div>';
}

async function saveManualSecurity() {
  const payload = {
    symbol: cleanSecuritySymbol(valueOf("manualSecuritySymbol")),
    name: valueOf("manualSecurityName"),
    stock_market: valueOf("manualSecurityMarket"),
    instrument_type: valueOf("manualInstrumentType"),
    currency: valueOf("manualSecurityCurrency") || "USD",
    location: valueOf("manualSecurityLocation") || "USA",
    underlying_symbol: cleanSecuritySymbol(valueOf("manualUnderlyingSymbol")),
    option_type: valueOf("manualOptionType"),
    expiration_date: valueOf("manualExpirationDate"),
    strike_price: valueOf("manualStrikePrice") || 0,
    contract_multiplier: valueOf("manualContractMultiplier") || 0,
    comments: valueOf("manualSecurityComments"),
  };
  const saved = await api("/api/local/manual-securities", { method: "POST", body: JSON.stringify(payload) });
  $("manualSecurityStatus").textContent = `Instrument saved: ${saved.symbol}`;
  ["manualSecuritySymbol", "manualSecurityName", "manualSecurityMarket", "manualUnderlyingSymbol", "manualExpirationDate", "manualStrikePrice", "manualContractMultiplier", "manualSecurityComments"].forEach((id) => { $(id).value = ""; });
  await loadManualSecurities();
  await loadPortfolio();
}

async function loadLocalSecurities() {
  await loadManualSecurities();
  const data = await api("/api/local/securities");
  state.localTransactions = data.items || [];
  $("securitiesList").innerHTML = state.localTransactions.length ? state.localTransactions.map((tx) => `
    <div class="stack-item management-item">
      <b>${esc(tx.action)} ${esc(tx.symbol)}</b>
      <span>${fmt(tx.quantity, 4)} @ ${fmt(tx.price_input, 4)} (${esc(tx.currency)} ${fmt(tx.price, 4)})${tx.instrument_type ? ` · ${esc(tx.instrument_type)}` : ""}</span>
      <button class="secondary compact-button" type="button" data-delete-security="${esc(tx.id)}">Remove</button>
      <div class="sub">${esc(tx.stock_market)} · ${esc(tx.asset_class)}${tx.option_type ? ` · ${esc(tx.option_type)}` : ""}${tx.expiration_date ? ` · Exp ${esc(tx.expiration_date)}` : ""}${tx.strike_price ? ` · Strike ${fmt(tx.strike_price, 4)}` : ""} · ${esc(tx.trade_date)} · ${transactionCashImpact(tx) ? `Cash ${signedMoney(transactionCashImpact(tx), tx.currency)}` : "No cash movement"} · ${esc(tx.management_company || "")} ${esc(tx.account_id || "")}</div>
    </div>
  `).join("") : '<div class="empty">No manual securities yet</div>';
}

async function saveSecurity() {
  const payload = {
    account_db_id: valueOf("securityAccount"),
    action: valueOf("securityAction"),
    symbol: cleanSecuritySymbol(valueOf("securitySymbol")),
    stock_market: valueOf("securityMarket"),
    asset_class: valueOf("securityAssetClass"),
    quantity: valueOf("securityQuantity"),
    price_input: valueOf("securityPrice"),
    trade_date: valueOf("securityDate") || todayString(),
    allow_manual: $("securityAllowManual").checked,
    comments: valueOf("securityComments"),
  };
  try {
    await api("/api/local/securities", { method: "POST", body: JSON.stringify(payload) });
    $("securityStatus").textContent = "Security transaction saved";
    ["securitySymbol", "securityMarket", "securityQuantity", "securityPrice", "securityComments"].forEach((id) => { $(id).value = ""; });
    await loadLocalSecurities();
    await loadPortfolio();
  } catch (error) {
    $("securityStatus").textContent = `Error: ${error.message}. Check "Manual if not found" to save a symbol without provider validation.`;
  }
}

async function loadLocalPrices() {
  await loadManualSecurities();
  const data = await api("/api/local/prices");
  state.localPrices = data.items || [];
  fillPriceFormFromFocus();
  renderPriceFocusBar();
  const visiblePrices = state.localPrices.filter(priceMatchesFocus);
  $("pricesList").innerHTML = visiblePrices.length ? visiblePrices.map((price) => `
    <div class="stack-item management-item">
      <b>${esc(price.symbol)}</b>
      <span>${esc(price.price_date)} · ${fmt(price.price_input, 4)} (${esc(price.currency)} ${fmt(price.price, 4)})</span>
      <button class="secondary compact-button" type="button" data-delete-price="${esc(price.id)}">Remove</button>
      <div class="sub">${esc(price.stock_market)} · ${esc(price.asset_class)} · ${esc(price.location)} · ${esc(price.comments || "")}</div>
    </div>
  `).join("") : `<div class="empty">${state.priceFocus ? "No saved history for this security yet" : "No manual prices yet"}</div>`;
}

async function savePrice() {
  const payload = {
    symbol: cleanSecuritySymbol(valueOf("priceSymbol")),
    stock_market: valueOf("priceMarket"),
    asset_class: valueOf("priceAssetClass"),
    location: valueOf("priceLocation") || "USA",
    currency: valueOf("priceCurrency") || "USD",
    price_input: valueOf("priceInput"),
    price_date: valueOf("priceDate") || todayString(),
    comments: valueOf("priceComments"),
  };
  await api("/api/local/prices", { method: "POST", body: JSON.stringify(payload) });
  $("priceStatus").textContent = "Historic price saved";
  ["priceSymbol", "priceMarket", "priceInput", "priceComments"].forEach((id) => { $(id).value = ""; });
  await loadLocalPrices();
  await loadPortfolio();
}

function renderReportSummary(report) {
  $("reportsSummary").innerHTML = [
    ["Accounts", report.accounts],
    ["Holdings", report.holdings],
    ["Total value", fmt(report.value, 0)],
    ["Cash", fmt(report.cash, 0)],
    ["Securities", fmt(report.securities_value, 0)],
    ["Profit", fmt(report.profit, 0)],
    ["Monthly pension estimate", fmt(report.funds.monthly_estimate, 0)],
  ].map(([label, value]) => `<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join("");
  $("reportsDetails").innerHTML = Object.entries(report.by_account || {}).map(([account, data]) => `
    <div class="stack-item management-item">
      <b>${esc(cleanSourceLabel(account))}</b>
      <span>Value ${fmt(data.value, 0)} · Cash ${fmt(data.cash, 0)} · Profit ${fmt(data.profit, 0)}</span>
      <div class="sub">${esc(data.currency || "")}</div>
    </div>
  `).join("") || '<div class="empty">No local report data</div>';
}

function renderAccountTrend(trend) {
  const series = (trend.accounts || []).flatMap((account) => account.points.map((point) => ({ ...point, account: account.account })));
  if (!series.length) {
    $("accountTrendChart").innerHTML = '<div class="empty">No trend data for this date range</div>';
    return;
  }
  const width = 760;
  const height = 280;
  const pad = 34;
  const labelWidth = 190;
  const plotWidth = width - pad * 2 - labelWidth;
  const values = series.map((point) => Number(point.value || 0));
  const profits = series.map((point) => Number(point.profit_percent || 0));
  const minValue = Math.min(...values, 0);
  const maxValue = Math.max(...values, 1);
  const minProfit = Math.min(...profits, 0);
  const maxProfit = Math.max(...profits, 1);
  const scaleLane = (value, min, max, top, bottom) => bottom - ((value - min) / (max - min || 1)) * (bottom - top);
  const scaleValue = (value) => scaleLane(value, minValue, maxValue, 42, 124);
  const scaleProfit = (value) => scaleLane(value, minProfit, maxProfit, 170, 244);
  const pointX = (pointIndex, count) => pad + (pointIndex / Math.max(1, count - 1)) * plotWidth;
  const accountLines = (trend.accounts || []).map((account, index) => {
    const points = account.points;
    const valuePath = points.map((point, pointIndex) => `${pointIndex ? "L" : "M"} ${pointX(pointIndex, points.length)} ${scaleValue(point.value)}`).join(" ");
    const profitPath = points.map((point, pointIndex) => `${pointIndex ? "L" : "M"} ${pointX(pointIndex, points.length)} ${scaleProfit(point.profit_percent)}`).join(" ");
    const last = points.at(-1) || {};
    return `<g>
      <path d="${valuePath}" fill="none" stroke="${colorAt(index)}" stroke-width="3"></path>
      <path d="${profitPath}" fill="none" stroke="${colorAt(index + 3)}" stroke-width="2" stroke-dasharray="5 5"></path>
      <text x="${width - labelWidth + 12}" y="${44 + index * 18}">${esc(accountLabel(account.account))}</text>
      <text x="${width - labelWidth + 12}" y="${62 + index * 18}">Value ${fmt(last.value, 0)} · ${pct(last.profit_percent)}</text>
    </g>`;
  }).join("");
  $("accountTrendChart").innerHTML = `
    <div class="chart-title">Account value and profit %</div>
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Account value and percent profit trend">
      <text x="${pad}" y="24">Value</text>
      <text x="${pad}" y="154">Profit %</text>
      <line x1="${pad}" y1="42" x2="${pad + plotWidth}" y2="42"></line>
      <line x1="${pad}" y1="124" x2="${pad + plotWidth}" y2="124"></line>
      <line x1="${pad}" y1="170" x2="${pad + plotWidth}" y2="170"></line>
      <line x1="${pad}" y1="244" x2="${pad + plotWidth}" y2="244"></line>
      <text x="${pad + plotWidth + 10}" y="46">${fmt(maxValue, 0)}</text>
      <text x="${pad + plotWidth + 10}" y="128">${fmt(minValue, 0)}</text>
      <text x="${pad + plotWidth + 10}" y="174">${pct(maxProfit)}</text>
      <text x="${pad + plotWidth + 10}" y="248">${pct(minProfit)}</text>
      ${accountLines}
    </svg>`;
}

function renderHistorySnapshots() {
  $("historyList").innerHTML = state.historySnapshots.length ? state.historySnapshots.map((snapshot) => `
    <div class="stack-item management-item">
      <b>${esc(snapshot.snapshot_date)} · ${esc(cleanSourceLabel(snapshot.account_label) || snapshot.account_db_id)}</b>
      <span>Value ${fmt(snapshot.value, 0)} · Cash ${fmt(snapshot.cash, 0)} · Profit ${fmt(snapshot.profit, 0)} · ${pct(snapshot.profit_percent)}</span>
      <button class="secondary compact-button" type="button"
        data-edit-history-snapshot
        data-history-account="${esc(snapshot.account_db_id)}"
        data-history-date="${esc(snapshot.snapshot_date)}"
        data-history-value="${esc(snapshot.value)}"
        data-history-cash="${esc(snapshot.cash)}"
        data-history-profit="${esc(snapshot.profit)}"
        data-history-profit-percent="${esc(snapshot.profit_percent)}">Edit</button>
      <button class="secondary compact-button" type="button" data-delete-history-snapshot data-history-account="${esc(snapshot.account_db_id)}" data-history-date="${esc(snapshot.snapshot_date)}">Delete</button>
      <div class="sub">${esc(snapshot.account?.currency || "")} · ${esc(snapshot.source || "manual")}</div>
    </div>
  `).join("") : '<div class="empty">No saved history points in this range</div>';
}

async function loadHistorySnapshots() {
  const params = new URLSearchParams({
    account_id: valueOf("reportAccount"),
    date_from: clampedHistoryDate(valueOf("reportFrom")),
    date_to: valueOf("reportTo"),
  });
  const data = await api(`/api/local/account-snapshots?${params}`);
  state.historySnapshots = data.items || [];
  renderHistorySnapshots();
}

async function saveHistorySnapshot() {
  const accountId = valueOf("historyAccount");
  if (!accountId) {
    $("historyStatus").textContent = "Choose an account before saving history";
    return;
  }
  await api("/api/local/account-snapshots", {
    method: "POST",
    body: JSON.stringify({
      account_id: accountId,
      snapshot_date: clampedHistoryDate(valueOf("historyDate") || todayString()),
      value: valueOf("historyValue"),
      cash: valueOf("historyCash") || 0,
      profit: valueOf("historyProfit") || 0,
      profit_percent: valueOf("historyProfitPercent") || 0,
    }),
  });
  $("historyStatus").textContent = "History point saved";
  ["historyValue", "historyCash", "historyProfit", "historyProfitPercent"].forEach((id) => { $(id).value = ""; });
  await Promise.all([loadReports(), loadPortfolio()]);
}

async function captureHistorySnapshot() {
  const result = await api("/api/local/account-snapshots/capture", {
    method: "POST",
    body: JSON.stringify({ snapshot_date: clampedHistoryDate(valueOf("historyDate") || todayString()) }),
  });
  $("historyStatus").textContent = `Captured ${result.snapshots} account history points for ${result.date}`;
  await Promise.all([loadReports(), loadPortfolio()]);
}

async function loadReports() {
  const params = new URLSearchParams({
    account_id: valueOf("reportAccount"),
    account_type: valueOf("reportAccountType"),
    location: valueOf("reportLocation"),
  });
  const trendParams = new URLSearchParams({
    account_id: valueOf("reportAccount"),
    account_type: valueOf("reportAccountType"),
    location: valueOf("reportLocation"),
    date_from: clampedHistoryDate(valueOf("reportFrom")),
    date_to: valueOf("reportTo"),
  });
  const [report, trend] = await Promise.all([
    api(`/api/local/reports?${params}`),
    api(`/api/local/account-trends?${trendParams}`),
  ]);
  renderReportSummary(report);
  renderAccountTrend(trend);
  await loadHistorySnapshots();
}

async function loadFunds() {
  const data = await api("/api/local/funds");
  state.localFunds = data.items || [];
  renderFundsOverview();
  renderPensionSimulatorControls();
  $("fundsList").innerHTML = state.localFunds.length ? state.localFunds.map((fund) => `
    <div class="stack-item management-item">
      <b>${esc(fund.kind)} ${esc(fund.pension_id)}</b>
      <span>Saved ${fmt(fund.amount, 0)} · Monthly ${fmt(fund.monthly_estimate, 0)}</span>
      <button class="secondary compact-button" type="button" data-delete-fund="${esc(fund.id)}">Remove</button>
      <div class="sub">Factor ${fmt(fund.factor, 2)}${(fund.persons || []).length ? ` · ${(fund.persons || []).map(personLabel).map(esc).join(" · ")}` : ""} · ${esc(fund.comments || "")}</div>
    </div>
  `).join("") : '<div class="empty">No pension, provident, or savings funds yet</div>';
  renderPersonLists();
}

function numberValue(id) {
  const value = valueOf(id);
  return value === "" ? "" : Number(value);
}

function ageFromBirthDate(value) {
  if (!value) return "";
  const birth = new Date(`${value}T00:00:00`);
  if (Number.isNaN(birth.getTime())) return "";
  const today = new Date();
  const diffDays = (Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()) - Date.UTC(birth.getFullYear(), birth.getMonth(), birth.getDate())) / 86400000;
  return diffDays >= 0 ? Math.round((diffDays / 365.2425) * 100) / 100 : "";
}

function personLabel(person) {
  const age = person.age ?? ageFromBirthDate(person.birth_date);
  return `${person.name || "Person"} · ${person.birth_date}${age ? ` · age ${fmt(age, 1)}` : ""}`;
}

function addPersonTo(listKey, nameId, birthDateId, statusId) {
  const name = valueOf(nameId);
  const birthDate = valueOf(birthDateId);
  if (!birthDate) {
    $(statusId).textContent = "Birthday is required for a family member";
    return;
  }
  state[listKey].push({ name: name || `Person ${state[listKey].length + 1}`, birth_date: birthDate });
  $(nameId).value = "";
  $(birthDateId).value = "";
  renderPersonLists();
}

function renderPersonList(id, people, deleteAttr) {
  const frame = $(id);
  if (!frame) return;
  frame.innerHTML = people.length ? people.map((person, index) => `
    <div class="person-chip">
      <span>${esc(personLabel(person))}</span>
      <button class="secondary compact-button" type="button" ${deleteAttr}="${index}">Remove</button>
    </div>
  `).join("") : '<div class="empty compact-empty">No family members added</div>';
}

function renderPersonLists() {
  renderPersonList("localAccountPersons", state.localAccountPersons, "data-delete-local-person");
  renderPersonList("fundPersons", state.fundPersons, "data-delete-fund-person");
}

function renderPensionSimulatorControls() {
  setOptions("simKind", state.localOptions.fund_kinds || ["Pension", "Provident Fund", "Savings Fund"]);
  const fundSelect = $("simFundSource");
  if (fundSelect) {
    const current = fundSelect.value;
    fundSelect.innerHTML = '<option value="">Custom amount</option>' + state.localFunds.map((fund) => (
      `<option value="${esc(fund.id)}">${esc(fund.kind)} ${esc(fund.pension_id)} · ${money(fund.amount, state.baseCurrency, 0)}</option>`
    )).join("");
    fundSelect.value = state.localFunds.some((fund) => fund.id === current) ? current : "";
  }
  renderSimulationPersonOptions();
  renderPensionPeriods();
  renderPensionScenarios();
  renderPensionSimulationResults();
}

function selectedSimulationFund() {
  const id = valueOf("simFundSource");
  return state.localFunds.find((fund) => fund.id === id);
}

function applySimulationFund() {
  const fund = selectedSimulationFund();
  if (!fund) return;
  $("simKind").value = fund.kind;
  $("simAmount").value = fund.amount;
  $("simFactor").value = fund.factor || 200;
  renderSimulationPersonOptions();
  applySimulationPerson();
  if (!$("simName").value) $("simName").value = fund.pension_id;
}

function renderSimulationPersonOptions() {
  const select = $("simPersonSource");
  if (!select) return;
  const current = select.value;
  const people = selectedSimulationFund()?.persons || [];
  select.innerHTML = '<option value="">Custom person</option>' + people.map((person, index) => (
    `<option value="${index}">${esc(personLabel(person))}</option>`
  )).join("");
  select.value = [...select.options].some((option) => option.value === current) ? current : (people.length === 1 ? "0" : "");
}

function selectedSimulationPerson() {
  const people = selectedSimulationFund()?.persons || [];
  const raw = valueOf("simPersonSource");
  if (raw === "") return null;
  const index = Number(raw);
  return Number.isInteger(index) ? people[index] : null;
}

function applySimulationPerson() {
  const person = selectedSimulationPerson();
  if (!person) return;
  $("simBirthDate").value = person.birth_date || "";
  $("simCurrentAge").value = ageFromBirthDate(person.birth_date);
}

function currentPensionScenario() {
  const fund = selectedSimulationFund();
  const person = selectedSimulationPerson();
  const birthDate = valueOf("simBirthDate") || person?.birth_date || "";
  return {
    name: valueOf("simName") || [fund?.pension_id, person?.name].filter(Boolean).join(" ") || `Scenario ${state.pensionScenarios.length + 1}`,
    kind: valueOf("simKind") || fund?.kind || "Pension",
    birth_date: birthDate,
    person_name: person?.name || "",
    current_age: numberValue("simCurrentAge") || ageFromBirthDate(birthDate),
    retire_age: numberValue("simRetireAge"),
    amount: numberValue("simAmount") || fund?.amount || 0,
    annual_return: numberValue("simAnnualReturn") || 0,
    monthly_income: numberValue("simMonthlyIncome") || 0,
    contribution_percent: numberValue("simContributionPercent") || 0,
    monthly_deposit: numberValue("simMonthlyDeposit") || 0,
    factor: numberValue("simFactor") || fund?.factor || 200,
    income_periods: state.pensionIncomePeriods.map((period) => ({ ...period })),
  };
}

function renderPensionPeriods() {
  const frame = $("pensionPeriods");
  if (!frame) return;
  frame.innerHTML = state.pensionIncomePeriods.length ? state.pensionIncomePeriods.map((period, index) => `
    <div class="simulator-chip">
      <b>${fmt(period.from_age, 1)}-${fmt(period.to_age, 1)}</b>
      <span>Income ${money(period.monthly_income, state.baseCurrency, 0)} · ${fmt(period.contribution_percent, 2)}%${period.monthly_deposit ? ` · ${money(period.monthly_deposit, state.baseCurrency, 0)}` : ""}</span>
      <button class="secondary compact-button" type="button" data-delete-pension-period="${index}">Remove</button>
    </div>
  `).join("") : '<div class="empty compact-empty">No custom income periods. The scenario monthly income/deposit fields will be used.</div>';
}

function renderPensionScenarios() {
  const frame = $("pensionScenarios");
  if (!frame) return;
  frame.innerHTML = state.pensionScenarios.length ? state.pensionScenarios.map((scenario, index) => `
    <div class="simulator-chip">
      <b>${esc(scenario.name)}</b>
      <span>${esc(scenario.kind)} · ${fmt(scenario.current_age, 1)} to ${fmt(scenario.retire_age, 1)} · ${fmt(scenario.annual_return, 2)}% return · ${money(scenario.amount, state.baseCurrency, 0)}</span>
      <button class="secondary compact-button" type="button" data-delete-pension-scenario="${index}">Remove</button>
    </div>
  `).join("") : '<div class="empty compact-empty">No scenarios added yet</div>';
}

function renderPensionSimulationResults() {
  const frame = $("pensionSimulationResults");
  if (!frame) return;
  frame.innerHTML = state.pensionSimulationResults.length ? state.pensionSimulationResults.map((result) => {
    const lastPoints = (result.timeline || []).slice(-4);
    return `
      <div class="simulation-result-card">
        <div class="metric-head">
          <span class="metric-name">${esc(result.name)}</span>
          <span class="metric-pill ${result.kind === "Pension" ? "ok" : "neutral"}">${esc(result.kind)}</span>
        </div>
        <strong>${money(result.final_amount, state.baseCurrency, 0)}</strong>
        <div class="simulation-grid">
          <span>Deposits <b>${money(result.total_deposits, state.baseCurrency, 0)}</b></span>
          <span>Gain <b class="${Number(result.investment_gain) >= 0 ? "positive" : "negative"}">${money(result.investment_gain, state.baseCurrency, 0)}</b></span>
          <span>Years <b>${fmt(result.years, 1)}</b></span>
          <span>${result.kind === "Pension" ? "Monthly pension" : "Projected amount"} <b>${result.monthly_pension ? money(result.monthly_pension, state.baseCurrency, 0) : money(result.final_amount, state.baseCurrency, 0)}</b></span>
        </div>
        <div class="simulation-timeline">
          ${lastPoints.map((point) => `<span>Age ${fmt(point.age, 1)} <b>${money(point.amount, state.baseCurrency, 0)}</b></span>`).join("")}
        </div>
      </div>`;
  }).join("") : "";
}

function addPensionPeriod() {
  const period = {
    from_age: numberValue("simPeriodFrom"),
    to_age: numberValue("simPeriodTo"),
    monthly_income: numberValue("simPeriodIncome") || 0,
    contribution_percent: numberValue("simPeriodContribution") || 0,
    monthly_deposit: numberValue("simPeriodDeposit") || 0,
  };
  if (!period.from_age || !period.to_age || period.to_age <= period.from_age) {
    $("pensionSimulationStatus").textContent = "Income period needs valid from/to ages";
    return;
  }
  state.pensionIncomePeriods.push(period);
  ["simPeriodFrom", "simPeriodTo", "simPeriodIncome", "simPeriodContribution", "simPeriodDeposit"].forEach((id) => { $(id).value = ""; });
  $("pensionSimulationStatus").textContent = "Income period added";
  renderPensionPeriods();
}

function addPensionScenario() {
  const scenario = currentPensionScenario();
  if (!scenario.current_age || !scenario.retire_age || scenario.retire_age <= scenario.current_age) {
    $("pensionSimulationStatus").textContent = "Scenario needs current age and retire age";
    return;
  }
  state.pensionScenarios.push(scenario);
  $("pensionSimulationStatus").textContent = "Scenario added";
  renderPensionScenarios();
}

async function runPensionSimulation() {
  const scenarios = state.pensionScenarios.length ? state.pensionScenarios : [currentPensionScenario()];
  const data = await api("/api/local/pension-simulate", {
    method: "POST",
    body: JSON.stringify({ scenarios }),
  });
  state.pensionSimulationResults = data.results || [];
  $("pensionSimulationStatus").textContent = `${state.pensionSimulationResults.length} simulation result${state.pensionSimulationResults.length === 1 ? "" : "s"}`;
  renderPensionSimulationResults();
}

async function saveFund() {
  await api("/api/local/funds", {
    method: "POST",
    body: JSON.stringify({
      kind: valueOf("fundKind"),
      pension_id: valueOf("fundPensionId"),
      amount: valueOf("fundAmount"),
      factor: valueOf("fundFactor") || 200,
      persons: state.fundPersons.map((person) => ({ ...person })),
      comments: valueOf("fundComments"),
    }),
  });
  $("fundStatus").textContent = "Fund saved";
  ["fundPensionId", "fundAmount", "fundComments"].forEach((id) => { $(id).value = ""; });
  state.fundPersons = [];
  renderPersonLists();
  await loadFunds();
}

async function loadPortfolio() {
  $("status").textContent = "Loading portfolio";
  setLoading(true, "Loading portfolio analytics");
  try {
    const trendParams = new URLSearchParams({
      date_from: HISTORY_START_DATE,
      date_to: todayString(),
    });
    const [data, trend] = await Promise.all([
      api("/api/portfolio"),
      api(`/api/local/account-trends?${trendParams}`),
    ]);
    state.items = data.items;
    state.accountTrend = trend;
    populateOptions(data.items);
    $("status").textContent = `${data.count} positions · ${Object.entries(data.status).map(([k, v]) => `${k}: ${v}`).join(", ")}`;
    renderPortfolio(data.items);
  } finally {
    setLoading(false);
  }
}

async function loadLocalOptions() {
  try {
    state.localOptions = await api("/api/local/options");
  } catch {
    state.localOptions = {
      account_types: ["Investment", "Long-Term Savings", "Bank"],
      fund_kinds: ["Pension", "Provident Fund", "Savings Fund"],
      asset_classes: ["EQUITY", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE"],
      instrument_types: ["STOCK", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE"],
      option_types: ["CALL", "PUT"],
    };
  }
  populateStaticOptions();
}

async function applyFilter() {
  $("status").textContent = "Applying portfolio filter";
  setLoading(true, "Applying portfolio filter");
  try {
    const data = await api("/api/screener", { method: "POST", body: JSON.stringify(criteriaFromForm()) });
    state.items = data.items;
    $("status").textContent = `${data.count} positions matched`;
    renderPortfolio(data.items);
  } finally {
    setLoading(false);
  }
}

function loadSavedBannerItems() {
  try {
    const raw = localStorage.getItem("portfolioAnalyzer.bannerItems");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveBannerItems() {
  localStorage.setItem("portfolioAnalyzer.bannerItems", JSON.stringify(state.bannerItems));
}

async function resolveBannerItems() {
  const data = await api("/api/banner/resolve", {
    method: "POST",
    body: JSON.stringify({ items: state.bannerItems }),
  });
  renderBanner(data.items);
  renderBannerSettings();
}

async function loadBanner() {
  const data = await api("/api/banner");
  state.configuredBannerItems = data.configured || [];
  state.bannerItems = loadSavedBannerItems() || state.configuredBannerItems;
  renderBanner(data.items || []);
  if (loadSavedBannerItems()) {
    await resolveBannerItems();
  }
}

function renderBanner(items) {
  state.fxRates = items.reduce((rates, item) => {
    if (item.type === "fx" && item.value) rates[item.symbol] = Number(item.value);
    return rates;
  }, {});
  $("bannerItems").innerHTML = items.length ? items.map((item) => {
    const hasValue = item.value !== null && item.value !== undefined;
    const status = Object.entries(item.status || {}).map(([name, value]) => `${name}: ${value}`).join(", ");
    const changeValue = item.changes_percentage;
    const change = changeValue !== null && changeValue !== undefined
      ? `<span class="ticker-change ${Number(changeValue) >= 0 ? "positive" : "negative"}">${esc(changeArrow(changeValue))} ${pct(Math.abs(Number(changeValue)))}</span>`
      : "";
    const symbol = bannerValueSymbol(item);
    const meta = item.type === "fx" ? "" : `<small class="ticker-meta">${esc(item.symbol)} · ${esc(status || "missing")}</small>`;
    return `<div class="ticker-card">
      ${bannerIconHtml(item)}
      <div class="ticker-body">
        <span class="ticker-label">${esc(item.label)}</span>
        <strong>${symbol ? `<small class="ticker-symbol">${esc(symbol)}</small>` : ""}${hasValue ? fmt(item.value, item.type === "fx" ? 4 : 2) : "∅"}</strong>
        ${change}
        ${meta}
      </div>
    </div>`;
  }).join("") : '<div class="empty">No banner items</div>';
  if (state.items.length) renderPortfolio(state.items);
}

function renderBannerSettings() {
  $("bannerList").innerHTML = state.bannerItems.map((item, index) => `
    <div class="stack-item">
      <b>${esc(item.label || item.symbol)}</b>
      <span>${esc(item.type || "quote")} · ${esc(item.symbol)}</span>
      <button class="secondary compact-button" type="button" data-remove-banner="${index}">Remove</button>
    </div>
  `).join("");
}

function addBannerItem() {
  const symbol = $("bannerSymbol").value.trim();
  if (!symbol) return;
  state.bannerItems.push({
    label: $("bannerLabel").value.trim() || symbol,
    type: $("bannerType").value,
    symbol,
  });
  $("bannerLabel").value = "";
  $("bannerSymbol").value = "";
  saveBannerItems();
  resolveBannerItems();
}

async function loadAlerts() {
  const data = await api("/api/alerts");
  $("alertsList").innerHTML = data.rules.length ? data.rules.map((rule) => `
    <div class="stack-item">
      <b>${esc(rule.name)}</b>
      <span>${esc(rule.last_status || "not run")}</span>
      <div class="sub">matches: ${esc((rule.last_matches || []).join(", ") || "none")}</div>
    </div>
  `).join("") : '<div class="empty">No alerts yet</div>';
}

async function saveAlert() {
  await api("/api/alerts", {
    method: "POST",
    body: JSON.stringify({
      name: $("alertName").value || "Daily portfolio screen",
      enabled: true,
      criteria: {
        trend: $("alertTrend").value,
        dividendTrend: $("alertDividendTrend").value,
        minProfitMarketCap: $("alertMinProfitMarketCap").value,
        minDividendGrowth: $("alertMinDividendGrowth").value,
        includeMissing: false,
      },
      notification: { channels: ["dashboard"] },
    }),
  });
  $("alertName").value = "";
  loadAlerts();
}

async function runAlerts() {
  $("status").textContent = "Running alerts";
  await api("/api/alerts/run", { method: "POST", body: "{}" });
  $("status").textContent = "Alert run finished";
  loadAlerts();
}

function marketCriteria() {
  return {
    query: $("marketQuery").value.trim(),
    exchange: $("marketExchange").value,
    sector: $("marketSector").value.trim(),
    marketCapMoreThan: $("marketCapMoreThan").value,
    dividendMoreThan: $("dividendMoreThan").value,
    limit: 50,
  };
}

async function runMarketScreener() {
  $("marketStatus").textContent = "Searching";
  const data = await api("/api/market/screener", { method: "POST", body: JSON.stringify(marketCriteria()) });
  const status = Object.entries(data.status || {}).map(([name, value]) => `${name}: ${value}`).join(", ");
  $("marketStatus").textContent = `${data.count} symbols · ${status}`;
  $("marketRows").innerHTML = data.items.length ? data.items.map((item) => `
    <tr>
      <td><div class="symbol">${esc(item.symbol)}</div></td>
      <td>${esc(item.name || "")}</td>
      <td>${esc(item.exchange || "")}</td>
      <td>${fmt(item.price)}</td>
      <td>${fmt(item.market_cap, 0)}</td>
      <td>${esc(item.sector || "")}<div class="sub">${esc(item.industry || "")}</div></td>
      <td>${fmt(item.dividend)}</td>
    </tr>
  `).join("") : '<tr><td colspan="7" class="empty-cell">No results</td></tr>';
}

async function loadCacheStatus() {
  const settings = await api("/api/settings");
  const data = settings.cache || {};
  const backup = settings.backup || {};
  state.backupSettings = {
    ...backup,
    schedule_config: normalizeBackupScheduleConfig(backup.schedule_config),
    missed_policy: backup.missed_policy === "run" ? "run" : "wait",
  };
  $("tableMaPeriod").value = state.tableMaPeriod || "30";
  $("backupEnabled").value = String(backup.enabled !== false);
  $("backupTimezone").value = backup.timezone || "";
  $("backupKeep").value = backup.keep || 30;
  updateBackupScheduleSummary();
  $("cacheStatus").innerHTML = [
    ["Cache file", data.path],
    ["API response entries", data.entries],
    ["Cached daily prices", data.price_entries ?? 0],
    ["Current size", `${data.size_mb} MB`],
    ["Max size", `${data.max_mb} MB`],
    ["TTL", `${data.ttl_hours} hours`],
  ].map(([label, value]) => `<div class="setting-row"><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join("");
  $("backupStatus").innerHTML = [
    ["Backup directory", backup.directory || ""],
    ["Schedule", backup.schedule_summary || backupScheduleSummary(backup.schedule_config)],
    ["Next run", backup.next_run || "Disabled"],
    ["Latest backup", backup.latest?.filename || "None"],
    ["Backup files", (backup.backups || []).length],
  ].map(([label, value]) => `<div class="setting-row"><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join("");
}

async function exportLocalData() {
  $("settingsStatus").textContent = "Exporting data";
  const response = await fetch("/api/local/export");
  if (!response.ok) throw new Error(await response.text());
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] || "portfolio-data.json";
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  $("settingsStatus").textContent = "Data exported";
}

async function importLocalData(file) {
  if (!file) return;
  const text = await file.text();
  const payload = JSON.parse(text);
  if (!confirm("Import will replace the local portfolio data. Continue?")) return;
  $("settingsStatus").textContent = "Importing data";
  const result = await api("/api/local/import", { method: "POST", body: JSON.stringify(payload) });
  const total = Object.values(result.imported || {}).reduce((count, value) => count + Number(value || 0), 0);
  $("settingsStatus").textContent = `Imported ${total} records`;
  await Promise.all([loadLocalAccounts(), loadPortfolio(), loadCacheStatus()]);
}

async function runBackupNow() {
  $("settingsStatus").textContent = "Creating backup";
  const result = await api("/api/local/backups", { method: "POST", body: "{}" });
  $("settingsStatus").textContent = `Backup saved: ${result.filename}`;
  await loadCacheStatus();
}

function defaultBackupScheduleConfig() {
  return { frequency: "weekly", weekdays: [0, 2, 4], month_days: [1], hour: 23, minute: 45 };
}

function normalizeBackupScheduleConfig(config = {}) {
  const base = defaultBackupScheduleConfig();
  const frequency = ["daily", "weekly", "monthly"].includes(config.frequency) ? config.frequency : base.frequency;
  const hour = Math.min(Math.max(Number(config.hour ?? base.hour), 0), 23);
  const minute = Math.min(Math.max(Number(config.minute ?? base.minute), 0), 59);
  const weekdays = Array.isArray(config.weekdays) ? config.weekdays.map(Number).filter((day) => day >= 0 && day <= 6) : base.weekdays;
  const monthDays = Array.isArray(config.month_days) ? config.month_days.map(Number).filter((day) => day >= 1 && day <= 31) : base.month_days;
  return {
    frequency,
    weekdays: [...new Set(weekdays)].sort((a, b) => a - b),
    month_days: [...new Set(monthDays)].sort((a, b) => a - b),
    hour,
    minute,
  };
}

function backupScheduleSummary(config = defaultBackupScheduleConfig()) {
  const item = normalizeBackupScheduleConfig(config);
  const time = `${String(item.hour).padStart(2, "0")}:${String(item.minute).padStart(2, "0")}`;
  if (item.frequency === "daily") return `Every day at ${time}`;
  if (item.frequency === "monthly") return `Monthly on day ${item.month_days.join(", ")} at ${time}`;
  const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return `${item.weekdays.map((day) => names[day]).join(", ")} at ${time}`;
}

function renderBackupSchedulePickers() {
  const weekly = $("backupWeeklyPicker");
  const monthly = $("backupMonthlyPicker");
  if (weekly && !weekly.innerHTML) {
    const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    weekly.innerHTML = names.map((name, index) => `<label class="schedule-option"><input type="checkbox" name="backupWeekday" value="${index}" /> <span>${name}</span></label>`).join("");
  }
  if (monthly && !monthly.innerHTML) {
    monthly.innerHTML = Array.from({ length: 31 }, (_, index) => {
      const day = index + 1;
      return `<label class="schedule-option small"><input type="checkbox" name="backupMonthDay" value="${day}" /> <span>${day}</span></label>`;
    }).join("");
  }
}

function updateBackupScheduleSummary() {
  const backup = state.backupSettings || {};
  const summary = backup.schedule_summary || backupScheduleSummary(backup.schedule_config);
  $("backupScheduleSummary").innerHTML = `<span>Schedule</span><b>${esc(summary)}</b><small>${backup.missed_policy === "run" ? "Backup now if the selected time already passed" : "Wait for the next selected time"}</small>`;
}

function populateBackupScheduleForm() {
  renderBackupSchedulePickers();
  const backup = state.backupSettings || {};
  const config = normalizeBackupScheduleConfig(backup.schedule_config);
  $("backupScheduleFrequency").value = config.frequency;
  $("backupScheduleHour").value = config.hour;
  $("backupScheduleMinute").value = config.minute;
  $("backupMissedPolicy").value = backup.missed_policy === "run" ? "run" : "wait";
  document.querySelectorAll("input[name='backupWeekday']").forEach((input) => { input.checked = config.weekdays.includes(Number(input.value)); });
  document.querySelectorAll("input[name='backupMonthDay']").forEach((input) => { input.checked = config.month_days.includes(Number(input.value)); });
  syncBackupSchedulePickers();
}

function syncBackupSchedulePickers() {
  const frequency = valueOf("backupScheduleFrequency") || "weekly";
  $("backupWeeklyPicker").hidden = frequency !== "weekly";
  $("backupMonthlyPicker").hidden = frequency !== "monthly";
}

function backupScheduleFromForm() {
  const frequency = valueOf("backupScheduleFrequency") || "weekly";
  const weekdays = [...document.querySelectorAll("input[name='backupWeekday']:checked")].map((input) => Number(input.value));
  const monthDays = [...document.querySelectorAll("input[name='backupMonthDay']:checked")].map((input) => Number(input.value));
  return normalizeBackupScheduleConfig({
    frequency,
    weekdays: weekdays.length ? weekdays : [0],
    month_days: monthDays.length ? monthDays : [1],
    hour: numberValue("backupScheduleHour"),
    minute: numberValue("backupScheduleMinute"),
  });
}

function applyBackupSchedule() {
  state.backupSettings = {
    ...(state.backupSettings || {}),
    schedule_config: backupScheduleFromForm(),
    missed_policy: valueOf("backupMissedPolicy") || "wait",
  };
  state.backupSettings.schedule_summary = backupScheduleSummary(state.backupSettings.schedule_config);
  updateBackupScheduleSummary();
  closeModal($("backupScheduleModal"));
}

async function saveBackupSettings() {
  $("settingsStatus").textContent = "Saving backup schedule";
  state.backupSettings = {
    ...(state.backupSettings || {}),
    schedule_config: normalizeBackupScheduleConfig(state.backupSettings?.schedule_config),
    missed_policy: state.backupSettings?.missed_policy === "run" ? "run" : "wait",
  };
  const backup = await api("/api/settings/backup", {
    method: "PUT",
    body: JSON.stringify({
      enabled: $("backupEnabled").value === "true",
      schedule_config: state.backupSettings.schedule_config,
      missed_policy: state.backupSettings.missed_policy,
      timezone: $("backupTimezone").value.trim(),
      keep: $("backupKeep").value,
    }),
  });
  state.backupSettings = backup;
  $("settingsStatus").textContent = backup.enabled ? `Backup scheduled: ${backup.schedule_summary || backupScheduleSummary(backup.schedule_config)}` : "Backup disabled";
  await loadCacheStatus();
}

async function loadAbout() {
  const about = await api("/api/about");
  $("aboutContent").innerHTML = [
    ["Name", about.name || "Portfolio Analyzer"],
    ["Version", about.version || ""],
    ["Python", about.python || ""],
    ["Local data", "Accounts, instruments, transactions, prices, history"],
    ["Backup", "Export, import, scheduled backup"],
  ].map(([label, value]) => `<div class="setting-row"><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join("");
}

function openModal(id) {
  const modal = $(id);
  if (!modal) return;
  modal.hidden = false;
  if (id === "accountsModal") loadLocalAccounts();
  if (id === "securitiesModal") Promise.all([loadLocalAccounts(), loadLocalSecurities()]);
  if (id === "pricesModal") loadLocalPrices();
  if (id === "reportsModal") Promise.all([loadLocalAccounts(), loadReports()]);
  if (id === "fundsModal") loadFunds();
  if (id === "alertsModal") loadAlerts();
  if (id === "bannerModal") renderBannerSettings();
  if (id === "settingsModal") loadCacheStatus();
  if (id === "backupScheduleModal") populateBackupScheduleForm();
  if (id === "aboutModal") loadAbout().catch((error) => { $("aboutContent").innerHTML = `<div class="empty">Error: ${esc(error.message)}</div>`; });
}

function closeModal(modal) {
  modal.hidden = true;
}

document.addEventListener("click", (event) => {
  const modalId = event.target.closest("[data-modal]")?.dataset.modal;
  if (modalId) openModal(modalId);

  if (event.target.matches("[data-close]")) {
    closeModal(event.target.closest(".modal"));
  }

  const removeIndex = event.target.closest("[data-remove-banner]")?.dataset.removeBanner;
  if (removeIndex !== undefined) {
    state.bannerItems.splice(Number(removeIndex), 1);
    saveBannerItems();
    resolveBannerItems();
  }

  const accountId = event.target.closest("[data-delete-account]")?.dataset.deleteAccount;
  if (accountId) {
    api(`/api/local/accounts/${accountId}`, { method: "DELETE" }).then(() => Promise.all([loadLocalAccounts(), loadPortfolio()]));
  }

  const securityDetailButton = event.target.closest("[data-security-detail-symbol]");
  if (securityDetailButton) {
    openSecurityDetail(securityDetailButton.dataset).catch((error) => {
      $("status").textContent = `Error: ${error.message}`;
    });
  }

  const securityChartPeriod = event.target.closest("[data-security-chart-period]")?.dataset.securityChartPeriod;
  if (securityChartPeriod) {
    state.securityChartPeriod = securityChartPeriod;
    state.securityChartStartDate = startDateForPeriod(securityChartPeriod);
    if ($("securityChartStartDate")) $("securityChartStartDate").value = state.securityChartStartDate;
    loadSecurityDetail().catch((error) => { $("securityDetailStatus").textContent = `Error: ${error.message}`; });
  }

  if (event.target.id === "openFocusedPrices" && state.securityDetail) {
    openPriceHistoryForSecurity({
      securityDetailSymbol: state.securityDetail.symbol,
      securityDetailMarketKey: state.securityDetail.market_key,
      securityDetailStockMarket: state.securityDetail.stock_market,
      securityDetailProvider: state.securityDetail.data_provider,
      securityDetailAsset: state.securityDetail.asset_class,
      securityDetailCurrency: state.securityDetail.currency,
      securityDetailLocation: state.securityDetail.location,
    });
  }

  if (event.target.closest("[data-clear-price-focus]")) {
    state.priceFocus = null;
    renderPriceFocusBar();
    loadLocalPrices();
  }

  const securityId = event.target.closest("[data-delete-security]")?.dataset.deleteSecurity;
  if (securityId) {
    api(`/api/local/securities/${securityId}`, { method: "DELETE" }).then(() => Promise.all([loadLocalSecurities(), loadPortfolio()]));
  }

  const manualSecurityId = event.target.closest("[data-delete-manual-security]")?.dataset.deleteManualSecurity;
  if (manualSecurityId) {
    api(`/api/local/manual-securities/${manualSecurityId}`, { method: "DELETE" }).then(() => Promise.all([loadManualSecurities(), loadPortfolio()]));
  }

  const useManualSecurityId = event.target.closest("[data-use-manual-security]")?.dataset.useManualSecurity;
  if (useManualSecurityId) {
    const item = instrumentById(useManualSecurityId);
    applyInstrumentToForm(item, "security");
    $("securityKnownInstrument").value = useManualSecurityId;
    $("securityStatus").textContent = `Using ${item?.symbol || "instrument"} for the next transaction`;
  }

  const priceId = event.target.closest("[data-delete-price]")?.dataset.deletePrice;
  if (priceId) {
    api(`/api/local/prices/${priceId}`, { method: "DELETE" }).then(() => Promise.all([loadLocalPrices(), loadSecurityDetail(), loadPortfolio()]));
  }

  const editSnapshot = event.target.closest("[data-edit-history-snapshot]");
  if (editSnapshot) {
    $("historyAccount").value = editSnapshot.dataset.historyAccount || "";
    $("historyDate").value = editSnapshot.dataset.historyDate || todayString();
    $("historyValue").value = editSnapshot.dataset.historyValue || "";
    $("historyCash").value = editSnapshot.dataset.historyCash || "";
    $("historyProfit").value = editSnapshot.dataset.historyProfit || "";
    $("historyProfitPercent").value = editSnapshot.dataset.historyProfitPercent || "";
    $("historyStatus").textContent = "Editing selected history point";
  }

  const deleteSnapshot = event.target.closest("[data-delete-history-snapshot]");
  if (deleteSnapshot) {
    const account = deleteSnapshot.dataset.historyAccount;
    const day = deleteSnapshot.dataset.historyDate;
    api(`/api/local/account-snapshots/${encodeURIComponent(account)}/${encodeURIComponent(day)}`, { method: "DELETE" })
      .then(() => Promise.all([loadReports(), loadPortfolio()]));
  }

  const fundId = event.target.closest("[data-delete-fund]")?.dataset.deleteFund;
  if (fundId) {
    api(`/api/local/funds/${fundId}`, { method: "DELETE" }).then(loadFunds);
  }

  const localPersonIndex = event.target.closest("[data-delete-local-person]")?.dataset.deleteLocalPerson;
  if (localPersonIndex !== undefined) {
    state.localAccountPersons.splice(Number(localPersonIndex), 1);
    renderPersonLists();
  }

  const fundPersonIndex = event.target.closest("[data-delete-fund-person]")?.dataset.deleteFundPerson;
  if (fundPersonIndex !== undefined) {
    state.fundPersons.splice(Number(fundPersonIndex), 1);
    renderPersonLists();
  }

  const periodIndex = event.target.closest("[data-delete-pension-period]")?.dataset.deletePensionPeriod;
  if (periodIndex !== undefined) {
    state.pensionIncomePeriods.splice(Number(periodIndex), 1);
    renderPensionPeriods();
  }

  const scenarioIndex = event.target.closest("[data-delete-pension-scenario]")?.dataset.deletePensionScenario;
  if (scenarioIndex !== undefined) {
    state.pensionScenarios.splice(Number(scenarioIndex), 1);
    renderPensionScenarios();
  }

  const moveButton = event.target.closest("[data-dashboard-move]");
  if (moveButton) {
    moveDashboardWidget(moveButton.dataset.dashboardMove, Number(moveButton.dataset.direction || 0));
  }

  const placementButton = event.target.closest("[data-dashboard-set-view]");
  if (placementButton) {
    setDashboardWidgetView(placementButton.dataset.dashboardSetView, placementButton.dataset.view);
  }

  const modeButton = event.target.closest("[data-dashboard-mode]");
  if (modeButton) {
    setDashboardMode(modeButton.dataset.dashboardMode);
  }
});

document.addEventListener("change", (event) => {
  const accountTrendSelect = event.target.closest("[data-account-trend-select]");
  if (accountTrendSelect) {
    state.dashboard.accountTrendAccountId = accountTrendSelect.value;
    localStorage.setItem(DASHBOARD_ACCOUNT_STORAGE_KEY, accountTrendSelect.value);
    saveDashboardSettings();
    renderAnalytics(state.items || []);
  }

  if (event.target.id === "manualInstrumentType") {
    toggleManualInstrumentFields();
  }

  if (event.target.id === "manualSecurityLocation") {
    syncCurrencyFromLocation("manualSecurityLocation", "manualSecurityCurrency");
  }

  if (event.target.id === "securityKnownInstrument") {
    applyInstrumentToForm(instrumentById(event.target.value), "security");
  }

  if (event.target.id === "priceKnownInstrument") {
    applyInstrumentToForm(instrumentById(event.target.value), "price");
  }

  if (event.target.id === "securityChartStartDate") {
    state.securityChartStartDate = clampedHistoryDate(event.target.value);
    event.target.value = state.securityChartStartDate;
    loadSecurityDetail().catch((error) => { $("securityDetailStatus").textContent = `Error: ${error.message}`; });
  }

  if (event.target.id === "simFundSource") {
    applySimulationFund();
  }

  if (event.target.id === "simPersonSource") {
    applySimulationPerson();
  }

  if (event.target.id === "simBirthDate" && !$("simCurrentAge").value) {
    $("simCurrentAge").value = ageFromBirthDate(event.target.value);
  }

  if (event.target.id === "backupScheduleFrequency") {
    syncBackupSchedulePickers();
  }

  if (event.target.id === "reportFrom" || event.target.id === "historyDate") {
    event.target.value = clampedHistoryDate(event.target.value);
  }
});

document.addEventListener("dragstart", (event) => {
  const widget = event.target.closest(".dashboard-widget");
  if (!widget || !state.dashboard?.edit) return;
  event.dataTransfer.setData("text/plain", widget.dataset.widget);
  event.dataTransfer.effectAllowed = "move";
  widget.classList.add("dragging");
});

document.addEventListener("dragend", (event) => {
  event.target.closest(".dashboard-widget")?.classList.remove("dragging");
});

document.addEventListener("dragover", (event) => {
  if (!state.dashboard?.edit || !event.target.closest(".dashboard-widget, .dashboard-section")) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
});

document.addEventListener("drop", (event) => {
  const target = event.target.closest(".dashboard-widget");
  const section = event.target.closest(".dashboard-section");
  if (!state.dashboard?.edit || (!target && !section)) return;
  event.preventDefault();
  const sourceId = event.dataTransfer.getData("text/plain");
  if (target) {
    reorderDashboardWidgets(sourceId, target.dataset.widget);
  } else if (section) {
    appendDashboardWidgetToSection(sourceId, section.dataset.dashboardSection);
  }
});

$("refresh").addEventListener("click", () => {
  loadPortfolio().catch((error) => { $("status").textContent = `Error: ${error.message}`; });
  loadBanner().catch(() => {});
});
$("apply").addEventListener("click", applyFilter);
$("saveAlert").addEventListener("click", saveAlert);
$("runAlerts").addEventListener("click", runAlerts);
$("addBannerItem").addEventListener("click", addBannerItem);
$("runMarketScreener").addEventListener("click", runMarketScreener);
$("saveLocalAccount").addEventListener("click", () => saveLocalAccount().catch((error) => { $("accountsStatus").textContent = `Error: ${error.message}`; }));
$("addLocalAccountPerson").addEventListener("click", () => addPersonTo("localAccountPersons", "localPersonName", "localPersonBirthDate", "accountsStatus"));
$("importSource").addEventListener("click", () => importSourceToLocal().catch((error) => { $("accountsStatus").textContent = `Error: ${error.message}`; }));
$("exportData").addEventListener("click", () => exportLocalData().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }));
$("chooseImportData").addEventListener("click", () => $("importDataFile").click());
$("importDataFile").addEventListener("change", (event) => importLocalData(event.target.files?.[0]).catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }).finally(() => { event.target.value = ""; }));
$("runBackupNow").addEventListener("click", () => runBackupNow().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }));
$("saveBackupSettings").addEventListener("click", () => saveBackupSettings().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }));
$("saveTableSettings").addEventListener("click", () => {
  state.tableMaPeriod = $("tableMaPeriod").value;
  saveTableSettings();
  $("settingsStatus").textContent = `Table moving average set to MA ${state.tableMaPeriod}`;
  renderRows(state.items || []);
});
$("dashboardEdit").addEventListener("click", () => setDashboardEdit(!state.dashboard.edit));
$("dashboardReset").addEventListener("click", resetDashboard);
$("saveManualSecurity").addEventListener("click", () => saveManualSecurity().catch((error) => { $("manualSecurityStatus").textContent = `Error: ${error.message}`; }));
$("saveSecurity").addEventListener("click", () => saveSecurity().catch((error) => { $("securityStatus").textContent = `Error: ${error.message}`; }));
$("savePrice").addEventListener("click", () => savePrice().catch((error) => { $("priceStatus").textContent = `Error: ${error.message}`; }));
$("saveDetailPrice").addEventListener("click", () => saveSecurityDetailPrice().catch((error) => { $("securityDetailStatus").textContent = `Error: ${error.message}`; }));
$("loadReports").addEventListener("click", () => loadReports().catch((error) => { $("reportsDetails").innerHTML = `<div class="empty">Error: ${esc(error.message)}</div>`; }));
$("saveHistorySnapshot").addEventListener("click", () => saveHistorySnapshot().catch((error) => { $("historyStatus").textContent = `Error: ${error.message}`; }));
$("captureHistorySnapshot").addEventListener("click", () => captureHistorySnapshot().catch((error) => { $("historyStatus").textContent = `Error: ${error.message}`; }));
$("saveFund").addEventListener("click", () => saveFund().catch((error) => { $("fundStatus").textContent = `Error: ${error.message}`; }));
$("addFundPerson").addEventListener("click", () => addPersonTo("fundPersons", "fundPersonName", "fundPersonBirthDate", "fundStatus"));
$("addPensionPeriod").addEventListener("click", addPensionPeriod);
$("addPensionScenario").addEventListener("click", addPensionScenario);
$("runPensionSimulation").addEventListener("click", () => runPensionSimulation().catch((error) => { $("pensionSimulationStatus").textContent = `Error: ${error.message}`; }));
$("applyBackupSchedule").addEventListener("click", applyBackupSchedule);
$("localAccountLocation").addEventListener("change", () => syncCurrencyFromLocation("localAccountLocation", "localAccountCurrency"));
$("priceLocation").addEventListener("change", () => syncCurrencyFromLocation("priceLocation", "priceCurrency"));
["manualSecuritySymbol", "manualUnderlyingSymbol", "securitySymbol", "priceSymbol"].forEach((id) => {
  $(id).addEventListener("blur", () => { $(id).value = cleanSecuritySymbol($(id).value); });
});

loadDashboardSettings();
loadTableSettings();

Promise.all([loadLocalOptions(), loadLocalAccounts(), loadFunds()])
  .then(() => Promise.all([loadPortfolio(), loadBanner(), loadAlerts()]))
  .catch((error) => {
  $("status").textContent = `Error: ${error.message}`;
});
