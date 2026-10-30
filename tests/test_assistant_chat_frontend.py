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
let profile = {first_name:'Test', last_name:'Owner', username:'test-owner', role:'Admin'};
const currentUser = () => ({id: userId, ...profile});
const canAdmin = () => currentUser().role === 'Admin';
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
        "assistantUi", "assistantText", "assistantChatLabel", "assistantUserName", "assistantReferenceId",
        "assistantAnswerText", "assistantMessageText", "assistantMessageMetadata", "assistantStatusText", "assistantToolLabel",
        "renderAssistantChat", "saveAssistantDraft", "assistantFailure", "setAssistantFailure", "selectAssistantChat",
        "loadAssistantChats", "newAssistantChat", "askPortfolioAssistant", "openAssistantFromLauncher",
        "loadAssistantSettings", "saveAssistantSettings", "loggingSettingsUi", "renderLoggingSettings", "loadLoggingSettings", "saveLoggingSettings",
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


def test_chat_authors_use_current_full_name_and_escape_profile_data():
    _run("""
const ui=assistantUi(); ui.chat=chat('saved');
profile.first_name='<img src=x>'; profile.last_name='Owner & Co';
renderAssistantChat();
assert.ok($('assistantMessages').innerHTML.includes('&lt;img src=x&gt; Owner &amp; Co'));
assert.ok(!$('assistantMessages').innerHTML.includes('<img'));
assert.ok(!$('assistantMessages').innerHTML.includes('>You</b>'));
profile.first_name='נועה'; profile.last_name='כהן'; state.language='he'; renderAssistantChat();
assert.ok($('assistantMessages').innerHTML.includes('נועה כהן'));
assert.ok(!$('assistantMessages').innerHTML.includes('>אתם</b>'));
profile.first_name='';profile.last_name='';
assert.equal(assistantUserName(),'test-owner');
""")


def test_saved_source_footers_are_hidden_without_removing_financial_facts_or_user_text():
    _run(r"""
const content='Revenue grew 12% on 31/12/2025.\n- Profit was $500.\n**Sources:** GET /api/portfolio\n- **Source:** annual report\nמקור: נתוני יישום\n* מקורות: נתונים\n- `GET /api/local/reports`\n- **GET** /api/security/history\nGET /api/portfolio?symbol=ABC\nRevenue source: services.\nThe source of income remains unchanged.';
const clean=assistantAnswerText(content);
assert.ok(clean.includes('Revenue grew 12% on 31/12/2025.'));
assert.ok(clean.includes('- Profit was $500.'));
assert.ok(clean.includes('Revenue source: services.'));
assert.ok(clean.includes('The source of income remains unchanged.'));
assert.ok(!clean.includes('/api/')&&!clean.includes('Sources:')&&!clean.includes('מקורות:'));
assert.equal(assistantMessageText({role:'user',content:'Source: explain this field'}),'Source: explain this field');
const ui=assistantUi();ui.chat={id:'old',title:'Old',messages:[{role:'assistant',content}]};renderAssistantChat();
assert.ok(!$('assistantMessages').innerHTML.includes('/api/'));
assert.ok($('assistantMessages').innerHTML.includes('31/12/2025'));
assert.equal(ui.chat.messages[0].content,content,'history cleaning must not mutate saved records');
""")


def test_unsupported_history_and_failed_request_references_follow_ui_language_and_keep_draft():
    _run("""
const reference='123e4567-e89b-42d3-a456-426614174000';
const ui=assistantUi();ui.enabled=true;
ui.chat={id:'unsupported',title:'Question',messages:[{role:'assistant',content:'Old English unsupported response. Reference: '+reference,support_status:'unsupported',request_id:reference}]};
for(const language of ['he','en','he']) {
  state.language=language;renderAssistantChat();
  const html=$('assistantMessages').innerHTML;
  assert.ok(html.includes(reference));
  assert.ok(!html.includes('Old English'));
  assert.ok(language==='he'?html.includes('מזהה פנייה:'):html.includes('Reference:'));
  assert.ok(language==='he'?html.includes('בקשה שאינה נתמכת'):html.includes('Unsupported request'));
}
api=async()=>{const error=new Error('Wrong-language server summary');error.code='assistant_failed';error.requestId=reference;throw error;};
$('assistantPrompt').value='Keep this draft';await askPortfolioAssistant();
assert.equal($('assistantPrompt').value,'Keep this draft');
assert.equal(ui.requestId,reference);
for(const language of ['en','he']){
 state.language=language;renderAssistantChat();
 assert.ok($('assistantStatus').textContent.includes(reference));
 assert.ok(language==='he'?$('assistantStatus').textContent.includes('מזהה פנייה:'):$('assistantStatus').textContent.includes('Reference:'));
 assert.ok(!$('assistantStatus').textContent.includes('Wrong-language'));
}
assert.equal(assistantReferenceId('<img>'),'');
""")


def test_logging_settings_are_global_admin_only_bounded_and_preserve_failed_edits():
    _run("""
api=async(path,options={})=>{requests.push({path,options});if(options.method==='PUT')return JSON.parse(options.body);return {max_files:10,max_size_mb:10};};
profile.role='Viewer';await loadLoggingSettings();await saveLoggingSettings();assert.equal(requests.length,0);
profile.role='Admin';await loadLoggingSettings();assert.equal($('loggingMaxFiles').value,10);assert.equal($('loggingMaxSizeMb').value,10);
for(const [files,size] of [['0','10'],['101','10'],['10','0'],['10','1025'],['2.5','10']]){
 $('loggingMaxFiles').value=files;$('loggingMaxSizeMb').value=size;await saveLoggingSettings();
 assert.equal(requests.length,1);
 assert.ok($('loggingSettingsStatus').textContent.includes('1–100'));
}
$('loggingMaxFiles').value='100';$('loggingMaxSizeMb').value='1024';await saveLoggingSettings();
assert.equal(requests.length,2);assert.deepEqual(JSON.parse(requests[1].options.body),{max_files:100,max_size_mb:1024});
api=async()=>{throw new Error('temporary disconnect');};
$('loggingMaxFiles').value='3';$('loggingMaxSizeMb').value='20';await saveLoggingSettings();
assert.equal($('loggingMaxFiles').value,'3');assert.equal($('loggingMaxSizeMb').value,'20');
state.language='he';renderLoggingSettings();assert.ok($('loggingSettingsStatus').textContent.includes('לא ניתן לשמור'));
state.language='en';renderLoggingSettings();assert.ok(!$('loggingSettingsStatus').textContent.match(/[א-ת]/u));
""")
    html = (ROOT / "web/index.html").read_text()
    assert 'data-settings-section="logging" aria-controls="settingsPanelLogging" data-admin-only hidden' in html
    assert 'id="loggingMaxFiles" type="number" min="1" max="100"' in html
    assert 'id="loggingMaxSizeMb" type="number" min="1" max="1024"' in html
    assert 'id="loggingSettingsForm" class="management-form settings-form" novalidate' in html
    assert 'includes its active log file' in html
    assert 'compressed to ZIP' in html


def test_api_error_keeps_safe_machine_code_and_request_reference_without_headers():
    code = _functions("api") + """
const assert = require('node:assert/strict');
const state={auth:{csrfToken:''}};
const warnings=[];
const appLog=()=>{};
const appWarn=(_event,details)=>warnings.push(details);
const showLogin=()=>{};
const showPasswordChange=()=>{};
const requestId='123e4567-e89b-42d3-a456-426614174000';
const fetch=async()=>({ok:false,status:503,statusText:'Unavailable',json:async()=>({detail:{code:'assistant_unavailable',message:'העוזר אינו זמין',request_id:requestId}})});
(async()=>{
 try { await api('/api/assistant/questions',{method:'POST',headers:{Authorization:'private-credential'}});assert.fail('must reject'); }
 catch(error){
  assert.equal(error.code,'assistant_unavailable');assert.equal(error.requestId,requestId);
  assert.equal(error.message,'העוזר אינו זמין');assert.equal(error.headers,undefined);
 }
 assert.equal(warnings[0].request_id,requestId);
 assert.ok(!JSON.stringify(warnings).includes('private-credential'));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(["node"], input=code, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
