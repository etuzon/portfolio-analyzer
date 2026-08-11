(() => {
  "use strict";

  const HEBREW_TEXT = Object.freeze({
    "Portfolio Analyzer": "מנהל תיק השקעות",
    "Portfolio analyzer": "מנהל תיק השקעות",
    "Portfolio": "תיק השקעות",
    "Main Menu": "תפריט ראשי",
    "Dashboard": "לוח בקרה",
    "Overview": "סקירה",
    "Reports": "דוחות",
    "Portfolio Data": "נתוני התיק",
    "Accounts": "חשבונות",
    "Brokers": "גופים מנהלים",
    "Employee Stock Options": "אופציות לעובדים",
    "Securities": "ניירות ערך",
    "Prices": "מחירים",
    "Events": "אירועים",
    "People": "אנשים",
    "Family Members": "בני משפחה",
    "Account Ownership": "שיוך חשבונות",
    "Retirement": "פרישה",
    "Pensions & Funds": "פנסיה וקופות",
    "Retirement Projections": "תחזיות פרישה",
    "Research": "מחקר",
    "Company Reports": "דוחות חברות",
    "Company Outlook": "תחזית חברה",
    "Portfolio Signals": "איתותי תיק",
    "Markets": "שווקים",
    "Market Screener": "סורק שוק",
    "Alerts": "התראות",
    "Market Banner": "סרגל שוק",
    "System": "מערכת",
    "Settings": "הגדרות",
    "About": "אודות",
    "Alarms": "התראות",
    "Preparing dashboard": "מכין את לוח הבקרה",
    "Loading portfolio": "טוען את תיק ההשקעות",
    "Reading cached analytics": "קורא ניתוחים שמורים",
    "Currency, indexes, and commodities": "מטבעות, מדדים וסחורות",
    "Manage": "ניהול",
    "Analytics": "ניתוח נתונים",
    "Portfolio visual overview": "סקירה חזותית של תיק ההשקעות",
    "Glance": "תמציתי",
    "Full": "מלא",
    "Edit": "עריכה",
    "Reset": "איפוס",
    "Refresh": "רענון",
    "Search": "חיפוש",
    "Save": "שמירה",
    "Save changes": "שמירת שינויים",
    "Cancel": "ביטול",
    "Cancel edit": "ביטול עריכה",
    "Clear form": "ניקוי הטופס",
    "Delete": "מחיקה",
    "Remove": "הסרה",
    "Add": "הוספה",
    "Back": "חזרה",
    "Continue": "המשך",
    "Done": "סיום",
    "Close": "סגירה",
    "Language": "שפה",
    "Display": "תצוגה",
    "App language": "שפת הממשק",
    "English": "English",
    "Table display": "תצוגת טבלה",
    "Table MA period": "תקופת ממוצע נע בטבלה",
    "Data": "נתונים",
    "Backup schedule": "תזמון גיבוי",
    "Save display settings": "שמירת הגדרות תצוגה",
    "Save table settings": "שמירת הגדרות טבלה",
    "Display settings saved": "הגדרות התצוגה נשמרו",
    "Settings saved": "ההגדרות נשמרו",
    "Local portfolio DB": "מסד נתונים מקומי של התיק",
    "Account": "חשבון",
    "Accounts": "חשבונות",
    "Account type": "סוג חשבון",
    "Account id": "מזהה חשבון",
    "Existing account": "חשבון קיים",
    "Existing accounts": "חשבונות קיימים",
    "New account": "חשבון חדש",
    "Create account": "יצירת חשבון",
    "Edit account": "עריכת חשבון",
    "Account setup": "הגדרת חשבון",
    "Initial cash": "יתרת מזומן התחלתית",
    "Username": "שם משתמש",
    "Broker": "גוף מנהל",
    "Country": "מדינה",
    "Location": "מיקום",
    "Currency": "מטבע",
    "Comments": "הערות",
    "Type": "סוג",
    "Name": "שם",
    "Date": "תאריך",
    "Action": "פעולה",
    "Actions": "פעולות",
    "Amount": "סכום",
    "Quantity": "כמות",
    "Units": "יחידות",
    "Unit price": "מחיר ליחידה",
    "Notes": "הערות",
    "Security": "נייר ערך",
    "Symbol": "סימול",
    "Stock Market": "בורסה",
    "Stock Market *": "בורסה *",
    "Currency *": "מטבע *",
    "Company Location *": "מדינת החברה *",
    "From date": "מתאריך",
    "To date": "עד תאריך",
    "From": "מ-",
    "To": "עד",
    "Any": "הכול",
    "Any account": "כל חשבון",
    "Any account type": "כל סוג חשבון",
    "Any asset": "כל סוג נכס",
    "Any currency": "כל מטבע",
    "Any level": "כל רמה",
    "Any location": "כל מיקום",
    "Include missing": "כולל נתונים חסרים",
    "Risk": "סיכון",
    "Value / P&L": "שווי / רווח והפסד",
    "Data Status": "מצב הנתונים",
    "Not available": "לא זמין",
    "Not applicable": "לא רלוונטי",
    "Not run": "טרם הופעל",
    "No comments": "ללא הערות",
    "No data": "אין נתונים",
    "Loading…": "טוען…",
    "Saving…": "שומר…",
    "Error": "שגיאה",
    "Active": "פעיל",
    "Inactive": "לא פעיל",
    "Enabled": "מופעל",
    "Disabled": "מושבת",
    "Yes": "כן",
    "No": "לא",
  });

  const HEBREW_PATTERNS = Object.freeze([
    [/^Error:\s*(.+)$/u, (_match, detail) => `שגיאה: ${detail}`],
    [/^Editing\s+(.+)$/u, (_match, detail) => `בעריכה: ${detail}`],
    [/^Deleting\s+(.+)…$/u, (_match, detail) => `מוחק את ${detail}…`],
    [/^Loading\s+(.+)…$/u, (_match, detail) => `טוען ${detail}…`],
    [/^Saved\s+(.+)$/u, (_match, detail) => `נשמר: ${detail}`],
  ]);

  const TRANSLATABLE_ATTRIBUTES = ["placeholder", "aria-label", "title", "alt"];
  const originalText = new WeakMap();
  const lastRenderedText = new WeakMap();
  const originalAttributes = new WeakMap();
  let currentLanguage = "he";
  let observer = null;

  function normalized(value) {
    return String(value || "").trim().replace(/\s+/gu, " ");
  }

  function translatedText(value, language = currentLanguage) {
    const source = String(value || "");
    if (language !== "he") return source;
    const key = normalized(source);
    if (!key) return source;
    const exact = HEBREW_TEXT[key];
    if (exact) return source.replace(key, exact);
    for (const [pattern, formatter] of HEBREW_PATTERNS) {
      const match = key.match(pattern);
      if (match) return source.replace(key, formatter(...match));
    }
    return source;
  }

  function translateTextNode(node, language) {
    const parent = node.parentElement;
    if (!parent || parent.closest("script, style, [data-i18n-skip]")) return;
    const previousRendered = lastRenderedText.get(node);
    if (!originalText.has(node) || (previousRendered !== undefined && node.data !== previousRendered)) {
      originalText.set(node, node.data);
    }
    const source = originalText.get(node) ?? node.data;
    const next = language === "he" ? translatedText(source, language) : source;
    if (node.data !== next) node.data = next;
    lastRenderedText.set(node, next);
  }

  function translateAttributes(element, language) {
    if (!(element instanceof Element) || element.closest("[data-i18n-skip]")) return;
    let originals = originalAttributes.get(element);
    if (!originals) {
      originals = {};
      originalAttributes.set(element, originals);
    }
    for (const name of TRANSLATABLE_ATTRIBUTES) {
      if (!element.hasAttribute(name)) continue;
      const current = element.getAttribute(name) || "";
      const lastKey = `last:${name}`;
      if (!(name in originals) || (originals[lastKey] !== undefined && current !== originals[lastKey])) {
        originals[name] = current;
      }
      const source = originals[name] || "";
      const next = language === "he" ? translatedText(source, language) : source;
      if (current !== next) element.setAttribute(name, next);
      originals[lastKey] = next;
    }
  }

  function translateTree(root, language = currentLanguage) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) {
      translateTextNode(root, language);
      return;
    }
    if (!(root instanceof Element || root instanceof Document || root instanceof DocumentFragment)) return;
    if (root instanceof Element) translateAttributes(root, language);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      if (node.nodeType === Node.TEXT_NODE) translateTextNode(node, language);
      else translateAttributes(node, language);
      node = walker.nextNode();
    }
  }

  function applyFieldDirection(root = document) {
    root.querySelectorAll?.('input:not([type="number"]):not([type="date"]):not([type="file"]), textarea').forEach((field) => {
      field.setAttribute("dir", "auto");
    });
    root.querySelectorAll?.('input[type="number"], .date-field, [id*="Symbol"], [id*="Currency"], [id*="Price"], [id*="Amount"], [id*="Quantity"], [id*="Percent"], [id*="Factor"], [id*="Age"]').forEach((field) => {
      field.setAttribute("dir", "ltr");
    });
  }

  function applyToDocument(language = currentLanguage) {
    currentLanguage = language === "en" ? "en" : "he";
    document.documentElement.lang = currentLanguage === "he" ? "he" : "en";
    document.documentElement.dir = currentLanguage === "he" ? "rtl" : "ltr";
    translateTree(document, currentLanguage);
    applyFieldDirection(document);
  }

  function observe() {
    if (observer || !document.documentElement) return;
    observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === "characterData") translateTextNode(mutation.target, currentLanguage);
        if (mutation.type === "attributes") translateAttributes(mutation.target, currentLanguage);
        mutation.addedNodes.forEach((node) => {
          translateTree(node, currentLanguage);
          if (node instanceof Element) applyFieldDirection(node);
        });
      }
    });
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: TRANSLATABLE_ATTRIBUTES,
    });
  }

  window.PortfolioI18n = Object.freeze({
    applyToDocument,
    observe,
    translate: translatedText,
    translations: { he: HEBREW_TEXT },
  });
})();
