/* Explain portfolio-risk-v2 inputs; this module does not change its score. */
function riskMissingDataDetails(items, options = {}) {
  const rows = items || [];
  const normalize = options.normalizeField || normalizedField;
  const value = item => {
    const amount = Math.abs(Number(normalize(item, "market_value")));
    return Number.isFinite(amount) ? amount : 0;
  };
  const exposed = rows.filter(item => value(item) > 0);
  const holdingsValue = Number.isFinite(options.holdingsValue) ? options.holdingsValue : exposed.reduce((total, item) => total + value(item), 0);
  const totalValue = Number.isFinite(options.totalValue) ? options.totalValue : holdingsValue;
  const industryRows = options.industryRows || exposed.filter(item =>
    ["EQUITY", "RSU", "ETF", "MUTUALFUND"].includes(String(item.holding?.asset_class || "").toUpperCase())
    && !["money_market", "government_bond", "investment_grade_bond", "high_yield_bond"].includes(item.exposure_profile?.asset_focus));
  const industrySet = new Set(industryRows);
  const details = [];
  const record = (code, affectedRows, denominator, maximum, fraction = () => 1) => {
    if (!(denominator > 0) || !affectedRows.length) return;
    const affectedValue = affectedRows.reduce((total, item) => total + value(item) * fraction(item), 0);
    if (!(affectedValue > 0)) return;
    details.push({
      code,
      weight_basis: code === "economic_currency" ? "total_assets" : "gross_holdings",
      weight_percent: affectedValue / denominator * 100,
      points_before_cap: affectedValue / denominator * maximum,
      symbols: [...new Set(affectedRows.map(item => String(item.holding?.symbol || "")).filter(Boolean))],
      affected: affectedRows.map(item => ({
        symbol: String(item.holding?.symbol || ""),
        stock_market: String(item.holding?.stock_market || ""),
        account_id: String(item.holding?.account_id || ""),
        missing_fields: code === "holding_metadata" ? [
          !item.holding?.currency ? "currency" : "",
          !item.holding?.asset_class ? "asset_class" : "",
        ].filter(Boolean) : [],
      })),
    });
  };
  record("price_history", exposed.filter(item => (item.missing || []).includes("price history")), holdingsValue, 2);
  record("industry", exposed.filter(item => industrySet.has(item) && !industryLabel(item)), holdingsValue, 1.5);
  record("holding_metadata", exposed.filter(item => !item.holding?.asset_class || !item.holding?.currency), holdingsValue, 1.5);
  record("economic_currency", exposed.filter(item => economicCurrencyExposure(item).unknownPercent > 0), totalValue, 1.5,
    item => economicCurrencyExposure(item).unknownPercent / 100);
  return details;
}

function riskMissingDataTooltipLines(details, language = "en", options = {}) {
  if (!Array.isArray(details) || !details.length) return [];
  const he = language === "he";
  const labels = he ? {
    price_history: "היסטוריית מחירים",
    industry: "מגזר או ענף",
    holding_metadata: "מטבע ההחזקה או סוג הנכס",
    economic_currency: "חשיפה כלכלית למטבע שאינה ידועה",
  } : {
    price_history: "Price history",
    industry: "Sector or industry",
    holding_metadata: "Holding currency or asset class",
    economic_currency: "Unknown economic currency exposure",
  };
  const fixes = he ? {
    price_history: "במחירים הוסיפו היסטוריית מחירים שמורה, ואז רעננו את התיק.",
    industry: "בחלוקה לפי ענף בחרו את נייר הערך והשתמשו בסיווג נייר ערך.",
    holding_metadata: "בעריכת המכשיר השלימו את המטבע או את סוג הנכס החסר.",
    economic_currency: "בעריכת החשיפה השלימו את הקצאות המטבע הכלכליות לפי דיווח או אומדן מסומן.",
  } : {
    price_history: "In Prices, add saved price history, then refresh the portfolio.",
    industry: "In Industry split, select the security and use Classify security.",
    holding_metadata: "Edit the instrument to complete its missing currency or asset class.",
    economic_currency: "Edit exposure to complete the economic currency allocations using reported data or a labelled estimate.",
  };
  const number = (value, digits) => new Intl.NumberFormat(he ? "he-IL" : "en-US", {minimumFractionDigits: digits, maximumFractionDigits: digits}).format(value);
  const known = details.filter(detail => labels[detail?.code] && Number.isFinite(detail.weight_percent) && detail.weight_percent > 0);
  if (!known.length) return [];
  if (options.compact) {
    return ["", ...known.map(detail => {
      const points = Number.isFinite(detail.points_before_cap)
        ? (he ? `${number(detail.points_before_cap, 2)} נקודות לפני התקרה המשותפת` : `${number(detail.points_before_cap, 2)} points before the combined cap`)
        : `${number(detail.weight_percent, 1)}%`;
      return `• ${labels[detail.code]}: ${points}`;
    }), he ? "הרחיבו את נתונים חסרים להצגת ניירות הערך המושפעים וצעדי ההשלמה." : "Expand Missing data for affected securities and recovery steps."];
  }
  return [
    "",
    he ? "פירוט הנתונים החסרים:" : "Missing data details:",
    he ? "רכיב הנתונים החסרים הוא ניקוד משוקלל עד 5, ולא מספר השדות החסרים." : "The missing-data component is an exposure-weighted score up to 5, not a count of missing fields.",
    ...known.flatMap(detail => {
      const basis = detail.weight_basis === "total_assets"
        ? (he ? "מהנכסים כולל מזומן חיובי" : "of assets including positive cash")
        : (he ? "מההחזקות ברוטו" : "of gross holdings");
      const entries = (Array.isArray(detail.affected) ? detail.affected : []).filter(entry => entry && typeof entry === "object").map(entry => {
        const symbol = entry.symbol || (he ? "נייר ללא סימול" : "Unnamed security");
        const missing = (Array.isArray(entry.missing_fields) ? entry.missing_fields : []).map(field => field === "currency" ? (he ? "מטבע" : "currency") : field === "asset_class" ? (he ? "סוג נכס" : "asset class") : "").filter(Boolean);
        return `${symbol}${missing.length ? ` (${missing.join(", ")})` : ""}`;
      });
      const securities = [...new Set(entries.length ? entries : (Array.isArray(detail.symbols) ? detail.symbols : []))];
      const limit = options.maxSymbols ?? 12;
      const shown = securities.slice(0, limit).join(", ");
      const more = securities.length > limit ? (he ? ` ועוד ${securities.length - limit}` : ` and ${securities.length - limit} more`) : "";
      const points = Number.isFinite(detail.points_before_cap) ? (he ? ` · ${number(detail.points_before_cap, 2)} נקודות לפני התקרה המשותפת` : ` · ${number(detail.points_before_cap, 2)} points before the combined cap`) : "";
      return [
        `• ${labels[detail.code]}: ${number(detail.weight_percent, 1)}% ${basis}${points}`,
        `  ${he ? "ניירות" : "Securities"}: ${shown || (he ? "לא זמין" : "Unavailable")}${more}`,
        `  ${fixes[detail.code]}`,
      ];
    }),
  ];
}


function riskDataQualityHtml(risk) {
  const points = risk?.components?.data_quality;
  const details = risk?.quality_details;
  if (!Number.isFinite(points) || (!(points > 0) && !details?.length)) return "";
  const language = typeof state !== "undefined" && state.language === "he" ? "he" : "en";
  const he = language === "he";
  const escape = value => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
  const formatted = new Intl.NumberFormat(he ? "he-IL" : "en-US", {maximumFractionDigits: 2}).format(points);
  const summary = he ? `נתונים חסרים: ${formatted}/5 נקודות` : `Missing data: ${formatted}/5 points`;
  const lines = riskMissingDataTooltipLines(details, language, {maxSymbols: Infinity}).filter(Boolean).slice(1);
  const content = lines.length ? lines.map(line => `<p>${escape(line)}</p>`).join("") : `<p>${escape(he ? "פירוט הנתונים החסרים לא נשמר במדידה זו." : "Missing-data details were not saved for this observation.")}</p>`;
  return `<details class="risk-data-quality"><summary>${escape(summary)}</summary><div class="risk-data-quality-content" tabindex="0" role="region" aria-label="${escape(summary)}">${content}</div></details>`;
}
