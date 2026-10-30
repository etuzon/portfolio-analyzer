"""Alarms must localize their own dynamic content and rerender on language changes."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_alarm_js(body):
    source = (ROOT / 'web/app.js').read_text()
    names = ('t', 'alarmText', 'alarmValue', 'alarmDueText', 'dividendAlarmMessage',
             'dividendAlarms', 'vestingAlarms', 'alarmDismissalId', 'currentAlarms',
             'renderAlarms', 'clearAlarms', 'saveVestingAlertSettings', 'applyLanguage')
    functions = []
    for name in names:
        start = re.search(rf'^function {name}\(', source, re.M).start()
        end = re.search(r'^}', source[start:], re.M).end()
        functions.append(source[start:start + end])
    setup = '''
const assert = require('node:assert/strict');
const window = {};
'''
    script = setup + (ROOT / 'web/i18n.js').read_text() + '''
const translator = window.PortfolioI18n;
window.PortfolioI18n = {...translator, applyToDocument() {}, observe() {}};
const TRANSLATIONS = {en: {}, he: {}};
const nodes = Object.fromEntries(['alarmsCount','alarmsStatus','alarmsList',
  'alarmSettingsStatus','vestingAlertDays','clearAlarms','alarmsButton'].map(id =>
  [id, {textContent: '', innerHTML: '', value: '30', classList: {toggle() {}}}]));
const $ = id => nodes[id];
const document = {documentElement: {}, querySelector: () => null, querySelectorAll: () => []};
const state = {language: 'he', baseCurrency: 'USD', localEvents: [], items: [],
  dismissedAlarmIds: [], vestingAlertDays: 30};
let lots = [];
const equityCompLots = kind => lots.filter(lot => lot.kind === kind);
const normalizedVestingAlertDays = value => Math.max(1, Math.min(365, Math.round(Number(value))));
const eventDaysFromToday = date => ({'2026-10-30': 0, '2026-10-31': 1, '2026-11-02': 3, '2026-12-31': 62}[date] ?? -60);
const formatDate = value => value.split('-').reverse().join('/');
const fmt = value => String(Number(value));
const money = (value, currency, digits) => `${currency} ${Number(value).toFixed(digits)}`;
const esc = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;');
const plain = text => text.replace(/[\\u2066-\\u2069]/gu, '');
const valueOf = id => nodes[id].value;
const VESTING_ALERT_SETTINGS_STORAGE_KEY = 'fixture.notice';
const writes = [];
const localStorage = {setItem: (...args) => writes.push(args)};
const scheduleClientStateSync = () => {};
const saveAlarmDismissals = () => {};
const noop = () => {};
const refreshLocalizedFormOptions = noop, refreshBrokerSelects = noop,
  renderBrokersList = noop, renderLocalAccountsList = noop, renderImportSkippedAccounts = noop,
  renderFundAccountOwners = noop, ensureHierarchicalNav = noop, bindNavAccordion = noop,
  renderCurrentUser = noop, renderFamilyMembers = noop, renderFamilyMemberEditor = noop,
  refreshFamilyMemberSelects = noop, refreshFamilyAccountSelects = noop,
  renderMacroScenario = noop, renderAssistantChat = noop, renderLoggingSettings = noop, renderAlertDismissalSettings = noop, refreshReportFilterOptions = noop,
  applyAutoDirection = noop, mountModalHomeLink = noop;
const paid = {id:'paid', type:'DIVIDEND', symbol:'TRIN', status:'processed',
  event_date:'2026-08-14', currency:'USD', gross_amount:2.72, tax_amount:0.68,
  net_amount:2.04, details:{gross_per_share:0.17, shares:16}};
'''
    script += '\n'.join(functions) + '\n' + body
    result = subprocess.run(['node'], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_live_language_switch_localizes_all_alarm_types_without_changing_data():
    run_alarm_js('''
state.localEvents = [paid, {...paid, id:'pending', symbol:'ONE', status:'pending', event_date:'2026-10-31'},
  {...paid, id:'later', symbol:'MANY', status:'pending', event_date:'2026-11-02'},
  {...paid, id:'today', symbol:'TODAY', status:'pending', event_date:'2026-10-30'}];
lots = [{kind:'rsu', symbol:'RSUQA', transactionId:'rsu', quantity:1, vestDate:'2026-10-30'},
  {kind:'option', symbol:'OPTIONQA', transactionId:'option', quantity:2, vestDate:'2026-10-31'}];
const original = JSON.stringify({events:state.localEvents,lots});
const identities = () => {const a=currentAlarms();return [...a.vesting,...a.dividends].map(alarmDismissalId)};
const ids = identities();
const output = [];
for (const language of ['he','en','he']) {
  state.language = language;
  applyLanguage(); // Actual entry point must rerender cards, status and notice.
  const text = plain(nodes.alarmsList.innerHTML.replace(/<[^>]*>/gu, '') + nodes.alarmsStatus.textContent + nodes.alarmSettingsStatus.textContent);
  if (language === 'he') {
    assert.ok(text.includes('הדיבידנד של TRIN שולם'));
    assert.ok(text.includes('נוספו USD 2.04 למזומן'));
    assert.ok(text.includes('מס USD 0.68'));
    assert.ok(text.includes('בעוד יום אחד') && text.includes('בעוד 3 ימים') && text.includes('היום'));
    assert.ok(text.includes('מועד הבשלה') && text.includes('אופציות לעובדים'));
    assert.ok(!/dividend|paid|Added|cash|share|vest|scheduled|Gross|Tax|Payment|notice|undefined|NaN/u.test(text));
  } else {
    assert.ok(text.includes('TRIN dividend was paid'));
    assert.ok(text.includes('in 1 day') && text.includes('in 3 days'));
    assert.ok(!/[א-ת]/u.test(text));
  }
  assert.ok(text.includes('14/08/2026'));
  assert.equal(nodes.alarmsCount.textContent,'6');
  assert.deepEqual(identities(),ids);
  assert.equal(JSON.stringify({events:state.localEvents,lots}),original);
  output.push(text);
}
assert.equal(output[0],output[2]);
''')


def test_notices_clear_empty_and_new_alarms_follow_language_and_keep_records():
    run_alarm_js('''
state.localEvents = [paid];
const original = JSON.stringify(paid);
applyLanguage();
nodes.vestingAlertDays.value = '1';
saveVestingAlertSettings();
assert.ok(nodes.alarmSettingsStatus.textContent.includes('יום אחד לפני ההבשלה'));
clearAlarms();
assert.equal(nodes.alarmsCount.textContent,'0');
assert.ok(nodes.alarmsStatus.textContent.includes('נוקתה התראה אחת'));
assert.ok(nodes.alarmsList.innerHTML.includes('אין התראות'));
const dismissed = [...state.dismissedAlarmIds];
state.language='en';applyLanguage();
assert.ok(nodes.alarmsStatus.textContent.includes('1 alarm cleared'));
assert.ok(nodes.alarmSettingsStatus.textContent.includes('1 day before vesting'));
state.language='he';applyLanguage();
assert.ok(nodes.alarmsStatus.textContent.includes('נוקתה התראה אחת'));
assert.deepEqual(state.dismissedAlarmIds,dismissed);
state.localEvents.push({...paid,id:'new',status:'pending',event_date:'2026-10-31',details:{}});
renderAlarms();
assert.equal(nodes.alarmsCount.textContent,'1');
assert.ok(nodes.alarmsList.innerHTML.includes('סכום למניה אינו זמין'));
assert.ok(nodes.alarmsList.innerHTML.includes('מספר המניות אינו זמין'));
assert.ok(!/undefined|NaN/u.test(nodes.alarmsList.innerHTML));
assert.equal(JSON.stringify(paid),original);
state.dismissedAlarmIds=[];state.localEvents=[];state.clearedAlarmCount=0;
renderAlarms();
assert.ok(nodes.alarmsStatus.textContent.includes('אין התראות'));
''')


def test_failed_update_message_follows_live_language_and_keeps_cached_alarms():
    run_alarm_js('''
state.localEvents = [paid];
state.alarmsLoadFailed = true;
for (const language of ['he','en','he']) {
  state.language = language;
  applyLanguage();
  assert.equal(nodes.alarmsCount.textContent,'1');
  assert.ok(nodes.alarmsList.innerHTML.includes('TRIN'));
  assert.ok(nodes.alarmsStatus.textContent.includes(language === 'he' ? 'לא ניתן לעדכן' : 'Could not update alarms'));
  assert.ok(language === 'he' ? !/[A-Za-z]/u.test(nodes.alarmsStatus.textContent) : !/[א-ת]/u.test(nodes.alarmsStatus.textContent));
}
state.alarmsLoadFailed = false;
renderAlarms();
assert.ok(!nodes.alarmsStatus.textContent.includes('לא ניתן לעדכן'));
assert.equal(state.localEvents[0],paid);
''')
