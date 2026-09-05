(function exposeScenarioModel(root, factory) {
  const model = factory();
  if (typeof module === "object" && module.exports) module.exports = model;
  if (root) root.PortfolioScenarioModel = Object.freeze(model);
})(typeof globalThis === "object" ? globalThis : this, () => {
  "use strict";

  const scenario = (id, label, triggerLabel, coreEnd, nodes) => ({ id, label, triggerLabel, coreEnd, nodes });
  const node = (id, parent, group, label, probability, direction, source = "assumption") => ({
    id, parent, group, label, probability, direction, source,
  });

  const SCENARIOS = Object.freeze([
    scenario("increase", "US interest rates increase", "Federal Reserve raises interest rates", "inc_housing", [
      node("inc_treasury", "", "Core transmission", "US Treasury yields rise", 0.90, "negative", "provided"),
      node("inc_nasdaq", "inc_treasury", "Core transmission", "NASDAQ valuation correction", 0.75, "negative", "provided"),
      node("inc_dollar", "inc_nasdaq", "Core transmission", "US dollar strengthens globally", 0.80, "mixed", "provided"),
      node("inc_tech", "inc_dollar", "High-tech", "Israeli high-tech funding contracts", 0.85, "negative", "provided"),
      node("inc_shekel", "inc_tech", "Core transmission", "Shekel weakens against the dollar", 0.80, "negative", "provided"),
      node("inc_cpi", "inc_shekel", "Core transmission", "Israeli CPI rises", 0.75, "negative", "provided"),
      node("inc_boi", "inc_cpi", "Core transmission", "Bank of Israel raises interest rates", 0.85, "negative", "provided"),
      node("inc_housing", "inc_boi", "Real estate and construction", "Housing activity and prices freeze or fall", 0.70, "negative", "provided"),
      node("inc_banks", "inc_boi", "Banks", "Deposit costs and credit losses pressure bank earnings", 0.64, "negative"),
      node("inc_cards", "inc_boi", "Credit-card companies", "Funding costs and delinquencies pressure card-company earnings", 0.72, "negative"),
      node("inc_nonbank", "inc_boi", "Non-bank lenders", "Funding costs and borrower risk pressure non-bank lenders", 0.78, "negative"),
      node("inc_discretionary", "inc_boi", "Consumer discretionary", "Discretionary demand weakens", 0.68, "negative"),
      node("inc_staples", "inc_cpi", "Consumer staples", "Staples remain relatively defensive despite input inflation", 0.62, "mixed"),
      node("inc_exporters", "inc_shekel", "Exporters", "A weaker shekel supports exporters' shekel revenue", 0.66, "positive"),
      node("inc_importers", "inc_shekel", "Importers and retail", "Imported costs compress importer and retail margins", 0.75, "negative"),
      node("inc_industrials", "inc_boi", "Industrials", "Financing costs and softer demand slow industrial activity", 0.64, "negative"),
      node("inc_energy", "inc_cpi", "Energy and materials", "Currency and input-cost volatility increases", 0.60, "mixed"),
      node("inc_healthcare", "inc_boi", "Healthcare", "Defensive demand offsets financing pressure", 0.58, "mixed"),
      node("inc_utilities", "inc_boi", "Utilities and telecom", "Debt-heavy utilities and telecom face valuation pressure", 0.72, "negative"),
      node("inc_insurers", "inc_boi", "Insurance", "Higher reinvestment income is offset by asset and credit risk", 0.63, "mixed"),
      node("inc_oil", "inc_dollar", "Oil", "A stronger dollar and weaker growth pressure oil unless war disrupts supply", 0.65, "mixed"),
      node("inc_gold", "inc_treasury", "Gold", "Higher real yields pressure gold while geopolitical demand provides support", 0.65, "mixed"),
      node("inc_uranium", "inc_nasdaq", "Uranium", "Structural nuclear demand offsets tighter financing conditions", 0.60, "mixed"),
      node("inc_ai", "inc_nasdaq", "Artificial intelligence", "AI valuations and startup funding compress", 0.80, "negative"),
      node("inc_electricity", "inc_ai", "Electricity and power infrastructure", "AI power demand supports electricity investment despite financing pressure", 0.70, "mixed"),
      node("inc_quantum", "inc_nasdaq", "Quantum computing", "Early-stage quantum funding and valuations contract", 0.78, "negative"),
      node("inc_gov_bond", "inc_boi", "Government bonds", "Shekel government-bond prices fall as yields rise", 0.82, "negative"),
      node("inc_corp_spread", "inc_boi", "Corporate bonds", "Corporate credit spreads widen", 0.70, "negative"),
      node("inc_ig_bond", "inc_corp_spread", "Corporate bonds", "Investment-grade corporate-bond prices fall", 0.75, "negative"),
      node("inc_hy_bond", "inc_corp_spread", "Corporate bonds", "High-yield corporate-bond prices fall", 0.82, "negative"),
      node("inc_money_fund", "inc_boi", "Shekel money-market funds", "Shekel money-market fund yield rises", 0.90, "positive"),
      node("inc_bond_fund", "inc_gov_bond", "Shekel bond mutual funds", "Shekel bond-fund net asset value comes under pressure", 0.78, "negative"),
      node("inc_corp_rating", "inc_corp_spread", "Corporate credit ratings", "Corporate downgrade and negative-outlook risk rises", 0.62, "negative"),
      node("inc_sovereign_rating", "inc_cpi", "Sovereign credit rating", "Sovereign rating pressure rises if inflation and fiscal stress persist", 0.45, "negative"),
    ]),
    scenario("decrease", "US interest rates decrease", "Federal Reserve cuts interest rates", "dec_ta125", [
      node("dec_treasury", "", "Core transmission", "US Treasury yields fall", 0.85, "positive", "provided"),
      node("dec_nasdaq", "dec_treasury", "Core transmission", "Growth and technology stocks rally", 0.80, "positive", "provided"),
      node("dec_risk", "dec_nasdaq", "Core transmission", "Global risk-on sentiment increases", 0.75, "positive", "provided"),
      node("dec_tech", "dec_risk", "High-tech", "Israeli high-tech funding and M&A surge", 0.80, "positive", "provided"),
      node("dec_shekel", "dec_tech", "Core transmission", "Shekel strengthens against the dollar", 0.75, "positive", "provided"),
      node("dec_boi", "dec_shekel", "Core transmission", "Bank of Israel cuts interest rates", 0.80, "positive", "provided"),
      node("dec_ta125", "dec_boi", "Israeli equities", "TA-125 rallies", 0.70, "positive", "provided"),
      node("dec_banks", "dec_boi", "Banks", "Lower credit losses offset pressure on bank interest margins", 0.65, "mixed"),
      node("dec_cards", "dec_boi", "Credit-card companies", "Cheaper funding and stronger spending support card companies", 0.72, "positive"),
      node("dec_nonbank", "dec_boi", "Non-bank lenders", "Refinancing conditions improve for non-bank lenders", 0.75, "positive"),
      node("dec_realestate", "dec_boi", "Real estate and construction", "Housing and construction activity recovers", 0.68, "positive"),
      node("dec_discretionary", "dec_boi", "Consumer discretionary", "Discretionary demand strengthens", 0.70, "positive"),
      node("dec_staples", "dec_shekel", "Consumer staples", "Lower imported costs support staple-company margins", 0.65, "positive"),
      node("dec_exporters", "dec_shekel", "Exporters", "A stronger shekel pressures exporters' translated revenue", 0.65, "negative"),
      node("dec_importers", "dec_shekel", "Importers and retail", "A stronger shekel improves importer and retail margins", 0.74, "positive"),
      node("dec_industrials", "dec_boi", "Industrials", "Cheaper finance supports industrial investment", 0.62, "positive"),
      node("dec_energy", "dec_shekel", "Energy and materials", "Currency relief is offset by global-cycle uncertainty", 0.58, "mixed"),
      node("dec_healthcare", "dec_boi", "Healthcare", "Lower financing costs modestly support healthcare", 0.60, "positive"),
      node("dec_utilities", "dec_boi", "Utilities and telecom", "Financing relief supports debt-heavy utilities and telecom", 0.78, "positive"),
      node("dec_insurers", "dec_boi", "Insurance", "Bond gains are offset by lower reinvestment yields", 0.65, "mixed"),
      node("dec_oil", "dec_risk", "Oil", "A weaker dollar and stronger demand support oil prices", 0.68, "positive"),
      node("dec_gold", "dec_treasury", "Gold", "Lower real yields and a softer dollar support gold", 0.75, "positive"),
      node("dec_uranium", "dec_risk", "Uranium", "Risk-on capital and nuclear investment support uranium", 0.65, "positive"),
      node("dec_ai", "dec_nasdaq", "Artificial intelligence", "AI funding and valuation multiples expand", 0.85, "positive"),
      node("dec_electricity", "dec_ai", "Electricity and power infrastructure", "Cheaper capital and AI demand accelerate power investment", 0.75, "positive"),
      node("dec_quantum", "dec_risk", "Quantum computing", "Early-stage quantum funding expands", 0.78, "positive"),
      node("dec_gov_bond", "dec_boi", "Government bonds", "Shekel government-bond prices rise as yields fall", 0.82, "positive"),
      node("dec_corp_spread", "dec_boi", "Corporate bonds", "Corporate credit spreads tighten", 0.72, "positive"),
      node("dec_ig_bond", "dec_corp_spread", "Corporate bonds", "Investment-grade corporate-bond prices rise", 0.80, "positive"),
      node("dec_hy_bond", "dec_corp_spread", "Corporate bonds", "High-yield corporate-bond prices rise", 0.75, "positive"),
      node("dec_money_fund", "dec_boi", "Shekel money-market funds", "Shekel money-market fund yield falls", 0.90, "negative"),
      node("dec_bond_fund", "dec_gov_bond", "Shekel bond mutual funds", "Shekel bond-fund net asset value rises", 0.80, "positive"),
      node("dec_corp_rating", "dec_corp_spread", "Corporate credit ratings", "Corporate rating outlooks improve", 0.55, "positive"),
      node("dec_sovereign_rating", "dec_shekel", "Sovereign credit rating", "Sovereign rating pressure eases if domestic risk also recedes", 0.50, "positive"),
    ]),
    scenario("unchanged", "US interest rates stay unchanged", "Fed unchanged plus Israeli war, geopolitical, or fiscal shock", "flat_gov_yield", [
      node("flat_rating", "", "Core transmission", "Israeli sovereign credit-rating risk rises", 0.65, "negative", "provided"),
      node("flat_gov_yield", "flat_rating", "Government bonds", "Government-bond yields spike independently of the US", 0.70, "negative", "provided"),
      node("flat_shekel", "flat_rating", "Core transmission", "Domestic risk premium weakens the shekel", 0.75, "negative"),
      node("flat_boi", "flat_shekel", "Core transmission", "Bank of Israel keeps policy restrictive or raises rates", 0.68, "negative"),
      node("flat_tech", "flat_rating", "High-tech", "Geopolitical risk reduces high-tech funding and exits", 0.75, "negative"),
      node("flat_banks", "flat_gov_yield", "Banks", "Credit losses and funding volatility pressure banks", 0.70, "negative"),
      node("flat_cards", "flat_boi", "Credit-card companies", "Household stress raises card delinquencies", 0.72, "negative"),
      node("flat_nonbank", "flat_boi", "Non-bank lenders", "Funding and borrower risk pressure non-bank lenders", 0.80, "negative"),
      node("flat_realestate", "flat_boi", "Real estate and construction", "Financing and demand weaken in real estate and construction", 0.78, "negative"),
      node("flat_discretionary", "flat_boi", "Consumer discretionary", "Domestic uncertainty weakens discretionary demand", 0.75, "negative"),
      node("flat_staples", "flat_shekel", "Consumer staples", "Imported inflation pressures staple-company margins", 0.66, "negative"),
      node("flat_exporters", "flat_shekel", "Exporters", "Currency support is offset by country-risk disruption", 0.62, "mixed"),
      node("flat_importers", "flat_shekel", "Importers and retail", "Currency weakness sharply raises imported costs", 0.82, "negative"),
      node("flat_industrials", "flat_boi", "Industrials", "Risk, labor constraints, and finance costs slow industry", 0.72, "negative"),
      node("flat_energy", "flat_shekel", "Energy and materials", "Supply and currency volatility pressure energy and materials", 0.68, "negative"),
      node("flat_healthcare", "flat_rating", "Healthcare", "Operational and fiscal pressure affects healthcare providers", 0.62, "negative"),
      node("flat_utilities", "flat_gov_yield", "Utilities and telecom", "Higher sovereign yields raise financing costs", 0.70, "negative"),
      node("flat_insurers", "flat_gov_yield", "Insurance", "Bond repricing and credit risk pressure insurers' assets", 0.70, "negative"),
      node("flat_oil", "flat_rating", "Oil", "Regional war adds a supply-risk premium to oil", 0.72, "positive"),
      node("flat_gold", "flat_rating", "Gold", "War and sovereign uncertainty increase safe-haven demand for gold", 0.82, "positive"),
      node("flat_uranium", "flat_rating", "Uranium", "Energy-security demand supports uranium amid supply uncertainty", 0.68, "mixed"),
      node("flat_ai", "flat_tech", "Artificial intelligence", "Israeli AI funding, valuations, and operating continuity weaken", 0.80, "negative"),
      node("flat_electricity", "flat_rating", "Electricity and power infrastructure", "War raises electricity infrastructure and operating risk", 0.72, "negative"),
      node("flat_quantum", "flat_tech", "Quantum computing", "Israeli quantum research and early-stage funding weaken", 0.72, "negative"),
      node("flat_defense", "flat_rating", "Defense and security", "War increases demand for defense and security companies", 0.85, "positive"),
      node("flat_tourism", "flat_rating", "Tourism and aviation", "War sharply reduces tourism and aviation activity", 0.88, "negative"),
      node("flat_corp_spread", "flat_rating", "Corporate bonds", "Corporate credit spreads widen", 0.78, "negative"),
      node("flat_ig_bond", "flat_corp_spread", "Corporate bonds", "Investment-grade corporate-bond prices fall", 0.74, "negative"),
      node("flat_hy_bond", "flat_corp_spread", "Corporate bonds", "High-yield corporate-bond prices fall sharply", 0.85, "negative"),
      node("flat_money_fund", "flat_boi", "Shekel money-market funds", "Shekel money-market fund yield stays high or rises", 0.80, "positive"),
      node("flat_bond_fund", "flat_gov_yield", "Shekel bond mutual funds", "Shekel bond-fund net asset value falls", 0.82, "negative"),
      node("flat_corp_rating", "flat_corp_spread", "Corporate credit ratings", "Corporate downgrade and negative-outlook risk rises", 0.78, "negative"),
    ]),
  ]);

  function finiteProbability(value) {
    if (value === "" || value === null || value === undefined) return null;
    const number = Number(value);
    return Number.isFinite(number) && number >= 0 && number <= 1 ? number : null;
  }

  function defaultSettings() {
    return { selected: "increase", priors: { increase: null, decrease: null, unchanged: null }, localTrigger: null, overrides: {} };
  }

  function normalizeSettings(value) {
    const defaults = defaultSettings();
    const input = value && typeof value === "object" ? value : {};
    const selected = SCENARIOS.some((item) => item.id === input.selected) ? input.selected : defaults.selected;
    const priors = Object.fromEntries(SCENARIOS.map((item) => [item.id, finiteProbability(input.priors?.[item.id])]));
    const validIds = new Set(SCENARIOS.flatMap((item) => item.nodes.map((entry) => entry.id)));
    const overrides = {};
    Object.entries(input.overrides || {}).forEach(([id, probability]) => {
      const normalized = finiteProbability(probability);
      if (validIds.has(id) && normalized !== null) overrides[id] = normalized;
    });
    return { selected, priors, localTrigger: finiteProbability(input.localTrigger), overrides };
  }

  function scenarioById(id) {
    return SCENARIOS.find((item) => item.id === id) || SCENARIOS[0];
  }

  function probabilityFor(entry, settings) {
    return Object.prototype.hasOwnProperty.call(settings.overrides, entry.id)
      ? settings.overrides[entry.id]
      : entry.probability;
  }

  function triggerProbability(definition, settings) {
    const fedPriors = SCENARIOS.map((item) => settings.priors[item.id]);
    if (fedPriors.some((value) => value === null)
      || Math.abs(fedPriors.reduce((sum, value) => sum + value, 0) - 1) >= 0.0001) return null;
    const fedPrior = settings.priors[definition.id];
    if (definition.id !== "unchanged") return fedPrior;
    return settings.localTrigger === null ? null : fedPrior * settings.localTrigger;
  }

  function calculateScenario(id, rawSettings) {
    const definition = scenarioById(id);
    const settings = normalizeSettings(rawSettings);
    const entries = new Map(definition.nodes.map((entry) => [entry.id, entry]));
    const memo = new Map();
    function conditionalFor(nodeId, trail = new Set()) {
      if (memo.has(nodeId)) return memo.get(nodeId);
      if (trail.has(nodeId)) throw new Error(`Scenario cycle detected at ${nodeId}`);
      const entry = entries.get(nodeId);
      if (!entry) throw new Error(`Unknown scenario node ${nodeId}`);
      const nextTrail = new Set(trail).add(nodeId);
      const parentProbability = entry.parent ? conditionalFor(entry.parent, nextTrail) : 1;
      const result = parentProbability * probabilityFor(entry, settings);
      memo.set(nodeId, result);
      return result;
    }
    const trigger = triggerProbability(definition, settings);
    const nodes = definition.nodes.map((entry) => {
      const conditional = conditionalFor(entry.id);
      return {
        ...entry,
        probability: probabilityFor(entry, settings),
        conditional,
        absolute: trigger === null ? null : trigger * conditional,
      };
    });
    return {
      ...definition,
      triggerProbability: trigger,
      nodes,
      headline: nodes.find((entry) => entry.id === definition.coreEnd),
    };
  }

  function pathTo(scenarioId, nodeId, rawSettings) {
    const result = calculateScenario(scenarioId, rawSettings);
    const entries = new Map(result.nodes.map((entry) => [entry.id, entry]));
    const path = [];
    let current = entries.get(nodeId);
    while (current) {
      path.unshift(current);
      current = current.parent ? entries.get(current.parent) : null;
    }
    return path;
  }

  function priorStatus(rawSettings) {
    const settings = normalizeSettings(rawSettings);
    const values = SCENARIOS.map((item) => settings.priors[item.id]);
    const complete = values.every((value) => value !== null);
    const total = complete ? values.reduce((sum, value) => sum + value, 0) : null;
    return { complete, total, valid: complete && Math.abs(total - 1) < 0.0001 };
  }

  return { SCENARIOS, defaultSettings, normalizeSettings, calculateScenario, pathTo, priorStatus };
});
