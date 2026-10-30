"""Behavioral checks for the chat UI with isolated synthetic API responses."""
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "web/app.js").read_text()


def _functions(*names):
    functions = []
    for name in names:
        start = re.search(rf"^(?:async )?function {name}\(", SOURCE, re.M).start()
        end = re.search(r"^}", SOURCE[start:], re.M).end()
        functions.append(SOURCE[start:start + end])
    return "\n".join(functions)


def _run(script):
    base = """
const assert = require('node:assert/strict');
const state = {language: 'en'};
let userId = 'user-a';
const currentUser = () => ({id: userId});
const nodes = {};
const $ = id => nodes[id] ||= {
  value: '', innerHTML: '', textContent: '', hidden: false, disabled: false,
  attributes: {}, setAttribute(name, value) { this.attributes[name] = value; },
  focus() { this.focused = true; }, setSelectionRange(a, b) { this.selection = [a, b]; }
};
const t = text => window.PortfolioI18n.translate(text, state.language);
const fmt = value => String(value);
const esc = text => String(text).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const formatDateTime = value => '30/10/2026, 12:00';
const requestAnimationFrame = fn => fn();
let opened = [];
const openModal = (...args) => opened.push(args);
const chat = (id, title = id) => ({id, title, updated_at: '2026-10-30T12:00:00Z',
  messages: [{role:'user', content: title, created_at: '2026-10-30T12:00:00Z'}, {role:'assistant', content:'Saved answer'}]});
const summary = value => ({id: value.id, title: value.title, updated_at: value.updated_at, message_count:value.messages.length});
let requests = [];
let api;
"""
    function_names = (
        "assistantUi", "assistantText", "assistantChatLabel", "assistantStatusText", "assistantToolLabel",
        "renderAssistantChat", "saveAssistantDraft", "assistantFailure", "selectAssistantChat",
        "loadAssistantChats", "newAssistantChat", "askPortfolioAssistant", "openAssistantFromLauncher",
        "loadAssistantSettings", "saveAssistantSettings",
    )
    code = "const window = {};\n" + (ROOT / "web/i18n.js").read_text() + base
    code += _functions(*function_names) + "\n(async () => {\nassistantUi();\n" + script
    code += "\n})().catch(error => {console.error(error); process.exitCode = 1;});"
    result = subprocess.run(["node"], input=code, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_launcher_carries_typing_without_sending_and_respects_ime():
    _run("""
api = () => {throw new Error('typing must not send a request');};
$('assistantLauncher').value = 'א';
openAssistantFromLauncher({isComposing:true});
assert.equal(opened.length, 0);
assert.equal($('assistantLauncher').value, 'א');
openAssistantFromLauncher({isComposing:false});
assert.equal(opened.length, 1);
assert.equal(opened[0][0], 'assistantModal');
assert.equal($('assistantPrompt').value, 'א');
assert.equal($('assistantLauncher').value, '');
assert.ok($('assistantPrompt').focused);
assert.deepEqual($('assistantPrompt').selection, [1, 1]);
assert.equal(assistantUi().drafts.new, 'א');
""")


def test_history_reopens_with_draft_and_safely_renders_localized_roles_and_tools():
    _run("""
const a = chat('a', '<img src=x onerror=alert(1)>');
api = async path => {
  requests.push(path);
  if (path === '/api/assistant/chats') return {chats:[summary(a)], max_chats:10};
  if (path === '/api/assistant/status') return {enabled:true, tools:[{name:'get_portfolio_summary', method:'GET', path:'/api/portfolio'}]};
  if (path === '/api/assistant/chats/a') return a;
  throw new Error(path);
};
$('assistantPrompt').value = 'New draft';
await loadAssistantChats();
assert.equal(assistantUi().chat.id, 'a');
assert.equal($('assistantPrompt').value, 'New draft');
assert.equal($('askAssistant').disabled, false);
assert.ok($('assistantMessages').innerHTML.includes('&lt;img'));
assert.ok(!$('assistantMessages').innerHTML.includes('<img'));
assert.ok($('assistantChatList').innerHTML.includes('aria-current="true"'));
assert.ok($('assistantReadTools').innerHTML.includes('GET /api/portfolio'));
assert.ok($('assistantMessages').innerHTML.includes('data-i18n-skip'));
state.language = 'he'; renderAssistantChat();
assert.ok($('assistantMessages').innerHTML.includes('עוזר התיק'));
assert.ok($('assistantHistoryCount').textContent.includes('שיחות שמורות'));
assert.ok($('assistantReadTools').innerHTML.includes('סיכום התיק'));
assert.equal($('askAssistant').textContent, 'שליחה');
assert.ok($('assistantMessages').innerHTML.includes('Saved answer'), 'conversation content must not be translated by the UI');
state.language = 'en'; renderAssistantChat();
assert.ok(!$('assistantHistoryCount').textContent.match(/[א-ת]/u));
""")


def test_send_failure_keeps_draft_retry_uses_same_chat_and_duplicate_send_is_blocked():
    _run("""
const ui = assistantUi(); ui.enabled = true; ui.chat = chat('a'); ui.chats = [summary(ui.chat)];
let resolveRequest, rejectRequest;
let fail = true;
api = (path, options) => {
  requests.push({path, body:JSON.parse(options.body)});
  return new Promise((resolve, reject) => {resolveRequest=resolve; rejectRequest=reject;});
};
$('assistantPrompt').value = 'Question';
const first = askPortfolioAssistant();
await askPortfolioAssistant();
assert.equal(requests.length, 1);
assert.ok(ui.sending);
assert.ok($('assistantPrompt').disabled);
assert.ok($('assistantMessages').innerHTML.includes('Question'));
rejectRequest(new Error('temporary disconnect')); await first;
assert.equal($('assistantPrompt').value, 'Question');
assert.equal(ui.chat.messages.length, 2);
assert.equal(ui.retry, 'send');
assert.ok(!ui.sending);
const retry = askPortfolioAssistant();
const updated = chat('a'); updated.messages.push({role:'user',content:'Question'}, {role:'assistant',content:'Answer'});
resolveRequest({chat:updated,chats:[summary(updated)],max_chats:10,answer:'Answer'}); await retry;
assert.equal(requests.length, 2);
assert.equal(requests[1].body.chat_id, 'a');
assert.equal(ui.chat.messages.length, 4);
assert.equal($('assistantPrompt').value, '');
assert.equal(ui.retry, '');
assert.ok(!ui.sending);
""")


def test_stale_chat_response_and_old_user_send_cannot_replace_current_user_state():
    _run("""
const ui = assistantUi(); ui.enabled = true;
const pending = {};
api = path => new Promise(resolve => { pending[path] = resolve; });
const oldSelection = selectAssistantChat('old');
const latestSelection = selectAssistantChat('latest');
pending['/api/assistant/chats/latest'](chat('latest')); await latestSelection;
pending['/api/assistant/chats/old'](chat('old')); await oldSelection;
assert.equal(ui.chat.id, 'latest');
$('assistantPrompt').value='Private question';
const sending = askPortfolioAssistant();
userId = 'user-b';
renderAssistantChat();
assert.equal($('assistantPrompt').value, '');
assert.ok(!$('assistantMessages').innerHTML.includes('Private question'));
pending['/api/assistant/questions']({chat:chat('private'),chats:[summary(chat('private'))],max_chats:10}); await sending;
assert.equal(assistantUi().owner, 'user-b');
assert.equal(assistantUi().chat, null);
assert.ok(!$('assistantMessages').innerHTML.includes('private'));
""")


def test_disconnected_assistant_keeps_history_and_guides_local_codex_setup_in_each_language():
    _run("""
const ui=assistantUi(); ui.enabled=false; ui.chat=chat('saved'); ui.chats=[summary(ui.chat)];
api=async()=>{throw new Error('disconnected assistant must not submit');};
for(const language of ['he','en']) {
  state.language=language; renderAssistantChat();
  assert.ok($('assistantMessages').innerHTML.includes('Saved answer'));
  assert.ok($('askAssistant').disabled);
  assert.ok($('assistantStatus').textContent.includes('Codex'));
  assert.ok(language==='he' ? $('assistantStatus').textContent.includes('השיחות השמורות') : $('assistantStatus').textContent.includes('Saved chats'));
}
$('assistantPrompt').value='Keep my draft'; await askPortfolioAssistant();
assert.equal($('assistantPrompt').value,'Keep my draft');
assert.equal(ui.chat.id,'saved');
""")


def test_new_chat_and_retention_settings_follow_server_result():
    _run("""
const ui = assistantUi(); ui.enabled = true; ui.chat = chat('a'); ui.chats=[summary(ui.chat)];
api = async (path, options) => {
  requests.push({path, options});
  if (path === '/api/assistant/chats') return {chat:{id:'new',messages:[]},chats:[{id:'new',message_count:0},summary(chat('a'))],max_chats:10};
  if (path === '/api/settings/assistant' && options?.method === 'PUT') return {max_chats:1,chats:[{id:'new',message_count:0}]};
  if (path === '/api/settings/assistant') return {max_chats:10};
  throw new Error(path);
};
await loadAssistantSettings(); assert.equal($('assistantMaxChats').value, 10);
await newAssistantChat();
assert.equal(ui.chat.id, 'new');
assert.equal($('assistantPrompt').value, '');
$('assistantMaxChats').value='0'; await saveAssistantSettings();
assert.ok($('assistantSettingsStatus').textContent.includes('1 to 100'));
assert.equal(requests.length, 2);
$('assistantMaxChats').value='1'; await saveAssistantSettings();
assert.equal(ui.maxChats, 1); assert.equal(ui.chats.length, 1);
assert.equal(JSON.parse(requests[2].options.body).max_chats, 1);
assert.equal(ui.chat.id, 'new');
""")


def test_chat_controls_are_labeled_and_keyboard_submission_is_composition_safe():
    html = (ROOT / "web/index.html").read_text()
    menu = html[html.index('<nav id="appNavigation"'):html.index('</nav>')]
    assert 'id="assistantLauncher"' in menu
    assert html.count('id="assistantLauncher"') == 1
    assert 'class="assistant-readonly"' not in html
    assert 'id="assistantReadOnlyNotice"' not in html
    assert 'for="assistantLauncher"' in html
    assert 'aria-haspopup="dialog" aria-controls="assistantModal"' in html
    assert 'role="log" aria-label="Chat messages"' in html
    assert 'id="assistantSettingsForm"' in html
    assert 'id="assistantMaxChats" type="number" min="1" max="100"' in html
    assert 'id="assistantPrompt"' in html and 'aria-describedby="assistantComposerHelp"' in html
    keyboard = SOURCE[SOURCE.index('$("assistantPrompt").addEventListener("keydown"'):]
    keyboard = keyboard[:keyboard.index('\n});')]
    assert '!event.shiftKey' in keyboard and '!event.isComposing' in keyboard and 'event.keyCode !== 229' in keyboard
