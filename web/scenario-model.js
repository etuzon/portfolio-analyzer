(function exposeScenarioModel(root, factory) {
  const model = factory();
  if (typeof module === "object" && module.exports) module.exports = model;
  if (root) root.PortfolioScenarioModel = Object.freeze(model);
})(typeof globalThis === "object" ? globalThis : this, () => {
  "use strict";

  const scenario = (id, label, triggerLabel, coreEnd, nodes) => ({
    id, label, triggerLabel, coreEnd, nodes, kind: "fed", category: "United States and Israel",
  });
  const independentScenario = (id, label, triggerLabel, category, coreEnd, nodes) => ({
    id, label, triggerLabel, category, coreEnd, nodes, kind: "independent",
  });
  const tagsFor = (tags = {}) => ({
    countries: Array.isArray(tags.countries) ? tags.countries : [],
    sectors: Array.isArray(tags.sectors) ? tags.sectors : [],
    currencies: Array.isArray(tags.currencies) ? tags.currencies : [],
    assetClasses: Array.isArray(tags.assetClasses) ? tags.assetClasses : [],
    keywords: Array.isArray(tags.keywords) ? tags.keywords : [],
  });
  const inferredTags = (group, label) => {
    const text = `${group} ${label}`.toLowerCase();
    const assetClasses = [];
    const currencies = [];
    const keywords = [group];
    if (text.includes("bond") || text.includes("credit rating")) {
      assetClasses.push("BOND");
      keywords.push("government bond", "corporate bond", "fixed income", "treasury");
    }
    if (text.includes("fund")) assetClasses.push("MUTUALFUND", "ETF");
    if (text.includes("shekel")) currencies.push("ILS");
    if (text.includes("gold")) keywords.push("gold", "precious metal");
    if (text.includes("uranium")) keywords.push("uranium", "nuclear");
    return { sectors: [group], assetClasses, currencies, keywords };
  };
  const node = (id, parent, group, label, probability, direction, source = "assumption", metadata = {}) => ({
    id,
    parent,
    group,
    label,
    probability,
    direction,
    source,
    impactMagnitude: Number.isFinite(Number(metadata.impactMagnitude)) ? Math.abs(Number(metadata.impactMagnitude)) : (direction === "mixed" ? 0.02 : 0.05),
    horizon: metadata.horizon || "3–12 months",
    lag: metadata.lag || "1–3 months",
    persistence: metadata.persistence || "6–18 months",
    confidence: metadata.confidence || (source === "provided" ? "High" : "Medium"),
    correlation: metadata.correlation || "Medium",
    asOf: metadata.asOf || "05/09/2026",
    tags: tagsFor(metadata.tags || inferredTags(group, label)),
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

  const TRIGGER_MODULES = Object.freeze([
    independentScenario("china_downturn", "China property and demand downturn", "China property and debt stress intensifies", "China", "chn_israel_exports", [
      node("chn_demand", "", "China demand", "Chinese domestic demand weakens", 0.75, "negative", "assumption", { impactMagnitude: 0.06, confidence: "High", tags: { countries: ["China"], sectors: ["China"], keywords: ["China", "Chinese"] } }),
      node("chn_commodities", "chn_demand", "Commodities", "China commodity imports contract", 0.70, "negative", "assumption", { impactMagnitude: 0.08, tags: { sectors: ["Materials", "Energy", "Mining"], keywords: ["commodity", "mining", "copper", "iron", "steel"] } }),
      node("chn_metals", "chn_commodities", "Metals and mining", "Industrial metal prices weaken", 0.75, "negative", "assumption", { impactMagnitude: 0.10, tags: { sectors: ["Materials", "Mining"], keywords: ["copper", "iron", "steel", "metals", "mining"] } }),
      node("chn_oil", "chn_commodities", "Oil", "Oil demand and prices weaken", 0.60, "negative", "assumption", { impactMagnitude: 0.08, tags: { sectors: ["Energy", "Oil & Gas"], keywords: ["oil", "petroleum", "energy"] } }),
      node("chn_exporters", "chn_commodities", "Global exporters", "Global industrial exporters lose demand", 0.65, "negative", "assumption", { impactMagnitude: 0.07, tags: { sectors: ["Industrials", "Materials"], keywords: ["industrial", "export", "manufacturing"] } }),
      node("chn_israel_exports", "chn_exporters", "Israeli exporters", "Israeli industrial, water, agritech, and chip exports weaken", 0.55, "negative", "assumption", { impactMagnitude: 0.06, horizon: "6–18 months", tags: { countries: ["Israel"], sectors: ["Industrials", "Technology"], keywords: ["water", "agritech", "semiconductor", "industrial"] } }),
      node("chn_cny", "chn_demand", "Currencies", "Renminbi weakens and Asian currencies face pressure", 0.72, "mixed", "assumption", { impactMagnitude: 0.05, tags: { currencies: ["CNY", "CNH"], keywords: ["China", "Asia"] } }),
    ]),
    independentScenario("china_stimulus", "China stimulus and demand recovery", "China launches effective fiscal and property stimulus", "China", "chs_israel_exports", [
      node("chs_activity", "", "China demand", "Infrastructure and household activity recover", 0.70, "positive", "assumption", { impactMagnitude: 0.06, tags: { countries: ["China"], keywords: ["China", "Chinese"] } }),
      node("chs_demand", "chs_activity", "Commodities and technology", "Commodity and technology demand rises", 0.75, "positive", "assumption", { impactMagnitude: 0.08, tags: { sectors: ["Materials", "Energy", "Technology"], keywords: ["commodity", "mining", "semiconductor", "technology"] } }),
      node("chs_exporters", "chs_demand", "Global exporters", "Global exporters and Asian supply chains strengthen", 0.65, "positive", "assumption", { impactMagnitude: 0.07, tags: { sectors: ["Industrials", "Technology", "Materials"], keywords: ["industrial", "export", "manufacturing"] } }),
      node("chs_israel_exports", "chs_exporters", "Israeli exporters", "Israeli technology, water, and industrial exports strengthen", 0.55, "positive", "assumption", { impactMagnitude: 0.06, horizon: "6–18 months", tags: { countries: ["Israel"], sectors: ["Industrials", "Technology"], keywords: ["water", "agritech", "semiconductor", "industrial"] } }),
      node("chs_metals", "chs_demand", "Metals and mining", "Industrial metals and uranium gain demand support", 0.72, "positive", "assumption", { impactMagnitude: 0.09, tags: { sectors: ["Materials", "Mining"], keywords: ["uranium", "copper", "iron", "metals", "mining"] } }),
    ]),
    independentScenario("china_trade", "US–China trade and technology escalation", "US–China tariffs and export controls escalate", "China", "cht_israel_tech", [
      node("cht_tariffs", "", "Global trade", "Tariffs and export controls broaden", 0.80, "negative", "assumption", { impactMagnitude: 0.05, tags: { countries: ["China", "United States"], sectors: ["Industrials"], keywords: ["trade", "export", "manufacturing"] } }),
      node("cht_chips", "cht_tariffs", "Semiconductors", "Semiconductor and critical-mineral supply is disrupted", 0.70, "negative", "assumption", { impactMagnitude: 0.10, tags: { sectors: ["Semiconductors", "Technology", "Materials"], keywords: ["semiconductor", "chip", "rare earth", "critical mineral"] } }),
      node("cht_ai_cost", "cht_chips", "Artificial intelligence", "AI and electronics costs rise", 0.75, "negative", "assumption", { impactMagnitude: 0.08, tags: { sectors: ["Technology", "Semiconductors"], keywords: ["AI", "artificial intelligence", "electronics", "chip"] } }),
      node("cht_israel_tech", "cht_ai_cost", "Israeli high-tech", "Israeli high-tech margins, funding, and exports weaken", 0.65, "negative", "assumption", { impactMagnitude: 0.08, tags: { countries: ["Israel"], sectors: ["Technology", "Semiconductors"], keywords: ["software", "cyber", "AI", "semiconductor"] } }),
      node("cht_minerals", "cht_chips", "Critical minerals", "Strategic-mineral prices and substitution investment rise", 0.72, "positive", "assumption", { impactMagnitude: 0.12, tags: { sectors: ["Materials", "Mining"], keywords: ["rare earth", "critical mineral", "uranium", "lithium"] } }),
    ]),
    independentScenario("europe_recession", "Eurozone recession and ECB response", "Eurozone demand contracts materially", "Europe", "eur_israel_exports", [
      node("eur_imports", "", "European demand", "European import demand falls", 0.75, "negative", "assumption", { impactMagnitude: 0.06, tags: { countries: ["Europe"], keywords: ["Europe", "European", "Eurozone"] } }),
      node("eur_industry", "eur_imports", "Industrials", "European industry and discretionary activity weaken", 0.65, "negative", "assumption", { impactMagnitude: 0.08, tags: { sectors: ["Industrials", "Consumer Cyclical"], keywords: ["industrial", "automotive", "consumer discretionary"] } }),
      node("eur_israel_exports", "eur_industry", "Israeli exporters", "Israeli exports, tourism, and business services to Europe weaken", 0.60, "negative", "assumption", { impactMagnitude: 0.06, tags: { countries: ["Israel"], sectors: ["Industrials", "Technology", "Travel"], keywords: ["export", "tourism", "software", "industrial"] } }),
      node("eur_ecb", "eur_imports", "Interest rates", "ECB easing lowers euro bond yields", 0.70, "positive", "assumption", { impactMagnitude: 0.05, tags: { currencies: ["EUR"], assetClasses: ["BOND"], keywords: ["European bond", "euro bond"] } }),
      node("eur_currency", "eur_ecb", "Currencies", "Euro weakens against the dollar", 0.65, "mixed", "assumption", { impactMagnitude: 0.05, tags: { currencies: ["EUR"], keywords: ["euro"] } }),
    ]),
    independentScenario("japan_carry", "Japan rate shock and carry-trade unwind", "Bank of Japan tightening triggers a yen carry unwind", "Japan", "jpy_risk_assets", [
      node("jpy_unwind", "", "Global liquidity", "Leveraged yen-funded positions unwind", 0.75, "negative", "assumption", { impactMagnitude: 0.07, lag: "Days to weeks", tags: { currencies: ["JPY"], keywords: ["Japan", "yen"] } }),
      node("jpy_selloff", "jpy_unwind", "Global equities", "Global risk assets sell off", 0.70, "negative", "assumption", { impactMagnitude: 0.10, lag: "Days to weeks", tags: { assetClasses: ["EQUITY", "ETF", "MUTUALFUND"], keywords: ["equity", "stock", "growth"] } }),
      node("jpy_risk_assets", "jpy_selloff", "Israeli high-tech", "Israeli technology valuations and funding come under pressure", 0.65, "negative", "assumption", { impactMagnitude: 0.08, tags: { countries: ["Israel"], sectors: ["Technology"], keywords: ["software", "cyber", "AI", "technology"] } }),
      node("jpy_havens", "jpy_unwind", "Gold and government bonds", "Safe-haven demand supports gold and high-quality government bonds", 0.60, "positive", "assumption", { impactMagnitude: 0.05, tags: { assetClasses: ["BOND"], keywords: ["gold", "government bond", "treasury"] } }),
    ]),
    independentScenario("india_asean_growth", "India and ASEAN growth acceleration", "India and ASEAN manufacturing growth accelerates", "Asia", "ias_israel_exports", [
      node("ias_manufacturing", "", "Asian manufacturing", "Manufacturing and infrastructure investment rises", 0.70, "positive", "assumption", { impactMagnitude: 0.06, horizon: "6–18 months", tags: { countries: ["India", "Singapore", "Vietnam", "Indonesia"], sectors: ["Industrials"], keywords: ["India", "ASEAN", "manufacturing"] } }),
      node("ias_demand", "ias_manufacturing", "Energy and materials", "Energy and raw-material demand rises", 0.65, "positive", "assumption", { impactMagnitude: 0.07, tags: { sectors: ["Energy", "Materials"], keywords: ["oil", "gas", "commodity", "materials"] } }),
      node("ias_oil", "ias_demand", "Oil", "Structural Asian demand supports oil prices", 0.60, "positive", "assumption", { impactMagnitude: 0.07, tags: { sectors: ["Energy", "Oil & Gas"], keywords: ["oil", "petroleum", "energy"] } }),
      node("ias_israel_exports", "ias_manufacturing", "Israeli exporters", "Demand for Israeli water, agritech, cyber, and defense solutions rises", 0.60, "positive", "assumption", { impactMagnitude: 0.07, horizon: "6–24 months", tags: { countries: ["Israel"], sectors: ["Technology", "Industrials", "Defense"], keywords: ["water", "agritech", "cyber", "defense"] } }),
    ]),
    independentScenario("taiwan_conflict", "Taiwan Strait semiconductor disruption", "A Taiwan Strait blockade or conflict disrupts trade", "Asia", "twn_israel_tech", [
      node("twn_chips", "", "Semiconductors", "Advanced semiconductor supply is disrupted", 0.90, "negative", "assumption", { impactMagnitude: 0.18, lag: "Days to weeks", tags: { countries: ["Taiwan"], sectors: ["Semiconductors", "Technology"], keywords: ["semiconductor", "chip", "electronics"] } }),
      node("twn_costs", "twn_chips", "Artificial intelligence", "AI, data-center, automotive, and electronics costs spike", 0.80, "negative", "assumption", { impactMagnitude: 0.12, tags: { sectors: ["Technology", "Semiconductors", "Automotive"], keywords: ["AI", "data center", "chip", "electronics"] } }),
      node("twn_equities", "twn_costs", "Global equities", "Global equities reprice growth and supply-chain risk", 0.75, "negative", "assumption", { impactMagnitude: 0.15, tags: { assetClasses: ["EQUITY", "ETF", "MUTUALFUND"], keywords: ["equity", "stock", "growth"] } }),
      node("twn_israel_tech", "twn_equities", "Israeli high-tech", "Israeli chip, AI, and hardware companies face valuation and supply pressure", 0.65, "negative", "assumption", { impactMagnitude: 0.12, tags: { countries: ["Israel"], sectors: ["Technology", "Semiconductors"], keywords: ["AI", "chip", "hardware", "semiconductor"] } }),
      node("twn_gold", "twn_chips", "Gold", "Geopolitical safe-haven demand supports gold", 0.78, "positive", "assumption", { impactMagnitude: 0.10, tags: { keywords: ["gold", "precious metal"] } }),
    ]),
    independentScenario("gulf_opec", "Gulf and OPEC oil-supply shock", "OPEC supply restraint or Gulf disruption lifts oil", "Middle East", "gulf_bonds", [
      node("gulf_oil", "", "Oil", "Oil prices rise sharply", 0.80, "positive", "assumption", { impactMagnitude: 0.15, lag: "Days to weeks", tags: { sectors: ["Energy", "Oil & Gas"], keywords: ["oil", "petroleum", "energy"] } }),
      node("gulf_inflation", "gulf_oil", "Global inflation", "Transport, manufacturing, and food inflation rises", 0.75, "negative", "assumption", { impactMagnitude: 0.06, tags: { sectors: ["Transportation", "Industrials", "Consumer Defensive"], keywords: ["airline", "shipping", "food", "industrial"] } }),
      node("gulf_rates", "gulf_inflation", "Interest rates", "Central banks keep rates higher for longer", 0.65, "negative", "assumption", { impactMagnitude: 0.05, tags: { sectors: ["Real Estate", "Financial Services"], keywords: ["real estate", "mortgage", "lender"] } }),
      node("gulf_bonds", "gulf_rates", "Government and corporate bonds", "Bond prices fall and refinancing pressure rises", 0.70, "negative", "assumption", { impactMagnitude: 0.07, tags: { assetClasses: ["BOND"], keywords: ["bond", "fixed income"] } }),
      node("gulf_swf", "gulf_oil", "Gulf investment", "Higher Gulf revenue supports sovereign investment and regional projects", 0.60, "positive", "assumption", { impactMagnitude: 0.06, horizon: "6–24 months", tags: { sectors: ["Industrials", "Technology", "Infrastructure"], keywords: ["infrastructure", "technology", "construction"] } }),
    ]),
    independentScenario("russia_ukraine", "Russia–Ukraine war escalation", "Russia–Ukraine war disrupts energy, grain, and fertilizer supply", "Europe", "ruk_israel_imports", [
      node("ruk_supply", "", "Energy and agriculture", "Energy, grain, and fertilizer prices rise", 0.75, "negative", "assumption", { impactMagnitude: 0.12, tags: { sectors: ["Energy", "Agriculture", "Materials"], keywords: ["oil", "gas", "grain", "fertilizer"] } }),
      node("ruk_eu_cpi", "ruk_supply", "European inflation", "European inflation and industrial costs rise", 0.70, "negative", "assumption", { impactMagnitude: 0.07, tags: { countries: ["Europe"], sectors: ["Industrials"], keywords: ["Europe", "industrial", "manufacturing"] } }),
      node("ruk_israel_imports", "ruk_eu_cpi", "Israeli importers", "Israeli food, agriculture, and industrial import costs rise", 0.60, "negative", "assumption", { impactMagnitude: 0.07, tags: { countries: ["Israel"], sectors: ["Consumer Defensive", "Industrials", "Agriculture"], keywords: ["food", "agriculture", "industrial", "import"] } }),
      node("ruk_defense", "ruk_supply", "Defense and security", "European and global defense spending rises", 0.80, "positive", "assumption", { impactMagnitude: 0.10, horizon: "6–24 months", tags: { sectors: ["Defense", "Aerospace"], keywords: ["defense", "aerospace", "security"] } }),
      node("ruk_gold", "ruk_supply", "Gold", "War-risk hedging supports gold", 0.70, "positive", "assumption", { impactMagnitude: 0.08, tags: { keywords: ["gold", "precious metal"] } }),
    ]),
    independentScenario("global_credit", "Global credit and refinancing shock", "A major borrower, bank, or fund triggers a global credit event", "Global finance", "gcr_lenders", [
      node("gcr_spreads", "", "Credit markets", "Global credit spreads widen", 0.85, "negative", "assumption", { impactMagnitude: 0.08, lag: "Days to weeks", tags: { assetClasses: ["BOND"], keywords: ["credit", "corporate bond", "high yield"] } }),
      node("gcr_downgrades", "gcr_spreads", "Corporate credit ratings", "Corporate downgrades and refinancing failures rise", 0.70, "negative", "assumption", { impactMagnitude: 0.10, tags: { assetClasses: ["BOND"], keywords: ["corporate bond", "credit", "debt"] } }),
      node("gcr_lenders", "gcr_downgrades", "Banks and non-bank lenders", "Loan losses and funding pressure hit banks, card companies, and non-bank lenders", 0.75, "negative", "assumption", { impactMagnitude: 0.12, tags: { sectors: ["Financial Services", "Banks", "Credit Services"], keywords: ["bank", "credit", "card", "lender", "finance"] } }),
      node("gcr_hy", "gcr_downgrades", "Corporate bonds", "High-yield and lower-rated corporate bonds fall sharply", 0.82, "negative", "assumption", { impactMagnitude: 0.14, tags: { assetClasses: ["BOND"], keywords: ["high yield", "corporate bond", "credit"] } }),
      node("gcr_gold", "gcr_spreads", "Gold and government bonds", "Liquidity and safe-haven flows support gold and top-rated sovereign bonds", 0.62, "positive", "assumption", { impactMagnitude: 0.06, tags: { assetClasses: ["BOND"], keywords: ["gold", "treasury", "government bond"] } }),
    ]),
    independentScenario("trade_logistics", "Trade, shipping, and logistics disruption", "Tariffs, Red Sea risk, or Suez disruption restricts trade", "Global trade", "log_israel_margins", [
      node("log_freight", "", "Shipping and logistics", "Freight, delay, and insurance costs rise", 0.80, "negative", "assumption", { impactMagnitude: 0.10, lag: "Days to weeks", tags: { sectors: ["Transportation", "Industrials"], keywords: ["shipping", "logistics", "freight", "airline"] } }),
      node("log_imports", "log_freight", "Importers and retail", "Imported input and inventory costs rise", 0.75, "negative", "assumption", { impactMagnitude: 0.07, tags: { sectors: ["Consumer Cyclical", "Consumer Defensive", "Industrials"], keywords: ["retail", "import", "consumer", "industrial"] } }),
      node("log_israel_margins", "log_imports", "Israeli economy", "Israeli CPI rises and importer margins contract", 0.70, "negative", "assumption", { impactMagnitude: 0.06, tags: { countries: ["Israel"], sectors: ["Consumer Cyclical", "Industrials"], keywords: ["retail", "import", "shipping", "industrial"] } }),
      node("log_defense", "log_freight", "Defense and cyber", "Maritime defense and logistics-cyber demand rises", 0.65, "positive", "assumption", { impactMagnitude: 0.07, tags: { sectors: ["Defense", "Technology"], keywords: ["defense", "cyber", "security"] } }),
    ]),
    independentScenario("climate_shock", "Climate and extreme-weather shock", "Heat, drought, flood, or wildfire disrupts production", "Climate", "clm_israel_costs", [
      node("clm_supply", "", "Food, power, and insurance", "Food supply, electricity systems, and insured assets come under pressure", 0.75, "negative", "assumption", { impactMagnitude: 0.09, horizon: "3–24 months", tags: { sectors: ["Agriculture", "Utilities", "Insurance"], keywords: ["food", "agriculture", "utility", "insurance"] } }),
      node("clm_prices", "clm_supply", "Inflation", "Food and electricity inflation rises", 0.70, "negative", "assumption", { impactMagnitude: 0.06, tags: { sectors: ["Consumer Defensive", "Utilities"], keywords: ["food", "electricity", "utility"] } }),
      node("clm_israel_costs", "clm_prices", "Israeli economy", "Israeli households, agriculture, and insurers face higher costs", 0.65, "negative", "assumption", { impactMagnitude: 0.07, tags: { countries: ["Israel"], sectors: ["Agriculture", "Insurance", "Utilities"], keywords: ["food", "agriculture", "insurance", "utility"] } }),
      node("clm_water", "clm_supply", "Water and adaptation", "Water, grid, cooling, and climate-adaptation investment rises", 0.72, "positive", "assumption", { impactMagnitude: 0.09, horizon: "6–36 months", tags: { sectors: ["Industrials", "Utilities", "Technology"], keywords: ["water", "grid", "cooling", "climate"] } }),
    ]),
    independentScenario("regulation_shock", "Technology, finance, and tax regulation shock", "Major AI, banking, pharmaceutical, or tax rules tighten", "Regulation", "reg_tech", [
      node("reg_compliance", "", "Regulation", "Compliance costs and business-model constraints rise", 0.70, "negative", "assumption", { impactMagnitude: 0.05, horizon: "6–24 months", tags: { keywords: ["regulated", "platform", "technology", "finance", "pharma"] } }),
      node("reg_tech", "reg_compliance", "Artificial intelligence and technology", "AI and platform margins and valuations come under pressure", 0.65, "negative", "assumption", { impactMagnitude: 0.09, tags: { sectors: ["Technology"], keywords: ["AI", "software", "platform", "technology"] } }),
      node("reg_finance", "reg_compliance", "Banks and lenders", "Capital, consumer-credit, and reporting rules pressure financial firms", 0.65, "negative", "assumption", { impactMagnitude: 0.07, tags: { sectors: ["Financial Services", "Banks", "Credit Services"], keywords: ["bank", "credit", "card", "lender", "finance"] } }),
      node("reg_pharma", "reg_compliance", "Healthcare and pharmaceuticals", "Drug-pricing and approval changes reprice healthcare earnings", 0.60, "mixed", "assumption", { impactMagnitude: 0.08, tags: { sectors: ["Healthcare"], keywords: ["pharma", "drug", "biotech", "health"] } }),
    ]),
    independentScenario("ai_power", "AI, electricity, nuclear, and uranium boom", "AI data-center investment accelerates", "Technology and energy", "aip_suppliers", [
      node("aip_electricity", "", "Electricity and data centers", "Data-center electricity demand rises rapidly", 0.85, "positive", "assumption", { impactMagnitude: 0.10, horizon: "1–5 years", tags: { sectors: ["Utilities", "Technology"], keywords: ["data center", "electricity", "power", "AI"] } }),
      node("aip_grid", "aip_electricity", "Grid, nuclear, and uranium", "Grid, gas, nuclear, and uranium investment rises", 0.70, "positive", "assumption", { impactMagnitude: 0.12, horizon: "1–5 years", tags: { sectors: ["Utilities", "Energy", "Industrials"], keywords: ["grid", "power", "nuclear", "uranium", "gas"] } }),
      node("aip_suppliers", "aip_grid", "Power infrastructure", "Power-equipment, utility, and uranium suppliers gain demand", 0.75, "positive", "assumption", { impactMagnitude: 0.14, horizon: "1–5 years", tags: { sectors: ["Utilities", "Industrials", "Energy"], keywords: ["grid", "power", "electrical", "nuclear", "uranium"] } }),
      node("aip_inflation", "aip_electricity", "Power prices", "Grid bottlenecks lift local electricity prices", 0.65, "negative", "assumption", { impactMagnitude: 0.06, tags: { sectors: ["Utilities", "Industrials"], keywords: ["electricity", "power", "data center"] } }),
      node("aip_quantum", "aip_electricity", "Quantum computing", "AI infrastructure spillovers support quantum research and funding", 0.55, "positive", "assumption", { impactMagnitude: 0.10, horizon: "2–7 years", tags: { sectors: ["Technology"], keywords: ["quantum", "computing", "research"] } }),
    ]),
    independentScenario("israel_war", "Israel regional-war escalation", "A regional war materially escalates", "Israel", "isw_rating", [
      node("isw_disruption", "", "War and operations", "Reserve duty, labor, aviation, and shipping disruption rises", 0.80, "negative", "assumption", { impactMagnitude: 0.10, lag: "Days to weeks", tags: { countries: ["Israel"], sectors: ["Industrials", "Travel"], keywords: ["airline", "shipping", "tourism", "industrial"] } }),
      node("isw_macro", "isw_disruption", "Israeli economy", "Israeli GDP weakens while inflation pressure rises", 0.75, "negative", "assumption", { impactMagnitude: 0.08, tags: { countries: ["Israel"], keywords: ["Israel", "Israeli"] } }),
      node("isw_risk", "isw_macro", "Sovereign risk", "Shekel and sovereign risk premium deteriorate", 0.70, "negative", "assumption", { impactMagnitude: 0.09, tags: { countries: ["Israel"], currencies: ["ILS"], assetClasses: ["BOND"], keywords: ["Israel bond", "shekel"] } }),
      node("isw_rating", "isw_risk", "Sovereign credit rating", "Government rating pressure and bond yields rise", 0.75, "negative", "assumption", { impactMagnitude: 0.10, tags: { countries: ["Israel"], currencies: ["ILS"], assetClasses: ["BOND"], keywords: ["government bond", "sovereign", "Israel bond"] } }),
      node("isw_defense", "isw_disruption", "Defense and cyber", "Demand for defense, cyber, and resilient infrastructure rises", 0.85, "positive", "assumption", { impactMagnitude: 0.12, tags: { sectors: ["Defense", "Technology"], keywords: ["defense", "cyber", "security"] } }),
      node("isw_gold_oil", "isw_disruption", "Oil and gold", "Oil risk premium and gold safe-haven demand rise", 0.72, "positive", "assumption", { impactMagnitude: 0.10, tags: { sectors: ["Energy"], keywords: ["oil", "gold", "energy", "precious metal"] } }),
    ]),
    independentScenario("israel_fiscal", "Israel fiscal and sovereign-debt shock", "Israel's deficit and debt path deteriorates", "Israel", "isf_finance", [
      node("isf_deficit", "", "Fiscal policy", "Government borrowing needs rise", 0.80, "negative", "assumption", { impactMagnitude: 0.05, tags: { countries: ["Israel"], assetClasses: ["BOND"], keywords: ["government bond", "sovereign", "Israel bond"] } }),
      node("isf_rating", "isf_deficit", "Sovereign credit rating", "Sovereign downgrade or negative-outlook risk rises", 0.70, "negative", "assumption", { impactMagnitude: 0.08, tags: { countries: ["Israel"], assetClasses: ["BOND"], keywords: ["government bond", "sovereign", "Israel bond"] } }),
      node("isf_yields", "isf_rating", "Government and corporate bonds", "Government yields and corporate spreads rise", 0.75, "negative", "assumption", { impactMagnitude: 0.09, tags: { countries: ["Israel"], currencies: ["ILS"], assetClasses: ["BOND"], keywords: ["bond", "fixed income"] } }),
      node("isf_finance", "isf_yields", "Banks and non-bank lenders", "Funding costs, credit losses, and housing pressure rise", 0.70, "negative", "assumption", { impactMagnitude: 0.09, tags: { countries: ["Israel"], sectors: ["Financial Services", "Banks", "Credit Services", "Real Estate"], keywords: ["bank", "credit", "card", "lender", "real estate"] } }),
      node("isf_money_fund", "isf_yields", "Shekel money-market funds", "Shekel money-market fund yields rise", 0.85, "positive", "assumption", { impactMagnitude: 0.04, tags: { currencies: ["ILS"], assetClasses: ["MUTUALFUND"], keywords: ["money market", "shekel fund", "cash fund"] } }),
    ]),
  ]);

  const WORKFLOWS = Object.freeze([...SCENARIOS, ...TRIGGER_MODULES]);

  function finiteProbability(value) {
    if (value === "" || value === null || value === undefined) return null;
    const number = Number(value);
    return Number.isFinite(number) && number >= 0 && number <= 1 ? number : null;
  }

  function defaultSettings() {
    return {
      selected: "increase",
      priors: { increase: null, decrease: null, unchanged: null },
      localTrigger: null,
      triggerPriors: Object.fromEntries(TRIGGER_MODULES.map((item) => [item.id, null])),
      overrides: {},
      impactOverrides: {},
    };
  }

  function normalizeSettings(value) {
    const defaults = defaultSettings();
    const input = value && typeof value === "object" ? value : {};
    const selected = WORKFLOWS.some((item) => item.id === input.selected) ? input.selected : defaults.selected;
    const priors = Object.fromEntries(SCENARIOS.map((item) => [item.id, finiteProbability(input.priors?.[item.id])]));
    const triggerPriors = Object.fromEntries(TRIGGER_MODULES.map((item) => [item.id, finiteProbability(input.triggerPriors?.[item.id])]));
    const validIds = new Set(WORKFLOWS.flatMap((item) => item.nodes.map((entry) => entry.id)));
    const overrides = {};
    Object.entries(input.overrides || {}).forEach(([id, probability]) => {
      const normalized = finiteProbability(probability);
      if (validIds.has(id) && normalized !== null) overrides[id] = normalized;
    });
    const impactOverrides = {};
    Object.entries(input.impactOverrides || {}).forEach(([id, magnitude]) => {
      const normalized = finiteProbability(magnitude);
      if (validIds.has(id) && normalized !== null) impactOverrides[id] = normalized;
    });
    return { selected, priors, localTrigger: finiteProbability(input.localTrigger), triggerPriors, overrides, impactOverrides };
  }

  function scenarioById(id) {
    return WORKFLOWS.find((item) => item.id === id) || SCENARIOS[0];
  }

  function probabilityFor(entry, settings) {
    return Object.prototype.hasOwnProperty.call(settings.overrides, entry.id)
      ? settings.overrides[entry.id]
      : entry.probability;
  }

  function triggerProbability(definition, settings) {
    if (definition.kind === "independent") return settings.triggerPriors[definition.id];
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
        impactMagnitude: Object.prototype.hasOwnProperty.call(settings.impactOverrides, entry.id)
          ? settings.impactOverrides[entry.id]
          : entry.impactMagnitude,
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

  return { SCENARIOS, TRIGGER_MODULES, WORKFLOWS, defaultSettings, normalizeSettings, calculateScenario, pathTo, priorStatus };
});
