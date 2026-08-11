const HISTORY_START_DATE = "2026-04-14";
const DATE_PLACEHOLDER = "dd/mm/yyyy";

const state = {
  items: [],
  accountTrend: { accounts: [] },
  dashboard: null,
  bannerItems: [],
  configuredBannerItems: [],
  historySnapshots: [],
  fxRates: {},
  coreFxRates: {},
  bannerFxRates: {},
  baseCurrency: "ILS",
  localAccounts: [],
  manualSecurities: [],
  localTransactions: [],
  localEvents: [],
  focusedEventId: "",
  localPrices: [],
  equityCompQuotes: {},
  priceFocus: null,
  securityDetail: null,
  positionTransactionsDetail: null,
  editingPositionTransactionId: "",
  securityChartPeriod: "1y",
  securityChartMode: "line",
  securityChartLevelPeriods: ["1y"],
  securityChartMaWindows: ["30"],
  securityChartStartDate: HISTORY_START_DATE,
  securityHistory: [],
  securityHistoryMeta: {},
  localFunds: [],
  fundAmountHistory: [],
  fundHistoryFundId: "",
  editingFundHistoryId: "",
  longTermView: "total",
  brokers: [],
  familyMembers: [],
  localAccountPersons: [],
  editAccountPersons: [],
  fundPersons: [],
  editFundPersons: [],
  editingAccountId: "",
  editingBrokerId: "",
  editingFamilyMemberId: "",
  editingFundId: "",
  editingTransactionId: "",
  securitiesWorkflow: "general",
  employeeOptionGrants: [],
  employeeOptionWizardMode: "browse",
  employeeOptionWizardStep: 1,
  employeeOptionWizardMaxStep: 1,
  editingEmployeeOptionSecurityId: "",
  editingEmployeeOptionTransactionId: "",
  returnToEmployeeOptionsAfterAccount: false,
  activeEmployeeListingSecurityId: "",
  activeEmployeeExerciseSecurityId: "",
  pensionScenarios: [],
  pensionSimulationResults: [],
  pensionSimulationGrid: null,
  pensionSimulationKey: "",
  pensionSimulationAutoRunningKey: "",
  pensionSimulationErrorKey: "",
  pensionSimulationError: "",
  financeReport: null,
  companyOutlook: null,
  companyOutlookHistory: [],
  researchSection: "finance",
  alertData: null,
  alertOptions: { metrics: [], operators: [], signals: [], match_modes: [] },
  alertConditions: [],
  editingAlertId: "",
  vestingAlertDays: 30,
  dismissedAlarmIds: [],
  activePensionScenarioIndex: null,
  localOptions: {
    account_types: ["Investment", "Long-Term Savings", "Bank", "ESOP"],
    fund_kinds: ["Pension", "Provident Fund", "Savings Fund"],
    asset_classes: ["EQUITY", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE", "RSU", "EMPLOYEE_STOCK_OPTION", "PRIVATE_STOCK", "STOCK_OPTION"],
    instrument_types: ["STOCK", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE", "RSU", "EMPLOYEE_STOCK_OPTION", "PRIVATE_STOCK", "STOCK_OPTION"],
    option_types: ["CALL", "PUT"],
    issuer_listing_statuses: ["PRIVATE", "PUBLIC"],
  },
  optionsReady: false,
  portfolioReady: false,
  tableMaPeriod: "30",
  backupSettings: null,
  riskSnapshot: null,
  language: "he",
};

const $ = (id) => document.getElementById(id);

const DASHBOARD_WIDGETS = [
  { id: "portfolio_value", title: "Portfolio value", view: "basic", size: "wide" },
  { id: "long_term_savings", title: "Long-term savings", view: "basic", size: "wide" },
  { id: "account_trend", title: "Account value trend", view: "basic", size: "wide" },
  { id: "long_term", title: "Long-term funds", view: "basic", size: "wide" },
  { id: "market_cost", title: "Market vs cost basis", view: "basic", size: "wide" },
  { id: "asset_mix", title: "Asset mix", view: "basic", size: "compact" },
  { id: "industry_split", title: "Industry split", view: "basic", size: "wide" },
  { id: "top_holdings", title: "Top holdings", view: "basic", size: "wide" },
  { id: "coverage", title: "Provider data coverage", view: "expanded", size: "medium" },
  { id: "currency", title: "Currency allocation", view: "expanded", size: "compact" },
  { id: "equity_comp", title: "Equity compensation", view: "expanded", size: "wide" },
  { id: "profit", title: "Unrealized P/L by holding", view: "expanded", size: "wide" },
  { id: "snapshot", title: "Portfolio snapshot", view: "expanded", size: "wide" },
];

const DASHBOARD_STORAGE_KEY = "portfolioAnalyzer.dashboard";
const DASHBOARD_ACCOUNT_STORAGE_KEY = "portfolioAnalyzer.dashboard.accountTrend";
const DASHBOARD_LONG_TERM_STORAGE_KEY = "portfolioAnalyzer.dashboard.longTerm";
const TABLE_SETTINGS_STORAGE_KEY = "portfolioAnalyzer.tableSettings";
const LANGUAGE_STORAGE_KEY = "portfolioAnalyzer.language";
const PENSION_SIMULATION_STORAGE_KEY = "portfolioAnalyzer.pensionSimulation";
const VESTING_ALERT_SETTINGS_STORAGE_KEY = "portfolioAnalyzer.vestingAlerts";
const ALARM_DISMISSALS_STORAGE_KEY = "portfolioAnalyzer.alarmDismissals";
const LOG_PREFIX = "[Portfolio Analyzer]";
const SENSITIVE_LOG_KEY = /(password|passwd|secret|token|api[_-]?key|authorization|credential|connection|string)/i;
const PENSION_INSURANCE_TRACKS = {
  comprehensive: { label: "Comprehensive", disability: 75, spouse: 60, children: 40 },
  savings_30: { label: "Savings 30/20", disability: 75, spouse: 30, children: 20 },
  savings_40: { label: "Savings 40/30", disability: 75, spouse: 40, children: 30 },
  survivors_oriented: { label: "Survivors-oriented", disability: 37.5, spouse: 60, children: 40 },
  single: { label: "Single status", disability: 75, spouse: 0, children: 0 },
  custom: { label: "Custom", disability: "", spouse: "", children: "" },
};
const DISABILITY_COVERAGE_OPTIONS = [75, 37.5];
const SPOUSE_SURVIVORS_OPTIONS = [60, 40, 30, 0];
const CHILDREN_SURVIVORS_OPTIONS = [40, 30, 20, 0];
const DASHBOARD_SECTIONS = [
  { view: "basic", label: "Glance" },
  { view: "expanded", label: "Full" },
  { view: "hidden", label: "Hidden" },
];
const SUPPORT_RESISTANCE_PERIODS = [
  { key: "5y", label: "5Y" },
  { key: "3y", label: "3Y" },
  { key: "1y", label: "1Y" },
  { key: "6m", label: "6M" },
  { key: "1m", label: "1M" },
];

const REGION_CODES = "AF AX AL DZ AS AD AO AI AQ AG AR AM AW AU AT AZ BS BH BD BB BY BE BZ BJ BM BT BO BQ BA BW BV BR IO BN BG BF BI CV KH CM CA KY CF TD CL CN CX CC CO KM CG CD CK CR CI HR CU CW CY CZ DK DJ DM DO EC EG SV GQ ER EE SZ ET FK FO FJ FI FR GF PF TF GA GM GE DE GH GI GR GL GD GP GU GT GG GN GW GY HT HM VA HN HK HU IS IN ID IR IQ IE IM IL IT JM JP JE JO KZ KE KI KP KR KW KG LA LV LB LS LR LY LI LT LU MO MG MW MY MV ML MT MH MQ MR MU YT MX FM MD MC MN ME MS MA MZ MM NA NR NP NL NC NZ NI NE NG NU NF MK MP NO OM PK PW PS PA PG PY PE PH PN PL PT PR QA RE RO RU RW BL SH KN LC MF PM VC WS SM ST SA SN RS SC SL SG SX SK SI SB SO ZA GS SS ES LK SD SR SJ SE CH SY TW TJ TZ TH TL TG TK TO TT TN TR TM TC TV UG UA AE GB US UM UY UZ VU VE VN VG VI WF EH YE ZM ZW".split(" ");
const ACCOUNT_COUNTRIES = ["USA", "Israel"];
const MARKET_OPTIONS = ["NASDAQ", "NYSE", "AMEX", "NYSEARCA", "OTC", "TASE"];
const FALLBACK_CURRENCIES = "USD ILS EUR GBP JPY CHF CAD AUD NZD CNY HKD SGD INR KRW MXN BRL ARS CLP COP ZAR AED SAR TRY PLN CZK HUF SEK NOK DKK ISK RUB UAH RON BGN HRK RSD THB IDR MYR PHP VND TWD ILS".split(" ");
const EMPLOYEE_OPTION_CURRENCIES = ["ILS", "USD", "EUR"];
const TRANSLATIONS = {
  en: {
    appName: "Portfolio analyzer",
    brand: "Portfolio",
    overview: "Overview",
    loadingPortfolio: "Loading portfolio",
    readingCachedAnalytics: "Reading cached analytics",
    mainMenu: "Main Menu",
    dashboard: "Dashboard",
    reports: "Reports",
    research: "Research",
    companyReports: "Company Reports",
    companyOutlook: "Company Outlook",
    signalRules: "Portfolio Signals",
    portfolioData: "Portfolio Data",
    accounts: "Accounts",
    brokers: "Brokers",
    employeeOptions: "Employee Stock Options",
    securities: "Securities",
    prices: "Prices",
    events: "Events",
    people: "People",
    familyMembers: "Family Members",
    accountOwnership: "Account Ownership",
    retirement: "Retirement",
    pensionsFunds: "Pensions & Funds",
    retirementProjections: "Retirement Projections",
    pensionFunds: "Pension/Funds",
    marketsAlerts: "Markets",
    marketScreener: "Market Screener",
    alerts: "Alerts",
    marketBanner: "Market Banner",
    system: "System",
    settings: "Settings",
    about: "About",
    markets: "Markets",
    currencyIndexesCommodities: "Currency, indexes, and commodities",
    manage: "Manage",
    longTermSavings: "Long-term savings",
    pensionAccountsFunds: "Pension accounts and funds",
    pension: "pension",
    provident: "provident",
    savingsFund: "savings fund",
    longTermAccounts: "long-term accounts",
    accountHoldingsCash: "account holdings/cash",
    pensionMonthlyEstimate: "pension monthly estimate",
    notApplicable: "Not applicable",
    language: "Language",
    display: "Display",
    appLanguage: "App language",
    saveDisplaySettings: "Save display settings",
    displaySettingsSaved: "Display settings saved",
    tableDisplay: "Table display",
    tableMaPeriod: "Table MA period",
    saveTableSettings: "Save table settings",
    data: "Data",
    backupSchedule: "Backup schedule",
  },
  he: {
    appName: "מנהל תיק השקעות",
    brand: "תיק השקעות",
    overview: "סקירה",
    loadingPortfolio: "טוען תיק",
    readingCachedAnalytics: "קורא נתוני ניתוח שמורים",
    mainMenu: "תפריט ראשי",
    dashboard: "לוח בקרה",
    reports: "דוחות",
    research: "מחקר",
    companyReports: "דוחות חברות",
    companyOutlook: "תחזית חברה",
    signalRules: "איתותי תיק ההשקעות",
    portfolioData: "נתוני תיק",
    accounts: "חשבונות",
    brokers: "ברוקרים",
    employeeOptions: "אופציות עובדים",
    securities: "ניירות ערך",
    prices: "מחירים",
    events: "אירועים",
    people: "אנשים",
    familyMembers: "בני משפחה",
    accountOwnership: "שיוך חשבונות",
    retirement: "פרישה",
    pensionsFunds: "פנסיה וקופות",
    retirementProjections: "תחזיות פרישה",
    pensionFunds: "פנסיה וקופות",
    marketsAlerts: "שווקים",
    marketScreener: "סורק שוק",
    alerts: "התראות",
    marketBanner: "סרגל שוק",
    system: "מערכת",
    settings: "הגדרות",
    about: "אודות",
    markets: "שווקים",
    currencyIndexesCommodities: "מטבעות, מדדים וסחורות",
    manage: "ניהול",
    longTermSavings: "חסכון לטווח ארוך",
    pensionAccountsFunds: "חשבונות פנסיה וקופות",
    pension: "פנסיה",
    provident: "גמל",
    savingsFund: "קרן השתלמות",
    longTermAccounts: "חשבונות לטווח ארוך",
    accountHoldingsCash: "יתרת חשבון/ניירות ערך",
    pensionMonthlyEstimate: "אומדן קצבה חודשית",
    notApplicable: "לא רלוונטי",
    language: "שפה",
    display: "תצוגה",
    appLanguage: "שפת הממשק",
    saveDisplaySettings: "שמור הגדרות תצוגה",
    displaySettingsSaved: "הגדרות התצוגה נשמרו",
    tableDisplay: "תצוגת טבלה",
    tableMaPeriod: "תקופת ממוצע נע בטבלה",
    saveTableSettings: "שמור הגדרות טבלה",
    data: "נתונים",
    backupSchedule: "תזמון גיבוי",
  },
};

function locale() {
  return state.language === "he" ? "he-IL" : undefined;
}

function t(key) {
  return TRANSLATIONS[state.language]?.[key] || TRANSLATIONS.en[key] || key;
}
const OPTION_LABELS = {
  MUTUALFUND: "Mutual Fund",
  OPTION: "Exchange-Traded Option",
  EMPLOYEE_STOCK_OPTION: "Employee Stock Option",
  PRIVATE_STOCK: "Private Company Shares",
  STOCK_OPTION: "Stock Option (Legacy)",
  RSU: "RSU",
};

function optionLabel(value) {
  const label = OPTION_LABELS[value] || value;
  return window.PortfolioI18n?.translate(label, state.language) || label;
}

function flagFor(code) {
  return code.replace(/./g, (char) => String.fromCodePoint(127397 + char.charCodeAt(0)));
}

function countryName(code) {
  try {
    const names = typeof Intl.DisplayNames === "function"
      ? new Intl.DisplayNames([locale() || navigator.language || "en"], { type: "region" })
      : null;
    return names?.of(code) || code;
  } catch {
    return code;
  }
}

function currencySymbol(code) {
  try {
    const part = new Intl.NumberFormat(locale(), { style: "currency", currency: code, currencyDisplay: "narrowSymbol" })
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

function normalizeAccountCountry(location) {
  const text = String(location || "").trim().toLowerCase();
  if (["israel", "il", "state of israel"].includes(text)) return "Israel";
  if (["usa", "us", "u.s.", "u.s.a.", "united states", "united states of america"].includes(text)) return "USA";
  return ACCOUNT_COUNTRIES.includes(location) ? location : "USA";
}

function sanitizeLogValue(value, depth = 0) {
  if (depth > 2) return "[nested]";
  if (Array.isArray(value)) return value.slice(0, 10).map((item) => sanitizeLogValue(item, depth + 1));
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.entries(value).map(([key, item]) => (
    SENSITIVE_LOG_KEY.test(key) ? [key, "[redacted]"] : [key, sanitizeLogValue(item, depth + 1)]
  )));
}

function appLog(event, details = {}) {
  console.info(LOG_PREFIX, event, sanitizeLogValue(details));
}

function appWarn(event, details = {}) {
  console.warn(LOG_PREFIX, event, sanitizeLogValue(details));
}

async function api(path, options = {}) {
  const started = performance.now();
  const method = options.method || "GET";
  const endpoint = String(path).split("?")[0];
  try {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    appLog("api.response", { method, endpoint, status: response.status, ms: Math.round(performance.now() - started) });
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
  } catch (error) {
    appWarn("api.error", { method, endpoint, message: error.message });
    throw error;
  }
}

let loadingRequests = 0;
let clientStateSyncTimer = null;

function setLoading(active, detail = "") {
  const overlay = $("loadingOverlay");
  const loadingDetailText = detail || t("readingCachedAnalytics");
  if (active && loadingRequests === 0) {
    appLog("loading.start", { detail: loadingDetailText });
  }
  loadingRequests = Math.max(0, loadingRequests + (active ? 1 : -1));
  if (overlay) overlay.hidden = true;
  document.body.classList.remove("is-loading-portfolio");
  if ($("loadingTitle")) $("loadingTitle").textContent = t("loadingPortfolio");
  if ($("loadingDetail")) $("loadingDetail").textContent = loadingDetailText;
  $("refresh")?.classList.toggle("is-loading", loadingRequests > 0);
  if (loadingRequests === 0) appLog("loading.end");
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

function parseDateInput(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) return validIsoDate(text) ? text : "";
  const display = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!display) return "";
  const day = display[1].padStart(2, "0");
  const month = display[2].padStart(2, "0");
  const candidate = `${display[3]}-${month}-${day}`;
  return validIsoDate(candidate) ? candidate : "";
}

function validIsoDate(value) {
  const [year, month, day] = String(value || "").split("-").map(Number);
  if (!year || !month || !day) return false;
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

function formatDate(value) {
  const iso = parseDateInput(value);
  if (!iso) return value || "";
  const [year, month, day] = iso.split("-");
  return `${day}/${month}/${year}`;
}

function formatDateTime(value) {
  if (!value) return "Not run";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(state.language === "he" ? "he-IL" : "en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function dateValue(id) {
  return parseDateInput(valueOf(id));
}

function setDateField(id, value) {
  const input = $(id);
  if (input) input.value = formatDate(value || "");
}

function nativeDatePicker() {
  let picker = $("nativeDatePicker");
  if (picker) return picker;
  picker = document.createElement("input");
  picker.id = "nativeDatePicker";
  picker.type = "date";
  picker.className = "native-date-picker";
  picker.tabIndex = -1;
  document.body.appendChild(picker);
  return picker;
}

function pickerBoundsForDateField(input) {
  const min = ["reportFrom", "historyDate", "securityChartStartDate"].includes(input.id) ? HISTORY_START_DATE : "";
  const max = ["familyMemberBirthDate", "simBirthDate"].includes(input.id) ? todayString() : "";
  return { min, max };
}

function openDatePickerFor(input) {
  if (!input || input.hidden || input.disabled || input.readOnly) return;
  const now = Date.now();
  if (Number(input.dataset.lastPickerOpen || 0) + 450 > now) return;
  input.dataset.lastPickerOpen = String(now);
  const picker = nativeDatePicker();
  const { min, max } = pickerBoundsForDateField(input);
  picker.min = min;
  picker.max = max;
  picker.value = parseDateInput(input.value) || (min && todayString() < min ? min : todayString());
  picker.onchange = () => {
    if (!picker.value) return;
    input.value = formatDate(picker.value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  };
  try {
    if (typeof picker.showPicker === "function") {
      picker.showPicker();
    } else {
      picker.click();
    }
  } catch (_error) {
    picker.click();
  }
}

function ensureHierarchicalNav() {
  const nav = document.querySelector(".nav");
  if (!nav) return;
  nav.innerHTML = `
    <div class="nav-title">${esc(t("mainMenu"))}</div>
    <details class="nav-menu" open>
      <summary>${esc(t("dashboard"))}</summary>
      <div class="nav-children">
        <button class="nav-item active" type="button">${esc(t("overview"))}</button>
        <button class="nav-item" type="button" data-modal="reportsModal">${esc(t("reports"))}</button>
      </div>
    </details>
    <details class="nav-menu" open>
      <summary>${esc(t("portfolioData"))}</summary>
      <div class="nav-children">
        <button class="nav-item" type="button" data-modal="accountsModal">${esc(t("accounts"))}</button>
        <button class="nav-item" type="button" data-modal="brokersModal">${esc(t("brokers"))}</button>
        <button class="nav-item" type="button" data-modal="securitiesModal" data-securities-workflow="employee-options">${esc(t("employeeOptions"))}</button>
        <button class="nav-item" type="button" data-modal="securitiesModal">${esc(t("securities"))}</button>
        <button class="nav-item" type="button" data-modal="pricesModal">${esc(t("prices"))}</button>
        <button class="nav-item" type="button" data-modal="eventsModal">${esc(t("events"))}</button>
      </div>
    </details>
    <details class="nav-menu">
      <summary>${esc(t("people"))}</summary>
      <div class="nav-children">
        <button class="nav-item" type="button" data-modal="familyModal" data-modal-target="familyMembersSection" data-modal-focus="familyMemberFirstName">${esc(t("familyMembers"))}</button>
        <button class="nav-item" type="button" data-modal="familyModal" data-modal-target="accountOwnershipSection" data-modal-focus="familyAttachAccount">${esc(t("accountOwnership"))}</button>
      </div>
    </details>
    <details class="nav-menu">
      <summary>${esc(t("retirement"))}</summary>
      <div class="nav-children">
        <button class="nav-item" type="button" data-modal="fundsModal" data-modal-target="fundsTitle" data-modal-focus="showFundCreate">${esc(t("pensionsFunds"))}</button>
        <button class="nav-item" type="button" data-modal="fundsModal" data-modal-target="simulatorPanel" data-modal-focus="simPersonSource">${esc(t("retirementProjections"))}</button>
      </div>
    </details>
    <details class="nav-menu">
      <summary>${esc(t("research"))}</summary>
      <div class="nav-children">
        <button class="nav-item" type="button" data-modal="researchModal" data-research-section="finance">${esc(t("companyReports"))}</button>
        <button class="nav-item" type="button" data-modal="researchModal" data-research-section="outlook">${esc(t("companyOutlook"))}</button>
        <button class="nav-item" type="button" data-modal="researchModal" data-research-section="signals">${esc(t("signalRules"))}</button>
      </div>
    </details>
    <details class="nav-menu">
      <summary>${esc(t("marketsAlerts"))}</summary>
      <div class="nav-children">
        <button class="nav-item" type="button" data-modal="marketModal">${esc(t("marketScreener"))}</button>
        <button class="nav-item" type="button" data-modal="bannerModal">${esc(t("marketBanner"))}</button>
      </div>
    </details>
    <details class="nav-menu">
      <summary>${esc(t("system"))}</summary>
      <div class="nav-children">
        <button class="nav-item" type="button" data-modal="settingsModal">${esc(t("settings"))}</button>
        <button class="nav-item" type="button" data-modal="aboutModal">${esc(t("about"))}</button>
      </div>
    </details>`;
}

function bindNavAccordion() {
  document.querySelectorAll(".nav-menu").forEach((navMenu) => {
    navMenu.addEventListener("toggle", () => {
      if (!navMenu.open) return;
      document.querySelectorAll(".nav-menu[open]").forEach((menu) => {
        if (menu !== navMenu) menu.open = false;
      });
    });
  });
}

function fmt(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "∅";
  return Number(value).toLocaleString(locale(), { maximumFractionDigits: digits });
}

function money(value, currency = "USD", digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "∅";
  try {
    return new Intl.NumberFormat(locale(), {
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
    return new Intl.NumberFormat(locale(), {
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
  return new Intl.NumberFormat(locale(), {
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

function updateFxRates() {
  state.fxRates = { ...(state.coreFxRates || {}), ...(state.bannerFxRates || {}) };
}

function setCoreFxRates(data) {
  state.coreFxRates = (data?.quotes || []).reduce((rates, item) => {
    const rate = Number(item?.quote?.rate || 0);
    if (item?.pair && rate > 0) rates[item.pair] = rate;
    return rates;
  }, {});
  updateFxRates();
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
    state.longTermView = ["total", "people", "funds"].includes(saved.longTermView)
      ? saved.longTermView
      : localStorage.getItem(DASHBOARD_LONG_TERM_STORAGE_KEY) || state.longTermView;
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
  localStorage.setItem(DASHBOARD_STORAGE_KEY, JSON.stringify({ ...state.dashboard, longTermView: state.longTermView }));
  scheduleClientStateSync();
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
  scheduleClientStateSync();
}

function loadLanguageSettings() {
  const saved = localStorage.getItem(LANGUAGE_STORAGE_KEY);
  state.language = saved === "en" ? "en" : "he";
}

function saveLanguageSettings() {
  localStorage.setItem(LANGUAGE_STORAGE_KEY, state.language);
  scheduleClientStateSync();
}

function normalizedVestingAlertDays(value) {
  const days = Math.round(Number(value));
  return Number.isFinite(days) ? Math.min(Math.max(days, 1), 365) : 30;
}

function loadVestingAlertSettings() {
  const settings = readLocalJson(VESTING_ALERT_SETTINGS_STORAGE_KEY, {});
  state.vestingAlertDays = normalizedVestingAlertDays(settings?.leadDays);
}

function normalizedAlarmDismissals(value) {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.map((item) => String(item || "").trim()).filter(Boolean))].slice(-2000);
}

function loadAlarmDismissals() {
  state.dismissedAlarmIds = normalizedAlarmDismissals(readLocalJson(ALARM_DISMISSALS_STORAGE_KEY, []));
}

function saveAlarmDismissals() {
  state.dismissedAlarmIds = normalizedAlarmDismissals(state.dismissedAlarmIds);
  localStorage.setItem(ALARM_DISMISSALS_STORAGE_KEY, JSON.stringify(state.dismissedAlarmIds));
  scheduleClientStateSync();
}

function saveVestingAlertSettings() {
  state.vestingAlertDays = normalizedVestingAlertDays(valueOf("vestingAlertDays"));
  localStorage.setItem(VESTING_ALERT_SETTINGS_STORAGE_KEY, JSON.stringify({ leadDays: state.vestingAlertDays }));
  $("vestingAlertDays").value = String(state.vestingAlertDays);
  $("alarmSettingsStatus").textContent = `Vesting alerts will appear ${state.vestingAlertDays} day${state.vestingAlertDays === 1 ? "" : "s"} before vesting.`;
  scheduleClientStateSync();
  renderAlarms();
}

function readLocalJson(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function collectClientState() {
  return {
    version: 1,
    saved_at: new Date().toISOString(),
    dashboard: state.dashboard ? { ...state.dashboard, longTermView: state.longTermView } : readLocalJson(DASHBOARD_STORAGE_KEY, {}),
    table: { maPeriod: state.tableMaPeriod || "30" },
    language: state.language || "en",
    bannerItems: Array.isArray(state.bannerItems) ? state.bannerItems : readLocalJson("portfolioAnalyzer.bannerItems", []),
    pensionSimulation: readLocalJson(PENSION_SIMULATION_STORAGE_KEY, {}),
    alarms: {
      vestingLeadDays: state.vestingAlertDays,
      dismissedIds: normalizedAlarmDismissals(state.dismissedAlarmIds),
    },
  };
}

function applyClientState(clientState) {
  if (!clientState || typeof clientState !== "object") return false;
  if (clientState.dashboard && typeof clientState.dashboard === "object") {
    localStorage.setItem(DASHBOARD_STORAGE_KEY, JSON.stringify(clientState.dashboard));
    if (clientState.dashboard.longTermView) localStorage.setItem(DASHBOARD_LONG_TERM_STORAGE_KEY, clientState.dashboard.longTermView);
  }
  if (clientState.table?.maPeriod) {
    localStorage.setItem(TABLE_SETTINGS_STORAGE_KEY, JSON.stringify({ maPeriod: clientState.table.maPeriod }));
  }
  if (clientState.language) {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, clientState.language === "he" ? "he" : "en");
  }
  if (Array.isArray(clientState.bannerItems)) {
    localStorage.setItem("portfolioAnalyzer.bannerItems", JSON.stringify(clientState.bannerItems));
  }
  if (clientState.pensionSimulation && typeof clientState.pensionSimulation === "object") {
    localStorage.setItem(PENSION_SIMULATION_STORAGE_KEY, JSON.stringify(clientState.pensionSimulation));
  }
  if (clientState.alarms && typeof clientState.alarms === "object") {
    localStorage.setItem(VESTING_ALERT_SETTINGS_STORAGE_KEY, JSON.stringify({
      leadDays: normalizedVestingAlertDays(clientState.alarms.vestingLeadDays),
    }));
    if (Array.isArray(clientState.alarms.dismissedIds)) {
      localStorage.setItem(ALARM_DISMISSALS_STORAGE_KEY, JSON.stringify(
        normalizedAlarmDismissals(clientState.alarms.dismissedIds),
      ));
    }
  }
  return true;
}

function loadClientStateFromStorage() {
  loadLanguageSettings();
  loadDashboardSettings();
  loadTableSettings();
  loadPensionSimulationState();
  loadVestingAlertSettings();
  loadAlarmDismissals();
  renderPensionInsuranceControls();
  applyLanguage();
}

function clientStateFromExportPayload(payload) {
  const rows = payload?.data?.app_preferences || payload?.app_preferences || [];
  const row = Array.isArray(rows) ? rows.find((item) => item?.key === "client_state") : null;
  if (!row?.value) return null;
  try {
    return typeof row.value === "string" ? JSON.parse(row.value) : row.value;
  } catch {
    return null;
  }
}

async function syncClientStateToServer() {
  await api("/api/settings/client-state", {
    method: "PUT",
    body: JSON.stringify(collectClientState()),
  });
}

function scheduleClientStateSync() {
  clearTimeout(clientStateSyncTimer);
  clientStateSyncTimer = setTimeout(() => {
    syncClientStateToServer().catch((error) => appWarn("client_state.sync_failed", { message: error.message }));
  }, 500);
}

async function loadClientStateFromServer() {
  const data = await api("/api/settings/client-state");
  applyClientState(data.state);
}

function applyAutoDirection() {
  document.querySelectorAll('input:not([type="number"]):not([type="date"]):not([type="file"]), textarea').forEach((field) => {
    field.setAttribute("dir", "auto");
  });
}

function applyLanguage() {
  document.documentElement.lang = state.language === "he" ? "he" : "en";
  document.documentElement.dir = state.language === "he" ? "rtl" : "ltr";
  document.title = t("appName");
  const brand = document.querySelector(".brand span:last-child");
  if (brand) brand.textContent = t("brand");
  const topEyebrow = document.querySelector(".topbar .eyebrow");
  if (topEyebrow) topEyebrow.textContent = t("overview");
  const topTitle = document.querySelector(".topbar h1");
  if (topTitle) topTitle.textContent = t("appName");
  const marketEyebrow = document.querySelector(".ticker-panel .eyebrow");
  if (marketEyebrow) marketEyebrow.textContent = t("markets");
  const marketTitle = document.querySelector(".ticker-panel h2");
  if (marketTitle) marketTitle.textContent = t("currencyIndexesCommodities");
  const marketManage = document.querySelector('.ticker-panel [data-modal="bannerModal"]');
  if (marketManage) marketManage.textContent = t("manage");
  const settingsTitle = $("settingsTitle");
  if (settingsTitle) settingsTitle.textContent = t("settings");
  const loadingTitle = $("loadingTitle");
  if (loadingTitle) loadingTitle.textContent = t("loadingPortfolio");
  const loadingDetail = $("loadingDetail");
  if (loadingDetail && !loadingDetail.textContent.trim()) loadingDetail.textContent = t("readingCachedAnalytics");
  const languageSelect = $("appLanguage");
  if (languageSelect) languageSelect.value = state.language;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  ensureHierarchicalNav();
  bindNavAccordion();
  applyAutoDirection();
  window.PortfolioI18n?.applyToDocument(state.language);
  window.PortfolioI18n?.observe();
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
  const sections = DASHBOARD_SECTIONS.filter((section) => (
    section.view === "basic" || (dashboard.mode === "expanded" && section.view === "expanded")
  ));
  return sections.flatMap((section) => (
    dashboard.widgets
      .filter((widget) => widget.view === section.view)
      .sort((a, b) => a.order - b.order)
  ));
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

function moveDashboardWidgetToPosition(sourceId, view, index) {
  const source = dashboardWidgetConfig(sourceId);
  if (!source || !DASHBOARD_SECTIONS.some((section) => section.view === view)) return;
  source.view = view;
  const widgets = state.dashboard.widgets
    .filter((widget) => widget.view === view && widget.id !== sourceId)
    .sort((a, b) => a.order - b.order);
  const targetIndex = Math.max(0, Math.min(Number(index || 0), widgets.length));
  widgets.splice(targetIndex, 0, source);
  widgets.forEach((widget, order) => { widget.order = order; });
  normalizeDashboardOrders();
  saveDashboardSettings();
  renderAnalytics(state.items || []);
}

function dashboardDropIndex(grid, event) {
  const widgets = [...(grid?.querySelectorAll(".dashboard-widget:not(.dragging)") || [])]
    .sort((a, b) => {
      const aRect = a.getBoundingClientRect();
      const bRect = b.getBoundingClientRect();
      return Math.abs(aRect.top - bRect.top) > 8 ? aRect.top - bRect.top : aRect.left - bRect.left;
    });
  if (!widgets.length) return 0;
  const pointerX = event.clientX;
  const pointerY = event.clientY;
  for (let index = 0; index < widgets.length; index += 1) {
    const rect = widgets[index].getBoundingClientRect();
    const sameRow = pointerY >= rect.top - 8 && pointerY <= rect.bottom + 8;
    if ((sameRow && pointerX < rect.left + rect.width / 2) || pointerY < rect.top + rect.height / 2) {
      return index;
    }
  }
  return widgets.length;
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
          <span>${widgets.length} cards</span>
        </div>
        <div class="dashboard-section-grid">
          ${widgets.length ? widgets.map((widget) => withDashboardToolbar(widget, renderers[widget.id]())).join("") : '<div class="empty">Drop cards here</div>'}
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
    `<div class="chart-card $1 dashboard-widget dashboard-widget-${esc(size)}${editClass}" data-widget="${esc(widget.id)}"${draggable}>${dashboardWidgetToolbar(widget)}`,
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

function isEquityCompAccount(account) {
  return String(account?.type || "").toUpperCase() === "ESOP";
}

function portfolioAccounts() {
  return (state.localAccounts || []).filter((account) => !isEquityCompAccount(account));
}

function isEquityCompHolding(item) {
  const holding = item?.holding || {};
  const assetClass = String(holding.asset_class || holding.asset_sub_class || "").toUpperCase();
  const account = state.localAccounts.find((candidate) => String(candidate.id || "") === String(holding.account_id || ""));
  return isEquityCompAccount(account)
    || String(holding.account_type || "").toUpperCase() === "ESOP"
    || ["RSU", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION"].includes(assetClass);
}

function portfolioItems(items) {
  return (items || []).filter((item) => !isEquityCompHolding(item));
}

function groupByAccount(items) {
  const groups = items.reduce((result, item) => {
    const holding = item.holding;
    const account = cleanSourceLabel(holding.account) || "Unassigned";
    const key = holding.account_id || account;
    const group = result[key] || {
      account,
      accountId: holding.account_id || "",
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
    result[key] = group;
    return result;
  }, {});
  portfolioAccounts().forEach((account) => {
    const label = cleanSourceLabel(accountLabel(account)) || account.id || "Unassigned";
    const matchingKey = groups[account.id]
      ? account.id
      : Object.keys(groups).find((key) => groups[key].account === label);
    const cashLocal = accountCashBalance(account);
    if (!matchingKey && Math.abs(cashLocal) <= 1e-9) return;
    const key = matchingKey || account.id || label;
    const group = groups[key] || {
      account: label,
      accountId: account.id || "",
      value: 0,
      profit: 0,
      localValues: {},
      symbols: [],
      currencies: new Set(),
      type: account.type || "",
      location: account.location || "",
    };
    const currency = account.currency || state.baseCurrency;
    group.value += normalizedAmount(cashLocal, currency);
    group.localValues[currency] = (group.localValues[currency] || 0) + cashLocal;
    group.cashLocal = cashLocal;
    group.cashCurrency = currency;
    group.currencies.add(currency);
    groups[key] = group;
  });
  return Object.values(groups).map((group) => ({ ...group, currencies: [...group.currencies] }));
}

function accountCashBalance(account) {
  if (!account) return 0;
  const transactions = state.localTransactions.filter((tx) => String(tx.account_db_id || "") === String(account.id || ""));
  return Number(account.initial_cash || 0) + sum(transactions.map(transactionCashImpact));
}

function accountCashValue(account) {
  if (!account) return 0;
  return Math.max(0, normalizedAmount(accountCashBalance(account), account.currency));
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
  if (["OPTION", "FUTURE", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION"].includes(asset) || ["OPTION", "FUTURE", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION"].includes(instrument)) return 1;
  if (symbol.includes("3X") || symbol.includes("2X") || symbol.includes("LEVERAGED")) return 1;
  if (asset === "BOND") return 0.35;
  if (asset === "ETF" || asset === "MUTUALFUND") return 0.45;
  if (asset === "EQUITY" || asset === "RSU") return 0.65;
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
  return ["OPTION", "FUTURE", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION"].includes(asset) || ["OPTION", "FUTURE", "STOCK_OPTION", "EMPLOYEE_STOCK_OPTION"].includes(instrument) || symbol.includes("3X") || symbol.includes("2X") || symbol.includes("LEVERAGED");
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
  return Math.max(0, Number(person?.retire_age || 67) - age);
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
  const band = riskBand(risk.score);
  const meaning = {
    low: "Relatively stable, but losses are still possible.",
    moderate: "Noticeable gains or losses are possible.",
    elevated: "Price swings could cause meaningful losses.",
    high: "Several factors create a high chance of large losses.",
    extreme: "Sharp losses are possible from very strong risk factors.",
  }[band.key];
  const simpleDriver = (driver) => {
    const text = String(driver || "");
    if (text.startsWith("Top holding ")) return `one holding is a large part of the portfolio (${text.slice(12)})`;
    if (text.startsWith("Holding weight ")) return `this holding is ${text.slice(15)} of the portfolio`;
    if (text.startsWith("Foreign currency ")) return `${text.slice(17)} is exposed to foreign currencies`;
    if (text.startsWith("Options/futures/leverage ")) return `${text.slice(25)} uses options, futures, or leverage`;
    if (text.startsWith("1Y volatility proxy ")) return `its recent price movement is about ${text.slice(20)}`;
    if (text.startsWith("Horizon ")) return `the investment horizon is ${text.slice(8)}`;
    if (text.startsWith("Issuer concentration ")) return `one issuer represents ${text.slice(21)}`;
    if (text.startsWith("Country concentration ")) return `one country represents ${text.slice(22)}`;
    if (text.startsWith("Low cash ")) return `the cash buffer is low (${text.slice(9)})`;
    if (text.startsWith("High cash ")) return `a large share is held in cash (${text.slice(10)})`;
    if (text.startsWith("Missing industry ")) return `industry information is missing for ${text.slice(17)}`;
    if (text.startsWith("Asset factor ")) return "its asset type carries market risk";
    if (text === "ETF/fund treated as diversified proxy") return "the fund is treated as diversified";
    if (text === "Option/future/leveraged instrument") return "it uses an option, future, or leveraged instrument";
    if (text.startsWith("Missing ")) return `${text.toLowerCase()} data makes the estimate less certain`;
    return text.toLowerCase();
  };
  const drivers = (risk.drivers || []).slice(0, 4).map(simpleDriver);
  return [
    `${band.label} risk · ${risk.score}/100`,
    meaning,
    "",
    "Main reasons:",
    ...(drivers.length ? drivers.map((driver) => `• ${driver}`) : ["• No single factor stands out"]),
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
  const combinedCash = sum(portfolioAccounts().map(accountCashValue));
  const portfolioHorizons = portfolioAccounts().map(accountHorizonYears).filter((value) => value !== null);
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
  return formatDate(row?.date || "");
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
    <div class="metric-row"><span>High</span><b>${money(range.high, currency)}</b>${range.high_date ? `<em>${esc(formatDate(range.high_date))}</em>` : ""}</div>
    <div class="metric-row"><span>Low</span><b>${money(range.min, currency)}</b>${range.min_date ? `<em>${esc(formatDate(range.min_date))}</em>` : ""}</div>
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
    technicalPeriod: $("technicalPeriod").value,
    technicalLevel: $("technicalLevel").value,
    technicalDirection: $("technicalDirection").value,
    technicalDistancePct: $("technicalDistancePct").value,
    includeMissing: $("includeMissing").checked,
  };
}

function setSelectOptions(id, values, label) {
  const select = $(id);
  const current = select.value;
  select.innerHTML = `<option value="">${label}</option>` + values
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b))
    .map((value) => `<option value="${esc(value)}">${esc(optionLabel(value))}</option>`)
    .join("");
  select.value = values.includes(current) ? current : "";
}

function setOptions(id, values, label = "") {
  const select = $(id);
  if (!select) return;
  const current = select.value;
  select.innerHTML = (label ? `<option value="">${esc(label)}</option>` : "") + values.map((value) => `<option value="${esc(value)}">${esc(optionLabel(value))}</option>`).join("");
  if (values.includes(current)) select.value = current;
}

function refreshMarketOptions() {
  $("marketOptions").innerHTML = MARKET_OPTIONS.map((market) => `<option value="${esc(market)}"></option>`).join("");
}

function setCurrencyOptions(id, supportedCodes = null) {
  const select = $(id);
  if (!select) return;
  const current = select.value;
  const codes = Array.isArray(supportedCodes)
    ? [...new Set(supportedCodes)]
    : [...new Set(currencyCodes())].sort();
  select.innerHTML = codes.map((code) => `<option value="${esc(code)}">${esc(currencySymbol(code))} ${esc(code)}</option>`).join("");
  select.value = codes.includes(current) ? current : (codes.includes("USD") ? "USD" : codes[0]);
}

function companyCountryChoices() {
  return REGION_CODES.map((code) => {
    const name = countryName(code);
    const value = code === "US" ? "USA" : code === "IL" ? "Israel" : name;
    return { code, name, value };
  }).sort((a, b) => a.name.localeCompare(b.name));
}

function normalizedCompanyLocation(location, choices = companyCountryChoices()) {
  const text = String(location || "").trim().toLowerCase();
  if (["usa", "us", "u.s.", "u.s.a.", "united states", "united states of america"].includes(text)) return "USA";
  if (["israel", "il", "state of israel"].includes(text)) return "Israel";
  return choices.find((choice) => (
    choice.code.toLowerCase() === text
    || choice.name.toLowerCase() === text
    || choice.value.toLowerCase() === text
  ))?.value || "";
}

function setCompanyLocationOptions(preferred = "", selectId = "manualSecurityLocation") {
  const select = $(selectId);
  if (!select) return;
  const choices = companyCountryChoices();
  const current = normalizedCompanyLocation(preferred || select.value, choices);
  select.innerHTML = choices.map((choice) => (
    `<option value="${esc(choice.value)}">${esc(flagFor(choice.code))} ${esc(choice.name)}</option>`
  )).join("");
  select.value = current || "USA";
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
  refreshMarketOptions();
  ["localAccountCurrency", "editAccountCurrency", "priceCurrency", "manualSecurityCurrency"].forEach((id) => setCurrencyOptions(id));
  setCurrencyOptions("employeeWizardCurrency", EMPLOYEE_OPTION_CURRENCIES);
  setCompanyLocationOptions("USA");
  setCompanyLocationOptions("USA", "employeeWizardLocation");
  const assetClasses = state.localOptions.asset_classes || ["EQUITY", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE", "RSU", "EMPLOYEE_STOCK_OPTION", "PRIVATE_STOCK", "STOCK_OPTION"];
  setOptions("localAccountType", state.localOptions.account_types);
  setOptions("editAccountType", state.localOptions.account_types);
  setOptions("localAccountLocation", ACCOUNT_COUNTRIES);
  setOptions("editAccountLocation", ACCOUNT_COUNTRIES);
  setOptions("brokerCountry", ACCOUNT_COUNTRIES);
  setOptions("brokerCurrency", ["USD", "ILS"]);
  setOptions("reportAccountType", state.localOptions.account_types, "Any account type");
  setOptions("fundKind", state.localOptions.fund_kinds);
  setOptions("editFundKind", state.localOptions.fund_kinds);
  setOptions("securityAssetClass", assetClasses);
  setOptions("priceAssetClass", assetClasses);
  setOptions("manualInstrumentType", (state.localOptions.instrument_types || ["STOCK", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE", "RSU", "EMPLOYEE_STOCK_OPTION", "PRIVATE_STOCK", "STOCK_OPTION"])
    .filter((type) => type !== "STOCK_OPTION"));
  setOptions("manualOptionType", state.localOptions.option_types || ["CALL", "PUT"]);
  $("localAccountLocation").value = "USA";
  $("editAccountLocation").value = "USA";
  $("brokerCountry").value = "USA";
  $("brokerCurrency").value = "USD";
  $("manualSecurityLocation").value = "USA";
  $("priceLocation").value = "USA";
  setDateField("securityDate", todayString());
  setDateField("priceDate", todayString());
  setDateField("historyDate", todayString());
  setDateField("reportTo", todayString());
  setDateField("reportFrom", HISTORY_START_DATE);
  toggleManualInstrumentFields();
  toggleTransactionCompFields();
}

function todayString() {
  return new Date().toISOString().slice(0, 10);
}

function clampedHistoryDate(value) {
  const dateValue = parseDateInput(value);
  return dateValue && dateValue > HISTORY_START_DATE ? dateValue : HISTORY_START_DATE;
}

function startDateForPeriod(period) {
  const days = { "1m": 31, "6m": 183, "1y": 366, "3y": 366 * 3, "5y": 366 * 5 }[period] || 366;
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
}

function renderPortfolioValueDashboard(items) {
  if (!state.portfolioReady) {
    return `
      <div class="chart-card portfolio-value-card">
        <div class="balance-panel">
          <p class="eyebrow">Portfolio value</p>
          <div class="balance-value portfolio-value-loading">Loading…</div>
        </div>
      </div>`;
  }
  state.riskSnapshot = portfolioRiskSnapshot(items);
  const securitiesValue = sum(items.map((item) => normalizedField(item, "market_value")));
  const cashValue = sum(portfolioAccounts().map((account) => normalizedAmount(accountCashBalance(account), account.currency || state.baseCurrency)));
  const primaryValue = securitiesValue + cashValue;
  const primaryProfit = sum(items.map((item) => normalizedField(item, "unrealized_profit")));
  const accountTotals = groupByAccount(items).sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
  const symbols = new Set(items.map((item) => item.holding.symbol)).size;
  const bonds = items.filter((item) => item.holding.asset_class === "BOND").length;
  const equities = items.filter((item) => item.holding.asset_class === "EQUITY").length;
  const gaps = missingStats(items);

  const accountsHtml = accountTotals
    .map((account) => {
      const accountRisk = state.riskSnapshot.accounts.find((entry) => entry.account === account.account)?.risk;
      const symbolsText = account.symbols.slice(0, 12).join(", ");
      const more = account.symbols.length > 12 ? `, +${account.symbols.length - 12} more` : "";
      const localAmounts = Object.entries(account.localValues || {})
        .filter(([currency]) => currency !== state.baseCurrency)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([currency, value]) => money(value, currency, 0));
      const localLine = localAmounts.length ? `<small>${esc(localAmounts.join(" · "))}</small>` : "";
      const cashText = account.cashCurrency ? `; Cash: ${money(account.cashLocal || 0, account.cashCurrency, 2)}` : "";
      const title = `Account: ${account.account}; ${account.type || "Account"}${account.location ? ` · ${account.location}` : ""}; Securities: ${symbolsText || "None"}${more}; Source currencies: ${account.currencies.join(", ")}${cashText}`;
      return `<span class="account-chip" title="${esc(title)}"><b>${esc(account.account)}</b><span class="account-chip-values"><strong>${money(account.value, state.baseCurrency, 0)}</strong>${localLine}</span>${riskBadge(accountRisk, true)}</span>`;
    })
    .join("");

  const totalRiskBand = riskBand(state.riskSnapshot.total.score);
  const statsHtml = [
    { label: "Risk", value: state.riskSnapshot.total.score, tooltip: riskTooltip(state.riskSnapshot.total), detail: totalRiskBand.label, className: `risk-${totalRiskBand.key}` },
    { label: "Positions", value: items.length, tooltip: "Number of open positions shown after filters" },
    { label: "Securities", value: symbols, tooltip: "Unique security symbols" },
    { label: "Equities", value: equities, tooltip: "Open equity positions" },
    { label: "Bonds", value: bonds, tooltip: "Open bond positions" },
    { label: "Data gaps", value: gaps.total, tooltip: gaps.topLabels || "No missing analytics fields", detail: `${gaps.positions}/${items.length} positions` },
  ].map((item) => `
    <div class="stat summary-stat ${esc(item.className || "")}" title="${esc(item.tooltip || "")}">
      <b>${esc(item.value)}</b>
      <span>${esc(item.label)}</span>
      ${item.detail ? `<small>${esc(item.detail)}</small>` : ""}
    </div>
  `).join("");
  const profitClass = primaryProfit > 0 ? "up" : primaryProfit < 0 ? "down" : "neutral";
  return `
    <div class="chart-card portfolio-value-card">
      <div class="balance-panel">
        <p class="eyebrow">Portfolio value</p>
        <div class="balance-value" title="Securities ${money(securitiesValue, state.baseCurrency, 0)} + cash ${money(cashValue, state.baseCurrency, 0)}">${money(primaryValue, state.baseCurrency)}</div>
        <div class="delta ${profitClass}" title="Holding profit converted to ${esc(state.baseCurrency)} using displayed FX rates when available">Holding Profit ${signedMoney(primaryProfit, state.baseCurrency)}</div>
        <details class="summary-drawer">
          <summary>Portfolio stats</summary>
          <div class="summary">${statsHtml}</div>
        </details>
        <div class="currency-strip">${accountsHtml}</div>
      </div>
    </div>
  `;
}

function renderPensionDashboardTable(monthlyEstimate) {
  const grid = state.pensionSimulationGrid;
  const hasResults = Boolean(grid && state.pensionSimulationResults.length);
  const currentKey = pensionScenarioKey();
  const simulationError = state.pensionSimulationErrorKey === currentKey ? state.pensionSimulationError : "";
  const canAutoRun = state.pensionScenarios.length && state.pensionScenarios.every((scenario) => (
    scenario.current_age && scenario.retire_age && scenario.retire_age > scenario.current_age && scenarioHasProfitRates(scenario) && !scenarioNeedsGenderForInsurance(scenario)
  ));
  const scenarios = hasResults ? (grid.baseScenarios || []) : state.pensionScenarios;
  const resultFor = (rowIndex) => hasResults ? (state.pensionSimulationResults[rowIndex] || null) : null;
  if (scenarios.length) {
    if (!hasResults && canAutoRun) schedulePensionSimulationAutoRun();
    return `
      <div class="dashboard-projection-table">
        <table class="projection-result-table compact-projection-table">
          <thead>
            <tr>
              <th>Pension Scenario</th>
              <th>Age Range</th>
              <th>Monthly Pension</th>
              <th>Final Amount</th>
              <th>Deposits</th>
              <th>Profit</th>
            </tr>
          </thead>
          <tbody>
            ${scenarios.map((scenario, rowIndex) => {
              const result = resultFor(rowIndex);
              const rowNeedsGender = scenarioNeedsGenderForInsurance(scenario);
              const statusText = simulationError || (rowNeedsGender ? "Set gender" : (canAutoRun ? "Calculating" : "Add profit rate"));
              const statusTitle = simulationError || (rowNeedsGender ? "Set Male/Female gender to calculate pension insurance cost" : "");
              return `
                <tr>
                  <td><b>${esc(scenario.name)}</b><small>${esc(scenario.person_name || "Manual")}</small></td>
                  <td>${fmt(scenario.current_age, 1)}-${fmt(scenario.retire_age, 1)}</td>
                  <td>${result ? `<b>${money(result.monthly_pension || 0, state.baseCurrency, 0)}</b>` : `<span class="muted-inline" title="${esc(statusTitle)}">${esc(statusText)}</span>`}</td>
                  <td>${result ? money(result.final_amount || 0, state.baseCurrency, 0) : ""}</td>
                  <td>${result ? money(result.total_deposits || 0, state.baseCurrency, 0) : ""}</td>
                  <td>${result ? money(result.investment_gain || 0, state.baseCurrency, 0) : ""}</td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;
  }
  return `
    <div class="dashboard-projection-table">
      <table class="projection-result-table compact-projection-table">
        <thead>
          <tr>
            <th>Pension Scenario</th>
            <th>Monthly Estimate</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Saved Funds Estimate</b><small>Pension records only</small></td>
            <td><b>${monthlyEstimate ? money(monthlyEstimate, state.baseCurrency, 0) : t("notApplicable")}</b></td>
            <td><span class="muted-inline">Add scenarios in Manage</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  `;
}

function renderFundsOverviewDashboard() {
  const funds = state.localFunds || [];
  const longTermLocalAccounts = (state.localAccounts || []).filter((account) => account.type === "Long-Term Savings");
  const longTermAccountItems = (state.items || []).filter((item) => item.holding.account_type === "Long-Term Savings");
  const longTermAccounts = new Set([
    ...longTermLocalAccounts.map(accountLabel),
    ...longTermAccountItems.map((item) => item.holding.account),
  ].filter(Boolean));
  const securitiesValue = sum(longTermAccountItems.map((item) => normalizedField(item, "market_value")));
  const accountCash = sum(longTermLocalAccounts.map((account) => normalizedAmount(account.initial_cash, account.currency || state.baseCurrency)));
  const pensionSaved = sum(funds.filter((fund) => fund.kind === "Pension").map((fund) => fund.amount));
  const providentSaved = sum(funds.filter((fund) => fund.kind === "Provident Fund").map((fund) => fund.amount));
  const savingsSaved = sum(funds.filter((fund) => fund.kind === "Savings Fund").map((fund) => fund.amount));
  const accountSaved = securitiesValue + accountCash;
  const pensionMonthlyFunds = funds.filter((fund) => fund.kind === "Pension" && fund.monthly_estimate !== null && fund.monthly_estimate !== undefined);
  const monthly = sum(pensionMonthlyFunds.map((fund) => fund.monthly_estimate));
  const hasAccountOnlyValue = Math.abs(accountSaved) > 0.005;
  const fundTitle = funds.map((fund) => {
    const label = [fund.kind, fund.fund_name || "", fund.pension_id].filter(Boolean).join(" ");
    const monthlyText = fund.kind === "Pension" && fund.monthly_estimate !== null && fund.monthly_estimate !== undefined
      ? `, ${t("pensionMonthlyEstimate")} ${fmt(fund.monthly_estimate, 0)}`
      : "";
    return `${label}: saved ${fmt(fund.amount, 0)}${monthlyText}`;
  }).join("; ");
  const accountTitle = [...longTermAccounts].join(", ");
  const savedBreakdown = [
    `${t("pension")} ${money(pensionSaved, state.baseCurrency, 0)}`,
    `${t("provident")} ${money(providentSaved, state.baseCurrency, 0)}`,
    `${t("savingsFund")} ${money(savingsSaved, state.baseCurrency, 0)}`,
    hasAccountOnlyValue ? `${t("accountHoldingsCash")} ${money(accountSaved, state.baseCurrency, 0)}` : "",
  ].filter(Boolean).join("; ");
  const title = [accountTitle ? `Long-term accounts: ${accountTitle}` : "", fundTitle, savedBreakdown].filter(Boolean).join("; ");
  const projectionTable = renderPensionDashboardTable(pensionMonthlyFunds.length ? monthly : 0);
  return `
    <div class="chart-card long-term-savings-card">
      <div class="funds-overview-panel">
        <div>
          <p class="eyebrow">${esc(t("longTermSavings"))}</p>
          <h2>${esc(t("pensionAccountsFunds"))}</h2>
        </div>
        <div class="funds-overview-stats" title="${esc(title || "No pension fund records")}">
          <span><b>${esc(longTermAccounts.size)}</b> ${esc(t("accounts"))}</span>
          <span><b>${esc(funds.length)}</b> ${esc(t("pensionFunds"))}</span>
          <span title="Pension fund saved balance"><b>${money(pensionSaved, state.baseCurrency, 0)}</b> ${esc(t("pension"))}</span>
          <span title="Provident fund saved balance"><b>${money(providentSaved, state.baseCurrency, 0)}</b> ${esc(t("provident"))}</span>
          <span title="Savings fund saved balance"><b>${money(savingsSaved, state.baseCurrency, 0)}</b> ${esc(t("savingsFund"))}</span>
          ${hasAccountOnlyValue ? `<span title="Account-level securities and cash not recorded as pension, provident, or savings fund balances"><b>${money(accountSaved, state.baseCurrency, 0)}</b> ${esc(t("accountHoldingsCash"))}</span>` : ""}
        </div>
        ${projectionTable}
        <button class="secondary" type="button" data-modal="fundsModal">${esc(t("manage"))}</button>
      </div>
    </div>
  `;
}

function renderFundsOverview() {
  renderAnalytics(state.items || []);
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
    const averageBuyPrice = Math.abs(Number(h.quantity || 0)) > 0
      ? Math.abs(Number(h.cost_basis || 0) / Number(h.quantity || 0))
      : 0;
    return `<tr>
      <td data-label="Security"><div class="security-cell"><button class="symbol security-history-link" type="button" data-security-detail-symbol="${esc(h.symbol)}" data-security-detail-market-key="${esc(marketKey)}" data-security-detail-stock-market="${esc(market)}" data-security-detail-provider="${esc(provider)}" data-security-detail-asset="${esc(h.asset_class)}" data-security-detail-currency="${esc(h.currency)}" data-security-detail-location="${esc(h.country || h.location || "")}" title="Open security overview">${esc(h.symbol)}</button><div class="security-name">${esc(companyLine)}</div>${industryLine}<div class="sub security-meta">${esc(marketLine)}</div></div></td>
      <td data-label="Account"><div>${esc(cleanSourceLabel(h.account) || "∅")}</div><div class="sub">${esc(cleanSourceLabel(h.account_type || h.location || h.sector || ""))}</div></td>
      <td data-label="Risk">${riskBadge(rowRisk)}</td>
      <td data-label="Value / P&L"><div class="value-cell">
        <strong>${money(h.market_value, h.currency)}</strong>
        <button class="units-history-link" type="button" data-position-history-symbol="${esc(h.symbol)}" data-position-history-market="${esc(marketKey)}" data-position-history-account-id="${esc(h.account_id || "")}" data-position-history-account="${esc(cleanSourceLabel(h.account) || "")}" data-position-history-currency="${esc(h.currency || state.baseCurrency)}" data-position-history-quantity="${esc(h.quantity || 0)}" data-position-history-average="${esc(averageBuyPrice)}" data-position-history-asset="${esc(h.asset_class || "EQUITY")}" data-position-history-location="${esc(h.country || h.location || "")}" title="Open buy and sell history">${fmt(h.quantity, 3)} units</button>
        <span class="average-buy-price">Avg buy ${averageBuyPrice ? money(averageBuyPrice, h.currency, 2) : "Not available"}</span>
        <b class="${Number(h.unrealized_profit) >= 0 ? "positive" : "negative"}">${signedMoney(h.unrealized_profit, h.currency)}</b>
      </div></td>
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
  const latestTooltip = `${selectedLabel}\nLatest total amount: ${trendAmount(last, "value")}\nLatest cash: ${trendAmount(last, "cash")}\nDate: ${formatDate(last.date || "")}`;
  const valueMarkers = points.map((point, index) => {
    const cx = x(point, index);
    const cy = y(point, "value");
    const tooltip = `${formatDate(point.date)}\n${selectedLabel}\nTotal amount: ${trendAmount(point, "value")}`;
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
    const tooltip = `${formatDate(point.date)}\n${selectedLabel}\nCash: ${trendAmount(point, "cash")}`;
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
          <title>${esc(`${selectedLabel}\nCash line\nLatest cash: ${trendAmount(last, "cash")}\nDate: ${formatDate(last.date || "")}`)}</title>
        </path>
        ${valueMarkers}
        ${cashMarkers}
        ${xTicks.map((point, index) => {
          const pointIndex = points.findIndex((item) => item.date === point.date);
          const tickX = x(point, pointIndex);
          const anchor = index === 0 ? "start" : index === xTicks.length - 1 ? "end" : "middle";
          return `<text class="axis-label" x="${tickX.toFixed(1)}" y="${height - 12}" text-anchor="${anchor}">${esc(formatDate(point.date || ""))}</text>`;
        }).join("")}
        <text class="axis-title" x="${padLeft + plotWidth / 2}" y="${height - 2}">Date</text>
      </svg>
    </div>`;
}

function longTermPersonKey(person) {
  const name = personFullName(person);
  return name && name !== "Family member" ? name : "Unassigned";
}

function longTermDates() {
  const dates = new Set([todayString()]);
  (state.accountTrend.accounts || []).forEach((entry) => {
    (entry.points || []).forEach((point) => {
      if (point.date) dates.add(point.date);
    });
  });
  return [...dates].sort((left, right) => left.localeCompare(right));
}

function emptyLongTermSeries(dates) {
  return Object.fromEntries(dates.map((date) => [date, 0]));
}

function addLongTermValue(groups, key, dates, valueByDate) {
  if (!groups[key]) groups[key] = emptyLongTermSeries(dates);
  dates.forEach((date) => {
    groups[key][date] += Number(valueByDate[date] || 0);
  });
}

function longTermSeriesHasValue(values, dates) {
  return dates.some((date) => Math.abs(Number(values[date] || 0)) > 0.005);
}

function longTermAccountSeries(dates) {
  const trendsById = new Map((state.accountTrend.accounts || []).map((entry) => [entry.account.id, entry]));
  return (state.localAccounts || [])
    .filter((account) => account.type === "Long-Term Savings")
    .map((account) => {
      const points = trendSeriesForAccount(trendsById.get(account.id));
      const values = emptyLongTermSeries(dates);
      if (points.length) {
        let latest = 0;
        dates.forEach((date) => {
          const point = points.find((item) => item.date === date);
          if (point) latest = Number(point.value || 0);
          values[date] = latest;
        });
      } else {
        const current = normalizedAmount(account.initial_cash || 0, account.currency || state.baseCurrency);
        dates.forEach((date) => { values[date] = current; });
      }
      return { account, values };
    });
}

function longTermData() {
  const dates = longTermDates();
  const today = dates.at(-1) || todayString();
  const byPerson = {};
  const byCategory = {};
  const total = emptyLongTermSeries(dates);
  const details = [];
  let monthly = 0;

  (state.localFunds || []).forEach((fund) => {
    const amount = normalizedAmount(fund.amount, state.baseCurrency);
    const values = Object.fromEntries(dates.map((date) => [date, amount]));
    const people = (fund.persons || []).length ? fund.persons : [{ name: "Unassigned" }];
    const share = amount / Math.max(people.length, 1);
    dates.forEach((date) => { total[date] += amount; });
    people.forEach((person) => {
      addLongTermValue(byPerson, longTermPersonKey(person), dates, Object.fromEntries(dates.map((date) => [date, share])));
    });
    addLongTermValue(byCategory, fund.kind || "Fund", dates, values);
    const monthlyEstimate = fund.kind === "Pension" && fund.monthly_estimate !== null && fund.monthly_estimate !== undefined
      ? Number(fund.monthly_estimate || 0)
      : null;
    monthly += Number(monthlyEstimate || 0);
    details.push({ label: [fund.kind, fund.fund_name || "", fund.pension_id].filter(Boolean).join(" · "), value: amount, monthly: monthlyEstimate, type: fund.kind || "Fund" });
  });

  longTermAccountSeries(dates).forEach(({ account, values }) => {
    if (!longTermSeriesHasValue(values, dates)) return;
    const people = (account.persons || []).length ? account.persons : [{ name: "Unassigned" }];
    dates.forEach((date) => { total[date] += Number(values[date] || 0); });
    people.forEach((person) => {
      addLongTermValue(
        byPerson,
        longTermPersonKey(person),
        dates,
        Object.fromEntries(dates.map((date) => [date, Number(values[date] || 0) / Math.max(people.length, 1)])),
      );
    });
    addLongTermValue(byCategory, t("accountHoldingsCash"), dates, values);
    details.push({ label: accountLabel(account), value: Number(values[today] || 0), monthly: 0, type: t("accountHoldingsCash") });
  });

  const sortByLatest = (left, right) => Number(right.values[today] || 0) - Number(left.values[today] || 0);
  return {
    dates,
    today,
    total,
    byPerson,
    byCategory,
    details,
    monthly,
    lineSets: {
      total: [{ label: "Total long-term", values: total }],
      people: Object.entries(byPerson).map(([label, values]) => ({ label, values })).sort(sortByLatest),
      funds: Object.entries(byCategory).map(([label, values]) => ({ label, values })).sort(sortByLatest),
    },
  };
}

function renderLongTermDashboard() {
  const data = longTermData();
  const view = ["total", "people", "funds"].includes(state.longTermView) ? state.longTermView : "total";
  const lines = data.lineSets[view] || data.lineSets.total;
  const latest = Number(data.total[data.today] || 0);
  if (!data.details.length || !lines.length) {
    return `
      <div class="chart-card long-term-card">
        <div class="chart-header">
          <div class="chart-title">Long-term funds</div>
        </div>
        <div class="empty">No long-term funds or savings accounts yet</div>
      </div>`;
  }

  const width = 640;
  const height = 230;
  const padLeft = 116;
  const padRight = 22;
  const padTop = 22;
  const padBottom = 40;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;
  const allValues = lines.flatMap((line) => data.dates.map((date) => Number(line.values[date] || 0)));
  const rawMax = Math.max(...allValues, 1);
  const max = rawMax * 1.08;
  const x = (_date, index) => padLeft + (index / Math.max(1, data.dates.length - 1)) * plotWidth;
  const yValue = (value) => padTop + plotHeight - (Number(value || 0) / (max || 1)) * plotHeight;
  const yTicks = [max, max * 0.67, max * 0.33, 0];
  const xTicks = data.dates.length <= 3 ? data.dates : [data.dates[0], data.dates[Math.floor((data.dates.length - 1) / 2)], data.dates.at(-1)];
  const paths = lines.map((line, index) => {
    const points = data.dates.map((date) => ({ date, value: Number(line.values[date] || 0) }));
    const path = linePath(points, (_point, pointIndex) => x(_point.date, pointIndex), (point) => yValue(point.value));
    const color = colorAt(index);
    return `
      <path class="long-term-line" d="${path}" fill="none" stroke="${color}"></path>
      ${points.map((point, pointIndex) => `
        <circle class="trend-hit" cx="${x(point.date, pointIndex).toFixed(1)}" cy="${yValue(point.value).toFixed(1)}" r="15" fill="transparent">
          <title>${esc(`${formatDate(point.date)}\n${line.label}\n${money(point.value, state.baseCurrency, 0)}`)}</title>
        </circle>
      `).join("")}
    `;
  }).join("");
  const lineLegend = lines.map((line, index) => `
    <span title="${esc(`${line.label}\n${money(Number(line.values[data.today] || 0), state.baseCurrency, 0)}`)}"><i style="background:${colorAt(index)}"></i>${esc(line.label)}</span>
  `).join("");
  const personStats = Object.entries(data.byPerson)
    .sort(([, left], [, right]) => Number(right[data.today] || 0) - Number(left[data.today] || 0))
    .slice(0, 4);
  return `
    <div class="chart-card long-term-card">
      <div class="chart-header">
        <div>
          <div class="chart-title">Long-term funds</div>
          <small class="chart-subtitle">Saved ${money(latest, state.baseCurrency, 0)} · <span class="${data.monthly ? "" : "muted-inline"}">Monthly pension estimate ${data.monthly ? fmt(data.monthly, 0) : "N/A"}</span></small>
        </div>
        <div class="long-term-controls">
          <div class="dashboard-view-toggle long-term-toggle" aria-label="Long-term dashboard view">
            <button type="button" data-long-term-view="total" class="${view === "total" ? "active" : ""}">Total</button>
            <button type="button" data-long-term-view="people" class="${view === "people" ? "active" : ""}">People</button>
            <button type="button" data-long-term-view="funds" class="${view === "funds" ? "active" : ""}">Funds</button>
          </div>
          <div class="chart-legend long-term-legend">${lineLegend}</div>
        </div>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Long-term funds line graph">
        ${yTicks.map((tick) => {
          const tickY = yValue(tick);
          return `
            <line class="chart-grid" x1="${padLeft}" y1="${tickY.toFixed(1)}" x2="${width - padRight}" y2="${tickY.toFixed(1)}"></line>
            <text class="axis-label y-axis-label" x="${padLeft - 8}" y="${(tickY + 3).toFixed(1)}">${money(tick, state.baseCurrency, 0)}</text>
          `;
        }).join("")}
        <line class="axis-line" x1="${padLeft}" y1="${height - padBottom}" x2="${width - padRight}" y2="${height - padBottom}"></line>
        <line class="axis-line" x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${height - padBottom}"></line>
        ${paths}
        ${xTicks.map((date, index) => {
          const tickX = x(date, data.dates.indexOf(date));
          const anchor = index === 0 ? "start" : index === xTicks.length - 1 ? "end" : "middle";
          return `<text class="axis-label" x="${tickX.toFixed(1)}" y="${height - 12}" text-anchor="${anchor}">${esc(formatDate(date))}</text>`;
        }).join("")}
      </svg>
      <div class="long-term-summary">
        ${personStats.length ? personStats.map(([label, values], index) => `
          <span title="${esc(`${label}\n${money(values[data.today], state.baseCurrency, 0)}`)}"><i style="background:${colorAt(index)}"></i>${esc(label)} <b>${money(values[data.today], state.baseCurrency, 0)}</b></span>
        `).join("") : '<span>No assigned family members</span>'}
      </div>
    </div>`;
}

function renderMarketCostBars(items) {
  const top = [...items].sort((a, b) => normalizedField(b, "market_value") - normalizedField(a, "market_value")).slice(0, 7);
  const width = 360;
  const height = 242;
  const padLeft = 28;
  const padRight = 22;
  const padTop = 22;
  const padBottom = 74;
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
  const groupWidth = (width - padLeft - padRight) / Math.max(rows.length, 1);
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
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Market value compared with cost basis">
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
        <line class="chart-grid" x1="${padLeft}" y1="${padTop}" x2="${width - padRight}" y2="${padTop}"></line>
        <line class="chart-grid" x1="${padLeft}" y1="${padTop + plotHeight / 2}" x2="${width - padRight}" y2="${padTop + plotHeight / 2}"></line>
        <line class="axis-line" x1="${padLeft}" y1="${baseline}" x2="${width - padRight}" y2="${baseline}"></line>
        ${rows.map((row, index) => {
          const center = padLeft + groupWidth * index + groupWidth / 2;
          const marketHeight = barHeight(row.market);
          const costHeight = barHeight(row.cost);
          const marketX = center - barWidth - gap / 2;
          const costX = center + gap / 2;
          const labelX = center + 6;
          const labelY = baseline + 16;
          const localTooltip = row.currency !== state.baseCurrency
            ? `\nLocal market: ${money(row.localMarket, row.currency, 0)}\nLocal cost: ${money(row.localCost, row.currency, 0)}`
            : "";
          const tooltip = `${row.symbol}\nMarket: ${money(row.market, state.baseCurrency, 0)}\nCost: ${money(row.cost, state.baseCurrency, 0)}${localTooltip}`;
          return `
            <g>
              <title>${esc(tooltip)}</title>
              <rect class="comparison-bar market-bar" x="${marketX.toFixed(1)}" y="${(baseline - marketHeight).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${marketHeight.toFixed(1)}" rx="4" fill="url(#barMarket)"></rect>
              <rect class="comparison-bar cost-bar" x="${costX.toFixed(1)}" y="${(baseline - costHeight).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${costHeight.toFixed(1)}" rx="4" fill="url(#barCost)"></rect>
              <text class="tilted-axis-label comparison-axis-label" x="${labelX.toFixed(1)}" y="${labelY.toFixed(1)}" transform="rotate(-25 ${labelX.toFixed(1)} ${labelY.toFixed(1)})">${esc(row.symbol)}</text>
            </g>
          `;
        }).join("")}
      </svg>
    </div>`;
}

function renderDonut(groups, title, centerLabel, total, centerSub = ["TOP", "ASSET"], extraClass = "") {
  const circumference = 2 * Math.PI * 42;
  let offset = 0;
  const centerSubLines = (centerSub || []).filter(Boolean);
  const centerSubText = centerSubLines.length <= 1
    ? `<text x="65" y="82" class="donut-sub single">${esc(centerSubLines[0] || "")}</text>`
    : centerSubLines.slice(0, 2).map((line, index) => `<text x="65" y="${76 + index * 12}" class="donut-sub">${esc(line)}</text>`).join("");
  return `
    <div class="chart-card donut-card ${esc(extraClass)}">
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
        ${centerSubText}
      </svg>
      <div class="donut-legend">
        ${groups.slice(0, 3).map((group, index) => `
          <span><i style="background:${colorAt(index)}"></i>${esc(group.label)} ${total ? Math.round(group.value / total * 100) : 0}%</span>
        `).join("")}
      </div>
    </div>`;
}

function renderCurrencyAllocation(groups, total) {
  const topPercent = total ? Math.round((groups[0]?.value || 0) / total * 100) : 0;
  return renderDonut(groups, "Currency allocation", `${topPercent}%`, total, [groups[0]?.label || state.baseCurrency], "currency-allocation-card");
}

function renderIndustrySplit(items) {
  const groups = Object.values(items.reduce((result, item) => {
    const label = industryLabel(item) || "Not classified";
    const value = Math.abs(normalizedField(item, "market_value"));
    const group = result[label] || { label, value: 0, holdings: [] };
    group.value += value;
    group.holdings.push({
      symbol: item.holding.symbol || "Unknown",
      name: item.holding.name || item.holding.symbol || "Unknown",
      value,
    });
    result[label] = group;
    return result;
  }, {}))
    .map((group) => ({ ...group, holdings: group.holdings.sort((a, b) => b.value - a.value) }))
    .sort((a, b) => b.value - a.value);
  const total = sum(groups.map((group) => group.value));
  return `
    <div class="chart-card industry-split-card">
      <div class="chart-header">
        <div>
          <div class="chart-title">Industry split</div>
          <span class="chart-subtitle">${groups.length} industries · holdings listed inside each industry</span>
        </div>
        <div class="chart-legend"><span><i style="background:#21a7ff"></i>Portfolio value</span></div>
      </div>
      <div class="industry-split-list">
        ${groups.map((group, index) => {
          const percent = total ? group.value / total * 100 : 0;
          return `
            <div class="industry-split-row">
              <div class="industry-split-head">
                <b>${esc(group.label)}</b>
                <span>${money(group.value, state.baseCurrency, 0)} · ${fmt(percent, 1)}%</span>
              </div>
              <div class="industry-split-track" title="${esc(`${group.label}: ${fmt(percent, 1)}%`)}">
                <i style="width:${Math.max(percent, 0.8)}%;background:${colorAt(index)}"></i>
              </div>
              <div class="industry-holdings">
                ${group.holdings.map((holding) => `<span title="${esc(`${holding.name}: ${money(holding.value, state.baseCurrency, 0)}`)}">${esc(holding.symbol)}</span>`).join("")}
              </div>
            </div>
          `;
        }).join("")}
      </div>
    </div>`;
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
          <span title="${esc(item.holding.symbol)}"><i style="background:${colorAt(index)}"></i>${String(index + 1).padStart(2, "0")} - ${esc(item.holding.symbol.slice(0, 8))}</span>
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
  const height = 165;
  const padLeft = 38;
  const padRight = 26;
  const baseline = 78;
  const topGuide = 25;
  const barSlot = (width - padLeft - padRight) / Math.max(1, top.length);
  const barWidth = Math.min(22, Math.max(8, barSlot * 0.54));
  const gainColor = "#726dff";
  const lossColor = "#ff5f6d";
  return `
    <div class="chart-card line-card">
      <div class="chart-header">
        <div>
          <div class="chart-title">Unrealized P/L by holding</div>
          <span class="chart-subtitle profit-total-summary">Total P/L ${money(total, state.baseCurrency, 0)}</span>
        </div>
        <div class="chart-legend"><span><i style="background:${gainColor}"></i>Gain</span><span><i style="background:${lossColor}"></i>Loss</span></div>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Unrealized profit and loss by holding">
        <line x1="${padLeft}" y1="${topGuide}" x2="${width - padRight}" y2="${topGuide}"></line>
        <line x1="${padLeft}" y1="${baseline}" x2="${width - padRight}" y2="${baseline}" class="axis-line"></line>
        ${top.map((item, index) => {
          const value = normalizedField(item, "unrealized_profit");
          const localValue = Number(item.holding.unrealized_profit || 0);
          const currency = item.holding.currency || state.baseCurrency;
          const localTooltip = currency !== state.baseCurrency ? `\nLocal P/L: ${money(localValue, currency, 0)}` : "";
          const tooltip = `${item.holding.symbol}\nUnrealized P/L: ${money(value, state.baseCurrency, 0)}${localTooltip}`;
          const barHeight = Math.max(3, Math.abs(value) / maxAbs * 48);
          const x = padLeft + index * barSlot + (barSlot - barWidth) / 2;
          const y = value >= 0 ? baseline - barHeight : baseline;
          const color = value >= 0 ? gainColor : lossColor;
          const labelY = value >= 0 ? Math.max(topGuide - 6, y - 7) : Math.min(baseline + 34, y + barHeight + 13);
          return `
          <g>
            <title>${esc(tooltip)}</title>
            <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="4" fill="${color}" opacity="${value >= 0 ? "1" : "0.94"}"></rect>
            <text x="${(x + barWidth / 2).toFixed(1)}" y="${labelY.toFixed(1)}">${fmt(value, 0)}</text>
          </g>
        `;
        }).join("")}
        ${top.map((item, index) => {
          const x = padLeft + index * barSlot + barSlot / 2 + 10;
          const y = baseline + 52;
          return `<text class="tilted-axis-label" x="${x.toFixed(1)}" y="${y}" transform="rotate(-25 ${x.toFixed(1)} ${y})">${esc(item.holding.symbol)}</text>`;
        }).join("")}
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

function txMarketKey(symbol, stockMarket = "") {
  return `${String(symbol || "").toUpperCase().trim()}|${String(stockMarket || "").toUpperCase().trim()}`;
}

function txInstrumentType(tx) {
  return String(tx.instrument_type || tx.asset_class || "").toUpperCase().trim();
}

function equityCompKind(tx) {
  const type = txInstrumentType(tx);
  const asset = String(tx.asset_class || "").toUpperCase().trim();
  if (type === "RSU" || asset === "RSU") return "rsu";
  if (["EMPLOYEE_STOCK_OPTION", "STOCK_OPTION"].includes(type) || ["EMPLOYEE_STOCK_OPTION", "STOCK_OPTION"].includes(asset)) return "option";
  return "";
}

function transactionSignedQuantity(tx) {
  const quantity = Number(tx.quantity || 0);
  const action = String(tx.action || "").toUpperCase();
  return ["SELL", "REMOVE", "SHORT"].includes(action) ? -quantity : quantity;
}

function compensationPriceMap(items) {
  const prices = new Map();
  [...(state.localPrices || [])]
    .sort((a, b) => String(a.price_date || "").localeCompare(String(b.price_date || "")))
    .forEach((priceRow) => {
      const price = Number(priceRow.price || 0);
      if (!priceRow.symbol || !Number.isFinite(price) || price <= 0) return;
      const entry = { price, currency: priceRow.currency || state.baseCurrency, source: "saved price" };
      prices.set(txMarketKey(priceRow.symbol, priceRow.stock_market), entry);
      prices.set(txMarketKey(priceRow.symbol), entry);
    });
  Object.values(state.equityCompQuotes || {}).forEach((quoteRow) => {
    const price = Number(quoteRow.value || 0);
    if (!quoteRow.symbol || !Number.isFinite(price) || price <= 0) return;
    const entry = { price, currency: quoteRow.currency || state.baseCurrency, source: "market quote" };
    prices.set(txMarketKey(quoteRow.symbol), entry);
  });
  items.forEach((item) => {
    const h = item.holding || {};
    const quantity = Math.abs(Number(h.quantity || 0));
    if (!h.symbol || !quantity) return;
    const price = Math.abs(Number(h.market_value || 0)) / quantity;
    if (!Number.isFinite(price) || price <= 0) return;
    const entry = { price, currency: h.currency || state.baseCurrency, source: "current holding price" };
    prices.set(txMarketKey(h.symbol, h.stock_market), entry);
    if (!prices.has(txMarketKey(h.symbol))) prices.set(txMarketKey(h.symbol), entry);
  });
  return prices;
}

function publicStockMarket(stockMarket) {
  const market = String(stockMarket || "").toUpperCase().trim();
  return Boolean(market && !["PRIVATE", "MANUAL", "LOCAL", "UNKNOWN", "N/A", "NONE"].includes(market));
}

function equityCompQuoteSymbols() {
  return [...new Set((state.localTransactions || [])
    .filter((tx) => {
      if (!equityCompKind(tx)) return false;
      const market = txInstrumentType(tx) === "EMPLOYEE_STOCK_OPTION" ? tx.public_market : tx.stock_market;
      return publicStockMarket(market);
    })
    .map((tx) => {
      if (txInstrumentType(tx) === "EMPLOYEE_STOCK_OPTION") return tx.public_symbol;
      return equityCompKind(tx) === "option" ? (tx.underlying_symbol || tx.symbol) : tx.symbol;
    })
    .map(cleanSecuritySymbol)
    .filter(Boolean))];
}

async function loadEquityCompQuotes() {
  const symbols = equityCompQuoteSymbols();
  if (!symbols.length) {
    state.equityCompQuotes = {};
    if (state.items?.length) renderAnalytics(state.items);
    return;
  }
  const data = await api("/api/banner/resolve", {
    method: "POST",
    body: JSON.stringify({ items: symbols.map((symbol) => ({ symbol, type: "quote", label: symbol })) }),
  });
  state.equityCompQuotes = Object.fromEntries((data.items || [])
    .filter((item) => item.symbol && Number(item.value || 0) > 0)
    .map((item) => [cleanSecuritySymbol(item.symbol), item]));
  if (state.items?.length) renderAnalytics(state.items);
}

function equityCompLots(kind, items) {
  const prices = compensationPriceMap(items);
  const lots = [];
  [...(state.localTransactions || [])]
    .filter((tx) => equityCompKind(tx) === kind)
    .sort((a, b) => String(a.trade_date || "").localeCompare(String(b.trade_date || "")) || String(a.created_at || "").localeCompare(String(b.created_at || "")))
    .forEach((tx) => {
      const quantity = transactionSignedQuantity(tx);
      const key = txMarketKey(tx.symbol, tx.stock_market);
      if (quantity > 0) {
        const employeeOption = txInstrumentType(tx) === "EMPLOYEE_STOCK_OPTION";
        const priceSymbol = employeeOption
          ? (tx.public_symbol || "")
          : kind === "option" ? (tx.underlying_symbol || tx.symbol) : tx.symbol;
        const priceMarket = employeeOption ? tx.public_market : tx.stock_market;
        const marketPrice = prices.get(txMarketKey(priceSymbol, priceMarket))
          || prices.get(txMarketKey(priceSymbol))
          || prices.get(key)
          || (employeeOption && String(tx.listing_status || "PRIVATE") !== "PUBLIC" && Number(tx.manual_share_value || 0) > 0
            ? { price: Number(tx.manual_share_value), currency: tx.currency || state.baseCurrency, source: "private company valuation" }
            : null);
        const txPrice = Number(tx.price || tx.price_input || 0);
        const scheduleTranches = Array.isArray(tx.vesting_schedule?.tranches) ? tx.vesting_schedule.tranches : [];
        const tranches = scheduleTranches.length
          ? scheduleTranches.map((tranche) => ({ quantity: Number(tranche.quantity || 0), vestDate: parseDateInput(tranche.vest_date), sequence: tranche.sequence }))
          : [{ quantity, vestDate: parseDateInput(tx.vest_date), sequence: 1 }];
        tranches.filter((tranche) => tranche.quantity > 0).forEach((tranche) => lots.push({
            key,
            transactionId: tx.id || "",
            trancheSequence: tranche.sequence,
            symbol: employeeOption ? (tx.company_name || tx.security_name || "Employee option") : (tx.symbol || "Unknown"),
            internalSymbol: tx.symbol || "",
            underlyingSymbol: employeeOption ? (tx.public_symbol || "") : (tx.underlying_symbol || tx.symbol || ""),
            stockMarket: employeeOption ? (tx.public_market || "PRIVATE") : (tx.stock_market || ""),
            listingStatus: employeeOption ? (tx.listing_status || "PRIVATE") : "PUBLIC",
            quantity: tranche.quantity,
            vestDate: tranche.vestDate,
            strikePrice: Number(tx.strike_price || 0),
            optionType: employeeOption ? "" : (tx.option_type || ""),
            publicMarket: publicStockMarket(priceMarket),
            currentPrice: Number(marketPrice?.price || 0),
            hasMarketPrice: Number(marketPrice?.price || 0) > 0,
            priceSource: marketPrice?.source || "",
            currency: marketPrice?.currency || tx.currency || state.baseCurrency,
            unitPrice: kind === "rsu" ? Number(marketPrice?.price || txPrice || 0) : Number(marketPrice?.price || 0),
          }));
        return;
      }
      let remaining = Math.abs(quantity);
      lots
        .filter((lot) => lot.key === key && lot.quantity > 0)
        .sort((a, b) => String(a.vestDate || "9999-12-31").localeCompare(String(b.vestDate || "9999-12-31")))
        .forEach((lot) => {
          if (remaining <= 0) return;
          const used = Math.min(lot.quantity, remaining);
          lot.quantity -= used;
          remaining -= used;
        });
    });
  return lots.filter((lot) => lot.quantity > 0.000001);
}

function lotVestingStatus(lot) {
  const vestDate = parseDateInput(lot.vestDate);
  return vestDate && vestDate <= todayString() ? "vested" : "unvested";
}

function lotBaseValue(lot) {
  return normalizedAmount(Number(lot.quantity || 0) * Number(lot.unitPrice || 0), lot.currency || state.baseCurrency);
}

function optionLotValue(lot) {
  if (!lot.hasMarketPrice) return 0;
  return normalizedAmount(Math.max(Number(lot.currentPrice || 0) - Number(lot.strikePrice || 0), 0) * Number(lot.quantity || 0), lot.currency || state.baseCurrency);
}

function equityCompLotValue(kind, lot) {
  return kind === "option" ? optionLotValue(lot) : lotBaseValue(lot);
}

function equityCompLotLocalValue(kind, lot) {
  if (kind === "option") {
    if (!lot.hasMarketPrice) return 0;
    return Math.max(Number(lot.currentPrice || 0) - Number(lot.strikePrice || 0), 0) * Number(lot.quantity || 0);
  }
  return Number(lot.quantity || 0) * Number(lot.unitPrice || 0);
}

function localCurrencyValueText(kind, lots) {
  const byCurrency = lots.reduce((acc, lot) => {
    const currency = lot.currency || state.baseCurrency;
    acc[currency] = (acc[currency] || 0) + equityCompLotLocalValue(kind, lot);
    return acc;
  }, {});
  return Object.entries(byCurrency)
    .filter(([, value]) => Math.abs(Number(value || 0)) > 0.005)
    .map(([currency, value]) => money(value, currency, 0))
    .join(" / ");
}

function equityCompValueHtml(kind, lots) {
  const quantity = sum(lots.map((lot) => lot.quantity));
  if (!quantity) return '<span class="muted-inline">∅</span>';
  if (kind === "rsu" && lots.every((lot) => Number(lot.unitPrice || 0) <= 0)) return '<span class="muted-inline">Missing market price</span>';
  if (kind === "option" && lots.every((lot) => !lot.publicMarket && !lot.hasMarketPrice)) return '<span class="muted-inline">Private company · add share valuation</span>';
  if (kind === "option" && lots.every((lot) => !lot.hasMarketPrice)) return '<span class="muted-inline">Missing stock price</span>';
  const baseValue = sum(lots.map((lot) => equityCompLotValue(kind, lot)));
  const localText = localCurrencyValueText(kind, lots);
  const baseText = money(baseValue, state.baseCurrency, 0);
  return `
    <span class="dual-currency-value">
      <b>${esc(baseText)}</b>
      ${localText && localText !== baseText ? `<small>${esc(localText)}</small>` : ""}
    </span>
  `;
}

function weightedAverageStrike(lots) {
  const quantity = sum(lots.map((lot) => lot.quantity));
  if (!quantity) return 0;
  return sum(lots.map((lot) => Number(lot.strikePrice || 0) * Number(lot.quantity || 0))) / quantity;
}

function vestingDetailsTitle(lots, unitLabel) {
  if (!lots.length) return "";
  return lots.map((lot) => {
    const date = lot.vestDate ? formatDate(lot.vestDate) : "Missing vest date";
    return `${fmt(lot.quantity, 2)} ${unitLabel} - Vest Date: ${date}`;
  }).join("\n");
}

function equityCompRows(rsuLots, optionLots) {
  return [
    ...rsuLots.map((lot) => ({ ...lot, kind: "rsu" })),
    ...optionLots.map((lot) => ({ ...lot, kind: "option" })),
  ].reduce((acc, lot) => {
    const key = [
      lot.kind,
      lot.symbol,
      lot.stockMarket,
      lot.kind === "option" ? lot.underlyingSymbol : "",
      lot.kind === "option" ? lot.strikePrice : "",
      lot.kind === "option" ? lot.optionType : "",
    ].join("|");
    acc[key] = acc[key] || { ...lot, vested: [], unvested: [] };
    acc[key][lotVestingStatus(lot)].push(lot);
    return acc;
  }, {});
}

function equityCompPriceText(group) {
  if (group.kind === "rsu") {
    const price = Number(group.unitPrice || group.currentPrice || 0);
    return price > 0 ? money(price, group.currency || state.baseCurrency, 2) : "Missing market price";
  }
  if (!group.publicMarket && !group.hasMarketPrice) return "Private company · valuation missing";
  const current = Number(group.currentPrice || 0);
  const currentText = current > 0 ? money(current, group.currency || state.baseCurrency, 2) : "Missing stock price";
  const source = !group.publicMarket && group.priceSource ? ` (${group.priceSource})` : "";
  return `${currentText}${source} / ${money(group.strikePrice || 0, group.currency || state.baseCurrency, 2)}`;
}

function renderEquityCompTable(rsuLots, optionLots) {
  const groups = Object.values(equityCompRows(rsuLots, optionLots)).sort((a, b) => (
    a.kind.localeCompare(b.kind) || a.symbol.localeCompare(b.symbol) || Number(a.strikePrice || 0) - Number(b.strikePrice || 0)
  ));
  if (!groups.length) return '<div class="empty compact-empty">No RSU or stock option grants</div>';
  return `
    <div class="equity-comp-table-wrap">
      <table class="equity-comp-table">
        <thead>
          <tr>
            <th>Instrument</th>
            <th>Type</th>
            <th>Vested</th>
            <th>Vested value</th>
            <th>Unvested</th>
            <th>Unvested value</th>
            <th>Current / Strike</th>
          </tr>
        </thead>
        <tbody>
          ${groups.map((group) => {
            const vestedQty = sum(group.vested.map((lot) => lot.quantity));
            const unvestedQty = sum(group.unvested.map((lot) => lot.quantity));
            const unitLabel = group.kind === "rsu" ? "RSU" : "options";
            const unvestedTitle = vestingDetailsTitle(group.unvested, unitLabel);
            const instrumentDetail = group.kind === "option"
              ? `${group.publicMarket ? (group.stockMarket || "Public") : "Private company"}${group.underlyingSymbol ? ` · Linked ${group.underlyingSymbol}` : ""}${group.optionType ? ` · ${group.optionType}` : ""}`
              : (group.stockMarket || "No market");
            return `
              <tr>
                <td><b>${esc(group.symbol)}</b><small>${esc(instrumentDetail)}</small></td>
                <td><span class="equity-kind ${group.kind}">${group.kind === "rsu" ? "RSU" : "Option"}</span></td>
                <td>${fmt(vestedQty, 2)}</td>
                <td>${equityCompValueHtml(group.kind, group.vested)}</td>
                <td class="${unvestedQty ? "vesting-tooltip-cell" : ""}" title="${esc(unvestedTitle)}">${fmt(unvestedQty, 2)}</td>
                <td>${equityCompValueHtml(group.kind, group.unvested)}</td>
                <td>${esc(equityCompPriceText(group))}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderEquityCompDashboard(items) {
  const rsuLots = equityCompLots("rsu", items);
  const optionLots = equityCompLots("option", items);
  const rsuQuantity = sum(rsuLots.map((lot) => lot.quantity));
  const optionQuantity = sum(optionLots.map((lot) => lot.quantity));
  const hasData = rsuLots.length || optionLots.length;
  return `
    <div class="chart-card equity-comp-card">
      <div class="chart-header">
        <div>
          <div class="chart-title">RSU and stock options</div>
          <span class="chart-subtitle">RSU value uses the app market price. Options use public quotes or the latest private share valuation, minus strike.</span>
        </div>
        <div class="chart-legend">
          ${rsuLots.length ? `<span><i style="background:#2ee59d"></i>${fmt(rsuQuantity, 2)} RSU shares</span>` : ""}
          ${optionLots.length ? `<span><i style="background:#21a7ff"></i>${fmt(optionQuantity, 2)} stock options</span>` : ""}
        </div>
      </div>
      ${hasData ? renderEquityCompTable(rsuLots, optionLots) : '<div class="empty compact-empty">No RSU or stock option grants</div>'}
    </div>
  `;
}

function renderAnalytics(items) {
  const board = $("analyticsBoard");
  if (!board) return;
  if (!state.dashboard) loadDashboardSettings();
  renderDashboardControls();
  if (!items.length && !(state.localFunds || []).length) {
    board.innerHTML = '<div class="empty">No portfolio data</div>';
    return;
  }
  const total = sum(items.map((item) => normalizedField(item, "market_value"))) || 1;
  const assetGroups = groupValues(items, (item) => item.holding.asset_class);
  const currencyGroups = groupValues(items, (item) => item.holding.currency);
  const renderers = {
    portfolio_value: () => renderPortfolioValueDashboard(items),
    long_term_savings: () => renderFundsOverviewDashboard(),
    account_trend: () => renderAccountValueTrend(),
    long_term: () => renderLongTermDashboard(),
    market_cost: () => renderMarketCostBars(items),
    asset_mix: () => renderDonut(assetGroups, "Asset mix", `${Math.round((assetGroups[0]?.value || 0) / total * 100)}%`, total),
    industry_split: () => renderIndustrySplit(items),
    top_holdings: () => renderMiniBars(items),
    coverage: () => renderCompleteness(items),
    currency: () => renderCurrencyAllocation(currencyGroups, total),
    equity_comp: () => renderEquityCompDashboard(items),
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
  const rows = portfolioItems(items);
  renderSummary(rows);
  renderAnalytics(rows);
  renderRows(rows);
}

function rerenderPortfolioIfLoaded() {
  if (state.items.length) renderPortfolio(state.items);
}

function reportBackgroundError(error) {
  $("status").textContent = `Error: ${error.message}`;
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

function brokerLabel(broker) {
  return `${broker.name} · ${broker.country} · ${broker.currency}`;
}

function brokerByName(name) {
  return state.brokers.find((broker) => broker.name === name);
}

function ensureBrokerOption(name) {
  const value = String(name || "").trim();
  if (!value) return;
  ["localAccountBroker", "editAccountBroker"].forEach((id) => {
    const select = $(id);
    if (!select || [...select.options].some((option) => option.value === value)) return;
    select.insertAdjacentHTML("beforeend", `<option value="${esc(value)}">${esc(value)} · Unlisted</option>`);
  });
}

function refreshBrokerSelects() {
  ["localAccountBroker", "editAccountBroker"].forEach((id) => {
    const select = $(id);
    if (!select) return;
    const current = select.value;
    select.innerHTML = '<option value="">Choose broker</option>' + state.brokers
      .map((broker) => `<option value="${esc(broker.name)}">${esc(brokerLabel(broker))}</option>`)
      .join("");
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  });
}

function applyBrokerToAccount(brokerId, locationId, currencyId) {
  const broker = brokerByName(valueOf(brokerId));
  if (!broker) return;
  $(locationId).value = normalizeAccountCountry(broker.country);
  $(currencyId).value = broker.currency;
}

async function loadBrokers() {
  const data = await api("/api/local/brokers");
  state.brokers = data.items || [];
  refreshBrokerSelects();
  const list = $("brokersList");
  if (list) {
    list.innerHTML = state.brokers.length ? state.brokers.map((broker) => `
      <div class="stack-item management-item">
        <b>${esc(broker.name)}</b>
        <span>${esc(broker.country)} · ${esc(broker.currency)}${broker.attached_accounts ? ` · ${broker.attached_accounts} account${broker.attached_accounts === 1 ? "" : "s"}` : ""}</span>
        <button class="secondary compact-button" type="button" data-edit-broker="${esc(broker.id)}">Edit</button>
        <button class="secondary compact-button" type="button" data-delete-broker="${esc(broker.id)}"${broker.attached_accounts ? " disabled" : ""} title="${broker.attached_accounts ? "Cannot delete while attached to an account" : "Remove broker"}">Remove</button>
        <div class="sub">${esc(broker.comments || "No comments")}</div>
      </div>
    `).join("") : '<div class="empty">No brokers yet</div>';
  }
}

async function saveBroker() {
  await api("/api/local/brokers", {
    method: "POST",
    body: JSON.stringify({
      id: state.editingBrokerId || undefined,
      name: valueOf("brokerName"),
      country: valueOf("brokerCountry"),
      currency: valueOf("brokerCurrency"),
      comments: valueOf("brokerComments"),
    }),
  });
  $("brokerStatus").textContent = state.editingBrokerId ? "Broker updated" : "Broker saved";
  clearBrokerForm();
  await loadBrokers();
}

function clearBrokerForm() {
  state.editingBrokerId = "";
  ["brokerName", "brokerComments"].forEach((id) => { $(id).value = ""; });
  $("brokerCountry").value = "USA";
  $("brokerCurrency").value = "USD";
}

function editBroker(brokerId) {
  const broker = state.brokers.find((item) => item.id === brokerId);
  if (!broker) return;
  state.editingBrokerId = broker.id;
  $("brokerName").value = broker.name || "";
  $("brokerCountry").value = normalizeAccountCountry(broker.country);
  $("brokerCurrency").value = broker.currency || preferredCurrencyForLocation(broker.country) || "USD";
  $("brokerComments").value = broker.comments || "";
  $("brokerStatus").textContent = `Editing ${broker.name}`;
}

function personFullName(person) {
  return [person.first_name, person.last_name].map((part) => String(part || "").trim()).filter(Boolean).join(" ") || person.name || "Family member";
}

function memberLabel(member) {
  return personFullName(member);
}

function memberMetaHtml(member) {
  const rows = [
    ["Gender", member.gender || "Not set"],
    ["Birth Date", formatDate(member.birth_date)],
    ["Retire Age", member.retire_age ? fmt(member.retire_age, 1) : "Not set"],
    ["Age", member.age ? fmt(member.age, 1) : ""],
  ].filter(([, value]) => value !== "");
  return rows.map(([label, value]) => `<span><strong>${esc(label)}</strong>${esc(value)}</span>`).join("");
}

function familyMemberById(id) {
  return state.familyMembers.find((member) => member.id === id);
}

function personFromFamilyMember(member) {
  return {
    member_id: member.id,
    name: memberLabel(member),
    first_name: member.first_name || "",
    last_name: member.last_name || "",
    gender: member.gender || "",
    birth_date: member.birth_date,
    retire_age: member.retire_age,
    age: member.age,
  };
}

function refreshFamilyMemberSelects() {
  const options = '<option value="">Choose family member</option>' + state.familyMembers
    .map((member) => `<option value="${esc(member.id)}">${esc(memberLabel(member))}</option>`)
    .join("");
  ["localAccountFamilyMember", "editAccountFamilyMember", "fundFamilyMember", "editFundFamilyMember", "familyAttachMember"].forEach((id) => {
    const select = $(id);
    if (!select) return;
    const current = select.value;
    select.innerHTML = options;
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  });
}

function refreshFamilyAccountSelects() {
  const options = '<option value="">Choose account</option>' + state.localAccounts
    .map((account) => `<option value="${esc(account.id)}">${esc(accountLabel(account))} · ${esc(account.type)}</option>`)
    .join("");
  ["familyAttachAccount"].forEach((id) => {
    const select = $(id);
    if (!select) return;
    const current = select.value;
    select.innerHTML = options;
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  });
}

async function loadFamilyMembers() {
  const data = await api("/api/local/family-members");
  state.familyMembers = data.items || [];
  refreshFamilyMemberSelects();
  refreshFamilyAccountSelects();
  renderSimulationPersonOptions();
  const list = $("familyMembersList");
  if (list) {
    list.innerHTML = state.familyMembers.length ? state.familyMembers.map((member) => {
      const attachedAccounts = member.attached_account_items || [];
      return `
      <div class="stack-item management-item family-member-item">
        <div class="family-member-main">
          <b>${esc(memberLabel(member))}</b>
          <div class="family-member-meta">${memberMetaHtml(member)}</div>
          <div class="sub">${esc(member.comments || "No comments")}</div>
        </div>
        <div class="family-member-actions">
          <button class="secondary compact-button" type="button" data-edit-family-member="${esc(member.id)}">Edit</button>
          <button class="secondary compact-button" type="button" data-delete-family-member="${esc(member.id)}"${member.attached_accounts ? " disabled" : ""} title="${member.attached_accounts ? "Cannot delete while attached to an account" : "Remove family member"}">Remove</button>
        </div>
        <div class="attached-account-list">
          ${attachedAccounts.length ? attachedAccounts.map((account) => `<span>${esc(account.label)} · ${esc(account.type)}</span>`).join("") : "<em>No attached accounts</em>"}
        </div>
      </div>
    `;
    }).join("") : '<div class="empty">No family members yet</div>';
  }
}

async function saveFamilyMember() {
  const birthDate = dateValue("familyMemberBirthDate");
  if (!birthDate) {
    $("familyStatus").textContent = `Birthday must use ${DATE_PLACEHOLDER}`;
    return;
  }
  await api("/api/local/family-members", {
    method: "POST",
    body: JSON.stringify({
      id: state.editingFamilyMemberId || undefined,
      first_name: valueOf("familyMemberFirstName"),
      last_name: valueOf("familyMemberLastName"),
      gender: valueOf("familyMemberGender"),
      birth_date: birthDate,
      retire_age: valueOf("familyMemberRetireAge"),
      comments: valueOf("familyMemberComments"),
    }),
  });
  $("familyStatus").textContent = state.editingFamilyMemberId ? "Person updated" : "Person saved";
  clearFamilyMemberForm();
  await loadFamilyMembers();
}

function clearFamilyMemberForm() {
  state.editingFamilyMemberId = "";
  ["familyMemberFirstName", "familyMemberLastName", "familyMemberBirthDate", "familyMemberRetireAge", "familyMemberComments"].forEach((id) => { $(id).value = ""; });
  $("familyMemberGender").value = "";
}

function editFamilyMember(memberId) {
  const member = familyMemberById(memberId);
  if (!member) return;
  state.editingFamilyMemberId = member.id;
  $("familyMemberFirstName").value = member.first_name || "";
  $("familyMemberLastName").value = member.last_name || "";
  $("familyMemberGender").value = member.gender || "";
  setDateField("familyMemberBirthDate", member.birth_date || "");
  $("familyMemberRetireAge").value = member.retire_age || "";
  $("familyMemberComments").value = member.comments || "";
  $("familyStatus").textContent = `Editing ${memberLabel(member)}`;
}

function attachFamilyMember(listKey, selectId, statusId, { single = false } = {}) {
  const member = familyMemberById(valueOf(selectId));
  if (!member) {
    $(statusId).textContent = "Choose a family member first";
    return;
  }
  const person = personFromFamilyMember(member);
  const current = state[listKey] || [];
  if (current.some((item) => item.member_id === person.member_id)) {
    $(statusId).textContent = "Family member already attached";
    return;
  }
  state[listKey] = single ? [person] : current.concat(person);
  $(selectId).value = "";
  $(statusId).textContent = single ? "Family member attached" : `${state[listKey].length} family members attached`;
  renderPersonLists();
}

function accountAllowsMultipleMembers(account) {
  return account?.type !== "Long-Term Savings";
}

function accountSavePayload(account, persons) {
  return {
    id: account.id,
    type: account.type,
    location: account.location,
    currency: account.currency,
    initial_cash: account.initial_cash || 0,
    username: account.username || "",
    account_id: account.account_id || "",
    management_company: account.management_company || "",
    persons,
    comments: account.comments || "",
  };
}

async function attachAccountToMember() {
  const account = state.localAccounts.find((item) => item.id === valueOf("familyAttachAccount"));
  const member = familyMemberById(valueOf("familyAttachMember"));
  if (!account || !member) {
    $("accountOwnershipStatus").textContent = "Choose an account and a family member";
    return;
  }
  const person = personFromFamilyMember(member);
  const current = account.persons || [];
  if (current.some((item) => item.member_id === person.member_id)) {
    $("accountOwnershipStatus").textContent = "That member is already attached to this account";
    return;
  }
  const persons = accountAllowsMultipleMembers(account) ? current.concat(person) : [person];
  await api("/api/local/accounts", {
    method: "POST",
    body: JSON.stringify(accountSavePayload(account, persons)),
  });
  $("accountOwnershipStatus").textContent = accountAllowsMultipleMembers(account)
    ? "Member attached to account"
    : "Member attached as the account owner";
  await Promise.all([loadLocalAccounts(), loadFamilyMembers(), loadPortfolio()]);
}

function isImportedAccount(account) {
  return String(account.account_id || "").startsWith("import-") || String(account.source || "").includes("import") || String(account.comments || "").toLowerCase().includes("imported");
}

function refreshLocalAccountSelects() {
  const accountOptions = '<option value="">All local accounts</option>' + state.localAccounts.map(accountOptionHtml).join("");
  ["securityAccount", "employeeWizardAccount", "reportAccount", "employeeExerciseAccount"].forEach((id) => {
    const select = $(id);
    if (!select) return;
    const current = select.value;
    const employeeWorkflowAccounts = (id === "employeeWizardAccount" || (id === "securityAccount" && state.securitiesWorkflow === "employee-options"))
      ? state.localAccounts.filter((account) => String(account.type || "").toUpperCase() === "ESOP")
      : state.localAccounts;
    select.innerHTML = ["securityAccount", "employeeWizardAccount", "employeeExerciseAccount"].includes(id)
      ? (employeeWorkflowAccounts.map(accountOptionHtml).join("") || (["securityAccount", "employeeWizardAccount"].includes(id) ? '<option value="">Create an ESOP account first</option>' : ""))
      : accountOptions;
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  });
  updateEmployeeOptionsAccountNotice();
  const historySelect = $("historyAccount");
  if (historySelect) {
    const current = historySelect.value;
    historySelect.innerHTML = '<option value="">Choose account</option>' + state.localAccounts.map(accountOptionHtml).join("");
    if ([...historySelect.options].some((option) => option.value === current)) historySelect.value = current;
  }
  refreshFundAccountSelects();
}

function refreshFundAccountSelects() {
  const accounts = (state.localAccounts || []).filter((account) => account.type === "Long-Term Savings");
  const options = '<option value="">No linked long-term account</option>' + accounts.map(accountOptionHtml).join("");
  ["fundAccount", "editFundAccount"].forEach((id) => {
    const select = $(id);
    if (!select) return;
    const current = select.value;
    select.innerHTML = options;
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  });
}

async function loadLocalAccounts() {
  const data = await api("/api/local/accounts");
  state.localAccounts = data.items || [];
  refreshLocalAccountSelects();
  refreshFamilyAccountSelects();
  renderFundsOverview();
  rerenderPortfolioIfLoaded();
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
      <button class="secondary compact-button" type="button" data-edit-account="${esc(account.id)}">Edit</button>
      ${isImportedAccount(account) ? '<span class="badge ok" title="Synced from the configured import source. Refresh with Sync import.">Synced</span>' : '<span class="badge" title="Manual account">Manual</span>'}
      <div class="sub">Initial cash ${fmt(account.initial_cash)}${(account.persons || []).length ? ` · ${(account.persons || []).map(personLabel).map(esc).join(" · ")}` : ""} · ${esc(cleanSourceLabel(account.comments) || "No comments")}</div>
    </div>
  `).join("") : '<div class="empty">No local accounts yet</div>';
  renderPersonLists();
}

function setAccountsTab(tab) {
  const activeTab = tab === "existing" ? "existing" : "new";
  document.querySelectorAll("[data-account-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.accountTab === activeTab);
  });
  $("accountNewPanel").hidden = activeTab !== "new";
  $("accountExistingPanel").hidden = activeTab !== "existing";
}

async function saveLocalAccount() {
  const country = normalizeAccountCountry(valueOf("localAccountLocation"));
  const payload = {
    type: valueOf("localAccountType"),
    location: country,
    currency: valueOf("localAccountCurrency") || "USD",
    initial_cash: valueOf("localInitialCash") || 0,
    username: valueOf("localUsername"),
    account_id: valueOf("localAccountId"),
    management_company: valueOf("localAccountBroker"),
    persons: state.localAccountPersons.map((person) => ({ ...person })),
    comments: valueOf("localAccountComments"),
  };
  await api("/api/local/accounts", { method: "POST", body: JSON.stringify(payload) });
  $("accountsStatus").textContent = "Account created";
  resetNewAccountForm();
  await loadLocalAccounts();
  await loadPortfolio();
  if (state.returnToEmployeeOptionsAfterAccount && payload.type === "ESOP") {
    state.returnToEmployeeOptionsAfterAccount = false;
    closeModal($("accountsModal"));
    setSecuritiesWorkflow("employee-options");
    openModal("securitiesModal");
    $("employeeOptionListStatus").textContent = "ESOP account created. You can now save employee option grants.";
    requestAnimationFrame(() => $("employeeWizardCompany")?.focus());
  }
}

function resetNewAccountForm() {
  $("localAccountType").value = "Investment";
  $("localAccountLocation").value = "USA";
  $("localAccountCurrency").value = "USD";
  ["localInitialCash", "localUsername", "localAccountId", "localAccountBroker", "localAccountComments", "localAccountFamilyMember"].forEach((id) => { $(id).value = ""; });
  state.localAccountPersons = [];
  renderPersonLists();
}

function editLocalAccount(accountId) {
  const account = state.localAccounts.find((item) => item.id === accountId);
  if (!account) return;
  state.editingAccountId = account.id;
  $("editAccountType").value = account.type || "Investment";
  $("editAccountLocation").value = normalizeAccountCountry(account.location);
  $("editAccountCurrency").value = account.currency || "USD";
  $("editInitialCash").value = account.initial_cash || 0;
  $("editUsername").value = account.username || "";
  $("editAccountId").value = account.account_id || "";
  ensureBrokerOption(account.management_company);
  $("editAccountBroker").value = account.management_company || "";
  $("editAccountComments").value = account.comments || "";
  $("editAccountFamilyMember").value = "";
  state.editAccountPersons = (account.persons || []).map((person) => ({ ...person }));
  $("editAccountStatus").textContent = accountLabel(account);
  renderPersonLists();
  openModal("accountEditModal");
}

async function saveEditAccount() {
  const account = state.localAccounts.find((item) => item.id === state.editingAccountId);
  if (!account) {
    $("editAccountStatus").textContent = "Choose an account to edit";
    return;
  }
  if (!confirm(`Save changes to ${accountLabel(account)}?`)) return;
  const country = normalizeAccountCountry(valueOf("editAccountLocation"));
  const payload = {
    id: account.id,
    type: valueOf("editAccountType"),
    location: country,
    currency: valueOf("editAccountCurrency") || "USD",
    initial_cash: valueOf("editInitialCash") || 0,
    username: valueOf("editUsername"),
    account_id: valueOf("editAccountId"),
    management_company: valueOf("editAccountBroker"),
    persons: state.editAccountPersons.map((person) => ({ ...person })),
    comments: valueOf("editAccountComments"),
  };
  await api("/api/local/accounts", { method: "POST", body: JSON.stringify(payload) });
  $("accountsStatus").textContent = "Account updated";
  $("editAccountStatus").textContent = "Account updated";
  closeModal($("accountEditModal"));
  state.editingAccountId = "";
  state.editAccountPersons = [];
  await loadLocalAccounts();
  await loadPortfolio();
}

async function importSourceToLocal() {
  $("accountsStatus").textContent = "Importing holdings";
  appLog("source_import.start");
  const result = await api("/api/local/import/source", { method: "POST", body: "{}" });
  appLog("source_import.done", {
    accounts: result.accounts,
    positions: result.positions,
    source_transactions: result.source_transactions,
    price_history: result.price_history,
    source: result.source,
  });
  $("accountsStatus").textContent = `Imported ${result.positions} positions and ${result.accounts} accounts`;
  await loadLocalAccounts();
  await loadLocalSecurities();
  await loadLocalPrices();
  await loadPortfolio({ refresh: true });
}

function transactionCashImpact(tx) {
  const value = Number(tx.quantity || 0) * Number(tx.price || 0);
  if (tx.action === "BUY") return -value;
  if (tx.action === "SELL" || tx.action === "SHORT" || tx.action === "DIVIDEND" || tx.action === "INTEREST") return value;
  if (tx.action === "FEE") return -value;
  return 0;
}

function cleanSecuritySymbol(value) {
  const text = String(value || "").trim().toUpperCase();
  return text.startsWith("GF_") ? text.slice(3) : text;
}

function instrumentLabel(item) {
  const name = item.name && item.name !== item.symbol ? ` · ${item.name}` : "";
  const employeeOption = item.instrument_type === "EMPLOYEE_STOCK_OPTION";
  const displayIdentity = employeeOption
    ? `${item.company_name || item.name || "Employee option"}${item.grant_id ? ` · ${item.grant_id}` : ""}`
    : item.symbol;
  const derivative = ["OPTION", "EMPLOYEE_STOCK_OPTION", "STOCK_OPTION"].includes(item.instrument_type)
    ? ` · ${item.option_type} ${fmt(item.strike_price, 4)} · exp ${formatDate(item.expiration_date)}`
    : item.instrument_type === "FUTURE"
      ? ` · exp ${formatDate(item.expiration_date)}`
      : "";
  return `${displayIdentity}${name} · ${optionLabel(item.instrument_type)}${derivative}`;
}

function instrumentById(id) {
  return state.manualSecurities.find((item) => item.id === id);
}

function selectedTransactionInstrumentType() {
  const instrument = instrumentById(valueOf("securityKnownInstrument"));
  return String(instrument?.instrument_type || valueOf("securityAssetClass") || "").toUpperCase();
}

function addCalendarMonths(isoDate, months) {
  const iso = parseDateInput(isoDate);
  if (!iso || !Number.isInteger(Number(months))) return "";
  const [year, month, day] = iso.split("-").map(Number);
  const monthIndex = month - 1 + Number(months);
  const targetYear = year + Math.floor(monthIndex / 12);
  const targetMonthIndex = ((monthIndex % 12) + 12) % 12;
  const lastDay = new Date(Date.UTC(targetYear, targetMonthIndex + 1, 0)).getUTCDate();
  const targetDay = Math.min(day, lastDay);
  return `${targetYear}-${String(targetMonthIndex + 1).padStart(2, "0")}-${String(targetDay).padStart(2, "0")}`;
}

function vestingScheduleFromForm(totalQuantity = Number(valueOf("securityQuantity") || 0)) {
  return {
    enabled: true,
    mode: valueOf("securityVestingMode") || "PERCENT",
    vesting_start_date: dateValue("securityVestingStartDate"),
    duration_months: Number(valueOf("securityVestingDuration") || 0),
    cliff_months: Number(valueOf("securityVestingCliffMonths") || 0),
    cliff_value: Number(valueOf("securityVestingCliffValue") || 0),
    interval_months: Number(valueOf("securityVestingInterval") || 0),
    installment_value: Number(valueOf("securityVestingInstallmentValue") || 0),
    total_quantity: Number(totalQuantity || 0),
  };
}

function buildVestingPreview(config) {
  const total = Number(config.total_quantity || 0);
  const duration = Number(config.duration_months);
  const cliffMonths = Number(config.cliff_months);
  const interval = Number(config.interval_months);
  const cliffValue = Number(config.cliff_value);
  const installmentValue = Number(config.installment_value);
  if (!parseDateInput(config.vesting_start_date)) throw new Error("Enter the Vesting Start Date");
  if (!(total > 0)) throw new Error("Enter the total number of options");
  if (!Number.isInteger(duration) || duration < 1 || duration > 600) throw new Error("Total period must be 1–600 months");
  if (!Number.isInteger(cliffMonths) || cliffMonths < 0 || cliffMonths > duration) throw new Error("Cliff must be within the total period");
  if (!Number.isInteger(interval) || interval < 1 || interval > duration) throw new Error("Recurring interval must be within the total period");
  if (!(cliffValue > 0)) throw new Error("Cliff amount must be greater than zero");
  if (config.mode === "PERCENT" && cliffValue > 100) throw new Error("Cliff percentage cannot exceed 100%");
  const toQuantity = (value) => config.mode === "PERCENT" ? total * value / 100 : value;
  const epsilon = Math.max(1e-8, Math.abs(total) * 1e-10);
  let vested = 0;
  const tranches = [];
  const addTranche = (monthOffset, requested) => {
    const quantity = Math.min(requested, total - vested);
    if (quantity <= epsilon) return;
    vested = Math.min(total, vested + quantity);
    tranches.push({
      sequence: tranches.length + 1,
      vest_date: addCalendarMonths(config.vesting_start_date, monthOffset),
      quantity: Number(quantity.toFixed(8)),
      cumulative_quantity: Number(vested.toFixed(8)),
      cumulative_percent: Number((vested / total * 100).toFixed(6)),
    });
  };
  addTranche(cliffMonths, toQuantity(cliffValue));
  if (vested < total - epsilon) {
    if (!(installmentValue > 0)) throw new Error("Recurring amount must be greater than zero");
    if (config.mode === "PERCENT" && installmentValue > 100) throw new Error("Recurring percentage cannot exceed 100%");
    for (let offset = cliffMonths + interval; vested < total - epsilon && offset <= duration; offset += interval) {
      addTranche(offset, toQuantity(installmentValue));
    }
  }
  if (vested < total - epsilon) {
    throw new Error(`${fmt(total - vested, 4)} options remain unvested by month ${duration}`);
  }
  return tranches;
}

function renderVestingSchedulePreview() {
  const preview = $("vestingSchedulePreview");
  if (!preview) return;
  const isSchedule = valueOf("securityVestingStyle") === "SCHEDULE";
  const isEmployeeGrantAdd = selectedTransactionInstrumentType() === "EMPLOYEE_STOCK_OPTION" && valueOf("securityAction") === "ADD";
  $("vestingScheduleFields").hidden = !isSchedule;
  $("securityVestDateField").hidden = !isEmployeeGrantAdd || isSchedule;
  const mode = valueOf("securityVestingMode") || "PERCENT";
  $("securityVestingCliffValueLabel").textContent = mode === "PERCENT" ? "Cliff Amount (%)" : "Cliff Amount (options)";
  $("securityVestingInstallmentValueLabel").textContent = mode === "PERCENT" ? "Each Installment (%)" : "Each Installment (options)";
  if (!isSchedule) {
    preview.classList.remove("error");
    preview.innerHTML = '<span>Choose the single vest date above.</span>';
    return;
  }
  try {
    const tranches = buildVestingPreview(vestingScheduleFromForm());
    const vested = tranches.filter((tranche) => tranche.vest_date <= todayString()).reduce((total, tranche) => total + tranche.quantity, 0);
    preview.classList.remove("error");
    preview.innerHTML = `
      <div class="vesting-preview-summary"><b>${tranches.length} vesting dates</b><span>${fmt(vested, 4)} vested as of ${esc(formatDate(todayString()))}</span></div>
      <div class="vesting-preview-tranches">
        ${tranches.map((tranche) => `<span class="vesting-tranche-chip ${tranche.vest_date <= todayString() ? "vested" : "future"}" title="Cumulative ${fmt(tranche.cumulative_percent, 4)}%">${esc(formatDate(tranche.vest_date))} · ${fmt(tranche.quantity, 4)}</span>`).join("")}
      </div>`;
  } catch (error) {
    preview.classList.add("error");
    preview.innerHTML = `<span>${esc(error.message)}</span>`;
  }
}

function toggleTransactionCompFields() {
  const type = selectedTransactionInstrumentType();
  const isRsu = type === "RSU";
  const isEmployeeOption = type === "EMPLOYEE_STOCK_OPTION";
  const isEmployeeGrantAdd = isEmployeeOption && valueOf("securityAction") === "ADD";
  const isOptionGrant = type === "STOCK_OPTION" || isEmployeeOption;
  const isEquityComp = isRsu || isOptionGrant;
  document.querySelectorAll("[data-equity-comp-field]").forEach((node) => { node.hidden = !isEquityComp; });
  document.querySelectorAll("[data-option-grant-field]").forEach((node) => { node.hidden = !isOptionGrant; });
  document.querySelectorAll("[data-employee-option-derived-field]").forEach((node) => {
    node.hidden = node.hidden || isEmployeeOption || employeeOptionsWorkflowActive();
  });
  document.querySelectorAll("[data-employee-option-transaction-field]").forEach((node) => { node.hidden = !isEmployeeGrantAdd; });
  $("securityPriceField").hidden = isEquityComp || employeeOptionsWorkflowActive();
  $("securityStrikePrice").required = isOptionGrant;
  $("securityPrice").placeholder = "Price";
  $("securityPurchasePrice").placeholder = isOptionGrant ? "Exercise/purchase price" : "Purchase price (optional)";
  if (isEquityComp && valueOf("securityAction") === "BUY") $("securityAction").value = "ADD";
  if (isEquityComp) $("securityPrice").value = "";
  if (!isEquityComp) {
    ["securityVestDate", "securityPurchasePrice", "securityStrikePrice"].forEach((id) => { $(id).value = ""; });
  }
  if (isEmployeeOption) renderVestingSchedulePreview();
}

function refreshManualSecuritySelects() {
  const transactionInstruments = employeeOptionsWorkflowActive()
    ? state.manualSecurities.filter((item) => item.instrument_type === "EMPLOYEE_STOCK_OPTION")
    : state.manualSecurities;
  const options = `<option value="">${employeeOptionsWorkflowActive() ? "Choose a saved employee option grant" : "Free symbol / not defined"}</option>` + transactionInstruments
    .map((item) => `<option value="${esc(item.id)}">${esc(instrumentLabel(item))}</option>`)
    .join("");
  const securitySelect = $("securityKnownInstrument");
  if (securitySelect) {
    const current = securitySelect.value;
    securitySelect.innerHTML = options;
    if ([...securitySelect.options].some((option) => option.value === current)) securitySelect.value = current;
  }
  const priceSelect = $("priceKnownInstrument");
  if (priceSelect) {
    const current = priceSelect.value;
    priceSelect.innerHTML = '<option value="">Free symbol / not defined</option>' + state.manualSecurities
      .map((item) => `<option value="${esc(item.id)}">${esc(instrumentLabel(item))}</option>`)
      .join("");
    if ([...priceSelect.options].some((option) => option.value === current)) priceSelect.value = current;
  }
  refreshMarketOptions();
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
    if (item.strike_price) $("securityStrikePrice").value = item.strike_price;
    if (item.instrument_type === "EMPLOYEE_STOCK_OPTION") {
      $("securityAction").value = "ADD";
      setDateField("securityDate", item.grant_date || todayString());
      setDateField("securityVestingStartDate", item.vesting_start_date || item.grant_date || "");
      $("securityVestingStyle").value = "SCHEDULE";
    }
    toggleTransactionCompFields();
  }
}

function setSecurityEditMode(tx = null) {
  state.editingTransactionId = tx?.id || "";
  const saveButton = $("saveSecurity");
  const cancelButton = $("cancelSecurityEdit");
  if (saveButton) saveButton.textContent = tx
    ? (employeeOptionsWorkflowActive() ? "Update employee option grant" : "Update transaction")
    : (employeeOptionsWorkflowActive() ? "Save employee option grant" : "Save transaction");
  if (cancelButton) cancelButton.hidden = !tx;
  updateEmployeeOptionsAccountNotice();
}

function clearSecurityForm() {
  ["securitySymbol", "securityMarket", "securityQuantity", "securityPrice", "securityVestDate", "securityPurchasePrice", "securityStrikePrice", "securityVestingStartDate", "securityComments"].forEach((id) => { $(id).value = ""; });
  $("securityAllowManual").checked = false;
  $("securityKnownInstrument").value = "";
  $("securityVestingStyle").value = "SCHEDULE";
  $("securityVestingMode").value = "PERCENT";
  $("securityVestingDuration").value = "48";
  $("securityVestingCliffMonths").value = "12";
  $("securityVestingCliffValue").value = "25";
  $("securityVestingInterval").value = "3";
  $("securityVestingInstallmentValue").value = "6.25";
  setSecurityEditMode(null);
  toggleTransactionCompFields();
}

function editSecurityTransaction(transactionId) {
  const tx = state.localTransactions.find((item) => item.id === transactionId);
  if (!tx) return;
  $("securityAccount").value = tx.account_db_id || "";
  $("securityKnownInstrument").value = tx.security_id || state.manualSecurities.find((item) => item.symbol === tx.symbol && item.stock_market === tx.stock_market)?.id || "";
  $("securityAction").value = tx.action || "BUY";
  $("securitySymbol").value = tx.symbol || "";
  $("securityMarket").value = tx.stock_market || "";
  $("securityAssetClass").value = tx.asset_class || "EQUITY";
  $("securityQuantity").value = tx.quantity || "";
  $("securityPrice").value = tx.price_input || "";
  setDateField("securityDate", tx.trade_date || "");
  setDateField("securityVestDate", tx.vest_date || "");
  const schedule = tx.vesting_schedule || {};
  $("securityVestingStyle").value = schedule.enabled ? "SCHEDULE" : "SINGLE";
  setDateField("securityVestingStartDate", schedule.vesting_start_date || tx.vesting_start_date || tx.grant_date || "");
  if (schedule.enabled) {
    $("securityVestingMode").value = schedule.mode || "PERCENT";
    $("securityVestingDuration").value = schedule.duration_months ?? 48;
    $("securityVestingCliffMonths").value = schedule.cliff_months ?? 12;
    $("securityVestingCliffValue").value = schedule.cliff_value ?? 25;
    $("securityVestingInterval").value = schedule.interval_months ?? 3;
    $("securityVestingInstallmentValue").value = schedule.installment_value ?? 6.25;
  }
  $("securityPurchasePrice").value = tx.purchase_price || "";
  $("securityStrikePrice").value = tx.strike_price || "";
  $("securityComments").value = tx.comments || "";
  $("securityAllowManual").checked = true;
  setSecurityEditMode(tx);
  toggleTransactionCompFields();
  $("securityStatus").textContent = `Editing ${tx.action} ${tx.symbol}`;
}

function fillPriceFormFromFocus() {
  const focus = state.priceFocus;
  if (!focus) return;
  $("priceSymbol").value = cleanSecuritySymbol(focus.symbol);
  $("priceMarket").value = focus.stock_market || "MANUAL";
  $("priceAssetClass").value = focus.asset_class || "EQUITY";
  $("priceLocation").value = focus.location || "USA";
  $("priceCurrency").value = focus.currency || "USD";
  setDateField("priceDate", todayString());
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

function transactionMatchesPosition(tx, detail) {
  return transactionMatchesSecurity(tx, { symbol: detail.symbol, market_key: detail.market })
    && (!detail.accountId || String(tx.account_db_id || "") === String(detail.accountId));
}

function positionTransactionDisplayAction(tx) {
  const importedAction = String(tx?.comments || "").match(/^Imported source (BUY|SELL|SHORT|ADD|REMOVE)\b/i)?.[1];
  return String(importedAction || tx?.action || "").toUpperCase();
}

function positionTransactionEditingRow() {
  return state.localTransactions.find((tx) => tx.id === state.editingPositionTransactionId) || null;
}

function positionTransactionAvailableQuantity(action = valueOf("positionTransactionAction")) {
  const detail = state.positionTransactionsDetail;
  if (!detail) return 0;
  if (positionTransactionEditingRow()) return Infinity;
  let current = Number(detail.quantity || 0);
  if (action === "SELL") return Math.max(0, current);
  if (action === "BUY" && current < 0) return Math.abs(current);
  return Infinity;
}

function syncPositionTransactionLimit() {
  const input = $("positionTransactionQuantity");
  const limit = $("positionTransactionLimit");
  const detail = state.positionTransactionsDetail;
  if (!input || !limit || !detail) return;
  const action = valueOf("positionTransactionAction");
  const current = Number(detail.quantity || 0);
  const available = positionTransactionAvailableQuantity(action);
  input.removeAttribute("max");
  if (Number.isFinite(available)) input.max = String(available);
  if (state.editingPositionTransactionId) {
    limit.textContent = "The full transaction history will be checked";
  } else if (action === "SELL") {
    limit.textContent = available > 0 ? `Available to sell: ${fmt(available, 4)} units` : "No long units available to sell";
  } else if (action === "BUY" && current < 0) {
    limit.textContent = `Short cover limit: ${fmt(available, 4)} units`;
  } else if (action === "SHORT" && current > 0 && !state.editingPositionTransactionId) {
    limit.textContent = "Sell the long position before opening a short";
  } else {
    limit.textContent = current < 0 ? `${fmt(Math.abs(current), 4)} units short` : `${fmt(current, 4)} units held`;
  }
  if ($("positionTransactionAction").disabled) limit.textContent = `${limit.textContent} · Imported action stays unchanged`;
}

function clearPositionTransactionForm(message = "") {
  state.editingPositionTransactionId = "";
  $("positionTransactionFormTitle").textContent = "Add transaction";
  $("positionTransactionAction").disabled = false;
  $("positionTransactionAction").value = "BUY";
  $("positionTransactionQuantity").value = "";
  $("positionTransactionPrice").value = "";
  $("positionTransactionComments").value = "";
  setDateField("positionTransactionDate", todayString());
  $("savePositionTransaction").textContent = "Save";
  $("cancelPositionTransactionEdit").hidden = true;
  $("positionTransactionStatus").textContent = message;
  syncPositionTransactionLimit();
}

function editPositionTransaction(transactionId) {
  const tx = state.localTransactions.find((item) => item.id === transactionId);
  if (!tx) return;
  state.editingPositionTransactionId = tx.id;
  const actualAction = String(tx.action || "").toUpperCase();
  const displayAction = positionTransactionDisplayAction(tx);
  $("positionTransactionFormTitle").textContent = `Edit ${displayAction.toLowerCase()} transaction`;
  $("positionTransactionAction").value = ["BUY", "SELL", "SHORT"].includes(displayAction) ? displayAction : "BUY";
  $("positionTransactionAction").disabled = !["BUY", "SELL", "SHORT"].includes(actualAction);
  $("positionTransactionQuantity").value = tx.quantity || "";
  $("positionTransactionPrice").value = tx.price_input ?? tx.price ?? "";
  setDateField("positionTransactionDate", tx.trade_date || "");
  $("positionTransactionComments").value = tx.comments || "";
  $("savePositionTransaction").textContent = "Update";
  $("cancelPositionTransactionEdit").hidden = false;
  $("positionTransactionStatus").textContent = `Editing ${displayAction} from ${formatDate(tx.trade_date)}`;
  syncPositionTransactionLimit();
  $("positionTransactionQuantity").focus();
}

function validatePositionTransactionForm() {
  const action = valueOf("positionTransactionAction");
  const quantity = Number(valueOf("positionTransactionQuantity"));
  const price = Number(valueOf("positionTransactionPrice") || 0);
  const tradeDate = dateValue("positionTransactionDate");
  if (!Number.isFinite(quantity) || quantity <= 0) throw new Error("Units must be greater than zero");
  if (!Number.isFinite(price) || price < 0) throw new Error("Unit price cannot be negative");
  if (!tradeDate) throw new Error(`Date must use ${DATE_PLACEHOLDER}`);
  const available = positionTransactionAvailableQuantity(action);
  if (action === "SELL" && available <= 0) throw new Error("There are no long units available to sell");
  if (Number.isFinite(available) && quantity > available + 1e-9) {
    throw new Error(action === "SELL" ? `You can sell at most ${fmt(available, 4)} units` : `You can buy at most ${fmt(available, 4)} units to close this short`);
  }
  const current = Number(state.positionTransactionsDetail?.quantity || 0);
  if (action === "SHORT" && current > 0 && !state.editingPositionTransactionId) {
    throw new Error("Sell the long position before opening a short");
  }
  return { action, quantity, price, tradeDate };
}

function refreshPositionTransactionDetail(positionQuantity) {
  const detail = state.positionTransactionsDetail;
  if (!detail) return;
  const refreshed = state.items.find((item) => {
    const holding = item.holding || {};
    return securityMatches(item, detail.symbol, detail.market)
      && (!detail.accountId || String(holding.account_id || "") === String(detail.accountId));
  });
  const holding = refreshed?.holding || {};
  detail.quantity = Number(holding.quantity ?? positionQuantity ?? detail.quantity ?? 0);
  detail.average = Math.abs(Number(holding.quantity || 0)) > 0
    ? Math.abs(Number(holding.cost_basis || 0) / Number(holding.quantity || 0))
    : 0;
}

async function savePositionTransaction() {
  const detail = state.positionTransactionsDetail;
  if (!detail) return;
  const values = validatePositionTransactionForm();
  const editing = positionTransactionEditingRow();
  const action = editing && !["BUY", "SELL", "SHORT"].includes(String(editing.action || "").toUpperCase())
    ? editing.action
    : values.action;
  const payload = {
    account_db_id: detail.accountId,
    action,
    symbol: detail.symbol,
    stock_market: detail.market,
    asset_class: detail.assetClass || "EQUITY",
    quantity: values.quantity,
    price_input: values.price,
    trade_date: values.tradeDate,
    currency: detail.currency,
    location: detail.location || "",
    allow_manual: true,
    comments: valueOf("positionTransactionComments"),
  };
  $("positionTransactionStatus").textContent = editing ? "Updating transaction…" : "Saving transaction…";
  const path = editing ? `/api/local/securities/${encodeURIComponent(editing.id)}` : "/api/local/securities";
  const result = await api(path, { method: editing ? "PUT" : "POST", body: JSON.stringify(payload) });
  await loadPortfolio({ refresh: true });
  if (result.position_closed) {
    closeModal($("positionTransactionsModal"));
    state.positionTransactionsDetail = null;
    clearPositionTransactionForm();
    $("positionClosedTitle").textContent = `${detail.symbol} position closed`;
    $("positionClosedMessage").textContent = `${detail.symbol} reached 0 units and was removed from the portfolio.`;
    openModal("positionClosedModal");
    return;
  }
  refreshPositionTransactionDetail(result.position_quantity);
  clearPositionTransactionForm(editing ? "Transaction updated" : "Transaction saved");
  renderPositionTransactionHistory();
}

function renderPositionTransactionHistory() {
  const detail = state.positionTransactionsDetail;
  if (!detail) return;
  const positionActions = new Set(["BUY", "SELL", "ADD", "REMOVE", "SHORT"]);
  const transactions = state.localTransactions
    .filter((tx) => positionActions.has(String(tx.action || "").toUpperCase()))
    .filter((tx) => transactionMatchesPosition(tx, detail))
    .sort((a, b) => String(b.trade_date || "").localeCompare(String(a.trade_date || "")));
  $("positionTransactionsTitle").textContent = `${detail.symbol} buy / sell history`;
  $("positionTransactionsSubtitle").textContent = [detail.account, `${fmt(detail.quantity, 3)} units`, detail.average ? `Avg buy ${money(detail.average, detail.currency, 2)}` : ""].filter(Boolean).join(" · ");
  $("positionTransactionsRows").innerHTML = transactions.length ? transactions.map((tx) => {
    const displayAction = positionTransactionDisplayAction(tx);
    const sourceLabel = String(tx.source || "").toLowerCase() === "ghostfolio_import" ? "Imported" : cleanSourceLabel(tx.source || "Manual");
    const amount = Math.abs(Number(tx.quantity || 0) * Number(tx.price || 0));
    const actionClass = ["BUY", "ADD"].includes(displayAction) ? "positive" : "negative";
    return `<tr>
      <td>${esc(formatDate(tx.trade_date))}</td>
      <td><span class="transaction-action ${actionClass}">${esc(displayAction)}</span></td>
      <td>${fmt(tx.quantity, 4)}</td>
      <td>${money(tx.price, tx.currency || detail.currency, 4)}</td>
      <td>${money(amount, tx.currency || detail.currency, 2)}</td>
      <td>${esc(sourceLabel)}</td>
      <td>${esc(cleanSourceLabel(tx.comments || "")) || "—"}</td>
      <td><button class="secondary compact-button" type="button" data-edit-position-transaction="${esc(tx.id)}">Edit</button></td>
    </tr>`;
  }).join("") : '<tr><td colspan="8" class="empty-cell">No buy or sell transactions found for this position</td></tr>';
}

async function openPositionTransactionHistory(dataset) {
  state.positionTransactionsDetail = {
    symbol: cleanSecuritySymbol(dataset.positionHistorySymbol),
    market: String(dataset.positionHistoryMarket || "MANUAL").toUpperCase(),
    accountId: dataset.positionHistoryAccountId || "",
    account: cleanSourceLabel(dataset.positionHistoryAccount || ""),
    currency: dataset.positionHistoryCurrency || state.baseCurrency,
    quantity: Number(dataset.positionHistoryQuantity || 0),
    average: Number(dataset.positionHistoryAverage || 0),
    assetClass: dataset.positionHistoryAsset || "EQUITY",
    location: dataset.positionHistoryLocation || "",
  };
  openModal("positionTransactionsModal");
  clearPositionTransactionForm();
  $("positionTransactionsRows").innerHTML = '<tr><td colspan="8" class="empty-cell">Loading transaction history…</td></tr>';
  const data = await api("/api/local/securities");
  state.localTransactions = data.items || [];
  renderPositionTransactionHistory();
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
  setDateField("securityChartStartDate", state.securityChartStartDate);
  setDateField("detailPriceDate", todayString());
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
  if (state.securityChartLevelPeriods?.length) params.set("level_periods", state.securityChartLevelPeriods.join(","));
  if (state.securityChartStartDate) params.set("date_from", state.securityChartStartDate);
  const [transactions, prices, history] = await Promise.all([
    api("/api/local/securities"),
    api("/api/local/prices"),
    api(`/api/security/history?${params}`),
  ]);
  state.localTransactions = transactions.items || [];
  state.localPrices = prices.items || [];
  state.securityHistory = history.points || [];
  state.securityHistoryMeta = history;
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
    ["Average buy price", Math.abs(Number(h.quantity || 0)) ? money(Math.abs(Number(h.cost_basis || 0) / Number(h.quantity || 0)), h.currency || detail.currency, 2) : "Not available"],
    ["Holding profit (open)", signedMoney(h.unrealized_profit || 0, h.currency || detail.currency), "Profit/loss on the quantity still held. It changes with the current price."],
    ["Closed profit", signedMoney(h.realized_profit || 0, h.currency || detail.currency), "Profit/loss already recorded by sell, cover, dividend, interest, or fee transactions."],
    ["Account", cleanSourceLabel(h.account || "")],
  ].map(([label, value, title]) => `<div class="security-kpi" title="${esc(title || "")}"><span>${esc(label)}</span><b>${esc(value || "∅")}</b></div>`).join("");
  const txs = state.localTransactions.filter((tx) => transactionMatchesSecurity(tx, detail));
  $("securityDetailTransactions").innerHTML = txs.length ? txs.map((tx) => `
    <div class="stack-item management-item">
      <b>${esc(tx.action)} ${fmt(tx.quantity, 4)}</b>
    <span>${esc(formatDate(tx.trade_date))} · input ${fmt(tx.price_input, 4)} · ${esc(tx.currency)} ${fmt(tx.price, 4)}</span>
      <button class="secondary compact-button" type="button" data-edit-security="${esc(tx.id)}">Edit</button>
      <button class="secondary compact-button" type="button" data-delete-security="${esc(tx.id)}">Delete</button>
      <div class="sub">${transactionCashImpact(tx) ? `Cash ${signedMoney(transactionCashImpact(tx), tx.currency)}` : "No cash movement"} · ${esc(cleanSourceLabel(tx.management_company || ""))} ${esc(cleanSourceLabel(tx.account_id || ""))}${tx.comments ? ` · ${esc(cleanSourceLabel(tx.comments))}` : ""}</div>
    </div>
  `).join("") : '<div class="empty">No transactions for this security</div>';
  const prices = state.localPrices.filter((price) => priceMatchesSecurity(price, detail));
  $("securityDetailPrices").innerHTML = prices.length ? prices.map((price) => `
    <div class="stack-item management-item">
      <b>${esc(formatDate(price.price_date))}</b>
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
  document.querySelectorAll("[data-security-chart-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.securityChartMode === state.securityChartMode);
  });
  document.querySelectorAll(".security-sr-toggle").forEach((input) => {
    input.checked = (state.securityChartLevelPeriods || []).includes(input.value);
  });
  document.querySelectorAll(".security-ma-toggle").forEach((input) => {
    input.checked = state.securityChartMaWindows.includes(input.value);
  });
  setDateField("securityChartStartDate", clampedHistoryDate(state.securityChartStartDate));
  const frame = $("securityDetailChart");
  const points = (state.securityHistory || [])
    .map((point) => {
      const close = Number(point.adjusted_close || point.close || point.price || 0);
      return {
        date: point.date,
        price: close,
        open: Number(point.open || close),
        high: Number(point.high || close),
        low: Number(point.low || close),
        close: Number(point.close || close),
        adjustedClose: close,
        volume: Number(point.volume || 0),
      };
    })
    .filter((point) => point.date && Number.isFinite(point.price) && point.price > 0);
  if (!points.length) {
    frame.innerHTML = '<div class="empty">No price history for this period</div>';
    return;
  }
  const meta = state.securityHistoryMeta || {};
  const showCandles = state.securityChartMode === "candles" && meta.has_candles;
  const hasVolume = points.some((point) => point.volume > 0);
  const width = 820;
  const height = hasVolume ? 340 : 270;
  const padTop = 24;
  const padRight = 36;
  const padBottom = 36;
  const padLeft = 58;
  const volumeGap = hasVolume ? 20 : 0;
  const volumeHeight = hasVolume ? 58 : 0;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom - volumeGap - volumeHeight;
  const selectedMaWindows = state.securityChartMaWindows || [];
  const maSeries = Object.fromEntries(selectedMaWindows.map((window) => [window, movingAverageSeries(points, Number(window))]));
  const selectedLevelPeriods = state.securityChartLevelPeriods || [];
  const chartLevels = selectedLevelPeriods.flatMap((period) => supportResistanceChartLevels(meta.support_resistance || {}, period, points));
  const levelPrices = chartLevels.map((level) => level.price).filter(Number.isFinite);
  const priceValues = points.flatMap((point) => [point.high, point.low, point.price])
    .concat(Object.values(maSeries).flat().map((point) => point.value))
    .concat(levelPrices);
  const min = Math.min(...priceValues);
  const max = Math.max(...priceValues);
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
  const candleWidth = Math.max(3, Math.min(11, plotWidth / Math.max(points.length, 1) * 0.62));
  const volumeBase = height - padBottom;
  const volumeTop = volumeBase - volumeHeight;
  const maxVolume = Math.max(...points.map((point) => point.volume), 1);
  const maColors = { 7: "#ffae18", 10: "#9b4dff", 15: "#5f67ff", 30: "#f7f9ff" };
  const maPaths = Object.entries(maSeries)
    .filter(([, series]) => series.length)
    .map(([window, series]) => {
      const path = series.map((point, index) => `${index ? "L" : "M"} ${x(point.index).toFixed(1)} ${y(point.value).toFixed(1)}`).join(" ");
      return `<path d="${path}" fill="none" stroke="${maColors[window] || "#aab4cf"}" stroke-width="1.8" opacity="0.9" />`;
    }).join("");
  const levelMarkers = chartLevels.map((level, index) => {
    const px = x(level.index);
    const py = y(level.price);
    const markerX = Math.max(padLeft + 2, Math.min(width - padRight - 48, px + (level.kind === "support" ? 7 : -42)));
    const markerY = Math.max(padTop + 2, Math.min(padTop + plotHeight - 14, py - 7 + (index % 3) * 13));
    const color = level.kind === "support" ? "#2dde98" : "#ff5b73";
    return `
      <g>
        <title>${esc(level.label)} ${esc(level.kind)} ${esc(fmt(level.price, 4))}</title>
        <rect x="${markerX.toFixed(1)}" y="${markerY.toFixed(1)}" width="9" height="9" rx="1.5" fill="${color}" />
        <text x="${(markerX + 13).toFixed(1)}" y="${(markerY + 8.5).toFixed(1)}" fill="${color}" font-size="11" font-weight="900">${esc(level.label)}</text>
      </g>
    `;
  }).join("");
  const candles = points.map((point, index) => {
    const px = x(index);
    const up = point.close >= point.open;
    const color = up ? "#2dde98" : "#ff5b73";
    const bodyTop = Math.min(y(point.open), y(point.close));
    const bodyHeight = Math.max(Math.abs(y(point.close) - y(point.open)), 2);
    return `
      <line x1="${px.toFixed(1)}" y1="${y(point.high).toFixed(1)}" x2="${px.toFixed(1)}" y2="${y(point.low).toFixed(1)}" stroke="${color}" stroke-width="1.4" />
      <rect x="${(px - candleWidth / 2).toFixed(1)}" y="${bodyTop.toFixed(1)}" width="${candleWidth.toFixed(1)}" height="${bodyHeight.toFixed(1)}" rx="1.5" fill="${up ? "rgba(45,222,152,0.34)" : "rgba(255,91,115,0.34)"}" stroke="${color}" stroke-width="1" />
    `;
  }).join("");
  const volumeBars = hasVolume ? points.map((point, index) => {
    const px = x(index);
    const previous = points[index - 1] || point;
    const up = point.close >= previous.close;
    const barHeight = Math.max(1, (point.volume / maxVolume) * volumeHeight);
    const barWidth = Math.max(2, Math.min(9, plotWidth / Math.max(points.length, 1) * 0.72));
    return `<rect x="${(px - barWidth / 2).toFixed(1)}" y="${(volumeBase - barHeight).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="1.5" fill="${up ? "#2dde98" : "#ff5b73"}" opacity="0.72" />`;
  }).join("") : "";
  const legend = [
    showCandles ? '<span><i style="background:#2dde98"></i>Up candle</span><span><i style="background:#ff5b73"></i>Down candle</span>' : '<span><i style="background:#21a7ff"></i>Adjusted close</span>',
    ...selectedMaWindows.map((window) => `<span><i style="background:${maColors[window] || "#aab4cf"}"></i>MA ${esc(window)}</span>`),
    ...selectedLevelPeriods.flatMap((period) => [
      `<span><i style="background:#2dde98"></i>${esc(levelPeriodLabel(period))} support</span>`,
      `<span><i style="background:#ff5b73"></i>${esc(levelPeriodLabel(period))} resistance</span>`,
    ]),
    hasVolume ? '<span><i style="background:#2dde98"></i>Volume up</span><span><i style="background:#ff5b73"></i>Volume down</span>' : "",
  ].filter(Boolean).join("");
  const volumeText = hasVolume
    ? `Volume ${fmt(meta.volume?.latest || last.volume, 0)} · Avg 20D ${meta.volume?.average_20d ? fmt(meta.volume.average_20d, 0) : "N/A"} · Avg 90D ${meta.volume?.average_90d ? fmt(meta.volume.average_90d, 0) : "N/A"}`
    : "No volume data from provider for this period";
  const chartNotice = state.securityChartMode === "candles" && !meta.has_candles ? '<div class="chart-notice">Candles need OHLC data. Showing line chart for this source.</div>' : "";
  frame.innerHTML = `
    ${chartNotice}
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Security price history">
      ${[max, mid, min].map((value) => `<line x1="${padLeft}" y1="${y(value).toFixed(1)}" x2="${width - padRight}" y2="${y(value).toFixed(1)}" stroke="#1e2835" stroke-dasharray="5 7" />`).join("")}
      <line x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${height - padBottom}" stroke="#344052" />
      <line x1="${padLeft}" y1="${(padTop + plotHeight).toFixed(1)}" x2="${width - padRight}" y2="${(padTop + plotHeight).toFixed(1)}" stroke="#344052" />
      ${hasVolume ? `<line x1="${padLeft}" y1="${volumeTop.toFixed(1)}" x2="${width - padRight}" y2="${volumeTop.toFixed(1)}" stroke="#26303d" stroke-dasharray="5 7" /><line x1="${padLeft}" y1="${volumeBase.toFixed(1)}" x2="${width - padRight}" y2="${volumeBase.toFixed(1)}" stroke="#344052" />${volumeBars}<text x="${padLeft}" y="${(volumeTop - 6).toFixed(1)}" fill="#9cacc2" font-size="11" font-weight="800">Volume</text>` : ""}
      <line x1="${middleX.toFixed(1)}" y1="${height - padBottom}" x2="${middleX.toFixed(1)}" y2="${(height - padBottom + 5).toFixed(1)}" stroke="#344052" />
      ${[max, mid, min].map((value) => `<text x="${padLeft - 8}" y="${(y(value) + 4).toFixed(1)}" fill="#9cacc2" font-size="11" font-weight="700" text-anchor="end">${esc(fmt(value, 4))}</text>`).join("")}
      ${showCandles ? candles : `<path d="${d}" fill="none" stroke="#21a7ff" stroke-width="3" />`}
      ${maPaths}
      ${levelMarkers}
      <g data-security-hover-marker hidden>
        <line data-security-hover-line x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${height - padBottom}" stroke="#8fb7e8" stroke-width="1" stroke-dasharray="4 5" opacity="0.75" />
        <circle data-security-hover-point cx="${padLeft}" cy="${height - padBottom}" r="4.5" fill="#f7f9ff" stroke="#21a7ff" stroke-width="2" />
      </g>
      <circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="4" fill="#ffb21a" />
      <rect x="${calloutX.toFixed(1)}" y="${calloutY.toFixed(1)}" width="${calloutWidth}" height="${calloutHeight}" rx="7" fill="#0b1018" stroke="#2d3543" opacity="0.96" />
      <text x="${(calloutX + calloutWidth - 9).toFixed(1)}" y="${(calloutY + 15).toFixed(1)}" fill="#dce7ff" font-size="13" font-weight="800" text-anchor="end">${esc(fmt(last.price, 4))}</text>
      <text x="${(calloutX + calloutWidth - 9).toFixed(1)}" y="${(calloutY + 30).toFixed(1)}" fill="${calloutTextColor}" font-size="11" font-weight="800" text-anchor="end">${esc(signedMoney(change, state.securityDetail?.currency || "USD"))} · ${esc(changePct.toFixed(2))}%</text>
      <text x="${padLeft}" y="${height - 10}" fill="#9cacc2" font-size="11" font-weight="700">${esc(formatDate(first.date))}</text>
      <text x="${middleX.toFixed(1)}" y="${height - 10}" fill="#9cacc2" font-size="11" font-weight="700" text-anchor="middle">${esc(formatDate(middle.date))}</text>
      <text x="${width - padRight}" y="${height - 10}" fill="#9cacc2" font-size="11" font-weight="700" text-anchor="end">${esc(formatDate(last.date))}</text>
      <rect data-security-chart-hitbox x="${padLeft}" y="${padTop}" width="${plotWidth}" height="${height - padTop - padBottom}" fill="transparent" />
    </svg>
    <div class="chart-hover-tip" hidden></div>
    <div class="security-chart-footer">
      <div class="chart-legend">${legend}</div>
      <div class="sub ${cls}">${points.length} price points · ${esc(volumeText)}</div>
    </div>
  `;
  attachSecurityChartHover(frame, points, { width, height, padLeft, padRight, padTop, padBottom, plotWidth, plotHeight, min, max });
}

function levelPeriodLabel(period) {
  return SUPPORT_RESISTANCE_PERIODS.find((item) => item.key === period)?.label || String(period || "").toUpperCase();
}

function supportResistanceChartLevels(levels, period, points) {
  const sr = levels?.[period] || {};
  if (sr.state !== "ok") return [];
  return ["support", "resistance"].map((kind) => {
    const level = sr[kind] || {};
    const price = Number(level.price);
    if (!Number.isFinite(price) || price <= 0) return null;
    const dateIndex = points.findIndex((point) => point.date === level.date);
    const priceIndex = points.reduce((best, point, index) => {
      const diff = Math.abs(point.price - price);
      return diff < best.diff ? { index, diff } : best;
    }, { index: Math.max(points.length - 1, 0), diff: Number.POSITIVE_INFINITY }).index;
    return {
      kind,
      period,
      label: levelPeriodLabel(period),
      price,
      index: dateIndex >= 0 ? dateIndex : priceIndex,
    };
  }).filter(Boolean);
}

function movingAverageSeries(points, window) {
  if (!window || points.length < window) return [];
  return points.map((point, index) => {
    if (index + 1 < window) return null;
    const slice = points.slice(index + 1 - window, index + 1);
    return { index, value: slice.reduce((total, item) => total + item.price, 0) / window };
  }).filter(Boolean);
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
    tip.innerHTML = `
      <b>${esc(formatDate(selected.date))}</b>
      <span>Close ${esc(money(selected.price, state.securityDetail?.currency || "USD", 4))}</span>
      <span>Open ${esc(fmt(selected.open, 4))} · High ${esc(fmt(selected.high, 4))} · Low ${esc(fmt(selected.low, 4))}</span>
      <span>Volume ${esc(fmt(selected.volume || 0, 0))}</span>
    `;
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
    price_date: dateValue("detailPriceDate") || todayString(),
    comments: valueOf("detailPriceComments"),
  };
  await api("/api/local/prices", { method: "POST", body: JSON.stringify(payload) });
  $("securityDetailStatus").textContent = "Price history saved";
  $("detailPriceInput").value = "";
  $("detailPriceComments").value = "";
  await loadSecurityDetail();
  await loadPortfolio();
}

function employeeOptionsWorkflowActive() {
  return state.securitiesWorkflow === "employee-options";
}

function setEmployeeOptionGuideStep(step, { complete = false } = {}) {
  if (!employeeOptionsWorkflowActive()) return;
  const normalizedStep = Math.max(1, Math.min(3, Number(step) || 1));
  state.employeeOptionWizardStep = normalizedStep;
  state.employeeOptionWizardMaxStep = complete
    ? 3
    : Math.max(state.employeeOptionWizardMaxStep || 1, normalizedStep);
  document.querySelectorAll("[data-employee-guide-step]").forEach((node) => {
    const nodeStep = Number(node.dataset.employeeGuideStep || 0);
    const active = nodeStep === normalizedStep && !complete;
    node.classList.toggle("active", active);
    node.classList.toggle("complete", nodeStep < normalizedStep || (complete && nodeStep <= normalizedStep));
    node.disabled = nodeStep > state.employeeOptionWizardMaxStep;
    if (active) node.setAttribute("aria-current", "step");
    else node.removeAttribute("aria-current");
  });
  document.querySelectorAll("[data-employee-wizard-panel]").forEach((panel) => {
    panel.hidden = Number(panel.dataset.employeeWizardPanel || 0) !== normalizedStep;
  });
}

function toggleEmployeeWizardCompanyFields() {
  const isPublic = valueOf("employeeWizardCompanyStatus") === "PUBLIC";
  document.querySelectorAll("[data-employee-wizard-public]").forEach((node) => { node.hidden = !isPublic; });
  document.querySelectorAll("[data-employee-wizard-private]").forEach((node) => { node.hidden = isPublic; });
}

function syncEmployeeWizardIssuerFromCompany() {
  const companyName = valueOf("employeeWizardCompany").toLocaleLowerCase();
  if (!companyName) return;
  const match = state.manualSecurities.find((item) => (
    item.instrument_type === "EMPLOYEE_STOCK_OPTION"
    && String(item.company_name || "").toLocaleLowerCase() === companyName
  ));
  if (!match) return;
  $("employeeWizardCompanyStatus").value = match.listing_status || "PRIVATE";
  setCompanyLocationOptions(match.location || "USA", "employeeWizardLocation");
  setCurrencyOptions("employeeWizardCurrency", EMPLOYEE_OPTION_CURRENCIES);
  $("employeeWizardCurrency").value = EMPLOYEE_OPTION_CURRENCIES.includes(match.currency) ? match.currency : "USD";
  $("employeeWizardPublicSymbol").value = match.public_symbol || "";
  $("employeeWizardPublicMarket").value = match.public_market || "";
  $("employeeWizardShareValue").value = Number(match.manual_share_value || 0) > 0 ? match.manual_share_value : "";
  setDateField("employeeWizardValuationDate", match.valuation_date || "");
  toggleEmployeeWizardCompanyFields();
  $("employeeWizardGrantStatus").textContent = `Using the saved company details for ${match.company_name}. This will still be a separate grant.`;
}

function employeeWizardFirstField(step) {
  return step === 1
    ? $("employeeWizardCompany")
    : step === 2
      ? $("employeeWizardAccount")
      : $("saveEmployeeOptionGrant");
}

function showEmployeeOptionWizard(mode = "create") {
  state.employeeOptionWizardMode = mode;
  $("employeeOptionWizard").hidden = false;
  $("employeeOptionsGuide").hidden = false;
  $("employeeOptionWizardTitle").textContent = mode === "edit" ? "Edit employee option grant" : "Add employee option grant";
  $("employeeOptionWizardHint").textContent = mode === "edit"
    ? "Update the grant terms or vesting rule, then review every date before saving."
    : "You will review every vesting date before anything is saved.";
  $("cancelEmployeeOptionWizard").textContent = mode === "edit" ? "Cancel edit" : "Cancel";
}

function hideEmployeeOptionWizard() {
  state.employeeOptionWizardMode = "browse";
  state.employeeOptionWizardStep = 1;
  state.employeeOptionWizardMaxStep = 1;
  state.editingEmployeeOptionSecurityId = "";
  state.editingEmployeeOptionTransactionId = "";
  $("employeeOptionWizard").hidden = true;
  $("employeeOptionsGuide").hidden = true;
}

function clearEmployeeOptionWizard() {
  [
    "employeeWizardCompany", "employeeWizardGrantId", "employeeWizardGrantDate", "employeeWizardExpiration",
    "employeeWizardStrikePrice", "employeeWizardPublicSymbol", "employeeWizardPublicMarket", "employeeWizardTaxScheme",
    "employeeWizardShareValue", "employeeWizardValuationDate", "employeeWizardRestrictionEnd", "employeeWizardComments",
    "employeeWizardQuantity", "employeeWizardVestingStart", "employeeWizardSingleVestDate",
  ].forEach((id) => { $(id).value = ""; });
  $("employeeWizardCompanyStatus").value = "PRIVATE";
  setCompanyLocationOptions("USA", "employeeWizardLocation");
  setCurrencyOptions("employeeWizardCurrency", EMPLOYEE_OPTION_CURRENCIES);
  $("employeeWizardCurrency").value = "USD";
  $("employeeWizardEarlyExercise").checked = false;
  $("employeeWizardVestingStyle").value = "SCHEDULE";
  $("employeeWizardVestingMode").value = "PERCENT";
  $("employeeWizardFirstMonths").value = "12";
  $("employeeWizardFirstValue").value = "25";
  $("employeeWizardInstallmentValue").value = "6.25";
  $("employeeWizardInterval").value = "3";
  const esopAccount = state.localAccounts.find((account) => String(account.type || "").toUpperCase() === "ESOP");
  $("employeeWizardAccount").value = esopAccount?.id || "";
  ["employeeWizardGrantStatus", "employeeWizardVestingStatus", "employeeOptionWizardStatus"].forEach((id) => { $(id).textContent = ""; });
  const advanced = $("employeeOptionWizard")?.querySelector(".employee-wizard-advanced");
  if (advanced) advanced.open = false;
  toggleEmployeeWizardCompanyFields();
  renderEmployeeWizardVestingPreview();
}

function beginNewEmployeeOptionGrant() {
  state.editingEmployeeOptionSecurityId = "";
  state.editingEmployeeOptionTransactionId = "";
  state.employeeOptionWizardMaxStep = 1;
  clearEmployeeOptionWizard();
  showEmployeeOptionWizard("create");
  setEmployeeOptionGuideStep(1);
  $("employeeOptionListStatus").textContent = "";
  requestAnimationFrame(() => $("employeeWizardCompany")?.focus());
}

function employeeWizardValidationError(statusId, message, fieldId) {
  $(statusId).textContent = message;
  if (fieldId) $(fieldId)?.focus();
  return false;
}

function validateEmployeeWizardGrant() {
  const required = [
    ["employeeWizardCompany", "Enter the company name."],
    ["employeeWizardGrantDate", "Enter the grant date in dd/mm/yyyy format."],
    ["employeeWizardLocation", "Choose the company location."],
    ["employeeWizardCurrency", "Choose the grant currency."],
    ["employeeWizardExpiration", "Enter the expiration date in dd/mm/yyyy format."],
    ["employeeWizardStrikePrice", "Enter a strike price greater than zero."],
  ];
  for (const [fieldId, message] of required) {
    if (!valueOf(fieldId)) return employeeWizardValidationError("employeeWizardGrantStatus", message, fieldId);
  }
  const grantDate = dateValue("employeeWizardGrantDate");
  const expirationDate = dateValue("employeeWizardExpiration");
  if (!grantDate) return employeeWizardValidationError("employeeWizardGrantStatus", "Enter a valid Grant Date in dd/mm/yyyy format.", "employeeWizardGrantDate");
  if (!expirationDate) return employeeWizardValidationError("employeeWizardGrantStatus", "Enter a valid Expiration Date in dd/mm/yyyy format.", "employeeWizardExpiration");
  if (expirationDate <= grantDate) return employeeWizardValidationError("employeeWizardGrantStatus", "Expiration Date must be after the Grant Date.", "employeeWizardExpiration");
  if (!(Number(valueOf("employeeWizardStrikePrice")) > 0)) return employeeWizardValidationError("employeeWizardGrantStatus", "Strike Price must be greater than zero.", "employeeWizardStrikePrice");
  if (!EMPLOYEE_OPTION_CURRENCIES.includes(valueOf("employeeWizardCurrency"))) {
    return employeeWizardValidationError("employeeWizardGrantStatus", "Currency must be ILS, USD, or EUR.", "employeeWizardCurrency");
  }
  if (valueOf("employeeWizardCompanyStatus") === "PUBLIC") {
    if (!valueOf("employeeWizardPublicSymbol")) return employeeWizardValidationError("employeeWizardGrantStatus", "Enter the public company symbol.", "employeeWizardPublicSymbol");
    if (!valueOf("employeeWizardPublicMarket")) return employeeWizardValidationError("employeeWizardGrantStatus", "Enter the public stock market.", "employeeWizardPublicMarket");
  }
  if (Number(valueOf("employeeWizardShareValue") || 0) > 0 && !dateValue("employeeWizardValuationDate")) {
    return employeeWizardValidationError("employeeWizardGrantStatus", "Enter the valuation date for the latest share value.", "employeeWizardValuationDate");
  }
  $("employeeWizardGrantStatus").textContent = "";
  return true;
}

function employeeWizardScheduleData() {
  const total = Number(valueOf("employeeWizardQuantity") || 0);
  const start = dateValue("employeeWizardVestingStart") || dateValue("employeeWizardGrantDate");
  if (!(total > 0)) throw new Error("Enter the total number of options granted");
  if (!start) throw new Error("Enter the Vesting Start Date in dd/mm/yyyy format");
  if (valueOf("employeeWizardVestingStyle") === "SINGLE") {
    const vestDate = dateValue("employeeWizardSingleVestDate");
    if (!vestDate) throw new Error("Enter the Vest Date in dd/mm/yyyy format");
    return {
      style: "SINGLE",
      vestDate,
      schedule: {},
      tranches: [{
        sequence: 1,
        vest_date: vestDate,
        quantity: total,
        cumulative_quantity: total,
        cumulative_percent: 100,
      }],
    };
  }
  const mode = valueOf("employeeWizardVestingMode") || "PERCENT";
  const firstMonths = Number(valueOf("employeeWizardFirstMonths"));
  const firstValue = Number(valueOf("employeeWizardFirstValue"));
  const interval = Number(valueOf("employeeWizardInterval"));
  const installmentValue = Number(valueOf("employeeWizardInstallmentValue"));
  if (!Number.isInteger(firstMonths) || firstMonths < 0 || firstMonths > 600) throw new Error("First vest must be 0–600 whole months after vesting starts");
  if (!Number.isInteger(interval) || interval < 1 || interval > 600) throw new Error("Repeating interval must be 1–600 whole months");
  if (!(firstValue > 0)) throw new Error("Enter the amount that vests first");
  const toQuantity = (value) => mode === "PERCENT" ? total * value / 100 : value;
  const firstQuantity = toQuantity(firstValue);
  if (firstQuantity > total) throw new Error(`The first vest cannot exceed ${fmt(total, 4)} options`);
  const remaining = Math.max(0, total - firstQuantity);
  if (remaining > 0 && !(installmentValue > 0)) throw new Error("Enter the amount that repeats after the first vest");
  const installmentQuantity = toQuantity(installmentValue);
  if (remaining > 0 && !(installmentQuantity > 0)) throw new Error("The repeating vest amount must be greater than zero");
  const recurringCount = remaining > 0 ? Math.ceil(remaining / installmentQuantity) : 0;
  const durationMonths = firstMonths + recurringCount * interval;
  if (durationMonths > 600) throw new Error("This schedule lasts more than 600 months; increase each repeating vest amount");
  const schedule = {
    enabled: true,
    mode,
    vesting_start_date: start,
    duration_months: durationMonths,
    cliff_months: firstMonths,
    cliff_value: firstValue,
    interval_months: interval,
    installment_value: installmentValue,
    total_quantity: total,
  };
  return { style: "SCHEDULE", vestDate: "", schedule, tranches: buildVestingPreview(schedule) };
}

function employeeWizardScheduleSentence(data, total = Number(valueOf("employeeWizardQuantity") || 0)) {
  if (data.style === "SINGLE") return `All ${fmt(total, 4)} options vest on ${formatDate(data.vestDate)}.`;
  const schedule = data.schedule;
  const unit = schedule.mode === "PERCENT" ? "% of the grant" : "options";
  return `First vest after ${schedule.cliff_months} month${schedule.cliff_months === 1 ? "" : "s"}: ${fmt(schedule.cliff_value, 4)} ${unit}. Then ${fmt(schedule.installment_value, 4)} ${unit} every ${schedule.interval_months} month${schedule.interval_months === 1 ? "" : "s"} until fully vested.`;
}

function employeeWizardTrancheTable(tranches) {
  return `
    <div class="employee-vesting-table-wrap">
      <table class="employee-vesting-table">
        <thead><tr><th>Vest</th><th>Date</th><th>Options</th><th>Total Vested</th></tr></thead>
        <tbody>${tranches.map((tranche) => `
          <tr>
            <td>${esc(tranche.sequence)}</td>
            <td>${esc(formatDate(tranche.vest_date))}</td>
            <td>${fmt(tranche.quantity, 4)}</td>
            <td>${fmt(tranche.cumulative_quantity, 4)} <small>(${fmt(tranche.cumulative_percent, 4)}%)</small></td>
          </tr>
        `).join("")}</tbody>
      </table>
    </div>`;
}

function renderEmployeeWizardVestingPreview() {
  const preview = $("employeeWizardVestingPreview");
  if (!preview) return;
  const single = valueOf("employeeWizardVestingStyle") === "SINGLE";
  $("employeeWizardRecurringFields").hidden = single;
  $("employeeWizardSingleFields").hidden = !single;
  const absolute = valueOf("employeeWizardVestingMode") === "ABSOLUTE";
  $("employeeWizardRecurringUnit").textContent = absolute ? "options every" : "% of the grant every";
  try {
    const data = employeeWizardScheduleData();
    const expiration = dateValue("employeeWizardExpiration");
    const last = data.tranches.at(-1);
    if (expiration && last.vest_date > expiration) throw new Error(`The final vest on ${formatDate(last.vest_date)} is after the option expiration date`);
    preview.classList.remove("error");
    preview.innerHTML = `
      <div class="employee-preview-summary">
        <b>${data.tranches.length} vesting date${data.tranches.length === 1 ? "" : "s"}</b>
        <span>First: ${esc(formatDate(data.tranches[0].vest_date))}</span>
        <span>Fully vested: ${esc(formatDate(last.vest_date))}</span>
      </div>
      <p>${esc(employeeWizardScheduleSentence(data))}</p>
      ${employeeWizardTrancheTable(data.tranches)}`;
    return data;
  } catch (error) {
    const incomplete = /^(Enter|Choose)/.test(error.message);
    preview.classList.toggle("error", !incomplete);
    preview.innerHTML = `<p>${esc(error.message)}</p>`;
    return null;
  }
}

function validateEmployeeWizardVesting() {
  if (!valueOf("employeeWizardAccount")) return employeeWizardValidationError("employeeWizardVestingStatus", "Choose an ESOP account. Create one first if the list is empty.", "employeeWizardAccount");
  const data = renderEmployeeWizardVestingPreview();
  if (!data) return employeeWizardValidationError("employeeWizardVestingStatus", "Correct the vesting rule shown above before continuing.", "employeeWizardQuantity");
  const expiration = dateValue("employeeWizardExpiration");
  if (expiration && data.tranches.at(-1).vest_date > expiration) {
    return employeeWizardValidationError("employeeWizardVestingStatus", "The vesting schedule must finish before the option Expiration Date.", "employeeWizardFirstMonths");
  }
  $("employeeWizardVestingStatus").textContent = "";
  return true;
}

function employeeWizardGrantPayload() {
  const isPublic = valueOf("employeeWizardCompanyStatus") === "PUBLIC";
  return {
    id: state.editingEmployeeOptionSecurityId || undefined,
    instrument_type: "EMPLOYEE_STOCK_OPTION",
    company_name: valueOf("employeeWizardCompany"),
    listing_status: isPublic ? "PUBLIC" : "PRIVATE",
    public_symbol: isPublic ? cleanSecuritySymbol(valueOf("employeeWizardPublicSymbol")) : "",
    public_market: isPublic ? valueOf("employeeWizardPublicMarket") : "",
    currency: valueOf("employeeWizardCurrency"),
    location: valueOf("employeeWizardLocation"),
    grant_id: valueOf("employeeWizardGrantId"),
    grant_date: dateValue("employeeWizardGrantDate"),
    vesting_start_date: dateValue("employeeWizardVestingStart") || dateValue("employeeWizardGrantDate"),
    expiration_date: dateValue("employeeWizardExpiration"),
    strike_price: valueOf("employeeWizardStrikePrice"),
    contract_multiplier: 1,
    tax_scheme: valueOf("employeeWizardTaxScheme"),
    early_exercise_allowed: $("employeeWizardEarlyExercise").checked,
    manual_share_value: valueOf("employeeWizardShareValue") || undefined,
    valuation_date: dateValue("employeeWizardValuationDate"),
    restriction_end_date: dateValue("employeeWizardRestrictionEnd"),
    comments: valueOf("employeeWizardComments"),
  };
}

function renderEmployeeWizardReview() {
  const grant = employeeWizardGrantPayload();
  const vesting = employeeWizardScheduleData();
  const account = state.localAccounts.find((item) => item.id === valueOf("employeeWizardAccount"));
  const total = Number(valueOf("employeeWizardQuantity") || 0);
  $("employeeWizardReview").innerHTML = `
    <div class="employee-review-card">
      <h4>Grant</h4>
      <dl>
        <div><dt>Company</dt><dd>${esc(grant.company_name)}</dd></div>
        <div><dt>Grant ID</dt><dd>${esc(grant.grant_id || "Not provided")}</dd></div>
        <div><dt>Grant Date</dt><dd>${esc(formatDate(grant.grant_date))}</dd></div>
        <div><dt>Expiration Date</dt><dd>${esc(formatDate(grant.expiration_date))}</dd></div>
        <div><dt>Strike Price</dt><dd>${money(grant.strike_price, grant.currency, 4)}</dd></div>
        <div><dt>Company</dt><dd>${esc(grant.listing_status === "PUBLIC" ? `${grant.public_symbol} · ${grant.public_market}` : "Private Company")}</dd></div>
      </dl>
    </div>
    <div class="employee-review-card">
      <h4>Options and vesting</h4>
      <dl>
        <div><dt>ESOP Account</dt><dd>${esc(account ? accountLabel(account) : "Not selected")}</dd></div>
        <div><dt>Total Options</dt><dd>${fmt(total, 4)}</dd></div>
        <div><dt>Vesting Starts</dt><dd>${esc(formatDate(grant.vesting_start_date))}</dd></div>
        <div><dt>Schedule</dt><dd>${esc(employeeWizardScheduleSentence(vesting, total))}</dd></div>
      </dl>
    </div>
    <div class="employee-review-schedule">
      <h4>Exact vesting dates</h4>
      ${employeeWizardTrancheTable(vesting.tranches)}
    </div>`;
}

async function saveEmployeeOptionGrant() {
  if (!validateEmployeeWizardGrant() || !validateEmployeeWizardVesting()) return;
  const vestingData = employeeWizardScheduleData();
  const editing = Boolean(state.editingEmployeeOptionSecurityId);
  const payload = {
    security_id: state.editingEmployeeOptionSecurityId || undefined,
    transaction_id: state.editingEmployeeOptionTransactionId || undefined,
    grant: employeeWizardGrantPayload(),
    vesting: {
      id: state.editingEmployeeOptionTransactionId || undefined,
      account_db_id: valueOf("employeeWizardAccount"),
      quantity: valueOf("employeeWizardQuantity"),
      vest_date: vestingData.style === "SINGLE" ? vestingData.vestDate : "",
      vesting_schedule: vestingData.style === "SCHEDULE" ? vestingData.schedule : {},
      trade_date: dateValue("employeeWizardGrantDate"),
      comments: valueOf("employeeWizardComments"),
    },
  };
  const button = $("saveEmployeeOptionGrant");
  button.disabled = true;
  $("employeeOptionWizardStatus").textContent = editing ? "Updating grant…" : "Saving grant…";
  try {
    const path = editing
      ? `/api/local/employee-option-grants/${encodeURIComponent(state.editingEmployeeOptionSecurityId)}`
      : "/api/local/employee-option-grants";
    const saved = await api(path, { method: editing ? "PUT" : "POST", body: JSON.stringify(payload) });
    hideEmployeeOptionWizard();
    await Promise.all([loadLocalSecurities(), loadEmployeeOptionGrants()]);
    await loadPortfolio();
    const company = saved.security?.company_name || "Employee option grant";
    $("employeeOptionListStatus").textContent = editing ? `${company} was updated.` : `${company} was saved with its vesting schedule.`;
  } catch (error) {
    $("employeeOptionWizardStatus").textContent = `Could not save the grant: ${error.message}. Your entries are still here.`;
  } finally {
    button.disabled = false;
  }
}

function employeeGrantCardSchedule(grant) {
  const tx = grant.transaction;
  if (!tx) return "Vesting setup is incomplete";
  const schedule = tx.vesting_schedule || {};
  const tranches = Array.isArray(schedule.tranches) ? schedule.tranches : [];
  if (!tranches.length) return tx.vest_date ? `All options vest on ${formatDate(tx.vest_date)}` : "No vesting date saved";
  const first = tranches[0];
  const last = tranches.at(-1);
  return `${tranches.length} vesting dates · first ${formatDate(first.vest_date)} · fully vested ${formatDate(last.vest_date)}`;
}

function renderEmployeeOptionGrants() {
  const list = $("employeeOptionGrantsList");
  if (!list) return;
  if (!state.employeeOptionGrants.length) {
    list.innerHTML = '<div class="empty">No grants yet. The wizard above will guide you through the first one.</div>';
    if (employeeOptionsWorkflowActive() && state.employeeOptionWizardMode === "browse") beginNewEmployeeOptionGrant();
    return;
  }
  list.innerHTML = state.employeeOptionGrants.map((grant) => {
    const security = grant.security || {};
    const tx = grant.transaction;
    const account = tx ? state.localAccounts.find((item) => item.id === tx.account_db_id) : null;
    const lockedReason = grant.has_lifecycle_history
      ? "This grant has exercise or listing history"
      : "This grant has additional activity";
    return `
      <article class="employee-grant-card">
        <div class="employee-grant-main">
          <div class="employee-grant-title">
            <h4>${esc(security.company_name || security.name || "Employee option grant")}</h4>
            <span class="badge ${tx ? "ok" : "warn"}">${tx ? "Complete" : "Setup incomplete"}</span>
          </div>
          <p>${esc(security.grant_id ? `Grant ${security.grant_id}` : "No grant ID")} · Granted ${esc(formatDate(security.grant_date))} · Expires ${esc(formatDate(security.expiration_date))}</p>
          <p>${tx ? `${fmt(tx.quantity, 4)} options · ${esc(account ? accountLabel(account) : tx.account_id || "ESOP account")}` : "Open Edit to add the option quantity and vesting rule."}</p>
          <p class="employee-grant-schedule">${esc(employeeGrantCardSchedule(grant))}</p>
        </div>
        <div class="employee-grant-actions row-actions">
          <button class="secondary compact-button" type="button" data-edit-employee-option-grant="${esc(security.id)}"${grant.can_edit ? "" : ` disabled title="${esc(lockedReason)}"`}>Edit</button>
          <button class="secondary compact-button danger-button" type="button" data-delete-employee-option-grant="${esc(security.id)}"${grant.can_delete ? "" : ` disabled title="${esc(lockedReason)}"`}>Delete</button>
          ${security.listing_status !== "PUBLIC" ? `<button class="secondary compact-button" type="button" data-link-employee-listing="${esc(security.id)}">Link listing</button>` : ""}
          ${tx ? `<button class="secondary compact-button" type="button" data-exercise-employee-option="${esc(security.id)}">Exercise</button>` : ""}
        </div>
      </article>`;
  }).join("");
}

async function loadEmployeeOptionGrants() {
  const data = await api("/api/local/employee-option-grants");
  state.employeeOptionGrants = data.items || [];
  renderEmployeeOptionGrants();
}

function editEmployeeOptionGrant(securityId) {
  const grant = state.employeeOptionGrants.find((item) => item.security?.id === securityId);
  if (!grant || !grant.can_edit) {
    $("employeeOptionListStatus").textContent = "This grant cannot be edited because it has additional lifecycle activity.";
    return;
  }
  const security = grant.security;
  const tx = grant.transaction;
  clearEmployeeOptionWizard();
  state.editingEmployeeOptionSecurityId = security.id;
  state.editingEmployeeOptionTransactionId = tx?.id || "";
  $("employeeWizardCompany").value = security.company_name || "";
  $("employeeWizardGrantId").value = security.grant_id || "";
  setDateField("employeeWizardGrantDate", security.grant_date || "");
  $("employeeWizardCompanyStatus").value = security.listing_status || "PRIVATE";
  setCompanyLocationOptions(security.location || "USA", "employeeWizardLocation");
  setCurrencyOptions("employeeWizardCurrency", EMPLOYEE_OPTION_CURRENCIES);
  $("employeeWizardCurrency").value = security.currency || "USD";
  setDateField("employeeWizardExpiration", security.expiration_date || "");
  $("employeeWizardStrikePrice").value = security.strike_price || "";
  $("employeeWizardPublicSymbol").value = security.public_symbol || "";
  $("employeeWizardPublicMarket").value = security.public_market || "";
  $("employeeWizardTaxScheme").value = security.tax_scheme || "";
  $("employeeWizardShareValue").value = Number(security.manual_share_value || 0) > 0 ? security.manual_share_value : "";
  setDateField("employeeWizardValuationDate", security.valuation_date || "");
  setDateField("employeeWizardRestrictionEnd", security.restriction_end_date || "");
  $("employeeWizardEarlyExercise").checked = Boolean(security.early_exercise_allowed);
  $("employeeWizardComments").value = security.comments || tx?.comments || "";
  if (tx) {
    $("employeeWizardAccount").value = tx.account_db_id || "";
    $("employeeWizardQuantity").value = tx.quantity || "";
    const schedule = tx.vesting_schedule || {};
    $("employeeWizardVestingStyle").value = schedule.enabled ? "SCHEDULE" : "SINGLE";
    setDateField("employeeWizardVestingStart", schedule.vesting_start_date || security.vesting_start_date || security.grant_date || "");
    setDateField("employeeWizardSingleVestDate", tx.vest_date || "");
    if (schedule.enabled) {
      $("employeeWizardVestingMode").value = schedule.mode || "PERCENT";
      $("employeeWizardFirstMonths").value = schedule.cliff_months ?? 12;
      $("employeeWizardFirstValue").value = schedule.cliff_value ?? 25;
      $("employeeWizardInstallmentValue").value = schedule.installment_value ?? 6.25;
      $("employeeWizardInterval").value = schedule.interval_months ?? 3;
    }
  } else {
    setDateField("employeeWizardVestingStart", security.vesting_start_date || security.grant_date || "");
  }
  toggleEmployeeWizardCompanyFields();
  renderEmployeeWizardVestingPreview();
  state.employeeOptionWizardMaxStep = 3;
  showEmployeeOptionWizard("edit");
  setEmployeeOptionGuideStep(1);
  $("employeeOptionListStatus").textContent = `Editing ${security.company_name || security.name}.`;
  $("employeeOptionWizard")?.scrollIntoView({ block: "start", behavior: "smooth" });
  requestAnimationFrame(() => $("employeeWizardCompany")?.focus({ preventScroll: true }));
}

async function deleteEmployeeOptionGrant(securityId) {
  const grant = state.employeeOptionGrants.find((item) => item.security?.id === securityId);
  if (!grant) return;
  const company = grant.security.company_name || grant.security.name || "this grant";
  if (!window.confirm(`Delete the ${company} grant and its vesting schedule? This cannot be undone.`)) return;
  $("employeeOptionListStatus").textContent = `Deleting ${company}…`;
  try {
    await api(`/api/local/employee-option-grants/${encodeURIComponent(securityId)}`, { method: "DELETE" });
    await Promise.all([loadLocalSecurities(), loadEmployeeOptionGrants()]);
    await loadPortfolio();
    $("employeeOptionListStatus").textContent = `${company} was deleted.`;
  } catch (error) {
    $("employeeOptionListStatus").textContent = `Could not delete the grant: ${error.message}`;
  }
}

function updateEmployeeOptionsAccountNotice() {
  const notice = $("employeeOptionsAccountNotice");
  if (!notice) return;
  const hasEsopAccount = state.localAccounts.some((account) => String(account.type || "").toUpperCase() === "ESOP");
  notice.hidden = !employeeOptionsWorkflowActive() || hasEsopAccount;
  const saveButton = $("saveSecurity");
  if (saveButton && !state.editingTransactionId) saveButton.disabled = employeeOptionsWorkflowActive() && !hasEsopAccount;
  const wizardSaveButton = $("saveEmployeeOptionGrant");
  if (wizardSaveButton) wizardSaveButton.disabled = employeeOptionsWorkflowActive() && !hasEsopAccount;
}

function setSecuritiesWorkflow(workflow = "general") {
  const employeeOptions = workflow === "employee-options";
  state.securitiesWorkflow = employeeOptions ? "employee-options" : "general";
  $("securitiesModal")?.classList.toggle("employee-options-mode", employeeOptions);
  $("employeeOptionSavedSection").hidden = !employeeOptions;
  $("instrumentDefinitionSection").hidden = employeeOptions;
  $("accountTransactionSection").hidden = employeeOptions;
  $("savedTransactionsLabel").hidden = employeeOptions;
  $("securitiesList").hidden = employeeOptions;
  $("instrumentDefinitionBadge").hidden = true;
  $("accountTransactionBadge").hidden = true;
  $("securitiesEyebrow").textContent = employeeOptions ? "Equity compensation" : "Manual transactions";
  $("securitiesTitle").textContent = employeeOptions ? "Employee Stock Options" : "Securities";
  $("securitiesSubtitle").textContent = employeeOptions
    ? "Add, review, edit, or delete a grant and its complete vesting schedule."
    : "Define an instrument, then record it in an account.";
  $("instrumentDefinitionTitle").textContent = employeeOptions ? "Enter grant details" : "Instrument definition";
  $("instrumentDefinitionHint").textContent = employeeOptions
    ? "Use the dates and strike price shown in your company grant agreement."
    : "Describe the security once so it can be reused in transactions and price history.";
  $("accountTransactionTitle").textContent = employeeOptions ? "Add options and vesting" : "Account transaction";
  $("accountTransactionHint").textContent = employeeOptions
    ? "Choose the ESOP account, enter the total options granted, and review the calculated vesting dates."
    : "Choose an account and record the security movement.";
  $("definedInstrumentsLabel").textContent = employeeOptions ? "Your employee option grants" : "Defined instruments";
  $("savedTransactionsLabel").textContent = employeeOptions ? "Saved employee option activity" : "Saved transactions";
  $("saveManualSecurity").textContent = employeeOptions ? "Continue to options and vesting" : "Save instrument";
  $("saveSecurity").textContent = employeeOptions ? "Save employee option grant" : "Save transaction";
  $("securityQuantityLabel").textContent = employeeOptions ? "Total Options Granted *" : "Quantity *";
  $("securityDateLabel").textContent = employeeOptions ? "Grant Added Date *" : "Transaction Date *";
  document.querySelectorAll("[data-general-security-field], [data-general-transaction-field]").forEach((node) => {
    node.hidden = employeeOptions;
  });
  const instrumentType = $("manualInstrumentType");
  if (instrumentType) {
    if (employeeOptions) instrumentType.value = "EMPLOYEE_STOCK_OPTION";
    else if (instrumentType.value === "EMPLOYEE_STOCK_OPTION") instrumentType.value = "STOCK";
    instrumentType.disabled = employeeOptions;
  }
  const action = $("securityAction");
  if (action) {
    if (employeeOptions) action.value = "ADD";
    action.disabled = employeeOptions;
  }
  if (employeeOptions) {
    hideEmployeeOptionWizard();
    renderEmployeeOptionGrants();
  } else {
    $("employeeOptionWizard").hidden = true;
    $("employeeOptionsGuide").hidden = true;
  }
  refreshLocalAccountSelects();
  refreshManualSecuritySelects();
  toggleManualInstrumentFields();
  toggleTransactionCompFields();
  updateEmployeeOptionsAccountNotice();
}

function toggleManualInstrumentFields() {
  const type = valueOf("manualInstrumentType") || "STOCK";
  const isEmployeeOption = type === "EMPLOYEE_STOCK_OPTION";
  setCurrencyOptions("manualSecurityCurrency", isEmployeeOption ? EMPLOYEE_OPTION_CURRENCIES : null);
  const isOption = type === "OPTION" || type === "STOCK_OPTION" || isEmployeeOption;
  const isDerivative = isOption || type === "FUTURE";
  document.querySelectorAll("[data-derivative-field]").forEach((node) => { node.hidden = !isDerivative; });
  document.querySelectorAll("[data-option-field]").forEach((node) => { node.hidden = !isOption; });
  document.querySelectorAll("[data-non-employee-derivative-field]").forEach((node) => { node.hidden = !isDerivative || isEmployeeOption; });
  document.querySelectorAll("[data-non-employee-option-field]").forEach((node) => { node.hidden = !isOption || isEmployeeOption; });
  document.querySelectorAll("[data-employee-option-field]").forEach((node) => { node.hidden = !isEmployeeOption; });
  const isPrivate = isEmployeeOption && valueOf("manualIssuerStatus") !== "PUBLIC";
  document.querySelectorAll("[data-private-issuer-field]").forEach((node) => { node.hidden = !isPrivate; });
  document.querySelectorAll("[data-public-issuer-field]").forEach((node) => { node.hidden = isPrivate; });
  $("manualSecuritySymbol").disabled = isPrivate;
  $("manualSecurityMarket").disabled = isPrivate;
  $("manualSecuritySymbol").placeholder = isEmployeeOption ? (isPrivate ? "Not required for a private company" : "Public symbol") : "ID or symbol";
  $("manualSecurityMarket").placeholder = isEmployeeOption ? (isPrivate ? "Not required for a private company" : "Public stock market") : "Market";
  $("manualUnderlyingSymbol").hidden = isEmployeeOption || !isDerivative;
  $("manualOptionType").hidden = isEmployeeOption || !isOption;
  $("manualContractMultiplier").hidden = isEmployeeOption || !isDerivative;
  if (isPrivate) {
    $("manualSecuritySymbol").value = "";
    $("manualSecurityMarket").value = "";
  }
  if (isEmployeeOption) {
    $("manualContractMultiplier").value = "1";
    $("manualOptionType").value = "CALL";
  } else if (isOption && !valueOf("manualContractMultiplier")) {
    $("manualContractMultiplier").value = "100";
  }
  if (!isDerivative) {
    ["manualUnderlyingSymbol", "manualExpirationDate", "manualStrikePrice", "manualContractMultiplier"].forEach((id) => { $(id).value = ""; });
  }
}

async function loadManualSecurities() {
  const data = await api("/api/local/manual-securities");
  state.manualSecurities = data.items || [];
  const companyOptions = $("employeeCompanyOptions");
  if (companyOptions) {
    const companies = [...new Set(state.manualSecurities
      .filter((item) => item.instrument_type === "EMPLOYEE_STOCK_OPTION" && item.company_name)
      .map((item) => item.company_name))].sort((a, b) => a.localeCompare(b));
    companyOptions.innerHTML = companies.map((company) => `<option value="${esc(company)}"></option>`).join("");
  }
  refreshManualSecuritySelects();
  const list = $("manualSecuritiesList");
  if (!list) return;
  const visibleSecurities = employeeOptionsWorkflowActive()
    ? state.manualSecurities.filter((item) => item.instrument_type === "EMPLOYEE_STOCK_OPTION")
    : state.manualSecurities;
  list.innerHTML = visibleSecurities.length ? visibleSecurities.map((item) => `
    <div class="stack-item management-item">
      <b>${esc(item.instrument_type === "EMPLOYEE_STOCK_OPTION" ? (item.company_name || item.name) : item.symbol)}</b>
      <div>${esc(item.name || item.symbol)} · ${esc(optionLabel(item.instrument_type))} · ${item.instrument_type === "EMPLOYEE_STOCK_OPTION" ? `<span class="badge ${item.listing_status === "PUBLIC" ? "ok" : "warn"}">${esc(item.listing_status === "PUBLIC" ? `${item.public_symbol} · ${item.public_market}` : "Private Company")}</span>` : `${esc(item.stock_market)} · ${esc(item.currency)}`}</div>
      <button class="secondary compact-button" type="button" data-use-manual-security="${esc(item.id)}">${employeeOptionsWorkflowActive() ? "Add to account" : "Use"}</button>
      ${item.instrument_type === "EMPLOYEE_STOCK_OPTION" && item.listing_status !== "PUBLIC" ? `<button class="secondary compact-button" type="button" data-link-employee-listing="${esc(item.id)}">Link public listing</button>` : ""}
      ${item.instrument_type === "EMPLOYEE_STOCK_OPTION" ? `<button class="secondary compact-button" type="button" data-exercise-employee-option="${esc(item.id)}">Exercise</button>` : ""}
      <button class="secondary compact-button" type="button" data-delete-manual-security="${esc(item.id)}">Remove</button>
      <div class="sub">${esc(optionLabel(item.asset_class))}${item.grant_id ? ` · Grant ID ${esc(item.grant_id)}` : ""}${item.grant_date ? ` · Grant Date ${esc(formatDate(item.grant_date))}` : ""}${item.vesting_start_date ? ` · Vesting Start ${esc(formatDate(item.vesting_start_date))}` : ""}${item.underlying_symbol ? ` · Underlying ${esc(item.underlying_symbol)}` : ""}${item.option_type && item.instrument_type !== "EMPLOYEE_STOCK_OPTION" ? ` · ${esc(item.option_type)} option` : ""}${item.expiration_date ? ` · Exp ${esc(formatDate(item.expiration_date))}` : ""}${item.strike_price ? ` · Strike ${fmt(item.strike_price, 4)}` : ""}${item.instrument_type !== "EMPLOYEE_STOCK_OPTION" && item.contract_multiplier ? ` · Multiplier ${fmt(item.contract_multiplier, 4)}` : ""}${item.manual_share_value ? ` · Valuation ${money(item.manual_share_value, item.currency, 4)} on ${esc(formatDate(item.valuation_date))}` : ""}${item.comments ? ` · ${esc(item.comments)}` : ""}</div>
    </div>
  `).join("") : `<div class="empty">${employeeOptionsWorkflowActive() ? "No employee option grants yet. Enter your first grant above." : "No defined instruments yet"}</div>`;
}

function syncEmployeeIssuerFromCompany() {
  const companyName = valueOf("manualCompanyName").toLocaleLowerCase();
  if (!companyName) return;
  const match = state.manualSecurities.find((item) => (
    item.instrument_type === "EMPLOYEE_STOCK_OPTION"
    && String(item.company_name || "").toLocaleLowerCase() === companyName
  ));
  if (!match) return;
  $("manualIssuerStatus").value = match.listing_status || "PRIVATE";
  $("manualSecuritySymbol").value = match.public_symbol || "";
  $("manualSecurityMarket").value = match.public_market || "";
  setCompanyLocationOptions(match.location || valueOf("manualSecurityLocation") || "USA");
  const matchCurrency = String(match.currency || "").toUpperCase();
  $("manualSecurityCurrency").value = EMPLOYEE_OPTION_CURRENCIES.includes(matchCurrency)
    ? matchCurrency
    : preferredCurrencyForLocation(valueOf("manualSecurityLocation")) || "USD";
  $("manualShareValue").value = Number(match.manual_share_value || 0) > 0 ? match.manual_share_value : "";
  setDateField("manualValuationDate", match.valuation_date || "");
  setDateField("manualRestrictionEndDate", match.restriction_end_date || "");
  toggleManualInstrumentFields();
  $("manualSecurityStatus").textContent = `Using existing issuer details for ${match.company_name}. This grant remains separate.`;
}

async function saveManualSecurity() {
  const isEmployeeOption = valueOf("manualInstrumentType") === "EMPLOYEE_STOCK_OPTION";
  const listingStatus = valueOf("manualIssuerStatus") || "PRIVATE";
  const currency = valueOf("manualSecurityCurrency") || "USD";
  if (isEmployeeOption && !EMPLOYEE_OPTION_CURRENCIES.includes(currency)) {
    $("manualSecurityStatus").textContent = "Employee stock-option currency must be ILS, USD, or EUR.";
    $("manualSecurityCurrency").focus();
    return;
  }
  const payload = {
    symbol: isEmployeeOption && listingStatus === "PRIVATE" ? "" : cleanSecuritySymbol(valueOf("manualSecuritySymbol")),
    name: valueOf("manualSecurityName"),
    stock_market: isEmployeeOption && listingStatus === "PRIVATE" ? "" : valueOf("manualSecurityMarket"),
    instrument_type: valueOf("manualInstrumentType"),
    currency,
    location: valueOf("manualSecurityLocation") || "USA",
    underlying_symbol: cleanSecuritySymbol(valueOf("manualUnderlyingSymbol")),
    option_type: valueOf("manualOptionType"),
    expiration_date: dateValue("manualExpirationDate"),
    strike_price: valueOf("manualStrikePrice") || 0,
    contract_multiplier: valueOf("manualContractMultiplier") || 0,
    company_name: valueOf("manualCompanyName"),
    listing_status: listingStatus,
    public_symbol: listingStatus === "PUBLIC" ? cleanSecuritySymbol(valueOf("manualSecuritySymbol")) : "",
    public_market: listingStatus === "PUBLIC" ? valueOf("manualSecurityMarket") : "",
    grant_id: valueOf("manualGrantId"),
    grant_date: dateValue("manualGrantDate"),
    vesting_start_date: dateValue("manualVestingStartDate") || dateValue("manualGrantDate"),
    tax_scheme: valueOf("manualTaxScheme"),
    early_exercise_allowed: $("manualEarlyExercise").checked,
    manual_share_value: valueOf("manualShareValue") || undefined,
    valuation_date: dateValue("manualValuationDate"),
    restriction_end_date: dateValue("manualRestrictionEndDate"),
    comments: valueOf("manualSecurityComments"),
  };
  const saved = await api("/api/local/manual-securities", { method: "POST", body: JSON.stringify(payload) });
  $("manualSecurityStatus").textContent = isEmployeeOption
    ? `Grant details saved for ${saved.company_name || saved.symbol}. Complete the options and vesting step below.`
    : `Instrument saved: ${saved.company_name || saved.symbol}${saved.grant_id ? ` · ${saved.grant_id}` : ""}`;
  ["manualSecuritySymbol", "manualSecurityName", "manualSecurityMarket", "manualCompanyName", "manualGrantId", "manualGrantDate", "manualVestingStartDate", "manualUnderlyingSymbol", "manualExpirationDate", "manualStrikePrice", "manualContractMultiplier", "manualTaxScheme", "manualShareValue", "manualValuationDate", "manualRestrictionEndDate", "manualSecurityComments"].forEach((id) => { $(id).value = ""; });
  $("manualEarlyExercise").checked = false;
  $("manualIssuerStatus").value = "PRIVATE";
  toggleManualInstrumentFields();
  await loadManualSecurities();
  if (isEmployeeOption) {
    $("securityKnownInstrument").value = saved.id;
    applyInstrumentToForm(saved, "security");
    const esopAccount = state.localAccounts.find((account) => String(account.type || "").toUpperCase() === "ESOP");
    if (esopAccount) $("securityAccount").value = esopAccount.id;
    setEmployeeOptionGuideStep(2);
    $("securityStatus").textContent = esopAccount
      ? "Grant selected. Enter the total options and confirm the vesting schedule."
      : "Grant details are saved. Create an ESOP account to add the options and vesting schedule.";
    requestAnimationFrame(() => {
      $("accountTransactionSection")?.scrollIntoView({ block: "start", behavior: "smooth" });
      $("securityQuantity")?.focus({ preventScroll: true });
    });
  }
  await loadPortfolio();
}

function openEmployeeListing(securityId) {
  const security = instrumentById(securityId);
  if (!security) return;
  state.activeEmployeeListingSecurityId = securityId;
  $("employeeListingSubtitle").textContent = `${security.company_name || security.name}${security.grant_id ? ` · Grant ${security.grant_id}` : ""}`;
  $("employeeListingSymbol").value = security.public_symbol || "";
  $("employeeListingMarket").value = security.public_market || "";
  setDateField("employeeListingDate", security.listing_date || todayString());
  setDateField("employeeListingRestrictionDate", security.restriction_end_date || "");
  $("employeeListingAllowManual").checked = false;
  $("employeeListingStatus").textContent = "Linking changes the issuer valuation source; the grant identity and vesting history remain unchanged.";
  openModal("employeeListingModal");
}

async function saveEmployeeListing() {
  const securityId = state.activeEmployeeListingSecurityId;
  if (!securityId) return;
  const result = await api(`/api/local/manual-securities/${encodeURIComponent(securityId)}/link-listing`, {
    method: "POST",
    body: JSON.stringify({
      public_symbol: cleanSecuritySymbol(valueOf("employeeListingSymbol")),
      public_market: valueOf("employeeListingMarket"),
      listing_date: dateValue("employeeListingDate"),
      restriction_end_date: dateValue("employeeListingRestrictionDate"),
      allow_manual: $("employeeListingAllowManual").checked,
    }),
  });
  $("employeeListingStatus").textContent = result.unchanged ? "This listing was already linked." : "Public listing linked. Existing grants and schedules were preserved.";
  await Promise.all([loadManualSecurities(), loadLocalSecurities(), loadPortfolio()]);
}

function openEmployeeExercise(securityId) {
  const security = instrumentById(securityId);
  if (!security) return;
  state.activeEmployeeExerciseSecurityId = securityId;
  refreshLocalAccountSelects();
  const esopAccount = state.localAccounts.find((account) => String(account.type || "").toUpperCase() === "ESOP");
  if (esopAccount) $("employeeExerciseAccount").value = esopAccount.id;
  $("employeeExerciseSubtitle").textContent = `${security.company_name || security.name}${security.grant_id ? ` · Grant ${security.grant_id}` : ""} · Strike ${money(security.strike_price || 0, security.currency || state.baseCurrency, 4)}`;
  $("employeeExerciseQuantity").value = "";
  $("employeeExerciseRatio").value = "1";
  $("employeeExerciseCostBasis").value = security.strike_price || "";
  setDateField("employeeExerciseDate", todayString());
  $("employeeExerciseComments").value = "";
  $("employeeExerciseStatus").textContent = security.early_exercise_allowed
    ? "Early exercise is enabled for this grant."
    : "Only options vested by the Exercise Date can be exercised.";
  openModal("employeeExerciseModal");
}

async function saveEmployeeExercise() {
  const securityId = state.activeEmployeeExerciseSecurityId;
  if (!securityId) return;
  const result = await api(`/api/local/manual-securities/${encodeURIComponent(securityId)}/exercise`, {
    method: "POST",
    body: JSON.stringify({
      account_db_id: valueOf("employeeExerciseAccount"),
      quantity: valueOf("employeeExerciseQuantity"),
      share_ratio: valueOf("employeeExerciseRatio") || 1,
      share_cost_basis: valueOf("employeeExerciseCostBasis"),
      exercise_date: dateValue("employeeExerciseDate"),
      comments: valueOf("employeeExerciseComments"),
    }),
  });
  $("employeeExerciseStatus").textContent = `Exercise recorded: ${fmt(result.option_quantity_exercised, 4)} options became ${fmt(result.share_quantity_acquired, 4)} shares. ${fmt(result.remaining_option_quantity, 4)} options remain.`;
  await Promise.all([loadManualSecurities(), loadLocalSecurities(), loadLocalPrices(), loadPortfolio()]);
}

function transactionVestingSummary(tx) {
  const tranches = Array.isArray(tx.vesting_schedule?.tranches) ? tx.vesting_schedule.tranches : [];
  if (tranches.length) {
    const first = tranches[0];
    const last = tranches[tranches.length - 1];
    return ` · ${tranches.length} vesting dates, ${formatDate(first.vest_date)}–${formatDate(last.vest_date)}`;
  }
  return tx.vest_date ? ` · Vests ${formatDate(tx.vest_date)}` : "";
}

async function loadLocalSecurities() {
  await loadManualSecurities();
  const data = await api("/api/local/securities");
  state.localTransactions = data.items || [];
  refreshMarketOptions();
  if (state.items?.length) renderAnalytics(state.items);
  const visibleTransactions = employeeOptionsWorkflowActive()
    ? state.localTransactions.filter((tx) => tx.instrument_type === "EMPLOYEE_STOCK_OPTION")
    : state.localTransactions;
  $("securitiesList").innerHTML = visibleTransactions.length ? visibleTransactions.map((tx) => `
    <div class="stack-item management-item">
      <b>${esc(tx.action)} ${esc(tx.instrument_type === "EMPLOYEE_STOCK_OPTION" ? (tx.company_name || tx.security_name || "Employee option") : tx.symbol)}</b>
      <span>${fmt(tx.quantity, 4)} @ ${fmt(tx.price_input, 4)} (${esc(tx.currency)} ${fmt(tx.price, 4)})${tx.instrument_type ? ` · ${esc(tx.instrument_type)}` : ""}</span>
      ${tx.transition_id
        ? '<span class="badge ok" title="Created by an audited employee-option lifecycle action">Lifecycle transaction · read-only</span>'
        : `<button class="secondary compact-button" type="button" data-edit-security="${esc(tx.id)}">Edit</button>
           <button class="secondary compact-button" type="button" data-delete-security="${esc(tx.id)}">Delete</button>`}
      <div class="sub">${esc(tx.instrument_type === "EMPLOYEE_STOCK_OPTION" ? (tx.listing_status === "PUBLIC" ? `${tx.public_symbol} · ${tx.public_market}` : "Private company") : tx.stock_market)} · ${esc(tx.asset_class)}${tx.grant_id ? ` · Grant ${esc(tx.grant_id)}` : ""}${tx.option_type && tx.instrument_type !== "EMPLOYEE_STOCK_OPTION" ? ` · ${esc(tx.option_type)}` : ""}${tx.expiration_date ? ` · Exp ${esc(formatDate(tx.expiration_date))}` : ""}${transactionVestingSummary(tx)}${tx.strike_price ? ` · Strike ${fmt(tx.strike_price, 4)}` : ""}${tx.purchase_price ? ` · Purchase ${fmt(tx.purchase_price, 4)}` : ""} · ${esc(formatDate(tx.trade_date))} · ${transactionCashImpact(tx) ? `Cash ${signedMoney(transactionCashImpact(tx), tx.currency)}` : "No cash movement"} · ${esc(tx.management_company || "")} ${esc(tx.account_id || "")}</div>
    </div>
  `).join("") : `<div class="empty">${employeeOptionsWorkflowActive() ? "No employee option activity saved yet" : "No manual securities yet"}</div>`;
  renderAlarms();
  loadEquityCompQuotes().catch(reportBackgroundError);
}

async function saveSecurity() {
  const instrumentType = selectedTransactionInstrumentType();
  const usesSchedule = instrumentType === "EMPLOYEE_STOCK_OPTION" && valueOf("securityAction") === "ADD" && valueOf("securityVestingStyle") === "SCHEDULE";
  const payload = {
    account_db_id: valueOf("securityAccount"),
    security_id: valueOf("securityKnownInstrument"),
    action: valueOf("securityAction"),
    symbol: cleanSecuritySymbol(valueOf("securitySymbol")),
    stock_market: valueOf("securityMarket"),
    asset_class: valueOf("securityAssetClass"),
    quantity: valueOf("securityQuantity"),
    price_input: valueOf("securityPrice"),
    vest_date: usesSchedule ? "" : dateValue("securityVestDate"),
    vesting_schedule: usesSchedule ? vestingScheduleFromForm() : {},
    purchase_price: valueOf("securityPurchasePrice"),
    strike_price: valueOf("securityStrikePrice"),
    trade_date: dateValue("securityDate") || todayString(),
    allow_manual: $("securityAllowManual").checked,
    comments: valueOf("securityComments"),
  };
  try {
    const editingId = state.editingTransactionId;
    const path = editingId ? `/api/local/securities/${encodeURIComponent(editingId)}` : "/api/local/securities";
    await api(path, { method: editingId ? "PUT" : "POST", body: JSON.stringify(payload) });
    $("securityStatus").textContent = employeeOptionsWorkflowActive()
      ? (editingId ? "Employee option grant updated" : "Employee option grant saved with its vesting schedule")
      : (editingId ? "Security transaction updated" : "Security transaction saved");
    clearSecurityForm();
    await loadLocalSecurities();
    await loadPortfolio();
    if (employeeOptionsWorkflowActive()) setEmployeeOptionGuideStep(2, { complete: true });
  } catch (error) {
    $("securityStatus").textContent = employeeOptionsWorkflowActive()
      ? `Could not save the options and vesting schedule: ${error.message}. Your grant definition is still available above, so you can correct this step and retry.`
      : `Error: ${error.message}. Check "Save manually if market data is unavailable" to save a symbol without provider validation.`;
  }
}

async function loadEvents() {
  const data = await api("/api/local/events");
  state.localEvents = data.items || [];
  const settings = data.dividends || {};
  const status = $("eventsStatus");
  if (status) {
    status.textContent = `Dividend scan starts ${formatDate(settings.start_date || "")} · tax ${pct(Number(settings.tax_rate || 0) * 100)} · next ${settings.next_run ? formatDate(String(settings.next_run).slice(0, 10)) : "not scheduled"}`;
  }
  const list = $("eventsList");
  if (!list) return;
  list.innerHTML = state.localEvents.length ? state.localEvents.map((event) => `
    <div class="stack-item management-item event-item ${state.focusedEventId === event.id ? "focused-event" : ""}" data-event-id="${esc(event.id)}">
      <b>${esc(event.type)} ${esc(event.symbol || "")}</b>
      <span>${esc(formatDate(event.event_date))} · ${esc(event.status)} · Net ${money(event.net_amount || 0, event.currency || state.baseCurrency, 2)}</span>
      ${event.transaction_id ? `<button class="secondary compact-button" type="button" data-edit-security="${esc(event.transaction_id)}">Edit transaction</button>` : ""}
      <div class="sub">${esc(event.account_label || event.account_db_id || "")} · Gross ${money(event.gross_amount || 0, event.currency || state.baseCurrency, 2)} · Tax ${money(event.tax_amount || 0, event.currency || state.baseCurrency, 2)} · ${esc(event.source_key || "")}</div>
    </div>
  `).join("") : '<div class="empty">No events yet</div>';
  renderAlarms();
  focusEventRow();
}

async function runDividendEvents() {
  $("eventsStatus").textContent = "Scanning dividends";
  const result = await api("/api/local/events/dividends/run", { method: "POST", body: "{}" });
  state.localEvents = result.items || [];
  $("eventsStatus").textContent = `Checked ${result.checked} holdings · ${result.processed} processed · ${result.pending} pending · ${result.skipped} skipped`;
  await Promise.all([loadEvents(), loadLocalSecurities(), loadPortfolio({ refresh: true })]);
}

function eventDaysFromToday(eventDate) {
  const iso = parseDateInput(eventDate);
  if (!iso) return 0;
  const [year, month, day] = iso.split("-").map(Number);
  const eventUtc = Date.UTC(year, month - 1, day);
  const todayIso = todayString();
  const [todayYear, todayMonth, todayDay] = todayIso.split("-").map(Number);
  const todayUtc = Date.UTC(todayYear, todayMonth - 1, todayDay);
  return Math.round((eventUtc - todayUtc) / 86400000);
}

function dividendAlarmMessage(event) {
  const details = event.details || {};
  const currency = event.currency || state.baseCurrency;
  const perShare = Number(details.gross_per_share || 0);
  const shares = Number(details.shares || 0);
  const perShareText = perShare > 0 ? `${money(perShare, currency, 4)} per share` : "per-share amount not available";
  const shareText = shares > 0 ? `${fmt(shares, 3)} shares` : "shares not available";
  const netText = money(event.net_amount || 0, currency, 2);
  const grossText = money(event.gross_amount || 0, currency, 2);
  const taxText = money(event.tax_amount || 0, currency, 2);
  const days = eventDaysFromToday(event.event_date);
  if (event.status === "pending") {
    const dueText = days > 0 ? `in ${days} day${days === 1 ? "" : "s"}` : `on ${formatDate(event.event_date)}`;
    return {
      tone: "future",
      title: `${event.symbol} dividend is expected ${dueText}`,
      body: `Expected ${perShareText}. Estimated net total ${netText} after ${taxText} tax for ${shareText}.`,
      meta: `Payment date ${formatDate(event.event_date)} · Gross ${grossText}`,
    };
  }
  return {
    tone: "paid",
    title: `${event.symbol} dividend was paid`,
    body: `Added ${netText} to cash from ${perShareText} for ${shareText}.`,
    meta: `Paid ${formatDate(event.event_date)} · Gross ${grossText} · Tax ${taxText}`,
  };
}

function dividendAlarms() {
  return (state.localEvents || [])
    .filter((event) => event.type === "DIVIDEND")
    .map((event) => ({ event, ...dividendAlarmMessage(event) }))
    .sort((a, b) => {
      if (a.event.status !== b.event.status) return a.event.status === "pending" ? -1 : 1;
      return String(a.event.event_date || "").localeCompare(String(b.event.event_date || ""));
    });
}

function vestingAlarms() {
  const leadDays = normalizedVestingAlertDays(state.vestingAlertDays);
  const lots = [
    ...equityCompLots("rsu", state.items || []).map((lot) => ({ ...lot, kind: "rsu" })),
    ...equityCompLots("option", state.items || []).map((lot) => ({ ...lot, kind: "option" })),
  ];
  return lots
    .filter((lot) => lot.vestDate)
    .map((lot) => ({ lot, days: eventDaysFromToday(lot.vestDate) }))
    .filter(({ days }) => days >= 0 && days <= leadDays)
    .map(({ lot, days }) => {
      const unit = lot.kind === "rsu" ? "RSU" : "stock option";
      const singular = Number(lot.quantity) === 1;
      const quantityLabel = `${fmt(lot.quantity, 2)} ${unit}${singular ? "" : "s"}`;
      const dueText = days === 0 ? "today" : `in ${days} day${days === 1 ? "" : "s"}`;
      return {
        kind: "vesting",
        tone: "vesting",
        transactionId: lot.transactionId,
        trancheSequence: lot.trancheSequence,
        title: `${lot.symbol} ${unit}${singular ? " vests" : "s vest"} ${dueText}`,
        body: `${quantityLabel} ${singular ? "is" : "are"} scheduled to vest.`,
        meta: `Vest Date: ${formatDate(lot.vestDate)} · ${leadDays}-day notice window`,
        sortDate: lot.vestDate,
      };
    })
    .sort((a, b) => String(a.sortDate).localeCompare(String(b.sortDate)) || a.title.localeCompare(b.title));
}

function alarmDismissalId(alarm) {
  if (alarm.kind === "vesting") {
    return ["vesting", alarm.transactionId, alarm.trancheSequence || 1, alarm.sortDate].join(":");
  }
  const event = alarm.event || {};
  return ["dividend", event.id || [event.symbol, event.event_date, event.status].join(":")].join(":");
}

function currentAlarms({ includeDismissed = false } = {}) {
  const dismissed = new Set(state.dismissedAlarmIds);
  const visible = (alarms) => includeDismissed
    ? alarms
    : alarms.filter((alarm) => !dismissed.has(alarmDismissalId(alarm)));
  return {
    dividends: visible(dividendAlarms()),
    vesting: visible(vestingAlarms()),
  };
}

function clearAlarms() {
  const { dividends, vesting } = currentAlarms();
  const alarms = [...vesting, ...dividends];
  if (!alarms.length) return;
  state.dismissedAlarmIds = [...state.dismissedAlarmIds, ...alarms.map(alarmDismissalId)];
  saveAlarmDismissals();
  renderAlarms();
  $("alarmsStatus").textContent = `${alarms.length} alarm${alarms.length === 1 ? "" : "s"} cleared. New alarms will still appear.`;
}

function renderAlarms() {
  const { dividends, vesting } = currentAlarms();
  const alarms = [...vesting, ...dividends];
  const count = $("alarmsCount");
  if (count) count.textContent = String(alarms.length);
  const button = $("alarmsButton");
  if (button) button.classList.toggle("has-alarms", alarms.length > 0);
  const clearButton = $("clearAlarms");
  if (clearButton) clearButton.disabled = alarms.length === 0;
  const status = $("alarmsStatus");
  if (status) {
    const future = dividends.filter((alarm) => alarm.event.status === "pending").length;
    const paid = dividends.filter((alarm) => alarm.event.status === "processed").length;
    status.textContent = alarms.length
      ? `${vesting.length} upcoming vesting alarm${vesting.length === 1 ? "" : "s"} · ${future} future dividend${future === 1 ? "" : "s"} · ${paid} paid dividend${paid === 1 ? "" : "s"}`
      : "No vesting or dividend alarms in the current notice window.";
  }
  if ($("vestingAlertDays")) $("vestingAlertDays").value = String(state.vestingAlertDays);
  if ($("alarmSettingsStatus") && !$("alarmSettingsStatus").textContent) {
    $("alarmSettingsStatus").textContent = `Showing vest dates up to ${state.vestingAlertDays} day${state.vestingAlertDays === 1 ? "" : "s"} in advance.`;
  }
  const list = $("alarmsList");
  if (!list) return;
  list.innerHTML = alarms.length ? alarms.map((alarm) => `
    <button class="alarm-item ${esc(alarm.tone)}" type="button" ${alarm.kind === "vesting" ? `data-open-vesting-alarm="${esc(alarm.transactionId)}"` : `data-open-dividend-alarm="${esc(alarm.event.id)}"`}>
      <span class="alarm-kind">${alarm.kind === "vesting" ? "Upcoming vesting" : alarm.tone === "future" ? "Future dividend" : "Dividend paid"}</span>
      <b>${esc(alarm.title)}</b>
      <span>${esc(alarm.body)}</span>
      <small>${esc(alarm.meta)}</small>
    </button>
  `).join("") : '<div class="empty">No vesting or dividend alarms</div>';
}

function focusEventRow() {
  if (!state.focusedEventId) return;
  const row = [...document.querySelectorAll("[data-event-id]")]
    .find((item) => item.dataset.eventId === state.focusedEventId);
  if (!row) return;
  row.classList.add("focused-event");
  row.scrollIntoView({ block: "center", behavior: "smooth" });
}

function openDividendAlarm(eventId) {
  state.focusedEventId = eventId;
  const alarmsModal = $("alarmsModal");
  if (alarmsModal && !alarmsModal.hidden) closeModal(alarmsModal);
  openModal("eventsModal");
  setTimeout(focusEventRow, 100);
}

function openVestingAlarm(transactionId) {
  const alarmsModal = $("alarmsModal");
  if (alarmsModal && !alarmsModal.hidden) closeModal(alarmsModal);
  const transaction = state.localTransactions.find((item) => item.id === transactionId);
  setSecuritiesWorkflow(transaction?.instrument_type === "EMPLOYEE_STOCK_OPTION" ? "employee-options" : "general");
  openModal("securitiesModal");
  if (transactionId) editSecurityTransaction(transactionId);
}

async function loadLocalPrices() {
  await loadManualSecurities();
  const data = await api("/api/local/prices");
  state.localPrices = data.items || [];
  fillPriceFormFromFocus();
  renderPriceFocusBar();
  if (state.items?.length) renderAnalytics(state.items);
  const visiblePrices = state.localPrices.filter(priceMatchesFocus);
  $("pricesList").innerHTML = visiblePrices.length ? visiblePrices.map((price) => `
    <div class="stack-item management-item">
      <b>${esc(price.symbol)}</b>
      <span>${esc(formatDate(price.price_date))} · ${fmt(price.price_input, 4)} (${esc(price.currency)} ${fmt(price.price, 4)})</span>
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
    price_date: dateValue("priceDate") || todayString(),
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
  const breakdown = (items) => Object.entries(items || {})
    .sort((left, right) => Number(right[1] || 0) - Number(left[1] || 0))
    .map(([label, value]) => `<div class="report-breakdown-row"><span>${esc(label)}</span><b>${fmt(value, 0)}</b></div>`)
    .join("") || '<div class="empty">No report data</div>';
  $("reportsByType").innerHTML = breakdown(report.by_type);
  $("reportsByLocation").innerHTML = breakdown(report.by_location);
  updatePdfReportMeta();
}

function updatePdfReportMeta() {
  const account = $("reportAccount")?.selectedOptions?.[0]?.textContent?.trim() || "All accounts";
  const accountType = $("reportAccountType")?.selectedOptions?.[0]?.textContent?.trim() || "Any account type";
  const location = valueOf("reportLocation") || "All locations";
  const from = valueOf("reportFrom") || formatDate(HISTORY_START_DATE);
  const to = valueOf("reportTo") || formatDate(todayString());
  $("pdfReportMeta").textContent = `${account} · ${accountType} · ${location} · ${from}–${to} · Generated ${formatDate(todayString())}`;
}

async function exportReportsPdf() {
  $("reportsExportStatus").textContent = "Preparing PDF report";
  await loadReports();
  updatePdfReportMeta();
  const previousTitle = document.title;
  let cleaned = false;
  const cleanup = () => {
    if (cleaned) return;
    cleaned = true;
    document.body.classList.remove("report-print-mode");
    document.title = previousTitle;
    $("reportsExportStatus").textContent = "PDF export opened. Choose Save as PDF in the print dialog.";
  };
  window.addEventListener("afterprint", cleanup, { once: true });
  document.body.classList.add("report-print-mode");
  document.title = `portfolio-report-${todayString()}`;
  requestAnimationFrame(() => requestAnimationFrame(() => {
    window.print();
    setTimeout(cleanup, 1000);
  }));
}

function renderAccountTrend(trend) {
  const accounts = (trend.accounts || []).filter((account) => account.points?.length);
  const series = accounts.flatMap((account) => account.points.map((point) => ({ ...point, account: account.account })));
  if (!series.length) {
    $("accountTrendChart").innerHTML = '<div class="empty">No trend data for this date range</div>';
    return;
  }
  const width = 760;
  const height = 280;
  const padLeft = 48;
  const padRight = 72;
  const plotWidth = width - padLeft - padRight;
  const values = series.map((point) => Number(point.value || 0));
  const profits = series.map((point) => Number(point.profit_percent || 0));
  const minValue = Math.min(...values, 0);
  const maxValue = Math.max(...values, 1);
  const minProfit = Math.min(...profits, 0);
  const maxProfit = Math.max(...profits, 1);
  const scaleLane = (value, min, max, top, bottom) => bottom - ((value - min) / (max - min || 1)) * (bottom - top);
  const scaleValue = (value) => scaleLane(value, minValue, maxValue, 42, 124);
  const scaleProfit = (value) => scaleLane(value, minProfit, maxProfit, 170, 244);
  const pointX = (pointIndex, count) => padLeft + (pointIndex / Math.max(1, count - 1)) * plotWidth;
  const accountLines = accounts.map((account, index) => {
    const points = account.points;
    const valuePath = points.map((point, pointIndex) => `${pointIndex ? "L" : "M"} ${pointX(pointIndex, points.length)} ${scaleValue(point.value)}`).join(" ");
    const profitPath = points.map((point, pointIndex) => `${pointIndex ? "L" : "M"} ${pointX(pointIndex, points.length)} ${scaleProfit(point.profit_percent)}`).join(" ");
    const last = points.at(-1) || {};
    const label = accountLabel(account.account);
    return `<g>
      <title>${esc(`${label}\nValue ${fmt(last.value, 0)}\nProfit ${pct(last.profit_percent)}\nDate ${formatDate(last.date || "")}`)}</title>
      <path d="${valuePath}" fill="none" stroke="${colorAt(index)}" stroke-width="3"></path>
      <path d="${profitPath}" fill="none" stroke="${colorAt(index + 3)}" stroke-width="2" stroke-dasharray="5 5"></path>
    </g>`;
  }).join("");
  const legend = accounts.map((account, index) => {
    const last = account.points.at(-1) || {};
    return `
      <div class="report-trend-account" title="${esc(accountLabel(account.account))}">
        <b><i style="--line-color:${colorAt(index)}"></i>${esc(accountLabel(account.account))}</b>
        <span>Value ${fmt(last.value, 0)} · Profit ${pct(last.profit_percent)}</span>
      </div>`;
  }).join("");
  $("accountTrendChart").innerHTML = `
    <div class="chart-header">
      <div>
        <div class="chart-title">Account value and profit %</div>
        <small class="chart-subtitle">Solid lines show value. Dashed lines show profit percentage.</small>
      </div>
    </div>
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Account value and percent profit trend">
      <text x="${padLeft}" y="24">Value</text>
      <text x="${padLeft}" y="154">Profit %</text>
      <line x1="${padLeft}" y1="42" x2="${padLeft + plotWidth}" y2="42"></line>
      <line x1="${padLeft}" y1="124" x2="${padLeft + plotWidth}" y2="124"></line>
      <line x1="${padLeft}" y1="170" x2="${padLeft + plotWidth}" y2="170"></line>
      <line x1="${padLeft}" y1="244" x2="${padLeft + plotWidth}" y2="244"></line>
      <text x="${padLeft + plotWidth + 10}" y="46">${fmt(maxValue, 0)}</text>
      <text x="${padLeft + plotWidth + 10}" y="128">${fmt(minValue, 0)}</text>
      <text x="${padLeft + plotWidth + 10}" y="174">${pct(maxProfit)}</text>
      <text x="${padLeft + plotWidth + 10}" y="248">${pct(minProfit)}</text>
      ${accountLines}
    </svg>
    <div class="report-trend-legend">${legend}</div>`;
}

function renderFinanceReport(report) {
  state.financeReport = report;
  const profile = report.profile || {};
  const summary = report.summary || {};
  const reports = report.reports || [];
  const company = profile.name || report.symbol || "Company";
  $("financeReportStatus").textContent = `${company} · ${providerStatusHint(report.provider_status || {}) || "Online data loaded"}`;
  $("financeReportSummary").innerHTML = [
    ["Years", summary.years || 0],
    ["Latest revenue", fmt(summary.latest_revenue, 0)],
    ["Revenue growth", pct(summary.latest_revenue_growth_percent)],
    ["Net income", fmt(summary.latest_net_income, 0)],
    ["Net margin", pct(summary.latest_net_margin_percent)],
    ["Free cash flow", fmt(summary.latest_free_cash_flow, 0)],
    ["Long-term debt", fmt(summary.latest_long_term_debt, 0)],
  ].map(([label, value]) => `<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join("");
  if (!reports.length) {
    $("financeReportTable").innerHTML = '<div class="empty">No annual online finance report data found for this symbol</div>';
    return;
  }
  $("financeReportTable").innerHTML = `
    <table class="holdings-table compact-report-table">
      <thead>
        <tr>
          <th>Fiscal date</th>
          <th>Revenue</th>
          <th>Revenue growth</th>
          <th>Net income</th>
          <th>Net income growth</th>
          <th>Net margin</th>
          <th>Free cash flow</th>
          <th>Debt</th>
        </tr>
      </thead>
      <tbody>
        ${reports.map((row) => `
          <tr>
            <td data-label="Fiscal date">${esc(formatDate(row.fiscal_date))}</td>
            <td data-label="Revenue">${fmt(row.revenue, 0)}</td>
            <td data-label="Revenue growth">${pct(row.revenue_growth_percent)}</td>
            <td data-label="Net income">${fmt(row.net_income, 0)}</td>
            <td data-label="Net income growth">${pct(row.net_income_growth_percent)}</td>
            <td data-label="Net margin">${pct(row.net_margin_percent)}</td>
            <td data-label="Free cash flow">${fmt(row.free_cash_flow, 0)}</td>
            <td data-label="Debt">${fmt(row.long_term_debt, 0)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>`;
}

function renderCompanyOutlookHistory(data) {
  state.companyOutlookHistory = data.items || [];
  const scorecard = data.scorecard || {};
  const qualityGate = scorecard.quality_gate || {};
  $("companyOutlookScorecard").innerHTML = [
    ["Predictions", scorecard.total || 0],
    ["Evaluated", scorecard.evaluated || 0],
    ["Pending", scorecard.pending || 0],
    ["Accuracy", scorecard.accuracy_percent == null ? "Not evaluated" : pct(scorecard.accuracy_percent)],
    ["Validation", qualityGate.passed ? "75% target met" : "Not validated"],
  ].map(([label, value]) => `<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join("");
  $("companyOutlookHistory").innerHTML = state.companyOutlookHistory.length ? state.companyOutlookHistory.map((item) => {
    const direction = item.actual_direction || "pending";
    const stateLabel = direction === "pending" ? "Pending" : direction.charAt(0).toUpperCase() + direction.slice(1);
    return `
      <article class="stack-item management-item outlook-history-item">
        <header class="outlook-history-head">
          <div class="outlook-history-identity">
            <b>${esc(item.symbol)} · ${fmt(item.score, 0)}/100</b>
            <span class="outlook-history-label">${esc(item.label || "Mixed")}</span>
          </div>
          <span class="outlook-history-state ${esc(direction)}">${esc(stateLabel)}</span>
        </header>
        <div class="outlook-history-meta">
          <span><small>Created</small><b>${esc(formatDate(String(item.created_at || "").slice(0, 10)))}</b></span>
          <span><small>Evaluate after</small><b>${esc(formatDate(item.horizon_date))}</b></span>
          <span><small>Confidence</small><b>${esc(item.confidence || "Low")}</b></span>
        </div>
        <p class="outlook-history-thesis">${esc(item.thesis || "No report-backed summary was stored for this prediction.")}</p>
        ${direction === "pending" ? "" : `<p class="outlook-history-evaluation">${item.accuracy_score == null ? esc(item.evaluation || "Inconclusive") : `Accuracy ${fmt(item.accuracy_score, 0)}% · ${esc(item.evaluation || "")}`}</p>`}
        <footer class="row-actions outlook-history-actions">
          ${direction === "pending" ? `<button class="secondary compact-button" type="button" data-evaluate-company-outlook="${esc(item.id)}">Evaluate next report</button>` : ""}
          <button class="secondary compact-button" type="button" data-delete-company-outlook="${esc(item.id)}" data-prediction-symbol="${esc(item.symbol)}">Remove</button>
        </footer>
      </article>
    `;
  }).join("") : '<div class="empty">No saved company predictions yet</div>';
}

async function loadCompanyOutlookHistory(symbol = "") {
  const query = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
  const data = await api(`/api/company-outlook/predictions${query}`);
  renderCompanyOutlookHistory(data);
}

let companyOutlookDiagramSequence = 0;

function renderCompanyOutlookDiagramFallback(outlook) {
  const graph = outlook.graph || {};
  const nodes = graph.nodes || [];
  const labels = Object.fromEntries(nodes.map((node) => [node.id, node.label || node.id]));
  const edges = graph.edges || [];
  return `
    <div class="outlook-map-fallback">
      <div class="outlook-map-nodes">
        ${nodes.map((node) => `<span class="outlook-map-node ${esc(node.type || "")}">${esc(node.label || node.id)}</span>`).join("")}
      </div>
      <div class="outlook-map-relations">
        ${edges.length ? edges.map((edge) => `<span><b>${esc(labels[edge.from] || edge.from)}</b> → ${esc(edge.label || "related to")} → <b>${esc(labels[edge.to] || edge.to)}</b></span>`).join("") : "<span>No report-backed relationships were available.</span>"}
      </div>
    </div>
  `;
}

async function renderCompanyOutlookDiagram(outlook) {
  const diagram = $("companyOutlookDiagram");
  diagram.innerHTML = "";
  if (!outlook.mermaid) {
    diagram.innerHTML = renderCompanyOutlookDiagramFallback(outlook);
    return;
  }
  if (!window.mermaid) {
    diagram.innerHTML = renderCompanyOutlookDiagramFallback(outlook);
    return;
  }
  try {
    window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "dark" });
    companyOutlookDiagramSequence += 1;
    const rendered = await window.mermaid.render(`companyOutlookMap${companyOutlookDiagramSequence}`, outlook.mermaid);
    diagram.innerHTML = rendered.svg;
    rendered.bindFunctions?.(diagram);
  } catch (error) {
    diagram.innerHTML = renderCompanyOutlookDiagramFallback(outlook);
    $("companyOutlookStatus").textContent = "Analysis loaded · Relationship map shown as a list";
    appWarn("company_outlook.diagram_fallback", { message: error?.message || "Diagram render failed" });
  }
}

function renderCompanyOutlook(outlook) {
  state.companyOutlook = outlook;
  $("companyOutlookEmpty").hidden = true;
  $("companyOutlookResults").hidden = false;
  const industry = outlook.industry || {};
  const components = outlook.score_components || {};
  $("companyOutlookStatus").textContent = `${outlook.symbol} · ${outlook.label || "Mixed"} · ${outlook.confidence || "Low"} confidence · ${outlook.peer_source || ""}`;
  $("companyOutlookSummary").innerHTML = [
    ["Final score", `${fmt(outlook.score, 0)}/100`],
    ["Peer rank", `${outlook.rank || 1}/${(outlook.companies || []).length || 1}`],
    ["Industry", industry.health || "Not available"],
    ["Industry score", `${fmt(industry.score, 0)}/25`],
    ["Company signals", `${fmt(components.company_fundamentals, 0)}/45`],
    ["Related effect", `${fmt(components.related_industry_effect, 0)}/15`],
  ].map(([label, value]) => `<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join("");
  $("companyOutlookWords").innerHTML = `
    <p>${esc(outlook.simple_words || "")}</p>
    ${outlook.missing?.length ? `<div class="sub">Missing or limited: ${esc(outlook.missing.join(", "))}</div>` : ""}
  `;
  const companies = outlook.companies || [];
  $("companyOutlookTable").innerHTML = companies.length ? `
    <table class="holdings-table compact-report-table outlook-table">
      <thead><tr><th>Company</th><th>Industry</th><th>Fiscal date</th><th>Revenue growth</th><th>Operating margin</th><th>Net margin</th><th>FCF margin</th><th>Current ratio</th><th>Score</th></tr></thead>
      <tbody>${companies.map((company) => `
        <tr>
          <td data-label="Company"><b>${esc(company.symbol)}</b><div class="sub">${esc(company.name || "")}</div></td>
          <td data-label="Industry">${esc(company.industry || "Not available")}</td>
          <td data-label="Fiscal date">${esc(formatDate(company.fiscal_date))}</td>
          <td data-label="Revenue growth">${pct(company.revenue_growth_percent)}</td>
          <td data-label="Operating margin">${pct(company.operating_margin_percent)}</td>
          <td data-label="Net margin">${pct(company.net_margin_percent)}</td>
          <td data-label="FCF margin">${pct(company.free_cash_flow_margin_percent)}</td>
          <td data-label="Current ratio">${fmt(company.current_ratio, 2)}</td>
          <td data-label="Score">${company.symbol === outlook.symbol ? `${fmt(outlook.score, 0)}/100` : `${fmt(company.score, 0)}/32`}</td>
        </tr>
      `).join("")}</tbody>
    </table>
  ` : '<div class="empty">No company report data was available for this analysis</div>';
  renderCompanyOutlookDiagram(outlook);
}

function setCompanyOutlookBusy(mode = "") {
  const active = Boolean(mode);
  const analyzeButton = $("runCompanyOutlook");
  const backtestButton = $("runCompanyOutlookBacktest");
  analyzeButton.disabled = active;
  backtestButton.disabled = active;
  analyzeButton.classList.toggle("is-working", mode === "analyze");
  backtestButton.classList.toggle("is-working", mode === "backtest");
  analyzeButton.textContent = mode === "analyze" ? "Analyzing reports" : "Analyze and save";
  backtestButton.textContent = mode === "backtest" ? "Running backtest" : "Run backtest";
  $("companyOutlookWorkbench").setAttribute("aria-busy", String(active));
}

async function loadCompanyOutlook() {
  const symbol = cleanSecuritySymbol(valueOf("outlookSymbol"));
  $("outlookSymbol").value = symbol;
  if (!symbol) {
    $("companyOutlookStatus").textContent = "Enter a target ticker symbol";
    $("outlookSymbol").setAttribute("aria-invalid", "true");
    $("outlookSymbol").focus();
    return;
  }
  $("outlookSymbol").removeAttribute("aria-invalid");
  $("companyOutlookStatus").textContent = "Reading company and industry reports";
  const peers = valueOf("outlookPeers").split(",").map((item) => cleanSecuritySymbol(item)).filter(Boolean);
  const relatedCompanies = valueOf("outlookRelated").split(",").map((item) => cleanSecuritySymbol(item)).filter(Boolean);
  setCompanyOutlookBusy("analyze");
  try {
    const outlook = await api(`/api/company-outlook/${encodeURIComponent(symbol)}`, {
      method: "POST",
      body: JSON.stringify({
        peers,
        industry: valueOf("outlookIndustry"),
        related_companies: relatedCompanies,
        related_effect: valueOf("outlookRelatedEffect"),
        horizon_months: Number(valueOf("outlookHorizon")) || 12,
        save_prediction: true,
      }),
    });
    renderCompanyOutlook(outlook);
    await loadCompanyOutlookHistory(symbol);
  } finally {
    setCompanyOutlookBusy();
  }
}

async function loadCompanyOutlookBacktest() {
  const symbol = cleanSecuritySymbol(valueOf("outlookSymbol"));
  const asOfDate = dateValue("outlookAsOfDate");
  $("outlookSymbol").value = symbol;
  if (!symbol || !asOfDate) {
    $("companyOutlookStatus").textContent = "Enter a target ticker and historical backtest date";
    if (!symbol) {
      $("outlookSymbol").setAttribute("aria-invalid", "true");
      $("outlookSymbol").focus();
    } else {
      $("outlookAsOfDate").setAttribute("aria-invalid", "true");
      $("outlookAsOfDate").focus();
    }
    return;
  }
  $("outlookSymbol").removeAttribute("aria-invalid");
  $("outlookAsOfDate").removeAttribute("aria-invalid");
  $("companyOutlookStatus").textContent = "Running historical report backtest";
  const peers = valueOf("outlookPeers").split(",").map((item) => cleanSecuritySymbol(item)).filter(Boolean);
  const relatedCompanies = valueOf("outlookRelated").split(",").map((item) => cleanSecuritySymbol(item)).filter(Boolean);
  setCompanyOutlookBusy("backtest");
  try {
    const result = await api(`/api/company-outlook/${encodeURIComponent(symbol)}/backtest`, {
      method: "POST",
      body: JSON.stringify({
        peers,
        industry: valueOf("outlookIndustry"),
        related_companies: relatedCompanies,
        related_effect: valueOf("outlookRelatedEffect"),
        horizon_months: Number(valueOf("outlookHorizon")) || 12,
        as_of_date: asOfDate,
      }),
    });
    renderCompanyOutlook(result.analysis || {});
    const evaluation = result.evaluation || {};
    const actual = evaluation.actual_direction || "pending";
    $("companyOutlookStatus").textContent = evaluation.accuracy_score == null
      ? `Backtest from ${formatDate(result.as_of_date)}: ${actual}. ${evaluation.evaluation || ""}`
      : `Backtest from ${formatDate(result.as_of_date)}: prediction accuracy ${fmt(evaluation.accuracy_score, 0)}% (${actual}).`;
    await loadCompanyOutlookHistory(symbol);
  } finally {
    setCompanyOutlookBusy();
  }
}

async function evaluateCompanyOutlookPrediction(predictionId) {
  const result = await api(`/api/company-outlook/predictions/${encodeURIComponent(predictionId)}/evaluate`, { method: "POST", body: "{}" });
  $("companyOutlookStatus").textContent = result.actual_direction === "pending" ? "No newer annual report is available for that prediction yet" : `Prediction evaluated: ${result.actual_direction}`;
  await loadCompanyOutlookHistory(valueOf("outlookSymbol"));
}

async function deleteCompanyOutlookPrediction(predictionId, symbol) {
  if (!confirm(`Remove the saved ${symbol || "company"} prediction? This cannot be undone.`)) return;
  await api(`/api/company-outlook/predictions/${encodeURIComponent(predictionId)}`, { method: "DELETE" });
  $("companyOutlookStatus").textContent = `${symbol || "Company"} prediction removed`;
  await loadCompanyOutlookHistory(valueOf("outlookSymbol"));
}

async function loadFinanceReport() {
  const symbol = cleanSecuritySymbol(valueOf("financeReportSymbol"));
  $("financeReportSymbol").value = symbol;
  if (!symbol) {
    $("financeReportStatus").textContent = "Enter a ticker symbol";
    return;
  }
  $("financeReportStatus").textContent = "Fetching online finance report";
  const report = await api(`/api/finance-reports/${encodeURIComponent(symbol)}`);
  renderFinanceReport(report);
}

function renderHistorySnapshots() {
  $("historyList").innerHTML = state.historySnapshots.length ? state.historySnapshots.map((snapshot) => `
    <div class="stack-item management-item">
      <b>${esc(formatDate(snapshot.snapshot_date))} · ${esc(cleanSourceLabel(snapshot.account_label) || snapshot.account_db_id)}</b>
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
    date_from: clampedHistoryDate(dateValue("reportFrom")),
    date_to: dateValue("reportTo"),
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
      snapshot_date: clampedHistoryDate(dateValue("historyDate") || todayString()),
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
    body: JSON.stringify({ snapshot_date: clampedHistoryDate(dateValue("historyDate") || todayString()) }),
  });
  $("historyStatus").textContent = `Captured ${result.snapshots} account history points for ${formatDate(result.date)}`;
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
    date_from: clampedHistoryDate(dateValue("reportFrom")),
    date_to: dateValue("reportTo"),
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
  refreshFundAccountSelects();
  renderFundsOverview();
  rerenderPortfolioIfLoaded();
  renderPensionSimulatorControls();
  $("fundsList").innerHTML = state.localFunds.length ? state.localFunds.map((fund) => {
    const hasMonthlyEstimate = fund.kind === "Pension" && fund.monthly_estimate !== null && fund.monthly_estimate !== undefined;
    const estimate = hasMonthlyEstimate
      ? `<span>Saved ${fmt(fund.amount, 0)} · Monthly pension estimate ${fmt(fund.monthly_estimate, 0)}</span>`
      : `<span>Saved ${fmt(fund.amount, 0)} · <em class="muted-inline">Monthly pension estimate N/A</em></span>`;
    const accountText = fund.account_label ? ` · Account ${esc(fund.account_label)}` : "";
    const historyChange = Number(fund.history_change || 0);
    const historyText = Number(fund.history_points || 0) > 1
      ? `Progress ${historyChange > 0 ? "+" : ""}${fmt(historyChange, 0)} (${historyChange > 0 ? "+" : ""}${pct(fund.history_change_percent)}) since ${formatDate(fund.history_first_date)}`
      : `${fmt(fund.history_points || 0, 0)} saved history point`;
    return `
      <div class="stack-item management-item">
        <b>${esc([fund.kind, fund.fund_name || "", fund.pension_id].filter(Boolean).join(" · "))}</b>
        ${estimate}
        <button class="secondary compact-button" type="button" data-fund-history="${esc(fund.id)}">History</button>
        <button class="secondary compact-button" type="button" data-edit-fund="${esc(fund.id)}">Edit</button>
        <button class="secondary compact-button" type="button" data-delete-fund="${esc(fund.id)}">Remove</button>
        <div class="sub">${esc(historyText)}${fund.history_latest_date ? ` · Updated ${esc(formatDate(fund.history_latest_date))}` : ""} · ${(fund.persons || []).length ? `${(fund.persons || []).map(personLabel).map(esc).join(" · ")} · ` : ""}${esc(fund.comments || "No comments")}${accountText}</div>
      </div>
    `;
  }).join("") : '<div class="empty">No pension, provident, or savings funds yet</div>';
  renderPersonLists();
}

function resetFundHistoryForm() {
  state.editingFundHistoryId = "";
  $("fundHistoryDate").value = formatDate(todayString());
  $("fundHistoryAmount").value = "";
  $("fundHistoryComments").value = "";
  $("fundHistoryFormTitle").textContent = "Add saved amount";
  $("saveFundHistory").textContent = "Add history point";
  $("cancelFundHistoryEdit").hidden = true;
}

function renderFundAmountHistory(data) {
  const fund = data.fund || state.localFunds.find((item) => item.id === state.fundHistoryFundId) || {};
  const items = [...(data.items || [])].sort((left, right) => String(left.amount_date).localeCompare(String(right.amount_date)));
  state.fundAmountHistory = items;
  const first = items[0];
  const latest = items.at(-1);
  const change = first && latest ? Number(latest.amount || 0) - Number(first.amount || 0) : 0;
  const changePercent = first && Number(first.amount || 0) ? change / Math.abs(Number(first.amount)) * 100 : null;
  $("fundHistorySubtitle").textContent = `${[fund.kind, fund.fund_name, fund.pension_id].filter(Boolean).join(" · ")} · The latest dated balance is used as the current saved amount.`;
  $("fundHistorySummary").innerHTML = [
    ["Current saved amount", latest ? fmt(latest.amount, 0) : fmt(fund.amount, 0)],
    ["Total progress", items.length > 1 ? `${change > 0 ? "+" : ""}${fmt(change, 0)}` : "Not enough history"],
    ["Progress %", items.length > 1 ? `${changePercent > 0 ? "+" : ""}${pct(changePercent)}` : "Not enough history"],
    ["History points", items.length],
  ].map(([label, value]) => `<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join("");

  if (!items.length) {
    $("fundHistoryChart").innerHTML = '<div class="empty">Add the first dated amount to start tracking progress</div>';
  } else {
    const width = 900;
    const height = 260;
    const padLeft = 66;
    const padRight = 28;
    const padTop = 32;
    const padBottom = 46;
    const values = items.map((item) => Number(item.amount || 0));
    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values);
    const padding = Math.max((rawMax - rawMin) * 0.15, rawMax * 0.03, 1);
    const minValue = Math.max(0, rawMin - padding);
    const maxValue = rawMax + padding;
    const plotWidth = width - padLeft - padRight;
    const plotHeight = height - padTop - padBottom;
    const pointX = (index) => items.length === 1 ? padLeft + plotWidth / 2 : padLeft + (index / (items.length - 1)) * plotWidth;
    const pointY = (amount) => padTop + (1 - (Number(amount) - minValue) / (maxValue - minValue || 1)) * plotHeight;
    const line = items.map((item, index) => `${index ? "L" : "M"} ${pointX(index)} ${pointY(item.amount)}`).join(" ");
    const area = `${line} L ${pointX(items.length - 1)} ${padTop + plotHeight} L ${pointX(0)} ${padTop + plotHeight} Z`;
    const points = items.map((item, index) => `
      <circle cx="${pointX(index)}" cy="${pointY(item.amount)}" r="5">
        <title>${esc(`${formatDate(item.amount_date)} · Saved ${fmt(item.amount, 0)}`)}</title>
      </circle>
    `).join("");
    const dateLabels = items.length === 1
      ? `<text x="${padLeft + plotWidth / 2}" y="${height - 12}" text-anchor="middle">${esc(formatDate(first.amount_date))}</text>`
      : `<text x="${padLeft}" y="${height - 12}">${esc(formatDate(first.amount_date))}</text><text x="${padLeft + plotWidth}" y="${height - 12}" text-anchor="end">${esc(formatDate(latest.amount_date))}</text>`;
    $("fundHistoryChart").innerHTML = `
      <div class="chart-header">
        <div>
          <div class="chart-title">Saved amount progress</div>
          <small class="chart-subtitle">Each point is a balance entered for that date.</small>
        </div>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Saved amount progress over time">
        <line x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${padTop + plotHeight}"></line>
        <line x1="${padLeft}" y1="${padTop + plotHeight}" x2="${padLeft + plotWidth}" y2="${padTop + plotHeight}"></line>
        <text x="8" y="${padTop + 5}">${fmt(maxValue, 0)}</text>
        <text x="8" y="${padTop + plotHeight}">${fmt(minValue, 0)}</text>
        <path class="fund-history-area" d="${area}"></path>
        <path class="fund-history-line" d="${line}"></path>
        ${points}
        ${dateLabels}
      </svg>`;
  }

  $("fundHistoryRows").innerHTML = items.length ? [...items].reverse().map((item, reverseIndex) => {
    const index = items.length - 1 - reverseIndex;
    const previous = index > 0 ? items[index - 1] : null;
    const delta = previous ? Number(item.amount || 0) - Number(previous.amount || 0) : null;
    return `<tr>
      <td data-label="Date">${esc(formatDate(item.amount_date))}</td>
      <td data-label="Saved amount"><b>${fmt(item.amount, 0)}</b></td>
      <td data-label="Change" class="${delta > 0 ? "positive" : delta < 0 ? "negative" : ""}">${delta === null ? "Opening" : `${delta > 0 ? "+" : ""}${fmt(delta, 0)}`}</td>
      <td data-label="Comments">${esc(item.comments || cleanSourceLabel(item.source) || "—")}</td>
      <td data-label="Actions"><div class="row-actions"><button class="secondary compact-button" type="button" data-edit-fund-history="${esc(item.id)}">Edit</button><button class="secondary compact-button" type="button" data-delete-fund-history="${esc(item.id)}">Delete</button></div></td>
    </tr>`;
  }).join("") : '<tr><td colspan="5" class="empty-cell">No saved amount history yet</td></tr>';
}

async function loadFundAmountHistory() {
  if (!state.fundHistoryFundId) return;
  const data = await api(`/api/local/funds/${encodeURIComponent(state.fundHistoryFundId)}/amount-history`);
  renderFundAmountHistory(data);
}

async function openFundAmountHistory(fundId) {
  const fund = state.localFunds.find((item) => item.id === fundId);
  if (!fund) return;
  state.fundHistoryFundId = fund.id;
  resetFundHistoryForm();
  $("fundHistoryStatus").textContent = "Loading saved amounts";
  openModal("fundHistoryModal");
  await loadFundAmountHistory();
  $("fundHistoryStatus").textContent = "";
}

function editFundAmountHistory(historyId) {
  const item = state.fundAmountHistory.find((row) => row.id === historyId);
  if (!item) return;
  state.editingFundHistoryId = item.id;
  $("fundHistoryDate").value = formatDate(item.amount_date);
  $("fundHistoryAmount").value = item.amount;
  $("fundHistoryComments").value = item.comments || "";
  $("fundHistoryFormTitle").textContent = "Edit saved amount";
  $("saveFundHistory").textContent = "Update history point";
  $("cancelFundHistoryEdit").hidden = false;
  $("fundHistoryStatus").textContent = `Editing ${formatDate(item.amount_date)}`;
}

async function saveFundAmountHistory() {
  const amount = Number(valueOf("fundHistoryAmount") || 0);
  const amountDate = dateValue("fundHistoryDate");
  if (!amountDate) {
    $("fundHistoryStatus").textContent = "Date is required";
    return;
  }
  if (amount <= 0) {
    $("fundHistoryStatus").textContent = "Saved amount must be greater than zero";
    return;
  }
  const editingId = state.editingFundHistoryId;
  const path = editingId
    ? `/api/local/funds/${encodeURIComponent(state.fundHistoryFundId)}/amount-history/${encodeURIComponent(editingId)}`
    : `/api/local/funds/${encodeURIComponent(state.fundHistoryFundId)}/amount-history`;
  await api(path, {
    method: editingId ? "PUT" : "POST",
    body: JSON.stringify({ amount_date: amountDate, amount, comments: valueOf("fundHistoryComments") }),
  });
  resetFundHistoryForm();
  $("fundHistoryStatus").textContent = editingId ? "History point updated" : "History point added";
  await Promise.all([loadFundAmountHistory(), loadFunds(), loadReports()]);
}

async function deleteFundAmountHistory(historyId) {
  if (!confirm("Delete this saved amount from the fund history?")) return;
  await api(`/api/local/funds/${encodeURIComponent(state.fundHistoryFundId)}/amount-history/${encodeURIComponent(historyId)}`, { method: "DELETE" });
  if (state.editingFundHistoryId === historyId) resetFundHistoryForm();
  $("fundHistoryStatus").textContent = "History point deleted";
  await Promise.all([loadFundAmountHistory(), loadFunds(), loadReports()]);
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
  return `${personFullName(person)} · ${formatDate(person.birth_date)}${age ? ` · age ${fmt(age, 1)}` : ""}`;
}

function addPersonTo(listKey, nameId, birthDateId, statusId) {
  const name = valueOf(nameId);
  const birthDate = dateValue(birthDateId);
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
  renderPersonList("editAccountPersons", state.editAccountPersons, "data-delete-edit-person");
  renderPersonList("fundPersons", state.fundPersons, "data-delete-fund-person");
  renderPersonList("editFundPersons", state.editFundPersons, "data-delete-edit-fund-person");
}

function renderPensionSimulatorControls() {
  renderSimulationPersonOptions();
  renderPensionInsuranceControls();
  renderPensionPeriods();
  renderPensionRates();
  renderPensionScenarios();
  renderPensionSimulationResults();
  renderPensionProjectionSummary();
  syncSimulationFactorState();
  syncPensionPeriodFromMode();
  syncPensionRateFromMode();
  syncScenarioDerivedFields();
  updatePensionActionStates();
}

function coverageOptionsHtml(values, selected, emptyLabel = "No coverage") {
  const current = selected === undefined || selected === null ? "" : String(selected);
  return `<option value=""${current === "" ? " selected" : ""}>${esc(emptyLabel)}</option>` + values.map((value) => (
    `<option value="${esc(value)}"${String(value) === current ? " selected" : ""}>${esc(value)}%</option>`
  )).join("");
}

function renderPensionInsuranceControls() {
  const disability = $("simDisabilityCoverage");
  const spouse = $("simSpouseSurvivorsCoverage");
  const children = $("simChildrenSurvivorsCoverage");
  if (!disability || !spouse || !children) return;
  disability.innerHTML = coverageOptionsHtml(DISABILITY_COVERAGE_OPTIONS, disability.value);
  spouse.innerHTML = coverageOptionsHtml(SPOUSE_SURVIVORS_OPTIONS, spouse.value);
  children.innerHTML = coverageOptionsHtml(CHILDREN_SURVIVORS_OPTIONS, children.value);
  syncPensionInsuranceTrack({ force: true });
}

function syncPensionInsuranceTrack({ force = false } = {}) {
  const trackId = valueOf("simInsuranceTrack") || "comprehensive";
  const track = PENSION_INSURANCE_TRACKS[trackId];
  if (!track || trackId === "custom") return;
  const fields = [
    ["simDisabilityCoverage", track.disability],
    ["simSpouseSurvivorsCoverage", track.spouse],
    ["simChildrenSurvivorsCoverage", track.children],
  ];
  fields.forEach(([id, value]) => {
    const input = $(id);
    if (input && (force || input.value === "")) input.value = String(value);
  });
  const factor = $("simSurvivorsFactor");
  if (factor && !factor.value) factor.value = "200";
}

function pensionInsuranceTrackFor(period) {
  const disability = Number(period?.disability_coverage_percent ?? 0);
  const spouse = Number(period?.spouse_survivors_coverage_percent ?? 0);
  const children = Number(period?.children_survivors_coverage_percent ?? 0);
  const match = Object.entries(PENSION_INSURANCE_TRACKS).find(([, track]) => (
    track.disability === disability && track.spouse === spouse && track.children === children
  ));
  return match?.[0] || "custom";
}

function syncSimulationFactorState() {
  const factorInput = $("simFactor");
  if (!factorInput) return;
  factorInput.disabled = false;
  factorInput.classList.remove("muted-control");
  factorInput.placeholder = "Payout factor";
  factorInput.title = "Pension payout factor";
  if (!factorInput.value) factorInput.value = "200";
}

function renderSimulationPersonOptions() {
  const select = $("simPersonSource");
  if (!select) return;
  const current = select.value;
  const people = state.familyMembers;
  select.innerHTML = '<option value="">Choose person</option>' + people.map((person, index) => (
    `<option value="${index}">${esc(personLabel(person))}</option>`
  )).join("");
  select.value = [...select.options].some((option) => option.value === current) ? current : (people.length === 1 ? "0" : "");
  if (select.value) applySimulationPerson();
}

function selectedSimulationPerson() {
  const people = state.familyMembers;
  const raw = valueOf("simPersonSource");
  if (raw === "") return null;
  const index = Number(raw);
  return Number.isInteger(index) ? people[index] : null;
}

function sameSimulationPerson(left, right) {
  if (!left || !right) return false;
  const leftMember = String(left.member_id || left.id || "").trim();
  const rightMember = String(right.member_id || right.id || "").trim();
  if (leftMember && rightMember) return leftMember === rightMember;
  const leftBirth = parseDateInput(left.birth_date || "");
  const rightBirth = parseDateInput(right.birth_date || "");
  if (!leftBirth || leftBirth !== rightBirth) return false;
  const leftName = personFullName(left).toLowerCase();
  const rightName = personFullName(right).toLowerCase();
  if (leftName === rightName) return true;
  return [leftName, rightName].some((name) => /^person \d+$/.test(name) || name === "family member");
}

function scenarioPerson(scenario) {
  const raw = scenario?.person_index;
  if (raw !== "" && raw !== undefined && raw !== null) {
    const index = Number(raw);
    if (Number.isInteger(index) && state.familyMembers[index]) return state.familyMembers[index];
  }
  return state.familyMembers.find((person) => sameSimulationPerson(person, {
    name: scenario?.person_name,
    birth_date: scenario?.birth_date,
  })) || null;
}

function scenarioGender(scenario) {
  return String(scenario?.gender || scenarioPerson(scenario)?.gender || "").trim();
}

function scenarioInsuranceSex(scenario) {
  const text = scenarioGender(scenario).toLowerCase();
  if (["male", "m", "man", "זכר", "גבר"].includes(text)) return "male";
  if (["female", "f", "woman", "נקבה", "אישה", "אשה"].includes(text)) return "female";
  return "";
}

function scenarioNeedsGenderForInsurance(scenario) {
  const rows = scenario?.income_periods || [];
  const hasInsurance = rows.some((period) => (
    Number(period?.disability_coverage_percent || 0) > 0
    || Number(period?.spouse_survivors_coverage_percent || 0) > 0
    || Number(period?.children_survivors_coverage_percent || 0) > 0
  ));
  return hasInsurance && !scenarioInsuranceSex(scenario);
}

function pensionSimulationPayloadScenarios() {
  return state.pensionScenarios.map((scenario) => ({
    ...scenario,
    gender: scenarioInsuranceSex(scenario) || scenarioGender(scenario),
  }));
}

function simulationFundsForPerson(person, kind = "Pension") {
  if (!person) return [];
  return state.localFunds.filter((fund) => {
    if ((fund.kind || "Pension") !== kind) return false;
    return (fund.persons || []).some((fundPerson) => sameSimulationPerson(person, fundPerson));
  });
}

function simulationPersonAmount(person, kind = "Pension") {
  return sum(simulationFundsForPerson(person, kind).map((fund) => Number(fund.amount || 0)));
}

function applySimulationPersonAmount() {
  const person = selectedSimulationPerson();
  if (!person) return;
  const amount = simulationPersonAmount(person, "Pension");
  $("simAmount").value = amount || "";
}

function syncScenarioDerivedFields() {
  document.querySelectorAll(".scenario-internal-field").forEach((node) => {
    node.hidden = true;
  });
}

function applySimulationPerson() {
  const person = selectedSimulationPerson();
  if (person) {
    setDateField("simBirthDate", person.birth_date || "");
    $("simCurrentAge").value = ageFromBirthDate(person.birth_date);
    if (person.retire_age) $("simRetireAge").value = person.retire_age;
    applySimulationPersonAmount();
  }
  syncScenarioDerivedFields();
}

function syncPensionPeriodFromMode() {
  const custom = valueOf("simPeriodFromMode") === "custom";
  const input = $("simPeriodFrom");
  if (!input) return;
  input.hidden = !custom;
  if (!custom) input.value = "";
}

function syncPensionRateFromMode() {
  const custom = valueOf("simRateFromMode") === "custom";
  const input = $("simRateFrom");
  if (!input) return;
  input.hidden = !custom;
  if (!custom) input.value = "";
}

function pensionPeriodSummary() {
  const scenario = activePensionScenario();
  const rows = scenario?.income_periods || [];
  if (!scenario) return "No scenario selected";
  if (!rows.length) return "No salary rows";
  return `${rows.length} salary row${rows.length === 1 ? "" : "s"}`;
}

function renderPensionProjectionSummary() {
  const frame = $("pensionProjectionSummary");
  if (!frame) return;
  const scenario = activePensionScenario();
  frame.innerHTML = `
    <span><b>Selected scenario</b>${esc(scenario?.name || "None")}</span>
    <span><b>Saved scenarios</b>${esc(state.pensionScenarios.length)}</span>
    <span><b>Profit rates</b>${esc(scenario?.return_periods?.length || 0)}</span>
  `;
}

function activePensionScenario() {
  const index = state.activePensionScenarioIndex;
  return Number.isInteger(index) && state.pensionScenarios[index] ? state.pensionScenarios[index] : null;
}

function selectedPensionScenarioRows() {
  const scenario = activePensionScenario();
  return scenario?.income_periods || [];
}

function selectedPensionReturnRows() {
  const scenario = activePensionScenario();
  return scenario?.return_periods || [];
}

function projectionFormValid() {
  const person = selectedSimulationPerson();
  const currentAge = numberValue("simCurrentAge") || ageFromBirthDate(dateValue("simBirthDate"));
  const retireAge = numberValue("simRetireAge");
  const factor = numberValue("simFactor") || 200;
  return Boolean(person)
    && Boolean(valueOf("simName"))
    && Number.isFinite(Number(currentAge))
    && Number(currentAge) > 0
    && Number.isFinite(Number(retireAge))
    && Number(retireAge) > Number(currentAge)
    && Number.isFinite(Number(factor))
    && Number(factor) > 0;
}

function pensionPeriodFormValid() {
  const scenario = activePensionScenario();
  if (!scenario) return false;
  const fromAge = valueOf("simPeriodFromMode") === "now" ? scenario.current_age : numberValue("simPeriodFrom");
  const toAge = numberValue("simPeriodTo");
  const income = numberValue("simPeriodIncome") || 0;
  const contribution = numberValue("simPeriodContribution") || 0;
  const deposit = numberValue("simPeriodDeposit") || 0;
  const spouse = numberValue("simSpouseSurvivorsCoverage") || 0;
  const children = numberValue("simChildrenSurvivorsCoverage") || 0;
  const survivorsFactor = numberValue("simSurvivorsFactor");
  const hasContribution = (income > 0 && contribution > 0) || deposit > 0;
  return Number.isFinite(Number(fromAge))
    && Number.isFinite(Number(toAge))
    && Number(toAge) > Number(fromAge)
    && hasContribution
    && (!(spouse > 0 || children > 0) || (Number.isFinite(Number(survivorsFactor)) && Number(survivorsFactor) > 0));
}

function pensionRateFormValid() {
  const scenario = activePensionScenario();
  if (!scenario) return false;
  const fromAge = valueOf("simRateFromMode") === "now" ? scenario.current_age : numberValue("simRateFrom");
  const toAge = numberValue("simRateTo");
  const annualReturn = numberValue("simRateAnnual");
  return Number.isFinite(Number(fromAge))
    && Number.isFinite(Number(toAge))
    && Number(toAge) > Number(fromAge)
    && annualReturn !== ""
    && Number.isFinite(Number(annualReturn));
}

function scenarioHasProfitRates(scenario) {
  return Array.isArray(scenario?.return_periods)
    && scenario.return_periods.some((period) => (
      Number(period?.to_age) > Number(period?.from_age)
      && period?.annual_return !== ""
      && period?.annual_return !== null
      && period?.annual_return !== undefined
      && Number.isFinite(Number(period.annual_return))
    ));
}

function pensionScenarioKey() {
  return JSON.stringify(state.pensionScenarios.map((scenario) => ({
    name: scenario.name,
    kind: scenario.kind,
    gender: scenarioInsuranceSex(scenario) || scenarioGender(scenario),
    current_age: scenario.current_age,
    retire_age: scenario.retire_age,
    amount: scenario.amount,
    factor: scenario.factor,
    income_periods: scenario.income_periods || [],
    return_periods: scenario.return_periods || [],
  })));
}

function schedulePensionSimulationAutoRun() {
  const key = pensionScenarioKey();
  if (!key || key === state.pensionSimulationKey || key === state.pensionSimulationAutoRunningKey || key === state.pensionSimulationErrorKey) return;
  state.pensionSimulationAutoRunningKey = key;
  setTimeout(() => {
    if (state.pensionSimulationAutoRunningKey !== key || key !== pensionScenarioKey()) return;
    runPensionSimulation({ silent: true }).catch((error) => {
      state.pensionSimulationAutoRunningKey = "";
      state.pensionSimulationErrorKey = key;
      state.pensionSimulationError = error.message;
      $("pensionSimulationStatus").textContent = `Error: ${error.message}`;
      savePensionSimulationState();
      renderPensionSimulationResults();
      renderFundsOverview();
    });
  }, 0);
}

function savePensionSimulationState() {
  try {
    localStorage.setItem(PENSION_SIMULATION_STORAGE_KEY, JSON.stringify({
      scenarios: state.pensionScenarios,
      results: state.pensionSimulationResults,
      grid: state.pensionSimulationGrid,
      key: state.pensionSimulationKey,
      errorKey: state.pensionSimulationErrorKey,
      error: state.pensionSimulationError,
      activeIndex: state.activePensionScenarioIndex,
    }));
    scheduleClientStateSync();
  } catch (error) {
    appWarn("pension.storage.save_failed", { message: error.message });
  }
}

function loadPensionSimulationState() {
  try {
    const raw = localStorage.getItem(PENSION_SIMULATION_STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    state.pensionScenarios = Array.isArray(saved.scenarios) ? saved.scenarios : [];
    state.activePensionScenarioIndex = Number.isInteger(saved.activeIndex) && state.pensionScenarios[saved.activeIndex]
      ? saved.activeIndex
      : null;
    const key = pensionScenarioKey();
    if (saved.errorKey && saved.errorKey === key) {
      state.pensionSimulationErrorKey = saved.errorKey;
      state.pensionSimulationError = saved.error || "";
    }
    if (saved.key && saved.key === key && Array.isArray(saved.results)) {
      state.pensionSimulationResults = saved.results;
      state.pensionSimulationGrid = saved.grid || { baseScenarios: state.pensionScenarios };
      state.pensionSimulationKey = saved.key;
    }
  } catch (error) {
    appWarn("pension.storage.load_failed", { message: error.message });
  }
}

function updatePensionActionStates() {
  const hasActiveScenario = Boolean(activePensionScenario());
  const projectionButton = $("addPensionScenario");
  if (projectionButton) {
    projectionButton.disabled = !projectionFormValid();
    projectionButton.textContent = hasActiveScenario ? "Update scenario" : "Add scenario";
  }
  const periodButton = $("addPensionPeriod");
  if (periodButton) periodButton.disabled = !pensionPeriodFormValid();
  const rateButton = $("addPensionRate");
  if (rateButton) rateButton.disabled = !pensionRateFormValid();
  const stopButton = $("pensionStopWorkNow");
  if (stopButton) stopButton.disabled = !hasActiveScenario;
  const runButton = $("runPensionSimulation");
  if (runButton) runButton.disabled = !state.pensionScenarios.length || state.pensionScenarios.some((scenario) => !scenarioHasProfitRates(scenario));
}

function resetPensionPeriodForm() {
  ["simPeriodFrom", "simPeriodTo", "simPeriodIncome", "simPeriodContribution", "simPeriodDeposit"].forEach((id) => {
    const input = $(id);
    if (input) input.value = "";
  });
  const mode = $("simPeriodFromMode");
  if (mode) mode.value = "now";
  const track = $("simInsuranceTrack");
  if (track) track.value = "comprehensive";
  syncPensionInsuranceTrack({ force: true });
  const factor = $("simSurvivorsFactor");
  if (factor) factor.value = "200";
  syncPensionPeriodFromMode();
  updatePensionActionStates();
}

function resetPensionRateForm() {
  ["simRateFrom", "simRateTo", "simRateAnnual"].forEach((id) => {
    const input = $(id);
    if (input) input.value = "";
  });
  const mode = $("simRateFromMode");
  if (mode) mode.value = "now";
  syncPensionRateFromMode();
  updatePensionActionStates();
}

function openPensionPeriodModal(index = state.activePensionScenarioIndex) {
  if (Number.isInteger(index) && state.pensionScenarios[index]) {
    state.activePensionScenarioIndex = index;
  }
  const scenario = activePensionScenario();
  if (!scenario) {
    $("pensionProjectionStatus").textContent = "Add or edit a scenario before adding salary rows";
    return;
  }
  resetPensionPeriodForm();
  const name = $("pensionPeriodProjectionName");
  if (name) name.textContent = scenario.name;
  const status = $("pensionPeriodStatus");
  if (status) status.textContent = "";
  renderPensionScenarios();
  renderPensionPeriods();
  renderPensionRates();
  openModal("pensionPeriodModal");
}

function currentPensionScenario() {
  const person = selectedSimulationPerson();
  const birthDate = dateValue("simBirthDate") || person?.birth_date || "";
  const kind = "Pension";
  const personAmount = simulationPersonAmount(person, kind);
  const existing = activePensionScenario();
  return {
    name: valueOf("simName"),
    kind,
    birth_date: birthDate,
    gender: person?.gender || "",
    person_name: person?.name || "",
    person_index: valueOf("simPersonSource"),
    current_age: numberValue("simCurrentAge") || ageFromBirthDate(birthDate),
    retire_age: numberValue("simRetireAge") || person?.retire_age,
    amount: personAmount || numberValue("simAmount") || 0,
    annual_return: 0,
    monthly_income: 0,
    contribution_percent: 0,
    monthly_deposit: 0,
    factor: numberValue("simFactor") || 200,
    income_periods: (existing?.income_periods || []).map((period) => ({ ...period })),
    return_periods: (existing?.return_periods || []).map((period) => ({ ...period })),
  };
}

function pensionPeriodCoverageSelect(index, field, values, selected) {
  return `<select data-pension-period-index="${index}" data-pension-period-field="${esc(field)}">${coverageOptionsHtml(values, selected)}</select>`;
}

function pensionPeriodTrackSelect(index, period) {
  const selected = period?.insurance_track || pensionInsuranceTrackFor(period);
  return `
    <select data-pension-period-index="${index}" data-pension-period-field="insurance_track">
      ${Object.entries(PENSION_INSURANCE_TRACKS).map(([id, track]) => (
        `<option value="${esc(id)}"${id === selected ? " selected" : ""}>${esc(track.label)}</option>`
      )).join("")}
    </select>
  `;
}

function renderPensionPeriods() {
  const frame = $("pensionPeriodRows");
  if (!frame) return;
  const scenario = activePensionScenario();
  const rows = selectedPensionScenarioRows();
  if (!scenario) {
    frame.innerHTML = '<div class="empty compact-empty">Choose a scenario before adding salary rows</div>';
    renderPensionProjectionSummary();
    updatePensionActionStates();
    return;
  }
  frame.innerHTML = rows.length ? `
    <table class="projection-table pension-period-table">
      <thead>
        <tr>
          <th>From Age</th>
          <th>To Age</th>
          <th>Monthly Salary</th>
          <th>Pension Deposit %</th>
          <th>Extra Deposit</th>
          <th>Insurance Track</th>
          <th>Disability</th>
          <th>Spouse Survivors</th>
          <th>Children Survivors</th>
          <th>Survivors Factor</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${rows.map((period, index) => `
          <tr>
            <td><input data-pension-period-index="${index}" data-pension-period-field="from_age" type="number" min="0" step="0.1" value="${esc(period.from_age ?? "")}" /></td>
            <td><input data-pension-period-index="${index}" data-pension-period-field="to_age" type="number" min="0" step="0.1" value="${esc(period.to_age ?? "")}" /></td>
            <td><input data-pension-period-index="${index}" data-pension-period-field="monthly_income" type="number" min="0" step="0.01" value="${esc(period.monthly_income ?? 0)}" /></td>
            <td><input data-pension-period-index="${index}" data-pension-period-field="contribution_percent" type="number" min="0" step="0.01" value="${esc(period.contribution_percent ?? 0)}" /></td>
            <td><input data-pension-period-index="${index}" data-pension-period-field="monthly_deposit" type="number" min="0" step="0.01" value="${esc(period.monthly_deposit ?? 0)}" /></td>
            <td>${pensionPeriodTrackSelect(index, period)}</td>
            <td>${pensionPeriodCoverageSelect(index, "disability_coverage_percent", DISABILITY_COVERAGE_OPTIONS, period.disability_coverage_percent)}</td>
            <td>${pensionPeriodCoverageSelect(index, "spouse_survivors_coverage_percent", SPOUSE_SURVIVORS_OPTIONS, period.spouse_survivors_coverage_percent)}</td>
            <td>${pensionPeriodCoverageSelect(index, "children_survivors_coverage_percent", CHILDREN_SURVIVORS_OPTIONS, period.children_survivors_coverage_percent)}</td>
            <td><input data-pension-period-index="${index}" data-pension-period-field="survivors_capitalization_factor" type="number" min="1" step="0.01" value="${esc(period.survivors_capitalization_factor ?? 200)}" /></td>
            <td><button class="secondary compact-button" type="button" data-delete-pension-period="${index}">Remove</button></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  ` : '<div class="empty compact-empty">No salary rows for the selected scenario</div>';
  renderPensionProjectionSummary();
  updatePensionActionStates();
}

function renderPensionRates() {
  const frame = $("pensionRateRows");
  if (!frame) return;
  const scenario = activePensionScenario();
  const rows = selectedPensionReturnRows();
  if (!scenario) {
    frame.innerHTML = '<div class="empty compact-empty">Choose a scenario before adding profit rates</div>';
    updatePensionActionStates();
    return;
  }
  frame.innerHTML = rows.length ? `
    <table class="projection-table">
      <thead>
        <tr>
          <th>From Age</th>
          <th>To Age</th>
          <th>Annual Profit %</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${rows.map((period, index) => `
          <tr>
            <td><input data-pension-rate-index="${index}" data-pension-rate-field="from_age" type="number" min="0" step="0.1" value="${esc(period.from_age ?? "")}" /></td>
            <td><input data-pension-rate-index="${index}" data-pension-rate-field="to_age" type="number" min="0" step="0.1" value="${esc(period.to_age ?? "")}" /></td>
            <td><input data-pension-rate-index="${index}" data-pension-rate-field="annual_return" type="number" step="0.01" value="${esc(period.annual_return ?? 0)}" /></td>
            <td><button class="secondary compact-button" type="button" data-delete-pension-rate="${index}">Remove</button></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  ` : '<div class="empty compact-empty">No profit rate rows. Scenario uses 0% annual profit unless rates are added.</div>';
  updatePensionActionStates();
}

function renderPensionScenarios() {
  const frame = $("pensionScenarios");
  if (!frame) return;
  frame.innerHTML = state.pensionScenarios.length ? `
    <div class="projection-table-wrap">
      <table class="projection-table pension-scenario-table">
        <thead>
          <tr>
            <th>Scenario</th>
            <th>Person</th>
            <th>Age Range</th>
            <th>Pension Total</th>
            <th>Salary Rows</th>
            <th>Profit Rates</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${state.pensionScenarios.map((scenario, index) => `
            <tr class="${state.activePensionScenarioIndex === index ? "selected-row" : ""}">
              <td><b>${esc(scenario.name)}</b></td>
              <td>${esc(scenario.person_name || "Manual")}</td>
              <td>${fmt(scenario.current_age, 1)} to ${fmt(scenario.retire_age, 1)}</td>
              <td>${money(scenario.amount, state.baseCurrency, 0)}</td>
              <td>${esc(scenario.income_periods?.length || 0)}</td>
              <td>${esc(scenario.return_periods?.length || 0)}</td>
              <td class="row-actions">
                <button class="secondary compact-button" type="button" data-edit-pension-scenario="${index}">Edit</button>
                <button class="secondary compact-button" type="button" data-schedule-pension-scenario="${index}">Salary schedule</button>
                <button class="secondary compact-button" type="button" data-delete-pension-scenario="${index}">Remove</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  ` : '<div class="empty compact-empty">No pension scenarios saved yet</div>';
  renderPensionProjectionSummary();
  updatePensionActionStates();
}

function renderPensionSimulationResults() {
  const frame = $("pensionSimulationResults");
  if (!frame) return;
  const grid = state.pensionSimulationGrid;
  if (!state.pensionSimulationResults.length || !grid) {
    frame.innerHTML = '<div class="empty compact-empty">Run scenarios to create the pension simulation table</div>';
    return;
  }
  const rows = grid.baseScenarios || [];
  frame.innerHTML = `
    <div class="projection-result-wrap">
      <table class="projection-result-table">
        <thead>
          <tr>
            <th>Scenario</th>
            <th>Profit Rates</th>
            <th>Monthly Pension</th>
            <th>Final Amount</th>
            <th>Deposits</th>
            <th>Insurance Cost</th>
            <th>Profit</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((scenario, rowIndex) => {
            const result = state.pensionSimulationResults[rowIndex] || {};
            return `
              <tr>
                <td>
                  <b>${esc(scenario.name)}</b>
                  <small>${esc(scenario.kind)} · Age ${fmt(scenario.current_age, 1)}-${fmt(scenario.retire_age, 1)} · ${scenario.income_periods?.length || 0} salary rows</small>
                </td>
                <td>${esc(scenario.return_periods?.length || 0)}</td>
                <td><b>${money(result.monthly_pension || 0, state.baseCurrency, 0)}</b></td>
                <td>${money(result.final_amount || 0, state.baseCurrency, 0)}</td>
                <td>${money(result.total_deposits || 0, state.baseCurrency, 0)}</td>
                <td>${money(result.total_insurance_cost || 0, state.baseCurrency, 0)}</td>
                <td>${money(result.investment_gain || 0, state.baseCurrency, 0)}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function invalidatePensionSimulation() {
  state.pensionSimulationResults = [];
  state.pensionSimulationGrid = null;
  state.pensionSimulationKey = "";
  state.pensionSimulationAutoRunningKey = "";
  state.pensionSimulationErrorKey = "";
  state.pensionSimulationError = "";
  savePensionSimulationState();
  renderPensionSimulationResults();
}

function editPensionScenario(index) {
  const scenario = state.pensionScenarios[index];
  if (!scenario) return;
  state.activePensionScenarioIndex = index;
  $("simPersonSource").value = scenario.person_index ?? "";
  $("simName").value = scenario.name || "";
  setDateField("simBirthDate", scenario.birth_date || "");
  $("simCurrentAge").value = scenario.current_age || "";
  $("simRetireAge").value = scenario.retire_age || "";
  $("simAmount").value = scenario.amount || "";
  $("simFactor").value = scenario.factor || 200;
  $("pensionProjectionStatus").textContent = `Editing ${scenario.name}`;
  syncScenarioDerivedFields();
  savePensionSimulationState();
  renderPensionScenarios();
  renderPensionPeriods();
  renderPensionRates();
}

function newPensionScenario() {
  state.activePensionScenarioIndex = null;
  ["simName", "simBirthDate", "simCurrentAge", "simRetireAge", "simAmount"].forEach((id) => { $(id).value = ""; });
  $("simFactor").value = "200";
  const people = state.familyMembers || [];
  $("simPersonSource").value = people.length === 1 ? "0" : "";
  if ($("simPersonSource").value) applySimulationPerson();
  syncScenarioDerivedFields();
  $("pensionProjectionStatus").textContent = "New pension scenario";
  savePensionSimulationState();
  renderPensionScenarios();
  renderPensionPeriods();
  renderPensionRates();
  updatePensionActionStates();
}

function addPensionPeriod() {
  const scenario = activePensionScenario();
  if (!scenario) {
    $("pensionPeriodStatus").textContent = "Add or edit a pension scenario first";
    updatePensionActionStates();
    return;
  }
  const fromAge = valueOf("simPeriodFromMode") === "now" ? scenario.current_age : numberValue("simPeriodFrom");
  const period = {
    from_age: fromAge,
    to_age: numberValue("simPeriodTo"),
    monthly_income: numberValue("simPeriodIncome") || 0,
    contribution_percent: numberValue("simPeriodContribution") || 0,
    monthly_deposit: numberValue("simPeriodDeposit") || 0,
    insurance_track: valueOf("simInsuranceTrack") || "comprehensive",
    disability_coverage_percent: numberValue("simDisabilityCoverage") || 0,
    spouse_survivors_coverage_percent: numberValue("simSpouseSurvivorsCoverage") || 0,
    children_survivors_coverage_percent: numberValue("simChildrenSurvivorsCoverage") || 0,
    survivors_capitalization_factor: numberValue("simSurvivorsFactor") || 200,
  };
  if (!pensionPeriodFormValid()) {
    $("pensionPeriodStatus").textContent = "Fill To Age, deposit fields, and survivors factor when survivors coverage is selected";
    return;
  }
  scenario.income_periods = [...(scenario.income_periods || []), period];
  invalidatePensionSimulation();
  $("pensionPeriodStatus").textContent = "Salary row added";
  resetPensionPeriodForm();
  renderPensionScenarios();
  renderPensionPeriods();
  renderFundsOverview();
}

function addPensionRate() {
  const scenario = activePensionScenario();
  if (!scenario) {
    $("pensionPeriodStatus").textContent = "Add or edit a pension scenario first";
    updatePensionActionStates();
    return;
  }
  const fromAge = valueOf("simRateFromMode") === "now" ? scenario.current_age : numberValue("simRateFrom");
  const period = {
    from_age: fromAge,
    to_age: numberValue("simRateTo"),
    annual_return: numberValue("simRateAnnual"),
  };
  if (!pensionRateFormValid()) {
    $("pensionPeriodStatus").textContent = "Fill To Age and Annual Profit %";
    return;
  }
  scenario.return_periods = [...(scenario.return_periods || []), period];
  invalidatePensionSimulation();
  $("pensionPeriodStatus").textContent = "Profit rate row added";
  resetPensionRateForm();
  renderPensionScenarios();
  renderPensionRates();
  renderFundsOverview();
}

function stopPensionWorkNow() {
  const scenario = activePensionScenario();
  if (!scenario) {
    $("pensionProjectionStatus").textContent = "Add or edit a pension scenario first";
    return;
  }
  const currentAge = scenario.current_age || 0;
  const retireAge = scenario.retire_age || currentAge;
  scenario.income_periods = currentAge && retireAge > currentAge
    ? [{ from_age: currentAge, to_age: retireAge, monthly_income: 0, contribution_percent: 0, monthly_deposit: 0 }]
    : [];
  invalidatePensionSimulation();
  $("pensionPeriodStatus").textContent = "Scenario set to no future salary deposits";
  renderPensionScenarios();
  renderPensionPeriods();
  renderPensionRates();
}

function addPensionScenario() {
  if (!projectionFormValid()) {
    $("pensionSimulationStatus").textContent = "Fill scenario name, age range, and payout factor";
    updatePensionActionStates();
    return;
  }
  const scenario = currentPensionScenario();
  if (activePensionScenario()) {
    state.pensionScenarios[state.activePensionScenarioIndex] = scenario;
    $("pensionSimulationStatus").textContent = "Scenario updated";
  } else {
    state.pensionScenarios.push(scenario);
    state.activePensionScenarioIndex = state.pensionScenarios.length - 1;
    $("pensionSimulationStatus").textContent = "Scenario added";
  }
  invalidatePensionSimulation();
  renderPensionScenarios();
  renderPensionPeriods();
  renderPensionRates();
  renderFundsOverview();
  if (state.activePensionScenarioIndex !== null) openPensionPeriodModal(state.activePensionScenarioIndex);
}

async function runPensionSimulation({ silent = false } = {}) {
  const baseScenarios = pensionSimulationPayloadScenarios();
  if (!baseScenarios.length || baseScenarios.some((scenario) => !scenario.current_age || !scenario.retire_age || scenario.retire_age <= scenario.current_age)) {
    if (!silent) $("pensionSimulationStatus").textContent = "Add at least one valid pension scenario before running";
    renderPensionSimulationResults();
    return;
  }
  if (baseScenarios.some((scenario) => !scenarioHasProfitRates(scenario))) {
    if (!silent) $("pensionSimulationStatus").textContent = "Add at least one profit rate row for every scenario before running";
    renderPensionSimulationResults();
    return;
  }
  if (state.pensionScenarios.some((scenario) => scenarioNeedsGenderForInsurance(scenario))) {
    const message = "Set Male/Female gender before running scenarios with pension insurance coverage";
    if (!silent) $("pensionSimulationStatus").textContent = message;
    state.pensionSimulationErrorKey = pensionScenarioKey();
    state.pensionSimulationError = message;
    savePensionSimulationState();
    renderPensionSimulationResults();
    renderFundsOverview();
    return;
  }
  const key = pensionScenarioKey();
  state.pensionSimulationAutoRunningKey = silent ? state.pensionSimulationAutoRunningKey : "";
  state.pensionSimulationErrorKey = "";
  state.pensionSimulationError = "";
  let data;
  try {
    data = await api("/api/local/pension-simulate", {
      method: "POST",
      body: JSON.stringify({ scenarios: baseScenarios }),
    });
  } catch (error) {
    const message = error.message || "Pension simulation failed";
    state.pensionSimulationAutoRunningKey = "";
    state.pensionSimulationErrorKey = key;
    state.pensionSimulationError = message;
    savePensionSimulationState();
    if (!silent) $("pensionSimulationStatus").textContent = `Error: ${message}`;
    renderPensionSimulationResults();
    renderFundsOverview();
    return;
  }
  state.pensionSimulationResults = data.results || [];
  state.pensionSimulationGrid = { baseScenarios };
  state.pensionSimulationKey = key;
  state.pensionSimulationAutoRunningKey = "";
  state.pensionSimulationErrorKey = "";
  state.pensionSimulationError = "";
  savePensionSimulationState();
  if (!silent) $("pensionSimulationStatus").textContent = `${baseScenarios.length} scenario${baseScenarios.length === 1 ? "" : "s"} calculated`;
  renderPensionSimulationResults();
  renderFundsOverview();
}

function clearFundCreateForm() {
  ["fundName", "fundPensionId", "fundAmount", "fundAccount", "fundComments", "fundFamilyMember"].forEach((id) => { $(id).value = ""; });
  state.fundPersons = [];
  renderPersonLists();
  updateFundActionStates();
}

function updateFundActionStates() {
  const button = $("saveFund");
  if (!button) return;
  button.disabled = !valueOf("fundPensionId") || Number(valueOf("fundAmount") || 0) <= 0;
}

function showFundCreate() {
  $("fundCreateSection").hidden = false;
  $("fundStatus").textContent = "";
  updateFundActionStates();
}

function hideFundCreate({ clear = false } = {}) {
  $("fundCreateSection").hidden = true;
  if (clear) clearFundCreateForm();
}

async function saveFund() {
  if (!valueOf("fundPensionId")) {
    $("fundStatus").textContent = "Fund ID is required";
    return;
  }
  if (Number(valueOf("fundAmount") || 0) <= 0) {
    $("fundStatus").textContent = "Saved amount is required";
    return;
  }
  await api("/api/local/funds", {
    method: "POST",
    body: JSON.stringify({
      kind: valueOf("fundKind"),
      fund_name: valueOf("fundName"),
      pension_id: valueOf("fundPensionId"),
      amount: valueOf("fundAmount"),
      account_id: valueOf("fundAccount"),
      persons: state.fundPersons.map((person) => ({ ...person })),
      comments: valueOf("fundComments"),
    }),
  });
  $("fundStatus").textContent = "Fund saved";
  hideFundCreate({ clear: true });
  await loadFunds();
}

function editFund(fundId) {
  const fund = state.localFunds.find((item) => item.id === fundId);
  if (!fund) return;
  state.editingFundId = fund.id;
  $("editFundKind").value = fund.kind || "Pension";
  $("editFundName").value = fund.fund_name || "";
  $("editFundPensionId").value = fund.pension_id || "";
  $("editFundAmount").value = fund.amount || "";
  refreshFundAccountSelects();
  $("editFundAccount").value = fund.account_id || "";
  $("editFundComments").value = fund.comments || "";
  $("editFundFamilyMember").value = "";
  state.editFundPersons = (fund.persons || []).map((person) => ({ ...person }));
  $("editFundStatus").textContent = [fund.kind, fund.fund_name, fund.pension_id].filter(Boolean).join(" · ");
  renderPersonLists();
  openModal("fundEditModal");
}

async function saveEditFund() {
  const fund = state.localFunds.find((item) => item.id === state.editingFundId);
  if (!fund) {
    $("editFundStatus").textContent = "Choose a fund to edit";
    return;
  }
  if (!valueOf("editFundPensionId")) {
    $("editFundStatus").textContent = "Fund ID is required";
    return;
  }
  if (Number(valueOf("editFundAmount") || 0) <= 0) {
    $("editFundStatus").textContent = "Saved amount is required";
    return;
  }
  await api("/api/local/funds", {
    method: "POST",
    body: JSON.stringify({
      id: fund.id,
      kind: valueOf("editFundKind"),
      fund_name: valueOf("editFundName"),
      pension_id: valueOf("editFundPensionId"),
      amount: valueOf("editFundAmount"),
      account_id: valueOf("editFundAccount"),
      persons: state.editFundPersons.map((person) => ({ ...person })),
      comments: valueOf("editFundComments"),
    }),
  });
  $("fundStatus").textContent = "Fund updated";
  $("editFundStatus").textContent = "Fund updated";
  closeModal($("fundEditModal"));
  state.editingFundId = "";
  state.editFundPersons = [];
  await loadFunds();
  await loadReports();
}

async function loadPortfolio({ refresh = false } = {}) {
  $("status").textContent = refresh ? "Refreshing analytics" : "Preparing dashboard";
  setLoading(true, refresh ? "Refreshing portfolio analytics" : "Loading portfolio analytics");
  appLog("portfolio.load.start", { refresh });
  try {
    const trendParams = new URLSearchParams({
      date_from: HISTORY_START_DATE,
      date_to: todayString(),
    });
    const portfolioPath = refresh ? "/api/portfolio?refresh=true" : "/api/portfolio";
    const [data, trend, fxData, accountData, transactionData] = await Promise.all([
      api(portfolioPath),
      api(`/api/local/account-trends?${trendParams}`),
      api("/api/fx").catch(() => ({ quotes: [] })),
      api("/api/local/accounts"),
      api("/api/local/securities"),
    ]);
    setCoreFxRates(fxData);
    state.localAccounts = accountData.items || [];
    state.localTransactions = transactionData.items || [];
    const allItems = data.items || [];
    state.items = portfolioItems(allItems);
    state.portfolioReady = true;
    state.accountTrend = {
      ...trend,
      accounts: (trend.accounts || []).filter((entry) => !isEquityCompAccount(entry.account)),
    };
    populateOptions(state.items);
    $("status").textContent = `${state.items.length} portfolio positions · ${Object.entries(data.status).map(([k, v]) => `${k}: ${v}`).join(", ")}`;
    renderPortfolio(state.items);
    appLog("portfolio.load.done", {
      count: state.items.length,
      equity_comp_positions_excluded: allItems.length - state.items.length,
      status: data.status,
      trend_accounts: state.accountTrend.accounts.length,
    });
    if (!data.count) {
      appWarn("portfolio.empty", {
        local_accounts: state.localAccounts.length,
        message: "Portfolio has no local position transactions. Use Accounts > Sync import to import positions.",
      });
    }
  } finally {
    setLoading(false);
  }
}

async function loadLocalOptions() {
  try {
    state.localOptions = await api("/api/local/options");
  } catch {
    state.localOptions = {
      account_types: ["Investment", "Long-Term Savings", "Bank", "ESOP"],
      fund_kinds: ["Pension", "Provident Fund", "Savings Fund"],
      asset_classes: ["EQUITY", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE", "RSU", "EMPLOYEE_STOCK_OPTION", "PRIVATE_STOCK", "STOCK_OPTION"],
      instrument_types: ["STOCK", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE", "RSU", "EMPLOYEE_STOCK_OPTION", "PRIVATE_STOCK", "STOCK_OPTION"],
      option_types: ["CALL", "PUT"],
      issuer_listing_statuses: ["PRIVATE", "PUBLIC"],
    };
  }
  populateStaticOptions();
}

async function applyFilter() {
  $("status").textContent = "Applying portfolio filter";
  setLoading(true, "Applying portfolio filter");
  try {
    const data = await api("/api/screener", { method: "POST", body: JSON.stringify(criteriaFromForm()) });
    state.items = portfolioItems(data.items || []);
    $("status").textContent = `${state.items.length} portfolio positions matched`;
    renderPortfolio(state.items);
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
  scheduleClientStateSync();
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
  state.bannerFxRates = items.reduce((rates, item) => {
    if (item.type === "fx" && item.value) rates[item.symbol] = Number(item.value);
    return rates;
  }, {});
  updateFxRates();
  if (state.items.length) renderPortfolio(state.items);
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

function alertMetric(metricKey) {
  return (state.alertOptions.metrics || []).find((item) => item.key === metricKey) || {
    key: metricKey,
    label: metricKey.replaceAll("_", " "),
    unit: "",
    digits: 2,
  };
}

function alertMetricValue(metricKey, value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "Data unavailable";
  const metric = alertMetric(metricKey);
  const amount = fmt(value, Number(metric.digits ?? 2));
  if (metric.unit === "%") return `${amount}%`;
  if (metric.unit === "×") return `${amount}×`;
  if (metric.unit === "ratio") return amount;
  return metric.unit ? `${amount} ${metric.unit}` : amount;
}

function alertMetricOptions(selected = "") {
  const groups = (state.alertOptions.metrics || []).reduce((result, metric) => {
    const group = metric.group || "Financials";
    (result[group] ||= []).push(metric);
    return result;
  }, {});
  if (!Object.keys(groups).length) return '<option value="">Loading metrics</option>';
  return Object.entries(groups).map(([group, metrics]) => `
    <optgroup label="${esc(group)}">
      ${metrics.map((metric) => `<option value="${esc(metric.key)}"${metric.key === selected ? " selected" : ""}>${esc(metric.label)}${metric.unit ? ` (${esc(metric.unit)})` : ""}</option>`).join("")}
    </optgroup>
  `).join("");
}

function readAlertConditions() {
  return [...document.querySelectorAll("[data-alert-condition]")].map((row) => ({
    metric: row.querySelector("[data-alert-condition-metric]")?.value || "",
    operator: row.querySelector("[data-alert-condition-operator]")?.value || ">",
    value: row.querySelector("[data-alert-condition-value]")?.value ?? "",
  }));
}

function renderAlertConditions() {
  const operatorOptions = state.alertOptions.operators || [];
  $("alertConditions").innerHTML = state.alertConditions.map((condition, index) => `
    <div class="signal-condition-row" data-alert-condition="${index}">
      <label><span>Financial measure</span><select data-alert-condition-metric>${alertMetricOptions(condition.metric)}</select></label>
      <label><span>Comparison</span><select data-alert-condition-operator>${operatorOptions.map((operator) => `<option value="${esc(operator.key)}"${operator.key === condition.operator ? " selected" : ""}>${esc(operator.label)}</option>`).join("")}</select></label>
      <label><span>Value</span><input data-alert-condition-value type="number" step="any" value="${esc(condition.value)}" inputmode="decimal" /></label>
      <button class="icon-button signal-remove-condition" type="button" data-remove-alert-condition="${index}" aria-label="Remove condition" title="Remove condition">×</button>
    </div>
  `).join("");
}

function resetAlertForm() {
  state.editingAlertId = "";
  state.alertConditions = [{ metric: "dividend_yield_percent", operator: ">", value: 2.5 }];
  $("alertName").value = "";
  $("alertSignal").value = "buy";
  $("alertMatchMode").value = "all";
  $("alertEnabled").checked = true;
  $("saveAlert").textContent = "Save rule";
  $("cancelAlertEdit").hidden = true;
  renderAlertConditions();
}

function addAlertCondition() {
  state.alertConditions = readAlertConditions();
  if (state.alertConditions.length >= 12) {
    $("alertStatus").textContent = "A rule can contain up to 12 conditions.";
    return;
  }
  const defaultMetrics = ["profit_market_cap_percent", "revenue_growth_percent", "price_earnings_ratio"];
  const used = new Set(state.alertConditions.map((condition) => condition.metric));
  const metric = defaultMetrics.find((key) => !used.has(key)) || state.alertOptions.metrics?.[0]?.key || "dividend_yield_percent";
  state.alertConditions.push({ metric, operator: ">", value: "" });
  renderAlertConditions();
  $("alertConditions").querySelector("[data-alert-condition]:last-child [data-alert-condition-value]")?.focus();
}

function removeAlertCondition(index) {
  state.alertConditions = readAlertConditions();
  state.alertConditions.splice(index, 1);
  renderAlertConditions();
}

function alertConditionText(condition) {
  const metric = alertMetric(condition.metric);
  return `${metric.label} ${condition.operator} ${alertMetricValue(condition.metric, condition.value)}`;
}

function alertReasonText(reason) {
  const metric = alertMetric(reason.metric);
  return `${metric.label}: ${alertMetricValue(reason.metric, reason.value)} ${reason.operator} ${alertMetricValue(reason.metric, reason.threshold)}`;
}

function renderAlerts(data) {
  state.alertData = data;
  state.alertOptions = data.options || state.alertOptions;
  if (!state.alertConditions.length) resetAlertForm();
  else renderAlertConditions();

  const rules = data.rules || [];
  const signals = data.active_signals || [];
  const runs = data.runs || [];
  $("alertActiveSummary").textContent = fmt(signals.length, 0);
  $("alertRuleSummary").textContent = `${rules.filter((rule) => rule.enabled).length} of ${rules.length}`;
  $("alertScheduleSummary").textContent = data.schedule?.next_run ? formatDateTime(data.schedule.next_run) : "Not scheduled";
  $("alertRunSummary").textContent = runs[0]?.run_at
    ? `${runs[0].status === "failed" ? "Failed · " : ""}${formatDateTime(runs[0].run_at)}`
    : "Not run";

  $("alertsSignals").innerHTML = signals.length ? signals.map((signal) => {
    const signalType = ["buy", "sell", "watch"].includes(signal.signal) ? signal.signal : "watch";
    const reasons = (signal.reasons || []).map((reason) => `<li>${esc(alertReasonText(reason))}</li>`).join("");
    const missing = (signal.missing || []).filter(Boolean);
    const missingRuleMetrics = (signal.missing_metrics || []).map((metric) => alertMetric(metric).label);
    return `<article class="signal-card signal-match-card signal-${esc(signalType)}">
      <div class="signal-card-head">
        <div><span class="signal-badge">${esc(signalType)} signal</span><h5>${esc(signal.symbol)} <small>${esc(signal.name || "")}</small></h5></div>
        <span class="signal-time">${esc(formatDateTime(signal.matched_at))}</span>
      </div>
      <p class="signal-rule-name">Matched “${esc(signal.rule_name || "Rule")}”</p>
      ${reasons ? `<ul class="signal-reasons">${reasons}</ul>` : ""}
      ${missingRuleMetrics.length ? `<p class="signal-missing">Rule data unavailable: ${esc(missingRuleMetrics.join(", "))}</p>` : ""}
      ${missing.length ? `<p class="signal-missing">Some provider data is unavailable: ${esc(missing.join(", "))}</p>` : ""}
      <div class="signal-card-actions">
        <button type="button" data-investigate-signal="${esc(signal.symbol)}">Investigate &amp; score</button>
      </div>
    </article>`;
  }).join("") : '<div class="empty signal-empty">No current matches. Run the rules now or wait for the next daily check.</div>';

  $("alertsList").innerHTML = rules.length ? rules.map((rule) => {
    const conditions = rule.conditions || [];
    const joiner = rule.match_mode === "any" ? " OR " : " AND ";
    const conditionText = conditions.length ? conditions.map(alertConditionText).join(joiner) : "This older rule needs a condition before it can run.";
    const matchCount = (rule.last_matches || []).length;
    return `<article class="signal-card saved-rule-card${rule.enabled ? "" : " is-disabled"}">
      <div class="signal-card-head">
        <div><span class="signal-badge signal-${esc(rule.signal || "watch")}">${esc(rule.signal || "watch")}</span><h5>${esc(rule.name)}</h5></div>
        <span class="rule-state">${rule.enabled ? "Daily" : "Paused"}</span>
      </div>
      <p>${esc(conditionText)}</p>
      <div class="signal-rule-meta"><span>${esc(rule.last_status || "Not run")}</span><span>${matchCount} current match${matchCount === 1 ? "" : "es"}</span></div>
      <div class="signal-card-actions">
        <button class="secondary compact-button" type="button" data-edit-alert="${esc(rule.id)}">Edit</button>
        <button class="secondary compact-button" type="button" data-toggle-alert="${esc(rule.id)}">${rule.enabled ? "Pause" : "Enable"}</button>
        <button class="danger compact-button" type="button" data-delete-alert="${esc(rule.id)}">Remove</button>
      </div>
    </article>`;
  }).join("") : '<div class="empty signal-empty">No saved rules. The example above starts with dividend yield &gt; 2.5%.</div>';

  $("alertRunHistory").innerHTML = runs.length ? runs.slice(0, 12).map((run) => {
    const providerErrors = run.metadata?.provider_errors?.length || 0;
    return `<article class="signal-card signal-run-card${run.status === "failed" ? " is-failed" : ""}">
      <div class="signal-card-head"><h5>${esc(formatDateTime(run.run_at))}</h5><span class="run-state">${esc(run.status || "completed")}</span></div>
      ${run.error ? `<p class="signal-missing">${esc(run.error)}</p>` : ""}
      <div class="signal-run-stats"><span><b>${fmt(run.evaluated_symbols || 0, 0)}</b> stocks checked</span><span><b>${fmt(run.matched_signals || 0, 0)}</b> matches</span><span><b>${fmt(providerErrors, 0)}</b> data errors</span></div>
    </article>`;
  }).join("") : '<div class="empty signal-empty">No run history yet.</div>';
}

async function loadAlerts() {
  const data = await api("/api/alerts");
  renderAlerts(data);
}

async function saveAlert() {
  const conditions = readAlertConditions();
  const payload = {
    name: $("alertName").value.trim() || "Daily portfolio rule",
    enabled: $("alertEnabled").checked,
    signal: $("alertSignal").value,
    match_mode: $("alertMatchMode").value,
    conditions,
    notification: { channels: ["dashboard"] },
  };
  $("saveAlert").disabled = true;
  $("alertStatus").textContent = state.editingAlertId ? "Updating rule…" : "Saving rule…";
  try {
    await api(state.editingAlertId ? `/api/alerts/${encodeURIComponent(state.editingAlertId)}` : "/api/alerts", {
      method: state.editingAlertId ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    resetAlertForm();
    $("alertStatus").textContent = "Rule saved. It will run during the daily check.";
    await loadAlerts();
  } catch (error) {
    $("alertStatus").textContent = `Error: ${error.message}`;
  } finally {
    $("saveAlert").disabled = false;
  }
}

function editAlertRule(ruleId) {
  const rule = (state.alertData?.rules || []).find((item) => item.id === ruleId);
  if (!rule) return;
  state.editingAlertId = rule.id;
  state.alertConditions = (rule.conditions || []).map((condition) => ({ ...condition }));
  $("alertName").value = rule.name || "";
  $("alertSignal").value = rule.signal || "watch";
  $("alertMatchMode").value = rule.match_mode || "all";
  $("alertEnabled").checked = Boolean(rule.enabled);
  $("saveAlert").textContent = "Update rule";
  $("cancelAlertEdit").hidden = false;
  $("alertStatus").textContent = `Editing “${rule.name}”`;
  renderAlertConditions();
  $("signalRuleBuilderTitle").scrollIntoView({ behavior: "smooth", block: "start" });
  $("alertName").focus({ preventScroll: true });
}

async function toggleAlertRule(ruleId) {
  const rule = (state.alertData?.rules || []).find((item) => item.id === ruleId);
  if (!rule) return;
  await api(`/api/alerts/${encodeURIComponent(ruleId)}`, {
    method: "PUT",
    body: JSON.stringify({
      name: rule.name,
      enabled: !rule.enabled,
      signal: rule.signal,
      match_mode: rule.match_mode,
      conditions: rule.conditions,
      notification: rule.notification,
    }),
  });
  $("alertStatus").textContent = rule.enabled ? "Rule paused." : "Rule enabled.";
  await loadAlerts();
}

async function deleteAlertRule(ruleId) {
  const rule = (state.alertData?.rules || []).find((item) => item.id === ruleId);
  if (!rule || !window.confirm(`Remove the rule “${rule.name}”?`)) return;
  await api(`/api/alerts/${encodeURIComponent(ruleId)}`, { method: "DELETE" });
  if (state.editingAlertId === ruleId) resetAlertForm();
  $("alertStatus").textContent = "Rule removed.";
  await loadAlerts();
}

async function investigateAlertSignal(symbol) {
  setResearchSection("outlook");
  $("outlookSymbol").value = cleanSecuritySymbol(symbol);
  $("companyOutlookStatus").textContent = `Investigating ${cleanSecuritySymbol(symbol)} using company reports…`;
  $("researchOutlookPanel").scrollIntoView({ block: "start" });
  await loadCompanyOutlook();
}

async function runAlerts() {
  state.alertConditions = readAlertConditions();
  $("runAlerts").disabled = true;
  $("alertStatus").textContent = "Checking portfolio stocks against the enabled rules…";
  try {
    const result = await api("/api/alerts/run", { method: "POST", body: "{}" });
    renderAlerts(result.state);
    const latestRun = result.state?.runs?.[0];
    $("alertStatus").textContent = latestRun?.status === "failed" ? latestRun.error || "Rule check failed." : "Rule check finished.";
  } catch (error) {
    $("alertStatus").textContent = `Error: ${error.message}`;
  } finally {
    $("runAlerts").disabled = false;
  }
}

function optionalMarketNumber(id, multiplier = 1) {
  const raw = valueOf(id);
  if (raw === "") return "";
  const number = Number(raw);
  return Number.isFinite(number) ? number * multiplier : "";
}

function marketCriteria() {
  return {
    query: valueOf("marketQuery"),
    exchange: valueOf("marketExchange"),
    sector: valueOf("marketSector"),
    industry: valueOf("marketIndustry"),
    country: valueOf("marketCountry"),
    priceMoreThan: optionalMarketNumber("marketPriceMin"),
    priceLowerThan: optionalMarketNumber("marketPriceMax"),
    marketCapMoreThan: optionalMarketNumber("marketCapMinMillions", 1_000_000),
    marketCapLowerThan: optionalMarketNumber("marketCapMaxMillions", 1_000_000),
    dividendYieldMoreThan: optionalMarketNumber("marketDividendYieldMin"),
    dividendYieldLowerThan: optionalMarketNumber("marketDividendYieldMax"),
    annualNetIncomeMoreThan: optionalMarketNumber("marketAnnualProfitMinMillions", 1_000_000),
    profitMarketCapMoreThan: optionalMarketNumber("marketProfitCapMin"),
    profitMarketCapLowerThan: optionalMarketNumber("marketProfitCapMax"),
    priceEarningsLowerThan: optionalMarketNumber("marketPeMax"),
    revenueGrowthMoreThan: optionalMarketNumber("marketRevenueGrowthMin"),
    netIncomeGrowthMoreThan: optionalMarketNumber("marketProfitGrowthMin"),
    netMarginMoreThan: optionalMarketNumber("marketNetMarginMin"),
    freeCashFlowMoreThan: optionalMarketNumber("marketFcfMinMillions", 1_000_000),
    freeCashFlowYieldMoreThan: optionalMarketNumber("marketFcfYieldMin"),
    debtRevenueLowerThan: optionalMarketNumber("marketDebtRevenueMax"),
    currentRatioMoreThan: optionalMarketNumber("marketCurrentRatioMin"),
    betaLowerThan: optionalMarketNumber("marketBetaMax"),
    volumeMoreThan: optionalMarketNumber("marketVolumeMin"),
    includeMissing: $("marketIncludeMissing").checked,
    sortBy: valueOf("marketSortBy") || "market_cap:desc",
    limit: Number(valueOf("marketResultLimit") || 25),
  };
}

function validateMarketRange(criteria, minimumKey, maximumKey, label) {
  const minimum = Number(criteria[minimumKey]);
  const maximum = Number(criteria[maximumKey]);
  if (criteria[minimumKey] !== "" && criteria[maximumKey] !== "" && minimum > maximum) {
    throw new Error(`${label} minimum cannot exceed maximum`);
  }
}

function marketMetricPercent(value, digits = 1) {
  return value === null || value === undefined ? "∅" : `${fmt(value, digits)}%`;
}

function marketMetricAmount(value, currency = "USD") {
  return value === null || value === undefined ? "∅" : `${esc(currency || "USD")} ${esc(compactNumber(value))}`;
}

function marketValueClass(value) {
  if (value === null || value === undefined) return "";
  return Number(value) >= 0 ? "positive" : "negative";
}

function resetMarketScreener() {
  [
    "marketQuery", "marketSector", "marketIndustry", "marketCountry", "marketPriceMin", "marketPriceMax",
    "marketCapMinMillions", "marketCapMaxMillions", "marketDividendYieldMin", "marketDividendYieldMax",
    "marketAnnualProfitMinMillions", "marketProfitCapMin", "marketProfitCapMax", "marketPeMax",
    "marketRevenueGrowthMin", "marketProfitGrowthMin", "marketNetMarginMin", "marketFcfMinMillions",
    "marketFcfYieldMin", "marketDebtRevenueMax", "marketCurrentRatioMin", "marketBetaMax", "marketVolumeMin",
  ].forEach((id) => { $(id).value = ""; });
  $("marketExchange").value = "";
  $("marketSortBy").value = "market_cap:desc";
  $("marketResultLimit").value = "25";
  $("marketIncludeMissing").checked = false;
  $("marketStatus").textContent = "Filters reset";
  $("marketFilterSummary").textContent = "";
  $("marketRows").innerHTML = "";
}

async function runMarketScreener() {
  const criteria = marketCriteria();
  validateMarketRange(criteria, "priceMoreThan", "priceLowerThan", "Price");
  validateMarketRange(criteria, "marketCapMoreThan", "marketCapLowerThan", "Market cap");
  validateMarketRange(criteria, "dividendYieldMoreThan", "dividendYieldLowerThan", "Dividend yield");
  validateMarketRange(criteria, "profitMarketCapMoreThan", "profitMarketCapLowerThan", "Profit / market cap");
  $("marketStatus").textContent = "Searching market and annual statements…";
  $("marketFilterSummary").textContent = "";
  const data = await api("/api/market/screener", { method: "POST", body: JSON.stringify(criteria) });
  const meta = data.meta || {};
  const provider = providerStatusHint(data.status || {});
  const reportText = meta.latest_annual_reports ? ` · ${meta.financial_rows || 0}/${meta.enriched || 0} annual reports available` : "";
  $("marketStatus").textContent = `${data.count} symbols${reportText}${provider ? ` · ${provider}` : ""}`;
  const activeFilters = meta.filters_applied || [];
  $("marketFilterSummary").textContent = activeFilters.length
    ? `Applied: ${activeFilters.join(", ")}${meta.include_missing ? " · missing values included" : " · rows missing filtered values excluded"}`
    : "No financial thresholds applied";
  $("marketRows").innerHTML = data.items.length ? data.items.map((item) => `
    <tr>
      <td><div class="symbol">${esc(item.symbol)}</div><div class="sub">${esc(item.exchange || "Unknown exchange")}</div></td>
      <td>${esc(item.name || "Unknown company")}<div class="sub">${esc([item.sector, item.industry, item.country].filter(Boolean).join(" · ") || "Classification unavailable")}</div></td>
      <td>${item.price === null || item.price === undefined ? "∅" : money(item.price, item.currency || "USD", 2)}</td>
      <td>${marketMetricAmount(item.market_cap, item.currency)}</td>
      <td>${marketMetricPercent(item.dividend_yield_percent, 2)}<div class="sub">${item.annual_dividend === null || item.annual_dividend === undefined ? "" : `${money(item.annual_dividend, item.currency || "USD", 3)} / share`}</div></td>
      <td class="${marketValueClass(item.annual_net_income)}">${marketMetricAmount(item.annual_net_income, item.currency)}<div class="sub">${item.fiscal_year || "Year unavailable"}</div></td>
      <td>${marketMetricPercent(item.profit_market_cap_percent, 2)}</td>
      <td class="${marketValueClass(item.revenue_growth_percent)}">${marketMetricPercent(item.revenue_growth_percent)}</td>
      <td class="${marketValueClass(item.net_income_growth_percent)}">${marketMetricPercent(item.net_income_growth_percent)}</td>
      <td>${marketMetricPercent(item.net_margin_percent)}</td>
      <td class="${marketValueClass(item.free_cash_flow)}">${marketMetricAmount(item.free_cash_flow, item.currency)}<div class="sub">Yield ${marketMetricPercent(item.free_cash_flow_yield_percent)}</div></td>
      <td>${item.price_earnings_ratio === null || item.price_earnings_ratio === undefined ? "∅" : fmt(item.price_earnings_ratio, 1)}</td>
      <td>${item.beta === null || item.beta === undefined ? "∅" : fmt(item.beta, 2)}</td>
      <td><button class="secondary compact-button" type="button" data-open-market-report="${esc(item.symbol)}">Report</button></td>
    </tr>
  `).join("") : '<tr><td colspan="14" class="empty-cell">No companies match these filters, or the required provider data is unavailable.</td></tr>';
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
  $("backupKeep").value = backup.keep || 100;
  updateBackupScheduleSummary();
  syncBackupEnabledControls();
  $("cacheStatus").innerHTML = [
    ["Cache file", data.path],
    ["API response entries", data.entries],
    ["Cached daily prices", data.price_entries ?? 0],
    ["Current size", `${data.size_mb} MB`],
    ["Max size", `${data.max_mb} MB`],
    ["TTL", `${data.ttl_hours} hours`],
  ].map(([label, value]) => `<div class="setting-row"><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join("");
  const backupRows = [
    ["Backup directory", backup.directory || ""],
    ["Schedule", backup.enabled === false ? "Disabled" : backup.schedule_summary || backupScheduleSummary(backup.schedule_config)],
    ["Next run", backup.next_run || "Disabled"],
    ["Latest backup", backup.latest?.filename || "None"],
    ["Backup files", backup.backup_count ?? (backup.backups || []).length],
  ].map(([label, value]) => `<div class="setting-row"><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join("");
  const backupFiles = (backup.backups || []).map((file) => `
    <div class="setting-row backup-file-row">
      <span>${esc(file.filename)}<small>${esc(file.modified_at || "")} · ${esc(file.size_kb || 0)} KB</small></span>
      <button class="secondary compact-button" type="button" data-download-backup="${esc(file.filename)}">Download</button>
    </div>
  `).join("");
  $("backupStatus").innerHTML = backupRows + backupFiles;
}

async function downloadResponse(response, defaultFilename) {
  if (!response.ok) throw new Error(await response.text());
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] || defaultFilename;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function exportLocalData() {
  $("settingsStatus").textContent = "Exporting data";
  await syncClientStateToServer();
  const response = await fetch("/api/local/export");
  await downloadResponse(response, "portfolio-data.json");
  $("settingsStatus").textContent = "Data exported";
}

async function importLocalData(file) {
  if (!file) return;
  const text = await file.text();
  const payload = JSON.parse(text);
  if (!confirm("Import will replace the local portfolio data. Continue?")) return;
  $("settingsStatus").textContent = "Importing data";
  const result = await api("/api/local/import", { method: "POST", body: JSON.stringify(payload) });
  if (applyClientState(clientStateFromExportPayload(payload))) {
    loadClientStateFromStorage();
  } else {
    await loadClientStateFromServer().catch(() => {});
    loadClientStateFromStorage();
  }
  const total = Object.values(result.imported || {}).reduce((count, value) => count + Number(value || 0), 0);
  $("settingsStatus").textContent = `Imported ${total} records`;
  await Promise.all([loadLocalAccounts(), loadPortfolio(), loadCacheStatus(), loadBanner()]);
}

async function runBackupNow() {
  $("settingsStatus").textContent = "Creating backup";
  await syncClientStateToServer();
  const result = await api("/api/local/backups", { method: "POST", body: "{}" });
  $("settingsStatus").textContent = `Backup saved: ${result.filename}`;
  await loadCacheStatus();
}

async function downloadBackup(filename) {
  $("settingsStatus").textContent = `Downloading ${filename}`;
  const response = await fetch(`/api/local/backups/${encodeURIComponent(filename)}`);
  await downloadResponse(response, filename);
  $("settingsStatus").textContent = `Downloaded ${filename}`;
}

async function downloadBackupsZip() {
  $("settingsStatus").textContent = "Downloading backup ZIP";
  const response = await fetch("/api/local/backups.zip");
  await downloadResponse(response, "portfolio-backups.zip");
  $("settingsStatus").textContent = "Backup ZIP downloaded";
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
  if (backup.enabled === false || $("backupEnabled")?.value === "false") {
    $("backupScheduleSummary").innerHTML = '<span>Schedule</span><b>Automatic backup disabled</b><small>Manual backups remain available</small>';
    return;
  }
  const summary = backup.schedule_summary || backupScheduleSummary(backup.schedule_config);
  $("backupScheduleSummary").innerHTML = `<span>Schedule</span><b>${esc(summary)}</b><small>${backup.missed_policy === "run" ? "Backup now if the selected time already passed" : "Wait for the next selected time"}</small>`;
}

function populateBackupScheduleForm() {
  renderBackupSchedulePickers();
  const backup = state.backupSettings || {};
  const config = normalizeBackupScheduleConfig(backup.schedule_config);
  $("backupScheduleFrequency").value = backup.enabled === false ? "none" : config.frequency;
  $("backupScheduleHour").value = config.hour;
  $("backupScheduleMinute").value = config.minute;
  $("backupMissedPolicy").value = backup.missed_policy === "run" ? "run" : "wait";
  document.querySelectorAll("input[name='backupWeekday']").forEach((input) => { input.checked = config.weekdays.includes(Number(input.value)); });
  document.querySelectorAll("input[name='backupMonthDay']").forEach((input) => { input.checked = config.month_days.includes(Number(input.value)); });
  syncBackupSchedulePickers();
}

function syncBackupSchedulePickers() {
  const frequency = valueOf("backupScheduleFrequency") || "weekly";
  const enabled = frequency !== "none";
  $("backupWeeklyPicker").hidden = frequency !== "weekly";
  $("backupMonthlyPicker").hidden = frequency !== "monthly";
  ["backupScheduleHour", "backupScheduleMinute", "backupMissedPolicy"].forEach((id) => {
    const input = $(id);
    if (input) input.disabled = !enabled;
  });
  document.querySelectorAll("#backupWeeklyPicker input, #backupMonthlyPicker input").forEach((input) => {
    const picker = input.closest(".schedule-picker");
    input.disabled = !enabled || picker?.hidden;
  });
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
  const automaticBackup = valueOf("backupScheduleFrequency") !== "none";
  state.backupSettings = {
    ...(state.backupSettings || {}),
    enabled: automaticBackup,
    schedule_config: backupScheduleFromForm(),
    missed_policy: valueOf("backupMissedPolicy") || "wait",
  };
  $("backupEnabled").value = String(automaticBackup);
  state.backupSettings.schedule_summary = backupScheduleSummary(state.backupSettings.schedule_config);
  updateBackupScheduleSummary();
  syncBackupEnabledControls();
  closeModal($("backupScheduleModal"));
}

function syncBackupEnabledControls() {
  const enabled = $("backupEnabled").value === "true";
  $("editBackupSchedule").disabled = !enabled;
  state.backupSettings = {
    ...(state.backupSettings || {}),
    enabled,
  };
  updateBackupScheduleSummary();
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

function setResearchSection(section = "finance") {
  const selected = ["finance", "outlook", "signals"].includes(section) ? section : "finance";
  state.researchSection = selected;
  document.querySelectorAll("[data-research-panel]").forEach((panel) => {
    const active = panel.dataset.researchPanel === selected;
    panel.hidden = !active;
    panel.setAttribute("aria-hidden", String(!active));
  });
  document.querySelectorAll("[data-research-tab]").forEach((tab) => {
    const active = tab.dataset.researchTab === selected;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
}

const modalReturnFocus = new Map();

function focusModalDestination(modal, { targetId = "", focusId = "" } = {}) {
  const target = targetId ? $(targetId) : null;
  const focusTarget = focusId ? $(focusId) : null;
  if ((!target || !modal.contains(target)) && (!focusTarget || !modal.contains(focusTarget))) return;
  requestAnimationFrame(() => {
    if (target && modal.contains(target)) target.scrollIntoView({ block: "start" });
    if (focusTarget && modal.contains(focusTarget)) focusTarget.focus({ preventScroll: Boolean(target) });
  });
}

function openModal(id, returnFocus = document.activeElement, destination = {}) {
  const modal = $(id);
  if (!modal) return;
  if (returnFocus instanceof HTMLElement) modalReturnFocus.set(id, returnFocus);
  modal.hidden = false;
  if (id === "accountsModal") {
    setAccountsTab("existing");
    Promise.all([loadBrokers(), loadFamilyMembers(), loadLocalAccounts()]);
  }
  if (id === "brokersModal") loadBrokers();
  if (id === "familyModal") Promise.all([loadLocalAccounts(), loadFamilyMembers()]);
  if (id === "securitiesModal") {
    Promise.all([
      loadLocalAccounts(),
      loadLocalSecurities(),
      employeeOptionsWorkflowActive() ? loadEmployeeOptionGrants() : Promise.resolve(),
    ]).then(() => {
      if (!employeeOptionsWorkflowActive()) return;
      const focusTarget = state.employeeOptionWizardMode === "browse" ? $("newEmployeeOptionGrant") : employeeWizardFirstField(1);
      requestAnimationFrame(() => focusTarget?.focus());
    }).catch((error) => {
      const status = employeeOptionsWorkflowActive() ? $("employeeOptionListStatus") : $("securityStatus");
      if (status) status.textContent = `Error: ${error.message}`;
    });
  }
  if (id === "pricesModal") loadLocalPrices();
  if (id === "eventsModal") {
    loadEvents().catch((error) => { $("eventsStatus").textContent = `Error: ${error.message}`; });
  }
  if (id === "alarmsModal") {
    renderAlarms();
    loadEvents().catch((error) => { $("alarmsStatus").textContent = `Error: ${error.message}`; });
  }
  if (id === "reportsModal") Promise.all([loadLocalAccounts(), loadReports()]);
  if (id === "researchModal") {
    setResearchSection(state.researchSection);
    loadCompanyOutlookHistory().catch((error) => { $("companyOutlookStatus").textContent = `Error: ${error.message}`; });
    loadAlerts().catch((error) => { $("alertStatus").textContent = `Error: ${error.message}`; });
    requestAnimationFrame(() => modal.querySelector("[data-modal-initial-focus]")?.focus());
  }
  if (id === "fundsModal") {
    hideFundCreate({ clear: true });
    Promise.all([loadLocalAccounts(), loadFamilyMembers(), loadFunds()]);
  }
  if (id === "bannerModal") renderBannerSettings();
  if (id === "settingsModal") loadCacheStatus();
  if (id === "backupScheduleModal") populateBackupScheduleForm();
  if (id === "aboutModal") loadAbout().catch((error) => { $("aboutContent").innerHTML = `<div class="empty">Error: ${esc(error.message)}</div>`; });
  focusModalDestination(modal, destination);
}

function closeModal(modal) {
  if (!modal) return;
  modal.hidden = true;
  if (modal.id === "accountsModal" && state.returnToEmployeeOptionsAfterAccount) {
    state.returnToEmployeeOptionsAfterAccount = false;
  }
  const returnFocus = modalReturnFocus.get(modal.id);
  modalReturnFocus.delete(modal.id);
  const fallbackSelector = modal.id === "securitiesModal" && employeeOptionsWorkflowActive()
    ? '[data-modal="securitiesModal"][data-securities-workflow="employee-options"]'
    : `[data-modal="${modal.id}"]`;
  requestAnimationFrame(() => {
    const focusTarget = returnFocus?.isConnected ? returnFocus : document.querySelector(fallbackSelector);
    if (focusTarget instanceof HTMLElement) {
      const parentMenu = focusTarget.closest("details");
      if (parentMenu && !parentMenu.open) parentMenu.open = true;
      focusTarget.focus();
    }
  });
}

document.addEventListener("keydown", (event) => {
  const activeResearchTab = event.target.closest?.("[data-research-tab]");
  if (activeResearchTab && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
    const tabs = [...document.querySelectorAll("[data-research-tab]")];
    const currentIndex = tabs.indexOf(activeResearchTab);
    const nextIndex = event.key === "Home"
      ? 0
      : event.key === "End"
        ? tabs.length - 1
        : (currentIndex + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    event.preventDefault();
    tabs[nextIndex].focus();
    tabs[nextIndex].click();
    return;
  }

  const activeModal = [...document.querySelectorAll(".modal:not([hidden])")].at(-1);
  if (!activeModal) return;
  if (event.key === "Escape") {
    event.preventDefault();
    closeModal(activeModal);
    return;
  }
  if (event.key !== "Tab") return;
  const focusable = [...activeModal.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), summary, [href], [tabindex]:not([tabindex="-1"])')]
    .filter((element) => element.offsetParent !== null);
  if (!focusable.length) return;
  const currentIndex = focusable.indexOf(document.activeElement);
  if (currentIndex === -1) {
    event.preventDefault();
    focusable[event.shiftKey ? focusable.length - 1 : 0].focus();
  } else if (event.shiftKey && currentIndex === 0) {
    event.preventDefault();
    focusable.at(-1).focus();
  } else if (!event.shiftKey && currentIndex === focusable.length - 1) {
    event.preventDefault();
    focusable[0].focus();
  }
});

document.addEventListener("click", (event) => {
  const modalTrigger = event.target.closest("[data-modal]");
  const modalId = modalTrigger?.dataset.modal;
  if (modalId) {
    if (modalTrigger.dataset.researchSection) setResearchSection(modalTrigger.dataset.researchSection);
    if (modalId === "securitiesModal") setSecuritiesWorkflow(modalTrigger.dataset.securitiesWorkflow || "general");
    openModal(modalId, modalTrigger, {
      targetId: modalTrigger.dataset.modalTarget || "",
      focusId: modalTrigger.dataset.modalFocus || "",
    });
  }

  const employeeWizardStep = Number(event.target.closest("[data-employee-guide-step]")?.dataset.employeeGuideStep || 0);
  if (employeeWizardStep && employeeWizardStep <= state.employeeOptionWizardMaxStep) {
    if (employeeWizardStep === 3) renderEmployeeWizardReview();
    setEmployeeOptionGuideStep(employeeWizardStep);
    requestAnimationFrame(() => employeeWizardFirstField(employeeWizardStep)?.focus());
  }

  const editEmployeeGrantId = event.target.closest("[data-edit-employee-option-grant]")?.dataset.editEmployeeOptionGrant;
  if (editEmployeeGrantId) editEmployeeOptionGrant(editEmployeeGrantId);

  const deleteEmployeeGrantId = event.target.closest("[data-delete-employee-option-grant]")?.dataset.deleteEmployeeOptionGrant;
  if (deleteEmployeeGrantId) deleteEmployeeOptionGrant(deleteEmployeeGrantId);

  if (event.target.id === "createEsopAccountFromOptions") {
    state.returnToEmployeeOptionsAfterAccount = true;
    closeModal($("securitiesModal"));
    openModal("accountsModal", event.target);
    setAccountsTab("new");
    $("localAccountType").value = "ESOP";
    $("accountsStatus").textContent = "Create an ESOP account for your employee stock option grants.";
    requestAnimationFrame(() => $("localUsername")?.focus());
  }

  const researchTab = event.target.closest("[data-research-tab]")?.dataset.researchTab;
  if (researchTab) setResearchSection(researchTab);

  const investigateSignal = event.target.closest("[data-investigate-signal]")?.dataset.investigateSignal;
  if (investigateSignal) {
    investigateAlertSignal(investigateSignal).catch((error) => {
      $("companyOutlookStatus").textContent = `Error: ${error.message}`;
    });
  }

  const editAlertId = event.target.closest("[data-edit-alert]")?.dataset.editAlert;
  if (editAlertId) editAlertRule(editAlertId);

  const toggleAlertId = event.target.closest("[data-toggle-alert]")?.dataset.toggleAlert;
  if (toggleAlertId) {
    toggleAlertRule(toggleAlertId).catch((error) => { $("alertStatus").textContent = `Error: ${error.message}`; });
  }

  const deleteAlertId = event.target.closest("[data-delete-alert]")?.dataset.deleteAlert;
  if (deleteAlertId) {
    deleteAlertRule(deleteAlertId).catch((error) => { $("alertStatus").textContent = `Error: ${error.message}`; });
  }

  const removeAlertConditionIndex = event.target.closest("[data-remove-alert-condition]")?.dataset.removeAlertCondition;
  if (removeAlertConditionIndex !== undefined) removeAlertCondition(Number(removeAlertConditionIndex));

  const marketReportSymbol = event.target.closest("[data-open-market-report]")?.dataset.openMarketReport;
  if (marketReportSymbol) {
    closeModal($("marketModal"));
    setResearchSection("finance");
    openModal("researchModal");
    $("financeReportSymbol").value = cleanSecuritySymbol(marketReportSymbol);
    loadFinanceReport().catch((error) => { $("financeReportStatus").textContent = `Error: ${error.message}`; });
  }

  const dividendAlarmId = event.target.closest("[data-open-dividend-alarm]")?.dataset.openDividendAlarm;
  if (dividendAlarmId) openDividendAlarm(dividendAlarmId);

  const vestingAlarmId = event.target.closest("[data-open-vesting-alarm]")?.dataset.openVestingAlarm;
  if (vestingAlarmId) openVestingAlarm(vestingAlarmId);

  const accountTab = event.target.closest("[data-account-tab]")?.dataset.accountTab;
  if (accountTab) setAccountsTab(accountTab);

  const longTermView = event.target.closest("[data-long-term-view]")?.dataset.longTermView;
  if (longTermView) {
    state.longTermView = longTermView;
    localStorage.setItem(DASHBOARD_LONG_TERM_STORAGE_KEY, longTermView);
    saveDashboardSettings();
    renderAnalytics(state.items || []);
  }

  if (event.target.matches("[data-close]")) {
    closeModal(event.target.closest(".modal"));
  }

  const removeIndex = event.target.closest("[data-remove-banner]")?.dataset.removeBanner;
  if (removeIndex !== undefined) {
    state.bannerItems.splice(Number(removeIndex), 1);
    saveBannerItems();
    resolveBannerItems();
  }

  const predictionId = event.target.closest("[data-evaluate-company-outlook]")?.dataset.evaluateCompanyOutlook;
  if (predictionId) {
    evaluateCompanyOutlookPrediction(predictionId).catch((error) => {
      $("companyOutlookStatus").textContent = `Error: ${error.message}`;
    });
  }

  const deletePrediction = event.target.closest("[data-delete-company-outlook]");
  if (deletePrediction) {
    deleteCompanyOutlookPrediction(deletePrediction.dataset.deleteCompanyOutlook, deletePrediction.dataset.predictionSymbol).catch((error) => {
      $("companyOutlookStatus").textContent = `Error: ${error.message}`;
    });
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

  const positionHistoryButton = event.target.closest("[data-position-history-symbol]");
  if (positionHistoryButton) {
    openPositionTransactionHistory(positionHistoryButton.dataset).catch((error) => {
      $("positionTransactionsRows").innerHTML = `<tr><td colspan="8" class="empty-cell">Error: ${esc(error.message)}</td></tr>`;
    });
  }

  const editPositionTransactionId = event.target.closest("[data-edit-position-transaction]")?.dataset.editPositionTransaction;
  if (editPositionTransactionId) editPositionTransaction(editPositionTransactionId);

  if (event.target.id === "cancelPositionTransactionEdit") {
    clearPositionTransactionForm("Transaction edit cancelled");
  }

  const securityChartPeriod = event.target.closest("[data-security-chart-period]")?.dataset.securityChartPeriod;
  if (securityChartPeriod) {
    state.securityChartPeriod = securityChartPeriod;
    state.securityChartStartDate = startDateForPeriod(securityChartPeriod);
    if ($("securityChartStartDate")) $("securityChartStartDate").value = state.securityChartStartDate;
    loadSecurityDetail().catch((error) => { $("securityDetailStatus").textContent = `Error: ${error.message}`; });
  }

  const securityChartMode = event.target.closest("[data-security-chart-mode]")?.dataset.securityChartMode;
  if (securityChartMode) {
    state.securityChartMode = securityChartMode === "candles" ? "candles" : "line";
    renderSecurityChart();
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
    api(`/api/local/securities/${securityId}`, { method: "DELETE" })
      .then(() => Promise.all([loadLocalSecurities(), loadPortfolio()]))
      .catch((error) => { $("securityStatus").textContent = `Error: ${error.message}`; });
  }

  const editSecurityId = event.target.closest("[data-edit-security]")?.dataset.editSecurity;
  if (editSecurityId) {
    if ($("securitiesModal")?.hidden) {
      const transaction = state.localTransactions.find((item) => item.id === editSecurityId);
      setSecuritiesWorkflow(transaction?.instrument_type === "EMPLOYEE_STOCK_OPTION" ? "employee-options" : "general");
      openModal("securitiesModal");
      Promise.resolve(loadLocalSecurities()).then(() => editSecurityTransaction(editSecurityId));
    } else {
      editSecurityTransaction(editSecurityId);
    }
  }

  if (event.target.id === "cancelSecurityEdit") {
    clearSecurityForm();
    $("securityStatus").textContent = "Transaction edit cancelled";
  }

  const editAccountId = event.target.closest("[data-edit-account]")?.dataset.editAccount;
  if (editAccountId) {
    editLocalAccount(editAccountId);
  }

  const manualSecurityId = event.target.closest("[data-delete-manual-security]")?.dataset.deleteManualSecurity;
  if (manualSecurityId) {
    api(`/api/local/manual-securities/${manualSecurityId}`, { method: "DELETE" })
      .then(() => Promise.all([loadManualSecurities(), loadPortfolio()]))
      .catch((error) => { $("manualSecurityStatus").textContent = `Error: ${error.message}`; });
  }

  const useManualSecurityId = event.target.closest("[data-use-manual-security]")?.dataset.useManualSecurity;
  if (useManualSecurityId) {
    const item = instrumentById(useManualSecurityId);
    applyInstrumentToForm(item, "security");
    $("securityKnownInstrument").value = useManualSecurityId;
    $("securityStatus").textContent = `Using ${item?.company_name || item?.symbol || "instrument"} for the next transaction`;
    if (item?.instrument_type === "EMPLOYEE_STOCK_OPTION") {
      setEmployeeOptionGuideStep(2);
      requestAnimationFrame(() => {
        $("accountTransactionSection")?.scrollIntoView({ block: "start", behavior: "smooth" });
        $("securityQuantity")?.focus({ preventScroll: true });
      });
    }
  }

  const listingSecurityId = event.target.closest("[data-link-employee-listing]")?.dataset.linkEmployeeListing;
  if (listingSecurityId) openEmployeeListing(listingSecurityId);

  const exerciseSecurityId = event.target.closest("[data-exercise-employee-option]")?.dataset.exerciseEmployeeOption;
  if (exerciseSecurityId) openEmployeeExercise(exerciseSecurityId);

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

  const fundHistoryId = event.target.closest("[data-fund-history]")?.dataset.fundHistory;
  if (fundHistoryId) {
    openFundAmountHistory(fundHistoryId).catch((error) => { $("fundStatus").textContent = `Error: ${error.message}`; });
  }

  const editFundHistoryId = event.target.closest("[data-edit-fund-history]")?.dataset.editFundHistory;
  if (editFundHistoryId) editFundAmountHistory(editFundHistoryId);

  const deleteFundHistoryId = event.target.closest("[data-delete-fund-history]")?.dataset.deleteFundHistory;
  if (deleteFundHistoryId) {
    deleteFundAmountHistory(deleteFundHistoryId).catch((error) => { $("fundHistoryStatus").textContent = `Error: ${error.message}`; });
  }

  const editFundId = event.target.closest("[data-edit-fund]")?.dataset.editFund;
  if (editFundId) {
    editFund(editFundId);
  }

  const familyMemberId = event.target.closest("[data-delete-family-member]")?.dataset.deleteFamilyMember;
  if (familyMemberId) {
    api(`/api/local/family-members/${familyMemberId}`, { method: "DELETE" })
      .then(loadFamilyMembers)
      .catch((error) => { $("familyStatus").textContent = `Error: ${error.message}`; });
  }

  const editFamilyMemberId = event.target.closest("[data-edit-family-member]")?.dataset.editFamilyMember;
  if (editFamilyMemberId) {
    editFamilyMember(editFamilyMemberId);
  }

  const brokerId = event.target.closest("[data-delete-broker]")?.dataset.deleteBroker;
  if (brokerId) {
    api(`/api/local/brokers/${brokerId}`, { method: "DELETE" })
      .then(loadBrokers)
      .catch((error) => { $("brokerStatus").textContent = `Error: ${error.message}`; });
  }

  const editBrokerId = event.target.closest("[data-edit-broker]")?.dataset.editBroker;
  if (editBrokerId) {
    editBroker(editBrokerId);
  }

  const localPersonIndex = event.target.closest("[data-delete-local-person]")?.dataset.deleteLocalPerson;
  if (localPersonIndex !== undefined) {
    state.localAccountPersons.splice(Number(localPersonIndex), 1);
    renderPersonLists();
  }

  const editPersonIndex = event.target.closest("[data-delete-edit-person]")?.dataset.deleteEditPerson;
  if (editPersonIndex !== undefined) {
    state.editAccountPersons.splice(Number(editPersonIndex), 1);
    renderPersonLists();
  }

  const fundPersonIndex = event.target.closest("[data-delete-fund-person]")?.dataset.deleteFundPerson;
  if (fundPersonIndex !== undefined) {
    state.fundPersons.splice(Number(fundPersonIndex), 1);
    renderPersonLists();
  }

  const editFundPersonIndex = event.target.closest("[data-delete-edit-fund-person]")?.dataset.deleteEditFundPerson;
  if (editFundPersonIndex !== undefined) {
    state.editFundPersons.splice(Number(editFundPersonIndex), 1);
    renderPersonLists();
  }

  const periodIndex = event.target.closest("[data-delete-pension-period]")?.dataset.deletePensionPeriod;
  if (periodIndex !== undefined) {
    const scenario = activePensionScenario();
    if (scenario) scenario.income_periods.splice(Number(periodIndex), 1);
    invalidatePensionSimulation();
    renderPensionScenarios();
    renderPensionPeriods();
  }

  const rateIndex = event.target.closest("[data-delete-pension-rate]")?.dataset.deletePensionRate;
  if (rateIndex !== undefined) {
    const scenario = activePensionScenario();
    if (scenario) scenario.return_periods.splice(Number(rateIndex), 1);
    invalidatePensionSimulation();
    renderPensionScenarios();
    renderPensionRates();
    renderFundsOverview();
  }

  if (event.target.id === "pensionStopWorkNow") {
    stopPensionWorkNow();
  }

  const scheduleScenarioIndex = event.target.closest("[data-schedule-pension-scenario]")?.dataset.schedulePensionScenario;
  if (scheduleScenarioIndex !== undefined) {
    openPensionPeriodModal(Number(scheduleScenarioIndex));
  }

  const editScenarioIndex = event.target.closest("[data-edit-pension-scenario]")?.dataset.editPensionScenario;
  if (editScenarioIndex !== undefined) {
    editPensionScenario(Number(editScenarioIndex));
  }

  const scenarioIndex = event.target.closest("[data-delete-pension-scenario]")?.dataset.deletePensionScenario;
  if (scenarioIndex !== undefined) {
    const removed = Number(scenarioIndex);
    state.pensionScenarios.splice(removed, 1);
    if (state.activePensionScenarioIndex === removed) {
      state.activePensionScenarioIndex = null;
    } else if (Number.isInteger(state.activePensionScenarioIndex) && state.activePensionScenarioIndex > removed) {
      state.activePensionScenarioIndex -= 1;
    }
    invalidatePensionSimulation();
    renderPensionScenarios();
    renderPensionPeriods();
    renderFundsOverview();
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

  const backupDownload = event.target.closest("[data-download-backup]")?.dataset.downloadBackup;
  if (backupDownload) {
    downloadBackup(backupDownload).catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; });
  }
});

document.addEventListener("change", (event) => {
  if (event.target.id === "employeeWizardCompanyStatus") toggleEmployeeWizardCompanyFields();
  if (event.target.id === "employeeWizardCompany") syncEmployeeWizardIssuerFromCompany();
  if (event.target.id === "employeeWizardLocation") syncCurrencyFromLocation("employeeWizardLocation", "employeeWizardCurrency");
  if (["employeeWizardVestingStyle", "employeeWizardVestingMode"].includes(event.target.id)) renderEmployeeWizardVestingPreview();
  if (event.target.id === "employeeWizardGrantDate" && !valueOf("employeeWizardVestingStart")) {
    setDateField("employeeWizardVestingStart", dateValue("employeeWizardGrantDate"));
    renderEmployeeWizardVestingPreview();
  }

  const pensionPeriodInput = event.target.closest("[data-pension-period-index][data-pension-period-field]");
  if (pensionPeriodInput) {
    const index = Number(pensionPeriodInput.dataset.pensionPeriodIndex);
    const field = pensionPeriodInput.dataset.pensionPeriodField;
    const scenario = activePensionScenario();
    const period = scenario?.income_periods?.[index];
    const numericFields = [
      "from_age", "to_age", "monthly_income", "contribution_percent", "monthly_deposit",
      "disability_coverage_percent", "spouse_survivors_coverage_percent", "children_survivors_coverage_percent",
      "survivors_capitalization_factor",
    ];
    if (period && field === "insurance_track") {
      const track = PENSION_INSURANCE_TRACKS[pensionPeriodInput.value];
      period.insurance_track = pensionPeriodInput.value;
      if (track && pensionPeriodInput.value !== "custom") {
        period.disability_coverage_percent = track.disability;
        period.spouse_survivors_coverage_percent = track.spouse;
        period.children_survivors_coverage_percent = track.children;
        if (!period.survivors_capitalization_factor) period.survivors_capitalization_factor = 200;
      }
      invalidatePensionSimulation();
      renderPensionScenarios();
      renderPensionPeriods();
      renderPensionProjectionSummary();
      renderFundsOverview();
    } else if (period && numericFields.includes(field)) {
      period[field] = pensionPeriodInput.value === "" ? 0 : Number(pensionPeriodInput.value);
      period.insurance_track = pensionInsuranceTrackFor(period);
      invalidatePensionSimulation();
      renderPensionScenarios();
      renderPensionPeriods();
      renderPensionProjectionSummary();
      renderFundsOverview();
    }
  }

  const pensionRateInput = event.target.closest("[data-pension-rate-index][data-pension-rate-field]");
  if (pensionRateInput) {
    const index = Number(pensionRateInput.dataset.pensionRateIndex);
    const field = pensionRateInput.dataset.pensionRateField;
    const scenario = activePensionScenario();
    if (scenario?.return_periods?.[index] && ["from_age", "to_age", "annual_return"].includes(field)) {
      scenario.return_periods[index][field] = pensionRateInput.value === "" ? "" : Number(pensionRateInput.value);
      invalidatePensionSimulation();
      renderPensionScenarios();
      renderPensionRates();
      renderPensionProjectionSummary();
      renderFundsOverview();
    }
  }

  const accountTrendSelect = event.target.closest("[data-account-trend-select]");
  if (accountTrendSelect) {
    state.dashboard.accountTrendAccountId = accountTrendSelect.value;
    localStorage.setItem(DASHBOARD_ACCOUNT_STORAGE_KEY, accountTrendSelect.value);
    saveDashboardSettings();
    renderAnalytics(state.items || []);
  }

  if (event.target.id === "manualInstrumentType" || event.target.id === "manualIssuerStatus") {
    toggleManualInstrumentFields();
  }

  if (event.target.id === "manualCompanyName") {
    syncEmployeeIssuerFromCompany();
  }

  if (event.target.id === "manualGrantDate" && !dateValue("manualVestingStartDate")) {
    setDateField("manualVestingStartDate", dateValue("manualGrantDate"));
  }

  if (event.target.id === "manualSecurityLocation") {
    syncCurrencyFromLocation("manualSecurityLocation", "manualSecurityCurrency");
  }

  if (event.target.id === "brokerCountry") {
    syncCurrencyFromLocation("brokerCountry", "brokerCurrency");
  }

  if (event.target.id === "localAccountBroker") {
    applyBrokerToAccount("localAccountBroker", "localAccountLocation", "localAccountCurrency");
  }

  if (event.target.id === "editAccountBroker") {
    applyBrokerToAccount("editAccountBroker", "editAccountLocation", "editAccountCurrency");
  }

  if (event.target.id === "securityKnownInstrument") {
    applyInstrumentToForm(instrumentById(event.target.value), "security");
    toggleTransactionCompFields();
    if (employeeOptionsWorkflowActive()) setEmployeeOptionGuideStep(event.target.value ? 2 : 1);
  }

  if (event.target.id === "securityAssetClass" || event.target.id === "securityAction") {
    toggleTransactionCompFields();
  }

  if (["securityVestingStyle", "securityVestingMode"].includes(event.target.id)) {
    renderVestingSchedulePreview();
  }

  if (event.target.id === "priceKnownInstrument") {
    applyInstrumentToForm(instrumentById(event.target.value), "price");
  }

  if (event.target.id === "securityChartStartDate") {
    state.securityChartStartDate = clampedHistoryDate(event.target.value);
    event.target.value = formatDate(state.securityChartStartDate);
    loadSecurityDetail().catch((error) => { $("securityDetailStatus").textContent = `Error: ${error.message}`; });
  }

  if (event.target.classList?.contains("security-sr-toggle")) {
    state.securityChartLevelPeriods = [...document.querySelectorAll(".security-sr-toggle:checked")]
      .map((input) => input.value);
    loadSecurityDetail().catch((error) => { $("securityDetailStatus").textContent = `Error: ${error.message}`; });
  }

  if (event.target.classList?.contains("security-ma-toggle")) {
    state.securityChartMaWindows = [...document.querySelectorAll(".security-ma-toggle:checked")]
      .map((input) => input.value);
    renderSecurityChart();
  }

  if (event.target.id === "simPersonSource") {
    applySimulationPerson();
    updatePensionActionStates();
  }

  if (event.target.id === "simPeriodFromMode") {
    syncPensionPeriodFromMode();
    updatePensionActionStates();
  }

  if (event.target.id === "simRateFromMode") {
    syncPensionRateFromMode();
    updatePensionActionStates();
  }

  if (event.target.id === "simInsuranceTrack") {
    syncPensionInsuranceTrack({ force: true });
    updatePensionActionStates();
  }

  if (["simDisabilityCoverage", "simSpouseSurvivorsCoverage", "simChildrenSurvivorsCoverage"].includes(event.target.id)) {
    const track = $("simInsuranceTrack");
    if (track) track.value = "custom";
    updatePensionActionStates();
  }

  if (event.target.id === "simBirthDate" && !$("simCurrentAge").value) {
    $("simCurrentAge").value = ageFromBirthDate(dateValue("simBirthDate"));
    updatePensionActionStates();
  }

  if (event.target.id === "backupScheduleFrequency") {
    syncBackupSchedulePickers();
  }

  if (event.target.id === "backupEnabled") {
    syncBackupEnabledControls();
  }

  if (event.target.classList.contains("date-field")) {
    const iso = event.target.id === "reportFrom" || event.target.id === "historyDate" || event.target.id === "securityChartStartDate"
      ? clampedHistoryDate(event.target.value)
      : parseDateInput(event.target.value);
    if (iso) event.target.value = formatDate(iso);
  }
});

document.addEventListener("input", (event) => {
  const pensionIds = [
    "simName", "simBirthDate", "simCurrentAge", "simRetireAge", "simAmount", "simFactor",
    "simPeriodFrom", "simPeriodTo", "simPeriodIncome", "simPeriodContribution", "simPeriodDeposit",
    "simSurvivorsFactor",
    "simRateFrom", "simRateTo", "simRateAnnual",
  ];
  if (pensionIds.includes(event.target.id)) updatePensionActionStates();
  if (["fundKind", "fundPensionId", "fundAmount"].includes(event.target.id)) updateFundActionStates();
  if (["outlookSymbol", "outlookAsOfDate"].includes(event.target.id) && event.target.value.trim()) {
    event.target.removeAttribute("aria-invalid");
  }
  if ([
    "securityQuantity", "securityVestingStartDate", "securityVestingDuration", "securityVestingCliffMonths",
    "securityVestingCliffValue", "securityVestingInterval", "securityVestingInstallmentValue",
  ].includes(event.target.id)) renderVestingSchedulePreview();
  if ([
    "employeeWizardQuantity", "employeeWizardVestingStart", "employeeWizardSingleVestDate",
    "employeeWizardFirstMonths", "employeeWizardFirstValue", "employeeWizardInstallmentValue",
    "employeeWizardInterval", "employeeWizardExpiration",
  ].includes(event.target.id)) renderEmployeeWizardVestingPreview();
});

document.addEventListener("focusin", (event) => {
  if (event.target.classList?.contains("date-field")) {
    openDatePickerFor(event.target);
  }
});

document.addEventListener("click", (event) => {
  if (event.target.classList?.contains("date-field")) {
    openDatePickerFor(event.target);
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
  document.querySelectorAll(".dashboard-section-grid.drag-over").forEach((grid) => grid.classList.remove("drag-over"));
});

document.addEventListener("dragover", (event) => {
  const grid = event.target.closest(".dashboard-section-grid");
  if (!state.dashboard?.edit || !grid) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
  document.querySelectorAll(".dashboard-section-grid.drag-over").forEach((item) => {
    if (item !== grid) item.classList.remove("drag-over");
  });
  grid.classList.add("drag-over");
});

document.addEventListener("drop", (event) => {
  const grid = event.target.closest(".dashboard-section-grid");
  const section = event.target.closest(".dashboard-section");
  if (!state.dashboard?.edit || !grid || !section) return;
  event.preventDefault();
  const sourceId = event.dataTransfer.getData("text/plain");
  grid.classList.remove("drag-over");
  moveDashboardWidgetToPosition(sourceId, section.dataset.dashboardSection, dashboardDropIndex(grid, event));
});

$("refresh").addEventListener("click", () => {
  loadPortfolio({ refresh: true }).catch((error) => { $("status").textContent = `Error: ${error.message}`; });
  loadBanner().catch(() => {});
});
$("apply").addEventListener("click", applyFilter);
$("saveAlert").addEventListener("click", saveAlert);
$("runAlerts").addEventListener("click", runAlerts);
$("addAlertCondition").addEventListener("click", addAlertCondition);
$("cancelAlertEdit").addEventListener("click", () => {
  resetAlertForm();
  $("alertStatus").textContent = "Edit cancelled.";
});
$("addBannerItem").addEventListener("click", addBannerItem);
$("runMarketScreener").addEventListener("click", () => runMarketScreener().catch((error) => { $("marketStatus").textContent = `Error: ${error.message}`; }));
$("resetMarketScreener").addEventListener("click", resetMarketScreener);
$("saveLocalAccount").addEventListener("click", () => saveLocalAccount().catch((error) => { $("accountsStatus").textContent = `Error: ${error.message}`; }));
$("saveEditAccount").addEventListener("click", () => saveEditAccount().catch((error) => { $("editAccountStatus").textContent = `Error: ${error.message}`; }));
$("saveBroker").addEventListener("click", () => saveBroker().catch((error) => { $("brokerStatus").textContent = `Error: ${error.message}`; }));
$("clearBrokerForm").addEventListener("click", clearBrokerForm);
$("saveFamilyMember").addEventListener("click", () => saveFamilyMember().catch((error) => { $("familyStatus").textContent = `Error: ${error.message}`; }));
$("clearFamilyMemberForm").addEventListener("click", clearFamilyMemberForm);
$("attachAccountToMember").addEventListener("click", () => attachAccountToMember().catch((error) => { $("accountOwnershipStatus").textContent = `Error: ${error.message}`; }));
$("attachLocalAccountPerson").addEventListener("click", () => attachFamilyMember("localAccountPersons", "localAccountFamilyMember", "accountsStatus", { single: !accountAllowsMultipleMembers({ type: valueOf("localAccountType") }) }));
$("attachEditAccountPerson").addEventListener("click", () => attachFamilyMember("editAccountPersons", "editAccountFamilyMember", "editAccountStatus", { single: !accountAllowsMultipleMembers({ type: valueOf("editAccountType") }) }));
$("importSource").addEventListener("click", () => importSourceToLocal().catch((error) => { $("accountsStatus").textContent = `Error: ${error.message}`; }));
$("exportData").addEventListener("click", () => exportLocalData().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }));
$("chooseImportData").addEventListener("click", () => $("importDataFile").click());
$("importDataFile").addEventListener("change", (event) => importLocalData(event.target.files?.[0]).catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }).finally(() => { event.target.value = ""; }));
$("runBackupNow").addEventListener("click", () => runBackupNow().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }));
$("downloadBackupsZip").addEventListener("click", () => downloadBackupsZip().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }));
$("saveBackupSettings").addEventListener("click", () => saveBackupSettings().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }));
$("saveTableSettings").addEventListener("click", () => {
  state.tableMaPeriod = $("tableMaPeriod").value;
  saveTableSettings();
  $("settingsStatus").textContent = `Table moving average set to MA ${state.tableMaPeriod}`;
  renderRows(state.items || []);
});
$("saveDisplaySettings").addEventListener("click", () => {
  state.language = valueOf("appLanguage") === "he" ? "he" : "en";
  saveLanguageSettings();
  applyLanguage();
  renderFundsOverview();
  renderSummary(state.items || []);
  renderAnalytics(state.items || []);
  $("settingsStatus").textContent = t("displaySettingsSaved");
});
$("dashboardEdit").addEventListener("click", () => setDashboardEdit(!state.dashboard.edit));
$("dashboardReset").addEventListener("click", resetDashboard);
$("saveManualSecurity").addEventListener("click", () => saveManualSecurity().catch((error) => { $("manualSecurityStatus").textContent = `Error: ${error.message}`; }));
$("saveSecurity").addEventListener("click", () => saveSecurity().catch((error) => { $("securityStatus").textContent = `Error: ${error.message}`; }));
$("newEmployeeOptionGrant").addEventListener("click", beginNewEmployeeOptionGrant);
$("cancelEmployeeOptionWizard").addEventListener("click", hideEmployeeOptionWizard);
$("employeeWizardToVesting").addEventListener("click", () => {
  if (!validateEmployeeWizardGrant()) return;
  if (!dateValue("employeeWizardVestingStart")) setDateField("employeeWizardVestingStart", dateValue("employeeWizardGrantDate"));
  renderEmployeeWizardVestingPreview();
  setEmployeeOptionGuideStep(2);
  requestAnimationFrame(() => employeeWizardFirstField(2)?.focus());
});
$("employeeWizardBackToGrant").addEventListener("click", () => {
  setEmployeeOptionGuideStep(1);
  requestAnimationFrame(() => employeeWizardFirstField(1)?.focus());
});
$("employeeWizardToReview").addEventListener("click", () => {
  if (!validateEmployeeWizardVesting()) return;
  renderEmployeeWizardReview();
  setEmployeeOptionGuideStep(3);
  requestAnimationFrame(() => employeeWizardFirstField(3)?.focus());
});
$("employeeWizardBackToVesting").addEventListener("click", () => {
  setEmployeeOptionGuideStep(2);
  requestAnimationFrame(() => employeeWizardFirstField(2)?.focus());
});
$("saveEmployeeOptionGrant").addEventListener("click", () => saveEmployeeOptionGrant().catch((error) => { $("employeeOptionWizardStatus").textContent = `Error: ${error.message}`; }));
$("saveEmployeeListing").addEventListener("click", () => saveEmployeeListing().catch((error) => { $("employeeListingStatus").textContent = `Error: ${error.message}`; }));
$("saveEmployeeExercise").addEventListener("click", () => saveEmployeeExercise().catch((error) => { $("employeeExerciseStatus").textContent = `Error: ${error.message}`; }));
$("savePositionTransaction").addEventListener("click", () => savePositionTransaction().catch((error) => { $("positionTransactionStatus").textContent = `Error: ${error.message}`; }));
$("positionTransactionAction").addEventListener("change", syncPositionTransactionLimit);
$("runDividendEvents").addEventListener("click", () => runDividendEvents().catch((error) => { $("eventsStatus").textContent = `Error: ${error.message}`; }));
$("saveAlarmSettings").addEventListener("click", saveVestingAlertSettings);
$("clearAlarms").addEventListener("click", clearAlarms);
$("savePrice").addEventListener("click", () => savePrice().catch((error) => { $("priceStatus").textContent = `Error: ${error.message}`; }));
$("saveDetailPrice").addEventListener("click", () => saveSecurityDetailPrice().catch((error) => { $("securityDetailStatus").textContent = `Error: ${error.message}`; }));
$("loadReports").addEventListener("click", () => loadReports().catch((error) => { $("reportsDetails").innerHTML = `<div class="empty">Error: ${esc(error.message)}</div>`; }));
$("exportReportsPdf").addEventListener("click", () => exportReportsPdf().catch((error) => { $("reportsExportStatus").textContent = `Error: ${error.message}`; }));
$("loadFinanceReport").addEventListener("click", () => loadFinanceReport().catch((error) => { $("financeReportStatus").textContent = `Error: ${error.message}`; }));
$("runCompanyOutlook").addEventListener("click", () => loadCompanyOutlook().catch((error) => { $("companyOutlookStatus").textContent = `Error: ${error.message}`; }));
$("runCompanyOutlookBacktest").addEventListener("click", () => loadCompanyOutlookBacktest().catch((error) => { $("companyOutlookStatus").textContent = `Error: ${error.message}`; }));
$("saveHistorySnapshot").addEventListener("click", () => saveHistorySnapshot().catch((error) => { $("historyStatus").textContent = `Error: ${error.message}`; }));
$("captureHistorySnapshot").addEventListener("click", () => captureHistorySnapshot().catch((error) => { $("historyStatus").textContent = `Error: ${error.message}`; }));
$("showFundCreate").addEventListener("click", showFundCreate);
$("cancelFundCreate").addEventListener("click", () => hideFundCreate({ clear: true }));
$("saveFund").addEventListener("click", () => saveFund().catch((error) => { $("fundStatus").textContent = `Error: ${error.message}`; }));
$("saveFundHistory").addEventListener("click", () => saveFundAmountHistory().catch((error) => { $("fundHistoryStatus").textContent = `Error: ${error.message}`; }));
$("cancelFundHistoryEdit").addEventListener("click", () => { resetFundHistoryForm(); $("fundHistoryStatus").textContent = "Edit cancelled"; });
$("saveEditFund").addEventListener("click", () => saveEditFund().catch((error) => { $("editFundStatus").textContent = `Error: ${error.message}`; }));
$("attachFundPerson").addEventListener("click", () => attachFamilyMember("fundPersons", "fundFamilyMember", "fundStatus", { single: true }));
$("attachEditFundPerson").addEventListener("click", () => attachFamilyMember("editFundPersons", "editFundFamilyMember", "editFundStatus", { single: true }));
$("addPensionPeriod").addEventListener("click", addPensionPeriod);
$("addPensionRate").addEventListener("click", addPensionRate);
$("addPensionScenario").addEventListener("click", addPensionScenario);
$("newPensionScenario").addEventListener("click", newPensionScenario);
$("runPensionSimulation").addEventListener("click", () => runPensionSimulation().catch((error) => { $("pensionSimulationStatus").textContent = `Error: ${error.message}`; }));
$("applyBackupSchedule").addEventListener("click", applyBackupSchedule);
$("localAccountLocation").addEventListener("change", () => syncCurrencyFromLocation("localAccountLocation", "localAccountCurrency"));
$("editAccountLocation").addEventListener("change", () => syncCurrencyFromLocation("editAccountLocation", "editAccountCurrency"));
$("brokerCountry").addEventListener("change", () => syncCurrencyFromLocation("brokerCountry", "brokerCurrency"));
$("priceLocation").addEventListener("change", () => syncCurrencyFromLocation("priceLocation", "priceCurrency"));
["manualSecuritySymbol", "manualUnderlyingSymbol", "securitySymbol", "priceSymbol", "financeReportSymbol", "outlookSymbol"].forEach((id) => {
  $(id).addEventListener("blur", () => { $(id).value = cleanSecuritySymbol($(id).value); });
});

async function initializeApp() {
  await loadClientStateFromServer().catch((error) => appWarn("client_state.load_failed", { message: error.message }));
  loadClientStateFromStorage();
  loadPortfolio().catch(reportBackgroundError);
  loadBanner().catch(() => {});
  loadAlerts().catch(() => {});
  loadLocalOptions().catch(reportBackgroundError);
  loadBrokers().catch(reportBackgroundError);
  loadFamilyMembers().catch(reportBackgroundError);
  loadLocalAccounts().catch(reportBackgroundError);
  loadLocalSecurities().catch(reportBackgroundError);
  loadLocalPrices().catch(reportBackgroundError);
  loadEvents().catch(reportBackgroundError);
  loadFunds().catch(reportBackgroundError);
}

initializeApp().catch(reportBackgroundError);
