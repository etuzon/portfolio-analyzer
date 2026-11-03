"""Heatmap discoverability and existing saved dashboard-layout compatibility."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_heatmap_is_a_default_investment_cell_and_migrates_existing_layouts():
    app = (ROOT / "web/app.js").read_text()
    catalog = app[app.index("const DASHBOARD_WIDGETS ="):app.index("const DASHBOARD_STORAGE_KEY")]
    sections = app[app.index("const DASHBOARD_SECTIONS ="):app.index("const SUPPORT_RESISTANCE_PERIODS")]
    defaults = app[app.index("function defaultDashboard()"):app.index("function saveDashboardSettings()")]
    visibility = app[app.index("function visibleDashboardWidgets()"):app.index("function dashboardWidgetConfig(")]
    script = r'''
const assert=require('node:assert/strict');const state={};let saved={};
const DASHBOARD_STORAGE_KEY='layout',DASHBOARD_ACCOUNT_STORAGE_KEY='account',DASHBOARD_LONG_TERM_STORAGE_KEY='longterm';
const localStorage={getItem:key=>key==='layout'?JSON.stringify(saved):null};
''' + catalog + sections + defaults + visibility + r'''
loadDashboardSettings();
assert.equal(state.dashboard.mode,'basic');
assert.ok(visibleDashboardWidgets().some(w=>w.id==='stock_heatmap'));
state.dashboard.area='investments';assert.ok(visibleDashboardWidgets().some(w=>w.id==='stock_heatmap'));
state.dashboard.area='long_term';assert.ok(!visibleDashboardWidgets().some(w=>w.id==='stock_heatmap'));
saved={mode:'expanded',area:'investments',widgets:[{id:'portfolio_value',view:'hidden',order:20},{id:'top_holdings',view:'expanded',order:0}]};
loadDashboardSettings();assert.equal(state.dashboard.widgets.find(w=>w.id==='portfolio_value').view,'hidden');
assert.equal(state.dashboard.widgets.find(w=>w.id==='top_holdings').order,0);
assert.ok(visibleDashboardWidgets().some(w=>w.id==='stock_heatmap'));
saved.widgets.push({id:'stock_heatmap',view:'hidden',order:100});loadDashboardSettings();
assert.ok(!visibleDashboardWidgets().some(w=>w.id==='stock_heatmap'));
'''
    result = subprocess.run(["node"], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_dashboard_mount_and_background_load_replace_research_modal_and_help():
    app = (ROOT / "web/app.js").read_text()
    html = (ROOT / "web/index.html").read_text()
    translations = (ROOT / "web/i18n.js").read_text()
    assert 'heatmapModal' not in app + html
    assert 'stock_heatmap: () => renderDashboardHeatmap()' in app
    renderer = app[app.index('function renderAnalytics('):app.index('function renderPortfolio(')]
    assert renderer.count('if (typeof renderHeatmap === "function") renderHeatmap();') == 2
    loader = app[app.index('async function loadPortfolio('):app.index('async function loadPortfolio(')+10000]
    assert 'if (typeof loadHeatmap === "function" && (!data.refresh_pending || enrichmentRetry === 0)) loadHeatmap();' in loader
    assert 'await loadHeatmap()' not in loader
    dashboard_help = html[html.index('<span>Dashboard</span>'):html.index('<span>Portfolio Data</span>')]
    assert '<h3>Portfolio stocks heatmap</h3>' in dashboard_help
    assert 'Research → Stock heatmap' not in html + translations
    assert 'Loading remains inside the card' in html
    assert '"Portfolio stocks heatmap": "מפת חום של מניות התיק"' in translations


def test_only_investment_account_shares_can_mount_the_heatmap_without_other_empty_cards():
    source = (ROOT / "web/app.js").read_text()
    renderer = source[source.index('function renderAnalytics('):source.index('function renderPortfolio(')]
    script = r'''
const assert=require('node:assert/strict');
const state={localAccounts:[{id:'invest',type:'Investment'},{id:'esop',type:'ESOP'}],allPortfolioItems:[{holding:{asset_class:'RSU',account_id:'invest',quantity:10}}],localFunds:[],dashboard:{area:'all',edit:false}};
const board={innerHTML:''};const $=()=>board;
const preserveRenderedInteraction=()=>()=>{},dashboardScrollPositions=()=>new Map(),restoreDashboardScrollPositions=()=>{};
const renderDashboardControls=()=>{},assetMixGroups=()=>[],currencyAllocationGroups=()=>[],sum=()=>0;
const visibleDashboardWidgets=()=>[{id:'stock_heatmap'},{id:'portfolio_value'}];
const withDashboardToolbar=(w,html)=>html,renderDashboardHeatmap=()=>'<div>portfolio stock heatmap</div>';
let mounted=0;const renderHeatmap=()=>mounted++;
''' + renderer + r'''
renderAnalytics([]);assert.ok(board.innerHTML.includes('portfolio stock heatmap'));assert.equal(mounted,1);
state.dashboard.area='investments';renderAnalytics([]);assert.ok(board.innerHTML.includes('portfolio stock heatmap'));
state.allPortfolioItems[0].holding.account_id='esop';renderAnalytics([]);assert.ok(board.innerHTML.includes('No portfolio data'));
state.allPortfolioItems=[];renderAnalytics([]);assert.ok(board.innerHTML.includes('No portfolio data'));
'''
    result = subprocess.run(["node"], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
