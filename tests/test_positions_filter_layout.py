"""Holdings filter proportions using real markup/CSS and synthetic labels only."""
import base64
import json
from pathlib import Path

import pytest

from test_account_cash_update_qa import browser_wait
from test_native_account_history_qa import chromium


ROOT = Path(__file__).resolve().parents[1]
ORDER = ["positionPerson", "positionAccountType", "positionAccount", "positionStock",
         "tradeHistorySearch", "tradeHistoryPositionStatus", "positionSort", "positionSortDirection",
         "resetPositionFilters"]


def document(tmp_path, language):
    source = (ROOT / "web/index.html").read_text()
    modal = source[source.index('    <div id="positionsModal"'):source.index('    <div id="tradeHistoryDetailModal"')]
    modal = modal.replace('id="positionsModal" class="modal" hidden', 'id="positionsModal" class="modal"')
    labels = {"en": ["Alexandra Johnson", "Interactive Brokers · Main account", "91282CKD2 · U.S. Treasury 2029"],
              "he": ["אלכסנדרה לוי", "אינטראקטיב ברוקרס · חשבון ראשי", "91282CKD2 · אג״ח ממשלת ארה״ב"]}[language]
    setup = '''
const labels=LABELS;
for(const [index,id] of ['positionPerson','positionAccount','positionStock'].entries()){
 document.getElementById(id).replaceChildren(new Option(labels[index],'synthetic',true,true));
}
window.PortfolioI18n.applyToDocument(LANGUAGE);
document.getElementById('tradeHistoryTitle').focus();
window.qaReady=true;
'''.replace("LABELS", json.dumps(labels)).replace("LANGUAGE", json.dumps(language))
    page = tmp_path / "positions-layout.html"
    page.write_text('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                    + f'<link rel="stylesheet" href="{(ROOT / "web/styles.css").as_uri()}"></head><body>'
                    + modal + f'<script src="{(ROOT / "web/i18n.js").as_uri()}"></script><script>'
                    + setup + "</script></body></html>")
    return page


@pytest.mark.parametrize("width,language", [(1280, "en"), (1280, "he"), (800, "en"), (800, "he"), (390, "en"), (390, "he")])
def test_field_proportions_and_task_order_survive_direction_and_narrow_layout(tmp_path, chromium, width, language):
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qaReady===true")
    evaluate("document.fonts.ready")
    geometry = evaluate('''(()=>{
 const controls=document.querySelector('.trade-history-controls');
 const result={};for(const field of controls.querySelectorAll('select,input,button')){
  if(field.hidden)continue;const r=field.getBoundingClientRect();
  result[field.id]={x:r.x,y:r.y,width:r.width,right:r.right,bottom:r.bottom};
 }
 return {fields:result,scroll:controls.scrollWidth,client:controls.clientWidth,
   order:[...controls.querySelectorAll('select,input,button')].filter(e=>!e.hidden).map(e=>e.id),
   direction:document.documentElement.dir};
})()''')
    assert geometry["order"] == ORDER
    assert geometry["direction"] == ("rtl" if language == "he" else "ltr")
    assert geometry["scroll"] <= geometry["client"] + 1, geometry
    assert all(item["x"] >= 0 and item["right"] <= width for item in geometry["fields"].values()), geometry
    fields = geometry["fields"]
    if width == 1280:
        assert fields["positionAccount"]["width"] > fields["positionAccountType"]["width"] * 1.4
        assert fields["positionStock"]["width"] > fields["positionAccountType"]["width"] * 1.3
        assert fields["tradeHistorySearch"]["width"] > fields["tradeHistoryPositionStatus"]["width"] * 1.3
        assert fields["positionPerson"]["y"] == fields["positionStock"]["y"]
        assert fields["tradeHistorySearch"]["bottom"] == fields["resetPositionFilters"]["bottom"]
    else:
        assert fields["positionAccount"]["width"] >= fields["positionAccountType"]["width"]
        assert fields["positionStock"]["width"] == fields["positionAccount"]["width"]
        assert fields["tradeHistorySearch"]["width"] >= fields["positionSortDirection"]["width"]
    # Keyboard flow follows scope -> security -> refinement -> sorting -> reset.
    evaluate("document.getElementById('positionPerson').focus()")
    actual = [evaluate("document.activeElement.id")]
    for _ in ORDER[1:]:
        command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
        command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
        actual.append(evaluate("document.activeElement.id"))
    assert actual == ORDER
    shot = command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    (tmp_path / f"positions-filters-{language}-{width}.png").write_bytes(base64.b64decode(shot["data"]))
