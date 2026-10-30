"""Security history displays localized labels and readable ledger provenance."""
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "web/app.js").read_text()


def js_functions(*names):
    result = []
    for name in names:
        start = re.search(rf"^(?:async )?function {name}\(", SOURCE, re.M).start()
        end = re.search(r"^}", SOURCE[start:], re.M).end()
        result.append(SOURCE[start:start + end])
    return "\n".join(result)


def test_security_history_localizes_actions_cash_and_generated_notes_without_audit_ids():
    script = "const window = {};\n" + (ROOT / "web/i18n.js").read_text()
    script += SOURCE[SOURCE.index("const TRANSLATIONS ="):SOURCE.index("function locale(")]
    script += js_functions("t", "securityTransactionCommentText", "renderSecurityDetail", "tradeHistoryActionLabel", "transactionCashImpact")
    script += r"""
const assert = require('node:assert/strict');
const auditId = 'cfbda34c-b7db-4e62-928a-2a02cdeef431';
const sourceKey = `dividend:${auditId}:NEWT:NASDAQ:2026-10-29:0.6300000000`;
const common = {quantity: 10, price_input: 4.7, price: 4.7, currency: 'USD', trade_date: '2026-10-29'};
const transactions = [
  {...common, id: 'one', action: 'DIVIDEND', source: 'dividend_scan', comments: `Dividend event ${sourceKey}`},
  {...common, id: 'two', action: 'ADD', source: 'portfolio_import', comments: 'Imported source BUY'},
  {...common, id: 'three', action: 'BUY', comments: 'Keep import-history; <em>my manual note</em>'},
  {...common, id: 'four', action: 'REMOVE', source: 'portfolio_import', comments: 'Imported source SELL · Preserved user note'},
  ...['SELL', 'SHORT', 'INTEREST', 'FEE'].map((action, index) => ({...common, id: `action-${index}`, action})),
];
const before = JSON.stringify(transactions);
const state = {language: 'he', securityDetail: {symbol: 'NEWT', currency: 'USD', asset_class: 'EQUITY'},
  localTransactions: transactions, localPrices: []};
const nodes = {};
const $ = id => nodes[id] ||= {};
const esc = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const fmt = value => String(value ?? 0);
const money = value => `$${value}`;
const signedMoney = value => `${value > 0 ? '+' : ''}$${value}`;
const formatDate = () => '29/10/2026';
const currencyDisplayLabel = () => '$';
const optionLabel = label => t(label);
const cleanSourceLabel = value => value;
const transactionMatchesSecurity = () => true;
const priceMatchesSecurity = () => true;
const renderSecurityTechnicalSignal = () => {};
const renderSecurityChart = () => {};
const outputs = [];
for (const language of ['he', 'en', 'he']) {
  state.language = language;
  renderSecurityDetail();
  const html = nodes.securityDetailTransactions.innerHTML;
  outputs.push(html);
  assert.ok(!html.includes(auditId));
  assert.ok(!html.includes('Dividend event'));
  assert.ok(!html.includes('Imported source'));
  assert.ok(!html.includes(sourceKey));
  assert.ok(html.includes('Keep import-history; &lt;em&gt;my manual note&lt;/em&gt;'));
  assert.ok(html.includes('Preserved user note'));
  assert.ok(html.includes('29/10/2026'));
  assert.ok(html.includes('data-edit-security="one"'), 'retain underlying edit identity');
  assert.ok(html.includes('data-delete-security="two"'), 'retain underlying delete identity');
  assert.equal(JSON.stringify(transactions), before, 'display must not rewrite raw ledger/comments');
  if (language === 'he') {
    for (const label of ['דיבידנד', 'הוספת נייר ערך', 'הסרת נייר ערך', 'קנייה', 'מכירה', 'שורט', 'ריבית', 'עמלה',
      'מחיר שהוזן', 'מזומן', 'ללא תנועת מזומן', 'דיבידנד שנרשם אוטומטית', 'פעולה מיובאת']) {
      assert.ok(html.includes(label), label);
    }
    assert.ok(!/\b(?:DIVIDEND|ADD|REMOVE|BUY|SELL|SHORT|INTEREST|FEE|Cash|input|Edit|Delete)\b/u.test(html));
  } else {
    for (const label of ['Dividend', 'Add security', 'Remove security', 'Buy', 'Sell', 'Short', 'Interest', 'Fee',
      'Entered price', 'Cash', 'No cash movement', 'Automatic dividend', 'Imported transaction']) assert.ok(html.includes(label), label);
    assert.ok(!/[א-ת]/u.test(html));
  }
}
assert.equal(outputs[0], outputs[2], 'rerender after language switch must restore localized history');
state.language = 'he';
assert.equal(securityTransactionCommentText({comments: `Dividend event ${sourceKey} · Keep my note`}), 'דיבידנד שנרשם אוטומטית · Keep my note');
assert.equal(securityTransactionCommentText({comments: 'Imported quantity -10.25'}), 'החזקה מיובאת');
assert.equal(securityTransactionCommentText({comments: 'Imported source order'}), 'פעולה מיובאת');
assert.equal(securityTransactionCommentText({comments: 'Employee stock option exercise'}), 'מימוש אופציה');
assert.equal(securityTransactionCommentText({comments: 'A manual note about Dividend event cash'}), 'A manual note about Dividend event cash');
assert.equal(securityTransactionCommentText({comments: ''}), '');
state.localTransactions = [];
renderSecurityDetail();
assert.ok(nodes.securityDetailTransactions.innerHTML.includes('אין פעולות בנייר הערך הזה'));
"""
    result = subprocess.run(["node"], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_chart_footer_counts_and_volume_states_follow_language_in_full_and_zoomed_ranges():
    script = "const window = {};\n" + (ROOT / "web/i18n.js").read_text()
    script += SOURCE[SOURCE.index("const TRANSLATIONS ="):SOURCE.index("function locale(")]
    script += js_functions("t", "renderSecurityChart")
    script += r"""
const assert = require('node:assert/strict');
const state = {language: 'he', securityChartMaWindows: [], securityChartLevelPeriods: [],
  securityChartMode: 'line', securityDetail: {currency: 'USD'}, securityHistoryMeta: {}};
const document = {querySelectorAll: () => []};
const frame = {innerHTML: ''};
const $ = () => frame;
const esc = value => String(value ?? '');
const fmt = value => String(value);
const signedMoney = value => `$${value}`;
const formatDate = value => value;
const setDateField = () => {};
const clampedHistoryDate = value => value;
const renderSecurityChartZoomControls = () => {};
const attachSecurityChartHover = () => {};
const attachSecurityChartZoom = () => {};
const supportResistanceChartLevels = () => [];
const levelPeriodLabel = value => value;
let points = Array.from({length: 100}, (_, index) => ({date: '29/10/2026', price: 10 + index,
  open: 10 + index, high: 12 + index, low: 9 + index, close: 11 + index, volume: 0}));
let zoomed = false;
const securityChartPoints = () => points;
const securityChartZoomWindow = count => ({start: zoomed ? 20 : 0, end: zoomed ? 49 : count - 1, isFull: !zoomed});
const footer = () => frame.innerHTML.split('<div class="security-chart-footer">')[1];
for (const language of ['he', 'en', 'he']) {
  state.language = language;
  zoomed = false;
  renderSecurityChart();
  if (language === 'he') {
    assert.ok(footer().includes('100 נקודות מחיר · אין נתוני מחזור מהספק לתקופה זו'));
    assert.ok(footer().includes('שער סגירה מתואם'));
    assert.ok(!/[A-Za-z]/u.test(footer().replace(/<[^>]*>/gu, '')));
  } else {
    assert.ok(footer().includes('100 price points · No volume data from provider for this period'));
    assert.ok(!/[א-ת]/u.test(footer()));
  }
  zoomed = true;
  renderSecurityChart();
  assert.ok(footer().includes(language === 'he' ? '30 מתוך 100 נקודות מחיר' : '30 of 100 price points'));
}
state.language = 'he';
zoomed = false;
points = points.map(point => ({...point, volume: 1234}));
state.securityHistoryMeta.volume = {latest: 9876, average_20d: 5432};
renderSecurityChart();
assert.ok(footer().includes('מחזור 9876 · ממוצע 20 ימים 5432 · ממוצע 90 ימים לא זמין'));
assert.ok(footer().includes('מחזור בעלייה'));
assert.ok(footer().includes('מחזור בירידה'));
assert.ok(!/[A-Za-z]/u.test(footer().replace(/<[^>]*>/gu, '')));
state.language = 'en';
renderSecurityChart();
assert.ok(footer().includes('Volume 9876 · Avg 20D 5432 · Avg 90D N/A'));
assert.ok(!/[א-ת]/u.test(footer()));
points = [];
state.language = 'he';
renderSecurityChart();
assert.ok(frame.innerHTML.includes('אין היסטוריית מחירים לתקופה הזו'));
"""
    result = subprocess.run(["node"], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
