/* Cash-flow-aware performance; drafts remain local until explicitly saved. */
let benchmarkView = {version:0,operation:0,loading:false,busy:false,data:null,error:"",message:"",filters:{account_id:"",benchmark_id:"sp500",date_from:"",date_to:""},drafts:{},indexDrafts:{},editorOpen:false,indexOpen:false};
const BENCHMARK_HE = {
 "Investment account":"חשבון השקעות", "All investment accounts":"כל חשבונות ההשקעה", "From":"מתאריך", "To":"עד תאריך", "Benchmark":"מדד ייחוס", "Compare":"השוואה", "Reload":"טעינה מחדש",
 "Loading saved performance data…":"טוען נתוני ביצועים שמורים…", "Could not load the comparison. Your inputs are retained. Use Compare to retry.":"לא ניתן לטעון את ההשוואה. הנתונים שהזנת נשמרו בטופס. יש ללחוץ על השוואה כדי לנסות שוב.",
 "Unavailable":"לא זמין", "Portfolio XIRR":"XIRR של התיק", "Annualized, money-weighted return":"תשואה שנתית משוקללת כסף", "Portfolio TWRR":"TWRR של התיק", "Cumulative, time-weighted return":"תשואה מצטברת משוקללת זמן", "Benchmark XIRR, same cash flows":"XIRR של המדד, באותן הפקדות ומשיכות", "Benchmark TWRR":"TWRR של המדד", "Opening value":"שווי התחלתי", "Closing value":"שווי סופי", "Net deposits / withdrawals":"הפקדות פחות משיכות", "Investment gain":"רווח השקעה", "Currency":"מטבע", "Price return; dividends excluded":"תשואת מחיר; ללא דיבידנדים", "Total return; dividends included":"תשואה כוללת; כולל דיבידנדים", "Source":"מקור", "No source supplied":"לא הוזן מקור", "Legacy index":"מדד היסטורי", "Portfolio":"תיק", "Growth of 100":"צמיחה של 100", "Show chart values":"הצגת ערכי הגרף", "Date":"תאריך", "Performance inputs":"נתוני ביצועים", "All values must describe the complete selected portfolio, including cash, in one currency. Saving performance inputs does not change holdings or account cash.":"כל שווי חייב לתאר את מלוא התיק שנבחר, כולל מזומן, במטבע אחד. שמירת נתוני הביצועים אינה משנה החזקות או מזומן בחשבון.",
 "Portfolio value CSV":"CSV של שווי התיק", "External cash-flow CSV":"CSV של הפקדות ומשיכות חיצוניות", "Dates: dd/mm/yyyy. Values: decimal numbers without thousands separators.":"תאריכים: dd/mm/yyyy. סכומים: מספרים עשרוניים ללא הפרדת אלפים.", "Positive amounts are deposits; negative amounts are withdrawals. Trades, dividends and interest retained inside the account are not external flows.":"סכום חיובי הוא הפקדה; סכום שלילי הוא משיכה. עסקאות, דיבידנדים וריבית שנשארו בחשבון אינם תנועות חיצוניות.", "Flows occur at end of day. Portfolio valuations must be after that day's flows. Exact TWRR needs a valuation on every cash-flow date; XIRR needs the opening and closing values and complete flows.":"הפקדות ומשיכות נרשמות בסוף היום. השווי חייב להיות לאחר תנועות אותו יום. TWRR מדויק מחייב שווי בכל יום של תנועה חיצונית; XIRR מחייב שווי פתיחה וסגירה ואת כל התנועות החיצוניות.",
 "I confirm all external deposits and withdrawals between the first and last saved valuation dates are recorded, including none if there were no flows.":"אני מאשר שכל ההפקדות והמשיכות החיצוניות בין תאריך השווי השמור הראשון והאחרון נרשמו, כולל היעדר תנועות אם לא היו כאלה.", "Save portfolio inputs":"שמירת נתוני התיק", "Use saved balance suggestions":"שימוש בהצעות שווי שמורות", "Balance suggestions copied. Review every valuation, add all external flows and confirm completeness before saving.":"הצעות השווי הועתקו. יש לבדוק כל שווי, להוסיף את כל התנועות החיצוניות ולאשר שהרישום מלא לפני השמירה.", "Index history":"היסטוריית המדד", "Index name":"שם המדד", "Return basis":"סוג התשואה", "Price":"מחיר", "Total return":"תשואה כוללת", "Index levels CSV":"CSV של ערכי המדד", "Index history must be in the portfolio currency. Import a historically converted series to compare different currencies; current exchange rates are not applied to past returns.":"היסטוריית המדד חייבת להיות במטבע התיק. להשוואת מטבעות שונים יש לייבא סדרה שהומרה לפי שערים היסטוריים; שערי חליפין נוכחיים אינם מוחלים על תשואות עבר.", "Save index history":"שמירת היסטוריית המדד", "Refresh index data":"עדכון נתוני המדד", "CSV file":"קובץ CSV", "Viewer access: saved inputs can be inspected; only an operator or administrator can save or refresh.":"גישה לצפייה: ניתן לבדוק נתונים שמורים; רק מפעיל או מנהל יכולים לשמור או לעדכן.", "Saved. Comparison updated.":"נשמר. ההשוואה עודכנה.", "Saved, but the comparison could not reload. Your draft is retained. Use Compare to retry.":"נשמר, אך לא ניתן לטעון את ההשוואה מחדש. הטיוטה נשמרה. יש ללחוץ על השוואה כדי לנסות שוב.", "Could not save. Your draft is retained. Check the source, currency and dated values, then retry.":"לא ניתן לשמור. הטיוטה נשמרה. יש לבדוק את המקור, המטבע והערכים המתוארכים ולנסות שוב.", "Saving…":"שומר…", "Refreshing index data…":"מעדכן נתוני מדד…", "Index data refreshed.":"נתוני המדד עודכנו.", "Could not refresh the index. Saved history is retained. Retry or import sourced index levels.":"לא ניתן לעדכן את המדד. ההיסטוריה השמורה נשמרה. ניתן לנסות שוב או לייבא ערכי מדד עם מקור.", "Enter two valid dates with From before To.":"יש להזין שני תאריכים תקינים, כאשר תאריך ההתחלה קודם לתאריך הסיום.", "CSV needs two columns: date and a finite numeric value. Valuation and index dates must be unique.":"CSV מחייב שתי עמודות: תאריך וערך מספרי סופי. כל תאריך שווי או מדד חייב להופיע פעם אחת בלבד.", "Enter a source and a three-letter currency code.":"יש להזין מקור וקוד מטבע בן שלוש אותיות.", "Could not read the CSV file. Paste the values instead.":"לא ניתן לקרוא את קובץ ה־CSV. אפשר להדביק את הערכים במקום זאת.", "The CSV file must be no larger than 1 MB.":"גודל קובץ ה־CSV חייב להיות עד 1 MB.", "CSV loaded into the form. Review before saving.":"ה־CSV נטען לטופס. יש לבדוק אותו לפני השמירה.", "Returns are unavailable until complete dated values and external flows are saved. Index history is required for the same dates.":"התשואות אינן זמינות עד לשמירת שווי מתוארך מלא ותנועות חיצוניות. נדרשת גם היסטוריית מדד לאותם תאריכים.", "No matching data":"אין נתונים תואמים", "Complete external flows have not been confirmed.":"טרם אושר שכל התנועות החיצוניות נרשמו.", "Opening or closing valuation is missing.":"חסר שווי לתחילת התקופה או לסופה.", "A valuation is missing on a cash-flow date.":"חסר שווי בתאריך של הפקדה או משיכה.", "The return is undefined for these cash flows or values.":"לא ניתן להגדיר תשואה עבור תנועות או ערכים אלה.", "More than one XIRR solution exists; no single rate is shown.":"קיים יותר מפתרון XIRR אחד; לא מוצגת תשואה יחידה.", "Cash-flow signs change more than once; XIRR may have multiple solutions.":"סימן התנועות החיצוניות משתנה יותר מפעם אחת; ל־XIRR עשויים להיות כמה פתרונות.", "No XIRR solution was found.":"לא נמצא פתרון XIRR.", "Portfolio and index currencies differ.":"מטבע התיק ומטבע המדד שונים.", "Index history is missing for a required date.":"חסרה היסטוריית מדד לתאריך נדרש.", "The selected period is outside this legacy index's history.":"התקופה שנבחרה חורגת מההיסטוריה של מדד זה.", "Benchmark withdrawals exceed the simulated available value.":"המשיכות מהמדד עולות על השווי הזמין בהדמיה.", "This result needs more valid observations.":"לתוצאה זו נדרשות תצפיות תקינות נוספות.", "Data saved locally":"נתונים שנשמרו מקומית", "Historical results do not predict future returns.":"תוצאות עבר אינן מנבאות תשואות עתידיות.", "After-fee portfolio return and index return may use different tax and cost assumptions.":"תשואת התיק לאחר עמלות ותשואת המדד עשויות להתבסס על הנחות שונות של מס ועלויות.", "Your unsaved inputs are retained separately for each account and index.":"הנתונים שטרם נשמרו נשמרים בטופס בנפרד לכל חשבון ומדד.", "Copying balance suggestions does not establish complete transaction or cash-flow history.":"העתקת הצעות שווי אינה מעידה על היסטוריית עסקאות או תנועות חיצוניות מלאה.", "Comparison unavailable":"ההשוואה אינה זמינה", "XIRR uses actual dates and a 365-day year; it is annualized even for periods shorter than a year.":"XIRR משתמש בתאריכים בפועל ובשנה של 365 יום; הוא מחושב במונחים שנתיים גם בתקופה קצרה משנה.", "No exact TWRR chart available":"לא זמין גרף TWRR מדויק"
};
function benchmarkText(text) { return state.language === "he" ? BENCHMARK_HE[text] || t(text) : text; }
function benchmarkEsc(text) { return esc(benchmarkText(text)); }
function benchmarkCanWrite() { return typeof canEditPortfolio === "function" ? canEditPortfolio() : canWrite(); }
function benchmarkNumber(value,digits=2) { return value === null || value === undefined || !Number.isFinite(Number(value)) ? benchmarkText("Unavailable") : fmt(Number(value),digits); }
function benchmarkPct(metric) { return metric?.value === null || metric?.value === undefined ? benchmarkText("Unavailable") : `${benchmarkNumber(metric.value)}%`; }
Object.assign(BENCHMARK_HE, {
 "Reload saved inputs":"טעינת נתונים שמורים מחדש", "Reload replaces unsaved edits in the selected account and index forms.":"טעינה מחדש מחליפה את השינויים שטרם נשמרו בטפסי החשבון והמדד שנבחרו.",
 "Saved inputs reloaded.":"הנתונים השמורים נטענו מחדש.", "The account is no longer available. Select another account.":"החשבון אינו זמין עוד. יש לבחור חשבון אחר.", "Choose an available benchmark.":"יש לבחור מדד זמין.", "Enter valid dates that are not in the future.":"יש להזין תאריכים תקינים שאינם בעתיד.", "No index provider is configured. Import sourced index levels instead.":"לא הוגדר ספק נתונים למדד. אפשר לייבא ערכי מדד עם מקור.", "Automatic refresh is unavailable for this index. Import sourced index levels.":"עדכון אוטומטי אינו זמין למדד זה. יש לייבא ערכי מדד עם מקור.", "Inputs changed during refresh. Reload saved inputs before retrying.":"הנתונים השתנו במהלך העדכון. יש לטעון מחדש את הנתונים השמורים לפני ניסיון נוסף.",
 "Enter valid nonnegative portfolio values and positive index levels.":"יש להזין שווי תיק תקין שאינו שלילי וערכי מדד חיוביים.", "Each valuation and index date must appear only once.":"כל תאריך שווי או מדד חייב להופיע פעם אחת בלבד.", "Cash-flow rows must have a nonzero amount.":"סכום בתנועת הפקדה או משיכה חייב להיות שונה מאפס.", "Enter an index name and choose price or total return.":"יש להזין שם מדד ולבחור תשואת מחיר או תשואה כוללת.", "Enter at least one valid dated observation, up to 10000 rows.":"יש להזין לפחות תצפית מתוארכת תקינה אחת, ועד 10000 שורות.", "Benchmark ending value":"שווי סופי במדד", "Index observations used":"תצפיות המדד ששימשו בחישוב", "Required date":"תאריך נדרש", "Observed date":"תאריך התצפית", "Index level":"ערך המדד", "On non-trading days, the latest earlier index observation may be used, up to 7 days old. Actual dates are shown below.":"בימים ללא מסחר ניתן להשתמש בתצפית המדד הקודמת האחרונה, עד גיל 7 ימים. התאריכים בפועל מוצגים להלן.", "Other index":"מדד אחר"
});
const BENCHMARK_ERRORS = {
 benchmark_unknown_account:"The account is no longer available. Select another account.", benchmark_unknown_index:"Choose an available benchmark.", unknown_benchmark:"Choose an available benchmark.",
 benchmark_invalid_dates:"Enter valid dates that are not in the future.", invalid_date:"Enter valid dates that are not in the future.", future_date:"Enter valid dates that are not in the future.", invalid_period:"Enter two valid dates with From before To.",
 benchmark_provider_not_configured:"No index provider is configured. Import sourced index levels instead.", benchmark_refresh_unsupported:"Automatic refresh is unavailable for this index. Import sourced index levels.",
 benchmark_inputs_changed:"Inputs changed during refresh. Reload saved inputs before retrying.", benchmark_refresh_failed:"Could not refresh the index. Saved history is retained. Retry or import sourced index levels.",
 invalid_number:"Enter valid nonnegative portfolio values and positive index levels.", currency_required:"Enter a source and a three-letter currency code.",source_required:"Enter a source and a three-letter currency code.",
 duplicate_date:"Each valuation and index date must appear only once.",zero_cash_flow:"Cash-flow rows must have a nonzero amount.",index_name_required:"Enter an index name and choose price or total return.",index_basis_required:"Enter an index name and choose price or total return.",
 invalid_rows:"Enter at least one valid dated observation, up to 10000 rows."
};
function benchmarkFailure(error,fallback) { return BENCHMARK_ERRORS[error?.code] || BENCHMARK_ERRORS[error?.message] || fallback; }
function benchmarkReason(status) {
 const reasons = {
  incomplete_cash_flows:"Complete external flows have not been confirmed.", flows_incomplete:"Complete external flows have not been confirmed.", incomplete_flows:"Complete external flows have not been confirmed.",
  missing_boundary_valuation:"Opening or closing valuation is missing.", missing_portfolio:"Returns are unavailable until complete dated values and external flows are saved. Index history is required for the same dates.", missing_boundaries:"Opening or closing valuation is missing.", missing_boundary_values:"Opening or closing valuation is missing.", missing_valuation:"Opening or closing valuation is missing.",
  missing_flow_valuation:"A valuation is missing on a cash-flow date.", missing_flow_valuations:"A valuation is missing on a cash-flow date.",
  nonpositive_base:"The return is undefined for these cash flows or values.", negative_pre_flow_value:"The return is undefined for these cash flows or values.", numeric_overflow:"The return is undefined for these cash flows or values.", invalid_cash_flow_signs:"The return is undefined for these cash flows or values.", invalid_cash_flows:"The return is undefined for these cash flows or values.", invalid_values:"The return is undefined for these cash flows or values.", nonpositive_value:"The return is undefined for these cash flows or values.",
  ambiguous_cash_flows:"Cash-flow signs change more than once; XIRR may have multiple solutions.", no_convergence:"No XIRR solution was found.", multiple_roots:"More than one XIRR solution exists; no single rate is shown.", no_root:"No XIRR solution was found.",
  missing_index:"Index history is missing for a required date.", missing_index_level:"Index history is missing for a required date.", currency_mismatch:"Portfolio and index currencies differ.", missing_index_history:"Index history is missing for a required date.", missing_index_levels:"Index history is missing for a required date.",
  index_outside_lifetime:"The selected period is outside this legacy index's history.", legacy_period:"The selected period is outside this legacy index's history.", legacy_index_period:"The selected period is outside this legacy index's history.",
  benchmark_overdrawn:"Benchmark withdrawals exceed the simulated available value.", insufficient_dates:"This result needs more valid observations.", insufficient_benchmark_value:"Benchmark withdrawals exceed the simulated available value.", insufficient_data:"This result needs more valid observations."
 };
 return !status || status === "ok" ? "" : benchmarkText(reasons[status] || "Comparison unavailable");
}
function benchmarkCsv(rows,key) { return `date,${key}\n` + (rows || []).map(row=>`${formatDate(row.date)},${row[key]}`).join("\n"); }
function benchmarkDraftKey() { return benchmarkView.filters.account_id || "__all__"; }
function benchmarkCapture() {
 const view=benchmarkView, portfolio=view.drafts[view.renderedAccount], index=view.indexDrafts[view.renderedIndex];
 const fields = [[portfolio,"currency","benchmarkCurrency"],[portfolio,"source","benchmarkSource"],[portfolio,"values","benchmarkValues"],[portfolio,"flows","benchmarkFlows"],[index,"currency","benchmarkIndexCurrency"],[index,"source","benchmarkIndexSource"],[index,"name","benchmarkIndexName"],[index,"basis","benchmarkIndexBasis"],[index,"levels","benchmarkLevels"]];
 fields.forEach(([draft,key,id])=>{if(draft && $(id)) draft[key]=$(id).value;});
 if(portfolio && $("benchmarkComplete")) portfolio.flows_complete=$("benchmarkComplete").checked;
 if($("benchmarkInputs")) view.editorOpen=$("benchmarkInputs").open;
 if($("benchmarkIndexInputs")) view.indexOpen=$("benchmarkIndexInputs").open;
}
function resetBenchmarkComparison() {
 benchmarkView={version:benchmarkView.version+1,operation:benchmarkView.operation+1,loading:false,busy:false,data:null,error:"",message:"",filters:{account_id:"",benchmark_id:"sp500",date_from:"",date_to:""},drafts:{},indexDrafts:{},editorOpen:false,indexOpen:false};
 renderBenchmarkComparison();
}
function benchmarkInitDrafts(data) {
 const v=benchmarkView, d=data.dataset || {}, idx=data.index_dataset || {};
 if(!v.drafts[benchmarkDraftKey()]) v.drafts[benchmarkDraftKey()]={currency:d.currency || data.suggested_currency || "",source:d.source || "",flows_complete:!!d.flows_complete,values:benchmarkCsv(d.valuations,"value"),flows:benchmarkCsv(d.cash_flows,"amount")};
 if(!v.indexDrafts[v.filters.benchmark_id]) v.indexDrafts[v.filters.benchmark_id]={name:idx.name || (v.filters.benchmark_id === "custom" ? "" : (data.catalog || []).find(row=>row.id===v.filters.benchmark_id)?.name) || "",currency:idx.currency || (data.catalog || []).find(row=>row.id===v.filters.benchmark_id)?.currency || "",source:idx.source || "",basis:idx.basis || "price",levels:benchmarkCsv(idx.levels,"level")};
}
function benchmarkMetricCard(title,kind,portfolio,index) {
 return `<section class="benchmark-kpi"><h3>${benchmarkEsc(title)}</h3><strong><bdi>${esc(benchmarkPct(portfolio))}</bdi></strong><p>${benchmarkEsc(kind)}</p>${benchmarkReason(portfolio?.status) ? `<p class="benchmark-warning">${esc(benchmarkReason(portfolio.status))}</p>` : ""}<p>${benchmarkEsc(title.includes("XIRR") ? "Benchmark XIRR, same cash flows" : "Benchmark TWRR")}: <bdi>${esc(benchmarkPct(index))}</bdi></p>${benchmarkReason(index?.status) ? `<p class="benchmark-warning">${esc(benchmarkReason(index.status))}</p>` : ""}</section>`;
}
function benchmarkChart(points) {
 const rows=(points || []).filter(row=>Number.isFinite(row.portfolio_growth)||Number.isFinite(row.benchmark_growth));
 if(rows.length<2) return `<p class="section-note">${benchmarkEsc("No exact TWRR chart available")}</p>`;
 const values=rows.flatMap(row=>[row.portfolio_growth,row.benchmark_growth]).filter(Number.isFinite), low=Math.min(100,...values), high=Math.max(100,...values), span=high-low || 1;
 const w=900,h=245,left=55,right=22,top=16,bottom=34;
 const dates=rows.map(row=>Date.parse(row.date)), first=Math.min(...dates), last=Math.max(...dates), x=i=>left+(dates[i]-first)/(last-first || 1)*(w-left-right), y=value=>top+(high-value)/span*(h-top-bottom);
 const line=key=>{let start=true;return rows.map((row,i)=>{if(!Number.isFinite(row[key])){start=true;return "";}const point=`${start ? "M" : "L"}${x(i).toFixed(2)},${y(row[key]).toFixed(2)}`;start=false;return point;}).join(" ");};
 const grid=[0,.5,1].map(part=>{const value=low+span*part,pos=y(value);return `<line class="benchmark-grid" x1="${left}" x2="${w-right}" y1="${pos}" y2="${pos}"/><text x="${left-8}" y="${pos+4}" text-anchor="end">${esc(benchmarkNumber(value,1))}</text>`;}).join("");
 const table=rows.map(row=>`<tr><td>${esc(formatDate(row.date))}</td><td>${esc(benchmarkNumber(row.portfolio_growth))}</td><td>${esc(benchmarkNumber(row.benchmark_growth))}</td></tr>`).join("");
 return `<figure class="benchmark-plot"><figcaption class="benchmark-legend"><span>${benchmarkEsc("Portfolio")}</span><span>${benchmarkEsc("Benchmark")}</span></figcaption><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${benchmarkEsc("Growth of 100")}"><title>${benchmarkEsc("Growth of 100")}</title>${grid}<path d="${line("portfolio_growth")}" class="benchmark-line-portfolio" fill="none" stroke-width="2.8"/><path d="${line("benchmark_growth")}" class="benchmark-line-index" fill="none" stroke-width="2.8"/><text x="${left}" y="${h-7}">${esc(formatDate(rows[0].date))}</text><text x="${w-right}" y="${h-7}" text-anchor="end">${esc(formatDate(rows[rows.length-1].date))}</text></svg><p class="section-note">${benchmarkEsc("Growth of 100")}</p><details class="benchmark-history"><summary>${benchmarkEsc("Show chart values")}</summary><div class="table-wrap" tabindex="0" role="region" aria-label="${benchmarkEsc("Show chart values")}"><table><thead><tr><th scope="col">${benchmarkEsc("Date")}</th><th scope="col">${benchmarkEsc("Portfolio")}</th><th scope="col">${benchmarkEsc("Benchmark")}</th></tr></thead><tbody>${table}</tbody></table></div></details></figure>`;
}
function renderBenchmarkComparison() {
 const target=$("benchmarkContent"); if(!target) return;
 const activeId=document.activeElement?.id;
 benchmarkCapture();
 const v=benchmarkView, data=v.data, f=v.filters, disabled=v.busy ? " disabled" : "", read=benchmarkCanWrite() ? "" : " readonly", ds=benchmarkCanWrite() ? "" : " disabled";
 const catalog=data?.catalog || v.catalog || [{id:"sp500",name:"S&P 500"}], accounts=data?.accounts || v.accounts || [];
 const accountOptions=`<option value="">${benchmarkEsc("All investment accounts")}</option>`+accounts.filter(row=>row.type==="Investment").map(row=>`<option value="${esc(row.id)}"${f.account_id===row.id ? " selected" : ""}>${esc(accountLabel(row))}</option>`).join("");
 const indexOptions=catalog.map(row=>`<option value="${esc(row.id)}"${f.benchmark_id===row.id ? " selected" : ""}>${benchmarkEsc(row.name)}${(row.valid_to || row.legacy_end) ? ` · ${benchmarkEsc("Legacy index")}` : ""}</option>`).join("");
 let html=`<div class="benchmark-controls"><label class="field"><span>${benchmarkEsc("Investment account")}</span><select id="benchmarkAccount"${disabled}>${accountOptions}</select></label><label class="field"><span>${benchmarkEsc("From")}</span><input id="benchmarkFrom" class="date-field" inputmode="numeric" placeholder="dd/mm/yyyy" value="${esc(formatDate(f.date_from))}"${disabled}/></label><label class="field"><span>${benchmarkEsc("To")}</span><input id="benchmarkTo" class="date-field" inputmode="numeric" placeholder="dd/mm/yyyy" value="${esc(formatDate(f.date_to))}"${disabled}/></label><label class="field"><span>${benchmarkEsc("Benchmark")}</span><select id="benchmarkIndex"${disabled}>${indexOptions}</select></label><div class="benchmark-control-actions"><button type="button" id="benchmarkCompare"${disabled}>${benchmarkEsc("Compare")}</button><button type="button" class="secondary" id="benchmarkReload" title="${benchmarkEsc("Reload replaces unsaved edits in the selected account and index forms.")}"${disabled}>${benchmarkEsc("Reload saved inputs")}</button></div></div><p id="benchmarkStatus" class="status-line" role="status" aria-live="polite">${benchmarkEsc(v.loading ? "Loading saved performance data…" : v.error)}</p>`;
 if(data?.result) {
  const r=data.result,p=r.portfolio || {},b=r.benchmark || {},idx=data.index_dataset || {},currency=r.currency || data.dataset?.currency || "";
  const amount=value=>value===null||value===undefined||!currency ? benchmarkText("Unavailable") : money(value,currency,2);
  html+=`<div class="benchmark-results" aria-busy="${String(v.loading)}"><div class="benchmark-kpis">${benchmarkMetricCard("Portfolio XIRR","Annualized, money-weighted return",p.xirr,b.xirr)}${benchmarkMetricCard("Portfolio TWRR","Cumulative, time-weighted return",p.twrr,b.twrr)}</div><div class="benchmark-facts">${[["Opening value",p.opening_value],["Closing value",p.closing_value],["Net deposits / withdrawals",p.net_flows],["Investment gain",p.gain],["Benchmark ending value",b.ending_value]].map(([label,value])=>`<span>${benchmarkEsc(label)}<b><bdi>${esc(amount(value))}</bdi></b></span>`).join("")}</div><p class="section-note"><bdi dir="ltr">${esc(formatDate(r.date_from))} – ${esc(formatDate(r.date_to))}</bdi> · ${benchmarkEsc("Currency")}: <bdi>${esc(currency || benchmarkText("Unavailable"))}</bdi></p><p class="section-note">${esc(idx.name || benchmarkText(catalog.find(row=>row.id===f.benchmark_id)?.name || ""))} · ${benchmarkEsc(idx.basis==="total_return" ? "Total return; dividends included" : "Price return; dividends excluded")} · ${benchmarkEsc("Source")}: <span dir="auto">${esc(idx.source || benchmarkText("No source supplied"))}</span>${idx.currency ? ` · <bdi>${esc(idx.currency)}</bdi>` : ""}</p>${benchmarkChart(r.chart)}${benchmarkIndexObservations(b.level_dates)}</div>`;
 } else if(data) html+=`<p class="benchmark-note">${benchmarkEsc("Returns are unavailable until complete dated values and external flows are saved. Index history is required for the same dates.")}</p>`;
 if(data) {
  const p=v.drafts[benchmarkDraftKey()],i=v.indexDrafts[f.benchmark_id];
  const field=(id,label,value,wide=false)=>`<label class="field${wide ? " benchmark-wide" : ""}"><span>${benchmarkEsc(label)}</span><input id="${id}" value="${esc(value)}"${read}${disabled}/></label>`;
  const csv=(id,label,value)=>`<label class="field"><span>${benchmarkEsc(label)}</span><textarea id="${id}" dir="ltr" spellcheck="false"${read}${disabled}>${esc(value)}</textarea>${benchmarkCanWrite() ? `<span>${benchmarkEsc("CSV file")}<input class="benchmark-file" type="file" accept=".csv,text/csv,text/plain" data-benchmark-file="${id}"${disabled}/></span>` : ""}</label>`;
  html+=`<details id="benchmarkInputs" class="benchmark-inputs"${v.editorOpen ? " open" : ""}><summary>${benchmarkEsc("Performance inputs")}</summary><p class="section-note">${benchmarkEsc("All values must describe the complete selected portfolio, including cash, in one currency. Saving performance inputs does not change holdings or account cash.")}</p><form id="benchmarkPortfolioForm"><div class="benchmark-editor">${field("benchmarkCurrency","Currency",p.currency)}${field("benchmarkSource","Source",p.source)}${csv("benchmarkValues","Portfolio value CSV",p.values)}${csv("benchmarkFlows","External cash-flow CSV",p.flows)}<p class="section-note benchmark-wide">${benchmarkEsc("Dates: dd/mm/yyyy. Values: decimal numbers without thousands separators.")}<br>${benchmarkEsc("Positive amounts are deposits; negative amounts are withdrawals. Trades, dividends and interest retained inside the account are not external flows.")}</p><label class="checkbox-field benchmark-wide"><input type="checkbox" id="benchmarkComplete"${p.flows_complete ? " checked" : ""}${ds}${disabled}/><span>${benchmarkEsc("I confirm all external deposits and withdrawals between the first and last saved valuation dates are recorded, including none if there were no flows.")}</span></label></div>${benchmarkCanWrite() ? `<div class="benchmark-actions"><button id="benchmarkSavePortfolio" type="submit"${disabled}>${benchmarkEsc("Save portfolio inputs")}</button>${data.suggested_valuations?.length ? `<button type="button" id="benchmarkUseSuggestions" class="secondary"${disabled}>${benchmarkEsc("Use saved balance suggestions")}</button>` : ""}</div>` : ""}</form><p class="section-note">${benchmarkEsc("Flows occur at end of day. Portfolio valuations must be after that day's flows. Exact TWRR needs a valuation on every cash-flow date; XIRR needs the opening and closing values and complete flows.")}</p><p class="section-note">${benchmarkEsc("Copying balance suggestions does not establish complete transaction or cash-flow history.")}</p></details>`;
  html+=`<details id="benchmarkIndexInputs" class="benchmark-inputs"${v.indexOpen ? " open" : ""}><summary>${benchmarkEsc("Index history")}</summary><p class="section-note">${benchmarkEsc("Index history must be in the portfolio currency. Import a historically converted series to compare different currencies; current exchange rates are not applied to past returns.")}</p><form id="benchmarkIndexForm"><div class="benchmark-editor">${field("benchmarkIndexName","Index name",i.name)}${field("benchmarkIndexCurrency","Currency",i.currency)}${field("benchmarkIndexSource","Source",i.source)}<label class="field"><span>${benchmarkEsc("Return basis")}</span><select id="benchmarkIndexBasis"${ds}${disabled}><option value="price"${i.basis==="price" ? " selected" : ""}>${benchmarkEsc("Price")}</option><option value="total_return"${i.basis==="total_return" ? " selected" : ""}>${benchmarkEsc("Total return")}</option></select></label>${csv("benchmarkLevels","Index levels CSV",i.levels)}</div>${benchmarkCanWrite() ? `<div class="benchmark-actions"><button id="benchmarkSaveIndex" type="submit"${disabled}>${benchmarkEsc("Save index history")}</button>${catalog.find(row=>row.id===f.benchmark_id)?.can_refresh || ["sp500","nasdaq","dow"].includes(f.benchmark_id) ? `<button type="button" id="benchmarkRefresh" class="secondary"${disabled}>${benchmarkEsc("Refresh index data")}</button>` : ""}</div>` : ""}</form></details>`;
  html+=`<p class="section-note">${benchmarkEsc("XIRR uses actual dates and a 365-day year; it is annualized even for periods shorter than a year.")} ${benchmarkEsc("After-fee portfolio return and index return may use different tax and cost assumptions.")}</p>`;
  if(!benchmarkCanWrite()) html+=`<p class="section-note">${benchmarkEsc("Viewer access: saved inputs can be inspected; only an operator or administrator can save or refresh.")}</p>`;
 }
 html+=`<p id="benchmarkSaveStatus" class="status-line benchmark-save-status" role="status" aria-live="polite">${benchmarkEsc(v.busy ? v.message || "Saving…" : v.message)}</p><p class="section-note">${benchmarkEsc("Historical results do not predict future returns.")}</p>`;
 target.innerHTML=html;v.renderedAccount=benchmarkDraftKey();v.renderedIndex=f.benchmark_id;if(activeId && $(activeId)) $(activeId).focus?.({preventScroll:true});
}
async function loadBenchmarkComparison() {
 benchmarkCapture();
 const v=benchmarkView, version=++v.version;v.loading=true;v.error="";renderBenchmarkComparison();
 const params=new URLSearchParams(Object.entries(v.filters).filter(([,value])=>value));
 try {
  const data=await api(`/api/portfolio/benchmark?${params}`);
  if(version!==benchmarkView.version) return false;
  v.data=data;v.catalog=data.catalog;v.accounts=(data.accounts || []).filter(row=>row.type==="Investment");data.accounts=v.accounts;v.filters.date_from ||= data.result?.date_from || data.date_from || "";v.filters.date_to ||= data.result?.date_to || data.date_to || "";
  benchmarkInitDrafts(data);v.loading=false;renderBenchmarkComparison();return true;
 } catch(error) {
  if(version!==benchmarkView.version) return false;
  if(v.filters.account_id && (error?.code || error?.message)==="benchmark_unknown_account"){delete v.drafts[v.filters.account_id];v.filters.account_id="";v.data=null;v.accounts=[];v.renderedAccount=undefined;v.loading=false;renderBenchmarkComparison();return loadBenchmarkComparison();}
  v.loading=false;v.error=benchmarkFailure(error,"Could not load the comparison. Your inputs are retained. Use Compare to retry.");renderBenchmarkComparison();return false;
 }
}
function benchmarkReadCsv(text,key) {
 const lines=String(text).replace(/^\uFEFF/,"").split(/\r?\n/).map(line=>line.trim()).filter(Boolean),rows=[],seen=new Set();
 if(lines.length && /^"?date"?\s*[,;\t]/i.test(lines[0])) lines.shift();
 for(const line of lines) {
  const cells=line.split(/[,;\t]/).map(cell=>cell.trim().replace(/^"|"$/g,""));
  if(cells.length!==2 || !cells[1]) throw new Error("benchmark_csv");
  const date=parseDateInput(cells[0]),value=Number(cells[1]);
  if(!date || !Number.isFinite(value) || (key!=="amount" && seen.has(date))) throw new Error("benchmark_csv");
  rows.push({date,[key]:value});seen.add(date);
 }
 return rows.sort((a,b)=>a.date.localeCompare(b.date));
}
function benchmarkReadFilters() {
 const f=benchmarkView.filters,from=parseDateInput($("benchmarkFrom")?.value),to=parseDateInput($("benchmarkTo")?.value);
 if(!from || !to || from>=to) {benchmarkView.error="Enter two valid dates with From before To.";$("benchmarkStatus").textContent=benchmarkText(benchmarkView.error);return false;}
 f.date_from=from;f.date_to=to;return true;
}
async function benchmarkSave(kind) {
 if(!benchmarkCanWrite() || benchmarkView.busy) return;
 benchmarkCapture();
 const v=benchmarkView, isIndex=kind==="index", draft=isIndex ? v.indexDrafts[v.filters.benchmark_id] : v.drafts[benchmarkDraftKey()];
 let payload;
 try {
  if(!draft.source.trim() || !/^[A-Za-z]{3}$/.test(draft.currency.trim())) throw new Error("benchmark_metadata");
  payload=isIndex ? {benchmark_id:v.filters.benchmark_id,name:draft.name,currency:draft.currency.toUpperCase(),basis:draft.basis,source:draft.source,levels:benchmarkReadCsv(draft.levels,"level")} : {account_id:v.filters.account_id,currency:draft.currency.toUpperCase(),source:draft.source,flows_complete:draft.flows_complete,valuations:benchmarkReadCsv(draft.values,"value"),cash_flows:benchmarkReadCsv(draft.flows,"amount")};
 } catch(error) {v.message=error.message==="benchmark_metadata" ? "Enter a source and a three-letter currency code." : "CSV needs two columns: date and a finite numeric value. Valuation and index dates must be unique.";renderBenchmarkComparison();return;}
 const operation=++v.operation;v.busy=true;v.message="Saving…";renderBenchmarkComparison();
 try {
  await api(`/api/local/benchmark-${isIndex ? "index" : "portfolio"}`,{method:"PUT",body:JSON.stringify(payload)});
  if(operation!==benchmarkView.operation) return;
  if(!isIndex && !v.periodEdited && payload.valuations.length>=2){v.filters.date_from=payload.valuations[0].date;v.filters.date_to=payload.valuations[payload.valuations.length-1].date;}
  const loaded=await loadBenchmarkComparison();
  if(operation!==benchmarkView.operation) return;
  v.message=loaded ? "Saved. Comparison updated." : "Saved, but the comparison could not reload. Your draft is retained. Use Compare to retry.";
 } catch(error) {if(operation===benchmarkView.operation) v.message=benchmarkFailure(error,"Could not save. Your draft is retained. Check the source, currency and dated values, then retry.");}
 if(operation!==benchmarkView.operation) return;
 v.busy=false;renderBenchmarkComparison();
}
async function benchmarkRefresh() {
 if(!benchmarkCanWrite() || benchmarkView.busy || !benchmarkReadFilters()) return;
 benchmarkCapture();const v=benchmarkView,operation=++v.operation;v.busy=true;v.message="Refreshing index data…";renderBenchmarkComparison();
 try {
  await api("/api/portfolio/benchmark/refresh",{method:"POST",body:JSON.stringify({benchmark_id:v.filters.benchmark_id,date_from:v.filters.date_from,date_to:v.filters.date_to})});
  if(operation!==benchmarkView.operation) return;
  // An explicit refresh replaces only saved index evidence; preserve the user's unsaved form.
  const loaded=await loadBenchmarkComparison();if(operation!==benchmarkView.operation) return;
  v.message=loaded ? "Index data refreshed." : "Saved, but the comparison could not reload. Your draft is retained. Use Compare to retry.";
 } catch(error) {if(operation===benchmarkView.operation) v.message=benchmarkFailure(error,"Could not refresh the index. Saved history is retained. Retry or import sourced index levels.");}
 if(operation!==benchmarkView.operation) return;v.busy=false;renderBenchmarkComparison();
}
function benchmarkIndexObservations(rows) {
 if(!rows?.length) return "";
 return `<details class="benchmark-history"><summary>${benchmarkEsc("Index observations used")}</summary><p class="section-note">${benchmarkEsc("On non-trading days, the latest earlier index observation may be used, up to 7 days old. Actual dates are shown below.")}</p><div class="table-wrap" tabindex="0" role="region" aria-label="${benchmarkEsc("Index observations used")}"><table><thead><tr>${["Required date","Observed date","Index level"].map(label=>`<th scope="col">${benchmarkEsc(label)}</th>`).join("")}</tr></thead><tbody>${rows.map(row=>`<tr><td>${esc(formatDate(row.date))}</td><td>${esc(formatDate(row.level_date))}</td><td>${esc(benchmarkNumber(row.level,4))}</td></tr>`).join("")}</tbody></table></div></details>`;
}
async function benchmarkReloadSaved() {
 if(benchmarkView.busy) return;
 benchmarkCapture();const v=benchmarkView,operation=++v.operation;v.busy=true;v.message="";renderBenchmarkComparison();
 const loaded=await loadBenchmarkComparison();if(operation!==benchmarkView.operation) return;
 if(loaded){delete v.drafts[benchmarkDraftKey()];delete v.indexDrafts[v.filters.benchmark_id];benchmarkInitDrafts(v.data);v.renderedAccount=undefined;v.renderedIndex=undefined;v.message="Saved inputs reloaded.";}
 v.busy=false;renderBenchmarkComparison();
}
async function benchmarkReadFile(input) {
 const file=input.files?.[0],id=input.dataset.benchmarkFile;if(!file || !benchmarkCanWrite() || benchmarkView.busy) return;
 benchmarkCapture();const version=benchmarkView.version, operation=++benchmarkView.operation;
 if(file.size>1000000){benchmarkView.message="The CSV file must be no larger than 1 MB.";renderBenchmarkComparison();return;}
 try {
  const text=await file.text();if(version!==benchmarkView.version || operation!==benchmarkView.operation) return;
  if($(id)) $(id).value=text;benchmarkCapture();benchmarkView.message="CSV loaded into the form. Review before saving.";
 } catch {if(operation===benchmarkView.operation) benchmarkView.message="Could not read the CSV file. Paste the values instead.";}
 if(version===benchmarkView.version && operation===benchmarkView.operation) renderBenchmarkComparison();
}
document.addEventListener("change",event=>{
 if(["benchmarkAccount","benchmarkIndex"].includes(event.target.id)) {
  if(benchmarkView.busy) return;benchmarkCapture();const v=benchmarkView;
  if(event.target.id==="benchmarkAccount") v.filters.account_id=event.target.value;else v.filters.benchmark_id=event.target.value;
  v.data=null;v.message="";loadBenchmarkComparison();
 }
 if(event.target.matches?.("[data-benchmark-file]")) benchmarkReadFile(event.target);
});
document.addEventListener("input",event=>{if(["benchmarkFrom","benchmarkTo"].includes(event.target.id)){benchmarkView.periodEdited=true;benchmarkView.filters[event.target.id==="benchmarkFrom" ? "date_from" : "date_to"]=parseDateInput(event.target.value) || event.target.value;}if(event.target.closest?.("#benchmarkContent")) benchmarkCapture();});
document.addEventListener("submit",event=>{
 if(event.target.id==="benchmarkPortfolioForm"){event.preventDefault();benchmarkSave("portfolio");}
 if(event.target.id==="benchmarkIndexForm"){event.preventDefault();benchmarkSave("index");}
});
document.addEventListener("click",event=>{
 if(event.target.closest("#benchmarkCompare")){if(!benchmarkView.busy && benchmarkReadFilters()) loadBenchmarkComparison();}
 if(event.target.closest("#benchmarkRefresh")) benchmarkRefresh();
 if(event.target.closest("#benchmarkReload")) benchmarkReloadSaved();
 if(event.target.closest("#benchmarkUseSuggestions") && benchmarkCanWrite() && !benchmarkView.busy){
  benchmarkCapture();const v=benchmarkView,draft=v.drafts[benchmarkDraftKey()];draft.values=benchmarkCsv(v.data.suggested_valuations,"value");draft.flows_complete=false;v.message="Balance suggestions copied. Review every valuation, add all external flows and confirm completeness before saving.";renderBenchmarkComparison();
 }
});
