"""Shared schedule editor behavior in disposable Chromium; no service calls."""
import json
from pathlib import Path

import pytest

from test_native_account_history_qa import chromium

ROOT = Path(__file__).resolve().parents[1]


def editor(chromium):
    _, evaluate = chromium
    evaluate("document.body.innerHTML='<div id=editor></div>'")
    evaluate((ROOT / "web/scheduler.js").read_text())
    evaluate("window.container=document.getElementById('editor');window.field=name=>container.querySelector('[data-schedule-field='+name+']');window.change=(name,value)=>{field(name).value=value;field(name).dispatchEvent(new Event('change',{bubbles:true}));}")
    return evaluate


def test_shared_editor_frequencies_preserve_drafts_and_validate(chromium):
    evaluate = editor(chromium)
    evaluate("ScheduleEditor.mount(container,{enabled:true,timezone:'Asia/Jerusalem',schedule_config:{frequency:'weekly',hour:19,minute:35,weekdays:[1,4],month_days:[15,31]}})")
    assert evaluate("ScheduleEditor.read(container).schedule_config.weekdays") == [1, 4]
    for frequency in ("minutely", "hourly", "daily", "monthly", "weekly"):
        evaluate(f"change('frequency',{json.dumps(frequency)})")
        assert evaluate("ScheduleEditor.read(container).schedule_config.frequency") == frequency
    assert evaluate("ScheduleEditor.read(container).schedule_config.hour") == 19
    evaluate("container.querySelectorAll('[data-schedule-field=weekdays]').forEach(input=>input.checked=false)")
    assert evaluate("(()=>{try{ScheduleEditor.read(container)}catch(error){return error.message}})()") == "Choose at least one day of the week."
    assert evaluate("document.activeElement.dataset.scheduleField") == "weekdays"
    evaluate("change('frequency','hourly');change('interval','24')")
    assert evaluate("(()=>{try{ScheduleEditor.read(container)}catch(error){return error.message}})()") == "Enter a whole number within the displayed range."
    evaluate("change('interval','2');change('timezone','invalid/timezone')")
    assert "valid timezone" in evaluate("(()=>{try{ScheduleEditor.read(container)}catch(error){return error.message}})()")


def test_relocalize_preserves_invalid_draft_without_read_validation(chromium):
    evaluate = editor(chromium)
    evaluate("ScheduleEditor.mount(container,{enabled:true,schedule_config:{frequency:'monthly',month_days:[]}});change('hour','22');ScheduleEditor.relocalize(container,text=>'translated:'+text)")
    assert evaluate("field('hour').value") == "22"
    evaluate("change('hour','');ScheduleEditor.relocalize(container,text=>'translated:'+text)")
    assert evaluate("field('hour').value") == ""
    evaluate("change('hour','22')")
    assert evaluate("container.querySelectorAll('[data-schedule-field=month_days]:checked').length") == 0
    assert evaluate("container.textContent.includes('translated:Automatic schedule')")
    assert evaluate("(()=>{try{ScheduleEditor.read(container)}catch(error){return error.message}})()") == "translated:Choose at least one day of the month."


@pytest.mark.parametrize("width", [390, 1400])
def test_editor_reflows_and_readonly_controls_are_disabled(chromium, width):
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    evaluate = editor(chromium)
    styles = (ROOT / "web/styles.css").read_text()
    # The full application stylesheet without external font requests.
    import re
    styles = re.sub(r'@import\s+url\([^;]+;', '', styles)
    evaluate(f"document.head.appendChild(Object.assign(document.createElement('style'),{{textContent:{json.dumps(styles)}}}))")
    evaluate("ScheduleEditor.mount(container,{enabled:true,schedule_config:{frequency:'monthly'}},{editable:false});document.documentElement.dir='rtl'")
    assert evaluate("Array.from(container.querySelectorAll('input,select')).every(input=>input.disabled)")
    assert evaluate("document.documentElement.scrollWidth<=window.innerWidth")
    assert evaluate("field('hour').getBoundingClientRect().width>=100")
