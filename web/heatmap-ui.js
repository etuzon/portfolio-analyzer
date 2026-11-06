/* Investment securities: value-sized rectangles, observed native-price moves, saved data only. */
let heatmapView = { version: 0, loading: false, error: false, data: null, account_id: "", layout: "combined", selected: null, categories: { stocks:true, bonds:true, funds:true } };
const HEATMAP_HE = {
  "Recorded daily FX quotes": "שערי מטבע יומיים שנשמרו",
  "valued listings": "ניירות עם שווי זמין",
  "Known gross exposure": "חשיפה ברוטו ששווייה ידוע",
  "Weight of known gross holdings": "משקל מתוך ההחזקות ברוטו ששוויין ידוע",
  "weight": "משקל",
  "Valuation basis": "בסיס השווי",
  "Valuation status": "מצב השווי",
  "Saved price": "מחיר שמור",
  "Recorded holding value": "שווי החזקה רשום",
  "Cost-based estimate": "אומדן לפי עלות",
  "Mixed valuation bases": "בסיסי שווי מעורבים",
  "Current": "עדכני",
  "Stale": "ישן",
  "Estimated": "משוער",
  "No ILS value is available; these holdings are outside the map and its known gross total.": "אין שווי זמין בשקלים; החזקות אלה אינן מוצגות במפה ואינן נכללות בסך החשיפה ברוטו ששווייה ידוע.",
  "Some selected holdings have no ILS value. Weights cover known gross holdings only, excluding cash.": "לחלק מההחזקות שנבחרו אין שווי זמין בשקלים. המשקלים כוללים רק החזקות ברוטו ששוויין ידוע, ללא מזומן.",
  "Includes older or estimated values. Select a security to inspect its basis and dates.": "הנתונים כוללים שווי ישן או משוער. בחרו נייר ערך לבדיקת בסיס השווי והתאריכים.",
  "A recorded holding value or cost basis is used as an estimate; it is not a current market price.": "שווי החזקה רשום או בסיס עלות משמשים כאומדן; זה אינו מחיר שוק נוכחי.",
  "Weight uses known gross values for the selected accounts and asset types; cash and unvalued holdings are excluded.": "המשקל משתמש בשווי ברוטו ידוע בחשבונות ובסוגי הנכסים שנבחרו; מזומן והחזקות ללא שווי אינם נכללים.",
  "Portfolio stocks heatmap": "מפת חום של מניות התיק", "Method and data": "שיטה ונתונים", "Area: gross ILS value · Color: latest observed price move": "שטח: שווי ברוטו בשקלים · צבע: שינוי המחיר האחרון שנצפה", "Investment account": "חשבון השקעות", "All investment accounts": "כל חשבונות ההשקעה", "View": "תצוגה", "Combined holdings": "החזקות מאוחדות", "By account": "לפי חשבון", "Reload saved data": "טעינת נתונים שמורים מחדש",
  "Loading saved securities data…": "טוען נתוני ניירות ערך שמורים…", "Could not load the heatmap. Use Reload saved data to retry.": "לא ניתן לטעון את מפת החום. יש לנסות שוב באמצעות טעינת נתונים שמורים מחדש.",
  "Previous saved result shown; the latest reload failed.": "מוצגת התוצאה השמורה הקודמת; הטעינה האחרונה נכשלה.",
  "Map area = gross value of the selected securities in ILS. Color = latest observed price change in the security's currency.": "שטח המלבן = שווי ברוטו של ניירות הערך שנבחרו בשקלים. הצבע = שינוי המחיר האחרון שנצפה במטבע הנייר.",
  "Fall": "ירידה", "Rise": "עלייה", "No change / unavailable": "ללא שינוי / לא זמין", "Colors saturate at ±3%.": "עוצמת הצבע מגיעה לשיאה ב־±3%.",
  "Asset types": "סוגי נכסים", "Stocks": "מניות", "Bonds": "אג״ח", "Funds": "קרנות", "Bond": "אג״ח", "Company": "חברה", "Accounts": "חשבונות", "Gross quantity": "כמות ברוטו", "Unrealized profit / loss": "רווח / הפסד לא ממומש", "Converted to ILS": "המרה לשקלים", "Observed price change": "שינוי המחיר שנצפה", "Choose Stocks, Bonds or Funds to display holdings.": "בחרו מניות, אג״ח או קרנות כדי להציג החזקות.", "No holdings match the selected asset types in this account scope.": "אין החזקות מסוגי הנכסים שנבחרו בחשבונות אלה.", "The recorded cost basis is unavailable or invalid.": "בסיס העלות הרשום חסר או אינו תקין.", "ILS profit is the native-currency unrealized profit converted at the current saved FX rate; it does not measure historical FX profit.": "הרווח בשקלים הוא הרווח הלא ממומש במטבע הנייר, לפי שער המט״ח השמור הנוכחי; הוא אינו מודד רווח היסטורי משינויי מט״ח.", "Priced gross exposure": "חשיפה ברוטו עם שווי זמין", "Sized listings": "ניירות עם שטח מחושב", "Known price moves": "שינויי מחיר זמינים", "As of": "נכון ל־", "Unavailable": "לא זמין",
  "Each account panel is scaled independently. Compare the ILS amounts to compare account sizes.": "השטח בכל לוח חשבון מחושב בנפרד. להשוואת גודל החשבונות יש להשוות את הסכומים בשקלים.",
  "Select a security in the map or list for prices, dates and account holdings.": "בחרו נייר ערך במפה או ברשימה להצגת מחירים, תאריכים והחזקות לפי חשבון.",
  "All listings and values": "כל הניירות והשווי שלהם", "Holdings not shown on the map": "החזקות שלא מוצגות במפה", "No fresh ILS value; these holdings are outside the map and the priced gross total.": "אין שווי עדכני בשקלים; החזקות אלה אינן מוצגות במפה ואינן נכללות בשטחי המלבנים ובסך החשיפה עם שווי זמין.",
  "Excluded holdings": "החזקות מחוץ למפה", "Cash, pensions and derivatives are outside this securities heatmap.": "מזומן, פנסיה ונגזרים אינם נכללים במפת ניירות הערך.",
  "Price change": "שינוי מחיר", "Gross value": "שווי ברוטו", "Share of priced gross exposure": "חלק מהחשיפה ברוטו עם שווי זמין", "Latest price": "מחיר אחרון", "Previous observation": "תצפית קודמת", "Quantity": "כמות", "Net quantity": "כמות נטו", "Short exposure": "חשיפה בחסר", "Long and short exposure": "חשיפה בלונג ובחסר", "Net value": "שווי נטו", "Stock": "מניה", "ETF": "קרן סל", "Fund": "קרן", "Security": "נייר", "Stock Heatmap": "מפת חום של מניות",
  "Saved exchange metadata is needed to identify this imported listing.": "נדרשים נתוני בורסה שמורים כדי לזהות את הנייר המיובא הזה.", "No saved price is available.": "אין מחיר שמור זמין.", "The latest saved price is more than 7 days old.": "המחיר השמור האחרון ישן מ־7 ימים.", "A previous price observation is missing.": "חסרה תצפית מחיר קודמת.", "Price observations are more than 7 days apart.": "תצפיות המחיר מרוחקות זו מזו יותר מ־7 ימים.", "A saved exchange rate to ILS is missing.": "חסר שער חליפין שמור לשקל.", "The saved exchange rate is more than 7 days old.": "שער החליפין השמור ישן מ־7 ימים.", "The recorded position is invalid.": "הפוזיציה הרשומה אינה תקינה.", "Asset classifications conflict for this listing.": "יש סתירה בסיווגי הנכס עבור נייר זה.", "The position value could not be calculated.": "לא ניתן לחשב את שווי הפוזיציה.", "This asset is outside the supported securities scope.": "נכס זה אינו נכלל בסוגי ניירות הערך הנתמכים.", "Data is incomplete.": "הנתונים אינם מלאים.",
  "Observed prices may span more than one trading session. Dates can differ between markets. Raw price changes can reflect splits or dividends; they exclude FX and are not position profit or total return.": "המחירים שנצפו עשויים להשתרע על יותר מיום מסחר אחד. התאריכים עשויים להיות שונים בין שווקים. שינויי מחיר לא מתואמים עשויים לשקף פיצולים או דיבידנדים; הם אינם כוללים מט״ח ואינם רווח הפוזיציה או תשואה כוללת.",
  "Long and short positions are added by absolute value for rectangle sizes; they are not netted across accounts.": "גודל המלבן מחבר את השווי המוחלט של פוזיציות לונג וחסר; אין קיזוז בין חשבונות.", "Saved exchange rates": "שערי חליפין שמורים", "ILS per unit": "שקלים ליחידת מטבע", "Source": "מקור", "External imported market data": "נתוני שוק ממקור מיובא", "Bank of Israel": "בנק ישראל", "Saved price source": "מקור המחיר השמור", "Local": "מקומי", "Cached provider": "ספק שמור במטמון", "Local and cached": "מקומי ומטמון", "Price observations": "תצפיות מחיר", "Recorded holdings only; no trades or external writes.": "החזקות רשומות בלבד; ללא ביצוע מסחר או כתיבה למקור חיצוני.", "No positions": "אין פוזיציות", "priced listings": "ניירות עם שווי זמין", "of": "מתוך", "Not all recorded holdings have a fresh ILS value. The total covers priced holdings only.": "לא לכל ההחזקות הרשומות יש שווי עדכני בשקלים. הסכום כולל רק החזקות עם שווי זמין."
};
function heatmapText(text) { return state.language === "he" ? (HEATMAP_HE[text] || t(text)) : text; }
function heatmapEsc(text) { return esc(heatmapText(text)); }
function heatmapKnown(value) { return typeof value === "number" && Number.isFinite(value); }
function heatmapMoney(value, currency = "ILS") { return heatmapKnown(value) ? money(value, currency, 2) : heatmapText("Unavailable"); }
function heatmapPercent(value) { return heatmapKnown(value) ? `${value > 0 ? "+" : ""}${fmt(value, 2)}%` : heatmapText("Unavailable"); }
function heatmapSum(values) { if (!values.every(heatmapKnown)) return null; const result = values.reduce((sum, value) => sum + value, 0); return Number.isFinite(result) ? result : null; }
function heatmapReason(code) { return ({unverified_listing:"Saved exchange metadata is needed to identify this imported listing.",missing_price:"No saved price is available.",stale_price:"The latest saved price is more than 7 days old.",missing_previous_price:"A previous price observation is missing.",sparse_prices:"Price observations are more than 7 days apart.",estimated_value:"A recorded holding value or cost basis is used as an estimate; it is not a current market price.",missing_fx:"A saved exchange rate to ILS is missing.",stale_fx:"The saved exchange rate is more than 7 days old.",invalid_cost_basis:"The recorded cost basis is unavailable or invalid.",invalid_position:"The recorded position is invalid.",classification_conflict:"Asset classifications conflict for this listing.",invalid_value:"The position value could not be calculated.",unsupported_asset:"This asset is outside the supported securities scope."})[code] || "Data is incomplete."; }
function heatmapValuationBasis(asset) { return ({saved_price:"Saved price",recorded_value:"Recorded holding value",cost_basis:"Cost-based estimate",mixed:"Mixed valuation bases"})[asset.valuation_basis] || "Unavailable"; }
function heatmapValuationStatus(asset) { return ({current:"Current",stale:"Stale",estimated:"Estimated"})[asset.valuation_status] || "Unavailable"; }
function heatmapValuationFacts(asset) { return heatmapFact("Valuation basis",heatmapEsc(heatmapValuationBasis(asset)))+heatmapFact("Valuation status",heatmapEsc(heatmapValuationStatus(asset))); }
function heatmapPnlValue(asset,field) { return ["recorded_value","cost_basis","mixed"].includes(asset.valuation_basis)?null:asset[field]; }
function heatmapClass(asset) { return /^BOND$/i.test(asset.asset_class || "") ? "Bond" : /ETF/i.test(asset.asset_class || "") ? "ETF" : /STOCK|EQUITY|RSU/i.test(asset.asset_class || "") ? "Stock" : "Fund"; }
function heatmapTypeIcon(asset) {
  const category=heatmapCategory(asset);
  if(!["bonds","funds"].includes(category))return "";
  const shape=category==="bonds"
    ? '<path d="M5 2h10v16l-5-3-5 3z"/><path d="M8 6h4M8 9h4"/>'
    : '<rect x="2" y="2" width="6" height="6" rx="1"/><rect x="12" y="2" width="6" height="6" rx="1"/><rect x="2" y="12" width="6" height="6" rx="1"/><rect x="12" y="12" width="6" height="6" rx="1"/>';
  return `<svg class="heatmap-type-icon" data-heatmap-type="${category}" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><title>${heatmapEsc(heatmapClass(asset))}</title>${shape}</svg>`;
}
function heatmapLabel(asset) { return [asset.symbol, asset.resolved_stock_market || (/^YAHOO$/i.test(asset.stock_market || "") ? "" : asset.stock_market), currencyDisplayLabel(asset.currency)].filter(Boolean).join(" · "); }
function heatmapAccount(id) { const row = heatmapView.data?.accounts?.find(account => account.id === id); return row ? accountLabel(row) : id; }
function heatmapFxSource(source) { return heatmapText(({external_import_market_data:"External imported market data",bank_of_israel_fx:"Bank of Israel",frankfurter_fx:"Frankfurter",financial_modeling_prep:"Financial Modeling Prep",alpha_vantage:"Alpha Vantage",yahoo_finance:"Yahoo Finance",google_finance:"Google Finance",nasdaq_quote:"Nasdaq",stooq:"Stooq"})[source] || source); }
function heatmapCategories() { return heatmapView.categories || { stocks:true,bonds:true,funds:true }; }
function heatmapCategory(asset) { const value=String(asset.asset_class || "").toUpperCase();return ["EQUITY","STOCK","RSU"].includes(value)?"stocks":value==="BOND"?"bonds":["ETF","MUTUALFUND","MUTUAL_FUND"].includes(value)?"funds":""; }
function heatmapScope(accountId = heatmapView.account_id) {
  const allowed=new Set((heatmapView.data?.accounts || []).filter(row=>row.type==="Investment").map(row=>row.id));
  if(accountId&&!allowed.has(accountId))return [];
  const categories=heatmapCategories();
  if(accountId && Array.isArray(heatmapView.data?.account_assets?.[accountId]))return heatmapView.data.account_assets[accountId].filter(asset=>categories[heatmapCategory(asset)]);
  return (heatmapView.data?.assets || []).filter(asset=>categories[heatmapCategory(asset)]).map(asset => {
    const accounts = (asset.accounts || []).filter(row => allowed.has(row.account_id) && (!accountId || row.account_id === accountId));
    if (!accounts.length) return null;
    const bases=[...new Set(accounts.map(row=>row.valuation_basis).filter(Boolean))],statuses=accounts.map(row=>row.valuation_status).filter(Boolean);
    const scopedValuation=accountId?{valuation_basis:bases.length===1?bases[0]:bases.length>1?"mixed":asset.valuation_basis,valuation_status:["unavailable","estimated","stale","current"].find(status=>statuses.includes(status)) || asset.valuation_status}:{};
    return {...asset, ...scopedValuation, accounts, quantity:heatmapSum(accounts.map(row => row.quantity)), gross_quantity:heatmapSum(accounts.map(row => heatmapKnown(row.quantity)?Math.abs(row.quantity):null)), gross_value_ils:heatmapSum(accounts.map(row => row.gross_value_ils)), value_ils:heatmapSum(accounts.map(row => row.value_ils)),cost_basis_native:heatmapSum(accounts.map(row=>row.cost_basis_native)),unrealized_pnl_native:heatmapSum(accounts.map(row=>row.unrealized_pnl_native)),unrealized_pnl_ils:heatmapSum(accounts.map(row=>row.unrealized_pnl_ils))};
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
function heatmapValueFraction(asset, assets) {
  const sized=assets.filter(row=>heatmapKnown(row.gross_value_ils)&&row.gross_value_ils>0),max=Math.max(...sized.map(row=>row.gross_value_ils));
  if(!(max>0)||!heatmapKnown(asset.gross_value_ils)||asset.gross_value_ils<0)return null;
  return (asset.gross_value_ils/max)/sized.reduce((sum,row)=>sum+row.gross_value_ils/max,0)*100;
}
function heatmapWeight(asset,assets) { const value=heatmapValueFraction(asset,assets);return heatmapKnown(value)?`${fmt(value,1)}% ${heatmapText("weight")}`:heatmapText("Unavailable"); }
function heatmapButtonLabel(asset,assets) { return `${heatmapLabel(asset)}; ${heatmapText(heatmapClass(asset))}; ${heatmapText("Gross value")}: ${heatmapMoney(asset.gross_value_ils)}; ${heatmapText("Weight of known gross holdings")}: ${heatmapWeight(asset,assets)}; ${heatmapText("Price change")}: ${heatmapPercent(asset.change_percent)}; ${heatmapText("Valuation basis")}: ${heatmapText(heatmapValuationBasis(asset))}; ${heatmapText("Valuation status")}: ${heatmapText(heatmapValuationStatus(asset))}${heatmapDirection(asset)?`; ${heatmapText(heatmapDirection(asset))}`:""}`; }
function heatmapTileMap(assets, accountId="") {
  const sized=assets.filter(asset=>heatmapKnown(asset.gross_value_ils)&&asset.gross_value_ils>0);
  if(!sized.length)return "";
  const all=heatmapView.data.assets;
  return `<div class="heatmap-canvas" role="group" aria-label="${heatmapEsc("Stock Heatmap")}">${heatmapRectangles(sized).map(rect=>{
    const asset=rect.asset,index=all.findIndex(row=>row.id===asset.id),label=heatmapButtonLabel(asset,assets),direction=heatmapDirection(asset);
    return `<button type="button" class="heatmap-tile" style="left:${rect.x}%;top:${rect.y}%;width:${rect.width}%;height:${rect.height}%;background:${heatmapColor(asset.change_percent)}" data-heatmap-asset="${index}" data-heatmap-account="${esc(accountId)}" data-heatmap-label-mode="full" aria-label="${esc(label)}" aria-pressed="false"><span class="heatmap-tile-label" aria-hidden="true"><bdi class="heatmap-tile-symbol">${heatmapTypeIcon(asset)}${esc(asset.symbol)}</bdi>${heatmapKnown(asset.change_percent)?`<strong class="heatmap-tile-change"><bdi>${esc(heatmapPercent(asset.change_percent))}</bdi></strong>`:""}<small class="heatmap-tile-value"><bdi>${esc(heatmapMoney(asset.gross_value_ils))}</bdi></small>${direction?`<small class="heatmap-tile-direction">${heatmapEsc(direction)}</small>`:""}</span></button>`;
  }).join("")}</div>`;
}
function heatmapListing(asset, accountId="") {
  const index=heatmapView.data.assets.findIndex(row=>row.id===asset.id);
  return `<li><button type="button" class="heatmap-listing" data-heatmap-asset="${index}" data-heatmap-account="${esc(accountId)}" aria-pressed="false"><span><bdi>${esc(heatmapLabel(asset))}</bdi><small>${esc(asset.name || "")} · ${heatmapEsc(heatmapClass(asset))}${heatmapDirection(asset)?` · ${heatmapEsc(heatmapDirection(asset))}`:""}</small></span><span><bdi>${esc(heatmapMoney(asset.gross_value_ils))}</bdi><small><bdi>${esc(heatmapPercent(asset.change_percent))}</bdi></small></span></button></li>`;
}
function heatmapFact(label,value) { return `<div><dt>${heatmapEsc(label)}</dt><dd>${value}</dd></div>`; }
function heatmapQuantity(value) { return heatmapKnown(value)?esc(fmt(value,4)):heatmapEsc("Unavailable"); }
function heatmapNativePnl(asset) { return `<bdi>${esc(heatmapMoney(heatmapPnlValue(asset,"unrealized_pnl_native"),asset.currency))}</bdi>`; }
function heatmapPrice(asset) { return `<bdi>${esc(heatmapMoney(asset.price,asset.currency))}</bdi>${asset.price_date?` · <bdi>${esc(formatDate(asset.price_date))}</bdi>`:""}`; }
function heatmapAccountBreakdown(asset) { return `<ul class="heatmap-account-list">${asset.accounts.map(row=>`<li><bdi>${esc(heatmapAccount(row.account_id))}</bdi> · ${heatmapEsc("Quantity")}: <bdi>${heatmapQuantity(row.quantity)}</bdi> · ${heatmapEsc("Unrealized profit / loss")}: <bdi>${esc(heatmapMoney(heatmapPnlValue(row,"unrealized_pnl_native"),asset.currency))}</bdi> · ${heatmapEsc("Gross value")}: <bdi>${esc(heatmapMoney(row.gross_value_ils))}</bdi> · ${heatmapEsc("Valuation basis")}: ${heatmapEsc(heatmapValuationBasis(row))} · ${heatmapEsc("Valuation status")}: ${heatmapEsc(heatmapValuationStatus(row))}</li>`).join("")}</ul>`; }
function heatmapTooltipHtml(asset,assets=heatmapScope()) {
  return `<h3><bdi>${esc(heatmapLabel(asset))}</bdi></h3><p class="heatmap-tooltip-company">${esc(asset.name || asset.symbol)} · ${heatmapEsc(heatmapClass(asset))}${heatmapDirection(asset)?` · ${heatmapEsc(heatmapDirection(asset))}`:""}</p><dl class="heatmap-tooltip-facts">${heatmapFact("Weight of known gross holdings",`<bdi>${esc(heatmapWeight(asset,assets))}</bdi>`)}${heatmapValuationFacts(asset)}${heatmapFact("Gross value",`<bdi>${esc(heatmapMoney(asset.gross_value_ils))}</bdi>`)}${heatmapFact("Net quantity",`<bdi>${heatmapQuantity(asset.quantity)}</bdi>`)}${heatmapDirection(asset)==="Long and short exposure"?heatmapFact("Gross quantity",`<bdi>${heatmapQuantity(asset.gross_quantity)}</bdi>`):""}${heatmapFact("Latest price",heatmapPrice(asset))}${heatmapFact("Unrealized profit / loss",heatmapNativePnl(asset))}${asset.currency!=="ILS"?heatmapFact("Converted to ILS",`<bdi>${esc(heatmapMoney(heatmapPnlValue(asset,"unrealized_pnl_ils")))}</bdi>`):""}${heatmapFact("Observed price change",`<bdi>${esc(heatmapPercent(asset.change_percent))}</bdi>`)}</dl><h4>${heatmapEsc("Accounts")}</h4>${heatmapAccountBreakdown(asset)}`;
}
function renderHeatmapSelection() {
  const target=$("heatmapSelection");if(!target)return;
  const selected=heatmapView.selected;
  const assets=heatmapScope(selected?.account_id || heatmapView.account_id),asset=assets.find(row=>row.id===selected?.id);
  if(!asset){target.innerHTML="";return;}
  const issues=[...new Set(asset.issues || [])];
  const fact=(label,value)=>`<div><dt>${heatmapEsc(label)}</dt><dd>${value}</dd></div>`;
  target.innerHTML=`<h3><bdi>${esc(heatmapLabel(asset))}</bdi></h3><p>${esc(asset.name || "")} · ${heatmapEsc(heatmapClass(asset))}${heatmapDirection(asset)?` · ${heatmapEsc(heatmapDirection(asset))}`:""}</p><dl class="heatmap-facts">${fact("Unrealized profit / loss",heatmapNativePnl(asset))}${asset.currency!=="ILS"?fact("Converted to ILS",`<bdi>${esc(heatmapMoney(heatmapPnlValue(asset,"unrealized_pnl_ils")))}</bdi>`):""}${heatmapDirection(asset)==="Long and short exposure"?fact("Gross quantity",`<bdi>${heatmapQuantity(asset.gross_quantity)}</bdi>`):""}${fact("Gross value",`<bdi>${esc(heatmapMoney(asset.gross_value_ils))}</bdi>`)}${fact("Net value",`<bdi>${esc(heatmapMoney(asset.value_ils))}</bdi>`)}${heatmapValuationFacts(asset)}${fact("Weight of known gross holdings",heatmapKnown(heatmapValueFraction(asset,assets))?`<bdi>${esc(fmt(heatmapValueFraction(asset,assets),2))}%</bdi>`:heatmapEsc("Unavailable"))}${fact("Price change",`<bdi>${esc(heatmapPercent(asset.change_percent))}</bdi>`)}${fact("Latest price",`${heatmapKnown(asset.price)?`<bdi>${esc(heatmapMoney(asset.price,asset.currency))}</bdi>`:heatmapEsc("Unavailable")}${asset.price_date?` · <bdi>${esc(formatDate(asset.price_date))}</bdi>`:""}`)}${fact("Previous observation",`${heatmapKnown(asset.previous_price)?`<bdi>${esc(heatmapMoney(asset.previous_price,asset.currency))}</bdi>`:heatmapEsc("Unavailable")}${asset.previous_date?` · <bdi>${esc(formatDate(asset.previous_date))}</bdi>`:""}`)}${fact("Net quantity",heatmapKnown(asset.quantity)?`<bdi>${esc(fmt(asset.quantity,4))}</bdi>`:heatmapEsc("Unavailable"))}${fact("Saved price source",heatmapEsc(({local:"Local",cached:"Cached provider",merged:"Local and cached"})[asset.source] || "Unavailable"))}</dl>${issues.length?`<ul class="heatmap-issues">${issues.map(code=>`<li>${heatmapEsc(heatmapReason(typeof code==="string"?code:code.code))}</li>`).join("")}</ul>`:""}${heatmapAccountBreakdown(asset)}`;
  const all=heatmapView.data.assets,index=all.findIndex(row=>row.id===asset.id);
  $("heatmapContent")?.querySelectorAll?.("[data-heatmap-asset]").forEach(button=>button.setAttribute("aria-pressed",String(Number(button.dataset.heatmapAsset)===index && (button.dataset.heatmapAccount || "")===(selected.account_id || ""))));
}
function renderDashboardHeatmap() {
  return `<div class="chart-card portfolio-heatmap-card"><div class="chart-header"><h3 class="chart-title">${heatmapEsc("Portfolio stocks heatmap")}</h3><button type="button" id="heatmapReload" class="secondary heatmap-reload" aria-label="${heatmapEsc("Reload saved data")}" title="${heatmapEsc("Reload saved data")}"${heatmapView.loading?" disabled":""}>↻</button></div><div id="heatmapContent"></div></div>`;
}
function renderHeatmap() {
  const target=$("heatmapContent");if(!target){heatmapResizeObserver?.disconnect();hideHeatmapTooltip();return;}hideHeatmapTooltip();
  const v=heatmapView,d=v.data;const restoreInteraction=typeof preserveRenderedInteraction==="function"?preserveRenderedInteraction(target):()=>{};target.setAttribute?.("aria-busy",String(v.loading));if($("heatmapReload"))$("heatmapReload").disabled=v.loading;
  let html=`<div class="heatmap-controls"><label class="field"><span>${heatmapEsc("Investment account")}</span><select id="heatmapAccount"><option value="">${heatmapEsc("All investment accounts")}</option>${(d?.accounts || []).filter(row=>row.type==="Investment").map(row=>`<option value="${esc(row.id)}"${v.account_id===row.id?" selected":""}>${esc(accountLabel(row))}</option>`).join("")}</select></label><label class="field"><span>${heatmapEsc("View")}</span><select id="heatmapLayout"><option value="combined"${v.layout==="combined"?" selected":""}>${heatmapEsc("Combined holdings")}</option><option value="accounts"${v.layout==="accounts"?" selected":""}>${heatmapEsc("By account")}</option></select></label></div><fieldset class="heatmap-filters"><legend>${heatmapEsc("Asset types")}</legend>${[["stocks","Stocks"],["bonds","Bonds"],["funds","Funds"]].map(([key,label])=>`<label><input type="checkbox" id="heatmapCategory-${key}" data-heatmap-category="${key}"${heatmapCategories()[key]?" checked":""}/> <span>${heatmapTypeIcon({asset_class:key==="bonds"?"BOND":key==="funds"?"MUTUALFUND":"STOCK"})}${heatmapEsc(label)}</span></label>`).join("")}</fieldset><p class="status-line" id="heatmapStatus" role="status" aria-live="polite">${heatmapEsc(v.loading?"Loading saved securities data…":v.error?"Could not load the heatmap. Use Reload saved data to retry.":"")}</p>`;
  if(d){
    if(v.error)html+=`<p class="heatmap-notice">${heatmapEsc("Previous saved result shown; the latest reload failed.")}</p>`;
    const assets=heatmapScope(),sized=assets.filter(asset=>heatmapKnown(asset.gross_value_ils)&&asset.gross_value_ils>0),unsized=assets.filter(asset=>!heatmapKnown(asset.gross_value_ils)||asset.gross_value_ils<=0),total=heatmapSum(sized.map(asset=>asset.gross_value_ils));
    html+=`<p class="heatmap-explainer">${heatmapEsc("Area: gross ILS value · Color: latest observed price move")}</p><div class="heatmap-legend"><span class="heatmap-loss">${heatmapEsc("Fall")}</span><span class="heatmap-neutral">${heatmapEsc("No change / unavailable")}</span><span class="heatmap-gain">${heatmapEsc("Rise")}</span><small>${heatmapEsc("Colors saturate at ±3%.")}</small></div><div class="heatmap-summary"><span>${heatmapEsc("Known gross exposure")}<b><bdi>${sized.length?esc(heatmapMoney(total)):heatmapEsc("Unavailable")}</bdi></b></span><span>${heatmapEsc("Sized listings")}<b>${sized.length} ${heatmapEsc("of")} ${assets.length}</b></span><span>${heatmapEsc("Known price moves")}<b>${assets.filter(asset=>heatmapKnown(asset.change_percent)).length} ${heatmapEsc("of")} ${assets.length}</b></span>${d.as_of?`<span>${heatmapEsc("As of")}<b><bdi>${esc(formatDate(d.as_of))}</bdi></b></span>`:""}</div>`;
    if(sized.some(asset=>["stale","estimated"].includes(asset.valuation_status)))html+=`<p class="heatmap-notice">${heatmapEsc("Includes older or estimated values. Select a security to inspect its basis and dates.")}</p>`;
    if(unsized.length)html+=`<p class="heatmap-notice">${heatmapEsc("Some selected holdings have no ILS value. Weights cover known gross holdings only, excluding cash.")}</p>`;
    if(!assets.length)html+=`<p class="heatmap-empty">${heatmapEsc(Object.values(heatmapCategories()).some(Boolean)?"No holdings match the selected asset types in this account scope.":"Choose Stocks, Bonds or Funds to display holdings.")}</p>`;
    else{
      html+=`<p class="section-note">${heatmapEsc("Select a security in the map or list for prices, dates and account holdings.")}</p>`;
      if(v.layout==="accounts"){
        html+=`<p class="section-note">${heatmapEsc("Each account panel is scaled independently. Compare the ILS amounts to compare account sizes.")}</p><div class="heatmap-account-panels" data-preserve-scroll="heatmap-accounts">${(d.accounts || []).filter(row=>row.type==="Investment" && (!v.account_id||row.id===v.account_id)).map(row=>{const scoped=heatmapScope(row.id),priced=scoped.filter(item=>heatmapKnown(item.gross_value_ils)&&item.gross_value_ils>0);return `<section class="heatmap-account-panel"><h3><bdi>${esc(accountLabel(row))}</bdi></h3><p><bdi>${priced.length?esc(heatmapMoney(heatmapSum(priced.map(item=>item.gross_value_ils)))):heatmapEsc("Unavailable")}</bdi> · ${priced.length}/${scoped.length} ${heatmapEsc("valued listings")}</p>${scoped.length?heatmapTileMap(scoped,row.id):`<p class="section-note">${heatmapEsc("No positions")}</p>`}</section>`;}).join("")}</div>`;
      }else html+=heatmapTileMap(assets);
      html+=`<section id="heatmapSelection" class="heatmap-selection" aria-live="polite"></section>`;
      if(unsized.length)html+=`<details class="heatmap-unsized"><summary>${heatmapEsc("Holdings not shown on the map")} (${unsized.length})</summary><p class="section-note">${heatmapEsc("No ILS value is available; these holdings are outside the map and its known gross total.")}</p><ul class="heatmap-list">${unsized.map(asset=>heatmapListing(asset)).join("")}</ul></details>`;
      html+=`<details class="heatmap-all-list"><summary>${heatmapEsc("All listings and values")} (${assets.length})</summary><ul class="heatmap-list">${assets.map(asset=>heatmapListing(asset)).join("")}</ul></details>`;
    }
    const excluded=heatmapExcluded();html+=`<details id="heatmapMethod" class="heatmap-method"><summary>${heatmapEsc("Method and data")}</summary><p class="section-note">${heatmapEsc("Map area = gross value of the selected securities in ILS. Color = latest observed price change in the security's currency.")}</p><p class="section-note">${heatmapEsc("Cash, pensions and derivatives are outside this securities heatmap.")}</p><p class="section-note">${heatmapEsc("Weight uses known gross values for the selected accounts and asset types; cash and unvalued holdings are excluded.")}</p>`;
    if(excluded.length)html+=`<details class="heatmap-excluded"><summary>${heatmapEsc("Excluded holdings")} (${excluded.length})</summary><ul>${excluded.map(row=>`<li><bdi>${esc([row.symbol,row.stock_market,row.account_id?heatmapAccount(row.account_id):""].filter(Boolean).join(" · "))}</bdi> · ${heatmapEsc(heatmapReason(row.reason || "unsupported_asset"))}</li>`).join("")}</ul></details>`;
    if(d.fx?.length)html+=`<details class="heatmap-fx"><summary>${heatmapEsc("Saved exchange rates")}</summary><ul>${d.fx.map(row=>`<li><bdi>${esc(currencyDisplayLabel(row.currency))}</bdi> · ${heatmapEsc("ILS per unit")}: <bdi>${heatmapKnown(row.rate)?esc(fmt(row.rate,6)):heatmapEsc("Unavailable")}</bdi>${row.date?` · <bdi>${esc(formatDate(row.date))}</bdi>`:""}${row.source?` · ${heatmapEsc("Source")}: ${esc(heatmapFxSource(row.source))}`:""}${row.status&&row.status!=="ok"?` · ${heatmapEsc(heatmapReason(row.status))}`:""}</li>`).join("")}</ul></details>`;
    html+=`<p class="section-note">${heatmapEsc("Observed prices may span more than one trading session. Dates can differ between markets. Raw price changes can reflect splits or dividends; they exclude FX and are not position profit or total return.")}</p><p class="section-note">${heatmapEsc("Long and short positions are added by absolute value for rectangle sizes; they are not netted across accounts.")}</p><p class="section-note">${heatmapEsc("Recorded holdings only; no trades or external writes.")}</p><p class="section-note">${heatmapEsc("ILS profit is the native-currency unrealized profit converted at the current saved FX rate; it does not measure historical FX profit.")}</p></details>`;
  }
  target.innerHTML=html;renderHeatmapSelection();restoreInteraction();heatmapObserveLabels(target);
}
function resetHeatmap() { hideHeatmapTooltip();heatmapView={version:heatmapView.version+1,loading:false,error:false,data:null,account_id:"",layout:"combined",selected:null,categories:{stocks:true,bonds:true,funds:true}};renderHeatmap(); }
async function loadHeatmap() {
  const v=heatmapView,version=++v.version;v.loading=true;v.error=false;renderHeatmap();
  try{const data=await api("/api/portfolio/heatmap");if(version!==heatmapView.version)return;data.accounts=(data.accounts || []).filter(row=>row.type==="Investment");v.data=data;v.loading=false;if(v.account_id&&!(data.accounts || []).some(row=>row.id===v.account_id)){v.account_id="";v.selected=null;}renderHeatmap();}
  catch{if(version!==heatmapView.version)return;v.loading=false;v.error=true;renderHeatmap();}
}
document.addEventListener("change",event=>{if(event.target.id?.startsWith("heatmapCategory-")){const key=event.target.id.slice("heatmapCategory-".length);if(["stocks","bonds","funds"].includes(key)){heatmapView.categories={...heatmapCategories(),[key]:Boolean(event.target.checked)};heatmapView.selected=null;renderHeatmap();$(event.target.id)?.focus?.({preventScroll:true});}}if(event.target.id==="heatmapAccount"){heatmapView.account_id=event.target.value;heatmapView.selected=null;renderHeatmap();$("heatmapAccount")?.focus?.({preventScroll:true});}if(event.target.id==="heatmapLayout"){heatmapView.layout=event.target.value;heatmapView.selected=null;renderHeatmap();$("heatmapLayout")?.focus?.({preventScroll:true});}});
document.addEventListener("click",event=>{if(event.target.closest?.("#heatmapReload")&&!heatmapView.loading)loadHeatmap();const button=event.target.closest?.("[data-heatmap-asset]");if(button){hideHeatmapTooltip();const asset=heatmapView.data?.assets?.[Number(button.dataset.heatmapAsset)];if(asset){heatmapView.selected={id:asset.id,account_id:button.dataset.heatmapAccount || ""};renderHeatmapSelection();}}});

// Fit against measured text and rectangle dimensions; data weights never change.
let heatmapResizeObserver=null, heatmapFitFrame=null;
function heatmapFitLabel(button) {
  const label=button.querySelector?.('.heatmap-tile-label');if(!label)return;
  const width=button.clientWidth,height=button.clientHeight;
  if(!(width>0&&height>0)){button.dataset.heatmapLabelMode='none';return;}
  const modes=[['full',['symbol','change','value','direction']],['compact',['symbol','change']],['symbol',['symbol']],['compact-wrap',['symbol','change']],['symbol-wrap',['symbol']]];
  for(const [mode,parts] of modes){
    button.dataset.heatmapLabelMode=mode;
    for(let size=16;size>=9;size--){
      button.style.setProperty('--heatmap-font',`${size}px`);
      const lines=parts.map(part=>button.querySelector(`.heatmap-tile-${part}`)).filter(Boolean);
      if(label.scrollHeight<=height && label.scrollWidth<=width && lines.every(line=>{const text=line.querySelector?.('bdi') || line;return text.scrollWidth<=text.clientWidth+0.5;}))return;
    }
  }
  button.dataset.heatmapLabelMode='none';
}
function heatmapScheduleFit(){
  if(typeof requestAnimationFrame!=='function')return;
  if(heatmapFitFrame!==null)cancelAnimationFrame(heatmapFitFrame);
  heatmapFitFrame=requestAnimationFrame(()=>{heatmapFitFrame=null;const target=$('heatmapContent');target?.querySelectorAll?.('.heatmap-tile').forEach(heatmapFitLabel);if(heatmapTooltipTrigger?.isConnected)positionHeatmapTooltip();else hideHeatmapTooltip();});
}
function heatmapObserveLabels(target){
  if(typeof ResizeObserver==='function'){
    if(!heatmapResizeObserver)heatmapResizeObserver=new ResizeObserver(heatmapScheduleFit);
    heatmapResizeObserver.disconnect();target.querySelectorAll?.('.heatmap-canvas').forEach(node=>heatmapResizeObserver.observe(node));
  }
  heatmapScheduleFit();
  if(document.fonts?.ready)document.fonts.ready.then(heatmapScheduleFit);
}

// A body-level tooltip remains visible outside the canvas/card overflow boundary.
let heatmapTooltipNode=null,heatmapTooltipTrigger=null,heatmapTooltipTimer=null,heatmapTooltipHovered=false,heatmapInputMode='keyboard';
function hideHeatmapTooltip(){
  if(heatmapTooltipTimer!==null){clearTimeout(heatmapTooltipTimer);heatmapTooltipTimer=null;}
  heatmapTooltipTrigger?.removeAttribute?.('aria-describedby');heatmapTooltipTrigger=null;heatmapTooltipHovered=false;
  if(heatmapTooltipNode){heatmapTooltipNode.hidden=true;heatmapTooltipNode.innerHTML='';}
}
function deferHideHeatmapTooltip(){
  if(heatmapTooltipTimer!==null)clearTimeout(heatmapTooltipTimer);
  heatmapTooltipTimer=setTimeout(hideHeatmapTooltip,150);
}
function positionHeatmapTooltip(){
  const node=heatmapTooltipNode,trigger=heatmapTooltipTrigger;if(!node||node.hidden||!trigger?.isConnected)return;
  const rect=trigger.getBoundingClientRect(),popup=node.getBoundingClientRect(),vw=window.innerWidth,vh=window.innerHeight,gap=8;
  const preferredX=state.language==='he'?rect.right-popup.width:rect.left;
  const x=Math.max(gap,Math.min(preferredX,vw-popup.width-gap));
  const below=rect.bottom+gap,y=Math.max(gap,Math.min(below+popup.height<=vh-gap?below:rect.top-popup.height-gap,vh-popup.height-gap));
  node.style.left=`${x}px`;node.style.top=`${y}px`;
}
function showHeatmapTooltip(button){
  if(!button)return;
  const original=heatmapView.data?.assets?.[Number(button.dataset.heatmapAsset)];
  const assets=heatmapScope(button.dataset.heatmapAccount || heatmapView.account_id),asset=original&&assets.find(row=>row.id===original.id);if(!asset)return;
  hideHeatmapTooltip();
  if(!heatmapTooltipNode){
    const node=document.createElement('div');node.id='heatmapTooltip';node.className='heatmap-tooltip';node.setAttribute('role','tooltip');node.hidden=true;document.body.appendChild(node);heatmapTooltipNode=node;
    node.addEventListener('pointerenter',()=>{heatmapTooltipHovered=true;if(heatmapTooltipTimer!==null){clearTimeout(heatmapTooltipTimer);heatmapTooltipTimer=null;}});
    node.addEventListener('pointerleave',()=>{heatmapTooltipHovered=false;deferHideHeatmapTooltip();});
  }
  heatmapTooltipTrigger=button;heatmapTooltipNode.dir=state.language==='he'?'rtl':'ltr';heatmapTooltipNode.innerHTML=heatmapTooltipHtml(asset,assets);heatmapTooltipNode.hidden=false;button.setAttribute('aria-describedby','heatmapTooltip');positionHeatmapTooltip();
}
document.addEventListener('pointerdown',event=>{heatmapInputMode=event.pointerType==='touch'?'touch':'mouse';});
document.addEventListener('pointerover',event=>{const button=event.target.closest?.('.heatmap-tile');if(!button||event.pointerType==='touch'||button.contains?.(event.relatedTarget))return;heatmapInputMode='mouse';showHeatmapTooltip(button);});
document.addEventListener('pointerout',event=>{const button=event.target.closest?.('.heatmap-tile');if(!button||button.contains?.(event.relatedTarget))return;if(heatmapTooltipNode?.contains?.(event.relatedTarget))return;deferHideHeatmapTooltip();});
document.addEventListener('focusin',event=>{if(heatmapInputMode!=='touch')showHeatmapTooltip(event.target.closest?.('.heatmap-tile'));});
document.addEventListener('focusout',event=>{if(event.target===heatmapTooltipTrigger&&!heatmapTooltipHovered)hideHeatmapTooltip();});
document.addEventListener('keydown',event=>{heatmapInputMode='keyboard';if(event.key==='Escape'&&heatmapTooltipNode&&!heatmapTooltipNode.hidden){hideHeatmapTooltip();event.preventDefault();event.stopImmediatePropagation();}});
document.addEventListener('scroll',event=>{if(heatmapTooltipNode?.contains?.(event.target))return;hideHeatmapTooltip();},true);
if(typeof window!=='undefined'&&window.addEventListener)window.addEventListener('resize',()=>{heatmapScheduleFit();positionHeatmapTooltip();});
