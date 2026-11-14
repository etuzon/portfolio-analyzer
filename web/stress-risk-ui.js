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

function stressRiskLossAmountText(risk) {
  if (risk?.intrinsic === true) return "";
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
  if (!(typeof sensitivity?.score === "number" && Number.isFinite(sensitivity.score)
      && typeof sensitivity?.loss_pct === "number" && Number.isFinite(sensitivity.loss_pct))) return "";
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
  };
  const prefix = Object.keys(labels).find(key => name === key || name.startsWith(`${key}:`) || name.startsWith(`${key}_`));
  let label = stressRiskText(labels[prefix] || "Adverse scenario");
  if (prefix === "country_crisis" && name.includes(":")) {
    const country = name.split(":").slice(1).join(":");
    const display = typeof countryName === "function" && /^[A-Z]{2}$/.test(country) ? countryName(country) : country;
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

function stressRiskTooltip(risk) {
  const available = typeof risk?.score === "number" && Number.isFinite(risk.score);
  const estimated = !available && typeof risk?.estimated_score === "number" && Number.isFinite(risk.estimated_score);
  const lines = [available ? `${stressRiskText("Stress risk")}: ${stressRiskNumber(risk.score, 0)}/100`
    : estimated ? `${stressRiskText("Estimated stress risk")}: ~${stressRiskNumber(risk.estimated_score, 0)}/100` : stressRiskText("Risk assessment incomplete"),
    stressRiskText("The score measures modeled stress-loss severity, not a probability or forecast.")];
  if (estimated) lines.push(stressRiskText("This estimate uses explicit assumptions. It is separate from a score supported by complete verified inputs."));
  if (typeof risk?.loss_pct === "number" && Number.isFinite(risk.loss_pct)) {
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
    lines.push(stressRiskText("Contribution to portfolio stress loss: {percent}%", { percent: stressRiskNumber(risk.contribution.loss_contribution_pct) }));
    lines.push(stressRiskText("The holding score describes standalone instrument exposure. Its signed portfolio contribution is shown separately."));
    lines.push(stressRiskText("Contribution uses the portfolio's binding scenario; a negative value offsets modeled loss."));
  }
  if (!available && !estimated) lines.push(stressRiskText("Missing inputs do not mean zero risk. Known partial scenarios do not establish a complete score."));
  if (typeof risk?.coverage?.covered_value_percent === "number" && Number.isFinite(risk.coverage.covered_value_percent)) {
    lines.push(stressRiskText("Input coverage: {percent}% of gross securities and positive cash", { percent: stressRiskNumber(risk.coverage.covered_value_percent) }));
  }
  if (risk?.coverage?.whole_wealth_available === false || risk?.coverage?.unmodeled_savings_count > 0) lines.push(stressRiskText("Savings without underlying allocations are excluded; this is securities and cash risk."));
  const debt = risk?.funding?.cash_debt ?? risk?.cash_debt;
  if (typeof debt === "number" && debt > 0) {
    const currency = risk.base_currency || (typeof state !== "undefined" ? state.baseCurrency : "");
    lines.push(`${stressRiskText("Modeled borrowing")}: ${stressRiskNumber(debt, 2)} ${currency}`.trim());
    lines.push(stressRiskText("Borrowing reduces net equity. Cash in another account does not establish transferable funding."));
  }
  if (risk?.net_equity <= 0 && available && risk.score === 100) lines.push(stressRiskText("Exposure or borrowing with nonpositive net equity is scored 100."));
  const seen = new Set();
  for (const gap of Array.isArray(risk?.gaps) ? risk.gaps : []) {
    const key = `${gap?.code || gap}:${gap?.symbol || ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    lines.push(`• ${gap?.symbol ? `${gap.symbol}: ` : ""}${stressRiskGapText(gap?.code || gap)}`);
    if (seen.size >= 6) break;
  }
  lines.push(stressRiskText("Scenario sizes and rating mappings are explicit assumptions. Liquidity, deposit protection and personal suitability are assessed separately."));
  return lines.join("\n");
}

function stressRiskSummaryHtml(risk, options = {}) {
  if (!risk) return "";
  const escape = stressRiskEscape;
  const unavailable = !(typeof risk.score === "number" && Number.isFinite(risk.score));
  const estimate = unavailable && typeof risk.estimated_score === "number" && Number.isFinite(risk.estimated_score);
  const loss = typeof risk.loss_pct === "number" && Number.isFinite(risk.loss_pct)
    ? `<span>${escape(stressRiskText(unavailable && !estimate ? "Known partial modeled loss: {percent}%" : "Largest modeled loss: {percent}%", { percent: stressRiskNumber(risk.loss_pct) }))}</span>` : "";
  const scenario = risk.worst_scenario ? `<small>${escape(stressRiskScenarioLabel(risk.worst_scenario))}</small>` : "";
  const amountText = stressRiskLossAmountText(risk);
  const amount = amountText ? `<span>${escape(amountText)}</span>` : "";
  const sensitivityText = stressRiskForwardSensitivityText(risk);
  const sensitivity = sensitivityText ? `<small>${escape(sensitivityText)}</small><small>${escape(stressRiskText("One rating-bucket downgrade assumption; baseline unchanged."))}</small>` : "";
  const incomplete = unavailable ? `<span class="stress-risk-incomplete">${escape(stressRiskText(estimate ? "Estimate from explicit assumptions" : "Risk assessment incomplete"))}</span>` : "";
  const scope = risk.coverage?.whole_wealth_available === false || risk.coverage?.unmodeled_savings_count > 0
    ? `<small>${escape(stressRiskText("Savings without underlying allocations are excluded; this is securities and cash risk."))}</small>` : "";
  return `<div class="stress-risk-summary${options.compact ? " is-compact" : ""}">${incomplete}${loss}${amount}${scenario}${sensitivity}${scope}</div>`;
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
  return `<details class="stress-risk-gaps"><summary>${escape(stressRiskText("Missing risk inputs"))}</summary><p>${escape(stressRiskText("Complete the missing evidence, then reload risk inputs. A partial calculation is not a complete portfolio score."))}</p><ul>${entries.join("")}</ul></details>`;
}

(() => {
  const session = { target: null, response: null, generation: 0, pending: false, actor: "" };
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
    if (clear) { clear.disabled = session.pending || !session.response || !writable(); clear.hidden = !Object.keys(session.response?.parameters || {}).length; }
    if (element("reloadStressRiskInputs")) element("reloadStressRiskInputs").disabled = session.pending;
    if (element("stressRiskViewerNote")) element("stressRiskViewerNote").hidden = writable();
    element("stressRiskInputsModal")?.querySelector(".modal-card")?.setAttribute("aria-busy", String(session.pending));
  }
  function fill(response) {
    const p = response.parameters || {};
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
      p.plain_nominal_noncallable = input("PlainBond")?.checked === true;
      p.pricing_model = value("PricingModel");
      if (p.pricing_model === "zero_coupon_continuous") p.zero_coupon_confirmed = input("ZeroConfirmed")?.checked === true;
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
    p.assumptions_enabled = input("Assumptions")?.checked === true;
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
    if (["stressRiskInstrumentKind", "stressRiskPricingModel"].includes(event.target.id)) refreshControls();
  });
  document.addEventListener("submit", event => {
    if (event.target.id !== "stressRiskInputsForm") return;
    event.preventDefault();
    mutate(false);
  });
})();
