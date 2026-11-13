"""Independent scope-schedule acceptance with synthetic, temporary state only."""
import json
import base64
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import main
from test_auth import _change_password, _login
from test_scheduling import schedule_environment
from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium


ENDPOINT = "/api/settings/ai-enrichment-schedule"


def rows(response):
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["items"]) == 2
    assert "owner_id" not in json.dumps(result)
    return {item["position_scope"]: item for item in result["items"]}


def save(client, session, scope, **changes):
    return client.put(ENDPOINT, headers={"X-CSRF-Token": session["csrf_token"]},
                      json={"position_scope": scope, **changes})


def test_independent_scope_schedules_persist_and_invalid_changes_are_atomic(schedule_environment):
    client, auth, session, path = schedule_environment
    assert set(rows(client.get(ENDPOINT))) == {"open", "all"}
    assert all(not item["enabled"] for item in rows(client.get(ENDPOINT)).values())
    examples = {
        "open": {"enabled": True, "timezone": "Asia/Jerusalem", "language": "he",
                 "schedule_config": {"frequency": "weekly", "weekdays": [0, 6], "hour": 9, "minute": 25}},
        "all": {"enabled": True, "timezone": "America/New_York", "language": "en",
                "schedule_config": {"frequency": "monthly", "month_days": [1, 31], "hour": 21, "minute": 47}},
    }
    for scope, payload in examples.items():
        assert save(client, session, scope, **payload).status_code == 200
    reopened = TestClient(main.app, base_url="https://localhost:6443")
    reopened.cookies.update(client.cookies)
    persisted = rows(reopened.get(ENDPOINT))
    for scope, payload in examples.items():
        assert all(persisted[scope][key] == value for key, value in payload.items())
        selected = reopened.get(ENDPOINT, params={"position_scope": scope}).json()
        assert selected["position_scope"] == scope
        assert selected["schedule_config"] == payload["schedule_config"]
    before = (path / "settings.json").read_bytes()
    for bad in [{"timezone": "Invalid/Zone"}, {"enabled": "true"},
                {"schedule_config": {"frequency": "weekly", "weekdays": []}}, {"language": "fr"}]:
        assert save(client, session, "all", **bad).status_code == 400
        assert (path / "settings.json").read_bytes() == before
    assert save(client, session, "closed", enabled=True).status_code == 400
    assert client.get(ENDPOINT, params={"position_scope": "closed"}).status_code == 400
    disabled = rows(save(client, session, "open", enabled=False,
                         timezone="Invalid/Zone", schedule_config={"frequency": "monthly", "month_days": []}))
    assert disabled["open"]["enabled"] is False
    assert disabled["open"]["schedule_config"] == examples["open"]["schedule_config"]
    assert disabled["all"] == persisted["all"]
    assert "cookie" not in (path / "settings.json").read_text()
    assert "csrf" not in (path / "settings.json").read_text()


@pytest.mark.parametrize("scope", ["open", "all"])
def test_legacy_single_schedule_migrates_its_actual_scope_and_owner(schedule_environment, scope):
    client, auth, session, path = schedule_environment
    legacy = {"enabled": True, "position_scope": scope, "timezone": "UTC", "language": "he",
              "owner_id": "legacy-owner", "schedule_config": {"frequency": "hourly", "interval": 7, "minute": 14}}
    main.save_runtime_settings({"ai_enrichment_schedule": legacy})
    read = rows(client.get(ENDPOINT))
    other = "all" if scope == "open" else "open"
    assert read[scope]["enabled"] is True
    assert all(read[scope]["schedule_config"][key] == value for key, value in legacy["schedule_config"].items())
    assert read[scope]["language"] == "he" and read[other]["enabled"] is False
    assert client.get(ENDPOINT).json()["position_scope"] == scope
    assert save(client, session, other, enabled=True, timezone="Asia/Jerusalem").status_code == 200
    disk = json.loads((path / "settings.json").read_text())["ai_enrichment_schedules"]
    assert all(disk[scope][key] == value for key, value in legacy.items() if key != "schedule_config")
    assert disk[scope]["schedule_config"] == read[scope]["schedule_config"]
    assert disk[other]["owner_id"] == session["user"]["id"]
    assert rows(client.get(ENDPOINT))[scope] == read[scope]


def test_concurrent_saves_do_not_drop_the_other_scope(schedule_environment):
    client, auth, session, path = schedule_environment
    def update(scope):
        isolated = TestClient(main.app, base_url="https://localhost:6443")
        isolated.cookies.update(client.cookies)
        return save(isolated, session, scope, enabled=True, timezone="UTC",
                    schedule_config={"frequency": "daily", "hour": 6 if scope == "open" else 22, "minute": 13})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["open", "all"]))
    assert all(result.status_code == 200 for result in results)
    final = rows(client.get(ENDPOINT))
    assert final["open"]["schedule_config"]["hour"] == 6
    assert final["all"]["schedule_config"]["hour"] == 22
    assert all(item["enabled"] for item in final.values())


def test_scope_auth_csrf_and_per_scope_saving_owner(schedule_environment):
    client, auth, session, path = schedule_environment
    assert TestClient(main.app).get(ENDPOINT).status_code == 401
    assert client.put(ENDPOINT, json={"enabled": True, "position_scope": "all"}).status_code == 403
    assert save(client, session, "open", enabled=True).status_code == 200
    for role in ["Viewer", "Operator"]:
        username = "scope-" + role.lower()
        auth.create_user({"first_name": "QA", "last_name": role, "username": username,
                          "password": "QA-Initial-Password-2026!", "role": role})
        other = TestClient(main.app, base_url="https://localhost:6443")
        other_session = _change_password(other, _login(other, username, "QA-Initial-Password-2026!"),
                                         "QA-Initial-Password-2026!", "QA-Replaced-Password-2026!")
        assert set(rows(other.get(ENDPOINT))) == {"open", "all"}
        assert save(other, other_session, "all", enabled=True).status_code == (403 if role == "Viewer" else 200)
        assert other.put(ENDPOINT, json={"position_scope": "all", "enabled": False}).status_code == 403
        if role == "Operator":
            disk = json.loads((path / "settings.json").read_text())["ai_enrichment_schedules"]
            assert disk["open"]["owner_id"] == session["user"]["id"]
            assert disk["all"]["owner_id"] == other_session["user"]["id"]


def test_separate_jobs_next_run_and_disabled_scope_removal(schedule_environment, monkeypatch):
    from apscheduler.schedulers.background import BackgroundScheduler
    client, auth, session, path = schedule_environment
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.start(paused=True)
    monkeypatch.setattr(main, "scheduler", scheduler)
    try:
        scheduler.add_job(lambda: None, "interval", days=1, id=main.AI_ENRICHMENT_JOB_ID)
        for scope, hour in [("open", 7), ("all", 19)]:
            assert save(client, session, scope, enabled=True, timezone="UTC",
                        schedule_config={"frequency": "daily", "hour": hour, "minute": 0}).status_code == 200
        assert scheduler.get_job(main.AI_ENRICHMENT_JOB_ID) is None
        status = rows(client.get(ENDPOINT))
        for scope, hour in [("open", 7), ("all", 19)]:
            job = scheduler.get_job(main.AI_ENRICHMENT_JOB_ID + ":" + scope)
            assert job and list(job.args) == [scope] and job.max_instances == 1 and job.coalesce is True
            assert status[scope]["next_run"] == job.next_run_time.isoformat()
            assert job.next_run_time.hour == hour
        assert save(client, session, "open", enabled=False).status_code == 200
        assert scheduler.get_job(main.AI_ENRICHMENT_JOB_ID + ":open") is None
        assert scheduler.get_job(main.AI_ENRICHMENT_JOB_ID + ":all")
        assert rows(client.get(ENDPOINT))["open"]["next_run"] is None
    finally:
        scheduler.shutdown(wait=False)


def test_callbacks_reload_scope_settings_and_current_owner_authorization(schedule_environment, monkeypatch):
    client, auth, session, path = schedule_environment
    owner = session["user"]["id"]
    for scope, language in [("open", "he"), ("all", "en")]:
        assert save(client, session, scope, enabled=True, language=language).status_code == 200
    events = []
    def start(user_id, filters, language, position_scope, *, scheduled_credentials):
        headers, revoke = scheduled_credentials()
        token = headers["cookie"].split("=", 1)[1]
        assert auth.session(token)["user"]["id"] == user_id
        assert filters == {}  # Existing backend controls the bounded enrichment workflow.
        events.append((user_id, language, position_scope))
        revoke()
        assert auth.session(token) is None
    monkeypatch.setattr(main.portfolio_ai_research, "start", start)
    monkeypatch.setattr(main, "_record_log", lambda *args, **kwargs: events.append(kwargs["code"]) if "code" in kwargs else None)
    main.run_scheduled_ai_enrichment("open")
    main.run_scheduled_ai_enrichment("all")
    assert events == [(owner, "he", "open"), (owner, "en", "all")]
    assert save(client, session, "open", enabled=False).status_code == 200
    main.run_scheduled_ai_enrichment("open")
    assert len(events) == 2
    # An enabled job must use current authorization, not its permission at save time.
    with auth._connect() as connection:
        connection.execute("UPDATE app_users SET role = 'Viewer' WHERE id = ?", (owner,))
    main.run_scheduled_ai_enrichment("all")
    assert events[-1] == "owner_not_authorized"


def test_restore_replaces_both_scope_jobs_without_retaining_old_jobs(schedule_environment, monkeypatch):
    client, auth, session, path = schedule_environment
    registered = {main.AI_ENRICHMENT_JOB_ID: "legacy", main.AI_ENRICHMENT_JOB_ID + ":open": "old", main.AI_ENRICHMENT_JOB_ID + ":all": "old"}
    class Scheduler:
        def pause(self): pass
        def resume(self): pass
        def remove_job(self, identifier): registered.pop(identifier, None)
        def add_job(self, callback, trigger, **kwargs): registered[kwargs["id"]] = kwargs
    monkeypatch.setattr(main, "scheduler", Scheduler())
    monkeypatch.setattr(main, "_validated_full_backup_archive", lambda payload: ({}, {}))
    monkeypatch.setattr(main, "write_full_backup", lambda keep: {"filename": "safety.zip"})
    restored = {"ai_enrichment_schedules": {
        "open": {"enabled": False, "position_scope": "open", "owner_id": "restored-open", "timezone": "UTC"},
        "all": {"enabled": True, "position_scope": "all", "owner_id": "restored-all", "timezone": "UTC",
                "schedule_config": {"frequency": "hourly", "interval": 4, "minute": 15}}}}
    monkeypatch.setattr(main, "_apply_full_backup_files", lambda files: main.save_runtime_settings(restored))
    monkeypatch.setattr(main, "load_config", lambda: main.config)
    monkeypatch.setattr(main, "configure_dividend_job", lambda: None)
    assert main.restore_full_backup(b"synthetic archive")["status"] == "restored"
    assert set(registered) == {main.AI_ENRICHMENT_JOB_ID + ":all"}
    assert registered[main.AI_ENRICHMENT_JOB_ID + ":all"]["args"] == ["all"]


def scope_browser(tmp_path, chromium, language="en", width=1440):
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": cash_browser_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate(r'''
qa.saved={
 open:{enabled:true,position_scope:'open',timezone:'Asia/Jerusalem',language:'he',schedule_config:{frequency:'weekly',weekdays:[0,6],hour:9,minute:25},next_run:'2026-12-01T09:25:00+02:00'},
 all:{enabled:true,position_scope:'all',timezone:'America/New_York',language:'en',schedule_config:{frequency:'monthly',month_days:[1,31],hour:21,minute:47},next_run:'2026-12-01T21:47:00-05:00'}
};qa.writes=[];qa.reads=[];qa.fail='';qa.hold=false;
qa.response=scope=>JSON.parse(JSON.stringify({...qa.saved[scope],items:Object.values(qa.saved)}));
api=async(path,options={})=>{
 if(path.startsWith('/api/settings/ai-enrichment-schedule')){
  const draft=options.method==='PUT'?JSON.parse(options.body):null;
  const scope=draft?.position_scope||new URL(path,'http://qa.local').searchParams.get('position_scope')||'open';
  if(draft)qa.writes.push(draft);else qa.reads.push(scope);
  if(qa.hold)await new Promise(resolve=>qa.resolve=resolve);
  if(qa.fail){qa.fail='';throw new Error('Synthetic network failure');}
  if(draft)qa.saved[scope]={...draft,next_run:draft.enabled?qa.saved[scope].next_run:null};
  return qa.response(scope);
 }
 if(path.endsWith('/status'))return {items:[],active_job:null};
 return {items:[]};
};loadCacheStatus=async()=>{};
qa.field=name=>$('aiScheduleEditor').querySelector('[data-schedule-field='+name+']');
qa.change=(name,value)=>{qa.field(name).value=value;qa.field(name).dispatchEvent(new Event('change',{bubbles:true}));};
qa.scope=value=>{$('aiScheduleScope').value=value;$('aiScheduleScope').dispatchEvent(new Event('change',{bubbles:true}));};
openModal('aiEnrichmentModal');$('aiScheduleEditor').closest('details').open=true;
''')
    evaluate("loadAISchedule()")
    return command, evaluate


@pytest.mark.parametrize("language,width", [("en",1440),("he",1440),("en",390),("he",390)])
def test_scope_picker_overview_drafts_localization_and_layout(tmp_path, chromium, language, width):
    command, evaluate = scope_browser(tmp_path, chromium, language, width)
    assert evaluate("qa.field('enabled').compareDocumentPosition($('aiScheduleScope'))&Node.DOCUMENT_POSITION_FOLLOWING")
    assert evaluate("$('aiScheduleScope').compareDocumentPosition(qa.field('frequency'))&Node.DOCUMENT_POSITION_FOLLOWING")
    evaluate("qa.field('enabled').focus();")
    for expected in ["scope", "frequency"]:
        command("Input.dispatchKeyEvent", {"type":"keyDown", "key":"Tab", "code":"Tab", "windowsVirtualKeyCode":9})
        command("Input.dispatchKeyEvent", {"type":"keyUp", "key":"Tab", "code":"Tab", "windowsVirtualKeyCode":9})
        assert evaluate("document.activeElement.id==='aiScheduleScope'?'scope':document.activeElement.dataset.scheduleField") == expected
    overview = evaluate("$('aiScheduleOverview').textContent")
    for timezone in ["Asia/Jerusalem", "America/New_York"]:
        assert timezone in overview
    assert ("Open positions" if language == "en" else "החזקות פתוחות") in overview
    assert ("Open and closed positions" if language == "en" else "פוזיציות פתוחות וסגורות") in overview
    assert "01/12/2026" in overview
    evaluate("qa.field('enabled').scrollIntoView({block:'start'});")
    (tmp_path / f"scope-schedules-initial-{language}-{width}.png").write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format":"png","captureBeyondViewport":True})["data"]))
    # Blank numeric and invalid text values are user drafts, not zero/default.
    evaluate("qa.change('frequency','daily');qa.change('hour','');qa.change('timezone','Invalid draft ');qa.scope('all');")
    assert evaluate("qa.field('frequency').value") == "monthly"
    evaluate("qa.change('minute','12');qa.scope('open');")
    assert evaluate("qa.field('hour').value") == ""
    assert evaluate("qa.field('timezone').value") == "Invalid draft "
    evaluate("qa.scope('all');")
    assert evaluate("qa.field('minute').value") == "12"
    # Explicit reload replaces only this scope, preserving the other draft.
    evaluate("loadAISchedule()")
    assert evaluate("qa.field('minute').value") == "47"
    evaluate("qa.scope('open');")
    assert evaluate("qa.field('hour').value") == ""
    assert evaluate("qa.field('timezone').value") == "Invalid draft "
    opposite = "he" if language == "en" else "en"
    evaluate(f"state.language={json.dumps(opposite)};applyLanguage();")
    assert evaluate("qa.field('hour').value") == ""
    assert evaluate("qa.field('timezone').value") == "Invalid draft "
    evaluate(f"state.language={json.dumps(language)};applyLanguage();closeModal($('aiEnrichmentModal'));openModal('aiEnrichmentModal');")
    assert evaluate("qa.field('hour').value") == ""
    assert evaluate("qa.field('timezone').value") == "Invalid draft "
    # Reload restores this scope before a valid independent save.
    evaluate("loadAISchedule()")
    evaluate("qa.change('frequency','daily');qa.change('hour','7');qa.change('minute','13');saveAISchedule()")
    assert evaluate("qa.writes.length") == 1
    assert evaluate("qa.writes[0].position_scope") == "open"
    assert evaluate("qa.saved.all.schedule_config.minute") == 47
    evaluate("qa.scope('all');")
    assert evaluate("qa.field('minute').value") == "47"
    assert evaluate("innerWidth") == width
    assert evaluate("document.documentElement.scrollWidth-innerWidth") <= 1
    evaluate("$('aiScheduleScope').scrollIntoView({block:'start'});")
    geometry = evaluate("Array.from($('aiEnrichmentModal').querySelectorAll('#aiScheduleScope,#aiScheduleEditor input,#aiScheduleEditor select')).filter(e=>e.offsetWidth&&!e.closest('[hidden]')).map(e=>({field:e.dataset.scheduleField||'scope',left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right,width:e.getBoundingClientRect().width}))")
    assert all(item["left"] >= 0 and item["right"] <= width for item in geometry), geometry
    assert all(item["width"] >= 100 for item in geometry if item["field"] in ["hour","minute","timezone","scope"]), geometry
    copy = evaluate("$('aiScheduleEditor').closest('details').textContent")
    if language == "he":
        assert all(word not in copy for word in ["Open positions", "Open and closed", "Automatic schedule", "Search scope", "Unsaved changes", "Next run", "Reload schedule", "Save schedule"])
    else:
        assert not any("\u0590" <= letter <= "\u05ff" for letter in copy)
    assert evaluate("qa.errors") == []
    screenshot = tmp_path / f"scope-schedules-{language}-{width}.png"
    screenshot.write_bytes(base64.b64decode(command("Page.captureScreenshot", {"format":"png","captureBeyondViewport":True})["data"]))


def test_scope_network_failure_request_lock_and_viewer_browsing(tmp_path, chromium):
    command, evaluate = scope_browser(tmp_path, chromium)
    evaluate("qa.change('hour','17');qa.fail='network';loadAISchedule();")
    assert evaluate("qa.field('hour').value") == "17"
    assert "Reload schedule" in evaluate("$('aiScheduleStatus').textContent")
    evaluate("qa.fail='network';saveAISchedule();")
    assert evaluate("qa.field('hour').value") == "17"
    assert not evaluate("$('aiScheduleScope').disabled||$('saveAISchedule').disabled")
    evaluate("qa.hold=true;window.qa.pending=saveAISchedule();void 0;")
    assert evaluate("$('aiScheduleScope').disabled&&$('saveAISchedule').disabled&&$('reloadAISchedule').disabled")
    assert evaluate("Array.from($('aiScheduleEditor').querySelectorAll('[data-schedule-field]')).every(e=>e.disabled)")
    evaluate("qa.hold=false;qa.resolve();qa.pending;")
    assert not evaluate("$('aiScheduleScope').disabled")
    evaluate("state.auth.user.role='Viewer';loadAISchedule();")
    assert evaluate("$('saveAISchedule').disabled")
    assert not evaluate("$('aiScheduleScope').disabled")
    assert evaluate("Array.from($('aiScheduleEditor').querySelectorAll('[data-schedule-field]')).every(e=>e.disabled)")
    evaluate("qa.scope('all');")
    assert evaluate("qa.field('frequency').value") == "monthly"
    assert evaluate("Array.from($('aiScheduleEditor').querySelectorAll('[data-schedule-field]')).every(e=>e.disabled)")
    count = evaluate("qa.writes.length")
    evaluate("saveAISchedule()")
    assert evaluate("qa.writes.length") == count
    assert evaluate("qa.errors") == []


def test_previous_user_request_cannot_restore_drafts_into_new_session(tmp_path, chromium):
    command, evaluate = scope_browser(tmp_path, chromium)
    evaluate("qa.change('hour','17');qa.hold=true;qa.pending=loadAISchedule();void 0;")
    evaluate("qa.oldResolve=qa.resolve;qa.hold=false;setAuthenticatedSession({user:{id:'qa-new-owner',username:'new-qa',role:'Viewer'},csrf_token:'synthetic-new-token'});")
    assert evaluate("$('aiScheduleEditor').children.length") == 0
    evaluate("loadAISchedule()")
    assert evaluate("qa.field('hour').value") == "9"
    evaluate("qa.oldResolve();qa.pending;")
    assert evaluate("qa.field('hour').value") == "9"
    assert evaluate("aiSchedulesView.userId") == "qa-new-owner"
    assert evaluate("aiSchedulesView.dirty.size") == 0
    assert evaluate("$('saveAISchedule').disabled")
    assert evaluate("qa.errors") == []


def test_browser_dual_scope_save_reload_to_real_temporary_api(tmp_path, chromium, schedule_environment):
    """Actual page handlers use actual authenticated routes and temporary disk."""
    import re
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from pathlib import Path
    from urllib.parse import unquote, urlsplit

    client, auth, session, settings_path = schedule_environment
    client.headers["X-CSRF-Token"] = session["csrf_token"]
    html = cash_browser_document(tmp_path, "en").read_text()
    assets = {}
    for index, uri in enumerate(set(re.findall(r'file://[^"\']+', html))):
        path = "/asset" + str(index)
        assets[path] = Path(unquote(urlsplit(uri).path))
        html = html.replace(uri, path)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
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
            response = client.put(self.path, content=self.rfile.read(int(self.headers["Content-Length"])), headers={"Content-Type":"application/json"})
            self.send_response(response.status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(response.content)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    command, evaluate = chromium
    def reopen():
        command("Page.navigate", {"url": f"http://127.0.0.1:{server.server_port}/"})
        browser_wait(evaluate, "window.qa?.ready===true")
        evaluate(r'''
api=async(path,options={})=>{const response=await fetch(path,{...options,headers:{'Content-Type':'application/json'}});if(!response.ok)throw new Error('HTTP '+response.status);return response.json();};
qa.field=name=>$('aiScheduleEditor').querySelector('[data-schedule-field='+name+']');
qa.change=(name,value)=>{qa.field(name).value=value;qa.field(name).dispatchEvent(new Event('change',{bubbles:true}));};
qa.scope=value=>{$('aiScheduleScope').value=value;$('aiScheduleScope').dispatchEvent(new Event('change',{bubbles:true}));};
openModal('aiEnrichmentModal');$('aiScheduleEditor').closest('details').open=true;
''')
        evaluate("loadAISchedule()")
    try:
        reopen()
        for scope, hour, timezone in [("open", "7", "Asia/Jerusalem"), ("all", "21", "America/New_York")]:
            evaluate(f"qa.scope({json.dumps(scope)});qa.field('enabled').click();qa.change('frequency','daily');qa.change('hour',{json.dumps(hour)});qa.change('timezone',{json.dumps(timezone)});saveAISchedule()")
        reopened = rows(client.get(ENDPOINT))
        assert reopened["open"]["schedule_config"]["hour"] == 7
        assert reopened["all"]["schedule_config"]["hour"] == 21
        disk = json.loads((settings_path / "settings.json").read_text())["ai_enrichment_schedules"]
        assert set(disk) == {"open","all"}
        reopen()
        for scope, hour, timezone in [("open", "7", "Asia/Jerusalem"), ("all", "21", "America/New_York")]:
            evaluate(f"qa.scope({json.dumps(scope)});")
            assert evaluate("qa.field('enabled').checked")
            assert evaluate("qa.field('hour').value") == hour
            assert evaluate("qa.field('timezone').value") == timezone
        evaluate("qa.scope('open');qa.field('enabled').click();saveAISchedule()")
        assert rows(client.get(ENDPOINT))["open"]["enabled"] is False
        assert rows(client.get(ENDPOINT))["all"]["enabled"] is True
        assert evaluate("qa.errors") == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
