(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PriceInputUnits = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  function describe(context = {}) {
    const location = String(context.location || "").trim().toLowerCase();
    const currency = String(context.currency || "USD").trim().toUpperCase();
    const action = String(context.action || "").trim().toUpperCase();
    const usa = ["usa", "us", "u.s.", "u.s.a.", "united states", "united states of america"].includes(location);
    const israel = ["israel", "il", "state of israel"].includes(location);
    const scaled = !["DIVIDEND", "INTEREST", "FEE"].includes(action)
      && (israel || (usa && String(context.assetClass || context.asset_class || "").trim().toUpperCase() === "BOND"));
    if (scaled && currency === "USD") return { unitKey: "US cents", hintKey: "Enter U.S. cents: 100 cents = $1 per recorded unit; 1 cent = $0.01. For example, 8,000 units at 100 cents total $8,000 before fees.", currency };
    if (scaled && currency === "ILS") return { unitKey: "Agorot", hintKey: "Enter agorot: 100 agorot = ₪1 per recorded unit. The app divides the entered price by 100 once.", currency };
    if (scaled) return { unitKey: "Hundredths of {currency}", hintKey: "Enter hundredths of {currency}: 100 = 1 {currency} per recorded unit. The app divides the entered price by 100 once.", currency };
    if (currency === "USD") return { unitKey: "US dollars", hintKey: "Enter U.S. dollars per recorded unit: 1 = $1. Dividends, interest and fees use currency units directly, including for bonds.", currency };
    return { unitKey: "{currency} per unit", hintKey: "Enter {currency} per recorded unit. Dividends, interest and fees use currency units directly, including for bonds.", currency };
  }
  function bind(nodes, context, translate = (value) => value) {
    const info = describe(context);
    const localize = (key) => translate(key).replaceAll("{currency}", info.currency);
    const unit = localize(info.unitKey), hint = localize(info.hintKey);
    if (nodes.unit) nodes.unit.textContent = unit;
    if (nodes.hint) nodes.hint.textContent = hint;
    if (nodes.input) {
      nodes.input.title = hint;
      if (nodes.hint?.id) nodes.input.setAttribute("aria-describedby", nodes.hint.id);
    }
    if (nodes.info) {
      nodes.info.title = hint;
      nodes.info.dataset.tooltip = hint;
      nodes.info.setAttribute("aria-label", hint);
    }
    return info;
  }
  return { describe, bind };
});
