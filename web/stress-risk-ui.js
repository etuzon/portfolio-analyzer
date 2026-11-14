/* Presentation and local evidence editor for the shared stress-loss risk model. */
function stressRiskLanguage() {
  return typeof state !== "undefined" && state.language === "he" ? "he" : "en";
}

function stressRiskText(text, values = {}) {
  const translated = window.PortfolioI18n?.translate(text, stressRiskLanguage()) || text;
  return translated.replace(/\{(\w+)\}/g, (match, key) => Object.hasOwn(values, key) ? String(values[key]) : match);
}

function stressRiskEscape(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
}

function stressRiskNumber(value, digits = 1) {
  return new Intl.NumberFormat(stressRiskLanguage() === "he" ? "he-IL" : "en-US", {
    maximumFractionDigits: digits, minimumFractionDigits: digits,
  }).format(value);
}

function stressRiskLossPercent(risk) {
  const valid = value => typeof value === "number" && Number.isFinite(value) && value >= 0;
  const automatic = ["portfolio-risk-provisional-v2", "portfolio-risk-provisional-v3"].includes(risk?.provisional_model);
  if (automatic && !Number.isFinite(risk?.score) && !Number.isFinite(risk?.estimated_score)) {
    if (risk?.provisional_scope === "known_values" || risk?.provisional_range) return null;
    if (valid(risk?.provisional_loss_pct)) return risk.provisional_loss_pct;
    return risk?.provisional_net_equity > 0 && valid(risk?.provisional_loss)
      ? risk.provisional_loss / risk.provisional_net_equity * 100 : null;
  }
  return valid(risk?.loss_pct) ? risk.loss_pct : null;
}

function stressRiskDisplay(risk) {
  const valid = value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100;
  const current = risk?.model === "portfolio-risk-v4";
  const available = valid(risk?.score);
  const estimated = !available && valid(risk?.estimated_score);
  const automatic = !available && !estimated && ["portfolio-risk-provisional-v2", "portfolio-risk-provisional-v3"].includes(risk?.provisional_model);
  const unknownScope = Boolean(automatic && (risk?.provisional_scope === "known_values" || risk?.provisional_range));
  const range = unknownScope ? {min:valid(risk?.provisional_range?.min) ? risk.provisional_range.min : 0,
    max:valid(risk?.provisional_range?.max) ? risk.provisional_range.max : 100} : null;
  const provisional = !available && !estimated && !unknownScope && valid(risk?.provisional_score);
  const compatibilityScore = available ? risk.score : estimated ? risk.estimated_score : provisional ? risk.provisional_score : null;
  const equity = automatic ? risk?.provisional_net_equity : risk?.net_equity;
  const nonpositiveEquity = current && !unknownScope && compatibilityScore === 100
    && typeof equity === "number" && Number.isFinite(equity) && equity <= 0;
  const rawLossPct = current && compatibilityScore !== null && !unknownScope && !nonpositiveEquity ? stressRiskLossPercent(risk) : null;
  const number = current ? compatibilityScore === null ? null : rawLossPct : compatibilityScore;
  const missing = provisional || unknownScope || (Array.isArray(risk?.gaps) && risk.gaps.length > 0) || risk?.coverage?.complete === false;
  const unit = number === null ? "" : current ? "%" : "/100";
  const value = nonpositiveEquity ? `${estimated || provisional ? "~" : ""}${stressRiskText("Nonpositive equity")}`
    : range && !current ? `${stressRiskNumber(range.min,0)}–${stressRiskNumber(range.max,0)}`
      : number === null ? stressRiskText("Incomplete") : `${estimated || provisional ? "~" : ""}${stressRiskNumber(number, current ? 1 : 0)}`;
  return { number, available, estimated, provisional, automatic, unknownScope, range, missing,
    current, legacy: !current, rawLossPct, compatibilityScore, nonpositiveEquity, unit, value, fullValue: `${value}${unit}`,
    metricLabel: stressRiskText(current ? "Stress loss" : "Legacy stress score"),
    ceiling: provisional && !automatic && risk.provisional_basis === "missing_valuation_ceiling",
    statusLabel: unknownScope ? stressRiskText("Uncertain scope") : (automatic && provisional || estimated) ? stressRiskText("Estimate") : provisional ? stressRiskText("Partial data") : "" };
}

function stressRiskProvisionalExplanation(risk) {
  const display = stressRiskDisplay(risk);
  if (display.automatic) {
    return stressRiskText(risk?.provisional_scope === "known_values" || risk?.provisional_range
      ? display.current
        ? "Incomplete exposure or pricing inputs prevent a whole-portfolio percentage. Known-position estimates are shown separately."
        : "Incomplete exposure or pricing inputs prevent a whole-portfolio point estimate. The range reflects unresolved scope; known-position estimates are shown separately."
      : "This estimate uses asset-class scenarios where complete inputs are unavailable. Cash reduces market exposure, and foreign-currency cash still carries currency risk. Missing data does not add a capital-loss penalty.");
  }
  if (risk?.provisional_basis === "unmodeled_exposure_allowance") {
    return stressRiskText("This provisional score adds a precautionary allowance equal to 100% of unmodeled long exposure to supported scenario losses. No rating or bond terms are inferred.");
  }
  return stressRiskText("A precautionary ceiling is shown because valuation or payoff inputs prevent a complete loss calculation. A score of 100 here is not evidence of insolvency or certain loss.");
}

function stressRiskLossAmountText(risk) {
  if (risk?.intrinsic === true) return "";
  if (stressRiskDisplay(risk).automatic) {
    if (risk.provisional_scope === "known_values" || risk.provisional_range) return "";
    if (!(typeof risk.provisional_loss === "number" && Number.isFinite(risk.provisional_loss))) return "";
    const currency = risk?.base_currency || (typeof state !== "undefined" ? state.baseCurrency : "");
    return currency ? stressRiskText("Estimated scenario loss amount: {amount} {currency}", {
      amount:stressRiskNumber(risk.provisional_loss,2),currency}) : "";
  }
  const completeAmount = typeof risk?.stress_loss === "number" && Number.isFinite(risk.stress_loss);
  const amount = completeAmount ? risk.stress_loss : risk?.partial_stress_loss;
  if (typeof amount !== "number" || !Number.isFinite(amount)) return "";
  const currency = risk?.base_currency || (typeof state !== "undefined" ? state.baseCurrency : "");
  if (!currency) return "";
  return stressRiskText(completeAmount ? "Modeled loss amount: {amount} {currency}" : "Known partial modeled loss amount: {amount} {currency}", {
    amount: stressRiskNumber(amount, 2), currency,
  });
}

function stressRiskForwardSensitivityText(risk) {
  const sensitivity = risk?.forward_sensitivity;
  if (!(typeof sensitivity?.loss_pct === "number" && Number.isFinite(sensitivity.loss_pct))) return "";
  if (risk?.model === "portfolio-risk-v4") return stressRiskText("Negative rating sensitivity: {percent}% scenario loss", {
    percent: stressRiskNumber(sensitivity.loss_pct),
  });
  if (!(typeof sensitivity?.score === "number" && Number.isFinite(sensitivity.score))) return "";
  return stressRiskText("Negative rating sensitivity: {score}/100 · {percent}% modeled loss", {
    score: stressRiskNumber(sensitivity.score, 0), percent: stressRiskNumber(sensitivity.loss_pct),
  });
}

function stressRiskScenarioLabel(code) {
  const name = String(code || "");
  const labels = {
    recession: "Recession", inflation: "Inflation and rising rates", rally: "Market rally",
    fx_only: "Currency movement", issuer_distress: "Issuer distress", issuer_rally: "Issuer price increase",
    country_crisis: "Country crisis", sovereign_crisis: "Sovereign credit stress",
    negative_rating_sensitivity: "Negative rating sensitivity",
    nonpositive_estimated_equity: "Nonpositive estimated net equity",
  };
  const prefix = Object.keys(labels).find(key => name === key || name.startsWith(`${key}:`) || name.startsWith(`${key}_`));
  let label = stressRiskText(labels[prefix] || "Adverse scenario");
  if (prefix === "country_crisis" && name.includes(":")) {
    const country = name.split(":").slice(1).join(":");
    const display = /^generic:[A-Z]{3}$/.test(country) ? `${stressRiskText("Unspecified country")} (${country.split(":")[1]})`
      : typeof countryName === "function" && /^[A-Z]{2}$/.test(country) ? countryName(country) : country;
    if (display) label += ` · ${display}`;
  }
  if (["issuer_distress", "issuer_rally"].includes(prefix) && name.includes(":")) {
    const issuer = name.split(":").slice(1).join(":");
    if (issuer) label += ` · ${issuer}`;
  }
  if (prefix && /(?:all_foreign|[A-Z]{3})_down$/.test(name)) label += ` · ${stressRiskText("Foreign currency weakens")}`;
  if (prefix && /(?:all_foreign|[A-Z]{3})_up$/.test(name)) label += ` · ${stressRiskText("Foreign currency strengthens")}`;
  return label;
}

function stressRiskGapText(code) {
  const labels = {
    valuation: "A holding valuation or quantity is missing.",
    valuation_stale: "The saved valuation needs a current observation.",
    cash: "An account's signed cash balance is missing.",
    cash_currency_breakdown: "The currencies of account cash and borrowing are missing.",
    fx: "A required conversion or economic currency exposure is missing.",
    asset_class: "The asset class is missing.",
    unsupported_instrument: "This instrument needs a supported pricing model.",
    issuer_identity: "The legal issuer has not been established.",
    country: "The issuer or underlying country exposure is missing.",
    country_exposure: "The underlying economic country allocation is incomplete.",
    country_currency: "The relevant country crisis currency is missing.",
    sovereign_currency_basis: "The sovereign debt's local- or foreign-currency rating basis is missing.",
    country_rating: "An eligible sovereign rating is missing.",
    credit_rating: "An eligible issue or issuer credit rating is missing.",
    rating_stale: "The applicable rating evidence needs a current check.",
    rating_unverified: "The rating is a manual assumption, without verified evidence.",
    bond_kind: "Choose corporate or direct sovereign debt.",
    bond_terms: "Confirm the bond's supported payment and redemption terms.",
    bond_cashflows: "The bond's future cash flows are missing.",
    bond_yield: "The continuous discount yield is missing.",
    bond_maturity: "A supported future redemption date is missing.",
    current_spread: "The current credit spread is needed to bound tightening gains in joint scenarios.",
    country_sensitivity: "The corporate bond's country sensitivity is missing.",
    fund_lookthrough: "The fund needs underlying issuer, credit, rate, country and currency allocations; an exposure profile alone is insufficient.",
    parameters_stale: "The bond's current yield or spread evidence is older than 7 days.",
    parameters_unverified: "User-entered instrument terms require explicit assumption mode for an estimate.",
    parameters_unavailable: "Risk inputs could not be loaded.",
  };
  return stressRiskText(labels[String(code || "").split(":")[0]] || "A required risk input is missing or unsupported.");
}

function stressRiskProxyAssumptionLines(risk) {
  const names = {
    money_market_proxy:"Money-market fund proxy", money_market:"Money-market fund proxy",
    bond_duration_proxy:"Bond sensitivity estimate", unrated_credit_proxy:"Credit risk estimated without inventing an agency rating",
    bond_duration_maturity_bound:"Sensitivity proxy capped by verified remaining maturity",
    credit_tightening_omitted:"Credit-tightening gains omitted because the current spread is missing",
    bond_fund_proxy:"Bond-fund category proxy", equity_fund_proxy:"Equity-fund category proxy", sector_fund_proxy:"Sector-fund category proxy",
    country_stress_proxy:"Country stress proxy", country_sensitivity_proxy:"Country spread sensitivity proxy",
    security_key_issuer_proxy:"Security identity used as a concentration proxy",
    government_bond_proxy:"Government-bond rate and credit proxy", sovereign_bond_proxy:"Government-bond rate and credit proxy",
    corporate_bond_proxy:"Corporate-bond rate and credit proxy", bond_proxy:"Bond rate and credit proxy",
    equity_proxy:"Equity market proxy", fund_proxy:"Fund asset-allocation proxy",
    unknown_asset_proxy:"Exposure or payoff model unavailable", recovery_model_required:"Recovery and payoff model required",
    currency_proxy:"Currency exposure proxy",
    quote_currency_proxy:"Trading currency used as an explicit currency proxy", economic_currency_estimate:"Declared economic currency estimate",
    exposure_profile:"Declared exposure profile", stale_valuation:"Saved price used for an estimate",
    saved_valuation:"Saved price used for an estimate", undated_valuation:"Undated saved value used for an estimate",
    missing_rating_proxy:"Credit risk estimated without inventing an agency rating",
    duration_proxy:"Bond sensitivity estimate", issuer_identity_proxy:"Issuer grouping estimate",
  };
  const dateText = value => {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ""));
    return match ? `${match[3]}/${match[2]}/${match[1]}` : "";
  };
  const lines = [], seen = new Set();
  for (const assumption of Array.isArray(risk?.provisional_assumptions) ? risk.provisional_assumptions : []) {
    const code = typeof assumption === "string" ? assumption : assumption?.code;
    const label = stressRiskText(names[code] || "Additional scenario assumption");
    const symbol = typeof assumption === "object" ? assumption?.symbol || "" : "";
    const observed = dateText(typeof assumption === "object" ? assumption?.valuation_date || assumption?.as_of || assumption?.source_date : "");
    const details = [];
    if (code === "bond_duration_maturity_bound") details.push(stressRiskText("This bound does not establish actual coupon duration."));
    if (code === "country_stress_proxy" && assumption?.basis === "issuer_domicile_proxy") details.push(stressRiskText("Issuer domicile used as a country-exposure proxy"));
    if (code === "country_stress_proxy" && assumption?.basis === "generic_country_proxy") details.push(stressRiskText("Generic country scenario assumption"));
    if (typeof assumption?.loss_fraction === "number" && Number.isFinite(assumption.loss_fraction)) details.push(stressRiskText("Local adverse move: {percent}%", {percent:stressRiskNumber(Math.abs(assumption.loss_fraction)*100)}));
    if (typeof assumption?.duration_years === "number" && Number.isFinite(assumption.duration_years)) details.push(stressRiskText("Duration assumption: {years} years", {years:stressRiskNumber(assumption.duration_years)}));
    if (typeof assumption?.spread_bps === "number" && Number.isFinite(assumption.spread_bps)) details.push(stressRiskText("Spread widening assumption: {bps} basis points", {bps:stressRiskNumber(assumption.spread_bps,0)}));
    const maturity = dateText(assumption?.maturity_date);
    if (maturity) details.push(`${stressRiskText("Maturity date")}: ${maturity}`);
    const referenceRetrieved = dateText(assumption?.reference_retrieved_at);
    if (referenceRetrieved) details.push(`${stressRiskText("Reference retrieval date")}: ${referenceRetrieved}`);
    if (assumption?.currency) details.push(stressRiskText("Currency proxy: {currency}", {currency:typeof currencyDisplayLabel === "function" ? currencyDisplayLabel(assumption.currency) : assumption.currency}));
    const currencyExposures = assumption?.currency_exposures;
    if (currencyExposures && !Array.isArray(currencyExposures) && typeof currencyExposures === "object") {
      const allocations = Object.entries(currencyExposures).filter(([currency, fraction]) => /^[A-Z]{3}$/.test(currency)
        && typeof fraction === "number" && Number.isFinite(fraction) && fraction >= 0 && fraction <= 1)
        .map(([currency, fraction]) => `${currency} ${stressRiskNumber(fraction*100)}%`);
      if (allocations.length) details.push(stressRiskText("Currency allocation assumption: {allocation}", {allocation:allocations.join(", ")}));
    }
    if (observed) details.push(`${stressRiskText(code === "stale_valuation" ? "Saved price date" : "Source observation date")}: ${observed}`);
    const row = `${symbol ? `${symbol}: ` : ""}${label}${details.length ? ` · ${details.join(" · ")}` : ""}`;
    if (!seen.has(row)) { seen.add(row); lines.push(`• ${row}`); }
  }
  const observed = dateText(risk?.provisional_valuation_date);
  if (observed) lines.unshift(`${stressRiskText("Saved price date")}: ${observed}`);
  return lines.length ? [stressRiskText("Estimate assumptions:"), ...lines] : [];
}

function stressRiskTooltip(risk) {
  const display = stressRiskDisplay(risk);
  const { available, estimated, provisional, automatic, unknownScope, range, missing, current } = display;
  const lines = current ? [`${display.metricLabel}: ${display.fullValue}${display.statusLabel ? ` · ${display.statusLabel}` : ""}`,
    stressRiskText(risk?.intrinsic === true
      ? "The percentage is the largest scenario loss relative to standalone instrument value, independent of position size."
      : "The percentage is the largest scenario loss relative to positive net equity."),
    stressRiskText("Fixed hypothetical shocks revalue current exposures immediately. These are assumptions, not forecasts, loss probabilities or a validated general risk rating.")]
    : [available ? `${stressRiskText("Legacy stress score")}: ${stressRiskNumber(risk.score, 0)}/100`
    : estimated ? `${stressRiskText("Estimated stress risk")}: ~${stressRiskNumber(risk.estimated_score, 0)}/100`
      : unknownScope ? `${stressRiskText("Risk range")}: ${stressRiskNumber(range.min,0)}–${stressRiskNumber(range.max,0)} · ${stressRiskText("Uncertain scope")}`
      : automatic && provisional ? `${stressRiskText("Estimated stress risk")}: ~${stressRiskNumber(risk.provisional_score, 0)}/100 · ${stressRiskText("Estimate")}`
      : provisional ? `${stressRiskText("Provisional stress risk")}: ~${stressRiskNumber(risk.provisional_score, 0)}/100 · ${stressRiskText("Partial data")}`
        : stressRiskText("Risk assessment incomplete"),
    stressRiskText("Legacy scale: twice the modeled loss percentage, capped at 100. Compare only matching model versions and currencies.")];
  if (current && unknownScope) lines.push(stressRiskText("The whole-portfolio loss percentage is unavailable. A capped index range is not an economic loss bound; leveraged or short positions can lose more than net equity."));
  if (display.nonpositiveEquity) lines.push(stressRiskText("A loss percentage is undefined when net equity is nonpositive and exposure or borrowing remains. The saved boundary flag is not a measured 100% loss or a verified insolvency finding."));
  if (estimated) lines.push(stressRiskText("This estimate uses explicit assumptions. It is separate from a score supported by complete verified inputs."));
  if (provisional || unknownScope) {
    lines.push(stressRiskProvisionalExplanation(risk));
    const currency = risk.base_currency || (typeof state !== "undefined" ? state.baseCurrency : "");
    if (automatic) {
      if (!unknownScope && risk.provisional_score === 100 && typeof risk.provisional_net_equity === "number"
          && risk.provisional_net_equity <= 0) lines.push(stressRiskText("Reported values imply nonpositive net equity with exposure or borrowing. This is an estimate using the stated saved values, not a verified insolvency finding."));
      if (!unknownScope && risk.provisional_net_equity > 0 && typeof risk.provisional_loss === "number" && Number.isFinite(risk.provisional_loss)) {
        lines.push(stressRiskText("Largest estimated scenario loss: {percent}%", {percent:stressRiskNumber(risk.provisional_loss/risk.provisional_net_equity*100)}));
      }
      const knownScore = risk.provisional_known_score ?? (unknownScope ? risk.provisional_score : null);
      if (current && unknownScope && typeof risk.provisional_known_loss_pct === "number" && Number.isFinite(risk.provisional_known_loss_pct)) {
        lines.push(stressRiskText("Known positions only: ~{percent}% scenario loss", {percent:stressRiskNumber(risk.provisional_known_loss_pct)}));
      } else if (!current && unknownScope && typeof knownScore === "number" && Number.isFinite(knownScore)) {
        lines.push(stressRiskText("Supported known positions only: ~{score}/100", {score:stressRiskNumber(knownScore,0)}));
      }
      if (!risk.intrinsic && currency && typeof risk.provisional_proxy_gross === "number" && Number.isFinite(risk.provisional_proxy_gross)) {
        lines.push(stressRiskText("Value using asset-class proxies: {amount} {currency}", {amount:stressRiskNumber(risk.provisional_proxy_gross,2),currency}));
      }
      lines.push(...stressRiskProxyAssumptionLines(risk));
    } else if (!risk.intrinsic && currency && typeof risk.provisional_loss === "number" && Number.isFinite(risk.provisional_loss)) {
      lines.push(stressRiskText("Provisional loss including allowance: {amount} {currency}", { amount: stressRiskNumber(risk.provisional_loss, 2), currency }));
    }
    if (!automatic && !risk.intrinsic && currency && typeof risk.provisional_unmodeled_gross === "number" && Number.isFinite(risk.provisional_unmodeled_gross)) {
      lines.push(stressRiskText("Unmodeled exposure allowance: {amount} {currency}", { amount: stressRiskNumber(risk.provisional_unmodeled_gross, 2), currency }));
    }
    if (!automatic && risk.provisional_model === "portfolio-risk-provisional-v1") lines.push(stressRiskText("This saved result uses the earlier precautionary method. Current estimates use asset-class scenarios."));
  }
  if (missing) lines.push(stressRiskText("Some risk inputs are missing. Review the details below."));
  if (!automatic && typeof risk?.loss_pct === "number" && Number.isFinite(risk.loss_pct)) {
    lines.push(stressRiskText(!available && !estimated ? "Known partial modeled loss: {percent}%" : "Largest modeled loss: {percent}%", { percent: stressRiskNumber(risk.loss_pct) }));
    if (risk.worst_scenario) lines.push(`${stressRiskText("Binding scenario")}: ${stressRiskScenarioLabel(risk.worst_scenario)}`);
  }
  const amount = stressRiskLossAmountText(risk);
  if (amount) lines.push(amount);
  const sensitivity = stressRiskForwardSensitivityText(risk);
  if (sensitivity) {
    lines.push(sensitivity);
    lines.push(stressRiskText("This separate sensitivity assumes one broad rating-bucket downgrade. Published grades and the baseline score are unchanged."));
  }
  if (typeof risk?.contribution?.loss_contribution_pct === "number" && Number.isFinite(risk.contribution.loss_contribution_pct)) {
    lines.push(stressRiskText(current
      ? "Contribution to portfolio loss: {percent} percentage points of net equity"
      : "Contribution to portfolio stress loss: {percent}%", { percent: stressRiskNumber(risk.contribution.loss_contribution_pct) }));
    lines.push(stressRiskText("The holding score describes standalone instrument exposure. Its signed portfolio contribution is shown separately."));
    lines.push(stressRiskText("Contribution uses the portfolio's binding scenario; a negative value offsets modeled loss."));
  }
  if (!available && !estimated) lines.push(stressRiskText("Missing inputs do not mean zero risk. Known partial scenarios do not establish a complete score."));
  if (typeof risk?.coverage?.covered_value_percent === "number" && Number.isFinite(risk.coverage.covered_value_percent)) {
    lines.push(stressRiskText(automatic ? "Full-model input coverage: {percent}% of gross securities and positive cash" : "Input coverage: {percent}% of gross securities and positive cash", { percent: stressRiskNumber(risk.coverage.covered_value_percent) }));
  }
  if (current && !risk?.intrinsic) lines.push(stressRiskText("Employee equity and savings without underlying allocations are excluded; this is not a whole-wealth assessment."));
  else if (risk?.coverage?.whole_wealth_available === false || risk?.coverage?.unmodeled_savings_count > 0) lines.push(stressRiskText("Savings without underlying allocations are excluded; this is securities and cash risk."));
  const debt = risk?.funding?.cash_debt ?? risk?.cash_debt;
  if (typeof debt === "number" && debt > 0) {
    const currency = risk.base_currency || (typeof state !== "undefined" ? state.baseCurrency : "");
    lines.push(`${stressRiskText("Modeled borrowing")}: ${stressRiskNumber(debt, 2)} ${currency}`.trim());
    lines.push(stressRiskText("Borrowing reduces net equity. Cash in another account does not establish transferable funding."));
  }
  if (!current && risk?.net_equity <= 0 && available && risk.score === 100) lines.push(stressRiskText("Exposure or borrowing with nonpositive net equity is scored 100."));
  const seen = new Set();
  for (const gap of Array.isArray(risk?.gaps) ? risk.gaps : []) {
    const key = `${gap?.code || gap}:${gap?.symbol || ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    lines.push(`• ${gap?.symbol ? `${gap.symbol}: ` : ""}${stressRiskGapText(gap?.code || gap)}`);
  }
  lines.push(stressRiskText(current
    ? "Scenario sizes and rating mappings are explicit assumptions. Liquidity, custody, deposit protection, purchasing power and personal suitability are assessed separately."
    : "Scenario sizes and rating mappings are explicit assumptions. Liquidity, deposit protection and personal suitability are assessed separately."));
  return lines.join("\n");
}

function stressRiskSummaryHtml(risk, options = {}) {
  if (!risk) return "";
  const escape = stressRiskEscape;
  const display = stressRiskDisplay(risk);
  const unavailable = !display.available;
  const estimate = display.estimated;
  const percent = display.current ? display.rawLossPct : !display.automatic ? risk.loss_pct : null;
  const lossText = typeof percent === "number" && Number.isFinite(percent)
    ? stressRiskText(display.current
      ? risk.intrinsic ? "Standalone scenario loss: {percent}%" : "Largest scenario loss: {percent}% of net equity"
      : unavailable && !estimate ? "Known partial modeled loss: {percent}%" : "Largest modeled loss: {percent}%", { percent: stressRiskNumber(percent) })
    : display.current && display.unknownScope && typeof risk.provisional_known_loss_pct === "number" && Number.isFinite(risk.provisional_known_loss_pct)
      ? stressRiskText("Known positions only: ~{percent}% scenario loss", {percent:stressRiskNumber(risk.provisional_known_loss_pct)}) : "";
  const loss = lossText ? `<span>${escape(lossText)}</span>` : "";
  const scenarioCode = display.nonpositiveEquity ? "" : display.automatic ? risk.provisional_worst_scenario : risk.worst_scenario;
  const scenario = scenarioCode ? `<small>${escape(stressRiskScenarioLabel(scenarioCode))}</small>` : "";
  const amountText = stressRiskLossAmountText(risk);
  const amount = amountText ? `<span>${escape(amountText)}</span>` : "";
  const sensitivityText = stressRiskForwardSensitivityText(risk);
  const sensitivity = sensitivityText ? `<small>${escape(sensitivityText)}</small><small>${escape(stressRiskText("One rating-bucket downgrade assumption; baseline unchanged."))}</small>` : "";
  const provisional = display.automatic ? `<small class="stress-risk-provisional-note">${escape(stressRiskText(display.unknownScope
    ? "Incomplete exposure or pricing inputs; review missing risk data." : "Estimate using asset-class scenarios; data quality is shown separately."))}</small>`
    : display.provisional ? `<small class="stress-risk-provisional-note">${escape(stressRiskText(risk.provisional_basis === "unmodeled_exposure_allowance"
      ? "Includes a precautionary allowance for unmodeled exposure." : "Precautionary ceiling; complete inputs are still needed."))}</small>` : "";
  const incomplete = display.nonpositiveEquity ? `<span class="stress-risk-incomplete">${escape(stressRiskText("Loss percentage undefined with nonpositive equity."))}</span>`
    : unavailable && !display.provisional && !display.unknownScope ? `<span class="stress-risk-incomplete">${escape(stressRiskText(estimate ? "Estimate from explicit assumptions" : "Risk assessment incomplete"))}</span>` : "";
  const scope = risk.coverage?.whole_wealth_available === false || risk.coverage?.unmodeled_savings_count > 0
    ? `<small>${escape(stressRiskText(display.current
      ? "Employee equity and savings without underlying allocations are excluded."
      : "Savings without underlying allocations are excluded; this is securities and cash risk."))}</small>` : "";
  return `<div class="stress-risk-summary${options.compact ? " is-compact" : ""}">${incomplete}${provisional}${loss}${amount}${scenario}${sensitivity}${scope}</div>`;
}

function stressRiskGapsHtml(risk) {
  const gaps = Array.isArray(risk?.gaps) ? risk.gaps : [];
  if (!gaps.length) return "";
  const escape = stressRiskEscape;
  const seen = new Set();
  const entries = gaps.filter(gap => {
    const key = `${gap?.code || gap}:${gap?.symbol || ""}:${gap?.security_key || ""}`;
    if (seen.has(key)) return false;
    seen.add(key); return true;
  }).map(gap => {
    const key = gap?.security_key || "";
    const symbol = gap?.symbol || "";
    const code = String(gap?.code || gap).split(":")[0];
    const [listingSymbol, market = "", currency = ""] = key.split("|");
    let action = "";
    if (["valuation", "valuation_stale"].includes(code)) {
      action = `<button type="button" class="secondary compact-button" data-modal="pricesModal">${escape(stressRiskText("Review saved prices"))}</button>`;
    } else if (["cash", "cash_currency_breakdown"].includes(code)) {
      action = `<button type="button" class="secondary compact-button" data-modal="accountsModal">${escape(stressRiskText("Review accounts"))}</button>`;
    } else if (key && ["credit_rating", "country_rating", "rating_stale", "rating_unverified", "issuer_identity", "country"].includes(code)) {
      action = `<button type="button" class="secondary compact-button" data-security-detail-symbol="${escape(listingSymbol || symbol)}" data-security-detail-market-key="${escape(market)}" data-security-detail-stock-market="${escape(market)}" data-security-detail-currency="${escape(currency)}">${escape(stressRiskText("Review ratings and sources"))}</button>`;
    } else if (key && ["fx", "country_exposure"].includes(code)) {
      action = `<button type="button" class="secondary compact-button" data-stress-risk-exposure="${escape(listingSymbol || symbol)}" data-stress-risk-market="${escape(market)}">${escape(stressRiskText("Review exposure profile"))}</button>`;
    } else if (code === "fund_lookthrough") {
      action = `<button type="button" class="secondary compact-button" data-modal="xrayModal">${escape(stressRiskText("Review fund holdings"))}</button>`;
    } else if (key) {
      action = `<button type="button" class="secondary compact-button" data-risk-inputs-security-key="${escape(key)}" data-risk-inputs-symbol="${escape(symbol)}">${escape(stressRiskText("Review risk inputs"))}</button>`;
    }
    return `<li><div>${symbol ? `<bdi dir="ltr">${escape(symbol)}</bdi> · ` : ""}${escape(stressRiskGapText(gap?.code || gap))}</div>${action}</li>`;
  });
  return `<details class="stress-risk-gaps"><summary>${escape(stressRiskText("Missing risk inputs"))}</summary><p>${escape(stressRiskText("Complete the missing evidence, then reload risk inputs. A partial calculation is not a complete portfolio score."))}</p><ul>${entries.join("")}</ul><div class="risk-retrieval-actions"><button type="button" class="secondary compact-button" data-open-risk-input-retrieval="run">${escape(stressRiskText("Find missing risk data"))}</button><button type="button" class="secondary compact-button" data-open-risk-input-retrieval="schedule">${escape(stressRiskText("Schedule risk data updates"))}</button></div></details>`;
}

(() => {
  const session = { target: null, response: null, generation: 0, pending: false, actor: "", touched: new Set() };
  const element = id => document.getElementById(id);
  const actor = () => typeof currentUser === "function" ? String(currentUser()?.id || currentUser()?.username || "") : "";
  const writable = () => typeof canWrite === "function" && canWrite();
  const text = stressRiskText;
  const setStatus = value => { if (element("stressRiskInputsStatus")) element("stressRiskInputsStatus").textContent = value; };
  const fields = ["InstrumentKind", "PricingModel", "Maturity", "ZeroConfirmed", "Cashflows", "Yield", "Spread", "CountrySensitivity", "SovereignBasis", "CountryCode", "CountryCurrency", "CountryBasis", "PlainBond", "Assumptions", "AsOf", "Source", "Notes"];
  const input = name => element(`stressRisk${name}`);
  const value = name => input(name)?.value.trim() || "";
  const assign = (name, next) => { if (input(name)) input(name).value = next ?? ""; };
  const date = raw => typeof parseDateInput === "function" ? parseDateInput(raw) : /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : "";
  const displayedDate = raw => typeof formatDate === "function" ? formatDate(raw) : raw || "";
  function refreshControls() {
    const isBond = ["corporate_bond", "sovereign_bond"].includes(value("InstrumentKind"));
    const government = value("InstrumentKind") === "sovereign_bond";
    if (element("stressRiskFundNote")) element("stressRiskFundNote").hidden = value("InstrumentKind") !== "fund";
    if (element("stressRiskBondFields")) element("stressRiskBondFields").hidden = !isBond;
    if (element("stressRiskZeroFields")) element("stressRiskZeroFields").hidden = value("PricingModel") !== "zero_coupon_continuous";
    if (element("stressRiskCashflowFields")) element("stressRiskCashflowFields").hidden = value("PricingModel") !== "cashflows_continuous";
    if (element("stressRiskSovereignFields")) element("stressRiskSovereignFields").hidden = !government;
    if (element("stressRiskCorporateFields")) element("stressRiskCorporateFields").hidden = !isBond || government;
    fields.forEach(name => { if (input(name)) input(name).disabled = session.pending || !writable(); });
    const save = element("saveStressRiskInputs");
    const clear = element("clearStressRiskInputs");
    if (save) save.disabled = session.pending || !session.response || !writable();
    if (clear) { clear.disabled = session.pending || !session.response || !writable(); clear.hidden = !Object.keys(session.response?.local_parameters ?? session.response?.parameters ?? {}).length; }
    if (element("reloadStressRiskInputs")) element("reloadStressRiskInputs").disabled = session.pending;
    if (element("stressRiskViewerNote")) element("stressRiskViewerNote").hidden = writable();
    element("stressRiskInputsModal")?.querySelector(".modal-card")?.setAttribute("aria-busy", String(session.pending));
  }
  function fill(response) {
    // Public facts remain read-only context; a manual save must never copy them
    // into a fresh user-entered parameter bag or replace their observation date.
    const p = response.local_parameters ?? response.parameters ?? {};
    session.touched.clear();
    assign("InstrumentKind", p.instrument_kind);
    assign("PricingModel", p.pricing_model);
    assign("Maturity", displayedDate(p.maturity_date));
    assign("Cashflows", (p.cashflows || []).map(row => `${displayedDate(row.date)}, ${row.amount}`).join("\n"));
    assign("Yield", typeof p.continuous_yield === "number" ? p.continuous_yield * 100 : "");
    assign("Spread", p.current_spread_bps);
    assign("CountrySensitivity", p.country_sensitivity);
    assign("SovereignBasis", p.sovereign_currency_basis);
    assign("CountryCode", p.country_code);
    assign("CountryCurrency", p.country_currency);
    assign("CountryBasis", p.country_basis);
    if (input("PlainBond")) input("PlainBond").checked = p.plain_nominal_noncallable === true;
    if (input("ZeroConfirmed")) input("ZeroConfirmed").checked = p.zero_coupon_confirmed === true;
    if (input("Assumptions")) input("Assumptions").checked = p.assumptions_enabled === true;
    assign("AsOf", displayedDate(p.as_of));
    assign("Source", p.source_url); assign("Notes", p.notes);
    const sources = element("stressRiskRatingSources");
    if (sources) sources.textContent = text("Agency ratings are read from saved verified evidence. This editor does not create or verify an agency rating.");
    const research = element("stressRiskResearchedInputs");
    if (research) {
      const labels = {instrument_kind:"Instrument type for risk",pricing_model:"Bond pricing model",maturity_date:"Contractual redemption date",cashflows:"Future bond payments",
        continuous_yield:"Continuous discount yield (%)",current_spread_bps:"Current credit spread (basis points)",country_sensitivity:"Country spread sensitivity (0–1)",
        sovereign_currency_basis:"Sovereign rating currency basis",country_code:"Country",country_currency:"Country crisis currency",country_basis:"Country exposure basis",
        plain_nominal_noncallable:"Plain nominal noncallable bond",zero_coupon_confirmed:"Confirmed zero coupon",as_of:"Information date"};
      const names = {equity:"Equity",fund:"Fund",corporate_bond:"Corporate bond",sovereign_bond:"Direct sovereign bond",
        zero_coupon_continuous:"Confirmed zero-coupon redemption",cashflows_continuous:"Explicit future payment schedule",local_currency:"Local-currency debt",foreign_currency:"Foreign-currency debt",
        economic_exposure:"Reported economic exposure",issuer_domicile_proxy:"Issuer domicile proxy"};
      const show = (key, value) => {
        if (typeof value === "boolean") return text(value ? "Yes" : "No");
        if (["maturity_date","as_of"].includes(key)) return displayedDate(value);
        if (key === "cashflows") return (value || []).map(row=>`${displayedDate(row.date)}, ${stressRiskNumber(row.amount,2)}`).join("; ");
        if (key === "continuous_yield") return `${stressRiskNumber(value * 100,2)}%`;
        if (key === "country_code" && typeof countryDisplayLabel === "function") return countryDisplayLabel(value);
        if (key === "country_currency" && typeof currencyDisplayLabel === "function") return currencyDisplayLabel(value);
        if (typeof value === "number") return stressRiskNumber(value,2);
        return text(names[value] || String(value));
      };
      const rows = Object.entries(response.researched_parameters || {}).filter(([key])=>labels[key]);
      research.hidden = !rows.length;
      const seen = new Set();
      const links = (response.source_evidence || []).filter(row => {
        if (!row?.source_url || seen.has(row.source_url)) return false;
        seen.add(row.source_url); return true;
      }).map((row,index) => {
        try {
          const url = new URL(row.source_url);
          if (!["https:","http:"].includes(url.protocol) || url.username || url.password) return "";
          const dateText = row.as_of ? `${text("Information date")}: ${displayedDate(row.as_of)}` : "";
          return `<li><a href="${stressRiskEscape(url.href)}" target="_blank" rel="noopener noreferrer">${stressRiskEscape(text("Source {number}",{number:index+1}))}</a>${dateText ? ` · ${stressRiskEscape(dateText)}` : ""}</li>`;
        } catch { return ""; }
      }).filter(Boolean);
      research.innerHTML = rows.length ? `<h3>${stressRiskEscape(text("Researched risk evidence"))}</h3><p>${stressRiskEscape(text("These read-only researched values keep their source dates. The editable fields below contain local overrides only."))}</p><dl>${rows.map(([key,value])=>`<div><dt>${stressRiskEscape(text(labels[key]))}</dt><dd>${stressRiskEscape(show(key,value))}</dd></div>`).join("")}</dl>${links.length ? `<ul>${links.join("")}</ul>` : ""}` : "";
    }
    refreshControls();
  }
  async function reload() {
    if (!session.target) return;
    const generation = ++session.generation;
    const target = { ...session.target };
    const user = actor();
    session.pending = true; setStatus(text("Loading saved risk inputs")); refreshControls();
    try {
      const query = new URLSearchParams({ symbol: target.symbol || "", stock_market: target.stock_market || "", currency: target.currency || "" });
      if (target.security_key) query.set("security_key", target.security_key);
      const response = await api(`/api/securities/risk-inputs?${query}`);
      if (generation !== session.generation || user !== actor()) return;
      session.response = response;
      session.target = { ...target, security_key: response.security_key || target.security_key };
      fill(response); setStatus("");
    } catch (_) {
      if (generation !== session.generation || user !== actor()) return;
      setStatus(text("Could not load risk inputs. The current draft is retained; use Reload saved inputs to retry."));
    } finally {
      if (generation === session.generation) { session.pending = false; refreshControls(); }
    }
  }
  function parameters() {
    const p = { instrument_kind: value("InstrumentKind") };
    const local = session.response?.local_parameters ?? session.response?.parameters ?? {};
    const supplied = (name, key) => session.touched.has(name) || Object.hasOwn(local, key);
    const fail = (message, name) => { input(name)?.focus(); throw Error(text(message)); };
    if (!p.instrument_kind) fail("Choose the instrument type.", "InstrumentKind");
    const optionalNumber = (name, key, scale = 1) => {
      if (!value(name)) return;
      const number = Number(value(name));
      if (!Number.isFinite(number)) fail("Enter a finite number.", name);
      p[key] = number * scale;
    };
    const isBond = ["corporate_bond", "sovereign_bond"].includes(p.instrument_kind);
    if (isBond) {
      if (supplied("PlainBond", "plain_nominal_noncallable")) p.plain_nominal_noncallable = input("PlainBond")?.checked === true;
      if (value("PricingModel")) p.pricing_model = value("PricingModel");
      if (p.pricing_model === "zero_coupon_continuous" && supplied("ZeroConfirmed", "zero_coupon_confirmed")) p.zero_coupon_confirmed = input("ZeroConfirmed")?.checked === true;
      if (p.pricing_model === "zero_coupon_continuous" && value("Maturity")) {
        p.maturity_date = date(value("Maturity"));
        if (!p.maturity_date) fail("Enter a valid date as dd/mm/yyyy.", "Maturity");
      }
      if (p.pricing_model === "cashflows_continuous" && value("Cashflows")) {
        p.cashflows = value("Cashflows").split(/\n+/).filter(line => line.trim()).map(line => {
          const parts = line.split(",");
          const paymentDate = date(parts[0]?.trim() || "");
          const amount = parts[1]?.trim() ? Number(parts[1].trim()) : NaN;
          if (parts.length !== 2 || !paymentDate || !Number.isFinite(amount) || amount <= 0) fail("Enter one cash flow per line: dd/mm/yyyy, positive amount.", "Cashflows");
          return { date: paymentDate, amount };
        });
      }
      if (p.pricing_model === "cashflows_continuous") optionalNumber("Yield", "continuous_yield", .01);
      optionalNumber("Spread", "current_spread_bps");
      if (p.instrument_kind === "corporate_bond") optionalNumber("CountrySensitivity", "country_sensitivity");
      if (p.instrument_kind === "sovereign_bond" && value("SovereignBasis")) p.sovereign_currency_basis = value("SovereignBasis");
    }
    if (value("CountryCode")) p.country_code = value("CountryCode").toUpperCase();
    if (value("CountryCurrency")) p.country_currency = value("CountryCurrency").toUpperCase();
    if (value("CountryBasis")) p.country_basis = value("CountryBasis");
    if (supplied("Assumptions", "assumptions_enabled")) p.assumptions_enabled = input("Assumptions")?.checked === true;
    if (p.current_spread_bps < 0) fail("Credit spread must be zero or positive.", "Spread");
    if (p.country_sensitivity < 0 || p.country_sensitivity > 1) fail("Country sensitivity must be between 0 and 1.", "CountrySensitivity");
    if (p.country_code && !/^[A-Z]{2}$/.test(p.country_code)) fail("Use a two-letter country ISO code.", "CountryCode");
    if (p.country_currency && !/^[A-Z]{3}$/.test(p.country_currency)) fail("Use a three-letter currency code.", "CountryCurrency");
    p.as_of = date(value("AsOf"));
    if (!p.as_of) fail("Enter the information date as dd/mm/yyyy.", "AsOf");
    p.source_url = value("Source"); p.notes = value("Notes");
    if (!p.source_url && !p.notes) fail("Add a source URL or a note describing these assumptions.", "Source");
    return p;
  }
  async function mutate(remove = false) {
    if (!writable() || session.pending || !session.response || session.actor !== actor()) return;
    let p;
    try { if (!remove) p = parameters(); } catch (error) { setStatus(error.message); return; }
    const response = session.response;
    const generation = session.generation;
    const user = actor();
    session.pending = true; setStatus(text(remove ? "Clearing local risk inputs" : "Saving risk inputs")); refreshControls();
    try {
      const body = { security_key: response.security_key, expected_identity: response.identity_token, expected_revision: response.revision };
      if (!remove) body.parameters = p;
      const saved = await api("/api/securities/risk-inputs", { method: remove ? "DELETE" : "PUT", body: JSON.stringify(body) });
      if (generation !== session.generation || user !== actor()) return;
      session.response = saved; fill(saved);
      setStatus(text(remove ? "Local risk inputs cleared." : "Risk inputs saved. Scores reload from the updated evidence."));
      document.dispatchEvent(new CustomEvent("stress-risk-inputs-changed", { detail: { security_key: saved.security_key || response.security_key } }));
    } catch (error) {
      if (generation !== session.generation || user !== actor()) return;
      setStatus(text(error?.status === 409
        ? "These risk inputs changed elsewhere. Your draft is retained; reload saved inputs before saving again."
        : "Could not save risk inputs. Your draft is retained; correct the inputs or retry."));
    } finally {
      if (generation === session.generation) { session.pending = false; refreshControls(); }
    }
  }
  window.openStressRiskInputs = async (target, returnFocus = document.activeElement) => {
    const next = typeof target === "string" ? { security_key: target } : { ...target };
    if (!next.security_key && !next.symbol) return;
    // Security keys encode listing identity; explicit fields supplied by callers win.
    const parts = String(next.security_key || "").split("|");
    if (!next.symbol) next.symbol = parts[0] || "";
    if (!next.stock_market) next.stock_market = parts[1] || "";
    if (!next.currency) next.currency = parts[2] || "";
    session.target = next; session.response = null; session.actor = actor(); session.generation++;
    element("stressRiskInputsSecurity").textContent = next.symbol || next.security_key;
    fill({ parameters: {} });
    openModal("stressRiskInputsModal", returnFocus);
    await reload();
    if (!element("stressRiskInputsModal").hidden) element("stressRiskInputsTitle")?.focus({ preventScroll: true });
  };
  document.addEventListener("click", event => {
    const exposure = event.target.closest?.("[data-stress-risk-exposure]");
    if (exposure && typeof openSecurityExposure === "function") {
      event.preventDefault();
      openSecurityExposure(exposure.dataset.stressRiskExposure, exposure.dataset.stressRiskMarket || "", exposure);
    }
    const entry = event.target.closest?.("[data-risk-inputs-security-key]");
    if (entry) {
      event.preventDefault();
      window.openStressRiskInputs({ security_key: entry.dataset.riskInputsSecurityKey, symbol: entry.dataset.riskInputsSymbol,
        stock_market: entry.dataset.riskInputsMarket, currency: entry.dataset.riskInputsCurrency }, entry);
    }
    if (event.target.closest?.("#saveStressRiskInputs")) mutate(false);
    if (event.target.closest?.("#clearStressRiskInputs")) mutate(true);
    if (event.target.closest?.("#reloadStressRiskInputs")) reload();
  });
  document.addEventListener("change", event => {
    const name = String(event.target.id || "").replace(/^stressRisk/, "");
    if (fields.includes(name) && event.target.closest?.("#stressRiskInputsForm")) session.touched.add(name);
    if (["stressRiskInstrumentKind", "stressRiskPricingModel"].includes(event.target.id)) refreshControls();
  });
  document.addEventListener("input", event => {
    const name = String(event.target.id || "").replace(/^stressRisk/, "");
    if (fields.includes(name) && event.target.closest?.("#stressRiskInputsForm")) session.touched.add(name);
  });
  document.addEventListener("submit", event => {
    if (event.target.id !== "stressRiskInputsForm") return;
    event.preventDefault();
    mutate(false);
  });
})();
