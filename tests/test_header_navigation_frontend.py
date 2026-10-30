"""Behavioral regressions for header navigation and Settings password handoff."""
from pathlib import Path
import re
import subprocess


SOURCE = (Path(__file__).resolve().parents[1] / 'web/app.js').read_text()


def functions(*names):
    result = []
    for name in names:
        start = re.search(rf'^function {name}\(', SOURCE, re.M).start()
        end = re.search(r'^}', SOURCE[start:], re.M).end()
        result.append(SOURCE[start:start + end])
    return '\n'.join(result)


def run_js(source):
    result = subprocess.run(['node'], input=source, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_navigation_rebuild_preserves_external_alarm_count_and_role_permissions():
    run_js(functions('ensureHierarchicalNav') + '''
const assert = require('node:assert/strict');
let admin = false;
const canAdmin = () => admin;
const launcher = {contains: () => false};
const nav = {innerHTML: '', querySelector: selector => selector === '.assistant-launcher' ? launcher : null,
  append(node) { assert.equal(node, launcher); this.launcher = node; }};
const nodes = {alarmsCount: {textContent: '28'}};
const $ = id => nodes[id];
const document = {querySelector: () => nav};
const t = value => value;
const esc = value => String(value);
const navMenuSummary = (_icon, label) => `<summary>${label}</summary>`;
const NAV_MENU_ICONS = {reports: ''};
for (const role of ['Viewer', 'Operator', 'Admin']) {
  admin = role === 'Admin';
  ensureHierarchicalNav();
  assert.equal(nav.launcher, launcher, 'menu rebuild must retain the chat controls and their listeners');
  assert.equal(nodes.alarmsCount.textContent, '28');
  assert.ok(!nav.innerHTML.includes('id="alarmsCount"'));
  assert.ok(!nav.innerHTML.includes('data-modal="alarmsModal"'));
  assert.ok(nav.innerHTML.includes('data-modal="settingsModal"'));
  assert.equal(nav.innerHTML.includes('data-modal="usersModal"'), admin);
}
nodes.alarmsCount.textContent = '0';
ensureHierarchicalNav();
assert.equal(nodes.alarmsCount.textContent, '0');
''')


def test_password_overlay_owns_keyboard_before_settings_and_restores_focus():
    start = SOURCE.index('document.addEventListener("keydown", (event) => {')
    end = SOURCE.index('\ndocument.addEventListener("click",', start)
    listener = SOURCE[start:end]
    run_js('''
const assert = require('node:assert/strict');
let keydown;
let passwordChangeReturnFocus = null;
const state = {auth: {forcedPasswordChange: false}};
let user = {role: 'Viewer', must_change_password: false};
const currentUser = () => user;
const optionLabel = value => value;
let locked = false;
const setAppAuthenticationLock = value => { locked = value; };
const requestAnimationFrame = fn => fn();
const node = () => ({hidden: false, value: 'secret', isConnected: true,
  getClientRects: () => [1], focus() { document.activeElement = this; }});
const nodes = Object.fromEntries(['authOverlay','loginForm','passwordChangeForm',
  'cancelPasswordChange','passwordChangeDescription','currentPassword','newPassword',
  'confirmPassword','passwordChangeStatus'].map(id => [id, node()]));
const $ = id => nodes[id];
const button = node();
const document = {activeElement: button, addEventListener(_event, callback) { keydown = callback; },
  querySelectorAll() { throw Error('Underlying Settings must not handle password keys'); }};
const controls = [nodes.currentPassword, nodes.newPassword, nodes.confirmPassword, nodes.cancelPasswordChange];
nodes.authOverlay.querySelectorAll = () => controls.filter(control => !control.hidden);
''' + functions('showPasswordChange', 'hideAuthOverlay') + listener + '''
const event = (key, shiftKey = false) => ({key, shiftKey, target: document.activeElement,
  preventDefault() { this.prevented = true; }});
showPasswordChange();
assert.ok(locked);
assert.equal(document.activeElement, nodes.currentPassword);
assert.equal(nodes.cancelPasswordChange.hidden, false);
assert.equal(nodes.newPassword.value, '');
keydown(event('Tab', true));
assert.equal(document.activeElement, nodes.cancelPasswordChange);
keydown(event('Tab'));
assert.equal(document.activeElement, nodes.currentPassword);
keydown(event('Escape'));
assert.equal(nodes.authOverlay.hidden, true);
assert.equal(locked, false);
assert.equal(document.activeElement, button);
user.must_change_password = true;
showPasswordChange();
assert.equal(nodes.cancelPasswordChange.hidden, true);
keydown(event('Escape'));
assert.equal(nodes.authOverlay.hidden, false);
assert.ok(locked);
''')
