const HISTORY_START_DATE = "2026-04-14";
const DATE_PLACEHOLDER = "dd/mm/yyyy";
const SECURITY_CHART_MIN_VISIBLE_POINTS = 5;

const state = {
  items: [],
  allPortfolioItems: [],
  portfolioFilterCriteria: null,
  accountTrend: { accounts: [] },
  dashboard: null,
  bannerItems: [],
  configuredBannerItems: [],
  historySnapshots: [],
  tradeHistory: null,
  tradeHistoryLoading: false,
  tradeHistoryPage: 1,
  positionsAccounts: [],
  positionsPeople: [],
  fxRates: {},
  coreFxRates: {},
  bannerFxRates: {},
  baseCurrency: "ILS",
  localAccounts: [],
  manualSecurities: [],
  industryClassifications: [],
  industryCatalog: [],
  industryClassificationTarget: null,
  securityExposureTarget: null,
  localTransactions: [],
  localEvents: [],
  eventDividendSettings: null,
  focusedEventId: "",
  localPrices: [],
  equityCompQuotes: {},
  priceFocus: null,
  securityDetail: null,
  positionTransactionsDetail: null,
  positionTransactionSaving: false,
  editingPositionTransactionId: "",
  securityChartPeriod: "1y",
  securityChartMode: "line",
  securityChartLevelPeriods: ["1y"],
  securityChartMaWindows: ["30"],
  securityChartStartDate: HISTORY_START_DATE,
  securityHistory: [],
  securityHistoryMeta: {},
  securityChartZoom: null,
  localFunds: [],
  activeReportFilters: null,
  activeReport: null,
  fundAmountHistory: [],
  fundHistoryFundId: "",
  editingFundHistoryId: "",
  longTermView: "total",
  longTermIncludePension: true,
  brokers: [],
  familyMembers: [],
  localAccountPersons: [],
  editAccountPersons: [],
  importSkippedAccounts: [],
  editingAccountId: "",
  editingBrokerId: "",
  editingFamilyMemberId: "",
  familyMemberSaving: false,
  deletingFamilyMemberIds: [],
  familyMembersLoaded: false,
  familyStatusMessage: "",
  familyMemberError: "",
  familyMemberErrorField: "",
  editingFundId: "",
  editingManualSecurityId: "",
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
  macroScenarioSettings: null,
  alertData: null,
  alertRefreshTimer: null,
  alertOptions: { metrics: [], operators: [], signals: [], match_modes: [] },
  alertConditions: [],
  editingAlertId: "",
  vestingAlertDays: 30,
  vestingNoticeSaved: false,
  clearedAlarmCount: 0,
  alarmsLoadFailed: false,
  dismissedAlarmIds: [],
  activePensionScenarioIndex: null,
  localOptions: {
    account_types: ["Investment", "Long-Term Savings", "Bank", "ESOP"],
    fund_kinds: ["Pension", "Provident Fund", "Savings Fund"],
    asset_classes: ["EQUITY", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE", "RSU", "EMPLOYEE_STOCK_OPTION", "PRIVATE_STOCK", "STOCK_OPTION"],
    instrument_types: ["STOCK", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE", "EMPLOYEE_STOCK_OPTION", "PRIVATE_STOCK", "STOCK_OPTION"],
    option_types: ["CALL", "PUT"],
    issuer_listing_statuses: ["PRIVATE", "PUBLIC"],
  },
  optionsReady: false,
  portfolioReady: false,
  tableMaPeriod: "30",
  backupSettings: null,
  apiAccess: null,
  mcpAccess: null,
  pendingFullRestoreFile: null,
  pendingFullRestoreInspection: null,
  riskSnapshot: null,
  auth: { user: null, csrfToken: "", forcedPasswordChange: false },
  users: [],
  authenticatedAppStarted: false,
  language: "he",
};

const $ = (id) => document.getElementById(id);

const DASHBOARD_WIDGETS = [
  { id: "portfolio_value", title: "Portfolio value", view: "basic", size: "wide", area: "investments" },
  { id: "long_term_savings", title: "Long-term savings", view: "basic", size: "wide", area: "long_term" },
  { id: "account_trend", title: "Account value trend", view: "basic", size: "wide", area: "investments" },
  { id: "long_term", title: "Long-term funds", view: "basic", size: "wide", area: "long_term" },
  { id: "market_cost", title: "Market vs cost basis", view: "basic", size: "wide", area: "investments" },
  { id: "asset_mix", title: "Asset mix", view: "basic", size: "compact", area: "investments" },
  { id: "cash_currency", title: "Cash by currency", view: "basic", size: "compact", area: "investments" },
  { id: "industry_split", title: "Industry split", view: "basic", size: "wide", area: "investments" },
  { id: "top_holdings", title: "Top holdings", view: "basic", size: "wide", area: "investments" },
  { id: "bond_currency", title: "Bonds by currency", view: "basic", size: "compact", area: "investments" },
  { id: "coverage", title: "Provider data coverage", view: "expanded", size: "medium", area: "investments" },
  { id: "currency", title: "Currency allocation", view: "expanded", size: "compact", area: "investments" },
  { id: "equity_comp", title: "Equity compensation", view: "expanded", size: "wide", area: "employee" },
  { id: "profit", title: "Unrealized P/L by holding", view: "expanded", size: "wide", area: "investments" },
  { id: "snapshot", title: "Portfolio snapshot", view: "expanded", size: "wide", area: "investments" },
];

const DASHBOARD_STORAGE_KEY = "portfolioAnalyzer.dashboard";
const DASHBOARD_ACCOUNT_STORAGE_KEY = "portfolioAnalyzer.dashboard.accountTrend";
const DASHBOARD_LONG_TERM_STORAGE_KEY = "portfolioAnalyzer.dashboard.longTerm";
const TABLE_SETTINGS_STORAGE_KEY = "portfolioAnalyzer.tableSettings";
const LANGUAGE_STORAGE_KEY = "portfolioAnalyzer.language";
const PENSION_SIMULATION_STORAGE_KEY = "portfolioAnalyzer.pensionSimulation";
const MACRO_SCENARIO_STORAGE_KEY = "portfolioAnalyzer.macroScenarios";
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
const DASHBOARD_AREAS = ["all", "investments", "long_term", "employee"];
const DASHBOARD_AREA_FEATURES = {
  investments: ["portfolio_value", "account_trend", "asset_mix", "top_holdings", "bond_currency"],
  long_term: ["long_term_savings", "long_term"],
  employee: ["equity_comp"],
};
const SUPPORT_RESISTANCE_PERIODS = [
  { key: "5y", label: "5Y" },
  { key: "3y", label: "3Y" },
  { key: "1y", label: "1Y" },
  { key: "6m", label: "6M" },
  { key: "1m", label: "1M" },
];

const REGION_CODES = "AF AX AL DZ AS AD AO AI AQ AG AR AM AW AU AT AZ BS BH BD BB BY BE BZ BJ BM BT BO BQ BA BW BV BR IO BN BG BF BI CV KH CM CA KY CF TD CL CN CX CC CO KM CG CD CK CR CI HR CU CW CY CZ DK DJ DM DO EC EG SV GQ ER EE SZ ET FK FO FJ FI FR GF PF TF GA GM GE DE GH GI GR GL GD GP GU GT GG GN GW GY HT HM VA HN HK HU IS IN ID IR IQ IE IM IL IT JM JP JE JO KZ KE KI KP KR KW KG LA LV LB LS LR LY LI LT LU MO MG MW MY MV ML MT MH MQ MR MU YT MX FM MD MC MN ME MS MA MZ MM NA NR NP NL NC NZ NI NE NG NU NF MK MP NO OM PK PW PA PG PY PE PH PN PL PT PR QA RE RO RU RW BL SH KN LC MF PM VC WS SM ST SA SN RS SC SL SG SX SK SI SB SO ZA GS SS ES LK SD SR SJ SE CH SY TW TJ TZ TH TL TG TK TO TT TN TR TM TC TV UG UA AE GB US UM UY UZ VU VE VN VG VI WF EH YE ZM ZW".split(" ");
const ACCOUNT_COUNTRIES = ["USA", "Israel"];
const ACCOUNT_COUNTRY_CODES = { USA: "US", Israel: "IL" };
const MARKET_OPTIONS = ["NASDAQ", "NYSE", "AMEX", "NYSEARCA", "OTC", "TASE"];
const FALLBACK_CURRENCIES = "USD ILS EUR GBP JPY CHF CAD AUD NZD CNY HKD SGD INR KRW MXN BRL ARS CLP COP ZAR AED SAR TRY PLN CZK HUF SEK NOK DKK ISK RUB UAH RON BGN HRK RSD THB IDR MYR PHP VND TWD ILS".split(" ");
const SUPPORTED_MANAGEMENT_CURRENCIES = ["ILS", "USD", "EUR"];
const HEBREW_CURRENCY_NAMES = { ILS: "שקל חדש", USD: "דולר אמריקאי", EUR: "אירו" };
const TRANSLATIONS = {
  en: {
    appName: "Portfolio analyzer",
    brand: "Portfolio",
    overview: "Home",
    loadingPortfolio: "Loading portfolio",
    readingCachedAnalytics: "Reading cached analytics",
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
    positions: "Positions",
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
    macroScenarios: "US–Israel Scenarios",
    alerts: "Alerts",
    marketBanner: "Market Banner",
    system: "System",
    users: "Users",
    settings: "Settings",
    about: "About",
    help: "Help",
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
    condition: "condition",
    conditions: "conditions",
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
    overview: "ראשי",
    loadingPortfolio: "טוען תיק",
    readingCachedAnalytics: "קורא נתוני ניתוח שמורים",
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
    positions: "פוזיציות",
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
    macroScenarios: "תרחישי ארה״ב–ישראל",
    alerts: "התראות",
    marketBanner: "סרגל שוק",
    system: "מערכת",
    users: "משתמשים",
    settings: "הגדרות",
    about: "אודות",
    help: "עזרה",
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
    condition: "תנאי",
    conditions: "תנאים",
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
  const text = TRANSLATIONS[state.language]?.[key] || TRANSLATIONS.en[key] || key;
  return window.PortfolioI18n?.translate(text, state.language) || text;
}

const ALERT_METRIC_LOCALIZATIONS = {
  he: {
    dividend_yield_percent: { label: "תשואת דיבידנד", guidance: { description: "סך הדיבידנדים השנתיים למניה חלקי מחיר המניה הנוכחי.", example: "תשואת דיבידנד > 2.5%", use: "מציג את שיעור ההכנסה הנוכחי, אך אינו מבטיח שהדיבידנד בטוח." } },
    dividend_growth_percent: { label: "צמיחת דיבידנד", guidance: { description: "השינוי בדיבידנד השנתי לעומת השנה הקודמת.", example: "צמיחת דיבידנד > 5%", use: "מציג אם תשלומי הדיבידנד לבעלי המניות גדלים או קטנים." } },
    market_cap_millions: { label: "שווי שוק", guidance: { description: "שווי השוק הכולל של כל מניות החברה, במיליוני דולרים.", example: "שווי שוק > 10,000 מיליון דולר", use: "מבדיל בין חברות גדולות ומבוססות לבין סיכון של חברות קטנות יותר." } },
    annual_net_income_millions: { label: "רווח נקי שנתי", guidance: { description: "רווח לאחר הוצאות ומס בדוח השנתי האחרון, במיליוני דולרים.", example: "רווח נקי שנתי > 500 מיליון דולר", use: "מאשר שהרווח המדווח חיובי ומהותי." } },
    profit_market_cap_percent: { label: "רווח / שווי שוק", guidance: { description: "הרווח הנקי השנתי האחרון חלקי שווי השוק; מדד הדומה לתשואת רווחים.", example: "רווח / שווי שוק > 5%", use: "משווה בין הרווח לשווי, אך אינו המלצת תמחור." } },
    price_earnings_ratio: { label: "מכפיל רווח", guidance: { description: "שווי השוק חלקי הרווח הנקי השנתי האחרון.", example: "מכפיל רווח < 20", use: "מציג כמה המשקיעים משלמים עבור כל יחידת רווח נוכחי." } },
    revenue_growth_percent: { label: "צמיחת הכנסות", guidance: { description: "השינוי השנתי במכירות לפי הדוח השנתי האחרון.", example: "צמיחת הכנסות > 10%", use: "מציג אם הביקוש והיקף הפעילות של החברה מתרחבים." } },
    net_income_growth_percent: { label: "צמיחת רווח", guidance: { description: "השינוי השנתי ברווח הנקי לפי הדוח השנתי האחרון.", example: "צמיחת רווח > 10%", use: "מציג אם הרווחים משתפרים מהר יותר או לאט יותר מבעבר." } },
    net_margin_percent: { label: "שיעור רווח נקי", guidance: { description: "הרווח הנקי כאחוז מההכנסות.", example: "שיעור רווח נקי > 15%", use: "מציג כמה מכל שקל הכנסה נשאר לאחר כל ההוצאות." } },
    free_cash_flow_millions: { label: "תזרים מזומנים חופשי", guidance: { description: "מזומן שנותר לאחר עלויות תפעול והשקעות הון, במיליוני דולרים.", example: "תזרים מזומנים חופשי > 250 מיליון דולר", use: "מציג מזומן הזמין להפחתת חוב, דיבידנדים, רכישות עצמיות או השקעה מחדש." } },
    free_cash_flow_yield_percent: { label: "תשואת תזרים מזומנים חופשי", guidance: { description: "תזרים המזומנים החופשי חלקי שווי השוק.", example: "תשואת תזרים חופשי > 4%", use: "משווה את ייצור המזומנים למחיר שהמשקיעים משלמים עבור העסק." } },
    debt_to_revenue_percent: { label: "חוב / הכנסות", guidance: { description: "סך החוב כאחוז מההכנסות השנתיות.", example: "חוב / הכנסות < 100%", use: "מסמן מינוף ביחס לגודל הפעילות." } },
    current_ratio: { label: "יחס שוטף", guidance: { description: "נכסים שוטפים חלקי התחייבויות שוטפות.", example: "יחס שוטף > 1.5", use: "מצביע על נזילות לטווח קצר, אך אינו מדד מלא ליכולת פירעון." } },
    unrealized_profit_percent: { label: "רווח/הפסד לא ממומש בהחזקה", guidance: { description: "הרווח או ההפסד הנוכחי בהחזקה ביחס לעלות הקנייה.", example: "רווח/הפסד לא ממומש < ‎-15%", use: "מדגיש החזקות שדורשות בדיקה, אך אינו הוראת מכירה." } },
    holding_allocation_percent: { label: "הקצאה בתיק", guidance: { description: "אחוז ההחזקה מתוך שווי התיק הכולל.", example: "הקצאה בתיק > 10%", use: "מזהה סיכון ריכוזיות וגודל פוזיציה." } },
    price_vs_ma30_percent: { label: "מחיר לעומת ממוצע נע 30", guidance: { description: "המחיר הנוכחי ביחס לממוצע הנע של 30 ימי מסחר.", example: "מחיר לעומת ממוצע נע 30 > 5%", use: "מציג מומנטום מחיר קצר טווח ביחס למגמה האחרונה." } },
    ma30_slope_percent: { label: "שיפוע ממוצע נע 30", guidance: { description: "הכיוון האחרון של הממוצע הנע ל־30 ימי מסחר.", example: "שיפוע ממוצע נע 30 > 0%", use: "מציג אם המגמה האחרונה עולה או יורדת." } },
    relative_volume_20d: { label: "מחזור יחסי לעומת 20 ימים", guidance: { description: "מחזור המסחר היום חלקי המחזור הממוצע ב־20 ימי המסחר האחרונים.", example: "מחזור יחסי > 1.5×", use: "מסמן מסחר חריג שיכול לאשש או לאתגר תנועת מחיר." } },
    confirmed_breakout: { label: "פריצת התנגדות מאושרת", guidance: { description: "האם המחיר חצה רמת התנגדות מחושבת עם אישור.", example: "פריצה מאושרת = 1", use: "מסמן אירוע טכני למחקר; רמות התנגדות הן הערכות." } },
    price_from_high_1y_percent: { label: "מחיר מהשיא השנתי", guidance: { description: "מרחק המחיר הנוכחי מהמחיר הגבוה ביותר בשנה האחרונה.", example: "מחיר מהשיא השנתי < ‎-20%", use: "מציג ירידה מהשיא השנתי, ולא אם מניה זולה." } },
  },
};
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

function bidiIsolate(value, direction = "auto") {
  const opener = direction === "rtl" ? "\u2067" : direction === "ltr" ? "\u2066" : "\u2068";
  return `${opener}${String(value || "")}\u2069`;
}

function countryName(code, language = state.language) {
  try {
    const names = typeof Intl.DisplayNames === "function"
      ? new Intl.DisplayNames([language === "he" ? "he-IL" : "en"], { type: "region" })
      : null;
    return names?.of(code) || code;
  } catch {
    return code;
  }
}

function countryCodeForLocation(location) {
  const text = String(location || "").trim().toLowerCase();
  if (!text) return "";
  if (["usa", "us", "u.s.", "u.s.a.", "united states", "united states of america", "ארצות הברית"].includes(text)) return "US";
  if (["israel", "il", "state of israel", "ישראל"].includes(text)) return "IL";
  return REGION_CODES.find((code) => (
    code.toLowerCase() === text
    || countryName(code, "en").toLowerCase() === text
    || countryName(code, "he").toLowerCase() === text
  )) || "";
}

function countryDisplayLabel(location) {
  const code = countryCodeForLocation(location);
  if (!code) return String(location || "").trim();
  const label = state.language === "he"
    ? `${countryName(code)} ${flagFor(code)}`
    : `${flagFor(code)} ${countryName(code)}`;
  return state.language === "he" ? bidiIsolate(label, "rtl") : label;
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

function currencyName(code) {
  if (state.language === "he" && HEBREW_CURRENCY_NAMES[code]) return HEBREW_CURRENCY_NAMES[code];
  try {
    const names = typeof Intl.DisplayNames === "function"
      ? new Intl.DisplayNames([locale() || navigator.language || "en"], { type: "currency" })
      : null;
    return names?.of(code) || code;
  } catch {
    return code;
  }
}

function currencyDisplayLabel(code) {
  const normalized = String(code || "").trim().toUpperCase();
  if (!normalized) return "";
  const label = state.language === "he"
    ? `${currencyName(normalized)} ${currencySymbol(normalized)}`
    : `${currencySymbol(normalized)} ${normalized}`;
  return state.language === "he" ? bidiIsolate(label, "rtl") : label;
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
  const { headers: requestedHeaders = {}, ...fetchOptions } = options;
  const headers = {
    "Content-Type": "application/json",
    ...requestedHeaders,
  };
  if (!["GET", "HEAD", "OPTIONS"].includes(String(method).toUpperCase()) && state.auth.csrfToken) {
    headers["X-CSRF-Token"] = state.auth.csrfToken;
  }
  try {
    const response = await fetch(path, {
      ...fetchOptions,
      method,
      headers,
    });
    appLog("api.response", { method, endpoint, status: response.status, ms: Math.round(performance.now() - started) });
    if (!response.ok) {
      let message = `${response.status} ${response.statusText}`;
      let code = "";
      let requestId = "";
      try {
        const data = await response.json();
        message = data.detail?.message || (typeof data.detail === "string" ? data.detail : message);
        code = data.detail?.code || "";
        requestId = data.detail?.request_id || "";
      } catch {
        // Keep the HTTP status text when the API returns no JSON body.
      }
      if (response.status === 401 || code === "authentication_required") showLogin();
      if (code === "password_change_required") showPasswordChange({ forced: true });
      const failure = new Error(message);
      failure.code = code;
      failure.requestId = requestId;
      throw failure;
    }
    return response.json();
  } catch (error) {
    appWarn("api.error", { method, endpoint, message: error.message, request_id: error.requestId || undefined });
    throw error;
  }
}

function assistantUi() {
  const owner = currentUser()?.id || "";
  if (!state.assistant || state.assistant.owner !== owner) {
    state.assistant = {
      owner, chats: [], chat: null, enabled: null, maxChats: 10,
      loading: false, selecting: false, creating: false, sending: false, pendingPrompt: "", status: "", requestId: "", retry: "",
      deleteChatId: "", deleting: false,
      loadVersion: 0, selectVersion: 0, drafts: {}, settingsVersion: 0,
    };
    if ($("assistantPrompt")) $("assistantPrompt").value = "";
    if ($("assistantLauncher")) $("assistantLauncher").value = "";
  }
  return state.assistant;
}

function assistantText(template, values = {}) {
  return Object.entries(values).reduce((text, [key, value]) => text.replaceAll(`{${key}}`, String(value)), t(template));
}

function assistantChatLabel(chat) {
  return chat?.message_count || chat?.messages?.length ? String(chat.title || t("Untitled chat")) : t("New chat");
}

function assistantUserName() {
  const user = currentUser();
  return [user?.first_name, user?.last_name].map((value) => String(value || "").trim()).filter(Boolean).join(" ")
    || String(user?.username || "").trim() || t("Signed-in user");
}

function assistantReferenceId(value) {
  const reference = String(value || "").trim();
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(reference) ? reference : "";
}

function assistantAnswerText(content) {
  const prefix = /^\s*(?:(?:[-*+]\s+|\d+[.)]\s+))?(?:\*\*|__|`)?\s*(?:sources?|מקור|מקורות)\s*(?:\*\*|__|`)?\s*[:：]/i;
  const endpoint = /^\s*(?:(?:[-*+]\s+|\d+[.)]\s+))?(?:\*\*|__|`)?\s*GET(?:\*\*|__|`)?\s+\/?api\//i;
  return String(content || "").split(/\r?\n/).filter((line) => !prefix.test(line) && !endpoint.test(line)).join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function assistantMessageText(message) {
  if (message.role === "user") return String(message.content || "");
  if (message.support_status === "unsupported") return t("This request is not supported by the available app data or approved read tools.");
  return assistantAnswerText(message.content);
}

function assistantMessageMetadata(message) {
  if (message.role === "user" || message.support_status !== "unsupported") return "";
  const reference = assistantReferenceId(message.request_id);
  return `<p class="assistant-message-outcome"><span>${esc(t("Unsupported request"))}</span>${reference ? `<span>${esc(assistantText("Reference: {id}", { id: `\u2066${reference}\u2069` }))}</span>` : ""}</p>`;
}

function assistantMessageHtml(message) {
  const text = assistantMessageText(message);
  if (message.role === "user" || message.support_status === "unsupported" || !window.PortfolioAssistantFormat) return esc(text);
  return window.PortfolioAssistantFormat.render(text, {
    tableLabel: t("Answer table. Scroll horizontally to see all columns."),
    codeLabel: t("Code block. Scroll to read all code."), columnLabel: t("Column {count}"),
    tones: { positive: t("Positive"), negative: t("Negative"), warning: t("Warning"), info: t("Information"), muted: t("Note") },
  });
}

function assistantStatusText(ui) {
  if (ui.sending) return t("Reading approved portfolio data…");
  if (ui.loading) return t("Loading your chats…");
  if (ui.status) {
    const reference = assistantReferenceId(ui.requestId);
    return [t(ui.status), reference ? assistantText("Reference: {id}", { id: `\u2066${reference}\u2069` }) : ""].filter(Boolean).join(" ");
  }
  if (ui.enabled === false) return t("Connect the local Codex bridge or configure an AI provider. Saved chats are still available.");
  return "";
}

function renderAssistantChat() {
  if (!$("assistantChatList")) return;
  const ui = assistantUi();
  const busy = ui.loading || ui.sending || ui.creating || ui.deleting;
  $("assistantHistoryCount").textContent = assistantText("{count} of {max} saved chats", { count: fmt(ui.chats.length, 0), max: fmt(ui.maxChats, 0) });
  $("assistantChatList").innerHTML = ui.chats.length ? ui.chats.map((chat) => `
    <div class="assistant-chat-row"><button class="assistant-chat-item${chat.id === ui.chat?.id ? " active" : ""}" type="button" data-assistant-chat="${esc(chat.id)}"${chat.id === ui.chat?.id ? ' aria-current="true"' : ""}${busy ? " disabled" : ""}>
      <span class="assistant-chat-name" dir="auto" data-i18n-skip>${esc(assistantChatLabel(chat))}</span>
      <time datetime="${esc(chat.updated_at || "")}">${esc(chat.updated_at ? formatDateTime(chat.updated_at) : "")}</time>
    </button><button class="secondary assistant-chat-delete" type="button" data-delete-assistant-chat="${esc(chat.id)}" aria-label="${esc(assistantText("Delete chat: {title}", { title: assistantChatLabel(chat) }))}" title="${esc(t("Delete chat"))}"${busy ? " disabled" : ""}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 10v7M14 10v7"/></svg></button></div>`).join("") : `<p class="assistant-empty">${esc(t(ui.loading ? "Loading your chats…" : "No saved chats yet."))}</p>`;
  const deleteTarget = ui.chats.find((chat) => chat.id === ui.deleteChatId);
  $("assistantDeleteConfirm").hidden = !deleteTarget;
  $("assistantDeleteChatName").textContent = deleteTarget ? assistantChatLabel(deleteTarget) : "";
  $("confirmAssistantDelete").disabled = busy;
  $("cancelAssistantDelete").disabled = busy;
  $("confirmAssistantDelete").textContent = t(ui.deleting ? "Deleting chat…" : "Delete chat");
  const title = $("assistantChatTitle");
  title.textContent = assistantChatLabel(ui.chat);
  title.setAttribute("data-i18n-skip", "");
  const messages = [...(ui.chat?.messages || [])];
  if (ui.sending && ui.pendingPrompt) messages.push({ role: "user", content: ui.pendingPrompt });
  $("assistantMessages").innerHTML = messages.length ? messages.map((message) => `
    <article class="assistant-message assistant-message-${message.role === "user" ? "user" : "answer"}">
      <div class="assistant-message-meta"><b dir="auto"${message.role === "user" ? " data-i18n-skip" : ""}>${esc(message.role === "user" ? assistantUserName() : t("Portfolio assistant"))}</b>${message.created_at ? `<time datetime="${esc(message.created_at)}">${esc(formatDateTime(message.created_at))}</time>` : ""}</div>
      <div class="assistant-message-content${message.role === "user" ? " assistant-message-plain" : " assistant-message-rich"}" dir="auto" data-i18n-skip>${assistantMessageHtml(message)}</div>
      ${assistantMessageMetadata(message)}
    </article>`).join("") : `<div class="assistant-empty"><p>${esc(t("Ask a question about your portfolio."))}</p><p>${esc(t("Answers use approved app data. If the data is missing, the assistant will say so."))}</p></div>`;
  $("assistantMessages").setAttribute("aria-busy", String(ui.sending || ui.loading));
  $("assistantStatus").textContent = assistantStatusText(ui);
  $("newAssistantChat").disabled = busy;
  $("assistantPrompt").disabled = ui.sending || ui.selecting || ui.deleting;
  $("askAssistant").disabled = busy || ui.enabled !== true;
  $("askAssistant").textContent = t(ui.sending ? "Sending…" : "Send");
  $("retryAssistant").hidden = !ui.retry || busy;
}

function saveAssistantDraft() {
  const ui = assistantUi();
  ui.drafts[ui.chat?.id || "new"] = $("assistantPrompt").value;
}

function requestAssistantChatDeletion(chatId) {
  const ui = assistantUi();
  if (ui.loading || ui.sending || ui.creating || ui.deleting || !ui.chats.some((chat) => chat.id === chatId)) return;
  saveAssistantDraft();
  ui.deleteChatId = chatId;
  ui.status = "";
  ui.requestId = "";
  ui.retry = "";
  renderAssistantChat();
  $("cancelAssistantDelete").focus();
}

function cancelAssistantChatDeletion() {
  const ui = assistantUi();
  if (ui.deleting) return;
  const chatId = ui.deleteChatId;
  ui.deleteChatId = "";
  ui.status = "";
  ui.requestId = "";
  renderAssistantChat();
  const buttons = $("assistantChatList").querySelectorAll?.("[data-delete-assistant-chat]") || [];
  [...buttons].find((button) => button.dataset.deleteAssistantChat === chatId)?.focus();
}

async function deleteAssistantChat() {
  const ui = assistantUi();
  const chatId = ui.deleteChatId;
  if (!chatId || ui.loading || ui.sending || ui.creating || ui.deleting) return;
  saveAssistantDraft();
  const deletingCurrent = ui.chat?.id === chatId;
  ++ui.loadVersion;
  ++ui.selectVersion;
  ui.deleting = true;
  ui.status = "Deleting chat…";
  ui.requestId = "";
  ui.retry = "";
  renderAssistantChat();
  try {
    const data = await api(`/api/assistant/chats/${encodeURIComponent(chatId)}`, { method: "DELETE" });
    if (assistantUi() !== ui) return;
    if (data.deleted !== true || data.chat_id !== chatId || !Array.isArray(data.chats)) throw new Error("Invalid chat deletion response");
    ui.chats = data.chats;
    ui.maxChats = data.max_chats || ui.maxChats;
    delete ui.drafts[chatId];
    ui.deleteChatId = "";
    ui.deleting = false;
    ui.status = "Chat deleted.";
    if (deletingCurrent) {
      ui.chat = null;
      const nextId = ui.chats[0]?.id;
      $("assistantPrompt").value = nextId ? ui.drafts[nextId] || "" : "";
      renderAssistantChat();
      if (nextId) await selectAssistantChat(nextId, { preserveDraft: true });
      if (!$("assistantModal").hidden) $("assistantPrompt").focus();
    }
  } catch (error) {
    if (assistantUi() !== ui) return;
    setAssistantFailure(ui, error, "Could not delete this chat. Your chat and draft are unchanged. Try again.");
  } finally {
    if (assistantUi() === ui) {
      ui.deleting = false;
      renderAssistantChat();
    }
  }
}

function assistantFailure(error, fallback) {
  const messages = {
    assistant_unavailable: "The assistant is unavailable. Reconnect the local Codex bridge and try again.",
    assistant_limit: "The request reached its read limit. Try a narrower question.",
    assistant_invalid_response: "The assistant returned an invalid answer. Your draft is kept. Try again.",
    assistant_invalid_request: "The question could not be accepted. Check your draft and try again.",
    assistant_busy: "A chat request is already running. Wait for it to finish, then retry.",
    assistant_chat_not_found: "This chat is no longer available. Start a new chat or refresh your history.",
    assistant_failed: "The assistant could not complete this request. Your draft is kept. Try again.",
    assistant_unsupported: "This request is not supported by the available app data or approved read tools.",
  };
  if (messages[error?.code]) return messages[error.code];
  return /not configured/i.test(String(error?.message || ""))
    ? "Connect the local Codex bridge or configure an AI provider. Saved chats are still available."
    : /limit|read limit/i.test(String(error?.message || ""))
      ? "The request reached its read limit. Try a narrower question."
      : fallback;
}

function setAssistantFailure(ui, error, fallback) {
  ui.status = assistantFailure(error, fallback);
  ui.requestId = assistantReferenceId(error?.requestId);
}

async function selectAssistantChat(chatId, { preserveDraft = false } = {}) {
  const ui = assistantUi();
  if (ui.sending || ui.deleting || ui.creating) return;
  if (!preserveDraft) saveAssistantDraft();
  const version = ++ui.selectVersion;
  ui.loading = true;
  ui.selecting = !preserveDraft;
  if (!preserveDraft) { ui.retry = ""; ui.status = ""; ui.requestId = ""; ui.deleteChatId = ""; }
  renderAssistantChat();
  try {
    const chat = await api(`/api/assistant/chats/${encodeURIComponent(chatId)}`);
    if (assistantUi() !== ui || version !== ui.selectVersion) return;
    ui.chat = chat;
    if (!preserveDraft) $("assistantPrompt").value = ui.drafts[chat.id] || "";
    ui.loading = false;
    ui.selecting = false;
    renderAssistantChat();
    $("assistantMessages").scrollTop = $("assistantMessages").scrollHeight;
  } catch (error) {
    if (assistantUi() !== ui || version !== ui.selectVersion) return;
    ui.loading = false;
    ui.selecting = false;
    setAssistantFailure(ui, error, "Could not load this chat. Retry to refresh your saved chats.");
    ui.retry = "load";
    renderAssistantChat();
  }
}

async function loadAssistantChats() {
  const ui = assistantUi();
  if (ui.sending || ui.creating || ui.deleting) { renderAssistantChat(); return; }
  const version = ++ui.loadVersion;
  ++ui.selectVersion;
  ui.selecting = false;
  ui.loading = true;
  ui.status = "";
  ui.requestId = "";
  ui.deleteChatId = "";
  ui.retry = "";
  renderAssistantChat();
  const results = await Promise.allSettled([api("/api/assistant/chats"), api("/api/assistant/status")]);
  if (assistantUi() !== ui || version !== ui.loadVersion) return;
  const [history, service] = results;
  if (service.status === "fulfilled") {
    ui.enabled = Boolean(service.value.enabled);
  } else {
    ui.enabled = null;
    setAssistantFailure(ui, service.reason, "Could not check the assistant connection. Retry to reconnect.");
    ui.retry = "load";
  }
  ui.loading = false;
  if (history.status !== "fulfilled") {
    setAssistantFailure(ui, history.reason, "Could not load your chats. Retry to reconnect.");
    ui.retry = "load";
    renderAssistantChat();
    return;
  }
  ui.chats = history.value.chats || [];
  ui.maxChats = history.value.max_chats || 10;
  if (ui.chat && !ui.chats.some((chat) => chat.id === ui.chat.id)) ui.chat = null;
  const selected = ui.chat?.id || ui.chats[0]?.id;
  renderAssistantChat();
  if (selected) await selectAssistantChat(selected, { preserveDraft: true });
}

async function newAssistantChat() {
  const ui = assistantUi();
  if (ui.loading || ui.sending || ui.deleting) return;
  saveAssistantDraft();
  ++ui.loadVersion;
  ++ui.selectVersion;
  ui.loading = true;
  ui.creating = true;
  ui.status = "";
  ui.requestId = "";
  ui.deleteChatId = "";
  ui.retry = "";
  renderAssistantChat();
  try {
    const data = await api("/api/assistant/chats", { method: "POST", body: JSON.stringify({}) });
    if (assistantUi() !== ui) return;
    ui.chat = data.chat;
    ui.chats = data.chats || [];
    ui.maxChats = data.max_chats || ui.maxChats;
    $("assistantPrompt").value = "";
    ui.loading = false;
    ui.creating = false;
    renderAssistantChat();
    $("assistantPrompt").focus();
  } catch (error) {
    if (assistantUi() !== ui) return;
    ui.loading = false;
    ui.creating = false;
    setAssistantFailure(ui, error, "Could not start a new chat. Your current chat is unchanged. Try again.");
    renderAssistantChat();
  }
}

async function askPortfolioAssistant() {
  const ui = assistantUi();
  if (ui.sending || ui.loading || ui.creating || ui.deleting || ui.enabled !== true) return;
  const prompt = $("assistantPrompt").value.trim();
  if (!prompt) {
    ui.status = "Enter a question first.";
    ui.requestId = "";
    renderAssistantChat();
    $("assistantPrompt").focus();
    return;
  }
  ++ui.loadVersion;
  ++ui.selectVersion;
  ui.sending = true;
  ui.pendingPrompt = prompt;
  ui.status = "";
  ui.requestId = "";
  ui.deleteChatId = "";
  ui.retry = "";
  renderAssistantChat();
  $("assistantMessages").scrollTop = $("assistantMessages").scrollHeight;
  try {
    const result = await api("/api/assistant/questions", {
      method: "POST", body: JSON.stringify({ prompt, language: state.language, ...(ui.chat?.id ? { chat_id: ui.chat.id } : {}) }),
    });
    if (assistantUi() !== ui) return;
    delete ui.drafts[ui.chat?.id || "new"];
    ui.chat = result.chat;
    ui.chats = result.chats || [];
    ui.maxChats = result.max_chats || ui.maxChats;
    $("assistantPrompt").value = "";
    ui.status = result.support_status === "unsupported" ? "Unsupported request" : "Answer saved in this chat.";
  } catch (error) {
    if (assistantUi() !== ui) return;
    setAssistantFailure(ui, error, "Could not send your question. Your draft is kept. Retry when ready.");
    ui.retry = "send";
  } finally {
    if (assistantUi() === ui) {
      ui.sending = false;
      ui.pendingPrompt = "";
      renderAssistantChat();
      $("assistantMessages").scrollTop = $("assistantMessages").scrollHeight;
      if (!$("assistantModal").hidden) $("assistantPrompt").focus();
    }
  }
}

function openAssistantFromLauncher(event) {
  if (event?.isComposing || !$("assistantLauncher").value) return;
  const draft = $("assistantLauncher").value;
  const ui = assistantUi();
  if (ui.sending || ui.deleting) return;
  $("assistantLauncher").value = "";
  $("assistantPrompt").value = [$("assistantPrompt").value, draft].filter(Boolean).join(" ");
  saveAssistantDraft();
  openModal("assistantModal", $("assistantLauncher"));
  requestAnimationFrame(() => {
    $("assistantPrompt").focus();
    $("assistantPrompt").setSelectionRange($("assistantPrompt").value.length, $("assistantPrompt").value.length);
  });
}

async function loadAssistantSettings() {
  const ui = assistantUi();
  const version = ++ui.settingsVersion;
  $("saveAssistantSettings").disabled = true;
  $("assistantSettingsStatus").textContent = t("Loading chat settings…");
  try {
    const data = await api("/api/settings/assistant");
    if (assistantUi() !== ui || version !== ui.settingsVersion) return;
    ui.maxChats = data.max_chats || 10;
    $("assistantMaxChats").value = ui.maxChats;
    $("assistantSettingsStatus").textContent = "";
  } catch {
    if (assistantUi() !== ui || version !== ui.settingsVersion) return;
    $("assistantSettingsStatus").textContent = t("Could not load chat settings. Reopen this section to retry.");
  } finally {
    if (assistantUi() === ui && version === ui.settingsVersion) $("saveAssistantSettings").disabled = false;
  }
}

async function saveAssistantSettings() {
  const ui = assistantUi();
  const maxChats = Number($("assistantMaxChats").value);
  if (!Number.isInteger(maxChats) || maxChats < 1 || maxChats > 100) {
    $("assistantSettingsStatus").textContent = t("Enter a whole number from 1 to 100.");
    return;
  }
  $("saveAssistantSettings").disabled = true;
  $("assistantSettingsStatus").textContent = t("Saving chat settings…");
  try {
    const data = await api("/api/settings/assistant", { method: "PUT", body: JSON.stringify({ max_chats: maxChats }) });
    if (assistantUi() !== ui) return;
    ui.maxChats = data.max_chats;
    ui.chats = data.chats || ui.chats;
    if (ui.chat && !ui.chats.some((chat) => chat.id === ui.chat.id)) {
      ui.chat = null;
      $("assistantPrompt").value = "";
    }
    $("assistantSettingsStatus").textContent = t("Chat settings saved. Older chats beyond the limit have been removed.");
    renderAssistantChat();
  } catch {
    if (assistantUi() !== ui) return;
    $("assistantSettingsStatus").textContent = t("Could not save chat settings. Your saved limit is unchanged. Try again.");
  } finally {
    if (assistantUi() === ui) $("saveAssistantSettings").disabled = false;
  }
}

function loggingSettingsUi() {
  const owner = currentUser()?.id || "";
  if (!state.loggingSettings || state.loggingSettings.owner !== owner) {
    state.loggingSettings = { owner, loading: false, saving: false, status: "", version: 0 };
  }
  return state.loggingSettings;
}

function renderLoggingSettings() {
  if (!$("loggingSettingsStatus")) return;
  const ui = loggingSettingsUi();
  $("loggingSettingsStatus").textContent = t(ui.status);
  const disabled = ui.loading || ui.saving || !canAdmin();
  $("saveLoggingSettings").disabled = disabled;
  $("loggingMaxFiles").disabled = disabled;
  $("loggingMaxSizeMb").disabled = disabled;
}

async function loadLoggingSettings() {
  if (!canAdmin()) return;
  const ui = loggingSettingsUi();
  const version = ++ui.version;
  ui.loading = true;
  ui.status = "Loading logging settings…";
  renderLoggingSettings();
  try {
    const data = await api("/api/settings/logging");
    if (!canAdmin() || loggingSettingsUi() !== ui || version !== ui.version) return;
    $("loggingMaxFiles").value = data.max_files;
    $("loggingMaxSizeMb").value = data.max_size_mb;
    ui.status = "";
  } catch {
    if (!canAdmin() || loggingSettingsUi() !== ui || version !== ui.version) return;
    ui.status = "Could not load logging settings. Reopen this section to retry.";
  } finally {
    if (loggingSettingsUi() === ui && version === ui.version) {
      ui.loading = false;
      renderLoggingSettings();
    }
  }
}

async function saveLoggingSettings() {
  if (!canAdmin()) return;
  const ui = loggingSettingsUi();
  if (ui.loading || ui.saving) return;
  const maxFiles = Number($("loggingMaxFiles").value);
  const maxSizeMb = Number($("loggingMaxSizeMb").value);
  if (!Number.isInteger(maxFiles) || maxFiles < 1 || maxFiles > 100 || !Number.isInteger(maxSizeMb) || maxSizeMb < 1 || maxSizeMb > 1024) {
    ui.status = "Enter whole numbers: 1–100 files and 1–1024 MB.";
    renderLoggingSettings();
    return;
  }
  const version = ++ui.version;
  ui.saving = true;
  ui.status = "Saving logging settings…";
  renderLoggingSettings();
  try {
    const data = await api("/api/settings/logging", { method: "PUT", body: JSON.stringify({ max_files: maxFiles, max_size_mb: maxSizeMb }) });
    if (!canAdmin() || loggingSettingsUi() !== ui || version !== ui.version) return;
    $("loggingMaxFiles").value = data.max_files;
    $("loggingMaxSizeMb").value = data.max_size_mb;
    ui.status = "Logging settings saved for all components.";
  } catch {
    if (!canAdmin() || loggingSettingsUi() !== ui || version !== ui.version) return;
    ui.status = "Could not save logging settings. Your saved limits are unchanged. Try again.";
  } finally {
    if (loggingSettingsUi() === ui && version === ui.version) {
      ui.saving = false;
      renderLoggingSettings();
    }
  }
}

const WRITE_CONTROL_IDS = new Set([
  "addAlertCondition", "newAlertRule", "addBannerItem", "addPensionPeriod", "addPensionRate", "addPensionScenario",
  "applyBackupSchedule", "attachAccountToMember", "attachEditAccountPerson", "attachLocalAccountPerson",
  "captureHistorySnapshot", "chooseFullRestore", "chooseImportData", "clearAlarms", "dashboardEdit",
  "dashboardReset", "importSource", "newEmployeeOptionGrant", "newPensionScenario", "runAlerts",
  "runBackupNow", "runCompanyOutlook", "runCompanyOutlookBacktest", "runDividendEvents", "saveAlarmSettings",
  "saveAlert", "saveApiAccessSettings", "saveBackupSettings", "saveBroker", "saveDetailPrice", "saveDisplaySettings", "saveEditAccount",
  "saveEditFund", "saveEmployeeExercise", "saveEmployeeListing", "saveEmployeeOptionGrant", "saveFamilyMember",
  "saveFund", "saveFundHistory", "saveHistorySnapshot", "saveLocalAccount", "saveManualSecurity",
  "saveIndustryClassification", "removeIndustryClassification", "savePositionTransaction", "savePrice", "saveSecurity", "saveTableSettings", "saveUser", "showFundCreate",
  "addSecurityExposureCurrency", "saveSecurityExposure", "removeSecurityExposure", "newFamilyMember",
  "showPensionPeriodEntry", "showPensionRateEntry",
]);
const WRITE_DATA_ACTIONS = new Set([
  "data-add-skipped-account", "data-dashboard-move", "data-dashboard-set-view", "data-delete-account",
  "data-delete-alert", "data-delete-broker", "data-delete-company-outlook", "data-delete-employee-option-grant",
  "data-delete-family-member", "data-delete-fund", "data-delete-fund-history", "data-delete-manual-security",
  "data-delete-pension-period", "data-delete-pension-rate", "data-delete-pension-scenario", "data-delete-price",
  "data-delete-security", "data-edit-account", "data-edit-alert", "data-edit-broker", "data-edit-employee-option-grant",
  "data-edit-family-member", "data-edit-fund", "data-edit-fund-history", "data-edit-manual-security",
  "data-edit-pension-scenario", "data-edit-position-transaction", "data-edit-security", "data-evaluate-company-outlook",
  "data-exercise-employee-option", "data-fix-skipped-account", "data-link-employee-listing", "data-remove-alert-condition", "data-add-alert-condition",
  "data-remove-banner", "data-run-alert", "data-schedule-pension-scenario", "data-toggle-alert", "data-use-manual-security",
  "data-user-enabled", "data-delete-user",
  "data-remove-exposure-currency",
  "data-position-action",
]);

function currentUser() {
  return state.auth.user;
}

function canAdmin() {
  return currentUser()?.role === "Admin";
}

function canWrite() {
  return ["Admin", "Operator"].includes(currentUser()?.role);
}

function authRequestHeaders(headers = {}) {
  return state.auth.csrfToken ? { ...headers, "X-CSRF-Token": state.auth.csrfToken } : { ...headers };
}

function isWriteControl(button) {
  if (!(button instanceof HTMLButtonElement)) return false;
  if (WRITE_CONTROL_IDS.has(button.id)) return true;
  return [...button.attributes].some((attribute) => WRITE_DATA_ACTIONS.has(attribute.name));
}

function applyRolePermissions(root = document) {
  const readOnly = currentUser()?.role === "Viewer";
  document.body.dataset.accessRole = currentUser()?.role || "anonymous";
  document.querySelectorAll("button[data-admin-only]").forEach((control) => { control.hidden = !canAdmin(); });
  const notice = $("readOnlyNotice");
  if (notice) notice.hidden = !readOnly;
  const buttons = [];
  if (root instanceof HTMLButtonElement) buttons.push(root);
  if (root.querySelectorAll) buttons.push(...root.querySelectorAll("button"));
  buttons.filter(isWriteControl).forEach((button) => {
    if (readOnly && !button.disabled) {
      button.disabled = true;
      button.dataset.roleDisabled = "true";
      button.classList.add("role-write-disabled");
      button.setAttribute("aria-disabled", "true");
      button.title = optionLabel("Viewer access is read-only");
    } else if (!readOnly && button.dataset.roleDisabled === "true") {
      button.disabled = false;
      delete button.dataset.roleDisabled;
      button.classList.remove("role-write-disabled");
      button.removeAttribute("aria-disabled");
      button.removeAttribute("title");
    }
  });
}

const rolePermissionObserver = new MutationObserver((mutations) => {
  mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
    if (node instanceof HTMLElement) applyRolePermissions(node);
  }));
});
rolePermissionObserver.observe(document.body, { childList: true, subtree: true });

function setAppAuthenticationLock(locked) {
  const shell = $("appShell");
  if (!shell) return;
  shell.inert = Boolean(locked);
  shell.setAttribute("aria-hidden", String(Boolean(locked)));
}

function renderCurrentUser() {
  const user = currentUser();
  const name = [user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.username || "";
  if ($("currentUserName")) {
    $("currentUserName").textContent = name;
    $("currentUserName").title = name;
  }
  if ($("currentUserRole")) $("currentUserRole").textContent = user ? optionLabel(user.role) : "";
  applyRolePermissions();
  renderAssistantChat();
}

function setAuthenticatedSession(payload) {
  state.auth.user = payload?.user || null;
  state.auth.csrfToken = String(payload?.csrf_token || "");
  state.auth.forcedPasswordChange = Boolean(payload?.user?.must_change_password);
  renderCurrentUser();
  ensureHierarchicalNav();
  bindNavAccordion();
}

function showLogin(message = "") {
  state.portfolioRefreshPending = false;
  state.portfolioLoadVersion = (state.portfolioLoadVersion || 0) + 1;
  clearTimeout(portfolioEnrichmentRetryTimer);
  portfolioEnrichmentRetryTimer = null;
  state.auth = { user: null, csrfToken: "", forcedPasswordChange: false };
  state.authenticatedAppStarted = false;
  document.querySelectorAll(".modal").forEach((modal) => { modal.hidden = true; });
  setAppAuthenticationLock(true);
  $("authOverlay").hidden = false;
  $("loginForm").hidden = false;
  $("passwordChangeForm").hidden = true;
  $("loginPassword").value = "";
  $("loginStatus").textContent = message;
  renderCurrentUser();
  ensureHierarchicalNav();
  bindNavAccordion();
  requestAnimationFrame(() => $("loginUsername")?.focus());
}

let passwordChangeReturnFocus = null;

function showPasswordChange({ forced = false } = {}) {
  state.auth.forcedPasswordChange = forced || Boolean(currentUser()?.must_change_password);
  passwordChangeReturnFocus = state.auth.forcedPasswordChange ? null : document.activeElement;
  setAppAuthenticationLock(true);
  $("authOverlay").hidden = false;
  $("loginForm").hidden = true;
  $("passwordChangeForm").hidden = false;
  $("cancelPasswordChange").hidden = state.auth.forcedPasswordChange;
  $("passwordChangeDescription").textContent = state.auth.forcedPasswordChange
    ? optionLabel("You must replace the temporary password before continuing.")
    : optionLabel("Enter the current password, then choose a new one.");
  $("currentPassword").value = "";
  $("newPassword").value = "";
  $("confirmPassword").value = "";
  $("passwordChangeStatus").textContent = "";
  requestAnimationFrame(() => $("currentPassword")?.focus());
}

function hideAuthOverlay() {
  $("authOverlay").hidden = true;
  setAppAuthenticationLock(false);
  const returnFocus = passwordChangeReturnFocus;
  passwordChangeReturnFocus = null;
  if (returnFocus?.isConnected) requestAnimationFrame(() => returnFocus.focus());
}

async function authResponse(response) {
  if (response.ok) return response.json();
  let message = `${response.status} ${response.statusText}`;
  try {
    const data = await response.json();
    message = data.detail?.message || data.detail || message;
  } catch {
    // Keep status text for non-JSON failures.
  }
  throw new Error(message);
}

async function restoreAuthSession() {
  const response = await fetch("/api/auth/session", { headers: { Accept: "application/json" } });
  if (response.status === 401) {
    showLogin();
    return false;
  }
  const payload = await authResponse(response);
  setAuthenticatedSession(payload);
  if (payload.user?.must_change_password) {
    showPasswordChange({ forced: true });
    return false;
  }
  hideAuthOverlay();
  return true;
}

async function signIn() {
  const button = $("loginButton");
  button.disabled = true;
  $("loginStatus").textContent = optionLabel("Signing in");
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: $("loginUsername").value, password: $("loginPassword").value }),
    });
    const payload = await authResponse(response);
    setAuthenticatedSession(payload);
    $("loginPassword").value = "";
    if (payload.user?.must_change_password) {
      showPasswordChange({ forced: true });
      return;
    }
    hideAuthOverlay();
    await startAuthenticatedApp();
  } finally {
    button.disabled = false;
  }
}

async function submitPasswordChange() {
  const newPassword = $("newPassword").value;
  if (newPassword !== $("confirmPassword").value) throw new Error(optionLabel("New password and confirmation do not match"));
  const button = $("changePasswordSubmit");
  button.disabled = true;
  $("passwordChangeStatus").textContent = optionLabel("Saving new password");
  try {
    const payload = await api("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        current_password: $("currentPassword").value,
        new_password: newPassword,
        confirm_password: $("confirmPassword").value,
      }),
    });
    setAuthenticatedSession(payload);
    hideAuthOverlay();
    await startAuthenticatedApp();
  } finally {
    button.disabled = false;
  }
}

async function signOut() {
  await api("/api/auth/logout", { method: "POST", body: "{}" });
  window.location.reload();
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

function formatBackupDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const twoDigits = (part) => String(part).padStart(2, "0");
  return `${twoDigits(date.getDate())}/${twoDigits(date.getMonth() + 1)}/${date.getFullYear()} ${twoDigits(date.getHours())}:${twoDigits(date.getMinutes())}`;
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

function datePickerAnchorPosition(input) {
  const rect = input.getBoundingClientRect();
  const viewportWidth = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
  const viewportHeight = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
  const margin = 12;
  const gap = 10;
  const estimatedPopupWidth = Math.min(280, Math.max(1, viewportWidth - margin * 2));
  const estimatedPopupHeight = Math.min(330, Math.max(1, viewportHeight - margin * 2));
  const fieldCenter = rect.left + rect.width / 2;
  const towardCenterLeft = fieldCenter <= viewportWidth / 2
    ? rect.right + gap
    : rect.left - estimatedPopupWidth - gap;
  const maxLeft = Math.max(margin, viewportWidth - estimatedPopupWidth - margin);
  const left = Math.min(Math.max(towardCenterLeft, margin), maxLeft);
  const below = rect.bottom + gap;
  const above = rect.top - estimatedPopupHeight - gap;
  const maxTop = Math.max(margin, viewportHeight - estimatedPopupHeight - margin);
  const top = below + estimatedPopupHeight <= viewportHeight - margin
    ? below
    : Math.min(Math.max(above, margin), maxTop);
  return { left: Math.round(left), top: Math.round(top) };
}

function positionNativeDatePicker(picker, input) {
  const position = datePickerAnchorPosition(input);
  picker.style.insetInlineStart = "auto";
  picker.style.insetInlineEnd = "auto";
  picker.style.right = "auto";
  picker.style.bottom = "auto";
  picker.style.left = `${position.left}px`;
  picker.style.top = `${position.top}px`;
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
  positionNativeDatePicker(picker, input);
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

const NAV_MENU_ICONS = Object.freeze({
  reports: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
  portfolio: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h18v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2"/></svg>',
  people: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  retirement: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 18 0Z"/><path d="M12 12v9M8 21h8M7 12V9M17 12V9"/></svg>',
  research: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="6"/><path d="m20 20-4.35-4.35M11 8v6M8 11h6"/></svg>',
  markets: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17 9 11l4 4 8-9"/><path d="M15 6h6v6"/></svg>',
  system: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.2 2.2-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56v.1h-3.12v-.1a1.7 1.7 0 0 0-1.03-1.56 1.7 1.7 0 0 0-1.88.34l-.06.06-2.2-2.2.06-.06A1.7 1.7 0 0 0 6.74 15a1.7 1.7 0 0 0-1.56-1.03h-.1v-3.12h.1A1.7 1.7 0 0 0 6.74 9.8a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.2-2.2.06.06a1.7 1.7 0 0 0 1.88.34 1.7 1.7 0 0 0 1.03-1.56v-.1h3.12v.1a1.7 1.7 0 0 0 1.03 1.56 1.7 1.7 0 0 0 1.88-.34l.06-.06 2.2 2.2-.06.06a1.7 1.7 0 0 0-.34 1.88 1.7 1.7 0 0 0 1.56 1.03h.1v3.12h-.1A1.7 1.7 0 0 0 19.4 15Z"/></svg>',
  help: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.4 9a2.7 2.7 0 1 1 4.7 1.8c-.9.9-2.1 1.35-2.1 2.7M12 17h.01"/></svg>',
});

function navMenuSummary(icon, label) {
  return `<summary><span class="nav-menu-icon" aria-hidden="true">${NAV_MENU_ICONS[icon]}</span><span class="nav-menu-label">${esc(label)}</span></summary>`;
}

function ensureHierarchicalNav() {
  const nav = document.querySelector(".nav");
  if (!nav) return;
  // Reuse the chat controls so language/role updates retain their listeners and draft.
  const chatLauncher = nav.querySelector?.(".assistant-launcher");
  const restoreChatFocus = chatLauncher?.contains(document.activeElement);
  // Top-level groups open as compact popovers, so keep the header uncluttered
  // until the user chooses a group.
  const defaultOpen = "";
  nav.innerHTML = `
    <details class="nav-menu"${defaultOpen}>
      ${navMenuSummary("portfolio", t("portfolioData"))}
      <div class="nav-children">
        <button class="nav-item" type="button" data-modal="accountsModal">${esc(t("accounts"))}</button>
        <button class="nav-item" type="button" data-modal="brokersModal">${esc(t("brokers"))}</button>
        <button class="nav-item" type="button" data-modal="securitiesModal" data-securities-workflow="employee-options">${esc(t("employeeOptions"))}</button>
        <button class="nav-item" type="button" data-modal="securitiesModal">${esc(t("securities"))}</button>
        <button class="nav-item" type="button" data-modal="positionsModal">${esc(t("positions"))}</button>
        <button class="nav-item" type="button" data-modal="pricesModal">${esc(t("prices"))}</button>
        <button class="nav-item" type="button" data-modal="eventsModal">${esc(t("events"))}</button>
      </div>
    </details>
    <details class="nav-menu">
      ${navMenuSummary("people", t("people"))}
      <div class="nav-children">
        <button class="nav-item" type="button" data-modal="familyModal" data-modal-target="familyMembersSection" data-modal-focus="newFamilyMember">${esc(t("familyMembers"))}</button>
        <button class="nav-item" type="button" data-modal="familyModal" data-modal-target="accountOwnershipSection" data-modal-focus="familyAttachAccount">${esc(t("accountOwnership"))}</button>
      </div>
    </details>
    <details class="nav-menu">
      ${navMenuSummary("retirement", t("retirement"))}
      <div class="nav-children">
        <button class="nav-item" type="button" data-modal="fundsModal" data-modal-target="fundsTitle" data-modal-focus="showFundCreate">${esc(t("pensionsFunds"))}</button>
        <button class="nav-item" type="button" data-modal="fundsModal" data-modal-target="simulatorPanel" data-modal-focus="simPersonSource">${esc(t("retirementProjections"))}</button>
      </div>
    </details>
    <details class="nav-menu">
      ${navMenuSummary("research", t("research"))}
      <div class="nav-children">
        <button class="nav-item" type="button" data-modal="researchModal" data-research-section="finance">${esc(t("companyReports"))}</button>
        <button class="nav-item" type="button" data-modal="researchModal" data-research-section="outlook">${esc(t("companyOutlook"))}</button>
        <button class="nav-item" type="button" data-modal="researchModal" data-research-section="signals">${esc(t("signalRules"))}</button>
      </div>
    </details>
    <details class="nav-menu">
      ${navMenuSummary("markets", t("marketsAlerts"))}
      <div class="nav-children">
        <button class="nav-item" type="button" data-modal="marketModal">${esc(t("marketScreener"))}</button>
        <button class="nav-item" type="button" data-modal="macroScenarioModal">${esc(t("macroScenarios"))}</button>
        <button class="nav-item" type="button" data-modal="bannerModal">${esc(t("marketBanner"))}</button>
      </div>
    </details>
    <button class="nav-menu-link" type="button" data-modal="reportsModal"><span class="nav-menu-icon" aria-hidden="true">${NAV_MENU_ICONS.reports}</span><span class="nav-menu-label">${esc(t("reports"))}</span></button>
    <details class="nav-menu">
      ${navMenuSummary("system", t("system"))}
      <div class="nav-children">
        ${canAdmin() ? `<button class="nav-item" type="button" data-modal="usersModal">${esc(t("users"))}</button>` : ""}
        <button class="nav-item" type="button" data-modal="settingsModal">${esc(t("settings"))}</button>
      </div>
    </details>
    <details class="nav-menu">
      ${navMenuSummary("help", t("help"))}
      <div class="nav-children">
        <button class="nav-item" type="button" data-modal="aboutModal">${esc(t("about"))}</button>
        <button class="nav-item" type="button" data-modal="helpModal">${esc(t("help"))}</button>
      </div>
    </details>`;
  if (chatLauncher) {
    nav.append(chatLauncher);
    if (restoreChatFocus) $("assistantLauncher").focus();
  }
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

function setMobileNavigation(expanded) {
  $("appNavigation")?.classList.toggle("is-expanded", expanded);
  $("navigationToggle")?.setAttribute("aria-expanded", String(expanded));
  if (!expanded) document.querySelectorAll(".nav-menu[open]").forEach((menu) => { menu.open = false; });
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
    area: "all",
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
    base.area = DASHBOARD_AREAS.includes(saved.area) ? saved.area : base.area;
    base.edit = false;
    base.accountTrendAccountId = saved.accountTrendAccountId || localStorage.getItem(DASHBOARD_ACCOUNT_STORAGE_KEY) || base.accountTrendAccountId;
    state.longTermView = ["total", "people", "funds"].includes(saved.longTermView)
      ? saved.longTermView
      : localStorage.getItem(DASHBOARD_LONG_TERM_STORAGE_KEY) || state.longTermView;
    state.longTermIncludePension = saved.longTermIncludePension !== false;
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
  localStorage.setItem(DASHBOARD_STORAGE_KEY, JSON.stringify({
    ...state.dashboard,
    longTermView: state.longTermView,
    longTermIncludePension: state.longTermIncludePension,
  }));
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

function loadMacroScenarioSettings() {
  const model = window.PortfolioScenarioModel;
  state.macroScenarioSettings = model
    ? model.normalizeSettings(readLocalJson(MACRO_SCENARIO_STORAGE_KEY, {}))
    : null;
}

function saveMacroScenarioSettings() {
  if (!state.macroScenarioSettings) return;
  localStorage.setItem(MACRO_SCENARIO_STORAGE_KEY, JSON.stringify(state.macroScenarioSettings));
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
  state.vestingNoticeSaved = true;
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
    dashboard: state.dashboard ? {
      ...state.dashboard,
      longTermView: state.longTermView,
      longTermIncludePension: state.longTermIncludePension,
    } : readLocalJson(DASHBOARD_STORAGE_KEY, {}),
    table: { maPeriod: state.tableMaPeriod || "30" },
    language: state.language || "en",
    bannerItems: Array.isArray(state.bannerItems) ? state.bannerItems : readLocalJson("portfolioAnalyzer.bannerItems", []),
    pensionSimulation: readLocalJson(PENSION_SIMULATION_STORAGE_KEY, {}),
    macroScenarios: state.macroScenarioSettings || readLocalJson(MACRO_SCENARIO_STORAGE_KEY, {}),
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
  if (clientState.macroScenarios && typeof clientState.macroScenarios === "object") {
    localStorage.setItem(MACRO_SCENARIO_STORAGE_KEY, JSON.stringify(clientState.macroScenarios));
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
  loadMacroScenarioSettings();
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
  if (!canWrite()) return;
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
  const brand = document.querySelector(".brand-name");
  if (brand) brand.textContent = t("brand");
  const topTitle = $("dashboardTitle");
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
  const authLanguageSelect = $("authLanguage");
  if (authLanguageSelect) authLanguageSelect.value = state.language;
  refreshLocalizedFormOptions();
  refreshBrokerSelects();
  renderBrokersList();
  renderLocalAccountsList();
  renderFamilyMembers();
  renderFamilyMemberEditor();
  refreshFamilyMemberSelects();
  refreshFamilyAccountSelects();
  renderImportSkippedAccounts();
  renderFundAccountOwners();
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  ensureHierarchicalNav();
  bindNavAccordion();
  renderCurrentUser();
  renderAlarms();
  renderMacroScenario();
  if (state.alertData) renderAlerts(state.alertData);
  renderAssistantChat();
  renderLoggingSettings();
  if (state.companyOutlook) renderCompanyOutlook(state.companyOutlook);
  if (state.financeReport) renderFinanceReport(state.financeReport);
  if (state.activeReport) renderReportSummary(state.activeReport);
  if (state.activeReportTrend) renderAccountTrend(state.activeReportTrend);
  if (state.tradeHistory || state.tradeHistoryLoading) { refreshPositionFilterOptions(); renderTradeHistory(); }
  if (state.tradeHistoryDetail) renderTradeHistoryDetails(state.tradeHistoryDetail);
  if (state.items?.length) renderRows(state.items);
  if (state.positionTransactionsDetail) syncPositionTransactionLimit();
  if (state.eventDividendSettings) renderEvents();
  refreshReportFilterOptions();
  document.querySelectorAll(".modal:not([hidden])").forEach(mountModalHomeLink);
  applyAutoDirection();
  window.PortfolioI18n?.applyToDocument(state.language);
  window.PortfolioI18n?.observe();
}

function revealInitializedApp() {
  document.documentElement.classList.remove("i18n-pending");
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
  const visible = sections.flatMap((section) => (
    dashboard.widgets
      .filter((widget) => widget.view === section.view)
      .sort((a, b) => a.order - b.order)
  ));
  if (dashboard.area === "all") return visible;
  const areaWidgetIds = new Set(DASHBOARD_WIDGETS
    .filter((widget) => widget.area === dashboard.area)
    .map((widget) => widget.id));
  if (dashboard.mode === "expanded") {
    return visible.filter((widget) => areaWidgetIds.has(widget.id));
  }
  const featuredIds = new Set(DASHBOARD_AREA_FEATURES[dashboard.area] || []);
  return dashboard.widgets
    .filter((widget) => widget.view !== "hidden" && areaWidgetIds.has(widget.id) && featuredIds.has(widget.id))
    .sort((left, right) => (
      (DASHBOARD_AREA_FEATURES[dashboard.area]?.indexOf(left.id) ?? 0)
      - (DASHBOARD_AREA_FEATURES[dashboard.area]?.indexOf(right.id) ?? 0)
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
  if (!["basic", "expanded"].includes(mode)) return;
  state.dashboard.mode = mode;
  saveDashboardSettings();
  renderAnalytics(state.items || []);
}

function setDashboardArea(area) {
  if (!DASHBOARD_AREAS.includes(area)) return;
  state.dashboard.area = area;
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
    const active = button.dataset.dashboardMode === dashboard.mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  document.querySelectorAll("[data-dashboard-area]").forEach((button) => {
    const active = button.dataset.dashboardArea === dashboard.area;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
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

function portfolioCashValue() {
  return sum(portfolioAccounts().map(accountCashValue));
}

function assetMixGroups(items) {
  const groups = groupValues(items, (item) => item.exposure_profile?.asset_focus
    ? EXPOSURE_FOCUS_LABELS[item.exposure_profile.asset_focus] || item.exposure_profile.asset_focus
    : ["ETF", "MUTUALFUND"].includes(String(item.holding.asset_class || "").toUpperCase())
      ? "Unclassified funds" : item.holding.asset_class);
  groups.push({ label: "Cash", value: portfolioCashValue() });
  return groups.sort((left, right) => Number(right.value || 0) - Number(left.value || 0));
}

function currencyAllocationGroups(items) {
  const totals = {};
  items.forEach((item) => {
    const value = normalizedField(item, "market_value");
    const exposure = economicCurrencyExposure(item);
    exposure.allocations.forEach(({ currency, percent }) => {
      totals[currency] = (totals[currency] || 0) + value * Number(percent || 0) / 100;
    });
    if (exposure.unknownPercent > 0) totals.Unknown = (totals.Unknown || 0) + value * exposure.unknownPercent / 100;
  });
  portfolioAccounts().forEach((account) => {
    const currency = account.currency || state.baseCurrency;
    const cash = accountCashValue(account);
    if (cash <= 0.005) return;
    totals[currency] = (totals[currency] || 0) + cash;
  });
  return Object.entries(totals)
    .map(([label, value]) => ({ label, value }))
    .sort((left, right) => Number(right.value || 0) - Number(left.value || 0));
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

function checkedAccountShareAmount(value, currency) {
  if (!["number", "string"].includes(typeof value) || String(value).trim() === "") return null;
  const amount = Number(value);
  if (!Number.isFinite(amount)) return null;
  if (amount === 0) return 0;
  const base = String(state.baseCurrency || "").trim().toUpperCase();
  const source = String(currency || "").trim().toUpperCase();
  if (!base || !source) return null;
  if (source === base) return amount;
  const validRate = (raw) => ["number", "string"].includes(typeof raw) && String(raw).trim() !== "" && Number.isFinite(Number(raw)) && Number(raw) > 0;
  const direct = state.fxRates?.[`${source}/${base}`];
  const reverse = state.fxRates?.[`${base}/${source}`];
  const converted = validRate(direct) ? amount * Number(direct) : validRate(reverse) ? amount / Number(reverse) : null;
  return converted !== null && Number.isFinite(converted) ? converted : null;
}

function accountShareSnapshot() {
  const unavailable = () => ({ available: false, total: null, shares: new Map() });
  const items = portfolioItems(state.items || []);
  const accounts = portfolioAccounts();
  // Validate every contribution before aggregation, including amounts that
  // offset each other. Never inherit normalizedAmount's missing-FX fallback.
  if (items.some((item) => checkedAccountShareAmount(item.holding.market_value, item.holding.currency) === null)
    || accounts.some((account) => checkedAccountShareAmount(accountCashBalance(account), account.currency) === null)) return unavailable();
  const groups = groupByAccount(items);
  const values = groups.map((group) => {
    const amounts = Object.entries(group.localValues || {}).map(([currency, value]) => checkedAccountShareAmount(value, currency));
    return amounts.some((value) => value === null) ? null : amounts.reduce((total, value) => total + value, 0);
  });
  if (values.some((value) => value === null || !Number.isFinite(value))) return unavailable();
  const total = values.reduce((value, amount) => value + amount, 0);
  if (!Number.isFinite(total) || total <= 0) return unavailable();
  const percentages = values.map((value) => value / total * 100);
  if (percentages.some((value) => !Number.isFinite(value))) return unavailable();
  const shares = new Map();
  groups.forEach((group, index) => shares.set(String(group.account), percentages[index]));
  groups.forEach((group, index) => { if (group.accountId) shares.set(String(group.accountId), percentages[index]); });
  return { available: true, total, shares };
}

function accountShareBadge(share) {
  const available = Number.isFinite(share);
  const chartAvailable = available && share >= 0 && share <= 100;
  const label = optionLabel("Share of total accounts");
  const value = available ? `${fmt(share, 1)}%` : optionLabel("Not available");
  const chart = chartAvailable
    ? `<svg class="account-share-ring" viewBox="0 0 28 28" aria-hidden="true" focusable="false"><circle class="account-share-ring-track" cx="14" cy="14" r="11"/><circle class="account-share-ring-value" cx="14" cy="14" r="11" pathLength="100" stroke-dasharray="${share} ${100 - share}"/></svg>`
    : `<span class="account-share-ring-placeholder" aria-hidden="true">${available ? "!" : "—"}</span>`;
  return `<span class="account-risk-portfolio-share" role="group" aria-label="${esc(label)}" title="${esc(label)}">${chart}<bdi dir="auto">${esc(value)}</bdi></span>`;
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
  const focus = item.exposure_profile?.asset_focus;
  const focusFactors = {
    money_market: 0.12, government_bond: 0.2, investment_grade_bond: 0.35,
    high_yield_bond: 0.6, broad_equity: 0.65, single_country_equity: 0.75,
    sector_equity: 0.8, multi_asset: 0.5, real_estate: 0.7,
    commodity: 0.85, derivative: 1, other: 0.7,
  };
  if (focus && Object.hasOwn(focusFactors, focus)) return focusFactors[focus];
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
  const focus = item.exposure_profile?.asset_focus;
  if (focus) {
    const sector = String(item.exposure_profile.sector_exposure || "").trim().toLowerCase();
    return (!sector || sector === "broad market")
      && ["broad_equity", "multi_asset", "money_market", "government_bond", "investment_grade_bond"].includes(focus);
  }
  if (industry.includes("sector") || industry.includes("industry")) return false;
  return !/(ARKK|SOXX|XLK|XLE|XLF|XLV|XLI|XLY|XLP|XLU|XLB|XLC|XBI|KWEB|TAN|ICLN|SMH)/.test(symbol);
}

function industryLabel(item) {
  const h = item.holding || {};
  const asset = String(h.asset_class || "").toUpperCase();
  const instrument = String(h.asset_sub_class || "").toUpperCase();
  if (asset === "BOND" || instrument === "BOND") return "Bonds";
  if (item.industry_source === "manual") return String(item.industry || "").trim();
  if (item.exposure_profile?.sector_exposure) return item.exposure_profile.sector_exposure;
  if (item.exposure_profile?.asset_focus === "money_market") return "Money market";
  if (diversifiedFund(item)) return "Diversified fund";
  return String(item.industry || h.industry || h.sector || "").trim();
}

function issuerLabel(item) {
  const h = item.holding || {};
  return String(h.symbol || h.name || "Unknown").trim().toUpperCase();
}

function countryLabel(item) {
  const h = item.holding || {};
  const fund = ["ETF", "MUTUALFUND"].includes(String(h.asset_class || "").toUpperCase());
  if (fund) return item.exposure_profile?.asset_focus === "single_country_equity"
    ? String(item.exposure_profile.geography || "").trim() : "";
  if (item.exposure_profile?.geography) return item.exposure_profile.geography;
  return String(h.country || h.location || "").trim();
}

function economicCurrencyExposure(item) {
  const h = item.holding || {};
  const profile = item.exposure_profile;
  const fund = ["ETF", "MUTUALFUND"].includes(String(h.asset_class || "").toUpperCase());
  if (!profile && !fund) return { allocations: [{ currency: h.currency || state.baseCurrency, percent: 100 }], unknownPercent: 0 };
  const enteredAllocations = profile?.currency_exposures || [];
  // A named FX exposure is a complete allocation when the user has not supplied
  // a detailed split. This avoids making users enter the same currency twice.
  const allocations = profile?.fx_basis === "unknown" ? []
    : (enteredAllocations.length
      ? enteredAllocations
      : (profile?.fx_reference_currency
        ? [{ currency: profile.fx_reference_currency, percent: 100 }]
        : []));
  return { allocations, unknownPercent: Math.max(0, 100 - sum(allocations.map((row) => Number(row.percent || 0)))) };
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
  if (item.exposure_profile?.asset_focus === "money_market") return 12;
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
  let band;
  if (score <= 20) band = { key: "low", label: "Low", symbol: "●" };
  else if (score <= 40) band = { key: "moderate", label: "Moderate", symbol: "◆" };
  else if (score <= 60) band = { key: "elevated", label: "Elevated", symbol: "▲" };
  else if (score <= 80) band = { key: "high", label: "High", symbol: "⬟" };
  else band = { key: "extreme", label: "Extreme", symbol: "!" };
  return { ...band, label: optionLabel(band.label) };
}

function riskAllocationBand(item) {
  const factor = assetRiskFactor(item);
  const foreignCurrencyExposure = economicCurrencyExposure(item).allocations
    .some(({ currency, percent }) => String(currency || "").toUpperCase() !== String(state.baseCurrency || "").toUpperCase() && Number(percent || 0) > 0);
  if (factor <= 0.12) return foreignCurrencyExposure ? "low" : "no-risk";
  if (factor <= 0.35) return "low";
  if (factor <= 0.65) return "medium";
  return "high";
}

function riskAllocationForItems(items, options = {}) {
  const cash = Math.max(0, Number(options.cash || 0));
  const cashCurrency = String(options.cashCurrency || state.baseCurrency || "").toUpperCase();
  const baseCurrency = String(state.baseCurrency || "").toUpperCase();
  const bands = [
    { key: "no-risk", label: "No risk", value: cashCurrency === baseCurrency ? cash : 0 },
    { key: "low", label: "Low risk", value: cashCurrency === baseCurrency ? 0 : cash },
    { key: "medium", label: "Medium risk", value: 0 },
    { key: "high", label: "High risk", value: 0 },
  ];
  const byKey = Object.fromEntries(bands.map((band) => [band.key, band]));
  (items || []).forEach((item) => {
    byKey[riskAllocationBand(item)].value += Math.abs(normalizedField(item, "market_value"));
  });
  const total = sum(bands.map((band) => band.value));
  let allocatedPercent = 0;
  return {
    total,
    bands: bands.map((band, index) => {
      const percent = total
        ? (index === bands.length - 1 ? Math.max(0, 100 - allocatedPercent) : Math.round(band.value / total * 1000) / 10)
        : 0;
      allocatedPercent += percent;
      return { ...band, percent };
    }),
  };
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
  const componentSpecs = [
    ["concentration", "Concentration", 16],
    ["asset_mix", "Asset mix", 14],
    ["currency", "Currency exposure", 10],
    ["industry", "Industry concentration", 10],
    ["cash", "Cash buffer", 7],
    ["derivatives", "Options, futures and leverage", 10],
    ["volatility", "Volatility", 10],
    ["horizon", "Investment horizon", 10],
    ["issuer_country", "Issuer and country concentration", 8],
    ["data_quality", "Missing data", 5],
  ];
  const simpleDriver = (driver) => {
    const text = String(driver || "");
    if (text.startsWith("Top holding ")) return `the largest single holding is ${text.slice(12)} of total value, including cash`;
    if (text.startsWith("Holding weight ")) return `this holding is ${text.slice(15)} of the portfolio`;
    if (text.startsWith("Foreign currency ")) return `${text.slice(17)} is exposed to foreign currencies`;
    if (text.startsWith("Options/futures/leverage ")) return `${text.slice(25)} uses options, futures, or leverage`;
    if (text.startsWith("1Y volatility proxy ")) return `its recent price movement is about ${text.slice(20)}`;
    if (text.startsWith("Horizon ")) return `the investment horizon is ${text.slice(8)}`;
    if (text.startsWith("Issuer concentration ")) return `one issuer represents ${text.slice(21)}`;
    if (text.startsWith("Symbol concentration ")) return `after combining holdings with the same symbol, one security is ${text.slice(21)} of securities value, excluding cash`;
    if (text.startsWith("Country concentration ")) return `one country represents ${text.slice(22)}`;
    if (text.startsWith("Low cash ")) return `the cash buffer is low (${text.slice(9)})`;
    if (text.startsWith("High cash ")) return `a large share is held in cash (${text.slice(10)})`;
    if (text.startsWith("Missing industry ")) return `industry information is missing for ${text.slice(17)}`;
    if (text.startsWith("Unknown FX exposure ")) return `currency exposure is unknown for ${text.slice(20)} of the portfolio`;
    if (text.startsWith("Asset factor ")) return "its asset type carries market risk";
    if (text === "ETF/fund treated as diversified proxy") return "the fund is treated as diversified";
    if (text === "Option/future/leveraged instrument") return "it uses an option, future, or leveraged instrument";
    if (text.startsWith("Missing ")) {
      const missingField = text.slice(8).trim();
      return state.language === "he"
        ? `היעדר נתוני ${optionLabel(missingField)} מקטין את ודאות האומדן`
        : `Missing ${missingField.toLowerCase()} data makes the estimate less certain`;
    }
    return text.toLowerCase();
  };
  const drivers = (risk.drivers || []).slice(0, 4).map(simpleDriver).map(optionLabel);
  const components = risk.show_component_breakdown === false ? [] : componentSpecs
    .filter(([key]) => risk.components && Number.isFinite(Number(risk.components[key])))
    .map(([key, label, maximum]) => `${optionLabel(label)}: ${fmt(risk.components[key], 1)}/${maximum}`);
  const title = state.language === "he"
    ? `${optionLabel("Risk")} ${band.label} · ${risk.score}/100`
    : `${band.label} risk · ${risk.score}/100`;
  return [
    title,
    optionLabel(meaning),
    ...(components.length ? ["", optionLabel("Components:"), ...components.map((component) => `• ${component}`)] : []),
    "",
    optionLabel("Main reasons:"),
    ...(drivers.length ? drivers.map((driver) => `• ${driver}`) : [`• ${optionLabel("No single factor stands out")}`]),
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
    const value = Math.abs(normalizedField(item, "market_value"));
    economicCurrencyExposure(item).allocations.forEach(({ currency, percent }) => {
      totals[currency] = (totals[currency] || 0) + value * Number(percent || 0) / 100;
    });
    return totals;
  }, {});
  const unknownCurrencyValue = rows.reduce((total, item) => total
    + Math.abs(normalizedField(item, "market_value")) * economicCurrencyExposure(item).unknownPercent / 100, 0);
  if (cash) {
    const cashCurrency = options.cashCurrency || state.baseCurrency;
    currencyTotals[cashCurrency] = (currencyTotals[cashCurrency] || 0) + cash;
  }
  const foreignValues = Object.entries(currencyTotals).filter(([currency]) => currency !== state.baseCurrency).map(([, value]) => value);
  const nonBaseCurrencyPct = sum(foreignValues) / totalValue * 100;
  const largestForeignCurrencyPct = (foreignValues.length ? Math.max(...foreignValues) : 0) / totalValue * 100;
  const currency = Math.min(nonBaseCurrencyPct / 80, 1) * 7 + Math.min(largestForeignCurrencyPct / 60, 1) * 3;

  const industryRows = rows.filter((item) => Math.abs(normalizedField(item, "market_value")) > 0
    && ["EQUITY", "RSU", "ETF", "MUTUALFUND"].includes(String(item.holding.asset_class || "").toUpperCase())
    && !["money_market", "government_bond", "investment_grade_bond", "high_yield_bond"].includes(item.exposure_profile?.asset_focus));
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
  const cashScore = cashPct >= 5 && cashPct <= 20 ? 0 : cashPct < 5 ? (5 - cashPct) / 5 * 7 : Math.min((cashPct - 20) / 50, 1) * 4;

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

  const issuerRiskTotals = rows.reduce((totals, item) => {
    const issuer = issuerLabel(item);
    const fundLookThroughWeight = diversifiedFund(item) ? 0.35 : 1;
    totals[issuer] = (totals[issuer] || 0) + Math.abs(normalizedField(item, "market_value")) * fundLookThroughWeight;
    return totals;
  }, {});
  const symbolTotals = rows.reduce((totals, item) => {
    const symbol = issuerLabel(item);
    totals[symbol] = (totals[symbol] || 0) + Math.abs(normalizedField(item, "market_value"));
    return totals;
  }, {});
  const countryTotals = rows.reduce((totals, item) => {
    const country = countryLabel(item);
    if (!country) return totals;
    totals[country] = (totals[country] || 0) + Math.abs(normalizedField(item, "market_value"));
    return totals;
  }, {});
  const largestIssuerRiskPct = holdingsValue ? Math.max(0, ...Object.values(issuerRiskTotals)) / holdingsValue * 100 : 0;
  const largestSymbolPct = holdingsValue ? Math.max(0, ...Object.values(symbolTotals)) / holdingsValue * 100 : 0;
  const largestCountryPct = holdingsValue ? Math.max(0, ...Object.values(countryTotals)) / holdingsValue * 100 : 0;
  const issuerCountry = Math.min(largestIssuerRiskPct / 35, 1) * 4 + Math.max(0, Math.min((largestCountryPct - 55) / 35, 1)) * 4;

  const missingPricePct = holdingsValue ? rows.filter((item) => (item.missing || []).includes("price history")).reduce((total, item) => total + Math.abs(normalizedField(item, "market_value")), 0) / holdingsValue * 100 : 0;
  const missingClassPct = holdingsValue ? rows.filter((item) => !item.holding.asset_class || !item.holding.currency).reduce((total, item) => total + Math.abs(normalizedField(item, "market_value")), 0) / holdingsValue * 100 : 0;
  const dataQuality = Math.min(missingPricePct / 100 * 2 + missingIndustryPct / 100 * 1.5
    + missingClassPct / 100 * 1.5 + unknownCurrencyValue / totalValue * 1.5, 5);

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
    unknownCurrencyValue / totalValue > 0.1 ? `Unknown FX exposure ${fmt(unknownCurrencyValue / totalValue * 100, 1)}%` : "",
    derivativePct > 0 ? `Options/futures/leverage ${fmt(derivativePct, 1)}%` : "",
    avgVolatilityPct > 35 ? `1Y volatility proxy ${fmt(avgVolatilityPct, 1)}%` : "",
    horizonYears !== null && horizonYears !== undefined ? `Horizon ${fmt(horizonYears, 1)} years` : "",
    largestSymbolPct > 25 ? `Symbol concentration ${fmt(largestSymbolPct, 1)}%` : "",
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
      show_component_breakdown: false,
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
  portfolioAccounts().forEach((account) => {
    if (accountCashValue(account) > 0 && !itemsByAccount[account.id]) itemsByAccount[account.id] = [];
  });
  const accountRisks = Object.entries(itemsByAccount).map(([key, rows]) => {
    const account = accountsById[key] || (rows[0] ? accountRecordForHolding(rows[0].holding) : null);
    const cash = accountCashValue(account);
    const value = sum(rows.map((item) => Math.abs(normalizedField(item, "market_value")))) + cash;
    const horizonYears = accountHorizonYears(account);
    const label = cleanSourceLabel(rows[0]?.holding.account) || account?.account_id || "Unassigned";
    return {
      key,
      account: label,
      value,
      horizonYears,
      risk: riskScoreForItems(rows, { label: `${label || "Account"} risk`, cash, cashCurrency: account?.currency, horizonYears }),
      allocation: riskAllocationForItems(rows, { cash, cashCurrency: account?.currency }),
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
    local_portfolio: "Local portfolio",
    local: "Local",
    manual: "Manual",
  };
  return optionLabel(names[key] || cleanSourceLabel(value));
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

function stockMarketDisplay(h, marketKey = "", exchange = "") {
  const candidate = [h.stock_market, exchange, marketKey].find((value) => String(value || "").trim() && !isProviderName(value));
  return candidate ? cleanSourceLabel(candidate).toUpperCase() : optionLabel("Not available");
}

function dataProviderDisplay(item, h, marketKey = "") {
  if (isProviderName(marketKey)) return providerDisplayName(marketKey);
  const usable = Object.entries(item.provider_status || {}).filter(([key, value]) => (
    ["ok", "stale"].some((stateName) => String(value).toLowerCase().includes(stateName)) && key.includes(".")
  ));
  const provider = usable.find(([key, value]) => key.startsWith("prices.") && String(value).toLowerCase() === "ok")
    || usable.find(([key]) => key.startsWith("prices."))
    || usable.find(([, value]) => String(value).toLowerCase() === "ok")
    || usable[0];
  if (provider) return providerDisplayName(provider[0].split(".").pop());
  if (h.data_source && h.data_source !== "LOCAL") return providerDisplayName(h.data_source);
  return providerDisplayName(h.data_source || "local");
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
  if (kind === "dividend") return `${money(value, currency, 2)} / ${t("share")}`;
  if (kind === "percent") return pct(Number(value) * 100);
  return compactNumber(value);
}

function analyticsStateCell(label, state, message) {
  const failed = state === "error";
  return `<div class="metric-cell analytics-state-cell"><div class="metric-head"><span class="metric-name">${esc(t(label))}</span><span class="metric-pill ${failed ? "warn" : "neutral"}">${esc(t(failed ? "Update failed" : "Loading"))}</span></div><small>${esc(t(message))}</small></div>`;
}

function trendCell(trend, label, { kind = "number", currency = "USD", marketCap = null } = {}) {
  if (["pending", "error"].includes(trend?.state)) return analyticsStateCell(label, trend.state, trend.state === "pending" ? "Loading financial data" : "Financial data could not be updated");
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
  if (["pending", "error"].includes(range?.state)) return analyticsStateCell("Price range", range.state, range.state === "pending" ? "Loading price history" : "Price history could not be updated");
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
  if (["pending", "error"].includes(sr?.state)) return analyticsStateCell("Technicals", sr.state, sr.state === "pending" ? "Loading price history" : "Price history could not be updated");
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
    .map(([provider, value]) => `${providerDisplayName(provider.split(".").pop())}: ${optionLabel(value)}`)
    .join("; ");
}

function providerStatusHint(providerStatus) {
  const entries = Object.entries(providerStatus || {});
  const okProviders = [...new Set(entries
    .filter(([, value]) => String(value).toLowerCase() === "ok")
    .map(([key]) => providerDisplayName(key.split(".").pop())))];
  const staleProviders = [...new Set(entries
    .filter(([, value]) => String(value).toLowerCase().includes("stale") || value === "cached")
    .map(([key]) => providerDisplayName(key.split(".").pop())))];
  const failedProviders = [...new Set(entries
    .filter(([, value]) => String(value).toLowerCase().includes("error"))
    .map(([key]) => providerDisplayName(key.split(".").pop())))];
  const missingKeyProviders = [...new Set(entries
    .filter(([, value]) => String(value).toLowerCase().includes("api key"))
    .map(([key]) => providerDisplayName(key.split(".").pop())))];
  if (staleProviders.length) return `Saved local history: ${staleProviders.slice(0, 2).join(", ")}${staleProviders.length > 2 ? ` +${staleProviders.length - 2}` : ""}`;
  if (okProviders.length) return `Data from ${okProviders.slice(0, 2).join(", ")}${okProviders.length > 2 ? ` +${okProviders.length - 2}` : ""}`;
  if (missingKeyProviders.length) return `Missing key: ${missingKeyProviders.slice(0, 2).join(", ")}`;
  if (failedProviders.length) return `Fallback failed: ${failedProviders.slice(0, 2).join(", ")}`;
  const values = entries.map(([, value]) => String(value));
  if (values.some((value) => value.toLowerCase().includes("missing"))) return "Some provider fields missing";
  return "";
}

function statusCell(item) {
  if (["queued", "updating"].includes(item.analytics_state)) {
    const saved = [item.income_trend, item.profit_trend, item.dividend_trend].some((metric) => ["ok", "partial", "stale"].includes(metric?.state));
    const label = item.analytics_state === "queued" ? (saved ? "Saved data · awaiting update" : "Awaiting update") : (saved ? "Saved data · updating" : "Updating analytics");
    return `<div class="status-cell status-cell-compact"><span class="badge neutral">${esc(t(label))}</span></div>`;
  }
  if (item.analytics_state === "refreshing" || item.analytics_state === "failed") {
    return `<div class="status-cell status-cell-compact"><span class="badge ${item.analytics_state === "failed" ? "partial" : "neutral"}">${esc(t(item.analytics_state === "failed" ? "Update failed" : "Updating analytics"))}</span></div>`;
  }
  const providerText = providerStatusText(item.provider_status);
  const providerHint = providerStatusHint(item.provider_status);
  const localizedMissing = item.missing.map(optionLabel);
  const detail = `${localizedMissing.join(", ")}${providerText ? `; ${providerText}` : ""}`;
  if (!item.missing.length) {
    return `<div class="status-cell status-cell-compact">
      <span class="badge ok" title="${esc(providerHint || providerText || "All displayed metrics are available")}">All displayed data available</span>
    </div>`;
  }
  return `<div class="status-cell status-cell-compact">
    <strong title="${esc(detail || "Provider data is unavailable")}">${item.missing.length} data gaps</strong>
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

function filterNumber(value) {
  if (value === null || value === undefined || String(value).trim() === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function portfolioTechnicalMatch(item, criteria) {
  const levelKind = String(criteria.technicalLevel || "").toLowerCase().trim();
  const distanceLimit = filterNumber(criteria.technicalDistancePct);
  if (!levelKind && distanceLimit === null) return true;
  if (!["support", "resistance"].includes(levelKind) || distanceLimit === null) return true;
  const levels = item.support_resistance?.[String(criteria.technicalPeriod || "1y").toLowerCase()] || {};
  if (levels.state !== "ok") return false;
  const levelPrice = filterNumber(levels[levelKind]?.price);
  const current = filterNumber(levels.current_price);
  const previous = filterNumber(levels.previous_price);
  if (levelPrice === null || levelPrice <= 0 || current === null) return false;
  const distance = ((current - levelPrice) / Math.abs(levelPrice)) * 100;
  const limit = Math.abs(distanceLimit);
  switch (String(criteria.technicalDirection || "near").toLowerCase()) {
    case "up": return distance >= 0 && distance <= limit;
    case "down": return distance >= -limit && distance <= 0;
    case "cross_up": return previous !== null && previous <= levelPrice && current > levelPrice && distance >= 0 && distance <= limit;
    case "cross_down": return previous !== null && previous >= levelPrice && current < levelPrice && distance >= -limit && distance <= 0;
    default: return Math.abs(distance) <= limit;
  }
}

function hasActivePortfolioFilter(criteria) {
  if (!criteria) return false;
  return Boolean(
    criteria.query || criteria.account || criteria.accountType || criteria.location
    || criteria.assetClass || criteria.currency || criteria.sector
    || filterNumber(criteria.minHoldingValue) !== null
    || filterNumber(criteria.maxHoldingValue) !== null
    || (criteria.technicalLevel && filterNumber(criteria.technicalDistancePct) !== null)
    || criteria.includeMissing === false
  );
}

function filterPortfolioItems(items, criteria) {
  if (!hasActivePortfolioFilter(criteria)) return portfolioItems(items);
  const query = String(criteria.query || "").toLowerCase();
  const account = String(criteria.account || "").toLowerCase();
  const sector = String(criteria.sector || "").toLowerCase();
  const minValue = filterNumber(criteria.minHoldingValue);
  const maxValue = filterNumber(criteria.maxHoldingValue);
  return (items || []).filter((item) => {
    const holding = item.holding || {};
    if (query && ![holding.symbol, holding.secondary_symbol, holding.name].some((value) => String(value || "").toLowerCase().includes(query))) return false;
    if (account && !String(holding.account || "").toLowerCase().includes(account)) return false;
    if (criteria.accountType && String(holding.account_type || "").toLowerCase() !== String(criteria.accountType).toLowerCase()) return false;
    if (criteria.location && String(holding.location || holding.country || "").toLowerCase() !== String(criteria.location).toLowerCase()) return false;
    if (criteria.assetClass && String(holding.asset_class || "").toUpperCase() !== String(criteria.assetClass).toUpperCase()) return false;
    if (criteria.currency && String(holding.currency || "").toUpperCase() !== String(criteria.currency).toUpperCase()) return false;
    if (sector && !String(holding.sector || "").toLowerCase().includes(sector)) return false;
    if (minValue !== null && Number(holding.market_value || 0) < minValue) return false;
    if (maxValue !== null && Number(holding.market_value || 0) > maxValue) return false;
    if (!portfolioTechnicalMatch(item, criteria)) return false;
    if (criteria.includeMissing === false && (item.missing || []).length) return false;
    return true;
  });
}

function setSelectOptions(id, values, label) {
  const select = $(id);
  const current = select.value;
  select.innerHTML = `<option value="">${label}</option>` + values
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b))
    .map((value) => `<option value="${esc(value)}">${esc(id === "currency" ? currencyDisplayLabel(value) : optionLabel(value))}</option>`)
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
  select.innerHTML = codes.map((code) => `<option value="${esc(code)}">${esc(currencyDisplayLabel(code))}</option>`).join("");
  select.value = codes.includes(current) ? current : (codes.includes("USD") ? "USD" : codes[0]);
}

function setAccountCountryOptions(selectId, preferred = "") {
  const select = $(selectId);
  if (!select) return;
  const current = normalizeAccountCountry(preferred || select.value);
  select.innerHTML = ACCOUNT_COUNTRIES.map((value) => {
    return `<option value="${esc(value)}">${esc(countryDisplayLabel(ACCOUNT_COUNTRY_CODES[value]))}</option>`;
  }).join("");
  select.value = current;
}

function companyCountryChoices() {
  return REGION_CODES.map((code) => {
    const name = countryName(code);
    const value = code === "US" ? "USA" : code === "IL" ? "Israel" : name;
    return { code, name, value };
  }).sort((a, b) => a.name.localeCompare(b.name));
}

function normalizedCompanyLocation(location, choices = companyCountryChoices()) {
  const code = countryCodeForLocation(location);
  if (code === "US") return "USA";
  if (code === "IL") return "Israel";
  return choices.find((choice) => choice.code === code)?.value || "";
}

function setCompanyLocationOptions(preferred = "", selectId = "manualSecurityLocation") {
  const select = $(selectId);
  if (!select) return;
  const choices = companyCountryChoices();
  const current = normalizedCompanyLocation(preferred || select.value, choices);
  select.innerHTML = choices.map((choice) => (
    `<option value="${esc(choice.value)}">${esc(countryDisplayLabel(choice.code))}</option>`
  )).join("");
  select.value = current || "USA";
}

function refreshCountryDatalist() {
  const datalist = $("countryOptions");
  if (!datalist) return;
  datalist.innerHTML = REGION_CODES.map((code) => {
    const name = countryName(code);
    return `<option value="${esc(name)}" label="${esc(countryDisplayLabel(code))}"></option>`;
  }).join("");
}

function refreshLocalizedFormOptions() {
  refreshCountryDatalist();
  ["localAccountLocation", "editAccountLocation", "brokerCountry"]
    .forEach((id) => setAccountCountryOptions(id, valueOf(id) || "USA"));
  setCompanyLocationOptions(valueOf("manualSecurityLocation") || "USA");
  setCompanyLocationOptions(valueOf("employeeWizardLocation") || "USA", "employeeWizardLocation");
  ["localAccountCurrency", "editAccountCurrency", "brokerCurrency", "employeeWizardCurrency"]
    .forEach((id) => setCurrencyOptions(id, SUPPORTED_MANAGEMENT_CURRENCIES));
  setCurrencyOptions("priceCurrency");
  setCurrencyOptions("manualSecurityCurrency", SUPPORTED_MANAGEMENT_CURRENCIES);
}

function syncCurrencyFromLocation(locationId, currencyId) {
  const currency = preferredCurrencyForLocation(valueOf(locationId));
  const select = $(currencyId);
  if (currency && select && [...select.options].some((option) => option.value === currency)) {
    select.value = currency;
  }
}

function populateStaticOptions() {
  refreshMarketOptions();
  refreshLocalizedFormOptions();
  const assetClasses = state.localOptions.asset_classes || ["EQUITY", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE", "RSU", "EMPLOYEE_STOCK_OPTION", "PRIVATE_STOCK", "STOCK_OPTION"];
  setOptions("localAccountType", state.localOptions.account_types);
  setOptions("editAccountType", state.localOptions.account_types);
  setOptions("reportAccountType", state.localOptions.account_types, optionLabel("All account categories"));
  setOptions("fundKind", state.localOptions.fund_kinds);
  setOptions("editFundKind", state.localOptions.fund_kinds);
  setOptions("securityAssetClass", assetClasses);
  setOptions("priceAssetClass", assetClasses);
  setOptions("manualInstrumentType", (state.localOptions.instrument_types || ["STOCK", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE", "EMPLOYEE_STOCK_OPTION", "PRIVATE_STOCK", "STOCK_OPTION"])
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
  if (period === "max") return HISTORY_START_DATE;
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
    .map(([label, count]) => `${optionLabel(label)}: ${count}`)
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
      const title = `Account: ${account.account}; ${account.type || "Account"}${account.location ? ` · ${countryDisplayLabel(account.location)}` : ""}; Securities: ${symbolsText || "None"}${more}; Source currencies: ${account.currencies.map(currencyDisplayLabel).join(", ")}${cashText}`;
      return `<span class="account-chip" title="${esc(title)}"><b>${esc(account.account)}</b><span class="account-chip-values"><strong>${money(account.value, state.baseCurrency, 0)}</strong>${localLine}</span>${riskBadge(accountRisk, true)}</span>`;
    })
    .join("");
  const accountShares = accountShareSnapshot();
  const accountRiskAllocationsHtml = state.riskSnapshot.accounts
    .sort((left, right) => right.value - left.value)
    .map((entry) => {
      const allocation = entry.allocation;
      if (!allocation?.total) return "";
      const share = accountShares.shares.get(String(entry.key)) ?? accountShares.shares.get(cleanSourceLabel(entry.key));
      const segments = allocation.bands.map((band) => `<span class="account-risk-segment account-risk-${band.key}" style="--risk-allocation:${band.percent}%" title="${esc(`${optionLabel(band.label)}: ${fmt(band.percent, 1)}%`)}"></span>`).join("");
      const labels = allocation.bands.map((band) => `<span class="account-risk-allocation-label"><i class="account-risk-dot account-risk-${band.key}"></i>${esc(optionLabel(band.label))} <b>${esc(fmt(band.percent, 1))}%</b></span>`).join("");
      return `<article class="account-risk-allocation-card" title="${esc(optionLabel("Allocation is based on each holding's asset-risk category. Cash and money-market holdings are No risk only in the base currency; foreign-currency exposure is Low risk."))}">
        <div class="account-risk-allocation-heading"><b>${esc(entry.account)}</b><span class="account-risk-metrics">${riskBadge(entry.risk, true)}${accountShareBadge(share)}</span></div>
        <div class="account-risk-allocation-bar" role="img" aria-label="${esc(`${entry.account}: ${allocation.bands.map((band) => `${optionLabel(band.label)} ${fmt(band.percent, 1)}%`).join(", ")}`)}">${segments}</div>
        <div class="account-risk-allocation-labels">${labels}</div>
      </article>`;
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
        <div class="portfolio-summary-metrics">
          <div class="portfolio-summary-value">
            <p class="eyebrow">Portfolio value</p>
            <div class="balance-value" title="Securities ${money(securitiesValue, state.baseCurrency, 0)} + cash ${money(cashValue, state.baseCurrency, 0)}">${money(primaryValue, state.baseCurrency)}</div>
          </div>
          <div class="portfolio-summary-profit">
            <p class="eyebrow">${esc(optionLabel("Holding Profit"))}</p>
            <div class="delta ${profitClass}" title="Holding profit converted to ${esc(state.baseCurrency)} using displayed FX rates when available">${signedMoney(primaryProfit, state.baseCurrency)}</div>
          </div>
          <div class="portfolio-risk-summary">
            <span>${esc(optionLabel("Total portfolio risk"))}</span>
            ${riskBadge(state.riskSnapshot.total)}
            <small>${esc(optionLabel("0 is very low · 100 is extreme"))}</small>
          </div>
        </div>
        <details class="summary-drawer">
          <summary>Portfolio stats</summary>
          <div class="summary">${statsHtml}</div>
        </details>
        <div class="currency-strip">${accountsHtml}</div>
        ${accountRiskAllocationsHtml ? `<section class="account-risk-allocations" aria-label="${esc(optionLabel("Account risk allocation"))}"><div class="account-risk-allocations-title"><span>${esc(optionLabel("Account risk allocation"))}</span><small>${esc(optionLabel("Split by current account value"))}</small></div><div class="account-risk-allocations-grid">${accountRiskAllocationsHtml}</div></section>` : ""}
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
    scenario.current_age
    && scenario.retire_age
    && scenario.retire_age > scenario.current_age
    && !pensionScenarioScheduleIssue(scenario)
    && !scenarioNeedsGenderForInsurance(scenario)
  ));
  const scenarios = hasResults ? (grid.baseScenarios || []) : state.pensionScenarios;
  const resultFor = (rowIndex) => hasResults ? (state.pensionSimulationResults[rowIndex] || null) : null;
  if (scenarios.length) {
    if (!hasResults && canAutoRun) schedulePensionSimulationAutoRun();
    return `
      <div class="dashboard-projection-table" data-preserve-scroll="pension-projection">
        <table class="projection-result-table compact-projection-table">
          <thead>
            <tr>
              <th>Pension Scenario</th>
              <th>Age Range</th>
              <th>Starting Balance</th>
              <th>Monthly Pension</th>
              <th>Final Amount</th>
              <th>Net Deposits</th>
              <th>Investment Gain</th>
            </tr>
          </thead>
          <tbody>
            ${scenarios.map((scenario, rowIndex) => {
              const result = resultFor(rowIndex);
              const rowNeedsGender = scenarioNeedsGenderForInsurance(scenario);
              const statusText = simulationError || (rowNeedsGender ? "Set gender" : (canAutoRun ? "Calculating" : "Add return period"));
              const statusTitle = simulationError || (rowNeedsGender ? "Set Male/Female gender to calculate pension insurance cost" : "");
              return `
                <tr>
                  <td><b>${esc(scenario.name)}</b><small>${esc(scenario.person_name || "Manual")}</small></td>
                  <td>${fmt(scenario.current_age, 1)}-${fmt(scenario.retire_age, 1)}</td>
                  <td>${result ? money(result.starting_amount || 0, state.baseCurrency, 0) : ""}</td>
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
    <div class="dashboard-projection-table" data-preserve-scroll="pension-projection">
      <table class="projection-result-table compact-projection-table compact-projection-table-empty">
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

function companyLogoHtml(holding) {
  const symbol = String(holding.symbol || "").trim();
  const assetClass = String(holding.asset_class || "EQUITY").toUpperCase();
  const supportsCompanyLogo = ["EQUITY", "ETF", "MUTUALFUND", "RSU"].includes(assetClass);
  const canResolve = supportsCompanyLogo && /^[A-Z0-9.-]+$/i.test(symbol);
  if (!canResolve) return "";
  const params = new URLSearchParams({ symbol, stock_market: holding.stock_market || "" });
  if (holding.secondary_symbol) params.set("secondary_symbol", holding.secondary_symbol);
  return `<span class="company-logo-frame" title="${esc(optionLabel("Company logo"))}" aria-hidden="true"><img class="company-logo" src="/api/company-logo?${esc(params.toString())}" alt="" decoding="async" fetchpriority="low" /></span>`;
}

function bindCompanyLogoImages(scope) {
  scope.querySelectorAll(".company-logo").forEach((image) => {
    const frame = image.closest(".company-logo-frame");
    const reveal = () => frame?.classList.add("has-logo");
    const discard = () => frame?.remove();
    image.addEventListener("load", reveal, { once: true });
    image.addEventListener("error", discard, { once: true });
    if (image.complete) (image.naturalWidth > 0 ? reveal : discard)();
  });
}

function preserveRenderedInteraction(root) {
  if (!root) return () => {};
  const active = root.contains(document.activeElement) ? document.activeElement : null;
  const rowKey = active?.closest("[data-portfolio-position]")?.dataset.portfolioPosition;
  const identity = active ? [...active.attributes].filter((attr) => /^(id|data-position-action|data-.*(symbol|market-key|market|account-id|currency|asset))$/.test(attr.name)).map((attr) => [attr.name, attr.value]) : [];
  const detailStates = [...root.querySelectorAll("details")].map((node) => ({ open: node.open, className: node.className, id: node.id }));
  const tagName = active?.tagName, className = active?.className;
  return () => {
    [...root.querySelectorAll("details")].forEach((node, index) => {
      const previous = detailStates[index];
      if (previous && previous.id === node.id && previous.className === node.className) node.open = previous.open;
    });
    if (!active || active.isConnected) return;
    const scope = rowKey ? [...root.querySelectorAll("[data-portfolio-position]")].find((node) => node.dataset.portfolioPosition === rowKey) : root;
    const replacement = [...(scope?.querySelectorAll(tagName) || [])].find((node) => identity.length
      ? identity.every(([name, value]) => node.getAttribute(name) === value)
      : node.className === className);
    replacement?.focus({ preventScroll: true });
  };
}

function renderRows(items) {
  const restoreInteraction = preserveRenderedInteraction($("rows"));
  $("count").textContent = `${items.length} shown`;
  $("rows").innerHTML = items.map((item) => {
    const h = item.holding;
    const range = item.price_ranges["1y"] || {};
    const maPeriod = state.tableMaPeriod || "30";
    const movingAverage = item.moving_averages[maPeriod] || {};
    const sr = item.support_resistance["1y"] || {};
    const marketKey = holdingMarketKey(h);
    const market = stockMarketDisplay(h, marketKey, item.exchange);
    const provider = dataProviderDisplay(item, h, marketKey);
    const securityName = String(h.name || "").trim();
    const companyLine = securityName || String(h.symbol || "").trim();
    const industry = industryLabel(item);
    const industryLine = `<div class="security-industry">${esc(optionLabel("Industry"))}: ${esc(industry ? optionLabel(industry) : optionLabel("Not available"))}</div>`;
    const exposure = item.exposure_profile;
    const exposureText = exposure
      ? [exposure.asset_focus && optionLabel(EXPOSURE_FOCUS_LABELS[exposure.asset_focus] || exposure.asset_focus),
        exposure.fx_reference_currency && `${currencyDisplayLabel(exposure.fx_reference_currency)} (${optionLabel("Named exposure")})`,
        exposure.currency_exposures?.length
          ? exposure.currency_exposures.map((row) => `${currencyDisplayLabel(row.currency)} ${fmt(row.percent, 1)}%`).join(" · ") : optionLabel("FX unknown"),
        exposure.fx_policy_limit_percent != null && `${optionLabel("Policy maximum")} ${fmt(exposure.fx_policy_limit_percent, 1)}%`,
        ["reported", "estimated"].includes(exposure.fx_basis) && optionLabel(exposure.fx_basis === "reported" ? "Reported holdings" : "Manual estimate"),
        exposure.as_of && formatDate(exposure.as_of)].filter(Boolean).join(" · ")
      : ["ETF", "MUTUALFUND"].includes(String(h.asset_class || "").toUpperCase())
        ? optionLabel("Exposure unclassified")
        : `${optionLabel("Currency proxy")}: ${currencyDisplayLabel(h.currency || state.baseCurrency)}`;
    const exposureLine = `<div class="security-exposure"><button class="secondary compact-button" type="button" data-edit-security-exposure-symbol="${esc(h.symbol)}" data-edit-security-exposure-market="${esc(marketKey)}" title="${esc(optionLabel("Edit exposure profile"))}">${esc(optionLabel("Exposure"))} ✎</button><span>${esc(exposureText)}</span></div>`;
    const marketLine = `${optionLabel(h.asset_class || "Asset")} · ${currencyDisplayLabel(h.currency || "")} · ${optionLabel("Market")}: ${market} · API: ${provider}`;
    const accountMeta = h.account_type
      ? optionLabel(h.account_type)
      : h.location
        ? countryDisplayLabel(h.location)
        : cleanSourceLabel(h.sector || "");
    const rowRisk = state.riskSnapshot?.total?.position_risks?.get(item);
    const averageBuyPrice = Math.abs(Number(h.quantity || 0)) > 0
      ? Math.abs(Number(h.cost_basis || 0) / Number(h.quantity || 0))
      : 0;
    return `<tr data-portfolio-position="${esc(JSON.stringify([h.account_id, h.symbol, marketKey, h.currency, h.asset_class]))}">
      <td data-label="Security"><div class="security-cell"><div class="security-symbols">${companyLogoHtml(h)}<button class="symbol security-history-link" type="button" data-security-detail-symbol="${esc(h.symbol)}" data-security-detail-market-key="${esc(marketKey)}" data-security-detail-stock-market="${esc(market)}" data-security-detail-provider="${esc(provider)}" data-security-detail-asset="${esc(h.asset_class)}" data-security-detail-currency="${esc(h.currency)}" data-security-detail-location="${esc(h.country || h.location || "")}" title="Open security overview">${esc(h.symbol)}</button>${h.secondary_symbol ? `<span class="secondary-symbol" title="Secondary symbol">${esc(h.secondary_symbol)}</span>` : ""}<span class="ux-tooltip security-meta-tooltip" tabindex="0" role="note" aria-label="Security details" title="${esc(marketLine)}" data-tooltip="${esc(marketLine)}">i</span></div><div class="security-name">${esc(companyLine)}</div>${industryLine}${exposureLine}</div></td>
      <td data-label="Account"><div>${esc(cleanSourceLabel(h.account) || "∅")}</div><div class="sub">${esc(accountMeta)}</div>${holdingTransactionActionsHtml(h)}</td>
      <td class="holding-risk-cell" data-label="Risk">${riskBadge(rowRisk)}</td>
      <td data-label="Value / P&L"><div class="value-cell">
        <strong>${money(h.market_value, h.currency)}</strong>
        <button class="units-history-link" type="button" data-position-history-symbol="${esc(h.symbol)}" data-position-history-market="${esc(marketKey)}" data-position-history-account-id="${esc(h.account_id || "")}" data-position-history-account="${esc(cleanSourceLabel(h.account) || "")}" data-position-history-currency="${esc(h.currency || state.baseCurrency)}" data-position-history-quantity="${esc(h.quantity || 0)}" data-position-history-average="${esc(averageBuyPrice)}" data-position-history-asset="${esc(h.asset_class || "EQUITY")}" data-position-history-location="${esc(h.country || h.location || "")}" title="Open buy and sell history">${fmt(h.quantity, 3)} ${esc(optionLabel("units"))}</button>
        <span class="average-buy-price">${esc(optionLabel("Avg buy"))} ${averageBuyPrice ? money(averageBuyPrice, h.currency, 2) : esc(optionLabel("Not available"))}</span>
        <b class="${Number(h.unrealized_profit) >= 0 ? "positive" : "negative"}">${signedMoney(h.unrealized_profit, h.currency)}</b>
      </div></td>
      <td data-label="1Y High / Low">${rangeCell(range, h.currency)}</td>
      <td data-label="Net income">${trendCell(item.profit_trend, "Net income", { currency: h.currency, marketCap: item.market_cap })}</td>
      <td data-label="Dividend Trend">${trendCell(item.dividend_trend, "Annual dividend", { kind: "dividend", currency: h.currency })}</td>
      <td data-label="Support / Resistance">${technicalsCell(sr, movingAverage, h.currency, maPeriod)}</td>
      <td data-label="Data Status">${statusCell(item)}</td>
    </tr>`;
  }).join("");
  bindCompanyLogoImages($("rows"));
  restoreInteraction();
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
          <small class="chart-subtitle">${state.language === "he"
            ? `${esc(optionLabel(selectedLabel))} · שווי ${esc(trendAmount(last, "value"))} · מזומן ${esc(trendAmount(last, "cash"))}`
            : `${esc(selectedLabel)} · Value ${esc(trendAmount(last, "value"))} · Cash ${esc(trendAmount(last, "cash"))}`}</small>
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

  (state.localFunds || [])
    .filter((fund) => state.longTermIncludePension || String(fund.kind || "").trim().toLowerCase() !== "pension")
    .forEach((fund) => {
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
  const pensionToggle = `
    <label class="long-term-pension-toggle">
      <input type="checkbox" data-long-term-include-pension ${state.longTermIncludePension ? "checked" : ""} />
      <span>${esc(optionLabel("Include pension"))}</span>
    </label>`;
  if (!data.details.length || !lines.length) {
    return `
      <div class="chart-card long-term-card">
        <div class="chart-header">
          <div class="chart-title">Long-term funds</div>
          <div class="long-term-controls">${pensionToggle}</div>
        </div>
        <div class="empty">${state.longTermIncludePension ? "No long-term funds or savings accounts yet" : "No non-pension savings to display"}</div>
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
  const monthlySummary = state.longTermIncludePension
    ? ` · <span class="${data.monthly ? "" : "muted-inline"}">${esc(optionLabel("Monthly pension estimate"))} ${data.monthly ? fmt(data.monthly, 0) : optionLabel("N/A")}</span>`
    : "";
  return `
    <div class="chart-card long-term-card">
      <div class="chart-header">
        <div>
          <div class="chart-title">Long-term funds</div>
          <small class="chart-subtitle">${esc(optionLabel("Saved"))} ${money(latest, state.baseCurrency, 0)}${monthlySummary}</small>
        </div>
        <div class="long-term-controls">
          <div class="long-term-control-row">
            ${pensionToggle}
            <div class="dashboard-view-toggle long-term-toggle" aria-label="Long-term dashboard view">
              <button type="button" data-long-term-view="total" class="${view === "total" ? "active" : ""}">Total</button>
              <button type="button" data-long-term-view="people" class="${view === "people" ? "active" : ""}">People</button>
              <button type="button" data-long-term-view="funds" class="${view === "funds" ? "active" : ""}">Funds</button>
            </div>
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

function renderDonut(groups, title, centerLabel, total, centerSub = null, extraClass = "") {
  const circumference = 2 * Math.PI * 42;
  let offset = 0;
  const visibleGroups = groups.slice(0, 6);
  const localizedTitle = optionLabel(title);
  const groupLabel = (label) => extraClass === "currency-allocation-card" && label !== "Unknown" && label !== "Other currencies"
    ? currencyDisplayLabel(label) : optionLabel(label);
  const requestedCenterSub = centerSub || (state.language === "he" ? ["נכס", "מוביל"] : ["TOP", "ASSET"]);
  const centerSubLines = requestedCenterSub.filter(Boolean).map(groupLabel);
  const centerSubText = `<foreignObject x="45" y="66" width="40" height="18" aria-hidden="true"><div xmlns="http://www.w3.org/1999/xhtml" class="donut-center-caption" dir="auto" title="${esc(centerSubLines.join(" "))}">${centerSubLines.slice(0, 2).map((line) => `<span>${esc(line)}</span>`).join("")}</div></foreignObject>`;
  return `
    <div class="chart-card donut-card ${esc(extraClass)}">
      <div class="chart-title">${esc(localizedTitle)}</div>
      <svg viewBox="0 0 130 130" role="img" aria-label="${esc([localizedTitle, centerLabel, ...centerSubLines].filter(Boolean).join(" · "))}">
        <circle cx="65" cy="65" r="42" fill="none" stroke="#202a3f" stroke-width="14"></circle>
        ${visibleGroups.map((group, index) => {
          const dash = total ? (group.value / total) * circumference : 0;
          const percent = total ? Math.round(group.value / total * 100) : 0;
          const tooltip = `${groupLabel(group.label)}\n${money(group.value, state.baseCurrency, 0)}\n${percent}%`;
          const circle = `<circle cx="65" cy="65" r="42" fill="none" stroke="${colorAt(index)}" stroke-width="14" stroke-dasharray="${dash.toFixed(1)} ${(circumference - dash).toFixed(1)}" stroke-dashoffset="${(-offset).toFixed(1)}" transform="rotate(-90 65 65)"><title>${esc(tooltip)}</title></circle>`;
          offset += dash;
          return circle;
        }).join("")}
        <circle cx="65" cy="65" r="28" fill="#171c24" stroke="#2f3848" stroke-width="2"></circle>
        <text x="65" y="60" class="donut-center">${esc(centerLabel)}</text>
        ${centerSubText}
      </svg>
      <div class="donut-legend">
        ${visibleGroups.map((group, index) => {
          const percent = total ? Math.round(group.value / total * 100) : 0;
          const cashAmount = group.label === "Cash" ? ` · ${money(group.value, state.baseCurrency, 0)}` : "";
          const tooltip = `${groupLabel(group.label)} · ${money(group.value, state.baseCurrency, 0)} · ${percent}%`;
          return `<span title="${esc(tooltip)}"><i style="background:${colorAt(index)}"></i>${esc(groupLabel(group.label))} ${percent}%${cashAmount}</span>`;
        }).join("")}
      </div>
    </div>`;
}

function renderCurrencyAllocation(groups, total) {
  const known = groups.filter((group) => group.label !== "Unknown");
  const unknown = groups.find((group) => group.label === "Unknown");
  const visible = known.slice(0, 4);
  const other = sum(known.slice(4).map((group) => group.value));
  if (other) visible.push({ label: "Other currencies", value: other });
  if (unknown) visible.push(unknown);
  visible.sort((left, right) => right.value - left.value);
  const topPercent = total ? Math.round((visible[0]?.value || 0) / total * 100) : 0;
  return renderDonut(visible, "Economic currency exposure", `${topPercent}%`, total, [visible[0]?.label || state.baseCurrency], "currency-allocation-card");
}

function cashByCurrencyData() {
  const totals = {};
  portfolioAccounts().forEach((account) => {
    const currency = account.currency || state.baseCurrency;
    const amount = Math.max(0, accountCashBalance(account));
    if (amount <= 0.005) return;
    totals[currency] = (totals[currency] || 0) + amount;
  });
  return Object.entries(totals)
    .map(([currency, amount]) => ({
      currency,
      amount,
      baseValue: normalizedAmount(amount, currency),
    }))
    .sort((left, right) => right.baseValue - left.baseValue);
}

function renderCashByCurrencyBars() {
  const rows = cashByCurrencyData();
  const title = optionLabel("Cash by currency");
  if (!rows.length) {
    return `
      <div class="chart-card cash-currency-card">
        <div class="chart-title">${esc(title)}</div>
        <div class="empty">${esc(optionLabel("No cash balances"))}</div>
      </div>`;
  }
  const max = Math.max(...rows.map((row) => row.baseValue), 1);
  return `
    <div class="chart-card cash-currency-card">
      <div class="chart-title">${esc(title)}</div>
      <div class="cash-currency-bars" role="img" aria-label="${esc(title)}">
        ${rows.map((row, index) => {
          const width = Math.max(row.baseValue / max * 100, 2);
          const amount = fmt(row.amount, 0);
          const tooltip = `${currencyDisplayLabel(row.currency)}\n${amount}\n${optionLabel("Base equivalent")}: ${money(row.baseValue, state.baseCurrency, 0)}`;
          return `
            <div class="cash-currency-row" title="${esc(tooltip)}">
              <div class="cash-currency-label">
                <span>${esc(currencyDisplayLabel(row.currency))}</span>
                <b>${esc(amount)}</b>
              </div>
              <div class="cash-currency-track"><i style="width:${width.toFixed(1)}%;background:${colorAt(index)}"></i></div>
            </div>`;
        }).join("")}
      </div>
    </div>`;
}

function bondsByCurrencyData(items) {
  const groups = (items || []).reduce((totals, item) => {
    const holding = item.holding || {};
    const isBond = [holding.asset_class, holding.asset_sub_class]
      .some((value) => String(value || "").toUpperCase() === "BOND");
    if (!isBond) return totals;
    const currency = String(holding.currency || state.baseCurrency).toUpperCase();
    const group = totals[currency] || { currency, amount: 0, positions: 0 };
    group.amount += Number(holding.market_value || 0);
    group.positions += 1;
    totals[currency] = group;
    return totals;
  }, {});
  return Object.values(groups)
    .map((group) => ({
      ...group,
      baseValue: normalizedAmount(group.amount, group.currency),
    }))
    .sort((left, right) => Math.abs(right.baseValue) - Math.abs(left.baseValue));
}

function renderBondsByCurrency(items) {
  const rows = bondsByCurrencyData(items);
  const title = optionLabel("Bonds by currency");
  if (!rows.length) {
    return `
      <div class="chart-card bond-currency-card">
        <div class="chart-title">${esc(title)}</div>
        <div class="empty">${esc(optionLabel("No bond holdings"))}</div>
      </div>`;
  }
  const max = Math.max(...rows.map((row) => Math.abs(row.baseValue)), 1);
  const totalBaseValue = sum(rows.map((row) => row.baseValue));
  const positionCount = sum(rows.map((row) => row.positions));
  const positionLabel = optionLabel(positionCount === 1 ? "bond position" : "bond positions");
  return `
    <div class="chart-card bond-currency-card">
      <div class="chart-header bond-currency-header">
        <div>
          <div class="chart-title">${esc(title)}</div>
          <span class="chart-subtitle">${fmt(positionCount, 0)} ${esc(positionLabel)} · ${esc(optionLabel("Base equivalent"))} ${money(totalBaseValue, state.baseCurrency, 0)}</span>
        </div>
      </div>
      <div class="bond-currency-bars" role="img" aria-label="${esc(title)}">
        ${rows.map((row, index) => {
          const width = Math.max(Math.abs(row.baseValue) / max * 100, 2);
          const amount = fmt(row.amount, 0);
          const rowPositionLabel = optionLabel(row.positions === 1 ? "bond position" : "bond positions");
          const tooltip = `${currencyDisplayLabel(row.currency)}\n${money(row.amount, row.currency, 0)}\n${row.positions} ${rowPositionLabel}\n${optionLabel("Base equivalent")}: ${money(row.baseValue, state.baseCurrency, 0)}`;
          return `
            <div class="bond-currency-row" title="${esc(tooltip)}">
              <div class="bond-currency-label">
                <span>${esc(currencyDisplayLabel(row.currency))}</span>
                <b>${esc(amount)}</b>
              </div>
              <div class="bond-currency-track"><i style="width:${width.toFixed(1)}%;background:${colorAt(index)}"></i></div>
            </div>`;
        }).join("")}
      </div>
    </div>`;
}

function renderIndustrySplit(items) {
  const groups = Object.values(items.reduce((result, item) => {
    const label = industryLabel(item) || "Not classified";
    const value = Math.abs(normalizedField(item, "market_value"));
    const group = result[label] || { label, value: 0, holdings: [], items: [] };
    group.value += value;
    group.items.push(item);
    group.holdings.push({
      symbol: item.holding.symbol || "Unknown",
      name: item.holding.name || item.holding.symbol || "Unknown",
      stockMarket: holdingMarketKey(item.holding),
      assetClass: String(item.holding.asset_class || "").toUpperCase(),
      assetSubClass: String(item.holding.asset_sub_class || "").toUpperCase(),
      industrySource: item.industry_source || "",
      value,
    });
    result[label] = group;
    return result;
  }, {}))
    .map((group) => ({ ...group, label: optionLabel(group.label), holdings: group.holdings.sort((a, b) => b.value - a.value) }))
    .sort((a, b) => b.value - a.value);
  const total = sum(groups.map((group) => group.value));
  const combinedCash = sum(portfolioAccounts().map(accountCashValue));
  const portfolioHorizons = portfolioAccounts().map(accountHorizonYears).filter((value) => value !== null);
  const horizonYears = portfolioHorizons.length ? Math.min(...portfolioHorizons) : null;
  groups.forEach((group) => {
    const allocatedCash = total ? combinedCash * (group.value / total) : 0;
    group.risk = riskScoreForItems(group.items, {
      label: `${group.label} industry risk`,
      cash: allocatedCash,
      horizonYears,
    });
  });
  const totalRisk = state.riskSnapshot?.total || portfolioRiskSnapshot(items).total;
  return `
    <div class="chart-card industry-split-card">
      <div class="chart-header">
        <div>
          <div class="chart-title">Industry split</div>
          <span class="chart-subtitle">${state.language === "he" ? `${groups.length} ענפים · ציון הסיכון של כל ענף מחושב בנפרד ואינו מתחבר לציון הכולל` : `${groups.length} industries · each industry risk is calculated separately and does not add up to the total`}</span>
        </div>
        <div class="industry-total-risk">
          <small>${esc(optionLabel("Total portfolio risk"))}</small>
          ${riskBadge(totalRisk)}
        </div>
      </div>
      <div class="industry-split-list" data-preserve-scroll="industry-split">
        ${groups.map((group, index) => {
          const percent = total ? group.value / total * 100 : 0;
          return `
            <div class="industry-split-row">
              <div class="industry-split-head">
                <b>${esc(group.label)}</b>
                <div class="industry-split-metrics">
                  <span>${money(group.value, state.baseCurrency, 0)} · ${fmt(percent, 1)}%</span>
                  <small>${esc(optionLabel("Industry risk"))}</small>
                  ${riskBadge(group.risk, true)}
                </div>
              </div>
              <div class="industry-split-track" title="${esc(`${group.label}: ${fmt(percent, 1)}%`)}">
                <i style="width:${Math.max(percent, 0.8)}%;background:${colorAt(index)}"></i>
              </div>
              <div class="industry-holdings">
                ${group.holdings.map((holding) => {
                  const title = `${holding.name}: ${money(holding.value, state.baseCurrency, 0)}`;
                  const isBond = holding.assetClass === "BOND" || holding.assetSubClass === "BOND";
                  if (isBond) return `<span title="${esc(title)}">${esc(holding.symbol)}</span>`;
                  const actionLabel = holding.industrySource === "manual" ? "Edit manual industry" : "Classify industry";
                  return `<button class="industry-holding-button${holding.industrySource === "manual" ? " is-manual" : ""}" type="button" data-classify-industry-symbol="${esc(holding.symbol)}" data-classify-industry-market="${esc(holding.stockMarket)}" title="${esc(`${optionLabel(actionLabel)} · ${title}`)}"><span>${esc(holding.symbol)}</span><i aria-hidden="true">✎</i><span class="sr-only">${esc(optionLabel(actionLabel))}</span></button>`;
                }).join("")}
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
    const usable = (metric) => metric && ["ok", "partial", "stale"].includes(metric.state);
    const ok = items.filter((item) => missingLabel === "price history"
      ? Object.values(item.price_ranges || {}).some(usable)
      : usable(item[missingLabel === "profit" ? "profit_trend" : "dividend_trend"])).length;
    return { label, ok, total, percent: total ? Math.round((ok / total) * 100) : 0 };
  });
  return `
    <div class="chart-card meters-card">
      <div class="chart-title">Provider data coverage</div>
      ${items.some((item) => ["refreshing", "queued", "updating"].includes(item.analytics_state)) ? `<p class="section-note">${esc(t("Updating analytics in the background"))}</p>` : ""}
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
          <span class="chart-subtitle profit-total-summary">${esc(optionLabel("Total P/L"))} ${money(total, state.baseCurrency, 0)}</span>
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
  [...(state.allPortfolioItems || []), ...(items || [])].forEach((item) => {
    const h = item.holding || {};
    const quantity = Math.abs(Number(h.quantity || 0));
    if (!h.symbol || !quantity) return;
    const price = Math.abs(Number(h.market_value || 0)) / quantity;
    if (!Number.isFinite(price) || price <= 0) return;
    const entry = { price, currency: h.currency || state.baseCurrency, source: "current holding price" };
    [h.symbol, h.secondary_symbol].filter(Boolean).forEach((symbol) => {
      prices.set(txMarketKey(symbol, h.stock_market), entry);
      if (!prices.has(txMarketKey(symbol))) prices.set(txMarketKey(symbol), entry);
    });
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
      return equityCompKind(tx) === "option" ? (tx.underlying_symbol || tx.symbol) : (tx.secondary_symbol || tx.symbol);
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
          : kind === "option" ? (tx.underlying_symbol || tx.symbol) : (tx.secondary_symbol || tx.symbol);
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
            secondarySymbol: tx.secondary_symbol || "",
            underlyingSymbol: employeeOption ? (tx.public_symbol || "") : (tx.underlying_symbol || tx.symbol || ""),
            stockMarket: employeeOption ? (tx.public_market || "PRIVATE") : (tx.stock_market || ""),
            assetClass: tx.asset_class || (kind === "rsu" ? "EQUITY" : "OPTION"),
            location: tx.location || tx.country || "",
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

function equityCompPriceHtml(group) {
  const text = equityCompPriceText(group);
  const missingPrice = group.kind === "rsu"
    ? Number(group.unitPrice || group.currentPrice || 0) <= 0
    : group.publicMarket && !group.hasMarketPrice;
  if (!missingPrice) return esc(text);
  const priceSymbol = group.kind === "option"
    ? (group.underlyingSymbol || group.internalSymbol || group.symbol)
    : (group.internalSymbol || group.symbol);
  return `
    <div class="equity-price-cell">
      <span class="muted-inline">${esc(text)}</span>
      <button class="secondary compact-button equity-price-action" type="button"
        data-price-history-symbol="${esc(priceSymbol)}"
        data-price-history-market="${esc(group.stockMarket || "MANUAL")}"
        data-price-history-asset="${esc(group.kind === "rsu" ? "EQUITY" : (group.assetClass || "OPTION"))}"
        data-price-history-currency="${esc(group.currency || state.baseCurrency)}"
        data-price-history-location="${esc(group.location || "")}">Add market price</button>
    </div>
  `;
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
            <th>Investment type</th>
            <th>Market / strike price</th>
            <th>Vested</th>
            <th>Unvested</th>
          </tr>
        </thead>
        <tbody>
          ${groups.map((group) => {
            const vestedQty = sum(group.vested.map((lot) => lot.quantity));
            const unvestedQty = sum(group.unvested.map((lot) => lot.quantity));
            const unitLabel = group.kind === "rsu" ? "RSU" : "options";
            const vestedTitle = vestingDetailsTitle(group.vested, unitLabel);
            const unvestedTitle = vestingDetailsTitle(group.unvested, unitLabel);
            const instrumentDetail = group.kind === "option"
              ? `${group.publicMarket ? (group.stockMarket || "Public") : "Private company"}${group.underlyingSymbol ? ` · Linked ${group.underlyingSymbol}` : ""}${group.optionType ? ` · ${group.optionType}` : ""}`
              : (group.stockMarket || "No market");
            return `
              <tr>
                <td><b>${esc(group.symbol)}${group.secondarySymbol ? ` · ${esc(group.secondarySymbol)}` : ""}</b><small>${esc(instrumentDetail)}</small></td>
                <td><span class="equity-kind ${group.kind}">${group.kind === "rsu" ? "RSU" : "Option"}</span></td>
                <td>${equityCompPriceHtml(group)}</td>
                <td class="equity-position-cell ${vestedQty ? "vesting-tooltip-cell" : ""}" title="${esc(vestedTitle)}">
                  <div class="equity-position-content">
                    <span class="equity-position-quantity">${fmt(vestedQty, 2)}</span>
                    ${equityCompValueHtml(group.kind, group.vested)}
                  </div>
                </td>
                <td class="equity-position-cell ${unvestedQty ? "vesting-tooltip-cell" : ""}" title="${esc(unvestedTitle)}">
                  <div class="equity-position-content">
                    <span class="equity-position-quantity">${fmt(unvestedQty, 2)}</span>
                    ${equityCompValueHtml(group.kind, group.unvested)}
                  </div>
                </td>
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

function dashboardScrollPositions(board) {
  return new Map([...board.querySelectorAll("[data-preserve-scroll]")]
    .map((element) => [element.dataset.preserveScroll, {
      left: element.scrollLeft,
      top: element.scrollTop,
    }]));
}

function restoreDashboardScrollPositions(board, positions) {
  positions.forEach(({ left, top }, key) => {
    const element = board.querySelector(`[data-preserve-scroll="${key}"]`);
    if (element) {
      element.scrollLeft = left;
      element.scrollTop = top;
    }
  });
}

function renderAnalytics(items) {
  const board = $("analyticsBoard");
  if (!board) return;
  const restoreInteraction = preserveRenderedInteraction(board);
  // Background enrichment replaces dashboard markup. Keep a reader's place in
  // bounded lists so that the refresh is not perceived as a jump to the top.
  const scrollPositions = dashboardScrollPositions(board);
  if (!state.dashboard) loadDashboardSettings();
  renderDashboardControls();
  if (!items.length && !(state.localFunds || []).length && state.dashboard.area !== "employee") {
    board.innerHTML = '<div class="empty">No portfolio data</div>';
    restoreInteraction();
    return;
  }
  const assetGroups = assetMixGroups(items);
  const assetTotal = sum(assetGroups.map((group) => group.value)) || 1;
  const currencyGroups = currencyAllocationGroups(items);
  const currencyTotal = sum(currencyGroups.map((group) => group.value)) || 1;
  const renderers = {
    portfolio_value: () => renderPortfolioValueDashboard(items),
    long_term_savings: () => renderFundsOverviewDashboard(),
    account_trend: () => renderAccountValueTrend(),
    long_term: () => renderLongTermDashboard(),
    market_cost: () => renderMarketCostBars(items),
    asset_mix: () => renderDonut(assetGroups, "Asset mix", `${Math.round((assetGroups[0]?.value || 0) / assetTotal * 100)}%`, assetTotal, null, "asset-mix-card"),
    cash_currency: () => renderCashByCurrencyBars(),
    industry_split: () => renderIndustrySplit(items),
    top_holdings: () => renderMiniBars(items),
    bond_currency: () => renderBondsByCurrency(items),
    coverage: () => renderCompleteness(items),
    currency: () => renderCurrencyAllocation(currencyGroups, currencyTotal),
    equity_comp: () => renderEquityCompDashboard(items),
    profit: () => renderProfitBars(items),
    snapshot: () => renderBubbles(items),
  };
  if (state.dashboard.edit) {
    board.innerHTML = renderDashboardEditor(renderers);
    restoreDashboardScrollPositions(board, scrollPositions);
    restoreInteraction();
    return;
  }
  const visible = visibleDashboardWidgets();
  board.innerHTML = visible.length
    ? visible.map((widget) => withDashboardToolbar(widget, renderers[widget.id]())).join("")
    : '<div class="empty">No dashboard cards in this area</div>';
  restoreDashboardScrollPositions(board, scrollPositions);
  restoreInteraction();
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

function setStatusMessage(id, message, { prominentSuccess = false } = {}) {
  const status = $(id);
  if (!status) return;
  status.textContent = message;
  status.classList.toggle("status-prominent-success", prominentSuccess);
}

function accountLabel(account) {
  const parts = [account.management_company, account.username, account.account_id]
    .map(cleanSourceLabel)
    .filter(Boolean)
    .filter((value, index, values) => values.indexOf(value) === index);
  return parts.join(" · ") || optionLabel("Unnamed account");
}

function accountOptionHtml(account) {
  return `<option value="${esc(account.id)}">${esc(accountLabel(account))}</option>`;
}

function brokerLabel(broker) {
  const name = state.language === "he" ? bidiIsolate(broker.name, "ltr") : broker.name;
  return `${name} · ${countryDisplayLabel(broker.country)} · ${currencyDisplayLabel(broker.currency)}`;
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
  renderBrokersList();
}

function renderBrokersList() {
  const list = $("brokersList");
  if (list) {
    list.innerHTML = state.brokers.length ? state.brokers.map((broker) => `
      <div class="stack-item management-item">
        <b>${esc(broker.name)}</b>
        <span>${esc(countryDisplayLabel(broker.country))} · ${esc(currencyDisplayLabel(broker.currency))}${broker.attached_accounts ? ` · ${broker.attached_accounts} account${broker.attached_accounts === 1 ? "" : "s"}` : ""}</span>
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
    ["Retire Age", member.retire_age != null ? fmt(member.retire_age, 1) : "Not set"],
    ["Age", member.age != null ? fmt(member.age, 1) : ""],
  ].filter(([, value]) => value !== "");
  return rows.map(([label, value]) => `<span><strong>${esc(t(label))}</strong><bdi>${esc(t(value))}</bdi></span>`).join("");
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
  const options = `<option value="">${esc(t("Choose family member"))}</option>` + state.familyMembers
    .map((member) => `<option value="${esc(member.id)}" data-i18n-skip>${esc(memberLabel(member))}</option>`)
    .join("");
  ["localAccountFamilyMember", "editAccountFamilyMember", "familyAttachMember"].forEach((id) => {
    const select = $(id);
    if (!select) return;
    const current = select.value;
    select.innerHTML = options;
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  });
}

function selectedReportPersonName() {
  const member = familyMemberById(valueOf("reportPerson"));
  return member ? memberLabel(member) : "";
}

function reportAccountMatchesPrimaryFilters(account) {
  const accountType = valueOf("reportAccountType");
  const personId = valueOf("reportPerson");
  const personName = selectedReportPersonName().toLocaleLowerCase();
  if (accountType && account.type !== accountType) return false;
  if (!personId) return true;
  return (account.persons || []).some((person) => (
    String(person.member_id || "") === personId
    || (!person.member_id && String(person.name || "").toLocaleLowerCase() === personName)
  ));
}

function refreshReportPersonSelect() {
  const select = $("reportPerson");
  if (!select) return;
  const current = select.value;
  select.innerHTML = `<option value="">${esc(optionLabel("All people"))}</option>` + state.familyMembers
    .map((member) => `<option value="${esc(member.id)}">${esc(memberLabel(member))}</option>`)
    .join("");
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}

function refreshReportAccountSelect() {
  const select = $("reportAccount");
  if (!select) return;
  const current = select.value;
  const accounts = state.localAccounts.filter(reportAccountMatchesPrimaryFilters);
  select.innerHTML = `<option value="">${esc(optionLabel("All matching accounts"))}</option>`
    + accounts.map(accountOptionHtml).join("");
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}

function refreshReportFilterOptions() {
  refreshReportPersonSelect();
  setOptions("reportAccountType", state.localOptions.account_types, optionLabel("All account categories"));
  refreshReportAccountSelect();
}

function refreshFamilyAccountSelects() {
  const options = `<option value="">${esc(t("Choose account"))}</option>` + state.localAccounts
    .map((account) => `<option value="${esc(account.id)}" data-i18n-skip>${esc(accountLabel(account))} · ${esc(t(account.type))}</option>`)
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
  state.familyMembersLoaded = true;
  refreshFamilyMemberSelects();
  refreshReportPersonSelect();
  refreshReportAccountSelect();
  refreshFamilyAccountSelects();
  renderSimulationPersonOptions();
  renderFamilyMembers();
}

function setFamilyStatus(message = "") {
  state.familyStatusMessage = message;
  if ($("familyStatus")) $("familyStatus").textContent = t(message);
}

function renderFamilyMembers() {
  setFamilyStatus(state.familyStatusMessage || "");
  const list = $("familyMembersList");
  if (list && state.familyMembersLoaded) {
    list.innerHTML = state.familyMembers.length ? state.familyMembers.map((member) => {
      const attachedAccounts = member.attached_account_items || [];
      const attached = Number(member.attached_accounts || 0) > 0 || attachedAccounts.length > 0;
      const deleting = (state.deletingFamilyMemberIds || []).includes(member.id);
      return `
      <div class="stack-item management-item family-member-item">
        <div class="family-member-main">
          <b dir="auto" data-i18n-skip>${esc(memberLabel(member))}</b>
          <div class="family-member-meta">${memberMetaHtml(member)}</div>
          ${member.comments ? `<div class="sub" dir="auto" data-i18n-skip>${esc(member.comments)}</div>` : ""}
        </div>
        <div class="family-member-actions">
          <button class="secondary compact-button" type="button" data-edit-family-member="${esc(member.id)}"${deleting ? " disabled" : ""}>${esc(t("Edit"))}</button>
          <button class="secondary compact-button" type="button" data-delete-family-member="${esc(member.id)}"${attached || deleting ? " disabled" : ""} title="${esc(t(attached ? "Cannot delete while attached to an account" : "Remove family member"))}">${esc(t(deleting ? "Deleting…" : "Delete"))}</button>
        </div>
        <div class="attached-account-list">
          ${attachedAccounts.length ? attachedAccounts.map((account) => `<span><bdi data-i18n-skip>${esc(account.label)}</bdi> · ${esc(t(account.type))}</span>`).join("") : `<em>${esc(t("No attached accounts"))}</em>`}
          ${attached ? `<small class="family-member-delete-note">${esc(t("Cannot delete while attached to an account"))}</small>` : ""}
        </div>
      </div>
    `;
    }).join("") : `<div class="empty">${esc(t("No family members yet"))}</div>`;
  }
}

async function saveFamilyMember() {
  if (!canWrite() || state.familyMemberSaving) return;
  const firstName = valueOf("familyMemberFirstName");
  const birthDate = dateValue("familyMemberBirthDate");
  const retireAge = valueOf("familyMemberRetireAge");
  if (!firstName) return familyMemberValidation("First name is required.", "familyMemberFirstName");
  if (!birthDate) {
    return familyMemberValidation("Enter a valid birth date in dd/mm/yyyy.", "familyMemberBirthDate");
  }
  if (birthDate > todayString()) return familyMemberValidation("Birth date cannot be in the future.", "familyMemberBirthDate");
  if ($("familyMemberRetireAge").validity.badInput || (retireAge !== "" && (!Number.isFinite(Number(retireAge)) || Number(retireAge) < 0))) {
    return familyMemberValidation("Retirement age must be zero or a positive number.", "familyMemberRetireAge");
  }
  const editingId = state.editingFamilyMemberId;
  const payload = {
      id: editingId || undefined,
      first_name: firstName,
      last_name: valueOf("familyMemberLastName"),
      gender: valueOf("familyMemberGender"),
      birth_date: birthDate,
      retire_age: retireAge,
      comments: valueOf("familyMemberComments"),
  };
  state.familyMemberError = "";
  state.familyMemberErrorField = "";
  setFamilyMemberSaving(true);
  try {
    const saved = await api("/api/local/family-members", { method: "POST", body: JSON.stringify(payload) });
    const existing = familyMemberById(saved.id);
    state.familyMembers = [...state.familyMembers.filter((member) => member.id !== saved.id), { ...existing, ...saved }];
    state.familyMembersLoaded = true;
    refreshFamilyMemberSelects();
    refreshReportPersonSelect();
    renderSimulationPersonOptions();
    renderFamilyMembers();
    const refreshed = await Promise.allSettled([loadFamilyMembers(), loadLocalAccounts()]);
    setFamilyStatus(refreshed.some((result) => result.status === "rejected")
      ? "Person saved. Some linked data could not refresh; reopen People to retry."
      : editingId ? "Person updated" : "Person saved");
    setFamilyMemberSaving(false);
    if (!$("familyMemberModal").hidden) closeModal($("familyMemberModal"));
  } catch (_error) {
    state.familyMemberError = "Could not save this person. Check the details and try again.";
    renderFamilyMemberEditor();
  } finally {
    setFamilyMemberSaving(false);
    if (state.familyMemberError && !$("familyMemberModal").hidden) requestAnimationFrame(() => $("saveFamilyMember")?.focus());
  }
}

function clearFamilyMemberForm() {
  state.editingFamilyMemberId = "";
  ["familyMemberFirstName", "familyMemberLastName", "familyMemberBirthDate", "familyMemberRetireAge", "familyMemberComments"].forEach((id) => { $(id).value = ""; });
  $("familyMemberGender").value = "";
  state.familyMemberError = "";
  state.familyMemberErrorField = "";
}

function familyMemberValidation(message, field) {
  state.familyMemberError = message;
  state.familyMemberErrorField = field;
  renderFamilyMemberEditor();
  $(field)?.focus();
}

function renderFamilyMemberEditor() {
  if (!$("familyMemberEditorTitle")) return;
  $("familyMemberEditorTitle").textContent = t(state.editingFamilyMemberId ? "Edit person" : "Add person");
  $("familyMemberEditorStatus").textContent = t(state.familyMemberError || "");
  $("saveFamilyMember").textContent = t(state.familyMemberSaving ? "Saving person…" : "Save person");
  $("familyMemberForm").querySelectorAll("input, select, textarea").forEach((field) => {
    if (field.id === state.familyMemberErrorField) {
      field.setAttribute("aria-invalid", "true");
      field.setAttribute("aria-describedby", "familyMemberEditorStatus");
    } else {
      field.removeAttribute("aria-invalid");
      field.removeAttribute("aria-describedby");
    }
  });
}

function setFamilyMemberSaving(saving) {
  state.familyMemberSaving = saving;
  $("familyMemberModal").querySelectorAll("button, input, select, textarea").forEach((control) => { control.disabled = saving; });
  $("saveFamilyMember").disabled = saving || !canWrite();
  $("newFamilyMember").disabled = saving || !canWrite();
  $("familyMemberForm").setAttribute("aria-busy", String(saving));
  renderFamilyMemberEditor();
}

function openFamilyMemberEditor(memberId = "", returnFocus = document.activeElement) {
  if (!canWrite() || state.familyMemberSaving) return;
  const member = memberId ? familyMemberById(memberId) : null;
  if (memberId && !member) return;
  clearFamilyMemberForm();
  if (member) {
    state.editingFamilyMemberId = member.id;
    $("familyMemberFirstName").value = member.first_name || "";
    $("familyMemberLastName").value = member.last_name || "";
    $("familyMemberGender").value = member.gender || "";
    setDateField("familyMemberBirthDate", member.birth_date || "");
    $("familyMemberRetireAge").value = member.retire_age ?? "";
    $("familyMemberComments").value = member.comments || "";
  }
  renderFamilyMemberEditor();
  $("familyModal").inert = true;
  $("familyModal").setAttribute("aria-hidden", "true");
  openModal("familyMemberModal", returnFocus, { focusId: "familyMemberFirstName" });
}

function editFamilyMember(memberId, returnFocus = document.activeElement) {
  openFamilyMemberEditor(memberId, returnFocus);
}

async function deleteFamilyMember(memberId) {
  if (!canWrite() || (state.deletingFamilyMemberIds || []).includes(memberId)) return;
  const member = familyMemberById(memberId);
  if (!member) return;
  if (Number(member.attached_accounts || 0) > 0 || member.attached_account_items?.length) {
    setFamilyStatus("Cannot delete while attached to an account");
    return;
  }
  if (!window.confirm(t("Delete {name}? This cannot be undone.").replace("{name}", memberLabel(member)))) return;
  state.deletingFamilyMemberIds = [...(state.deletingFamilyMemberIds || []), memberId];
  renderFamilyMembers();
  try {
    await api(`/api/local/family-members/${encodeURIComponent(memberId)}`, { method: "DELETE" });
    state.familyMembers = state.familyMembers.filter((item) => item.id !== memberId);
    renderFamilyMembers();
    refreshFamilyMemberSelects();
    refreshReportPersonSelect();
    renderSimulationPersonOptions();
    const refreshed = await Promise.allSettled([loadFamilyMembers(), loadLocalAccounts()]);
    setFamilyStatus(refreshed.some((result) => result.status === "rejected") ? "Person deleted. Reopen People to refresh linked data." : "Person deleted");
    $("newFamilyMember")?.focus();
  } catch (_error) {
    setFamilyStatus("Could not delete this person. They may have linked accounts; refresh People and try again.");
  } finally {
    state.deletingFamilyMemberIds = state.deletingFamilyMemberIds.filter((id) => id !== memberId);
    renderFamilyMembers();
  }
}

function attachFamilyMember(listKey, selectId, statusId, { single = false } = {}) {
  const member = familyMemberById(valueOf(selectId));
  if (!member) {
    setStatusMessage(statusId, "Choose a family member first");
    return;
  }
  const person = personFromFamilyMember(member);
  const current = state[listKey] || [];
  if (current.some((item) => item.member_id === person.member_id)) {
    setStatusMessage(statusId, "Family member already attached");
    return;
  }
  state[listKey] = single ? [person] : current.concat(person);
  $(selectId).value = "";
  setStatusMessage(statusId, single ? "Family member attached" : `${state[listKey].length} family members attached`);
  renderPersonLists();
}

function accountAllowsMultipleMembers(account) {
  return !["Long-Term Savings", "ESOP"].includes(account?.type);
}

function validateAccountOwnership(type, persons, statusId) {
  if (!persons.length) {
    setStatusMessage(statusId, state.language === "he"
      ? "יש לשייך כל חשבון לאדם אחד לפחות"
      : "Every account must be assigned to at least one person");
    return false;
  }
  if (!["Long-Term Savings", "ESOP"].includes(type) || persons.length === 1) return true;
  setStatusMessage(statusId, state.language === "he"
    ? "לחשבון חיסכון ארוך טווח או אופציות לעובדים חייב להיות אדם אחד בדיוק"
    : "Long-Term Savings and ESOP accounts must have exactly one person");
  return false;
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
  ["securityAccount", "employeeWizardAccount", "employeeExerciseAccount"].forEach((id) => {
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
  refreshReportAccountSelect();
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
  const accounts = (state.localAccounts || []).filter((account) => account.type === "Long-Term Savings" && (account.persons || []).length === 1);
  const emptyLabel = state.language === "he" ? "בחירת חשבון חיסכון ארוך טווח" : "Choose a long-term account";
  const options = `<option value="">${esc(emptyLabel)}</option>` + accounts.map(accountOptionHtml).join("");
  ["fundAccount", "editFundAccount"].forEach((id) => {
    const select = $(id);
    if (!select) return;
    const current = select.value;
    select.innerHTML = options;
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  });
  renderFundAccountOwners();
  updateFundActionStates();
}

function renderFundAccountOwner(selectId, targetId) {
  const target = $(targetId);
  if (!target) return;
  const account = state.localAccounts.find((item) => item.id === valueOf(selectId));
  const person = account?.persons?.[0];
  if (!account || !person) {
    target.textContent = state.language === "he"
      ? "יש לבחור חשבון חיסכון ארוך טווח כדי להשתמש באדם המשויך אליו."
      : "Choose a long-term account to use its assigned person.";
    return;
  }
  target.textContent = state.language === "he"
    ? `האדם ישויך אוטומטית מהחשבון: ${personLabel(person)}`
    : `Person inherited automatically from the account: ${personLabel(person)}`;
}

function renderFundAccountOwners() {
  renderFundAccountOwner("fundAccount", "fundAccountOwner");
  renderFundAccountOwner("editFundAccount", "editFundAccountOwner");
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
    ["Imported accounts", importedAccounts, "Accounts synced from the configured import source"],
    ["Manual accounts", manualAccounts, "Accounts created directly in this dashboard"],
    ["Attached securities", data.sync?.attached_positions ?? data.status?.transactions ?? 0, "Imported securities linked to local account records"],
    ["Local DB records", data.status?.transactions ?? 0, "Stored security transactions and imported position links"],
  ].map(([label, value, tooltip]) => `<div class="stat" title="${esc(tooltip)}"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join("");
  renderLocalAccountsList();
  renderPersonLists();
}

function renderLocalAccountsList() {
  const list = $("accountsList");
  if (!list) return;
  list.innerHTML = state.localAccounts.length ? state.localAccounts.map((account) => {
    const attachmentRows = [
      ["transactions", "Security transactions"],
      ["funds", "Pension and fund records"],
      ["account_snapshots", "Account history points"],
      ["events", "Account events"],
      ["equity_transitions", "Equity transitions"],
    ].map(([key, label]) => [Number(account.attachment_counts?.[key] || 0), label]).filter(([count]) => count > 0);
    const removalDisabled = account.can_delete === false || attachmentRows.length > 0;
    const removalHelp = removalDisabled ? `
      <details class="row-action-help account-delete-help" style="--attachment-rows:${attachmentRows.length}">
        <summary aria-label="${esc(optionLabel("Why account removal is disabled"))}" title="${esc(optionLabel("Why account removal is disabled"))}">i</summary>
        <div class="row-action-help-popover" role="note">
          <strong>${esc(optionLabel("Cannot remove this account while data is attached."))}</strong>
          <span>${esc(optionLabel("Attached to this account"))}</span>
          <ul>${attachmentRows.map(([count, label]) => `<li><span>${esc(optionLabel(label))}</span><b>${esc(fmt(count, 0))}</b></li>`).join("")}</ul>
        </div>
      </details>` : "";
    return `
      <div class="stack-item management-item account-management-item">
        <div class="account-management-main">
          <b>${esc(accountLabel(account))}</b>
          <span>${esc(optionLabel(account.type))} · ${esc(countryDisplayLabel(account.location))} · ${esc(currencyDisplayLabel(account.currency))} · ${esc(optionLabel(isImportedAccount(account) ? "Imported" : "Manual"))}</span>
          ${isImportedAccount(account) ? '<span class="badge ok" title="Synced from the configured import source. Refresh with Sync import.">Synced</span>' : '<span class="badge" title="Manual account">Manual</span>'}
        </div>
        <div class="row-actions account-management-actions">
          <button class="secondary compact-button" type="button" data-edit-account="${esc(account.id)}">Edit</button>
          <button class="secondary compact-button" type="button" data-delete-account="${esc(account.id)}"${removalDisabled ? " disabled" : ""}>Remove</button>
          ${removalHelp}
        </div>
        <div class="sub">${esc(optionLabel("Initial cash"))} ${fmt(account.initial_cash)}${(account.persons || []).length ? ` · ${(account.persons || []).map(personLabel).map(esc).join(" · ")}` : ""} · ${esc(cleanSourceLabel(account.comments) || optionLabel("No comments"))}</div>
      </div>
    `;
  }).join("") : '<div class="empty">No local accounts yet</div>';
}

async function removeLocalAccount(accountId) {
  const account = state.localAccounts.find((item) => item.id === accountId);
  if (!account || account.can_delete === false) return;
  const question = state.language === "he"
    ? `להסיר את החשבון ${accountLabel(account)}? לא ניתן לבטל פעולה זו.`
    : `Remove account ${accountLabel(account)}? This cannot be undone.`;
  if (!confirm(question)) return;
  await api(`/api/local/accounts/${accountId}`, { method: "DELETE" });
  setStatusMessage("accountsStatus", state.language === "he" ? "החשבון הוסר" : "Account removed");
  await Promise.all([loadLocalAccounts(), loadPortfolio()]);
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
  const accountType = valueOf("localAccountType");
  if (!validateAccountOwnership(accountType, state.localAccountPersons, "accountsStatus")) return;
  const payload = {
    type: accountType,
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
  setStatusMessage("accountsStatus", "Account created", { prominentSuccess: true });
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
  const accountType = valueOf("editAccountType");
  if (!validateAccountOwnership(accountType, state.editAccountPersons, "editAccountStatus")) return;
  if (!confirm(`Save changes to ${accountLabel(account)}?`)) return;
  const country = normalizeAccountCountry(valueOf("editAccountLocation"));
  const payload = {
    id: account.id,
    type: accountType,
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
  setStatusMessage("accountsStatus", "Account updated");
  $("editAccountStatus").textContent = "Account updated";
  closeModal($("accountEditModal"));
  state.editingAccountId = "";
  state.editAccountPersons = [];
  await loadLocalAccounts();
  await loadPortfolio();
}

async function importSourceToLocal() {
  setStatusMessage("accountsStatus", "Importing holdings");
  state.importSkippedAccounts = [];
  renderImportSkippedAccounts();
  appLog("source_import.start");
  const result = await api("/api/local/import/source", { method: "POST", body: "{}" });
  appLog("source_import.done", {
    accounts: result.accounts,
    positions: result.positions,
    source_transactions: result.source_transactions,
    price_history: result.price_history,
    skipped_accounts: (result.skipped_accounts || []).length,
    skipped_positions: result.skipped_positions || 0,
    skipped_transactions: result.skipped_transactions || 0,
    source: result.source,
  });
  state.importSkippedAccounts = result.skipped_accounts || [];
  if (result.partial) {
    setStatusMessage("accountsStatus", state.language === "he"
      ? `הייבוא הושלם עם שגיאות: ${state.importSkippedAccounts.length} חשבונות דולגו, ${result.skipped_positions || 0} החזקות ו־${result.skipped_transactions || 0} תנועות לא יובאו.`
      : `Import completed with errors: ${state.importSkippedAccounts.length} accounts skipped; ${result.skipped_positions || 0} positions and ${result.skipped_transactions || 0} transactions were not imported.`);
  } else {
    setStatusMessage("accountsStatus", state.language === "he"
      ? `יובאו ${result.positions || 0} החזקות ועודכנו ${result.account_cash_updated || 0} חשבונות.`
      : `Imported ${result.positions || 0} positions and updated ${result.account_cash_updated || 0} accounts.`);
  }
  renderImportSkippedAccounts();
  await loadLocalAccounts();
  await loadLocalSecurities();
  await loadLocalPrices();
  await loadPortfolio({ refresh: true });
}

function renderImportSkippedAccounts() {
  const frame = $("importSkippedList");
  if (!frame) return;
  const items = state.importSkippedAccounts || [];
  frame.hidden = !items.length;
  frame.innerHTML = items.map((item, index) => {
    const reason = item.reason === "account_owner_required"
      ? (state.language === "he" ? "החשבון קיים אך חסר לו שיוך תקין לאדם." : "The account exists but does not have a valid person assignment.")
      : (state.language === "he" ? "החשבון אינו קיים מקומית ולכן הנתונים שלו דולגו." : "The account does not exist locally, so its data was skipped.");
    const facts = [
      `${state.language === "he" ? "מטבע" : "Currency"}: ${currencyDisplayLabel(item.currency)}`,
      item.has_cash ? `${state.language === "he" ? "מזומן שלא יובא" : "Cash not imported"}: ${fmt(item.cash, 2)}` : "",
      `${state.language === "he" ? "החזקות שלא יובאו" : "Positions not imported"}: ${item.positions || 0}`,
      `${state.language === "he" ? "תנועות שלא יובאו" : "Transactions not imported"}: ${item.transactions || 0}`,
    ].filter(Boolean).join(" · ");
    const action = item.existing_account_id
      ? `<button class="secondary compact-button" type="button" data-fix-skipped-account="${index}">${state.language === "he" ? "שיוך אדם לחשבון" : "Assign a person"}</button>`
      : `<button class="secondary compact-button" type="button" data-add-skipped-account="${index}">${state.language === "he" ? "הוספת החשבון ידנית" : "Add account manually"}</button>`;
    return `
      <div class="stack-item management-item import-skipped-item">
        <b>${esc(state.language === "he" ? `לא יובא: ${item.account}` : `Not imported: ${item.account}`)}</b>
        <span>${esc(reason)}</span>
        ${action}
        <div class="sub">${esc(facts)}</div>
      </div>
    `;
  }).join("");
}

function prepareSkippedImportAccount(index) {
  const item = state.importSkippedAccounts?.[Number(index)];
  if (!item) return;
  if (item.existing_account_id) {
    editLocalAccount(item.existing_account_id);
    $("editAccountStatus").textContent = state.language === "he"
      ? "יש לשייך אדם אחד לפחות לפני הייבוא הבא."
      : "Assign at least one person before the next import.";
    requestAnimationFrame(() => $("editAccountFamilyMember")?.focus());
    return;
  }
  resetNewAccountForm();
  setAccountsTab("new");
  $("localAccountType").value = "Investment";
  $("localAccountLocation").value = item.currency === "ILS" ? "Israel" : "USA";
  $("localAccountCurrency").value = item.currency || "USD";
  $("localInitialCash").value = item.has_cash ? item.cash : 0;
  $("localUsername").value = item.account || "";
  $("localAccountId").value = item.required_account_id || item.account || "";
  ensureBrokerOption(item.platform);
  $("localAccountBroker").value = item.platform || "";
  $("localAccountComments").value = state.language === "he" ? "נוצר ידנית עבור ייבוא חיצוני" : "Created manually for external import";
  setStatusMessage("accountsStatus", state.language === "he"
    ? "החשבון הוכן. יש לשייך אדם אחד לפחות ולאחר השמירה להפעיל שוב את הייבוא."
    : "The account is ready. Assign at least one person, save it, then run the import again.");
  requestAnimationFrame(() => $("localAccountFamilyMember")?.focus());
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
    : `${item.symbol}${item.secondary_symbol ? ` · ${item.secondary_symbol}` : ""}`;
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
  const isRsu = String(valueOf("securityAssetClass") || "").toUpperCase() === "RSU";
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
    <span>Editing history for <b>${esc(focus.symbol)}</b> · ${esc(focus.stock_market || "MANUAL")} · ${esc(focus.asset_class || "")} · ${esc(currencyDisplayLabel(focus.currency || ""))}</span>
    <button class="secondary compact-button" type="button" data-clear-price-focus>Show all prices</button>
  `;
}

function priceMatchesFocus(price) {
  const focus = state.priceFocus;
  if (!focus) return true;
  return cleanSecuritySymbol(price.symbol) === cleanSecuritySymbol(focus.symbol)
    && String(price.stock_market || "").toUpperCase() === String(focus.stock_market || "").toUpperCase();
}

function openPriceHistoryForSecurity(dataset, returnFocus = document.activeElement) {
  state.priceFocus = {
    symbol: cleanSecuritySymbol(dataset.priceHistorySymbol || dataset.securityDetailSymbol),
    stock_market: String(dataset.priceHistoryMarket || dataset.securityDetailMarketKey || "MANUAL").toUpperCase(),
    asset_class: dataset.priceHistoryAsset || dataset.securityDetailAsset || "EQUITY",
    currency: dataset.priceHistoryCurrency || dataset.securityDetailCurrency || "USD",
    location: dataset.priceHistoryLocation || dataset.securityDetailLocation || "USA",
  };
  fillPriceFormFromFocus();
  openModal("pricesModal", returnFocus, { focusId: "priceInput" });
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

function holdingTransactionActions(quantity) {
  const current = Number(quantity);
  if (!Number.isFinite(current)) return [];
  if (current > 0) return ["BUY", "SELL"];
  if (current < 0) return ["SHORT", "BUY"];
  return ["BUY"];
}

function holdingTransactionActionLabel(action, quantity) {
  return t(action === "BUY" ? (Number(quantity) < 0 ? "Buy to cover" : "Buy")
    : action === "SHORT" ? "Add short" : "Sell");
}

function holdingTransactionActionsHtml(holding) {
  if (!canWrite() || !holding.account_id) return "";
  const quantity = Number(holding.quantity);
  const average = quantity ? Math.abs(Number(holding.cost_basis || 0) / quantity) : 0;
  const attributes = {
    symbol: holding.symbol, market: holdingMarketKey(holding), accountId: holding.account_id,
    account: cleanSourceLabel(holding.account || ""), currency: holding.currency || state.baseCurrency,
    quantity, average, asset: holding.asset_class || "EQUITY", location: holding.country || holding.location || "",
  };
  const context = Object.entries(attributes).map(([key, value]) => {
    const name = key.replace(/[A-Z]/gu, (letter) => `-${letter.toLowerCase()}`);
    return `data-position-history-${name}="${esc(value)}"`;
  }).join(" ");
  return `<div class="row-actions holding-transaction-actions">${holdingTransactionActions(quantity).map((action) => {
    const label = holdingTransactionActionLabel(action, quantity);
    return `<button class="secondary compact-button" type="button" data-position-action="${action}" ${context} aria-label="${esc(`${label} · ${holding.symbol} · ${attributes.account}`)}">${esc(label)}</button>`;
  }).join("")}</div>`;
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
  const actionSelect = $("positionTransactionAction");
  const allowed = holdingTransactionActions(current);
  [...actionSelect.options].forEach((option) => {
    option.disabled = !state.editingPositionTransactionId && !allowed.includes(option.value);
    option.hidden = option.disabled;
    option.textContent = holdingTransactionActionLabel(option.value, current);
  });
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
  $("positionTransactionStatus").textContent = t(message);
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
  if (!state.editingPositionTransactionId && !holdingTransactionActions(state.positionTransactionsDetail?.quantity).includes(action)) {
    throw new Error(t("This action is unavailable for the current position"));
  }
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
  if (!detail || !canWrite() || state.positionTransactionSaving) return;
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
  state.positionTransactionSaving = true;
  $("savePositionTransaction").disabled = true;
  $("positionTransactionStatus").textContent = t(editing ? "Updating transaction…" : "Saving transaction…");
  const path = editing ? `/api/local/securities/${encodeURIComponent(editing.id)}` : "/api/local/securities";
  let result;
  try {
    result = await api(path, { method: editing ? "PUT" : "POST", body: JSON.stringify(payload) });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(t("Could not confirm the save. Check transaction history before trying again."));
    }
    throw error;
  } finally {
    state.positionTransactionSaving = false;
    $("savePositionTransaction").disabled = !canWrite();
  }
  state.localTransactions = [result, ...state.localTransactions.filter((tx) => tx.id !== result.id)];
  const message = t(editing ? "Transaction updated successfully." : "Transaction added successfully.")
    + (result.position_closed ? ` ${t("Position closed. No units remain.")}` : "");
  if (state.positionTransactionsDetail === detail) {
    detail.quantity = Number(result.position_quantity);
    clearPositionTransactionForm(message);
    renderPositionTransactionHistory();
  }
  // The saved transaction is already confirmed; analytics must not delay or undo its feedback.
  loadPortfolio().then(() => {
    if (!$("positionsModal")?.hidden) loadTradeHistory();
    if (state.positionTransactionsDetail !== detail) return;
    refreshPositionTransactionDetail(result.position_quantity);
    renderPositionTransactionHistory();
  }).catch(() => {
    if (state.positionTransactionsDetail !== detail) return;
    $("positionTransactionStatus").textContent = `${message} ${t("Dashboard refresh failed. Your transaction is saved; refresh the dashboard to update totals.")}`;
  });
}

function renderPositionTransactionHistory() {
  const detail = state.positionTransactionsDetail;
  if (!detail) return;
  const positionActions = new Set(["BUY", "SELL", "ADD", "REMOVE", "SHORT"]);
  const transactions = state.localTransactions
    .filter((tx) => positionActions.has(String(tx.action || "").toUpperCase()))
    .filter((tx) => transactionMatchesPosition(tx, detail))
    .sort((a, b) => String(b.trade_date || "").localeCompare(String(a.trade_date || ""))
      || String(b.created_at || "").localeCompare(String(a.created_at || "")));
  $("positionTransactionsTitle").textContent = t(`${detail.symbol} buy / sell history`);
  $("positionTransactionsSubtitle").textContent = [detail.account, `${fmt(detail.quantity, 3)} ${t("units")}`, detail.average ? `${t("Avg buy")} ${money(detail.average, detail.currency, 2)}` : ""].filter(Boolean).join(" · ");
  $("positionTransactionsRows").innerHTML = transactions.length ? transactions.map((tx) => {
    const displayAction = positionTransactionDisplayAction(tx);
    const sourceLabel = String(tx.source || "").toLowerCase().endsWith("_import") ? "Imported" : cleanSourceLabel(tx.source || "Manual");
    const amount = Math.abs(Number(tx.quantity || 0) * Number(tx.price || 0));
    const actionClass = ["BUY", "ADD"].includes(displayAction) ? "positive" : "negative";
    return `<tr>
      <td>${esc(formatDate(tx.trade_date))}</td>
      <td><span class="transaction-action ${actionClass}">${esc(t({ BUY: "Buy", SELL: "Sell", SHORT: "Short", ADD: "Add", REMOVE: "Remove" }[displayAction] || displayAction))}</span></td>
      <td>${fmt(tx.quantity, 4)}</td>
      <td>${money(tx.price, tx.currency || detail.currency, 4)}</td>
      <td>${money(amount, tx.currency || detail.currency, 2)}</td>
      <td>${esc(sourceLabel)}</td>
      <td>${esc(cleanSourceLabel(tx.comments || "")) || "—"}</td>
      <td><button class="secondary compact-button" type="button" data-edit-position-transaction="${esc(tx.id)}">Edit</button></td>
    </tr>`;
  }).join("") : '<tr><td colspan="8" class="empty-cell">No buy or sell transactions found for this position</td></tr>';
}

async function openPositionTransactionHistory(dataset, returnFocus) {
  const requestedAction = dataset.positionAction;
  if (requestedAction && (!canWrite() || !dataset.positionHistoryAccountId
    || !holdingTransactionActions(dataset.positionHistoryQuantity).includes(requestedAction))) return;
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
  openModal("positionTransactionsModal", returnFocus);
  clearPositionTransactionForm();
  if (requestedAction) {
    $("positionTransactionAction").value = requestedAction;
    syncPositionTransactionLimit();
    $("positionTransactionQuantity").focus();
  }
  $("positionTransactionsRows").innerHTML = '<tr><td colspan="8" class="empty-cell">Loading transaction history…</td></tr>';
  const data = await api("/api/local/securities");
  state.localTransactions = data.items || [];
  renderPositionTransactionHistory();
}

function priceMatchesSecurity(price, detail) {
  return [detail.symbol, detail.secondary_symbol].some((symbol) => cleanSecuritySymbol(price.symbol) === cleanSecuritySymbol(symbol))
    && String(price.stock_market || "").toUpperCase() === String(detail.market_key || detail.stock_market || "").toUpperCase();
}

async function openSecurityDetail(dataset) {
  const symbol = cleanSecuritySymbol(dataset.securityDetailSymbol);
  const marketKey = String(dataset.securityDetailMarketKey || "MANUAL").toUpperCase();
  const item = (state.allPortfolioItems || state.items).find((candidate) => securityMatches(candidate, symbol, marketKey));
  const h = item?.holding || {};
  state.securityDetail = {
    item,
    symbol,
    secondary_symbol: h.secondary_symbol || "",
    market_key: marketKey,
    stock_market: dataset.securityDetailStockMarket || stockMarketDisplay(h, marketKey, item?.exchange),
    data_provider: dataset.securityDetailProvider || dataProviderDisplay(item || {}, h, marketKey),
    asset_class: dataset.securityDetailAsset || h.asset_class || "EQUITY",
    currency: dataset.securityDetailCurrency || h.currency || "USD",
    location: dataset.securityDetailLocation || h.country || h.location || "USA",
  };
  state.securityChartStartDate = clampedHistoryDate(state.securityChartStartDate);
  resetSecurityChartZoom({ render: false });
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
  $("securityDetailTitle").textContent = `${detail.symbol}${detail.secondary_symbol ? ` · ${detail.secondary_symbol}` : ""} overview`;
  $("securityDetailOverview").innerHTML = [
    ["Name", h.name || detail.symbol],
    ...(detail.secondary_symbol ? [["Secondary symbol", detail.secondary_symbol, "Optional alternate ticker used for market-data lookup."]] : []),
    ["Stock market", detail.stock_market, "The exchange/market where the security trades. This is not the API provider."],
    ["Data provider", detail.data_provider, "Where the market data was read from."],
    ["Type", h.asset_class || detail.asset_class],
    ["Currency", currencyDisplayLabel(h.currency || detail.currency)],
    ["Quantity", fmt(h.quantity || 0, 4)],
    ["Market value", money(h.market_value || 0, h.currency || detail.currency)],
    ["Cost basis", money(h.cost_basis || 0, h.currency || detail.currency)],
    ["Average buy price", Math.abs(Number(h.quantity || 0)) ? money(Math.abs(Number(h.cost_basis || 0) / Number(h.quantity || 0)), h.currency || detail.currency, 2) : "Not available"],
    ["Holding profit (open)", signedMoney(h.unrealized_profit || 0, h.currency || detail.currency), "Profit/loss on the quantity still held. It changes with the current price."],
    ["Closed profit", signedMoney(h.realized_profit || 0, h.currency || detail.currency), "Profit/loss already recorded by sell, cover, dividend, interest, or fee transactions."],
    ["Account", cleanSourceLabel(h.account || "")],
  ].map(([label, value, title]) => `<div class="security-kpi" title="${esc(title || "")}"><span>${esc(optionLabel(label))}</span><b>${esc(value || "∅")}</b></div>`).join("");
  const txs = state.localTransactions.filter((tx) => transactionMatchesSecurity(tx, detail));
  $("securityDetailTransactions").innerHTML = txs.length ? txs.map((tx) => `
    <div class="stack-item management-item">
      <b>${esc(tx.action)} ${fmt(tx.quantity, 4)}</b>
    <span>${esc(formatDate(tx.trade_date))} · input ${fmt(tx.price_input, 4)} · ${esc(currencyDisplayLabel(tx.currency))} ${fmt(tx.price, 4)}</span>
      <button class="secondary compact-button" type="button" data-edit-security="${esc(tx.id)}">Edit</button>
      <button class="secondary compact-button" type="button" data-delete-security="${esc(tx.id)}">Delete</button>
      <div class="sub">${transactionCashImpact(tx) ? `Cash ${signedMoney(transactionCashImpact(tx), tx.currency)}` : "No cash movement"} · ${esc(cleanSourceLabel(tx.management_company || ""))} ${esc(cleanSourceLabel(tx.account_id || ""))}${tx.comments ? ` · ${esc(cleanSourceLabel(tx.comments))}` : ""}</div>
    </div>
  `).join("") : '<div class="empty">No transactions for this security</div>';
  const prices = state.localPrices.filter((price) => priceMatchesSecurity(price, detail));
  $("securityDetailPrices").innerHTML = prices.length ? prices.map((price) => `
    <div class="stack-item management-item">
      <b>${esc(formatDate(price.price_date))}</b>
      <span>${fmt(price.price_input, 4)} · ${esc(currencyDisplayLabel(price.currency))} ${fmt(price.price, 4)}</span>
      <button class="secondary compact-button" type="button" data-delete-price="${esc(price.id)}">Remove</button>
      <div class="sub">${esc(price.asset_class)} · ${esc(countryDisplayLabel(price.location))}${price.comments ? ` · ${esc(price.comments)}` : ""}</div>
    </div>
  `).join("") : '<div class="empty">No saved price history for this security</div>';
  renderSecurityTechnicalSignal();
  renderSecurityChart();
}

function renderSecurityTechnicalSignal() {
  const frame = $("securityTechnicalSignal");
  if (!frame) return;
  const signal = state.securityHistoryMeta?.technical_signals?.confirmed_breakout || {};
  const missing = signal.state !== "ok";
  const triggered = signal.state === "ok" && signal.triggered === true;
  const title = missing ? "Signal unavailable" : triggered ? "Confirmed breakout" : "Breakout watch";
  const summary = missing
    ? "More price or volume history is required."
    : triggered
      ? "The resistance breakout has both volume and MA30 confirmation."
      : "Confirmation is incomplete; review the conditions below.";
  const fallbackLabels = {
    resistance_breakout: "Price crossed above 1Y resistance",
    relative_volume: "Volume is at least 1.5× its 20D average",
    above_ma30: "Price is above MA30",
    rising_ma30: "MA30 is rising",
  };
  const conditionDetail = (key, condition) => {
    if (key === "resistance_breakout") {
      return condition.resistance == null ? "Not available" : `Previous ${fmt(condition.previous_price, 4)} · resistance ${fmt(condition.resistance, 4)} · latest ${fmt(condition.current_price, 4)}`;
    }
    if (key === "relative_volume") {
      return condition.value == null ? "Not available" : `${fmt(condition.value, 2)}× · required ${fmt(condition.minimum, 2)}×`;
    }
    if (key === "above_ma30") {
      return condition.ma30 == null ? "Not available" : `Price ${fmt(condition.current_price, 4)} · MA30 ${fmt(condition.ma30, 4)}`;
    }
    return condition.slope_percent == null ? "Not available" : `Slope ${condition.slope_percent >= 0 ? "+" : ""}${fmt(condition.slope_percent, 3)}%`;
  };
  const conditions = Object.entries(signal.conditions || {}).map(([key, condition]) => {
    const status = condition.met === true ? "met" : condition.met === false ? "unmet" : "unavailable";
    const icon = condition.met === true ? "✓" : condition.met === false ? "×" : "–";
    return `
      <div class="technical-signal-condition ${status}">
        <span class="technical-condition-icon" aria-hidden="true">${icon}</span>
        <span><b>${esc(condition.label || fallbackLabels[key] || key)}</b><small>${esc(conditionDetail(key, condition))}</small></span>
      </div>
    `;
  }).join("");
  const score = Number.isFinite(Number(signal.score_total))
    ? `${Number(signal.score_met || 0)} / ${Number(signal.score_total)} conditions`
    : "Waiting for data";
  frame.className = `technical-signal ${missing ? "missing" : triggered ? "confirmed" : "watch"}`;
  frame.innerHTML = `
    <div class="technical-signal-head">
      <div><span class="technical-signal-kicker">Technical signal</span><h3>${esc(title)}</h3><p>${esc(summary)}</p></div>
      <span class="technical-signal-score">${esc(score)}</span>
    </div>
    <div class="technical-signal-conditions">${conditions}</div>
    <p class="technical-signal-disclaimer">Research indicator · not investment advice</p>
  `;
}

function securityChartPoints() {
  return (state.securityHistory || [])
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
}

function securityChartZoomWindow(pointCount) {
  const full = { start: 0, end: Math.max(0, pointCount - 1), isFull: true };
  if (pointCount <= 1 || !state.securityChartZoom) return full;
  let start = Math.max(0, Math.min(pointCount - 1, Math.floor(Number(state.securityChartZoom.start) || 0)));
  let end = Math.max(start, Math.min(pointCount - 1, Math.floor(Number(state.securityChartZoom.end) || pointCount - 1)));
  const minVisible = Math.min(SECURITY_CHART_MIN_VISIBLE_POINTS, pointCount);
  if (end - start + 1 < minVisible) {
    end = Math.min(pointCount - 1, start + minVisible - 1);
    start = Math.max(0, end - minVisible + 1);
  }
  if (start === 0 && end === pointCount - 1) {
    state.securityChartZoom = null;
    return full;
  }
  state.securityChartZoom = { start, end };
  return { start, end, isFull: false };
}

function focusSecurityChart() {
  $("securityDetailChart")?.querySelector("svg")?.focus({ preventScroll: true });
}

function setSecurityChartZoom(start, end, pointCount = securityChartPoints().length, { focusChart = false } = {}) {
  if (!pointCount) return;
  const minVisible = Math.min(SECURITY_CHART_MIN_VISIBLE_POINTS, pointCount);
  let nextStart = Math.max(0, Math.min(pointCount - 1, Math.round(start)));
  let nextEnd = Math.max(nextStart, Math.min(pointCount - 1, Math.round(end)));
  if (nextEnd - nextStart + 1 < minVisible) {
    const center = (nextStart + nextEnd) / 2;
    nextStart = Math.round(center - (minVisible - 1) / 2);
    nextEnd = nextStart + minVisible - 1;
  }
  if (nextStart < 0) {
    nextEnd -= nextStart;
    nextStart = 0;
  }
  if (nextEnd >= pointCount) {
    nextStart -= nextEnd - pointCount + 1;
    nextEnd = pointCount - 1;
  }
  nextStart = Math.max(0, nextStart);
  state.securityChartZoom = nextStart === 0 && nextEnd === pointCount - 1 ? null : { start: nextStart, end: nextEnd };
  renderSecurityChart();
  if (focusChart) focusSecurityChart();
}

function zoomSecurityChart(factor, anchor = 0.5, { focusChart = false } = {}) {
  const pointCount = securityChartPoints().length;
  if (!pointCount) return;
  const window = securityChartZoomWindow(pointCount);
  const currentSpan = window.end - window.start + 1;
  const minVisible = Math.min(SECURITY_CHART_MIN_VISIBLE_POINTS, pointCount);
  const nextSpan = Math.max(minVisible, Math.min(pointCount, Math.round(currentSpan * factor)));
  const safeAnchor = Math.max(0, Math.min(1, anchor));
  const anchorIndex = window.start + safeAnchor * Math.max(currentSpan - 1, 0);
  const nextStart = Math.round(anchorIndex - safeAnchor * Math.max(nextSpan - 1, 0));
  setSecurityChartZoom(nextStart, nextStart + nextSpan - 1, pointCount, { focusChart });
}

function panSecurityChart(direction, { focusChart = false } = {}) {
  const pointCount = securityChartPoints().length;
  const window = securityChartZoomWindow(pointCount);
  if (!pointCount || window.isFull) return;
  const span = window.end - window.start + 1;
  const shift = Math.max(1, Math.round(span * 0.2)) * direction;
  let start = window.start + shift;
  let end = window.end + shift;
  if (start < 0) {
    end -= start;
    start = 0;
  }
  if (end >= pointCount) {
    start -= end - pointCount + 1;
    end = pointCount - 1;
  }
  setSecurityChartZoom(start, end, pointCount, { focusChart });
}

function resetSecurityChartZoom({ render = true, focusChart = false } = {}) {
  state.securityChartZoom = null;
  if (render) renderSecurityChart();
  if (render && focusChart) focusSecurityChart();
}

function renderSecurityChartZoomControls(allPoints, window) {
  const count = allPoints.length;
  const span = count ? window.end - window.start + 1 : 0;
  const status = $("securityChartZoomStatus");
  if (status) {
    if (!count) status.textContent = state.language === "he" ? "אין נתונים להצגה" : "No data to display";
    else if (window.isFull) status.textContent = state.language === "he" ? `כל הטווח · ${count} נקודות` : `Full range · ${count} points`;
    else status.textContent = `${formatDate(allPoints[window.start].date)} – ${formatDate(allPoints[window.end].date)} · ${span} / ${count} ${state.language === "he" ? "נקודות" : "points"}`;
  }
  document.querySelectorAll("[data-security-chart-zoom]").forEach((button) => {
    const action = button.dataset.securityChartZoom;
    button.disabled = !count
      || (action === "in" && span <= Math.min(SECURITY_CHART_MIN_VISIBLE_POINTS, count))
      || (["out", "reset"].includes(action) && window.isFull)
      || (action === "earlier" && (window.isFull || window.start === 0))
      || (action === "later" && (window.isFull || window.end === count - 1));
  });
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
  const allPoints = securityChartPoints();
  const zoomWindow = securityChartZoomWindow(allPoints.length);
  renderSecurityChartZoomControls(allPoints, zoomWindow);
  const points = allPoints.slice(zoomWindow.start, zoomWindow.end + 1);
  if (!allPoints.length) {
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
  const maSeries = Object.fromEntries(selectedMaWindows.map((window) => [window, movingAverageSeries(allPoints, Number(window))
    .filter((point) => point.index >= zoomWindow.start && point.index <= zoomWindow.end)
    .map((point) => ({ ...point, index: point.index - zoomWindow.start }))]));
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
    <svg viewBox="0 0 ${width} ${height}" role="img" tabindex="0" aria-label="Interactive security price history. Drag horizontally to zoom.">
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
      <rect data-security-zoom-selection x="${padLeft}" y="${padTop}" width="0" height="${height - padTop - padBottom}" rx="3" fill="rgba(33,167,255,0.18)" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="5 4" pointer-events="none" hidden />
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
      <div class="sub ${cls}">${points.length}${zoomWindow.isFull ? "" : ` of ${allPoints.length}`} price points · ${esc(volumeText)}</div>
    </div>
  `;
  attachSecurityChartHover(frame, points, { width, height, padLeft, padRight, padTop, padBottom, plotWidth, plotHeight, min, max });
  attachSecurityChartZoom(frame, allPoints, zoomWindow, { width, height, padLeft, padRight, padTop, padBottom, plotWidth });
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

function attachSecurityChartZoom(frame, allPoints, zoomWindow, dims) {
  const svg = frame.querySelector("svg");
  const hitbox = frame.querySelector("[data-security-chart-hitbox]");
  const selection = frame.querySelector("[data-security-zoom-selection]");
  if (!svg || !hitbox || !selection || allPoints.length < 2) return;
  const pointers = new Map();
  let drag = null;
  let pinch = null;
  const svgPoint = (event) => {
    const rect = svg.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / Math.max(rect.width, 1)) * dims.width,
      y: ((event.clientY - rect.top) / Math.max(rect.height, 1)) * dims.height,
    };
  };
  const clampedX = (value) => Math.max(dims.padLeft, Math.min(dims.padLeft + dims.plotWidth, value));
  const ratioForX = (value) => Math.max(0, Math.min(1, (clampedX(value) - dims.padLeft) / dims.plotWidth));
  const distance = (first, second) => Math.hypot(second.x - first.x, second.y - first.y);
  const hideSelection = () => {
    selection.setAttribute("hidden", "");
    selection.setAttribute("width", "0");
  };
  const updateSelection = (fromX, toX) => {
    const start = clampedX(Math.min(fromX, toX));
    const end = clampedX(Math.max(fromX, toX));
    selection.setAttribute("x", start.toFixed(1));
    selection.setAttribute("width", Math.max(0, end - start).toFixed(1));
    selection.removeAttribute("hidden");
  };
  hitbox.addEventListener("pointerdown", (event) => {
    const point = svgPoint(event);
    pointers.set(event.pointerId, point);
    hitbox.setPointerCapture?.(event.pointerId);
    svg.focus({ preventScroll: true });
    if (pointers.size === 1) {
      drag = { pointerId: event.pointerId, start: point, current: point };
      pinch = null;
    } else if (pointers.size === 2) {
      const [first, second] = [...pointers.values()];
      pinch = {
        startDistance: Math.max(distance(first, second), 1),
        currentDistance: Math.max(distance(first, second), 1),
        anchor: ratioForX((first.x + second.x) / 2),
      };
      drag = null;
      hideSelection();
      event.preventDefault();
    }
  });
  hitbox.addEventListener("pointermove", (event) => {
    if (!pointers.has(event.pointerId)) return;
    const point = svgPoint(event);
    pointers.set(event.pointerId, point);
    if (pinch && pointers.size >= 2) {
      const [first, second] = [...pointers.values()];
      pinch.currentDistance = Math.max(distance(first, second), 1);
      event.preventDefault();
      return;
    }
    if (!drag || drag.pointerId !== event.pointerId) return;
    drag.current = point;
    const dx = point.x - drag.start.x;
    const dy = point.y - drag.start.y;
    if (Math.abs(dx) >= 5 && Math.abs(dx) >= Math.abs(dy)) {
      updateSelection(drag.start.x, point.x);
      event.preventDefault();
    }
  });
  const finishPointer = (event, cancelled = false) => {
    if (!pointers.has(event.pointerId)) return;
    const point = svgPoint(event);
    pointers.set(event.pointerId, point);
    if (!cancelled && pinch && pointers.size >= 2) {
      const factor = Math.max(0.25, Math.min(4, pinch.startDistance / Math.max(pinch.currentDistance, 1)));
      const anchor = pinch.anchor;
      pointers.clear();
      pinch = null;
      drag = null;
      hideSelection();
      if (Math.abs(factor - 1) >= 0.04) zoomSecurityChart(factor, anchor, { focusChart: true });
      return;
    }
    if (!cancelled && drag?.pointerId === event.pointerId) {
      const dx = point.x - drag.start.x;
      const dy = point.y - drag.start.y;
      if (Math.abs(dx) >= 18 && Math.abs(dx) >= Math.abs(dy)) {
        const visibleSpan = zoomWindow.end - zoomWindow.start;
        const startRatio = ratioForX(Math.min(drag.start.x, point.x));
        const endRatio = ratioForX(Math.max(drag.start.x, point.x));
        const start = zoomWindow.start + Math.round(startRatio * visibleSpan);
        const end = zoomWindow.start + Math.round(endRatio * visibleSpan);
        pointers.clear();
        drag = null;
        hideSelection();
        setSecurityChartZoom(start, end, allPoints.length, { focusChart: true });
        return;
      }
    }
    pointers.delete(event.pointerId);
    drag = null;
    pinch = null;
    hideSelection();
  };
  hitbox.addEventListener("pointerup", (event) => finishPointer(event));
  hitbox.addEventListener("pointercancel", (event) => finishPointer(event, true));
  svg.addEventListener("wheel", (event) => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    const anchor = ratioForX(svgPoint(event).x);
    zoomSecurityChart(event.deltaY > 0 ? 1.35 : 0.72, anchor, { focusChart: true });
  }, { passive: false });
  svg.addEventListener("keydown", (event) => {
    if (["+", "="].includes(event.key)) zoomSecurityChart(0.72, 0.5, { focusChart: true });
    else if (["-", "_"].includes(event.key)) zoomSecurityChart(1.35, 0.5, { focusChart: true });
    else if (event.key === "ArrowLeft") panSecurityChart(-1, { focusChart: true });
    else if (event.key === "ArrowRight") panSecurityChart(1, { focusChart: true });
    else if (["Escape", "0", "Home"].includes(event.key)) resetSecurityChartZoom({ focusChart: true });
    else return;
    event.preventDefault();
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
  setCurrencyOptions("employeeWizardCurrency", SUPPORTED_MANAGEMENT_CURRENCIES);
  $("employeeWizardCurrency").value = SUPPORTED_MANAGEMENT_CURRENCIES.includes(match.currency) ? match.currency : "USD";
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
  setCurrencyOptions("employeeWizardCurrency", SUPPORTED_MANAGEMENT_CURRENCIES);
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
  if (!SUPPORTED_MANAGEMENT_CURRENCIES.includes(valueOf("employeeWizardCurrency"))) {
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
  setCurrencyOptions("employeeWizardCurrency", SUPPORTED_MANAGEMENT_CURRENCIES);
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
  setCurrencyOptions("manualSecurityCurrency", SUPPORTED_MANAGEMENT_CURRENCIES);
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
  list.innerHTML = visibleSecurities.length ? visibleSecurities.map((item) => {
    const attachmentRows = manualSecurityAttachmentRows(item);
    const removalDisabled = item.can_delete === false || attachmentRows.length > 0;
    const removalHelp = removalDisabled ? `
      <details class="row-action-help security-delete-help" style="--attachment-rows:${attachmentRows.length}">
        <summary aria-label="${esc(optionLabel("Why instrument removal is disabled"))}" title="${esc(optionLabel("Why instrument removal is disabled"))}">i</summary>
        <div class="row-action-help-popover" role="note">
          <strong>${esc(optionLabel("Cannot remove this instrument while data is attached."))}</strong>
          <span>${esc(optionLabel("Attached to this instrument"))}</span>
          <ul>${attachmentRows.map(([count, label]) => `<li><span>${esc(optionLabel(label))}</span><b>${esc(fmt(count, 0))}</b></li>`).join("")}</ul>
        </div>
      </details>` : "";
    return `
      <div class="stack-item management-item security-management-item">
        <div class="security-management-main">
          <b>${esc(item.instrument_type === "EMPLOYEE_STOCK_OPTION" ? (item.company_name || item.name) : `${item.symbol}${item.secondary_symbol ? ` · ${item.secondary_symbol}` : ""}`)}</b>
          <span>${esc(item.name || item.symbol)} · ${esc(optionLabel(item.instrument_type))} · ${item.instrument_type === "EMPLOYEE_STOCK_OPTION" ? `<span class="badge ${item.listing_status === "PUBLIC" ? "ok" : "warn"}">${esc(item.listing_status === "PUBLIC" ? `${item.public_symbol} · ${item.public_market}` : "Private Company")}</span>` : `${esc(item.stock_market)} · ${esc(currencyDisplayLabel(item.currency))}`}</span>
          <div class="sub">${esc(optionLabel(item.asset_class))}${item.grant_id ? ` · Grant ID ${esc(item.grant_id)}` : ""}${item.grant_date ? ` · Grant Date ${esc(formatDate(item.grant_date))}` : ""}${item.vesting_start_date ? ` · Vesting Start ${esc(formatDate(item.vesting_start_date))}` : ""}${item.underlying_symbol ? ` · Underlying ${esc(item.underlying_symbol)}` : ""}${item.option_type && item.instrument_type !== "EMPLOYEE_STOCK_OPTION" ? ` · ${esc(item.option_type)} option` : ""}${item.expiration_date ? ` · Exp ${esc(formatDate(item.expiration_date))}` : ""}${item.strike_price ? ` · Strike ${fmt(item.strike_price, 4)}` : ""}${item.instrument_type !== "EMPLOYEE_STOCK_OPTION" && item.contract_multiplier ? ` · Multiplier ${fmt(item.contract_multiplier, 4)}` : ""}${item.manual_share_value ? ` · Valuation ${money(item.manual_share_value, item.currency, 4)} on ${esc(formatDate(item.valuation_date))}` : ""}${item.comments ? ` · ${esc(item.comments)}` : ""}</div>
        </div>
        <div class="row-actions security-management-actions">
          <button class="secondary compact-button" type="button" data-use-manual-security="${esc(item.id)}">${employeeOptionsWorkflowActive() ? "Add to account" : "Use"}</button>
          <button class="secondary compact-button" type="button" data-edit-manual-security="${esc(item.id)}">Edit</button>
          ${item.instrument_type === "EMPLOYEE_STOCK_OPTION" && item.listing_status !== "PUBLIC" ? `<button class="secondary compact-button" type="button" data-link-employee-listing="${esc(item.id)}">Link public listing</button>` : ""}
          ${item.instrument_type === "EMPLOYEE_STOCK_OPTION" ? `<button class="secondary compact-button" type="button" data-exercise-employee-option="${esc(item.id)}">Exercise</button>` : ""}
          <button class="secondary compact-button" type="button" data-delete-manual-security="${esc(item.id)}"${removalDisabled ? " disabled" : ""}>Remove</button>
          ${removalHelp}
        </div>
      </div>`;
  }).join("") : `<div class="empty">${employeeOptionsWorkflowActive() ? "No employee option grants yet. Enter your first grant above." : "No defined instruments yet"}</div>`;
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
  $("manualSecurityCurrency").value = SUPPORTED_MANAGEMENT_CURRENCIES.includes(matchCurrency)
    ? matchCurrency
    : preferredCurrencyForLocation(valueOf("manualSecurityLocation")) || "USD";
  $("manualShareValue").value = Number(match.manual_share_value || 0) > 0 ? match.manual_share_value : "";
  setDateField("manualValuationDate", match.valuation_date || "");
  setDateField("manualRestrictionEndDate", match.restriction_end_date || "");
  toggleManualInstrumentFields();
  $("manualSecurityStatus").textContent = `Using existing issuer details for ${match.company_name}. This grant remains separate.`;
}

function manualSecurityAttachmentRows(item) {
  return [
    ["transactions", "Security transactions"],
    ["price_history", "Saved price history"],
    ["events", "Security events"],
    ["equity_transitions", "Equity transitions"],
  ].map(([key, label]) => [Number(item.attachment_counts?.[key] || 0), label]).filter(([count]) => count > 0);
}

function clearManualSecurityForm() {
  state.editingManualSecurityId = "";
  [
    "manualSecuritySymbol", "manualSecondarySymbol", "manualSecurityName", "manualSecurityMarket", "manualCompanyName", "manualGrantId",
    "manualGrantDate", "manualVestingStartDate", "manualUnderlyingSymbol", "manualExpirationDate", "manualStrikePrice",
    "manualContractMultiplier", "manualTaxScheme", "manualShareValue", "manualValuationDate",
    "manualRestrictionEndDate", "manualSecurityComments",
  ].forEach((id) => { $(id).value = ""; });
  $("manualEarlyExercise").checked = false;
  $("manualIssuerStatus").value = "PRIVATE";
  $("manualInstrumentType").value = "STOCK";
  $("manualSecuritySymbol").disabled = false;
  $("manualSecurityMarket").disabled = false;
  $("saveManualSecurity").textContent = "Save instrument";
  $("cancelManualSecurityEdit").hidden = true;
  toggleManualInstrumentFields();
}

function editManualSecurity(securityId) {
  const item = instrumentById(securityId);
  if (!item) return;
  if (item.instrument_type === "EMPLOYEE_STOCK_OPTION") {
    setSecuritiesWorkflow("employee-options");
    editEmployeeOptionGrant(securityId);
    return;
  }
  state.editingManualSecurityId = item.id;
  $("manualSecuritySymbol").value = item.symbol || "";
  $("manualSecondarySymbol").value = item.secondary_symbol || "";
  $("manualSecurityName").value = item.name || "";
  $("manualSecurityMarket").value = item.stock_market || "";
  $("manualInstrumentType").value = item.instrument_type || "STOCK";
  $("manualSecurityCurrency").value = item.currency || "USD";
  setCompanyLocationOptions(item.location || "USA");
  $("manualUnderlyingSymbol").value = item.underlying_symbol || "";
  $("manualOptionType").value = item.option_type || "CALL";
  setDateField("manualExpirationDate", item.expiration_date || "");
  $("manualStrikePrice").value = Number(item.strike_price || 0) || "";
  $("manualContractMultiplier").value = Number(item.contract_multiplier || 0) || "";
  $("manualSecurityComments").value = item.comments || "";
  toggleManualInstrumentFields();
  const identityLocked = item.can_delete === false;
  $("manualSecuritySymbol").disabled = identityLocked;
  $("manualSecurityMarket").disabled = identityLocked;
  $("saveManualSecurity").textContent = "Update instrument";
  $("cancelManualSecurityEdit").hidden = false;
  $("manualSecurityStatus").textContent = identityLocked
    ? "Editing instrument. Its symbol and stock market stay locked while attached data exists."
    : "Editing instrument.";
  requestAnimationFrame(() => {
    $("instrumentDefinitionSection")?.scrollIntoView({ block: "start", behavior: "smooth" });
    $("manualSecurityName")?.focus({ preventScroll: true });
  });
}

async function saveManualSecurity() {
  const editing = Boolean(state.editingManualSecurityId);
  const isEmployeeOption = valueOf("manualInstrumentType") === "EMPLOYEE_STOCK_OPTION";
  const listingStatus = valueOf("manualIssuerStatus") || "PRIVATE";
  const currency = valueOf("manualSecurityCurrency") || "USD";
  const primarySymbol = isEmployeeOption && listingStatus === "PRIVATE" ? "" : cleanSecuritySymbol(valueOf("manualSecuritySymbol"));
  const secondarySymbol = isEmployeeOption ? "" : cleanSecuritySymbol(valueOf("manualSecondarySymbol"));
  if (!SUPPORTED_MANAGEMENT_CURRENCIES.includes(currency)) {
    $("manualSecurityStatus").textContent = "Security currency must be ILS, USD, or EUR.";
    $("manualSecurityCurrency").focus();
    return;
  }
  if (secondarySymbol && secondarySymbol === primarySymbol) {
    $("manualSecurityStatus").textContent = "Secondary symbol must be different from the primary symbol.";
    $("manualSecondarySymbol").focus();
    return;
  }
  const payload = {
    id: state.editingManualSecurityId || undefined,
    symbol: primarySymbol,
    secondary_symbol: secondarySymbol,
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
    : `${editing ? "Instrument updated" : "Instrument saved"}: ${saved.company_name || saved.symbol}${saved.grant_id ? ` · ${saved.grant_id}` : ""}`;
  clearManualSecurityForm();
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
      <b>${esc(tx.action)} ${esc(tx.instrument_type === "EMPLOYEE_STOCK_OPTION" ? (tx.company_name || tx.security_name || "Employee option") : `${tx.symbol}${tx.secondary_symbol ? ` · ${tx.secondary_symbol}` : ""}`)}</b>
      <span>${fmt(tx.quantity, 4)} @ ${fmt(tx.price_input, 4)} (${esc(currencyDisplayLabel(tx.currency))} ${fmt(tx.price, 4)})${tx.instrument_type ? ` · ${esc(tx.instrument_type)}` : ""}</span>
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
  state.eventDividendSettings = data.dividends || {};
  state.alarmsLoadFailed = false;
  renderEvents();
  renderAlarms();
  focusEventRow();
}

function renderEvents() {
  const settings = state.eventDividendSettings || {};
  const status = $("eventsStatus");
  if (status) {
    status.textContent = `${t("Dividend scan starts")} ${formatDate(settings.start_date || "")} · ${t("Tax")} ${pct(Number(settings.tax_rate || 0) * 100)} · ${t("Next scan")}: ${settings.next_run ? formatDate(String(settings.next_run).slice(0, 10)) : t("Not scheduled")}`;
  }
  const list = $("eventsList");
  if (!list) return;
  list.innerHTML = state.localEvents.length ? state.localEvents.map((event) => {
    const currency = event.currency || state.baseCurrency;
    const details = event.details || {};
    const statusLabel = { processed: "Payment recorded", pending: "Pending", failed: "Failed", skipped: "Skipped" }[event.status] || "Status unavailable";
    const account = event.account_label && event.account_label !== event.account_db_id ? event.account_label : t("Account unavailable");
    const facts = [account];
    if (Number(details.shares) > 0) facts.push(`${t("Shares")}: ${fmt(Number(details.shares), 3)}`);
    if (Number(details.gross_per_share) > 0) facts.push(`${t("Dividend per share")}: ${money(Number(details.gross_per_share), currency, 4)}`);
    facts.push(`${t("Gross")}: ${money(event.gross_amount || 0, currency, 2)}`, `${t("Tax")}: ${money(event.tax_amount || 0, currency, 2)}`);
    return `
    <div class="stack-item management-item event-item ${state.focusedEventId === event.id ? "focused-event" : ""}" data-event-id="${esc(event.id)}">
      <b>${esc(t(event.type === "DIVIDEND" ? "Dividend" : "Event"))} ${esc(event.symbol || "")}</b>
      <span>${esc(formatDate(event.event_date))} · ${esc(t(statusLabel))} · ${t("Net")}: ${money(event.net_amount || 0, currency, 2)}</span>
      ${event.transaction_id ? `<button class="secondary compact-button" type="button" data-edit-security="${esc(event.transaction_id)}">${t("Edit transaction")}</button>` : ""}
      <div class="sub">${esc(facts.join(" · "))}</div>
    </div>
  `;
  }).join("") : `<div class="empty">${t("No events yet")}</div>`;
}

async function runDividendEvents() {
  $("eventsStatus").textContent = t("Scanning dividends");
  const result = await api("/api/local/events/dividends/run", { method: "POST", body: "{}" });
  state.localEvents = result.items || [];
  $("eventsStatus").textContent = t(`Checked ${result.checked} holdings · ${result.processed} processed · ${result.pending} pending · ${result.skipped} skipped`);
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

function alarmText(template, values = {}) {
  return t(template).replace(/\{(\w+)\}/gu, (placeholder, key) => Object.hasOwn(values, key) ? String(values[key]) : placeholder);
}

function alarmValue(value) {
  return `\u2066${value}\u2069`;
}

function alarmDueText(days, date) {
  if (days === 0) return t("today");
  if (days === 1) return t("in 1 day");
  if (days > 1) return alarmText("in {days} days", { days: fmt(days, 0) });
  return alarmText("on {date}", { date: alarmValue(formatDate(date)) });
}

function dividendAlarmMessage(event) {
  const details = event.details || {};
  const currency = event.currency || state.baseCurrency;
  const perShare = Number(details.gross_per_share || 0);
  const shares = Number(details.shares || 0);
  const perShareText = perShare > 0 ? alarmText("{amount} per share", { amount: alarmValue(money(perShare, currency, 4)) }) : t("per-share amount not available");
  const shareText = shares > 0 ? alarmText(shares === 1 ? "{count} share" : "{count} shares", { count: alarmValue(fmt(shares, 3)) }) : t("shares not available");
  const values = {
    symbol: alarmValue(event.symbol),
    perShare: perShareText,
    shares: shareText,
    net: alarmValue(money(event.net_amount || 0, currency, 2)),
    gross: alarmValue(money(event.gross_amount || 0, currency, 2)),
    tax: alarmValue(money(event.tax_amount || 0, currency, 2)),
    date: alarmValue(formatDate(event.event_date)),
  };
  const days = eventDaysFromToday(event.event_date);
  if (event.status === "pending") {
    values.due = alarmDueText(days, event.event_date);
    return {
      tone: "future",
      title: alarmText("{symbol} dividend is expected {due}", values),
      body: alarmText("Expected {perShare}. Estimated net total {net} after {tax} tax for {shares}.", values),
      meta: alarmText("Payment date {date} · Gross {gross}", values),
    };
  }
  return {
    tone: "paid",
    title: alarmText("{symbol} dividend was paid", values),
    body: alarmText("Added {net} to cash from {perShare} for {shares}.", values),
    meta: alarmText("Paid {date} · Gross {gross} · Tax {tax}", values),
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
      const singular = Number(lot.quantity) === 1;
      const values = { symbol: alarmValue(lot.symbol), quantity: alarmValue(fmt(lot.quantity, 2)), due: alarmDueText(days, lot.vestDate), date: alarmValue(formatDate(lot.vestDate)), days: leadDays };
      const title = lot.kind === "rsu" ? "{symbol} RSU vesting {due}" : "{symbol} stock option vesting {due}";
      const body = lot.kind === "rsu"
        ? singular ? "{quantity} RSU is scheduled to vest." : "{quantity} RSUs are scheduled to vest."
        : singular ? "{quantity} stock option is scheduled to vest." : "{quantity} stock options are scheduled to vest.";
      return {
        kind: "vesting",
        tone: "vesting",
        transactionId: lot.transactionId,
        trancheSequence: lot.trancheSequence,
        title: alarmText(title, values),
        body: alarmText(body, values),
        meta: alarmText("Vest Date: {date} · {days}-day notice window", values),
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
  state.clearedAlarmCount = alarms.length;
  saveAlarmDismissals();
  renderAlarms();
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
    status.textContent = state.alarmsLoadFailed ? t("Could not update alarms. Reopen Alerts to retry.") : alarms.length ? [
      alarmText(vesting.length === 1 ? "{count} upcoming vesting alarm" : "{count} upcoming vesting alarms", { count: vesting.length }),
      alarmText(future === 1 ? "{count} future dividend" : "{count} future dividends", { count: future }),
      alarmText(paid === 1 ? "{count} paid dividend" : "{count} paid dividends", { count: paid }),
    ].join(" · ") : state.clearedAlarmCount
      ? alarmText(state.clearedAlarmCount === 1 ? "{count} alarm cleared. New alarms will still appear." : "{count} alarms cleared. New alarms will still appear.", { count: state.clearedAlarmCount })
      : t("No vesting or dividend alarms in the current notice window.");
  }
  if ($("vestingAlertDays")) $("vestingAlertDays").value = String(state.vestingAlertDays);
  if ($("alarmSettingsStatus")) {
    const notice = state.vestingNoticeSaved
      ? state.vestingAlertDays === 1 ? "Vesting alerts will appear {days} day before vesting." : "Vesting alerts will appear {days} days before vesting."
      : state.vestingAlertDays === 1 ? "Showing vest dates up to {days} day in advance." : "Showing vest dates up to {days} days in advance.";
    $("alarmSettingsStatus").textContent = alarmText(notice, { days: state.vestingAlertDays });
  }
  const list = $("alarmsList");
  if (!list) return;
  list.innerHTML = alarms.length ? alarms.map((alarm) => `
    <button class="alarm-item ${esc(alarm.tone)}" type="button" ${alarm.kind === "vesting" ? `data-open-vesting-alarm="${esc(alarm.transactionId)}"` : `data-open-dividend-alarm="${esc(alarm.event.id)}"`}>
      <span class="alarm-heading">
        <b>${esc(alarm.title)}</b>
        <span class="alarm-kind">${esc(t(alarm.kind === "vesting" ? "Upcoming vesting" : alarm.tone === "future" ? "Future dividend" : "Dividend paid"))}</span>
      </span>
      <span class="alarm-details">
        <span class="alarm-body">${esc(alarm.body)}</span>
        <small class="alarm-meta">${esc(alarm.meta)}</small>
      </span>
    </button>
  `).join("") : `<div class="empty">${esc(t("No vesting or dividend alarms"))}</div>`;
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
      <span>${esc(formatDate(price.price_date))} · ${fmt(price.price_input, 4)} (${esc(currencyDisplayLabel(price.currency))} ${fmt(price.price, 4)})</span>
      <button class="secondary compact-button" type="button" data-delete-price="${esc(price.id)}">Remove</button>
      <div class="sub">${esc(price.stock_market)} · ${esc(price.asset_class)} · ${esc(countryDisplayLabel(price.location))} · ${esc(price.comments || "")}</div>
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

// Report totals must never silently treat unlike currencies as equivalent.
function reportAmount(value, currency, target = state.baseCurrency) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return null;
  if (!currency || !target) return null;
  if (currency === target) return Number(value);
  if (Number(value) === 0) return 0;
  const direct = Number(state.fxRates[`${currency}/${target}`]);
  const reverse = Number(state.fxRates[`${target}/${currency}`]);
  if (Number.isFinite(direct) && direct > 0) return Number(value) * direct;
  if (Number.isFinite(reverse) && reverse > 0) return Number(value) / reverse;
  if (currency !== state.baseCurrency && target !== state.baseCurrency) {
    const baseValue = reportAmount(value, currency, state.baseCurrency);
    return baseValue === null ? null : reportAmount(baseValue, state.baseCurrency, target);
  }
  return null;
}

function reportSum(values) {
  return values.some((value) => value === null) ? null : sum(values);
}

function reportMoney(value, currency = state.baseCurrency) {
  return value === null ? t("Not available") : money(value, currency, 0);
}

function reportAccountAmounts(account, currency = state.baseCurrency) {
  const cash = reportAmount(account.cash, account.currency, currency);
  const securities = reportSum((account.holdings || []).map((holding) => reportAmount(holding.market_value, holding.currency || account.currency, currency)));
  const profit = reportSum((account.holdings || []).map((holding) => reportAmount(holding.profit, holding.currency || account.currency, currency)));
  return { cash, securities, profit, value: reportSum([cash, securities]) };
}

const TRADE_HISTORY_ISSUES = Object.freeze({
  imported_position_date_unknown: "Purchase date unavailable — imported position snapshot",
  opening_date_unknown: "Opening date is unavailable",
  unsupported_instrument: "P/L is unavailable for this instrument type",
  trade_date_unknown: "A transaction date is unavailable",
  zero_duration: "Daily and yearly P/L are unavailable for a same-day position",
  valuation_before_as_of: "Valuation uses the saved price date shown in Details",
  missing_valuation: "No suitable saved price is available",
  transfer_without_profit: "A transfer or removal does not establish sale profit",
  incomplete_cost_basis: "The recorded position or cost basis is incomplete",
  ambiguous_cash_allocation: "Some income or fees cannot be assigned to this holding period",
  invalid_transaction: "An invalid transaction needs review",
  unsupported_action: "An unsupported transaction action needs review",
  unallocated_cash_entry: "Income or fees recorded while no position was open remain unallocated",
  transfer_without_position: "A removal has no recorded open position",
  excess_closing_quantity: "A closing quantity exceeds the recorded position",
});

function tradeHistoryIssueText(issue) {
  return t(TRADE_HISTORY_ISSUES[issue] || "Some history data is incomplete");
}

function tradeHistoryAmount(value, currency) {
  return value === null || value === undefined || !Number.isFinite(Number(value))
    ? t("Not available") : money(value, currency, 2);
}

function tradeHistoryActionLabel(action) {
  const labels = { BUY: "Buy", SELL: "Sell", ADD: "Add", REMOVE: "Remove", SHORT: "Short", DIVIDEND: "Dividend", INTEREST: "Interest", FEE: "Fee" };
  return t(labels[action] || "Other activity");
}

function tradeHistorySourceLabel(source) {
  const key = String(source || "").toLowerCase();
  if (key.endsWith("_import")) return t("Imported");
  if (key === "manual") return t("Manual");
  if (key === "dividend_scan") return t("Automatic dividend");
  if (key === "employee_option_exercise") return t("Option exercise");
  return t("Recorded locally");
}

function positionAccountMatchesScope(account) {
  const type = valueOf("positionAccountType");
  const personId = valueOf("positionPerson");
  if (type && account.type !== type) return false;
  if (!personId) return true;
  const member = (state.positionsPeople || []).find((person) => person.id === personId);
  const normalize = (name) => String(name || "").trim().replace(/\s+/g, " ").toLocaleLowerCase();
  const name = member ? normalize(memberLabel(member)) : "";
  return (account.persons || []).some((person) => String(person.member_id || "") === personId
    || (!person.member_id && name && normalize(person.name) === name));
}

function positionAccountMatchesFilters(accountId) {
  const selected = valueOf("positionAccount");
  if (selected && accountId !== selected) return false;
  if (!valueOf("positionAccountType") && !valueOf("positionPerson")) return true;
  const account = (state.positionsAccounts || []).find((row) => row.id === accountId);
  return Boolean(account && positionAccountMatchesScope(account));
}

function refreshPositionAccountSelect() {
  const select = $("positionAccount");
  const current = select.value;
  select.innerHTML = `<option value="">${esc(t("All matching accounts"))}</option>`
    + (state.positionsAccounts || []).filter(positionAccountMatchesScope).map(accountOptionHtml).join("");
  if ([...select.options].some((option) => option.value === current)) select.value = current;
  select.title = select.selectedOptions?.[0]?.textContent || "";
}

function positionStockKey(row) {
  const asset = ["STOCK", "RSU"].includes(row.asset_class) ? "EQUITY" : row.asset_class || "";
  return JSON.stringify([row.symbol || "", row.stock_market || "", row.currency || "", asset, row.security_id || ""]);
}

function refreshPositionStockSelect() {
  const select = $("positionStock"), current = select.value;
  const securities = new Map();
  (state.tradeHistory?.items || []).filter((row) => positionAccountMatchesFilters(row.account_id)).forEach((row) => {
    const key = positionStockKey(row);
    if (!securities.has(key)) securities.set(key, row);
  });
  const rows = [...securities.entries()].sort((a, b) => String(a[1].symbol).localeCompare(String(b[1].symbol), locale()) || a[0].localeCompare(b[0]));
  const labels = rows.map(([, row]) => [row.symbol, row.name !== row.symbol ? row.name : "", row.stock_market, currencyDisplayLabel(row.currency), optionLabel(row.asset_class)].filter(Boolean).join(" · "));
  select.innerHTML = `<option value="">${esc(t("All securities"))}</option>` + rows.map(([key, row], index) => {
    const duplicate = labels.indexOf(labels[index]) !== labels.lastIndexOf(labels[index]);
    const label = labels[index] + (duplicate ? ` · ${t("Instrument")}: ${row.security_id || t("Not available")}` : "");
    return `<option value="${esc(key)}">${esc(label)}</option>`;
  }).join("");
  if ([...select.options].some((option) => option.value === current)) select.value = current;
  select.title = select.selectedOptions?.[0]?.textContent || "";
}

function refreshPositionFilterOptions() {
  const populate = (id, options, all) => {
    const select = $(id), current = select.value;
    select.innerHTML = `<option value="">${esc(t(all))}</option>` + options.map(([value, label]) => `<option value="${esc(value)}">${esc(label)}</option>`).join("");
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  };
  populate("positionPerson", (state.positionsPeople || []).map((person) => [person.id, memberLabel(person)]), "All people");
  const types = [...new Set(["Investment", ...(state.positionsAccounts || []).map((account) => account.type)])].filter(Boolean);
  populate("positionAccountType", types.map((type) => [type, optionLabel(type)]), "All account categories");
  refreshPositionAccountSelect();
  refreshPositionStockSelect();
}

function positionMonetarySort(key = valueOf("positionSort")) {
  return ["total_profit", "realized_profit", "unrealized_profit", "profit_per_day", "profit_per_year"].includes(key);
}

function filteredTradeHistoryItems() {
  const status = valueOf("tradeHistoryPositionStatus") || "all";
  const query = valueOf("tradeHistorySearch").toLocaleLowerCase();
  const stock = valueOf("positionStock");
  const key = valueOf("positionSort") || "opened_date";
  const direction = valueOf("positionSortDirection") === "asc" ? 1 : -1;
  const numeric = ["duration_days", "total_profit", "realized_profit", "unrealized_profit", "profit_per_day", "profit_per_year"].includes(key);
  const rows = (state.tradeHistory?.items || []).filter((item) => (
    positionAccountMatchesFilters(item.account_id)
    && (!stock || positionStockKey(item) === stock)
    && (status === "all" || item.status === status)
    && (!query || [item.symbol, item.name, item.account_label, item.stock_market,
      formatDate(item.opened_date || ""), formatDate(item.closed_date || "")]
      .some((part) => String(part || "").toLocaleLowerCase().includes(query)))
  ));
  return rows.sort((a, b) => {
    const valid = (value) => value !== null && value !== undefined && value !== "" && (!numeric || Number.isFinite(Number(value)));
    const sortValue = (row) => key === "status" ? t(row.status === "closed" ? "Closed position" : "Open position")
      : key === "currency" ? currencyDisplayLabel(row.currency) : row[key];
    const av = sortValue(a), bv = sortValue(b);
    if (valid(av) !== valid(bv)) return valid(av) ? -1 : 1;
    if (positionMonetarySort(key) && a.currency !== b.currency) return String(a.currency || "").localeCompare(String(b.currency || ""));
    const order = !valid(av) ? 0 : numeric ? Number(av) - Number(bv) : String(av).localeCompare(String(bv), locale());
    return order * direction || String(a.symbol || "").localeCompare(String(b.symbol || ""), locale()) || String(a.id || "").localeCompare(String(b.id || ""));
  });
}

function updatePositionFilters({ scopeChanged = false, accountChanged = false } = {}) {
  if (scopeChanged) refreshPositionAccountSelect();
  if (scopeChanged || accountChanged) refreshPositionStockSelect();
  state.tradeHistoryPage = 1;
  renderTradeHistory();
  $("tradeHistoryTable").scrollTop = 0;
}

function resetPositionFilters() {
  $("positionPerson").value = "";
  $("positionAccountType").value = "Investment";
  $("positionAccount").value = "";
  $("positionStock").value = "";
  $("tradeHistoryPositionStatus").value = "all";
  $("tradeHistorySearch").value = "";
  $("positionSort").value = "opened_date";
  $("positionSortDirection").value = "desc";
  updatePositionFilters({ scopeChanged: true });
}

function setPositionColumnSort(key) {
  const select = $("positionSort");
  if (![...select.options].some((option) => option.value === key)) return;
  $("positionSortDirection").value = select.value === key
    ? (valueOf("positionSortDirection") === "asc" ? "desc" : "asc")
    : (["symbol", "name", "account_label", "currency", "stock_market", "status"].includes(key) ? "asc" : "desc");
  select.value = key;
  updatePositionFilters();
  $("tradeHistoryTable").querySelector(`[data-position-sort="${key}"]`)?.focus({ preventScroll: true });
}

async function loadTradeHistory() {
  const version = (state.tradeHistoryRequestVersion || 0) + 1;
  state.tradeHistoryRequestVersion = version;
  state.tradeHistoryLoading = true;
  state.tradeHistoryError = false;
  renderTradeHistory();
  try {
    const [data, accounts, people] = await Promise.all([
      api("/api/local/trade-history"), api("/api/local/accounts"), api("/api/local/family-members"),
    ]);
    if (version !== state.tradeHistoryRequestVersion) return;
    state.tradeHistory = data;
    state.positionsAccounts = accounts.items || [];
    state.positionsPeople = people.items || [];
    refreshPositionFilterOptions();
    state.tradeHistoryPage = 1;
  } catch (_error) {
    if (version !== state.tradeHistoryRequestVersion) return;
    state.tradeHistory = null;
    state.tradeHistoryError = true;
  } finally {
    if (version === state.tradeHistoryRequestVersion) {
      state.tradeHistoryLoading = false;
      renderTradeHistory();
    }
  }
}

function renderTradeHistory() {
  const status = $("tradeHistoryStatus");
  const table = $("tradeHistoryTable");
  const unallocated = $("tradeHistoryUnallocated");
  $("retryTradeHistory").hidden = !state.tradeHistoryError;
  $("exportTradeHistoryCsv").disabled = true;
  $("positionSortNote").hidden = !positionMonetarySort();
  if (state.tradeHistoryLoading) {
    status.textContent = t("Loading recorded trade history…");
    table.innerHTML = "";
    unallocated.innerHTML = "";
    return;
  }
  if (state.tradeHistoryError) {
    status.textContent = t("Could not load trade history. Retry to load this section.");
    table.innerHTML = "";
    unallocated.innerHTML = "";
    return;
  }
  const data = state.tradeHistory;
  if (!data) return;
  const rows = filteredTradeHistoryItems();
  const pageSize = 20;
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  const page = Math.min(Math.max(Number(state.tradeHistoryPage || 1), 1), pages);
  state.tradeHistoryPage = page;
  $("exportTradeHistoryCsv").disabled = !rows.length;
  status.textContent = `${rows.length} ${t("Holding periods")} · ${t("As of")} ${formatDate(data.as_of_date)} · ${t("Saved local prices")}`;
  const headers = ["Security / account", "Position status", "Opened / closed", "Total P/L", "P/L per day", "P/L per year", "Actions"];
  const sortFields = [
    [["symbol", "Security"], ["name", "Security name"], ["account_label", "Account name"], ["currency", "Currency"], ["stock_market", "Market"]],
    [["status", "Position status"]],
    [["opened_date", "Opened"], ["closed_date", "Closed"], ["duration_days", "Days held"]],
    [["total_profit", "Total P/L"], ["realized_profit", "Realized P/L"], ["unrealized_profit", "Unrealized P/L"]],
    [["profit_per_day", "P/L per day"]], [["profit_per_year", "P/L per year"]], [],
  ];
  const sortKey = valueOf("positionSort"), ascending = valueOf("positionSortDirection") === "asc";
  const heading = (header, index) => {
    const fields = sortFields[index], active = fields.some(([key]) => key === sortKey);
    const buttons = fields.map(([key, label]) => {
      const selected = key === sortKey;
      const text = ["symbol", "name", "account_label", "currency", "stock_market", "status"].includes(key);
      const nextDirection = selected ? (ascending ? "Descending" : "Ascending") : text ? "Ascending" : "Descending";
      return `<button class="position-sort-button${selected ? " active" : ""}" type="button" data-position-sort="${key}" aria-pressed="${selected}" aria-label="${esc(`${t("Sort by")} ${t(label)} · ${t(nextDirection)}`)}">${esc(t(label))}<span aria-hidden="true">${selected ? (ascending ? "↑" : "↓") : "↕"}</span></button>`;
    }).join("");
    return `<th scope="col"${active ? ` aria-sort="${ascending ? "ascending" : "descending"}"` : ""}>${fields.length > 1 ? `<span class="position-header-label">${esc(t(header))}</span>` : ""}${buttons ? `<div class="position-header-sorts">${buttons}</div>` : esc(t(header))}</th>`;
  };
  const cell = (label, content, extra = "") => `<td data-label="${esc(t(label))}"${extra}>${content}</td>`;
  table.innerHTML = rows.length ? `<table class="holdings-table compact-report-table trade-history-table"><thead><tr>${headers.map(heading).join("")}</tr></thead><tbody>${rows.slice((page - 1) * pageSize, page * pageSize).map((row) => `<tr>
    ${cell("Security / account", `<b>${esc(row.symbol)}</b>${row.name && row.name !== row.symbol ? `<small>${esc(row.name)}</small>` : ""}<small>${esc(row.account_label)}</small><small>${esc(currencyDisplayLabel(row.currency))} · ${esc(row.stock_market)}</small>`)}
    ${cell("Position status", `<span class="badge ${row.status === "closed" ? "ok" : "partial"}">${esc(t(row.status === "closed" ? "Closed position" : "Open position"))}</span>${row.issues?.length ? `<small title="${esc(row.issues.map(tradeHistoryIssueText).join(" · "))}">${esc(t("Limited data"))} · ${row.issues.length}</small>` : ""}`)}
    ${cell("Opened / closed", `<span>${esc(t("Opened"))}: ${esc(row.opened_date ? formatDate(row.opened_date) : t("Not available"))}</span><small>${esc(t("Closed"))}: ${esc(row.closed_date ? formatDate(row.closed_date) : t(row.status === "open" ? "Still open" : "Not available"))}</small><small>${esc(t("Days held"))}: ${esc(row.duration_days ?? t("Not available"))}</small>`)}
    ${cell("Total P/L", `<b class="${row.total_profit > 0 ? "positive" : row.total_profit < 0 ? "negative" : ""}">${esc(tradeHistoryAmount(row.total_profit, row.currency))}</b><small>${esc(t("Realized P/L"))}: ${esc(tradeHistoryAmount(row.realized_profit, row.currency))}</small><small>${esc(t("Unrealized P/L"))}: ${esc(tradeHistoryAmount(row.unrealized_profit, row.currency))}</small>`)}
    ${["profit_per_day", "profit_per_year"].map((key, index) => cell(headers[index + 4], esc(tradeHistoryAmount(row[key], row.currency)), ` class="${row[key] > 0 ? "positive" : row[key] < 0 ? "negative" : ""}"`)).join("")}
    ${cell("Actions", `<button class="secondary compact-button" type="button" data-trade-history-details="${esc(row.id)}" aria-label="${esc(t("Position history details"))}: ${esc(row.symbol)} · ${esc(row.account_label)}">${esc(t("Details"))}</button>`)}
  </tr>`).join("")}</tbody></table>${pages > 1 ? `<div class="trade-history-pagination"><button type="button" class="secondary compact-button" data-trade-history-page="-1"${page === 1 ? " disabled" : ""}>${esc(t("Previous"))}</button><span>${esc(t("Page"))} ${page} / ${pages}</span><button type="button" class="secondary compact-button" data-trade-history-page="1"${page === pages ? " disabled" : ""}>${esc(t("Next"))}</button></div>` : ""}`
    : `<div class="empty">${esc(t(data.items?.length ? "No positions match these history filters" : "No recorded position history is available"))}${data.items?.length ? `<button class="secondary compact-button" type="button" data-reset-position-filters>${esc(t("Reset filters"))}</button>` : ""}</div>`;
  const query = valueOf("tradeHistorySearch").toLocaleLowerCase();
  const selectedStock = valueOf("positionStock");
  const entries = (data.unallocated_transactions || []).filter((entry) => positionAccountMatchesFilters(entry.account_id) && (!selectedStock || positionStockKey(entry) === selectedStock) && (!query || String(entry.symbol || "").toLocaleLowerCase().includes(query)));
  const reportIssues = [...new Set(entries.flatMap((entry) => entry.issues || []))];
  unallocated.innerHTML = reportIssues.length || entries.length ? `<details class="trade-history-data-note"><summary>${esc(t("History data notes"))}${entries.length ? ` · ${entries.length} ${esc(t("Unallocated activities"))}` : ""}</summary>${reportIssues.map((issue) => `<p class="section-note">${esc(tradeHistoryIssueText(issue))}</p>`).join("")}${entries.map((entry) => `<p class="section-note"><b>${esc(entry.symbol)}</b> · ${esc(entry.trade_date ? formatDate(entry.trade_date) : t("Not available"))} · ${esc(tradeHistoryActionLabel(entry.action))} · ${esc(tradeHistoryAmount(Number.isFinite(entry.quantity) && Number.isFinite(entry.price) ? entry.quantity * entry.price : null, entry.currency))}</p>`).join("")}</details>` : "";
}

function openTradeHistoryDetails(id, trigger) {
  const row = state.tradeHistory?.items?.find((item) => item.id === id);
  if (!row) return;
  state.tradeHistoryDetail = row;
  renderTradeHistoryDetails(row);
  $("positionsModal").inert = true;
  $("positionsModal").setAttribute("aria-hidden", "true");
  openModal("tradeHistoryDetailModal", trigger, { focusId: "tradeHistoryDetailTitle" });
}

function renderTradeHistoryDetails(row) {
  $("tradeHistoryDetailTitle").textContent = `${row.symbol} · ${t("Position history details")}`;
  $("tradeHistoryDetailSubtitle").textContent = [row.account_label, currencyDisplayLabel(row.currency),
    t(row.side === "short" ? "Short position" : "Long position"), t(row.status === "closed" ? "Closed position" : "Open position"),
    `${t("Opened")}: ${row.opened_date ? formatDate(row.opened_date) : t("Not available")}`,
    `${t("Closed")}: ${row.closed_date ? formatDate(row.closed_date) : t(row.status === "open" ? "Still open" : "Not available")}`].join(" · ");
  $("tradeHistoryDetailSummary").innerHTML = [
    ["Days held", row.duration_days ?? t("Not available")],
    ["Units remaining", fmt(row.quantity_remaining, 4)],
    ["Trading realized P/L", tradeHistoryAmount(row.realized_trading_profit, row.currency)],
    ["Recorded income", tradeHistoryAmount(row.income, row.currency)],
    ["Recorded fees", tradeHistoryAmount(row.fees, row.currency)],
    ["Unrealized P/L", tradeHistoryAmount(row.unrealized_profit, row.currency)],
    ["Total P/L", tradeHistoryAmount(row.total_profit, row.currency)],
    ["P/L per day", tradeHistoryAmount(row.profit_per_day, row.currency)],
    ["P/L per year", tradeHistoryAmount(row.profit_per_year, row.currency)],
    ["Price date", row.valuation_date ? formatDate(row.valuation_date) : t("Not applicable")],
  ].map(([label, value]) => `<div class="stat"><span>${esc(t(label))}</span><b dir="auto">${esc(value)}</b></div>`).join("");
  $("tradeHistoryDetailIssues").textContent = (row.issues || []).map(tradeHistoryIssueText).join(" · ");
  const headers = ["Date", "Action", "Units", "Unit price", "Total", "Source"];
  $("tradeHistoryDetailTransactions").innerHTML = `<table class="holdings-table compact-report-table trade-history-table"><thead><tr>${headers.map((header) => `<th scope="col">${esc(t(header))}</th>`).join("")}</tr></thead><tbody>${(row.transactions || []).map((tx) => {
    const quantity = tx.allocated_quantity ?? tx.quantity;
    const values = [tx.trade_date ? formatDate(tx.trade_date) : t("Not available"), tradeHistoryActionLabel(tx.action), fmt(quantity, 4),
      tx.price === null || tx.price === undefined ? t("Not available") : money(tx.price, tx.currency || row.currency, 4),
      tradeHistoryAmount(Number.isFinite(quantity) && Number.isFinite(tx.price) ? quantity * tx.price : null, tx.currency || row.currency),
      tradeHistorySourceLabel(tx.source)];
    return `<tr>${values.map((value, index) => `<td data-label="${esc(t(headers[index]))}">${esc(value)}</td>`).join("")}</tr>`;
  }).join("")}</tbody></table>`;
}

function tradeHistoryCsvCell(value) {
  let text = value === null || value === undefined ? "" : String(value);
  if (typeof value !== "number" && /^\s*[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

function exportTradeHistoryCsv() {
  const rows = filteredTradeHistoryItems();
  if (!rows.length) return;
  const headers = ["Symbol", "Account", "Currency", "Position status", "Opened", "Closed", "Days held", "Realized P/L", "Unrealized P/L", "Total P/L", "P/L per day", "P/L per year", "History data notes"];
  const lines = [headers.map(t), ...rows.map((row) => [row.symbol, row.account_label, currencyDisplayLabel(row.currency),
    t(row.status === "closed" ? "Closed position" : "Open position"), row.opened_date ? formatDate(row.opened_date) : "", row.closed_date ? formatDate(row.closed_date) : "", row.duration_days,
    row.realized_profit, row.unrealized_profit, row.total_profit, row.profit_per_day, row.profit_per_year, (row.issues || []).map(tradeHistoryIssueText).join(" · ")])];
  const blob = new Blob(["\uFEFF", lines.map((line) => line.map(tradeHistoryCsvCell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `trade-history-${formatDate(state.tradeHistory.as_of_date).replaceAll("/", "-")}.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function renderReportSummary(report) {
  const accountDetails = report.account_details || [];
  const amounts = accountDetails.map((account) => reportAccountAmounts(account));
  const reportCash = reportSum(amounts.map((account) => account.cash));
  const reportSecurities = reportSum(amounts.map((account) => account.securities));
  const reportProfit = reportSum(amounts.map((account) => account.profit));
  const total = reportSum([reportCash, reportSecurities]);
  const funds = accountDetails.flatMap((account) => (account.funds || []).map((fund) => ({...fund, currency: account.currency})));
  const fundAmount = reportSum(funds.map((fund) => reportAmount(fund.amount, fund.currency)));
  const monthlyPension = reportSum(funds.filter((fund) => fund.kind === "Pension").map((fund) => reportAmount(fund.monthly_estimate, fund.currency)));
  $("reportsSummary").innerHTML = [
    ["Cash + securities", total, "Excludes linked fund records"],
    ["Cash", reportCash, "Recorded account cash"],
    ["Securities", reportSecurities, "Value of open positions"],
    ["P/L on open positions", reportProfit, "Realized + unrealized P/L attached to open positions; excludes closed positions and dividends"],
  ].map(([label, value, note]) => `<div class="stat"><span>${esc(t(label))}</span><b dir="auto">${esc(reportMoney(value))}</b><small>${esc(t(note))}</small></div>`).join("");
  $("reportValuationNote").textContent = total === null || reportProfit === null || fundAmount === null || monthlyPension === null
    ? t("Some totals are unavailable because an exchange rate or amount is missing. Account details retain their original currencies.")
    : `${t("Summary currency")}: ${currencyDisplayLabel(state.baseCurrency)} · ${t("Converted using current exchange rates")}`;
  $("reportRetirementSummary").innerHTML = funds.length ? `<div><b>${esc(t("Linked long-term funds"))}</b><span>${esc(t("Shown separately; not added to cash + securities to avoid double counting"))}</span></div><dl><div><dt>${esc(t("Recorded fund balances"))}</dt><dd>${esc(reportMoney(fundAmount))}</dd></div><div><dt>${esc(t("Monthly pension estimate"))}</dt><dd>${esc(reportMoney(monthlyPension))}</dd></div></dl>` : "";
  $("reportsDetails").innerHTML = accountDetails.length ? accountDetails.map((account, index) => {
    const owners = (account.persons || []).map(personLabel).join(", ") || optionLabel("No assigned people");
    const holdings = account.holdings || [];
    const funds = account.funds || [];
    const native = reportAccountAmounts(account, account.currency);
    return `
      <details class="report-account-card"${index === 0 ? " open" : ""}>
        <summary>
          <span><b>${esc(cleanSourceLabel(account.label) || account.id)}</b><small>${esc(optionLabel(account.type))} · ${esc(countryDisplayLabel(account.location))} · ${esc(owners)}</small></span>
          <strong>${reportMoney(native.value, account.currency)}</strong>
        </summary>
        <div class="report-account-content">
          <dl class="report-account-facts">
            <div><dt>Cash</dt><dd>${money(account.cash, account.currency, 0)}</dd></div>
            <div><dt>Securities</dt><dd>${reportMoney(native.securities, account.currency)}</dd></div>
            <div><dt>${esc(t("P/L on open positions"))}</dt><dd>${reportMoney(native.profit, account.currency)}</dd></div>
            <div><dt>Holdings</dt><dd>${esc(holdings.length)}</dd></div>
          </dl>
          <div class="table-wrap report-holdings-table">
            ${holdings.length ? `<table class="holdings-table compact-report-table">
              <thead><tr><th>Symbol</th><th>Name</th><th>Asset class</th><th>Quantity</th><th>Value</th><th>${esc(t("P/L on open positions"))}</th></tr></thead>
              <tbody>${holdings.map((holding) => `<tr>
                <td data-label="${esc(t("Symbol"))}"><b>${esc(holding.symbol)}</b></td>
                <td data-label="${esc(t("Name"))}">${esc(holding.name || holding.symbol)}</td>
                <td data-label="${esc(t("Asset class"))}">${esc(optionLabel(holding.asset_class || ""))}</td>
                <td data-label="${esc(t("Quantity"))}">${fmt(holding.quantity, 3)}</td>
                <td data-label="${esc(t("Value"))}">${money(holding.market_value, holding.currency || account.currency, 0)}</td>
                <td data-label="${esc(t("P/L on open positions"))}">${money(holding.profit, holding.currency || account.currency, 0)}</td>
              </tr>`).join("")}</tbody>
            </table>` : '<div class="empty">No holdings in this account</div>'}
          </div>
          ${funds.length ? `<div class="report-account-funds"><h4>Linked long-term funds</h4>${funds.map((fund) => `
            <span><b>${esc(fund.fund_name || fund.pension_id || fund.kind)}</b><small>${esc(optionLabel(fund.kind))} · ${money(fund.amount, account.currency, 0)}</small></span>`).join("")}</div>` : ""}
        </div>
      </details>`;
  }).join("") : '<div class="empty report-empty-state"><b>No accounts match these filters</b><span>Try All people or All account categories.</span></div>';
  const totalsBy = (field) => {
    const groups = new Map();
    accountDetails.forEach((account, index) => {
      const label = account[field] || "Unknown";
      if (!groups.has(label)) groups.set(label, []);
      groups.get(label).push(amounts[index].value);
    });
    return [...groups].map(([label, values]) => [label, reportSum(values)]);
  };
  const breakdown = (items, formatLabel) => items
    .sort((left, right) => (right[1] ?? -Infinity) - (left[1] ?? -Infinity))
    .map(([label, value]) => `<div class="report-breakdown-row"><span>${esc(formatLabel(label))}</span><b>${esc(reportMoney(value))}${total > 0 && value !== null ? `<small>${pct(value / total * 100)}</small>` : ""}</b></div>`)
    .join("") || `<div class="empty">${esc(t("No report data"))}</div>`;
  $("reportsByType").innerHTML = breakdown(totalsBy("type"), optionLabel);
  $("reportsByLocation").innerHTML = breakdown(totalsBy("location"), countryDisplayLabel);
  renderReportScopeSummary(report);
}

function currentReportFilters() {
  return {
    account_id: valueOf("reportAccount"),
    account_type: valueOf("reportAccountType"),
    location: valueOf("reportLocation"),
    person_id: valueOf("reportPerson"),
    person_name: selectedReportPersonName(),
    date_from: clampedHistoryDate(dateValue("reportFrom") || HISTORY_START_DATE),
    date_to: dateValue("reportTo") || todayString(),
  };
}

function reportQueryParams(filters, { includeDates = false } = {}) {
  const keys = ["account_id", "account_type", "location", "person_id", "person_name"];
  if (includeDates) keys.push("date_from", "date_to");
  const params = new URLSearchParams();
  keys.forEach((key) => {
    if (filters[key]) params.set(key, filters[key]);
  });
  return params;
}

function renderReportScopeSummary(report) {
  const filters = state.activeReportFilters || currentReportFilters();
  const accountLabelText = filters.account_id
    ? state.localAccounts.find((account) => account.id === filters.account_id)?.label || $("reportAccount")?.selectedOptions?.[0]?.textContent
    : "";
  const scope = [
    filters.person_name ? `${optionLabel("Person")}: ${filters.person_name}` : "",
    filters.account_type ? optionLabel(filters.account_type) : "",
    accountLabelText || "",
    filters.location ? countryDisplayLabel(filters.location) : "",
  ].filter(Boolean);
  const title = scope.length ? scope.join(" · ") : optionLabel("Entire portfolio");
  $("reportScopeSummary").innerHTML = `<b>${esc(title)}</b><span>${esc(report.accounts)} ${esc(t("Accounts"))} · ${esc(report.holdings)} ${esc(t("Holdings"))} · ${esc(report.funds?.count || 0)} ${esc(t("Linked funds"))}</span>`;
}

function markReportFiltersChanged() {
  refreshReportAccountSelect();
  if (!state.activeReportFilters) return;
  const changed = JSON.stringify(currentReportFilters()) !== JSON.stringify(state.activeReportFilters);
  $("reportsExportStatus").textContent = changed
    ? "Filters changed. Generate the report to update the preview; PDF download still uses the displayed report."
    : "";
}

async function exportReportsPdf() {
  if (!state.activeReportFilters) await loadReports();
  if (!state.activeReportFilters) return;
  const button = $("exportReportsPdf");
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  $("reportsExportStatus").textContent = "Preparing PDF report";
  try {
    const params = reportQueryParams(state.activeReportFilters, { includeDates: true });
    params.set("language", state.language);
    const response = await fetch(`/api/local/reports.pdf?${params}`);
    await downloadResponse(response, `portfolio-report-${todayString()}.pdf`);
    $("reportsExportStatus").textContent = "PDF report downloaded";
  } finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
  }
}

function renderAccountTrend(trend) {
  state.activeReportTrend = trend;
  const metric = state.reportTrendMetric || "value";
  const isValue = metric === "value";
  const accounts = (trend.accounts || []).map((account, index) => ({
    ...account,
    color: colorAt(index),
    points: (account.points || []).map((point) => ({
      ...point,
      plotted: isValue ? reportAmount(point.value, account.account?.currency) : (point.profit_percent == null ? null : Number(point.profit_percent)),
    })).filter((point) => point.plotted !== null && Number.isFinite(point.plotted) && Number.isFinite(Date.parse(point.date))),
  })).filter((account) => account.points.length);
  const series = accounts.flatMap((account) => account.points);
  const control = `<div class="report-chart-metrics" role="group" aria-label="${esc(t("Chart measure"))}">${[["value", "Account value"], ["profit_percent", "Recorded profit %"]].map(([key, label]) => `<button type="button" class="secondary compact-button" data-report-metric="${key}" aria-pressed="${metric === key}">${esc(t(label))}</button>`).join("")}</div>`;
  const dates = (trend.accounts || []).flatMap((account) => (account.points || []).map((point) => point.date)).filter((day) => Number.isFinite(Date.parse(day))).sort();
  const startDate = dates[0];
  const endDate = dates.at(-1);
  const period = startDate ? `${formatDate(startDate)} – ${formatDate(endDate)}` : "";
  if (!series.length) {
    $("accountTrendChart").innerHTML = control + `<div class="empty">${esc(t("No chart values available. Check the date range and exchange rates."))}</div>`;
    return;
  }
  const width = 920, height = 270, left = 100, right = 40, top = 22, bottom = 226;
  const minimum = Math.min(...series.map((point) => point.plotted), 0);
  const maximum = Math.max(...series.map((point) => point.plotted), 1);
  const first = Date.parse(startDate), last = Date.parse(endDate);
  const x = (day) => left + (Date.parse(day) - first) / (last - first || 1) * (width - left - right);
  const y = (value) => bottom - (value - minimum) / (maximum - minimum || 1) * (bottom - top);
  const display = (value) => isValue ? compactMoney(value, state.baseCurrency) : pct(value);
  const grid = [0, 0.5, 1].map((fraction) => {
    const value = minimum + (maximum - minimum) * fraction;
    return `<line x1="${left}" y1="${y(value)}" x2="${width - right}" y2="${y(value)}"></line><text x="${left - 12}" y="${y(value) + 4}" text-anchor="end">${esc(display(value))}</text>`;
  }).join("");
  const lines = accounts.map((account) => {
    const path = account.points.map((point, i) => `${i ? "L" : "M"} ${x(point.date)} ${y(point.plotted)}`).join(" ");
    // Isolated observations need a visible marker; they cannot form a line.
    const markers = account.points.length === 1 ? account.points : [account.points[0], account.points.at(-1)];
    return `<g><title>${esc(accountLabel(account.account))}</title><path d="${path}" fill="none" stroke="${account.color}" stroke-width="3"/>${markers.map((point) => `<circle cx="${x(point.date)}" cy="${y(point.plotted)}" r="4" fill="${account.color}"><title>${esc(`${accountLabel(account.account)} · ${formatDate(point.date)} · ${display(point.plotted)}`)}</title></circle>`).join("")}</g>`;
  }).join("");
  const legend = accounts.map((account) => {
    const lastPoint = account.points.at(-1);
    return `<div class="report-trend-account"><b><i style="--line-color:${account.color}"></i>${esc(accountLabel(account.account))}</b><span>${esc(display(lastPoint.plotted))} · ${esc(formatDate(lastPoint.date))}</span></div>`;
  }).join("");
  const missing = (trend.accounts || []).filter((account) => (account.points || []).some((point) => isValue && reportAmount(point.value, account.account?.currency) === null)).length;
  $("accountTrendChart").innerHTML = `
    <div class="chart-header"><div><div class="chart-title">${esc(t(isValue ? "Account value" : "Recorded profit %"))}</div><small class="chart-subtitle"><bdi dir="ltr">${esc(period)}</bdi> · ${isValue ? esc(currencyDisplayLabel(state.baseCurrency)) : esc(t("Saved or calculated P/L %; not a period return"))}</small></div>${control}</div>
    ${missing ? `<p class="section-note">${esc(t("Some history values are hidden because an exchange rate is missing."))}</p>` : ""}
    <div class="report-plot-scroll"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(t(isValue ? "Account value" : "Recorded profit %"))}"><title>${esc(t("Account history"))} · ${esc(period)}</title>${grid}${lines}<text x="${left}" y="256">${esc(formatDate(startDate))}</text>${startDate !== endDate ? `<text x="${width - right}" y="256" text-anchor="end">${esc(formatDate(endDate))}</text>` : ""}</svg></div>
    <div class="report-trend-legend">${legend}</div>`;
}

function financeReportMetricTooltip(metric, row, previous) {
  const definitions = {
    "Years": "Number of annual financial reports available for this company.",
    "Fiscal date": "The fiscal year-end date of this annual report; it is not the filing date or today's date.",
    "Latest revenue": "Total revenue reported for the latest available fiscal year.",
    "Revenue": "Total revenue reported for this fiscal year.",
    "Revenue growth": "Change in annual revenue compared with the previous available annual report.",
    "Net income": "Annual net income after expenses and taxes, as reported by the company.",
    "Net income growth": "Change in annual net income compared with the previous available annual report.",
    "Net margin": "Annual net income divided by annual revenue, multiplied by 100. Both amounts are from the same fiscal year.",
    "Free cash flow": "Annual operating cash flow minus capital expenditures from the same fiscal year.",
    "Long-term debt": "Long-term debt reported at fiscal year-end. Total debt or net debt may be used when long-term debt is unavailable.",
    "Debt": "Long-term debt reported at fiscal year-end. Total debt or net debt may be used when long-term debt is unavailable.",
  };
  const parts = [t(definitions[metric] || metric)];
  if (metric === "Years") return parts[0];
  if (!row) return parts[0];
  if (row.fiscal_date) parts.push(t("Fiscal year ending {date}.").replace("{date}", formatDate(row.fiscal_date)));
  if (["Revenue growth", "Net income growth"].includes(metric)) {
    const comparisonDate = row.comparison_fiscal_date || previous?.fiscal_date;
    if (!comparisonDate) return [...parts, t("No earlier annual report is available for comparison.")].join(" ");
    parts.push(t("Compares fiscal years ending {previous} and {current}; these may not be calendar years.")
      .replace("{previous}", formatDate(comparisonDate)).replace("{current}", formatDate(row.fiscal_date)));
    const field = metric === "Revenue growth" ? "revenue" : "net_income";
    const prior = row[`previous_${field}`] ?? previous?.[field];
    if (prior != null && row[field] != null) {
      parts.push(t("Previous amount: {previous}. Current amount: {current}.")
        .replace("{previous}", fmt(prior, 0)).replace("{current}", fmt(row[field], 0)));
    }
    parts.push(t(prior === 0 ? "Growth is unavailable because the previous amount is zero."
      : "Formula: (current amount − previous amount) / absolute previous amount × 100."));
  }
  return parts.join(" ");
}

function renderFinanceReport(report) {
  state.financeReport = report;
  const profile = report.profile || {};
  const summary = report.summary || {};
  const reports = report.reports || [];
  const company = profile.name || report.symbol || t("Company");
  $("financeReportStatus").textContent = `${company} · ${t(providerStatusHint(report.provider_status || {}) || "Online data loaded")}`;
  $("financeReportSummary").innerHTML = [
    ["Years", summary.years || 0],
    ["Latest revenue", fmt(summary.latest_revenue, 0)],
    ["Revenue growth", pct(summary.latest_revenue_growth_percent)],
    ["Net income", fmt(summary.latest_net_income, 0)],
    ["Net margin", pct(summary.latest_net_margin_percent)],
    ["Free cash flow", fmt(summary.latest_free_cash_flow, 0)],
    ["Long-term debt", fmt(summary.latest_long_term_debt, 0)],
  ].map(([label, value]) => `<div class="stat" tabindex="0" title="${esc(financeReportMetricTooltip(label, reports[0], reports[1]))}"><b>${esc(value)}</b><span>${esc(t(label))}</span></div>`).join("");
  if (!reports.length) {
    $("financeReportTable").innerHTML = `<div class="empty">${t("No annual online finance report data found for this symbol")}</div>`;
    return;
  }
  $("financeReportTable").innerHTML = `
    <table class="holdings-table compact-report-table">
      <thead>
        <tr>
          ${["Fiscal date", "Revenue", "Revenue growth", "Net income", "Net income growth", "Net margin", "Free cash flow", "Debt"].map((label) => `<th class="finance-metric-label" title="${esc(financeReportMetricTooltip(label, reports[0], reports[1]))}">${esc(t(label))}</th>`).join("")}
        </tr>
      </thead>
      <tbody>
        ${reports.map((row, index) => `
          <tr>
            ${[
              ["Fiscal date", formatDate(row.fiscal_date)], ["Revenue", fmt(row.revenue, 0)],
              ["Revenue growth", pct(row.revenue_growth_percent)], ["Net income", fmt(row.net_income, 0)],
              ["Net income growth", pct(row.net_income_growth_percent)], ["Net margin", pct(row.net_margin_percent)],
              ["Free cash flow", fmt(row.free_cash_flow, 0)], ["Debt", fmt(row.long_term_debt, 0)],
            ].map(([label, value]) => `<td tabindex="0" data-label="${esc(t(label))}" title="${esc(financeReportMetricTooltip(label, row, reports[index + 1]))}">${esc(value)}</td>`).join("")}
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

function companyOutlookDiagramSource(source) {
  // Translate labels before Mermaid turns them into SVG foreignObject content.
  return String(source || "").replace(/"([^"\n]*)"/gu, (_match, label) => {
    const localized = label.split("<br/>").map((line) => {
      const separator = line.indexOf(": ");
      return separator < 0 ? t(line)
        : `${t(line.slice(0, separator))}: ${t(line.slice(separator + 2))}`;
    }).join("<br/>");
    return `"${localized.replace(/"/gu, "'")}"`;
  });
}

function renderCompanyOutlookDiagramFallback(outlook) {
  const graph = outlook.graph || {};
  const nodes = graph.nodes || [];
  const labels = Object.fromEntries(nodes.map((node) => [node.id, node.label || node.id]));
  const edges = graph.edges || [];
  return `
    <div class="outlook-map-fallback">
      <div class="outlook-map-nodes">
        ${nodes.map((node) => `<span class="outlook-map-node ${esc(node.type || "")}">${esc(t(node.label || node.id))}</span>`).join("")}
      </div>
      <div class="outlook-map-relations">
        ${edges.length ? edges.map((edge) => `<span><b>${esc(t(labels[edge.from] || edge.from))}</b> → ${esc(t(edge.label || "related to"))} → <b>${esc(t(labels[edge.to] || edge.to))}</b></span>`).join("") : `<span>${t("No report-backed relationships were available.")}</span>`}
      </div>
    </div>
  `;
}

async function renderCompanyOutlookDiagram(outlook) {
  const diagram = $("companyOutlookDiagram");
  const language = state.language;
  const sequence = ++companyOutlookDiagramSequence;
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
    const rendered = await window.mermaid.render(`companyOutlookMap${sequence}`, companyOutlookDiagramSource(outlook.mermaid));
    if (sequence !== companyOutlookDiagramSequence || language !== state.language) return;
    diagram.innerHTML = rendered.svg;
    rendered.bindFunctions?.(diagram);
  } catch (error) {
    if (sequence !== companyOutlookDiagramSequence || language !== state.language) return;
    diagram.innerHTML = renderCompanyOutlookDiagramFallback(outlook);
    $("companyOutlookStatus").textContent = "Analysis loaded · Relationship map shown as a list";
    appWarn("company_outlook.diagram_fallback", { message: error?.message || "Diagram render failed" });
  }
}

function outlookScoreText(value, maximum = 100) {
  if (value == null || !Number.isFinite(Number(value)) || maximum <= 0) return t("Not available");
  return `${fmt(Math.round(Number(value) / maximum * 1000) / 10, 1)}/100`;
}

function renderCompanyOutlook(outlook) {
  state.companyOutlook = outlook;
  $("companyOutlookEmpty").hidden = true;
  $("companyOutlookResults").hidden = false;
  const industry = outlook.industry || {};
  const components = outlook.score_components || {};
  $("companyOutlookStatus").textContent = `${outlook.symbol} · ${t(outlook.label || "Mixed")} · ${t("Confidence")}: ${t(outlook.confidence || "Low")} · ${t(outlook.peer_source || "")}`;
  $("companyOutlookSummary").innerHTML = [
    ["Final score", outlookScoreText(outlook.score), "Final outlook score on a 0–100 scale. Combines company fundamentals, industry outlook, related-industry effects, peer rank and data quality."],
    ["Peer rank", `${outlook.rank || 1}/${(outlook.companies || []).length || 1}`],
    ["Industry", industry.health || "Not available"],
    ["Industry score", outlookScoreText(industry.score, 25), "Industry score on a 0–100 scale. Contributes up to 25 points to the final outlook score."],
    ["Company signals", outlookScoreText(components.company_fundamentals, 45), "Company fundamentals on a 0–100 scale. Contributes up to 45 points to the final outlook score."],
    ["Related effect", outlookScoreText(components.related_industry_effect, 15), "Related-industry effect on a 0–100 scale. Contributes up to 15 points to the final outlook score."],
  ].map(([label, value, tooltip]) => `<div class="stat"${tooltip ? ` title="${esc(t(tooltip))}"` : ""}><b>${esc(t(value))}</b><span>${esc(t(label))}</span></div>`).join("");
  $("companyOutlookWords").innerHTML = `
    <p>${esc(t(outlook.simple_words || ""))}</p>
    ${outlook.missing?.length ? `<div class="sub">${t("Missing or limited")}: ${esc(outlook.missing.map((item) => t(item)).join(", "))}</div>` : ""}
  `;
  const companies = outlook.companies || [];
  const fundamentalsTooltip = t("Company fundamentals score, out of 100. Compares growth, profitability, cash flow and balance-sheet metrics with the peer group. This component contributes up to 45 points to the final outlook score shown above.");
  $("companyOutlookTable").innerHTML = companies.length ? `
    <table class="holdings-table compact-report-table outlook-table">
      <thead><tr>${["Company", "Industry", "Fiscal date", "Revenue growth", "Operating margin", "Net margin", "FCF margin", "Current ratio", "Company signals"].map((label) => `<th${label === "Company signals" ? ` title="${esc(fundamentalsTooltip)}"` : ""}>${esc(t(label))}</th>`).join("")}</tr></thead>
      <tbody>${companies.map((company) => `
        <tr>
          <td data-label="Company"><b>${esc(company.symbol)}</b><div class="sub">${esc(company.name || "")}</div></td>
          <td data-label="Industry">${esc(t(company.industry || "Not available"))}</td>
          <td data-label="Fiscal date">${esc(formatDate(company.fiscal_date))}</td>
          <td data-label="Revenue growth">${pct(company.revenue_growth_percent)}</td>
          <td data-label="Operating margin">${pct(company.operating_margin_percent)}</td>
          <td data-label="Net margin">${pct(company.net_margin_percent)}</td>
          <td data-label="FCF margin">${pct(company.free_cash_flow_margin_percent)}</td>
          <td data-label="Current ratio">${fmt(company.current_ratio, 2)}</td>
          <td data-label="${esc(t("Company signals"))}" title="${esc(fundamentalsTooltip)}">${outlookScoreText(company.symbol === outlook.symbol ? components.company_fundamentals ?? company.score : company.score, 45)}</td>
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
    $("financeReportStatus").textContent = t("Enter a ticker symbol");
    return;
  }
  $("financeReportStatus").textContent = t("Fetching online finance report");
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
      <div class="sub">${esc(currencyDisplayLabel(snapshot.account?.currency || ""))} · ${esc(t(snapshot.source || "manual"))}</div>
    </div>
  `).join("") : '<div class="empty">No saved history points in this range</div>';
}

async function loadHistorySnapshots(filters = currentReportFilters()) {
  const params = reportQueryParams(filters, { includeDates: true });
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
  const value = valueOf("historyValue");
  if (!value.trim() || !Number.isFinite(Number(value))) {
    $("historyStatus").textContent = t("Enter a total value before saving history. Blank values do not replace existing records.");
    $("historyValue").setAttribute("aria-invalid", "true");
    $("historyValue").focus();
    return;
  }
  $("historyValue").removeAttribute("aria-invalid");
  await api("/api/local/account-snapshots", {
    method: "POST",
    body: JSON.stringify({
      account_id: accountId,
      snapshot_date: clampedHistoryDate(dateValue("historyDate") || todayString()),
      value,
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
  const filters = currentReportFilters();
  if (["reportFrom", "reportTo"].some((id) => valueOf(id) && !dateValue(id)) || filters.date_from > filters.date_to) {
    $("reportsExportStatus").textContent = t("Enter a valid history range: From must be on or before To (dd/mm/yyyy).");
    return;
  }
  const params = reportQueryParams(filters);
  const trendParams = reportQueryParams(filters, { includeDates: true });
  const button = $("loadReports");
  const historyButton = $("updateReportHistory");
  const version = (state.reportLoadVersion || 0) + 1;
  state.reportLoadVersion = version;
  button.disabled = true;
  historyButton.disabled = true;
  button.setAttribute("aria-busy", "true");
  $("reportsExportStatus").textContent = "Generating report";
  try {
    const [report, trend, snapshots] = await Promise.all([
      api(`/api/local/reports?${params}`),
      api(`/api/local/account-trends?${trendParams}`),
      api(`/api/local/account-snapshots?${trendParams}`),
    ]);
    if (version !== state.reportLoadVersion) return;
    state.activeReportFilters = filters;
    state.activeReport = report;
    state.historySnapshots = snapshots.items || [];
    renderReportSummary(report);
    renderAccountTrend(trend);
    renderHistorySnapshots();
    $("reportsExportStatus").textContent = report.accounts
      ? `Report ready · ${report.accounts} accounts included`
      : "No accounts match these filters";
  } catch (error) {
    if (version === state.reportLoadVersion) {
      $("reportsExportStatus").textContent = t(state.activeReport
        ? "Could not update the report. The previous report is still displayed. Try again."
        : "Could not load the report. Try again.");
    }
    throw error;
  } finally {
    if (version === state.reportLoadVersion) {
      button.disabled = false;
      historyButton.disabled = false;
      button.removeAttribute("aria-busy");
    }
  }
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
      ? `<span>${esc(optionLabel("Saved"))} ${fmt(fund.amount, 0)} · ${esc(optionLabel("Monthly pension estimate"))} ${fmt(fund.monthly_estimate, 0)}</span>`
      : `<span>${esc(optionLabel("Saved"))} ${fmt(fund.amount, 0)} · <em class="muted-inline">${esc(optionLabel("Monthly pension estimate"))} ${esc(optionLabel("N/A"))}</em></span>`;
    const accountText = fund.account_label ? ` · ${esc(optionLabel("Account"))} ${esc(fund.account_label)}` : "";
    const historyChange = Number(fund.history_change || 0);
    const historyText = Number(fund.history_points || 0) > 1
      ? (state.language === "he"
        ? `התקדמות ${historyChange > 0 ? "+" : ""}${fmt(historyChange, 0)} (${historyChange > 0 ? "+" : ""}${pct(fund.history_change_percent)}) מאז ${formatDate(fund.history_first_date)}`
        : `Progress ${historyChange > 0 ? "+" : ""}${fmt(historyChange, 0)} (${historyChange > 0 ? "+" : ""}${pct(fund.history_change_percent)}) since ${formatDate(fund.history_first_date)}`)
      : (state.language === "he" ? `${fmt(fund.history_points || 0, 0)} נקודות היסטוריה שמורות` : `${fmt(fund.history_points || 0, 0)} saved history point`);
    return `
      <div class="stack-item management-item fund-management-item">
        <div class="fund-management-main">
          <b>${esc([optionLabel(fund.kind), fund.fund_name || "", fund.pension_id].filter(Boolean).join(" · "))}</b>
          ${estimate}
        </div>
        <div class="row-actions fund-management-actions">
          <button class="secondary compact-button" type="button" data-fund-history="${esc(fund.id)}">${esc(optionLabel("History"))}</button>
          <button class="secondary compact-button" type="button" data-edit-fund="${esc(fund.id)}">Edit</button>
          <button class="secondary compact-button" type="button" data-delete-fund="${esc(fund.id)}">Remove</button>
        </div>
        <div class="sub">${esc(historyText)}${fund.history_latest_date ? ` · ${esc(optionLabel("Updated"))} ${esc(formatDate(fund.history_latest_date))}` : ""} · ${(fund.persons || []).length ? `${(fund.persons || []).map(personLabel).map(esc).join(" · ")} · ` : ""}${esc(fund.comments || optionLabel("No comments"))}${accountText}</div>
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
  return `${personFullName(person)} · ${formatDate(person.birth_date)}${age ? ` · ${optionLabel("Age")} ${fmt(age, 1)}` : ""}`;
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
}

function renderPensionSimulatorControls() {
  renderSimulationPersonOptions();
  renderPensionInsuranceControls();
  renderPensionPeriods();
  renderPensionRates();
  renderPensionScenarios();
  renderPensionSimulationResults();
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
  const field = $("simPeriodFromField");
  if (!input) return;
  input.hidden = !custom;
  if (field) field.hidden = !custom;
  if (!custom) input.value = "";
}

function syncPensionRateFromMode() {
  const custom = valueOf("simRateFromMode") === "custom";
  const input = $("simRateFrom");
  const field = $("simRateFromField");
  if (!input) return;
  input.hidden = !custom;
  if (field) field.hidden = !custom;
  if (!custom) input.value = "";
}

function pensionPeriodSummary() {
  const scenario = activePensionScenario();
  const rows = scenario?.income_periods || [];
  if (!scenario) return "No scenario selected";
  if (!rows.length) return "No salary periods";
  return `${rows.length} salary period${rows.length === 1 ? "" : "s"}`;
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
  const spouse = numberValue("simSpouseSurvivorsCoverage") || 0;
  const children = numberValue("simChildrenSurvivorsCoverage") || 0;
  const survivorsFactor = numberValue("simSurvivorsFactor");
  return Number.isFinite(Number(fromAge))
    && Number.isFinite(Number(toAge))
    && Number(toAge) > Number(fromAge)
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

function scheduleAgeLabel(value) {
  return String(Math.round(Number(value) * 100) / 100);
}

function pensionScheduleCoverageIssue(scenario, field, label) {
  const currentAge = Number(scenario?.current_age);
  const retireAge = Number(scenario?.retire_age);
  if (!Number.isFinite(currentAge) || !Number.isFinite(retireAge) || retireAge <= currentAge) return "";
  const tolerance = 1e-6;
  const sourceRows = Array.isArray(scenario?.[field]) ? scenario[field] : [];
  const periods = sourceRows.map((period) => ({
    fromAge: Math.max(Number(period?.from_age), currentAge),
    toAge: Math.min(Number(period?.to_age), retireAge),
    annualReturn: period?.annual_return,
  })).filter((period) => (
    Number.isFinite(period.fromAge)
    && Number.isFinite(period.toAge)
    && period.toAge > currentAge + tolerance
    && period.fromAge < retireAge - tolerance
  )).sort((left, right) => left.fromAge - right.fromAge);
  let cursor = currentAge;
  if (!periods.length) {
    return `${label} schedule is missing ages ${scheduleAgeLabel(currentAge)}–${scheduleAgeLabel(retireAge)}.`;
  }
  for (const period of periods) {
    if (field === "return_periods" && (
      period.annualReturn === ""
      || period.annualReturn === null
      || period.annualReturn === undefined
      || !Number.isFinite(Number(period.annualReturn))
    )) {
      return "Return schedule has an invalid annual return.";
    }
    if (period.fromAge > cursor + tolerance) {
      return `${label} schedule is missing ages ${scheduleAgeLabel(cursor)}–${scheduleAgeLabel(period.fromAge)}.`;
    }
    if (period.fromAge < cursor - tolerance) {
      return `${label} schedule has overlapping periods at ages ${scheduleAgeLabel(period.fromAge)}–${scheduleAgeLabel(Math.min(cursor, period.toAge))}.`;
    }
    cursor = Math.max(cursor, period.toAge);
  }
  if (cursor < retireAge - tolerance) {
    return `${label} schedule is missing ages ${scheduleAgeLabel(cursor)}–${scheduleAgeLabel(retireAge)}.`;
  }
  return "";
}

function pensionScenarioScheduleIssue(scenario) {
  return pensionScheduleCoverageIssue(scenario, "income_periods", "Salary")
    || pensionScheduleCoverageIssue(scenario, "return_periods", "Return");
}

function scenarioHasProfitRates(scenario) {
  return !pensionScheduleCoverageIssue(scenario, "return_periods", "Return");
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
    projectionButton.textContent = hasActiveScenario ? "Save changes" : "Save scenario";
    projectionButton.title = hasActiveScenario
      ? "Save the changes to this retirement scenario."
      : "Save this retirement scenario.";
  }
  const editorTitle = $("pensionScenarioFormTitle");
  if (editorTitle) editorTitle.textContent = hasActiveScenario ? "Edit scenario" : "Create scenario";
  const periodButton = $("addPensionPeriod");
  if (periodButton) periodButton.disabled = !pensionPeriodFormValid();
  const rateButton = $("addPensionRate");
  if (rateButton) rateButton.disabled = !pensionRateFormValid();
  const stopButton = $("pensionStopWorkNow");
  if (stopButton) stopButton.disabled = !hasActiveScenario;
  const showPeriodButton = $("showPensionPeriodEntry");
  const salaryIssue = hasActiveScenario
    ? pensionScheduleCoverageIssue(activePensionScenario(), "income_periods", "Salary")
    : "";
  if (showPeriodButton) {
    showPeriodButton.disabled = !hasActiveScenario || !salaryIssue.includes("is missing ages");
    showPeriodButton.title = !hasActiveScenario
      ? "Choose a scenario before adding salary periods."
      : salaryIssue || "The salary schedule already covers the full age range.";
  }
  const showRateButton = $("showPensionRateEntry");
  const returnIssue = hasActiveScenario
    ? pensionScheduleCoverageIssue(activePensionScenario(), "return_periods", "Return")
    : "";
  if (showRateButton) {
    showRateButton.disabled = !hasActiveScenario || !returnIssue.includes("is missing ages");
    showRateButton.title = !hasActiveScenario
      ? "Choose a scenario before adding return periods."
      : returnIssue || "The return schedule already covers the full age range.";
  }
  const runButton = $("runPensionSimulation");
  const scheduleProblem = state.pensionScenarios.map((scenario) => ({
    scenario,
    issue: pensionScenarioScheduleIssue(scenario),
  })).find((item) => item.issue);
  const scheduleProblemText = scheduleProblem
    ? `${scheduleProblem.scenario.name}: ${scheduleProblem.issue}`
    : "";
  if (runButton) {
    runButton.disabled = !state.pensionScenarios.length || Boolean(scheduleProblem);
    runButton.title = !state.pensionScenarios.length
      ? "Save at least one scenario before running the comparison."
      : scheduleProblem
        ? scheduleProblemText
        : "Calculate and compare every saved scenario.";
  }
  const runHint = $("pensionRunHint");
  if (runHint) {
    runHint.textContent = !state.pensionScenarios.length
      ? "Save a scenario and add its return periods before running the comparison."
      : scheduleProblem
        ? scheduleProblemText
        : "All scenarios are ready to compare.";
  }
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

function setPensionEntryVisibility(entryId, triggerId, visible, focusId, { focus = true } = {}) {
  const entry = $(entryId);
  const trigger = $(triggerId);
  if (!entry || !trigger) return;
  entry.hidden = !visible;
  trigger.hidden = visible;
  trigger.setAttribute("aria-expanded", String(visible));
  if (!focus) return;
  requestAnimationFrame(() => {
    const target = visible ? $(focusId) : trigger;
    target?.focus();
  });
}

function nextPensionScheduleStart(scenario, field) {
  const currentAge = Number(scenario?.current_age);
  const retireAge = Number(scenario?.retire_age);
  if (!Number.isFinite(currentAge) || !Number.isFinite(retireAge)) return currentAge;
  const periods = (Array.isArray(scenario?.[field]) ? scenario[field] : []).map((period) => ({
    fromAge: Math.max(Number(period?.from_age), currentAge),
    toAge: Math.min(Number(period?.to_age), retireAge),
  })).filter((period) => Number.isFinite(period.fromAge) && Number.isFinite(period.toAge) && period.toAge > period.fromAge)
    .sort((left, right) => left.fromAge - right.fromAge);
  let cursor = currentAge;
  for (const period of periods) {
    if (period.fromAge > cursor + 1e-6) return cursor;
    if (period.fromAge <= cursor + 1e-6 && period.toAge > cursor) cursor = period.toAge;
  }
  return Math.min(cursor, retireAge);
}

function openPensionPeriodEntry() {
  resetPensionPeriodForm();
  const scenario = activePensionScenario();
  const nextAge = nextPensionScheduleStart(scenario, "income_periods");
  if (Number.isFinite(nextAge) && nextAge > Number(scenario?.current_age) + 1e-6) {
    $("simPeriodFromMode").value = "custom";
    $("simPeriodFrom").value = scheduleAgeLabel(nextAge);
    syncPensionPeriodFromMode();
  }
  setPensionEntryVisibility("pensionPeriodEntry", "showPensionPeriodEntry", true, "simPeriodFromMode");
}

function closePensionPeriodEntry({ focus = true } = {}) {
  resetPensionPeriodForm();
  setPensionEntryVisibility("pensionPeriodEntry", "showPensionPeriodEntry", false, "simPeriodFromMode", { focus });
}

function openPensionRateEntry() {
  resetPensionRateForm();
  const scenario = activePensionScenario();
  const nextAge = nextPensionScheduleStart(scenario, "return_periods");
  if (Number.isFinite(nextAge) && nextAge > Number(scenario?.current_age) + 1e-6) {
    $("simRateFromMode").value = "custom";
    $("simRateFrom").value = scheduleAgeLabel(nextAge);
    syncPensionRateFromMode();
  }
  setPensionEntryVisibility("pensionRateEntry", "showPensionRateEntry", true, "simRateFromMode");
}

function closePensionRateEntry({ focus = true } = {}) {
  resetPensionRateForm();
  setPensionEntryVisibility("pensionRateEntry", "showPensionRateEntry", false, "simRateFromMode", { focus });
}

function openPensionPeriodModal(index = state.activePensionScenarioIndex) {
  if (Number.isInteger(index) && state.pensionScenarios[index]) {
    state.activePensionScenarioIndex = index;
  }
  const scenario = activePensionScenario();
  if (!scenario) {
    $("pensionProjectionStatus").textContent = "Add or edit a scenario before adding salary periods";
    return;
  }
  resetPensionPeriodForm();
  resetPensionRateForm();
  setPensionEntryVisibility("pensionPeriodEntry", "showPensionPeriodEntry", false, "simPeriodFromMode", { focus: false });
  setPensionEntryVisibility("pensionRateEntry", "showPensionRateEntry", false, "simRateFromMode", { focus: false });
  const name = $("pensionPeriodProjectionName");
  if (name) name.textContent = scenario.name;
  const status = $("pensionPeriodStatus");
  if (status) status.textContent = pensionScenarioScheduleIssue(scenario);
  renderPensionScenarios();
  renderPensionPeriods();
  renderPensionRates();
  openModal("pensionPeriodModal", document.activeElement, { focusId: "pensionPeriodTitle" });
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
    frame.innerHTML = '<div class="empty compact-empty">Choose a scenario before adding salary periods</div>';
    updatePensionActionStates();
    return;
  }
  frame.innerHTML = rows.length ? rows.map((period, index) => `
    <article class="retirement-period-card" aria-label="Salary period ${index + 1}">
      <div class="retirement-period-card-head">
        <h4>Salary period ${index + 1}</h4>
        <button class="secondary compact-button" type="button" data-delete-pension-period="${index}" title="Remove this salary period from the selected scenario.">Remove</button>
      </div>
      <div class="retirement-period-fields salary-period-fields">
        <label class="management-field"><span>From age</span><input data-pension-period-index="${index}" data-pension-period-field="from_age" type="number" min="0" step="0.1" value="${esc(period.from_age ?? "")}" /></label>
        <label class="management-field"><span>To age</span><input data-pension-period-index="${index}" data-pension-period-field="to_age" type="number" min="0" step="0.1" value="${esc(period.to_age ?? "")}" /></label>
        <label class="management-field"><span>Monthly salary</span><input data-pension-period-index="${index}" data-pension-period-field="monthly_income" type="number" min="0" step="0.01" value="${esc(period.monthly_income ?? 0)}" /></label>
        <label class="management-field"><span>Pension deposit %</span><input data-pension-period-index="${index}" data-pension-period-field="contribution_percent" type="number" min="0" step="0.01" value="${esc(period.contribution_percent ?? 0)}" /></label>
        <label class="management-field"><span>Extra monthly deposit</span><input data-pension-period-index="${index}" data-pension-period-field="monthly_deposit" type="number" min="0" step="0.01" value="${esc(period.monthly_deposit ?? 0)}" /></label>
        <label class="management-field"><span>Insurance track</span>${pensionPeriodTrackSelect(index, period)}</label>
        <label class="management-field"><span>Disability coverage</span>${pensionPeriodCoverageSelect(index, "disability_coverage_percent", DISABILITY_COVERAGE_OPTIONS, period.disability_coverage_percent)}</label>
        <label class="management-field"><span>Spouse survivors coverage</span>${pensionPeriodCoverageSelect(index, "spouse_survivors_coverage_percent", SPOUSE_SURVIVORS_OPTIONS, period.spouse_survivors_coverage_percent)}</label>
        <label class="management-field"><span>Children survivors coverage</span>${pensionPeriodCoverageSelect(index, "children_survivors_coverage_percent", CHILDREN_SURVIVORS_OPTIONS, period.children_survivors_coverage_percent)}</label>
        <label class="management-field"><span>Survivors factor</span><input data-pension-period-index="${index}" data-pension-period-field="survivors_capitalization_factor" type="number" min="1" step="0.01" value="${esc(period.survivors_capitalization_factor ?? 200)}" /></label>
      </div>
    </article>
  `).join("") : '<div class="empty compact-empty">No salary periods yet. Add the first period directly below.</div>';
  updatePensionActionStates();
}

function renderPensionRates() {
  const frame = $("pensionRateRows");
  if (!frame) return;
  const scenario = activePensionScenario();
  const rows = selectedPensionReturnRows();
  if (!scenario) {
    frame.innerHTML = '<div class="empty compact-empty">Choose a scenario before adding return periods</div>';
    updatePensionActionStates();
    return;
  }
  frame.innerHTML = rows.length ? rows.map((period, index) => `
    <article class="retirement-period-card" aria-label="Return period ${index + 1}">
      <div class="retirement-period-card-head">
        <h4>Return period ${index + 1}</h4>
        <button class="secondary compact-button" type="button" data-delete-pension-rate="${index}" title="Remove this return period from the selected scenario.">Remove</button>
      </div>
      <div class="retirement-period-fields return-period-fields">
        <label class="management-field"><span>From age</span><input data-pension-rate-index="${index}" data-pension-rate-field="from_age" type="number" min="0" step="0.1" value="${esc(period.from_age ?? "")}" /></label>
        <label class="management-field"><span>To age</span><input data-pension-rate-index="${index}" data-pension-rate-field="to_age" type="number" min="0" step="0.1" value="${esc(period.to_age ?? "")}" /></label>
        <label class="management-field"><span>Annual profit %</span><input data-pension-rate-index="${index}" data-pension-rate-field="annual_return" type="number" step="0.01" value="${esc(period.annual_return ?? 0)}" /></label>
      </div>
    </article>
  `).join("") : '<div class="empty compact-empty">No return periods yet. Add at least one period directly below.</div>';
  updatePensionActionStates();
}

function renderPensionScenarios() {
  const frame = $("pensionScenarios");
  if (!frame) return;
  const count = $("pensionScenarioCount");
  if (count) {
    const scenarioCount = state.pensionScenarios.length;
    count.textContent = optionLabel(`${scenarioCount} saved scenario${scenarioCount === 1 ? "" : "s"}`);
  }
  frame.innerHTML = state.pensionScenarios.length ? state.pensionScenarios.map((scenario, index) => {
    const salaryCount = scenario.income_periods?.length || 0;
    const returnCount = scenario.return_periods?.length || 0;
    const salaryIssue = pensionScheduleCoverageIssue(scenario, "income_periods", "Salary");
    const returnIssue = pensionScheduleCoverageIssue(scenario, "return_periods", "Return");
    return `
      <article class="retirement-scenario-card" aria-label="Scenario ${esc(scenario.name)}">
        <div class="retirement-scenario-card-head">
          <div>
            <span class="retirement-scenario-kicker">Saved scenario</span>
            <h4>${esc(scenario.name)}</h4>
          </div>
        </div>
        <dl class="retirement-scenario-facts">
          <div><dt>Person</dt><dd>${esc(scenario.person_name || "Manual")}</dd></div>
          <div><dt>Age range</dt><dd>${fmt(scenario.current_age, 1)}–${fmt(scenario.retire_age, 1)}</dd></div>
          <div><dt>Pension total</dt><dd>${money(scenario.amount, state.baseCurrency, 0)}</dd></div>
          <div class="${salaryIssue ? "needs-attention" : ""}"${salaryIssue ? ` title="${esc(salaryIssue)}"` : ""}><dt>Salary periods</dt><dd>${esc(salaryCount)}${salaryIssue ? " · Incomplete" : ""}</dd></div>
          <div class="${returnIssue ? "needs-attention" : ""}"${returnIssue ? ` title="${esc(returnIssue)}"` : ""}><dt>Return periods</dt><dd>${esc(returnCount)}${returnIssue ? " · Incomplete" : ""}</dd></div>
        </dl>
        <div class="retirement-scenario-actions">
          <button class="secondary compact-button" type="button" data-edit-pension-scenario="${index}" title="Open this saved scenario in the edit dialog.">Edit scenario</button>
          <button class="secondary compact-button" type="button" data-schedule-pension-scenario="${index}" title="Edit salary, deposits, insurance, and return assumptions for this scenario.">Salary &amp; returns</button>
          <button class="secondary compact-button danger-outline" type="button" data-delete-pension-scenario="${index}" title="Remove this scenario and all of its saved periods.">Remove scenario</button>
        </div>
      </article>
    `;
  }).join("") : '<div class="empty compact-empty">No scenarios yet. Select New scenario to create your first retirement alternative.</div>';
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
            <th>Return Periods</th>
            <th>Starting Balance</th>
            <th>Monthly Pension</th>
            <th>Final Amount</th>
            <th>Net Deposits</th>
            <th>Insurance Cost</th>
            <th>Investment Gain</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((scenario, rowIndex) => {
            const result = state.pensionSimulationResults[rowIndex] || {};
            return `
              <tr>
                <td>
                  <b>${esc(scenario.name)}</b>
                  <small>${esc(optionLabel(scenario.kind))} · ${esc(optionLabel("Age"))} ${fmt(scenario.current_age, 1)}-${fmt(scenario.retire_age, 1)} · ${scenario.income_periods?.length || 0} ${esc(optionLabel("salary periods"))}</small>
                </td>
                <td>${esc(scenario.return_periods?.length || 0)}</td>
                <td>${money(result.starting_amount || 0, state.baseCurrency, 0)}</td>
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
  const returnFocus = document.activeElement;
  state.activePensionScenarioIndex = index;
  $("simPersonSource").value = scenario.person_index ?? "";
  $("simName").value = scenario.name || "";
  setDateField("simBirthDate", scenario.birth_date || "");
  $("simCurrentAge").value = scenario.current_age || "";
  $("simRetireAge").value = scenario.retire_age || "";
  $("simAmount").value = scenario.amount || "";
  $("simFactor").value = scenario.factor || 200;
  $("pensionProjectionStatus").textContent = "";
  syncScenarioDerivedFields();
  savePensionSimulationState();
  renderPensionPeriods();
  renderPensionRates();
  updatePensionActionStates();
  openModal("pensionScenarioModal", returnFocus, { focusId: "pensionScenarioFormTitle" });
}

function newPensionScenario() {
  const returnFocus = document.activeElement;
  state.activePensionScenarioIndex = null;
  ["simName", "simBirthDate", "simCurrentAge", "simRetireAge", "simAmount"].forEach((id) => { $(id).value = ""; });
  $("simFactor").value = "200";
  const people = state.familyMembers || [];
  $("simPersonSource").value = people.length === 1 ? "0" : "";
  if ($("simPersonSource").value) applySimulationPerson();
  syncScenarioDerivedFields();
  $("pensionProjectionStatus").textContent = "";
  savePensionSimulationState();
  renderPensionPeriods();
  renderPensionRates();
  updatePensionActionStates();
  openModal("pensionScenarioModal", returnFocus, { focusId: "simPersonSource" });
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
    $("pensionPeriodStatus").textContent = "Fill To Age and survivors factor when survivors coverage is selected";
    return;
  }
  scenario.income_periods = [...(scenario.income_periods || []), period];
  invalidatePensionSimulation();
  renderPensionScenarios();
  renderPensionPeriods();
  renderFundsOverview();
  const remainingIssue = pensionScenarioScheduleIssue(scenario);
  $("pensionPeriodStatus").textContent = remainingIssue || "Salary period added";
  closePensionPeriodEntry();
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
  renderPensionScenarios();
  renderPensionRates();
  renderFundsOverview();
  const remainingIssue = pensionScenarioScheduleIssue(scenario);
  $("pensionPeriodStatus").textContent = remainingIssue || "Return period added";
  closePensionRateEntry();
}

function stopPensionWorkNow() {
  const scenario = activePensionScenario();
  if (!scenario) {
    $("pensionPeriodStatus").textContent = "Add or edit a pension scenario first";
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
  closePensionPeriodEntry({ focus: false });
}

function addPensionScenario() {
  if (!projectionFormValid()) {
    $("pensionProjectionStatus").textContent = "Fill scenario name, age range, and payout factor";
    updatePensionActionStates();
    return;
  }
  const editing = Boolean(activePensionScenario());
  const scenario = currentPensionScenario();
  if (editing) {
    state.pensionScenarios[state.activePensionScenarioIndex] = scenario;
    $("pensionSimulationStatus").textContent = "Scenario updated";
  } else {
    state.pensionScenarios.push(scenario);
    state.activePensionScenarioIndex = state.pensionScenarios.length - 1;
    $("pensionSimulationStatus").textContent = "Scenario added";
  }
  const savedIndex = state.activePensionScenarioIndex;
  invalidatePensionSimulation();
  closeModal($("pensionScenarioModal"));
  renderPensionScenarios();
  renderPensionPeriods();
  renderPensionRates();
  renderFundsOverview();
  requestAnimationFrame(() => {
    document.querySelector(`[data-edit-pension-scenario="${savedIndex}"]`)?.focus();
  });
}

async function runPensionSimulation({ silent = false } = {}) {
  const baseScenarios = pensionSimulationPayloadScenarios();
  if (!baseScenarios.length || baseScenarios.some((scenario) => !scenario.current_age || !scenario.retire_age || scenario.retire_age <= scenario.current_age)) {
    if (!silent) $("pensionSimulationStatus").textContent = "Add at least one valid pension scenario before running";
    renderPensionSimulationResults();
    return;
  }
  const scheduleProblem = baseScenarios.map((scenario) => ({
    scenario,
    issue: pensionScenarioScheduleIssue(scenario),
  })).find((item) => item.issue);
  if (scheduleProblem) {
    if (!silent) $("pensionSimulationStatus").textContent = `${scheduleProblem.scenario.name}: ${scheduleProblem.issue}`;
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
  ["fundName", "fundPensionId", "fundAmount", "fundAccount", "fundComments"].forEach((id) => { $(id).value = ""; });
  renderFundAccountOwners();
  updateFundActionStates();
}

function updateFundActionStates() {
  const button = $("saveFund");
  if (!button) return;
  button.disabled = !valueOf("fundPensionId") || Number(valueOf("fundAmount") || 0) <= 0 || !valueOf("fundAccount");
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
  if (!valueOf("fundAccount")) {
    $("fundStatus").textContent = state.language === "he" ? "יש לבחור חשבון חיסכון ארוך טווח" : "Choose a long-term account";
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
  renderFundAccountOwners();
  $("editFundStatus").textContent = [fund.kind, fund.fund_name, fund.pension_id].filter(Boolean).join(" · ");
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
  if (!valueOf("editFundAccount")) {
    $("editFundStatus").textContent = state.language === "he" ? "יש לבחור חשבון חיסכון ארוך טווח" : "Choose a long-term account";
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
      comments: valueOf("editFundComments"),
    }),
  });
  $("fundStatus").textContent = "Fund updated";
  $("editFundStatus").textContent = "Fund updated";
  closeModal($("fundEditModal"));
  state.editingFundId = "";
  await loadFunds();
  await loadReports();
}

function portfolioItemBySecurity(symbol, stockMarket) {
  const cleanSymbol = String(symbol || "").trim().toUpperCase();
  const cleanMarket = String(stockMarket || "").trim().toUpperCase();
  return (state.allPortfolioItems || []).find((item) => {
    const holding = item.holding || {};
    return String(holding.symbol || "").trim().toUpperCase() === cleanSymbol
      && holdingMarketKey(holding).toUpperCase() === cleanMarket;
  });
}

function openIndustryClassification(symbol, stockMarket, returnFocus) {
  const item = portfolioItemBySecurity(symbol, stockMarket);
  if (!item) return;
  const holding = item.holding || {};
  const asset = String(holding.asset_class || "").toUpperCase();
  const instrument = String(holding.asset_sub_class || "").toUpperCase();
  if (asset === "BOND" || instrument === "BOND") return;
  const catalog = [...new Set(state.industryCatalog || [])]
    .sort((left, right) => optionLabel(left).localeCompare(optionLabel(right), state.language === "he" ? "he" : "en"));
  const current = String(item.industry || "").trim();
  const provider = String(item.provider_industry || holding.sector || "").trim();
  state.industryClassificationTarget = {
    symbol: String(holding.symbol || symbol).trim(),
    stockMarket: holdingMarketKey(holding),
  };
  $("industryClassificationSecurity").textContent = `${holding.symbol}${holding.name ? ` · ${holding.name}` : ""}`;
  $("industryClassificationProvider").textContent = provider
    ? `${optionLabel("Provider classification")}: ${optionLabel(provider)}`
    : optionLabel("The provider did not classify this security.");
  $("industryClassificationSelect").innerHTML = [
    `<option value="">${esc(optionLabel("Choose an industry"))}</option>`,
    ...catalog.map((industry) => `<option value="${esc(industry)}">${esc(optionLabel(industry))}</option>`),
  ].join("");
  $("industryClassificationSelect").value = catalog.includes(current) ? current : "";
  $("industryClassificationStatus").textContent = "";
  $("removeIndustryClassification").hidden = item.industry_source !== "manual";
  openModal("industryClassificationModal", returnFocus);
  applyRolePermissions($("industryClassificationModal"));
  requestAnimationFrame(() => $("industryClassificationSelect")?.focus());
}

async function saveIndustryClassification() {
  const target = state.industryClassificationTarget;
  if (!target) return;
  const industry = valueOf("industryClassificationSelect");
  if (!industry) {
    $("industryClassificationStatus").textContent = optionLabel("Choose an industry before saving.");
    $("industryClassificationSelect").focus();
    return;
  }
  const button = $("saveIndustryClassification");
  button.disabled = true;
  $("industryClassificationStatus").textContent = optionLabel("Saving classification");
  try {
    await api("/api/local/security-industry-overrides", {
      method: "PUT",
      body: JSON.stringify({ symbol: target.symbol, stock_market: target.stockMarket, industry }),
    });
    closeModal($("industryClassificationModal"));
    await loadPortfolio();
    $("status").textContent = optionLabel("Industry classification saved");
  } finally {
    button.disabled = false;
  }
}

async function removeIndustryClassification() {
  const target = state.industryClassificationTarget;
  if (!target) return;
  const button = $("removeIndustryClassification");
  button.disabled = true;
  $("industryClassificationStatus").textContent = optionLabel("Restoring provider classification");
  try {
    const params = new URLSearchParams({ stock_market: target.stockMarket });
    await api(`/api/local/security-industry-overrides/${encodeURIComponent(target.symbol)}?${params}`, { method: "DELETE" });
    closeModal($("industryClassificationModal"));
    await loadPortfolio();
    $("status").textContent = optionLabel("Provider classification restored");
  } finally {
    button.disabled = false;
  }
}

const EXPOSURE_FOCUS_LABELS = {
  money_market: "Money market", government_bond: "Government bonds",
  investment_grade_bond: "Investment grade bonds", high_yield_bond: "High yield bonds",
  broad_equity: "Broad equities", single_country_equity: "Single-country equities",
  sector_equity: "Sector equities", multi_asset: "Mixed assets", real_estate: "Real estate",
  commodity: "Commodities", derivative: "Derivatives / leverage", other: "Other assets",
};

const EXPOSURE_CURRENCIES = ["ILS", "USD", "EUR", "GBP", "INR", "JPY", "CHF", "CAD", "AUD"];

function securityExposureCurrencyOptions(selected = "") {
  return [...new Set([...EXPOSURE_CURRENCIES, selected].filter(Boolean))]
    .map((code) => `<option value="${esc(code)}"${code === selected ? " selected" : ""}>${esc(currencyDisplayLabel(code))}</option>`).join("");
}

function securityExposureCurrencyRow(currency = "", percent = "") {
  return `<div class="exposure-currency-row">
    <label class="field"><span>${esc(optionLabel("Currency"))}</span><select data-exposure-currency><option value="">${esc(optionLabel("Choose currency"))}</option>${securityExposureCurrencyOptions(currency)}</select></label>
    <label class="field"><span>${esc(optionLabel("Exposure %"))}</span><input data-exposure-percent type="number" min="0.1" max="100" step="0.1" value="${esc(percent)}" /></label>
    <button class="secondary compact-button" type="button" data-remove-exposure-currency aria-label="${esc(optionLabel("Remove currency"))}">×</button>
  </div>`;
}

function updateSecurityExposureCurrencyState() {
  const known = $("securityExposureFxBasis").value !== "unknown";
  $("addSecurityExposureCurrency").disabled = !known || !canWrite();
  $("securityExposureCurrencies").querySelectorAll("select, input, button").forEach((field) => { field.disabled = !known || !canWrite(); });
  const total = known ? [...$("securityExposureCurrencies").querySelectorAll("[data-exposure-percent]")]
    .reduce((value, input) => value + Number(input.value || 0), 0) : 0;
  $("securityExposureUnknown").textContent = `${optionLabel("Unclassified currency exposure")}: ${fmt(Math.max(0, 100 - total), 1)}%`;
}

function openSecurityExposure(symbol, stockMarket, returnFocus) {
  const item = portfolioItemBySecurity(symbol, stockMarket);
  if (!item) return;
  const holding = item.holding || {};
  const profile = item.exposure_profile || {};
  state.securityExposureTarget = { symbol: holding.symbol, stockMarket: String(holding.stock_market || "").trim() };
  $("securityExposureSecurity").textContent = `${holding.symbol}${holding.name ? ` · ${holding.name}` : ""}`;
  $("securityExposureTradingCurrency").textContent = `${optionLabel("Trading currency")}: ${currencyDisplayLabel(holding.currency)}`;
  $("securityExposureFocus").innerHTML = `<option value="">${esc(optionLabel("Unknown"))}</option>`
    + Object.entries(EXPOSURE_FOCUS_LABELS).map(([key, label]) => `<option value="${esc(key)}">${esc(optionLabel(label))}</option>`).join("");
  $("securityExposureFocus").value = profile.asset_focus || "";
  $("securityExposureGeography").value = profile.geography || "";
  $("securityExposureSector").value = profile.sector_exposure || "";
  $("securityExposureFxBasis").value = profile.fx_basis || "unknown";
  $("securityExposureFxReference").innerHTML = `<option value="">${esc(optionLabel("Unknown"))}</option>${securityExposureCurrencyOptions(profile.fx_reference_currency || "")}`;
  $("securityExposureFxReference").value = profile.fx_reference_currency || "";
  $("securityExposureCurrencies").innerHTML = (profile.currency_exposures || [])
    .map((row) => securityExposureCurrencyRow(row.currency, row.percent)).join("");
  $("securityExposureFxLimit").value = profile.fx_policy_limit_percent ?? "";
  setDateField("securityExposureDate", profile.as_of || "");
  $("securityExposureSource").value = profile.source_note || "";
  $("securityExposureStatus").textContent = "";
  $("removeSecurityExposure").hidden = !item.exposure_profile;
  updateSecurityExposureCurrencyState();
  openModal("securityExposureModal", returnFocus);
  applyRolePermissions($("securityExposureModal"));
  requestAnimationFrame(() => $("securityExposureFocus")?.focus());
}

async function saveSecurityExposure() {
  const target = state.securityExposureTarget;
  if (!target) return;
  const basis = $("securityExposureFxBasis").value;
  const rows = basis === "unknown" ? [] : [...$("securityExposureCurrencies").querySelectorAll(".exposure-currency-row")];
  const currencyExposures = rows.map((row) => ({
    currency: row.querySelector("[data-exposure-currency]").value,
    percent: Number(row.querySelector("[data-exposure-percent]").value),
  }));
  const total = sum(currencyExposures.map((row) => row.percent));
  if (currencyExposures.some((row) => !row.currency || !Number.isFinite(row.percent) || row.percent <= 0) || total > 100.00001) {
    $("securityExposureStatus").textContent = optionLabel("Enter unique currencies with positive percentages totaling at most 100%.");
    return;
  }
  const enteredDate = valueOf("securityExposureDate");
  const asOf = parseDateInput(enteredDate);
  if (enteredDate && !asOf) {
    $("securityExposureStatus").textContent = optionLabel("Enter a valid date as dd/mm/yyyy.");
    return;
  }
  if (basis === "reported" && currencyExposures.length && !asOf) {
    $("securityExposureStatus").textContent = optionLabel("Reported currency exposures require an information date.");
    return;
  }
  const profile = {
    asset_focus: valueOf("securityExposureFocus"),
    geography: valueOf("securityExposureGeography"),
    sector_exposure: valueOf("securityExposureSector"),
    fx_basis: basis,
    fx_reference_currency: valueOf("securityExposureFxReference"),
    currency_exposures: currencyExposures,
    fx_policy_limit_percent: valueOf("securityExposureFxLimit") || null,
    as_of: asOf,
    source_note: valueOf("securityExposureSource"),
  };
  if (profile.asset_focus === "single_country_equity" && !profile.geography) {
    $("securityExposureStatus").textContent = optionLabel("Choose an underlying country for a single-country fund.");
    $("securityExposureGeography").focus();
    return;
  }
  if (profile.asset_focus === "sector_equity" && !profile.sector_exposure) {
    $("securityExposureStatus").textContent = optionLabel("Choose an underlying sector for a sector fund.");
    $("securityExposureSector").focus();
    return;
  }
  const button = $("saveSecurityExposure");
  button.disabled = true;
  $("securityExposureStatus").textContent = optionLabel("Saving exposure profile");
  try {
    await api("/api/local/security-exposure-profiles", {
      method: "PUT", body: JSON.stringify({ symbol: target.symbol, stock_market: target.stockMarket, profile }),
    });
    closeModal($("securityExposureModal"));
    await loadPortfolio();
    $("status").textContent = optionLabel("Exposure profile saved");
  } finally {
    button.disabled = false;
  }
}

async function removeSecurityExposure() {
  const target = state.securityExposureTarget;
  if (!target) return;
  const button = $("removeSecurityExposure");
  button.disabled = true;
  try {
    const params = new URLSearchParams({ stock_market: target.stockMarket });
    await api(`/api/local/security-exposure-profiles/${encodeURIComponent(target.symbol)}?${params}`, { method: "DELETE" });
    closeModal($("securityExposureModal"));
    await loadPortfolio();
    $("status").textContent = optionLabel("Exposure profile removed");
  } finally {
    button.disabled = false;
  }
}

let portfolioEnrichmentRetryTimer = null;
const PORTFOLIO_ENRICHMENT_RETRY_MS = 1500;

async function loadPortfolio({ refresh = false, enrichmentRetry = 0 } = {}) {
  const version = (state.portfolioLoadVersion || 0) + 1;
  state.portfolioLoadVersion = version;
  clearTimeout(portfolioEnrichmentRetryTimer);
  portfolioEnrichmentRetryTimer = null;
  const retry = () => {
    portfolioEnrichmentRetryTimer = setTimeout(() => {
      portfolioEnrichmentRetryTimer = null;
      if (version !== state.portfolioLoadVersion) return;
      loadPortfolio({ enrichmentRetry: enrichmentRetry + 1 }).catch(() => {});
    }, Math.min(PORTFOLIO_ENRICHMENT_RETRY_MS * (1 + Math.floor(enrichmentRetry / 10)), 15000));
  };
  $("status").textContent = refresh ? "Refreshing analytics" : "Preparing dashboard";
  setLoading(true, refresh ? "Refreshing portfolio analytics" : "Loading portfolio analytics");
  appLog("portfolio.load.start", { refresh });
  try {
    const trendParams = new URLSearchParams({
      date_from: HISTORY_START_DATE,
      date_to: todayString(),
    });
    const portfolioPath = refresh ? "/api/portfolio?refresh=true" : "/api/portfolio";
    const [data, trend, fxData, accountData, transactionData, classificationData] = await Promise.all([
      api(portfolioPath),
      api(`/api/local/account-trends?${trendParams}`),
      api("/api/fx").catch(() => ({ quotes: [] })),
      api("/api/local/accounts"),
      api("/api/local/securities"),
      api("/api/local/security-industry-overrides"),
    ]);
    if (version !== state.portfolioLoadVersion) return;
    state.portfolioRefreshPending = Boolean(data.refresh_pending);
    setCoreFxRates(fxData);
    state.localAccounts = accountData.items || [];
    state.localTransactions = transactionData.items || [];
    state.industryClassifications = classificationData.items || [];
    state.industryCatalog = classificationData.industries || [];
    const allItems = data.items || [];
    state.allPortfolioItems = allItems;
    state.items = portfolioItems(allItems);
    state.portfolioReady = true;
    state.accountTrend = {
      ...trend,
      accounts: (trend.accounts || []).filter((entry) => !isEquityCompAccount(entry.account)),
    };
    populateOptions(allItems);
    const progress = data.refresh_progress;
    const refreshText = data.refresh_pending && progress?.total
      ? `${t("Updating analytics")}: ${progress.completed}/${progress.total} ${t("securities completed")}`
      : data.refresh_state === "failed" && progress?.failed
        ? `${t("Update finished")}: ${progress.completed - progress.failed}/${progress.total} ${t("securities updated")} · ${progress.failed} ${t("updates failed. Use Refresh to retry.")}`
      : t(data.refresh_pending ? "Updating analytics in the background" : data.refresh_state === "failed" ? "Financial data could not be updated. Use Refresh to retry." : "Analytics updated");
    $("status").textContent = `${state.items.length} ${t("portfolio positions")} · ${refreshText}`;
    renderPortfolio(state.items);
    if (!$("macroScenarioModal")?.hidden) renderMacroScenario();
    if (hasActivePortfolioFilter(state.portfolioFilterCriteria)) {
      const matches = filterPortfolioItems(state.allPortfolioItems, state.portfolioFilterCriteria);
      renderRows(matches);
      $("status").textContent = `${matches.length} ${t("portfolio positions matched")} · ${refreshText}`;
    }
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
    if (data.refresh_pending) retry();
  } catch (error) {
    if (version !== state.portfolioLoadVersion) return;
    if (version === state.portfolioLoadVersion && state.portfolioRefreshPending) {
      $("status").textContent = t("Connection interrupted. Retrying the analytics update.");
      retry();
    }
    throw error;
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
      instrument_types: ["STOCK", "ETF", "MUTUALFUND", "BOND", "OPTION", "FUTURE", "EMPLOYEE_STOCK_OPTION", "PRIVATE_STOCK", "STOCK_OPTION"],
      option_types: ["CALL", "PUT"],
      issuer_listing_statuses: ["PRIVATE", "PUBLIC"],
    };
  }
  populateStaticOptions();
}

function applyFilter() {
  state.portfolioFilterCriteria = criteriaFromForm();
  const matches = filterPortfolioItems(state.allPortfolioItems, state.portfolioFilterCriteria);
  $("status").textContent = `${matches.length} portfolio positions matched`;
  renderRows(matches);
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
  const metric = (state.alertOptions.metrics || []).find((item) => item.key === metricKey) || {
    key: metricKey,
    label: metricKey.replaceAll("_", " "),
    unit: "",
    digits: 2,
  };
  const localized = ALERT_METRIC_LOCALIZATIONS[state.language]?.[metricKey];
  return localized ? { ...metric, ...localized, guidance: { ...metric.guidance, ...localized.guidance } } : metric;
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
    (result[group] ||= []).push(alertMetric(metric.key));
    return result;
  }, {});
  if (!Object.keys(groups).length) return '<option value="">Loading metrics</option>';
  return Object.entries(groups).map(([group, metrics]) => `
    <optgroup label="${esc(group)}">
      ${metrics.map((metric) => `<option value="${esc(metric.key)}"${metric.key === selected ? " selected" : ""}>${esc(metric.label)}${metric.unit ? ` (${esc(metric.unit)})` : ""}</option>`).join("")}
    </optgroup>
  `).join("");
}

function alertMetricGuidance(metricKey) {
  return alertMetric(metricKey).guidance || {
    description: "The latest available value for this financial measure.",
    example: "Choose a threshold that fits your research question.",
    use: "Use it with other conditions to narrow the review list.",
  };
}

function alertConditionGuidanceHtml(metricKey) {
  const guidance = alertMetricGuidance(metricKey);
  const labels = state.language === "he"
    ? { measures: "מה המדד מודד:", example: "דוגמה:", tells: "מה ניתן ללמוד ממנו:" }
    : { measures: "What it measures:", example: "Example:", tells: "What it tells you:" };
  return `<b>${labels.measures}</b> ${esc(guidance.description)} <b>${labels.example}</b> ${esc(guidance.example)} <b>${labels.tells}</b> ${esc(guidance.use)}`;
}

function alertConditionGuidanceTooltip(metricKey) {
  const metric = alertMetric(metricKey);
  const guidance = alertMetricGuidance(metricKey);
  const labels = state.language === "he"
    ? { example: "דוגמה:", tells: "מה ניתן ללמוד ממנו:" }
    : { example: "Example:", tells: "What it tells you:" };
  return `${metric.label}. ${guidance.description} ${labels.example} ${guidance.example}. ${labels.tells} ${guidance.use}`;
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
  const conditionCount = state.alertConditions.length;
  const count = $("alertConditionCount");
  if (count) count.textContent = `${conditionCount} ${t(conditionCount === 1 ? "condition" : "conditions")}`;
  $("alertConditions").innerHTML = state.alertConditions.map((condition, index) => `
    <div class="signal-condition-row" data-alert-condition="${index}">
      <div class="signal-condition-metric"><label for="alertConditionMetric${index}"><span>Financial measure</span></label><div class="signal-condition-control"><select id="alertConditionMetric${index}" data-alert-condition-metric>${alertMetricOptions(condition.metric)}</select><button class="ux-tooltip signal-condition-help" type="button" aria-label="Explain ${esc(alertMetric(condition.metric).label)}" data-tooltip="${esc(alertConditionGuidanceTooltip(condition.metric))}">?</button></div></div>
      <label><span>Comparison</span><select data-alert-condition-operator>${operatorOptions.map((operator) => `<option value="${esc(operator.key)}"${operator.key === condition.operator ? " selected" : ""}>${esc(operator.label)}</option>`).join("")}</select></label>
      <label><span>Value</span><input data-alert-condition-value type="number" step="any" value="${esc(condition.value)}" inputmode="decimal" /></label>
      <button class="icon-button signal-remove-condition" type="button" data-remove-alert-condition="${index}" aria-label="Remove condition" title="Remove condition">×</button>
      <p class="signal-condition-guidance">${alertConditionGuidanceHtml(condition.metric)}</p>
    </div>
  `).join("");
}

function updateAlertConditionGuidance(row) {
  const metricKey = row.querySelector("[data-alert-condition-metric]")?.value || "";
  const metric = alertMetric(metricKey);
  const help = row.querySelector(".signal-condition-help");
  if (help) {
    help.setAttribute("aria-label", `Explain ${metric.label}`);
    help.dataset.tooltip = alertConditionGuidanceTooltip(metricKey);
  }
  const guidance = row.querySelector(".signal-condition-guidance");
  if (guidance) guidance.innerHTML = alertConditionGuidanceHtml(metricKey);
}

function resetAlertForm() {
  state.editingAlertId = "";
  state.alertConditions = [{ metric: "dividend_yield_percent", operator: ">", value: 2.5 }];
  $("alertName").value = "";
  $("alertSignal").value = "buy";
  $("alertMatchMode").value = "all";
  $("alertEnabled").checked = true;
  $("saveAlert").textContent = t("Save rule & start another");
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

async function openAlertSignalChart(symbol, button) {
  const normalized = cleanSecuritySymbol(symbol);
  const item = (state.allPortfolioItems || state.items || []).find((candidate) => cleanSecuritySymbol((candidate.holding || {}).symbol) === normalized);
  const holding = item?.holding || {};
  await openSecurityDetail({
    securityDetailSymbol: normalized,
    securityDetailMarketKey: holdingMarketKey(holding),
    securityDetailStockMarket: stockMarketDisplay(holding, holdingMarketKey(holding), item?.exchange),
    securityDetailProvider: dataProviderDisplay(item || {}, holding, holdingMarketKey(holding)),
    securityDetailAsset: holding.asset_class || "EQUITY",
    securityDetailCurrency: holding.currency || "USD",
    securityDetailLocation: holding.country || holding.location || "USA",
  }, button);
}

function alertRunStatusText(status) {
  const value = String(status || "completed");
  if (value === "Running" || value === "running") return t("Running…");
  if (value === "completed") return t("Completed");
  if (value === "failed") return t("Failed");
  if (value === "Not run") return t("Not run");
  if (value === "No matches") return t("No matches");
  const match = value.match(/^(\d+) match(?:es)?$/);
  if (match) return `${fmt(Number(match[1]), 0)} ${t(Number(match[1]) === 1 ? "match" : "matches")}`;
  if (value.startsWith("Rule check failed:")) return t("Rule check failed.");
  return t(value);
}

function alertRunProgressText(progress) {
  const value = progress || {};
  const completed = Number(value.completed || 0);
  const total = Number(value.total || 0);
  const label = {
    starting: t("Starting…"),
    loading_saved_data: t("Loading saved portfolio data…"),
    loading_rule_data: t("Loading rule data…"),
    evaluating: t("Evaluating rule…"),
  }[String(value.phase || "starting")] || t("Running…");
  return total ? `${label} ${fmt(completed, 0)}/${fmt(total, 0)}` : label;
}

function renderAlerts(data) {
  const wasRunning = alertRunIsActive(state.alertData);
  state.alertData = data;
  state.alertOptions = data.options || state.alertOptions;
  if (!state.alertConditions.length) resetAlertForm();
  else renderAlertConditions();

  const rules = data.rules || [];
  const signals = data.active_signals || [];
  const runs = data.runs || [];
  $("alertActiveSummary").textContent = fmt(signals.length, 0);
  $("alertRuleSummary").textContent = `${rules.filter((rule) => rule.enabled).length} of ${rules.length}`;
  $("alertScheduleSummary").textContent = data.schedule?.next_run ? formatDateTime(data.schedule.next_run) : t("Not scheduled");
  $("alertRunSummary").textContent = runs[0]?.run_at
    ? `${runs[0].status === "failed" ? `${t("Failed")} · ` : ""}${formatDateTime(runs[0].run_at)}`
    : t("Not run");

  $("alertsSignals").innerHTML = signals.length ? signals.map((signal) => {
    const signalType = ["buy", "sell", "watch"].includes(signal.signal) ? signal.signal : "watch";
    const reasons = (signal.reasons || []).map((reason) => `<li>${esc(alertReasonText(reason))}</li>`).join("");
    const missing = (signal.missing || []).filter(Boolean);
    const missingRuleMetrics = (signal.missing_metrics || []).map((metric) => alertMetric(metric).label);
    return `<article class="signal-card signal-match-card signal-${esc(signalType)}">
      <div class="signal-card-head">
        <div><span class="signal-badge">${esc(t(`${signalType[0].toUpperCase()}${signalType.slice(1)} signal`))}</span><h5>${esc(signal.symbol)} <small>${esc(signal.name || "")}</small></h5></div>
        <span class="signal-time">${esc(formatDateTime(signal.matched_at))}</span>
      </div>
      <p class="signal-rule-name">Matched “${esc(signal.rule_name || "Rule")}”</p>
      ${reasons ? `<ul class="signal-reasons">${reasons}</ul>` : ""}
      ${missingRuleMetrics.length ? `<p class="signal-missing">Rule data unavailable: ${esc(missingRuleMetrics.join(", "))}</p>` : ""}
      ${missing.length ? `<p class="signal-missing">Some provider data is unavailable: ${esc(missing.join(", "))}</p>` : ""}
      <div class="signal-card-actions">
        <button class="secondary compact-button" type="button" data-alert-chart="${esc(signal.symbol)}">${t("Chart")}</button>
        <button type="button" data-investigate-signal="${esc(signal.symbol)}">Investigate &amp; score</button>
      </div>
    </article>`;
  }).join("") : '<div class="empty signal-empty">No current matches. Run the rules now or wait for the next daily check.</div>';

  $("alertsList").innerHTML = rules.length ? rules.map((rule) => {
    const conditions = rule.conditions || [];
    const joiner = rule.match_mode === "any" ? ` ${t("or")} ` : ` ${t("and")} `;
    const conditionText = conditions.length ? conditions.map(alertConditionText).join(joiner) : "This older rule needs a condition before it can run.";
    const matchCount = (rule.last_matches || []).length;
    const isRunning = rule.last_status === "Running";
    return `<article class="signal-card saved-rule-card${rule.enabled ? "" : " is-disabled"}${isRunning ? " is-running" : ""}">
      <div class="signal-card-head">
        <div><span class="signal-badge signal-${esc(rule.signal || "watch")}">${esc(rule.signal || "watch")}</span><h5>${esc(rule.name)}</h5></div>
        <span class="rule-state">${isRunning ? t("Running…") : rule.enabled ? t("Daily") : t("Paused")}</span>
      </div>
      <p>${esc(conditionText)}</p>
      <div class="signal-rule-meta"><span>${isRunning ? esc(alertRunProgressText(rule.last_progress)) : esc(alertRunStatusText(rule.last_status || "Not run"))}</span><span>${isRunning ? t("Results will appear automatically.") : `${fmt(matchCount, 0)} ${t(matchCount === 1 ? "current match" : "current matches")}`}</span></div>
      <div class="signal-card-actions">
        <button class="secondary compact-button" type="button" data-run-alert="${esc(rule.id)}"${isRunning ? " disabled" : ""}>${isRunning ? t("Running…") : t("Run now")}</button>
        <button class="secondary compact-button" type="button" data-edit-alert="${esc(rule.id)}">${t("Edit")}</button>
        <button class="secondary compact-button" type="button" data-toggle-alert="${esc(rule.id)}">${rule.enabled ? t("Pause") : t("Enable")}</button>
        <button class="danger compact-button" type="button" data-delete-alert="${esc(rule.id)}">${t("Remove")}</button>
      </div>
    </article>`;
  }).join("") : '<div class="empty signal-empty">No saved rules. The example above starts with dividend yield &gt; 2.5%.</div>';

  $("alertRunHistory").innerHTML = runs.length ? runs.slice(0, 12).map((run) => {
    const providerErrors = run.metadata?.provider_errors?.length || 0;
    return `<article class="signal-card signal-run-card${run.status === "failed" ? " is-failed" : ""}">
      <div class="signal-card-head"><h5>${esc(formatDateTime(run.run_at))}</h5><span class="run-state">${esc(alertRunStatusText(run.status))}</span></div>
      ${run.error ? `<p class="signal-missing">${esc(alertRunStatusText(run.error))}</p>` : ""}
      ${run.status === "running" ? `<p class="signal-run-progress">${esc(alertRunProgressText(run.progress))}</p>` : ""}
      <div class="signal-run-stats"><span><b>${fmt(run.evaluated_symbols || 0, 0)}</b> ${t("stocks checked")}</span><span><b>${fmt(run.matched_signals || 0, 0)}</b> ${t("matches")}</span><span><b>${fmt(providerErrors, 0)}</b> ${t("data errors")}</span></div>
    </article>`;
  }).join("") : '<div class="empty signal-empty">No run history yet.</div>';
  if (wasRunning && !alertRunIsActive(data)) {
    const latestRun = runs[0];
    $("alertStatus").textContent = latestRun?.status === "failed" ? t("Rule check failed.") : t("Rule check finished.");
  } else if ($("alertStatus").textContent === t("Connection interrupted. Retrying run updates…")) {
    $("alertStatus").textContent = alertRunIsActive(data) ? t("Running your saved portfolio rule…") : "";
  }
  scheduleAlertRefresh();
}

function alertRunIsActive(data) {
  return (data?.rules || []).some((rule) => String(rule.last_status).toLowerCase() === "running")
    || (data?.runs || []).some((run) => run.status === "running");
}

function scheduleAlertRefresh() {
  if (state.alertRefreshTimer) clearTimeout(state.alertRefreshTimer);
  state.alertRefreshTimer = null;
  if (!alertRunIsActive(state.alertData)) return;
  state.alertRefreshTimer = window.setTimeout(async () => {
    state.alertRefreshTimer = null;
    try {
      await loadAlerts();
    } catch {
      $("alertStatus").textContent = t("Connection interrupted. Retrying run updates…");
      scheduleAlertRefresh();
    }
  }, 1500);
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
    $("alertStatus").textContent = t("Rule saved. Start the next rule above, or add more conditions before saving it.");
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

async function runAlertRule(ruleId, button) {
  const rule = (state.alertData?.rules || []).find((item) => item.id === ruleId);
  if (!rule) return;
  if (button) {
    button.disabled = true;
    button.textContent = t("Running…");
    button.closest(".saved-rule-card")?.classList.add("is-running");
  }
  $("alertStatus").textContent = `Checking “${rule.name}” now…`;
  try {
    const result = await api(`/api/alerts/${encodeURIComponent(ruleId)}/run`, { method: "POST", body: "{}" });
    renderAlerts(result.state);
    $("alertStatus").textContent = result.started ? t("Running your saved portfolio rule…") : t("This rule is already running.");
  } catch (error) {
    $("alertStatus").textContent = `Error: ${error.message}`;
  }
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

function macroPercent(value, digits = 1) {
  return value === null || value === undefined ? "∅" : `${fmt(Number(value) * 100, digits)}%`;
}

function setMacroProbabilityInput(id, value) {
  const input = $(id);
  if (!input || document.activeElement === input) return;
  input.value = value === null || value === undefined ? "" : String(Number((value * 100).toFixed(4)));
}

function macroLeafNodes(result) {
  const parents = new Set(result.nodes.map((entry) => entry.parent).filter(Boolean));
  return result.nodes.filter((entry) => !parents.has(entry.id));
}

function macroMostLikelyEnd(result, direction) {
  return macroLeafNodes(result)
    .filter((entry) => entry.direction === direction)
    .sort((left, right) => right.conditional - left.conditional)[0] || null;
}

function macroScenarioFallback(result) {
  const labels = Object.fromEntries(result.nodes.map((entry) => [entry.id, entry.label]));
  return `<div class="macro-network-fallback">
    <div class="macro-network-trigger"><b>${esc(optionLabel(result.triggerLabel))}</b><span>${esc(optionLabel("Trigger P"))}: ${esc(macroPercent(result.triggerProbability))}</span></div>
    ${result.nodes.map((entry) => `<div class="macro-network-edge ${esc(entry.direction)}">
      <span>${esc(optionLabel(labels[entry.parent] || result.triggerLabel))}</span>
      <b>→ P=${esc(macroPercent(entry.probability))} →</b>
      <span>${esc(optionLabel(entry.label))} · ${esc(optionLabel("Path P"))} ${esc(macroPercent(entry.conditional))}</span>
    </div>`).join("")}
  </div>`;
}

let macroScenarioDiagramSequence = 0;

function macroMermaidText(result) {
  const clean = (value) => optionLabel(value).replace(/["<>]/g, "").replace(/\n/g, " ");
  const trigger = result.triggerProbability === null
    ? optionLabel("Set trigger priors")
    : macroPercent(result.triggerProbability);
  const lines = [
    "flowchart LR",
    `trigger["${clean(result.triggerLabel)}<br/>P(trigger) = ${clean(trigger)}"]`,
  ];
  result.nodes.forEach((entry) => {
    lines.push(`${entry.id}["${clean(entry.label)}<br/>P(path) = ${macroPercent(entry.conditional)}"]`);
    lines.push(`${entry.parent || "trigger"} -->|"P = ${macroPercent(entry.probability)}"| ${entry.id}`);
    lines.push(`class ${entry.id} ${entry.direction}`);
  });
  lines.push("classDef positive fill:#123524,stroke:#6ee787,color:#f4fff7");
  lines.push("classDef negative fill:#3b1821,stroke:#ff6b88,color:#fff4f6");
  lines.push("classDef mixed fill:#332b14,stroke:#f0d86a,color:#fffbea");
  lines.push("classDef trigger fill:#183b56,stroke:#64d2ff,color:#f4fbff");
  lines.push("class trigger trigger");
  return lines.join("\n");
}

async function renderMacroScenarioDiagram(result) {
  const diagram = $("macroScenarioDiagram");
  if (!diagram) return;
  diagram.innerHTML = macroScenarioFallback(result);
  if (!window.mermaid) return;
  try {
    window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "dark", flowchart: { htmlLabels: true } });
    macroScenarioDiagramSequence += 1;
    const sequence = macroScenarioDiagramSequence;
    const rendered = await window.mermaid.render(`macroScenarioMap${sequence}`, macroMermaidText(result));
    if (sequence !== macroScenarioDiagramSequence || state.macroScenarioSettings?.selected !== result.id) return;
    diagram.innerHTML = rendered.svg;
    rendered.bindFunctions?.(diagram);
  } catch (error) {
    appWarn("macro_scenario.diagram_fallback", { message: error?.message || "Diagram render failed" });
  }
}

function renderMacroPriorStatus() {
  const model = window.PortfolioScenarioModel;
  const settings = state.macroScenarioSettings;
  if (!model || !settings || !$("macroPriorStatus")) return;
  setMacroProbabilityInput("macroPriorIncrease", settings.priors.increase);
  setMacroProbabilityInput("macroPriorDecrease", settings.priors.decrease);
  setMacroProbabilityInput("macroPriorUnchanged", settings.priors.unchanged);
  setMacroProbabilityInput("macroLocalTrigger", settings.localTrigger);
  const prior = model.priorStatus(settings);
  const invalidTotal = prior.complete && !prior.valid;
  ["macroPriorIncrease", "macroPriorDecrease", "macroPriorUnchanged"].forEach((id) => {
    $(id)?.setAttribute("aria-invalid", String(invalidTotal));
  });
  const status = !prior.complete
    ? optionLabel("Enter all three Fed priors to calculate absolute probabilities.")
    : !prior.valid
      ? `${optionLabel("Fed priors total")} ${macroPercent(prior.total)}. ${optionLabel("They must total 100%.")}`
      : settings.localTrigger === null
        ? optionLabel("Fed priors are valid. Set the domestic-shock probability to complete the unchanged-rate scenario.")
        : optionLabel("Trigger priors are valid. Absolute probabilities are enabled.");
  $("macroPriorStatus").textContent = status;
  $("macroPriorStatus").classList.toggle("negative", invalidTotal);
  $("macroPriorStatus").classList.toggle("positive", prior.valid && settings.localTrigger !== null);
}

function renderMacroScenarioOverview() {
  const model = window.PortfolioScenarioModel;
  const settings = state.macroScenarioSettings;
  if (!model || !settings) return;
  const results = model.SCENARIOS.map((definition) => model.calculateScenario(definition.id, settings));
  $("macroScenarioTabs").innerHTML = results.map((result) => {
    const active = result.id === settings.selected;
    return `<button class="macro-scenario-tab ${active ? "active" : ""}" type="button" role="tab" aria-selected="${String(active)}" data-macro-scenario="${esc(result.id)}">
      <b>${esc(optionLabel(result.label))}</b>
      <span>${esc(optionLabel("Headline path"))}: ${esc(macroPercent(result.headline?.conditional))}</span>
    </button>`;
  }).join("");
  $("macroScenarioOverview").innerHTML = results.map((result) => `<article class="macro-overview-card ${esc(result.id)}">
    <span>${esc(optionLabel(result.label))}</span>
    <b>${esc(macroPercent(result.headline?.conditional))}</b>
    <small>${esc(optionLabel("Conditional headline outcome"))}</small>
    <em>${result.headline?.absolute === null ? esc(optionLabel("Set trigger priors for absolute P")) : `${esc(optionLabel("Absolute P"))} ${esc(macroPercent(result.headline.absolute))}`}</em>
  </article>`).join("");
}

function renderMacroTriggerLibrary() {
  const model = window.PortfolioScenarioModel;
  const settings = state.macroScenarioSettings;
  const library = $("macroTriggerLibrary");
  if (!model || !settings || !library) return;
  const groups = model.TRIGGER_MODULES.reduce((result, definition) => {
    (result[definition.category] ||= []).push(definition);
    return result;
  }, {});
  library.innerHTML = Object.entries(groups).map(([category, definitions]) => {
    const categoryId = `macro-trigger-${category.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;
    return `<section class="macro-trigger-group" aria-labelledby="${esc(categoryId)}">
      <h4 id="${esc(categoryId)}">${esc(optionLabel(category))}</h4>
      <div class="macro-trigger-grid">
        ${definitions.map((definition) => {
          const selected = settings.selected === definition.id;
          const prior = settings.triggerPriors[definition.id];
          const result = model.calculateScenario(definition.id, settings);
          return `<article class="macro-trigger-card${selected ? " active" : ""}">
            <button type="button" data-macro-scenario="${esc(definition.id)}" aria-pressed="${String(selected)}">
              <b>${esc(optionLabel(definition.label))}</b>
              <small>${esc(optionLabel(definition.triggerLabel))}</small>
              <span>${esc(optionLabel("Headline path"))}: ${esc(macroPercent(result.headline?.conditional))}</span>
            </button>
            <label><span>${esc(optionLabel("Trigger P"))}</span><span class="probability-input compact"><input type="number" min="0" max="100" step="0.1" inputmode="decimal" value="${prior === null ? "" : esc(Number((prior * 100).toFixed(4)))}" data-macro-trigger-prior="${esc(definition.id)}" aria-label="${esc(`${optionLabel("Trigger probability")}: ${optionLabel(definition.label)}`)}" placeholder="${esc(optionLabel("Set prior"))}" /><b>%</b></span></label>
          </article>`;
        }).join("")}
      </div>
    </section>`;
  }).join("");
}

function macroImpactLabel(entry) {
  const prefix = entry.direction === "positive" ? "+" : entry.direction === "negative" ? "−" : "±";
  return `${prefix}${macroPercent(entry.impactMagnitude)}`;
}

function renderMacroScenarioRows(result) {
  const labels = Object.fromEntries(result.nodes.map((entry) => [entry.id, entry.label]));
  $("macroScenarioRows").innerHTML = result.nodes.map((entry) => `
    <tr>
      <td data-label="Group"><b>${esc(optionLabel(entry.group))}</b><small class="macro-source ${esc(entry.source)}">${esc(optionLabel(entry.source === "provided" ? "Provided probability" : "Editable assumption"))}</small></td>
      <td data-label="Outcome node"><div class="macro-node-label">${esc(optionLabel(entry.label))}</div><div class="macro-node-meta"><label class="macro-impact-input"><span>${esc(optionLabel("Impact"))}</span><input type="number" min="0" max="100" step="0.1" inputmode="decimal" value="${esc(Number((entry.impactMagnitude * 100).toFixed(4)))}" data-macro-impact="${esc(entry.id)}" aria-label="${esc(`${optionLabel("Impact assumption")}: ${optionLabel(entry.label)}`)}" /><b>%</b></label><span>${esc(optionLabel("Horizon"))} ${esc(optionLabel(entry.horizon))}</span><span>${esc(optionLabel("Lag"))} ${esc(optionLabel(entry.lag))}</span><span>${esc(optionLabel("Persistence"))} ${esc(optionLabel(entry.persistence))}</span><span>${esc(optionLabel("Confidence"))} ${esc(optionLabel(entry.confidence))}</span><span>${esc(optionLabel("Correlation"))} ${esc(optionLabel(entry.correlation))}</span><span>${esc(optionLabel("Assumption date"))} ${esc(entry.asOf)}</span></div></td>
      <td data-label="Direction"><span class="macro-direction ${esc(entry.direction)}">${esc(optionLabel(entry.direction))}</span></td>
      <td data-label="Prior event">${esc(optionLabel(labels[entry.parent] || result.triggerLabel))}</td>
      <td data-label="Conditional P"><label class="probability-input compact"><span class="sr-only">${esc(optionLabel("Conditional probability"))}: ${esc(optionLabel(entry.label))}</span><input type="number" min="0" max="100" step="0.1" inputmode="decimal" value="${esc(Number((entry.probability * 100).toFixed(4)))}" data-macro-node="${esc(entry.id)}" /><b>%</b></label></td>
      <td data-label="Path P"><b>${esc(macroPercent(entry.conditional))}</b></td>
      <td data-label="Absolute P">${entry.absolute === null ? `<span class="muted-inline">${esc(optionLabel("Set trigger priors"))}</span>` : `<b>${esc(macroPercent(entry.absolute))}</b>`}</td>
    </tr>`).join("");
}

function macroHoldingMatchesTags(item, tags = {}) {
  const holding = item?.holding || {};
  const descriptive = [
    holding.symbol, holding.secondary_symbol, holding.name, holding.company_name,
    holding.sector, holding.industry, item?.sector, item?.industry,
  ].filter(Boolean).join(" ").toLocaleLowerCase();
  const country = [holding.country, holding.location].filter(Boolean).join(" ").toLocaleLowerCase();
  const currency = String(holding.currency || "").toLocaleLowerCase();
  const assetClass = [holding.asset_class, holding.instrument_type].filter(Boolean).join(" ").toLocaleLowerCase();
  const descriptiveTerms = [...(tags.sectors || []), ...(tags.keywords || [])]
    .map((value) => String(value).toLocaleLowerCase()).filter(Boolean);
  const classTerms = (tags.assetClasses || []).map((value) => String(value).toLocaleLowerCase()).filter(Boolean);
  const currencyTerms = (tags.currencies || []).map((value) => String(value).toLocaleLowerCase()).filter(Boolean);
  const countryTerms = (tags.countries || []).map((value) => String(value).toLocaleLowerCase()).filter(Boolean);
  const axisMatches = [
    descriptiveTerms.length > 0 && descriptiveTerms.some((term) => descriptive.includes(term)),
    classTerms.length > 0 && classTerms.some((term) => assetClass === term || assetClass.includes(term)),
    currencyTerms.length > 0 && currencyTerms.includes(currency),
  ];
  if (!axisMatches.some(Boolean)) return false;
  if (countryTerms.length && country && !countryTerms.some((term) => country.includes(term))) return false;
  return true;
}

function macroPortfolioExposure(entry, totalPortfolioValue) {
  const holdings = (state.items || []).filter((item) => macroHoldingMatchesTags(item, entry.tags));
  const exposedValue = sum(holdings.map((item) => Math.abs(normalizedField(item, "market_value"))));
  const probability = entry.absolute === null ? entry.conditional : entry.absolute;
  const directionFactor = entry.direction === "positive" ? 1 : entry.direction === "negative" ? -1 : 0;
  return {
    entry,
    holdings,
    exposedValue,
    exposurePercent: totalPortfolioValue > 0 ? exposedValue / totalPortfolioValue : 0,
    probability,
    probabilityBasis: entry.absolute === null ? "Conditional" : "Absolute",
    estimatedImpact: exposedValue * probability * entry.impactMagnitude * directionFactor,
  };
}

function renderMacroPortfolioImpact(result) {
  const panel = $("macroPortfolioImpact");
  if (!panel) return;
  if (!state.portfolioReady) {
    panel.innerHTML = `<div class="macro-panel-head"><div><h3 id="macroPortfolioImpactTitle">${esc(optionLabel("Portfolio exposure"))}</h3><p>${esc(optionLabel("Portfolio holdings are still loading."))}</p></div></div>`;
    return;
  }
  const totalPortfolioValue = sum((state.items || []).map((item) => Math.abs(normalizedField(item, "market_value"))));
  const exposures = macroLeafNodes(result)
    .map((entry) => macroPortfolioExposure(entry, totalPortfolioValue))
    .filter((item) => item.exposedValue > 0)
    .sort((left, right) => right.exposedValue - left.exposedValue)
    .slice(0, 12);
  const rows = exposures.map((item) => {
    const symbols = item.holdings.map((holding) => holding.holding?.symbol).filter(Boolean).join(", ");
    const estimate = item.entry.direction === "mixed"
      ? `<span class="muted-inline">${esc(optionLabel("Direction not quantified"))}</span>`
      : `<b class="${esc(item.entry.direction)}">${esc(signedMoney(item.estimatedImpact, state.baseCurrency))}</b>`;
    return `<tr>
      <td data-label="Outcome"><b>${esc(optionLabel(item.entry.label))}</b><small title="${esc(symbols)}">${esc(fmt(item.holdings.length, 0))} ${esc(optionLabel("matching holdings"))}</small></td>
      <td data-label="Exposed value">${esc(money(item.exposedValue, state.baseCurrency))}</td>
      <td data-label="Portfolio share">${esc(macroPercent(item.exposurePercent))}</td>
      <td data-label="Probability"><b>${esc(macroPercent(item.probability))}</b><small>${esc(optionLabel(item.probabilityBasis))}</small></td>
      <td data-label="Impact assumption">${esc(macroImpactLabel(item.entry))}</td>
      <td data-label="Probability-weighted impact">${estimate}</td>
    </tr>`;
  }).join("");
  panel.innerHTML = `
    <div class="macro-panel-head"><div><h3 id="macroPortfolioImpactTitle">${esc(optionLabel("Portfolio exposure"))}</h3><p>${esc(optionLabel("Impact magnitude is an editable directional portfolio-value shock assumption, not a forecast. Estimated impact equals probability × impact magnitude × exposed portfolio value."))}</p></div><div class="macro-portfolio-total"><span>${esc(optionLabel("Portfolio value analyzed"))}</span><b>${esc(money(totalPortfolioValue, state.baseCurrency))}</b></div></div>
    ${rows ? `<div class="table-wrap"><table class="macro-exposure-table"><thead><tr><th>${esc(optionLabel("Outcome"))}</th><th>${esc(optionLabel("Exposed value"))}</th><th>${esc(optionLabel("Portfolio share"))}</th><th>${esc(optionLabel("Probability"))}</th><th>${esc(optionLabel("Impact assumption"))}</th><th>${esc(optionLabel("Probability-weighted impact"))}</th></tr></thead><tbody>${rows}</tbody></table></div>` : `<div class="empty">${esc(optionLabel("No holdings matched this workflow's terminal exposure tags."))}</div>`}
    <p class="macro-exposure-note">${esc(optionLabel("Do not add these rows together: outcomes can overlap, share holdings, and be correlated. Matching uses available holding country, sector, industry, currency, asset class, symbol, and name metadata."))}</p>`;
}

function renderMacroMathSummary(result) {
  const model = window.PortfolioScenarioModel;
  const path = model.pathTo(result.id, result.coreEnd, state.macroScenarioSettings);
  const equation = path.map((entry) => entry.probability.toFixed(2)).join(" × ");
  const best = macroMostLikelyEnd(result, "positive");
  const worst = macroMostLikelyEnd(result, "negative");
  const absolute = result.headline?.absolute === null
    ? optionLabel("Set trigger priors to calculate the unconditional end-state probability.")
    : `P(${optionLabel(result.headline.label)}) = ${macroPercent(result.triggerProbability)} × ${macroPercent(result.headline.conditional)} = ${macroPercent(result.headline.absolute)}`;
  $("macroMathSummary").innerHTML = `
    <div class="macro-panel-head"><div><h3 id="macroMathTitle">${esc(optionLabel("Mathematical summary"))}</h3><p>${esc(optionLabel("Multiplication follows the selected parent chain; sibling outcomes are not multiplied together."))}</p></div></div>
    <div class="macro-equation" dir="ltr">P(${esc(optionLabel(result.headline?.label || result.label))} | ${esc(optionLabel(result.triggerLabel))}) = ${esc(equation)} = <b>${esc(macroPercent(result.headline?.conditional))}</b></div>
    <div class="macro-equation" dir="ltr">${esc(absolute)}</div>
    <div class="macro-end-states">
      <div class="negative"><span>${esc(optionLabel("Most likely adverse leaf"))}</span><b>${esc(worst ? optionLabel(worst.label) : optionLabel("Not available"))}</b><em>${esc(macroPercent(worst?.conditional))}</em></div>
      <div class="positive"><span>${esc(optionLabel("Most likely favorable leaf"))}</span><b>${esc(best ? optionLabel(best.label) : optionLabel("Not available"))}</b><em>${esc(macroPercent(best?.conditional))}</em></div>
    </div>`;
}

function renderMacroScenario() {
  const model = window.PortfolioScenarioModel;
  if (!model || !$("macroScenarioModal")) return;
  state.macroScenarioSettings = model.normalizeSettings(state.macroScenarioSettings || {});
  renderMacroPriorStatus();
  renderMacroScenarioOverview();
  renderMacroTriggerLibrary();
  const result = model.calculateScenario(state.macroScenarioSettings.selected, state.macroScenarioSettings);
  renderMacroScenarioRows(result);
  renderMacroPortfolioImpact(result);
  renderMacroMathSummary(result);
  renderMacroScenarioDiagram(result);
}

function updateMacroScenarioProbability(target) {
  const settings = state.macroScenarioSettings;
  if (!settings) return;
  const priorIds = {
    macroPriorIncrease: "increase",
    macroPriorDecrease: "decrease",
    macroPriorUnchanged: "unchanged",
  };
  const raw = String(target.value || "").trim();
  const percent = raw === "" ? null : Number(raw);
  const value = percent === null ? null : percent / 100;
  if (percent !== null && (!Number.isFinite(percent) || percent < 0 || percent > 100)) {
    target.setAttribute("aria-invalid", "true");
    $("macroPriorStatus").textContent = optionLabel("Probability must be between 0% and 100%.");
    return;
  }
  target.removeAttribute("aria-invalid");
  if (priorIds[target.id]) settings.priors[priorIds[target.id]] = value;
  else if (target.id === "macroLocalTrigger") settings.localTrigger = value;
  else if (target.dataset.macroTriggerPrior) settings.triggerPriors[target.dataset.macroTriggerPrior] = value;
  else if (target.dataset.macroImpact) {
    if (value === null) delete settings.impactOverrides[target.dataset.macroImpact];
    else settings.impactOverrides[target.dataset.macroImpact] = value;
  }
  else if (target.dataset.macroNode) {
    if (value === null) delete settings.overrides[target.dataset.macroNode];
    else settings.overrides[target.dataset.macroNode] = value;
  }
  saveMacroScenarioSettings();
  renderMacroScenario();
}

function resetMacroScenario() {
  if (!window.confirm(optionLabel("Reset all trigger priors and conditional probabilities to their defaults?"))) return;
  state.macroScenarioSettings = window.PortfolioScenarioModel.defaultSettings();
  saveMacroScenarioSettings();
  renderMacroScenario();
  $("macroPriorStatus").textContent = optionLabel("Scenario assumptions reset.");
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
      <td>${esc(item.name || "Unknown company")}<div class="sub">${esc([item.sector, item.industry, item.country ? countryDisplayLabel(item.country) : ""].filter(Boolean).join(" · ") || "Classification unavailable")}</div></td>
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
  state.apiAccess = settings.integration_access?.rest || settings.api_access || { mode: "disabled", active_tokens: 0, token_ttl_seconds: 28800 };
  state.mcpAccess = settings.integration_access?.mcp || settings.mcp_access || { mode: "disabled", active_tokens: 0, token_ttl_seconds: 28800 };
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
    ["Saved security snapshots", data.security_snapshots ?? 0],
    ["Securities with saved history", data.security_symbols ?? 0],
    ["Cached company logos", data.company_logos ?? 0],
    ["Blank logo records", data.missing_company_logos ?? 0],
    ["Current size", `${data.size_mb} MB`],
    ["Max size", `${data.max_mb} MB`],
    ["TTL", `${data.ttl_hours} hours`],
  ].map(([label, value]) => `<div class="setting-row"><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join("");
  const backupRows = [
    ["Backup directory", backup.directory || ""],
    ["Backup contents", backup.backup_type === "full" ? "Full application state · sensitive" : "Portfolio data only"],
    ["Schedule", backup.enabled === false ? "Disabled" : backup.schedule_summary || backupScheduleSummary(backup.schedule_config)],
    ["Next run", backup.next_run ? formatBackupDateTime(backup.next_run) : "Disabled"],
    ["Latest backup", backup.latest?.filename || "None"],
    ["Backup files", backup.backup_count ?? (backup.backups || []).length],
  ].map(([label, value]) => `<div class="setting-row"><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join("");
  const backupFiles = (backup.backups || []).map((file) => `
    <div class="setting-row backup-file-row">
      <span class="backup-file-summary">
        <bdi class="backup-file-name" dir="ltr">${esc(file.filename)}</bdi>
        <span class="backup-file-separator" aria-hidden="true">·</span>
        <small>${esc(optionLabel(file.type === "full" ? "Full backup · sensitive" : "Data-only backup"))}</small>
        <span class="backup-file-separator" aria-hidden="true">·</span>
        <time datetime="${esc(file.modified_at || "")}" dir="ltr">${esc(formatBackupDateTime(file.modified_at))}</time>
        <span class="backup-file-separator" aria-hidden="true">·</span>
        <span class="backup-file-size" dir="ltr">${esc(fmt(file.size_kb ?? 0, 1))} KB</span>
      </span>
      <button class="secondary compact-button" type="button" data-download-backup="${esc(file.filename)}">Download</button>
    </div>
  `).join("");
  $("backupStatus").innerHTML = backupRows + backupFiles;
  renderApiAccessSettings();
}

const SETTINGS_SECTIONS = new Set(["display", "security", "table", "assistant", "api", "logging", "data", "backup", "system"]);

function setSettingsSection(requestedSection = "display", { focus = false } = {}) {
  const allowedSection = !["api", "logging"].includes(requestedSection) || canAdmin();
  const section = SETTINGS_SECTIONS.has(requestedSection) && allowedSection ? requestedSection : "display";
  document.querySelectorAll("[data-settings-section]").forEach((button) => {
    const active = button.dataset.settingsSection === section;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  document.querySelectorAll("[data-settings-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.settingsPanel !== section;
  });
  document.querySelectorAll(".settings-menu-help[open]").forEach((details) => details.removeAttribute("open"));
  if (section === "api" || section === "backup" || section === "system") {
    loadCacheStatus().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; });
  }
  if (section === "assistant") loadAssistantSettings();
  if (section === "logging") loadLoggingSettings();
  if (focus) requestAnimationFrame(() => document.querySelector(`[data-settings-section="${section}"]`)?.focus());
}

function apiAccessModeLabel(mode) {
  return {
    disabled: optionLabel("Off"),
    read_only: optionLabel("Read only"),
    read_write: optionLabel("Read and write"),
  }[mode] || optionLabel("Off");
}

function renderApiAccessSettings() {
  [
    ["apiAccessMode", "apiAccessSummary", state.apiAccess],
    ["mcpAccessMode", "mcpAccessSummary", state.mcpAccess],
  ].forEach(([radioName, summaryId, rawAccess]) => {
    const access = rawAccess || { mode: "disabled", active_tokens: 0, token_ttl_seconds: 28800 };
    const selected = document.querySelector(`input[name="${radioName}"][value="${access.mode}"]`)
      || document.querySelector(`input[name="${radioName}"][value="disabled"]`);
    if (selected) selected.checked = true;
    const summary = $(summaryId);
    if (!summary) return;
    const hours = Math.max(1, Math.round(Number(access.token_ttl_seconds || 28800) / 3600));
    summary.innerHTML = `<b>${esc(apiAccessModeLabel(access.mode))}</b><span>${esc(access.active_tokens || 0)} ${esc(optionLabel("active tokens"))} · ${esc(optionLabel("Tokens expire after"))} ${esc(hours)} ${esc(optionLabel("hours"))}</span>`;
  });
}

async function saveApiAccessSettings() {
  const restMode = document.querySelector('input[name="apiAccessMode"]:checked')?.value || "disabled";
  const mcpMode = document.querySelector('input[name="mcpAccessMode"]:checked')?.value || "disabled";
  const turnsOffService = (state.apiAccess?.mode !== "disabled" && restMode === "disabled")
    || (state.mcpAccess?.mode !== "disabled" && mcpMode === "disabled");
  if (turnsOffService
      && !confirm(optionLabel("Turning a service off immediately revokes its active tokens. Continue?"))) {
    renderApiAccessSettings();
    return;
  }
  const button = $("saveApiAccessSettings");
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  $("settingsStatus").textContent = optionLabel("Saving integration access");
  try {
    const access = await api("/api/settings/integration-access", {
      method: "PUT",
      body: JSON.stringify({ rest_mode: restMode, mcp_mode: mcpMode }),
    });
    state.apiAccess = access.rest;
    state.mcpAccess = access.mcp;
    renderApiAccessSettings();
    $("settingsStatus").textContent = optionLabel("Integration access saved");
  } finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
  }
}

function clearFullRestorePreview() {
  state.pendingFullRestoreFile = null;
  state.pendingFullRestoreInspection = null;
  const input = $("fullRestoreFile");
  if (input) input.value = "";
  const preview = $("fullRestorePreview");
  if (preview) {
    preview.hidden = true;
    preview.innerHTML = "";
  }
}

function renderFullRestorePreview(file, inspection) {
  const preview = $("fullRestorePreview");
  if (!preview) return;
  const contains = inspection.contains || {};
  const included = [
    contains.portfolio_database ? optionLabel("Portfolio database") : "",
    contains.client_preferences_and_pension_simulations ? optionLabel("Pension simulations and preferences") : "",
    contains.application_config ? "config.yaml" : "",
    contains.runtime_data_and_caches ? optionLabel("Runtime data and caches") : "",
    contains.tls_certificates ? optionLabel("TLS certificates") : "",
  ].filter(Boolean).join(" · ");
  preview.innerHTML = `
    <h4>${esc(optionLabel("Full backup verified"))}</h4>
    <dl class="restore-summary">
      <dt>${esc(optionLabel("File"))}</dt><dd dir="ltr">${esc(file.name)}</dd>
      <dt>${esc(optionLabel("Created"))}</dt><dd dir="ltr">${esc(formatBackupDateTime(inspection.created_at))}</dd>
      <dt>${esc(optionLabel("Application version"))}</dt><dd dir="ltr">${esc(inspection.app_version || "Unknown")}</dd>
      <dt>${esc(optionLabel("Contents"))}</dt><dd>${esc(included || optionLabel("No recognized contents"))}</dd>
      <dt>${esc(optionLabel("Files"))}</dt><dd>${esc(fmt(inspection.files || 0, 0))} · ${esc(fmt((inspection.total_size_bytes || 0) / 1024, 1))} KB</dd>
    </dl>
    <p class="restore-warning">${esc(optionLabel("Restoring replaces the current application state. The app will first create a full safety backup automatically."))}</p>
    <label class="restore-confirmation"><input id="confirmFullRestoreRisk" type="checkbox" /> <span>${esc(optionLabel("I understand that the current database, settings, configuration, caches, and certificates will be replaced."))}</span></label>
    <div class="restore-actions">
      <button id="runFullRestore" class="danger-button" type="button" disabled>${esc(optionLabel("Restore full backup"))}</button>
      <button id="cancelFullRestore" class="secondary" type="button">${esc(optionLabel("Cancel"))}</button>
    </div>`;
  preview.hidden = false;
}

async function inspectFullRestore(file) {
  if (!file) return;
  $("settingsStatus").textContent = "Validating full backup";
  const response = await fetch("/api/local/backups/inspect", {
    method: "POST",
    headers: authRequestHeaders({ "Content-Type": "application/zip", "X-Backup-Filename": encodeURIComponent(file.name) }),
    body: file,
  });
  if (!response.ok) {
    let detail = "Backup validation failed";
    const responseText = await response.text();
    try { detail = JSON.parse(responseText).detail || detail; } catch { detail = responseText || detail; }
    throw new Error(optionLabel(detail));
  }
  const inspection = await response.json();
  state.pendingFullRestoreFile = file;
  state.pendingFullRestoreInspection = inspection;
  renderFullRestorePreview(file, inspection);
  $("settingsStatus").textContent = "Full backup verified. Review the details before restoring.";
}

async function restoreFullBackup() {
  const file = state.pendingFullRestoreFile;
  const confirmation = $("confirmFullRestoreRisk");
  if (!file || !confirmation?.checked) return;
  const restoreButton = $("runFullRestore");
  if (restoreButton) restoreButton.disabled = true;
  $("settingsStatus").textContent = "Creating a safety backup and restoring the full application";
  const response = await fetch("/api/local/backups/restore", {
    method: "POST",
    headers: authRequestHeaders({
      "Content-Type": "application/zip",
      "X-Backup-Filename": encodeURIComponent(file.name),
      "X-Restore-Confirm": "replace-current-application-state",
    }),
    body: file,
  });
  if (!response.ok) {
    let detail = "Full restore failed";
    const responseText = await response.text();
    try { detail = JSON.parse(responseText).detail || detail; } catch { detail = responseText || detail; }
    if (restoreButton) restoreButton.disabled = false;
    throw new Error(optionLabel(detail));
  }
  const result = await response.json();
  clearFullRestorePreview();
  $("settingsStatus").textContent = `Full restore completed. Safety backup: ${result.safety_backup}. Restart the application to load restored configuration and certificates.`;
  await loadCacheStatus();
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
  if (canWrite()) await syncClientStateToServer();
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
  $("settingsStatus").textContent = "Creating full backup";
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
  const name = about.name || "Portfolio Analyzer";
  const version = about.version || "";
  $("aboutContent").innerHTML = `
    <section class="about-product" aria-labelledby="aboutProductName">
      <span class="about-product-mark" aria-hidden="true"></span>
      <div>
        <div class="about-product-heading">
          <h3 id="aboutProductName">${esc(name)}</h3>
          ${version ? `<span class="about-version">Version <bdi dir="ltr">${esc(version)}</bdi></span>` : ""}
        </div>
        <p>A private, self-hosted workspace for understanding investments, long-term savings, retirement scenarios, company research, and portfolio alerts.</p>
      </div>
    </section>
    <div class="about-principles">
      <article>
        <h4>One financial picture</h4>
        <p>Bring household accounts, holdings, pensions, reports, and research together without turning the dashboard into a public service.</p>
      </article>
      <article>
        <h4>Local control</h4>
        <p>Portfolio changes stay in this installation. Role-based access separates administration, editing, and read-only viewing.</p>
      </article>
    </div>
    <p class="about-disclaimer" role="note">Analytics, market signals, and retirement projections are decision-support estimates. They are not financial, tax, or pension advice.</p>`;
}

function renderUsers() {
  const container = $("usersList");
  if (!container) return;
  if ($("userCount")) $("userCount").textContent = String(state.users.length);
  if (!state.users.length) {
    container.innerHTML = `<div class="empty">${esc(optionLabel("No users found"))}</div>`;
    return;
  }
  container.innerHTML = state.users.map((user) => {
    const isCurrent = user.id === currentUser()?.id;
    const status = user.enabled ? "Enabled" : "Disabled";
    const passwordState = user.must_change_password ? optionLabel("Password change required") : optionLabel("Password active");
    return `
      <article class="user-management-item${user.enabled ? "" : " is-disabled"}">
        <div class="user-summary">
          <strong>${esc(`${user.first_name} ${user.last_name}`.trim() || user.username)}</strong>
          <span><bdi dir="ltr">@${esc(user.username)}</bdi> · ${esc(optionLabel(user.role))} · ${esc(optionLabel(status))}</span>
          <span>${esc(passwordState)}${isCurrent ? ` · ${esc(optionLabel("Current user"))}` : ""}</span>
        </div>
        <div class="user-actions">
          <button class="secondary" type="button" data-user-enabled="${esc(user.id)}" data-enabled="${String(!user.enabled)}"${isCurrent ? " disabled" : ""}>${esc(optionLabel(user.enabled ? "Disable" : "Enable"))}</button>
          <button class="secondary danger-outline" type="button" data-delete-user="${esc(user.id)}"${isCurrent ? " disabled" : ""}>${esc(optionLabel("Delete"))}</button>
        </div>
      </article>`;
  }).join("");
}

async function loadUsers() {
  const data = await api("/api/auth/users");
  state.users = data.items || [];
  renderUsers();
  applyRolePermissions($("usersList"));
}

async function createUser() {
  const button = $("saveUser");
  button.disabled = true;
  $("userFormStatus").textContent = optionLabel("Adding user");
  try {
    await api("/api/auth/users", {
      method: "POST",
      body: JSON.stringify({
        first_name: $("userFirstName").value,
        last_name: $("userLastName").value,
        username: $("userUsername").value,
        password: $("userPassword").value,
        role: $("userRole").value,
      }),
    });
    $("userCreateForm").reset();
    $("userPassword").value = "";
    $("userFormStatus").textContent = optionLabel("User added. A password change is required at first sign-in.");
    await loadUsers();
  } finally {
    button.disabled = false;
  }
}

async function setUserEnabled(userId, enabled) {
  $("usersStatus").textContent = optionLabel(enabled ? "Enabling user" : "Disabling user");
  await api(`/api/auth/users/${encodeURIComponent(userId)}/status`, {
    method: "PUT",
    body: JSON.stringify({ enabled }),
  });
  $("usersStatus").textContent = optionLabel(enabled ? "User enabled" : "User disabled");
  await loadUsers();
}

async function removeUser(userId) {
  if (!confirm(optionLabel("Delete this user? This cannot be undone."))) return;
  $("usersStatus").textContent = optionLabel("Deleting user");
  await api(`/api/auth/users/${encodeURIComponent(userId)}`, { method: "DELETE" });
  $("usersStatus").textContent = optionLabel("User deleted");
  await loadUsers();
}

async function loadBrandVersion() {
  const badge = $("brandVersion");
  if (!badge) return;
  const about = await api("/api/about");
  const version = String(about.version || "").trim();
  badge.textContent = version ? `v${version.replace(/^v/i, "")}` : "";
  badge.hidden = !version;
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

function mountModalHomeLink(modal) {
  modal.querySelector(".modal-home-link")?.remove();
  const brand = $("dashboardHome");
  if (!brand) return;
  const link = brand.cloneNode(true);
  link.removeAttribute("id");
  link.querySelectorAll("[id]").forEach((node) => node.removeAttribute("id"));
  link.classList.add("modal-home-link");
  link.setAttribute("aria-label", t("Return to dashboard"));
  link.setAttribute("title", t("Return to dashboard"));
  link.querySelector(".brand-version")?.setAttribute("aria-label", t("Application version"));
  modal.append(link);
  positionModalHomeLinks();
}

function positionModalHomeLinks() {
  const brand = $("dashboardHome");
  if (!brand) return;
  const rect = brand.getBoundingClientRect();
  document.querySelectorAll(".modal-home-link").forEach((link) => {
    link.style.left = `${Math.min(Math.max(rect.left, 8), Math.max(8, window.innerWidth - rect.width - 8))}px`;
    link.style.top = `${rect.top}px`;
    link.style.width = `${rect.width}px`;
    link.style.height = `${rect.height}px`;
  });
}

function returnToDashboard() {
  document.querySelectorAll(".modal:not([hidden])").forEach((modal) => {
    modal.hidden = true;
    modal.inert = false;
    modal.removeAttribute("aria-hidden");
    modal.querySelector(".modal-home-link")?.remove();
  });
  modalReturnFocus.clear();
  setMobileNavigation(false);
  state.returnToEmployeeOptionsAfterAccount = false;
  document.querySelectorAll(".nav-menu[open]").forEach((menu) => { menu.open = false; });
  window.scrollTo({ top: 0, behavior: "instant" });
  $("dashboardTitle")?.focus({ preventScroll: true });
}

window.addEventListener("resize", positionModalHomeLinks);

function openModal(id, returnFocus = document.activeElement, destination = {}) {
  const modal = $(id);
  if (!modal) return;
  if (returnFocus instanceof HTMLElement) modalReturnFocus.set(id, returnFocus);
  modal.hidden = false;
  mountModalHomeLink(modal);
  if (id === "assistantModal") {
    loadAssistantChats();
    requestAnimationFrame(() => $("assistantPrompt")?.focus());
  }
  if (id === "accountsModal") {
    setAccountsTab("existing");
    Promise.all([loadBrokers(), loadFamilyMembers(), loadLocalAccounts()]);
  }
  if (id === "brokersModal") loadBrokers();
  if (id === "familyModal") {
    setFamilyStatus("Loading people…");
    Promise.all([loadLocalAccounts(), loadFamilyMembers()])
      .then(() => setFamilyStatus())
      .catch(() => setFamilyStatus("Could not load people. Close and reopen People to retry."));
  }
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
    state.alarmsLoadFailed = false;
    renderAlarms();
    loadEvents().catch(() => { state.alarmsLoadFailed = true; renderAlarms(); });
  }
  if (id === "reportsModal") {
    Promise.all([loadLocalAccounts(), loadFamilyMembers()])
      .then(loadReports)
      .catch((error) => { $("reportsExportStatus").textContent = `Error: ${error.message}`; });
  }
  if (id === "positionsModal") {
    loadTradeHistory();
    requestAnimationFrame(() => $("tradeHistoryTitle").focus());
  }
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
  if (id === "macroScenarioModal") {
    renderMacroScenario();
    requestAnimationFrame(() => modal.querySelector("[data-modal-initial-focus]")?.focus());
  }
  if (id === "bannerModal") renderBannerSettings();
  if (id === "usersModal") {
    $("userFormStatus").textContent = "";
    $("usersStatus").textContent = "";
    loadUsers().catch((error) => { $("usersStatus").textContent = `Error: ${error.message}`; });
  }
  if (id === "settingsModal") {
    setSettingsSection("display", { focus: true });
    clearFullRestorePreview();
    $("settingsStatus").textContent = "";
  }
  if (id === "backupScheduleModal") populateBackupScheduleForm();
  if (id === "aboutModal") loadAbout().catch((error) => { $("aboutContent").innerHTML = `<div class="empty">Error: ${esc(error.message)}</div>`; });
  if (id === "helpModal") requestAnimationFrame(() => modal.querySelector("[data-modal-initial-focus]")?.focus());
  focusModalDestination(modal, destination);
}

function closeModal(modal) {
  if (!modal) return;
  if (modal.id === "assistantModal") saveAssistantDraft();
  if (modal.id === "familyMemberModal") {
    if (state.familyMemberSaving) return;
    $("familyModal").inert = false;
    $("familyModal").removeAttribute("aria-hidden");
    if (!modalReturnFocus.get(modal.id)?.isConnected) {
      const editButton = [...document.querySelectorAll("[data-edit-family-member]")]
        .find((button) => button.dataset.editFamilyMember === state.editingFamilyMemberId);
      modalReturnFocus.set(modal.id, editButton || $("newFamilyMember"));
    }
    clearFamilyMemberForm();
    renderFamilyMemberEditor();
  }
  if (modal.id === "tradeHistoryDetailModal") {
    $("positionsModal").inert = false;
    $("positionsModal").removeAttribute("aria-hidden");
  }
  modal.hidden = true;
  modal.querySelector(".modal-home-link")?.remove();
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
      focusTarget.focus({ preventScroll: modal.id === "tradeHistoryDetailModal" });
    }
  });
}

document.addEventListener("keydown", (event) => {
  const authOverlay = $("authOverlay");
  if (authOverlay && !authOverlay.hidden) {
    if (event.key === "Escape" && !$("passwordChangeForm").hidden && !state.auth.forcedPasswordChange) {
      event.preventDefault();
      hideAuthOverlay();
    } else if (event.key === "Tab") {
      const controls = [...authOverlay.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled])')]
        .filter((control) => control.getClientRects().length > 0);
      const index = controls.indexOf(document.activeElement);
      if (controls.length && (index === -1 || (event.shiftKey && index === 0) || (!event.shiftKey && index === controls.length - 1))) {
        event.preventDefault();
        controls[event.shiftKey ? controls.length - 1 : 0].focus();
      }
    }
    return;
  }
  if (event.target.id === "query" && event.key === "Enter") {
    event.preventDefault();
    applyFilter();
    return;
  }

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
  if (!activeModal) {
    if (event.key === "Escape") {
      const menu = event.target.closest?.(".nav-menu[open]") || document.querySelector(".nav-menu[open]");
      if (menu) {
        event.preventDefault();
        menu.open = false;
        menu.querySelector("summary")?.focus();
      } else if (window.matchMedia("(max-width: 760px)").matches && $("appNavigation")?.classList.contains("is-expanded")) {
        event.preventDefault();
        setMobileNavigation(false);
        $("navigationToggle")?.focus();
      }
    }
    return;
  }
  if (event.key === "Escape") {
    event.preventDefault();
    closeModal(activeModal);
    return;
  }
  if (event.key !== "Tab") return;
  const focusable = [...activeModal.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [href], [tabindex]:not([tabindex="-1"])')]
    .filter((element) => element.getClientRects().length > 0);
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
  if (event.target.closest("#navigationToggle")) {
    setMobileNavigation($("navigationToggle").getAttribute("aria-expanded") !== "true");
    return;
  }
  if (event.target.closest("[data-dashboard-home]")) {
    event.preventDefault();
    returnToDashboard();
    return;
  }
  const tradeDetail = event.target.closest("[data-trade-history-details]");
  if (tradeDetail) {
    openTradeHistoryDetails(tradeDetail.dataset.tradeHistoryDetails, tradeDetail);
    return;
  }
  const positionSort = event.target.closest("[data-position-sort]");
  if (positionSort) {
    setPositionColumnSort(positionSort.dataset.positionSort);
    return;
  }
  if (event.target.closest("[data-reset-position-filters]")) {
    resetPositionFilters();
    return;
  }
  const tradePage = event.target.closest("[data-trade-history-page]");
  if (tradePage) {
    state.tradeHistoryPage += Number(tradePage.dataset.tradeHistoryPage);
    renderTradeHistory();
    $("tradeHistoryTitle").scrollIntoView({ block: "nearest" });
    return;
  }
  const actionHelpSummary = event.target.closest(".row-action-help summary");
  if (actionHelpSummary) {
    requestAnimationFrame(() => {
      const help = actionHelpSummary.parentElement;
      if (!help?.open) return;
      const popover = help.querySelector(".row-action-help-popover");
      const scrollContainer = help.closest(".management-list");
      help.classList.remove("open-up");
      if (popover && scrollContainer) {
        const availableBelow = scrollContainer.getBoundingClientRect().bottom - actionHelpSummary.getBoundingClientRect().bottom;
        help.classList.toggle("open-up", availableBelow < popover.offsetHeight + 10);
      }
      actionHelpSummary.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  }

  const modalTrigger = event.target.closest("[data-modal]");
  const modalId = modalTrigger?.dataset.modal;
  if (modalId) {
    if (modalTrigger.dataset.researchSection) setResearchSection(modalTrigger.dataset.researchSection);
    if (modalId === "securitiesModal") setSecuritiesWorkflow(modalTrigger.dataset.securitiesWorkflow || "general");
    const mobileNavigation = modalTrigger.closest("#appNavigation") && window.matchMedia("(max-width: 760px)").matches;
    openModal(modalId, mobileNavigation ? $("navigationToggle") : modalTrigger, {
      targetId: modalTrigger.dataset.modalTarget || "",
      focusId: modalTrigger.dataset.modalFocus || "",
    });
    if (mobileNavigation) setMobileNavigation(false);
  }

  const userEnabledButton = event.target.closest("[data-user-enabled]");
  if (userEnabledButton) {
    setUserEnabled(userEnabledButton.dataset.userEnabled, userEnabledButton.dataset.enabled === "true")
      .catch((error) => { $("usersStatus").textContent = `Error: ${error.message}`; });
  }

  const deleteUserButton = event.target.closest("[data-delete-user]");
  if (deleteUserButton) {
    removeUser(deleteUserButton.dataset.deleteUser)
      .catch((error) => { $("usersStatus").textContent = `Error: ${error.message}`; });
  }

  const settingsSection = event.target.closest("[data-settings-section]")?.dataset.settingsSection;
  if (settingsSection) setSettingsSection(settingsSection);

  if (event.target.id === "cancelFullRestore") clearFullRestorePreview();
  if (event.target.id === "runFullRestore") {
    restoreFullBackup().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; });
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
    setStatusMessage("accountsStatus", "Create an ESOP account for your employee stock option grants.");
    requestAnimationFrame(() => $("localUsername")?.focus());
  }

  const researchTab = event.target.closest("[data-research-tab]")?.dataset.researchTab;
  if (researchTab) setResearchSection(researchTab);

  const macroScenario = event.target.closest("[data-macro-scenario]")?.dataset.macroScenario;
  if (macroScenario && window.PortfolioScenarioModel?.WORKFLOWS.some((item) => item.id === macroScenario)) {
    state.macroScenarioSettings.selected = macroScenario;
    saveMacroScenarioSettings();
    renderMacroScenario();
  }
  if (event.target.id === "resetMacroScenario") resetMacroScenario();

  const investigateSignal = event.target.closest("[data-investigate-signal]")?.dataset.investigateSignal;
  if (investigateSignal) {
    investigateAlertSignal(investigateSignal).catch((error) => {
      $("companyOutlookStatus").textContent = `Error: ${error.message}`;
    });
  }

  const alertChartButton = event.target.closest("[data-alert-chart]");
  if (alertChartButton) {
    openAlertSignalChart(alertChartButton.dataset.alertChart, alertChartButton).catch((error) => {
      $("alertStatus").textContent = `Error: ${error.message}`;
    });
  }

  const editAlertId = event.target.closest("[data-edit-alert]")?.dataset.editAlert;
  if (editAlertId) editAlertRule(editAlertId);

  const toggleAlertId = event.target.closest("[data-toggle-alert]")?.dataset.toggleAlert;
  if (toggleAlertId) {
    toggleAlertRule(toggleAlertId).catch((error) => { $("alertStatus").textContent = `Error: ${error.message}`; });
  }

  const runAlertButton = event.target.closest("[data-run-alert]");
  const runAlertId = runAlertButton?.dataset.runAlert;
  if (runAlertId) runAlertRule(runAlertId, runAlertButton).catch((error) => { $("alertStatus").textContent = `Error: ${error.message}`; });

  const deleteAlertId = event.target.closest("[data-delete-alert]")?.dataset.deleteAlert;
  if (deleteAlertId) {
    deleteAlertRule(deleteAlertId).catch((error) => { $("alertStatus").textContent = `Error: ${error.message}`; });
  }

  const removeAlertConditionIndex = event.target.closest("[data-remove-alert-condition]")?.dataset.removeAlertCondition;
  if (removeAlertConditionIndex !== undefined) removeAlertCondition(Number(removeAlertConditionIndex));

  if (event.target.closest("[data-add-alert-condition]")) addAlertCondition();

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

  const industryClassificationButton = event.target.closest("[data-classify-industry-symbol]");
  if (industryClassificationButton) {
    openIndustryClassification(
      industryClassificationButton.dataset.classifyIndustrySymbol,
      industryClassificationButton.dataset.classifyIndustryMarket,
      industryClassificationButton,
    );
  }

  const exposureButton = event.target.closest("[data-edit-security-exposure-symbol]");
  if (exposureButton) {
    openSecurityExposure(exposureButton.dataset.editSecurityExposureSymbol, exposureButton.dataset.editSecurityExposureMarket, exposureButton);
  }
  if (event.target.closest("[data-remove-exposure-currency]")) {
    event.target.closest(".exposure-currency-row")?.remove();
    updateSecurityExposureCurrencyState();
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
    removeLocalAccount(accountId).catch((error) => {
      setStatusMessage("accountsStatus", `Error: ${error.message}`);
    });
  }

  const securityDetailButton = event.target.closest("[data-security-detail-symbol]");
  if (securityDetailButton) {
    openSecurityDetail(securityDetailButton.dataset).catch((error) => {
      $("status").textContent = `Error: ${error.message}`;
    });
  }

  const positionHistoryButton = event.target.closest("[data-position-history-symbol]");
  if (positionHistoryButton) {
    openPositionTransactionHistory(positionHistoryButton.dataset, positionHistoryButton).catch((error) => {
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
    resetSecurityChartZoom({ render: false });
    if ($("securityChartStartDate")) $("securityChartStartDate").value = state.securityChartStartDate;
    loadSecurityDetail().catch((error) => { $("securityDetailStatus").textContent = `Error: ${error.message}`; });
  }

  const securityChartMode = event.target.closest("[data-security-chart-mode]")?.dataset.securityChartMode;
  if (securityChartMode) {
    state.securityChartMode = securityChartMode === "candles" ? "candles" : "line";
    renderSecurityChart();
  }

  const securityChartZoom = event.target.closest("[data-security-chart-zoom]")?.dataset.securityChartZoom;
  if (securityChartZoom === "in") zoomSecurityChart(0.72, 0.5);
  if (securityChartZoom === "out") zoomSecurityChart(1.35, 0.5);
  if (securityChartZoom === "earlier") panSecurityChart(-1);
  if (securityChartZoom === "later") panSecurityChart(1);
  if (securityChartZoom === "reset") resetSecurityChartZoom();

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

  const equityPriceTrigger = event.target.closest("[data-price-history-symbol]");
  if (equityPriceTrigger) openPriceHistoryForSecurity(equityPriceTrigger.dataset, equityPriceTrigger);

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

  const addSkippedAccount = event.target.closest("[data-add-skipped-account]")?.dataset.addSkippedAccount;
  if (addSkippedAccount !== undefined) prepareSkippedImportAccount(addSkippedAccount);

  const fixSkippedAccount = event.target.closest("[data-fix-skipped-account]")?.dataset.fixSkippedAccount;
  if (fixSkippedAccount !== undefined) prepareSkippedImportAccount(fixSkippedAccount);

  const editManualSecurityId = event.target.closest("[data-edit-manual-security]")?.dataset.editManualSecurity;
  if (editManualSecurityId) editManualSecurity(editManualSecurityId);

  if (event.target.id === "cancelManualSecurityEdit") {
    clearManualSecurityForm();
    $("manualSecurityStatus").textContent = "Edit cancelled.";
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
    deleteFamilyMember(familyMemberId);
  }

  const editFamilyMemberId = event.target.closest("[data-edit-family-member]")?.dataset.editFamilyMember;
  if (editFamilyMemberId) {
    editFamilyMember(editFamilyMemberId, event.target.closest("[data-edit-family-member]"));
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

  const periodIndex = event.target.closest("[data-delete-pension-period]")?.dataset.deletePensionPeriod;
  if (periodIndex !== undefined) {
    const scenario = activePensionScenario();
    if (scenario) scenario.income_periods.splice(Number(periodIndex), 1);
    invalidatePensionSimulation();
    renderPensionScenarios();
    renderPensionPeriods();
    renderFundsOverview();
    if (scenario) $("pensionPeriodStatus").textContent = pensionScenarioScheduleIssue(scenario);
  }

  const rateIndex = event.target.closest("[data-delete-pension-rate]")?.dataset.deletePensionRate;
  if (rateIndex !== undefined) {
    const scenario = activePensionScenario();
    if (scenario) scenario.return_periods.splice(Number(rateIndex), 1);
    invalidatePensionSimulation();
    renderPensionScenarios();
    renderPensionRates();
    renderFundsOverview();
    if (scenario) $("pensionPeriodStatus").textContent = pensionScenarioScheduleIssue(scenario);
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
    const scenario = state.pensionScenarios[removed];
    if (!scenario || !confirm(optionLabel("Remove this scenario? Its salary and return periods will also be deleted."))) return;
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
    $("pensionSimulationStatus").textContent = "Scenario removed";
  }

  const moveButton = event.target.closest("[data-dashboard-move]");
  if (moveButton) {
    moveDashboardWidget(moveButton.dataset.dashboardMove, Number(moveButton.dataset.direction || 0));
  }

  const placementButton = event.target.closest("[data-dashboard-set-view]");
  if (placementButton) {
    setDashboardWidgetView(placementButton.dataset.dashboardSetView, placementButton.dataset.view);
  }

  const areaButton = event.target.closest("[data-dashboard-area]");
  if (areaButton) {
    setDashboardArea(areaButton.dataset.dashboardArea);
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
  const alertMetricSelect = event.target.closest("[data-alert-condition-metric]");
  if (alertMetricSelect) updateAlertConditionGuidance(alertMetricSelect.closest("[data-alert-condition]"));
  if (["macroPriorIncrease", "macroPriorDecrease", "macroPriorUnchanged", "macroLocalTrigger"].includes(event.target.id)
    || event.target.matches("[data-macro-node], [data-macro-trigger-prior], [data-macro-impact]")) {
    updateMacroScenarioProbability(event.target);
  }
  if (event.target.id === "confirmFullRestoreRisk") {
    const restoreButton = $("runFullRestore");
    if (restoreButton) restoreButton.disabled = !event.target.checked;
  }
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
      renderFundsOverview();
    } else if (period && numericFields.includes(field)) {
      period[field] = pensionPeriodInput.value === "" ? 0 : Number(pensionPeriodInput.value);
      period.insurance_track = pensionInsuranceTrackFor(period);
      invalidatePensionSimulation();
      renderPensionScenarios();
      renderPensionPeriods();
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

  const longTermPensionToggle = event.target.closest("[data-long-term-include-pension]");
  if (longTermPensionToggle) {
    state.longTermIncludePension = longTermPensionToggle.checked;
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
    resetSecurityChartZoom({ render: false });
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

$("loginForm").addEventListener("submit", (event) => {
  event.preventDefault();
  signIn().catch((error) => { $("loginStatus").textContent = error.message; });
});
$("passwordChangeForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitPasswordChange().catch((error) => { $("passwordChangeStatus").textContent = error.message; });
});
$("cancelPasswordChange").addEventListener("click", hideAuthOverlay);
$("changePasswordButton").addEventListener("click", () => showPasswordChange({ forced: false }));
$("logoutButton").addEventListener("click", () => signOut().catch((error) => { $("status").textContent = `Error: ${error.message}`; }));
$("authLanguage").addEventListener("change", () => {
  state.language = $("authLanguage").value === "en" ? "en" : "he";
  localStorage.setItem(LANGUAGE_STORAGE_KEY, state.language);
  applyLanguage();
});
$("userCreateForm").addEventListener("submit", (event) => {
  event.preventDefault();
  createUser().catch((error) => { $("userFormStatus").textContent = `Error: ${error.message}`; });
});

$("refresh").addEventListener("click", () => {
  loadPortfolio({ refresh: true }).catch((error) => { $("status").textContent = `Error: ${error.message}`; });
  loadBanner().catch(() => {});
});
$("assistantComposer").addEventListener("submit", (event) => {
  event.preventDefault();
  askPortfolioAssistant();
});
$("assistantPrompt").addEventListener("input", saveAssistantDraft);
$("assistantPrompt").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault();
    askPortfolioAssistant();
  }
});
$("assistantLauncher").addEventListener("input", openAssistantFromLauncher);
$("assistantLauncher").addEventListener("compositionend", openAssistantFromLauncher);
$("newAssistantChat").addEventListener("click", newAssistantChat);
$("assistantChatList").addEventListener("click", (event) => {
  const deleteId = event.target.closest("[data-delete-assistant-chat]")?.dataset.deleteAssistantChat;
  if (deleteId) { requestAssistantChatDeletion(deleteId); return; }
  const chatId = event.target.closest("[data-assistant-chat]")?.dataset.assistantChat;
  if (chatId) selectAssistantChat(chatId);
});
$("confirmAssistantDelete").addEventListener("click", deleteAssistantChat);
$("cancelAssistantDelete").addEventListener("click", cancelAssistantChatDeletion);
$("retryAssistant").addEventListener("click", () => {
  if (assistantUi().retry === "send") askPortfolioAssistant();
  else loadAssistantChats();
});
$("assistantSettingsForm").addEventListener("submit", (event) => {
  event.preventDefault();
  saveAssistantSettings();
});
$("loggingSettingsForm").addEventListener("submit", (event) => {
  event.preventDefault();
  saveLoggingSettings();
});
$("apply").addEventListener("click", applyFilter);
$("saveAlert").addEventListener("click", saveAlert);
$("runAlerts").addEventListener("click", runAlerts);
$("addAlertCondition").addEventListener("click", addAlertCondition);
$("newAlertRule").addEventListener("click", () => {
  resetAlertForm();
  $("alertStatus").textContent = t("New rule ready. Add one or more conditions, then save it.");
  $("alertName").focus();
});
$("cancelAlertEdit").addEventListener("click", () => {
  resetAlertForm();
  $("alertStatus").textContent = "Edit cancelled.";
});
$("addBannerItem").addEventListener("click", addBannerItem);
$("runMarketScreener").addEventListener("click", () => runMarketScreener().catch((error) => { $("marketStatus").textContent = `Error: ${error.message}`; }));
$("resetMarketScreener").addEventListener("click", resetMarketScreener);
$("saveLocalAccount").addEventListener("click", () => saveLocalAccount().catch((error) => { setStatusMessage("accountsStatus", `Error: ${error.message}`); }));
$("saveEditAccount").addEventListener("click", () => saveEditAccount().catch((error) => { $("editAccountStatus").textContent = `Error: ${error.message}`; }));
$("saveBroker").addEventListener("click", () => saveBroker().catch((error) => { $("brokerStatus").textContent = `Error: ${error.message}`; }));
$("clearBrokerForm").addEventListener("click", clearBrokerForm);
$("newFamilyMember").addEventListener("click", () => openFamilyMemberEditor("", $("newFamilyMember")));
$("familyMemberForm").addEventListener("submit", (event) => {
  event.preventDefault();
  saveFamilyMember().catch(() => familyMemberValidation("Could not save this person. Check the details and try again.", ""));
});
$("attachAccountToMember").addEventListener("click", () => attachAccountToMember().catch((error) => { $("accountOwnershipStatus").textContent = `Error: ${error.message}`; }));
$("attachLocalAccountPerson").addEventListener("click", () => attachFamilyMember("localAccountPersons", "localAccountFamilyMember", "accountsStatus", { single: !accountAllowsMultipleMembers({ type: valueOf("localAccountType") }) }));
$("attachEditAccountPerson").addEventListener("click", () => attachFamilyMember("editAccountPersons", "editAccountFamilyMember", "editAccountStatus", { single: !accountAllowsMultipleMembers({ type: valueOf("editAccountType") }) }));
$("importSource").addEventListener("click", () => importSourceToLocal().catch((error) => { setStatusMessage("accountsStatus", `Error: ${error.message}`); }));
$("exportData").addEventListener("click", () => exportLocalData().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }));
$("chooseImportData").addEventListener("click", () => $("importDataFile").click());
$("importDataFile").addEventListener("change", (event) => importLocalData(event.target.files?.[0]).catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }).finally(() => { event.target.value = ""; }));
$("chooseFullRestore").addEventListener("click", () => $("fullRestoreFile").click());
$("fullRestoreFile").addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  clearFullRestorePreview();
  if (!file) return;
  inspectFullRestore(file).catch((error) => {
    $("settingsStatus").textContent = `Error: ${error.message}`;
    clearFullRestorePreview();
  });
});
$("runBackupNow").addEventListener("click", () => runBackupNow().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }));
$("downloadBackupsZip").addEventListener("click", () => downloadBackupsZip().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }));
$("saveBackupSettings").addEventListener("click", () => saveBackupSettings().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }));
$("saveApiAccessSettings").addEventListener("click", () => saveApiAccessSettings().catch((error) => { $("settingsStatus").textContent = `Error: ${error.message}`; }));
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
  loadCacheStatus().catch(reportBackgroundError);
  $("settingsStatus").textContent = t("displaySettingsSaved");
});
$("dashboardEdit").addEventListener("click", () => setDashboardEdit(!state.dashboard.edit));
$("dashboardReset").addEventListener("click", resetDashboard);
$("saveManualSecurity").addEventListener("click", () => saveManualSecurity().catch((error) => { $("manualSecurityStatus").textContent = `Error: ${error.message}`; }));
$("saveIndustryClassification").addEventListener("click", () => saveIndustryClassification().catch((error) => { $("industryClassificationStatus").textContent = `Error: ${error.message}`; }));
$("removeIndustryClassification").addEventListener("click", () => removeIndustryClassification().catch((error) => { $("industryClassificationStatus").textContent = `Error: ${error.message}`; }));
$("securityExposureFxBasis").addEventListener("change", updateSecurityExposureCurrencyState);
$("securityExposureCurrencies").addEventListener("input", updateSecurityExposureCurrencyState);
$("addSecurityExposureCurrency").addEventListener("click", () => {
  $("securityExposureCurrencies").insertAdjacentHTML("beforeend", securityExposureCurrencyRow());
  updateSecurityExposureCurrencyState();
});
$("saveSecurityExposure").addEventListener("click", () => saveSecurityExposure().catch((error) => { $("securityExposureStatus").textContent = `Error: ${error.message}`; }));
$("removeSecurityExposure").addEventListener("click", () => removeSecurityExposure().catch((error) => { $("securityExposureStatus").textContent = `Error: ${error.message}`; }));
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
$("savePositionTransaction").addEventListener("click", () => savePositionTransaction().catch((error) => { $("positionTransactionStatus").textContent = `${t("Error")}: ${t(error.message)}`; }));
$("positionTransactionAction").addEventListener("change", syncPositionTransactionLimit);
$("runDividendEvents").addEventListener("click", () => runDividendEvents().catch((error) => { $("eventsStatus").textContent = `Error: ${error.message}`; }));
$("saveAlarmSettings").addEventListener("click", saveVestingAlertSettings);
$("clearAlarms").addEventListener("click", clearAlarms);
$("savePrice").addEventListener("click", () => savePrice().catch((error) => { $("priceStatus").textContent = `Error: ${error.message}`; }));
$("saveDetailPrice").addEventListener("click", () => saveSecurityDetailPrice().catch((error) => { $("securityDetailStatus").textContent = `Error: ${error.message}`; }));
$("loadReports").addEventListener("click", () => loadReports().catch(() => {}));
$("updateReportHistory").addEventListener("click", () => loadReports().catch(() => {}));
$("accountTrendChart").addEventListener("click", (event) => {
  const metric = event.target.closest("[data-report-metric]")?.dataset.reportMetric;
  if (!["value", "profit_percent"].includes(metric)) return;
  state.reportTrendMetric = metric;
  if (state.activeReportTrend) renderAccountTrend(state.activeReportTrend);
  $("accountTrendChart").querySelector(`[data-report-metric="${metric}"]`)?.focus();
});
$("positionPerson").addEventListener("change", () => updatePositionFilters({ scopeChanged: true }));
$("positionAccountType").addEventListener("change", () => updatePositionFilters({ scopeChanged: true }));
$("positionAccount").addEventListener("change", () => { $("positionAccount").title = $("positionAccount").selectedOptions?.[0]?.textContent || ""; updatePositionFilters({ accountChanged: true }); });
$("positionStock").addEventListener("change", () => { $("positionStock").title = $("positionStock").selectedOptions?.[0]?.textContent || ""; updatePositionFilters(); });
$("tradeHistoryPositionStatus").addEventListener("change", () => updatePositionFilters());
$("tradeHistorySearch").addEventListener("input", () => updatePositionFilters());
$("positionSort").addEventListener("change", () => updatePositionFilters());
$("positionSortDirection").addEventListener("change", () => updatePositionFilters());
$("resetPositionFilters").addEventListener("click", resetPositionFilters);
$("retryTradeHistory").addEventListener("click", loadTradeHistory);
$("exportTradeHistoryCsv").addEventListener("click", exportTradeHistoryCsv);
$("exportReportsPdf").addEventListener("click", () => exportReportsPdf().catch((error) => { $("reportsExportStatus").textContent = `Error: ${error.message}`; }));
["reportPerson", "reportAccountType", "reportAccount", "reportLocation", "reportFrom", "reportTo"].forEach((id) => {
  $(id).addEventListener("change", markReportFiltersChanged);
});
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
$("fundAccount").addEventListener("change", () => { renderFundAccountOwners(); updateFundActionStates(); });
$("editFundAccount").addEventListener("change", renderFundAccountOwners);
$("addPensionPeriod").addEventListener("click", addPensionPeriod);
$("addPensionRate").addEventListener("click", addPensionRate);
$("showPensionPeriodEntry").addEventListener("click", openPensionPeriodEntry);
$("cancelPensionPeriodEntry").addEventListener("click", closePensionPeriodEntry);
$("showPensionRateEntry").addEventListener("click", openPensionRateEntry);
$("cancelPensionRateEntry").addEventListener("click", closePensionRateEntry);
$("addPensionScenario").addEventListener("click", addPensionScenario);
$("newPensionScenario").addEventListener("click", newPensionScenario);
$("runPensionSimulation").addEventListener("click", () => runPensionSimulation().catch((error) => { $("pensionSimulationStatus").textContent = `Error: ${error.message}`; }));
$("applyBackupSchedule").addEventListener("click", applyBackupSchedule);
$("localAccountLocation").addEventListener("change", () => syncCurrencyFromLocation("localAccountLocation", "localAccountCurrency"));
$("editAccountLocation").addEventListener("change", () => syncCurrencyFromLocation("editAccountLocation", "editAccountCurrency"));
$("brokerCountry").addEventListener("change", () => syncCurrencyFromLocation("brokerCountry", "brokerCurrency"));
$("priceLocation").addEventListener("change", () => syncCurrencyFromLocation("priceLocation", "priceCurrency"));
["manualSecuritySymbol", "manualSecondarySymbol", "manualUnderlyingSymbol", "securitySymbol", "priceSymbol", "financeReportSymbol", "outlookSymbol"].forEach((id) => {
  $(id).addEventListener("blur", () => { $(id).value = cleanSecuritySymbol($(id).value); });
});

async function startAuthenticatedApp() {
  if (state.authenticatedAppStarted || !currentUser() || currentUser().must_change_password) return;
  state.authenticatedAppStarted = true;
  await loadClientStateFromServer().catch((error) => appWarn("client_state.load_failed", { message: error.message }));
  loadClientStateFromStorage();
  renderCurrentUser();
  loadBrandVersion().catch(() => {});
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

async function initializeApp() {
  loadClientStateFromStorage();
  revealInitializedApp();
  try {
    if (await restoreAuthSession()) await startAuthenticatedApp();
  } catch (error) {
    appWarn("auth.session_failed", { message: error.message });
    showLogin(optionLabel("Unable to verify the session. Sign in again."));
  }
}

initializeApp().catch(reportBackgroundError).finally(revealInitializedApp);
