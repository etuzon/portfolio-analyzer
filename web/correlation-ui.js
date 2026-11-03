/* Saved-evidence analysis. Loading and retry stay inside the matrix dialog. */
let correlationView = { version: 0, status: "idle", data: null, accounts: [], selected: null };

function resetCorrelation() {
  correlationView = { version: correlationView.version + 1, status: "idle", data: null, accounts: [], selected: null };
  if ($("correlationAccount")) $("correlationAccount").innerHTML = `<option value="">${esc(t("All investment accounts"))}</option>`;
  renderCorrelation();
}

function correlationLabel(asset) {
  return [asset.symbol, asset.stock_market, asset.currency ? currencyDisplayLabel(asset.currency) : ""].filter(Boolean).join(" · ");
}

function correlationReason(cell) {
  if (cell.status === "currency_conflict") return t("Currency labels conflict for this listing. Choose one account and recalculate.");
  return t(cell.status === "constant_returns" ? "Returns do not vary." : "Fewer than 30 matching return observations.");
}

function renderCorrelation() {
  const target = $("correlationResults");
  if (!target) return;
  const view = correlationView;
  const account = $("correlationAccount");
  const chosen = account.value;
  account.innerHTML = `<option value="">${esc(t("All investment accounts"))}</option>` + view.accounts.filter(row => row.type === "Investment").map(row => `<option value="${esc(row.id)}">${esc(accountLabel(row))}</option>`).join("");
  account.value = chosen;
  target.setAttribute("aria-busy", String(view.status === "loading"));
  $("correlationRecalculate").disabled = view.status === "loading";
  const status = $("correlationStatus");
  status.textContent = t(view.status === "loading" ? "Calculating saved-price correlations…" : view.status === "error" ? "Could not calculate correlations. Use Recalculate to retry." : "");
  if (!view.data) {
    target.innerHTML = "";
    $("correlationPairDetails").textContent = "";
    return;
  }
  const data = view.data;
  if (data.status === "too_many_assets") {
    target.innerHTML = `<p>${esc(t("More than 60 securities. Choose one account to narrow the matrix."))}</p>`;
    return;
  }
  if (data.assets.length < 2) {
    target.innerHTML = `<p>${esc(t("At least two held securities are needed. Choose another account or add holdings in Positions."))}</p>`;
    return;
  }
  const coverage = `${t("Current holdings")} · ${data.asset_count} ${t("unique securities")} · ${data.usable_pairs}/${data.pair_count} ${t("pairs available")}`;
  const label = asset => esc(correlationLabel(asset));
  const cellHtml = (cell, i, j) => {
    const known = cell.value !== null;
    const value = known ? `${cell.value > 0 ? "+" : ""}${fmt(cell.value, 2)}` : t("Unavailable");
    const description = `${correlationLabel(data.assets[i])} / ${correlationLabel(data.assets[j])}: ${value}; ${cell.observations} ${t("matching returns")}${known ? "" : `; ${correlationReason(cell)}`}`;
    const hue = cell.value >= 0 ? 210 : 35;
    const color = known ? `background:hsla(${hue},75%,42%,${0.08 + Math.abs(cell.value) * 0.34})` : "background:var(--ux-panel-soft)";
    return `<td><button type="button" class="correlation-cell" style="${color}" data-correlation-pair="${i},${j}" aria-label="${esc(description)}"><b dir="ltr">${esc(value)}</b><small>${cell.observations} ${esc(t("matching returns"))}</small></button></td>`;
  };
  target.innerHTML = `<p>${esc(coverage)}</p>
    <p class="section-note">${esc(t("Requested period"))}: ${esc(formatDate(data.from))} – ${esc(formatDate(data.to))}. ${esc(t("Select a cell for its actual dates and data limits."))}</p>
    <div class="table-wrap correlation-scroll" tabindex="0" role="region" aria-label="${esc(t("Correlation Matrix"))}"><table class="correlation-table">
    <caption class="sr-only">${esc(t("Pearson correlation of matching percentage returns"))}</caption>
    <thead><tr><th scope="col">${esc(t("Security"))}</th>${data.assets.map(asset => `<th scope="col"><bdi>${label(asset)}</bdi></th>`).join("")}</tr></thead>
    <tbody>${data.matrix.map((row, i) => `<tr><th scope="row"><bdi>${label(data.assets[i])}</bdi></th>${row.map((cell, j) => cellHtml(cell, i, j)).join("")}</tr>`).join("")}</tbody></table></div>
    <details class="correlation-coverage"><summary>${esc(t("Price history coverage"))}</summary><ul>${data.assets.map(asset => `<li><bdi>${label(asset)}</bdi>: ${asset.price_count} ${esc(t("saved prices"))} · ${esc(t(asset.basis === "adjusted_close" ? "Provider adjusted close" : "Unadjusted close"))} · ${asset.from ? `${esc(formatDate(asset.from))} – ${esc(formatDate(asset.to))}` : esc(t("No saved history"))}</li>`).join("")}</ul></details>`;
  renderCorrelationPair();
}

function renderCorrelationPair() {
  const view = correlationView;
  const selected = view.selected;
  const node = $("correlationPairDetails");
  if (!node) return;
  if (!selected || !view.data?.matrix?.[selected[0]]?.[selected[1]]) { node.textContent = ""; return; }
  const [i, j] = selected;
  const cell = view.data.matrix[i][j];
  node.textContent = `${correlationLabel(view.data.assets[i])} / ${correlationLabel(view.data.assets[j])} · ${cell.observations} ${t("matching returns")} · ${cell.from ? `${formatDate(cell.from)} – ${formatDate(cell.to)}` : t("No matching dates")}${cell.value === null ? ` · ${correlationReason(cell)}` : ""}`;
}

async function loadCorrelation() {
  const version = ++correlationView.version;
  correlationView.status = "loading";
  correlationView.data = null;
  correlationView.selected = null;
  const params = new URLSearchParams({ period: $("correlationPeriod").value, account_id: $("correlationAccount").value });
  renderCorrelation();
  try {
    const data = await api(`/api/portfolio/correlation?${params}`);
    if (version !== correlationView.version) return;
    correlationView.data = data;
    correlationView.accounts = (data.accounts || []).filter(row => row.type === "Investment");
    correlationView.status = "ready";
  } catch (error) {
    if (version !== correlationView.version) return;
    if(params.get("account_id") && (error?.code || error?.message)==="unknown_account") { $("correlationAccount").value=""; correlationView.accounts=[]; correlationView.data=null; return loadCorrelation(); }
    correlationView.status = "error";
  }
  if (version === correlationView.version) renderCorrelation();
}

document.addEventListener("change", event => {
  if (["correlationAccount", "correlationPeriod"].includes(event.target.id)) loadCorrelation();
});
document.addEventListener("click", event => {
  if (event.target.closest("#correlationRecalculate")) loadCorrelation();
  const pair = event.target.closest("[data-correlation-pair]");
  if (pair) { correlationView.selected = pair.dataset.correlationPair.split(",").map(Number); renderCorrelationPair(); }
});
