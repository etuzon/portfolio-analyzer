let xrayView = { version: 0, editorVersion: 0, fileVersion: 0, operation: 0, data: null, error: "", loading: false, busy: false, editorLoading: false, fileLoading: false, target: "", drafts: {}, message: "" };
const XRAY_FIELDS = ["xrayReportDate", "xrayReportSource", "xrayReportUrl", "xrayReportCsv"];
const XRAY_ERRORS = {
  xray_fund_not_held: "Choose a currently held fund.",
  xray_unknown_account: "This account is no longer available. Choose another account.",
  xray_invalid_date: "Enter a valid holdings date that is not in the future.",
  xray_source_required: "Enter the report source name (up to 240 characters).",
  xray_invalid_source_url: "Use an http or https source URL without login credentials.",
  xray_invalid_csv: "Enter a valid CSV report of at most 1 MB.",
  xray_csv_columns: "CSV requires symbol, market and weight_percent columns.",
  xray_invalid_rows: "Enter 1–5000 valid constituents. Optional asset_class must be EQUITY, ETF, MUTUALFUND or UNKNOWN.",
  xray_invalid_identity: "Each constituent needs a symbol and a market scope, such as US or TASE.",
  xray_invalid_weight: "Each weight must be a finite percentage greater than 0 and at most 100.",
  xray_duplicate_constituent: "Each symbol and market pair must appear only once in the report.",
  xray_self_holding: "A fund cannot list itself as an underlying holding.",
  xray_weight_total: "Reported weights cannot total more than 100%. Do not rescale partial reports.",
  xray_issuer_unsupported: "Official downloads currently support US-listed SPY and IVV only. Add a sourced report for other funds.",
  xray_issuer_failed: "Could not fetch a valid issuer report. Your saved report is retained. Retry or enter a report locally.",
  xray_report_changed: "A newer report was saved during the download. Reload X-Ray before retrying.",
};

function resetXray() {
  xrayView = { version: xrayView.version + 1, editorVersion: xrayView.editorVersion + 1, fileVersion: xrayView.fileVersion + 1, operation: xrayView.operation + 1, data: null, error: "", loading: false, busy: false, editorLoading: false, fileLoading: false, target: "", drafts: {}, message: "" };
  if ($("xrayAccount")) $("xrayAccount").innerHTML = `<option value="">${esc(t("All investment accounts"))}</option>`;
  if ($("xrayFund")) $("xrayFund").innerHTML = "";
  XRAY_FIELDS.forEach(id => { if ($(id)) $(id).value = ""; });
  renderXray();
}

function xrayFundKey(fund) { return JSON.stringify([fund.symbol, fund.stock_market]); }
function xrayListing(row) { return [row.symbol, row.stock_market || row.market].filter(Boolean).join(" · "); }
function xrayTimestamp(value) {
  if (!value) return t("Not available");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return t("Unknown");
  return `${date.toLocaleDateString("en-GB")} ${date.toLocaleTimeString("en-GB", {hour:"2-digit", minute:"2-digit", hour12:false})}`;
}
function xraySource(row) {
  const label = esc(row.source_name || t("Not available"));
  return /^https?:\/\//i.test(row.source_url || "") ? `<a href="${esc(row.source_url)}" target="_blank" rel="noopener noreferrer">${label}</a>` : label;
}

function xrayPermissions() {
  const editable = canWrite();
  $("xrayReportEditor").hidden = !editable || !xrayView.data?.fund_count || xrayView.data.account_id !== $("xrayAccount").value;
  $("xrayViewerNote").hidden = editable;
  $("xrayAccount").disabled = xrayView.busy;
  $("xrayReload").disabled = xrayView.loading || xrayView.busy;
  ["xrayFund", "fetchXrayIssuer", "saveXrayReport", "xrayReportFile", "chooseXrayReportFile", ...XRAY_FIELDS].forEach(id => {
    $(id).disabled = !editable || xrayView.busy || xrayView.editorLoading || xrayView.fileLoading;
  });
}

function renderXray() {
  if (!$("xrayResults")) return;
  const view = xrayView, data = view.data;
  const chosen = $("xrayAccount").value;
  if (data) {
    $("xrayAccount").innerHTML = `<option value="">${esc(t("All investment accounts"))}</option>` + data.accounts.filter(row => row.type === "Investment").map(row => `<option value="${esc(row.id)}">${esc(accountLabel(row))}</option>`).join("");
    $("xrayAccount").value = chosen;
  }
  $("xrayStatus").textContent = t(view.loading ? "Reading saved fund reports…" : view.error || "");
  $("xrayResults").setAttribute("aria-busy", String(view.loading));
  $("xrayReportStatus").textContent = t(view.message);
  xrayPermissions();
  if (!data || data.account_id !== chosen) {
    $("xrayResults").innerHTML = "";
    return;
  }
  const accounts = new Map(data.accounts.filter(row => row.type === "Investment").map(row => [row.id, accountLabel(row)]));
  const positionText = positions => positions.map(row => `${esc(accounts.get(row.account_id) || t("Investment account"))} · ${esc(t(row.quantity < 0 ? "Short" : "Long"))}`).join("<br>");
  const funds = new Map(data.funds.map(row => [xrayFundKey(row), row]));
  const securityHtml = row => `<bdi>${esc(xrayListing(row))}</bdi>${row.name ? `<small dir="auto">${esc(row.name)}</small>` : ""}`;
  const directHtml = row => row.direct.length ? positionText(row.direct) : esc(t("Through funds only"));
  const pathsHtml = row => row.funds.map(path => `<div><bdi>${esc(xrayListing(path))}</bdi> · <b>${fmt(path.weight_percent, 4)}%</b> ${esc(t("of fund"))}${path.nested ? ` · ${esc(t("Nested fund; not expanded"))}` : ""}<small>${positionText(funds.get(xrayFundKey(path))?.positions || [])}</small></div>`).join("");
  const rows = data.overlaps.map(row => `<tr><th scope="row">${securityHtml(row)}</th><td>${directHtml(row)}</td><td>${pathsHtml(row)}</td></tr>`).join("");
  const cards = `<ul class="xray-mobile-overlaps">${data.overlaps.map(row => `<li><h4>${securityHtml(row)}</h4><dl><dt>${esc(t("Held directly"))}</dt><dd>${directHtml(row)}</dd><dt>${esc(t("Held through funds"))}</dt><dd>${pathsHtml(row)}</dd></dl></li>`).join("")}</ul>`;
  const statusLabels = {missing:"Holdings unavailable; overlap unknown.", undated:"Holdings date unknown", stale:"Report older than 45 days", available:"Dated report available"};
  $("xrayResults").innerHTML = `${data.has_shorts ? `<p class="info-strip">${esc(t("Includes short positions. Shared holdings show membership, not net exposure or hedge effectiveness."))}</p>` : ""}
    <h3>${esc(t("Shared securities"))} · ${data.overlaps.length}</h3>
    ${rows ? `<div class="table-wrap xray-scroll" tabindex="0" role="region" aria-label="${esc(t("Shared securities"))}"><table class="xray-table"><thead><tr><th scope="col">${esc(t("Security"))}</th><th scope="col">${esc(t("Held directly"))}</th><th scope="col">${esc(t("Held through funds"))}</th></tr></thead><tbody>${rows}</tbody></table></div>${cards}` : `<p>${esc(t(data.fund_count ? "No overlaps found in the available reports. Review fund coverage before drawing conclusions." : "No ETF or mutual fund holdings in this account scope."))}</p>`}
    ${data.fund_pairs.length ? `<h3>${esc(t("Fund overlap"))}</h3><ul class="xray-pairs">${data.fund_pairs.map(pair => `<li><bdi>${esc(xrayListing(pair.left))} / ${esc(xrayListing(pair.right))}</bdi> · <b>${fmt(pair.observed_overlap_percent, 4)}%</b> ${esc(t("observed overlap"))} · ${pair.shared_count} ${esc(t("shared securities"))}</li>`).join("")}</ul>` : ""}
    <h3>${esc(t("Fund coverage"))}</h3><ul class="xray-coverage">${data.funds.map(fund => `<li><bdi><strong>${esc(xrayListing(fund))}</strong></bdi> · ${esc(t(statusLabels[fund.status]))}
      <div>${fund.constituent_count} ${esc(t("reported constituents"))} · ${fmt(fund.covered_weight_percent, 4)}% ${esc(t("reported allocation"))}</div>
      <div>${esc(t("Holdings as of"))}: ${fund.as_of ? esc(formatDate(fund.as_of)) : esc(t("Unknown"))} · ${esc(t("Retrieved on"))}: ${esc(xrayTimestamp(fund.retrieved_at))}</div>
      <div>${esc(t(fund.source_kind === "issuer" ? "Official issuer report" : fund.source_kind ? "Locally entered report" : "No saved report"))} · ${xraySource(fund)}</div>
      ${fund.nested_constituents ? `<div>${fund.nested_constituents} ${esc(t("nested funds not expanded"))}</div>` : ""}</li>`).join("")}</ul>
    ${data.excluded.length ? `<p>${data.excluded.length} ${esc(t("unsupported holdings excluded"))}: ${data.excluded.map(row => `<bdi>${esc(xrayListing(row))}</bdi>`).join(", ")}</p>` : ""}`;
  const selected = $("xrayFund").value;
  $("xrayFund").innerHTML = data.funds.map(fund => `<option value="${esc(xrayFundKey(fund))}">${esc(xrayListing(fund))}</option>`).join("");
  $("xrayFund").value = funds.has(selected) ? selected : data.funds.length ? xrayFundKey(data.funds[0]) : "";
  if (canWrite() && $("xrayFund").value !== view.target) selectXrayFund();
  xrayPreview();
}

async function loadXray() {
  const version = ++xrayView.version;
  xrayView.loading = true;
  xrayView.error = "";
  const params = new URLSearchParams({account_id:$("xrayAccount").value});
  renderXray();
  let loaded = false;
  try {
    const data = await api(`/api/portfolio/xray?${params}`);
    if (version !== xrayView.version) return;
    xrayView.data = data;
    loaded = true;
  } catch (error) {
    if (version !== xrayView.version) return;
    if(params.get("account_id") && (error?.code || error?.message)==="xray_unknown_account") { $("xrayAccount").value=""; xrayView.data=null; xrayView.loading=false; return loadXray(); }
    xrayView.error = XRAY_ERRORS[error.message] || "Could not load X-Ray. Use Reload to retry.";
  }
  if (version !== xrayView.version) return;
  xrayView.loading = false;
  renderXray();
  return loaded;
}

function rememberXrayDraft() {
  if (xrayView.target && !xrayView.editorLoading) xrayView.drafts[xrayView.target] = XRAY_FIELDS.map(id => $(id).value);
}

async function selectXrayFund(force = false) {
  rememberXrayDraft();
  const target = $("xrayFund").value;
  const previous = target === xrayView.target ? XRAY_FIELDS.map(id => $(id).value) : null;
  const version = ++xrayView.editorVersion;
  xrayView.fileVersion++;
  xrayView.fileLoading = false;
  xrayView.editorLoading = false;
  xrayView.target = target;
  xrayView.message = "";
  if (!target) return;
  if (!force && xrayView.drafts[target]) {
    XRAY_FIELDS.forEach((id, i) => { $(id).value = xrayView.drafts[target][i]; });
    xrayPreview();
    xrayPermissions();
    return;
  }
  if (!previous) XRAY_FIELDS.forEach(id => { $(id).value = ""; });
  xrayView.editorLoading = true;
  let loaded = false;
  xrayPermissions();
  try {
    const [symbol, stock_market] = JSON.parse(target);
    const result = await api(`/api/local/fund-holdings?${new URLSearchParams({symbol, stock_market})}`);
    if (version !== xrayView.editorVersion) return;
    const report = result.snapshot;
    loaded = true;
    XRAY_FIELDS.forEach(id => { $(id).value = ""; });
    if (report) {
      $("xrayReportDate").value = report.as_of ? formatDate(report.as_of) : "";
      $("xrayReportSource").value = report.source_name;
      $("xrayReportUrl").value = report.source_url || "";
      const quote = value => `"${String(value || "").replaceAll('"', '""')}"`;
      $("xrayReportCsv").value = "symbol,market,weight_percent,name,asset_class\n" + report.holdings.map(row => [quote(row.symbol), quote(row.market), row.weight_percent, quote(row.name), quote(row.asset_class || "UNKNOWN")].join(",")).join("\n");
    }
  } catch {
    if (version === xrayView.editorVersion) xrayView.message = "Could not load this report. Your saved report is retained. Use Reload to retry.";
  }
  if (version !== xrayView.editorVersion) return;
  xrayView.editorLoading = false;
  xrayPermissions();
  $("xrayReportStatus").textContent = t(xrayView.message);
  xrayPreview();
  return loaded;
}

function xrayPreview() {
  if (!$("xrayPreview")) return;
  const text = $("xrayReportCsv").value;
  if (!text.trim()) { $("xrayPreview").textContent = ""; return; }
  // Only preview counts and weights; the server validates every field atomically.
  const rows = [], fields = []; let field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"') { if (quoted && text[i + 1] === '"') { field += '"'; i++; } else quoted = !quoted; }
    else if (!quoted && (char === "," || char === "\n")) {
      fields.push(field.replace(/\r$/, "")); field = "";
      if (char === "\n") { rows.push(fields.splice(0)); }
    } else field += char;
  }
  fields.push(field.replace(/\r$/, "")); if (fields.some(value => value.trim())) rows.push(fields);
  const index = rows[0]?.indexOf("weight_percent");
  const values = rows.slice(1).filter(row => row.some(value => value.trim())).map(row => Number(row[index]));
  $("xrayPreview").textContent = !quoted && index >= 0 && values.length && values.every(value => Number.isFinite(value) && value > 0 && value <= 100)
    ? `${values.length} ${t("reported constituents")} · ${fmt(values.reduce((sum, value) => sum + value, 0), 4)}% ${t("reported allocation")}`
    : t("Preview unavailable. Check the CSV columns, quotes and weights.");
}

async function writeXrayReport(issuer = false) {
  if (!canWrite() || xrayView.busy || xrayView.editorLoading || xrayView.fileLoading || !xrayView.target) return;
  rememberXrayDraft();
  const operation = ++xrayView.operation, target = xrayView.target;
  const [symbol, stock_market] = JSON.parse(target);
  xrayView.busy = true;
  xrayView.message = issuer ? "Fetching official issuer holdings…" : "Saving fund report…";
  renderXray();
  try {
    await api(issuer ? "/api/portfolio/xray/refresh" : "/api/local/fund-holdings", {
      method: issuer ? "POST" : "PUT", body:JSON.stringify({symbol, stock_market,
        as_of:parseDateInput($("xrayReportDate").value), source_name:$("xrayReportSource").value,
        source_url:$("xrayReportUrl").value, csv_text:$("xrayReportCsv").value}),
    });
    if (operation !== xrayView.operation) return;
    const reloaded = await loadXray();
    if (operation !== xrayView.operation) return;
    if (!reloaded) {
      xrayView.message = "Report saved, but X-Ray could not reload. Your draft is retained. Use Reload to retry.";
    } else {
      const editorLoaded = await selectXrayFund(true);
      if (operation !== xrayView.operation) return;
      xrayView.message = editorLoaded ? "Fund report saved. X-Ray recalculated from saved evidence." : "Report saved and X-Ray updated, but the report editor could not reload. Your draft is retained.";
    }
  } catch (error) {
    if (operation !== xrayView.operation) return;
    xrayView.message = XRAY_ERRORS[error.message] || "Could not save the report. Your draft is retained. Try again.";
  }
  if (operation !== xrayView.operation) return;
  xrayView.busy = false;
  renderXray();
}

async function readXrayFile(file) {
  if (!canWrite() || xrayView.busy) return;
  const target = xrayView.target, version = xrayView.editorVersion, fileVersion = ++xrayView.fileVersion;
  if (file.size > 1_000_000) { xrayView.fileLoading = false; xrayView.message = "Enter a valid CSV report of at most 1 MB."; renderXray(); return; }
  xrayView.fileLoading = true;
  xrayView.message = "Reading selected CSV file…";
  renderXray();
  const current = () => version === xrayView.editorVersion && target === xrayView.target && fileVersion === xrayView.fileVersion;
  try {
    const text = await file.text();
    if (!current()) return;
    $("xrayReportCsv").value = text;
    xrayView.message = "CSV loaded. Review allocation before saving.";
  } catch {
    if (current()) xrayView.message = "Could not read the CSV file. Paste the report instead.";
  }
  if (!current()) return;
  xrayView.fileLoading = false;
  renderXray();
}

document.addEventListener("change", event => {
  if (event.target.id === "xrayAccount") loadXray();
  if (event.target.id === "xrayFund") selectXrayFund();
  if (event.target.id === "xrayReportFile" && event.target.files?.[0]) {
    readXrayFile(event.target.files[0]);
  }
});
document.addEventListener("input", event => { if (event.target.id === "xrayReportCsv") xrayPreview(); });
document.addEventListener("click", event => {
  if (event.target.closest("#chooseXrayReportFile")) $("xrayReportFile").click();
  if (event.target.closest("#xrayReload")) { if (!xrayView.loading && !xrayView.busy) { loadXray().then(() => { if (xrayView.editorLoading === false && !$("xrayReportCsv").value) selectXrayFund(true); }); } }
  if (event.target.closest("#fetchXrayIssuer")) writeXrayReport(true);
});
document.addEventListener("submit", event => { if (event.target.id === "xrayReportForm") { event.preventDefault(); writeXrayReport(); } });
