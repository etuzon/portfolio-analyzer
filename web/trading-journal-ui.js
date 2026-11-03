/* A recorded decision and later reviews remain separate, dated observations. */
let tradingJournalView = {
  version: 0, operation: 0, loading: false, busy: false, data: null,
  selected: "", rendered: "", error: "", message: "", drafts: {},
  filters: {account: "", action: "", review: "", query: ""},
};

const TRADING_JOURNAL_HE = Object.freeze({
  "Trading Journal": "יומן מסחר", "Account": "חשבון", "All accounts": "כל החשבונות",
  "Action": "פעולה", "All actions": "כל הפעולות", "Buy": "קנייה", "Sell": "מכירה", "Short": "מכירה בחסר",
  "Add": "הוספה", "Remove": "הסרה", "Dividend": "דיבידנד", "Interest": "ריבית", "Fee": "עמלה",
  "Review": "סקירה", "All reviews": "כל הסקירות", "Not reviewed": "טרם נסקר", "Good": "טובה", "Mixed": "מעורבת", "Bad": "גרועה",
  "Due for review": "הגיע מועד הסקירה", "Search reasons or symbols": "חיפוש סיבות או סימולים", "Reload": "טעינה מחדש",
  "Loading saved journal…": "טוען את היומן השמור…", "Could not load the journal. Your draft is retained. Use Reload to retry.": "לא ניתן לטעון את היומן. הטיוטה נשמרה. לחצו על טעינה מחדש כדי לנסות שוב.",
  "Record why you made a trade, then revisit the decision and what you learned.": "רשמו מדוע ביצעתם עסקה, ובהמשך חזרו להחלטה וללקחים ממנה.",
  "Choose a recorded trade": "בחירת עסקה רשומה", "Select a buy, sell or short transaction": "בחרו עסקת קנייה, מכירה או מכירה בחסר",
  "No recorded buy, sell or short transactions are available. Record a transaction in Positions first.": "אין עסקאות קנייה, מכירה או מכירה בחסר רשומות. תחילה רשמו עסקה במסך החזקות.",
  "No journal entries yet. Choose a recorded trade to add its reason.": "עדיין אין רשומות ביומן. בחרו עסקה רשומה כדי להוסיף את הסיבה לה.",
  "No entries match these filters.": "אין רשומות התואמות למסננים האלה.", "journal entries": "רשומות ביומן", "Open entry": "פתיחת רשומה", "Journal": "יומן",
  "Captured trade": "העסקה בעת הרישום", "Current ledger trade": "העסקה הנוכחית ביומן העסקאות", "Units": "יחידות", "Unit price": "מחיר ליחידה",
  "Trade date": "תאריך העסקה", "Reason recorded": "מועד רישום הסיבה", "Review date": "תאריך לסקירה", "No review date": "לא נקבע מועד לסקירה",
  "This trade changed after the journal entry was recorded. The captured trade is preserved.": "העסקה השתנתה לאחר יצירת הרשומה ביומן. פרטי העסקה בעת הרישום נשמרו.",
  "This transaction was deleted. The recorded decision and reviews remain available.": "העסקה נמחקה. ההחלטה שנרשמה והסקירות נשארות זמינות.",
  "Why I made this trade": "מדוע ביצעתי את העסקה", "What would change my mind?": "מה יגרום לי לשנות את דעתי?", "Optional": "רשות",
  "Save reason": "שמירת הסיבה", "Save reasoning revision": "שמירת עדכון לסיבה", "Each saved revision keeps the earlier reasoning and its recording time.": "כל עדכון שנשמר משמר את הסיבות הקודמות ואת מועד רישומן.",
  "Your assessment": "ההערכה שלכם", "What happened and what did I learn?": "מה קרה ומה למדתי?", "Save review": "שמירת סקירה",
  "Choose an assessment": "בחירת הערכה",
  "Assess the decision using your original reasoning and later evidence.": "העריכו את ההחלטה לפי הסיבה המקורית והנתונים שהתקבלו בהמשך.",
  "Reason history": "היסטוריית הסיבות", "Original reason": "הסיבה המקורית", "Reasoning revision": "עדכון לסיבה", "Review history": "היסטוריית הסקירות",
  "No reviews yet.": "עדיין אין סקירות.", "Price change since trade": "שינוי המחיר מאז העסקה", "Saved price": "מחיר שמור", "Price date": "תאריך המחיר",
  "Price-only evidence excludes dividends, fees, taxes and split adjustments. It is not realized trade profit or an automatic decision rating.": "הנתון מבוסס על שינוי המחיר בלבד, ללא דיבידנדים, עמלות, מסים או התאמות לפיצולים. הוא אינו רווח ממומש מהעסקה או דירוג אוטומטי של ההחלטה.",
  "For a sale or short sale, a lower subsequent price supports the trade direction.": "במכירה או במכירה בחסר, מחיר נמוך יותר בהמשך תומך בכיוון העסקה.",
  "Saved price is more than 7 days old.": "המחיר השמור ישן מ־7 ימים.", "No later saved price is available.": "אין מחיר שמור מתאריך מאוחר יותר.",
  "Price comparison is unavailable for this instrument.": "השוואת מחירים אינה זמינה למכשיר הזה.", "The captured trade has no usable unit price.": "בעסקה שנשמרה אין מחיר תקין ליחידה.",
  "Price evidence is unavailable after this trade changed.": "נתוני השוואת המחיר אינם זמינים לאחר שהעסקה השתנתה.", "Price evidence is unavailable for a deleted transaction.": "נתוני השוואת המחיר אינם זמינים לעסקה שנמחקה.",
  "Unavailable": "לא זמין", "Saving…": "שומר…", "Saved.": "נשמר.", "Saved, but the journal could not reload. Use Reload to retry.": "נשמר, אך לא ניתן לטעון מחדש את היומן. לחצו על טעינה מחדש כדי לנסות שוב.",
  "Could not save. Your draft is retained. Retry after checking the fields.": "לא ניתן לשמור. הטיוטה נשמרה. בדקו את השדות ונסו שוב.",
  "Enter why you made this trade, up to 5000 characters.": "הזינו מדוע ביצעתם את העסקה, עד 5000 תווים.", "Enter a valid review date as dd/mm/yyyy, or leave it blank.": "הזינו תאריך תקין לסקירה בתבנית יום/חודש/שנה, או השאירו ריק.",
  "Enter your review and lessons, up to 5000 characters.": "הזינו את הסקירה והלקחים, עד 5000 תווים.", "Each text field can contain up to 5000 characters.": "כל שדה טקסט יכול להכיל עד 5000 תווים.",
  "This entry changed elsewhere. Your draft is retained. Load the saved entry before saving again.": "הרשומה השתנתה במקום אחר. הטיוטה נשמרה. טענו את הרשומה השמורה לפני שמירה נוספת.",
  "The transaction is unavailable for a new journal entry. Reload to choose another trade.": "העסקה אינה זמינה ליצירת רשומה חדשה ביומן. טענו מחדש ובחרו עסקה אחרת.",
  "Choose Good, Mixed or Bad for your review.": "בחרו בהערכה טובה, מעורבת או גרועה לסקירה.", "The entry is unavailable. Reload the journal.": "הרשומה אינה זמינה. טענו את היומן מחדש.",
  "Discard draft and load saved entry": "ביטול הטיוטה וטעינת הרשומה השמורה", "Saved entry loaded.": "הרשומה השמורה נטענה.",
  "Viewer access: you can read saved decisions and reviews. An operator or administrator can add or update them.": "גישה לצפייה: ניתן לקרוא החלטות וסקירות שמורות. מפעיל או מנהל יכולים להוסיף ולעדכן אותן.",
  "Choose an entry to read its reason and reviews, or select a transaction to record a new reason.": "בחרו רשומה כדי לקרוא את הסיבה והסקירות שלה, או בחרו עסקה כדי לרשום סיבה חדשה.",
  "This draft is based on an older saved version.": "הטיוטה מבוססת על גרסה שמורה קודמת.", "Recorded by": "נרשם בידי",
  "This entry has reached its history limit. Earlier reasons and reviews are preserved.": "הרשומה הגיעה למגבלת ההיסטוריה. הסיבות והסקירות הקודמות נשמרו.",
  "The journal has reached its entry limit. Existing decisions and reviews remain available.": "היומן הגיע למגבלת הרשומות. ההחלטות והסקירות הקיימות נשארות זמינות.",
  "Saved journal data could not be read. Restore a valid local backup or ask an administrator for help.": "לא ניתן לקרוא את נתוני היומן השמורים. שחזרו גיבוי מקומי תקין או פנו למנהל לקבלת עזרה.",
});

function tradingJournalText(text) {
  return state.language === "he" ? (TRADING_JOURNAL_HE[text] || t(text)) : text;
}
function tradingJournalEsc(text) { return esc(tradingJournalText(text)); }
function tradingJournalCanWrite() { return typeof canWrite === "function" && canWrite(); }
function tradingJournalAction(action) { return tradingJournalText({BUY:"Buy", SELL:"Sell", SHORT:"Short",ADD:"Add",REMOVE:"Remove",DIVIDEND:"Dividend",INTEREST:"Interest",FEE:"Fee"}[action] || "Action"); }
function tradingJournalRating(rating) { return tradingJournalText({good:"Good", mixed:"Mixed", bad:"Bad", pending:"Not reviewed"}[rating] || "Not reviewed"); }
function tradingJournalStamp(value) { return value ? formatDateTime(value) : "—"; }
function tradingJournalDue(row) {
  return typeof row.review_due === "boolean" ? row.review_due : row.review_status==="pending" && !!row.review_date && row.review_date<=(tradingJournalView.data?.as_of_date || tradingJournalView.data?.as_of || "");
}
function tradingJournalRestoreFocus(id) {
  if(!$("tradingJournalModal")?.hidden && $(id) && !$(id).disabled) $(id).focus?.({preventScroll:true});
}
function tradingJournalSelected() { return (tradingJournalView.data?.items || []).find(row=>row.id === tradingJournalView.selected); }
function tradingJournalTrade() {
  return tradingJournalSelected()?.trade || (tradingJournalView.data?.transactions || []).find(row=>row.id === tradingJournalView.selected);
}
function tradingJournalDraft(id=tradingJournalView.selected) {
  const v=tradingJournalView;
  if(!id) return null;
  const row=(v.data?.items || []).find(item=>item.id===id);
  return v.drafts[id] ||= {reason:row?.reason || "",thesis:row?.thesis || "",review_date:row?.review_date || "",expected_revision:row?.revision || 0,rating:"",notes:""};
}
function tradingJournalCapture() {
  const v=tradingJournalView,draft=v.drafts[v.rendered];
  if(!draft) return;
  [["reason","journalReason"],["thesis","journalThesis"],["review_date","journalReviewDate"],["rating","journalRating"],["notes","journalReviewNotes"]].forEach(([key,id])=>{
    if($(id)) draft[key]=$(id).value;
  });
}
function resetTradingJournal() {
  const v=tradingJournalView;
  tradingJournalView={version:v.version+1,operation:v.operation+1,loading:false,busy:false,data:null,selected:"",rendered:"",error:"",message:"",drafts:{},filters:{account:"",action:"",review:"",query:""}};
  renderTradingJournal();
}
function tradingJournalFailure(error,fallback) {
  const code=error?.code || error?.message;
  return ({journal_conflict:"This entry changed elsewhere. Your draft is retained. Load the saved entry before saving again.",
    journal_reason_required:"Enter why you made this trade, up to 5000 characters.", journal_invalid_reason:"Enter why you made this trade, up to 5000 characters.",
    journal_invalid_text:"Each text field can contain up to 5000 characters.", journal_text_too_long:"Each text field can contain up to 5000 characters.",
    journal_invalid_review_date:"Enter a valid review date as dd/mm/yyyy, or leave it blank.", journal_invalid_date:"Enter a valid review date as dd/mm/yyyy, or leave it blank.", journal_invalid_rating:"Choose Good, Mixed or Bad for your review.",
    journal_notes_required:"Enter your review and lessons, up to 5000 characters.", journal_review_notes_required:"Enter your review and lessons, up to 5000 characters.", journal_invalid_notes:"Enter your review and lessons, up to 5000 characters.",
    journal_transaction_missing:"The transaction is unavailable for a new journal entry. Reload to choose another trade.", journal_transaction_not_found:"The transaction is unavailable for a new journal entry. Reload to choose another trade.", journal_invalid_transaction:"The transaction is unavailable for a new journal entry. Reload to choose another trade.",
    journal_unsupported_action:"The transaction is unavailable for a new journal entry. Reload to choose another trade.", journal_invalid_action:"The transaction is unavailable for a new journal entry. Reload to choose another trade.", journal_not_found:"The entry is unavailable. Reload the journal.",
    journal_revision_required:"This entry changed elsewhere. Your draft is retained. Load the saved entry before saving again.",
    journal_history_limit:"This entry has reached its history limit. Earlier reasons and reviews are preserved.", journal_entry_limit:"The journal has reached its entry limit. Existing decisions and reviews remain available.",
    journal_invalid_saved_entry:"Saved journal data could not be read. Restore a valid local backup or ask an administrator for help.",
  })[code] || fallback;
}
function tradingJournalTradeLabel(trade) {
  return [trade?.symbol, tradingJournalAction(trade?.action), trade?.trade_date ? formatDate(trade.trade_date) : "", trade?.account_label].filter(Boolean).join(" · ");
}
function tradingJournalFiltered() {
  const v=tradingJournalView,f=v.filters,query=f.query.trim().toLocaleLowerCase();
  return (v.data?.items || []).filter(row=>{
    const trade=row.trade || {};
    return (!f.account || trade.account_id===f.account) && (!f.action || trade.action===f.action)
      && (!f.review || (f.review==="due" ? tradingJournalDue(row) : row.review_status===f.review))
      && (!query || [trade.symbol,trade.name,trade.account_label,row.reason,row.thesis,...(row.reviews || []).map(review=>review.notes)].join(" ").toLocaleLowerCase().includes(query));
  });
}
function tradingJournalFacts(trade,label) {
  const price=Number.isFinite(trade.price) && trade.currency ? money(trade.price,trade.currency,4) : tradingJournalText("Unavailable");
  return `<section class="journal-facts"><h3>${tradingJournalEsc(label)}</h3><p class="journal-trade-title"><bdi>${esc([trade.symbol,trade.stock_market].filter(Boolean).join(" · "))}</bdi> · ${esc(tradingJournalAction(trade.action))} · <bdi>${esc(formatDate(trade.trade_date || ""))}</bdi></p><p dir="auto">${esc(trade.account_label || "")}</p><dl><div><dt>${tradingJournalEsc("Units")}</dt><dd><bdi>${esc(Number.isFinite(trade.quantity) ? fmt(trade.quantity,4) : "—")}</bdi></dd></div><div><dt>${tradingJournalEsc("Unit price")}</dt><dd><bdi>${esc(price)}</bdi></dd></div></dl></section>`;
}
function tradingJournalOutcome(row) {
  const outcome=row.outcome || {}, known=Number.isFinite(outcome.price_change_percent) && ["ok","stale"].includes(outcome.status);
  const reasons={stale:"Saved price is more than 7 days old.",no_later_price:"No later saved price is available.",unsupported_instrument:"Price comparison is unavailable for this instrument.",invalid_trade_price:"The captured trade has no usable unit price.",link_changed:"Price evidence is unavailable after this trade changed.",deleted_transaction:"Price evidence is unavailable for a deleted transaction."};
  return `<section class="journal-outcome"><h3>${tradingJournalEsc("Price change since trade")}</h3>${known ? `<strong class="${outcome.price_change_percent>0 ? "positive" : outcome.price_change_percent<0 ? "negative" : ""}"><bdi>${esc((outcome.price_change_percent>0 ? "+" : "")+fmt(outcome.price_change_percent,2))}%</bdi></strong><p>${tradingJournalEsc("Saved price")}: <bdi>${esc(money(outcome.last_price,outcome.currency || row.trade.currency,4))}</bdi> · ${tradingJournalEsc("Price date")}: <bdi>${esc(formatDate(outcome.last_price_date))}</bdi></p>` : `<p>${tradingJournalEsc("Unavailable")}</p>`}${reasons[outcome.status] ? `<p class="section-note">${tradingJournalEsc(reasons[outcome.status])}</p>` : ""}${["SELL","SHORT"].includes(row.trade.action) ? `<p class="section-note">${tradingJournalEsc("For a sale or short sale, a lower subsequent price supports the trade direction.")}</p>` : ""}<p class="section-note">${tradingJournalEsc("Price-only evidence excludes dividends, fees, taxes and split adjustments. It is not realized trade profit or an automatic decision rating.")}</p></section>`;
}
function tradingJournalHistory(row) {
  const reasons=(row.reason_history || []).map((item,index)=>`<li><p><b>${tradingJournalEsc(index===0 ? "Original reason" : "Reasoning revision")}</b> · <bdi>${esc(tradingJournalStamp(item.recorded_at))}</bdi>${item.author ? ` · <span dir="auto">${esc(item.author)}</span>` : ""}</p><p class="journal-prose" dir="auto">${esc(item.reason || "")}</p>${item.thesis ? `<p class="journal-prose" dir="auto">${esc(item.thesis)}</p>` : ""}${item.review_date ? `<p>${tradingJournalEsc("Review date")}: <bdi>${esc(formatDate(item.review_date))}</bdi></p>` : ""}</li>`).join("");
  const reviews=[...(row.reviews || [])].reverse().map(item=>`<li><p><b class="journal-rating journal-rating-${esc(item.rating)}">${esc(tradingJournalRating(item.rating))}</b> · <bdi>${esc(tradingJournalStamp(item.recorded_at))}</bdi>${item.author ? ` · <span dir="auto">${esc(item.author)}</span>` : ""}</p><p class="journal-prose" dir="auto">${esc(item.notes || "")}</p></li>`).join("");
  return `<details class="journal-history"><summary>${tradingJournalEsc("Reason history")} (${(row.reason_history || []).length})</summary><ol>${reasons}</ol></details><details class="journal-history"><summary>${tradingJournalEsc("Review history")} (${(row.reviews || []).length})</summary>${reviews ? `<ol>${reviews}</ol>` : `<p>${tradingJournalEsc("No reviews yet.")}</p>`}</details>`;
}
function renderTradingJournal() {
  const target=$("tradingJournalContent");if(!target) return;
  tradingJournalCapture();
  const activeId=typeof document!=="undefined" ? document.activeElement?.id : "";
  const activeStart=document.activeElement?.selectionStart,activeEnd=document.activeElement?.selectionEnd;
  const v=tradingJournalView,d=v.data,f=v.filters,disabled=v.busy ? " disabled" : "",read=tradingJournalCanWrite() ? "" : " readonly";
  let html=`<p class="section-note">${tradingJournalEsc("Record why you made a trade, then revisit the decision and what you learned.")}</p>`;
  const accounts=new Map((d?.accounts || []).map(row=>[row.id,{id:row.id,label:accountLabel(row)}]));
  for(const row of d?.items || []) if(!accounts.has(row.trade.account_id)) accounts.set(row.trade.account_id,{id:row.trade.account_id,label:row.trade.account_label || row.trade.account_id});
  html+=`<div class="journal-controls"><label class="field"><span>${tradingJournalEsc("Account")}</span><select id="journalAccount"${disabled}><option value="">${tradingJournalEsc("All accounts")}</option>${[...accounts.values()].map(row=>`<option value="${esc(row.id)}"${f.account===row.id ? " selected" : ""}>${esc(row.label)}</option>`).join("")}</select></label><label class="field"><span>${tradingJournalEsc("Action")}</span><select id="journalAction"${disabled}><option value="">${tradingJournalEsc("All actions")}</option>${["BUY","SELL","SHORT"].map(action=>`<option value="${action}"${f.action===action ? " selected" : ""}>${esc(tradingJournalAction(action))}</option>`).join("")}</select></label><label class="field"><span>${tradingJournalEsc("Review")}</span><select id="journalReviewFilter"${disabled}><option value="">${tradingJournalEsc("All reviews")}</option>${["pending","good","mixed","bad","due"].map(rating=>`<option value="${rating}"${f.review===rating ? " selected" : ""}>${rating==="due" ? tradingJournalEsc("Due for review") : esc(tradingJournalRating(rating))}</option>`).join("")}</select></label><label class="field journal-search"><span>${tradingJournalEsc("Search reasons or symbols")}</span><input id="journalQuery" value="${esc(f.query)}"${disabled}/></label><button type="button" class="secondary" id="journalReload"${disabled}>${tradingJournalEsc("Reload")}</button></div><p id="journalStatus" class="status-line" role="status" aria-live="polite">${tradingJournalEsc(v.loading ? "Loading saved journal…" : v.error)}</p>`;
  if(d) {
    const transactions=[...(d.transactions || [])];
    const selected=tradingJournalSelected();
    if(selected && !transactions.some(tx=>tx.id===selected.id)) transactions.push({...selected.trade,id:selected.id});
    if(transactions.length) html+=`<label class="field journal-transaction-picker"><span>${tradingJournalEsc("Choose a recorded trade")}</span><select id="journalTransaction"${disabled}><option value="">${tradingJournalEsc("Select a buy, sell or short transaction")}</option>${transactions.map(tx=>`<option value="${esc(tx.id)}"${v.selected===tx.id ? " selected" : ""}>${esc(tradingJournalTradeLabel(tx))}</option>`).join("")}</select></label>`;
    else html+=`<p class="journal-empty">${tradingJournalEsc("No recorded buy, sell or short transactions are available. Record a transaction in Positions first.")}</p>`;
    const rows=tradingJournalFiltered();
    html+=`<p class="section-note journal-count">${rows.length} ${tradingJournalEsc("journal entries")}</p><div class="journal-layout"><div class="journal-list" aria-label="${tradingJournalEsc("Trading Journal")}">${rows.length ? rows.map(row=>`<article class="journal-list-entry${v.selected===row.id ? " selected" : ""}"><div class="journal-entry-heading"><bdi>${esc(row.trade.symbol)}</bdi><span class="journal-rating journal-rating-${esc(row.review_status)}">${esc(tradingJournalRating(row.review_status))}</span></div><p>${esc(tradingJournalAction(row.trade.action))} · <bdi>${esc(formatDate(row.trade.trade_date))}</bdi></p><p dir="auto">${esc(row.trade.account_label || "")}</p><p class="journal-entry-reason" dir="auto">${esc(row.reason || "")}</p>${row.review_date ? `<p class="section-note">${tradingJournalEsc(tradingJournalDue(row) ? "Due for review" : "Review date")}: <bdi>${esc(formatDate(row.review_date))}</bdi></p>` : ""}<div class="row-actions"><button type="button" class="secondary compact-button" data-journal-entry="${esc(row.id)}"${disabled}>${tradingJournalEsc("Open entry")}</button></div></article>`).join("") : `<p class="journal-empty">${tradingJournalEsc(d.items?.length ? "No entries match these filters." : "No journal entries yet. Choose a recorded trade to add its reason.")}</p>`}</div><div id="journalDetail" class="journal-detail">`;
    const trade=tradingJournalTrade();
    if(trade) {
      const draft=tradingJournalDraft();
      if(selected?.link_status==="changed") html+=`<p class="journal-notice" role="note">${tradingJournalEsc("This trade changed after the journal entry was recorded. The captured trade is preserved.")}</p>`;
      if(selected?.link_status==="deleted") html+=`<p class="journal-notice" role="note">${tradingJournalEsc("This transaction was deleted. The recorded decision and reviews remain available.")}</p>`;
      html+=tradingJournalFacts(trade,selected ? "Captured trade" : "Choose a recorded trade");
      if(selected?.link_status==="changed" && selected.current_trade) html+=tradingJournalFacts(selected.current_trade,"Current ledger trade");
      if(selected) html+=`<p class="section-note">${tradingJournalEsc("Reason recorded")}: <bdi>${esc(tradingJournalStamp(selected.created_at))}</bdi></p>${tradingJournalOutcome(selected)}`;
      if(selected && draft.expected_revision!==selected.revision) html+=`<p class="journal-notice">${tradingJournalEsc("This draft is based on an older saved version.")}</p>`;
      html+=`<form id="journalReasonForm" class="journal-form" novalidate><label class="field"><span>${tradingJournalEsc("Why I made this trade")}</span><textarea id="journalReason" dir="auto" maxlength="5000" required${read}${disabled}>${esc(draft.reason)}</textarea></label><label class="field"><span>${tradingJournalEsc("What would change my mind?")} · ${tradingJournalEsc("Optional")}</span><textarea id="journalThesis" dir="auto" maxlength="5000"${read}${disabled}>${esc(draft.thesis)}</textarea></label><label class="field journal-date"><span>${tradingJournalEsc("Review date")} · ${tradingJournalEsc("Optional")}</span><input id="journalReviewDate" class="date-field" inputmode="numeric" placeholder="dd/mm/yyyy" value="${esc(formatDate(draft.review_date))}"${read}${disabled}/></label>${tradingJournalCanWrite() ? `<div class="journal-actions"><button id="journalSaveReason" type="submit"${disabled}>${tradingJournalEsc(selected ? "Save reasoning revision" : "Save reason")}</button><button id="journalDiscard" type="button" class="secondary"${disabled}>${tradingJournalEsc("Discard draft and load saved entry")}</button></div>` : ""}<p class="section-note">${tradingJournalEsc("Each saved revision keeps the earlier reasoning and its recording time.")}</p></form>`;
      if(selected) {
        html+=`<form id="journalReviewForm" class="journal-form" novalidate><h3>${tradingJournalEsc("Review")}</h3><p class="section-note">${tradingJournalEsc("Assess the decision using your original reasoning and later evidence.")}</p><label class="field journal-rating-field"><span>${tradingJournalEsc("Your assessment")}</span><select id="journalRating"${tradingJournalCanWrite() ? "" : " disabled"}${disabled}><option value="">${tradingJournalEsc("Choose an assessment")}</option>${["good","mixed","bad"].map(rating=>`<option value="${rating}"${draft.rating===rating ? " selected" : ""}>${esc(tradingJournalRating(rating))}</option>`).join("")}</select></label><label class="field"><span>${tradingJournalEsc("What happened and what did I learn?")}</span><textarea id="journalReviewNotes" maxlength="5000" dir="auto" required${read}${disabled}>${esc(draft.notes)}</textarea></label>${tradingJournalCanWrite() ? `<div class="journal-actions"><button id="journalSaveReview" type="submit"${disabled}>${tradingJournalEsc("Save review")}</button></div>` : ""}</form>${tradingJournalHistory(selected)}`;
      }
    } else html+=`<p class="journal-empty">${tradingJournalEsc("Choose an entry to read its reason and reviews, or select a transaction to record a new reason.")}</p>`;
    html+=`</div></div>`;
  }
  if(!tradingJournalCanWrite()) html+=`<p class="section-note">${tradingJournalEsc("Viewer access: you can read saved decisions and reviews. An operator or administrator can add or update them.")}</p>`;
  html+=`<p id="journalSaveStatus" class="status-line" role="status" aria-live="polite">${tradingJournalEsc(v.busy ? "Saving…" : v.message)}</p>`;
  target.innerHTML=html;v.rendered=v.selected;
  if(activeId && $(activeId)) {
    $(activeId).focus?.({preventScroll:true});
    if(Number.isInteger(activeStart) && Number.isInteger(activeEnd)) $(activeId).setSelectionRange?.(activeStart,activeEnd);
  }
}
async function loadTradingJournal() {
  tradingJournalCapture();
  const v=tradingJournalView,version=++v.version;
  v.loading=true;v.error="";renderTradingJournal();
  try {
    const data=await api("/api/local/trading-journal");
    if(version!==tradingJournalView.version) return false;
    v.data=data;v.loading=false;
    if(v.selected) tradingJournalDraft();
    renderTradingJournal();return true;
  } catch(error) {
    if(version!==tradingJournalView.version) return false;
    v.loading=false;v.error=tradingJournalFailure(error,"Could not load the journal. Your draft is retained. Use Reload to retry.");renderTradingJournal();return false;
  }
}
function openTradingJournal(transactionId="",returnFocus=document.activeElement) {
  tradingJournalCapture();
  const v=tradingJournalView;
  if(!v.busy && transactionId) {v.selected=String(transactionId);v.filters={account:"",action:"",review:"",query:""};v.message="";}
  if($("tradingJournalModal")?.hidden && typeof openModal==="function") openModal("tradingJournalModal",returnFocus);
  else {if(v.data) {tradingJournalDraft();renderTradingJournal();} else loadTradingJournal();}
}
async function saveTradingJournal(kind="reason") {
  const v=tradingJournalView;
  if(!tradingJournalCanWrite() || v.busy || !v.selected) return;
  tradingJournalCapture();
  const id=v.selected,draft=tradingJournalDraft(),isReview=kind==="review";
  let date="";
  if(isReview) {
    if(!["good","mixed","bad"].includes(draft.rating)) {v.message="Choose Good, Mixed or Bad for your review.";renderTradingJournal();return;}
    if(!draft.notes.trim() || draft.notes.length>5000) {v.message="Enter your review and lessons, up to 5000 characters.";renderTradingJournal();return;}
  } else {
    if(!draft.reason.trim() || draft.reason.length>5000) {v.message="Enter why you made this trade, up to 5000 characters.";renderTradingJournal();return;}
    if(draft.thesis.length>5000) {v.message="Each text field can contain up to 5000 characters.";renderTradingJournal();return;}
    date=draft.review_date ? parseDateInput(draft.review_date) : "";
    if(draft.review_date && !date) {v.message="Enter a valid review date as dd/mm/yyyy, or leave it blank.";renderTradingJournal();return;}
  }
  const payload=isReview ? {expected_revision:draft.expected_revision,rating:draft.rating,notes:draft.notes.trim()} : {transaction_id:id,expected_revision:draft.expected_revision,reason:draft.reason.trim(),thesis:draft.thesis.trim(),review_date:date};
  const operation=++v.operation;v.busy=true;v.message="";renderTradingJournal();
  try {
    const result=await api(isReview ? `/api/local/trading-journal/${encodeURIComponent(id)}/reviews` : "/api/local/trading-journal",{method:isReview ? "POST" : "PUT",body:JSON.stringify(payload)});
    if(operation!==tradingJournalView.operation) return;
    if(result.entry) {
      const offset=(v.data?.items || []).findIndex(row=>row.id===id);
      if(offset>=0) v.data.items[offset]=result.entry;else if(v.data) v.data.items.unshift(result.entry);
      draft.expected_revision=result.entry.revision;
      if(isReview) {draft.notes="";draft.rating="";}
      else Object.assign(draft,{reason:result.entry.reason,thesis:result.entry.thesis || "",review_date:result.entry.review_date || ""});
      // Remove stale field nodes before the saved server state is rendered.
      v.rendered="";
    }
    const loaded=await loadTradingJournal();
    if(operation!==tradingJournalView.operation) return;
    v.message=loaded ? "Saved." : "Saved, but the journal could not reload. Use Reload to retry.";
  } catch(error) {
    if(operation!==tradingJournalView.operation) return;
    v.message=tradingJournalFailure(error,"Could not save. Your draft is retained. Retry after checking the fields.");
  }
  if(operation!==tradingJournalView.operation) return;
  v.busy=false;renderTradingJournal();tradingJournalRestoreFocus(isReview ? "journalSaveReview" : "journalSaveReason");
}
async function discardTradingJournalDraft() {
  const v=tradingJournalView;
  if(v.busy || !v.selected) return;
  tradingJournalCapture();const id=v.selected,operation=++v.operation;
  v.busy=true;v.message="";renderTradingJournal();
  const loaded=await loadTradingJournal();
  if(operation!==tradingJournalView.operation) return;
  if(loaded) {delete v.drafts[id];v.rendered="";tradingJournalDraft(id);v.message="Saved entry loaded.";}
  v.busy=false;renderTradingJournal();tradingJournalRestoreFocus("journalDiscard");
}
document.addEventListener("input",event=>{
  if(event.target.id==="journalQuery") {tradingJournalView.filters.query=event.target.value;renderTradingJournal();return;}
  if(event.target.closest?.("#tradingJournalContent")) tradingJournalCapture();
});
document.addEventListener("change",event=>{
  const v=tradingJournalView;if(v.busy) return;
  const filter={journalAccount:"account",journalAction:"action",journalReviewFilter:"review"}[event.target.id];
  if(filter) {tradingJournalCapture();v.filters[filter]=event.target.value;renderTradingJournal();}
  if(event.target.id==="journalTransaction") {tradingJournalCapture();v.selected=event.target.value;v.message="";tradingJournalDraft();renderTradingJournal();}
});
document.addEventListener("submit",event=>{
  if(event.target.id==="journalReasonForm") {event.preventDefault();saveTradingJournal("reason");}
  if(event.target.id==="journalReviewForm") {event.preventDefault();saveTradingJournal("review");}
});
document.addEventListener("click",event=>{
  const shortcut=event.target.closest?.("[data-trading-journal]");if(shortcut) {openTradingJournal(shortcut.dataset.tradingJournal,shortcut);return;}
  const entry=event.target.closest?.("[data-journal-entry]");if(entry && !tradingJournalView.busy) {tradingJournalCapture();tradingJournalView.selected=entry.dataset.journalEntry;tradingJournalView.message="";tradingJournalDraft();renderTradingJournal();$("journalDetail")?.scrollIntoView?.({block:"nearest"});return;}
  if(event.target.closest?.("#journalReload") && !tradingJournalView.busy) loadTradingJournal();
  if(event.target.closest?.("#journalDiscard")) discardTradingJournalDraft();
});
