"""Exercise remembered username behavior with browser storage available or blocked."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_remembered_username_and_successful_login():
    source = (ROOT / 'web/app.js').read_text()
    start = source.index('const REMEMBER_USERNAME_KEY =')
    end = source.index('\nasync function submitPasswordChange', start)
    script = source[start:end] + r'''
const assert = require('node:assert/strict');
const nodes = {loginUsername: {value: ''}, loginPassword: {value: 'test-password'}, loginRemember: {checked: false}, loginButton: {}, loginStatus: {}};
const $ = id => nodes[id];
const storage = new Map();
const localStorage = {getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)};
const optionLabel = x => x;
let request, started = 0;
const fetch = async (url, options) => {request = JSON.parse(options.body); return {};};
let fail = false;
const authResponse = async () => {if (fail) throw Error('Invalid credentials'); return {user: {username: 'Alice'}};};
const setAuthenticatedSession = () => {};
const hideAuthOverlay = () => {};
const startAuthenticatedApp = async () => {started++;};
(async () => {
restoreRememberedUsername();
assert.equal(nodes.loginRemember.checked, false);
saveRememberedUsername('Alice', true);
restoreRememberedUsername();
assert.equal(nodes.loginUsername.value, 'Alice');
assert.equal(nodes.loginRemember.checked, true);
await signIn();
assert.deepEqual(request, {username: 'Alice', password: 'test-password', remember_me: true});
assert.equal(nodes.loginPassword.value, '');
assert.equal(started, 1);
assert.deepEqual([...storage.values()], ['Alice']);
fail = true;
nodes.loginUsername.value = 'Bob';
await assert.rejects(signIn());
assert.equal(storage.get(REMEMBER_USERNAME_KEY), 'Alice');
assert.equal(nodes.loginButton.disabled, false);
saveRememberedUsername('', false);
assert.equal(storage.size, 0);
localStorage.getItem = () => {throw Error('blocked');};
localStorage.setItem = () => {throw Error('blocked');};
restoreRememberedUsername();
saveRememberedUsername('Alice', true);
})().catch(error => {console.error(error); process.exit(1);});
'''
    subprocess.run(['node', '-e', script], check=True, cwd=ROOT)
