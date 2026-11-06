"""Independent lifecycle checks; mocked geometry does not replace browser QA."""

import subprocess
from pathlib import Path

from test_shared_cash_risk_qa import app_functions


ROOT = Path(__file__).resolve().parents[1]


def run_layout_check(check):
    setup = r"""
const assert = require('node:assert/strict');
const state = {dashboard:{edit:false,order:['first','second'],hidden:['other']}};
const frames = new Map();let frameId=0;
function requestAnimationFrame(callback){frames.set(++frameId,callback);return frameId;}
function cancelAnimationFrame(id){frames.delete(id);}
function flush(){const queued=[...frames.values()];frames.clear();queued.forEach(cb=>cb());}
function getComputedStyle(){return {rowGap:'12px',gridAutoRows:'1px'};}
class ResizeObserver {
  static instances=[];
  constructor(callback){this.callback=callback;this.targets=[];this.disconnected=false;ResizeObserver.instances.push(this);}
  observe(target){this.targets.push(target);}
  disconnect(){this.disconnected=true;this.targets=[];}
  notify(targets){this.callback(targets.map(target=>({target})));}
}
function classes(...values){const set=new Set(values);return {contains:v=>set.has(v),remove:v=>set.delete(v),toggle(v,yes){yes?set.add(v):set.delete(v);}};}
function card(height){return {height,style:{gridRowEnd:''},classList:classes('dashboard-widget'),getBoundingClientRect(){return {height:this.height};}};}
function board(width,cards){return {clientWidth:width,children:cards,dataset:{},classList:classes()};}
let dashboardLayoutObserver=null,dashboardLayoutFrame=0;
"""
    script = setup + app_functions("layoutDashboardCards", "observeDashboardLayout") + check
    result = subprocess.run(["node"], input=script, text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr


def test_async_card_height_and_container_width_reflow_without_data_or_order_changes():
    run_layout_check(r"""
const first=card(150),second=card(390),view=board(1400,[first,second]);
const saved=JSON.stringify(state);
observeDashboardLayout(view);
const observer=ResizeObserver.instances.at(-1);
assert.deepEqual(observer.targets,[view,first,second]);
const originalSpan=first.style.gridRowEnd;
first.height=930;observer.notify([first]);observer.notify([first,view]);
assert.equal(frames.size,1,'coalesce concurrent enrichment changes');
flush();
assert.ok(parseInt(first.style.gridRowEnd.slice(5))>parseInt(originalSpan.slice(5)));
first.height=100;observer.notify([first]);flush();
assert.ok(parseInt(first.style.gridRowEnd.slice(5))<parseInt(originalSpan.slice(5)));
observer.notify([view]);assert.equal(frames.size,0,'own height output must not schedule a layout loop');
view.clientWidth=350;observer.notify([view]);flush();
assert.equal(view.classList.contains('dashboard-packed'),false);
assert.equal(first.style.gridRowEnd,'');assert.equal(second.style.gridRowEnd,'');
view.clientWidth=960;observer.notify([view]);flush();
assert.equal(view.classList.contains('dashboard-packed'),true);
assert.notEqual(first.style.gridRowEnd,'');
assert.deepEqual(view.children,[first,second]);
assert.equal(JSON.stringify(state),saved);
""")


def test_area_replacement_edit_and_empty_states_disconnect_old_observers_and_frames():
    run_layout_check(r"""
const first=card(150),view=board(1400,[first]);
observeDashboardLayout(view);
const oldObserver=ResizeObserver.instances.at(-1);
first.height=500;oldObserver.notify([first]);assert.equal(frames.size,1);
const replacement=card(300);view.children=[replacement];observeDashboardLayout(view);
assert.equal(oldObserver.disconnected,true);assert.equal(frames.size,0);
const areaObserver=ResizeObserver.instances.at(-1);
assert.deepEqual(areaObserver.targets,[view,replacement]);
state.dashboard.edit=true;view.children=[{classList:classes('dashboard-section')}];
observeDashboardLayout(view);
assert.equal(areaObserver.disconnected,true);
assert.equal(view.classList.contains('dashboard-packed'),false);
assert.equal(view.dataset.layout,undefined);
assert.equal(ResizeObserver.instances.length,2,'edit mode must not install an observer');
state.dashboard.edit=false;view.children=[];observeDashboardLayout(view);
assert.equal(ResizeObserver.instances.length,2,'empty state must not install an observer');
assert.equal(view.classList.contains('dashboard-packed'),false);
""")


def test_resize_observer_unavailable_still_renders_initial_layout():
    run_layout_check(r"""
ResizeObserver=undefined;
const view=board(960,[card(150),card(300)]);
observeDashboardLayout(view);
assert.equal(view.classList.contains('dashboard-packed'),true);
assert.ok(view.children.every(c=>c.style.gridRowEnd.startsWith('span ')));
""")
