"""Independent scheduler acceptance: real app controls, isolated REST state.

Disposable Chromium loads production HTML, CSS, translations and application
scripts. API integration checks below use temporary databases/settings; neither
fixture accesses private runtime configuration or starts an AI lookup.
"""
import base64
import json

import pytest

from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium
from test_scheduling import schedule_environment


def ready(tmp_path, chromium, language="en", width=1440):
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": cash_browser_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate(r'''
qa.saved={enabled:false,timezone:'UTC',position_scope:'open',schedule_config:{frequency:'daily',hour:8,minute:0}};
qa.scheduleWrites=[];qa.backupWrites=[];qa.fail='';
api=async(path,options={})=>{
 if(path==='/api/settings/ai-enrichment-schedule'){
  if(qa.fail){qa.fail='';throw new Error('Synthetic network failure');}
  if(options.method==='PUT'){qa.saved=JSON.parse(options.body);qa.scheduleWrites.push(qa.saved);}
  return JSON.parse(JSON.stringify(qa.saved));
 }
 if(path==='/api/settings/backup'&&options.method==='PUT'){
  qa.backupWrites.push(JSON.parse(options.body));return qa.backupWrites.at(-1);
 }
 if(path.endsWith('/status'))return {items:[],active_job:null};
 return {items:[]};
};
loadCacheStatus=async()=>{};
qa.field=name=>$('aiScheduleEditor').querySelector('[data-schedule-field='+name+']');
qa.change=(name,value)=>{qa.field(name).value=value;qa.field(name).dispatchEvent(new Event('change',{bubbles:true}));};
qa.check=(name,values)=>$('aiScheduleEditor').querySelectorAll('[data-schedule-field='+name+']').forEach(input=>{input.checked=values.includes(Number(input.value));input.dispatchEvent(new Event('change',{bubbles:true}));});
openModal('aiEnrichmentModal');$('aiScheduleEditor').closest('details').open=true;
''')
    evaluate("loadAISchedule()")
    return command, evaluate


@pytest.mark.parametrize("language,width", [("en", 1440), ("he", 1440), ("en", 390), ("he", 390)])
def test_all_five_ai_frequencies_save_reload_localization_and_layout(tmp_path, chromium, language, width):
    command, evaluate = ready(tmp_path, chromium, language, width)
    assert evaluate("qa.field('enabled').checked") is False
    assert evaluate("qa.field('frequency').disabled") is True
    evaluate("$('aiScheduleScope').value='all';$('aiScheduleScope').dispatchEvent(new Event('change',{bubbles:true}));qa.field('enabled').click();qa.change('timezone','Asia/Jerusalem');")
    for frequency in ["minutely", "hourly", "daily", "weekly", "monthly"]:
        evaluate(f"qa.change('frequency',{json.dumps(frequency)});qa.change('interval','2');qa.change('hour','21');qa.change('minute','47');qa.check('weekdays',[0,6]);qa.check('month_days',[1,15,31]);$('saveAISchedule').click();")
        browser_wait(evaluate, "!$('saveAISchedule').disabled")
        assert evaluate("qa.saved.schedule_config.frequency") == frequency
        assert evaluate("qa.saved.timezone") == "Asia/Jerusalem"
        assert evaluate("qa.saved.position_scope") == "all"
        assert evaluate("qa.saved.language") == language
        evaluate("qa.change('frequency','daily');qa.change('hour','0');$('reloadAISchedule').click();")
        browser_wait(evaluate, "!$('reloadAISchedule').disabled")
        assert evaluate("qa.field('frequency').value") == frequency
        if frequency in ("daily", "weekly", "monthly"):
            assert evaluate("qa.field('hour').value") == "21"
        if frequency == "weekly":
            assert evaluate("ScheduleEditor.read($('aiScheduleEditor')).schedule_config.weekdays") == [0, 6]
        if frequency == "monthly":
            assert evaluate("ScheduleEditor.read($('aiScheduleEditor')).schedule_config.month_days") == [1, 15, 31]
    assert evaluate("qa.scheduleWrites.length") == 5
    assert evaluate("qa.errors") == []
    assert evaluate("innerWidth") == width
    assert evaluate("document.documentElement.scrollWidth-innerWidth") <= 1
    evaluate("$('aiScheduleEditor').scrollIntoView({block:'start'});")
    geometry = evaluate("Array.from($('aiScheduleEditor').querySelectorAll('input,select')).filter(e=>e.offsetWidth&&!e.closest('[hidden]')).map(e=>({field:e.dataset.scheduleField||e.id,width:e.getBoundingClientRect().width,left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right}))")
    assert all(item["left"] >= 0 and item["right"] <= width for item in geometry), geometry
    assert all(item["width"] >= 100 for item in geometry if item["field"] in ("hour", "minute", "timezone")), geometry
    text = evaluate("$('aiScheduleEditor').textContent")
    assert ("Dates that do not occur in a month are skipped." if language == "en" else "תאריכים שאינם קיימים בחודש מסוים ידולגו.") in text
    if language == "he":
        assert all(word not in text for word in ["Frequency", "Automatic schedule", "Every N", "Timezone", "Monday", "Dates that"])
    else:
        assert not any("\u0590" <= letter <= "\u05ff" for letter in text)
    image = tmp_path / f"scheduler-{language}-{width}.png"
    image.write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format": "png"})["data"]))


@pytest.mark.parametrize("language", ["en", "he"])
def test_validation_network_recovery_disabled_draft_and_viewer_permissions(tmp_path, chromium, language):
    command, evaluate = ready(tmp_path, chromium, language)
    evaluate("qa.field('enabled').click();qa.change('frequency','weekly');qa.check('weekdays',[]);$('saveAISchedule').click();")
    assert evaluate("qa.scheduleWrites.length") == 0
    assert evaluate("document.activeElement.dataset.scheduleField") == "weekdays"
    assert evaluate("$('aiScheduleStatus').textContent") == ("Choose at least one day of the week." if language == "en" else "יש לבחור לפחות יום אחד בשבוע.")
    evaluate("qa.change('frequency','monthly');qa.check('month_days',[]);$('saveAISchedule').click();")
    assert evaluate("qa.scheduleWrites.length") == 0
    assert evaluate("document.activeElement.dataset.scheduleField") == "month_days"
    evaluate("qa.change('frequency','daily');qa.change('hour','24');$('saveAISchedule').click();")
    assert evaluate("qa.scheduleWrites.length") == 0
    assert evaluate("document.activeElement.dataset.scheduleField") == "hour"
    evaluate("qa.change('hour','18');qa.change('timezone','Bad/Timezone');$('saveAISchedule').click();")
    assert evaluate("qa.scheduleWrites.length") == 0
    assert evaluate("document.activeElement.dataset.scheduleField") == "timezone"
    # Disabling automation must remain possible even when its draft is invalid.
    evaluate("qa.field('enabled').click();$('saveAISchedule').click();")
    browser_wait(evaluate, "qa.scheduleWrites.length===1")
    assert evaluate("qa.saved.enabled") is False
    evaluate("qa.fail='network';$('reloadAISchedule').click();")
    browser_wait(evaluate, "!$('reloadAISchedule').disabled")
    assert ("Reload schedule" if language == "en" else "טעינת התזמון מחדש") in evaluate("$('aiScheduleStatus').textContent")
    evaluate("$('reloadAISchedule').click();")
    browser_wait(evaluate, "!$('reloadAISchedule').disabled")
    evaluate("state.auth.user.role='Viewer';loadAISchedule()")
    assert evaluate("Array.from($('aiScheduleEditor').querySelectorAll('[data-schedule-field]')).every(e=>e.disabled)")
    assert evaluate("!$('aiScheduleScope').disabled&&$('saveAISchedule').disabled")
    evaluate("saveAISchedule()")
    assert evaluate("qa.scheduleWrites.length") == 1
    assert evaluate("qa.errors") == []


def test_backup_uses_shared_editor_timezone_roundtrip_and_keyboard(tmp_path, chromium):
    command, evaluate = ready(tmp_path, chromium)
    evaluate("closeModal($('aiEnrichmentModal'));state.backupSettings={enabled:true,timezone:'UTC',schedule_config:{frequency:'daily',hour:8,minute:0},missed_policy:'wait'};$('backupEnabled').value='true';openModal('backupScheduleModal');")
    evaluate("qa.backupField=name=>$('backupScheduleEditor').querySelector('[data-schedule-field='+name+']');qa.backupField('frequency').value='hourly';qa.backupField('frequency').dispatchEvent(new Event('change',{bubbles:true}));qa.backupField('interval').value='3';qa.backupField('minute').value='7';qa.backupField('timezone').value='America/New_York';$('applyBackupSchedule').focus();")
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
    assert evaluate("$('backupScheduleModal').hidden")
    assert evaluate("$('backupTimezone').value") == "America/New_York"
    assert evaluate("state.backupSettings.schedule_config.interval") == 3
    assert "America/New_York" in evaluate("$('backupScheduleSummary').textContent")
    evaluate("saveBackupSettings()")
    assert evaluate("qa.backupWrites[0].timezone") == "America/New_York"
    assert evaluate("qa.backupWrites[0].schedule_config.frequency") == "hourly"
    evaluate("openModal('backupScheduleModal')")
    assert evaluate("qa.backupField('timezone').value") == "America/New_York"
    assert evaluate("qa.backupField('minute').value") == "7"
    assert evaluate("qa.errors") == []


def test_api_all_frequencies_survive_reopen_and_reject_viewer(schedule_environment):
    from fastapi.testclient import TestClient
    from app import main
    from test_auth import _login, _change_password

    client, auth, session, path = schedule_environment
    endpoint = "/api/settings/ai-enrichment-schedule"
    headers = {"X-CSRF-Token": session["csrf_token"]}
    examples = [
        {"frequency": "minutely", "interval": 1},
        {"frequency": "hourly", "interval": 23, "minute": 59},
        {"frequency": "daily", "hour": 23, "minute": 59},
        {"frequency": "weekly", "weekdays": [0, 6], "hour": 5, "minute": 30},
        {"frequency": "monthly", "month_days": [1, 15, 31], "hour": 8, "minute": 0},
    ]
    for config in examples:
        response = client.put(endpoint, headers=headers, json={"enabled": True, "timezone": "America/New_York", "schedule_config": config})
        assert response.status_code == 200, response.text
        persisted = client.get(endpoint).json()
        assert all(persisted["schedule_config"][key] == value for key, value in config.items())
        # Status must read persisted disk state on each request, without a runtime cache.
        assert json.loads((path / "settings.json").read_text())["ai_enrichment_schedule"]["schedule_config"] == persisted["schedule_config"]
        assert persisted["timezone"] == "America/New_York"
    auth.create_user({"first_name": "QA", "last_name": "Viewer", "username": "scheduler-viewer", "password": "QA-Initial-Password-2026!", "role": "Viewer"})
    viewer = TestClient(main.app, base_url="https://localhost:6443")
    viewer_session = _change_password(viewer, _login(viewer, "scheduler-viewer", "QA-Initial-Password-2026!"), "QA-Initial-Password-2026!", "QA-Replaced-Password-2026!")
    assert viewer.get(endpoint).status_code == 200
    assert viewer.put(endpoint, headers={"X-CSRF-Token": viewer_session["csrf_token"]}, json={"enabled": False}).status_code == 403


def test_browser_save_and_reload_roundtrip_to_real_isolated_api(tmp_path, chromium, schedule_environment):
    """Connect the browser's application handlers to actual FastAPI endpoints.

    The localhost HTTP adapter forwards to the isolated authenticated TestClient;
    application routes, authorization, validation and disk persistence are real.
    """
    import re
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from pathlib import Path
    from urllib.parse import unquote, urlsplit

    client, auth, session, settings_path = schedule_environment
    client.headers["X-CSRF-Token"] = session["csrf_token"]
    fixture = cash_browser_document(tmp_path, "en")
    html = fixture.read_text()
    assets = {}
    for index, uri in enumerate(set(re.findall(r'file://[^"\']+', html))):
        path = "/asset" + str(index)
        assets[path] = Path(unquote(urlsplit(uri).path))
        html = html.replace(uri, path)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path.startswith("/api/"):
                response = client.get(self.path)
                self.send_response(response.status_code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(response.content)
                return
            asset = assets.get(self.path)
            self.send_response(200 if self.path == "/" or asset else 404)
            mime = "text/html" if self.path == "/" else "text/css" if asset and asset.suffix == ".css" else "application/javascript"
            self.send_header("Content-Type", mime)
            self.end_headers()
            self.wfile.write(html.encode() if self.path == "/" else asset.read_bytes() if asset else b"")

        def do_PUT(self):
            response = client.put(self.path, content=self.rfile.read(int(self.headers["Content-Length"])), headers={"Content-Type": "application/json"})
            self.send_response(response.status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(response.content)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        command, evaluate = chromium
        command("Page.navigate", {"url": f"http://127.0.0.1:{server.server_port}/"})
        browser_wait(evaluate, "window.qa?.ready===true")
        evaluate(r'''
api=async(path,options={})=>{const response=await fetch(path,{...options,headers:{'Content-Type':'application/json'}});if(!response.ok)throw new Error('HTTP '+response.status);return response.json();};
qa.field=name=>$('aiScheduleEditor').querySelector('[data-schedule-field='+name+']');
qa.change=(name,value)=>{qa.field(name).value=value;qa.field(name).dispatchEvent(new Event('change',{bubbles:true}));};
openModal('aiEnrichmentModal');$('aiScheduleEditor').closest('details').open=true;
''')
        evaluate("loadAISchedule()")
        evaluate("qa.field('enabled').click();qa.change('timezone','America/New_York');")
        endpoint = "/api/settings/ai-enrichment-schedule"
        for frequency in ["minutely", "hourly", "daily", "weekly", "monthly"]:
            evaluate(f"qa.change('frequency',{json.dumps(frequency)});qa.change('interval','3');qa.change('hour','17');qa.change('minute','42');saveAISchedule()")
            response = client.get(endpoint).json()
            assert response["enabled"] is True and response["schedule_config"]["frequency"] == frequency
            assert response["timezone"] == "America/New_York"
            persisted = json.loads((settings_path / "settings.json").read_text())["ai_enrichment_schedule"]
            assert persisted["schedule_config"] == response["schedule_config"]
            evaluate("qa.change('frequency','daily');qa.change('hour','0');loadAISchedule()")
            assert evaluate("qa.field('frequency').value") == frequency
        assert evaluate("qa.errors") == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
