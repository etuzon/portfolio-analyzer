"""Behavioral coverage for temporary signal dismissal and its duration setting."""
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "web/app.js").read_text()


def functions(*names):
    result = []
    for name in names:
        start = re.search(rf"^(?:async )?function {name}\(", SOURCE, re.M).start()
        end = re.search(r"^}", SOURCE[start:], re.M).end()
        result.append(SOURCE[start:start + end])
    return "\n".join(result)


def run_js(code):
    script = "const window = {};\n" + (ROOT / "web/i18n.js").read_text()
    script += SOURCE[SOURCE.index("const TRANSLATIONS ="):SOURCE.index("function locale(")]
    script += functions("t") + code
    result = subprocess.run(["node"], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_dismissal_is_cross_rule_type_specific_retryable_and_resists_stale_responses():
    run_js(functions("renderAlerts", "alertRunIsActive", "loadAlerts", "dismissAlertSignal") + r"""
const assert = require('node:assert/strict');
const state = {language: 'he', alertConditions: [1]};
let writer = true;
const canWrite = () => writer;
const nodes = {};
const $ = id => nodes[id] ||= {focus() { document.activeElement = this; }};
const esc = value => String(value ?? '');
const fmt = value => String(value);
const formatDateTime = () => '29/12/2026, 21:47';
const renderAlertConditions = () => {};
const scheduleAlertRefresh = () => {};
const requestAnimationFrame = callback => callback();
const buttons = ['buy', 'buy', 'sell', 'watch'].map(signal => ({disabled: false,
  dataset: {dismissAlertSignal: signal === 'watch' ? 'NREF' : 'NEWT', dismissAlertType: signal}}));
const document = {activeElement: buttons[0], querySelectorAll: () => buttons};
const initial = {rules: [], runs: [], active_signals: [
  {symbol: 'NEWT', signal: 'buy', rule_name: 'one'},
  {symbol: 'NEWT', signal: 'buy', rule_name: 'two'},
  {symbol: 'NEWT', signal: 'sell'}, {symbol: 'NREF', signal: 'watch'},
]};
let finishRead, finishDismiss;
let requests = [];
let fail = false;
const api = (path, options = {}) => {
  requests.push({path, options});
  if (path === '/api/alerts') return new Promise(resolve => { finishRead = resolve; });
  assert.equal(path, '/api/alerts/dismiss');
  assert.equal(options.method, 'POST');
  if (fail) return Promise.reject(new Error('private backend error must stay hidden'));
  return new Promise(resolve => { finishDismiss = resolve; });
};
(async () => {
  renderAlerts(initial);
  assert.equal(nodes.alertActiveSummary.textContent, '4');
  assert.equal((nodes.alertsSignals.innerHTML.match(/data-dismiss-alert-signal=/gu) || []).length, 4);
  assert.ok(nodes.alertsSignals.innerHTML.includes('למשך 60 ימים'));
  renderAlerts({...initial, dismissal_days: 90});
  assert.ok(nodes.alertsSignals.innerHTML.includes('למשך 90 ימים'));
  const staleRead = loadAlerts();
  const pending = dismissAlertSignal('newt', 'buy', buttons[0]);
  await dismissAlertSignal('NEWT', 'buy', buttons[1]);
  assert.equal(requests.filter(request => request.path === '/api/alerts/dismiss').length, 1, 'prevent duplicate cross-rule clicks');
  assert.deepEqual(JSON.parse(requests.at(-1).options.body), {symbol: 'NEWT', signal: 'buy'});
  assert.ok(buttons[0].disabled && buttons[1].disabled);
  assert.equal(buttons[2].disabled, false, 'other signal types stay usable');
  renderAlerts(initial); // An in-progress polling render must keep both dismiss buttons disabled.
  assert.equal((nodes.alertsSignals.innerHTML.match(/ disabled/gu) || []).length, 2);
  finishDismiss({dismissed: true, days: 60, expires_at: new Date(Date.now() + 60 * 86400000).toISOString(),
    state: {...initial, dismissal_days: 60, active_signals: initial.active_signals.slice(2)}});
  await pending;
  assert.equal(nodes.alertActiveSummary.textContent, '2');
  assert.ok(nodes.alertSignalStatus.textContent.includes('האיתות של NEWT הוסר עד 29/12/2026'));
  assert.equal(document.activeElement, nodes.alertSignalStatus);
  finishRead(initial);
  await staleRead;
  assert.equal(nodes.alertActiveSummary.textContent, '2', 'late GET must not resurrect dismissed signals');
  renderAlerts(initial);
  assert.equal(nodes.alertActiveSummary.textContent, '2', 'late concurrent POST snapshots are suppressed too');
  assert.ok(nodes.alertsSignals.innerHTML.includes('data-dismiss-alert-type="sell"'));
  fail = true;
  await dismissAlertSignal('NREF', 'watch', buttons[3]);
  assert.ok(nodes.alertSignalStatus.textContent.includes('לא ניתן להסיר'));
  assert.ok(!nodes.alertSignalStatus.textContent.includes('private'));
  assert.ok(nodes.alertsSignals.innerHTML.includes('data-dismiss-alert-signal="NREF"'));
  assert.equal(state.alertDismissPending.length, 0);
  document.activeElement = buttons[3];
  const interrupted = dismissAlertSignal('NREF', 'watch', buttons[3]);
  const anotherScreenControl = {};
  document.activeElement = anotherScreenControl;
  await interrupted;
  assert.equal(document.activeElement, anotherScreenControl, 'completion must not steal focus after the user moves on');
  writer = false;
  const count = requests.length;
  await dismissAlertSignal('NEWT', 'sell', buttons[2]);
  assert.equal(requests.length, count, 'Viewer cannot mutate dismissals');
  state.language = 'en';
  renderAlerts(initial);
  assert.equal(nodes.alertSignalStatus.textContent, 'Could not dismiss the signal. Try again.');
  assert.ok(nodes.alertsSignals.innerHTML.includes('>Dismiss</button>'));
  state.alertClientDismissals[0].expires_at = '2000-01-01T00:00:00Z';
  renderAlerts(initial);
  assert.equal(nodes.alertActiveSummary.textContent, '4', 'expired client suppression does not outlive backend expiry');
})().catch(error => {console.error(error); process.exitCode = 1;});
""")


def test_duration_settings_load_validate_save_retry_and_respect_writer_role():
    run_js(functions("alertDismissalSettingsUi", "renderAlertDismissalSettings", "loadAlertDismissalSettings", "saveAlertDismissalSettings") + r"""
const assert = require('node:assert/strict');
const state = {language: 'he', alertData: {dismissal_days: 60}};
const nodes = {};
const $ = id => nodes[id] ||= {value: '60', setAttribute() {}, focus() { this.focused = true; }};
let writer = true;
const canWrite = () => writer;
let rendered;
const renderAlerts = data => {rendered = data; state.alertData = data;};
let failRead = false, failWrite = false, finishWrite;
const requests = [];
const api = (path, options = {}) => {
  requests.push({path, options});
  assert.equal(path, '/api/settings/alerts');
  if (!options.method) return failRead ? Promise.reject(new Error('network')) : Promise.resolve({dismissal_days: 60});
  assert.equal(options.method, 'PUT');
  if (failWrite) return Promise.reject(new Error('private backend error'));
  return new Promise(resolve => {finishWrite = resolve;});
};
(async () => {
  renderAlertDismissalSettings();
  assert.equal(nodes.saveAlertDismissalSettings.disabled, true, 'do not overwrite unknown server settings');
  failRead = true;
  await loadAlertDismissalSettings();
  assert.ok(nodes.alertDismissalSettingsStatus.textContent.includes('לא ניתן לטעון'));
  assert.equal(nodes.saveAlertDismissalSettings.disabled, true);
  failRead = false;
  await loadAlertDismissalSettings();
  assert.equal(nodes.alertDismissalDays.value, '60');
  assert.equal(nodes.saveAlertDismissalSettings.disabled, false);
  const beforeValidation = requests.length;
  for (const value of ['', '0', '-1', '1.2', '3651', 'NaN']) {
    nodes.alertDismissalDays.value = value;
    await saveAlertDismissalSettings();
    assert.ok(nodes.alertDismissalSettingsStatus.textContent.includes('בין 1 ל־3650'));
  }
  assert.equal(requests.length, beforeValidation);
  nodes.alertDismissalDays.value = '90';
  const saving = saveAlertDismissalSettings();
  await saveAlertDismissalSettings();
  assert.equal(nodes.alertDismissalDays.disabled, true);
  assert.equal(nodes.reloadAlertDismissalSettings.disabled, true);
  assert.deepEqual(JSON.parse(requests.at(-1).options.body), {dismissal_days: 90});
  finishWrite({dismissal_days: 90});
  await saving;
  assert.equal(rendered.dismissal_days, 90);
  assert.ok(nodes.alertDismissalSettingsStatus.textContent.includes('מועד הסיום המקורי'));
  assert.equal(nodes.alertDismissalDays.disabled, false);
  failWrite = true;
  nodes.alertDismissalDays.value = '120';
  await saveAlertDismissalSettings();
  assert.equal(nodes.alertDismissalDays.value, '120');
  assert.ok(nodes.alertDismissalSettingsStatus.textContent.includes('הערך שהזנתם נשמר'));
  writer = false;
  renderAlertDismissalSettings();
  assert.equal(nodes.alertDismissalDays.disabled, true);
  assert.equal(nodes.saveAlertDismissalSettings.disabled, true);
  const count = requests.length;
  await saveAlertDismissalSettings();
  assert.equal(requests.length, count);
  state.language = 'en';
  renderAlertDismissalSettings();
  assert.equal(nodes.alertDismissalSettingsStatus.textContent, 'Could not save signal settings. Your value is kept. Try again.');
})().catch(error => {console.error(error); process.exitCode = 1;});
""")


def test_dismiss_controls_and_settings_are_registered_for_existing_accessibility_and_permissions():
    html = (ROOT / "web/index.html").read_text()
    assert 'data-settings-section="signals" aria-controls="settingsPanelSignals"' in html
    assert 'id="alertSignalStatus" class="status-line" role="status" aria-live="polite" tabindex="-1"' in html
    assert 'for="alertDismissalDays"' in html
    assert 'id="alertDismissalDays" type="number" min="1" max="3650" step="1" value="60"' in html
    assert 'aria-describedby="alertDismissalDaysHelp"' in html
    controls = SOURCE.split("const WRITE_CONTROL_IDS", 1)[1].split("const WRITE_DATA_ACTIONS", 1)[0]
    actions = SOURCE.split("const WRITE_DATA_ACTIONS", 1)[1].split("function currentUser", 1)[0]
    assert '"saveAlertDismissalSettings"' in controls
    assert '"data-dismiss-alert-signal"' in actions
