/* Stock/fund sleeve: value-sized tiles, observed native-price moves, saved data only. */
let heatmapView = { version: 0, loading: false, error: false, data: null, account_id: "", layout: "combined", selected: null };
const HEATMAP_HE = {
  "Portfolio stocks heatmap": "מפת חום של מניות התיק", "Method and data": "שיטה ונתונים", "Area: gross ILS value · Color: latest observed price move": "שטח: שווי ברוטו בשקלים · צבע: שינוי המחיר האחרון שנצפה", "Investment account": "חשבון השקעות", "All investment accounts": "כל חשבונות ההשקעה", "View": "תצוגה", "Combined holdings": "החזקות מאוחדות", "By account": "לפי חשבון", "Reload saved data": "טעינת נתונים שמורים מחדש",
  "Loading saved stock data…": "טוען נתוני מניות שמורים…", "Could not load the heatmap. Use Reload saved data to retry.": "לא ניתן לטעון את מפת החום. יש לנסות שוב באמצעות טעינת נתונים שמורים מחדש.",
  "Previous saved result shown; the latest reload failed.": "מוצגת התוצאה השמורה הקודמת; הטעינה האחרונה נכשלה.",
  "Tile area = gross stock/fund value in ILS. Color = latest observed price change in the security's currency.": "שטח האריח = שווי ברוטו של מניות וקרנות בשקלים. הצבע = שינוי המחיר האחרון שנצפה במטבע הנייר.",
  "Fall": "ירידה", "Rise": "עלייה", "No change / unavailable": "ללא שינוי / לא זמין", "Colors saturate at ±3%.": "עוצמת הצבע מגיעה לשיאה ב־±3%.",
  "Priced gross exposure": "חשיפה ברוטו עם שווי זמין", "Sized listings": "ניירות עם שטח מחושב", "Known price moves": "שינויי מחיר זמינים", "As of": "נכון ל־", "Unavailable": "לא זמין",
  "No stock or fund holdings in this account scope.": "אין החזקות במניות או בקרנות בחשבונות שנבחרו.",
  "Each account panel is scaled independently. Compare the ILS amounts to compare account sizes.": "השטח בכל לוח חשבון מחושב בנפרד. להשוואת גודל החשבונות יש להשוות את הסכומים בשקלים.",
  "Select a tile or a listing for prices, dates and account holdings.": "בחרו אריח או נייר ברשימה להצגת מחירים, תאריכים והחזקות לפי חשבון.",
  "All listings and values": "כל הניירות והשווי שלהם", "Holdings without a tile": "החזקות ללא אריח", "No fresh ILS value; these holdings are excluded from tile sizes and the priced gross total.": "אין שווי עדכני בשקלים; החזקות אלה אינן נכללות בשטחי האריחים ובסך החשיפה עם שווי זמין.",
  "Excluded holdings": "החזקות מחוץ למפה", "Cash, bonds, pensions and derivatives are outside this stock/fund heatmap.": "מזומן, אג״ח, פנסיה ונגזרים אינם נכללים במפת המניות והקרנות.",
  "Price change": "שינוי מחיר", "Gross value": "שווי ברוטו", "Share of priced gross exposure": "חלק מהחשיפה ברוטו עם שווי זמין", "Latest price": "מחיר אחרון", "Previous observation": "תצפית קודמת", "Quantity": "כמות", "Net quantity": "כמות נטו", "Short exposure": "חשיפה בחסר", "Long and short exposure": "חשיפה בלונג ובחסר", "Net value": "שווי נטו", "Stock": "מניה", "ETF": "קרן סל", "Fund": "קרן", "Security": "נייר", "Stock Heatmap": "מפת חום של מניות",
  "Saved exchange metadata is needed to identify this imported listing.": "נדרשים נתוני בורסה שמורים כדי לזהות את הנייר המיובא הזה.", "No saved price is available.": "אין מחיר שמור זמין.", "The latest saved price is more than 7 days old.": "המחיר השמור האחרון ישן מ־7 ימים.", "A previous price observation is missing.": "חסרה תצפית מחיר קודמת.", "Price observations are more than 7 days apart.": "תצפיות המחיר מרוחקות זו מזו יותר מ־7 ימים.", "A saved exchange rate to ILS is missing.": "חסר שער חליפין שמור לשקל.", "The saved exchange rate is more than 7 days old.": "שער החליפין השמור ישן מ־7 ימים.", "The recorded position is invalid.": "הפוזיציה הרשומה אינה תקינה.", "Asset classifications conflict for this listing.": "יש סתירה בסיווגי הנכס עבור נייר זה.", "The position value could not be calculated.": "לא ניתן לחשב את שווי הפוזיציה.", "This asset is outside the stock/fund scope.": "נכס זה אינו נכלל בתחום המניות והקרנות.", "Data is incomplete.": "הנתונים אינם מלאים.",
  "Observed prices may span more than one trading session. Dates can differ between markets. Raw price changes can reflect splits or dividends; they exclude FX and are not position profit or total return.": "המחירים שנצפו עשויים להשתרע על יותר מיום מסחר אחד. התאריכים עשויים להיות שונים בין שווקים. שינויי מחיר לא מתואמים עשויים לשקף פיצולים או דיבידנדים; הם אינם כוללים מט״ח ואינם רווח הפוזיציה או תשואה כוללת.",
  "Long and short positions are added by absolute value for tile sizes; they are not netted across accounts.": "גודל האריח מחבר את השווי המוחלט של פוזיציות לונג וחסר; אין קיזוז בין חשבונות.", "Saved exchange rates": "שערי חליפין שמורים", "ILS per unit": "שקלים ליחידת מטבע", "Source": "מקור", "External imported market data": "נתוני שוק ממקור מיובא", "Bank of Israel": "בנק ישראל", "Saved price source": "מקור המחיר השמור", "Local": "מקומי", "Cached provider": "ספק שמור במטמון", "Local and cached": "מקומי ומטמון", "Price observations": "תצפיות מחיר", "Recorded holdings only; no trades or external writes.": "החזקות רשומות בלבד; ללא ביצוע מסחר או כתיבה למקור חיצוני.", "No positions": "אין פוזיציות", "priced listings": "ניירות עם שווי זמין", "of": "מתוך", "Not all recorded holdings have a fresh ILS value. The total covers priced holdings only.": "לא לכל ההחזקות הרשומות יש שווי עדכני בשקלים. הסכום כולל רק החזקות עם שווי זמין."
};
function heatmapText(text) { return state.language === "he" ? (HEATMAP_HE[text] || t(text)) : text; }
function heatmapEsc(text) { return esc(heatmapText(text)); }
function heatmapKnown(value) { return typeof value === "number" && Number.isFinite(value); }
function heatmapMoney(value, currency = "ILS") { return heatmapKnown(value) ? money(value, currency, 2) : heatmapText("Unavailable"); }
function heatmapPercent(value) { return heatmapKnown(value) ? `${value > 0 ? "+" : ""}${fmt(value, 2)}%` : heatmapText("Unavailable"); }
function heatmapSum(values) { if (!values.every(heatmapKnown)) return null; const result = values.reduce((sum, value) => sum + value, 0); return Number.isFinite(result) ? result : null; }
function heatmapReason(code) { return ({unverified_listing:"Saved exchange metadata is needed to identify this imported listing.",missing_price:"No saved price is available.",stale_price:"The latest saved price is more than 7 days old.",missing_previous_price:"A previous price observation is missing.",sparse_prices:"Price observations are more than 7 days apart.",missing_fx:"A saved exchange rate to ILS is missing.",stale_fx:"The saved exchange rate is more than 7 days old.",invalid_position:"The recorded position is invalid.",classification_conflict:"Asset classifications conflict for this listing.",invalid_value:"The position value could not be calculated.",unsupported_asset:"This asset is outside the stock/fund scope."})[code] || "Data is incomplete."; }
function heatmapClass(asset) { return /ETF/i.test(asset.asset_class || "") ? "ETF" : /STOCK|EQUITY|RSU/i.test(asset.asset_class || "") ? "Stock" : "Fund"; }
function heatmapLabel(asset) { return [asset.symbol, asset.resolved_stock_market || (/^YAHOO$/i.test(asset.stock_market || "") ? "" : asset.stock_market), currencyDisplayLabel(asset.currency)].filter(Boolean).join(" · "); }
function heatmapAccount(id) { const row = heatmapView.data?.accounts?.find(account => account.id === id); return row ? accountLabel(row) : id; }
function heatmapFxSource(source) { return heatmapText(({external_import_market_data:"External imported market data",bank_of_israel_fx:"Bank of Israel",frankfurter_fx:"Frankfurter",financial_modeling_prep:"Financial Modeling Prep",alpha_vantage:"Alpha Vantage",yahoo_finance:"Yahoo Finance",google_finance:"Google Finance",nasdaq_quote:"Nasdaq",stooq:"Stooq"})[source] || source); }
function heatmapScope(accountId = heatmapView.account_id) {
  const allowed=new Set((heatmapView.data?.accounts || []).filter(row=>row.type==="Investment").map(row=>row.id));
  if(accountId&&!allowed.has(accountId))return [];
  if(accountId && Array.isArray(heatmapView.data?.account_assets?.[accountId]))return heatmapView.data.account_assets[accountId];
  return (heatmapView.data?.assets || []).map(asset => {
    const accounts = (asset.accounts || []).filter(row => allowed.has(row.account_id) && (!accountId || row.account_id === accountId));
    if (!accounts.length) return null;
    return {...asset, accounts, quantity:heatmapSum(accounts.map(row => row.quantity)), gross_quantity:heatmapSum(accounts.map(row => Math.abs(row.quantity))), gross_value_ils:heatmapSum(accounts.map(row => row.gross_value_ils)), value_ils:heatmapSum(accounts.map(row => row.value_ils))};
  }).filter(Boolean);
}
function heatmapDirection(asset) {
  const short = asset.accounts.some(row => row.quantity < 0), long = asset.accounts.some(row => row.quantity > 0);
  return short ? long ? "Long and short exposure" : "Short exposure" : "";
}
function heatmapExcluded() { return (heatmapView.data?.excluded || []).filter(row => !heatmapView.account_id || row.account_id === heatmapView.account_id); }
function heatmapColor(value) {
  if (!heatmapKnown(value) || value === 0) return "#27354b";
  const intensity = Math.min(Math.abs(value) / 3, 1);
  return value > 0 ? `hsl(165 58% ${19 + intensity * 9}%)` : `hsl(350 56% ${22 + intensity * 10}%)`;
}
/* Balanced rectangle splits preserve each asset's share, without minimum-area distortion. */
function heatmapRectangles(items) {
  if (!items.length) return [];
  const max = Math.max(...items.map(row => row.gross_value_ils));
  if (!(max > 0)) return [];
  const weighted = items.map(item => ({item,weight:item.gross_value_ils/max})).sort((a,b) => b.weight-a.weight || String(a.item.id).localeCompare(String(b.item.id)));
  function split(rows,x,y,width,height) {
    if (rows.length === 1) return [{asset:rows[0].item,x,y,width,height}];
    const total=rows.reduce((sum,row)=>sum+row.weight,0);let left=0,at=1,best=Infinity;
    for(let i=1;i<rows.length;i++){left+=rows[i-1].weight;const difference=Math.abs(total/2-left);if(difference<best){best=difference;at=i;}else break;}
    const first=rows.slice(0,at),second=rows.slice(at),ratio=first.reduce((sum,row)=>sum+row.weight,0)/total;
    // The visual canvas is about twice as wide as it is tall on desktop.
    return width*1.7>=height ? [...split(first,x,y,width*ratio,height),...split(second,x+width*ratio,y,width*(1-ratio),height)] : [...split(first,x,y,width,height*ratio),...split(second,x,y+height*ratio,width,height*(1-ratio))];
  }
  return split(weighted,0,0,100,100);
}
function heatmapValueFraction(asset, assets) { const max=Math.max(...assets.map(row=>row.gross_value_ils || 0));if(!(max>0)||!heatmapKnown(asset.gross_value_ils))return null;return (asset.gross_value_ils/max)/assets.reduce((sum,row)=>sum+(heatmapKnown(row.gross_value_ils)?row.gross_value_ils/max:0),0)*100; }
function heatmapButtonLabel(asset) { return `${heatmapLabel(asset)}; ${heatmapText(heatmapClass(asset))}; ${heatmapText("Gross value")}: ${heatmapMoney(asset.gross_value_ils)}; ${heatmapText("Price change")}: ${heatmapPercent(asset.change_percent)}${heatmapDirection(asset)?`; ${heatmapText(heatmapDirection(asset))}`:""}`; }
function heatmapTileMap(assets, accountId="") {
  const sized=assets.filter(asset=>heatmapKnown(asset.gross_value_ils)&&asset.gross_value_ils>0);
  if(!sized.length)return "";
  const all=heatmapView.data.assets;
  return `<div class="heatmap-canvas" role="group" aria-label="${heatmapEsc("Stock Heatmap")}">${heatmapRectangles(sized).map(rect=>{
    const asset=rect.asset,index=all.findIndex(row=>row.id===asset.id),tiny=rect.width<10 || rect.height<13;
    const label=heatmapButtonLabel(asset),direction=heatmapDirection(asset);
    return `<button type="button" class="heatmap-tile${tiny?" heatmap-tiny":""}" style="left:${rect.x}%;top:${rect.y}%;width:${rect.width}%;height:${rect.height}%;background:${heatmapColor(asset.change_percent)}" data-heatmap-asset="${index}" data-heatmap-account="${esc(accountId)}" aria-label="${esc(label)}" title="${esc(label)}" aria-pressed="false"><span aria-hidden="true"><bdi>${esc(asset.symbol)}</bdi><strong><bdi>${esc(heatmapPercent(asset.change_percent))}</bdi></strong><small><bdi>${esc(heatmapMoney(asset.gross_value_ils))}</bdi></small>${direction?`<small>${heatmapEsc(direction)}</small>`:""}</span></button>`;
  }).join("")}</div>`;
}
function heatmapListing(asset, accountId="") {
  const index=heatmapView.data.assets.findIndex(row=>row.id===asset.id);
  return `<li><button type="button" class="heatmap-listing" data-heatmap-asset="${index}" data-heatmap-account="${esc(accountId)}" aria-pressed="false"><span><bdi>${esc(heatmapLabel(asset))}</bdi><small>${esc(asset.name || "")} · ${heatmapEsc(heatmapClass(asset))}${heatmapDirection(asset)?` · ${heatmapEsc(heatmapDirection(asset))}`:""}</small></span><span><bdi>${esc(heatmapMoney(asset.gross_value_ils))}</bdi><small><bdi>${esc(heatmapPercent(asset.change_percent))}</bdi></small></span></button></li>`;
}
function renderHeatmapSelection() {
  const target=$("heatmapSelection");if(!target)return;
  const selected=heatmapView.selected;
  const assets=heatmapScope(selected?.account_id || heatmapView.account_id),asset=assets.find(row=>row.id===selected?.id);
  if(!asset){target.innerHTML="";return;}
  const issues=[...new Set(asset.issues || [])];
  const fact=(label,value)=>`<div><dt>${heatmapEsc(label)}</dt><dd>${value}</dd></div>`;
  target.innerHTML=`<h3><bdi>${esc(heatmapLabel(asset))}</bdi></h3><p>${esc(asset.name || "")} · ${heatmapEsc(heatmapClass(asset))}${heatmapDirection(asset)?` · ${heatmapEsc(heatmapDirection(asset))}`:""}</p><dl class="heatmap-facts">${fact("Gross value",`<bdi>${esc(heatmapMoney(asset.gross_value_ils))}</bdi>`)}${fact("Net value",`<bdi>${esc(heatmapMoney(asset.value_ils))}</bdi>`)}${fact("Share of priced gross exposure",heatmapKnown(heatmapValueFraction(asset,assets))?`<bdi>${esc(fmt(heatmapValueFraction(asset,assets),2))}%</bdi>`:heatmapEsc("Unavailable"))}${fact("Price change",`<bdi>${esc(heatmapPercent(asset.change_percent))}</bdi>`)}${fact("Latest price",`${heatmapKnown(asset.price)?`<bdi>${esc(heatmapMoney(asset.price,asset.currency))}</bdi>`:heatmapEsc("Unavailable")}${asset.price_date?` · <bdi>${esc(formatDate(asset.price_date))}</bdi>`:""}`)}${fact("Previous observation",`${heatmapKnown(asset.previous_price)?`<bdi>${esc(heatmapMoney(asset.previous_price,asset.currency))}</bdi>`:heatmapEsc("Unavailable")}${asset.previous_date?` · <bdi>${esc(formatDate(asset.previous_date))}</bdi>`:""}`)}${fact("Net quantity",heatmapKnown(asset.quantity)?`<bdi>${esc(fmt(asset.quantity,4))}</bdi>`:heatmapEsc("Unavailable"))}${fact("Saved price source",heatmapEsc(({local:"Local",cached:"Cached provider",merged:"Local and cached"})[asset.source] || "Unavailable"))}</dl>${issues.length?`<ul class="heatmap-issues">${issues.map(code=>`<li>${heatmapEsc(heatmapReason(typeof code==="string"?code:code.code))}</li>`).join("")}</ul>`:""}<ul class="heatmap-account-list">${asset.accounts.map(row=>`<li><bdi>${esc(heatmapAccount(row.account_id))}</bdi> · ${heatmapEsc("Quantity")}: <bdi>${heatmapKnown(row.quantity)?esc(fmt(row.quantity,4)):heatmapEsc("Unavailable")}</bdi> · ${heatmapEsc("Gross value")}: <bdi>${esc(heatmapMoney(row.gross_value_ils))}</bdi></li>`).join("")}</ul>`;
  const all=heatmapView.data.assets,index=all.findIndex(row=>row.id===asset.id);
  $("heatmapContent")?.querySelectorAll?.("[data-heatmap-asset]").forEach(button=>button.setAttribute("aria-pressed",String(Number(button.dataset.heatmapAsset)===index && (button.dataset.heatmapAccount || "")===(selected.account_id || ""))));
}
function renderDashboardHeatmap() {
  return `<div class="chart-card portfolio-heatmap-card"><div class="chart-header"><h3 class="chart-title">${heatmapEsc("Portfolio stocks heatmap")}</h3><button type="button" id="heatmapReload" class="secondary heatmap-reload" aria-label="${heatmapEsc("Reload saved data")}" title="${heatmapEsc("Reload saved data")}"${heatmapView.loading?" disabled":""}>↻</button></div><div id="heatmapContent"></div></div>`;
}
function renderHeatmap() {
  const target=$("heatmapContent");if(!target)return;
  const v=heatmapView,d=v.data;const restoreInteraction=typeof preserveRenderedInteraction==="function"?preserveRenderedInteraction(target):()=>{};target.setAttribute?.("aria-busy",String(v.loading));if($("heatmapReload"))$("heatmapReload").disabled=v.loading;
  let html=`<div class="heatmap-controls"><label class="field"><span>${heatmapEsc("Investment account")}</span><select id="heatmapAccount"><option value="">${heatmapEsc("All investment accounts")}</option>${(d?.accounts || []).filter(row=>row.type==="Investment").map(row=>`<option value="${esc(row.id)}"${v.account_id===row.id?" selected":""}>${esc(accountLabel(row))}</option>`).join("")}</select></label><label class="field"><span>${heatmapEsc("View")}</span><select id="heatmapLayout"><option value="combined"${v.layout==="combined"?" selected":""}>${heatmapEsc("Combined holdings")}</option><option value="accounts"${v.layout==="accounts"?" selected":""}>${heatmapEsc("By account")}</option></select></label></div><p class="status-line" id="heatmapStatus" role="status" aria-live="polite">${heatmapEsc(v.loading?"Loading saved stock data…":v.error?"Could not load the heatmap. Use Reload saved data to retry.":"")}</p>`;
  if(d){
    if(v.error)html+=`<p class="heatmap-notice">${heatmapEsc("Previous saved result shown; the latest reload failed.")}</p>`;
    const assets=heatmapScope(),sized=assets.filter(asset=>heatmapKnown(asset.gross_value_ils)&&asset.gross_value_ils>0),unsized=assets.filter(asset=>!heatmapKnown(asset.gross_value_ils)||asset.gross_value_ils<=0),total=heatmapSum(sized.map(asset=>asset.gross_value_ils));
    html+=`<p class="heatmap-explainer">${heatmapEsc("Area: gross ILS value · Color: latest observed price move")}</p><div class="heatmap-legend"><span class="heatmap-loss">${heatmapEsc("Fall")}</span><span class="heatmap-neutral">${heatmapEsc("No change / unavailable")}</span><span class="heatmap-gain">${heatmapEsc("Rise")}</span><small>${heatmapEsc("Colors saturate at ±3%.")}</small></div><div class="heatmap-summary"><span>${heatmapEsc("Priced gross exposure")}<b><bdi>${sized.length?esc(heatmapMoney(total)):heatmapEsc("Unavailable")}</bdi></b></span><span>${heatmapEsc("Sized listings")}<b>${sized.length} ${heatmapEsc("of")} ${assets.length}</b></span><span>${heatmapEsc("Known price moves")}<b>${assets.filter(asset=>heatmapKnown(asset.change_percent)).length} ${heatmapEsc("of")} ${assets.length}</b></span>${d.as_of?`<span>${heatmapEsc("As of")}<b><bdi>${esc(formatDate(d.as_of))}</bdi></b></span>`:""}</div>`;
    if(unsized.length)html+=`<p class="heatmap-notice">${heatmapEsc("Not all recorded holdings have a fresh ILS value. The total covers priced holdings only.")}</p>`;
    if(!assets.length)html+=`<p>${heatmapEsc("No stock or fund holdings in this account scope.")}</p>`;
    else{
      html+=`<p class="section-note">${heatmapEsc("Select a tile or a listing for prices, dates and account holdings.")}</p>`;
      if(v.layout==="accounts"){
        html+=`<p class="section-note">${heatmapEsc("Each account panel is scaled independently. Compare the ILS amounts to compare account sizes.")}</p><div class="heatmap-account-panels" data-preserve-scroll="heatmap-accounts">${(d.accounts || []).filter(row=>row.type==="Investment" && (!v.account_id||row.id===v.account_id)).map(row=>{const scoped=heatmapScope(row.id),priced=scoped.filter(item=>heatmapKnown(item.gross_value_ils)&&item.gross_value_ils>0);return `<section class="heatmap-account-panel"><h3><bdi>${esc(accountLabel(row))}</bdi></h3><p><bdi>${priced.length?esc(heatmapMoney(heatmapSum(priced.map(item=>item.gross_value_ils)))):heatmapEsc("Unavailable")}</bdi> · ${priced.length}/${scoped.length} ${heatmapEsc("priced listings")}</p>${scoped.length?heatmapTileMap(scoped,row.id):`<p class="section-note">${heatmapEsc("No positions")}</p>`}</section>`;}).join("")}</div>`;
      }else html+=heatmapTileMap(assets);
      html+=`<section id="heatmapSelection" class="heatmap-selection" aria-live="polite"></section>`;
      if(unsized.length)html+=`<details class="heatmap-unsized"><summary>${heatmapEsc("Holdings without a tile")} (${unsized.length})</summary><p class="section-note">${heatmapEsc("No fresh ILS value; these holdings are excluded from tile sizes and the priced gross total.")}</p><ul class="heatmap-list">${unsized.map(asset=>heatmapListing(asset)).join("")}</ul></details>`;
      html+=`<details class="heatmap-all-list"><summary>${heatmapEsc("All listings and values")} (${assets.length})</summary><ul class="heatmap-list">${assets.map(asset=>heatmapListing(asset)).join("")}</ul></details>`;
    }
    const excluded=heatmapExcluded();html+=`<details id="heatmapMethod" class="heatmap-method"><summary>${heatmapEsc("Method and data")}</summary><p class="section-note">${heatmapEsc("Tile area = gross stock/fund value in ILS. Color = latest observed price change in the security's currency.")}</p><p class="section-note">${heatmapEsc("Cash, bonds, pensions and derivatives are outside this stock/fund heatmap.")}</p>`;
    if(excluded.length)html+=`<details class="heatmap-excluded"><summary>${heatmapEsc("Excluded holdings")} (${excluded.length})</summary><ul>${excluded.map(row=>`<li><bdi>${esc([row.symbol,row.stock_market,row.account_id?heatmapAccount(row.account_id):""].filter(Boolean).join(" · "))}</bdi> · ${heatmapEsc(heatmapReason(row.reason || "unsupported_asset"))}</li>`).join("")}</ul></details>`;
    if(d.fx?.length)html+=`<details class="heatmap-fx"><summary>${heatmapEsc("Saved exchange rates")}</summary><ul>${d.fx.map(row=>`<li><bdi>${esc(currencyDisplayLabel(row.currency))}</bdi> · ${heatmapEsc("ILS per unit")}: <bdi>${heatmapKnown(row.rate)?esc(fmt(row.rate,6)):heatmapEsc("Unavailable")}</bdi>${row.date?` · <bdi>${esc(formatDate(row.date))}</bdi>`:""}${row.source?` · ${heatmapEsc("Source")}: ${esc(heatmapFxSource(row.source))}`:""}${row.status&&row.status!=="ok"?` · ${heatmapEsc(heatmapReason(row.status))}`:""}</li>`).join("")}</ul></details>`;
    html+=`<p class="section-note">${heatmapEsc("Observed prices may span more than one trading session. Dates can differ between markets. Raw price changes can reflect splits or dividends; they exclude FX and are not position profit or total return.")}</p><p class="section-note">${heatmapEsc("Long and short positions are added by absolute value for tile sizes; they are not netted across accounts.")}</p><p class="section-note">${heatmapEsc("Recorded holdings only; no trades or external writes.")}</p></details>`;
  }
  target.innerHTML=html;renderHeatmapSelection();restoreInteraction();
}
function resetHeatmap() { heatmapView={version:heatmapView.version+1,loading:false,error:false,data:null,account_id:"",layout:"combined",selected:null};renderHeatmap(); }
async function loadHeatmap() {
  const v=heatmapView,version=++v.version;v.loading=true;v.error=false;renderHeatmap();
  try{const data=await api("/api/portfolio/heatmap");if(version!==heatmapView.version)return;data.accounts=(data.accounts || []).filter(row=>row.type==="Investment");v.data=data;v.loading=false;if(v.account_id&&!(data.accounts || []).some(row=>row.id===v.account_id)){v.account_id="";v.selected=null;}renderHeatmap();}
  catch{if(version!==heatmapView.version)return;v.loading=false;v.error=true;renderHeatmap();}
}
document.addEventListener("change",event=>{if(event.target.id==="heatmapAccount"){heatmapView.account_id=event.target.value;heatmapView.selected=null;renderHeatmap();$("heatmapAccount")?.focus?.({preventScroll:true});}if(event.target.id==="heatmapLayout"){heatmapView.layout=event.target.value;heatmapView.selected=null;renderHeatmap();$("heatmapLayout")?.focus?.({preventScroll:true});}});
document.addEventListener("click",event=>{if(event.target.closest?.("#heatmapReload")&&!heatmapView.loading)loadHeatmap();const button=event.target.closest?.("[data-heatmap-asset]");if(button){const asset=heatmapView.data?.assets?.[Number(button.dataset.heatmapAsset)];if(asset){heatmapView.selected={id:asset.id,account_id:button.dataset.heatmapAccount || ""};renderHeatmapSelection();}}});
